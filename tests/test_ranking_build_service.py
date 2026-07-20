from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import pytest

from backend.investment_candidates.contracts import RankingBuildRequest, RankingBuildResult
from backend.investment_candidates.service import RankingBuildService


def _request() -> RankingBuildRequest:
    return RankingBuildRequest(
        cache_key="ranking-cache-key",
        symbols=("7203.T", "AAPL"),
        start=date(2023, 7, 20),
        end=date(2026, 7, 20),
        provider="yahoo",
    )


def test_ranking_build_service_reuses_completed_cache_without_market_data() -> None:
    progress: list[tuple[str, float]] = []
    writes: list[tuple[str, list[dict[str, str]], list[dict[str, str]]]] = []

    def fail_preflight(_request: RankingBuildRequest) -> None:
        raise AssertionError("preflight must not run for a completed cache entry")

    async def fail_build(*_args: object) -> RankingBuildResult:
        raise AssertionError("MarketData build must not run for a completed cache entry")

    def fail_maintenance(_name: str):
        raise AssertionError("maintenance guard must not run for a completed cache entry")

    service = RankingBuildService(
        read_cache=lambda _key: ([{"symbol": "7203.T"}], [{"symbol": "AAPL"}]),
        write_cache=lambda key, *, rows, error_rows: writes.append((key, rows, error_rows)),
        preflight=fail_preflight,
        build_market_data=fail_build,
        maintenance_operation=fail_maintenance,
    )

    result = service.execute(_request(), lambda message, ratio: progress.append((message, ratio)))

    assert result.reused_cache is True
    assert result.rows == [{"symbol": "7203.T"}]
    assert result.error_rows == [{"symbol": "AAPL"}]
    assert writes == [("ranking-cache-key", [{"symbol": "7203.T"}], [{"symbol": "AAPL"}])]
    assert progress == [
        ("ランキング対象と取得条件を確認しています。", 0.04),
        ("同じ条件の完成済みランキングを再利用しています。", 0.98),
        ("ランキング更新が完了しました。", 1.0),
    ]


def test_ranking_build_service_runs_preflight_then_market_data_under_guards() -> None:
    events: list[str] = []
    writes: list[tuple[str, list[dict[str, str]], list[dict[str, str]]]] = []

    @contextmanager
    def maintenance(name: str):
        events.append(f"enter:{name}")
        try:
            yield
        finally:
            events.append(f"exit:{name}")

    def preflight(request: RankingBuildRequest) -> None:
        events.append(f"preflight:{','.join(request.symbols)}")

    async def build(
        request: RankingBuildRequest,
        progress_callback,
    ) -> RankingBuildResult:
        events.append(f"build:{request.provider}")
        progress_callback("価格データを整理しています。", 0.45)
        return RankingBuildResult(rows=[{"symbol": "7203.T"}], error_rows=[])

    service = RankingBuildService(
        read_cache=lambda _key: None,
        write_cache=lambda key, *, rows, error_rows: writes.append((key, rows, error_rows)),
        preflight=preflight,
        build_market_data=build,
        maintenance_operation=maintenance,
    )
    progress: list[tuple[str, float]] = []

    result = service.execute(_request(), lambda message, ratio: progress.append((message, ratio)))

    assert result.reused_cache is False
    assert events == [
        "enter:ranking_build_preflight",
        "preflight:7203.T,AAPL",
        "exit:ranking_build_preflight",
        "enter:ranking_build",
        "build:yahoo",
        "exit:ranking_build",
    ]
    assert writes == [("ranking-cache-key", [{"symbol": "7203.T"}], [])]
    assert progress[-2:] == [
        ("価格データを整理しています。", 0.45),
        ("ランキング更新が完了しました。", 1.0),
    ]


def test_ranking_build_service_does_not_publish_failed_market_data_result() -> None:
    writes: list[object] = []

    @contextmanager
    def maintenance(_name: str):
        yield

    async def fail_build(*_args: object) -> RankingBuildResult:
        raise RuntimeError("provider response must not be exposed by the job snapshot")

    service = RankingBuildService(
        read_cache=lambda _key: None,
        write_cache=lambda *args, **kwargs: writes.append((args, kwargs)),
        preflight=lambda _request: None,
        build_market_data=fail_build,
        maintenance_operation=maintenance,
    )

    with pytest.raises(RuntimeError, match="provider response"):
        service.execute(_request(), lambda _message, _ratio: None)

    assert writes == []
