from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel

SYMBOL_REFRESH_SCHEMA_VERSION = "symbol-refresh-v1"
SYMBOL_RECORD_SCHEMA_VERSION = "symbol-record-v1"

SymbolFreshnessStatus = Literal["fresh", "stale", "expired", "missing"]
SymbolRefreshTaskStatus = Literal[
    "pending",
    "in_progress",
    "succeeded",
    "failed",
    "skipped",
    "retryable",
]


class SymbolUsageStats(StrictBaseModel):
    """Lightweight aggregate usage metadata for one symbol."""

    symbol: str = Field(min_length=1)
    view_count_total: int = Field(default=0, ge=0)
    view_count_last_30_days: int = Field(default=0, ge=0)
    last_viewed_at: datetime | None = None
    last_opened_from: str | None = Field(default=None, min_length=1)


class SymbolImportanceMeta(StrictBaseModel):
    """Static or derived importance metadata for refresh prioritization."""

    symbol: str = Field(min_length=1)
    importance_rank: int | None = Field(default=None, ge=1)
    is_major_symbol: bool = False
    is_core_etf: bool = False
    is_ranking_base_symbol: bool = False


class SymbolDataFreshness(StrictBaseModel):
    """Current freshness state for a stored symbol record."""

    symbol: str = Field(min_length=1)
    last_price_updated_at: datetime | None = None
    last_fundamental_updated_at: datetime | None = None
    last_refreshed_at: datetime | None = None
    data_freshness_status: SymbolFreshnessStatus
    should_refresh: bool
    reason: str | None = Field(default=None, min_length=1)


class SymbolRefreshPriority(StrictBaseModel):
    """Score components used to rank symbol refresh tasks."""

    symbol: str = Field(min_length=1)
    data_freshness_status: SymbolFreshnessStatus
    usage_score: int = Field(default=0, ge=0)
    importance_score: int = Field(default=0, ge=0)
    stale_score: int = Field(default=0, ge=0)
    recent_view_bonus: int = Field(default=0, ge=0)
    ranking_candidate_bonus: int = Field(default=0, ge=0)
    manual_refresh_bonus: int = Field(default=0, ge=0)
    refresh_priority_score: int = Field(ge=0)
    reason: str | None = Field(default=None, min_length=1)
    last_refreshed_at: datetime | None = None


class SymbolRefreshTask(StrictBaseModel):
    """Persistable unit of work for refreshing one symbol."""

    schema_version: str = SYMBOL_REFRESH_SCHEMA_VERSION
    symbol: str = Field(min_length=1)
    market: str | None = Field(default=None, min_length=1)
    priority: int = Field(ge=0)
    refresh_priority_score: int = Field(default=0, ge=0)
    reason: str = Field(min_length=1)
    status: SymbolRefreshTaskStatus = "pending"
    data_freshness_status: SymbolFreshnessStatus = "missing"
    requested_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error_type: str | None = Field(default=None, min_length=1)
    retry_count: int = Field(default=0, ge=0)
    last_refreshed_at: datetime | None = None


class SymbolRefreshItemResult(StrictBaseModel):
    """Outcome for one symbol refresh attempt."""

    symbol: str = Field(min_length=1)
    success: bool
    provider: str | None = Field(default=None, min_length=1)
    updated_fields: list[str] = Field(default_factory=list)
    skipped_reason: str | None = Field(default=None, min_length=1)
    error_type: str | None = Field(default=None, min_length=1)
    elapsed_ms: int | None = Field(default=None, ge=0)


class SymbolRefreshResult(StrictBaseModel):
    """Bounded summary for one refresh run."""

    started_at: datetime
    finished_at: datetime
    attempted_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    items: list[SymbolRefreshItemResult] = Field(default_factory=list)


class SymbolRefreshStatus(StrictBaseModel):
    """Latest-only state for symbol background refresh operations."""

    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_type: str | None = Field(default=None, min_length=1)
    consecutive_failures: int = Field(default=0, ge=0)
    last_refreshed_symbols: list[str] = Field(default_factory=list)
    refresh_queue_size: int = Field(default=0, ge=0)
    is_refreshing: bool = False


class SymbolRecord(StrictBaseModel):
    """Normalized latest-only symbol data persisted by the refresh layer."""

    schema_version: str = SYMBOL_RECORD_SCHEMA_VERSION
    symbol: str = Field(min_length=1)
    market: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    updated_at: datetime
    last_price_updated_at: datetime | None = None
    last_fundamental_updated_at: datetime | None = None
    data_freshness_status: SymbolFreshnessStatus = "fresh"
    normalized_fields: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SymbolMetricRecord(StrictBaseModel):
    """Official lightweight metrics used by search/filter UI paths."""

    symbol: str = Field(min_length=1)
    source: str | None = Field(default=None, min_length=1)
    source_updated_at: datetime | None = None
    promoted_at: datetime
    fields: dict[str, str] = Field(default_factory=dict)


class SymbolCacheSyncResult(StrictBaseModel):
    """Summary for moving runtime cache records into official search metrics."""

    scanned_count: int = Field(ge=0)
    promoted_count: int = Field(ge=0)
    deleted_count: int = Field(ge=0)
    missing_deleted_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    promoted_symbols: list[str] = Field(default_factory=list)
    deleted_symbols: list[str] = Field(default_factory=list)


class SymbolStartupRefreshSummary(StrictBaseModel):
    """Compact startup-refresh summary for UI/session diagnostics."""

    attempted_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    pending_like_count: int = Field(ge=0)
    record_count: int = Field(ge=0)
    queue_symbols: list[str] = Field(default_factory=list)
    refreshed_symbols: list[str] = Field(default_factory=list)
