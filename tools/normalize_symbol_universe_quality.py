from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_REPORT_PATH = (
    PROJECT_ROOT / "data" / "marketdata" / "symbol_universe_quality_normalization.json"
)

METRICS = (
    "per",
    "pbr",
    "roe_pct",
    "dividend_yield_pct",
    "market_cap",
    "market_cap_tier",
    "expense_ratio_pct",
    "aum",
    "average_volume",
)
CONFIRMED_SOURCES = {"yahoo", "curated_csv", "manual", "manual_review", "verified_csv"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize symbol_universe.csv metric quality/source/as_of fields."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--checked-at", type=_parse_datetime, default=datetime.now().astimezone())
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--mark-suspicious",
        action="store_true",
        help="Mark obvious metric outliers as suspicious instead of only normalizing missing quality.",
    )
    args = parser.parse_args(argv)

    fieldnames, rows = _read_csv(args.csv)
    new_rows, report = normalize_rows(
        rows,
        checked_at=args.checked_at,
        mark_suspicious=args.mark_suspicious,
    )
    report["csv"] = _report_path(args.csv)
    report["dry_run"] = not args.write

    write_fieldnames = _write_fieldnames(fieldnames, new_rows)
    if args.write:
        _write_csv(args.csv, new_rows, write_fieldnames)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def normalize_rows(
    rows: Sequence[dict[str, str]],
    *,
    checked_at: datetime,
    mark_suspicious: bool = False,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    new_rows = [dict(row) for row in rows]
    changed_rows: set[str] = set()
    changed_columns: set[str] = set()
    changes_by_metric: dict[str, int] = {metric: 0 for metric in METRICS}
    suspicious_by_metric: dict[str, int] = {metric: 0 for metric in METRICS}

    for row in new_rows:
        symbol = row.get("symbol", "").strip()
        row_changed = False
        for metric in METRICS:
            value = row.get(metric, "").strip()
            source_col = f"{metric}_source"
            as_of_col = f"{metric}_as_of"
            quality_col = f"{metric}_quality"
            source = row.get(source_col, "").strip()
            as_of = row.get(as_of_col, "").strip()
            quality = row.get(quality_col, "").strip()

            if value and source and as_of and quality in {"", "missing"}:
                row[quality_col] = _quality_for_source(source)
                row_changed = True
                changed_columns.add(quality_col)
                changes_by_metric[metric] += 1

            if not value and not quality:
                row[quality_col] = "missing"
                row_changed = True
                changed_columns.add(quality_col)
                changes_by_metric[metric] += 1

            if value and not source and row.get("metadata_source", "").strip():
                row[source_col] = row.get("metadata_source", "").strip()
                row_changed = True
                changed_columns.add(source_col)
                changes_by_metric[metric] += 1

            if value and not as_of and row.get("metadata_as_of", "").strip():
                row[as_of_col] = row.get("metadata_as_of", "").strip()
                row_changed = True
                changed_columns.add(as_of_col)
                changes_by_metric[metric] += 1

            if mark_suspicious and value and _is_suspicious(metric, value):
                if row.get(quality_col, "").strip() != "suspicious":
                    row[quality_col] = "suspicious"
                    row_changed = True
                    changed_columns.add(quality_col)
                    suspicious_by_metric[metric] += 1
                reason = f"{metric}:outlier"
                reasons = _reason_set(row.get("data_quality_reasons", ""))
                if reason not in reasons:
                    reasons.add(reason)
                    row["data_quality_reasons"] = ";".join(sorted(reasons))
                    row_changed = True
                    changed_columns.add("data_quality_reasons")

        if row_changed and symbol:
            changed_rows.add(symbol)

    report = {
        "operation": "symbol_universe_quality_normalization",
        "checked_at": checked_at.isoformat(),
        "total_rows": len(new_rows),
        "changed_rows": len(changed_rows),
        "changed_symbols_sample": sorted(changed_rows)[:50],
        "changed_symbols_truncated": len(changed_rows) > 50,
        "changed_columns": sorted(changed_columns),
        "changes_by_metric": changes_by_metric,
        "suspicious_by_metric": suspicious_by_metric,
        "mark_suspicious": mark_suspicious,
    }
    return new_rows, report


def _quality_for_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized in CONFIRMED_SOURCES:
        return "confirmed"
    if normalized in {"chatgpt_manual", "manual_web"}:
        return "reviewed"
    return "confirmed"


def _is_suspicious(metric: str, raw: str) -> bool:
    value = _decimal(raw)
    if value is None:
        return True
    if metric == "per":
        return value <= 0 or value > Decimal("300")
    if metric == "pbr":
        return value <= 0 or value > Decimal("100")
    if metric == "roe_pct":
        return value < Decimal("-150") or value > Decimal("150")
    if metric == "dividend_yield_pct":
        return value < 0 or value > Decimal("25")
    if metric in {"market_cap", "aum", "average_volume"}:
        return value <= 0
    if metric == "expense_ratio_pct":
        return value < 0 or value > Decimal("5")
    return False


def _decimal(raw: str) -> Decimal | None:
    try:
        value = Decimal(str(raw).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite():
        return None
    return value


def _reason_set(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(";") if part.strip()}


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        rows = [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in reader
            if row.get("symbol")
        ]
    return fieldnames, rows


def _write_csv(path: Path, rows: Sequence[dict[str, str]], fieldnames: Sequence[str]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)


def _write_fieldnames(fieldnames: Sequence[str], rows: Sequence[dict[str, str]]) -> list[str]:
    result = list(fieldnames)
    for metric in METRICS:
        for suffix in ("source", "as_of", "quality"):
            column = f"{metric}_{suffix}"
            if column not in result:
                result.append(column)
    if "data_quality_reasons" not in result:
        result.append("data_quality_reasons")
    for row in rows:
        for column in row:
            if column not in result:
                result.append(column)
    return result


def _report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
