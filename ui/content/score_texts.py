from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreText:
    label: str
    description: str
    short_label: str | None = None


SCORE_TEXTS = {
    "investment_score": ScoreText(
        label="Investment Score",
        short_label="総合スコア",
        description="複数観点を統合した比較・分析用スコアです。",
    ),
    "decision_view": ScoreText(
        label="Decision View",
        short_label="見方",
        description="スコア帯を確認レベルに置き換えた見方です。",
    ),
    "upside_signal_score": ScoreText(
        label="上昇気配",
        short_label="上向きシグナル",
        description="予測エッジ、モデル別の上向き強度、直近モメンタム、トレンド確認を合わせた補助指標です。",
    ),
    "downside_signal_score": ScoreText(
        label="下降警戒",
        short_label="下向きシグナル",
        description="下向きの予測エッジ、モデル別の下向き強度、直近モメンタム、トレンド確認を合わせた警戒指標です。",
    ),
    "forecast_return_pct": ScoreText(
        label="予測変化率",
        description="平均予測価格が直近終値からどの程度離れているかを示します。",
    ),
    "data_confidence": ScoreText(
        label="Data Confidence",
        short_label="データ品質",
        description="投資魅力度ではなく、評価に使えるデータの充実度を示します。",
    ),
    "risk": ScoreText(
        label="Risk",
        description="取得期間の値動きや警告を整理したリスク確認材料です。",
    ),
}

SCORE_LABEL_TO_KEY = {text.label: key for key, text in SCORE_TEXTS.items()}
SCORE_LABELS = {key: text.label for key, text in SCORE_TEXTS.items()}


def score_text_key(label_or_key: str) -> str:
    return (
        label_or_key
        if label_or_key in SCORE_TEXTS
        else SCORE_LABEL_TO_KEY.get(label_or_key, label_or_key)
    )
