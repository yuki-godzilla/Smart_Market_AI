from datetime import UTC, datetime

import pytest

from backend.news import (
    NewsCategoryQuery,
    NewsHeadlineCard,
    StaticNewsSourceAdapter,
    build_demo_news_dashboard_snapshot,
    build_news_dashboard_snapshot,
    build_standard_news_dashboard_snapshot,
    contains_prohibited_recommendation_terms,
    dedupe_news_headline_cards,
    google_news_dashboard_cards_from_rss,
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
    assert any(cell.price_change_pct is not None for cell in snapshot.heatmap_cells)
    assert any(cell.volume_activity_score is not None for cell in snapshot.heatmap_cells)
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


def test_standard_news_dashboard_snapshot_uses_bounded_dedupe_from_adapter():
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    headlines = [
        NewsHeadlineCard(
            title=f"市場ニュース {index}",
            summary="市場材料を確認します。",
            url=f"https://example.com/news/{index % 110}",
            source_name="Example News",
            source_type="news",
            category="日本株" if index % 2 else "米国株",
            region="日本" if index % 2 else "米国",
            material_type="macro",
            published_at=fetched_at,
            fetched_at=fetched_at,
            freshness_status="latest",
            related_symbols=["7203.T"],
        )
        for index in range(130)
    ]

    snapshot = build_standard_news_dashboard_snapshot(
        adapters=[StaticNewsSourceAdapter(headlines)],
        allow_network=False,
        now=fetched_at,
    )

    assert len(snapshot.stream_headlines) == 100
    assert len({card.url for card in snapshot.stream_headlines}) == 100
    assert {lane.category for lane in snapshot.category_lanes} == {"日本株", "米国株"}


def test_standard_news_dashboard_snapshot_without_network_uses_demo_fallback():
    snapshot = build_standard_news_dashboard_snapshot(
        allow_network=False,
        now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )

    assert len(snapshot.stream_headlines) == 8
    assert all((card.source_name or "").startswith("SMAI") for card in snapshot.stream_headlines)


def test_standard_news_dashboard_snapshot_can_fail_without_demo_fallback():
    with pytest.raises(RuntimeError):
        build_standard_news_dashboard_snapshot(
            adapters=[StaticNewsSourceAdapter([])],
            allow_network=True,
            fallback_to_demo=False,
            now=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
        )


def test_google_news_dashboard_cards_from_rss_parses_category_fixture():
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    category_query = NewsCategoryQuery(
        category="半導体・AI",
        region="グローバル",
        material_type="theme",
        query="半導体 AI 株",
        related_symbols=("NVDA", "6857.T"),
    )
    rss = """
    <rss><channel>
      <item>
        <title>NVIDIAと半導体投資のニュース</title>
        <link>https://example.com/semiconductor</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>AI投資と半導体設備の動向を確認します。</p>]]></description>
      </item>
      <item>
        <title>重複ニュース</title>
        <link>https://example.com/semiconductor</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:00:00 GMT</pubDate>
      </item>
    </channel></rss>
    """

    cards = google_news_dashboard_cards_from_rss(
        rss,
        category_query=category_query,
        fetched_at=fetched_at,
        as_of=fetched_at.date(),
        max_results=10,
    )

    assert len(cards) == 1
    assert cards[0].category == "半導体・AI"
    assert cards[0].source_name == "Example Market"
    assert cards[0].freshness_status == "latest"
    assert cards[0].related_symbols[0] == "NVDA"
    assert "公式資料" in (cards[0].ai_comment or "")


def test_google_news_related_symbols_prefer_text_hits_over_category_fallback():
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    category_query = NewsCategoryQuery(
        category="半導体・AI",
        region="グローバル",
        material_type="theme",
        query="半導体 AI 株",
        related_symbols=("NVDA", "6857.T", "8035.T"),
    )
    rss = """
    <rss><channel>
      <item>
        <title>半導体供給は今後数年間、需要を満たすのに十分ではない</title>
        <link>https://example.com/chip-supply</link>
        <source>Vietnam.vn</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[
          <p>TSMCの幹部はAI向け半導体の供給制約について説明しました。</p>
        ]]></description>
      </item>
    </channel></rss>
    """

    cards = google_news_dashboard_cards_from_rss(
        rss,
        category_query=category_query,
        fetched_at=fetched_at,
        as_of=fetched_at.date(),
        max_results=10,
    )

    assert cards[0].related_symbols == ["TSM"]
    assert cards[0].inferred_symbols == ["NVDA", "6857.T", "8035.T"]


def test_google_news_related_symbols_keep_article_mention_order():
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    category_query = NewsCategoryQuery(
        category="semiconductors",
        region="global",
        material_type="theme",
        query="semiconductor AI stocks",
        related_symbols=("NVDA", "TSM", "AMD"),
    )
    rss = """
    <rss><channel>
      <item>
        <title>Chip supply pressure continues</title>
        <link>https://example.com/chip-order</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[
          <p>TSMC said demand is strong before NVIDIA and AMD were mentioned by analysts.</p>
        ]]></description>
      </item>
    </channel></rss>
    """

    cards = google_news_dashboard_cards_from_rss(
        rss,
        category_query=category_query,
        fetched_at=fetched_at,
        as_of=fetched_at.date(),
        max_results=10,
    )

    assert cards[0].related_symbols == ["TSM", "NVDA", "AMD"]
    assert cards[0].inferred_symbols == []


def test_google_news_related_symbols_extract_japanese_company_names_and_codes():
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    category_query = NewsCategoryQuery(
        category="earnings",
        region="jp",
        material_type="earnings",
        query="earnings",
        related_symbols=("6758.T", "9432.T", "9984.T"),
    )
    rss = """
    <rss><channel>
      <item>
        <title>決算プレビュー：ルルレモンと米ブロードコムに注目</title>
        <link>https://example.com/earnings-preview</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[
          <p>メディア工房【3815】、ティーライフ【3172】も業績修正を発表しました。</p>
        ]]></description>
      </item>
    </channel></rss>
    """

    cards = google_news_dashboard_cards_from_rss(
        rss,
        category_query=category_query,
        fetched_at=fetched_at,
        as_of=fetched_at.date(),
        max_results=10,
    )

    assert cards[0].related_symbols == ["LULU", "AVGO", "3815.T", "3172.T"]


def test_google_news_related_symbols_do_not_invent_seed_symbols_for_generic_theme():
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    category_query = NewsCategoryQuery(
        category="半導体・AI",
        region="グローバル",
        material_type="theme",
        query="半導体 AI 株",
        related_symbols=("NVDA", "6857.T", "8035.T"),
    )
    rss = """
    <rss><channel>
      <item>
        <title>半導体供給は今後数年間、需要を満たすのに十分ではない</title>
        <link>https://example.com/chip-supply-generic</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[
          <p>AI向け半導体の供給制約が業界全体の課題になっています。</p>
        ]]></description>
      </item>
    </channel></rss>
    """

    cards = google_news_dashboard_cards_from_rss(
        rss,
        category_query=category_query,
        fetched_at=fetched_at,
        as_of=fetched_at.date(),
        max_results=10,
    )

    assert cards[0].related_symbols == []
    assert cards[0].inferred_symbols == ["NVDA", "6857.T", "8035.T"]


def test_dedupe_news_headline_cards_prefers_url_and_limit():
    cards = [
        NewsHeadlineCard(
            title=f"ニュース {index}",
            url="https://example.com/same" if index < 2 else f"https://example.com/{index}",
            source_type="news",
            category="国内株",
            material_type="macro",
        )
        for index in range(5)
    ]

    deduped = dedupe_news_headline_cards(cards, limit=3)

    assert [card.url for card in deduped] == [
        "https://example.com/same",
        "https://example.com/2",
        "https://example.com/3",
    ]
