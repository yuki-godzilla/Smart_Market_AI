"""Point-in-time adaptive calibration for evaluation-only forecast price centers.

The candidate learns non-negative ensemble weights only from calibration labels
that were already observable at each evaluation origin.  Evaluation symbols are
expected to be disjoint from calibration symbols.  Direction remains the current
forecast consensus and runtime consumers are deliberately not connected here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from math import ceil
from typing import Iterable, Literal, Self

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
    ConservativeCalibrationMetric,
    ConservativeCalibrationObservation,
)
from backend.forecast.evaluation import CONSENSUS_MODEL_NAME

ADAPTIVE_CALIBRATION_MODEL_NAME = "point_in_time_adaptive_calibration"
ZERO_RETURN_MODEL_NAME = "zero_return"
ADAPTIVE_SOURCE_MODEL_NAMES = (
    CONSENSUS_MODEL_NAME,
    ADVANCED_QUANTILE_ADAPTER_NAME,
    MOVING_AVERAGE_3_MODEL_NAME,
    ZERO_RETURN_MODEL_NAME,
)
ADAPTIVE_CALIBRATION_GROUP_TYPES = (
    *CALIBRATION_GROUP_TYPES,
    "period",
    "selection_status",
)
DEFAULT_MIN_TRAINING_SAMPLE_COUNT = 40
DEFAULT_MIN_TRAINING_ORIGIN_COUNT = 3
DEFAULT_MIN_FIT_SAMPLE_COUNT = 20
DEFAULT_MIN_VALIDATION_SAMPLE_COUNT = 10
DEFAULT_INTERNAL_FIT_FRACTION = Decimal("0.7")
MIN_ADAPTIVE_SELECTION_RATE = Decimal("0.50")


class AdaptiveCalibrationWeightDecision(StrictBaseModel):
    """Causal weight decision available at one asset/horizon/origin boundary."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = ADAPTIVE_CALIBRATION_MODEL_NAME
    asset_type: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    as_of: datetime
    status: Literal["selected", "fallback"]
    reason: str = Field(min_length=1)
    available_sample_count: int = Field(ge=0)
    available_origin_count: int = Field(ge=0)
    fit_sample_count: int = Field(ge=0)
    validation_sample_count: int = Field(ge=0)
    weights: dict[str, Decimal]
    fit_consensus_rmse: Decimal | None = Field(default=None, ge=0)
    fit_candidate_rmse: Decimal | None = Field(default=None, ge=0)
    fit_relative_rmse_improvement: Decimal | None = None
    validation_consensus_rmse: Decimal | None = Field(default=None, ge=0)
    validation_candidate_rmse: Decimal | None = Field(default=None, ge=0)
    validation_relative_rmse_improvement: Decimal | None = None

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        if set(self.weights) != set(ADAPTIVE_SOURCE_MODEL_NAMES):
            raise ValueError("adaptive weights must contain every configured source model")
        if any(weight < 0 or weight > 1 for weight in self.weights.values()):
            raise ValueError("adaptive weights must stay between 0 and 1")
        if sum(self.weights.values(), Decimal("0")) != Decimal("1"):
            raise ValueError("adaptive weights must sum to 1")
        if self.status == "fallback" and self.weights != _consensus_only_weights():
            raise ValueError("fallback decisions must retain the current consensus")
        return self


class AdaptiveCalibrationPrediction(StrictBaseModel):
    """Adaptive center prediction with the original consensus direction retained."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = ADAPTIVE_CALIBRATION_MODEL_NAME
    symbol: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    target_at: datetime
    price_center_return: Decimal
    direction_return: Decimal
    original_consensus_return: Decimal
    return_was_capped: bool = False
    decision: AdaptiveCalibrationWeightDecision


class AdaptiveCalibrationEvaluationReport(StrictBaseModel):
    """Evaluation metrics and conservative adoption gate for the adaptive candidate."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = ADAPTIVE_CALIBRATION_MODEL_NAME
    metrics: list[ConservativeCalibrationMetric]
    prediction_count: int = Field(ge=0)
    selected_prediction_count: int = Field(ge=0)
    fallback_prediction_count: int = Field(ge=0)
    selection_rate: Decimal = Field(ge=0, le=1)
    runtime_review_eligible: bool
    gate_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def fit_point_in_time_adaptive_weights(
    calibration_history: Iterable[ConservativeCalibrationObservation],
    *,
    asset_type: str,
    horizon_days: int,
    as_of: datetime,
    min_training_sample_count: int = DEFAULT_MIN_TRAINING_SAMPLE_COUNT,
    min_training_origin_count: int = DEFAULT_MIN_TRAINING_ORIGIN_COUNT,
    min_fit_sample_count: int = DEFAULT_MIN_FIT_SAMPLE_COUNT,
    min_validation_sample_count: int = DEFAULT_MIN_VALIDATION_SAMPLE_COUNT,
    internal_fit_fraction: Decimal = DEFAULT_INTERNAL_FIT_FRACTION,
) -> AdaptiveCalibrationWeightDecision:
    """Choose weights from labels known before ``as_of`` or retain consensus.

    Candidate weights are selected on the older fit origins.  The more recent
    internal validation origins are used only as a pass/fail gate, not to choose
    among candidates.
    """

    normalized_asset_type = asset_type.strip().lower()
    if not normalized_asset_type:
        raise ValueError("asset_type must not be empty")
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

    selected: list[ConservativeCalibrationObservation] = []
    for observation in calibration_history:
        if observation.target_at.tzinfo is None or observation.origin_at.tzinfo is None:
            raise ValueError("calibration timestamps must be timezone-aware")
        if (
            observation.asset_type.strip().lower() == normalized_asset_type
            and observation.horizon_days == horizon_days
            and observation.target_at <= as_of
            and _has_adaptive_sources(observation)
        ):
            selected.append(observation)
    selected.sort(key=lambda item: (item.origin_at, item.target_at, item.symbol))
    origin_times = sorted({observation.origin_at for observation in selected})
    if len(selected) < min_training_sample_count:
        return _fallback_decision(
            asset_type=normalized_asset_type,
            horizon_days=horizon_days,
            as_of=as_of,
            reason="insufficient_history_samples",
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
        )
    if len(origin_times) < min_training_origin_count:
        return _fallback_decision(
            asset_type=normalized_asset_type,
            horizon_days=horizon_days,
            as_of=as_of,
            reason="insufficient_history_origins",
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
        )

    fit_origin_count = ceil(Decimal(len(origin_times)) * internal_fit_fraction)
    fit_origin_count = min(max(fit_origin_count, 1), len(origin_times) - 1)
    fit_origin_times = set(origin_times[:fit_origin_count])
    fit = [observation for observation in selected if observation.origin_at in fit_origin_times]
    validation = [
        observation for observation in selected if observation.origin_at not in fit_origin_times
    ]
    if len(fit) < min_fit_sample_count or len(validation) < min_validation_sample_count:
        return _fallback_decision(
            asset_type=normalized_asset_type,
            horizon_days=horizon_days,
            as_of=as_of,
            reason="insufficient_internal_temporal_samples",
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
            fit_sample_count=len(fit),
            validation_sample_count=len(validation),
        )

    fit_consensus_rmse = _rmse(
        observation.consensus_return - observation.actual_return for observation in fit
    )
    candidates: list[tuple[Decimal, Decimal, int, tuple[Decimal, ...]]] = []
    for weights_tuple in _candidate_weight_grid():
        weights = dict(zip(ADAPTIVE_SOURCE_MODEL_NAMES, weights_tuple))
        candidate_rmse = _weighted_rmse(fit, weights)
        active_model_count = sum(weight > 0 for weight in weights_tuple)
        candidates.append(
            (
                candidate_rmse,
                -weights[CONSENSUS_MODEL_NAME],
                active_model_count,
                weights_tuple,
            )
        )
    fit_candidate_rmse, _negative_consensus, _active_count, chosen_tuple = min(candidates)
    chosen_weights = dict(zip(ADAPTIVE_SOURCE_MODEL_NAMES, chosen_tuple))
    fit_improvement = _relative_improvement(fit_consensus_rmse, fit_candidate_rmse)
    validation_consensus_rmse = _rmse(
        observation.consensus_return - observation.actual_return for observation in validation
    )
    validation_candidate_rmse = _weighted_rmse(validation, chosen_weights)
    validation_improvement = _relative_improvement(
        validation_consensus_rmse,
        validation_candidate_rmse,
    )

    def build_decision(
        *,
        status: Literal["selected", "fallback"],
        reason: str,
        weights: dict[str, Decimal],
    ) -> AdaptiveCalibrationWeightDecision:
        return AdaptiveCalibrationWeightDecision(
            asset_type=normalized_asset_type,
            horizon_days=horizon_days,
            as_of=as_of,
            status=status,
            reason=reason,
            available_sample_count=len(selected),
            available_origin_count=len(origin_times),
            fit_sample_count=len(fit),
            validation_sample_count=len(validation),
            weights=weights,
            fit_consensus_rmse=_metric(fit_consensus_rmse),
            fit_candidate_rmse=_metric(fit_candidate_rmse),
            fit_relative_rmse_improvement=fit_improvement,
            validation_consensus_rmse=_metric(validation_consensus_rmse),
            validation_candidate_rmse=_metric(validation_candidate_rmse),
            validation_relative_rmse_improvement=validation_improvement,
        )

    if fit_improvement < MIN_RELATIVE_RMSE_IMPROVEMENT:
        return build_decision(
            status="fallback",
            reason="fit_improvement_gate_failed",
            weights=_consensus_only_weights(),
        )
    if validation_improvement < MIN_RELATIVE_RMSE_IMPROVEMENT:
        return build_decision(
            status="fallback",
            reason="validation_improvement_gate_failed",
            weights=_consensus_only_weights(),
        )
    return build_decision(
        status="selected",
        reason="fit_and_validation_gates_passed",
        weights=chosen_weights,
    )


def apply_point_in_time_adaptive_calibration(
    observation: ConservativeCalibrationObservation,
    decision: AdaptiveCalibrationWeightDecision,
) -> AdaptiveCalibrationPrediction:
    """Apply a causal decision while retaining the consensus direction head."""

    if observation.asset_type.strip().lower() != decision.asset_type:
        raise ValueError("observation and adaptive decision asset types do not match")
    if observation.horizon_days != decision.horizon_days:
        raise ValueError("observation and adaptive decision horizons do not match")
    if observation.origin_at != decision.as_of:
        raise ValueError("adaptive decision must be made at the observation origin")
    returns = _source_returns(observation)
    raw_return = sum(
        (
            returns[model_name] * decision.weights[model_name]
            for model_name in ADAPTIVE_SOURCE_MODEL_NAMES
        ),
        Decimal("0"),
    )
    capped_return = max(
        -MAX_ABSOLUTE_CALIBRATED_RETURN,
        min(MAX_ABSOLUTE_CALIBRATED_RETURN, raw_return),
    )
    return AdaptiveCalibrationPrediction(
        symbol=observation.symbol,
        asset_type=observation.asset_type.strip().lower(),
        horizon_days=observation.horizon_days,
        origin_at=observation.origin_at,
        target_at=observation.target_at,
        price_center_return=_return_value(capped_return),
        direction_return=observation.consensus_return,
        original_consensus_return=observation.consensus_return,
        return_was_capped=capped_return != raw_return,
        decision=decision,
    )


def evaluate_point_in_time_adaptive_calibration(
    calibration_history: Iterable[ConservativeCalibrationObservation],
    evaluation_observations: Iterable[ConservativeCalibrationObservation],
    *,
    min_training_sample_count: int = DEFAULT_MIN_TRAINING_SAMPLE_COUNT,
    min_training_origin_count: int = DEFAULT_MIN_TRAINING_ORIGIN_COUNT,
    min_fit_sample_count: int = DEFAULT_MIN_FIT_SAMPLE_COUNT,
    min_validation_sample_count: int = DEFAULT_MIN_VALIDATION_SAMPLE_COUNT,
) -> list[AdaptiveCalibrationPrediction]:
    """Evaluate adaptive decisions at each origin without using evaluation labels."""

    history = list(calibration_history)
    evaluation = sorted(
        evaluation_observations,
        key=lambda item: (item.origin_at, item.horizon_days, item.asset_type, item.symbol),
    )
    decisions: dict[tuple[str, int, datetime], AdaptiveCalibrationWeightDecision] = {}
    predictions: list[AdaptiveCalibrationPrediction] = []
    for observation in evaluation:
        key = (
            observation.asset_type.strip().lower(),
            observation.horizon_days,
            observation.origin_at,
        )
        decision = decisions.get(key)
        if decision is None:
            decision = fit_point_in_time_adaptive_weights(
                history,
                asset_type=key[0],
                horizon_days=key[1],
                as_of=key[2],
                min_training_sample_count=min_training_sample_count,
                min_training_origin_count=min_training_origin_count,
                min_fit_sample_count=min_fit_sample_count,
                min_validation_sample_count=min_validation_sample_count,
            )
            decisions[key] = decision
        predictions.append(apply_point_in_time_adaptive_calibration(observation, decision))
    return predictions


def evaluate_adaptive_calibration_metrics(
    observations: Iterable[ConservativeCalibrationObservation],
    predictions: Iterable[AdaptiveCalibrationPrediction],
) -> list[ConservativeCalibrationMetric]:
    """Compare adaptive centers with consensus across temporal and domain groups."""

    selected_observations = list(observations)
    selected_predictions = list(predictions)
    predictions_by_key = {_point_key(prediction): prediction for prediction in selected_predictions}
    if len(selected_predictions) != len(selected_observations) or len(predictions_by_key) != len(
        selected_predictions
    ):
        raise ValueError("adaptive predictions must match observations one-to-one")
    grouped: dict[
        tuple[str, str, str, int],
        list[tuple[ConservativeCalibrationObservation, AdaptiveCalibrationPrediction]],
    ] = defaultdict(list)
    for observation in selected_observations:
        prediction = predictions_by_key.get(_point_key(observation))
        if prediction is None:
            raise ValueError(f"adaptive prediction is missing for {_point_key(observation)}")
        for group_type in ADAPTIVE_CALIBRATION_GROUP_TYPES:
            grouped[
                (
                    observation.split,
                    group_type,
                    _adaptive_group_value(observation, prediction, group_type),
                    observation.horizon_days,
                )
            ].append((observation, prediction))

    metrics: list[ConservativeCalibrationMetric] = []
    for (split, group_type, group_value, horizon), pairs in sorted(grouped.items()):
        consensus_errors = [
            observation.consensus_return - observation.actual_return
            for observation, _prediction in pairs
        ]
        candidate_errors = [
            prediction.price_center_return - observation.actual_return
            for observation, prediction in pairs
        ]
        consensus_rmse = _rmse(consensus_errors)
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
            ConservativeCalibrationMetric(
                split=split,
                group_type=group_type,
                group_value=group_value,
                horizon_days=horizon,
                symbol_count=len({observation.symbol for observation, _prediction in pairs}),
                sample_count=len(pairs),
                consensus_mae=_metric(_mean(abs(error) for error in consensus_errors)),
                candidate_price_mae=_metric(_mean(abs(error) for error in candidate_errors)),
                consensus_rmse=_metric(consensus_rmse),
                candidate_price_rmse=_metric(candidate_rmse),
                relative_rmse_improvement=_relative_improvement(
                    consensus_rmse,
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


def build_adaptive_calibration_report(
    metrics: Iterable[ConservativeCalibrationMetric],
    predictions: Iterable[AdaptiveCalibrationPrediction],
    *,
    required_splits: tuple[str, ...],
) -> AdaptiveCalibrationEvaluationReport:
    """Apply overall, temporal, subgroup, coverage, and safety gates."""

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
            if overall.relative_rmse_improvement < MIN_RELATIVE_RMSE_IMPROVEMENT:
                failures.append(
                    f"{split} {horizon}日: RMSE改善が1%未満です"
                    f"（{overall.relative_rmse_improvement * Decimal('100'):.2f}%）。"
                )
            if overall.retained_direction_accuracy < overall.consensus_direction_accuracy:
                failures.append(f"{split} {horizon}日: retained directionが悪化しました。")
            if overall.maximum_absolute_candidate_return > MAX_ABSOLUTE_CALIBRATED_RETURN:
                failures.append(f"{split} {horizon}日: return安全上限を超えました。")

    for metric in selected_metrics:
        if (
            metric.split not in required_splits
            or metric.group_type in ("overall", "selection_status")
            or metric.sample_count < MIN_SUBGROUP_SAMPLE_COUNT
        ):
            continue
        absolute_degradation = metric.candidate_price_rmse - metric.consensus_rmse
        relative_degradation = (
            absolute_degradation / metric.consensus_rmse
            if metric.consensus_rmse > 0
            else Decimal("Infinity")
        )
        if (
            relative_degradation > MAX_SUBGROUP_RELATIVE_RMSE_DEGRADATION
            and absolute_degradation > MAX_SUBGROUP_ABSOLUTE_RMSE_DEGRADATION
        ):
            failures.append(
                f"{metric.split} {metric.horizon_days}日 {metric.group_type}="
                f"{metric.group_value}: RMSEが重大劣化しました"
                f"（{relative_degradation * Decimal('100'):.2f}%）。"
            )

    selected_count = sum(
        prediction.decision.status == "selected" for prediction in selected_predictions
    )
    prediction_count = len(selected_predictions)
    selection_rate = (
        Decimal(selected_count) / Decimal(prediction_count) if prediction_count else Decimal("0")
    )
    if selection_rate < MIN_ADAPTIVE_SELECTION_RATE:
        failures.append(
            "adaptive weightの採用率が50%未満です" f"（{selection_rate * Decimal('100'):.2f}%）。"
        )
    failures = list(dict.fromkeys(failures))
    gate_reasons = failures or [
        "全required split / horizonでoverall RMSEを1%以上改善しました。",
        "重大なmarket / asset type / regime / period劣化を検出しませんでした。",
        "direction headとreturn安全上限を維持し、adaptive採用率50%以上でした。",
    ]
    return AdaptiveCalibrationEvaluationReport(
        metrics=selected_metrics,
        prediction_count=prediction_count,
        selected_prediction_count=selected_count,
        fallback_prediction_count=prediction_count - selected_count,
        selection_rate=_metric(selection_rate),
        runtime_review_eligible=not failures and bool(selected_predictions),
        gate_reasons=gate_reasons,
        warnings=[
            "評価専用shadow候補です。Forecast、Cockpit、Ranking、スコアを変更しません。",
            "監査結果を使ったweight再調整は禁止し、後日の新期間監査を別途必要とします。",
        ],
    )


def _fallback_decision(
    *,
    asset_type: str,
    horizon_days: int,
    as_of: datetime,
    reason: str,
    available_sample_count: int,
    available_origin_count: int,
    fit_sample_count: int = 0,
    validation_sample_count: int = 0,
) -> AdaptiveCalibrationWeightDecision:
    return AdaptiveCalibrationWeightDecision(
        asset_type=asset_type,
        horizon_days=horizon_days,
        as_of=as_of,
        status="fallback",
        reason=reason,
        available_sample_count=available_sample_count,
        available_origin_count=available_origin_count,
        fit_sample_count=fit_sample_count,
        validation_sample_count=validation_sample_count,
        weights=_consensus_only_weights(),
    )


def _consensus_only_weights() -> dict[str, Decimal]:
    return {
        model_name: Decimal("1") if model_name == CONSENSUS_MODEL_NAME else Decimal("0")
        for model_name in ADAPTIVE_SOURCE_MODEL_NAMES
    }


@lru_cache(maxsize=1)
def _candidate_weight_grid() -> tuple[tuple[Decimal, ...], ...]:
    unit = Decimal("0.1")
    candidates: list[tuple[Decimal, ...]] = []
    for consensus_units in range(11):
        for quantile_units in range(11 - consensus_units):
            for moving_average_units in range(11 - consensus_units - quantile_units):
                zero_units = 10 - consensus_units - quantile_units - moving_average_units
                candidates.append(
                    (
                        Decimal(consensus_units) * unit,
                        Decimal(quantile_units) * unit,
                        Decimal(moving_average_units) * unit,
                        Decimal(zero_units) * unit,
                    )
                )
    return tuple(candidates)


def _has_adaptive_sources(observation: ConservativeCalibrationObservation) -> bool:
    return {
        ADVANCED_QUANTILE_ADAPTER_NAME,
        MOVING_AVERAGE_3_MODEL_NAME,
    }.issubset(observation.conservative_returns)


def _source_returns(
    observation: ConservativeCalibrationObservation,
) -> dict[str, Decimal]:
    if not _has_adaptive_sources(observation):
        raise ValueError("observation is missing adaptive calibration source returns")
    return {
        CONSENSUS_MODEL_NAME: observation.consensus_return,
        ADVANCED_QUANTILE_ADAPTER_NAME: observation.conservative_returns[
            ADVANCED_QUANTILE_ADAPTER_NAME
        ],
        MOVING_AVERAGE_3_MODEL_NAME: observation.conservative_returns[MOVING_AVERAGE_3_MODEL_NAME],
        ZERO_RETURN_MODEL_NAME: Decimal("0"),
    }


def _weighted_return(
    observation: ConservativeCalibrationObservation,
    weights: dict[str, Decimal],
) -> Decimal:
    returns = _source_returns(observation)
    return sum(
        (returns[model_name] * weights[model_name] for model_name in ADAPTIVE_SOURCE_MODEL_NAMES),
        Decimal("0"),
    )


def _weighted_rmse(
    observations: Iterable[ConservativeCalibrationObservation],
    weights: dict[str, Decimal],
) -> Decimal:
    return _rmse(
        _weighted_return(observation, weights) - observation.actual_return
        for observation in observations
    )


def _point_key(
    item: ConservativeCalibrationObservation | AdaptiveCalibrationPrediction,
) -> tuple[str, int, datetime, datetime]:
    return (item.symbol, item.horizon_days, item.origin_at, item.target_at)


def _adaptive_group_value(
    observation: ConservativeCalibrationObservation,
    prediction: AdaptiveCalibrationPrediction,
    group_type: str,
) -> str:
    if group_type == "overall":
        return "all"
    if group_type == "period":
        return _period_label(observation.origin_at.year)
    if group_type == "selection_status":
        return prediction.decision.status
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


def _metric(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _return_value(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
