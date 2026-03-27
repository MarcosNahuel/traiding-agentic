"""Tests para estrategias QuantScience (Mar 2026).

QS1: PPO (Percentage Price Oscillator) — reemplaza MACD raw
QS2: Autocorrelación pre-trade — confirmación de momentum
QS3: Filtro de volumen relativo — vol > 1.2× media
QS4: Chandelier Exit — trailing basado en highest high - k*ATR
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone


# ════════════════════════════════════════════════════════════════════
# QS1: PPO (Percentage Price Oscillator)
# ════════════════════════════════════════════════════════════════════

def test_ppo_computed_in_indicators():
    """TechnicalIndicators should include ppo field."""
    from app.models.quant_models import TechnicalIndicators
    ti = TechnicalIndicators(
        symbol="BTCUSDT", interval="1h",
        candle_time=datetime.now(timezone.utc),
        ppo=1.5,
    )
    assert ti.ppo == 1.5


def test_ppo_calculation_is_percentage():
    """PPO = (EMA12 - EMA26) / EMA26 * 100. Must be normalized by price."""
    from app.services.technical_analysis import compute_ppo
    # EMA12=105, EMA26=100 → PPO = (105-100)/100*100 = 5.0%
    assert compute_ppo(105.0, 100.0) == pytest.approx(5.0)


def test_ppo_negative():
    """PPO should be negative when EMA12 < EMA26 (bearish)."""
    from app.services.technical_analysis import compute_ppo
    # EMA12=95, EMA26=100 → PPO = (95-100)/100*100 = -5.0%
    assert compute_ppo(95.0, 100.0) == pytest.approx(-5.0)


def test_ppo_zero_division():
    """PPO should return None if EMA26 is zero or None."""
    from app.services.technical_analysis import compute_ppo
    assert compute_ppo(100.0, 0.0) is None
    assert compute_ppo(100.0, None) is None


# ════════════════════════════════════════════════════════════════════
# QS2: Autocorrelación pre-trade
# ════════════════════════════════════════════════════════════════════

def test_autocorrelation_computed():
    """TechnicalIndicators should include autocorr_1 field."""
    from app.models.quant_models import TechnicalIndicators
    ti = TechnicalIndicators(
        symbol="BTCUSDT", interval="1h",
        candle_time=datetime.now(timezone.utc),
        autocorr_1=0.15,
    )
    assert ti.autocorr_1 == 0.15


def test_autocorrelation_trending_series():
    """Autocorrelation of a trending series should be positive."""
    from app.services.technical_analysis import compute_autocorrelation
    # Strongly trending: each return similar to previous
    prices = pd.Series([100 + i * 0.5 for i in range(50)])
    result = compute_autocorrelation(prices, lag=1)
    assert result is not None
    assert result > 0.0


def test_autocorrelation_mean_reverting_series():
    """Autocorrelation of alternating series should be negative."""
    from app.services.technical_analysis import compute_autocorrelation
    # Mean-reverting: up-down-up-down
    prices = pd.Series([100 + (-1)**i * 2 for i in range(50)])
    result = compute_autocorrelation(prices, lag=1)
    assert result is not None
    assert result < 0.0


def test_autocorrelation_insufficient_data():
    """Should return None with too few data points."""
    from app.services.technical_analysis import compute_autocorrelation
    prices = pd.Series([100, 101, 102])
    assert compute_autocorrelation(prices, lag=1) is None


# ════════════════════════════════════════════════════════════════════
# QS3: Filtro de volumen relativo
# ════════════════════════════════════════════════════════════════════

def test_volume_ratio_computed():
    """TechnicalIndicators should include volume_ratio field."""
    from app.models.quant_models import TechnicalIndicators
    ti = TechnicalIndicators(
        symbol="BTCUSDT", interval="1h",
        candle_time=datetime.now(timezone.utc),
        volume_ratio=1.5,
    )
    assert ti.volume_ratio == 1.5


def test_volume_ratio_high_volume():
    """Volume 2x the 20-period average → ratio = 2.0."""
    from app.services.technical_analysis import compute_volume_ratio
    volumes = pd.Series([100.0] * 20 + [200.0])
    result = compute_volume_ratio(volumes, window=20)
    assert result is not None
    assert result == pytest.approx(2.0, rel=0.01)


def test_volume_ratio_low_volume():
    """Volume half the average → ratio = 0.5."""
    from app.services.technical_analysis import compute_volume_ratio
    volumes = pd.Series([100.0] * 20 + [50.0])
    result = compute_volume_ratio(volumes, window=20)
    assert result is not None
    assert result == pytest.approx(0.5, rel=0.01)


def test_buy_blocked_when_volume_low():
    """BUY should be blocked when volume_ratio < 1.2."""
    with patch("app.services.signal_generator.compute_indicators") as mock_ind, \
         patch("app.services.signal_generator.compute_entropy") as mock_ent, \
         patch("app.services.signal_generator.detect_regime") as mock_reg, \
         patch("app.services.signal_generator.binance_client") as mock_bc, \
         patch("app.services.signal_generator.settings") as mock_s, \
         patch("app.services.signal_generator._submit_proposal", new_callable=AsyncMock) as mock_submit, \
         patch("app.services.signal_generator._cooled_down", return_value=True):

        ind = MagicMock()
        ind.rsi_14 = 30.0
        ind.macd_histogram = 2.0
        ind.adx_14 = 30.0
        ind.sma_20 = 51000.0
        ind.sma_50 = 50000.0
        ind.ppo = 1.0
        ind.autocorr_1 = 0.1
        ind.volume_ratio = 0.8  # TOO LOW — should block
        mock_ind.return_value = ind

        ent = MagicMock()
        ent.entropy_ratio = 0.5
        mock_ent.return_value = ent

        reg = MagicMock()
        reg.regime = "ranging"
        reg.confidence = 50.0
        mock_reg.return_value = reg

        mock_s.quant_primary_interval = "1h"
        mock_s.buy_adx_min = 20.0
        mock_s.buy_entropy_max = 0.85
        mock_s.buy_regime_confidence_min = 80.0
        mock_bc.get_price = AsyncMock(return_value={"price": "50000.0"})

        import asyncio
        from app.services.signal_generator import _evaluate_symbol
        asyncio.get_event_loop().run_until_complete(
            _evaluate_symbol(MagicMock(), "BTCUSDT", set(), 0)
        )

    mock_submit.assert_not_called()


# ════════════════════════════════════════════════════════════════════
# QS4: Chandelier Exit
# ════════════════════════════════════════════════════════════════════

def test_chandelier_exit_basic():
    """Chandelier Exit: SL = highest_high - k * ATR."""
    from app.services.trading_loop import compute_chandelier_sl
    # Highest high = 110, ATR = 5, multiplier = 2.0
    sl = compute_chandelier_sl(highest_high=110.0, atr=5.0, multiplier=2.0)
    assert sl == 100.0


def test_chandelier_exit_with_real_prices():
    """Chandelier with BTC-like prices."""
    from app.services.trading_loop import compute_chandelier_sl
    # BTC highest = 71000, ATR = 800, multiplier = 2.0
    sl = compute_chandelier_sl(highest_high=71000.0, atr=800.0, multiplier=2.0)
    assert sl == 69400.0


def test_chandelier_exit_none_on_invalid():
    """Should return None if ATR or highest_high is None/zero."""
    from app.services.trading_loop import compute_chandelier_sl
    assert compute_chandelier_sl(0.0, 5.0, 2.0) is None
    assert compute_chandelier_sl(110.0, 0.0, 2.0) is None
    assert compute_chandelier_sl(110.0, None, 2.0) is None
