"""Evaluation-only horizon-conditioned calibration for forecast price centers.

The calibrated price center and the retained direction signal are deliberately
separate.  Profiles are fitted from a tuning split and can then be evaluated on
symbol-disjoint validation and audit splits without refitting.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from itertools import product
from typing import Iterable, Self

from pydantic import ConfigDict, Field, model_validator

from backend.core.data_contracts import StrictBaseModel
from backend.forecast.adapters import ADVANCED_QUANTILE_ADAPTER_NAME
from backend.forecast.evaluation import (
    CONSENSUS_MODEL_NAME,
    ForecastEvaluationCase,
    ForecastValidationPoint,
)
from backend.forecast.regime_gated_ensemble import classify_forecast_regime
from backend.forecast.service import MovingAverageForecastModel

CONSERVATIVE_CALIBRATION_MODEL_NAME = "horizon_conditioned_conservative_calibration"
DEFAULT_CONSERVATIVE_MODEL_NAMES = ("advanced_quantile", "moving_average_3")
DEFAULT_CONSENSUS_WEIGHTS = tuple(Decimal(index) / Decimal("10") for index in range(11))
MIN_RELATIVE_RMSE_IMPROVEMENT = Decimal("0.01")
MAX_SUBGROUP_RELATIVE_RMSE_DEGRADATION = Decimal("0.10")
MAX_SUBGROUP_ABSOLUTE_RMSE_DEGRADATION = Decimal("0.005")
MIN_SUBGROUP_SAMPLE_COUNT = 10
MAX_ABSOLUTE_CALIBRATED_RETURN = Decimal("0.75")
CALIBRATION_GROUP_TYPES = ("overall", "cohort", "market", "asset_type", "regime")
MOVING_AVERAGE_3_MODEL_NAME = "moving_average_3"


class ConservativeCalibrationObservation(StrictBaseModel):
    """One paired point-in-time observation used by the shadow evaluator."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    cohort: str = Field(min_length=1)
    split: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    target_at: datetime
    consensus_return: Decimal
    actual_return: Decimal
    conservative_returns: dict[str, Decimal]


class HorizonConservativeCalibrationProfile(StrictBaseModel):
    """Frozen price-center blend selected from tuning observations only."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = CONSERVATIVE_CALIBRATION_MODEL_NAME
    horizon_days: int = Field(ge=1)
    conservative_model_name: str = Field(min_length=1)
    consensus_weight: Decimal = Field(ge=0, le=1)
    conservative_weight: Decimal = Field(ge=0, le=1)
    tuning_sample_count: int = Field(ge=1)
    tuning_consensus_rmse: Decimal = Field(ge=0)
    tuning_conservative_rmse: Decimal = Field(ge=0)
    tuning_candidate_rmse: Decimal = Field(ge=0)
    tuning_relative_rmse_improvement: Decimal
    tuning_consensus_direction_accuracy: Decimal = Field(ge=0, le=1)
    tuning_candidate_center_direction_accuracy: Decimal = Field(ge=0, le=1)
    tuning_retained_direction_accuracy: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_weights(self) -> Self:
        if self.consensus_weight + self.conservative_weight != Decimal("1"):
            raise ValueError("calibration weights must sum to 1")
        return self


class ConservativeCalibrationPrediction(StrictBaseModel):
    """Two-head shadow prediction: calibrated center plus retained direction."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = CONSERVATIVE_CALIBRATION_MODEL_NAME
    horizon_days: int = Field(ge=1)
    conservative_model_name: str = Field(min_length=1)
    consensus_weight: Decimal = Field(ge=0, le=1)
    conservative_weight: Decimal = Field(ge=0, le=1)
    price_center_return: Decimal
    direction_return: Decimal
    original_consensus_return: Decimal
    conservative_return: Decimal


class ConservativeCalibrationMetric(StrictBaseModel):
    """Paired metric for one split, subgroup, and horizon."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    split: str = Field(min_length=1)
    group_type: str = Field(min_length=1)
    group_value: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    symbol_count: int = Field(ge=0)
    sample_count: int = Field(ge=0)
    consensus_mae: Decimal = Field(ge=0)
    candidate_price_mae: Decimal = Field(ge=0)
    consensus_rmse: Decimal = Field(ge=0)
    candidate_price_rmse: Decimal = Field(ge=0)
    relative_rmse_improvement: Decimal
    consensus_direction_accuracy: Decimal = Field(ge=0, le=1)
    candidate_center_direction_accuracy: Decimal = Field(ge=0, le=1)
    retained_direction_accuracy: Decimal = Field(ge=0, le=1)
    maximum_absolute_candidate_return: Decimal = Field(ge=0)


class ConservativeCalibrationEvaluationReport(StrictBaseModel):
    """Frozen profiles, validation metrics, and explicit runtime-review gate."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = CONSERVATIVE_CALIBRATION_MODEL_NAME
    profiles: list[HorizonConservativeCalibrationProfile]
    metrics: list[ConservativeCalibrationMetric]
    runtime_review_eligible: bool
    gate_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def fit_horizon_conditioned_calibration(
    observations: Iterable[ConservativeCalibrationObservation],
    *,
    conservative_model_names: tuple[str, ...] = DEFAULT_CONSERVATIVE_MODEL_NAMES,
    consensus_weights: tuple[Decimal, ...] = DEFAULT_CONSENSUS_WEIGHTS,
) -> list[HorizonConservativeCalibrationProfile]:
    """Fit one jointly constrained profile per horizon from tuning data only.

    Longer horizons cannot retain more consensus weight than shorter horizons.
    This makes the intended stronger long-horizon shrinkage an explicit contract.
    """

    selected = list(observations)
    if not selected:
        raise ValueError("tuning observations are required")
    if any(observation.split != "tuning" for observation in selected):
        raise ValueError("calibration profiles must be fitted from tuning observations only")
    model_names = tuple(dict.fromkeys(name.strip() for name in conservative_model_names))
    if not model_names or any(not name for name in model_names):
        raise ValueError("conservative_model_names must not be empty")
    weights = tuple(dict.fromkeys(consensus_weights))
    if not weights or any(weight < 0 or weight > 1 for weight in weights):
        raise ValueError("consensus_weights must contain values between 0 and 1")
    horizons = sorted({observation.horizon_days for observation in selected})
    by_horizon = {
        horizon: [observation for observation in selected if observation.horizon_days == horizon]
        for horizon in horizons
    }
    for observation in selected:
        missing = set(model_names) - set(observation.conservative_returns)
        if missing:
            raise ValueError(
                f"observation is missing conservative models: {','.join(sorted(missing))}"
            )

    candidates_by_horizon: dict[int, list[tuple[str, Decimal, Decimal, Decimal]]] = {}
    for horizon, horizon_observations in by_horizon.items():
        candidates: list[tuple[str, Decimal, Decimal, Decimal]] = []
        consensus_rmse = _rmse(
            observation.consensus_return - observation.actual_return
            for observation in horizon_observations
        )
        for model_name in model_names:
            for weight in weights:
                candidate_rmse = _candidate_rmse(horizon_observations, model_name, weight)
                normalized_rmse = (
                    candidate_rmse / consensus_rmse if consensus_rmse > 0 else candidate_rmse
                )
                candidates.append((model_name, weight, candidate_rmse, normalized_rmse))
        candidates_by_horizon[horizon] = candidates

    feasible: list[tuple[tuple[Decimal, Decimal, Decimal, tuple[str, ...]], tuple]] = []
    for candidate_set in product(*(candidates_by_horizon[horizon] for horizon in horizons)):
        candidate_weights = [candidate[1] for candidate in candidate_set]
        if any(
            longer_weight > shorter_weight
            for shorter_weight, longer_weight in zip(candidate_weights, candidate_weights[1:])
        ):
            continue
        objective = (
            sum((candidate[3] for candidate in candidate_set), Decimal("0")),
            sum((candidate[2] for candidate in candidate_set), Decimal("0")),
            -sum(candidate_weights, Decimal("0")),
            tuple(candidate[0] for candidate in candidate_set),
        )
        feasible.append((objective, candidate_set))
    if not feasible:
        raise ValueError("no horizon-conditioned calibration profile is feasible")
    _objective, selected_candidates = min(feasible, key=lambda item: item[0])

    profiles: list[HorizonConservativeCalibrationProfile] = []
    for horizon, candidate in zip(horizons, selected_candidates):
        model_name, consensus_weight, candidate_rmse, _normalized_rmse = candidate
        horizon_observations = by_horizon[horizon]
        consensus_rmse = _rmse(
            observation.consensus_return - observation.actual_return
            for observation in horizon_observations
        )
        conservative_rmse = _rmse(
            observation.conservative_returns[model_name] - observation.actual_return
            for observation in horizon_observations
        )
        consensus_direction = _direction_accuracy(
            (observation.consensus_return, observation.actual_return)
            for observation in horizon_observations
        )
        center_direction = _direction_accuracy(
            (
                _calibrated_return(observation, model_name, consensus_weight),
                observation.actual_return,
            )
            for observation in horizon_observations
        )
        profiles.append(
            HorizonConservativeCalibrationProfile(
                horizon_days=horizon,
                conservative_model_name=model_name,
                consensus_weight=consensus_weight,
                conservative_weight=Decimal("1") - consensus_weight,
                tuning_sample_count=len(horizon_observations),
                tuning_consensus_rmse=_metric(consensus_rmse),
                tuning_conservative_rmse=_metric(conservative_rmse),
                tuning_candidate_rmse=_metric(candidate_rmse),
                tuning_relative_rmse_improvement=_relative_improvement(
                    consensus_rmse, candidate_rmse
                ),
                tuning_consensus_direction_accuracy=_metric(consensus_direction),
                tuning_candidate_center_direction_accuracy=_metric(center_direction),
                tuning_retained_direction_accuracy=_metric(consensus_direction),
            )
        )
    return profiles


def build_point_in_time_calibration_observations(
    cases: Iterable[ForecastEvaluationCase],
    validation_points: Iterable[ForecastValidationPoint],
    *,
    cohort: str,
    split: str,
) -> list[ConservativeCalibrationObservation]:
    """Join frozen-candidate inputs at identical future-safe origins.

    Regime labels and the moving-average baseline use only bars available at
    each origin.  Actual returns remain evaluation labels and never enter a
    prediction input.
    """

    if not cohort.strip() or not split.strip():
        raise ValueError("cohort and split must not be empty")
    cases_by_symbol = {case.symbol: case for case in cases}
    selected_points = list(validation_points)

    def point_key(point: ForecastValidationPoint) -> tuple[str, int, datetime, datetime]:
        return (
            point.symbol,
            point.horizon_days,
            point.origin_at,
            point.target_at,
        )

    consensus_points = {
        point_key(point): point
        for point in selected_points
        if point.model_name == CONSENSUS_MODEL_NAME
    }
    quantile_points = {
        point_key(point): point
        for point in selected_points
        if point.model_name == ADVANCED_QUANTILE_ADAPTER_NAME
    }
    moving_average = MovingAverageForecastModel(window=3)
    observations: list[ConservativeCalibrationObservation] = []
    for key, consensus in sorted(consensus_points.items()):
        quantile = quantile_points.get(key)
        case = cases_by_symbol.get(consensus.symbol)
        if quantile is None or case is None:
            continue
        if quantile.actual_return != consensus.actual_return:
            raise ValueError(f"actual return mismatch for calibration point: {key}")
        bars = sorted(case.bars, key=lambda bar: bar.ts)
        origin_index = next(
            (index for index, bar in enumerate(bars) if bar.ts == consensus.origin_at),
            None,
        )
        if origin_index is None or origin_index + consensus.horizon_days >= len(bars):
            raise ValueError(f"origin is not available in calibration case: {key}")
        target = bars[origin_index + consensus.horizon_days]
        if target.ts != consensus.target_at:
            raise ValueError(f"target does not match calibration horizon: {key}")
        history = bars[: origin_index + 1]
        origin = history[-1]
        if origin.close <= 0:
            raise ValueError(f"origin close must be positive: {key}")
        baseline = moving_average.predict(history, horizon_days=consensus.horizon_days)
        moving_average_return = baseline.forecast_close / origin.close - Decimal("1")
        observations.append(
            ConservativeCalibrationObservation(
                cohort=cohort,
                split=split,
                symbol=consensus.symbol,
                market=consensus.market,
                asset_type=consensus.asset_type,
                regime=classify_forecast_regime(history),
                horizon_days=consensus.horizon_days,
                origin_at=consensus.origin_at,
                target_at=consensus.target_at,
                consensus_return=consensus.predicted_return,
                actual_return=consensus.actual_return,
                conservative_returns={
                    ADVANCED_QUANTILE_ADAPTER_NAME: quantile.predicted_return,
                    MOVING_AVERAGE_3_MODEL_NAME: moving_average_return,
                },
            )
        )
    return observations


def apply_horizon_conditioned_calibration(
    observation: ConservativeCalibrationObservation,
    profile: HorizonConservativeCalibrationProfile,
) -> ConservativeCalibrationPrediction:
    """Apply a frozen profile without changing the original direction head."""

    if observation.horizon_days != profile.horizon_days:
        raise ValueError("observation and calibration profile horizons do not match")
    if profile.conservative_model_name not in observation.conservative_returns:
        raise ValueError("observation does not contain the profile's conservative model")
    conservative_return = observation.conservative_returns[profile.conservative_model_name]
    price_center_return = _calibrated_return(
        observation,
        profile.conservative_model_name,
        profile.consensus_weight,
    )
    lower = min(observation.consensus_return, conservative_return)
    upper = max(observation.consensus_return, conservative_return)
    if price_center_return < lower or price_center_return > upper:
        raise ValueError("calibrated return must stay within its source predictions")
    return ConservativeCalibrationPrediction(
        horizon_days=observation.horizon_days,
        conservative_model_name=profile.conservative_model_name,
        consensus_weight=profile.consensus_weight,
        conservative_weight=profile.conservative_weight,
        price_center_return=_return_value(price_center_return),
        direction_return=observation.consensus_return,
        original_consensus_return=observation.consensus_return,
        conservative_return=conservative_return,
    )


def evaluate_horizon_conditioned_calibration(
    observations: Iterable[ConservativeCalibrationObservation],
    profiles: Iterable[HorizonConservativeCalibrationProfile],
) -> list[ConservativeCalibrationMetric]:
    """Evaluate frozen profiles across overall, cohort, and market subgroups."""

    selected = list(observations)
    profiles_by_horizon = {profile.horizon_days: profile for profile in profiles}
    if len(profiles_by_horizon) == 0:
        raise ValueError("at least one calibration profile is required")
    missing_horizons = {
        observation.horizon_days
        for observation in selected
        if observation.horizon_days not in profiles_by_horizon
    }
    if missing_horizons:
        raise ValueError(f"missing profiles for horizons: {sorted(missing_horizons)}")

    grouped: dict[
        tuple[str, str, str, int], list[tuple[ConservativeCalibrationObservation, Decimal]]
    ] = defaultdict(list)
    for observation in selected:
        profile = profiles_by_horizon[observation.horizon_days]
        prediction = apply_horizon_conditioned_calibration(observation, profile)
        for group_type in CALIBRATION_GROUP_TYPES:
            grouped[
                (
                    observation.split,
                    group_type,
                    _group_value(observation, group_type),
                    observation.horizon_days,
                )
            ].append((observation, prediction.price_center_return))

    metrics: list[ConservativeCalibrationMetric] = []
    for (split, group_type, group_value, horizon), pairs in sorted(grouped.items()):
        consensus_errors = [
            observation.consensus_return - observation.actual_return
            for observation, _candidate_return in pairs
        ]
        candidate_errors = [
            candidate_return - observation.actual_return for observation, candidate_return in pairs
        ]
        consensus_rmse = _rmse(consensus_errors)
        candidate_rmse = _rmse(candidate_errors)
        consensus_direction = _direction_accuracy(
            (observation.consensus_return, observation.actual_return)
            for observation, _candidate_return in pairs
        )
        center_direction = _direction_accuracy(
            (candidate_return, observation.actual_return) for observation, candidate_return in pairs
        )
        metrics.append(
            ConservativeCalibrationMetric(
                split=split,
                group_type=group_type,
                group_value=group_value,
                horizon_days=horizon,
                symbol_count=len({observation.symbol for observation, _value in pairs}),
                sample_count=len(pairs),
                consensus_mae=_metric(_mean(abs(error) for error in consensus_errors)),
                candidate_price_mae=_metric(_mean(abs(error) for error in candidate_errors)),
                consensus_rmse=_metric(consensus_rmse),
                candidate_price_rmse=_metric(candidate_rmse),
                relative_rmse_improvement=_relative_improvement(consensus_rmse, candidate_rmse),
                consensus_direction_accuracy=_metric(consensus_direction),
                candidate_center_direction_accuracy=_metric(center_direction),
                retained_direction_accuracy=_metric(consensus_direction),
                maximum_absolute_candidate_return=_metric(
                    max(abs(candidate_return) for _observation, candidate_return in pairs)
                ),
            )
        )
    return metrics


def build_conservative_calibration_report(
    profiles: Iterable[HorizonConservativeCalibrationProfile],
    metrics: Iterable[ConservativeCalibrationMetric],
    *,
    required_splits: tuple[str, ...] = ("validation", "audit"),
) -> ConservativeCalibrationEvaluationReport:
    """Apply the fixed overall and subgroup gates without automatic adoption."""

    selected_profiles = list(profiles)
    selected_metrics = list(metrics)
    horizons = {profile.horizon_days for profile in selected_profiles}
    failures: list[str] = []
    for split in required_splits:
        for horizon in sorted(horizons):
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
                failures.append(f"{split} {horizon}日: 比較可能なoverall sampleがありません。")
                continue
            if overall.relative_rmse_improvement < MIN_RELATIVE_RMSE_IMPROVEMENT:
                failures.append(
                    f"{split} {horizon}日: RMSE改善が1%未満です"
                    f"（{overall.relative_rmse_improvement * Decimal('100'):.2f}%）。"
                )
            if overall.retained_direction_accuracy < overall.consensus_direction_accuracy:
                failures.append(f"{split} {horizon}日: direction headが悪化しました。")
            if overall.maximum_absolute_candidate_return > MAX_ABSOLUTE_CALIBRATED_RETURN:
                failures.append(f"{split} {horizon}日: calibrated returnが安全上限を超えました。")

    for metric in selected_metrics:
        if (
            metric.split not in required_splits
            or metric.group_type == "overall"
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
    failures = list(dict.fromkeys(failures))
    gate_reasons = failures or [
        "validation / auditの20日・60日overall RMSEを各1%以上改善しました。",
        "consensus由来のdirection headを維持し、重大なsubgroup劣化を検出しませんでした。",
    ]
    return ConservativeCalibrationEvaluationReport(
        profiles=selected_profiles,
        metrics=selected_metrics,
        runtime_review_eligible=not failures and bool(selected_profiles),
        gate_reasons=gate_reasons,
        warnings=[
            "評価専用shadow候補です。Cockpit、Ranking、Forecast APIのruntime値は変更しません。",
            "runtime_review_eligibleは自動採用を意味せず、新期間のsealed auditが別途必要です。",
        ],
    )


def _candidate_rmse(
    observations: list[ConservativeCalibrationObservation],
    model_name: str,
    consensus_weight: Decimal,
) -> Decimal:
    return _rmse(
        _calibrated_return(observation, model_name, consensus_weight) - observation.actual_return
        for observation in observations
    )


def _calibrated_return(
    observation: ConservativeCalibrationObservation,
    model_name: str,
    consensus_weight: Decimal,
) -> Decimal:
    return observation.consensus_return * consensus_weight + observation.conservative_returns[
        model_name
    ] * (Decimal("1") - consensus_weight)


def _group_value(observation: ConservativeCalibrationObservation, group_type: str) -> str:
    if group_type == "overall":
        return "all"
    return str(getattr(observation, group_type))


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
