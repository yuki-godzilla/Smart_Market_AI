from __future__ import annotations

from typing import NotRequired, TypedDict


class RankingChartProfileText(TypedDict):
    title: str
    description: str
    how_to_read: tuple[str, ...]
    caution: NotRequired[str]


class RankingCriteriaGuideRow(TypedDict):
    表示: str
    使う場面: str
    読み方: str


class RankingPolicyDescription(TypedDict):
    short_summary: str
    suited_for: str
    main_focus: tuple[str, ...]
    caution: str


RANKING_REGION_LABELS = {
    "japan": "国内",
    "us": "米国",
    "china_hk": "中国/香港",
    "korea": "韓国",
    "asean": "ASEAN",
    "other_global": "その他海外",
    "all": "全体",
}
RANKING_MVP_REGION_LABELS = {
    "japan": RANKING_REGION_LABELS["japan"],
    "us": RANKING_REGION_LABELS["us"],
    "china_hk": RANKING_REGION_LABELS["china_hk"],
    "korea": RANKING_REGION_LABELS["korea"],
    "asean": RANKING_REGION_LABELS["asean"],
    "other_global": RANKING_REGION_LABELS["other_global"],
    "all": RANKING_REGION_LABELS["all"],
}

RANKING_PRODUCT_TYPE_LABELS = {
    "stock": "株式",
    "etf": "ETF",
    "all": "指定なし",
    "mutual_fund": "投信",
}
RANKING_MVP_PRODUCT_TYPE_LABELS = {
    "stock": RANKING_PRODUCT_TYPE_LABELS["stock"],
    "etf": RANKING_PRODUCT_TYPE_LABELS["etf"],
    "all": RANKING_PRODUCT_TYPE_LABELS["all"],
}

RANKING_PURPOSE_LABELS = {
    "reversal_expectation": "反転期待",
    "sort_total_score": "総合スコア順",
    "sort_dividend_yield": "配当利回り順",
    "sort_per": "PER低い順",
    "sort_pbr": "PBR低い順",
    "sort_roe": "ROE高い順",
    "sort_market_cap": "時価総額大きい順",
    "sort_volume": "出来高多い順",
    "sort_volatility": "値動き小さい順",
    "sort_risk": "リスク確認しやすい順",
    "sort_data_quality": "データ信頼度順",
    "multi_factor": "総合マルチファクター",
    "upside_signal": "上昇気配重視",
    "momentum": "モメンタム・トレンド",
    "quality_growth": "成長クオリティ",
    "quality_value": "割安クオリティ",
    "sustainable_income": "高配当の持続性",
    "min_volatility": "低ボラ・安定",
    "risk_adjusted": "安定成長",
    "small_growth": "小型・成長探索",
    "nisa_long_term": "NISA長期適合",
    "data_confidence": "データ信頼度優先",
    "etf_core_cost": "ETF低コスト・コア",
    "etf_income": "ETFインカム・分散",
    "dividend": "配当重視",
    "growth": "成長重視",
    "value": "割安重視",
    "stability": "安定重視",
    "trend": "トレンド重視",
}

RANKING_WEIGHT_PRESET_LABELS = {
    "reversal_expectation_profile": "反転期待",
    "sort_total_score": "総合スコア順",
    "sort_dividend_yield": "配当利回り順",
    "sort_per": "PER低い順",
    "sort_pbr": "PBR低い順",
    "sort_roe": "ROE高い順",
    "sort_market_cap": "時価総額大きい順",
    "sort_volume": "出来高多い順",
    "sort_volatility": "値動き小さい順",
    "sort_risk": "リスク確認しやすい順",
    "sort_data_quality": "データ信頼度順",
    "balanced": "総合バランス",
    "forecast": "上昇気配重視",
    "quality": "データ信頼度重視",
    "risk": "リスク控えめ",
    "income": "配当・インカム重視",
    "growth_profile": "成長性重視",
    "value_profile": "割安性重視",
    "stability_profile": "安定性重視",
    "trend_profile": "トレンド重視",
    "upside_signal_profile": "上昇気配重視",
    "multi_factor_profile": "総合マルチファクター",
    "quality_growth_profile": "成長クオリティ",
    "quality_value_profile": "割安クオリティ",
    "sustainable_income_profile": "高配当の持続性",
    "min_volatility_profile": "低ボラ・安定",
    "momentum_profile": "モメンタム・トレンド",
    "risk_adjusted_profile": "安定成長",
    "small_growth_profile": "小型・成長探索",
    "nisa_long_term_profile": "NISA長期適合",
    "data_confidence_profile": "データ信頼度優先",
    "etf_core_cost_profile": "ETF低コスト・コア",
    "etf_income_profile": "ETFインカム・分散",
}

RANKING_FETCH_LIMIT_LABELS = {
    "fast_100": "高速: 上位100件",
    "balanced_300": "標準: 上位300件",
    "broad_800": "広め: 上位800件",
    "all": "全件取得",
}

RANKING_PERIOD_LABELS = {
    "short": "短期: 1か月",
    "standard": "標準: 3か月",
    "medium": "中期: 6か月",
    "long": "長期: 1年",
    "long_3y": "長期: 3年",
    "long_5y": "長期: 5年",
}

RANKING_MARKET_LABELS = {"all": "すべて", "jp": "日本株", "us": "米国株", "etf": "ETF"}
RANKING_ASSET_TYPE_LABELS = {"all": "すべて", "stock": "個別株", "etf": "ETF"}
RANKING_CURRENCY_LABELS = {
    "all": "すべて",
    "JPY": "JPY",
    "USD": "USD",
    "HKD": "HKD",
    "KRW": "KRW",
    "VND": "VND",
    "IDR": "IDR",
    "SGD": "SGD",
    "THB": "THB",
    "MYR": "MYR",
    "CNY": "CNY",
}
RANKING_DIVIDEND_LABELS = {
    "all": "指定なし",
    "high_dividend": "配当利回り 3%以上",
    "dividend": "配当利回り 0%超〜3%未満",
    "none": "配当利回り 0%",
    "growth_dividend": "連続増配候補（metadata指定・利回り条件なし）",
}
RANKING_COMPLEXITY_LABELS = {
    "beginner": "初心者向け",
    "standard": "標準まで",
    "all": "上級者向けも含める",
}
RANKING_THEME_LABELS = {
    "all": "指定なし",
    "balanced": "分散/その他",
    "technology": "テクノロジー",
    "telecom": "通信（旧分類）",
    "communication": "通信・メディア",
    "semiconductor": "半導体",
    "financial": "金融",
    "consumer": "消費財・サービス",
    "healthcare": "ヘルスケア",
    "energy": "エネルギー",
    "automotive": "自動車",
    "trading": "商社",
    "industrial": "工業・資本財",
    "materials": "素材",
    "real_estate": "不動産",
    "utilities": "公益",
    "index": "インデックスETF",
    "bond": "債券",
    "reit": "REIT",
    "commodity": "コモディティ",
}
RANKING_OFFICIAL_SECTOR_LABELS = {
    "all": "指定なし",
    "technology": "大分類: 情報技術",
    "communication": "大分類: 通信・メディア",
    "consumer": "大分類: 消費関連",
    "financial": "大分類: 金融",
    "healthcare": "大分類: ヘルスケア",
    "energy": "大分類: エネルギー",
    "industrial": "大分類: 工業・資本財",
    "materials": "大分類: 素材",
    "real_estate": "大分類: 不動産",
    "utilities": "大分類: 公益",
    "index": "大分類: 指数・ETF",
    "水産・農林業": "JPX33: 水産・農林業",
    "鉱業": "JPX33: 鉱業",
    "建設業": "JPX33: 建設業",
    "食料品": "JPX33: 食料品",
    "繊維製品": "JPX33: 繊維製品",
    "パルプ・紙": "JPX33: パルプ・紙",
    "化学": "JPX33: 化学",
    "石油・石炭製品": "JPX33: 石油・石炭製品",
    "ゴム製品": "JPX33: ゴム製品",
    "ガラス・土石製品": "JPX33: ガラス・土石製品",
    "鉄鋼": "JPX33: 鉄鋼",
    "非鉄金属": "JPX33: 非鉄金属",
    "金属製品": "JPX33: 金属製品",
    "電気機器": "JPX33: 電気機器",
    "輸送用機器": "JPX33: 輸送用機器",
    "精密機器": "JPX33: 精密機器",
    "その他製品": "JPX33: その他製品",
    "電気・ガス業": "JPX33: 電気・ガス業",
    "陸運業": "JPX33: 陸運業",
    "海運業": "JPX33: 海運業",
    "空運業": "JPX33: 空運業",
    "倉庫・運輸関連業": "JPX33: 倉庫・運輸関連業",
    "情報・通信業": "JPX33: 情報・通信業",
    "卸売業": "JPX33: 卸売業",
    "小売業": "JPX33: 小売業",
    "銀行業": "JPX33: 銀行業",
    "証券、商品先物取引業": "JPX33: 証券・商品先物取引業",
    "保険業": "JPX33: 保険業",
    "その他金融業": "JPX33: その他金融業",
    "不動産業": "JPX33: 不動産業",
    "サービス業": "JPX33: サービス業",
    "食品": "TOPIX-17: 食品",
    "エネルギー資源": "TOPIX-17: エネルギー資源",
    "建設・資材": "TOPIX-17: 建設・資材",
    "素材・化学": "TOPIX-17: 素材・化学",
    "医薬品": "TOPIX-17: 医薬品",
    "自動車・輸送機": "TOPIX-17: 自動車・輸送機",
    "鉄鋼・非鉄": "TOPIX-17: 鉄鋼・非鉄",
    "機械": "TOPIX-17: 機械",
    "電機・精密": "TOPIX-17: 電機・精密",
    "情報通信・サービスその他": "TOPIX-17: 情報通信・サービスその他",
    "電力・ガス": "TOPIX-17: 電力・ガス",
    "運輸・物流": "TOPIX-17: 運輸・物流",
    "商社・卸売": "TOPIX-17: 商社・卸売",
    "小売": "TOPIX-17: 小売",
    "銀行": "TOPIX-17: 銀行",
    "金融（除く銀行）": "TOPIX-17: 金融（除く銀行）",
    "不動産": "TOPIX-17: 不動産",
    "Energy": "GICS: Energy",
    "Materials": "GICS: Materials",
    "Industrials": "GICS: Industrials",
    "Consumer Discretionary": "GICS: Consumer Discretionary",
    "Consumer Staples": "GICS: Consumer Staples",
    "Health Care": "GICS: Health Care",
    "Financials": "GICS: Financials",
    "Information Technology": "GICS: Information Technology",
    "Communication Services": "GICS: Communication Services",
    "Utilities": "GICS: Utilities",
    "Real Estate": "GICS: Real Estate",
}
RANKING_INVESTMENT_THEME_LABELS = {
    "all": "指定なし",
    "balanced": "分散/その他",
    "technology": "テクノロジー",
    "communication": "通信・メディア",
    "semiconductor": "半導体",
    "financial": "金融",
    "bank": "銀行",
    "insurance": "保険",
    "consumer": "消費財・サービス",
    "healthcare": "ヘルスケア",
    "energy": "エネルギー",
    "automotive": "自動車",
    "trading": "商社・卸売",
    "high_dividend": "高配当",
    "industrial": "工業・資本財",
    "materials": "素材",
    "real_estate": "不動産",
    "utilities": "公益",
    "index": "インデックスETF",
    "bond": "債券",
    "reit": "REIT",
    "commodity": "コモディティ",
    "sp500": "指数: S&P 500",
    "nasdaq100": "指数: NASDAQ 100",
    "total_us": "指数: 全米株式",
    "small_us": "指数: 米国小型株",
    "acwi": "指数: 全世界株式",
    "msci_world": "指数: 先進国株式",
    "topix": "指数: TOPIX",
    "nikkei225": "指数: 日経225",
    "jpx_nikkei400": "指数: JPX日経400",
    "dow_jones": "指数: Dow Jones",
    "emerging": "地域: 新興国",
    "china": "地域: 中国",
    "india": "地域: インド",
    "japan_equity": "地域: 日本株",
    "singapore_equity": "地域: シンガポール株",
    "dividend": "指数: 配当系",
    "single_stock": "個別株連動ETF",
    "style_factor": "スタイル/ファクター",
    "active": "アクティブ運用",
    "sector": "セクター/テーマETF",
    "currency": "通貨",
}
RANKING_MARKET_CAP_LABELS = {
    "all": "指定なし",
    "mega": "超大型（JP 10兆円以上 / US $200B以上）",
    "large": "大型（JP 1兆〜10兆円 / US $10B〜$200B）",
    "mid": "中型（JP 1,000億〜1兆円 / US $2B〜$10B）",
    "small": "小型（JP 100億〜1,000億円 / US $300M〜$2B）",
    "micro": "超小型（JP 100億円未満 / US $300M未満）",
}
RANKING_INDEX_FAMILY_LABELS = {
    "all": "指定なし",
    "sp500": "S&P 500",
    "nasdaq100": "NASDAQ 100",
    "total_us": "全米",
    "small_us": "米国小型",
    "acwi": "全世界",
    "msci_world": "先進国",
    "topix": "TOPIX",
    "nikkei225": "日経225",
    "jpx_nikkei400": "JPX日経400",
    "dow_jones": "Dow Jones",
    "emerging": "新興国",
    "china": "中国株",
    "india": "インド株",
    "singapore_equity": "シンガポール株",
    "japan_equity": "日本株",
    "dividend": "配当系指数",
    "reit": "REIT",
    "bond": "債券",
    "commodity": "コモディティ",
    "currency": "通貨",
    "single_stock": "個別株連動",
    "style_factor": "スタイル/ファクター",
    "active": "アクティブ",
    "sector": "セクター/テーマ",
}
RANKING_RISK_BAND_LABELS = {
    "all": "指定なし",
    "LOW": "低め",
    "MEDIUM": "中くらい",
    "HIGH": "高め",
}
RANKING_BETA_RISK_LABELS = {
    "all": "指定なし（値動きリスクで絞らない）",
    "low": "低めのみ",
    "standard_or_lower": "標準以下",
    "standard": "標準のみ",
    "high": "高めのみ",
}
RANKING_MANAGEMENT_STYLE_LABELS = {
    "all": "指定なし",
    "index": "インデックス",
    "active": "アクティブ",
}
RANKING_NISA_ELIGIBILITY_LABELS = {
    "all": "指定なし（NISAで絞らない）",
    "eligible": "NISA対象のみ（成長投資枠）",
    "none": "NISA対象外のみ",
}
RANKING_INSTALLMENT_LABELS = {"all": "指定なし", "true": "積立可能", "false": "積立不可"}
RANKING_DETAIL_FILTER_LABELS = {
    "industry_or_sector": "業種/テーマ",
    "official_sector": "業種・セクター（公式分類）",
    "investment_theme": "投資テーマ（SMAIタグ）",
    "market_cap": "時価総額",
    "risk_band": "値動きリスク",
    "dividend_yield": "配当利回り",
    "per": "PER",
    "pbr": "PBR",
    "roe": "ROE",
    "nisa_eligibility": "NISA",
    "benchmark_index": "連動指数",
    "expense_ratio": "信託報酬/経費率",
    "complexity": "複雑さ",
}
RANKING_SCORE_FIELD_LABELS = {
    "screening_score": "基礎評価",
    "upside_signal_score": "予測・上昇気配",
    "downside_signal_score": "下振れ警戒",
    "advanced_forecast_upside_score": "AI予測上昇",
    "advanced_forecast_downside_score": "AI下振れ警戒",
    "advanced_forecast_quality_score": "AI予測信頼度",
    "data_quality_score": "データ信頼度",
    "risk_signal_score": "リスク",
    "database_fit_score": "条件適合度",
    "metadata_confidence_score": "DB信頼度",
    "research_score": "Research確認材料",
}

RANKING_FILTER_HELP_TEXTS = {
    "industry_or_sector": (
        "業種やテーマで候補を絞ります。株式は主にsector/theme、ETFは指数・投資対象の"
        "分類を使います。"
    ),
    "official_sector": (
        "業種・セクター専用の条件です。日本株はJPXの33業種/TOPIX-17、"
        "米国株はGICS系セクター、SMAI大分類を件数付きで表示します。"
        "半導体や高配当などの投資テーマは下の投資テーマ条件で分けて扱います。"
    ),
    "investment_theme": (
        "投資テーマ専用の条件です。SMAIが銘柄名、別名、商品分類、smai_theme_tagsから"
        "半導体、自動車、高配当、債券、REITなどを整理します。"
        "JPX/GICSの公式業種とは分離して扱います。"
    ),
    "market_cap": (
        "会社の規模感です。日本株は10兆円/1兆円/1,000億円/100億円、米国株は"
        "$200B/$10B/$2B/$300Mを境目に分類します。JPX規模区分由来の行は"
        "TOPIX Core30/Large70/Mid400/Smallなどを対応させています。"
    ),
    "risk_band": (
        "値動きリスクは、取得元のbetaを低め・標準・高めの帯に整理した参考区分です。"
        "厳密なβ値そのものではなく、価格変動の確認材料として使います。"
        "将来の値動きや損失を保証するものではありません。"
    ),
    "nisa_eligibility": (
        "NISA対象/対象外で絞ります。現在のランキング対象は株式・ETF中心です。"
        "株式候補は成長投資枠対象として整理済みなので、株式でNISA対象のみを"
        "選んでも件数が変わらない場合があります。ETFは対象/対象外が混在します。"
        "制度上の候補条件であり、投資適合性や安全性を示すものではありません。"
    ),
    "benchmark_index": (
        "ETFが主に連動を目指す指数や投資対象です。S&P 500、全世界、債券などの"
        "中身の違いを確認します。"
    ),
    "expense_ratio": (
        "ETFや投信の保有コストです。長期保有では低いほど手元に残るリターンに効きやすくなります。"
    ),
    "complexity": (
        "商品の分かりやすさの目安です。標準までを選ぶと、レバレッジ型など複雑な商品を"
        "避けやすくなります。"
    ),
    "dividend_category": (
        "配当利回りの帯で候補を絞ります。0%、0%超〜3%未満、3%以上を選べます。"
        "下の配当利回り(%)をONにして細かく指定する場合、この分類条件は使いません。"
        "連続増配候補は利回りではなく、curated metadataで指定された分類です。"
        "高配当そのものを推奨とは扱わず、減配や一時要因も確認します。"
    ),
    "currency": "取引通貨で候補を絞ります。為替の影響も確認したい時に使います。",
    "dividend_yield": (
        "株価に対する年間配当の目安です。高いほど配当収入は大きく見えますが、"
        "極端に高い場合は減配や株価下落も確認します。"
    ),
    "per": (
        "利益に対して株価が何倍かを示します。低いほど割安に見えますが、"
        "成長鈍化や一時的な利益変動も確認します。"
    ),
    "pbr": (
        "純資産に対して株価が何倍かを示します。低いほど資産面では割安に見えますが、"
        "収益力もあわせて確認します。"
    ),
    "roe": (
        "自己資本でどれだけ利益を出しているかを示します。高いほど資本効率が良い目安ですが、"
        "一時的な上振れもあります。"
    ),
    "keyword": "ticker、会社名、テーマ、別名で候補を探します。",
    "period": (
        "ランキング計算に使う価格データの期間です。標準は3か月で、20日/60日系の予測材料を見やすくします。"
        "1か月は直近反応、6か月は中期トレンド、1年は安定性、3年/5年は長期トレンドの確認に使います。"
        "候補の絞り込み条件ではなく、スコア・リスク・上昇気配・下降警戒の見え方に影響します。"
    ),
}

RANKING_PURPOSE_HELP_TEXTS = {
    "sort_total_score": (
        "総合スコアが高い順に表示します。割安性・収益性・配当魅力・成長性・"
        "リスク・データ信頼度などを統合した比較用スコアで、売買推奨ではありません。"
    ),
    "sort_dividend_yield": (
        "配当利回りが高い順に表示します。高配当でも、業績・財務・減配リスクを"
        "あわせて確認してください。"
    ),
    "sort_per": (
        "PERが低い順に表示します。低PERは割安に見える一方、業績悪化や一時要因を"
        "反映している場合があります。"
    ),
    "sort_pbr": (
        "PBRが低い順に表示します。低PBRは資産面で割安に見える一方、収益性の低さや"
        "市場評価の低さを反映している場合があります。"
    ),
    "sort_roe": (
        "ROEが高い順に表示します。資本効率の高さを示しますが、一時利益や"
        "財務レバレッジの影響も確認してください。"
    ),
    "sort_market_cap": (
        "時価総額が大きい順に表示します。企業規模や流動性の確認に使いますが、"
        "成長余地や割安性とは別観点です。"
    ),
    "sort_volume": (
        "出来高が多い順に表示します。取引の活発さを確認する指標で、短期的な注目度や"
        "流動性の参考になります。"
    ),
    "sort_volatility": (
        "値動きが小さい順に表示します。安定性の確認に使えますが、値動きが小さいことが"
        "必ずしも高リターンを意味するわけではありません。"
    ),
    "sort_risk": (
        "リスク確認スコアが高い順に表示します。安定性を確認しやすい候補の"
        "参考指標で、安全を保証するものではありません。"
    ),
    "sort_data_quality": (
        "データ信頼度が高い順に表示します。欠損が少なく、取得状態が安定している候補を"
        "優先して確認できます。"
    ),
    "multi_factor": (
        "基礎評価、上昇気配・下降警戒、リスク、データ信頼度、条件適合度をバランスよく見ます。"
        "特定テーマに寄せず、まず深掘り候補を広く並べたい時の基準です。"
    ),
    "quality_growth": (
        "ROE、上昇気配、基礎評価、データ信頼度を重視します。"
        "高PER/PBRは単純減点ではなく、成長期待と価格水準の釣り合いを確認する材料として扱います。"
    ),
    "quality_value": (
        "PER/PBRの低さだけでなく、ROE、データ信頼度、リスクも合わせて見ます。"
        "割安に見える理由が業績不安やデータ不足ではないかを確認するための並べ替えです。"
    ),
    "sustainable_income": (
        "配当利回り、配当カテゴリ、リスク、PBR、データ信頼度を重視します。"
        "極端な高配当は魅力だけでなく、減配リスクの確認対象として扱います。"
    ),
    "min_volatility": (
        "リスク、β分類、データ信頼度、銘柄規模を重視します。"
        "上昇率よりも値動きの落ち着きと確認しやすさを優先する基準です。"
    ),
    "momentum": (
        "取得期間の価格評価、上昇気配・下降警戒、基礎評価を重視します。"
        "上昇基調でもリスクが目立つ候補は確認対象として扱い、追随リスクを見落としにくくします。"
    ),
    "risk_adjusted": (
        "リターンだけでなくリスク、データ信頼度、条件適合度を合わせて見ます。"
        "同じ上昇でも、値動きの荒さに対して見合うかを確認する安定成長向けの基準です。"
    ),
    "small_growth": (
        "小型・中型の成長余地、ROE、基礎評価、上昇気配を重視します。"
        "変動率や流動性の不確実性が出やすいため、リスクとDB信頼度も確認します。"
    ),
    "nisa_long_term": (
        "NISA適合、投資スタイル、リスク、データ信頼度、ROEを重視します。"
        "制度上の候補条件と長期確認のしやすさを整理する基準です。"
        "投資適合性や安全性を保証するものではありません。"
    ),
    "data_confidence": (
        "取得元情報、更新日、データ信頼度、欠損の少なさを最優先します。"
        "判断前に、まず根拠がそろった銘柄から確認したい時に使います。"
    ),
    "etf_core_cost": (
        "経費率、連動指数、複雑性、NISA適合、DB信頼度を重視します。"
        "低コスト・分散確認に寄せたETF比較条件です。万能評価や商品適合性の判定ではありません。"
    ),
    "etf_income": (
        "ETFの利回り、経費率、指数、通貨、複雑性、データ信頼度を重視します。"
        "インカム候補でもコスト、分散性、分配方針を同時に確認します。"
        "分配金の継続や商品適合性を保証するものではありません。"
    ),
    "dividend": (
        "旧来の配当重視です。配当利回りと条件適合度を中心に比較します。"
        "新しい配当評価には「高配当の持続性」も使えます。"
    ),
    "growth": (
        "旧来の成長重視です。上昇気配・下降警戒とROE寄りの条件適合度を中心に比較します。"
        "将来成長の保証ではありません。より品質を見たい場合は「成長クオリティ」を使います。"
    ),
    "value": (
        "旧来の割安重視です。PER/PBR寄りの条件適合度を中心に比較します。"
        "割安の質まで確認する場合は「割安クオリティ」を使います。"
    ),
    "stability": (
        "旧来の安定重視です。リスクとデータ信頼度を中心に比較します。"
        "より低変動に寄せる場合は「低ボラ・安定」を使います。"
    ),
    "trend": (
        "旧来のトレンド重視です。上昇気配・下降警戒と直近の価格評価を中心に比較します。"
        "外部ファクターのMomentumに近い見方は「モメンタム・トレンド」を使います。"
    ),
    "upside_signal": (
        "上昇気配、下向きシグナルの低さ、基礎評価、データ信頼度を重視します。"
        "売買の指示ではなく、短期的に深掘りする候補を整理するための基準です。"
    ),
}


RANKING_POLICY_DESCRIPTIONS: dict[str, RankingPolicyDescription] = {
    "multi_factor": {
        "short_summary": "基礎評価、予測、リスク、データ信頼度、Research確認材料を広く見る既定方針です。",
        "suited_for": "まず深掘り候補を広く並べたい時",
        "main_focus": (
            "基礎評価",
            "予測・上昇気配",
            "リスク・下振れ警戒",
            "データ信頼度",
            "Research確認材料",
        ),
        "caution": "総合点が高くても、下降警戒やデータ不足があれば先に確認します。",
    },
    "upside_signal": {
        "short_summary": "上向き材料が強く、下振れ警戒が相対的に低い候補を見つける方針です。",
        "suited_for": "短期から中期の深掘り候補を探す時",
        "main_focus": ("予測・上昇気配", "下振れ警戒", "基礎評価", "データ信頼度"),
        "caution": "上昇気配が強くても、下降警戒が高い候補は値動きの荒さを確認します。",
    },
    "reversal_expectation": {
        "short_summary": (
            "直近は下落または調整中でも、予測余地と下落安全性がある戻り候補を探す方針です。"
        ),
        "suited_for": "押し目・調整中の銘柄から深掘り候補を探す時",
        "main_focus": ("押し目状態", "予測余地", "下落安全性", "データ品質", "反転初動"),
        "caution": ("反転期待は買い推奨ではありません。下降警戒と下落理由を必ず確認してください。"),
    },
    "momentum": {
        "short_summary": "足元の価格評価と上昇気配を中心に、追随リスクも見る方針です。",
        "suited_for": "直近の勢いがある候補を比較したい時",
        "main_focus": ("価格モメンタム", "予測・上昇気配", "下振れ警戒", "リスク"),
        "caution": "勢いの強さは将来継続の保証ではないため、反転リスクを確認します。",
    },
    "quality_growth": {
        "short_summary": "成長条件と収益性を見ながら、上昇気配とデータ信頼度を確認する方針です。",
        "suited_for": "成長性と質の両方を見たい時",
        "main_focus": ("ROE", "条件適合度", "予測・上昇気配", "データ信頼度"),
        "caution": "高PER/PBRは単純減点ではなく、成長期待との釣り合いを確認します。",
    },
    "quality_value": {
        "short_summary": "割安に見える候補を、収益性・リスク・資料確認も含めて見る方針です。",
        "suited_for": "PER/PBRだけでなく割安の質を見たい時",
        "main_focus": ("条件適合度", "基礎評価", "リスク", "データ信頼度", "Research確認材料"),
        "caution": "割安の理由が業績不安や一時要因ではないか確認します。",
    },
    "sustainable_income": {
        "short_summary": "高配当候補を、持続性・リスク・データ信頼度と合わせて確認する方針です。",
        "suited_for": "配当利回りだけでなく減配リスクも見たい時",
        "main_focus": ("条件適合度", "リスク", "データ信頼度", "基礎評価", "Research確認材料"),
        "caution": "高配当は魅力だけでなく、減配や業績悪化の確認対象として扱います。",
    },
    "min_volatility": {
        "short_summary": "値動きの落ち着きと確認しやすさを優先する方針です。",
        "suited_for": "荒い値動きを避けて候補を比較したい時",
        "main_focus": ("リスク", "データ信頼度", "DB信頼度", "基礎評価", "Research確認材料"),
        "caution": "低ボラは安全保証ではなく、上昇余地が小さい場合もあります。",
    },
    "risk_adjusted": {
        "short_summary": "安定成長の候補として、上昇材料とリスク・データ信頼度の釣り合いを見る方針です。",
        "suited_for": "安定的に深掘りできる候補を探す時",
        "main_focus": ("リスク", "基礎評価", "予測・上昇気配", "条件適合度", "データ信頼度"),
        "caution": "安定成長は安全保証ではなく、下振れ警戒と個別材料を合わせて確認します。",
    },
    "small_growth": {
        "short_summary": "小型・中型の成長候補を、リスクとデータ信頼度も含めて見る方針です。",
        "suited_for": "成長余地を探しつつ不確実性も確認したい時",
        "main_focus": ("条件適合度", "基礎評価", "予測・上昇気配", "リスク", "データ信頼度"),
        "caution": "小型候補は変動率や流動性の影響が大きいため、リスク確認を省略しません。",
    },
    "nisa_long_term": {
        "short_summary": "NISA制度上の候補条件と、長期確認のしやすさを合わせて見る方針です。",
        "suited_for": "長期保有の検討材料を整理したい時",
        "main_focus": ("基礎評価", "リスク", "データ信頼度", "条件適合度", "Research確認材料"),
        "caution": "制度適合は投資適合性や安全性を保証するものではありません。",
    },
    "data_confidence": {
        "short_summary": "取得元、更新日、欠損の少なさを優先し、確認材料がそろった候補から見る方針です。",
        "suited_for": "まずデータが安定した候補を確認したい時",
        "main_focus": ("データ信頼度", "DB信頼度", "条件適合度", "基礎評価"),
        "caution": "データがそろっていることは、投資魅力度の高さそのものではありません。",
    },
    "etf_core_cost": {
        "short_summary": "低コストで中核に置きやすいETF候補を、指数・複雑性・信頼度で確認する方針です。",
        "suited_for": "ETFのコア候補を比較したい時",
        "main_focus": ("条件適合度", "データ信頼度", "リスク", "基礎評価", "Research確認材料"),
        "caution": "低コストでも、連動指数や為替、商品構造の確認が必要です。",
    },
    "etf_income": {
        "short_summary": "ETFのインカム候補を、分配材料・コスト・分散性・複雑性で確認する方針です。",
        "suited_for": "ETFの分配金候補を比較したい時",
        "main_focus": (
            "条件適合度",
            "リスク・複雑性",
            "データ信頼度",
            "基礎評価",
            "Research確認材料",
        ),
        "caution": "分配金の継続や商品適合性を保証するものではありません。",
    },
}


RANKING_CRITERIA_GUIDE_ROWS: tuple[RankingCriteriaGuideRow, ...] = (
    {
        "表示": "評価方針",
        "使う場面": "取得後の候補をどの観点で並べるかを選ぶ",
        "読み方": "売買推奨ではなく、比較・深掘り候補を整理する採点軸です。",
    },
    {
        "表示": "詳細条件",
        "使う場面": "取得前に候補 universe を絞る",
        "読み方": "対象範囲を狭める条件です。条件に合うこと自体が投資魅力度ではありません。",
    },
    {
        "表示": "条件適合度",
        "使う場面": "選択中のランキング基準にどれだけ合う材料があるかを見る",
        "読み方": "投資魅力度ではなく、目的別の確認材料がそろっているかを示す補助指標です。",
    },
    {
        "表示": "DB信頼度",
        "使う場面": "銘柄マスタや provider metadata の充実度を確認する",
        "読み方": "投資魅力度ではなく、評価に使える登録情報・取得情報の充実度です。",
    },
    {
        "表示": "NISA",
        "使う場面": "NISA対象/対象外で候補を絞る、またはNISA長期適合で確認する",
        "読み方": "制度上の候補条件です。投資適合性や安全性を示すものではありません。",
    },
    {
        "表示": "配当 / 分配金",
        "使う場面": "配当・インカム候補を絞る、または利回り順に確認する",
        "読み方": "収入材料の目安です。高利回りは推奨ではなく、減配・一時要因・価格下落も確認します。",
    },
    {
        "表示": "ETF低コスト / ETFインカム",
        "使う場面": "ETFのコスト、指数、通貨、分配方針、複雑性を比較する",
        "読み方": "目的別の比較条件です。万能評価や商品適合性の判定ではありません。",
    },
)


RANKING_CHART_PROFILE_TEXTS: dict[str, RankingChartProfileText] = {
    "score_risk": {
        "title": "スコア x リスク",
        "description": "スコアが高い候補の中で、リスクもあわせて確認できます。高スコアでもリスクが高い場合は、詳細確認に進むと安心です。",
        "how_to_read": (
            "スコア高め / リスク低め: 深掘り優先候補",
            "スコア高め / リスク高め: 強みはあるが注意して確認",
            "スコア低め / リスク低め: 安定性中心で確認",
            "スコア低め / リスク高め: 優先度低め",
        ),
    },
    "screening_risk": {
        "title": "基礎評価 x リスク",
        "description": "方向データが不足する場合でも、価格・出来高・モメンタム由来の基礎評価とリスクを分けて確認できます。",
        "how_to_read": (
            "基礎評価高め / リスク評価高め: 足元条件が強く、リスク面も比較しやすい候補",
            "基礎評価高め / リスク評価低め: 足元条件は強いが、値動きや下落耐性を確認",
            "基礎評価低め / リスク評価高め: 安定性はあるが、足元条件は弱め",
            "基礎評価低め / リスク評価低め: 優先度低め、またはデータ確認候補",
        ),
    },
    "score_forecast": {
        "title": "スコア x 上昇気配",
        "description": "スコアが高い候補について、上昇気配と下降警戒を分けて確認できます。",
        "how_to_read": (
            "スコア高め / 上昇気配高め: 上向きシグナルがある深掘り候補",
            "スコア高め / 上昇気配低め: 下降警戒や上向き材料の弱さを確認",
            "スコア低め / 上昇気配高め: 上向き材料はあるが総合点は低め",
            "スコア低め / 上昇気配低め: 優先度低め",
        ),
    },
    "score_confidence": {
        "title": "スコア x データ信頼度",
        "description": "スコアとデータの充実度を分けて確認できます。高スコアでも信頼度が低い場合はデータ確認が先です。",
        "how_to_read": (
            "スコア高め / 信頼度高め: 深掘りしやすい候補",
            "スコア高め / 信頼度低め: データ確認が必要な候補",
            "スコア低め / 信頼度高め: 評価は安定しているが総合点は低め",
            "スコア低め / 信頼度低め: 優先度低め",
        ),
        "caution": "データ信頼度は投資魅力度ではなく、評価に使えるデータの充実度を示す補助指標です。",
    },
    "dividend_stability": {
        "title": "配当 x 安定性",
        "description": "配当観点の候補について、安定性もあわせて確認できます。",
        "how_to_read": (
            "配当高め / 安定性高め: 配当観点で深掘りしやすい候補",
            "配当高め / 安定性低め: 配当の持続性を確認",
            "配当低め / 安定性高め: 安定性中心で確認",
            "配当低め / 安定性低め: 優先度低め",
        ),
    },
    "growth_momentum": {
        "title": "成長性 x モメンタム",
        "description": "成長観点の候補について、足元の勢いもあわせて確認できます。",
        "how_to_read": (
            "成長性高め / モメンタム高め: 成長観点で深掘りしやすい候補",
            "成長性高め / モメンタム低め: 直近トレンドを確認",
            "成長性低め / モメンタム高め: 短期材料を確認",
            "成長性低め / モメンタム低め: 優先度低め",
        ),
    },
    "value_risk": {
        "title": "割安性 x リスク",
        "description": "割安に見える候補について、リスクもあわせて確認できます。",
        "how_to_read": (
            "割安性高め / リスク低め: 割安観点で深掘りしやすい候補",
            "割安性高め / リスク高め: 割安理由とリスクを確認",
            "割安性低め / リスク低め: 安定性中心で確認",
            "割安性低め / リスク高め: 優先度低め",
        ),
    },
    "stability_risk": {
        "title": "安定性 x リスク",
        "description": "安定性を重視する候補について、リスクの強さもあわせて確認できます。",
        "how_to_read": (
            "安定性高め / リスク低め: 安定観点で深掘りしやすい候補",
            "安定性高め / リスク高め: リスク要因を確認",
            "安定性低め / リスク低め: データや事業特性を確認",
            "安定性低め / リスク高め: 優先度低め",
        ),
    },
    "momentum_forecast": {
        "title": "モメンタム x 上昇気配",
        "description": "足元の勢いがある候補について、上昇気配と下降警戒もあわせて確認できます。",
        "how_to_read": (
            "モメンタム高め / 上昇気配高め: トレンド観点で深掘りしやすい候補",
            "モメンタム高め / 上昇気配低め: 上昇気配と下降警戒を確認",
            "モメンタム低め / 上昇気配高め: 上向き材料はあるが足元の勢いは弱め",
            "モメンタム低め / 上昇気配低め: 優先度低め",
        ),
    },
    "long_term_confidence": {
        "title": "長期適合 x データ信頼度",
        "description": "長期で確認したい候補について、安定性とデータ充実度を分けて確認できます。",
        "how_to_read": (
            "適合度高め / 信頼度高め: 長期観点で深掘りしやすい候補",
            "適合度高め / 信頼度低め: データ充実度を確認",
            "適合度低め / 信頼度高め: 評価は安定しているが適合度は低め",
            "適合度低め / 信頼度低め: 優先度低め",
        ),
    },
    "etf_cost_score": {
        "title": "ETFコスト x スコア",
        "description": "ETF候補について、コスト観点と総合スコアを分けて確認できます。",
        "how_to_read": (
            "コスト低め / スコア高め: コア候補として深掘りしやすい候補",
            "コスト低め / スコア低め: コスト以外の観点を確認",
            "コスト高め / スコア高め: コストに見合う理由を確認",
            "コスト高め / スコア低め: 優先度低め",
        ),
    },
    "upside_downside": {
        "title": "上昇気配 x 下降警戒",
        "description": "上昇気配と下降警戒を分けて確認できます。",
        "how_to_read": (
            "上昇気配高め / 下降警戒低め: "
            "上向きシグナルが強く、警戒材料が相対的に少ない深掘り候補",
            "上昇気配高め / 下降警戒高め: 上向き材料はあるが、下降警戒も先に確認",
            "上昇気配低め / 下降警戒高め: リスク確認を優先する候補",
            "上昇気配低め / 下降警戒低め: 方向材料は限定的な比較候補",
        ),
    },
    "fit_direction": {
        "title": "条件適合 x 上昇気配",
        "description": "選択中の目的に合う候補について、上昇気配と下降警戒を確認できます。",
        "how_to_read": (
            "適合度高め / 上昇気配高め: 条件に合い、上向きシグナルもある深掘り候補",
            "適合度高め / 上昇気配低め: 条件には合うが、上昇気配や下降警戒を確認",
            "適合度低め / 上昇気配高め: 上向き材料はあるが、目的適合は低め",
            "適合度低め / 上昇気配低め: 優先度低め",
        ),
    },
    "fit_risk": {
        "title": "条件適合 x リスク",
        "description": "条件に合う候補について、リスクとデータ信頼度をあわせて確認できます。",
        "how_to_read": (
            "適合度高め / リスク評価高め: 条件に合い、リスク面も比較しやすい候補",
            "適合度高め / リスク評価低め: 条件には合うが、リスク要因を確認",
            "適合度低め / リスク評価高め: 安定性はあるが、目的適合は低め",
            "適合度低め / リスク評価低め: 優先度低め",
        ),
    },
    "confidence_quality": {
        "title": "データ信頼度 x 価格データ品質",
        "description": "データ信頼度優先で見る候補について、DB信頼度と価格データ品質を分けて確認できます。",
        "how_to_read": (
            "信頼度高め / 品質高め: 根拠と価格データがそろった確認しやすい候補",
            "信頼度高め / 品質低め: DB情報はあるが、価格データ品質を確認",
            "信頼度低め / 品質高め: 価格評価はできるが、銘柄DBや根拠を確認",
            "信頼度低め / 品質低め: 先にデータ確認が必要",
        ),
        "caution": "データ信頼度とDB信頼度は投資魅力度ではなく、評価に使えるデータの充実度です。",
    },
    "etf_fit_confidence": {
        "title": "ETF条件適合 x データ信頼度",
        "description": "ETF候補について、目的適合とデータ充実度を分けて確認できます。",
        "how_to_read": (
            "適合度高め / 信頼度高め: ETF条件に合い、確認材料もそろった候補",
            "適合度高め / 信頼度低め: 条件には合うが、指数・コスト・分配方針を確認",
            "適合度低め / 信頼度高め: データはあるが、選択目的との一致は低め",
            "適合度低め / 信頼度低め: 先にデータ確認が必要",
        ),
    },
}
