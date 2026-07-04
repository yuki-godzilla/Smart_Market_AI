from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.server_ops.maintenance import MaintenanceManager


def _manager(tmp_path: Path) -> MaintenanceManager:
    return MaintenanceManager(
        state_path=tmp_path / "state.json",
        activity_path=tmp_path / "activity.json",
        notice_path=tmp_path / "notice.json",
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

