"""ML Trainer — Walk-forward LightGBM pipeline para prediccion de retornos.

Pipeline completo:
1. Construye dataset multi-symbol desde feature_store
2. Genera target: logret_next = log(close[t+1] / close[t])
3. Walk-forward expanding window (min 180 dias train, 14 dias test)
4. Entrena LightGBM regression con early stopping
5. Evalua out-of-sample: Sharpe, hit rate, MAE
6. Persiste modelo (joblib) y metadata
7. Genera senales BUY/SELL a partir de predicciones

Uso:
    import asyncio
    from app.services.ml.trainer import run_full_pipeline
    result = asyncio.run(run_full_pipeline())
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from .feature_store import compute_features, FEATURE_COLUMNS
from .data_ingest import ML_SYMBOLS
from ...db import get_supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Directorio para persistir modelos entrenados
MODEL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models"

# Target: log-return de la siguiente barra (estrictamente futuro)
TARGET_COL = "logret_next"

# Hyperparametros LightGBM (del research report)
DEFAULT_LGB_PARAMS: dict[str, Any] = {
    "objective": "regression",
    "metric": "mae",
    "boosting_type": "gbdt",
    "learning_rate": 0.03,
    "num_leaves": 31,
    "max_depth": 6,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "feature_fraction": 0.7,
    "reg_alpha": 1.0,
    "reg_lambda": 5.0,
    "n_estimators": 500,
    "verbose": -1,
}

# Walk-forward defaults
DEFAULT_TRAIN_DAYS = 180
DEFAULT_TEST_DAYS = 14

# Umbrales para senales (en log-return predicho)
# AGGRESSIVE TESTING: threshold bajo para generar más señales
# Producción sería ~0.001, testing usamos 0.0001
SIGNAL_THRESHOLD = 0.0001

# Cantidad de velas por dia (1h interval)
BARS_PER_DAY = 24


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------

async def build_dataset(
    symbols: list[str] | None = None,
    interval: str = "1h",
    limit: int = 5000,
) -> pd.DataFrame:
    """Construye dataset de entrenamiento desde feature_store para todos los symbols.

    Para cada symbol:
    1. Computa las 30 features via compute_features()
    2. Agrega columna close (necesaria para calcular target)
    3. Calcula target: logret_next = log(close[t+1] / close[t])
    4. Concatena todos los symbols

    Parameters
    ----------
    symbols : list[str] | None
        Lista de pares. Default: ML_SYMBOLS.
    interval : str
        Intervalo de velas.
    limit : int
        Cantidad maxima de velas por symbol a leer.

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas: symbol, open_time, FEATURE_COLUMNS, close, logret_next.
        Ordenado por open_time. Filas con NaN en features o target ya eliminadas.
    """
    target_symbols = symbols or ML_SYMBOLS
    logger.info(
        "Construyendo dataset ML para %d symbols: %s",
        len(target_symbols),
        ", ".join(target_symbols),
    )

    # Cargar BTC close para cross-asset features
    btc_close: Optional[pd.Series] = None
    if "BTCUSDT" in [s.upper() for s in target_symbols]:
        from .feature_store import _load_klines
        btc_df = _load_klines("BTCUSDT", interval, limit)
        if btc_df is not None:
            btc_close = btc_df["close"]

    all_frames: list[pd.DataFrame] = []

    for sym in target_symbols:
        try:
            feat_df = compute_features(
                symbol=sym,
                interval=interval,
                limit=limit,
                btc_close=btc_close,
            )
            if feat_df is None:
                logger.warning("Sin features para %s, skipping", sym)
                continue

            # Necesitamos close para calcular el target.
            # compute_features no incluye close, asi que lo leemos aparte.
            from .feature_store import _load_klines
            klines_df = _load_klines(sym, interval, limit)
            if klines_df is None:
                logger.warning("Sin klines para %s, skipping", sym)
                continue

            # Alinear close con features por open_time
            close_series = klines_df["close"].reset_index()
            close_series.columns = ["open_time", "close"]

            feat_df = feat_df.merge(close_series, on="open_time", how="left")

            # Target: log(close[t+1] / close[t]) — estrictamente futuro
            # Agrupado por symbol para no contaminar entre symbols
            feat_df[TARGET_COL] = np.log(
                feat_df["close"].shift(-1) / feat_df["close"]
            )

            all_frames.append(feat_df)
            logger.info(
                "Dataset %s: %d filas con features", sym, len(feat_df),
            )

        except Exception as e:
            logger.error("Error construyendo dataset para %s: %s", sym, e)

    if not all_frames:
        logger.error("No se pudo construir dataset para ningun symbol")
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True)
    combined.sort_values("open_time", inplace=True)

    # Eliminar filas con NaN en features o target
    initial_len = len(combined)
    combined.dropna(subset=FEATURE_COLUMNS + [TARGET_COL], inplace=True)
    combined.reset_index(drop=True, inplace=True)
    dropped = initial_len - len(combined)

    logger.info(
        "Dataset completo: %d filas (%d eliminadas por NaN), %d symbols, "
        "rango %s → %s",
        len(combined),
        dropped,
        combined["symbol"].nunique(),
        combined["open_time"].min(),
        combined["open_time"].max(),
    )

    return combined


# ---------------------------------------------------------------------------
# LightGBM training (single fold)
# ---------------------------------------------------------------------------

def train_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    params: dict[str, Any] | None = None,
) -> Any:
    """Entrena un LightGBM Booster con early stopping.

    Parameters
    ----------
    X_train, y_train : train data
    X_val, y_val : validation data para early stopping
    params : dict, optional
        Hyperparametros LightGBM. Default: DEFAULT_LGB_PARAMS.

    Returns
    -------
    lgb.Booster
        Modelo entrenado.
    """
    try:
        import lightgbm as lgb
    except ImportError:
        raise ImportError(
            "lightgbm no esta instalado. Ejecutar: pip install lightgbm"
        )

    lgb_params = {**(params or DEFAULT_LGB_PARAMS)}
    n_estimators = lgb_params.pop("n_estimators", 500)

    train_set = lgb.Dataset(X_train, label=y_train)
    val_set = lgb.Dataset(X_val, label=y_val, reference=train_set)

    callbacks = [
        lgb.early_stopping(stopping_rounds=50),
        lgb.log_evaluation(period=100),
    ]

    model = lgb.train(
        lgb_params,
        train_set,
        num_boost_round=n_estimators,
        valid_sets=[train_set, val_set],
        valid_names=["train", "val"],
        callbacks=callbacks,
    )

    logger.info(
        "LightGBM entrenado: %d iteraciones (best: %d)",
        model.current_iteration(),
        model.best_iteration,
    )

    return model


# ---------------------------------------------------------------------------
# Metricas por fold
# ---------------------------------------------------------------------------

def _compute_fold_metrics(
    y_true: pd.Series,
    y_pred: np.ndarray,
) -> dict[str, float]:
    """Calcula metricas out-of-sample para un fold.

    Returns
    -------
    dict con:
        sharpe : Sharpe ratio anualizado (asumiendo 1h bars, 24*365 = 8760 bars/yr)
        hit_rate : Fraccion de predicciones con signo correcto
        mean_abs_pred : Media de |prediccion| (magnitud promedio de la senal)
        mae : Mean Absolute Error
        mse : Mean Squared Error
        n_samples : Cantidad de observaciones
    """
    residuals = y_true.values - y_pred

    # Hit rate: fraccion donde el signo de prediccion == signo de retorno real
    correct_sign = np.sign(y_pred) == np.sign(y_true.values)
    hit_rate = float(np.mean(correct_sign))

    # Sharpe de la estrategia "go long si pred > 0, short si pred < 0"
    # PnL por barra = sign(pred) * retorno_real
    strategy_returns = np.sign(y_pred) * y_true.values
    mean_ret = np.mean(strategy_returns)
    std_ret = np.std(strategy_returns, ddof=1) if len(strategy_returns) > 1 else 1e-9
    bars_per_year = BARS_PER_DAY * 365
    sharpe = (mean_ret / max(std_ret, 1e-9)) * np.sqrt(bars_per_year)

    return {
        "sharpe": round(float(sharpe), 4),
        "hit_rate": round(hit_rate, 4),
        "mean_abs_pred": round(float(np.mean(np.abs(y_pred))), 8),
        "mae": round(float(np.mean(np.abs(residuals))), 8),
        "mse": round(float(np.mean(residuals ** 2)), 12),
        "n_samples": len(y_true),
    }


# ---------------------------------------------------------------------------
# Walk-forward training
# ---------------------------------------------------------------------------

def walk_forward_train(
    df: pd.DataFrame,
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Walk-forward expanding window training y evaluacion.

    Protocolo:
    - Fold 0: train en [0, train_days), test en [train_days, train_days + test_days)
    - Fold 1: train en [0, train_days + test_days), test siguiente bloque
    - ... expanding window hasta agotar datos

    Parameters
    ----------
    df : pd.DataFrame
        Dataset con FEATURE_COLUMNS + TARGET_COL. Debe estar ordenado por open_time.
    train_days : int
        Minimo de dias de training (expanding window).
    test_days : int
        Dias por fold de test.
    params : dict, optional
        LightGBM hyperparametros.

    Returns
    -------
    dict con:
        model : ultimo modelo entrenado (lgb.Booster)
        fold_metrics : list[dict] metricas por fold
        oos_predictions : pd.DataFrame con predicciones out-of-sample
        aggregate_metrics : dict con metricas agregadas sobre todos los folds
        n_folds : int
    """
    if df.empty:
        raise ValueError("Dataset vacio, no se puede entrenar")

    # Asegurar orden temporal
    df = df.sort_values("open_time").reset_index(drop=True)

    # Convertir open_time a datetime si no lo es
    if not pd.api.types.is_datetime64_any_dtype(df["open_time"]):
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)

    min_date = df["open_time"].min()
    max_date = df["open_time"].max()
    total_days = (max_date - min_date).total_seconds() / 86400

    logger.info(
        "Walk-forward: %.0f dias de datos, min_train=%d, test_block=%d",
        total_days, train_days, test_days,
    )

    if total_days < train_days + test_days:
        raise ValueError(
            f"Datos insuficientes: {total_days:.0f} dias disponibles, "
            f"necesarios {train_days + test_days} dias minimo"
        )

    # Calcular boundaries de folds en base a dias desde min_date
    train_end_offset = pd.Timedelta(days=train_days)
    test_block = pd.Timedelta(days=test_days)

    fold_metrics: list[dict[str, Any]] = []
    oos_predictions_list: list[pd.DataFrame] = []
    last_model = None
    fold_idx = 0

    current_test_start = min_date + train_end_offset

    while current_test_start + test_block <= max_date + pd.Timedelta(hours=1):
        current_test_end = current_test_start + test_block

        # Train: todo hasta current_test_start (expanding window)
        train_mask = df["open_time"] < current_test_start
        test_mask = (
            (df["open_time"] >= current_test_start)
            & (df["open_time"] < current_test_end)
        )

        train_df = df[train_mask]
        test_df = df[test_mask]

        if len(train_df) < BARS_PER_DAY * 30 or len(test_df) < BARS_PER_DAY:
            logger.warning(
                "Fold %d: datos insuficientes (train=%d, test=%d), saltando",
                fold_idx, len(train_df), len(test_df),
            )
            current_test_start += test_block
            continue

        X_train = train_df[FEATURE_COLUMNS]
        y_train = train_df[TARGET_COL]
        X_test = test_df[FEATURE_COLUMNS]
        y_test = test_df[TARGET_COL]

        # Usar ultimo 10% del train como validation para early stopping
        val_split = int(len(X_train) * 0.9)
        X_tr, X_val = X_train.iloc[:val_split], X_train.iloc[val_split:]
        y_tr, y_val = y_train.iloc[:val_split], y_train.iloc[val_split:]

        logger.info(
            "Fold %d: train=%d (val=%d), test=%d, periodo test: %s → %s",
            fold_idx,
            len(X_tr),
            len(X_val),
            len(X_test),
            current_test_start.strftime("%Y-%m-%d"),
            current_test_end.strftime("%Y-%m-%d"),
        )

        try:
            model = train_lightgbm(X_tr, y_tr, X_val, y_val, params)
            last_model = model

            # Prediccion out-of-sample
            y_pred = model.predict(X_test)
            metrics = _compute_fold_metrics(y_test, y_pred)
            metrics["fold"] = fold_idx
            metrics["train_size"] = len(X_tr)
            metrics["test_start"] = current_test_start.isoformat()
            metrics["test_end"] = current_test_end.isoformat()
            fold_metrics.append(metrics)

            # Guardar predicciones OOS
            oos_df = test_df[["symbol", "open_time"]].copy()
            oos_df["y_true"] = y_test.values
            oos_df["y_pred"] = y_pred
            oos_df["fold"] = fold_idx
            oos_predictions_list.append(oos_df)

            logger.info(
                "Fold %d resultado: Sharpe=%.3f, hit_rate=%.3f, MAE=%.6f",
                fold_idx,
                metrics["sharpe"],
                metrics["hit_rate"],
                metrics["mae"],
            )

        except Exception as e:
            logger.error("Error en fold %d: %s", fold_idx, e)
            fold_metrics.append({
                "fold": fold_idx,
                "error": str(e),
                "test_start": current_test_start.isoformat(),
                "test_end": current_test_end.isoformat(),
            })

        fold_idx += 1
        current_test_start += test_block

    # Agregar predicciones OOS
    if oos_predictions_list:
        oos_predictions = pd.concat(oos_predictions_list, ignore_index=True)
    else:
        oos_predictions = pd.DataFrame()

    # Metricas agregadas
    valid_folds = [m for m in fold_metrics if "error" not in m]
    if valid_folds:
        aggregate_metrics = {
            "mean_sharpe": round(
                float(np.mean([m["sharpe"] for m in valid_folds])), 4,
            ),
            "mean_hit_rate": round(
                float(np.mean([m["hit_rate"] for m in valid_folds])), 4,
            ),
            "mean_mae": round(
                float(np.mean([m["mae"] for m in valid_folds])), 8,
            ),
            "total_oos_samples": sum(m["n_samples"] for m in valid_folds),
            "n_valid_folds": len(valid_folds),
            "n_failed_folds": len(fold_metrics) - len(valid_folds),
        }
    else:
        aggregate_metrics = {
            "mean_sharpe": 0.0,
            "mean_hit_rate": 0.0,
            "mean_mae": 0.0,
            "total_oos_samples": 0,
            "n_valid_folds": 0,
            "n_failed_folds": len(fold_metrics),
        }

    logger.info(
        "Walk-forward completo: %d folds, Sharpe medio=%.3f, hit_rate medio=%.3f",
        len(fold_metrics),
        aggregate_metrics["mean_sharpe"],
        aggregate_metrics["mean_hit_rate"],
    )

    return {
        "model": last_model,
        "fold_metrics": fold_metrics,
        "oos_predictions": oos_predictions,
        "aggregate_metrics": aggregate_metrics,
        "n_folds": len(fold_metrics),
    }


# ---------------------------------------------------------------------------
# Model persistence
# ---------------------------------------------------------------------------

def _ensure_model_dir() -> Path:
    """Crea el directorio de modelos si no existe."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_DIR


def save_model(
    model: Any,
    metadata: dict[str, Any],
    model_name: str = "lgb_logret",
) -> Path:
    """Persiste modelo y metadata en disco.

    Guarda dos archivos:
    - {model_name}_{timestamp}.pkl — modelo serializado
    - {model_name}_{timestamp}_meta.json — metadata (features, metricas, etc.)
    - Symlink/copia: {model_name}_latest.pkl apuntando al ultimo modelo

    Parameters
    ----------
    model : lgb.Booster
        Modelo LightGBM entrenado.
    metadata : dict
        Informacion del training run (features, metricas, fechas, etc.).
    model_name : str
        Prefijo del nombre de archivo.

    Returns
    -------
    Path
        Path al archivo del modelo guardado.
    """
    model_dir = _ensure_model_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Modelo
    model_path = model_dir / f"{model_name}_{timestamp}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Metadata
    meta_path = model_dir / f"{model_name}_{timestamp}_meta.json"
    # Asegurar que metadata es serializable
    serializable_meta = _make_serializable(metadata)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(serializable_meta, f, indent=2, ensure_ascii=False)

    # "Latest" — copiar como referencia rapida
    latest_model_path = model_dir / f"{model_name}_latest.pkl"
    latest_meta_path = model_dir / f"{model_name}_latest_meta.json"

    with open(latest_model_path, "wb") as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(latest_meta_path, "w", encoding="utf-8") as f:
        json.dump(serializable_meta, f, indent=2, ensure_ascii=False)

    logger.info(
        "Modelo guardado: %s (%.1f KB) + metadata",
        model_path.name,
        model_path.stat().st_size / 1024,
    )

    return model_path


def load_model(
    model_name: str = "lgb_logret",
) -> tuple[Any, dict[str, Any]]:
    """Carga el ultimo modelo y su metadata desde disco.

    Parameters
    ----------
    model_name : str
        Prefijo del modelo a cargar.

    Returns
    -------
    tuple[lgb.Booster, dict]
        Modelo y metadata.

    Raises
    ------
    FileNotFoundError
        Si no se encuentra el modelo.
    """
    model_dir = _ensure_model_dir()

    model_path = model_dir / f"{model_name}_latest.pkl"
    meta_path = model_dir / f"{model_name}_latest_meta.json"

    if not model_path.exists():
        raise FileNotFoundError(
            f"No se encontro modelo en {model_path}. "
            "Ejecutar run_full_pipeline() primero."
        )

    with open(model_path, "rb") as f:
        model = pickle.load(f)  # noqa: S301

    metadata: dict[str, Any] = {}
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    logger.info("Modelo cargado: %s", model_path.name)
    return model, metadata


def _make_serializable(obj: Any) -> Any:
    """Convierte recursivamente numpy/pandas types a tipos nativos de Python."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return str(obj)
    return obj


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------

def generate_ml_signals(
    model: Any,
    latest_features: pd.DataFrame,
    threshold: float = SIGNAL_THRESHOLD,
) -> list[dict[str, Any]]:
    """Convierte predicciones del modelo en senales BUY/SELL accionables.

    Parameters
    ----------
    model : lgb.Booster
        Modelo LightGBM entrenado.
    latest_features : pd.DataFrame
        Features mas recientes (output de compute_features).
        Debe contener columnas: symbol, open_time, FEATURE_COLUMNS.
    threshold : float
        Umbral minimo de prediccion para generar senal.
        Default: 0.001 (~0.1% de log-return predicho).

    Returns
    -------
    list[dict]
        Lista de senales, cada una con:
        - symbol, signal (BUY/SELL), predicted_return, confidence, timestamp
    """
    if latest_features is None or latest_features.empty:
        logger.warning("Sin features para generar senales ML")
        return []

    # Filtrar filas con NaN en features
    clean = latest_features.dropna(subset=FEATURE_COLUMNS)
    if clean.empty:
        logger.warning("Todas las filas tienen NaN, sin senales")
        return []

    X = clean[FEATURE_COLUMNS]
    predictions = model.predict(X)

    signals: list[dict[str, Any]] = []

    for i, (_, row) in enumerate(clean.iterrows()):
        pred = float(predictions[i])
        abs_pred = abs(pred)

        if abs_pred < threshold:
            continue

        signal_type = "BUY" if pred > 0 else "SELL"

        # Confidence: mapeo simple de magnitud de prediccion
        # Cuanto mas lejos del threshold, mas confianza (capped a 1.0)
        confidence = min(abs_pred / (threshold * 5), 1.0)

        signals.append({
            "symbol": row["symbol"],
            "signal": signal_type,
            "predicted_return": round(pred, 8),
            "confidence": round(confidence, 4),
            "threshold_used": threshold,
            "timestamp": row["open_time"].isoformat()
            if hasattr(row["open_time"], "isoformat")
            else str(row["open_time"]),
            "source": "ml_lgb_logret",
        })

    logger.info(
        "Senales ML generadas: %d/%d (threshold=%.4f)",
        len(signals),
        len(clean),
        threshold,
    )

    return signals


# ---------------------------------------------------------------------------
# Supabase persistence
# ---------------------------------------------------------------------------

def _persist_training_run(
    run_metadata: dict[str, Any],
) -> Optional[str]:
    """Persiste metadata del training run en tabla ml_training_runs.

    Returns
    -------
    str | None
        ID del registro insertado, o None si falla.
    """
    try:
        supabase = get_supabase()
        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_name": run_metadata.get("model_name", "lgb_logret"),
            "n_folds": run_metadata.get("n_folds", 0),
            "mean_sharpe": run_metadata.get("aggregate_metrics", {}).get(
                "mean_sharpe", 0.0
            ),
            "mean_hit_rate": run_metadata.get("aggregate_metrics", {}).get(
                "mean_hit_rate", 0.0
            ),
            "mean_mae": run_metadata.get("aggregate_metrics", {}).get(
                "mean_mae", 0.0
            ),
            "total_oos_samples": run_metadata.get("aggregate_metrics", {}).get(
                "total_oos_samples", 0
            ),
            "symbols": run_metadata.get("symbols", []),
            "train_days": run_metadata.get("train_days", DEFAULT_TRAIN_DAYS),
            "test_days": run_metadata.get("test_days", DEFAULT_TEST_DAYS),
            "hyperparams": _make_serializable(
                run_metadata.get("hyperparams", DEFAULT_LGB_PARAMS)
            ),
            "fold_metrics": _make_serializable(
                run_metadata.get("fold_metrics", [])
            ),
            "feature_columns": FEATURE_COLUMNS,
            "elapsed_seconds": run_metadata.get("elapsed_seconds", 0.0),
        }

        resp = (
            supabase.table("ml_training_runs")
            .insert(record)
            .execute()
        )
        if resp.data:
            run_id = resp.data[0].get("id", str(resp.data[0]))
            logger.info("Training run persistido en Supabase: %s", run_id)
            return str(run_id)

    except Exception as e:
        logger.warning(
            "No se pudo persistir training run en Supabase "
            "(tabla ml_training_runs puede no existir): %s",
            e,
        )

    return None


def _persist_oos_predictions(
    oos_df: pd.DataFrame,
    run_id: Optional[str] = None,
) -> int:
    """Persiste predicciones out-of-sample en tabla ml_predictions.

    Returns
    -------
    int
        Cantidad de filas insertadas.
    """
    if oos_df.empty:
        return 0

    try:
        supabase = get_supabase()

        df_clean = oos_df.copy()
        df_clean["open_time"] = pd.to_datetime(
            df_clean["open_time"], utc=True
        ).dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        # Reemplazar NaN/inf
        df_clean = df_clean.replace([np.inf, -np.inf], np.nan)

        records = []
        for _, row in df_clean.iterrows():
            record = {
                "symbol": row["symbol"],
                "open_time": row["open_time"],
                "y_true": float(row["y_true"]) if pd.notna(row["y_true"]) else None,
                "y_pred": float(row["y_pred"]) if pd.notna(row["y_pred"]) else None,
                "fold": int(row["fold"]),
            }
            if run_id:
                record["run_id"] = run_id
            records.append(record)

        inserted = 0
        batch_size = 500
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            try:
                resp = (
                    supabase.table("ml_predictions")
                    .insert(batch)
                    .execute()
                )
                inserted += len(resp.data) if resp.data else 0
            except Exception as e:
                logger.warning(
                    "Error insertando predicciones batch %d: %s", i, e,
                )

        logger.info("Persistidas %d predicciones OOS en Supabase", inserted)
        return inserted

    except Exception as e:
        logger.warning(
            "No se pudo persistir predicciones OOS "
            "(tabla ml_predictions puede no existir): %s",
            e,
        )
        return 0


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

async def run_full_pipeline(
    symbols: list[str] | None = None,
    interval: str = "1h",
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    params: dict[str, Any] | None = None,
    persist_to_supabase: bool = True,
) -> dict[str, Any]:
    """Pipeline completo: build data -> train -> evaluate -> save model.

    Parameters
    ----------
    symbols : list[str] | None
        Symbols a incluir. Default: ML_SYMBOLS.
    interval : str
        Intervalo de velas.
    train_days : int
        Minimo de dias para training (expanding window).
    test_days : int
        Dias por bloque de test.
    params : dict, optional
        Hyperparametros LightGBM.
    persist_to_supabase : bool
        Si True, persiste run metadata y predicciones en Supabase.

    Returns
    -------
    dict con:
        status : "success" | "error"
        model_path : Path al modelo guardado
        aggregate_metrics : metricas agregadas
        fold_metrics : metricas por fold
        n_folds : cantidad de folds
        elapsed_seconds : duracion total
        run_id : ID del run en Supabase (si persist_to_supabase)
    """
    target_symbols = symbols or ML_SYMBOLS
    start_time = time.time()

    logger.info(
        "=== ML Training Pipeline START === symbols=%s, train=%dd, test=%dd",
        target_symbols,
        train_days,
        test_days,
    )

    result: dict[str, Any] = {
        "status": "error",
        "symbols": target_symbols,
        "train_days": train_days,
        "test_days": test_days,
    }

    try:
        # 1. Build dataset
        logger.info("Paso 1/4: Construyendo dataset...")
        df = await build_dataset(
            symbols=target_symbols,
            interval=interval,
        )
        if df.empty:
            result["error"] = "Dataset vacio — verificar datos en Supabase"
            logger.error(result["error"])
            return result

        result["dataset_rows"] = len(df)
        result["dataset_symbols"] = int(df["symbol"].nunique())
        logger.info(
            "Dataset: %d filas, %d symbols",
            len(df), df["symbol"].nunique(),
        )

        # 2. Walk-forward training
        logger.info("Paso 2/4: Walk-forward training...")
        wf_result = walk_forward_train(
            df,
            train_days=train_days,
            test_days=test_days,
            params=params,
        )

        model = wf_result["model"]
        if model is None:
            result["error"] = "Ningun fold produjo un modelo valido"
            logger.error(result["error"])
            return result

        result["n_folds"] = wf_result["n_folds"]
        result["fold_metrics"] = wf_result["fold_metrics"]
        result["aggregate_metrics"] = wf_result["aggregate_metrics"]

        # 3. Save model
        logger.info("Paso 3/4: Guardando modelo...")
        model_metadata = {
            "model_name": "lgb_logret",
            "symbols": target_symbols,
            "interval": interval,
            "train_days": train_days,
            "test_days": test_days,
            "feature_columns": FEATURE_COLUMNS,
            "target": TARGET_COL,
            "hyperparams": params or DEFAULT_LGB_PARAMS,
            "aggregate_metrics": wf_result["aggregate_metrics"],
            "fold_metrics": wf_result["fold_metrics"],
            "n_folds": wf_result["n_folds"],
            "dataset_rows": len(df),
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }
        model_path = save_model(model, model_metadata)
        result["model_path"] = str(model_path)

        # 4. Persist to Supabase
        if persist_to_supabase:
            logger.info("Paso 4/4: Persistiendo resultados en Supabase...")
            elapsed = round(time.time() - start_time, 1)
            model_metadata["elapsed_seconds"] = elapsed

            run_id = _persist_training_run(model_metadata)
            result["run_id"] = run_id

            n_preds = _persist_oos_predictions(
                wf_result["oos_predictions"], run_id,
            )
            result["oos_predictions_persisted"] = n_preds
        else:
            logger.info("Paso 4/4: Skip persistencia Supabase (deshabilitada)")

        result["status"] = "success"

    except ImportError as e:
        result["error"] = str(e)
        logger.error("Dependencia faltante: %s", e)
    except Exception as e:
        result["error"] = str(e)
        logger.error("Error en pipeline ML: %s", e, exc_info=True)

    elapsed = round(time.time() - start_time, 1)
    result["elapsed_seconds"] = elapsed

    logger.info(
        "=== ML Training Pipeline %s === %.1fs, %d folds, Sharpe=%.3f",
        result["status"].upper(),
        elapsed,
        result.get("n_folds", 0),
        result.get("aggregate_metrics", {}).get("mean_sharpe", 0.0),
    )

    return result
