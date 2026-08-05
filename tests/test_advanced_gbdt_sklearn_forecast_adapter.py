from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import (
    ADVANCED_GBDT_SKLEARN_ADAPTER_NAME,
    SUPPORTED_ADVANCED_GBDT_SKLEARN_HORIZONS,
    AdvancedGbdtSklearnForecastAdapter,
    advanced_forecast_adapter_keys,
    advanced_forecast_adapter_spec,
)


def test_advanced_gbdt_sklearn_adapter_predicts_forward_return():
    result = AdvancedGbdtSklearnForecastAdapter().forecast(_bars(72), horizon_days=5)

    assert result.adapter_name == ADVANCED_GBDT_SKLEARN_ADAPTER_NAME
    assert result.model_name == "HistGradientBoostingRegressor"
    assert result.symbol == "AAPL"
    assert result.horizon_days == 5
    assert SUPPORTED_ADVANCED_GBDT_SKLEARN_HORIZONS[0] == 1
    assert 61 in SUPPORTED_ADVANCED_GBDT_SKLEARN_HORIZONS
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
    assert any("Boosting feature impact" in warning for warning in result.warnings)


def test_advanced_gbdt_sklearn_adapter_supports_common_forecast_horizon():
    result = AdvancedGbdtSklearnForecastAdapter().forecast(_bars(72), horizon_days=10)

    assert result.horizon_days == 10
    assert result.validation_metrics.sample_count == 62


def test_advanced_gbdt_sklearn_adapter_accepts_smaller_iteration_count():
    result = AdvancedGbdtSklearnForecastAdapter(
        max_iter=16,
        min_samples=12,
    ).forecast(_bars(72), horizon_days=5)

    assert result.adapter_name == ADVANCED_GBDT_SKLEARN_ADAPTER_NAME
    assert result.model_name == "HistGradientBoostingRegressor"
    assert result.feature_contribution_summary


def test_advanced_gbdt_sklearn_adapter_supports_horizon_above_former_limit():
    result = AdvancedGbdtSklearnForecastAdapter().forecast(_bars(180), horizon_days=75)

    assert result.horizon_days == 75


def test_advanced_gbdt_sklearn_adapter_rejects_non_positive_horizon():
    with pytest.raises(ValueError, match="horizon_days"):
        AdvancedGbdtSklearnForecastAdapter().forecast(_bars(80), horizon_days=0)


def test_advanced_gbdt_sklearn_adapter_returns_graceful_data_shortage_error():
    with pytest.raises(ValueError, match="not enough bars"):
        AdvancedGbdtSklearnForecastAdapter().forecast(_bars(20), horizon_days=10)


def test_advanced_forecast_registry_lists_gbdt_sklearn_adapter():
    spec = advanced_forecast_adapter_spec("advanced_gbdt_sklearn")

    assert "advanced_gbdt_sklearn" in advanced_forecast_adapter_keys()
    assert spec is not None
    assert spec.display_name == "高度予測: ブースティングモデル"
    assert spec.supported_horizons[0] == 1
    assert 120 in spec.supported_horizons


def _bars(count: int) -> list[Bar]:
    symbol = Symbol(raw="AAPL", exchange="NASDAQ", code="AAPL", currency="USD")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars: list[Bar] = []
    close = Decimal("100")
    for index in range(count):
        drift = Decimal("0.28")
        trend_cycle = Decimal((index % 9) - 4) / Decimal("18")
        regime = Decimal("0.18") if (index // 18) % 2 == 0 else Decimal("-0.04")
        close = close + drift + trend_cycle + regime
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
