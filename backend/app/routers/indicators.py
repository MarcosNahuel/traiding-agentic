"""API routes for technical indicators."""

from fastapi import APIRouter, HTTPException
from ..services.technical_analysis import compute_indicators, store_indicators, get_latest_indicators
from ..config import settings
import logging

router = APIRouter(prefix="/indicators", tags=["indicators"])
logger = logging.getLogger(__name__)


@router.get("/{symbol}")
async def get_indicators(symbol: str, interval: str = "1h"):
    """Compute and return technical indicators for a symbol."""
    symbol = symbol.upper()
    indicators = compute_indicators(symbol, interval)
    if indicators is None:
        raise HTTPException(404, f"Not enough data to compute indicators for {symbol} {interval}")
    # Also store snapshot
    store_indicators(indicators)
    return {"symbol": symbol, "interval": interval, "indicators": indicators.model_dump()}


@router.get("/{symbol}/stored")
async def get_stored_indicators(symbol: str, interval: str = "1h"):
    """Get last stored indicators from DB."""
    data = get_latest_indicators(symbol.upper(), interval)
    if data is None:
        raise HTTPException(404, f"No stored indicators for {symbol} {interval}")
    return {"symbol": symbol.upper(), "interval": interval, "indicators": data}
