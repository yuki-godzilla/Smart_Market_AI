"""Altair renderer for the Cockpit price and Forecast chart."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import altair as alt
import pandas as pd

from ui.content.common_texts import FORECAST_ACTUAL_LABEL
from ui.styles import FORECAST_ACTUAL_PRICE_COLOR, THEME_COLORS


@dataclass(frozen=True)
class CockpitMarketChartLayerData:
    """Pre-shaped data frames for one chart viewport."""

    chart_data: pd.DataFrame
    range_band_data: pd.DataFrame
    boundary_data: pd.DataFrame
    latest_actual_data: pd.DataFrame


@dataclass(frozen=True)
class CockpitMarketChartRenderContext:
    """All deterministic display inputs for the two Cockpit Forecast chart views."""

    y_axis_title: str
    title: str
    color_domain: tuple[str, ...]
    color_range: tuple[str, ...]
    legend_labels: tuple[str, ...]
    main: CockpitMarketChartLayerData
    focus: CockpitMarketChartLayerData
    focus_title: str
    full_width: int
    focus_width: int
    height: int
    combined_spacing: int


def render_cockpit_market_chart(
    context: CockpitMarketChartRenderContext,
    *,
    render_altair_chart: Callable[[Any], None],
) -> None:
    """Build and render the established linked Forecast chart and its legend."""

    color_scale = alt.Scale(domain=list(context.color_domain), range=list(context.color_range))
    disabled_series = alt.selection_point(
        fields=["series_label"],
        on="click",
        toggle="true",
        empty=False,
    )
    chart = _market_chart_layers(
        context.main,
        y_axis_title=context.y_axis_title,
        color_scale=color_scale,
        disabled_series=disabled_series,
        height=context.height,
        width=context.full_width,
        title="価格チャート",
        compact_points=True,
    )
    focus_chart = _market_chart_layers(
        context.focus,
        y_axis_title=context.y_axis_title,
        color_scale=color_scale,
        disabled_series=disabled_series,
        height=context.height,
        width=context.focus_width,
        title=context.focus_title,
        compact_points=False,
    )
    main_chart = alt.hconcat(chart, focus_chart, spacing=context.combined_spacing)
    legend_chart = _market_chart_interactive_legend(
        context.legend_labels,
        color_scale=color_scale,
        disabled_series=disabled_series,
        width=context.full_width + context.focus_width + context.combined_spacing,
    )
    combined_chart = (
        alt.vconcat(main_chart, legend_chart, spacing=4)
        .add_params(disabled_series)
        .resolve_scale(color="shared", y="independent", x="independent")
        .configure(background=THEME_COLORS["bg_surface"])
        .configure_view(fill=THEME_COLORS["bg_card"], stroke=THEME_COLORS["border_strong"])
        .configure_axis(
            domainColor=THEME_COLORS["border_strong"],
            gridColor="rgba(148, 163, 184, 0.14)",
            labelColor=THEME_COLORS["text_caption"],
            titleColor=THEME_COLORS["text_label"],
            tickColor=THEME_COLORS["border_strong"],
        )
        .configure_title(color=THEME_COLORS["text_heading"], fontSize=16, anchor="start", offset=10)
    )
    if context.title:
        combined_chart = combined_chart.properties(title=context.title)
    render_altair_chart(combined_chart)


def _market_chart_interactive_legend(
    labels: Sequence[str],
    *,
    color_scale: alt.Scale,
    disabled_series: alt.Parameter,
    width: int,
) -> alt.LayerChart:
    columns = 3
    legend_rows = [
        {
            "series_label": label,
            "legend_col": index % columns,
            "legend_row": index // columns,
        }
        for index, label in enumerate(labels)
    ]
    legend_data = pd.DataFrame(legend_rows)
    row_count = max(1, math.ceil(len(labels) / columns))
    base = alt.Chart(legend_data).encode(
        x=alt.X("legend_col:O", axis=None, title=None, scale=alt.Scale(paddingInner=0.18)),
        y=alt.Y("legend_row:O", axis=None, title=None, scale=alt.Scale(paddingInner=0.36)),
        tooltip=[alt.Tooltip("series_label:N", title="価格・モデル")],
    )
    points = base.mark_point(filled=True, size=96).encode(
        color=alt.Color("series_label:N", legend=None, scale=color_scale),
        opacity=alt.condition(disabled_series, alt.value(0.14), alt.value(1.0)),
    )
    text = base.mark_text(
        align="left",
        baseline="middle",
        dx=13,
        fontSize=13,
        fontWeight=700,
    ).encode(
        text="series_label:N",
        color=alt.value(THEME_COLORS["text_secondary"]),
        opacity=alt.condition(disabled_series, alt.value(0.28), alt.value(1.0)),
    )
    return (points + text).properties(
        width=width,
        height=max(38, row_count * 30),
        title="価格・モデル",
    )


def _market_chart_layers(
    data: CockpitMarketChartLayerData,
    *,
    y_axis_title: str,
    color_scale: alt.Scale,
    disabled_series: alt.Parameter,
    height: int,
    width: int,
    title: str,
    compact_points: bool,
) -> alt.LayerChart:
    forecast_data = data.chart_data[data.chart_data["series_label"] != FORECAST_ACTUAL_LABEL]
    actual_data = data.chart_data[data.chart_data["series_label"] == FORECAST_ACTUAL_LABEL]
    base_x = alt.X("date:T", title="日付", axis=alt.Axis(format="%Y/%m/%d", labelAngle=0))
    base_encoding: Mapping[str, object] = {
        "x": base_x,
        "y": alt.Y("value:Q", title=y_axis_title, scale=alt.Scale(zero=False)),
        "color": alt.Color(
            "series_label:N",
            title="価格・モデル",
            legend=None,
            scale=color_scale,
        ),
        "strokeDash": alt.StrokeDash(
            "line_label:N",
            title="実績/予測",
            scale=alt.Scale(domain=["実績", "予測"], range=[[1, 0], [6, 4]]),
            legend=None,
        ),
        "tooltip": [
            alt.Tooltip("date:T", title="日付"),
            alt.Tooltip("series_label:N", title="価格・モデル"),
            alt.Tooltip("value:Q", title="終値"),
            alt.Tooltip("line_label:N", title="実績/予測"),
        ],
        "opacity": alt.condition(disabled_series, alt.value(0.04), alt.value(1.0)),
    }
    forecast_point = alt.OverlayMarkDef(
        filled=True,
        size=22 if compact_points else 36,
        opacity=0.58 if compact_points else 0.92,
    )
    actual_point = alt.OverlayMarkDef(
        filled=True,
        size=24 if compact_points else 52,
        opacity=0.62 if compact_points else 0.92,
    )
    range_band = (
        alt.Chart(data.range_band_data)
        .mark_area(opacity=0.18)
        .encode(
            x=base_x,
            y=alt.Y("lower:Q", title=y_axis_title, scale=alt.Scale(zero=False)),
            y2=alt.Y2("upper:Q"),
            color=alt.Color("series_label:N", title="価格・モデル", legend=None, scale=color_scale),
            tooltip=[
                alt.Tooltip("date:T", title="日付"),
                alt.Tooltip("series_label:N", title="価格・モデル"),
                alt.Tooltip("lower:Q", title="下振れ"),
                alt.Tooltip("upper:Q", title="上振れ"),
            ],
            opacity=alt.condition(disabled_series, alt.value(0.01), alt.value(0.18)),
        )
        .properties(height=height, width=width)
    )
    forecast_lines = (
        alt.Chart(forecast_data)
        .mark_line(point=forecast_point, strokeWidth=1.9, opacity=0.9)
        .encode(**base_encoding)
        .properties(height=height, width=width)
    )
    actual_line = (
        alt.Chart(actual_data)
        .mark_line(point=actual_point, strokeWidth=2.8)
        .encode(**base_encoding)
        .properties(height=height, width=width)
    )
    chart = range_band + forecast_lines + actual_line
    if not data.latest_actual_data.empty:
        latest_marker = (
            alt.Chart(data.latest_actual_data)
            .mark_point(
                filled=True,
                shape="diamond",
                size=180,
                color=FORECAST_ACTUAL_PRICE_COLOR,
                stroke=THEME_COLORS["text_title"],
                strokeWidth=1.8,
            )
            .encode(
                x=alt.X("date:T"),
                y=alt.Y("value:Q"),
                tooltip=[
                    alt.Tooltip("date:T", title="日付"),
                    alt.Tooltip("marker_label:N", title="状態"),
                    alt.Tooltip("value:Q", title="現在価格"),
                ],
                opacity=alt.condition(disabled_series, alt.value(0.04), alt.value(1.0)),
            )
        )
        chart = chart + latest_marker
    if not data.boundary_data.empty:
        chart = chart + (
            alt.Chart(data.boundary_data)
            .mark_rule(color=THEME_COLORS["text_muted"], opacity=0.52, strokeDash=[4, 4])
            .encode(x="date:T")
        )
    return chart.properties(height=height, width=width, title=title)
