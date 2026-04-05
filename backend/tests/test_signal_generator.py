"""Unit tests for signal_generator.py — verifica filtros de entrada."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone


DEFAULT_THRESHOLDS = {
    "buy_rsi_max": 50.0,
    "buy_adx_min": 25.0,
    "buy_entropy_max": 0.70,
    "sell_rsi_min": 65.0,
    "signal_cooldown_minutes": 180,
    "max_open_positions": 5,
}


def _indicators(rsi=30.0, macd_hist=2.0, adx=30.0, sma_20=51000.0, sma_50=50000.0):
    m = MagicMock()
    m.rsi_14 = rsi
    m.macd_histogram = macd_hist
    m.adx_14 = adx
    m.sma_20 = sma_20
    m.sma_50 = sma_50
    m.ppo = 1.0
    m.autocorr_1 = 0.1
    m.volume_ratio = 1.5
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
async def test_buy_blocked_in_extreme_downtrend():
    """BUY should be blocked when regime is trending_down with confidence > 95% (testnet mode)."""
    with patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator.get_supabase", return_value=_supabase_with_positions()), \
         patch("app.services.signal_generator.compute_indicators", return_value=_indicators()), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("trending_down", 98.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
        mock_settings.quant_enabled = True
        mock_settings.quant_primary_interval = "1h"
        mock_settings.quant_symbols = "BTCUSDT"
        mock_settings.buy_adx_min = 15.0
        mock_settings.buy_entropy_max = 0.85
        mock_settings.buy_regime_confidence_min = 95.0
        mock_settings.risk_max_open_positions = 5
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
         patch("app.services.signal_generator._cooled_down", return_value=True), \
         patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
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
         patch("app.services.signal_generator._cooled_down", return_value=True), \
         patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
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
         patch("app.services.signal_generator._cooled_down", return_value=True), \
         patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
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
         patch("app.services.signal_generator._cooled_down", return_value=True), \
         patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(MagicMock(), "BTCUSDT", set(), 0)

    mock_submit.assert_not_called()  # SMA cross ES gate obligatorio — trade bloqueado


@pytest.mark.asyncio
async def test_adx_threshold_blocks_very_low():
    """ADX below 15 (new threshold) should block BUY."""
    with patch("app.services.signal_generator.compute_indicators",
               return_value=_indicators(adx=12.0)), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True), \
         patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 15.0
        mock_settings.buy_entropy_max = 0.85
        mock_settings.buy_regime_confidence_min = 80.0
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(MagicMock(), "BTCUSDT", set(), 0)

    mock_submit.assert_not_called()


def _make_supabase_for_cooldown(
    has_recent_buy_proposal: bool = False,
    has_recent_closed_position: bool = False,
):
    """Supabase mock que diferencia trade_proposals vs positions para _cooled_down."""
    mock = MagicMock()

    proposals_resp = MagicMock()
    proposals_resp.data = [{"id": "p1"}] if has_recent_buy_proposal else []
    proposals_mock = MagicMock()
    proposals_mock.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = proposals_resp

    positions_resp = MagicMock()
    positions_resp.data = [{"id": "pos-1"}] if has_recent_closed_position else []
    positions_mock = MagicMock()
    positions_mock.select.return_value.eq.return_value.eq.return_value.gte.return_value.execute.return_value = positions_resp

    def table_side_effect(name):
        if name == "trade_proposals":
            return proposals_mock
        if name == "positions":
            return positions_mock
        return MagicMock()

    mock.table.side_effect = table_side_effect
    return mock


def test_cooled_down_buy_blocked_by_recent_closed_position():
    """_cooled_down returns False cuando hay posición cerrada recientemente (post-SL/TP guard)."""
    with patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
        from app.services.signal_generator import _cooled_down
        sb = _make_supabase_for_cooldown(
            has_recent_buy_proposal=False,
            has_recent_closed_position=True,
        )
        assert _cooled_down("BTCUSDT", "buy", sb) is False


def test_cooled_down_buy_allowed_when_no_recent_close():
    """_cooled_down returns True cuando no hay propuestas ni posiciones cerradas recientes."""
    with patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
        from app.services.signal_generator import _cooled_down
        sb = _make_supabase_for_cooldown(
            has_recent_buy_proposal=False,
            has_recent_closed_position=False,
        )
        assert _cooled_down("BTCUSDT", "buy", sb) is True


def test_cooled_down_sell_not_blocked_by_recent_closed_position():
    """_cooled_down para 'sell' ignora posiciones cerradas — solo usa propuestas."""
    with patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
        from app.services.signal_generator import _cooled_down
        sb = _make_supabase_for_cooldown(
            has_recent_buy_proposal=False,
            has_recent_closed_position=True,  # debería ser ignorado para sell
        )
        assert _cooled_down("BTCUSDT", "sell", sb) is True


@pytest.mark.asyncio
async def test_buy_blocked_after_recent_position_close():
    """BUY no se genera cuando la posición del símbolo se cerró dentro de la ventana de cooldown."""
    sb = _make_supabase_for_cooldown(
        has_recent_buy_proposal=False,
        has_recent_closed_position=True,
    )

    with patch("app.services.signal_generator.compute_indicators", return_value=_indicators()), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_settings.buy_regime_confidence_min = 85.0
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(sb, "BTCUSDT", set(), 0)

    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_sell_signal_with_open_position():
    """SELL signal should fire when RSI > 68, position is open, min hold passed, and profit > breakeven."""
    indicators = _indicators(rsi=72.0, macd_hist=-2.0)
    # Mock supabase to return a position opened 4 hours ago at lower price (profit > breakeven)
    mock_supabase = MagicMock()
    from datetime import datetime, timezone, timedelta
    old_time = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    pos_resp = MagicMock()
    pos_resp.data = [{"opened_at": old_time, "entry_price": "49000.0"}]
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = pos_resp

    with patch("app.services.signal_generator.compute_indicators", return_value=indicators), \
         patch("app.services.signal_generator.compute_entropy", return_value=_entropy(0.5)), \
         patch("app.services.signal_generator.detect_regime", return_value=_regime("ranging", 50.0)), \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_settings, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True), \
         patch("app.services.signal_generator._get_thresholds", return_value=DEFAULT_THRESHOLDS):
        mock_settings.quant_primary_interval = "1h"
        mock_settings.buy_adx_min = 25.0
        mock_settings.buy_entropy_max = 0.70
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        from app.services.signal_generator import _evaluate_symbol
        await _evaluate_symbol(mock_supabase, "BTCUSDT", {"BTCUSDT"}, 1)

    mock_submit.assert_called_once()
    assert mock_submit.call_args[0][1] == "sell"
