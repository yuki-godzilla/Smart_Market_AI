from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pandas as pd
from st_aggrid import GridOptionsBuilder, JsCode


@dataclass(frozen=True)
class RankingTableConfig:
    """Immutable display configuration supplied by the Ranking composition root."""

    nowrap_cell_style: dict[str, str]
    numeric_cell_style: dict[str, str]
    numeric_sort_directions: dict[str, str]
    numeric_sort_comparator: JsCode
    llm_factor_detail_columns: tuple[str, ...]
    llm_factor_column_tooltips: dict[str, str]
    hidden_columns: tuple[str, ...]


def build_ranking_aggrid_options(
    frame: pd.DataFrame,
    config: RankingTableConfig,
) -> dict[str, object]:
    builder = GridOptionsBuilder.from_dataframe(frame)
    builder.configure_default_column(
        sortable=True,
        filter=True,
        resizable=True,
        wrapText=False,
        autoHeight=False,
    )
    builder.configure_selection(
        selection_mode="single",
        use_checkbox=False,
        suppressRowClickSelection=False,
        suppressRowDeselection=False,
    )
    builder.configure_grid_options(
        rowHeight=38,
        headerHeight=38,
        suppressCellFocus=True,
        tooltipShowDelay=250,
        ensureDomOrder=True,
        enableCellTextSelection=True,
    )
    if "順位" in frame.columns:
        builder.configure_column(
            "順位",
            width=58,
            pinned="left",
            filter=False,
            cellStyle=config.numeric_cell_style,
        )
    if "銘柄" in frame.columns:
        builder.configure_column(
            "銘柄",
            width=92,
            pinned="left",
            cellStyle=config.nowrap_cell_style,
        )
    if "お気に入り" in frame.columns:
        builder.configure_column(
            "お気に入り",
            width=116,
            pinned="left",
            sortable=False,
            filter=False,
            suppressMenu=True,
            cellStyle=JsCode(
                """
                function(params) {
                    const active = String(params.value || '').startsWith('★');
                    return {
                        color: active ? '#fbbf24' : '#dbeafe',
                        backgroundColor: active
                            ? 'rgba(245, 158, 11, 0.16)'
                            : 'rgba(15, 23, 42, 0.54)',
                        borderLeft: active
                            ? '3px solid rgba(250, 204, 21, 0.82)'
                            : '3px solid rgba(96, 165, 250, 0.42)',
                        fontWeight: '800',
                        cursor: 'pointer',
                        textAlign: 'center',
                        whiteSpace: 'nowrap'
                    };
                }
                """
            ),
        )
    if "銘柄名" in frame.columns:
        builder.configure_column(
            "銘柄名",
            width=200,
            minWidth=170,
            maxWidth=260,
            pinned="left",
            tooltipField="銘柄名",
            wrapText=False,
            autoHeight=False,
            cellStyle=config.nowrap_cell_style,
        )
    if "判断方針" in frame.columns:
        builder.configure_column(
            "判断方針",
            width=116,
            cellStyle=config.nowrap_cell_style,
        )
    for column in (
        "総合スコア",
        "Screening",
        "基礎評価",
        "上昇気配",
        "下降警戒",
        "予測変化率",
        "予測確度",
        "高度予測",
        "高度予測日数",
        "高度予測スコア",
        "データ品質",
        "データ信頼度",
        "条件適合度",
        "Risk",
        "リスク",
        "DB信頼度",
        "PER",
        "PBR",
        "ROE",
        "配当利回り",
        "株価",
        "時価総額",
        "出来高",
        "ボラティリティ",
        "自己資本比率",
        "営業利益率",
        "売上成長率",
        "経費率",
    ):
        if column in frame.columns:
            header_name = {
                "Screening": "基礎評価",
                "Risk": "リスク",
                "データ品質": "データ信頼度",
            }.get(column, column)
            sort_direction = config.numeric_sort_directions.get(column, "desc")
            sorting_order = (
                ["asc", "desc", None] if sort_direction == "asc" else ["desc", "asc", None]
            )
            builder.configure_column(
                column,
                width=168 if column == "株価" else 92,
                filter=False,
                headerName=header_name,
                comparator=config.numeric_sort_comparator,
                sortingOrder=sorting_order,
                unSortIcon=True,
                wrapText=False,
                autoHeight=False,
                cellStyle=config.numeric_cell_style,
            )
    for column in config.llm_factor_detail_columns:
        if column in frame.columns:
            is_numeric_material_column = column != "ニュース材料"
            builder.configure_column(
                column,
                width=128,
                filter=False,
                sortable=False,
                headerTooltip=config.llm_factor_column_tooltips[column],
                wrapText=False,
                autoHeight=False,
                cellStyle=(
                    config.numeric_cell_style
                    if is_numeric_material_column
                    else config.nowrap_cell_style
                ),
            )
    if "方向一致" in frame.columns:
        builder.configure_column(
            "方向一致",
            width=112,
            headerName="モデル方向",
            cellStyle=config.nowrap_cell_style,
        )
    if "モデル方向" in frame.columns:
        builder.configure_column(
            "モデル方向",
            width=128,
            cellStyle=config.nowrap_cell_style,
        )
    if "予測根拠" in frame.columns:
        builder.configure_column(
            "予測根拠",
            width=180,
            tooltipField="予測根拠",
            cellStyle=config.nowrap_cell_style,
        )
    if "高度予測信頼度" in frame.columns:
        builder.configure_column(
            "高度予測信頼度",
            width=120,
            cellStyle=config.nowrap_cell_style,
        )
    if "信頼度/根拠" in frame.columns:
        builder.configure_column(
            "信頼度/根拠",
            width=142,
            tooltipField="信頼度/根拠",
            cellStyle=config.nowrap_cell_style,
        )
    if "根拠状態" in frame.columns:
        builder.configure_column(
            "根拠状態",
            width=116,
            cellStyle=config.nowrap_cell_style,
        )
    if "見方" in frame.columns:
        builder.configure_column(
            "見方",
            width=96,
            cellStyle=config.nowrap_cell_style,
        )
    for column in ("NISA", "投資スタイル", "時価総額", "連動指数", "通貨", "複雑性"):
        if column in frame.columns:
            builder.configure_column(
                column,
                width=112,
                cellStyle=config.nowrap_cell_style,
            )
    if "SMAIメモ" in frame.columns:
        builder.configure_column(
            "SMAIメモ",
            width=280,
            minWidth=220,
            maxWidth=360,
            tooltipField="確認詳細",
            wrapText=False,
            autoHeight=False,
            cellStyle=config.nowrap_cell_style,
        )
    if "確認メモ" in frame.columns:
        builder.configure_column(
            "確認メモ",
            width=420,
            minWidth=300,
            maxWidth=520,
            tooltipField="確認詳細",
            wrapText=False,
            autoHeight=False,
            cellStyle=config.nowrap_cell_style,
        )
    for column in config.hidden_columns:
        if column in frame.columns:
            builder.configure_column(column, hide=True, tooltipField=column)
    return cast(dict[str, object], builder.build())
