from __future__ import annotations

import asyncio
import time
from contextlib import nullcontext
from datetime import date

from ui import app as app_module
from ui.ranking_jobs import get_ranking_job, start_ranking_job


class _FailOnSessionStateAccess:
    def pop(self, *_args, **_kwargs):
        raise AssertionError("background ranking worker accessed Streamlit session state")

    def __setitem__(self, _key, _value):
        raise AssertionError("background ranking worker accessed Streamlit session state")


def test_unexpected_fundamental_error_does_not_abort_ranking_cohort(monkeypatch):
    class Adapter:
        async def fetch_fundamentals(self, symbols, as_of):
            if symbols == ["BROKEN.T"]:
                raise ValueError("unexpected provider payload")
            return []

    monkeypatch.setattr(
        app_module,
        "_get_cached_ranking_fundamentals",
        lambda *args, **kwargs: None,
    )

    fundamentals, errors = asyncio.run(
        app_module._fetch_ranking_fundamentals_tolerant(
            Adapter(),
            ["GOOD.T", "BROKEN.T"],
            provider="yahoo",
            as_of=date(2026, 7, 11),
            display_symbols_by_provider_symbol={
                "GOOD.T": ["GOOD.T"],
                "BROKEN.T": ["BROKEN.T"],
            },
        )
    )

    assert fundamentals == []
    assert len(errors) == 1
    assert errors[0]["symbol"] == "BROKEN.T"
    assert "unexpected provider payload" not in errors[0]["details"]
    assert "ValueError" in errors[0]["details"]


def test_market_data_ranking_worker_finishes_without_streamlit_session_state(monkeypatch):
    cached: list[tuple[list[dict[str, str]], list[dict[str, str]]]] = []

    async def fake_build(symbols, **kwargs):
        kwargs["progress_callback"]("価格データを整理しています。", 0.45)
        return ([{"symbol": symbols[0]}], [])

    monkeypatch.setattr(app_module, "get_cached_ranking_build", lambda _key: None)
    monkeypatch.setattr(app_module, "ranking_symbol_db_preflight_symbols", lambda symbols: symbols)
    monkeypatch.setattr(app_module, "ranking_symbol_db_preflight_limit", lambda _count: 1)
    monkeypatch.setattr(app_module, "_run_symbol_database_preflight_refresh", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "maintenance_operation", lambda _name: nullcontext())
    monkeypatch.setattr(app_module, "_build_market_data_ranking_rows", fake_build)
    monkeypatch.setattr(
        app_module,
        "set_cached_ranking_build",
        lambda _key, *, rows, error_rows: cached.append((rows, error_rows)),
    )

    start_ranking_job(
        "ranking-worker-no-session-state",
        lambda progress: app_module._execute_market_data_ranking_job(
            cache_key="ranking-worker-no-session-state",
            ranking_symbols=["7203.T"],
            start=date(2023, 7, 11),
            end=date(2026, 7, 11),
            provider="yahoo",
            progress_callback=progress,
        ),
    )
    deadline = time.monotonic() + 2
    completed = None
    while time.monotonic() < deadline:
        completed = get_ranking_job("ranking-worker-no-session-state")
        if completed is not None and completed.status != "running":
            break
        time.sleep(0.01)

    assert completed is not None
    assert completed.status == "completed"
    assert completed.rows == [{"symbol": "7203.T"}]
    assert cached == [([{"symbol": "7203.T"}], [])]


def test_ranking_preflight_can_run_without_streamlit_session_state(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "run_symbol_database_target_refresh",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        app_module,
        "sync_symbol_cache_to_official_metrics",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(app_module.st, "session_state", _FailOnSessionStateAccess())

    summary = app_module._run_symbol_database_preflight_refresh(
        ["7203.T"],
        context="ranking",
        max_items=1,
        update_session_state=False,
    )

    assert summary is not None
