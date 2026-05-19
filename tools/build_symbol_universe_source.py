from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Sequence
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
    SBI_US_ETF_SOURCE_FIELDNAMES,
    SBI_US_STOCK_SOURCE_FIELDNAMES,
    build_jpx_etf_source_rows,
    build_jpx_listed_stock_source_rows,
    build_sbi_us_etf_source_rows,
    build_sbi_us_stock_source_rows,
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
    "sbi_us_stock": (
        build_sbi_us_stock_source_rows,
        SBI_US_STOCK_SOURCE_FIELDNAMES,
    ),
    "sbi_us_etf": (
        build_sbi_us_etf_source_rows,
        SBI_US_ETF_SOURCE_FIELDNAMES,
    ),
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
    if suffix == ".xlsx":
        return _read_xlsx_rows(path)
    raise ValueError(f"Unsupported raw file type: {path.suffix}")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in reader
        ]


def _read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        worksheet_path = _xlsx_first_worksheet_path(archive)
        worksheet_root = ElementTree.fromstring(archive.read(worksheet_path))

    table_rows = [
        _xlsx_row_values(row_element, shared_strings)
        for row_element in worksheet_root.findall(".//{*}sheetData/{*}row")
    ]
    return _table_rows_to_dicts(table_rows)


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(".//{*}si"):
        strings.append("".join(text.text or "" for text in item.findall(".//{*}t")).strip())
    return strings


def _xlsx_first_worksheet_path(archive: zipfile.ZipFile) -> str:
    workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    first_sheet = workbook_root.find(".//{*}sheet")
    if first_sheet is None:
        raise ValueError("XLSX workbook has no sheets.")
    relationship_id = first_sheet.attrib.get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
        "",
    )
    rels_root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in rels_root.findall(".//{*}Relationship"):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib.get("Target", "")
            if target.startswith("/"):
                return target.lstrip("/")
            return f"xl/{target}" if not target.startswith("xl/") else target
    raise ValueError("XLSX first worksheet relationship was not found.")


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
            or ({"code", "security_name"} <= normalized_headers)
            or ({"symbol", "name"} <= normalized_headers)
            or ({"ticker", "name"} <= normalized_headers)
            or ({"ティッカー", "銘柄名"} <= normalized_headers)
        ):
            return index
    return None


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
