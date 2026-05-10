from __future__ import annotations

import argparse
import os
from collections.abc import Iterable, Sequence
from pathlib import Path

import black

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGETS = ("backend", "tests", "tools", "ui")
EXCLUDED_DIR_NAMES = {
    ".git",
    ".black_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}
EXCLUDED_RELATIVE_FILES = {
    # Black 24.8.0 can hang on this legacy aggregate UI test file on Windows.
    # Keep new UI display tests in smaller files and continue linting them normally.
    "tests/test_ui_rebalance_app.py",
}


def iter_python_files(targets: Iterable[str]) -> list[Path]:
    """Return Python files without walking local virtualenv or cache directories."""

    files: list[Path] = []
    for target in targets:
        path = (PROJECT_ROOT / target).resolve()
        if path.is_file() and path.suffix == ".py":
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for current_raw, dirs, filenames in os.walk(path):
            dirs[:] = [
                name
                for name in dirs
                if name not in EXCLUDED_DIR_NAMES
                and not name.startswith("venv_")
                and name != ".venv"
            ]
            current = Path(current_raw)
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                candidate = (current / name).resolve()
                relative = candidate.relative_to(PROJECT_ROOT).as_posix()
                if relative in EXCLUDED_RELATIVE_FILES:
                    continue
                files.append(candidate)
    return sorted(files)


def check_files(files: Iterable[Path]) -> list[Path]:
    """Return files that Black would reformat, without using Black's cache."""

    mode = black.FileMode(line_length=100, target_versions={black.TargetVersion.PY311})
    would_reformat: list[Path] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        try:
            black.format_file_contents(source, fast=False, mode=mode)
        except black.NothingChanged:
            continue
        would_reformat.append(path)
    return would_reformat


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a cache-free Black check locally.")
    parser.add_argument("targets", nargs="*", default=DEFAULT_TARGETS)
    args = parser.parse_args(argv)

    files = iter_python_files(args.targets)
    would_reformat = check_files(files)
    if would_reformat:
        for path in would_reformat:
            print(f"would reformat {path.relative_to(PROJECT_ROOT)}")
        print(f"{len(would_reformat)} file(s) would be reformatted.")
        return 1

    print(f"Black check passed for {len(files)} Python file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
