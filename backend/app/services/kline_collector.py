"""Kline (candlestick) data collector from Binance.

Handles fetching, normalizing, storing, and backfilling OHLCV data.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from ..db import get_supabase
from ..config import settings
from . import binance_client

logger = logging.getLogger(__name__)

# Binance kline array indices
_OT, _O, _H, _L, _C, _V, _CT, _QV, _T, _TBV, _TQV, _IGNORE = range(12)

INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]


def _parse_kline(symbol: str, interval: str, raw: list) -> Dict[str, Any]:
    """Convert Binance kline array to dict."""
    return {
        "symbol": symbol,
        "interval": interval,
        "open_time": datetime.fromtimestamp(raw[_OT] / 1000, tz=timezone.utc).isoformat(),
        "close_time": datetime.fromtimestamp(raw[_CT] / 1000, tz=timezone.utc).isoformat(),
        "open": float(raw[_O]),
        "high": float(raw[_H]),
        "low": float(raw[_L]),
        "close": float(raw[_C]),
        "volume": float(raw[_V]),
        "quote_volume": float(raw[_QV]),
        "trades_count": int(raw[_T]),
        "taker_buy_base_volume": float(raw[_TBV]),
        "taker_buy_quote_volume": float(raw[_TQV]),
    }


async def fetch_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 500,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fetch klines from Binance and normalize them."""
    raw = await binance_client.get_klines(
        symbol=symbol,
        interval=interval,
        limit=limit,
        start_time=start_time,
        end_time=end_time,
    )
    return [_parse_kline(symbol, interval, k) for k in raw]


async def store_klines(klines: List[Dict[str, Any]]) -> int:
    """Batch upsert klines to DB. Returns count of inserted rows."""
    if not klines:
        return 0
    supabase = get_supabase()
    # Upsert in batches of 500
    inserted = 0
    for i in range(0, len(klines), 500):
        batch = klines[i : i + 500]
        try:
            resp = supabase.table("klines_ohlcv").upsert(
                batch, on_conflict="symbol,interval,open_time"
            ).execute()
            inserted += len(resp.data) if resp.data else 0
        except Exception as e:
            logger.error(f"Failed to upsert klines batch: {e}")
    return inserted


def _interval_ms(interval: str) -> int:
    """Convert interval string to milliseconds."""
    multipliers = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
    unit = interval[-1]
    num = int(interval[:-1])
    return num * multipliers[unit]


async def backfill(
    symbol: str,
    interval: str = "1h",
    days: int = 30,
) -> int:
    """Backfill historical klines in batches of 1000 going backward."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - (days * 86_400_000)
    total_stored = 0
    current_start = start_ms
    batch_size = 1000
    interval_duration = _interval_ms(interval)

    while current_start < now_ms:
        try:
            klines = await fetch_klines(
                symbol=symbol,
                interval=interval,
                limit=batch_size,
                start_time=current_start,
            )
            if not klines:
                break
            stored = await store_klines(klines)
            total_stored += stored
            # Move to after last candle
            last_open = klines[-1]["open_time"]
            last_ts = int(datetime.fromisoformat(last_open).timestamp() * 1000)
            current_start = last_ts + interval_duration
            logger.info(
                f"Backfill {symbol} {interval}: stored {stored} candles "
                f"(total: {total_stored})"
            )
        except Exception as e:
            logger.error(f"Backfill error {symbol} {interval}: {e}")
            break

    return total_stored


async def collect_latest(symbol: str, interval: str = "1h") -> int:
    """Fetch 3 most recent candles (incremental update)."""
    klines = await fetch_klines(symbol=symbol, interval=interval, limit=3)
    return await store_klines(klines)


async def get_klines_status() -> List[Dict[str, Any]]:
    """Get latest timestamps per symbol/interval pair."""
    supabase = get_supabase()
    symbols = settings.quant_symbols.split(",")
    status = []
    for sym in symbols:
        for iv in INTERVALS:
            try:
                resp = (
                    supabase.table("klines_ohlcv")
                    .select("open_time")
                    .eq("symbol", sym)
                    .eq("interval", iv)
                    .order("open_time", desc=True)
                    .limit(1)
                    .execute()
                )
                count_resp = (
                    supabase.table("klines_ohlcv")
                    .select("id", count="exact")
                    .eq("symbol", sym)
                    .eq("interval", iv)
                    .execute()
                )
                status.append({
                    "symbol": sym,
                    "interval": iv,
                    "latest_open_time": resp.data[0]["open_time"] if resp.data else None,
                    "count": count_resp.count or 0,
                })
            except Exception:
                status.append({"symbol": sym, "interval": iv, "latest_open_time": None, "count": 0})
    return status
