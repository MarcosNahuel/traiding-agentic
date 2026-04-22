"""Unit tests for regime_detector.py."""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def _make_indicators(adx=20.0, bb_bw=0.05, atr=500.0, rsi=50.0):
    from app.models.quant_models import TechnicalIndicators
    return TechnicalIndicators(
        symbol="BTCUSDT", interval="1h",
        candle_time=datetime.now(timezone.utc),
        adx_14=adx, bb_bandwidth=bb_bw, atr_14=atr, rsi_14=rsi,
        sma_20=50500.0, sma_50=50000.0,
    )


def _sideways_df(price: float = 50000.0, n: int = 200) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n, freq="1h", tz=timezone.utc)
    base = price + np.sin(np.linspace(0, 6 * np.pi, n)) * (price * 0.002)
    high = base * 1.001
    low = base * 0.999
    volume = np.full(n, 100.0)
    return pd.DataFrame(
        {
            "open": base,
            "high": high,
            "low": low,
            "close": base,
            "volume": volume,
            "quote_volume": base * volume,
        },
        index=dates,
    )


def test_detect_regime_returns_valid_result(trending_df, mock_supabase):
    """detect_regime should return MarketRegime with valid regime name."""
    indicators = _make_indicators(adx=35.0, bb_bw=0.04)
    with patch("app.services.regime_detector.compute_indicators", return_value=indicators), \
         patch("app.services.regime_detector._load_klines_df", return_value=trending_df), \
         patch("app.services.regime_detector.get_supabase", return_value=mock_supabase):
        from app.services.regime_detector import detect_regime
        result = detect_regime("BTCUSDT", "1h")
    assert result is not None
    assert result.regime in (
        "trending_up",
        "trending_down",
        "ranging",
        "ranging_low_vol",
        "ranging_high_vol",
        "volatile",
        "low_liquidity",
    )


def test_detect_regime_confidence_in_range(trending_df, mock_supabase):
    """Confidence must be in [0, 100]."""
    indicators = _make_indicators()
    with patch("app.services.regime_detector.compute_indicators", return_value=indicators), \
         patch("app.services.regime_detector._load_klines_df", return_value=trending_df), \
         patch("app.services.regime_detector.get_supabase", return_value=mock_supabase):
        from app.services.regime_detector import detect_regime
        result = detect_regime("BTCUSDT", "1h")
    if result:
        assert 0.0 <= result.confidence <= 100.0


def test_detect_regime_returns_none_without_indicators(trending_df, mock_supabase):
    """Should return None when indicators are unavailable."""
    with patch("app.services.regime_detector.compute_indicators", return_value=None), \
         patch("app.services.regime_detector._load_klines_df", return_value=trending_df), \
         patch("app.services.regime_detector.get_supabase", return_value=mock_supabase):
        from app.services.regime_detector import detect_regime
        result = detect_regime("BTCUSDT", "1h")
    assert result is None


def test_store_regime_uses_market_regimes_table(mock_supabase):
    """store_regime should upsert to market_regimes table."""
    from app.models.quant_models import MarketRegime
    regime = MarketRegime(
        symbol="BTCUSDT", interval="1h",
        regime="trending_up", confidence=75.0,
        adx_value=35.0, bb_bandwidth=0.05,
        atr_close_ratio=0.01, hurst_exponent=0.65,
    )
    with patch("app.services.regime_detector.get_supabase", return_value=mock_supabase):
        from app.services.regime_detector import store_regime
        store_regime(regime)
    mock_supabase.table.assert_called_with("market_regimes")


def test_detect_regime_ranging_low_vol(mock_supabase):
    """Low ADX + low ATR + neutral Hurst should classify as ranging_low_vol."""
    indicators = _make_indicators(adx=16.0, bb_bw=0.03, atr=300.0)
    df = _sideways_df(price=50000.0)
    with patch("app.services.regime_detector.compute_indicators", return_value=indicators), \
         patch("app.services.regime_detector._load_klines_df", return_value=df), \
         patch("app.services.regime_detector._hurst_exponent", return_value=0.5), \
         patch("app.services.regime_detector.get_supabase", return_value=mock_supabase):
        from app.services.regime_detector import detect_regime
        result = detect_regime("BTCUSDT", "1h")

    assert result is not None
    assert result.regime == "ranging_low_vol"


def test_detect_regime_ranging_high_vol(mock_supabase):
    """Low ADX + neutral Hurst but elevated ATR should classify as ranging_high_vol."""
    indicators = _make_indicators(adx=17.0, bb_bw=0.07, atr=900.0)
    df = _sideways_df(price=50000.0)
    with patch("app.services.regime_detector.compute_indicators", return_value=indicators), \
         patch("app.services.regime_detector._load_klines_df", return_value=df), \
         patch("app.services.regime_detector._hurst_exponent", return_value=0.5), \
         patch("app.services.regime_detector.get_supabase", return_value=mock_supabase):
        from app.services.regime_detector import detect_regime
        result = detect_regime("BTCUSDT", "1h")

    assert result is not None
    assert result.regime == "ranging_high_vol"
