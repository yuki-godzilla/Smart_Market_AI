from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.server_ops import maintenance
from backend.server_ops.maintenance import MaintenanceManager


def _manager(tmp_path: Path) -> MaintenanceManager:
    return MaintenanceManager(
        state_path=tmp_path / "state.json",
        activity_path=tmp_path / "activity.json",
        notice_path=tmp_path / "notice.json",
        intent_path=tmp_path / "intent.json",
        lock_roots=(tmp_path / "writes",),
    )


def test_maintenance_becomes_due_but_defers_for_active_session(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    started_at = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
    manager.record_startup(now=started_at)
    manager.heartbeat("session-1", now=started_at + timedelta(hours=24, minutes=1))

    decision = manager.evaluate(now=started_at + timedelta(hours=24, minutes=2))

    assert decision.due is True
    assert decision.safe_to_restart is False
    assert decision.active_sessions == 1
    assert "active_sessions" in decision.blockers


def test_maintenance_allows_restart_after_session_timeout(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    started_at = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
    manager.record_startup(now=started_at)
    manager.heartbeat("session-1", now=started_at + timedelta(hours=23))

    decision = manager.evaluate(now=started_at + timedelta(hours=24, minutes=1))

    assert decision.due is True
    assert decision.safe_to_restart is True
    assert decision.active_sessions == 0


def test_busy_operation_and_file_lock_both_block_restart(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    started_at = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
    manager.record_startup(now=started_at)
    manager.begin_operation(
        "ai_processing",
        now=started_at + timedelta(hours=24),
        pid=None,
    )
    lock_path = tmp_path / "writes" / "cache.lock"
    lock_path.parent.mkdir()
    lock_path.write_text("busy", encoding="utf-8")

    decision = manager.evaluate(now=started_at + timedelta(hours=24, minutes=1))

    assert decision.safe_to_restart is False
    assert "busy_operations" in decision.blockers
    assert "file_write_locks" in decision.blockers


def test_notice_is_published_and_cleared(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    now = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)

    manager.publish_notice(now=now)

    notice = manager.notice()
    assert notice is not None
    assert notice["restart_at"] == (now + timedelta(seconds=30)).isoformat()
    manager.clear_notice()
    assert manager.notice() is None


def test_corrupt_activity_state_fails_closed(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    started_at = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
    manager.record_startup(now=started_at)
    manager.activity_path.write_text("{broken", encoding="utf-8")

    decision = manager.evaluate(now=started_at + timedelta(hours=25))

    assert decision.safe_to_restart is False
    assert "activity_state_unavailable" in decision.blockers


def test_pid_check_treats_windows_system_error_as_stale(monkeypatch) -> None:
    def raise_system_error(_pid: int, _signal: int) -> None:
        raise SystemError("<class 'OSError'> returned a result with an exception set")

    monkeypatch.setattr(maintenance.os, "kill", raise_system_error)

    assert maintenance._posix_pid_exists(12345) is False


def test_pid_check_keeps_current_windows_process_active() -> None:
    if maintenance.os.name != "nt":
        return

    assert maintenance._pid_exists(maintenance.os.getpid()) is True


def test_atomic_write_retries_a_transient_windows_permission_error(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "state.json"
    real_replace = maintenance.os.replace
    attempts = 0

    def replace_after_transient_lock(source: str, destination: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, "Access is denied", str(destination))
        real_replace(source, destination)

    monkeypatch.setattr(maintenance.os, "replace", replace_after_transient_lock)
    monkeypatch.setattr(maintenance.time, "sleep", lambda _delay: None)

    maintenance._atomic_write(path, {"saved": True})

    assert attempts == 3
    assert maintenance._read_json(path) == {"saved": True}


def test_maintenance_operation_does_not_surface_cleanup_write_error(monkeypatch, caplog) -> None:
    class FailingCleanupManager:
        def begin_operation(self, _name: str) -> str:
            return "token"

        def end_operation(self, _token: str) -> None:
            raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(maintenance, "MaintenanceManager", FailingCleanupManager)

    with maintenance.maintenance_operation("ranking_build_preflight"):
        pass

    assert "Could not record maintenance operation end" in caplog.text


def test_drain_defers_until_sessions_operations_and_locks_are_clear(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    now = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)
    manager.record_startup(now=now)
    manager.heartbeat("session-1", now=now)
    manager.begin_operation("ranking_build", now=now, pid=None)
    lock_path = tmp_path / "writes" / "output.lock"
    lock_path.parent.mkdir()
    lock_path.write_text("busy", encoding="utf-8")

    decision = manager.evaluate_drain(now=now + timedelta(seconds=1))

    assert decision.safe_to_restart is False
    assert decision.active_sessions == 1
    assert decision.busy_operations == 1
    assert set(decision.blockers) == {
        "active_sessions",
        "busy_operations",
        "file_write_locks",
    }


def test_service_intent_round_trip_and_invalid_state_is_unknown(tmp_path: Path) -> None:
    intent_path = tmp_path / "intent.json"
    now = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)

    maintenance.write_service_intent(
        mode="manual_stop",
        path=intent_path,
        now=now,
    )
    assert maintenance.read_service_intent(intent_path)["status"] == "requested"  # type: ignore[index]
    assert maintenance.update_service_intent("draining", path=intent_path, now=now) is not None
    assert maintenance.read_service_intent(intent_path)["status"] == "draining"  # type: ignore[index]

    intent_path.write_text("{broken", encoding="utf-8")
    unknown = maintenance.read_service_intent(intent_path)
    assert unknown is not None
    assert unknown["mode"] == "unknown"
    assert unknown["status"] == "unknown"
