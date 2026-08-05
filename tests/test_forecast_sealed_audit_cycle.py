from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from filelock import FileLock

from backend.forecast.sealed_audit import (
    SealedForecastAuditRepository,
    create_forecast_sealed_audit_manifest,
)
from backend.forecast.sealed_audit_cycle import (
    ForecastSealedAuditCycleError,
    run_forecast_sealed_audit_cycle,
)
from tools.run_forecast_sealed_audit_cycle import main as run_cycle_main


def test_cycle_is_replay_safe_and_creates_verified_backup(tmp_path: Path) -> None:
    metadata, ohlcv, origin_at = _dataset(tmp_path, ["AAPL"])
    repository = SealedForecastAuditRepository(tmp_path / "sealed.sqlite")
    manifest = create_forecast_sealed_audit_manifest(
        symbols=["AAPL"],
        horizons=[20],
        created_at=origin_at + timedelta(hours=1),
        accept_origins_at_or_after=origin_at - timedelta(days=1),
        cohort="new_calendar",
        source_revision="frozen-revision",
        manifest_id="fsa_cycle_manifest_001",
    )
    repository.add_manifest(manifest)

    first = run_forecast_sealed_audit_cycle(
        repository,
        manifest_id=manifest.manifest_id,
        source_revision="frozen-revision",
        ohlcv_path=ohlcv,
        metadata_path=metadata,
        required_bar_count=180,
        output_dir=tmp_path / "first",
        backup_path=tmp_path / "first.sqlite",
        observed_at=origin_at + timedelta(hours=2),
    )
    second = run_forecast_sealed_audit_cycle(
        repository,
        manifest_id=manifest.manifest_id,
        source_revision="frozen-revision",
        ohlcv_path=ohlcv,
        metadata_path=metadata,
        required_bar_count=180,
        output_dir=tmp_path / "second",
        backup_path=tmp_path / "second.sqlite",
        observed_at=origin_at + timedelta(hours=3),
    )

    assert first.capture.inserted_count == 1
    assert first.integrity.prediction_count == 1
    assert second.capture.inserted_count == 0
    assert second.capture.existing_origin_skipped_count == 1
    assert second.summary.pending_count == 1
    assert "maturation:target_not_yet_available=1" in second.warnings
    backup = SealedForecastAuditRepository(Path(second.backup_path))
    assert backup.verify_integrity().prediction_count == 1
    assert (tmp_path / "second" / "sealed_forecast_audit_cycle.json").is_file()


def test_cycle_rejects_incomplete_frozen_cohort_before_capture(tmp_path: Path) -> None:
    metadata, ohlcv, origin_at = _dataset(tmp_path, ["AAPL"])
    repository = SealedForecastAuditRepository(tmp_path / "sealed.sqlite")
    manifest = create_forecast_sealed_audit_manifest(
        symbols=["AAPL", "MSFT"],
        horizons=[20],
        created_at=origin_at + timedelta(hours=1),
        accept_origins_at_or_after=origin_at - timedelta(days=1),
        cohort="new_calendar",
        source_revision="frozen-revision",
        manifest_id="fsa_cycle_incomplete_001",
    )
    repository.add_manifest(manifest)

    with pytest.raises(ForecastSealedAuditCycleError, match="MSFT"):
        run_forecast_sealed_audit_cycle(
            repository,
            manifest_id=manifest.manifest_id,
            source_revision="frozen-revision",
            ohlcv_path=ohlcv,
            metadata_path=metadata,
            required_bar_count=180,
            output_dir=tmp_path / "output",
            backup_path=tmp_path / "backup.sqlite",
            observed_at=origin_at + timedelta(hours=2),
        )
    assert repository.list_predictions(manifest.manifest_id) == []


def test_cycle_rejects_concurrent_run_for_same_database(tmp_path: Path) -> None:
    metadata, ohlcv, origin_at = _dataset(tmp_path, ["AAPL"])
    repository = SealedForecastAuditRepository(tmp_path / "sealed.sqlite")
    manifest = create_forecast_sealed_audit_manifest(
        symbols=["AAPL"],
        horizons=[20],
        created_at=origin_at + timedelta(hours=1),
        accept_origins_at_or_after=origin_at - timedelta(days=1),
        cohort="new_calendar",
        source_revision="frozen-revision",
        manifest_id="fsa_cycle_lock_001",
    )
    repository.add_manifest(manifest)
    lock_path = repository.path.with_name(f"{repository.path.name}.cycle.lock")

    with FileLock(str(lock_path), timeout=0):
        with pytest.raises(ForecastSealedAuditCycleError, match="already running"):
            run_forecast_sealed_audit_cycle(
                repository,
                manifest_id=manifest.manifest_id,
                source_revision="frozen-revision",
                ohlcv_path=ohlcv,
                metadata_path=metadata,
                required_bar_count=180,
                output_dir=tmp_path / "output",
                backup_path=tmp_path / "backup.sqlite",
                observed_at=origin_at + timedelta(hours=2),
            )
    assert repository.list_predictions(manifest.manifest_id) == []


def test_run_cycle_cli_executes_local_replay_safe_operation(tmp_path: Path) -> None:
    metadata, ohlcv, origin_at = _dataset(tmp_path, ["AAPL"])
    database = tmp_path / "sealed.sqlite"
    repository = SealedForecastAuditRepository(database)
    manifest = create_forecast_sealed_audit_manifest(
        symbols=["AAPL"],
        horizons=[20],
        created_at=origin_at + timedelta(hours=1),
        accept_origins_at_or_after=origin_at - timedelta(days=1),
        cohort="new_calendar",
        source_revision="frozen-revision",
        manifest_id="fsa_cycle_cli_001",
    )
    repository.add_manifest(manifest)
    output = tmp_path / "runs"

    assert (
        run_cycle_main(
            [
                "--database",
                str(database),
                "--manifest-id",
                manifest.manifest_id,
                "--source-revision",
                "frozen-revision",
                "--output",
                str(output),
                "--ohlcv",
                str(ohlcv),
                "--metadata",
                str(metadata),
            ]
        )
        == 0
    )
    run_dirs = list(output.iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "forecast_sealed_audit.sqlite").is_file()
    assert (run_dirs[0] / "artifacts" / "sealed_forecast_audit_cycle.json").is_file()

    failed_output = tmp_path / "failed-runs"
    failed_args = [
        "--database",
        str(database),
        "--manifest-id",
        manifest.manifest_id,
        "--source-revision",
        "wrong-revision",
        "--output",
        str(failed_output),
        "--ohlcv",
        str(ohlcv),
        "--metadata",
        str(metadata),
    ]
    assert run_cycle_main(failed_args) == 1
    failed_run = next(failed_output.iterdir())
    failure = json.loads(
        (failed_run / "sealed_forecast_audit_cycle_failure.json").read_text("utf-8")
    )
    assert failure["status"] == "failed"
    assert failure["stage"] == "cycle"
    assert failure["retry_safe"] is True


def _dataset(tmp_path: Path, symbols: list[str]) -> tuple[Path, Path, datetime]:
    metadata = tmp_path / "metadata.csv"
    metadata.write_text(
        "symbol,market,asset_type,currency,exchange,local_symbol\n"
        + "".join(f"{symbol},US,stock,USD,NASDAQ,{symbol}\n" for symbol in symbols),
        encoding="utf-8",
    )
    origin_at = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start = origin_at - timedelta(days=199)
    ohlcv = tmp_path / "ohlcv.csv"
    with ohlcv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["symbol", "ts", "open", "high", "low", "close", "volume"],
            lineterminator="\n",
        )
        writer.writeheader()
        for symbol in symbols:
            for index in range(200):
                close = Decimal("100") + Decimal(index) * Decimal("0.10")
                writer.writerow(
                    {
                        "symbol": symbol,
                        "ts": (start + timedelta(days=index)).isoformat(),
                        "open": close,
                        "high": close + Decimal("0.25"),
                        "low": close - Decimal("0.25"),
                        "close": close,
                        "volume": "1000000",
                    }
                )
    return metadata, ohlcv, origin_at
