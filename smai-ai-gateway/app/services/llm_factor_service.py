from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Mapping

from pydantic import ValidationError

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.schemas.common import LlmMessage
from app.schemas.llm_factor import (
    LLM_FACTOR_GATEWAY_RESPONSE_SCHEMA_VERSION,
    LLM_FACTOR_LIVE_PROMPT_VERSION,
    LLMFactorDirection,
    LLMFactorEvidenceContext,
    LLMFactorGatewayEvidence,
    LLMFactorGatewayFactor,
    LLMFactorGatewayOpportunity,
    LLMFactorGatewayRisk,
    LLMFactorGenerationRequest,
    LLMFactorGenerationResponse,
    LLMFactorSentimentLabel,
)
from app.services.model_router import ModelRoute, resolve_model_route

LOGGER = logging.getLogger(__name__)
_JA_DECISION_SUPPORT_NOTE = "この結果は判断材料の整理であり、投資助言ではありません。"
_EN_DECISION_SUPPORT_NOTE = "This response is decision-support context, not investment advice."


class LLMFactorGenerationService:
    """Generate structured one-symbol qualitative factors through the LLM Gateway."""

    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def generate(self, request: LLMFactorGenerationRequest) -> LLMFactorGenerationResponse:
        started = perf_counter()
        route = resolve_model_route(
            settings=self.client.settings,
            task_type="llm_factor_generation",
            execution_mode=request.execution_mode,
            environment_profile=request.environment_profile,
            preferred_profile=request.preferred_profile,
            requested_model=request.model,
        )
        messages = _build_llm_factor_messages(request)
        prompt_chars = sum(len(message.content) for message in messages)
        context_tokens_estimate = max(1, len(request.context.model_dump_json()) // 4)
        if route.fallback:
            return _fallback_response(
                request=request,
                route=route,
                started=started,
                prompt_chars=prompt_chars,
                context_tokens_estimate=context_tokens_estimate,
                fallback_reason=route.reason,
                provider=route.provider,
                model=route.model,
            )

        LOGGER.info(
            "[gateway.llm_factor.start] request_id=%s symbol=%s provider=%s model=%s "
            "profile=%s prompt_chars=%s context_tokens_estimate=%s",
            request.request_id,
            request.symbol,
            route.provider,
            route.model,
            route.profile,
            prompt_chars,
            context_tokens_estimate,
        )
        try:
            result = self.client.chat(
                messages,
                model=route.model,
                timeout_seconds=route.timeout_seconds,
                max_tokens=route.max_tokens,
            )
        except OllamaClientError as exc:
            return _fallback_response(
                request=request,
                route=route,
                started=started,
                prompt_chars=prompt_chars,
                context_tokens_estimate=context_tokens_estimate,
                fallback_reason=exc.code,
                provider=exc.provider,
                model=route.model,
                warning=str(exc),
            )

        parsed = _parse_llm_factor_response(
            result.answer,
            request=request,
            route=route,
            provider=result.provider,
            model=result.model,
            elapsed_ms=result.elapsed_ms,
            prompt_chars=result.prompt_chars or prompt_chars,
            response_chars=result.response_chars or len(result.answer),
            context_tokens_estimate=context_tokens_estimate,
        )
        if parsed is None:
            return _fallback_response(
                request=request,
                route=route,
                started=started,
                prompt_chars=prompt_chars,
                context_tokens_estimate=context_tokens_estimate,
                fallback_reason="validation_error",
                provider=result.provider,
                model=result.model,
                warning="LLM response could not be validated as llm_factor.v1 JSON.",
            )
        return parsed


def _build_llm_factor_messages(request: LLMFactorGenerationRequest) -> list[LlmMessage]:
    language_instruction = "Return Japanese strings." if request.language == "ja" else "Return English strings."
    system_prompt = (
        "/no_think\n"
        "You are a careful investment-decision support JSON generator. "
        "Use only the supplied context. Do not invent facts, prices, rankings, or forecasts. "
        "Do not give buy/sell advice or definitive investment recommendations. "
        "If information is missing, put field names in missing_fields and lower confidence. "
        "Every factor, risk, opportunity, and evidence item must reference evidence_ids that exist "
        "in the supplied context. Do not output markdown or explanations. "
        f"{language_instruction} Output JSON only."
    )
    user_prompt = (
        f"schema_version: {request.response_schema_version}\n"
        f"prompt_version: {request.prompt_version}\n"
        f"symbol: {request.symbol}\n"
        f"company_name: {request.company_name or ''}\n"
        f"as_of: {request.as_of.isoformat()}\n\n"
        "Safety constraints:\n"
        f"- no_investment_advice: {request.constraints.no_investment_advice}\n"
        f"- use_only_supplied_context: {request.constraints.use_only_supplied_context}\n"
        f"- do_not_change_scores: {request.constraints.do_not_change_scores}\n"
        f"- do_not_rank_symbols: {request.constraints.do_not_rank_symbols}\n"
        f"- require_evidence_ids: {request.constraints.require_evidence_ids}\n\n"
        "Context JSON:\n"
        f"{request.context.model_dump_json()}\n\n"
        "Return only valid JSON with these keys:\n"
        "- schema_version\n"
        "- symbol\n"
        "- overall_summary\n"
        "- sentiment_label: positive, neutral, negative, mixed, or unknown\n"
        "- confidence: number from 0 to 1\n"
        "- factors: array of {title, direction, summary, strength, evidence_ids}\n"
        "- risks: array of {title, summary, severity, evidence_ids}\n"
        "- opportunities: array of {title, summary, impact, evidence_ids}\n"
        "- evidence: array of {evidence_id, title, source_type, source_url, source_date, summary}\n"
        "- missing_fields\n"
        "- warnings\n"
        "- prompt_version\n"
        "Do not add fields. Do not wrap the JSON in markdown."
    )
    return [
        LlmMessage(role="system", content=system_prompt),
        LlmMessage(role="user", content=user_prompt),
    ]


def _parse_llm_factor_response(
    answer: str,
    *,
    request: LLMFactorGenerationRequest,
    route: ModelRoute,
    provider: str,
    model: str,
    elapsed_ms: int,
    prompt_chars: int,
    response_chars: int,
    context_tokens_estimate: int,
) -> LLMFactorGenerationResponse | None:
    raw_json = _extract_json_object(answer)
    if raw_json is None:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    data = dict(payload)
    protocol_warnings: list[str] = []
    if "schema_version" not in data:
        protocol_warnings.append("missing schema_version")
    if "prompt_version" not in data:
        protocol_warnings.append("missing prompt_version")
    data.setdefault("schema_version", LLM_FACTOR_GATEWAY_RESPONSE_SCHEMA_VERSION)
    data.setdefault("symbol", request.symbol)
    data.setdefault("prompt_version", request.prompt_version)
    data.setdefault("provider", provider)
    data.setdefault("model", model)
    data.setdefault("profile", route.profile)
    data.setdefault("generated_at", datetime.now(UTC).isoformat())
    data.setdefault("elapsed_ms", elapsed_ms)
    data.setdefault("gateway_status", "ok")
    data.setdefault("request_id", request.request_id)
    data.setdefault("timeout_sec", route.timeout_seconds)
    data.setdefault("context_tokens_estimate", context_tokens_estimate)
    data.setdefault("prompt_chars", prompt_chars)
    data.setdefault("response_chars", response_chars)
    data.setdefault("decision_support_note", _decision_support_note(request))
    if protocol_warnings:
        existing_warnings = data.get("warnings")
        if isinstance(existing_warnings, list):
            data["warnings"] = [*existing_warnings, *protocol_warnings]
        else:
            data["warnings"] = protocol_warnings
    try:
        response = LLMFactorGenerationResponse.model_validate(data)
    except ValidationError:
        return None
    if response.symbol.strip().upper() != request.symbol.strip().upper():
        return None
    if not _response_references_supplied_evidence(response, request=request):
        return None
    if response.confidence > 0.7 and not _referenced_evidence_ids(response):
        return None
    return response


def _fallback_response(
    *,
    request: LLMFactorGenerationRequest,
    route: ModelRoute,
    started: float,
    prompt_chars: int,
    context_tokens_estimate: int,
    fallback_reason: str,
    provider: str,
    model: str,
    warning: str | None = None,
) -> LLMFactorGenerationResponse:
    evidence = request.context.evidence[:3]
    warning_items = [fallback_reason]
    if warning:
        warning_items.append(warning)
    missing_fields = _missing_fields_for_context(request)
    return LLMFactorGenerationResponse(
        symbol=request.symbol,
        overall_summary=_fallback_summary(request, evidence),
        sentiment_label=_fallback_sentiment(evidence),
        confidence=0.2 if missing_fields else 0.35,
        factors=_fallback_factors(evidence),
        risks=_fallback_risks(evidence, missing_fields=missing_fields),
        opportunities=_fallback_opportunities(evidence),
        evidence=[_response_evidence_from_context(item) for item in evidence],
        missing_fields=missing_fields,
        warnings=warning_items,
        prompt_version=request.prompt_version or LLM_FACTOR_LIVE_PROMPT_VERSION,
        provider=provider,
        model=model,
        profile=route.profile,
        generated_at=datetime.now(UTC),
        elapsed_ms=int((perf_counter() - started) * 1000),
        gateway_status="fallback",
        fallback_reason=fallback_reason,
        request_id=request.request_id,
        timeout_sec=route.timeout_seconds,
        context_tokens_estimate=context_tokens_estimate,
        prompt_chars=prompt_chars,
        response_chars=0,
        decision_support_note=_decision_support_note(request),
    )


def _fallback_summary(
    request: LLMFactorGenerationRequest,
    evidence: list[LLMFactorEvidenceContext],
) -> str:
    label = request.company_name or request.symbol
    if request.language == "en":
        if evidence:
            return f"{label} has supplied evidence, but live LLM generation fell back to a conservative structured response."
        return f"{label} has insufficient supplied evidence for live LLM factor generation."
    if evidence:
        return f"{label} は出典付き材料を受け取りましたが、LLM生成は保守的なfallback表示に切り替えました。"
    return f"{label} はLLM材料分析に使える出典が不足しているため、低信頼の参考表示です。"


def _fallback_sentiment(evidence: list[LLMFactorEvidenceContext]) -> LLMFactorSentimentLabel:
    if not evidence:
        return "unknown"
    return "mixed"


def _fallback_factors(evidence: list[LLMFactorEvidenceContext]) -> list[LLMFactorGatewayFactor]:
    return [
        LLMFactorGatewayFactor(
            title=item.title[:80],
            direction=_direction_from_text(item),
            summary=item.summary[:240],
            strength=0.35,
            evidence_ids=[item.evidence_id],
        )
        for item in evidence[:2]
    ]


def _fallback_risks(
    evidence: list[LLMFactorEvidenceContext],
    *,
    missing_fields: list[str],
) -> list[LLMFactorGatewayRisk]:
    risks: list[LLMFactorGatewayRisk] = []
    if missing_fields:
        risks.append(
            LLMFactorGatewayRisk(
                title="不足材料の確認",
                summary="十分な出典または補助情報が不足しているため、確信度を低く扱います。",
                severity=0.45,
                evidence_ids=[],
            )
        )
    for item in evidence[:1]:
        risks.append(
            LLMFactorGatewayRisk(
                title=f"確認材料: {item.title[:60]}",
                summary=item.summary[:240],
                severity=0.3,
                evidence_ids=[item.evidence_id],
            )
        )
    return risks


def _fallback_opportunities(
    evidence: list[LLMFactorEvidenceContext],
) -> list[LLMFactorGatewayOpportunity]:
    return [
        LLMFactorGatewayOpportunity(
            title=f"材料確認: {item.title[:60]}",
            summary=item.summary[:240],
            impact=0.3,
            evidence_ids=[item.evidence_id],
        )
        for item in evidence[:1]
    ]


def _direction_from_text(item: LLMFactorEvidenceContext) -> LLMFactorDirection:
    text = f"{item.title} {item.summary}"
    if any(keyword in text for keyword in ("増配", "自社株買", "好決算", "上方修正", "成長")):
        return "positive"
    if any(keyword in text for keyword in ("下方修正", "減益", "リスク", "警戒", "規制")):
        return "negative"
    return "neutral"


def _response_evidence_from_context(item: LLMFactorEvidenceContext) -> LLMFactorGatewayEvidence:
    return LLMFactorGatewayEvidence(
        evidence_id=item.evidence_id,
        title=item.title,
        source_type=item.source_type,
        source_url=item.source_url,
        source_date=item.source_date,
        summary=item.summary,
    )


def _missing_fields_for_context(request: LLMFactorGenerationRequest) -> list[str]:
    missing: list[str] = []
    if not request.company_name:
        missing.append("company_name")
    if not request.context.evidence:
        missing.append("evidence")
    if not request.context.forecast_summary:
        missing.append("forecast_summary")
    return missing


def _response_references_supplied_evidence(
    response: LLMFactorGenerationResponse,
    *,
    request: LLMFactorGenerationRequest,
) -> bool:
    valid_ids = {item.evidence_id for item in request.context.evidence}
    if not valid_ids and not _referenced_evidence_ids(response):
        return True
    return _referenced_evidence_ids(response).issubset(valid_ids)


def _referenced_evidence_ids(response: LLMFactorGenerationResponse) -> set[str]:
    referenced: set[str] = set()
    for factor in response.factors:
        referenced.update(factor.evidence_ids)
    for risk in response.risks:
        referenced.update(risk.evidence_ids)
    for opportunity in response.opportunities:
        referenced.update(opportunity.evidence_ids)
    for evidence in response.evidence:
        referenced.add(evidence.evidence_id)
    return {item for item in referenced if item}


def _extract_json_object(text: str) -> str | None:
    normalized = text.strip()
    if not normalized:
        return None
    if normalized.startswith("```"):
        normalized = normalized.strip("`").strip()
        if normalized.lower().startswith("json"):
            normalized = normalized[4:].strip()
    start = normalized.find("{")
    end = normalized.rfind("}")
    if start < 0 or end < start:
        return None
    return normalized[start : end + 1]


def _decision_support_note(request: LLMFactorGenerationRequest) -> str:
    return _JA_DECISION_SUPPORT_NOTE if request.language == "ja" else _EN_DECISION_SUPPORT_NOTE
