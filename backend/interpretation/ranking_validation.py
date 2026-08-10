from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from backend.assistant import AssistantGatewayEvidencePoint, AssistantGatewayResponse

from .ranking_models import (
    RANKING_INTERPRETATION_PROMPT_VERSION,
    RANKING_INTERPRETATION_SCHEMA_VERSION,
    RankingCandidateInterpretationNote,
    RankingInterpretationContext,
    RankingInterpretationPoint,
    RankingInterpretationResult,
)

_FORBIDDEN_PATTERNS = (
    "買うべき",
    "売るべき",
    "保有推奨",
    "買い推奨",
    "売り推奨",
    "購入してください",
    "売却してください",
    "strong buy",
    "strong sell",
)
_CHANGE_PATTERNS = (
    "scoreを変更",
    "スコアを変更",
    "予測値を変更",
    "ランキングを変更",
    "順位を変更",
    "再計算しました",
)
_NUMERIC_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:[%％])?(?![A-Za-z0-9])"
)
_ISO_DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)")
_JAPANESE_DATE_PATTERN = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_JAPANESE_TICKER_PATTERN = re.compile(r"(?<![A-Za-z0-9])(\d{4}\.T)(?![A-Za-z0-9])")
_US_TICKER_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3,6})(?![A-Za-z0-9])")
_NON_SYMBOL_TOKENS = {
    "AI",
    "API",
    "BPS",
    "DCF",
    "EBITDA",
    "EPS",
    "ETF",
    "GICS",
    "ID",
    "IR",
    "JPY",
    "JSON",
    "LLM",
    "MACD",
    "NISA",
    "PBR",
    "PER",
    "RAG",
    "REIT",
    "ROE",
    "RSI",
    "SMAI",
    "TOPIX",
    "USD",
    "UTC",
}


class RankingInterpretationValidationError(ValueError):
    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


def ranking_interpretation_from_gateway_response(
    response: AssistantGatewayResponse,
    *,
    context: RankingInterpretationContext,
    generated_at: datetime,
    prompt_version: str = RANKING_INTERPRETATION_PROMPT_VERSION,
    schema_version: str = RANKING_INTERPRETATION_SCHEMA_VERSION,
) -> RankingInterpretationResult:
    """Accept the payload only when every statement is tied to supplied evidence."""

    if response.gateway_status != "ok":
        raise RankingInterpretationValidationError(response.fallback_reason or "validation_error")
    payload = response.ranking_interpretation
    if payload is None or payload.schema_version != schema_version:
        raise RankingInterpretationValidationError("malformed_json")
    if payload.ranking_context_id != context.ranking_context_id:
        raise RankingInterpretationValidationError("wrong_context")

    candidate_ids = [note.candidate_id for note in payload.candidate_notes]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise RankingInterpretationValidationError("duplicate_candidate")
    if set(candidate_ids) - set(context.candidate_ids):
        raise RankingInterpretationValidationError("wrong_candidate")

    summary = _validated_point(payload.summary, context=context)
    strengths = _validated_points(payload.common_strengths, context=context)
    cautions = _validated_points(payload.common_cautions, context=context)
    metric_notes = _validated_points(payload.metric_notes, context=context)
    sector_notes = _validated_points(payload.sector_notes, context=context)
    next_checks = _validated_points(payload.next_checkpoints, context=context)
    notes_by_id = {
        note.candidate_id: RankingCandidateInterpretationNote(
            candidate_id=note.candidate_id,
            reading=_validated_point(note.reading, context=context),
            caution=(
                _validated_point(note.caution, context=context)
                if note.caution is not None
                else None
            ),
            next_check=_validated_point(note.next_check, context=context),
        )
        for note in payload.candidate_notes
    }
    candidate_notes = [notes_by_id[item] for item in context.candidate_ids if item in notes_by_id]
    referenced_ids = _referenced_ids(
        summary,
        *strengths,
        *cautions,
        *metric_notes,
        *sector_notes,
        *next_checks,
        *(point for note in candidate_notes for point in _candidate_points(note)),
    )
    response_ids = _dedupe([item.section_id for item in response.referenced_sections])
    if response_ids != referenced_ids:
        raise RankingInterpretationValidationError("unknown_evidence")

    warnings = _response_warnings(response, context=context)
    return RankingInterpretationResult(
        ranking_context_id=context.ranking_context_id,
        status="live",
        overall_reading=summary.summary,
        common_strengths=strengths,
        common_cautions=cautions,
        metric_notes=metric_notes,
        sector_notes=sector_notes,
        candidate_notes=candidate_notes,
        next_checks=next_checks,
        referenced_evidence_ids=referenced_ids,
        warnings=_dedupe(warnings),
        provider=response.provider,
        model=response.model,
        gateway_profile=response.profile,
        generated_at=_ensure_utc(generated_at),
        prompt_version=prompt_version,
        schema_version=schema_version,
        context_hash=context.context_hash,
        is_fallback=False,
    )


def _validated_points(
    points: list[AssistantGatewayEvidencePoint], *, context: RankingInterpretationContext
) -> list[RankingInterpretationPoint]:
    return [_validated_point(point, context=context) for point in points]


def _response_warnings(
    response: AssistantGatewayResponse, *, context: RankingInterpretationContext
) -> list[str]:
    warnings = list(context.warnings)
    if not response.provider or not response.model or not response.profile:
        warnings.append("LLM接続メタ情報の一部が不足しています。")
    return warnings


def _validated_point(
    point: AssistantGatewayEvidencePoint, *, context: RankingInterpretationContext
) -> RankingInterpretationPoint:
    evidence_ids = _dedupe(point.cited_evidence_ids)
    if not evidence_ids or set(evidence_ids) - set(context.allowed_evidence_ids):
        raise RankingInterpretationValidationError("unknown_evidence")
    _validate_text(point.text, context=context)
    return RankingInterpretationPoint(
        summary=" ".join(point.text.split()), evidence_ids=evidence_ids
    )


def _validate_text(value: str, *, context: RankingInterpretationContext) -> None:
    lowered = value.lower()
    if any(item.lower() in lowered for item in (*_FORBIDDEN_PATTERNS, *_CHANGE_PATTERNS)):
        raise RankingInterpretationValidationError("policy_violation")
    observed_symbols = {
        *{item.upper() for item in _JAPANESE_TICKER_PATTERN.findall(value)},
        *{
            item.upper()
            for item in _US_TICKER_PATTERN.findall(value)
            if item.upper() not in _NON_SYMBOL_TOKENS
        },
    }
    allowed_symbols = {item.upper() for item in context.allowed_symbols}
    if observed_symbols - allowed_symbols:
        raise RankingInterpretationValidationError("wrong_candidate")
    observed_dates = {
        *_canonical_dates(value, _ISO_DATE_PATTERN),
        *_canonical_dates(value, _JAPANESE_DATE_PATTERN),
    }
    if observed_dates - set(context.allowed_dates):
        raise RankingInterpretationValidationError("unsupported_date")
    observed_numbers = {_normalize_number(item) for item in _NUMERIC_PATTERN.findall(value)}
    if observed_numbers - set(context.allowed_numeric_values):
        raise RankingInterpretationValidationError("unsupported_number")


def _candidate_points(
    note: RankingCandidateInterpretationNote,
) -> list[RankingInterpretationPoint]:
    return [note.reading, *([note.caution] if note.caution is not None else []), note.next_check]


def _referenced_ids(*points: RankingInterpretationPoint) -> list[str]:
    return _dedupe([evidence_id for point in points for evidence_id in point.evidence_ids])


def _canonical_dates(value: str, pattern: re.Pattern[str]) -> set[str]:
    result: set[str] = set()
    for year_text, month_text, day_text in pattern.findall(value):
        try:
            result.add(date(int(year_text), int(month_text), int(day_text)).isoformat())
        except ValueError:
            continue
    return result


def _normalize_number(value: str) -> str:
    cleaned = value.replace(",", "").replace("％", "%").rstrip("%")
    try:
        return format(Decimal(cleaned).normalize(), "f")
    except InvalidOperation:
        return cleaned


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
