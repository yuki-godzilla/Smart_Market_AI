from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.forecast.evaluation import CONSENSUS_MODEL_NAME, ForecastValidationPoint
from backend.forecast.rolling_conformal import (
    ROLLING_CONFORMAL_POLICY_VERSION,
    apply_rolling_conformal_decision,
    evaluate_rolling_conformal_intervals,
    fit_rolling_conformal_decision,
    write_rolling_conformal_outputs,
)


def test_fit_uses_only_matured_labels_at_the_forecast_origin() -> None:
    as_of = datetime(2022, 1, 1, tzinfo=UTC)
    matured = _calibration_history(count=40, actual="0.08")
    future = [
        _point(
            symbol=f"FUTURE{index}",
            origin=datetime(2022, 2, 1, tzinfo=UTC),
            target=datetime(2022, 3, 1, tzinfo=UTC),
            actual="1.00",
        )
        for index in range(100)
    ]

    decision = fit_rolling_conformal_decision(
        [*matured, *future],
        market="us",
        asset_type="stock",
        regime="sideways",
        horizon_days=20,
        as_of=as_of,
        max_score_quantile=None,
    )

    assert decision.status == "calibrated"
    assert decision.available_sample_count == 40
    assert decision.raw_score_quantile == Decimal("0.600000")
    assert decision.score_quantile == Decimal("0.600000")
    assert decision.policy_version == ROLLING_CONFORMAL_POLICY_VERSION


def test_hierarchical_scope_falls_back_from_sparse_regime_to_asset_type() -> None:
    history = [
        *_calibration_history(count=20, actual="0.08", regime="sideways"),
        *_calibration_history(count=20, actual="0.08", regime="uptrend", symbol_prefix="UP"),
    ]

    decision = fit_rolling_conformal_decision(
        history,
        market="us",
        asset_type="stock",
        regime="sideways",
        horizon_days=20,
        as_of=datetime(2022, 1, 1, tzinfo=UTC),
    )

    assert decision.status == "calibrated"
    assert decision.scope_type == "asset_type"
    assert decision.available_sample_count == 40


def test_insufficient_history_keeps_the_baseline_interval() -> None:
    point = _point(
        symbol="EVAL",
        origin=datetime(2022, 1, 1, tzinfo=UTC),
        target=datetime(2022, 2, 1, tzinfo=UTC),
        actual="0.08",
    )
    decision = fit_rolling_conformal_decision(
        _calibration_history(count=10, actual="0.08"),
        market=point.market,
        asset_type=point.asset_type,
        regime=point.regime,
        horizon_days=point.horizon_days,
        as_of=point.origin_at,
        max_score_quantile=None,
    )

    prediction = apply_rolling_conformal_decision(point, decision)

    assert decision.status == "fallback"
    assert prediction.adjusted_lower == prediction.baseline_lower
    assert prediction.adjusted_upper == prediction.baseline_upper
    assert prediction.adjusted_center == prediction.baseline_center
    assert prediction.adjusted_direction == prediction.baseline_direction


def test_normalized_conformal_expands_only_the_interval() -> None:
    point = _point(
        symbol="EVAL",
        origin=datetime(2022, 1, 1, tzinfo=UTC),
        target=datetime(2022, 2, 1, tzinfo=UTC),
        actual="0.08",
    )
    decision = fit_rolling_conformal_decision(
        _calibration_history(count=40, actual="0.08"),
        market=point.market,
        asset_type=point.asset_type,
        regime=point.regime,
        horizon_days=point.horizon_days,
        as_of=point.origin_at,
        max_score_quantile=None,
    )

    prediction = apply_rolling_conformal_decision(point, decision)

    assert prediction.baseline_lower == Decimal("-0.05")
    assert prediction.baseline_upper == Decimal("0.05")
    assert prediction.adjusted_lower == Decimal("-0.0800")
    assert prediction.adjusted_upper == Decimal("0.0800")
    assert prediction.adjusted_covered is True
    assert prediction.adjusted_center == Decimal("0")
    assert prediction.adjusted_direction == Decimal("0.01")


def test_optional_quantile_cap_bounds_expansion_and_records_the_cap() -> None:
    point = _point(
        symbol="EVAL",
        origin=datetime(2022, 1, 1, tzinfo=UTC),
        target=datetime(2022, 2, 1, tzinfo=UTC),
        actual="0.08",
    )
    decision = fit_rolling_conformal_decision(
        _calibration_history(count=40, actual="0.08"),
        market=point.market,
        asset_type=point.asset_type,
        regime=point.regime,
        horizon_days=point.horizon_days,
        as_of=point.origin_at,
        max_score_quantile=Decimal("0.5"),
    )

    prediction = apply_rolling_conformal_decision(point, decision)

    assert decision.raw_score_quantile == Decimal("0.600000")
    assert decision.score_quantile == Decimal("0.500000")
    assert decision.quantile_was_capped is True
    assert prediction.adjusted_lower == Decimal("-0.0750")
    assert prediction.adjusted_upper == Decimal("0.0750")


def test_new_symbol_disjoint_audit_can_become_a_review_candidate(tmp_path) -> None:
    calibration = _calibration_history(count=50, actual="0.075")
    origin = datetime(2022, 1, 1, tzinfo=UTC)
    evaluation = [
        _point(
            symbol=f"AUDIT{index}",
            origin=origin,
            target=origin + timedelta(days=30),
            actual="0.075",
        )
        for index in range(120)
    ]

    report = evaluate_rolling_conformal_intervals(
        calibration,
        evaluation,
        evaluation_role="new_sealed_audit",
        separation_mode="symbol_disjoint",
    )
    paths = write_rolling_conformal_outputs(report, tmp_path)

    horizon = next(row for row in report.metrics if row.group_type == "horizon")
    assert horizon.sample_count == 120
    assert horizon.calibration_rate == Decimal("1.000000")
    assert horizon.baseline_coverage == Decimal("0.000000")
    assert horizon.adjusted_coverage == Decimal("1.000000")
    assert horizon.interval_score_improvement > Decimal("0.01")
    assert report.metric_gates_passed is True
    assert report.runtime_review_eligible is True
    assert report.review_status == "runtime_review_candidate"
    assert all(path.exists() for path in paths.values())
    assert "center_return_changed: false" in paths["report"].read_text(encoding="utf-8")


def test_historical_replay_and_symbol_overlap_fail_closed() -> None:
    calibration = _calibration_history(count=50, actual="0.08")
    origin = datetime(2022, 1, 1, tzinfo=UTC)
    evaluation = [
        _point(
            symbol="CAL0" if index == 0 else f"AUDIT{index}",
            origin=origin,
            target=origin + timedelta(days=30),
            actual="0.08",
        )
        for index in range(120)
    ]

    historical = evaluate_rolling_conformal_intervals(calibration, evaluation)
    sealed = evaluate_rolling_conformal_intervals(
        calibration,
        evaluation,
        evaluation_role="new_sealed_audit",
    )

    assert historical.review_status == "historical_replay"
    assert historical.runtime_review_eligible is False
    assert sealed.separation_valid is False
    assert sealed.review_status == "gate_failed"
    assert sealed.runtime_review_eligible is False


def test_prequential_mode_uses_an_evaluation_label_only_after_it_matures() -> None:
    calibration = _calibration_history(count=40, actual="0.08")
    early_origin = datetime(2022, 1, 1, tzinfo=UTC)
    later_origin = datetime(2022, 3, 1, tzinfo=UTC)
    evaluation = [
        _point(
            symbol="EARLY",
            origin=early_origin,
            target=early_origin + timedelta(days=30),
            actual="0.08",
        ),
        _point(
            symbol="LATER",
            origin=later_origin,
            target=later_origin + timedelta(days=30),
            actual="0.08",
        ),
    ]

    static = evaluate_rolling_conformal_intervals(calibration, evaluation)
    prequential = evaluate_rolling_conformal_intervals(
        calibration,
        evaluation,
        include_matured_evaluation_history=True,
    )

    assert static.predictions[1].calibration_sample_count == 40
    assert prequential.predictions[1].calibration_sample_count == 41
    assert prequential.online_update_enabled is True


def _calibration_history(
    *,
    count: int,
    actual: str,
    regime: str = "sideways",
    symbol_prefix: str = "CAL",
) -> list[ForecastValidationPoint]:
    origins = (
        datetime(2020, 1, 1, tzinfo=UTC),
        datetime(2020, 4, 1, tzinfo=UTC),
    )
    return [
        _point(
            symbol=f"{symbol_prefix}{index}",
            origin=origins[index % len(origins)],
            target=origins[index % len(origins)] + timedelta(days=30),
            actual=actual,
            regime=regime,
        )
        for index in range(count)
    ]


def _point(
    *,
    symbol: str,
    origin: datetime,
    target: datetime,
    actual: str,
    regime: str = "sideways",
) -> ForecastValidationPoint:
    return ForecastValidationPoint(
        symbol=symbol,
        market="us",
        asset_type="stock",
        regime=regime,
        model_name=CONSENSUS_MODEL_NAME,
        horizon_days=20,
        origin_at=origin,
        target_at=target,
        predicted_return=Decimal("0"),
        direction_predicted_return=Decimal("0.01"),
        predicted_return_lower=Decimal("-0.05"),
        predicted_return_upper=Decimal("0.05"),
        actual_return=Decimal(actual),
    )
