from __future__ import annotations

from ui.ranking_filter_chips import (
    _row_matches_country,
    _row_sector_values,
    _row_theme_values,
)


def test_row_matches_country_hong_kong_aliases() -> None:
    assert _row_matches_country({"market": "hong_kong"}, ["hong_kong"])
    assert _row_matches_country({"market": "hk"}, ["hong_kong"])
    assert _row_matches_country({"market": "china"}, ["hong_kong"])
    assert not _row_matches_country({"market": "jp"}, ["hong_kong"])


def test_row_sector_values_collects_known_fields() -> None:
    row = {
        "sector": "technology",
        "sector_gics": "semiconductor",
        "asset_type": "reit",
    }
    values = _row_sector_values(row)
    assert "technology" in values
    assert "semiconductor" in values
    assert "reit" in values
    assert "real_estate" in values


def test_row_theme_values_adds_flags() -> None:
    row = {
        "theme": "growth",
        "tags": "ai;semiconductor",
        "is_leveraged": "true",
        "is_inverse": "true",
        "is_hedged": "true",
        "expense_ratio_pct": "0.10",
    }
    values = _row_theme_values(row)
    assert {"growth", "ai", "semiconductor", "leveraged", "inverse", "hedged", "low_cost"} <= values
