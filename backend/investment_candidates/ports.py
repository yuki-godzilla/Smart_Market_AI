"""Ports required by investment-candidate export orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, Protocol


class RankingPolicyPort(Protocol):
    """Ranking behavior supplied by an application-edge adapter.

    The export use case belongs to the backend and must not depend on a
    Streamlit/UI module.  The UI currently owns the established ranking policy,
    so composition code injects an adapter implementing this contract.
    """

    @property
    def stock_product_type(self) -> str:
        """Return the ranking product identifier for an equity."""

    def filter_rows(
        self,
        rows: list[dict[str, str]],
        **filters: Any,
    ) -> list[dict[str, str]]:
        """Filter symbol-universe rows with the established ranking policy."""

    def period_dates(self, preset: str, end: date) -> tuple[date, date]:
        """Resolve the inclusive ranking period."""

    def weight_preset_for_purpose(self, purpose: str) -> Any:
        """Resolve the existing weight preset for a ranking purpose."""

    def rank_rows(
        self,
        rows: list[dict[str, str]],
        preset: Any,
        symbol_rows_by_symbol: Mapping[str, dict[str, str]],
    ) -> list[dict[str, str]]:
        """Apply the established scoring policy and return ranked rows."""
