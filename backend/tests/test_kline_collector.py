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
