"""Read-only Binance Futures derivatives data client.

Provides funding rates, open interest, and long/short ratios for spot decision
support. ALWAYS read-only — no orders are ever placed via this module.

All endpoints are public (no auth required). Rate limit: 2400/min, well above
our daily query budget. We cache responses for 5 minutes to avoid spam.
"""

import asyncio
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FAPI_BASE = "https://fapi.binance.com"
CACHE_TTL_SECONDS = 300  # 5 minutes

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = asyncio.Lock()


async def _cached_get(url: str, params: dict) -> Optional[list | dict]:
    """GET with simple TTL cache keyed by url+params."""
    cache_key = f"{url}?{sorted(params.items())}"
    async with _cache_lock:
        if cache_key in _cache:
            ts, payload = _cache[cache_key]
            if time.time() - ts < CACHE_TTL_SECONDS:
                return payload

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("derivatives_client GET failed: %s — %s", url, e)
        return None

    async with _cache_lock:
        _cache[cache_key] = (time.time(), data)
    return data


async def get_funding_rate_history(symbol: str, limit: int = 50) -> Optional[list]:
    """Recent funding rate history. Returns list of {symbol, fundingTime, fundingRate}."""
    url = f"{FAPI_BASE}/fapi/v1/fundingRate"
    return await _cached_get(url, {"symbol": symbol, "limit": limit})


async def get_open_interest(symbol: str) -> Optional[dict]:
    """Current open interest. Returns {symbol, openInterest, time}."""
    url = f"{FAPI_BASE}/fapi/v1/openInterest"
    return await _cached_get(url, {"symbol": symbol})


async def get_open_interest_hist(symbol: str, period: str = "1h", limit: int = 24) -> Optional[list]:
    """Historical open interest. period: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d."""
    url = f"{FAPI_BASE}/futures/data/openInterestHist"
    return await _cached_get(url, {"symbol": symbol, "period": period, "limit": limit})


async def get_top_long_short_account_ratio(symbol: str, period: str = "1h", limit: int = 24) -> Optional[list]:
    """Top trader accounts long/short ratio."""
    url = f"{FAPI_BASE}/futures/data/topLongShortAccountRatio"
    return await _cached_get(url, {"symbol": symbol, "period": period, "limit": limit})


async def get_top_long_short_position_ratio(symbol: str, period: str = "1h", limit: int = 24) -> Optional[list]:
    """Top trader positions long/short ratio."""
    url = f"{FAPI_BASE}/futures/data/topLongShortPositionRatio"
    return await _cached_get(url, {"symbol": symbol, "period": period, "limit": limit})


async def get_derivatives_snapshot(symbol: str) -> dict:
    """Aggregated derivatives view for a symbol — used by quant_orchestrator.

    Returns normalized dict; missing fields are None on partial failures.
    """
    funding, oi_now, oi_hist, ls_acct = await asyncio.gather(
        get_funding_rate_history(symbol, limit=10),
        get_open_interest(symbol),
        get_open_interest_hist(symbol, period="1h", limit=24),
        get_top_long_short_account_ratio(symbol, period="1h", limit=24),
        return_exceptions=False,
    )

    out = {
        "symbol": symbol,
        "funding_rate_current": None,
        "funding_rate_8h_avg": None,
        "funding_rate_trend": None,
        "oi_current_usd": None,
        "oi_change_24h_pct": None,
        "long_short_ratio_24h_avg": None,
        "long_short_ratio_inverting": None,
    }

    if funding and isinstance(funding, list) and len(funding) > 0:
        rates = [float(r["fundingRate"]) for r in funding if "fundingRate" in r]
        if rates:
            out["funding_rate_current"] = rates[0]
            if len(rates) >= 3:
                out["funding_rate_8h_avg"] = sum(rates[:3]) / 3
            if len(rates) >= 5:
                recent3 = sum(rates[:3]) / 3
                older3 = sum(rates[2:5]) / 3
                if recent3 > older3 * 1.1:
                    out["funding_rate_trend"] = "rising"
                elif recent3 < older3 * 0.9:
                    out["funding_rate_trend"] = "falling"
                else:
                    out["funding_rate_trend"] = "neutral"

    if oi_now and "openInterest" in oi_now:
        try:
            out["oi_current_usd"] = float(oi_now["openInterest"])
        except (TypeError, ValueError):
            pass

    if oi_hist and isinstance(oi_hist, list) and len(oi_hist) >= 2:
        try:
            latest = float(oi_hist[-1]["sumOpenInterest"])
            oldest = float(oi_hist[0]["sumOpenInterest"])
            if oldest > 0:
                out["oi_change_24h_pct"] = (latest - oldest) / oldest * 100.0
        except (TypeError, ValueError, KeyError):
            pass

    if ls_acct and isinstance(ls_acct, list) and len(ls_acct) >= 5:
        try:
            ratios = [float(r["longShortRatio"]) for r in ls_acct]
            out["long_short_ratio_24h_avg"] = sum(ratios) / len(ratios)
            recent = sum(ratios[-3:]) / 3
            older = sum(ratios[:3]) / 3
            out["long_short_ratio_inverting"] = (
                (recent < 1.0 and older > 1.0) or (recent > 1.0 and older < 1.0)
            )
        except (TypeError, ValueError, KeyError):
            pass

    return out
