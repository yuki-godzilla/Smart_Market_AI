from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from backend.marketdata.symbol_metadata_refresh import (
    CuratedSymbolMetadataProvider,
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


def test_metadata_provider_details_keep_yahoo_planned_not_implemented():
    assert metadata_refresh_provider_details("curated_csv")["implemented"] is True
    yahoo = metadata_refresh_provider_details("yahoo")

    assert yahoo["registered"] is True
    assert yahoo["implemented"] is False
    assert yahoo["requires_external_opt_in"] is True


def test_create_symbol_metadata_provider_rejects_planned_live_provider():
    with pytest.raises(ValueError, match="planned but not implemented"):
        create_symbol_metadata_provider("yahoo")


def test_summarize_validation_issues_counts_default_severity_as_error():
    assert summarize_validation_issues([{}, {"severity": "warning"}]) == {
        "total": 2,
        "errors": 1,
        "warnings": 1,
    }
