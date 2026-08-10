from __future__ import annotations

from datetime import UTC, date, datetime

from backend.assistant import (
    AssistantGatewayEvidencePoint,
    AssistantGatewayRankingCandidateNote,
    AssistantGatewayRankingInterpretation,
    AssistantGatewayReferencedSection,
    AssistantGatewayResponse,
    MockAssistantGatewayClient,
)
from backend.core.config import RankingInterpretationConfig, Settings
from backend.interpretation import (
    RankingCandidateEvidence,
    RankingInterpretationGatewayAdapter,
    RankingInterpretationInput,
    RankingInterpretationService,
    RankingSectorEvidence,
    build_ranking_interpretation_context,
    build_ranking_interpretation_from_settings,
)


def test_ranking_context_is_stable_and_bounded() -> None:
    context = _context()
    same = _context()

    assert context.context_hash == same.context_hash
    assert context.ranking_context_id == same.ranking_context_id
    assert context.allowed_evidence_ids == [
        "ranking_scope",
        "ranking_metrics",
        "ranking_sectors",
        "ranking_candidate:7203.T",
        "ranking_candidate:6758.T",
    ]
    assert len(context.bundle.sections) == 5
    serialized = context.bundle.model_dump_json()
    assert "provider_raw" not in serialized
    assert "user_note" not in serialized


def test_ranking_service_accepts_grounded_payload_and_caches_live_result(tmp_path) -> None:
    context = _context()
    payload = _payload(context.ranking_context_id)
    client = MockAssistantGatewayClient(response=_response(payload))
    service = RankingInterpretationService(
        RankingInterpretationGatewayAdapter(client),
        config=RankingInterpretationConfig(enabled=True),
        cache_dir=tmp_path,
    )

    first = service.interpret(context, now=datetime(2026, 8, 10, 10, 0, tzinfo=UTC))
    second = service.interpret(context, now=datetime(2026, 8, 10, 10, 1, tzinfo=UTC))

    assert first.result.status == "live"
    assert first.cache.status == "miss"
    assert second.cache.status == "hit"
    assert second.cache.cache_hit is True
    assert len(client.requests) == 1
    assert client.requests[0].task_type == "ranking_interpretation"
    assert client.requests[0].response_schema == "ranking_interpretation.v1"
    assert [note.candidate_id for note in first.result.candidate_notes] == context.candidate_ids
    assert (tmp_path / "ranking_interpretation_results.json").exists()
    assert not (tmp_path / "ranking_interpretation_results.json.tmp").exists()


def test_ranking_service_rejects_unknown_number_for_whole_payload(tmp_path) -> None:
    context = _context()
    payload = _payload(context.ranking_context_id, summary="総合スコアは999.9です。")
    service = _service(payload, cache_dir=tmp_path)

    result = service.interpret(context, now=datetime(2026, 8, 10, 10, 0, tzinfo=UTC))

    assert result.result.status == "validation_error"
    assert result.result.fallback_reason == "unsupported_number"
    assert result.result.is_fallback is True
    assert result.cache.cache_hit is False


def test_ranking_service_rejects_recommendation_and_does_not_cache_it(tmp_path) -> None:
    context = _context()
    payload = _payload(context.ranking_context_id, summary="この候補は買うべきです。")
    service = _service(payload, cache_dir=tmp_path)

    result = service.interpret(context, now=datetime(2026, 8, 10, 10, 0, tzinfo=UTC))

    assert result.result.status == "validation_error"
    assert result.result.fallback_reason == "policy_violation"
    assert not (tmp_path / "ranking_interpretation_results.json").exists()


def test_ranking_service_rejects_wrong_context_and_duplicate_candidate(tmp_path) -> None:
    context = _context()
    wrong = _service(_payload("ranking:wrong"), cache_dir=tmp_path / "wrong").interpret(context)
    duplicate_payload = _payload(context.ranking_context_id)
    duplicate_payload.candidate_notes[1].candidate_id = duplicate_payload.candidate_notes[
        0
    ].candidate_id
    duplicate = _service(duplicate_payload, cache_dir=tmp_path / "duplicate").interpret(context)

    assert wrong.result.fallback_reason == "wrong_context"
    assert duplicate.result.fallback_reason == "duplicate_candidate"


def test_ranking_disabled_setting_never_constructs_a_live_result(tmp_path) -> None:
    result = build_ranking_interpretation_from_settings(
        _context(),
        settings=Settings(),
        cache_dir=tmp_path,
        now=datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
    )

    assert result.result.status == "disabled"
    assert result.result.provider == "deterministic"
    assert result.cache.status == "disabled"


def _input() -> RankingInterpretationInput:
    candidates = [
        RankingCandidateEvidence(
            candidate_id="ranking_candidate:7203.T",
            rank=1,
            symbol="7203.T",
            company_name="Toyota Motor",
            primary_metric_id="metric:total-score",
            primary_metric_label="総合スコア",
            primary_metric_value="82.0",
            total_score="82.0",
            screening_score="78",
            downside_warning="34",
            data_quality="90",
            reason="総合スコアとデータ品質を確認します。",
        ),
        RankingCandidateEvidence(
            candidate_id="ranking_candidate:6758.T",
            rank=2,
            symbol="6758.T",
            company_name="Sony Group",
            primary_metric_id="metric:total-score",
            primary_metric_label="総合スコア",
            primary_metric_value="79.0",
            total_score="79.0",
            screening_score="76",
            downside_warning="41",
            data_quality="88",
            reason="総合スコアと下降警戒を確認します。",
        ),
    ]
    return RankingInterpretationInput(
        result_id="result-2026-08-10",
        as_of=date(2026, 8, 10),
        ranking_policy="総合比較",
        weight_preset="バランス",
        region="日本",
        product_type="個別株",
        candidate_count=10,
        candidates=candidates,
        sector_groups=[
            RankingSectorEvidence(
                sector_id="sector:consumer",
                sector_label="一般消費財",
                candidate_count=2,
                best_rank=1,
                representative_candidate_id="ranking_candidate:7203.T",
                primary_metric_average="80.5",
                comparison_state="comparable",
            )
        ],
    )


def _context():
    return build_ranking_interpretation_context(
        _input(),
        now=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
    )


def _point(text: str, *evidence_ids: str) -> AssistantGatewayEvidencePoint:
    return AssistantGatewayEvidencePoint(text=text, cited_evidence_ids=list(evidence_ids))


def _payload(
    context_id: str,
    *,
    summary: str = "上位候補は主要指標と注意点を分けて確認します。",
) -> AssistantGatewayRankingInterpretation:
    return AssistantGatewayRankingInterpretation(
        ranking_context_id=context_id,
        summary=_point(summary, "ranking_scope"),
        common_strengths=[_point("主要指標の内訳を比較できます。", "ranking_metrics")],
        common_cautions=[
            _point("データ品質は投資魅力度と分けて確認します。", "ranking_candidate:7203.T")
        ],
        metric_notes=[_point("総合スコアの構成要素を確認します。", "ranking_metrics")],
        sector_notes=[_point("今回の候補集合内のセクター傾向です。", "ranking_sectors")],
        candidate_notes=[
            AssistantGatewayRankingCandidateNote(
                candidate_id="ranking_candidate:7203.T",
                reading=_point("表示中の強みを確認します。", "ranking_candidate:7203.T"),
                caution=_point("下降警戒も確認します。", "ranking_candidate:7203.T"),
                next_check=_point("最新の根拠資料を確認します。", "ranking_candidate:7203.T"),
            ),
            AssistantGatewayRankingCandidateNote(
                candidate_id="ranking_candidate:6758.T",
                reading=_point("主要指標の違いを確認します。", "ranking_candidate:6758.T"),
                caution=None,
                next_check=_point("データ更新時刻を確認します。", "ranking_candidate:6758.T"),
            ),
        ],
        next_checkpoints=[_point("候補ごとの根拠を確認します。", "ranking_scope")],
    )


def _response(payload: AssistantGatewayRankingInterpretation) -> AssistantGatewayResponse:
    points = [
        payload.summary,
        *payload.common_strengths,
        *payload.common_cautions,
        *payload.metric_notes,
        *payload.sector_notes,
        *payload.next_checkpoints,
        *(
            point
            for note in payload.candidate_notes
            for point in [
                note.reading,
                *([note.caution] if note.caution is not None else []),
                note.next_check,
            ]
        ),
    ]
    evidence_ids = list(
        dict.fromkeys(evidence_id for point in points for evidence_id in point.cited_evidence_ids)
    )
    return AssistantGatewayResponse(
        answer=payload.summary.text,
        referenced_sections=[
            AssistantGatewayReferencedSection(
                section_id=evidence_id,
                title=evidence_id,
                source_kind="ranking_evidence",
            )
            for evidence_id in evidence_ids
        ],
        ranking_interpretation=payload,
        provider="fake",
        model="qwen3:8b",
        profile="desktop_fast",
    )


def _service(
    payload: AssistantGatewayRankingInterpretation,
    *,
    cache_dir,
) -> RankingInterpretationService:
    client = MockAssistantGatewayClient(response=_response(payload))
    return RankingInterpretationService(
        RankingInterpretationGatewayAdapter(client),
        config=RankingInterpretationConfig(enabled=True),
        cache_dir=cache_dir,
    )
