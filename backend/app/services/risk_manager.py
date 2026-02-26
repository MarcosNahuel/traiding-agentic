from typing import List, Optional
from ..models import RiskCheck, ValidationResult
from ..db import get_supabase
from ..config import settings
import logging

logger = logging.getLogger(__name__)


def _risk_score(checks: List[RiskCheck], notional: float) -> float:
    """Calculate 0-100 risk score. Higher = riskier."""
    score = 0.0
    size_ratio = min(notional / settings.risk_max_position_size, 1.0)
    score += size_ratio * 40
    failed = sum(1 for c in checks if not c.passed)
    score += failed * 20
    return min(score, 100.0)


async def validate_proposal(
    trade_type: str,
    symbol: str,
    quantity: float,
    notional: float,
    current_price: float,
) -> ValidationResult:
    checks: List[RiskCheck] = []
    supabase = get_supabase()

    # 1. Position size
    size_ok = settings.risk_min_position_size <= notional <= settings.risk_max_position_size
    checks.append(RiskCheck(
        name="position_size",
        passed=size_ok,
        message=f"Position size ${notional:.2f} {'ok' if size_ok else f'must be ${settings.risk_min_position_size}-${settings.risk_max_position_size}'}",
        value=notional,
        limit=settings.risk_max_position_size,
    ))

    # 2. Open positions count
    open_resp = supabase.table("positions").select("id").eq("status", "open").execute()
    open_count = len(open_resp.data) if open_resp.data else 0
    positions_ok = open_count < settings.risk_max_open_positions
    checks.append(RiskCheck(
        name="max_open_positions",
        passed=positions_ok,
        message=f"{open_count}/{settings.risk_max_open_positions} open positions",
        value=float(open_count),
        limit=float(settings.risk_max_open_positions),
    ))

    # 3. Symbol concentration (no duplicate positions)
    if trade_type.lower() == "buy":
        sym_resp = supabase.table("positions").select("id").eq("symbol", symbol).eq("status", "open").execute()
        sym_count = len(sym_resp.data) if sym_resp.data else 0
        sym_ok = sym_count < settings.risk_max_positions_per_symbol
        checks.append(RiskCheck(
            name="symbol_concentration",
            passed=sym_ok,
            message=f"{'No existing' if sym_ok else 'Already have'} position in {symbol}",
            value=float(sym_count),
            limit=float(settings.risk_max_positions_per_symbol),
        ))

    # 4. Account balance & utilization
    try:
        from . import binance_client
        account = await binance_client.get_account()
        balances = {b["asset"]: float(b["free"]) for b in account.get("balances", [])}
        usdt_free = balances.get("USDT", 0.0)

        balance_ok = usdt_free >= notional
        checks.append(RiskCheck(
            name="account_balance",
            passed=balance_ok,
            message=f"USDT available: ${usdt_free:.2f}, need ${notional:.2f}",
            value=usdt_free,
            limit=notional,
        ))

        # Utilization
        total_in_positions = sum(
            float(p.get("entry_notional", 0)) for p in (
                supabase.table("positions").select("entry_notional").eq("status", "open").execute().data or []
            )
        )
        total_balance = usdt_free + total_in_positions
        utilization = total_in_positions / total_balance if total_balance > 0 else 0
        util_ok = utilization < settings.risk_max_account_utilization
        checks.append(RiskCheck(
            name="account_utilization",
            passed=util_ok,
            message=f"Utilization {utilization*100:.1f}% (max {settings.risk_max_account_utilization*100:.0f}%)",
            value=utilization,
            limit=settings.risk_max_account_utilization,
        ))
    except Exception as e:
        logger.warning(f"Could not fetch account: {e}")
        checks.append(RiskCheck(name="account_balance", passed=True, message="Balance check skipped (proxy unavailable)"))

    # 5. Daily loss
    try:
        from datetime import date
        today = date.today().isoformat()
        snap_resp = supabase.table("account_snapshots").select("daily_pnl").eq("snapshot_date", today).execute()
        daily_pnl = float(snap_resp.data[0]["daily_pnl"]) if snap_resp.data else 0.0
        loss_ok = daily_pnl > -settings.risk_max_daily_loss
        checks.append(RiskCheck(
            name="daily_loss_limit",
            passed=loss_ok,
            message=f"Daily PnL: ${daily_pnl:.2f} (limit: -${settings.risk_max_daily_loss})",
            value=daily_pnl,
            limit=-settings.risk_max_daily_loss,
        ))
    except Exception as e:
        logger.warning(f"Could not check daily loss: {e}")
        checks.append(RiskCheck(name="daily_loss_limit", passed=True, message="Daily loss check skipped"))

    all_passed = all(c.passed for c in checks)
    rejection_reason = next((c.message for c in checks if not c.passed), None)
    score = _risk_score(checks, notional)
    auto_approved = all_passed and notional < settings.risk_auto_approval_threshold

    return ValidationResult(
        approved=all_passed,
        auto_approved=auto_approved,
        risk_score=score,
        checks=checks,
        rejection_reason=rejection_reason,
    )
