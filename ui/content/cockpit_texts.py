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
        (Decimal("75"), "有望。内訳・予測・リスクを見比べます。"),
        (Decimal("65"), "やや有望。強みと警戒材料を見ます。"),
        (Decimal("45"), "中立。内訳の偏りを見ます。"),
        (Decimal("0"), "低め。データ不足と警戒材料を先に見ます。"),
    ),
    "upside_signal_score": (
        (Decimal("75"), "強め。上向き材料がそろっています。"),
        (Decimal("65"), "やや強め。モデル方向と予測変化率を見ます。"),
        (Decimal("45"), "中立。上向き材料は拮抗しています。"),
        (Decimal("0"), "弱め。上向き材料は少なめです。"),
    ),
    "downside_signal_score": (
        (Decimal("70"), "強め。下向き材料を先に見ます。"),
        (Decimal("55"), "やや強め。上昇気配と見比べます。"),
        (Decimal("50"), "中立寄り。下向き材料がやや優勢です。"),
        (Decimal("45"), "中立。上昇・下降の材料が拮抗しています。"),
        (Decimal("0"), "低め。下降警戒は小さめです。"),
    ),
    "data_confidence": (
        (Decimal("80"), "高め。評価に使える材料がそろっています。"),
        (Decimal("60"), "標準。欠損と鮮度を見ます。"),
        (Decimal("40"), "やや不足。足りないデータを先に見ます。"),
        (Decimal("0"), "不足。スコアの根拠が少なめです。"),
    ),
    "risk": (
        (Decimal("75"), "落ち着き。今回の期間では値動きは安定寄りです。"),
        (Decimal("65"), "やや落ち着き。値動きと警告を見ます。"),
        (Decimal("50"), "標準。値動きと警告を見ます。"),
        (Decimal("0"), "要注意。値動きの荒さと下落耐性を先に見ます。"),
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
