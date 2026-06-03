from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.news import (
    MAX_AI_COMMENT_CHARS,
    MAX_CHECKPOINTS_PER_NEWS,
    MAX_HEADLINES_PER_CATEGORY,
    MAX_HEATMAP_CELLS,
    MAX_NEWS_ITEMS,
    MAX_STREAM_HEADLINES,
    MAX_SUMMARY_CHARS,
    NewsCategoryLane,
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    NewsHeatmapCell,
    contains_prohibited_recommendation_terms,
    news_snapshot_item_count,
    normalize_snapshot_for_cache,
)


def _headline(index: int, *, category: str = "国内株") -> NewsHeadlineCard:
    return NewsHeadlineCard(
        title=f"ニュース {index}",
        summary="要約" * 200,
        url=f"https://example.com/news/{index}",
        source_name="Example News",
        source_type="news",
        published_at=datetime(2026, 6, 3, 9, index % 60, tzinfo=UTC),
        fetched_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        freshness_status="latest",
        category=category,
        material_type="earnings",
        related_symbols=["7203.T", "7203.t", " NVDA ", "", "NVDA"],
        ai_comment="コメント" * 200,
        investment_checkpoints=[
            "業績への影響を決算資料で確認します。",
            "セクター全体の材料か個別企業の材料か確認します。",
            "業績への影響を決算資料で確認します。",
            "バリュエーション指標と矛盾しないか確認します。",
            "追加の公式資料を確認します。",
        ],
    )


def _heatmap_cell(index: int) -> NewsHeatmapCell:
    return NewsHeatmapCell(
        category=f"カテゴリ {index}",
        price_change_pct=round(index * 0.1, 1),
        volume_activity_score=round(1.0 + index * 0.05, 2),
        news_count=index,
        risk_count=index % 3,
        positive_count=index % 2,
        official_source_count=index % 4,
        freshness_ratio=0.75,
        heat_score=float(index),
        dominant_material_type="risk" if index % 2 else "positive",
    )


def _snapshot() -> NewsDashboardSnapshot:
    lanes = [
        NewsCategoryLane(
            category=f"レーン {lane_index}",
            headlines=[
                _headline(lane_index * 10 + headline_index, category=f"レーン {lane_index}")
                for headline_index in range(12)
            ],
        )
        for lane_index in range(25)
    ]
    return NewsDashboardSnapshot(
        generated_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 6, 3, 9, 55, tzinfo=UTC),
        freshness_status="latest",
        stream_headlines=[_headline(index) for index in range(40)],
        heatmap_cells=[_heatmap_cell(index) for index in range(50)],
        category_lanes=lanes,
    )


def test_normalize_snapshot_for_cache_applies_collection_limits():
    normalized = normalize_snapshot_for_cache(_snapshot())

    assert len(normalized.stream_headlines) == MAX_STREAM_HEADLINES
    assert len(normalized.heatmap_cells) == MAX_HEATMAP_CELLS
    assert all(
        len(lane.headlines) <= MAX_HEADLINES_PER_CATEGORY for lane in normalized.category_lanes
    )
    assert news_snapshot_item_count(normalized) == MAX_NEWS_ITEMS


def test_normalize_snapshot_for_cache_preserves_heatmap_market_metrics():
    normalized = normalize_snapshot_for_cache(_snapshot())
    cell = normalized.heatmap_cells[3]

    assert cell.price_change_pct == 0.3
    assert cell.volume_activity_score == 1.15


def test_normalize_snapshot_for_cache_truncates_text_and_limits_checkpoints():
    normalized = normalize_snapshot_for_cache(_snapshot())
    card = normalized.stream_headlines[0]

    assert card.summary is not None
    assert len(card.summary) == MAX_SUMMARY_CHARS
    assert card.summary.endswith("...")
    assert card.ai_comment is not None
    assert len(card.ai_comment) == MAX_AI_COMMENT_CHARS
    assert card.ai_comment.endswith("...")
    assert len(card.investment_checkpoints) == MAX_CHECKPOINTS_PER_NEWS
    assert card.investment_checkpoints == [
        "業績への影響を決算資料で確認します。",
        "セクター全体の材料か個別企業の材料か確認します。",
        "バリュエーション指標と矛盾しないか確認します。",
    ]


def test_normalize_snapshot_for_cache_dedupes_related_symbols_and_strips_empty_text():
    headline = _headline(1)
    snapshot = NewsDashboardSnapshot(
        generated_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
        stream_headlines=[
            headline.model_copy(
                update={
                    "summary": "   ",
                    "url": "   ",
                    "source_name": "  Example   News  ",
                    "region": "  Japan  ",
                }
            )
        ],
    )

    normalized = normalize_snapshot_for_cache(snapshot)
    card = normalized.stream_headlines[0]

    assert card.related_symbols == ["7203.T", "NVDA"]
    assert card.summary is None
    assert card.url is None
    assert card.source_name == "Example News"
    assert card.region == "Japan"


def test_news_contracts_reject_raw_provider_fields():
    with pytest.raises(ValidationError):
        NewsHeadlineCard(
            title="raw field test",
            source_type="news",
            category="国内株",
            material_type="earnings",
            freshness_status="latest",
            raw_response={"body": "provider payload"},
        )


def test_contains_prohibited_recommendation_terms_flags_banned_wording():
    assert contains_prohibited_recommendation_terms("今すぐ投資すると確実に儲かる")
    assert contains_prohibited_recommendation_terms("この銘柄は買いです")
    assert not contains_prohibited_recommendation_terms(
        "業績への影響は決算資料と合わせて確認します。"
    )
