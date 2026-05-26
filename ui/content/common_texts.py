from __future__ import annotations

EMPTY_TEXT = "未登録"
NOT_CALCULATED_TEXT = "未計算"
UNKNOWN_TEXT = "未確認"
OK_TEXT = "OK"
WARN_TEXT = "要確認"
CAUTION_TEXT = "注意"
NO_SYMBOL_CANDIDATE_LABEL = "条件に合う候補なし"

MARKET_DATA_PERIOD_CUSTOM = "custom"
MARKET_DATA_PERIOD_PRESETS = {
    MARKET_DATA_PERIOD_CUSTOM: "カスタム",
    "short_1w": "短期: 1週間",
    "short_1m": "短期: 1か月",
    "medium_3m": "中期: 3か月",
    "medium_6m": "中期: 6か月",
    "ytd": "年初来",
    "long_1y": "長期: 1年",
    "long_3y": "長期: 3年",
    "long_5y": "長期: 5年",
}
MARKET_DATA_PERIOD_HELP_TEXT = {
    MARKET_DATA_PERIOD_CUSTOM: "検証したい決算日、急落日、投資開始想定日に合わせて任意の期間を設定します。",
    "short_1w": "決算・ニュース・急変後の短期反応を確認します。ノイズが大きいため、売買判断の主根拠にはしません。",
    "short_1m": "直近の需給変化やモメンタムの継続性を確認します。短期材料の賞味期限を見る補助期間です。",
    "medium_3m": "四半期決算や業績修正後の評価変化を確認します。短期ノイズと中期トレンドの切り分けに使います。",
    "medium_6m": "半期程度のトレンド、押し目、下落耐性を確認します。投資テーマが市場に織り込まれているかを見ます。",
    "ytd": "年初来の市場環境に対する相対感を確認します。同じ年の地合いの中で強弱を比べる時に使います。",
    "long_1y": "直近1年の業績期待、相場循環、リスク耐性を確認します。初期レビューの基準期間として使いやすい設定です。",
    "long_3y": "複数決算期をまたぐ成長持続性と景気感応度を確認します。一時的な上振れや下振れをならして見ます。",
    "long_5y": "長期の構造変化、最大下落、回復力を確認します。長期保有の候補では必ず確認したい期間です。",
}

FORECAST_ACTUAL_LABEL = "実績価格"
MARKET_DATA_MODE_LABELS = {
    "cockpit": "銘柄コックピット",
    "ranking": "銘柄ランキング",
}

DECISION_SUPPORT_DISCLAIMER = (
    "SMAIの表示は投資判断を補助する確認材料であり、売買を推奨するものではありません。"
)

NG_INVESTMENT_ADVICE_TERMS = (
    "買い" + "推奨",
    "売り" + "推奨",
    "上がる" + "銘柄",
    "下がる" + "銘柄",
    "上昇" + "確定",
    "下落" + "確定",
    "必ず" + "上がる",
    "必ず" + "下がる",
)
