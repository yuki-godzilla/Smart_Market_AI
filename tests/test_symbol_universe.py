from __future__ import annotations

from datetime import date, datetime

from backend.marketdata.ranking_universe_policy import (
    symbol_allowed_by_ranking_universe_policy,
)
from backend.symbols.contracts import SymbolRecord
from ui.symbol_universe import (
    SYMBOL_UNIVERSE_REQUIRED_COLUMNS,
    symbol_name,
    symbol_provider_symbol,
    symbol_universe_csv_metadata_summary,
    symbol_universe_csv_rows,
    symbol_universe_csv_validation_issues,
    symbol_universe_metadata_summary,
    symbol_universe_name_map,
    symbol_universe_runtime_rows,
    symbol_universe_search_rows,
    validate_symbol_universe_rows,
)


def test_symbol_universe_csv_matches_schema():
    rows = symbol_universe_csv_rows()
    row_by_symbol = {row["symbol"]: row for row in rows}

    assert rows
    assert row_by_symbol["6861.T"]["metadata_source"] == "yahoo"
    assert row_by_symbol["6861.T"]["metadata_as_of"] == "2026-06-01"
    assert rows[0]["broker"] == "sbi_securities"
    assert rows[0]["tradability"] == "unknown"
    assert row_by_symbol["7203.T"]["nisa_category"] == "growth"
    assert row_by_symbol["7203.T"]["nisa_growth_eligible"] == "true"
    assert row_by_symbol["1301.T"]["nisa_category"] == "growth"
    assert row_by_symbol["1301.T"]["nisa_growth_eligible"] == "true"
    assert row_by_symbol["1540.T"]["nisa_category"] == "growth"
    assert row_by_symbol["1540.T"]["nisa_growth_eligible"] == "true"
    assert row_by_symbol["BRK-B"]["nisa_category"] == "growth"
    assert row_by_symbol["BRK-B"]["nisa_growth_eligible"] == "true"
    jp_stock_growth_rows = [
        row
        for row in rows
        if row["market"] == "jp"
        and row["asset_type"] == "stock"
        and (row["nisa_category"] in {"growth", "both"} or row["nisa_growth_eligible"] == "true")
    ]
    us_stock_growth_rows = [
        row
        for row in rows
        if row["market"] == "us"
        and row["asset_type"] == "stock"
        and (row["nisa_category"] in {"growth", "both"} or row["nisa_growth_eligible"] == "true")
    ]
    stock_rows = [row for row in rows if row["asset_type"] == "stock"]
    etf_rows = [row for row in rows if row["asset_type"] == "etf"]
    assert len(jp_stock_growth_rows) >= 3700
    assert len(us_stock_growth_rows) >= 4300
    assert all(row["investment_style"] == "lump_sum" for row in stock_rows)
    assert all(row["nisa_category"] != "unknown" for row in etf_rows)
    assert all(row["index_family"] for row in etf_rows)
    assert _nisa_flags_match_category(rows)
    assert rows[0]["is_sbi_supported"] == "true"
    assert rows[0]["is_active"] == "true"
    assert rows[0]["is_leveraged"] == "false"
    assert rows[0]["is_inverse"] == "false"
    assert symbol_universe_csv_validation_issues() == []


def test_symbol_universe_csv_metadata_summary_counts_source_and_freshness():
    summary = symbol_universe_csv_metadata_summary(today=date(2026, 6, 1))

    assert summary["total_rows"] >= 9197
    assert summary["source_counts"] == {"yahoo": 9197}
    assert summary["metadata_period"] == "2026-06-01"
    assert summary["missing_metadata_count"] == 0
    assert summary["stale_metadata_count"] == 0
    assert summary["validation_summary"] == "OK"


def test_symbol_universe_csv_includes_sbi_etf_and_mutual_fund_expansion():
    rows = symbol_universe_csv_rows()
    row_by_symbol = {row["symbol"]: row for row in rows}

    assert row_by_symbol["VT"]["asset_type"] == "etf"
    assert row_by_symbol["VT"]["tradability"] == "tradable"
    assert row_by_symbol["TQQQ"]["is_leveraged"] == "true"
    assert row_by_symbol["SQQQ"]["is_inverse"] == "true"
    assert row_by_symbol["MF-EMAXIS-ACWI"]["asset_type"] == "mutual_fund"
    assert row_by_symbol["MF-EMAXIS-ACWI"]["trust_fee_pct"] == "0.05775"
    assert row_by_symbol["MF-EMAXIS-ACWI"]["nisa_tsumitate_eligible"] == "true"


def test_symbol_universe_csv_includes_expanded_stock_and_etf_seeds():
    rows = symbol_universe_csv_rows()
    row_by_symbol = {row["symbol"]: row for row in rows}

    assert row_by_symbol["1301.T"]["metadata_source"] == "yahoo"
    assert row_by_symbol["1301.T"]["tradability"] == "unknown"
    assert row_by_symbol["1301.T"]["market_cap_tier"] == "small"
    assert row_by_symbol["1301.T"]["per"]
    assert row_by_symbol["9503.T"]["metadata_source"] == "yahoo"
    assert row_by_symbol["9503.T"]["asset_type"] == "stock"
    assert row_by_symbol["2558.T"]["asset_type"] == "etf"
    assert row_by_symbol["2558.T"]["index_family"] == "sp500"
    assert row_by_symbol["PANW"]["metadata_source"] == "yahoo"
    assert row_by_symbol["PANW"]["theme"] == "technology"
    assert row_by_symbol["A"]["metadata_source"] == "yahoo"
    assert row_by_symbol["A"]["asset_type"] == "stock"
    assert row_by_symbol["A"]["dividend_yield_pct"]
    assert row_by_symbol["QQQM"]["metadata_source"] == "yahoo"
    assert row_by_symbol["QQQM"]["index_family"] == "nasdaq100"
    assert row_by_symbol["QQQM"]["dividend_yield_pct"] in {"", "0"}
    assert row_by_symbol["ACWI"]["metadata_source"] == "yahoo"
    assert row_by_symbol["ACWI"]["nisa_category"] == "growth"
    assert row_by_symbol["DIA"]["asset_type"] == "etf"
    assert row_by_symbol["CSOP"]["yahoo_symbol"] == "SRU.SI"
    assert row_by_symbol["2554.T"]["is_leveraged"] == "false"
    assert row_by_symbol["FAI"]["is_leveraged"] == "false"
    assert row_by_symbol["MRAL"]["is_leveraged"] == "true"
    assert row_by_symbol["MRAL"]["nisa_category"] == "none"
    assert row_by_symbol["PXIU"]["is_leveraged"] == "true"
    assert row_by_symbol["526A.T"]["index_family"] == "japan_equity"
    assert row_by_symbol["1684.T"]["index_family"] == "commodity"
    assert row_by_symbol["BBUS"]["index_family"] == "total_us"
    assert row_by_symbol["AVL"]["index_family"] == "single_stock"
    assert row_by_symbol["SPHY"]["index_family"] == "bond"
    assert row_by_symbol["8951.T"]["asset_type"] == "reit"
    assert row_by_symbol["8951.T"]["nisa_category"] == "growth"
    assert symbol_allowed_by_ranking_universe_policy(row_by_symbol["QQQM"])
    assert symbol_allowed_by_ranking_universe_policy(row_by_symbol["1301.T"])
    assert symbol_allowed_by_ranking_universe_policy(row_by_symbol["9503.T"])
    assert not symbol_allowed_by_ranking_universe_policy(row_by_symbol["8951.T"])


def test_symbol_universe_runtime_rows_overlay_symbol_cache_values(tmp_path):
    csv_path = tmp_path / "symbol_universe.csv"
    csv_path.write_text(
        ",".join(SYMBOL_UNIVERSE_REQUIRED_COLUMNS)
        + "\n"
        + "AAPL,Apple,us,stock,USD,sbi_securities,tradable,growth,lump_sum,true,true,false,false\n",
        encoding="utf-8",
    )
    rows = symbol_universe_runtime_rows(
        csv_path,
        symbol_records={
            "AAPL": SymbolRecord(
                symbol="AAPL",
                provider="fixture",
                updated_at=datetime(2026, 6, 4, 9, 0, 0),
                last_price_updated_at=datetime(2026, 6, 4, 8, 30, 0),
                last_fundamental_updated_at=datetime(2026, 6, 4, 8, 45, 0),
                data_freshness_status="stale",
                normalized_fields={
                    "name": "Apple Runtime",
                    "per": "28.1",
                    "metadata_source": "cache",
                    "raw_response": "ignored",
                },
            )
        },
    )

    assert rows[0]["name"] == "Apple Runtime"
    assert rows[0]["per"] == "28.1"
    assert rows[0]["metadata_source"] == "cache"
    assert rows[0]["symbol_cache_provider"] == "fixture"
    assert rows[0]["symbol_cache_updated_at"] == "2026-06-04T09:00:00"
    assert rows[0]["symbol_cache_last_price_updated_at"] == "2026-06-04T08:30:00"
    assert rows[0]["symbol_cache_last_fundamental_updated_at"] == "2026-06-04T08:45:00"
    assert rows[0]["symbol_cache_freshness_status"] == "stale"
    assert "raw_response" not in rows[0]


def test_symbol_universe_search_rows_overlay_official_metrics(monkeypatch):
    def fake_metric_fields() -> dict[str, dict[str, str]]:
        return {"AAPL": {"per": "18.2", "dividend_yield_pct": "3.5"}}

    monkeypatch.setattr("ui.symbol_universe.load_symbol_metric_fields", fake_metric_fields)

    rows = symbol_universe_search_rows()
    aapl = next(row for row in rows if row["symbol"] == "AAPL")

    assert aapl["per"] == "18.2"
    assert aapl["dividend_yield_pct"] == "3.5"


def test_symbol_name_map_uses_formal_master_without_runtime_cache():
    name_map = symbol_universe_name_map()

    assert name_map["NVDA"] == "NVIDIA"
    assert name_map["7203.T"]


def test_symbol_name_uses_single_runtime_record_before_csv(monkeypatch):
    now = datetime(2026, 6, 6, 9, 0, 0)

    def fake_load_symbol_record(symbol: str):
        assert symbol == "NVDA"
        return SymbolRecord(
            symbol="NVDA",
            provider="fixture",
            updated_at=now,
            normalized_fields={"name": "Runtime NVIDIA"},
        )

    monkeypatch.setattr("ui.symbol_universe.load_symbol_record", fake_load_symbol_record)

    assert symbol_name("nvda") == "Runtime NVIDIA"


def _nisa_flags_match_category(rows: list[dict[str, str]]) -> bool:
    expected_flags = {
        "growth": ("true", "false"),
        "tsumitate": ("false", "true"),
        "both": ("true", "true"),
        "none": ("false", "false"),
    }
    return all(
        (row["nisa_growth_eligible"], row["nisa_tsumitate_eligible"])
        == expected_flags[row["nisa_category"]]
        for row in rows
        if row["nisa_category"] in expected_flags
    )


def test_symbol_provider_symbol_uses_curated_yahoo_mapping():
    assert symbol_provider_symbol("CSOP", "yahoo") == "SRU.SI"
    assert symbol_provider_symbol("AAPL", "yahoo") == "AAPL"
    assert symbol_provider_symbol("CSOP", "mock") == "CSOP"


def test_validate_symbol_universe_rows_reports_missing_required_column():
    issues = validate_symbol_universe_rows(
        [{"symbol": "AAPL", "name": "Apple Inc."}],
        fieldnames=["symbol", "name"],
    )

    assert "market" in SYMBOL_UNIVERSE_REQUIRED_COLUMNS
    assert any(issue["code"] == "SYMBOL-UNIVERSE-MISSING-COLUMN" for issue in issues)
    assert any(issue["column"] == "market" for issue in issues)


def test_validate_symbol_universe_rows_reports_duplicate_symbol():
    rows = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
        },
        {
            "symbol": "aapl",
            "name": "Apple duplicate",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
        },
    ]

    issues = validate_symbol_universe_rows(rows)

    assert any(issue["code"] == "SYMBOL-UNIVERSE-DUPLICATE-SYMBOL" for issue in issues)


def test_validate_symbol_universe_rows_warns_when_metadata_is_missing():
    rows = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
        }
    ]

    issues = validate_symbol_universe_rows(rows)

    assert [issue for issue in issues if issue["code"] == "SYMBOL-UNIVERSE-MISSING-METADATA"] == [
        {
            "severity": "warning",
            "row": "1",
            "symbol": "AAPL",
            "column": "metadata_source",
            "code": "SYMBOL-UNIVERSE-MISSING-METADATA",
            "message": "metadata_source is not set.",
        },
        {
            "severity": "warning",
            "row": "1",
            "symbol": "AAPL",
            "column": "metadata_as_of",
            "code": "SYMBOL-UNIVERSE-MISSING-METADATA",
            "message": "metadata_as_of is not set.",
        },
    ]


def test_symbol_universe_metadata_summary_counts_stale_rows():
    summary = symbol_universe_metadata_summary(
        [
            {
                "symbol": "AAPL",
                "metadata_source": "curated_csv",
                "metadata_as_of": "2025-01-01",
            }
        ],
        validation_issues=[{"severity": "warning", "code": "SYMBOL-UNIVERSE-MISSING-METADATA"}],
        today=date(2026, 5, 18),
        stale_after_days=180,
    )

    assert summary["source_summary"] == "curated_csv: 1"
    assert summary["metadata_period"] == "2025-01-01"
    assert summary["stale_metadata_count"] == 1
    assert summary["validation_warnings"] == 1


def test_validate_symbol_universe_rows_warns_for_stale_ranking_metadata():
    rows = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
            "dividend_yield_pct": "0.5",
            "metadata_source": "curated_csv",
            "metadata_as_of": "2025-01-01",
        }
    ]

    issues = validate_symbol_universe_rows(rows, today=date(2026, 5, 18))

    assert any(
        issue["code"] == "SYMBOL-UNIVERSE-STALE-METADATA"
        and issue["column"] == "dividend_yield_pct"
        for issue in issues
    )


def test_validate_symbol_universe_rows_reports_invalid_values():
    rows = [
        {
            "symbol": "BAD",
            "name": "Invalid row",
            "market": "moon",
            "asset_type": "stock",
            "currency": "USD",
            "dividend_yield_pct": "not-a-number",
            "consensus_rating": "6",
            "tags": "balanced,unknown_tag",
            "metadata_as_of": "2026/05/18",
        }
    ]

    issues = validate_symbol_universe_rows(rows)
    codes = {issue["code"] for issue in issues}

    assert "SYMBOL-UNIVERSE-INVALID-VALUE" in codes
    assert "SYMBOL-UNIVERSE-INVALID-DECIMAL" in codes
    assert "SYMBOL-UNIVERSE-RATING-RANGE" in codes
    assert "SYMBOL-UNIVERSE-INVALID-TAG" in codes
    assert "SYMBOL-UNIVERSE-INVALID-DATE" in codes
