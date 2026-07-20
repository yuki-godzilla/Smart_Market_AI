from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.forecast import (
    ConservativeCalibrationObservation,
    HorizonConservativeCalibrationProfile,
    build_cross_sectional_residual_report,
    evaluate_cross_sectional_residual_metrics,
    evaluate_point_in_time_cross_sectional_residual,
)

UTC = timezone.utc


def test_cross_sectional_tree_improves_stable_nonlinear_residual_pattern() -> None:
    profile = _profile()
    history = _observations(origin_count=10, split="development")
    evaluation = _observations(
        origin_count=2,
        split="audit",
        start=datetime(2023, 1, 1, tzinfo=UTC),
    )

    predictions = evaluate_point_in_time_cross_sectional_residual(
        history,
        evaluation,
        [profile],
        min_samples_leaf=5,
    )
    metrics = evaluate_cross_sectional_residual_metrics(evaluation, predictions)
    report = build_cross_sectional_residual_report(
        metrics,
        predictions,
        required_splits=("audit",),
    )

    assert len(predictions) == 40
    assert all(item.decision.status == "selected" for item in predictions)
    assert all(item.direction_return == item.original_consensus_return for item in predictions)
    overall = next(item for item in metrics if item.group_type == "overall")
    assert overall.candidate_rmse < overall.anchor_rmse
    assert overall.candidate_rmse < overall.consensus_rmse
    assert report.runtime_review_eligible is True


def test_unmatured_history_cannot_change_origin_decision() -> None:
    profile = _profile()
    history = _observations(origin_count=10, split="development")
    evaluation = _observations(
        origin_count=1,
        split="audit",
        start=datetime(2023, 1, 1, tzinfo=UTC),
    )
    future = history[0].model_copy(
        update={
            "symbol": "FUTURE",
            "origin_at": evaluation[0].origin_at - timedelta(days=1),
            "target_at": evaluation[0].origin_at + timedelta(days=20),
            "actual_return": Decimal("9"),
        }
    )

    baseline = evaluate_point_in_time_cross_sectional_residual(
        history,
        evaluation,
        [profile],
        min_samples_leaf=5,
    )
    with_future = evaluate_point_in_time_cross_sectional_residual(
        [*history, future],
        evaluation,
        [profile],
        min_samples_leaf=5,
    )

    assert [item.price_center_return for item in with_future] == [
        item.price_center_return for item in baseline
    ]
    assert with_future[0].decision.available_sample_count == len(history)


def test_small_prediction_cross_section_falls_back_to_anchor() -> None:
    profile = _profile()
    history = _observations(origin_count=10, split="development")
    evaluation = _observations(
        origin_count=1,
        symbol_count=1,
        split="audit",
        start=datetime(2023, 1, 1, tzinfo=UTC),
    )

    predictions = evaluate_point_in_time_cross_sectional_residual(
        history,
        evaluation,
        [profile],
        min_samples_leaf=5,
    )

    assert len(predictions) == 1
    assert predictions[0].decision.status == "fallback"
    assert predictions[0].decision.reason == "insufficient_prediction_cross_section"
    assert predictions[0].price_center_return == predictions[0].anchor_return


def test_cross_sectional_evaluation_rejects_naive_timestamps() -> None:
    profile = _profile()
    history = _observations(origin_count=10, split="development")
    evaluation = _observations(origin_count=1, split="audit")
    evaluation[0] = evaluation[0].model_copy(update={"origin_at": datetime(2023, 1, 1)})

    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_point_in_time_cross_sectional_residual(
            history,
            evaluation,
            [profile],
            min_samples_leaf=5,
        )


def _profile() -> HorizonConservativeCalibrationProfile:
    return HorizonConservativeCalibrationProfile(
        horizon_days=20,
        conservative_model_name="moving_average_3",
        consensus_weight=Decimal("0"),
        conservative_weight=Decimal("1"),
        tuning_sample_count=100,
        tuning_consensus_rmse=Decimal("0.1"),
        tuning_conservative_rmse=Decimal("0.1"),
        tuning_candidate_rmse=Decimal("0.1"),
        tuning_relative_rmse_improvement=Decimal("0"),
        tuning_consensus_direction_accuracy=Decimal("0.5"),
        tuning_candidate_center_direction_accuracy=Decimal("0.5"),
        tuning_retained_direction_accuracy=Decimal("0.5"),
    )


def _observations(
    *,
    origin_count: int,
    split: str,
    symbol_count: int = 20,
    start: datetime = datetime(2020, 1, 1, tzinfo=UTC),
) -> list[ConservativeCalibrationObservation]:
    observations: list[ConservativeCalibrationObservation] = []
    for origin_index in range(origin_count):
        origin_at = start + timedelta(days=origin_index * 60)
        for symbol_index in range(symbol_count):
            anchor = Decimal("-0.05") + Decimal(symbol_index) * Decimal("0.005")
            residual = Decimal("0.06") if symbol_index >= symbol_count // 2 else Decimal("-0.06")
            quantile = anchor + (Decimal("0.01") if residual > 0 else Decimal("-0.01"))
            observations.append(
                ConservativeCalibrationObservation(
                    cohort="synthetic_cross_section",
                    split=split,
                    symbol=f"S{symbol_index:03d}",
                    market="jp",
                    asset_type="stock",
                    regime="sideways",
                    horizon_days=20,
                    origin_at=origin_at,
                    target_at=origin_at + timedelta(days=20),
                    consensus_return=anchor,
                    actual_return=anchor + residual,
                    conservative_returns={
                        "advanced_quantile": quantile,
                        "moving_average_3": anchor,
                    },
                )
            )
    return observations
