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
            "dividendYield": 0.006,
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
        "market_cap_tier": "mega",
        "risk_band": "HIGH",
    }


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
