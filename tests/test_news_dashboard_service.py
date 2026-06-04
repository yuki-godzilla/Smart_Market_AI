import html
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
    assert cards[0].inferred_symbols == ["NVDA", "ASML", "AMD"]


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
    assert cards[0].inferred_symbols == ["ASML", "6857.T"]


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


def test_google_news_related_symbols_keep_more_direct_mentions_before_inferred_balance():
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    category_query = NewsCategoryQuery(
        category="semiconductors",
        region="global",
        material_type="theme",
        query="semiconductor AI stocks",
        related_symbols=("NVDA", "TSM", "ASML", "AMD", "6857.T", "8035.T"),
    )
    rss = """
    <rss><channel>
      <item>
        <title>NVIDIA、TSMC、ASML、AMD、Broadcom、Apple、Microsoft、Amazon、トヨタを確認</title>
        <link>https://example.com/many-direct-symbols</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>AI半導体と大型テックの決算反応を確認します。</p>]]></description>
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

    assert cards[0].related_symbols == [
        "NVDA",
        "TSM",
        "ASML",
        "AMD",
        "AVGO",
        "AAPL",
        "MSFT",
        "AMZN",
    ]
    assert cards[0].inferred_symbols == []


def test_google_news_inferred_symbols_are_balanced_when_direct_mentions_exist():
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    category_query = NewsCategoryQuery(
        category="semiconductors",
        region="global",
        material_type="theme",
        query="semiconductor AI stocks",
        related_symbols=("NVDA", "TSM", "ASML", "AMD", "6857.T", "8035.T"),
    )
    rss = """
    <rss><channel>
      <item>
        <title>TSMC、NVIDIA、AMDがAI半導体の需要を説明</title>
        <link>https://example.com/balanced-inferred-symbols</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>半導体装置や関連企業への波及も確認します。</p>]]></description>
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
    assert cards[0].inferred_symbols == ["ASML", "6857.T"]


def test_google_news_related_symbols_extract_local_universe_aliases():
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
        <title>伊藤園、第一三共、三井不動産、セコムが決算材料に反応</title>
        <link>https://example.com/local-universe-aliases</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>ニチレイとメディア工房も業績を確認します。</p>]]></description>
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

    assert cards[0].related_symbols == [
        "2593.T",
        "4568.T",
        "8801.T",
        "9735.T",
        "2871.T",
        "3815.T",
    ]


def test_google_news_related_symbols_prefer_longer_alias_match():
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
        <title>オービックビジネスコンサルタントが業績予想を更新</title>
        <link>https://example.com/longer-alias</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>親しみやすい短縮名を含む銘柄名でも確認します。</p>]]></description>
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

    assert cards[0].related_symbols == ["4733.T"]


def test_google_news_related_symbols_do_not_match_short_katakana_inside_longer_name():
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
        <title>レントラクス、前期経常を一転減益に下方修正</title>
        <link>https://example.com/short-katakana-boundary</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>短い別銘柄aliasの部分一致は避けます。</p>]]></description>
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


def test_google_news_related_symbols_extract_common_japanese_short_names():
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
        <title>アトラＧ、燦ＨＤ、リネットＪ、ＫＮＴＣＴが業績予想を修正</title>
        <link>https://example.com/japanese-short-names</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>ニュース見出しの短縮表記も確認します。</p>]]></description>
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

    assert cards[0].related_symbols == ["6029.T", "9628.T", "3556.T", "9726.T"]


@pytest.mark.parametrize(
    ("title", "description", "fallback", "expected_direct", "expected_inferred_prefix"),
    [
        (
            "本日（6月3日）の金価格：下落傾向が継続。",
            "金価格は下落傾向が続き、米国株や金利の動向も確認したい材料です。",
            ("7011.T", "9101.T", "GLD"),
            ["GLD"],
            ["SPY", "TLT", "QQQ"],
        ),
        (
            "今後数年間、半導体の供給は需要を満たすのに十分ではないだろう。",
            "TSMCは生産能力増強を続けています。",
            ("NVDA", "6857.T", "8035.T", "TSM"),
            ["TSM"],
            ["NVDA", "ASML", "AMD"],
        ),
        (
            "Chip supply pressure continues",
            "TSMC said demand is strong before NVIDIA and AMD were mentioned.",
            ("NVDA", "TSM", "AMD"),
            ["TSM", "NVDA", "AMD"],
            ["ASML", "6857.T"],
        ),
        (
            "決算プレビュー：ルルレモンの第1四半期決算",
            "消費関連企業の決算を確認します。",
            ("6758.T", "9432.T", "9984.T"),
            ["LULU"],
            ["QQQ", "SPY", "6758.T"],
        ),
        (
            "米ブロードコム決算が冷や水",
            "AI半導体の期待と決算反応を確認します。",
            ("7203.T", "8306.T", "6758.T"),
            ["AVGO"],
            ["NVDA", "TSM", "ASML"],
        ),
        (
            "ティーライフ【3172】、今期経常を下方修正",
            "業績修正を発表しました。",
            ("6758.T", "9432.T", "9984.T"),
            ["3172.T"],
            ["QQQ", "SPY", "6758.T"],
        ),
        (
            "メディア工房【3815】、今期最終を赤字拡大に下方修正",
            "決算速報です。",
            ("6758.T", "9432.T", "9984.T"),
            ["3815.T"],
            ["QQQ", "SPY", "6758.T"],
        ),
        (
            "日経平均終値931円安、米ブロードコム決算が冷や水",
            "日本株の地合いとAI半導体の反応を確認します。",
            ("7203.T", "8306.T", "6758.T"),
            ["1488.T", "AVGO"],
            ["NVDA", "TSM", "ASML"],
        ),
        (
            "NASDAQが反落、ハイテク株に売り",
            "米国株は金利上昇を嫌気しました。",
            ("NVDA", "JPM", "QQQ"),
            ["QQQ"],
            ["SPY", "NVDA", "TLT"],
        ),
        (
            "SP500週間展望、雇用統計と金利に注目",
            "米国株と国債利回りが焦点です。",
            ("NVDA", "JPM", "QQQ"),
            ["VOO"],
            ["SPY", "QQQ", "TLT"],
        ),
    ],
)
def test_google_news_symbol_extraction_sprint_regression_cases(
    title,
    description,
    fallback,
    expected_direct,
    expected_inferred_prefix,
):
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    escaped_title = html.escape(title)
    escaped_description = html.escape(description)
    category_query = NewsCategoryQuery(
        category="sprint",
        region="global",
        material_type="theme",
        query="sprint regression",
        related_symbols=fallback,
    )
    rss = f"""
    <rss><channel>
      <item>
        <title>{escaped_title}</title>
        <link>https://example.com/sprint-regression</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>{escaped_description}</p>]]></description>
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

    assert cards[0].related_symbols == expected_direct
    assert cards[0].inferred_symbols[: len(expected_inferred_prefix)] == expected_inferred_prefix


def _sprint_case(
    name: str,
    title: str,
    description: str,
    fallback: tuple[str, ...],
    expected_direct: list[str],
    expected_inferred_prefix: list[str],
) -> tuple[str, str, str, tuple[str, ...], list[str], list[str]]:
    return (name, title, description, fallback, expected_direct, expected_inferred_prefix)


def _sprint_100_cases() -> list[tuple[str, str, str, tuple[str, ...], list[str], list[str]]]:
    semi = [
        _sprint_case(
            "semi_01_tsmc",
            "TSMCがAI半導体の増産を説明",
            "半導体需要とAI投資が焦点です。",
            ("NVDA", "TSM", "ASML"),
            ["TSM"],
            ["NVDA", "ASML", "AMD"],
        ),
        _sprint_case(
            "semi_02_nvidia",
            "NVIDIAがAI半導体で最高値",
            "半導体関連の需要が続きます。",
            ("NVDA", "TSM", "ASML"),
            ["NVDA"],
            ["TSM", "ASML", "AMD"],
        ),
        _sprint_case(
            "semi_03_asml",
            "ASMLの受注が回復",
            "AI向け半導体設備投資を確認します。",
            ("NVDA", "TSM", "ASML"),
            ["ASML"],
            ["NVDA", "TSM", "AMD"],
        ),
        _sprint_case(
            "semi_04_amd",
            "AMDが新型AIチップを発表",
            "半導体市場の競争を確認します。",
            ("NVDA", "TSM", "ASML"),
            ["AMD"],
            ["NVDA", "TSM", "ASML"],
        ),
        _sprint_case(
            "semi_05_tel",
            "東京エレクトロンが半導体装置で反発",
            "AI投資の波及を確認します。",
            ("NVDA", "6857.T", "8035.T"),
            ["8035.T"],
            ["NVDA", "TSM", "ASML"],
        ),
        _sprint_case(
            "semi_06_advantest",
            "アドバンテストが半導体検査需要で上昇",
            "AI半導体の需要が材料です。",
            ("NVDA", "6857.T", "8035.T"),
            ["6857.T"],
            ["NVDA", "TSM", "ASML"],
        ),
        _sprint_case(
            "semi_07_broadcom",
            "ブロードコム決算、AI半導体がけん引",
            "半導体とデータセンター需要を確認します。",
            ("7203.T", "8306.T", "6758.T"),
            ["AVGO"],
            ["NVDA", "TSM", "ASML"],
        ),
        _sprint_case(
            "semi_08_three_direct",
            "TSMC、NVIDIA、AMDがAI需要で注目",
            "半導体関連の直接銘柄が複数あります。",
            ("NVDA", "TSM", "AMD"),
            ["TSM", "NVDA", "AMD"],
            [],
        ),
        _sprint_case(
            "semi_09_generic",
            "半導体供給制約が再燃",
            "AI投資とchip需要が続きます。",
            ("NVDA", "6857.T", "8035.T"),
            [],
            ["NVDA", "TSM", "ASML"],
        ),
        _sprint_case(
            "semi_10_code",
            "東京エレクトロン【8035】が業績修正",
            "半導体装置と決算を確認します。",
            ("NVDA", "6857.T", "8035.T"),
            ["8035.T"],
            ["NVDA", "TSM", "ASML"],
        ),
    ]
    tech = [
        _sprint_case(
            "tech_01_apple",
            "AppleがAI機能を発表",
            "大型テックと生成AIの反応を確認します。",
            ("NVDA", "QQQ", "SPY"),
            ["AAPL"],
            ["MSFT", "NVDA", "AMZN"],
        ),
        _sprint_case(
            "tech_02_microsoft",
            "Microsoftのクラウド売上が拡大",
            "生成AIとデータセンター投資が焦点です。",
            ("NVDA", "QQQ", "SPY"),
            ["MSFT"],
            ["NVDA", "AMZN", "QQQ"],
        ),
        _sprint_case(
            "tech_03_amazon",
            "Amazonがクラウド投資を拡大",
            "大型テックのデータセンター需要を確認します。",
            ("NVDA", "QQQ", "SPY"),
            ["AMZN"],
            ["MSFT", "NVDA", "QQQ"],
        ),
        _sprint_case(
            "tech_04_google",
            "Google親会社AlphabetがAI投資を加速",
            "生成AIと大型テックの材料です。",
            ("NVDA", "QQQ", "SPY"),
            ["GOOGL"],
            ["MSFT", "NVDA", "AMZN"],
        ),
        _sprint_case(
            "tech_05_nasdaq",
            "NASDAQが反落、ハイテク株に売り",
            "米国株は金利上昇を嫌気しました。",
            ("NVDA", "JPM", "QQQ"),
            ["QQQ"],
            ["SPY", "NVDA", "TLT"],
        ),
        _sprint_case(
            "tech_06_sp500",
            "S&P500が週間で上昇",
            "米国株と国債利回りを確認します。",
            ("NVDA", "JPM", "QQQ"),
            ["VOO"],
            ["SPY", "QQQ", "TLT"],
        ),
        _sprint_case(
            "tech_07_softbank",
            "ソフトバンクがAI関連投資を拡大",
            "大型テックと生成AIの投資先を確認します。",
            ("7203.T", "9984.T", "6758.T"),
            ["9984.T"],
            ["MSFT", "NVDA", "AMZN"],
        ),
        _sprint_case(
            "tech_08_sony",
            "ソニーがゲームとAI技術で反発",
            "大型テックの材料も確認します。",
            ("6758.T", "7974.T", "9432.T"),
            ["6758.T"],
            ["MSFT", "NVDA", "AMZN"],
        ),
        _sprint_case(
            "tech_09_nintendo",
            "任天堂が新型機期待で上昇",
            "消費と大型テックのセンチメントを確認します。",
            ("6758.T", "7974.T", "9432.T"),
            ["7974.T"],
            ["MSFT", "NVDA", "AMZN"],
        ),
        _sprint_case(
            "tech_10_ntt",
            "NTTがデータセンター投資を拡大",
            "クラウドと生成AI需要を確認します。",
            ("9432.T", "6758.T", "9984.T"),
            ["9432.T"],
            ["MSFT", "NVDA", "AMZN"],
        ),
    ]
    japan = [
        _sprint_case(
            "jp_01_toyota",
            "トヨタが日本株を支える",
            "日経平均とTOPIXの地合いを確認します。",
            ("7203.T", "8306.T", "6758.T"),
            ["7203.T", "1488.T", "1306.T"],
            [],
        ),
        _sprint_case(
            "jp_02_mufg",
            "三菱UFJが日本株の銀行株をけん引",
            "TOPIXと金融株を確認します。",
            ("7203.T", "8306.T", "6758.T"),
            ["8306.T", "1306.T"],
            ["1488.T", "7203.T", "JPM"],
        ),
        _sprint_case(
            "jp_03_smfg",
            "三井住友FGが利ざや改善で上昇",
            "銀行と日本株の材料です。",
            ("8306.T", "8316.T", "JPM"),
            ["8316.T"],
            ["1488.T", "1306.T", "7203.T"],
        ),
        _sprint_case(
            "jp_04_mitsubishi_corp",
            "三菱商事が株主還元を強化",
            "配当と自社株買いを確認します。",
            ("8058.T", "8306.T", "2914.T"),
            ["8058.T"],
            ["8306.T", "2914.T"],
        ),
        _sprint_case(
            "jp_05_jt",
            "日本たばこが高配当銘柄として注目",
            "配当と株主還元を確認します。",
            ("8058.T", "8306.T", "2914.T"),
            ["2914.T"],
            ["8306.T", "8058.T"],
        ),
        _sprint_case(
            "jp_06_code_3172",
            "ティーライフ【3172】が下方修正",
            "業績修正を確認します。",
            ("6758.T", "9432.T", "9984.T"),
            ["3172.T"],
            ["QQQ", "SPY", "6758.T"],
        ),
        _sprint_case(
            "jp_07_code_3815",
            "メディア工房【3815】が赤字拡大",
            "決算速報です。",
            ("6758.T", "9432.T", "9984.T"),
            ["3815.T"],
            ["QQQ", "SPY", "6758.T"],
        ),
        _sprint_case(
            "jp_08_nikkei",
            "日経平均が大幅反落",
            "日本株とTOPIXの地合いを確認します。",
            ("7203.T", "8306.T", "6758.T"),
            ["1488.T", "1306.T"],
            ["7203.T"],
        ),
        _sprint_case(
            "jp_09_topix",
            "TOPIXが高値を更新",
            "日本株の循環物色を確認します。",
            ("7203.T", "8306.T", "6758.T"),
            ["1306.T"],
            ["1488.T", "7203.T"],
        ),
        _sprint_case(
            "jp_10_nikkei_broadcom",
            "日経平均終値931円安、米ブロードコム決算が冷や水",
            "日本株の地合いとAI半導体の反応を確認します。",
            ("7203.T", "8306.T", "6758.T"),
            ["1488.T", "AVGO"],
            ["NVDA", "TSM", "ASML"],
        ),
    ]
    financial = [
        _sprint_case(
            "fin_01_jpm",
            "JPMorganが銀行決算で上昇",
            "銀行と利ざやを確認します。",
            ("JPM", "BAC", "8306.T"),
            ["JPM"],
            ["BAC", "8306.T"],
        ),
        _sprint_case(
            "fin_02_bac",
            "Bank of Americaが融資拡大で反発",
            "銀行株の決算を確認します。",
            ("JPM", "BAC", "8306.T"),
            ["BAC"],
            ["JPM", "8306.T", "QQQ"],
        ),
        _sprint_case(
            "fin_03_gs",
            "Goldman Sachsが市場部門で増益",
            "金融株と銀行決算を確認します。",
            ("JPM", "BAC", "GS"),
            ["GS"],
            ["JPM", "BAC", "8306.T"],
        ),
        _sprint_case(
            "fin_04_ms",
            "Morgan Stanleyが投資銀行部門で改善",
            "金融株とbankの材料です。",
            ("JPM", "BAC", "MS"),
            ["MS"],
            ["JPM", "BAC", "8306.T"],
        ),
        _sprint_case(
            "fin_05_mufg",
            "三菱UFJが金利上昇で買われる",
            "銀行と利ざやが材料です。",
            ("JPM", "BAC", "8306.T"),
            ["8306.T"],
            ["TLT", "JPM", "SPY"],
        ),
        _sprint_case(
            "fin_06_smfg",
            "三井住友FGが銀行株高に連動",
            "金融株と融資の動向を確認します。",
            ("JPM", "BAC", "8306.T"),
            ["8316.T"],
            ["JPM", "BAC", "8306.T"],
        ),
        _sprint_case(
            "fin_07_generic_bank",
            "銀行株が世界的に反発",
            "利ざやと融資需要を確認します。",
            ("JPM", "BAC", "8306.T"),
            [],
            ["JPM", "BAC", "8306.T"],
        ),
        _sprint_case(
            "fin_08_rates",
            "米国債利回り上昇で金融株に注目",
            "金利と銀行の材料です。",
            ("JPM", "BAC", "8306.T"),
            [],
            ["TLT", "JPM", "SPY"],
        ),
        _sprint_case(
            "fin_09_jpm_bac",
            "JPMorganとBank of Americaが決算で明暗",
            "銀行株の反応を確認します。",
            ("JPM", "BAC", "8306.T"),
            ["JPM", "BAC"],
            ["8306.T", "QQQ", "SPY"],
        ),
        _sprint_case(
            "fin_10_gs_ms_jpm",
            "Goldman Sachs、Morgan Stanley、JPMorganが上昇",
            "金融株の直接銘柄が複数あります。",
            ("JPM", "GS", "MS"),
            ["GS", "MS", "JPM"],
            [],
        ),
    ]
    energy = [
        _sprint_case(
            "energy_01_inpex",
            "INPEXが原油高で上昇",
            "エネルギーとOPECの動向を確認します。",
            ("1605.T", "XLE", "XOM"),
            ["1605.T"],
            ["XLE", "XOM", "CVX"],
        ),
        _sprint_case(
            "energy_02_xom",
            "Exxon Mobilが原油高で買われる",
            "石油とエネルギー株を確認します。",
            ("1605.T", "XLE", "XOM"),
            ["XOM"],
            ["XLE", "CVX", "1605.T"],
        ),
        _sprint_case(
            "energy_03_cvx",
            "ChevronがLNG投資を拡大",
            "エネルギー需要を確認します。",
            ("1605.T", "XLE", "XOM"),
            ["CVX"],
            ["XLE", "XOM", "1605.T"],
        ),
        _sprint_case(
            "energy_04_eneos",
            "ENEOSが石油製品価格で上昇",
            "原油とエネルギー価格を確認します。",
            ("1605.T", "XLE", "XOM"),
            ["5020.T"],
            ["XLE", "XOM", "CVX"],
        ),
        _sprint_case(
            "energy_05_oil_generic",
            "原油価格が急騰、OPEC会合に注目",
            "石油とエネルギー株の反応を確認します。",
            ("1605.T", "XLE", "XOM"),
            [],
            ["XLE", "XOM", "CVX"],
        ),
        _sprint_case(
            "energy_06_lng",
            "LNG需要がアジアで拡大",
            "エネルギー株の材料です。",
            ("1605.T", "XLE", "XOM"),
            [],
            ["XLE", "XOM", "CVX"],
        ),
        _sprint_case(
            "energy_07_inpex_eneos",
            "INPEXとENEOSが資源高で上昇",
            "原油価格を確認します。",
            ("1605.T", "5020.T", "XLE"),
            ["1605.T", "5020.T"],
            ["XLE", "XOM", "CVX"],
        ),
        _sprint_case(
            "energy_08_xom_cvx",
            "Exxon MobilとChevronが石油株をけん引",
            "OPECと原油価格が焦点です。",
            ("XOM", "CVX", "XLE"),
            ["XOM", "CVX"],
            ["XLE", "1605.T"],
        ),
        _sprint_case(
            "energy_09_oil_rates",
            "原油高と金利上昇が市場を揺らす",
            "エネルギーと国債利回りを確認します。",
            ("1605.T", "XLE", "XOM"),
            [],
            ["TLT", "JPM", "SPY"],
        ),
        _sprint_case(
            "energy_10_energy_market",
            "エネルギー株に資金流入",
            "原油と石油需要の材料です。",
            ("1605.T", "XLE", "XOM"),
            [],
            ["XLE", "XOM", "CVX"],
        ),
    ]
    defense = [
        _sprint_case(
            "def_01_mhi",
            "三菱重工が防衛需要で上昇",
            "地政学と安全保障を確認します。",
            ("7011.T", "6208.T", "GLD"),
            ["7011.T"],
            ["6208.T", "GLD"],
        ),
        _sprint_case(
            "def_02_ishikawa",
            "石川製作所が防衛関連で急伸",
            "地政学リスクを確認します。",
            ("7011.T", "6208.T", "GLD"),
            ["6208.T", "7011.T"],
            ["GLD"],
        ),
        _sprint_case(
            "def_03_generic",
            "防衛関連株に買い",
            "安全保障と地政学の材料です。",
            ("7011.T", "6208.T", "GLD"),
            ["7011.T"],
            ["6208.T", "GLD"],
        ),
        _sprint_case(
            "def_04_middle_east",
            "中東情勢が緊迫",
            "地政学リスクと安全保障を確認します。",
            ("7011.T", "6208.T", "GLD"),
            [],
            ["7011.T", "6208.T", "GLD"],
        ),
        _sprint_case(
            "def_05_defense_en",
            "Defense stocks rise on geopolitical tension",
            "security spending is in focus.",
            ("7011.T", "6208.T", "GLD"),
            ["7011.T"],
            ["6208.T", "GLD"],
        ),
        _sprint_case(
            "def_06_gold_risk",
            "地政学リスクで金価格が上昇",
            "中東情勢も確認します。",
            ("7011.T", "6208.T", "GLD"),
            ["GLD"],
            ["SPY", "TLT", "QQQ"],
        ),
        _sprint_case(
            "def_07_shipping",
            "日本郵船が中東リスクで下落",
            "地政学と海運を確認します。",
            ("9101.T", "7011.T", "GLD"),
            ["9101.T"],
            ["7011.T", "6208.T", "GLD"],
        ),
        _sprint_case(
            "def_08_mhi_ishikawa",
            "三菱重工と石川製作所が防衛予算で上昇",
            "安全保障を確認します。",
            ("7011.T", "6208.T", "GLD"),
            ["7011.T", "6208.T"],
            ["GLD"],
        ),
        _sprint_case(
            "def_09_war_gold",
            "軍事緊張でゴールドが買われる",
            "地政学リスクを確認します。",
            ("7011.T", "6208.T", "GLD"),
            ["GLD"],
            ["SPY", "TLT", "QQQ"],
        ),
        _sprint_case(
            "def_10_security_generic",
            "安全保障関連の投資が拡大",
            "防衛と地政学の材料です。",
            ("7011.T", "6208.T", "GLD"),
            ["7011.T"],
            ["6208.T", "GLD"],
        ),
    ]
    gold_rates = [
        _sprint_case(
            "gold_01_price",
            "本日（6月3日）の金価格：下落傾向が継続。",
            "米国株や金利の動向も確認したい材料です。",
            ("7011.T", "9101.T", "GLD"),
            ["GLD"],
            ["SPY", "TLT", "QQQ"],
        ),
        _sprint_case(
            "gold_02_gold_en",
            "Gold falls as dollar strengthens",
            "Treasury yield and US stocks are also in focus.",
            ("GLD", "SPY", "TLT"),
            ["GLD"],
            ["TLT", "JPM", "SPY"],
        ),
        _sprint_case(
            "gold_03_gold_sp",
            "金価格とS&P500が同時に下落",
            "リスク資産と金利を確認します。",
            ("GLD", "SPY", "TLT"),
            ["GLD", "VOO"],
            ["SPY", "TLT", "QQQ"],
        ),
        _sprint_case(
            "gold_04_rates",
            "米国債利回りが上昇",
            "金利と米国株の反応を確認します。",
            ("JPM", "QQQ", "TLT"),
            [],
            ["TLT", "JPM", "SPY"],
        ),
        _sprint_case(
            "gold_05_tlt",
            "金利上昇で債券ETFに注目",
            "国債利回りが焦点です。",
            ("JPM", "QQQ", "TLT"),
            [],
            ["TLT", "JPM", "SPY"],
        ),
        _sprint_case(
            "gold_06_sp",
            "SP500週間展望、雇用統計と金利に注目",
            "米国株と国債利回りが焦点です。",
            ("NVDA", "JPM", "QQQ"),
            ["VOO"],
            ["SPY", "QQQ", "TLT"],
        ),
        _sprint_case(
            "gold_07_nasdaq_rate",
            "ナスダックが金利上昇で反落",
            "米国株の地合いを確認します。",
            ("NVDA", "JPM", "QQQ"),
            ["QQQ"],
            ["SPY", "NVDA", "TLT"],
        ),
        _sprint_case(
            "gold_08_gold_safe",
            "ゴールドが安全資産として上昇",
            "金相場と米国株を確認します。",
            ("GLD", "SPY", "TLT"),
            ["GLD"],
            ["SPY", "TLT", "QQQ"],
        ),
        _sprint_case(
            "gold_09_gold_rate",
            "金相場は金利上昇で失速",
            "国債利回りと米国株を確認します。",
            ("GLD", "SPY", "TLT"),
            ["GLD"],
            ["SPY", "TLT", "QQQ"],
        ),
        _sprint_case(
            "gold_10_s_and_p",
            "S＆P500が反発",
            "株安後の米国株を確認します。",
            ("NVDA", "JPM", "QQQ"),
            ["VOO"],
            ["SPY", "QQQ"],
        ),
    ]
    retail = [
        _sprint_case(
            "retail_01_lulu",
            "ルルレモンの決算プレビュー",
            "消費関連企業の決算を確認します。",
            ("6758.T", "9432.T", "9984.T"),
            ["LULU"],
            ["QQQ", "SPY", "6758.T"],
        ),
        _sprint_case(
            "retail_02_amazon",
            "Amazonが小売需要で上昇",
            "retailと個人消費を確認します。",
            ("AMZN", "WMT", "COST"),
            ["AMZN"],
            ["WMT", "COST"],
        ),
        _sprint_case(
            "retail_03_walmart",
            "Walmartが消費底堅さで上昇",
            "小売と個人消費が材料です。",
            ("AMZN", "WMT", "COST"),
            ["WMT"],
            ["AMZN", "COST"],
        ),
        _sprint_case(
            "retail_04_ko",
            "Coca-Colaが消費関連で堅調",
            "個人消費と小売の地合いを確認します。",
            ("AMZN", "WMT", "COST"),
            ["KO"],
            ["AMZN", "WMT", "COST"],
        ),
        _sprint_case(
            "retail_05_generic",
            "小売株に資金流入",
            "個人消費とretailの反応を確認します。",
            ("AMZN", "WMT", "COST"),
            [],
            ["AMZN", "WMT", "COST"],
        ),
        _sprint_case(
            "retail_06_consumer",
            "個人消費が市場を支える",
            "消費関連企業を確認します。",
            ("AMZN", "WMT", "COST"),
            [],
            ["AMZN", "WMT", "COST"],
        ),
        _sprint_case(
            "retail_07_lulu_amzn",
            "ルルレモンとAmazonが消費株をけん引",
            "小売の材料です。",
            ("AMZN", "WMT", "COST"),
            ["LULU", "AMZN"],
            ["WMT", "COST"],
        ),
        _sprint_case(
            "retail_08_wmt_ko",
            "WalmartとCoca-Colaがディフェンシブ消費で上昇",
            "個人消費を確認します。",
            ("AMZN", "WMT", "COST"),
            ["WMT", "KO"],
            ["AMZN", "COST"],
        ),
        _sprint_case(
            "retail_09_jt",
            "JTが消費関連の高配当株として注目",
            "配当と個人消費を確認します。",
            ("8306.T", "8058.T", "2914.T"),
            ["2914.T"],
            ["8306.T", "8058.T"],
        ),
        _sprint_case(
            "retail_10_lulu_code",
            "ルルレモンとティーライフ【3172】が決算で注目",
            "小売と業績修正を確認します。",
            ("AMZN", "WMT", "COST"),
            ["LULU", "3172.T"],
            ["QQQ", "SPY", "6758.T"],
        ),
    ]
    shareholder = [
        _sprint_case(
            "sh_01_mitsubishi",
            "三菱商事が自社株買いを発表",
            "株主還元と配当を確認します。",
            ("8306.T", "8058.T", "2914.T"),
            ["8058.T"],
            ["8306.T", "2914.T"],
        ),
        _sprint_case(
            "sh_02_mufg",
            "三菱UFJが増配を発表",
            "配当と株主還元が材料です。",
            ("8306.T", "8058.T", "2914.T"),
            ["8306.T"],
            ["8058.T", "2914.T"],
        ),
        _sprint_case(
            "sh_03_jt",
            "Japan Tobaccoが配当方針を維持",
            "株主還元を確認します。",
            ("8306.T", "8058.T", "2914.T"),
            ["2914.T"],
            ["8306.T", "8058.T"],
        ),
        _sprint_case(
            "sh_04_generic",
            "高配当株に資金流入",
            "自社株買いと株主還元を確認します。",
            ("8306.T", "8058.T", "2914.T"),
            [],
            ["8306.T", "8058.T", "2914.T"],
        ),
        _sprint_case(
            "sh_05_mitsubishi_mufg",
            "三菱商事と三菱UFJが株主還元で上昇",
            "配当を確認します。",
            ("8306.T", "8058.T", "2914.T"),
            ["8058.T", "8306.T"],
            ["2914.T"],
        ),
        _sprint_case(
            "sh_06_jt_mitsubishi",
            "JTと三菱商事が高配当で注目",
            "株主還元を確認します。",
            ("8306.T", "8058.T", "2914.T"),
            ["2914.T", "8058.T"],
            ["8306.T"],
        ),
        _sprint_case(
            "sh_07_buyback",
            "自社株買い発表企業が相次ぐ",
            "配当と株主還元を確認します。",
            ("8306.T", "8058.T", "2914.T"),
            [],
            ["8306.T", "8058.T", "2914.T"],
        ),
        _sprint_case(
            "sh_08_dividend_bank",
            "銀行株が増配期待で上昇",
            "配当と利ざやを確認します。",
            ("8306.T", "8058.T", "2914.T"),
            [],
            ["8306.T", "8058.T", "2914.T"],
        ),
        _sprint_case(
            "sh_09_code_dividend",
            "日本たばこ【2914】が増配",
            "株主還元を確認します。",
            ("8306.T", "8058.T", "2914.T"),
            ["2914.T"],
            ["8306.T", "8058.T"],
        ),
        _sprint_case(
            "sh_10_return_theme",
            "株主還元テーマが日本株を支える",
            "配当と日本株の地合いを確認します。",
            ("8306.T", "8058.T", "2914.T"),
            [],
            ["1488.T", "1306.T", "7203.T"],
        ),
    ]
    mixed = [
        _sprint_case(
            "mix_01",
            "NVIDIA、Microsoft、AmazonがAI投資で上昇",
            "直接銘柄が複数あります。",
            ("NVDA", "MSFT", "AMZN"),
            ["NVDA", "MSFT", "AMZN"],
            [],
        ),
        _sprint_case(
            "mix_02",
            "トヨタ、ソニー、任天堂が日本株を支える",
            "直接銘柄が複数あります。",
            ("7203.T", "6758.T", "7974.T"),
            ["7203.T", "6758.T", "7974.T"],
            [],
        ),
        _sprint_case(
            "mix_03",
            "JPMorgan、Bank of America、Goldman Sachsが銀行株をけん引",
            "金融株の材料です。",
            ("JPM", "BAC", "GS"),
            ["JPM", "BAC", "GS"],
            [],
        ),
        _sprint_case(
            "mix_04",
            "Exxon Mobil、Chevron、INPEXが原油高で上昇",
            "エネルギー株の直接銘柄です。",
            ("XOM", "CVX", "1605.T"),
            ["XOM", "CVX", "1605.T"],
            [],
        ),
        _sprint_case(
            "mix_05",
            "三菱重工、石川製作所、GLDが地政学リスクで注目",
            "防衛と金価格を確認します。",
            ("7011.T", "6208.T", "GLD"),
            ["7011.T", "6208.T", "GLD"],
            [],
        ),
        _sprint_case(
            "mix_06",
            "Apple、Google、NASDAQがハイテク株を押し上げ",
            "大型テックが材料です。",
            ("AAPL", "GOOGL", "QQQ"),
            ["AAPL", "GOOGL", "QQQ"],
            [],
        ),
        _sprint_case(
            "mix_07",
            "三菱UFJ、三井住友FG、JPMorganが金利上昇で買われる",
            "銀行株が材料です。",
            ("8306.T", "8316.T", "JPM"),
            ["8306.T", "8316.T", "JPM"],
            [],
        ),
        _sprint_case(
            "mix_08",
            "ルルレモン、Walmart、Coca-Colaが消費株で上昇",
            "小売と個人消費を確認します。",
            ("LULU", "WMT", "KO"),
            ["LULU", "WMT", "KO"],
            [],
        ),
        _sprint_case(
            "mix_09",
            "日経平均、TOPIX、S&P500がそろって反発",
            "指数を直接確認します。",
            ("1488.T", "1306.T", "VOO"),
            ["1488.T", "1306.T", "VOO"],
            [],
        ),
        _sprint_case(
            "mix_10",
            "TSMC、ASML、東京エレクトロンが半導体設備で注目",
            "直接銘柄が複数あります。",
            ("TSM", "ASML", "8035.T"),
            ["TSM", "ASML", "8035.T"],
            [],
        ),
    ]
    cases = (
        semi
        + tech
        + japan
        + financial
        + energy
        + defense
        + gold_rates
        + retail
        + shareholder
        + mixed
    )
    assert len(cases) == 100
    return cases


@pytest.mark.parametrize(
    ("name", "title", "description", "fallback", "expected_direct", "expected_inferred_prefix"),
    _sprint_100_cases(),
)
def test_google_news_symbol_extraction_100_case_sprint(
    name,
    title,
    description,
    fallback,
    expected_direct,
    expected_inferred_prefix,
):
    fetched_at = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)
    escaped_title = html.escape(title)
    escaped_description = html.escape(description)
    category_query = NewsCategoryQuery(
        category=f"sprint-{name}",
        region="global",
        material_type="theme",
        query="sprint regression",
        related_symbols=fallback,
    )
    rss = f"""
    <rss><channel>
      <item>
        <title>{escaped_title}</title>
        <link>https://example.com/{name}</link>
        <source>Example Market</source>
        <pubDate>Thu, 04 Jun 2026 09:30:00 GMT</pubDate>
        <description><![CDATA[<p>{escaped_description}</p>]]></description>
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

    assert cards[0].related_symbols == expected_direct
    assert cards[0].inferred_symbols[: len(expected_inferred_prefix)] == expected_inferred_prefix


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
    assert cards[0].inferred_symbols == ["NVDA", "TSM", "ASML", "AMD"]


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
