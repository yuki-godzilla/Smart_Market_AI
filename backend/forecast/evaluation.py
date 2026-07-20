from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ConfigDict, Field

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.forecast.advanced_registry import (
    advanced_forecast_adapter_keys,
    advanced_forecast_adapter_spec,
)
from backend.forecast.regime_gated_ensemble import (
    REGIME_GATED_ENSEMBLE_MODEL_NAME,
    classify_forecast_regime,
    summarize_regime_gated_forecasts,
)
from backend.forecast.service import (
    AdvancedForecastEvaluation,
    evaluate_advanced_forecast,
    summarize_advanced_forecast_evaluations,
)

DEFAULT_EVALUATION_HORIZONS = (20, 60)
CONSENSUS_MODEL_NAME = "forecast_consensus"
DEFAULT_MAX_ORIGINS = 5
MIN_RELATIVE_RMSE_IMPROVEMENT = Decimal("0.01")


class ForecastEvaluationCase(StrictBaseModel):
    """Point-in-time price history and grouping metadata for one symbol."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    bars: list[Bar]
    market: str = Field(default="unknown", min_length=1)
    asset_type: str = Field(default="unknown", min_length=1)
    regime: str = Field(default="unknown", min_length=1)


class ForecastValidationPoint(StrictBaseModel):
    """One future-safe rolling-origin prediction and observed return."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    target_at: datetime
    predicted_return: Decimal
    direction_predicted_return: Decimal | None = None
    actual_return: Decimal
    model_disagreement: Decimal | None = Field(default=None, ge=0)


class ForecastPredictionRow(StrictBaseModel):
    """Latest point-in-time prediction kept separate from validation results."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    as_of: datetime
    predicted_return: Decimal
    direction_predicted_return: Decimal | None = None
    confidence: str = Field(min_length=1)
    model_disagreement: Decimal | None = Field(default=None, ge=0)


class ForecastModelEvaluationRow(StrictBaseModel):
    """Aggregated rolling-origin metrics for one model, group, and horizon."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    group_type: str = Field(min_length=1)
    group_value: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    evaluation_method: str = "rolling_origin"
    horizon_days: int = Field(ge=1)
    evaluated_case_count: int = Field(ge=0)
    skipped_case_count: int = Field(ge=0)
    validation_sample_count: int = Field(ge=0)
    fold_count: int = Field(ge=0)
    mae: Decimal = Field(ge=0)
    rmse: Decimal = Field(ge=0)
    direction_accuracy: Decimal = Field(ge=0, le=1)
    baseline_zero_rmse: Decimal = Field(ge=0)
    rmse_improvement: Decimal
    mean_model_disagreement: Decimal | None = Field(default=None, ge=0)


class ForecastWeightAdjustment(StrictBaseModel):
    """Offline candidate weights and their same-fold comparison."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    horizon_days: int = Field(ge=1)
    model_weights: dict[str, Decimal]
    tuning_sample_count: int = Field(ge=0)
    holdout_sample_count: int = Field(ge=0)
    current_consensus_rmse: Decimal = Field(ge=0)
    candidate_consensus_rmse: Decimal = Field(ge=0)
    current_direction_accuracy: Decimal = Field(ge=0, le=1)
    candidate_direction_accuracy: Decimal = Field(ge=0, le=1)
    adopted: bool
    reason: str = Field(min_length=1)


class ForecastModelEvaluationReport(StrictBaseModel):
    """Deterministic Phase 33 evaluation, prediction, and tuning result."""

    model_config = ConfigDict(extra="forbid")

    horizons: list[int]
    requested_case_count: int = Field(ge=0)
    rows: list[ForecastModelEvaluationRow]
    validation_points: list[ForecastValidationPoint]
    predictions: list[ForecastPredictionRow]
    weight_adjustments: list[ForecastWeightAdjustment]
    warnings: list[str] = Field(default_factory=list)


def evaluate_forecast_models(
    cases: list[ForecastEvaluationCase],
    *,
    horizons: tuple[int, ...] = DEFAULT_EVALUATION_HORIZONS,
    adapter_names: tuple[str, ...] | None = None,
    max_origins: int = DEFAULT_MAX_ORIGINS,
) -> ForecastModelEvaluationReport:
    """Run future-safe rolling-origin evaluation and latest predictions."""

    resolved_horizons = _validated_horizons(horizons)
    resolved_adapters = _validated_adapters(adapter_names or advanced_forecast_adapter_keys())
    if max_origins < 1:
        raise ValueError("max_origins must be at least 1")

    points: list[ForecastValidationPoint] = []
    predictions: list[ForecastPredictionRow] = []
    skipped: dict[tuple[str, int], int] = defaultdict(int)
    for case in cases:
        bars = sorted(case.bars, key=lambda bar: bar.ts)
        for horizon in resolved_horizons:
            case_points = _evaluate_case_origins(
                case,
                bars,
                horizon_days=horizon,
                adapter_names=resolved_adapters,
                max_origins=max_origins,
            )
            points.extend(case_points)
            present_models = {point.model_name for point in case_points}
            for model_name in (
                *resolved_adapters,
                CONSENSUS_MODEL_NAME,
                REGIME_GATED_ENSEMBLE_MODEL_NAME,
            ):
                if model_name not in present_models:
                    skipped[(model_name, horizon)] += 1
            predictions.extend(
                _latest_predictions(
                    case,
                    bars,
                    horizon_days=horizon,
                    adapter_names=resolved_adapters,
                )
            )

    rows = _aggregate_all_groups(
        points,
        cases=cases,
        horizons=resolved_horizons,
        model_names=(
            *resolved_adapters,
            CONSENSUS_MODEL_NAME,
            REGIME_GATED_ENSEMBLE_MODEL_NAME,
        ),
        skipped=skipped,
    )
    adjustments = _build_weight_adjustments(
        points,
        horizons=resolved_horizons,
        adapter_names=resolved_adapters,
    )
    warnings: list[str] = []
    if not cases:
        warnings.append("評価ケースがありません。")
    if any(value > 0 for value in skipped.values()):
        warnings.append(
            "履歴不足などで評価できないケースがあります。skipped_case_countを確認してください。"
        )
    if any(not adjustment.adopted for adjustment in adjustments):
        warnings.append("改善候補weightは同一fold比較を通過していないため、自動採用されません。")
    return ForecastModelEvaluationReport(
        horizons=list(resolved_horizons),
        requested_case_count=len(cases),
        rows=rows,
        validation_points=points,
        predictions=predictions,
        weight_adjustments=adjustments,
        warnings=warnings,
    )


def evaluated_consensus_prediction(
    evaluations: list[AdvancedForecastEvaluation],
    adjustment: ForecastWeightAdjustment,
) -> Decimal:
    """Apply an adopted offline weight profile to matching evaluations."""

    if not adjustment.adopted:
        raise ValueError("weight adjustment has not passed the adoption gate")
    matching = [
        evaluation
        for evaluation in evaluations
        if evaluation.horizon_days == adjustment.horizon_days
        and evaluation.adapter_name in adjustment.model_weights
    ]
    if len(matching) != len(adjustment.model_weights):
        raise ValueError("evaluations do not match the adopted weight profile")
    return _weighted_prediction(
        {evaluation.adapter_name: evaluation.predicted_return for evaluation in matching},
        adjustment.model_weights,
    )


def write_forecast_evaluation_artifacts(
    report: ForecastModelEvaluationReport,
    output_dir: Path,
) -> dict[str, Path]:
    """Write Phase 33 evaluation, prediction, error, and tuning artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": output_dir / "forecast_model_evaluation_summary.md",
        "by_horizon": output_dir / "forecast_model_evaluation_by_horizon.csv",
        "by_market": output_dir / "forecast_model_evaluation_by_market.csv",
        "by_asset_type": output_dir / "forecast_model_evaluation_by_asset_type.csv",
        "by_regime": output_dir / "forecast_model_evaluation_by_regime.csv",
        "predictions": output_dir / "forecast_model_predictions.csv",
        "validation_points": output_dir / "forecast_model_validation_points.csv",
        "error_cases": output_dir / "forecast_model_error_cases.md",
        "weighting_adjustments": output_dir / "forecast_model_weighting_adjustments.md",
    }
    paths["summary"].write_text(
        _render_summary(report),
        encoding="utf-8",
        newline="\n",
    )
    _write_group_csv(paths["by_horizon"], report.rows, group_type="overall")
    _write_group_csv(paths["by_market"], report.rows, group_type="market")
    _write_group_csv(paths["by_asset_type"], report.rows, group_type="asset_type")
    _write_group_csv(paths["by_regime"], report.rows, group_type="regime")
    _write_predictions_csv(paths["predictions"], report.predictions)
    _write_validation_points_csv(paths["validation_points"], report.validation_points)
    paths["error_cases"].write_text(
        _render_error_cases(report.validation_points),
        encoding="utf-8",
        newline="\n",
    )
    paths["weighting_adjustments"].write_text(
        _render_weight_adjustments(report.weight_adjustments),
        encoding="utf-8",
        newline="\n",
    )
    return paths


def _evaluate_case_origins(
    case: ForecastEvaluationCase,
    bars: list[Bar],
    *,
    horizon_days: int,
    adapter_names: tuple[str, ...],
    max_origins: int,
) -> list[ForecastValidationPoint]:
    points: list[ForecastValidationPoint] = []
    for origin_index in _rolling_origins(
        len(bars),
        horizon_days=horizon_days,
        max_origins=max_origins,
    ):
        history = bars[: origin_index + 1]
        evaluations = _safe_evaluations(
            history,
            horizon_days=horizon_days,
            adapter_names=adapter_names,
        )
        actual_return = _forward_return(bars, origin_index, horizon_days)
        target = bars[origin_index + horizon_days]
        for evaluation in evaluations:
            points.append(
                ForecastValidationPoint(
                    symbol=case.symbol,
                    market=case.market,
                    asset_type=case.asset_type,
                    regime=case.regime,
                    model_name=evaluation.adapter_name,
                    horizon_days=horizon_days,
                    origin_at=bars[origin_index].ts,
                    target_at=target.ts,
                    predicted_return=evaluation.predicted_return,
                    actual_return=actual_return,
                )
            )
        consensus = summarize_advanced_forecast_evaluations(evaluations)
        if consensus is not None:
            points.append(
                ForecastValidationPoint(
                    symbol=case.symbol,
                    market=case.market,
                    asset_type=case.asset_type,
                    regime=case.regime,
                    model_name=CONSENSUS_MODEL_NAME,
                    horizon_days=horizon_days,
                    origin_at=bars[origin_index].ts,
                    target_at=target.ts,
                    predicted_return=consensus.consensus_predicted_return,
                    direction_predicted_return=consensus.direction_predicted_return,
                    actual_return=actual_return,
                    model_disagreement=consensus.predicted_return_range,
                )
            )
        regime_gated = summarize_regime_gated_forecasts(
            evaluations,
            regime=classify_forecast_regime(history),
        )
        if regime_gated is not None:
            points.append(
                ForecastValidationPoint(
                    symbol=case.symbol,
                    market=case.market,
                    asset_type=case.asset_type,
                    regime=case.regime,
                    model_name=REGIME_GATED_ENSEMBLE_MODEL_NAME,
                    horizon_days=horizon_days,
                    origin_at=bars[origin_index].ts,
                    target_at=target.ts,
                    predicted_return=regime_gated.predicted_return,
                    actual_return=actual_return,
                    model_disagreement=regime_gated.predicted_return_range,
                )
            )
    return points


def _latest_predictions(
    case: ForecastEvaluationCase,
    bars: list[Bar],
    *,
    horizon_days: int,
    adapter_names: tuple[str, ...],
) -> list[ForecastPredictionRow]:
    if not bars:
        return []
    evaluations = _safe_evaluations(
        bars,
        horizon_days=horizon_days,
        adapter_names=adapter_names,
    )
    rows = [
        ForecastPredictionRow(
            symbol=case.symbol,
            market=case.market,
            asset_type=case.asset_type,
            regime=case.regime,
            model_name=evaluation.adapter_name,
            horizon_days=horizon_days,
            as_of=bars[-1].ts,
            predicted_return=evaluation.predicted_return,
            confidence=evaluation.confidence,
        )
        for evaluation in evaluations
    ]
    consensus = summarize_advanced_forecast_evaluations(evaluations)
    if consensus is not None:
        rows.append(
            ForecastPredictionRow(
                symbol=case.symbol,
                market=case.market,
                asset_type=case.asset_type,
                regime=case.regime,
                model_name=CONSENSUS_MODEL_NAME,
                horizon_days=horizon_days,
                as_of=bars[-1].ts,
                predicted_return=consensus.consensus_predicted_return,
                direction_predicted_return=consensus.direction_predicted_return,
                confidence=consensus.confidence,
                model_disagreement=consensus.predicted_return_range,
            )
        )
    regime_gated = summarize_regime_gated_forecasts(
        evaluations,
        regime=classify_forecast_regime(bars),
    )
    if regime_gated is not None:
        rows.append(
            ForecastPredictionRow(
                symbol=case.symbol,
                market=case.market,
                asset_type=case.asset_type,
                regime=case.regime,
                model_name=REGIME_GATED_ENSEMBLE_MODEL_NAME,
                horizon_days=horizon_days,
                as_of=bars[-1].ts,
                predicted_return=regime_gated.predicted_return,
                confidence=regime_gated.confidence,
                model_disagreement=regime_gated.predicted_return_range,
            )
        )
    return rows


def _safe_evaluations(
    bars: list[Bar],
    *,
    horizon_days: int,
    adapter_names: tuple[str, ...],
) -> list[AdvancedForecastEvaluation]:
    evaluations: list[AdvancedForecastEvaluation] = []
    for adapter_name in adapter_names:
        try:
            evaluations.append(
                evaluate_advanced_forecast(
                    bars,
                    adapter_name=adapter_name,
                    horizon_days=horizon_days,
                )
            )
        except ValueError:
            continue
    return evaluations


def _rolling_origins(
    bar_count: int,
    *,
    horizon_days: int,
    max_origins: int,
) -> list[int]:
    minimum_history = max(40, horizon_days + 24)
    first = minimum_history - 1
    last = bar_count - horizon_days - 1
    if last < first:
        return []
    available = list(range(first, last + 1))
    if len(available) <= max_origins:
        return available
    if max_origins == 1:
        return [available[-1]]
    selected = {
        available[round(index * (len(available) - 1) / (max_origins - 1))]
        for index in range(max_origins)
    }
    return sorted(selected)


def _forward_return(bars: list[Bar], origin_index: int, horizon_days: int) -> Decimal:
    origin = bars[origin_index].close
    target = bars[origin_index + horizon_days].close
    if origin <= 0:
        return Decimal("0.0000")
    return _decimal((target / origin) - Decimal("1"))


def _aggregate_all_groups(
    points: list[ForecastValidationPoint],
    *,
    cases: list[ForecastEvaluationCase],
    horizons: tuple[int, ...],
    model_names: tuple[str, ...],
    skipped: dict[tuple[str, int], int],
) -> list[ForecastModelEvaluationRow]:
    rows: list[ForecastModelEvaluationRow] = []
    group_values = {
        "overall": ("all",),
        "market": tuple(sorted({case.market for case in cases})),
        "asset_type": tuple(sorted({case.asset_type for case in cases})),
        "regime": tuple(sorted({case.regime for case in cases})),
    }
    for group_type, values in group_values.items():
        for group_value in values:
            for horizon in horizons:
                for model_name in model_names:
                    selected = [
                        point
                        for point in points
                        if point.horizon_days == horizon
                        and point.model_name == model_name
                        and _point_group_value(point, group_type) == group_value
                    ]
                    rows.append(
                        _aggregate_points(
                            selected,
                            group_type=group_type,
                            group_value=group_value,
                            model_name=model_name,
                            horizon_days=horizon,
                            skipped_case_count=(
                                skipped[(model_name, horizon)] if group_type == "overall" else 0
                            ),
                        )
                    )
    return rows


def _aggregate_points(
    points: list[ForecastValidationPoint],
    *,
    group_type: str,
    group_value: str,
    model_name: str,
    horizon_days: int,
    skipped_case_count: int,
) -> ForecastModelEvaluationRow:
    errors = [point.predicted_return - point.actual_return for point in points]
    actuals = [point.actual_return for point in points]
    mae = _mean([abs(error) for error in errors])
    rmse = _root_mean_square(errors)
    baseline_rmse = _root_mean_square(actuals)
    direction_accuracy = _direction_accuracy(points)
    disagreements = [
        point.model_disagreement for point in points if point.model_disagreement is not None
    ]
    return ForecastModelEvaluationRow(
        group_type=group_type,
        group_value=group_value,
        model_name=model_name,
        horizon_days=horizon_days,
        evaluated_case_count=len({point.symbol for point in points}),
        skipped_case_count=skipped_case_count,
        validation_sample_count=len(points),
        fold_count=len({(point.symbol, point.origin_at) for point in points}),
        mae=mae,
        rmse=rmse,
        direction_accuracy=direction_accuracy,
        baseline_zero_rmse=baseline_rmse,
        rmse_improvement=_decimal(baseline_rmse - rmse),
        mean_model_disagreement=(_mean(disagreements) if disagreements else None),
    )


def _build_weight_adjustments(
    points: list[ForecastValidationPoint],
    *,
    horizons: tuple[int, ...],
    adapter_names: tuple[str, ...],
) -> list[ForecastWeightAdjustment]:
    adjustments: list[ForecastWeightAdjustment] = []
    for horizon in horizons:
        horizon_points = [point for point in points if point.horizon_days == horizon]
        origins = sorted({point.origin_at for point in horizon_points})
        split_index = max(1, int(len(origins) * 0.6)) if len(origins) >= 2 else len(origins)
        tuning_origins = set(origins[:split_index])
        holdout_origins = set(origins[split_index:])
        tuning_points = [point for point in horizon_points if point.origin_at in tuning_origins]
        holdout_points = [point for point in horizon_points if point.origin_at in holdout_origins]
        model_rows = {
            model_name: _aggregate_points(
                [point for point in tuning_points if point.model_name == model_name],
                group_type="overall",
                group_value="all",
                model_name=model_name,
                horizon_days=horizon,
                skipped_case_count=0,
            )
            for model_name in adapter_names
        }
        weights = _quality_weights(model_rows)
        current_points = {
            (point.symbol, point.origin_at): point
            for point in holdout_points
            if point.model_name == CONSENSUS_MODEL_NAME
        }
        model_points: dict[tuple[str, datetime], dict[str, Decimal]] = defaultdict(dict)
        for point in holdout_points:
            if point.model_name in adapter_names:
                model_points[(point.symbol, point.origin_at)][
                    point.model_name
                ] = point.predicted_return
        candidate_points: list[ForecastValidationPoint] = []
        comparable_current: list[ForecastValidationPoint] = []
        for key, predictions in model_points.items():
            current = current_points.get(key)
            if current is None or set(predictions) != set(weights):
                continue
            comparable_current.append(current)
            candidate_points.append(
                current.model_copy(
                    update={
                        "model_name": "candidate_consensus",
                        "predicted_return": _weighted_prediction(predictions, weights),
                    }
                )
            )
        current_rmse = _points_rmse(comparable_current)
        candidate_rmse = _points_rmse(candidate_points)
        current_direction = _direction_accuracy(comparable_current)
        candidate_direction = _direction_accuracy(candidate_points)
        required_rmse = current_rmse * (Decimal("1") - MIN_RELATIVE_RMSE_IMPROVEMENT)
        adopted = bool(candidate_points) and (
            candidate_rmse <= required_rmse and candidate_direction >= current_direction
        )
        reason = (
            "時系列holdoutでRMSEを1%以上改善し、方向一致率を維持したため採用候補です。"
            if adopted
            else "時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。"
        )
        adjustments.append(
            ForecastWeightAdjustment(
                horizon_days=horizon,
                model_weights=weights,
                tuning_sample_count=len(tuning_origins),
                holdout_sample_count=len(holdout_origins),
                current_consensus_rmse=current_rmse,
                candidate_consensus_rmse=candidate_rmse,
                current_direction_accuracy=current_direction,
                candidate_direction_accuracy=candidate_direction,
                adopted=adopted,
                reason=reason,
            )
        )
    return adjustments


def _quality_weights(
    rows: dict[str, ForecastModelEvaluationRow],
) -> dict[str, Decimal]:
    raw: dict[str, Decimal] = {}
    for model_name, row in rows.items():
        baseline = row.baseline_zero_rmse
        if baseline <= 0 or row.validation_sample_count == 0:
            raw[model_name] = Decimal("0.01")
            continue
        relative_rmse = row.rmse / baseline
        error_quality = Decimal("1") / max(Decimal("0.25"), relative_rmse)
        error_quality = min(Decimal("2"), error_quality)
        direction_quality = Decimal("0.50") + row.direction_accuracy
        baseline_penalty = Decimal("0.20") if row.rmse_improvement < 0 else Decimal("1")
        raw[model_name] = max(
            Decimal("0.01"),
            error_quality * direction_quality * baseline_penalty,
        )
    total = sum(raw.values(), Decimal("0"))
    if total <= 0:
        equal = Decimal("1") / Decimal(len(raw)) if raw else Decimal("0")
        return {name: _decimal(equal) for name in raw}
    return {name: _decimal(value / total) for name, value in raw.items()}


def _weighted_prediction(
    predictions: dict[str, Decimal],
    weights: dict[str, Decimal],
) -> Decimal:
    total_weight = sum(weights.values(), Decimal("0"))
    if total_weight <= 0:
        return Decimal("0.0000")
    return _decimal(
        sum(predictions[name] * weight for name, weight in weights.items() if name in predictions)
        / total_weight
    )


def _point_group_value(point: ForecastValidationPoint, group_type: str) -> str:
    if group_type == "overall":
        return "all"
    return str(getattr(point, group_type))


def _direction_accuracy(points: list[ForecastValidationPoint]) -> Decimal:
    if not points:
        return Decimal("0.0000")
    matches = sum(
        1
        for point in points
        if _sign(
            point.direction_predicted_return
            if point.direction_predicted_return is not None
            else point.predicted_return
        )
        == _sign(point.actual_return)
    )
    return _decimal(Decimal(matches) / Decimal(len(points)))


def _points_rmse(points: list[ForecastValidationPoint]) -> Decimal:
    return _root_mean_square([point.predicted_return - point.actual_return for point in points])


def _root_mean_square(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.0000")
    mean_square = sum((value * value for value in values), Decimal("0")) / Decimal(len(values))
    return _decimal(mean_square.sqrt())


def _mean(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.0000")
    return _decimal(sum(values, Decimal("0")) / Decimal(len(values)))


def _sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _validated_horizons(horizons: tuple[int, ...]) -> tuple[int, ...]:
    normalized = tuple(dict.fromkeys(horizons))
    if not normalized or any(horizon < 1 for horizon in normalized):
        raise ValueError("horizons must contain positive values")
    return normalized


def _validated_adapters(adapter_names: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(name.strip() for name in adapter_names if name.strip()))
    if not normalized or any(advanced_forecast_adapter_spec(name) is None for name in normalized):
        raise ValueError("adapter_names must contain registered advanced forecast adapters")
    return normalized


def _write_group_csv(
    path: Path,
    rows: list[ForecastModelEvaluationRow],
    *,
    group_type: str,
) -> None:
    selected = [row for row in rows if row.group_type == group_type]
    fieldnames = list(ForecastModelEvaluationRow.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in selected:
            writer.writerow({field: _csv_value(getattr(row, field)) for field in fieldnames})


def _write_predictions_csv(path: Path, rows: list[ForecastPredictionRow]) -> None:
    fieldnames = list(ForecastPredictionRow.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(getattr(row, field)) for field in fieldnames})


def _write_validation_points_csv(path: Path, rows: list[ForecastValidationPoint]) -> None:
    fieldnames = list(ForecastValidationPoint.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(getattr(row, field)) for field in fieldnames})


def _render_summary(report: ForecastModelEvaluationReport) -> str:
    overall = [row for row in report.rows if row.group_type == "overall"]
    lines = [
        "# Forecast Model Evaluation Summary",
        "",
        "未来情報を使わないrolling-origin評価です。"
        "予測は投資助言や将来成果の保証ではありません。",
        "",
        f"- 評価ケース数: {report.requested_case_count}",
        f"- 対象horizon: {', '.join(str(value) for value in report.horizons)}営業日",
        f"- rolling-origin予測数: {len(report.validation_points)}",
        "- 改善weightは後半holdoutで現行consensusと比較し、条件通過時だけ採用候補にします。",
        "",
        "| Model | Horizon | Cases | Samples | MAE | RMSE | Direction | "
        "RMSE improvement | Disagreement |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in overall:
        lines.append(
            f"| {row.model_name} | {row.horizon_days} | {row.evaluated_case_count} | "
            f"{row.validation_sample_count} | {row.mae} | {row.rmse} | "
            f"{row.direction_accuracy} | {row.rmse_improvement} | "
            f"{_display_optional(row.mean_model_disagreement)} |"
        )
    if report.warnings:
        lines.extend(["", "## 注意", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"


def _render_error_cases(points: list[ForecastValidationPoint]) -> str:
    sorted_points = sorted(
        points,
        key=lambda point: abs(point.predicted_return - point.actual_return),
        reverse=True,
    )[:20]
    lines = [
        "# Forecast Model Error Cases",
        "",
        "誤差が大きいrolling-origin例です。売買判断ではなくモデル改善用です。",
        "",
        "| Symbol | Model | Horizon | Origin | Predicted | Actual | Absolute error |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for point in sorted_points:
        error = abs(point.predicted_return - point.actual_return)
        lines.append(
            f"| {point.symbol} | {point.model_name} | {point.horizon_days} | "
            f"{point.origin_at.date().isoformat()} | {point.predicted_return} | "
            f"{point.actual_return} | {_decimal(error)} |"
        )
    return "\n".join(lines) + "\n"


def _render_weight_adjustments(
    adjustments: list[ForecastWeightAdjustment],
) -> str:
    lines = [
        "# Forecast Model Weighting Adjustments",
        "",
        "同一rolling-origin foldで現行consensusと候補weightを比較します。"
        "前半originでweightを作り、後半holdoutでRMSE 1%以上改善かつ方向一致率維持を確認します。",
        "",
    ]
    for adjustment in adjustments:
        lines.extend(
            [
                f"## {adjustment.horizon_days}営業日",
                "",
                f"- 判定: {'採用候補' if adjustment.adopted else '保留'}",
                f"- tuning origin数: {adjustment.tuning_sample_count}",
                f"- holdout origin数: {adjustment.holdout_sample_count}",
                f"- 現行RMSE: {adjustment.current_consensus_rmse}",
                f"- 候補RMSE: {adjustment.candidate_consensus_rmse}",
                f"- 現行方向一致率: {adjustment.current_direction_accuracy}",
                f"- 候補方向一致率: {adjustment.candidate_direction_accuracy}",
                f"- 理由: {adjustment.reason}",
                "- 候補weight:",
            ]
        )
        lines.extend(f"  - `{name}`: {weight}" for name, weight in adjustment.model_weights.items())
        lines.append("")
    return "\n".join(lines)


def _display_optional(value: Decimal | None) -> str:
    return str(value) if value is not None else "-"


def _csv_value(value: object) -> object:
    return "" if value is None else value


def _decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))
