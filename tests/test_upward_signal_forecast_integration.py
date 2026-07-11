from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.forecast.evaluation import ForecastValidationPoint
from backend.forecast.service import AdvancedForecastConsensus
from backend.scoring.upward_signal_forecast_integration import (
    calculate_forecast_integration,
    evaluate_forecast_validation_points,
    evaluate_upward_signal_forecast_case,
    write_upward_signal_forecast_outputs,
)


def _row() -> dict[str, str]:
    return {
        "drawdown_20d": "-8",
        "momentum_5d": "-1",
        "forecast_return_pct": "6",
        "up_model_count": "3",
        "down_model_count": "1",
        "upside_signal_score": "70",
        "downside_signal_score": "40",
        "risk_signal_score": "70",
        "data_quality_score": "85",
    }


def test_forecast_integration_uses_quantile_downside_and_low_confidence_ceiling():
    consensus = AdvancedForecastConsensus(
        symbol="AAA",
        horizon_days=20,
        model_count=4,
        consensus_predicted_return=Decimal("0.08"),
        consensus_forecast_close=Decimal("108"),
        median_predicted_return=Decimal("0.08"),
        min_predicted_return=Decimal("0.02"),
        max_predicted_return=Decimal("0.14"),
        predicted_return_range=Decimal("0.12"),
        predicted_return_lower=Decimal("-0.04"),
        predicted_return_upper=Decimal("0.16"),
        agreement="wide",
        confidence="low",
        direction_agreement_score=Decimal("50"),
        weighted_direction_score=Decimal("0.55"),
        mean_direction_accuracy=Decimal("0.60"),
        mean_rmse=Decimal("0.10"),
    )

    result = calculate_forecast_integration(_row(), consensus)

    assert result.forecast_upside_score == Decimal("70.00")
    assert result.downside_safety_score == Decimal("40.00")
    assert result.score_ceiling == Decimal("65")
    assert result.forecast_integration_score <= result.score_ceiling
    assert "forecast_confidence:low" in result.warnings
    assert "model_disagreement:high" in result.warnings
    assert "quantile_downside:negative" in result.warnings


def test_case_and_artifacts_are_evaluation_only(tmp_path):
    consensus = {
        "consensus_predicted_return": "0.06",
        "predicted_return_lower": "0.01",
        "predicted_return_upper": "0.10",
        "predicted_return_range": "0.09",
        "direction_agreement_score": "75",
        "confidence": "high",
        "model_count": 4,
        "up_model_count": 3,
        "down_model_count": 1,
        "flat_model_count": 0,
    }
    case = evaluate_upward_signal_forecast_case("AAA", _row(), consensus)
    integration = calculate_forecast_integration(_row(), consensus)
    paths = write_upward_signal_forecast_outputs([case], {"AAA": integration}, tmp_path)

    assert case.symbol == "AAA"
    assert paths["cases"].read_text(encoding="utf-8-sig").startswith("symbol,")
    summary = paths["integration"].read_text(encoding="utf-8")
    assert "通常Rankingの順位・runtime weightは変更していません" in summary
    assert "confidence" in paths["confidence"].read_text(encoding="utf-8")


def test_validation_points_reconstruct_consensus_evidence_without_using_actual_return():
    origin = datetime(2025, 1, 1, tzinfo=UTC)
    points = [
        ForecastValidationPoint(
            symbol="AAA",
            market="US",
            asset_type="stock",
            regime="uptrend",
            model_name=model,
            horizon_days=20,
            origin_at=origin,
            target_at=origin + timedelta(days=20),
            predicted_return=predicted,
            actual_return=actual,
        )
        for model, predicted, actual in (
            ("advanced_linear", Decimal("0.06"), Decimal("0.20")),
            ("advanced_tree_sklearn", Decimal("0.05"), Decimal("0.20")),
            ("advanced_quantile", Decimal("0.04"), Decimal("0.20")),
            ("forecast_consensus", Decimal("0.05"), Decimal("0.20")),
        )
    ]

    first = evaluate_forecast_validation_points(points)
    changed_actual = [
        point.model_copy(update={"actual_return": Decimal("-0.20")}) for point in points
    ]
    second = evaluate_forecast_validation_points(changed_actual)

    assert len(first) == 1
    assert first[0].confidence == "high"
    assert first[0].direction_agreement_score == Decimal("100.00")
    assert first[0].forecast_integration_score == second[0].forecast_integration_score
    assert first[0].actual_return == Decimal("0.20")
    assert second[0].actual_return == Decimal("-0.20")
