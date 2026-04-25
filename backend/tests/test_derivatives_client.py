"""Tests for derivatives_client. Uses respx for HTTP mocking."""

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_get_derivatives_snapshot_normalized():
    """Snapshot returns expected shape with mocked Binance responses."""
    fake_funding = [
        {"symbol": "BTCUSDT", "fundingTime": 1, "fundingRate": "0.0001"},
        {"symbol": "BTCUSDT", "fundingTime": 2, "fundingRate": "0.0001"},
        {"symbol": "BTCUSDT", "fundingTime": 3, "fundingRate": "0.0001"},
        {"symbol": "BTCUSDT", "fundingTime": 4, "fundingRate": "0.00008"},
        {"symbol": "BTCUSDT", "fundingTime": 5, "fundingRate": "0.00008"},
    ]
    fake_oi_now = {"symbol": "BTCUSDT", "openInterest": "1000000.0", "time": 1}
    fake_oi_hist = [
        {"symbol": "BTCUSDT", "sumOpenInterest": "950000", "timestamp": 1},
        {"symbol": "BTCUSDT", "sumOpenInterest": "1000000", "timestamp": 24},
    ]
    fake_ls = [
        {"symbol": "BTCUSDT", "longShortRatio": "1.2", "timestamp": 1},
        {"symbol": "BTCUSDT", "longShortRatio": "1.3", "timestamp": 2},
        {"symbol": "BTCUSDT", "longShortRatio": "1.4", "timestamp": 3},
        {"symbol": "BTCUSDT", "longShortRatio": "1.5", "timestamp": 4},
        {"symbol": "BTCUSDT", "longShortRatio": "1.6", "timestamp": 5},
    ]

    from app.services import derivatives_client as mod
    # Reset cache between tests
    mod._cache.clear()

    async def fake_get(url, params):
        if "fundingRate" in url:
            return fake_funding
        if url.endswith("/openInterest"):
            return fake_oi_now
        if "openInterestHist" in url:
            return fake_oi_hist
        if "topLongShortAccountRatio" in url:
            return fake_ls
        return None

    with patch.object(mod, "_cached_get", side_effect=fake_get):
        snap = await mod.get_derivatives_snapshot("BTCUSDT")

    assert snap["symbol"] == "BTCUSDT"
    assert snap["funding_rate_current"] == pytest.approx(0.0001)
    assert snap["funding_rate_8h_avg"] == pytest.approx(0.0001)
    # 5.26% change from 950k -> 1M
    assert snap["oi_change_24h_pct"] == pytest.approx(5.263, abs=0.01)
    assert snap["oi_current_usd"] == 1_000_000.0
    assert snap["long_short_ratio_24h_avg"] == pytest.approx(1.4)


@pytest.mark.asyncio
async def test_get_derivatives_snapshot_partial_failure():
    """If funding fails, other fields still populate."""
    from app.services import derivatives_client as mod
    mod._cache.clear()

    async def fake_get(url, params):
        if "fundingRate" in url:
            return None  # fail
        if url.endswith("/openInterest"):
            return {"symbol": "ETHUSDT", "openInterest": "500000.0", "time": 1}
        return None

    with patch.object(mod, "_cached_get", side_effect=fake_get):
        snap = await mod.get_derivatives_snapshot("ETHUSDT")

    assert snap["funding_rate_current"] is None
    assert snap["oi_current_usd"] == 500_000.0
