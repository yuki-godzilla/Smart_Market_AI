from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a replay-safe Forecast sealed audit cycle from local data or an explicit live snapshot."
        )
    )
    parser.add_argument(
        "--database",
        default="data/cache/forecast_sealed_audit.sqlite",
    )
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--required-bars", type=int, default=180)
    parser.add_argument("--ohlcv", default=None)
    parser.add_argument("--metadata", default=None)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--metadata-source", default="data/marketdata/symbol_universe.csv")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=6)
    args = parser.parse_args(argv)
    if args.required_bars < 80:
        parser.error("--required-bars must be at least 80")
    if args.years < 2:
        parser.error("--years must be at least 2")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if args.allow_live and (args.ohlcv or args.metadata):
        parser.error("--allow-live cannot be combined with --ohlcv or --metadata")
    if not args.allow_live and not (args.ohlcv and args.metadata):
        parser.error("local mode requires both --ohlcv and --metadata")
    return asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> int:
    from backend.forecast.sealed_audit import SealedForecastAuditRepository
    from backend.forecast.sealed_audit_cycle import (
        ForecastSealedAuditCycleError,
        create_forecast_sealed_audit_run_id,
        run_forecast_sealed_audit_cycle,
        write_forecast_sealed_audit_cycle_failure,
    )

    started_at = datetime.now(UTC)
    run_id = create_forecast_sealed_audit_run_id(started_at)
    run_dir = Path(args.output) / (f"{started_at:%Y%m%dT%H%M%SZ}_{secrets.token_hex(3)}")
    run_dir.mkdir(parents=True, exist_ok=False)
    repository = SealedForecastAuditRepository(Path(args.database))
    if args.allow_live:
        from backend.core.config import DataAccessConfig, TimeoutConfig
        from backend.forecast.live_dataset import collect_forecast_live_dataset
        from backend.marketdata.providers.yahoo import YahooMarketDataProviderAdapter

        manifest = repository.get_manifest(args.manifest_id)
        snapshot_dir = run_dir / "live_snapshot"
        provider = YahooMarketDataProviderAdapter(
            DataAccessConfig(
                provider="yahoo",
                allow_external_providers=True,
                timeouts_ms=TimeoutConfig(connect=5000, read=30000),
            )
        )
        collection = await collect_forecast_live_dataset(
            provider,
            provider_name="yahoo",
            symbols=manifest.symbols,
            start=started_at - timedelta(days=365 * args.years),
            end=started_at,
            batch_size=args.batch_size,
            metadata_source=Path(args.metadata_source),
            output_dir=snapshot_dir,
            started_at=started_at,
        )
        print(
            f"collection: complete={str(collection.complete).lower()} "
            f"bars={collection.bar_count} symbols={len(collection.returned_symbols)}"
        )
        if not collection.complete:
            error = ForecastSealedAuditCycleError(
                "live snapshot is incomplete: "
                + ",".join(sorted({failure.reason for failure in collection.failures}))
            )
            failure_path = write_forecast_sealed_audit_cycle_failure(
                run_dir,
                run_id=run_id,
                manifest_id=args.manifest_id,
                source_revision=args.source_revision,
                started_at=started_at,
                stage="collection",
                error=error,
            )
            print(f"live snapshot incomplete; sealed database unchanged: {snapshot_dir}")
            print(f"failure: {failure_path}")
            return 2
        ohlcv_path = Path(collection.ohlcv_path)
        metadata_path = Path(collection.metadata_path)
    else:
        ohlcv_path = Path(args.ohlcv)
        metadata_path = Path(args.metadata)

    try:
        result = run_forecast_sealed_audit_cycle(
            repository,
            manifest_id=args.manifest_id,
            source_revision=args.source_revision,
            ohlcv_path=ohlcv_path,
            metadata_path=metadata_path,
            required_bar_count=args.required_bars,
            output_dir=run_dir / "artifacts",
            backup_path=run_dir / "forecast_sealed_audit.sqlite",
            observed_at=started_at,
            run_id=run_id,
        )
    except (ForecastSealedAuditCycleError, ValueError) as exc:
        failure_path = write_forecast_sealed_audit_cycle_failure(
            run_dir,
            run_id=run_id,
            manifest_id=args.manifest_id,
            source_revision=args.source_revision,
            started_at=started_at,
            stage="cycle",
            error=exc,
        )
        print(f"sealed audit cycle failed: {exc}")
        print(f"failure: {failure_path}")
        return 1
    print(f"run: {result.run_id}")
    print(f"output: {run_dir}")
    print(
        f"capture inserted={result.capture.inserted_count} "
        f"existing={result.capture.existing_origin_skipped_count}"
    )
    print(
        f"matured inserted={result.maturation.inserted_count} "
        f"pending={result.summary.pending_count}"
    )
    print(f"backup: {result.backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
