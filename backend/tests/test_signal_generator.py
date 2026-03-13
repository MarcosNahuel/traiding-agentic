"""Unit tests for signal_generator.py — verifica filtros de entrada."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


def _indicators(rsi=30.0, macd_hist=2.0, adx=30.0, sma_20=51000.0, sma_50=50000.0):
    m = MagicMock()
    m.rsi_14 = rsi
    m.macd_histogram = macd_hist
    m.adx_14 = adx
    m.sma_20 = sma_20
    m.sma_50 = sma_50
    return m


def _entropy(ratio=0.5):
    m = MagicMock()
    m.entropy_ratio = ratio
    m.is_tradable = True
    return m


def _regime(regime="ranging", confidence=50.0):
    m = MagicMock()
    m.regime = regime
    m.confidence = confidence
    return m


def _supabase_with_positions(open_symbols=None):
    """Mock supabase: positions query returns open_symbols."""
    mock = MagicMock()
    positions_data = [{"symbol": s} for s in (open_symbols or [])]
    pos_resp = MagicMock()
    pos_resp.data = positions_data
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = pos_resp
    # Para insert de proposals
    insert_resp = MagicMock()
    insert_resp.data = [{"id": "test-id"}]
    mock.table.return_value.insert.return_value.execute.return_value = insert_resp
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    return mock


@pytest.mark.asyncio
async def test_buy_blocked_in_downtrend():
    """BUY should be blocked when regime is trending_down with confidence > 60%."""
    with patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator.get_supabase", return_value=_supabase_with_positions()), \
         patch("app.services.signal_generator.compute_indicators", return_value=_indicators()), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("trending_down", 75.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit:
        mock_settings.quant_enabled = True
        mock_settings.quant_primary_interval = "1h"
        mock_settings.quant_symbols = "BTCUSDT"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_settings.buy_regime_confidence_min = 60.0
        mock_settings.risk_max_open_positions = 3
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(_supabase_with_positions(), "BTCUSDT", set(), 0)

    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_buy_allowed_in_uptrend():
    """BUY should proceed when all conditions are met in uptrend."""
    with patch("app.services.signal_generator.compute_indicators", return_value=_indicators()), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("trending_up", 70.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(MagicMock(), "BTCUSDT", set(), 0)

    mock_submit.assert_called_once()
    assert mock_submit.call_args[0][1] == "buy"


@pytest.mark.asyncio
async def test_entropy_high_blocks_buy():
    """Entropy ratio > BUY_ENTROPY_MAX should block BUY."""
    with patch("app.services.signal_generator.compute_indicators", return_value=_indicators()), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.85)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(MagicMock(), "BTCUSDT", set(), 0)

    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_entropy_low_allows_buy():
    """Entropy ratio < BUY_ENTROPY_MAX should allow BUY (all other conditions met)."""
    with patch("app.services.signal_generator.compute_indicators", return_value=_indicators()), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.45)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(MagicMock(), "BTCUSDT", set(), 0)

    mock_submit.assert_called_once()


@pytest.mark.asyncio
async def test_sma_cross_required():
    """BUY should be blocked when SMA20 < SMA50 (no bullish cross)."""
    with patch("app.services.signal_generator.compute_indicators",
               return_value=_indicators(sma_20=49000.0, sma_50=50000.0)), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(MagicMock(), "BTCUSDT", set(), 0)

    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_adx_threshold_25():
    """ADX below 25 should block BUY."""
    with patch("app.services.signal_generator.compute_indicators",
               return_value=_indicators(adx=22.0)), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(MagicMock(), "BTCUSDT", set(), 0)

    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_sell_signal_with_open_position():
    """SELL signal should fire when RSI > 68 and position is open."""
    indicators = _indicators(rsi=72.0, macd_hist=-2.0)
    with patch("app.services.signal_generator.compute_indicators", return_value=indicators), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(MagicMock(), "BTCUSDT", {"BTCUSDT"}, 1)

    mock_submit.assert_called_once()
    assert mock_submit.call_args[0][1] == "sell"
