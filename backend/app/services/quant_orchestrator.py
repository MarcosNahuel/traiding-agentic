"""Quant Engine Orchestrator.

Central coordinator called every 60s from trading_loop.py.
Schedules data collection and analysis at different frequencies using tick counters.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..config import settings
from ..models.quant_models import QuantSnapshot, QuantEngineStatus
from .quant_cache import get_analysis_cache

logger = logging.getLogger(__name__)

# Module state
_tick_count: int = 0
_last_tick_at: Optional[datetime] = None
_errors: List[str] = []


async def run_quant_tick() -> None:
    """Run one quant engine tick. Called every 60s from trading loop."""
    global _tick_count, _last_tick_at, _errors

    if not settings.quant_enabled:
        return

    _tick_count += 1
    _last_tick_at = datetime.now(timezone.utc)
    _errors.clear()

    symbols = settings.quant_symbols.split(",")
    interval = settings.quant_primary_interval
    tick = _tick_count

    try:
        # ── Kline Collection (parallel across symbols) ──
        await _collect_klines(symbols, tick)

        # ── Analysis (parallel across symbols) ──
        tasks = []
        for sym in symbols:
            tasks.append(_process_symbol(sym, interval, tick))
        await asyncio.gather(*tasks, return_exceptions=True)

        # ── Performance metrics (every 360 ticks = 6 hours) ──
        if tick % 360 == 0:
            await _update_performance_metrics()

    except Exception as e:
        msg = f"Quant tick {tick} error: {e}"
        logger.error(msg)
        _errors.append(msg)


async def _collect_klines(symbols: List[str], tick: int) -> None:
    """Collect klines at varying intervals."""
    from . import kline_collector

    # Schedule: 1m=every tick, 5m=5, 15m=15, 1h=60, 4h=240, 1d=1440
    intervals_schedule = {
        "1m": 1, "5m": 5, "15m": 15, "1h": 1, "4h": 240, "1d": 1440,
    }
    # Always collect primary interval
    intervals_to_fetch = ["1h"]
    for iv, freq in intervals_schedule.items():
        if iv != "1h" and tick % freq == 0:
            intervals_to_fetch.append(iv)

    for iv in intervals_to_fetch:
        tasks = []
        for sym in symbols:
            tasks.append(_safe_collect(sym, iv))
        await asyncio.gather(*tasks, return_exceptions=True)


async def _safe_collect(symbol: str, interval: str) -> None:
    """Safely collect latest klines for a symbol/interval."""
    try:
        from . import kline_collector
        await kline_collector.collect_latest(symbol, interval)
    except Exception as e:
        logger.warning(f"Kline collect failed {symbol} {interval}: {e}")


async def _process_symbol(symbol: str, interval: str, tick: int) -> None:
    """Run analysis modules for a single symbol."""
    try:
        # Indicators: every tick (for primary interval)
        from .technical_analysis import compute_indicators, store_indicators
        indicators = compute_indicators(symbol, interval)
        if indicators:
            store_indicators(indicators)

        # Entropy: every 5 ticks
        if tick % 5 == 0:
            from .entropy_filter import compute_entropy, store_entropy
            entropy = compute_entropy(symbol, interval)
            if entropy:
                store_entropy(entropy)

        # Regime: every 15 ticks
        if tick % 15 == 0:
            from .regime_detector import detect_regime, store_regime
            regime = detect_regime(symbol, interval)
            if regime:
                store_regime(regime)

        # S/R levels: every 60 ticks
        if tick % 60 == 0:
            from .support_resistance import compute_sr_levels, store_sr_levels
            sr = compute_sr_levels(symbol, interval)
            if sr:
                store_sr_levels(sr)

    except Exception as e:
        msg = f"Process {symbol} error: {e}"
        logger.error(msg)
        _errors.append(msg)


async def _update_performance_metrics() -> None:
    """Compute and store rolling performance metrics for all_time, 30d and 7d windows."""
    from ..db import get_supabase
    from datetime import timedelta
    import numpy as np

    supabase = get_supabase()
    now_dt = datetime.now(timezone.utc)

    windows = {
        "all_time": None,
        "rolling_30d": now_dt - timedelta(days=30),
        "rolling_7d": now_dt - timedelta(days=7),
    }

    for metric_type, since in windows.items():
        try:
            query = supabase.table("positions").select(
                "realized_pnl,entry_notional,opened_at,closed_at"
            ).eq("status", "closed")
            if since:
                query = query.gte("closed_at", since.isoformat())
            resp = query.execute()

            if not resp.data or len(resp.data) < 2:
                continue

            positions = resp.data
            pnls = [float(p.get("realized_pnl", 0) or 0) for p in positions]
            notionals = [float(p.get("entry_notional", 0) or 1) for p in positions]
            returns = [p / n if n > 0 else 0 for p, n in zip(pnls, notionals)]

            wins = [r for r in returns if r > 0]
            losses = [abs(r) for r in returns if r < 0]

            total = len(returns)
            win_rate = len(wins) / total if total > 0 else 0
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            profit_factor = (sum(wins) / sum(losses)) if losses and sum(losses) > 0 else None
            expectancy = sum(pnls) / total if total > 0 else 0

            returns_arr = np.array(returns)

            # Sharpe ratio (annualised, simplified)
            sharpe = None
            if len(returns_arr) > 1 and np.std(returns_arr) > 0:
                sharpe = round(float(np.mean(returns_arr) / np.std(returns_arr) * np.sqrt(252)), 4)

            # Sortino ratio
            sortino = None
            downside = returns_arr[returns_arr < 0]
            if len(downside) > 0 and np.std(downside) > 0:
                sortino = round(float(np.mean(returns_arr) / np.std(downside) * np.sqrt(252)), 4)

            # Max drawdown (in USD)
            cumulative = np.cumsum(pnls)
            peak = np.maximum.accumulate(cumulative)
            drawdowns = cumulative - peak
            max_dd = round(float(np.min(drawdowns)), 4) if len(drawdowns) > 0 else 0

            # Calmar ratio = annualised_return / |max_drawdown|
            calmar = None
            if max_dd < 0:
                annualised_return = sum(pnls) * (252 / max(total, 1))
                calmar = round(annualised_return / abs(max_dd), 4)

            # Kelly fraction (half-Kelly)
            kelly = None
            if avg_loss > 0 and 0 < win_rate < 1:
                b = avg_win / avg_loss
                kelly = round((win_rate * b - (1 - win_rate)) / b * settings.kelly_dampener, 4)

            now = datetime.now(timezone.utc).isoformat()
            metrics = {
                "metric_type": metric_type,
                "sharpe_ratio": sharpe,
                "sortino_ratio": sortino,
                "calmar_ratio": calmar,
                "max_drawdown": max_dd,
                "win_rate": round(win_rate, 4),
                "profit_factor": round(profit_factor, 4) if profit_factor else None,
                "expectancy": round(expectancy, 8),
                "kelly_fraction": kelly,
                "total_trades": total,
                "avg_win": round(avg_win, 8),
                "avg_loss": round(avg_loss, 8),
                "calculated_at": now,
            }

            supabase.table("performance_metrics").upsert(
                metrics, on_conflict="metric_type"
            ).execute()
            logger.info(f"Performance metrics updated: {metric_type} ({total} trades)")

        except Exception as e:
            logger.error(f"Performance metrics update failed for {metric_type}: {e}")


async def get_quant_snapshot(symbol: str) -> Optional[QuantSnapshot]:
    """Get the complete quant analysis snapshot for a symbol (for LLM injection)."""
    cache = get_analysis_cache()
    cache_key = f"snapshot:{symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    interval = settings.quant_primary_interval

    from .technical_analysis import compute_indicators
    from .entropy_filter import compute_entropy
    from .regime_detector import detect_regime
    from .support_resistance import compute_sr_levels
    from .position_sizer import compute_position_size

    indicators = compute_indicators(symbol, interval)
    entropy = compute_entropy(symbol, interval)
    regime = detect_regime(symbol, interval)
    sr = compute_sr_levels(symbol, interval)
    sizing = await compute_position_size(symbol, interval)

    trade_blocks = []
    if entropy and not entropy.is_tradable:
        trade_blocks.append(f"entropy_high ({entropy.entropy_ratio:.3f})")
    if regime and regime.regime == "volatile" and regime.confidence > 60:
        trade_blocks.append(f"regime_volatile ({regime.confidence:.1f}%)")

    snapshot = QuantSnapshot(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        indicators=indicators,
        entropy=entropy,
        regime=regime,
        sr_levels=sr,
        position_sizing=sizing,
        is_tradable=len(trade_blocks) == 0,
        trade_blocks=trade_blocks,
    )

    cache.set(cache_key, snapshot, ttl=60)
    return snapshot


def get_engine_status() -> QuantEngineStatus:
    """Get current quant engine status."""
    symbols = settings.quant_symbols.split(",")
    return QuantEngineStatus(
        enabled=settings.quant_enabled,
        tick_count=_tick_count,
        last_tick_at=_last_tick_at,
        symbols=symbols,
        primary_interval=settings.quant_primary_interval,
        modules={
            "kline_collector": {"status": "active"},
            "technical_analysis": {"status": "active"},
            "entropy_filter": {"status": "active", "threshold": settings.entropy_threshold_ratio},
            "regime_detector": {"status": "active"},
            "support_resistance": {"status": "active", "clusters": settings.sr_clusters},
            "position_sizer": {"status": "active", "kelly_dampener": settings.kelly_dampener},
        },
        errors=_errors[-10:],  # Last 10 errors
    )
