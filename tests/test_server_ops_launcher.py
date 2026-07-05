from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from backend.server_ops.launcher import (
    EXIT_INTERRUPTED,
    ServerLockUnavailable,
    is_smai_healthy,
    server_lock,
    streamlit_command,
    streamlit_creation_flags,
    wait_for_streamlit,
)


def test_streamlit_command_uses_expected_lan_settings() -> None:
    command = streamlit_command("192.168.1.20")

    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert "ui/app.py" in command
    assert command[command.index("--server.address") + 1] == "0.0.0.0"
    assert command[command.index("--server.port") + 1] == "8501"
    assert command[command.index("--server.headless") + 1] == "true"
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
