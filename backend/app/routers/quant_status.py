"""API routes for quant engine status and performance."""

from fastapi import APIRouter
from ..services.quant_orchestrator import get_engine_status, get_quant_snapshot
from ..db import get_supabase
from ..config import settings
import logging

router = APIRouter(prefix="/quant", tags=["quant"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def quant_status():
    """Get quant engine status (tick count, last updates, errors)."""
    status = get_engine_status()
    return status.model_dump()


@router.get("/performance")
async def quant_performance():
    """Get rolling performance metrics (Sharpe, Sortino, Calmar, Kelly)."""
    supabase = get_supabase()
    resp = supabase.table("performance_metrics").select("*").execute()
    metrics = resp.data or []
    return {"metrics": metrics}


@router.get("/health")
async def quant_health():
    """Health check of all quant modules."""
    status = get_engine_status()
    symbols = settings.quant_symbols.split(",")

    health = {
        "engine_enabled": status.enabled,
        "tick_count": status.tick_count,
        "last_tick": status.last_tick_at.isoformat() if status.last_tick_at else None,
        "errors_count": len(status.errors),
        "modules_ok": all(m.get("status") == "active" for m in status.modules.values()),
    }

    # Check data freshness
    supabase = get_supabase()
    for sym in symbols[:2]:  # Sample check on first 2 symbols
        kline_resp = (
            supabase.table("klines_ohlcv")
            .select("open_time")
            .eq("symbol", sym)
            .eq("interval", "1h")
            .order("open_time", desc=True)
            .limit(1)
            .execute()
        )
        health[f"latest_kline_{sym}"] = kline_resp.data[0]["open_time"] if kline_resp.data else None

    return health


@router.get("/snapshot/{symbol}")
async def quant_snapshot(symbol: str):
    """Get full quant snapshot for a symbol (same data fed to LLM)."""
    snapshot = await get_quant_snapshot(symbol.upper())
    if snapshot is None:
        return {"error": f"No data available for {symbol}"}
    return snapshot.model_dump()
