"""Opt-in, evidence-bound LLM interpretation for Investment Radar candidates."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from typing import Literal, Mapping

import httpx
from pydantic import Field, ValidationError

from backend.assistant.gateway_client import (
    AssistantGatewayClient,
    AssistantGatewayError,
    AssistantGatewayTimeoutError,
    HttpAssistantGatewayClient,
)
from backend.assistant.gateway_contracts import (
    ASSISTANT_GATEWAY_RADAR_INTERPRETATION_SCHEMA_VERSION,
    AssistantContextBundle,
    AssistantContextSection,
    AssistantGatewayEvidencePoint,
    AssistantGatewayResponse,
    build_assistant_gateway_request,
)
from backend.core.config import RadarInterpretationConfig, Settings, get_settings
from backend.core.data_contracts import StrictBaseModel
from backend.news.contracts import RadarCandidate, RadarEvidenceBundle

RADAR_INTERPRETATION_SCHEMA_VERSION = ASSISTANT_GATEWAY_RADAR_INTERPRETATION_SCHEMA_VERSION
RADAR_INTERPRETATION_PROMPT_VERSION = "radar_interpretation_mvp.v1"

RadarInterpretationStatus = Literal["live", "fallback", "disabled", "validation_error"]
RadarInterpretationFallbackReason = Literal[
    "disabled",
    "gateway_unavailable",
    "gateway_timeout",
    "gateway_http_error",
    "malformed_json",
    "validation_error",
    "unknown_evidence",
    "wrong_symbol",
    "unsupported_number",
    "unsupported_date",
    "policy_violation",
    "provider_error",
]

_MAX_NEWS_EVIDENCE = 4
_MAX_CITATIONS = 5
_MAX_TEXT_CHARS = 320
_MAX_READING_CHARS = 700
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
_SCORE_OR_RANKING_CHANGE_PATTERNS = (
    "scoreを変更",
    "スコアを変更",
    "予測値を変更",
    "ランキングを変更",
    "順位を変更",
    "再計算しました",
)
_NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:[%％])?(?![A-Za-z0-9])"
)
_ISO_DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)")
_JAPANESE_DATE_PATTERN = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
_JAPANESE_TICKER_PATTERN = re.compile(r"(?<![A-Za-z0-9])(\d{4}\.T)(?![A-Za-z0-9])")
_US_TICKER_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3,6})(?![A-Za-z0-9])")
_NON_SYMBOL_UPPERCASE_TOKENS = {
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
    "USD",
    "UTC",
}


class RadarInterpretationPoint(StrictBaseModel):
    """One bounded explanation point tied only to supplied evidence IDs."""

    summary: str = Field(min_length=1, max_length=_MAX_TEXT_CHARS)
    evidence_ids: list[str] = Field(default_factory=list)


class RadarInterpretationContext(StrictBaseModel):
    """Gateway-safe context that contains candidate metadata and cited evidence only."""

    candidate_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    as_of: date
    bundle: AssistantContextBundle
    context_hash: str = Field(min_length=1)
    allowed_evidence_ids: list[str] = Field(default_factory=list)
    allowed_symbols: list[str] = Field(default_factory=list)
    allowed_numeric_values: list[str] = Field(default_factory=list)
    allowed_dates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RadarInterpretationResult(StrictBaseModel):
    """Validated optional explanation; it never changes deterministic Radar values."""

    candidate_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    status: RadarInterpretationStatus
    overall_reading: str = Field(min_length=1, max_length=_MAX_READING_CHARS)
    material_points: list[RadarInterpretationPoint] = Field(default_factory=list)
    caution_points: list[RadarInterpretationPoint] = Field(default_factory=list)
    unknowns: list[RadarInterpretationPoint] = Field(default_factory=list)
    next_checks: list[RadarInterpretationPoint] = Field(default_factory=list)
    referenced_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    gateway_profile: str | None = Field(default=None, min_length=1)
    generated_at: datetime
    prompt_version: str = Field(default=RADAR_INTERPRETATION_PROMPT_VERSION, min_length=1)
    schema_version: str = Field(default=RADAR_INTERPRETATION_SCHEMA_VERSION, min_length=1)
    context_hash: str | None = Field(default=None, min_length=1)
    fallback_reason: RadarInterpretationFallbackReason | None = None
    is_fallback: bool = False


class RadarInterpretationValidationError(ValueError):
    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


class RadarInterpretationGatewayAdapter:
    """Use the generic Gateway endpoint without adding a provider-specific API."""

    def __init__(
        self,
        client: AssistantGatewayClient,
        *,
        execution_mode: str = "auto",
        environment_profile: str = "notebook",
        preferred_profile: str | None = None,
    ) -> None:
        self.client = client
        self.execution_mode = execution_mode
        self.environment_profile = environment_profile
        self.preferred_profile = preferred_profile

    def generate(self, context: RadarInterpretationContext) -> AssistantGatewayResponse:
        request = build_assistant_gateway_request(
            question=(
                "intent: radar_interpretation\n"
                "投資レーダーの一候補について、指定された根拠IDだけを使い、"
                "材料・注意点・未確認点・次の確認事項を整理してください。"
                "売買推奨、ランキング、Investment Score、Forecast数値の変更や再計算はしないでください。"
                "Radar専用JSONの各項目へ、参照した根拠IDを正確に付けてください。"
            ),
            context=context.bundle,
            task="explain",
            language="ja",
            active_context_id="radar_interpretation",
            referenced_context_ids=context.allowed_evidence_ids[:8],
            response_schema=RADAR_INTERPRETATION_SCHEMA_VERSION,
            task_type="news_materials",
            execution_mode=self.execution_mode,  # type: ignore[arg-type]
            environment_profile=self.environment_profile,  # type: ignore[arg-type]
            preferred_profile=self.preferred_profile,  # type: ignore[arg-type]
        )
        return _coerce_gateway_response(self.client.answer(request))


class RadarInterpretationService:
    """Run an optional Radar interpretation and always provide a safe fallback."""

    def __init__(
        self,
        gateway_adapter: RadarInterpretationGatewayAdapter | None,
        *,
        config: RadarInterpretationConfig,
    ) -> None:
        self.gateway_adapter = gateway_adapter
        self.config = config

    def interpret(
        self,
        context: RadarInterpretationContext,
        *,
        now: datetime | None = None,
    ) -> RadarInterpretationResult:
        generated_at = _ensure_utc(now or datetime.now(UTC))
        if not self.config.enabled or self.config.execution_mode == "off":
            return build_deterministic_radar_interpretation(
                context,
                status="disabled",
                fallback_reason="disabled",
                generated_at=generated_at,
                prompt_version=self.config.prompt_version,
                schema_version=self.config.schema_version,
            )
        if self.gateway_adapter is None:
            return build_deterministic_radar_interpretation(
                context,
                status="fallback",
                fallback_reason="gateway_unavailable",
                generated_at=generated_at,
                prompt_version=self.config.prompt_version,
                schema_version=self.config.schema_version,
            )
        try:
            response = self.gateway_adapter.generate(context)
            return radar_interpretation_from_gateway_response(
                response,
                context=context,
                generated_at=generated_at,
                prompt_version=self.config.prompt_version,
                schema_version=self.config.schema_version,
            )
        except (
            AssistantGatewayError,
            AssistantGatewayTimeoutError,
            RadarInterpretationValidationError,
            TimeoutError,
            ValueError,
        ) as exc:
            reason = _fallback_reason(exc)
            return build_deterministic_radar_interpretation(
                context,
                status=(
                    "validation_error"
                    if reason
                    in {
                        "validation_error",
                        "policy_violation",
                        "unknown_evidence",
                        "wrong_symbol",
                        "unsupported_number",
                        "unsupported_date",
                    }
                    else "fallback"
                ),
                fallback_reason=reason,
                generated_at=generated_at,
                prompt_version=self.config.prompt_version,
                schema_version=self.config.schema_version,
            )


def build_radar_interpretation_context(
    candidate: RadarCandidate,
    evidence_bundle: RadarEvidenceBundle,
    *,
    as_of: date | None = None,
    now: datetime | None = None,
    max_citations: int = _MAX_CITATIONS,
    max_text_chars: int = _MAX_TEXT_CHARS,
) -> RadarInterpretationContext:
    """Create a compact context without provider bodies, score values, or ranking values."""

    if evidence_bundle.candidate_id != candidate.candidate_id:
        raise ValueError("radar_interpretation_candidate_mismatch")
    created_at = _ensure_utc(now or datetime.now(UTC))
    resolved_as_of = as_of or evidence_bundle.context.as_of
    sections: list[AssistantContextSection] = [
        AssistantContextSection(
            section_id="radar_candidate",
            title="Radar candidate",
            source_kind="radar_candidate",
            symbol=candidate.symbol,
            summary={
                "candidate_id": candidate.candidate_id,
                "symbol": candidate.symbol,
                "display_name": candidate.display_name or "unknown",
                "provenance": candidate.provenance,
                "material_tone": candidate.material_tone,
                "freshness": candidate.freshness_status,
                "watchlist_match": "yes" if candidate.watchlist_match else "no",
            },
            notes=[
                "This is a confirmation candidate, not a ranking or investment recommendation.",
                "Do not calculate, replace, or change scores, ranks, forecasts, or prices.",
            ],
            included_fields=[
                "symbol",
                "candidate_id",
                "display_name",
                "provenance",
                "material_tone",
                "freshness",
                "watchlist_match",
            ],
        )
    ]
    allowed_ids: list[str] = []
    for evidence in candidate.evidence[:_MAX_NEWS_EVIDENCE]:
        allowed_ids.append(evidence.evidence_id)
        sections.append(
            AssistantContextSection(
                section_id=evidence.evidence_id,
                title=_clip(evidence.headline_title, max_text_chars),
                source_kind="radar_news_evidence",
                symbol=candidate.symbol,
                summary={
                    "source_type": evidence.source_type,
                    "source_name": evidence.source_name or "unknown",
                    "category": evidence.category,
                    "material_type": evidence.material_type,
                    "freshness": evidence.freshness_status,
                    "published_at": _format_datetime(evidence.published_at),
                    "provenance": evidence.provenance,
                },
                notes=["News headline metadata only; full provider text is excluded."],
                included_fields=[
                    "source_type",
                    "source_name",
                    "category",
                    "material_type",
                    "freshness",
                    "published_at",
                    "provenance",
                ],
            )
        )
    for citation in evidence_bundle.citations[: max(1, min(max_citations, _MAX_CITATIONS))]:
        allowed_ids.append(citation.citation_id)
        sections.append(
            AssistantContextSection(
                section_id=citation.citation_id,
                title=_clip(citation.title, max_text_chars),
                source_kind="radar_rag_evidence",
                symbol=candidate.symbol,
                summary={
                    "source_type": citation.source_type,
                    "published_at": (
                        citation.published_at.isoformat()
                        if citation.published_at is not None
                        else "unknown"
                    ),
                    "freshness": citation.freshness_status,
                    "excerpt": _clip(citation.excerpt, max_text_chars),
                },
                notes=["Local RAG excerpt only; full source text is excluded."],
                included_fields=["source_type", "published_at", "freshness", "excerpt"],
            )
        )
    warnings = _dedupe(evidence_bundle.confirmation_gaps)
    if not allowed_ids:
        warnings.append("参照できるニュースまたはローカルRAG根拠がありません。")
    bundle = AssistantContextBundle(
        bundle_id=f"radar-interpretation-{candidate.candidate_id}-{resolved_as_of.isoformat()}",
        title=f"Radar Interpretation - {candidate.symbol}",
        source="streamlit_context",
        created_at=created_at,
        active_context_id="radar_interpretation",
        sections=sections,
        tags=["radar", "interpretation", candidate.symbol, candidate.provenance],
        privacy_notes=[
            "Provider raw fields, debug logs, and full external source bodies are excluded.",
            "Only news evidence IDs and local-RAG citation IDs may be cited by the response.",
            "This bundle is for confirmation support, never score, rank, or forecast recomputation.",
        ],
    )
    return RadarInterpretationContext(
        candidate_id=candidate.candidate_id,
        symbol=candidate.symbol,
        as_of=resolved_as_of,
        bundle=bundle,
        context_hash=_context_hash(bundle),
        allowed_evidence_ids=_dedupe(allowed_ids),
        allowed_symbols=[candidate.symbol],
        allowed_numeric_values=_allowed_numeric_values(bundle),
        allowed_dates=_allowed_dates(bundle, as_of=resolved_as_of),
        warnings=_dedupe(warnings),
    )


def build_radar_interpretation_from_settings(
    candidate: RadarCandidate,
    evidence_bundle: RadarEvidenceBundle,
    *,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> RadarInterpretationResult:
    """Build context and use the Gateway only when the Radar setting is explicitly enabled."""

    resolved_settings = settings or get_settings()
    config = resolved_settings.llm_interpretation.radar
    context = build_radar_interpretation_context(
        candidate,
        evidence_bundle,
        now=now,
        max_citations=config.max_citations,
        max_text_chars=config.max_context_text_chars,
    )
    if not config.enabled or config.execution_mode == "off":
        return RadarInterpretationService(None, config=config).interpret(context, now=now)
    client = HttpAssistantGatewayClient(
        base_url=config.base_url,
        context_answer_path=config.context_answer_path,
        timeout_seconds=config.timeout_seconds,
        model=config.model,
        execution_mode=config.execution_mode,
        environment_profile=config.environment_profile,
        preferred_profile=config.preferred_profile,
        transport=transport,
    )
    adapter = RadarInterpretationGatewayAdapter(
        client,
        execution_mode=config.execution_mode,
        environment_profile=config.environment_profile,
        preferred_profile=config.preferred_profile,
    )
    return RadarInterpretationService(adapter, config=config).interpret(context, now=now)


def radar_interpretation_from_gateway_response(
    response: AssistantGatewayResponse,
    *,
    context: RadarInterpretationContext,
    generated_at: datetime,
    prompt_version: str = RADAR_INTERPRETATION_PROMPT_VERSION,
    schema_version: str = RADAR_INTERPRETATION_SCHEMA_VERSION,
) -> RadarInterpretationResult:
    """Validate that generated text remains evidence-bound and advisory-free."""

    if response.gateway_status != "ok":
        raise RadarInterpretationValidationError(response.fallback_reason or "validation_error")
    payload = response.radar_interpretation
    if payload is None:
        raise RadarInterpretationValidationError("malformed_json")
    if payload.schema_version != RADAR_INTERPRETATION_SCHEMA_VERSION:
        raise RadarInterpretationValidationError("malformed_json")
    if payload.candidate_id != context.candidate_id:
        raise RadarInterpretationValidationError("wrong_symbol")
    summary = _validated_point(payload.summary, context=context)
    material_points = _validated_points(payload.positive_materials, context=context)
    caution_points = _validated_points(payload.cautions, context=context)
    unknowns = _validated_points(payload.unknowns, context=context)
    next_checks = _validated_points(payload.next_checkpoints, context=context)
    referenced_ids = _dedupe(
        [
            *summary.evidence_ids,
            *(evidence_id for point in material_points for evidence_id in point.evidence_ids),
            *(evidence_id for point in caution_points for evidence_id in point.evidence_ids),
            *(evidence_id for point in unknowns for evidence_id in point.evidence_ids),
            *(evidence_id for point in next_checks for evidence_id in point.evidence_ids),
        ]
    )
    response_reference_ids = _dedupe([item.section_id for item in response.referenced_sections])
    if response_reference_ids != referenced_ids:
        raise RadarInterpretationValidationError("unknown_evidence")
    warnings = list(context.warnings)
    if not response.provider or not response.model or not response.profile:
        warnings.append("LLM接続メタ情報の一部が不足しています。")
    return RadarInterpretationResult(
        candidate_id=context.candidate_id,
        symbol=context.symbol,
        status="live",
        overall_reading=_clip(summary.summary, _MAX_READING_CHARS),
        material_points=material_points,
        caution_points=caution_points,
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
        fallback_reason=None,
        is_fallback=False,
    )


def _validated_points(
    points: list[AssistantGatewayEvidencePoint],
    *,
    context: RadarInterpretationContext,
) -> list[RadarInterpretationPoint]:
    return [_validated_point(point, context=context) for point in points]


def _validated_point(
    point: AssistantGatewayEvidencePoint,
    *,
    context: RadarInterpretationContext,
) -> RadarInterpretationPoint:
    evidence_ids = _dedupe(point.cited_evidence_ids)
    if not evidence_ids or set(evidence_ids) - set(context.allowed_evidence_ids):
        raise RadarInterpretationValidationError("unknown_evidence")
    _validate_grounded_text(point.text, context=context)
    return RadarInterpretationPoint(
        summary=_clip(point.text, _MAX_TEXT_CHARS),
        evidence_ids=evidence_ids,
    )


def _validate_grounded_text(value: str, *, context: RadarInterpretationContext) -> None:
    values = [value]
    if _has_forbidden_policy_text(values) or _has_score_or_ranking_change_text(values):
        raise RadarInterpretationValidationError("policy_violation")
    _validate_symbols(value, allowed_symbols=context.allowed_symbols)
    _validate_dates(value, allowed_dates=context.allowed_dates)
    _validate_numbers(value, allowed_values=context.allowed_numeric_values)


def _validate_symbols(value: str, *, allowed_symbols: list[str]) -> None:
    allowed = {symbol.strip().upper() for symbol in allowed_symbols if symbol.strip()}
    observed = {
        *{match.upper() for match in _JAPANESE_TICKER_PATTERN.findall(value)},
        *{
            match.upper()
            for match in _US_TICKER_PATTERN.findall(value)
            if match.upper() not in _NON_SYMBOL_UPPERCASE_TOKENS
        },
    }
    if observed - allowed:
        raise RadarInterpretationValidationError("wrong_symbol")


def _validate_dates(value: str, *, allowed_dates: list[str]) -> None:
    allowed = set(allowed_dates)
    observed = {
        *_canonical_dates(value, _ISO_DATE_PATTERN),
        *_canonical_dates(value, _JAPANESE_DATE_PATTERN),
    }
    if observed - allowed:
        raise RadarInterpretationValidationError("unsupported_date")


def _validate_numbers(value: str, *, allowed_values: list[str]) -> None:
    allowed = set(allowed_values)
    observed = {_normalize_numeric_token(match) for match in _NUMERIC_TOKEN_PATTERN.findall(value)}
    if observed - allowed:
        raise RadarInterpretationValidationError("unsupported_number")


def build_deterministic_radar_interpretation(
    context: RadarInterpretationContext,
    *,
    status: RadarInterpretationStatus,
    fallback_reason: RadarInterpretationFallbackReason,
    generated_at: datetime,
    prompt_version: str = RADAR_INTERPRETATION_PROMPT_VERSION,
    schema_version: str = RADAR_INTERPRETATION_SCHEMA_VERSION,
) -> RadarInterpretationResult:
    """Keep failure transparent without inventing investment conclusions."""

    unknowns = _points(context.warnings, evidence_ids=[])
    if not unknowns:
        unknowns = [
            RadarInterpretationPoint(
                summary="この根拠だけでは判断できません。出典と未確認事項を確認してください。",
                evidence_ids=[],
            )
        ]
    return RadarInterpretationResult(
        candidate_id=context.candidate_id,
        symbol=context.symbol,
        status=status,
        overall_reading="この根拠だけでは判断できません。出典・鮮度・未確認事項を確認してください。",
        unknowns=unknowns,
        next_checks=[
            RadarInterpretationPoint(
                summary="ニュース根拠とローカルRAG根拠を個別に確認してください。",
                evidence_ids=context.allowed_evidence_ids[:3],
            )
        ],
        referenced_evidence_ids=context.allowed_evidence_ids,
        warnings=_dedupe(context.warnings),
        generated_at=_ensure_utc(generated_at),
        prompt_version=prompt_version,
        schema_version=schema_version,
        context_hash=context.context_hash,
        fallback_reason=fallback_reason,
        is_fallback=True,
    )


def radar_interpretation_contract_metadata() -> dict[str, str]:
    return {
        "task_type": "news_materials",
        "prompt_version": RADAR_INTERPRETATION_PROMPT_VERSION,
        "schema_version": RADAR_INTERPRETATION_SCHEMA_VERSION,
        "response_schema": RADAR_INTERPRETATION_SCHEMA_VERSION,
    }


def _coerce_gateway_response(
    response: AssistantGatewayResponse | Mapping[str, object],
) -> AssistantGatewayResponse:
    if isinstance(response, AssistantGatewayResponse):
        return response
    try:
        return AssistantGatewayResponse.model_validate(response)
    except ValidationError as exc:
        raise RadarInterpretationValidationError("malformed_json") from exc


def _fallback_reason(exc: Exception) -> RadarInterpretationFallbackReason:
    if isinstance(exc, RadarInterpretationValidationError):
        return _normalize_reason(exc.reason)
    if isinstance(exc, AssistantGatewayTimeoutError) or isinstance(exc, TimeoutError):
        return "gateway_timeout"
    if isinstance(exc, AssistantGatewayError):
        if exc.provider_error_type:
            return "provider_error"
        if exc.gateway_error_type == "gateway_http_error":
            return "gateway_http_error"
        if exc.gateway_error_type == "invalid_gateway_response":
            return "malformed_json"
        return "gateway_unavailable"
    return "validation_error"


def _normalize_reason(reason: str | None) -> RadarInterpretationFallbackReason:
    normalized = (reason or "").strip().lower()
    allowed = {
        "disabled",
        "gateway_unavailable",
        "gateway_timeout",
        "gateway_http_error",
        "malformed_json",
        "validation_error",
        "unknown_evidence",
        "policy_violation",
        "wrong_symbol",
        "unsupported_number",
        "unsupported_date",
        "provider_error",
    }
    return normalized if normalized in allowed else "validation_error"  # type: ignore[return-value]


def _points(values: list[str], *, evidence_ids: list[str]) -> list[RadarInterpretationPoint]:
    return [
        RadarInterpretationPoint(
            summary=_clip(value, _MAX_TEXT_CHARS), evidence_ids=evidence_ids[:5]
        )
        for value in values[:4]
        if value.strip()
    ]


def _unknown_points(
    values: list[str], *, evidence_ids: list[str]
) -> list[RadarInterpretationPoint]:
    return _points(
        [
            value
            for value in values
            if any(token in value for token in ("未確認", "不足", "不確実", "確認", "注意"))
        ],
        evidence_ids=evidence_ids,
    )


def _has_forbidden_policy_text(values: list[str]) -> bool:
    joined = "\n".join(values).lower()
    return any(pattern.lower() in joined for pattern in _FORBIDDEN_PATTERNS)


def _has_score_or_ranking_change_text(values: list[str]) -> bool:
    joined = "\n".join(values).lower()
    return any(pattern.lower() in joined for pattern in _SCORE_OR_RANKING_CHANGE_PATTERNS)


def _allowed_numeric_values(bundle: AssistantContextBundle) -> list[str]:
    return sorted(
        {
            _normalize_numeric_token(match)
            for match in _context_text_values(bundle)
            for match in _NUMERIC_TOKEN_PATTERN.findall(match)
        }
    )


def _allowed_dates(bundle: AssistantContextBundle, *, as_of: date) -> list[str]:
    values = [*list(_context_text_values(bundle)), as_of.isoformat()]
    return sorted(
        {
            *(
                canonical
                for value in values
                for canonical in _canonical_dates(value, _ISO_DATE_PATTERN)
            ),
            *(
                canonical
                for value in values
                for canonical in _canonical_dates(value, _JAPANESE_DATE_PATTERN)
            ),
        }
    )


def _context_text_values(bundle: AssistantContextBundle) -> list[str]:
    values = [bundle.bundle_id, bundle.title, *bundle.tags]
    for section in bundle.sections:
        values.extend(
            [
                section.section_id,
                section.title,
                *section.summary.values(),
                *section.warnings,
                *section.notes,
            ]
        )
        for row in section.rows:
            values.extend(row.values())
    return values


def _canonical_dates(value: str, pattern: re.Pattern[str]) -> set[str]:
    result: set[str] = set()
    for year_text, month_text, day_text in pattern.findall(value):
        try:
            result.add(date(int(year_text), int(month_text), int(day_text)).isoformat())
        except ValueError:
            continue
    return result


def _normalize_numeric_token(value: str) -> str:
    return value.replace(",", "").replace("％", "%")


def _context_hash(bundle: AssistantContextBundle) -> str:
    payload = bundle.model_dump(mode="json")
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _clip(value: str, max_chars: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}…"


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat() if value is not None else "unknown"


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
