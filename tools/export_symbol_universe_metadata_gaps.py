from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "marketdata" / "manual_metadata_patches" / "metadata_gap_candidates.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "marketdata" / "manual_metadata_patches" / "metadata_gap_report.json"
CORE_METRICS = ("per", "pbr", "roe_pct", "dividend_yield_pct", "market_cap", "average_volume")
PATCH_VALUE_COLUMNS = (
    "per",
    "pbr",
    "roe_pct",
    "dividend_yield_pct",
    "market_cap",
    "average_volume",
    "expense_ratio_pct",
    "aum",
    "sector_gics",
    "industry_gics",
)
PRESETS: dict[str, dict[str, str]] = {
    "weak-asia": {
        "markets": "vietnam,singapore,korea",
        "metrics": ",".join(CORE_METRICS),
    },
    "korea-pbr": {
        "markets": "korea",
        "metrics": "pbr",
    },
    "vietnam-core": {
        "markets": "vietnam",
        "metrics": "per,pbr,roe_pct,dividend_yield_pct,market_cap,average_volume",
    },
    "singapore-core": {
        "markets": "singapore",
        "metrics": "pbr,roe_pct,market_cap",
    },
    "sector-gics": {
        "markets": "",
        "metrics": "sector_gics,industry_gics",
    },
    "etf-core": {
        "asset_type": "etf",
        "metrics": "expense_ratio_pct,aum,dividend_yield_pct,average_volume",
    },
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export missing metadata candidates for trusted-source manual review. "
            "The output can be filled and then applied with apply_symbol_universe_metadata_patch.py."
        )
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--preset", choices=sorted(PRESETS), default="weak-asia")
    parser.add_argument("--markets", default="", help="Comma-separated market allowlist; overrides preset.")
    parser.add_argument("--asset-type", default=None, help="Asset type filter; overrides preset when set.")
    parser.add_argument("--metrics", default="", help="Comma-separated target metrics; overrides preset.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--include-complete", action="store_true", help="Include rows even when target metrics are complete.")
    parser.add_argument("--sort", choices=("gap_count", "market", "symbol"), default="gap_count")
    args = parser.parse_args(argv)

    rows = _read_rows(args.csv)
    preset = PRESETS[args.preset]
    markets = _split(args.markets or preset.get("markets", ""))
    asset_type = preset.get("asset_type", "") if args.asset_type is None else args.asset_type
    metrics = _split(args.metrics or preset.get("metrics", ",".join(CORE_METRICS)))

    candidates = _build_candidates(
        rows,
        markets=markets,
        asset_type=asset_type,
        metrics=metrics,
        include_complete=args.include_complete,
    )
    if args.sort == "gap_count":
        candidates.sort(key=lambda row: (-int(row["gap_count"]), row["market"], row["symbol"]))
    elif args.sort == "market":
        candidates.sort(key=lambda row: (row["market"], row["symbol"]))
    else:
        candidates.sort(key=lambda row: row["symbol"])
    if args.limit > 0:
        candidates = candidates[: args.limit]

    fieldnames = _fieldnames(metrics)
    _write_csv(args.output, candidates, fieldnames)
    report = _report(candidates, metrics=metrics, markets=markets, asset_type=asset_type, preset=args.preset)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**report, "output": _display_path(args.output), "report": _display_path(args.report)}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_candidates(
    rows: Sequence[dict[str, str]],
    *,
    markets: Sequence[str],
    asset_type: str,
    metrics: Sequence[str],
    include_complete: bool,
) -> list[dict[str, str]]:
    market_set = {m for m in markets if m}
    candidates: list[dict[str, str]] = []
    for row in rows:
        if market_set and row.get("market", "") not in market_set:
            continue
        if asset_type and row.get("asset_type", "") != asset_type:
            continue
        missing = [metric for metric in metrics if not row.get(metric, "").strip()]
        if not include_complete and not missing:
            continue
        symbol = row.get("symbol", "").strip()
        name = row.get("name", "").strip()
        market = row.get("market", "").strip()
        candidate = {
            "symbol": symbol,
            "name": name,
            "market": market,
            "asset_type": row.get("asset_type", "").strip(),
            "currency": row.get("currency", "").strip(),
            "yahoo_symbol": row.get("yahoo_symbol", "").strip(),
            "missing_metrics": ",".join(missing),
            "gap_count": str(len(missing)),
            "recommended_source": _recommended_source(market, row.get("asset_type", "")),
            "source": "",
            "source_url": "",
            "as_of": "",
            "quality": "reviewed",
            "note": "",
            "search_query": _search_query(symbol=symbol, name=name, market=market, missing=missing),
        }
        for metric in PATCH_VALUE_COLUMNS:
            candidate[metric] = row.get(metric, "") if metric not in missing else ""
        candidates.append(candidate)
    return candidates


def _recommended_source(market: str, asset_type: str) -> str:
    if asset_type == "etf":
        return "fund issuer factsheet / exchange page / Yahoo Finance"
    if market == "korea":
        return "KRX / company IR / Yahoo Finance fallback"
    if market == "vietnam":
        return "HOSE/HNX company page / Vietstock / company IR"
    if market == "singapore":
        return "SGX company page / company IR / Yahoo Finance fallback"
    if market == "hong_kong":
        return "HKEX / company IR / Yahoo Finance fallback"
    return "exchange or company IR / Yahoo Finance fallback"


def _search_query(*, symbol: str, name: str, market: str, missing: Sequence[str]) -> str:
    metrics = " ".join(missing[:4])
    return f"{symbol} {name} {market} {metrics} financial metrics"


def _report(candidates: Sequence[dict[str, str]], *, metrics: Sequence[str], markets: Sequence[str], asset_type: str, preset: str) -> dict[str, object]:
    by_market: Counter[str] = Counter(row.get("market", "") or "(blank)" for row in candidates)
    by_metric: Counter[str] = Counter()
    for row in candidates:
        for metric in _split(row.get("missing_metrics", "")):
            by_metric[metric] += 1
    return {
        "operation": "symbol_universe_metadata_gap_export",
        "preset": preset,
        "markets": list(markets),
        "asset_type": asset_type,
        "metrics": list(metrics),
        "candidate_rows": len(candidates),
        "candidate_rows_by_market": dict(sorted(by_market.items())),
        "missing_cells_by_metric": dict(sorted(by_metric.items())),
        "updated_at": datetime.now().astimezone().isoformat(),
    }


def _fieldnames(metrics: Sequence[str]) -> list[str]:
    base = [
        "symbol",
        "name",
        "market",
        "asset_type",
        "currency",
        "yahoo_symbol",
        "missing_metrics",
        "gap_count",
        "recommended_source",
    ]
    value_columns = [column for column in PATCH_VALUE_COLUMNS if column in set(metrics) or column in {"sector_gics", "industry_gics"}]
    return base + value_columns + ["source", "source_url", "as_of", "quality", "note", "search_query"]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in csv.DictReader(file)
            if row.get("symbol")
        ]


def _write_csv(path: Path, rows: Sequence[dict[str, str]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
