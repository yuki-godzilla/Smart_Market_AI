from __future__ import annotations

from decimal import Decimal
from typing import Literal

import numpy as np
from pydantic import ConfigDict, Field
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.forecast.adapters.advanced_linear import (
    DEFAULT_RANDOM_STATE,
    AdvancedForecastConfidence,
    AdvancedForecastValidationMetrics,
    FeatureContribution,
    _confidence_from_metrics,
    _decimal,
    _direction_score,
    _prepare_dataset,
    _validation_metrics,
)

ADVANCED_TREE_SKLEARN_ADAPTER_NAME = "advanced_tree_sklearn"
SUPPORTED_ADVANCED_TREE_SKLEARN_HORIZONS = tuple(range(1, 61))

AdvancedTreeSklearnModelName = Literal["ExtraTreesRegressor", "RandomForestRegressor"]


class AdvancedTreeSklearnForecastResult(StrictBaseModel):
    """scikit-learn tree ensemble forecast output for one symbol and horizon."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    adapter_name: str = ADVANCED_TREE_SKLEARN_ADAPTER_NAME
    model_name: AdvancedTreeSklearnModelName
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    predicted_return: Decimal
    direction_score: Decimal = Field(ge=0, le=1)
    confidence: AdvancedForecastConfidence
    validation_metrics: AdvancedForecastValidationMetrics
    feature_contribution_summary: list[FeatureContribution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AdvancedTreeSklearnForecastAdapter:
    """Deterministic scikit-learn tree ensemble adapter for forward-return forecasts."""

    def __init__(
        self,
        *,
        model_name: AdvancedTreeSklearnModelName = "ExtraTreesRegressor",
        n_estimators: int = 64,
        max_depth: int | None = 4,
        min_samples_leaf: int = 4,
        max_features: float = 0.85,
        random_state: int = DEFAULT_RANDOM_STATE,
        min_samples: int = 24,
        max_contributions: int = 5,
    ) -> None:
        if model_name not in {"ExtraTreesRegressor", "RandomForestRegressor"}:
            raise ValueError("model_name must be ExtraTreesRegressor or RandomForestRegressor")
        if n_estimators < 8:
            raise ValueError("n_estimators must be at least 8")
        if min_samples_leaf < 1:
            raise ValueError("min_samples_leaf must be at least 1")
        if not 0 < max_features <= 1:
            raise ValueError("max_features must be between 0 and 1")
        if min_samples < 8:
            raise ValueError("min_samples must be at least 8")
        self.model_name = model_name
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.random_state = random_state
        self.min_samples = min_samples
        self.max_contributions = max_contributions

    def forecast(
        self,
        bars: list[Bar],
        *,
        horizon_days: int,
    ) -> AdvancedTreeSklearnForecastResult:
        if horizon_days not in SUPPORTED_ADVANCED_TREE_SKLEARN_HORIZONS:
            raise ValueError("horizon_days must be between 1 and 60")

        sorted_bars = sorted(bars, key=lambda bar: bar.ts)
        if not sorted_bars:
            raise ValueError("bars are required")

        dataset = _prepare_dataset(sorted_bars, horizon_days=horizon_days)
        if len(dataset.targets) < self.min_samples:
            raise ValueError("not enough bars with future return targets")

        min_train_size = max(12, min(self.min_samples, len(dataset.targets) // 2))
        validation_predictions = _walk_forward_predictions(
            dataset.features,
            dataset.targets,
            model_name=self.model_name,
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            max_features=self.max_features,
            random_state=self.random_state,
            min_train_size=min_train_size,
            purge_window=horizon_days,
        )
        fitted = _fit_tree_pipeline(
            dataset.features,
            dataset.targets,
            model_name=self.model_name,
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            max_features=self.max_features,
            random_state=self.random_state,
        )
        predicted_return = float(fitted.predict(dataset.latest_features.reshape(1, -1))[0])
        metrics = _validation_metrics(dataset.targets, validation_predictions)
        confidence = _confidence_from_metrics(metrics)

        return AdvancedTreeSklearnForecastResult(
            model_name=self.model_name,
            symbol=dataset.symbol,
            horizon_days=horizon_days,
            predicted_return=_decimal(predicted_return),
            direction_score=_decimal(_direction_score(predicted_return)),
            confidence=confidence,
            validation_metrics=metrics,
            feature_contribution_summary=_feature_contributions(
                fitted,
                dataset.feature_names,
                dataset.features,
                dataset.targets,
                max_items=self.max_contributions,
            ),
            warnings=_warnings_for_result(
                model_name=self.model_name,
                confidence=confidence,
                metrics=metrics,
                random_state=self.random_state,
            ),
        )


def _walk_forward_predictions(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    model_name: AdvancedTreeSklearnModelName,
    n_estimators: int,
    max_depth: int | None,
    min_samples_leaf: int,
    max_features: float,
    random_state: int,
    min_train_size: int,
    purge_window: int,
) -> list[tuple[float, float]]:
    sample_count = len(targets)
    test_size = max(1, sample_count // 6)
    fold_count = min(4, max(1, (sample_count - min_train_size) // test_size))
    predictions: list[tuple[float, float]] = []
    for fold in range(fold_count, 0, -1):
        test_start = sample_count - (fold * test_size)
        test_end = min(test_start + test_size, sample_count)
        train_end = test_start - purge_window
        if train_end < min_train_size or test_start >= test_end:
            continue
        fitted = _fit_tree_pipeline(
            features[:train_end],
            targets[:train_end],
            model_name=model_name,
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            max_features=max_features,
            random_state=random_state,
        )
        predicted = fitted.predict(features[test_start:test_end])
        predictions.extend(zip(predicted.tolist(), targets[test_start:test_end].tolist()))
    return predictions


def _fit_tree_pipeline(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    model_name: AdvancedTreeSklearnModelName,
    n_estimators: int,
    max_depth: int | None,
    min_samples_leaf: int,
    max_features: float,
    random_state: int,
) -> Pipeline:
    estimator = _tree_estimator(
        model_name=model_name,
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        max_features=max_features,
        random_state=random_state,
    )
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("model", estimator),
        ]
    )
    pipeline.fit(features, targets)
    return pipeline


def _tree_estimator(
    *,
    model_name: AdvancedTreeSklearnModelName,
    n_estimators: int,
    max_depth: int | None,
    min_samples_leaf: int,
    max_features: float,
    random_state: int,
) -> ExtraTreesRegressor | RandomForestRegressor:
    common_kwargs = {
        "n_estimators": n_estimators,
        "max_depth": max_depth,
        "min_samples_leaf": min_samples_leaf,
        "max_features": max_features,
        "random_state": random_state,
        "n_jobs": 1,
    }
    if model_name == "RandomForestRegressor":
        return RandomForestRegressor(bootstrap=True, **common_kwargs)
    return ExtraTreesRegressor(bootstrap=False, **common_kwargs)


def _feature_contributions(
    fitted: Pipeline,
    feature_names: list[str],
    features: np.ndarray,
    targets: np.ndarray,
    *,
    max_items: int,
) -> list[FeatureContribution]:
    estimator = fitted.named_steps["model"]
    importances = getattr(estimator, "feature_importances_", np.asarray([]))
    if len(importances) == 0:
        return []
    imputed_features = fitted.named_steps["imputer"].transform(features)
    ranked = sorted(
        zip(feature_names, importances, range(len(feature_names))),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    contributions: list[FeatureContribution] = []
    for feature, importance, index in ranked[:max_items]:
        if importance <= 0:
            continue
        correlation = _feature_target_correlation(imputed_features[:, index], targets)
        effect: Literal["positive", "negative"]
        effect = "positive" if correlation >= 0 else "negative"
        contributions.append(
            FeatureContribution(
                feature=feature,
                effect=effect,
                weight=_decimal(float(importance)),
            )
        )
    return contributions


def _feature_target_correlation(feature_values: np.ndarray, targets: np.ndarray) -> float:
    feature_std = float(np.std(feature_values))
    target_std = float(np.std(targets))
    if feature_std == 0 or target_std == 0:
        return 0.0
    correlation = np.corrcoef(feature_values, targets)[0, 1]
    if np.isnan(correlation):
        return 0.0
    return float(correlation)


def _warnings_for_result(
    *,
    model_name: AdvancedTreeSklearnModelName,
    confidence: AdvancedForecastConfidence,
    metrics: AdvancedForecastValidationMetrics,
    random_state: int,
) -> list[str]:
    warnings = [
        "This advanced forecast is experimental reference information, not investment advice.",
        "Tree feature importance is model importance and not a causal explanation.",
        f"{model_name} uses a fixed random_state for deterministic local checks.",
    ]
    if confidence == "low":
        warnings.append(
            "Validation data is limited or unstable; treat this forecast as low confidence."
        )
    if metrics.rmse_improvement is not None and metrics.rmse_improvement < 0:
        warnings.append("Validation RMSE did not improve over the zero-return baseline.")
    if random_state != DEFAULT_RANDOM_STATE:
        warnings.append("Non-default random_state may change the tree ensemble forecast.")
    return warnings
