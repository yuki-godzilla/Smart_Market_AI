from __future__ import annotations

from datetime import UTC, datetime

from backend.news import (
    NewsHeadlineCard,
    NewsSymbolMatch,
    build_news_dashboard_snapshot,
    build_radar_candidate_map,
    filter_radar_candidates,
)


def _snapshot(*cards: NewsHeadlineCard):
    return build_news_dashboard_snapshot(
        list(cards),
        generated_at=datetime(2026, 7, 13, 9, 0, tzinfo=UTC),
    )


def _card(
    *,
    title: str,
    source_name: str,
    published_at: datetime,
    material_type: str = "theme",
    related_symbols: list[str] | None = None,
    inferred_symbols: list[str] | None = None,
    macro_proxy_symbols: list[str] | None = None,
    symbol_matches: list[NewsSymbolMatch] | None = None,
) -> NewsHeadlineCard:
    return NewsHeadlineCard(
        title=title,
        source_type="news",
        source_name=source_name,
        url=f"https://example.test/{title}",
        category="半導体・AI",
        region="日本",
        material_type=material_type,
        published_at=published_at,
        fetched_at=published_at,
        freshness_status="latest",
        related_symbols=related_symbols or [],
        inferred_symbols=inferred_symbols or [],
        macro_proxy_symbols=macro_proxy_symbols or [],
        symbol_matches=symbol_matches or [],
    )


def test_radar_candidate_map_keeps_direct_inferred_and_macro_provenance_separate():
    snapshot = _snapshot(
        _card(
            title="トヨタの設備投資",
            source_name="Official IR",
            published_at=datetime(2026, 7, 13, 8, 30, tzinfo=UTC),
            material_type="earnings",
            related_symbols=["7203.T"],
            inferred_symbols=["NVDA"],
            macro_proxy_symbols=["TLT"],
            symbol_matches=[
                NewsSymbolMatch(
                    symbol="7203.T",
                    name="Toyota Motor",
                    kind="direct_mention",
                    confidence=0.95,
                )
            ],
        ),
        _card(
            title="トヨタの追加開示",
            source_name="Market News",
            published_at=datetime(2026, 7, 13, 8, 45, tzinfo=UTC),
            related_symbols=["7203.T"],
        ),
    )

    candidate_map = build_radar_candidate_map(
        snapshot,
        watchlist_symbols=["7203.T"],
        symbol_metadata_by_symbol={
            "7203.T": {
                "name": "Toyota Motor",
                "market": "jp",
                "asset_type": "stock",
                "data_freshness_status": "fresh",
            },
            "NVDA": {"market": "us", "asset_type": "stock"},
        },
    )
    candidates = {(item.symbol, item.provenance): item for item in candidate_map.candidates}

    direct = candidates[("7203.T", "direct_mention")]
    inferred = candidates[("NVDA", "inferred_candidate")]
    macro = candidates[("TLT", "macro_proxy")]

    assert direct.display_name == "Toyota Motor"
    assert direct.watchlist_match is True
    assert direct.symbol_data_status == "available"
    assert direct.independent_source_count == 2
    assert len(direct.evidence_ids) == 2
    assert direct.confirmation_priority > inferred.confirmation_priority
    assert [reason.kind for reason in direct.confirmation_priority_reasons] == [
        "freshness",
        "evidence_breadth",
        "material_type",
        "watchlist_match",
    ]
    assert sum(reason.points for reason in direct.confirmation_priority_reasons) == (
        direct.confirmation_priority
    )
    assert direct.confirmation_priority_reasons[0].detail == "latest"
    assert direct.confirmation_priority_reasons[1].detail == "2"
    assert direct.confirmation_priority_reasons[2].detail == "earnings"
    assert inferred.symbol_data_status == "partial"
    assert macro.is_investigation_candidate is False
    assert macro.directness == 0.1
    assert any("代理指標" in gap for gap in macro.confirmation_gaps)
    assert all(item.evidence_ids and item.evidence for item in candidate_map.candidates)


def test_radar_candidate_map_is_deterministic_and_hides_rejected_or_symbol_free_news():
    direct = _card(
        title="NVIDIAの決算",
        source_name="News A",
        published_at=datetime(2026, 7, 13, 8, 0, tzinfo=UTC),
        related_symbols=["NVDA"],
        symbol_matches=[
            NewsSymbolMatch(symbol="NVDA", kind="ticker_match", confidence=0.98),
            NewsSymbolMatch(symbol="NOPE", kind="rejected", confidence=0.0),
        ],
    )
    symbol_free = _card(
        title="市場全体の雑感",
        source_name="News B",
        published_at=datetime(2026, 7, 13, 7, 0, tzinfo=UTC),
    )
    symbol_free = symbol_free.model_copy(update={"related_symbols": [], "inferred_symbols": []})

    first = build_radar_candidate_map(_snapshot(direct, symbol_free))
    second = build_radar_candidate_map(_snapshot(symbol_free, direct))

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert [(item.symbol, item.provenance) for item in first.candidates] == [
        ("NVDA", "direct_mention")
    ]


def test_radar_candidate_material_taxonomy_does_not_imply_headline_direction():
    """A query category must never turn a negative headline into a positive signal."""

    snapshot = _snapshot(
        _card(
            title="Ａｎｄ Ｄｏ、前期経常を一転65％減益に下方修正",
            source_name="Market News",
            published_at=datetime(2026, 7, 13, 8, 30, tzinfo=UTC),
            material_type="earnings",
            related_symbols=["3457.T"],
        )
    )

    candidate_map = build_radar_candidate_map(snapshot)

    assert len(candidate_map.candidates) == 1
    candidate = candidate_map.candidates[0]
    assert candidate.evidence[0].material_type == "earnings"
    assert candidate.material_tone == "unknown"


def test_radar_candidate_filters_are_display_only_and_keep_map_order():
    snapshot = _snapshot(
        _card(
            title="直接銘柄",
            source_name="News A",
            published_at=datetime(2026, 7, 13, 8, 0, tzinfo=UTC),
            related_symbols=["7203.T"],
        ),
        _card(
            title="推測候補",
            source_name="News B",
            published_at=datetime(2026, 7, 13, 7, 0, tzinfo=UTC),
            inferred_symbols=["NVDA"],
        ),
    )
    candidate_map = build_radar_candidate_map(
        snapshot,
        watchlist_symbols=["NVDA"],
        symbol_metadata_by_symbol={
            "7203.T": {"market": "jp", "asset_type": "stock"},
            "NVDA": {"market": "us", "asset_type": "stock"},
        },
    )

    direct_only = filter_radar_candidates(
        candidate_map,
        provenances=["direct_mention"],
    )
    watchlist_only = filter_radar_candidates(candidate_map, watchlist_only=True)

    assert [(item.symbol, item.provenance) for item in direct_only] == [
        ("7203.T", "direct_mention")
    ]
    assert [(item.symbol, item.provenance) for item in watchlist_only] == [
        ("NVDA", "inferred_candidate")
    ]
