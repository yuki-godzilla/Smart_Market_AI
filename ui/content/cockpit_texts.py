from __future__ import annotations

from decimal import Decimal

from ui.content.score_texts import SCORE_TEXTS

COCKPIT_CARD_MEANINGS = {
    key: text.description
    for key, text in SCORE_TEXTS.items()
    if key
    in {
        "investment_score",
        "decision_view",
        "upside_signal_score",
        "downside_signal_score",
        "forecast_return_pct",
        "data_confidence",
        "risk",
    }
}

COCKPIT_SCORE_EVALUATION_TABLE = {
    "investment_score": (
        (Decimal("75"), "高め。比較候補の中で確認優先度が高い状態です。"),
        (Decimal("65"), "やや高め。内訳とリスクを見ながら深掘りしやすい状態です。"),
        (Decimal("45"), "中立圏。決め手よりも内訳の偏りを確認します。"),
        (Decimal("0"), "低め。データ不足やリスク要因を先に確認します。"),
    ),
    "upside_signal_score": (
        (Decimal("75"), "強め。上向き材料が比較的そろっています。"),
        (Decimal("65"), "やや強め。モデル方向と予測変化率を確認します。"),
        (Decimal("45"), "中立圏。上向き材料は限定的または拮抗しています。"),
        (Decimal("0"), "弱め。上向き根拠は控えめに見ます。"),
    ),
    "downside_signal_score": (
        (Decimal("70"), "高め。下向き材料を先に確認します。"),
        (Decimal("55"), "やや高め。上昇気配とのバランスを確認します。"),
        (Decimal("50"), "中立圏の上側。下向き材料がやや優勢か確認します。"),
        (Decimal("45"), "中立圏。上昇・下降の材料が拮抗しています。"),
        (Decimal("0"), "低め。下降警戒は相対的に抑えめです。"),
    ),
    "data_confidence": (
        (Decimal("80"), "高め。評価に使える材料は比較的そろっています。"),
        (Decimal("60"), "標準圏。欠損や鮮度を確認しながら使います。"),
        (Decimal("40"), "やや不足。足りないデータを先に確認します。"),
        (Decimal("0"), "不足。スコア解釈はかなり控えめにします。"),
    ),
    "risk": (
        (Decimal("75"), "落ち着き。今回の期間ではリスク確認材料は比較的安定しています。"),
        (Decimal("65"), "やや落ち着き。値動きと警告を念のため確認します。"),
        (Decimal("50"), "標準圏。値動きや警告を合わせて確認します。"),
        (Decimal("0"), "確認優先。値動きの荒さや下落耐性を先に確認します。"),
    ),
}

COCKPIT_FORECAST_RETURN_EVALUATION_TABLE = (
    (Decimal("5"), "上向き大きめ。予測線と実績価格の距離を確認します。"),
    (Decimal("1"), "やや上向き。上昇気配との整合を確認します。"),
    (Decimal("-1"), "ほぼ中立。方向材料は控えめに見ます。"),
    (Decimal("-5"), "やや下向き。下降警戒との整合を確認します。"),
    (Decimal("-999"), "下向き大きめ。予測のばらつきと直近トレンドを確認します。"),
)

COCKPIT_DECISION_VIEW_EVALUATION_TABLE = {
    "強め": "強め。高スコアでも内訳と警戒材料を確認します。",
    "バランス型": "バランス型。強みと注意点を並べて確認します。",
    "比較候補": "比較候補。ほかの候補との差を確認します。",
    "注意して確認": "注意。Risk、データ品質、上昇気配・下降警戒を先に確認します。",
    "要確認": "要確認。データ不足や警告を先に見ます。",
    "未判定": "未判定。データ取得後に表示します。",
}
