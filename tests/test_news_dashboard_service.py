from datetime import UTC, datetime

from backend.news import (
    NewsHeadlineCard,
    build_demo_news_dashboard_snapshot,
    build_news_dashboard_snapshot,
    contains_prohibited_recommendation_terms,
)


def test_build_news_dashboard_snapshot_groups_heatmap_and_lanes():
    snapshot = build_news_dashboard_snapshot(
        [
            NewsHeadlineCard(
                title="AI設備投資ニュース",
                summary="設備投資の継続性を確認します。",
                source_type="news",
                category="半導体・AI",
                region="米国",
                material_type="theme",
                published_at=datetime(2026, 6, 4, 9, 0, tzinfo=UTC),
                freshness_status="latest",
                related_symbols=["NVDA"],
            ),
            NewsHeadlineCard(
                title="政策リスクニュース",
                summary="公式資料と影響期間を確認します。",
                source_type="news",
                category="政策・規制",
                region="日本",
                material_type="risk",
                published_at=datetime(2026, 6, 4, 8, 30, tzinfo=UTC),
                freshness_status="recent",
                related_symbols=["7203.T"],
            ),
        ],
        generated_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    assert [card.title for card in snapshot.stream_headlines] == [
        "AI設備投資ニュース",
        "政策リスクニュース",
    ]
    assert {cell.category for cell in snapshot.heatmap_cells} == {"半導体・AI", "政策・規制"}
    assert {lane.category for lane in snapshot.category_lanes} == {"半導体・AI", "政策・規制"}


def test_demo_news_dashboard_snapshot_has_no_recommendation_wording():
    snapshot = build_demo_news_dashboard_snapshot(
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    assert snapshot.stream_headlines
    assert snapshot.heatmap_cells
    assert snapshot.category_lanes
    assert any(card.related_symbols for card in snapshot.stream_headlines)
    for card in snapshot.stream_headlines:
        text = " ".join(
            [
                card.title,
                card.summary or "",
                card.ai_comment or "",
                *card.investment_checkpoints,
            ]
        )
        assert not contains_prohibited_recommendation_terms(text)
