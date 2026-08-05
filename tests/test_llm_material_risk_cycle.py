from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from backend.core.data_contracts import Bar, Symbol
from backend.forecast.sealed_audit import (
    SealedForecastAuditRepository,
    build_forecast_sealed_prediction,
    create_forecast_sealed_audit_manifest,
)
from backend.forecast.service import (
    FORECAST_ROLE_CONFIDENCE_POLICY_VERSION,
    AdvancedForecastConsensus,
)
from backend.llm_factor.gateway_adapter import LLMFactorGatewayError
from backend.llm_factor.live_contracts import LLMFactorGenerationResponse
from backend.llm_factor.material_archive import (
    archive_material_records,
    load_material_risk_signals,
    material_records_from_news_snapshot,
)
from backend.llm_factor.material_risk_cycle import run_material_risk_cycle
from backend.news.contracts import NewsDashboardSnapshot, NewsHeadlineCard


class _Gateway:
    def __init__(self, generated_at: datetime, *, fail: bool = False) -> None:
        self.generated_at = generated_at
        self.fail = fail
        self.call_count = 0

    def generate(self, request):
        self.call_count += 1
        if self.fail:
            raise LLMFactorGatewayError(
                "temporary provider error",
                gateway_error_type="provider_error",
                provider_error_type="provider_timeout",
                retryable=True,
            )
        evidence = request.context.evidence[0]
        return LLMFactorGenerationResponse.model_validate(
            {
                "symbol": request.symbol,
                "overall_summary": "下方修正リスクを一次情報とともに確認します。",
                "sentiment_label": "negative",
                "confidence": 0.75,
                "factors": [],
                "risks": [
                    {
                        "title": "業績下方修正",
                        "summary": "会社開示を確認します。",
                        "severity": 0.85,
                        "evidence_ids": [evidence.evidence_id],
                    }
                ],
                "opportunities": [],
                "evidence": [],
                "prompt_version": request.prompt_version,
                "provider": "fixture-gateway",
                "model": "fixture-model",
                "profile": "desktop_analysis",
                "generated_at": self.generated_at,
                "elapsed_ms": 10,
                "gateway_status": "ok",
                "request_id": request.request_id,
            }
        )


def test_material_risk_cycle_generates_immutable_signals_and_replays(tmp_path: Path) -> None:
    repository, manifest_id, decision_at = _sealed_prediction(tmp_path)
    archive_path = _archive(tmp_path, archived_at=decision_at - timedelta(hours=1))
    signal_path = tmp_path / "signals.json"
    gateway = _Gateway(decision_at + timedelta(hours=2))

    first = run_material_risk_cycle(
        repository,
        gateway,
        manifest_id=manifest_id,
        archive_path=archive_path,
        signal_path=signal_path,
        output_dir=tmp_path / "first",
        started_at=decision_at + timedelta(hours=3),
    )
    second = run_material_risk_cycle(
        repository,
        gateway,
        manifest_id=manifest_id,
        archive_path=archive_path,
        signal_path=signal_path,
        output_dir=tmp_path / "second",
        started_at=decision_at + timedelta(hours=4),
    )

    assert first.status == "completed"
    assert first.generated_signal_count == 1
    signal = load_material_risk_signals(signal_path).signals[0]
    assert signal.adverse_risk_score == Decimal("85.00")
    assert signal.predicted_impact_label == -1
    assert signal.source_hash is not None
    assert second.generated_signal_count == 0
    assert second.existing_signal_count == 1
    assert gateway.call_count == 1
    assert (tmp_path / "second" / "llm_material_risk_signals.json").is_file()


def test_material_risk_cycle_never_uses_late_archived_evidence(tmp_path: Path) -> None:
    repository, manifest_id, decision_at = _sealed_prediction(tmp_path)
    archive_path = _archive(tmp_path, archived_at=decision_at + timedelta(hours=1))
    gateway = _Gateway(decision_at + timedelta(hours=2))

    result = run_material_risk_cycle(
        repository,
        gateway,
        manifest_id=manifest_id,
        archive_path=archive_path,
        signal_path=tmp_path / "signals.json",
        output_dir=tmp_path / "output",
        started_at=decision_at + timedelta(hours=3),
    )

    assert result.status == "completed_no_eligible"
    assert result.generated_signal_count == 0
    assert gateway.call_count == 0


def test_material_risk_cycle_records_retryable_gateway_failure(tmp_path: Path) -> None:
    repository, manifest_id, decision_at = _sealed_prediction(tmp_path)
    archive_path = _archive(tmp_path, archived_at=decision_at - timedelta(hours=1))
    gateway = _Gateway(decision_at + timedelta(hours=2), fail=True)

    result = run_material_risk_cycle(
        repository,
        gateway,
        manifest_id=manifest_id,
        archive_path=archive_path,
        signal_path=tmp_path / "signals.json",
        output_dir=tmp_path / "output",
        started_at=decision_at + timedelta(hours=3),
    )

    assert result.status == "completed_with_failures"
    assert result.generated_signal_count == 0
    assert result.item_results[0].status == "gateway_error"
    assert result.item_results[0].retryable is True


def _sealed_prediction(tmp_path: Path) -> tuple[SealedForecastAuditRepository, str, datetime]:
    decision_at = datetime(2026, 7, 20, 12, tzinfo=UTC)
    bars = _bars(decision_at)
    manifest = create_forecast_sealed_audit_manifest(
        symbols=["7203.T"],
        horizons=[20],
        created_at=decision_at + timedelta(hours=1),
        accept_origins_at_or_after=decision_at - timedelta(days=1),
        cohort="new_calendar",
        source_revision="frozen-revision",
        manifest_id="fsa_material_risk_cycle_001",
    )
    repository = SealedForecastAuditRepository(tmp_path / "sealed.sqlite")
    repository.add_manifest(manifest)
    repository.add_predictions(
        [
            build_forecast_sealed_prediction(
                manifest,
                _consensus(),
                bars,
                recorded_at=decision_at + timedelta(hours=1),
                market="JP",
                asset_type="stock",
                regime="sideways",
            )
        ]
    )
    return repository, manifest.manifest_id, decision_at


def _archive(tmp_path: Path, *, archived_at: datetime) -> Path:
    published_at = archived_at - timedelta(hours=1)
    card = NewsHeadlineCard(
        title="トヨタが通期業績予想を更新",
        summary="会社発表と市場反応を確認します。",
        url="https://example.test/news/7203",
        source_name="Example News",
        source_type="news",
        published_at=published_at,
        fetched_at=archived_at,
        category="決算・業績修正",
        material_type="earnings",
        related_symbols=["7203.T"],
    )
    snapshot = NewsDashboardSnapshot(
        generated_at=archived_at,
        fetched_at=archived_at,
        stream_headlines=[card],
    )
    path = tmp_path / "archive.json"
    archive_material_records(material_records_from_news_snapshot(snapshot), path=path)
    return path


def _consensus() -> AdvancedForecastConsensus:
    return AdvancedForecastConsensus(
        symbol="7203.T",
        horizon_days=20,
        model_count=1,
        available_model_count=1,
        center_model_count=1,
        consensus_predicted_return=Decimal("0.05"),
        direction_predicted_return=Decimal("0.04"),
        consensus_forecast_close=Decimal("105"),
        median_predicted_return=Decimal("0.05"),
        min_predicted_return=Decimal("0.05"),
        max_predicted_return=Decimal("0.05"),
        predicted_return_range=Decimal("0"),
        center_predicted_return_range=Decimal("0"),
        direction_predicted_return_range=Decimal("0"),
        predicted_return_lower=Decimal("-0.10"),
        predicted_return_upper=Decimal("0.20"),
        forecast_close_lower=Decimal("90"),
        forecast_close_upper=Decimal("120"),
        agreement="medium",
        confidence="medium",
        center_confidence="medium",
        direction_confidence="medium",
        confidence_policy_version=FORECAST_ROLE_CONFIDENCE_POLICY_VERSION,
        direction_agreement_score=Decimal("70"),
        weighted_direction_score=Decimal("0.70"),
        mean_direction_accuracy=Decimal("0.60"),
        mean_rmse=Decimal("0.10"),
        selection_policy_version="horizon_validation_router_v1",
        horizon_band="short",
        audit_status="interpolated",
        selection_mode="quantile_anchor",
        center_adapter_names=["advanced_quantile"],
        direction_adapter_names=["advanced_quantile"],
        selected_adapter_names=["advanced_quantile"],
        model_weights={"advanced_quantile": Decimal("1")},
    )


def _bars(decision_at: datetime) -> list[Bar]:
    symbol = Symbol(raw="7203.T", exchange="TSE", code="7203", currency="JPY")
    return [
        Bar(
            symbol=symbol,
            ts=decision_at - timedelta(days=5 - index),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=Decimal("1000"),
            interval="1d",
            provider="fixture",
        )
        for index in range(6)
    ]
