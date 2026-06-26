from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
DEFAULT_RUN_DIR = PROJECT_ROOT / "data" / "marketdata" / "refresh_runs"
REFRESH_TOOL = PROJECT_ROOT / "tools" / "refresh_symbol_universe_metadata.py"
DEFAULT_METRICS = "per,pbr,roe_pct,dividend_yield_pct,market_cap,average_volume"


@dataclass(frozen=True)
class BatchPlan:
    name: str
    markets: tuple[str, ...]
    asset_type: str
    missing_any: str
    chunk_size: int
    timeout_seconds: float


PRESETS = {
    "all-core": BatchPlan(
        name="all-core",
        markets=("jp", "us", "hong_kong", "korea", "singapore", "thailand", "malaysia", "indonesia", "vietnam"),
        asset_type="",
        missing_any=DEFAULT_METRICS,
        chunk_size=200,
        timeout_seconds=20,
    ),
    "weak-asia": BatchPlan(
        name="weak-asia",
        markets=("vietnam", "singapore", "korea"),
        asset_type="",
        missing_any=DEFAULT_METRICS,
        chunk_size=50,
        timeout_seconds=30,
    ),
    "etf": BatchPlan(
        name="etf",
        markets=("",),
        asset_type="etf",
        missing_any="dividend_yield_pct,expense_ratio_pct,aum,average_volume",
        chunk_size=100,
        timeout_seconds=20,
    ),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run refresh_symbol_universe_metadata.py in checkpointed chunks."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--provider", default="yahoo")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="all-core")
    parser.add_argument("--market", default="", help="Override preset market with one market.")
    parser.add_argument("--asset-type", default=None, help="Override preset asset type.")
    parser.add_argument("--missing-any", default="", help="Override preset missing-any columns.")
    parser.add_argument("--chunk-size", type=int, default=0, help="Override preset chunk size.")
    parser.add_argument("--max-chunks", type=int, default=0, help="0 means no explicit cap.")
    parser.add_argument("--symbol-timeout-seconds", type=float, default=-1)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--fill-missing-only", action="store_true", default=True)
    parser.add_argument("--dry-run-refresh", action="store_true", help="Do not pass --write to refresh tool.")
    args = parser.parse_args(argv)

    plan = _resolve_plan(args)
    run_id = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    run_dir = args.run_dir / f"{plan.name}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = run_dir / "chunks.jsonl"
    failure_path = run_dir / "failed_symbols.csv"
    attempted_symbols: set[str] = set()
    failures: list[dict[str, str]] = []
    no_update_rows: list[dict[str, str]] = []
    chunks_run = 0

    print(
        json.dumps(
            {
                "event": "batch_start",
                "run_dir": _display_path(run_dir),
                "plan": plan.__dict__,
                "write": args.write and not args.dry_run_refresh,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )

    for market in plan.markets:
        while True:
            rows = _read_rows(args.csv)
            symbols = _select_next_symbols(
                rows,
                market=market,
                asset_type=plan.asset_type,
                missing_any=_split(plan.missing_any),
                limit=plan.chunk_size,
                attempted_symbols=attempted_symbols,
            )
            if not symbols:
                print(
                    json.dumps(
                        {"event": "market_done", "market": market or "(all)", "remaining_chunk": 0},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    flush=True,
                )
                break
            chunks_run += 1
            attempted_symbols.update(symbols)
            manifest_path = run_dir / f"chunk_{chunks_run:04d}.json"
            command = _refresh_command(
                args,
                plan,
                symbols=symbols,
                market=market,
                manifest_path=manifest_path,
            )
            print(
                json.dumps(
                    {
                        "event": "chunk_start",
                        "chunk": chunks_run,
                        "market": market or "(all)",
                        "symbols": len(symbols),
                        "first_symbol": symbols[0],
                        "last_symbol": symbols[-1],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
            completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, check=False)
            chunk_record = {
                "event": "chunk_done",
                "chunk": chunks_run,
                "market": market or "(all)",
                "returncode": completed.returncode,
                "manifest": _display_path(manifest_path),
            }
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                chunk_record.update(
                    {
                        "changed_rows": manifest.get("changed_rows", 0),
                        "failed_symbols": len(manifest.get("failed_symbols", [])),
                    }
                )
                for failure in manifest.get("failures", []):
                    if isinstance(failure, dict):
                        failures.append({str(k): str(v) for k, v in failure.items()})
                no_update_symbols = manifest.get("no_update_symbols", [])
                if isinstance(no_update_symbols, list):
                    no_update_rows.extend(
                        {
                            "symbol": str(symbol),
                            "market": market or "",
                            "reason": "provider_returned_no_metadata",
                            "manifest": _display_path(manifest_path),
                        }
                        for symbol in no_update_symbols
                    )
                unchanged_symbols = manifest.get("unchanged_update_symbols", [])
                if isinstance(unchanged_symbols, list):
                    no_update_rows.extend(
                        {
                            "symbol": str(symbol),
                            "market": market or "",
                            "reason": "metadata_fetched_but_no_blank_target_changed",
                            "manifest": _display_path(manifest_path),
                        }
                        for symbol in unchanged_symbols
                    )
            _append_jsonl(jsonl_path, chunk_record)
            print(json.dumps(chunk_record, ensure_ascii=False, sort_keys=True), flush=True)
            if completed.returncode != 0:
                _write_failures(failure_path, failures)
                _write_no_updates(run_dir / "no_update_symbols.csv", no_update_rows)
                print(
                    json.dumps(
                        {"event": "batch_aborted", "returncode": completed.returncode},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    file=sys.stderr,
                )
                return completed.returncode
            if args.max_chunks and chunks_run >= args.max_chunks:
                _write_failures(failure_path, failures)
                _write_no_updates(run_dir / "no_update_symbols.csv", no_update_rows)
                print(
                    json.dumps(
                        {"event": "batch_stopped", "reason": "max_chunks", "chunks": chunks_run},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    flush=True,
                )
                return 0

    no_update_path = run_dir / "no_update_symbols.csv"
    _write_failures(failure_path, failures)
    _write_no_updates(no_update_path, no_update_rows)
    print(
        json.dumps(
            {
                "event": "batch_done",
                "chunks": chunks_run,
                "attempted_symbols": len(attempted_symbols),
                "failure_rows": len(failures),
                "failure_csv": _display_path(failure_path),
                "no_update_rows": len(no_update_rows),
                "no_update_csv": _display_path(no_update_path),
                "chunks_jsonl": _display_path(jsonl_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def _resolve_plan(args: argparse.Namespace) -> BatchPlan:
    base = PRESETS[args.preset]
    markets = (args.market,) if args.market else base.markets
    asset_type = base.asset_type if args.asset_type is None else args.asset_type
    missing_any = args.missing_any or base.missing_any
    chunk_size = args.chunk_size or base.chunk_size
    timeout = base.timeout_seconds if args.symbol_timeout_seconds < 0 else args.symbol_timeout_seconds
    return BatchPlan(
        name=base.name,
        markets=markets,
        asset_type=asset_type,
        missing_any=missing_any,
        chunk_size=chunk_size,
        timeout_seconds=timeout,
    )


def _refresh_command(
    args: argparse.Namespace,
    plan: BatchPlan,
    *,
    symbols: Sequence[str],
    market: str,
    manifest_path: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(REFRESH_TOOL),
        "--csv",
        str(args.csv),
        "--provider",
        args.provider,
        "--symbols",
        ",".join(symbols),
        "--missing-any",
        plan.missing_any,
        "--manifest",
        str(manifest_path),
        "--progress-every",
        str(args.progress_every),
        "--symbol-timeout-seconds",
        str(plan.timeout_seconds),
    ]
    if market:
        command.extend(["--market", market])
    if plan.asset_type:
        command.extend(["--asset-type", plan.asset_type])
    if args.allow_live:
        command.append("--allow-live")
    if args.fill_missing_only:
        command.append("--fill-missing-only")
    if args.write and not args.dry_run_refresh:
        command.append("--write")
    return command


def _select_next_symbols(
    rows: Sequence[dict[str, str]],
    *,
    market: str,
    asset_type: str,
    missing_any: Sequence[str],
    limit: int,
    attempted_symbols: set[str],
) -> list[str]:
    selected: list[str] = []
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        if not symbol or symbol in attempted_symbols:
            continue
        if market and row.get("market", "") != market:
            continue
        if asset_type and row.get("asset_type", "") != asset_type:
            continue
        if missing_any and not any(not row.get(column, "").strip() for column in missing_any):
            continue
        selected.append(symbol)
        if len(selected) >= limit:
            break
    return selected


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [
            {str(key): "" if value is None else str(value).strip() for key, value in row.items()}
            for row in csv.DictReader(file)
            if row.get("symbol")
        ]


def _write_failures(path: Path, failures: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["symbol", "code", "message"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(failures)


def _write_no_updates(path: Path, rows: Sequence[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["symbol", "market", "reason", "manifest"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _append_jsonl(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
