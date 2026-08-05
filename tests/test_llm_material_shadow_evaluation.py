from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.forecast.evaluation import ForecastValidationPoint
from backend.llm_factor import (
    LLMMaterialRiskSignal,
    evaluate_material_risk_shadow,
    material_records_from_news_snapshot,
    write_material_risk_shadow_outputs,
)
from backend.news.contracts import NewsDashboardSnapshot, NewsHeadlineCard


def test_shadow_evaluation_requires_mature_case_volume() -> None:
    record = _record()
    point = _point(0)
    report = evaluate_material_risk_shadow([point], [_signal(point, record.record_id)], [record])

    assert report.applied_case_count == 1
    assert report.adoption_status == "insufficient_evidence"
    assert report.center_return_changed is False
    assert report.direction_return_changed is False


def test_shadow_evaluation_uses_interval_score_not_coverage_alone(tmp_path) -> None:
    record = _record()
    points = [_point(index) for index in range(100)]
    signals = [_signal(point, record.record_id) for point in points]

    report = evaluate_material_risk_shadow(points, signals, [record])
    overall = next(row for row in report.metrics if row.group_type == "overall")

    assert report.adoption_status == "confidence_range_candidate"
    assert overall.baseline_coverage == Decimal("0.0000")
    assert overall.adjusted_coverage == Decimal("1.0000")
    assert overall.interval_score_improvement > Decimal("0.01")
    assert all(case.baseline_center == Decimal("0") for case in report.cases)

    paths = write_material_risk_shadow_outputs(report, tmp_path)
    assert set(paths) == {"cases", "metrics", "report"}
    assert "center_return_changed: false" in paths["report"].read_text(encoding="utf-8")


def _record():
    archived_at = datetime(2025, 1, 1, tzinfo=UTC)
    snapshot = NewsDashboardSnapshot(
        generated_at=archived_at,
        fetched_at=archived_at,
        stream_headlines=[
            NewsHeadlineCard(
                title="業績リスクを公表",
                summary="業績見通しの不確実性が高まりました。",
                url="https://example.test/material/1",
                source_name="Example News",
                source_type="news",
                published_at=archived_at - timedelta(hours=1),
                fetched_at=archived_at,
                category="決算",
                material_type="earnings",
                related_symbols=["AAA"],
            )
        ],
    )
    return material_records_from_news_snapshot(snapshot)[0]


def _point(index: int) -> ForecastValidationPoint:
    origin_at = datetime(2025, 2, 1, tzinfo=UTC) + timedelta(days=index)
    return ForecastValidationPoint(
        symbol="AAA",
        market="US",
        asset_type="stock",
        regime="sideways",
        model_name="forecast_consensus",
        horizon_days=20,
        origin_at=origin_at,
        target_at=origin_at + timedelta(days=20),
        predicted_return=Decimal("0"),
        direction_predicted_return=Decimal("0.01"),
        predicted_return_lower=Decimal("-0.10"),
        predicted_return_upper=Decimal("0.10"),
        confidence="medium",
        actual_return=Decimal("0.12"),
    )


def _signal(point: ForecastValidationPoint, record_id: str) -> LLMMaterialRiskSignal:
    return LLMMaterialRiskSignal(
        signal_id=f"signal-{point.origin_at.date().isoformat()}",
        symbol=point.symbol,
        horizon_days=point.horizon_days,
        decision_at=point.origin_at,
        generated_at=point.origin_at,
        provider="gateway",
        model_name="test-model",
        prompt_version="material-risk-v1",
        adverse_risk_score=Decimal("85"),
        event_relevance_score=Decimal("90"),
        evidence_confidence_score=Decimal("80"),
        uncertainty_score=Decimal("70"),
        predicted_impact_label=-1,
        cited_record_ids=[record_id],
        rationale="不確実性の上昇を確認しました。",
    )
