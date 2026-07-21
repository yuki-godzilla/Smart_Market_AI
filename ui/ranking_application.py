"""Streamlit-independent adapters for the Ranking application flow."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Literal, MutableMapping, Protocol

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
        progress_callback: ProgressReporter | None,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]: ...


RankingRowsBuilder = LegacyMarketDataRankingBuilder
RankingProviderErrorRowsBuilder = Callable[[str, list[str], Exception], list[dict[str, str]]]
RankingLiveProviderChecker = Callable[[str], bool]
RankingProgressReporter = Callable[[ProgressReporter | None, str, float], None]


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


@dataclass(frozen=True)
class MarketDataRankingPipeline:
    """Route one Ranking build through its bounded live-data failure policy.

    Provider-specific fetch, feature, and score functions are injected at the
    application edge. This keeps the pipeline selection and fallback contract
    independent of Streamlit while preserving the established implementations.
    """

    is_live_provider: RankingLiveProviderChecker
    live_cohort_size: int
    build_large: RankingRowsBuilder
    build_fast: RankingRowsBuilder
    build_previews: RankingRowsBuilder
    provider_error_rows: RankingProviderErrorRowsBuilder
    app_error_type: type[Exception]
    report_progress: RankingProgressReporter

    async def build(
        self,
        symbols: list[str],
        *,
        start: date,
        end: date,
        provider: str,
        progress_callback: ProgressReporter | None = None,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        is_live = self.is_live_provider(provider)
        if is_live and len(symbols) > self.live_cohort_size:
            return await self.build_large(
                symbols,
                start=start,
                end=end,
                provider=provider,
                progress_callback=progress_callback,
            )
        try:
            return await self.build_fast(
                symbols,
                start=start,
                end=end,
                provider=provider,
                progress_callback=progress_callback,
            )
        except self.app_error_type as exc:
            if is_live:
                self.report_progress(
                    progress_callback,
                    "Yahoo live data の一括取得に失敗しました。",
                    1.0,
                )
                return [], self.provider_error_rows(provider, symbols, exc)
            return await self.build_previews(
                symbols,
                start=start,
                end=end,
                provider=provider,
                progress_callback=progress_callback,
            )


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
