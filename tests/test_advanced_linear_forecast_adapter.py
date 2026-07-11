from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import (
    ADVANCED_LINEAR_ADAPTER_NAME,
    ADVANCED_LINEAR_CLIP_VERSION,
    SUPPORTED_ADVANCED_LINEAR_HORIZONS,
    AdvancedLinearForecastAdapter,
    NaiveForecastModel,
    evaluate_models,
)


def test_advanced_linear_adapter_predicts_forward_return_for_supported_horizon():
    adapter = AdvancedLinearForecastAdapter()

    result = adapter.forecast(_bars(72), horizon_days=5)

    assert result.adapter_name == ADVANCED_LINEAR_ADAPTER_NAME
    assert result.model_name == "Ridge"
    assert result.symbol == "AAPL"
    assert result.horizon_days == 5
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


def test_advanced_linear_adapter_supports_twenty_day_forward_return():
    result = AdvancedLinearForecastAdapter().forecast(_bars(80), horizon_days=20)

    assert SUPPORTED_ADVANCED_LINEAR_HORIZONS[0] == 1
    assert SUPPORTED_ADVANCED_LINEAR_HORIZONS[-1] == 60
    assert result.horizon_days == 20
    assert result.validation_metrics.sample_count == 60
    assert result.predicted_return != Decimal("0.0000")


def test_advanced_linear_adapter_supports_common_forecast_horizon():
    result = AdvancedLinearForecastAdapter().forecast(_bars(72), horizon_days=10)

    assert result.horizon_days == 10
    assert result.validation_metrics.sample_count == 62


def test_advanced_linear_adapter_rejects_out_of_range_horizon():
    with pytest.raises(ValueError, match="horizon_days"):
        AdvancedLinearForecastAdapter().forecast(_bars(80), horizon_days=61)


def test_advanced_linear_adapter_returns_graceful_data_shortage_error():
    with pytest.raises(ValueError, match="not enough bars"):
        AdvancedLinearForecastAdapter().forecast(_bars(12), horizon_days=20)


def test_advanced_linear_adapter_tolerates_missing_like_feature_windows():
    bars = _bars(28)

    result = AdvancedLinearForecastAdapter(min_samples=8).forecast(bars, horizon_days=5)

    assert result.validation_metrics.sample_count == 23
    assert result.feature_contribution_summary


def test_advanced_linear_adapter_clips_unstable_extrapolation():
    bars = _bars(120)
    bars[-1] = bars[-1].model_copy(
        update={
            "close": bars[-1].close * Decimal("8"),
            "high": bars[-1].high * Decimal("8"),
            "open": bars[-1].open * Decimal("8"),
            "low": bars[-1].low * Decimal("8"),
        }
    )

    result = AdvancedLinearForecastAdapter().forecast(bars, horizon_days=20)

    assert Decimal("-0.75") <= result.predicted_return <= Decimal("0.75")
    assert ADVANCED_LINEAR_CLIP_VERSION == "robust-linear-clip-v1"


def test_advanced_linear_adapter_keeps_default_baseline_forecast_path_unchanged():
    bars = _bars(24)

    evaluations = evaluate_models(bars, models=[NaiveForecastModel()], horizon_days=5)

    assert evaluations[0].model_name == "naive"
    assert evaluations[0].latest_forecast.horizon_days == 5
    assert evaluations[0].metrics.sample_count == 19


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
