from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.forecast import (
    ConservativeCalibrationObservation,
    HorizonConservativeCalibrationProfile,
    apply_horizon_conditioned_calibration,
    build_conservative_calibration_report,
    evaluate_horizon_conditioned_calibration,
    fit_horizon_conditioned_calibration,
)


def test_fit_uses_tuning_only_and_shrinks_longer_horizon_more() -> None:
    observations = [
        *[
            _observation(
                index=index,
                horizon=20,
                consensus="0.10",
                quantile="0.04",
                moving_average="0.02",
                actual="0.10",
            )
            for index in range(12)
        ],
        *[
            _observation(
                index=index,
                horizon=60,
                consensus="0.40",
                quantile="0.20",
                moving_average="0.10",
                actual="0.10",
            )
            for index in range(12)
        ],
    ]

    profiles = fit_horizon_conditioned_calibration(observations)
    by_horizon = {profile.horizon_days: profile for profile in profiles}

    assert by_horizon[20].consensus_weight == Decimal("1")
    assert by_horizon[60].consensus_weight == Decimal("0")
    assert by_horizon[60].conservative_model_name == "moving_average_3"
    assert by_horizon[60].consensus_weight <= by_horizon[20].consensus_weight

    with pytest.raises(ValueError, match="tuning observations only"):
        fit_horizon_conditioned_calibration(
            [observations[0].model_copy(update={"split": "validation"})]
        )


def test_prediction_separates_price_center_from_retained_direction() -> None:
    observation = _observation(
        index=0,
        horizon=20,
        consensus="0.08",
        quantile="-0.03",
        moving_average="-0.02",
        actual="-0.01",
        split="validation",
    )
    profile = _profile(horizon=20, consensus_weight="0", conservative_model="moving_average_3")

    prediction = apply_horizon_conditioned_calibration(observation, profile)

    assert prediction.price_center_return == Decimal("-0.0200")
    assert prediction.direction_return == Decimal("0.08")
    assert prediction.original_consensus_return == Decimal("0.08")
    assert prediction.price_center_return != prediction.direction_return


def test_validation_and_audit_gate_uses_fixed_profile_and_paired_metrics() -> None:
    profile = _profile(horizon=20, consensus_weight="0", conservative_model="moving_average_3")
    observations = [
        _observation(
            index=index,
            horizon=20,
            consensus="0.20",
            quantile="0.12",
            moving_average="0.10",
            actual="0.10",
            split=split,
        )
        for split in ("validation", "audit")
        for index in range(12)
    ]

    metrics = evaluate_horizon_conditioned_calibration(observations, [profile])
    report = build_conservative_calibration_report([profile], metrics)
    overall = [metric for metric in metrics if metric.group_type == "overall"]

    assert report.runtime_review_eligible is True
    assert len(overall) == 2
    assert all(metric.relative_rmse_improvement == Decimal("1.000000") for metric in overall)
    assert all(
        metric.retained_direction_accuracy == metric.consensus_direction_accuracy
        for metric in overall
    )


def test_subgroup_major_regression_blocks_runtime_review() -> None:
    profile = _profile(horizon=20, consensus_weight="0", conservative_model="moving_average_3")
    observations: list[ConservativeCalibrationObservation] = []
    for split in ("validation", "audit"):
        observations.extend(
            _observation(
                index=index,
                horizon=20,
                consensus="0.20",
                quantile="0.12",
                moving_average="0.10",
                actual="0.10",
                split=split,
                market="us",
            )
            for index in range(20)
        )
        observations.extend(
            _observation(
                index=100 + index,
                horizon=20,
                consensus="0.10",
                quantile="0.12",
                moving_average="0.20",
                actual="0.10",
                split=split,
                market="jp",
            )
            for index in range(10)
        )

    metrics = evaluate_horizon_conditioned_calibration(observations, [profile])
    report = build_conservative_calibration_report([profile], metrics)

    assert report.runtime_review_eligible is False
    assert any("market=jp" in reason for reason in report.gate_reasons)


def _observation(
    *,
    index: int,
    horizon: int,
    consensus: str,
    quantile: str,
    moving_average: str,
    actual: str,
    split: str = "tuning",
    market: str = "us",
) -> ConservativeCalibrationObservation:
    origin = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=index)
    return ConservativeCalibrationObservation(
        cohort="fixture",
        split=split,
        symbol=f"SYM{index:03d}",
        market=market,
        asset_type="stock",
        regime="range_bound",
        horizon_days=horizon,
        origin_at=origin,
        target_at=origin + timedelta(days=horizon),
        consensus_return=Decimal(consensus),
        actual_return=Decimal(actual),
        conservative_returns={
            "advanced_quantile": Decimal(quantile),
            "moving_average_3": Decimal(moving_average),
        },
    )


def _profile(
    *,
    horizon: int,
    consensus_weight: str,
    conservative_model: str,
) -> HorizonConservativeCalibrationProfile:
    weight = Decimal(consensus_weight)
    return HorizonConservativeCalibrationProfile(
        horizon_days=horizon,
        conservative_model_name=conservative_model,
        consensus_weight=weight,
        conservative_weight=Decimal("1") - weight,
        tuning_sample_count=10,
        tuning_consensus_rmse=Decimal("0.10"),
        tuning_conservative_rmse=Decimal("0.05"),
        tuning_candidate_rmse=Decimal("0.05"),
        tuning_relative_rmse_improvement=Decimal("0.50"),
        tuning_consensus_direction_accuracy=Decimal("0.60"),
        tuning_candidate_center_direction_accuracy=Decimal("0.55"),
        tuning_retained_direction_accuracy=Decimal("0.60"),
    )
