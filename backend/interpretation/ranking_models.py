from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from backend.assistant import AssistantContextBundle
from backend.core.data_contracts import StrictBaseModel

RANKING_INTERPRETATION_SCHEMA_VERSION = "ranking_interpretation.v1"
RANKING_INTERPRETATION_PROMPT_VERSION = "ranking_interpretation_mvp.v1"

RankingInterpretationStatus = Literal["live", "fallback", "disabled", "validation_error"]
RankingInterpretationFallbackReason = Literal[
    "disabled",
    "gateway_unavailable",
    "gateway_timeout",
    "gateway_http_error",
    "malformed_json",
    "validation_error",
    "wrong_context",
    "wrong_candidate",
    "duplicate_candidate",
    "unknown_evidence",
    "unsupported_number",
    "unsupported_date",
    "policy_violation",
    "cache_corrupt",
    "provider_error",
]


class RankingCandidateEvidence(StrictBaseModel):
    candidate_id: str = Field(min_length=1)
    rank: int = Field(gt=0)
    symbol: str = Field(min_length=1)
    company_name: str | None = Field(default=None, min_length=1)
    primary_metric_id: str = Field(min_length=1)
    primary_metric_label: str = Field(min_length=1)
    primary_metric_value: str = Field(min_length=1)
    total_score: str = ""
    screening_score: str = ""
    upside_signal: str = ""
    upward_signal: str = ""
    downside_warning: str = ""
    risk_score: str = ""
    data_quality: str = ""
    database_fit: str = ""
    metadata_confidence: str = ""
    forecast_summary: str = ""
    reason: str = ""
    caution: str = ""
    research_status: str = ""


class RankingSectorEvidence(StrictBaseModel):
    sector_id: str = Field(min_length=1)
    sector_label: str = Field(min_length=1)
    candidate_count: int = Field(gt=0)
    best_rank: int = Field(gt=0)
    representative_candidate_id: str = Field(min_length=1)
    primary_metric_average: str | None = Field(default=None, min_length=1)
    comparison_state: Literal["comparable", "insufficient"]


class RankingInterpretationInput(StrictBaseModel):
    result_id: str = Field(min_length=1)
    as_of: date
    ranking_policy: str = Field(min_length=1)
    weight_preset: str = Field(min_length=1)
    region: str = Field(min_length=1)
    product_type: str = Field(min_length=1)
    candidate_count: int = Field(ge=0)
    candidates: list[RankingCandidateEvidence] = Field(min_length=1, max_length=5)
    sector_groups: list[RankingSectorEvidence] = Field(default_factory=list, max_length=6)
    warnings: list[str] = Field(default_factory=list)


class RankingInterpretationContext(StrictBaseModel):
    ranking_context_id: str = Field(min_length=1)
    as_of: date
    bundle: AssistantContextBundle
    context_hash: str = Field(min_length=1)
    candidate_ids: list[str] = Field(min_length=1, max_length=5)
    allowed_evidence_ids: list[str] = Field(min_length=1)
    allowed_symbols: list[str] = Field(min_length=1, max_length=5)
    allowed_numeric_values: list[str] = Field(default_factory=list)
    allowed_dates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RankingInterpretationPoint(StrictBaseModel):
    summary: str = Field(min_length=1, max_length=320)
    evidence_ids: list[str] = Field(default_factory=list, max_length=5)


class RankingCandidateInterpretationNote(StrictBaseModel):
    candidate_id: str = Field(min_length=1)
    reading: RankingInterpretationPoint
    caution: RankingInterpretationPoint | None = None
    next_check: RankingInterpretationPoint


class RankingInterpretationResult(StrictBaseModel):
    ranking_context_id: str = Field(min_length=1)
    status: RankingInterpretationStatus
    overall_reading: str = Field(min_length=1, max_length=900)
    common_strengths: list[RankingInterpretationPoint] = Field(default_factory=list, max_length=4)
    common_cautions: list[RankingInterpretationPoint] = Field(default_factory=list, max_length=4)
    metric_notes: list[RankingInterpretationPoint] = Field(default_factory=list, max_length=4)
    sector_notes: list[RankingInterpretationPoint] = Field(default_factory=list, max_length=4)
    candidate_notes: list[RankingCandidateInterpretationNote] = Field(
        default_factory=list, max_length=5
    )
    next_checks: list[RankingInterpretationPoint] = Field(default_factory=list, max_length=4)
    referenced_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    gateway_profile: str | None = Field(default=None, min_length=1)
    generated_at: datetime | None = None
    prompt_version: str = Field(default=RANKING_INTERPRETATION_PROMPT_VERSION, min_length=1)
    schema_version: str = Field(default=RANKING_INTERPRETATION_SCHEMA_VERSION, min_length=1)
    context_hash: str = Field(min_length=1)
    fallback_reason: RankingInterpretationFallbackReason | None = None
    is_fallback: bool = False


class RankingInterpretationCacheMetadata(StrictBaseModel):
    status: Literal["hit", "miss", "disabled", "invalid"]
    cache_hit: bool = False
    cache_key: str = Field(min_length=1)
    generated_at: datetime | None = None
    expires_at: datetime | None = None


class RankingInterpretationServiceResult(StrictBaseModel):
    result: RankingInterpretationResult
    cache: RankingInterpretationCacheMetadata
