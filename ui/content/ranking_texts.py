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


RANKING_REGION_LABELS = {
    "japan": "国内",
    "us": "米国",
    "other_global": "その他海外",
    "all": "全体",
}
RANKING_MVP_REGION_LABELS = {
    "japan": RANKING_REGION_LABELS["japan"],
    "us": RANKING_REGION_LABELS["us"],
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
    "sort_total_score": "総合スコア順",
    "sort_dividend_yield": "配当利回り順",
    "sort_per": "PER低い順",
    "sort_pbr": "PBR低い順",
    "sort_roe": "ROE高い順",
    "sort_market_cap": "時価総額大きい順",
    "sort_volume": "出来高多い順",
    "sort_volatility": "値動き小さい順",
    "sort_risk": "リスク確認しやすい順",
    "sort_data_quality": "データ品質順",
    "multi_factor": "総合マルチファクター",
    "upside_signal": "上昇気配重視",
    "momentum": "モメンタム・トレンド",
    "quality_growth": "成長クオリティ",
    "quality_value": "割安クオリティ",
    "sustainable_income": "高配当の持続性",
    "min_volatility": "低ボラ・安定",
    "risk_adjusted": "リスク調整パフォーマンス",
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
    "sort_total_score": "総合スコア順",
    "sort_dividend_yield": "配当利回り順",
    "sort_per": "PER低い順",
    "sort_pbr": "PBR低い順",
    "sort_roe": "ROE高い順",
    "sort_market_cap": "時価総額大きい順",
    "sort_volume": "出来高多い順",
    "sort_volatility": "値動き小さい順",
    "sort_risk": "リスク確認しやすい順",
    "sort_data_quality": "データ品質順",
    "balanced": "総合バランス",
    "forecast": "上昇気配重視",
    "quality": "データ品質重視",
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
    "risk_adjusted_profile": "リスク調整パフォーマンス",
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
}

RANKING_MARKET_LABELS = {"all": "すべて", "jp": "日本株", "us": "米国株", "etf": "ETF"}
RANKING_ASSET_TYPE_LABELS = {"all": "すべて", "stock": "個別株", "etf": "ETF"}
RANKING_CURRENCY_LABELS = {"all": "すべて", "JPY": "JPY", "USD": "USD"}
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
    "all": "指定なし（βで絞らない）",
    "low": "低変動のみ（β < 0.8）",
    "standard_or_lower": "標準以下（β <= 1.2）",
    "standard": "標準のみ（0.8 <= β <= 1.2）",
    "high": "高変動のみ（β > 1.2）",
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
    "market_cap": "時価総額",
    "risk_band": "市場感応度（β）",
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
    "screening_score": "スクリーニング",
    "upside_signal_score": "上昇気配",
    "downside_signal_score": "下降警戒控えめ",
    "advanced_forecast_upside_score": "高度予測上昇",
    "advanced_forecast_downside_score": "高度予測警戒控えめ",
    "advanced_forecast_quality_score": "高度予測信頼",
    "data_quality_score": "データ品質",
    "risk_signal_score": "リスク確認",
    "database_fit_score": "条件適合度",
    "metadata_confidence_score": "DB信頼度",
    "research_score": "根拠資料",
}

RANKING_FILTER_HELP_TEXTS = {
    "industry_or_sector": (
        "業種やテーマで候補を絞ります。株式は主にsector/theme、ETFは指数・投資対象の"
        "分類を使います。"
    ),
    "market_cap": (
        "会社の規模感です。日本株は10兆円/1兆円/1,000億円/100億円、米国株は"
        "$200B/$10B/$2B/$300Mを境目に分類します。JPX規模区分由来の行は"
        "TOPIX Core30/Large70/Mid400/Smallなどを対応させています。"
    ),
    "risk_band": (
        "市場感応度（β）は、市場平均を1.0とした値動きの大きさの目安です。"
        "β 0.8未満は低変動、0.8〜1.2は市場並み、1.2超は高変動として扱います。"
        "SMAIでは主にYahoo metadataのbetaから分類しています。"
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
        "1か月は直近反応、6か月は中期トレンド、1年は大きな上下動を含めた安定性の確認に使います。"
        "候補の絞り込み条件ではなく、スコア・リスク確認・上昇気配・下降警戒の見え方に影響します。"
    ),
}

RANKING_PURPOSE_HELP_TEXTS = {
    "sort_total_score": (
        "総合スコアが高い順に表示します。割安性・収益性・配当魅力・成長性・"
        "リスク確認・データ品質などを統合した比較用スコアで、売買推奨ではありません。"
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
        "データ品質が高い順に表示します。欠損が少なく、取得状態が安定している候補を"
        "優先して確認できます。"
    ),
    "multi_factor": (
        "スクリーニング、上昇気配・下降警戒、リスク確認、データ品質、条件適合度をバランスよく見ます。"
        "特定テーマに寄せず、まず深掘り候補を広く並べたい時の基準です。"
    ),
    "quality_growth": (
        "ROE、上昇気配、スクリーニング、データ品質を重視します。"
        "高PER/PBRは単純減点ではなく、成長期待と価格水準の釣り合いを確認する材料として扱います。"
    ),
    "quality_value": (
        "PER/PBRの低さだけでなく、ROE、データ品質、リスク確認も合わせて見ます。"
        "割安に見える理由が業績不安やデータ不足ではないかを確認するための並べ替えです。"
    ),
    "sustainable_income": (
        "配当利回り、配当カテゴリ、リスク確認、PBR、データ品質を重視します。"
        "極端な高配当は魅力だけでなく、減配リスクの確認対象として扱います。"
    ),
    "min_volatility": (
        "リスク確認、β分類、データ品質、銘柄規模を重視します。"
        "上昇率よりも値動きの落ち着きと確認しやすさを優先する基準です。"
    ),
    "momentum": (
        "取得期間の価格評価、上昇気配・下降警戒、スクリーニングを重視します。"
        "上昇基調でもリスク確認が強い候補は確認対象として扱い、追随リスクを見落としにくくします。"
    ),
    "risk_adjusted": (
        "リターンだけでなくリスク確認、データ品質、条件適合度を合わせて見ます。"
        "同じ上昇でも、値動きの荒さに対して見合うかを確認するための基準です。"
    ),
    "small_growth": (
        "小型・中型の成長余地、ROE、スクリーニング、上昇気配を重視します。"
        "変動率や流動性の不確実性が出やすいため、リスク確認とDB信頼度も確認します。"
    ),
    "nisa_long_term": (
        "NISA適合、投資スタイル、リスク確認、データ品質、ROEを重視します。"
        "制度上の候補条件と長期確認のしやすさを整理する基準です。"
        "投資適合性や安全性を保証するものではありません。"
    ),
    "data_confidence": (
        "取得元情報、更新日、データ品質、欠損の少なさを最優先します。"
        "判断前に、まず根拠がそろった銘柄から確認したい時に使います。"
    ),
    "etf_core_cost": (
        "経費率、連動指数、複雑性、NISA適合、DB信頼度を重視します。"
        "低コスト・分散確認に寄せたETF比較条件です。万能評価や商品適合性の判定ではありません。"
    ),
    "etf_income": (
        "ETFの利回り、経費率、指数、通貨、複雑性、データ品質を重視します。"
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
        "旧来の安定重視です。リスク確認とデータ品質を中心に比較します。"
        "より低変動に寄せる場合は「低ボラ・安定」を使います。"
    ),
    "trend": (
        "旧来のトレンド重視です。上昇気配・下降警戒と直近の価格評価を中心に比較します。"
        "外部ファクターのMomentumに近い見方は「モメンタム・トレンド」を使います。"
    ),
    "upside_signal": (
        "上昇気配、下向きシグナルの低さ、スクリーニング、データ品質を重視します。"
        "売買の指示ではなく、短期的に深掘りする候補を整理するための基準です。"
    ),
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
        "使う場面": "選択中の評価方針にどれだけ合う材料があるかを見る",
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
        "title": "スコア x リスク確認",
        "description": "スコアが高い候補の中で、リスクもあわせて確認できます。高スコアでもリスクが高い場合は、詳細確認に進むと安心です。",
        "how_to_read": (
            "スコア高め / リスク低め: 深掘り優先候補",
            "スコア高め / リスク高め: 強みはあるが注意して確認",
            "スコア低め / リスク低め: 安定性中心で確認",
            "スコア低め / リスク高め: 優先度低め",
        ),
    },
    "screening_risk": {
        "title": "スクリーニング x リスク確認",
        "description": "方向データが不足する場合でも、価格・出来高・モメンタム由来のスクリーニングとリスク確認を分けて確認できます。",
        "how_to_read": (
            "スクリーニング高め / リスク確認高め: 足元条件が強く、リスク面も比較しやすい候補",
            "スクリーニング高め / リスク確認低め: 足元条件は強いが、値動きや下落耐性を確認",
            "スクリーニング低め / リスク確認高め: 安定性はあるが、足元条件は弱め",
            "スクリーニング低め / リスク確認低め: 優先度低め、またはデータ確認候補",
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
        "title": "割安性 x リスク確認",
        "description": "割安に見える候補について、リスクもあわせて確認できます。",
        "how_to_read": (
            "割安性高め / リスク低め: 割安観点で深掘りしやすい候補",
            "割安性高め / リスク高め: 割安理由とリスクを確認",
            "割安性低め / リスク低め: 安定性中心で確認",
            "割安性低め / リスク高め: 優先度低め",
        ),
    },
    "stability_risk": {
        "title": "安定性 x リスク確認",
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
            "上昇気配低め / 下降警戒高め: リスク確認候補",
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
        "title": "条件適合 x リスク確認",
        "description": "条件に合う候補について、リスク確認とデータ品質をあわせて確認できます。",
        "how_to_read": (
            "適合度高め / リスク確認高め: 条件に合い、リスク面も比較しやすい候補",
            "適合度高め / リスク確認低め: 条件には合うが、リスク要因を確認",
            "適合度低め / リスク確認高め: 安定性はあるが、目的適合は低め",
            "適合度低め / リスク確認低め: 優先度低め",
        ),
    },
    "confidence_quality": {
        "title": "データ品質 x データ信頼度",
        "description": "データ信頼度優先で見る候補について、DB信頼度と価格データ品質を分けて確認できます。",
        "how_to_read": (
            "信頼度高め / 品質高め: 根拠と価格データがそろった確認しやすい候補",
            "信頼度高め / 品質低め: DB情報はあるが、価格データ品質を確認",
            "信頼度低め / 品質高め: 価格評価はできるが、銘柄DBや根拠を確認",
            "信頼度低め / 品質低め: 先にデータ確認が必要",
        ),
        "caution": "データ品質とDB信頼度は投資魅力度ではなく、評価に使えるデータの充実度です。",
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
