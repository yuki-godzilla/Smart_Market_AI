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


def test_symbol_metadata_catalog_keeps_fund_metadata_out_of_symbol_universe():
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
    assert fund_fields <= future_fund_fields
    assert fund_fields.isdisjoint(symbol_universe_fields)
