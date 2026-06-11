from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import GatewayBaseModel

CONTEXT_ANSWER_RESPONSE_SCHEMA_VERSION = "assistant-gateway-response-v1"

ContextAnswerTask = Literal["explain", "summarize", "compare", "next_steps", "chat"]
ContextAnswerLanguage = Literal["ja", "en"]
ContextAnswerConfidence = Literal["low", "medium", "high"]


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
    model: str | None = Field(default=None, min_length=1)


class ContextReferencedSection(GatewayBaseModel):
    """Reference back to a section from the supplied context bundle."""

    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)


class ContextAnswerResponse(GatewayBaseModel):
    """Structured answer expected by client-side assistant UIs."""

    schema_version: str = CONTEXT_ANSWER_RESPONSE_SCHEMA_VERSION
    answer: str = Field(min_length=1)
    materials: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    next_checkpoints: list[str] = Field(default_factory=list)
    referenced_sections: list[ContextReferencedSection] = Field(default_factory=list)
    confidence: ContextAnswerConfidence = "low"
    safety_notes: list[str] = Field(default_factory=list)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    elapsed_ms: int = Field(ge=0)
    decision_support_note: str = Field(
        default="This response is decision-support context, not investment advice.",
        min_length=1,
    )
