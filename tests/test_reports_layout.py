from __future__ import annotations

import re
from pathlib import Path

REPORT_RUN_PATTERN = re.compile(r"^20\d{2}-\d{2}-\d{2}_\d{4}$")
ROOT_REFERENCE_REPORT_PATTERN = re.compile(r"^phase\d+_[a-z0-9_]+\.md$")
ROOT_REFERENCE_REPORT_DIRECTORY_PATTERN = re.compile(
    r"^(?:forecast_evaluation|phase\d+_[a-z0-9_]+)$"
)


def test_generated_reports_are_grouped_into_execution_minute_directories() -> None:
    report_root = Path("reports")
    root_files = sorted(path.name for path in report_root.iterdir() if path.is_file())

    # Execution artifacts belong in their minute directory.  A small number
    # of phase summaries are intentionally kept at the root for the current
    # project context to reference directly.
    assert "README.md" in root_files
    assert all(
        path_name == "README.md" or ROOT_REFERENCE_REPORT_PATTERN.fullmatch(path_name)
        for path_name in root_files
    )
    run_directories = sorted(path for path in report_root.iterdir() if path.is_dir())
    assert all(
        REPORT_RUN_PATTERN.fullmatch(path.name)
        or ROOT_REFERENCE_REPORT_DIRECTORY_PATTERN.fullmatch(path.name)
        for path in run_directories
    )
    assert all(any(path.iterdir()) for path in run_directories)
