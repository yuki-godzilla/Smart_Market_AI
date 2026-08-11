from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from backend.assistant.gateway_contracts import AssistantGatewayResponse
from backend.assistant.news_interpretation_contracts import (
    AssistantGatewayNewsEvidencePoint,
    AssistantGatewayNewsInterpretation,
)

from .news_interpretation_models import (
    NEWS_INTERPRETATION_PROMPT_VERSION,
    NEWS_INTERPRETATION_SCHEMA_VERSION,
    NewsHandoffHint,
    NewsInterpretationContext,
    NewsInterpretationPoint,
    NewsInterpretationResult,
    NewsMaterialNote,
    NewsSectorNote,
)

_FORBIDDEN = (
    "買うべき",
    "売るべき",
    "買い推奨",
    "売り推奨",
    "必ず上がる",
    "必ず下がる",
    "株価が上昇する",
    "株価が下落する",
    "利益を保証",
    "strong buy",
    "strong sell",
    "スコアを変更",
    "順位を変更",
    "forecastを変更",
    "市場全体が上昇",
    "市場全体が下落",
)
_UNSAFE = re.compile(r"https?://|www\.|<[^>]+>|\[[^\]]+\]\([^)]*\)|```", re.IGNORECASE)
_NUMBER = re.compile(
    r"(?<![A-Za-z0-9])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:[%％])?(?![A-Za-z0-9])"
)
_ISO_DATE = re.compile(r"(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)")
_JA_DATE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_JP_TICKER = re.compile(r"(?<![A-Za-z0-9])(\d{4}\.T)(?![A-Za-z0-9])")
_US_TICKER = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3,6})(?![A-Za-z0-9])")
_NON_SYMBOLS = {"AI", "API", "ETF", "ID", "IR", "JSON", "LLM", "RAG", "REIT", "RSS", "SMAI", "UTC"}


class NewsInterpretationValidationError(ValueError):
    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


def news_interpretation_from_gateway_response(
    response: AssistantGatewayResponse,
    *,
    context: NewsInterpretationContext,
    generated_at: datetime,
    prompt_version: str = NEWS_INTERPRETATION_PROMPT_VERSION,
    schema_version: str = NEWS_INTERPRETATION_SCHEMA_VERSION,
) -> NewsInterpretationResult:
    if response.gateway_status != "ok":
        raise NewsInterpretationValidationError(response.fallback_reason or "validation_error")
    payload = response.news_interpretation
    if payload is None or payload.schema_version != schema_version:
        raise NewsInterpretationValidationError("malformed_json")
    if (
        payload.news_context_id != context.news_context_id
        or payload.context_hash != context.context_hash
    ):
        raise NewsInterpretationValidationError("wrong_context")
    _validate_ids(payload, context=context)
    summary = _point(payload.summary, context=context, required="news_scope")
    materials = _material_notes(payload, context=context)
    sector_notes = [
        NewsSectorNote(
            sector_id=item.sector_id,
            reading=_point(item.reading, context=context, required="news_sector_relations"),
        )
        for item in payload.sector_notes
    ]
    handoffs = [
        NewsHandoffHint(
            candidate_id=item.candidate_id,
            reason=_point(item.reason, context=context, required="news_cockpit_handoffs"),
        )
        for item in payload.handoff_hints
    ]
    noise = [
        _point(item, context=context, required="news_source_quality")
        for item in payload.noise_notes
    ]
    unknowns = [_point(item, context=context) for item in payload.unknowns]
    next_checks = [_point(item, context=context) for item in payload.next_checkpoints]
    return _result_from_points(
        response,
        context=context,
        payload=payload,
        generated_at=generated_at,
        prompt_version=prompt_version,
        schema_version=schema_version,
        summary=summary,
        materials=materials,
        sector_notes=sector_notes,
        handoffs=handoffs,
        noise=noise,
        unknowns=unknowns,
        next_checks=next_checks,
    )


def _material_notes(
    payload: AssistantGatewayNewsInterpretation, *, context: NewsInterpretationContext
) -> list[NewsMaterialNote]:
    result: list[NewsMaterialNote] = []
    for item in payload.material_notes:
        sectors = _dedupe(item.related_sector_ids)
        if set(sectors) - set(context.material_sector_ids.get(item.material_id, [])):
            raise NewsInterpretationValidationError("wrong_sector")
        result.append(
            NewsMaterialNote(
                material_id=item.material_id,
                business_impact_direction=item.business_impact_direction,
                impact_horizon=item.impact_horizon,
                related_sector_ids=sectors,
                reading=_point(item.reading, context=context, required=item.material_id),
                uncertainty=(
                    _point(item.uncertainty, context=context, required=item.material_id)
                    if item.uncertainty
                    else None
                ),
            )
        )
    return result


def _result_from_points(
    response: AssistantGatewayResponse,
    *,
    context: NewsInterpretationContext,
    payload: AssistantGatewayNewsInterpretation,
    generated_at: datetime,
    prompt_version: str,
    schema_version: str,
    summary: NewsInterpretationPoint,
    materials: list[NewsMaterialNote],
    sector_notes: list[NewsSectorNote],
    handoffs: list[NewsHandoffHint],
    noise: list[NewsInterpretationPoint],
    unknowns: list[NewsInterpretationPoint],
    next_checks: list[NewsInterpretationPoint],
) -> NewsInterpretationResult:
    points = [
        summary,
        *[x.reading for x in materials],
        *[x.uncertainty for x in materials if x.uncertainty],
        *[x.reading for x in sector_notes],
        *noise,
        *[x.reason for x in handoffs],
        *unknowns,
        *next_checks,
    ]
    referenced = _dedupe([evidence for point in points for evidence in point.evidence_ids])
    response_refs = _dedupe([item.section_id for item in response.referenced_sections])
    if response_refs != referenced:
        raise NewsInterpretationValidationError("unknown_evidence")
    return NewsInterpretationResult(
        news_context_id=context.news_context_id,
        status="live",
        summary=summary,
        material_notes=materials,
        sector_notes=sector_notes,
        noise_notes=noise,
        handoff_hints=handoffs,
        unknowns=unknowns,
        next_checks=next_checks,
        referenced_evidence_ids=referenced,
        warnings=list(context.warnings),
        provider=response.provider,
        model=response.model,
        gateway_profile=response.profile,
        generated_at=_ensure_utc(generated_at),
        prompt_version=prompt_version,
        schema_version=schema_version,
        context_hash=context.context_hash,
        is_fallback=False,
    )


def _validate_ids(
    payload: AssistantGatewayNewsInterpretation, *, context: NewsInterpretationContext
) -> None:
    material_ids = [item.material_id for item in payload.material_notes]
    sector_ids = [item.sector_id for item in payload.sector_notes]
    candidate_ids = [item.candidate_id for item in payload.handoff_hints]
    for values, allowed, reason in (
        (material_ids, context.allowed_material_ids, "wrong_material"),
        (sector_ids, context.allowed_sector_ids, "wrong_sector"),
        (candidate_ids, context.allowed_handoff_candidate_ids, "wrong_candidate"),
    ):
        if (
            len(values) != len(set(values))
            or set(values) - set(allowed)
            or not _relative_order(values, allowed)
        ):
            raise NewsInterpretationValidationError(reason)
    if candidate_ids != context.allowed_handoff_candidate_ids:
        raise NewsInterpretationValidationError("wrong_candidate")


def _point(
    point: AssistantGatewayNewsEvidencePoint,
    *,
    context: NewsInterpretationContext,
    required: str | None = None,
) -> NewsInterpretationPoint:
    evidence_ids = _dedupe(point.cited_evidence_ids)
    if (
        not evidence_ids
        or set(evidence_ids) - set(context.allowed_evidence_ids)
        or (required and required not in evidence_ids)
    ):
        raise NewsInterpretationValidationError("unknown_evidence")
    lowered = point.text.lower()
    if any(value.lower() in lowered for value in _FORBIDDEN) or _UNSAFE.search(point.text):
        raise NewsInterpretationValidationError("policy_violation")
    _validate_grounding(point.text, context=context)
    return NewsInterpretationPoint(summary=" ".join(point.text.split()), evidence_ids=evidence_ids)


def _validate_grounding(value: str, *, context: NewsInterpretationContext) -> None:
    symbols = {item.upper() for item in _JP_TICKER.findall(value)} | {
        item.upper() for item in _US_TICKER.findall(value) if item.upper() not in _NON_SYMBOLS
    }
    if symbols - {item.upper() for item in context.allowed_symbols}:
        raise NewsInterpretationValidationError("wrong_candidate")
    dates = _canonical_dates(value, _ISO_DATE) | _canonical_dates(value, _JA_DATE)
    if dates - set(context.allowed_dates):
        raise NewsInterpretationValidationError("unsupported_date")
    numbers = {_normalize_number(item) for item in _NUMBER.findall(value)}
    if numbers - set(context.allowed_numeric_values):
        raise NewsInterpretationValidationError("unsupported_number")


def _canonical_dates(value: str, pattern: re.Pattern[str]) -> set[str]:
    result: set[str] = set()
    for year, month, day in pattern.findall(value):
        try:
            result.add(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            continue
    return result


def _normalize_number(value: str) -> str:
    cleaned = value.replace(",", "").replace("％", "%").rstrip("%")
    try:
        return format(Decimal(cleaned).normalize(), "f")
    except InvalidOperation:
        return cleaned


def _relative_order(values: list[str], allowed: list[str]) -> bool:
    selected = set(values)
    return values == [item for item in allowed if item in selected]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
