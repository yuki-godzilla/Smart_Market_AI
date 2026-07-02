from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.core.data_contracts import StrictBaseModel

SCHEMA_VERSION = 1


class RankingHistoryError(RuntimeError):
    """Base error for recoverable ranking-history failures."""


class RankingHistoryLockTimeout(RankingHistoryError):
    pass


class RankingHistoryCorruptData(RankingHistoryError):
    pass


class RankingHistoryTarget(StrictBaseModel):
    region: str = "all"
    product_type: str = "all"
    market: str = "all"


class RankingHistoryPeriod(StrictBaseModel):
    start: date
    end: date


class RankingHistoryResultRow(StrictBaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    rank: int | None = None
    symbol: str = Field(min_length=1)
    name: str | None = None
    market: str | None = None
    country: str | None = None
    asset_type: str | None = None
    currency: str | None = None
    price: float | None = None
    price_jpy: float | None = None
    price_as_of: date | None = None
    total_score: float | None = None
    screening_score: float | None = None
    risk_score: float | None = None
    data_quality_score: float | None = None
    condition_fit_score: float | None = None
    upside_signal_score: float | None = None
    downside_signal_score: float | None = None
    forecast_change_pct: float | None = None
    forecast_confidence: float | None = None
    forecast_days: int | None = None
    model_direction: str | None = None
    dividend_yield_pct: float | None = None
    per: float | None = None
    pbr: float | None = None
    roe_pct: float | None = None
    market_cap: float | None = None
    volume: float | None = None
    volatility: float | None = None
    equity_ratio: float | None = None
    operating_margin: float | None = None
    revenue_growth_pct: float | None = None
    expense_ratio: float | None = None
    nisa_eligibility: str | None = None
    investment_style: str | None = None
    benchmark_index: str | None = None
    complexity: str | None = None
    ranking_reason: str | None = None
    confirmation_point: str | None = None
    smai_memo: str | None = None
    warning: str | None = None
    favorite_status_at_save: bool | None = None
    display: dict[str, str] = Field(default_factory=dict)


class RankingHistoryIndexItem(StrictBaseModel):
    run_id: str
    user_id: str
    created_at: datetime
    data_as_of: date
    ranking_type: str
    target: RankingHistoryTarget
    target_label: str
    condition_summary: str
    candidate_count: int = Field(ge=0)
    saved_row_count: int = Field(ge=0)
    top_symbols: list[str] = Field(default_factory=list)
    is_pinned: bool = False
    title: str | None = None
    memo: str | None = None
    snapshot_file: str
    signature: str
    snapshot_status: Literal["available", "missing", "invalid"] = "available"


class RankingHistoryIndex(StrictBaseModel):
    schema_version: int = SCHEMA_VERSION
    updated_at: datetime
    items: list[RankingHistoryIndexItem] = Field(default_factory=list)


class RankingHistorySnapshot(StrictBaseModel):
    schema_version: int = SCHEMA_VERSION
    run_id: str
    user_id: str
    created_at: datetime
    data_as_of: date
    provider: str
    period: RankingHistoryPeriod
    ranking_type: str
    weight_preset: str
    target: RankingHistoryTarget
    target_label: str
    filters: dict[str, Any] = Field(default_factory=dict)
    condition_summary: str
    candidate_count: int = Field(ge=0)
    saved_row_count: int = Field(ge=0)
    top_symbols: list[str] = Field(default_factory=list)
    result_rows: list[RankingHistoryResultRow]
    is_pinned: bool = False
    title: str | None = None
    memo: str | None = None
    ranking_logic_version: str
    universe_version: str | None = None
    signature: str


class RankingHistorySaveRequest(StrictBaseModel):
    data_as_of: date
    provider: str
    period: RankingHistoryPeriod
    ranking_type: str
    weight_preset: str
    target: RankingHistoryTarget
    target_label: str
    filters: dict[str, Any] = Field(default_factory=dict)
    condition_summary: str
    candidate_count: int = Field(ge=0)
    result_rows: list[RankingHistoryResultRow]
    ranking_logic_version: str
    universe_version: str | None = None


class RankingHistorySaveResult(StrictBaseModel):
    status: Literal["saved", "duplicate", "skipped_default", "skipped_empty", "failed"]
    run_id: str | None = None
    message: str


class RankingHistoryListResult(StrictBaseModel):
    items: list[RankingHistoryIndexItem] = Field(default_factory=list)
    error: str | None = None


class RankingHistorySnapshotResult(StrictBaseModel):
    snapshot: RankingHistorySnapshot | None = None
    error: str | None = None


class RankingHistoryMutationResult(StrictBaseModel):
    success: bool
    error: str | None = None
