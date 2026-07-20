from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from backend.forecast.sealed_audit import SealedForecastAuditRepository
from tools.manage_forecast_sealed_audit import main


def test_cli_initializes_status_and_exports_empty_sealed_audit(
    tmp_path: Path,
    capsys,
) -> None:
    database = tmp_path / "sealed.sqlite"
    symbols = tmp_path / "symbols.csv"
    symbols.write_text("symbol\nAAPL\n7203.T\n", encoding="utf-8")
    manifest_id = "fsa_cli_manifest_001"

    assert (
        main(
            [
                "init",
                "--database",
                str(database),
                "--manifest-id",
                manifest_id,
                "--symbols-file",
                str(symbols),
                "--horizons",
                "20,60",
                "--cohort",
                "new_calendar",
                "--accept-from",
                "2026-07-01T00:00:00Z",
                "--source-revision",
                "test-revision",
            ]
        )
        == 0
    )
    manifest = SealedForecastAuditRepository(database).get_manifest(manifest_id)
    assert manifest.symbols == ["7203.T", "AAPL"]
    assert manifest.horizons == [20, 60]

    assert (
        main(
            [
                "status",
                "--database",
                str(database),
                "--manifest-id",
                manifest_id,
            ]
        )
        == 0
    )
    assert "predictions=0 matured=0 pending=0" in capsys.readouterr().out

    output = tmp_path / "output"
    assert (
        main(
            [
                "export",
                "--database",
                str(database),
                "--manifest-id",
                manifest_id,
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert (output / "sealed_forecast_audit_manifest.json").is_file()
    assert (output / "forecast_model_validation_points.csv").is_file()
    report = (output / "sealed_forecast_audit_report.md").read_text("utf-8")
    assert "予測snapshot: 0" in report
    assert "runtime modelを自動変更しない" in report


def test_cli_captures_current_consensus_once_from_local_daily_bars(
    tmp_path: Path,
) -> None:
    database = tmp_path / "sealed.sqlite"
    metadata, ohlcv, origin_at = _write_dataset(tmp_path)
    manifest_id = "fsa_cli_capture_001"
    common = ["--database", str(database), "--manifest-id", manifest_id]

    assert (
        main(
            [
                "init",
                *common,
                "--symbol",
                "AAPL",
                "--horizons",
                "20",
                "--cohort",
                "new_calendar",
                "--accept-from",
                (origin_at - timedelta(days=1)).isoformat(),
                "--source-revision",
                "test-revision",
            ]
        )
        == 0
    )
    capture_args = [
        "capture",
        *common,
        "--source-revision",
        "test-revision",
        "--ohlcv",
        str(ohlcv),
        "--metadata",
        str(metadata),
        "--required-bars",
        "180",
    ]
    wrong_revision_args = [
        "wrong-revision" if value == "test-revision" else value for value in capture_args
    ]
    assert main(wrong_revision_args) == 1
    assert not SealedForecastAuditRepository(database).list_predictions(manifest_id)
    assert main(capture_args) == 0
    assert main(capture_args) == 0

    predictions = SealedForecastAuditRepository(database).list_predictions(manifest_id)
    assert len(predictions) == 1
    assert predictions[0].symbol == "AAPL"
    assert predictions[0].horizon_days == 20
    assert predictions[0].origin_at == origin_at
    assert predictions[0].source_bar_count == 200


def _write_dataset(tmp_path: Path) -> tuple[Path, Path, datetime]:
    metadata = tmp_path / "metadata.csv"
    metadata.write_text(
        "symbol,market,asset_type,currency,exchange,local_symbol\n"
        "AAPL,US,stock,USD,NASDAQ,AAPL\n",
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
        for index in range(200):
            close = Decimal("100") + Decimal(index) * Decimal("0.10")
            writer.writerow(
                {
                    "symbol": "AAPL",
                    "ts": (start + timedelta(days=index)).isoformat(),
                    "open": close,
                    "high": close + Decimal("0.25"),
                    "low": close - Decimal("0.25"),
                    "close": close,
                    "volume": "1000000",
                }
            )
    return metadata, ohlcv, origin_at
