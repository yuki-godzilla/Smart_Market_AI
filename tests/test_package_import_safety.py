from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("package", ["backend.assistant", "backend.news", "backend.research"])
def test_public_package_import_has_no_network_worker_or_cache_write_side_effect(
    package: str,
) -> None:
    source = """
import builtins
import importlib
import json
import socket
import threading

def blocked(*args, **kwargs):
    raise RuntimeError("package import attempted an external side effect")

original_open = builtins.open
def guarded_open(path, mode="r", *args, **kwargs):
    if any(flag in mode for flag in ("w", "a", "x", "+")):
        raise RuntimeError("package import attempted a filesystem write")
    return original_open(path, mode, *args, **kwargs)

builtins.open = guarded_open
socket.socket.connect = blocked
threading.Thread.start = blocked
module = importlib.import_module(__import__("sys").argv[1])
print(json.dumps({"exports": len(module.__all__)}))
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", source, package],
        cwd=Path.cwd(),
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["exports"] > 0
