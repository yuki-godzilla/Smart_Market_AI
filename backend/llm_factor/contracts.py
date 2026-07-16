from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field

from backend.core.data_contracts import StrictBaseModel

LLM_FACTOR_SCHEMA_VERSION = "llm-factor-result-v1"
LLM_FACTOR_CACHE_ENTRY_SCHEMA_VERSION = "llm-factor-cache-entry-v1"
LLM_FACTOR_PROMPT_VERSION = "llm-factor-reference-v2"
LLM_FACTOR_FAKE_MODEL_NAME = "deterministic_fake_llm_factor"

LLMFactorCacheStatus = Literal["hit", "miss", "expired", "invalid"]
LLMFactorGatewayStatus = Literal["ok", "fallback", "error"]
LLMFactorSentimentLabel = Literal["positive", "neutral", "negative", "mixed", "unknown"]

LLMFactorSourceType = Literal[
    "research_summary",
    "news",
    "tdnet",
    "edinet",
    "company_ir",
    "provider_profile",
    "symbol_db",
    "local_reference",
    "other",
]


class EvidenceSource(StrictBaseModel):
    """Source metadata used to ground an LLM material factor."""

    title: str = Field(min_length=1)
    source_type: LLMFactorSourceType = "other"
    source_url: str = Field(min_length=1)
    source_date: date
    fetched_at: datetime | None = None
    provider: str | None = Field(default=None, min_length=1)
    summary: str | None = Field(default=None, min_length=1)
    reliability_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)


class LLMFactorEvidenceSelection(StrictBaseModel):
    """Audit metadata for evidence retained for an LLM Factor result.

    Counts describe the supplied candidates before the local fallback source is
    added.  This keeps the UI honest when a result is only a local reference.
    """

    input_count: int = Field(default=0, ge=0)
    retained_count: int = Field(default=0, ge=0)
    duplicate_count: int = Field(default=0, ge=0)
    unrelated_count: int = Field(default=0, ge=0)
    official_count: int = Field(default=0, ge=0)
    primary_disclosure_count: int = Field(default=0, ge=0)
    fallback_used: bool = False


class BullishFactor(StrictBaseModel):
    """Structured positive material candidate extracted from source evidence."""

    title: str = Field(min_length=1)
    score: Decimal = Field(ge=0, le=100)
    reason: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    source_date: date
    source_type: LLMFactorSourceType = "other"


class BearishFactor(StrictBaseModel):
    """Structured caution material candidate extracted from source evidence."""

    title: str = Field(min_length=1)
    score: Decimal = Field(ge=0, le=100)
    reason: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    source_date: date
    source_type: LLMFactorSourceType = "other"


class LLMFactorResult(StrictBaseModel):
    """SMAI-owned qualitative factor result produced from source-backed context."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = Field(default=LLM_FACTOR_SCHEMA_VERSION, min_length=1)
    ticker: str = Field(min_length=1)
    as_of: date
    generated_at: datetime
    model_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    source_hash: str = Field(min_length=1)
    llm_bullish_score: Decimal = Field(ge=0, le=100)
    llm_bearish_score: Decimal = Field(ge=0, le=100)
    llm_catalyst_score: Decimal = Field(ge=0, le=100)
    llm_risk_score: Decimal = Field(ge=0, le=100)
    llm_theme_score: Decimal = Field(ge=0, le=100)
    llm_freshness_score: Decimal = Field(ge=0, le=100)
    llm_evidence_quality_score: Decimal = Field(ge=0, le=100)
    llm_confidence_score: Decimal = Field(ge=0, le=100)
    bullish_factors: list[BullishFactor] = Field(default_factory=list)
    bearish_factors: list[BearishFactor] = Field(default_factory=list)
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    evidence_selection: LLMFactorEvidenceSelection = Field(
        default_factory=LLMFactorEvidenceSelection
    )
    summary: str = Field(min_length=1)
    disclaimer: str = Field(
        default="本結果は投資判断材料の整理であり、売買推奨ではありません。",
        min_length=1,
    )
    warnings: list[str] = Field(default_factory=list)
    provider: str | None = Field(default=None, min_length=1)
    gateway_profile: str | None = Field(default=None, min_length=1)
    gateway_status: LLMFactorGatewayStatus = "ok"
    fallback_reason: str | None = Field(default=None, min_length=1)
    sentiment_label: LLMFactorSentimentLabel = "unknown"
    missing_fields: list[str] = Field(default_factory=list)


class LLMFactorCacheEntry(StrictBaseModel):
    """Persisted LLM Factor result keyed by source hash and execution contract."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = Field(default=LLM_FACTOR_CACHE_ENTRY_SCHEMA_VERSION, min_length=1)
    cache_key: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    as_of: date
    source_hash: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    generated_at: datetime
    expires_at: datetime
    result: LLMFactorResult


class LLMFactorCacheLookup(StrictBaseModel):
    """Cache lookup result used by services to decide reuse or regeneration."""

    cache_key: str = Field(min_length=1)
    status: LLMFactorCacheStatus
    cache_hit: bool = False
    entry: LLMFactorCacheEntry | None = None


class LLMFactorCacheMetadata(StrictBaseModel):
    """User-visible cache/reproducibility metadata for a generated factor result."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    status: LLMFactorCacheStatus
    cache_hit: bool
    cache_key: str = Field(min_length=1)
    source_hash: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    generated_at: datetime | None = None
    expires_at: datetime | None = None


class LLMFactorServiceResult(StrictBaseModel):
    """LLM Factor output plus cache metadata for UI/reporting reuse."""

    result: LLMFactorResult
    cache: LLMFactorCacheMetadata
