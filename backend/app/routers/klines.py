"""API routes for kline (candlestick) data."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from ..services import kline_collector
from ..config import settings
import logging

router = APIRouter(prefix="/klines", tags=["klines"])
logger = logging.getLogger(__name__)


class BackfillRequest(BaseModel):
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    days: int = 30


@router.get("/{symbol}")
async def get_klines(
    symbol: str,
    interval: str = Query("1h", description="Candle interval"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get stored klines for a symbol."""
    from ..db import get_supabase
    supabase = get_supabase()
    resp = (
        supabase.table("klines_ohlcv")
        .select("*")
        .eq("symbol", symbol.upper())
        .eq("interval", interval)
        .order("open_time", desc=True)
        .limit(limit)
        .execute()
    )
    data = resp.data or []
    # Reverse so oldest first
    data.reverse()
    return {"symbol": symbol.upper(), "interval": interval, "count": len(data), "klines": data}


@router.post("/backfill")
async def trigger_backfill(req: BackfillRequest):
    """Trigger historical kline backfill."""
    try:
        count = await kline_collector.backfill(
            symbol=req.symbol.upper(),
            interval=req.interval,
            days=req.days,
        )
        return {
            "success": True,
            "symbol": req.symbol.upper(),
            "interval": req.interval,
            "days": req.days,
            "candles_stored": count,
        }
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        raise HTTPException(500, f"Backfill failed: {e}")


@router.get("/status/all")
async def klines_status():
    """Get latest timestamps per symbol/interval."""
    status = await kline_collector.get_klines_status()
    return {"status": status}
