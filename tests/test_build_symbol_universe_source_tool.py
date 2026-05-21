from __future__ import annotations

import csv
import json
import sys
from html import escape
from types import SimpleNamespace
from zipfile import ZipFile

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


def test_build_symbol_universe_source_tool_reads_jpx_xls_with_xlrd(tmp_path, monkeypatch, capsys):
    raw_xls = tmp_path / "jpx_listed_stock_raw.xls"
    output_csv = tmp_path / "jpx_listed_stock_source.csv"
    raw_xls.write_bytes(b"fake-xls")

    class FakeSheet:
        nrows = 2
        ncols = 6
        rows = [
            ["コード", "銘柄名", "市場・商品区分", "33業種区分", "17業種区分", "規模区分"],
            [
                7203.0,
                "トヨタ自動車",
                "プライム（内国株式）",
                "輸送用機器",
                "自動車・輸送機",
                "TOPIX Core30",
            ],
        ]

        def cell_value(self, row_index, column_index):
            return self.rows[row_index][column_index]

    fake_xlrd = SimpleNamespace(
        open_workbook=lambda _path: SimpleNamespace(sheet_by_index=lambda _index: FakeSheet())
    )
    monkeypatch.setitem(sys.modules, "xlrd", fake_xlrd)

    exit_code = main(
        [
            "--source-kind",
            "jpx_listed_stock",
            "--raw-file",
            str(raw_xls),
            "--output-csv",
            str(output_csv),
            "--as-of",
            "2026-05-19",
            "--write",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    rows = _read_rows(output_csv)
    assert exit_code == 0
    assert output["output_rows"] == 1
    assert rows[0]["code"] == "7203"
    assert rows[0]["security_name"] == "トヨタ自動車"


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


def test_build_symbol_universe_source_tool_writes_nisa_eligibility_source(tmp_path, capsys):
    raw_csv = tmp_path / "nisa_raw.csv"
    output_csv = tmp_path / "nisa_source.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_raw_nisa_rows(
        raw_csv,
        [
            {
                "コード": "7203",
                "NISA区分": "成長投資枠",
                "成長投資枠": "",
                "つみたて投資枠": "",
            },
            {
                "コード": "VOO",
                "NISA区分": "",
                "成長投資枠": "対象",
                "つみたて投資枠": "対象",
            },
        ],
    )

    exit_code = main(
        [
            "--source-kind",
            "nisa_eligibility",
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
    assert rows[0]["symbol"] == "7203.T"
    assert rows[0]["nisa_category"] == "growth"
    assert rows[0]["nisa_growth_eligible"] == "true"
    assert rows[0]["nisa_tsumitate_eligible"] == "false"
    assert rows[1]["symbol"] == "VOO"
    assert rows[1]["nisa_category"] == "both"
    assert rows[1]["nisa_tsumitate_eligible"] == "true"
    assert manifest["source_kind"] == "nisa_eligibility"


def test_build_symbol_universe_source_tool_reads_jpx_growth_nisa_xlsx(tmp_path, capsys):
    raw_xlsx = tmp_path / "jpx_growth_nisa_raw.xlsx"
    output_csv = tmp_path / "nisa_source.csv"
    manifest_path = tmp_path / "manifest.json"
    _write_minimal_xlsx(
        raw_xlsx,
        [
            ["", "", "特定非課税管理勘定（ＮＩＳＡの成長投資枠）対象銘柄一覧"],
            [
                "",
                "",
                "銘柄コードメイガラ",
                "銘柄名称メイガラメイショウ",
                "管理会社カンリカイシャ",
            ],
            ["", "", "1540", "純金上場信託（現物国内保管型）", "三菱UFJ 信託銀行株式会社"],
        ],
    )

    exit_code = main(
        [
            "--source-kind",
            "nisa_eligibility",
            "--raw-file",
            str(raw_xlsx),
            "--output-csv",
            str(output_csv),
            "--manifest",
            str(manifest_path),
            "--as-of",
            "2026-05-21",
            "--write",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    rows = _read_rows(output_csv)
    assert exit_code == 0
    assert output["output_rows"] == 1
    assert rows[0]["symbol"] == "1540.T"
    assert rows[0]["nisa_category"] == "growth"
    assert rows[0]["nisa_growth_eligible"] == "true"
    assert rows[0]["nisa_tsumitate_eligible"] == "false"


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


def _write_raw_nisa_rows(path, rows):
    fieldnames = ["コード", "NISA区分", "成長投資枠", "つみたて投資枠"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_minimal_xlsx(path, rows):
    worksheet = "".join(
        f'<row r="{row_index}">'
        + "".join(
            _inline_string_cell(_cell_ref(row_index, column_index), value)
            for column_index, value in enumerate(row_values, start=1)
        )
        + "</row>"
        for row_index, row_values in enumerate(rows, start=1)
    )
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                "</Types>"
            ),
        )
        archive.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="xl/workbook.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                "</workbook>"
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f"<sheetData>{worksheet}</sheetData>"
                "</worksheet>"
            ),
        )


def _inline_string_cell(cell_ref, value):
    return f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def _cell_ref(row_index, column_index):
    return f"{chr(ord('A') + column_index - 1)}{row_index}"


def _read_rows(path):
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))
