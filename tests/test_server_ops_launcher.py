from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

from backend.server_ops.launcher import (
    ServerLockUnavailable,
    server_lock,
    streamlit_command,
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
