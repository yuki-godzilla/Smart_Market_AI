from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKGROUND_WORKER_DISABLE_ENV = "SMAI_DISABLE_BACKGROUND_WORKERS"


def build_commands(
    python_executable: str,
    *,
    skip_ruff: bool = False,
    skip_pytest: bool = False,
) -> list[list[str]]:
    """Build deterministic local verification commands."""

    commands: list[list[str]] = []
    if not skip_ruff:
        commands.append(
            [
                python_executable,
                "tools/run_black_check.py",
            ]
        )
        commands.append(
            [
                python_executable,
                "-m",
                "ruff",
                "check",
                "backend",
                "ui",
                "tests",
                "--no-cache",
            ]
        )
    if not skip_pytest:
        commands.append(
            [
                python_executable,
                "-m",
                "pytest",
                "tests",
                "-q",
                "-s",
                "-p",
                "no:cacheprovider",
            ]
        )
    return commands


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local MVP verification checks.")
    parser.add_argument("--skip-ruff", action="store_true", help="Skip Ruff lint checks.")
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest checks.")
    args = parser.parse_args(argv)

    for command in build_commands(
        sys.executable,
        skip_ruff=args.skip_ruff,
        skip_pytest=args.skip_pytest,
    ):
        print(f"+ {' '.join(command)}")
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
            env=_verification_env(),
        )
        if completed.returncode != 0:
            return completed.returncode

    return 0


def _verification_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault(BACKGROUND_WORKER_DISABLE_ENV, "1")
    return env


if __name__ == "__main__":
    raise SystemExit(main())
