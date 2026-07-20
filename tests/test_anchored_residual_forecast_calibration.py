import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from backend.forecast import (
    AnchoredResidualCalibrationDecision,
    apply_anchored_residual_calibration,
    build_anchored_residual_calibration_report,
    evaluate_anchored_residual_calibration_metrics,
    evaluate_point_in_time_anchored_residual_calibration,
    fit_point_in_time_anchored_residual,
)
from backend.forecast.conservative_calibration import (
    ConservativeCalibrationObservation,
    HorizonConservativeCalibrationProfile,
)
from tools.evaluate_anchored_residual_forecast_calibration import main


def test_residual_fit_ignores_labels_not_available_at_evaluation_origin() -> None:
    history = _linear_history()
    as_of = datetime(2021, 3, 1, tzinfo=UTC)
    future = [
        _observation(
            symbol=f"FUTURE{index}",
            origin=datetime(2021, 4, 1, tzinfo=UTC),
            consensus=Decimal("0.4"),
            actual=Decimal("-0.6"),
        )
        for index in range(100)
    ]

    expected = fit_point_in_time_anchored_residual(history, _profile(), as_of=as_of)
    actual = fit_point_in_time_anchored_residual([*history, *future], _profile(), as_of=as_of)

    assert expected.status == "selected"
    assert actual == expected
    assert actual.available_sample_count == 80
    assert actual.available_origin_count == 4


def test_recent_temporal_validation_failure_falls_back_to_frozen_anchor() -> None:
    history = _linear_history(validation_reversal=True)

    decision = fit_point_in_time_anchored_residual(
        history,
        _profile(),
        as_of=datetime(2021, 3, 1, tzinfo=UTC),
    )

    assert decision.status == "fallback"
    assert decision.reason == "validation_improvement_vs_anchor_gate_failed"
    assert decision.selected_spec == "anchor_only"
    assert decision.correction_limit == 0


def test_insufficient_history_falls_back_without_residual_state() -> None:
    decision = fit_point_in_time_anchored_residual(
        _linear_history()[:20],
        _profile(),
        as_of=datetime(2021, 3, 1, tzinfo=UTC),
    )

    assert decision.status == "fallback"
    assert decision.reason == "insufficient_history_samples"
    assert decision.feature_names == ()
    assert decision.coefficients == ()


def test_prediction_retains_consensus_direction_and_clips_residual() -> None:
    origin = datetime(2021, 3, 1, tzinfo=UTC)
    observation = _observation(
        symbol="AUDIT",
        origin=origin,
        consensus=Decimal("0.2"),
        actual=Decimal("0"),
    )
    decision = AnchoredResidualCalibrationDecision(
        horizon_days=20,
        as_of=origin,
        status="selected",
        reason="fixture",
        selected_spec="global_ridge",
        available_sample_count=80,
        available_origin_count=4,
        fit_sample_count=60,
        validation_sample_count=20,
        feature_names=(
            "anchor_return",
            "consensus_anchor_spread",
            "quantile_anchor_spread",
            "moving_average_anchor_spread",
        ),
        feature_means=(Decimal("0"),) * 4,
        feature_scales=(Decimal("1"),) * 4,
        coefficients=(Decimal("0"),) * 4,
        intercept=Decimal("1"),
        correction_limit=Decimal("0.25"),
    )

    prediction = apply_anchored_residual_calibration(observation, _profile(), decision)

    assert prediction.anchor_return == Decimal("0.0670")
    assert prediction.raw_residual_correction == Decimal("1.0000")
    assert prediction.residual_correction == Decimal("0.2500")
    assert prediction.price_center_return == Decimal("0.3170")
    assert prediction.correction_was_clipped is True
    assert prediction.direction_return == observation.consensus_return


def test_point_in_time_evaluation_keeps_a_single_causal_decision_per_origin() -> None:
    history = _linear_history()
    origin = datetime(2021, 3, 1, tzinfo=UTC)
    evaluation = [
        _observation(
            symbol=f"AUDIT{index}",
            origin=origin,
            consensus=Decimal("0.08") + Decimal(index) / Decimal("1000"),
            actual=Decimal("0.05"),
            split="residual_audit",
        )
        for index in range(12)
    ]

    predictions = evaluate_point_in_time_anchored_residual_calibration(
        history,
        evaluation,
        [_profile()],
    )

    assert len(predictions) == 12
    assert predictions[0].decision.status == "selected"
    assert all(prediction.decision == predictions[0].decision for prediction in predictions)


def test_residual_metrics_and_report_gate_against_frozen_anchor() -> None:
    history = _linear_history()
    origin = datetime(2021, 3, 1, tzinfo=UTC)
    evaluation = []
    for index in range(12):
        consensus = Decimal("0.08") + Decimal(index) / Decimal("1000")
        draft = _observation(
            symbol=f"AUDIT{index}",
            origin=origin,
            consensus=consensus,
            actual=Decimal("0"),
            split="residual_audit",
        )
        anchor = Decimal("0.3") * consensus + Decimal("0.7") * Decimal("0.01")
        actual = anchor + Decimal("0.5") * (consensus - anchor)
        evaluation.append(draft.model_copy(update={"actual_return": actual}))
    predictions = evaluate_point_in_time_anchored_residual_calibration(
        history,
        evaluation,
        [_profile()],
    )
    metrics = evaluate_anchored_residual_calibration_metrics(evaluation, predictions)
    report = build_anchored_residual_calibration_report(
        metrics,
        predictions,
        required_splits=("residual_audit",),
    )

    assert report.runtime_review_eligible is True
    assert report.selection_rate == Decimal("1.000000")
    overall = next(metric for metric in metrics if metric.group_type == "overall")
    assert overall.relative_rmse_improvement_vs_anchor > Decimal("0.01")
    assert overall.relative_rmse_improvement_vs_consensus > Decimal("0.01")
    assert overall.retained_direction_accuracy == overall.consensus_direction_accuracy


def test_residual_metrics_require_one_prediction_per_observation() -> None:
    observation = _observation(
        symbol="AUDIT",
        origin=datetime(2021, 3, 1, tzinfo=UTC),
        consensus=Decimal("0.1"),
        actual=Decimal("0"),
    )

    with pytest.raises(ValueError, match="one-to-one"):
        evaluate_anchored_residual_calibration_metrics([observation], [])


def test_residual_report_fails_closed_without_overall_metrics() -> None:
    report = build_anchored_residual_calibration_report(
        [],
        [],
        required_splits=("residual_audit",),
    )

    assert report.runtime_review_eligible is False
    assert "overall horizon metricがありません。" in report.gate_reasons


def test_residual_cli_writes_evaluation_only_audit_artifacts(tmp_path) -> None:
    calibration_path = tmp_path / "calibration.csv"
    evaluation_path = tmp_path / "evaluation.csv"
    output = tmp_path / "output"
    history = _linear_history()
    origin = datetime(2021, 3, 1, tzinfo=UTC)
    evaluation = []
    for index in range(12):
        consensus = Decimal("0.08") + Decimal(index) / Decimal("1000")
        anchor = Decimal("0.3") * consensus + Decimal("0.7") * Decimal("0.01")
        evaluation.append(
            _observation(
                symbol=f"AUDIT{index}",
                origin=origin,
                consensus=consensus,
                actual=anchor + Decimal("0.5") * (consensus - anchor),
            )
        )
    _write_points(calibration_path, history)
    _write_points(evaluation_path, evaluation)

    exit_code = main(
        [
            "--calibration-points",
            str(calibration_path),
            "--evaluation-points",
            str(evaluation_path),
            "--output",
            str(output),
            "--evaluation-split",
            "residual_audit",
        ]
    )

    assert exit_code == 0
    manifest = json.loads(
        (output / "anchored_residual_calibration_manifest.json").read_text("utf-8")
    )
    summary = (output / "anchored_residual_calibration_evaluation.md").read_text("utf-8")
    assert manifest["evaluation_only"] is True
    assert manifest["runtime_changed"] is False
    assert manifest["symbol_disjoint"] is True
    assert manifest["selected_prediction_count"] == 12
    assert manifest["parameters"]["ridge_alpha"]["global_ridge"] == "10"
    assert "ランタイムは未変更" in summary
    assert "通過: **はい**" in summary
    assert (output / "anchored_residual_calibration_decisions.csv").is_file()


def _linear_history(
    *,
    validation_reversal: bool = False,
) -> list[ConservativeCalibrationObservation]:
    origins = (
        datetime(2020, 1, 1, tzinfo=UTC),
        datetime(2020, 4, 1, tzinfo=UTC),
        datetime(2020, 7, 1, tzinfo=UTC),
        datetime(2020, 10, 1, tzinfo=UTC),
    )
    observations = []
    for origin_index, origin in enumerate(origins):
        for symbol_index in range(20):
            consensus = Decimal("0.05") + Decimal(symbol_index) / Decimal("200")
            anchor = Decimal("0.3") * consensus + Decimal("0.7") * Decimal("0.01")
            correction = Decimal("0.5") * (consensus - anchor)
            if validation_reversal and origin_index == len(origins) - 1:
                correction = -correction
            observations.append(
                _observation(
                    symbol=f"TRAIN{origin_index}_{symbol_index}",
                    origin=origin,
                    consensus=consensus,
                    actual=anchor + correction,
                    split="calibration_history",
                )
            )
    return observations


def _observation(
    *,
    symbol: str,
    origin: datetime,
    consensus: Decimal,
    actual: Decimal,
    split: str = "residual_audit",
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
        target_at=origin + timedelta(days=30),
        consensus_return=consensus,
        actual_return=actual,
        conservative_returns={
            "advanced_quantile": Decimal("0.02"),
            "moving_average_3": Decimal("0.01"),
        },
    )


def _profile() -> HorizonConservativeCalibrationProfile:
    return HorizonConservativeCalibrationProfile(
        horizon_days=20,
        conservative_model_name="moving_average_3",
        consensus_weight=Decimal("0.3"),
        conservative_weight=Decimal("0.7"),
        tuning_sample_count=100,
        tuning_consensus_rmse=Decimal("0.1"),
        tuning_conservative_rmse=Decimal("0.08"),
        tuning_candidate_rmse=Decimal("0.07"),
        tuning_relative_rmse_improvement=Decimal("0.3"),
        tuning_consensus_direction_accuracy=Decimal("0.5"),
        tuning_candidate_center_direction_accuracy=Decimal("0.5"),
        tuning_retained_direction_accuracy=Decimal("0.5"),
    )


def _write_points(
    path,
    observations: list[ConservativeCalibrationObservation],
) -> None:
    fieldnames = [
        "cohort",
        "split",
        "symbol",
        "market",
        "asset_type",
        "regime",
        "horizon_days",
        "origin_at",
        "target_at",
        "consensus_return",
        "advanced_quantile_return",
        "moving_average_3_return",
        "actual_return",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for observation in observations:
            writer.writerow(
                {
                    "cohort": observation.cohort,
                    "split": observation.split,
                    "symbol": observation.symbol,
                    "market": observation.market,
                    "asset_type": observation.asset_type,
                    "regime": observation.regime,
                    "horizon_days": observation.horizon_days,
                    "origin_at": observation.origin_at.isoformat(),
                    "target_at": observation.target_at.isoformat(),
                    "consensus_return": observation.consensus_return,
                    "advanced_quantile_return": observation.conservative_returns[
                        "advanced_quantile"
                    ],
                    "moving_average_3_return": observation.conservative_returns["moving_average_3"],
                    "actual_return": observation.actual_return,
                }
            )
