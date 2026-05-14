from __future__ import annotations

from decimal import Decimal
from math import sqrt
from typing import Protocol

from pydantic import ConfigDict, Field

from backend.core.data_contracts import Bar, StrictBaseModel


class ForecastPoint(StrictBaseModel):
    """One deterministic forecast for a symbol and horizon."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    forecast_close: Decimal = Field(ge=0)


class ForecastMetrics(StrictBaseModel):
    """Walk-forward evaluation metrics for one model."""

    mae: Decimal = Field(ge=0)
    rmse: Decimal = Field(ge=0)
    direction_accuracy: Decimal = Field(ge=0, le=1)
    sample_count: int = Field(ge=0)


class ForecastEvaluation(StrictBaseModel):
    """Forecast points and metrics produced by a model."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    latest_forecast: ForecastPoint
    metrics: ForecastMetrics


class ForecastConsensus(StrictBaseModel):
    """Consensus summary across forecast model outputs."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    model_count: int = Field(ge=0)
    median_forecast_close: Decimal = Field(ge=0)
    min_forecast_close: Decimal = Field(ge=0)
    max_forecast_close: Decimal = Field(ge=0)
    forecast_range: Decimal = Field(ge=0)
    forecast_range_pct: Decimal = Field(ge=0)
    agreement: str = Field(min_length=1)


class ForecastModel(Protocol):
    """Small interface shared by deterministic baseline forecast models."""

    name: str
    min_history: int

    def predict(self, history: list[Bar], *, horizon_days: int = 1) -> ForecastPoint:
        """Predict the future close from bars available before the target date."""


class NaiveForecastModel:
    """Predict that the next close equals the latest observed close."""

    name = "naive"
    min_history = 1

    def predict(self, history: list[Bar], *, horizon_days: int = 1) -> ForecastPoint:
        _require_history(history, self.min_history, self.name)
        latest = history[-1]
        return ForecastPoint(
            symbol=latest.symbol.raw,
            model_name=self.name,
            horizon_days=horizon_days,
            forecast_close=_round_price(latest.close),
        )


class MovingAverageForecastModel:
    """Predict the next close from a trailing simple moving average."""

    def __init__(self, window: int = 3) -> None:
        if window < 1:
            raise ValueError("window must be at least 1")
        self.window = window
        self.name = f"moving_average_{window}"
        self.min_history = window

    def predict(self, history: list[Bar], *, horizon_days: int = 1) -> ForecastPoint:
        _require_history(history, self.min_history, self.name)
        selected = history[-self.window :]
        forecast_close = sum((bar.close for bar in selected), Decimal("0")) / Decimal(len(selected))
        return ForecastPoint(
            symbol=history[-1].symbol.raw,
            model_name=self.name,
            horizon_days=horizon_days,
            forecast_close=_round_price(forecast_close),
        )


class MomentumForecastModel:
    """Predict by extending the latest lookback return one horizon forward."""

    def __init__(self, lookback: int = 3) -> None:
        if lookback < 1:
            raise ValueError("lookback must be at least 1")
        self.lookback = lookback
        self.name = f"momentum_{lookback}"
        self.min_history = lookback + 1

    def predict(self, history: list[Bar], *, horizon_days: int = 1) -> ForecastPoint:
        _require_history(history, self.min_history, self.name)
        previous = history[-(self.lookback + 1)].close
        latest = history[-1].close
        if previous <= 0:
            forecast_close = latest
        else:
            period_return = (latest / previous) - Decimal("1")
            daily_return = period_return / Decimal(self.lookback)
            forecast_close = latest * ((Decimal("1") + daily_return) ** horizon_days)
        return ForecastPoint(
            symbol=history[-1].symbol.raw,
            model_name=self.name,
            horizon_days=horizon_days,
            forecast_close=_round_price(forecast_close),
        )


def evaluate_models(
    bars: list[Bar],
    models: list[ForecastModel] | None = None,
    *,
    horizon_days: int = 1,
) -> list[ForecastEvaluation]:
    """Evaluate deterministic baseline models with one-step walk-forward splits."""

    sorted_bars = sorted(bars, key=lambda bar: bar.ts)
    if not sorted_bars:
        return []
    resolved_models = models or [
        NaiveForecastModel(),
        MovingAverageForecastModel(),
        MomentumForecastModel(),
    ]
    return [
        _evaluate_model(sorted_bars, model, horizon_days=horizon_days) for model in resolved_models
    ]


def summarize_forecast_evaluations(
    evaluations: list[ForecastEvaluation],
) -> ForecastConsensus | None:
    """Summarize model agreement across forecast evaluations."""

    if not evaluations:
        return None

    forecasts = sorted(evaluation.latest_forecast.forecast_close for evaluation in evaluations)
    model_count = len(forecasts)
    median = _median(forecasts)
    lowest = forecasts[0]
    highest = forecasts[-1]
    forecast_range = highest - lowest
    if median > 0:
        forecast_range_pct = forecast_range / median
    else:
        forecast_range_pct = Decimal("0")

    first = evaluations[0]
    return ForecastConsensus(
        symbol=first.symbol,
        horizon_days=first.horizon_days,
        model_count=model_count,
        median_forecast_close=_round_price(median),
        min_forecast_close=_round_price(lowest),
        max_forecast_close=_round_price(highest),
        forecast_range=_round_price(forecast_range),
        forecast_range_pct=_round_metric(forecast_range_pct),
        agreement=_agreement_label(forecast_range_pct, model_count),
    )


def _evaluate_model(
    bars: list[Bar],
    model: ForecastModel,
    *,
    horizon_days: int,
) -> ForecastEvaluation:
    _require_history(bars, model.min_history, model.name)
    latest_forecast = model.predict(bars, horizon_days=horizon_days)
    errors: list[Decimal] = []
    squared_errors: list[Decimal] = []
    direction_hits = 0
    sample_count = 0

    for target_index in range(model.min_history + horizon_days - 1, len(bars)):
        history_end = target_index - horizon_days + 1
        history = bars[:history_end]
        actual = bars[target_index].close
        previous = history[-1].close
        forecast = model.predict(history, horizon_days=horizon_days)
        error = forecast.forecast_close - actual
        errors.append(abs(error))
        squared_errors.append(error * error)
        if _direction(forecast.forecast_close - previous) == _direction(actual - previous):
            direction_hits += 1
        sample_count += 1

    return ForecastEvaluation(
        model_name=model.name,
        symbol=bars[-1].symbol.raw,
        horizon_days=horizon_days,
        latest_forecast=latest_forecast,
        metrics=ForecastMetrics(
            mae=_mean(errors),
            rmse=_rmse(squared_errors),
            direction_accuracy=_accuracy(direction_hits, sample_count),
            sample_count=sample_count,
        ),
    )


def _require_history(history: list[Bar], min_history: int, model_name: str) -> None:
    if len(history) < min_history:
        raise ValueError(f"{model_name} requires at least {min_history} bars")


def _mean(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return _round_metric(sum(values, Decimal("0")) / Decimal(len(values)))


def _median(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    midpoint = len(values) // 2
    if len(values) % 2 == 1:
        return values[midpoint]
    return (values[midpoint - 1] + values[midpoint]) / Decimal("2")


def _agreement_label(forecast_range_pct: Decimal, model_count: int) -> str:
    if model_count < 2:
        return "UNKNOWN"
    if forecast_range_pct <= Decimal("0.01"):
        return "HIGH"
    if forecast_range_pct <= Decimal("0.03"):
        return "MEDIUM"
    return "LOW"


def _rmse(squared_errors: list[Decimal]) -> Decimal:
    if not squared_errors:
        return Decimal("0")
    mean_squared = sum(squared_errors, Decimal("0")) / Decimal(len(squared_errors))
    return _round_metric(Decimal(str(sqrt(float(mean_squared)))))


def _accuracy(hits: int, sample_count: int) -> Decimal:
    if sample_count == 0:
        return Decimal("0")
    return _round_metric(Decimal(hits) / Decimal(sample_count))


def _direction(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _round_price(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _round_metric(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))
