"""Idempotent run-once orchestration for Forecast sealed audit operations."""

from __future__ import annotations

import secrets
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from filelock import FileLock, Timeout
from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.forecast.advanced_registry import advanced_forecast_adapter_keys
from backend.forecast.dataset import ForecastDatasetLoadResult, load_forecast_evaluation_dataset
from backend.forecast.model_policy import AUDITED_HORIZON_MAX_DAYS
from backend.forecast.sealed_audit import (
    SEALED_AUDIT_HARD_MATURATION_REASONS,
    ForecastSealedAuditIntegrityResult,
    ForecastSealedAuditMaturationResult,
    ForecastSealedAuditSummary,
    ForecastSealedPrediction,
    SealedForecastAuditRepository,
    build_forecast_sealed_prediction,
    mature_forecast_sealed_predictions,
    summarize_forecast_sealed_audit,
    write_forecast_sealed_audit_artifacts,
)
from backend.forecast.service import (
    evaluate_advanced_forecast,
    summarize_advanced_forecast_evaluations,
)

FORECAST_SEALED_AUDIT_CYCLE_SCHEMA_VERSION = "forecast-sealed-audit-cycle-v1"


class ForecastSealedAuditCycleError(RuntimeError):
    """Raised when a run-once cycle must stop without pretending success."""


class ForecastSealedAuditCaptureFailure(StrictBaseModel):
    symbol: str = Field(min_length=1)
    horizon_days: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=1)


class ForecastSealedAuditCaptureResult(StrictBaseModel):
    manifest_id: str = Field(min_length=1)
    requested_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    inserted_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    existing_origin_skipped_count: int = Field(ge=0)
    failures: list[ForecastSealedAuditCaptureFailure] = Field(default_factory=list)


class ForecastSealedAuditCycleResult(StrictBaseModel):
    schema_version: str = FORECAST_SEALED_AUDIT_CYCLE_SCHEMA_VERSION
    run_id: str = Field(pattern=r"^fsar_[A-Za-z0-9_-]{8,96}$")
    manifest_id: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    status: Literal["completed"] = "completed"
    dataset_symbol_count: int = Field(ge=0)
    dataset_eligible_symbol_count: int = Field(ge=0)
    capture: ForecastSealedAuditCaptureResult
    maturation: ForecastSealedAuditMaturationResult
    integrity: ForecastSealedAuditIntegrityResult
    summary: ForecastSealedAuditSummary
    artifact_paths: dict[str, str]
    backup_path: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class ForecastSealedAuditCycleFailureResult(StrictBaseModel):
    schema_version: str = FORECAST_SEALED_AUDIT_CYCLE_SCHEMA_VERSION
    run_id: str = Field(pattern=r"^fsar_[A-Za-z0-9_-]{8,96}$")
    manifest_id: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    status: Literal["failed"] = "failed"
    stage: Literal["collection", "cycle"]
    reason_type: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)
    retry_safe: bool = True


def capture_forecast_sealed_predictions(
    repository: SealedForecastAuditRepository,
    manifest_id: str,
    dataset: ForecastDatasetLoadResult,
    *,
    source_revision: str,
    recorded_at: datetime,
) -> ForecastSealedAuditCaptureResult:
    """Compute every missing current prediction, then append the whole successful batch."""

    _require_aware(recorded_at, "recorded_at")
    manifest = repository.get_manifest(manifest_id)
    if source_revision.strip() != manifest.source_revision:
        raise ForecastSealedAuditCycleError("source revision differs from the frozen manifest")
    cases = {case.symbol.strip().upper(): case for case in dataset.cases}
    failures: list[ForecastSealedAuditCaptureFailure] = []
    for symbol in manifest.symbols:
        if symbol not in cases:
            coverage = next(
                (row for row in dataset.coverage if row.symbol.strip().upper() == symbol),
                None,
            )
            failures.append(
                ForecastSealedAuditCaptureFailure(
                    symbol=symbol,
                    reason=(
                        coverage.reason if coverage is not None else "eligible_daily_bars_missing"
                    ),
                )
            )
    requested_count = len(manifest.symbols) * len(manifest.horizons)
    if failures:
        return ForecastSealedAuditCaptureResult(
            manifest_id=manifest_id,
            requested_count=requested_count,
            candidate_count=0,
            inserted_count=0,
            duplicate_count=0,
            existing_origin_skipped_count=0,
            failures=failures,
        )

    existing = {
        (item.symbol, item.horizon_days, item.origin_at)
        for item in repository.list_predictions(manifest_id)
    }
    predictions: list[ForecastSealedPrediction] = []
    skipped_existing = 0
    for symbol in manifest.symbols:
        case = cases[symbol]
        origin_at = max(bar.ts for bar in case.bars)
        for horizon in manifest.horizons:
            if (symbol, horizon, origin_at) in existing:
                skipped_existing += 1
                continue
            adapter_names = (
                advanced_forecast_adapter_keys()
                if horizon <= AUDITED_HORIZON_MAX_DAYS
                else ("advanced_quantile",)
            )
            evaluations = []
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
                failures.append(
                    ForecastSealedAuditCaptureFailure(
                        symbol=symbol,
                        horizon_days=horizon,
                        reason="consensus_unavailable",
                    )
                )
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
                failures.append(
                    ForecastSealedAuditCaptureFailure(
                        symbol=symbol,
                        horizon_days=horizon,
                        reason=str(exc),
                    )
                )
    if failures:
        return ForecastSealedAuditCaptureResult(
            manifest_id=manifest_id,
            requested_count=requested_count,
            candidate_count=len(predictions),
            inserted_count=0,
            duplicate_count=0,
            existing_origin_skipped_count=skipped_existing,
            failures=failures,
        )
    write_result = repository.add_predictions(predictions)
    return ForecastSealedAuditCaptureResult(
        manifest_id=manifest_id,
        requested_count=requested_count,
        candidate_count=len(predictions),
        inserted_count=write_result.inserted_count,
        duplicate_count=write_result.duplicate_count,
        existing_origin_skipped_count=skipped_existing,
    )


def run_forecast_sealed_audit_cycle(
    repository: SealedForecastAuditRepository,
    *,
    manifest_id: str,
    source_revision: str,
    ohlcv_path: Path,
    metadata_path: Path,
    required_bar_count: int,
    output_dir: Path,
    backup_path: Path,
    observed_at: datetime | None = None,
    run_id: str | None = None,
) -> ForecastSealedAuditCycleResult:
    """Run verify, mature, capture, export, and backup as one replay-safe operation."""

    started_at = observed_at or datetime.now(UTC)
    _require_aware(started_at, "observed_at")
    resolved_run_id = run_id or create_forecast_sealed_audit_run_id(started_at)
    lock_path = repository.path.with_name(f"{repository.path.name}.cycle.lock")
    try:
        with FileLock(str(lock_path), timeout=0):
            return _run_forecast_sealed_audit_cycle_unlocked(
                repository,
                manifest_id=manifest_id,
                source_revision=source_revision,
                ohlcv_path=ohlcv_path,
                metadata_path=metadata_path,
                required_bar_count=required_bar_count,
                output_dir=output_dir,
                backup_path=backup_path,
                started_at=started_at,
                run_id=resolved_run_id,
            )
    except Timeout as exc:
        raise ForecastSealedAuditCycleError(
            "another sealed audit cycle is already running"
        ) from exc


def create_forecast_sealed_audit_run_id(started_at: datetime) -> str:
    _require_aware(started_at, "started_at")
    return f"fsar_{started_at.astimezone(UTC):%Y%m%dT%H%M%SZ}_{secrets.token_hex(4)}"


def write_forecast_sealed_audit_cycle_failure(
    output_dir: Path,
    *,
    run_id: str,
    manifest_id: str,
    source_revision: str,
    started_at: datetime,
    stage: Literal["collection", "cycle"],
    error: Exception,
) -> Path:
    """Write a bounded typed failure result for schedulers and diagnostics."""

    reason = " ".join(str(error).split())[:500] or type(error).__name__
    result = ForecastSealedAuditCycleFailureResult(
        run_id=run_id,
        manifest_id=manifest_id,
        source_revision=source_revision,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        stage=stage,
        reason_type=type(error).__name__,
        reason=reason,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "sealed_forecast_audit_cycle_failure.json"
    path.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _run_forecast_sealed_audit_cycle_unlocked(
    repository: SealedForecastAuditRepository,
    *,
    manifest_id: str,
    source_revision: str,
    ohlcv_path: Path,
    metadata_path: Path,
    required_bar_count: int,
    output_dir: Path,
    backup_path: Path,
    started_at: datetime,
    run_id: str,
) -> ForecastSealedAuditCycleResult:
    repository.verify_integrity()
    manifest = repository.get_manifest(manifest_id)
    if source_revision.strip() != manifest.source_revision:
        raise ForecastSealedAuditCycleError("source revision differs from the frozen manifest")
    dataset = load_forecast_evaluation_dataset(
        ohlcv_path,
        metadata_path,
        required_bar_count=required_bar_count,
    )
    eligible_symbols = {case.symbol.strip().upper() for case in dataset.cases}
    missing = sorted(set(manifest.symbols) - eligible_symbols)
    if missing:
        raise ForecastSealedAuditCycleError(
            "sealed cohort is not fully eligible: " + ",".join(missing)
        )

    bars_by_symbol = {
        case.symbol.strip().upper(): case.bars
        for case in dataset.cases
        if case.symbol.strip().upper() in manifest.symbols
    }
    maturation = mature_forecast_sealed_predictions(
        repository,
        manifest_id,
        bars_by_symbol,
        observed_at=started_at,
        atomic_on_hard_failure=True,
    )
    hard_reasons = sorted(
        {
            skip.reason
            for skip in maturation.skips
            if skip.reason in SEALED_AUDIT_HARD_MATURATION_REASONS
        }
    )
    if hard_reasons:
        raise ForecastSealedAuditCycleError("hard maturation failure: " + ",".join(hard_reasons))
    capture = capture_forecast_sealed_predictions(
        repository,
        manifest_id,
        dataset,
        source_revision=source_revision,
        recorded_at=started_at,
    )
    if capture.failures:
        reasons = sorted({failure.reason for failure in capture.failures})
        raise ForecastSealedAuditCycleError(
            "sealed capture failed before append: " + ",".join(reasons)
        )

    integrity = repository.verify_integrity()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = write_forecast_sealed_audit_artifacts(
        repository,
        manifest_id,
        output_dir,
    )
    repository.backup_to(backup_path)
    summary = summarize_forecast_sealed_audit(repository, manifest_id)
    warnings = _cycle_warnings(maturation, summary)
    result_path = output_dir / "sealed_forecast_audit_cycle.json"
    report_path = output_dir / "sealed_forecast_audit_cycle.md"
    paths = {name: str(path) for name, path in artifact_paths.items()}
    paths["cycle_result"] = str(result_path)
    paths["cycle_report"] = str(report_path)
    result = ForecastSealedAuditCycleResult(
        run_id=run_id,
        manifest_id=manifest_id,
        source_revision=manifest.source_revision,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        dataset_symbol_count=len(dataset.coverage),
        dataset_eligible_symbol_count=len(dataset.cases),
        capture=capture,
        maturation=maturation,
        integrity=integrity,
        summary=summary,
        artifact_paths=paths,
        backup_path=str(backup_path),
        warnings=warnings,
    )
    result_path.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path.write_text(
        _cycle_markdown(result),
        encoding="utf-8",
        newline="\n",
    )
    return result


def _cycle_warnings(
    maturation: ForecastSealedAuditMaturationResult,
    summary: ForecastSealedAuditSummary,
) -> list[str]:
    counts = Counter(skip.reason for skip in maturation.skips)
    warnings = [f"maturation:{reason}={count}" for reason, count in sorted(counts.items())]
    warnings.extend(summary.warnings)
    return warnings


def _cycle_markdown(result: ForecastSealedAuditCycleResult) -> str:
    lines = [
        "# Forecast封印監査 Run-once結果",
        "",
        f"- Run ID: `{result.run_id}`",
        f"- Manifest: `{result.manifest_id}`",
        f"- 状態: `{result.status}`",
        f"- 開始: `{result.started_at.isoformat()}`",
        f"- 完了: `{result.completed_at.isoformat()}`",
        f"- Dataset: {result.dataset_eligible_symbol_count}/{result.dataset_symbol_count} symbols eligible",
        f"- Prediction追加: {result.capture.inserted_count}",
        f"- 同一origin skip: {result.capture.existing_origin_skipped_count}",
        f"- Outcome追加: {result.maturation.inserted_count}",
        f"- DB: manifest {result.integrity.manifest_count} / prediction {result.integrity.prediction_count} / outcome {result.integrity.outcome_count}",
        f"- Backup: `{result.backup_path}`",
        "",
        "このrunの完了は監査データの保存成功を示し、runtime modelの自動採用を意味しません。",
    ]
    if result.warnings:
        lines.extend(["", "## 警告", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines) + "\n"


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
