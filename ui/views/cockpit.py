from __future__ import annotations

import streamlit as st

from backend.research import CompanyResearchReport


def _display_value(value: object, fallback: str = "未取得") -> str:
    text = str(value or "").strip()
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
            "label": "Forecast Agreement",
            "value": _display_value(row.get("予測一致"), "未計算"),
            "help": "予測モデル間の見方の近さです。",
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
    st.markdown("#### Symbol Cockpit Summary")
    st.caption(
        "この画面は、選択銘柄の価格・予測・スコア・根拠資料を整理する分析ビューです。表示内容は売買推奨ではありません。"
    )
    columns = st.columns(4)
    for index, item in enumerate(items):
        with columns[index % len(columns)]:
            st.metric(item["label"], item["value"], help=item.get("help"))


def render_cockpit_kpi_cards(cards: list[dict[str, str]]) -> None:
    st.markdown("#### Analysis KPI")
    st.caption("既存の分析結果を、確認しやすい主要KPIとして整理しています。")
    columns = st.columns(min(5, len(cards)))
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            st.metric(card["label"], card["value"], help=card.get("help"))


def render_research_evidence_summary(report: CompanyResearchReport) -> None:
    st.markdown("##### Research Evidence Summary")
    st.caption(
        "Research Evidence は登録資料から検索できた確認材料です。確定情報やスコアの正しさを保証するものではありません。"
    )
    items = research_evidence_summary_items(report)
    columns = st.columns(min(5, len(items)))
    for index, item in enumerate(items):
        with columns[index % len(columns)]:
            st.metric(item["label"], item["value"], help=item.get("help"))
