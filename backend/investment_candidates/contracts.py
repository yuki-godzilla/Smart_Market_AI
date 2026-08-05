"""Typed contracts for investment-candidate ranking builds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

RankingRow = dict[str, str]


@dataclass(frozen=True)
class RankingBuildRequest:
    """Immutable input passed from an application edge to a ranking build."""

    cache_key: str
    symbols: tuple[str, ...]
    start: date
    end: date
    provider: str


@dataclass(frozen=True)
class RankingBuildResult:
    """Ranking rows and non-fatal per-symbol errors returned by a build."""

    rows: list[RankingRow]
    error_rows: list[RankingRow]
    reused_cache: bool = False

    def as_legacy_tuple(self) -> tuple[list[RankingRow], list[RankingRow]]:
        """Keep the existing background-worker return contract during migration."""

        return self.rows, self.error_rows
