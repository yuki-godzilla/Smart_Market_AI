from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal

from backend.llm_factor.contracts import EvidenceSource
from backend.llm_factor.live_contracts import (
    LLM_FACTOR_GATEWAY_RESPONSE_SCHEMA_VERSION,
    LLM_FACTOR_LIVE_PROMPT_VERSION,
    LLMFactorEvidenceContext,
    LLMFactorGenerationConstraints,
    LLMFactorGenerationContext,
    LLMFactorGenerationRequest,
)

DEFAULT_LLM_FACTOR_MAX_EVIDENCE_ITEMS = 8
DEFAULT_LLM_FACTOR_CONTEXT_TEXT_CHARS = 280


def build_llm_factor_generation_request(
    *,
    ticker: str,
    as_of: date,
    evidence_sources: Iterable[EvidenceSource],
    company_name: str | None = None,
    symbol_profile: Mapping[str, object] | None = None,
    forecast_summary: Mapping[str, object] | None = None,
    language: str = "ja",
    prompt_version: str = LLM_FACTOR_LIVE_PROMPT_VERSION,
    response_schema_version: str = LLM_FACTOR_GATEWAY_RESPONSE_SCHEMA_VERSION,
    max_evidence_items: int = DEFAULT_LLM_FACTOR_MAX_EVIDENCE_ITEMS,
    max_text_chars: int = DEFAULT_LLM_FACTOR_CONTEXT_TEXT_CHARS,
) -> LLMFactorGenerationRequest:
    """Build a compact one-symbol Gateway request without provider raw fields."""

    normalized_company_name = str(company_name or "").strip() or None
    sources = list(evidence_sources)[: max(1, max_evidence_items)]
    evidence = [
        LLMFactorEvidenceContext(
            evidence_id=f"evidence_{index:03d}",
            title=_trim_text(source.title, max_text_chars),
            source_type=source.source_type,
            source_url=source.source_url,
            source_date=source.source_date,
            provider=source.provider,
            summary=_trim_text(source.summary or source.title, max_text_chars),
            reliability_score=_float_from_decimal(source.reliability_score),
        )
        for index, source in enumerate(sources, start=1)
    ]
    profile = _string_map(symbol_profile or {})
    if normalized_company_name:
        profile.setdefault(
            "company_name",
            _trim_text(normalized_company_name, max_text_chars),
        )
    profile.setdefault("symbol", ticker)
    context = LLMFactorGenerationContext(
        symbol_profile=profile,
        research_summary=[
            item.summary
            for item in evidence
            if item.source_type not in {"news"} and item.summary.strip()
        ][:4],
        news_summary=[
            item.summary for item in evidence if item.source_type == "news" and item.summary.strip()
        ][:4],
        forecast_summary=_string_map(forecast_summary or {}),
        evidence=evidence,
    )
    return LLMFactorGenerationRequest(
        symbol=ticker,
        company_name=normalized_company_name,
        as_of=as_of,
        language="ja" if language != "en" else "en",
        context=context,
        constraints=LLMFactorGenerationConstraints(),
        prompt_version=prompt_version,
        response_schema_version=response_schema_version,
    )


def llm_factor_context_hash(request: LLMFactorGenerationRequest) -> str:
    """Return a stable hash for the supplied one-symbol context."""

    payload = {
        "symbol": request.symbol.strip().upper(),
        "company_name": request.company_name or "",
        "as_of": request.as_of.isoformat(),
        "language": request.language,
        "context": request.context.model_dump(mode="json"),
        "constraints": request.constraints.model_dump(mode="json"),
        "response_schema_version": request.response_schema_version,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _string_map(values: Mapping[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values.items():
        normalized_key = str(key).strip()
        normalized_value = str(value).strip()
        if normalized_key and normalized_value:
            result[normalized_key] = _trim_text(
                normalized_value,
                DEFAULT_LLM_FACTOR_CONTEXT_TEXT_CHARS,
            )
    return result


def _float_from_decimal(value: Decimal) -> float:
    return float(value)


def _trim_text(value: str, max_chars: int) -> str:
    normalized = " ".join(str(value or "").split())
    if not normalized:
        return ""
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max(1, max_chars - 3)].rstrip() + "..."
