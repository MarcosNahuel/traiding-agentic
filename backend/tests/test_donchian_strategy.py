"""Tests para la estrategia donchian_breakout + bull filter + chandelier puro.

Cubre los cambios del backtest lab 2026-06-10:
  1. market_state.is_bull_market — bull / bear / fail-closed sin datos
  2. market_state.donchian_breakout_level — máximo de N velas cerradas
  3. signal_generator._evaluate_donchian_entry — gates en orden
  4. executor._compute_sl_tp — SL 2×ATR + TP cap lejano para donchian
  5. trading_loop._update_trailing_stop — chandelier puro (ratchet sin progress gate)
  6. signal exits suprimidos cuando la estrategia es donchian
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.config import settings


def _klines_df(n: int, close: float = 100.0, high: float = 101.0) -> pd.DataFrame:
    return pd.DataFrame({
        "close": [close] * n,
        "high": [high] * n,
        "low": [close - 1] * n,
        "volume": [10.0] * n,
    })


# ───────────────────────── is_bull_market ─────────────────────────

def test_bull_market_true_when_price_above_rising_sma(monkeypatch):
    from app.services import market_state

    monkeypatch.setattr(settings, "bull_sma_bars", 10)
    monkeypatch.setattr(settings, "bull_slope_bars", 3)
    # Serie ascendente: close > SMA y SMA subiendo
    df = pd.DataFrame({"close": [float(i) for i in range(1, 31)]})
    with patch.object(market_state, "_load_klines_df", return_value=df):
        assert market_state.is_bull_market("ETHUSDT") is True


def test_bull_market_false_when_price_below_sma(monkeypatch):
    from app.services import market_state

    monkeypatch.setattr(settings, "bull_sma_bars", 10)
    monkeypatch.setattr(settings, "bull_slope_bars", 3)
    # Serie descendente: close < SMA
    df = pd.DataFrame({"close": [float(100 - i) for i in range(30)]})
    with patch.object(market_state, "_load_klines_df", return_value=df):
        assert market_state.is_bull_market("ETHUSDT") is False


def test_bull_market_none_when_insufficient_data(monkeypatch):
    from app.services import market_state

    monkeypatch.setattr(settings, "bull_sma_bars", 600)
    monkeypatch.setattr(settings, "bull_slope_bars", 24)
    df = pd.DataFrame({"close": [100.0] * 50})  # muy pocas velas
    with patch.object(market_state, "_load_klines_df", return_value=df):
        assert market_state.is_bull_market("ETHUSDT") is None


def test_bull_market_none_when_no_df(monkeypatch):
    from app.services import market_state

    with patch.object(market_state, "_load_klines_df", return_value=None):
        assert market_state.is_bull_market("ETHUSDT") is None


# ───────────────────────── donchian_breakout_level ─────────────────────────

def _df_with_hourly_index(highs: list[float], include_forming: bool = False) -> pd.DataFrame:
    """DataFrame con index de open_times 1h. La última vela puede estar en formación."""
    now = pd.Timestamp.now(tz="UTC").floor("h")
    n = len(highs)
    if include_forming:
        # la última vela abre en la hora actual (aún no cerró)
        idx = pd.date_range(end=now, periods=n, freq="h")
    else:
        # todas cerradas: la última abrió hace 2 horas
        idx = pd.date_range(end=now - pd.Timedelta(hours=2), periods=n, freq="h")
    return pd.DataFrame({"high": highs}, index=idx)


def test_donchian_level_is_max_high(monkeypatch):
    from app.services import market_state

    monkeypatch.setattr(settings, "donchian_entry_bars", 5)
    df = _df_with_hourly_index([10.0, 20.0, 99.0, 15.0, 12.0, 11.0])
    with patch.object(market_state, "_load_klines_df", return_value=df):
        # todas cerradas — últimas 5: 20, 99, 15, 12, 11 → max 99
        assert market_state.donchian_breakout_level("ETHUSDT") == 99.0


def test_donchian_level_excludes_forming_candle(monkeypatch):
    from app.services import market_state

    monkeypatch.setattr(settings, "donchian_entry_bars", 5)
    # la vela en formación tiene el high más alto (999) — NO debe contar
    df = _df_with_hourly_index([10.0, 20.0, 99.0, 15.0, 12.0, 999.0], include_forming=True)
    with patch.object(market_state, "_load_klines_df", return_value=df):
        assert market_state.donchian_breakout_level("ETHUSDT") == 99.0


def test_donchian_level_none_when_insufficient(monkeypatch):
    from app.services import market_state

    monkeypatch.setattr(settings, "donchian_entry_bars", 55)
    with patch.object(market_state, "_load_klines_df", return_value=_df_with_hourly_index([10.0] * 10)):
        assert market_state.donchian_breakout_level("ETHUSDT") is None


# ───────────────────────── _evaluate_donchian_entry ─────────────────────────

def _entry_mocks(monkeypatch, bull=True, level=100.0, loss_pause=False, cooled=True, regime=None):
    import app.services.signal_generator as sg

    monkeypatch.setattr(sg, "_loss_streak_pause_active", lambda sb, s: (loss_pause, "pausa" if loss_pause else ""))
    monkeypatch.setattr(sg, "detect_regime", lambda s, i: regime)
    monkeypatch.setattr(sg, "_cooled_down", lambda s, t, sb=None: cooled)
    submit = AsyncMock()
    monkeypatch.setattr(sg, "_submit_proposal", submit)
    patches = patch.multiple(
        "app.services.market_state",
        is_bull_market=MagicMock(return_value=bull),
        donchian_breakout_level=MagicMock(return_value=level),
    )
    return sg, submit, patches


@pytest.mark.asyncio
async def test_donchian_entry_submits_on_breakout_in_bull(monkeypatch):
    sg, submit, patches = _entry_mocks(monkeypatch, bull=True, level=100.0)
    with patches:
        await sg._evaluate_donchian_entry(MagicMock(), "ETHUSDT", "1h", current_price=101.0)
    submit.assert_awaited_once()
    assert submit.await_args.args[1] == "buy"


@pytest.mark.asyncio
async def test_donchian_entry_blocked_in_bear(monkeypatch):
    sg, submit, patches = _entry_mocks(monkeypatch, bull=False, level=100.0)
    with patches:
        await sg._evaluate_donchian_entry(MagicMock(), "ETHUSDT", "1h", current_price=101.0)
    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_donchian_entry_fail_closed_without_bull_data(monkeypatch):
    sg, submit, patches = _entry_mocks(monkeypatch, bull=None, level=100.0)
    with patches:
        await sg._evaluate_donchian_entry(MagicMock(), "ETHUSDT", "1h", current_price=101.0)
    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_donchian_entry_blocked_without_breakout(monkeypatch):
    sg, submit, patches = _entry_mocks(monkeypatch, bull=True, level=100.0)
    with patches:
        await sg._evaluate_donchian_entry(MagicMock(), "ETHUSDT", "1h", current_price=99.5)
    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_donchian_entry_blocked_on_loss_streak(monkeypatch):
    sg, submit, patches = _entry_mocks(monkeypatch, bull=True, level=100.0, loss_pause=True)
    with patches:
        await sg._evaluate_donchian_entry(MagicMock(), "ETHUSDT", "1h", current_price=101.0)
    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_donchian_entry_respects_cooldown(monkeypatch):
    sg, submit, patches = _entry_mocks(monkeypatch, bull=True, level=100.0, cooled=False)
    with patches:
        await sg._evaluate_donchian_entry(MagicMock(), "ETHUSDT", "1h", current_price=101.0)
    submit.assert_not_awaited()


# ───────────────────────── executor SL/TP donchian ─────────────────────────

def test_executor_donchian_sl_tp(monkeypatch):
    from app.services import executor

    monkeypatch.setattr(settings, "entry_strategy", "donchian_breakout")
    monkeypatch.setattr(settings, "donchian_sl_atr_mult", 2.0)
    monkeypatch.setattr(settings, "donchian_tp_max_pct", 0.15)

    ind = MagicMock()
    ind.atr_14 = 1.0  # 1% del precio
    with patch.object(executor, "compute_indicators", return_value=ind):
        sl, tp = executor._compute_sl_tp("ETHUSDT", 100.0)

    assert sl == pytest.approx(98.0)    # 100 - 2*1.0
    assert tp == pytest.approx(115.0)   # cap lejano 15% — el exit real es el trailing


def test_executor_legacy_sl_tp_unchanged(monkeypatch):
    from app.services import executor

    monkeypatch.setattr(settings, "entry_strategy", "legacy")
    ind = MagicMock()
    ind.atr_14 = 1.0
    with patch.object(executor, "compute_indicators", return_value=ind):
        sl, tp = executor._compute_sl_tp("ETHUSDT", 100.0)

    assert sl == pytest.approx(100.0 - settings.sl_atr_multiplier * 1.0)
    assert tp == pytest.approx(100.0 + settings.tp_atr_multiplier * 1.0)


# ───────────────────────── trailing chandelier puro ─────────────────────────

def _position(entry=100.0, sl=98.0, tp=115.0):
    return {
        "id": "pos-1",
        "symbol": "ETHUSDT",
        "entry_price": str(entry),
        "stop_loss_price": str(sl),
        "take_profit_price": str(tp),
        "status": "open",
    }


def _mock_supabase():
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    return sb


@pytest.mark.asyncio
async def test_chandelier_pure_ratchets_up(monkeypatch):
    from app.services import trading_loop

    monkeypatch.setattr(settings, "entry_strategy", "donchian_breakout")
    monkeypatch.setattr(settings, "trail_mode", "chandelier_pure")
    monkeypatch.setattr(settings, "trail_chandelier_mult", 3.0)

    ind = MagicMock()
    ind.atr_14 = 1.0
    sb = _mock_supabase()
    with patch("app.services.technical_analysis.compute_indicators", return_value=ind):
        # price 105 → chandelier = 105 - 3 = 102 > sl 98 → ratchet
        await trading_loop._update_trailing_stop(sb, _position(sl=98.0), 105.0, 98.0, 115.0)

    sb.table.return_value.update.assert_called_once()
    payload = sb.table.return_value.update.call_args.args[0]
    assert payload["stop_loss_price"] == pytest.approx(102.0)


@pytest.mark.asyncio
async def test_chandelier_pure_never_lowers_sl(monkeypatch):
    from app.services import trading_loop

    monkeypatch.setattr(settings, "entry_strategy", "donchian_breakout")
    monkeypatch.setattr(settings, "trail_mode", "chandelier_pure")
    monkeypatch.setattr(settings, "trail_chandelier_mult", 3.0)

    ind = MagicMock()
    ind.atr_14 = 1.0
    sb = _mock_supabase()
    with patch("app.services.technical_analysis.compute_indicators", return_value=ind):
        # price 100 → chandelier = 97 < sl 98 → no tocar
        await trading_loop._update_trailing_stop(sb, _position(sl=98.0), 100.0, 98.0, 115.0)

    sb.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_chandelier_pure_no_atr_no_move(monkeypatch):
    from app.services import trading_loop

    monkeypatch.setattr(settings, "entry_strategy", "donchian_breakout")
    monkeypatch.setattr(settings, "trail_mode", "chandelier_pure")

    sb = _mock_supabase()
    with patch("app.services.technical_analysis.compute_indicators", return_value=None):
        await trading_loop._update_trailing_stop(sb, _position(sl=98.0), 110.0, 98.0, 115.0)

    sb.table.return_value.update.assert_not_called()


# ───────────────────────── signal exits suprimidos en donchian ─────────────────────────

@pytest.mark.asyncio
async def test_signal_exit_suppressed_for_donchian(monkeypatch):
    import app.services.signal_generator as sg

    monkeypatch.setattr(settings, "entry_strategy", "donchian_breakout")

    ind = MagicMock()
    ind.rsi_14, ind.macd_histogram, ind.adx_14 = 80.0, -5.0, 30.0  # señal SELL clarísima en legacy
    ind.ppo, ind.autocorr_1, ind.volume_ratio, ind.atr_14 = 1.0, 0.1, 1.5, 1.0

    submit = AsyncMock()
    monkeypatch.setattr(sg, "_submit_proposal", submit)
    monkeypatch.setattr(sg, "compute_indicators", lambda s, i: ind)
    monkeypatch.setattr(sg, "compute_entropy", lambda s, i: None)
    monkeypatch.setattr(sg.binance_client, "get_price", AsyncMock(return_value={"price": "100.0"}))

    await sg._evaluate_symbol(MagicMock(), "ETHUSDT", open_symbols={"ETHUSDT"}, open_count=1)

    submit.assert_not_awaited()  # ningún SELL por señal: exit solo via SL/trailing
