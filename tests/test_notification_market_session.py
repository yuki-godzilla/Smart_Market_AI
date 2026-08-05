from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.notifications.market_calendar import (
    DEFAULT_MARKET_CALENDAR_PATH,
    load_market_calendar,
)
from backend.notifications.market_session import evaluate_market_session

CALENDAR = load_market_calendar(DEFAULT_MARKET_CALENDAR_PATH)
assert CALENDAR is not None


@pytest.mark.parametrize(
    ("market", "evaluated_at", "eligible", "reason"),
    [
        ("TSE", datetime(2026, 6, 30, 1, 0, tzinfo=UTC), True, "market_session_open"),
        ("JPX", datetime(2026, 6, 30, 3, 0, tzinfo=UTC), False, "outside_market_session"),
        ("Tokyo", datetime(2026, 6, 30, 4, 30, tzinfo=UTC), True, "market_session_open"),
        ("NASDAQ", datetime(2026, 7, 1, 14, 0, tzinfo=UTC), True, "market_session_open"),
        ("NYSE", datetime(2026, 1, 5, 15, 0, tzinfo=UTC), True, "market_session_open"),
    ],
)
def test_market_session_policy_uses_exchange_timezone_and_regular_sessions(
    market: str,
    evaluated_at: datetime,
    eligible: bool,
    reason: str,
) -> None:
    decision = evaluate_market_session(
        market, "stock", evaluated_at=evaluated_at, calendar=CALENDAR
    )

    assert decision.eligible is eligible
    assert decision.reason == reason


def test_market_session_policy_fails_closed_for_unknown_weekend_and_unsupported_assets() -> None:
    saturday = datetime(2026, 7, 4, 15, 0, tzinfo=UTC)

    assert (
        evaluate_market_session(None, "stock", evaluated_at=saturday, calendar=CALENDAR).reason
        == "market_session_unknown"
    )
    assert (
        evaluate_market_session("NYSE", "stock", evaluated_at=saturday, calendar=CALENDAR).reason
        == "market_weekend"
    )
    assert (
        evaluate_market_session("NASDAQ", "crypto", evaluated_at=saturday, calendar=CALENDAR).reason
        == "market_asset_type_unsupported"
    )
