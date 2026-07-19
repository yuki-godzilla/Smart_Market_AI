"""Causal residual calibration anchored to the frozen conservative forecast.

This module is intentionally evaluation-only.  A small ridge model predicts the
residual around an already-frozen horizon anchor.  At every evaluation origin it
can use only development labels whose targets are already observable.  The more
recent part of that causal history is reserved for a temporal pass/fail gate.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from math import ceil
from typing import Iterable, Literal, Self

import numpy as np
from pydantic import ConfigDict, Field, model_validator

from backend.core.data_contracts import StrictBaseModel
from backend.forecast.adapters import ADVANCED_QUANTILE_ADAPTER_NAME
from backend.forecast.conservative_calibration import (
    CALIBRATION_GROUP_TYPES,
    MAX_ABSOLUTE_CALIBRATED_RETURN,
    MAX_SUBGROUP_ABSOLUTE_RMSE_DEGRADATION,
    MAX_SUBGROUP_RELATIVE_RMSE_DEGRADATION,
    MIN_RELATIVE_RMSE_IMPROVEMENT,
    MIN_SUBGROUP_SAMPLE_COUNT,
    MOVING_AVERAGE_3_MODEL_NAME,
    ConservativeCalibrationObservation,
    HorizonConservativeCalibrationProfile,
    apply_horizon_conditioned_calibration,
)

ANCHORED_RESIDUAL_CALIBRATION_MODEL_NAME = "horizon_anchored_residual_calibration"
ResidualRidgeSpec = Literal["global_ridge", "context_ridge"]
ResidualModelSpec = Literal["anchor_only", "global_ridge", "context_ridge"]
ANCHOR_ONLY_SPEC: Literal["anchor_only"] = "anchor_only"
GLOBAL_RIDGE_SPEC: Literal["global_ridge"] = "global_ridge"
CONTEXT_RIDGE_SPEC: Literal["context_ridge"] = "context_ridge"
RIDGE_SPECS: tuple[ResidualRidgeSpec, ...] = (GLOBAL_RIDGE_SPEC, CONTEXT_RIDGE_SPEC)
BASE_FEATURE_NAMES = (
    "anchor_return",
    "consensus_anchor_spread",
    "quantile_anchor_spread",
    "moving_average_anchor_spread",
)
CONTEXT_FEATURE_NAMES = (
    *BASE_FEATURE_NAMES,
    "market_jp",
    "market_us",
    "asset_etf",
    "regime_uptrend",
    "regime_downtrend",
    "regime_sideways",
)
RIDGE_ALPHA_BY_SPEC = {
    GLOBAL_RIDGE_SPEC: Decimal("10"),
    CONTEXT_RIDGE_SPEC: Decimal("25"),
}
DEFAULT_MIN_TRAINING_SAMPLE_COUNT = 80
DEFAULT_MIN_TRAINING_ORIGIN_COUNT = 3
DEFAULT_MIN_FIT_SAMPLE_COUNT = 40
DEFAULT_MIN_VALIDATION_SAMPLE_COUNT = 20
DEFAULT_INTERNAL_FIT_FRACTION = Decimal("0.7")
DEFAULT_RESIDUAL_CLIP_QUANTILE = Decimal("0.90")
DEFAULT_MAX_ABSOLUTE_RESIDUAL_CORRECTION = Decimal("0.25")
MIN_RESIDUAL_SELECTION_RATE = Decimal("0.50")
RESIDUAL_CALIBRATION_GROUP_TYPES = (
    *CALIBRATION_GROUP_TYPES,
    "period",
    "selection_status",
    "model_spec",
)


class AnchoredResidualCalibrationDecision(StrictBaseModel):
    """Fitted model state and gate result for one horizon/origin boundary."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = ANCHORED_RESIDUAL_CALIBRATION_MODEL_NAME
    horizon_days: int = Field(ge=1)
    as_of: datetime
    status: Literal["selected", "fallback"]
    reason: str = Field(min_length=1)
    selected_spec: ResidualModelSpec
    available_sample_count: int = Field(ge=0)
    available_origin_count: int = Field(ge=0)
    fit_sample_count: int = Field(ge=0)
    validation_sample_count: int = Field(ge=0)
    feature_names: tuple[str, ...]
    feature_means: tuple[Decimal, ...]
    feature_scales: tuple[Decimal, ...]
    coefficients: tuple[Decimal, ...]
    intercept: Decimal
    correction_limit: Decimal = Field(ge=0)
    fit_anchor_rmse: Decimal | None = Field(default=None, ge=0)
    fit_candidate_rmse: Decimal | None = Field(default=None, ge=0)
    fit_relative_rmse_improvement_vs_anchor: Decimal | None = None
    validation_anchor_rmse: Decimal | None = Field(default=None, ge=0)
    validation_candidate_rmse: Decimal | None = Field(default=None, ge=0)
    validation_relative_rmse_improvement_vs_anchor: Decimal | None = None

    @model_validator(mode="after")
    def validate_model_state(self) -> Self:
        size = len(self.feature_names)
        if not (
            len(self.feature_means) == size
            and len(self.feature_scales) == size
            and len(self.coefficients) == size
        ):
            raise ValueError("residual model state lengths must match")
        if any(scale <= 0 for scale in self.feature_scales):
            raise ValueError("residual feature scales must be positive")
        expected_names = _feature_names(self.selected_spec)
        if self.feature_names != expected_names:
            raise ValueError("residual feature names do not match the selected model spec")
        if self.status == "fallback":
            if self.selected_spec != ANCHOR_ONLY_SPEC:
                raise ValueError("fallback decisions must use the frozen anchor")
            if self.intercept != 0 or self.correction_limit != 0:
                raise ValueError("fallback decisions must not apply a residual correction")
        elif self.selected_spec == ANCHOR_ONLY_SPEC:
            raise ValueError("selected decisions must use a ridge model")
        return self


class AnchoredResidualCalibrationPrediction(StrictBaseModel):
    """Residual-corrected center with consensus retained as direction head."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = ANCHORED_RESIDUAL_CALIBRATION_MODEL_NAME
    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    target_at: datetime
    price_center_return: Decimal
    anchor_return: Decimal
    residual_correction: Decimal
    raw_residual_correction: Decimal
    direction_return: Decimal
    original_consensus_return: Decimal
    correction_was_clipped: bool = False
    return_was_capped: bool = False
    decision: AnchoredResidualCalibrationDecision


class AnchoredResidualCalibrationMetric(StrictBaseModel):
    """Paired consensus, frozen-anchor, and residual-candidate metric."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    split: str = Field(min_length=1)
    group_type: str = Field(min_length=1)
    group_value: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    symbol_count: int = Field(ge=0)
    sample_count: int = Field(ge=0)
    consensus_mae: Decimal = Field(ge=0)
    anchor_mae: Decimal = Field(ge=0)
    candidate_mae: Decimal = Field(ge=0)
    consensus_rmse: Decimal = Field(ge=0)
    anchor_rmse: Decimal = Field(ge=0)
    candidate_rmse: Decimal = Field(ge=0)
    relative_rmse_improvement_vs_consensus: Decimal
    relative_rmse_improvement_vs_anchor: Decimal
    consensus_direction_accuracy: Decimal = Field(ge=0, le=1)
    candidate_center_direction_accuracy: Decimal = Field(ge=0, le=1)
    retained_direction_accuracy: Decimal = Field(ge=0, le=1)
    maximum_absolute_candidate_return: Decimal = Field(ge=0)


class AnchoredResidualCalibrationEvaluationReport(StrictBaseModel):
    """Evaluation metrics and conservative runtime-review decision."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = ANCHORED_RESIDUAL_CALIBRATION_MODEL_NAME
    metrics: list[AnchoredResidualCalibrationMetric]
    prediction_count: int = Field(ge=0)
    selected_prediction_count: int = Field(ge=0)
    fallback_prediction_count: int = Field(ge=0)
    selection_rate: Decimal = Field(ge=0, le=1)
    runtime_review_eligible: bool
    gate_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def fit_point_in_time_anchored_residual(
    calibration_history: Iterable[ConservativeCalibrationObservation],
    profile: HorizonConservativeCalibrationProfile,
    *,
    as_of: datetime,
    min_training_sample_count: int = DEFAULT_MIN_TRAINING_SAMPLE_COUNT,
    min_training_origin_count: int = DEFAULT_MIN_TRAINING_ORIGIN_COUNT,
    min_fit_sample_count: int = DEFAULT_MIN_FIT_SAMPLE_COUNT,
    min_validation_sample_count: int = DEFAULT_MIN_VALIDATION_SAMPLE_COUNT,
    internal_fit_fraction: Decimal = DEFAULT_INTERNAL_FIT_FRACTION,
    residual_clip_quantile: Decimal = DEFAULT_RESIDUAL_CLIP_QUANTILE,
    max_absolute_residual_correction: Decimal = DEFAULT_MAX_ABSOLUTE_RESIDUAL_CORRECTION,
) -> AnchoredResidualCalibrationDecision:
    """Fit on older causal history and use newer causal history only as a gate."""

    _validate_fit_parameters(
        as_of=as_of,
        min_training_sample_count=min_training_sample_count,
        min_training_origin_count=min_training_origin_count,
        min_fit_sample_count=min_fit_sample_count,
        min_validation_sample_count=min_validation_sample_count,
        internal_fit_fraction=internal_fit_fraction,
        residual_clip_quantile=residual_clip_quantile,
        max_absolute_residual_correction=max_absolute_residual_correction,
    )
    selected: list[ConservativeCalibrationObservation] = []
    for observation in calibration_history:
        if observation.origin_at.tzinfo is None or observation.target_at.tzinfo is None:
            raise ValueError("calibration timestamps must be timezone-aware")
        if (
            observation.horizon_days == profile.horizon_days
            and observation.target_at <= as_of
            and _has_required_sources(observation)
        ):
            selected.append(observation)
    selected.sort(key=lambda item: (item.origin_at, item.target_at, item.symbol))
    origin_times = sorted({observation.origin_at for observation in selected})
    if len(selected) < min_training_sample_count:
        return _fallback_decision(
            horizon_days=profile.horizon_days,
            as_of=as_of,
            reason="insufficient_history_samples",
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
        )
    if len(origin_times) < min_training_origin_count:
        return _fallback_decision(
            horizon_days=profile.horizon_days,
            as_of=as_of,
            reason="insufficient_history_origins",
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
        )

    fit_origin_count = ceil(Decimal(len(origin_times)) * internal_fit_fraction)
    fit_origin_count = min(max(fit_origin_count, 1), len(origin_times) - 1)
    fit_origins = set(origin_times[:fit_origin_count])
    fit = [item for item in selected if item.origin_at in fit_origins]
    validation = [item for item in selected if item.origin_at not in fit_origins]
    if len(fit) < min_fit_sample_count or len(validation) < min_validation_sample_count:
        return _fallback_decision(
            horizon_days=profile.horizon_days,
            as_of=as_of,
            reason="insufficient_internal_temporal_samples",
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
            fit_sample_count=len(fit),
            validation_sample_count=len(validation),
        )

    anchor_fit = [_anchor_return(item, profile) for item in fit]
    anchor_validation = [_anchor_return(item, profile) for item in validation]
    fit_anchor_rmse = _rmse(
        anchor - observation.actual_return for observation, anchor in zip(fit, anchor_fit)
    )
    candidates: list[tuple[Decimal, int, _FittedResidualModel]] = []
    for spec_index, spec in enumerate(RIDGE_SPECS):
        model = _fit_residual_model(
            fit,
            anchor_fit,
            spec=spec,
            residual_clip_quantile=residual_clip_quantile,
            max_absolute_residual_correction=max_absolute_residual_correction,
        )
        candidate_rmse = _candidate_rmse(fit, anchor_fit, model)
        candidates.append((candidate_rmse, spec_index, model))
    fit_candidate_rmse, _spec_index, chosen = min(candidates, key=lambda item: item[:2])
    fit_improvement = _relative_improvement(fit_anchor_rmse, fit_candidate_rmse)
    validation_anchor_rmse = _rmse(
        anchor - observation.actual_return
        for observation, anchor in zip(validation, anchor_validation)
    )
    validation_candidate_rmse = _candidate_rmse(validation, anchor_validation, chosen)
    validation_improvement = _relative_improvement(
        validation_anchor_rmse,
        validation_candidate_rmse,
    )
    fit_anchor_metric = _metric(fit_anchor_rmse)
    fit_candidate_metric = _metric(fit_candidate_rmse)
    validation_anchor_metric = _metric(validation_anchor_rmse)
    validation_candidate_metric = _metric(validation_candidate_rmse)
    if fit_improvement < MIN_RELATIVE_RMSE_IMPROVEMENT:
        return _fallback_decision(
            horizon_days=profile.horizon_days,
            as_of=as_of,
            reason="fit_improvement_vs_anchor_gate_failed",
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
            fit_sample_count=len(fit),
            validation_sample_count=len(validation),
            fit_anchor_rmse=fit_anchor_metric,
            fit_candidate_rmse=fit_candidate_metric,
            fit_relative_rmse_improvement_vs_anchor=fit_improvement,
            validation_anchor_rmse=validation_anchor_metric,
            validation_candidate_rmse=validation_candidate_metric,
            validation_relative_rmse_improvement_vs_anchor=validation_improvement,
        )
    if validation_improvement < MIN_RELATIVE_RMSE_IMPROVEMENT:
        return _fallback_decision(
            horizon_days=profile.horizon_days,
            as_of=as_of,
            reason="validation_improvement_vs_anchor_gate_failed",
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
            fit_sample_count=len(fit),
            validation_sample_count=len(validation),
            fit_anchor_rmse=fit_anchor_metric,
            fit_candidate_rmse=fit_candidate_metric,
            fit_relative_rmse_improvement_vs_anchor=fit_improvement,
            validation_anchor_rmse=validation_anchor_metric,
            validation_candidate_rmse=validation_candidate_metric,
            validation_relative_rmse_improvement_vs_anchor=validation_improvement,
        )
    return AnchoredResidualCalibrationDecision(
        horizon_days=profile.horizon_days,
        as_of=as_of,
        status="selected",
        reason="fit_and_validation_anchor_gates_passed",
        selected_spec=chosen.spec,
        available_sample_count=len(selected),
        available_origin_count=len(origin_times),
        fit_sample_count=len(fit),
        validation_sample_count=len(validation),
        feature_names=chosen.feature_names,
        feature_means=chosen.feature_means,
        feature_scales=chosen.feature_scales,
        coefficients=chosen.coefficients,
        intercept=chosen.intercept,
        correction_limit=chosen.correction_limit,
        fit_anchor_rmse=fit_anchor_metric,
        fit_candidate_rmse=fit_candidate_metric,
        fit_relative_rmse_improvement_vs_anchor=fit_improvement,
        validation_anchor_rmse=validation_anchor_metric,
        validation_candidate_rmse=validation_candidate_metric,
        validation_relative_rmse_improvement_vs_anchor=validation_improvement,
    )


def apply_anchored_residual_calibration(
    observation: ConservativeCalibrationObservation,
    profile: HorizonConservativeCalibrationProfile,
    decision: AnchoredResidualCalibrationDecision,
) -> AnchoredResidualCalibrationPrediction:
    """Apply a fitted residual correction without using the observation label."""

    if observation.horizon_days != profile.horizon_days:
        raise ValueError("observation and anchor profile horizons do not match")
    if observation.horizon_days != decision.horizon_days:
        raise ValueError("observation and residual decision horizons do not match")
    if observation.origin_at != decision.as_of:
        raise ValueError("residual decision must be made at the observation origin")
    anchor = _anchor_return(observation, profile)
    raw_correction = _predict_residual(observation, anchor, decision)
    correction = max(-decision.correction_limit, min(decision.correction_limit, raw_correction))
    raw_return = anchor + correction
    capped_return = max(
        -MAX_ABSOLUTE_CALIBRATED_RETURN,
        min(MAX_ABSOLUTE_CALIBRATED_RETURN, raw_return),
    )
    return AnchoredResidualCalibrationPrediction(
        symbol=observation.symbol,
        horizon_days=observation.horizon_days,
        origin_at=observation.origin_at,
        target_at=observation.target_at,
        price_center_return=_return_value(capped_return),
        anchor_return=_return_value(anchor),
        residual_correction=_return_value(correction),
        raw_residual_correction=_return_value(raw_correction),
        direction_return=observation.consensus_return,
        original_consensus_return=observation.consensus_return,
        correction_was_clipped=correction != raw_correction,
        return_was_capped=capped_return != raw_return,
        decision=decision,
    )


def evaluate_point_in_time_anchored_residual_calibration(
    calibration_history: Iterable[ConservativeCalibrationObservation],
    evaluation_observations: Iterable[ConservativeCalibrationObservation],
    profiles: Iterable[HorizonConservativeCalibrationProfile],
    *,
    min_training_sample_count: int = DEFAULT_MIN_TRAINING_SAMPLE_COUNT,
    min_training_origin_count: int = DEFAULT_MIN_TRAINING_ORIGIN_COUNT,
    min_fit_sample_count: int = DEFAULT_MIN_FIT_SAMPLE_COUNT,
    min_validation_sample_count: int = DEFAULT_MIN_VALIDATION_SAMPLE_COUNT,
) -> list[AnchoredResidualCalibrationPrediction]:
    """Evaluate causal residual decisions with one decision per horizon/origin."""

    history = list(calibration_history)
    profile_by_horizon = {profile.horizon_days: profile for profile in profiles}
    if not profile_by_horizon:
        raise ValueError("at least one frozen anchor profile is required")
    evaluation = sorted(
        evaluation_observations,
        key=lambda item: (item.origin_at, item.horizon_days, item.symbol),
    )
    decisions: dict[tuple[int, datetime], AnchoredResidualCalibrationDecision] = {}
    predictions: list[AnchoredResidualCalibrationPrediction] = []
    for observation in evaluation:
        profile = profile_by_horizon.get(observation.horizon_days)
        if profile is None:
            raise ValueError(f"missing anchor profile for horizon {observation.horizon_days}")
        key = (observation.horizon_days, observation.origin_at)
        decision = decisions.get(key)
        if decision is None:
            decision = fit_point_in_time_anchored_residual(
                history,
                profile,
                as_of=observation.origin_at,
                min_training_sample_count=min_training_sample_count,
                min_training_origin_count=min_training_origin_count,
                min_fit_sample_count=min_fit_sample_count,
                min_validation_sample_count=min_validation_sample_count,
            )
            decisions[key] = decision
        predictions.append(apply_anchored_residual_calibration(observation, profile, decision))
    return predictions


def evaluate_anchored_residual_calibration_metrics(
    observations: Iterable[ConservativeCalibrationObservation],
    predictions: Iterable[AnchoredResidualCalibrationPrediction],
) -> list[AnchoredResidualCalibrationMetric]:
    """Compare residual candidate with both consensus and frozen anchor."""

    selected_observations = list(observations)
    selected_predictions = list(predictions)
    by_key = {_point_key(item): item for item in selected_predictions}
    if len(selected_observations) != len(selected_predictions) or len(by_key) != len(
        selected_predictions
    ):
        raise ValueError("residual predictions must match observations one-to-one")
    grouped: dict[
        tuple[str, str, str, int],
        list[tuple[ConservativeCalibrationObservation, AnchoredResidualCalibrationPrediction]],
    ] = defaultdict(list)
    for observation in selected_observations:
        prediction = by_key.get(_point_key(observation))
        if prediction is None:
            raise ValueError(f"residual prediction is missing for {_point_key(observation)}")
        for group_type in RESIDUAL_CALIBRATION_GROUP_TYPES:
            group_value = _group_value(observation, prediction, group_type)
            grouped[(observation.split, group_type, group_value, observation.horizon_days)].append(
                (observation, prediction)
            )

    metrics: list[AnchoredResidualCalibrationMetric] = []
    for (split, group_type, group_value, horizon), pairs in sorted(grouped.items()):
        consensus_errors = [
            observation.consensus_return - observation.actual_return
            for observation, _prediction in pairs
        ]
        anchor_errors = [
            prediction.anchor_return - observation.actual_return
            for observation, prediction in pairs
        ]
        candidate_errors = [
            prediction.price_center_return - observation.actual_return
            for observation, prediction in pairs
        ]
        consensus_rmse = _rmse(consensus_errors)
        anchor_rmse = _rmse(anchor_errors)
        candidate_rmse = _rmse(candidate_errors)
        consensus_direction = _direction_accuracy(
            (observation.consensus_return, observation.actual_return)
            for observation, _prediction in pairs
        )
        center_direction = _direction_accuracy(
            (prediction.price_center_return, observation.actual_return)
            for observation, prediction in pairs
        )
        metrics.append(
            AnchoredResidualCalibrationMetric(
                split=split,
                group_type=group_type,
                group_value=group_value,
                horizon_days=horizon,
                symbol_count=len({observation.symbol for observation, _prediction in pairs}),
                sample_count=len(pairs),
                consensus_mae=_metric(_mean(abs(error) for error in consensus_errors)),
                anchor_mae=_metric(_mean(abs(error) for error in anchor_errors)),
                candidate_mae=_metric(_mean(abs(error) for error in candidate_errors)),
                consensus_rmse=_metric(consensus_rmse),
                anchor_rmse=_metric(anchor_rmse),
                candidate_rmse=_metric(candidate_rmse),
                relative_rmse_improvement_vs_consensus=_relative_improvement(
                    consensus_rmse,
                    candidate_rmse,
                ),
                relative_rmse_improvement_vs_anchor=_relative_improvement(
                    anchor_rmse,
                    candidate_rmse,
                ),
                consensus_direction_accuracy=_metric(consensus_direction),
                candidate_center_direction_accuracy=_metric(center_direction),
                retained_direction_accuracy=_metric(consensus_direction),
                maximum_absolute_candidate_return=_metric(
                    max(abs(prediction.price_center_return) for _observation, prediction in pairs)
                ),
            )
        )
    return metrics


def build_anchored_residual_calibration_report(
    metrics: Iterable[AnchoredResidualCalibrationMetric],
    predictions: Iterable[AnchoredResidualCalibrationPrediction],
    *,
    required_splits: tuple[str, ...],
) -> AnchoredResidualCalibrationEvaluationReport:
    """Gate against the stronger frozen anchor and the original consensus."""

    if not required_splits:
        raise ValueError("required_splits must not be empty")
    selected_metrics = list(metrics)
    selected_predictions = list(predictions)
    horizons = sorted(
        {metric.horizon_days for metric in selected_metrics if metric.group_type == "overall"}
    )
    failures: list[str] = []
    if not horizons:
        failures.append("overall horizon metricがありません。")
    for split in required_splits:
        for horizon in horizons:
            overall = next(
                (
                    metric
                    for metric in selected_metrics
                    if metric.split == split
                    and metric.group_type == "overall"
                    and metric.horizon_days == horizon
                ),
                None,
            )
            if overall is None or overall.sample_count == 0:
                failures.append(f"{split} {horizon}日: overall sampleがありません。")
                continue
            if overall.relative_rmse_improvement_vs_anchor < MIN_RELATIVE_RMSE_IMPROVEMENT:
                failures.append(
                    f"{split} {horizon}日: 固定anchor比RMSE改善が1%未満です"
                    f"（{overall.relative_rmse_improvement_vs_anchor * Decimal('100'):.2f}%）。"
                )
            if overall.relative_rmse_improvement_vs_consensus < MIN_RELATIVE_RMSE_IMPROVEMENT:
                failures.append(
                    f"{split} {horizon}日: Consensus比RMSE改善が1%未満です"
                    f"（{overall.relative_rmse_improvement_vs_consensus * Decimal('100'):.2f}%）。"
                )
            if overall.retained_direction_accuracy < overall.consensus_direction_accuracy:
                failures.append(f"{split} {horizon}日: retained directionが悪化しました。")
            if overall.maximum_absolute_candidate_return > MAX_ABSOLUTE_CALIBRATED_RETURN:
                failures.append(f"{split} {horizon}日: return安全上限を超えました。")

    for metric in selected_metrics:
        if (
            metric.split not in required_splits
            or metric.group_type in ("overall", "selection_status", "model_spec")
            or metric.sample_count < MIN_SUBGROUP_SAMPLE_COUNT
        ):
            continue
        absolute_degradation = metric.candidate_rmse - metric.anchor_rmse
        relative_degradation = (
            absolute_degradation / metric.anchor_rmse
            if metric.anchor_rmse > 0
            else Decimal("Infinity")
        )
        if (
            relative_degradation > MAX_SUBGROUP_RELATIVE_RMSE_DEGRADATION
            and absolute_degradation > MAX_SUBGROUP_ABSOLUTE_RMSE_DEGRADATION
        ):
            failures.append(
                f"{metric.split} {metric.horizon_days}日 {metric.group_type}="
                f"{metric.group_value}: 固定anchor比RMSEが重大劣化しました"
                f"（{relative_degradation * Decimal('100'):.2f}%）。"
            )

    selected_count = sum(
        prediction.decision.status == "selected" for prediction in selected_predictions
    )
    prediction_count = len(selected_predictions)
    selection_rate = (
        Decimal(selected_count) / Decimal(prediction_count) if prediction_count else Decimal("0")
    )
    if selection_rate < MIN_RESIDUAL_SELECTION_RATE:
        failures.append(
            "residual補正の採用率が50%未満です" f"（{selection_rate * Decimal('100'):.2f}%）。"
        )
    failures = list(dict.fromkeys(failures))
    return AnchoredResidualCalibrationEvaluationReport(
        metrics=selected_metrics,
        prediction_count=prediction_count,
        selected_prediction_count=selected_count,
        fallback_prediction_count=prediction_count - selected_count,
        selection_rate=_metric(selection_rate),
        runtime_review_eligible=not failures and bool(selected_predictions),
        gate_reasons=failures
        or [
            "全required split / horizonで固定anchorとConsensusを各1%以上改善しました。",
            "固定anchor比の重大なsubgroup劣化を検出しませんでした。",
            "direction head、安全上限、residual補正採用率50%以上を維持しました。",
        ],
        warnings=[
            "評価専用shadow候補です。Forecast、Cockpit、Ranking、スコアを変更しません。",
            "監査結果を使った係数・alpha・feature・gateの再調整は禁止します。",
        ],
    )


class _FittedResidualModel:
    def __init__(
        self,
        *,
        spec: ResidualRidgeSpec,
        feature_names: tuple[str, ...],
        feature_means: tuple[Decimal, ...],
        feature_scales: tuple[Decimal, ...],
        coefficients: tuple[Decimal, ...],
        intercept: Decimal,
        correction_limit: Decimal,
    ) -> None:
        self.spec = spec
        self.feature_names = feature_names
        self.feature_means = feature_means
        self.feature_scales = feature_scales
        self.coefficients = coefficients
        self.intercept = intercept
        self.correction_limit = correction_limit


def _fit_residual_model(
    observations: list[ConservativeCalibrationObservation],
    anchors: list[Decimal],
    *,
    spec: ResidualRidgeSpec,
    residual_clip_quantile: Decimal,
    max_absolute_residual_correction: Decimal,
) -> _FittedResidualModel:
    feature_names = _feature_names(spec)
    matrix = np.asarray(
        [
            [float(value) for value in _features(observation, anchor, spec)]
            for observation, anchor in zip(observations, anchors)
        ],
        dtype=np.float64,
    )
    target = np.asarray(
        [
            float(observation.actual_return - anchor)
            for observation, anchor in zip(observations, anchors)
        ],
        dtype=np.float64,
    )
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales <= 1e-12] = 1.0
    standardized = (matrix - means) / scales
    centered_target = target - target.mean()
    alpha = float(RIDGE_ALPHA_BY_SPEC[spec])
    gram = standardized.T @ standardized + alpha * np.eye(standardized.shape[1])
    coefficients = np.linalg.solve(gram, standardized.T @ centered_target)
    residual_limit = min(
        float(max_absolute_residual_correction),
        float(np.quantile(np.abs(target), float(residual_clip_quantile), method="higher")),
    )
    return _FittedResidualModel(
        spec=spec,
        feature_names=feature_names,
        feature_means=tuple(_decimal(value) for value in means),
        feature_scales=tuple(_decimal(value) for value in scales),
        coefficients=tuple(_decimal(value) for value in coefficients),
        intercept=_decimal(target.mean()),
        correction_limit=_decimal(residual_limit),
    )


def _candidate_rmse(
    observations: list[ConservativeCalibrationObservation],
    anchors: list[Decimal],
    model: _FittedResidualModel,
) -> Decimal:
    return _rmse(
        anchor + _predict_from_model(observation, anchor, model) - observation.actual_return
        for observation, anchor in zip(observations, anchors)
    )


def _predict_residual(
    observation: ConservativeCalibrationObservation,
    anchor: Decimal,
    decision: AnchoredResidualCalibrationDecision,
) -> Decimal:
    if decision.status == "fallback":
        return Decimal("0")
    values = _features(observation, anchor, decision.selected_spec)
    return decision.intercept + sum(
        (
            ((value - mean) / scale) * coefficient
            for value, mean, scale, coefficient in zip(
                values,
                decision.feature_means,
                decision.feature_scales,
                decision.coefficients,
            )
        ),
        Decimal("0"),
    )


def _predict_from_model(
    observation: ConservativeCalibrationObservation,
    anchor: Decimal,
    model: _FittedResidualModel,
) -> Decimal:
    values = _features(observation, anchor, model.spec)
    raw = model.intercept + sum(
        (
            ((value - mean) / scale) * coefficient
            for value, mean, scale, coefficient in zip(
                values,
                model.feature_means,
                model.feature_scales,
                model.coefficients,
            )
        ),
        Decimal("0"),
    )
    return max(-model.correction_limit, min(model.correction_limit, raw))


def _features(
    observation: ConservativeCalibrationObservation,
    anchor: Decimal,
    spec: str,
) -> tuple[Decimal, ...]:
    quantile = observation.conservative_returns[ADVANCED_QUANTILE_ADAPTER_NAME]
    moving_average = observation.conservative_returns[MOVING_AVERAGE_3_MODEL_NAME]
    base = (
        anchor,
        observation.consensus_return - anchor,
        quantile - anchor,
        moving_average - anchor,
    )
    if spec == GLOBAL_RIDGE_SPEC:
        return base
    if spec == CONTEXT_RIDGE_SPEC:
        market = observation.market.strip().lower()
        asset_type = observation.asset_type.strip().lower()
        regime = observation.regime.strip().lower()
        return (
            *base,
            Decimal(market == "jp"),
            Decimal(market == "us"),
            Decimal(asset_type == "etf"),
            Decimal(regime == "uptrend"),
            Decimal(regime == "downtrend"),
            Decimal(regime == "sideways"),
        )
    if spec == ANCHOR_ONLY_SPEC:
        return ()
    raise ValueError(f"unknown residual model spec: {spec}")


def _feature_names(spec: str) -> tuple[str, ...]:
    if spec == GLOBAL_RIDGE_SPEC:
        return BASE_FEATURE_NAMES
    if spec == CONTEXT_RIDGE_SPEC:
        return CONTEXT_FEATURE_NAMES
    if spec == ANCHOR_ONLY_SPEC:
        return ()
    raise ValueError(f"unknown residual model spec: {spec}")


def _anchor_return(
    observation: ConservativeCalibrationObservation,
    profile: HorizonConservativeCalibrationProfile,
) -> Decimal:
    return apply_horizon_conditioned_calibration(observation, profile).price_center_return


def _has_required_sources(observation: ConservativeCalibrationObservation) -> bool:
    return {
        ADVANCED_QUANTILE_ADAPTER_NAME,
        MOVING_AVERAGE_3_MODEL_NAME,
    }.issubset(observation.conservative_returns)


def _fallback_decision(
    *,
    horizon_days: int,
    as_of: datetime,
    reason: str,
    available_sample_count: int,
    available_origin_count: int,
    fit_sample_count: int = 0,
    validation_sample_count: int = 0,
    fit_anchor_rmse: Decimal | None = None,
    fit_candidate_rmse: Decimal | None = None,
    fit_relative_rmse_improvement_vs_anchor: Decimal | None = None,
    validation_anchor_rmse: Decimal | None = None,
    validation_candidate_rmse: Decimal | None = None,
    validation_relative_rmse_improvement_vs_anchor: Decimal | None = None,
) -> AnchoredResidualCalibrationDecision:
    return AnchoredResidualCalibrationDecision(
        horizon_days=horizon_days,
        as_of=as_of,
        status="fallback",
        reason=reason,
        selected_spec=ANCHOR_ONLY_SPEC,
        available_sample_count=available_sample_count,
        available_origin_count=available_origin_count,
        fit_sample_count=fit_sample_count,
        validation_sample_count=validation_sample_count,
        feature_names=(),
        feature_means=(),
        feature_scales=(),
        coefficients=(),
        intercept=Decimal("0"),
        correction_limit=Decimal("0"),
        fit_anchor_rmse=fit_anchor_rmse,
        fit_candidate_rmse=fit_candidate_rmse,
        fit_relative_rmse_improvement_vs_anchor=fit_relative_rmse_improvement_vs_anchor,
        validation_anchor_rmse=validation_anchor_rmse,
        validation_candidate_rmse=validation_candidate_rmse,
        validation_relative_rmse_improvement_vs_anchor=(
            validation_relative_rmse_improvement_vs_anchor
        ),
    )


def _validate_fit_parameters(
    *,
    as_of: datetime,
    min_training_sample_count: int,
    min_training_origin_count: int,
    min_fit_sample_count: int,
    min_validation_sample_count: int,
    internal_fit_fraction: Decimal,
    residual_clip_quantile: Decimal,
    max_absolute_residual_correction: Decimal,
) -> None:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if min_training_sample_count < 1:
        raise ValueError("min_training_sample_count must be positive")
    if min_training_origin_count < 2:
        raise ValueError("min_training_origin_count must be at least 2")
    if min_fit_sample_count < 1 or min_validation_sample_count < 1:
        raise ValueError("fit and validation sample minimums must be positive")
    if internal_fit_fraction <= 0 or internal_fit_fraction >= 1:
        raise ValueError("internal_fit_fraction must be between 0 and 1")
    if residual_clip_quantile <= 0 or residual_clip_quantile > 1:
        raise ValueError("residual_clip_quantile must be in (0, 1]")
    if max_absolute_residual_correction <= 0:
        raise ValueError("max_absolute_residual_correction must be positive")


def _point_key(
    item: ConservativeCalibrationObservation | AnchoredResidualCalibrationPrediction,
) -> tuple[str, int, datetime, datetime]:
    return (item.symbol, item.horizon_days, item.origin_at, item.target_at)


def _group_value(
    observation: ConservativeCalibrationObservation,
    prediction: AnchoredResidualCalibrationPrediction,
    group_type: str,
) -> str:
    if group_type == "overall":
        return "all"
    if group_type == "period":
        return _period_label(observation.origin_at.year)
    if group_type == "selection_status":
        return prediction.decision.status
    if group_type == "model_spec":
        return prediction.decision.selected_spec
    return str(getattr(observation, group_type))


def _period_label(year: int) -> str:
    if year <= 2019:
        return "through_2019"
    if year <= 2021:
        return "2020_2021"
    if year <= 2023:
        return "2022_2023"
    return "2024_plus"


def _rmse(errors: Iterable[Decimal]) -> Decimal:
    selected = list(errors)
    if not selected:
        return Decimal("0")
    mean_square = sum((error * error for error in selected), Decimal("0")) / Decimal(len(selected))
    return mean_square.sqrt()


def _mean(values: Iterable[Decimal]) -> Decimal:
    selected = list(values)
    if not selected:
        return Decimal("0")
    return sum(selected, Decimal("0")) / Decimal(len(selected))


def _direction_accuracy(values: Iterable[tuple[Decimal, Decimal]]) -> Decimal:
    selected = list(values)
    if not selected:
        return Decimal("0")
    matches = sum(_sign(predicted) == _sign(actual) for predicted, actual in selected)
    return Decimal(matches) / Decimal(len(selected))


def _relative_improvement(baseline: Decimal, candidate: Decimal) -> Decimal:
    if baseline <= 0:
        return Decimal("0.000000")
    return _metric((baseline - candidate) / baseline)


def _sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _decimal(value: float | np.floating) -> Decimal:
    return Decimal(str(float(value)))


def _metric(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _return_value(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
