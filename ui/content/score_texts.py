from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreText:
    label: str
    description: str
    short_label: str | None = None


SCORE_TEXTS = {
    "investment_score": ScoreText(
        label="投資スコア",
        short_label="総合スコア",
        description="スコア・予測・リスク・根拠をまとめた比較の目安です。",
    ),
    "decision_view": ScoreText(
        label="総合評価",
        short_label="評価",
        description="総合スコアをひと目で読むためのラベルです。内訳も見比べます。",
    ),
    "upside_signal_score": ScoreText(
        label="上昇気配",
        short_label="上向きシグナル",
        description="予測、直近の勢い、トレンドを合わせた上向きの目安です。",
    ),
    "downside_signal_score": ScoreText(
        label="下降警戒",
        short_label="下向きシグナル",
        description="下向き予測、直近の勢い、トレンドを合わせた警戒の目安です。",
    ),
    "forecast_return_pct": ScoreText(
        label="予測変化率",
        description="平均予測価格が直近終値からどれだけ動く見込みかを示します。",
    ),
    "data_confidence": ScoreText(
        label="データ信頼度",
        short_label="データ信頼度",
        description="評価に使えるデータがどれだけそろっているかの目安です。",
    ),
    "risk": ScoreText(
        label="リスク確認",
        description="期間内の値動きと警戒材料をまとめた目安です。",
    ),
}

SCORE_LABEL_ALIASES = {
    "Investment Score": "investment_score",
    "Decision View": "decision_view",
    "Data Confidence": "data_confidence",
    "Data Quality": "data_confidence",
    "Risk": "risk",
    "見方": "decision_view",
}
SCORE_LABEL_TO_KEY = {
    **{text.label: key for key, text in SCORE_TEXTS.items()},
    **SCORE_LABEL_ALIASES,
}
SCORE_LABELS = {key: text.label for key, text in SCORE_TEXTS.items()}


def score_text_key(label_or_key: str) -> str:
    return (
        label_or_key
        if label_or_key in SCORE_TEXTS
        else SCORE_LABEL_TO_KEY.get(label_or_key, label_or_key)
    )
