"""Streamlit-independent adapters for the Ranking application flow."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, MutableMapping, Protocol

from backend.investment_candidates.contracts import RankingBuildRequest, RankingBuildResult
from backend.investment_candidates.service import (
    MaintenanceOperationFactory,
    ProgressReporter,
    RankingBuildCacheReader,
    RankingBuildCacheWriter,
    RankingBuildService,
)
from ui.ranking_jobs import (
    RankingJobSnapshot,
    RankingProgressCallback,
    RankingRows,
    RankingWorker,
)


class RankingPreflightSymbolsResolver(Protocol):
    def __call__(self, symbols: Sequence[str]) -> list[str]: ...


class RankingPreflightLimitResolver(Protocol):
    def __call__(self, symbol_count: int) -> int: ...


class RankingPreflightRunner(Protocol):
    def __call__(
        self,
        symbols: Sequence[str],
        *,
        context: Literal["ranking"],
        max_items: int,
        update_session_state: bool,
    ) -> object | None: ...


class LegacyMarketDataRankingBuilder(Protocol):
    async def __call__(
        self,
        symbols: list[str],
        *,
        start: date,
        end: date,
        provider: str,
        progress_callback: ProgressReporter,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]: ...


class RankingJobStarter(Protocol):
    def __call__(self, cache_key: str, worker: RankingWorker) -> RankingJobSnapshot: ...


class RankingRequestExecutor(Protocol):
    def __call__(
        self,
        request: RankingBuildRequest,
        progress_callback: RankingProgressCallback,
    ) -> RankingBuildResult: ...


@dataclass(frozen=True)
class RankingJobSessionKeys:
    """Session-state keys owned by the Streamlit Ranking controller."""

    rows: str
    error_rows: str
    source: str
    updated_at: str
    adopted_job_id: str
    history_pending_job_id: str


@dataclass(frozen=True)
class RankingPreflightAdapter:
    resolve_symbols: RankingPreflightSymbolsResolver
    resolve_limit: RankingPreflightLimitResolver
    run: RankingPreflightRunner

    def __call__(self, request: RankingBuildRequest) -> None:
        symbols = list(request.symbols)
        self.run(
            self.resolve_symbols(symbols),
            context="ranking",
            max_items=self.resolve_limit(len(symbols)),
            update_session_state=False,
        )


@dataclass(frozen=True)
class MarketDataRankingBuilderAdapter:
    build_rows: LegacyMarketDataRankingBuilder

    async def __call__(
        self,
        request: RankingBuildRequest,
        progress_callback: ProgressReporter,
    ) -> RankingBuildResult:
        rows, error_rows = await self.build_rows(
            list(request.symbols),
            start=request.start,
            end=request.end,
            provider=request.provider,
            progress_callback=progress_callback,
        )
        return RankingBuildResult(rows=rows, error_rows=error_rows)


def execute_ranking_build_request(
    request: RankingBuildRequest,
    progress_callback: ProgressReporter,
    *,
    read_cache: RankingBuildCacheReader,
    write_cache: RankingBuildCacheWriter,
    resolve_preflight_symbols: RankingPreflightSymbolsResolver,
    resolve_preflight_limit: RankingPreflightLimitResolver,
    run_preflight: RankingPreflightRunner,
    build_market_data: LegacyMarketDataRankingBuilder,
    maintenance_operation: MaintenanceOperationFactory,
) -> RankingBuildResult:
    """Adapt established edge functions to the backend-owned build service."""

    service = RankingBuildService(
        read_cache=read_cache,
        write_cache=write_cache,
        preflight=RankingPreflightAdapter(
            resolve_symbols=resolve_preflight_symbols,
            resolve_limit=resolve_preflight_limit,
            run=run_preflight,
        ),
        build_market_data=MarketDataRankingBuilderAdapter(build_rows=build_market_data),
        maintenance_operation=maintenance_operation,
    )
    return service.execute(request, progress_callback)


def start_ranking_build_job(
    request: RankingBuildRequest,
    *,
    start_job: RankingJobStarter,
    execute_request: RankingRequestExecutor,
) -> RankingJobSnapshot:
    """Launch a typed request through the existing process-wide job registry."""

    def worker(progress_callback: RankingProgressCallback) -> RankingRows:
        return execute_request(request, progress_callback).as_legacy_tuple()

    return start_job(request.cache_key, worker)


def adopt_completed_ranking_job(
    job: RankingJobSnapshot,
    *,
    cache_key: str,
    session_state: MutableMapping[str, Any],
    session_keys: RankingJobSessionKeys,
    updated_at: str,
) -> bool:
    """Adopt one completed process-wide job into a browser session exactly once.

    The worker result is immutable process-wide state. This controller adapter
    keeps per-browser adoption, history handoff, and timestamp state out of the
    Streamlit view while preserving the existing session-state contract.
    """

    if job.status != "completed" or job.cache_key != cache_key:
        return False
    if str(session_state.get(session_keys.adopted_job_id) or "") == job.job_id:
        return False

    session_state[session_keys.rows] = job.rows
    session_state[session_keys.error_rows] = job.error_rows
    session_state[session_keys.source] = cache_key
    session_state[session_keys.updated_at] = updated_at
    session_state[session_keys.adopted_job_id] = job.job_id
    session_state[session_keys.history_pending_job_id] = job.job_id
    return True
