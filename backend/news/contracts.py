from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel

NEWS_DASHBOARD_SCHEMA_VERSION = "news-dashboard-snapshot-v1"

NewsFreshnessStatus = Literal["latest", "recent", "stale", "unknown"]
RadarCandidateProvenance = Literal["direct_mention", "inferred_candidate", "macro_proxy"]
RadarCandidateMaterialTone = Literal["positive", "caution", "mixed", "unknown"]
RadarCandidateDataStatus = Literal["available", "partial", "unavailable", "not_checked"]
NewsSymbolMatchKind = Literal[
    "direct_mention",
    "alias_match",
    "ticker_match",
    "code_match",
    "macro_proxy",
    "category_inferred",
    "llm_verified_inferred",
    "rejected",
]
NewsSymbolEvidenceField = Literal["title", "summary", "body", "category", "fallback"]


class NewsSymbolMatch(StrictBaseModel):
    """Classified symbol evidence for one Investment Radar headline."""

    symbol: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1)
    kind: NewsSymbolMatchKind
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_text: str | None = Field(default=None, min_length=1)
    evidence_field: NewsSymbolEvidenceField | None = None
    reason: str | None = Field(default=None, min_length=1)


class NewsSymbolUniverseAlias(StrictBaseModel):
    """Minimal alias row shared with a future LLM recheck gateway."""

    symbol: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1)
    aliases: list[str] = Field(default_factory=list)


class NewsSymbolLLMExtractionRequest(StrictBaseModel):
    """Network-free contract boundary for future LLM-assisted symbol rechecks."""

    title: str = Field(min_length=1)
    summary: str | None = None
    category: str = Field(min_length=1)
    region: str | None = Field(default=None, min_length=1)
    material_type: str = Field(min_length=1)
    deterministic_candidates: list[NewsSymbolMatch] = Field(default_factory=list)
    symbol_universe_aliases: list[NewsSymbolUniverseAlias] = Field(default_factory=list)


class NewsSymbolLLMExtractionResponse(StrictBaseModel):
    """LLM response contract; callers still decide what is displayed."""

    direct_symbols: list[NewsSymbolMatch] = Field(default_factory=list)
    inferred_symbols: list[NewsSymbolMatch] = Field(default_factory=list)
    macro_proxy_symbols: list[NewsSymbolMatch] = Field(default_factory=list)
    rejected_symbols: list[NewsSymbolMatch] = Field(default_factory=list)


class NewsHeadlineCard(StrictBaseModel):
    """Normalized display-ready news card for the Investment News dashboard."""

    title: str = Field(min_length=1)
    summary: str | None = None
    url: str | None = Field(default=None, min_length=1)
    source_name: str | None = Field(default=None, min_length=1)
    source_type: str = Field(min_length=1)
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    freshness_status: NewsFreshnessStatus = "unknown"
    category: str = Field(min_length=1)
    region: str | None = Field(default=None, min_length=1)
    material_type: str = Field(min_length=1)
    related_symbols: list[str] = Field(default_factory=list)
    inferred_symbols: list[str] = Field(default_factory=list)
    macro_proxy_symbols: list[str] = Field(default_factory=list)
    symbol_matches: list[NewsSymbolMatch] = Field(default_factory=list)
    is_official_source: bool = False
    ai_comment: str | None = None
    investment_checkpoints: list[str] = Field(default_factory=list)


class RadarCandidateEvidence(StrictBaseModel):
    """One stable, traceable news reason for a Radar exploration candidate."""

    evidence_id: str = Field(min_length=1)
    headline_title: str = Field(min_length=1)
    source_name: str | None = Field(default=None, min_length=1)
    source_type: str = Field(min_length=1)
    source_url: str | None = Field(default=None, min_length=1)
    category: str = Field(min_length=1)
    material_type: str = Field(min_length=1)
    provenance: RadarCandidateProvenance
    directness: float = Field(ge=0.0, le=1.0)
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    freshness_status: NewsFreshnessStatus = "unknown"


class RadarCandidate(StrictBaseModel):
    """A deterministic candidate for confirmation, never an investment ranking row."""

    candidate_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    display_name: str | None = Field(default=None, min_length=1)
    market: str | None = Field(default=None, min_length=1)
    asset_type: str | None = Field(default=None, min_length=1)
    provenance: RadarCandidateProvenance
    categories: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence: list[RadarCandidateEvidence] = Field(default_factory=list)
    freshness_status: NewsFreshnessStatus = "unknown"
    latest_published_at: datetime | None = None
    independent_source_count: int = Field(default=0, ge=0)
    watchlist_match: bool = False
    symbol_data_status: RadarCandidateDataStatus = "not_checked"
    price_data_status: RadarCandidateDataStatus = "not_checked"
    rag_data_status: RadarCandidateDataStatus = "not_checked"
    confirmation_gaps: list[str] = Field(default_factory=list)
    directness: float = Field(ge=0.0, le=1.0)
    confirmation_priority: int = Field(ge=0, le=100)
    material_tone: RadarCandidateMaterialTone = "unknown"
    is_investigation_candidate: bool = True


class RadarCandidateMap(StrictBaseModel):
    """Bounded, network-free candidate map constructed from a news snapshot."""

    generated_at: datetime
    candidates: list[RadarCandidate] = Field(default_factory=list)


class NewsHeatmapCell(StrictBaseModel):
    """Investment heat cell for market category intensity."""

    category: str = Field(min_length=1)
    region: str | None = Field(default=None, min_length=1)
    price_change_pct: float | None = None
    volume_activity_score: float | None = Field(default=None, ge=0.0)
    news_count: int = Field(ge=0)
    risk_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    official_source_count: int = Field(ge=0)
    freshness_ratio: float = Field(ge=0.0, le=1.0)
    heat_score: float = Field(ge=0.0)
    dominant_material_type: str | None = Field(default=None, min_length=1)


class NewsCategoryLane(StrictBaseModel):
    """Compact lane of headline cards for one investment category."""

    category: str = Field(min_length=1)
    headlines: list[NewsHeadlineCard] = Field(default_factory=list)


class NewsDashboardSnapshot(StrictBaseModel):
    """Bounded dashboard snapshot persisted for the Investment News screen."""

    schema_version: str = NEWS_DASHBOARD_SCHEMA_VERSION
    generated_at: datetime
    fetched_at: datetime | None = None
    freshness_status: NewsFreshnessStatus = "unknown"
    stream_headlines: list[NewsHeadlineCard] = Field(default_factory=list)
    heatmap_cells: list[NewsHeatmapCell] = Field(default_factory=list)
    category_lanes: list[NewsCategoryLane] = Field(default_factory=list)


class NewsUpdateStatus(StrictBaseModel):
    """Latest-only status for dashboard refresh/cache operations."""

    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_type: str | None = Field(default=None, min_length=1)
    consecutive_failures: int = Field(default=0, ge=0)
    is_refreshing: bool = False
    cache_file_size_bytes: int | None = Field(default=None, ge=0)
