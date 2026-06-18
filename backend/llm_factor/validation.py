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


class LLMFactorLiveValidationError(ValueError):
    """Raised when a live LLM Factor response cannot be trusted."""


def llm_factor_result_from_gateway_response(
    response: LLMFactorGenerationResponse,
    *,
    request: LLMFactorGenerationRequest,
    context_hash: str,
    fallback_sources: list[EvidenceSource],
) -> LLMFactorResult:
    """Validate a Gateway response and map it into the existing SMAI result shape."""

    if response.gateway_status != "ok":
        raise LLMFactorLiveValidationError(response.fallback_reason or "gateway_fallback")
    if response.symbol.strip().upper() != request.symbol.strip().upper():
        raise LLMFactorLiveValidationError("symbol_mismatch")

    valid_evidence_ids = {item.evidence_id for item in request.context.evidence}
    referenced_ids = _referenced_evidence_ids(response)
    if not referenced_ids and response.confidence > 0.7:
        raise LLMFactorLiveValidationError("high_confidence_without_evidence")
    unknown_ids = referenced_ids - valid_evidence_ids
    if unknown_ids:
        raise LLMFactorLiveValidationError(f"unknown_evidence_ids:{','.join(sorted(unknown_ids))}")

    evidence_by_id = {item.evidence_id: item for item in request.context.evidence}
    result_sources = _evidence_sources_from_response(
        response,
        evidence_by_id=evidence_by_id,
        fallback_sources=fallback_sources,
        as_of=request.as_of,
    )
    if not result_sources:
        result_sources = fallback_sources

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
    confidence = _score_from_unit(response.confidence)
    warnings = _dedupe(
        [
            *response.warnings,
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
            "summary": response.overall_summary,
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
                summary=context_item.summary,
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
                title=item.title[:48],
                score=_score_from_unit(item.strength),
                reason=item.summary,
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
                title=opportunity.title[:48],
                score=_score_from_unit(opportunity.impact),
                reason=opportunity.summary,
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
                title=item.title[:48],
                score=_score_from_unit(item.strength),
                reason=item.summary,
                source_url=_source_url(source, item.evidence_ids),
                source_date=source.source_date if source and source.source_date else as_of,
                source_type=_source_type(source.source_type) if source else "other",
            )
        )
    for risk in response.risks:
        source = _first_evidence_by_ids(risk.evidence_ids, evidence_by_id=evidence_by_id)
        factors.append(
            BearishFactor(
                title=risk.title[:48],
                score=_score_from_unit(risk.severity),
                reason=risk.summary,
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
