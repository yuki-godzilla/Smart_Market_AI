"""Deterministic market-session policy for notification eligibility.

This module intentionally uses only persisted market metadata and the standard
library time-zone database.  It does not infer a market from a ticker, fetch a
calendar, or refresh any market-data provider.  Holiday-calendar coverage is a
separate N6-6B concern; until that work is adopted, an open weekday means only
that the regular session is open, not that a special exchange closure was
verified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time

from zoneinfo import ZoneInfo

from backend.notifications.market_calendar import MarketCalendar


@dataclass(frozen=True, slots=True)
class MarketSessionProfile:
    """A regular exchange session expressed in its local IANA time zone."""

    profile_id: str
    timezone_name: str
    sessions: tuple[tuple[time, time], ...]


@dataclass(frozen=True, slots=True)
class MarketSessionDecision:
    """Safe, explainable eligibility result for one price measurement."""

    profile_id: str | None
    local_time: datetime | None
    eligible: bool
    reason: str


JP_EQUITY = MarketSessionProfile(
    "jp_equity",
    "Asia/Tokyo",
    ((time(9, 0), time(11, 30)), (time(12, 30), time(15, 30))),
)
US_EQUITY = MarketSessionProfile(
    "us_equity",
    "America/New_York",
    ((time(9, 30), time(16, 0)),),
)

_PROFILES_BY_MARKET = {
    "japan": JP_EQUITY,
    "jpx": JP_EQUITY,
    "tokyo": JP_EQUITY,
    "tse": JP_EQUITY,
    "us": US_EQUITY,
    "usa": US_EQUITY,
    "nasdaq": US_EQUITY,
    "nyse": US_EQUITY,
    "newyork": US_EQUITY,
}
_UNSUPPORTED_ASSET_TYPES = {
    "bond",
    "crypto",
    "cryptocurrency",
    "forex",
    "fx",
}


def evaluate_market_session(
    market: str | None,
    asset_type: str | None,
    *,
    evaluated_at: datetime,
    calendar: MarketCalendar | None,
) -> MarketSessionDecision:
    """Return whether a saved equity measurement is within regular trading hours.

    Missing or unsupported metadata is deliberately fail-closed.  The caller
    must provide an aware timestamp so scheduler and dry-run executions make
    the same decision at session boundaries.
    """

    if evaluated_at.tzinfo is None:
        return MarketSessionDecision(None, None, False, "invalid_evaluation_time")
    if _normalized_asset_type(asset_type) in _UNSUPPORTED_ASSET_TYPES:
        return MarketSessionDecision(None, None, False, "market_asset_type_unsupported")
    profile = _PROFILES_BY_MARKET.get(_normalized_market(market))
    if profile is None:
        return MarketSessionDecision(None, None, False, "market_session_unknown")

    local_time = evaluated_at.astimezone(ZoneInfo(profile.timezone_name))
    if calendar is None:
        return MarketSessionDecision(
            profile.profile_id, local_time, False, "market_calendar_unavailable"
        )
    calendar_day = calendar.day_for(profile.profile_id, local_time.date())
    if calendar_day.reason != "market_calendar_open":
        return MarketSessionDecision(profile.profile_id, local_time, False, calendar_day.reason)
    if local_time.weekday() >= 5:
        return MarketSessionDecision(profile.profile_id, local_time, False, "market_weekend")
    local_clock = local_time.timetz().replace(tzinfo=None)
    sessions = calendar_day.sessions or profile.sessions
    if any(start <= local_clock < end for start, end in sessions):
        return MarketSessionDecision(profile.profile_id, local_time, True, "market_session_open")
    return MarketSessionDecision(profile.profile_id, local_time, False, "outside_market_session")


def _normalized_market(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _normalized_asset_type(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
