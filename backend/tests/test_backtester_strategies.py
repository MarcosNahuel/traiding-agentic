"""Unit tests for backtester strategy signal generators."""

import pandas as pd
import pytest
from datetime import datetime, timezone

pytest.importorskip("pandas_ta_classic")

from app.models.quant_models import BacktestResult
from app.services import backtester
from app.services.backtester import (
    STRATEGIES,
    _apply_max_hold_exits,
    _generate_breakout_volatility_v2_signals,
    _generate_mean_reversion_v2_signals,
    _generate_trend_momentum_v2_signals,
    get_backtest_presets,
    run_backtest_benchmark,
)


def test_new_strategies_registered():
    assert "trend_momentum_v2" in STRATEGIES
    assert "mean_reversion_v2" in STRATEGIES
    assert "breakout_volatility_v2" in STRATEGIES


def test_apply_max_hold_exits_forces_timeout_exit():
    idx = pd.date_range("2026-01-01", periods=6, freq="1h", utc=True)
    entries = pd.Series([True, False, False, False, False, False], index=idx)
    exits = pd.Series([False, False, False, False, False, False], index=idx)

    result = _apply_max_hold_exits(entries, exits, max_hold_bars=2)

    # Position opens at bar 0 and should be forcibly closed at bar 2.
    assert bool(result.iloc[2]) is True


def test_trend_momentum_v2_no_entries_with_extreme_adx_threshold(trending_df):
    entries, exits = _generate_trend_momentum_v2_signals(
        trending_df,
        {
            "adx_threshold": 200,
            "fast_period": 20,
            "slow_period": 50,
        },
    )

    assert entries.dtype == bool
    assert exits.dtype == bool
    assert len(entries) == len(trending_df)
    assert len(exits) == len(trending_df)
    assert int(entries.sum()) == 0


def test_mean_reversion_v2_generates_entries_with_loose_thresholds(noisy_df):
    entries, exits = _generate_mean_reversion_v2_signals(
        noisy_df,
        {
            "z_window": 30,
            "z_entry": 0.5,   # very loose
            "adx_max": 100,   # disable adx gate
            "rsi_entry": 100, # disable rsi gate
        },
    )

    assert entries.dtype == bool
    assert exits.dtype == bool
    assert len(entries) == len(noisy_df)
    assert len(exits) == len(noisy_df)
    assert int(entries.sum()) > 0


def test_breakout_volatility_v2_no_entries_when_never_expanding(trending_df):
    entries, exits = _generate_breakout_volatility_v2_signals(
        trending_df,
        {
            "squeeze_pct": 1.0,  # squeeze always true -> never expanding
            "bb_length": 20,
            "bb_std": 2.0,
        },
    )

    assert entries.dtype == bool
    assert exits.dtype == bool
    assert len(entries) == len(trending_df)
    assert int(entries.sum()) == 0


def test_backtest_presets_have_expected_matrix():
    presets = get_backtest_presets()
    assert "spot" in presets
    assert "futures" in presets
    assert "intraday" in presets["spot"]
    assert isinstance(presets["spot"]["intraday"], list)
    assert len(presets["spot"]["intraday"]) > 0


@pytest.mark.asyncio
async def test_run_backtest_benchmark_ranks_and_persists(monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_run_backtest(req):
        by_strategy = {
            "breakout_volatility_v2": {"total_return": 0.12, "sharpe_ratio": 1.4, "max_drawdown": 0.08, "profit_factor": 1.4},
            "mean_reversion_v2": {"total_return": 0.05, "sharpe_ratio": 0.9, "max_drawdown": 0.06, "profit_factor": 1.2},
            "trend_momentum_v2": {"total_return": 0.08, "sharpe_ratio": 1.1, "max_drawdown": 0.09, "profit_factor": 1.3},
        }
        stats = by_strategy.get(req.strategy_id, by_strategy["mean_reversion_v2"])
        return BacktestResult(
            strategy_id=req.strategy_id,
            symbol=req.symbol,
            interval=req.interval,
            start_date=now,
            end_date=now,
            parameters=req.parameters,
            total_return=stats["total_return"],
            sharpe_ratio=stats["sharpe_ratio"],
            max_drawdown=stats["max_drawdown"],
            profit_factor=stats["profit_factor"],
            total_trades=20,
        )

    stored_results = []

    def fake_store_backtest_result(result):
        stored_results.append(result)
        return f"fake-{len(stored_results)}"

    monkeypatch.setattr(backtester, "run_backtest", fake_run_backtest)
    monkeypatch.setattr(backtester, "store_backtest_result", fake_store_backtest_result)

    benchmark = await run_backtest_benchmark(
        symbol="BTCUSDT",
        market="spot",
        horizon="scalping",
        lookback_days=20,
        store_results=True,
    )

    results = benchmark["results"]
    assert benchmark["total_tested"] == len(backtester.STRATEGY_PRESETS["spot"]["scalping"])
    assert benchmark["total_ranked"] == len(results)
    assert len(stored_results) == len(results)
    assert [r["rank"] for r in results] == list(range(1, len(results) + 1))
    assert [r["rank_score"] for r in results] == sorted(
        [r["rank_score"] for r in results], reverse=True
    )

    for stored in stored_results:
        assert "_benchmark" in stored.parameters
        meta = stored.parameters["_benchmark"]
        assert meta["market"] == "spot"
        assert meta["horizon"] == "scalping"
