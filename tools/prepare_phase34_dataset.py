from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SPLITS = ("tuning", "validation", "audit")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create fixed symbol-disjoint Phase 34 evaluation splits.",
    )
    parser.add_argument("--ohlcv", default="data/phase34_evaluation/ohlcv.csv")
    parser.add_argument("--metadata", default="data/phase34_evaluation/symbols.csv")
    parser.add_argument("--output-dir", default="data/phase34_evaluation/splits")
    args = parser.parse_args(argv)
    paths = prepare_phase34_splits(Path(args.ohlcv), Path(args.metadata), Path(args.output_dir))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def prepare_phase34_splits(
    ohlcv_path: Path,
    metadata_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    metadata_fields, metadata_rows = _read_rows(metadata_path)
    by_symbol = {
        row["symbol"].strip(): row for row in metadata_rows if row.get("symbol", "").strip()
    }
    assignments = assign_symbol_splits(by_symbol)
    ohlcv_fields, ohlcv_rows = _read_rows(ohlcv_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for split in SPLITS:
        symbols = {symbol for symbol, assigned in assignments.items() if assigned == split}
        split_dir = output_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        metadata_target = split_dir / "symbols.csv"
        ohlcv_target = split_dir / "ohlcv.csv"
        _write_rows(
            metadata_target, metadata_fields, [by_symbol[symbol] for symbol in sorted(symbols)]
        )
        _write_rows(
            ohlcv_target,
            ohlcv_fields,
            [row for row in ohlcv_rows if row.get("symbol", "").strip() in symbols],
        )
        paths[f"{split}_metadata"] = metadata_target
        paths[f"{split}_ohlcv"] = ohlcv_target
    manifest = output_dir / "phase34_split_manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["symbol", "market", "asset_type", "split"],
            lineterminator="\n",
        )
        writer.writeheader()
        for symbol in sorted(assignments):
            row = by_symbol[symbol]
            writer.writerow(
                {
                    "symbol": symbol,
                    "market": row.get("market") or "unknown",
                    "asset_type": row.get("asset_type") or "unknown",
                    "split": assignments[symbol],
                }
            )
    paths["manifest"] = manifest
    return paths


def assign_symbol_splits(metadata: dict[str, dict[str, str]]) -> dict[str, str]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for symbol, row in metadata.items():
        groups[(row.get("market") or "unknown", row.get("asset_type") or "unknown")].append(symbol)
    assignments: dict[str, str] = {}
    for group, symbols in sorted(groups.items()):
        ordered = sorted(
            symbols,
            key=lambda symbol: hashlib.sha256(
                f"phase34-v1|{group[0]}|{group[1]}|{symbol}".encode()
            ).hexdigest(),
        )
        for index, symbol in enumerate(ordered):
            assignments[symbol] = SPLITS[index % len(SPLITS)]
    return assignments


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV header not found: {path}")
        return list(reader.fieldnames), list(reader)


def _write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
