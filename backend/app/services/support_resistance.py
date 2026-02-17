"""K-Means Support/Resistance level detection.

Clusters high/low price points to identify key support and resistance levels.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List

import numpy as np
from sklearn.cluster import KMeans

from ..db import get_supabase
from ..config import settings
from ..models.quant_models import SRLevel, SRLevelsResult
from .technical_analysis import _load_klines_df

logger = logging.getLogger(__name__)


def compute_sr_levels(symbol: str, interval: str = "1h") -> Optional[SRLevelsResult]:
    """Detect support/resistance levels using K-Means clustering.

    Process:
    1. Extract highs and lows from last N candles
    2. K-Means clustering (K=8)
    3. Classify centroids as support/resistance based on current price
    4. Calculate strength (cluster density) and touch count
    """
    lookback = settings.sr_lookback
    n_clusters = settings.sr_clusters

    df = _load_klines_df(symbol, interval, limit=lookback)
    if df is None or len(df) < 50:
        logger.warning(f"Not enough data for S/R: {symbol} {interval}")
        return None

    try:
        highs = df["high"].values
        lows = df["low"].values
        current_price = float(df["close"].iloc[-1])

        # Combine highs and lows as price points of interest
        price_points = np.concatenate([highs, lows]).reshape(-1, 1)

        # Fit K-Means
        actual_k = min(n_clusters, len(price_points) // 2)
        if actual_k < 2:
            return None

        kmeans = KMeans(n_clusters=actual_k, n_init=10, random_state=42)
        kmeans.fit(price_points)
        centroids = sorted(kmeans.cluster_centers_.flatten())
        labels = kmeans.labels_

        # Build levels
        levels: List[SRLevel] = []
        for i, centroid in enumerate(centroids):
            price_level = float(centroid)
            # Count how many points are in this cluster
            cluster_idx = np.argmin(np.abs(kmeans.cluster_centers_.flatten() - centroid))
            cluster_size = int(np.sum(labels == cluster_idx))
            # Strength based on cluster density relative to total points
            strength = round(cluster_size / len(price_points), 4)

            # Count "touches" - how many candle highs/lows are within 0.5% of the level
            tolerance = price_level * 0.005
            touch_high = int(np.sum(np.abs(highs - price_level) <= tolerance))
            touch_low = int(np.sum(np.abs(lows - price_level) <= tolerance))
            touch_count = touch_high + touch_low

            # Classify as support or resistance
            level_type = "support" if price_level < current_price else "resistance"
            distance_pct = round(((price_level - current_price) / current_price) * 100, 4)

            levels.append(SRLevel(
                level_type=level_type,
                price_level=round(price_level, 8),
                strength=strength,
                touch_count=touch_count,
                distance_pct=distance_pct,
            ))

        result = SRLevelsResult(
            symbol=symbol,
            interval=interval,
            current_price=current_price,
            levels=levels,
        )
        return result

    except Exception as e:
        logger.error(f"Error computing S/R for {symbol}: {e}")
        return None


def store_sr_levels(result: SRLevelsResult) -> None:
    """Store S/R levels in DB (replace old ones for the symbol/interval)."""
    supabase = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    try:
        # Delete old levels for this symbol/interval
        supabase.table("support_resistance_levels").delete().eq(
            "symbol", result.symbol
        ).eq("interval", result.interval).execute()

        # Insert new levels
        rows = []
        for level in result.levels:
            rows.append({
                "symbol": result.symbol,
                "interval": result.interval,
                "level_type": level.level_type,
                "price_level": level.price_level,
                "strength": level.strength,
                "touch_count": level.touch_count,
                "distance_pct": level.distance_pct,
                "calculated_at": now,
            })
        if rows:
            supabase.table("support_resistance_levels").insert(rows).execute()
    except Exception as e:
        logger.error(f"Failed to store S/R levels: {e}")


def get_latest_sr_levels(symbol: str, interval: str = "1h") -> Optional[List[dict]]:
    """Get latest stored S/R levels."""
    supabase = get_supabase()
    resp = (
        supabase.table("support_resistance_levels")
        .select("*")
        .eq("symbol", symbol)
        .eq("interval", interval)
        .order("price_level", desc=False)
        .execute()
    )
    return resp.data if resp.data else None
