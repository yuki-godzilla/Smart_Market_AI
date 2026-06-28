from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation

import streamlit as st

from backend.research import CompanyResearchReport
from ui.content.cockpit_texts import (
    COCKPIT_CARD_MEANINGS,
    COCKPIT_DECISION_VIEW_EVALUATION_TABLE,
    COCKPIT_FORECAST_RETURN_EVALUATION_TABLE,
    COCKPIT_SCORE_EVALUATION_TABLE,
)
from ui.content.score_texts import score_text_key
from ui.styles import (
    badge_html,
    metric_progress_from_value,
    render_dashboard_header,
    render_metric_card,
    render_section_heading,
)


def _display_value(value: object, fallback: str = "未取得") -> str:
    text = "" if value is None else str(value).strip()
    return text if text else fallback


def cockpit_summary_items(
    *,
    symbol: str,
    name: str,
    provider: str,
    as_of: str,
    reference_period_days: int,
    forecast_horizon_days: int,
    score_row: dict[str, str] | None,
    symbol_metadata: dict[str, str] | None,
) -> list[dict[str, str]]:
    metadata = symbol_metadata or {}
    return [
        {
            "label": "銘柄コード",
            "value": _display_value(symbol),
            "help": "分析対象の銘柄コードです。",
        },
        {
            "label": "銘柄名",
            "value": _display_value(name),
            "help": "銘柄マスタに登録されている名称です。",
        },
        {
            "label": "データ取得元",
            "value": _display_value(provider, "unknown"),
            "help": "今回の価格データ取得元です。",
        },
        {
            "label": "基準日",
            "value": _display_value(as_of),
            "help": "表示データの基準日です。",
        },
        {
            "label": "参照期間",
            "value": f"{reference_period_days}日",
            "help": "今回のチャートと評価に使っている参照期間です。",
        },
        {
            "label": "商品/地域",
            "value": " / ".join(
                part
                for part in [
                    metadata.get("asset_type", ""),
                    metadata.get("region", ""),
                    metadata.get("sector", ""),
                ]
                if part
            )
            or "未登録",
            "help": "銘柄マスタ由来の分類情報です。",
        },
        {
            "label": "投資スコア",
            "value": _display_value((score_row or {}).get("総合スコア"), "未計算"),
            "caption": _cockpit_card_caption("投資スコア", (score_row or {}).get("総合スコア")),
            "help_text": _cockpit_metric_help("投資スコア"),
        },
        {
            "label": "総合評価",
            "value": _display_value((score_row or {}).get("見方"), "未判定"),
            "caption": _cockpit_card_caption("総合評価", (score_row or {}).get("見方")),
            "help_text": _cockpit_metric_help("総合評価"),
        },
        {
            "label": "データ信頼度",
            "value": _display_value((score_row or {}).get("データ品質"), "未計算"),
            "caption": _cockpit_card_caption("データ信頼度", (score_row or {}).get("データ品質")),
            "help_text": _cockpit_metric_help("データ信頼度"),
        },
        {
            "label": "リスク確認",
            "value": _display_value((score_row or {}).get("Risk"), "未接続"),
            "caption": _cockpit_card_caption("リスク確認", (score_row or {}).get("Risk")),
            "help_text": _cockpit_metric_help("リスク確認"),
        },
        {
            "label": "予測期間",
            "value": f"{forecast_horizon_days}日",
            "help": "チャート上に表示する予測日数です。",
        },
    ]


def cockpit_kpi_cards(score_row: dict[str, str] | None) -> list[dict[str, str]]:
    row = score_row or {}
    return [
        {
            "label": "投資スコア",
            "value": _display_value(row.get("総合スコア"), "未計算"),
            "caption": _cockpit_card_caption("投資スコア", row.get("総合スコア")),
            "help_text": _cockpit_metric_help("投資スコア"),
        },
        {
            "label": "上昇気配",
            "value": _display_value(row.get("上昇気配"), "未計算"),
            "caption": _cockpit_card_caption("上昇気配", row.get("上昇気配")),
            "help_text": _cockpit_metric_help("上昇気配"),
        },
        {
            "label": "下降警戒",
            "value": _display_value(row.get("下降警戒"), "未計算"),
            "caption": _cockpit_card_caption("下降警戒", row.get("下降警戒")),
            "help_text": _cockpit_metric_help("下降警戒"),
        },
        {
            "label": "データ信頼度",
            "value": _display_value(row.get("データ品質"), "未計算"),
            "caption": _cockpit_card_caption("データ信頼度", row.get("データ品質")),
            "help_text": _cockpit_metric_help("データ信頼度"),
        },
        {
            "label": "リスク確認",
            "value": _display_value(row.get("Risk"), "未接続"),
            "caption": _cockpit_card_caption("リスク確認", row.get("Risk")),
            "help_text": _cockpit_metric_help("リスク確認"),
        },
    ]


def cockpit_direction_signal_cards(
    score_row: dict[str, str] | None,
    consensus_row: dict[str, str] | None,
) -> list[dict[str, str]]:
    """Return cockpit cards for one-symbol direction-signal review."""

    row = score_row or {}
    consensus = consensus_row or {}
    return [
        {
            "label": "上昇気配",
            "value": _display_value(
                row.get("上昇気配") or consensus.get("upside_signal_score"),
                "未計算",
            ),
            "caption": _cockpit_card_caption(
                "上昇気配",
                row.get("上昇気配") or consensus.get("upside_signal_score"),
            ),
            "help_text": _cockpit_metric_help("上昇気配"),
        },
        {
            "label": "下降警戒",
            "value": _display_value(
                row.get("下降警戒") or consensus.get("downside_signal_score"),
                "未計算",
            ),
            "caption": _cockpit_card_caption(
                "下降警戒",
                row.get("下降警戒") or consensus.get("downside_signal_score"),
            ),
            "help_text": _cockpit_metric_help("下降警戒"),
        },
        {
            "label": "予測変化率",
            "value": _display_value(
                row.get("予測変化率") or consensus.get("forecast_return_pct"),
                "未計算",
            ),
            "caption": _cockpit_card_caption(
                "予測変化率",
                row.get("予測変化率") or consensus.get("forecast_return_pct"),
            ),
            "help_text": _cockpit_metric_help("予測変化率"),
        },
    ]


def cockpit_direction_signal_detail_rows(
    score_row: dict[str, str] | None,
    consensus_row: dict[str, str] | None,
) -> list[dict[str, str]]:
    """Return detail rows explaining direction-signal inputs for cockpit."""

    row = score_row or {}
    consensus = consensus_row or {}
    upside = _display_value(row.get("上昇気配") or consensus.get("upside_signal_score"), "未計算")
    downside = _display_value(
        row.get("下降警戒") or consensus.get("downside_signal_score"),
        "未計算",
    )
    forecast_return = _display_value(
        row.get("予測変化率") or consensus.get("forecast_return_pct"),
        "未計算",
    )
    direction_match = _display_value(
        row.get("方向一致") or _direction_count_text(consensus),
        "未計算",
    )
    forecast_range = _display_value(consensus.get("forecast_range_pct"), "未計算")
    agreement = _display_value(row.get("モデル一致度") or consensus.get("agreement"), "未計算")
    overall_label, overall_check = _direction_signal_overall_reading(
        upside=upside,
        downside=downside,
        forecast_return=forecast_return,
        direction_match=direction_match,
        forecast_range=forecast_range,
        agreement=agreement,
    )
    return [
        {
            "観点": "読み取り",
            "内容": overall_label,
            "確認ポイント": overall_check,
        },
        {
            "観点": "上昇気配",
            "内容": upside,
            "確認ポイント": _direction_score_check("upside", upside, downside),
        },
        {
            "観点": "下降警戒",
            "内容": downside,
            "確認ポイント": _direction_score_check("downside", downside, upside),
        },
        {
            "観点": "予測変化率",
            "内容": forecast_return,
            "確認ポイント": _forecast_return_check(forecast_return),
        },
        {
            "観点": "モデル方向一致",
            "内容": direction_match,
            "確認ポイント": _model_direction_check(direction_match),
        },
        {
            "観点": "予測のばらつき",
            "内容": f"{forecast_range} / モデル一致度 {agreement}",
            "確認ポイント": _forecast_range_check(forecast_range, agreement),
        },
    ]


def cockpit_direction_signal_summary(
    score_row: dict[str, str] | None,
    consensus_row: dict[str, str] | None,
) -> str:
    """Return a short non-advisory direction-signal explanation."""

    row = score_row or {}
    consensus = consensus_row or {}
    upside = _decimal_display_value(row.get("上昇気配") or consensus.get("upside_signal_score"))
    downside = _decimal_display_value(row.get("下降警戒") or consensus.get("downside_signal_score"))
    forecast_return = _display_value(
        row.get("予測変化率") or consensus.get("forecast_return_pct"),
        "未計算",
    )
    forecast_return_value = _decimal_display_value(forecast_return)
    direction_match = _display_value(
        row.get("方向一致") or _direction_count_text(consensus),
        "未計算",
    )
    forecast_range = _display_value(consensus.get("forecast_range_pct"), "未計算")
    range_value = _decimal_display_value(forecast_range)
    agreement = _display_value(row.get("モデル一致度") or consensus.get("agreement"), "未計算")
    if upside is None or downside is None:
        return "方向シグナルは未計算です。価格チャート、予測レンジ、データ品質を先に確認します。"

    gap = upside - downside
    counts = _direction_counts(direction_match)
    direction_split = _direction_counts_are_split(counts)
    high_forecast_spread = range_value is not None and range_value >= Decimal("10")
    if _direction_signal_data_is_limited(upside, downside, counts, forecast_return_value):
        return (
            "方向シグナルは中立寄りで、モデル方向の材料も不足しています。"
            "上昇気配・下降警戒だけで判断せず、取得期間、データ品質、価格チャートを先に確認します。"
        )
    if upside < Decimal("45") and downside < Decimal("45"):
        return (
            f"上昇気配{_format_direction_decimal(upside)}、"
            f"下降警戒{_format_direction_decimal(downside)}で、どちらの方向材料も控えめです。"
            f"{_forecast_return_summary_clause(forecast_return, forecast_return_value)}"
            "強い方向感より、価格レンジとデータ不足の有無を確認します。"
        )
    if upside >= Decimal("65") and downside >= Decimal("65"):
        if gap > 0:
            lead = "上昇気配がやや優勢"
        elif gap < 0:
            lead = "下降警戒がやや優勢"
        else:
            lead = "上下はほぼ拮抗"
        return (
            f"上向き材料と下向き材料がどちらも強めで、今回は{lead}です。"
            f"上昇気配{_format_direction_decimal(upside)}、"
            f"下降警戒{_format_direction_decimal(downside)}なので、"
            "材料の衝突と予測レンジを分けて確認します。"
        )
    if high_forecast_spread and abs(gap) <= Decimal("12"):
        return (
            f"予測のばらつきが{forecast_range}と大きめです。"
            f"上昇気配{_format_direction_decimal(upside)}、"
            f"下降警戒{_format_direction_decimal(downside)}なので、"
            "平均予測だけで方向を読まず、上限・下限と実績チャートを分けて確認します。"
        )
    if direction_split and abs(gap) <= Decimal("12"):
        return (
            "モデル方向が分散していて、上昇・下降の材料が一方向にそろっていません。"
            f"上昇気配{_format_direction_decimal(upside)}、"
            f"下降警戒{_format_direction_decimal(downside)}です。"
            f"{_forecast_return_summary_clause(forecast_return, forecast_return_value)}"
            "1モデルだけの見方に寄せず、価格チャートと予測レンジを確認します。"
        )
    if downside >= Decimal("65") and gap <= Decimal("-12"):
        return (
            f"下降警戒が{_format_direction_decimal(downside)}と"
            f"上昇気配{_format_direction_decimal(upside)}を上回っています。"
            f"{_forecast_return_summary_clause(forecast_return, forecast_return_value)}"
            f"{_uncertainty_summary_clause(direction_match, forecast_range, range_value, agreement)}"
            "下落継続リスクと反転材料を分けて確認します。"
        )
    if upside >= Decimal("65") and gap >= Decimal("12"):
        return (
            f"上昇気配が{_format_direction_decimal(upside)}と"
            f"下降警戒{_format_direction_decimal(downside)}を上回っています。"
            f"{_forecast_return_summary_clause(forecast_return, forecast_return_value)}"
            f"{_uncertainty_summary_clause(direction_match, forecast_range, range_value, agreement)}"
            "上向き材料が価格チャートでも確認できるかを深掘りします。"
        )
    if abs(gap) <= Decimal("8"):
        return (
            f"上昇気配{_format_direction_decimal(upside)}、"
            f"下降警戒{_format_direction_decimal(downside)}で近い水準です。"
            f"{_forecast_return_summary_clause(forecast_return, forecast_return_value)}"
            "一方向に決めつけず、モデル方向一致と予測レンジを合わせて確認します。"
        )
    if gap > 0:
        return (
            f"上昇気配が{_format_direction_decimal(upside)}でやや優勢です。"
            f"{_forecast_return_summary_clause(forecast_return, forecast_return_value)}"
            "下降警戒が残っていないか、短期トレンドと予測下限を確認します。"
        )
    return (
        f"下降警戒が{_format_direction_decimal(downside)}でやや優勢です。"
        f"{_forecast_return_summary_clause(forecast_return, forecast_return_value)}"
        "上向き材料が残るか、直近トレンドと予測上限を確認します。"
    )


_DIRECTION_COUNT_PATTERN = re.compile(r"(上昇|下降|横ばい)\s*(\d+)")


def _direction_signal_overall_reading(
    *,
    upside: str,
    downside: str,
    forecast_return: str,
    direction_match: str,
    forecast_range: str,
    agreement: str,
) -> tuple[str, str]:
    upside_value = _decimal_display_value(upside)
    downside_value = _decimal_display_value(downside)
    forecast_value = _decimal_display_value(forecast_return)
    range_value = _decimal_display_value(forecast_range)
    if upside_value is None or downside_value is None:
        return (
            "未計算",
            "方向シグナルがそろっていないため、価格チャートとデータ品質を先に確認します。",
        )

    gap = upside_value - downside_value
    if upside_value >= Decimal("65") and downside_value >= Decimal("65"):
        balance = "上下材料が強め"
        check = "強い材料が同時に出ているため、予測上限・下限と直近トレンドを分けて確認します。"
    elif gap >= Decimal("12"):
        balance = "上昇気配優勢"
        check = (
            "上向き材料が価格チャート、モデル方向一致、予測レンジでも支えられているか確認します。"
        )
    elif gap <= Decimal("-12"):
        balance = "下降警戒優勢"
        check = "下落継続リスクと、反転材料がどこにあるかを分けて確認します。"
    elif abs(gap) <= Decimal("8"):
        balance = "材料が拮抗"
        check = "一方向に寄せず、予測レンジとモデル方向一致を見て深掘り順を決めます。"
    elif gap > 0:
        balance = "上昇気配やや優勢"
        check = "上向き材料が残る一方で、下降警戒や予測下限も確認します。"
    else:
        balance = "下降警戒やや優勢"
        check = "下向き材料が残る一方で、予測上限や反転材料も確認します。"

    labels = [
        balance,
        _forecast_return_label(forecast_value),
        _forecast_range_label(range_value, agreement),
    ]
    if _direction_counts_are_split(_direction_counts(direction_match)):
        labels.append("モデル方向は分散")
    return " / ".join(labels), check


def _direction_score_check(kind: str, value: str, counterpart: str) -> str:
    score = _decimal_display_value(value)
    other = _decimal_display_value(counterpart)
    if score is None:
        return "未計算です。予測レンジ、モデル方向一致、データ品質を先に確認します。"
    score_text = _format_direction_decimal(score)
    if kind == "upside":
        if score >= Decimal("75"):
            comment = f"{score_text}は強めです。上向き材料が複数要素でそろっているか確認します。"
        elif score >= Decimal("65"):
            comment = (
                f"{score_text}はやや強めです。予測変化率と直近トレンドが同じ向きか確認します。"
            )
        elif score >= Decimal("45"):
            comment = f"{score_text}は中立圏です。決め手よりもモデル方向の割れを確認します。"
        else:
            comment = (
                f"{score_text}は弱めです。上向き材料だけで深掘りせず、反転材料の有無を確認します。"
            )
        if other is not None and other - score >= Decimal("12"):
            comment += " 今回は下降警戒のほうが優勢です。"
        return comment

    if score >= Decimal("70"):
        comment = f"{score_text}は高めです。直近安値割れ、下落継続リスク、予測下限を確認します。"
    elif score >= Decimal("65"):
        comment = (
            f"{score_text}はやや高めです。価格トレンドと予測変化率が下向きにそろうか確認します。"
        )
    elif score >= Decimal("55"):
        comment = f"{score_text}は中立圏の上側です。上昇気配とのバランスを確認します。"
    elif score >= Decimal("45"):
        comment = f"{score_text}は中立圏です。下向き材料は限定的か、拮抗している状態です。"
    else:
        comment = f"{score_text}は低めです。下向き材料は相対的に抑えめです。"
    if other is not None and other - score >= Decimal("12"):
        comment += " 今回は上昇気配のほうが優勢です。"
    return comment


def _forecast_return_check(value: str) -> str:
    forecast_value = _decimal_display_value(value)
    value_text = _display_value(value, "未計算")
    if forecast_value is None:
        return "予測変化率は未計算です。平均予測、上下限、モデル別予測線を確認します。"
    if forecast_value >= Decimal("3"):
        return f"{value_text}は上向き大きめです。予測上限だけでなく下限とモデル一致も確認します。"
    if forecast_value >= Decimal("1"):
        return f"{value_text}はやや上向きです。上昇気配と価格トレンドがそろうか確認します。"
    if forecast_value > Decimal("-1"):
        return f"{value_text}はほぼ中立です。平均値よりも予測レンジとモデル方向一致を見ます。"
    if forecast_value > Decimal("-3"):
        return f"{value_text}は平均予測が直近終値を下回る状態です。下降警戒との整合を確認します。"
    return f"{value_text}は下向き大きめです。予測下限と直近トレンドを慎重に確認します。"


def _model_direction_check(value: str) -> str:
    counts = _direction_counts(value)
    if counts is None or sum(counts) == 0:
        return "モデル方向は未計算です。予測評価と価格チャートを優先して確認します。"
    up, down, flat = counts
    if _direction_counts_are_split(counts):
        return "モデル方向は割れています。1モデルだけの方向に寄せず、実績チャートと予測レンジを合わせます。"
    if up > down and up > flat:
        return "上向きモデルが多めです。上昇気配、予測変化率、直近トレンドがそろうか確認します。"
    if down > up and down > flat:
        return "下向きモデルが多めです。下降警戒、予測変化率、直近トレンドがそろうか確認します。"
    return "横ばいモデルが多めです。大きな方向より、レンジ内の振れとデータ品質を確認します。"


def _forecast_range_check(value: str, agreement: str) -> str:
    range_value = _decimal_display_value(value)
    value_text = _display_value(value, "未計算")
    if range_value is None:
        return "予測の開きは未計算です。モデル別予測線と評価サンプル数を確認します。"
    if range_value >= Decimal("10") and _agreement_is_low(agreement):
        return f"{value_text}は大きめでモデル一致度も低めです。平均値だけでなく上下限と実績チャートを確認します。"
    if range_value >= Decimal("10"):
        return (
            f"{value_text}は大きめです。上昇気配・下降警戒の解釈は控えめにし、上下限を確認します。"
        )
    if range_value >= Decimal("5"):
        return f"{value_text}はやや大きめです。平均予測だけでなくモデルごとの差を確認します。"
    return f"{value_text}は小さめです。モデル間の見方は比較的近い状態です。"


def _forecast_return_summary_clause(value_text: str, value: Decimal | None) -> str:
    display_text = _display_value(value_text, "未計算")
    if value is None:
        return f"予測変化率は{display_text}です。"
    if value >= Decimal("1"):
        return f"予測変化率は{display_text}で、平均予測は直近終値を上回っています。"
    if value <= Decimal("-1"):
        return f"予測変化率は{display_text}で、平均予測は直近終値を下回っています。"
    return f"予測変化率は{display_text}で、平均予測は直近終値に近い水準です。"


def _uncertainty_summary_clause(
    direction_match: str,
    forecast_range: str,
    range_value: Decimal | None,
    agreement: str,
) -> str:
    counts = _direction_counts(direction_match)
    direction_split = _direction_counts_are_split(counts)
    low_agreement = _agreement_is_low(agreement)
    if range_value is not None and range_value >= Decimal("10") and direction_split:
        return f"モデル方向は割れていて予測の開きも{forecast_range}と大きめなので、"
    if range_value is not None and range_value >= Decimal("10"):
        return f"予測の開きは{forecast_range}と大きめなので、"
    if direction_split or low_agreement:
        return "モデル同士の見方にばらつきがあるため、"
    return ""


def _forecast_return_label(value: Decimal | None) -> str:
    if value is None:
        return "予測変化率は未計算"
    if value >= Decimal("1"):
        return "予測は上向き"
    if value <= Decimal("-1"):
        return "予測は下向き"
    return "予測は中立"


def _forecast_range_label(value: Decimal | None, agreement: str) -> str:
    if value is None:
        return "ばらつき未計算"
    if value >= Decimal("10") or _agreement_is_low(agreement):
        return "ばらつき大きめ"
    if value >= Decimal("5"):
        return "ばらつきやや大きめ"
    return "ばらつき小さめ"


def _direction_counts(value: str) -> tuple[int, int, int] | None:
    matches = _DIRECTION_COUNT_PATTERN.findall(str(value or ""))
    if not matches:
        return None
    counts = {"上昇": 0, "下降": 0, "横ばい": 0}
    for label, count_text in matches:
        counts[label] = int(count_text)
    return counts["上昇"], counts["下降"], counts["横ばい"]


def _direction_counts_are_split(counts: tuple[int, int, int] | None) -> bool:
    if counts is None or sum(counts) == 0:
        return False
    ordered = sorted(counts, reverse=True)
    return ordered[0] == ordered[1] or ordered[0] <= 1


def _direction_signal_data_is_limited(
    upside: Decimal,
    downside: Decimal,
    counts: tuple[int, int, int] | None,
    forecast_return: Decimal | None,
) -> bool:
    counts_missing = counts is None or sum(counts) == 0
    forecast_neutral = forecast_return is None or abs(forecast_return) < Decimal("0.5")
    return (
        Decimal("48") <= upside <= Decimal("52")
        and Decimal("48") <= downside <= Decimal("52")
        and counts_missing
        and forecast_neutral
    )


def _agreement_is_low(value: str) -> bool:
    decimal_value = _decimal_display_value(value)
    if decimal_value is not None:
        return decimal_value < Decimal("50")
    text = str(value or "").strip().upper()
    return text in {"LOW", "低", "低め", "低い", "LOW AGREEMENT"}


def render_cockpit_direction_signal_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        return
    render_section_heading("03 上昇気配・下降警戒")
    st.caption(
        "ランキングと同じ上昇気配・下降警戒を、1銘柄の深掘り用に確認します。売買推奨ではありません。"
    )
    columns = st.columns(min(4, len(cards)))
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            render_metric_card(
                card["label"],
                card["value"],
                caption=_card_caption(card),
                help_text=card.get("help_text", ""),
                badges=(_badge_for_direction_card(card),),
                tone=_tone_for_direction_card(card),
                progress=_progress_for_direction_card(card),
            )


def research_evidence_summary_items(
    report: CompanyResearchReport,
) -> list[dict[str, str]]:
    positive_count = sum(
        len(point.evidence)
        for point in report.points
        if point.category in {"growth", "shareholder_return", "financial_safety"}
    )
    risk_count = sum(
        len(point.evidence)
        for point in report.points
        if point.category in {"business_risk", "confirmation_gap"}
    )
    news_count = sum(1 for evidence in report.evidence if evidence.source_type == "news")
    return [
        {
            "label": "重要ニュース",
            "value": f"{news_count}件",
            "help": "ニュース資料として確認できた根拠数です。",
        },
        {
            "label": "ポジティブ材料",
            "value": f"{positive_count}件",
            "help": "成長、株主還元、財務安全性に関係する確認材料です。",
        },
        {
            "label": "リスク材料",
            "value": f"{risk_count}件",
            "help": "事業リスクや確認不足に関係する材料です。",
        },
        {
            "label": "信頼度",
            "value": _research_confidence_label(report),
            "help": "資料数、根拠数、警告から見た確認材料としての信頼度です。",
        },
        {
            "label": "最終更新",
            "value": (
                report.data_quality.latest_document_date.isoformat()
                if report.data_quality.latest_document_date
                else "未取得"
            ),
            "help": "参照資料のうち最新の日付です。",
        },
    ]


def _research_confidence_label(report: CompanyResearchReport) -> str:
    if report.data_quality.evidence_count <= 0:
        return "低め"
    if report.data_quality.status == "OK" and not report.data_quality.warnings:
        return "高め"
    if report.data_quality.status == "WARN":
        return "中くらい"
    return "低め"


def render_cockpit_summary_header(
    items: list[dict[str, str]],
    *,
    header_action: Callable[[], None] | None = None,
) -> None:
    item_by_label = {item["label"]: item for item in items}
    symbol = _item_value(item_by_label, "銘柄コード")
    name = _item_value(item_by_label, "銘柄名")
    title = symbol if name in {"", "-", "未取得"} else f"{symbol} - {name}"
    render_dashboard_header(
        title,
        "価格・予測・スコア・根拠資料を1画面で確認する分析ビューです。表示内容は売買推奨ではありません。",
        chips=[
            ("データ取得元", _item_value(item_by_label, "データ取得元")),
            ("基準日", _item_value(item_by_label, "基準日")),
            ("期間", _item_value(item_by_label, "参照期間")),
            ("総合評価", _item_value(item_by_label, "総合評価")),
        ],
    )
    if header_action is not None:
        _action_spacer, action_col = st.columns([3.4, 1.6])
        with action_col:
            st.markdown(
                '<span class="smai-cockpit-favorite-action-anchor"></span>',
                unsafe_allow_html=True,
            )
            header_action()
    render_section_heading("01 サマリー / 銘柄コックピット")
    st.caption(
        "この画面は、選択銘柄の価格・予測・スコア・根拠資料を整理する分析ビューです。表示内容は売買推奨ではありません。"
    )
    columns = st.columns(4)
    for index, item in enumerate(items):
        with columns[index % len(columns)]:
            render_metric_card(
                item["label"],
                item["value"],
                caption=_card_caption(item),
                help_text=item.get("help_text", ""),
                badges=(_badge_for_summary_item(item),),
                tone=_tone_for_summary_item(item),
                progress=_progress_for_summary_item(item),
            )


def render_cockpit_kpi_cards(cards: list[dict[str, str]]) -> None:
    render_section_heading("主要KPI")
    st.caption("まず主要KPIで全体感をつかみ、その後に価格チャートと評価内訳を確認します。")
    columns = st.columns(min(5, len(cards)))
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            render_metric_card(
                card["label"],
                card["value"],
                caption=_card_caption(card),
                help_text=card.get("help_text", ""),
                badges=(_badge_for_kpi_card(card),),
                tone=_tone_for_kpi_card(card),
                progress=_progress_for_kpi_card(card),
            )


def render_research_evidence_summary(report: CompanyResearchReport) -> None:
    st.markdown("##### 根拠資料サマリー")
    st.caption("根拠資料はスコア算出そのものではなく、投資判断を補助する参考情報として扱います。")
    items = research_evidence_summary_items(report)
    columns = st.columns(min(5, len(items)))
    for index, item in enumerate(items):
        with columns[index % len(columns)]:
            render_metric_card(
                item["label"],
                item["value"],
                caption=item.get("help", ""),
                badges=(_badge_for_research_item(item),),
            )


def _badge_for_summary_item(item: dict[str, str]) -> str:
    label = item.get("label", "")
    value = item.get("value", "")
    if label in {"銘柄コード", "銘柄名", "データ取得元", "商品/地域"}:
        return badge_html("情報", "info")
    if label == "データ信頼度" and value not in {"-", "未計算"}:
        return badge_html("データ", "success")
    if label in {"リスク確認", "総合評価"}:
        return badge_html("確認", "caution")
    return badge_html("補足", "neutral")


def _tone_for_summary_item(item: dict[str, str]) -> str:
    label = item.get("label", "")
    if label == "投資スコア":
        return "score"
    if label == "データ信頼度":
        return "success"
    if label == "リスク確認":
        return "risk"
    if label == "予測期間":
        return "forecast"
    if label == "総合評価":
        return "caution"
    if label in {"銘柄コード", "銘柄名", "データ取得元", "商品/地域"}:
        return "info"
    return "neutral"


def _progress_for_summary_item(item: dict[str, str]) -> int | None:
    if item.get("label") in {"投資スコア", "データ信頼度", "リスク確認"}:
        return metric_progress_from_value(item.get("value"))
    return None


def _badge_for_kpi_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    value = card.get("value", "")
    if label == "データ信頼度" and value not in {"-", "未計算"}:
        return badge_html("データ", "success")
    if label in {"リスク確認", "総合評価"}:
        return badge_html("確認", "caution")
    return badge_html("分析", "info")


def _tone_for_kpi_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    if label == "投資スコア":
        return "score"
    if label == "上昇気配":
        return "forecast"
    if label == "下降警戒":
        return "risk"
    if label == "データ信頼度":
        return "success"
    if label == "リスク確認":
        return "risk"
    if label == "総合評価":
        return "caution"
    return "info"


def _progress_for_kpi_card(card: dict[str, str]) -> int | None:
    if card.get("label") in {
        "投資スコア",
        "上昇気配",
        "下降警戒",
        "データ信頼度",
        "リスク確認",
    }:
        return metric_progress_from_value(card.get("value"))
    return None


def _badge_for_direction_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    if label == "下降警戒":
        return badge_html("確認", "caution")
    if label == "上昇気配":
        return badge_html("シグナル", "info")
    return badge_html("予測", "neutral")


def _tone_for_direction_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    if label == "下降警戒":
        return "risk"
    if label == "上昇気配":
        return "forecast"
    return "info"


def _progress_for_direction_card(card: dict[str, str]) -> int | None:
    if card.get("label") in {"上昇気配", "下降警戒"}:
        return metric_progress_from_value(card.get("value"))
    return None


def _badge_for_research_item(item: dict[str, str]) -> str:
    label = item.get("label", "")
    value = item.get("value", "")
    if label == "信頼度" and value in {"高め", "High"}:
        return badge_html("信頼度高め", "success")
    if label in {"信頼度", "リスク材料"} and value not in {"0件", "-", "高め", "High"}:
        return badge_html("要確認", "caution")
    return badge_html("根拠", "info")


def _item_value(items: dict[str, dict[str, str]], label: str) -> str:
    return _display_value(items.get(label, {}).get("value"), "-")


def _card_caption(card: dict[str, str]) -> str:
    return card.get("caption") or card.get("help", "")


def _cockpit_metric_help(label: str) -> str:
    return COCKPIT_CARD_MEANINGS.get(score_text_key(label), "")


def _cockpit_card_caption(label: str, value: object) -> str:
    evaluation = _cockpit_card_evaluation(label, value)
    if not evaluation:
        return ""
    return f"今回: {evaluation}"


def _cockpit_card_evaluation(label: str, value: object) -> str:
    if label in {"総合評価", "Decision View"}:
        text = _display_value(value, "未判定")
        return COCKPIT_DECISION_VIEW_EVALUATION_TABLE.get(
            text,
            "確認レベルの目安です。売買指示ではありません。",
        )
    score = _decimal_display_value(value)
    if score is None:
        return "未計算です。データ取得後に読み取りを確認します。"
    if label == "予測変化率":
        return _score_comment(score, COCKPIT_FORECAST_RETURN_EVALUATION_TABLE)
    return _score_comment(score, COCKPIT_SCORE_EVALUATION_TABLE.get(score_text_key(label), ()))


def _score_comment(
    score: Decimal,
    table: tuple[tuple[Decimal, str], ...],
) -> str:
    for threshold, comment in table:
        if score >= threshold:
            return comment
    return "値の読み取りは詳細表で確認します。"


def _direction_count_text(row: dict[str, str]) -> str:
    up = row.get("up_model_count", "")
    down = row.get("down_model_count", "")
    flat = row.get("flat_model_count", "")
    if not any([up, down, flat]):
        return ""
    return f"上昇 {up or '0'} / 下降 {down or '0'} / 横ばい {flat or '0'}"


def _direction_label_text(value: object) -> str:
    labels = {
        "STRONG_UPSIDE": "強い上昇気配",
        "MODERATE_UPSIDE": "上昇気配あり",
        "NEUTRAL": "中立",
        "MODERATE_DOWNSIDE": "下降警戒",
        "STRONG_DOWNSIDE": "強い下降警戒",
        "UNKNOWN": "方向データ不足",
    }
    text = str(value or "").strip()
    return labels.get(text, text)


def _decimal_display_value(value: object) -> Decimal | None:
    text = "" if value is None else str(value).replace("%", "").replace(",", "").strip()
    if not text or text in {"-", "未接続", "未登録", "未計算"}:
        return None
    try:
        decimal_value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _format_direction_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.1'))}".rstrip("0").rstrip(".")
