import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from backend.llm_factor import (
    LLMMaterialRiskSignal,
    MaterialArchiveConflict,
    PointInTimeEventAnchor,
    archive_material_records,
    archive_material_risk_signals,
    build_material_risk_shadow_adjustment,
    load_material_archive,
    load_material_risk_signals,
    material_record_from_external_payload,
    material_records_from_news_snapshot,
    point_in_time_evidence_from_material_record,
    select_point_in_time_evidence,
    verify_material_archive,
    verify_material_risk_signal_store,
)
from backend.news.contracts import NewsDashboardSnapshot, NewsHeadlineCard
from backend.research.external_contracts import ExternalResearchSourcePayload


def test_news_archive_keeps_actual_first_seen_time_and_is_idempotent(tmp_path) -> None:
    published_at = datetime(2026, 7, 20, 1, tzinfo=UTC)
    archived_at = datetime(2026, 7, 20, 3, tzinfo=UTC)
    snapshot = _snapshot(published_at=published_at, fetched_at=archived_at)

    records = material_records_from_news_snapshot(snapshot)
    assert len(records) == 1
    assert records[0].symbols == ["7203.T"]
    assert records[0].available_at == published_at
    assert records[0].first_archived_at == archived_at

    path = tmp_path / "material.json"
    first = archive_material_records(records, path=path)
    second = archive_material_records(records, path=path)
    loaded = load_material_archive(path)

    assert first.inserted_count == 1
    assert second.updated_count == 1
    assert len(loaded.records) == 1
    assert loaded.records[0].observation_count == 2


def test_archived_today_cannot_be_used_at_an_older_decision_origin() -> None:
    published_at = datetime(2026, 7, 1, tzinfo=UTC)
    archived_at = datetime(2026, 7, 20, tzinfo=UTC)
    record = material_records_from_news_snapshot(
        _snapshot(published_at=published_at, fetched_at=archived_at)
    )[0]
    evidence = point_in_time_evidence_from_material_record(record, symbol="7203.T")
    event = PointInTimeEventAnchor(
        event_id="event-1",
        symbol="7203.T",
        occurred_at=datetime(2026, 7, 10, tzinfo=UTC),
        decision_at=datetime(2026, 7, 11, tzinfo=UTC),
        headline="決算発表",
        event_type="earnings_guidance",
    )

    selection = select_point_in_time_evidence(event, [evidence])

    assert selection.candidates == []
    assert selection.audit.archive_late_count == 1


def test_date_only_ir_payload_uses_fetch_time_as_causal_availability() -> None:
    fetched_at = datetime(2026, 7, 20, 8, 30, tzinfo=UTC)
    payload = ExternalResearchSourcePayload(
        symbol="7203.T",
        title="決算短信",
        content="通期業績と配当方針を公表しました。",
        source_type="tdnet",
        source_url="https://example.test/tdnet/1",
        provider="tdnet",
        published_at=date(2026, 7, 20),
        fetched_at=fetched_at,
    )

    record = material_record_from_external_payload(payload)

    assert record.published_at == datetime(2026, 7, 20, tzinfo=UTC)
    assert record.available_at == fetched_at
    assert record.first_archived_at == fetched_at
    assert record.is_official_source is True


def test_llm_material_risk_can_only_widen_range_and_cap_confidence() -> None:
    archived_at = datetime(2026, 7, 20, 3, tzinfo=UTC)
    record = material_records_from_news_snapshot(
        _snapshot(
            published_at=archived_at - timedelta(hours=1),
            fetched_at=archived_at,
        )
    )[0]
    decision_at = archived_at + timedelta(hours=1)
    signal = LLMMaterialRiskSignal(
        signal_id="risk-1",
        symbol="7203.T",
        horizon_days=20,
        decision_at=decision_at,
        generated_at=decision_at,
        provider="gateway",
        model_name="test-model",
        prompt_version="material-risk-v1",
        adverse_risk_score=Decimal("85"),
        event_relevance_score=Decimal("90"),
        evidence_confidence_score=Decimal("75"),
        uncertainty_score=Decimal("40"),
        predicted_impact_label=-1,
        cited_record_ids=[record.record_id],
        rationale="業績下方修正の可能性を確認する必要があります。",
    )

    adjustment = build_material_risk_shadow_adjustment(signal, [record])

    assert adjustment.applied is True
    assert adjustment.confidence_cap == "low"
    assert adjustment.range_multiplier == Decimal("1.25")
    assert adjustment.center_return_adjustment == 0


def test_corrupt_archive_is_visible_and_not_silently_overwritten(tmp_path) -> None:
    path = tmp_path / "material.json"
    path.write_text("{bad json", encoding="utf-8")
    loaded = load_material_archive(path)

    assert loaded.records == []
    assert loaded.warnings
    with pytest.raises(ValueError, match="could not be loaded"):
        archive_material_records([], path=path)


def test_archive_rejects_same_identity_with_changed_content(tmp_path) -> None:
    archived_at = datetime(2026, 7, 20, 3, tzinfo=UTC)
    record = material_records_from_news_snapshot(
        _snapshot(
            published_at=archived_at - timedelta(hours=1),
            fetched_at=archived_at,
        )
    )[0]
    path = tmp_path / "material.json"
    archive_material_records([record], path=path)
    changed_summary = "後から異なる内容へ書き換えられました。"
    changed_hash = hashlib.sha256(
        "\n".join([record.title, changed_summary, record.source_url]).encode("utf-8")
    ).hexdigest()
    changed = record.model_copy(update={"summary": changed_summary, "content_sha256": changed_hash})

    with pytest.raises(MaterialArchiveConflict, match="immutable material changed"):
        archive_material_records([changed], path=path)
    assert verify_material_archive(path).record_count == 1


def test_material_risk_signal_store_hashes_and_freezes_decision_key(tmp_path) -> None:
    signal = _risk_signal()
    path = tmp_path / "signals.json"

    first = archive_material_risk_signals([signal], path=path)
    second = archive_material_risk_signals([signal], path=path)

    assert first.inserted_count == 1
    assert second.duplicate_count == 1
    assert load_material_risk_signals(path).signals == [signal]
    assert verify_material_risk_signal_store(path).signal_count == 1
    payload = json.loads(path.read_text("utf-8"))
    assert len(payload["signals"][0]["content_hash"]) == 64
    changed = signal.model_copy(update={"adverse_risk_score": Decimal("99")})
    with pytest.raises(MaterialArchiveConflict, match="immutable material risk signal"):
        archive_material_risk_signals([changed], path=path)


def _snapshot(*, published_at: datetime, fetched_at: datetime) -> NewsDashboardSnapshot:
    card = NewsHeadlineCard(
        title="トヨタが通期業績予想を更新",
        summary="会社発表と市場反応を確認します。",
        url="https://example.test/news/7203",
        source_name="Example News",
        source_type="news",
        published_at=published_at,
        fetched_at=fetched_at,
        category="決算・業績修正",
        material_type="earnings",
        related_symbols=["7203.T"],
    )
    return NewsDashboardSnapshot(
        generated_at=fetched_at,
        fetched_at=fetched_at,
        stream_headlines=[card],
    )


def _risk_signal() -> LLMMaterialRiskSignal:
    decision_at = datetime(2026, 7, 20, 4, tzinfo=UTC)
    return LLMMaterialRiskSignal(
        signal_id="risk-store-1",
        symbol="7203.T",
        horizon_days=20,
        decision_at=decision_at,
        generated_at=decision_at,
        provider="gateway",
        model_name="test-model",
        prompt_version="material-risk-v1",
        adverse_risk_score=Decimal("85"),
        event_relevance_score=Decimal("90"),
        evidence_confidence_score=Decimal("75"),
        uncertainty_score=Decimal("40"),
        predicted_impact_label=-1,
        cited_record_ids=["record-1"],
        rationale="業績下方修正の可能性を確認する必要があります。",
    )
