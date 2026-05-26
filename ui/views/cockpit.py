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
            "help": "複数観点を統合した比較・分析用スコアです。",
        },
        {
            "label": "Decision View",
            "value": _display_value((score_row or {}).get("見方"), "未判定"),
            "help": "売買指示ではなく、確認レベルの目安です。",
        },
        {
            "label": "Data Confidence",
            "value": _display_value((score_row or {}).get("データ品質"), "未計算"),
            "help": "投資魅力度ではなく、評価に使えるデータの充実度です。",
        },
        {
            "label": "Risk",
            "value": _display_value((score_row or {}).get("Risk"), "未接続"),
            "help": "注意すべきリスク確認材料です。",
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
            "help": "比較・分析用の総合スコアです。売買判断そのものではありません。",
        },
        {
            "label": "Decision View",
            "value": _display_value(row.get("見方"), "未判定"),
            "help": "確認レベルの目安です。売買指示ではありません。",
        },
        {
            "label": "Direction Signal",
            "value": _display_value(row.get("方向スコア") or row.get("方向感"), "未計算"),
            "help": "上昇気配と下降警戒の差分を整理した深掘り用シグナルです。",
        },
        {
            "label": "Data Confidence",
            "value": _display_value(row.get("データ品質"), "未計算"),
            "help": "評価に使えるデータの充実度です。投資魅力度ではありません。",
        },
        {
            "label": "Risk",
            "value": _display_value(row.get("Risk"), "未接続"),
            "help": "取得期間から見たリスク確認材料です。",
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
            "label": "方向スコア",
            "value": _display_value(
                row.get("方向スコア") or consensus.get("direction_net_score"),
                "未計算",
            ),
            "help": "上昇気配と下降警戒の差分を0〜100で整理した深掘り用シグナルです。",
        },
        {
            "label": "上昇気配",
            "value": _display_value(
                row.get("上昇気配") or consensus.get("upside_signal_score"),
                "未計算",
            ),
            "help": "予測上昇率、モデル別の上向き強度、直近モメンタムを合わせたスコアです。",
        },
        {
            "label": "下降警戒",
            "value": _display_value(
                row.get("下降警戒") or consensus.get("downside_signal_score"),
                "未計算",
            ),
            "help": "予測下落率、モデル別の下向き強度、直近モメンタムを合わせた警戒スコアです。",
        },
        {
            "label": "予測変化率",
            "value": _display_value(
                row.get("予測変化率") or consensus.get("forecast_return_pct"),
                "未計算",
            ),
            "help": "平均予測価格が直近終値からどの程度離れているかを示します。",
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
    direction_score = _display_value(
        row.get("方向スコア") or consensus.get("direction_net_score"),
        "未計算",
    )
    direction_label = _display_value(
        row.get("方向感") or _direction_label_text(consensus.get("direction_signal_label")),
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
            "観点": "方向感",
            "内容": f"{direction_label} / 方向スコア {direction_score}",
            "確認ポイント": "ランキングと同じ方向分類です。深掘り候補の見方として確認します。",
        },
        {
            "観点": "上昇・下降バランス",
            "内容": f"上昇気配 {upside} / 下降警戒 {downside} / 方向スコア {direction_score}",
            "確認ポイント": "上昇気配だけでなく、下降警戒との差し引きで深掘り優先度を確認します。",
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
            "確認ポイント": "モデルの開きが大きい場合、方向スコアは中立寄りに扱います。",
        },
    ]


def cockpit_direction_signal_summary(
    score_row: dict[str, str] | None,
    consensus_row: dict[str, str] | None,
) -> str:
    """Return a short non-advisory direction-signal explanation."""

    row = score_row or {}
    consensus = consensus_row or {}
    direction = _decimal_display_value(
        row.get("方向スコア") or consensus.get("direction_net_score")
    )
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
    if (
        upside is not None
        and upside >= Decimal("70")
        and (direction is None or direction >= Decimal("55"))
    ):
        return (
            f"上昇気配が{_format_direction_decimal(upside)}と相対的に強めです。"
            f"方向スコアと下降警戒を合わせて深掘りします。"
        )
    if direction is not None and direction <= Decimal("45"):
        return (
            f"方向スコアが{_format_direction_decimal(direction)}で中立以下です。"
            "下向き材料と直近トレンドを先に確認します。"
        )
    return "上昇気配と下降警戒が拮抗しています。価格チャート、モデル方向一致、予測のばらつきを合わせて確認します。"


def render_cockpit_direction_signal_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        return
    render_section_heading("03 Direction Signal / 上昇気配・下降警戒")
    st.caption(
        "ランキングで使う方向シグナルを、1銘柄の深掘り用に分解して確認します。売買推奨ではありません。"
    )
    columns = st.columns(min(4, len(cards)))
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            render_metric_card(
                card["label"],
                card["value"],
                caption=card.get("help", ""),
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
                caption=item.get("help", ""),
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
                caption=card.get("help", ""),
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
    if label == "Direction Signal":
        return "forecast"
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
        "Direction Signal",
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
    if label == "方向スコア":
        return badge_html("Balance", "info")
    return badge_html("Forecast", "neutral")


def _tone_for_direction_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    if label == "下降警戒":
        return "risk"
    if label == "上昇気配":
        return "forecast"
    if label == "方向スコア":
        return "score"
    return "info"


def _progress_for_direction_card(card: dict[str, str]) -> int | None:
    if card.get("label") in {"方向スコア", "上昇気配", "下降警戒"}:
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
