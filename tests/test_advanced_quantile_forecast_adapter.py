from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import (
    ADVANCED_QUANTILE_ADAPTER_NAME,
    SUPPORTED_ADVANCED_QUANTILE_HORIZONS,
    AdvancedQuantileForecastAdapter,
    advanced_forecast_adapter_keys,
    advanced_forecast_adapter_spec,
)


def test_advanced_quantile_adapter_returns_forecast_range():
    result = AdvancedQuantileForecastAdapter().forecast(_bars(72), horizon_days=5)

    assert result.adapter_name == ADVANCED_QUANTILE_ADAPTER_NAME
    assert result.model_name == "HistoricalQuantile"
    assert result.symbol == "AAPL"
    assert result.horizon_days == 5
    assert SUPPORTED_ADVANCED_QUANTILE_HORIZONS[0] == 1
    assert SUPPORTED_ADVANCED_QUANTILE_HORIZONS[-1] == 60
    assert result.predicted_return_lower <= result.predicted_return <= result.predicted_return_upper
    assert result.predicted_return != Decimal("0.0000")
    assert result.validation_metrics.sample_count == 67
    assert result.validation_metrics.fold_count >= 3
    assert Decimal("0") <= result.direction_score <= Decimal("1")
    assert result.confidence in {"low", "medium", "high"}
    assert any("not investment advice" in warning for warning in result.warnings)
    assert any("not a guaranteed interval" in warning for warning in result.warnings)


def test_advanced_quantile_adapter_supports_common_forecast_horizon():
    result = AdvancedQuantileForecastAdapter().forecast(_bars(72), horizon_days=10)

    assert result.horizon_days == 10
    assert result.validation_metrics.sample_count == 62


def test_advanced_quantile_adapter_rejects_out_of_range_horizon():
    with pytest.raises(ValueError, match="horizon_days"):
        AdvancedQuantileForecastAdapter().forecast(_bars(80), horizon_days=61)


def test_advanced_forecast_registry_lists_quantile_adapter():
    spec = advanced_forecast_adapter_spec("advanced_quantile")

    assert "advanced_quantile" in advanced_forecast_adapter_keys()
    assert spec is not None
    assert spec.display_name == "高度予測: レンジモデル"
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
