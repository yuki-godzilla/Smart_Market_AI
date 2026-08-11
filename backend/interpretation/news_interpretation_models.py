from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from backend.assistant import AssistantContextBundle
from backend.core.data_contracts import StrictBaseModel

NEWS_INTERPRETATION_SCHEMA_VERSION = "news_interpretation.v1"
NEWS_INTERPRETATION_PROMPT_VERSION = "news_interpretation_mvp.v1"

NewsBusinessImpactDirection = Literal[
    "tailwind_candidate", "headwind_candidate", "mixed", "unclear", "not_applicable"
]
NewsImpactHorizon = Literal[
    "current_event", "next_confirmation_cycle", "multi_quarter", "structural", "unclear"
]
NewsInterpretationStatus = Literal["live", "fallback", "disabled", "validation_error"]
NewsInterpretationFallbackReason = Literal[
    "disabled",
    "gateway_unavailable",
    "gateway_timeout",
    "gateway_http_error",
    "malformed_json",
    "validation_error",
    "wrong_context",
    "wrong_material",
    "wrong_sector",
    "wrong_candidate",
    "unknown_evidence",
    "unsupported_number",
    "unsupported_date",
    "policy_violation",
    "cache_corrupt",
    "provider_error",
]


class NewsInterpretationContext(StrictBaseModel):
    news_context_id: str = Field(min_length=1)
    as_of: date
    bundle: AssistantContextBundle
    context_hash: str = Field(min_length=1)
    allowed_evidence_ids: list[str] = Field(min_length=1, max_length=8)
    allowed_symbols: list[str] = Field(default_factory=list)
    allowed_numeric_values: list[str] = Field(default_factory=list)
    allowed_dates: list[str] = Field(default_factory=list)
    allowed_material_ids: list[str] = Field(default_factory=list, max_length=4)
    allowed_sector_ids: list[str] = Field(default_factory=list, max_length=4)
    allowed_handoff_candidate_ids: list[str] = Field(default_factory=list, max_length=3)
    material_sector_ids: dict[str, list[str]] = Field(default_factory=dict)
    material_candidate_ids: dict[str, list[str]] = Field(default_factory=dict)
    candidate_provenance: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class NewsInterpretationPoint(StrictBaseModel):
    summary: str = Field(min_length=1, max_length=320)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class NewsMaterialNote(StrictBaseModel):
    material_id: str = Field(min_length=1)
    business_impact_direction: NewsBusinessImpactDirection
    impact_horizon: NewsImpactHorizon
    related_sector_ids: list[str] = Field(default_factory=list, max_length=4)
    reading: NewsInterpretationPoint
    uncertainty: NewsInterpretationPoint | None = None


class NewsSectorNote(StrictBaseModel):
    sector_id: str = Field(min_length=1)
    reading: NewsInterpretationPoint


class NewsHandoffHint(StrictBaseModel):
    candidate_id: str = Field(min_length=1)
    reason: NewsInterpretationPoint


class NewsInterpretationResult(StrictBaseModel):
    news_context_id: str = Field(min_length=1)
    status: NewsInterpretationStatus
    summary: NewsInterpretationPoint
    material_notes: list[NewsMaterialNote] = Field(default_factory=list, max_length=4)
    sector_notes: list[NewsSectorNote] = Field(default_factory=list, max_length=4)
    noise_notes: list[NewsInterpretationPoint] = Field(default_factory=list, max_length=3)
    handoff_hints: list[NewsHandoffHint] = Field(default_factory=list, max_length=3)
    unknowns: list[NewsInterpretationPoint] = Field(default_factory=list, max_length=4)
    next_checks: list[NewsInterpretationPoint] = Field(default_factory=list, max_length=4)
    referenced_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    gateway_profile: str | None = Field(default=None, min_length=1)
    generated_at: datetime | None = None
    prompt_version: str = Field(default=NEWS_INTERPRETATION_PROMPT_VERSION, min_length=1)
    schema_version: str = Field(default=NEWS_INTERPRETATION_SCHEMA_VERSION, min_length=1)
    context_hash: str = Field(min_length=1)
    fallback_reason: NewsInterpretationFallbackReason | None = None
    is_fallback: bool = False


class NewsInterpretationCacheMetadata(StrictBaseModel):
    status: Literal["hit", "miss", "disabled", "invalid"]
    cache_hit: bool = False
    cache_key: str = Field(min_length=1)
    generated_at: datetime | None = None
    expires_at: datetime | None = None


class NewsInterpretationServiceResult(StrictBaseModel):
    result: NewsInterpretationResult
    cache: NewsInterpretationCacheMetadata
