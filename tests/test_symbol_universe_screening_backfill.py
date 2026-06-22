from __future__ import annotations

from tools.backfill_symbol_universe_screening_metadata import (
    _backfill_etf_classification,
    _backfill_official_classification,
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


def test_screening_backfill_materializes_jpx_official_industries_without_live_fetch():
    row = {
        "symbol": "7203.T",
        "market": "jp",
        "asset_type": "stock",
        "tse_33_industry": "",
        "topix_17": "",
    }

    _backfill_official_classification(
        row,
        jpx_official_classifications={
            "7203.T": {
                "tse_33_industry": "輸送用機器",
                "topix_17": "自動車・輸送機",
            }
        },
    )

    assert row["tse_33_industry"] == "輸送用機器"
    assert row["topix_17"] == "自動車・輸送機"


def test_screening_backfill_only_sets_unambiguous_gics_sector_labels():
    technology_row = {
        "symbol": "MSFT",
        "market": "us",
        "asset_type": "stock",
        "sector": "technology",
        "sector_gics": "",
    }
    consumer_row = {
        "symbol": "AMZN",
        "market": "us",
        "asset_type": "stock",
        "sector": "consumer",
        "sector_gics": "",
    }

    _backfill_official_classification(technology_row, jpx_official_classifications={})
    _backfill_official_classification(consumer_row, jpx_official_classifications={})

    assert technology_row["sector_gics"] == "Information Technology"
    assert consumer_row["sector_gics"] == ""


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
