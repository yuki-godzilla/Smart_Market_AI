from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYMBOL_UNIVERSE_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
SYMBOL_UNIVERSE_FIELDS = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "theme",
    "dividend_category",
    "dividend_yield_pct",
    "market_cap_tier",
    "index_family",
    "expense_ratio_pct",
    "complexity",
    "tags",
    "aliases",
]


@lru_cache(maxsize=4)
def _cached_symbol_universe_rows(path: str) -> tuple[tuple[tuple[str, str], ...], ...]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = []
        for raw_row in reader:
            row = {field: (raw_row.get(field) or "").strip() for field in SYMBOL_UNIVERSE_FIELDS}
            if row["symbol"]:
                rows.append(tuple(row.items()))
    return tuple(rows)


def symbol_universe_csv_rows(path: Path = SYMBOL_UNIVERSE_CSV) -> list[dict[str, str]]:
    """Return local-first symbol universe rows from the curated CSV."""

    return [dict(row) for row in _cached_symbol_universe_rows(str(path))]


def symbol_reference_rows() -> list[dict[str, str]]:
    """Return ticker/name rows for lightweight UI selectors."""

    return [
        {"symbol": row["symbol"], "name": row["name"] or row["symbol"]}
        for row in symbol_universe_csv_rows()
    ]


def symbol_name(symbol: str) -> str | None:
    """Return the known company name for a yfinance-compatible ticker."""

    normalized_symbol = symbol.strip().upper()
    for row in symbol_universe_csv_rows():
        if row["symbol"].upper() == normalized_symbol:
            return row["name"] or row["symbol"]
    return None
