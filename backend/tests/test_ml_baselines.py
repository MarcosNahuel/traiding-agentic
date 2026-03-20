"""Tests TDD para baselines lineales (Ridge, ElasticNet) y comparative analysis.

RED: estos tests se escriben ANTES de la implementación.
Los tests definen el contrato que los baselines deben cumplir.
"""

import pytest
import numpy as np
import pandas as pd


def _make_dummy_dataset(n_rows=500, n_features=10, seed=42):
    """Genera dataset sintético para testing de modelos."""
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2025-01-01", periods=n_rows, freq="h")
    X = pd.DataFrame(
        rng.randn(n_rows, n_features),
        columns=[f"feat_{i}" for i in range(n_features)],
    )
    # Target con algo de señal lineal + ruido
    y = 0.001 * X["feat_0"] - 0.0005 * X["feat_1"] + rng.randn(n_rows) * 0.01
    X["open_time"] = dates
    X["symbol"] = "BTCUSDT"
    return X, pd.Series(y, name="logret_next")


class TestTrainBaseline:
    """Tests para train_baseline() — entrena Ridge o ElasticNet."""

    def test_train_ridge_returns_model_and_metrics(self):
        """Ridge debe devolver modelo entrenado y métricas de evaluación."""
        from app.services.ml.baselines import train_baseline

        X, y = _make_dummy_dataset()
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = train_baseline(
            X_train=X.iloc[:split][feature_cols],
            y_train=y.iloc[:split],
            X_test=X.iloc[split:][feature_cols],
            y_test=y.iloc[split:],
            model_type="ridge",
        )

        assert "model" in result
        assert "metrics" in result
        assert "mae" in result["metrics"]
        assert "sharpe" in result["metrics"]
        assert "hit_rate" in result["metrics"]
        assert result["metrics"]["model_type"] == "ridge"

    def test_train_elasticnet_returns_model_and_metrics(self):
        """ElasticNet debe devolver modelo entrenado y métricas."""
        from app.services.ml.baselines import train_baseline

        X, y = _make_dummy_dataset()
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = train_baseline(
            X_train=X.iloc[:split][feature_cols],
            y_train=y.iloc[:split],
            X_test=X.iloc[split:][feature_cols],
            y_test=y.iloc[split:],
            model_type="elasticnet",
        )

        assert result["metrics"]["model_type"] == "elasticnet"
        assert "mae" in result["metrics"]

    def test_predictions_are_float_array(self):
        """Las predicciones deben ser un array de floats del mismo largo que test."""
        from app.services.ml.baselines import train_baseline

        X, y = _make_dummy_dataset()
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = train_baseline(
            X_train=X.iloc[:split][feature_cols],
            y_train=y.iloc[:split],
            X_test=X.iloc[split:][feature_cols],
            y_test=y.iloc[split:],
            model_type="ridge",
        )

        assert "predictions" in result
        assert len(result["predictions"]) == len(X) - split

    def test_invalid_model_type_raises(self):
        """Tipo de modelo inválido debe lanzar ValueError."""
        from app.services.ml.baselines import train_baseline

        X, y = _make_dummy_dataset(n_rows=100)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        with pytest.raises(ValueError, match="model_type"):
            train_baseline(
                X_train=X[feature_cols],
                y_train=y,
                X_test=X[feature_cols],
                y_test=y,
                model_type="invalid_model",
            )


class TestWalkForwardBaselines:
    """Tests para walk_forward_baselines() — evalúa todos los baselines."""

    def test_returns_results_for_each_model(self):
        """Debe devolver resultados para ridge, elasticnet, y random_forest."""
        from app.services.ml.baselines import walk_forward_baselines

        X, y = _make_dummy_dataset(n_rows=600)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        df = X.copy()
        df["logret_next"] = y.values
        df["open_time"] = pd.date_range("2025-01-01", periods=600, freq="h")

        results = walk_forward_baselines(
            df=df,
            feature_cols=feature_cols,
            target_col="logret_next",
            train_days=15,
            test_days=5,
        )

        assert "ridge" in results
        assert "elasticnet" in results
        assert "random_forest" in results

    def test_each_result_has_aggregate_metrics(self):
        """Cada modelo debe tener métricas agregadas."""
        from app.services.ml.baselines import walk_forward_baselines

        X, y = _make_dummy_dataset(n_rows=600)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        df = X.copy()
        df["logret_next"] = y.values
        df["open_time"] = pd.date_range("2025-01-01", periods=600, freq="h")

        results = walk_forward_baselines(
            df=df,
            feature_cols=feature_cols,
            target_col="logret_next",
            train_days=15,
            test_days=5,
        )

        for model_name, model_result in results.items():
            assert "mean_sharpe" in model_result, f"{model_name} missing mean_sharpe"
            assert "mean_hit_rate" in model_result, f"{model_name} missing mean_hit_rate"
            assert "mean_mae" in model_result, f"{model_name} missing mean_mae"
            assert "n_folds" in model_result, f"{model_name} missing n_folds"


class TestComparativeTable:
    """Tests para generate_comparative_table()."""

    def test_returns_dataframe_with_all_models(self):
        """Debe devolver DataFrame con una fila por modelo."""
        from app.services.ml.baselines import generate_comparative_table

        # Simular resultados de walk_forward_baselines
        mock_results = {
            "ridge": {"mean_sharpe": 0.1, "mean_hit_rate": 0.51, "mean_mae": 0.005, "n_folds": 3},
            "elasticnet": {"mean_sharpe": 0.15, "mean_hit_rate": 0.52, "mean_mae": 0.0048, "n_folds": 3},
            "lightgbm": {"mean_sharpe": -1.6, "mean_hit_rate": 0.47, "mean_mae": 0.005, "n_folds": 1},
        }

        table = generate_comparative_table(mock_results)

        assert isinstance(table, pd.DataFrame)
        assert len(table) == 3
        assert "model" in table.columns
        assert "mean_sharpe" in table.columns
        assert "mean_hit_rate" in table.columns

    def test_table_sorted_by_sharpe_descending(self):
        """La tabla debe estar ordenada por Sharpe de mayor a menor."""
        from app.services.ml.baselines import generate_comparative_table

        mock_results = {
            "ridge": {"mean_sharpe": 0.1, "mean_hit_rate": 0.51, "mean_mae": 0.005, "n_folds": 3},
            "elasticnet": {"mean_sharpe": 0.5, "mean_hit_rate": 0.52, "mean_mae": 0.004, "n_folds": 3},
            "lightgbm": {"mean_sharpe": -1.6, "mean_hit_rate": 0.47, "mean_mae": 0.005, "n_folds": 1},
        }

        table = generate_comparative_table(mock_results)
        sharpes = table["mean_sharpe"].tolist()
        assert sharpes == sorted(sharpes, reverse=True)


class TestXGBoostAndLightGBM:
    """Tests para XGBoost y LightGBM como baselines."""

    def test_train_xgboost_returns_metrics(self):
        from app.services.ml.baselines import train_baseline

        X, y = _make_dummy_dataset()
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = train_baseline(
            X.iloc[:split][feature_cols], y.iloc[:split],
            X.iloc[split:][feature_cols], y.iloc[split:],
            model_type="xgboost",
        )
        assert result["metrics"]["model_type"] == "xgboost"
        assert "sharpe" in result["metrics"]

    def test_train_lightgbm_returns_metrics(self):
        from app.services.ml.baselines import train_baseline

        X, y = _make_dummy_dataset()
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = train_baseline(
            X.iloc[:split][feature_cols], y.iloc[:split],
            X.iloc[split:][feature_cols], y.iloc[split:],
            model_type="lightgbm",
        )
        assert result["metrics"]["model_type"] == "lightgbm"
        assert "sharpe" in result["metrics"]


class TestOptunaHPO:
    """Tests para Optuna hyperparameter optimization."""

    def test_optuna_returns_best_params(self):
        from app.services.ml.baselines import optuna_lightgbm_hpo

        X, y = _make_dummy_dataset(n_rows=300)
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = optuna_lightgbm_hpo(
            X.iloc[:split][feature_cols], y.iloc[:split],
            X.iloc[split:][feature_cols], y.iloc[split:],
            n_trials=5,  # pocos trials para test rápido
        )

        assert "best_params" in result
        assert "best_sharpe" in result
        assert isinstance(result["best_params"], dict)
        assert "learning_rate" in result["best_params"]

    def test_optuna_best_sharpe_is_float(self):
        from app.services.ml.baselines import optuna_lightgbm_hpo

        X, y = _make_dummy_dataset(n_rows=300)
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = optuna_lightgbm_hpo(
            X.iloc[:split][feature_cols], y.iloc[:split],
            X.iloc[split:][feature_cols], y.iloc[split:],
            n_trials=3,
        )

        assert isinstance(result["best_sharpe"], float)


class TestEnsemble:
    """Tests para ensemble de modelos."""

    def test_ensemble_returns_predictions_and_weights(self):
        from app.services.ml.baselines import train_ensemble

        X, y = _make_dummy_dataset()
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = train_ensemble(
            X.iloc[:split][feature_cols], y.iloc[:split],
            X.iloc[split:][feature_cols], y.iloc[split:],
            models=["ridge", "lightgbm"],
        )

        assert "ensemble_predictions" in result
        assert "weights" in result
        assert "ensemble_metrics" in result
        assert len(result["ensemble_predictions"]) == len(X) - split

    def test_ensemble_weights_sum_to_one(self):
        from app.services.ml.baselines import train_ensemble

        X, y = _make_dummy_dataset()
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = train_ensemble(
            X.iloc[:split][feature_cols], y.iloc[:split],
            X.iloc[split:][feature_cols], y.iloc[split:],
            models=["ridge", "lightgbm"],
        )

        total_weight = sum(result["weights"].values())
        assert abs(total_weight - 1.0) < 0.01

    def test_ensemble_metrics_has_sharpe(self):
        from app.services.ml.baselines import train_ensemble

        X, y = _make_dummy_dataset()
        split = int(len(X) * 0.7)
        feature_cols = [c for c in X.columns if c.startswith("feat_")]

        result = train_ensemble(
            X.iloc[:split][feature_cols], y.iloc[:split],
            X.iloc[split:][feature_cols], y.iloc[split:],
        )

        assert "sharpe" in result["ensemble_metrics"]
        assert result["ensemble_metrics"]["model_type"] == "ensemble"
