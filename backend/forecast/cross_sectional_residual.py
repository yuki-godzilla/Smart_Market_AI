"""Evaluation-only nonlinear residual forecast using point-in-time cross sections.

The existing conservative price center remains the anchor and the consensus
remains the direction head.  A small deterministic histogram GBDT may adjust
the anchor only after passing older-fit and newer-validation gates.  At each
origin it can use only labels whose targets have already matured.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from math import ceil
from statistics import median
from typing import Iterable, Literal, TypedDict

import numpy as np
from pydantic import ConfigDict, Field
from sklearn.ensemble import HistGradientBoostingRegressor

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

CROSS_SECTIONAL_RESIDUAL_MODEL_NAME = "point_in_time_cross_sectional_residual_gbdt"
DEFAULT_MIN_TRAINING_SAMPLE_COUNT = 80
DEFAULT_MIN_TRAINING_ORIGIN_COUNT = 4
DEFAULT_MIN_FIT_SAMPLE_COUNT = 50
DEFAULT_MIN_VALIDATION_SAMPLE_COUNT = 20
DEFAULT_MIN_CROSS_SECTION_SIZE = 5
DEFAULT_INTERNAL_FIT_FRACTION = Decimal("0.70")
DEFAULT_RESIDUAL_CLIP_QUANTILE = Decimal("0.90")
DEFAULT_MAX_ABSOLUTE_RESIDUAL_CORRECTION = Decimal("0.25")
MIN_CROSS_SECTIONAL_SELECTION_RATE = Decimal("0.50")

CrossSectionalDecisionStatus = Literal["selected", "fallback"]
CROSS_SECTIONAL_FEATURE_NAMES = (
    "anchor_return",
    "consensus_anchor_spread",
    "quantile_anchor_spread",
    "moving_average_anchor_spread",
    "model_dispersion",
    "anchor_cross_section_rank",
    "consensus_cross_section_rank",
    "quantile_cross_section_rank",
    "moving_average_cross_section_rank",
    "dispersion_cross_section_rank",
    "market_jp",
    "market_us",
    "asset_etf",
    "regime_uptrend",
    "regime_downtrend",
    "regime_sideways",
)
CROSS_SECTIONAL_GROUP_TYPES = (
    *CALIBRATION_GROUP_TYPES,
    "period",
    "selection_status",
)


class CrossSectionalResidualDecision(StrictBaseModel):
    """Causal training boundary and internal gate result for one origin batch."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = CROSS_SECTIONAL_RESIDUAL_MODEL_NAME
    horizon_days: int = Field(ge=1)
    as_of: datetime
    status: CrossSectionalDecisionStatus
    reason: str = Field(min_length=1)
    available_sample_count: int = Field(ge=0)
    available_origin_count: int = Field(ge=0)
    fit_sample_count: int = Field(ge=0)
    validation_sample_count: int = Field(ge=0)
    prediction_cross_section_size: int = Field(ge=0)
    feature_names: tuple[str, ...] = CROSS_SECTIONAL_FEATURE_NAMES
    correction_limit: Decimal = Field(ge=0)
    fit_anchor_rmse: Decimal | None = Field(default=None, ge=0)
    fit_candidate_rmse: Decimal | None = Field(default=None, ge=0)
    fit_relative_rmse_improvement_vs_anchor: Decimal | None = None
    validation_anchor_rmse: Decimal | None = Field(default=None, ge=0)
    validation_candidate_rmse: Decimal | None = Field(default=None, ge=0)
    validation_relative_rmse_improvement_vs_anchor: Decimal | None = None


class CrossSectionalResidualPrediction(StrictBaseModel):
    """Shadow price center with the original consensus retained for direction."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = CROSS_SECTIONAL_RESIDUAL_MODEL_NAME
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
    cross_section_rank: Decimal = Field(ge=0, le=1)
    correction_was_clipped: bool = False
    return_was_capped: bool = False
    decision: CrossSectionalResidualDecision


class CrossSectionalResidualMetric(StrictBaseModel):
    """Paired metric against both consensus and the frozen conservative anchor."""

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


class CrossSectionalResidualEvaluationReport(StrictBaseModel):
    """Metrics plus the conservative runtime-review gate."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = CROSS_SECTIONAL_RESIDUAL_MODEL_NAME
    metrics: list[CrossSectionalResidualMetric]
    prediction_count: int = Field(ge=0)
    selected_prediction_count: int = Field(ge=0)
    fallback_prediction_count: int = Field(ge=0)
    selection_rate: Decimal = Field(ge=0, le=1)
    runtime_review_eligible: bool
    gate_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class _FeatureRow:
    def __init__(
        self,
        observation: ConservativeCalibrationObservation,
        anchor: Decimal,
        values: tuple[Decimal, ...],
    ) -> None:
        self.observation = observation
        self.anchor = anchor
        self.values = values


class _FittedCrossSectionalModel:
    def __init__(
        self,
        estimator: HistGradientBoostingRegressor,
        correction_limit: Decimal,
    ) -> None:
        self.estimator = estimator
        self.correction_limit = correction_limit


class _FallbackArgs(TypedDict):
    horizon_days: int
    as_of: datetime
    available_sample_count: int
    available_origin_count: int
    prediction_cross_section_size: int


class _MetricArgs(TypedDict):
    fit_sample_count: int
    validation_sample_count: int
    fit_anchor_rmse: Decimal
    fit_candidate_rmse: Decimal
    fit_relative_rmse_improvement_vs_anchor: Decimal
    validation_anchor_rmse: Decimal
    validation_candidate_rmse: Decimal
    validation_relative_rmse_improvement_vs_anchor: Decimal


def evaluate_point_in_time_cross_sectional_residual(
    calibration_history: Iterable[ConservativeCalibrationObservation],
    evaluation_observations: Iterable[ConservativeCalibrationObservation],
    profiles: Iterable[HorizonConservativeCalibrationProfile],
    *,
    min_training_sample_count: int = DEFAULT_MIN_TRAINING_SAMPLE_COUNT,
    min_training_origin_count: int = DEFAULT_MIN_TRAINING_ORIGIN_COUNT,
    min_fit_sample_count: int = DEFAULT_MIN_FIT_SAMPLE_COUNT,
    min_validation_sample_count: int = DEFAULT_MIN_VALIDATION_SAMPLE_COUNT,
    min_cross_section_size: int = DEFAULT_MIN_CROSS_SECTION_SIZE,
    internal_fit_fraction: Decimal = DEFAULT_INTERNAL_FIT_FRACTION,
    residual_clip_quantile: Decimal = DEFAULT_RESIDUAL_CLIP_QUANTILE,
    max_absolute_residual_correction: Decimal = DEFAULT_MAX_ABSOLUTE_RESIDUAL_CORRECTION,
    min_samples_leaf: int = 20,
) -> list[CrossSectionalResidualPrediction]:
    """Walk evaluation origins and fit only from already-matured development labels."""

    history = list(calibration_history)
    evaluation = list(evaluation_observations)
    _validate_observations(history, label="calibration")
    _validate_observations(evaluation, label="evaluation")
    profiles_by_horizon = {profile.horizon_days: profile for profile in profiles}
    _validate_parameters(
        min_training_sample_count=min_training_sample_count,
        min_training_origin_count=min_training_origin_count,
        min_fit_sample_count=min_fit_sample_count,
        min_validation_sample_count=min_validation_sample_count,
        min_cross_section_size=min_cross_section_size,
        internal_fit_fraction=internal_fit_fraction,
        residual_clip_quantile=residual_clip_quantile,
        max_absolute_residual_correction=max_absolute_residual_correction,
        min_samples_leaf=min_samples_leaf,
    )
    missing = {item.horizon_days for item in evaluation} - set(profiles_by_horizon)
    if missing:
        raise ValueError(f"missing profiles for horizons: {sorted(missing)}")
    grouped: dict[tuple[int, datetime], list[ConservativeCalibrationObservation]] = defaultdict(
        list
    )
    for item in evaluation:
        grouped[(item.horizon_days, item.origin_at)].append(item)

    predictions: list[CrossSectionalResidualPrediction] = []
    for (horizon, origin_at), cross_section in sorted(grouped.items()):
        cross_section.sort(key=lambda item: item.symbol)
        profile = profiles_by_horizon[horizon]
        decision, fitted = _fit_point_in_time_cross_sectional_model(
            history,
            profile,
            as_of=origin_at,
            prediction_cross_section_size=len(cross_section),
            min_training_sample_count=min_training_sample_count,
            min_training_origin_count=min_training_origin_count,
            min_fit_sample_count=min_fit_sample_count,
            min_validation_sample_count=min_validation_sample_count,
            min_cross_section_size=min_cross_section_size,
            internal_fit_fraction=internal_fit_fraction,
            residual_clip_quantile=residual_clip_quantile,
            max_absolute_residual_correction=max_absolute_residual_correction,
            min_samples_leaf=min_samples_leaf,
        )
        feature_rows = _build_feature_rows(cross_section, profile)
        for row in feature_rows:
            raw_correction = (
                Decimal("0")
                if fitted is None
                else _decimal(fitted.estimator.predict(_matrix([row]))[0])
            )
            correction = max(
                -decision.correction_limit,
                min(decision.correction_limit, raw_correction),
            )
            raw_return = row.anchor + correction
            capped_return = max(
                -MAX_ABSOLUTE_CALIBRATED_RETURN,
                min(MAX_ABSOLUTE_CALIBRATED_RETURN, raw_return),
            )
            predictions.append(
                CrossSectionalResidualPrediction(
                    symbol=row.observation.symbol,
                    horizon_days=horizon,
                    origin_at=row.observation.origin_at,
                    target_at=row.observation.target_at,
                    price_center_return=_return_value(capped_return),
                    anchor_return=_return_value(row.anchor),
                    residual_correction=_return_value(correction),
                    raw_residual_correction=_return_value(raw_correction),
                    direction_return=row.observation.consensus_return,
                    original_consensus_return=row.observation.consensus_return,
                    cross_section_rank=_metric(row.values[5]),
                    correction_was_clipped=correction != raw_correction,
                    return_was_capped=capped_return != raw_return,
                    decision=decision,
                )
            )
    return predictions


def evaluate_cross_sectional_residual_metrics(
    observations: Iterable[ConservativeCalibrationObservation],
    predictions: Iterable[CrossSectionalResidualPrediction],
) -> list[CrossSectionalResidualMetric]:
    """Measure overall and subgroup performance with paired observations."""

    observation_list = list(observations)
    observation_keys = [_point_key(item) for item in observation_list]
    if len(set(observation_keys)) != len(observation_keys):
        raise ValueError("observations must not contain duplicate points")
    observations_by_key = {_point_key(item): item for item in observation_list}
    prediction_list = list(predictions)
    prediction_keys = [_point_key(item) for item in prediction_list]
    if len(set(prediction_keys)) != len(prediction_keys):
        raise ValueError("predictions must not contain duplicate points")
    if set(prediction_keys) != set(observations_by_key):
        raise ValueError("predictions and observations must cover identical points")
    grouped: dict[
        tuple[str, str, str, int],
        list[tuple[ConservativeCalibrationObservation, CrossSectionalResidualPrediction]],
    ] = defaultdict(list)
    for prediction in prediction_list:
        observation = observations_by_key[_point_key(prediction)]
        for group_type in CROSS_SECTIONAL_GROUP_TYPES:
            grouped[
                (
                    observation.split,
                    group_type,
                    _group_value(observation, prediction, group_type),
                    observation.horizon_days,
                )
            ].append((observation, prediction))

    metrics: list[CrossSectionalResidualMetric] = []
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
        candidate_direction = _direction_accuracy(
            (prediction.price_center_return, observation.actual_return)
            for observation, prediction in pairs
        )
        metrics.append(
            CrossSectionalResidualMetric(
                split=split,
                group_type=group_type,
                group_value=group_value,
                horizon_days=horizon,
                symbol_count=len({observation.symbol for observation, _prediction in pairs}),
                sample_count=len(pairs),
                consensus_mae=_metric(_mean(abs(item) for item in consensus_errors)),
                anchor_mae=_metric(_mean(abs(item) for item in anchor_errors)),
                candidate_mae=_metric(_mean(abs(item) for item in candidate_errors)),
                consensus_rmse=_metric(consensus_rmse),
                anchor_rmse=_metric(anchor_rmse),
                candidate_rmse=_metric(candidate_rmse),
                relative_rmse_improvement_vs_consensus=_relative_improvement(
                    consensus_rmse, candidate_rmse
                ),
                relative_rmse_improvement_vs_anchor=_relative_improvement(
                    anchor_rmse, candidate_rmse
                ),
                consensus_direction_accuracy=_metric(consensus_direction),
                candidate_center_direction_accuracy=_metric(candidate_direction),
                retained_direction_accuracy=_metric(consensus_direction),
                maximum_absolute_candidate_return=max(
                    (abs(prediction.price_center_return) for _observation, prediction in pairs),
                    default=Decimal("0"),
                ),
            )
        )
    return metrics


def build_cross_sectional_residual_report(
    metrics: Iterable[CrossSectionalResidualMetric],
    predictions: Iterable[CrossSectionalResidualPrediction],
    *,
    required_splits: Iterable[str],
) -> CrossSectionalResidualEvaluationReport:
    """Require overall, selected-only, subgroup, and coverage gates."""

    selected_metrics = list(metrics)
    selected_predictions = list(predictions)
    reasons: list[str] = []
    required = set(required_splits)
    overall = [
        metric
        for metric in selected_metrics
        if metric.group_type == "overall" and metric.split in required
    ]
    horizons = {prediction.horizon_days for prediction in selected_predictions}
    for split in sorted(required):
        for horizon in sorted(horizons):
            metric = next(
                (item for item in overall if item.split == split and item.horizon_days == horizon),
                None,
            )
            if metric is None:
                reasons.append(f"{split}/{horizon}日: overall metricがありません")
                continue
            if metric.relative_rmse_improvement_vs_anchor < MIN_RELATIVE_RMSE_IMPROVEMENT:
                reasons.append(
                    f"{split}/{horizon}日: 固定anchor比RMSE改善が1%未満です "
                    f"({metric.relative_rmse_improvement_vs_anchor})"
                )
            if metric.relative_rmse_improvement_vs_consensus < MIN_RELATIVE_RMSE_IMPROVEMENT:
                reasons.append(
                    f"{split}/{horizon}日: Consensus比RMSE改善が1%未満です "
                    f"({metric.relative_rmse_improvement_vs_consensus})"
                )
            selected_only = next(
                (
                    item
                    for item in selected_metrics
                    if item.split == split
                    and item.horizon_days == horizon
                    and item.group_type == "selection_status"
                    and item.group_value == "selected"
                ),
                None,
            )
            if (
                selected_only is not None
                and selected_only.sample_count >= MIN_SUBGROUP_SAMPLE_COUNT
                and selected_only.relative_rmse_improvement_vs_anchor
                < MIN_RELATIVE_RMSE_IMPROVEMENT
            ):
                reasons.append(
                    f"{split}/{horizon}日: 補正採用点が固定anchorを改善していません "
                    f"({selected_only.relative_rmse_improvement_vs_anchor})"
                )
    for metric in selected_metrics:
        if (
            metric.split not in required
            or metric.group_type in {"overall", "selection_status"}
            or metric.sample_count < MIN_SUBGROUP_SAMPLE_COUNT
        ):
            continue
        relative_degradation = -metric.relative_rmse_improvement_vs_anchor
        absolute_degradation = metric.candidate_rmse - metric.anchor_rmse
        if (
            relative_degradation > MAX_SUBGROUP_RELATIVE_RMSE_DEGRADATION
            and absolute_degradation > MAX_SUBGROUP_ABSOLUTE_RMSE_DEGRADATION
        ):
            reasons.append(
                f"{metric.split}/{metric.horizon_days}日/{metric.group_type}="
                f"{metric.group_value}: 固定anchor比の重大劣化です"
            )
    prediction_count = len(selected_predictions)
    selected_count = sum(
        prediction.decision.status == "selected" for prediction in selected_predictions
    )
    selection_rate = (
        Decimal(selected_count) / Decimal(prediction_count) if prediction_count else Decimal("0")
    )
    if selection_rate < MIN_CROSS_SECTIONAL_SELECTION_RATE:
        reasons.append(f"補正採用率が50%未満です ({_metric(selection_rate)})")
    return CrossSectionalResidualEvaluationReport(
        metrics=selected_metrics,
        prediction_count=prediction_count,
        selected_prediction_count=selected_count,
        fallback_prediction_count=prediction_count - selected_count,
        selection_rate=_metric(selection_rate),
        runtime_review_eligible=bool(prediction_count) and not reasons,
        gate_reasons=reasons,
        warnings=[
            "評価専用shadow候補です。Forecast、Cockpit、Ranking、スコアを変更しません。",
            "この監査結果を使ったtree深さ、leaf数、feature、gateの再調整は禁止します。",
        ],
    )


def _fit_point_in_time_cross_sectional_model(
    calibration_history: list[ConservativeCalibrationObservation],
    profile: HorizonConservativeCalibrationProfile,
    *,
    as_of: datetime,
    prediction_cross_section_size: int,
    min_training_sample_count: int,
    min_training_origin_count: int,
    min_fit_sample_count: int,
    min_validation_sample_count: int,
    min_cross_section_size: int,
    internal_fit_fraction: Decimal,
    residual_clip_quantile: Decimal,
    max_absolute_residual_correction: Decimal,
    min_samples_leaf: int,
) -> tuple[CrossSectionalResidualDecision, _FittedCrossSectionalModel | None]:
    selected = [
        item
        for item in calibration_history
        if item.horizon_days == profile.horizon_days
        and item.target_at <= as_of
        and _has_required_sources(item)
    ]
    selected.sort(key=lambda item: (item.origin_at, item.symbol))
    eligible_groups = {
        origin
        for origin, count in Counter(item.origin_at for item in selected).items()
        if count >= min_cross_section_size
    }
    selected = [item for item in selected if item.origin_at in eligible_groups]
    origin_times = sorted(eligible_groups)
    fallback_args: _FallbackArgs = {
        "horizon_days": profile.horizon_days,
        "as_of": as_of,
        "available_sample_count": len(selected),
        "available_origin_count": len(origin_times),
        "prediction_cross_section_size": prediction_cross_section_size,
    }
    if prediction_cross_section_size < min_cross_section_size:
        return _fallback(reason="insufficient_prediction_cross_section", **fallback_args), None
    if len(selected) < min_training_sample_count:
        return _fallback(reason="insufficient_history_samples", **fallback_args), None
    if len(origin_times) < min_training_origin_count:
        return _fallback(reason="insufficient_history_origins", **fallback_args), None

    fit_origin_count = ceil(Decimal(len(origin_times)) * internal_fit_fraction)
    fit_origin_count = min(max(fit_origin_count, 1), len(origin_times) - 1)
    fit_origins = set(origin_times[:fit_origin_count])
    fit_observations = [item for item in selected if item.origin_at in fit_origins]
    validation_observations = [item for item in selected if item.origin_at not in fit_origins]
    if (
        len(fit_observations) < min_fit_sample_count
        or len(validation_observations) < min_validation_sample_count
    ):
        return (
            _fallback(
                reason="insufficient_internal_temporal_samples",
                fit_sample_count=len(fit_observations),
                validation_sample_count=len(validation_observations),
                **fallback_args,
            ),
            None,
        )

    fit_rows = _build_feature_rows(fit_observations, profile)
    validation_rows = _build_feature_rows(validation_observations, profile)
    estimator = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.05,
        max_iter=100,
        max_leaf_nodes=7,
        min_samples_leaf=min_samples_leaf,
        l2_regularization=10.0,
        early_stopping=False,
    )
    fit_targets = np.asarray(
        [float(row.observation.actual_return - row.anchor) for row in fit_rows],
        dtype=np.float64,
    )
    estimator.fit(_matrix(fit_rows), fit_targets)
    correction_limit = min(
        max_absolute_residual_correction,
        _decimal(np.quantile(np.abs(fit_targets), float(residual_clip_quantile))),
    )
    fitted = _FittedCrossSectionalModel(estimator, correction_limit)
    fit_anchor_rmse, fit_candidate_rmse = _row_rmse_pair(fit_rows, fitted)
    validation_anchor_rmse, validation_candidate_rmse = _row_rmse_pair(validation_rows, fitted)
    fit_improvement = _relative_improvement(fit_anchor_rmse, fit_candidate_rmse)
    validation_improvement = _relative_improvement(
        validation_anchor_rmse, validation_candidate_rmse
    )
    metric_args: _MetricArgs = {
        "fit_sample_count": len(fit_rows),
        "validation_sample_count": len(validation_rows),
        "fit_anchor_rmse": _metric(fit_anchor_rmse),
        "fit_candidate_rmse": _metric(fit_candidate_rmse),
        "fit_relative_rmse_improvement_vs_anchor": fit_improvement,
        "validation_anchor_rmse": _metric(validation_anchor_rmse),
        "validation_candidate_rmse": _metric(validation_candidate_rmse),
        "validation_relative_rmse_improvement_vs_anchor": validation_improvement,
    }
    if fit_improvement < MIN_RELATIVE_RMSE_IMPROVEMENT:
        return (
            _fallback(
                reason="fit_improvement_vs_anchor_gate_failed",
                **metric_args,
                **fallback_args,
            ),
            None,
        )
    if validation_improvement < MIN_RELATIVE_RMSE_IMPROVEMENT:
        return (
            _fallback(
                reason="validation_improvement_vs_anchor_gate_failed",
                **metric_args,
                **fallback_args,
            ),
            None,
        )
    return (
        CrossSectionalResidualDecision(
            status="selected",
            reason="fit_and_validation_anchor_gates_passed",
            correction_limit=_return_value(correction_limit),
            **metric_args,
            **fallback_args,
        ),
        fitted,
    )


def _build_feature_rows(
    observations: list[ConservativeCalibrationObservation],
    profile: HorizonConservativeCalibrationProfile,
) -> list[_FeatureRow]:
    grouped: dict[datetime, list[ConservativeCalibrationObservation]] = defaultdict(list)
    for item in observations:
        grouped[item.origin_at].append(item)
    rows: list[_FeatureRow] = []
    for _origin_at, cross_section in sorted(grouped.items()):
        cross_section.sort(key=lambda item: item.symbol)
        anchors = [_anchor_return(item, profile) for item in cross_section]
        consensus = [item.consensus_return for item in cross_section]
        quantiles = [
            item.conservative_returns[ADVANCED_QUANTILE_ADAPTER_NAME] for item in cross_section
        ]
        moving_averages = [
            item.conservative_returns[MOVING_AVERAGE_3_MODEL_NAME] for item in cross_section
        ]
        dispersions = [
            _dispersion((consensus_value, quantile, moving_average))
            for consensus_value, quantile, moving_average in zip(
                consensus, quantiles, moving_averages
            )
        ]
        ranks = [
            _percentile_ranks(values)
            for values in (anchors, consensus, quantiles, moving_averages, dispersions)
        ]
        for index, item in enumerate(cross_section):
            anchor = anchors[index]
            values = (
                anchor,
                consensus[index] - anchor,
                quantiles[index] - anchor,
                moving_averages[index] - anchor,
                dispersions[index],
                ranks[0][index],
                ranks[1][index],
                ranks[2][index],
                ranks[3][index],
                ranks[4][index],
                Decimal(item.market.casefold() == "jp"),
                Decimal(item.market.casefold() == "us"),
                Decimal(item.asset_type.casefold() == "etf"),
                Decimal(item.regime.casefold() == "uptrend"),
                Decimal(item.regime.casefold() == "downtrend"),
                Decimal(item.regime.casefold() == "sideways"),
            )
            rows.append(_FeatureRow(item, anchor, values))
    return rows


def _matrix(rows: list[_FeatureRow]) -> np.ndarray:
    return np.asarray(
        [[float(value) for value in row.values] for row in rows],
        dtype=np.float64,
    )


def _row_rmse_pair(
    rows: list[_FeatureRow],
    fitted: _FittedCrossSectionalModel,
) -> tuple[Decimal, Decimal]:
    raw_corrections = fitted.estimator.predict(_matrix(rows))
    anchor_errors: list[Decimal] = []
    candidate_errors: list[Decimal] = []
    for row, raw_correction in zip(rows, raw_corrections):
        correction = max(
            -fitted.correction_limit,
            min(fitted.correction_limit, _decimal(raw_correction)),
        )
        candidate = max(
            -MAX_ABSOLUTE_CALIBRATED_RETURN,
            min(MAX_ABSOLUTE_CALIBRATED_RETURN, row.anchor + correction),
        )
        anchor_errors.append(row.anchor - row.observation.actual_return)
        candidate_errors.append(candidate - row.observation.actual_return)
    return _rmse(anchor_errors), _rmse(candidate_errors)


def _fallback(
    *,
    reason: str,
    horizon_days: int,
    as_of: datetime,
    available_sample_count: int,
    available_origin_count: int,
    prediction_cross_section_size: int,
    fit_sample_count: int = 0,
    validation_sample_count: int = 0,
    fit_anchor_rmse: Decimal | None = None,
    fit_candidate_rmse: Decimal | None = None,
    fit_relative_rmse_improvement_vs_anchor: Decimal | None = None,
    validation_anchor_rmse: Decimal | None = None,
    validation_candidate_rmse: Decimal | None = None,
    validation_relative_rmse_improvement_vs_anchor: Decimal | None = None,
) -> CrossSectionalResidualDecision:
    return CrossSectionalResidualDecision(
        horizon_days=horizon_days,
        as_of=as_of,
        status="fallback",
        reason=reason,
        available_sample_count=available_sample_count,
        available_origin_count=available_origin_count,
        fit_sample_count=fit_sample_count,
        validation_sample_count=validation_sample_count,
        prediction_cross_section_size=prediction_cross_section_size,
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


def _validate_parameters(
    *,
    min_training_sample_count: int,
    min_training_origin_count: int,
    min_fit_sample_count: int,
    min_validation_sample_count: int,
    min_cross_section_size: int,
    internal_fit_fraction: Decimal,
    residual_clip_quantile: Decimal,
    max_absolute_residual_correction: Decimal,
    min_samples_leaf: int,
) -> None:
    if min_training_sample_count < 1:
        raise ValueError("min_training_sample_count must be positive")
    if min_training_origin_count < 2:
        raise ValueError("min_training_origin_count must be at least 2")
    if min_fit_sample_count < 1 or min_validation_sample_count < 1:
        raise ValueError("fit and validation sample minimums must be positive")
    if min_cross_section_size < 2:
        raise ValueError("min_cross_section_size must be at least 2")
    if internal_fit_fraction <= 0 or internal_fit_fraction >= 1:
        raise ValueError("internal_fit_fraction must be between 0 and 1")
    if residual_clip_quantile <= 0 or residual_clip_quantile > 1:
        raise ValueError("residual_clip_quantile must be in (0, 1]")
    if max_absolute_residual_correction <= 0:
        raise ValueError("max_absolute_residual_correction must be positive")
    if min_samples_leaf < 2:
        raise ValueError("min_samples_leaf must be at least 2")


def _validate_observations(
    observations: list[ConservativeCalibrationObservation],
    *,
    label: str,
) -> None:
    keys: set[tuple[str, int, datetime, datetime]] = set()
    for observation in observations:
        if observation.origin_at.tzinfo is None or observation.origin_at.utcoffset() is None:
            raise ValueError(f"{label} origin_at must be timezone-aware")
        if observation.target_at.tzinfo is None or observation.target_at.utcoffset() is None:
            raise ValueError(f"{label} target_at must be timezone-aware")
        if observation.target_at <= observation.origin_at:
            raise ValueError(f"{label} target_at must follow origin_at")
        key = _point_key(observation)
        if key in keys:
            raise ValueError(f"{label} observations must not contain duplicate points")
        keys.add(key)


def _percentile_ranks(values: list[Decimal]) -> list[Decimal]:
    if len(values) == 1:
        return [Decimal("0.5")]
    indexed = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [Decimal("0")] * len(values)
    cursor = 0
    denominator = Decimal(len(values) - 1)
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        average_position = Decimal(cursor + end - 1) / Decimal("2")
        percentile = average_position / denominator
        for position in range(cursor, end):
            ranks[indexed[position][0]] = percentile
        cursor = end
    return ranks


def _dispersion(values: tuple[Decimal, ...]) -> Decimal:
    center = Decimal(str(median(values)))
    variance = sum((value - center) ** 2 for value in values) / Decimal(len(values))
    return variance.sqrt()


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


def _point_key(
    item: ConservativeCalibrationObservation | CrossSectionalResidualPrediction,
) -> tuple[str, int, datetime, datetime]:
    return (item.symbol, item.horizon_days, item.origin_at, item.target_at)


def _group_value(
    observation: ConservativeCalibrationObservation,
    prediction: CrossSectionalResidualPrediction,
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


def _decimal(value: float | np.floating) -> Decimal:
    return Decimal(str(float(value)))


def _metric(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _return_value(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
