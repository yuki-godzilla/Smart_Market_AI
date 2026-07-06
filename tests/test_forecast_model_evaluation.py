from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.forecast import (
    ForecastEvaluationCase,
    evaluate_forecast_models,
    write_forecast_evaluation_artifacts,
)


def test_evaluate_forecast_models_aggregates_twenty_and_sixty_day_metrics():
    report = evaluate_forecast_models(
        [
            ForecastEvaluationCase(
                symbol="AAPL",
                bars=_bars("AAPL", 260, drift=Decimal("0.30")),
                market="US",
                asset_type="stock",
                regime="uptrend",
            ),
            ForecastEvaluationCase(
                symbol="MSFT",
                bars=_bars("MSFT", 260, drift=Decimal("0.12")),
                market="US",
                asset_type="stock",
                regime="sideways",
            ),
        ]
    )

    assert report.horizons == [20, 60]
    assert report.requested_case_count == 2
    assert len(report.rows) == 10
    assert {row.model_name for row in report.rows} == {
        "advanced_linear",
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
        "advanced_quantile",
        "forecast_consensus",
    }
    assert all(row.evaluated_case_count == 2 for row in report.rows)
    assert all(row.validation_sample_count > 0 for row in report.rows)
    assert all(Decimal("0") <= row.direction_accuracy <= Decimal("1") for row in report.rows)
    consensus_rows = [row for row in report.rows if row.model_name == "forecast_consensus"]
    assert all(row.evaluation_method == "component_metric_proxy" for row in consensus_rows)
    assert all(row.mean_model_disagreement is not None for row in consensus_rows)
    assert all(
        row.low_confidence_count + row.medium_confidence_count + row.high_confidence_count == 2
        for row in consensus_rows
    )


def test_evaluate_forecast_models_records_short_history_as_skipped():
    report = evaluate_forecast_models(
        [
            ForecastEvaluationCase(
                symbol="AAPL",
                bars=_bars("AAPL", 90, drift=Decimal("0.20")),
            )
        ],
        horizons=(20, 60),
        adapter_names=("advanced_linear",),
    )

    twenty_day = next(
        row for row in report.rows if row.model_name == "advanced_linear" and row.horizon_days == 20
    )
    sixty_day = next(
        row for row in report.rows if row.model_name == "advanced_linear" and row.horizon_days == 60
    )
    assert twenty_day.evaluated_case_count == 1
    assert sixty_day.evaluated_case_count == 0
    assert sixty_day.skipped_case_count == 1
    assert report.warnings


def test_write_forecast_evaluation_artifacts_is_deterministic(tmp_path):
    report = evaluate_forecast_models(
        [
            ForecastEvaluationCase(
                symbol="AAPL",
                bars=_bars("AAPL", 90, drift=Decimal("0.25")),
                market="US",
                asset_type="stock",
                regime="uptrend",
            )
        ],
        horizons=(20,),
        adapter_names=("advanced_linear", "advanced_quantile"),
    )

    paths = write_forecast_evaluation_artifacts(report, tmp_path)

    assert set(paths) == {"summary", "by_horizon"}
    summary = paths["summary"].read_text(encoding="utf-8")
    csv_text = paths["by_horizon"].read_text(encoding="utf-8")
    assert "Forecast Model Evaluation Summary" in summary
    assert "advanced_linear" in summary
    assert "forecast_consensus" in summary
    assert "投資助言" in summary
    assert "model_name,evaluation_method,horizon_days" in csv_text
    assert "advanced_quantile,adapter_walk_forward,20" in csv_text


def test_evaluate_forecast_models_rejects_unknown_adapter():
    with pytest.raises(ValueError, match="registered"):
        evaluate_forecast_models([], adapter_names=("missing",))


def _bars(
    raw_symbol: str,
    count: int,
    *,
    drift: Decimal,
) -> list[Bar]:
    symbol = Symbol(
        raw=raw_symbol,
        exchange="NASDAQ",
        code=raw_symbol,
        currency="USD",
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
