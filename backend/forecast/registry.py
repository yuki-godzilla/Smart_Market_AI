from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.forecast.service import (
    ForecastModel,
    MomentumForecastModel,
    MovingAverageForecastModel,
    NaiveForecastModel,
)


@dataclass(frozen=True)
class ForecastModelSpec:
    """Registry metadata for deterministic forecast baseline models."""

    key: str
    display_name: str
    description: str
    factory: Callable[[int], ForecastModel]


def forecast_model_specs() -> list[ForecastModelSpec]:
    """Return deterministic forecast model specs in display/evaluation order."""

    return [
        ForecastModelSpec(
            key="naive",
            display_name="予測: 直近値維持",
            description="直近の終値をそのまま予測値として使う基準モデル。",
            factory=lambda _reference_period: NaiveForecastModel(),
        ),
        ForecastModelSpec(
            key="moving_average",
            display_name="予測: {reference_period}日移動平均",
            description="直近の参照期間の平均終値を予測値として使う基準モデル。",
            factory=lambda reference_period: MovingAverageForecastModel(window=reference_period),
        ),
        ForecastModelSpec(
            key="momentum",
            display_name="予測: {reference_period}日モメンタム",
            description="直近の参照期間の値動きを延長する基準モデル。",
            factory=lambda reference_period: MomentumForecastModel(lookback=reference_period),
        ),
    ]


def default_forecast_models(*, reference_period: int = 3) -> list[ForecastModel]:
    """Instantiate deterministic baseline models from the registry."""

    _validate_reference_period(reference_period)
    return [spec.factory(reference_period) for spec in forecast_model_specs()]


def available_forecast_models(
    bar_count: int,
    *,
    reference_period: int = 3,
) -> list[ForecastModel]:
    """Return registry models that have enough bars to run."""

    return [
        model
        for model in default_forecast_models(reference_period=reference_period)
        if bar_count >= model.min_history
    ]


def forecast_model_display_name(model_name: str) -> str:
    """Return a beginner-friendly display label for a forecast model name."""

    if model_name == "naive":
        return "予測: 直近値維持"
    if model_name.startswith("moving_average_"):
        window = model_name.removeprefix("moving_average_")
        return f"予測: {window}日移動平均"
    if model_name.startswith("momentum_"):
        lookback = model_name.removeprefix("momentum_")
        return f"予測: {lookback}日モメンタム"
    return model_name


def forecast_model_registry_rows(*, reference_period: int = 3) -> list[dict[str, str]]:
    """Return registry rows suitable for UI or documentation display."""

    _validate_reference_period(reference_period)
    return [
        {
            "key": spec.key,
            "display_name": spec.display_name.format(reference_period=reference_period),
            "description": spec.description,
        }
        for spec in forecast_model_specs()
    ]


def _validate_reference_period(reference_period: int) -> None:
    if reference_period < 1:
        raise ValueError("reference_period must be at least 1")
