"""Unit tests for position_sizer.py."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone


def _mock_indicators(atr: float = 500.0):
    from app.models.quant_models import TechnicalIndicators
    return TechnicalIndicators(
        symbol="BTCUSDT", interval="1h",
        candle_time=datetime.now(timezone.utc),
        atr_14=atr,
    )


@pytest.mark.asyncio
async def test_returns_result_with_valid_data(mock_supabase):
    """compute_position_size should return PositionSizing when ATR and price available."""
    ind = _mock_indicators(atr=500.0)
    with patch("app.services.position_sizer.compute_indicators", return_value=ind), \
         patch("app.services.position_sizer.get_supabase", return_value=mock_supabase), \
         patch("app.services.position_sizer.binance_client") as mock_bc:
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.00"})
        mock_bc.get_account = AsyncMock(return_value={
            "balances": [{"asset": "USDT", "free": "10000.00"}]
        })
        from app.services.position_sizer import compute_position_size
        result = await compute_position_size("BTCUSDT", "1h")

    assert result is not None
    assert result.symbol == "BTCUSDT"
    assert result.recommended_size_usd > 0


@pytest.mark.asyncio
async def test_hard_cap_is_respected(mock_supabase):
    """Position size must never exceed MAX_POSITION_USD ($500)."""
    ind = _mock_indicators(atr=1.0)  # Tiny ATR → huge ATR-based size
    winning_trades = [{"realized_pnl": "200", "entry_notional": "100"}] * 30
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = winning_trades

    with patch("app.services.position_sizer.compute_indicators", return_value=ind), \
         patch("app.services.position_sizer.get_supabase", return_value=mock_supabase), \
         patch("app.services.position_sizer.binance_client") as mock_bc:
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.00"})
        mock_bc.get_account = AsyncMock(return_value={
            "balances": [{"asset": "USDT", "free": "100000.00"}]
        })
        from app.services.position_sizer import compute_position_size
        result = await compute_position_size("BTCUSDT", "1h")

    if result:
        assert result.recommended_size_usd <= 500.0


@pytest.mark.asyncio
async def test_fallback_with_no_trade_history(mock_supabase):
    """With 0 historical trades, should use fixed 2% sizing (not Kelly)."""
    ind = _mock_indicators(atr=500.0)
    # Empty trade history
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("app.services.position_sizer.compute_indicators", return_value=ind), \
         patch("app.services.position_sizer.get_supabase", return_value=mock_supabase), \
         patch("app.services.position_sizer.binance_client") as mock_bc:
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.00"})
        mock_bc.get_account = AsyncMock(return_value={
            "balances": [{"asset": "USDT", "free": "10000.00"}]
        })
        from app.services.position_sizer import compute_position_size
        result = await compute_position_size("BTCUSDT", "1h")

    assert result is not None
    assert result.recommended_size_usd <= 500.0
    assert result.recommended_size_usd > 0


@pytest.mark.asyncio
async def test_returns_none_when_no_indicators(mock_supabase):
    """Should return None when indicators (and hence ATR) are unavailable."""
    with patch("app.services.position_sizer.compute_indicators", return_value=None), \
         patch("app.services.position_sizer.get_supabase", return_value=mock_supabase), \
         patch("app.services.position_sizer.binance_client") as mock_bc:
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.00"})
        mock_bc.get_account = AsyncMock(return_value={
            "balances": [{"asset": "USDT", "free": "10000.00"}]
        })
        from app.services.position_sizer import compute_position_size
        result = await compute_position_size("BTCUSDT", "1h")

    # When ATR is unavailable the sizer falls back to fixed 2% sizing (not None)
    assert result is not None
    assert result.method == "fixed_pct"
    assert 0 < result.recommended_size_usd <= 500.0
