from __future__ import annotations

from decimal import Decimal
from math import sqrt, tanh
from typing import Literal

import numpy as np
from pydantic import ConfigDict, Field

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.forecast.adapters.advanced_linear import (
    AdvancedForecastConfidence,
    AdvancedForecastValidationMetrics,
    FeatureContribution,
)

ADVANCED_QUANTILE_ADAPTER_NAME = "advanced_quantile"
SUPPORTED_ADVANCED_QUANTILE_HORIZONS = tuple(range(1, 31))

AdvancedQuantileModelName = Literal["HistoricalQuantile"]


class AdvancedQuantileForecastResult(StrictBaseModel):
    """Distribution-style forecast output based on historical forward returns."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    adapter_name: str = ADVANCED_QUANTILE_ADAPTER_NAME
    model_name: AdvancedQuantileModelName = "HistoricalQuantile"
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    predicted_return: Decimal
    predicted_return_lower: Decimal
    predicted_return_upper: Decimal
    direction_score: Decimal = Field(ge=0, le=1)
    confidence: AdvancedForecastConfidence
    validation_metrics: AdvancedForecastValidationMetrics
    feature_contribution_summary: list[FeatureContribution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AdvancedQuantileForecastAdapter:
    """Lightweight deterministic forecast range adapter using historical quantiles."""

    def __init__(
        self,
        *,
        lower_quantile: float = 0.20,
        center_quantile: float = 0.50,
        upper_quantile: float = 0.80,
        min_samples: int = 20,
    ) -> None:
        if not 0 < lower_quantile < center_quantile < upper_quantile < 1:
            raise ValueError("quantiles must satisfy 0 < lower < center < upper < 1")
        if min_samples < 4:
            raise ValueError("min_samples must be at least 4")
        self.lower_quantile = lower_quantile
        self.center_quantile = center_quantile
        self.upper_quantile = upper_quantile
        self.min_samples = min_samples

    def forecast(
        self,
        bars: list[Bar],
        *,
        horizon_days: int,
    ) -> AdvancedQuantileForecastResult:
        if horizon_days not in SUPPORTED_ADVANCED_QUANTILE_HORIZONS:
            raise ValueError("horizon_days must be between 1 and 30")

        sorted_bars = sorted(bars, key=lambda bar: bar.ts)
        targets = _forward_returns(sorted_bars, horizon_days=horizon_days)
        if len(targets) < self.min_samples:
            raise ValueError("not enough bars with future return targets")

        predicted_return = _quantile(targets, self.center_quantile)
        lower_return = _quantile(targets, self.lower_quantile)
        upper_return = _quantile(targets, self.upper_quantile)
        validation_predictions = _expanding_quantile_predictions(
            targets,
            quantile=self.center_quantile,
            min_train_size=max(6, min(self.min_samples, len(targets) // 2)),
        )
        metrics = _validation_metrics(targets, validation_predictions)
        confidence = _confidence_from_metrics(metrics)

        return AdvancedQuantileForecastResult(
            symbol=sorted_bars[-1].symbol.raw,
            horizon_days=horizon_days,
            predicted_return=_decimal(predicted_return),
            predicted_return_lower=_decimal(lower_return),
            predicted_return_upper=_decimal(upper_return),
            direction_score=_decimal(_direction_score(predicted_return)),
            confidence=confidence,
            validation_metrics=metrics,
            warnings=_warnings_for_result(confidence=confidence, metrics=metrics),
        )


def _forward_returns(bars: list[Bar], *, horizon_days: int) -> np.ndarray:
    if len(bars) <= horizon_days:
        raise ValueError("not enough bars with future return targets")

    targets: list[float] = []
    for index in range(len(bars) - horizon_days):
        current_close = float(bars[index].close)
        future_close = float(bars[index + horizon_days].close)
        if current_close <= 0:
            continue
        targets.append((future_close / current_close) - 1.0)
    if not targets:
        raise ValueError("not enough bars with future return targets")
    return np.asarray(targets, dtype=float)


def _expanding_quantile_predictions(
    targets: np.ndarray,
    *,
    quantile: float,
    min_train_size: int,
) -> list[tuple[float, float]]:
    predictions: list[tuple[float, float]] = []
    for index in range(min_train_size, len(targets)):
        predicted = _quantile(targets[:index], quantile)
        predictions.append((predicted, float(targets[index])))
    return predictions


def _quantile(values: np.ndarray, quantile: float) -> float:
    return float(np.quantile(values, quantile))


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


def _warnings_for_result(
    *,
    confidence: AdvancedForecastConfidence,
    metrics: AdvancedForecastValidationMetrics,
) -> list[str]:
    warnings = [
        "This advanced forecast is experimental reference information, not investment advice.",
        "Quantile range is based on historical forward returns and is not a guaranteed interval.",
    ]
    if confidence == "low":
        warnings.append(
            "Validation data is limited or unstable; treat this forecast as low confidence."
        )
    if metrics.rmse_improvement is not None and metrics.rmse_improvement < 0:
        warnings.append("Validation RMSE did not improve over the zero-return baseline.")
    return warnings


def _direction_score(predicted_return: float) -> float:
    return (tanh(predicted_return / 0.05) + 1.0) / 2.0


def _decimal(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))
