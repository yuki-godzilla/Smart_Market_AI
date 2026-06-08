from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import sqrt, tanh
from typing import Literal

import numpy as np
from pydantic import ConfigDict, Field

from backend.core.data_contracts import Bar, StrictBaseModel

ADVANCED_LINEAR_ADAPTER_NAME = "advanced_linear"
SUPPORTED_ADVANCED_LINEAR_HORIZONS = tuple(range(1, 61))
DEFAULT_RANDOM_STATE = 42

AdvancedLinearModelName = Literal["Ridge", "ElasticNet"]
AdvancedForecastConfidence = Literal["low", "medium", "high"]


class AdvancedForecastValidationMetrics(StrictBaseModel):
    """Walk-forward metrics for an advanced forecast adapter."""

    mae: Decimal = Field(ge=0)
    rmse: Decimal = Field(ge=0)
    direction_accuracy: Decimal = Field(ge=0, le=1)
    fold_count: int = Field(ge=0)
    sample_count: int = Field(ge=0)
    baseline_zero_rmse: Decimal | None = Field(default=None, ge=0)
    rmse_improvement: Decimal | None = None


class FeatureContribution(StrictBaseModel):
    """Linear-model coefficient summary for display, not causal explanation."""

    feature: str = Field(min_length=1)
    effect: Literal["positive", "negative"]
    weight: Decimal


class AdvancedLinearForecastResult(StrictBaseModel):
    """Advanced linear forecast output for one symbol and horizon."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    adapter_name: str = ADVANCED_LINEAR_ADAPTER_NAME
    model_name: AdvancedLinearModelName
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    predicted_return: Decimal
    direction_score: Decimal = Field(ge=0, le=1)
    confidence: AdvancedForecastConfidence
    validation_metrics: AdvancedForecastValidationMetrics
    feature_contribution_summary: list[FeatureContribution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _PreparedDataset:
    symbol: str
    feature_names: list[str]
    features: np.ndarray
    targets: np.ndarray
    latest_features: np.ndarray


@dataclass(frozen=True)
class _FittedRidge:
    feature_names: list[str]
    medians: np.ndarray
    means: np.ndarray
    scales: np.ndarray
    coefficients: np.ndarray

    def predict(self, features: np.ndarray) -> np.ndarray:
        imputed = _impute(features, self.medians)
        scaled = _scale(imputed, self.means, self.scales)
        design = _with_intercept(scaled)
        return design @ self.coefficients


class AdvancedLinearForecastAdapter:
    """Lightweight deterministic advanced forecast adapter using ridge regression."""

    def __init__(
        self,
        *,
        model_name: AdvancedLinearModelName = "Ridge",
        alpha: float = 1.0,
        random_state: int = DEFAULT_RANDOM_STATE,
        min_samples: int = 12,
        max_contributions: int = 5,
    ) -> None:
        if model_name not in {"Ridge", "ElasticNet"}:
            raise ValueError("model_name must be Ridge or ElasticNet")
        if alpha <= 0:
            raise ValueError("alpha must be positive")
        if min_samples < 4:
            raise ValueError("min_samples must be at least 4")
        self.model_name = model_name
        self.alpha = alpha
        self.random_state = random_state
        self.min_samples = min_samples
        self.max_contributions = max_contributions

    def forecast(
        self,
        bars: list[Bar],
        *,
        horizon_days: int,
    ) -> AdvancedLinearForecastResult:
        if horizon_days not in SUPPORTED_ADVANCED_LINEAR_HORIZONS:
            raise ValueError("horizon_days must be between 1 and 60")

        sorted_bars = sorted(bars, key=lambda bar: bar.ts)
        if not sorted_bars:
            raise ValueError("bars are required")

        dataset = _prepare_dataset(sorted_bars, horizon_days=horizon_days)
        if len(dataset.targets) < self.min_samples:
            raise ValueError("not enough bars with future return targets")

        validation_predictions = _walk_forward_predictions(
            dataset.features,
            dataset.targets,
            alpha=self.alpha,
            min_train_size=max(6, min(self.min_samples, len(dataset.targets) // 2)),
        )
        fitted = _fit_ridge(
            dataset.features,
            dataset.targets,
            dataset.feature_names,
            alpha=self.alpha,
        )
        predicted_return = float(fitted.predict(dataset.latest_features.reshape(1, -1))[0])
        metrics = _validation_metrics(dataset.targets, validation_predictions)
        confidence = _confidence_from_metrics(metrics)
        warnings = _warnings_for_result(
            model_name=self.model_name,
            confidence=confidence,
            metrics=metrics,
            random_state=self.random_state,
        )

        return AdvancedLinearForecastResult(
            model_name=self.model_name,
            symbol=dataset.symbol,
            horizon_days=horizon_days,
            predicted_return=_decimal(predicted_return),
            direction_score=_decimal(_direction_score(predicted_return)),
            confidence=confidence,
            validation_metrics=metrics,
            feature_contribution_summary=_feature_contributions(
                fitted,
                max_items=self.max_contributions,
            ),
            warnings=warnings,
        )


def _prepare_dataset(bars: list[Bar], *, horizon_days: int) -> _PreparedDataset:
    feature_rows: list[dict[str, float]] = []
    targets: list[float] = []
    feature_names = _feature_names()
    if len(bars) <= horizon_days:
        raise ValueError("not enough bars with future return targets")

    for index in range(len(bars) - horizon_days):
        current_close = float(bars[index].close)
        future_close = float(bars[index + horizon_days].close)
        if current_close <= 0:
            continue
        row = _features_for_index(bars, index)
        feature_rows.append(row)
        targets.append((future_close / current_close) - 1.0)

    if not feature_rows:
        raise ValueError("not enough bars with future return targets")
    latest_features = _feature_array(
        _features_for_index(bars, len(bars) - 1),
        feature_names,
    )
    features = np.vstack([_feature_array(row, feature_names) for row in feature_rows])
    symbol = bars[-1].symbol.raw
    return _PreparedDataset(
        symbol=symbol,
        feature_names=feature_names,
        features=features,
        targets=np.asarray(targets, dtype=float),
        latest_features=latest_features,
    )


def _feature_names() -> list[str]:
    return [
        "return_1d",
        "return_5d",
        "return_20d",
        "volatility_20d",
        "drawdown_20d",
        "volume_change_5d",
        "rolling_volume_20d",
        "ma_gap_5d",
        "ma_gap_20d",
    ]


def _features_for_index(bars: list[Bar], index: int) -> dict[str, float]:
    closes = [float(bar.close) for bar in bars[: index + 1]]
    volumes = [float(bar.volume) for bar in bars[: index + 1]]
    latest_close = closes[-1]
    return {
        "return_1d": _trailing_return(closes, 1),
        "return_5d": _trailing_return(closes, 5),
        "return_20d": _trailing_return(closes, 20),
        "volatility_20d": _trailing_volatility(closes, 20),
        "drawdown_20d": _trailing_drawdown(closes, 20),
        "volume_change_5d": _trailing_return(volumes, 5),
        "rolling_volume_20d": _trailing_mean(volumes, 20),
        "ma_gap_5d": _moving_average_gap(closes, latest_close, 5),
        "ma_gap_20d": _moving_average_gap(closes, latest_close, 20),
    }


def _feature_array(row: dict[str, float], feature_names: list[str]) -> np.ndarray:
    return np.asarray([row.get(name, np.nan) for name in feature_names], dtype=float)


def _trailing_return(values: list[float], period: int) -> float:
    if len(values) <= period:
        return np.nan
    previous = values[-(period + 1)]
    latest = values[-1]
    if previous <= 0:
        return np.nan
    return (latest / previous) - 1.0


def _trailing_volatility(closes: list[float], window: int) -> float:
    if len(closes) <= 1:
        return np.nan
    selected = closes[-(window + 1) :] if len(closes) > window else closes
    returns = [
        (selected[i] / selected[i - 1]) - 1.0
        for i in range(1, len(selected))
        if selected[i - 1] > 0
    ]
    if len(returns) < 2:
        return np.nan
    return float(np.std(np.asarray(returns, dtype=float), ddof=1))


def _trailing_drawdown(closes: list[float], window: int) -> float:
    selected = closes[-window:] if len(closes) >= window else closes
    if not selected:
        return np.nan
    peak = max(selected)
    if peak <= 0:
        return np.nan
    return (peak - selected[-1]) / peak


def _trailing_mean(values: list[float], window: int) -> float:
    selected = values[-window:] if len(values) >= window else values
    clean = [value for value in selected if value >= 0]
    if not clean:
        return np.nan
    return float(np.mean(np.asarray(clean, dtype=float)))


def _moving_average_gap(closes: list[float], latest_close: float, window: int) -> float:
    if len(closes) < window or latest_close <= 0:
        return np.nan
    moving_average = float(np.mean(np.asarray(closes[-window:], dtype=float)))
    if moving_average <= 0:
        return np.nan
    return (latest_close / moving_average) - 1.0


def _walk_forward_predictions(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    alpha: float,
    min_train_size: int,
) -> list[tuple[float, float]]:
    sample_count = len(targets)
    test_size = max(1, sample_count // 6)
    fold_count = min(5, max(1, (sample_count - min_train_size) // test_size))
    predictions: list[tuple[float, float]] = []
    for fold in range(fold_count, 0, -1):
        test_start = sample_count - (fold * test_size)
        test_end = min(test_start + test_size, sample_count)
        if test_start < min_train_size or test_start >= test_end:
            continue
        fitted = _fit_ridge(
            features[:test_start],
            targets[:test_start],
            _feature_names(),
            alpha=alpha,
        )
        predicted = fitted.predict(features[test_start:test_end])
        predictions.extend(zip(predicted.tolist(), targets[test_start:test_end].tolist()))
    return predictions


def _fit_ridge(
    features: np.ndarray,
    targets: np.ndarray,
    feature_names: list[str],
    *,
    alpha: float,
) -> _FittedRidge:
    medians = _column_medians(features)
    imputed = _impute(features, medians)
    means = np.mean(imputed, axis=0)
    scales = np.std(imputed, axis=0)
    scales = np.where(scales == 0, 1.0, scales)
    scaled = _scale(imputed, means, scales)
    design = _with_intercept(scaled)
    regularization = np.eye(design.shape[1]) * alpha
    regularization[0, 0] = 0.0
    coefficients = np.linalg.pinv(design.T @ design + regularization) @ design.T @ targets
    return _FittedRidge(
        feature_names=feature_names,
        medians=medians,
        means=means,
        scales=scales,
        coefficients=coefficients,
    )


def _column_medians(features: np.ndarray) -> np.ndarray:
    medians: list[float] = []
    for column_index in range(features.shape[1]):
        column = features[:, column_index]
        clean = column[~np.isnan(column)]
        medians.append(float(np.median(clean)) if len(clean) > 0 else 0.0)
    return np.asarray(medians, dtype=float)


def _impute(features: np.ndarray, medians: np.ndarray) -> np.ndarray:
    return np.where(np.isnan(features), medians, features)


def _scale(features: np.ndarray, means: np.ndarray, scales: np.ndarray) -> np.ndarray:
    return (features - means) / scales


def _with_intercept(features: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(features.shape[0]), features])


def _validation_metrics(
    targets: np.ndarray,
    predictions: list[tuple[float, float]],
) -> AdvancedForecastValidationMetrics:
    if not predictions:
        return AdvancedForecastValidationMetrics(
            mae=Decimal("0.0000"),
            rmse=Decimal("0.0000"),
            direction_accuracy=Decimal("0.0000"),
            fold_count=0,
            sample_count=0,
            baseline_zero_rmse=_decimal(_rmse([0.0 for _ in targets], targets.tolist())),
            rmse_improvement=Decimal("0.0000"),
        )
    predicted_values = [predicted for predicted, _actual in predictions]
    actual_values = [actual for _predicted, actual in predictions]
    mae = float(np.mean(np.abs(np.asarray(predicted_values) - np.asarray(actual_values))))
    rmse = _rmse(predicted_values, actual_values)
    baseline_rmse = _rmse([0.0 for _ in actual_values], actual_values)
    direction_accuracy = sum(
        1 for predicted, actual in predictions if _sign(predicted) == _sign(actual)
    ) / len(predictions)
    return AdvancedForecastValidationMetrics(
        mae=_decimal(mae),
        rmse=_decimal(rmse),
        direction_accuracy=_decimal(direction_accuracy),
        fold_count=_estimated_fold_count(len(predictions), len(targets)),
        sample_count=len(targets),
        baseline_zero_rmse=_decimal(baseline_rmse),
        rmse_improvement=_decimal(baseline_rmse - rmse),
    )


def _estimated_fold_count(prediction_count: int, sample_count: int) -> int:
    if prediction_count <= 0 or sample_count <= 0:
        return 0
    test_size = max(1, sample_count // 6)
    return max(1, prediction_count // test_size)


def _rmse(predicted_values: list[float], actual_values: list[float]) -> float:
    if not predicted_values:
        return 0.0
    errors = np.asarray(predicted_values) - np.asarray(actual_values)
    return sqrt(float(np.mean(errors * errors)))


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _confidence_from_metrics(
    metrics: AdvancedForecastValidationMetrics,
) -> AdvancedForecastConfidence:
    baseline_rmse = metrics.baseline_zero_rmse
    rmse_is_reasonable = baseline_rmse is not None and metrics.rmse <= baseline_rmse * Decimal(
        "1.10"
    )
    if (
        metrics.sample_count >= 60
        and metrics.fold_count >= 3
        and metrics.direction_accuracy >= Decimal("0.55")
        and rmse_is_reasonable
    ):
        return "high"
    if metrics.sample_count >= 20 and metrics.fold_count >= 2:
        return "medium"
    return "low"


def _feature_contributions(
    fitted: _FittedRidge,
    *,
    max_items: int,
) -> list[FeatureContribution]:
    coefficients = fitted.coefficients[1:]
    ranked = sorted(
        zip(fitted.feature_names, coefficients),
        key=lambda item: abs(float(item[1])),
        reverse=True,
    )
    contributions: list[FeatureContribution] = []
    for feature, coefficient in ranked[:max_items]:
        if coefficient == 0:
            continue
        contributions.append(
            FeatureContribution(
                feature=feature,
                effect="positive" if coefficient > 0 else "negative",
                weight=_decimal(float(coefficient)),
            )
        )
    return contributions


def _warnings_for_result(
    *,
    model_name: AdvancedLinearModelName,
    confidence: AdvancedForecastConfidence,
    metrics: AdvancedForecastValidationMetrics,
    random_state: int,
) -> list[str]:
    warnings = [
        "This advanced forecast is experimental reference information, not investment advice.",
        "Feature contributions describe model coefficients and are not causal explanations.",
    ]
    if model_name == "ElasticNet":
        warnings.append(
            "ElasticNet is reserved for the adapter contract; current implementation "
            "uses the same deterministic ridge path."
        )
    if confidence == "low":
        warnings.append(
            "Validation data is limited or unstable; treat this forecast as low confidence."
        )
    if metrics.rmse_improvement is not None and metrics.rmse_improvement < 0:
        warnings.append("Validation RMSE did not improve over the zero-return baseline.")
    if random_state != DEFAULT_RANDOM_STATE:
        warnings.append(
            "Non-default random_state was provided, but the ridge path remains deterministic."
        )
    return warnings


def _direction_score(predicted_return: float) -> float:
    return (tanh(predicted_return / 0.05) + 1.0) / 2.0


def _decimal(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))
