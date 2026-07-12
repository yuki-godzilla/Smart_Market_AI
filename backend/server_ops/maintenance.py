from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Mapping, TypedDict

from filelock import FileLock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = PROJECT_ROOT / "data" / "ops" / "server_ops"
STATE_PATH = OPS_DIR / "maintenance_state.json"
ACTIVITY_PATH = OPS_DIR / "activity_state.json"
NOTICE_PATH = OPS_DIR / "maintenance_notice.json"
SERVICE_INTENT_PATH = OPS_DIR / "service_intent.json"
SESSION_TIMEOUT = timedelta(minutes=3)
MAINTENANCE_AFTER = timedelta(hours=24)
_ACTIVITY_LOCK = threading.RLock()
_WRITE_LOCK_TIMEOUT_SECONDS = 2
_REPLACE_RETRY_DELAYS_SECONDS = (0.025, 0.05, 0.1, 0.2, 0.4)
LOGGER = logging.getLogger(__name__)
SERVICE_MODES = {"manual_stop", "maintenance_restart", "unexpected_exit"}
SERVICE_STATUSES = {"requested", "draining", "stopped", "cancelled", "timed_out", "unknown"}
CLIENT_TYPES = {"desktop", "smartphone", "tablet", "unknown"}
_WINDOWS_ERROR_ACCESS_DENIED = 5
_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOWS_STILL_ACTIVE = 259


class ActivityState(TypedDict):
    """Persisted maintenance activity state with intentionally opaque entry values."""

    schema_version: int
    sessions: dict[str, object]
    operations: dict[str, object]
    updated_at: object


def normalize_client_type(value: object) -> str:
    """Keep only the small device category required for operations monitoring."""

    normalized = str(value or "").strip().casefold()
    aliases = {
        "pc": "desktop",
        "phone": "smartphone",
        "mobile": "smartphone",
        "ipad": "tablet",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in CLIENT_TYPES else "unknown"


def classify_client_type(user_agent: object) -> str:
    """Classify a request locally without persisting its raw User-Agent value."""

    value = str(user_agent or "").casefold()
    if not value:
        return "unknown"
    # iPadOS can identify as Macintosh in desktop-browser mode, while keeping
    # the Mobile token.  Evaluate it before desktop platforms.
    if any(token in value for token in ("ipad", "tablet", "kindle", "silk/", "playbook", "sm-t")):
        return "tablet"
    if "macintosh" in value and "mobile/" in value:
        return "tablet"
    if "android" in value:
        return "smartphone" if "mobile" in value else "tablet"
    if any(token in value for token in ("iphone", "ipod", "windows phone", "mobile", "mobi")):
        return "smartphone"
    if any(token in value for token in ("windows nt", "macintosh", "x11", "linux")):
        return "desktop"
    return "unknown"


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


def _write_lock_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.write.lock")


@contextmanager
def _exclusive_write_lock(path: Path) -> Iterator[None]:
    """Serialize state updates from separate Streamlit and worker processes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(_write_lock_path(path)), timeout=_WRITE_LOCK_TIMEOUT_SECONDS):
        yield


def _atomic_write_unlocked(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        for delay in (*_REPLACE_RETRY_DELAYS_SECONDS, None):
            try:
                os.replace(temp_name, path)
                break
            except PermissionError:
                if delay is None:
                    raise
                time.sleep(delay)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


def _atomic_write(path: Path, value: Mapping[str, object]) -> None:
    with _exclusive_write_lock(path):
        _atomic_write_unlocked(path, value)


@dataclass(frozen=True)
class MaintenanceDecision:
    due: bool
    safe_to_restart: bool
    uptime_seconds: int
    active_sessions: int
    busy_operations: int
    blockers: tuple[str, ...]


def read_service_intent(path: Path = SERVICE_INTENT_PATH) -> dict[str, object] | None:
    """Read the restart/stop intent, treating malformed state as unknown."""

    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "schema_version": 1,
            "mode": "unknown",
            "status": "unknown",
            "reason_code": "intent_unreadable",
        }
    if not isinstance(value, dict):
        return {
            "schema_version": 1,
            "mode": "unknown",
            "status": "unknown",
            "reason_code": "intent_invalid",
        }
    mode = value.get("mode")
    status = value.get("status")
    if mode not in SERVICE_MODES or status not in SERVICE_STATUSES:
        return {**value, "mode": "unknown", "status": "unknown", "reason_code": "intent_invalid"}
    return value


def write_service_intent(
    *,
    mode: str,
    status: str = "requested",
    requested_by: str = "local_operator",
    reason_code: str = "operator_requested",
    path: Path = SERVICE_INTENT_PATH,
    now: datetime | None = None,
    deadline_at: datetime | None = None,
) -> dict[str, object]:
    if mode not in SERVICE_MODES or status not in SERVICE_STATUSES:
        raise ValueError("Unsupported service intent mode or status")
    now = now or _utc_now()
    payload: dict[str, object] = {
        "schema_version": 1,
        "requested_at": _iso(now),
        "mode": mode,
        "requested_by": requested_by[:80],
        "reason_code": reason_code[:120],
        "status": status,
        "updated_at": _iso(now),
    }
    if deadline_at is not None:
        payload["deadline_at"] = _iso(deadline_at)
    _atomic_write(path, payload)
    return payload


def update_service_intent(
    status: str,
    *,
    path: Path = SERVICE_INTENT_PATH,
    now: datetime | None = None,
) -> dict[str, object] | None:
    if status not in SERVICE_STATUSES:
        raise ValueError("Unsupported service intent status")
    with _exclusive_write_lock(path):
        current = read_service_intent(path)
        if current is None or current.get("mode") == "unknown":
            return None
        current["status"] = status
        current["updated_at"] = _iso(now or _utc_now())
        _atomic_write_unlocked(path, current)
        return current


class MaintenanceManager:
    """Persist uptime and make conservative, fail-closed restart decisions."""

    def __init__(
        self,
        *,
        state_path: Path = STATE_PATH,
        activity_path: Path = ACTIVITY_PATH,
        notice_path: Path = NOTICE_PATH,
        intent_path: Path = SERVICE_INTENT_PATH,
        lock_roots: tuple[Path, ...] | None = None,
    ) -> None:
        self.state_path = state_path
        self.activity_path = activity_path
        self.notice_path = notice_path
        self.intent_path = intent_path
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
        self.clear_intent()

    def heartbeat(
        self,
        session_id: str,
        *,
        client_type: str = "unknown",
        now: datetime | None = None,
    ) -> None:
        now = now or _utc_now()
        with _ACTIVITY_LOCK, _exclusive_write_lock(self.activity_path):
            activity = self._clean_activity(now)
            sessions = dict(activity["sessions"])
            # Rewrite the record from the explicit monitoring contract.  In
            # particular, never carry forward an unknown field such as a raw
            # User-Agent from a manually edited or older activity-state file.
            sessions[session_id] = {
                "last_seen_at": _iso(now),
                "client_type": normalize_client_type(client_type),
                "connection_state": "connected",
            }
            activity["sessions"] = sessions
            activity["updated_at"] = _iso(now)
            _atomic_write_unlocked(self.activity_path, activity)

    def begin_operation(
        self, name: str, *, now: datetime | None = None, pid: int | None = None
    ) -> str:
        now = now or _utc_now()
        token = uuid.uuid4().hex
        with _ACTIVITY_LOCK, _exclusive_write_lock(self.activity_path):
            activity = self._clean_activity(now)
            operations = dict(activity["operations"])
            operations[token] = {
                "name": name,
                "started_at": _iso(now),
                "pid": pid if pid is not None else os.getpid(),
            }
            activity["operations"] = operations
            activity["updated_at"] = _iso(now)
            _atomic_write_unlocked(self.activity_path, activity)
        return token

    def end_operation(self, token: str, *, now: datetime | None = None) -> None:
        now = now or _utc_now()
        with _ACTIVITY_LOCK, _exclusive_write_lock(self.activity_path):
            activity = self._clean_activity(now)
            operations = dict(activity["operations"])
            operations.pop(token, None)
            activity["operations"] = operations
            activity["updated_at"] = _iso(now)
            _atomic_write_unlocked(self.activity_path, activity)

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

    def evaluate_drain(self, *, now: datetime | None = None) -> MaintenanceDecision:
        """Evaluate whether sessions, operations, and write locks have drained."""

        now = now or _utc_now()
        blockers: list[str] = []
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
        return MaintenanceDecision(
            due=True,
            safe_to_restart=not blockers,
            uptime_seconds=0,
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

    def clear_intent(self) -> None:
        try:
            self.intent_path.unlink()
        except FileNotFoundError:
            pass

    def _clean_activity(self, now: datetime) -> ActivityState:
        raw = _read_json(self.activity_path)
        sessions_raw = raw.get("sessions")
        operations_raw = raw.get("operations")
        sessions: dict[str, object] = {}
        for key, value in sessions_raw.items() if isinstance(sessions_raw, dict) else ():
            last_seen_at = value.get("last_seen_at") if isinstance(value, dict) else value
            seen = _parse(last_seen_at)
            if seen is not None and now - seen <= SESSION_TIMEOUT:
                sessions[str(key)] = value
        operations: dict[str, object] = {}
        for key, value in operations_raw.items() if isinstance(operations_raw, dict) else ():
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
        ignored = {
            self.state_path,
            self.activity_path,
            self.notice_path,
            self.intent_path,
            _write_lock_path(self.state_path),
            _write_lock_path(self.activity_path),
            _write_lock_path(self.notice_path),
            _write_lock_path(self.intent_path),
        }
        for root in self.lock_roots:
            if not root.exists():
                continue
            for pattern in ("*.lock", "*.tmp"):
                if any(path not in ignored for path in root.rglob(pattern)):
                    return True
        return False


def _windows_pid_exists(pid: int) -> bool:
    """Check a Windows process without using ``os.kill(pid, 0)``.

    On Windows, unlike POSIX, ``os.kill`` can terminate a process for signals
    other than Ctrl events.  Opening the process for limited query access is
    sufficient for the conservative maintenance drain decision.
    """

    try:
        import ctypes
        from ctypes import wintypes

        ctypes_win: Any = ctypes
        kernel32 = ctypes_win.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        open_process.restype = wintypes.HANDLE
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        get_exit_code_process = kernel32.GetExitCodeProcess
        get_exit_code_process.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        get_exit_code_process.restype = wintypes.BOOL

        handle = open_process(_WINDOWS_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # A protected process might exist but be unavailable to this
            # process; preserve the fail-closed maintenance policy.
            return ctypes_win.get_last_error() == _WINDOWS_ERROR_ACCESS_DENIED
        try:
            exit_code = wintypes.DWORD()
            if not get_exit_code_process(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == _WINDOWS_STILL_ACTIVE
        finally:
            close_handle(handle)
    except (AttributeError, OSError):
        # If the local process table cannot be queried, do not allow a restart
        # merely because the safety check was unavailable.
        return True


def _posix_pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, SystemError):
        return False
    return True


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_exists(pid)
    return _posix_pid_exists(pid)


@contextmanager
def maintenance_operation(name: str) -> Iterator[None]:
    manager = MaintenanceManager()
    try:
        token = manager.begin_operation(name)
    except OSError:
        LOGGER.warning("Could not record maintenance operation start: %s", name, exc_info=True)
        token = None
    try:
        yield
    finally:
        if token is not None:
            try:
                manager.end_operation(token)
            except OSError:
                # The operation remains recorded, so maintenance stays fail-closed.
                # Never let observability cleanup break the user-facing operation.
                LOGGER.warning(
                    "Could not record maintenance operation end: %s", name, exc_info=True
                )


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "startup",
            "evaluate",
            "drain",
            "notice",
            "clear-notice",
            "request-stop",
            "mark-intent",
        ),
    )
    parser.add_argument("--mode", choices=sorted(SERVICE_MODES), default="manual_stop")
    parser.add_argument("--status", choices=sorted(SERVICE_STATUSES), default="requested")
    parser.add_argument("--requested-by", default="local_operator")
    parser.add_argument("--reason-code", default="operator_requested")
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
    if args.action == "request-stop":
        write_service_intent(
            mode=args.mode,
            requested_by=args.requested_by,
            reason_code=args.reason_code,
        )
        return 0
    if args.action == "mark-intent":
        return 0 if update_service_intent(args.status) is not None else 1
    if args.action == "drain":
        decision = manager.evaluate_drain()
        print(json.dumps(asdict(decision), ensure_ascii=False))
        return 0 if decision.safe_to_restart else 20
    decision = manager.evaluate()
    print(json.dumps(asdict(decision), ensure_ascii=False))
    if not decision.due:
        return 10
    return 0 if decision.safe_to_restart else 20


if __name__ == "__main__":
    raise SystemExit(_main())
