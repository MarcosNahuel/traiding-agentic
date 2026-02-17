"""API routes for backtesting."""

from fastapi import APIRouter, HTTPException
from typing import Optional
from ..models.quant_models import BacktestRequest
from ..services.backtester import run_backtest, store_backtest_result, get_backtest_results
import logging

router = APIRouter(prefix="/backtest", tags=["backtest"])
logger = logging.getLogger(__name__)


@router.post("/run")
async def execute_backtest(req: BacktestRequest):
    """Run a backtest with the given strategy and parameters."""
    result = await run_backtest(req)
    if result is None:
        raise HTTPException(500, "Backtest failed - check logs for details")

    # Store result
    result_id = store_backtest_result(result)
    data = result.model_dump()
    data["id"] = result_id

    return {"success": True, "result": data}


@router.get("/results")
async def list_backtest_results(strategy_id: Optional[str] = None, limit: int = 20):
    """List stored backtest results."""
    results = get_backtest_results(strategy_id=strategy_id, limit=limit)
    return {"results": results, "count": len(results)}


@router.get("/results/{result_id}")
async def get_backtest_result(result_id: str):
    """Get a specific backtest result with equity curve."""
    from ..db import get_supabase
    supabase = get_supabase()
    resp = supabase.table("backtest_results").select("*").eq("id", result_id).single().execute()
    if not resp.data:
        raise HTTPException(404, "Backtest result not found")
    return {"result": resp.data}


@router.get("/strategies")
async def list_strategies():
    """List available backtest strategies."""
    from ..services.backtester import STRATEGIES
    return {
        "strategies": [
            {"id": "sma_cross", "name": "SMA Crossover", "params": {"fast_period": 20, "slow_period": 50}},
            {"id": "rsi_reversal", "name": "RSI Reversal", "params": {"rsi_period": 14, "oversold": 30, "overbought": 70}},
            {"id": "bbands_squeeze", "name": "Bollinger Bands Squeeze", "params": {"bb_length": 20, "bb_std": 2.0, "squeeze_pct": 0.02}},
        ]
    }
