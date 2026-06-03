from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from backend.news.contracts import (
    NewsCategoryLane,
    NewsDashboardSnapshot,
    NewsFreshnessStatus,
    NewsHeadlineCard,
    NewsHeatmapCell,
)

_FRESHNESS_WEIGHTS: dict[NewsFreshnessStatus, float] = {
    "latest": 1.0,
    "recent": 0.72,
    "stale": 0.32,
    "unknown": 0.18,
}

_MATERIAL_PRIORITY = {
    "risk": 5,
    "earnings": 4,
    "policy": 3,
    "macro": 3,
    "shareholder_return": 2,
    "theme": 2,
    "fund_flow": 1,
}

_DEMO_CATEGORY_MARKET_METRICS: dict[str, tuple[float, float]] = {
    "半導体・AI": (2.4, 1.8),
    "配当・株主還元": (1.2, 1.35),
    "為替・金利": (-0.8, 1.6),
    "エネルギー": (1.7, 1.45),
    "ETF": (0.6, 1.2),
    "決算・業績修正": (-1.1, 1.75),
    "地政学・マクロリスク": (-2.0, 2.1),
    "金融": (0.9, 1.3),
}


def build_news_dashboard_snapshot(
    headlines: Sequence[NewsHeadlineCard],
    *,
    generated_at: datetime | None = None,
    fetched_at: datetime | None = None,
    freshness_status: NewsFreshnessStatus = "latest",
) -> NewsDashboardSnapshot:
    """Build a deterministic Investment News dashboard snapshot from normalized cards."""

    now = generated_at or datetime.now(UTC)
    sorted_headlines = sorted(
        headlines,
        key=lambda card: (
            _FRESHNESS_WEIGHTS.get(card.freshness_status, 0.0),
            _MATERIAL_PRIORITY.get(card.material_type, 0),
            card.published_at or datetime.min.replace(tzinfo=UTC),
            card.title,
        ),
        reverse=True,
    )
    return NewsDashboardSnapshot(
        generated_at=now,
        fetched_at=fetched_at,
        freshness_status=freshness_status,
        stream_headlines=list(sorted_headlines),
        heatmap_cells=_build_heatmap_cells(sorted_headlines),
        category_lanes=_build_category_lanes(sorted_headlines),
    )


def build_demo_news_dashboard_snapshot(
    *,
    now: datetime | None = None,
) -> NewsDashboardSnapshot:
    """Return a network-free sample snapshot for the first Investment News UI slice."""

    base_time = now or datetime(2026, 6, 4, 9, 0, tzinfo=UTC)
    headlines = [
        _headline(
            title="半導体設備の受注見通しに強弱感",
            summary="AI投資の継続期待と在庫調整の長期化が同時に意識されています。",
            category="半導体・AI",
            region="グローバル",
            material_type="theme",
            source_name="SMAI Market Fixture",
            minutes_ago=12,
            freshness_status="latest",
            related_symbols=["NVDA", "6857.T", "8035.T"],
            ai_comment="テーマ全体の材料か、個別企業の受注・粗利率に効く材料かを分けて確認します。",
            investment_checkpoints=[
                "直近決算の受注残と会社計画を確認します。",
                "関連銘柄ごとの売上構成と在庫循環を見比べます。",
                "為替と設備投資サイクルの前提を確認します。",
            ],
        ),
        _headline(
            title="国内大型株で株主還元方針の更新が相次ぐ",
            summary="自己株式取得、増配方針、資本効率の説明が比較材料になっています。",
            category="配当・株主還元",
            region="日本",
            material_type="shareholder_return",
            source_name="SMAI Disclosure Fixture",
            source_type="disclosure",
            minutes_ago=38,
            freshness_status="latest",
            related_symbols=["7203.T", "8306.T"],
            is_official_source=True,
            ai_comment="還元方針だけでなく、利益水準とキャッシュフローの持続性を合わせて確認します。",
            investment_checkpoints=[
                "一時的な還元か継続方針かを開示資料で確認します。",
                "配当性向と自己資本比率の変化を見ます。",
            ],
        ),
        _headline(
            title="米金利の高止まりで金融株と高PER銘柄に見方の差",
            summary="金利感応度の違いにより、金融、成長株、REITで材料の受け止めが分かれています。",
            category="為替・金利",
            region="米国",
            material_type="macro",
            source_name="SMAI Macro Fixture",
            minutes_ago=55,
            freshness_status="latest",
            related_symbols=["JPM", "QQQ", "1488.T"],
            ai_comment="金利材料はセクターごとの追い風と逆風を分け、価格変動リスクも確認します。",
            investment_checkpoints=[
                "金利感応度とバリュエーションの関係を確認します。",
                "ETFの場合は構成比率と為替ヘッジ有無を見ます。",
            ],
        ),
        _headline(
            title="エネルギー関連で原油価格と政策報道を確認",
            summary="供給制約、政策、為替が重なり、短期材料と中期材料の区別が必要です。",
            category="エネルギー",
            region="グローバル",
            material_type="policy",
            source_name="SMAI Policy Fixture",
            minutes_ago=82,
            freshness_status="recent",
            related_symbols=["1605.T", "XLE"],
            ai_comment="資源価格だけでなく、ヘッジ、コスト、政策影響を分けて確認します。",
            investment_checkpoints=[
                "資源価格の前提が業績見通しにどう反映されているか見ます。",
                "政策報道は公式発表と企業開示で確認します。",
            ],
        ),
        _headline(
            title="ETF市場で低コスト商品の資金流入が続く",
            summary="指数連動、経費率、流動性の違いが長期保有の比較材料になっています。",
            category="ETF",
            region="グローバル",
            material_type="fund_flow",
            source_name="SMAI ETF Fixture",
            minutes_ago=110,
            freshness_status="recent",
            related_symbols=["VOO", "2558.T", "QQQ"],
            ai_comment="低コストだけでなく、指数、分配、為替、流動性を並べて確認します。",
            investment_checkpoints=[
                "連動指数と経費率を商品資料で確認します。",
                "分配方針と出来高を見ます。",
            ],
        ),
        _headline(
            title="決算発表前の業績修正ニュースが増加",
            summary="上方修正と下方修正が混在し、個別企業ごとの前提確認が重要です。",
            category="決算・業績修正",
            region="日本",
            material_type="earnings",
            source_name="SMAI Earnings Fixture",
            source_type="news",
            minutes_ago=145,
            freshness_status="recent",
            related_symbols=["6758.T", "9432.T"],
            ai_comment="見通し修正の理由が数量、価格、為替、一時要因のどれかを確認します。",
            investment_checkpoints=[
                "修正理由と通期計画への影響を確認します。",
                "同業他社にも広がる材料か見ます。",
            ],
        ),
        _headline(
            title="地政学リスクで防衛・海運・資源に注目材料",
            summary="短期的な価格変動が出やすい材料のため、根拠と期間を分けて確認します。",
            category="地政学・マクロリスク",
            region="グローバル",
            material_type="risk",
            source_name="SMAI Risk Fixture",
            minutes_ago=210,
            freshness_status="recent",
            related_symbols=["7011.T", "9101.T", "GLD"],
            ai_comment="リスク材料は価格反応だけでなく、企業業績への経路と一時性を確認します。",
            investment_checkpoints=[
                "公式発表と継続性を確認します。",
                "値動きが大きい場合はポジションサイズの前提も確認します。",
            ],
        ),
        _headline(
            title="金融セクターで与信費用と金利収益の見方を確認",
            summary="銀行株では金利収益、与信費用、資本政策が同時に比較されています。",
            category="金融",
            region="日本",
            material_type="earnings",
            source_name="SMAI Banking Fixture",
            minutes_ago=260,
            freshness_status="stale",
            related_symbols=["8306.T", "8316.T"],
            ai_comment="金利収益の追い風と与信費用の変化を同じ表で確認します。",
            investment_checkpoints=[
                "決算資料の利ざやと与信費用を見ます。",
                "株主還元方針と自己資本比率を確認します。",
            ],
        ),
    ]
    return build_news_dashboard_snapshot(
        headlines,
        generated_at=base_time,
        fetched_at=base_time - timedelta(minutes=2),
        freshness_status="latest",
    )


def _build_category_lanes(headlines: Sequence[NewsHeadlineCard]) -> list[NewsCategoryLane]:
    grouped: dict[str, list[NewsHeadlineCard]] = defaultdict(list)
    for headline in headlines:
        grouped[headline.category].append(headline)
    heat_by_category = {cell.category: cell.heat_score for cell in _build_heatmap_cells(headlines)}
    return [
        NewsCategoryLane(category=category, headlines=cards)
        for category, cards in sorted(
            grouped.items(),
            key=lambda item: (heat_by_category.get(item[0], 0.0), item[0]),
            reverse=True,
        )
    ]


def _build_heatmap_cells(headlines: Sequence[NewsHeadlineCard]) -> list[NewsHeatmapCell]:
    grouped: dict[tuple[str, str | None], list[NewsHeadlineCard]] = defaultdict(list)
    for headline in headlines:
        grouped[(headline.category, headline.region)].append(headline)
    cells = [
        _heatmap_cell(category, region, cards) for (category, region), cards in grouped.items()
    ]
    return sorted(cells, key=lambda cell: (cell.heat_score, cell.category), reverse=True)


def _heatmap_cell(
    category: str,
    region: str | None,
    cards: Sequence[NewsHeadlineCard],
) -> NewsHeatmapCell:
    risk_count = sum(1 for card in cards if card.material_type == "risk")
    positive_count = sum(1 for card in cards if card.material_type in {"earnings", "theme"})
    official_count = sum(1 for card in cards if card.is_official_source)
    freshness_ratio = sum(
        _FRESHNESS_WEIGHTS.get(card.freshness_status, 0.0) for card in cards
    ) / max(1, len(cards))
    material_counts: dict[str, int] = defaultdict(int)
    for card in cards:
        material_counts[card.material_type] += 1
    dominant_material = max(
        material_counts,
        key=lambda material: (material_counts[material], _MATERIAL_PRIORITY.get(material, 0)),
    )
    heat_score = round(
        len(cards) * (0.7 + freshness_ratio)
        + risk_count * 1.4
        + positive_count * 0.7
        + official_count * 0.6,
        2,
    )
    price_change_pct, volume_activity_score = _category_market_metrics(category)
    if price_change_pct is not None and volume_activity_score is not None:
        heat_score = round(
            heat_score + abs(price_change_pct) * 0.45 + min(volume_activity_score, 3.0) * 0.7,
            2,
        )
    return NewsHeatmapCell(
        category=category,
        region=region,
        price_change_pct=price_change_pct,
        volume_activity_score=volume_activity_score,
        news_count=len(cards),
        risk_count=risk_count,
        positive_count=positive_count,
        official_source_count=official_count,
        freshness_ratio=round(freshness_ratio, 2),
        heat_score=heat_score,
        dominant_material_type=dominant_material,
    )


def _category_market_metrics(category: str) -> tuple[float | None, float | None]:
    return _DEMO_CATEGORY_MARKET_METRICS.get(category, (None, None))


def _headline(
    *,
    title: str,
    summary: str,
    category: str,
    region: str,
    material_type: str,
    source_name: str,
    minutes_ago: int,
    freshness_status: NewsFreshnessStatus,
    related_symbols: list[str],
    ai_comment: str,
    investment_checkpoints: list[str],
    source_type: str = "news",
    is_official_source: bool = False,
) -> NewsHeadlineCard:
    base_time = datetime(2026, 6, 4, 9, 0, tzinfo=UTC)
    return NewsHeadlineCard(
        title=title,
        summary=summary,
        url=f"https://example.com/smai-news/{category.lower().replace('・', '-')}",
        source_name=source_name,
        source_type=source_type,
        published_at=base_time - timedelta(minutes=minutes_ago),
        fetched_at=base_time,
        freshness_status=freshness_status,
        category=category,
        region=region,
        material_type=material_type,
        related_symbols=related_symbols,
        is_official_source=is_official_source,
        ai_comment=ai_comment,
        investment_checkpoints=investment_checkpoints,
    )
