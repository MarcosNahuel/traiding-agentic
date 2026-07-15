"""Unit tests for kline_collector.py."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def test_parse_kline_converts_binance_array():
    """_parse_kline should correctly convert a Binance raw kline array to dict."""
    from app.services.kline_collector import _parse_kline

    raw = [
        1700000000000, "50000.00", "51000.00", "49000.00", "50500.00",
        "100.5", 1700003600000, "5075250.00", 1500, "60.0", "3045000.00", "0",
    ]
    result = _parse_kline("BTCUSDT", "1h", raw)

    assert result["symbol"] == "BTCUSDT"
    assert result["interval"] == "1h"
    assert result["open"] == 50000.0
    assert result["high"] == 51000.0
    assert result["low"] == 49000.0
    assert result["close"] == 50500.0
    assert result["volume"] == 100.5
    assert result["trades_count"] == 1500


def test_parse_kline_returns_isoformat_timestamps():
    """open_time and close_time should be ISO 8601 strings."""
    from app.services.kline_collector import _parse_kline

    raw = [
        1700000000000, "50000", "51000", "49000", "50500",
        "100", 1700003600000, "5000000", "1000", "60", "3000000", "0",
    ]
    result = _parse_kline("ETHUSDT", "1h", raw)
    # Should not raise
    from datetime import datetime
    datetime.fromisoformat(result["open_time"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_collect_latest_calls_binance_get_klines(mock_supabase):
    """collect_latest should call binance_client.get_klines for the symbol/interval."""
    mock_kline_raw = [[
        1700000000000, "50000", "51000", "49000", "50500",
        "100", 1700003600000, "5000000", "1000", "60", "3000000", "0",
    ]]

    with patch("app.services.kline_collector.binance_client") as mock_bc, \
         patch("app.services.kline_collector.get_supabase", return_value=mock_supabase):
        mock_bc.get_klines = AsyncMock(return_value=mock_kline_raw)
        upsert_result = MagicMock()
        upsert_result.data = [{"id": "test-id"}]
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = upsert_result

        from app.services.kline_collector import collect_latest
        await collect_latest("BTCUSDT", "1h")

        mock_bc.get_klines.assert_called_once()
        call_kwargs = mock_bc.get_klines.call_args
        # binance_client.get_klines uses keyword args: symbol, interval, limit
        all_args = {**dict(zip(["symbol", "interval", "limit"], call_kwargs.args)), **call_kwargs.kwargs}
        assert all_args.get("symbol") == "BTCUSDT"
        assert all_args.get("interval") == "1h"
        assert all_args.get("limit") == 3


@pytest.mark.asyncio
async def test_collect_latest_handles_empty_response(mock_supabase):
    """collect_latest should handle empty Binance response gracefully."""
    with patch("app.services.kline_collector.binance_client") as mock_bc, \
         patch("app.services.kline_collector.get_supabase", return_value=mock_supabase):
        mock_bc.get_klines = AsyncMock(return_value=[])

        from app.services.kline_collector import collect_latest
        # Should not raise
        await collect_latest("BTCUSDT", "1h")


# ───────────────────────── corrupt-wick filtering ─────────────────────────
# Evidencia 2026-07-14: klines_ohlcv (ETHUSDT/BTCUSDT 1h) mostraron highs
# corruptos (wicks de hasta 12.7% que no corresponden a movimiento real,
# varios en números redondos sospechosos) mientras open/close se mantenían
# sanos. Esto inflaba el techo Donchian y contaminaba el ATR de SL/TP.

_NORMAL_RAW = [
    1700000000000, "1800.00", "1810.00", "1795.00", "1805.00",
    "50.0", 1700003600000, "91000.00", "800", "25.0", "45500.00", "0",
]
# high 12.66% por encima de max(open,close)=1826.60 — wick imposible en 1h
_CORRUPT_HIGH_RAW = [
    1700003600000, "1800.00", "2057.90", "1795.00", "1826.60",
    "50.0", 1700007200000, "91000.00", "800", "25.0", "45500.00", "0",
]
# low 12.66% por debajo de min(open,close)=1826.60 — mismo patrón, lado bajo
_CORRUPT_LOW_RAW = [
    1700007200000, "1826.60", "1830.00", "1596.30", "1820.00",
    "50.0", 1700010800000, "91000.00", "800", "25.0", "45500.00", "0",
]


def test_is_corrupt_wick_false_for_normal_candle():
    from app.services.kline_collector import _is_corrupt_wick, _parse_kline

    k = _parse_kline("ETHUSDT", "1h", _NORMAL_RAW)
    assert _is_corrupt_wick(k) is False


def test_is_corrupt_wick_true_for_high_side_outlier():
    from app.services.kline_collector import _is_corrupt_wick, _parse_kline

    k = _parse_kline("ETHUSDT", "1h", _CORRUPT_HIGH_RAW)
    assert _is_corrupt_wick(k) is True


def test_is_corrupt_wick_true_for_low_side_outlier():
    from app.services.kline_collector import _is_corrupt_wick, _parse_kline

    k = _parse_kline("ETHUSDT", "1h", _CORRUPT_LOW_RAW)
    assert _is_corrupt_wick(k) is True


@pytest.mark.asyncio
async def test_fetch_klines_drops_corrupt_wick_candles():
    """fetch_klines debe descartar velas con wick corrupto y no poner en riesgo las sanas."""
    from app.services.kline_collector import fetch_klines

    with patch("app.services.kline_collector.binance_client") as mock_bc:
        mock_bc.get_klines = AsyncMock(
            return_value=[_NORMAL_RAW, _CORRUPT_HIGH_RAW, _CORRUPT_LOW_RAW]
        )
        result = await fetch_klines("ETHUSDT", "1h", limit=3)

    assert len(result) == 1
    assert result[0]["high"] == 1810.00


@pytest.mark.asyncio
async def test_fetch_klines_keeps_all_normal_candles_unchanged():
    """Comportamiento existente para velas normales: sin filtrado espurio."""
    from app.services.kline_collector import fetch_klines

    raws = [_NORMAL_RAW, _NORMAL_RAW, _NORMAL_RAW]
    with patch("app.services.kline_collector.binance_client") as mock_bc:
        mock_bc.get_klines = AsyncMock(return_value=raws)
        result = await fetch_klines("ETHUSDT", "1h", limit=3)

    assert len(result) == 3
