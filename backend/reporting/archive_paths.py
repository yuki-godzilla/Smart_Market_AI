"""User-scoped locations for locally persisted Decision Report artifacts."""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT_USER_ID = "default"
PROFILE_ROOT = Path("data/user/profiles")
REPORT_ARCHIVE_DIRECTORY = "decision_reports"
_SAFE_USER_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def assistant_report_archive_dir(
    user_id: str,
    *,
    profile_root: Path = PROFILE_ROOT,
) -> Path | None:
    """Return a custom user's private Assistant Report archive directory.

    The system default user is intentionally session-only and therefore has no
    persistent archive destination.  The caller owns the UI decision to offer
    a browser download instead.
    """

    normalized_user_id = user_id.strip()
    if normalized_user_id == DEFAULT_USER_ID:
        return None
    if not normalized_user_id or not _SAFE_USER_ID.fullmatch(normalized_user_id):
        raise ValueError("Invalid user identifier for Decision Report archive.")
    return Path(profile_root) / normalized_user_id / REPORT_ARCHIVE_DIRECTORY
