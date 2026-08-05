from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

import pytest

from backend.forecast import (
    CONSENSUS_MODEL_NAME,
    AdaptiveCalibrationWeightDecision,
    apply_point_in_time_adaptive_calibration,
    build_adaptive_calibration_report,
    evaluate_adaptive_calibration_metrics,
    evaluate_point_in_time_adaptive_calibration,
    fit_point_in_time_adaptive_weights,
)
from backend.forecast.conservative_calibration import ConservativeCalibrationObservation


def test_weight_fit_uses_only_labels_available_before_evaluation_origin() -> None:
    history = _history(actual_by_origin=("0", "0", "0", "0"))
    future = [
        _observation(
            symbol=f"FUTURE{index}",
            origin=datetime(2021, 4, 1, tzinfo=UTC),
            target=datetime(2021, 5, 1, tzinfo=UTC),
            actual="0.2",
        )
        for index in range(100)
    ]
    as_of = datetime(2021, 3, 1, tzinfo=UTC)

    decision = fit_point_in_time_adaptive_weights(
        [*history, *future],
        asset_type="stock",
        horizon_days=20,
        as_of=as_of,
    )

    assert decision.status == "selected"
    assert decision.available_sample_count == 40
    assert decision.available_origin_count == 4
    assert decision.weights["zero_return"] == Decimal("1")
    assert decision.weights[CONSENSUS_MODEL_NAME] == Decimal("0")


def test_recent_internal_validation_failure_keeps_current_consensus() -> None:
    history = _history(actual_by_origin=("0", "0", "0", "0.2"))

    decision = fit_point_in_time_adaptive_weights(
        history,
        asset_type="stock",
        horizon_days=20,
        as_of=datetime(2021, 3, 1, tzinfo=UTC),
    )

    assert decision.status == "fallback"
    assert decision.reason == "validation_improvement_gate_failed"
    assert decision.weights[CONSENSUS_MODEL_NAME] == Decimal("1")
    assert decision.weights["zero_return"] == Decimal("0")


def test_insufficient_temporal_history_falls_back_to_consensus() -> None:
    history = _history(actual_by_origin=("0",))

    decision = fit_point_in_time_adaptive_weights(
        history,
        asset_type="stock",
        horizon_days=20,
        as_of=datetime(2021, 3, 1, tzinfo=UTC),
        min_training_sample_count=10,
    )

    assert decision.status == "fallback"
    assert decision.reason == "insufficient_history_origins"
    assert decision.weights[CONSENSUS_MODEL_NAME] == Decimal("1")


def test_adaptive_prediction_retains_consensus_direction_and_applies_safe_center() -> None:
    origin = datetime(2021, 3, 1, tzinfo=UTC)
    observation = _observation(
        symbol="AUDIT",
        origin=origin,
        target=origin + timedelta(days=30),
        actual="-0.1",
    )
    decision = AdaptiveCalibrationWeightDecision(
        asset_type="stock",
        horizon_days=20,
        as_of=origin,
        status="selected",
        reason="fixture",
        available_sample_count=40,
        available_origin_count=4,
        fit_sample_count=30,
        validation_sample_count=10,
        weights={
            "forecast_consensus": Decimal("0.2"),
            "advanced_quantile": Decimal("0.3"),
            "moving_average_3": Decimal("0.5"),
            "zero_return": Decimal("0"),
        },
    )

    prediction = apply_point_in_time_adaptive_calibration(observation, decision)

    assert prediction.price_center_return == Decimal("0.0950")
    assert prediction.direction_return == Decimal("0.2")
    assert prediction.original_consensus_return == Decimal("0.2")


def test_symbol_disjoint_adaptive_evaluation_passes_period_and_safety_gates() -> None:
    history = _history(actual_by_origin=("0", "0", "0", "0"))
    origin = datetime(2021, 3, 1, tzinfo=UTC)
    evaluation = [
        _observation(
            symbol=f"AUDIT{index}",
            origin=origin,
            target=origin + timedelta(days=30),
            actual="0",
            split="adaptive_audit",
        )
        for index in range(12)
    ]

    predictions = evaluate_point_in_time_adaptive_calibration(history, evaluation)
    metrics = evaluate_adaptive_calibration_metrics(evaluation, predictions)
    report = build_adaptive_calibration_report(
        metrics,
        predictions,
        required_splits=("adaptive_audit",),
    )

    assert report.runtime_review_eligible is True
    assert report.selection_rate == Decimal("1.000000")
    assert any(metric.group_type == "period" for metric in metrics)
    assert all(prediction.decision.status == "selected" for prediction in predictions)


def test_adaptive_metrics_require_one_prediction_per_observation() -> None:
    observation = _observation(
        symbol="AUDIT",
        origin=datetime(2021, 3, 1, tzinfo=UTC),
        target=datetime(2021, 4, 1, tzinfo=UTC),
        actual="0",
    )

    with pytest.raises(ValueError, match="one-to-one"):
        evaluate_adaptive_calibration_metrics([observation], [])


def test_adaptive_metrics_reject_duplicate_prediction_even_when_all_keys_exist() -> None:
    origin = datetime(2021, 3, 1, tzinfo=UTC)
    observations = [
        _observation(
            symbol=symbol,
            origin=origin,
            target=origin + timedelta(days=30),
            actual="0",
        )
        for symbol in ("AUDIT1", "AUDIT2")
    ]
    decision = _decision(origin, status="selected")
    predictions = [
        apply_point_in_time_adaptive_calibration(observation, decision)
        for observation in observations
    ]

    with pytest.raises(ValueError, match="one-to-one"):
        evaluate_adaptive_calibration_metrics(observations, [*predictions, predictions[0]])


def test_adaptive_report_fails_closed_without_overall_metrics() -> None:
    origin = datetime(2021, 3, 1, tzinfo=UTC)
    observation = _observation(
        symbol="AUDIT",
        origin=origin,
        target=origin + timedelta(days=30),
        actual="0",
    )
    prediction = apply_point_in_time_adaptive_calibration(
        observation,
        _decision(origin, status="selected"),
    )

    report = build_adaptive_calibration_report(
        [],
        [prediction],
        required_splits=("adaptive_audit",),
    )

    assert report.runtime_review_eligible is False
    assert "overall horizon metricがありません。" in report.gate_reasons


def test_adaptive_report_requires_audit_split_contract() -> None:
    with pytest.raises(ValueError, match="required_splits"):
        build_adaptive_calibration_report([], [], required_splits=())


def _history(*, actual_by_origin: tuple[str, ...]) -> list[ConservativeCalibrationObservation]:
    origins = (
        datetime(2020, 1, 1, tzinfo=UTC),
        datetime(2020, 4, 1, tzinfo=UTC),
        datetime(2020, 7, 1, tzinfo=UTC),
        datetime(2020, 10, 1, tzinfo=UTC),
    )
    observations: list[ConservativeCalibrationObservation] = []
    for origin_index, actual in enumerate(actual_by_origin):
        origin = origins[origin_index]
        observations.extend(
            _observation(
                symbol=f"TRAIN{origin_index}_{symbol_index}",
                origin=origin,
                target=origin + timedelta(days=30),
                actual=actual,
                split="calibration_history",
            )
            for symbol_index in range(10)
        )
    return observations


def _decision(
    origin: datetime,
    *,
    status: Literal["selected", "fallback"],
) -> AdaptiveCalibrationWeightDecision:
    selected = status == "selected"
    return AdaptiveCalibrationWeightDecision(
        asset_type="stock",
        horizon_days=20,
        as_of=origin,
        status=status,
        reason="fixture",
        available_sample_count=40,
        available_origin_count=4,
        fit_sample_count=30,
        validation_sample_count=10,
        weights={
            "forecast_consensus": Decimal("0") if selected else Decimal("1"),
            "advanced_quantile": Decimal("0") if selected else Decimal("0"),
            "moving_average_3": Decimal("0") if selected else Decimal("0"),
            "zero_return": Decimal("1") if selected else Decimal("0"),
        },
    )


def _observation(
    *,
    symbol: str,
    origin: datetime,
    target: datetime,
    actual: str,
    split: str = "adaptive_audit",
) -> ConservativeCalibrationObservation:
    return ConservativeCalibrationObservation(
        cohort="fixture",
        split=split,
        symbol=symbol,
        market="us",
        asset_type="stock",
        regime="uptrend",
        horizon_days=20,
        origin_at=origin,
        target_at=target,
        consensus_return=Decimal("0.2"),
        actual_return=Decimal(actual),
        conservative_returns={
            "advanced_quantile": Decimal("0.1"),
            "moving_average_3": Decimal("0.05"),
        },
    )
