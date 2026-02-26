"""API routes for backtesting."""

from fastapi import APIRouter, HTTPException
from typing import Optional
from ..models.quant_models import BacktestRequest, BacktestBenchmarkRequest
from ..services.backtester import (
    run_backtest,
    store_backtest_result,
    get_backtest_results,
    get_backtest_presets,
    run_backtest_benchmark,
)
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
    return {
        "strategies": [
            {"id": "sma_cross", "name": "SMA Crossover", "params": {"fast_period": 20, "slow_period": 50}},
            {"id": "rsi_reversal", "name": "RSI Reversal", "params": {"rsi_period": 14, "oversold": 30, "overbought": 70}},
            {"id": "bbands_squeeze", "name": "Bollinger Bands Squeeze", "params": {"bb_length": 20, "bb_std": 2.0, "squeeze_pct": 0.02}},
            {
                "id": "trend_momentum_v2",
                "name": "Trend Momentum v2",
                "params": {
                    "fast_period": 20,
                    "slow_period": 50,
                    "adx_threshold": 25,
                    "volume_mult": 1.2,
                    "atr_stop_mult": 2.0,
                    "max_hold_bars": 72,
                },
            },
            {
                "id": "mean_reversion_v2",
                "name": "Mean Reversion v2",
                "params": {
                    "z_window": 50,
                    "z_entry": -2.0,
                    "z_exit": 0.0,
                    "adx_max": 20,
                    "rsi_entry": 30,
                    "rsi_exit": 55,
                    "max_hold_bars": 24,
                },
            },
            {
                "id": "breakout_volatility_v2",
                "name": "Breakout Volatility v2",
                "params": {
                    "bb_length": 20,
                    "bb_std": 2.0,
                    "squeeze_pct": 0.02,
                    "volume_mult": 1.3,
                    "adx_min": 20,
                    "atr_stop_mult": 1.8,
                    "max_hold_bars": 48,
                },
            },
        ]
    }


@router.get("/presets")
async def list_presets():
    """List benchmark presets grouped by market and horizon."""
    return {"presets": get_backtest_presets()}


@router.post("/benchmark")
async def execute_benchmark(req: BacktestBenchmarkRequest):
    """Run comparative benchmark for preset strategies and persist ranked outputs."""
    try:
        data = await run_backtest_benchmark(
            symbol=req.symbol,
            market=req.market,
            horizon=req.horizon,
            lookback_days=req.lookback_days,
            store_results=req.store_results,
            interval_override=req.interval_override,
        )
        return {"success": True, **data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Benchmark failed")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {e}") from e
