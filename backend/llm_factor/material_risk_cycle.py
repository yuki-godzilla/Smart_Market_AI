"""Point-in-time LLM material-risk signal collection for sealed Forecast audits."""

from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

from filelock import FileLock, Timeout
from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.forecast.sealed_audit import SealedForecastAuditRepository
from backend.llm_factor.context_builder import (
    build_llm_factor_generation_request,
    llm_factor_context_hash,
)
from backend.llm_factor.contracts import EvidenceSource, LLMFactorSourceType
from backend.llm_factor.gateway_adapter import LLMFactorGatewayClient, LLMFactorGatewayError
from backend.llm_factor.live_contracts import LLMFactorGenerationResponse
from backend.llm_factor.material_archive import (
    LLMMaterialRiskSignal,
    MaterialArchiveIntegrityResult,
    MaterialRiskSignalIntegrityResult,
    MaterialRiskSignalWriteResult,
    PointInTimeMaterialRecord,
    archive_material_risk_signals,
    backup_material_archive,
    backup_material_risk_signal_store,
    load_material_archive,
    load_material_risk_signals,
    verify_material_archive,
    verify_material_risk_signal_store,
)
from backend.llm_factor.validation import (
    LLMFactorLiveValidationError,
    llm_factor_result_from_gateway_response,
)

MATERIAL_RISK_CYCLE_SCHEMA_VERSION = "llm-material-risk-cycle-v1"
MATERIAL_RISK_MAPPING_VERSION = "llm-factor-response-risk-map-v1"

MaterialRiskCycleItemStatus = Literal[
    "generated",
    "existing",
    "insufficient_point_in_time_material",
    "gateway_error",
    "validation_error",
    "no_citations",
]
MaterialRiskCycleStatus = Literal[
    "completed",
    "completed_no_eligible",
    "completed_with_failures",
]


class MaterialRiskCycleError(RuntimeError):
    """Raised when archive or persistence integrity prevents a safe cycle."""


class MaterialRiskCycleItem(StrictBaseModel):
    symbol: str = Field(min_length=1)
    decision_at: datetime
    horizons: list[int] = Field(min_length=1)
    material_count: int = Field(ge=0)
    signal_count: int = Field(ge=0)
    status: MaterialRiskCycleItemStatus
    reason: str | None = Field(default=None, max_length=300)
    retryable: bool = False


class MaterialRiskCycleResult(StrictBaseModel):
    schema_version: str = MATERIAL_RISK_CYCLE_SCHEMA_VERSION
    run_id: str = Field(pattern=r"^lmrr_[A-Za-z0-9_-]{8,96}$")
    manifest_id: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    status: MaterialRiskCycleStatus
    archive_integrity: MaterialArchiveIntegrityResult
    signal_integrity: MaterialRiskSignalIntegrityResult
    signal_write: MaterialRiskSignalWriteResult
    forecast_group_count: int = Field(ge=0)
    generated_signal_count: int = Field(ge=0)
    existing_signal_count: int = Field(ge=0)
    item_results: list[MaterialRiskCycleItem]
    artifact_paths: dict[str, str]


class MaterialRiskCycleFailureResult(StrictBaseModel):
    schema_version: str = MATERIAL_RISK_CYCLE_SCHEMA_VERSION
    run_id: str = Field(pattern=r"^lmrr_[A-Za-z0-9_-]{8,96}$")
    manifest_id: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    status: Literal["failed"] = "failed"
    stage: Literal["preflight", "cycle"]
    reason_type: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)
    retryable: bool = True


def run_material_risk_cycle(
    repository: SealedForecastAuditRepository,
    gateway_client: LLMFactorGatewayClient,
    *,
    manifest_id: str,
    archive_path: Path,
    signal_path: Path,
    output_dir: Path,
    started_at: datetime | None = None,
    max_evidence_items: int = 8,
    prompt_version: str = "llm_factor_live_mvp.v1",
    run_id: str | None = None,
) -> MaterialRiskCycleResult:
    """Generate immutable shadow signals only from evidence available at each origin."""

    observed_at = started_at or datetime.now(UTC)
    _require_aware(observed_at, "started_at")
    if max_evidence_items < 1 or max_evidence_items > 20:
        raise ValueError("max_evidence_items must be between 1 and 20")
    if not archive_path.is_file():
        raise MaterialRiskCycleError("point-in-time material archive does not exist")
    resolved_run_id = run_id or create_material_risk_cycle_run_id(observed_at)
    lock_path = signal_path.with_suffix(signal_path.suffix + ".cycle.lock")
    try:
        with FileLock(str(lock_path), timeout=0):
            return _run_material_risk_cycle_unlocked(
                repository,
                gateway_client,
                manifest_id=manifest_id,
                archive_path=archive_path,
                signal_path=signal_path,
                output_dir=output_dir,
                observed_at=observed_at,
                max_evidence_items=max_evidence_items,
                prompt_version=prompt_version,
                run_id=resolved_run_id,
            )
    except Timeout as exc:
        raise MaterialRiskCycleError("another material risk cycle is already running") from exc


def create_material_risk_cycle_run_id(started_at: datetime) -> str:
    _require_aware(started_at, "started_at")
    return f"lmrr_{started_at.astimezone(UTC):%Y%m%dT%H%M%SZ}_{secrets.token_hex(4)}"


def write_material_risk_cycle_failure(
    output_dir: Path,
    *,
    run_id: str,
    manifest_id: str,
    started_at: datetime,
    stage: Literal["preflight", "cycle"],
    error: Exception,
) -> Path:
    reason = " ".join(str(error).split())[:500] or type(error).__name__
    result = MaterialRiskCycleFailureResult(
        run_id=run_id,
        manifest_id=manifest_id,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        stage=stage,
        reason_type=type(error).__name__,
        reason=reason,
        retryable=isinstance(error, (MaterialRiskCycleError, LLMFactorGatewayError)),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "llm_material_risk_cycle_failure.json"
    path.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def _run_material_risk_cycle_unlocked(
    repository: SealedForecastAuditRepository,
    gateway_client: LLMFactorGatewayClient,
    *,
    manifest_id: str,
    archive_path: Path,
    signal_path: Path,
    output_dir: Path,
    observed_at: datetime,
    max_evidence_items: int,
    prompt_version: str,
    run_id: str,
) -> MaterialRiskCycleResult:
    repository.verify_integrity()
    repository.get_manifest(manifest_id)
    archive = load_material_archive(archive_path)
    if archive.warnings:
        raise MaterialRiskCycleError(archive.warnings[0])
    loaded_signals = load_material_risk_signals(signal_path)
    if loaded_signals.warnings:
        raise MaterialRiskCycleError(loaded_signals.warnings[0])
    existing_keys = {
        (signal.symbol, signal.horizon_days, signal.decision_at)
        for signal in loaded_signals.signals
    }
    grouped = _prediction_groups(repository, manifest_id)
    generated: list[LLMMaterialRiskSignal] = []
    items: list[MaterialRiskCycleItem] = []
    for (symbol, decision_at), horizons in grouped:
        missing_horizons = [
            horizon for horizon in horizons if (symbol, horizon, decision_at) not in existing_keys
        ]
        if not missing_horizons:
            items.append(
                MaterialRiskCycleItem(
                    symbol=symbol,
                    decision_at=decision_at,
                    horizons=horizons,
                    material_count=0,
                    signal_count=0,
                    status="existing",
                )
            )
            continue
        records = _eligible_records(
            archive.records,
            symbol=symbol,
            decision_at=decision_at,
            limit=max_evidence_items,
        )
        if not records:
            items.append(
                MaterialRiskCycleItem(
                    symbol=symbol,
                    decision_at=decision_at,
                    horizons=missing_horizons,
                    material_count=0,
                    signal_count=0,
                    status="insufficient_point_in_time_material",
                    reason="decision時点以前に保存された銘柄一致材料がない",
                )
            )
            continue
        sources = [_evidence_source(record) for record in records]
        request = build_llm_factor_generation_request(
            ticker=symbol,
            as_of=decision_at.date(),
            evidence_sources=sources,
            forecast_summary={"horizons": ",".join(str(value) for value in missing_horizons)},
            prompt_version=prompt_version,
            max_evidence_items=max_evidence_items,
        )
        context_hash = llm_factor_context_hash(request)
        record_by_evidence_id = {
            context.evidence_id: record
            for context, record in zip(request.context.evidence, records, strict=True)
        }
        try:
            response = gateway_client.generate(request)
            validated = llm_factor_result_from_gateway_response(
                response,
                request=request,
                context_hash=context_hash,
                fallback_sources=sources,
            )
            cited_ids = _cited_record_ids(response, record_by_evidence_id)
            if not cited_ids:
                items.append(
                    MaterialRiskCycleItem(
                        symbol=symbol,
                        decision_at=decision_at,
                        horizons=missing_horizons,
                        material_count=len(records),
                        signal_count=0,
                        status="no_citations",
                        reason="Gateway応答に有効なcitationがない",
                    )
                )
                continue
            signals = [
                _signal_from_response(
                    response,
                    symbol=symbol,
                    horizon_days=horizon,
                    decision_at=decision_at,
                    cited_record_ids=cited_ids,
                    context_hash=context_hash,
                    evidence_confidence=validated.llm_confidence_score,
                )
                for horizon in missing_horizons
            ]
        except LLMFactorGatewayError as exc:
            items.append(
                MaterialRiskCycleItem(
                    symbol=symbol,
                    decision_at=decision_at,
                    horizons=missing_horizons,
                    material_count=len(records),
                    signal_count=0,
                    status="gateway_error",
                    reason=(exc.provider_error_type or exc.gateway_error_type)[:300],
                    retryable=exc.retryable,
                )
            )
            continue
        except (LLMFactorLiveValidationError, ValueError) as exc:
            items.append(
                MaterialRiskCycleItem(
                    symbol=symbol,
                    decision_at=decision_at,
                    horizons=missing_horizons,
                    material_count=len(records),
                    signal_count=0,
                    status="validation_error",
                    reason=" ".join(str(exc).split())[:300] or type(exc).__name__,
                )
            )
            continue
        generated.extend(signals)
        items.append(
            MaterialRiskCycleItem(
                symbol=symbol,
                decision_at=decision_at,
                horizons=missing_horizons,
                material_count=len(records),
                signal_count=len(signals),
                status="generated",
            )
        )

    write_result = archive_material_risk_signals(generated, path=signal_path)
    archive_integrity = verify_material_archive(archive_path)
    signal_integrity = verify_material_risk_signal_store(signal_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_backup = backup_material_archive(
        archive_path,
        output_dir / "point_in_time_material_archive.json",
    )
    signal_backup = backup_material_risk_signal_store(
        signal_path,
        output_dir / "llm_material_risk_signals.json",
    )
    status = _cycle_status(items, generated)
    result_path = output_dir / "llm_material_risk_cycle.json"
    report_path = output_dir / "llm_material_risk_cycle.md"
    result = MaterialRiskCycleResult(
        run_id=run_id,
        manifest_id=manifest_id,
        started_at=observed_at,
        completed_at=datetime.now(UTC),
        status=status,
        archive_integrity=archive_integrity,
        signal_integrity=signal_integrity,
        signal_write=write_result,
        forecast_group_count=len(grouped),
        generated_signal_count=len(generated),
        existing_signal_count=sum(
            len(item.horizons) for item in items if item.status == "existing"
        ),
        item_results=items,
        artifact_paths={
            "archive_backup": str(archive_backup),
            "signal_backup": str(signal_backup),
            "result": str(result_path),
            "report": str(report_path),
        },
    )
    result_path.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path.write_text(_result_markdown(result), encoding="utf-8", newline="\n")
    return result


def _prediction_groups(
    repository: SealedForecastAuditRepository,
    manifest_id: str,
) -> list[tuple[tuple[str, datetime], list[int]]]:
    grouped: dict[tuple[str, datetime], set[int]] = defaultdict(set)
    for prediction in repository.list_predictions(manifest_id):
        grouped[(prediction.symbol, prediction.origin_at)].add(prediction.horizon_days)
    return [
        (key, sorted(horizons))
        for key, horizons in sorted(grouped.items(), key=lambda item: item[0])
    ]


def _eligible_records(
    records: list[PointInTimeMaterialRecord],
    *,
    symbol: str,
    decision_at: datetime,
    limit: int,
) -> list[PointInTimeMaterialRecord]:
    eligible = [
        record
        for record in records
        if symbol in record.symbols
        and record.published_at <= decision_at
        and record.available_at <= decision_at
        and record.first_archived_at <= decision_at
    ]
    return sorted(
        eligible,
        key=lambda record: (
            not record.is_official_source,
            -record.first_archived_at.timestamp(),
            record.record_id,
        ),
    )[:limit]


def _evidence_source(record: PointInTimeMaterialRecord) -> EvidenceSource:
    allowed = {
        "research_summary",
        "news",
        "tdnet",
        "edinet",
        "company_ir",
        "provider_profile",
        "symbol_db",
        "local_reference",
        "other",
    }
    source_type = record.source_type if record.source_type in allowed else "other"
    return EvidenceSource(
        title=record.title,
        source_type=cast(LLMFactorSourceType, source_type),
        source_url=record.source_url,
        source_date=record.published_at.date(),
        fetched_at=record.first_archived_at,
        provider=record.source_family,
        summary=record.summary,
        reliability_score=Decimal("85") if record.is_official_source else Decimal("60"),
    )


def _cited_record_ids(
    response: LLMFactorGenerationResponse,
    record_by_evidence_id: dict[str, PointInTimeMaterialRecord],
) -> list[str]:
    evidence_ids: set[str] = set()
    for factor in response.factors:
        evidence_ids.update(factor.evidence_ids)
    for risk in response.risks:
        evidence_ids.update(risk.evidence_ids)
    for opportunity in response.opportunities:
        evidence_ids.update(opportunity.evidence_ids)
    evidence_ids.update(item.evidence_id for item in response.evidence)
    return sorted(
        {
            record_by_evidence_id[evidence_id].record_id
            for evidence_id in evidence_ids
            if evidence_id in record_by_evidence_id
        }
    )


def _signal_from_response(
    response: LLMFactorGenerationResponse,
    *,
    symbol: str,
    horizon_days: int,
    decision_at: datetime,
    cited_record_ids: list[str],
    context_hash: str,
    evidence_confidence: Decimal,
) -> LLMMaterialRiskSignal:
    adverse = _unit_score(max([item.severity for item in response.risks] or [0.0]))
    relevance = _unit_score(
        max(
            [item.severity for item in response.risks]
            + [item.strength for item in response.factors]
            + [item.impact for item in response.opportunities]
            + [0.0]
        )
    )
    predicted_impact: Literal[-1, 0, 1]
    if response.sentiment_label == "negative":
        predicted_impact = -1
    elif response.sentiment_label == "positive":
        predicted_impact = 1
    else:
        predicted_impact = 0
    identity = "|".join(
        [
            symbol,
            str(horizon_days),
            decision_at.isoformat(),
            response.prompt_version,
            response.model,
            MATERIAL_RISK_MAPPING_VERSION,
            context_hash,
        ]
    )
    return LLMMaterialRiskSignal(
        signal_id="lmrs_" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        symbol=symbol,
        horizon_days=horizon_days,
        decision_at=decision_at,
        generated_at=response.generated_at,
        provider=response.provider,
        model_name=response.model,
        prompt_version=response.prompt_version,
        mapping_version=MATERIAL_RISK_MAPPING_VERSION,
        source_hash=context_hash,
        adverse_risk_score=adverse,
        event_relevance_score=relevance,
        evidence_confidence_score=evidence_confidence,
        uncertainty_score=max(Decimal("0"), Decimal("100") - evidence_confidence),
        predicted_impact_label=predicted_impact,
        cited_record_ids=cited_record_ids,
        rationale=_bounded_text(response.overall_summary, 800),
    )


def _unit_score(value: float) -> Decimal:
    return (Decimal(str(value)) * Decimal("100")).quantize(Decimal("0.01"))


def _cycle_status(
    items: list[MaterialRiskCycleItem],
    generated: list[LLMMaterialRiskSignal],
) -> MaterialRiskCycleStatus:
    if any(item.status in {"gateway_error", "validation_error", "no_citations"} for item in items):
        return "completed_with_failures"
    if not generated and not any(item.status == "existing" for item in items):
        return "completed_no_eligible"
    return "completed"


def _result_markdown(result: MaterialRiskCycleResult) -> str:
    lines = [
        "# LLM材料リスク Run-once結果",
        "",
        f"- Run ID: `{result.run_id}`",
        f"- Forecast manifest: `{result.manifest_id}`",
        f"- 状態: `{result.status}`",
        f"- Forecast origin group: {result.forecast_group_count}",
        f"- 新規signal: {result.generated_signal_count}",
        f"- 既存signal: {result.existing_signal_count}",
        f"- Archive record: {result.archive_integrity.record_count}",
        f"- Signal total: {result.signal_integrity.signal_count}",
        "",
        "signalはconfidence上限とrange拡張のshadow評価専用で、価格中心値、方向値、Ranking、Scoreを変更しません。",
        "",
        "| Symbol | Decision | Horizons | Materials | Signals | Status |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| {item.symbol} | {item.decision_at.isoformat()} | "
        f"{','.join(str(value) for value in item.horizons)} | {item.material_count} | "
        f"{item.signal_count} | {item.status} |"
        for item in result.item_results
    )
    return "\n".join(lines) + "\n"


def _bounded_text(value: str, max_chars: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        return "根拠付き材料リスクを確認"
    return normalized[:max_chars]


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
