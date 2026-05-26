from __future__ import annotations

from typing import NotRequired, TypedDict


class RankingChartProfileText(TypedDict):
    title: str
    description: str
    how_to_read: tuple[str, ...]
    caution: NotRequired[str]


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
    "mutual_fund": "投信",
    "all": "全体",
}
RANKING_MVP_PRODUCT_TYPE_LABELS = {
    "stock": RANKING_PRODUCT_TYPE_LABELS["stock"],
    "etf": RANKING_PRODUCT_TYPE_LABELS["etf"],
}

RANKING_PURPOSE_LABELS = {
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
    "screening_score": "Screening",
    "upside_signal_score": "上昇気配",
    "downside_signal_score": "下降警戒控えめ",
    "data_quality_score": "データ品質",
    "risk_signal_score": "Risk",
    "database_fit_score": "条件適合度",
    "metadata_confidence_score": "DB信頼度",
    "research_score": "Research",
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
        "候補の絞り込み条件ではなく、スコア・Risk・上昇気配・下降警戒の見え方に影響します。"
    ),
}

RANKING_PURPOSE_HELP_TEXTS = {
    "multi_factor": (
        "Screening、上昇気配・下降警戒、Risk、Data Quality、条件適合度をバランスよく見ます。"
        "特定テーマに寄せず、まず深掘り候補を広く並べたい時の基準です。"
    ),
    "quality_growth": (
        "ROE、上昇気配、Screening、Data Qualityを重視します。"
        "高PER/PBRは単純減点ではなく、成長期待と価格水準の釣り合いを確認する材料として扱います。"
    ),
    "quality_value": (
        "PER/PBRの低さだけでなく、ROE、Data Quality、Riskも合わせて見ます。"
        "割安に見える理由が業績不安やデータ不足ではないかを確認するための並べ替えです。"
    ),
    "sustainable_income": (
        "配当利回り、配当カテゴリ、Risk、PBR、Data Qualityを重視します。"
        "極端な高配当は魅力だけでなく、減配リスクの確認対象として扱います。"
    ),
    "min_volatility": (
        "Risk signal、β分類、Data Quality、銘柄規模を重視します。"
        "上昇率よりも値動きの落ち着きと確認しやすさを優先する基準です。"
    ),
    "momentum": (
        "取得期間の価格評価、上昇気配・下降警戒、Screeningを重視します。"
        "上昇基調でもRiskが強い候補は確認対象として扱い、追随リスクを見落としにくくします。"
    ),
    "risk_adjusted": (
        "リターンだけでなくRisk signal、Data Quality、条件適合度を合わせて見ます。"
        "同じ上昇でも、値動きの荒さに対して見合うかを確認するための基準です。"
    ),
    "small_growth": (
        "小型・中型の成長余地、ROE、Screening、上昇気配を重視します。"
        "変動率や流動性の不確実性が出やすいため、RiskとDB信頼度も確認します。"
    ),
    "nisa_long_term": (
        "NISA適合、投資スタイル、Risk、Data Quality、ROEを重視します。"
        "長期保有候補として、制度適合と事業品質を一緒に確認する基準です。"
    ),
    "data_confidence": (
        "metadata source、更新日、Data Quality、欠損の少なさを最優先します。"
        "判断前に、まず根拠がそろった銘柄から確認したい時に使います。"
    ),
    "etf_core_cost": (
        "経費率、連動指数、複雑性、NISA適合、DB信頼度を重視します。"
        "長期保有の土台になりやすいETF候補を整理する基準です。"
    ),
    "etf_income": (
        "ETFの利回り、経費率、指数、通貨、複雑性、Data Qualityを重視します。"
        "インカム候補でもコストと分散性を同時に確認します。"
    ),
    "dividend": (
        "旧来の配当重視です。配当利回りと条件適合度を中心に比較します。"
        "新しい配当評価には「高配当の持続性」も使えます。"
    ),
    "growth": (
        "旧来の成長重視です。上昇気配・下降警戒とROE寄りの条件適合度を中心に比較します。"
        "より品質を見たい場合は「成長クオリティ」を使います。"
    ),
    "value": (
        "旧来の割安重視です。PER/PBR寄りの条件適合度を中心に比較します。"
        "割安の質まで確認する場合は「割安クオリティ」を使います。"
    ),
    "stability": (
        "旧来の安定重視です。RiskとData Qualityを中心に比較します。"
        "より低変動に寄せる場合は「低ボラ・安定」を使います。"
    ),
    "trend": (
        "旧来のトレンド重視です。上昇気配・下降警戒と直近の価格評価を中心に比較します。"
        "外部ファクターのMomentumに近い見方は「モメンタム・トレンド」を使います。"
    ),
    "upside_signal": (
        "上昇気配、下向きシグナルの低さ、Screening、Data Qualityを重視します。"
        "売買の指示ではなく、短期的に深掘りする候補を整理するための基準です。"
    ),
}


RANKING_CHART_PROFILE_TEXTS: dict[str, RankingChartProfileText] = {
    "score_risk": {
        "title": "Score x Risk Map",
        "description": "スコアが高い候補の中で、リスクもあわせて確認できます。高スコアでもリスクが高い場合は、詳細確認に進むと安心です。",
        "how_to_read": (
            "High score / Low risk: 深掘り優先候補",
            "High score / High risk: 魅力はあるが注意して確認",
            "Low score / Low risk: 安定だが魅力度は低め",
            "Low score / High risk: 優先度低め",
        ),
    },
    "screening_risk": {
        "title": "Screening x Risk Map",
        "description": "方向データが不足する場合でも、価格・出来高・モメンタム由来のScreeningとRiskを分けて確認できます。",
        "how_to_read": (
            "High screening / High risk score: " "足元条件が強く、リスク面も比較しやすい候補",
            "High screening / Low risk score: 足元条件は強いが、値動きや下落耐性を確認",
            "Low screening / High risk score: 安定性はあるが、足元条件は弱め",
            "Low screening / Low risk score: 優先度低め、またはデータ確認候補",
        ),
    },
    "score_forecast": {
        "title": "Score x Upside Signal Map",
        "description": "スコアが高い候補について、上昇気配と下降警戒を分けて確認できます。",
        "how_to_read": (
            "High score / High upside: 上向きシグナルがある深掘り候補",
            "High score / Low upside: 下降警戒や上向き材料の弱さを確認",
            "Low score / High upside: 上向き材料はあるが総合点は低め",
            "Low score / Low upside: 優先度低め",
        ),
    },
    "score_confidence": {
        "title": "Score x Evaluation Confidence",
        "description": "スコアとデータの充実度を分けて確認できます。高スコアでも信頼度が低い場合はデータ確認が先です。",
        "how_to_read": (
            "High score / High confidence: 深掘りしやすい候補",
            "High score / Low confidence: データ確認が必要な候補",
            "Low score / High confidence: 評価は安定しているが総合点は低め",
            "Low score / Low confidence: 優先度低め",
        ),
        "caution": "Evaluation Confidence "
        "は投資魅力度ではなく、評価に使えるデータの充実度を示す補助指標です。",
    },
    "dividend_stability": {
        "title": "Dividend x Stability Map",
        "description": "配当観点の候補について、安定性もあわせて確認できます。",
        "how_to_read": (
            "High dividend / High stability: 配当観点で深掘りしやすい候補",
            "High dividend / Low stability: 配当の持続性を確認",
            "Low dividend / High stability: 安定性中心で確認",
            "Low dividend / Low stability: 優先度低め",
        ),
    },
    "growth_momentum": {
        "title": "Growth x Momentum Map",
        "description": "成長観点の候補について、足元の勢いもあわせて確認できます。",
        "how_to_read": (
            "High growth / High momentum: 成長観点で深掘りしやすい候補",
            "High growth / Low momentum: 直近トレンドを確認",
            "Low growth / High momentum: 短期材料を確認",
            "Low growth / Low momentum: 優先度低め",
        ),
    },
    "value_risk": {
        "title": "Valuation x Risk Map",
        "description": "割安に見える候補について、リスクもあわせて確認できます。",
        "how_to_read": (
            "High valuation / Low risk: 割安観点で深掘りしやすい候補",
            "High valuation / High risk: 割安理由とリスクを確認",
            "Low valuation / Low risk: 安定性中心で確認",
            "Low valuation / High risk: 優先度低め",
        ),
    },
    "stability_risk": {
        "title": "Stability x Risk Map",
        "description": "安定性を重視する候補について、リスクの強さもあわせて確認できます。",
        "how_to_read": (
            "High stability / Low risk: 安定観点で深掘りしやすい候補",
            "High stability / High risk: リスク要因を確認",
            "Low stability / Low risk: データや事業特性を確認",
            "Low stability / High risk: 優先度低め",
        ),
    },
    "momentum_forecast": {
        "title": "Momentum x Upside Signal Map",
        "description": "足元の勢いがある候補について、上昇気配と下降警戒もあわせて確認できます。",
        "how_to_read": (
            "High momentum / High upside: トレンド観点で深掘りしやすい候補",
            "High momentum / Low upside: 上昇気配と下降警戒を確認",
            "Low momentum / High upside: 上向き材料はあるが足元の勢いは弱め",
            "Low momentum / Low upside: 優先度低め",
        ),
    },
    "long_term_confidence": {
        "title": "Long-term Fit x Confidence Map",
        "description": "長期で確認したい候補について、安定性とデータ充実度を分けて確認できます。",
        "how_to_read": (
            "High fit / High confidence: 長期観点で深掘りしやすい候補",
            "High fit / Low confidence: データ充実度を確認",
            "Low fit / High confidence: 評価は安定しているが適合度は低め",
            "Low fit / Low confidence: 優先度低め",
        ),
    },
    "etf_cost_score": {
        "title": "ETF Cost x Score Map",
        "description": "ETF候補について、コスト観点と総合スコアを分けて確認できます。",
        "how_to_read": (
            "Low cost / High score: コア候補として深掘りしやすい候補",
            "Low cost / Low score: コスト以外の観点を確認",
            "High cost / High score: コストに見合う理由を確認",
            "High cost / Low score: 優先度低め",
        ),
    },
    "upside_downside": {
        "title": "Upside x Downside Watch Map",
        "description": "上昇気配と下降警戒を分けて確認できます。",
        "how_to_read": (
            "High upside / Low downside: "
            "上向きシグナルが強く、警戒材料が相対的に少ない深掘り候補",
            "High upside / High downside: 上向き材料はあるが、下降警戒も先に確認",
            "Low upside / High downside: リスク確認候補",
            "Low upside / Low downside: 方向材料は限定的な比較候補",
        ),
    },
    "fit_direction": {
        "title": "Fit x Upside Signal Map",
        "description": "選択中の目的に合う候補について、上昇気配と下降警戒を確認できます。",
        "how_to_read": (
            "High fit / High upside: 条件に合い、上向きシグナルもある深掘り候補",
            "High fit / Low upside: 条件には合うが、上昇気配や下降警戒を確認",
            "Low fit / High upside: 上向き材料はあるが、目的適合は低め",
            "Low fit / Low upside: 優先度低め",
        ),
    },
    "fit_risk": {
        "title": "Fit x Risk Map",
        "description": "条件に合う候補について、Riskとデータ品質をあわせて確認できます。",
        "how_to_read": (
            "High fit / High risk score: 条件に合い、Risk面も比較しやすい候補",
            "High fit / Low risk score: 条件には合うが、リスク要因を確認",
            "Low fit / High risk score: 安定性はあるが、目的適合は低め",
            "Low fit / Low risk score: 優先度低め",
        ),
    },
    "confidence_quality": {
        "title": "Data Quality x Confidence Map",
        "description": "データ信頼度優先で見る候補について、DB信頼度と価格データ品質を分けて確認できます。",
        "how_to_read": (
            "High confidence / High quality: " "根拠と価格データがそろった確認しやすい候補",
            "High confidence / Low quality: " "DB情報はあるが、価格データ品質を確認",
            "Low confidence / High quality: " "価格評価はできるが、銘柄DBや根拠を確認",
            "Low confidence / Low quality: 先にデータ確認が必要",
        ),
        "caution": "Data Quality と DB信頼度は投資魅力度ではなく、評価に使えるデータの充実度です。",
    },
    "etf_fit_confidence": {
        "title": "ETF Fit x Confidence Map",
        "description": "ETF候補について、目的適合とデータ充実度を分けて確認できます。",
        "how_to_read": (
            "High fit / High confidence: ETF条件に合い、確認材料もそろった候補",
            "High fit / Low confidence: 条件には合うが、指数・コスト・分配方針を確認",
            "Low fit / High confidence: データはあるが、選択目的との一致は低め",
            "Low fit / Low confidence: 先にデータ確認が必要",
        ),
    },
}
