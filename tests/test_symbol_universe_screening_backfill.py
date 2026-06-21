from __future__ import annotations

from tools.backfill_symbol_universe_screening_metadata import (
    _backfill_etf_classification,
    _backfill_reliability_status,
    _backfill_theme_tags,
)


def test_screening_backfill_adds_conservative_theme_tags_from_aliases():
    row = {
        "symbol": "8035.T",
        "name": "Tokyo Electron",
        "asset_type": "stock",
        "theme": "technology",
        "sector": "technology",
        "aliases": "東京エレクトロン 半導体",
        "dividend_category": "none",
        "smai_theme_tags": "",
        "theme_confidence": "",
        "theme_source": "",
    }

    _backfill_theme_tags(row)

    assert set(row["smai_theme_tags"].split(",")) == {"semiconductor", "technology"}
    assert row["theme_confidence"] == "0.80"
    assert row["theme_source"] == "rule_backfill_v1"


def test_screening_backfill_materializes_estimated_sbi_and_nisa_statuses():
    row = {
        "symbol": "7203.T",
        "is_sbi_supported": "true",
        "tradability": "unknown",
        "nisa_category": "growth",
        "metadata_source": "jpx_listed_stock",
        "metadata_as_of": "2026-06-01",
    }

    _backfill_reliability_status(row)

    assert row["sbi_tradability_status"] == "estimated"
    assert row["sbi_tradability_verified"] == "false"
    assert row["nisa_growth_status"] == "estimated"
    assert row["nisa_tsumitate_status"] == "not_supported"


def test_screening_backfill_derives_etf_asset_class_from_index_family_without_live_fetch():
    row = {
        "symbol": "SPY",
        "asset_type": "etf",
        "index_family": "sp500",
        "asset_class": "",
        "region_exposure": "",
        "is_hedged": "",
    }

    _backfill_etf_classification(row)

    assert row["asset_class"] == "equity"
    assert row["region_exposure"] == "us"
    assert row["is_hedged"] == "unknown"
