from __future__ import annotations

import csv
import json

from tools.build_symbol_universe_source import main


def test_build_symbol_universe_source_tool_writes_jpx_listed_stock_source(tmp_path, capsys):
    raw_csv = tmp_path / "jpx_listed_stock_raw.csv"
    output_csv = tmp_path / "jpx_listed_stock_source.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_raw_jpx_rows(
        raw_csv,
        [
            {
                "コード": "8058",
                "銘柄名": "三菱商事",
                "市場・商品区分": "プライム（内国株式）",
                "33業種区分": "卸売業",
                "17業種区分": "商社・卸売",
                "規模区分": "TOPIX Core30",
            },
            {
                "コード": "1343",
                "銘柄名": "NEXT FUNDS 東証REIT指数連動型上場投信",
                "市場・商品区分": "ETF・ETN",
                "33業種区分": "",
                "17業種区分": "",
                "規模区分": "",
            },
        ],
    )

    exit_code = main(
        [
            "--source-kind",
            "jpx_listed_stock",
            "--raw-file",
            str(raw_csv),
            "--output-csv",
            str(output_csv),
            "--manifest",
            str(manifest_path),
            "--as-of",
            "2026-05-19",
            "--write",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    rows = _read_rows(output_csv)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert output["output_rows"] == 1
    assert output["skipped_rows"] == 1
    assert rows[0]["code"] == "8058"
    assert rows[0]["security_name"] == "三菱商事"
    assert rows[0]["theme"] == "trading"
    assert rows[0]["sector"] == "industrial"
    assert rows[0]["tags"] == "dividend"
    assert manifest["source_kind"] == "jpx_listed_stock"


def test_build_symbol_universe_source_tool_dry_run_does_not_write(tmp_path, capsys):
    raw_csv = tmp_path / "jpx_listed_stock_raw.csv"
    output_csv = tmp_path / "jpx_listed_stock_source.csv"
    _write_raw_jpx_rows(
        raw_csv,
        [
            {
                "コード": "6701",
                "銘柄名": "日本電気",
                "市場・商品区分": "プライム（内国株式）",
                "33業種区分": "電気機器",
                "17業種区分": "電機・精密",
                "規模区分": "TOPIX 500",
            }
        ],
    )

    exit_code = main(
        [
            "--source-kind",
            "jpx_listed_stock",
            "--raw-file",
            str(raw_csv),
            "--output-csv",
            str(output_csv),
            "--as-of",
            "2026-05-19",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["output_rows"] == 1
    assert not output_csv.exists()


def _write_raw_jpx_rows(path, rows):
    fieldnames = ["コード", "銘柄名", "市場・商品区分", "33業種区分", "17業種区分", "規模区分"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
