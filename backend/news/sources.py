from __future__ import annotations

import csv
import html
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from backend.news.cache import MAX_NEWS_ITEMS
from backend.news.contracts import (
    NewsDashboardSnapshot,
    NewsFreshnessStatus,
    NewsHeadlineCard,
    NewsSymbolEvidenceField,
    NewsSymbolMatch,
    NewsSymbolMatchKind,
)
from backend.news.dashboard import build_demo_news_dashboard_snapshot, build_news_dashboard_snapshot

STANDARD_NEWS_RAW_FETCH_TARGET = 250
STANDARD_NEWS_NORMALIZED_TARGET = MAX_NEWS_ITEMS
STANDARD_NEWS_CATEGORY_QUERY_COUNT = 12
STANDARD_NEWS_PER_QUERY_LIMIT = 15
STANDARD_NEWS_LOOKBACK_DAYS = 7
GOOGLE_NEWS_RSS_SEARCH_URL = "https://news.google.com/rss/search"
DIRECT_SYMBOL_EXTRACTION_LIMIT = 8
INFERRED_SYMBOL_EXTRACTION_LIMIT = 4
MARKET_PROXY_SYMBOL_EXTRACTION_LIMIT = 5
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYMBOL_UNIVERSE_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
MARKET_CONFIRMATION_SYMBOLS = {
    "1306.T",
    "1488.T",
    "2558.T",
    "GLD",
    "QQQ",
    "SPY",
    "TLT",
    "USDJPY",
    "US10Y",
    "VTI",
    "XLE",
}
SYMBOL_NAME_HINTS = {
    "1306.T": "NEXT FUNDS TOPIX ETF",
    "1488.T": "iFreeETF 東証REIT指数",
    "2558.T": "MAXIS S&P500 ETF",
    "6758.T": "Sony Group",
    "6857.T": "Advantest",
    "7203.T": "Toyota Motor",
    "8035.T": "Tokyo Electron",
    "8306.T": "Mitsubishi UFJ",
    "8316.T": "Sumitomo Mitsui FG",
    "AAPL": "Apple",
    "AMD": "Advanced Micro Devices",
    "AMZN": "Amazon",
    "ASML": "ASML",
    "BAC": "Bank of America",
    "GLD": "SPDR Gold Shares",
    "JPM": "JPMorgan Chase",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "QQQ": "Invesco QQQ Trust",
    "SPY": "SPDR S&P 500 ETF",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "TSM": "Taiwan Semiconductor",
    "USDJPY": "ドル円",
    "US10Y": "米10年金利",
    "VTI": "Vanguard Total Stock Market ETF",
    "XLE": "Energy Select Sector SPDR Fund",
}
SYMBOL_ALIAS_BLOCKLIST = {
    "ai",
    "etf",
    "reit",
    "株",
    "日本",
    "米国",
    "銀行",
    "金融",
    "商社",
    "食品",
    "機械",
    "電機",
    "情報",
    "通信",
    "投資",
    "投資証券",
    "プライム",
    "グロース",
    "スタンダード",
    "内国株式",
    "卸売業",
    "食料品",
    "医薬品",
    "化学",
    "サービス業",
    "その他",
}


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


@dataclass(frozen=True)
class NewsSymbolExtractionResult:
    related_symbols: list[str]
    inferred_symbols: list[str]
    macro_proxy_symbols: list[str]
    symbol_matches: list[NewsSymbolMatch]


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
        related_symbols=("TLT", "SPY", "QQQ", "USDJPY", "US10Y"),
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
        related_symbols=("SPY", "QQQ", "VTI", "TLT", "US10Y"),
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
        key = news_headline_dedupe_key(card)
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
    symbol_text = f"{title} {description}"
    symbol_extraction = _extract_news_symbols(symbol_text, category_query)
    ai_comment = _standard_news_ai_comment(
        category_query,
        title=title,
        summary=description,
        related_symbols=symbol_extraction.related_symbols,
        inferred_symbols=symbol_extraction.inferred_symbols,
        macro_proxy_symbols=symbol_extraction.macro_proxy_symbols,
    )
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
        related_symbols=symbol_extraction.related_symbols,
        inferred_symbols=symbol_extraction.inferred_symbols,
        macro_proxy_symbols=symbol_extraction.macro_proxy_symbols,
        symbol_matches=symbol_extraction.symbol_matches,
        ai_comment=ai_comment,
        investment_checkpoints=_standard_news_checkpoints(
            category_query,
            title=title,
            summary=description,
            related_symbols=symbol_extraction.related_symbols,
            inferred_symbols=symbol_extraction.inferred_symbols,
            macro_proxy_symbols=symbol_extraction.macro_proxy_symbols,
        ),
    )


def news_headline_dedupe_key(card: NewsHeadlineCard) -> str:
    """Return the stable, display-safe duplicate key for a normalized headline."""

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


def _extract_news_symbols(
    text: str,
    category_query: NewsCategoryQuery,
) -> NewsSymbolExtractionResult:
    related_symbols = _symbols_from_text(
        text,
        fallback=category_query.related_symbols,
    )
    macro_subthemes = _macro_subthemes_from_text(text, category_query)
    macro_proxy_symbols = _macro_proxy_symbols_from_text(
        text,
        category_query,
        related_symbols=related_symbols,
        macro_subthemes=macro_subthemes,
    )
    inferred_symbols = _inferred_symbols_from_text(
        text,
        related_symbols,
        fallback=category_query.related_symbols,
        category_query=category_query,
        macro_proxy_symbols=macro_proxy_symbols,
        macro_subthemes=macro_subthemes,
    )
    symbol_matches = [
        *_direct_symbol_matches_from_text(text, related_symbols),
        *_symbol_matches_from_symbols(
            inferred_symbols,
            kind="category_inferred",
            confidence=0.45,
            evidence_field="category",
            reason="ニュースカテゴリと本文キーワードからのSMAI推測候補",
        ),
        *_symbol_matches_from_symbols(
            macro_proxy_symbols,
            kind="macro_proxy",
            confidence=0.62,
            evidence_field="category",
            reason="個別銘柄ではなく市場環境を確認するための代理指標",
        ),
        *_rejected_macro_fallback_matches(
            category_query,
            related_symbols=related_symbols,
            inferred_symbols=inferred_symbols,
            macro_proxy_symbols=macro_proxy_symbols,
        ),
    ]
    return NewsSymbolExtractionResult(
        related_symbols=related_symbols,
        inferred_symbols=inferred_symbols,
        macro_proxy_symbols=macro_proxy_symbols,
        symbol_matches=symbol_matches,
    )


def _symbols_from_text(
    text: str,
    *,
    fallback: Sequence[str],
    limit: int = DIRECT_SYMBOL_EXTRACTION_LIMIT,
) -> list[str]:
    symbol_patterns = (
        (r"(?<![A-Za-z0-9])nvidia(?![A-Za-z0-9])|エヌビディア|エヌヴィディア", "NVDA"),
        (
            r"(?<![A-Za-z0-9])tsmc(?![A-Za-z0-9])"
            r"|(?<![A-Za-z0-9])tsm(?![A-Za-z0-9])"
            r"|taiwan semiconductor|台湾積体電路|台積電",
            "TSM",
        ),
        (r"(?<![A-Za-z0-9])asml(?![A-Za-z0-9])", "ASML"),
        (r"(?<![A-Za-z0-9])amd(?![A-Za-z0-9])|advanced micro devices", "AMD"),
        (r"(?<![A-Za-z0-9])broadcom(?![A-Za-z0-9])|ブロードコム", "AVGO"),
        (r"(?<![A-Za-z0-9])lululemon(?![A-Za-z0-9])|ルルレモン", "LULU"),
        (r"(?<![A-Za-z0-9])apple(?![A-Za-z0-9])|アップル", "AAPL"),
        (r"(?<![A-Za-z0-9])microsoft(?![A-Za-z0-9])|マイクロソフト", "MSFT"),
        (r"(?<![A-Za-z0-9])amazon(?![A-Za-z0-9])|アマゾン", "AMZN"),
        (
            r"(?<![A-Za-z0-9])alphabet(?![A-Za-z0-9])|(?<![A-Za-z0-9])google(?![A-Za-z0-9])|グーグル",
            "GOOGL",
        ),
        (r"東京エレクトロン|tokyo electron", "8035.T"),
        (r"アドバンテスト|advantest", "6857.T"),
        (r"トヨタ|toyota", "7203.T"),
        (r"ソニー|sony", "6758.T"),
        (r"ソフトバンク|softbank", "9984.T"),
        (r"任天堂|nintendo", "7974.T"),
        (r"ntt|日本電信電話", "9432.T"),
        (r"三菱商事|mitsubishi corp", "8058.T"),
        (r"三井住友|sumitomo mitsui", "8316.T"),
        (r"三菱ufj|三菱UFJ|mitsubishi ufj", "8306.T"),
        (r"(?<![A-Za-z0-9])jpmorgan(?![A-Za-z0-9])|(?<![A-Za-z0-9])jpm(?![A-Za-z0-9])", "JPM"),
        (r"bank of america|バンク・オブ・アメリカ", "BAC"),
        (r"goldman sachs|ゴールドマン", "GS"),
        (r"morgan stanley|モルガン・スタンレー", "MS"),
        (r"exxon mobil|エクソン", "XOM"),
        (r"chevron|シェブロン", "CVX"),
        (r"eneos", "5020.T"),
        (r"日本郵船|nippon yusen", "9101.T"),
        (r"石川製作所", "6208.T"),
        (r"japan tobacco|日本たばこ|(?<![A-Za-z0-9])jt(?![A-Za-z0-9])", "2914.T"),
        (r"walmart|ウォルマート", "WMT"),
        (r"coca-?cola|コカ・コーラ", "KO"),
        (r"(?<![A-Za-z0-9])inpex(?![A-Za-z0-9])", "1605.T"),
        (
            r"spdr\s*ゴールド\s*シェア|spdr\s*gold\s*shares|(?<![A-Za-z0-9])gld(?![A-Za-z0-9])",
            "GLD",
        ),
        (r"vanguard\s*s&p\s*500\s*etf|(?<![A-Za-z0-9])voo(?![A-Za-z0-9])", "VOO"),
        (r"spdr\s*s&p\s*500\s*etf|(?<![A-Za-z0-9])spy(?![A-Za-z0-9])", "SPY"),
        (r"invesco\s*qqq|(?<![A-Za-z0-9])qqq(?![A-Za-z0-9])", "QQQ"),
        (r"maxis\s*s&p\s*500|ＭＡＸＩＳ米国株式", "2558.T"),
        (r"next\s*funds\s*topix|ＴＯＰＩＸ連動型上場投信", "1306.T"),
        (r"ifreeetf\s*東証reit|東証REIT指数", "1488.T"),
        (r"三菱重工|mitsubishi heavy", "7011.T"),
        (r"三菱電機|mitsubishi electric", "6503.T"),
        (r"住友商事|sumitomo corp", "8053.T"),
        (r"アトラ[ＧG]|アトラグループ", "6029.T"),
        (r"燦[ＨH][ＤD]|燦ホールディングス", "9628.T"),
        (r"リネット[ＪJ]|リネットジャパングループ", "3556.T"),
        (r"ＫＮＴＣＴ|KNTCT|ＫＮＴ－ＣＴ|KNT-CT", "9726.T"),
    )
    matches: dict[str, tuple[int, int]] = {}
    for match in re.finditer(r"【(\d{4})】", text):
        matches[f"{match.group(1)}.T"] = (match.start(), -1)
    for match in re.finditer(r"[（(［\[](\d{4})[）)］\]]", text):
        matches[f"{match.group(1)}.T"] = (match.start(), -1)
    for match in re.finditer(
        r"(?<![A-Za-z0-9])(\d{4})\.T(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    ):
        matches[f"{match.group(1)}.T"] = (match.start(), -1)
    for pattern_index, (pattern, symbol) in enumerate(symbol_patterns):
        pattern_match = re.search(pattern, text, flags=re.IGNORECASE)
        if pattern_match is None:
            continue
        candidate = (pattern_match.start(), pattern_index)
        current = matches.get(symbol)
        if current is None or candidate < current:
            matches[symbol] = candidate
    matched_alias_spans: list[tuple[int, int]] = []
    lowered_text = text.casefold()
    for alias_index, (alias, symbol) in enumerate(_symbol_universe_aliases()):
        alias_match = _find_symbol_alias_match(text, lowered_text, alias)
        if alias_match is None:
            continue
        start, end = alias_match
        if any(
            start >= matched_start and end <= matched_end
            for matched_start, matched_end in matched_alias_spans
        ):
            continue
        matched_alias_spans.append((start, end))
        candidate = (start, len(symbol_patterns) + alias_index)
        current = matches.get(symbol)
        if current is None or candidate < current:
            matches[symbol] = candidate
    return [
        symbol
        for symbol, _ in sorted(
            matches.items(),
            key=lambda item: (item[1][0], item[1][1], item[0]),
        )
    ][:limit]


def _direct_symbol_matches_from_text(
    text: str,
    symbols: Sequence[str],
) -> list[NewsSymbolMatch]:
    return [
        NewsSymbolMatch(
            symbol=symbol,
            name=_symbol_name_hint(symbol),
            kind=kind,
            confidence=confidence,
            evidence_text=evidence_text,
            evidence_field="body",
            reason="本文または見出しに出た銘柄として抽出",
        )
        for symbol in symbols
        for kind, confidence, evidence_text in [_direct_symbol_evidence(text, symbol)]
    ]


def _direct_symbol_evidence(
    text: str,
    symbol: str,
) -> tuple[NewsSymbolMatchKind, float, str | None]:
    normalized = symbol.strip().upper()
    if normalized.endswith(".T") and normalized[:-2].isdigit():
        code = normalized[:-2]
        for pattern in (
            rf"【{re.escape(code)}】",
            rf"[（(［\[]{re.escape(code)}[）)］\]]",
            rf"(?<![A-Za-z0-9]){re.escape(normalized)}(?![A-Za-z0-9])",
        ):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return "code_match", 0.98, match.group(0)
    if re.fullmatch(r"[A-Z][A-Z0-9.-]{0,7}", normalized):
        match = re.search(
            rf"(?<![A-Za-z0-9]){re.escape(normalized)}(?![A-Za-z0-9])",
            text,
        )
        if match:
            return "ticker_match", 0.98, match.group(0)
    lowered_text = text.casefold()
    for alias, alias_symbol in _symbol_universe_aliases():
        if alias_symbol != normalized:
            continue
        alias_match = _find_symbol_alias_match(text, lowered_text, alias)
        if alias_match is None:
            continue
        start, end = alias_match
        confidence = 0.8 if _is_ascii_symbol_alias(alias) else 0.95
        return "alias_match", confidence, text[start:end]
    return "direct_mention", 0.95, None


def _symbol_matches_from_symbols(
    symbols: Sequence[str],
    *,
    kind: NewsSymbolMatchKind,
    confidence: float,
    evidence_field: NewsSymbolEvidenceField,
    reason: str,
) -> list[NewsSymbolMatch]:
    return [
        NewsSymbolMatch(
            symbol=symbol,
            name=_symbol_name_hint(symbol),
            kind=kind,
            confidence=confidence,
            evidence_field=evidence_field,
            reason=reason,
        )
        for symbol in symbols
    ]


def _macro_proxy_symbols_from_text(
    text: str,
    category_query: NewsCategoryQuery,
    *,
    related_symbols: Sequence[str],
    macro_subthemes: set[str],
    limit: int = MARKET_PROXY_SYMBOL_EXTRACTION_LIMIT,
) -> list[str]:
    if not _is_macro_news_context(category_query, macro_subthemes):
        return []

    candidates: list[str] = []
    if "reit" in macro_subthemes:
        candidates.extend(("1488.T", "TLT", "US10Y"))
    if category_query.category == "為替・金利" or macro_subthemes.intersection(
        {"fx", "rates", "bonds", "central_bank", "inflation"}
    ):
        candidates.extend(("TLT", "SPY", "QQQ", "USDJPY", "US10Y"))
    if category_query.category == "米国株" or "us_market" in macro_subthemes:
        candidates.extend(("SPY", "QQQ", "TLT", "US10Y", "VTI"))
    if category_query.category == "日本株" or "japan_market" in macro_subthemes:
        candidates.extend(("1306.T", "USDJPY", "1488.T", "SPY"))
    if "gold" in macro_subthemes:
        candidates.extend(("GLD", "TLT", "SPY"))
    if "energy" in macro_subthemes:
        candidates.extend(("XLE", "SPY", "USDJPY"))

    if not candidates and category_query.material_type == "macro":
        candidates.extend(category_query.related_symbols)
    return _dedupe_symbol_candidates(
        candidates,
        exclude=related_symbols,
        limit=limit,
        allowed=MARKET_CONFIRMATION_SYMBOLS,
    )


def _macro_subthemes_from_text(
    text: str,
    category_query: NewsCategoryQuery,
) -> set[str]:
    lowered = text.casefold()
    subthemes: set[str] = set()
    if category_query.category == "為替・金利":
        subthemes.update({"fx", "rates"})
    if category_query.category == "米国株":
        subthemes.add("us_market")
    if category_query.category == "日本株":
        subthemes.add("japan_market")
    keyword_groups = (
        (("為替", "ドル円", "円安", "円高", "yen", "usd/jpy", "dollar"), "fx"),
        (
            ("金利", "利回り", "米10年", "国債", "treasury", "yield", "利上げ", "利下げ"),
            "rates",
        ),
        (("債券", "米国債", "bond"), "bonds"),
        (("frb", "fomc", "fed", "日銀", "中央銀行"), "central_bank"),
        (
            ("米国株", "米国市場", "s&p", "sp500", "s&p500", "nasdaq", "ナスダック"),
            "us_market",
        ),
        (("日本株", "日経平均", "topix", "東証"), "japan_market"),
        (("銀行", "銀行株", "金融株", "利ざや", "jpmorgan", "bank stocks"), "banks"),
        (("reit", "不動産投信", "東証reit"), "reit"),
        (("インフレ", "物価", "cpi", "ppi"), "inflation"),
        (("金価格", "金相場", "ゴールド", "gold"), "gold"),
        (("原油", "石油", "opec", "lng", "エネルギー"), "energy"),
    )
    for keywords, subtheme in keyword_groups:
        if any(keyword in lowered for keyword in keywords):
            subthemes.add(subtheme)
    return subthemes


def _is_macro_news_context(
    category_query: NewsCategoryQuery,
    macro_subthemes: set[str],
) -> bool:
    if category_query.material_type == "macro":
        return True
    if category_query.category in {"為替・金利", "米国株", "日本株", "地政学・マクロリスク"}:
        return True
    return False


def _rejected_macro_fallback_matches(
    category_query: NewsCategoryQuery,
    *,
    related_symbols: Sequence[str],
    inferred_symbols: Sequence[str],
    macro_proxy_symbols: Sequence[str],
) -> list[NewsSymbolMatch]:
    if category_query.material_type != "macro":
        return []
    visible = {
        symbol.strip().upper()
        for symbol in [*related_symbols, *inferred_symbols, *macro_proxy_symbols]
        if symbol.strip()
    }
    rejected = [
        symbol.strip().upper()
        for symbol in category_query.related_symbols
        if _should_reject_macro_seed_symbol(symbol, visible)
    ]
    return _symbol_matches_from_symbols(
        rejected,
        kind="rejected",
        confidence=0.12,
        evidence_field="fallback",
        reason="カテゴリseedだけでは個別銘柄候補として弱いため非表示",
    )


def _should_reject_macro_seed_symbol(symbol: str, visible_symbols: set[str]) -> bool:
    normalized = symbol.strip().upper()
    return bool(
        normalized
        and normalized not in visible_symbols
        and normalized not in MARKET_CONFIRMATION_SYMBOLS
    )


def _dedupe_symbol_candidates(
    candidates: Sequence[str],
    *,
    exclude: Sequence[str],
    limit: int,
    allowed: set[str] | None = None,
) -> list[str]:
    seen = {symbol.strip().upper() for symbol in exclude if symbol.strip()}
    result: list[str] = []
    for symbol in candidates:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        if allowed is not None and normalized not in allowed:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _symbol_name_hint(symbol: str) -> str | None:
    return SYMBOL_NAME_HINTS.get(symbol.strip().upper())


@lru_cache(maxsize=1)
def _symbol_universe_aliases() -> tuple[tuple[str, str], ...]:
    if not SYMBOL_UNIVERSE_CSV.exists():
        return ()
    symbols_by_alias: dict[str, set[str]] = {}
    try:
        with SYMBOL_UNIVERSE_CSV.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                symbol = (row.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                for alias in _symbol_alias_candidates(row):
                    symbols_by_alias.setdefault(alias, set()).add(symbol)
    except OSError:
        return ()
    symbol_by_alias = {
        alias: next(iter(symbols))
        for alias, symbols in symbols_by_alias.items()
        if len(symbols) == 1
    }
    return tuple(
        sorted(
            symbol_by_alias.items(),
            key=lambda item: (-len(item[0]), item[0], item[1]),
        )
    )


def _symbol_alias_candidates(row: dict[str, str]) -> list[str]:
    alias_tokens = (row.get("aliases") or "").split()
    raw_values = [row.get("name") or ""]
    if alias_tokens:
        raw_values.append(alias_tokens[0])
    aliases: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        alias = _normalize_symbol_alias(value)
        if not alias or alias in seen:
            continue
        seen.add(alias)
        aliases.append(alias)
    return aliases


def _normalize_symbol_alias(value: str) -> str:
    alias = value.strip().strip("、，,・/（）()[]【】")
    if not alias:
        return ""
    if not re.search(r"[^\x00-\x7F]", alias):
        return ""
    lowered = alias.casefold()
    if lowered in SYMBOL_ALIAS_BLOCKLIST or alias in SYMBOL_ALIAS_BLOCKLIST:
        return ""
    if re.fullmatch(r"\d+(?:/\d+)?", alias):
        return ""
    if re.search(r"\d{4}/\d{2}/\d{2}", alias):
        return ""
    if len(alias) < 3 and not re.search(r"[A-Za-z]{3,}", alias):
        return ""
    return alias


def _find_symbol_alias_match(
    text: str,
    lowered_text: str,
    alias: str,
) -> tuple[int, int] | None:
    if _is_ascii_symbol_alias(alias):
        lowered_alias = alias.casefold()
        start = lowered_text.find(lowered_alias)
        while start >= 0:
            end = start + len(alias)
            if _has_ascii_symbol_boundaries(text, start, end):
                return start, end
            start = lowered_text.find(lowered_alias, start + 1)
        return None
    start = text.find(alias)
    while start >= 0:
        end = start + len(alias)
        if _has_non_ascii_symbol_boundaries(text, alias, start, end):
            return start, end
        start = text.find(alias, start + 1)
    return None


def _is_ascii_symbol_alias(alias: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9 .&+-]+", alias))


def _has_ascii_symbol_boundaries(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not (before.isascii() and before.isalnum()) and not (after.isascii() and after.isalnum())


def _has_non_ascii_symbol_boundaries(text: str, alias: str, start: int, end: int) -> bool:
    if not _is_short_katakana_alias(alias):
        return True
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not _is_katakana(before) and not _is_katakana(after)


def _is_short_katakana_alias(alias: str) -> bool:
    return len(alias) <= 3 and all(_is_katakana(char) for char in alias)


def _is_katakana(value: str) -> bool:
    return bool(value) and all("\u30a0" <= char <= "\u30ff" for char in value)


def _inferred_symbols_from_fallback(
    related_symbols: Sequence[str],
    *,
    fallback: Sequence[str],
    limit: int = 3,
) -> list[str]:
    return _dedupe_inferred_symbols(related_symbols, fallback, limit=limit)


def _inferred_symbols_from_text(
    text: str,
    related_symbols: Sequence[str],
    *,
    fallback: Sequence[str],
    category_query: NewsCategoryQuery | None = None,
    macro_proxy_symbols: Sequence[str] = (),
    macro_subthemes: set[str] | None = None,
    limit: int = INFERRED_SYMBOL_EXTRACTION_LIMIT,
) -> list[str]:
    direct_count = len({symbol.strip().upper() for symbol in related_symbols if symbol.strip()})
    if direct_count >= DIRECT_SYMBOL_EXTRACTION_LIMIT:
        return []
    if direct_count >= 6:
        limit = min(limit, 1)
    elif direct_count >= 3:
        limit = min(limit, 2)
    elif direct_count >= 1:
        limit = min(limit, 3)
    lowered = text.casefold()
    subthemes = macro_subthemes or (
        _macro_subthemes_from_text(text, category_query) if category_query else set()
    )
    is_macro_context = bool(category_query and _is_macro_news_context(category_query, subthemes))
    if is_macro_context:
        macro_context_candidates: list[str] = []
        if "banks" in subthemes:
            macro_context_candidates.extend(("JPM", "BAC", "8306.T", "8316.T"))
        if "reit" in subthemes:
            macro_context_candidates.extend(("1488.T",))
        if "energy" in subthemes:
            macro_context_candidates.extend(("XLE", "XOM", "CVX", "1605.T"))
        if "gold" in subthemes:
            macro_context_candidates.extend(("GLD",))
        return _dedupe_inferred_symbols(
            related_symbols,
            macro_context_candidates,
            limit=limit,
            extra_exclude=macro_proxy_symbols,
        )

    context_candidates: list[str] = []
    context_rules = (
        (
            ("金価格", "金相場", "ゴールド"),
            ("GLD", "SPY", "TLT", "QQQ"),
        ),
        (
            ("s&p", "sp500", "s&p500", "s＆p", "株安"),
            ("SPY", "QQQ"),
        ),
        (
            ("nasdaq", "ナスダック"),
            ("QQQ", "SPY", "NVDA"),
        ),
        (
            ("金利", "利回り", "国債", "treasury", "yield"),
            ("TLT", "JPM", "SPY"),
        ),
        (
            ("半導体", "ai半導体", "chip", "semiconductor", "tsmc", "nvidia"),
            ("NVDA", "TSM", "ASML", "AMD", "6857.T", "8035.T"),
        ),
        (
            ("クラウド", "生成ai", "データセンター", "大型テック", "ハイテク"),
            ("MSFT", "NVDA", "AMZN"),
        ),
        (
            ("日経平均", "topix", "日本株"),
            ("1488.T", "1306.T", "7203.T"),
        ),
        (
            ("配当", "自社株買い", "株主還元"),
            ("8306.T", "8058.T", "2914.T"),
        ),
        (
            ("銀行", "金融株", "利ざや", "融資", "bank"),
            ("JPM", "BAC", "8306.T"),
        ),
        (
            ("原油", "石油", "opec", "lng", "エネルギー"),
            ("XLE", "XOM", "CVX", "1605.T"),
        ),
        (
            ("防衛", "地政学", "中東", "軍事", "安全保障"),
            ("7011.T", "6208.T", "GLD"),
        ),
        (
            ("決算", "業績修正", "上方修正", "下方修正"),
            ("QQQ", "SPY", "6758.T"),
        ),
        (
            ("小売", "消費", "個人消費", "retail"),
            ("AMZN", "WMT", "COST"),
        ),
    )
    for keywords, symbols in context_rules:
        if any(keyword.casefold() in lowered for keyword in keywords):
            context_candidates.extend(symbols)
    return _dedupe_inferred_symbols(
        related_symbols,
        [*context_candidates, *fallback],
        limit=limit,
    )


def _dedupe_inferred_symbols(
    related_symbols: Sequence[str],
    candidates: Sequence[str],
    *,
    limit: int,
    extra_exclude: Sequence[str] = (),
) -> list[str]:
    direct_symbols = {
        symbol.strip().upper() for symbol in [*related_symbols, *extra_exclude] if symbol.strip()
    }
    inferred: list[str] = []
    for symbol in candidates:
        normalized = symbol.strip().upper()
        if not normalized or normalized in direct_symbols or normalized in inferred:
            continue
        inferred.append(normalized)
        if len(inferred) >= limit:
            break
    return inferred


def _standard_news_ai_comment(
    category_query: NewsCategoryQuery,
    *,
    title: str,
    summary: str,
    related_symbols: Sequence[str],
    inferred_symbols: Sequence[str],
    macro_proxy_symbols: Sequence[str],
) -> str:
    """Build a compact, RAG-style reading note for a dashboard headline."""

    profile = _news_reading_profile(category_query.material_type)
    topic = _topic_hint(title, summary, category_query)
    source_distance = _symbol_distance_phrase(
        related_symbols,
        inferred_symbols,
        macro_proxy_symbols,
    )
    return (
        f"{profile['lead']} {topic}を中心に、{source_distance}。"
        f"{profile['rag']} ニュース単体では判断せず、公式資料・市場データ・銘柄コックピットで確認します。"
    )


def _standard_news_checkpoints(
    category_query: NewsCategoryQuery,
    *,
    title: str,
    summary: str,
    related_symbols: Sequence[str],
    inferred_symbols: Sequence[str],
    macro_proxy_symbols: Sequence[str],
) -> list[str]:
    profile = _news_reading_profile(category_query.material_type)
    checkpoints = [
        profile["checkpoint"],
        _symbol_checkpoint(related_symbols, inferred_symbols, macro_proxy_symbols),
        _fresh_context_checkpoint(title, summary, category_query),
    ]
    return [checkpoint for checkpoint in checkpoints if checkpoint]


def _news_reading_profile(material_type: str) -> dict[str, str]:
    profiles = {
        "earnings": {
            "lead": "決算・業績材料です。",
            "rag": "会社発表、通期見通し、利益率、需要の継続性を分けて読みます。",
            "checkpoint": "一時的な決算反応か、業績予想や受注に続く材料かを確認します。",
        },
        "fund_flow": {
            "lead": "資金フロー材料です。",
            "rag": "ETFの資金流入、指数採用、金利環境、為替影響を分けて読みます。",
            "checkpoint": "基準価額、出来高、コスト、連動対象の変化を確認します。",
        },
        "macro": {
            "lead": "マクロ環境の材料です。",
            "rag": "金利、為替、指数、景気敏感度のどこに波及しやすいかを整理します。",
            "checkpoint": "指数全体の話か、個別銘柄に波及する話かを切り分けます。",
        },
        "policy": {
            "lead": "政策・規制に関する材料です。",
            "rag": "規制、補助金、関税、制度変更の対象範囲と時期を確認します。",
            "checkpoint": "公式発表の有無、対象地域、企業ごとの影響差を確認します。",
        },
        "risk": {
            "lead": "リスク材料です。",
            "rag": "地政学、資源価格、金利、ディフェンシブ需要のどれに近いかを整理します。",
            "checkpoint": "短期の警戒材料か、業績や需給に継続して効く材料かを確認します。",
        },
        "shareholder_return": {
            "lead": "配当・株主還元の材料です。",
            "rag": "増配、自社株買い、資本効率、財務余力を合わせて読みます。",
            "checkpoint": "還元方針が一過性か、利益成長や財務余力に支えられているかを確認します。",
        },
        "theme": {
            "lead": "テーマ性のある材料です。",
            "rag": "需要、供給制約、設備投資、関連企業への波及を分けて読みます。",
            "checkpoint": "テーマの見出しだけでなく、売上・受注・投資計画に結びつくかを確認します。",
        },
    }
    return profiles.get(
        material_type,
        {
            "lead": "市場ニュース材料です。",
            "rag": "見出し、出典、関連銘柄、価格データを突き合わせて読みます。",
            "checkpoint": "ニュースの発生源と、個別銘柄への距離を確認します。",
        },
    )


def _symbol_distance_phrase(
    related_symbols: Sequence[str],
    inferred_symbols: Sequence[str],
    macro_proxy_symbols: Sequence[str] = (),
) -> str:
    if related_symbols and inferred_symbols:
        return "本文に出た銘柄とSMAI推測候補を分けて確認します"
    if related_symbols:
        return "本文に出た銘柄を優先して確認します"
    if inferred_symbols:
        return "テーマから近そうな銘柄をSMAI推測候補として確認します"
    if macro_proxy_symbols:
        return "個別銘柄ではなく市場確認指標で背景を確認します"
    return "関連銘柄は追加確認候補として慎重に見ます"


def _symbol_checkpoint(
    related_symbols: Sequence[str],
    inferred_symbols: Sequence[str],
    macro_proxy_symbols: Sequence[str] = (),
) -> str:
    if related_symbols:
        return "本文に出た銘柄は、業績・開示・市場データを銘柄コックピットで確認します。"
    if inferred_symbols:
        return "SMAI推測候補は、テーマとの距離が近いかを事業内容で確認します。"
    if macro_proxy_symbols:
        return "市場確認指標は背景確認用として扱い、個別銘柄候補とは分けて見ます。"
    return "関連銘柄が薄い場合は、カテゴリ全体の材料として扱います。"


def _topic_hint(title: str, summary: str, category_query: NewsCategoryQuery) -> str:
    text = f"{title} {summary}".casefold()
    hints = (
        (("gold", "金価格", "金相場"), "金価格・リスク回避"),
        (("tsmc", "nvidia", "半導体", "chip"), "半導体需要と供給"),
        (("決算", "業績", "earnings"), "業績と見通し"),
        (("金利", "為替", "ドル", "treasury", "yield"), "金利・為替"),
        (("配当", "自社株", "shareholder"), "株主還元"),
        (("原油", "lng", "opec", "energy"), "資源・エネルギー"),
        (("防衛", "地政学", "geopolitical"), "地政学リスク"),
    )
    for keywords, label in hints:
        if any(keyword in text for keyword in keywords):
            return label
    return category_query.category


def _fresh_context_checkpoint(
    title: str,
    summary: str,
    category_query: NewsCategoryQuery,
) -> str:
    text = f"{title} {summary}"
    if len(text) < 60:
        return "本文情報が短い場合は、元記事と公式資料で不足情報を補います。"
    return f"{category_query.category}全体の温度感と、個別企業の材料を分けて確認します。"


def _clip_text(value: str, *, max_chars: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max(0, max_chars - 3)].rstrip() + "..."
