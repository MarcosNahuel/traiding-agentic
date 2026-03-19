"""Feature Store — computa las 30 features ML desde klines OHLCV.

Lee velas de la tabla ``klines_ohlcv`` en Supabase, calcula 30 features
agrupadas en 7 categorias (price, momentum, trend, volatility, volume,
cross-asset, calendar) y devuelve un DataFrame listo para entrenamiento
o inferencia.  Opcionalmente persiste en ``ml_features_1h``.

Todas las features usan **exclusivamente** datos disponibles en tiempo *t*
(sin data-leakage).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta_classic as ta

from ...db import get_supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
FEATURE_COLUMNS: list[str] = [
    # Price-based (6)
    "ret_1h",
    "ret_3h",
    "ret_6h",
    "ret_12h",
    "ret_24h",
    "logret_1h",
    # Momentum (5)
    "rsi_2",
    "rsi_14",
    "stoch_k_14",
    "macd_hist",
    "adx_14",
    # Trend (4)
    "sma20_sma50_ratio",
    "ema12_ema26_ratio",
    "ema20_slope",
    "plus_di_minus_di",
    # Volatility (5)
    "atr_pct",
    "bb_width_20_2",
    "bb_percent_b",
    "realized_vol_6",
    "realized_vol_24",
    # Volume (5)
    "volume_zscore_24",
    "quote_volume_zscore",
    "trades_count_zscore",
    "taker_buy_base_ratio",
    "mfi_14",
    # Cross-asset (3)
    "btc_ret_1h",
    "aroon_osc_25",
    "rolling_corr_btc_24",
    # Calendar (2)
    "hour_sin",
    "hour_cos",
]

_REQUIRED_KLINE_COLS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trades_count",
    "taker_buy_base_volume",
]

# Minimo de filas necesarias para calcular todas las features (SMA-50 + 1)
_MIN_ROWS = 60


# ---------------------------------------------------------------------------
# Helpers de lectura
# ---------------------------------------------------------------------------

def _load_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 500,
) -> Optional[pd.DataFrame]:
    """Lee klines de Supabase con paginación automática (PostgREST max 1000/req)."""
    supabase = get_supabase()
    PAGE_SIZE = 1000
    all_rows: list[dict] = []
    remaining = limit
    offset = 0

    while remaining > 0:
        page_limit = min(PAGE_SIZE, remaining)
        resp = (
            supabase.table("klines_ohlcv")
            .select(",".join(_REQUIRED_KLINE_COLS))
            .eq("symbol", symbol)
            .eq("interval", interval)
            .order("open_time", desc=True)
            .limit(page_limit)
            .offset(offset)
            .execute()
        )
        batch = resp.data or []
        all_rows.extend(batch)
        if len(batch) < page_limit:
            break  # No hay más datos
        remaining -= len(batch)
        offset += len(batch)

    if len(all_rows) < _MIN_ROWS:
        logger.warning(
            "Pocas klines para %s %s: %d (min %d)",
            symbol, interval, len(all_rows), _MIN_ROWS,
        )
        return None

    rows = all_rows
    rows.reverse()  # mas vieja primero

    df = pd.DataFrame(rows)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    numeric_cols = [
        "open", "high", "low", "close", "volume",
        "quote_volume", "trades_count", "taker_buy_base_volume",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.set_index("open_time", inplace=True)
    df.sort_index(inplace=True)
    return df


def _rolling_zscore(
    series: pd.Series,
    window: int,
    min_periods: int = 1,
) -> pd.Series:
    """Z-score rolling: (x - mean) / std, con min_periods para evitar NaN excesivos."""
    roll_mean = series.rolling(window, min_periods=min_periods).mean()
    roll_std = series.rolling(window, min_periods=min_periods).std()
    return (series - roll_mean) / roll_std.replace(0, np.nan)


def _safe_mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    length: int = 14,
) -> pd.Series:
    """Money Flow Index manual — evita bug de pandas_ta_classic con pandas >= 2.

    pandas_ta_classic.mfi() falla con pandas 2+/3+ por un conflicto de dtypes
    int64 vs float64 interno. Esta implementacion manual es equivalente.
    """
    typical_price = (high + low + close) / 3.0
    raw_mf = typical_price * volume

    # Diferencia del typical price para determinar up/down
    tp_diff = typical_price.diff()

    pos_mf = pd.Series(0.0, index=close.index)
    neg_mf = pd.Series(0.0, index=close.index)

    pos_mf[tp_diff > 0] = raw_mf[tp_diff > 0]
    neg_mf[tp_diff < 0] = raw_mf[tp_diff < 0]

    pos_sum = pos_mf.rolling(length, min_periods=length).sum()
    neg_sum = neg_mf.rolling(length, min_periods=length).sum()

    mfr = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100.0 - (100.0 / (1.0 + mfr))
    mfi.name = f"MFI_{length}"
    return mfi


# ---------------------------------------------------------------------------
# Feature computation
# ---------------------------------------------------------------------------

def compute_features(
    symbol: str,
    interval: str = "1h",
    limit: int = 500,
    btc_close: Optional[pd.Series] = None,
) -> Optional[pd.DataFrame]:
    """Computa las 30 ML features para *symbol* a partir de klines OHLCV.

    Parameters
    ----------
    symbol : str
        Par de trading (e.g. ``ETHUSDT``).
    interval : str
        Intervalo de velas. Default ``1h``.
    limit : int
        Cantidad de velas a leer (debe ser >= 60).
    btc_close : pd.Series, optional
        Serie de cierre de BTC alineada por ``open_time`` (DatetimeIndex UTC).
        Si ``symbol`` ya es ``BTCUSDT`` o no se provee, las features
        cross-asset BTC se rellenan con 0 / NaN.

    Returns
    -------
    pd.DataFrame | None
        DataFrame con columnas ``[symbol, open_time] + FEATURE_COLUMNS``.
        Las primeras ~50 filas tendran NaN por el lookback de indicadores.
        Retorna ``None`` si no hay suficientes klines.
    """
    df = _load_klines(symbol, interval, limit)
    if df is None:
        return None

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    features = pd.DataFrame(index=df.index)

    # ------------------------------------------------------------------
    # 1. Price-based (6)
    # ------------------------------------------------------------------
    features["ret_1h"] = close.pct_change(1)
    features["ret_3h"] = close.pct_change(3)
    features["ret_6h"] = close.pct_change(6)
    features["ret_12h"] = close.pct_change(12)
    features["ret_24h"] = close.pct_change(24)
    features["logret_1h"] = np.log(close / close.shift(1))

    # ------------------------------------------------------------------
    # 2. Momentum (5)
    # ------------------------------------------------------------------
    features["rsi_2"] = ta.rsi(close, length=2)
    features["rsi_14"] = ta.rsi(close, length=14)

    stoch_df = ta.stoch(high, low, close, k=14, d=3, smooth_k=3)
    features["stoch_k_14"] = stoch_df["STOCHk_14_3_3"]

    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    features["macd_hist"] = macd_df["MACDh_12_26_9"]

    adx_df = ta.adx(high, low, close, length=14)
    features["adx_14"] = adx_df["ADX_14"]

    # ------------------------------------------------------------------
    # 3. Trend (4)
    # ------------------------------------------------------------------
    sma_20 = ta.sma(close, length=20)
    sma_50 = ta.sma(close, length=50)
    ema_12 = ta.ema(close, length=12)
    ema_26 = ta.ema(close, length=26)
    ema_20 = ta.ema(close, length=20)

    features["sma20_sma50_ratio"] = sma_20 / sma_50 - 1
    features["ema12_ema26_ratio"] = ema_12 / ema_26 - 1
    features["ema20_slope"] = ema_20.diff()

    # +DI - -DI (del mismo ADX DataFrame)
    features["plus_di_minus_di"] = adx_df["DMP_14"] - adx_df["DMN_14"]

    # ------------------------------------------------------------------
    # 4. Volatility (5)
    # ------------------------------------------------------------------
    atr_14 = ta.atr(high, low, close, length=14)
    features["atr_pct"] = atr_14 / close

    bb_df = ta.bbands(close, length=20, std=2)
    features["bb_width_20_2"] = bb_df["BBB_20_2.0"]  # bandwidth = (upper-lower)/middle * 100
    features["bb_percent_b"] = bb_df["BBP_20_2.0"]   # %B = (close-lower)/(upper-lower)

    logret = features["logret_1h"]
    features["realized_vol_6"] = logret.rolling(6, min_periods=3).std()
    features["realized_vol_24"] = logret.rolling(24, min_periods=6).std()

    # ------------------------------------------------------------------
    # 5. Volume (5)
    # ------------------------------------------------------------------
    features["volume_zscore_24"] = _rolling_zscore(volume, window=24, min_periods=6)
    features["quote_volume_zscore"] = _rolling_zscore(
        df["quote_volume"], window=24, min_periods=6,
    )
    features["trades_count_zscore"] = _rolling_zscore(
        df["trades_count"], window=24, min_periods=6,
    )

    # Ratio taker buy / volume total (0 = sin presion compradora, 1 = todo taker buy)
    features["taker_buy_base_ratio"] = (
        df["taker_buy_base_volume"] / volume.replace(0, np.nan)
    )

    features["mfi_14"] = _safe_mfi(high, low, close, volume, length=14)

    # ------------------------------------------------------------------
    # 6. Cross-asset (3)
    # ------------------------------------------------------------------
    _compute_cross_asset(features, high, low, close, symbol, btc_close)

    # ------------------------------------------------------------------
    # 7. Calendar (2)
    # ------------------------------------------------------------------
    hour = df.index.hour
    features["hour_sin"] = np.sin(2 * math.pi * hour / 24)
    features["hour_cos"] = np.cos(2 * math.pi * hour / 24)

    # ------------------------------------------------------------------
    # Resultado final
    # ------------------------------------------------------------------
    features.reset_index(inplace=True)
    features.rename(columns={"open_time": "open_time"}, inplace=True)
    features.insert(0, "symbol", symbol)

    # Asegurar que tenemos exactamente las columnas esperadas
    for col in FEATURE_COLUMNS:
        if col not in features.columns:
            features[col] = np.nan

    return features[["symbol", "open_time"] + FEATURE_COLUMNS]


def _compute_cross_asset(
    features: pd.DataFrame,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    symbol: str,
    btc_close: Optional[pd.Series],
) -> None:
    """Calcula features cross-asset (BTC correlation, Aroon)."""
    # btc_ret_1h
    if symbol.upper() == "BTCUSDT" or btc_close is None:
        # Para BTC o sin datos de referencia, usar su propio retorno / llenar con 0
        if symbol.upper() == "BTCUSDT":
            features["btc_ret_1h"] = close.pct_change(1)
        else:
            features["btc_ret_1h"] = 0.0
        features["rolling_corr_btc_24"] = np.nan
    else:
        # Alinear por index
        btc_aligned = btc_close.reindex(close.index)
        btc_ret = btc_aligned.pct_change(1)
        features["btc_ret_1h"] = btc_ret

        # Correlacion rolling 24 barras entre retorno del asset y retorno BTC
        asset_ret = close.pct_change(1)
        features["rolling_corr_btc_24"] = asset_ret.rolling(
            24, min_periods=12,
        ).corr(btc_ret)

    # Aroon Oscillator
    aroon_df = ta.aroon(high, low, length=25)
    features["aroon_osc_25"] = aroon_df["AROONOSC_25"]


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def persist_features(features_df: pd.DataFrame) -> int:
    """Persiste el DataFrame de features en la tabla ``ml_features_1h``.

    Usa upsert con conflicto en ``(symbol, open_time)`` para ser idempotente.

    Parameters
    ----------
    features_df : pd.DataFrame
        Output de :func:`compute_features`.

    Returns
    -------
    int
        Cantidad de filas insertadas/actualizadas.
    """
    if features_df is None or features_df.empty:
        return 0

    # Descartar filas con NaN en features criticas (primeras filas de lookback)
    df_clean = features_df.dropna(subset=FEATURE_COLUMNS, how="any").copy()
    if df_clean.empty:
        logger.warning("Ningun registro sin NaN para persistir.")
        return 0

    # Convertir timestamps a ISO 8601 para Supabase
    df_clean["open_time"] = df_clean["open_time"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    # Reemplazar NaN/inf por None para JSON
    df_clean = df_clean.replace([np.inf, -np.inf], np.nan)
    records = df_clean.where(df_clean.notna(), None).to_dict(orient="records")

    supabase = get_supabase()
    inserted = 0
    batch_size = 500

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            resp = (
                supabase.table("ml_features_1h")
                .upsert(batch, on_conflict="symbol,open_time")
                .execute()
            )
            inserted += len(resp.data) if resp.data else 0
        except Exception as e:
            logger.error("Error persistiendo features batch %d: %s", i, e)

    logger.info(
        "Persistidas %d filas de features para %s",
        inserted,
        df_clean["symbol"].iloc[0] if not df_clean.empty else "?",
    )
    return inserted


# ---------------------------------------------------------------------------
# Pipeline combinado (multi-symbol)
# ---------------------------------------------------------------------------

def compute_all_features(
    symbols: list[str],
    interval: str = "1h",
    limit: int = 500,
    persist: bool = False,
) -> dict[str, pd.DataFrame]:
    """Computa features para multiples symbols, compartiendo BTC close.

    Parameters
    ----------
    symbols : list[str]
        Lista de pares (e.g. ``["BTCUSDT", "ETHUSDT", ...]``).
    interval : str
        Intervalo de velas.
    limit : int
        Cantidad de velas por symbol.
    persist : bool
        Si ``True``, persiste cada DataFrame en ``ml_features_1h``.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping ``symbol -> features DataFrame``.
    """
    results: dict[str, pd.DataFrame] = {}

    # Cargar BTC close una sola vez para cross-asset features
    btc_close: Optional[pd.Series] = None
    if "BTCUSDT" in [s.upper() for s in symbols]:
        btc_df = _load_klines("BTCUSDT", interval, limit)
        if btc_df is not None:
            btc_close = btc_df["close"]

    for sym in symbols:
        try:
            feat_df = compute_features(
                symbol=sym,
                interval=interval,
                limit=limit,
                btc_close=btc_close,
            )
            if feat_df is not None:
                results[sym] = feat_df
                if persist:
                    persist_features(feat_df)
            else:
                logger.warning("No se pudieron computar features para %s", sym)
        except Exception as e:
            logger.error("Error computando features para %s: %s", sym, e)

    logger.info(
        "Feature store: %d/%d symbols procesados", len(results), len(symbols),
    )
    return results
