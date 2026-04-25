"""Smoke tests for kline_loader.py.

Skips if data/diagnostics/klines.parquet does not exist (e.g. on CI).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

KLINES_PATH = Path("data/diagnostics/klines.parquet")
pytestmark = pytest.mark.skipif(
    not KLINES_PATH.exists(),
    reason="klines parquet not generated (run 01_fetch_klines.py)",
)


def _loader():
    from backend.scripts.diagnostics.lib.kline_loader import KlineLoader
    return KlineLoader(KLINES_PATH)


def test_loader_loads_some_data():
    loader = _loader()
    assert len(loader.symbols) >= 1
    assert "1m" in loader.intervals or "1h" in loader.intervals


def test_slice_returns_dataframe():
    loader = _loader()
    sym = loader.symbols[0]
    iv = loader.intervals[0]
    df = loader.slice(sym, iv)
    assert len(df) > 0
    assert {"open", "high", "low", "close", "volume"}.issubset(df.columns)


def test_kline_at_finds_known_timestamp():
    loader = _loader()
    sym = loader.symbols[0]
    iv = loader.intervals[0]
    df = loader.slice(sym, iv).iloc[:5]
    if df.empty:
        pytest.skip("no data")
    # pick a timestamp inside the first kline
    target = df.iloc[0]["open_time"] + (df.iloc[0]["close_time"] - df.iloc[0]["open_time"]) / 2
    kl = loader.kline_at(sym, iv, target)
    assert kl is not None
    assert kl["open_time"] == df.iloc[0]["open_time"]


def test_kline_at_returns_none_outside_range():
    loader = _loader()
    sym = loader.symbols[0]
    iv = loader.intervals[0]
    far_past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    assert loader.kline_at(sym, iv, far_past) is None
