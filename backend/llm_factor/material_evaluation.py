from __future__ import annotations

import csv
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field

from backend.core.data_contracts import StrictBaseModel

LLM_MATERIAL_EVALUATION_SCHEMA_VERSION = "llm-material-evaluation-v1"
LLMMaterialReviewStatus = Literal["retain", "caution", "unavailable"]
LLMMaterialRunStatus = Literal["completed", "failed", "skipped"]
LLMMaterialAdoptionStatus = Literal[
    "evidence_insufficient",
    "badge_only_candidate",
    "not_adopted",
]


class LLMMaterialEvaluationCase(StrictBaseModel):
    """One point-in-time top-candidate material review for Phase 36.

    ``actual_positive`` and optional expected warning labels are evaluation
    labels. They are never available to an LLM material assessment or to the
    live Ranking path.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    evaluation_date: date
    baseline_rank: int = Field(ge=1)
    actual_positive: bool
    review_status: LLMMaterialReviewStatus
    run_status: LLMMaterialRunStatus
    cache_hit: bool = False
    latency_ms: int | None = Field(default=None, ge=0)
    material_relevance_score: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    adverse_material_detected: bool = False
    dividend_trap_detected: bool = False
    adverse_material_expected: bool | None = None
    dividend_trap_expected: bool | None = None
    failure_reason: str | None = Field(default=None, min_length=1)


class LLMMaterialEvaluationSummary(StrictBaseModel):
    """Deterministic comparison metrics for a completed Phase 36 sample."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = Field(
        default=LLM_MATERIAL_EVALUATION_SCHEMA_VERSION,
    )
    case_count: int = Field(ge=0)
    evaluation_date_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    cache_hit_count: int = Field(ge=0)
    cache_hit_rate: Decimal = Field(ge=0, le=1)
    failure_rate: Decimal = Field(ge=0, le=1)
    average_latency_ms: Decimal | None = Field(default=None, ge=0)
    baseline_false_positive_count: int = Field(ge=0)
    baseline_false_positive_rate: Decimal = Field(ge=0, le=1)
    retained_count: int = Field(ge=0)
    retained_false_positive_count: int = Field(ge=0)
    retained_false_positive_rate: Decimal = Field(ge=0, le=1)
    false_positive_reduction_count: int = Field(ge=0)
    positive_candidate_coverage: Decimal = Field(ge=0, le=1)
    adverse_precision: Decimal | None = Field(default=None, ge=0, le=1)
    adverse_recall: Decimal | None = Field(default=None, ge=0, le=1)
    dividend_trap_precision: Decimal | None = Field(default=None, ge=0, le=1)
    dividend_trap_recall: Decimal | None = Field(default=None, ge=0, le=1)


class LLMMaterialAdoptionDecision(StrictBaseModel):
    """A conservative Phase 36 decision that cannot enable rank correction."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    status: LLMMaterialAdoptionStatus
    reasons: list[str] = Field(min_length=1)
    allow_rank_correction: Literal[False] = False
    allow_badges: bool = False


def summarize_llm_material_evaluation(
    cases: list[LLMMaterialEvaluationCase],
) -> LLMMaterialEvaluationSummary:
    """Compare a baseline top-candidate set with LLM material review labels.

    A ``caution`` review removes a candidate only within this offline
    evaluation calculation. The function does not return a score, ordering,
    or runtime decision for Ranking.
    """

    completed = [case for case in cases if case.run_status == "completed"]
    failed = [case for case in cases if case.run_status == "failed"]
    skipped = [case for case in cases if case.run_status == "skipped"]
    retained = [case for case in completed if case.review_status == "retain"]
    baseline_false_positives = sum(not case.actual_positive for case in cases)
    retained_false_positives = sum(not case.actual_positive for case in retained)
    positive_count = sum(case.actual_positive for case in cases)
    retained_positive_count = sum(case.actual_positive for case in retained)
    latencies = [case.latency_ms for case in completed if case.latency_ms is not None]
    completed_count = len(completed)
    expected_adverse = [case for case in cases if case.adverse_material_expected is not None]
    expected_dividend = [case for case in cases if case.dividend_trap_expected is not None]
    return LLMMaterialEvaluationSummary(
        case_count=len(cases),
        evaluation_date_count=len({case.evaluation_date for case in cases}),
        completed_count=completed_count,
        failed_count=len(failed),
        skipped_count=len(skipped),
        cache_hit_count=sum(case.cache_hit for case in completed),
        cache_hit_rate=_ratio(
            sum(case.cache_hit for case in completed),
            completed_count,
        ),
        failure_rate=_ratio(len(failed), len(cases)),
        average_latency_ms=(
            _round(sum(latencies, start=0) / len(latencies)) if latencies else None
        ),
        baseline_false_positive_count=baseline_false_positives,
        baseline_false_positive_rate=_ratio(
            baseline_false_positives,
            len(cases),
        ),
        retained_count=len(retained),
        retained_false_positive_count=retained_false_positives,
        retained_false_positive_rate=_ratio(
            retained_false_positives,
            len(retained),
        ),
        false_positive_reduction_count=max(
            0,
            baseline_false_positives - retained_false_positives,
        ),
        positive_candidate_coverage=_ratio(retained_positive_count, positive_count),
        adverse_precision=_precision(
            expected_adverse,
            "adverse_material_detected",
            "adverse_material_expected",
        ),
        adverse_recall=_recall(
            expected_adverse,
            "adverse_material_detected",
            "adverse_material_expected",
        ),
        dividend_trap_precision=_precision(
            expected_dividend,
            "dividend_trap_detected",
            "dividend_trap_expected",
        ),
        dividend_trap_recall=_recall(
            expected_dividend,
            "dividend_trap_detected",
            "dividend_trap_expected",
        ),
    )


def decide_llm_material_adoption(
    summary: LLMMaterialEvaluationSummary,
) -> LLMMaterialAdoptionDecision:
    """Return the bounded Phase 36 adoption decision.

    Even a favorable result can at most recommend display-only badges. Ranking
    correction stays disabled until an explicitly approved later phase.
    """

    if summary.completed_count < 30 or summary.evaluation_date_count < 3:
        return LLMMaterialAdoptionDecision(
            status="evidence_insufficient",
            reasons=[
                "完了ケース30件・評価日3日未満のため、効果を判断できません。",
                "通常Ranking、順位、スコアへの統合は行いません。",
            ],
        )
    if summary.failure_rate > Decimal("0.05"):
        return LLMMaterialAdoptionDecision(
            status="not_adopted",
            reasons=[
                "LLM材料評価の失敗率が5%を超えたため、表示用途にも安定性が不足しています。",
                "通常Ranking、順位、スコアへの統合は行いません。",
            ],
        )
    if (
        summary.false_positive_reduction_count > 0
        and summary.positive_candidate_coverage >= Decimal("0.80")
    ):
        return LLMMaterialAdoptionDecision(
            status="badge_only_candidate",
            allow_badges=True,
            reasons=[
                "false positive削減と候補維持率の評価条件を満たしました。",
                "順位補正ではなく、材料バッジ・警告の限定表示だけを後続検討できます。",
                "通常Ranking、順位、スコアへの統合は行いません。",
            ],
        )
    return LLMMaterialAdoptionDecision(
        status="not_adopted",
        reasons=[
            "false positive削減または候補維持率の条件を満たしませんでした。",
            "通常Ranking、順位、スコアへの統合は行いません。",
        ],
    )


def write_llm_material_evaluation_outputs(
    cases: list[LLMMaterialEvaluationCase],
    output_dir: Path,
) -> dict[str, Path]:
    """Write the five Phase 36 review artifacts from reproducible input cases."""

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_llm_material_evaluation(cases)
    decision = decide_llm_material_adoption(summary)
    paths = {
        "cases": output_dir / "llm_material_eval_cases.csv",
        "summary": output_dir / "llm_material_eval_summary.md",
        "false_positive": output_dir / "llm_false_positive_reduction.md",
        "latency": output_dir / "llm_ranking_latency_report.md",
        "decision": output_dir / "llm_adoption_decision.md",
    }
    with paths["cases"].open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(LLMMaterialEvaluationCase.model_fields),
        )
        writer.writeheader()
        writer.writerows(case.model_dump(mode="json") for case in cases)
    paths["summary"].write_text(
        _summary_markdown(summary),
        encoding="utf-8",
        newline="\n",
    )
    paths["false_positive"].write_text(
        _false_positive_markdown(summary), encoding="utf-8", newline="\n"
    )
    paths["latency"].write_text(
        _latency_markdown(cases, summary),
        encoding="utf-8",
        newline="\n",
    )
    paths["decision"].write_text(
        _decision_markdown(decision),
        encoding="utf-8",
        newline="\n",
    )
    return paths


def _summary_markdown(summary: LLMMaterialEvaluationSummary) -> str:
    return (
        "# LLM材料評価サマリー\n\n"
        "これはPhase 36の評価専用出力です。通常Rankingの順位・スコアは変更していません。\n\n"
        f"- 評価ケース: {summary.case_count}件 / 評価日: {summary.evaluation_date_count}日\n"
        f"- 完了: {summary.completed_count}件 / 失敗: {summary.failed_count}件 / skip: {summary.skipped_count}件\n"
        f"- cache hit: {summary.cache_hit_count}件 ({_percent(summary.cache_hit_rate)})\n"
        f"- failure rate: {_percent(summary.failure_rate)}\n"
        f"- 候補維持率: {_percent(summary.positive_candidate_coverage)}\n"
    )


def _false_positive_markdown(summary: LLMMaterialEvaluationSummary) -> str:
    return (
        "# LLM材料評価 False Positive比較\n\n"
        "cautionは評価用の仮想除外であり、通常Rankingの順位・候補は変更していません。\n\n"
        f"- LLMなし false positive: {summary.baseline_false_positive_count}件 "
        f"({_percent(summary.baseline_false_positive_rate)})\n"
        f"- retain後 false positive: {summary.retained_false_positive_count}件 "
        f"({_percent(summary.retained_false_positive_rate)})\n"
        f"- 削減件数: {summary.false_positive_reduction_count}件\n"
        f"- positive候補維持率: {_percent(summary.positive_candidate_coverage)}\n"
    )


def _latency_markdown(
    cases: list[LLMMaterialEvaluationCase],
    summary: LLMMaterialEvaluationSummary,
) -> str:
    reasons = Counter(
        case.failure_reason or "unspecified" for case in cases if case.run_status == "failed"
    )
    lines = [
        "# LLM材料評価 Latency / Failure / Cache\n",
        "通常Ranking本体の完走とは独立した評価記録です。\n",
        f"- 平均latency: {summary.average_latency_ms if summary.average_latency_ms is not None else 'N/A'} ms",
        f"- failure rate: {_percent(summary.failure_rate)}",
        f"- cache hit rate: {_percent(summary.cache_hit_rate)}",
        "- failure reasons:",
    ]
    lines.extend(f"  - `{reason}`: {count}件" for reason, count in sorted(reasons.items()))
    if not reasons:
        lines.append("  - なし")
    return "\n".join(lines) + "\n"


def _decision_markdown(decision: LLMMaterialAdoptionDecision) -> str:
    lines = [
        "# LLM材料評価 採用判断\n",
        f"- status: `{decision.status}`",
        f"- material_badges_candidate: {'true' if decision.allow_badges else 'false'}",
        "- ranking_rank_correction: false",
        "- ranking_score_correction: false",
        *[f"- {reason}" for reason in decision.reasons],
    ]
    return "\n".join(lines) + "\n"


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator < 1:
        return Decimal("0")
    return _round(Decimal(numerator) / Decimal(denominator))


def _precision(
    cases: list[LLMMaterialEvaluationCase],
    detected: str,
    expected: str,
) -> Decimal | None:
    detected_cases = [case for case in cases if bool(getattr(case, detected))]
    if not detected_cases:
        return None
    return _ratio(
        sum(bool(getattr(case, expected)) for case in detected_cases),
        len(detected_cases),
    )


def _recall(
    cases: list[LLMMaterialEvaluationCase],
    detected: str,
    expected: str,
) -> Decimal | None:
    expected_cases = [case for case in cases if bool(getattr(case, expected))]
    if not expected_cases:
        return None
    return _ratio(
        sum(bool(getattr(case, detected)) for case in expected_cases),
        len(expected_cases),
    )


def _percent(value: Decimal) -> str:
    return f"{(value * Decimal('100')).quantize(Decimal('0.1'))}%"


def _round(value: Decimal | int | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))
