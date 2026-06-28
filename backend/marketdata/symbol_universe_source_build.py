from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

JPX_LISTED_STOCK_SOURCE_FIELDNAMES = [
    "code",
    "security_name",
    "market",
    "asset_type",
    "currency",
    "theme",
    "sector",
    "tags",
    "aliases",
    "market_cap_tier",
    "source_market_segment",
    "source_industry_33",
    "source_industry_17",
    "source_scale_category",
]

JPX_ETF_SOURCE_FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "theme",
    "sector",
    "index_family",
    "expense_ratio_pct",
    "complexity",
    "tags",
    "aliases",
    "is_leveraged",
    "is_inverse",
    "source_market_segment",
]

JPX_REIT_SOURCE_FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "theme",
    "sector",
    "tags",
    "aliases",
    "source_listing_date",
    "source_settlement_months",
]

SBI_US_STOCK_SOURCE_FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "sector",
    "theme",
    "aliases",
    "dividend_category",
    "dividend_yield_pct",
    "market_cap_tier",
    "tags",
    "per",
    "pbr",
    "roe_pct",
    "consensus_rating",
    "forecast_agreement",
    "data_quality",
    "risk_band",
]

SBI_US_ETF_SOURCE_FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "index_family",
    "expense_ratio_pct",
    "complexity",
    "tags",
    "nisa_category",
    "investment_style",
    "is_leveraged",
    "is_inverse",
    "aliases",
]

SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "asset_type",
    "currency",
    "country",
    "exchange",
    "local_symbol",
    "primary_listing_country",
    "trading_currency",
    "settlement_currency",
    "quote_currency",
    "fx_pair_to_jpy",
    "foreign_market_group",
    "country_risk_band",
    "liquidity_tier",
    "sector",
    "theme",
    "aliases",
    "data_quality",
    "risk_band",
    "foreign_data_quality",
    "foreign_data_quality_reasons",
    "sbi_foreign_tradability",
]

NISA_ELIGIBILITY_SOURCE_FIELDNAMES = [
    "symbol",
    "nisa_category",
    "nisa_growth_eligible",
    "nisa_tsumitate_eligible",
]

_JPX_CODE_PATTERN = re.compile(r"^[0-9A-Z]{4}$")
_US_SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9-]{0,14}$")
_JPX_STOCK_MARKET_MARKERS = ("グロース", "スタンダード", "プライム")
_JPX_ETF_MARKERS = (
    "ETF",
    "ＥＴＦ",
    "ETN",
    "ＥＴＮ",
    "上場投信",
    "上場信託",
    "上場投資信託",
    "上場インデックスファンド",
)
_JPX_NON_STOCK_MARKERS = (
    "ETF",
    "ETN",
    "REIT",
    "インフラファンド",
    "カントリーファンド",
    "ベンチャーファンド",
    "優先出資",
    "出資証券",
)

_CODE_ALIASES = (
    "code",
    "security_code",
    "local_code",
    "コード",
    "コード （ISINコード）",
    "コード（ISINコード）",
    "銘柄コード",
    "銘柄コードメイガラ",
)
_NAME_ALIASES = (
    "security_name",
    "name",
    "company_name",
    "銘柄名",
    "銘柄名称",
    "銘柄名称メイガラメイショウ",
    "ファンド名称",
    "名称",
)
_MARKET_SEGMENT_ALIASES = (
    "market_segment",
    "market_category",
    "market_product_category",
    "市場・商品区分",
    "市場区分",
)
_INDUSTRY_33_ALIASES = (
    "industry_33",
    "industry33",
    "33_industry",
    "33業種区分",
    "33業種",
)
_INDUSTRY_17_ALIASES = (
    "industry_17",
    "industry17",
    "17_industry",
    "17業種区分",
    "17業種",
)
_SCALE_ALIASES = ("scale_category", "size_category", "規模区分", "規模")
_SYMBOL_ALIASES = (
    "symbol",
    "ticker",
    "code",
    "local_code",
    "銘柄コード",
    "ティッカー",
    "シンボル",
    "コード",
    "銘柄コードメイガラ",
)
_COUNTRY_ALIASES = ("country", "国", "国・地域", "取扱国")
_EXCHANGE_ALIASES = ("exchange", "取引所", "市場")
_US_NAME_ALIASES = (
    "name",
    "security_name",
    "company_name",
    "english_name",
    "銘柄名",
    "銘柄（英語）",
    "銘柄(英語)",
    "名称",
    "英文名称",
)
_SECTOR_ALIASES = ("sector", "industry", "gics_sector", "セクター", "業種")
_TAGS_ALIASES = ("tags", "tag", "investment_style_tags", "タグ")
_DIVIDEND_CATEGORY_ALIASES = ("dividend_category", "配当カテゴリ")
_DIVIDEND_YIELD_ALIASES = ("dividend_yield_pct", "dividend_yield", "配当利回り")
_MARKET_CAP_TIER_ALIASES = ("market_cap_tier", "market_cap_size", "時価総額")
_PER_ALIASES = ("per", "pe_ratio", "PER")
_PBR_ALIASES = ("pbr", "price_to_book", "PBR")
_ROE_ALIASES = ("roe_pct", "roe", "ROE")
_CONSENSUS_RATING_ALIASES = ("consensus_rating", "rating", "コンセンサス")
_FORECAST_AGREEMENT_ALIASES = ("forecast_agreement", "予測一致")
_DATA_QUALITY_ALIASES = ("data_quality", "データ品質")
_RISK_BAND_ALIASES = ("risk_band", "risk", "リスク")
_INDEX_FAMILY_ALIASES = (
    "index_family",
    "underlying_index",
    "benchmark",
    "benchmark_index",
    "target_index",
    "連動指数",
    "連動対象指標",
    "対象指標",
    "指数",
    "概要",
)
_EXPENSE_RATIO_ALIASES = (
    "expense_ratio_pct",
    "expense_ratio",
    "trust_fee_pct",
    "経費率",
    "経費 率(年)",
    "経費率(年)",
    "信託報酬",
)
_COMPLEXITY_ALIASES = ("complexity", "leverage_type", "複雑さ")
_NISA_CATEGORY_ALIASES = (
    "nisa_category",
    "nisa_type",
    "NISA区分",
    "NISA 成長投資枠",
)
_NISA_GROWTH_ELIGIBLE_ALIASES = (
    "nisa_growth_eligible",
    "growth_nisa",
    "growth_eligible",
    "成長投資枠",
    "成長投資枠対象",
    "成長投資枠取扱可能日",
    "成長投資枠取扱可能日カノウ",
    "NISA成長投資枠",
)
_NISA_TSUMITATE_ELIGIBLE_ALIASES = (
    "nisa_tsumitate_eligible",
    "tsumitate_nisa",
    "tsumitate_eligible",
    "つみたて投資枠",
    "つみたて投資枠対象",
    "積立投資枠",
    "NISAつみたて投資枠",
)
_INVESTMENT_STYLE_ALIASES = ("investment_style", "投資スタイル")
_IS_LEVERAGED_ALIASES = ("is_leveraged", "leveraged", "レバレッジ")
_IS_INVERSE_ALIASES = ("is_inverse", "inverse", "インバース")
_JPX_NISA_GROWTH_LIST_MARKER_ALIASES = (
    "管理会社",
    "管理会社カンリカイシャ",
    "運用会社名",
    "取扱い開始日",
    "取扱い開始日ト",
    "成長投資枠取扱可能日",
    "成長投資枠取扱可能日カノウ",
)

_INDUSTRY_THEME_SECTOR_MAP = {
    "水産・農林業": ("consumer", "consumer"),
    "鉱業": ("energy", "energy"),
    "建設業": ("industrial", "industrial"),
    "建設・資材": ("industrial", "industrial"),
    "食料品": ("consumer", "consumer"),
    "繊維製品": ("consumer", "consumer"),
    "パルプ・紙": ("materials", "materials"),
    "化学": ("materials", "materials"),
    "素材・化学": ("materials", "materials"),
    "医薬品": ("healthcare", "healthcare"),
    "石油・石炭製品": ("energy", "energy"),
    "ゴム製品": ("automotive", "materials"),
    "ガラス・土石製品": ("materials", "materials"),
    "鉄鋼": ("materials", "materials"),
    "鉄鋼・非鉄": ("materials", "materials"),
    "非鉄金属": ("materials", "materials"),
    "金属製品": ("materials", "materials"),
    "機械": ("industrial", "industrial"),
    "電気機器": ("technology", "technology"),
    "電機・精密": ("technology", "technology"),
    "輸送用機器": ("automotive", "consumer"),
    "自動車・輸送機": ("automotive", "consumer"),
    "精密機器": ("technology", "technology"),
    "その他製品": ("consumer", "consumer"),
    "電気・ガス業": ("utilities", "utilities"),
    "電力・ガス": ("utilities", "utilities"),
    "陸運業": ("industrial", "industrial"),
    "海運業": ("industrial", "industrial"),
    "空運業": ("industrial", "industrial"),
    "倉庫・運輸関連業": ("industrial", "industrial"),
    "運輸・物流": ("industrial", "industrial"),
    "情報・通信業": ("communication", "communication"),
    "情報通信・サービスその他": ("communication", "communication"),
    "卸売業": ("trading", "industrial"),
    "商社・卸売": ("trading", "industrial"),
    "小売業": ("consumer", "consumer"),
    "銀行業": ("bank", "financial"),
    "銀行": ("bank", "financial"),
    "証券、商品先物取引業": ("financial", "financial"),
    "保険業": ("insurance", "financial"),
    "その他金融業": ("financial", "financial"),
    "金融（除く銀行）": ("financial", "financial"),
    "不動産業": ("real_estate", "real_estate"),
    "不動産": ("real_estate", "real_estate"),
    "サービス業": ("consumer", "consumer"),
}

_US_SECTOR_THEME_SECTOR_MAP = {
    "communication": ("communication", "communication"),
    "communication services": ("communication", "communication"),
    "consumer discretionary": ("consumer", "consumer"),
    "consumer staples": ("consumer", "consumer"),
    "consumer": ("consumer", "consumer"),
    "energy": ("energy", "energy"),
    "financial": ("financial", "financial"),
    "financials": ("financial", "financial"),
    "health care": ("healthcare", "healthcare"),
    "healthcare": ("healthcare", "healthcare"),
    "industrial": ("industrial", "industrial"),
    "industrials": ("industrial", "industrial"),
    "information technology": ("technology", "technology"),
    "materials": ("materials", "materials"),
    "real estate": ("real_estate", "real_estate"),
    "semiconductor": ("semiconductor", "technology"),
    "semiconductors": ("semiconductor", "technology"),
    "technology": ("technology", "technology"),
    "utilities": ("utilities", "utilities"),
    "コミュニケーション": ("communication", "communication"),
    "一般消費財": ("consumer", "consumer"),
    "生活必需品": ("consumer", "consumer"),
    "エネルギー": ("energy", "energy"),
    "金融": ("financial", "financial"),
    "ヘルスケア": ("healthcare", "healthcare"),
    "資本財": ("industrial", "industrial"),
    "素材": ("materials", "materials"),
    "不動産": ("real_estate", "real_estate"),
    "情報技術": ("technology", "technology"),
    "公益事業": ("utilities", "utilities"),
}

_COMMODITY_MARKERS = (
    "COMMODITY",
    "GOLD",
    "SILVER",
    "PLATINUM",
    "PALLADIUM",
    "ALUMINUM",
    "COPPER",
    "ENERGY SUBINDEX",
    "WTI",
    "OIL",
    "純金",
    "金価格",
    "金地金",
    "ゴールド",
    "銀価格",
    "純銀",
    "シルバー",
    "プラチナ",
    "パラジウム",
    "原油",
    "商品",
    "コモディティ",
    "金上場",
    "白金",
    "銀上場",
    "天然ガス",
    "ガソリン",
    "農産物",
    "穀物",
    "ニッケル",
    "小麦",
    "とうもろこし",
    "大豆",
    "産業用金属",
)

_INDEX_FAMILY_KEYWORDS = {
    "sp500": ("S&P 500", "SP500", "S&P500", "Ｓ＆Ｐ５００", "Ｓ＆Ｐ ５００"),
    "nasdaq100": ("NASDAQ 100", "NASDAQ100", "NASDAQ-100", "ナスダック100", "ナスダック１００"),
    "total_us": (
        "TOTAL STOCK MARKET",
        "TOTAL U.S.",
        "TOTAL US",
        "TOTAL MARKET",
        "US TARGET MARKET",
        "CRSP US",
        "S&P 1500",
        "S&P1500",
        "コンポジット1500",
        "RUSSELL 1000",
        "RUSSELL1000",
        "ラッセル1000",
        "ラッセル1000種",
        "RUSSELL 3000",
        "RUSSELL3000",
        "ラッセル3000",
        "全米",
        "米国株式市場全体",
    ),
    "small_us": (
        "RUSSELL 2000",
        "RUSSELL2000",
        "ラッセル2000",
        "SMALL-CAP",
        "SMALL CAP",
        "SMALLCAP",
        "小型",
    ),
    "acwi": (
        "ACWI",
        "ALL COUNTRY",
        "TOTAL WORLD",
        "GLOBAL ALL CAP",
        "GLOBAL 100",
        "グローバル100",
        "グローバル 100",
        "全世界",
    ),
    "msci_world": (
        "MSCI WORLD",
        "MSCI EAFE",
        "MSCI PACIFIC",
        "MSCI GERMANY",
        "MSCI ドイツ",
        "MSCIコクサイ",
        "MSCIパシフィック",
        "MSCI‐KOKUSAI",
        "EURO STOXX",
        "ユーロ・ストックス",
        "ヨーロッパ",
        "DAX",
        "KOKUSAI",
        "FTSE DEVELOPED",
        "DEVELOPED",
        "外国株式",
        "海外株式",
        "先進国",
    ),
    "topix": ("TOPIX",),
    "nikkei225": ("NIKKEI 225", "日経225", "日経２２５", "日経平均", "インデックスファンド225"),
    "jpx_nikkei400": ("JPX日経", "ＪＰＸ日経", "JPX-NIKKEI"),
    "dow_jones": ("DOW JONES", "DOW JONES INDUSTRIAL", "ダウ"),
    "china": ("MSCI CHINA", "CSI", "中国", "チャイナ", "FTSE中国", "KWEB"),
    "india": (
        "MSCI INDIA",
        "NIFTY",
        "インディア",
        "インド株",
        "インド成長",
        "インド・オール",
        "インド オール",
        "INDIA",
    ),
    "singapore_equity": (
        "STRAITS TIMES",
        "SINGAPORE STI",
        "MSCI SINGAPORE",
        "MSCI シンガポール",
        "STI ETF",
        "シンガポール STI",
        "シンガポール・低炭素",
    ),
    "emerging": (
        "EMERGING",
        "MSCI EM",
        "新興国",
        "エマージング",
        "ブラジル",
        "ボベスパ",
        "アフリカ",
        "サウジ",
        "VIETNAM",
        "ベトナム",
        "INDONESIA",
        "インドネシア",
        "PHILIPPINES",
        "フィリピン",
        "POLAND",
        "ポーランド",
        "MALAYSIA",
        "マレーシア",
        "TAIWAN",
        "台湾",
        "KOREA",
        "韓国",
        "MEXICO",
        "メキシコ",
        "SOUTH AFRICA",
        "南アフリカ",
        "LATIN AMERICA",
        "ラテンアメリカ",
        "THAILAND",
        "タイ・キャップト",
        "TURKEY",
        "トルコ",
    ),
    "reit": ("REIT", "リート", "不動産投信"),
    "bond": (
        "BOND",
        "TREASURY",
        "FIXED INCOME",
        "PREFERRED",
        "MBS",
        "MORTGAGE",
        "債券",
        "国債",
        "社債",
        "優先証券",
        "優先株式",
        "ハイブリッド証券",
        "モーゲージ",
        "HIGH YIELD",
        "ハイイールド",
        "ハイ イールド",
        "SENIOR LOAN",
        "シニアローン",
        "レバレッジド・ローン",
        "FLOATING RATE",
        "変動金利",
        "転換証券",
        "転換社債",
    ),
    "dividend": (
        "HIGH DIVIDEND",
        "DIVIDEND",
        "SUPERDIVIDEND",
        "高配当",
        "配当貴族",
        "増配",
        "配当",
        "スーパーディビィデンド",
        "スーパーディビデンド",
    ),
    "commodity": _COMMODITY_MARKERS,
    "currency": ("通貨", "米ドル・ブル", "米ドル・ベア", "USD BULL", "USD BEAR"),
    "single_stock": (
        "SINGLE STOCK",
        "DAILY TARGET",
        "DAILY ETF",
        "DAILY ET",
        "デイリー ETF",
        "デイリーETF",
        "デイリーET",
        "デイリーターゲット",
        "普通株式",
        "日次変動率",
        "NASDAQ:",
        "NYSE:",
        "株 ベア",
        "株 ブル",
        "株ベア",
        "株ブル",
    ),
    "style_factor": (
        "GROWTH ETF",
        "VALUE ETF",
        "QUALITY FACTOR",
        "MID-CAP",
        "MID CAP",
        "MIDCAP",
        "S&P MIDCAP",
        "S&Pミッドキャップ",
        "MEGA CAP",
        "MEGACAP",
        "メガキャップ",
        "S&P 100",
        "S&P100",
        "S&P 400",
        "S&P400",
        "S&P中型株",
        "IPOX",
        "IPO",
        "MINIMUM VOLATILITY",
        "LOW VOLATILITY",
        "ESG",
        "ＥＳＧ",
        "BLOSSOM",
        "CARBON",
        "LOW CARBON",
        "カーボン",
        "低カーボン",
        "女性活躍",
        "キャッシュフロー",
        "PRICING POWER",
        "プライシングパワー",
        "SHAREHOLDER YIELD",
        "株主還元",
        "TOP SHARE",
        "トップシェア",
        "COVERED CALL",
        "BUYWRITE",
        "バイライト",
        "カバードコール",
        "カバード・コール",
        "プレミアムインカム",
        "プレミアム ETF",
        "エクイティ プレミアム",
        "ALPHADEX",
        "WIDE MOAT",
        "ワイド モート",
        "バッファー",
        "GROWTH STRENGTH",
        "グロース ストレングス",
        "ロングショート",
        "ロング／ショート",
        "イコールウェイト",
        "均等ウェイト",
        "高ベータ",
        "低ベータ",
        "PBR１倍",
        "PBR1倍",
    ),
    "japan_equity": (
        "日本株",
        "JAPAN EQUITY",
        "MSCI JAPAN",
        "MSCI ジャパン",
        "MSCIジャパン",
        "MSCI日本株",
        "JAPAN TARGET MARKET",
        "JAPAN OPPORTUNITIES",
        "日本オポチュニティー",
        "日経300",
        "日経３００",
        "JPXプライム",
        "ＪＰＸプライム",
        "JPXスタートアップ",
        "S&P／JPX",
        "S&P/JPX",
        "東証グロース",
        "東証スタンダード",
        "日本経済貢献",
        "JPX/S&P",
        "ＪＰＸ／Ｓ＆Ｐ",
        "設備・人材",
        "読売３３３",
        "銀行株",
    ),
    "active": (
        "アクティブ運用型",
        "アクティブ型ETF",
        "アクティブETF",
        "ACTIVE ETF",
        "インカム&アービトラージ",
        "クローズドエンド",
        "CEFハイ",
    ),
    "sector": (
        "SELECT SECTOR",
        "SECTOR",
        "セクター",
        "業種別",
        "半導体",
        "ロボット",
        "ROBOTICS",
        "自動運転",
        "スマートモビリティ",
        "ビッグデータ",
        "BIG DATA",
        "ウラニウム",
        "防衛",
        "DEFENSE",
        "メガトレンド",
        "インバウンド",
        "テレビ業界",
        "地銀",
        "バイオテク",
        "BIOTECH",
        "ブロックチェーン",
        "BLOCKCHAIN",
        "サイバーセキュリティ",
        "CYBERSECURITY",
        "クラウド",
        "CLOUD",
        "eコマース",
        "E-COMMERCE",
        "クリーンテック",
        "CLEAN ENERGY",
        "CLEAN EDGE",
        "クリーンエネルギー",
        "グリーンエネルギー",
        "水素",
        "HYDROGEN",
        "WIND ENERGY",
        "インフラ",
        "INFRASTRUCTURE",
        "ウォーター",
        "WATER",
        "フィンテック",
        "FINTECH",
        "ゲーム",
        "Eスポーツ",
        "ESPORTS",
        "FANG+",
        "ミレニアル",
        "MILLENNIAL",
        "ソーシャルメディア",
        "SOCIAL MEDIA",
        "マグニフィセント",
        "MAGNIFICENT",
        "ヒューマノイド",
        "HUMANOID",
        "イノベーション",
        "INNOVATION",
        "テーマティック",
        "THEMATIC",
        "ヘルステック",
        "HEALTHTECH",
        "HEALTH CARE",
        "ヘルスケア",
        "クリプト",
        "CRYPTO",
        "DIGITAL PAYMENTS",
        "地方銀行",
        "AGRICULTURE",
        "アグリビジネス",
        "農業",
        "FOOD",
        "リチウム",
        "LITHIUM",
        "バッテリー",
        "MLP",
        "次世代通信",
        "NEXTG",
        "石油サービス",
        "医薬品",
        "PHARMACEUTICAL",
        "RARE EARTH",
        "レアアース",
        "戦略的金属",
        "RENEWABLE ENERGY",
        "再生可能",
        "小売",
        "RETAIL",
        "GENDER",
        "DIVERSITY",
        "ジェンダー",
        "鉄鋼",
        "STEEL",
        "SOLAR",
        "ソーラー",
        "太陽光",
        "ラグジュアリー",
        "コッパー",
        "銅ビジネス",
        "AI ",
        "ＡＩ",
        "EV ETF",
        "ＥＶ",
    ),
}

_LEVERAGED_MARKERS = (
    "2X",
    "3X",
    "BULL",
    "LEVERAGED",
    "ULTRA",
    "レバレッジ",
    "ダブル・ブル",
    "ダブル ブル",
    "ダブルブル",
)
_LEVERAGED_PATTERNS = (
    re.compile(r"(?:2|２|3|３)\s*倍"),
    re.compile(r"ブル\s*(?:2|２|3|３)\s*倍"),
    re.compile(r"ダブル\s*[・･]?\s*ブル"),
)
_INVERSE_MARKERS = (
    "BEAR",
    "INVERSE",
    "SHORT",
    "インバース",
    "ベア",
    "反対",
)
_ETN_MARKERS = ("ETN", "ＥＴＮ", "エーティーエヌ")
_REIT_MARKERS = ("REIT", "J-REIT", "リート", "不動産投信")


@dataclass(frozen=True)
class SymbolUniverseSourceBuildResult:
    """Rows and manifest for a generated symbol-universe source CSV."""

    rows: list[dict[str, str]]
    manifest: dict[str, object]


def build_jpx_listed_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build source-import rows from JPX listed-stock raw rows.

    The JPX listed issue file is broader than the MVP ranking universe. This
    builder keeps domestic listed stocks and leaves ETF/ETN/REIT rows for a
    separate ETF/ETN source.
    """

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        code = _normalize_jpx_code(_first_value(raw_row, _CODE_ALIASES))
        name = _first_value(raw_row, _NAME_ALIASES)
        market_segment = _first_value(raw_row, _MARKET_SEGMENT_ALIASES)
        industry_33 = _first_value(raw_row, _INDUSTRY_33_ALIASES)
        industry_17 = _first_value(raw_row, _INDUSTRY_17_ALIASES)
        scale_category = _first_value(raw_row, _SCALE_ALIASES)

        if not code or not name:
            skipped_rows.append(_skipped_row(index, code, "JPX-LISTED-STOCK-MISSING-CODE-OR-NAME"))
            continue
        if not _is_jpx_listed_stock(code, name, market_segment):
            skipped_rows.append(_skipped_row(index, code, "JPX-LISTED-STOCK-OUT-OF-SCOPE"))
            continue

        theme, sector = _theme_sector_for_industry(industry_33, industry_17)
        tags = _tag_for_theme_sector(theme, sector)
        output_rows.append(
            {
                "code": code,
                "security_name": name,
                "market": "jp",
                "asset_type": "stock",
                "currency": "JPY",
                "theme": theme,
                "sector": sector,
                "tags": tags,
                "aliases": _aliases_for_jpx_row(
                    name,
                    market_segment,
                    industry_33,
                    industry_17,
                ),
                "market_cap_tier": _market_cap_tier_for_jpx_scale(scale_category),
                "source_market_segment": market_segment,
                "source_industry_33": industry_33,
                "source_industry_17": industry_17,
                "source_scale_category": scale_category,
            }
        )

    manifest = _source_build_manifest(
        source_kind="jpx_listed_stock",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=JPX_LISTED_STOCK_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def build_jpx_etf_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build source-import rows from JPX ETF/ETN raw rows."""

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        code = _normalize_jpx_code(_first_value(raw_row, _CODE_ALIASES))
        name = _first_value(raw_row, _NAME_ALIASES)
        market_segment = _first_value(raw_row, _MARKET_SEGMENT_ALIASES)
        index_raw = _first_value(raw_row, _INDEX_FAMILY_ALIASES)

        if not code or not name:
            skipped_rows.append(_skipped_row(index, code, "JPX-ETF-MISSING-CODE-OR-NAME"))
            continue
        if (
            not _is_jpx_etf_or_etn(code, name, market_segment)
            and not _is_jpx_nisa_growth_list_row(raw_row)
            and not _is_jpx_etf_issue_table_row(raw_row, index_raw)
        ):
            skipped_rows.append(_skipped_row(index, code, "JPX-ETF-OUT-OF-SCOPE"))
            continue

        complexity = _complexity_for_etf(raw_row, name)
        is_leveraged = _flag_for_etf(
            raw_row,
            _IS_LEVERAGED_ALIASES,
            name,
            _LEVERAGED_MARKERS,
        )
        is_inverse = _flag_for_etf(raw_row, _IS_INVERSE_ALIASES, name, _INVERSE_MARKERS)
        theme, sector = _theme_sector_for_jpx_etf(name, index_raw)
        output_rows.append(
            {
                "symbol": f"{code}.T",
                "name": name,
                "market": "jp",
                "asset_type": "etf",
                "currency": "JPY",
                "theme": theme,
                "sector": sector,
                "index_family": _index_family_for_text(index_raw, name),
                "expense_ratio_pct": _normalize_percent(
                    _first_value(raw_row, _EXPENSE_RATIO_ALIASES)
                ),
                "complexity": complexity,
                "tags": _first_value(raw_row, _TAGS_ALIASES)
                or _tags_for_jpx_etf(theme, complexity, name),
                "aliases": _aliases_for_values(name, market_segment, index_raw),
                "is_leveraged": is_leveraged,
                "is_inverse": is_inverse,
                "source_market_segment": market_segment,
            }
        )

    manifest = _source_build_manifest(
        source_kind="jpx_etf",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=JPX_ETF_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def build_jpx_reit_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build source-import rows from JPX listed REIT raw rows."""

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        code = _normalize_jpx_code(_first_value(raw_row, _CODE_ALIASES))
        name = _first_value(raw_row, _NAME_ALIASES)
        listing_date = _first_value(raw_row, ("上場日",))
        settlement_months = _first_value(raw_row, ("決算期",))

        if not code or not name:
            skipped_rows.append(_skipped_row(index, code, "JPX-REIT-MISSING-CODE-OR-NAME"))
            continue
        if not _is_jpx_reit_issue(name):
            skipped_rows.append(_skipped_row(index, code, "JPX-REIT-OUT-OF-SCOPE"))
            continue

        output_rows.append(
            {
                "symbol": f"{code}.T",
                "name": name,
                "market": "jp",
                "asset_type": "reit",
                "currency": "JPY",
                "theme": "reit",
                "sector": "real_estate",
                "tags": "dividend,balanced",
                "aliases": _aliases_for_values(name, listing_date, settlement_months),
                "source_listing_date": listing_date,
                "source_settlement_months": settlement_months,
            }
        )

    manifest = _source_build_manifest(
        source_kind="jpx_reit",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=JPX_REIT_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def build_sbi_us_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build source-import rows from a local SBI US stock handling list."""

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        symbol = _normalize_us_symbol(_first_value(raw_row, _SYMBOL_ALIASES))
        name = _first_value(raw_row, _US_NAME_ALIASES)
        sector_raw = _first_value(raw_row, _SECTOR_ALIASES)
        market_raw = _first_value(raw_row, ("market", "exchange", "市場"))

        if not symbol or not name:
            skipped_rows.append(_skipped_row(index, symbol, "SBI-US-STOCK-MISSING-SYMBOL-OR-NAME"))
            continue
        if "事業内容" in raw_row and not market_raw:
            skipped_rows.append(_skipped_row(index, symbol, "SBI-US-STOCK-MALFORMED-OFFICIAL-ROW"))
            continue

        theme, sector = _theme_sector_for_us_sector(sector_raw)
        output_rows.append(
            {
                "symbol": symbol,
                "name": name,
                "market": "us",
                "asset_type": "stock",
                "currency": "USD",
                "sector": sector,
                "theme": theme,
                "aliases": _aliases_for_values(name, sector_raw),
                "dividend_category": _first_value(raw_row, _DIVIDEND_CATEGORY_ALIASES),
                "dividend_yield_pct": _normalize_percent(
                    _first_value(raw_row, _DIVIDEND_YIELD_ALIASES)
                ),
                "market_cap_tier": _first_value(raw_row, _MARKET_CAP_TIER_ALIASES),
                "tags": _first_value(raw_row, _TAGS_ALIASES)
                or _tag_for_theme_sector(theme, sector),
                "per": _first_value(raw_row, _PER_ALIASES),
                "pbr": _first_value(raw_row, _PBR_ALIASES),
                "roe_pct": _normalize_percent(_first_value(raw_row, _ROE_ALIASES)),
                "consensus_rating": _first_value(raw_row, _CONSENSUS_RATING_ALIASES),
                "forecast_agreement": _first_value(raw_row, _FORECAST_AGREEMENT_ALIASES),
                "data_quality": _first_value(raw_row, _DATA_QUALITY_ALIASES),
                "risk_band": _first_value(raw_row, _RISK_BAND_ALIASES),
            }
        )

    manifest = _source_build_manifest(
        source_kind="sbi_us_stock",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=SBI_US_STOCK_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def build_sbi_us_etf_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build source-import rows from a local SBI US/overseas ETF handling list."""

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        symbol = _normalize_us_symbol(_first_value(raw_row, _SYMBOL_ALIASES))
        name = _first_value(raw_row, _US_NAME_ALIASES)
        index_raw = _first_value(raw_row, _INDEX_FAMILY_ALIASES)

        if not symbol or not name:
            skipped_rows.append(_skipped_row(index, symbol, "SBI-US-ETF-MISSING-SYMBOL-OR-NAME"))
            continue

        complexity = _complexity_for_etf(raw_row, name)
        is_leveraged = _flag_for_etf(raw_row, _IS_LEVERAGED_ALIASES, name, _LEVERAGED_MARKERS)
        is_inverse = _flag_for_etf(raw_row, _IS_INVERSE_ALIASES, name, _INVERSE_MARKERS)
        nisa_category = _nisa_category_for_sbi_growth_column(
            _first_value(raw_row, _NISA_CATEGORY_ALIASES)
        )
        output_rows.append(
            {
                "symbol": symbol,
                "name": name,
                "market": "us",
                "asset_type": "etf",
                "currency": "USD",
                "index_family": _index_family_for_text(index_raw, name),
                "expense_ratio_pct": _normalize_percent(
                    _first_value(raw_row, _EXPENSE_RATIO_ALIASES)
                ),
                "complexity": complexity,
                "tags": _first_value(raw_row, _TAGS_ALIASES) or _tags_for_etf(complexity),
                "nisa_category": nisa_category,
                "investment_style": _first_value(raw_row, _INVESTMENT_STYLE_ALIASES)
                or ("lump_sum" if is_leveraged == "true" or is_inverse == "true" else "both"),
                "is_leveraged": is_leveraged,
                "is_inverse": is_inverse,
                "aliases": _aliases_for_values(name, index_raw),
            }
        )

    manifest = _source_build_manifest(
        source_kind="sbi_us_etf",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=SBI_US_ETF_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def build_sbi_hk_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    return _build_sbi_foreign_stock_source_rows(raw_rows, as_of=as_of, profile="sbi_hk_stock")


def build_sbi_korea_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    return _build_sbi_foreign_stock_source_rows(raw_rows, as_of=as_of, profile="sbi_korea_stock")


def build_sbi_vietnam_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    return _build_sbi_foreign_stock_source_rows(raw_rows, as_of=as_of, profile="sbi_vietnam_stock")


def build_sbi_indonesia_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    return _build_sbi_foreign_stock_source_rows(
        raw_rows, as_of=as_of, profile="sbi_indonesia_stock"
    )


def build_sbi_singapore_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    return _build_sbi_foreign_stock_source_rows(
        raw_rows, as_of=as_of, profile="sbi_singapore_stock"
    )


def build_sbi_thailand_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    return _build_sbi_foreign_stock_source_rows(raw_rows, as_of=as_of, profile="sbi_thailand_stock")


def build_sbi_malaysia_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    return _build_sbi_foreign_stock_source_rows(raw_rows, as_of=as_of, profile="sbi_malaysia_stock")


def _build_sbi_foreign_stock_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
    profile: str,
) -> SymbolUniverseSourceBuildResult:
    defaults = _foreign_stock_defaults(profile)
    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        local_symbol = _normalize_foreign_symbol(_first_value(raw_row, _SYMBOL_ALIASES))
        name = _first_value(raw_row, _US_NAME_ALIASES)
        sector_raw = _first_value(raw_row, _SECTOR_ALIASES)
        if not local_symbol or not name:
            skipped_rows.append(
                _skipped_row(index, local_symbol, "SBI-FOREIGN-MISSING-SYMBOL-OR-NAME")
            )
            continue

        theme, sector = _theme_sector_for_us_sector(sector_raw)
        symbol = (
            f"{local_symbol}{defaults['yahoo_suffix']}"
            if defaults["yahoo_suffix"]
            else local_symbol
        )
        output_rows.append(
            {
                "symbol": symbol,
                "name": name,
                "market": defaults["market"],
                "asset_type": "stock",
                "currency": defaults["currency"],
                "country": _first_value(raw_row, _COUNTRY_ALIASES) or defaults["country"],
                "exchange": _first_value(raw_row, _EXCHANGE_ALIASES) or defaults["exchange"],
                "local_symbol": local_symbol,
                "primary_listing_country": defaults["country"],
                "trading_currency": defaults["currency"],
                "settlement_currency": defaults["currency"],
                "quote_currency": defaults["currency"],
                "fx_pair_to_jpy": defaults["fx_pair_to_jpy"],
                "foreign_market_group": defaults["foreign_market_group"],
                "country_risk_band": defaults["country_risk_band"],
                "liquidity_tier": _first_value(raw_row, ("liquidity_tier", "流動性ランク"))
                or "unknown",
                "sector": sector,
                "theme": theme,
                "aliases": _aliases_for_values(
                    name, sector_raw, defaults["country"], defaults["exchange"]
                ),
                "data_quality": _first_value(raw_row, _DATA_QUALITY_ALIASES) or "WARN",
                "risk_band": _first_value(raw_row, _RISK_BAND_ALIASES) or "standard",
                "foreign_data_quality": "WARN",
                "foreign_data_quality_reasons": "new_foreign_source_requires_review",
                "sbi_foreign_tradability": "tradable",
            }
        )

    manifest = _source_build_manifest(
        source_kind=profile,
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=SBI_FOREIGN_STOCK_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def build_nisa_eligibility_source_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> SymbolUniverseSourceBuildResult:
    """Build update-only NISA metadata source rows from local raw rows."""

    output_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        symbol = _normalize_nisa_symbol(_first_value(raw_row, _SYMBOL_ALIASES))
        category_raw = _first_value(raw_row, _NISA_CATEGORY_ALIASES)
        growth_raw = _first_value(raw_row, _NISA_GROWTH_ELIGIBLE_ALIASES)
        tsumitate_raw = _first_value(raw_row, _NISA_TSUMITATE_ELIGIBLE_ALIASES)

        if not symbol:
            skipped_rows.append(_skipped_row(index, "", "NISA-ELIGIBILITY-MISSING-SYMBOL"))
            continue
        if not category_raw and _is_jpx_nisa_growth_list_row(raw_row):
            category_raw = "成長投資枠"
        if not category_raw and not growth_raw and not tsumitate_raw:
            skipped_rows.append(_skipped_row(index, symbol, "NISA-ELIGIBILITY-MISSING-FLAGS"))
            continue

        category, growth_eligible, tsumitate_eligible = _nisa_category_and_flags(
            category_raw,
            growth_raw,
            tsumitate_raw,
        )
        output_rows.append(
            {
                "symbol": symbol,
                "nisa_category": category,
                "nisa_growth_eligible": growth_eligible,
                "nisa_tsumitate_eligible": tsumitate_eligible,
            }
        )

    manifest = _source_build_manifest(
        source_kind="nisa_eligibility",
        as_of=as_of,
        raw_rows=raw_rows,
        output_rows=output_rows,
        skipped_rows=skipped_rows,
        fieldnames=NISA_ELIGIBILITY_SOURCE_FIELDNAMES,
    )
    return SymbolUniverseSourceBuildResult(rows=output_rows, manifest=manifest)


def _first_value(row: Mapping[str, Any], aliases: Sequence[str]) -> str:
    normalized_by_key = {str(key).strip().lower(): value for key, value in row.items()}
    for alias in aliases:
        value = normalized_by_key.get(alias.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _is_jpx_nisa_growth_list_row(row: Mapping[str, Any]) -> bool:
    """Detect JPX growth-NISA list rows that imply growth eligibility."""

    return bool(_first_value(row, _JPX_NISA_GROWTH_LIST_MARKER_ALIASES))


def _normalize_jpx_code(value: str) -> str:
    text = value.strip().upper()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    text = text.replace(".T", "")
    if not _JPX_CODE_PATTERN.match(text):
        text = re.split(r"\s|　|（|\(|<", text, maxsplit=1)[0]
    return text if _JPX_CODE_PATTERN.match(text) else ""


def _normalize_us_symbol(value: str) -> str:
    text = value.strip().upper().replace("$", "")
    if not text:
        return ""
    text = text.split()[0]
    text = {
        "BRKA": "BRK-A",
        "BRKB": "BRK-B",
        "UHALB": "UHAL-B",
    }.get(text, text)
    text = text.replace(".", "-").replace("/", "-")
    return text if _US_SYMBOL_PATTERN.match(text) else ""


def _normalize_foreign_symbol(value: str) -> str:
    text = value.strip().upper().replace("$", "")
    if not text:
        return ""
    text = text.split()[0]
    text = text.replace(" ", "").replace("　", "")
    return re.sub(r"[^0-9A-Z-]", "", text)


def _foreign_stock_defaults(profile: str) -> dict[str, str]:
    defaults = {
        "sbi_hk_stock": {
            "market": "hong_kong",
            "currency": "HKD",
            "country": "Hong Kong",
            "exchange": "HKEX",
            "foreign_market_group": "china_hk",
            "country_risk_band": "MEDIUM",
            "fx_pair_to_jpy": "HKDJPY",
            "yahoo_suffix": ".HK",
        },
        "sbi_korea_stock": {
            "market": "korea",
            "currency": "KRW",
            "country": "South Korea",
            "exchange": "KRX",
            "foreign_market_group": "korea",
            "country_risk_band": "MEDIUM",
            "fx_pair_to_jpy": "KRWJPY",
            "yahoo_suffix": ".KS",
        },
        "sbi_vietnam_stock": {
            "market": "vietnam",
            "currency": "VND",
            "country": "Vietnam",
            "exchange": "HOSE",
            "foreign_market_group": "asean",
            "country_risk_band": "HIGH",
            "fx_pair_to_jpy": "VNDJPY",
            "yahoo_suffix": ".VN",
        },
        "sbi_indonesia_stock": {
            "market": "indonesia",
            "currency": "IDR",
            "country": "Indonesia",
            "exchange": "IDX",
            "foreign_market_group": "asean",
            "country_risk_band": "HIGH",
            "fx_pair_to_jpy": "IDRJPY",
            "yahoo_suffix": ".JK",
        },
        "sbi_singapore_stock": {
            "market": "singapore",
            "currency": "SGD",
            "country": "Singapore",
            "exchange": "SGX",
            "foreign_market_group": "asean",
            "country_risk_band": "MEDIUM",
            "fx_pair_to_jpy": "SGDJPY",
            "yahoo_suffix": ".SI",
        },
        "sbi_thailand_stock": {
            "market": "thailand",
            "currency": "THB",
            "country": "Thailand",
            "exchange": "SET",
            "foreign_market_group": "asean",
            "country_risk_band": "HIGH",
            "fx_pair_to_jpy": "THBJPY",
            "yahoo_suffix": ".BK",
        },
        "sbi_malaysia_stock": {
            "market": "malaysia",
            "currency": "MYR",
            "country": "Malaysia",
            "exchange": "BURSA",
            "foreign_market_group": "asean",
            "country_risk_band": "MEDIUM",
            "fx_pair_to_jpy": "MYRJPY",
            "yahoo_suffix": ".KL",
        },
    }
    return defaults[profile]


def _normalize_nisa_symbol(value: str) -> str:
    text = value.strip().upper()
    if text.isdigit() and len(text) == 5 and text.endswith("0"):
        text = text[:4]
    jpx_code = _normalize_jpx_code(text)
    if jpx_code and (text.endswith(".T") or any(character.isdigit() for character in jpx_code)):
        return f"{jpx_code}.T"
    return _normalize_us_symbol(value)


def _is_jpx_listed_stock(code: str, name: str, market_segment: str) -> bool:
    if not _JPX_CODE_PATTERN.match(code):
        return False
    combined_text = f"{name} {market_segment}".upper()
    if any(marker.upper() in combined_text for marker in _JPX_NON_STOCK_MARKERS):
        return False
    if market_segment and not any(marker in market_segment for marker in _JPX_STOCK_MARKET_MARKERS):
        return False
    return True


def _is_jpx_etf_or_etn(code: str, name: str, market_segment: str) -> bool:
    if not _JPX_CODE_PATTERN.match(code):
        return False
    combined_text = f"{name} {market_segment}".upper()
    return any(marker.upper() in combined_text for marker in _JPX_ETF_MARKERS)


def _is_jpx_etf_issue_table_row(row: Mapping[str, Any], index_text: str) -> bool:
    return bool(index_text and _first_value(row, _EXPENSE_RATIO_ALIASES))


def _is_jpx_reit_issue(name: str) -> bool:
    return "投資法人" in name or any(marker in name.upper() for marker in _REIT_MARKERS)


def _theme_sector_for_industry(industry_33: str, industry_17: str) -> tuple[str, str]:
    for industry in (industry_33, industry_17):
        if industry in _INDUSTRY_THEME_SECTOR_MAP:
            return _INDUSTRY_THEME_SECTOR_MAP[industry]
    return "balanced", "industrial"


def _theme_sector_for_jpx_etf(name: str, index_text: str) -> tuple[str, str]:
    combined_text = f"{name} {index_text}".upper()
    if any(marker in combined_text for marker in _COMMODITY_MARKERS):
        return "commodity", "index"
    if any(marker in combined_text for marker in _REIT_MARKERS):
        return "reit", "real_estate"
    return "index", "index"


def _theme_sector_for_us_sector(sector: str) -> tuple[str, str]:
    normalized_sector = sector.strip().lower()
    if normalized_sector in _US_SECTOR_THEME_SECTOR_MAP:
        return _US_SECTOR_THEME_SECTOR_MAP[normalized_sector]
    for marker, mapped in _US_SECTOR_THEME_SECTOR_MAP.items():
        if marker and marker in normalized_sector:
            return mapped
    return "balanced", "industrial"


def _tag_for_theme_sector(theme: str, sector: str) -> str:
    if theme in {"healthcare", "semiconductor", "technology"}:
        return "growth"
    if theme in {"energy", "financial", "telecom", "trading"} or sector == "utilities":
        return "dividend"
    if sector == "materials":
        return "value"
    return "balanced"


def _market_cap_tier_for_jpx_scale(scale_category: str) -> str:
    normalized_scale = scale_category.strip().lower().replace(" ", "")
    if "core30" in normalized_scale:
        return "mega"
    if "large70" in normalized_scale:
        return "large"
    if "mid400" in normalized_scale:
        return "mid"
    if "small" in normalized_scale:
        return "small"
    return ""


def _normalize_percent(value: str) -> str:
    text = value.strip().replace("%", "").replace(",", "")
    match = re.search(r"[0-9]+(?:\.[0-9]+)?", text)
    if match:
        return match.group(0)
    return text


def _index_family_for_text(index_text: str, name: str) -> str:
    combined_text = f"{index_text} {name}".upper()
    for index_family, markers in _INDEX_FAMILY_KEYWORDS.items():
        if any(marker in combined_text for marker in markers):
            return index_family
    return ""


def infer_index_family_for_text(index_text: str, name: str) -> str:
    """Infer the ranking UI index family from official index/name text."""

    return _index_family_for_text(index_text, name)


def _complexity_for_etf(row: Mapping[str, Any], name: str) -> str:
    explicit_value = _first_value(row, _COMPLEXITY_ALIASES).strip().lower()
    if explicit_value:
        return explicit_value
    name_upper = name.upper()
    if any(marker in name_upper for marker in _ETN_MARKERS):
        return "etn"
    if _name_has_inverse_marker(name_upper):
        return "inverse"
    if _name_has_leveraged_marker(name_upper):
        return "leveraged"
    return "beginner"


def _flag_for_etf(
    row: Mapping[str, Any],
    aliases: Sequence[str],
    name: str,
    name_markers: Sequence[str],
) -> str:
    explicit_value = _first_value(row, aliases).strip().lower()
    if explicit_value in {"true", "1", "yes", "y", "あり", "有"}:
        return "true"
    if explicit_value in {"false", "0", "no", "n", "なし", "無"}:
        return "false"
    name_upper = name.upper()
    return "true" if _name_has_any_etf_marker(name_upper, name_markers) else "false"


def infer_etf_leveraged_for_text(name: str) -> bool:
    """Return whether ETF name text indicates a leveraged product."""

    return _name_has_leveraged_marker(name.upper())


def infer_etf_inverse_for_text(name: str) -> bool:
    """Return whether ETF name text indicates an inverse product."""

    return _name_has_inverse_marker(name.upper())


def _name_has_any_etf_marker(name_upper: str, markers: Sequence[str]) -> bool:
    if markers == _LEVERAGED_MARKERS:
        return _name_has_leveraged_marker(name_upper)
    if markers == _INVERSE_MARKERS:
        return _name_has_inverse_marker(name_upper)
    return any(marker in name_upper for marker in markers)


def _name_has_leveraged_marker(name_upper: str) -> bool:
    return any(marker in name_upper for marker in _LEVERAGED_MARKERS) or any(
        pattern.search(name_upper) for pattern in _LEVERAGED_PATTERNS
    )


def _name_has_inverse_marker(name_upper: str) -> bool:
    return any(marker in name_upper for marker in _INVERSE_MARKERS)


def _tags_for_etf(complexity: str) -> str:
    if complexity in {"leveraged", "inverse", "etn", "advanced"}:
        return ""
    return "low_cost"


def _tags_for_jpx_etf(theme: str, complexity: str, name: str) -> str:
    if complexity in {"leveraged", "inverse", "etn", "advanced"}:
        return ""
    if theme == "commodity":
        return "balanced"
    if "高配当" in name or "HIGH DIVIDEND" in name.upper():
        return "dividend,balanced"
    if "NASDAQ" in name.upper():
        return "growth"
    return "low_cost,balanced"


def _nisa_category_for_sbi_growth_column(value: str) -> str:
    if not value.strip():
        return ""
    growth_eligible = _normalize_nisa_bool(value)
    if growth_eligible == "true":
        return "growth"
    if growth_eligible == "false":
        return "none"
    return "unknown"


def _nisa_category_and_flags(
    category_raw: str,
    growth_raw: str,
    tsumitate_raw: str,
) -> tuple[str, str, str]:
    category = _normalize_nisa_category(category_raw)
    growth_eligible = _normalize_nisa_bool(growth_raw)
    tsumitate_eligible = _normalize_nisa_bool(tsumitate_raw)

    if category and category != "unknown":
        inferred_growth, inferred_tsumitate = _nisa_flags_from_category(category)
        if growth_eligible == "unknown":
            growth_eligible = inferred_growth
        if tsumitate_eligible == "unknown":
            tsumitate_eligible = inferred_tsumitate

    if not category:
        category = _nisa_category_from_flags(growth_eligible, tsumitate_eligible)
    if not category:
        category = "unknown"
    return category, growth_eligible, tsumitate_eligible


def _normalize_nisa_category(value: str) -> str:
    text = _normalized_decision_text(value)
    if not text:
        return ""
    if text in {"unknown", "不明"}:
        return "unknown"
    if text in {"none", "対象外", "非対象", "不可", "対象外含む"} or "noteligible" in text:
        return "none"
    has_growth = "growth" in text or "成長" in text
    has_tsumitate = "tsumitate" in text or "つみたて" in text or "積立" in text
    if "both" in text or (has_growth and has_tsumitate):
        return "both"
    if has_growth:
        return "growth"
    if has_tsumitate:
        return "tsumitate"
    if text in {"nisa対象", "対象", "eligible", "true", "yes", "○", "〇"}:
        return "unknown"
    return "unknown"


def _normalize_nisa_bool(value: str) -> str:
    text = _normalized_decision_text(value)
    if not text:
        return "unknown"
    if text in {"true", "1", "yes", "y", "eligible", "対象", "○", "〇", "あり", "有"}:
        return "true"
    if text in {"false", "0", "no", "n", "対象外", "非対象", "×", "なし", "無"}:
        return "false"
    if text in {"unknown", "不明"}:
        return "unknown"
    if "noteligible" in text:
        return "false"
    if "対象外" in text or "非対象" in text:
        return "false"
    if "対象" in text or "eligible" in text:
        return "true"
    return "unknown"


def _nisa_flags_from_category(category: str) -> tuple[str, str]:
    if category == "growth":
        return "true", "false"
    if category == "tsumitate":
        return "false", "true"
    if category == "both":
        return "true", "true"
    if category == "none":
        return "false", "false"
    return "unknown", "unknown"


def _nisa_category_from_flags(growth_eligible: str, tsumitate_eligible: str) -> str:
    if growth_eligible == "true" and tsumitate_eligible == "true":
        return "both"
    if growth_eligible == "true" and tsumitate_eligible == "false":
        return "growth"
    if growth_eligible == "false" and tsumitate_eligible == "true":
        return "tsumitate"
    if growth_eligible == "false" and tsumitate_eligible == "false":
        return "none"
    return "unknown"


def _normalized_decision_text(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "")
        .replace("　", "")
        .replace("/", "")
        .replace("／", "")
        .replace("・", "")
        .replace("-", "")
        .replace("_", "")
    )


def _aliases_for_jpx_row(
    name: str,
    market_segment: str,
    industry_33: str,
    industry_17: str,
) -> str:
    values = [name, market_segment, industry_33, industry_17]
    return " ".join(value for value in values if value)


def _aliases_for_values(*values: str) -> str:
    return " ".join(value for value in values if value)


def _source_build_manifest(
    *,
    source_kind: str,
    as_of: date,
    raw_rows: Sequence[Mapping[str, Any]],
    output_rows: Sequence[Mapping[str, str]],
    skipped_rows: Sequence[Mapping[str, str]],
    fieldnames: Sequence[str],
) -> dict[str, object]:
    return {
        "operation": "symbol_universe_source_build",
        "source_kind": source_kind,
        "as_of": as_of.isoformat(),
        "input_rows": len(raw_rows),
        "output_rows": len(output_rows),
        "skipped_rows": len(skipped_rows),
        "skipped": list(skipped_rows[:50]),
        "fieldnames": list(fieldnames),
    }


def _skipped_row(source_row: int, code: str, code_name: str) -> dict[str, str]:
    return {
        "source_row": str(source_row),
        "code": code,
        "reason": code_name,
    }
