from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOL_UNIVERSE_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "marketdata" / "live_checks"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.marketdata.ranking_universe_policy import (  # noqa: E402
    symbol_allowed_by_ranking_universe_policy,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Yahoo coverage check failures.")
    parser.add_argument("--coverage-csv", type=Path, required=True)
    parser.add_argument("--symbol-universe-csv", type=Path, default=DEFAULT_SYMBOL_UNIVERSE_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    coverage_rows = _read_rows(args.coverage_csv)
    universe_rows = _read_rows(args.symbol_universe_csv)
    analysis_rows = analyze_failures(coverage_rows, universe_rows)
    manifest = build_manifest(
        analysis_rows,
        coverage_csv=args.coverage_csv,
        symbol_universe_csv=args.symbol_universe_csv,
    )
    paths = _write_outputs(
        args.output_dir,
        label=args.label or f"{args.coverage_csv.stem}_failure_analysis",
        manifest=manifest,
        rows=analysis_rows,
    )
    print(json.dumps({**manifest, "outputs": paths}, ensure_ascii=False, indent=2))
    return 0


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {key: "" if value is None else str(value).strip() for key, value in row.items()}
            for row in csv.DictReader(file)
        ]


def analyze_failures(
    coverage_rows: Sequence[dict[str, str]],
    symbol_universe_rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    rows_by_symbol = _rows_by_symbol_and_alias(symbol_universe_rows)
    analysis_rows = []
    for coverage_row in coverage_rows:
        if coverage_row.get("status") == "ok":
            continue
        symbol = coverage_row.get("symbol", "")
        universe_row = rows_by_symbol.get(symbol.upper(), {})
        reason = classify_failure(coverage_row, universe_row)
        analysis_rows.append(
            {
                "symbol": symbol,
                "canonical_symbol": universe_row.get("symbol", ""),
                "name": universe_row.get("name", ""),
                "asset_type": universe_row.get("asset_type", ""),
                "market": universe_row.get("market", ""),
                "metadata_source": universe_row.get("metadata_source", ""),
                "yahoo_symbol": universe_row.get("yahoo_symbol", ""),
                "status": coverage_row.get("status", ""),
                "code": coverage_row.get("code", ""),
                "reason": reason,
                "recommended_action": recommended_action(reason, universe_row),
                "policy_allowed": str(
                    symbol_allowed_by_ranking_universe_policy(universe_row)
                    if universe_row
                    else False
                ).lower(),
                "complexity": universe_row.get("complexity", ""),
                "theme": universe_row.get("theme", ""),
                "is_leveraged": universe_row.get("is_leveraged", ""),
                "is_inverse": universe_row.get("is_inverse", ""),
                "message": coverage_row.get("message", ""),
            }
        )
    return analysis_rows


def classify_failure(coverage_row: dict[str, str], universe_row: dict[str, str]) -> str:
    if not universe_row:
        return "missing_from_symbol_universe"
    if coverage_row.get("symbol", "").upper() != universe_row.get("symbol", "").upper():
        return "resolved_by_symbol_alias"

    complexity = universe_row.get("complexity", "")
    if universe_row.get("is_leveraged") == "true" or complexity == "leveraged":
        return "excluded_leveraged"
    if universe_row.get("is_inverse") == "true" or complexity == "inverse":
        return "excluded_inverse"
    if complexity == "etn":
        return "excluded_etn"
    if universe_row.get("theme") == "commodity" or universe_row.get("index_family") == "commodity":
        return "excluded_commodity"
    if not symbol_allowed_by_ranking_universe_policy(universe_row):
        return "excluded_by_ranking_policy"
    if coverage_row.get("code") == "YAHOO-NO-BARS" and universe_row.get("yahoo_symbol"):
        return "mapped_yahoo_symbol_available"
    if coverage_row.get("code") == "YAHOO-NO-BARS" and universe_row.get("asset_type") == "etf":
        return "etf_market_mapping_or_yahoo_unsupported"
    if coverage_row.get("code") == "YAHOO-NO-BARS":
        return "no_bars_short_window_or_yahoo_unsupported"
    return "provider_error"


def recommended_action(reason: str, universe_row: dict[str, str]) -> str:
    if reason.startswith("excluded_") or reason == "excluded_by_ranking_policy":
        return "exclude_from_default_ranking"
    if reason == "mapped_yahoo_symbol_available":
        return "use_yahoo_symbol_mapping"
    if reason == "etf_market_mapping_or_yahoo_unsupported":
        return "map_symbol_or_use_alternative_provider"
    if reason == "resolved_by_symbol_alias":
        return "refresh_coverage_with_canonical_symbol"
    if reason == "missing_from_symbol_universe":
        return "review_source_universe"
    if universe_row.get("asset_type") == "stock":
        return "review_symbol_status_or_provider_support"
    return "review_provider_error"


def _rows_by_symbol_and_alias(rows: Sequence[dict[str, str]]) -> dict[str, dict[str, str]]:
    rows_by_symbol: dict[str, dict[str, str]] = {}
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        if symbol:
            rows_by_symbol[symbol] = row
        for alias in _alias_tokens(row.get("aliases", "")):
            rows_by_symbol.setdefault(alias.upper(), row)
    return rows_by_symbol


def _alias_tokens(value: str) -> list[str]:
    return [
        token.strip()
        for token in value.replace(",", " ").split()
        if token.strip() and token.strip().isascii()
    ]


def build_manifest(
    rows: Sequence[dict[str, str]],
    *,
    coverage_csv: Path,
    symbol_universe_csv: Path,
) -> dict[str, object]:
    reason_counts = Counter(row["reason"] for row in rows)
    asset_type_counts = Counter(row["asset_type"] for row in rows)
    return {
        "operation": "yahoo_coverage_failure_analysis",
        "coverage_csv": str(coverage_csv),
        "symbol_universe_csv": str(symbol_universe_csv),
        "failed_symbols": len(rows),
        "reason_counts": dict(reason_counts),
        "asset_type_counts": dict(asset_type_counts),
        "failed_symbol_sample": [row["symbol"] for row in rows[:50]],
    }


def _write_outputs(
    output_dir: Path,
    *,
    label: str,
    manifest: dict[str, object],
    rows: Sequence[dict[str, str]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{label}.json"
    csv_path = output_dir / f"{label}.csv"
    json_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "symbol",
                "canonical_symbol",
                "name",
                "asset_type",
                "market",
                "metadata_source",
                "yahoo_symbol",
                "status",
                "code",
                "reason",
                "recommended_action",
                "policy_allowed",
                "complexity",
                "theme",
                "is_leveraged",
                "is_inverse",
                "message",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return {"manifest": str(json_path), "rows": str(csv_path)}


if __name__ == "__main__":
    raise SystemExit(main())
