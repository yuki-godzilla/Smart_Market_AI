from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field

from app.schemas.common import GatewayBaseModel
from app.services.model_router import (
    LlmEnvironmentProfile,
    LlmExecutionMode,
    LlmProfileName,
    LlmTaskType,
)

CONTEXT_ANSWER_RESPONSE_SCHEMA_VERSION = "assistant-gateway-response-v1"
RADAR_INTERPRETATION_RESPONSE_SCHEMA_VERSION = "radar_interpretation.v1"
RADAR_OVERVIEW_INTERPRETATION_RESPONSE_SCHEMA_VERSION = "radar_overview_interpretation.v1"
RANKING_INTERPRETATION_RESPONSE_SCHEMA_VERSION = "ranking_interpretation.v1"

ContextAnswerTask = Literal["explain", "summarize", "compare", "next_steps", "chat"]
ContextAnswerLanguage = Literal["ja", "en"]
ContextAnswerConfidence = Literal["low", "medium", "high"]
ContextAnswerGatewayStatus = Literal["ok", "fallback"]


class ContextSection(GatewayBaseModel):
    """Safe section context supplied by a client application."""

    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    summary: dict[str, str] = Field(default_factory=dict)
    rows: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    included_fields: list[str] = Field(default_factory=list)
    redacted_fields: list[str] = Field(default_factory=list)


class ContextBundle(GatewayBaseModel):
    """Generic context bundle for context-grounded answers."""

    schema_version: str = Field(default="context-bundle-v1", min_length=1)
    bundle_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(default="manual", min_length=1)
    created_at: datetime | None = None
    language: ContextAnswerLanguage = "ja"
    active_context_id: str | None = Field(default=None, min_length=1)
    sections: list[ContextSection] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    privacy_notes: list[str] = Field(default_factory=list)
    decision_support_note: str | None = Field(default=None, min_length=1)


class ContextAnswerConstraints(GatewayBaseModel):
    """Safety and output constraints requested by the client application."""

    no_investment_advice: bool = True
    do_not_change_scores: bool = True
    do_not_rank_symbols: bool = True
    answer_format: str = Field(default="materials_cautions_checkpoints", min_length=1)
    require_referenced_sections: bool = True


class ContextAnswerMessage(GatewayBaseModel):
    """Optional prior chat message supplied by a client application."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ContextAnswerRequest(GatewayBaseModel):
    """Request for a grounded answer over a supplied context bundle."""

    schema_version: str = Field(default="context-answer-request-v1", min_length=1)
    task: ContextAnswerTask = "explain"
    language: ContextAnswerLanguage = "ja"
    user_question: str = Field(min_length=1)
    context: ContextBundle
    constraints: ContextAnswerConstraints = Field(default_factory=ContextAnswerConstraints)
    conversation_id: str | None = Field(default=None, min_length=1)
    message_history: list[ContextAnswerMessage] = Field(default_factory=list)
    active_context_id: str | None = Field(default=None, min_length=1)
    referenced_context_ids: list[str] = Field(default_factory=list)
    response_schema: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    profile: LlmProfileName | None = None
    task_type: LlmTaskType = "free_chat"
    execution_mode: LlmExecutionMode = "auto"
    environment_profile: LlmEnvironmentProfile = "notebook"
    preferred_profile: LlmProfileName | None = None
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)


class ContextReferencedSection(GatewayBaseModel):
    """Reference back to a section from the supplied context bundle."""

    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)


class ContextEvidencePoint(GatewayBaseModel):
    """One short Radar field tied to exact evidence section IDs."""

    text: str = Field(min_length=1, max_length=320)
    cited_evidence_ids: list[str] = Field(min_length=1, max_length=5)


class ContextRadarInterpretation(GatewayBaseModel):
    """Optional evidence-bound Radar interpretation payload."""

    schema_version: str = Field(
        default=RADAR_INTERPRETATION_RESPONSE_SCHEMA_VERSION,
        min_length=1,
    )
    candidate_id: str = Field(min_length=1)
    summary: ContextEvidencePoint
    positive_materials: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)
    cautions: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)
    unknowns: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)
    next_checkpoints: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)


class ContextRankingCandidateNote(GatewayBaseModel):
    """One evidence-bound explanation for an already-ranked candidate."""

    candidate_id: str = Field(min_length=1)
    reading: ContextEvidencePoint
    caution: ContextEvidencePoint | None = None
    next_check: ContextEvidencePoint


class ContextRadarOverviewSectorNote(GatewayBaseModel):
    sector_id: str = Field(min_length=1)
    reading: ContextEvidencePoint


class ContextRadarOverviewThemeNote(GatewayBaseModel):
    theme_id: str = Field(min_length=1)
    related_candidate_ids: list[str] = Field(default_factory=list, max_length=3)
    reading: ContextEvidencePoint


class ContextRadarOverviewDeepDiveHint(GatewayBaseModel):
    candidate_id: str = Field(min_length=1)
    reason: ContextEvidencePoint


class ContextRadarOverviewInterpretation(GatewayBaseModel):
    """Strict screen-wide Investment Radar interpretation payload."""

    schema_version: str = Field(
        default=RADAR_OVERVIEW_INTERPRETATION_RESPONSE_SCHEMA_VERSION,
        min_length=1,
    )
    radar_context_id: str = Field(min_length=1)
    context_hash: str = Field(min_length=1)
    summary: ContextEvidencePoint
    candidate_set_movement: ContextEvidencePoint | None = None
    sector_notes: list[ContextRadarOverviewSectorNote] = Field(default_factory=list, max_length=4)
    theme_notes: list[ContextRadarOverviewThemeNote] = Field(default_factory=list, max_length=3)
    deep_dive_hints: list[ContextRadarOverviewDeepDiveHint] = Field(
        default_factory=list, max_length=2
    )
    unknowns: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)
    next_checkpoints: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)


class ContextRankingInterpretation(GatewayBaseModel):
    """Strict payload for an explicit, reference-only Ranking explanation."""

    schema_version: str = Field(
        default=RANKING_INTERPRETATION_RESPONSE_SCHEMA_VERSION,
        min_length=1,
    )
    ranking_context_id: str = Field(min_length=1)
    summary: ContextEvidencePoint
    common_strengths: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)
    common_cautions: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)
    metric_notes: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)
    sector_notes: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)
    candidate_notes: list[ContextRankingCandidateNote] = Field(
        default_factory=list,
        max_length=5,
    )
    next_checkpoints: list[ContextEvidencePoint] = Field(default_factory=list, max_length=4)


class ContextAnswerResponse(GatewayBaseModel):
    """Structured answer expected by client-side assistant UIs."""

    schema_version: str = CONTEXT_ANSWER_RESPONSE_SCHEMA_VERSION
    answer: str = Field(min_length=1)
    materials: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    next_checkpoints: list[str] = Field(default_factory=list)
    referenced_sections: list[ContextReferencedSection] = Field(default_factory=list)
    radar_interpretation: ContextRadarInterpretation | None = None
    radar_overview_interpretation: ContextRadarOverviewInterpretation | None = None
    ranking_interpretation: ContextRankingInterpretation | None = None
    confidence: ContextAnswerConfidence = "low"
    safety_notes: list[str] = Field(default_factory=list)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    profile: LlmProfileName = "fallback"
    elapsed_ms: int = Field(ge=0)
    gateway_status: ContextAnswerGatewayStatus = "ok"
    fallback_reason: str | None = Field(default=None, min_length=1)
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    timeout_sec: float | None = Field(default=None, ge=0)
    context_tokens_estimate: int | None = Field(default=None, ge=0)
    prompt_chars: int | None = Field(default=None, ge=0)
    response_chars: int | None = Field(default=None, ge=0)
    tool_execution_ms: int | None = Field(default=None, ge=0)
    llm_generation_ms: int | None = Field(default=None, ge=0)
    total_elapsed_ms: int | None = Field(default=None, ge=0)
    decision_support_note: str = Field(
        default="This response is decision-support context, not investment advice.",
        min_length=1,
    )
