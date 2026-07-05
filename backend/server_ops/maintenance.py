from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = PROJECT_ROOT / "data" / "ops" / "server_ops"
STATE_PATH = OPS_DIR / "maintenance_state.json"
ACTIVITY_PATH = OPS_DIR / "activity_state.json"
NOTICE_PATH = OPS_DIR / "maintenance_notice.json"
SESSION_TIMEOUT = timedelta(minutes=3)
MAINTENANCE_AFTER = timedelta(hours=24)
_ACTIVITY_LOCK = threading.RLock()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class MaintenanceDecision:
    due: bool
    safe_to_restart: bool
    uptime_seconds: int
    active_sessions: int
    busy_operations: int
    blockers: tuple[str, ...]


class MaintenanceManager:
    """Persist uptime and make conservative, fail-closed restart decisions."""

    def __init__(
        self,
        *,
        state_path: Path = STATE_PATH,
        activity_path: Path = ACTIVITY_PATH,
        notice_path: Path = NOTICE_PATH,
        lock_roots: tuple[Path, ...] | None = None,
    ) -> None:
        self.state_path = state_path
        self.activity_path = activity_path
        self.notice_path = notice_path
        self.lock_roots = lock_roots or (PROJECT_ROOT / "data", PROJECT_ROOT / "logs")

    def record_startup(self, *, now: datetime | None = None) -> None:
        now = now or _utc_now()
        _atomic_write(
            self.state_path,
            {
                "schema_version": 1,
                "started_at": _iso(now),
                "maintenance_pending": False,
                "last_checked_at": _iso(now),
            },
        )
        self.clear_notice()

    def heartbeat(self, session_id: str, *, now: datetime | None = None) -> None:
        now = now or _utc_now()
        with _ACTIVITY_LOCK:
            activity = self._clean_activity(now)
            sessions = dict(activity["sessions"])
            sessions[session_id] = _iso(now)
            activity["sessions"] = sessions
            activity["updated_at"] = _iso(now)
            _atomic_write(self.activity_path, activity)

    def begin_operation(
        self, name: str, *, now: datetime | None = None, pid: int | None = None
    ) -> str:
        now = now or _utc_now()
        token = uuid.uuid4().hex
        with _ACTIVITY_LOCK:
            activity = self._clean_activity(now)
            operations = dict(activity["operations"])
            operations[token] = {
                "name": name,
                "started_at": _iso(now),
                "pid": pid if pid is not None else os.getpid(),
            }
            activity["operations"] = operations
            activity["updated_at"] = _iso(now)
            _atomic_write(self.activity_path, activity)
        return token

    def end_operation(self, token: str, *, now: datetime | None = None) -> None:
        now = now or _utc_now()
        with _ACTIVITY_LOCK:
            activity = self._clean_activity(now)
            operations = dict(activity["operations"])
            operations.pop(token, None)
            activity["operations"] = operations
            activity["updated_at"] = _iso(now)
            _atomic_write(self.activity_path, activity)

    def evaluate(self, *, now: datetime | None = None) -> MaintenanceDecision:
        now = now or _utc_now()
        state = _read_json(self.state_path)
        started_at = _parse(state.get("started_at"))
        blockers: list[str] = []
        if started_at is None or started_at > now:
            blockers.append("startup_time_unavailable")
            uptime = timedelta(0)
        else:
            uptime = now - started_at
        due = uptime >= MAINTENANCE_AFTER
        if self.activity_path.exists() and not _read_json(self.activity_path):
            blockers.append("activity_state_unavailable")
        activity = self._clean_activity(now)
        sessions = dict(activity["sessions"])
        operations = dict(activity["operations"])
        if sessions:
            blockers.append("active_sessions")
        if operations:
            blockers.append("busy_operations")
        if self._has_write_locks():
            blockers.append("file_write_locks")
        state.update(
            {
                "schema_version": 1,
                "last_checked_at": _iso(now),
                "maintenance_pending": due,
                "uptime_seconds": int(uptime.total_seconds()),
                "last_blockers": blockers,
            }
        )
        _atomic_write(self.state_path, state)
        return MaintenanceDecision(
            due=due,
            safe_to_restart=due and not blockers,
            uptime_seconds=int(uptime.total_seconds()),
            active_sessions=len(sessions),
            busy_operations=len(operations),
            blockers=tuple(blockers),
        )

    def publish_notice(self, *, now: datetime | None = None, delay_seconds: int = 30) -> None:
        now = now or _utc_now()
        _atomic_write(
            self.notice_path,
            {
                "schema_version": 1,
                "created_at": _iso(now),
                "restart_at": _iso(now + timedelta(seconds=delay_seconds)),
                "message": "SMAIの安定運用のため30秒後にメンテナンス再起動を行います。",
            },
        )

    def notice(self) -> dict[str, object] | None:
        value = _read_json(self.notice_path)
        return value or None

    def clear_notice(self) -> None:
        try:
            self.notice_path.unlink()
        except FileNotFoundError:
            pass

    def _clean_activity(self, now: datetime) -> dict[str, object]:
        raw = _read_json(self.activity_path)
        sessions_raw = raw.get("sessions")
        operations_raw = raw.get("operations")
        sessions = {
            str(key): value
            for key, value in (sessions_raw.items() if isinstance(sessions_raw, dict) else ())
            if (seen := _parse(value)) is not None and now - seen <= SESSION_TIMEOUT
        }
        operations: dict[str, object] = {}
        for key, value in (
            operations_raw.items() if isinstance(operations_raw, dict) else ()
        ):
            if not isinstance(value, dict):
                continue
            started_at = _parse(value.get("started_at"))
            if started_at is None:
                continue
            pid = value.get("pid")
            if isinstance(pid, int) and not _pid_exists(pid):
                continue
            operations[str(key)] = value
        return {
            "schema_version": 1,
            "sessions": sessions,
            "operations": operations,
            "updated_at": raw.get("updated_at"),
        }

    def _has_write_locks(self) -> bool:
        ignored = {self.state_path, self.activity_path, self.notice_path}
        for root in self.lock_roots:
            if not root.exists():
                continue
            for pattern in ("*.lock", "*.tmp"):
                if any(path not in ignored for path in root.rglob(pattern)):
                    return True
        return False


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, SystemError):
        return False
    return True


@contextmanager
def maintenance_operation(name: str) -> Iterator[None]:
    manager = MaintenanceManager()
    token = manager.begin_operation(name)
    try:
        yield
    finally:
        manager.end_operation(token)


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("startup", "evaluate", "notice", "clear-notice"))
    args = parser.parse_args()
    manager = MaintenanceManager()
    if args.action == "startup":
        manager.record_startup()
        return 0
    if args.action == "notice":
        manager.publish_notice()
        return 0
    if args.action == "clear-notice":
        manager.clear_notice()
        return 0
    decision = manager.evaluate()
    print(json.dumps(asdict(decision), ensure_ascii=False))
    if not decision.due:
        return 10
    return 0 if decision.safe_to_restart else 20


if __name__ == "__main__":
    raise SystemExit(_main())
