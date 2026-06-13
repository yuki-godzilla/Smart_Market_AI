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
        messages = self.prompt_service.build_context_answer_messages(request)
        result = self.client.chat(messages, model=request.model)
        sections = _selected_sections(request)
        llm_payload = _parse_llm_context_answer(result.answer)
        return ContextAnswerResponse(
            answer=llm_payload.answer if llm_payload else result.answer,
            materials=_bounded_non_empty(
                llm_payload.materials if llm_payload else (),
                fallback=_materials_from_sections(sections),
                limit=8,
            ),
            cautions=_bounded_non_empty(
                llm_payload.cautions if llm_payload else (),
                fallback=_cautions_from_request(request),
                limit=8,
            ),
            next_checkpoints=_bounded_non_empty(
                llm_payload.next_checkpoints if llm_payload else (),
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
            confidence=llm_payload.confidence if llm_payload else _confidence_from_request(request),
            safety_notes=_safety_notes_from_request(request),
            provider=result.provider,
            model=result.model,
            elapsed_ms=result.elapsed_ms,
            decision_support_note=(
                _JA_DECISION_SUPPORT_NOTE if request.language == "ja" else _EN_DECISION_SUPPORT_NOTE
            ),
        )


def _parse_llm_context_answer(answer: str) -> LlmContextAnswerPayload | None:
    raw_json = _extract_json_object(answer)
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
