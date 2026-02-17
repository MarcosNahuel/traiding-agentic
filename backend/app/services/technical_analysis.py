"""Technical analysis engine using pandas-ta.

Reads klines from DB, computes indicators, and stores snapshots.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import pandas as pd
import pandas_ta_classic as ta

from ..db import get_supabase
from ..config import settings
from ..models.quant_models import TechnicalIndicators
from .quant_cache import get_kline_cache, get_indicator_cache

logger = logging.getLogger(__name__)


def _load_klines_df(symbol: str, interval: str, limit: int = 500) -> Optional[pd.DataFrame]:
    """Load klines from DB into a pandas DataFrame. Uses cache."""
    cache_key = f"klines_df:{symbol}:{interval}:{limit}"
    cache = get_kline_cache()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    supabase = get_supabase()
    resp = (
        supabase.table("klines_ohlcv")
        .select("open_time,open,high,low,close,volume,quote_volume")
        .eq("symbol", symbol)
        .eq("interval", interval)
        .order("open_time", desc=True)
        .limit(limit)
        .execute()
    )
    if not resp.data or len(resp.data) < 20:
        return None

    data = resp.data
    data.reverse()  # Oldest first

    df = pd.DataFrame(data)
    df["open_time"] = pd.to_datetime(df["open_time"])
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.set_index("open_time", inplace=True)

    cache.set(cache_key, df, ttl=60)
    return df


def compute_indicators(symbol: str, interval: str = "1h") -> Optional[TechnicalIndicators]:
    """Compute all technical indicators for a symbol/interval."""
    cache_key = f"indicators:{symbol}:{interval}"
    cache = get_indicator_cache()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    df = _load_klines_df(symbol, interval, limit=250)
    if df is None or len(df) < 50:
        logger.warning(f"Not enough klines for {symbol} {interval} (need 50, got {len(df) if df is not None else 0})")
        return None

    try:
        # Trend
        sma_20 = ta.sma(df["close"], length=20)
        sma_50 = ta.sma(df["close"], length=50)
        sma_200 = ta.sma(df["close"], length=200) if len(df) >= 200 else None
        ema_12 = ta.ema(df["close"], length=12)
        ema_26 = ta.ema(df["close"], length=26)
        ema_50 = ta.ema(df["close"], length=50)

        # Momentum
        rsi = ta.rsi(df["close"], length=14)
        macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
        stoch_df = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
        adx_df = ta.adx(df["high"], df["low"], df["close"], length=14)

        # Volatility
        bb_df = ta.bbands(df["close"], length=20, std=2)
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)

        # Volume
        obv = ta.obv(df["close"], df["volume"])
        # VWAP: approximate with cumulative (typical_price * volume) / cumulative volume
        typical = (df["high"] + df["low"] + df["close"]) / 3
        vwap_val = (typical * df["volume"]).cumsum() / df["volume"].cumsum()

        # Extract latest values
        idx = -1

        def _val(series, i=idx):
            if series is None:
                return None
            v = series.iloc[i]
            return float(v) if pd.notna(v) else None

        def _df_val(frame, col, i=idx):
            if frame is None or col not in frame.columns:
                return None
            v = frame[col].iloc[i]
            return float(v) if pd.notna(v) else None

        # BB bandwidth
        bb_upper_v = _df_val(bb_df, "BBU_20_2.0")
        bb_lower_v = _df_val(bb_df, "BBL_20_2.0")
        bb_middle_v = _df_val(bb_df, "BBM_20_2.0")
        bb_bw = None
        if bb_upper_v and bb_lower_v and bb_middle_v and bb_middle_v != 0:
            bb_bw = (bb_upper_v - bb_lower_v) / bb_middle_v

        candle_time = df.index[idx]

        indicators = TechnicalIndicators(
            symbol=symbol,
            interval=interval,
            candle_time=candle_time,
            sma_20=_val(sma_20),
            sma_50=_val(sma_50),
            sma_200=_val(sma_200) if sma_200 is not None else None,
            ema_12=_val(ema_12),
            ema_26=_val(ema_26),
            ema_50=_val(ema_50),
            rsi_14=_val(rsi),
            macd_line=_df_val(macd_df, "MACD_12_26_9"),
            macd_signal=_df_val(macd_df, "MACDs_12_26_9"),
            macd_histogram=_df_val(macd_df, "MACDh_12_26_9"),
            stoch_k=_df_val(stoch_df, "STOCHk_14_3_3"),
            stoch_d=_df_val(stoch_df, "STOCHd_14_3_3"),
            adx_14=_df_val(adx_df, "ADX_14"),
            bb_upper=bb_upper_v,
            bb_middle=bb_middle_v,
            bb_lower=bb_lower_v,
            bb_bandwidth=bb_bw,
            atr_14=_val(atr),
            obv=_val(obv),
            vwap=_val(vwap_val),
        )

        cache.set(cache_key, indicators, ttl=120)
        return indicators

    except Exception as e:
        logger.error(f"Error computing indicators for {symbol} {interval}: {e}")
        return None


def store_indicators(indicators: TechnicalIndicators) -> None:
    """Store the latest indicator snapshot in DB."""
    supabase = get_supabase()
    data = indicators.model_dump(exclude_none=False)
    data["candle_time"] = indicators.candle_time.isoformat()
    data["calculated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        supabase.table("technical_indicators").upsert(
            data, on_conflict="symbol,interval,candle_time"
        ).execute()
    except Exception as e:
        logger.error(f"Failed to store indicators: {e}")


def get_latest_indicators(symbol: str, interval: str = "1h") -> Optional[Dict[str, Any]]:
    """Get latest stored indicators from DB."""
    supabase = get_supabase()
    resp = (
        supabase.table("technical_indicators")
        .select("*")
        .eq("symbol", symbol)
        .eq("interval", interval)
        .order("candle_time", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None
