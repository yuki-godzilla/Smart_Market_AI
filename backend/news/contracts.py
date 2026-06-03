from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel

NEWS_DASHBOARD_SCHEMA_VERSION = "news-dashboard-snapshot-v1"

NewsFreshnessStatus = Literal["latest", "recent", "stale", "unknown"]


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
    is_official_source: bool = False
    ai_comment: str | None = None
    investment_checkpoints: list[str] = Field(default_factory=list)


class NewsHeatmapCell(StrictBaseModel):
    """News heat cell for market theme / category intensity."""

    category: str = Field(min_length=1)
    region: str | None = Field(default=None, min_length=1)
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
