"""Offline evaluation for bounded LLM material confidence/range adjustments."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Literal, Sequence

from pydantic import ConfigDict, Field

from backend.core.data_contracts import StrictBaseModel
from backend.forecast.evaluation import CONSENSUS_MODEL_NAME, ForecastValidationPoint
from backend.llm_factor.material_archive import (
    LLMMaterialRiskSignal,
    PointInTimeMaterialRecord,
    build_material_risk_shadow_adjustment,
)

MATERIAL_SHADOW_EVALUATION_SCHEMA_VERSION = "llm-material-shadow-evaluation-v1"
MIN_MATERIAL_SHADOW_ADOPTION_CASES = 100
MIN_MATERIAL_SHADOW_INTERVAL_SCORE_IMPROVEMENT = Decimal("0.01")

MaterialShadowAdoptionStatus = Literal[
    "insufficient_evidence",
    "retain_shadow",
    "confidence_range_candidate",
]


class MaterialShadowEvaluationCase(StrictBaseModel):
    """One causally matched forecast, material signal, and realized return."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    target_at: datetime
    baseline_center: Decimal
    baseline_lower: Decimal
    baseline_upper: Decimal
    adjusted_lower: Decimal
    adjusted_upper: Decimal
    actual_return: Decimal
    range_multiplier: Decimal = Field(ge=1, le=Decimal("1.25"))
    confidence_cap: str | None = None
    baseline_covered: bool
    adjusted_covered: bool
    baseline_interval_score: Decimal = Field(ge=0)
    adjusted_interval_score: Decimal = Field(ge=0)
    cited_record_count: int = Field(ge=1)


class MaterialShadowMetricRow(StrictBaseModel):
    """Coverage, width, and proper interval-score comparison for one horizon group."""

    group_type: str = Field(min_length=1)
    group_value: str = Field(min_length=1)
    horizon_days: int = Field(ge=0)
    sample_count: int = Field(ge=0)
    baseline_coverage: Decimal = Field(ge=0, le=1)
    adjusted_coverage: Decimal = Field(ge=0, le=1)
    baseline_mean_width: Decimal = Field(ge=0)
    adjusted_mean_width: Decimal = Field(ge=0)
    baseline_interval_score: Decimal = Field(ge=0)
    adjusted_interval_score: Decimal = Field(ge=0)
    interval_score_improvement: Decimal
    low_cap_count: int = Field(ge=0)
    medium_cap_count: int = Field(ge=0)


class MaterialShadowEvaluationReport(StrictBaseModel):
    """Evaluation report; center-return and direction changes are structurally forbidden."""

    schema_version: str = MATERIAL_SHADOW_EVALUATION_SCHEMA_VERSION
    eligible_forecast_count: int = Field(ge=0)
    matched_signal_count: int = Field(ge=0)
    applied_case_count: int = Field(ge=0)
    cases: list[MaterialShadowEvaluationCase] = Field(default_factory=list)
    metrics: list[MaterialShadowMetricRow] = Field(default_factory=list)
    adoption_status: MaterialShadowAdoptionStatus
    adoption_reasons: list[str] = Field(default_factory=list)
    center_return_changed: bool = False
    direction_return_changed: bool = False


def evaluate_material_risk_shadow(
    forecast_points: Iterable[ForecastValidationPoint],
    signals: Iterable[LLMMaterialRiskSignal],
    records: Iterable[PointInTimeMaterialRecord],
    *,
    target_interval_coverage: Decimal = Decimal("0.60"),
) -> MaterialShadowEvaluationReport:
    """Compare bounded range adjustments without altering price or direction predictions."""

    if target_interval_coverage <= 0 or target_interval_coverage >= 1:
        raise ValueError("target_interval_coverage must be between zero and one")
    eligible = [
        point
        for point in forecast_points
        if point.model_name == CONSENSUS_MODEL_NAME
        and point.predicted_return_lower is not None
        and point.predicted_return_upper is not None
        and point.predicted_return_upper >= point.predicted_return_lower
    ]
    signal_by_key = {
        (signal.symbol.strip().upper(), signal.horizon_days, signal.decision_at): signal
        for signal in signals
    }
    archive = list(records)
    cases: list[MaterialShadowEvaluationCase] = []
    matched_signal_count = 0
    for point in eligible:
        signal = signal_by_key.get(
            (point.symbol.strip().upper(), point.horizon_days, point.origin_at)
        )
        if signal is None:
            continue
        matched_signal_count += 1
        adjustment = build_material_risk_shadow_adjustment(signal, archive)
        if not adjustment.applied:
            continue
        lower = point.predicted_return_lower
        upper = point.predicted_return_upper
        if lower is None or upper is None:  # pragma: no cover - narrowed above
            continue
        adjusted_lower = point.predicted_return - (
            (point.predicted_return - lower) * adjustment.range_multiplier
        )
        adjusted_upper = point.predicted_return + (
            (upper - point.predicted_return) * adjustment.range_multiplier
        )
        cases.append(
            MaterialShadowEvaluationCase(
                symbol=point.symbol,
                horizon_days=point.horizon_days,
                origin_at=point.origin_at,
                target_at=point.target_at,
                baseline_center=point.predicted_return,
                baseline_lower=lower,
                baseline_upper=upper,
                adjusted_lower=adjusted_lower,
                adjusted_upper=adjusted_upper,
                actual_return=point.actual_return,
                range_multiplier=adjustment.range_multiplier,
                confidence_cap=adjustment.confidence_cap,
                baseline_covered=lower <= point.actual_return <= upper,
                adjusted_covered=adjusted_lower <= point.actual_return <= adjusted_upper,
                baseline_interval_score=_interval_score(
                    point.actual_return,
                    lower,
                    upper,
                    target_interval_coverage=target_interval_coverage,
                ),
                adjusted_interval_score=_interval_score(
                    point.actual_return,
                    adjusted_lower,
                    adjusted_upper,
                    target_interval_coverage=target_interval_coverage,
                ),
                cited_record_count=len(adjustment.valid_cited_record_ids),
            )
        )
    metrics = _metric_rows(cases)
    status, reasons = _adoption_decision(cases, metrics)
    return MaterialShadowEvaluationReport(
        eligible_forecast_count=len(eligible),
        matched_signal_count=matched_signal_count,
        applied_case_count=len(cases),
        cases=cases,
        metrics=metrics,
        adoption_status=status,
        adoption_reasons=reasons,
    )


def write_material_risk_shadow_outputs(
    report: MaterialShadowEvaluationReport,
    output_dir: Path,
) -> dict[str, Path]:
    """Write deterministic report artifacts for later mature-archive evaluation."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "cases": output_dir / "llm_material_shadow_cases.csv",
        "metrics": output_dir / "llm_material_shadow_metrics.csv",
        "report": output_dir / "llm_material_shadow_report.md",
    }
    _write_models_csv(paths["cases"], report.cases, MaterialShadowEvaluationCase)
    _write_models_csv(paths["metrics"], report.metrics, MaterialShadowMetricRow)
    paths["report"].write_text(_report_markdown(report), encoding="utf-8", newline="\n")
    return paths


def _metric_rows(cases: list[MaterialShadowEvaluationCase]) -> list[MaterialShadowMetricRow]:
    grouped: dict[tuple[str, str, int], list[MaterialShadowEvaluationCase]] = defaultdict(list)
    grouped[("overall", "all", 0)] = list(cases)
    for case in cases:
        grouped[("horizon", str(case.horizon_days), case.horizon_days)].append(case)
    return [
        _aggregate_cases(selected, group_type=key[0], group_value=key[1], horizon_days=key[2])
        for key, selected in sorted(grouped.items())
    ]


def _aggregate_cases(
    cases: list[MaterialShadowEvaluationCase],
    *,
    group_type: str,
    group_value: str,
    horizon_days: int,
) -> MaterialShadowMetricRow:
    baseline_score = _mean([case.baseline_interval_score for case in cases])
    adjusted_score = _mean([case.adjusted_interval_score for case in cases])
    improvement = (
        (baseline_score - adjusted_score) / baseline_score if baseline_score > 0 else Decimal("0")
    )
    return MaterialShadowMetricRow(
        group_type=group_type,
        group_value=group_value,
        horizon_days=horizon_days,
        sample_count=len(cases),
        baseline_coverage=_mean([Decimal(case.baseline_covered) for case in cases]),
        adjusted_coverage=_mean([Decimal(case.adjusted_covered) for case in cases]),
        baseline_mean_width=_mean([case.baseline_upper - case.baseline_lower for case in cases]),
        adjusted_mean_width=_mean([case.adjusted_upper - case.adjusted_lower for case in cases]),
        baseline_interval_score=baseline_score,
        adjusted_interval_score=adjusted_score,
        interval_score_improvement=_round(improvement),
        low_cap_count=sum(case.confidence_cap == "low" for case in cases),
        medium_cap_count=sum(case.confidence_cap == "medium" for case in cases),
    )


def _adoption_decision(
    cases: list[MaterialShadowEvaluationCase],
    metrics: list[MaterialShadowMetricRow],
) -> tuple[MaterialShadowAdoptionStatus, list[str]]:
    overall = next((row for row in metrics if row.group_type == "overall"), None)
    if overall is None or len(cases) < MIN_MATERIAL_SHADOW_ADOPTION_CASES:
        return "insufficient_evidence", [
            f"時点整合した成熟caseが{MIN_MATERIAL_SHADOW_ADOPTION_CASES}件未満",
            "中心returnと方向returnは変更しない",
        ]
    if (
        overall.interval_score_improvement < MIN_MATERIAL_SHADOW_INTERVAL_SCORE_IMPROVEMENT
        or overall.adjusted_coverage < overall.baseline_coverage
    ):
        return "retain_shadow", [
            "proper interval scoreまたはcoverageの改善gateを満たさない",
            "中心returnと方向returnは変更しない",
        ]
    return "confidence_range_candidate", [
        "時点整合caseでinterval scoreとcoverageのgateを通過",
        "候補はconfidence上限とrangeのみ。中心returnと方向returnは変更しない",
    ]


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
    return _round(score)


def _mean(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0.0000")
    return _round(sum(values, Decimal("0")) / Decimal(len(values)))


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


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


def _report_markdown(report: MaterialShadowEvaluationReport) -> str:
    lines = [
        "# LLM材料リスク shadow評価",
        "",
        "LLMは価格中心値と方向値を変更せず、confidence上限とrange拡張だけを比較します。",
        "",
        f"- 評価可能Forecast: {report.eligible_forecast_count}",
        f"- 時点一致signal: {report.matched_signal_count}",
        f"- 適用case: {report.applied_case_count}",
        f"- 採用判定: `{report.adoption_status}`",
        "- center_return_changed: false",
        "- direction_return_changed: false",
        "",
        "| Group | Horizon | Cases | Coverage before | Coverage after | Interval score before | Interval score after | Improvement |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.metrics:
        lines.append(
            f"| {row.group_value} | {row.horizon_days or '-'} | {row.sample_count} | "
            f"{row.baseline_coverage} | {row.adjusted_coverage} | "
            f"{row.baseline_interval_score} | {row.adjusted_interval_score} | "
            f"{row.interval_score_improvement} |"
        )
    lines.extend(["", "## 判定理由", ""])
    lines.extend(f"- {reason}" for reason in report.adoption_reasons)
    return "\n".join(lines) + "\n"
