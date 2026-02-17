"""Unit tests for quant_risk.py -- verifies all 8 risk checks."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.models import ValidationResult, RiskCheck


def _base_ok():
    """Base validation that passes all 5 base checks."""
    checks = [
        RiskCheck(name="position_size", passed=True, message="OK", value=100.0, limit=500.0),
        RiskCheck(name="max_open_positions", passed=True, message="OK", value=1.0, limit=3.0),
        RiskCheck(name="account_balance", passed=True, message="OK", value=9900.0, limit=100.0),
        RiskCheck(name="account_utilization", passed=True, message="OK", value=0.1, limit=0.8),
        RiskCheck(name="daily_loss_limit", passed=True, message="OK", value=0.0, limit=-200.0),
    ]
    return ValidationResult(approved=True, auto_approved=False, risk_score=10.0,
                            checks=checks, rejection_reason=None)


def _base_fail():
    """Base validation that fails (position size too large)."""
    checks = [
        RiskCheck(name="position_size", passed=False, message="Too large", value=600.0, limit=500.0),
    ]
    return ValidationResult(approved=False, auto_approved=False, risk_score=80.0,
                            checks=checks, rejection_reason="Too large")


def _entropy(tradable=True, ratio=0.5):
    m = MagicMock()
    m.is_tradable = tradable
    m.entropy_ratio = ratio
    m.entropy_value = ratio * 3.32
    m.max_entropy = 3.32
    return m


def _regime(regime="ranging", confidence=50.0):
    m = MagicMock()
    m.regime = regime
    m.confidence = confidence
    return m


def _sizing(usd=200.0):
    m = MagicMock()
    m.recommended_size_usd = usd
    m.method = "kelly"
    return m


@pytest.mark.asyncio
async def test_all_8_checks_pass(mock_supabase):
    """All 8 checks should pass when market conditions are favorable."""
    with patch("app.services.quant_risk._base_validate", return_value=_base_ok()), \
         patch("app.services.quant_risk.compute_entropy", return_value=_entropy(True, 0.5)), \
         patch("app.services.quant_risk.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.quant_risk.compute_position_size", new_callable=AsyncMock, return_value=_sizing(200.0)), \
         patch("app.services.quant_risk.get_supabase", return_value=mock_supabase):
        from app.services.quant_risk import validate_proposal_enhanced
        result = await validate_proposal_enhanced(
            trade_type="buy", symbol="BTCUSDT",
            quantity=0.002, notional=100.0, current_price=50000.0,
        )

    assert result.approved is True
    assert len(result.checks) == 8
    assert all(c.passed for c in result.checks)


@pytest.mark.asyncio
async def test_entropy_gate_blocks_noisy_market(mock_supabase):
    """High entropy (ratio > threshold) should block the trade."""
    with patch("app.services.quant_risk._base_validate", return_value=_base_ok()), \
         patch("app.services.quant_risk.compute_entropy", return_value=_entropy(False, 0.92)), \
         patch("app.services.quant_risk.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.quant_risk.compute_position_size", new_callable=AsyncMock, return_value=_sizing(200.0)), \
         patch("app.services.quant_risk.get_supabase", return_value=mock_supabase):
        from app.services.quant_risk import validate_proposal_enhanced
        result = await validate_proposal_enhanced(
            trade_type="buy", symbol="BTCUSDT",
            quantity=0.002, notional=100.0, current_price=50000.0,
        )

    assert result.approved is False
    entropy_check = next((c for c in result.checks if c.name == "entropy_gate"), None)
    assert entropy_check is not None
    assert entropy_check.passed is False


@pytest.mark.asyncio
async def test_volatile_regime_blocks_trade(mock_supabase):
    """Volatile regime with confidence > 60% should block all trades."""
    with patch("app.services.quant_risk._base_validate", return_value=_base_ok()), \
         patch("app.services.quant_risk.compute_entropy", return_value=_entropy(True, 0.5)), \
         patch("app.services.quant_risk.detect_regime", return_value=_regime("volatile", 75.0)), \
         patch("app.services.quant_risk.compute_position_size", new_callable=AsyncMock, return_value=_sizing(200.0)), \
         patch("app.services.quant_risk.get_supabase", return_value=mock_supabase):
        from app.services.quant_risk import validate_proposal_enhanced
        result = await validate_proposal_enhanced(
            trade_type="buy", symbol="BTCUSDT",
            quantity=0.002, notional=100.0, current_price=50000.0,
        )

    assert result.approved is False
    regime_check = next((c for c in result.checks if c.name == "regime_check"), None)
    assert regime_check is not None
    assert regime_check.passed is False


@pytest.mark.asyncio
async def test_contra_trend_sell_in_uptrend_blocked(mock_supabase):
    """Selling during strong uptrend (confidence > 70%) should be blocked."""
    with patch("app.services.quant_risk._base_validate", return_value=_base_ok()), \
         patch("app.services.quant_risk.compute_entropy", return_value=_entropy(True, 0.5)), \
         patch("app.services.quant_risk.detect_regime", return_value=_regime("trending_up", 80.0)), \
         patch("app.services.quant_risk.compute_position_size", new_callable=AsyncMock, return_value=_sizing(200.0)), \
         patch("app.services.quant_risk.get_supabase", return_value=mock_supabase):
        from app.services.quant_risk import validate_proposal_enhanced
        result = await validate_proposal_enhanced(
            trade_type="sell", symbol="BTCUSDT",
            quantity=0.002, notional=100.0, current_price=50000.0,
        )

    assert result.approved is False
    regime_check = next((c for c in result.checks if c.name == "regime_check"), None)
    assert regime_check is not None
    assert regime_check.passed is False


@pytest.mark.asyncio
async def test_contra_trend_buy_in_downtrend_blocked(mock_supabase):
    """Buying during strong downtrend (confidence > 70%) should be blocked."""
    with patch("app.services.quant_risk._base_validate", return_value=_base_ok()), \
         patch("app.services.quant_risk.compute_entropy", return_value=_entropy(True, 0.5)), \
         patch("app.services.quant_risk.detect_regime", return_value=_regime("trending_down", 80.0)), \
         patch("app.services.quant_risk.compute_position_size", new_callable=AsyncMock, return_value=_sizing(200.0)), \
         patch("app.services.quant_risk.get_supabase", return_value=mock_supabase):
        from app.services.quant_risk import validate_proposal_enhanced
        result = await validate_proposal_enhanced(
            trade_type="buy", symbol="BTCUSDT",
            quantity=0.002, notional=100.0, current_price=50000.0,
        )

    assert result.approved is False


@pytest.mark.asyncio
async def test_kelly_size_validation_blocks_oversized_trade(mock_supabase):
    """Notional exceeding 1.5x recommended size should fail kelly_size_validation."""
    with patch("app.services.quant_risk._base_validate", return_value=_base_ok()), \
         patch("app.services.quant_risk.compute_entropy", return_value=_entropy(True, 0.5)), \
         patch("app.services.quant_risk.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.quant_risk.compute_position_size", new_callable=AsyncMock, return_value=_sizing(50.0)), \
         patch("app.services.quant_risk.get_supabase", return_value=mock_supabase):
        from app.services.quant_risk import validate_proposal_enhanced
        result = await validate_proposal_enhanced(
            trade_type="buy", symbol="BTCUSDT",
            quantity=0.004, notional=200.0,  # 200 > 50 * 1.5 = 75
            current_price=50000.0,
        )

    assert result.approved is False
    size_check = next((c for c in result.checks if c.name == "quant_size_validation"), None)
    assert size_check is not None
    assert size_check.passed is False


@pytest.mark.asyncio
async def test_base_rejection_propagates(mock_supabase):
    """A failing base check should result in overall rejection."""
    with patch("app.services.quant_risk._base_validate", return_value=_base_fail()), \
         patch("app.services.quant_risk.compute_entropy", return_value=_entropy(True, 0.5)), \
         patch("app.services.quant_risk.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.quant_risk.compute_position_size", new_callable=AsyncMock, return_value=_sizing(200.0)), \
         patch("app.services.quant_risk.get_supabase", return_value=mock_supabase):
        from app.services.quant_risk import validate_proposal_enhanced
        result = await validate_proposal_enhanced(
            trade_type="buy", symbol="BTCUSDT",
            quantity=0.002, notional=100.0, current_price=50000.0,
        )

    assert result.approved is False
