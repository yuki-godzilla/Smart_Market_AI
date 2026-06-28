from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools.symbol_maintenance_state import (
    EXIT_LOCKED,
    EXIT_NOT_DUE,
    EXIT_RETRY_COOLDOWN,
    EXIT_RUN,
    MaintenanceState,
    begin_maintenance,
    finish_maintenance,
    load_maintenance_state,
    maintenance_decision,
    maintenance_settings,
)

NOW = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)


def _write_state(path: Path, **overrides: object) -> None:
    payload = {
        "last_success_at": None,
        "last_attempt_at": None,
        "last_exit_code": None,
        "last_log_path": None,
        "interval_days": 7,
        "retry_cooldown_hours": 24,
        **overrides,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_state_is_due(tmp_path: Path) -> None:
    decision = maintenance_decision(
        state_path=tmp_path / "missing.json",
        lock_path=tmp_path / "missing.lock",
        now=NOW,
    )

    assert decision.should_run is True
    assert decision.exit_code == EXIT_RUN


def test_recent_success_is_not_due(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _write_state(state_path, last_success_at=(NOW - timedelta(days=2)).isoformat())

    decision = maintenance_decision(
        state_path=state_path,
        lock_path=tmp_path / "state.lock",
        now=NOW,
    )

    assert decision.should_run is False
    assert decision.exit_code == EXIT_NOT_DUE
    assert decision.next_due_at == (NOW + timedelta(days=5)).isoformat()


def test_old_success_is_due(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _write_state(state_path, last_success_at=(NOW - timedelta(days=8)).isoformat())

    decision = maintenance_decision(
        state_path=state_path,
        lock_path=tmp_path / "state.lock",
        now=NOW,
    )

    assert decision.should_run is True
    assert decision.exit_code == EXIT_RUN


def test_recent_failure_uses_retry_cooldown(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        last_attempt_at=(NOW - timedelta(hours=3)).isoformat(),
        last_exit_code=1,
    )

    decision = maintenance_decision(
        state_path=state_path,
        lock_path=tmp_path / "state.lock",
        now=NOW,
    )

    assert decision.should_run is False
    assert decision.exit_code == EXIT_RETRY_COOLDOWN


def test_lock_blocks_run_and_stale_lock_is_not_deleted(tmp_path: Path) -> None:
    lock_path = tmp_path / "state.lock"
    lock_path.write_text(
        json.dumps({"created_at": (NOW - timedelta(hours=30)).isoformat()}),
        encoding="utf-8",
    )

    decision = maintenance_decision(
        state_path=tmp_path / "state.json",
        lock_path=lock_path,
        now=NOW,
    )

    assert decision.exit_code == EXIT_LOCKED
    assert any("stale" in warning for warning in decision.warnings)
    assert lock_path.exists()


def test_broken_state_warns_and_runs_safely(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{broken", encoding="utf-8")

    decision = maintenance_decision(
        state_path=state_path,
        lock_path=tmp_path / "state.lock",
        now=NOW,
    )

    assert decision.should_run is True
    assert decision.warnings


def test_begin_is_atomic_and_finish_records_success(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    lock_path = tmp_path / "state.lock"
    decision = begin_maintenance(
        state_path=state_path,
        lock_path=lock_path,
        log_path="logs/maintenance/test.log",
        now=NOW,
    )

    assert decision.should_run is True
    assert lock_path.exists()
    second = begin_maintenance(
        state_path=state_path,
        lock_path=lock_path,
        log_path="logs/maintenance/test-2.log",
        now=NOW,
    )
    assert second.exit_code == EXIT_LOCKED

    state = finish_maintenance(
        state_path=state_path,
        lock_path=lock_path,
        exit_code=0,
        log_path="logs/maintenance/test.log",
        now=NOW,
    )

    assert state.last_success_at == NOW.isoformat()
    assert state.last_attempt_at == NOW.isoformat()
    assert state.last_exit_code == 0
    assert not lock_path.exists()
    loaded, warnings = load_maintenance_state(state_path)
    assert loaded == state
    assert warnings == ()


def test_failure_preserves_last_success_and_removes_lock(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    lock_path = tmp_path / "state.lock"
    previous_success = (NOW - timedelta(days=9)).isoformat()
    _write_state(state_path, last_success_at=previous_success, last_exit_code=0)
    lock_path.write_text("{}", encoding="utf-8")

    state = finish_maintenance(
        state_path=state_path,
        lock_path=lock_path,
        exit_code=7,
        log_path="logs/maintenance/failed.log",
        now=NOW,
    )

    assert state.last_success_at == previous_success
    assert state.last_attempt_at == NOW.isoformat()
    assert state.last_exit_code == 7
    assert not lock_path.exists()


def test_force_ignores_due_and_cooldown_but_not_lock(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        last_success_at=(NOW - timedelta(days=1)).isoformat(),
        last_attempt_at=(NOW - timedelta(hours=1)).isoformat(),
        last_exit_code=1,
    )

    decision = maintenance_decision(
        state_path=state_path,
        lock_path=tmp_path / "state.lock",
        now=NOW,
        force=True,
    )

    assert decision.should_run is True
    assert decision.reason == "manual force run"


def test_environment_settings_are_configurable() -> None:
    assert maintenance_settings(
        {
            "SMAI_SYMBOL_MAINTENANCE_INTERVAL_DAYS": "14",
            "SMAI_SYMBOL_MAINTENANCE_RETRY_COOLDOWN_HOURS": "36",
        }
    ) == (14, 36)
    assert MaintenanceState().interval_days == 7
