"""Market regime detector.

Classifies the current market state using multiple features:
- ADX (trend strength)
- Bollinger Bandwidth (volatility)
- ATR/Close ratio (normalized volatility)
- Hurst Exponent (trending vs mean-reverting)

Regimes: trending_up, trending_down, ranging, volatile, low_liquidity
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from ..db import get_supabase
from ..config import settings
from ..models.quant_models import MarketRegime
from .technical_analysis import compute_indicators, _load_klines_df

logger = logging.getLogger(__name__)


def _hurst_exponent(prices: np.ndarray, max_lag: int = 20) -> float:
    """Estimate Hurst exponent using R/S (rescaled range) analysis.

    H < 0.5: mean-reverting
    H = 0.5: random walk
    H > 0.5: trending
    """
    if len(prices) < max_lag * 2:
        return 0.5  # Default to random walk

    lags = range(2, max_lag + 1)
    rs_values = []

    for lag in lags:
        # Split into non-overlapping sub-series
        n_subseries = len(prices) // lag
        if n_subseries < 1:
            continue

        rs_for_lag = []
        for i in range(n_subseries):
            subseries = prices[i * lag : (i + 1) * lag]
            if len(subseries) < 2:
                continue
            returns = np.diff(subseries)
            mean_ret = np.mean(returns)
            deviations = np.cumsum(returns - mean_ret)
            r = np.max(deviations) - np.min(deviations)
            s = np.std(returns, ddof=1) if np.std(returns, ddof=1) > 0 else 1e-10
            rs_for_lag.append(r / s)

        if rs_for_lag:
            rs_values.append((np.log(lag), np.log(np.mean(rs_for_lag))))

    if len(rs_values) < 3:
        return 0.5

    log_lags, log_rs = zip(*rs_values)
    # Linear regression: log(R/S) = H * log(n) + c
    try:
        coeffs = np.polyfit(log_lags, log_rs, 1)
        hurst = float(coeffs[0])
        return max(0.0, min(1.0, hurst))  # Clamp to [0, 1]
    except Exception:
        return 0.5


def detect_regime(symbol: str, interval: str = "1h") -> Optional[MarketRegime]:
    """Detect the current market regime for a symbol."""
    indicators = compute_indicators(symbol, interval)
    if indicators is None:
        return None

    df = _load_klines_df(symbol, interval, limit=250)
    if df is None:
        return None

    try:
        adx = indicators.adx_14 or 0.0
        bb_bw = indicators.bb_bandwidth or 0.0
        atr = indicators.atr_14 or 0.0
        close = float(df["close"].iloc[-1])
        atr_ratio = atr / close if close > 0 else 0.0

        # Hurst exponent
        prices = df["close"].values[-100:]
        hurst = _hurst_exponent(prices)

        # Decision tree classification
        regime = "ranging"
        confidence = 50.0

        if adx > 40 and hurst > 0.6:
            # Strong trend
            sma_20 = indicators.sma_20 or close
            if close > sma_20:
                regime = "trending_up"
                confidence = min(90.0, 50 + adx)
            else:
                regime = "trending_down"
                confidence = min(90.0, 50 + adx)
        elif adx > 25 and hurst > 0.55:
            # Moderate trend
            sma_20 = indicators.sma_20 or close
            if close > sma_20:
                regime = "trending_up"
                confidence = min(75.0, 40 + adx)
            else:
                regime = "trending_down"
                confidence = min(75.0, 40 + adx)
        elif bb_bw > 0.08 or atr_ratio > 0.04:
            # High volatility
            regime = "volatile"
            confidence = min(85.0, 50 + bb_bw * 200)
        elif adx < 20 and 0.4 < hurst < 0.6:
            # Ranging / mean-reverting
            regime = "ranging"
            confidence = min(80.0, 60 + (20 - adx))
        # Low liquidity detection via volume
        elif df["volume"].iloc[-5:].mean() < df["volume"].mean() * 0.3:
            regime = "low_liquidity"
            confidence = 60.0

        result = MarketRegime(
            symbol=symbol,
            interval=interval,
            regime=regime,
            confidence=round(confidence, 2),
            adx_value=round(adx, 4) if adx else None,
            bb_bandwidth=round(bb_bw, 6) if bb_bw else None,
            atr_close_ratio=round(atr_ratio, 6),
            hurst_exponent=round(hurst, 6),
        )
        return result

    except Exception as e:
        logger.error(f"Error detecting regime for {symbol}: {e}")
        return None


def store_regime(regime: MarketRegime) -> None:
    """Store/update regime in DB."""
    supabase = get_supabase()
    data = regime.model_dump()
    data["detected_at"] = datetime.now(timezone.utc).isoformat()

    try:
        supabase.table("market_regimes").upsert(
            data, on_conflict="symbol,interval"
        ).execute()
    except Exception as e:
        logger.error(f"Failed to store regime: {e}")


def get_latest_regime(symbol: str, interval: str = "1h") -> Optional[dict]:
    """Get latest stored regime."""
    supabase = get_supabase()
    resp = (
        supabase.table("market_regimes")
        .select("*")
        .eq("symbol", symbol)
        .eq("interval", interval)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None
