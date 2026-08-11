from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from time import perf_counter

from pydantic import Field, ValidationError

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.schemas.common import GatewayBaseModel, LlmMessage
from app.schemas.context_answer import (
    NEWS_INTERPRETATION_RESPONSE_SCHEMA_VERSION,
    RADAR_INTERPRETATION_RESPONSE_SCHEMA_VERSION,
    RADAR_OVERVIEW_INTERPRETATION_RESPONSE_SCHEMA_VERSION,
    RANKING_INTERPRETATION_RESPONSE_SCHEMA_VERSION,
    ContextAnswerConfidence,
    ContextAnswerGatewayStatus,
    ContextAnswerRequest,
    ContextAnswerResponse,
    ContextNewsInterpretation,
    ContextRadarInterpretation,
    ContextRadarOverviewInterpretation,
    ContextRankingInterpretation,
    ContextReferencedSection,
    ContextSection,
)
from app.services.model_router import resolve_model_route
from app.services.prompt_service import PromptService

_JA_DECISION_SUPPORT_NOTE = "この回答は判断材料の整理であり、投資助言ではありません。"
_EN_DECISION_SUPPORT_NOTE = "This response is decision-support context, not investment advice."
LOGGER = logging.getLogger(__name__)

_FORBIDDEN_PRESENTATION_PATTERNS: tuple[str, ...] = (
    "provider raw fields",
    "debug logs",
    "full external source bodies",
    "external source bodies",
    "raw fields",
    "provider fields",
    "excluded",
    "the bundle is",
    "bundle is for explanation",
    "confirmation support",
    "not score",
    "not ranking",
    "ranking recomputation",
    "score or ranking recomputation",
    "privacy_notes",
    "safety_notes",
    "provider_notes",
    "internal_notes",
    "debug_notes",
    "tool says",
    "the tool says",
    "i need to",
    "first, i need",
    "the answer should",
    "json fields",
    "内部情報",
    "デバッグ情報",
    "provider情報",
    "raw field",
    "外部ソース本文",
    "ランキング再計算",
    "スコア再計算",
    "内部ログ",
    "開発者向け",
)


class LlmContextAnswerPayload(GatewayBaseModel):
    """Structured payload requested from the LLM provider."""

    answer: str = Field(min_length=1)
    materials: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    next_checkpoints: list[str] = Field(default_factory=list)
    confidence: ContextAnswerConfidence = "medium"


class ContextAnswerService:
    """Build a grounded assistant answer from supplied context."""

    def __init__(
        self,
        client: OllamaClient,
        *,
        prompt_service: PromptService | None = None,
    ) -> None:
        self.client = client
        self.prompt_service = prompt_service or PromptService()

    def answer(self, request: ContextAnswerRequest) -> ContextAnswerResponse:
        started = perf_counter()
        route = resolve_model_route(
            settings=self.client.settings,
            task_type=request.task_type,
            execution_mode=request.execution_mode,
            environment_profile=request.environment_profile,
            preferred_profile=request.profile or request.preferred_profile,
            requested_model=request.model,
        )
        messages = self.prompt_service.build_context_answer_messages(request)
        sections = [] if _is_llm_micro_request(request) else _selected_sections(request)
        prompt_chars = sum(len(message.content) for message in messages)
        context_tokens_estimate = _estimate_context_tokens(request)
        LOGGER.info(
            "[gateway.request.start] request_id=%s task_type=%s provider=%s model=%s "
            "profile=%s timeout_sec=%s prompt_chars=%s context_tokens_estimate=%s",
            request.request_id,
            request.task_type,
            route.provider,
            route.model,
            route.profile,
            route.timeout_seconds,
            prompt_chars,
            context_tokens_estimate,
        )
        if route.fallback:
            return ContextAnswerResponse(
                answer=_fallback_answer_for_request(request, sections),
                materials=_materials_from_sections(sections),
                cautions=_cautions_from_request(request),
                next_checkpoints=_next_checkpoints_from_sections(
                    sections,
                    language=request.language,
                ),
                referenced_sections=[
                    ContextReferencedSection(
                        section_id=section.section_id,
                        title=section.title,
                        source_kind=section.source_kind,
                    )
                    for section in sections
                ],
                confidence=_confidence_from_request(request),
                safety_notes=[*_safety_notes_from_request(request), route.reason],
                provider=route.provider,
                model=route.model,
                profile=route.profile,
                elapsed_ms=0,
                gateway_status="fallback",
                fallback_reason=route.reason,
                request_id=request.request_id,
                timeout_sec=route.timeout_seconds,
                context_tokens_estimate=context_tokens_estimate,
                prompt_chars=prompt_chars,
                response_chars=0,
                tool_execution_ms=0,
                llm_generation_ms=0,
                total_elapsed_ms=_elapsed_ms(started),
                decision_support_note=(
                    _JA_DECISION_SUPPORT_NOTE
                    if request.language == "ja"
                    else _EN_DECISION_SUPPORT_NOTE
                ),
            )
        try:
            result = self.client.chat(
                messages,
                model=route.model,
                timeout_seconds=route.timeout_seconds,
                max_tokens=route.max_tokens,
            )
        except OllamaClientError as exc:
            total_elapsed_ms = _elapsed_ms(started)
            error_fallback_reason = (
                "local_conversation_fallback"
                if _is_llm_micro_request(request) and exc.code == "provider_timeout"
                else exc.code
            )
            LOGGER.warning(
                "[gateway.provider.result] request_id=%s status=error code=%s "
                "provider=%s model=%s profile=%s timeout_sec=%s elapsed_ms=%s",
                request.request_id,
                exc.code,
                exc.provider,
                route.model,
                route.profile,
                route.timeout_seconds,
                total_elapsed_ms,
            )
            return ContextAnswerResponse(
                answer=_fallback_answer_for_request(request, sections),
                materials=_materials_from_sections(sections),
                cautions=_cautions_from_request(request),
                next_checkpoints=_next_checkpoints_from_sections(
                    sections,
                    language=request.language,
                ),
                referenced_sections=[
                    ContextReferencedSection(
                        section_id=section.section_id,
                        title=section.title,
                        source_kind=section.source_kind,
                    )
                    for section in sections
                ],
                confidence=_confidence_from_request(request),
                safety_notes=[*_safety_notes_from_request(request), str(exc)],
                provider=exc.provider,
                model=route.model,
                profile=route.profile,
                elapsed_ms=total_elapsed_ms,
                gateway_status="fallback",
                fallback_reason=error_fallback_reason,
                request_id=request.request_id,
                timeout_sec=route.timeout_seconds,
                context_tokens_estimate=context_tokens_estimate,
                prompt_chars=prompt_chars,
                response_chars=0,
                tool_execution_ms=0,
                llm_generation_ms=total_elapsed_ms,
                total_elapsed_ms=total_elapsed_ms,
                decision_support_note=(
                    _JA_DECISION_SUPPORT_NOTE
                    if request.language == "ja"
                    else _EN_DECISION_SUPPORT_NOTE
                ),
            )
        radar_payload = (
            _parse_llm_radar_interpretation(result.answer)
            if _is_radar_interpretation_request(request)
            else None
        )
        radar_overview_payload = (
            _parse_llm_radar_overview_interpretation(result.answer)
            if _is_radar_overview_interpretation_request(request)
            else None
        )
        news_payload = (
            _parse_llm_news_interpretation(result.answer)
            if _is_news_interpretation_request(request)
            else None
        )
        ranking_payload = (
            _parse_llm_ranking_interpretation(result.answer)
            if _is_ranking_interpretation_request(request)
            else None
        )
        if _is_radar_interpretation_request(request):
            usable_payload = (
                _llm_payload_from_radar(radar_payload)
                if radar_payload is not None
                and _radar_payload_matches_request(radar_payload, request)
                else None
            )
        elif _is_radar_overview_interpretation_request(request):
            usable_payload = (
                _llm_payload_from_radar_overview(radar_overview_payload)
                if radar_overview_payload is not None
                and _radar_overview_payload_matches_request(radar_overview_payload, request)
                else None
            )
        elif _is_news_interpretation_request(request):
            usable_payload = (
                _llm_payload_from_news(news_payload)
                if news_payload is not None and _news_payload_matches_request(news_payload, request)
                else None
            )
        elif _is_ranking_interpretation_request(request):
            usable_payload = (
                _llm_payload_from_ranking(ranking_payload)
                if ranking_payload is not None
                and _ranking_payload_matches_request(ranking_payload, request)
                else None
            )
        else:
            llm_payload = _parse_llm_context_answer(result.answer)
            usable_payload = _usable_llm_payload(
                structured_payload=llm_payload,
                plain_answer=_strip_thinking_blocks(result.answer).strip(),
                request=request,
            )
        if usable_payload is None and not _is_structured_interpretation_request(request):
            try:
                repair_messages = _quality_repair_messages(messages)
                repair_result = self.client.chat(
                    repair_messages,
                    model=route.model,
                    timeout_seconds=route.timeout_seconds,
                    max_tokens=route.max_tokens,
                )
            except OllamaClientError:
                repair_result = None
            if repair_result is not None:
                repair_payload = _parse_llm_context_answer(repair_result.answer)
                usable_payload = _usable_llm_payload(
                    structured_payload=repair_payload,
                    plain_answer=_strip_thinking_blocks(repair_result.answer).strip(),
                    request=request,
                )
                if usable_payload is not None:
                    result = repair_result
        gateway_status: ContextAnswerGatewayStatus = (
            "ok" if usable_payload is not None else "fallback"
        )
        fallback_reason = None if usable_payload is not None else "response_validation_failure"
        answer = (
            usable_payload.answer
            if usable_payload is not None
            else _fallback_answer_for_request(request, sections)
        )
        total_elapsed_ms = _elapsed_ms(started)
        response_chars = result.response_chars if result.response_chars is not None else len(answer)
        LOGGER.info(
            "[gateway.provider.result] request_id=%s status=%s provider=%s model=%s "
            "profile=%s llm_generation_ms=%s total_elapsed_ms=%s response_chars=%s "
            "fallback_reason=%s",
            request.request_id,
            gateway_status,
            result.provider,
            result.model,
            route.profile,
            result.elapsed_ms,
            total_elapsed_ms,
            response_chars,
            fallback_reason,
        )
        return ContextAnswerResponse(
            answer=answer,
            materials=_bounded_non_empty(
                usable_payload.materials if usable_payload is not None else (),
                fallback=_materials_from_sections(sections),
                limit=8,
            ),
            cautions=_bounded_non_empty(
                usable_payload.cautions if usable_payload is not None else (),
                fallback=_cautions_from_request(request),
                limit=8,
            ),
            next_checkpoints=_bounded_non_empty(
                usable_payload.next_checkpoints if usable_payload is not None else (),
                fallback=_next_checkpoints_from_sections(sections, language=request.language),
                limit=6,
            ),
            referenced_sections=(
                _radar_referenced_sections(radar_payload, sections)
                if radar_payload is not None and usable_payload is not None
                else (
                    _radar_overview_referenced_sections(radar_overview_payload, sections)
                    if radar_overview_payload is not None and usable_payload is not None
                    else (
                        _news_referenced_sections(news_payload, sections)
                        if news_payload is not None and usable_payload is not None
                        else (
                            _ranking_referenced_sections(ranking_payload, sections)
                            if ranking_payload is not None and usable_payload is not None
                            else [
                                ContextReferencedSection(
                                    section_id=section.section_id,
                                    title=section.title,
                                    source_kind=section.source_kind,
                                )
                                for section in sections
                            ]
                        )
                    )
                )
            ),
            radar_interpretation=(
                radar_payload if radar_payload is not None and usable_payload is not None else None
            ),
            radar_overview_interpretation=(
                radar_overview_payload
                if radar_overview_payload is not None and usable_payload is not None
                else None
            ),
            news_interpretation=(
                news_payload if news_payload is not None and usable_payload is not None else None
            ),
            ranking_interpretation=(
                ranking_payload
                if ranking_payload is not None and usable_payload is not None
                else None
            ),
            confidence=(
                usable_payload.confidence
                if usable_payload is not None
                else _confidence_from_request(request)
            ),
            safety_notes=_safety_notes_from_request(request),
            provider=result.provider,
            model=result.model,
            profile=route.profile,
            elapsed_ms=result.elapsed_ms,
            gateway_status=gateway_status,
            fallback_reason=fallback_reason,
            request_id=request.request_id,
            timeout_sec=route.timeout_seconds,
            context_tokens_estimate=context_tokens_estimate,
            prompt_chars=result.prompt_chars if result.prompt_chars is not None else prompt_chars,
            response_chars=response_chars,
            tool_execution_ms=0,
            llm_generation_ms=result.elapsed_ms,
            total_elapsed_ms=total_elapsed_ms,
            decision_support_note=(
                _JA_DECISION_SUPPORT_NOTE if request.language == "ja" else _EN_DECISION_SUPPORT_NOTE
            ),
        )


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)


def _estimate_context_tokens(request: ContextAnswerRequest) -> int:
    if _is_llm_micro_request(request):
        return max(1, len(request.user_question.strip()) // 4)
    context_json = request.context.model_dump_json()
    return max(1, len(context_json) // 4)


def _is_llm_micro_request(request: ContextAnswerRequest) -> bool:
    return request.task_type in {
        "free_chat",
        "identity",
        "app_help",
        "capability_help",
        "screen_guidance",
    }


def _quality_repair_messages(messages: list[LlmMessage]) -> list[LlmMessage]:
    repair_instruction = (
        "前回の回答が短すぎる、または質問に直接答えていません。"
        "ユーザーの質問に直接答え、2～4文の自然な日本語で返してください。"
        "内部説明や技術情報は出さないでください。"
    )
    return [*messages, LlmMessage(role="user", content=repair_instruction)]


def _parse_llm_context_answer(answer: str) -> LlmContextAnswerPayload | None:
    raw_json = _extract_json_object(_strip_thinking_blocks(answer))
    if raw_json is None:
        return None
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return _coerce_llm_context_answer_payload_from_text(raw_json)
    try:
        return LlmContextAnswerPayload.model_validate(data)
    except ValidationError:
        return _coerce_llm_context_answer_payload(data)


def _parse_llm_radar_interpretation(answer: str) -> ContextRadarInterpretation | None:
    raw_json = _extract_json_object(_strip_thinking_blocks(answer))
    if raw_json is None:
        return None
    try:
        return ContextRadarInterpretation.model_validate_json(raw_json)
    except ValidationError:
        return None


def _is_radar_interpretation_request(request: ContextAnswerRequest) -> bool:
    return request.response_schema == RADAR_INTERPRETATION_RESPONSE_SCHEMA_VERSION


def _is_ranking_interpretation_request(request: ContextAnswerRequest) -> bool:
    return request.response_schema == RANKING_INTERPRETATION_RESPONSE_SCHEMA_VERSION


def _is_radar_overview_interpretation_request(request: ContextAnswerRequest) -> bool:
    return request.response_schema == RADAR_OVERVIEW_INTERPRETATION_RESPONSE_SCHEMA_VERSION


def _is_news_interpretation_request(request: ContextAnswerRequest) -> bool:
    return request.response_schema == NEWS_INTERPRETATION_RESPONSE_SCHEMA_VERSION


def _is_structured_interpretation_request(request: ContextAnswerRequest) -> bool:
    return (
        _is_radar_interpretation_request(request)
        or _is_radar_overview_interpretation_request(request)
        or _is_news_interpretation_request(request)
        or _is_ranking_interpretation_request(request)
    )


def _radar_payload_matches_request(
    payload: ContextRadarInterpretation,
    request: ContextAnswerRequest,
) -> bool:
    if payload.schema_version != RADAR_INTERPRETATION_RESPONSE_SCHEMA_VERSION:
        return False
    candidate_id = _radar_candidate_id(request)
    if not candidate_id or payload.candidate_id != candidate_id:
        return False
    allowed_ids = set(request.referenced_context_ids)
    cited_ids = _radar_cited_evidence_ids(payload)
    return bool(cited_ids) and set(cited_ids).issubset(allowed_ids)


def _radar_candidate_id(request: ContextAnswerRequest) -> str:
    for section in request.context.sections:
        if section.section_id != "radar_candidate":
            continue
        return str(section.summary.get("candidate_id") or "").strip()
    return ""


def _radar_cited_evidence_ids(payload: ContextRadarInterpretation) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    points = [
        payload.summary,
        *payload.positive_materials,
        *payload.cautions,
        *payload.unknowns,
        *payload.next_checkpoints,
    ]
    for point in points:
        for evidence_id in point.cited_evidence_ids:
            normalized = evidence_id.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
    return result


def _radar_referenced_sections(
    payload: ContextRadarInterpretation,
    sections: Sequence[ContextSection],
) -> list[ContextReferencedSection]:
    by_id = {section.section_id: section for section in sections}
    return [
        ContextReferencedSection(
            section_id=evidence_id,
            title=by_id[evidence_id].title,
            source_kind=by_id[evidence_id].source_kind,
        )
        for evidence_id in _radar_cited_evidence_ids(payload)
        if evidence_id in by_id
    ]


def _llm_payload_from_radar(
    payload: ContextRadarInterpretation,
) -> LlmContextAnswerPayload:
    return LlmContextAnswerPayload(
        answer=payload.summary.text,
        materials=[point.text for point in payload.positive_materials],
        cautions=[
            *(point.text for point in payload.cautions),
            *(point.text for point in payload.unknowns),
        ],
        next_checkpoints=[point.text for point in payload.next_checkpoints],
        confidence="low",
    )


def _parse_llm_radar_overview_interpretation(
    answer: str,
) -> ContextRadarOverviewInterpretation | None:
    raw_json = _extract_json_object(_strip_thinking_blocks(answer))
    if raw_json is None:
        return None
    try:
        return ContextRadarOverviewInterpretation.model_validate_json(raw_json)
    except ValidationError:
        return None


def _radar_overview_payload_matches_request(
    payload: ContextRadarOverviewInterpretation,
    request: ContextAnswerRequest,
) -> bool:
    if payload.schema_version != RADAR_OVERVIEW_INTERPRETATION_RESPONSE_SCHEMA_VERSION:
        return False
    return (
        _radar_overview_identity_matches(payload, request)
        and _radar_overview_sector_ids_match(payload, request)
        and _radar_overview_theme_ids_match(payload, request)
        and _radar_overview_candidate_ids_match(payload, request)
        and _radar_overview_citations_match(payload, request)
    )


def _radar_overview_identity_matches(
    payload: ContextRadarOverviewInterpretation,
    request: ContextAnswerRequest,
) -> bool:
    scope = next(
        (item for item in request.context.sections if item.section_id == "radar_scope"),
        None,
    )
    if scope is None:
        return False
    if payload.radar_context_id != str(scope.summary.get("radar_context_id") or "").strip():
        return False
    if payload.context_hash != str(scope.summary.get("context_hash") or "").strip():
        return False
    return True


def _radar_overview_sector_ids_match(
    payload: ContextRadarOverviewInterpretation,
    request: ContextAnswerRequest,
) -> bool:
    allowed_ids = [
        str(row.get("sector_id") or "").strip()
        for section in request.context.sections
        if section.section_id == "radar_sector_comparison"
        for row in section.rows
        if str(row.get("sector_id") or "").strip()
    ]
    payload_sector_ids = [item.sector_id for item in payload.sector_notes]
    if len(payload_sector_ids) != len(set(payload_sector_ids)):
        return False
    if set(payload_sector_ids) - set(allowed_ids):
        return False
    return _preserves_relative_order(payload_sector_ids, allowed_ids)


def _radar_overview_theme_ids_match(
    payload: ContextRadarOverviewInterpretation,
    request: ContextAnswerRequest,
) -> bool:
    theme_candidates = {
        str(section.summary.get("theme_id") or "").strip(): [
            item
            for item in str(section.summary.get("related_candidate_ids") or "").split(",")
            if item
        ]
        for section in request.context.sections
        if section.source_kind == "radar_news_theme"
    }
    payload_theme_ids = [item.theme_id for item in payload.theme_notes]
    if len(payload_theme_ids) != len(set(payload_theme_ids)):
        return False
    if not _preserves_relative_order(payload_theme_ids, list(theme_candidates)):
        return False
    for note in payload.theme_notes:
        if note.theme_id not in theme_candidates:
            return False
        allowed_related = theme_candidates[note.theme_id]
        if set(note.related_candidate_ids) - set(allowed_related):
            return False
        if not _preserves_relative_order(note.related_candidate_ids, allowed_related):
            return False
    return True


def _radar_overview_candidate_ids_match(
    payload: ContextRadarOverviewInterpretation,
    request: ContextAnswerRequest,
) -> bool:
    allowed_ids = [
        str(section.summary.get("candidate_id") or "").strip()
        for section in request.context.sections
        if section.source_kind == "radar_overview_candidate"
        if str(section.summary.get("candidate_id") or "").strip()
    ]
    payload_candidate_ids = [item.candidate_id for item in payload.deep_dive_hints]
    if len(payload_candidate_ids) != len(set(payload_candidate_ids)):
        return False
    if set(payload_candidate_ids) - set(allowed_ids):
        return False
    return _preserves_relative_order(payload_candidate_ids, allowed_ids)


def _radar_overview_citations_match(
    payload: ContextRadarOverviewInterpretation,
    request: ContextAnswerRequest,
) -> bool:
    market = next(
        (item for item in request.context.sections if item.section_id == "radar_market_breadth"),
        None,
    )
    market_state = str(market.summary.get("market_state") or "missing") if market else "missing"
    if market_state in {"missing", "stale"} and payload.candidate_set_movement is not None:
        return False
    if "radar_scope" not in payload.summary.cited_evidence_ids:
        return False
    if (
        payload.candidate_set_movement is not None
        and "radar_market_breadth" not in payload.candidate_set_movement.cited_evidence_ids
    ):
        return False
    if any(
        "radar_sector_comparison" not in note.reading.cited_evidence_ids
        for note in payload.sector_notes
    ):
        return False
    if any(note.theme_id not in note.reading.cited_evidence_ids for note in payload.theme_notes):
        return False
    if any(
        note.candidate_id not in note.reason.cited_evidence_ids for note in payload.deep_dive_hints
    ):
        return False
    cited_ids = _radar_overview_cited_evidence_ids(payload)
    return bool(cited_ids) and set(cited_ids).issubset(set(request.referenced_context_ids))


def _radar_overview_cited_evidence_ids(
    payload: ContextRadarOverviewInterpretation,
) -> list[str]:
    points = [
        payload.summary,
        *([payload.candidate_set_movement] if payload.candidate_set_movement is not None else []),
        *[item.reading for item in payload.sector_notes],
        *[item.reading for item in payload.theme_notes],
        *[item.reason for item in payload.deep_dive_hints],
        *payload.unknowns,
        *payload.next_checkpoints,
    ]
    return _dedupe_non_empty(
        [evidence_id for point in points for evidence_id in point.cited_evidence_ids]
    )


def _radar_overview_referenced_sections(
    payload: ContextRadarOverviewInterpretation,
    sections: Sequence[ContextSection],
) -> list[ContextReferencedSection]:
    by_id = {section.section_id: section for section in sections}
    return [
        ContextReferencedSection(
            section_id=evidence_id,
            title=by_id[evidence_id].title,
            source_kind=by_id[evidence_id].source_kind,
        )
        for evidence_id in _radar_overview_cited_evidence_ids(payload)
        if evidence_id in by_id
    ]


def _llm_payload_from_radar_overview(
    payload: ContextRadarOverviewInterpretation,
) -> LlmContextAnswerPayload:
    return LlmContextAnswerPayload(
        answer=payload.summary.text,
        materials=[
            *(
                [payload.candidate_set_movement.text]
                if payload.candidate_set_movement is not None
                else []
            ),
            *(item.reading.text for item in payload.sector_notes),
            *(item.reading.text for item in payload.theme_notes),
        ],
        cautions=[item.text for item in payload.unknowns],
        next_checkpoints=[
            *(item.reason.text for item in payload.deep_dive_hints),
            *(item.text for item in payload.next_checkpoints),
        ],
        confidence="low",
    )


def _parse_llm_news_interpretation(answer: str) -> ContextNewsInterpretation | None:
    raw_json = _extract_json_object(_strip_thinking_blocks(answer))
    if raw_json is None:
        return None
    try:
        return ContextNewsInterpretation.model_validate_json(raw_json)
    except ValidationError:
        return None


def _news_payload_matches_request(
    payload: ContextNewsInterpretation, request: ContextAnswerRequest
) -> bool:
    if payload.schema_version != NEWS_INTERPRETATION_RESPONSE_SCHEMA_VERSION:
        return False
    scope = next(
        (item for item in request.context.sections if item.section_id == "news_scope"), None
    )
    if scope is None:
        return False
    if payload.news_context_id != str(scope.summary.get("news_context_id") or "").strip():
        return False
    if payload.context_hash != str(scope.summary.get("context_hash") or "").strip():
        return False
    material_sections = [
        item for item in request.context.sections if item.source_kind == "news_material_group"
    ]
    allowed_materials = [item.section_id for item in material_sections]
    payload_materials = [item.material_id for item in payload.material_notes]
    if len(payload_materials) != len(set(payload_materials)) or not _preserves_relative_order(
        payload_materials, allowed_materials
    ):
        return False
    material_sectors = {
        item.section_id: [
            value for value in str(item.summary.get("related_sector_ids") or "").split(",") if value
        ]
        for item in material_sections
    }
    if any(
        set(item.related_sector_ids) - set(material_sectors.get(item.material_id, []))
        for item in payload.material_notes
    ):
        return False
    sector_ids = [
        str(row.get("sector_id") or "").strip()
        for section in request.context.sections
        if section.section_id == "news_sector_relations"
        for row in section.rows
        if str(row.get("sector_id") or "").strip()
    ]
    payload_sectors = [item.sector_id for item in payload.sector_notes]
    if len(payload_sectors) != len(set(payload_sectors)) or not _preserves_relative_order(
        payload_sectors, sector_ids
    ):
        return False
    candidate_ids = [
        str(row.get("candidate_id") or "").strip()
        for section in request.context.sections
        if section.section_id == "news_cockpit_handoffs"
        for row in section.rows
        if str(row.get("candidate_id") or "").strip()
    ]
    if [item.candidate_id for item in payload.handoff_hints] != candidate_ids:
        return False
    if "news_scope" not in payload.summary.cited_evidence_ids:
        return False
    if any(
        item.material_id not in item.reading.cited_evidence_ids for item in payload.material_notes
    ):
        return False
    if any(
        item.uncertainty is not None and item.material_id not in item.uncertainty.cited_evidence_ids
        for item in payload.material_notes
    ):
        return False
    if any(
        "news_sector_relations" not in item.reading.cited_evidence_ids
        for item in payload.sector_notes
    ):
        return False
    if any("news_source_quality" not in item.cited_evidence_ids for item in payload.noise_notes):
        return False
    if any(
        "news_cockpit_handoffs" not in item.reason.cited_evidence_ids
        for item in payload.handoff_hints
    ):
        return False
    cited = _news_cited_evidence_ids(payload)
    return bool(cited) and set(cited).issubset(set(request.referenced_context_ids))


def _news_cited_evidence_ids(payload: ContextNewsInterpretation) -> list[str]:
    points = [
        payload.summary,
        *[item.reading for item in payload.material_notes],
        *[item.uncertainty for item in payload.material_notes if item.uncertainty is not None],
        *[item.reading for item in payload.sector_notes],
        *payload.noise_notes,
        *[item.reason for item in payload.handoff_hints],
        *payload.unknowns,
        *payload.next_checkpoints,
    ]
    return _dedupe_non_empty(
        [evidence_id for point in points for evidence_id in point.cited_evidence_ids]
    )


def _news_referenced_sections(
    payload: ContextNewsInterpretation, sections: Sequence[ContextSection]
) -> list[ContextReferencedSection]:
    by_id = {section.section_id: section for section in sections}
    return [
        ContextReferencedSection(
            section_id=item, title=by_id[item].title, source_kind=by_id[item].source_kind
        )
        for item in _news_cited_evidence_ids(payload)
        if item in by_id
    ]


def _llm_payload_from_news(payload: ContextNewsInterpretation) -> LlmContextAnswerPayload:
    return LlmContextAnswerPayload(
        answer=payload.summary.text,
        materials=[item.reading.text for item in payload.material_notes]
        + [item.reading.text for item in payload.sector_notes],
        cautions=[item.text for item in payload.noise_notes]
        + [item.text for item in payload.unknowns],
        next_checkpoints=[item.reason.text for item in payload.handoff_hints]
        + [item.text for item in payload.next_checkpoints],
        confidence="low",
    )


def _preserves_relative_order(values: list[str], allowed_values: list[str]) -> bool:
    selected = set(values)
    return values == [item for item in allowed_values if item in selected]


def _parse_llm_ranking_interpretation(answer: str) -> ContextRankingInterpretation | None:
    raw_json = _extract_json_object(_strip_thinking_blocks(answer))
    if raw_json is None:
        return None
    try:
        return ContextRankingInterpretation.model_validate_json(raw_json)
    except ValidationError:
        return None


def _ranking_payload_matches_request(
    payload: ContextRankingInterpretation,
    request: ContextAnswerRequest,
) -> bool:
    if payload.schema_version != RANKING_INTERPRETATION_RESPONSE_SCHEMA_VERSION:
        return False
    if payload.ranking_context_id != _ranking_context_id(request):
        return False
    payload_candidate_ids = [note.candidate_id for note in payload.candidate_notes]
    if payload_candidate_ids != _ranking_candidate_ids(request):
        return False
    cited_ids = _ranking_cited_evidence_ids(payload)
    return bool(cited_ids) and set(cited_ids).issubset(set(request.referenced_context_ids))


def _ranking_context_id(request: ContextAnswerRequest) -> str:
    for section in request.context.sections:
        if section.section_id == "ranking_scope":
            return str(section.summary.get("ranking_context_id") or "").strip()
    return ""


def _ranking_candidate_ids(request: ContextAnswerRequest) -> list[str]:
    return [
        candidate_id
        for section in request.context.sections
        if section.source_kind == "ranking_candidate"
        if (candidate_id := str(section.summary.get("candidate_id") or "").strip())
    ]


def _ranking_cited_evidence_ids(payload: ContextRankingInterpretation) -> list[str]:
    points = [
        payload.summary,
        *payload.common_strengths,
        *payload.common_cautions,
        *payload.metric_notes,
        *payload.sector_notes,
        *payload.next_checkpoints,
        *(
            point
            for note in payload.candidate_notes
            for point in [
                note.reading,
                *([note.caution] if note.caution is not None else []),
                note.next_check,
            ]
        ),
    ]
    return _dedupe_non_empty(
        [evidence_id for point in points for evidence_id in point.cited_evidence_ids]
    )


def _ranking_referenced_sections(
    payload: ContextRankingInterpretation,
    sections: Sequence[ContextSection],
) -> list[ContextReferencedSection]:
    by_id = {section.section_id: section for section in sections}
    return [
        ContextReferencedSection(
            section_id=evidence_id,
            title=by_id[evidence_id].title,
            source_kind=by_id[evidence_id].source_kind,
        )
        for evidence_id in _ranking_cited_evidence_ids(payload)
        if evidence_id in by_id
    ]


def _llm_payload_from_ranking(
    payload: ContextRankingInterpretation,
) -> LlmContextAnswerPayload:
    candidate_cautions = [
        note.caution.text for note in payload.candidate_notes if note.caution is not None
    ]
    return LlmContextAnswerPayload(
        answer=payload.summary.text,
        materials=[
            *(point.text for point in payload.common_strengths),
            *(point.text for point in payload.metric_notes),
            *(point.text for point in payload.sector_notes),
        ],
        cautions=[*(point.text for point in payload.common_cautions), *candidate_cautions],
        next_checkpoints=[
            *(point.text for point in payload.next_checkpoints),
            *(note.next_check.text for note in payload.candidate_notes),
        ],
        confidence="low",
    )


def _coerce_llm_context_answer_payload(data: object) -> LlmContextAnswerPayload | None:
    if not isinstance(data, dict):
        return None
    answer = _first_text(data, "answer", "response", "summary", "回答", "返答")
    if not answer:
        return None
    confidence = str(data.get("confidence") or data.get("確信度") or "low").strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"
    return LlmContextAnswerPayload(
        answer=answer,
        materials=_string_list_from_value(data.get("materials") or data.get("見る材料")),
        cautions=_string_list_from_value(data.get("cautions") or data.get("注意点")),
        next_checkpoints=_string_list_from_value(
            data.get("next_checkpoints") or data.get("次に確認")
        ),
        confidence=confidence,  # type: ignore[arg-type]
    )


def _coerce_llm_context_answer_payload_from_text(text: str) -> LlmContextAnswerPayload | None:
    match = re.search(r'"(?:answer|回答)"\s*:\s*"((?:\\.|[^"\\])*)"', text)
    if match is None:
        return None
    try:
        answer = json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        answer = match.group(1)
    answer = str(answer).strip()
    if not answer:
        return None
    return LlmContextAnswerPayload(answer=answer, confidence="low")


def _coerce_answer_label_payload_from_text(text: str) -> LlmContextAnswerPayload | None:
    match = re.search(r'answer\s*:\s*"([^"]+)"', text, flags=re.IGNORECASE)
    if match is None:
        return None
    answer = match.group(1).strip()
    if not answer:
        return None
    return LlmContextAnswerPayload(answer=answer, confidence="low")


def _first_text(data: dict[object, object], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _string_list_from_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _usable_llm_payload(
    *,
    structured_payload: LlmContextAnswerPayload | None,
    plain_answer: str,
    request: ContextAnswerRequest,
) -> LlmContextAnswerPayload | None:
    if structured_payload is not None and not _is_low_quality_payload(
        structured_payload,
        request=request,
    ):
        return LlmContextAnswerPayload(
            answer=structured_payload.answer,
            materials=_drop_low_quality_items(structured_payload.materials),
            cautions=_drop_low_quality_items(structured_payload.cautions),
            next_checkpoints=_drop_low_quality_items(structured_payload.next_checkpoints),
            confidence=structured_payload.confidence,
        )
    text_payload = _coerce_answer_label_payload_from_text(
        plain_answer
    ) or _coerce_llm_context_answer_payload_from_text(plain_answer)
    if text_payload is not None and not _is_low_quality_payload(text_payload, request=request):
        return text_payload
    if plain_answer.lstrip().startswith("{") or plain_answer.lstrip().startswith("```"):
        return None
    if plain_answer and not _is_low_quality_text(plain_answer, request=request):
        return LlmContextAnswerPayload(answer=plain_answer, confidence="low")
    return None


def _strip_thinking_blocks(text: str) -> str:
    normalized = text.strip()
    while "<think>" in normalized and "</think>" in normalized:
        start = normalized.find("<think>")
        end = normalized.find("</think>", start)
        if end < start:
            break
        normalized = (normalized[:start] + normalized[end + len("</think>") :]).strip()
    if "</think>" in normalized:
        normalized = normalized.split("</think>")[-1].strip()
    return normalized


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


def _is_low_quality_payload(
    payload: LlmContextAnswerPayload,
    *,
    request: ContextAnswerRequest,
) -> bool:
    return _is_low_quality_text(payload.answer, request=request)


def _drop_low_quality_items(values: list[str]) -> list[str]:
    return [value for value in values if not _is_low_quality_text(value)]


def _is_low_quality_text(text: str, *, request: ContextAnswerRequest | None = None) -> bool:
    joined = str(text or "")
    if "????" in joined or "�" in joined:
        return True
    lowered = joined.lower().lstrip()
    if any(marker in lowered for marker in _FORBIDDEN_PRESENTATION_PATTERNS):
        return True
    reasoning_markers = (
        "<think>",
        "</think>",
        "first, i need",
        "i need to",
        "i should",
        "the answer should",
        "the tool says",
        "we are given",
        "steps:",
        "we must return a json",
        "final decision:",
        "let me",
    )
    if any(marker in lowered for marker in reasoning_markers):
        return True
    mojibake_markers = ("ã", "æ", "é", "縺", "繧", "荳", "譁")
    if any(marker in joined for marker in mojibake_markers):
        return True
    if request is None or not _is_llm_micro_request(request):
        return False
    compact = re.sub(r"\s+", "", joined)
    weak_phrases = (
        "整理します",
        "確認材料を整理します",
        "SMAIで確認する観点を整理します",
        "分かる範囲で短く整理します",
    )
    if len(compact) < 40:
        return True
    if any(phrase in joined for phrase in weak_phrases) and len(compact) < 70:
        return True
    if _is_identity_question(request.user_question) and "SMAIナビ" not in joined:
        return True
    return False


def _fallback_answer_for_request(
    request: ContextAnswerRequest,
    sections: list[ContextSection],
) -> str:
    if _is_llm_micro_request(request):
        return _llm_micro_fallback_answer(request)
    return _fallback_answer_from_sections(sections, language=request.language)


def _llm_micro_fallback_answer(request: ContextAnswerRequest) -> str:
    question = str(request.user_question or "").strip()
    if request.language != "ja":
        if request.task_type == "identity":
            return (
                "I am SMAI Navi. I help organize Smart Market AI screens, symbol checks, "
                "AI forecasts, news, evidence, and next checkpoints."
            )
        if request.task_type == "capability_help":
            return (
                "SMAI Navi can help with SMAI usage, symbol review order, forecast and risk "
                "comparison, news material sorting, and Decision Report preparation."
            )
        if request.task_type == "app_help":
            return (
                "SMAI is easiest to use by purpose. Use the symbol cockpit for a single "
                "symbol, rankings to find candidates, and the investment radar to review "
                "broader market materials."
            )
        if _is_simple_greeting(question):
            return (
                "Hello, I am SMAI Navi. I can help organize SMAI screens, "
                "review materials, cautions, and next checks."
            )
        if _is_identity_question(question):
            return (
                "I am SMAI Navi. I help organize Smart Market AI screens, symbols, "
                "AI forecasts, news, evidence, and next checkpoints."
            )
        return (
            "I can organize this as SMAI review support. Separate the visible "
            "price, forecast, news, evidence, and missing checks before treating it as a decision input."
        )
    if request.task_type == "identity" or _is_identity_question(question):
        return (
            "私はSMAIナビです。"
            "Smart Market AIの中で、銘柄の見方やAI予測、ニュース、根拠資料の整理をお手伝いします。"
        )
    if request.task_type == "capability_help" or _is_capability_question(question):
        return (
            "SMAIナビでは、SMAIの使い方、銘柄の確認順、AI予測とリスクの見比べ方、"
            "ニュース材料の整理をお手伝いできます。"
            "迷ったときは「この銘柄で最初に見る材料は？」のように聞いてください。"
        )
    if request.task_type == "app_help":
        return (
            "SMAIは、目的別に画面を使い分けると分かりやすいです。"
            "銘柄を深掘りするなら「銘柄コックピット」、候補を探すなら「銘柄ランキング」、"
            "市場全体を見るなら「投資レーダー」を使います。"
            "迷ったら、気になる銘柄名を入れて「何を見ればいい？」と聞いてください。"
        )
    if _is_simple_greeting(question):
        return (
            "こんにちは。SMAIナビです。SMAIの使い方、銘柄の確認材料、"
            "AI予測やニュースの見方を短く整理できます。"
        )
    if question:
        return (
            f"「{question[:40]}」について、SMAIで確認する観点を整理します。"
            "価格・AI予測・ニュース・根拠資料を分けて見て、最後に不足している材料を確認すると判断しやすいです。"
        )
    return "SMAIで確認したいことを送ってください。見ている材料、注意点、次に確認することの順に整理します。"


def _is_identity_question(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "あなたの名前",
            "あなたのなまえ",
            "あなたは誰",
            "あなたはだれ",
            "君の名前",
            "君は誰",
            "名前は",
            "名前を教えて",
            "お名前",
            "なまえ",
            "だれ",
            "誰",
            "who are you",
            "your name",
        )
    )


def _is_capability_question(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "何ができる",
            "なにができる",
            "できること",
            "何を相談",
            "何を聞ける",
            "どう使える",
            "どんなことができる",
            "help",
            "capability",
        )
    )


def _is_simple_greeting(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return normalized in {"こんにちは", "こんばんは", "おはよう", "hello", "hi"} or any(
        normalized.startswith(prefix)
        for prefix in (
            "こんにちは。",
            "こんにちは、",
            "こんばんは。",
            "こんばんは、",
            "hello ",
            "hi ",
        )
    )


def _fallback_answer_from_sections(
    sections: list[ContextSection],
    *,
    language: str,
) -> str:
    if not sections:
        return (
            "画面の材料が不足しています。まず表示中のデータ、注意点、根拠資料を確認してください。"
            if language == "ja"
            else "The screen context is insufficient. Check the visible data, cautions, and evidence first."
        )
    section = sections[0]
    fields = _dedupe_non_empty([section.title, *section.included_fields, *section.summary.keys()])
    if language == "ja":
        if fields:
            return f"{section.title}では、{_join_ja(fields[:4])}をまず確認します。注意点と根拠資料も同じ画面で見てください。"
        return f"{section.title}の表示内容、注意点、次に確認することを順に確認します。"
    if fields:
        return f"First check {_join_en(fields[:4])} in {section.title}, then review cautions and evidence on the same screen."
    return f"Review the visible values, cautions, and next checks in {section.title}."


def _join_ja(values: list[str]) -> str:
    if len(values) <= 1:
        return values[0] if values else ""
    return "、".join(values[:-1]) + "、" + values[-1]


def _join_en(values: list[str]) -> str:
    if len(values) <= 1:
        return values[0] if values else ""
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _bounded_non_empty(
    values: Sequence[str],
    *,
    fallback: list[str],
    limit: int,
) -> list[str]:
    bounded = _dedupe_non_empty([str(value) for value in values])[:limit]
    return bounded or fallback[:limit]


def _selected_sections(request: ContextAnswerRequest) -> list[ContextSection]:
    limit = (
        8
        if _is_ranking_interpretation_request(request)
        or _is_radar_overview_interpretation_request(request)
        or _is_news_interpretation_request(request)
        else 4
    )
    ids = set(request.referenced_context_ids)
    if request.active_context_id:
        ids.add(request.active_context_id)
    if request.context.active_context_id:
        ids.add(request.context.active_context_id)
    if ids:
        selected = [section for section in request.context.sections if section.section_id in ids]
        if selected:
            return selected[:limit]
    return request.context.sections[:limit]


def _materials_from_sections(sections: list[ContextSection]) -> list[str]:
    materials: list[str] = []
    for section in sections:
        materials.append(section.title)
        materials.extend(section.included_fields[:4])
        materials.extend(list(section.summary.keys())[:4])
    return _dedupe_non_empty(materials)[:8]


def _cautions_from_request(request: ContextAnswerRequest) -> list[str]:
    cautions: list[str] = []
    for section in _selected_sections(request):
        cautions.extend(section.warnings[:4])
    if request.constraints.no_investment_advice:
        cautions.append(
            "投資助言ではなく、確認材料の整理として扱ってください。"
            if request.language == "ja"
            else "Treat this as decision-support context, not investment advice."
        )
    return _dedupe_non_empty(cautions)[:8]


def _next_checkpoints_from_sections(
    sections: list[ContextSection],
    *,
    language: str,
) -> list[str]:
    checkpoints: list[str] = []
    for section in sections:
        checkpoints.extend(section.notes[:4])
    if checkpoints:
        return _dedupe_non_empty(checkpoints)[:6]
    if language == "ja":
        return [
            "根拠資料、データ品質、注意点を同じ画面で確認してください。",
        ]
    return [
        "Check source evidence, data quality, and cautions in the same screen.",
    ]


def _safety_notes_from_request(request: ContextAnswerRequest) -> list[str]:
    notes: list[str] = []
    constraints = request.constraints
    if constraints.do_not_change_scores:
        notes.append(
            "スコア、予測値、ランキング順位は変更していません。"
            if request.language == "ja"
            else "Scores, forecasts, and rankings were not changed."
        )
    if constraints.do_not_rank_symbols:
        notes.append(
            "銘柄の売買判断や順位決定は行いません。"
            if request.language == "ja"
            else "No buy/sell decision or symbol ranking was performed."
        )
    return _dedupe_non_empty(notes)


def _confidence_from_request(request: ContextAnswerRequest) -> ContextAnswerConfidence:
    sections = _selected_sections(request)
    warning_count = sum(len(section.warnings) for section in sections)
    redacted_count = sum(len(section.redacted_fields) for section in sections)
    has_summary = any(section.summary or section.rows for section in sections)
    if not has_summary:
        return "low"
    if warning_count >= 3 or redacted_count >= 3:
        return "low"
    if warning_count or redacted_count:
        return "medium"
    return "medium"


def _dedupe_non_empty(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
