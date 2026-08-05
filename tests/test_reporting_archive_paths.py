from __future__ import annotations

from pathlib import Path

import pytest

from backend.reporting import assistant_report_archive_dir


def test_assistant_report_archive_dir_is_profile_scoped_for_custom_users(tmp_path: Path) -> None:
    archive = assistant_report_archive_dir("yuki_01", profile_root=tmp_path)

    assert archive == tmp_path / "yuki_01" / "decision_reports"


def test_assistant_report_archive_dir_has_no_persistent_default_destination(tmp_path: Path) -> None:
    assert assistant_report_archive_dir("default", profile_root=tmp_path) is None


@pytest.mark.parametrize("user_id", ("", "../other", "yuki/report", "yuki report"))
def test_assistant_report_archive_dir_rejects_unsafe_user_ids(tmp_path: Path, user_id: str) -> None:
    with pytest.raises(ValueError, match="Invalid user identifier"):
        assistant_report_archive_dir(user_id, profile_root=tmp_path)
