"""Unit tests for entropy_filter.py."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


def _low_entropy_df(n: int = 150) -> pd.DataFrame:
    """Perfect linear trend → very low entropy."""
    np.random.seed(1)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=timezone.utc)
    close = 50000.0 + np.arange(n) * 100.0  # No noise
    return pd.DataFrame(
        {"open": close - 10, "high": close + 20, "low": close - 20,
         "close": close, "volume": np.ones(n) * 100, "quote_volume": close * 100},
        index=dates,
    )


def _high_entropy_df(n: int = 150) -> pd.DataFrame:
    """Uniformly random returns → high entropy."""
    np.random.seed(2)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=timezone.utc)
    # Each return chosen from a uniform set of 10 bins → max entropy
    bins = np.linspace(-0.02, 0.02, 10)
    returns = np.random.choice(bins, size=n)
    close = 50000.0 * np.exp(np.cumsum(returns))
    return pd.DataFrame(
        {"open": close * 0.999, "high": close * 1.002,
         "low": close * 0.998, "close": close,
         "volume": np.ones(n) * 100, "quote_volume": close * 100},
        index=dates,
    )


def test_compute_entropy_returns_result(mock_supabase):
    """compute_entropy should return EntropyReading when data is sufficient."""
    df = _high_entropy_df()
    with patch("app.services.entropy_filter._load_klines_df", return_value=df), \
         patch("app.services.entropy_filter.get_supabase", return_value=mock_supabase):
        from app.services.entropy_filter import compute_entropy
        result = compute_entropy("BTCUSDT", "1h")
    assert result is not None
    assert result.symbol == "BTCUSDT"
    assert result.interval == "1h"


def test_compute_entropy_ratio_in_range(mock_supabase):
    """entropy_ratio must be in [0, 1]."""
    df = _high_entropy_df()
    with patch("app.services.entropy_filter._load_klines_df", return_value=df), \
         patch("app.services.entropy_filter.get_supabase", return_value=mock_supabase):
        from app.services.entropy_filter import compute_entropy
        result = compute_entropy("BTCUSDT", "1h")
    if result:
        assert 0.0 <= result.entropy_ratio <= 1.0


def test_compute_entropy_returns_none_when_df_none(mock_supabase):
    """Should return None when _load_klines_df returns None."""
    with patch("app.services.entropy_filter._load_klines_df", return_value=None), \
         patch("app.services.entropy_filter.get_supabase", return_value=mock_supabase):
        from app.services.entropy_filter import compute_entropy
        result = compute_entropy("BTCUSDT", "1h")
    assert result is None


def test_compute_entropy_returns_none_with_tiny_df(mock_supabase):
    """Should return None when DataFrame has too few rows."""
    tiny = pd.DataFrame({"close": [50000.0] * 5})
    with patch("app.services.entropy_filter._load_klines_df", return_value=tiny), \
         patch("app.services.entropy_filter.get_supabase", return_value=mock_supabase):
        from app.services.entropy_filter import compute_entropy
        result = compute_entropy("BTCUSDT", "1h")
    assert result is None


def test_entropy_value_leq_max_entropy(mock_supabase):
    """entropy_value should never exceed max_entropy."""
    df = _high_entropy_df()
    with patch("app.services.entropy_filter._load_klines_df", return_value=df), \
         patch("app.services.entropy_filter.get_supabase", return_value=mock_supabase):
        from app.services.entropy_filter import compute_entropy
        result = compute_entropy("BTCUSDT", "1h")
    if result:
        assert result.entropy_value <= result.max_entropy + 1e-9


def test_store_entropy_calls_upsert(mock_supabase):
    """store_entropy should upsert to entropy_readings table."""
    from app.models.quant_models import EntropyReading
    reading = EntropyReading(
        symbol="BTCUSDT", interval="1h",
        entropy_value=2.5, max_entropy=3.32,
        entropy_ratio=0.75, is_tradable=True,
        window_size=100, bins_used=10,
    )
    with patch("app.services.entropy_filter.get_supabase", return_value=mock_supabase):
        from app.services.entropy_filter import store_entropy
        store_entropy(reading)
    mock_supabase.table.assert_called_with("entropy_readings")
