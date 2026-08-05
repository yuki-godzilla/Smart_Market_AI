"""Evaluation-only, regime-aware ensemble for advanced forecasts.

The policy is intentionally compact and deterministic.  It is a comparison
candidate for the validation-weighted consensus, not a ranking input.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import ConfigDict, Field

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.forecast.service import AdvancedForecastEvaluation

REGIME_GATED_ENSEMBLE_MODEL_NAME = "advanced_regime_gated_ensemble"

_WEIGHTS_BY_REGIME: dict[str, dict[str, Decimal]] = {
    "uptrend": {
        "advanced_linear": Decimal("0.25"),
        "advanced_tree_sklearn": Decimal("0.25"),
        "advanced_gbdt_sklearn": Decimal("0.30"),
        "advanced_quantile": Decimal("0.20"),
    },
    "downtrend": {
        "advanced_linear": Decimal("0.30"),
        "advanced_tree_sklearn": Decimal("0.15"),
        "advanced_gbdt_sklearn": Decimal("0.20"),
        "advanced_quantile": Decimal("0.35"),
    },
    "drawdown": {
        "advanced_linear": Decimal("0.30"),
        "advanced_tree_sklearn": Decimal("0.15"),
        "advanced_gbdt_sklearn": Decimal("0.20"),
        "advanced_quantile": Decimal("0.35"),
    },
    "high_volatility": {
        "advanced_linear": Decimal("0.30"),
        "advanced_tree_sklearn": Decimal("0.20"),
        "advanced_gbdt_sklearn": Decimal("0.15"),
        "advanced_quantile": Decimal("0.35"),
    },
    "range_bound": {
        "advanced_linear": Decimal("0.20"),
        "advanced_tree_sklearn": Decimal("0.30"),
        "advanced_gbdt_sklearn": Decimal("0.30"),
        "advanced_quantile": Decimal("0.20"),
    },
    "unknown": {
        "advanced_linear": Decimal("0.30"),
        "advanced_tree_sklearn": Decimal("0.25"),
        "advanced_gbdt_sklearn": Decimal("0.25"),
        "advanced_quantile": Decimal("0.20"),
    },
}


class RegimeGatedForecastConsensus(StrictBaseModel):
    """Transparent reference ensemble for Cockpit and offline evaluation."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = REGIME_GATED_ENSEMBLE_MODEL_NAME
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    regime: str = Field(min_length=1)
    model_count: int = Field(ge=2)
    model_weights: dict[str, Decimal]
    predicted_return: Decimal
    forecast_close: Decimal = Field(ge=0)
    predicted_return_lower: Decimal
    predicted_return_upper: Decimal
    forecast_close_lower: Decimal = Field(ge=0)
    forecast_close_upper: Decimal = Field(ge=0)
    predicted_return_range: Decimal = Field(ge=0)
    agreement: str = Field(min_length=1)
    confidence: str = Field(min_length=1)
    direction_agreement_score: Decimal = Field(ge=0, le=100)
    mean_direction_accuracy: Decimal = Field(ge=0, le=1)
    mean_rmse: Decimal = Field(ge=0)
    best_adapter_name: str = ""
    warnings: list[str] = Field(default_factory=list)


def classify_forecast_regime(bars: list[Bar]) -> str:
    """Classify the current regime using only bars available at prediction time."""

    sorted_bars = sorted(bars, key=lambda bar: bar.ts)
    if len(sorted_bars) < 21:
        return "unknown"
    closes = [bar.close for bar in sorted_bars[-21:]]
    if any(close <= 0 for close in closes):
        return "unknown"
    return_20d = (closes[-1] / closes[0]) - Decimal("1")
    peak = max(closes)
    drawdown = (closes[-1] / peak) - Decimal("1") if peak > 0 else Decimal("0")
    daily_returns = [
        (current / previous) - Decimal("1") for previous, current in zip(closes, closes[1:])
    ]
    mean_return = sum(daily_returns, Decimal("0")) / Decimal(len(daily_returns))
    variance = sum(((value - mean_return) ** 2 for value in daily_returns), Decimal("0")) / Decimal(
        len(daily_returns)
    )
    volatility = variance.sqrt()
    if drawdown <= Decimal("-0.08"):
        return "drawdown"
    if volatility >= Decimal("0.035"):
        return "high_volatility"
    if return_20d >= Decimal("0.05"):
        return "uptrend"
    if return_20d <= Decimal("-0.05"):
        return "downtrend"
    return "range_bound"


def summarize_regime_gated_forecasts(
    evaluations: list[AdvancedForecastEvaluation],
    *,
    regime: str,
) -> RegimeGatedForecastConsensus | None:
    """Return the reference ensemble for one common symbol and horizon."""

    if len(evaluations) < 2:
        return None
    if (
        len({evaluation.horizon_days for evaluation in evaluations}) != 1
        or len({evaluation.symbol for evaluation in evaluations}) != 1
        or len({evaluation.latest_close for evaluation in evaluations}) != 1
    ):
        raise ValueError("regime-gated ensemble requires one symbol, close, and horizon")

    normalized_regime = regime if regime in _WEIGHTS_BY_REGIME else "unknown"
    available = {
        evaluation.adapter_name: evaluation
        for evaluation in evaluations
        if evaluation.adapter_name in _WEIGHTS_BY_REGIME[normalized_regime]
    }
    if len(available) < 2:
        return None
    raw_weights = _WEIGHTS_BY_REGIME[normalized_regime]
    total_weight = sum((raw_weights[name] for name in available), Decimal("0"))
    weights = {name: raw_weights[name] / total_weight for name in sorted(available)}
    ordered = [available[name] for name in sorted(available)]
    predicted_return = sum(
        (evaluation.predicted_return * weights[evaluation.adapter_name] for evaluation in ordered),
        Decimal("0"),
    )
    lower = min(
        (
            evaluation.predicted_return_lower
            if evaluation.predicted_return_lower is not None
            else evaluation.predicted_return
        )
        for evaluation in ordered
    )
    upper = max(
        (
            evaluation.predicted_return_upper
            if evaluation.predicted_return_upper is not None
            else evaluation.predicted_return
        )
        for evaluation in ordered
    )
    latest_close = ordered[0].latest_close
    direction_agreement = _direction_agreement_score(ordered, weights)
    mean_direction_accuracy = sum(
        (
            evaluation.validation_metrics.direction_accuracy * weights[evaluation.adapter_name]
            for evaluation in ordered
        ),
        Decimal("0"),
    )
    mean_rmse = sum(
        (
            evaluation.validation_metrics.rmse * weights[evaluation.adapter_name]
            for evaluation in ordered
        ),
        Decimal("0"),
    )
    best = min(ordered, key=lambda evaluation: evaluation.validation_metrics.rmse)
    predicted_range = upper - lower
    agreement = _agreement_label(direction_agreement, predicted_range)
    confidence = _confidence_label(agreement, mean_direction_accuracy)
    warnings = [
        "局面別の固定weightを使う評価専用モデルです。通常の合意予測、Ranking、AI総合には反映されません。",
        f"判定局面: {normalized_regime}。",
    ]
    if len(ordered) < len(raw_weights):
        warnings.append("一部モデルが利用できないため、利用可能なweightで再正規化しました。")
    return RegimeGatedForecastConsensus(
        symbol=ordered[0].symbol,
        horizon_days=ordered[0].horizon_days,
        regime=normalized_regime,
        model_count=len(ordered),
        model_weights={name: _round_metric(weight) for name, weight in weights.items()},
        predicted_return=_round_metric(predicted_return),
        forecast_close=_round_price(latest_close * (Decimal("1") + predicted_return)),
        predicted_return_lower=_round_metric(lower),
        predicted_return_upper=_round_metric(upper),
        forecast_close_lower=_round_price(latest_close * (Decimal("1") + lower)),
        forecast_close_upper=_round_price(latest_close * (Decimal("1") + upper)),
        predicted_return_range=_round_metric(predicted_range),
        agreement=agreement,
        confidence=confidence,
        direction_agreement_score=_round_metric(direction_agreement),
        mean_direction_accuracy=_round_metric(mean_direction_accuracy),
        mean_rmse=_round_metric(mean_rmse),
        best_adapter_name=best.adapter_name,
        warnings=warnings,
    )


def _direction_agreement_score(
    evaluations: list[AdvancedForecastEvaluation], weights: dict[str, Decimal]
) -> Decimal:
    positive = sum(
        (
            weights[evaluation.adapter_name]
            for evaluation in evaluations
            if evaluation.predicted_return > 0
        ),
        Decimal("0"),
    )
    negative = sum(
        (
            weights[evaluation.adapter_name]
            for evaluation in evaluations
            if evaluation.predicted_return < 0
        ),
        Decimal("0"),
    )
    neutral = Decimal("1") - positive - negative
    return max(positive, negative, neutral) * Decimal("100")


def _agreement_label(direction_agreement: Decimal, predicted_range: Decimal) -> str:
    if direction_agreement >= Decimal("75") and predicted_range <= Decimal("0.08"):
        return "HIGH"
    if direction_agreement >= Decimal("55") and predicted_range <= Decimal("0.16"):
        return "MEDIUM"
    return "LOW"


def _confidence_label(agreement: str, mean_direction_accuracy: Decimal) -> str:
    if agreement == "HIGH" and mean_direction_accuracy >= Decimal("0.55"):
        return "high"
    if agreement == "LOW" or mean_direction_accuracy < Decimal("0.50"):
        return "low"
    return "medium"


def _round_metric(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _round_price(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
