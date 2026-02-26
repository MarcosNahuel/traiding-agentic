"""VectorBT-based backtesting engine.

Built-in strategies:
- sma_cross
- rsi_reversal
- bbands_squeeze
- trend_momentum_v2
- mean_reversion_v2
- breakout_volatility_v2

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


def _to_bool_series(series: pd.Series, index: pd.Index) -> pd.Series:
    """Normalize any boolean-like series to a safe bool Series."""
    if series is None:
        return pd.Series(False, index=index)
    return series.fillna(False).astype(bool)


def _safe_div(a: pd.Series, b: pd.Series, default: float = 0.0) -> pd.Series:
    """Element-wise safe division for pandas series."""
    out = a / b.replace(0, np.nan)
    out = out.replace([np.inf, -np.inf], np.nan).fillna(default)
    return out


def _apply_max_hold_exits(entries: pd.Series, exits: pd.Series, max_hold_bars: int) -> pd.Series:
    """Force exit after N bars in position to avoid stale trades.

    max_hold_bars <= 0 means disabled.
    """
    entries_s = _to_bool_series(entries, entries.index)
    exits_s = _to_bool_series(exits, exits.index).copy()

    if max_hold_bars <= 0:
        return exits_s

    in_pos = False
    bars_in_pos = 0

    for i in range(len(entries_s)):
        if not in_pos and entries_s.iloc[i]:
            in_pos = True
            bars_in_pos = 0
            continue

        if not in_pos:
            continue

        # Natural exit takes precedence.
        if exits_s.iloc[i]:
            in_pos = False
            bars_in_pos = 0
            continue

        bars_in_pos += 1
        if bars_in_pos >= max_hold_bars:
            exits_s.iloc[i] = True
            in_pos = False
            bars_in_pos = 0

    return exits_s


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


def _generate_trend_momentum_v2_signals(df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
    """Trend/momentum strategy with ADX + volume + ATR-aware exits."""
    fast = int(params.get("fast_period", 20))
    slow = int(params.get("slow_period", 50))
    adx_period = int(params.get("adx_period", 14))
    adx_threshold = float(params.get("adx_threshold", 25.0))
    volume_period = int(params.get("volume_period", 20))
    volume_mult = float(params.get("volume_mult", 1.2))
    rsi_period = int(params.get("rsi_period", 14))
    rsi_exit = float(params.get("rsi_exit", 75.0))
    atr_period = int(params.get("atr_period", 14))
    atr_stop_mult = float(params.get("atr_stop_mult", 2.0))
    max_hold_bars = int(params.get("max_hold_bars", 72))

    close = df["close"]
    sma_fast = ta.sma(close, length=fast)
    sma_slow = ta.sma(close, length=slow)
    adx_df = ta.adx(df["high"], df["low"], close, length=adx_period)
    rsi = ta.rsi(close, length=rsi_period)
    if rsi is None:
        rsi = pd.Series(np.nan, index=df.index)
    atr = ta.atr(df["high"], df["low"], close, length=atr_period)
    vol_ma = ta.sma(df["volume"], length=volume_period)

    if sma_fast is None or sma_slow is None or adx_df is None:
        empty = pd.Series(False, index=df.index)
        return empty, empty

    adx = adx_df.get(f"ADX_{adx_period}")
    if adx is None:
        adx = pd.Series(np.nan, index=df.index)

    vol_ratio = _safe_div(df["volume"], vol_ma if vol_ma is not None else pd.Series(np.nan, index=df.index))
    stop_line = sma_slow - (atr_stop_mult * atr if atr is not None else 0.0)

    cross_up = (sma_fast > sma_slow) & (sma_fast.shift(1) <= sma_slow.shift(1))
    cross_down = (sma_fast < sma_slow) & (sma_fast.shift(1) >= sma_slow.shift(1))

    entries = (
        cross_up
        & (adx > adx_threshold)
        & (vol_ratio > volume_mult)
        & (close > sma_slow)
    )

    exits = (
        cross_down
        | (adx < (adx_threshold * 0.7))
        | (rsi > rsi_exit)
        | (close < stop_line)
    )

    entries = _to_bool_series(entries, df.index)
    exits = _to_bool_series(exits, df.index)
    exits = _apply_max_hold_exits(entries, exits, max_hold_bars)
    return entries, exits


def _generate_mean_reversion_v2_signals(df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
    """Mean-reversion strategy gated by low trend strength and z-score extremes."""
    z_window = int(params.get("z_window", 50))
    z_entry = float(params.get("z_entry", -2.0))
    z_exit = float(params.get("z_exit", 0.0))
    z_stop = float(params.get("z_stop", -3.5))
    adx_period = int(params.get("adx_period", 14))
    adx_max = float(params.get("adx_max", 20.0))
    rsi_period = int(params.get("rsi_period", 14))
    rsi_entry = float(params.get("rsi_entry", 30.0))
    rsi_exit = float(params.get("rsi_exit", 55.0))
    max_hold_bars = int(params.get("max_hold_bars", 24))

    close = df["close"]
    mean = ta.sma(close, length=z_window)
    std = close.rolling(z_window).std()
    z = _safe_div(close - mean, std, default=0.0)

    adx_df = ta.adx(df["high"], df["low"], close, length=adx_period)
    adx = adx_df.get(f"ADX_{adx_period}") if adx_df is not None else pd.Series(np.nan, index=df.index)
    rsi = ta.rsi(close, length=rsi_period)
    if rsi is None:
        rsi = pd.Series(np.nan, index=df.index)

    entries = (
        (z < z_entry)
        & (adx < adx_max)
        & (rsi < rsi_entry)
    )

    exits = (
        (z > z_exit)
        | (rsi > rsi_exit)
        | (adx > (adx_max + 5))
        | (z < z_stop)
    )

    entries = _to_bool_series(entries, df.index)
    exits = _to_bool_series(exits, df.index)
    exits = _apply_max_hold_exits(entries, exits, max_hold_bars)
    return entries, exits


def _generate_breakout_volatility_v2_signals(df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
    """Breakout strategy after volatility compression with volume confirmation."""
    bb_length = int(params.get("bb_length", 20))
    bb_std = float(params.get("bb_std", 2.0))
    squeeze_pct = float(params.get("squeeze_pct", 0.02))
    volume_period = int(params.get("volume_period", 20))
    volume_mult = float(params.get("volume_mult", 1.3))
    adx_period = int(params.get("adx_period", 14))
    adx_min = float(params.get("adx_min", 20.0))
    atr_period = int(params.get("atr_period", 14))
    atr_stop_mult = float(params.get("atr_stop_mult", 1.8))
    max_hold_bars = int(params.get("max_hold_bars", 48))

    close = df["close"]
    bb = ta.bbands(close, length=bb_length, std=bb_std)
    adx_df = ta.adx(df["high"], df["low"], close, length=adx_period)
    atr = ta.atr(df["high"], df["low"], close, length=atr_period)
    vol_ma = ta.sma(df["volume"], length=volume_period)

    if bb is None or adx_df is None:
        empty = pd.Series(False, index=df.index)
        return empty, empty

    upper_col = f"BBU_{bb_length}_{bb_std}"
    lower_col = f"BBL_{bb_length}_{bb_std}"
    mid_col = f"BBM_{bb_length}_{bb_std}"
    if upper_col not in bb.columns or lower_col not in bb.columns or mid_col not in bb.columns:
        empty = pd.Series(False, index=df.index)
        return empty, empty

    upper = bb[upper_col]
    lower = bb[lower_col]
    mid = bb[mid_col]
    bw = _safe_div(upper - lower, mid)
    squeeze = bw < squeeze_pct
    expanding = ~squeeze & squeeze.shift(1).fillna(False)
    adx = adx_df.get(f"ADX_{adx_period}")
    if adx is None:
        adx = pd.Series(np.nan, index=df.index)

    vol_ratio = _safe_div(df["volume"], vol_ma if vol_ma is not None else pd.Series(np.nan, index=df.index))
    stop_line = mid - (atr_stop_mult * atr if atr is not None else 0.0)

    entries = (
        expanding
        & (close > upper)
        & (vol_ratio > volume_mult)
        & (adx > adx_min)
    )

    exits = (
        (close < mid)
        | (close < stop_line)
        | (adx < (adx_min * 0.7))
    )

    entries = _to_bool_series(entries, df.index)
    exits = _to_bool_series(exits, df.index)
    exits = _apply_max_hold_exits(entries, exits, max_hold_bars)
    return entries, exits


STRATEGIES = {
    "sma_cross": _generate_sma_cross_signals,
    "rsi_reversal": _generate_rsi_reversal_signals,
    "bbands_squeeze": _generate_bbands_squeeze_signals,
    "trend_momentum_v2": _generate_trend_momentum_v2_signals,
    "mean_reversion_v2": _generate_mean_reversion_v2_signals,
    "breakout_volatility_v2": _generate_breakout_volatility_v2_signals,
}


# Preset matrix for quick benchmark runs by market and horizon.
STRATEGY_PRESETS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "spot": {
        "scalping": [
            {
                "strategy_id": "breakout_volatility_v2",
                "interval": "15m",
                "parameters": {
                    "bb_length": 20,
                    "bb_std": 2.0,
                    "squeeze_pct": 0.018,
                    "volume_mult": 1.35,
                    "adx_min": 22,
                    "atr_stop_mult": 1.6,
                    "max_hold_bars": 16,
                },
            },
            {
                "strategy_id": "mean_reversion_v2",
                "interval": "15m",
                "parameters": {
                    "z_window": 40,
                    "z_entry": -1.9,
                    "z_exit": -0.1,
                    "adx_max": 18,
                    "rsi_entry": 28,
                    "rsi_exit": 52,
                    "max_hold_bars": 12,
                },
            },
        ],
        "intraday": [
            {
                "strategy_id": "trend_momentum_v2",
                "interval": "1h",
                "parameters": {
                    "fast_period": 20,
                    "slow_period": 50,
                    "adx_threshold": 25,
                    "volume_mult": 1.2,
                    "atr_stop_mult": 2.0,
                    "max_hold_bars": 48,
                },
            },
            {
                "strategy_id": "mean_reversion_v2",
                "interval": "1h",
                "parameters": {
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
                "strategy_id": "breakout_volatility_v2",
                "interval": "1h",
                "parameters": {
                    "bb_length": 20,
                    "bb_std": 2.0,
                    "squeeze_pct": 0.02,
                    "volume_mult": 1.3,
                    "adx_min": 20,
                    "atr_stop_mult": 1.8,
                    "max_hold_bars": 36,
                },
            },
        ],
        "swing": [
            {
                "strategy_id": "trend_momentum_v2",
                "interval": "4h",
                "parameters": {
                    "fast_period": 20,
                    "slow_period": 50,
                    "adx_threshold": 23,
                    "volume_mult": 1.1,
                    "atr_stop_mult": 2.2,
                    "max_hold_bars": 40,
                },
            },
            {
                "strategy_id": "breakout_volatility_v2",
                "interval": "4h",
                "parameters": {
                    "bb_length": 20,
                    "bb_std": 2.0,
                    "squeeze_pct": 0.025,
                    "volume_mult": 1.2,
                    "adx_min": 18,
                    "atr_stop_mult": 2.0,
                    "max_hold_bars": 28,
                },
            },
        ],
    },
    "futures": {
        "scalping": [
            {
                "strategy_id": "breakout_volatility_v2",
                "interval": "15m",
                "parameters": {
                    "bb_length": 20,
                    "bb_std": 2.0,
                    "squeeze_pct": 0.017,
                    "volume_mult": 1.4,
                    "adx_min": 24,
                    "atr_stop_mult": 1.5,
                    "max_hold_bars": 14,
                },
            },
            {
                "strategy_id": "mean_reversion_v2",
                "interval": "15m",
                "parameters": {
                    "z_window": 36,
                    "z_entry": -1.8,
                    "z_exit": -0.05,
                    "adx_max": 17,
                    "rsi_entry": 30,
                    "rsi_exit": 54,
                    "max_hold_bars": 10,
                },
            },
        ],
        "intraday": [
            {
                "strategy_id": "trend_momentum_v2",
                "interval": "1h",
                "parameters": {
                    "fast_period": 20,
                    "slow_period": 50,
                    "adx_threshold": 26,
                    "volume_mult": 1.25,
                    "atr_stop_mult": 1.9,
                    "max_hold_bars": 36,
                },
            },
            {
                "strategy_id": "breakout_volatility_v2",
                "interval": "1h",
                "parameters": {
                    "bb_length": 20,
                    "bb_std": 2.0,
                    "squeeze_pct": 0.02,
                    "volume_mult": 1.35,
                    "adx_min": 21,
                    "atr_stop_mult": 1.7,
                    "max_hold_bars": 24,
                },
            },
            {
                "strategy_id": "mean_reversion_v2",
                "interval": "1h",
                "parameters": {
                    "z_window": 48,
                    "z_entry": -2.0,
                    "z_exit": -0.1,
                    "adx_max": 19,
                    "rsi_entry": 30,
                    "rsi_exit": 55,
                    "max_hold_bars": 16,
                },
            },
        ],
        "swing": [
            {
                "strategy_id": "trend_momentum_v2",
                "interval": "4h",
                "parameters": {
                    "fast_period": 20,
                    "slow_period": 50,
                    "adx_threshold": 24,
                    "volume_mult": 1.15,
                    "atr_stop_mult": 2.1,
                    "max_hold_bars": 24,
                },
            },
            {
                "strategy_id": "breakout_volatility_v2",
                "interval": "4h",
                "parameters": {
                    "bb_length": 20,
                    "bb_std": 2.0,
                    "squeeze_pct": 0.024,
                    "volume_mult": 1.25,
                    "adx_min": 19,
                    "atr_stop_mult": 1.9,
                    "max_hold_bars": 20,
                },
            },
        ],
    },
}


def get_backtest_presets() -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Return static backtest presets by market and horizon."""
    return STRATEGY_PRESETS


def _compute_rank_score(result: BacktestResult) -> float:
    """Compute a 0..100 score for ranking backtest outcomes."""
    score = 0.0

    # Sharpe (target around >= 1)
    if result.sharpe_ratio is not None:
        score += 40.0 * float(np.clip(result.sharpe_ratio / 2.0, -1.0, 1.0))

    # Total return (target around >= 20%)
    if result.total_return is not None:
        score += 25.0 * float(np.clip(result.total_return / 0.20, -1.0, 1.0))

    # Drawdown (lower is better, cap at 20%)
    if result.max_drawdown is not None:
        dd = abs(result.max_drawdown)
        score += 20.0 * float(np.clip(1.0 - (dd / 0.20), 0.0, 1.0))

    # Profit factor (good when > 1.2)
    if result.profit_factor is not None:
        pf_component = np.clip((result.profit_factor - 1.0) / 1.0, 0.0, 1.0)
        score += 15.0 * float(pf_component)

    return round(float(np.clip(score, 0.0, 100.0)), 4)


async def run_backtest_benchmark(
    symbol: str = "BTCUSDT",
    market: str = "spot",
    horizon: str = "intraday",
    lookback_days: int = 30,
    store_results: bool = True,
    interval_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all preset strategies for a market/horizon and return ranked results."""
    market_key = market.lower().strip()
    horizon_key = horizon.lower().strip()

    if market_key not in STRATEGY_PRESETS:
        raise ValueError(f"Unknown market '{market}'. Expected one of: {list(STRATEGY_PRESETS.keys())}")
    if horizon_key not in STRATEGY_PRESETS[market_key]:
        raise ValueError(
            f"Unknown horizon '{horizon}'. Expected one of: {list(STRATEGY_PRESETS[market_key].keys())}"
        )

    presets = STRATEGY_PRESETS[market_key][horizon_key]
    scored_rows: List[Dict[str, Any]] = []

    for preset in presets:
        interval_to_use = interval_override or preset["interval"]
        strategy_params = dict(preset["parameters"])
        req = BacktestRequest(
            strategy_id=preset["strategy_id"],
            symbol=symbol.upper(),
            interval=interval_to_use,
            lookback_days=lookback_days,
            parameters=strategy_params,
        )
        result = await run_backtest(req)
        if result is None:
            continue

        scored_rows.append(
            {
                "result": result,
                "interval": interval_to_use,
                "strategy_id": preset["strategy_id"],
                "parameters": strategy_params,
                "rank_score": _compute_rank_score(result),
            }
        )

    scored_rows.sort(key=lambda row: row["rank_score"], reverse=True)
    results = []
    for rank_idx, row in enumerate(scored_rows, start=1):
        result: BacktestResult = row["result"]
        rank_score = float(row["rank_score"])

        benchmark_meta = {
            "market": market_key,
            "horizon": horizon_key,
            "lookback_days": lookback_days,
            "rank": rank_idx,
            "rank_score": rank_score,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        persisted_params = dict(result.parameters or {})
        persisted_params["_benchmark"] = benchmark_meta

        stored_result = result.model_copy(update={"parameters": persisted_params})

        result_id = None
        if store_results:
            result_id = store_backtest_result(stored_result)

        response_row = stored_result.model_dump()
        response_row["id"] = result_id
        response_row["market"] = market_key
        response_row["horizon"] = horizon_key
        response_row["rank_score"] = rank_score
        response_row["rank"] = rank_idx
        results.append(response_row)

    return {
        "symbol": symbol.upper(),
        "market": market_key,
        "horizon": horizon_key,
        "lookback_days": lookback_days,
        "interval_override": interval_override,
        "total_tested": len(presets),
        "total_ranked": len(results),
        "results": results,
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
