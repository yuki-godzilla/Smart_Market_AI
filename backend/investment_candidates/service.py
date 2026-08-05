"""UI-independent orchestration for investment-candidate ranking builds."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from .contracts import RankingBuildRequest, RankingBuildResult, RankingRow

ProgressReporter = Callable[[str, float], None]


class RankingBuildCacheReader(Protocol):
    def __call__(
        self,
        cache_key: str,
    ) -> tuple[list[RankingRow], list[RankingRow]] | None: ...


class RankingBuildCacheWriter(Protocol):
    def __call__(
        self,
        cache_key: str,
        *,
        rows: list[RankingRow],
        error_rows: list[RankingRow],
    ) -> None: ...


class RankingBuildPreflight(Protocol):
    def __call__(self, request: RankingBuildRequest) -> None: ...


class MarketDataRankingBuilder(Protocol):
    async def __call__(
        self,
        request: RankingBuildRequest,
        progress_callback: ProgressReporter,
    ) -> RankingBuildResult: ...


class MaintenanceOperationFactory(Protocol):
    def __call__(self, name: str) -> AbstractContextManager[None]: ...


class RankingBuildService:
    """Coordinate cache, symbol preflight and MarketData ranking execution.

    Framework-specific state and provider wiring stay at the application edge.
    This service owns the stable execution order and can run in a background
    thread without importing Streamlit.
    """

    def __init__(
        self,
        *,
        read_cache: RankingBuildCacheReader,
        write_cache: RankingBuildCacheWriter,
        preflight: RankingBuildPreflight,
        build_market_data: MarketDataRankingBuilder,
        maintenance_operation: MaintenanceOperationFactory,
    ) -> None:
        self._read_cache = read_cache
        self._write_cache = write_cache
        self._preflight = preflight
        self._build_market_data = build_market_data
        self._maintenance_operation = maintenance_operation

    def execute(
        self,
        request: RankingBuildRequest,
        progress_callback: ProgressReporter,
    ) -> RankingBuildResult:
        """Execute one ranking build without reading UI or session state."""

        progress_callback("ランキング対象と取得条件を確認しています。", 0.04)
        cached_build = self._read_cache(request.cache_key)
        if cached_build is not None and cached_build[0]:
            result = RankingBuildResult(
                rows=cached_build[0],
                error_rows=cached_build[1],
                reused_cache=True,
            )
            progress_callback("同じ条件の完成済みランキングを再利用しています。", 0.98)
        else:
            with self._maintenance_operation("ranking_build_preflight"):
                self._preflight(request)
            with self._maintenance_operation("ranking_build"):
                result = asyncio.run(self._build_market_data(request, progress_callback))

        self._write_cache(
            request.cache_key,
            rows=result.rows,
            error_rows=result.error_rows,
        )
        progress_callback("ランキング更新が完了しました。", 1.0)
        return result
