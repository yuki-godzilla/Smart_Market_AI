from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pydantic import TypeAdapter  # noqa: E402

from backend.symbols.contracts import SymbolRecord  # noqa: E402
from backend.symbols.repository import (  # noqa: E402
    load_symbol_record,
    load_symbol_records,
    save_symbol_records,
)

LEGACY_RECORD_COUNT = 5_000
BATCH_RECORD_COUNT = 1_000
LOOKUP_REPEAT_COUNT = 1_000
MAX_MIGRATION_SECONDS = 10.0
MAX_LOOKUP_SECONDS = 1.5
MAX_BATCH_UPSERT_SECONDS = 2.0

_SYMBOL_RECORD_MAP_ADAPTER = TypeAdapter(dict[str, SymbolRecord])


def main() -> int:
    now = datetime(2026, 6, 5, 12, 0, 0)
    with TemporaryDirectory(prefix="smai-symbol-cache-perf-") as temp_dir:
        cache_dir = Path(temp_dir)
        _write_legacy_json_cache(cache_dir, now=now)

        migration_seconds = _elapsed(lambda: load_symbol_records(cache_dir=cache_dir))
        loaded_count = len(load_symbol_records(cache_dir=cache_dir))

        lookup_seconds = _elapsed(
            lambda: [
                load_symbol_record(f"T{index % LEGACY_RECORD_COUNT:04d}", cache_dir=cache_dir)
                for index in range(LOOKUP_REPEAT_COUNT)
            ]
        )

        batch_records = [
            SymbolRecord(
                symbol=f"N{index:04d}",
                provider="perf",
                updated_at=now,
                normalized_fields={"name": f"New Symbol {index}", "per": index / 10},
            )
            for index in range(BATCH_RECORD_COUNT)
        ]
        batch_seconds = _elapsed(lambda: save_symbol_records(batch_records, cache_dir=cache_dir))

        db_size = (cache_dir / "symbols_cache.sqlite").stat().st_size

    print(f"legacy_records={LEGACY_RECORD_COUNT}")
    print(f"loaded_records_after_migration={loaded_count}")
    print(f"migration_seconds={migration_seconds:.4f}")
    print(f"lookup_repeat_count={LOOKUP_REPEAT_COUNT}")
    print(f"lookup_seconds={lookup_seconds:.4f}")
    print(f"batch_upsert_records={BATCH_RECORD_COUNT}")
    print(f"batch_upsert_seconds={batch_seconds:.4f}")
    print(f"sqlite_bytes={db_size}")

    failures = []
    if loaded_count != LEGACY_RECORD_COUNT:
        failures.append(f"loaded_count expected {LEGACY_RECORD_COUNT}, got {loaded_count}")
    if migration_seconds > MAX_MIGRATION_SECONDS:
        failures.append(f"migration_seconds exceeded {MAX_MIGRATION_SECONDS}")
    if lookup_seconds > MAX_LOOKUP_SECONDS:
        failures.append(f"lookup_seconds exceeded {MAX_LOOKUP_SECONDS}")
    if batch_seconds > MAX_BATCH_UPSERT_SECONDS:
        failures.append(f"batch_upsert_seconds exceeded {MAX_BATCH_UPSERT_SECONDS}")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PASS")
    return 0


def _write_legacy_json_cache(cache_dir: Path, *, now: datetime) -> None:
    records = {
        f"T{index:04d}": SymbolRecord(
            symbol=f"T{index:04d}",
            provider="legacy-json",
            updated_at=now,
            normalized_fields={
                "name": f"Legacy Symbol {index}",
                "market": "JP" if index % 2 == 0 else "US",
                "per": index / 10,
                "pbr": index / 100,
            },
        )
        for index in range(LEGACY_RECORD_COUNT)
    }
    (cache_dir / "symbols_cache.json").write_text(
        _SYMBOL_RECORD_MAP_ADAPTER.dump_json(records).decode("utf-8"),
        encoding="utf-8",
    )


def _elapsed(action) -> float:
    started = perf_counter()
    action()
    return perf_counter() - started


if __name__ == "__main__":
    raise SystemExit(main())
