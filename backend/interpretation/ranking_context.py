from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from backend.assistant import AssistantContextBundle, AssistantContextSection

from .ranking_models import (
    RankingCandidateEvidence,
    RankingInterpretationContext,
    RankingInterpretationInput,
    RankingSectorEvidence,
)

_NUMERIC_PATTERN = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:[.,]\d+)*(?:%|点|位|件|日)?")
_ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def build_ranking_interpretation_context(
    value: RankingInterpretationInput,
    *,
    now: datetime | None = None,
    max_text_chars: int = 240,
) -> RankingInterpretationContext:
    """Build a compact stable context from the already-frozen Ranking display."""

    context_hash = ranking_interpretation_context_hash(value)
    context_id = f"ranking:{context_hash[:24]}"
    sections = [
        _scope_section(value, context_id=context_id, max_chars=max_text_chars),
        _metrics_section(value, max_chars=max_text_chars),
        _sectors_section(value.sector_groups, max_chars=max_text_chars),
        *[_candidate_section(item, max_chars=max_text_chars) for item in value.candidates],
    ]
    bundle = AssistantContextBundle(
        bundle_id=f"ranking-interpretation-{context_hash[:24]}",
        title="Ranking Interpretation",
        source="streamlit_context",
        created_at=_ensure_utc(now or datetime.now(UTC)),
        active_context_id="ranking_interpretation",
        sections=sections,
        tags=["ranking", "interpretation", value.ranking_policy],
        privacy_notes=[
            "Only already-displayed Ranking values and bounded local metadata are included.",
            "Provider raw fields, external source bodies, user notes, tags, and debug data are excluded.",
            "The supplied order is frozen and must not be recalculated or changed.",
        ],
    )
    return RankingInterpretationContext(
        ranking_context_id=context_id,
        as_of=value.as_of,
        bundle=bundle,
        context_hash=context_hash,
        candidate_ids=[item.candidate_id for item in value.candidates],
        allowed_evidence_ids=[section.section_id for section in sections],
        allowed_symbols=[item.symbol for item in value.candidates],
        allowed_numeric_values=_allowed_numeric_values(bundle),
        allowed_dates=_allowed_dates(bundle, as_of=value.as_of.isoformat()),
        warnings=_dedupe(value.warnings),
    )


def ranking_interpretation_context_hash(value: RankingInterpretationInput) -> str:
    payload = value.model_dump(mode="json")
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _scope_section(
    value: RankingInterpretationInput,
    *,
    context_id: str,
    max_chars: int,
) -> AssistantContextSection:
    summary = {
        "ranking_context_id": context_id,
        "as_of": value.as_of.isoformat(),
        "ranking_policy": _clean(value.ranking_policy, max_chars),
        "weight_preset": _clean(value.weight_preset, max_chars),
        "region": _clean(value.region, max_chars),
        "product_type": _clean(value.product_type, max_chars),
        "candidate_count": str(value.candidate_count),
        "interpreted_candidate_count": str(len(value.candidates)),
    }
    return _section(
        section_id="ranking_scope",
        title="ランキング条件",
        source_kind="ranking_scope",
        summary=summary,
        notes=[
            "This is an already-frozen comparison result, not a request to create a new ranking.",
            "Every explanation must preserve the supplied rank order and score values.",
        ],
    )


def _metrics_section(
    value: RankingInterpretationInput,
    *,
    max_chars: int,
) -> AssistantContextSection:
    rows = [
        {
            "candidate_id": item.candidate_id,
            "rank": str(item.rank),
            "metric_id": _clean(item.primary_metric_id, max_chars),
            "metric_label": _clean(item.primary_metric_label, max_chars),
            "metric_value": _clean(item.primary_metric_value, max_chars),
        }
        for item in value.candidates
    ]
    return _section(
        section_id="ranking_metrics",
        title="上位候補で効いている指標",
        source_kind="ranking_metrics",
        summary={"candidate_count": str(len(rows))},
        rows=rows,
        notes=["Metric values are copied from the current display and must not be recalculated."],
    )


def _sectors_section(
    values: list[RankingSectorEvidence],
    *,
    max_chars: int,
) -> AssistantContextSection:
    rows = [
        {
            "sector_id": item.sector_id,
            "sector_label": _clean(item.sector_label, max_chars),
            "candidate_count": str(item.candidate_count),
            "best_rank": str(item.best_rank),
            "representative_candidate_id": item.representative_candidate_id,
            "primary_metric_average": item.primary_metric_average or "未計算",
            "comparison_state": item.comparison_state,
        }
        for item in values
    ]
    return _section(
        section_id="ranking_sectors",
        title="今回の候補集合内のセクター比較",
        source_kind="ranking_sector_comparison",
        summary={"sector_group_count": str(len(rows))},
        rows=rows,
        notes=[
            "This comparison applies only to the current result cohort, not the whole market.",
            "A sector with one candidate is comparison_state=insufficient.",
        ],
    )


def _candidate_section(
    item: RankingCandidateEvidence,
    *,
    max_chars: int,
) -> AssistantContextSection:
    summary = {
        "candidate_id": item.candidate_id,
        "rank": str(item.rank),
        "symbol": item.symbol,
        "company_name": _clean(item.company_name or "名称未登録", max_chars),
        "primary_metric_label": _clean(item.primary_metric_label, max_chars),
        "primary_metric_value": _clean(item.primary_metric_value, max_chars),
        "total_score": _clean(item.total_score, max_chars),
        "screening_score": _clean(item.screening_score, max_chars),
        "upside_signal": _clean(item.upside_signal, max_chars),
        "upward_signal": _clean(item.upward_signal, max_chars),
        "downside_warning": _clean(item.downside_warning, max_chars),
        "risk_score": _clean(item.risk_score, max_chars),
        "data_quality": _clean(item.data_quality, max_chars),
        "database_fit": _clean(item.database_fit, max_chars),
        "metadata_confidence": _clean(item.metadata_confidence, max_chars),
        "forecast_summary": _clean(item.forecast_summary, max_chars),
        "reason": _clean(item.reason, max_chars),
        "caution": _clean(item.caution, max_chars),
        "research_status": _clean(item.research_status, max_chars),
    }
    return _section(
        section_id=item.candidate_id,
        title=f"{item.rank}位 {item.symbol}",
        source_kind="ranking_candidate",
        summary={key: value for key, value in summary.items() if value},
        symbol=item.symbol,
        notes=["Explain this supplied candidate without changing its rank or score."],
    )


def _section(
    *,
    section_id: str,
    title: str,
    source_kind: str,
    summary: dict[str, str],
    rows: list[dict[str, str]] | None = None,
    notes: list[str] | None = None,
    symbol: str | None = None,
) -> AssistantContextSection:
    return AssistantContextSection(
        section_id=section_id,
        title=title,
        source_kind=source_kind,
        symbol=symbol,
        summary=summary,
        rows=rows or [],
        notes=notes or [],
        included_fields=sorted(summary),
    )


def _allowed_numeric_values(bundle: AssistantContextBundle) -> list[str]:
    values: set[str] = set()
    for text in _bundle_values(bundle):
        for match in _NUMERIC_PATTERN.findall(text):
            normalized = _normalize_number(match)
            if normalized:
                values.add(normalized)
    return sorted(values)


def _allowed_dates(bundle: AssistantContextBundle, *, as_of: str) -> list[str]:
    values = {as_of}
    for text in _bundle_values(bundle):
        values.update(_ISO_DATE_PATTERN.findall(text))
    return sorted(values)


def _bundle_values(bundle: AssistantContextBundle) -> list[str]:
    values: list[str] = []
    for section in bundle.sections:
        values.extend(section.summary.values())
        values.extend(value for row in section.rows for value in row.values())
    return values


def _normalize_number(value: str) -> str:
    cleaned = value.replace(",", "").rstrip("%点位件日").lstrip("+")
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return ""
    return format(number.normalize(), "f")


def _clean(value: object, max_chars: int) -> str:
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
