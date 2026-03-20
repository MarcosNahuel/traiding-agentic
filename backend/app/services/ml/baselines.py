"""Baselines lineales y comparative analysis para ML trading.

Implementa Ridge, ElasticNet, y RandomForest como baselines para comparar
con LightGBM. Sigue la recomendación de Kelly & Xiu (2023) Sec 3.3-3.4:
siempre comparar modelos complejos contra baselines lineales.

Uso:
    from app.services.ml.baselines import walk_forward_baselines, generate_comparative_table
    results = walk_forward_baselines(df, feature_cols, "logret_next")
    table = generate_comparative_table(results)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.ensemble import RandomForestRegressor

logger = logging.getLogger(__name__)

# Modelos disponibles
SUPPORTED_MODELS = {"ridge", "elasticnet", "random_forest", "xgboost", "lightgbm"}

BARS_PER_DAY = 24


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Calcula métricas de evaluación OOS."""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    mse = float(np.mean((y_true - y_pred) ** 2))

    # Hit rate: fracción de veces que el signo predicho coincide
    signs_match = np.sign(y_pred) == np.sign(y_true)
    hit_rate = float(np.mean(signs_match)) if len(y_true) > 0 else 0.0

    # Sharpe del strategy return: pred_sign * actual_return
    strategy_returns = np.sign(y_pred) * y_true
    mean_ret = np.mean(strategy_returns)
    std_ret = np.std(strategy_returns)
    sharpe = float(mean_ret / std_ret * np.sqrt(BARS_PER_DAY * 365)) if std_ret > 0 else 0.0

    return {
        "mae": round(mae, 8),
        "mse": round(mse, 10),
        "hit_rate": round(hit_rate, 4),
        "sharpe": round(sharpe, 4),
        "n_samples": len(y_true),
    }


def train_baseline(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_type: str = "ridge",
) -> dict[str, Any]:
    """Entrena un baseline y evalúa en test set.

    Parameters
    ----------
    model_type : str
        "ridge", "elasticnet", o "random_forest"

    Returns
    -------
    dict con keys: model, metrics, predictions
    """
    if model_type not in SUPPORTED_MODELS:
        raise ValueError(
            f"model_type '{model_type}' no soportado. "
            f"Opciones: {SUPPORTED_MODELS}"
        )

    if model_type == "ridge":
        model = Ridge(alpha=1.0)
    elif model_type == "elasticnet":
        model = ElasticNet(alpha=0.001, l1_ratio=0.5, max_iter=5000)
    elif model_type == "random_forest":
        model = RandomForestRegressor(
            n_estimators=100, max_depth=6, min_samples_leaf=20,
            random_state=42, n_jobs=-1,
        )
    elif model_type == "xgboost":
        import xgboost as xgb
        model = xgb.XGBRegressor(
            objective="reg:squarederror", n_estimators=300,
            max_depth=6, learning_rate=0.03, subsample=0.8,
            colsample_bytree=0.7, reg_alpha=1.0, reg_lambda=5.0,
            min_child_weight=10, random_state=42, verbosity=0,
        )
    elif model_type == "lightgbm":
        import lightgbm as lgb
        model = lgb.LGBMRegressor(
            objective="regression", n_estimators=300,
            max_depth=6, learning_rate=0.03, num_leaves=31,
            subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
            reg_alpha=1.0, reg_lambda=5.0, min_child_samples=50,
            verbose=-1,
        )

    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    metrics = _compute_metrics(y_test.values, predictions)
    metrics["model_type"] = model_type

    return {
        "model": model,
        "metrics": metrics,
        "predictions": predictions,
    }


def walk_forward_baselines(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "logret_next",
    train_days: int = 15,
    test_days: int = 5,
) -> dict[str, dict[str, Any]]:
    """Walk-forward evaluation de todos los baselines.

    Expanding window: train en [0..t], test en [t..t+test_block],
    avanza test_block, repite.

    Returns
    -------
    dict[model_name -> {mean_sharpe, mean_hit_rate, mean_mae, n_folds, fold_metrics}]
    """
    df = df.sort_values("open_time").reset_index(drop=True)

    train_bars = train_days * BARS_PER_DAY
    test_bars = test_days * BARS_PER_DAY
    total_bars = len(df)

    if total_bars < train_bars + test_bars:
        raise ValueError(
            f"Data insuficiente: {total_bars} bars, necesarios {train_bars + test_bars}"
        )

    model_types = ["ridge", "elasticnet", "random_forest", "xgboost", "lightgbm"]
    all_results: dict[str, list[dict]] = {m: [] for m in model_types}

    fold_start = train_bars
    fold_idx = 0

    while fold_start + test_bars <= total_bars:
        train_df = df.iloc[:fold_start]
        test_df = df.iloc[fold_start : fold_start + test_bars]

        X_train = train_df[feature_cols]
        y_train = train_df[target_col]
        X_test = test_df[feature_cols]
        y_test = test_df[target_col]

        # Eliminar NaN
        train_mask = X_train.notna().all(axis=1) & y_train.notna()
        test_mask = X_test.notna().all(axis=1) & y_test.notna()

        if train_mask.sum() < 50 or test_mask.sum() < 10:
            fold_start += test_bars
            fold_idx += 1
            continue

        X_tr = X_train[train_mask]
        y_tr = y_train[train_mask]
        X_te = X_test[test_mask]
        y_te = y_test[test_mask]

        for mt in model_types:
            try:
                result = train_baseline(X_tr, y_tr, X_te, y_te, model_type=mt)
                result["metrics"]["fold"] = fold_idx
                all_results[mt].append(result["metrics"])
            except Exception as e:
                logger.error("Fold %d, %s error: %s", fold_idx, mt, e)

        fold_start += test_bars
        fold_idx += 1

    # Agregar métricas
    output: dict[str, dict[str, Any]] = {}
    for mt in model_types:
        folds = all_results[mt]
        if not folds:
            output[mt] = {
                "mean_sharpe": 0.0, "mean_hit_rate": 0.0,
                "mean_mae": 0.0, "n_folds": 0, "fold_metrics": [],
            }
            continue

        output[mt] = {
            "mean_sharpe": round(float(np.mean([f["sharpe"] for f in folds])), 4),
            "mean_hit_rate": round(float(np.mean([f["hit_rate"] for f in folds])), 4),
            "mean_mae": round(float(np.mean([f["mae"] for f in folds])), 8),
            "n_folds": len(folds),
            "fold_metrics": folds,
        }

    return output


def generate_comparative_table(
    results: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Genera tabla comparativa de todos los modelos, ordenada por Sharpe."""
    rows = []
    for model_name, metrics in results.items():
        rows.append({
            "model": model_name,
            "mean_sharpe": metrics.get("mean_sharpe", 0.0),
            "mean_hit_rate": metrics.get("mean_hit_rate", 0.0),
            "mean_mae": metrics.get("mean_mae", 0.0),
            "n_folds": metrics.get("n_folds", 0),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("mean_sharpe", ascending=False).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Optuna HPO para LightGBM (Kelly & Xiu Sec 3.2)
# ---------------------------------------------------------------------------

def optuna_lightgbm_hpo(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_trials: int = 30,
) -> dict[str, Any]:
    """Optimiza hiperparámetros de LightGBM con Optuna.

    Busca la combinación que maximiza el Sharpe OOS en el validation set.

    Returns
    -------
    dict con keys: best_params, best_sharpe, study_results
    """
    import optuna
    import lightgbm as lgb

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        params = {
            "objective": "regression",
            "metric": "mae",
            "verbosity": -1,
            "n_estimators": trial.suggest_int("n_estimators", 100, 800),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 127),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 200),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 20.0),
        }

        model = lgb.LGBMRegressor(**params)
        model.fit(X_train, y_train)
        preds = model.predict(X_val)

        metrics = _compute_metrics(y_val.values, preds)
        return metrics["sharpe"]

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    return {
        "best_params": study.best_params,
        "best_sharpe": round(study.best_value, 4),
        "n_trials": n_trials,
        "study_results": [
            {"trial": t.number, "sharpe": round(t.value, 4) if t.value else None, "params": t.params}
            for t in study.trials[:10]  # top 10
        ],
    }


# ---------------------------------------------------------------------------
# Ensemble (Kelly & Xiu Sec 3.8, 6.4)
# ---------------------------------------------------------------------------

def train_ensemble(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    models: list[str] | None = None,
) -> dict[str, Any]:
    """Entrena ensemble de modelos con weighted average basado en OOS Sharpe.

    Parameters
    ----------
    models : list[str]
        Modelos a incluir. Default: ["ridge", "lightgbm", "xgboost"]

    Returns
    -------
    dict con: ensemble_predictions, individual_metrics, weights, ensemble_metrics
    """
    model_list = models or ["ridge", "lightgbm", "xgboost"]

    individual_results = {}
    all_predictions = {}

    for mt in model_list:
        try:
            result = train_baseline(X_train, y_train, X_test, y_test, model_type=mt)
            individual_results[mt] = result["metrics"]
            all_predictions[mt] = result["predictions"]
        except Exception as e:
            logger.error("Ensemble: error con %s: %s", mt, e)

    if not all_predictions:
        return {"error": "Ningún modelo pudo entrenarse"}

    # Calcular pesos basados en Sharpe (soft-max normalizado)
    sharpes = {m: max(individual_results[m]["sharpe"], 0.001) for m in all_predictions}
    total = sum(sharpes.values())
    weights = {m: round(s / total, 4) for m, s in sharpes.items()}

    # Ensemble: weighted average de predicciones
    ensemble_pred = np.zeros(len(y_test))
    for mt, preds in all_predictions.items():
        ensemble_pred += weights[mt] * np.array(preds)

    ensemble_metrics = _compute_metrics(y_test.values, ensemble_pred)
    ensemble_metrics["model_type"] = "ensemble"

    return {
        "ensemble_predictions": ensemble_pred,
        "ensemble_metrics": ensemble_metrics,
        "individual_metrics": individual_results,
        "weights": weights,
    }
