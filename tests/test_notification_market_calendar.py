from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import pytest

from backend.notifications.market_calendar import (
    DEFAULT_MARKET_CALENDAR_PATH,
    load_market_calendar,
    parse_market_calendar,
)
from backend.notifications.market_session import evaluate_market_session


def test_local_market_calendar_covers_2026_holidays_and_early_closes() -> None:
    calendar = load_market_calendar(DEFAULT_MARKET_CALENDAR_PATH)

    assert calendar is not None
    assert calendar.revision == "2026.1"
    assert (
        evaluate_market_session(
            "TSE", "stock", evaluated_at=datetime(2026, 9, 22, 1, tzinfo=UTC), calendar=calendar
        ).reason
        == "market_calendar_closed"
    )
    assert evaluate_market_session(
        "NYSE", "stock", evaluated_at=datetime(2026, 12, 24, 17, tzinfo=UTC), calendar=calendar
    ).eligible
    assert (
        evaluate_market_session(
            "NYSE", "stock", evaluated_at=datetime(2026, 12, 24, 19, tzinfo=UTC), calendar=calendar
        ).reason
        == "outside_market_session"
    )


def test_market_calendar_fails_closed_when_unavailable_or_outside_coverage() -> None:
    calendar = load_market_calendar(DEFAULT_MARKET_CALENDAR_PATH)
    assert calendar is not None

    assert (
        evaluate_market_session(
            "NYSE", "stock", evaluated_at=datetime(2027, 1, 4, 15, tzinfo=UTC), calendar=calendar
        ).reason
        == "market_calendar_coverage_missing"
    )
    assert (
        evaluate_market_session(
            "NYSE", "stock", evaluated_at=datetime(2026, 6, 30, 15, tzinfo=UTC), calendar=None
        ).reason
        == "market_calendar_unavailable"
    )


def test_market_calendar_rejects_overlapping_or_conflicting_exceptions() -> None:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "revision": "test",
        "markets": {
            "us_equity": {
                "coverage": {
                    "from": "2026-01-01",
                    "through": "2026-12-31",
                    "source_name": "test source",
                    "source_url": "https://example.test/calendar",
                    "verified_at": "2026-01-01",
                },
                "closed_dates": ["2026-11-27"],
                "session_overrides": {"2026-11-27": {"sessions": [["09:30", "13:00"]]}},
            }
        },
    }

    with pytest.raises(ValueError, match="closed date"):
        parse_market_calendar(payload)

    overlapping = deepcopy(payload)
    overlapping["markets"]["us_equity"]["closed_dates"] = []
    overlapping["markets"]["us_equity"]["session_overrides"] = {
        "2026-11-27": {"sessions": [["09:30", "13:00"], ["12:00", "14:00"]]}
    }
    with pytest.raises(ValueError, match="non-overlapping"):
        parse_market_calendar(overlapping)
