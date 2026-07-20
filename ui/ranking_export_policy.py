"""UI-owned adapter for the investment-candidate ranking export use case."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from backend.investment_candidates.ports import RankingPolicyPort
from ui.ranking import (
    RANKING_PRODUCT_STOCK,
    apply_ranking_weight_preset,
    filter_symbol_universe_rows,
    ranking_period_dates,
    ranking_weight_preset_for_purpose,
)


class UIRankingPolicyAdapter:
    """Expose the current UI ranking policy through a backend-facing port."""

    @property
    def stock_product_type(self) -> str:
        return RANKING_PRODUCT_STOCK

    def filter_rows(
        self,
        rows: list[dict[str, str]],
        **filters: Any,
    ) -> list[dict[str, str]]:
        return filter_symbol_universe_rows(rows, **filters)

    def period_dates(self, preset: str, end: date) -> tuple[date, date]:
        return ranking_period_dates(preset, end)

    def weight_preset_for_purpose(self, purpose: str) -> Any:
        return ranking_weight_preset_for_purpose(purpose)

    def rank_rows(
        self,
        rows: list[dict[str, str]],
        preset: Any,
        symbol_rows_by_symbol: Mapping[str, dict[str, str]],
    ) -> list[dict[str, str]]:
        return apply_ranking_weight_preset(rows, preset, dict(symbol_rows_by_symbol))


def create_ranking_export_policy() -> RankingPolicyPort:
    """Build the adapter at the application composition boundary."""

    return UIRankingPolicyAdapter()
