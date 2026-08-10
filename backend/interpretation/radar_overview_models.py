from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from backend.assistant import AssistantContextBundle
from backend.core.data_contracts import StrictBaseModel

RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION = "radar_overview_interpretation.v1"
RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION = "radar_overview_interpretation_mvp.v1"

RadarOverviewMarketState = Literal["fresh", "stale", "missing", "partial"]
RadarOverviewInterpretationStatus = Literal["live", "fallback", "disabled", "validation_error"]
RadarOverviewInterpretationFallbackReason = Literal[
    "disabled",
    "gateway_unavailable",
    "gateway_timeout",
    "gateway_http_error",
    "malformed_json",
    "validation_error",
    "wrong_context",
    "wrong_candidate",
    "wrong_theme",
    "wrong_sector",
    "duplicate_candidate",
    "unknown_evidence",
    "unsupported_number",
    "unsupported_date",
    "policy_violation",
    "cache_corrupt",
    "provider_error",
]


class RadarOverviewInterpretationContext(StrictBaseModel):
    radar_context_id: str = Field(min_length=1)
    as_of: date
    bundle: AssistantContextBundle
    context_hash: str = Field(min_length=1)
    market_state: RadarOverviewMarketState
    allowed_evidence_ids: list[str] = Field(min_length=1, max_length=8)
    allowed_symbols: list[str] = Field(default_factory=list)
    allowed_numeric_values: list[str] = Field(default_factory=list)
    allowed_dates: list[str] = Field(default_factory=list)
    allowed_sector_ids: list[str] = Field(default_factory=list, max_length=4)
    allowed_theme_ids: list[str] = Field(default_factory=list, max_length=3)
    allowed_candidate_ids: list[str] = Field(default_factory=list)
    deep_dive_candidate_ids: list[str] = Field(default_factory=list, max_length=2)
    theme_candidate_ids: dict[str, list[str]] = Field(default_factory=dict)
    candidate_provenance: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RadarOverviewInterpretationPoint(StrictBaseModel):
    summary: str = Field(min_length=1, max_length=320)
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class RadarOverviewSectorNote(StrictBaseModel):
    sector_id: str = Field(min_length=1)
    reading: RadarOverviewInterpretationPoint


class RadarOverviewThemeNote(StrictBaseModel):
    theme_id: str = Field(min_length=1)
    related_candidate_ids: list[str] = Field(default_factory=list, max_length=3)
    reading: RadarOverviewInterpretationPoint


class RadarOverviewDeepDiveHint(StrictBaseModel):
    candidate_id: str = Field(min_length=1)
    reason: RadarOverviewInterpretationPoint


class RadarOverviewInterpretationResult(StrictBaseModel):
    radar_context_id: str = Field(min_length=1)
    status: RadarOverviewInterpretationStatus
    summary: RadarOverviewInterpretationPoint
    candidate_set_movement: RadarOverviewInterpretationPoint | None = None
    sector_notes: list[RadarOverviewSectorNote] = Field(default_factory=list, max_length=4)
    theme_notes: list[RadarOverviewThemeNote] = Field(default_factory=list, max_length=3)
    deep_dive_hints: list[RadarOverviewDeepDiveHint] = Field(default_factory=list, max_length=2)
    unknowns: list[RadarOverviewInterpretationPoint] = Field(default_factory=list, max_length=4)
    next_checks: list[RadarOverviewInterpretationPoint] = Field(default_factory=list, max_length=4)
    referenced_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    gateway_profile: str | None = Field(default=None, min_length=1)
    generated_at: datetime | None = None
    prompt_version: str = Field(default=RADAR_OVERVIEW_INTERPRETATION_PROMPT_VERSION, min_length=1)
    schema_version: str = Field(default=RADAR_OVERVIEW_INTERPRETATION_SCHEMA_VERSION, min_length=1)
    context_hash: str = Field(min_length=1)
    fallback_reason: RadarOverviewInterpretationFallbackReason | None = None
    is_fallback: bool = False


class RadarOverviewInterpretationCacheMetadata(StrictBaseModel):
    status: Literal["hit", "miss", "disabled", "invalid"]
    cache_hit: bool = False
    cache_key: str = Field(min_length=1)
    generated_at: datetime | None = None
    expires_at: datetime | None = None


class RadarOverviewInterpretationServiceResult(StrictBaseModel):
    result: RadarOverviewInterpretationResult
    cache: RadarOverviewInterpretationCacheMetadata
