from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from backend.news.cache import MAX_NEWS_ITEMS
from backend.news.contracts import NewsDashboardSnapshot, NewsFreshnessStatus, NewsHeadlineCard
from backend.news.dashboard import build_demo_news_dashboard_snapshot, build_news_dashboard_snapshot

STANDARD_NEWS_RAW_FETCH_TARGET = 250
STANDARD_NEWS_NORMALIZED_TARGET = MAX_NEWS_ITEMS
STANDARD_NEWS_CATEGORY_QUERY_COUNT = 12
STANDARD_NEWS_PER_QUERY_LIMIT = 15
STANDARD_NEWS_LOOKBACK_DAYS = 7
GOOGLE_NEWS_RSS_SEARCH_URL = "https://news.google.com/rss/search"


@dataclass(frozen=True)
class NewsCategoryQuery:
    category: str
    region: str
    material_type: str
    query: str
    related_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewsSourceFetchRequest:
    as_of: date
    fetched_at: datetime
    allow_network: bool
    raw_limit: int = STANDARD_NEWS_RAW_FETCH_TARGET
    max_per_query: int = STANDARD_NEWS_PER_QUERY_LIMIT
    lookback_days: int = STANDARD_NEWS_LOOKBACK_DAYS
    category_queries: Sequence[NewsCategoryQuery] = ()


class NewsSourceAdapter:
    provider: str
    requires_network: bool

    def fetch_headlines(self, request: NewsSourceFetchRequest) -> list[NewsHeadlineCard]:
        raise NotImplementedError


class StaticNewsSourceAdapter(NewsSourceAdapter):
    """Network-free adapter for deterministic tests and local fallbacks."""

    provider = "static"
    requires_network = False

    def __init__(self, headlines: Sequence[NewsHeadlineCard]) -> None:
        self._headlines = list(headlines)

    def fetch_headlines(self, request: NewsSourceFetchRequest) -> list[NewsHeadlineCard]:
        return self._headlines[: max(0, request.raw_limit)]


class GoogleNewsRSSDashboardAdapter(NewsSourceAdapter):
    """Market-wide Google News RSS adapter for the Investment Radar dashboard."""

    provider = "google_news_rss"
    requires_network = True

    def __init__(
        self,
        *,
        http_get: Callable[[str], str] | None = None,
        hl: str = "ja",
        gl: str = "JP",
        ceid: str = "JP:ja",
    ) -> None:
        self._http_get = http_get
        self.hl = hl
        self.gl = gl
        self.ceid = ceid

    def fetch_headlines(self, request: NewsSourceFetchRequest) -> list[NewsHeadlineCard]:
        if self.requires_network and not request.allow_network:
            return []
        headlines: list[NewsHeadlineCard] = []
        for category_query in request.category_queries[:STANDARD_NEWS_CATEGORY_QUERY_COUNT]:
            if len(headlines) >= request.raw_limit:
                break
            rss_url = google_news_dashboard_rss_url(
                category_query,
                lookback_days=request.lookback_days,
                hl=self.hl,
                gl=self.gl,
                ceid=self.ceid,
            )
            try:
                rss_text = self._get_text(rss_url)
            except OSError:
                continue
            remaining = max(0, request.raw_limit - len(headlines))
            per_query_limit = min(request.max_per_query, remaining)
            headlines.extend(
                google_news_dashboard_cards_from_rss(
                    rss_text,
                    category_query=category_query,
                    fetched_at=request.fetched_at,
                    as_of=request.as_of,
                    max_results=per_query_limit,
                    provider=self.provider,
                )
            )
        return headlines

    def _get_text(self, url: str) -> str:
        if self._http_get is not None:
            return self._http_get(url)
        try:
            request = UrlRequest(url, headers={"User-Agent": "SmartMarketAI/1.0"})
            with urlopen(request, timeout=10) as response:  # noqa: S310
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - provider-specific network failure
            raise OSError(f"Google News RSS fetch failed: {url}") from exc


STANDARD_NEWS_CATEGORY_QUERIES: tuple[NewsCategoryQuery, ...] = (
    NewsCategoryQuery(
        category="半導体・AI",
        region="グローバル",
        material_type="theme",
        query="半導体 AI NVIDIA TSMC 設備投資 株",
        related_symbols=("NVDA", "6857.T", "8035.T", "TSM", "ASML", "AMD"),
    ),
    NewsCategoryQuery(
        category="決算・業績修正",
        region="日本",
        material_type="earnings",
        query="決算 業績修正 上方修正 下方修正 株",
        related_symbols=("6758.T", "9432.T", "9984.T", "7974.T", "6861.T"),
    ),
    NewsCategoryQuery(
        category="配当・株主還元",
        region="日本",
        material_type="shareholder_return",
        query="配当 自社株買い 株主還元 ROE 日本株",
        related_symbols=("7203.T", "8306.T", "8316.T", "9432.T", "8058.T"),
    ),
    NewsCategoryQuery(
        category="為替・金利",
        region="米国",
        material_type="macro",
        query="為替 金利 米国債 ドル円 株式市場",
        related_symbols=("JPM", "QQQ", "1488.T", "SPY", "TLT", "8306.T"),
    ),
    NewsCategoryQuery(
        category="金融",
        region="日本",
        material_type="earnings",
        query="銀行 金融株 金利 与信費用 株主還元",
        related_symbols=("8306.T", "8316.T", "JPM", "BAC", "GS", "MS"),
    ),
    NewsCategoryQuery(
        category="エネルギー",
        region="グローバル",
        material_type="policy",
        query="原油 エネルギー株 OPEC LNG 政策",
        related_symbols=("1605.T", "XLE", "XOM", "CVX", "5020.T"),
    ),
    NewsCategoryQuery(
        category="ETF",
        region="グローバル",
        material_type="fund_flow",
        query="ETF 資金流入 経費率 インデックス 投資信託",
        related_symbols=("VOO", "2558.T", "QQQ", "SPY", "VTI", "1306.T"),
    ),
    NewsCategoryQuery(
        category="地政学・マクロリスク",
        region="グローバル",
        material_type="risk",
        query="地政学 リスク 防衛 資源 株式市場",
        related_symbols=("7011.T", "9101.T", "GLD", "6208.T", "6301.T", "1605.T"),
    ),
    NewsCategoryQuery(
        category="政策・規制",
        region="グローバル",
        material_type="policy",
        query="政策 規制 関税 補助金 株式市場",
        related_symbols=("7203.T", "NVDA", "6758.T", "9432.T", "9984.T", "8306.T"),
    ),
    NewsCategoryQuery(
        category="日本株",
        region="日本",
        material_type="macro",
        query="日本株 日経平均 TOPIX 海外投資家 決算",
        related_symbols=("7203.T", "8306.T", "6758.T", "9984.T", "7974.T", "6861.T"),
    ),
    NewsCategoryQuery(
        category="米国株",
        region="米国",
        material_type="macro",
        query="米国株 S&P500 Nasdaq FRB 決算",
        related_symbols=("NVDA", "JPM", "QQQ", "AAPL", "MSFT", "AMZN"),
    ),
    NewsCategoryQuery(
        category="小売・消費",
        region="グローバル",
        material_type="earnings",
        query="小売 消費 インフレ 決算 消費者 株",
        related_symbols=("AMZN", "7203.T", "HD", "WMT", "COST", "9983.T"),
    ),
)


def build_standard_news_dashboard_snapshot(
    *,
    adapters: Sequence[NewsSourceAdapter] | None = None,
    allow_network: bool = False,
    now: datetime | None = None,
    raw_limit: int = STANDARD_NEWS_RAW_FETCH_TARGET,
    normalized_limit: int = STANDARD_NEWS_NORMALIZED_TARGET,
    fallback_to_demo: bool | None = None,
) -> NewsDashboardSnapshot:
    """Build the standard Investment Radar snapshot from broad but bounded sources."""

    fetched_at = now or datetime.now(UTC)
    should_fallback_to_demo = (not allow_network) if fallback_to_demo is None else fallback_to_demo
    request = NewsSourceFetchRequest(
        as_of=fetched_at.date(),
        fetched_at=fetched_at,
        allow_network=allow_network,
        raw_limit=max(1, raw_limit),
        category_queries=STANDARD_NEWS_CATEGORY_QUERIES,
    )
    source_adapters = list(adapters) if adapters is not None else [GoogleNewsRSSDashboardAdapter()]
    raw_headlines: list[NewsHeadlineCard] = []
    for adapter in source_adapters:
        if adapter.requires_network and not allow_network:
            continue
        try:
            raw_headlines.extend(adapter.fetch_headlines(request))
        except Exception:
            continue
        if len(raw_headlines) >= raw_limit:
            break
    headlines = dedupe_news_headline_cards(raw_headlines, limit=normalized_limit)
    if not headlines:
        if should_fallback_to_demo:
            return build_demo_news_dashboard_snapshot(now=fetched_at)
        raise RuntimeError("standard news fetch returned no headlines")
    return build_news_dashboard_snapshot(
        headlines,
        generated_at=fetched_at,
        fetched_at=fetched_at,
        freshness_status=_snapshot_freshness(headlines),
    )


def dedupe_news_headline_cards(
    headlines: Sequence[NewsHeadlineCard],
    *,
    limit: int = STANDARD_NEWS_NORMALIZED_TARGET,
) -> list[NewsHeadlineCard]:
    deduped: list[NewsHeadlineCard] = []
    seen: set[str] = set()
    for card in headlines:
        key = _headline_dedupe_key(card)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(card)
        if len(deduped) >= limit:
            break
    return deduped


def google_news_dashboard_rss_url(
    category_query: NewsCategoryQuery,
    *,
    lookback_days: int,
    hl: str,
    gl: str,
    ceid: str,
) -> str:
    query = f"({category_query.query}) when:{max(1, lookback_days)}d"
    return (
        f"{GOOGLE_NEWS_RSS_SEARCH_URL}?"
        f"{urlencode({'q': query, 'hl': hl, 'gl': gl, 'ceid': ceid})}"
    )


def google_news_dashboard_cards_from_rss(
    rss_text: str,
    *,
    category_query: NewsCategoryQuery,
    fetched_at: datetime,
    as_of: date,
    max_results: int,
    provider: str = GoogleNewsRSSDashboardAdapter.provider,
) -> list[NewsHeadlineCard]:
    try:
        root = ET.fromstring(rss_text)
    except ET.ParseError:
        return []
    cards: list[NewsHeadlineCard] = []
    seen_urls: set[str] = set()
    for item in root.findall(".//item"):
        card = _google_news_dashboard_card_from_item(
            item,
            category_query=category_query,
            fetched_at=fetched_at,
            as_of=as_of,
            provider=provider,
        )
        if card is None:
            continue
        key = (card.url or card.title).casefold()
        if key in seen_urls:
            continue
        seen_urls.add(key)
        cards.append(card)
        if len(cards) >= max_results:
            break
    return cards


def _google_news_dashboard_card_from_item(
    item: ET.Element,
    *,
    category_query: NewsCategoryQuery,
    fetched_at: datetime,
    as_of: date,
    provider: str,
) -> NewsHeadlineCard | None:
    title = _rss_child_text(item, "title")
    url = _rss_child_text(item, "link")
    if not title or not url:
        return None
    source = _rss_child_text(item, "source") or "Google News"
    description = _description_text(_rss_child_text(item, "description"))
    published_at = _rss_datetime(_rss_child_text(item, "pubDate"))
    return NewsHeadlineCard(
        title=_clip_text(title, max_chars=120),
        summary=_clip_text(description or title, max_chars=220),
        url=url,
        source_name=source,
        source_type="news",
        published_at=published_at,
        fetched_at=fetched_at,
        freshness_status=_freshness_from_published_at(published_at, as_of=as_of),
        category=category_query.category,
        region=category_query.region,
        material_type=category_query.material_type,
        related_symbols=_symbols_from_text(
            f"{title} {description}",
            fallback=category_query.related_symbols,
        ),
        ai_comment=_standard_news_ai_comment(category_query),
        investment_checkpoints=_standard_news_checkpoints(category_query),
    )


def _headline_dedupe_key(card: NewsHeadlineCard) -> str:
    if card.url:
        return re.sub(r"[?#].*$", "", card.url.strip()).casefold()
    normalized_title = re.sub(r"\s+", " ", card.title.strip()).casefold()
    return f"{card.category}|{normalized_title}"


def _snapshot_freshness(headlines: Sequence[NewsHeadlineCard]) -> NewsFreshnessStatus:
    statuses = {card.freshness_status for card in headlines}
    if "latest" in statuses:
        return "latest"
    if "recent" in statuses:
        return "recent"
    if "stale" in statuses:
        return "stale"
    return "unknown"


def _rss_child_text(item: ET.Element, tag_name: str) -> str:
    child = item.find(tag_name)
    if child is None or child.text is None:
        return ""
    return html.unescape(child.text).strip()


def _description_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return _clip_text(" ".join(html.unescape(without_tags).split()), max_chars=240)


def _rss_datetime(value: str) -> datetime | None:
    if not value.strip():
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _freshness_from_published_at(
    published_at: datetime | None,
    *,
    as_of: date,
) -> NewsFreshnessStatus:
    if published_at is None:
        return "unknown"
    age_days = (as_of - published_at.date()).days
    if age_days <= 1:
        return "latest"
    if age_days <= 7:
        return "recent"
    return "stale"


def _symbols_from_text(
    text: str,
    *,
    fallback: Sequence[str],
    limit: int = 6,
) -> list[str]:
    symbol_map = {
        "nvidia": "NVDA",
        "エヌビディア": "NVDA",
        "トヨタ": "7203.T",
        "toyota": "7203.T",
        "ソニー": "6758.T",
        "sony": "6758.T",
        "三菱ufj": "8306.T",
        "jpmorgan": "JPM",
        "jpm": "JPM",
        "東京エレクトロン": "8035.T",
        "アドバンテスト": "6857.T",
        "inpex": "1605.T",
        "日経平均": "1488.T",
        "nasdaq": "QQQ",
        "s&p500": "VOO",
        "s&p 500": "VOO",
        "金": "GLD",
        "防衛": "7011.T",
    }
    lowered = text.casefold()
    symbols: list[str] = []
    for needle, symbol in symbol_map.items():
        if needle.casefold() in lowered and symbol not in symbols:
            symbols.append(symbol)
    for symbol in fallback:
        normalized = symbol.strip().upper()
        if normalized and normalized not in symbols:
            symbols.append(normalized)
        if len(symbols) >= limit:
            break
    return symbols[:limit]


def _standard_news_ai_comment(category_query: NewsCategoryQuery) -> str:
    return (
        f"{category_query.category}の材料です。ニュース本文だけで判断せず、"
        "関連銘柄の業績、公式資料、市場データを銘柄コックピットで確認します。"
    )


def _standard_news_checkpoints(category_query: NewsCategoryQuery) -> list[str]:
    return [
        "一時的な見出しか、業績や需給に継続して効く材料かを分けます。",
        "関連銘柄の決算、公式開示、市場データで裏取りします。",
        f"{category_query.category}全体の材料か、個別企業の材料かを確認します。",
    ]


def _clip_text(value: str, *, max_chars: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max(0, max_chars - 3)].rstrip() + "..."
