from __future__ import annotations

from datetime import date, datetime, timezone

from backend.marketdata.ranking_universe_policy import (
    symbol_allowed_by_ranking_universe_policy,
)
from backend.marketdata.symbol_universe_import import (
    MANIFEST_SYMBOL_SAMPLE_LIMIT,
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


def test_merge_symbol_universe_source_rows_caps_manifest_symbol_samples():
    source_rows = [
        {"symbol": f"JP{index:04d}", "name": f"Imported {index}"}
        for index in range(MANIFEST_SYMBOL_SAMPLE_LIMIT + 1)
    ]

    result = merge_symbol_universe_source_rows(
        [],
        source_rows,
        source_name="jpx_listed_stock",
        as_of=date(2026, 5, 20),
        updated_at=datetime(2026, 5, 20, 0, 0, tzinfo=timezone.utc),
    )

    assert result.manifest["imported_rows"] == MANIFEST_SYMBOL_SAMPLE_LIMIT + 1
    assert len(result.manifest["imported_symbols"]) == MANIFEST_SYMBOL_SAMPLE_LIMIT
    assert result.manifest["imported_symbols_truncated"] is True
    assert result.manifest["manifest_symbol_sample_limit"] == MANIFEST_SYMBOL_SAMPLE_LIMIT


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
    assert {
        "jpx_listed_stock",
        "jpx_stock",
        "jpx_etf",
        "jpx_reit",
        "sbi_us_stock",
        "sbi_us_etf",
        "nisa_eligibility",
        "ranking_metadata",
    } <= set(symbol_universe_source_profile_names())
    assert "mutual_fund_seed" in symbol_universe_source_profile_names()


def test_jpx_listed_stock_profile_applies_local_universe_defaults():
    profile = symbol_universe_source_profile("jpx_listed_stock")
    result = merge_symbol_universe_source_rows(
        [],
        [{"code": "8058", "security_name": "Mitsubishi Corp", "sector": "industrial"}],
        source_name=profile.source_name,
        as_of=date(2026, 5, 19),
        updated_at=datetime(2026, 5, 19, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
    )

    imported_row = result.rows[0]
    assert imported_row["symbol"] == "8058.T"
    assert imported_row["market"] == "jp"
    assert imported_row["asset_type"] == "stock"
    assert imported_row["currency"] == "JPY"
    assert imported_row["broker"] == "sbi_securities"
    assert imported_row["tradability"] == "unknown"
    assert imported_row["nisa_category"] == "growth"
    assert imported_row["nisa_growth_eligible"] == "true"
    assert imported_row["nisa_tsumitate_eligible"] == "false"
    assert imported_row["is_sbi_supported"] == "true"
    assert result.manifest["source"] == "jpx_listed_stock"


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
    assert imported_row["nisa_category"] == "growth"
    assert imported_row["nisa_growth_eligible"] == "true"
    assert imported_row["nisa_tsumitate_eligible"] == "false"
    assert imported_row["is_sbi_supported"] == "true"
    assert result.manifest["source"] == "jpx"


def test_jpx_etf_profile_updates_filter_metadata_without_nisa_overwrite():
    profile = symbol_universe_source_profile("jpx_etf")
    result = merge_symbol_universe_source_rows(
        [
            {
                "symbol": "1308.T",
                "name": "NEXT FUNDS TOPIX ETF",
                "market": "jp",
                "asset_type": "etf",
                "currency": "JPY",
                "broker": "sbi_securities",
                "tradability": "unknown",
                "nisa_category": "growth",
                "investment_style": "unknown",
                "is_sbi_supported": "true",
                "is_active": "true",
                "is_leveraged": "false",
                "is_inverse": "false",
                "theme": "index",
                "sector": "index",
                "expense_ratio_pct": "0.09",
                "metadata_source": "fsa",
            }
        ],
        [
            {
                "symbol": "1308.T",
                "name": "上場インデックスファンドTOPIX",
                "index_family": "topix",
                "expense_ratio_pct": "0.047",
                "nisa_category": "unknown",
            }
        ],
        source_name=profile.source_name,
        as_of=date(2026, 5, 20),
        updated_at=datetime(2026, 5, 20, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
        update_existing=True,
    )

    updated_row = result.rows[0]
    assert updated_row["expense_ratio_pct"] == "0.047"
    assert updated_row["index_family"] == "topix"
    assert updated_row["nisa_category"] == "growth"
    assert updated_row["metadata_source"] == "jpx"
    assert result.manifest["updated_rows"] == 1


def test_jpx_reit_profile_imports_reits_as_mvp_excluded_rows():
    profile = symbol_universe_source_profile("jpx_reit")
    result = merge_symbol_universe_source_rows(
        [],
        [{"symbol": "8951.T", "name": "日本ビルファンド投資法人 投資証券"}],
        source_name=profile.source_name,
        as_of=date(2026, 5, 21),
        updated_at=datetime(2026, 5, 21, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
    )

    imported_row = result.rows[0]
    assert imported_row["symbol"] == "8951.T"
    assert imported_row["asset_type"] == "reit"
    assert imported_row["theme"] == "reit"
    assert imported_row["sector"] == "real_estate"
    assert imported_row["tradability"] == "unknown"
    assert imported_row["metadata_source"] == "jpx_reit"


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
    assert imported_row["nisa_category"] == "growth"
    assert imported_row["nisa_growth_eligible"] == "true"
    assert imported_row["nisa_tsumitate_eligible"] == "false"
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


def test_nisa_eligibility_profile_rejects_new_symbols():
    profile = symbol_universe_source_profile("nisa_eligibility")
    result = merge_symbol_universe_source_rows(
        [],
        [
            {
                "symbol": "MISSING",
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

    assert result.rows == []
    assert result.manifest["failed_rows"] == 1
    assert result.manifest["failures"][0]["code"] == "SYMBOL-UNIVERSE-IMPORT-UNKNOWN-SYMBOL"


def test_ranking_metadata_profile_updates_only_existing_filter_columns():
    profile = symbol_universe_source_profile("ranking_metadata")
    result = merge_symbol_universe_source_rows(
        [
            {
                "symbol": "1301.T",
                "name": "Kyokuyo",
                "market": "jp",
                "asset_type": "stock",
                "currency": "JPY",
                "per": "",
                "pbr": "",
                "roe_pct": "",
            }
        ],
        [
            {
                "symbol": "1301.T",
                "name": "Should not overwrite",
                "pe_ratio": "8.5",
                "price_to_book": "0.9",
                "roe": "10.2",
                "dividend_yield": "2.4",
                "risk": "MEDIUM",
            }
        ],
        source_name=profile.source_name,
        as_of=date(2026, 5, 21),
        updated_at=datetime(2026, 5, 21, 0, 0, tzinfo=timezone.utc),
        defaults=profile.defaults,
        update_existing=True,
    )

    updated_row = result.rows[0]
    assert updated_row["name"] == "Kyokuyo"
    assert updated_row["per"] == "8.5"
    assert updated_row["pbr"] == "0.9"
    assert updated_row["roe_pct"] == "10.2"
    assert updated_row["dividend_yield_pct"] == "2.4"
    assert updated_row["risk_band"] == "MEDIUM"
    assert updated_row["metadata_source"] == "curated_csv"
    assert result.manifest["update_columns"] == [
        "aliases",
        "complexity",
        "consensus_rating",
        "data_quality",
        "dividend_category",
        "dividend_yield_pct",
        "expense_ratio_pct",
        "forecast_agreement",
        "index_family",
        "market_cap_tier",
        "metadata_as_of",
        "metadata_source",
        "metadata_updated_at",
        "pbr",
        "per",
        "risk_band",
        "roe_pct",
        "sector",
        "tags",
        "theme",
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
