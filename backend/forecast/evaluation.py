from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from pydantic import ConfigDict, Field

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.forecast.advanced_registry import (
    advanced_forecast_adapter_keys,
    advanced_forecast_adapter_spec,
)
from backend.forecast.service import (
    AdvancedForecastEvaluation,
    evaluate_advanced_forecast,
    summarize_advanced_forecast_evaluations,
)

DEFAULT_EVALUATION_HORIZONS = (20, 60)
CONSENSUS_MODEL_NAME = "forecast_consensus"


class ForecastEvaluationCase(StrictBaseModel):
    """Point-in-time price history and grouping metadata for one symbol."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    bars: list[Bar]
    market: str = Field(default="unknown", min_length=1)
    asset_type: str = Field(default="unknown", min_length=1)
    regime: str = Field(default="unknown", min_length=1)


class ForecastModelEvaluationRow(StrictBaseModel):
    """Aggregated walk-forward metrics for one model and horizon."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str = Field(min_length=1)
    evaluation_method: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    evaluated_case_count: int = Field(ge=0)
    skipped_case_count: int = Field(ge=0)
    validation_sample_count: int = Field(ge=0)
    fold_count: int = Field(ge=0)
    mae: Decimal = Field(ge=0)
    rmse: Decimal = Field(ge=0)
    direction_accuracy: Decimal = Field(ge=0, le=1)
    rmse_improvement: Decimal | None = None
    mean_model_disagreement: Decimal | None = Field(default=None, ge=0)
    low_confidence_count: int = Field(default=0, ge=0)
    medium_confidence_count: int = Field(default=0, ge=0)
    high_confidence_count: int = Field(default=0, ge=0)


class ForecastModelEvaluationReport(StrictBaseModel):
    """Deterministic Phase 33 evaluation result."""

    model_config = ConfigDict(extra="forbid")

    horizons: list[int]
    requested_case_count: int = Field(ge=0)
    rows: list[ForecastModelEvaluationRow]
    warnings: list[str] = Field(default_factory=list)


def evaluate_forecast_models(
    cases: list[ForecastEvaluationCase],
    *,
    horizons: tuple[int, ...] = DEFAULT_EVALUATION_HORIZONS,
    adapter_names: tuple[str, ...] | None = None,
) -> ForecastModelEvaluationReport:
    """Evaluate registered advanced models without network or future-data access."""

    resolved_horizons = _validated_horizons(horizons)
    resolved_adapters = _validated_adapters(adapter_names or advanced_forecast_adapter_keys())
    evaluations: dict[tuple[str, int], list[AdvancedForecastEvaluation]] = defaultdict(list)
    skipped: dict[tuple[str, int], int] = defaultdict(int)
    consensus_by_horizon: dict[int, list[tuple[list[AdvancedForecastEvaluation], Decimal]]] = (
        defaultdict(list)
    )

    for case in cases:
        bars = sorted(case.bars, key=lambda bar: bar.ts)
        for horizon in resolved_horizons:
            case_evaluations: list[AdvancedForecastEvaluation] = []
            for adapter_name in resolved_adapters:
                try:
                    evaluation = evaluate_advanced_forecast(
                        bars,
                        adapter_name=adapter_name,
                        horizon_days=horizon,
                    )
                except ValueError:
                    skipped[(adapter_name, horizon)] += 1
                    continue
                if evaluation.validation_metrics.fold_count <= 0:
                    skipped[(adapter_name, horizon)] += 1
                    continue
                evaluations[(adapter_name, horizon)].append(evaluation)
                case_evaluations.append(evaluation)
            consensus = summarize_advanced_forecast_evaluations(case_evaluations)
            if consensus is not None:
                consensus_by_horizon[horizon].append(
                    (case_evaluations, consensus.predicted_return_range)
                )
            else:
                skipped[(CONSENSUS_MODEL_NAME, horizon)] += 1

    rows: list[ForecastModelEvaluationRow] = []
    for horizon in resolved_horizons:
        for adapter_name in resolved_adapters:
            rows.append(
                _aggregate_model_rows(
                    adapter_name,
                    horizon,
                    evaluations[(adapter_name, horizon)],
                    skipped_case_count=skipped[(adapter_name, horizon)],
                )
            )
        rows.append(
            _aggregate_consensus_rows(
                horizon,
                consensus_by_horizon[horizon],
                skipped_case_count=skipped[(CONSENSUS_MODEL_NAME, horizon)],
            )
        )

    warnings: list[str] = []
    if not cases:
        warnings.append("評価ケースがありません。")
    if any(row.skipped_case_count for row in rows):
        warnings.append(
            "履歴不足などで評価できないケースがあります。skipped_case_countを確認してください。"
        )
    return ForecastModelEvaluationReport(
        horizons=list(resolved_horizons),
        requested_case_count=len(cases),
        rows=rows,
        warnings=warnings,
    )


def write_forecast_evaluation_artifacts(
    report: ForecastModelEvaluationReport,
    output_dir: Path,
) -> dict[str, Path]:
    """Write the first Phase 33 Markdown and horizon CSV artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "forecast_model_evaluation_summary.md"
    horizon_path = output_dir / "forecast_model_evaluation_by_horizon.csv"
    summary_path.write_text(_render_summary(report), encoding="utf-8")
    with horizon_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "model_name",
            "evaluation_method",
            "horizon_days",
            "evaluated_case_count",
            "skipped_case_count",
            "validation_sample_count",
            "fold_count",
            "mae",
            "rmse",
            "direction_accuracy",
            "rmse_improvement",
            "mean_model_disagreement",
            "low_confidence_count",
            "medium_confidence_count",
            "high_confidence_count",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in report.rows:
            writer.writerow({field: _csv_value(getattr(row, field)) for field in fieldnames})
    return {
        "summary": summary_path,
        "by_horizon": horizon_path,
    }


def _aggregate_model_rows(
    model_name: str,
    horizon_days: int,
    evaluations: list[AdvancedForecastEvaluation],
    *,
    skipped_case_count: int,
) -> ForecastModelEvaluationRow:
    sample_count = sum(row.validation_metrics.sample_count for row in evaluations)
    return ForecastModelEvaluationRow(
        model_name=model_name,
        evaluation_method="adapter_walk_forward",
        horizon_days=horizon_days,
        evaluated_case_count=len(evaluations),
        skipped_case_count=skipped_case_count,
        validation_sample_count=sample_count,
        fold_count=sum(row.validation_metrics.fold_count for row in evaluations),
        mae=_weighted_metric(evaluations, "mae"),
        rmse=_pooled_rmse(evaluations),
        direction_accuracy=_weighted_metric(evaluations, "direction_accuracy"),
        rmse_improvement=_weighted_optional_metric(evaluations, "rmse_improvement"),
        low_confidence_count=_confidence_count(evaluations, "low"),
        medium_confidence_count=_confidence_count(evaluations, "medium"),
        high_confidence_count=_confidence_count(evaluations, "high"),
    )


def _aggregate_consensus_rows(
    horizon_days: int,
    groups: list[tuple[list[AdvancedForecastEvaluation], Decimal]],
    *,
    skipped_case_count: int,
) -> ForecastModelEvaluationRow:
    case_weights = [_case_weight(group) for group, _disagreement in groups]
    case_mae = [_case_metric(group, "mae") for group, _disagreement in groups]
    case_rmse = [_case_rmse(group) for group, _disagreement in groups]
    case_direction = [_case_metric(group, "direction_accuracy") for group, _disagreement in groups]
    case_improvements = [
        _case_optional_metric(group, "rmse_improvement") for group, _disagreement in groups
    ]
    consensus_confidences: list[str] = []
    for group, _disagreement in groups:
        consensus = summarize_advanced_forecast_evaluations(group)
        if consensus is not None:
            consensus_confidences.append(consensus.confidence)
    total_weight = sum(case_weights)
    disagreements = [disagreement for _group, disagreement in groups]
    return ForecastModelEvaluationRow(
        model_name=CONSENSUS_MODEL_NAME,
        evaluation_method="component_metric_proxy",
        horizon_days=horizon_days,
        evaluated_case_count=len(groups),
        skipped_case_count=skipped_case_count,
        validation_sample_count=total_weight,
        fold_count=sum(
            max(row.validation_metrics.fold_count for row in group)
            for group, _disagreement in groups
        ),
        mae=_weighted_values(case_weights, case_mae),
        rmse=_weighted_values(case_weights, case_rmse),
        direction_accuracy=_weighted_values(case_weights, case_direction),
        rmse_improvement=_weighted_optional_values(case_weights, case_improvements),
        mean_model_disagreement=(
            _decimal(sum(disagreements, Decimal("0")) / Decimal(len(disagreements)))
            if disagreements
            else Decimal("0.0000")
        ),
        low_confidence_count=consensus_confidences.count("low"),
        medium_confidence_count=consensus_confidences.count("medium"),
        high_confidence_count=consensus_confidences.count("high"),
    )


def _validated_horizons(horizons: tuple[int, ...]) -> tuple[int, ...]:
    normalized = tuple(dict.fromkeys(horizons))
    if not normalized or any(horizon < 1 or horizon > 60 for horizon in normalized):
        raise ValueError("horizons must contain values between 1 and 60")
    return normalized


def _validated_adapters(adapter_names: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(name.strip() for name in adapter_names if name.strip()))
    if not normalized or any(advanced_forecast_adapter_spec(name) is None for name in normalized):
        raise ValueError("adapter_names must contain registered advanced forecast adapters")
    return normalized


def _weighted_metric(
    evaluations: list[AdvancedForecastEvaluation],
    field: str,
) -> Decimal:
    total_weight = sum(row.validation_metrics.sample_count for row in evaluations)
    if total_weight <= 0:
        return Decimal("0.0000")
    total = sum(
        getattr(row.validation_metrics, field) * Decimal(row.validation_metrics.sample_count)
        for row in evaluations
    )
    return _decimal(total / Decimal(total_weight))


def _pooled_rmse(evaluations: list[AdvancedForecastEvaluation]) -> Decimal:
    total_weight = sum(row.validation_metrics.sample_count for row in evaluations)
    if total_weight <= 0:
        return Decimal("0.0000")
    squared = sum(
        (row.validation_metrics.rmse**2) * Decimal(row.validation_metrics.sample_count)
        for row in evaluations
    )
    return _decimal((squared / Decimal(total_weight)).sqrt())


def _weighted_optional_metric(
    evaluations: list[AdvancedForecastEvaluation],
    field: str,
) -> Decimal | None:
    available = [row for row in evaluations if getattr(row.validation_metrics, field) is not None]
    if not available:
        return None
    return _weighted_metric(available, field)


def _confidence_count(
    evaluations: list[AdvancedForecastEvaluation],
    confidence: str,
) -> int:
    return sum(1 for row in evaluations if row.confidence == confidence)


def _case_weight(evaluations: list[AdvancedForecastEvaluation]) -> int:
    if not evaluations:
        return 0
    return max(row.validation_metrics.sample_count for row in evaluations)


def _case_metric(
    evaluations: list[AdvancedForecastEvaluation],
    field: str,
) -> Decimal:
    if not evaluations:
        return Decimal("0.0000")
    return _decimal(
        sum(
            (getattr(row.validation_metrics, field) for row in evaluations),
            Decimal("0"),
        )
        / Decimal(len(evaluations))
    )


def _case_rmse(evaluations: list[AdvancedForecastEvaluation]) -> Decimal:
    if not evaluations:
        return Decimal("0.0000")
    mean_square = sum(
        (row.validation_metrics.rmse**2 for row in evaluations),
        Decimal("0"),
    ) / Decimal(len(evaluations))
    return _decimal(mean_square.sqrt())


def _case_optional_metric(
    evaluations: list[AdvancedForecastEvaluation],
    field: str,
) -> Decimal | None:
    values = [
        getattr(row.validation_metrics, field)
        for row in evaluations
        if getattr(row.validation_metrics, field) is not None
    ]
    if not values:
        return None
    return _decimal(sum(values, Decimal("0")) / Decimal(len(values)))


def _weighted_values(
    weights: list[int],
    values: list[Decimal],
) -> Decimal:
    total_weight = sum(weights)
    if total_weight <= 0:
        return Decimal("0.0000")
    return _decimal(
        sum(
            (value * Decimal(weight) for weight, value in zip(weights, values, strict=True)),
            Decimal("0"),
        )
        / Decimal(total_weight)
    )


def _weighted_optional_values(
    weights: list[int],
    values: list[Decimal | None],
) -> Decimal | None:
    available = [
        (weight, value) for weight, value in zip(weights, values, strict=True) if value is not None
    ]
    if not available:
        return None
    total_weight = sum(weight for weight, _value in available)
    if total_weight <= 0:
        return Decimal("0.0000")
    return _decimal(
        sum(
            (value * Decimal(weight) for weight, value in available),
            Decimal("0"),
        )
        / Decimal(total_weight)
    )


def _render_summary(report: ForecastModelEvaluationReport) -> str:
    lines = [
        "# Forecast Model Evaluation Summary",
        "",
        "既存advanced forecastモデルのwalk-forward評価です。"
        "予測は投資助言や将来成果の保証ではありません。",
        "",
        f"- 評価ケース数: {report.requested_case_count}",
        f"- 対象horizon: {', '.join(str(value) for value in report.horizons)}営業日",
        "- 通常ランキングとは分離した、明示実行のオフライン評価です。",
        "",
        "| Model | Method | Horizon | Cases | Skipped | Samples | MAE | RMSE | Direction | "
        "RMSE improvement | Disagreement | Confidence (L/M/H) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report.rows:
        lines.append(
            f"| {row.model_name} | {row.evaluation_method} | {row.horizon_days} | "
            f"{row.evaluated_case_count} | "
            f"{row.skipped_case_count} | {row.validation_sample_count} | {row.mae} | "
            f"{row.rmse} | {row.direction_accuracy} | "
            f"{_display_optional(row.rmse_improvement)} | "
            f"{_display_optional(row.mean_model_disagreement)} | "
            f"{row.low_confidence_count}/{row.medium_confidence_count}/"
            f"{row.high_confidence_count} |"
        )
    if report.warnings:
        lines.extend(["", "## 注意", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"


def _display_optional(value: Decimal | None) -> str:
    return str(value) if value is not None else "-"


def _csv_value(value: object) -> object:
    return "" if value is None else value


def _decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))
