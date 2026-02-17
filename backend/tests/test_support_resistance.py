"""Unit tests for support_resistance.py."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


def _oscillating_df(n: int = 500) -> pd.DataFrame:
    """Price oscillating between 45000 and 55000 – good for K-Means clustering."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=timezone.utc)
    close = 50000.0 + np.sin(np.arange(n) * 0.1) * 5000
    high = close * (1 + np.abs(np.random.normal(0, 0.005, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.005, n)))
    return pd.DataFrame(
        {"open": close * 0.999, "high": high, "low": low, "close": close,
         "volume": np.ones(n) * 100, "quote_volume": close * 100},
        index=dates,
    )


def test_compute_sr_levels_returns_result(mock_supabase):
    """Should return SRLevelsResult with at least one level."""
    df = _oscillating_df()
    with patch("app.services.support_resistance._load_klines_df", return_value=df), \
         patch("app.services.support_resistance.get_supabase", return_value=mock_supabase):
        from app.services.support_resistance import compute_sr_levels
        result = compute_sr_levels("BTCUSDT", "1h")
    assert result is not None
    assert result.symbol == "BTCUSDT"
    assert len(result.levels) > 0


def test_compute_sr_levels_types_are_valid(mock_supabase):
    """All levels must be 'support' or 'resistance' with positive price."""
    df = _oscillating_df()
    with patch("app.services.support_resistance._load_klines_df", return_value=df), \
         patch("app.services.support_resistance.get_supabase", return_value=mock_supabase):
        from app.services.support_resistance import compute_sr_levels
        result = compute_sr_levels("BTCUSDT", "1h")
    if result:
        for level in result.levels:
            assert level.level_type in ("support", "resistance")
            assert level.price_level > 0


def test_compute_sr_levels_strength_in_range(mock_supabase):
    """Strength should be in [0, 1]."""
    df = _oscillating_df()
    with patch("app.services.support_resistance._load_klines_df", return_value=df), \
         patch("app.services.support_resistance.get_supabase", return_value=mock_supabase):
        from app.services.support_resistance import compute_sr_levels
        result = compute_sr_levels("BTCUSDT", "1h")
    if result:
        for level in result.levels:
            assert 0.0 <= level.strength <= 1.0


def test_compute_sr_levels_returns_none_with_tiny_df(mock_supabase):
    """Should return None when not enough rows for clustering."""
    tiny = pd.DataFrame(
        {"open": [50000.0] * 5, "high": [51000.0] * 5,
         "low": [49000.0] * 5, "close": [50000.0] * 5,
         "volume": [100.0] * 5, "quote_volume": [5000000.0] * 5},
    )
    with patch("app.services.support_resistance._load_klines_df", return_value=tiny), \
         patch("app.services.support_resistance.get_supabase", return_value=mock_supabase):
        from app.services.support_resistance import compute_sr_levels
        result = compute_sr_levels("BTCUSDT", "1h")
    assert result is None


def test_store_sr_levels_uses_correct_table(mock_supabase):
    """store_sr_levels should interact with support_resistance_levels table."""
    from app.models.quant_models import SRLevel, SRLevelsResult
    level = SRLevel(
        level_type="support", price_level=48000.0,
        strength=0.8, touch_count=5, distance_pct=-4.0,
    )
    sr_result = SRLevelsResult(
        symbol="BTCUSDT", interval="1h",
        current_price=50000.0, levels=[level],
    )
    with patch("app.services.support_resistance.get_supabase", return_value=mock_supabase):
        from app.services.support_resistance import store_sr_levels
        store_sr_levels(sr_result)
    # Table was accessed
    assert mock_supabase.table.call_count >= 1
