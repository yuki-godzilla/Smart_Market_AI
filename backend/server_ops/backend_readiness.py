"""Cross-boundary readiness audit for the backend-to-frontend sprint gate."""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from backend.core.config import Settings
from backend.core.data_contracts import StrictBaseModel
from backend.forecast.sealed_audit import (
    SealedForecastAuditRepository,
    summarize_forecast_sealed_audit,
)
from backend.llm_factor.material_archive import (
    load_material_risk_signals,
    verify_material_archive,
    verify_material_risk_signal_store,
)
from backend.marketdata.provider_factory import create_market_data_provider_adapter

BACKEND_READINESS_SCHEMA_VERSION = "backend-readiness-v1"
REQUIRED_BACKEND_API_ROUTES = frozenset(
    {
        ("GET", "/health"),
        ("POST", "/risk/pre-trade-check"),
        ("POST", "/portfolio/rebalance-check"),
        ("POST", "/screening/score"),
        ("POST", "/forecast/evaluate"),
        ("POST", "/scoring/investment-score"),
    }
)

BackendReadinessCheckStatus = Literal["pass", "pending", "fail"]
BackendReadinessStatus = Literal["ready", "ready_with_pending_evidence", "not_ready"]


class BackendReadinessCheck(StrictBaseModel):
    check_id: str = Field(pattern=r"^[a-z0-9_.-]+$")
    area: str = Field(min_length=1)
    status: BackendReadinessCheckStatus
    summary: str = Field(min_length=1, max_length=300)
    details: dict[str, object] = Field(default_factory=dict)


class BackendReadinessReport(StrictBaseModel):
    schema_version: str = BACKEND_READINESS_SCHEMA_VERSION
    generated_at: datetime
    status: BackendReadinessStatus
    frontend_sprint_ready: bool
    checks: list[BackendReadinessCheck] = Field(min_length=1)
    blocker_ids: list[str] = Field(default_factory=list)
    pending_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_report_state(self) -> Self:
        _require_aware(self.generated_at)
        expected_blockers = [check.check_id for check in self.checks if check.status == "fail"]
        expected_pending = [check.check_id for check in self.checks if check.status == "pending"]
        if self.blocker_ids != expected_blockers:
            raise ValueError("blocker_ids must match failed checks")
        if self.pending_ids != expected_pending:
            raise ValueError("pending_ids must match pending checks")
        if self.frontend_sprint_ready == bool(expected_blockers):
            raise ValueError("frontend_sprint_ready must be false exactly when blockers exist")
        expected_status: BackendReadinessStatus
        if expected_blockers:
            expected_status = "not_ready"
        elif expected_pending:
            expected_status = "ready_with_pending_evidence"
        else:
            expected_status = "ready"
        if self.status != expected_status:
            raise ValueError("status does not match readiness checks")
        return self


def audit_backend_readiness(
    settings: Settings,
    *,
    api_routes: set[tuple[str, str]],
    sealed_audit_database: Path,
    sealed_audit_manifest_id: str | None,
    material_archive_path: Path,
    material_risk_signal_path: Path,
    generated_at: datetime | None = None,
) -> BackendReadinessReport:
    """Audit code/runtime contracts without making network calls or changing runtime values."""

    observed_at = generated_at or datetime.now(UTC)
    _require_aware(observed_at)
    checks = [
        _api_routes_check(api_routes),
        _marketdata_provider_check(settings),
        _marketdata_deadline_check(settings),
        *_sealed_audit_checks(sealed_audit_database, sealed_audit_manifest_id),
        *_material_checks(material_archive_path, material_risk_signal_path),
    ]
    blockers = [check.check_id for check in checks if check.status == "fail"]
    pending = [check.check_id for check in checks if check.status == "pending"]
    status: BackendReadinessStatus
    if blockers:
        status = "not_ready"
    elif pending:
        status = "ready_with_pending_evidence"
    else:
        status = "ready"
    return BackendReadinessReport(
        generated_at=observed_at,
        status=status,
        frontend_sprint_ready=not blockers,
        checks=checks,
        blocker_ids=blockers,
        pending_ids=pending,
    )


def write_backend_readiness_outputs(
    report: BackendReadinessReport,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "backend_readiness.json"
    markdown_path = output_dir / "backend_readiness.md"
    _atomic_write(json_path, report.model_dump_json(indent=2) + "\n")
    _atomic_write(markdown_path, _readiness_markdown(report))
    return {"json": json_path, "markdown": markdown_path}


def _api_routes_check(api_routes: set[tuple[str, str]]) -> BackendReadinessCheck:
    missing = sorted(REQUIRED_BACKEND_API_ROUTES - api_routes)
    return BackendReadinessCheck(
        check_id="api.required_routes",
        area="API",
        status="fail" if missing else "pass",
        summary=(
            "必須backend API routeが不足しています。"
            if missing
            else "必須backend API routeを確認しました。"
        ),
        details={
            "required_count": len(REQUIRED_BACKEND_API_ROUTES),
            "missing": [f"{method} {path}" for method, path in missing],
        },
    )


def _marketdata_provider_check(settings: Settings) -> BackendReadinessCheck:
    try:
        health = create_market_data_provider_adapter(settings.dataaccess).healthcheck()
    except Exception as exc:  # noqa: BLE001 - convert configured-provider failures to a gate.
        return BackendReadinessCheck(
            check_id="marketdata.provider",
            area="MarketData",
            status="fail",
            summary="設定されたMarketData Providerを初期化できません。",
            details={"provider": settings.dataaccess.provider, "error_type": type(exc).__name__},
        )
    status = str(health.get("status", "unknown"))
    failed = status not in {"ok", "available"}
    return BackendReadinessCheck(
        check_id="marketdata.provider",
        area="MarketData",
        status="fail" if failed else "pass",
        summary=(
            "MarketData Providerが利用できません。"
            if failed
            else "MarketData Provider contractを確認しました。"
        ),
        details={"provider": settings.dataaccess.provider, "health_status": status},
    )


def _marketdata_deadline_check(settings: Settings) -> BackendReadinessCheck:
    timeout = settings.dataaccess.timeouts_ms
    valid = timeout.operation >= timeout.read
    return BackendReadinessCheck(
        check_id="marketdata.operation_deadline",
        area="MarketData",
        status="pass" if valid else "fail",
        summary=(
            "MarketData全体deadlineを確認しました。"
            if valid
            else "MarketData全体deadlineがrequest read timeoutより短いです。"
        ),
        details={
            "connect_ms": timeout.connect,
            "read_ms": timeout.read,
            "operation_ms": timeout.operation,
        },
    )


def _sealed_audit_checks(database: Path, manifest_id: str | None) -> list[BackendReadinessCheck]:
    if not database.is_file():
        return [
            BackendReadinessCheck(
                check_id="forecast.sealed_audit",
                area="Forecast",
                status="pending",
                summary="sealed Forecast監査DBはまだ作成されていません。",
                details={"database": str(database)},
            )
        ]
    if not manifest_id:
        return [
            BackendReadinessCheck(
                check_id="forecast.sealed_audit",
                area="Forecast",
                status="pending",
                summary="監査するsealed Forecast manifestが指定されていません。",
                details={"database": str(database)},
            )
        ]
    try:
        repository = SealedForecastAuditRepository(database)
        integrity = repository.verify_integrity()
        summary = summarize_forecast_sealed_audit(repository, manifest_id)
    except Exception as exc:  # noqa: BLE001 - readiness must retain a typed blocker.
        return [
            BackendReadinessCheck(
                check_id="forecast.sealed_audit",
                area="Forecast",
                status="fail",
                summary="sealed Forecast監査の完全性を確認できません。",
                details={
                    "database": str(database),
                    "manifest_id": manifest_id,
                    "error_type": type(exc).__name__,
                },
            )
        ]
    integrity_check = BackendReadinessCheck(
        check_id="forecast.sealed_audit",
        area="Forecast",
        status="pass",
        summary="sealed Forecast監査DB・manifest・hashを確認しました。",
        details={
            "manifest_id": manifest_id,
            "manifest_count": integrity.manifest_count,
            "prediction_count": summary.prediction_count,
            "matured_count": summary.matured_count,
            "pending_count": summary.pending_count,
        },
    )
    sample_ready = all(row.sample_ready for row in summary.horizon_rows)
    maturity_check = BackendReadinessCheck(
        check_id="forecast.matured_evidence",
        area="Forecast",
        status="pass" if sample_ready else "pending",
        summary=(
            "全horizonが成熟case gateへ到達しました。"
            if sample_ready
            else "将来targetの成熟caseを継続収集中です。"
        ),
        details={
            "horizons": [
                {
                    "horizon_days": row.horizon_days,
                    "matured_count": row.matured_count,
                    "required_count": row.required_count,
                    "sample_ready": row.sample_ready,
                }
                for row in summary.horizon_rows
            ]
        },
    )
    return [integrity_check, maturity_check]


def _material_checks(archive_path: Path, signal_path: Path) -> list[BackendReadinessCheck]:
    checks: list[BackendReadinessCheck] = []
    if not archive_path.is_file():
        checks.append(
            BackendReadinessCheck(
                check_id="llm_material.archive",
                area="LLM material",
                status="pending",
                summary="point-in-time材料archiveはまだ作成されていません。",
                details={"archive": str(archive_path)},
            )
        )
    else:
        try:
            archive_integrity = verify_material_archive(archive_path)
        except Exception as exc:  # noqa: BLE001 - readiness must retain a typed blocker.
            checks.append(
                BackendReadinessCheck(
                    check_id="llm_material.archive",
                    area="LLM material",
                    status="fail",
                    summary="point-in-time材料archiveの完全性を確認できません。",
                    details={"archive": str(archive_path), "error_type": type(exc).__name__},
                )
            )
        else:
            checks.append(
                BackendReadinessCheck(
                    check_id="llm_material.archive",
                    area="LLM material",
                    status="pass",
                    summary="point-in-time材料archiveのhashを確認しました。",
                    details={"record_count": archive_integrity.record_count},
                )
            )
    if not signal_path.is_file():
        checks.append(
            BackendReadinessCheck(
                check_id="llm_material.signals",
                area="LLM material",
                status="pending",
                summary="LLM材料risk signal storeはまだ作成されていません。",
                details={"signals": str(signal_path)},
            )
        )
        return checks
    try:
        signal_integrity = verify_material_risk_signal_store(signal_path)
        loaded = load_material_risk_signals(signal_path)
        if loaded.warnings:
            raise ValueError(loaded.warnings[0])
    except Exception as exc:  # noqa: BLE001 - readiness must retain a typed blocker.
        checks.append(
            BackendReadinessCheck(
                check_id="llm_material.signals",
                area="LLM material",
                status="fail",
                summary="LLM材料risk signal storeの完全性を確認できません。",
                details={"signals": str(signal_path), "error_type": type(exc).__name__},
            )
        )
    else:
        checks.append(
            BackendReadinessCheck(
                check_id="llm_material.signals",
                area="LLM material",
                status="pass" if loaded.signals else "pending",
                summary=(
                    "LLM材料risk signalのhashを確認しました。"
                    if loaded.signals
                    else "因果条件を満たすLLM材料risk signalを継続収集中です。"
                ),
                details={"signal_count": signal_integrity.signal_count},
            )
        )
    return checks


def _readiness_markdown(report: BackendReadinessReport) -> str:
    lines = [
        "# Backend Readiness",
        "",
        f"- 状態: `{report.status}`",
        f"- Frontend usability sprintへ移行可能: `{str(report.frontend_sprint_ready).lower()}`",
        f"- Blocker: {len(report.blocker_ids)}",
        f"- 成熟・運用待ち: {len(report.pending_ids)}",
        "",
        "| Area | Check | Status | Summary |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {check.area} | `{check.check_id}` | {check.status} | {check.summary} |"
        for check in report.checks
    )
    lines.extend(
        [
            "",
            "`pending`はコード欠落ではなく、将来target・新規材料・運用artifactの蓄積待ちを表します。",
            "`fail`が1件でもある場合だけFrontend usability sprintのblockerです。",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
