from __future__ import annotations

from typing import Literal

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel

ASSISTANT_GATEWAY_NEWS_INTERPRETATION_SCHEMA_VERSION = "news_interpretation.v1"


class AssistantGatewayNewsEvidencePoint(StrictBaseModel):
    text: str = Field(min_length=1, max_length=320)
    cited_evidence_ids: list[str] = Field(min_length=1, max_length=5)


class AssistantGatewayNewsMaterialNote(StrictBaseModel):
    material_id: str = Field(min_length=1)
    business_impact_direction: Literal[
        "tailwind_candidate", "headwind_candidate", "mixed", "unclear", "not_applicable"
    ]
    impact_horizon: Literal[
        "current_event", "next_confirmation_cycle", "multi_quarter", "structural", "unclear"
    ]
    related_sector_ids: list[str] = Field(default_factory=list, max_length=4)
    reading: AssistantGatewayNewsEvidencePoint
    uncertainty: AssistantGatewayNewsEvidencePoint | None = None


class AssistantGatewayNewsSectorNote(StrictBaseModel):
    sector_id: str = Field(min_length=1)
    reading: AssistantGatewayNewsEvidencePoint


class AssistantGatewayNewsHandoffHint(StrictBaseModel):
    candidate_id: str = Field(min_length=1)
    reason: AssistantGatewayNewsEvidencePoint


class AssistantGatewayNewsInterpretation(StrictBaseModel):
    schema_version: str = Field(
        default=ASSISTANT_GATEWAY_NEWS_INTERPRETATION_SCHEMA_VERSION, min_length=1
    )
    news_context_id: str = Field(min_length=1)
    context_hash: str = Field(min_length=1)
    summary: AssistantGatewayNewsEvidencePoint
    material_notes: list[AssistantGatewayNewsMaterialNote] = Field(
        default_factory=list, max_length=4
    )
    sector_notes: list[AssistantGatewayNewsSectorNote] = Field(default_factory=list, max_length=4)
    noise_notes: list[AssistantGatewayNewsEvidencePoint] = Field(default_factory=list, max_length=3)
    handoff_hints: list[AssistantGatewayNewsHandoffHint] = Field(default_factory=list, max_length=3)
    unknowns: list[AssistantGatewayNewsEvidencePoint] = Field(default_factory=list, max_length=4)
    next_checkpoints: list[AssistantGatewayNewsEvidencePoint] = Field(
        default_factory=list, max_length=4
    )
