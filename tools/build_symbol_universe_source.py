from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Sequence
from xml.etree import ElementTree

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_source_build_manifest.json"
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.marketdata.symbol_universe_source_build import (  # noqa: E402
    JPX_ETF_SOURCE_FIELDNAMES,
    JPX_LISTED_STOCK_SOURCE_FIELDNAMES,
    JPX_REIT_SOURCE_FIELDNAMES,
    NISA_ELIGIBILITY_SOURCE_FIELDNAMES,
    SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES,
    SBI_US_ETF_SOURCE_FIELDNAMES,
    SBI_US_STOCK_SOURCE_FIELDNAMES,
    build_sbi_hk_stock_source_rows,
    build_sbi_indonesia_stock_source_rows,
    build_sbi_korea_stock_source_rows,
    build_sbi_malaysia_stock_source_rows,
    build_sbi_singapore_stock_source_rows,
    build_sbi_thailand_stock_source_rows,
    build_jpx_etf_source_rows,
    build_jpx_listed_stock_source_rows,
    build_jpx_reit_source_rows,
    build_nisa_eligibility_source_rows,
    build_sbi_us_etf_source_rows,
    build_sbi_us_stock_source_rows,
    build_sbi_vietnam_stock_source_rows,
)

SOURCE_BUILDERS = {
    "jpx_listed_stock": (
        build_jpx_listed_stock_source_rows,
        JPX_LISTED_STOCK_SOURCE_FIELDNAMES,
    ),
    "jpx_etf": (
        build_jpx_etf_source_rows,
        JPX_ETF_SOURCE_FIELDNAMES,
    ),
    "jpx_reit": (
        build_jpx_reit_source_rows,
        JPX_REIT_SOURCE_FIELDNAMES,
    ),
    "sbi_us_stock": (
        build_sbi_us_stock_source_rows,
        SBI_US_STOCK_SOURCE_FIELDNAMES,
    ),
    "sbi_us_etf": (
        build_sbi_us_etf_source_rows,
        SBI_US_ETF_SOURCE_FIELDNAMES,
    ),
    "nisa_eligibility": (
        build_nisa_eligibility_source_rows,
        NISA_ELIGIBILITY_SOURCE_FIELDNAMES,
    ),
    "sbi_hk_stock": (build_sbi_hk_stock_source_rows, SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES),
    "sbi_korea_stock": (build_sbi_korea_stock_source_rows, SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES),
    "sbi_vietnam_stock": (build_sbi_vietnam_stock_source_rows, SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES),
    "sbi_indonesia_stock": (build_sbi_indonesia_stock_source_rows, SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES),
    "sbi_singapore_stock": (build_sbi_singapore_stock_source_rows, SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES),
    "sbi_thailand_stock": (build_sbi_thailand_stock_source_rows, SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES),
    "sbi_malaysia_stock": (build_sbi_malaysia_stock_source_rows, SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build SMAI symbol-universe source CSVs from official raw files."
    )
    parser.add_argument(
        "--source-kind",
        choices=tuple(SOURCE_BUILDERS),
        required=True,
        help="Raw source format to convert.",
    )
    parser.add_argument("--raw-file", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--as-of", type=_parse_date, default=date.today())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write output CSV and manifest. Without this flag the command is a dry-run.",
    )
    args = parser.parse_args(argv)

    raw_rows = _read_raw_rows(args.raw_file)
    build_source_rows, fieldnames = SOURCE_BUILDERS[args.source_kind]
    result = build_source_rows(raw_rows, as_of=args.as_of)

    if args.write:
        _write_csv(args.output_csv, result.rows, fieldnames)
        _write_manifest(args.manifest, result.manifest)

    print(json.dumps(result.manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _read_raw_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return _read_csv_rows(path)
    if suffix == ".xls":
        return _read_xls_rows(path)
    if suffix == ".xlsx":
        return _read_xlsx_rows(path)
    if suffix in {".html", ".htm"}:
        return _read_html_rows(path)
    raise ValueError(f"Unsupported raw file type: {path.suffix}")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in reader
        ]


def _read_xls_rows(path: Path) -> list[dict[str, str]]:
    try:
        import xlrd
    except ImportError as exc:
        raise ValueError(
            "Reading .xls raw files requires xlrd. "
            "Install setup requirements or save the raw file as .xlsx/.csv."
        ) from exc

    workbook = xlrd.open_workbook(str(path))
    sheet = workbook.sheet_by_index(0)
    table_rows = [
        [
            _xls_cell_text(sheet.cell_value(row_index, column_index))
            for column_index in range(sheet.ncols)
        ]
        for row_index in range(sheet.nrows)
    ]
    return _table_rows_to_dicts(table_rows)


def _xls_cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).strip()
    return str(value).strip()


def _read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        worksheet_paths = _xlsx_worksheet_paths(archive)
        for worksheet_path in worksheet_paths:
            worksheet_root = ElementTree.fromstring(archive.read(worksheet_path))
            table_rows = [
                _xlsx_row_values(row_element, shared_strings)
                for row_element in worksheet_root.findall(".//{*}sheetData/{*}row")
            ]
            rows = _table_rows_to_dicts(table_rows)
            if rows:
                return rows
    return []


def _read_html_rows(path: Path) -> list[dict[str, str]]:
    parser = _HtmlTableParser()
    parser.feed(_read_text_with_encoding_fallback(path))
    return _table_rows_to_dicts(parser.rows)


def _read_text_with_encoding_fallback(path: Path) -> str:
    for encoding in ("utf-8", "cp932", "shift_jis"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


class _HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._in_row = False
        self._in_cell = False
        self._skip_depth = 0
        self._row: list[str] = []
        self._cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_by_name = {name: value or "" for name, value in attrs}
        if tag == "tr":
            self._in_row = True
            self._row = []
        if self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._cell_parts = []
        if self._in_cell and "inav-btn" in attrs_by_name.get("class", ""):
            self._skip_depth += 1

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if self._in_cell and not self._skip_depth and text:
            self._cell_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            self._skip_depth -= 1
            return
        if self._in_row and tag in {"td", "th"}:
            self._row.append(_normalize_html_cell_text(" ".join(self._cell_parts)))
            self._in_cell = False
        if tag == "tr" and self._in_row:
            if self._row:
                self.rows.append(self._row)
            self._in_row = False


def _normalize_html_cell_text(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    return {
        "信託 報酬": "信託報酬",
        "連動対象指標": "連動対象指標",
        "コード": "コード",
        "名称": "名称",
    }.get(normalized, normalized)


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(".//{*}si"):
        strings.append("".join(text.text or "" for text in item.findall(".//{*}t")).strip())
    return strings


def _xlsx_worksheet_paths(archive: zipfile.ZipFile) -> list[str]:
    workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    sheets = workbook_root.findall(".//{*}sheet")
    if not sheets:
        raise ValueError("XLSX workbook has no sheets.")
    rels_root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    paths_by_relationship_id = {
        relationship.attrib.get("Id", ""): _xlsx_target_path(
            relationship.attrib.get("Target", ""),
        )
        for relationship in rels_root.findall(".//{*}Relationship")
        if relationship.attrib.get("Target")
    }
    worksheet_paths: list[str] = []
    for sheet in sheets:
        relationship_id = sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
            "",
        )
        worksheet_path = paths_by_relationship_id.get(relationship_id)
        if worksheet_path:
            worksheet_paths.append(worksheet_path)
    return worksheet_paths


def _xlsx_target_path(target: str) -> str:
    normalized = target.replace("\\", "/")
    if normalized.startswith("/"):
        return normalized.lstrip("/")
    if normalized.startswith("xl/"):
        return normalized
    return f"xl/{normalized}"


def _xlsx_row_values(row_element: ElementTree.Element, shared_strings: Sequence[str]) -> list[str]:
    values_by_index: dict[int, str] = {}
    for cell in row_element.findall("{*}c"):
        cell_ref = cell.attrib.get("r", "")
        column_index = _xlsx_column_index(cell_ref)
        values_by_index[column_index] = _xlsx_cell_value(cell, shared_strings)
    if not values_by_index:
        return []
    return [values_by_index.get(index, "") for index in range(max(values_by_index) + 1)]


def _xlsx_column_index(cell_ref: str) -> int:
    letters = "".join(character for character in cell_ref if character.isalpha()).upper()
    index = 0
    for character in letters:
        index = index * 26 + (ord(character) - ord("A") + 1)
    return max(index - 1, 0)


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: Sequence[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//{*}t")).strip()

    value_element = cell.find("{*}v")
    if value_element is None or value_element.text is None:
        return ""
    raw_value = value_element.text.strip()
    if cell_type == "s":
        index = int(raw_value)
        return shared_strings[index] if index < len(shared_strings) else ""
    return raw_value


def _table_rows_to_dicts(table_rows: Sequence[Sequence[str]]) -> list[dict[str, str]]:
    header_index = _header_index(table_rows)
    if header_index is None:
        return []
    headers = [value.strip() for value in table_rows[header_index]]
    rows: list[dict[str, str]] = []
    for row_values in table_rows[header_index + 1 :]:
        if not any(value.strip() for value in row_values):
            continue
        rows.append(
            {
                header: (row_values[index].strip() if index < len(row_values) else "")
                for index, header in enumerate(headers)
                if header
            }
        )
    return rows


def _header_index(table_rows: Sequence[Sequence[str]]) -> int | None:
    for index, row_values in enumerate(table_rows):
        normalized_headers = {value.strip().lower() for value in row_values}
        if (
            ({"コード", "銘柄名"} <= normalized_headers)
            or ({"コード", "名称"} <= normalized_headers)
            or ({"code", "security_name"} <= normalized_headers)
            or ({"symbol", "name"} <= normalized_headers)
            or ({"ticker", "name"} <= normalized_headers)
            or ({"ティッカー", "銘柄名"} <= normalized_headers)
            or ({"ティッカー", "銘柄（英語）"} <= normalized_headers)
            or ({"銘柄コード", "名称"} <= normalized_headers)
            or ({"symbol", "nisa_category"} <= normalized_headers)
            or ({"コード", "nisa区分"} <= normalized_headers)
            or ({"銘柄コード", "nisa区分"} <= normalized_headers)
            or (
                _header_contains(normalized_headers, "コード")
                and (
                    _header_contains(normalized_headers, "銘柄名")
                    or _header_contains(normalized_headers, "名称")
                )
            )
            or (
                _header_contains(normalized_headers, "銘柄コード")
                and (
                    _header_contains(normalized_headers, "銘柄名")
                    or _header_contains(normalized_headers, "銘柄名称")
                    or _header_contains(normalized_headers, "ファンド名称")
                )
            )
        ):
            return index
    return None


def _header_contains(headers: set[str], marker: str) -> bool:
    return any(marker.lower() in header for header in headers)


def _write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
