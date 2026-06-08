from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import (
    ADVANCED_TREE_SKLEARN_ADAPTER_NAME,
    SUPPORTED_ADVANCED_TREE_SKLEARN_HORIZONS,
    AdvancedTreeSklearnForecastAdapter,
    advanced_forecast_adapter_keys,
    advanced_forecast_adapter_spec,
)


def test_advanced_tree_sklearn_adapter_predicts_forward_return():
    result = AdvancedTreeSklearnForecastAdapter().forecast(_bars(72), horizon_days=5)

    assert result.adapter_name == ADVANCED_TREE_SKLEARN_ADAPTER_NAME
    assert result.model_name == "ExtraTreesRegressor"
    assert result.symbol == "AAPL"
    assert result.horizon_days == 5
    assert SUPPORTED_ADVANCED_TREE_SKLEARN_HORIZONS[0] == 1
    assert SUPPORTED_ADVANCED_TREE_SKLEARN_HORIZONS[-1] == 60
    assert result.validation_metrics.sample_count == 67
    assert result.validation_metrics.fold_count >= 3
    assert result.validation_metrics.mae >= Decimal("0")
    assert result.validation_metrics.rmse >= Decimal("0")
    assert Decimal("0") <= result.validation_metrics.direction_accuracy <= Decimal("1")
    assert result.validation_metrics.baseline_zero_rmse is not None
    assert Decimal("0") <= result.direction_score <= Decimal("1")
    assert result.confidence in {"low", "medium", "high"}
    assert result.feature_contribution_summary
    assert any("not investment advice" in warning for warning in result.warnings)
    assert any("Tree feature importance" in warning for warning in result.warnings)


def test_advanced_tree_sklearn_adapter_supports_common_forecast_horizon():
    result = AdvancedTreeSklearnForecastAdapter().forecast(_bars(72), horizon_days=10)

    assert result.horizon_days == 10
    assert result.validation_metrics.sample_count == 62


def test_advanced_tree_sklearn_adapter_can_use_random_forest_model():
    result = AdvancedTreeSklearnForecastAdapter(
        model_name="RandomForestRegressor",
        n_estimators=16,
        min_samples=12,
    ).forecast(_bars(72), horizon_days=5)

    assert result.adapter_name == ADVANCED_TREE_SKLEARN_ADAPTER_NAME
    assert result.model_name == "RandomForestRegressor"
    assert result.feature_contribution_summary


def test_advanced_tree_sklearn_adapter_rejects_out_of_range_horizon():
    with pytest.raises(ValueError, match="horizon_days"):
        AdvancedTreeSklearnForecastAdapter().forecast(_bars(80), horizon_days=61)


def test_advanced_tree_sklearn_adapter_returns_graceful_data_shortage_error():
    with pytest.raises(ValueError, match="not enough bars"):
        AdvancedTreeSklearnForecastAdapter().forecast(_bars(20), horizon_days=10)


def test_advanced_forecast_registry_lists_tree_sklearn_adapter():
    spec = advanced_forecast_adapter_spec("advanced_tree_sklearn")

    assert "advanced_tree_sklearn" in advanced_forecast_adapter_keys()
    assert spec is not None
    assert spec.display_name == "高度予測: ツリーモデル"
    assert spec.supported_horizons[0] == 1
    assert spec.supported_horizons[-1] == 60


def _bars(count: int) -> list[Bar]:
    symbol = Symbol(raw="AAPL", exchange="NASDAQ", code="AAPL", currency="USD")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars: list[Bar] = []
    close = Decimal("100")
    for index in range(count):
        drift = Decimal("0.35")
        cycle = Decimal((index % 7) - 3) / Decimal("20")
        close = close + drift + cycle
        bars.append(
            Bar(
                symbol=symbol,
                ts=start + timedelta(days=index),
                open=close - Decimal("0.4"),
                high=close + Decimal("0.8"),
                low=close - Decimal("0.9"),
                close=close,
                volume=Decimal(1000 + (index * 17) + ((index % 5) * 11)),
                interval="1d",
                provider="fixture",
            )
        )
    return bars
