from __future__ import annotations

from datetime import UTC, date
from decimal import Decimal

from backend.llm_factor.contracts import (
    BearishFactor,
    BullishFactor,
    EvidenceSource,
    LLMFactorResult,
    LLMFactorSourceType,
)
from backend.llm_factor.live_contracts import (
    LLMFactorEvidenceContext,
    LLMFactorGatewayFactor,
    LLMFactorGenerationRequest,
    LLMFactorGenerationResponse,
)
from backend.llm_factor.service import FakeLLMFactorService

_MAX_SUMMARY_CHARS = 700
_MAX_FACTOR_REASON_CHARS = 320
_MAX_SOURCE_SUMMARY_CHARS = 360
_STALE_SOURCE_DAYS = 365
_FUTURE_SOURCE_DAYS = 1


class LLMFactorLiveValidationError(ValueError):
    """Raised when a live LLM Factor response cannot be trusted."""

    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


def llm_factor_result_from_gateway_response(
    response: LLMFactorGenerationResponse,
    *,
    request: LLMFactorGenerationRequest,
    context_hash: str,
    fallback_sources: list[EvidenceSource],
) -> LLMFactorResult:
    """Validate a Gateway response and map it into the existing SMAI result shape."""

    if response.gateway_status != "ok":
        raise LLMFactorLiveValidationError(response.fallback_reason or "validation_error")
    if response.symbol.strip().upper() != request.symbol.strip().upper():
        raise LLMFactorLiveValidationError("wrong_symbol")

    valid_evidence_ids = {item.evidence_id for item in request.context.evidence}
    referenced_ids = _referenced_evidence_ids(response)
    declared_ids = {item.evidence_id for item in response.evidence if item.evidence_id}
    if not referenced_ids and response.confidence > 0.7:
        raise LLMFactorLiveValidationError("validation_error")
    unknown_ids = (referenced_ids | declared_ids) - valid_evidence_ids
    if unknown_ids:
        raise LLMFactorLiveValidationError("unknown_evidence")

    quality_warnings: list[str] = []
    confidence_cap = Decimal("100")
    if response.schema_version != request.response_schema_version:
        quality_warnings.append("AI応答のschema_versionが想定と異なるため、参考度を下げています。")
        confidence_cap = min(confidence_cap, Decimal("60"))
    if response.prompt_version != request.prompt_version:
        quality_warnings.append("AI応答のprompt_versionが想定と異なるため、参考度を下げています。")
        confidence_cap = min(confidence_cap, Decimal("60"))
    if _response_has_overlong_text(response):
        quality_warnings.append("AI応答が長いため、画面表示用に一部を短くしました。")

    evidence_by_id = {item.evidence_id: item for item in request.context.evidence}
    result_sources = _evidence_sources_from_response(
        response,
        evidence_by_id=evidence_by_id,
        fallback_sources=fallback_sources,
        as_of=request.as_of,
    )
    if not result_sources:
        result_sources = fallback_sources
    if _has_stale_or_future_source(result_sources, as_of=request.as_of):
        quality_warnings.append(
            "古い、または日付が未来の出典が含まれるため、AI材料分析の確信度を控えめに扱います。"
        )
        confidence_cap = min(confidence_cap, Decimal("55"))
    if _has_contradictory_materials(response):
        quality_warnings.append(
            "強弱材料が同時に強く出ているため、AI材料分析の確信度を控えめに扱います。"
        )
        confidence_cap = min(confidence_cap, Decimal("55"))

    base = FakeLLMFactorService().build_reference_result(
        ticker=request.symbol,
        as_of=request.as_of,
        evidence_sources=result_sources,
        generated_at=response.generated_at.astimezone(UTC),
    )
    bullish_factors = _bullish_factors_from_response(
        response,
        evidence_by_id=evidence_by_id,
        as_of=request.as_of,
    )
    bearish_factors = _bearish_factors_from_response(
        response,
        evidence_by_id=evidence_by_id,
        as_of=request.as_of,
    )
    confidence = min(_score_from_unit(response.confidence), confidence_cap)
    warnings = _dedupe(
        [
            *response.warnings,
            *quality_warnings,
            *(
                [f"不足項目: {', '.join(response.missing_fields)}"]
                if response.missing_fields
                else []
            ),
        ]
    )
    return base.model_copy(
        update={
            "generated_at": response.generated_at.astimezone(UTC),
            "model_name": response.model,
            "prompt_version": response.prompt_version,
            "source_hash": context_hash,
            "llm_bullish_score": _material_score(
                bullish_factors,
                fallback=base.llm_bullish_score,
            ),
            "llm_bearish_score": _material_score(
                bearish_factors,
                fallback=base.llm_bearish_score,
            ),
            "llm_catalyst_score": _score_from_unit(
                max([item.strength for item in response.factors] or [0.0])
            ),
            "llm_risk_score": _score_from_unit(
                max(
                    [item.severity for item in response.risks] or [float(base.llm_risk_score) / 100]
                )
            ),
            "llm_confidence_score": confidence,
            "bullish_factors": bullish_factors[:3],
            "bearish_factors": bearish_factors[:3],
            "evidence_sources": result_sources,
            "summary": _trim_text(response.overall_summary, _MAX_SUMMARY_CHARS),
            "warnings": warnings,
            "provider": response.provider,
            "gateway_profile": response.profile,
            "gateway_status": response.gateway_status,
            "fallback_reason": response.fallback_reason,
            "sentiment_label": response.sentiment_label,
            "missing_fields": response.missing_fields,
        }
    )


def _evidence_sources_from_response(
    response: LLMFactorGenerationResponse,
    *,
    evidence_by_id: dict[str, LLMFactorEvidenceContext],
    fallback_sources: list[EvidenceSource],
    as_of: date,
) -> list[EvidenceSource]:
    result: list[EvidenceSource] = []
    used_ids = _referenced_evidence_ids(response) or {
        item.evidence_id for item in response.evidence
    }
    fallback_by_url = {source.source_url: source for source in fallback_sources}
    for evidence_id in sorted(used_ids):
        context_item = evidence_by_id.get(evidence_id)
        if context_item is None:
            continue
        existing = fallback_by_url.get(context_item.source_url or "")
        if existing is not None:
            result.append(existing)
            continue
        result.append(
            EvidenceSource(
                title=context_item.title,
                source_type=_source_type(context_item.source_type),
                source_url=(context_item.source_url or f"smai://llm-factor/evidence/{evidence_id}"),
                source_date=context_item.source_date or as_of,
                provider=context_item.provider,
                summary=_trim_text(context_item.summary, _MAX_SOURCE_SUMMARY_CHARS),
                reliability_score=_decimal_score(context_item.reliability_score, default=50),
            )
        )
    return _dedupe_sources(result)


def _bullish_factors_from_response(
    response: LLMFactorGenerationResponse,
    *,
    evidence_by_id: dict[str, LLMFactorEvidenceContext],
    as_of: date,
) -> list[BullishFactor]:
    factors: list[BullishFactor] = []
    for item in response.factors:
        if item.direction != "positive":
            continue
        source = _first_evidence_for_item(item, evidence_by_id=evidence_by_id)
        factors.append(
            BullishFactor(
                title=_trim_text(item.title, 48),
                score=_score_from_unit(item.strength),
                reason=_trim_text(item.summary, _MAX_FACTOR_REASON_CHARS),
                source_url=_source_url(source, item.evidence_ids),
                source_date=source.source_date if source and source.source_date else as_of,
                source_type=_source_type(source.source_type) if source else "other",
            )
        )
    for opportunity in response.opportunities:
        source = _first_evidence_by_ids(
            opportunity.evidence_ids,
            evidence_by_id=evidence_by_id,
        )
        factors.append(
            BullishFactor(
                title=_trim_text(opportunity.title, 48),
                score=_score_from_unit(opportunity.impact),
                reason=_trim_text(opportunity.summary, _MAX_FACTOR_REASON_CHARS),
                source_url=_source_url(source, opportunity.evidence_ids),
                source_date=source.source_date if source and source.source_date else as_of,
                source_type=_source_type(source.source_type) if source else "other",
            )
        )
    return factors


def _bearish_factors_from_response(
    response: LLMFactorGenerationResponse,
    *,
    evidence_by_id: dict[str, LLMFactorEvidenceContext],
    as_of: date,
) -> list[BearishFactor]:
    factors: list[BearishFactor] = []
    for item in response.factors:
        if item.direction != "negative":
            continue
        source = _first_evidence_for_item(item, evidence_by_id=evidence_by_id)
        factors.append(
            BearishFactor(
                title=_trim_text(item.title, 48),
                score=_score_from_unit(item.strength),
                reason=_trim_text(item.summary, _MAX_FACTOR_REASON_CHARS),
                source_url=_source_url(source, item.evidence_ids),
                source_date=source.source_date if source and source.source_date else as_of,
                source_type=_source_type(source.source_type) if source else "other",
            )
        )
    for risk in response.risks:
        source = _first_evidence_by_ids(risk.evidence_ids, evidence_by_id=evidence_by_id)
        factors.append(
            BearishFactor(
                title=_trim_text(risk.title, 48),
                score=_score_from_unit(risk.severity),
                reason=_trim_text(risk.summary, _MAX_FACTOR_REASON_CHARS),
                source_url=_source_url(source, risk.evidence_ids),
                source_date=source.source_date if source and source.source_date else as_of,
                source_type=_source_type(source.source_type) if source else "other",
            )
        )
    return factors


def _first_evidence_for_item(
    item: LLMFactorGatewayFactor,
    *,
    evidence_by_id: dict[str, LLMFactorEvidenceContext],
) -> LLMFactorEvidenceContext | None:
    return _first_evidence_by_ids(item.evidence_ids, evidence_by_id=evidence_by_id)


def _first_evidence_by_ids(
    evidence_ids: list[str],
    *,
    evidence_by_id: dict[str, LLMFactorEvidenceContext],
) -> LLMFactorEvidenceContext | None:
    for evidence_id in evidence_ids:
        source = evidence_by_id.get(evidence_id)
        if source is not None:
            return source
    return None


def _source_url(source: LLMFactorEvidenceContext | None, evidence_ids: list[str]) -> str:
    if source is not None and source.source_url:
        return source.source_url
    evidence_id = evidence_ids[0] if evidence_ids else "unknown"
    return f"smai://llm-factor/evidence/{evidence_id}"


def _referenced_evidence_ids(response: LLMFactorGenerationResponse) -> set[str]:
    referenced: set[str] = set()
    for factor in response.factors:
        referenced.update(factor.evidence_ids)
    for risk in response.risks:
        referenced.update(risk.evidence_ids)
    for opportunity in response.opportunities:
        referenced.update(opportunity.evidence_ids)
    return {item for item in referenced if item}


def _response_has_overlong_text(response: LLMFactorGenerationResponse) -> bool:
    if len(response.overall_summary) > _MAX_SUMMARY_CHARS:
        return True
    for factor in response.factors:
        if len(factor.summary) > _MAX_FACTOR_REASON_CHARS or len(factor.title) > 48:
            return True
    for risk in response.risks:
        if len(risk.summary) > _MAX_FACTOR_REASON_CHARS or len(risk.title) > 48:
            return True
    for opportunity in response.opportunities:
        if len(opportunity.summary) > _MAX_FACTOR_REASON_CHARS or len(opportunity.title) > 48:
            return True
    return any(len(item.summary) > _MAX_SOURCE_SUMMARY_CHARS for item in response.evidence)


def _has_stale_or_future_source(sources: list[EvidenceSource], *, as_of: date) -> bool:
    for source in sources:
        delta_days = (as_of - source.source_date).days
        if delta_days > _STALE_SOURCE_DAYS or delta_days < -_FUTURE_SOURCE_DAYS:
            return True
    return False


def _has_contradictory_materials(response: LLMFactorGenerationResponse) -> bool:
    positive_strength = max(
        [
            *(item.strength for item in response.factors if item.direction == "positive"),
            *(item.impact for item in response.opportunities),
            0.0,
        ]
    )
    negative_strength = max(
        [
            *(item.strength for item in response.factors if item.direction == "negative"),
            *(item.severity for item in response.risks),
            0.0,
        ]
    )
    if positive_strength >= 0.7 and negative_strength >= 0.7:
        return True
    if response.sentiment_label == "positive" and negative_strength >= 0.75:
        return True
    if response.sentiment_label == "negative" and positive_strength >= 0.75:
        return True
    return False


def _trim_text(value: str, max_chars: int) -> str:
    normalized = value.strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _material_score(
    factors: list[BullishFactor] | list[BearishFactor],
    *,
    fallback: Decimal,
) -> Decimal:
    if not factors:
        return fallback
    return _decimal_score(sum(factor.score for factor in factors) / Decimal(len(factors)))


def _score_from_unit(value: float) -> Decimal:
    return _decimal_score(Decimal(str(value)) * Decimal("100"))


def _decimal_score(value: Decimal | float | None, *, default: int = 0) -> Decimal:
    if value is None:
        value = Decimal(default)
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return max(Decimal("0"), min(Decimal("100"), value.quantize(Decimal("1"))))


def _source_type(value: str) -> LLMFactorSourceType:
    allowed = {
        "research_summary",
        "news",
        "tdnet",
        "edinet",
        "company_ir",
        "provider_profile",
        "symbol_db",
        "local_reference",
        "other",
    }
    return value if value in allowed else "other"  # type: ignore[return-value]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _dedupe_sources(sources: list[EvidenceSource]) -> list[EvidenceSource]:
    result: list[EvidenceSource] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (source.source_url, source.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(source)
    return result
