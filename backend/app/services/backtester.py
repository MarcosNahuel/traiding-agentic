"""VectorBT-based backtesting engine.

Built-in strategies: sma_cross, rsi_reversal, bbands_squeeze.
Computes full performance metrics and equity curves.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import numpy as np
import pandas as pd
import pandas_ta_classic as ta

from ..db import get_supabase
from ..models.quant_models import BacktestRequest, BacktestResult
from .technical_analysis import _load_klines_df

logger = logging.getLogger(__name__)

# Default fees and slippage
DEFAULT_FEES = 0.001      # 0.1%
DEFAULT_SLIPPAGE = 0.0005  # 0.05%


def _generate_sma_cross_signals(df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
    """SMA crossover strategy: buy when fast > slow, sell when fast < slow."""
    fast = params.get("fast_period", 20)
    slow = params.get("slow_period", 50)

    sma_fast = ta.sma(df["close"], length=fast)
    sma_slow = ta.sma(df["close"], length=slow)

    if sma_fast is None or sma_slow is None:
        return pd.Series(False, index=df.index), pd.Series(False, index=df.index)

    entries = (sma_fast > sma_slow) & (sma_fast.shift(1) <= sma_slow.shift(1))
    exits = (sma_fast < sma_slow) & (sma_fast.shift(1) >= sma_slow.shift(1))
    return entries.fillna(False), exits.fillna(False)


def _generate_rsi_reversal_signals(df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
    """RSI reversal: buy when RSI crosses above oversold, sell when crosses below overbought."""
    period = params.get("rsi_period", 14)
    oversold = params.get("oversold", 30)
    overbought = params.get("overbought", 70)

    rsi = ta.rsi(df["close"], length=period)
    if rsi is None:
        return pd.Series(False, index=df.index), pd.Series(False, index=df.index)

    entries = (rsi > oversold) & (rsi.shift(1) <= oversold)
    exits = (rsi < overbought) & (rsi.shift(1) >= overbought)
    return entries.fillna(False), exits.fillna(False)


def _generate_bbands_squeeze_signals(df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
    """Bollinger Bands squeeze: buy on breakout above upper band after squeeze."""
    length = params.get("bb_length", 20)
    std = params.get("bb_std", 2.0)
    squeeze_threshold = params.get("squeeze_pct", 0.02)

    bb = ta.bbands(df["close"], length=length, std=std)
    if bb is None:
        return pd.Series(False, index=df.index), pd.Series(False, index=df.index)

    upper_col = f"BBU_{length}_{std}"
    lower_col = f"BBL_{length}_{std}"
    mid_col = f"BBM_{length}_{std}"

    if upper_col not in bb.columns:
        return pd.Series(False, index=df.index), pd.Series(False, index=df.index)

    bandwidth = (bb[upper_col] - bb[lower_col]) / bb[mid_col]
    is_squeeze = bandwidth < squeeze_threshold
    was_squeeze = is_squeeze.shift(1).fillna(False)

    entries = was_squeeze & ~is_squeeze & (df["close"] > bb[upper_col])
    exits = df["close"] < bb[mid_col]
    return entries.fillna(False), exits.fillna(False)


STRATEGIES = {
    "sma_cross": _generate_sma_cross_signals,
    "rsi_reversal": _generate_rsi_reversal_signals,
    "bbands_squeeze": _generate_bbands_squeeze_signals,
}


async def run_backtest(request: BacktestRequest) -> Optional[BacktestResult]:
    """Run a backtest with the specified strategy and parameters."""
    if request.strategy_id not in STRATEGIES:
        logger.error(f"Unknown strategy: {request.strategy_id}")
        return None

    # Load data
    limit = request.lookback_days * 24 if request.interval == "1h" else request.lookback_days * 24 * 4
    limit = min(limit, 5000)

    df = _load_klines_df(request.symbol, request.interval, limit=limit)
    if df is None or len(df) < 2:
        logger.error(f"Not enough data for backtest: {request.symbol} {request.interval} ({0 if df is None else len(df)} rows)")
        return None

    try:
        import vectorbt as vbt

        # Generate signals
        strategy_fn = STRATEGIES[request.strategy_id]
        entries, exits = strategy_fn(df, request.parameters)

        # Run portfolio simulation
        close = df["close"]
        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            fees=request.parameters.get("fees", DEFAULT_FEES),
            slippage=request.parameters.get("slippage", DEFAULT_SLIPPAGE),
            init_cash=10000,
            freq="1h" if request.interval == "1h" else request.interval,
        )

        # Extract metrics
        stats = pf.stats()
        total_return = float(stats.get("Total Return [%]", 0)) / 100 if "Total Return [%]" in stats else None
        sharpe = float(stats.get("Sharpe Ratio", 0)) if "Sharpe Ratio" in stats else None
        sortino = float(stats.get("Sortino Ratio", 0)) if "Sortino Ratio" in stats else None
        calmar = float(stats.get("Calmar Ratio", 0)) if "Calmar Ratio" in stats else None
        max_dd = float(stats.get("Max Drawdown [%]", 0)) / 100 if "Max Drawdown [%]" in stats else None
        win_rate = float(stats.get("Win Rate [%]", 0)) / 100 if "Win Rate [%]" in stats else None
        total_trades = int(stats.get("Total Trades", 0)) if "Total Trades" in stats else 0
        profit_factor = float(stats.get("Profit Factor", 0)) if "Profit Factor" in stats else None

        # Expectancy
        expectancy = None
        if total_trades > 0:
            total_pnl = float(pf.total_profit()) if hasattr(pf, "total_profit") else 0
            expectancy = total_pnl / total_trades

        # Equity curve (sampled to 500 points)
        equity = pf.value()
        equity_curve = None
        if equity is not None and len(equity) > 0:
            step = max(1, len(equity) // 500)
            sampled = equity.iloc[::step]
            equity_curve = [
                {"time": str(t), "value": round(float(v), 2)}
                for t, v in sampled.items()
            ]

        result = BacktestResult(
            strategy_id=request.strategy_id,
            symbol=request.symbol,
            interval=request.interval,
            start_date=df.index[0],
            end_date=df.index[-1],
            parameters=request.parameters,
            total_return=round(total_return, 4) if total_return is not None else None,
            sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
            sortino_ratio=round(sortino, 4) if sortino is not None else None,
            calmar_ratio=round(calmar, 4) if calmar is not None else None,
            max_drawdown=round(max_dd, 4) if max_dd is not None else None,
            win_rate=round(win_rate, 4) if win_rate is not None else None,
            profit_factor=round(profit_factor, 4) if profit_factor is not None else None,
            expectancy=round(expectancy, 8) if expectancy is not None else None,
            total_trades=total_trades,
            equity_curve=equity_curve,
        )
        return result

    except ImportError:
        logger.error("vectorbt not installed, falling back to manual backtest")
        return await _manual_backtest(request, df)
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return None


async def _manual_backtest(request: BacktestRequest, df: pd.DataFrame) -> Optional[BacktestResult]:
    """Fallback manual backtest without vectorbt."""
    try:
        strategy_fn = STRATEGIES[request.strategy_id]
        entries, exits = strategy_fn(df, request.parameters)
        close = df["close"].values

        # Simple simulation
        position = False
        entry_price = 0.0
        pnls = []
        trades = 0

        for i in range(len(close)):
            if not position and entries.iloc[i]:
                position = True
                entry_price = close[i]
                trades += 1
            elif position and exits.iloc[i]:
                position = False
                pnl_pct = (close[i] - entry_price) / entry_price - DEFAULT_FEES * 2
                pnls.append(pnl_pct)

        if not pnls:
            return BacktestResult(
                strategy_id=request.strategy_id, symbol=request.symbol,
                interval=request.interval, start_date=df.index[0], end_date=df.index[-1],
                parameters=request.parameters, total_trades=0,
            )

        pnls_arr = np.array(pnls)
        total_return = float(np.prod(1 + pnls_arr) - 1)
        wins = pnls_arr[pnls_arr > 0]
        losses = pnls_arr[pnls_arr < 0]
        win_rate = len(wins) / len(pnls_arr) if len(pnls_arr) > 0 else 0
        sharpe = float(np.mean(pnls_arr) / np.std(pnls_arr) * np.sqrt(252)) if np.std(pnls_arr) > 0 else 0

        # Max drawdown from cumulative returns
        cumulative = np.cumprod(1 + pnls_arr)
        peak = np.maximum.accumulate(cumulative)
        dd = (cumulative - peak) / peak
        max_dd = float(np.min(dd)) if len(dd) > 0 else 0

        return BacktestResult(
            strategy_id=request.strategy_id, symbol=request.symbol,
            interval=request.interval, start_date=df.index[0], end_date=df.index[-1],
            parameters=request.parameters,
            total_return=round(total_return, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(abs(max_dd), 4),
            win_rate=round(win_rate, 4),
            total_trades=trades,
        )
    except Exception as e:
        logger.error(f"Manual backtest error: {e}")
        return None


def store_backtest_result(result: BacktestResult) -> Optional[str]:
    """Store backtest result in DB. Returns the ID."""
    supabase = get_supabase()
    data = result.model_dump(exclude={"id", "created_at"})
    data["start_date"] = result.start_date.isoformat()
    data["end_date"] = result.end_date.isoformat()
    data["created_at"] = datetime.now(timezone.utc).isoformat()

    try:
        resp = supabase.table("backtest_results").insert(data).execute()
        return resp.data[0]["id"] if resp.data else None
    except Exception as e:
        logger.error(f"Failed to store backtest result: {e}")
        return None


def get_backtest_results(strategy_id: Optional[str] = None, limit: int = 20) -> List[dict]:
    """Get stored backtest results."""
    supabase = get_supabase()
    query = supabase.table("backtest_results").select("*").order("created_at", desc=True).limit(limit)
    if strategy_id:
        query = query.eq("strategy_id", strategy_id)
    resp = query.execute()
    return resp.data or []
