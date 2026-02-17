"""Shared fixtures for quant engine unit tests."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import MagicMock


def make_trending_df(n: int = 200) -> pd.DataFrame:
    """Strongly trending OHLCV data (low entropy, clear direction)."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=timezone.utc)
    close = 50000.0 + np.arange(n) * 50 + np.random.normal(0, 80, n)
    high = close + np.abs(np.random.normal(0, 50, n))
    low = close - np.abs(np.random.normal(0, 50, n))
    open_ = close - np.random.normal(0, 30, n)
    volume = np.abs(np.random.normal(100, 15, n)) + 10
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": volume, "quote_volume": close * volume},
        index=dates,
    )
    return df


def make_noisy_df(n: int = 200) -> pd.DataFrame:
    """Pure random-walk OHLCV data (high entropy)."""
    np.random.seed(0)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=timezone.utc)
    returns = np.random.choice([-1, 1], size=n) * np.random.uniform(0.001, 0.02, n)
    close = 50000.0 * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(np.random.normal(0, 0.005, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.005, n)))
    open_ = close * (1 + np.random.normal(0, 0.003, n))
    volume = np.abs(np.random.normal(100, 50, n)) + 10
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": volume, "quote_volume": close * volume},
        index=dates,
    )
    return df


@pytest.fixture
def trending_df() -> pd.DataFrame:
    return make_trending_df()


@pytest.fixture
def noisy_df() -> pd.DataFrame:
    return make_noisy_df()


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Mock Supabase client returning empty data by default."""
    mock = MagicMock()
    empty = MagicMock()
    empty.data = []
    empty.count = 0
    # Most common call chains
    mock.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = empty
    mock.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = empty
    mock.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = empty
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = empty
    mock.table.return_value.select.return_value.execute.return_value = empty
    mock.table.return_value.upsert.return_value.execute.return_value = empty
    mock.table.return_value.insert.return_value.execute.return_value = empty
    mock.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = empty
    mock.table.return_value.delete.return_value.eq.return_value.execute.return_value = empty
    mock.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = empty
    return mock
