from datetime import date
from decimal import Decimal

from backend.forecast.adapters import AdvancedForecastValidationMetrics
from backend.forecast.horizon import determine_forecast_horizon
from backend.forecast.model_policy import (
    AdvancedForecastModelCandidate,
    select_advanced_forecast_models,
)
from backend.forecast.service import (
    AdvancedForecastEvaluation,
    summarize_advanced_forecast_evaluations,
)


def test_acquisition_period_decision_routes_to_matching_model_band():
    short_decision = determine_forecast_horizon(
        start=date(2026, 1, 1),
        end=date(2026, 12, 31),
    )
    long_decision = determine_forecast_horizon(
        start=date(2021, 1, 1),
        end=date(2026, 12, 31),
    )

    short_selection = select_advanced_forecast_models(
        _candidates(), horizon_days=short_decision.horizon_days
    )
    long_selection = select_advanced_forecast_models(
        _candidates(), horizon_days=long_decision.horizon_days
    )

    assert short_decision.horizon_days == 20
    assert short_selection.horizon_band == "short"
    assert len(short_selection.center_adapter_names) == 3
    assert long_decision.horizon_days == 120
    assert long_selection.horizon_band == "long"
    assert long_selection.center_adapter_names == ("advanced_quantile",)


def test_short_horizon_routes_validated_center_and_preserves_direction_head():
    selection = select_advanced_forecast_models(_candidates(), horizon_days=20)

    assert selection.audit_status == "sealed_anchor"
    assert selection.selection_mode == "validated_consensus"
    assert selection.center_adapter_names == (
        "advanced_quantile",
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
    )
    assert selection.direction_adapter_names == (
        "advanced_linear",
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
        "advanced_quantile",
    )
    assert selection.center_excluded_adapter_names == ("advanced_linear",)


def test_medium_horizon_limits_center_to_one_validated_secondary():
    selection = select_advanced_forecast_models(_candidates(), horizon_days=45)

    assert selection.audit_status == "interpolated"
    assert selection.center_adapter_names == (
        "advanced_quantile",
        "advanced_tree_sklearn",
    )
    assert len(selection.direction_adapter_names) == 4
    assert set(selection.center_excluded_adapter_names) == {
        "advanced_linear",
        "advanced_gbdt_sklearn",
    }


def test_secondary_must_beat_quantile_not_only_zero_return_baseline():
    candidates = [
        _candidate("advanced_tree_sklearn", rmse="0.085", improvement="0.015"),
        _candidate("advanced_gbdt_sklearn", rmse="0.090", improvement="0.010"),
        _candidate("advanced_quantile", rmse="0.080", improvement="0.020"),
    ]

    selection = select_advanced_forecast_models(candidates, horizon_days=20)

    assert selection.selection_mode == "quantile_anchor"
    assert selection.center_adapter_names == ("advanced_quantile",)
    assert set(selection.center_excluded_adapter_names) == {
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
    }


def test_long_horizon_uses_range_first_center_and_direction_with_low_audit_status():
    selection = select_advanced_forecast_models(_candidates(), horizon_days=120)

    assert selection.audit_status == "outside_sealed_audit"
    assert selection.selection_mode == "range_first_long_horizon"
    assert selection.center_adapter_names == ("advanced_quantile",)
    assert selection.direction_adapter_names == ("advanced_quantile",)
    assert selection.selected_adapter_names == ("advanced_quantile",)
    assert set(selection.center_excluded_adapter_names) == {
        "advanced_linear",
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
    }


def test_missing_quantile_falls_back_to_best_validated_nonlinear_model():
    selection = select_advanced_forecast_models(_candidates()[:-1], horizon_days=20)

    assert selection.selection_mode == "best_available_fallback"
    assert selection.center_adapter_names == (
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
    )
    assert any("quantile anchor was unavailable" in warning for warning in selection.warnings)


def test_consensus_separates_center_return_from_audited_direction_return():
    evaluations = [
        _evaluation("advanced_linear", "-0.04"),
        _evaluation("advanced_tree_sklearn", "0.02"),
        _evaluation("advanced_gbdt_sklearn", "0.03"),
        _evaluation("advanced_quantile", "0.01"),
    ]

    consensus = summarize_advanced_forecast_evaluations(evaluations)

    assert consensus is not None
    assert consensus.model_count == 4
    assert consensus.center_model_count == 3
    assert consensus.direction_predicted_return == Decimal("0.0050")
    assert consensus.consensus_predicted_return == Decimal("0.0175")
    assert consensus.center_predicted_return_range == Decimal("0.0200")
    assert consensus.direction_predicted_return_range == Decimal("0.0700")
    assert consensus.predicted_return_range == consensus.direction_predicted_return_range
    assert consensus.model_weights["advanced_quantile"] == Decimal("0.5000")
    assert consensus.center_excluded_adapter_names == ["advanced_linear"]


def test_long_horizon_consensus_caps_confidence_and_uses_quantile_direction():
    evaluations = [
        _evaluation("advanced_linear", "-0.04", horizon_days=120),
        _evaluation("advanced_tree_sklearn", "0.02", horizon_days=120),
        _evaluation("advanced_gbdt_sklearn", "0.03", horizon_days=120),
        _evaluation("advanced_quantile", "0.01", horizon_days=120),
    ]

    consensus = summarize_advanced_forecast_evaluations(evaluations)

    assert consensus is not None
    assert consensus.model_count == 1
    assert consensus.center_model_count == 1
    assert consensus.consensus_predicted_return == Decimal("0.0100")
    assert consensus.direction_predicted_return == Decimal("0.0100")
    assert consensus.confidence == "low"
    assert consensus.center_confidence == "low"
    assert consensus.direction_confidence == "medium"
    assert consensus.confidence_policy_version == "role_separated_confidence_v1"


def _candidates() -> list[AdvancedForecastModelCandidate]:
    return [
        _candidate("advanced_linear", rmse="0.08", improvement="0.02"),
        _candidate("advanced_tree_sklearn", rmse="0.07", improvement="0.03"),
        _candidate("advanced_gbdt_sklearn", rmse="0.08", improvement="0.02"),
        _candidate("advanced_quantile", rmse="0.09", improvement="0.01"),
    ]


def _candidate(
    adapter_name: str,
    *,
    rmse: str,
    improvement: str,
) -> AdvancedForecastModelCandidate:
    return AdvancedForecastModelCandidate(
        adapter_name=adapter_name,
        rmse=Decimal(rmse),
        baseline_zero_rmse=Decimal("0.10"),
        rmse_improvement=Decimal(improvement),
        direction_accuracy=Decimal("0.60"),
        sample_count=30,
        fold_count=2,
    )


def _evaluation(
    adapter_name: str,
    predicted_return: str,
    *,
    horizon_days: int = 20,
) -> AdvancedForecastEvaluation:
    predicted = Decimal(predicted_return)
    rmse = {
        "advanced_tree_sklearn": Decimal("0.06"),
        "advanced_gbdt_sklearn": Decimal("0.07"),
    }.get(adapter_name, Decimal("0.08"))
    baseline_rmse = Decimal("0.20")
    return AdvancedForecastEvaluation(
        adapter_name=adapter_name,
        model_name=adapter_name,
        symbol="AAA",
        horizon_days=horizon_days,
        latest_close=Decimal("100"),
        forecast_close=Decimal("100") * (Decimal("1") + predicted),
        predicted_return=predicted,
        predicted_return_lower=(predicted - Decimal("0.01")),
        predicted_return_upper=(predicted + Decimal("0.01")),
        direction_score=Decimal("0.60"),
        confidence="medium",
        validation_metrics=AdvancedForecastValidationMetrics(
            mae=Decimal("0.05"),
            rmse=rmse,
            direction_accuracy=Decimal("0.60"),
            fold_count=2,
            sample_count=30,
            baseline_zero_rmse=baseline_rmse,
            rmse_improvement=baseline_rmse - rmse,
        ),
    )
