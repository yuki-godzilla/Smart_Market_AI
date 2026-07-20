from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import (
    ForecastEvaluationCase,
    ForecastWeightAdjustment,
    evaluate_advanced_forecast,
    evaluate_forecast_models,
    evaluated_consensus_prediction,
    write_forecast_evaluation_artifacts,
)
from backend.forecast.evaluation import ForecastValidationPoint, _direction_accuracy


def test_evaluation_runs_real_consensus_folds_and_group_summaries():
    report = evaluate_forecast_models(
        [
            ForecastEvaluationCase(
                symbol="AAPL",
                bars=_bars("AAPL", 180, drift=Decimal("0.30")),
                market="US",
                asset_type="stock",
                regime="uptrend",
            ),
            ForecastEvaluationCase(
                symbol="1306.T",
                bars=_bars("1306.T", 180, drift=Decimal("0.08"), currency="JPY"),
                market="JP",
                asset_type="etf",
                regime="sideways",
            ),
        ],
        max_origins=2,
    )

    assert report.horizons == [20, 60]
    assert report.requested_case_count == 2
    assert report.validation_points
    assert report.predictions
    assert len(report.weight_adjustments) == 2
    overall = [row for row in report.rows if row.group_type == "overall"]
    assert len(overall) == 12
    consensus_rows = [row for row in overall if row.model_name == "forecast_consensus"]
    assert all(row.evaluation_method == "rolling_origin" for row in consensus_rows)
    assert all(row.validation_sample_count == 4 for row in consensus_rows)
    assert all(row.mean_model_disagreement is not None for row in consensus_rows)
    assert all(row.interval_sample_count == 4 for row in consensus_rows)
    assert all(row.interval_coverage is not None for row in consensus_rows)
    assert all(row.mean_interval_width is not None for row in consensus_rows)
    consensus_points = [
        point for point in report.validation_points if point.model_name == "forecast_consensus"
    ]
    assert all(point.predicted_return_lower is not None for point in consensus_points)
    assert all(point.predicted_return_upper is not None for point in consensus_points)
    assert all(point.confidence is not None for point in consensus_points)
    assert all(point.selection_policy_version for point in consensus_points)
    regime_rows = [row for row in overall if row.model_name == "advanced_regime_gated_ensemble"]
    assert all(row.evaluation_method == "rolling_origin" for row in regime_rows)
    assert all(row.validation_sample_count == 4 for row in regime_rows)
    assert all(row.mean_model_disagreement is not None for row in regime_rows)
    assert {row.group_value for row in report.rows if row.group_type == "market"} == {
        "JP",
        "US",
    }
    assert {row.group_value for row in report.rows if row.group_type == "asset_type"} == {
        "etf",
        "stock",
    }
    assert {row.group_value for row in report.rows if row.group_type == "regime"} == {
        "sideways",
        "uptrend",
    }
    assert all(Decimal("0") <= row.direction_accuracy <= Decimal("1") for row in report.rows)


def test_rolling_origin_uses_only_history_available_at_origin():
    original = _bars("AAPL", 120, drift=Decimal("0.20"))
    changed_future = [
        bar.model_copy(update={"close": bar.close * Decimal("5")}) if index >= 100 else bar
        for index, bar in enumerate(original)
    ]
    first = evaluate_forecast_models(
        [ForecastEvaluationCase(symbol="AAPL", bars=original)],
        horizons=(20,),
        adapter_names=("advanced_linear",),
        max_origins=1,
    )
    second = evaluate_forecast_models(
        [ForecastEvaluationCase(symbol="AAPL", bars=changed_future)],
        horizons=(20,),
        adapter_names=("advanced_linear",),
        max_origins=1,
    )

    first_point = next(
        point for point in first.validation_points if point.model_name == "advanced_linear"
    )
    second_point = next(
        point for point in second.validation_points if point.model_name == "advanced_linear"
    )
    assert first_point.origin_at == second_point.origin_at
    assert first_point.predicted_return == second_point.predicted_return
    assert first_point.actual_return != second_point.actual_return


def test_direction_accuracy_uses_separate_direction_head_when_available():
    origin = datetime(2025, 1, 1, tzinfo=UTC)
    point = ForecastValidationPoint(
        symbol="AAPL",
        market="US",
        asset_type="stock",
        regime="downtrend",
        model_name="forecast_consensus",
        horizon_days=20,
        origin_at=origin,
        target_at=origin + timedelta(days=20),
        predicted_return=Decimal("0.10"),
        direction_predicted_return=Decimal("-0.02"),
        actual_return=Decimal("-0.05"),
    )

    assert _direction_accuracy([point]) == Decimal("1.0000")


def test_short_history_is_recorded_as_skipped():
    report = evaluate_forecast_models(
        [
            ForecastEvaluationCase(
                symbol="AAPL",
                bars=_bars("AAPL", 70, drift=Decimal("0.20")),
            )
        ],
        horizons=(20, 60),
        adapter_names=("advanced_linear",),
        max_origins=2,
    )

    twenty_day = next(
        row
        for row in report.rows
        if row.group_type == "overall"
        and row.model_name == "advanced_linear"
        and row.horizon_days == 20
    )
    sixty_day = next(
        row
        for row in report.rows
        if row.group_type == "overall"
        and row.model_name == "advanced_linear"
        and row.horizon_days == 60
    )
    assert twenty_day.validation_sample_count > 0
    assert sixty_day.validation_sample_count == 0
    assert sixty_day.skipped_case_count == 1
    assert report.warnings


def test_weight_adjustment_gate_and_explicit_prediction():
    bars = _bars("AAPL", 140, drift=Decimal("0.25"))
    evaluations = [
        evaluate_advanced_forecast(
            bars,
            adapter_name=name,
            horizon_days=20,
        )
        for name in ("advanced_linear", "advanced_quantile")
    ]
    adopted = ForecastWeightAdjustment(
        horizon_days=20,
        model_weights={
            "advanced_linear": Decimal("0.7500"),
            "advanced_quantile": Decimal("0.2500"),
        },
        tuning_sample_count=3,
        holdout_sample_count=2,
        current_consensus_rmse=Decimal("0.1000"),
        candidate_consensus_rmse=Decimal("0.0900"),
        current_direction_accuracy=Decimal("0.5000"),
        candidate_direction_accuracy=Decimal("0.6000"),
        adopted=True,
        reason="test",
    )

    predicted = evaluated_consensus_prediction(evaluations, adopted)

    expected = (
        evaluations[0].predicted_return * Decimal("0.7500")
        + evaluations[1].predicted_return * Decimal("0.2500")
    ).quantize(Decimal("0.0001"))
    assert predicted == expected
    with pytest.raises(ValueError, match="not passed"):
        evaluated_consensus_prediction(
            evaluations,
            adopted.model_copy(update={"adopted": False}),
        )


def test_artifacts_cover_groups_predictions_errors_and_weights(tmp_path):
    report = evaluate_forecast_models(
        [
            ForecastEvaluationCase(
                symbol="AAPL",
                bars=_bars("AAPL", 120, drift=Decimal("0.25")),
                market="US",
                asset_type="stock",
                regime="uptrend",
            )
        ],
        horizons=(20,),
        adapter_names=("advanced_linear", "advanced_quantile"),
        max_origins=2,
    )

    paths = write_forecast_evaluation_artifacts(report, tmp_path)

    assert set(paths) == {
        "summary",
        "by_horizon",
        "by_market",
        "by_asset_type",
        "by_regime",
        "predictions",
        "validation_points",
        "error_cases",
        "weighting_adjustments",
    }
    assert "rolling-origin" in paths["summary"].read_text(encoding="utf-8")
    assert (
        paths["validation_points"]
        .read_text(encoding="utf-8")
        .startswith("symbol,market,asset_type,regime,model_name")
    )
    assert "group_type,group_value" in paths["by_market"].read_text(encoding="utf-8")
    assert "forecast_consensus" in paths["predictions"].read_text(encoding="utf-8")
    assert "Absolute error" in paths["error_cases"].read_text(encoding="utf-8")
    assert "holdout" in paths["weighting_adjustments"].read_text(encoding="utf-8")


def test_evaluation_rejects_invalid_options():
    with pytest.raises(ValueError, match="registered"):
        evaluate_forecast_models([], adapter_names=("missing",))
    with pytest.raises(ValueError, match="max_origins"):
        evaluate_forecast_models([], max_origins=0)


def _bars(
    raw_symbol: str,
    count: int,
    *,
    drift: Decimal,
    currency: Literal["JPY", "USD"] = "USD",
) -> list[Bar]:
    symbol = Symbol(
        raw=raw_symbol,
        exchange="NASDAQ" if currency == "USD" else "TSE",
        code=raw_symbol,
        currency=currency,
    )
    start = datetime(2025, 1, 1, tzinfo=UTC)
    close = Decimal("100")
    bars: list[Bar] = []
    for index in range(count):
        cycle = Decimal((index % 11) - 5) / Decimal("25")
        close = max(Decimal("1"), close + drift + cycle)
        bars.append(
            Bar(
                symbol=symbol,
                ts=start + timedelta(days=index),
                open=close - Decimal("0.4"),
                high=close + Decimal("0.7"),
                low=close - Decimal("0.8"),
                close=close,
                volume=Decimal(1000 + (index * 13) + ((index % 7) * 19)),
                interval="1d",
                provider="fixture",
            )
        )
    return bars
