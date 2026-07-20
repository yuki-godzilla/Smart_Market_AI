from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from backend.core.data_contracts import Bar
from backend.forecast.adapters import (
    ADVANCED_GBDT_SKLEARN_ADAPTER_NAME,
    ADVANCED_LINEAR_ADAPTER_NAME,
    ADVANCED_QUANTILE_ADAPTER_NAME,
    ADVANCED_TREE_SKLEARN_ADAPTER_NAME,
    SUPPORTED_ADVANCED_GBDT_SKLEARN_HORIZONS,
    SUPPORTED_ADVANCED_LINEAR_HORIZONS,
    SUPPORTED_ADVANCED_QUANTILE_HORIZONS,
    SUPPORTED_ADVANCED_TREE_SKLEARN_HORIZONS,
    AdvancedGbdtSklearnForecastAdapter,
    AdvancedGbdtSklearnForecastResult,
    AdvancedLinearForecastAdapter,
    AdvancedLinearForecastResult,
    AdvancedQuantileForecastAdapter,
    AdvancedQuantileForecastResult,
    AdvancedTreeSklearnForecastAdapter,
    AdvancedTreeSklearnForecastResult,
)

AdvancedForecastResult = (
    AdvancedLinearForecastResult
    | AdvancedTreeSklearnForecastResult
    | AdvancedGbdtSklearnForecastResult
    | AdvancedQuantileForecastResult
)


class AdvancedForecastAdapter(Protocol):
    """Small interface shared by deterministic advanced forecast adapters."""

    def forecast(
        self,
        bars: list[Bar],
        *,
        horizon_days: int,
    ) -> AdvancedForecastResult:
        """Return one advanced forecast result for the requested horizon."""


@dataclass(frozen=True)
class AdvancedForecastAdapterSpec:
    """Registry metadata for deterministic advanced forecast adapters."""

    key: str
    display_name: str
    description: str
    supported_horizons: range
    factory: Callable[[], AdvancedForecastAdapter]


def advanced_forecast_adapter_specs() -> list[AdvancedForecastAdapterSpec]:
    """Return advanced forecast adapter specs in display/evaluation order."""

    return [
        AdvancedForecastAdapterSpec(
            key=ADVANCED_LINEAR_ADAPTER_NAME,
            display_name="高度予測: 線形モデル",
            description="価格特徴量から取得期間に合わせたforward returnを軽量Ridgeで参考推定します。",
            supported_horizons=SUPPORTED_ADVANCED_LINEAR_HORIZONS,
            factory=lambda: AdvancedLinearForecastAdapter(),
        ),
        AdvancedForecastAdapterSpec(
            key=ADVANCED_TREE_SKLEARN_ADAPTER_NAME,
            display_name="高度予測: ツリーモデル",
            description=(
                "価格特徴量の非線形な組み合わせをscikit-learnのExtraTreesで参考推定します。"
            ),
            supported_horizons=SUPPORTED_ADVANCED_TREE_SKLEARN_HORIZONS,
            factory=lambda: AdvancedTreeSklearnForecastAdapter(),
        ),
        AdvancedForecastAdapterSpec(
            key=ADVANCED_GBDT_SKLEARN_ADAPTER_NAME,
            display_name="高度予測: ブースティングモデル",
            description=(
                "価格特徴量の非線形な変化をscikit-learnのHistogram Gradient Boostingで"
                "参考推定します。"
            ),
            supported_horizons=SUPPORTED_ADVANCED_GBDT_SKLEARN_HORIZONS,
            factory=lambda: AdvancedGbdtSklearnForecastAdapter(),
        ),
        AdvancedForecastAdapterSpec(
            key=ADVANCED_QUANTILE_ADAPTER_NAME,
            display_name="高度予測: レンジモデル",
            description="過去のforward return分布から中央値と下振れ / 上振れレンジを参考表示します。",
            supported_horizons=SUPPORTED_ADVANCED_QUANTILE_HORIZONS,
            factory=lambda: AdvancedQuantileForecastAdapter(),
        ),
    ]


def advanced_forecast_adapter_spec(adapter_name: str) -> AdvancedForecastAdapterSpec | None:
    """Return the advanced forecast adapter spec for a key, if available."""

    normalized_name = adapter_name.strip()
    for spec in advanced_forecast_adapter_specs():
        if spec.key == normalized_name:
            return spec
    return None


def advanced_forecast_adapter_keys() -> tuple[str, ...]:
    """Return available advanced forecast adapter keys."""

    return tuple(spec.key for spec in advanced_forecast_adapter_specs())


def advanced_forecast_supported_horizons(adapter_name: str) -> range:
    """Return supported horizons for an advanced adapter key."""

    spec = advanced_forecast_adapter_spec(adapter_name)
    return spec.supported_horizons if spec is not None else range(0)
