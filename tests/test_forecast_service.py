from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import (
    MomentumForecastModel,
    MovingAverageForecastModel,
    NaiveForecastModel,
    evaluate_models,
    summarize_forecast_evaluations,
)


def test_evaluate_models_returns_baseline_metrics():
    bars = _bars([100, 102, 104, 103, 106, 108])

    evaluations = evaluate_models(
        bars,
        models=[
            NaiveForecastModel(),
            MovingAverageForecastModel(window=3),
            MomentumForecastModel(lookback=3),
        ],
    )

    assert [row.model_name for row in evaluations] == [
        "naive",
        "moving_average_3",
        "momentum_3",
    ]
    assert evaluations[0].latest_forecast.forecast_close == Decimal("108.0000")
    assert evaluations[0].metrics.sample_count == 5
    assert evaluations[0].metrics.mae == Decimal("2.0000")
    assert evaluations[0].metrics.rmse == Decimal("2.0976")
    assert evaluations[0].metrics.direction_accuracy == Decimal("0.0000")
    assert evaluations[1].metrics.sample_count == 3
    assert evaluations[2].metrics.sample_count == 2


def test_evaluate_models_uses_horizon_days_for_walk_forward_target():
    bars = _bars([100, 102, 104, 103, 106, 108])

    evaluations = evaluate_models(
        bars,
        models=[
            NaiveForecastModel(),
            MovingAverageForecastModel(window=3),
            MomentumForecastModel(lookback=3),
        ],
        horizon_days=2,
    )

    assert evaluations[0].latest_forecast.horizon_days == 2
    assert evaluations[0].metrics.sample_count == 4
    assert evaluations[0].metrics.mae == Decimal("3.0000")
    assert evaluations[0].metrics.rmse == Decimal("3.3912")
    assert evaluations[1].metrics.sample_count == 2
    assert evaluations[2].metrics.sample_count == 1


def test_summarize_forecast_evaluations_returns_model_agreement():
    evaluations = evaluate_models(
        _bars([100, 102, 104, 103, 106, 108]),
        models=[
            NaiveForecastModel(),
            MovingAverageForecastModel(window=3),
            MomentumForecastModel(lookback=3),
        ],
    )

    consensus = summarize_forecast_evaluations(evaluations)

    assert consensus is not None
    assert consensus.symbol == "AAPL"
    assert consensus.horizon_days == 1
    assert consensus.model_count == 3
    assert consensus.median_forecast_close == Decimal("108.0000")
    assert consensus.min_forecast_close == Decimal("105.6667")
    assert consensus.max_forecast_close == Decimal("109.3846")
    assert consensus.forecast_range == Decimal("3.7179")
    assert consensus.forecast_range_pct == Decimal("0.0344")
    assert consensus.agreement == "LOW"


def test_moving_average_predict_uses_trailing_window():
    forecast = MovingAverageForecastModel(window=3).predict(_bars([100, 110, 120]))

    assert forecast.model_name == "moving_average_3"
    assert forecast.forecast_close == Decimal("110.0000")


def test_momentum_predict_extends_recent_return():
    forecast = MomentumForecastModel(lookback=2).predict(_bars([100, 110, 121]))

    assert forecast.model_name == "momentum_2"
    assert forecast.forecast_close == Decimal("133.7050")


def test_forecast_model_rejects_too_short_history():
    with pytest.raises(ValueError, match="moving_average_3 requires at least 3 bars"):
        MovingAverageForecastModel(window=3).predict(_bars([100, 101]))


def _bars(closes: list[int]) -> list[Bar]:
    symbol = Symbol(raw="AAPL", exchange="NASDAQ", code="AAPL", currency="USD")
    start = datetime(2026, 5, 1, tzinfo=UTC)
    return [
        Bar(
            symbol=symbol,
            ts=start + timedelta(days=index),
            open=Decimal(str(close)),
            high=Decimal(str(close + 1)),
            low=Decimal(str(close - 1)),
            close=Decimal(str(close)),
            volume=Decimal("1000"),
            interval="1d",
            provider="test",
        )
        for index, close in enumerate(closes)
    ]
