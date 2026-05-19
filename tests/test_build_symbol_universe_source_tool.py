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


def test_build_symbol_universe_source_tool_writes_jpx_etf_source(tmp_path, capsys):
    raw_csv = tmp_path / "jpx_etf_raw.csv"
    output_csv = tmp_path / "jpx_etf_source.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_raw_jpx_etf_rows(
        raw_csv,
        [
            {
                "コード": "1306",
                "銘柄名": "NEXT FUNDS TOPIX連動型上場投信",
                "市場・商品区分": "ETF・ETN",
                "対象指標": "TOPIX",
                "信託報酬": "0.06%",
            },
            {
                "コード": "7203",
                "銘柄名": "トヨタ自動車",
                "市場・商品区分": "プライム（内国株式）",
                "対象指標": "",
                "信託報酬": "",
            },
        ],
    )

    exit_code = main(
        [
            "--source-kind",
            "jpx_etf",
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
    assert rows[0]["symbol"] == "1306.T"
    assert rows[0]["name"] == "NEXT FUNDS TOPIX連動型上場投信"
    assert rows[0]["index_family"] == "topix"
    assert rows[0]["expense_ratio_pct"] == "0.06"
    assert manifest["source_kind"] == "jpx_etf"


def test_build_symbol_universe_source_tool_writes_sbi_us_etf_source(tmp_path, capsys):
    raw_csv = tmp_path / "sbi_us_etf_raw.csv"
    output_csv = tmp_path / "sbi_us_etf_source.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_raw_sbi_us_etf_rows(
        raw_csv,
        [
            {
                "ticker": "VOO",
                "name": "Vanguard S&P 500 ETF",
                "underlying_index": "S&P 500",
                "expense_ratio": "0.03%",
            },
            {
                "ticker": "SQQQ",
                "name": "ProShares UltraPro Short QQQ",
                "underlying_index": "NASDAQ 100",
                "expense_ratio": "0.95%",
            },
        ],
    )

    exit_code = main(
        [
            "--source-kind",
            "sbi_us_etf",
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
    assert output["output_rows"] == 2
    assert rows[0]["symbol"] == "VOO"
    assert rows[0]["index_family"] == "sp500"
    assert rows[0]["expense_ratio_pct"] == "0.03"
    assert rows[1]["symbol"] == "SQQQ"
    assert rows[1]["complexity"] == "inverse"
    assert rows[1]["is_inverse"] == "true"
    assert manifest["source_kind"] == "sbi_us_etf"


def _write_raw_jpx_rows(path, rows):
    fieldnames = ["コード", "銘柄名", "市場・商品区分", "33業種区分", "17業種区分", "規模区分"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_raw_jpx_etf_rows(path, rows):
    fieldnames = ["コード", "銘柄名", "市場・商品区分", "対象指標", "信託報酬"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_raw_sbi_us_etf_rows(path, rows):
    fieldnames = ["ticker", "name", "underlying_index", "expense_ratio"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
