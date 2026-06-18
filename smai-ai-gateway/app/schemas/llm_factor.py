from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field

from app.schemas.common import GatewayBaseModel
from app.services.model_router import LlmEnvironmentProfile, LlmExecutionMode, LlmProfileName

LLM_FACTOR_GATEWAY_REQUEST_SCHEMA_VERSION = "llm-factor-gateway-request-v1"
LLM_FACTOR_GATEWAY_RESPONSE_SCHEMA_VERSION = "llm_factor.v1"
LLM_FACTOR_LIVE_PROMPT_VERSION = "llm_factor_live_mvp.v1"

LLMFactorGatewayLanguage = Literal["ja", "en"]
LLMFactorSentimentLabel = Literal["positive", "neutral", "negative", "mixed", "unknown"]
LLMFactorDirection = Literal["positive", "negative", "neutral"]
LLMFactorGatewayStatus = Literal["ok", "fallback"]


class LLMFactorEvidenceContext(GatewayBaseModel):
    """Compact source context supplied by SMAI parent."""

    evidence_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_url: str | None = Field(default=None, min_length=1)
    source_date: date | None = None
    provider: str | None = Field(default=None, min_length=1)
    summary: str = Field(min_length=1)
    reliability_score: float | None = Field(default=None, ge=0, le=100)


class LLMFactorGenerationContext(GatewayBaseModel):
    """SMAI-owned compressed context for one-symbol factor generation."""

    symbol_profile: dict[str, str] = Field(default_factory=dict)
    research_summary: list[str] = Field(default_factory=list)
    news_summary: list[str] = Field(default_factory=list)
    forecast_summary: dict[str, str] = Field(default_factory=dict)
    evidence: list[LLMFactorEvidenceContext] = Field(default_factory=list)


class LLMFactorGenerationConstraints(GatewayBaseModel):
    """Safety constraints for qualitative factor generation."""

    no_investment_advice: bool = True
    use_only_supplied_context: bool = True
    do_not_change_scores: bool = True
    do_not_rank_symbols: bool = True
    require_evidence_ids: bool = True
    max_factors: int = Field(default=5, ge=1, le=10)
    max_risks: int = Field(default=5, ge=1, le=10)
    max_opportunities: int = Field(default=5, ge=1, le=10)


class LLMFactorGenerationRequest(GatewayBaseModel):
    """Gateway request for one-symbol LLM Factor live generation."""

    schema_version: str = Field(
        default=LLM_FACTOR_GATEWAY_REQUEST_SCHEMA_VERSION,
        min_length=1,
    )
    symbol: str = Field(min_length=1)
    company_name: str | None = Field(default=None, min_length=1)
    as_of: date
    language: LLMFactorGatewayLanguage = "ja"
    context: LLMFactorGenerationContext
    constraints: LLMFactorGenerationConstraints = Field(
        default_factory=LLMFactorGenerationConstraints
    )
    prompt_version: str = Field(default=LLM_FACTOR_LIVE_PROMPT_VERSION, min_length=1)
    response_schema_version: str = Field(
        default=LLM_FACTOR_GATEWAY_RESPONSE_SCHEMA_VERSION,
        min_length=1,
    )
    model: str | None = Field(default=None, min_length=1)
    execution_mode: LlmExecutionMode = "auto"
    environment_profile: LlmEnvironmentProfile = "notebook"
    preferred_profile: LlmProfileName | None = None
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)


class LLMFactorGatewayFactor(GatewayBaseModel):
    """Qualitative material factor returned by the LLM provider."""

    title: str = Field(min_length=1)
    direction: LLMFactorDirection
    summary: str = Field(min_length=1)
    strength: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class LLMFactorGatewayRisk(GatewayBaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    severity: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class LLMFactorGatewayOpportunity(GatewayBaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    impact: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)


class LLMFactorGatewayEvidence(GatewayBaseModel):
    evidence_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_url: str | None = Field(default=None, min_length=1)
    source_date: date | None = None
    summary: str = Field(min_length=1)


class LLMFactorGenerationResponse(GatewayBaseModel):
    """Structured one-symbol factor output returned to SMAI parent."""

    schema_version: str = Field(
        default=LLM_FACTOR_GATEWAY_RESPONSE_SCHEMA_VERSION,
        min_length=1,
    )
    symbol: str = Field(min_length=1)
    overall_summary: str = Field(min_length=1)
    sentiment_label: LLMFactorSentimentLabel = "unknown"
    confidence: float = Field(ge=0, le=1)
    factors: list[LLMFactorGatewayFactor] = Field(default_factory=list)
    risks: list[LLMFactorGatewayRisk] = Field(default_factory=list)
    opportunities: list[LLMFactorGatewayOpportunity] = Field(default_factory=list)
    evidence: list[LLMFactorGatewayEvidence] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    prompt_version: str = Field(default=LLM_FACTOR_LIVE_PROMPT_VERSION, min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    profile: LlmProfileName = "fallback"
    generated_at: datetime
    elapsed_ms: int = Field(ge=0)
    gateway_status: LLMFactorGatewayStatus = "ok"
    fallback_reason: str | None = Field(default=None, min_length=1)
    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    timeout_sec: float | None = Field(default=None, ge=0)
    context_tokens_estimate: int | None = Field(default=None, ge=0)
    prompt_chars: int | None = Field(default=None, ge=0)
    response_chars: int | None = Field(default=None, ge=0)
    decision_support_note: str = Field(
        default="This response is decision-support context, not investment advice.",
        min_length=1,
    )
