from __future__ import annotations

import csv
import json

from tools.import_symbol_universe_source import main
from ui.symbol_universe import SYMBOL_UNIVERSE_FIELDS


def test_import_symbol_universe_source_tool_dry_run_does_not_write(tmp_path, capsys):
    base_csv = tmp_path / "symbol_universe.csv"
    source_csv = tmp_path / "jpx_seed.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_base_rows(base_csv, [{"symbol": "AAPL", "name": "Apple Inc."}])
    _write_source_rows(
        source_csv,
        [
            {
                "symbol": "1306.T",
                "name": "NEXT FUNDS TOPIX ETF",
                "asset_type": "etf",
            }
        ],
    )

    exit_code = main(
        [
            "--base-csv",
            str(base_csv),
            "--source-csv",
            str(source_csv),
            "--source-name",
            "jpx",
            "--manifest",
            str(manifest_path),
            "--as-of",
            "2026-05-18",
            "--updated-at",
            "2026-05-18T00:00:00+00:00",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    rows = _read_rows(base_csv)
    assert exit_code == 0
    assert output["dry_run"] is True
    assert output["imported_symbols"] == ["1306.T"]
    assert [row["symbol"] for row in rows] == ["AAPL"]
    assert not manifest_path.exists()


def test_import_symbol_universe_source_tool_write_updates_csv_and_manifest(tmp_path, capsys):
    base_csv = tmp_path / "symbol_universe.csv"
    source_csv = tmp_path / "jpx_seed.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_base_rows(base_csv, [{"symbol": "AAPL", "name": "Apple Inc."}])
    _write_source_rows(
        source_csv,
        [
            {
                "symbol": "1306.T",
                "name": "NEXT FUNDS TOPIX ETF",
                "asset_type": "etf",
            }
        ],
    )

    exit_code = main(
        [
            "--base-csv",
            str(base_csv),
            "--source-csv",
            str(source_csv),
            "--source-name",
            "jpx",
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
    rows = _read_rows(base_csv)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert output["dry_run"] is False
    assert [row["symbol"] for row in rows] == ["AAPL", "1306.T"]
    assert rows[1]["metadata_source"] == "jpx"
    assert manifest["imported_symbols"] == ["1306.T"]


def test_import_symbol_universe_source_tool_applies_jpx_defaults(tmp_path, capsys):
    base_csv = tmp_path / "symbol_universe.csv"
    source_csv = tmp_path / "jpx_stock_seed.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_base_rows(base_csv, [{"symbol": "AAPL", "name": "Apple Inc."}])
    _write_source_rows(
        source_csv,
        [
            {
                "code": "4689",
                "security_name": "LY Corporation",
                "sector": "technology",
            }
        ],
    )

    exit_code = main(
        [
            "--base-csv",
            str(base_csv),
            "--source-csv",
            str(source_csv),
            "--source-name",
            "jpx",
            "--manifest",
            str(manifest_path),
            "--default-market",
            "jp",
            "--default-asset-type",
            "stock",
            "--default-currency",
            "JPY",
            "--symbol-suffix",
            ".T",
            "--as-of",
            "2026-05-18",
            "--updated-at",
            "2026-05-18T00:00:00+00:00",
            "--write",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    rows = _read_rows(base_csv)
    assert exit_code == 0
    assert output["imported_symbols"] == ["4689.T"]
    assert rows[1]["symbol"] == "4689.T"
    assert rows[1]["market"] == "jp"
    assert rows[1]["currency"] == "JPY"


def test_import_symbol_universe_source_tool_applies_source_profile(tmp_path, capsys):
    base_csv = tmp_path / "symbol_universe.csv"
    source_csv = tmp_path / "sbi_us_stock_seed.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_base_rows(base_csv, [{"symbol": "AAPL", "name": "Apple Inc."}])
    _write_source_rows(
        source_csv,
        [
            {
                "symbol": "V",
                "name": "Visa",
                "sector": "financial",
            }
        ],
    )

    exit_code = main(
        [
            "--base-csv",
            str(base_csv),
            "--source-csv",
            str(source_csv),
            "--source-profile",
            "sbi_us_stock",
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
    rows = _read_rows(base_csv)
    assert exit_code == 0
    assert output["source"] == "sbi_us_stock"
    assert rows[1]["market"] == "us"
    assert rows[1]["asset_type"] == "stock"
    assert rows[1]["currency"] == "USD"
    assert rows[1]["broker"] == "sbi_securities"
    assert rows[1]["tradability"] == "tradable"
    assert rows[1]["is_sbi_supported"] == "true"
    assert rows[1]["is_active"] == "true"


def test_import_symbol_universe_source_tool_refuses_invalid_write(tmp_path, capsys):
    base_csv = tmp_path / "symbol_universe.csv"
    source_csv = tmp_path / "jpx_seed.csv"
    _write_base_rows(base_csv, [{"symbol": "AAPL", "name": "Apple Inc."}])
    _write_source_rows(
        source_csv,
        [
            {
                "symbol": "1306.T",
                "name": "NEXT FUNDS TOPIX ETF",
                "market": "moon",
                "asset_type": "etf",
            }
        ],
    )

    exit_code = main(
        [
            "--base-csv",
            str(base_csv),
            "--source-csv",
            str(source_csv),
            "--source-name",
            "jpx",
            "--as-of",
            "2026-05-18",
            "--updated-at",
            "2026-05-18T00:00:00+00:00",
            "--write",
        ]
    )

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    rows = _read_rows(base_csv)
    assert exit_code == 2
    assert output["validation_after"]["errors"] > 0
    assert "Refusing to write" in captured.err
    assert [row["symbol"] for row in rows] == ["AAPL"]


def _write_base_rows(path, rows):
    fieldnames = list(SYMBOL_UNIVERSE_FIELDS)
    defaults = {
        "market": "us",
        "asset_type": "stock",
        "currency": "USD",
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
        "metadata_source": "curated_csv",
        "metadata_as_of": "2026-05-18",
        "metadata_updated_at": "2026-05-18T00:00:00+00:00",
    }
    complete_rows = [{**defaults, **row} for row in rows]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(complete_rows)


def _write_source_rows(path, rows):
    fieldnames = [
        "symbol",
        "code",
        "name",
        "security_name",
        "market",
        "asset_type",
        "currency",
        "sector",
        "index_family",
        "expense_ratio_pct",
        "broker",
        "tradability",
        "is_sbi_supported",
        "is_active",
        "is_leveraged",
        "is_inverse",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
