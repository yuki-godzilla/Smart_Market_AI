from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel

ResearchSourceType = Literal[
    "annual_report",
    "earnings_report",
    "earnings_presentation",
    "medium_term_plan",
    "integrated_report",
    "company_ir",
    "tdnet",
    "news",
    "provider_profile",
    "user_note",
]

StockNewsFreshnessStatus = Literal["latest", "recent", "stale", "unknown"]


class ExternalResearchFetchRequest(StrictBaseModel):
    """Explicit opt-in request for external research/news source adapters."""

    symbol: str = Field(min_length=1)
    company_name: str | None = None
    related_keywords: list[str] = Field(default_factory=list)
    provider: str = Field(min_length=1)
    as_of: date | None = None
    allow_network: bool = False


class ExternalResearchSourcePayload(StrictBaseModel):
    """Fetched external source payload before local cache/registration."""

    symbol: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_url: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    company_name: str | None = None
    published_at: date | None = None
    fetched_at: datetime
    reliability: Decimal = Field(default=Decimal("0.70"), ge=0, le=1)


class ExternalResearchFetchManifestEntry(StrictBaseModel):
    """Trace row for an explicitly fetched external source."""

    title: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_url: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    published_at: date | None = None
    fetched_at: datetime
    freshness_status: StockNewsFreshnessStatus = "unknown"
    document_id: str = Field(min_length=1)
    retention_policy: Literal["session", "archive"] = "session"
    content_summary: str = ""
    local_path: str | None = None
    document_hash: str | None = None


class ExternalResearchFetchResult(StrictBaseModel):
    """Result of opt-in external fetch registered for the current analysis session."""

    symbol: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    fetched_at: datetime
    entries: list[ExternalResearchFetchManifestEntry] = Field(default_factory=list)
    retention_policy: Literal["session", "archive"] = "session"
    manifest_path: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ExternalResearchSourceAdapter(Protocol):
    """Adapter protocol for opt-in external research/news fetches."""

    provider: str
    requires_network: bool

    def fetch_sources(
        self, request: ExternalResearchFetchRequest
    ) -> list[ExternalResearchSourcePayload]: ...
