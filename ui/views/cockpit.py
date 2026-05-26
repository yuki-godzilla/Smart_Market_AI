from __future__ import annotations

from decimal import Decimal, InvalidOperation

import streamlit as st

from backend.research import CompanyResearchReport
from ui.styles import (
    badge_html,
    metric_progress_from_value,
    render_dashboard_header,
    render_metric_card,
    render_section_heading,
)

COCKPIT_CARD_MEANINGS = {
    "Investment Score": "売買判断ではなく、複数観点を統合した比較・分析用スコアです。",
    "Decision View": "売買指示ではなく、スコア帯を確認レベルに置き換えた見方です。",
    "上昇気配": "予測エッジ、モデル別の上向き強度、直近モメンタム、トレンド確認を合わせた補助指標です。",
    "下降警戒": "下向きの予測エッジ、モデル別の下向き強度、直近モメンタム、トレンド確認を合わせた警戒指標です。",
    "予測変化率": "平均予測価格が直近終値からどの程度離れているかを示します。",
    "Data Confidence": "投資魅力度ではなく、評価に使えるデータの充実度を示します。",
    "Risk": "取得期間の値動きや警告を整理したリスク確認材料です。",
}

COCKPIT_SCORE_EVALUATION_TABLE = {
    "Investment Score": (
        (Decimal("75"), "高め。比較候補の中で確認優先度が高い状態です。"),
        (Decimal("65"), "やや高め。内訳とリスクを見ながら深掘りしやすい状態です。"),
        (Decimal("45"), "中立圏。決め手よりも内訳の偏りを確認します。"),
        (Decimal("0"), "低め。データ不足やリスク要因を先に確認します。"),
    ),
    "上昇気配": (
        (Decimal("75"), "強め。上向き材料が比較的そろっています。"),
        (Decimal("65"), "やや強め。モデル方向と予測変化率を確認します。"),
        (Decimal("45"), "中立圏。上向き材料は限定的または拮抗しています。"),
        (Decimal("0"), "弱め。上向き根拠は控えめに見ます。"),
    ),
    "下降警戒": (
        (Decimal("70"), "高め。下向き材料を先に確認します。"),
        (Decimal("55"), "やや高め。上昇気配とのバランスを確認します。"),
        (Decimal("50"), "中立圏の上側。下向き材料がやや優勢か確認します。"),
        (Decimal("45"), "中立圏。上昇・下降の材料が拮抗しています。"),
        (Decimal("0"), "低め。下降警戒は相対的に抑えめです。"),
    ),
    "Data Confidence": (
        (Decimal("80"), "高め。評価に使える材料は比較的そろっています。"),
        (Decimal("60"), "標準圏。欠損や鮮度を確認しながら使います。"),
        (Decimal("40"), "やや不足。足りないデータを先に確認します。"),
        (Decimal("0"), "不足。スコア解釈はかなり控えめにします。"),
    ),
    "Risk": (
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
            "label": "Symbol",
            "value": _display_value(symbol),
            "help": "分析対象の銘柄コードです。",
        },
        {
            "label": "Name",
            "value": _display_value(name),
            "help": "銘柄マスタに登録されている名称です。",
        },
        {
            "label": "Provider",
            "value": _display_value(provider, "unknown"),
            "help": "今回の価格データ取得元です。",
        },
        {
            "label": "As of",
            "value": _display_value(as_of),
            "help": "表示データの基準日です。",
        },
        {
            "label": "Reference period",
            "value": f"{reference_period_days}日",
            "help": "今回のチャートと評価に使っている参照期間です。",
        },
        {
            "label": "Asset / Region",
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
            "label": "Investment Score",
            "value": _display_value((score_row or {}).get("総合スコア"), "未計算"),
            "caption": _cockpit_card_caption(
                "Investment Score", (score_row or {}).get("総合スコア")
            ),
            "help_text": _cockpit_metric_help("Investment Score"),
        },
        {
            "label": "Decision View",
            "value": _display_value((score_row or {}).get("見方"), "未判定"),
            "caption": _cockpit_card_caption("Decision View", (score_row or {}).get("見方")),
            "help_text": _cockpit_metric_help("Decision View"),
        },
        {
            "label": "Data Confidence",
            "value": _display_value((score_row or {}).get("データ品質"), "未計算"),
            "caption": _cockpit_card_caption(
                "Data Confidence", (score_row or {}).get("データ品質")
            ),
            "help_text": _cockpit_metric_help("Data Confidence"),
        },
        {
            "label": "Risk",
            "value": _display_value((score_row or {}).get("Risk"), "未接続"),
            "caption": _cockpit_card_caption("Risk", (score_row or {}).get("Risk")),
            "help_text": _cockpit_metric_help("Risk"),
        },
        {
            "label": "Forecast horizon",
            "value": f"{forecast_horizon_days}日",
            "help": "チャート上に表示する予測日数です。",
        },
    ]


def cockpit_kpi_cards(score_row: dict[str, str] | None) -> list[dict[str, str]]:
    row = score_row or {}
    return [
        {
            "label": "Investment Score",
            "value": _display_value(row.get("総合スコア"), "未計算"),
            "caption": _cockpit_card_caption("Investment Score", row.get("総合スコア")),
            "help_text": _cockpit_metric_help("Investment Score"),
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
            "label": "Data Confidence",
            "value": _display_value(row.get("データ品質"), "未計算"),
            "caption": _cockpit_card_caption("Data Confidence", row.get("データ品質")),
            "help_text": _cockpit_metric_help("Data Confidence"),
        },
        {
            "label": "Risk",
            "value": _display_value(row.get("Risk"), "未接続"),
            "caption": _cockpit_card_caption("Risk", row.get("Risk")),
            "help_text": _cockpit_metric_help("Risk"),
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
    return [
        {
            "観点": "上昇気配",
            "内容": upside,
            "確認ポイント": "予測エッジ、モデル別方向、モメンタム、トレンド確認を合わせた上向き材料です。",
        },
        {
            "観点": "下降警戒",
            "内容": downside,
            "確認ポイント": "下向き材料が強い場合は、上昇気配が高くても直近トレンドを確認します。",
        },
        {
            "観点": "予測変化率",
            "内容": forecast_return,
            "確認ポイント": "平均予測価格が直近終値より上か下かを確認します。断定ではありません。",
        },
        {
            "観点": "モデル方向一致",
            "内容": direction_match,
            "確認ポイント": "複数モデルが同じ方向を示しているか、割れているかを確認します。",
        },
        {
            "観点": "予測のばらつき",
            "内容": f"{forecast_range} / モデル一致度 {agreement}",
            "確認ポイント": "モデルの開きが大きい場合、上昇気配・下降警戒は中立寄りに扱います。",
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
    if downside is not None and downside >= Decimal("70"):
        return (
            f"下降警戒が{_format_direction_decimal(downside)}と高めです。"
            f"上昇気配と予測変化率 {forecast_return} を合わせて確認します。"
        )
    if upside is not None and upside >= Decimal("70"):
        return (
            f"上昇気配が{_format_direction_decimal(upside)}と相対的に強めです。"
            "下降警戒と直近トレンドを合わせて深掘りします。"
        )
    return "上昇気配と下降警戒が拮抗しています。価格チャート、モデル方向一致、予測のばらつきを合わせて確認します。"


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
    return [
        {
            "label": "Document Count",
            "value": str(report.data_quality.document_count),
            "help": "登録資料として参照できた資料数です。",
        },
        {
            "label": "Evidence Count",
            "value": str(report.data_quality.evidence_count),
            "help": "検索で確認できた根拠抜粋数です。",
        },
        {
            "label": "Latest Source Date",
            "value": (
                report.data_quality.latest_document_date.isoformat()
                if report.data_quality.latest_document_date
                else "未取得"
            ),
            "help": "参照資料のうち最新の日付です。",
        },
        {
            "label": "Data Quality Status",
            "value": report.data_quality.status,
            "help": "Research Evidence の確認材料としての状態です。",
        },
        {
            "label": "Warnings",
            "value": str(len(report.data_quality.warnings)),
            "help": "根拠不足や資料不足などの注意数です。",
        },
    ]


def render_cockpit_summary_header(items: list[dict[str, str]]) -> None:
    item_by_label = {item["label"]: item for item in items}
    symbol = _item_value(item_by_label, "Symbol")
    name = _item_value(item_by_label, "Name")
    title = symbol if name in {"", "-", "未取得"} else f"{symbol} - {name}"
    render_dashboard_header(
        title,
        "価格・予測・スコア・根拠資料を1画面で確認する分析ビューです。表示内容は売買推奨ではありません。",
        chips=[
            ("Provider", _item_value(item_by_label, "Provider")),
            ("As of", _item_value(item_by_label, "As of")),
            ("期間", _item_value(item_by_label, "Reference period")),
            ("見方", _item_value(item_by_label, "Decision View")),
        ],
    )
    render_section_heading("01 Summary / Symbol Cockpit")
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
    render_section_heading("Analysis KPI")
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
    st.markdown("##### Research Evidence Summary")
    st.caption(
        "Research Evidence は登録資料から検索できた確認材料です。確定情報やスコアの正しさを保証するものではありません。"
    )
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
    if label in {"Symbol", "Name", "Provider", "Asset / Region"}:
        return badge_html("Info", "info")
    if label == "Data Confidence" and value not in {"-", "未計算"}:
        return badge_html("Data state", "success")
    if label in {"Risk", "Decision View"}:
        return badge_html("Review", "caution")
    return badge_html("Context", "neutral")


def _tone_for_summary_item(item: dict[str, str]) -> str:
    label = item.get("label", "")
    if label == "Investment Score":
        return "score"
    if label == "Data Confidence":
        return "success"
    if label == "Risk":
        return "risk"
    if label == "Forecast horizon":
        return "forecast"
    if label == "Decision View":
        return "caution"
    if label in {"Symbol", "Name", "Provider", "Asset / Region"}:
        return "info"
    return "neutral"


def _progress_for_summary_item(item: dict[str, str]) -> int | None:
    if item.get("label") in {"Investment Score", "Data Confidence", "Risk"}:
        return metric_progress_from_value(item.get("value"))
    return None


def _badge_for_kpi_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    value = card.get("value", "")
    if label == "Data Confidence" and value not in {"-", "未計算"}:
        return badge_html("Data state", "success")
    if label in {"Risk", "Decision View"}:
        return badge_html("Review", "caution")
    return badge_html("Analysis", "info")


def _tone_for_kpi_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    if label == "Investment Score":
        return "score"
    if label == "上昇気配":
        return "forecast"
    if label == "下降警戒":
        return "risk"
    if label == "Data Confidence":
        return "success"
    if label == "Risk":
        return "risk"
    if label == "Decision View":
        return "caution"
    return "info"


def _progress_for_kpi_card(card: dict[str, str]) -> int | None:
    if card.get("label") in {
        "Investment Score",
        "上昇気配",
        "下降警戒",
        "Data Confidence",
        "Risk",
    }:
        return metric_progress_from_value(card.get("value"))
    return None


def _badge_for_direction_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    if label == "下降警戒":
        return badge_html("Check", "caution")
    if label == "上昇気配":
        return badge_html("Signal", "info")
    return badge_html("Forecast", "neutral")


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
    if label == "Data Quality Status" and value == "OK":
        return badge_html("High Confidence", "success")
    if label == "Warnings" and value not in {"0", "-"}:
        return badge_html("Check data", "caution")
    return badge_html("Evidence", "info")


def _item_value(items: dict[str, dict[str, str]], label: str) -> str:
    return _display_value(items.get(label, {}).get("value"), "-")


def _card_caption(card: dict[str, str]) -> str:
    return card.get("caption") or card.get("help", "")


def _cockpit_metric_help(label: str) -> str:
    return COCKPIT_CARD_MEANINGS.get(label, "")


def _cockpit_card_caption(label: str, value: object) -> str:
    evaluation = _cockpit_card_evaluation(label, value)
    if not evaluation:
        return ""
    return f"今回: {evaluation}"


def _cockpit_card_evaluation(label: str, value: object) -> str:
    if label == "Decision View":
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
    return _score_comment(score, COCKPIT_SCORE_EVALUATION_TABLE.get(label, ()))


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
