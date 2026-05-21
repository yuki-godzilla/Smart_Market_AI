from __future__ import annotations

from backend.marketdata.symbol_metadata_schema import (
    METADATA_STORAGE_FUTURE_FUND_METADATA,
    METADATA_STORAGE_SYMBOL_UNIVERSE,
    METADATA_TIER_CORE,
    METADATA_TIER_FUND_EXTENDED,
    METADATA_TIER_RANKING_FILTER,
    metadata_field_by_key,
    metadata_fields_by_storage,
    metadata_fields_by_tier,
    symbol_universe_decimal_columns,
    symbol_universe_required_columns,
    symbol_universe_source_required_fields,
)


def test_symbol_metadata_catalog_defines_core_symbol_universe_fields():
    assert set(symbol_universe_required_columns()) >= {
        "symbol",
        "name",
        "market",
        "asset_type",
        "currency",
        "broker",
        "tradability",
        "nisa_category",
        "investment_style",
        "is_sbi_supported",
        "is_active",
        "is_leveraged",
        "is_inverse",
        "sector",
        "theme",
    }
    assert {field.key for field in metadata_fields_by_tier(METADATA_TIER_CORE)} >= {
        "symbol",
        "name",
        "market",
        "asset_type",
        "currency",
    }
    assert {"reit", "fx", "cfd", "futures", "option", "crypto", "bond", "mmf"} <= set(
        metadata_field_by_key("asset_type").allowed_values
    )


def test_symbol_metadata_catalog_defines_sbi_universe_policy_fields():
    assert set(metadata_field_by_key("tradability").allowed_values) == {
        "tradable",
        "not_tradable",
        "unknown",
    }
    assert set(metadata_field_by_key("nisa_category").allowed_values) == {
        "growth",
        "tsumitate",
        "both",
        "none",
        "unknown",
    }
    assert metadata_field_by_key("is_sbi_supported").value_type == "bool"
    assert set(metadata_field_by_key("is_leveraged").allowed_values) == {
        "true",
        "false",
        "unknown",
    }


def test_symbol_metadata_catalog_marks_ranking_fields_with_source_policy():
    source_required_keys = {field.key for field in symbol_universe_source_required_fields()}

    assert set(symbol_universe_decimal_columns()) >= {
        "dividend_yield_pct",
        "expense_ratio_pct",
        "per",
        "pbr",
        "roe_pct",
    }
    assert {"dividend_yield_pct", "per", "pbr", "risk_band"} <= source_required_keys
    assert metadata_field_by_key("dividend_yield_pct").freshness_days == 90
    assert metadata_field_by_key("risk_band").tier == METADATA_TIER_RANKING_FILTER


def test_symbol_metadata_catalog_includes_fund_metadata_for_source_import():
    fund_fields = {field.key for field in metadata_fields_by_tier(METADATA_TIER_FUND_EXTENDED)}
    symbol_universe_fields = {
        field.key for field in metadata_fields_by_storage(METADATA_STORAGE_SYMBOL_UNIVERSE)
    }
    future_fund_fields = {
        field.key for field in metadata_fields_by_storage(METADATA_STORAGE_FUTURE_FUND_METADATA)
    }

    assert {
        "trust_fee_pct",
        "aum",
        "nisa_tsumitate_eligible",
        "nisa_growth_eligible",
        "installment_available",
        "management_style",
        "distribution_policy",
    } <= fund_fields
    assert {
        "trust_fee_pct",
        "aum",
        "nisa_tsumitate_eligible",
        "nisa_growth_eligible",
        "installment_available",
        "management_style",
        "distribution_policy",
    } <= symbol_universe_fields
    assert "installment_source" in future_fund_fields
    assert {"trust_fee_pct", "aum"} <= set(symbol_universe_decimal_columns())


def test_symbol_metadata_catalog_allows_official_source_names():
    metadata_source = metadata_field_by_key("metadata_source")

    assert metadata_source is not None
    assert {
        "jpx",
        "fsa",
        "imaj",
        "yahoo",
        "fmp",
        "eodhd",
        "alpha_vantage",
        "jpx_listed_stock",
        "jpx_nisa_growth",
        "sbi_us_stock",
        "sbi_us_etf",
        "mutual_fund_seed",
    } <= set(metadata_source.allowed_values)
