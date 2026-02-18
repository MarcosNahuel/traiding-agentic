"""Enhanced risk middleware with quantitative checks.

Wraps the existing risk_manager.py (5 checks) and adds 3 quant checks:
1. Entropy Gate: Blocks trading in noisy markets
2. Regime Check: Blocks contra-trend trades and volatile regimes
3. Kelly/ATR Size Validation: Validates notional doesn't exceed 1.5x recommended

Total: 8 risk checks.
"""

import asyncio
import logging
from typing import Optional

from ..models import RiskCheck, ValidationResult
from ..config import settings
from .risk_manager import validate_proposal as _base_validate
from .entropy_filter import compute_entropy
from .regime_detector import detect_regime
from .position_sizer import compute_position_size
from .telegram_notifier import notify_entropy_blocked, notify_regime_blocked
from ..db import get_supabase

logger = logging.getLogger(__name__)


async def validate_proposal_enhanced(
    trade_type: str,
    symbol: str,
    quantity: float,
    notional: float,
    current_price: float,
) -> ValidationResult:
    """Run all 8 risk checks (5 base + 3 quant)."""

    # Run base 5 checks first
    base_result = await _base_validate(trade_type, symbol, quantity, notional, current_price)
    checks = list(base_result.checks)

    if not settings.quant_enabled:
        return base_result

    interval = settings.quant_primary_interval

    # ── Check 6: Entropy Gate ──
    try:
        entropy = compute_entropy(symbol, interval)
        if entropy:
            entropy_ok = entropy.is_tradable
            checks.append(RiskCheck(
                name="entropy_gate",
                passed=entropy_ok,
                message=(
                    f"Entropy ratio {entropy.entropy_ratio:.3f} "
                    f"({'< ' if entropy_ok else '>= '}{settings.entropy_threshold_ratio})"
                ),
                value=entropy.entropy_ratio,
                limit=settings.entropy_threshold_ratio,
            ))
            if not entropy_ok:
                _log_risk_event("entropy_gate_blocked", "warning",
                    f"Trading blocked: market too noisy (entropy ratio {entropy.entropy_ratio:.3f})",
                    {"symbol": symbol, "entropy_ratio": entropy.entropy_ratio})
                asyncio.ensure_future(notify_entropy_blocked(symbol, entropy.entropy_ratio))
        else:
            checks.append(RiskCheck(
                name="entropy_gate", passed=True,
                message="Entropy check skipped (insufficient data)",
            ))
    except Exception as e:
        logger.warning(f"Entropy check failed: {e}")
        checks.append(RiskCheck(name="entropy_gate", passed=True, message="Entropy check skipped (error)"))

    # ── Check 7: Regime Check ──
    try:
        regime = detect_regime(symbol, interval)
        if regime:
            regime_ok = True
            msg = f"Regime: {regime.regime} (confidence: {regime.confidence:.1f}%)"

            # Block all trades in volatile regime
            if regime.regime == "volatile" and regime.confidence > 60:
                regime_ok = False
                msg = f"Regime volatile with {regime.confidence:.1f}% confidence - trading blocked"

            # Block contra-trend trades in strong trends
            elif regime.regime == "trending_up" and trade_type.lower() == "sell" and regime.confidence > 70:
                regime_ok = False
                msg = f"Selling against strong uptrend ({regime.confidence:.1f}%) - blocked"
            elif regime.regime == "trending_down" and trade_type.lower() == "buy" and regime.confidence > 70:
                regime_ok = False
                msg = f"Buying against strong downtrend ({regime.confidence:.1f}%) - blocked"

            checks.append(RiskCheck(
                name="regime_check",
                passed=regime_ok,
                message=msg,
                value=regime.confidence,
            ))
            if not regime_ok:
                _log_risk_event("regime_warning", "warning", msg, {
                    "symbol": symbol, "regime": regime.regime, "confidence": regime.confidence,
                })
                asyncio.ensure_future(notify_regime_blocked(symbol, regime.regime, regime.confidence, msg))
        else:
            checks.append(RiskCheck(
                name="regime_check", passed=True,
                message="Regime check skipped (insufficient data)",
            ))
    except Exception as e:
        logger.warning(f"Regime check failed: {e}")
        checks.append(RiskCheck(name="regime_check", passed=True, message="Regime check skipped (error)"))

    # ── Check 8: Kelly/ATR Size Validation ──
    try:
        sizing = await compute_position_size(symbol, interval)
        if sizing:
            max_allowed = sizing.recommended_size_usd * 1.5
            size_ok = notional <= max_allowed
            checks.append(RiskCheck(
                name="quant_size_validation",
                passed=size_ok,
                message=(
                    f"Notional ${notional:.2f} vs recommended ${sizing.recommended_size_usd:.2f} "
                    f"(max ${max_allowed:.2f}, method: {sizing.method})"
                ),
                value=notional,
                limit=max_allowed,
            ))
            if not size_ok:
                _log_risk_event("kelly_size_override", "warning",
                    f"Position size ${notional:.2f} exceeds 1.5x recommended ${sizing.recommended_size_usd:.2f}",
                    {"symbol": symbol, "notional": notional, "recommended": sizing.recommended_size_usd})
        else:
            checks.append(RiskCheck(
                name="quant_size_validation", passed=True,
                message="Size validation skipped (no sizing data)",
            ))
    except Exception as e:
        logger.warning(f"Size validation failed: {e}")
        checks.append(RiskCheck(name="quant_size_validation", passed=True, message="Size validation skipped (error)"))

    # Recalculate overall result
    all_passed = all(c.passed for c in checks)
    rejection_reason = next((c.message for c in checks if not c.passed), None)

    # Recalculate risk score (keep base scoring + penalty for quant failures)
    score = base_result.risk_score
    quant_failures = sum(1 for c in checks[len(base_result.checks):] if not c.passed)
    score += quant_failures * 15  # 15 points per quant failure
    score = min(score, 100.0)

    auto_approved = all_passed and notional < 100 and base_result.auto_approved

    return ValidationResult(
        approved=all_passed,
        auto_approved=auto_approved,
        risk_score=score,
        checks=checks,
        rejection_reason=rejection_reason,
    )


def _log_risk_event(event_type: str, severity: str, message: str, details: dict) -> None:
    """Log a quant risk event to DB."""
    try:
        supabase = get_supabase()
        supabase.table("risk_events").insert({
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "details": details,
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to log risk event: {e}")
