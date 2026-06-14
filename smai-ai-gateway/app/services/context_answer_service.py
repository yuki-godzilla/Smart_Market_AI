from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from time import perf_counter

from pydantic import Field, ValidationError

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.schemas.common import GatewayBaseModel
from app.schemas.context_answer import (
    ContextAnswerConfidence,
    ContextAnswerRequest,
    ContextAnswerResponse,
    ContextReferencedSection,
    ContextSection,
)
from app.services.model_router import resolve_model_route
from app.services.prompt_service import PromptService

_JA_DECISION_SUPPORT_NOTE = "この回答は判断材料の整理であり、投資助言ではありません。"
_EN_DECISION_SUPPORT_NOTE = "This response is decision-support context, not investment advice."
LOGGER = logging.getLogger(__name__)


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
        sections = _selected_sections(request)
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
                answer=_fallback_answer_from_sections(sections, language=request.language),
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
                answer=_fallback_answer_from_sections(sections, language=request.language),
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
                fallback_reason=exc.code,
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
        llm_payload = _parse_llm_context_answer(result.answer)
        usable_payload = _usable_llm_payload(
            structured_payload=llm_payload,
            plain_answer=_strip_thinking_blocks(result.answer).strip(),
        )
        gateway_status = "ok" if usable_payload is not None else "fallback"
        fallback_reason = None if usable_payload is not None else "response_validation_failure"
        answer = (
            usable_payload.answer
            if usable_payload is not None
            else _fallback_answer_from_sections(sections, language=request.language)
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
            referenced_sections=[
                ContextReferencedSection(
                    section_id=section.section_id,
                    title=section.title,
                    source_kind=section.source_kind,
                )
                for section in sections
            ],
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
    context_json = request.context.model_dump_json()
    return max(1, len(context_json) // 4)


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
) -> LlmContextAnswerPayload | None:
    if structured_payload is not None and not _is_low_quality_payload(structured_payload):
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
    if text_payload is not None and not _is_low_quality_payload(text_payload):
        return text_payload
    if plain_answer.lstrip().startswith("{") or plain_answer.lstrip().startswith("```"):
        return None
    if plain_answer and not _is_low_quality_text(plain_answer):
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


def _is_low_quality_payload(payload: LlmContextAnswerPayload) -> bool:
    return _is_low_quality_text(payload.answer)


def _drop_low_quality_items(values: list[str]) -> list[str]:
    return [value for value in values if not _is_low_quality_text(value)]


def _is_low_quality_text(text: str) -> bool:
    joined = str(text or "")
    if "????" in joined or "�" in joined:
        return True
    lowered = joined.lower().lstrip()
    reasoning_markers = (
        "we are given",
        "steps:",
        "we must return a json",
        "final decision:",
        "let me",
    )
    if any(marker in lowered for marker in reasoning_markers):
        return True
    mojibake_markers = ("ã", "æ", "é", "縺", "繧", "荳", "譁")
    return any(marker in joined for marker in mojibake_markers)


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
    ids = set(request.referenced_context_ids)
    if request.active_context_id:
        ids.add(request.active_context_id)
    if request.context.active_context_id:
        ids.add(request.context.active_context_id)
    if ids:
        selected = [section for section in request.context.sections if section.section_id in ids]
        if selected:
            return selected[:4]
    return request.context.sections[:4]


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
        if section.redacted_fields:
            cautions.append(f"{section.title}: some raw or sensitive fields were excluded.")
    cautions.extend(request.context.privacy_notes[:4])
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
