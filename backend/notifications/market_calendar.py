"""Validated, local exchange-calendar data for notification eligibility.

The calendar is reviewed configuration, not a runtime market-data source. A
missing or malformed file therefore returns no calendar and lets callers fail
closed without starting a provider request or modifying user data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

DEFAULT_MARKET_CALENDAR_PATH = Path("config/notification_market_calendar.v1.json")
_SUPPORTED_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CalendarCoverage:
    start: date
    end: date
    source_name: str
    source_url: str
    verified_at: date


@dataclass(frozen=True, slots=True)
class MarketCalendarProfile:
    coverage: CalendarCoverage
    closed_dates: frozenset[date]
    session_overrides: Mapping[date, tuple[tuple[time, time], ...]]


@dataclass(frozen=True, slots=True)
class CalendarDayDecision:
    reason: str
    sessions: tuple[tuple[time, time], ...] | None = None


@dataclass(frozen=True, slots=True)
class MarketCalendar:
    revision: str
    profiles: Mapping[str, MarketCalendarProfile]

    def day_for(self, profile_id: str, local_date: date) -> CalendarDayDecision:
        profile = self.profiles.get(profile_id)
        if profile is None or not (profile.coverage.start <= local_date <= profile.coverage.end):
            return CalendarDayDecision("market_calendar_coverage_missing")
        if local_date in profile.closed_dates:
            return CalendarDayDecision("market_calendar_closed")
        return CalendarDayDecision(
            "market_calendar_open", profile.session_overrides.get(local_date)
        )


def load_market_calendar(path: Path | str = DEFAULT_MARKET_CALENDAR_PATH) -> MarketCalendar | None:
    """Load a local calendar or return ``None`` for an unavailable calendar."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return parse_market_calendar(payload)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def parse_market_calendar(payload: object) -> MarketCalendar:
    """Validate a decoded calendar payload and return immutable domain data."""

    root = _mapping(payload, "calendar")
    if root.get("schema_version") != _SUPPORTED_SCHEMA_VERSION:
        raise ValueError("unsupported market calendar schema")
    revision = _text(root.get("revision"), "revision")
    raw_profiles = _mapping(root.get("markets"), "markets")
    profiles: dict[str, MarketCalendarProfile] = {}
    for profile_id, raw_profile in raw_profiles.items():
        normalized_profile_id = _text(profile_id, "market profile")
        if normalized_profile_id in profiles:
            raise ValueError("duplicate market profile")
        profile = _mapping(raw_profile, "market profile")
        coverage = _parse_coverage(profile.get("coverage"))
        closed_dates = _parse_closed_dates(profile.get("closed_dates"), coverage)
        overrides = _parse_session_overrides(profile.get("session_overrides"), coverage)
        if closed_dates & set(overrides):
            raise ValueError("closed date cannot have a session override")
        profiles[normalized_profile_id] = MarketCalendarProfile(
            coverage, closed_dates, MappingProxyType(overrides)
        )
    if not profiles:
        raise ValueError("market calendar must contain profiles")
    return MarketCalendar(revision, MappingProxyType(profiles))


def _parse_coverage(value: object) -> CalendarCoverage:
    raw = _mapping(value, "coverage")
    start = _date(raw.get("from"), "coverage.from")
    end = _date(raw.get("through"), "coverage.through")
    if end < start:
        raise ValueError("calendar coverage end precedes start")
    return CalendarCoverage(
        start,
        end,
        _text(raw.get("source_name"), "coverage.source_name"),
        _https_url(raw.get("source_url"), "coverage.source_url"),
        _date(raw.get("verified_at"), "coverage.verified_at"),
    )


def _parse_closed_dates(value: object, coverage: CalendarCoverage) -> frozenset[date]:
    if not isinstance(value, list):
        raise ValueError("closed_dates must be a list")
    dates = [_date(item, "closed date") for item in value]
    if len(dates) != len(set(dates)) or any(not _covered(day, coverage) for day in dates):
        raise ValueError("closed_dates must be unique and covered")
    return frozenset(dates)


def _parse_session_overrides(
    value: object, coverage: CalendarCoverage
) -> dict[date, tuple[tuple[time, time], ...]]:
    raw = _mapping(value, "session_overrides")
    overrides: dict[date, tuple[tuple[time, time], ...]] = {}
    for raw_date, raw_override in raw.items():
        day = _date(raw_date, "session override date")
        if not _covered(day, coverage):
            raise ValueError("session override is outside coverage")
        override = _mapping(raw_override, "session override")
        overrides[day] = _sessions(override.get("sessions"))
    return overrides


def _sessions(value: object) -> tuple[tuple[time, time], ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("sessions must be a non-empty list")
    sessions: list[tuple[time, time]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("session must contain start and end")
        start = _clock(item[0])
        end = _clock(item[1])
        if start >= end:
            raise ValueError("session start must precede end")
        sessions.append((start, end))
    ordered = sorted(sessions)
    if sessions != ordered or any(
        previous[1] > current[0] for previous, current in zip(sessions, sessions[1:])
    ):
        raise ValueError("sessions must be ordered and non-overlapping")
    return tuple(sessions)


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _https_url(value: object, name: str) -> str:
    url = _text(value, name)
    if not url.startswith("https://"):
        raise ValueError(f"{name} must use HTTPS")
    return url


def _date(value: object, name: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO date") from exc


def _clock(value: object) -> time:
    if not isinstance(value, str) or len(value) != 5:
        raise ValueError("session time must use HH:MM")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("session time must use HH:MM") from exc
    if parsed.second or parsed.microsecond:
        raise ValueError("session time must use HH:MM")
    return parsed


def _covered(value: date, coverage: CalendarCoverage) -> bool:
    return coverage.start <= value <= coverage.end
