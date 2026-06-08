from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import (
    MomentumForecastModel,
    MovingAverageForecastModel,
    NaiveForecastModel,
    calculate_direction_net_score,
    calculate_downside_signal_score,
    calculate_model_forecast_strength_score,
    calculate_momentum_edge_score,
    calculate_trend_confirmation_score,
    calculate_upside_signal_score,
    direction_confidence_factor,
    direction_signal_label,
    edge_to_down_score,
    edge_to_up_score,
    evaluate_advanced_forecast,
    evaluate_advanced_linear_forecast,
    evaluate_models,
    forecast_model_signal_weight,
    safe_signal_volatility,
    summarize_forecast_evaluations,
    volatility_adjusted_edge,
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


def test_evaluate_advanced_linear_forecast_returns_api_ready_close():
    bars = _bars(list(range(100, 172)))

    evaluation = evaluate_advanced_linear_forecast(bars, horizon_days=5)

    assert evaluation.adapter_name == "advanced_linear"
    assert evaluation.model_name == "Ridge"
    assert evaluation.symbol == "AAPL"
    assert evaluation.horizon_days == 5
    assert evaluation.latest_close == Decimal("171.0000")
    assert evaluation.forecast_close >= Decimal("0")
    assert evaluation.validation_metrics.sample_count == 67
    assert evaluation.feature_contribution_summary


def test_evaluate_advanced_forecast_returns_quantile_range():
    bars = _bars(list(range(100, 172)))

    evaluation = evaluate_advanced_forecast(
        bars,
        adapter_name="advanced_quantile",
        horizon_days=5,
    )

    assert evaluation.adapter_name == "advanced_quantile"
    assert evaluation.model_name == "HistoricalQuantile"
    assert evaluation.symbol == "AAPL"
    assert evaluation.horizon_days == 5
    assert evaluation.latest_close == Decimal("171.0000")
    assert evaluation.forecast_close >= Decimal("0")
    assert evaluation.forecast_close_lower is not None
    assert evaluation.forecast_close_upper is not None
    assert (
        evaluation.forecast_close_lower
        <= evaluation.forecast_close
        <= evaluation.forecast_close_upper
    )
    assert evaluation.predicted_return_lower is not None
    assert evaluation.predicted_return_upper is not None
    assert evaluation.validation_metrics.sample_count == 67


def test_evaluate_advanced_forecast_returns_tree_sklearn_adapter():
    bars = _bars(list(range(100, 172)))

    evaluation = evaluate_advanced_forecast(
        bars,
        adapter_name="advanced_tree_sklearn",
        horizon_days=5,
    )

    assert evaluation.adapter_name == "advanced_tree_sklearn"
    assert evaluation.model_name == "ExtraTreesRegressor"
    assert evaluation.symbol == "AAPL"
    assert evaluation.horizon_days == 5
    assert evaluation.latest_close == Decimal("171.0000")
    assert evaluation.forecast_close >= Decimal("0")
    assert evaluation.validation_metrics.sample_count == 67
    assert evaluation.feature_contribution_summary


def test_evaluate_advanced_forecast_returns_gbdt_sklearn_adapter():
    bars = _bars(list(range(100, 172)))

    evaluation = evaluate_advanced_forecast(
        bars,
        adapter_name="advanced_gbdt_sklearn",
        horizon_days=5,
    )

    assert evaluation.adapter_name == "advanced_gbdt_sklearn"
    assert evaluation.model_name == "HistGradientBoostingRegressor"
    assert evaluation.symbol == "AAPL"
    assert evaluation.horizon_days == 5
    assert evaluation.latest_close == Decimal("171.0000")
    assert evaluation.forecast_close >= Decimal("0")
    assert evaluation.validation_metrics.sample_count == 67
    assert evaluation.feature_contribution_summary


def test_evaluate_advanced_forecast_supports_common_horizon():
    bars = _bars(list(range(100, 172)))

    evaluation = evaluate_advanced_forecast(
        bars,
        adapter_name="advanced_quantile",
        horizon_days=10,
    )

    assert evaluation.horizon_days == 10
    assert evaluation.validation_metrics.sample_count == 62
    assert evaluation.forecast_close_lower is not None
    assert evaluation.forecast_close_upper is not None


def test_summarize_forecast_evaluations_returns_model_agreement():
    evaluations = evaluate_models(
        _bars([100, 102, 104, 103, 106, 108]),
        models=[
            NaiveForecastModel(),
            MovingAverageForecastModel(window=3),
            MomentumForecastModel(lookback=3),
        ],
    )

    bars = _bars([100, 102, 104, 103, 106, 108])
    consensus = summarize_forecast_evaluations(evaluations, history=bars)

    assert consensus is not None
    assert consensus.symbol == "AAPL"
    assert consensus.horizon_days == 1
    assert consensus.model_count == 3
    assert consensus.ensemble_forecast_close == Decimal("107.6838")
    assert consensus.median_forecast_close == Decimal("108.0000")
    assert consensus.min_forecast_close == Decimal("105.6667")
    assert consensus.max_forecast_close == Decimal("109.3846")
    assert consensus.forecast_range == Decimal("3.7179")
    assert consensus.forecast_range_pct == Decimal("0.0344")
    assert consensus.agreement == "LOW"
    assert consensus.latest_close == Decimal("108.0000")
    assert consensus.forecast_return_pct == Decimal("-0.0029")
    assert consensus.up_model_count == 1
    assert consensus.down_model_count == 1
    assert consensus.flat_model_count == 1
    assert consensus.direction_signal_label == "NEUTRAL"
    assert Decimal("0") <= consensus.direction_net_score <= Decimal("100")


def test_upside_signal_score_rewards_upside_direction_and_momentum():
    score = calculate_upside_signal_score(
        latest_close=Decimal("100"),
        ensemble_forecast_close=Decimal("106"),
        model_forecast_closes=[Decimal("105"), Decimal("106"), Decimal("107")],
        model_forecast_weights=[Decimal("1"), Decimal("1"), Decimal("1")],
        momentum_5d=Decimal("0.02"),
        momentum_20d=Decimal("0.04"),
        forecast_range_pct=Decimal("0.012"),
    )

    assert score >= Decimal("70")


def test_upside_signal_score_stays_limited_for_extreme_single_model_spread():
    score = calculate_upside_signal_score(
        latest_close=Decimal("100"),
        ensemble_forecast_close=Decimal("104"),
        model_forecast_closes=[Decimal("100"), Decimal("100"), Decimal("112")],
        model_forecast_weights=[Decimal("1"), Decimal("1"), Decimal("1")],
        momentum_5d=Decimal("0.01"),
        momentum_20d=Decimal("-0.01"),
        forecast_range_pct=Decimal("0.10"),
    )

    assert score < Decimal("75")


def test_direction_score_uses_agreement_as_neutral_confidence_not_bonus():
    tight_score = calculate_upside_signal_score(
        latest_close=Decimal("100"),
        ensemble_forecast_close=Decimal("106"),
        model_forecast_closes=[Decimal("105"), Decimal("106"), Decimal("107")],
        model_forecast_weights=[Decimal("1"), Decimal("1"), Decimal("1")],
        momentum_5d=Decimal("0.02"),
        momentum_20d=Decimal("0.04"),
        forecast_range_pct=Decimal("0.005"),
    )
    wide_score = calculate_upside_signal_score(
        latest_close=Decimal("100"),
        ensemble_forecast_close=Decimal("106"),
        model_forecast_closes=[Decimal("105"), Decimal("106"), Decimal("107")],
        model_forecast_weights=[Decimal("1"), Decimal("1"), Decimal("1")],
        momentum_5d=Decimal("0.02"),
        momentum_20d=Decimal("0.04"),
        forecast_range_pct=Decimal("0.10"),
    )

    assert Decimal("50") < wide_score < tight_score


def test_downside_signal_score_rewards_decline_direction_and_momentum():
    score = calculate_downside_signal_score(
        latest_close=Decimal("100"),
        ensemble_forecast_close=Decimal("94"),
        model_forecast_closes=[Decimal("93"), Decimal("94"), Decimal("96")],
        model_forecast_weights=[Decimal("1"), Decimal("1"), Decimal("1")],
        momentum_5d=Decimal("-0.02"),
        momentum_20d=Decimal("-0.04"),
        forecast_range_pct=Decimal("0.012"),
    )

    assert score >= Decimal("70")


def test_downside_signal_score_stays_limited_for_extreme_single_model_spread():
    score = calculate_downside_signal_score(
        latest_close=Decimal("100"),
        ensemble_forecast_close=Decimal("96"),
        model_forecast_closes=[Decimal("100"), Decimal("100"), Decimal("88")],
        model_forecast_weights=[Decimal("1"), Decimal("1"), Decimal("1")],
        momentum_5d=Decimal("-0.01"),
        momentum_20d=Decimal("0.01"),
        forecast_range_pct=Decimal("0.10"),
    )

    assert score < Decimal("75")


def test_model_forecast_strength_scores_model_return_size_and_weight():
    weak_upside = calculate_upside_signal_score(
        latest_close=Decimal("100"),
        ensemble_forecast_close=Decimal("106"),
        model_forecast_closes=[Decimal("100"), Decimal("100"), Decimal("104")],
        model_forecast_weights=[Decimal("1"), Decimal("1"), Decimal("1")],
        momentum_5d=Decimal("0.01"),
        momentum_20d=Decimal("0.02"),
        forecast_range_pct=Decimal("0.02"),
    )
    strong_upside = calculate_upside_signal_score(
        latest_close=Decimal("100"),
        ensemble_forecast_close=Decimal("106"),
        model_forecast_closes=[Decimal("100"), Decimal("100"), Decimal("118")],
        model_forecast_weights=[Decimal("1"), Decimal("1"), Decimal("1")],
        momentum_5d=Decimal("0.01"),
        momentum_20d=Decimal("0.02"),
        forecast_range_pct=Decimal("0.02"),
    )

    assert strong_upside > weak_upside

    lower_weighted = calculate_model_forecast_strength_score(
        latest_close=Decimal("100"),
        model_forecast_closes=[Decimal("100"), Decimal("120")],
        model_forecast_weights=[Decimal("2"), Decimal("1")],
        side="upside",
    )
    higher_weighted = calculate_model_forecast_strength_score(
        latest_close=Decimal("100"),
        model_forecast_closes=[Decimal("100"), Decimal("120")],
        model_forecast_weights=[Decimal("1"), Decimal("2")],
        side="upside",
    )

    assert higher_weighted > lower_weighted


def test_forecast_edge_scores_are_volatility_adjusted_and_bounded():
    low_vol_edge = volatility_adjusted_edge(Decimal("0.03"), Decimal("0.02"))
    high_vol_edge = volatility_adjusted_edge(Decimal("0.03"), Decimal("0.10"))

    assert low_vol_edge > high_vol_edge
    assert edge_to_up_score(low_vol_edge) > edge_to_up_score(high_vol_edge)
    assert edge_to_down_score(Decimal("-1.5")) > edge_to_down_score(Decimal("-0.3"))
    assert safe_signal_volatility(None) == Decimal("0.02")
    assert safe_signal_volatility(Decimal("0")) == Decimal("0.02")
    assert edge_to_up_score(Decimal("99")) <= Decimal("100")
    assert edge_to_down_score(Decimal("-99")) <= Decimal("100")


def test_momentum_edge_score_is_continuous_and_missing_data_is_neutral():
    upside = calculate_momentum_edge_score(
        momentum_5d=Decimal("0.02"),
        momentum_20d=Decimal("0.04"),
        volatility_20d=Decimal("0.02"),
        volatility_60d=Decimal("0.04"),
        side="upside",
    )
    downside = calculate_momentum_edge_score(
        momentum_5d=Decimal("-0.02"),
        momentum_20d=Decimal("-0.04"),
        volatility_20d=Decimal("0.02"),
        volatility_60d=Decimal("0.04"),
        side="downside",
    )
    neutral = calculate_momentum_edge_score(
        momentum_5d=None,
        momentum_20d=None,
        side="upside",
    )

    assert upside > Decimal("50")
    assert downside > Decimal("50")
    assert neutral == Decimal("50.00")


def test_trend_confirmation_score_counts_ma_conditions_and_handles_missing_data():
    assert calculate_trend_confirmation_score(
        latest_close=Decimal("110"),
        ma5=Decimal("108"),
        ma20=Decimal("100"),
        ma20_slope=Decimal("1"),
        side="upside",
    ) == Decimal("100")
    assert calculate_trend_confirmation_score(
        latest_close=Decimal("90"),
        ma5=Decimal("95"),
        ma20=Decimal("100"),
        ma20_slope=Decimal("-1"),
        side="downside",
    ) == Decimal("100")
    assert calculate_trend_confirmation_score(
        latest_close=None,
        ma5=Decimal("95"),
        ma20=Decimal("100"),
        ma20_slope=Decimal("-1"),
        side="downside",
    ) == Decimal("50")


def test_direction_confidence_factor_keeps_wide_spread_from_over_neutralizing():
    assert direction_confidence_factor(Decimal("0.005")) == Decimal("1")
    assert direction_confidence_factor(Decimal("0.10")) == Decimal("0.70")


def test_forecast_model_signal_weight_blends_accuracy_with_sample_count():
    evaluations = evaluate_models(
        _bars([100, 102, 104, 103, 106, 108]),
        models=[NaiveForecastModel()],
    )

    assert Decimal("0.80") <= forecast_model_signal_weight(evaluations[0]) <= Decimal("1.20")


def test_direction_signal_label_and_net_score_classify_upside_downside_and_unknown():
    assert (
        direction_signal_label(
            upside_signal_score=Decimal("85"),
            downside_signal_score=Decimal("40"),
            data_is_insufficient=False,
        )
        == "STRONG_UPSIDE"
    )
    assert (
        direction_signal_label(
            upside_signal_score=Decimal("40"),
            downside_signal_score=Decimal("85"),
            data_is_insufficient=False,
        )
        == "STRONG_DOWNSIDE"
    )
    assert (
        direction_signal_label(
            upside_signal_score=Decimal("58"),
            downside_signal_score=Decimal("55"),
            data_is_insufficient=False,
        )
        == "NEUTRAL"
    )
    assert (
        direction_signal_label(
            upside_signal_score=Decimal("50"),
            downside_signal_score=Decimal("50"),
            data_is_insufficient=True,
        )
        == "UNKNOWN"
    )
    assert calculate_direction_net_score(
        upside_signal_score=Decimal("80"),
        downside_signal_score=Decimal("30"),
    ) == Decimal("75.00")
    assert calculate_direction_net_score(
        upside_signal_score=Decimal("40"),
        downside_signal_score=Decimal("80"),
    ) == Decimal("30.00")
    assert calculate_direction_net_score(
        upside_signal_score=Decimal("200"),
        downside_signal_score=Decimal("0"),
    ) == Decimal("100.00")


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
