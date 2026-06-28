from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping, Sequence

DEFAULT_INTERVAL_DAYS = 7
DEFAULT_RETRY_COOLDOWN_HOURS = 24
STALE_LOCK_HOURS = 24

EXIT_RUN = 0
EXIT_NOT_DUE = 10
EXIT_RETRY_COOLDOWN = 11
EXIT_LOCKED = 12
EXIT_ERROR = 20


@dataclass(frozen=True)
class MaintenanceState:
    last_success_at: str | None = None
    last_attempt_at: str | None = None
    last_exit_code: int | None = None
    last_log_path: str | None = None
    interval_days: int = DEFAULT_INTERVAL_DAYS
    retry_cooldown_hours: int = DEFAULT_RETRY_COOLDOWN_HOURS


@dataclass(frozen=True)
class MaintenanceDecision:
    should_run: bool
    exit_code: int
    reason: str
    last_success_at: str | None
    last_attempt_at: str | None
    next_due_at: str | None
    interval_days: int
    retry_cooldown_hours: int
    warnings: tuple[str, ...] = ()


def local_now() -> datetime:
    return datetime.now().astimezone()


def maintenance_settings(
    environ: Mapping[str, str] | None = None,
) -> tuple[int, int]:
    values = os.environ if environ is None else environ
    interval_days = _positive_int(
        values.get("SMAI_SYMBOL_MAINTENANCE_INTERVAL_DAYS"),
        default=DEFAULT_INTERVAL_DAYS,
        name="SMAI_SYMBOL_MAINTENANCE_INTERVAL_DAYS",
    )
    cooldown_hours = _positive_int(
        values.get("SMAI_SYMBOL_MAINTENANCE_RETRY_COOLDOWN_HOURS"),
        default=DEFAULT_RETRY_COOLDOWN_HOURS,
        name="SMAI_SYMBOL_MAINTENANCE_RETRY_COOLDOWN_HOURS",
    )
    return interval_days, cooldown_hours


def load_maintenance_state(path: Path) -> tuple[MaintenanceState, tuple[str, ...]]:
    if not path.exists():
        return MaintenanceState(), ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("state root must be an object")
        return (
            MaintenanceState(
                last_success_at=_optional_text(payload.get("last_success_at")),
                last_attempt_at=_optional_text(payload.get("last_attempt_at")),
                last_exit_code=_optional_int(payload.get("last_exit_code")),
                last_log_path=_optional_text(payload.get("last_log_path")),
                interval_days=_positive_int(
                    payload.get("interval_days"),
                    default=DEFAULT_INTERVAL_DAYS,
                    name="interval_days",
                ),
                retry_cooldown_hours=_positive_int(
                    payload.get("retry_cooldown_hours"),
                    default=DEFAULT_RETRY_COOLDOWN_HOURS,
                    name="retry_cooldown_hours",
                ),
            ),
            (),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return (
            MaintenanceState(),
            (f"State file is unreadable and will be treated as not run: {exc}",),
        )


def maintenance_decision(
    *,
    state_path: Path,
    lock_path: Path,
    now: datetime | None = None,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    retry_cooldown_hours: int = DEFAULT_RETRY_COOLDOWN_HOURS,
    force: bool = False,
) -> MaintenanceDecision:
    current = _aware_datetime(now or local_now())
    state, state_warnings = load_maintenance_state(state_path)
    warnings = list(state_warnings)

    if lock_path.exists():
        age = _lock_age(lock_path, current)
        if age is not None and age >= timedelta(hours=STALE_LOCK_HOURS):
            warnings.append(
                f"Maintenance lock is stale ({age.total_seconds() / 3600:.1f} hours) "
                "and was not removed automatically."
            )
        return _decision(
            False,
            EXIT_LOCKED,
            "maintenance lock exists",
            state,
            interval_days,
            retry_cooldown_hours,
            warnings,
        )

    if force:
        return _decision(
            True,
            EXIT_RUN,
            "manual force run",
            state,
            interval_days,
            retry_cooldown_hours,
            warnings,
        )

    last_attempt = _parse_timestamp(state.last_attempt_at, warnings, "last_attempt_at")
    if (
        state.last_exit_code is not None
        and state.last_exit_code != 0
        and last_attempt is not None
        and current - last_attempt < timedelta(hours=retry_cooldown_hours)
    ):
        return _decision(
            False,
            EXIT_RETRY_COOLDOWN,
            "previous failure is inside retry cooldown",
            state,
            interval_days,
            retry_cooldown_hours,
            warnings,
        )

    last_success = _parse_timestamp(state.last_success_at, warnings, "last_success_at")
    if last_success is None:
        return _decision(
            True,
            EXIT_RUN,
            "no successful maintenance is recorded",
            state,
            interval_days,
            retry_cooldown_hours,
            warnings,
        )

    next_due = last_success + timedelta(days=interval_days)
    if current >= next_due:
        return _decision(
            True,
            EXIT_RUN,
            "maintenance interval has elapsed",
            state,
            interval_days,
            retry_cooldown_hours,
            warnings,
            next_due=next_due,
        )
    return _decision(
        False,
        EXIT_NOT_DUE,
        "maintenance is not due",
        state,
        interval_days,
        retry_cooldown_hours,
        warnings,
        next_due=next_due,
    )


def begin_maintenance(
    *,
    state_path: Path,
    lock_path: Path,
    log_path: str,
    force: bool = False,
    now: datetime | None = None,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    retry_cooldown_hours: int = DEFAULT_RETRY_COOLDOWN_HOURS,
) -> MaintenanceDecision:
    current = _aware_datetime(now or local_now())
    decision = maintenance_decision(
        state_path=state_path,
        lock_path=lock_path,
        now=current,
        interval_days=interval_days,
        retry_cooldown_hours=retry_cooldown_hours,
        force=force,
    )
    if not decision.should_run:
        return decision

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_payload = {
        "created_at": current.isoformat(),
        "pid": os.getpid(),
        "log_path": log_path,
    }
    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o644,
        )
    except FileExistsError:
        return MaintenanceDecision(
            should_run=False,
            exit_code=EXIT_LOCKED,
            reason="maintenance lock was acquired by another process",
            last_success_at=decision.last_success_at,
            last_attempt_at=decision.last_attempt_at,
            next_due_at=decision.next_due_at,
            interval_days=interval_days,
            retry_cooldown_hours=retry_cooldown_hours,
            warnings=decision.warnings,
        )
    with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
        json.dump(lock_payload, lock_file, ensure_ascii=False, indent=2)
        lock_file.write("\n")
        lock_file.flush()
        os.fsync(lock_file.fileno())
    return decision


def finish_maintenance(
    *,
    state_path: Path,
    lock_path: Path,
    exit_code: int,
    log_path: str,
    now: datetime | None = None,
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    retry_cooldown_hours: int = DEFAULT_RETRY_COOLDOWN_HOURS,
) -> MaintenanceState:
    current = _aware_datetime(now or local_now())
    previous, _warnings = load_maintenance_state(state_path)
    state = MaintenanceState(
        last_success_at=(current.isoformat() if exit_code == 0 else previous.last_success_at),
        last_attempt_at=current.isoformat(),
        last_exit_code=exit_code,
        last_log_path=log_path,
        interval_days=interval_days,
        retry_cooldown_hours=retry_cooldown_hours,
    )
    _write_state_atomic(state_path, state)
    lock_path.unlink(missing_ok=True)
    return state


def _write_state_atomic(path: Path, state: MaintenanceState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(asdict(state), output, ensure_ascii=False, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def _decision(
    should_run: bool,
    exit_code: int,
    reason: str,
    state: MaintenanceState,
    interval_days: int,
    retry_cooldown_hours: int,
    warnings: Sequence[str],
    *,
    next_due: datetime | None = None,
) -> MaintenanceDecision:
    return MaintenanceDecision(
        should_run=should_run,
        exit_code=exit_code,
        reason=reason,
        last_success_at=state.last_success_at,
        last_attempt_at=state.last_attempt_at,
        next_due_at=next_due.isoformat() if next_due else None,
        interval_days=interval_days,
        retry_cooldown_hours=retry_cooldown_hours,
        warnings=tuple(warnings),
    )


def _lock_age(path: Path, now: datetime) -> timedelta | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        created_at = _parse_timestamp_value(payload.get("created_at"))
        if created_at is not None:
            return max(now - created_at, timedelta())
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    try:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        return max(now - modified_at, timedelta())
    except OSError:
        return None


def _parse_timestamp(
    value: str | None,
    warnings: list[str],
    field_name: str,
) -> datetime | None:
    if value is None:
        return None
    parsed = _parse_timestamp_value(value)
    if parsed is None:
        warnings.append(f"{field_name} is invalid and will be treated as missing.")
    return parsed


def _parse_timestamp_value(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _aware_datetime(datetime.fromisoformat(value.strip()))
    except ValueError:
        return None


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.astimezone()
    return value


def _positive_int(value: object, *, default: int, name: str) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(str(value))


def _print_decision(decision: MaintenanceDecision) -> None:
    print(f"[SMAI] Decision: {'run' if decision.should_run else 'skip'}")
    print(f"[SMAI] Reason: {decision.reason}")
    print(f"[SMAI] Last success: {decision.last_success_at or 'not recorded'}")
    print(f"[SMAI] Last attempt: {decision.last_attempt_at or 'not recorded'}")
    print(f"[SMAI] Next due: {decision.next_due_at or 'now / not available'}")
    print(f"[SMAI] Interval days: {decision.interval_days}")
    print(f"[SMAI] Retry cooldown hours: {decision.retry_cooldown_hours}")
    for warning in decision.warnings:
        print(f"[WARN] {warning}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage SMAI symbol maintenance state.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    begin = subparsers.add_parser("begin")
    begin.add_argument("--state", type=Path, required=True)
    begin.add_argument("--lock", type=Path, required=True)
    begin.add_argument("--log-path", required=True)
    begin.add_argument("--force", action="store_true")

    finish = subparsers.add_parser("finish")
    finish.add_argument("--state", type=Path, required=True)
    finish.add_argument("--lock", type=Path, required=True)
    finish.add_argument("--log-path", required=True)
    finish.add_argument("--exit-code", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        interval_days, cooldown_hours = maintenance_settings()
        if args.command == "begin":
            decision = begin_maintenance(
                state_path=args.state,
                lock_path=args.lock,
                log_path=args.log_path,
                force=args.force,
                interval_days=interval_days,
                retry_cooldown_hours=cooldown_hours,
            )
            _print_decision(decision)
            return decision.exit_code

        state = finish_maintenance(
            state_path=args.state,
            lock_path=args.lock,
            exit_code=args.exit_code,
            log_path=args.log_path,
            interval_days=interval_days,
            retry_cooldown_hours=cooldown_hours,
        )
        print(f"[SMAI] State updated: {args.state}")
        print(f"[SMAI] Last attempt: {state.last_attempt_at}")
        print(f"[SMAI] Last success: {state.last_success_at or 'unchanged / none'}")
        print(f"[SMAI] Exit code: {state.last_exit_code}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"[ERROR] Symbol maintenance state operation failed: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
