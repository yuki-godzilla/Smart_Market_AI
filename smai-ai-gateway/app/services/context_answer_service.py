from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import Field, ValidationError

from app.clients.ollama_client import OllamaClient
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
        route = resolve_model_route(
            settings=self.client.settings,
            task_type=request.task_type,
            execution_mode=request.execution_mode,
            environment_profile=request.environment_profile,
            preferred_profile=request.preferred_profile,
            requested_model=request.model,
        )
        messages = self.prompt_service.build_context_answer_messages(request)
        sections = _selected_sections(request)
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
                decision_support_note=(
                    _JA_DECISION_SUPPORT_NOTE
                    if request.language == "ja"
                    else _EN_DECISION_SUPPORT_NOTE
                ),
            )
        result = self.client.chat(
            messages,
            model=route.model,
            timeout_seconds=route.timeout_seconds,
            max_tokens=route.max_tokens,
        )
        llm_payload = _parse_llm_context_answer(result.answer)
        usable_payload = (
            llm_payload
            if llm_payload is not None and not _is_low_quality_payload(llm_payload)
            else None
        )
        return ContextAnswerResponse(
            answer=(
                usable_payload.answer
                if usable_payload is not None
                else _fallback_answer_from_sections(sections, language=request.language)
            ),
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
            decision_support_note=(
                _JA_DECISION_SUPPORT_NOTE if request.language == "ja" else _EN_DECISION_SUPPORT_NOTE
            ),
        )


def _parse_llm_context_answer(answer: str) -> LlmContextAnswerPayload | None:
    raw_json = _extract_json_object(_strip_thinking_blocks(answer))
    if raw_json is None:
        return None
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    try:
        return LlmContextAnswerPayload.model_validate(data)
    except ValidationError:
        return None


def _strip_thinking_blocks(text: str) -> str:
    normalized = text.strip()
    while "<think>" in normalized and "</think>" in normalized:
        start = normalized.find("<think>")
        end = normalized.find("</think>", start)
        if end < start:
            break
        normalized = (normalized[:start] + normalized[end + len("</think>") :]).strip()
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
    values = [
        payload.answer,
        *payload.materials,
        *payload.cautions,
        *payload.next_checkpoints,
    ]
    joined = "\n".join(values)
    if "????" in joined or "�" in joined:
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
