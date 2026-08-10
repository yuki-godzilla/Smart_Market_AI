from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from backend.assistant import (
    AssistantGatewayEvidencePoint,
    AssistantGatewayRadarOverviewInterpretation,
    AssistantGatewayResponse,
)

from .radar_overview_models import (
    RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION,
    RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
    RadarOverviewDeepDiveHint,
    RadarOverviewInterpretationContext,
    RadarOverviewInterpretationPoint,
    RadarOverviewInterpretationResult,
    RadarOverviewSectorNote,
    RadarOverviewThemeNote,
)

_FORBIDDEN_PATTERNS = (
    "買うべき",
    "売るべき",
    "保有推奨",
    "買い推奨",
    "売り推奨",
    "購入してください",
    "売却してください",
    "必ず上がる",
    "利益を保証",
    "strong buy",
    "strong sell",
)
_CHANGE_PATTERNS = (
    "scoreを変更",
    "スコアを変更",
    "予測値を変更",
    "ランキングを変更",
    "順位を変更",
    "候補順を変更",
    "再計算しました",
)
_OVERGENERALIZATION_PATTERNS = (
    "市場全体が上昇",
    "市場全体が下落",
    "市場全体は上昇",
    "市場全体は下落",
    "全面高",
    "全面安",
)
_NUMERIC_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:[%％])?(?![A-Za-z0-9])"
)
_ISO_DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)")
_JAPANESE_DATE_PATTERN = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_JAPANESE_TICKER_PATTERN = re.compile(r"(?<![A-Za-z0-9])(\d{4}\.T)(?![A-Za-z0-9])")
_US_TICKER_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3,6})(?![A-Za-z0-9])")
_UNSAFE_PRESENTATION_PATTERN = re.compile(
    r"https?://|www\.|<[^>]+>|\[[^\]]+\]\([^)]*\)|```",
    re.IGNORECASE,
)
_NON_SYMBOL_TOKENS = {
    "AI",
    "API",
    "ETF",
    "ID",
    "IR",
    "JPY",
    "JSON",
    "LLM",
    "RAG",
    "REIT",
    "RSS",
    "SMAI",
    "TOPIX",
    "USD",
    "UTC",
}


class RadarOverviewInterpretationValidationError(ValueError):
    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


def radar_overview_interpretation_from_gateway_response(
    response: AssistantGatewayResponse,
    *,
    context: RadarOverviewInterpretationContext,
    generated_at: datetime,
    prompt_version: str = RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION,
    schema_version: str = RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION,
) -> RadarOverviewInterpretationResult:
    """Accept the Radar overview only when every field matches supplied context."""

    payload = _validated_payload(
        response,
        context=context,
        schema_version=schema_version,
    )
    _validate_payload_ids(payload, context=context)
    summary = _validated_point(
        payload.summary,
        context=context,
        required_evidence_id="radar_scope",
    )
    movement = _validated_movement(payload, context=context)
    sector_notes = _validated_sector_notes(payload, context=context)
    theme_notes = _validated_theme_notes(payload, context=context)
    deep_dive_hints = _validated_deep_dive_hints(payload, context=context)
    unknowns = _validated_points(payload.unknowns, context=context)
    next_checks = _validated_points(payload.next_checkpoints, context=context)
    referenced_ids = _referenced_ids(
        summary,
        *([movement] if movement is not None else []),
        *[item.reading for item in sector_notes],
        *[item.reading for item in theme_notes],
        *[item.reason for item in deep_dive_hints],
        *unknowns,
        *next_checks,
    )
    if _dedupe([item.section_id for item in response.referenced_sections]) != referenced_ids:
        raise RadarOverviewInterpretationValidationError("unknown_evidence")
    warnings = list(context.warnings)
    if not response.provider or not response.model or not response.profile:
        warnings.append("LLM接続メタ情報の一部が不足しています。")
    return RadarOverviewInterpretationResult(
        radar_context_id=context.radar_context_id,
        status="live",
        summary=summary,
        candidate_set_movement=movement,
        sector_notes=sector_notes,
        theme_notes=theme_notes,
        deep_dive_hints=deep_dive_hints,
        unknowns=unknowns,
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


def _validated_payload(
    response: AssistantGatewayResponse,
    *,
    context: RadarOverviewInterpretationContext,
    schema_version: str,
) -> AssistantGatewayRadarOverviewInterpretation:
    if response.gateway_status != "ok":
        raise RadarOverviewInterpretationValidationError(
            response.fallback_reason or "validation_error"
        )
    payload = response.radar_overview_interpretation
    if payload is None or payload.schema_version != schema_version:
        raise RadarOverviewInterpretationValidationError("malformed_json")
    if (
        payload.radar_context_id != context.radar_context_id
        or payload.context_hash != context.context_hash
    ):
        raise RadarOverviewInterpretationValidationError("wrong_context")
    return payload


def _validate_payload_ids(
    payload: AssistantGatewayRadarOverviewInterpretation,
    *,
    context: RadarOverviewInterpretationContext,
) -> None:
    sector_ids = [item.sector_id for item in payload.sector_notes]
    theme_ids = [item.theme_id for item in payload.theme_notes]
    candidate_ids = [item.candidate_id for item in payload.deep_dive_hints]
    _validate_unique(sector_ids, reason="wrong_sector")
    _validate_unique(theme_ids, reason="wrong_theme")
    _validate_unique(candidate_ids, reason="duplicate_candidate")
    if set(sector_ids) - set(context.allowed_sector_ids):
        raise RadarOverviewInterpretationValidationError("wrong_sector")
    if not _preserves_relative_order(sector_ids, context.allowed_sector_ids):
        raise RadarOverviewInterpretationValidationError("wrong_sector")
    if set(theme_ids) - set(context.allowed_theme_ids):
        raise RadarOverviewInterpretationValidationError("wrong_theme")
    if not _preserves_relative_order(theme_ids, context.allowed_theme_ids):
        raise RadarOverviewInterpretationValidationError("wrong_theme")
    if set(candidate_ids) - set(context.deep_dive_candidate_ids):
        raise RadarOverviewInterpretationValidationError("wrong_candidate")
    if not _preserves_relative_order(candidate_ids, context.deep_dive_candidate_ids):
        raise RadarOverviewInterpretationValidationError("wrong_candidate")


def _validated_movement(
    payload: AssistantGatewayRadarOverviewInterpretation,
    *,
    context: RadarOverviewInterpretationContext,
) -> RadarOverviewInterpretationPoint | None:
    movement = (
        _validated_point(
            payload.candidate_set_movement,
            context=context,
            required_evidence_id="radar_market_breadth",
        )
        if payload.candidate_set_movement is not None
        else None
    )
    if movement is not None and context.market_state in {"missing", "stale"}:
        raise RadarOverviewInterpretationValidationError("policy_violation")
    return movement


def _validated_sector_notes(
    payload: AssistantGatewayRadarOverviewInterpretation,
    *,
    context: RadarOverviewInterpretationContext,
) -> list[RadarOverviewSectorNote]:
    return [
        RadarOverviewSectorNote(
            sector_id=item.sector_id,
            reading=_validated_point(
                item.reading,
                context=context,
                required_evidence_id="radar_sector_comparison",
            ),
        )
        for item in payload.sector_notes
    ]


def _validated_theme_notes(
    payload: AssistantGatewayRadarOverviewInterpretation,
    *,
    context: RadarOverviewInterpretationContext,
) -> list[RadarOverviewThemeNote]:
    theme_notes: list[RadarOverviewThemeNote] = []
    for item in payload.theme_notes:
        related_ids = _dedupe(item.related_candidate_ids)
        allowed_related = context.theme_candidate_ids.get(item.theme_id, [])
        if set(related_ids) - set(allowed_related):
            raise RadarOverviewInterpretationValidationError("wrong_candidate")
        if not _preserves_relative_order(related_ids, allowed_related):
            raise RadarOverviewInterpretationValidationError("wrong_candidate")
        theme_notes.append(
            RadarOverviewThemeNote(
                theme_id=item.theme_id,
                related_candidate_ids=related_ids,
                reading=_validated_point(
                    item.reading,
                    context=context,
                    required_evidence_id=item.theme_id,
                ),
            )
        )
    return theme_notes


def _validated_deep_dive_hints(
    payload: AssistantGatewayRadarOverviewInterpretation,
    *,
    context: RadarOverviewInterpretationContext,
) -> list[RadarOverviewDeepDiveHint]:
    deep_dive_hints: list[RadarOverviewDeepDiveHint] = []
    for deep_item in payload.deep_dive_hints:
        if context.candidate_provenance.get(deep_item.candidate_id) == "macro_proxy":
            raise RadarOverviewInterpretationValidationError("wrong_candidate")
        deep_dive_hints.append(
            RadarOverviewDeepDiveHint(
                candidate_id=deep_item.candidate_id,
                reason=_validated_point(
                    deep_item.reason,
                    context=context,
                    required_evidence_id=deep_item.candidate_id,
                ),
            )
        )
    return deep_dive_hints


def _validated_points(
    points: list[AssistantGatewayEvidencePoint],
    *,
    context: RadarOverviewInterpretationContext,
) -> list[RadarOverviewInterpretationPoint]:
    return [_validated_point(item, context=context) for item in points]


def _validated_point(
    point: AssistantGatewayEvidencePoint,
    *,
    context: RadarOverviewInterpretationContext,
    required_evidence_id: str | None = None,
) -> RadarOverviewInterpretationPoint:
    evidence_ids = _dedupe(point.cited_evidence_ids)
    if not evidence_ids or set(evidence_ids) - set(context.allowed_evidence_ids):
        raise RadarOverviewInterpretationValidationError("unknown_evidence")
    if required_evidence_id is not None and required_evidence_id not in evidence_ids:
        raise RadarOverviewInterpretationValidationError("unknown_evidence")
    _validate_text(point.text, context=context)
    return RadarOverviewInterpretationPoint(
        summary=" ".join(point.text.split()),
        evidence_ids=evidence_ids,
    )


def _validate_text(value: str, *, context: RadarOverviewInterpretationContext) -> None:
    lowered = value.lower()
    forbidden = (*_FORBIDDEN_PATTERNS, *_CHANGE_PATTERNS, *_OVERGENERALIZATION_PATTERNS)
    if any(item.lower() in lowered for item in forbidden) or _UNSAFE_PRESENTATION_PATTERN.search(
        value
    ):
        raise RadarOverviewInterpretationValidationError("policy_violation")
    observed_symbols = {
        *{item.upper() for item in _JAPANESE_TICKER_PATTERN.findall(value)},
        *{
            item.upper()
            for item in _US_TICKER_PATTERN.findall(value)
            if item.upper() not in _NON_SYMBOL_TOKENS
        },
    }
    if observed_symbols - {item.upper() for item in context.allowed_symbols}:
        raise RadarOverviewInterpretationValidationError("wrong_candidate")
    observed_dates = {
        *_canonical_dates(value, _ISO_DATE_PATTERN),
        *_canonical_dates(value, _JAPANESE_DATE_PATTERN),
    }
    if observed_dates - set(context.allowed_dates):
        raise RadarOverviewInterpretationValidationError("unsupported_date")
    observed_numbers = {_normalize_number(item) for item in _NUMERIC_PATTERN.findall(value)}
    if observed_numbers - set(context.allowed_numeric_values):
        raise RadarOverviewInterpretationValidationError("unsupported_number")


def _validate_unique(values: list[str], *, reason: str) -> None:
    if len(values) != len(set(values)):
        raise RadarOverviewInterpretationValidationError(reason)


def _preserves_relative_order(values: list[str], allowed_values: list[str]) -> bool:
    selected = set(values)
    return values == [item for item in allowed_values if item in selected]


def _referenced_ids(*points: RadarOverviewInterpretationPoint) -> list[str]:
    return _dedupe([item for point in points for item in point.evidence_ids])


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
