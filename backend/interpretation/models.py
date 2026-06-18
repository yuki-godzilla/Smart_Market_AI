from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from backend.assistant import AssistantContextBundle
from backend.core.data_contracts import StrictBaseModel

COCKPIT_INTERPRETATION_SCHEMA_VERSION = "cockpit_interpretation.v1"
COCKPIT_INTERPRETATION_PROMPT_VERSION = "cockpit_interpretation_mvp.v1"

CockpitInterpretationStatus = Literal["live", "fallback", "disabled", "validation_error"]
CockpitInterpretationFallbackReason = Literal[
    "disabled",
    "gateway_unavailable",
    "gateway_timeout",
    "gateway_http_error",
    "malformed_json",
    "validation_error",
    "wrong_symbol",
    "unknown_evidence",
    "policy_violation",
    "cache_miss",
    "cache_corrupt",
    "provider_error",
]


class InterpretationBullet(StrictBaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class CockpitInterpretationContext(StrictBaseModel):
    symbol: str = Field(min_length=1)
    company_name: str | None = Field(default=None, min_length=1)
    as_of: date
    bundle: AssistantContextBundle
    context_hash: str = Field(min_length=1)
    allowed_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class CockpitInterpretationResult(StrictBaseModel):
    symbol: str = Field(min_length=1)
    company_name: str | None = Field(default=None, min_length=1)
    status: CockpitInterpretationStatus
    overall_reading: str = Field(min_length=1)
    positive_points: list[InterpretationBullet] = Field(default_factory=list)
    caution_points: list[InterpretationBullet] = Field(default_factory=list)
    contradictions: list[InterpretationBullet] = Field(default_factory=list)
    uncertainties: list[InterpretationBullet] = Field(default_factory=list)
    next_checks: list[InterpretationBullet] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    gateway_profile: str | None = Field(default=None, min_length=1)
    generated_at: datetime | None = None
    prompt_version: str = Field(default=COCKPIT_INTERPRETATION_PROMPT_VERSION, min_length=1)
    schema_version: str = Field(default=COCKPIT_INTERPRETATION_SCHEMA_VERSION, min_length=1)
    context_hash: str | None = Field(default=None, min_length=1)
    fallback_reason: CockpitInterpretationFallbackReason | None = None
    is_fallback: bool = False


class CockpitInterpretationCacheMetadata(StrictBaseModel):
    status: Literal["hit", "miss", "disabled", "invalid"]
    cache_hit: bool = False
    cache_key: str | None = None
    context_hash: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    generated_at: datetime | None = None
    expires_at: datetime | None = None


class CockpitInterpretationServiceResult(StrictBaseModel):
    result: CockpitInterpretationResult
    cache: CockpitInterpretationCacheMetadata
