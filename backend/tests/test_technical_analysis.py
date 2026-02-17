"""Unit tests for technical_analysis.py."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


def test_compute_indicators_returns_none_with_insufficient_data(mock_supabase):
    """Should return None when DataFrame has < 50 rows."""
    n = 30
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=timezone.utc)
    small_df = pd.DataFrame(
        {"open": [50000.0] * n, "high": [51000.0] * n,
         "low": [49000.0] * n, "close": [50000.0] * n,
         "volume": [100.0] * n, "quote_volume": [5000000.0] * n},
        index=dates,
    )
    with patch("app.services.technical_analysis._load_klines_df", return_value=small_df), \
         patch("app.services.technical_analysis.get_supabase", return_value=mock_supabase), \
         patch("app.services.technical_analysis.get_kline_cache"), \
         patch("app.services.technical_analysis.get_indicator_cache", return_value=MagicMock(get=lambda k: None, set=lambda *a, **kw: None)):
        from app.services.technical_analysis import compute_indicators
        result = compute_indicators("BTCUSDT", "1h")
    assert result is None


def test_compute_indicators_returns_none_when_no_df(mock_supabase):
    """Should return None when _load_klines_df returns None."""
    with patch("app.services.technical_analysis._load_klines_df", return_value=None), \
         patch("app.services.technical_analysis.get_supabase", return_value=mock_supabase), \
         patch("app.services.technical_analysis.get_indicator_cache", return_value=MagicMock(get=lambda k: None, set=lambda *a, **kw: None)):
        from app.services.technical_analysis import compute_indicators
        result = compute_indicators("BTCUSDT", "1h")
    assert result is None


def test_compute_indicators_rsi_in_valid_range(trending_df, mock_supabase):
    """RSI must be in [0, 100] when computable."""
    with patch("app.services.technical_analysis._load_klines_df", return_value=trending_df), \
         patch("app.services.technical_analysis.get_supabase", return_value=mock_supabase), \
         patch("app.services.technical_analysis.get_indicator_cache", return_value=MagicMock(get=lambda k: None, set=lambda *a, **kw: None)):
        from app.services.technical_analysis import compute_indicators
        result = compute_indicators("BTCUSDT", "1h")

    assert result is not None
    if result.rsi_14 is not None:
        assert 0.0 <= result.rsi_14 <= 100.0


def test_compute_indicators_atr_is_positive(trending_df, mock_supabase):
    """ATR(14) should be positive."""
    with patch("app.services.technical_analysis._load_klines_df", return_value=trending_df), \
         patch("app.services.technical_analysis.get_supabase", return_value=mock_supabase), \
         patch("app.services.technical_analysis.get_indicator_cache", return_value=MagicMock(get=lambda k: None, set=lambda *a, **kw: None)):
        from app.services.technical_analysis import compute_indicators
        result = compute_indicators("BTCUSDT", "1h")

    if result and result.atr_14 is not None:
        assert result.atr_14 > 0.0


def test_compute_indicators_symbol_and_interval_set(trending_df, mock_supabase):
    """Symbol and interval should be set correctly on result."""
    with patch("app.services.technical_analysis._load_klines_df", return_value=trending_df), \
         patch("app.services.technical_analysis.get_supabase", return_value=mock_supabase), \
         patch("app.services.technical_analysis.get_indicator_cache", return_value=MagicMock(get=lambda k: None, set=lambda *a, **kw: None)):
        from app.services.technical_analysis import compute_indicators
        result = compute_indicators("ETHUSDT", "4h")

    if result:
        assert result.symbol == "ETHUSDT"
        assert result.interval == "4h"


def test_store_indicators_calls_upsert(mock_supabase):
    """store_indicators should upsert to technical_indicators table."""
    from app.models.quant_models import TechnicalIndicators
    ind = TechnicalIndicators(
        symbol="BTCUSDT", interval="1h",
        candle_time=datetime.now(timezone.utc),
        rsi_14=55.0, adx_14=30.0, atr_14=500.0,
    )
    with patch("app.services.technical_analysis.get_supabase", return_value=mock_supabase):
        from app.services.technical_analysis import store_indicators
        store_indicators(ind)
    mock_supabase.table.assert_called_with("technical_indicators")
