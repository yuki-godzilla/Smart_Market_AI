from __future__ import annotations

import csv
import json

from tools.refresh_symbol_universe_metadata import main
from ui.symbol_universe import SYMBOL_UNIVERSE_REQUIRED_COLUMNS


def test_refresh_symbol_universe_metadata_tool_dry_run_does_not_write(tmp_path, capsys):
    csv_path = tmp_path / "symbol_universe.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_rows(
        csv_path,
        [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "market": "us",
                "asset_type": "stock",
                "currency": "USD",
            }
        ],
    )

    exit_code = main(
        [
            "--csv",
            str(csv_path),
            "--manifest",
            str(manifest_path),
            "--as-of",
            "2026-05-18",
            "--updated-at",
            "2026-05-18T00:00:00+00:00",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    rows = _read_rows(csv_path)
    assert exit_code == 0
    assert output["dry_run"] is True
    assert output["changed_symbols"] == ["AAPL"]
    assert rows[0].get("metadata_source") is None
    assert not manifest_path.exists()


def test_refresh_symbol_universe_metadata_tool_write_updates_csv_and_manifest(
    tmp_path,
    capsys,
):
    csv_path = tmp_path / "symbol_universe.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_rows(
        csv_path,
        [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "market": "us",
                "asset_type": "stock",
                "currency": "USD",
            }
        ],
    )

    exit_code = main(
        [
            "--csv",
            str(csv_path),
            "--manifest",
            str(manifest_path),
            "--as-of",
            "2026-05-18",
            "--updated-at",
            "2026-05-18T00:00:00+00:00",
            "--write",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    rows = _read_rows(csv_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert output["dry_run"] is False
    assert rows[0]["metadata_source"] == "curated_csv"
    assert rows[0]["metadata_as_of"] == "2026-05-18"
    assert manifest["changed_symbols"] == ["AAPL"]


def test_refresh_symbol_universe_metadata_tool_reports_unimplemented_provider(tmp_path, capsys):
    csv_path = tmp_path / "symbol_universe.csv"
    _write_rows(
        csv_path,
        [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "market": "us",
                "asset_type": "stock",
                "currency": "USD",
            }
        ],
    )

    exit_code = main(["--csv", str(csv_path), "--provider", "yahoo"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "planned but not implemented" in captured.err


def _write_rows(path, rows):
    fieldnames = list(SYMBOL_UNIVERSE_REQUIRED_COLUMNS)
    defaults = {
        "theme": "technology",
        "dividend_category": "dividend",
        "dividend_yield_pct": "0.5",
        "market_cap_tier": "mega",
        "index_family": "",
        "expense_ratio_pct": "",
        "complexity": "standard",
        "tags": "balanced",
        "aliases": "",
        "per": "20",
        "pbr": "2",
        "roe_pct": "10",
        "sector": "technology",
        "consensus_rating": "3",
        "forecast_agreement": "MEDIUM",
        "data_quality": "OK",
        "risk_band": "MEDIUM",
    }
    complete_rows = [{**defaults, **row} for row in rows]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(complete_rows)


def _read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
