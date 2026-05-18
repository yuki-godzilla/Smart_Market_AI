from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYMBOL_UNIVERSE_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
SYMBOL_UNIVERSE_REQUIRED_COLUMNS = (
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
    "per",
    "pbr",
    "roe_pct",
    "sector",
    "consensus_rating",
    "forecast_agreement",
    "data_quality",
    "risk_band",
)
SYMBOL_UNIVERSE_OPTIONAL_COLUMNS = (
    "metadata_source",
    "metadata_as_of",
    "metadata_updated_at",
)
SYMBOL_UNIVERSE_METADATA_VALUE_COLUMNS = (
    "metadata_source",
    "metadata_as_of",
)
SYMBOL_UNIVERSE_METADATA_STALE_AFTER_DAYS = 180
SYMBOL_UNIVERSE_FIELDS = [
    *SYMBOL_UNIVERSE_REQUIRED_COLUMNS,
    *SYMBOL_UNIVERSE_OPTIONAL_COLUMNS,
]
SYMBOL_UNIVERSE_REQUIRED_VALUE_COLUMNS = (
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
)
SYMBOL_UNIVERSE_ALLOWED_VALUES = {
    "market": {
        "jp",
        "us",
        "developed_ex_us",
        "emerging",
        "europe",
        "china",
        "india",
        "global",
        "other_global",
    },
    "asset_type": {"stock", "etf", "adr", "mutual_fund", "fund", "investment_trust"},
    "currency": {"JPY", "USD", "EUR", "GBP", "CHF", "CAD", "AUD", "HKD", "CNY", "INR"},
    "theme": {
        "automotive",
        "balanced",
        "bond",
        "commodity",
        "communication",
        "consumer",
        "energy",
        "financial",
        "healthcare",
        "index",
        "reit",
        "semiconductor",
        "technology",
        "telecom",
        "trading",
    },
    "dividend_category": {"dividend", "growth_dividend", "high_dividend", "none"},
    "market_cap_tier": {"mega", "large", "mid", "small", "micro"},
    "index_family": {
        "acwi",
        "msci_world",
        "nasdaq100",
        "nikkei225",
        "small_us",
        "sp500",
        "topix",
        "total_us",
    },
    "complexity": {
        "beginner",
        "standard",
        "advanced",
        "currency_select",
        "etn",
        "inverse",
        "leveraged",
        "thematic",
    },
    "sector": {
        "communication",
        "consumer",
        "energy",
        "financial",
        "healthcare",
        "index",
        "industrial",
        "materials",
        "real_estate",
        "technology",
        "utilities",
    },
    "forecast_agreement": {"HIGH", "MEDIUM", "LOW"},
    "data_quality": {"OK", "WARN", "BLOCK"},
    "risk_band": {"LOW", "MEDIUM", "HIGH"},
    "metadata_source": {"curated_csv", "csv", "manual", "polygon", "unknown", "yahoo"},
}
SYMBOL_UNIVERSE_ALLOWED_TAGS = {
    "balanced",
    "dividend",
    "growth",
    "installment",
    "lower_risk",
    "low_cost",
    "quality",
    "value",
}
SYMBOL_UNIVERSE_DECIMAL_COLUMNS = (
    "dividend_yield_pct",
    "expense_ratio_pct",
    "per",
    "pbr",
    "roe_pct",
    "consensus_rating",
)
SYMBOL_UNIVERSE_NON_NEGATIVE_DECIMAL_COLUMNS = (
    "dividend_yield_pct",
    "expense_ratio_pct",
    "pbr",
    "consensus_rating",
)


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


@lru_cache(maxsize=4)
def _cached_symbol_universe_validation_issues(
    path: str,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        issues = validate_symbol_universe_rows(
            list(reader),
            fieldnames=reader.fieldnames or [],
        )
    return tuple(tuple(issue.items()) for issue in issues)


def symbol_universe_csv_validation_issues(
    path: Path = SYMBOL_UNIVERSE_CSV,
) -> list[dict[str, str]]:
    """Return schema and row validation issues for the local symbol universe CSV."""

    return [dict(issue) for issue in _cached_symbol_universe_validation_issues(str(path))]


def symbol_universe_csv_metadata_summary(
    path: Path = SYMBOL_UNIVERSE_CSV,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Return compact metadata freshness and validation status for the local CSV."""

    rows = symbol_universe_csv_rows(path)
    validation_issues = symbol_universe_csv_validation_issues(path)
    return symbol_universe_metadata_summary(
        rows,
        validation_issues=validation_issues,
        today=today,
    )


def symbol_universe_metadata_summary(
    rows: Sequence[dict[str, str]],
    *,
    validation_issues: Sequence[dict[str, str]] | None = None,
    today: date | None = None,
    stale_after_days: int = SYMBOL_UNIVERSE_METADATA_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    """Summarize metadata source and freshness without fetching live data."""

    validation_issues = validation_issues or []
    source_counts: dict[str, int] = {}
    metadata_dates: list[date] = []
    stale_count = 0
    missing_metadata_count = 0
    reference_date = today or date.today()

    for row in rows:
        metadata_source = row.get("metadata_source", "").strip()
        metadata_as_of = row.get("metadata_as_of", "").strip()
        if not metadata_source or not metadata_as_of:
            missing_metadata_count += 1
        if metadata_source:
            source_counts[metadata_source] = source_counts.get(metadata_source, 0) + 1
        parsed_date = _date_value(metadata_as_of)
        if parsed_date is None:
            continue
        metadata_dates.append(parsed_date)
        if (reference_date - parsed_date).days > stale_after_days:
            stale_count += 1

    validation_errors = _issue_count(validation_issues, "error")
    validation_warnings = _issue_count(validation_issues, "warning")
    metadata_period = "-"
    if metadata_dates:
        oldest = min(metadata_dates).isoformat()
        latest = max(metadata_dates).isoformat()
        metadata_period = latest if oldest == latest else f"{oldest} 〜 {latest}"

    return {
        "total_rows": len(rows),
        "source_counts": source_counts,
        "source_summary": _metadata_source_summary(source_counts),
        "metadata_period": metadata_period,
        "oldest_metadata_as_of": min(metadata_dates).isoformat() if metadata_dates else "",
        "latest_metadata_as_of": max(metadata_dates).isoformat() if metadata_dates else "",
        "missing_metadata_count": missing_metadata_count,
        "stale_metadata_count": stale_count,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "validation_summary": _validation_summary_label(validation_errors, validation_warnings),
    }


def validate_symbol_universe_rows(
    rows: Sequence[dict[str | None, Any]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> list[dict[str, str]]:
    """Validate symbol universe rows without mutating the existing CSV loading path."""

    issues: list[dict[str, str]] = []
    header_fields = list(fieldnames) if fieldnames is not None else _fieldnames_from_rows(rows)
    issues.extend(_symbol_universe_header_issues(header_fields))

    seen_symbols: dict[str, str] = {}
    start_row = 2 if fieldnames is not None else 1
    for row_number, raw_row in enumerate(rows, start=start_row):
        row = {
            str(key): ("" if value is None else str(value).strip())
            for key, value in raw_row.items()
            if key is not None
        }
        symbol = row.get("symbol", "").strip()
        if None in raw_row:
            issues.append(
                _validation_issue(
                    row_number,
                    symbol,
                    "*",
                    "SYMBOL-UNIVERSE-EXTRA-VALUE",
                    "CSV row has more values than the schema defines.",
                )
            )

        for column in SYMBOL_UNIVERSE_REQUIRED_VALUE_COLUMNS:
            if not row.get(column, "").strip():
                issues.append(
                    _validation_issue(
                        row_number,
                        symbol,
                        column,
                        "SYMBOL-UNIVERSE-MISSING-VALUE",
                        f"{column} is required.",
                    )
                )
        for column in SYMBOL_UNIVERSE_METADATA_VALUE_COLUMNS:
            if not row.get(column, "").strip():
                issues.append(
                    _validation_issue(
                        row_number,
                        symbol,
                        column,
                        "SYMBOL-UNIVERSE-MISSING-METADATA",
                        f"{column} is not set.",
                        severity="warning",
                    )
                )

        normalized_symbol = symbol.upper()
        if normalized_symbol:
            first_row = seen_symbols.get(normalized_symbol)
            if first_row is not None:
                issues.append(
                    _validation_issue(
                        row_number,
                        symbol,
                        "symbol",
                        "SYMBOL-UNIVERSE-DUPLICATE-SYMBOL",
                        f"symbol duplicates row {first_row}.",
                    )
                )
            else:
                seen_symbols[normalized_symbol] = str(row_number)

        for column, allowed_values in SYMBOL_UNIVERSE_ALLOWED_VALUES.items():
            value = row.get(column, "")
            if value and value not in allowed_values:
                issues.append(
                    _validation_issue(
                        row_number,
                        symbol,
                        column,
                        "SYMBOL-UNIVERSE-INVALID-VALUE",
                        f"{value} is not allowed for {column}.",
                    )
                )

        for tag in _csv_values(row.get("tags", "")):
            if tag not in SYMBOL_UNIVERSE_ALLOWED_TAGS:
                issues.append(
                    _validation_issue(
                        row_number,
                        symbol,
                        "tags",
                        "SYMBOL-UNIVERSE-INVALID-TAG",
                        f"{tag} is not a known ranking tag.",
                    )
                )

        for column in SYMBOL_UNIVERSE_DECIMAL_COLUMNS:
            value = row.get(column, "")
            if not value:
                continue
            decimal_value = _decimal_value(value)
            if decimal_value is None:
                issues.append(
                    _validation_issue(
                        row_number,
                        symbol,
                        column,
                        "SYMBOL-UNIVERSE-INVALID-DECIMAL",
                        f"{column} must be a decimal value.",
                    )
                )
                continue
            if column in SYMBOL_UNIVERSE_NON_NEGATIVE_DECIMAL_COLUMNS and decimal_value < 0:
                issues.append(
                    _validation_issue(
                        row_number,
                        symbol,
                        column,
                        "SYMBOL-UNIVERSE-NEGATIVE-DECIMAL",
                        f"{column} must not be negative.",
                    )
                )
            if column == "consensus_rating" and not Decimal("1") <= decimal_value <= Decimal("5"):
                issues.append(
                    _validation_issue(
                        row_number,
                        symbol,
                        column,
                        "SYMBOL-UNIVERSE-RATING-RANGE",
                        "consensus_rating must be between 1 and 5.",
                    )
                )

        if row.get("metadata_as_of") and not _is_iso_date(row["metadata_as_of"]):
            issues.append(
                _validation_issue(
                    row_number,
                    symbol,
                    "metadata_as_of",
                    "SYMBOL-UNIVERSE-INVALID-DATE",
                    "metadata_as_of must be an ISO date.",
                )
            )
        if row.get("metadata_updated_at") and not _is_iso_datetime(row["metadata_updated_at"]):
            issues.append(
                _validation_issue(
                    row_number,
                    symbol,
                    "metadata_updated_at",
                    "SYMBOL-UNIVERSE-INVALID-DATETIME",
                    "metadata_updated_at must be an ISO datetime.",
                )
            )

    return issues


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


def _fieldnames_from_rows(rows: Sequence[dict[str | None, Any]]) -> list[str]:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key is not None and key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


def _symbol_universe_header_issues(fieldnames: Sequence[str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    known_columns = set(SYMBOL_UNIVERSE_FIELDS)
    for column in SYMBOL_UNIVERSE_REQUIRED_COLUMNS:
        if column not in fieldnames:
            issues.append(
                _validation_issue(
                    "header",
                    "",
                    column,
                    "SYMBOL-UNIVERSE-MISSING-COLUMN",
                    f"{column} column is required.",
                )
            )
    for column in fieldnames:
        if column not in known_columns:
            issues.append(
                _validation_issue(
                    "header",
                    "",
                    column,
                    "SYMBOL-UNIVERSE-UNKNOWN-COLUMN",
                    f"{column} is not part of the symbol universe schema.",
                )
            )
    return issues


def _validation_issue(
    row: int | str,
    symbol: str,
    column: str,
    code: str,
    message: str,
    *,
    severity: str = "error",
) -> dict[str, str]:
    return {
        "severity": severity,
        "row": str(row),
        "symbol": symbol,
        "column": column,
        "code": code,
        "message": message,
    }


def _csv_values(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _decimal_value(value: str) -> Decimal | None:
    try:
        decimal_value = Decimal(value)
    except InvalidOperation:
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _date_value(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _issue_count(issues: Sequence[dict[str, str]], severity: str) -> int:
    return sum(1 for issue in issues if issue.get("severity", "error") == severity)


def _metadata_source_summary(source_counts: dict[str, int]) -> str:
    if not source_counts:
        return "-"
    return ", ".join(f"{source}: {count}" for source, count in sorted(source_counts.items()))


def _validation_summary_label(error_count: int, warning_count: int) -> str:
    if error_count == 0 and warning_count == 0:
        return "OK"
    return f"エラー {error_count} / 確認 {warning_count}"


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True
