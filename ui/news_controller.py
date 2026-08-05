"""UI-independent snapshot loading for the Investment Radar page."""

from __future__ import annotations

from collections.abc import Callable

from backend.news import NewsDashboardSnapshot, NewsUpdateStatus


def load_news_dashboard_snapshot(
    *,
    load_status: Callable[[], NewsUpdateStatus],
    load_snapshot: Callable[[], NewsDashboardSnapshot | None],
    build_demo_snapshot: Callable[[], NewsDashboardSnapshot],
) -> tuple[NewsDashboardSnapshot, NewsUpdateStatus]:
    """Load cached Radar data, falling back to the deterministic demo snapshot."""

    status = load_status()
    snapshot = load_snapshot()
    return (snapshot if snapshot is not None else build_demo_snapshot(), status)
