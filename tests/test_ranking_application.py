from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import date
from typing import Any

from backend.investment_candidates.contracts import RankingBuildRequest, RankingBuildResult
from ui.ranking_application import (
    MarketDataRankingPipeline,
    RankingJobSessionKeys,
    adopt_completed_ranking_job,
    execute_ranking_build_request,
    start_ranking_build_job,
)
from ui.ranking_jobs import RankingJobSnapshot


def _request() -> RankingBuildRequest:
    return RankingBuildRequest(
        cache_key="ranking-typed-request",
        symbols=("7203.T", "AAPL"),
        start=date(2024, 7, 20),
        end=date(2026, 7, 20),
        provider="yahoo",
    )


def test_ranking_application_adapts_preflight_and_market_data_builder() -> None:
    events: list[Any] = []

    @contextmanager
    def maintenance(name: str):
        events.append(("enter", name))
        try:
            yield
        finally:
            events.append(("exit", name))

    def run_preflight(symbols, **kwargs):
        events.append(("preflight", list(symbols), kwargs))

    async def build_market_data(symbols, **kwargs):
        events.append(("build", list(symbols), kwargs))
        return [{"symbol": symbols[0]}], [{"symbol": symbols[1]}]

    writes: list[tuple[str, list[dict[str, str]], list[dict[str, str]]]] = []
    result = execute_ranking_build_request(
        _request(),
        lambda _message, _ratio: None,
        read_cache=lambda _key: None,
        write_cache=lambda key, *, rows, error_rows: writes.append((key, rows, error_rows)),
        resolve_preflight_symbols=lambda symbols: list(reversed(symbols)),
        resolve_preflight_limit=lambda count: count - 1,
        run_preflight=run_preflight,
        build_market_data=build_market_data,
        maintenance_operation=maintenance,
    )

    assert result.rows == [{"symbol": "7203.T"}]
    assert result.error_rows == [{"symbol": "AAPL"}]
    assert writes == [("ranking-typed-request", [{"symbol": "7203.T"}], [{"symbol": "AAPL"}])]
    assert events[0:3] == [
        ("enter", "ranking_build_preflight"),
        (
            "preflight",
            ["AAPL", "7203.T"],
            {"context": "ranking", "max_items": 1, "update_session_state": False},
        ),
        ("exit", "ranking_build_preflight"),
    ]
    build_event = events[4]
    assert build_event[0:2] == ("build", ["7203.T", "AAPL"])
    assert build_event[2]["start"] == date(2024, 7, 20)
    assert build_event[2]["end"] == date(2026, 7, 20)
    assert build_event[2]["provider"] == "yahoo"


def test_ranking_job_controller_keeps_typed_request_until_worker_execution() -> None:
    request = _request()
    received: list[RankingBuildRequest] = []

    def execute(build_request, progress_callback):
        received.append(build_request)
        progress_callback("実行中", 0.5)
        return RankingBuildResult(rows=[{"symbol": "7203.T"}], error_rows=[])

    def start_job(cache_key, worker):
        rows, error_rows = worker(lambda _message, _ratio: None)
        assert cache_key == request.cache_key
        assert rows == [{"symbol": "7203.T"}]
        assert error_rows == []
        return RankingJobSnapshot(
            job_id="job-1",
            cache_key=cache_key,
            status="completed",
            message="完了",
            ratio=1.0,
            rows=rows,
            error_rows=error_rows,
            error_type="",
            started_at=1.0,
            updated_at=2.0,
        )

    snapshot = start_ranking_build_job(
        request,
        start_job=start_job,
        execute_request=execute,
    )

    assert snapshot.job_id == "job-1"
    assert received == [request]


def test_completed_ranking_job_adoption_updates_one_browser_session_once() -> None:
    session_keys = RankingJobSessionKeys(
        rows="rows",
        error_rows="errors",
        source="source",
        updated_at="updated_at",
        adopted_job_id="adopted_job_id",
        history_pending_job_id="history_pending_job_id",
    )
    job = RankingJobSnapshot(
        job_id="job-1",
        cache_key="ranking-typed-request",
        status="completed",
        message="完了",
        ratio=1.0,
        rows=[{"symbol": "7203.T"}],
        error_rows=[{"symbol": "AAPL"}],
        error_type="",
        started_at=1.0,
        updated_at=2.0,
    )
    session_state: dict[str, object] = {"unrelated": "kept"}

    assert adopt_completed_ranking_job(
        job,
        cache_key="ranking-typed-request",
        session_state=session_state,
        session_keys=session_keys,
        updated_at="2026-07-21 12:34",
    )
    assert session_state == {
        "unrelated": "kept",
        "rows": [{"symbol": "7203.T"}],
        "errors": [{"symbol": "AAPL"}],
        "source": "ranking-typed-request",
        "updated_at": "2026-07-21 12:34",
        "adopted_job_id": "job-1",
        "history_pending_job_id": "job-1",
    }
    assert not adopt_completed_ranking_job(
        job,
        cache_key="ranking-typed-request",
        session_state=session_state,
        session_keys=session_keys,
        updated_at="later",
    )
    assert session_state["updated_at"] == "2026-07-21 12:34"


def test_ranking_job_adoption_rejects_non_matching_or_non_completed_job() -> None:
    session_keys = RankingJobSessionKeys(
        "rows", "errors", "source", "updated", "adopted", "history"
    )
    session_state: dict[str, object] = {}
    running = RankingJobSnapshot(
        job_id="job-1",
        cache_key="ranking-typed-request",
        status="running",
        message="実行中",
        ratio=0.5,
        rows=[],
        error_rows=[],
        error_type="",
        started_at=1.0,
        updated_at=2.0,
    )

    assert not adopt_completed_ranking_job(
        running,
        cache_key="ranking-typed-request",
        session_state=session_state,
        session_keys=session_keys,
        updated_at="now",
    )
    completed_elsewhere = RankingJobSnapshot(
        job_id=running.job_id,
        cache_key="other-cache",
        status="completed",
        message=running.message,
        ratio=1.0,
        rows=running.rows,
        error_rows=running.error_rows,
        error_type=running.error_type,
        started_at=running.started_at,
        updated_at=running.updated_at,
    )
    assert not adopt_completed_ranking_job(
        completed_elsewhere,
        cache_key="ranking-typed-request",
        session_state=session_state,
        session_keys=session_keys,
        updated_at="now",
    )
    assert session_state == {}


def test_market_data_ranking_pipeline_uses_live_cohorts_above_limit() -> None:
    calls: list[str] = []

    async def build_large(symbols, **_kwargs):
        calls.append(f"large:{','.join(symbols)}")
        return [{"symbol": symbols[0]}], []

    async def unexpected_builder(*_args, **_kwargs):
        raise AssertionError("unexpected pipeline route")

    pipeline = MarketDataRankingPipeline(
        is_live_provider=lambda provider: provider == "yahoo",
        live_cohort_size=1,
        build_large=build_large,
        build_fast=unexpected_builder,
        build_previews=unexpected_builder,
        provider_error_rows=lambda _provider, _symbols, _exc: [],
        app_error_type=RuntimeError,
        report_progress=lambda _message, _ratio: None,
    )

    rows, errors = asyncio.run(
        pipeline.build(
            ["7203.T", "AAPL"],
            start=date(2024, 7, 20),
            end=date(2026, 7, 20),
            provider="yahoo",
        )
    )

    assert rows == [{"symbol": "7203.T"}]
    assert errors == []
    assert calls == ["large:7203.T,AAPL"]


def test_market_data_ranking_pipeline_falls_back_or_fails_closed_by_provider() -> None:
    progress: list[tuple[str, float]] = []

    async def fail_fast(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    async def previews(symbols, **_kwargs):
        return [{"symbol": symbols[0]}], []

    pipeline = MarketDataRankingPipeline(
        is_live_provider=lambda provider: provider == "yahoo",
        live_cohort_size=100,
        build_large=previews,
        build_fast=fail_fast,
        build_previews=previews,
        provider_error_rows=lambda provider, symbols, _exc: [
            {"provider": provider, "symbol": ",".join(symbols)}
        ],
        app_error_type=RuntimeError,
        report_progress=lambda _callback, message, ratio: progress.append((message, ratio)),
    )

    preview_rows, preview_errors = asyncio.run(
        pipeline.build(
            ["7203.T"],
            start=date(2024, 7, 20),
            end=date(2026, 7, 20),
            provider="fixture",
        )
    )
    live_rows, live_errors = asyncio.run(
        pipeline.build(
            ["7203.T"],
            start=date(2024, 7, 20),
            end=date(2026, 7, 20),
            provider="yahoo",
        )
    )

    assert preview_rows == [{"symbol": "7203.T"}]
    assert preview_errors == []
    assert live_rows == []
    assert live_errors == [{"provider": "yahoo", "symbol": "7203.T"}]
    assert progress == [("Yahoo live data の一括取得に失敗しました。", 1.0)]
