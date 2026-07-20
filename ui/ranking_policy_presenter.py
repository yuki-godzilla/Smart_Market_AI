"""Pure presenters for Ranking policy guidance and condition summaries."""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence

from ui.ranking import (
    RANKING_PURPOSE_REVERSAL_EXPECTATION,
    ranking_period_label,
    ranking_policy_description,
    ranking_policy_label,
    ranking_weight_group_rows,
)


def reversal_expectation_component_rows() -> list[dict[str, str]]:
    return [
        {
            "評価要素": "チャート形状",
            "配点": "30%",
            "初心者向けの意味": "狙う形に近い下げ方か",
            "主な材料": "押し目の深さ、短期騰落、底打ち・安値更新",
            "計算の要点": "押し目、底打ち、横ばい上放れ、蓄積準備の最大値で形状を評価",
        },
        {
            "評価要素": "予測上向き余地",
            "配点": "25%",
            "初心者向けの意味": "今後戻る予測材料があるか",
            "主な材料": "予測変化率、上向きモデル数、高度予測",
            "計算の要点": "予測値40%・方向一致25%・高度予測等35%",
        },
        {
            "評価要素": "下落安全性",
            "配点": "20%",
            "初心者向けの意味": "下落継続の危険が強すぎないか",
            "主な材料": "下降警戒、Risk、値動きの荒さ",
            "計算の要点": "下降警戒45%・Risk35%・値動き20%",
        },
        {
            "評価要素": "押し目状態",
            "配点": "10%",
            "初心者向けの意味": "押し目として適度な深さか",
            "主な材料": "20日高値からの下落、5日騰落率",
            "計算の要点": "6〜12%下落を中心に、急落と上昇済みを減点",
        },
        {
            "評価要素": "上向き材料",
            "配点": "5%",
            "初心者向けの意味": "戻りを後押しする材料があるか",
            "主な材料": "調査・ニュース材料、予測方向、上昇余地",
            "計算の要点": "材料スコアを優先し、なければ予測情報で補完",
        },
        {
            "評価要素": "企業・データ品質",
            "配点": "10%",
            "初心者向けの意味": "企業情報と配当維持力に弱さがないか",
            "主な材料": "スクリーニング、登録情報、配当安全性",
            "計算の要点": "データ品質は魅力度に加点せず、未評価判定と確認表示に使う",
        },
    ]


def reversal_expectation_pullback_rows() -> list[dict[str, str]]:
    return [
        {"20日高値からの下落": "0%以上〜3%未満", "基礎点": "30", "読み方": "調整が浅い"},
        {"20日高値からの下落": "3%以上〜6%未満", "基礎点": "60", "読み方": "軽い押し目"},
        {"20日高値からの下落": "6%以上〜12%未満", "基礎点": "90", "読み方": "中心的な押し目"},
        {"20日高値からの下落": "12%以上〜18%未満", "基礎点": "80", "読み方": "やや深い調整"},
        {"20日高値からの下落": "18%以上〜25%未満", "基礎点": "60", "読み方": "深めの調整"},
        {"20日高値からの下落": "25%以上〜35%未満", "基礎点": "35", "読み方": "急落を警戒"},
        {"20日高値からの下落": "35%以上", "基礎点": "20", "読み方": "落ちるナイフを警戒"},
    ]


def reversal_expectation_cap_rows() -> list[dict[str, str]]:
    return [
        {
            "危険条件": "価格・時系列データ不足",
            "扱い": "未評価",
            "理由": "比較に必要な価格材料が不足",
        },
        {"危険条件": "データ品質BLOCK", "扱い": "未評価", "理由": "評価材料が不足"},
        {
            "危険条件": "下降警戒 70以上",
            "扱い": "-6〜-18点",
            "理由": "下振れ警戒が強いほど段階減点",
        },
        {"危険条件": "Risk 50未満", "扱い": "-5〜-16点", "理由": "安全確認が弱いほど段階減点"},
        {"危険条件": "5日騰落率 -5%以下", "扱い": "-6〜-18点", "理由": "足元の急落を警戒"},
        {
            "危険条件": "20日高値から25%以上下落",
            "扱い": "-6〜-14点",
            "理由": "下落幅が大きいほど警戒",
        },
        {
            "危険条件": "急落と安値割れ・下降警戒の重なり",
            "扱い": "-22〜-30点",
            "理由": "落ちるナイフ候補として強めに減点",
        },
        {
            "危険条件": "予測変化率 0%以下",
            "扱い": "-3〜-12点",
            "理由": "戻る予測根拠が弱いほど軽〜中程度に減点",
        },
        {
            "危険条件": "下落3%未満かつ5日で+3%超",
            "扱い": "-5〜-11点",
            "理由": "すでに上昇済みの追いかけ注意",
        },
        {
            "危険条件": "高配当・配当維持注意",
            "扱い": "0〜-8点",
            "理由": "基本は注意タグ。減配リスクが高い場合のみ軽く減点",
        },
        {
            "危険条件": "通常時の累積減点",
            "扱い": "最大-35点",
            "理由": "複数条件が重なっても点数の分解能を残す",
        },
        {
            "危険条件": "落ちるナイフ級の累積減点",
            "扱い": "最大-45点",
            "理由": "急落継続だけは強めに抑制",
        },
    ]


def ranking_condition_summary_chips_html(chips: Sequence[Mapping[str, str]]) -> str:
    rows = "".join(
        (
            '<span class="smai-ranking-condition-chip '
            f'smai-ranking-condition-chip--{html.escape(chip.get("tone", "neutral"))}">'
            f'{html.escape(chip.get("label", ""))}</span>'
        )
        for chip in chips
    )
    return f'<div class="smai-ranking-condition-chip-row">{rows}</div>'


def ranking_policy_builder_card_html(ranking_policy: str, weight_preset: str) -> str:
    description = ranking_policy_description(ranking_policy)
    if ranking_policy == RANKING_PURPOSE_REVERSAL_EXPECTATION:
        group_rows = [
            {"group": row["評価要素"], "weight": row["配点"]}
            for row in reversal_expectation_component_rows()
        ]
        beginner_explanation = (
            '<div class="smai-ranking-policy-beginner-note">'
            "<strong>計算の考え方</strong>"
            "<p>下がっただけでは評価せず、下の6項目を合算します。"
            "下降警戒・急落・低品質がある場合は最終スコアに上限をかけます。</p>"
            "</div>"
        )
        caution = "上位は反発の断定ではなく、下落理由と危険度を確認する候補です。"
    else:
        group_rows = ranking_weight_group_rows(weight_preset)
        beginner_explanation = ""
        caution = "上位銘柄は、まず詳しく確認したい候補として見てください。"
    group_items = "".join(
        "<span>"
        f"{html.escape(row['group'])} <strong>{html.escape(row['weight'])}</strong>"
        "</span>"
        for row in group_rows
    )
    return (
        '<section class="smai-ranking-policy-builder">'
        '<div class="smai-card-label">選択中のランキング基準</div>'
        f"<h4>{html.escape(ranking_policy_label(ranking_policy))}</h4>"
        f'<p>この基準で候補を並べます。{html.escape(description["short_summary"])}</p>'
        f"{beginner_explanation}"
        f'<div class="smai-ranking-policy-weight-chips">{group_items}</div>'
        '<p class="smai-ranking-policy-caution">'
        f"{html.escape(caution)}"
        "</p>"
        "</section>"
    )


def ranking_creation_target_summary_html(
    *,
    candidate_count: int,
    selected_count: int,
    effective_count: int,
    fetch_limit_label: str,
    ranking_policy: str,
    period_preset: str,
    provider: str,
    has_detail_conditions: bool,
) -> str:
    tone = "warning" if candidate_count == 0 or effective_count == 0 else "ready"
    if candidate_count == 0:
        lead = "現在の条件では候補がありません。条件を緩めてください。"
    else:
        lead = f"候補 {candidate_count:,}件から、{effective_count:,}件を作成します。"
    detail_state = "詳細条件あり" if has_detail_conditions else "詳細条件なし"
    selection_note = f" / 選択: {selected_count:,}件" if selected_count != candidate_count else ""
    details = (
        f"ランキング基準: {ranking_policy_label(ranking_policy)} / "
        f"期間: {ranking_period_label(period_preset)} / "
        f"取得元: {provider} / "
        f"作成対象: {fetch_limit_label} / "
        f"{detail_state}"
        f"{selection_note}"
    )
    return (
        f'<div class="smai-ranking-target-summary smai-ranking-target-summary--{tone}">'
        f"<strong>{html.escape(lead)}</strong>"
        f"<span>{html.escape(details)}</span>"
        "</div>"
    )
