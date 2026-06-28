from __future__ import annotations

from tools.backfill_symbol_universe_screening_metadata import (
    _backfill_etf_classification,
    _backfill_metric_quality_reasons,
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


def test_screening_backfill_does_not_tag_non_bank_financial_bucket_as_bank():
    row = {
        "symbol": "8604.T",
        "name": "野村ホールディングス",
        "asset_type": "stock",
        "theme": "financial",
        "sector": "financial",
        "aliases": "証券、商品先物取引業 金融（除く銀行）",
        "dividend_category": "none",
        "smai_theme_tags": "financial",
        "theme_confidence": "",
        "theme_source": "",
    }

    _backfill_theme_tags(row)

    assert "financial" in row["smai_theme_tags"].split(",")
    assert "bank" not in row["smai_theme_tags"].split(",")


def test_screening_backfill_removes_automotive_false_positive_names():
    row = {
        "symbol": "4021.T",
        "name": "日産化学",
        "asset_type": "stock",
        "theme": "materials",
        "sector": "materials",
        "aliases": "日産化学 化学 素材・化学",
        "dividend_category": "none",
        "smai_theme_tags": "automotive,materials",
        "theme_confidence": "0.80",
        "theme_source": "rule_backfill_v1",
    }

    _backfill_theme_tags(row)

    assert "materials" in row["smai_theme_tags"].split(",")
    assert "automotive" not in row["smai_theme_tags"].split(",")


def test_screening_backfill_adds_asset_type_aware_metric_quality_reasons():
    row = {
        "symbol": "ORR",
        "asset_type": "etf",
        "expense_ratio_pct": "10.91",
        "per": "12.0",
        "pbr": "1.2",
        "roe_pct": "8.0",
        "data_quality": "OK",
        "data_quality_reasons": "",
    }

    _backfill_metric_quality_reasons(row)

    reasons = set(row["data_quality_reasons"].split(","))
    assert "extreme_expense_ratio" in reasons
    assert "fundamental_metrics_not_primary_for_etf" in reasons
    assert row["data_quality"] == "WARN"
