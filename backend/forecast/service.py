from __future__ import annotations

from decimal import Decimal
from math import sqrt, tanh
from typing import Literal, Protocol, TypedDict

from pydantic import ConfigDict, Field

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.forecast.adapters import (
    AdvancedForecastValidationMetrics,
    AdvancedLinearForecastAdapter,
    FeatureContribution,
)

DirectionSignalLabel = Literal[
    "STRONG_UPSIDE",
    "MODERATE_UPSIDE",
    "NEUTRAL",
    "MODERATE_DOWNSIDE",
    "STRONG_DOWNSIDE",
    "UNKNOWN",
]

VOLATILITY_FLOOR = Decimal("0.02")
DIRECTION_EDGE_SCALE = Decimal("1.25")


class ForecastDirectionSignal(TypedDict):
    forecast_return_pct: Decimal
    up_model_count: int
    down_model_count: int
    flat_model_count: int
    up_direction_ratio: Decimal
    down_direction_ratio: Decimal
    model_upside_strength_score: Decimal
    model_downside_strength_score: Decimal
    upside_signal_score: Decimal
    downside_signal_score: Decimal
    direction_net_score: Decimal
    direction_signal_label: DirectionSignalLabel


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


class AdvancedForecastEvaluation(StrictBaseModel):
    """Advanced forecast output enriched for service and API consumers."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    adapter_name: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    latest_close: Decimal = Field(ge=0)
    forecast_close: Decimal = Field(ge=0)
    predicted_return: Decimal
    direction_score: Decimal = Field(ge=0, le=1)
    confidence: str = Field(min_length=1)
    validation_metrics: AdvancedForecastValidationMetrics
    feature_contribution_summary: list[FeatureContribution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ForecastConsensus(StrictBaseModel):
    """Consensus summary across forecast model outputs."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    model_count: int = Field(ge=0)
    ensemble_forecast_close: Decimal = Field(ge=0)
    median_forecast_close: Decimal = Field(ge=0)
    min_forecast_close: Decimal = Field(ge=0)
    max_forecast_close: Decimal = Field(ge=0)
    forecast_range: Decimal = Field(ge=0)
    forecast_range_pct: Decimal = Field(ge=0)
    agreement: str = Field(min_length=1)
    latest_close: Decimal | None = Field(default=None, ge=0)
    forecast_return_pct: Decimal = Decimal("0")
    up_model_count: int = Field(default=0, ge=0)
    down_model_count: int = Field(default=0, ge=0)
    flat_model_count: int = Field(default=0, ge=0)
    up_direction_ratio: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    down_direction_ratio: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    model_upside_strength_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    model_downside_strength_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    upside_signal_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    downside_signal_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    direction_net_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    direction_signal_label: DirectionSignalLabel = "NEUTRAL"


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


def evaluate_advanced_linear_forecast(
    bars: list[Bar],
    *,
    horizon_days: int,
) -> AdvancedForecastEvaluation:
    """Evaluate the deterministic advanced-linear forecast adapter."""

    sorted_bars = sorted(bars, key=lambda bar: bar.ts)
    if not sorted_bars:
        raise ValueError("bars are required")
    result = AdvancedLinearForecastAdapter().forecast(sorted_bars, horizon_days=horizon_days)
    latest_close = sorted_bars[-1].close
    forecast_close = latest_close * (Decimal("1") + result.predicted_return)
    return AdvancedForecastEvaluation(
        adapter_name=result.adapter_name,
        model_name=result.model_name,
        symbol=result.symbol,
        horizon_days=result.horizon_days,
        latest_close=_round_price(latest_close),
        forecast_close=_round_price(forecast_close),
        predicted_return=result.predicted_return,
        direction_score=result.direction_score,
        confidence=result.confidence,
        validation_metrics=result.validation_metrics,
        feature_contribution_summary=result.feature_contribution_summary,
        warnings=result.warnings,
    )


def summarize_forecast_evaluations(
    evaluations: list[ForecastEvaluation],
    *,
    history: list[Bar] | None = None,
    latest_close: Decimal | None = None,
    momentum_5d: Decimal | None = None,
    momentum_20d: Decimal | None = None,
) -> ForecastConsensus | None:
    """Summarize model agreement across forecast evaluations."""

    if not evaluations:
        return None

    model_forecast_closes = [
        evaluation.latest_forecast.forecast_close for evaluation in evaluations
    ]
    model_forecast_weights = [
        forecast_model_signal_weight(evaluation) for evaluation in evaluations
    ]
    forecasts = sorted(model_forecast_closes)
    model_count = len(forecasts)
    ensemble = _mean_price(forecasts)
    median = _median(forecasts)
    lowest = forecasts[0]
    highest = forecasts[-1]
    forecast_range = highest - lowest
    if median > 0:
        forecast_range_pct = forecast_range / median
    else:
        forecast_range_pct = Decimal("0")
    resolved_latest_close = latest_close
    resolved_momentum_5d = momentum_5d
    resolved_momentum_20d = momentum_20d
    resolved_volatility_20d: Decimal | None = None
    resolved_volatility_60d: Decimal | None = None
    resolved_ma5: Decimal | None = None
    resolved_ma20: Decimal | None = None
    resolved_ma20_slope: Decimal | None = None
    if history:
        sorted_history = sorted(history, key=lambda bar: bar.ts)
        resolved_latest_close = sorted_history[-1].close
        if resolved_momentum_5d is None:
            resolved_momentum_5d = _history_return(sorted_history, 5)
        if resolved_momentum_20d is None:
            resolved_momentum_20d = _history_return(sorted_history, 20)
        resolved_volatility_20d = _history_volatility(sorted_history, 20)
        resolved_volatility_60d = _history_volatility(sorted_history, 60)
        resolved_ma5 = _history_moving_average(sorted_history, 5)
        resolved_ma20 = _history_moving_average(sorted_history, 20)
        resolved_ma20_slope = _history_moving_average_slope(sorted_history, 20)
    direction_signal = forecast_direction_signal(
        latest_close=resolved_latest_close,
        ensemble_forecast_close=ensemble,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        momentum_5d=resolved_momentum_5d,
        momentum_20d=resolved_momentum_20d,
        volatility_20d=resolved_volatility_20d,
        volatility_60d=resolved_volatility_60d,
        ma5=resolved_ma5,
        ma20=resolved_ma20,
        ma20_slope=resolved_ma20_slope,
        forecast_range_pct=forecast_range_pct,
    )

    first = evaluations[0]
    return ForecastConsensus(
        symbol=first.symbol,
        horizon_days=first.horizon_days,
        model_count=model_count,
        ensemble_forecast_close=_round_price(ensemble),
        median_forecast_close=_round_price(median),
        min_forecast_close=_round_price(lowest),
        max_forecast_close=_round_price(highest),
        forecast_range=_round_price(forecast_range),
        forecast_range_pct=_round_metric(forecast_range_pct),
        agreement=_agreement_label(forecast_range_pct, model_count),
        latest_close=(
            _round_price(resolved_latest_close) if resolved_latest_close is not None else None
        ),
        forecast_return_pct=direction_signal["forecast_return_pct"],
        up_model_count=int(direction_signal["up_model_count"]),
        down_model_count=int(direction_signal["down_model_count"]),
        flat_model_count=int(direction_signal["flat_model_count"]),
        up_direction_ratio=direction_signal["up_direction_ratio"],
        down_direction_ratio=direction_signal["down_direction_ratio"],
        model_upside_strength_score=direction_signal["model_upside_strength_score"],
        model_downside_strength_score=direction_signal["model_downside_strength_score"],
        upside_signal_score=direction_signal["upside_signal_score"],
        downside_signal_score=direction_signal["downside_signal_score"],
        direction_net_score=direction_signal["direction_net_score"],
        direction_signal_label=direction_signal["direction_signal_label"],
    )


def forecast_direction_signal(
    *,
    latest_close: Decimal | None,
    ensemble_forecast_close: Decimal,
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None = None,
    momentum_5d: Decimal | None,
    momentum_20d: Decimal | None,
    volatility_20d: Decimal | None = None,
    volatility_60d: Decimal | None = None,
    ma5: Decimal | None = None,
    ma20: Decimal | None = None,
    ma20_slope: Decimal | None = None,
    forecast_range_pct: Decimal,
) -> ForecastDirectionSignal:
    """Return upside/downside direction signals for ranking support."""

    model_count = len(model_forecast_closes)
    if latest_close is None or latest_close <= 0 or model_count < 1:
        return {
            "forecast_return_pct": Decimal("0"),
            "up_model_count": 0,
            "down_model_count": 0,
            "flat_model_count": model_count,
            "up_direction_ratio": Decimal("0"),
            "down_direction_ratio": Decimal("0"),
            "model_upside_strength_score": Decimal("50"),
            "model_downside_strength_score": Decimal("50"),
            "upside_signal_score": Decimal("50"),
            "downside_signal_score": Decimal("50"),
            "direction_net_score": Decimal("50"),
            "direction_signal_label": "UNKNOWN",
        }

    forecast_return_pct = (ensemble_forecast_close / latest_close) - Decimal("1")
    up_model_count = sum(1 for close in model_forecast_closes if close > latest_close)
    down_model_count = sum(1 for close in model_forecast_closes if close < latest_close)
    flat_model_count = model_count - up_model_count - down_model_count
    up_direction_ratio = Decimal(up_model_count) / Decimal(model_count)
    down_direction_ratio = Decimal(down_model_count) / Decimal(model_count)
    model_upside_strength_score = calculate_model_forecast_strength_score(
        latest_close=latest_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        volatility_20d=volatility_20d,
        side="upside",
    )
    model_downside_strength_score = calculate_model_forecast_strength_score(
        latest_close=latest_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        volatility_20d=volatility_20d,
        side="downside",
    )
    upside_signal_score = calculate_upside_signal_score(
        latest_close=latest_close,
        ensemble_forecast_close=ensemble_forecast_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        momentum_5d=momentum_5d,
        momentum_20d=momentum_20d,
        volatility_20d=volatility_20d,
        volatility_60d=volatility_60d,
        ma5=ma5,
        ma20=ma20,
        ma20_slope=ma20_slope,
        forecast_range_pct=forecast_range_pct,
    )
    downside_signal_score = calculate_downside_signal_score(
        latest_close=latest_close,
        ensemble_forecast_close=ensemble_forecast_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        momentum_5d=momentum_5d,
        momentum_20d=momentum_20d,
        volatility_20d=volatility_20d,
        volatility_60d=volatility_60d,
        ma5=ma5,
        ma20=ma20,
        ma20_slope=ma20_slope,
        forecast_range_pct=forecast_range_pct,
    )
    direction_net_score = calculate_direction_net_score(
        upside_signal_score=upside_signal_score,
        downside_signal_score=downside_signal_score,
    )
    return {
        "forecast_return_pct": _round_metric(forecast_return_pct),
        "up_model_count": up_model_count,
        "down_model_count": down_model_count,
        "flat_model_count": flat_model_count,
        "up_direction_ratio": _round_metric(up_direction_ratio),
        "down_direction_ratio": _round_metric(down_direction_ratio),
        "model_upside_strength_score": model_upside_strength_score,
        "model_downside_strength_score": model_downside_strength_score,
        "upside_signal_score": upside_signal_score,
        "downside_signal_score": downside_signal_score,
        "direction_net_score": direction_net_score,
        "direction_signal_label": direction_signal_label(
            upside_signal_score=upside_signal_score,
            downside_signal_score=downside_signal_score,
            data_is_insufficient=False,
        ),
    }


def calculate_upside_signal_score(
    *,
    latest_close: Decimal,
    ensemble_forecast_close: Decimal,
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None = None,
    momentum_5d: Decimal | None,
    momentum_20d: Decimal | None,
    volatility_20d: Decimal | None = None,
    volatility_60d: Decimal | None = None,
    ma5: Decimal | None = None,
    ma20: Decimal | None = None,
    ma20_slope: Decimal | None = None,
    forecast_range_pct: Decimal,
) -> Decimal:
    """Score upward signal strength without treating it as advice."""

    if latest_close <= 0:
        return Decimal("50")
    forecast_return_pct = (ensemble_forecast_close / latest_close) - Decimal("1")
    forecast_up_edge_score = edge_to_up_score(
        volatility_adjusted_edge(forecast_return_pct, volatility_20d)
    )
    model_up_edge_score = calculate_model_forecast_strength_score(
        latest_close=latest_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        volatility_20d=volatility_20d,
        side="upside",
    )
    momentum_up_score = calculate_momentum_edge_score(
        momentum_5d=momentum_5d,
        momentum_20d=momentum_20d,
        volatility_20d=volatility_20d,
        volatility_60d=volatility_60d,
        side="upside",
    )
    trend_up_confirmation = calculate_trend_confirmation_score(
        latest_close=latest_close,
        ma5=ma5,
        ma20=ma20,
        ma20_slope=ma20_slope,
        side="upside",
    )
    raw_score = (
        forecast_up_edge_score * Decimal("0.35")
        + model_up_edge_score * Decimal("0.35")
        + momentum_up_score * Decimal("0.20")
        + trend_up_confirmation * Decimal("0.10")
    )
    return confidence_adjusted_direction_score(raw_score, forecast_range_pct)


def calculate_downside_signal_score(
    *,
    latest_close: Decimal,
    ensemble_forecast_close: Decimal,
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None = None,
    momentum_5d: Decimal | None,
    momentum_20d: Decimal | None,
    volatility_20d: Decimal | None = None,
    volatility_60d: Decimal | None = None,
    ma5: Decimal | None = None,
    ma20: Decimal | None = None,
    ma20_slope: Decimal | None = None,
    forecast_range_pct: Decimal,
) -> Decimal:
    """Score downside warning strength without treating it as advice."""

    if latest_close <= 0:
        return Decimal("50")
    forecast_return_pct = (ensemble_forecast_close / latest_close) - Decimal("1")
    forecast_down_edge_score = edge_to_down_score(
        volatility_adjusted_edge(forecast_return_pct, volatility_20d)
    )
    model_down_edge_score = calculate_model_forecast_strength_score(
        latest_close=latest_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        volatility_20d=volatility_20d,
        side="downside",
    )
    momentum_down_score = calculate_momentum_edge_score(
        momentum_5d=momentum_5d,
        momentum_20d=momentum_20d,
        volatility_20d=volatility_20d,
        volatility_60d=volatility_60d,
        side="downside",
    )
    trend_down_confirmation = calculate_trend_confirmation_score(
        latest_close=latest_close,
        ma5=ma5,
        ma20=ma20,
        ma20_slope=ma20_slope,
        side="downside",
    )
    raw_score = (
        forecast_down_edge_score * Decimal("0.35")
        + model_down_edge_score * Decimal("0.35")
        + momentum_down_score * Decimal("0.20")
        + trend_down_confirmation * Decimal("0.10")
    )
    return confidence_adjusted_direction_score(raw_score, forecast_range_pct)


def calculate_model_forecast_strength_score(
    *,
    latest_close: Decimal,
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None = None,
    volatility_20d: Decimal | None = None,
    side: Literal["upside", "downside"],
) -> Decimal:
    """Score weighted model-by-model forecast return strength for one side."""

    if latest_close <= 0 or not model_forecast_closes:
        return Decimal("50")
    weights = _model_signal_weights_for_closes(
        model_forecast_closes,
        model_forecast_weights,
    )
    weighted_total = Decimal("0")
    total_weight = Decimal("0")
    for forecast_close, weight in zip(model_forecast_closes, weights):
        forecast_return_pct = (forecast_close / latest_close) - Decimal("1")
        if side == "upside":
            model_score = edge_to_up_score(
                volatility_adjusted_edge(forecast_return_pct, volatility_20d)
            )
        else:
            model_score = edge_to_down_score(
                volatility_adjusted_edge(forecast_return_pct, volatility_20d)
            )
        weighted_total += model_score * weight
        total_weight += weight
    if total_weight <= 0:
        return Decimal("50")
    return clamp_score(weighted_total / total_weight)


def calculate_momentum_edge_score(
    *,
    momentum_5d: Decimal | None,
    momentum_20d: Decimal | None,
    volatility_20d: Decimal | None = None,
    volatility_60d: Decimal | None = None,
    side: Literal["upside", "downside"],
) -> Decimal:
    """Score recent price momentum continuously after volatility adjustment."""

    score_func = edge_to_up_score if side == "upside" else edge_to_down_score
    score_5d = (
        score_func(volatility_adjusted_edge(momentum_5d, volatility_20d))
        if momentum_5d is not None
        else Decimal("50")
    )
    score_20d = (
        score_func(
            volatility_adjusted_edge(
                momentum_20d,
                volatility_60d if volatility_60d is not None else volatility_20d,
            )
        )
        if momentum_20d is not None
        else Decimal("50")
    )
    return clamp_score((score_5d * Decimal("0.40")) + (score_20d * Decimal("0.60")))


def calculate_trend_confirmation_score(
    *,
    latest_close: Decimal | None,
    ma5: Decimal | None,
    ma20: Decimal | None,
    ma20_slope: Decimal | None,
    side: Literal["upside", "downside"],
) -> Decimal:
    """Score simple MA trend confirmation for upside/downside signals."""

    if latest_close is None or ma5 is None or ma20 is None or ma20_slope is None:
        return Decimal("50")
    if side == "upside":
        matches = sum(
            [
                latest_close > ma20,
                ma5 > ma20,
                ma20_slope > 0,
            ]
        )
    else:
        matches = sum(
            [
                latest_close < ma20,
                ma5 < ma20,
                ma20_slope < 0,
            ]
        )
    scores = {
        3: Decimal("100"),
        2: Decimal("75"),
        1: Decimal("50"),
        0: Decimal("25"),
    }
    return scores[matches]


def volatility_adjusted_edge(
    return_pct: Decimal | None,
    volatility: Decimal | None,
) -> Decimal:
    """Normalize a return by recent volatility with a conservative floor."""

    if return_pct is None:
        return Decimal("0")
    return return_pct / safe_signal_volatility(volatility)


def edge_to_up_score(
    edge: Decimal,
    scale: Decimal = DIRECTION_EDGE_SCALE,
) -> Decimal:
    """Convert a volatility-adjusted edge to a bounded 0-100 upside score."""

    if scale <= 0:
        scale = DIRECTION_EDGE_SCALE
    tanh_value = Decimal(str(tanh(float(edge / scale))))
    return clamp_score(Decimal("50") + (Decimal("50") * tanh_value))


def edge_to_down_score(
    edge: Decimal,
    scale: Decimal = DIRECTION_EDGE_SCALE,
) -> Decimal:
    """Convert a volatility-adjusted edge to a bounded 0-100 downside score."""

    return edge_to_up_score(-edge, scale)


def safe_signal_volatility(volatility: Decimal | None) -> Decimal:
    """Return the volatility denominator used by direction-signal v2."""

    if volatility is None or volatility <= 0:
        return VOLATILITY_FLOOR
    return max(volatility, VOLATILITY_FLOOR)


def forecast_model_signal_weight(evaluation: ForecastEvaluation) -> Decimal:
    """Return a conservative model weight from walk-forward direction accuracy."""

    sample_count = evaluation.metrics.sample_count
    if sample_count <= 0:
        return Decimal("1")
    direction_accuracy = min(
        max(evaluation.metrics.direction_accuracy, Decimal("0")),
        Decimal("1"),
    )
    raw_weight = Decimal("1") + (direction_accuracy - Decimal("0.50"))
    return _round_metric(min(max(raw_weight, Decimal("0.80")), Decimal("1.20")))


def _model_signal_weights_for_closes(
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None,
) -> list[Decimal]:
    model_count = len(model_forecast_closes)
    if not model_forecast_weights:
        return [Decimal("1") for _ in model_forecast_closes]
    normalized = [
        min(max(weight, Decimal("0.80")), Decimal("1.20"))
        for weight in model_forecast_weights[:model_count]
    ]
    if len(normalized) < model_count:
        normalized.extend(Decimal("1") for _ in range(model_count - len(normalized)))
    return normalized


def calculate_direction_net_score(
    *,
    upside_signal_score: Decimal,
    downside_signal_score: Decimal,
) -> Decimal:
    """Normalize upside minus downside warning into a 0-100 ranking signal."""

    return clamp_score(Decimal("50") + ((upside_signal_score - downside_signal_score) / 2))


def confidence_adjusted_direction_score(
    raw_score: Decimal,
    forecast_range_pct: Decimal,
) -> Decimal:
    """Pull directional scores toward neutral when model spread is wide."""

    factor = direction_confidence_factor(forecast_range_pct)
    return clamp_score(Decimal("50") + ((raw_score - Decimal("50")) * factor))


def direction_confidence_factor(forecast_range_pct: Decimal) -> Decimal:
    """Return a conservative confidence factor from model spread, not an additive bonus."""

    confidence = agreement_confidence_score(forecast_range_pct) / Decimal("100")
    return max(confidence, Decimal("0.70"))


def direction_signal_label(
    *,
    upside_signal_score: Decimal,
    downside_signal_score: Decimal,
    data_is_insufficient: bool,
) -> DirectionSignalLabel:
    """Classify direction signals for UI display."""

    if data_is_insufficient:
        return "UNKNOWN"
    signal_gap = upside_signal_score - downside_signal_score
    if upside_signal_score >= Decimal("80") and signal_gap >= Decimal("20"):
        return "STRONG_UPSIDE"
    if upside_signal_score >= Decimal("65") and signal_gap >= Decimal("10"):
        return "MODERATE_UPSIDE"
    if downside_signal_score >= Decimal("80") and signal_gap <= Decimal("-20"):
        return "STRONG_DOWNSIDE"
    if downside_signal_score >= Decimal("65") and signal_gap <= Decimal("-10"):
        return "MODERATE_DOWNSIDE"
    return "NEUTRAL"


def linear_score(
    value: Decimal,
    *,
    low: Decimal,
    mid: Decimal,
    high: Decimal,
) -> Decimal:
    """Map low/mid/high thresholds to 0/50/100."""

    if value <= low:
        return Decimal("0")
    if value >= high:
        return Decimal("100")
    if value <= mid:
        return clamp_score(Decimal("50") * (value - low) / (mid - low))
    return clamp_score(Decimal("50") + (Decimal("50") * (value - mid) / (high - mid)))


def inverse_linear_score(
    value: Decimal,
    *,
    low: Decimal,
    mid: Decimal,
    high: Decimal,
) -> Decimal:
    """Map low/mid/high thresholds to 100/50/0."""

    return clamp_score(Decimal("100") - linear_score(value, low=low, mid=mid, high=high))


def agreement_confidence_score(forecast_range_pct: Decimal) -> Decimal:
    """Return confidence that model spread is not excessive."""

    if forecast_range_pct <= Decimal("0.01"):
        return Decimal("100")
    if forecast_range_pct <= Decimal("0.03"):
        return Decimal("70")
    return Decimal("40")


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


def _mean_price(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


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


def _history_return(history: list[Bar], lookback: int) -> Decimal | None:
    if len(history) <= lookback:
        return None
    previous = history[-(lookback + 1)].close
    latest = history[-1].close
    if previous <= 0:
        return None
    return (latest / previous) - Decimal("1")


def _history_volatility(history: list[Bar], window: int) -> Decimal | None:
    if len(history) <= window:
        return None
    selected = history[-(window + 1) :]
    returns: list[Decimal] = []
    for previous, current in zip(selected, selected[1:]):
        if previous.close <= 0:
            continue
        returns.append((current.close / previous.close) - Decimal("1"))
    if len(returns) < 2:
        return None
    mean_return = sum(returns, Decimal("0")) / Decimal(len(returns))
    variance = sum(
        ((value - mean_return) * (value - mean_return) for value in returns),
        Decimal("0"),
    ) / Decimal(len(returns))
    if variance <= 0:
        return Decimal("0")
    return _round_metric(Decimal(str(sqrt(float(variance)))))


def _history_moving_average(history: list[Bar], window: int) -> Decimal | None:
    if len(history) < window:
        return None
    closes = [bar.close for bar in history[-window:]]
    return _round_metric(sum(closes, Decimal("0")) / Decimal(window))


def _history_moving_average_slope(history: list[Bar], window: int) -> Decimal | None:
    if len(history) <= window:
        return None
    current = _history_moving_average(history, window)
    previous = _history_moving_average(history[:-1], window)
    if current is None or previous is None:
        return None
    return current - previous


def clamp_score(value: Decimal) -> Decimal:
    return _round_score(min(max(value, Decimal("0")), Decimal("100")))


def _round_price(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _round_metric(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _round_score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
