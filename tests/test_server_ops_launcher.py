from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from backend.server_ops.launcher import (
    EXIT_INTERRUPTED,
    ServerLockUnavailable,
    consume_supervisor_stop_request,
    is_smai_healthy,
    optimized_child_environment,
    resilient_restart_delay,
    server_lock,
    should_leave_resilient_launcher,
    streamlit_command,
    streamlit_creation_flags,
    supervise_streamlit,
    wait_for_streamlit,
)


def test_optimized_child_environment_bounds_nested_numerical_threads() -> None:
    environment = optimized_child_environment({"PATH": "test"})

    assert environment["OPENBLAS_NUM_THREADS"] == "1"
    assert environment["OMP_NUM_THREADS"] == "1"
    assert environment["MKL_NUM_THREADS"] == "1"
    assert environment["NUMEXPR_MAX_THREADS"] == "4"


def test_optimized_child_environment_preserves_operator_override() -> None:
    environment = optimized_child_environment({"OPENBLAS_NUM_THREADS": "2"})

    assert environment["OPENBLAS_NUM_THREADS"] == "2"


def test_resilient_restart_delay_uses_bounded_exponential_backoff() -> None:
    assert [resilient_restart_delay(index) for index in range(7)] == [
        2.0,
        4.0,
        8.0,
        16.0,
        32.0,
        60.0,
        60.0,
    ]


def test_streamlit_command_uses_expected_lan_settings() -> None:
    command = streamlit_command("192.168.1.20")

    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert "ui/app.py" in command
    assert command[command.index("--server.address") + 1] == "0.0.0.0"
    assert command[command.index("--server.port") + 1] == "8501"
    assert command[command.index("--server.headless") + 1] == "true"
    assert command[command.index("--server.runOnSave") + 1] == "false"
    assert command[command.index("--browser.serverAddress") + 1] == "192.168.1.20"


def test_server_lock_allows_only_one_launcher_and_is_reusable() -> None:
    lock_path = Path("data/ops/server_ops") / f"test-streamlit-{uuid4().hex}.lock"
    try:
        with server_lock(lock_path):
            with pytest.raises(ServerLockUnavailable):
                with server_lock(lock_path):
                    pass

        with server_lock(lock_path):
            pass
    finally:
        lock_path.unlink(missing_ok=True)


def test_resilient_wait_ignores_console_interrupt() -> None:
    class Process:
        def __init__(self) -> None:
            self.wait_count = 0

        def wait(self, timeout=None) -> int:
            self.wait_count += 1
            if self.wait_count == 1:
                raise KeyboardInterrupt
            return 0

        def poll(self):
            return None

    process = Process()

    assert wait_for_streamlit(process, resilient=True) == 0  # type: ignore[arg-type]
    assert process.wait_count == 2


def test_non_resilient_wait_stops_streamlit_after_console_interrupt() -> None:
    class Process:
        def __init__(self) -> None:
            self.wait_count = 0
            self.terminated = False

        def wait(self, timeout=None) -> int:
            self.wait_count += 1
            if self.wait_count == 1:
                raise KeyboardInterrupt
            return 130

        def terminate(self) -> None:
            self.terminated = True

    process = Process()

    assert wait_for_streamlit(process, resilient=False) == EXIT_INTERRUPTED  # type: ignore[arg-type]
    assert process.terminated is True


def test_resilient_creation_flags_are_windows_only(monkeypatch) -> None:
    monkeypatch.setattr("backend.server_ops.launcher.sys.platform", "linux")

    assert streamlit_creation_flags(resilient=True) == 0


def test_resilient_wait_returns_when_child_already_stopped() -> None:
    class Process:
        def wait(self, timeout=None) -> int:
            raise KeyboardInterrupt

        def poll(self) -> int:
            return 1

    assert wait_for_streamlit(Process(), resilient=True) == 1  # type: ignore[arg-type]


def test_resilient_supervisor_restarts_after_clean_streamlit_exit(monkeypatch) -> None:
    starts: list[object] = []

    class Process:
        pass

    def fake_popen(*_args, **_kwargs):
        process = Process()
        starts.append(process)
        if len(starts) == 3:
            raise RuntimeError("stop test loop")
        return process

    monkeypatch.setattr("backend.server_ops.launcher.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "backend.server_ops.launcher.wait_for_streamlit", lambda *_args, **_kwargs: 0
    )
    monkeypatch.setattr("backend.server_ops.launcher.time.sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="stop test loop"):
        supervise_streamlit("localhost", resilient=True)

    assert len(starts) == 3


def test_resilient_supervisor_leaves_after_explicit_stop_request(
    monkeypatch, tmp_path: Path
) -> None:
    request_path = tmp_path / "streamlit.stop"
    request_path.write_text("maintenance_restart", encoding="ascii")

    monkeypatch.setattr(
        "backend.server_ops.launcher.subprocess.Popen",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "backend.server_ops.launcher.wait_for_streamlit", lambda *_args, **_kwargs: 0
    )
    monkeypatch.setattr(
        "backend.server_ops.launcher.consume_supervisor_stop_request",
        lambda *_args, **_kwargs: consume_supervisor_stop_request(request_path),
    )

    assert supervise_streamlit("localhost", resilient=True) == 0
    assert not request_path.exists()


def test_missing_supervisor_stop_request_is_not_consumed(tmp_path: Path) -> None:
    assert consume_supervisor_stop_request(tmp_path / "missing.stop") is False


def test_manual_stop_intent_suppresses_resilient_restart(tmp_path: Path) -> None:
    request_path = tmp_path / "streamlit.stop"
    intent_path = tmp_path / "service_intent.json"
    request_path.write_text("manual_stop", encoding="ascii")
    intent_path.write_text(
        '{"schema_version": 1, "mode": "manual_stop", "status": "requested"}',
        encoding="utf-8",
    )

    assert (
        should_leave_resilient_launcher(
            stop_path=request_path,
            intent_path=intent_path,
        )
        is True
    )
    assert not request_path.exists()


def test_unexpected_exit_intent_allows_resilient_restart(tmp_path: Path) -> None:
    intent_path = tmp_path / "service_intent.json"
    intent_path.write_text(
        '{"schema_version": 1, "mode": "unexpected_exit", "status": "requested"}',
        encoding="utf-8",
    )

    assert (
        should_leave_resilient_launcher(
            stop_path=tmp_path / "missing.stop",
            intent_path=intent_path,
        )
        is False
    )


def test_unknown_intent_is_fail_closed_for_resilient_restart(tmp_path: Path) -> None:
    intent_path = tmp_path / "service_intent.json"
    intent_path.write_text("{broken", encoding="utf-8")

    assert (
        should_leave_resilient_launcher(
            stop_path=tmp_path / "missing.stop",
            intent_path=intent_path,
        )
        is True
    )


def test_non_resilient_supervisor_returns_child_exit_code(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.server_ops.launcher.subprocess.Popen",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "backend.server_ops.launcher.wait_for_streamlit", lambda *_args, **_kwargs: 7
    )

    assert supervise_streamlit("localhost", resilient=False) == 7


def test_smai_health_accepts_streamlit_ok_response(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    monkeypatch.setattr(
        "backend.server_ops.launcher.urlopen",
        lambda *_args, **_kwargs: Response(),
    )

    assert is_smai_healthy() is True
