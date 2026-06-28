from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOL_UNIVERSE_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "marketdata" / "live_checks"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import DataAccessConfig, TimeoutConfig  # noqa: E402
from backend.core.errors import AppError  # noqa: E402
from backend.marketdata.providers.yahoo import YahooMarketDataProviderAdapter  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check Yahoo OHLCV coverage for symbol_universe.csv rows."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_SYMBOL_UNIVERSE_CSV)
    parser.add_argument("--metadata-source", default="")
    parser.add_argument("--asset-type", default="stock")
    parser.add_argument("--market", default="jp")
    parser.add_argument("--symbols", default="", help="Comma-separated symbol allowlist.")
    parser.add_argument("--sample-size", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--start", type=_parse_date, required=True)
    parser.add_argument("--end", type=_parse_date, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    rows = _read_symbol_universe_rows(args.csv)
    selected_rows = _select_rows(
        rows,
        metadata_source=args.metadata_source,
        asset_type=args.asset_type,
        market=args.market,
        symbols=_parse_symbols(args.symbols),
    )
    check_rows = _coverage_check_rows(selected_rows)
    if args.sample_size > 0:
        selected_symbols = set(
            _even_sample([row["symbol"] for row in check_rows], args.sample_size)
        )
        check_rows = [row for row in check_rows if row["symbol"] in selected_symbols]
    if args.limit > 0:
        check_rows = check_rows[: args.limit]

    result = asyncio.run(
        _check_yahoo_coverage(
            check_rows,
            start=args.start,
            end=args.end,
            batch_size=args.batch_size,
            timeout_ms=args.timeout_ms,
        )
    )
    manifest = _manifest(
        result,
        selected_rows=len(selected_rows),
        metadata_source=args.metadata_source,
        asset_type=args.asset_type,
        market=args.market,
        sample_size=args.sample_size,
        limit=args.limit,
        batch_size=args.batch_size,
        timeout_ms=args.timeout_ms,
        start=args.start,
        end=args.end,
    )
    paths = _write_outputs(
        args.output_dir,
        label=args.label or _default_label(args),
        manifest=manifest,
        rows=result,
    )
    print(json.dumps({**manifest, "outputs": paths}, ensure_ascii=False, indent=2))
    return 0 if manifest["failed_symbols"] == 0 else 1


def _read_symbol_universe_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {key: "" if value is None else str(value).strip() for key, value in row.items()}
            for row in csv.DictReader(file)
        ]


def _select_rows(
    rows: Sequence[dict[str, str]],
    *,
    metadata_source: str,
    asset_type: str,
    market: str,
    symbols: Sequence[str] = (),
) -> list[dict[str, str]]:
    symbol_allowlist = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
    return [
        row
        for row in rows
        if (not metadata_source or row.get("metadata_source") == metadata_source)
        and (not asset_type or row.get("asset_type") == asset_type)
        and (not market or row.get("market") == market)
        and (not symbol_allowlist or row.get("symbol", "").upper() in symbol_allowlist)
        and row.get("symbol")
    ]


def _coverage_check_rows(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    check_rows: list[dict[str, str]] = []
    for row in rows:
        symbol = row.get("symbol", "").strip()
        provider_symbol = (row.get("yahoo_symbol", "") or symbol).strip()
        if not symbol or not provider_symbol:
            continue
        check_rows.append(
            {
                "symbol": symbol,
                "provider_symbol": provider_symbol,
                "yahoo_symbol_status": row.get("yahoo_symbol_status", ""),
            }
        )
    return check_rows


def _even_sample(symbols: Sequence[str], sample_size: int) -> list[str]:
    if sample_size <= 0 or sample_size >= len(symbols):
        return list(symbols)
    if sample_size == 1:
        return [symbols[0]]
    max_index = len(symbols) - 1
    indexes = sorted({round(index * max_index / (sample_size - 1)) for index in range(sample_size)})
    return [symbols[index] for index in indexes]


async def _check_yahoo_coverage(
    rows: Sequence[dict[str, str]],
    *,
    start: date,
    end: date,
    batch_size: int,
    timeout_ms: int,
) -> list[dict[str, str]]:
    provider = YahooMarketDataProviderAdapter(
        DataAccessConfig(
            provider="yahoo",
            allow_external_providers=True,
            timeouts_ms=TimeoutConfig(read=timeout_ms),
        )
    )
    results: list[dict[str, str]] = []
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end, datetime.min.time(), tzinfo=UTC)

    for batch_index, batch_rows in enumerate(_chunks(list(rows), batch_size), start=1):
        provider_symbols = [row["provider_symbol"] for row in batch_rows]
        try:
            bars = await provider.fetch_ohlcv(
                provider_symbols, start=start_dt, end=end_dt, interval="1d"
            )
        except AppError as exc:
            results.extend(
                _failed_row(
                    row,
                    status="batch_error",
                    code=str(exc.code),
                    message=str(exc.message),
                    batch_index=batch_index,
                )
                for row in batch_rows
            )
            continue
        except Exception as exc:  # pragma: no cover - live smoke guardrail
            results.extend(
                _failed_row(
                    row,
                    status="batch_error",
                    code=type(exc).__name__,
                    message=str(exc),
                    batch_index=batch_index,
                )
                for row in batch_rows
            )
            continue

        count_by_symbol = Counter(bar.symbol.raw for bar in bars)
        timestamps_by_symbol: dict[str, list[datetime]] = {}
        for bar in bars:
            timestamps_by_symbol.setdefault(bar.symbol.raw, []).append(bar.ts)
        for row in batch_rows:
            provider_symbol = row["provider_symbol"]
            bar_count = count_by_symbol.get(provider_symbol, 0)
            timestamps = sorted(timestamps_by_symbol.get(provider_symbol, []))
            if bar_count:
                results.append(
                    {
                        "symbol": row["symbol"],
                        "provider_symbol": provider_symbol,
                        "yahoo_symbol_status": row.get("yahoo_symbol_status", ""),
                        "status": "ok",
                        "bar_count": str(bar_count),
                        "first_date": timestamps[0].date().isoformat() if timestamps else "",
                        "last_date": timestamps[-1].date().isoformat() if timestamps else "",
                        "code": "",
                        "message": "",
                        "recommended_action": _recommended_action("ok", row),
                        "batch_index": str(batch_index),
                    }
                )
            else:
                results.append(
                    _failed_row(
                        row,
                        status="no_bars",
                        code="YAHOO-NO-BARS",
                        message="Yahoo returned no OHLCV bars for this provider symbol.",
                        batch_index=batch_index,
                    )
                )
    return results


def _failed_row(
    row: dict[str, str],
    *,
    status: str,
    code: str,
    message: str,
    batch_index: int,
) -> dict[str, str]:
    return {
        "symbol": row.get("symbol", ""),
        "provider_symbol": row.get("provider_symbol", ""),
        "yahoo_symbol_status": row.get("yahoo_symbol_status", ""),
        "status": status,
        "bar_count": "0",
        "first_date": "",
        "last_date": "",
        "code": code,
        "message": message,
        "recommended_action": _recommended_action(status, row),
        "batch_index": str(batch_index),
    }


def _recommended_action(status: str, row: dict[str, str]) -> str:
    if status == "ok":
        return "mark_confirmed"
    current_status = row.get("yahoo_symbol_status", "")
    if current_status in {"confirmed", "generated", "stale"}:
        return "review_or_mark_unavailable"
    return "keep_requires_review_or_mark_unavailable"


def _manifest(
    rows: Sequence[dict[str, str]],
    *,
    selected_rows: int,
    metadata_source: str,
    asset_type: str,
    market: str,
    sample_size: int,
    limit: int,
    batch_size: int,
    timeout_ms: int,
    start: date,
    end: date,
) -> dict[str, object]:
    checked_symbols = len(rows)
    ok_symbols = sum(1 for row in rows if row["status"] == "ok")
    failed_rows = [row for row in rows if row["status"] != "ok"]
    return {
        "operation": "symbol_universe_yahoo_coverage_check",
        "provider": "yahoo",
        "metadata_source": metadata_source,
        "asset_type": asset_type,
        "market": market,
        "selected_rows": selected_rows,
        "checked_symbols": checked_symbols,
        "ok_symbols": ok_symbols,
        "failed_symbols": len(failed_rows),
        "success_rate": round(ok_symbols / checked_symbols, 4) if checked_symbols else 0,
        "sample_size": sample_size,
        "limit": limit,
        "batch_size": batch_size,
        "timeout_ms": timeout_ms,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "checked_at": datetime.now(tz=UTC).isoformat(),
        "failure_code_counts": dict(Counter(row["code"] for row in failed_rows)),
        "failed_symbol_sample": [row["symbol"] for row in failed_rows[:50]],
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
                "provider_symbol",
                "yahoo_symbol_status",
                "status",
                "bar_count",
                "first_date",
                "last_date",
                "code",
                "message",
                "recommended_action",
                "batch_index",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return {
        "manifest": str(json_path),
        "rows": str(csv_path),
    }


def _default_label(args: argparse.Namespace) -> str:
    scope = f"sample{args.sample_size}" if args.sample_size else "full"
    return f"yahoo_coverage_{args.metadata_source}_{scope}_{args.end.isoformat().replace('-', '')}"


def _chunks(symbols: Sequence[str], size: int) -> list[list[str]]:
    if size <= 0:
        raise ValueError("batch-size must be greater than 0.")
    return [list(symbols[index : index + size]) for index in range(0, len(symbols), size)]


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_symbols(value: str) -> list[str]:
    return [symbol.strip() for symbol in value.split(",") if symbol.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
