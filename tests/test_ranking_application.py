from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

from backend.investment_candidates.contracts import RankingBuildRequest, RankingBuildResult
from ui.ranking_application import execute_ranking_build_request, start_ranking_build_job
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
