from __future__ import annotations

from decimal import Decimal
from typing import Literal

import numpy as np
from pydantic import ConfigDict, Field
from sklearn.ensemble import HistGradientBoostingRegressor
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
    _rmse,
    _validation_metrics,
)

ADVANCED_GBDT_SKLEARN_ADAPTER_NAME = "advanced_gbdt_sklearn"
SUPPORTED_ADVANCED_GBDT_SKLEARN_HORIZONS = tuple(range(1, 61))

AdvancedGbdtSklearnModelName = Literal["HistGradientBoostingRegressor"]


class AdvancedGbdtSklearnForecastResult(StrictBaseModel):
    """scikit-learn gradient boosting forecast output for one symbol and horizon."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    adapter_name: str = ADVANCED_GBDT_SKLEARN_ADAPTER_NAME
    model_name: AdvancedGbdtSklearnModelName
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    predicted_return: Decimal
    direction_score: Decimal = Field(ge=0, le=1)
    confidence: AdvancedForecastConfidence
    validation_metrics: AdvancedForecastValidationMetrics
    feature_contribution_summary: list[FeatureContribution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AdvancedGbdtSklearnForecastAdapter:
    """Deterministic scikit-learn histogram gradient boosting adapter."""

    def __init__(
        self,
        *,
        max_iter: int = 48,
        learning_rate: float = 0.05,
        max_leaf_nodes: int = 15,
        max_depth: int | None = 4,
        min_samples_leaf: int = 4,
        l2_regularization: float = 0.01,
        max_features: float = 0.85,
        random_state: int = DEFAULT_RANDOM_STATE,
        min_samples: int = 24,
        max_contributions: int = 5,
    ) -> None:
        if max_iter < 8:
            raise ValueError("max_iter must be at least 8")
        if learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if max_leaf_nodes < 2:
            raise ValueError("max_leaf_nodes must be at least 2")
        if min_samples_leaf < 1:
            raise ValueError("min_samples_leaf must be at least 1")
        if l2_regularization < 0:
            raise ValueError("l2_regularization must be non-negative")
        if not 0 < max_features <= 1:
            raise ValueError("max_features must be between 0 and 1")
        if min_samples < 8:
            raise ValueError("min_samples must be at least 8")
        self.model_name: AdvancedGbdtSklearnModelName = "HistGradientBoostingRegressor"
        self.max_iter = max_iter
        self.learning_rate = learning_rate
        self.max_leaf_nodes = max_leaf_nodes
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.l2_regularization = l2_regularization
        self.max_features = max_features
        self.random_state = random_state
        self.min_samples = min_samples
        self.max_contributions = max_contributions

    def forecast(
        self,
        bars: list[Bar],
        *,
        horizon_days: int,
    ) -> AdvancedGbdtSklearnForecastResult:
        if horizon_days not in SUPPORTED_ADVANCED_GBDT_SKLEARN_HORIZONS:
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
            max_iter=self.max_iter,
            learning_rate=self.learning_rate,
            max_leaf_nodes=self.max_leaf_nodes,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            l2_regularization=self.l2_regularization,
            max_features=self.max_features,
            random_state=self.random_state,
            min_train_size=min_train_size,
        )
        fitted = _fit_gbdt_pipeline(
            dataset.features,
            dataset.targets,
            max_iter=self.max_iter,
            learning_rate=self.learning_rate,
            max_leaf_nodes=self.max_leaf_nodes,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            l2_regularization=self.l2_regularization,
            max_features=self.max_features,
            random_state=self.random_state,
        )
        predicted_return = float(fitted.predict(dataset.latest_features.reshape(1, -1))[0])
        metrics = _validation_metrics(dataset.targets, validation_predictions)
        confidence = _confidence_from_metrics(metrics)

        return AdvancedGbdtSklearnForecastResult(
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
                confidence=confidence,
                metrics=metrics,
                random_state=self.random_state,
            ),
        )


def _walk_forward_predictions(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    max_depth: int | None,
    min_samples_leaf: int,
    l2_regularization: float,
    max_features: float,
    random_state: int,
    min_train_size: int,
) -> list[tuple[float, float]]:
    sample_count = len(targets)
    test_size = max(1, sample_count // 6)
    fold_count = min(4, max(1, (sample_count - min_train_size) // test_size))
    predictions: list[tuple[float, float]] = []
    for fold in range(fold_count, 0, -1):
        test_start = sample_count - (fold * test_size)
        test_end = min(test_start + test_size, sample_count)
        if test_start < min_train_size or test_start >= test_end:
            continue
        fitted = _fit_gbdt_pipeline(
            features[:test_start],
            targets[:test_start],
            max_iter=max_iter,
            learning_rate=learning_rate,
            max_leaf_nodes=max_leaf_nodes,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            l2_regularization=l2_regularization,
            max_features=max_features,
            random_state=random_state,
        )
        predicted = fitted.predict(features[test_start:test_end])
        predictions.extend(zip(predicted.tolist(), targets[test_start:test_end].tolist()))
    return predictions


def _fit_gbdt_pipeline(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    max_iter: int,
    learning_rate: float,
    max_leaf_nodes: int,
    max_depth: int | None,
    min_samples_leaf: int,
    l2_regularization: float,
    max_features: float,
    random_state: int,
) -> Pipeline:
    estimator = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=max_iter,
        learning_rate=learning_rate,
        max_leaf_nodes=max_leaf_nodes,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        l2_regularization=l2_regularization,
        max_features=max_features,
        early_stopping=False,
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


def _feature_contributions(
    fitted: Pipeline,
    feature_names: list[str],
    features: np.ndarray,
    targets: np.ndarray,
    *,
    max_items: int,
) -> list[FeatureContribution]:
    imputed_features = fitted.named_steps["imputer"].transform(features)
    baseline_predictions = fitted.named_steps["model"].predict(imputed_features)
    baseline_rmse = _rmse(baseline_predictions.tolist(), targets.tolist())
    raw_importances: list[tuple[str, float, int]] = []
    for index, feature in enumerate(feature_names):
        replaced = imputed_features.copy()
        fill_value = float(np.median(imputed_features[:, index]))
        replaced[:, index] = fill_value
        replaced_predictions = fitted.named_steps["model"].predict(replaced)
        replaced_rmse = _rmse(replaced_predictions.tolist(), targets.tolist())
        raw_importances.append((feature, max(0.0, replaced_rmse - baseline_rmse), index))

    positive_importances = [
        importance for _feature, importance, _index in raw_importances if importance > 0
    ]
    if positive_importances:
        total_importance = sum(positive_importances)
        ranked = sorted(raw_importances, key=lambda item: item[1], reverse=True)
        return _contribution_rows(
            ranked,
            imputed_features,
            targets,
            total_importance=total_importance,
            max_items=max_items,
        )

    correlation_importances = [
        (feature, abs(_feature_target_correlation(imputed_features[:, index], targets)), index)
        for feature, _importance, index in raw_importances
    ]
    total_correlation = sum(importance for _feature, importance, _index in correlation_importances)
    if total_correlation <= 0:
        return []
    ranked = sorted(correlation_importances, key=lambda item: item[1], reverse=True)
    return _contribution_rows(
        ranked,
        imputed_features,
        targets,
        total_importance=total_correlation,
        max_items=max_items,
    )


def _contribution_rows(
    ranked: list[tuple[str, float, int]],
    imputed_features: np.ndarray,
    targets: np.ndarray,
    *,
    total_importance: float,
    max_items: int,
) -> list[FeatureContribution]:
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
                weight=_decimal(float(importance / total_importance)),
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
    confidence: AdvancedForecastConfidence,
    metrics: AdvancedForecastValidationMetrics,
    random_state: int,
) -> list[str]:
    warnings = [
        "This advanced forecast is experimental reference information, not investment advice.",
        "Boosting feature impact is model sensitivity and not a causal explanation.",
        "HistGradientBoostingRegressor uses a fixed random_state for deterministic local checks.",
    ]
    if confidence == "low":
        warnings.append(
            "Validation data is limited or unstable; treat this forecast as low confidence."
        )
    if metrics.rmse_improvement is not None and metrics.rmse_improvement < 0:
        warnings.append("Validation RMSE did not improve over the zero-return baseline.")
    if random_state != DEFAULT_RANDOM_STATE:
        warnings.append("Non-default random_state may change the boosting forecast.")
    return warnings
