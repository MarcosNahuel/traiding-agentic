"""ML Signal Policy — conecta predicciones ML con el signal generator del bot.

Carga el modelo LightGBM entrenado, computa features en tiempo real,
genera predicciones, y las convierte en señales BUY/SELL que el
signal_generator puede consumir.

Uso desde signal_generator.py:
    from .ml.signal_policy import get_ml_signals
    signals = await get_ml_signals()
    # signals = [{"symbol": "BTCUSDT", "signal": "BUY", "confidence": 0.8, ...}]
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .feature_store import compute_features, FEATURE_COLUMNS
from .trainer import load_model, generate_ml_signals, SIGNAL_THRESHOLD
from .data_ingest import ML_SYMBOLS

logger = logging.getLogger(__name__)

# Cache del modelo en memoria (se carga una vez)
_cached_model: Any = None
_cached_metadata: dict[str, Any] = {}


def _get_model():
    """Carga el modelo LightGBM (lazy load, cached en memoria)."""
    global _cached_model, _cached_metadata
    if _cached_model is not None:
        return _cached_model, _cached_metadata
    try:
        _cached_model, _cached_metadata = load_model()
        logger.info("Modelo ML cargado: %s", _cached_metadata.get("model_file", "?"))
        return _cached_model, _cached_metadata
    except FileNotFoundError:
        logger.warning("No hay modelo ML entrenado — usar run_full_pipeline() primero")
        return None, {}


def reload_model() -> bool:
    """Fuerza recarga del modelo (después de retrain)."""
    global _cached_model, _cached_metadata
    _cached_model = None
    _cached_metadata = {}
    model, meta = _get_model()
    return model is not None


async def get_ml_signals(
    symbols: list[str] | None = None,
    threshold: float = SIGNAL_THRESHOLD,
) -> list[dict[str, Any]]:
    """Genera señales ML para todos los símbolos monitoreados.

    1. Carga modelo (cached)
    2. Computa features más recientes para cada symbol
    3. Genera predicciones
    4. Filtra por threshold y devuelve señales accionables

    Returns:
        Lista de señales: [{symbol, signal, predicted_return, confidence, ...}]
    """
    model, metadata = _get_model()
    if model is None:
        return []

    target_symbols = symbols or ML_SYMBOLS
    all_features = []

    # Cargar BTC close para cross-asset features
    btc_close = None
    if "BTCUSDT" in [s.upper() for s in target_symbols]:
        from .feature_store import _load_klines
        btc_df = _load_klines("BTCUSDT", "1h", 100)
        if btc_df is not None:
            btc_close = btc_df["close"]

    for sym in target_symbols:
        try:
            feat = compute_features(
                symbol=sym,
                interval="1h",
                limit=100,  # Solo necesitamos las últimas ~100 velas para features
                btc_close=btc_close,
            )
            if feat is not None and not feat.empty:
                # Solo la última fila (más reciente, la que queremos predecir)
                last_row = feat.iloc[[-1]]
                all_features.append(last_row)
        except Exception as e:
            logger.error("Error computando features ML para %s: %s", sym, e)

    if not all_features:
        logger.warning("Sin features disponibles para ML signals")
        return []

    import pandas as pd
    latest = pd.concat(all_features, ignore_index=True)

    signals = generate_ml_signals(model, latest, threshold=threshold)

    if signals:
        logger.info(
            "ML signals: %s",
            ", ".join(f"{s['symbol']} {s['signal']} ({s['confidence']:.2f})" for s in signals),
        )

    return signals
