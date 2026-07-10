import csv
from pathlib import Path

from tools.prepare_phase34_dataset import assign_symbol_splits, prepare_phase34_splits


def test_assign_symbol_splits_is_deterministic_and_symbol_disjoint():
    metadata = {f"S{index}": {"market": "jp", "asset_type": "stock"} for index in range(9)}

    first = assign_symbol_splits(metadata)
    second = assign_symbol_splits(dict(reversed(list(metadata.items()))))

    assert first == second
    assert set(first.values()) == {"tuning", "validation", "audit"}
    assert all(list(first).count(symbol) == 1 for symbol in first)


def test_prepare_phase34_splits_writes_each_symbol_to_one_split(tmp_path: Path):
    metadata = tmp_path / "symbols.csv"
    ohlcv = tmp_path / "ohlcv.csv"
    metadata.write_text(
        "symbol,market,asset_type\nA,jp,stock\nB,jp,stock\nC,jp,stock\n",
        encoding="utf-8",
    )
    ohlcv.write_text(
        "symbol,ts,open,high,low,close,volume\n"
        "A,2025-01-01T00:00:00+00:00,1,1,1,1,1\n"
        "B,2025-01-01T00:00:00+00:00,1,1,1,1,1\n"
        "C,2025-01-01T00:00:00+00:00,1,1,1,1,1\n",
        encoding="utf-8",
    )

    paths = prepare_phase34_splits(ohlcv, metadata, tmp_path / "out")

    with paths["manifest"].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert {row["split"] for row in rows} == {"tuning", "validation", "audit"}
    split_symbols = []
    for split in ("tuning", "validation", "audit"):
        with paths[f"{split}_metadata"].open(encoding="utf-8", newline="") as handle:
            split_symbols.extend(row["symbol"] for row in csv.DictReader(handle))
    assert sorted(split_symbols) == ["A", "B", "C"]
