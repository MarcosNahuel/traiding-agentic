"""Shannon Entropy filter for market noise detection.

When entropy is high (close to max), the market is noisy/random and trading
should be blocked to avoid losses from indeterminate conditions.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from ..db import get_supabase
from ..config import settings
from ..models.quant_models import EntropyReading
from .technical_analysis import _load_klines_df

logger = logging.getLogger(__name__)


def compute_entropy(symbol: str, interval: str = "1h") -> Optional[EntropyReading]:
    """Compute Shannon entropy of log-returns.

    Process:
    1. Get last N candles (entropy_window)
    2. Compute log-returns: ln(close_t / close_{t-1})
    3. Discretize into bins
    4. H = -sum(p * log2(p))
    5. Compare H / H_max with threshold
    """
    window = settings.entropy_window
    bins = settings.entropy_bins
    threshold = settings.entropy_threshold_ratio

    df = _load_klines_df(symbol, interval, limit=window + 10)
    if df is None or len(df) < window:
        logger.warning(f"Not enough data for entropy: {symbol} {interval}")
        return None

    try:
        closes = df["close"].values[-window:]
        # Log returns
        log_returns = np.diff(np.log(closes))
        log_returns = log_returns[~np.isnan(log_returns)]

        if len(log_returns) < 20:
            return None

        # Discretize into bins using histogram
        counts, _ = np.histogram(log_returns, bins=bins)
        total = counts.sum()
        if total == 0:
            return None

        # Probabilities
        probs = counts / total
        probs = probs[probs > 0]  # Remove zeros for log

        # Shannon entropy
        h = -np.sum(probs * np.log2(probs))
        h_max = math.log2(bins)
        ratio = h / h_max if h_max > 0 else 0.0
        is_tradable = ratio < threshold

        reading = EntropyReading(
            symbol=symbol,
            interval=interval,
            entropy_value=round(float(h), 6),
            max_entropy=round(float(h_max), 6),
            entropy_ratio=round(float(ratio), 6),
            is_tradable=is_tradable,
            window_size=window,
            bins_used=bins,
        )
        return reading

    except Exception as e:
        logger.error(f"Error computing entropy for {symbol}: {e}")
        return None


def store_entropy(reading: EntropyReading) -> None:
    """Store/update entropy reading in DB."""
    supabase = get_supabase()
    data = reading.model_dump()
    data["measured_at"] = datetime.now(timezone.utc).isoformat()

    try:
        supabase.table("entropy_readings").upsert(
            data, on_conflict="symbol,interval"
        ).execute()
    except Exception as e:
        logger.error(f"Failed to store entropy: {e}")


def get_latest_entropy(symbol: str, interval: str = "1h") -> Optional[dict]:
    """Get latest stored entropy reading."""
    supabase = get_supabase()
    resp = (
        supabase.table("entropy_readings")
        .select("*")
        .eq("symbol", symbol)
        .eq("interval", interval)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None
