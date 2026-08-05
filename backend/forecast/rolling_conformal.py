"""Causal rolling conformal calibration for forecast return intervals.

The implementation is evaluation-only.  It recalibrates interval bounds from
already matured validation labels and cannot change the price center or the
direction head.  Runtime Forecast, Ranking, and Scoring consumers are not
connected to this module.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Iterable, Literal, Self, Sequence

from pydantic import ConfigDict, Field, model_validator

from backend.core.data_contracts import StrictBaseModel
from backend.forecast.evaluation import CONSENSUS_MODEL_NAME, ForecastValidationPoint

ROLLING_CONFORMAL_SCHEMA_VERSION = "rolling-conformal-interval-v1"
ROLLING_CONFORMAL_POLICY_VERSION = "bounded-normalized-cqr-temporal-gate-v1"
DEFAULT_TARGET_INTERVAL_COVERAGE = Decimal("0.60")
DEFAULT_INTERVAL_HALF_WIDTH_FLOOR = Decimal("0.005")
DEFAULT_MIN_GROUP_SAMPLE_COUNT = 30
DEFAULT_MIN_POOLED_SAMPLE_COUNT = 40
DEFAULT_MIN_ORIGIN_COUNT = 2
DEFAULT_MAX_HISTORY_POINTS = 500
DEFAULT_MAX_SCORE_QUANTILE = Decimal("0.50")
DEFAULT_INTERNAL_FIT_FRACTION = Decimal("0.70")
DEFAULT_MIN_INTERNAL_SAMPLE_COUNT = 10
MIN_INTERNAL_INTERVAL_SCORE_IMPROVEMENT = Decimal("0.01")
MIN_REVIEW_HORIZON_CASES = 100
MIN_REVIEW_ADJUSTMENT_RATE = Decimal("0.50")
MIN_INTERVAL_SCORE_IMPROVEMENT = Decimal("0.01")
MAX_TARGET_COVERAGE_SHORTFALL = Decimal("0.05")
MIN_SUBGROUP_CASES = 10
MAX_SUBGROUP_RELATIVE_SCORE_DEGRADATION = Decimal("0.10")
MAX_SUBGROUP_ABSOLUTE_SCORE_DEGRADATION = Decimal("0.005")
MAX_SUBGROUP_COVERAGE_DEGRADATION = Decimal("0.05")

ConformalDecisionStatus = Literal["calibrated", "fallback"]
ConformalEvaluationRole = Literal["historical_replay", "new_sealed_audit"]
ConformalSeparationMode = Literal["symbol_disjoint", "temporal_disjoint"]
ConformalReviewStatus = Literal[
    "historical_replay",
    "insufficient_evidence",
    "gate_failed",
    "runtime_review_candidate",
]


class RollingConformalDecision(StrictBaseModel):
    """A range-only calibration decision available at one forecast origin."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    policy_version: str = ROLLING_CONFORMAL_POLICY_VERSION
    horizon_days: int = Field(ge=1)
    as_of: datetime
    status: ConformalDecisionStatus
    reason: str = Field(min_length=1)
    scope_type: str = Field(min_length=1)
    scope_value: str = Field(min_length=1)
    available_sample_count: int = Field(ge=0)
    available_origin_count: int = Field(ge=0)
    fit_sample_count: int = Field(ge=0)
    validation_sample_count: int = Field(ge=0)
    raw_score_quantile: Decimal = Field(ge=0)
    score_quantile: Decimal = Field(ge=0)
    quantile_was_capped: bool = False
    target_interval_coverage: Decimal = Field(gt=0, lt=1)
    interval_half_width_floor: Decimal = Field(gt=0)
    validation_baseline_coverage: Decimal | None = Field(default=None, ge=0, le=1)
    validation_adjusted_coverage: Decimal | None = Field(default=None, ge=0, le=1)
    validation_baseline_interval_score: Decimal | None = Field(default=None, ge=0)
    validation_adjusted_interval_score: Decimal | None = Field(default=None, ge=0)
    validation_interval_score_improvement: Decimal | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.as_of.tzinfo is None:
            raise ValueError("conformal decision as_of must be timezone-aware")
        if self.status == "fallback" and self.score_quantile != 0:
            raise ValueError("fallback decisions cannot adjust the interval")
        if self.score_quantile > self.raw_score_quantile:
            raise ValueError("applied conformal quantile cannot exceed its raw quantile")
        return self


class RollingConformalPrediction(StrictBaseModel):
    """One baseline and conformal interval comparison with unchanged center/direction."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    target_at: datetime
    baseline_center: Decimal
    adjusted_center: Decimal
    baseline_direction: Decimal | None = None
    adjusted_direction: Decimal | None = None
    baseline_lower: Decimal
    baseline_upper: Decimal
    adjusted_lower: Decimal
    adjusted_upper: Decimal
    actual_return: Decimal
    interval_adjustment: Decimal = Field(ge=0)
    decision_status: ConformalDecisionStatus
    decision_reason: str = Field(min_length=1)
    calibration_scope_type: str = Field(min_length=1)
    calibration_scope_value: str = Field(min_length=1)
    calibration_sample_count: int = Field(ge=0)
    calibration_origin_count: int = Field(ge=0)
    calibration_fit_sample_count: int = Field(ge=0)
    calibration_validation_sample_count: int = Field(ge=0)
    raw_score_quantile: Decimal = Field(ge=0)
    score_quantile: Decimal = Field(ge=0)
    quantile_was_capped: bool
    validation_interval_score_improvement: Decimal | None = None
    baseline_covered: bool
    adjusted_covered: bool
    baseline_interval_score: Decimal = Field(ge=0)
    adjusted_interval_score: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_range_only_adjustment(self) -> Self:
        if self.adjusted_center != self.baseline_center:
            raise ValueError("rolling conformal calibration cannot change the price center")
        if self.adjusted_direction != self.baseline_direction:
            raise ValueError("rolling conformal calibration cannot change the direction head")
        if self.baseline_lower > self.baseline_center or self.baseline_center > self.baseline_upper:
            raise ValueError("baseline interval must contain its center")
        if self.adjusted_lower > self.adjusted_center or self.adjusted_center > self.adjusted_upper:
            raise ValueError("adjusted interval must contain its center")
        return self


class RollingConformalMetricRow(StrictBaseModel):
    """Coverage, width, and proper interval-score comparison for one group."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    group_type: str = Field(min_length=1)
    group_value: str = Field(min_length=1)
    horizon_days: int = Field(ge=0)
    sample_count: int = Field(ge=0)
    calibrated_count: int = Field(ge=0)
    capped_count: int = Field(ge=0)
    calibration_rate: Decimal = Field(ge=0, le=1)
    baseline_coverage: Decimal = Field(ge=0, le=1)
    adjusted_coverage: Decimal = Field(ge=0, le=1)
    target_coverage: Decimal = Field(gt=0, lt=1)
    baseline_mean_width: Decimal = Field(ge=0)
    adjusted_mean_width: Decimal = Field(ge=0)
    mean_interval_adjustment: Decimal = Field(ge=0)
    baseline_interval_score: Decimal = Field(ge=0)
    adjusted_interval_score: Decimal = Field(ge=0)
    interval_score_improvement: Decimal


class RollingConformalEvaluationReport(StrictBaseModel):
    """Evaluation-only report with fail-closed runtime review gates."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = ROLLING_CONFORMAL_SCHEMA_VERSION
    policy_version: str = ROLLING_CONFORMAL_POLICY_VERSION
    evaluation_role: ConformalEvaluationRole
    separation_mode: ConformalSeparationMode
    target_interval_coverage: Decimal = Field(gt=0, lt=1)
    requested_calibration_count: int = Field(ge=0)
    eligible_calibration_count: int = Field(ge=0)
    requested_evaluation_count: int = Field(ge=0)
    eligible_evaluation_count: int = Field(ge=0)
    invalid_evaluation_count: int = Field(ge=0)
    calibration_symbol_count: int = Field(ge=0)
    evaluation_symbol_count: int = Field(ge=0)
    overlapping_symbols: list[str] = Field(default_factory=list)
    separation_valid: bool
    online_update_enabled: bool
    max_score_quantile: Decimal | None = Field(default=None, gt=0)
    predictions: list[RollingConformalPrediction] = Field(default_factory=list)
    metrics: list[RollingConformalMetricRow] = Field(default_factory=list)
    metric_gates_passed: bool
    runtime_review_eligible: bool
    review_status: ConformalReviewStatus
    review_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    center_return_changed: bool = False
    direction_return_changed: bool = False


def fit_rolling_conformal_decision(
    calibration_history: Iterable[ForecastValidationPoint],
    *,
    market: str,
    asset_type: str,
    regime: str,
    horizon_days: int,
    as_of: datetime,
    target_interval_coverage: Decimal = DEFAULT_TARGET_INTERVAL_COVERAGE,
    interval_half_width_floor: Decimal = DEFAULT_INTERVAL_HALF_WIDTH_FLOOR,
    min_group_sample_count: int = DEFAULT_MIN_GROUP_SAMPLE_COUNT,
    min_pooled_sample_count: int = DEFAULT_MIN_POOLED_SAMPLE_COUNT,
    min_origin_count: int = DEFAULT_MIN_ORIGIN_COUNT,
    max_history_points: int = DEFAULT_MAX_HISTORY_POINTS,
    max_score_quantile: Decimal | None = DEFAULT_MAX_SCORE_QUANTILE,
    internal_fit_fraction: Decimal = DEFAULT_INTERNAL_FIT_FRACTION,
    min_internal_sample_count: int = DEFAULT_MIN_INTERNAL_SAMPLE_COUNT,
) -> RollingConformalDecision:
    """Fit an expansion-only normalized CQR quantile from matured labels."""

    _validate_configuration(
        target_interval_coverage=target_interval_coverage,
        interval_half_width_floor=interval_half_width_floor,
        min_group_sample_count=min_group_sample_count,
        min_pooled_sample_count=min_pooled_sample_count,
        min_origin_count=min_origin_count,
        max_history_points=max_history_points,
        internal_fit_fraction=internal_fit_fraction,
        min_internal_sample_count=min_internal_sample_count,
    )
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if max_score_quantile is not None and max_score_quantile <= 0:
        raise ValueError("max_score_quantile must be positive when provided")
    normalized_market = market.strip().lower()
    normalized_asset_type = asset_type.strip().lower()
    normalized_regime = regime.strip().lower()
    matured = [
        point
        for point in calibration_history
        if _is_eligible_interval_point(point)
        and point.horizon_days == horizon_days
        and point.target_at <= as_of
    ]
    matured.sort(key=lambda point: (point.target_at, point.origin_at, point.symbol))
    scopes = (
        (
            "market_asset_regime",
            f"{normalized_market}|{normalized_asset_type}|{normalized_regime}",
            [
                point
                for point in matured
                if point.market.strip().lower() == normalized_market
                and point.asset_type.strip().lower() == normalized_asset_type
                and point.regime.strip().lower() == normalized_regime
            ],
            min_group_sample_count,
        ),
        (
            "asset_type",
            normalized_asset_type,
            [
                point
                for point in matured
                if point.asset_type.strip().lower() == normalized_asset_type
            ],
            min_group_sample_count,
        ),
        ("horizon", str(horizon_days), matured, min_pooled_sample_count),
    )
    last_failed: RollingConformalDecision | None = None
    for scope_type, scope_value, available, minimum_samples in scopes:
        selected = available[-max_history_points:]
        origin_times = sorted({point.origin_at for point in selected})
        origin_count = len(origin_times)
        if len(selected) < minimum_samples or origin_count < min_origin_count:
            continue
        fit_origin_count = int(
            (Decimal(origin_count) * internal_fit_fraction).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
        fit_origin_count = min(max(fit_origin_count, 1), origin_count - 1)
        fit_origins = set(origin_times[:fit_origin_count])
        fit_points = [point for point in selected if point.origin_at in fit_origins]
        validation_points = [point for point in selected if point.origin_at not in fit_origins]
        if (
            len(fit_points) < min_internal_sample_count
            or len(validation_points) < min_internal_sample_count
        ):
            continue
        scores = [
            _normalized_nonconformity_score(
                point,
                interval_half_width_floor=interval_half_width_floor,
            )
            for point in fit_points
        ]
        raw_quantile = _finite_sample_quantile(scores, target_interval_coverage)
        quantile = (
            min(raw_quantile, max_score_quantile)
            if max_score_quantile is not None
            else raw_quantile
        )
        baseline_coverage, baseline_score = _historical_interval_metrics(
            validation_points,
            score_quantile=Decimal("0"),
            target_interval_coverage=target_interval_coverage,
            interval_half_width_floor=interval_half_width_floor,
        )
        adjusted_coverage, adjusted_score = _historical_interval_metrics(
            validation_points,
            score_quantile=quantile,
            target_interval_coverage=target_interval_coverage,
            interval_half_width_floor=interval_half_width_floor,
        )
        improvement = (
            (baseline_score - adjusted_score) / baseline_score
            if baseline_score > 0
            else Decimal("0")
        )
        gate_passed = (
            improvement >= MIN_INTERNAL_INTERVAL_SCORE_IMPROVEMENT
            and adjusted_coverage >= baseline_coverage
        )
        decision = RollingConformalDecision(
            horizon_days=horizon_days,
            as_of=as_of,
            status="calibrated" if gate_passed else "fallback",
            reason=(
                f"matured_{scope_type}_temporal_gate_passed"
                if gate_passed
                else f"matured_{scope_type}_temporal_gate_failed"
            ),
            scope_type=scope_type,
            scope_value=scope_value,
            available_sample_count=len(selected),
            available_origin_count=origin_count,
            fit_sample_count=len(fit_points),
            validation_sample_count=len(validation_points),
            raw_score_quantile=_round_metric(raw_quantile),
            score_quantile=_round_metric(quantile if gate_passed else Decimal("0")),
            quantile_was_capped=quantile < raw_quantile,
            target_interval_coverage=target_interval_coverage,
            interval_half_width_floor=interval_half_width_floor,
            validation_baseline_coverage=baseline_coverage,
            validation_adjusted_coverage=adjusted_coverage,
            validation_baseline_interval_score=baseline_score,
            validation_adjusted_interval_score=adjusted_score,
            validation_interval_score_improvement=_round_metric(improvement),
        )
        if gate_passed:
            return decision
        last_failed = decision

    if last_failed is not None:
        return last_failed

    pooled = matured[-max_history_points:]
    return RollingConformalDecision(
        horizon_days=horizon_days,
        as_of=as_of,
        status="fallback",
        reason="insufficient_matured_calibration_history",
        scope_type="horizon",
        scope_value=str(horizon_days),
        available_sample_count=len(pooled),
        available_origin_count=len({point.origin_at for point in pooled}),
        fit_sample_count=0,
        validation_sample_count=0,
        raw_score_quantile=Decimal("0"),
        score_quantile=Decimal("0"),
        target_interval_coverage=target_interval_coverage,
        interval_half_width_floor=interval_half_width_floor,
    )


def apply_rolling_conformal_decision(
    point: ForecastValidationPoint,
    decision: RollingConformalDecision,
) -> RollingConformalPrediction:
    """Apply a conformal range adjustment without changing center or direction."""

    if not _is_eligible_interval_point(point):
        raise ValueError("forecast point does not have a valid consensus interval")
    if point.horizon_days != decision.horizon_days:
        raise ValueError("forecast point and conformal decision horizons do not match")
    if point.origin_at != decision.as_of:
        raise ValueError("conformal decision must be made at the forecast origin")
    lower = point.predicted_return_lower
    upper = point.predicted_return_upper
    if lower is None or upper is None:  # pragma: no cover - narrowed above
        raise ValueError("forecast interval bounds are required")
    half_width = max((upper - lower) / Decimal("2"), decision.interval_half_width_floor)
    adjustment = (
        decision.score_quantile * half_width if decision.status == "calibrated" else Decimal("0")
    )
    adjusted_lower = lower - adjustment
    adjusted_upper = upper + adjustment
    baseline_score = _interval_score(
        point.actual_return,
        lower,
        upper,
        target_interval_coverage=decision.target_interval_coverage,
    )
    adjusted_score = _interval_score(
        point.actual_return,
        adjusted_lower,
        adjusted_upper,
        target_interval_coverage=decision.target_interval_coverage,
    )
    return RollingConformalPrediction(
        symbol=point.symbol,
        market=point.market,
        asset_type=point.asset_type,
        regime=point.regime,
        horizon_days=point.horizon_days,
        origin_at=point.origin_at,
        target_at=point.target_at,
        baseline_center=point.predicted_return,
        adjusted_center=point.predicted_return,
        baseline_direction=point.direction_predicted_return,
        adjusted_direction=point.direction_predicted_return,
        baseline_lower=lower,
        baseline_upper=upper,
        adjusted_lower=_round_return(adjusted_lower),
        adjusted_upper=_round_return(adjusted_upper),
        actual_return=point.actual_return,
        interval_adjustment=_round_return(adjustment),
        decision_status=decision.status,
        decision_reason=decision.reason,
        calibration_scope_type=decision.scope_type,
        calibration_scope_value=decision.scope_value,
        calibration_sample_count=decision.available_sample_count,
        calibration_origin_count=decision.available_origin_count,
        calibration_fit_sample_count=decision.fit_sample_count,
        calibration_validation_sample_count=decision.validation_sample_count,
        raw_score_quantile=decision.raw_score_quantile,
        score_quantile=decision.score_quantile,
        quantile_was_capped=decision.quantile_was_capped,
        validation_interval_score_improvement=(decision.validation_interval_score_improvement),
        baseline_covered=lower <= point.actual_return <= upper,
        adjusted_covered=adjusted_lower <= point.actual_return <= adjusted_upper,
        baseline_interval_score=baseline_score,
        adjusted_interval_score=adjusted_score,
    )


def evaluate_rolling_conformal_intervals(
    calibration_points: Iterable[ForecastValidationPoint],
    evaluation_points: Iterable[ForecastValidationPoint],
    *,
    evaluation_role: ConformalEvaluationRole = "historical_replay",
    separation_mode: ConformalSeparationMode = "symbol_disjoint",
    target_interval_coverage: Decimal = DEFAULT_TARGET_INTERVAL_COVERAGE,
    interval_half_width_floor: Decimal = DEFAULT_INTERVAL_HALF_WIDTH_FLOOR,
    min_group_sample_count: int = DEFAULT_MIN_GROUP_SAMPLE_COUNT,
    min_pooled_sample_count: int = DEFAULT_MIN_POOLED_SAMPLE_COUNT,
    min_origin_count: int = DEFAULT_MIN_ORIGIN_COUNT,
    max_history_points: int = DEFAULT_MAX_HISTORY_POINTS,
    include_matured_evaluation_history: bool = False,
    max_score_quantile: Decimal | None = DEFAULT_MAX_SCORE_QUANTILE,
    internal_fit_fraction: Decimal = DEFAULT_INTERNAL_FIT_FRACTION,
    min_internal_sample_count: int = DEFAULT_MIN_INTERNAL_SAMPLE_COUNT,
) -> RollingConformalEvaluationReport:
    """Evaluate causal range calibration across horizon and domain subgroups."""

    calibration_input = list(calibration_points)
    evaluation_input = list(evaluation_points)
    calibration_consensus = [
        point for point in calibration_input if point.model_name == CONSENSUS_MODEL_NAME
    ]
    evaluation_consensus = [
        point for point in evaluation_input if point.model_name == CONSENSUS_MODEL_NAME
    ]
    calibration = [point for point in calibration_consensus if _is_eligible_interval_point(point)]
    evaluation = [point for point in evaluation_consensus if _is_eligible_interval_point(point)]
    _validate_unique_points(calibration, label="calibration")
    _validate_unique_points(evaluation, label="evaluation")
    calibration_symbols = {point.symbol.strip().upper() for point in calibration}
    evaluation_symbols = {point.symbol.strip().upper() for point in evaluation}
    overlap = sorted(calibration_symbols & evaluation_symbols)
    separation_valid = _separation_is_valid(
        calibration,
        evaluation,
        separation_mode=separation_mode,
        overlapping_symbols=overlap,
    )

    predictions: list[RollingConformalPrediction] = []
    rolling_history = list(calibration)
    for point in sorted(
        evaluation,
        key=lambda item: (item.origin_at, item.horizon_days, item.symbol),
    ):
        decision = fit_rolling_conformal_decision(
            rolling_history,
            market=point.market,
            asset_type=point.asset_type,
            regime=point.regime,
            horizon_days=point.horizon_days,
            as_of=point.origin_at,
            target_interval_coverage=target_interval_coverage,
            interval_half_width_floor=interval_half_width_floor,
            min_group_sample_count=min_group_sample_count,
            min_pooled_sample_count=min_pooled_sample_count,
            min_origin_count=min_origin_count,
            max_history_points=max_history_points,
            max_score_quantile=max_score_quantile,
            internal_fit_fraction=internal_fit_fraction,
            min_internal_sample_count=min_internal_sample_count,
        )
        predictions.append(apply_rolling_conformal_decision(point, decision))
        if include_matured_evaluation_history:
            rolling_history.append(point)

    metrics = _build_metric_rows(
        predictions,
        target_interval_coverage=target_interval_coverage,
    )
    metric_gates_passed, gate_reasons = _metric_gate_decision(
        metrics,
        target_interval_coverage=target_interval_coverage,
    )
    runtime_review_eligible = (
        evaluation_role == "new_sealed_audit"
        and separation_valid
        and metric_gates_passed
        and max_score_quantile is not None
    )
    review_status: ConformalReviewStatus
    review_reasons = list(gate_reasons)
    if evaluation_role == "historical_replay":
        review_status = "historical_replay"
        review_reasons.insert(0, "既確認データのhistorical replayはruntime採用根拠にしない")
    elif len(evaluation) < MIN_REVIEW_HORIZON_CASES:
        review_status = "insufficient_evidence"
    elif max_score_quantile is None:
        review_status = "gate_failed"
        review_reasons.insert(0, "unbounded conformalはresearch専用でruntime候補にしない")
    elif not separation_valid or not metric_gates_passed:
        review_status = "gate_failed"
    else:
        review_status = "runtime_review_candidate"
        review_reasons.append("新しいsealed auditのrange候補。runtime統合には別途明示reviewが必要")

    warnings: list[str] = []
    invalid_count = len(evaluation_consensus) - len(evaluation)
    if invalid_count:
        warnings.append(f"有効なConsensus intervalを持たない評価点を{invalid_count}件除外")
    if overlap:
        warnings.append(f"calibration / evaluationでsymbolが{len(overlap)}件重複")
    if not separation_valid:
        warnings.append(f"{separation_mode}境界を満たさない")
    if any(prediction.decision_status == "fallback" for prediction in predictions):
        warnings.append("履歴不足によりbaseline intervalを維持した評価点がある")
    return RollingConformalEvaluationReport(
        evaluation_role=evaluation_role,
        separation_mode=separation_mode,
        target_interval_coverage=target_interval_coverage,
        requested_calibration_count=len(calibration_consensus),
        eligible_calibration_count=len(calibration),
        requested_evaluation_count=len(evaluation_consensus),
        eligible_evaluation_count=len(evaluation),
        invalid_evaluation_count=invalid_count,
        calibration_symbol_count=len(calibration_symbols),
        evaluation_symbol_count=len(evaluation_symbols),
        overlapping_symbols=overlap,
        separation_valid=separation_valid,
        online_update_enabled=include_matured_evaluation_history,
        max_score_quantile=max_score_quantile,
        predictions=predictions,
        metrics=metrics,
        metric_gates_passed=metric_gates_passed,
        runtime_review_eligible=runtime_review_eligible,
        review_status=review_status,
        review_reasons=review_reasons,
        warnings=warnings,
    )


def write_rolling_conformal_outputs(
    report: RollingConformalEvaluationReport,
    output_dir: Path,
) -> dict[str, Path]:
    """Write deterministic cases, subgroup metrics, and a review summary."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "cases": output_dir / "rolling_conformal_cases.csv",
        "metrics": output_dir / "rolling_conformal_metrics.csv",
        "report": output_dir / "rolling_conformal_report.md",
    }
    _write_models_csv(paths["cases"], report.predictions, RollingConformalPrediction)
    _write_models_csv(paths["metrics"], report.metrics, RollingConformalMetricRow)
    paths["report"].write_text(
        _render_report_markdown(report),
        encoding="utf-8",
        newline="\n",
    )
    return paths


def _is_eligible_interval_point(point: ForecastValidationPoint) -> bool:
    lower = point.predicted_return_lower
    upper = point.predicted_return_upper
    return bool(
        point.model_name == CONSENSUS_MODEL_NAME
        and lower is not None
        and upper is not None
        and lower <= point.predicted_return <= upper
        and point.origin_at.tzinfo is not None
        and point.target_at.tzinfo is not None
    )


def _normalized_nonconformity_score(
    point: ForecastValidationPoint,
    *,
    interval_half_width_floor: Decimal,
) -> Decimal:
    lower = point.predicted_return_lower
    upper = point.predicted_return_upper
    if lower is None or upper is None:  # pragma: no cover - narrowed by caller
        raise ValueError("forecast interval bounds are required")
    outside_distance = max(
        lower - point.actual_return,
        point.actual_return - upper,
        Decimal("0"),
    )
    half_width = max((upper - lower) / Decimal("2"), interval_half_width_floor)
    return outside_distance / half_width


def _historical_interval_metrics(
    points: list[ForecastValidationPoint],
    *,
    score_quantile: Decimal,
    target_interval_coverage: Decimal,
    interval_half_width_floor: Decimal,
) -> tuple[Decimal, Decimal]:
    coverages: list[Decimal] = []
    interval_scores: list[Decimal] = []
    for point in points:
        lower = point.predicted_return_lower
        upper = point.predicted_return_upper
        if lower is None or upper is None:  # pragma: no cover - narrowed by caller
            continue
        half_width = max((upper - lower) / Decimal("2"), interval_half_width_floor)
        adjustment = score_quantile * half_width
        adjusted_lower = lower - adjustment
        adjusted_upper = upper + adjustment
        coverages.append(Decimal(adjusted_lower <= point.actual_return <= adjusted_upper))
        interval_scores.append(
            _interval_score(
                point.actual_return,
                adjusted_lower,
                adjusted_upper,
                target_interval_coverage=target_interval_coverage,
            )
        )
    return _mean(coverages), _mean(interval_scores)


def _finite_sample_quantile(values: Sequence[Decimal], coverage: Decimal) -> Decimal:
    if not values:
        raise ValueError("conformal quantile requires at least one score")
    ordered = sorted(values)
    rank = int((Decimal(len(ordered) + 1) * coverage).to_integral_value(rounding=ROUND_CEILING))
    rank = min(max(rank, 1), len(ordered))
    return ordered[rank - 1]


def _build_metric_rows(
    predictions: list[RollingConformalPrediction],
    *,
    target_interval_coverage: Decimal,
) -> list[RollingConformalMetricRow]:
    grouped: dict[tuple[str, str, int], list[RollingConformalPrediction]] = defaultdict(list)
    grouped[("all_horizons", "all", 0)] = list(predictions)
    for prediction in predictions:
        horizon = prediction.horizon_days
        grouped[("horizon", str(horizon), horizon)].append(prediction)
        grouped[("market", prediction.market.strip().lower(), horizon)].append(prediction)
        grouped[("asset_type", prediction.asset_type.strip().lower(), horizon)].append(prediction)
        grouped[("regime", prediction.regime.strip().lower(), horizon)].append(prediction)
        grouped[("calibration_scope", prediction.calibration_scope_type, horizon)].append(
            prediction
        )
    return [
        _aggregate_predictions(
            selected,
            group_type=key[0],
            group_value=key[1],
            horizon_days=key[2],
            target_interval_coverage=target_interval_coverage,
        )
        for key, selected in sorted(grouped.items())
    ]


def _aggregate_predictions(
    predictions: list[RollingConformalPrediction],
    *,
    group_type: str,
    group_value: str,
    horizon_days: int,
    target_interval_coverage: Decimal,
) -> RollingConformalMetricRow:
    baseline_score = _mean([row.baseline_interval_score for row in predictions])
    adjusted_score = _mean([row.adjusted_interval_score for row in predictions])
    improvement = (
        (baseline_score - adjusted_score) / baseline_score if baseline_score > 0 else Decimal("0")
    )
    calibrated_count = sum(row.decision_status == "calibrated" for row in predictions)
    return RollingConformalMetricRow(
        group_type=group_type,
        group_value=group_value,
        horizon_days=horizon_days,
        sample_count=len(predictions),
        calibrated_count=calibrated_count,
        capped_count=sum(
            row.quantile_was_capped and row.decision_status == "calibrated" for row in predictions
        ),
        calibration_rate=(
            _round_metric(Decimal(calibrated_count) / Decimal(len(predictions)))
            if predictions
            else Decimal("0")
        ),
        baseline_coverage=_mean([Decimal(row.baseline_covered) for row in predictions]),
        adjusted_coverage=_mean([Decimal(row.adjusted_covered) for row in predictions]),
        target_coverage=target_interval_coverage,
        baseline_mean_width=_mean([row.baseline_upper - row.baseline_lower for row in predictions]),
        adjusted_mean_width=_mean([row.adjusted_upper - row.adjusted_lower for row in predictions]),
        mean_interval_adjustment=_mean([row.interval_adjustment for row in predictions]),
        baseline_interval_score=baseline_score,
        adjusted_interval_score=adjusted_score,
        interval_score_improvement=_round_metric(improvement),
    )


def _metric_gate_decision(
    metrics: list[RollingConformalMetricRow],
    *,
    target_interval_coverage: Decimal,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    horizons = [row for row in metrics if row.group_type == "horizon"]
    if not horizons:
        return False, ["horizon別metricがない"]
    for row in horizons:
        label = f"{row.horizon_days}日"
        if row.sample_count < MIN_REVIEW_HORIZON_CASES:
            reasons.append(f"{label}: 評価点が{MIN_REVIEW_HORIZON_CASES}件未満")
        if row.calibration_rate < MIN_REVIEW_ADJUSTMENT_RATE:
            reasons.append(f"{label}: calibration適用率が{MIN_REVIEW_ADJUSTMENT_RATE}未満")
        if row.interval_score_improvement < MIN_INTERVAL_SCORE_IMPROVEMENT:
            reasons.append(f"{label}: proper interval score改善が1%未満")
        if row.adjusted_coverage < row.baseline_coverage:
            reasons.append(f"{label}: coverageがbaselineより低下")
        if row.adjusted_coverage < target_interval_coverage - MAX_TARGET_COVERAGE_SHORTFALL:
            reasons.append(f"{label}: target coverageとの差が5 percentage points超")

    for row in metrics:
        if row.group_type not in {"market", "asset_type", "regime"}:
            continue
        if row.sample_count < MIN_SUBGROUP_CASES:
            continue
        score_delta = row.adjusted_interval_score - row.baseline_interval_score
        relative_degradation = (
            score_delta / row.baseline_interval_score
            if row.baseline_interval_score > 0
            else Decimal("0")
        )
        if (
            score_delta > MAX_SUBGROUP_ABSOLUTE_SCORE_DEGRADATION
            and relative_degradation > MAX_SUBGROUP_RELATIVE_SCORE_DEGRADATION
        ):
            reasons.append(
                f"{row.horizon_days}日 {row.group_type}={row.group_value}: interval score重大劣化"
            )
        if row.baseline_coverage - row.adjusted_coverage > MAX_SUBGROUP_COVERAGE_DEGRADATION:
            reasons.append(
                f"{row.horizon_days}日 {row.group_type}={row.group_value}: coverage重大劣化"
            )
    if reasons:
        return False, reasons
    return True, ["全horizonのcoverage・proper score・subgroup gateを通過"]


def _separation_is_valid(
    calibration: list[ForecastValidationPoint],
    evaluation: list[ForecastValidationPoint],
    *,
    separation_mode: ConformalSeparationMode,
    overlapping_symbols: list[str],
) -> bool:
    if separation_mode == "symbol_disjoint":
        return not overlapping_symbols
    if not calibration or not evaluation:
        return False
    return max(point.target_at for point in calibration) <= min(
        point.origin_at for point in evaluation
    )


def _validate_configuration(
    *,
    target_interval_coverage: Decimal,
    interval_half_width_floor: Decimal,
    min_group_sample_count: int,
    min_pooled_sample_count: int,
    min_origin_count: int,
    max_history_points: int,
    internal_fit_fraction: Decimal,
    min_internal_sample_count: int,
) -> None:
    if target_interval_coverage <= 0 or target_interval_coverage >= 1:
        raise ValueError("target_interval_coverage must be between zero and one")
    if interval_half_width_floor <= 0:
        raise ValueError("interval_half_width_floor must be positive")
    if min_group_sample_count < 1 or min_pooled_sample_count < 1:
        raise ValueError("minimum conformal sample counts must be positive")
    if min_origin_count < 1:
        raise ValueError("min_origin_count must be positive")
    if max_history_points < max(min_group_sample_count, min_pooled_sample_count):
        raise ValueError("max_history_points cannot be smaller than minimum sample counts")
    if internal_fit_fraction <= 0 or internal_fit_fraction >= 1:
        raise ValueError("internal_fit_fraction must be between zero and one")
    if min_internal_sample_count < 1:
        raise ValueError("min_internal_sample_count must be positive")


def _validate_unique_points(points: list[ForecastValidationPoint], *, label: str) -> None:
    keys = [
        (point.symbol.strip().upper(), point.horizon_days, point.origin_at, point.target_at)
        for point in points
    ]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} forecast points contain duplicate consensus keys")


def _interval_score(
    actual: Decimal,
    lower: Decimal,
    upper: Decimal,
    *,
    target_interval_coverage: Decimal,
) -> Decimal:
    alpha = Decimal("1") - target_interval_coverage
    score = upper - lower
    if actual < lower:
        score += (Decimal("2") / alpha) * (lower - actual)
    elif actual > upper:
        score += (Decimal("2") / alpha) * (actual - upper)
    return _round_metric(score)


def _mean(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.000000")
    return _round_metric(sum(values, Decimal("0")) / Decimal(len(values)))


def _round_metric(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _round_return(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _write_models_csv(
    path: Path,
    rows: Sequence[StrictBaseModel],
    model_type: type[StrictBaseModel],
) -> None:
    fieldnames = list(model_type.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.model_dump(mode="json"))


def _render_report_markdown(report: RollingConformalEvaluationReport) -> str:
    lines = [
        "# Rolling Conformal予測レンジ shadow評価",
        "",
        "中心returnと方向returnを変更せず、origin時点で成熟済みの過去誤差だけでrangeを校正します。",
        "",
        f"- policy: `{report.policy_version}`",
        f"- evaluation role: `{report.evaluation_role}`",
        f"- separation: `{report.separation_mode}` / valid={str(report.separation_valid).lower()}",
        f"- matured evaluation history update: {str(report.online_update_enabled).lower()}",
        f"- max normalized quantile: {report.max_score_quantile or 'none'}",
        f"- calibration symbols: {report.calibration_symbol_count}",
        f"- evaluation symbols: {report.evaluation_symbol_count}",
        f"- eligible evaluation points: {report.eligible_evaluation_count}",
        f"- review status: `{report.review_status}`",
        f"- metric gates passed: {str(report.metric_gates_passed).lower()}",
        f"- runtime review eligible: {str(report.runtime_review_eligible).lower()}",
        "- center_return_changed: false",
        "- direction_return_changed: false",
        "",
        "| Group | Value | Horizon | N | Calibrated | Capped | Coverage before | Coverage after | Width before | Width after | Interval score improvement |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.metrics:
        if row.group_type not in {"all_horizons", "horizon", "market", "asset_type", "regime"}:
            continue
        lines.append(
            f"| {row.group_type} | {row.group_value} | {row.horizon_days or '-'} | "
            f"{row.sample_count} | {row.calibrated_count} | {row.capped_count} | "
            f"{row.baseline_coverage} | "
            f"{row.adjusted_coverage} | {row.baseline_mean_width} | "
            f"{row.adjusted_mean_width} | {row.interval_score_improvement} |"
        )
    lines.extend(["", "## 判定理由", ""])
    lines.extend(f"- {reason}" for reason in report.review_reasons)
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"
