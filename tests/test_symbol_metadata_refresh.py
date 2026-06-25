from __future__ import annotations

from datetime import date, datetime, timezone

from backend.marketdata.symbol_metadata_refresh import (
    CuratedSymbolMetadataProvider,
    YahooSymbolMetadataProvider,
    create_symbol_metadata_provider,
    metadata_refresh_provider_details,
    refresh_symbol_universe_metadata,
    summarize_validation_issues,
)


def test_curated_provider_proposes_metadata_columns_without_network():
    provider = CuratedSymbolMetadataProvider()

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL"}, {"symbol": ""}, {"symbol": "7203.T"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert [update.symbol for update in updates] == ["AAPL", "7203.T"]
    assert updates[0].values == {
        "metadata_source": "curated_csv",
        "metadata_as_of": "2026-05-18",
        "metadata_updated_at": "2026-05-18T00:00:00+00:00",
    }


def test_refresh_symbol_universe_metadata_returns_dry_run_manifest():
    rows = [
        {"symbol": "AAPL", "metadata_source": "", "metadata_as_of": ""},
        {
            "symbol": "7203.T",
            "metadata_source": "curated_csv",
            "metadata_as_of": "2026-05-18",
            "metadata_updated_at": "2026-05-18T00:00:00+00:00",
        },
    ]

    result = refresh_symbol_universe_metadata(
        rows,
        provider=CuratedSymbolMetadataProvider(),
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        dry_run=True,
        validation_before=[{"severity": "warning"}],
        validation_after=[],
    )

    assert rows[0]["metadata_source"] == ""
    assert result.rows[0]["metadata_source"] == "curated_csv"
    assert result.manifest["dry_run"] is True
    assert result.manifest["provider"] == "curated_csv"
    assert result.manifest["updates_requested"] == 2
    assert result.manifest["updates_applied"] == 2
    assert result.manifest["changed_rows"] == 1
    assert result.manifest["changed_symbols"] == ["AAPL"]
    assert result.manifest["changed_columns"] == [
        "metadata_as_of",
        "metadata_source",
        "metadata_updated_at",
    ]
    assert result.manifest["validation_before"] == {
        "total": 1,
        "errors": 0,
        "warnings": 1,
    }


def test_metadata_provider_details_describe_yahoo_live_provider():
    assert metadata_refresh_provider_details("curated_csv")["implemented"] is True
    yahoo = metadata_refresh_provider_details("yahoo")

    assert yahoo["registered"] is True
    assert yahoo["implemented"] is True
    assert yahoo["deterministic"] is False
    assert yahoo["requires_external_opt_in"] is True


def test_create_symbol_metadata_provider_returns_yahoo_provider():
    assert isinstance(create_symbol_metadata_provider("yahoo"), YahooSymbolMetadataProvider)


def test_yahoo_provider_maps_ticker_info_to_catalog_fields_without_network():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "sector": "Technology",
            "dividendYield": 0.6,
            "trailingPE": 28.123,
            "priceToBook": 5.456,
            "returnOnEquity": 0.221,
            "marketCap": 250_000_000_000,
            "currency": "USD",
            "beta": 1.25,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert provider.failures == []
    assert updates[0].symbol == "AAPL"
    assert updates[0].values == {
        "metadata_source": "yahoo",
        "metadata_as_of": "2026-05-18",
        "metadata_updated_at": "2026-05-18T00:00:00+00:00",
        "sector": "technology",
        "theme": "technology",
        "dividend_yield_pct": "0.6",
        "dividend_category": "dividend",
        "per": "28.12",
        "pbr": "5.46",
        "roe_pct": "22.1",
        "market_cap": "250000000000",
        "market_cap_tier": "mega",
        "risk_band": "HIGH",
        "yahoo_symbol": "AAPL",
        "yahoo_symbol_status": "confirmed",
        "yahoo_symbol_checked_at": "2026-05-18T00:00:00+00:00",
    }


def test_yahoo_provider_prefers_explicit_yahoo_symbol_without_network():
    requested_symbols: list[str] = []

    def _reader(symbol: str) -> dict[str, object]:
        requested_symbols.append(symbol)
        return {"marketCap": 10_000_000_000, "currency": "HKD"}

    provider = YahooSymbolMetadataProvider(ticker_info_reader=_reader)

    updates = provider.fetch_metadata(
        [{"symbol": "00001.HK", "yahoo_symbol": "0001.HK", "asset_type": "stock", "currency": "HKD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert requested_symbols == ["0001.HK"]
    assert updates[0].symbol == "00001.HK"
    assert updates[0].values["market_cap"] == "10000000000"
    assert updates[0].values["yahoo_symbol_status"] == "confirmed"


def test_refresh_fill_missing_only_preserves_existing_values_and_adds_provenance():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "trailingPE": 18,
            "priceToBook": 2.5,
        }
    )

    result = refresh_symbol_universe_metadata(
        [{"symbol": "AAPL", "per": "20", "pbr": ""}],
        provider=provider,
        as_of=date(2026, 6, 21),
        updated_at=datetime(2026, 6, 21, tzinfo=timezone.utc),
        fill_missing_only=True,
    )

    row = result.rows[0]
    assert row["per"] == "20"
    assert "per_source" not in row
    assert row["pbr"] == "2.5"
    assert row["pbr_source"] == "yahoo"
    assert row["pbr_as_of"] == "2026-06-21"
    assert row["pbr_quality"] == "confirmed"
    assert result.manifest["fill_missing_only"] is True


def test_yahoo_provider_treats_trailing_annual_dividend_yield_as_ratio():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "trailingAnnualDividendYield": 0.006,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["dividend_yield_pct"] == "0.6"


def test_yahoo_provider_scales_jp_stock_integer_dividend_yield_basis_points():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "dividendYield": 23,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "6857.T", "market": "jp", "asset_type": "stock", "currency": "JPY"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["dividend_yield_pct"] == "0.23"
    assert updates[0].values["dividend_category"] == "dividend"


def test_yahoo_provider_converts_ratio_style_dividend_yield_to_percent():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "dividendYield": 0.032,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["dividend_yield_pct"] == "3.2"
    assert updates[0].values["dividend_category"] == "high_dividend"


def test_yahoo_provider_scales_large_jp_integer_dividend_yield_basis_points():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "dividendYield": 132,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "6479.T", "market": "jp", "asset_type": "stock", "currency": "JPY"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["dividend_yield_pct"] == "1.32"
    assert updates[0].values["dividend_category"] == "dividend"


def test_yahoo_provider_skips_abnormal_dividend_yield():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "dividendYield": 25,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert "dividend_yield_pct" not in updates[0].values
    assert "dividend_category" not in updates[0].values


def test_yahoo_provider_treats_annual_expense_ratio_as_ratio():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "annualReportExpenseRatio": 0.0003,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "IVV", "asset_type": "etf", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["expense_ratio_pct"] == "0.03"


def test_yahoo_provider_treats_net_expense_ratio_as_percentage():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "netExpenseRatio": 0.15,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "QQQM", "asset_type": "etf", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["expense_ratio_pct"] == "0.15"


def test_yahoo_provider_maps_sector_to_allowed_theme_without_network():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "sector": "Industrials",
            "marketCap": 120_000_000_000,
            "currency": "USD",
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "CAT", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["sector"] == "industrial"
    assert updates[0].values["theme"] == "balanced"


def test_yahoo_provider_records_symbol_failures_without_raising():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: (_ for _ in ()).throw(RuntimeError("timeout"))
    )

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates == []
    assert provider.failures[0].symbol == "AAPL"
    assert provider.failures[0].code == "YAHOO-METADATA-FAILED"


def test_yahoo_provider_skips_non_finite_numeric_fields_without_raising():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "trailingPE": "inf",
            "priceToBook": "-inf",
            "returnOnEquity": "nan",
            "marketCap": 250_000_000_000,
            "currency": "USD",
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert provider.failures == []
    assert "per" not in updates[0].values
    assert "pbr" not in updates[0].values
    assert "roe_pct" not in updates[0].values
    assert updates[0].values["market_cap_tier"] == "mega"


def test_yahoo_provider_skips_invalid_numeric_fields_without_raising():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "trailingPE": "not-a-number",
            "marketCap": "also-not-a-number",
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["metadata_source"] == "yahoo"
    assert provider.failures == []


def test_yahoo_provider_skips_negative_filter_values_without_network():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "dividendYield": -0.01,
            "priceToBook": -2.5,
            "annualReportExpenseRatio": -0.01,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "BAD.T", "asset_type": "etf", "currency": "JPY"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert "dividend_yield_pct" not in updates[0].values
    assert "dividend_category" not in updates[0].values
    assert "pbr" not in updates[0].values
    assert "expense_ratio_pct" not in updates[0].values


def test_yahoo_provider_skips_abnormal_valuation_metrics_without_network():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "trailingPE": 250,
            "forwardPE": -1,
            "priceToBook": 51,
            "returnOnEquity": 1.5,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "BAD", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert "per" not in updates[0].values
    assert "pbr" not in updates[0].values
    assert "roe_pct" not in updates[0].values


def test_yahoo_provider_uses_forward_pe_when_trailing_pe_is_abnormal():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: {
            "trailingPE": 250,
            "forwardPE": 18.456,
        }
    )

    updates = provider.fetch_metadata(
        [{"symbol": "AAPL", "asset_type": "stock", "currency": "USD"}],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["per"] == "18.46"


def test_yahoo_provider_clears_existing_abnormal_metrics_when_provider_has_no_valid_value():
    provider = YahooSymbolMetadataProvider(ticker_info_reader=lambda symbol: {})

    updates = provider.fetch_metadata(
        [
            {
                "symbol": "BAD",
                "asset_type": "stock",
                "currency": "USD",
                "dividend_yield_pct": "293.19",
                "dividend_category": "high_dividend",
                "per": "-12.3",
                "pbr": "51",
                "roe_pct": "125",
            }
        ],
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert updates[0].values["dividend_yield_pct"] == ""
    assert updates[0].values["dividend_category"] == ""
    assert updates[0].values["per"] == ""
    assert updates[0].values["pbr"] == ""
    assert updates[0].values["roe_pct"] == ""


def test_refresh_manifest_includes_provider_failures():
    provider = YahooSymbolMetadataProvider(
        ticker_info_reader=lambda symbol: (_ for _ in ()).throw(RuntimeError("timeout"))
    )

    result = refresh_symbol_universe_metadata(
        [{"symbol": "AAPL"}],
        provider=provider,
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert result.manifest["updates_requested"] == 0
    assert result.manifest["failed_symbols"] == ["AAPL"]
    assert result.manifest["failures"] == [
        {
            "symbol": "AAPL",
            "code": "YAHOO-METADATA-FAILED",
            "message": "timeout",
        }
    ]


def test_summarize_validation_issues_counts_default_severity_as_error():
    assert summarize_validation_issues([{}, {"severity": "warning"}]) == {
        "total": 2,
        "errors": 1,
        "warnings": 1,
    }


def test_refresh_tool_allows_preexisting_validation_errors_without_strict_mode():
    from tools.refresh_symbol_universe_metadata import _should_refuse_write_due_to_validation

    assert not _should_refuse_write_due_to_validation(
        validation_before_summary={"total": 5, "errors": 5, "warnings": 0},
        validation_after_summary={"total": 5, "errors": 5, "warnings": 0},
        strict_validation=False,
    )


def test_refresh_tool_refuses_new_validation_errors_without_strict_mode():
    from tools.refresh_symbol_universe_metadata import _should_refuse_write_due_to_validation

    assert _should_refuse_write_due_to_validation(
        validation_before_summary={"total": 5, "errors": 5, "warnings": 0},
        validation_after_summary={"total": 6, "errors": 6, "warnings": 0},
        strict_validation=False,
    )


def test_refresh_tool_strict_validation_refuses_any_after_errors():
    from tools.refresh_symbol_universe_metadata import _should_refuse_write_due_to_validation

    assert _should_refuse_write_due_to_validation(
        validation_before_summary={"total": 5, "errors": 5, "warnings": 0},
        validation_after_summary={"total": 5, "errors": 5, "warnings": 0},
        strict_validation=True,
    )
