from __future__ import annotations

from datetime import date, datetime, timezone

from backend.marketdata.ranking_universe_policy import (
    symbol_allowed_by_ranking_universe_policy,
)
from backend.marketdata.symbol_universe_import import (
    SymbolUniverseImportDefaults,
    merge_symbol_universe_source_rows,
    symbol_universe_import_fieldnames,
    symbol_universe_source_profile,
    symbol_universe_source_profile_names,
)
from ui.symbol_universe import validate_symbol_universe_rows


def test_merge_symbol_universe_source_rows_imports_new_rows_with_inferred_fields():
    result = merge_symbol_universe_source_rows(
        [{"symbol": "AAPL", "name": "Apple Inc."}],
        [
            {
                "symbol": "1306.T",
                "name": "NEXT FUNDS TOPIX ETF",
                "asset_type": "etf",
                "index_family": "topix",
                "expense_ratio_pct": "0.06",
            }
        ],
        source_name="jpx",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    imported_row = result.rows[1]
    assert imported_row["symbol"] == "1306.T"
    assert imported_row["market"] == "jp"
    assert imported_row["currency"] == "JPY"
    assert imported_row["theme"] == "index"
    assert imported_row["sector"] == "index"
    assert imported_row["complexity"] == "beginner"
    assert imported_row["tags"] == "low_cost"
    assert imported_row["metadata_source"] == "jpx"
    assert imported_row["metadata_as_of"] == "2026-05-18"
    assert result.manifest["imported_symbols"] == ["1306.T"]
    assert result.manifest["imported_rows"] == 1


def test_merge_symbol_universe_source_rows_normalizes_jpx_numeric_codes_with_defaults():
    result = merge_symbol_universe_source_rows(
        [],
        [{"code": "4689", "security_name": "LY Corporation", "sector": "technology"}],
        source_name="jpx",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        defaults=SymbolUniverseImportDefaults(
            market="jp",
            asset_type="stock",
            currency="JPY",
            symbol_suffix=".T",
        ),
    )

    imported_row = result.rows[0]
    assert imported_row["symbol"] == "4689.T"
    assert imported_row["market"] == "jp"
    assert imported_row["asset_type"] == "stock"
    assert imported_row["currency"] == "JPY"
    assert result.manifest["defaults"] == {
        "market": "jp",
        "asset_type": "stock",
        "currency": "JPY",
        "symbol_suffix": ".T",
    }


def test_source_profiles_expose_expected_names():
    assert {"jpx_stock", "jpx_etf", "sbi_us_stock", "sbi_us_etf", "nisa_eligibility"} <= set(
        symbol_universe_source_profile_names()
    )
    assert "mutual_fund_seed" in symbol_universe_source_profile_names()


def test_jpx_stock_profile_applies_local_universe_defaults():
    profile = symbol_universe_source_profile("jpx_stock")
    result = merge_symbol_universe_source_rows(
        [],
        [{"code": "4689", "security_name": "LY Corporation", "sector": "technology"}],
        source_name=profile.source_name,
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
    )

    imported_row = result.rows[0]
    assert imported_row["symbol"] == "4689.T"
    assert imported_row["market"] == "jp"
    assert imported_row["asset_type"] == "stock"
    assert imported_row["currency"] == "JPY"
    assert imported_row["broker"] == "sbi_securities"
    assert imported_row["tradability"] == "unknown"
    assert imported_row["is_sbi_supported"] == "true"
    assert result.manifest["source"] == "jpx"


def test_sbi_us_stock_profile_applies_policy_defaults():
    profile = symbol_universe_source_profile("sbi_us_stock")
    result = merge_symbol_universe_source_rows(
        [],
        [{"symbol": "V", "name": "Visa", "sector": "financial"}],
        source_name=profile.source_name,
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
    )

    imported_row = result.rows[0]
    assert imported_row["market"] == "us"
    assert imported_row["asset_type"] == "stock"
    assert imported_row["currency"] == "USD"
    assert imported_row["broker"] == "sbi_securities"
    assert imported_row["tradability"] == "tradable"
    assert imported_row["is_sbi_supported"] == "true"
    assert imported_row["is_active"] == "true"
    assert imported_row["is_leveraged"] == "false"
    assert imported_row["is_inverse"] == "false"
    assert result.manifest["source"] == "sbi_us_stock"
    assert result.manifest["default_columns"]["broker"] == "sbi_securities"


def test_nisa_eligibility_profile_updates_only_nisa_fields():
    profile = symbol_universe_source_profile("nisa_eligibility")
    result = merge_symbol_universe_source_rows(
        [
            {
                "symbol": "VOO",
                "name": "Vanguard S&P 500 ETF",
                "market": "us",
                "asset_type": "etf",
                "currency": "USD",
                "nisa_category": "unknown",
                "metadata_source": "sbi_us_etf",
            }
        ],
        [
            {
                "symbol": "VOO",
                "name": "Vanguard S&P 500 ETF source",
                "market": "jp",
                "asset_type": "stock",
                "currency": "JPY",
                "nisa_type": "growth",
                "growth_eligible": "true",
            }
        ],
        source_name=profile.source_name,
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
        update_existing=True,
    )

    updated_row = result.rows[0]
    assert updated_row["name"] == "Vanguard S&P 500 ETF"
    assert updated_row["market"] == "us"
    assert updated_row["asset_type"] == "etf"
    assert updated_row["currency"] == "USD"
    assert updated_row["nisa_category"] == "growth"
    assert updated_row["nisa_growth_eligible"] == "true"
    assert updated_row["metadata_source"] == "fsa"
    assert result.manifest["updated_symbols"] == ["VOO"]
    assert result.manifest["update_columns"] == [
        "metadata_as_of",
        "metadata_source",
        "metadata_updated_at",
        "nisa_category",
        "nisa_growth_eligible",
        "nisa_tsumitate_eligible",
    ]


def test_sbi_us_etf_profile_keeps_leveraged_inverse_flags_for_policy_exclusion():
    profile = symbol_universe_source_profile("sbi_us_etf")
    result = merge_symbol_universe_source_rows(
        [],
        [
            {"symbol": "VOO", "name": "Vanguard S&P 500 ETF"},
            {
                "symbol": "SQQQ",
                "name": "ProShares UltraPro Short QQQ",
                "is_leveraged": "true",
                "is_inverse": "true",
                "complexity": "inverse",
            },
        ],
        source_name=profile.source_name,
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
    )

    row_by_symbol = {row["symbol"]: row for row in result.rows}
    assert row_by_symbol["VOO"]["asset_type"] == "etf"
    assert row_by_symbol["VOO"]["theme"] == "index"
    assert symbol_allowed_by_ranking_universe_policy(row_by_symbol["VOO"])
    assert not symbol_allowed_by_ranking_universe_policy(row_by_symbol["SQQQ"])


def test_mutual_fund_profile_imports_minimum_fund_metadata():
    profile = symbol_universe_source_profile("mutual_fund_seed")
    result = merge_symbol_universe_source_rows(
        [],
        [
            {
                "symbol": "MF-EMAXIS-ACWI",
                "fund_name": "eMAXIS Slim 全世界株式（オール・カントリー）",
                "index_family": "acwi",
                "trust_fee_pct": "0.05775",
                "aum": "5000000000000",
                "nisa_tsumitate_eligible": "true",
                "nisa_growth_eligible": "true",
                "installment_available": "true",
                "management_style": "index",
                "distribution_policy": "none",
            }
        ],
        source_name=profile.source_name,
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
    )

    imported_row = result.rows[0]
    assert imported_row["name"] == "eMAXIS Slim 全世界株式（オール・カントリー）"
    assert imported_row["asset_type"] == "mutual_fund"
    assert imported_row["trust_fee_pct"] == "0.05775"
    assert imported_row["aum"] == "5000000000000"
    assert imported_row["nisa_tsumitate_eligible"] == "true"
    assert imported_row["nisa_growth_eligible"] == "true"
    assert imported_row["installment_available"] == "true"
    assert imported_row["management_style"] == "index"
    assert imported_row["distribution_policy"] == "none"
    assert (
        validate_symbol_universe_rows(
            result.rows,
            fieldnames=symbol_universe_import_fieldnames(),
        )
        == []
    )


def test_merge_symbol_universe_source_rows_skips_existing_by_default():
    result = merge_symbol_universe_source_rows(
        [{"symbol": "AAPL", "name": "Apple Inc.", "sector": "technology"}],
        [{"symbol": "aapl", "name": "Apple updated", "sector": "consumer"}],
        source_name="curated_csv",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert result.rows[0]["name"] == "Apple Inc."
    assert result.rows[0]["sector"] == "technology"
    assert result.manifest["skipped_existing_symbols"] == ["AAPL"]
    assert result.manifest["updated_rows"] == 0


def test_merge_symbol_universe_source_rows_updates_existing_when_enabled():
    result = merge_symbol_universe_source_rows(
        [{"symbol": "AAPL", "name": "Apple Inc.", "sector": "technology"}],
        [{"symbol": "AAPL", "name": "Apple updated", "sector": "consumer"}],
        source_name="curated_csv",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        update_existing=True,
    )

    assert result.rows[0]["name"] == "Apple updated"
    assert result.rows[0]["sector"] == "consumer"
    assert result.rows[0]["metadata_source"] == "curated_csv"
    assert result.manifest["updated_symbols"] == ["AAPL"]
    assert "name" in result.manifest["changed_columns"]


def test_merge_symbol_universe_source_rows_records_missing_name_failure():
    result = merge_symbol_universe_source_rows(
        [],
        [{"symbol": "1306.T"}],
        source_name="jpx",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert result.rows == []
    assert result.manifest["failed_rows"] == 1
    assert result.manifest["failures"][0]["code"] == "SYMBOL-UNIVERSE-IMPORT-MISSING-NAME"


def test_symbol_universe_import_fieldnames_include_operational_metadata():
    assert set(symbol_universe_import_fieldnames()) >= {
        "symbol",
        "name",
        "market",
        "asset_type",
        "currency",
        "metadata_source",
        "metadata_as_of",
        "metadata_updated_at",
    }
