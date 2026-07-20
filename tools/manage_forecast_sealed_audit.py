from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return _initialize(args, parser)
    if args.command == "capture":
        return _capture(args)
    if args.command == "mature":
        return _mature(args)
    if args.command in {"status", "export"}:
        return _status_or_export(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "backup":
        return _backup(args)
    parser.error("a command is required")
    return 2


def _parser() -> argparse.ArgumentParser:
    from backend.forecast.sealed_audit import DEFAULT_SEALED_AUDIT_DATABASE

    parser = argparse.ArgumentParser(
        description="Manage append-only point-in-time Forecast sealed audits."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Freeze a new audit manifest.")
    _database_argument(init_parser, DEFAULT_SEALED_AUDIT_DATABASE)
    init_parser.add_argument("--manifest-id", default=None)
    init_parser.add_argument("--symbol", action="append", default=[])
    init_parser.add_argument("--symbols-file", default=None)
    init_parser.add_argument("--horizons", default="20,40,60,80,100,120")
    init_parser.add_argument(
        "--cohort", choices=("new_calendar", "new_symbol", "mixed"), required=True
    )
    init_parser.add_argument("--accept-from", required=True)
    init_parser.add_argument("--source-revision", required=True)
    init_parser.add_argument("--min-cases-per-horizon", type=int, default=100)

    capture_parser = subparsers.add_parser(
        "capture", help="Capture current consensus predictions from a local OHLCV snapshot."
    )
    _database_argument(capture_parser, DEFAULT_SEALED_AUDIT_DATABASE)
    _manifest_argument(capture_parser)
    capture_parser.add_argument("--source-revision", required=True)
    _dataset_arguments(capture_parser)

    mature_parser = subparsers.add_parser(
        "mature", help="Attach outcomes that now have enough later trading bars."
    )
    _database_argument(mature_parser, DEFAULT_SEALED_AUDIT_DATABASE)
    _manifest_argument(mature_parser)
    _dataset_arguments(mature_parser)

    status_parser = subparsers.add_parser("status", help="Print maturity by horizon.")
    _database_argument(status_parser, DEFAULT_SEALED_AUDIT_DATABASE)
    _manifest_argument(status_parser)

    export_parser = subparsers.add_parser(
        "export", help="Write compatible evaluation CSV and a Japanese status report."
    )
    _database_argument(export_parser, DEFAULT_SEALED_AUDIT_DATABASE)
    _manifest_argument(export_parser)
    export_parser.add_argument("--output", required=True)

    verify_parser = subparsers.add_parser(
        "verify", help="Validate SQLite, foreign keys, schemas, and every content digest."
    )
    _database_argument(verify_parser, DEFAULT_SEALED_AUDIT_DATABASE)

    backup_parser = subparsers.add_parser(
        "backup", help="Create an atomic, integrity-checked online SQLite backup."
    )
    _database_argument(backup_parser, DEFAULT_SEALED_AUDIT_DATABASE)
    backup_parser.add_argument("--output", required=True)
    return parser


def _database_argument(parser: argparse.ArgumentParser, default: Path) -> None:
    parser.add_argument("--database", default=str(default))


def _manifest_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest-id", required=True)


def _dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ohlcv", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--required-bars", type=int, default=180)


def _initialize(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    from backend.forecast.sealed_audit import (
        SealedForecastAuditRepository,
        create_forecast_sealed_audit_manifest,
    )

    try:
        symbols = [*args.symbol, *_symbols_from_file(args.symbols_file)]
        if not symbols:
            parser.error("init requires --symbol or --symbols-file")
        horizons = _parse_horizons(args.horizons)
        accept_from = _parse_datetime(args.accept_from)
        manifest = create_forecast_sealed_audit_manifest(
            symbols=symbols,
            horizons=horizons,
            created_at=datetime.now(UTC),
            accept_origins_at_or_after=accept_from,
            cohort=args.cohort,
            source_revision=args.source_revision,
            manifest_id=args.manifest_id,
            min_cases_per_horizon=args.min_cases_per_horizon,
        )
    except ValueError as exc:
        parser.error(str(exc))
    inserted = SealedForecastAuditRepository(Path(args.database)).add_manifest(manifest)
    print(f"manifest: {manifest.manifest_id}")
    print(f"database: {args.database}")
    print(f"created: {str(inserted).lower()}")
    print(f"symbols: {len(manifest.symbols)}")
    print("horizons: " + ",".join(str(value) for value in manifest.horizons))
    return 0


def _capture(args: argparse.Namespace) -> int:
    from backend.forecast import (
        AUDITED_HORIZON_MAX_DAYS,
        advanced_forecast_adapter_keys,
        evaluate_advanced_forecast,
        summarize_advanced_forecast_evaluations,
    )
    from backend.forecast.dataset import load_forecast_evaluation_dataset
    from backend.forecast.sealed_audit import (
        SealedForecastAuditRepository,
        build_forecast_sealed_prediction,
    )

    repository = SealedForecastAuditRepository(Path(args.database))
    manifest = repository.get_manifest(args.manifest_id)
    if args.source_revision.strip() != manifest.source_revision:
        print("source revision differs from the frozen manifest")
        return 1
    dataset = load_forecast_evaluation_dataset(
        Path(args.ohlcv),
        Path(args.metadata),
        required_bar_count=args.required_bars,
    )
    cases = {case.symbol.strip().upper(): case for case in dataset.cases}
    existing = {
        (item.symbol, item.horizon_days, item.origin_at)
        for item in repository.list_predictions(manifest.manifest_id)
    }
    recorded_at = datetime.now(UTC)
    predictions = []
    failures: list[str] = []
    skipped_existing = 0
    for symbol in manifest.symbols:
        case = cases.get(symbol)
        if case is None:
            failures.append(f"{symbol}:eligible_daily_bars_missing")
            continue
        origin_at = max(bar.ts for bar in case.bars)
        for horizon in manifest.horizons:
            if (symbol, horizon, origin_at) in existing:
                skipped_existing += 1
                continue
            evaluations = []
            adapter_names = (
                advanced_forecast_adapter_keys()
                if horizon <= AUDITED_HORIZON_MAX_DAYS
                else ("advanced_quantile",)
            )
            for adapter_name in adapter_names:
                try:
                    evaluations.append(
                        evaluate_advanced_forecast(
                            case.bars,
                            adapter_name=adapter_name,
                            horizon_days=horizon,
                        )
                    )
                except ValueError:
                    continue
            consensus = summarize_advanced_forecast_evaluations(evaluations)
            if consensus is None:
                failures.append(f"{symbol}/{horizon}:consensus_unavailable")
                continue
            try:
                predictions.append(
                    build_forecast_sealed_prediction(
                        manifest,
                        consensus,
                        case.bars,
                        recorded_at=recorded_at,
                        market=case.market,
                        asset_type=case.asset_type,
                        regime=case.regime,
                    )
                )
            except ValueError as exc:
                failures.append(f"{symbol}/{horizon}:{exc}")
    result = repository.add_predictions(predictions)
    print(f"manifest: {manifest.manifest_id}")
    print(f"inserted: {result.inserted_count}")
    print(f"duplicates: {result.duplicate_count}")
    print(f"existing origin skipped: {skipped_existing}")
    if failures:
        print("failures:")
        for failure in failures:
            print(f"- {failure}")
    return 1 if failures else 0


def _mature(args: argparse.Namespace) -> int:
    from backend.forecast.dataset import load_forecast_evaluation_dataset
    from backend.forecast.sealed_audit import (
        SealedForecastAuditRepository,
        mature_forecast_sealed_predictions,
    )

    repository = SealedForecastAuditRepository(Path(args.database))
    manifest = repository.get_manifest(args.manifest_id)
    dataset = load_forecast_evaluation_dataset(
        Path(args.ohlcv),
        Path(args.metadata),
        required_bar_count=args.required_bars,
    )
    bars_by_symbol = {
        case.symbol.strip().upper(): case.bars
        for case in dataset.cases
        if case.symbol.strip().upper() in manifest.symbols
    }
    result = mature_forecast_sealed_predictions(
        repository,
        manifest.manifest_id,
        bars_by_symbol,
        observed_at=datetime.now(UTC),
    )
    reason_counts: dict[str, int] = {}
    for skip in result.skips:
        reason_counts[skip.reason] = reason_counts.get(skip.reason, 0) + 1
    print(f"manifest: {manifest.manifest_id}")
    print(f"pending checked: {result.pending_count}")
    print(f"outcomes inserted: {result.inserted_count}")
    print(f"outcome duplicates: {result.duplicate_count}")
    if reason_counts:
        print(
            "not matured: "
            + ", ".join(f"{reason}={count}" for reason, count in sorted(reason_counts.items()))
        )
    hard_failures = {
        "duplicate_bar_timestamp",
        "origin_bar_missing",
        "origin_close_revised",
        "prediction_recorded_after_target",
        "target_close_non_positive",
        "bar_timestamp_naive",
    }
    return 1 if hard_failures.intersection(reason_counts) else 0


def _status_or_export(args: argparse.Namespace) -> int:
    from backend.forecast.sealed_audit import (
        SealedForecastAuditRepository,
        summarize_forecast_sealed_audit,
        write_forecast_sealed_audit_artifacts,
    )

    repository = SealedForecastAuditRepository(Path(args.database))
    summary = summarize_forecast_sealed_audit(repository, args.manifest_id)
    print(f"manifest: {summary.manifest_id}")
    print(
        f"predictions={summary.prediction_count} matured={summary.matured_count} "
        f"pending={summary.pending_count}"
    )
    for row in summary.horizon_rows:
        print(
            f"{row.horizon_days}d: captured={row.captured_count} "
            f"matured={row.matured_count}/{row.required_count} "
            f"ready={str(row.sample_ready).lower()}"
        )
    if args.command == "export":
        paths = write_forecast_sealed_audit_artifacts(
            repository,
            args.manifest_id,
            Path(args.output),
        )
        for name, path in paths.items():
            print(f"{name}: {path}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    from backend.forecast.sealed_audit import SealedForecastAuditRepository

    result = SealedForecastAuditRepository(Path(args.database)).verify_integrity()
    print(f"database: {result.database_path}")
    print(f"sqlite integrity: {result.sqlite_integrity}")
    print(f"manifests: {result.manifest_count}")
    print(f"predictions: {result.prediction_count}")
    print(f"outcomes: {result.outcome_count}")
    print(f"foreign key violations: {result.foreign_key_violation_count}")
    return 0


def _backup(args: argparse.Namespace) -> int:
    from backend.forecast.sealed_audit import SealedForecastAuditRepository

    repository = SealedForecastAuditRepository(Path(args.database))
    target = repository.backup_to(Path(args.output))
    result = SealedForecastAuditRepository(target).verify_integrity()
    print(f"backup: {target}")
    print(
        f"verified: manifests={result.manifest_count} "
        f"predictions={result.prediction_count} outcomes={result.outcome_count}"
    )
    return 0


def _parse_horizons(value: str) -> list[int]:
    try:
        parsed = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError("--horizons must contain comma-separated integers") from exc
    if not parsed or any(item < 1 for item in parsed):
        raise ValueError("--horizons must contain positive integers")
    if len(parsed) != len(set(parsed)):
        raise ValueError("--horizons must not contain duplicates")
    return sorted(parsed)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return parsed


def _symbols_from_file(value: str | None) -> list[str]:
    if not value:
        return []
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"symbols file not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return []
    if rows[0] and rows[0][0].strip().lower() == "symbol":
        rows = rows[1:]
    return [row[0].strip() for row in rows if row and row[0].strip()]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
