from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import backend.interpretation.radar_overview_service as radar_overview_service_module
from backend.assistant import (
    AssistantGatewayEvidencePoint,
    AssistantGatewayRadarOverviewDeepDiveHint,
    AssistantGatewayRadarOverviewInterpretation,
    AssistantGatewayRadarOverviewSectorNote,
    AssistantGatewayRadarOverviewThemeNote,
    AssistantGatewayReferencedSection,
    AssistantGatewayResponse,
    MockAssistantGatewayClient,
)
from backend.core.config import RadarOverviewInterpretationConfig, Settings
from backend.interpretation import (
    RadarOverviewInterpretationGatewayAdapter,
    RadarOverviewInterpretationService,
    RadarOverviewInterpretationValidationError,
    build_radar_overview_interpretation_context,
    build_radar_overview_interpretation_from_settings,
    radar_overview_interpretation_from_gateway_response,
)
from backend.news import NewsDashboardSnapshot, NewsHeatmapCell, RadarCandidate, RadarCandidateMap
from backend.news.radar_market import RadarMarketSnapshot, RadarMarketTile

NOW = datetime(2026, 8, 10, 3, 0, tzinfo=UTC)


def _candidate(
    symbol: str,
    *,
    category: str,
    provenance: str = "direct_mention",
    watchlist_match: bool = False,
) -> RadarCandidate:
    return RadarCandidate(
        candidate_id=f"radar:{provenance}:{symbol}",
        symbol=symbol,
        display_name=f"Name {symbol}",
        provenance=provenance,  # type: ignore[arg-type]
        categories=[category],
        evidence_ids=[f"news:{symbol}"],
        freshness_status="latest",
        independent_source_count=2,
        watchlist_match=watchlist_match,
        directness=1.0 if provenance == "direct_mention" else 0.6,
        confirmation_priority=80 if provenance == "direct_mention" else 60,
        confirmation_gaps=["追加資料を確認してください。"],
        is_investigation_candidate=provenance != "macro_proxy",
    )


def _inputs(*, stale_market: bool = False):
    candidates = [
        _candidate("AAA", category="半導体・AI", watchlist_match=True),
        _candidate("BBB", category="半導体・AI", provenance="inferred_candidate"),
        _candidate("CCC", category="エネルギー"),
        _candidate("SPY", category="市場", provenance="macro_proxy"),
    ]
    news = NewsDashboardSnapshot(
        generated_at=NOW,
        fetched_at=NOW,
        freshness_status="latest",
        heatmap_cells=[
            NewsHeatmapCell(
                category="半導体・AI",
                region="日本",
                news_count=4,
                risk_count=1,
                positive_count=2,
                official_source_count=1,
                freshness_ratio=1.0,
                heat_score=8.0,
                dominant_material_type="theme",
            ),
            NewsHeatmapCell(
                category="エネルギー",
                region="米国",
                news_count=2,
                risk_count=0,
                positive_count=1,
                official_source_count=0,
                freshness_ratio=0.5,
                heat_score=4.0,
                dominant_material_type="macro",
            ),
        ],
    )
    candidate_map = RadarCandidateMap(generated_at=NOW, candidates=candidates)
    generated_at = NOW - timedelta(minutes=20) if stale_market else NOW
    market = RadarMarketSnapshot(
        generated_at=generated_at,
        provider="fixture",
        lookback_sessions=20,
        requested_count=3,
        tiles=[
            RadarMarketTile(
                symbol="AAA",
                display_name="Name AAA",
                category="半導体・AI",
                sector="technology",
                industry="semiconductors",
                news_categories=["半導体・AI"],
                change_pct=3.0,
                magnitude_pct=3.0,
                latest_close=103.0,
                as_of=NOW,
                provenance="direct_mention",
            ),
            RadarMarketTile(
                symbol="BBB",
                display_name="Name BBB",
                category="半導体・AI",
                sector="technology",
                industry="semiconductors",
                news_categories=["半導体・AI"],
                change_pct=-1.0,
                magnitude_pct=1.0,
                latest_close=99.0,
                as_of=NOW,
                provenance="inferred_candidate",
            ),
            RadarMarketTile(
                symbol="CCC",
                display_name="Name CCC",
                category="エネルギー",
                sector="energy",
                industry="energy",
                news_categories=["エネルギー"],
                change_pct=1.0,
                magnitude_pct=1.0,
                latest_close=101.0,
                as_of=NOW,
                provenance="direct_mention",
            ),
        ],
    )
    return news, candidate_map, market


def _context(*, stale_market: bool = False):
    return build_radar_overview_interpretation_context(
        *_inputs(stale_market=stale_market),
        now=NOW,
    )


def _point(text: str, evidence_id: str) -> AssistantGatewayEvidencePoint:
    return AssistantGatewayEvidencePoint(text=text, cited_evidence_ids=[evidence_id])


def _payload(context) -> AssistantGatewayRadarOverviewInterpretation:
    theme_id = context.allowed_theme_ids[0]
    candidate_id = context.deep_dive_candidate_ids[0]
    sector_notes = []
    if context.allowed_sector_ids:
        sector_notes = [
            AssistantGatewayRadarOverviewSectorNote(
                sector_id=context.allowed_sector_ids[0],
                reading=_point("候補集合内のセクター比較です。", "radar_sector_comparison"),
            )
        ]
    return AssistantGatewayRadarOverviewInterpretation(
        radar_context_id=context.radar_context_id,
        context_hash=context.context_hash,
        summary=_point("本文言及とテーマ推測を分けて確認します。", "radar_scope"),
        candidate_set_movement=_point(
            "取得済み候補集合の値動きとして確認します。", "radar_market_breadth"
        ),
        sector_notes=sector_notes,
        theme_notes=[
            AssistantGatewayRadarOverviewThemeNote(
                theme_id=theme_id,
                related_candidate_ids=context.theme_candidate_ids[theme_id],
                reading=_point("ニュースの量と鮮度を確認します。", theme_id),
            )
        ],
        deep_dive_hints=[
            AssistantGatewayRadarOverviewDeepDiveHint(
                candidate_id=candidate_id,
                reason=_point("根拠と確認不足を詳しく確認します。", candidate_id),
            )
        ],
        unknowns=[],
        next_checkpoints=[_point("候補詳細で根拠記事を確認します。", candidate_id)],
    )


def _response(context, payload=None) -> AssistantGatewayResponse:
    value = payload or _payload(context)
    points = [
        value.summary,
        *([value.candidate_set_movement] if value.candidate_set_movement else []),
        *[item.reading for item in value.sector_notes],
        *[item.reading for item in value.theme_notes],
        *[item.reason for item in value.deep_dive_hints],
        *value.unknowns,
        *value.next_checkpoints,
    ]
    ids = list(
        dict.fromkeys(evidence_id for point in points for evidence_id in point.cited_evidence_ids)
    )
    return AssistantGatewayResponse(
        answer=value.summary.text,
        radar_overview_interpretation=value,
        referenced_sections=[
            AssistantGatewayReferencedSection(
                section_id=item,
                title=item,
                source_kind="radar_overview",
            )
            for item in ids
        ],
        provider="fixture",
        model="fixture-model",
        profile="desktop_fast",
        elapsed_ms=1,
    )


def test_radar_overview_context_is_bounded_and_excludes_raw_fields():
    context = _context()

    assert len(context.bundle.sections) <= 8
    assert len(context.allowed_theme_ids) == 2
    assert len(context.deep_dive_candidate_ids) == 2
    assert context.market_state == "fresh"
    assert "radar:macro_proxy:SPY" not in context.deep_dive_candidate_ids
    serialized = context.bundle.model_dump_json()
    assert "source_url" not in serialized
    assert "raw_payload" not in serialized
    assert "Forecast" not in serialized


def test_radar_overview_context_drops_stale_market_direction():
    context = _context(stale_market=True)
    market = next(
        item for item in context.bundle.sections if item.section_id == "radar_market_breadth"
    )

    assert context.market_state == "stale"
    assert market.summary["direction_available"] == "no"
    assert not context.allowed_sector_ids
    assert "3.00%" not in context.bundle.model_dump_json()


def test_radar_overview_validation_accepts_exact_grounded_payload():
    context = _context()

    result = radar_overview_interpretation_from_gateway_response(
        _response(context),
        context=context,
        generated_at=NOW,
    )

    assert result.status == "live"
    assert result.context_hash == context.context_hash
    assert result.deep_dive_hints[0].candidate_id == context.deep_dive_candidate_ids[0]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("unknown_evidence", "unknown_evidence"),
        ("wrong_evidence_relation", "unknown_evidence"),
        ("wrong_context", "wrong_context"),
        ("wrong_candidate", "wrong_candidate"),
        ("wrong_theme", "wrong_theme"),
        ("wrong_sector", "wrong_sector"),
        ("duplicate_candidate", "duplicate_candidate"),
        ("wrong_symbol", "wrong_candidate"),
        ("unsupported_number", "unsupported_number"),
        ("unsupported_date", "unsupported_date"),
        ("investment_advice", "policy_violation"),
        ("whole_market_claim", "policy_violation"),
        ("unsafe_link", "policy_violation"),
    ],
)
def test_radar_overview_validation_rejects_unsafe_payload(mutation: str, reason: str):
    context = _context()
    payload = _payload(context)
    if mutation == "unknown_evidence":
        payload.summary.cited_evidence_ids = ["unknown"]
    elif mutation == "wrong_evidence_relation":
        payload.theme_notes[0].reading.cited_evidence_ids = ["radar_scope"]
    elif mutation == "wrong_context":
        payload.context_hash = "wrong"
    elif mutation == "wrong_candidate":
        payload.deep_dive_hints[0].candidate_id = "radar:direct_mention:UNKNOWN"
    elif mutation == "wrong_theme":
        payload.theme_notes[0].theme_id = "radar_theme:unknown"
    elif mutation == "wrong_sector":
        payload.sector_notes[0].sector_id = "radar_sector:unknown"
    elif mutation == "duplicate_candidate":
        payload.deep_dive_hints.append(payload.deep_dive_hints[0])
    elif mutation == "wrong_symbol":
        payload.summary.text = "ZZZZを確認します。"
    elif mutation == "unsupported_number":
        payload.summary.text = "取得済み候補は999.9%上昇しました。"
    elif mutation == "unsupported_date":
        payload.summary.text = "2025-01-01の材料を確認します。"
    elif mutation == "investment_advice":
        payload.summary.text = "買うべき候補です。"
    elif mutation == "whole_market_claim":
        payload.summary.text = "市場全体が上昇しています。"
    else:
        payload.summary.text = "[外部リンク](https://example.invalid)を確認します。"

    with pytest.raises(RadarOverviewInterpretationValidationError) as exc_info:
        radar_overview_interpretation_from_gateway_response(
            _response(context, payload),
            context=context,
            generated_at=NOW,
        )

    assert exc_info.value.reason == reason


def test_radar_overview_validation_preserves_deep_dive_candidate_order():
    context = _context()
    payload = _payload(context)
    second_candidate_id = context.deep_dive_candidate_ids[1]
    payload.deep_dive_hints.append(
        AssistantGatewayRadarOverviewDeepDiveHint(
            candidate_id=second_candidate_id,
            reason=_point("根拠と確認不足を詳しく確認します。", second_candidate_id),
        )
    )
    payload.deep_dive_hints.reverse()

    with pytest.raises(RadarOverviewInterpretationValidationError) as exc_info:
        radar_overview_interpretation_from_gateway_response(
            _response(context, payload),
            context=context,
            generated_at=NOW,
        )

    assert exc_info.value.reason == "wrong_candidate"


def test_radar_overview_validation_rejects_movement_for_stale_snapshot():
    context = _context(stale_market=True)
    payload = _payload(context)

    with pytest.raises(RadarOverviewInterpretationValidationError) as exc_info:
        radar_overview_interpretation_from_gateway_response(
            _response(context, payload),
            context=context,
            generated_at=NOW,
        )

    assert exc_info.value.reason == "policy_violation"


def test_radar_overview_disabled_path_does_not_create_gateway_client():
    context = _context()
    settings = Settings()

    result = build_radar_overview_interpretation_from_settings(
        context,
        user_id="default",
        settings=settings,
        now=NOW,
    )

    assert result.result.status == "disabled"
    assert result.result.is_fallback
    assert result.cache.status == "disabled"


def test_radar_overview_service_caches_only_valid_live_result(tmp_path):
    context = _context()
    client = MockAssistantGatewayClient(response=_response(context))
    adapter = RadarOverviewInterpretationGatewayAdapter(client)
    service = RadarOverviewInterpretationService(
        adapter,
        config=RadarOverviewInterpretationConfig(enabled=True),
        user_id="yuki",
        cache_file=tmp_path / "radar-overview.json",
    )

    first = service.interpret(context, now=NOW)
    second = service.interpret(context, now=NOW + timedelta(minutes=1))

    assert first.result.status == "live"
    assert first.cache.cache_hit is False
    assert second.cache.cache_hit is True
    assert len(client.requests) == 1


def test_radar_overview_default_user_never_uses_persistent_cache(tmp_path):
    context = _context()
    client = MockAssistantGatewayClient(response=_response(context))
    cache_file = tmp_path / "default-user-cache.json"
    service = RadarOverviewInterpretationService(
        RadarOverviewInterpretationGatewayAdapter(client),
        config=RadarOverviewInterpretationConfig(enabled=True),
        user_id="default",
        cache_file=cache_file,
    )

    first = service.interpret(context, now=NOW)
    second = service.interpret(context, now=NOW + timedelta(minutes=1))

    assert first.cache.status == "disabled"
    assert second.cache.status == "disabled"
    assert len(client.requests) == 2
    assert not cache_file.exists()


def test_radar_overview_cache_write_failure_is_visible(monkeypatch, tmp_path):
    context = _context()
    client = MockAssistantGatewayClient(response=_response(context))
    monkeypatch.setattr(
        radar_overview_service_module,
        "save_radar_overview_interpretation_cache_entry",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("read only")),
    )
    service = RadarOverviewInterpretationService(
        RadarOverviewInterpretationGatewayAdapter(client),
        config=RadarOverviewInterpretationConfig(enabled=True),
        user_id="yuki",
        cache_file=tmp_path / "radar-overview.json",
    )

    service_result = service.interpret(context, now=NOW)

    assert service_result.result.status == "live"
    assert service_result.cache.status == "invalid"
    assert service_result.cache.expires_at is None
    assert any("cacheへ保存できませんでした" in item for item in service_result.result.warnings)
