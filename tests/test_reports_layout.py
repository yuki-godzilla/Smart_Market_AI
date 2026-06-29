from __future__ import annotations

import re
from pathlib import Path

REPORT_RUN_PATTERN = re.compile(r"^20\d{2}-\d{2}-\d{2}_\d{4}$")


def test_generated_reports_are_grouped_into_execution_minute_directories() -> None:
    report_root = Path("reports")
    root_files = sorted(path.name for path in report_root.iterdir() if path.is_file())

    assert root_files == ["README.md"]
    run_directories = sorted(path for path in report_root.iterdir() if path.is_dir())
    assert run_directories
    assert all(REPORT_RUN_PATTERN.fullmatch(path.name) for path in run_directories)
    assert all(any(path.iterdir()) for path in run_directories)
