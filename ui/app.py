from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import time as perf_time
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Callable, Iterable, Literal, Mapping, Sequence, cast

import altair as alt
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, JsCode

from backend.core.config import get_settings
from backend.core.data_contracts import (
    Bar,
    DailySnapshot,
    DataQuality,
    FeatureSnapshot,
    FundamentalSnapshot,
    Quote,
)
from backend.core.errors import AppError
from backend.forecast import forecast_model_display_name
from backend.marketdata import create_market_data_provider_adapter
from backend.marketdata.feature_builder import build_daily_snapshots_from_market_data
from backend.reporting import (
    DecisionReportContext,
    DecisionReportSection,
    ReportSourceKind,
    build_data_confidence_section,
    build_decision_checkpoints_section,
    build_decision_report_context,
    build_external_research_trace_section,
    build_report_section,
    build_research_evidence_section,
    build_research_score_section,
    build_symbol_metadata_section,
    decision_report_manifest_json_download,
    decision_report_zip_download,
    render_decision_report_markdown,
)
from backend.reporting import (
    decision_report_json_download as reporting_decision_report_json_download,
)
from backend.research import (
    CompanyResearchReport,
    CompanyResearchSummary,
    ETFResearchSummary,
    ExternalResearchFetchManifestEntry,
    ExternalResearchFetchResult,
    InvestmentActionHint,
    InvestmentInsight,
    InvestmentInsightBuilder,
    InvestmentInsightItem,
    InvestmentQuestionAnswer,
    InvestmentQuestionSummary,
    IRSummaryItem,
    NewsSummaryItem,
    QuantitativeSummary,
    ResearchBrief,
    ResearchBriefBuilder,
    ResearchBriefMaterial,
    ResearchBriefSourceCard,
    ResearchDocument,
    ResearchFactItem,
    ResearchFactSummary,
    ResearchPageViewModelBuilder,
    ResearchScore,
    ResearchScoreService,
    SecurityResearchType,
    StockNewsReport,
)
from backend.scoring import InvestmentScoringService
from backend.screening import ScreeningService
from ui.components.mascot import (
    render_app_header,
    render_mascot_loading,
    render_mascot_panel,
    render_page_title,
    smai_insight_html,
)
from ui.components.sidemenu import (
    SIDEMENU_PAGE_COCKPIT,
    SIDEMENU_PAGE_RANKING,
    SIDEMENU_PAGE_REBALANCE,
    render_sidemenu,
)
from ui.content.common_texts import (
    EMPTY_STATE_MESSAGES,
    FORECAST_ACTUAL_LABEL,
    MARKET_DATA_PERIOD_CUSTOM,
    MARKET_DATA_PERIOD_HELP_TEXT,
    MARKET_DATA_PERIOD_PRESETS,
    NO_SYMBOL_CANDIDATE_LABEL,
    user_facing_table_rows,
)
from ui.content.research_texts import (
    RESEARCH_AI_READING_MEMO_TITLE,
    RESEARCH_COCKPIT_INTRO,
    RESEARCH_COCKPIT_SECTION_TITLE,
    RESEARCH_COMPANY_RESEARCH_TITLE,
    RESEARCH_DETAIL_EXPANDER_LABEL,
    RESEARCH_DETAIL_OK_CAPTION,
    RESEARCH_DOCUMENTS_OR_CHUNKS_MISSING,
    RESEARCH_EVIDENCE_CHECK_FALLBACK,
    RESEARCH_FETCH_BUTTON_LABEL,
    RESEARCH_FETCH_SPINNER,
    RESEARCH_INSUFFICIENT_REPORT_NOTE,
    RESEARCH_INVESTMENT_INSIGHT_GAPS_LABEL,
    RESEARCH_INVESTMENT_INSIGHT_NEGATIVE_LABEL,
    RESEARCH_INVESTMENT_INSIGHT_NOTE,
    RESEARCH_INVESTMENT_INSIGHT_POSITIVE_LABEL,
    RESEARCH_INVESTMENT_INSIGHT_SUMMARY_LABEL,
    RESEARCH_INVESTMENT_INSIGHT_TITLE,
    RESEARCH_INVESTMENT_QUESTION_MORE_LABEL,
    RESEARCH_INVESTMENT_QUESTION_SUMMARY_TITLE,
    RESEARCH_IR_SUMMARY_TITLE,
    RESEARCH_NEWS_SUMMARY_TITLE,
    RESEARCH_NO_REGISTERED_DOCUMENTS,
    RESEARCH_NOT_FETCHED_MESSAGE,
    RESEARCH_QUANTITATIVE_SUMMARY_TITLE,
    RESEARCH_RANKING_FETCH_BUTTON_LABEL,
    RESEARCH_RANKING_LOOKUP_INTRO,
    RESEARCH_RANKING_LOOKUP_TITLE,
    RESEARCH_REGISTERED_EVIDENCE_NOTE,
    RESEARCH_STALE_DOCUMENT_NOTE,
    RESEARCH_STALE_REPORT_NOTE,
    RESEARCH_STATUS_INSUFFICIENT,
    RESEARCH_STATUS_STALE,
    RESEARCH_STATUS_WITH_EVIDENCE,
    research_evidence_confirmed_note,
)
from ui.content.symbol_texts import (
    SYMBOL_UNIVERSE_DETAIL_LABELS,
    SYMBOL_UNIVERSE_DISPLAY_LABELS,
    SYMBOL_UNIVERSE_NISA_SHORT_LABELS,
    SYMBOL_UNIVERSE_RISK_BAND_SHORT_LABELS,
)
from ui.ranking import (
    LIVE_MARKET_DATA_PROVIDERS,
    MAX_RANKING_BUILD_CACHE_ENTRIES,
    MAX_RANKING_CONCURRENT_FETCHES,
    RANKING_BETA_RISK_LABELS,
    RANKING_COMPLEXITY_LABELS,
    RANKING_CURRENCY_LABELS,
    RANKING_DEFAULT_PERIOD_PRESET,
    RANKING_DIVIDEND_LABELS,
    RANKING_FETCH_LIMIT_LABELS,
    RANKING_FETCH_LIMIT_PRESET,
    RANKING_FILTER_HELP_TEXTS,
    RANKING_INDEX_FAMILY_LABELS,
    RANKING_MARKET_CAP_LABELS,
    RANKING_MVP_PRODUCT_TYPE_LABELS,
    RANKING_MVP_REGION_LABELS,
    RANKING_NISA_ELIGIBILITY_LABELS,
    RANKING_PERIOD_PRESETS,
    RANKING_PRODUCT_ALL,
    RANKING_PRODUCT_ETF,
    RANKING_PURPOSE_MULTI_FACTOR,
    RANKING_THEME_LABELS,
    apply_ranking_weight_preset,
    filter_symbol_universe_rows,
    limited_ranking_selected_labels,
    live_ranking_symbol_warning_message,
    normalize_dividend_filter_values,
    rank_investment_score_rows,
    ranking_build_cache_key,
    ranking_deep_dive_default_symbol,
    ranking_detail_filters_for_category,
    ranking_dividend_yield_pct_is_abnormal,
    ranking_dividend_yield_pct_value,
    ranking_fetch_limit_label,
    ranking_filter_signature,
    ranking_fundamental_metric_is_abnormal,
    ranking_fundamental_metric_value,
    ranking_no_bars_error_row,
    ranking_period_dates,
    ranking_period_label,
    ranking_policy_for_purpose,
    ranking_policy_label,
    ranking_policy_options,
    ranking_product_type_label,
    ranking_provider_error_rows,
    ranking_purpose_focus_summary,
    ranking_purpose_help,
    ranking_purpose_label,
    ranking_purpose_primary_columns,
    ranking_purpose_weight_summary,
    ranking_region_label,
    ranking_symbol_chunks,
    ranking_symbol_options,
    ranking_symbols_state_key,
    ranking_weight_preset_for_purpose,
    ranking_weight_preset_label,
    symbol_candidate_labels,
    symbol_universe_rows,
)
from ui.ranking_state import (
    clear_ranking_filter_state,
    ensure_ranking_selection_widget_state,
    sync_ranking_selection_state,
)
from ui.ranking_state import (
    ranking_filter_bool as _ranking_filter_bool,
)
from ui.ranking_state import (
    ranking_filter_value as _ranking_filter_value,
)
from ui.rebalance_app import (
    MarketDataPreview,
    _available_forecast_evaluations,
    build_market_data_preview,
    forecast_chart_rows,
    forecast_consensus_rows_for_bars,
    forecast_metric_csv_download,
    forecast_metric_json_download,
    forecast_metric_rows_for_bars,
    forecast_reference_period,
    investment_score_csv_download,
    investment_score_json_download,
    investment_score_rows,
    runtime_settings_summary,
    screening_score_csv_download,
    screening_score_json_download,
    summarize_forecast_evaluations_for_ui,
    symbol_name,
    yfinance_search_symbol_rows,
)
from ui.research_state import (
    analyze_research_for_symbol,
    analyze_stock_news_for_symbol,
    autoload_local_research_documents,
    external_research_fetch_cache_info,
    fetch_external_research_for_symbol,
    research_store,
)
from ui.state import (
    MARKET_DATA_EXTERNAL_RESEARCH_FETCH_STATE_KEY,
    MARKET_DATA_FORECAST_DAYS_STATE_KEY,
    MARKET_DATA_PREVIEW_STATE_KEY,
    MARKET_DATA_RANKING_BUILD_CACHE_STATE_KEY,
    MARKET_DATA_RANKING_DEEP_DIVE_SOURCE_STATE_KEY,
    MARKET_DATA_RANKING_ERROR_STATE_KEY,
    MARKET_DATA_RANKING_RESEARCH_REPORTS_STATE_KEY,
    MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY,
    MARKET_DATA_RANKING_SOURCE_STATE_KEY,
    MARKET_DATA_RANKING_STATE_KEY,
    MARKET_DATA_RANKING_UPDATED_AT_STATE_KEY,
    MARKET_DATA_RESEARCH_REPORT_STATE_KEY,
    MARKET_DATA_STATUS_STATE_KEY,
    MARKET_DATA_STOCK_NEWS_REPORT_STATE_KEY,
    MARKET_DATA_TOAST_STATE_KEY,
)
from ui.styles import (
    CHART_COLORS,
    FORECAST_ACTUAL_PRICE_COLOR,
    FORECAST_MODEL_COLORS,
    RANKING_GRID_CUSTOM_CSS,
    THEME_COLORS,
    badge_html,
    metric_progress_from_value,
    render_dashboard_header,
    render_global_styles,
    render_metric_card,
    render_section_heading,
    style_altair_chart,
    truncate_text,
)
from ui.symbol_universe import symbol_provider_symbol, symbol_universe_csv_rows
from ui.views.cockpit import (
    cockpit_direction_signal_detail_rows,
    cockpit_direction_signal_summary,
    cockpit_kpi_cards,
    cockpit_summary_items,
    render_cockpit_kpi_cards,
    render_cockpit_summary_header,
    render_research_evidence_summary,
)
from ui.views.common import (
    _optional_decimal_from_text,
    _render_table,
    _single_date_from_input,
    default_as_of_date,
)
from ui.views.ranking_chart_profiles import chart_profile_for_purpose, ranking_chart_frame
from ui.views.rebalance import (
    REBALANCE_REQUEST_STATE_KEY,
    REBALANCE_RESULT_STATE_KEY,
    allocation_chart_frame,
    rebalance_flow_rows,
    rebalance_result_from_state,
    render_rebalance_page,
    risk_breach_display_rows,
    risk_breach_message,
)
from ui.views.settings import render_settings_page

__all__ = [
    "REBALANCE_REQUEST_STATE_KEY",
    "REBALANCE_RESULT_STATE_KEY",
    "allocation_chart_frame",
    "default_as_of_date",
    "rebalance_flow_rows",
    "rebalance_result_from_state",
    "risk_breach_display_rows",
    "risk_breach_message",
]

MARKET_DATA_PROVIDER_OPTIONS = ["yahoo", "csv", "mock"]
MARKET_DATA_PROVIDER_WIDGET_KEY = "market_data_provider_live_first"
MARKET_DATA_RANKING_PROVIDER_WIDGET_KEY = "market_data_ranking_provider_live_first"
RANKING_BUILD_CACHE_VERSION = "signal-v4"
RESEARCH_SUMMARY_BUILD_CACHE_STATE_KEY = "market_data_research_summary_build_cache_v1"
RESEARCH_REFRESH_TRACE_STATE_KEY = "market_data_research_refresh_trace_v1"
RESEARCH_STALE_DAYS = 730
DEFAULT_MARKET_DATA_PERIOD_PRESET = MARKET_DATA_PERIOD_CUSTOM
MARKET_DATA_COCKPIT_FILTER_DEFAULTS: dict[str, str | bool] = {
    "market_data_cockpit_region": "all",
    "market_data_cockpit_product_type": "all",
    "market_data_cockpit_theme": "all",
    "market_data_cockpit_market_cap": "all",
    "market_data_cockpit_dividend": "all",
    "market_data_cockpit_currency": "all",
    "market_data_cockpit_nisa": "all",
    "market_data_cockpit_risk_band": "all",
    "market_data_cockpit_dividend_enabled": False,
    "market_data_cockpit_min_dividend": "0.0",
    "market_data_cockpit_dividend_max": "10.0",
    "market_data_cockpit_per_enabled": False,
    "market_data_cockpit_per_min": "2.0",
    "market_data_cockpit_per_max": "20.0",
    "market_data_cockpit_pbr_enabled": False,
    "market_data_cockpit_pbr_min": "0.5",
    "market_data_cockpit_pbr_max": "2.0",
    "market_data_cockpit_roe_enabled": False,
    "market_data_cockpit_roe_min": "8.0",
    "market_data_cockpit_roe_max": "30.0",
}


@dataclass(frozen=True)
class ResearchSummaryBundle:
    brief: ResearchBrief
    insight: InvestmentInsight
    security_type: SecurityResearchType
    company_summary: CompanyResearchSummary | None
    etf_summary: ETFResearchSummary | None
    question_summary: InvestmentQuestionSummary | None
    research_score: ResearchScore


MARKET_DATA_COCKPIT_DETAIL_FILTERS = frozenset(
    {
        "industry_or_sector",
        "market_cap",
        "risk_band",
        "dividend_yield",
        "per",
        "pbr",
        "roe",
        "nisa_eligibility",
    }
)

MARKET_DATA_MODE_COCKPIT = "cockpit"
MARKET_DATA_MODE_RANKING = "ranking"


@dataclass(frozen=True)
class RankingResearchStatus:
    label: str
    tone: str
    note: str
    document_count: int = 0
    evidence_count: int = 0
    latest_document_date: date | None = None
    research_score: Decimal | None = None
    research_confidence: Decimal | None = None
    research_score_warning_count: int = 0


RANKING_RESULT_GRID_CUSTOM_CSS = RANKING_GRID_CUSTOM_CSS
RANKING_MISSING_DISPLAY = "N/A"
RANKING_ABNORMAL_DIVIDEND_DISPLAY = "要確認"
RANKING_TABLE_BASE_COLUMNS = (
    "順位",
    "銘柄",
    "銘柄名",
    "総合スコア",
    "配当利回り",
    "PER",
    "PBR",
    "ROE",
    "見方",
)
RANKING_NUMERIC_SORT_DIRECTIONS = {
    "総合スコア": "desc",
    "Screening": "desc",
    "上昇気配": "desc",
    "下降警戒": "asc",
    "配当利回り": "desc",
    "PER": "asc",
    "PBR": "asc",
    "ROE": "desc",
    "現在値": "desc",
    "時価総額": "desc",
    "出来高": "desc",
    "ボラティリティ": "asc",
    "自己資本比率": "desc",
    "営業利益率": "desc",
    "売上成長率": "desc",
    "Risk": "asc",
    "データ品質": "desc",
    "経費率": "asc",
}
RANKING_TABLE_SORT_GUIDANCE = (
    "詳細テーブルでは、列名をクリックして各指標順に並べ替えできます。"
    "総合スコア・配当利回り・ROE・時価総額・出来高・データ品質・スクリーニング・上昇気配は高い順、"
    "PER・PBR・ボラティリティ・リスク・下降警戒は低い順から確認します。"
    "N/Aは末尾に置きます。"
)
RANKING_LOW_VALUE_BETTER_COLUMNS = {"PER", "PBR", "ボラティリティ", "Risk", "下降警戒"}
RANKING_NUMERIC_SORT_COMPARATOR = JsCode(
    """
function(valueA, valueB, nodeA, nodeB, isDescending) {
  function parseMetric(value) {
    if (value === null || value === undefined) {
      return null;
    }
    var text = String(value).replace(/,/g, "").replace(/%/g, "").trim();
    var missing = ["", "-", "N/A", "未登録", "未取得", "取得不可", "未計算", "未接続"];
    if (missing.indexOf(text) >= 0) {
      return null;
    }
    var numberValue = Number(text);
    return Number.isFinite(numberValue) ? numberValue : null;
  }
  var a = parseMetric(valueA);
  var b = parseMetric(valueB);
  if (a === null && b === null) {
    return 0;
  }
  if (a === null) {
    return isDescending ? -1 : 1;
  }
  if (b === null) {
    return isDescending ? 1 : -1;
  }
  return a - b;
}
"""
)
SYMBOL_DETAIL_DIALOG_CSS = """
<style>
div[data-testid="stDialog"] div[role="dialog"] {
    width: min(90vw, 1100px);
    max-width: min(90vw, 1100px);
}
div[data-testid="stDialog"] [data-testid="stMetricValue"] {
    font-size: clamp(1.05rem, 1.35vw, 1.35rem);
    line-height: 1.25;
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
}
div[data-testid="stDialog"] [data-testid="stMetricValue"] > div {
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
    overflow-wrap: anywhere;
}
div[data-testid="stDialog"] [data-testid="stMetricLabel"] {
    min-height: 1.25rem;
}
.symbol-detail-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 0.95rem;
}
.symbol-detail-table th,
.symbol-detail-table td {
    border: 1px solid var(--border-default);
    padding: 0.72rem 0.82rem;
    vertical-align: top;
    white-space: normal;
    overflow-wrap: anywhere;
    word-break: auto-phrase;
    line-height: 1.6;
}
.symbol-detail-table th {
    background: var(--table-header-bg);
    color: var(--text-label);
    font-weight: 700;
}
.symbol-detail-table td {
    background: var(--table-row-bg);
    color: var(--text-value);
}
.symbol-detail-table td:first-child {
    color: var(--text-label);
    font-weight: 700;
}
.research-summary-table {
    margin-top: 0.6rem;
}
.research-summary-table th,
.research-summary-table td {
    padding: 0.62rem 0.72rem;
}
.research-summary-table .research-topic {
    width: 8.5rem;
    font-weight: 700;
}
.research-summary-table .research-count {
    width: 5rem;
    text-align: right;
}
.research-ai-cta {
    padding: 0.2rem 0.1rem;
    margin: 0.15rem 0 0.2rem;
}
.research-ai-cta-title {
    color: var(--text-ai-title);
    font-weight: 800;
    font-size: 1.02rem;
    margin-bottom: 0.45rem;
}
.research-ai-cta-copy {
    color: var(--text-ai-primary);
    font-size: 0.9rem;
    line-height: 1.55;
}
.research-ai-cta-source {
    color: var(--text-ai-muted);
    font-size: 0.82rem;
    line-height: 1.45;
    margin-top: 0.42rem;
    overflow-wrap: anywhere;
}
.research-ai-cta-note {
    color: var(--text-caption);
    font-size: 0.78rem;
    line-height: 1.45;
    margin-top: 0.34rem;
}
.research-next-step {
    border-left: 3px solid var(--ai-cyan);
    color: var(--text-ai-primary);
    font-weight: 750;
    margin-top: 0.45rem;
    padding-left: 0.62rem;
}
.research-action-label {
    color: var(--text-ai-title);
    font-size: 0.78rem;
    font-weight: 850;
    letter-spacing: 0;
    margin: 0.1rem 0 0.36rem;
}
.research-action-label.secondary {
    color: var(--text-caption);
    margin-top: 0.78rem;
}
.research-action-help {
    color: var(--text-ai-muted);
    font-size: 0.8rem;
    line-height: 1.45;
    margin-top: 0.34rem;
}
.research-result-brief {
    border: 1px solid var(--ai-border);
    border-radius: 8px;
    background: var(--ai-bg);
    padding: 0.9rem 1rem;
    margin: 0.75rem 0 0.65rem;
}
.research-result-brief.hero {
    border-color: rgba(34, 211, 238, 0.58);
    background:
        linear-gradient(135deg, rgba(8, 27, 42, 0.98), rgba(17, 31, 53, 0.94));
    box-shadow: 0 18px 42px rgba(2, 8, 23, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.research-result-brief-title {
    color: var(--text-ai-title);
    font-size: 1.12rem;
    font-weight: 800;
    margin-bottom: 0.35rem;
}
.research-result-brief-summary {
    color: var(--text-ai-primary);
    font-size: 0.98rem;
    line-height: 1.65;
    margin-bottom: 0.75rem;
}
.research-summary-next-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin: 0.28rem 0 0.72rem;
}
.research-summary-next-chip {
    border: 1px solid rgba(34, 211, 238, 0.42);
    border-radius: 999px;
    background: rgba(34, 211, 238, 0.08);
    color: var(--text-ai-primary);
    font-size: 0.8rem;
    font-weight: 780;
    line-height: 1.35;
    padding: 0.22rem 0.58rem;
}
.research-brief-reading-grid {
    display: grid;
    gap: 0.58rem;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    margin: 0.68rem 0 0.7rem;
}
.research-brief-reading-item {
    border: 1px solid var(--border-default);
    border-left: 3px solid var(--ai-cyan);
    border-radius: 6px;
    background: var(--bg-card);
    padding: 0.68rem 0.78rem;
}
.research-brief-reading-item.tone-positive {
    border-left-color: var(--text-positive);
}
.research-brief-reading-item.tone-warning {
    border-left-color: var(--text-warning);
}
.research-brief-reading-item.tone-neutral {
    border-left-color: var(--text-neutral);
}
.research-brief-reading-label {
    color: var(--text-ai-title);
    font-size: 0.8rem;
    font-weight: 850;
    margin-bottom: 0.26rem;
}
.research-brief-reading-body {
    color: var(--text-secondary);
    font-size: 0.84rem;
    line-height: 1.55;
    overflow-wrap: anywhere;
}
.research-brief-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-bottom: 0.7rem;
}
.research-brief-badge {
    border: 1px solid var(--border-default);
    border-radius: 999px;
    color: var(--text-neutral);
    font-size: 0.76rem;
    font-weight: 820;
    padding: 0.18rem 0.55rem;
}
.research-brief-badge.info,
.research-evidence-pill.confidence-high {
    border-color: rgba(34, 211, 238, 0.56);
    color: var(--text-ai-title);
}
.research-brief-badge.neutral,
.research-evidence-pill.confidence-unknown {
    border-color: var(--border-default);
    color: var(--text-neutral);
}
.research-brief-badge.warning,
.research-evidence-pill.confidence-medium {
    border-color: rgba(251, 191, 36, 0.58);
    color: var(--text-warning);
}
.research-brief-badge.low,
.research-evidence-pill.confidence-low {
    border-color: rgba(251, 113, 133, 0.56);
    color: var(--text-negative);
}
.research-brief-metric-grid {
    display: grid;
    gap: 0.62rem;
    grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
    margin: 0.75rem 0 0.65rem;
}
.research-brief-metric-card {
    border: 1px solid var(--border-default);
    border-radius: 6px;
    background: var(--bg-card);
    padding: 0.72rem 0.82rem;
}
.research-brief-metric-label {
    color: var(--text-label);
    font-size: 0.78rem;
    font-weight: 760;
    margin-bottom: 0.24rem;
}
.research-brief-metric-value {
    color: var(--text-value);
    font-size: 1.02rem;
    font-weight: 850;
    line-height: 1.35;
    overflow-wrap: anywhere;
}
.research-brief-metric-source {
    color: var(--text-caption);
    font-size: 0.78rem;
    line-height: 1.45;
    margin-top: 0.38rem;
    overflow-wrap: anywhere;
}
.research-brief-gap-panel {
    border: 1px solid rgba(251, 191, 36, 0.5);
    border-radius: 8px;
    background: rgba(251, 191, 36, 0.08);
    color: var(--text-warning);
    margin: 0.75rem 0 0.65rem;
    padding: 0.82rem 0.95rem;
}
.research-brief-gap-title {
    color: var(--text-warning);
    font-weight: 840;
    margin-bottom: 0.36rem;
}
.research-brief-gap-item {
    color: var(--text-secondary);
    line-height: 1.55;
    margin-top: 0.24rem;
}
.research-brief-focus-grid {
    display: grid;
    gap: 0.65rem;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    margin: 0.75rem 0 0.65rem;
}
.research-brief-focus-card {
    border: 1px solid var(--border-default);
    border-radius: 6px;
    background: var(--bg-card);
    padding: 0.78rem 0.86rem;
    min-height: 108px;
}
.research-brief-focus-title {
    color: var(--text-ai-title);
    font-size: 0.82rem;
    font-weight: 850;
    margin-bottom: 0.4rem;
}
.research-brief-focus-body {
    color: var(--text-secondary);
    font-size: 0.86rem;
    line-height: 1.55;
    overflow-wrap: anywhere;
}
.research-brief-focus-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin: 0.08rem 0 0.34rem;
}
.research-brief-focus-meta {
    color: var(--text-caption);
    font-size: 0.76rem;
    line-height: 1.45;
    margin-top: 0.22rem;
    overflow-wrap: anywhere;
}
.research-brief-focus-list {
    display: grid;
    gap: 0.38rem;
}
.research-brief-focus-more {
    color: var(--text-caption);
    font-size: 0.78rem;
    margin-top: 0.38rem;
}
.research-brief-next-list {
    border: 1px solid var(--border-default);
    border-radius: 6px;
    background: var(--bg-card);
    display: grid;
    gap: 0.4rem;
    margin: 0.65rem 0 0.55rem;
    padding: 0.74rem 0.86rem;
}
.research-brief-next-item {
    color: var(--text-secondary);
    line-height: 1.5;
}
.research-result-brief-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.55rem;
}
.research-result-brief-item {
    border: 1px solid var(--border-default);
    border-radius: 6px;
    padding: 0.62rem 0.7rem;
    background: var(--bg-card);
}
.research-result-brief-label {
    color: var(--text-label);
    font-size: 0.78rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}
.research-result-brief-value {
    color: var(--text-value);
    font-size: 0.92rem;
    line-height: 1.45;
}
@media (max-width: 900px) {
    .research-result-brief-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .research-brief-focus-grid {
        grid-template-columns: 1fr;
    }
}
@media (max-width: 560px) {
    .research-result-brief-grid {
        grid-template-columns: 1fr;
    }
}
.research-evidence-list {
    display: grid;
    gap: 0.65rem;
    margin-top: 0.75rem;
}
.research-evidence-item {
    border: 1px solid var(--border-default);
    border-radius: 6px;
    background: var(--bg-card);
    padding: 0.75rem 0.85rem;
}
.research-evidence-card-header {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    align-items: center;
    margin-bottom: 0.55rem;
}
.research-evidence-pill {
    border: 1px solid var(--border-default);
    border-radius: 999px;
    color: var(--text-ai-muted);
    font-size: 0.74rem;
    font-weight: 800;
    padding: 0.16rem 0.48rem;
}
.research-evidence-pill.positive {
    border-color: rgba(52, 211, 153, 0.52);
    color: var(--text-positive);
}
.research-evidence-pill.risk {
    border-color: rgba(251, 191, 36, 0.58);
    color: var(--text-warning);
}
.research-evidence-title {
    color: var(--text-heading);
    font-size: 1.02rem;
    font-weight: 800;
    line-height: 1.45;
    margin-bottom: 0.5rem;
    overflow-wrap: anywhere;
}
.research-evidence-body {
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 0.35rem 0;
    overflow-wrap: anywhere;
}
.research-evidence-label {
    color: var(--text-ai-title);
    font-weight: 800;
}
.research-evidence-meta {
    color: var(--text-caption);
    font-size: 0.86rem;
    line-height: 1.5;
    margin-bottom: 0.4rem;
}
.research-evidence-excerpt {
    color: var(--text-secondary);
    line-height: 1.65;
    overflow-wrap: anywhere;
    white-space: normal;
}
.research-evidence-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.65rem;
}
.research-evidence-actions a,
.research-evidence-action-muted {
    border: 1px solid var(--border-default);
    border-radius: 6px;
    color: var(--text-ai-muted);
    font-size: 0.82rem;
    font-weight: 700;
    padding: 0.34rem 0.58rem;
    text-decoration: none;
}
.research-point-list {
    display: grid;
    gap: 0.55rem;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    margin: 0.75rem 0 0.65rem;
}
.research-point-item {
    border: 1px solid var(--border-default);
    border-radius: 6px;
    background: var(--bg-card);
    padding: 0.72rem 0.82rem;
}
.research-point-label {
    color: var(--text-ai-title);
    font-weight: 800;
    margin-bottom: 0.32rem;
}
.research-point-summary {
    color: var(--text-ai-primary);
    line-height: 1.55;
}
.decision-report-card {
    border: 1px solid var(--border-default);
    border-radius: 8px;
    background: var(--bg-card);
    padding: 1rem 1.1rem;
    margin: 0.65rem 0 0.85rem;
}
.decision-report-title {
    color: var(--text-heading);
    font-size: 1.12rem;
    font-weight: 850;
    margin-bottom: 0.75rem;
}
.decision-report-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.58rem;
}
.decision-report-field {
    border: 1px solid var(--border-default);
    border-radius: 6px;
    background: var(--bg-surface);
    padding: 0.68rem 0.78rem;
}
.decision-report-field-label {
    color: var(--text-label);
    font-size: 0.76rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
}
.decision-report-field-value {
    color: var(--text-value);
    line-height: 1.45;
    overflow-wrap: anywhere;
}
.decision-summary-list {
    margin: 0.6rem 0 0.85rem 1.1rem;
    color: var(--text-secondary);
    line-height: 1.65;
}
.decision-summary-list li {
    margin-bottom: 0.3rem;
}
.symbol-detail-table th:first-child,
.symbol-detail-table td:first-child {
    width: 9rem;
}
</style>
"""


def main() -> None:
    st.set_page_config(page_title="Smart Market AI", layout="wide")
    render_global_styles()

    selected_page = render_sidemenu(runtime_settings_summary())
    render_app_header()
    if selected_page == SIDEMENU_PAGE_COCKPIT:
        _render_market_data_cockpit()
    elif selected_page == SIDEMENU_PAGE_RANKING:
        _render_market_data_ranking()
    elif selected_page == SIDEMENU_PAGE_REBALANCE:
        render_rebalance_page()
    else:
        render_settings_page()


def default_market_data_start_date() -> date:
    start, _ = market_data_period_dates(
        DEFAULT_MARKET_DATA_PERIOD_PRESET,
        default_market_data_end_date(),
    )
    return start


def default_market_data_end_date() -> date:
    return date.today()


def market_data_period_dates(preset: str, end: date) -> tuple[date, date]:
    if preset == "short_1w":
        return end - timedelta(days=7), end
    if preset == "short_1m":
        return _shift_months(end, -1), end
    if preset == "medium_3m":
        return _shift_months(end, -3), end
    if preset == "medium_6m":
        return _shift_months(end, -6), end
    if preset == "ytd":
        return date(end.year, 1, 1), end
    if preset == "long_3y":
        return _shift_years(end, -3), end
    if preset == "long_5y":
        return _shift_years(end, -5), end
    return _shift_years(end, -1), end


def market_data_period_help(preset: str) -> str:
    return MARKET_DATA_PERIOD_HELP_TEXT.get(
        preset,
        MARKET_DATA_PERIOD_HELP_TEXT[DEFAULT_MARKET_DATA_PERIOD_PRESET],
    )


def _shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return date(year, month, day)


def _shift_years(value: date, years: int) -> date:
    year = value.year + years
    day = min(value.day, _days_in_month(year, value.month))
    return date(year, value.month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day


def default_forecast_horizon_days(start: date, end: date) -> int:
    """Choose a compact forecast horizon from the displayed chart period."""

    if end < start:
        raise ValueError("End must be on or after Start")
    display_days = (end - start).days + 1
    return max(1, min(30, round(display_days / 10)))


def _provider_option_index(provider: str) -> int:
    try:
        return MARKET_DATA_PROVIDER_OPTIONS.index(provider)
    except ValueError:
        return 0


def default_market_data_provider() -> str:
    return "yahoo"


def _symbol_from_candidate(label: str) -> str | None:
    if not label or label == NO_SYMBOL_CANDIDATE_LABEL:
        return None
    return label.split(" - ", 1)[0]


def _name_from_candidate(label: str) -> str | None:
    if " - " not in label:
        return None
    return label.split(" - ", 1)[1]


def _ranking_symbols_from_selected_labels(selected_labels: list[str]) -> list[str]:
    return [symbol for label in selected_labels if (symbol := _symbol_from_candidate(label))]


def _ranking_source_key_for_selection(
    *,
    provider: str,
    selected_labels: list[str],
    start: date,
    end: date,
) -> str:
    ranking_symbols = _ranking_symbols_from_selected_labels(selected_labels)
    if not ranking_symbols:
        return ""
    base_key = ranking_build_cache_key(
        provider=provider,
        symbols=ranking_symbols,
        start=start,
        end=end,
    )
    return f"{RANKING_BUILD_CACHE_VERSION}|{base_key}"


def _ranking_result_matches_current_selection(
    stored_source: str,
    *,
    provider: str,
    selected_labels: list[str],
    start: date,
    end: date,
) -> bool:
    current_source = _ranking_source_key_for_selection(
        provider=provider,
        selected_labels=selected_labels,
        start=start,
        end=end,
    )
    return bool(current_source) and stored_source == current_source


def _symbol_universe_row_for_symbol(symbol: str) -> dict[str, str] | None:
    normalized_symbol = symbol.strip().upper()
    return _symbol_universe_rows_by_symbol().get(normalized_symbol)


def _symbol_universe_rows_by_symbol(
    rows: list[dict[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    source_rows = rows if rows is not None else symbol_universe_csv_rows()
    return {
        row.get("symbol", "").strip().upper(): row
        for row in source_rows
        if row.get("symbol", "").strip()
    }


def selected_symbol_has_universe_detail(symbol: str) -> bool:
    return _symbol_universe_row_for_symbol(symbol) is not None


def _symbol_detail_raw_value(row: dict[str, str], column: str) -> str:
    return str(row.get(column, "")).strip()


def _symbol_detail_bool_display(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "true":
        return "はい"
    if normalized == "false":
        return "いいえ"
    return "未確認"


def _symbol_detail_decimal_display(value: str, *, suffix: str = "") -> str:
    if not value.strip() or value.strip() == "-":
        return "未登録"
    try:
        decimal_value = Decimal(value)
    except Exception:
        return value
    text = f"{decimal_value:.2f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def _symbol_detail_date_display(value: str) -> str:
    if not value.strip() or value.strip() == "-":
        return "未登録"
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value)
            return parsed.strftime("%Y-%m-%d %H:%M")
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return value


def _symbol_detail_lookup_display(column: str, value: str) -> str:
    if not value.strip() or value.strip() == "-":
        return "未登録"
    if column in {"theme"}:
        return RANKING_THEME_LABELS.get(value, value)
    if column == "dividend_category":
        return RANKING_DIVIDEND_LABELS.get(value, value)
    if column == "market_cap_tier":
        return RANKING_MARKET_CAP_LABELS.get(value, value)
    if column == "index_family":
        return RANKING_INDEX_FAMILY_LABELS.get(value, value)
    return SYMBOL_UNIVERSE_DISPLAY_LABELS.get(column, {}).get(value, value)


def symbol_universe_detail_display_value(row: dict[str, str], column: str) -> str:
    value = _symbol_detail_raw_value(row, column)
    if column in {
        "is_sbi_supported",
        "is_active",
        "is_leveraged",
        "is_inverse",
        "nisa_tsumitate_eligible",
        "nisa_growth_eligible",
        "installment_available",
    }:
        return _symbol_detail_bool_display(value)
    if column == "dividend_yield_pct":
        if ranking_dividend_yield_pct_is_abnormal(value):
            return RANKING_ABNORMAL_DIVIDEND_DISPLAY
        return _symbol_detail_decimal_display(value, suffix="%")
    if column in {
        "expense_ratio_pct",
        "trust_fee_pct",
        "roe_pct",
    }:
        if ranking_fundamental_metric_is_abnormal(column, value):
            return RANKING_ABNORMAL_DIVIDEND_DISPLAY
        return _symbol_detail_decimal_display(value, suffix="%")
    if column in {"per", "pbr", "consensus_rating", "aum"}:
        if ranking_fundamental_metric_is_abnormal(column, value):
            return RANKING_ABNORMAL_DIVIDEND_DISPLAY
        return _symbol_detail_decimal_display(value)
    if column in {"metadata_as_of", "metadata_updated_at"}:
        return _symbol_detail_date_display(value)
    if column == "yahoo_symbol":
        return value or "表示銘柄と同じ"
    return _symbol_detail_lookup_display(column, value)


def symbol_universe_nisa_display(row: dict[str, str]) -> str:
    nisa_category = _symbol_detail_raw_value(row, "nisa_category")
    growth = _symbol_detail_raw_value(row, "nisa_growth_eligible").lower() == "true"
    tsumitate = _symbol_detail_raw_value(row, "nisa_tsumitate_eligible").lower() == "true"
    if nisa_category in {"growth", "tsumitate", "both", "none"}:
        return symbol_universe_detail_display_value(row, "nisa_category")
    if growth and tsumitate:
        return SYMBOL_UNIVERSE_DISPLAY_LABELS["nisa_category"]["both"]
    if growth:
        return SYMBOL_UNIVERSE_DISPLAY_LABELS["nisa_category"]["growth"]
    if tsumitate:
        return SYMBOL_UNIVERSE_DISPLAY_LABELS["nisa_category"]["tsumitate"]
    if nisa_category == "none":
        return SYMBOL_UNIVERSE_DISPLAY_LABELS["nisa_category"]["none"]
    return SYMBOL_UNIVERSE_DISPLAY_LABELS["nisa_category"]["unknown"]


def symbol_universe_leverage_display(row: dict[str, str]) -> str:
    leveraged = _symbol_detail_raw_value(row, "is_leveraged").lower() == "true"
    inverse = _symbol_detail_raw_value(row, "is_inverse").lower() == "true"
    if leveraged and inverse:
        return "レバレッジ・インバース"
    if leveraged:
        return "レバレッジ"
    if inverse:
        return "インバース"
    return "該当なし"


def _symbol_detail_row(label: str, value: str) -> dict[str, str]:
    return {"項目": label, "内容": value or "未登録"}


def _symbol_data_info_row(label: str, value: str, purpose: str) -> dict[str, str]:
    return {"項目": label, "内容": value or "未登録", "使い道": purpose}


def symbol_universe_overview_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        _symbol_detail_row("市場", symbol_universe_detail_display_value(row, "market")),
        _symbol_detail_row("商品分類", symbol_universe_detail_display_value(row, "asset_type")),
        _symbol_detail_row("通貨", symbol_universe_detail_display_value(row, "currency")),
        _symbol_detail_row("取扱元", symbol_universe_detail_display_value(row, "broker")),
        _symbol_detail_row("取扱状況", symbol_universe_detail_display_value(row, "tradability")),
        _symbol_detail_row("NISA", symbol_universe_nisa_display(row)),
        _symbol_detail_row(
            "投資スタイル",
            symbol_universe_detail_display_value(row, "investment_style"),
        ),
        _symbol_detail_row("テーマ", symbol_universe_detail_display_value(row, "theme")),
        _symbol_detail_row("業種/セクター", symbol_universe_detail_display_value(row, "sector")),
        _symbol_detail_row("レバレッジ/インバース", symbol_universe_leverage_display(row)),
    ]


def symbol_universe_investment_metric_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        _symbol_detail_row(
            "配当利回り",
            symbol_universe_detail_display_value(row, "dividend_yield_pct"),
        ),
        _symbol_detail_row(
            "配当カテゴリ",
            symbol_universe_detail_display_value(row, "dividend_category"),
        ),
        _symbol_detail_row("PER", symbol_universe_detail_display_value(row, "per")),
        _symbol_detail_row("PBR", symbol_universe_detail_display_value(row, "pbr")),
        _symbol_detail_row("ROE", symbol_universe_detail_display_value(row, "roe_pct")),
        _symbol_detail_row(
            "時価総額",
            symbol_universe_detail_display_value(row, "market_cap_tier"),
        ),
        _symbol_detail_row(
            "市場感応度",
            symbol_universe_detail_display_value(row, "risk_band"),
        ),
        _symbol_detail_row(
            "データ品質",
            symbol_universe_detail_display_value(row, "data_quality"),
        ),
    ]


def symbol_universe_fund_detail_rows(row: dict[str, str]) -> list[dict[str, str]]:
    fund_asset_types = {"etf", "mutual_fund", "reit"}
    fund_specific_columns = {
        "index_family",
        "expense_ratio_pct",
        "trust_fee_pct",
        "aum",
        "complexity",
        "management_style",
        "distribution_policy",
        "installment_available",
    }
    if _symbol_detail_raw_value(row, "asset_type") not in fund_asset_types and not any(
        _symbol_detail_raw_value(row, column) for column in fund_specific_columns
    ):
        return []
    fund_columns = [
        ("連動指数", "index_family"),
        ("信託報酬/経費率", "expense_ratio_pct"),
        ("信託報酬", "trust_fee_pct"),
        ("純資産総額", "aum"),
        ("複雑さ", "complexity"),
        ("運用方式", "management_style"),
        ("分配方針", "distribution_policy"),
        ("つみたて投資枠", "nisa_tsumitate_eligible"),
        ("成長投資枠", "nisa_growth_eligible"),
        ("積立可否", "installment_available"),
    ]
    rows = [
        _symbol_detail_row(label, symbol_universe_detail_display_value(row, column))
        for label, column in fund_columns
        if _symbol_detail_raw_value(row, column)
    ]
    return rows


def symbol_universe_data_info_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        _symbol_data_info_row(
            "データ出所",
            symbol_universe_detail_display_value(row, "metadata_source"),
            "指標や分類をどの情報源で補完したかを確認します。",
        ),
        _symbol_data_info_row(
            "データ基準日",
            symbol_universe_detail_display_value(row, "metadata_as_of"),
            "指標や分類の鮮度を確認します。",
        ),
        _symbol_data_info_row(
            "最終更新",
            symbol_universe_detail_display_value(row, "metadata_updated_at"),
            "ローカル銘柄マスタに反映したタイミングを確認します。",
        ),
        _symbol_data_info_row(
            "価格取得用ticker",
            symbol_universe_detail_display_value(row, "yahoo_symbol"),
            "Yahoo取得時に表示用銘柄と別tickerを使う場合に確認します。",
        ),
    ]


def _symbol_universe_key_metric_value(row: dict[str, str], column: str) -> str:
    if column == "nisa_category":
        nisa_text = symbol_universe_nisa_display(row)
        return SYMBOL_UNIVERSE_NISA_SHORT_LABELS.get(nisa_text, nisa_text)
    if column == "risk_band":
        return SYMBOL_UNIVERSE_RISK_BAND_SHORT_LABELS.get(
            _symbol_detail_raw_value(row, column), symbol_universe_detail_display_value(row, column)
        )
    return symbol_universe_detail_display_value(row, column)


def symbol_universe_key_metric_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        _symbol_detail_row("商品分類", symbol_universe_detail_display_value(row, "asset_type")),
        _symbol_detail_row("NISA", _symbol_universe_key_metric_value(row, "nisa_category")),
        _symbol_detail_row(
            "配当利回り", symbol_universe_detail_display_value(row, "dividend_yield_pct")
        ),
        _symbol_detail_row(
            "時価総額", symbol_universe_detail_display_value(row, "market_cap_tier")
        ),
    ]


def symbol_universe_detail_rows(row: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for column, value in row.items():
        label = SYMBOL_UNIVERSE_DETAIL_LABELS.get(column, column)
        text_value = str(value).strip()
        rows.append(
            {
                "項目": label,
                "表示値": symbol_universe_detail_display_value(row, column),
                "CSV列": column,
                "登録値": text_value or "-",
            }
        )
    return rows


def _ranking_result_table_base_key(ranking_source: str, weight_preset: str) -> str:
    source_hash = hashlib.sha1(
        f"{ranking_source}|{weight_preset}".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:12]
    return f"market_data_ranking_result_table_{source_hash}"


def _ranking_result_grid_key(base_key: str) -> str:
    return "market_data_ranking_result_grid"


def _dedupe_columns(columns: tuple[str, ...]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for column in columns:
        if column in seen:
            continue
        ordered.append(column)
        seen.add(column)
    return ordered


def _ranking_result_columns(ranking_purpose: str) -> list[str]:
    focus_columns = ranking_purpose_primary_columns(ranking_purpose)
    focus_set = set(focus_columns)
    support_columns: tuple[str, ...] = (
        () if {"条件適合度", "DB信頼度", "根拠状態"}.intersection(focus_set) else ("信頼度/根拠",)
    )
    secondary_focus_columns = tuple(
        column for column in focus_columns if column not in set(RANKING_TABLE_BASE_COLUMNS)
    )
    return _dedupe_columns(
        (
            *RANKING_TABLE_BASE_COLUMNS,
            *secondary_focus_columns,
            *support_columns,
            "確認メモ",
            "確認詳細",
            "並べ替え理由",
            "確認ポイント",
        )
    )


def _ranking_metric_text(row: dict[str, str], column: str) -> str:
    value = str(row.get(column, "")).strip()
    if not value:
        return ""
    return f"{_ranking_display_column_label(column)} {value}"


def _ranking_first_metric(row: dict[str, str], columns: tuple[str, ...]) -> tuple[str, str]:
    for column in columns:
        value = str(row.get(column, "")).strip()
        if value and value not in {"未計算", "未登録", "未接続", "-"}:
            return _ranking_display_column_label(column), value
    return "総合スコア", str(row.get("総合スコア", "未計算"))


def _ranking_display_column_label(column: str) -> str:
    return {
        "Screening": "スクリーニング",
        "Risk": "リスク確認",
    }.get(column, column)


def _ranking_table_display_value(value: object) -> str:
    text = str(value or "").strip()
    if not text or text in {"-", "未登録", "未取得", "取得不可", "未計算"}:
        return RANKING_MISSING_DISPLAY
    return text


def _ranking_distinct_numeric_count(rows: list[dict[str, str]], column: str) -> int:
    values = {value for row in rows if (value := _decimal_from_text(row.get(column))) is not None}
    return len(values)


def _ranking_direction_data_limited(rows: list[dict[str, str]]) -> bool:
    if not rows:
        return False
    upside_values = [
        _decimal_from_text(row.get("上昇気配"))
        for row in rows
        if _decimal_from_text(row.get("上昇気配")) is not None
    ]
    downside_values = [
        _decimal_from_text(row.get("下降警戒"))
        for row in rows
        if _decimal_from_text(row.get("下降警戒")) is not None
    ]
    if not upside_values or not downside_values:
        return False
    neutral = Decimal("50")
    scores_are_neutral = all(
        value == neutral for values in (upside_values, downside_values) for value in values
    )
    no_model_counts = all(
        str(row.get("方向一致", "")).strip() in {"", "上昇 0 / 下降 0 / 横ばい 0"} for row in rows
    )
    return scores_are_neutral and no_model_counts


def _ranking_reason_columns(
    rows: list[dict[str, str]],
    ranking_purpose: str,
) -> tuple[str, ...]:
    primary_columns = ranking_purpose_primary_columns(ranking_purpose)
    direction_columns = {"上昇気配", "下降警戒"}
    if direction_columns.intersection(primary_columns) and _ranking_direction_data_limited(rows):
        return ("総合スコア", "Risk", "データ品質", "条件適合度")
    return primary_columns


def _ranking_primary_columns_for_cards(
    rows: list[dict[str, str]],
    ranking_purpose: str,
) -> tuple[str, ...]:
    columns = _ranking_reason_columns(rows, ranking_purpose)
    informative = tuple(
        column for column in columns if _ranking_distinct_numeric_count(rows, column) >= 2
    )
    return informative or columns


def ranking_purpose_row_reason(
    row: dict[str, str],
    ranking_purpose: str,
    *,
    focus_columns: tuple[str, ...] | None = None,
    direction_limited: bool = False,
) -> str:
    columns = focus_columns or ranking_purpose_primary_columns(ranking_purpose)
    metrics = [metric for column in columns if (metric := _ranking_metric_text(row, column))][:3]
    focus = ranking_purpose_focus_summary(ranking_purpose)
    if direction_limited:
        fallback = " / ".join(metrics)
        return (
            "方向データが不足しているため、上昇気配・下降警戒は中立値50として扱っています。"
            f"{fallback}を補助確認してください。"
        )
    if not metrics:
        return focus
    return f"{' / '.join(metrics)}。{focus}"


def ranking_purpose_row_checkpoint(row: dict[str, str], ranking_purpose: str) -> str:
    downside = _decimal_from_text(row.get("下降警戒"))
    risk = _decimal_from_text(row.get("Risk"))
    data_quality = _decimal_from_text(row.get("データ品質"))
    caution = str(row.get("注意点", "")).strip()
    if caution:
        return caution
    if downside is not None and downside >= Decimal("65"):
        return "下降警戒が高めです。上向き材料とあわせて短期リスクを確認します。"
    if risk is not None and risk < Decimal("50"):
        return "リスク確認が低めです。値動きの荒さや下落耐性を確認します。"
    if data_quality is not None and data_quality < Decimal("80"):
        return "データ品質に確認余地があります。欠損や取得期間を確認します。"
    if ranking_purpose in {"etf_core_cost", "etf_income"}:
        return "連動指数、経費率、分配方針をETF資料で確認します。"
    return "銘柄コックピットで価格・予測・リスクを確認します。"


def _ranking_compact_confidence_summary(row: dict[str, str]) -> str:
    parts: list[str] = []
    for label, column in (
        ("品質", "データ品質"),
        ("条件", "条件適合度"),
        ("DB", "DB信頼度"),
    ):
        value = str(row.get(column, "")).strip()
        if value:
            parts.append(f"{label}{value}")
    research_status = str(row.get("根拠状態", "")).strip()
    if research_status:
        parts.append(research_status)
    return " / ".join(parts)


def _ranking_compact_confirmation_note(reason: str, checkpoint: str) -> str:
    return truncate_text(_ranking_full_confirmation_note(reason, checkpoint), max_chars=96)


def _ranking_full_confirmation_note(reason: str, checkpoint: str) -> str:
    checkpoint = checkpoint.strip()
    reason = reason.strip()
    generic_checkpoint = "銘柄コックピットで価格・予測・リスクを確認します。"
    if checkpoint and checkpoint != generic_checkpoint:
        if reason and reason != checkpoint:
            return f"{reason} / {checkpoint}"
        return checkpoint
    return reason or checkpoint


def ranking_result_aggrid_frame(
    display_rows: list[dict[str, str]],
    ranking_purpose: str = "multi_factor",
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    reason_columns = _ranking_reason_columns(display_rows, ranking_purpose)
    direction_limited = _ranking_direction_data_limited(display_rows)
    for row in display_rows:
        reason = ranking_purpose_row_reason(
            row,
            ranking_purpose,
            focus_columns=reason_columns,
            direction_limited=direction_limited,
        )
        checkpoint = ranking_purpose_row_checkpoint(row, ranking_purpose)
        record = {
            "順位": row.get("順位", ""),
            "銘柄": row.get("銘柄", ""),
            "銘柄名": truncate_text(row.get("銘柄名", ""), max_chars=56),
            "総合スコア": row.get("総合スコア", ""),
            "Screening": row.get("Screening", ""),
            "上昇気配": row.get("上昇気配", ""),
            "下降警戒": row.get("下降警戒", ""),
            "予測変化率": row.get("予測変化率", ""),
            "方向一致": row.get("方向一致", ""),
            "Risk": row.get("Risk", ""),
            "データ品質": row.get("データ品質", ""),
            "条件適合度": row.get("条件適合度") or row.get("DB適合", ""),
            "DB信頼度": row.get("DB信頼度", ""),
            "根拠状態": row.get("根拠状態", ""),
            "信頼度/根拠": _ranking_compact_confidence_summary(row),
            "見方": row.get("見方", ""),
            "PER": _ranking_table_display_value(row.get("PER", "")),
            "PBR": _ranking_table_display_value(row.get("PBR", "")),
            "ROE": _ranking_table_display_value(row.get("ROE", "")),
            "配当利回り": _ranking_table_display_value(row.get("配当利回り", "")),
            "経費率": row.get("経費率", ""),
            "NISA": row.get("NISA", ""),
            "投資スタイル": row.get("投資スタイル", ""),
            "現在値": _ranking_table_display_value(row.get("現在値", "")),
            "時価総額": _ranking_table_display_value(row.get("時価総額", "")),
            "出来高": _ranking_table_display_value(row.get("出来高", "")),
            "ボラティリティ": _ranking_table_display_value(row.get("ボラティリティ", "")),
            "自己資本比率": _ranking_table_display_value(row.get("自己資本比率", "")),
            "営業利益率": _ranking_table_display_value(row.get("営業利益率", "")),
            "売上成長率": _ranking_table_display_value(row.get("売上成長率", "")),
            "連動指数": row.get("連動指数", ""),
            "通貨": row.get("通貨", ""),
            "複雑性": row.get("複雑性", ""),
            "注意点": row.get("注意点", ""),
            "確認メモ": _ranking_compact_confirmation_note(reason, checkpoint),
            "確認詳細": _ranking_full_confirmation_note(reason, checkpoint),
            "並べ替え理由": reason,
            "確認ポイント": checkpoint,
        }
        rows.append(
            {column: record.get(column, "") for column in _ranking_result_columns(ranking_purpose)}
        )
    return pd.DataFrame(rows)


def ranking_result_aggrid_options(
    display_rows: list[dict[str, str]] | pd.DataFrame,
    ranking_purpose: str = "multi_factor",
) -> dict[str, object]:
    frame = (
        display_rows
        if isinstance(display_rows, pd.DataFrame)
        else ranking_result_aggrid_frame(display_rows, ranking_purpose=ranking_purpose)
    )
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
        builder.configure_column("順位", width=64, pinned="left", filter=False)
    if "銘柄" in frame.columns:
        builder.configure_column("銘柄", width=96, pinned="left")
    if "銘柄名" in frame.columns:
        builder.configure_column(
            "銘柄名",
            minWidth=220,
            pinned="left",
            tooltipField="銘柄名",
            wrapText=True,
            autoHeight=True,
        )
    for column in (
        "総合スコア",
        "Screening",
        "上昇気配",
        "下降警戒",
        "予測変化率",
        "データ品質",
        "条件適合度",
        "Risk",
        "DB信頼度",
        "PER",
        "PBR",
        "ROE",
        "配当利回り",
        "現在値",
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
                "Screening": "スクリーニング",
                "Risk": "リスク",
            }.get(column, column)
            sort_direction = RANKING_NUMERIC_SORT_DIRECTIONS.get(column, "desc")
            sorting_order = (
                ["asc", "desc", None] if sort_direction == "asc" else ["desc", "asc", None]
            )
            builder.configure_column(
                column,
                width=118,
                filter=False,
                headerName=header_name,
                comparator=RANKING_NUMERIC_SORT_COMPARATOR,
                sortingOrder=sorting_order,
                unSortIcon=True,
            )
    if "方向一致" in frame.columns:
        builder.configure_column("方向一致", width=142, headerName="モデル方向")
    if "信頼度/根拠" in frame.columns:
        builder.configure_column("信頼度/根拠", width=168, tooltipField="信頼度/根拠")
    if "根拠状態" in frame.columns:
        builder.configure_column("根拠状態", width=138)
    if "見方" in frame.columns:
        builder.configure_column("見方", width=112)
    for column in ("NISA", "投資スタイル", "時価総額", "連動指数", "通貨", "複雑性"):
        if column in frame.columns:
            builder.configure_column(column, width=130)
    if "確認メモ" in frame.columns:
        builder.configure_column(
            "確認メモ",
            minWidth=360,
            flex=1,
            tooltipField="確認詳細",
            wrapText=True,
            autoHeight=True,
        )
    for column in ("確認詳細", "並べ替え理由", "確認ポイント"):
        if column in frame.columns:
            builder.configure_column(column, hide=True, tooltipField=column)
    return cast(dict[str, object], builder.build())


def _aggrid_event_data(grid_response: object) -> dict[str, object]:
    event_data = getattr(grid_response, "event_data", None)
    if event_data is None and isinstance(grid_response, dict):
        event_data = grid_response.get("eventData") or grid_response.get("event_data")
    return cast(dict[str, object], event_data) if isinstance(event_data, dict) else {}


def _ranking_symbol_from_row(row: object) -> str | None:
    if not isinstance(row, dict):
        return None
    symbol = str(row.get("銘柄", "")).strip()
    return symbol or None


def ranking_detail_symbol_from_aggrid_response(grid_response: object) -> str | None:
    event_data = _aggrid_event_data(grid_response)
    symbol = _ranking_symbol_from_row(event_data.get("data"))
    if symbol:
        return symbol
    node = event_data.get("node")
    if isinstance(node, dict):
        symbol = _ranking_symbol_from_row(node.get("data"))
        if symbol:
            return symbol

    selected_rows = getattr(grid_response, "selected_rows", None)
    if selected_rows is None and isinstance(grid_response, dict):
        selected_rows = grid_response.get("selected_rows")
    if selected_rows is None:
        return None
    if isinstance(selected_rows, pd.DataFrame):
        if selected_rows.empty:
            return None
        row = selected_rows.iloc[0].to_dict()
    elif isinstance(selected_rows, list):
        row = selected_rows[0] if selected_rows else None
    elif isinstance(selected_rows, dict):
        row = selected_rows
    else:
        return None
    return _ranking_symbol_from_row(row)


def ranking_detail_event_token_from_aggrid_response(
    grid_response: object,
    selected_symbol: str | None,
) -> str | None:
    if not selected_symbol:
        return None
    event_data = _aggrid_event_data(grid_response)
    trigger_name = str(event_data.get("streamlitRerunEventTriggerName") or "").strip()
    if not trigger_name:
        return f"selection|{selected_symbol}"
    node = event_data.get("node")
    row_index = event_data.get("rowIndex")
    if row_index is None and isinstance(node, dict):
        row_index = node.get("rowIndex")
    mouse_event = event_data.get("event")
    timestamp = event_data.get("timeStamp")
    if timestamp is None and isinstance(mouse_event, dict):
        timestamp = mouse_event.get("timeStamp")
    row_index_text = "" if row_index is None else str(row_index)
    timestamp_text = "" if timestamp is None else str(timestamp)
    return f"{trigger_name}|{selected_symbol}|{row_index_text}|{timestamp_text}"


def ranking_detail_symbol_to_open(
    selected_symbol: str | None,
    current_event_token: str | None,
    last_opened_event_token: object,
) -> str | None:
    if not selected_symbol or not current_event_token:
        return None
    previous_event_token = (
        str(last_opened_event_token).strip() if last_opened_event_token is not None else ""
    )
    if current_event_token == previous_event_token:
        return None
    return selected_symbol


def _ranking_result_grid_height(display_rows: list[dict[str, str]]) -> int:
    return min(520, max(150, 44 * len(display_rows) + 48))


def _selectbox_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def _ensure_selectbox_state_value(key: str, options: list[str]) -> None:
    value = _ranking_filter_value(key, options[0])
    if value not in options:
        st.session_state[key] = options[0]


def _sync_ranking_policy_state(product_type: str) -> None:
    policy_options = ranking_policy_options(product_type)
    policy_value = _ranking_filter_value("market_data_ranking_policy", "")
    if policy_value not in policy_options:
        legacy_purpose = _ranking_filter_value(
            "market_data_ranking_purpose",
            RANKING_PURPOSE_MULTI_FACTOR,
        )
        st.session_state["market_data_ranking_policy"] = ranking_policy_for_purpose(legacy_purpose)
    if st.session_state.get("market_data_ranking_policy") not in policy_options:
        st.session_state["market_data_ranking_policy"] = RANKING_PURPOSE_MULTI_FACTOR


def _normalize_dividend_filter_state() -> None:
    dividend_category = _ranking_filter_value("market_data_ranking_dividend", "all")
    dividend_range_enabled = _ranking_filter_bool(
        "market_data_ranking_dividend_enabled",
        False,
    )
    normalized_category, _, normalized_range_enabled, _ = normalize_dividend_filter_values(
        dividend_category=dividend_category,
        dividend_yield_enabled=dividend_range_enabled,
    )
    if normalized_category != dividend_category:
        st.session_state["market_data_ranking_dividend"] = normalized_category
    if normalized_range_enabled != dividend_range_enabled:
        st.session_state["market_data_ranking_dividend_enabled"] = normalized_range_enabled


def _render_metric_range_filter(
    label: str,
    *,
    enabled_key: str,
    min_key: str,
    max_key: str,
    min_default: str,
    max_default: str,
    min_value: float = 0.0,
    max_value: float = 100.0,
    step: float = 0.1,
    help_text: str | None = None,
    disabled: bool = False,
) -> tuple[bool, float, float]:
    min_input_value = _coerce_number_input_state(min_key, min_default)
    max_input_value = _coerce_number_input_state(max_key, max_default)
    col_enabled, col_min, col_max = st.columns([1.0, 1.0, 1.0])
    with col_enabled:
        enabled = st.checkbox(
            label,
            value=_ranking_filter_bool(enabled_key, False),
            key=enabled_key,
            help=help_text,
            disabled=disabled,
        )
    with col_min:
        min_selected = cast(
            float,
            st.number_input(
                "下限",
                min_value=min_value,
                max_value=max_value,
                value=min_input_value,
                step=step,
                key=min_key,
                disabled=disabled or not enabled,
            ),
        )
    with col_max:
        max_selected = cast(
            float,
            st.number_input(
                "上限",
                min_value=min_value,
                max_value=max_value,
                value=max_input_value,
                step=step,
                key=max_key,
                disabled=disabled or not enabled,
            ),
        )
    return enabled, min_selected, max_selected


def _coerce_number_input_state(key: str, default: str) -> float:
    value = st.session_state.get(key, _ranking_filter_value(key, default))
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        numeric_value = float(default)
    st.session_state[key] = numeric_value
    return numeric_value


def _render_detail_selectbox(
    label: str,
    *,
    options: list[str],
    key: str,
    format_func: Callable[[str], str],
    default_value: str | None = None,
    help_text: str | None = None,
    disabled: bool = False,
) -> str:
    default = default_value if default_value in options else options[0]
    _ensure_selectbox_state_value(key, options)
    return cast(
        str,
        st.selectbox(
            label,
            options,
            index=_selectbox_index(options, _ranking_filter_value(key, default)),
            key=key,
            format_func=format_func,
            help=help_text,
            disabled=disabled,
        ),
    )


def _render_metric_filter_grid(
    filters: list[tuple[str, dict[str, object]]],
    *,
    columns_per_row: int = 2,
) -> None:
    for start_index in range(0, len(filters), columns_per_row):
        row_filters = filters[start_index : start_index + columns_per_row]
        columns = st.columns(columns_per_row)
        for column, (label, kwargs) in zip(columns, row_filters, strict=False):
            with column:
                _render_metric_range_filter(
                    label,
                    enabled_key=cast(str, kwargs["enabled_key"]),
                    min_key=cast(str, kwargs["min_key"]),
                    max_key=cast(str, kwargs["max_key"]),
                    min_default=cast(str, kwargs["min_default"]),
                    max_default=cast(str, kwargs["max_default"]),
                    min_value=cast(float, kwargs.get("min_value", 0.0)),
                    max_value=cast(float, kwargs.get("max_value", 100.0)),
                    step=cast(float, kwargs.get("step", 0.1)),
                    help_text=cast(str | None, kwargs.get("help_text")),
                    disabled=cast(bool, kwargs.get("disabled", False)),
                )


def symbol_detail_table_html(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    columns = list(rows[0].keys())
    header_cells = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        '<table class="symbol-detail-table">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _render_symbol_detail_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        st.info("この区分に表示できる登録値はありません。")
        return
    st.markdown(SYMBOL_DETAIL_DIALOG_CSS, unsafe_allow_html=True)
    st.markdown(symbol_detail_table_html(rows), unsafe_allow_html=True)


@st.dialog("銘柄データ", width="large")
def _render_symbol_universe_detail_dialog(
    symbol: str,
    ranking_row: dict[str, str] | None = None,
) -> None:
    row = _symbol_universe_row_for_symbol(symbol)
    if row is None:
        st.warning("銘柄マスタに該当するデータが見つかりませんでした。")
        return
    st.markdown(SYMBOL_DETAIL_DIALOG_CSS, unsafe_allow_html=True)
    display_name = row.get("name") or symbol
    st.subheader(f"{symbol} - {display_name}")
    st.caption("ローカル銘柄マスタの登録値を、確認しやすい項目に整理しています。")

    metric_columns = st.columns(4)
    for column, metric in zip(metric_columns, symbol_universe_key_metric_rows(row), strict=False):
        column.metric(metric["項目"], metric["内容"])

    ranking_detail_rows = ranking_investment_detail_rows(ranking_row, row) if ranking_row else []
    tab_labels = ["概要", "投資指標", "データ情報", "AI Research"]
    if ranking_detail_rows:
        tab_labels.insert(0, "判断補助")
    fund_rows = symbol_universe_fund_detail_rows(row)
    if fund_rows:
        tab_labels.insert(3 if ranking_detail_rows else 2, "ETF/ファンド")
    tabs = st.tabs(tab_labels)

    tab_index = 0
    if ranking_detail_rows:
        with tabs[tab_index]:
            _render_symbol_detail_table(ranking_detail_rows)
        tab_index += 1

    with tabs[tab_index]:
        _render_symbol_detail_table(symbol_universe_overview_rows(row))
    with tabs[tab_index + 1]:
        _render_symbol_detail_table(symbol_universe_investment_metric_rows(row))
    tab_offset = tab_index + 2
    if fund_rows:
        with tabs[tab_offset]:
            _render_symbol_detail_table(fund_rows)
        tab_offset += 1
    with tabs[tab_offset]:
        _render_symbol_detail_table(symbol_universe_data_info_rows(row))
    with tabs[tab_offset + 1]:
        _render_ranking_symbol_research_lookup(symbol)
    with st.expander("CSV登録値を確認", expanded=False):
        st.caption("CSVの列名、画面表示用の値、登録されている元データを確認できます。")
        st.dataframe(
            symbol_universe_detail_rows(row),
            hide_index=True,
            use_container_width=True,
        )


def _ranking_display_decimal(row: dict[str, str], key: str) -> Decimal | None:
    return _decimal_from_text(row.get(key, ""))


def _ranking_display_float(row: dict[str, str], key: str) -> float | None:
    value = _ranking_display_decimal(row, key)
    return float(value) if value is not None else None


def ranking_research_status_from_documents(
    documents: Sequence[ResearchDocument],
    chunks_by_document_id: Mapping[str, Sequence[object]],
    *,
    as_of: date,
) -> RankingResearchStatus:
    latest_document_date = max(
        (document.published_at for document in documents if document.published_at is not None),
        default=None,
    )
    chunk_count = sum(
        len(chunks_by_document_id.get(document.document_id, ())) for document in documents
    )
    if not documents or chunk_count <= 0:
        return RankingResearchStatus(
            label=RESEARCH_STATUS_INSUFFICIENT,
            tone="caution",
            note=RESEARCH_DOCUMENTS_OR_CHUNKS_MISSING,
            document_count=len(documents),
            latest_document_date=latest_document_date,
        )
    if latest_document_date and (as_of - latest_document_date).days > RESEARCH_STALE_DAYS:
        return RankingResearchStatus(
            label=RESEARCH_STATUS_STALE,
            tone="caution",
            note=RESEARCH_STALE_DOCUMENT_NOTE,
            document_count=len(documents),
            evidence_count=chunk_count,
            latest_document_date=latest_document_date,
        )
    return RankingResearchStatus(
        label=RESEARCH_STATUS_WITH_EVIDENCE,
        tone="success",
        note=RESEARCH_REGISTERED_EVIDENCE_NOTE,
        document_count=len(documents),
        evidence_count=chunk_count,
        latest_document_date=latest_document_date,
    )


def ranking_research_status_from_report(
    report: CompanyResearchReport,
) -> RankingResearchStatus:
    latest_document_date = report.data_quality.latest_document_date
    research_score = ResearchScoreService().score_report(report)
    if latest_document_date and (report.as_of - latest_document_date).days > RESEARCH_STALE_DAYS:
        return RankingResearchStatus(
            label=RESEARCH_STATUS_STALE,
            tone="caution",
            note=RESEARCH_STALE_REPORT_NOTE,
            document_count=report.data_quality.document_count,
            evidence_count=report.data_quality.evidence_count,
            latest_document_date=latest_document_date,
            research_score=research_score.total_score,
            research_confidence=research_score.confidence,
            research_score_warning_count=len(research_score.warnings),
        )
    if report.data_quality.document_count <= 0 or report.data_quality.evidence_count <= 0:
        return RankingResearchStatus(
            label=RESEARCH_STATUS_INSUFFICIENT,
            tone="caution",
            note=RESEARCH_INSUFFICIENT_REPORT_NOTE,
            document_count=report.data_quality.document_count,
            evidence_count=report.data_quality.evidence_count,
            latest_document_date=latest_document_date,
            research_score=research_score.total_score,
            research_confidence=research_score.confidence,
            research_score_warning_count=len(research_score.warnings),
        )
    return RankingResearchStatus(
        label=RESEARCH_STATUS_WITH_EVIDENCE,
        tone="success",
        note=research_evidence_confirmed_note(report.data_quality.evidence_count),
        document_count=report.data_quality.document_count,
        evidence_count=report.data_quality.evidence_count,
        latest_document_date=latest_document_date,
        research_score=research_score.total_score,
        research_confidence=research_score.confidence,
        research_score_warning_count=len(research_score.warnings),
    )


def ranking_display_rows_with_research_status(
    display_rows: list[dict[str, str]],
    statuses_by_symbol: Mapping[str, RankingResearchStatus],
) -> list[dict[str, str]]:
    enriched_rows: list[dict[str, str]] = []
    for row in display_rows:
        symbol = _normalize_research_symbol(row.get("銘柄", "") or row.get("symbol", ""))
        status = statuses_by_symbol.get(symbol) or RankingResearchStatus(
            label=RESEARCH_STATUS_INSUFFICIENT,
            tone="caution",
            note=RESEARCH_NO_REGISTERED_DOCUMENTS,
        )
        latest_date = status.latest_document_date.isoformat() if status.latest_document_date else ""
        research_score = str(status.research_score) if status.research_score is not None else ""
        research_confidence = (
            str(status.research_confidence) if status.research_confidence is not None else ""
        )
        score_warning_count = (
            str(status.research_score_warning_count) if status.research_score is not None else ""
        )
        enriched_rows.append(
            {
                **row,
                "根拠状態": status.label,
                "根拠トーン": status.tone,
                "根拠補足": status.note,
                "根拠資料数": str(status.document_count),
                "根拠数": str(status.evidence_count),
                "最新資料日": latest_date,
                "根拠スコア": research_score,
                "根拠信頼度": research_confidence,
                "根拠スコア注意": score_warning_count,
            }
        )
    return enriched_rows


def _ranking_research_statuses_for_display_rows(
    display_rows: list[dict[str, str]],
    *,
    as_of: date,
) -> dict[str, RankingResearchStatus]:
    symbols = [
        symbol
        for row in display_rows
        if (symbol := _normalize_research_symbol(row.get("銘柄", "") or row.get("symbol", "")))
    ]
    if not symbols:
        return {}
    autoload_local_research_documents()
    store = research_store()
    statuses = {
        symbol: ranking_research_status_from_documents(
            store.list_documents(symbol),
            store.chunks_by_document_id,
            as_of=as_of,
        )
        for symbol in dict.fromkeys(symbols)
    }
    reports = st.session_state.get(MARKET_DATA_RANKING_RESEARCH_REPORTS_STATE_KEY)
    if isinstance(reports, dict):
        for report in reports.values():
            if not isinstance(report, CompanyResearchReport):
                continue
            normalized_symbol = _normalize_research_symbol(report.symbol)
            if normalized_symbol in statuses:
                statuses[normalized_symbol] = ranking_research_status_from_report(report)
    return statuses


def _normalize_research_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def ranking_summary_cards(
    display_rows: list[dict[str, str]],
    *,
    ranking_axis: str,
    weight_preset: str,
    region: str,
    product_type: str,
    selected_count: int,
) -> list[dict[str, str]]:
    scores = [
        score
        for row in display_rows
        if (score := _ranking_display_decimal(row, "総合スコア")) is not None
    ]
    confidence_values = [
        confidence
        for row in display_rows
        if (confidence := _ranking_display_decimal(row, "DB信頼度")) is not None
    ]
    average_score = (
        str((sum(scores, Decimal("0")) / Decimal(len(scores))).quantize(Decimal("0.1")))
        if scores
        else "未計算"
    )
    high_confidence_count = sum(
        1 for confidence in confidence_values if confidence >= Decimal("75")
    )
    return [
        {
            "label": "対象銘柄数",
            "value": str(selected_count),
            "help": "現在の条件で取得対象になった銘柄数です。",
        },
        {
            "label": "表示候補数",
            "value": str(len(display_rows)),
            "help": "ランキング結果として表示している比較候補数です。",
        },
        {
            "label": "平均投資スコア",
            "value": average_score,
            "help": "表示候補の総合スコア平均です。売買判断そのものではありません。",
        },
        {
            "label": "データ信頼度高め",
            "value": str(high_confidence_count),
            "help": "DB信頼度が75以上の候補数です。投資魅力度ではなく評価信頼度です。",
        },
        {
            "label": "ランキング軸",
            "value": ranking_axis,
            "help": weight_preset,
        },
        {
            "label": "対象範囲",
            "value": f"{region} / {product_type}",
            "help": "取得前フィルターで選んだ地域と商品分類です。",
        },
    ]


def ranking_top_candidate_cards(
    display_rows: list[dict[str, str]],
    *,
    ranking_purpose: str = "multi_factor",
    limit: int = 5,
) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    focus_columns = _ranking_primary_columns_for_cards(display_rows, ranking_purpose)
    direction_limited = _ranking_direction_data_limited(display_rows)
    for row in display_rows[:limit]:
        primary_label, primary_value = _ranking_first_metric(row, focus_columns)
        cards.append(
            {
                "rank": row.get("順位", ""),
                "symbol": row.get("銘柄", ""),
                "name": row.get("銘柄名", ""),
                "score": row.get("総合スコア", "未計算"),
                "primary_label": primary_label,
                "primary_value": primary_value,
                "reason": ranking_purpose_row_reason(
                    row,
                    ranking_purpose,
                    focus_columns=focus_columns,
                    direction_limited=direction_limited,
                ),
                "confidence": row.get("DB信頼度") or row.get("条件適合度") or "未登録",
                "upside": row.get("上昇気配", ""),
                "downside": row.get("下降警戒", ""),
                "view": row.get("見方", ""),
                "caution": row.get("注意点", ""),
                "note": row.get("補足", ""),
                "research_status": row.get("根拠状態", ""),
                "research_tone": row.get("根拠トーン", "neutral"),
                "research_note": row.get("根拠補足", ""),
            }
        )
    return cards


def ranking_score_bar_chart_frame(
    display_rows: list[dict[str, str]],
    *,
    ranking_purpose: str = "multi_factor",
    limit: int = 10,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    metric_column = _ranking_bar_chart_metric_column(display_rows, ranking_purpose)
    sort_direction = _ranking_bar_chart_sort_direction(metric_column)
    for row in display_rows[:limit]:
        score = _ranking_display_float(row, metric_column)
        if score is None:
            continue
        symbol = row.get("銘柄", "")
        name = row.get("銘柄名", "")
        records.append(
            {
                "rank": row.get("順位", ""),
                "rank_sort": _ranking_rank_sort_value(row.get("順位")),
                "symbol": symbol,
                "name": name,
                "label": symbol or name,
                "score": score,
                "metric": metric_column,
            }
        )
    records.sort(key=lambda record: _ranking_bar_chart_sort_key(record, sort_direction))
    records = records[:limit]
    for index, record in enumerate(records, start=1):
        record["bar_order"] = index
    frame = pd.DataFrame.from_records(records)
    frame.attrs["metric_column"] = metric_column
    frame.attrs["sort_direction"] = sort_direction
    return frame


def _ranking_bar_chart_sort_direction(metric_column: str) -> str:
    return "asc" if metric_column in RANKING_LOW_VALUE_BETTER_COLUMNS else "desc"


def _ranking_bar_chart_sort_key(
    record: dict[str, object],
    sort_direction: str,
) -> tuple[float, int, str]:
    score = cast(float, record["score"])
    metric_key = score if sort_direction == "asc" else -score
    return (metric_key, cast(int, record["rank_sort"]), str(record["symbol"]))


def ranking_score_bar_chart_caption(
    ranking_purpose: str,
    metric_column: str,
    sort_direction: str = "desc",
) -> str:
    order_text = "低い順" if sort_direction == "asc" else "高い順"
    policy_label = ranking_policy_label(ranking_purpose)
    focus_summary = ranking_purpose_focus_summary(ranking_purpose)
    return (
        f"{policy_label}の評価方針に基づく上位候補です。"
        f"代表指標「{metric_column}」は{order_text}に表示します。"
        f"{focus_summary}"
        "詳細テーブルの列ヘッダーで行を並べ替えても、グラフ指標は自動では切り替わりません。"
    )


def _ranking_rank_sort_value(value: object) -> int:
    rank = _decimal_from_text(value)
    if rank is None:
        return 999999
    return int(rank)


def _ranking_bar_chart_metric_column(
    display_rows: list[dict[str, str]],
    ranking_purpose: str,
) -> str:
    direction_columns = {"上昇気配", "下降警戒"}
    candidates = _ranking_bar_chart_candidate_columns(ranking_purpose)
    if direction_columns.intersection(candidates):
        if _ranking_direction_data_limited(display_rows):
            fallback_columns = ("Screening", "Risk", "データ品質", "条件適合度", "総合スコア")
            for column in fallback_columns:
                if _ranking_distinct_numeric_count(display_rows, column) >= 1:
                    return column
    for column in candidates:
        if _ranking_distinct_numeric_count(display_rows, column) >= 1:
            return column
    return "総合スコア"


def _ranking_bar_chart_candidate_columns(ranking_purpose: str) -> tuple[str, ...]:
    purpose_columns: dict[str, tuple[str, ...]] = {
        "sort_total_score": ("総合スコア",),
        "sort_dividend_yield": ("配当利回り",),
        "sort_per": ("PER",),
        "sort_pbr": ("PBR",),
        "sort_roe": ("ROE",),
        "sort_market_cap": ("時価総額",),
        "sort_volume": ("出来高",),
        "sort_volatility": ("ボラティリティ",),
        "sort_risk": ("Risk",),
        "sort_data_quality": ("データ品質",),
        "multi_factor": ("総合スコア", "上昇気配", "下降警戒", "Risk", "データ品質"),
        "upside_signal": ("上昇気配", "下降警戒"),
        "momentum": ("Screening", "上昇気配", "下降警戒"),
        "trend": ("Screening", "上昇気配", "下降警戒"),
        "quality_growth": ("条件適合度", "ROE", "Screening"),
        "growth": ("条件適合度", "ROE", "Screening"),
        "small_growth": ("条件適合度", "上昇気配", "ROE"),
        "quality_value": ("条件適合度", "Risk", "データ品質"),
        "value": ("条件適合度", "Risk", "データ品質"),
        "sustainable_income": ("配当利回り", "条件適合度", "Risk"),
        "dividend": ("配当利回り", "条件適合度", "Risk"),
        "min_volatility": ("Risk", "データ品質", "DB信頼度"),
        "stability": ("Risk", "データ品質", "DB信頼度"),
        "risk_adjusted": ("Risk", "総合スコア", "Screening"),
        "nisa_long_term": ("条件適合度", "Risk", "データ品質"),
        "data_confidence": ("データ品質", "DB信頼度", "条件適合度"),
        "etf_core_cost": ("条件適合度", "データ品質", "DB信頼度"),
        "etf_income": ("配当利回り", "条件適合度", "Risk"),
    }
    return purpose_columns.get(ranking_purpose, ranking_purpose_primary_columns(ranking_purpose))


def ranking_score_confidence_frame(display_rows: list[dict[str, str]]) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in display_rows:
        score = _ranking_display_float(row, "総合スコア")
        metadata_confidence = _ranking_display_float(row, "DB信頼度")
        database_fit = _ranking_display_float(row, "条件適合度")
        confidence = metadata_confidence if metadata_confidence is not None else database_fit
        if score is None or confidence is None:
            continue
        confidence_band = "信頼度高め" if confidence >= 75 else "データ確認"
        records.append(
            {
                "rank": row.get("順位", ""),
                "symbol": row.get("銘柄", ""),
                "name": row.get("銘柄名", ""),
                "score": score,
                "confidence": confidence,
                "confidence_band": confidence_band,
                "database_fit": database_fit,
                "metadata_confidence": metadata_confidence,
                "caution": row.get("注意点", ""),
            }
        )
    return pd.DataFrame.from_records(records)


def ranking_candidate_breakdown_rows(
    display_rows: list[dict[str, str]],
    selected_symbol: str | None,
    ranking_purpose: str | None = None,
) -> list[dict[str, str]]:
    if not selected_symbol:
        return []
    selected_row = next(
        (row for row in display_rows if row.get("銘柄") == selected_symbol),
        None,
    )
    if selected_row is None:
        return []
    rows = [
        {
            "観点": "投資スコア",
            "値": selected_row.get("総合スコア", "未計算"),
            "確認ポイント": truncate_text(
                selected_row.get("見方", "")
                or "複数観点を統合した比較用スコアです。内訳と注意点を確認します。",
                max_chars=56,
            ),
        },
        {
            "観点": "スクリーニング",
            "値": selected_row.get("Screening", "未計算"),
            "確認ポイント": "市場データ由来の候補評価です。モメンタム、流動性、リスク確認の偏りを確認します。",
        },
        {
            "観点": "上昇気配・下降警戒",
            "値": (
                f"上昇気配 {selected_row.get('上昇気配', '未計算')} / "
                f"下降警戒 {selected_row.get('下降警戒', '未計算')}"
            ),
            "確認ポイント": _ranking_direction_check(selected_row),
        },
        {
            "観点": "データ信頼度",
            "値": selected_row.get("DB信頼度") or selected_row.get("条件適合度") or "未登録",
            "確認ポイント": "銘柄メタデータと価格データの充実度です。低い場合はスコア解釈を控えめにします。",
        },
        {
            "観点": "リスク確認",
            "値": selected_row.get("Risk", "未接続"),
            "確認ポイント": truncate_text(
                selected_row.get("注意点", "") or "価格変動、下落幅、品質警告がないか確認します。",
                max_chars=56,
            ),
        },
        {
            "観点": "根拠資料",
            "値": selected_row.get("根拠状態", RESEARCH_STATUS_INSUFFICIENT),
            "確認ポイント": truncate_text(
                selected_row.get("根拠補足", RESEARCH_EVIDENCE_CHECK_FALLBACK),
                max_chars=42,
            ),
        },
    ]
    research_score = selected_row.get("根拠スコア", "").strip()
    if research_score:
        rows.append(
            {
                "観点": "根拠スコア",
                "値": research_score,
                "確認ポイント": _ranking_research_score_check(selected_row),
            }
        )
    if ranking_purpose:
        direction_limited = _ranking_direction_data_limited(display_rows)
        focus_columns = _ranking_reason_columns(display_rows, ranking_purpose)
        primary_label, primary_value = _ranking_first_metric(
            selected_row,
            focus_columns,
        )
        rows.insert(
            0,
            {
                "観点": ranking_purpose_label(ranking_purpose),
                "値": f"{primary_label} {primary_value}",
                "確認ポイント": truncate_text(
                    ranking_purpose_row_reason(
                        selected_row,
                        ranking_purpose,
                        focus_columns=focus_columns,
                        direction_limited=direction_limited,
                    ),
                    max_chars=52,
                ),
            },
        )
    return rows


def _ranking_research_score_check(row: Mapping[str, str]) -> str:
    confidence = row.get("根拠信頼度", "").strip()
    warning_count = _int_from_text(row.get("根拠スコア注意", ""))
    if not row.get("根拠数", "").strip() or row.get("根拠数") == "0":
        return "資料不足の参考値です。AI Researchで根拠カードと不足観点を確認します。"
    if warning_count > 0:
        return truncate_text(
            f"confidence {confidence or '未計算'}。注意点があるため、根拠カードと内訳を確認します。",
            max_chars=56,
        )
    return truncate_text(
        f"confidence {confidence or '未計算'}。売買推奨ではなく、資料の充実度確認です。",
        max_chars=56,
    )


def _ranking_direction_check(row: Mapping[str, str]) -> str:
    upside = _decimal_from_text(row.get("上昇気配"))
    downside = _decimal_from_text(row.get("下降警戒"))
    forecast_return = _display_table_value(row.get("予測変化率"))
    if upside is None or downside is None:
        return "方向シグナルが不足しています。コックピットで価格チャートと予測レンジを確認します。"
    gap = upside - downside
    if downside >= Decimal("65") and gap <= Decimal("-10"):
        return (
            f"下降警戒が相対的に高めです。予測変化率 {forecast_return} と直近トレンドを確認します。"
        )
    if upside >= Decimal("65") and gap >= Decimal("10"):
        return f"上昇気配が相対的に高めです。予測変化率 {forecast_return} と予測下限を確認します。"
    if upside >= Decimal("65") and downside >= Decimal("65"):
        return "上向き・下向き材料が同時に強めです。予測レンジとモデル方向の割れを確認します。"
    return "ランキングとコックピットで同じ2指標を使い、どちらが優勢かを価格チャートと合わせて確認します。"


def _render_ranking_summary_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        return
    columns = st.columns(3)
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            render_metric_card(
                card["label"],
                card["value"],
                caption=card.get("help", ""),
                badges=(_metric_badge_for_card(card),) if _metric_badge_for_card(card) else (),
                tone=_metric_card_tone(card),
                progress=_metric_card_progress(card),
            )


def _render_ranking_purpose_context(ranking_purpose: str, weight_preset: str) -> None:
    render_section_heading("ランキングの見方")
    st.caption(ranking_purpose_focus_summary(ranking_purpose))
    weight_items = ranking_purpose_weight_summary(ranking_purpose, limit=4)
    columns = st.columns(max(1, min(4, len(weight_items))))
    for index, item in enumerate(weight_items):
        label, _, value = item.partition(" ")
        with columns[index % len(columns)]:
            render_metric_card(
                label,
                value or item,
                caption="この評価方針で重視する指標",
                badges=(badge_html("重み", "info"),),
                tone="info",
                progress=metric_progress_from_value(value),
            )
    st.caption(
        f"評価プロファイル: {ranking_weight_preset_label(weight_preset)}。"
        "評価方針は売買推奨ではなく、比較・深掘り候補の採点軸です。"
    )


def _render_top_screening_candidate_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        st.info("比較候補カードを表示できるランキング結果がありません。")
        return
    render_section_heading("注目候補")
    st.caption(
        "現在の条件で抽出された深掘り候補です。売買推奨ではなく、比較対象を絞るための入口です。"
    )
    columns = st.columns(min(5, len(cards)))
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            st.markdown(
                _ranking_candidate_card_html(card, index=index),
                unsafe_allow_html=True,
            )


def _ranking_candidate_card_html(card: dict[str, str], *, index: int) -> str:
    primary_label = card.get("primary_label") or "総合スコア"
    primary_value = card.get("primary_value") or card["score"]
    name = card.get("name") or card.get("symbol") or "名称未登録"
    symbol_line = f"#{card.get('rank', '')} {card.get('symbol', '')}".strip()
    score_line = f"総合 {card['score']}" if card.get("score") else ""
    reason = card.get("reason", "")
    progress = metric_progress_from_value(primary_value)
    safe_progress = min(100, max(0, int(progress))) if progress is not None else 0
    badges = (
        badge_html(primary_label, "info") if primary_label else "",
        badge_html(card["view"], "info") if card["view"] else "",
        (
            badge_html("下降警戒", "caution")
            if (_decimal_from_text(card.get("downside")) or Decimal("0")) >= Decimal("65")
            else ""
        ),
        _confidence_badge(card["confidence"]),
        _research_status_badge(card["research_status"], card["research_tone"]),
        badge_html("要確認", "caution") if card["caution"] else "",
    )
    badge_row = "".join(badge for badge in badges if badge)
    caption_parts = [score_line, reason]
    caption = " / ".join(part for part in caption_parts if part)
    return (
        '<div class="smai-ranking-card" '
        f'data-emphasis="{"spotlight" if index == 0 else "normal"}">'
        '<div class="smai-ranking-card-header">'
        f'<span class="smai-ranking-card-symbol">{html.escape(symbol_line)}</span>'
        "</div>"
        f'<div class="smai-ranking-card-name">{html.escape(name)}</div>'
        '<div class="smai-ranking-card-metric">'
        f'<span class="smai-ranking-card-metric-label">{html.escape(primary_label)}</span>'
        f'<span class="smai-ranking-card-metric-value">{html.escape(str(primary_value))}</span>'
        "</div>"
        '<div class="smai-score-track" aria-hidden="true">'
        f'<div class="smai-score-fill" style="--smai-score-width: {safe_progress}%"></div>'
        "</div>"
        f'<div class="smai-ranking-card-caption">{html.escape(caption)}</div>'
        f'<div class="smai-badge-row">{badge_row}</div>'
        "</div>"
    )


def _metric_badge_for_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    value = card.get("value", "")
    if "信頼度" in label and value not in {"0", "-", "未計算"}:
        return badge_html("データ", "success")
    if "ランキング" in label or "対象範囲" in label:
        return badge_html("条件", "info")
    return ""


def _metric_card_tone(card: dict[str, str]) -> str:
    label = card.get("label", "")
    if "スコア" in label:
        return "score"
    if "信頼度" in label:
        return "success"
    if "ランキング" in label or "対象範囲" in label:
        return "info"
    if "候補" in label or "銘柄" in label:
        return "forecast"
    return "neutral"


def _metric_card_progress(card: dict[str, str]) -> int | None:
    label = card.get("label", "")
    if "スコア" in label or "信頼度" in label:
        return metric_progress_from_value(card.get("value"))
    return None


def _confidence_badge(value: str) -> str:
    confidence = _decimal_from_text(value)
    if confidence is not None and confidence >= Decimal("75"):
        return badge_html("信頼度高め", "success")
    if confidence is not None:
        return badge_html("データ確認", "caution")
    return badge_html("データ不足", "neutral")


def _direction_badge_tone(label: str) -> str:
    if "上昇" in label:
        return "success"
    if "下降" in label:
        return "caution"
    if "判定不足" in label or "データ不足" in label:
        return "neutral"
    return "info"


def _research_status_badge(label: str, tone: str) -> str:
    if not label:
        return badge_html("根拠未確認", "neutral")
    return badge_html(label, tone)


def _render_ranking_score_bar_chart(
    display_rows: list[dict[str, str]],
    ranking_purpose: str,
) -> None:
    frame = ranking_score_bar_chart_frame(display_rows, ranking_purpose=ranking_purpose)
    metric_column = str(frame.attrs.get("metric_column", "総合スコア"))
    sort_direction = str(frame.attrs.get("sort_direction", "desc"))
    render_section_heading(f"上位10件: {ranking_policy_label(ranking_purpose)}")
    st.caption(ranking_score_bar_chart_caption(ranking_purpose, metric_column, sort_direction))
    if frame.empty:
        st.info(f"{metric_column} をグラフ化できる候補がありません。")
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("score:Q", title=metric_column),
            y=alt.Y("label:N", sort=alt.SortField("bar_order", order="ascending"), title=None),
            tooltip=[
                alt.Tooltip("rank:N", title="順位"),
                alt.Tooltip("symbol:N", title="銘柄コード"),
                alt.Tooltip("name:N", title="銘柄名"),
                alt.Tooltip("score:Q", title=metric_column, format=".1f"),
            ],
            color=alt.value(CHART_COLORS["ai"]),
        )
        .properties(height=max(260, min(420, 34 * len(frame))))
    )
    st.altair_chart(style_altair_chart(chart), use_container_width=True)


def _render_ranking_confidence_scatter(display_rows: list[dict[str, str]]) -> None:
    frame = ranking_score_confidence_frame(display_rows)
    render_section_heading("スコア x データ信頼度")
    st.caption("投資スコアは比較用スコア、データ信頼度は評価に使えるデータの充実度です。")
    if frame.empty:
        st.info("スコアと評価信頼度を同時に表示できる候補がありません。")
        return
    chart = (
        alt.Chart(frame)
        .mark_circle(size=90, opacity=0.78)
        .encode(
            x=alt.X("score:Q", title="投資スコア"),
            y=alt.Y("confidence:Q", title="データ信頼度"),
            color=alt.Color(
                "confidence_band:N",
                title="データ確認",
                scale=alt.Scale(
                    domain=["信頼度高め", "データ確認"],
                    range=[THEME_COLORS["signal_buy"], THEME_COLORS["signal_hold"]],
                ),
            ),
            tooltip=[
                alt.Tooltip("rank:N", title="順位"),
                alt.Tooltip("symbol:N", title="銘柄コード"),
                alt.Tooltip("name:N", title="銘柄名"),
                alt.Tooltip("score:Q", title="投資スコア", format=".1f"),
                alt.Tooltip("confidence:Q", title="データ信頼度", format=".1f"),
                alt.Tooltip("caution:N", title="注意点"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(style_altair_chart(chart), use_container_width=True)
    st.caption("データ信頼度は投資魅力度ではなく、評価に使えるデータの充実度を示す補助指標です。")


def _render_ranking_profile_chart(
    display_rows: list[dict[str, str]],
    ranking_purpose: str,
) -> None:
    requested_profile = chart_profile_for_purpose(ranking_purpose)
    selection = ranking_chart_frame(display_rows, requested_profile)
    render_section_heading(selection.profile.title if selection else requested_profile.title)
    if selection is None:
        st.info(
            "この条件で使える既存列が不足しているため、メインチャートは表示していません。詳細表で候補を確認してください。"
        )
        return
    if selection.used_fallback:
        st.caption(
            "指定条件向けの列が不足している、または同じ値に偏っているため、"
            f"代替チャート `{selection.profile.title}` を表示しています。"
        )
    st.caption("選択中の評価方針とは別に、候補の期待・警戒バランスを確認する補助グラフです。")
    st.caption(selection.profile.description)
    with st.expander("読み方", expanded=False):
        for item in selection.profile.how_to_read:
            st.caption(f"- {item}")
        st.caption(selection.profile.caution)
    chart_tooltips = [
        alt.Tooltip("rank:N", title="順位"),
        alt.Tooltip("symbol:N", title="銘柄コード"),
        alt.Tooltip("name:N", title="銘柄名"),
        alt.Tooltip("x_value:Q", title=selection.x_column, format=".1f"),
        alt.Tooltip("y_value:Q", title=selection.y_column, format=".1f"),
        alt.Tooltip("caution:N", title="注意点"),
    ]
    if selection.color_column:
        chart_tooltips.insert(
            -1,
            alt.Tooltip("color_value:N", title=selection.color_column),
        )
    encoding = {
        "x": alt.X("x_value:Q", title=selection.x_column, scale=alt.Scale(zero=False)),
        "y": alt.Y("y_value:Q", title=selection.y_column, scale=alt.Scale(zero=False)),
        "tooltip": chart_tooltips,
    }
    color_is_numeric = (
        selection.color_column is not None
        and "color_numeric_value" in selection.frame
        and selection.frame["color_numeric_value"].notna().any()
    )
    if selection.color_column and color_is_numeric:
        numeric_color_range = [
            THEME_COLORS["signal_buy"],
            THEME_COLORS["signal_hold"],
            THEME_COLORS["signal_risk"],
        ]
        if selection.color_column in {
            "上昇気配",
            "Risk",
            "総合スコア",
            "Screening",
            "データ品質",
            "条件適合度",
            "DB信頼度",
        }:
            numeric_color_range = [
                THEME_COLORS["signal_risk"],
                THEME_COLORS["signal_hold"],
                THEME_COLORS["ai_cyan"],
            ]
        encoding["color"] = alt.Color(
            "color_numeric_value:Q",
            title=selection.color_column,
            scale=alt.Scale(domain=[0, 50, 100], range=numeric_color_range),
        )
    elif selection.color_column:
        encoding["color"] = alt.Color(
            "color_value:N",
            title=selection.color_column,
            scale=alt.Scale(
                range=[
                    THEME_COLORS["ai_cyan"],
                    THEME_COLORS["signal_buy"],
                    THEME_COLORS["signal_hold"],
                    THEME_COLORS["signal_risk"],
                    THEME_COLORS["ai_purple"],
                ]
            ),
        )
    else:
        encoding["color"] = alt.value(CHART_COLORS["ai"])
    chart = (
        alt.Chart(selection.frame)
        .mark_circle(size=90, opacity=0.78)
        .encode(**encoding)
        .properties(height=320)
    )
    st.altair_chart(style_altair_chart(chart), use_container_width=True)


def _render_selected_ranking_candidate_breakdown(
    display_rows: list[dict[str, str]],
    selected_symbol: str | None,
    ranking_purpose: str,
) -> None:
    render_section_heading("Selected Candidate Breakdown")
    st.caption("選択中の候補が上位にある理由を、主要スコアで確認します。")
    rows = ranking_candidate_breakdown_rows(
        display_rows,
        selected_symbol,
        ranking_purpose=ranking_purpose,
    )
    if not rows:
        st.info("内訳を表示する候補を選択してください。")
        return
    st.dataframe(rows, hide_index=True, use_container_width=True)
    selected_row = next(
        (row for row in display_rows if row.get("銘柄") == selected_symbol),
        None,
    )
    if selected_row and selected_row.get("補足"):
        st.caption(selected_row["補足"])


def _render_ranking_advanced_insights(
    display_rows: list[dict[str, str]],
    *,
    include_confidence_map: bool,
) -> None:
    with st.expander("補助分析を表示", expanded=False):
        scores = ranking_score_bar_chart_frame(display_rows, limit=len(display_rows))
        confidence_frame = ranking_score_confidence_frame(display_rows)
        if scores.empty and (not include_confidence_map or confidence_frame.empty):
            st.info("補助分析に使えるスコアがありません。")
            return
        st.caption("常時表示すると情報が多くなる補助分析です。必要な場合だけ開いて確認します。")
        if not scores.empty:
            histogram = (
                alt.Chart(scores)
                .mark_bar()
                .encode(
                    x=alt.X("score:Q", bin=alt.Bin(maxbins=12), title="投資スコア"),
                    y=alt.Y("count():Q", title="候補数"),
                    tooltip=[alt.Tooltip("count():Q", title="候補数")],
                    color=alt.value(CHART_COLORS["volume"]),
                )
                .properties(height=220)
            )
            st.altair_chart(style_altair_chart(histogram), use_container_width=True)
        if include_confidence_map and not confidence_frame.empty:
            st.divider()
            _render_ranking_confidence_scatter(display_rows)


def _render_ranking_score_explanation() -> None:
    with st.expander("総合スコアとは", expanded=False):
        st.markdown(
            """
総合スコアは、複数の投資指標を100点満点で統合した比較用スコアです。

- 割安性: PER、PBRなど
- 収益性: ROE、営業利益率など
- 財務安定性: 自己資本比率など
- 配当魅力: 配当利回りなど
- 成長性: 売上成長率など
- リスク: ボラティリティ、下降警戒など
- データ品質: 欠損や取得信頼性

このスコアは売買推奨ではなく、比較対象を絞るための参考指標です。
"""
        )


def _ranking_data_state_text(
    *,
    provider: str,
    rows: list[dict[str, str]],
    error_rows: list[dict[str, str]],
    updated_at: str,
) -> tuple[str, list[dict[str, str]]]:
    fetched_count = sum(1 for row in rows if str(row.get("取得元", "")).strip() not in {"", "N/A"})
    saved_count = max(0, len(rows) - fetched_count)
    failed_count = len(error_rows)
    if provider in LIVE_MARKET_DATA_PROVIDERS:
        if fetched_count and saved_count:
            status = "保存済みデータを表示中。一部銘柄は最新取得データを反映済み。"
        elif fetched_count:
            status = "最新取得データを表示中。"
        else:
            status = "保存済みデータを表示中。"
    else:
        status = "ローカル/保存済みデータを表示中。"
    rows_for_detail = [
        {"区分": "保存済み", "件数": str(saved_count)},
        {"区分": "最新反映", "件数": str(fetched_count)},
        {"区分": "取得失敗", "件数": str(failed_count)},
    ]
    if failed_count:
        rows_for_detail.append(
            {
                "区分": "補足",
                "件数": "取得失敗した銘柄は保存済みデータがあれば継続確認します。",
            }
        )
    last_updated = updated_at or "未取得"
    return f"現在のデータ: {status}  最終更新: {last_updated}", rows_for_detail


def _render_ranking_data_state(
    *,
    provider: str,
    display_rows: list[dict[str, str]],
    error_rows: list[dict[str, str]],
) -> None:
    updated_at = str(st.session_state.get(MARKET_DATA_RANKING_UPDATED_AT_STATE_KEY, "")).strip()
    state_text, detail_rows = _ranking_data_state_text(
        provider=provider,
        rows=display_rows,
        error_rows=error_rows,
        updated_at=updated_at,
    )
    st.caption(state_text)
    with st.expander("データ状態", expanded=False):
        st.dataframe(detail_rows, hide_index=True, use_container_width=True)
        st.caption("テーブル内のソート、検索、絞り込みでは外部取得を実行しません。")


def _render_ranking_result_table(
    display_rows: list[dict[str, str]],
    *,
    ranking_source: str,
    weight_preset: str,
    ranking_purpose: str,
) -> None:
    if not display_rows:
        st.info(EMPTY_STATE_MESSAGES["ranking_rows"])
        return
    table_base_key = _ranking_result_table_base_key(ranking_source, weight_preset)
    grid_key = _ranking_result_grid_key(table_base_key)
    st.caption("詳細確認用のテーブルです。銘柄データを見るには行をクリックしてください。")
    st.caption(RANKING_TABLE_SORT_GUIDANCE)
    frame = ranking_result_aggrid_frame(display_rows, ranking_purpose=ranking_purpose)
    grid_response = AgGrid(
        frame,
        gridOptions=ranking_result_aggrid_options(frame, ranking_purpose=ranking_purpose),
        height=_ranking_result_grid_height(display_rows),
        update_on=["rowClicked"],
        data_return_mode=DataReturnMode.AS_INPUT,
        theme="dark",
        custom_css=RANKING_RESULT_GRID_CUSTOM_CSS,
        key=grid_key,
        show_toolbar=False,
        show_search=False,
        show_download_button=False,
        allow_unsafe_jscode=True,
    )
    selected_symbol = ranking_detail_symbol_from_aggrid_response(grid_response)
    detail_event_token = ranking_detail_event_token_from_aggrid_response(
        grid_response,
        selected_symbol,
    )
    last_opened_key = f"{table_base_key}_last_opened_event_token"
    symbol_to_open = ranking_detail_symbol_to_open(
        selected_symbol,
        detail_event_token,
        st.session_state.get(last_opened_key),
    )
    if detail_event_token is None:
        st.session_state.pop(last_opened_key, None)
    elif symbol_to_open:
        st.session_state[last_opened_key] = detail_event_token
        _render_symbol_universe_detail_dialog(
            symbol_to_open,
            ranking_row=_ranking_display_row_for_symbol(display_rows, symbol_to_open),
        )


def _ranking_display_row_for_symbol(
    display_rows: list[dict[str, str]],
    symbol: str,
) -> dict[str, str] | None:
    normalized_symbol = symbol.strip().upper()
    for row in display_rows:
        if row.get("銘柄", "").strip().upper() == normalized_symbol:
            return row
    return None


def ranking_comparison_summary(
    *,
    start: date,
    end: date,
    candidate_count: int,
    selected_count: int,
) -> dict[str, str]:
    if candidate_count <= 0:
        status = "候補なし"
        selected = "0件"
    elif selected_count <= 0:
        status = "未選択"
        selected = f"0 / {candidate_count}件"
    elif selected_count >= candidate_count:
        status = "全候補を比較"
        selected = f"{candidate_count} / {candidate_count}件"
    else:
        status = "一部を比較"
        selected = f"{selected_count} / {candidate_count}件"
    return {
        "period": f"{start.isoformat()} 〜 {end.isoformat()}",
        "candidate": f"{max(candidate_count, 0)}件",
        "selected": selected,
        "status": status,
        "inline": (
            f"取得期間: {start.isoformat()} 〜 {end.isoformat()} / "
            f"候補: {max(candidate_count, 0)}件 / 選択: {selected}（{status}）"
        ),
    }


def _income_distribution_label(product_type: str) -> str:
    if product_type == RANKING_PRODUCT_ETF:
        return "分配金"
    if product_type == RANKING_PRODUCT_ALL:
        return "配当/分配金"
    return "配当"


def _dividend_category_filter_label(product_type: str) -> str:
    return f"{_income_distribution_label(product_type)}カテゴリ"


def _dividend_yield_filter_label(product_type: str) -> str:
    return f"{_income_distribution_label(product_type)}利回り(%)"


def _dividend_filter_help_text(help_text: str, product_type: str) -> str:
    return help_text.replace("配当", _income_distribution_label(product_type))


def _dividend_category_option_label(value: str, product_type: str) -> str:
    return _dividend_filter_help_text(RANKING_DIVIDEND_LABELS[value], product_type)


def _render_ranking_filter_panel() -> None:
    has_ranking_result = bool(st.session_state.get(MARKET_DATA_RANKING_STATE_KEY))
    region = _ranking_filter_value("market_data_ranking_region", "japan")
    product_type = _ranking_filter_value("market_data_ranking_product_type", "stock")
    detail_filters = set(ranking_detail_filters_for_category(region, product_type))
    if "dividend_yield" in detail_filters:
        _normalize_dividend_filter_state()
    with st.expander("詳細条件", expanded=not has_ranking_result):
        st.caption("ここは候補を絞る条件です。上の並べ替え設定とは別に使います。")

        st.markdown("**属性条件**")
        columns = st.columns(4)
        column_index = 0
        dividend_category_value = _ranking_filter_value("market_data_ranking_dividend", "all")
        dividend_range_enabled = _ranking_filter_bool("market_data_ranking_dividend_enabled", False)
        dividend_category_disabled = dividend_range_enabled
        dividend_range_disabled = dividend_category_value != "all"

        def next_column():
            nonlocal column_index
            column = columns[column_index % len(columns)]
            column_index += 1
            return column

        if "industry_or_sector" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "業種/テーマ",
                    options=list(RANKING_THEME_LABELS),
                    key="market_data_ranking_theme",
                    format_func=lambda value: RANKING_THEME_LABELS[value],
                    help_text=RANKING_FILTER_HELP_TEXTS["industry_or_sector"],
                )
        if "market_cap" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "時価総額",
                    options=list(RANKING_MARKET_CAP_LABELS),
                    key="market_data_ranking_market_cap",
                    format_func=lambda value: RANKING_MARKET_CAP_LABELS[value],
                    help_text=RANKING_FILTER_HELP_TEXTS["market_cap"],
                )
        if "risk_band" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "市場感応度（β）",
                    options=list(RANKING_BETA_RISK_LABELS),
                    key="market_data_ranking_risk_band",
                    format_func=lambda value: RANKING_BETA_RISK_LABELS[value],
                    help_text=RANKING_FILTER_HELP_TEXTS["risk_band"],
                )
        if "nisa_eligibility" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "NISA",
                    options=list(RANKING_NISA_ELIGIBILITY_LABELS),
                    key="market_data_ranking_nisa",
                    format_func=lambda value: RANKING_NISA_ELIGIBILITY_LABELS[value],
                    help_text=RANKING_FILTER_HELP_TEXTS["nisa_eligibility"],
                )
        if "benchmark_index" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "連動指数",
                    options=list(RANKING_INDEX_FAMILY_LABELS),
                    key="market_data_ranking_index_family",
                    format_func=lambda value: RANKING_INDEX_FAMILY_LABELS[value],
                    help_text=RANKING_FILTER_HELP_TEXTS["benchmark_index"],
                )
        if "expense_ratio" in detail_filters:
            with next_column():
                st.number_input(
                    "信託報酬/経費率(%)以下",
                    min_value=0.0,
                    max_value=2.0,
                    value=float(_ranking_filter_value("market_data_ranking_max_expense", "1.00")),
                    step=0.01,
                    key="market_data_ranking_max_expense",
                    help=RANKING_FILTER_HELP_TEXTS["expense_ratio"],
                )
        if "complexity" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "複雑さ",
                    options=list(RANKING_COMPLEXITY_LABELS),
                    key="market_data_ranking_complexity",
                    format_func=lambda value: RANKING_COMPLEXITY_LABELS[value],
                    help_text=RANKING_FILTER_HELP_TEXTS["complexity"],
                )
        if "dividend_yield" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    _dividend_category_filter_label(product_type),
                    options=list(RANKING_DIVIDEND_LABELS),
                    key="market_data_ranking_dividend",
                    format_func=lambda value: _dividend_category_option_label(
                        value,
                        product_type,
                    ),
                    help_text=_dividend_filter_help_text(
                        RANKING_FILTER_HELP_TEXTS["dividend_category"],
                        product_type,
                    ),
                    disabled=dividend_category_disabled,
                )
        with next_column():
            _render_detail_selectbox(
                "通貨",
                options=list(RANKING_CURRENCY_LABELS),
                key="market_data_ranking_currency",
                format_func=lambda value: RANKING_CURRENCY_LABELS[value],
                help_text=RANKING_FILTER_HELP_TEXTS["currency"],
            )

        metric_filters: list[tuple[str, dict[str, object]]] = []
        if "dividend_yield" in detail_filters:
            metric_filters.append(
                (
                    _dividend_yield_filter_label(product_type),
                    {
                        "enabled_key": "market_data_ranking_dividend_enabled",
                        "min_key": "market_data_ranking_min_dividend",
                        "max_key": "market_data_ranking_dividend_max",
                        "min_default": "3.0",
                        "max_default": "10.0",
                        "max_value": 15.0,
                        "help_text": _dividend_filter_help_text(
                            RANKING_FILTER_HELP_TEXTS["dividend_yield"],
                            product_type,
                        ),
                        "disabled": dividend_range_disabled,
                    },
                )
            )
        if "per" in detail_filters:
            metric_filters.append(
                (
                    "PER",
                    {
                        "enabled_key": "market_data_ranking_per_enabled",
                        "min_key": "market_data_ranking_per_min",
                        "max_key": "market_data_ranking_per_max",
                        "min_default": "2.0",
                        "max_default": "20.0",
                        "max_value": 80.0,
                        "help_text": RANKING_FILTER_HELP_TEXTS["per"],
                    },
                )
            )
        if "pbr" in detail_filters:
            metric_filters.append(
                (
                    "PBR",
                    {
                        "enabled_key": "market_data_ranking_pbr_enabled",
                        "min_key": "market_data_ranking_pbr_min",
                        "max_key": "market_data_ranking_pbr_max",
                        "min_default": "0.5",
                        "max_default": "2.0",
                        "max_value": 20.0,
                        "help_text": RANKING_FILTER_HELP_TEXTS["pbr"],
                    },
                )
            )
        if "roe" in detail_filters:
            metric_filters.append(
                (
                    "ROE(%)",
                    {
                        "enabled_key": "market_data_ranking_roe_enabled",
                        "min_key": "market_data_ranking_roe_min",
                        "max_key": "market_data_ranking_roe_max",
                        "min_default": "8.0",
                        "max_default": "30.0",
                        "max_value": 60.0,
                        "help_text": RANKING_FILTER_HELP_TEXTS["roe"],
                    },
                )
            )
        if metric_filters:
            st.markdown("**数値条件**")
            _render_metric_filter_grid(metric_filters)

        st.markdown("**キーワード検索**")
        col_keyword, col_clear = st.columns([3.0, 0.8])
        with col_keyword:
            st.text_input(
                "キーワード",
                value=_ranking_filter_value("market_data_ranking_symbol_query", ""),
                key="market_data_ranking_symbol_query",
                placeholder="銘柄コード、会社名、テーマ",
                help=RANKING_FILTER_HELP_TEXTS["keyword"],
            )
        with col_clear:
            st.button("クリアする", on_click=clear_ranking_filter_state)


def _render_cockpit_symbol_filter_panel(
    symbol_options: list[dict[str, str]],
) -> list[dict[str, str]]:
    with st.expander(
        "銘柄候補フィルター",
        expanded=False,
    ):
        st.caption(
            "銘柄候補を好みの条件で絞ります。取得期間や予測計算ではなく、候補リストだけに効きます。"
        )
        col_region, col_product, col_nisa, col_clear = st.columns([1.0, 1.0, 1.0, 0.8])
        with col_region:
            region = _render_detail_selectbox(
                "地域",
                options=list(RANKING_MVP_REGION_LABELS),
                key="market_data_cockpit_region",
                format_func=lambda value: RANKING_MVP_REGION_LABELS[value],
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_region"]
                ),
                help_text="候補に含める市場地域です。国内株、米国株、全体から選びます。",
            )
        with col_product:
            product_type = _render_detail_selectbox(
                "商品",
                options=list(RANKING_MVP_PRODUCT_TYPE_LABELS),
                key="market_data_cockpit_product_type",
                format_func=lambda value: RANKING_MVP_PRODUCT_TYPE_LABELS[value],
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_product_type"]
                ),
                help_text="指定なしなら商品では絞らず、個別株かETFを選ぶと候補を絞ります。",
            )
        with col_nisa:
            nisa_eligibility = _render_detail_selectbox(
                "NISA",
                options=list(RANKING_NISA_ELIGIBILITY_LABELS),
                key="market_data_cockpit_nisa",
                format_func=lambda value: RANKING_NISA_ELIGIBILITY_LABELS[value],
                default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_nisa"]),
                help_text=RANKING_FILTER_HELP_TEXTS["nisa_eligibility"],
            )
        with col_clear:
            st.write("")
            st.button("クリア", on_click=_clear_cockpit_symbol_filter_state)

        st.markdown("**属性条件**")
        attr_cols = st.columns(5)
        with attr_cols[0]:
            theme = _render_detail_selectbox(
                "業種/テーマ",
                options=list(RANKING_THEME_LABELS),
                key="market_data_cockpit_theme",
                format_func=lambda value: RANKING_THEME_LABELS[value],
                default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_theme"]),
                help_text=RANKING_FILTER_HELP_TEXTS["industry_or_sector"],
            )
        with attr_cols[1]:
            market_cap_tier = _render_detail_selectbox(
                "時価総額",
                options=list(RANKING_MARKET_CAP_LABELS),
                key="market_data_cockpit_market_cap",
                format_func=lambda value: RANKING_MARKET_CAP_LABELS[value],
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_market_cap"]
                ),
                help_text=RANKING_FILTER_HELP_TEXTS["market_cap"],
            )
        with attr_cols[2]:
            risk_band = _render_detail_selectbox(
                "市場感応度（β）",
                options=list(RANKING_BETA_RISK_LABELS),
                key="market_data_cockpit_risk_band",
                format_func=lambda value: RANKING_BETA_RISK_LABELS[value],
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_risk_band"]
                ),
                help_text=RANKING_FILTER_HELP_TEXTS["risk_band"],
            )
        with attr_cols[3]:
            dividend_category = _render_detail_selectbox(
                _dividend_category_filter_label(product_type),
                options=list(RANKING_DIVIDEND_LABELS),
                key="market_data_cockpit_dividend",
                format_func=lambda value: _dividend_category_option_label(value, product_type),
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_dividend"]
                ),
                help_text=_dividend_filter_help_text(
                    RANKING_FILTER_HELP_TEXTS["dividend_category"],
                    product_type,
                ),
                disabled=_cockpit_filter_bool("market_data_cockpit_dividend_enabled", False),
            )
        with attr_cols[4]:
            currency = _render_detail_selectbox(
                "通貨",
                options=list(RANKING_CURRENCY_LABELS),
                key="market_data_cockpit_currency",
                format_func=lambda value: RANKING_CURRENCY_LABELS[value],
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_currency"]
                ),
                help_text=RANKING_FILTER_HELP_TEXTS["currency"],
            )

        st.markdown("**数値条件**")
        metric_cols = st.columns(2)
        with metric_cols[0]:
            dividend_enabled, min_dividend, max_dividend = _render_metric_range_filter(
                _dividend_yield_filter_label(product_type),
                enabled_key="market_data_cockpit_dividend_enabled",
                min_key="market_data_cockpit_min_dividend",
                max_key="market_data_cockpit_dividend_max",
                min_default="0.0",
                max_default="10.0",
                max_value=15.0,
                help_text=_dividend_filter_help_text(
                    RANKING_FILTER_HELP_TEXTS["dividend_yield"],
                    product_type,
                ),
                disabled=dividend_category != "all",
            )
        with metric_cols[1]:
            per_enabled, per_min, per_max = _render_metric_range_filter(
                "PER",
                enabled_key="market_data_cockpit_per_enabled",
                min_key="market_data_cockpit_per_min",
                max_key="market_data_cockpit_per_max",
                min_default="2.0",
                max_default="20.0",
                max_value=80.0,
                help_text=RANKING_FILTER_HELP_TEXTS["per"],
            )
        metric_cols = st.columns(2)
        with metric_cols[0]:
            pbr_enabled, pbr_min, pbr_max = _render_metric_range_filter(
                "PBR",
                enabled_key="market_data_cockpit_pbr_enabled",
                min_key="market_data_cockpit_pbr_min",
                max_key="market_data_cockpit_pbr_max",
                min_default="0.5",
                max_default="2.0",
                max_value=20.0,
                help_text=RANKING_FILTER_HELP_TEXTS["pbr"],
            )
        with metric_cols[1]:
            roe_enabled, roe_min, roe_max = _render_metric_range_filter(
                "ROE(%)",
                enabled_key="market_data_cockpit_roe_enabled",
                min_key="market_data_cockpit_roe_min",
                max_key="market_data_cockpit_roe_max",
                min_default="8.0",
                max_default="30.0",
                max_value=60.0,
                help_text=RANKING_FILTER_HELP_TEXTS["roe"],
            )
        filtered_rows = cockpit_filtered_symbol_rows_from_values(
            symbol_options,
            region=region,
            product_type=product_type,
            currency=currency,
            dividend_category=dividend_category,
            market_cap_tier=market_cap_tier,
            nisa_eligibility=nisa_eligibility,
            risk_band=risk_band,
            theme=theme,
            dividend_yield_enabled=dividend_enabled,
            min_dividend_yield_pct=min_dividend,
            dividend_yield_max_pct=max_dividend,
            per_enabled=per_enabled,
            per_min=per_min,
            per_max=per_max,
            pbr_enabled=pbr_enabled,
            pbr_min=pbr_min,
            pbr_max=pbr_max,
            roe_enabled=roe_enabled,
            roe_min_pct=roe_min,
            roe_max_pct=roe_max,
        )
        if filtered_rows:
            st.caption(f"現在の候補: {len(filtered_rows)} / {len(symbol_options)}件")
        else:
            st.warning("条件に合う銘柄候補がありません。条件を緩めるか、クリアしてください。")
    return filtered_rows


def cockpit_filtered_symbol_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return cockpit_filtered_symbol_rows_from_values(
        rows,
        region=_cockpit_filter_value("market_data_cockpit_region", "all"),
        product_type=_cockpit_filter_value("market_data_cockpit_product_type", "all"),
        currency=_cockpit_filter_value("market_data_cockpit_currency", "all"),
        dividend_category=_cockpit_filter_value("market_data_cockpit_dividend", "all"),
        market_cap_tier=_cockpit_filter_value("market_data_cockpit_market_cap", "all"),
        nisa_eligibility=_cockpit_filter_value("market_data_cockpit_nisa", "all"),
        risk_band=_cockpit_filter_value("market_data_cockpit_risk_band", "all"),
        theme=_cockpit_filter_value("market_data_cockpit_theme", "all"),
        dividend_yield_enabled=_cockpit_filter_bool(
            "market_data_cockpit_dividend_enabled",
            False,
        ),
        min_dividend_yield_pct=_cockpit_filter_value(
            "market_data_cockpit_min_dividend",
            "0.0",
        ),
        dividend_yield_max_pct=_cockpit_filter_value(
            "market_data_cockpit_dividend_max",
            "10.0",
        ),
        per_enabled=_cockpit_filter_bool("market_data_cockpit_per_enabled", False),
        per_min=_cockpit_filter_value("market_data_cockpit_per_min", "2.0"),
        per_max=_cockpit_filter_value("market_data_cockpit_per_max", "20.0"),
        pbr_enabled=_cockpit_filter_bool("market_data_cockpit_pbr_enabled", False),
        pbr_min=_cockpit_filter_value("market_data_cockpit_pbr_min", "0.5"),
        pbr_max=_cockpit_filter_value("market_data_cockpit_pbr_max", "2.0"),
        roe_enabled=_cockpit_filter_bool("market_data_cockpit_roe_enabled", False),
        roe_min_pct=_cockpit_filter_value("market_data_cockpit_roe_min", "8.0"),
        roe_max_pct=_cockpit_filter_value("market_data_cockpit_roe_max", "30.0"),
    )


def cockpit_filtered_symbol_rows_from_values(
    rows: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
    currency: str,
    dividend_category: str,
    market_cap_tier: str,
    nisa_eligibility: str,
    risk_band: str,
    theme: str,
    dividend_yield_enabled: bool,
    min_dividend_yield_pct: Decimal | str | int | float,
    dividend_yield_max_pct: Decimal | str | int | float,
    per_enabled: bool,
    per_min: Decimal | str | int | float,
    per_max: Decimal | str | int | float,
    pbr_enabled: bool,
    pbr_min: Decimal | str | int | float,
    pbr_max: Decimal | str | int | float,
    roe_enabled: bool,
    roe_min_pct: Decimal | str | int | float,
    roe_max_pct: Decimal | str | int | float,
) -> list[dict[str, str]]:
    return filter_symbol_universe_rows(
        rows,
        region=region,
        product_type=product_type,
        currency=currency,
        dividend_category=dividend_category,
        market_cap_tier=market_cap_tier,
        nisa_eligibility=nisa_eligibility,
        risk_band=risk_band,
        theme=theme,
        dividend_yield_enabled=dividend_yield_enabled,
        min_dividend_yield_pct=str(min_dividend_yield_pct),
        dividend_yield_max_pct=str(dividend_yield_max_pct),
        per_enabled=per_enabled,
        per_min=str(per_min),
        per_max=str(per_max),
        pbr_enabled=pbr_enabled,
        pbr_min=str(pbr_min),
        pbr_max=str(pbr_max),
        roe_enabled=roe_enabled,
        roe_min_pct=str(roe_min_pct),
        roe_max_pct=str(roe_max_pct),
        limit=len(rows),
        apply_universe_policy=False,
        active_detail_filters=MARKET_DATA_COCKPIT_DETAIL_FILTERS,
    )


def _cockpit_filter_value(key: str, default: str) -> str:
    value = st.session_state.get(key, MARKET_DATA_COCKPIT_FILTER_DEFAULTS.get(key, default))
    return str(value) if value is not None else default


def _cockpit_filter_bool(key: str, default: bool) -> bool:
    value = st.session_state.get(key, MARKET_DATA_COCKPIT_FILTER_DEFAULTS.get(key, default))
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def _clear_cockpit_symbol_filter_state() -> None:
    for key in MARKET_DATA_COCKPIT_FILTER_DEFAULTS:
        st.session_state.pop(key, None)
    st.session_state.pop("market_data_symbol_candidate", None)


def _current_or_default_symbol_labels(symbol_options: list[dict[str, str]]) -> list[str]:
    labels = symbol_candidate_labels(symbol_options)
    return labels[:1] if labels else [NO_SYMBOL_CANDIDATE_LABEL]


def merged_symbol_candidate_rows(
    reference_rows: list[dict[str, str]],
    live_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge representative and live-search symbol candidates without duplicates."""

    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in [*reference_rows, *live_rows]:
        symbol = row.get("symbol", "").strip()
        name = row.get("name", "").strip() or symbol
        normalized_symbol = symbol.upper()
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        merged.append({"symbol": symbol, "name": name})
    return merged


def _render_market_data_preview() -> None:
    _render_market_data_cockpit()


def _render_market_data_cockpit() -> None:
    render_page_title(
        "銘柄コックピット",
        "1銘柄の価格、予測、投資スコア、注意点を確認します。",
        "cockpit",
    )
    symbol_options = symbol_universe_rows()
    filtered_symbol_options = _render_cockpit_symbol_filter_panel(symbol_options)
    col_provider, col_search, col_symbol, col_detail, col_name = st.columns(
        [1.0, 1.35, 1.75, 0.95, 1.35]
    )
    with col_provider:
        provider = cast(
            str,
            st.selectbox(
                "データ取得元",
                MARKET_DATA_PROVIDER_OPTIONS,
                index=_provider_option_index(default_market_data_provider()),
                key=MARKET_DATA_PROVIDER_WIDGET_KEY,
            ),
        )
        if provider in LIVE_MARKET_DATA_PROVIDERS:
            st.caption("Yahooからライブデータを取得します。")
    with col_search:
        symbol_query = st.text_input(
            "銘柄検索",
            value="",
            key="market_data_symbol_search",
            placeholder="銘柄コードまたは会社名",
        )
    with col_symbol:
        live_symbol_options = (
            yfinance_search_symbol_rows(symbol_query) if symbol_query.strip() else []
        )
        candidate_rows = merged_symbol_candidate_rows(filtered_symbol_options, live_symbol_options)
        symbol_option_labels = symbol_candidate_labels(candidate_rows, symbol_query)
        if not symbol_option_labels:
            symbol_option_labels = [NO_SYMBOL_CANDIDATE_LABEL]
        _ensure_selectbox_state_value("market_data_symbol_candidate", symbol_option_labels)
        symbol_candidate = cast(
            str,
            st.selectbox(
                "銘柄",
                symbol_option_labels,
                index=_selectbox_index(
                    symbol_option_labels,
                    str(
                        st.session_state.get(
                            "market_data_symbol_candidate", symbol_option_labels[0]
                        )
                    ),
                ),
                key="market_data_symbol_candidate",
                placeholder="銘柄コードまたは会社名",
            ),
        )
    symbol = _symbol_from_candidate(symbol_candidate) or ""
    with col_detail:
        st.write("")
        if selected_symbol_has_universe_detail(symbol):
            if st.button(
                "銘柄データを見る",
                key="market_data_open_symbol_detail",
                help=("ローカル銘柄マスタに登録されている" "選択中の銘柄データを確認します。"),
                use_container_width=True,
            ):
                _render_symbol_universe_detail_dialog(symbol)
        else:
            st.caption("銘柄データ未登録")
    with col_name:
        company_name = symbol_name(symbol) or _name_from_candidate(symbol_candidate) or ""
        st.text_input("銘柄名", value=company_name, disabled=True, key="market_data_symbol_name")
    col_period, col_start, col_end, _ = st.columns([1.2, 1.0, 1.0, 3.8])
    with col_period:
        period_preset = cast(
            str,
            st.selectbox(
                "取得期間",
                list(MARKET_DATA_PERIOD_PRESETS),
                index=list(MARKET_DATA_PERIOD_PRESETS).index(DEFAULT_MARKET_DATA_PERIOD_PRESET),
                format_func=lambda value: MARKET_DATA_PERIOD_PRESETS[value],
                key="market_data_period_preset",
                help=(
                    "投資判断の補助として、短期は材料反応、中期はトレンド、"
                    "長期は下落耐性や構造変化を確認します。"
                ),
            ),
        )
        st.caption(market_data_period_help(period_preset))
    default_end = default_market_data_end_date()
    preset_start, preset_end = market_data_period_dates(period_preset, default_end)
    is_custom_period = period_preset == MARKET_DATA_PERIOD_CUSTOM
    with col_start:
        if is_custom_period:
            start = st.date_input(
                "開始日",
                value=default_market_data_start_date(),
                key="market_data_start",
            )
        else:
            start = preset_start
            st.text_input(
                "開始日",
                value=preset_start.isoformat(),
                disabled=True,
                key="market_data_start_preview",
            )
    with col_end:
        if is_custom_period:
            end = st.date_input(
                "終了日",
                value=default_end,
                key="market_data_end",
            )
        else:
            end = preset_end
            st.text_input(
                "終了日",
                value=preset_end.isoformat(),
                disabled=True,
                key="market_data_end_preview",
            )

    if st.button(
        "データを取得",
        key="fetch_market_data",
        disabled=not symbol,
        type="primary",
        help="選択した銘柄と取得期間で、価格・予測・投資スコアを再計算します。",
    ):
        loading_slot = st.empty()
        try:
            start_date = _single_date_from_input(start)
            end_date = _single_date_from_input(end)
            forecast_horizon_days = default_forecast_horizon_days(start_date, end_date)
            st.session_state[MARKET_DATA_FORECAST_DAYS_STATE_KEY] = forecast_horizon_days
            with loading_slot.container():
                render_mascot_loading(
                    "cockpit",
                    title="市場データを取得中",
                    message="価格、予測、スコアの材料をまとめています。少しだけお待ちください。",
                    tone="forecast",
                )
            preview = asyncio.run(
                build_market_data_preview(
                    symbol=symbol.strip(),
                    start=start_date,
                    end=end_date,
                    provider_override=provider,
                    forecast_horizon_days=forecast_horizon_days,
                )
            )
        except ValueError as exc:
            loading_slot.empty()
            st.error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            loading_slot.empty()
            st.error(str(exc))
            return

        loading_slot.empty()
        st.session_state[MARKET_DATA_PREVIEW_STATE_KEY] = preview
        st.session_state[MARKET_DATA_STATUS_STATE_KEY] = preview.status
        if preview.status == "OK":
            st.session_state[MARKET_DATA_TOAST_STATE_KEY] = "データを取得しました。"

    stored_preview = _market_data_preview_from_state()
    if stored_preview is None:
        render_mascot_panel(
            "empty",
            message="銘柄、取得期間、データ取得元を選んでデータを取得すると、確認ポイントをまとめます。",
            layout="compact",
        )
        return

    toast_message = st.session_state.pop(MARKET_DATA_TOAST_STATE_KEY, None)
    if toast_message:
        st.toast(str(toast_message), icon="✅")

    if st.session_state.get(MARKET_DATA_STATUS_STATE_KEY) != "OK":
        st.error("価格データを取得できませんでした。")
        _render_provider_error_summary(stored_preview.error_rows)
        return

    _render_market_data_preview_result(stored_preview)


def _render_market_data_ranking() -> None:
    render_page_title(
        "銘柄ランキング",
        "複数銘柄を比較し、深掘り候補を整理します。売買推奨ではありません。",
        "ranking",
    )
    symbol_options = symbol_universe_rows()
    purpose = "all"

    st.markdown("#### 比較対象")
    col_region, col_product = st.columns(2)
    with col_region:
        region_options = list(RANKING_MVP_REGION_LABELS)
        _ensure_selectbox_state_value("market_data_ranking_region", region_options)
        region = cast(
            str,
            st.selectbox(
                "地域",
                region_options,
                index=_selectbox_index(
                    region_options,
                    _ranking_filter_value("market_data_ranking_region", "japan"),
                ),
                key="market_data_ranking_region",
                format_func=ranking_region_label,
            ),
        )
    with col_product:
        product_options = list(RANKING_MVP_PRODUCT_TYPE_LABELS)
        _ensure_selectbox_state_value("market_data_ranking_product_type", product_options)
        product_type = cast(
            str,
            st.selectbox(
                "商品",
                product_options,
                index=_selectbox_index(
                    product_options,
                    _ranking_filter_value("market_data_ranking_product_type", "stock"),
                ),
                key="market_data_ranking_product_type",
                format_func=ranking_product_type_label,
            ),
        )
    _sync_ranking_policy_state(product_type)
    ranking_policy = _ranking_filter_value(
        "market_data_ranking_policy",
        RANKING_PURPOSE_MULTI_FACTOR,
    )
    st.markdown("#### 取得条件")
    col_period, col_provider = st.columns(2)
    with col_period:
        period_options = list(RANKING_PERIOD_PRESETS)
        _ensure_selectbox_state_value("market_data_ranking_period", period_options)
        st.selectbox(
            "取得期間",
            period_options,
            index=_selectbox_index(
                period_options,
                _ranking_filter_value(
                    "market_data_ranking_period",
                    RANKING_DEFAULT_PERIOD_PRESET,
                ),
            ),
            key="market_data_ranking_period",
            format_func=ranking_period_label,
            help=RANKING_FILTER_HELP_TEXTS["period"],
        )
    with col_provider:
        provider = cast(
            str,
            st.selectbox(
                "データ取得元",
                MARKET_DATA_PROVIDER_OPTIONS,
                index=_provider_option_index(default_market_data_provider()),
                key=MARKET_DATA_RANKING_PROVIDER_WIDGET_KEY,
            ),
        )
        if provider in LIVE_MARKET_DATA_PROVIDERS:
            st.caption("Yahooからライブデータを取得してランキングを作成します。")
    policy_preset = ranking_weight_preset_for_purpose(ranking_policy)
    st.caption(
        f"評価方針: {ranking_policy_label(ranking_policy)} / "
        f"評価プロファイル: {ranking_weight_preset_label(policy_preset)}。"
        "候補は選択中の評価方針スコア順に表示されます。"
    )
    _render_ranking_filter_panel()

    period_preset = _ranking_filter_value(
        "market_data_ranking_period",
        RANKING_DEFAULT_PERIOD_PRESET,
    )
    market = "all"
    asset_type = "all"
    currency = _ranking_filter_value("market_data_ranking_currency", "all")
    dividend_category = _ranking_filter_value("market_data_ranking_dividend", "all")
    min_dividend_yield_pct = _ranking_filter_value("market_data_ranking_min_dividend", "0.0")
    market_cap_tier = _ranking_filter_value("market_data_ranking_market_cap", "all")
    index_family = _ranking_filter_value("market_data_ranking_index_family", "all")
    max_expense_ratio_pct = _ranking_filter_value("market_data_ranking_max_expense", "1.00")
    complexity = _ranking_filter_value("market_data_ranking_complexity", "standard")
    nisa_eligibility = _ranking_filter_value("market_data_ranking_nisa", "all")
    risk_band = _ranking_filter_value("market_data_ranking_risk_band", "all")
    theme = _ranking_filter_value("market_data_ranking_theme", "all")
    symbol_query = _ranking_filter_value("market_data_ranking_symbol_query", "")
    per_enabled = _ranking_filter_bool("market_data_ranking_per_enabled", False)
    per_min = _ranking_filter_value("market_data_ranking_per_min", "2.0")
    per_max = _ranking_filter_value("market_data_ranking_per_max", "20.0")
    pbr_enabled = _ranking_filter_bool("market_data_ranking_pbr_enabled", False)
    pbr_min = _ranking_filter_value("market_data_ranking_pbr_min", "0.5")
    pbr_max = _ranking_filter_value("market_data_ranking_pbr_max", "2.0")
    dividend_yield_enabled = _ranking_filter_bool("market_data_ranking_dividend_enabled", False)
    dividend_yield_max_pct = _ranking_filter_value("market_data_ranking_dividend_max", "10.0")
    roe_enabled = _ranking_filter_bool("market_data_ranking_roe_enabled", False)
    roe_min_pct = _ranking_filter_value("market_data_ranking_roe_min", "8.0")
    roe_max_pct = _ranking_filter_value("market_data_ranking_roe_max", "30.0")
    consensus_enabled = _ranking_filter_bool("market_data_ranking_consensus_enabled", False)
    consensus_min = _ranking_filter_value("market_data_ranking_consensus_min", "2.5")
    consensus_max = _ranking_filter_value("market_data_ranking_consensus_max", "5.0")
    filtered_symbol_rows = filter_symbol_universe_rows(
        symbol_options,
        region=region,
        product_type=product_type,
        ranking_purpose=RANKING_PURPOSE_MULTI_FACTOR,
        purpose=purpose,
        market=market,
        asset_type=asset_type,
        currency=currency,
        dividend_category=dividend_category,
        min_dividend_yield_pct=min_dividend_yield_pct,
        market_cap_tier=market_cap_tier,
        index_family=index_family,
        max_expense_ratio_pct=max_expense_ratio_pct,
        complexity=complexity,
        nisa_eligibility=nisa_eligibility,
        risk_band=risk_band,
        theme=theme,
        query=symbol_query,
        per_enabled=per_enabled,
        per_min=per_min,
        per_max=per_max,
        pbr_enabled=pbr_enabled,
        pbr_min=pbr_min,
        pbr_max=pbr_max,
        dividend_yield_enabled=dividend_yield_enabled,
        dividend_yield_max_pct=dividend_yield_max_pct,
        roe_enabled=roe_enabled,
        roe_min_pct=roe_min_pct,
        roe_max_pct=roe_max_pct,
        consensus_enabled=consensus_enabled,
        consensus_min=consensus_min,
        consensus_max=consensus_max,
        limit=len(symbol_options),
    )
    labels = symbol_candidate_labels(filtered_symbol_rows)
    filter_signature = ranking_filter_signature(
        region=region,
        product_type=product_type,
        ranking_purpose=RANKING_PURPOSE_MULTI_FACTOR,
        purpose=purpose,
        period_preset=period_preset,
        market=market,
        asset_type=asset_type,
        currency=currency,
        dividend_category=dividend_category,
        min_dividend_yield_pct=min_dividend_yield_pct,
        market_cap_tier=market_cap_tier,
        index_family=index_family,
        max_expense_ratio_pct=max_expense_ratio_pct,
        complexity=complexity,
        nisa_eligibility=nisa_eligibility,
        risk_band=risk_band,
        theme=theme,
        query=symbol_query,
        per_enabled=per_enabled,
        per_min=per_min,
        per_max=per_max,
        pbr_enabled=pbr_enabled,
        pbr_min=pbr_min,
        pbr_max=pbr_max,
        dividend_yield_enabled=dividend_yield_enabled,
        dividend_yield_max_pct=dividend_yield_max_pct,
        roe_enabled=roe_enabled,
        roe_min_pct=roe_min_pct,
        roe_max_pct=roe_max_pct,
        consensus_enabled=consensus_enabled,
        consensus_min=consensus_min,
        consensus_max=consensus_max,
        limit=0,
    )
    selection_key = ranking_symbols_state_key(filter_signature)
    stored_selected_labels = cast(
        list[str],
        st.session_state.get(MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY, []),
    )
    ensure_ranking_selection_widget_state(
        selection_key=selection_key,
        labels=labels,
        stored_selected_labels=stored_selected_labels,
    )
    selected_labels_for_summary = cast(list[str], st.session_state.get(selection_key, []))
    end_date = default_market_data_end_date()
    start_date, end_date = ranking_period_dates(period_preset, end_date)
    comparison_summary = ranking_comparison_summary(
        start=start_date,
        end=end_date,
        candidate_count=len(filtered_symbol_rows),
        selected_count=len(selected_labels_for_summary),
    )
    st.caption(comparison_summary["inline"])

    expander_label = f"比較する銘柄を確認・変更（{comparison_summary['selected']}）"
    with st.expander(expander_label, expanded=False):
        st.caption("候補は初期状態ですべて選択されています。変更する場合だけ開いてください。")
        selected_labels = cast(
            list[str],
            st.multiselect(
                "比較する銘柄",
                labels,
                key=selection_key,
            ),
        )
    if not labels:
        st.warning("この条件に合う候補がありません。候補条件を広げてください。")

    action_policy_col, action_limit_col, action_button_col, _action_spacer = st.columns(
        [1.55, 1.0, 0.75, 1.9]
    )
    with action_policy_col:
        policy_options = ranking_policy_options(product_type)
        _ensure_selectbox_state_value("market_data_ranking_policy", policy_options)
        ranking_policy = cast(
            str,
            st.selectbox(
                "評価方針",
                policy_options,
                index=_selectbox_index(
                    policy_options,
                    _ranking_filter_value(
                        "market_data_ranking_policy",
                        RANKING_PURPOSE_MULTI_FACTOR,
                    ),
                ),
                key="market_data_ranking_policy",
                format_func=ranking_policy_label,
                help=(
                    "どの観点で候補を評価するかを選びます。"
                    "上位候補・グラフ・確認メモは、この評価方針に基づいて表示されます。"
                ),
            ),
        )
    policy_preset = ranking_weight_preset_for_purpose(ranking_policy)
    with action_limit_col:
        fetch_limit_options = list(RANKING_FETCH_LIMIT_LABELS)
        _ensure_selectbox_state_value("market_data_ranking_fetch_limit", fetch_limit_options)
        fetch_limit = cast(
            str,
            st.selectbox(
                "作成対象",
                fetch_limit_options,
                index=_selectbox_index(
                    fetch_limit_options,
                    _ranking_filter_value("market_data_ranking_fetch_limit", "balanced_300"),
                ),
                key="market_data_ranking_fetch_limit",
                format_func=ranking_fetch_limit_label,
                help=(
                    "候補が多い場合、外部取得前に総合マルチファクター基準で上位に絞ります。"
                    "評価方針を変えても、取得済みデータは再利用して再評価できます。"
                    "全件取得も選べますが、Yahooライブデータでは時間がかかります。"
                ),
            ),
        )
    effective_selected_labels = limited_ranking_selected_labels(
        selected_labels,
        filtered_symbol_rows,
        preset=RANKING_FETCH_LIMIT_PRESET,
        limit_key=fetch_limit,
    )
    ranking_symbols = _ranking_symbols_from_selected_labels(effective_selected_labels)
    current_ranking_source = _ranking_source_key_for_selection(
        provider=provider,
        selected_labels=effective_selected_labels,
        start=start_date,
        end=end_date,
    )
    st.caption(
        "評価方針: どの観点で候補を評価するかを選びます。"
        "候補は選択中の評価方針スコア順に表示されます。"
        "配当利回り、PER、PBR、ROEなどで並べ替えたい場合は、詳細テーブルの列名をクリックしてください。"
        f" {ranking_policy_label(ranking_policy)}は{ranking_purpose_help(ranking_policy)}"
    )
    if len(effective_selected_labels) < len(selected_labels):
        st.info(
            f"候補が多いため、{ranking_fetch_limit_label(fetch_limit)}として"
            f"{len(effective_selected_labels)}件を取得します。"
            "総合マルチファクター基準の条件適合度とDB信頼度で事前に並べています。"
        )
    warning_message = live_ranking_symbol_warning_message(provider, len(ranking_symbols))
    if warning_message is not None:
        st.warning(warning_message)
    with action_button_col:
        st.write("")
        build_ranking_clicked = st.button(
            "最新データを取得して更新",
            key="build_market_data_ranking",
            type="primary",
        )

    if build_ranking_clicked:
        sync_ranking_selection_state(selection_key, selected_labels)
        if not ranking_symbols:
            st.error("対象の銘柄を1件以上選んでください。")
            return
        cache_key = current_ranking_source
        loading_slot = st.empty()
        with loading_slot.container():
            render_mascot_loading(
                "ranking",
                title="ランキング更新中",
                message="候補ごとの価格データを集めて、深掘り候補を整理しています。",
                tone="success",
            )
        progress_bar = st.progress(0.0)
        progress_status = st.empty()

        def update_progress(message: str, ratio: float) -> None:
            progress_status.caption(message)
            progress_bar.progress(max(0.0, min(1.0, ratio)))

        try:
            rows, error_rows = asyncio.run(
                _build_market_data_ranking_rows(
                    ranking_symbols,
                    start=start_date,
                    end=end_date,
                    provider=provider,
                    progress_callback=update_progress,
                )
            )
            update_progress("ランキング更新が完了しました。", 1.0)
        finally:
            loading_slot.empty()
        set_cached_ranking_build(cache_key, rows=rows, error_rows=error_rows)
        st.session_state[MARKET_DATA_RANKING_STATE_KEY] = rows
        st.session_state[MARKET_DATA_RANKING_ERROR_STATE_KEY] = error_rows
        st.session_state[MARKET_DATA_RANKING_SOURCE_STATE_KEY] = cache_key
        st.session_state[MARKET_DATA_RANKING_UPDATED_AT_STATE_KEY] = datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )

    rows = st.session_state.get(MARKET_DATA_RANKING_STATE_KEY, [])
    error_rows = st.session_state.get(MARKET_DATA_RANKING_ERROR_STATE_KEY, [])
    ranking_source = str(st.session_state.get(MARKET_DATA_RANKING_SOURCE_STATE_KEY, ""))
    is_current_ranking_result = _ranking_result_matches_current_selection(
        ranking_source,
        provider=provider,
        selected_labels=effective_selected_labels,
        start=start_date,
        end=end_date,
    )
    if (rows or error_rows) and not is_current_ranking_result:
        _clear_ranking_deep_dive_state()
        st.info("条件が変わりました。最新データを取得して更新してください。")
        render_mascot_panel(
            "guide",
            message="条件を変えた後は、更新ボタンでもう一度候補を整理しましょう。",
            layout="compact",
        )
    elif rows:
        ranked_rows = apply_ranking_weight_preset(
            cast(list[dict[str, str]], rows),
            policy_preset,
            _symbol_universe_rows_by_symbol(),
        )
        display_rows = investment_score_display_rows(ranked_rows)
        display_rows = ranking_display_rows_with_research_status(
            display_rows,
            _ranking_research_statuses_for_display_rows(display_rows, as_of=end_date),
        )
        render_dashboard_header(
            "ランキング候補ダッシュボード",
            "比較候補と深掘り候補を整理するための画面です。買う銘柄を決める画面ではありません。",
            chips=[
                ("評価方針", ranking_policy_label(ranking_policy)),
                ("評価プロファイル", ranking_weight_preset_label(policy_preset)),
                (
                    "対象",
                    f"{ranking_region_label(region)} / {ranking_product_type_label(product_type)}",
                ),
                ("表示", f"{len(display_rows)}件"),
            ],
        )
        render_mascot_panel(
            "ranking",
            message=(
                "上位候補は深掘りの入口です。"
                f"{ranking_policy_label(ranking_policy)}の重視ポイントと注意点をセットで見比べます。"
            ),
            layout="compact",
        )
        _render_ranking_purpose_context(ranking_policy, policy_preset)
        _render_ranking_data_state(
            provider=provider,
            display_rows=display_rows,
            error_rows=cast(list[dict[str, str]], error_rows),
        )
        _render_ranking_score_explanation()
        _render_ranking_summary_cards(
            ranking_summary_cards(
                display_rows,
                ranking_axis=ranking_policy_label(ranking_policy),
                weight_preset=ranking_weight_preset_label(policy_preset),
                region=ranking_region_label(region),
                product_type=ranking_product_type_label(product_type),
                selected_count=len(effective_selected_labels),
            )
        )
        _render_top_screening_candidate_cards(
            ranking_top_candidate_cards(display_rows, ranking_purpose=ranking_policy)
        )
        chart_col, confidence_col = st.columns(2)
        with chart_col:
            _render_ranking_score_bar_chart(display_rows, ranking_policy)
        with confidence_col:
            _render_ranking_profile_chart(display_rows, ranking_policy)
        deep_dive_symbols = ranking_symbol_options(ranked_rows)
        selected_symbol: str | None = None
        if deep_dive_symbols:
            deep_dive_source = f"{ranking_source}|{policy_preset}"
            default_deep_dive_symbol = ranking_deep_dive_default_symbol(
                ranked_rows,
                current_symbol=cast(
                    str | None,
                    st.session_state.get("market_data_ranking_deep_dive_symbol"),
                ),
                source_key=deep_dive_source,
                current_source_key=cast(
                    str | None,
                    st.session_state.get(MARKET_DATA_RANKING_DEEP_DIVE_SOURCE_STATE_KEY),
                ),
            )
            if default_deep_dive_symbol is not None:
                st.session_state["market_data_ranking_deep_dive_symbol"] = default_deep_dive_symbol
                st.session_state[MARKET_DATA_RANKING_DEEP_DIVE_SOURCE_STATE_KEY] = deep_dive_source
            st.markdown("#### 深掘り候補の選択")
            st.caption(
                "気になる銘柄を1つ選び、銘柄コックピットで価格・予測・スコア理由を確認します。"
            )
            selected_symbol = cast(
                str,
                st.selectbox(
                    "深掘りする銘柄",
                    deep_dive_symbols,
                    format_func=symbol_candidate_label,
                    key="market_data_ranking_deep_dive_symbol",
                ),
            )
            st.button(
                "銘柄コックピットで確認",
                key="market_data_ranking_open_cockpit",
                on_click=_select_ranking_symbol_for_cockpit_with_period,
                args=(selected_symbol, provider, start_date, end_date),
            )
        _render_selected_ranking_candidate_breakdown(
            display_rows,
            selected_symbol,
            ranking_policy,
        )
        _render_ranking_advanced_insights(
            display_rows,
            include_confidence_map=ranking_policy != "data_confidence",
        )
        st.markdown("#### 詳細テーブル")
        st.caption(
            "カードとグラフで気になる候補を絞ったあと、詳細列を確認するためのテーブルです。行をクリックすると銘柄データを確認できます。"
        )
        _render_ranking_result_table(
            display_rows,
            ranking_source=ranking_source,
            weight_preset=policy_preset,
            ranking_purpose=ranking_policy,
        )
        _render_ranking_error_rows(cast(list[dict[str, str]], error_rows))
        _render_ranking_decision_report_lazy(
            ranked_rows=ranked_rows,
            provider=provider,
            start=start_date,
            end=end_date,
            ranking_purpose=ranking_policy_label(ranking_policy),
            weight_preset=ranking_weight_preset_label(policy_preset),
            comparison_summary=comparison_summary["inline"],
            error_rows=cast(list[dict[str, str]], error_rows),
            report_state_key=_ranking_decision_report_state_key(
                ranking_source,
                policy_preset,
            ),
        )
        col_json, col_csv = st.columns(2)
        col_json.download_button(
            "ランキングJSONをダウンロード",
            data=investment_score_json_download(ranked_rows),
            file_name="investment_score_ranking.json",
            mime="application/json",
        )
        col_csv.download_button(
            "ランキングCSVをダウンロード",
            data=investment_score_csv_download(ranked_rows),
            file_name="investment_score_ranking.csv",
            mime="text/csv",
        )
    elif error_rows:
        _clear_ranking_deep_dive_state()
        st.warning("ランキング対象の価格データを取得できませんでした。")
        _render_ranking_error_rows(cast(list[dict[str, str]], error_rows))
    else:
        _clear_ranking_deep_dive_state()
        st.info("銘柄を選んで最新データを取得してください。")
        render_mascot_panel(
            "empty",
            title="ランキング準備",
            message="比較条件を選んで最新データを取得すると、SMAIが深掘り候補を整理します。",
            layout="compact",
        )


def _render_ranking_error_rows(error_rows: list[dict[str, str]]) -> None:
    if not error_rows:
        return

    st.warning(
        f"{len(error_rows)}件の銘柄は価格データを取得できなかったため、ランキングから除外しました。"
    )
    with st.expander("取得できなかった銘柄"):
        _render_table(
            provider_error_summary_rows(error_rows), EMPTY_STATE_MESSAGES["ranking_errors"]
        )
        details_rows = [
            format_provider_error_details(row)
            for row in error_rows
            if format_provider_error_details(row)
        ]
        if details_rows:
            st.caption("診断情報")
            for details in details_rows:
                st.code(details, language="json")


def _format_ranking_decimal_value(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text


def _format_ranking_percent_value(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{_format_ranking_decimal_value(value * Decimal('100'))}%"


def _ranking_missing_items(row: DailySnapshot) -> str:
    return ", ".join(feature for feature, is_missing in sorted(row.missing.items()) if is_missing)


def _latest_volume_by_symbol(bars_by_symbol: dict[str, list[Bar]]) -> dict[str, str]:
    volumes: dict[str, str] = {}
    for symbol, bars in bars_by_symbol.items():
        if not bars:
            continue
        volumes[symbol] = _format_ranking_decimal_value(bars[-1].volume)
    return volumes


def _enrich_ranking_rows_with_feature_details(
    rows: list[dict[str, str]],
    feature_rows: list[DailySnapshot],
    *,
    latest_volume_by_symbol: dict[str, str] | None = None,
    provider_name: str = "",
) -> list[dict[str, str]]:
    feature_by_symbol = {row.symbol.strip().upper(): row for row in feature_rows}
    latest_volumes = latest_volume_by_symbol or {}
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        feature = feature_by_symbol.get(symbol)
        if feature is None:
            enriched_rows.append(row)
            continue
        enriched_rows.append(
            {
                **row,
                "current_price": _format_ranking_decimal_value(feature.last),
                "market_cap": _format_ranking_decimal_value(feature.market_cap_jpy),
                "volume": latest_volumes.get(symbol, ""),
                "volatility": _format_ranking_percent_value(feature.vol_20d),
                "dividend_yield_pct": row.get("dividend_yield_pct", "")
                or _format_ranking_decimal_value(
                    feature.dividend_yield * Decimal("100")
                    if feature.dividend_yield is not None
                    else None
                ),
                "data_as_of": feature.as_of.isoformat(),
                "data_provider": provider_name,
                "missing_items": _ranking_missing_items(feature),
            }
        )
    return enriched_rows


def _percent_display_to_pct_text(value: object) -> str:
    return str(value or "").replace("%", "").strip()


def _enrich_ranking_rows_with_feature_display_rows(
    rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    feature_by_symbol = {
        row.get("symbol", "").strip().upper(): row
        for row in feature_rows
        if row.get("symbol", "").strip()
    }
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        feature = feature_by_symbol.get(symbol)
        if feature is None:
            enriched_rows.append(row)
            continue
        enriched_rows.append(
            {
                **row,
                "current_price": feature.get("last", ""),
                "market_cap": feature.get("market_cap_jpy", ""),
                "volume": feature.get("adv_20d", ""),
                "volatility": feature.get("vol_20d", ""),
                "dividend_yield_pct": row.get("dividend_yield_pct", "")
                or _percent_display_to_pct_text(feature.get("dividend_yield", "")),
                "data_as_of": feature.get("as_of", ""),
                "data_provider": feature.get("provider", ""),
                "missing_items": feature.get("missing", ""),
            }
        )
    return enriched_rows


async def _build_market_data_ranking_rows(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    try:
        return await _build_market_data_ranking_rows_fast(
            symbols,
            start=start,
            end=end,
            provider=provider,
            progress_callback=progress_callback,
        )
    except AppError as exc:
        if provider in LIVE_MARKET_DATA_PROVIDERS:
            _report_ranking_progress(
                progress_callback,
                "Yahoo live data の一括取得に失敗しました。",
                1.0,
            )
            return [], ranking_provider_error_rows(provider, symbols, exc)
        return await _build_market_data_ranking_rows_from_previews(
            symbols,
            start=start,
            end=end,
            provider=provider,
            progress_callback=progress_callback,
        )


async def _build_market_data_ranking_rows_fast(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    _report_ranking_progress(progress_callback, "ランキング用データの準備を開始しています。", 0.05)
    settings = get_settings()
    dataaccess_cfg = settings.dataaccess
    if provider:
        dataaccess_cfg = dataaccess_cfg.model_copy(
            update={
                "provider": provider,
                "allow_external_providers": provider == "yahoo"
                or dataaccess_cfg.allow_external_providers,
            }
        )
    adapter = create_market_data_provider_adapter(dataaccess_cfg)
    end_dt = datetime.combine(end, time.max, tzinfo=UTC)
    feature_start = min(start, end - timedelta(days=90))
    feature_start_dt = datetime.combine(feature_start, time.min, tzinfo=UTC)
    bars: list[Bar] = []
    provider_symbols_by_symbol = _provider_symbols_by_display_symbol(symbols, provider)
    fetch_symbols = _unique_provider_symbols(provider_symbols_by_symbol.values())
    symbol_chunks = ranking_symbol_chunks(fetch_symbols)
    for index, symbol_chunk in enumerate(symbol_chunks, start=1):
        _report_ranking_progress(
            progress_callback,
            f"価格データをまとめて取得しています ({index}/{len(symbol_chunks)})。",
            0.1 + (0.35 * (index - 1) / len(symbol_chunks)),
        )
        bars.extend(await adapter.fetch_ohlcv(symbol_chunk, start=feature_start_dt, end=end_dt))
    bars = _bars_with_display_symbols(
        bars,
        provider_symbols_by_symbol=provider_symbols_by_symbol,
    )
    _report_ranking_progress(progress_callback, "価格データを整理しています。", 0.45)
    bars_by_symbol = _ranking_bars_by_symbol(symbols, bars)

    available_symbols: list[str] = []
    quotes: list[Quote] = []
    error_rows: list[dict[str, str]] = []
    for symbol in symbols:
        symbol_bars = bars_by_symbol[symbol]
        if not symbol_bars:
            error_rows.append(
                ranking_no_bars_error_row(
                    provider=provider,
                    symbol=symbol,
                    display_start=start,
                    display_end=end,
                    fetch_start=feature_start_dt,
                    fetch_end=end_dt,
                )
            )
            continue
        latest = symbol_bars[-1]
        available_symbols.append(symbol)
        quotes.append(
            Quote(
                symbol=latest.symbol,
                bid=None,
                ask=None,
                last=latest.close,
                ts=latest.ts,
            )
        )

    if not available_symbols:
        _report_ranking_progress(progress_callback, "ランキング対象の価格データがありません。", 1.0)
        return [], error_rows

    _report_ranking_progress(progress_callback, "ファンダメンタル情報を取得しています。", 0.55)
    provider_available_symbols = [
        provider_symbols_by_symbol[symbol] for symbol in available_symbols
    ]
    provider_fundamentals = await adapter.fetch_fundamentals(provider_available_symbols, as_of=end)
    fundamentals = _fundamentals_with_display_symbols(
        provider_fundamentals,
        provider_symbols_by_symbol={
            symbol: provider_symbols_by_symbol[symbol] for symbol in available_symbols
        },
    )
    _report_ranking_progress(progress_callback, "スクリーニング用特徴量を作成しています。", 0.65)
    feature_rows = build_daily_snapshots_from_market_data(
        symbols=available_symbols,
        as_of=end,
        quotes=quotes,
        fundamentals=fundamentals,
        bars=bars,
        cfg=settings.feature_builder,
    )
    provider_name = adapter.healthcheck().get("provider", provider)
    feature_snapshot = FeatureSnapshot(
        as_of=end,
        provider=provider_name,
        rows=feature_rows,
        missing_summary=_feature_missing_summary(feature_rows),
        quality_summary=_feature_quality_summary(feature_rows),
    )
    forecast_horizon_days = default_forecast_horizon_days(start, end)
    forecast_consensus_by_symbol = {}
    for index, symbol in enumerate(available_symbols, start=1):
        forecast_history_bars = bars_by_symbol[symbol]
        forecast_consensus = summarize_forecast_evaluations_for_ui(
            _available_forecast_evaluations(
                forecast_history_bars,
                horizon_days=forecast_horizon_days,
            ),
            history=forecast_history_bars,
        )
        if forecast_consensus is not None:
            forecast_consensus_by_symbol[forecast_consensus.symbol] = forecast_consensus
        should_report_progress = index == 1 or index % 10 == 0 or index == len(available_symbols)
        if not should_report_progress:
            continue
        progress = 0.65 + (0.2 * index / len(available_symbols))
        _report_ranking_progress(
            progress_callback,
            f"方向シグナルを計算しています ({index}/{len(available_symbols)})。",
            progress,
        )

    _report_ranking_progress(progress_callback, "総合スコアを計算しています。", 0.9)
    screening_scores = ScreeningService().score(
        feature_snapshot,
        forecast_consensus_by_symbol=forecast_consensus_by_symbol,
    )
    investment_scores = InvestmentScoringService(weights=settings.scoring.weights).score(
        screening_scores,
        forecast_consensus_by_symbol=forecast_consensus_by_symbol,
    )
    score_rows = _enrich_ranking_rows_with_feature_details(
        investment_score_rows(investment_scores),
        feature_rows,
        latest_volume_by_symbol=_latest_volume_by_symbol(bars_by_symbol),
        provider_name=provider_name,
    )
    ranked_rows = rank_investment_score_rows(score_rows)
    _report_ranking_progress(progress_callback, "ランキングを並べ替えています。", 0.98)
    return ranked_rows, error_rows


def _provider_symbols_by_display_symbol(
    symbols: list[str],
    provider: str,
) -> dict[str, str]:
    return {symbol: symbol_provider_symbol(symbol, provider) for symbol in symbols}


def _unique_provider_symbols(symbols: Iterable[str]) -> list[str]:
    unique_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        if not isinstance(symbol, str):
            continue
        if symbol in seen:
            continue
        unique_symbols.append(symbol)
        seen.add(symbol)
    return unique_symbols


def _bars_with_display_symbols(
    bars: list[Bar],
    *,
    provider_symbols_by_symbol: dict[str, str],
) -> list[Bar]:
    symbol_by_provider_symbol = {
        provider_symbol: symbol for symbol, provider_symbol in provider_symbols_by_symbol.items()
    }
    return [
        _bar_with_display_symbol(
            bar,
            display_symbol=symbol_by_provider_symbol.get(bar.symbol.raw, bar.symbol.raw),
        )
        for bar in bars
    ]


def _bar_with_display_symbol(bar: Bar, *, display_symbol: str) -> Bar:
    return bar.model_copy(
        update={
            "symbol": bar.symbol.model_copy(
                update={"raw": display_symbol, "code": display_symbol.removesuffix(".T")}
            )
        }
    )


def _fundamentals_with_display_symbols(
    fundamentals: list[FundamentalSnapshot],
    *,
    provider_symbols_by_symbol: dict[str, str],
) -> list[FundamentalSnapshot]:
    symbol_by_provider_symbol = {
        provider_symbol: symbol for symbol, provider_symbol in provider_symbols_by_symbol.items()
    }
    return [
        fundamental.model_copy(
            update={"symbol": symbol_by_provider_symbol.get(fundamental.symbol, fundamental.symbol)}
        )
        for fundamental in fundamentals
    ]


def _ranking_bars_by_symbol(
    symbols: list[str],
    bars: list[Bar],
) -> dict[str, list[Bar]]:
    grouped: dict[str, list[Bar]] = {symbol: [] for symbol in symbols}
    for bar in bars:
        if bar.symbol.raw in grouped:
            grouped[bar.symbol.raw].append(bar)
    for symbol_bars in grouped.values():
        symbol_bars.sort(key=lambda bar: bar.ts)
    return grouped


RankingProgressCallback = Callable[[str, float], None]


def _report_ranking_progress(
    progress_callback: RankingProgressCallback | None,
    message: str,
    ratio: float,
) -> None:
    if progress_callback is not None:
        progress_callback(message, ratio)


def _ranking_build_cache() -> dict[str, dict[str, list[dict[str, str]]]]:
    cache = st.session_state.setdefault(MARKET_DATA_RANKING_BUILD_CACHE_STATE_KEY, {})
    if isinstance(cache, dict):
        return cast(dict[str, dict[str, list[dict[str, str]]]], cache)
    st.session_state[MARKET_DATA_RANKING_BUILD_CACHE_STATE_KEY] = {}
    return {}


def get_cached_ranking_build(
    cache_key: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]] | None:
    cached = _ranking_build_cache().get(cache_key)
    if cached is None:
        return None
    return cached.get("rows", []), cached.get("error_rows", [])


def set_cached_ranking_build(
    cache_key: str,
    *,
    rows: list[dict[str, str]],
    error_rows: list[dict[str, str]],
) -> None:
    cache = _ranking_build_cache()
    if cache_key in cache:
        cache.pop(cache_key)
    cache[cache_key] = {"rows": rows, "error_rows": error_rows}
    while len(cache) > MAX_RANKING_BUILD_CACHE_ENTRIES:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key)


def _feature_missing_summary(rows: list[DailySnapshot]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        for feature, is_missing in row.missing.items():
            if is_missing:
                summary[feature] = summary.get(feature, 0) + 1
    return summary


def _feature_quality_summary(rows: list[DailySnapshot]) -> dict[DataQuality, int]:
    summary: dict[DataQuality, int] = {}
    for row in rows:
        summary[row.data_quality] = summary.get(row.data_quality, 0) + 1
    return summary


async def _build_market_data_ranking_rows_from_previews(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    error_rows: list[dict[str, str]] = []
    forecast_horizon_days = default_forecast_horizon_days(start, end)
    semaphore = asyncio.Semaphore(MAX_RANKING_CONCURRENT_FETCHES)
    _report_ranking_progress(
        progress_callback,
        "銘柄別の取得に切り替えてランキングを作成しています。",
        0.05,
    )

    async def build_symbol_preview(
        symbol: str,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        async with semaphore:
            preview = await build_market_data_preview(
                symbol=symbol,
                start=start,
                end=end,
                provider_override=provider,
                forecast_horizon_days=forecast_horizon_days,
            )
        return _enrich_ranking_rows_with_feature_display_rows(
            preview.investment_score_rows,
            getattr(preview, "feature_rows", []),
        ), [{"symbol": symbol, **error_row} for error_row in getattr(preview, "error_rows", [])]

    tasks = [asyncio.create_task(build_symbol_preview(symbol)) for symbol in symbols]
    for completed_count, task in enumerate(asyncio.as_completed(tasks), start=1):
        preview_rows, preview_error_rows = await task
        rows.extend(preview_rows)
        error_rows.extend(preview_error_rows)
        should_report_progress = (
            completed_count == 1 or completed_count % 10 == 0 or completed_count == len(symbols)
        )
        if not should_report_progress:
            continue
        _report_ranking_progress(
            progress_callback,
            f"銘柄別に取得しています ({completed_count}/{len(symbols)})。",
            0.1 + (0.85 * completed_count / len(symbols)),
        )
    _report_ranking_progress(progress_callback, "ランキングを並べ替えています。", 0.98)
    return rank_investment_score_rows(rows), error_rows


def _select_ranking_symbol_for_cockpit(symbol: str, provider: str) -> None:
    st.session_state["sidemenu_page"] = SIDEMENU_PAGE_COCKPIT
    st.session_state["market_data_mode"] = MARKET_DATA_MODE_COCKPIT
    st.session_state[MARKET_DATA_PROVIDER_WIDGET_KEY] = provider
    st.session_state["market_data_symbol_candidate"] = symbol_candidate_label(symbol)
    st.session_state.pop(MARKET_DATA_PREVIEW_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_STATUS_STATE_KEY, None)
    _clear_ranking_deep_dive_state()


def _select_ranking_symbol_for_cockpit_with_period(
    symbol: str,
    provider: str,
    start: date,
    end: date,
) -> None:
    _select_ranking_symbol_for_cockpit(symbol, provider)
    st.session_state["market_data_period_preset"] = MARKET_DATA_PERIOD_CUSTOM
    st.session_state["market_data_start"] = start
    st.session_state["market_data_end"] = end


def _clear_ranking_deep_dive_state() -> None:
    st.session_state.pop("market_data_ranking_deep_dive_symbol", None)
    st.session_state.pop(MARKET_DATA_RANKING_DEEP_DIVE_SOURCE_STATE_KEY, None)
    st.session_state.pop("market_data_ranking_open_cockpit", None)


def symbol_candidate_label(symbol: str) -> str:
    name = symbol_name(symbol)
    if name:
        return f"{symbol} - {name}"
    return symbol


def _market_data_preview_from_state() -> MarketDataPreview | None:
    preview = st.session_state.get(MARKET_DATA_PREVIEW_STATE_KEY)
    if isinstance(preview, MarketDataPreview):
        return preview
    return None


def _render_market_data_preview_result(preview: MarketDataPreview) -> None:
    symbol_label = _market_data_preview_symbol_label(preview)
    forecast_horizon_days = _render_market_data_cockpit_header(preview, symbol_label)
    forecast_rows = forecast_chart_rows(preview.bars, horizon_days=forecast_horizon_days)
    consensus_rows = forecast_consensus_rows_for_bars(
        preview.bars,
        horizon_days=forecast_horizon_days,
    )
    metric_rows = forecast_metric_rows_for_bars(preview.bars, horizon_days=forecast_horizon_days)

    symbol = _market_data_preview_symbol(preview)
    provider_name = _metadata_value(preview.provider_rows, "provider") or "unknown"
    reference_period = forecast_reference_period(preview.bars, horizon_days=forecast_horizon_days)
    score_display_rows = investment_score_display_rows(preview.investment_score_rows)
    render_cockpit_summary_header(
        cockpit_summary_items(
            symbol=symbol,
            name=symbol_name(symbol) or "",
            provider=provider_name,
            as_of=_market_data_as_of(preview),
            reference_period_days=reference_period,
            forecast_horizon_days=forecast_horizon_days,
            score_row=score_display_rows[0] if score_display_rows else None,
            symbol_metadata=_symbol_universe_row_for_symbol(symbol) if symbol else None,
        )
    )
    render_mascot_panel(
        "cockpit",
        message="まずKPIで全体感をつかみ、チャート、評価内訳、確認サマリーの順に見ていきます。",
        layout="compact",
    )
    score_row = _render_investment_score_section(
        preview,
        symbol_label,
        rows=score_display_rows,
    )
    _render_price_forecast_hero(
        preview,
        symbol_label,
        forecast_rows,
        consensus_rows,
        metric_rows,
    )
    if score_row is not None:
        _render_cockpit_direction_signal_section(score_row, consensus_rows)
        _render_score_breakdown_context(preview, symbol_label, score_row, score_display_rows)

    summary_rows = cockpit_detail_summary_rows(preview, consensus_rows, metric_rows)
    if summary_rows:
        st.subheader("05 確認サマリー")
        st.caption(
            "詳細データのうち、深掘り前に見ておきたい代表項目を確認観点として整理しています。"
        )
        _render_symbol_detail_table(summary_rows)

    _render_cockpit_research_summary(preview)
    _render_cockpit_decision_report(preview)

    st.subheader("08 詳細データ")
    st.caption(
        "取得元データや計算に使った詳細情報です。通常の投資判断では、必要な場合のみ確認してください。"
    )
    with st.expander("予測の詳細データを表示", expanded=False):
        st.caption(
            "予測モデルごとの詳細値です。チャートで気になった点を確認するための補助データです。"
        )
        for index, message in enumerate(forecast_metric_summary(metric_rows)):
            if index == 0:
                st.info(message)
            else:
                st.caption(message)
        st.subheader("予測サマリー")
        _render_target_symbol_caption(symbol_label)
        _render_table(
            forecast_consensus_display_rows(consensus_rows),
            EMPTY_STATE_MESSAGES["forecast_summary"],
        )
        st.subheader("予測精度")
        _render_target_symbol_caption(symbol_label)
        _render_table(
            forecast_metric_display_rows(metric_rows),
            EMPTY_STATE_MESSAGES["forecast_metrics"],
        )
        if metric_rows:
            col_json, col_csv = st.columns(2)
            col_json.download_button(
                "予測JSONをダウンロード",
                data=forecast_metric_json_download(metric_rows),
                file_name="forecast_metrics.json",
                mime="application/json",
            )
            col_csv.download_button(
                "予測CSVをダウンロード",
                data=forecast_metric_csv_download(metric_rows),
                file_name="forecast_metrics.csv",
                mime="text/csv",
            )

    with st.expander("スクリーニングの詳細データを表示", expanded=False):
        st.caption(
            "スクリーニングスコアの元データです。主要KPIで気になった点を詳しく見るために使います。"
        )
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.screening_rows, EMPTY_STATE_MESSAGES["screening_score_rows"])
        if preview.screening_rows:
            col_json, col_csv = st.columns(2)
            col_json.download_button(
                "スクリーニングJSONをダウンロード",
                data=screening_score_json_download(preview.screening_rows),
                file_name="screening_score.json",
                mime="application/json",
            )
            col_csv.download_button(
                "スクリーニングCSVをダウンロード",
                data=screening_score_csv_download(preview.screening_rows),
                file_name="screening_score.csv",
                mime="text/csv",
            )

    with st.expander("取得元データを表示", expanded=False):
        st.caption(
            "データ取得元、現在値、価格データの詳細です。データ鮮度や取得内容を確認したい場合に使います。"
        )
        st.subheader("データ取得元")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.provider_rows, EMPTY_STATE_MESSAGES["provider_metadata"])

        st.subheader("現在値")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.quote_rows, EMPTY_STATE_MESSAGES["quote_rows"])

        st.subheader("価格データ概要")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.ohlcv_rows, EMPTY_STATE_MESSAGES["ohlcv_rows"])

    with st.expander("為替・特徴量データを表示", expanded=False):
        st.caption("為替換算や特徴量データの詳細です。通常は主要KPIとチャート確認後に参照します。")
        st.subheader("為替")
        _render_table(preview.fx_rows, EMPTY_STATE_MESSAGES["fx_rows"])

        st.subheader("特徴量データ")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.feature_rows, EMPTY_STATE_MESSAGES["feature_snapshot_rows"])

    if preview.error_rows:
        st.subheader("補助データの取得警告")
        _render_provider_error_summary(preview.error_rows)


def _render_cockpit_research_summary(preview: MarketDataPreview) -> None:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return
    st.subheader(RESEARCH_COCKPIT_SECTION_TITLE)
    st.caption(RESEARCH_COCKPIT_INTRO)
    report = _cockpit_research_report_from_state(preview)
    news_report = _cockpit_stock_news_report_from_state(preview)
    fetch_clicked = _render_research_operation_card(
        preview,
        report=report,
        news_report=news_report,
    )
    if fetch_clicked:
        with st.spinner(RESEARCH_FETCH_SPINNER):
            refresh_started = perf_time.perf_counter()
            trace_rows: list[tuple[str, float]] = []
            try:
                step_started = perf_time.perf_counter()
                external_result = _fetch_external_research_for_preview(preview)
                trace_rows.append(("外部取得", perf_time.perf_counter() - step_started))
                if external_result.entries:
                    st.success(
                        f"外部参照ソース {len(external_result.entries)}件をAI調査に反映しました。"
                    )
                cache_info = external_research_fetch_cache_info()
                if cache_info.get("cache_hit") is True:
                    st.info(
                        "直近の外部参照ソースを再利用しました。表示内容は同じ品質で更新します。"
                    )
                for warning in external_result.warnings:
                    st.warning(warning)
            except AppError as exc:
                st.warning(
                    "外部参照ソースを取得できませんでした。保存済み資料と既存データでAI調査を続行します。"
                )
                st.caption(exc.message)
                if exc.details:
                    st.caption(json.dumps(exc.details, ensure_ascii=False, sort_keys=True))
            step_started = perf_time.perf_counter()
            st.session_state[MARKET_DATA_RESEARCH_REPORT_STATE_KEY] = (
                _build_cockpit_research_report(preview)
            )
            trace_rows.append(("企業レポート生成", perf_time.perf_counter() - step_started))
            step_started = perf_time.perf_counter()
            st.session_state[MARKET_DATA_STOCK_NEWS_REPORT_STATE_KEY] = (
                _build_cockpit_stock_news_report(preview)
            )
            trace_rows.append(("ニュース整理", perf_time.perf_counter() - step_started))
            trace_rows.append(("合計", perf_time.perf_counter() - refresh_started))
            st.session_state[RESEARCH_REFRESH_TRACE_STATE_KEY] = trace_rows
            st.caption(_research_refresh_trace_caption(trace_rows))

    report = _cockpit_research_report_from_state(preview)
    news_report = _cockpit_stock_news_report_from_state(preview)
    if report is None:
        st.info(RESEARCH_NOT_FETCHED_MESSAGE)
        if news_report is not None and news_report.news:
            _render_stock_news_cards_panel(news_report)
    else:
        _render_research_summary_panel(
            report,
            detail_expanded=False,
            news_report=news_report,
            external_research_result=_cockpit_external_research_fetch_result_from_state(preview),
        )


def _fetch_external_research_for_preview(
    preview: MarketDataPreview,
) -> ExternalResearchFetchResult:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        raise AppError("AI調査の対象銘柄が選択されていません。")
    company_name = symbol_name(symbol) or None
    related_keywords = [company_name] if company_name else []
    result = fetch_external_research_for_symbol(
        symbol,
        company_name=company_name,
        related_keywords=related_keywords,
        as_of=_date_from_iso_text(_market_data_as_of(preview)),
        allow_network=True,
    )
    st.session_state[MARKET_DATA_EXTERNAL_RESEARCH_FETCH_STATE_KEY] = result
    return result


def _cockpit_external_research_fetch_result_from_state(
    preview: MarketDataPreview,
) -> ExternalResearchFetchResult | None:
    result = st.session_state.get(MARKET_DATA_EXTERNAL_RESEARCH_FETCH_STATE_KEY)
    if not isinstance(result, ExternalResearchFetchResult):
        return None
    if result.symbol.strip().upper() != _market_data_preview_symbol(preview).strip().upper():
        return None
    return result


def _external_research_fetch_summary_rows(
    result: ExternalResearchFetchResult,
) -> list[dict[str, str]]:
    warnings = " / ".join(result.warnings) if result.warnings else "なし"
    return [
        {"項目": "取得元", "内容": result.provider},
        {"項目": "取得日時", "内容": _datetime_display_text(result.fetched_at)},
        {"項目": "登録資料数", "内容": f"{len(result.entries)}件"},
        {
            "項目": "保持方針",
            "内容": "このセッションのみ" if result.retention_policy == "session" else "保存済み",
        },
        {"項目": "注意", "内容": warnings},
    ]


def _external_research_fetch_overview_html(result: ExternalResearchFetchResult) -> str:
    latest_dates = [entry.published_at for entry in result.entries if entry.published_at]
    latest_text = max(latest_dates).isoformat() if latest_dates else "未確認"
    official_count = sum(1 for entry in result.entries if entry.source_type == "tdnet")
    stale_count = sum(1 for entry in result.entries if entry.freshness_status == "stale")
    source_types = sorted(
        {_research_source_type_label(entry.source_type) for entry in result.entries}
    )
    summary = (
        "外部から取得した根拠候補です。公式開示を優先して確認し、"
        "外部データやニュースは補助情報として扱ってください。"
    )
    items = [
        ("取得元", _external_research_provider_label(result.provider)),
        ("取得件数", f"{len(result.entries)}件"),
        ("最新公開日", latest_text),
        ("公式開示", f"{official_count}件"),
        ("資料種別", " / ".join(source_types) if source_types else "未確認"),
        ("注意", f"古い可能性 {stale_count}件" if stale_count else "鮮度警告なし"),
    ]
    item_markup = "".join(
        '<div class="research-result-brief-item">'
        f'<div class="research-result-brief-label">{html.escape(label)}</div>'
        f'<div class="research-result-brief-value">{html.escape(value)}</div>'
        "</div>"
        for label, value in items
    )
    return (
        '<section class="research-result-brief">'
        '<div class="research-result-brief-title">外部参照ソースの確認メモ</div>'
        f'<div class="research-result-brief-summary">{html.escape(summary)}</div>'
        f'<div class="research-result-brief-grid">{item_markup}</div>'
        "</section>"
    )


def _external_research_source_cards_html(result: ExternalResearchFetchResult) -> str:
    if not result.entries:
        return ""
    items: list[str] = []
    for entry in result.entries:
        provider = _external_research_provider_label(entry.provider)
        source_type = _research_source_type_label(entry.source_type)
        freshness = _research_freshness_status_label(entry.freshness_status)
        published_at = entry.published_at.isoformat() if entry.published_at else "未確認"
        note = _external_research_entry_check_note(entry)
        summary = _external_research_entry_summary_display_text(entry)
        items.append(
            '<article class="research-evidence-item">'
            '<div class="research-evidence-card-header">'
            f'<span class="research-evidence-pill positive">{html.escape(source_type)}</span>'
            f'<span class="research-evidence-pill">{html.escape(provider)}</span>'
            f'<span class="research-evidence-pill">鮮度: {html.escape(freshness)}</span>'
            "</div>"
            f'<div class="research-evidence-title">{html.escape(entry.title)}</div>'
            f'<div class="research-evidence-meta">公開日: {html.escape(published_at)} / '
            f"取得: {html.escape(_datetime_display_text(entry.fetched_at))}</div>"
            '<div class="research-evidence-body">'
            f'<span class="research-evidence-label">まず確認:</span> {html.escape(note)}'
            "</div>"
            f'<div class="research-evidence-excerpt">{html.escape(summary)}</div>'
            '<div class="research-evidence-actions">'
            f'<a href="{html.escape(entry.source_url)}" target="_blank" rel="noopener noreferrer">'
            "出典を開く</a>"
            "</div>"
            "</article>"
        )
    return f'<div class="research-evidence-list">{"".join(items)}</div>'


def _external_research_fetch_result_rows(
    result: ExternalResearchFetchResult,
) -> list[dict[str, str]]:
    return [
        {
            "資料名": entry.title,
            "資料種別": _research_source_type_label(entry.source_type),
            "取得元": entry.provider,
            "公開日": entry.published_at.isoformat() if entry.published_at else "未確認",
            "鮮度": _research_freshness_status_label(entry.freshness_status),
            "取得日時": _datetime_display_text(entry.fetched_at),
            "URL": entry.source_url,
            "要約": _external_research_entry_summary_display_text(entry),
        }
        for entry in result.entries
    ]


def _external_research_entry_summary_display_text(
    entry: ExternalResearchFetchManifestEntry,
) -> str:
    summary = entry.content_summary or "要約はありません。リンク先で本文を確認してください。"
    if entry.source_type != "provider_profile":
        return (
            _research_brief_ui_text(summary, max_chars=360) or "リンク先で本文を確認してください。"
        )

    cleaned = _external_research_provider_profile_display_text(summary)
    return (
        _research_brief_ui_text(cleaned, max_chars=520)
        or "外部データの企業プロフィールを取得しました。重要事項は公式IRで確認してください。"
    )


def _external_research_provider_profile_display_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    raw_labels = (
        "Company Name",
        "Provider Symbol",
        "Quote Type",
        "Exchange",
        "Currency",
        "Sector",
        "Industry",
        "Country",
        "Website",
        "Market Cap",
        "Enterprise Value",
        "Total Revenue",
        "Revenue",
        "Operating Income",
        "Net Income To Common",
        "Net Income",
        "Trailing EPS",
        "Forward EPS",
        "PER",
        "PBR",
        "ROE",
        "Trailing PE",
        "Forward PE",
        "Price To Book",
        "Return On Equity",
        "Dividend Rate",
        "Dividend Yield",
        "Yield",
        "Trailing Annual Dividend Yield",
        "Full Time Employees",
        "Payout Ratio",
        "Beta",
        "Data Quality Notes",
    )
    stop_labels = "|".join(re.escape(label) for label in (*raw_labels, "Business Summary"))
    for label in raw_labels:
        cleaned = re.sub(
            rf"\b{re.escape(label)}\s*[:：]\s*.*?(?=\s+(?:{stop_labels})\s*[:：]|$)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    cleaned = re.sub(r"\bBusiness Summary\s*[:：]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhttps?://\S+", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _external_research_provider_label(provider: str) -> str:
    labels = {
        "tdnet": "TDnet（適時開示）",
        "yahoo_finance": "Yahoo Finance",
        "tdnet_yahoo_finance": "TDnet / Yahoo Finance",
    }
    return labels.get(provider, provider)


def _external_research_entry_check_note(entry: ExternalResearchFetchManifestEntry) -> str:
    if entry.source_type == "tdnet":
        return "公式開示です。PDF本文で対象期間、数値、会社発表の前提を確認してください。"
    if entry.source_type == "provider_profile":
        return "外部データです。事業内容や指標は公式IR・決算資料と照合してください。"
    if entry.source_type == "news":
        return "ニュースです。一次情報ではないため、会社発表や開示資料で裏取りしてください。"
    return "出典URL、公開日、本文の該当箇所を確認してください。"


def _datetime_display_text(value: datetime) -> str:
    return value.isoformat(timespec="minutes")


def _render_research_operation_card(
    preview: MarketDataPreview,
    *,
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
) -> bool:
    symbol = _market_data_preview_symbol(preview)
    insight = _research_operation_insight(report, news_report)
    with st.container(border=True):
        text_col, action_col = st.columns([1.55, 1.0])
        with text_col:
            st.markdown(
                (
                    '<div class="research-ai-cta">'
                    f'<div class="research-ai-cta-title">{html.escape(insight["title"])}</div>'
                    '<div class="research-ai-cta-copy">'
                    f'{html.escape(insight["summary"])}</div>'
                    '<div class="research-ai-cta-source">'
                    f'{html.escape(insight["source_summary"])}</div>'
                    f'<div class="research-next-step">{html.escape(insight["next_step"])}</div>'
                    '<div class="research-ai-cta-note">'
                    "売買推奨ではなく、企業理解のための外部情報整理です。</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
        with action_col:
            st.markdown(
                '<div class="research-action-label">まずここから</div>', unsafe_allow_html=True
            )
            fetch_clicked = st.button(
                RESEARCH_FETCH_BUTTON_LABEL,
                key=f"research_ai_fetch_{symbol}",
                help=(
                    "外部参照ソースと保存済み資料から、企業概要、事業内容、定量情報、IR、ニュースを整理します。"
                    "売買判断の代行ではありません。"
                ),
                type="primary",
                use_container_width=True,
            )
            st.markdown(
                '<div class="research-action-help">根拠資料とニュースをまとめて更新します。</div>',
                unsafe_allow_html=True,
            )
            return fetch_clicked


def _research_operation_insight(
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
) -> dict[str, str]:
    if report is None:
        if news_report is not None and news_report.news:
            news_count = len(news_report.news)
            source_summary = _research_operation_news_source_summary(news_report)
            return {
                "title": "AI調査で確認すること",
                "summary": (
                    f"関連ニュース{news_count}件は確認済みです。"
                    "AI調査を更新すると、事業概要、定量情報、IR情報も企業リサーチとして整理します。"
                ),
                "source_summary": source_summary,
                "next_step": "追加確認: AI調査を更新して、IR・開示・外部データを合わせて確認します。",
            }
        return {
            "title": "AI調査で確認すること",
            "summary": (
                "まだ企業リサーチレポートは整理されていません。"
                "AI調査を更新すると、外部情報・ニュース・保存済み資料を企業理解の材料に変換します。"
            ),
            "source_summary": "確認済み: 未取得",
            "next_step": "追加確認: AI調査を更新して、根拠資料を整理します。",
        }

    brief = ResearchBriefBuilder().build(report, news_report=news_report)
    return {
        "title": "企業リサーチレポートを更新しました",
        "summary": _research_operation_fact_summary(brief),
        "source_summary": _research_operation_source_summary(brief),
        "next_step": _research_operation_next_step(brief),
    }


def _research_operation_fact_summary(brief: ResearchBrief) -> str:
    fact_summary = brief.fact_summary
    if fact_summary is None:
        business_overview = _research_brief_ui_text(brief.business_overview, max_chars=118)
        material_summary = _research_operation_material_summary(brief)
        return f"事業: {business_overview} {material_summary}"

    parts: list[str] = []
    if fact_summary.business_overview:
        overview = _research_brief_ui_text(fact_summary.business_overview[0].value, max_chars=92)
        parts.append(f"事業: {overview}")
    business_context = [
        *fact_summary.business_regions[:1],
        *fact_summary.revenue_drivers[:1],
        *fact_summary.business_segments[:1],
    ]
    if business_context:
        context = " / ".join(
            _research_brief_ui_text(item.value, max_chars=32) for item in business_context[:2]
        )
        parts.append(f"補足: {context}")
    if not parts:
        return _research_operation_material_summary(brief)
    return " ".join(parts)


def _research_operation_source_summary(brief: ResearchBrief) -> str:
    labels: list[str] = []
    has_official = False
    has_supporting = False
    for card in brief.source_cards:
        label = _research_source_type_label(card.source_type)
        if label not in labels:
            labels.append(label)
        if card.source_confidence == "high":
            has_official = True
        elif card.source_confidence in {"medium", "low", "unknown"}:
            has_supporting = True
    if not labels:
        return "確認済み: 根拠資料はまだ少なめです。"
    source_text = " / ".join(labels[:4])
    if len(labels) > 4:
        source_text += f" ほか{len(labels) - 4}種"
    if has_official:
        prefix = "確認済み: 公式資料を含みます"
    elif has_supporting:
        prefix = "確認済み: 外部データ中心。公式IRは未確認です"
    else:
        prefix = "確認済み: 資料の信頼度は未確認です"
    return f"{prefix}。資料: {source_text}。"


def _research_operation_news_source_summary(news_report: StockNewsReport) -> str:
    source_names: list[str] = []
    for news in news_report.news:
        source = news.source or "ニュース"
        if source not in source_names:
            source_names.append(source)
    if not source_names:
        return "確認済み: ニュース"
    source_text = " / ".join(source_names[:3])
    if len(source_names) > 3:
        source_text += f" ほか{len(source_names) - 3}件"
    return f"確認済み: {source_text}"


def _research_operation_material_summary(brief: ResearchBrief) -> str:
    positive_materials = brief.positive_materials or brief.positive_candidates
    caution_materials = brief.caution_materials or brief.caution_candidates
    if positive_materials:
        material = (
            positive_materials[0].summary
            if isinstance(positive_materials[0], ResearchBriefMaterial)
            else positive_materials[0]
        )
        return f"確認材料: {_research_brief_ui_text(material, max_chars=70)}"
    if caution_materials:
        material = (
            caution_materials[0].summary
            if isinstance(caution_materials[0], ResearchBriefMaterial)
            else caution_materials[0]
        )
        return f"確認材料: {_research_brief_ui_text(material, max_chars=70)}"
    if brief.metrics:
        return "補足: 主要数値は下の定量指標で確認できます。"
    return "主な材料はまだ整理できていません。"


def _research_operation_next_step(brief: ResearchBrief) -> str:
    if brief.missing_metrics:
        missing = "、".join(brief.missing_metrics[:5])
        if len(brief.missing_metrics) > 5:
            missing += f" ほか{len(brief.missing_metrics) - 5}件"
        return f"追加確認: 決算短信・有価証券報告書で {missing} を確認します。"
    if brief.confirmation_gaps:
        return f"追加確認: {_research_brief_gap_display_text(brief.confirmation_gaps[0])}"
    return "追加確認: 出典カードで資料名、公開日、URLを確認します。"


def _render_ranking_symbol_research_lookup(symbol: str) -> None:
    st.subheader(RESEARCH_RANKING_LOOKUP_TITLE)
    st.caption(RESEARCH_RANKING_LOOKUP_INTRO)
    fetch_clicked = st.button(
        RESEARCH_RANKING_FETCH_BUTTON_LABEL,
        key=f"ranking_research_fetch_{_widget_key_fragment(symbol)}",
        help=(
            "保存済み資料から、成長材料、株主還元、財務安全性、事業リスク、確認不足を根拠付きで表示します。"
            "ランキング詳細では外部取得を自動実行しません。"
        ),
        type="primary",
    )
    if fetch_clicked:
        with st.spinner(RESEARCH_FETCH_SPINNER):
            fetched_report = analyze_research_for_symbol(symbol)
            _store_ranking_research_report(fetched_report)

    report = _ranking_research_report_from_state(symbol)
    if report is None:
        st.info("資料確認は未実行です。必要な場合は「AIで資料を確認」を押してください。")
        return
    _render_research_summary_panel(report, detail_expanded=False)


def _render_research_summary_panel(
    report: CompanyResearchReport,
    *,
    detail_expanded: bool,
    news_report: StockNewsReport | None = None,
    external_research_result: ExternalResearchFetchResult | None = None,
) -> None:
    summary_bundle = _research_summary_bundle(
        report,
        news_report=news_report,
        external_research_result=external_research_result,
    )
    brief = summary_bundle.brief
    insight = summary_bundle.insight
    company_summary = summary_bundle.company_summary
    etf_summary = summary_bundle.etf_summary
    question_summary = summary_bundle.question_summary
    security_type = summary_bundle.security_type
    research_score = summary_bundle.research_score
    if security_type in {"etf", "fund"} and etf_summary is not None:
        _render_etf_research_summary_panel(etf_summary)
        _render_etf_metric_summary_panel(etf_summary)
        _render_etf_holdings_panel(etf_summary)
        _render_etf_distribution_cost_panel(etf_summary)
        _render_news_summary_panel(etf_summary.news_items, security_type=security_type)
        _render_etf_question_summary_panel(etf_summary)
    elif company_summary is not None and question_summary is not None:
        _render_company_research_summary_panel(
            company_summary,
            security_type=security_type,
        )
        _render_quantitative_summary_panel(company_summary.quantitative)
        _render_ir_summary_panel(company_summary.ir_items, security_type=security_type)
        _render_news_summary_panel(company_summary.news_items, security_type=security_type)
        _render_investment_question_summary_panel(question_summary, security_type=security_type)
    with st.expander("AI読み取りメモを表示", expanded=False):
        if company_summary is not None and company_summary.ai_reading_notes:
            st.markdown(
                _company_research_ai_notes_html(
                    company_summary.ai_reading_notes,
                    security_type=security_type,
                ),
                unsafe_allow_html=True,
            )
        st.markdown(_investment_insight_panel_html(insight), unsafe_allow_html=True)
    with st.expander("根拠確認（会社概要・確認できた事実）を表示", expanded=detail_expanded):
        st.markdown(_research_brief_overview_html(brief), unsafe_allow_html=True)
        st.markdown("##### 読み方サマリー")
        st.markdown(_research_brief_reading_guide_html(brief), unsafe_allow_html=True)
        if report.data_quality.status != "OK":
            st.warning("根拠資料が不足しています。表示内容は確認材料として控えめに扱ってください。")
        _render_research_brief_sections(brief)

    card_rows = _research_brief_source_card_rows(brief)
    if card_rows:
        with st.expander(f"出典カードを表示（{len(card_rows)}件）", expanded=detail_expanded):
            st.caption("出典、公開日、URL、情報源信頼度を確認できます。")
            st.markdown(
                _research_evidence_cards_html(card_rows),
                unsafe_allow_html=True,
            )
    else:
        st.info("根拠カードとして表示できる資料はまだありません。AI調査を更新してください。")

    score_rows = _research_score_summary_rows(research_score)
    if score_rows:
        with st.expander("Research Score（参考）を表示", expanded=False):
            st.caption(
                "根拠資料の充実度・鮮度・信頼度を整理する参考スコアです。売買推奨ではありません。"
            )
            _render_compact_dataframe(score_rows)

    if news_report is not None and news_report.warnings:
        for warning in news_report.warnings:
            st.warning(warning)

    if external_research_result is not None and external_research_result.entries:
        with st.expander(
            f"外部参照ソースを表示（{len(external_research_result.entries)}件）",
            expanded=False,
        ):
            st.caption(
                "AI調査で一時参照した外部ソースです。"
                "取得本文は保存せず、URL・公開日・取得日時を確認材料として残します。"
            )
            st.markdown(
                _external_research_fetch_overview_html(external_research_result),
                unsafe_allow_html=True,
            )
            st.markdown(
                _external_research_source_cards_html(external_research_result),
                unsafe_allow_html=True,
            )

    with st.expander(RESEARCH_DETAIL_EXPANDER_LABEL, expanded=detail_expanded):
        if report.data_quality.status == "OK":
            st.caption(RESEARCH_DETAIL_OK_CAPTION)
        else:
            st.caption("登録資料または検索できた根拠が少ないため、詳細は確認材料として扱います。")
        render_research_evidence_summary(report)
        warning_rows = _research_quality_warning_rows(report)
        if warning_rows:
            st.markdown("###### データ品質・注意点")
            _render_compact_dataframe(warning_rows)
        document_rows = _research_document_display_rows(report)
        if document_rows:
            st.markdown("###### データ取得元・出典")
            _render_compact_dataframe(document_rows)
        grounded_rows = _research_grounded_answer_rows(report)
        if grounded_rows:
            st.markdown("###### 根拠付き回答")
            _render_compact_dataframe(grounded_rows)
        retrieval_quality_rows = _research_retrieval_quality_rows(report)
        if retrieval_quality_rows:
            st.markdown("###### 検索品質")
            _render_compact_dataframe(retrieval_quality_rows)
        score_component_rows = _research_score_component_rows(research_score)
        if score_component_rows:
            st.markdown("###### Research Score内訳")
            _render_compact_dataframe(score_component_rows)
        score_warning_rows = _research_score_warning_rows(research_score)
        if score_warning_rows:
            st.markdown("###### Research Score注意点")
            _render_compact_dataframe(score_warning_rows)
        point_rows = _research_investment_point_rows(report)
        if point_rows:
            st.markdown("###### 要点サマリー")
            _render_compact_dataframe(point_rows)
        claim_rows = _research_extracted_claim_rows(report)
        if claim_rows:
            st.markdown("###### 抽出した主張")
            _render_compact_dataframe(claim_rows)
        evidence_detail_rows = _research_evidence_detail_rows(report)
        if evidence_detail_rows:
            st.markdown("###### 根拠資料の詳細")
            _render_compact_dataframe(evidence_detail_rows)
        if news_report is not None and news_report.news:
            st.markdown("###### 関連ニュース")
            _render_compact_dataframe(_stock_news_detail_rows(news_report))
        if external_research_result is not None:
            st.markdown("###### 外部参照ソース取得状況")
            _render_compact_dataframe(
                _external_research_fetch_summary_rows(external_research_result)
            )


def _research_summary_bundle(
    report: CompanyResearchReport,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> ResearchSummaryBundle:
    cache_key = _research_summary_cache_key(
        report,
        news_report=news_report,
        external_research_result=external_research_result,
    )
    cached = st.session_state.get(RESEARCH_SUMMARY_BUILD_CACHE_STATE_KEY)
    if isinstance(cached, dict):
        cached_bundle = cached.get("bundle")
        if cached.get("key") == cache_key and isinstance(cached_bundle, ResearchSummaryBundle):
            return cached_bundle

    brief = ResearchBriefBuilder().build(
        report,
        news_report=news_report,
        external_research_result=external_research_result,
    )
    insight = InvestmentInsightBuilder().build(
        report,
        news_report=news_report,
        external_research_result=external_research_result,
        brief=brief,
    )
    page_model = ResearchPageViewModelBuilder().build(
        report,
        news_report=news_report,
        external_research_result=external_research_result,
        brief=brief,
        insight=insight,
    )
    bundle = ResearchSummaryBundle(
        brief=brief,
        insight=insight,
        security_type=page_model.security_type,
        company_summary=page_model.company_summary,
        etf_summary=page_model.etf_summary,
        question_summary=page_model.question_summary,
        research_score=ResearchScoreService().score_report(report),
    )
    st.session_state[RESEARCH_SUMMARY_BUILD_CACHE_STATE_KEY] = {
        "key": cache_key,
        "bundle": bundle,
    }
    return bundle


def _research_summary_cache_key(
    report: CompanyResearchReport,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> str:
    payload = {
        "version": "research-summary-build-v2-security-type",
        "report": report.model_dump(mode="json"),
        "news_report": news_report.model_dump(mode="json") if news_report is not None else None,
        "external_research_result": (
            external_research_result.model_dump(mode="json")
            if external_research_result is not None
            else None
        ),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _research_refresh_trace_caption(trace_rows: list[tuple[str, float]]) -> str:
    if not trace_rows:
        return ""
    parts = [f"{label}: {elapsed:.2f}秒" for label, elapsed in trace_rows]
    return "AI調査の処理時間: " + " / ".join(parts)


def _render_company_research_summary_panel(
    summary: CompanyResearchSummary,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> None:
    st.markdown(
        _company_research_summary_html(summary, security_type=security_type),
        unsafe_allow_html=True,
    )


def _render_etf_research_summary_panel(summary: ETFResearchSummary) -> None:
    st.markdown(_etf_research_summary_html(summary), unsafe_allow_html=True)


def _render_etf_metric_summary_panel(summary: ETFResearchSummary) -> None:
    st.markdown(_etf_metric_summary_html(summary), unsafe_allow_html=True)


def _render_etf_holdings_panel(summary: ETFResearchSummary) -> None:
    st.markdown(_etf_holdings_html(summary), unsafe_allow_html=True)


def _render_etf_distribution_cost_panel(summary: ETFResearchSummary) -> None:
    st.markdown(_etf_distribution_cost_html(summary), unsafe_allow_html=True)


def _render_quantitative_summary_panel(summary: QuantitativeSummary) -> None:
    st.markdown(_quantitative_summary_html(summary), unsafe_allow_html=True)


def _render_ir_summary_panel(
    items: Sequence[IRSummaryItem],
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> None:
    st.markdown(_ir_summary_html(items, security_type=security_type), unsafe_allow_html=True)


def _render_news_summary_panel(
    items: Sequence[NewsSummaryItem],
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> None:
    st.markdown(_news_summary_html(items, security_type=security_type), unsafe_allow_html=True)


def _etf_research_summary_html(summary: ETFResearchSummary) -> str:
    badges = [
        (
            f"根拠: {_research_evidence_level_label(getattr(summary, 'evidence_level', 'missing'))}",
            "info",
        ),
        (f"銘柄: {getattr(summary, 'symbol', '')}", "info"),
    ]
    if summary.provider_name:
        badges.append((f"運用会社: {summary.provider_name}", "neutral"))
    badge_markup = "".join(
        f'<span class="research-brief-badge {html.escape(tone)}">{html.escape(label)}</span>'
        for label, tone in badges
        if label.strip()
    )
    rows = [
        ("ファンド概要", summary.fund_overview),
        ("投資対象", summary.investment_target),
        ("対象資産", summary.asset_class or ""),
        ("対象地域", summary.region_focus or ""),
        ("対象セクター", summary.sector_focus or ""),
        ("ベンチマーク指数", summary.benchmark_index or ""),
    ]
    row_markup = "".join(
        '<div class="research-result-brief-item">'
        f'<div class="research-result-brief-label">{html.escape(label)}</div>'
        f'<div class="research-result-brief-value">{html.escape(value or "未取得")}</div>'
        "</div>"
        for label, value in rows
    )
    missing_markup = "".join(
        f'<span class="research-summary-next-chip">{html.escape(str(item))}</span>'
        for item in summary.missing_items[:6]
        if str(item).strip()
    )
    missing_block = (
        '<div class="research-result-brief-label">追加確認が必要なETF情報</div>'
        f'<div class="research-summary-next-list">{missing_markup}</div>'
        if missing_markup
        else ""
    )
    return (
        '<section class="research-result-brief hero">'
        '<div class="research-result-brief-title">ETFリサーチサマリー</div>'
        f'<div class="research-brief-badge-row">{badge_markup}</div>'
        '<div class="research-result-brief-summary">'
        "外部情報から、ETFの投資対象、対象地域、費用、分配金、構成情報を整理します。"
        "</div>"
        f'<div class="research-result-brief-grid">{row_markup}</div>'
        f"{missing_block}"
        "</section>"
    )


def _etf_metric_summary_html(summary: ETFResearchSummary) -> str:
    metric_rows = [
        ("純資産総額", summary.aum),
        ("基準価額 / NAV", summary.nav),
        ("経費率", summary.expense_ratio),
        ("分配金利回り", summary.dividend_yield),
        ("PER", summary.per),
        ("PBR", summary.pbr),
    ]
    metric_markup = "".join(
        '<section class="research-brief-metric-card">'
        f'<div class="research-brief-metric-label">{html.escape(label)}</div>'
        f'<div class="research-brief-metric-value">{html.escape(value or "未取得")}</div>'
        "</section>"
        for label, value in metric_rows
    )
    return (
        '<section class="research-result-brief">'
        '<div class="research-result-brief-title">ファンド指標サマリー</div>'
        f'<div class="research-brief-metric-grid">{metric_markup}</div>'
        "</section>"
    )


def _etf_holdings_html(summary: ETFResearchSummary) -> str:
    holdings = summary.top_holdings[:8]
    if holdings:
        holdings_markup = "".join(
            f'<span class="research-summary-next-chip">{html.escape(item)}</span>'
            for item in holdings
        )
    else:
        holdings_markup = (
            '<div class="research-brief-focus-body">'
            "上位保有銘柄は未取得です。運用会社ページ、月次レポート、構成銘柄データで確認してください。"
            "</div>"
        )
    return (
        '<section class="research-result-brief">'
        '<div class="research-result-brief-title">構成銘柄・投資対象</div>'
        f'<div class="research-summary-next-list">{holdings_markup}</div>'
        "</section>"
    )


def _etf_distribution_cost_html(summary: ETFResearchSummary) -> str:
    notes = summary.risk_notes or [
        "経費率、分配金利回り、ベンチマーク、構成銘柄の更新日を運用会社資料で確認してください。"
    ]
    note_markup = "".join(
        f'<div class="research-brief-next-item">{html.escape(_research_brief_ui_text(note, max_chars=120))}</div>'
        for note in notes[:4]
    )
    return (
        '<section class="research-result-brief">'
        '<div class="research-result-brief-title">分配金・コスト</div>'
        '<div class="research-result-brief-summary">'
        f"経費率: {html.escape(summary.expense_ratio or '未取得')} / "
        f"分配金利回り: {html.escape(summary.dividend_yield or '未取得')}"
        "</div>"
        f'<div class="research-brief-next-list">{note_markup}</div>'
        "</section>"
    )


def _company_research_summary_html(
    summary: CompanyResearchSummary,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    overview = summary.overview
    profile = getattr(overview, "business_profile", None)
    badges = [
        (
            f"根拠: {_research_evidence_level_label(getattr(overview, 'evidence_level', 'missing'))}",
            _research_evidence_level_tone(getattr(overview, "evidence_level", "missing")),
        ),
        (f"銘柄: {getattr(summary, 'symbol', '')}", "info"),
    ]
    if getattr(overview, "company_name", ""):
        badges.append((f"会社名: {overview.company_name}", "neutral"))
    badge_markup = "".join(
        f'<span class="research-brief-badge {html.escape(tone)}">{html.escape(label)}</span>'
        for label, tone in badges
        if label.strip()
    )
    rows = [
        (
            "企業概要",
            _security_specific_research_text(
                getattr(overview, "business_overview", ""),
                security_type=security_type,
            ),
        ),
        (
            "主な事業",
            _company_research_join_values(
                getattr(overview, "main_businesses", [])
                or getattr(overview, "business_segments", [])
            ),
        ),
        (
            "補助事業・関連事業",
            _security_specific_research_text(
                _company_research_join_values(getattr(overview, "supporting_businesses", [])),
                security_type=security_type,
            ),
        ),
        (
            "製品・サービス",
            _security_specific_research_text(
                _company_research_join_values(getattr(overview, "products_services", [])),
                security_type=security_type,
            ),
        ),
        (
            "地域展開",
            _security_specific_research_text(
                _company_research_join_values(getattr(overview, "regions", [])),
                security_type=security_type,
            ),
        ),
        (
            "規模感",
            _security_specific_research_text(
                getattr(overview, "scale_summary", ""),
                security_type=security_type,
            ),
        ),
        (
            "直近の注目ポイント",
            _security_specific_research_text(
                getattr(overview, "recent_focus", ""),
                security_type=security_type,
            ),
        ),
    ]
    if profile is not None:
        industry = getattr(profile, "industry", None)
        sector = getattr(profile, "sector", None)
        if industry or sector:
            profile_labels = []
            if sector:
                profile_labels.append(f"セクター: {_company_research_profile_label(sector)}")
            if industry:
                profile_labels.append(f"業種: {_company_research_profile_label(industry)}")
            rows.insert(
                1,
                (
                    "業種・セクター",
                    _company_research_join_values(profile_labels),
                ),
            )
    row_markup = "".join(
        '<div class="research-result-brief-item">'
        f'<div class="research-result-brief-label">{html.escape(label)}</div>'
        f'<div class="research-result-brief-value">{html.escape(value or "未取得")}</div>'
        "</div>"
        for label, value in rows
    )
    missing_items = getattr(summary, "missing_critical_items", [])[:5]
    missing_markup = "".join(
        '<span class="research-summary-next-chip">'
        f"{html.escape(_security_specific_research_text(str(item), security_type=security_type))}</span>"
        for item in missing_items
        if str(item).strip()
    )
    missing_block = (
        '<div class="research-result-brief-label">追加確認が必要な情報</div>'
        f'<div class="research-summary-next-list">{missing_markup}</div>'
        if missing_markup
        else ""
    )
    return (
        '<section class="research-result-brief hero">'
        f'<div class="research-result-brief-title">{html.escape(RESEARCH_COMPANY_RESEARCH_TITLE)}</div>'
        f'<div class="research-brief-badge-row">{badge_markup}</div>'
        '<div class="research-result-brief-summary">'
        "外部情報・ニュース・保存済み資料から、企業概要、事業内容、規模感、直近情報を整理します。"
        "</div>"
        f'<div class="research-result-brief-grid">{row_markup}</div>'
        f"{missing_block}"
        "</section>"
    )


def _quantitative_summary_html(summary: QuantitativeSummary) -> str:
    metric_rows = [
        ("売上高", summary.revenue),
        ("営業利益", summary.operating_profit),
        ("純利益", summary.net_income),
        ("EPS", summary.eps),
        ("PER", summary.per),
        ("PBR", summary.pbr),
        ("ROE", summary.roe),
        ("配当利回り", summary.dividend_yield),
        ("時価総額", summary.market_cap),
        ("企業価値", getattr(summary, "enterprise_value", None)),
        ("従業員数", getattr(summary, "employee_count", None)),
    ]
    metric_markup = "".join(
        '<section class="research-brief-metric-card">'
        f'<div class="research-brief-metric-label">{html.escape(label)}</div>'
        f'<div class="research-brief-metric-value">{html.escape(value or "未取得")}</div>'
        "</section>"
        for label, value in metric_rows
    )
    source_markup = _research_evidence_badge_markup(summary.evidence_level)
    missing_markup = "".join(
        f'<span class="research-summary-next-chip">{html.escape(str(item))}</span>'
        for item in getattr(summary, "missing_items", [])[:8]
        if str(item).strip()
    )
    missing_block = (
        '<div class="research-result-brief-label">未取得の指標</div>'
        f'<div class="research-summary-next-list">{missing_markup}</div>'
        if missing_markup
        else ""
    )
    return (
        '<section class="research-result-brief">'
        f'<div class="research-result-brief-title">{html.escape(RESEARCH_QUANTITATIVE_SUMMARY_TITLE)}</div>'
        f'<div class="research-brief-badge-row">{source_markup}</div>'
        f'<div class="research-brief-metric-grid">{metric_markup}</div>'
        f"{missing_block}"
        "</section>"
    )


def _ir_summary_html(
    items: Sequence[IRSummaryItem],
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    cards = "".join(_ir_summary_item_html(item, security_type=security_type) for item in items)
    if not cards:
        cards = (
            '<section class="research-brief-focus-card">'
            '<div class="research-brief-focus-body">IR資料の取得状況はまだ整理できていません。</div>'
            "</section>"
        )
    title = "海外IR情報サマリー" if security_type == "foreign_stock" else RESEARCH_IR_SUMMARY_TITLE
    summary_text = (
        "Earnings Release、Annual Report、10-K / 10-Q、Investor Presentation、SEC Filingの取得状況を整理します。"
        if security_type == "foreign_stock"
        else "決算資料、適時開示、中期計画、株主還元情報の取得状況を整理します。"
    )
    return (
        '<section class="research-result-brief">'
        f'<div class="research-result-brief-title">{html.escape(title)}</div>'
        f'<div class="research-result-brief-summary">{html.escape(summary_text)}</div>'
        f'<div class="research-brief-focus-grid">{cards}</div>'
        "</section>"
    )


def _ir_summary_item_html(
    item: IRSummaryItem,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    information_status = getattr(item, "information_status", "missing")
    status_label = _information_status_label(information_status)
    tone = _information_status_tone(information_status)
    document_type = _ir_document_type_display_label(
        getattr(item, "document_type", ""),
        security_type=security_type,
    )
    title = getattr(item, "title", "")
    key_points = "".join(
        f'<div class="research-brief-focus-body">- {html.escape(_research_brief_ui_text(point, max_chars=92))}</div>'
        for point in item.key_points[:2]
    )
    if not key_points:
        summary_text = _ir_item_summary_display_text(
            item,
            document_type=document_type,
            security_type=security_type,
        )
        key_points = f'<div class="research-brief-focus-body">{html.escape(summary_text)}</div>'
    source = item.source_title or ""
    source_markup = (
        '<div class="research-brief-focus-meta">'
        f"出典: {html.escape(_research_brief_ui_text(source, max_chars=62))}</div>"
        if source
        else ""
    )
    source_url = _research_brief_ui_text(str(item.source_url or ""), max_chars=80)
    url_markup = (
        '<div class="research-brief-focus-meta">' f"URL: {html.escape(source_url)}</div>"
        if source_url
        else ""
    )
    return (
        '<section class="research-brief-focus-card">'
        '<div class="research-brief-focus-badge-row">'
        f'<span class="research-evidence-pill confidence-{html.escape(tone)}">{html.escape(status_label)}</span>'
        "</div>"
        f'<div class="research-brief-focus-title">{html.escape(document_type)}</div>'
        f'<div class="research-brief-focus-meta">資料タイトル: {html.escape(_research_brief_ui_text(title, max_chars=64))}</div>'
        f"{key_points}{source_markup}{url_markup}"
        "</section>"
    )


def _ir_document_type_display_label(
    document_type: str,
    *,
    security_type: SecurityResearchType,
) -> str:
    if security_type != "foreign_stock":
        return document_type
    labels = {
        "決算短信": "Earnings Release",
        "決算説明資料": "Investor Presentation",
        "有価証券報告書": "Annual Report / 10-K",
        "適時開示": "SEC Filing / Company Release",
        "中期経営計画": "Investor Presentation",
        "配当・自社株買い": "Dividend / Buyback Policy",
        "業績予想修正": "Guidance / Forecast Update",
    }
    return labels.get(document_type, document_type)


def _ir_item_summary_display_text(
    item: IRSummaryItem,
    *,
    document_type: str,
    security_type: SecurityResearchType,
) -> str:
    if security_type == "foreign_stock":
        if getattr(item, "information_status", "missing") == "missing":
            return (
                f"{document_type}は未取得です。公式IR、Annual Report、10-K / 10-Q、"
                "Earnings Release、SEC Filingで確認してください。"
            )
        if getattr(item, "information_status", "missing") == "unparsed":
            return "資料タイトルまたはURLは取得済みですが、本文は未解析です。詳細は公式IRまたはSEC Filingで確認してください。"
        return item.summary or f"{document_type}から確認できる要点があります。"
    return item.summary or "追加確認が必要です。"


def _news_summary_html(
    items: Sequence[NewsSummaryItem],
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    if not items:
        missing_text = (
            "ニュース・開示は取得できていません。必要に応じて外部ニュース、公式IR、SEC Filingを追加確認してください。"
            if security_type == "foreign_stock"
            else "ニュース・適時開示は取得できていません。必要に応じて外部ニュースや公式IRを追加確認してください。"
        )
        body = '<div class="research-brief-focus-body">' f"{html.escape(missing_text)}</div>"
    else:
        body = "".join(
            _news_summary_item_html(index, item, security_type=security_type)
            for index, item in enumerate(items, 1)
        )
    return (
        '<section class="research-result-brief">'
        f'<div class="research-result-brief-title">{html.escape(RESEARCH_NEWS_SUMMARY_TITLE)}</div>'
        f'<div class="research-evidence-list">{body}</div>'
        "</section>"
    )


def _news_summary_item_html(
    index: int,
    item: NewsSummaryItem,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    published = item.published_at.isoformat() if item.published_at else "日付未設定"
    impact = _news_impact_hint_label(item.impact_hint)
    topic_type = _latest_topic_type_label(
        getattr(item, "topic_type", "news"),
        security_type=security_type,
    )
    source = _latest_topic_source_label(item, security_type=security_type)
    confirmation_label = _latest_topic_confirmation_label(
        item,
        security_type=security_type,
    )
    status_label = _information_status_label(getattr(item, "information_status", "unverified"))
    status_tone = _information_status_tone(getattr(item, "information_status", "unverified"))
    url_markup = (
        '<div class="research-evidence-meta">'
        f"URL: {html.escape(_research_brief_ui_text(item.source_url or '', max_chars=96))}</div>"
        if item.source_url
        else ""
    )
    return (
        '<article class="research-evidence-item">'
        '<div class="research-evidence-card-header">'
        f'<span class="research-evidence-pill">{html.escape(topic_type)} {index}</span>'
        f'<span class="research-evidence-pill">影響カテゴリ: {html.escape(impact)}</span>'
        f'<span class="research-evidence-pill confidence-low">公式確認: {html.escape(confirmation_label)}</span>'
        f'<span class="research-evidence-pill confidence-{html.escape(status_tone)}">状態: {html.escape(status_label)}</span>'
        "</div>"
        f'<div class="research-evidence-title">{html.escape(item.title)}</div>'
        f'<div class="research-evidence-body">{html.escape(item.summary)}</div>'
        f'<div class="research-evidence-meta">出典: {html.escape(source)} / {html.escape(published)}</div>'
        f"{url_markup}"
        "</article>"
    )


def _latest_topic_type_label(
    topic_type: str,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    if security_type == "foreign_stock":
        labels = {
            "news": "ニュース",
            "tdnet": "Company Release",
            "ir_disclosure": "Company Release",
            "earnings": "Earnings",
            "forecast_revision": "Guidance Update",
            "shareholder_return": "Dividend / Buyback",
            "business_reorganization": "Business Reorganization",
            "product": "Product / Service",
            "governance": "Governance",
            "unknown": "トピック",
        }
        return labels.get(topic_type, "トピック")
    labels = {
        "news": "ニュース",
        "tdnet": "TDnet",
        "ir_disclosure": "適時開示",
        "earnings": "決算",
        "forecast_revision": "業績予想修正",
        "shareholder_return": "株主還元",
        "business_reorganization": "事業再編",
        "product": "製品・サービス",
        "governance": "ガバナンス",
        "unknown": "トピック",
    }
    return labels.get(topic_type, "トピック")


def _latest_topic_confirmation_label(
    item: NewsSummaryItem,
    *,
    security_type: SecurityResearchType,
) -> str:
    if not getattr(item, "official_confirmation_required", True):
        return "公式開示資料"
    if security_type == "foreign_stock":
        return "未確認（公式IR・SEC Filing確認が必要）"
    return "未確認（公式IR確認が必要）"


def _latest_topic_source_label(
    item: NewsSummaryItem,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    topic_type = getattr(item, "topic_type", "news")
    if security_type == "foreign_stock" and topic_type in {
        "tdnet",
        "ir_disclosure",
        "earnings",
        "forecast_revision",
        "shareholder_return",
    }:
        return item.source_title or "公式IR・SEC Filing"
    if topic_type in {
        "tdnet",
        "ir_disclosure",
        "earnings",
        "forecast_revision",
        "shareholder_return",
    }:
        return "TDnet適時開示"
    if getattr(item, "official_confirmation_required", True):
        return item.source_title or "外部ニュース"
    return item.source_title or "公式開示"


def _company_research_profile_label(value: str) -> str:
    labels = {
        "Consumer Cyclical": "一般消費財",
        "Technology": "テクノロジー",
        "Financial Services": "金融サービス",
        "Healthcare": "ヘルスケア",
        "Industrials": "資本財・サービス",
        "Communication Services": "通信サービス",
        "Utilities": "公益・インフラ",
        "Auto Manufacturers": "自動車メーカー",
        "Utilities - Regulated Gas": "ガス・公益インフラ",
        "Semiconductor Equipment & Materials": "半導体製造装置・材料",
        "Scientific & Technical Instruments": "科学・計測機器",
        "Consumer Electronics": "民生用電機",
    }
    return labels.get(value, value)


def _company_research_ai_notes_html(
    notes: Sequence[str],
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    body = "".join(
        '<div class="research-brief-next-item">'
        f"{html.escape(_research_brief_ui_text(_security_specific_research_text(note, security_type=security_type), max_chars=150))}</div>"
        for note in notes[:6]
    )
    return (
        '<section class="research-result-brief">'
        f'<div class="research-result-brief-title">{html.escape(RESEARCH_AI_READING_MEMO_TITLE)}</div>'
        f'<div class="research-brief-next-list">{body}</div>'
        "</section>"
    )


def _company_research_join_values(values: Sequence[str]) -> str:
    return "、".join(str(value) for value in values if str(value).strip())


def _research_evidence_badge_markup(level: str) -> str:
    label = _research_evidence_level_label(level)
    tone = _research_evidence_level_tone(level)
    return (
        f'<span class="research-brief-badge {html.escape(tone)}">'
        f"根拠: {html.escape(label)}</span>"
    )


def _research_evidence_level_label(level: str) -> str:
    labels = {
        "high": "高",
        "medium": "中",
        "low": "低",
        "missing": "不足",
    }
    return labels.get(level, "不足")


def _research_evidence_level_tone(level: str) -> str:
    tones = {
        "high": "info",
        "medium": "warning",
        "low": "low",
        "missing": "neutral",
    }
    return tones.get(level, "neutral")


def _research_evidence_level_confidence_tone(level: str) -> str:
    tones = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "missing": "unknown",
    }
    return tones.get(level, "unknown")


def _information_status_label(status: str) -> str:
    labels = {
        "found": "取得済み・要約済み",
        "missing": "未取得",
        "unparsed": "取得済み・本文未解析",
        "unverified": "公式未確認",
        "not_applicable": "対象外",
    }
    return labels.get(status, "未取得")


def _information_status_tone(status: str) -> str:
    tones = {
        "found": "high",
        "missing": "unknown",
        "unparsed": "medium",
        "unverified": "low",
        "not_applicable": "unknown",
    }
    return tones.get(status, "unknown")


def _news_impact_hint_label(impact: str) -> str:
    labels = {
        "business": "事業影響あり",
        "financial": "財務影響あり",
        "market": "市場材料",
        "governance": "ガバナンス",
        "product": "製品・サービス",
        "ir": "IR・適時開示",
        "unknown": "不明",
    }
    return labels.get(impact, "不明")


def _render_investment_insight_panel(insight: InvestmentInsight) -> None:
    st.markdown(_investment_insight_panel_html(insight), unsafe_allow_html=True)


def _render_investment_insight_summary_panel(insight: InvestmentInsight) -> None:
    st.markdown(_investment_insight_summary_html(insight), unsafe_allow_html=True)


def _render_investment_insight_materials_panel(insight: InvestmentInsight) -> None:
    st.markdown(_investment_insight_materials_html(insight), unsafe_allow_html=True)


def _investment_insight_panel_html(insight: InvestmentInsight) -> str:
    return (
        f"{_investment_insight_summary_html(insight)}{_investment_insight_materials_html(insight)}"
    )


def _investment_insight_summary_html(insight: InvestmentInsight) -> str:
    status_label = _investment_insight_status_label(insight)
    confidence_label = _investment_insight_confidence_label(insight, status_label)
    primary_action_label = _investment_insight_primary_action_label(insight, status_label)
    badges = [
        (f"ステータス: {status_label}", _investment_status_tone(status_label)),
        (
            f"信頼度: {confidence_label}",
            _investment_confidence_label_tone(confidence_label, status_label),
        ),
        (f"次のアクション: {primary_action_label}", "info"),
    ]
    badge_markup = "".join(
        f'<span class="research-brief-badge {html.escape(tone)}">{html.escape(label)}</span>'
        for label, tone in badges
    )
    next_materials = _investment_insight_next_materials(insight)
    next_material_markup = "".join(
        f'<span class="research-summary-next-chip">{html.escape(item)}</span>'
        for item in next_materials
    )
    hero = (
        '<section class="research-result-brief hero">'
        f'<div class="research-result-brief-title">{html.escape(RESEARCH_INVESTMENT_INSIGHT_TITLE)}</div>'
        f'<div class="research-brief-badge-row">{badge_markup}</div>'
        f'<div class="research-result-brief-label">{html.escape(RESEARCH_INVESTMENT_INSIGHT_SUMMARY_LABEL)}</div>'
        f'<div class="research-result-brief-summary">{html.escape(insight.short_summary)}</div>'
        '<div class="research-result-brief-label">追加確認する資料・指標</div>'
        f'<div class="research-summary-next-list">{next_material_markup}</div>'
        f'<div class="research-result-brief-note">{html.escape(RESEARCH_INVESTMENT_INSIGHT_NOTE)}</div>'
        "</section>"
    )
    return hero


def _investment_insight_materials_html(insight: InvestmentInsight) -> str:
    cards = [
        _investment_insight_items_card_html(
            RESEARCH_INVESTMENT_INSIGHT_POSITIVE_LABEL,
            _investment_insight_positive_display_items(insight),
            fallback="確認できた情報はまだ限定的です。公式資料とニュースを追加確認します。",
            limit=3,
        ),
        _investment_insight_items_card_html(
            RESEARCH_INVESTMENT_INSIGHT_NEGATIVE_LABEL,
            getattr(insight, "negative_points", []),
            fallback="注意して読む情報は未確認です。根拠不足や公式資料不足は別枠で確認します。",
            limit=3,
        ),
        _investment_insight_gap_card_html(getattr(insight, "confirmation_gaps", [])),
    ]
    return f'<div class="research-brief-focus-grid">{"".join(cards)}</div>'


def _render_investment_question_summary_panel(
    summary: InvestmentQuestionSummary,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> None:
    st.markdown(
        _investment_question_summary_intro_html(summary, security_type=security_type),
        unsafe_allow_html=True,
    )
    primary_answers = _investment_question_primary_answers(summary)
    st.markdown(
        _investment_question_answers_html(primary_answers, security_type=security_type),
        unsafe_allow_html=True,
    )
    secondary_answers = [
        answer for answer in getattr(summary, "answers", []) if answer not in primary_answers
    ]
    if secondary_answers:
        with st.expander(RESEARCH_INVESTMENT_QUESTION_MORE_LABEL, expanded=False):
            st.markdown(
                _investment_question_answers_html(secondary_answers, security_type=security_type),
                unsafe_allow_html=True,
            )


def _investment_question_summary_intro_html(
    summary: InvestmentQuestionSummary,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    top_takeaway = _research_brief_ui_text(getattr(summary, "top_takeaway", ""), max_chars=170)
    top_takeaway = _security_specific_research_text(top_takeaway, security_type=security_type)
    missing_items = getattr(summary, "missing_critical_items", [])[:4]
    missing_markup = "".join(
        f'<span class="research-summary-next-chip">'
        f"{html.escape(_security_specific_research_text(str(item), security_type=security_type))}</span>"
        for item in missing_items
        if str(item).strip()
    )
    missing_block = (
        '<div class="research-result-brief-label">優先して確認</div>'
        f'<div class="research-summary-next-list">{missing_markup}</div>'
        if missing_markup
        else ""
    )
    summary_body = (
        top_takeaway or "企業理解に必要な確認ポイントを、取得できた根拠ごとに整理します。"
    )
    return (
        '<section class="research-result-brief">'
        f'<div class="research-result-brief-title">{html.escape(RESEARCH_INVESTMENT_QUESTION_SUMMARY_TITLE)}</div>'
        f'<div class="research-result-brief-summary">{html.escape(summary_body)}</div>'
        f"{missing_block}"
        "</section>"
    )


def _investment_question_primary_answers(
    summary: InvestmentQuestionSummary,
) -> list[InvestmentQuestionAnswer]:
    primary_categories = (
        "business_model",
        "financial_trend",
        "forecast",
        "growth_driver",
        "key_takeaway",
    )
    answers_by_category = {
        getattr(answer, "category", ""): answer for answer in getattr(summary, "answers", [])
    }
    return [
        answers_by_category[category]
        for category in primary_categories
        if category in answers_by_category
    ]


def _investment_question_answers_html(
    answers: Sequence[InvestmentQuestionAnswer],
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    cards = "".join(
        _investment_question_answer_card_html(answer, security_type=security_type)
        for answer in answers
    )
    if not cards:
        cards = (
            '<section class="research-brief-focus-card">'
            '<div class="research-brief-focus-body">確認ポイントはまだ作成されていません。</div>'
            "</section>"
        )
    return f'<div class="research-brief-focus-grid">{cards}</div>'


def _investment_question_answer_card_html(
    answer: InvestmentQuestionAnswer,
    *,
    security_type: SecurityResearchType = "domestic_stock",
) -> str:
    evidence_label = _investment_question_evidence_label(
        getattr(answer, "evidence_level", "missing")
    )
    evidence_tone = _investment_question_evidence_tone(getattr(answer, "evidence_level", "missing"))
    source_titles = [
        _research_brief_ui_text(str(title), max_chars=46)
        for title in getattr(answer, "source_titles", [])[:2]
        if str(title).strip()
    ]
    source_markup = (
        '<div class="research-brief-focus-meta">'
        f"出典: {html.escape(' / '.join(source_titles))}</div>"
        if source_titles
        else ""
    )
    answer_text = _security_specific_research_text(
        str(answer.answer),
        security_type=security_type,
    )
    missing_reason = _security_specific_research_text(
        _research_brief_ui_text(
            getattr(answer, "missing_reason", ""),
            max_chars=82,
        ),
        security_type=security_type,
    )
    missing_markup = (
        '<div class="research-brief-focus-meta">' f"不足: {html.escape(missing_reason)}</div>"
        if missing_reason
        else ""
    )
    return (
        '<section class="research-brief-focus-card">'
        '<div class="research-brief-focus-badge-row">'
        f'<span class="research-evidence-pill confidence-{html.escape(evidence_tone)}">'
        f"根拠: {html.escape(evidence_label)}</span>"
        "</div>"
        f'<div class="research-brief-focus-title">Q. {html.escape(str(answer.question))}</div>'
        f'<div class="research-brief-focus-body">A. {html.escape(answer_text)}</div>'
        f"{source_markup}{missing_markup}"
        "</section>"
    )


def _investment_question_evidence_label(level: str) -> str:
    labels = {
        "high": "高",
        "medium": "中",
        "low": "低",
        "missing": "不足",
    }
    return labels.get(level, "不足")


def _investment_question_evidence_tone(level: str) -> str:
    tones = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "missing": "unknown",
    }
    return tones.get(level, "unknown")


def _render_etf_question_summary_panel(summary: ETFResearchSummary) -> None:
    st.markdown(_etf_question_summary_html(summary), unsafe_allow_html=True)


def _etf_question_summary_html(summary: ETFResearchSummary) -> str:
    cards = "".join(
        _etf_question_card_html(question, answer)
        for question, answer in [
            (
                "このETFは何に投資している？",
                summary.investment_target
                or "投資対象は未取得です。運用会社ページ、目論見書、月次レポートで確認してください。",
            ),
            (
                "対象地域・対象資産は何か？",
                _etf_question_region_asset_answer(summary),
            ),
            (
                "上位保有銘柄は何か？",
                (
                    "上位保有銘柄は"
                    + "、".join(summary.top_holdings[:5])
                    + "です。構成比率と更新日は運用会社資料で確認してください。"
                    if summary.top_holdings
                    else "上位保有銘柄は未取得です。構成銘柄データまたは月次レポートで確認してください。"
                ),
            ),
            (
                "経費率や分配金はどうか？",
                (
                    f"経費率は{summary.expense_ratio or '未取得'}、分配金利回りは"
                    f"{summary.dividend_yield or '未取得'}です。未取得項目は運用会社ページで確認してください。"
                ),
            ),
            (
                "このETFを見るうえで一番重要な論点は何か？",
                _etf_question_key_takeaway(summary),
            ),
        ]
    )
    missing_markup = "".join(
        f'<span class="research-summary-next-chip">{html.escape(item)}</span>'
        for item in summary.missing_items[:5]
    )
    missing_block = (
        '<div class="research-result-brief-label">優先して確認</div>'
        f'<div class="research-summary-next-list">{missing_markup}</div>'
        if missing_markup
        else ""
    )
    return (
        '<section class="research-result-brief">'
        '<div class="research-result-brief-title">ETF理解の確認ポイント</div>'
        '<div class="research-result-brief-summary">'
        "ETFは企業の売上や利益ではなく、投資対象、構成銘柄、費用、分配金、ベンチマークを中心に確認します。"
        "</div>"
        f"{missing_block}"
        f'<div class="research-brief-focus-grid">{cards}</div>'
        "</section>"
    )


def _etf_question_card_html(question: str, answer: str) -> str:
    return (
        '<section class="research-brief-focus-card">'
        '<div class="research-brief-focus-badge-row">'
        '<span class="research-evidence-pill confidence-medium">根拠: 確認材料</span>'
        "</div>"
        f'<div class="research-brief-focus-title">Q. {html.escape(question)}</div>'
        f'<div class="research-brief-focus-body">A. {html.escape(answer)}</div>'
        "</section>"
    )


def _etf_question_region_asset_answer(summary: ETFResearchSummary) -> str:
    parts = []
    if summary.region_focus:
        parts.append(f"対象地域は{summary.region_focus}")
    if summary.asset_class:
        parts.append(f"対象資産は{summary.asset_class}")
    if summary.sector_focus:
        parts.append(f"対象セクターは{summary.sector_focus}")
    if parts:
        return "、".join(parts) + "として整理できます。正確な投資方針は目論見書で確認してください。"
    return (
        "対象地域・対象資産は未取得です。目論見書、月次レポート、ETF情報サイトで確認してください。"
    )


def _etf_question_key_takeaway(summary: ETFResearchSummary) -> str:
    if summary.missing_items:
        return (
            "現時点では、"
            + "、".join(summary.missing_items[:4])
            + "を確認することが最優先です。企業IRではなく、運用会社資料とETF情報サイトで確認してください。"
        )
    return "投資対象、費用、分配金、構成銘柄、ベンチマークの整合性を確認することが重要です。"


def _security_specific_research_text(
    text: str,
    *,
    security_type: SecurityResearchType,
) -> str:
    if security_type != "foreign_stock":
        return text
    replacements = {
        "決算短信・有価証券報告書・決算説明資料": "Earnings Release、Annual Report、10-K / 10-Q、Investor Presentation",
        "決算短信": "Earnings Release",
        "有価証券報告書": "Annual Report / 10-K",
        "決算説明資料": "Investor Presentation",
        "適時開示": "Company Release",
        "TDnet": "公式IR",
        "EDINET": "SEC Filing",
    }
    converted = text
    for source, target in replacements.items():
        converted = converted.replace(source, target)
    return converted


def _investment_insight_positive_display_items(
    insight: InvestmentInsight,
) -> Sequence[InvestmentInsightItem]:
    positive_points = getattr(insight, "positive_points", [])
    if positive_points:
        return positive_points
    return getattr(insight, "neutral_points", [])[:3]


def _investment_insight_next_materials(insight: InvestmentInsight) -> list[str]:
    gap_text = " ".join(getattr(insight, "confirmation_gaps", []))
    materials: list[str] = []
    if "決算" in gap_text or "公式" in gap_text:
        materials.extend(["決算短信", "有価証券報告書", "決算説明資料"])
    if any(keyword in gap_text for keyword in ("PER", "PBR", "ROE")):
        materials.append("PER / PBR / ROE")
    if "EPS" in gap_text:
        materials.append("EPS")
    if "配当" in gap_text:
        materials.append("配当方針")
    if not materials:
        materials.extend(["出典カード", "公開日", "対象期間"])
    return list(dict.fromkeys(materials))[:6]


def _investment_insight_status_label(insight: InvestmentInsight) -> str:
    status_label = getattr(insight, "status_label", "")
    if status_label:
        return str(status_label)
    positive_points = getattr(insight, "positive_points", [])
    negative_points = getattr(insight, "negative_points", [])
    action_hints = set(getattr(insight, "action_hints", []))
    gap_text = " ".join(getattr(insight, "confirmation_gaps", []))
    if "insufficient_evidence" in action_hints:
        return "判断材料不足"
    if positive_points and negative_points:
        return "材料混在"
    if "ニュース" in gap_text and ("公式IR" in gap_text or "裏取り" in gap_text):
        return "ニュース先行"
    if any(keyword in gap_text for keyword in ("PER", "PBR", "ROE", "EPS")):
        return "定量指標不足"
    if "公式" in gap_text or "決算" in gap_text:
        return "公式資料確認待ち"
    return "監視向き"


def _investment_insight_confidence_label(
    insight: InvestmentInsight,
    status_label: str,
) -> str:
    confidence_label = getattr(insight, "confidence_label", "")
    if confidence_label:
        return str(confidence_label)
    if status_label in {"判断材料不足", "公式資料確認待ち", "ニュース先行"}:
        return "低"
    if status_label == "定量指標不足":
        return "低〜中"
    if status_label == "材料混在":
        return "中"
    confidence = getattr(insight, "confidence", "unknown")
    labels = {
        "high": "中〜高",
        "medium": "中",
        "low": "低",
        "unknown": "低",
    }
    return labels.get(str(confidence), "低")


def _investment_insight_primary_action_label(
    insight: InvestmentInsight,
    status_label: str,
) -> str:
    primary_action_label = getattr(insight, "primary_action_label", "")
    if primary_action_label:
        return str(primary_action_label)
    labels = {
        "監視向き": "継続して材料を確認",
        "材料混在": "良悪材料を比較",
        "判断材料不足": "資料追加が必要",
        "公式資料確認待ち": "決算資料を確認",
        "ニュース先行": "公式IRで裏取り",
        "定量指標不足": "PER/PBR/ROEを確認",
    }
    return labels.get(status_label, "確認資料を追加")


def _investment_status_tone(status_label: str) -> str:
    warning_statuses = {"公式資料確認待ち", "ニュース先行", "定量指標不足", "材料混在"}
    low_statuses = {"判断材料不足"}
    if status_label in warning_statuses:
        return "warning"
    if status_label in low_statuses:
        return "low"
    return "info"


def _investment_confidence_label_tone(confidence_label: str, status_label: str) -> str:
    if "低" in confidence_label and "中" not in confidence_label:
        return "low"
    if "低" in confidence_label or status_label in {"材料混在", "定量指標不足"}:
        return "warning"
    return "info"


def _investment_insight_items_card_html(
    title: str,
    items: Sequence[InvestmentInsightItem],
    *,
    fallback: str,
    limit: int,
) -> str:
    visible_items = [item for item in items[:limit] if item.summary.strip()]
    body = "".join(_investment_insight_item_html(item) for item in visible_items)
    if len(items) > limit:
        body += (
            '<div class="research-brief-focus-more">'
            f"ほか {len(items) - limit}件は詳細データで確認できます。</div>"
        )
    if not body:
        body = f'<div class="research-brief-focus-body">{html.escape(fallback)}</div>'
    return (
        '<section class="research-brief-focus-card">'
        f'<div class="research-brief-focus-title">{html.escape(title)}</div>'
        f'<div class="research-brief-focus-list">{body}</div>'
        "</section>"
    )


def _investment_insight_item_html(item: InvestmentInsightItem) -> str:
    confidence = _research_source_confidence_short_label(item.source_confidence)
    confidence_tone = _research_source_confidence_tone(item.source_confidence)
    source_type = _research_source_type_label(item.source_type)
    published = item.published_at.isoformat() if item.published_at else "日付未設定"
    summary = _research_brief_ui_text(item.summary, max_chars=138)
    source_title = _research_brief_ui_text(item.source_title, max_chars=72)
    reason = _research_brief_ui_text(item.reason, max_chars=92) if item.reason else ""
    reason_markup = (
        f'<div class="research-brief-focus-meta">理由: {html.escape(reason)}</div>'
        if reason
        else ""
    )
    return (
        '<div class="research-brief-focus-material">'
        '<div class="research-brief-focus-badge-row">'
        f'<span class="research-evidence-pill">{html.escape(source_type)}</span>'
        f'<span class="research-evidence-pill confidence-{html.escape(confidence_tone)}">'
        f"{html.escape(confidence)}</span>"
        "</div>"
        f'<div class="research-brief-focus-body">{html.escape(summary)}</div>'
        '<div class="research-brief-focus-meta">'
        f"出典: {html.escape(source_title)} / {html.escape(published)}</div>"
        f"{reason_markup}"
        "</div>"
    )


def _investment_insight_gap_card_html(gaps: Sequence[str]) -> str:
    visible_gaps = [_research_brief_ui_text(gap, max_chars=132) for gap in gaps[:5]]
    body = "".join(
        f'<div class="research-brief-focus-body">{html.escape(gap)}</div>'
        for gap in visible_gaps
        if gap.strip()
    )
    if len(gaps) > 5:
        body += (
            '<div class="research-brief-focus-more">'
            f"ほか {len(gaps) - 5}件は詳細データで確認できます。</div>"
        )
    if not body:
        body = (
            '<div class="research-brief-focus-body">'
            "不足している情報は未検出です。出典カードで資料名、公開日、URLを確認します。</div>"
        )
    return (
        '<section class="research-brief-focus-card">'
        f'<div class="research-brief-focus-title">{html.escape(RESEARCH_INVESTMENT_INSIGHT_GAPS_LABEL)}</div>'
        f'<div class="research-brief-focus-list">{body}</div>'
        "</section>"
    )


def _investment_action_hint_label(hint: InvestmentActionHint) -> str:
    labels: dict[InvestmentActionHint, str] = {
        "watch": "監視・追加確認",
        "review": "材料を読み比べる",
        "wait_for_confirmation": "定量指標待ち",
        "check_official_materials": "公式資料確認",
        "insufficient_evidence": "根拠不足",
    }
    return labels.get(hint, "確認材料")


def _investment_action_hint_tone(hint: InvestmentActionHint) -> str:
    tones: dict[InvestmentActionHint, str] = {
        "watch": "info",
        "review": "warning",
        "wait_for_confirmation": "warning",
        "check_official_materials": "warning",
        "insufficient_evidence": "low",
    }
    return tones.get(hint, "neutral")


def _render_research_brief_sections(brief: ResearchBrief) -> None:
    st.markdown("##### 確認ポイント")
    st.markdown(_research_brief_focus_html(brief), unsafe_allow_html=True)

    metric_markup = _research_brief_metric_cards_html(brief)
    if metric_markup:
        st.markdown("##### 定量指標")
        st.markdown(metric_markup, unsafe_allow_html=True)

    gap_markup = _research_brief_gap_panel_html(brief)
    if gap_markup:
        st.markdown("##### 不足している情報")
        st.markdown(gap_markup, unsafe_allow_html=True)

    action_markup = _research_brief_next_actions_html(brief)
    if action_markup:
        st.markdown("##### 追加確認する資料・指標")
        st.markdown(action_markup, unsafe_allow_html=True)


def _research_brief_overview_html(brief: ResearchBrief) -> str:
    badge_markup = _research_brief_status_badges_html(brief)
    detail_hint = (
        "指標件数、出典カード、Research Score は下の折りたたみで確認できます。"
        "ここでは根拠確認の要点だけを表示します。"
    )
    return (
        '<section class="research-result-brief hero">'
        '<div class="research-result-brief-title">AI整理メモ</div>'
        f"{badge_markup}"
        f'<div class="research-result-brief-summary">{html.escape(brief.memo)}</div>'
        f'<div class="research-result-brief-note">{html.escape(detail_hint)}</div>'
        "</section>"
    )


def _research_brief_business_html(brief: ResearchBrief) -> str:
    return (
        '<section class="research-result-brief">'
        '<div class="research-result-brief-summary">'
        f"{html.escape(_research_brief_ui_text(brief.business_overview, max_chars=220))}</div>"
        "</section>"
    )


def _research_brief_reading_guide_rows(brief: ResearchBrief) -> list[dict[str, str]]:
    fact_summary = brief.fact_summary
    positive_count = len(brief.positive_materials or brief.positive_candidates)
    caution_count = len(brief.caution_materials or brief.caution_candidates)
    high_source_count = sum(1 for card in brief.source_cards if card.source_confidence == "high")
    source_count = len(brief.source_cards)

    if fact_summary is not None:
        confirmed = _research_brief_fact_confirmed_text(fact_summary)
    else:
        confirmed_parts: list[str] = []
        if source_count:
            source_phrase = (
                "公式資料を含む資料で確認しました"
                if high_source_count
                else "外部データ・ニュース中心に確認しました"
            )
            confirmed_parts.append(source_phrase)
        if positive_count:
            material = (
                brief.positive_materials[0].summary
                if brief.positive_materials
                else brief.positive_candidates[0]
            )
            confirmed_parts.append(_research_brief_ui_text(material, max_chars=72))
        if brief.metrics:
            confirmed_parts.append("主要数値も一部確認しました")
        if confirmed_parts:
            confirmed = (
                "。".join(confirmed_parts) + "。企業理解のための整理で、売買推奨ではありません。"
            )
        else:
            confirmed = "確認済みの根拠はまだ少なめです。まず資料登録やAI調査の更新を確認します。"

    if fact_summary is not None and fact_summary.caution_materials:
        caution_item = fact_summary.caution_materials[0]
        caution = (
            f"{caution_item.label}: "
            f"{_research_brief_ui_text(caution_item.value, max_chars=86)}"
            " ニュースや外部データ由来の材料は、公式資料で裏取りして読みます。"
        )
    elif caution_count:
        caution_source = (
            brief.caution_materials[0].summary
            if brief.caution_materials
            else brief.caution_candidates[0]
        )
        caution = (
            f"{_research_brief_ui_text(caution_source, max_chars=86)} "
            "ニュースや外部データ由来の材料は、公式資料で裏取りして読みます。"
        )
    elif brief.confirmation_gaps:
        caution = (
            "注意点よりも確認不足が中心です。根拠不足を悪材料と混同せず、追加資料で確認します。"
        )
    else:
        caution = "目立つ注意点は未確認です。価格、業績、出典日付を合わせて確認します。"

    if fact_summary is not None and fact_summary.missing_items:
        missing_item = fact_summary.missing_items[0]
        gap = (
            f"{missing_item.label}: {_research_brief_ui_text(missing_item.reason, max_chars=88)}。"
            f"{missing_item.next_source_hint}で追加確認します。"
        )
    elif brief.missing_metrics:
        missing = "、".join(brief.missing_metrics[:5])
        if len(brief.missing_metrics) > 5:
            missing += f" ほか{len(brief.missing_metrics) - 5}件"
        gap = (
            f"まだ確認できていない数値: {missing}。悪材料ではなく、公式資料で追加確認する項目です。"
        )
    elif brief.confirmation_gaps:
        gap = _research_brief_gap_display_text(brief.confirmation_gaps[0])
    else:
        gap = "大きな確認不足はありません。出典カードで資料名、公開日、URLを念のため確認します。"

    next_action = (
        _research_brief_ui_text(brief.next_actions[0], max_chars=96)
        if brief.next_actions
        else "出典カードで資料名、公開日、URL、情報源信頼度を確認します。"
    )

    return [
        {"label": "確認できたこと", "body": confirmed, "tone": "positive"},
        {"label": "注意して見ること", "body": caution, "tone": "warning"},
        {"label": "まだ足りないこと", "body": gap, "tone": "warning"},
        {"label": "次にやること", "body": next_action, "tone": "neutral"},
    ]


def _research_brief_reading_guide_html(brief: ResearchBrief) -> str:
    item_markup = "".join(
        (
            f'<div class="research-brief-reading-item tone-{html.escape(row["tone"])}">'
            f'<div class="research-brief-reading-label">{html.escape(row["label"])}</div>'
            '<div class="research-brief-reading-body">'
            f'{html.escape(_research_brief_ui_text(row["body"], max_chars=128))}</div>'
            "</div>"
        )
        for row in _research_brief_reading_guide_rows(brief)
    )
    return f'<div class="research-brief-reading-grid">{item_markup}</div>'


def _research_brief_focus_html(brief: ResearchBrief) -> str:
    cards = [
        _research_brief_focus_card_html(
            "会社概要",
            _research_brief_company_profile_items(brief),
            limit=4,
        ),
        _research_brief_focus_card_html(
            "確認できた事実",
            _research_brief_confirmed_fact_items(brief),
            limit=5,
        ),
        _research_brief_focus_card_html(
            "公式資料で未確認",
            _research_brief_unconfirmed_items(brief),
            limit=4,
        ),
    ]
    return f'<div class="research-brief-focus-grid">{"".join(cards)}</div>'


def _research_brief_company_profile_items(brief: ResearchBrief) -> list[str]:
    items = [_research_brief_ui_text(brief.business_overview, max_chars=170)]
    fact_summary = brief.fact_summary
    if fact_summary is None:
        return items
    if fact_summary.business_segments:
        items.append(f"主要事業: {fact_summary.business_segments[0].value}")
    if fact_summary.business_regions:
        items.append(f"地域: {fact_summary.business_regions[0].value}")
    if fact_summary.revenue_drivers:
        items.append(f"収益源: {fact_summary.revenue_drivers[0].value}")
    return _unique_text_items(items)


def _research_brief_confirmed_fact_items(brief: ResearchBrief) -> list[str]:
    fact_summary = brief.fact_summary
    items: list[str] = []
    if fact_summary is not None:
        if fact_summary.financial_snapshot:
            metrics = "、".join(
                f"{item.label} {item.value}" for item in fact_summary.financial_snapshot[:3]
            )
            if len(fact_summary.financial_snapshot) > 3:
                metrics += f" ほか{len(fact_summary.financial_snapshot) - 3}指標"
            items.append(f"主要数値: {metrics}")
        if fact_summary.earnings_outlook:
            items.append(f"業績見通し: {fact_summary.earnings_outlook[0].value}")
        if fact_summary.shareholder_return_policy:
            items.append(f"配当・株主還元: {fact_summary.shareholder_return_policy[0].value}")
        if fact_summary.recent_events:
            event = fact_summary.recent_events[0]
            title = _research_brief_ui_text(event.source_title, max_chars=56)
            items.append(f"直近資料: {event.label}「{title}」")
    if not items:
        items.extend(brief.positive_candidates[:2])
    return _unique_text_items(items) or ["確認済みの事実はまだ少なめです。"]


def _research_brief_unconfirmed_items(brief: ResearchBrief) -> list[str]:
    fact_summary = brief.fact_summary
    items: list[str] = []
    if fact_summary is not None:
        items.extend(
            f"{item.label}: {item.reason}。{item.next_source_hint}で確認します。"
            for item in fact_summary.missing_items[:3]
        )
    if brief.missing_metrics:
        missing = "、".join(brief.missing_metrics[:5])
        if len(brief.missing_metrics) > 5:
            missing += f" ほか{len(brief.missing_metrics) - 5}件"
        items.append(f"主要数値: {missing} は公式資料で確認します。")
    if not items and brief.confirmation_gaps:
        items.append(_research_brief_gap_display_text(brief.confirmation_gaps[0]))
    return _unique_text_items(items) or [
        "大きな未確認項目はありません。出典カードで日付とURLを確認します。"
    ]


def _unique_text_items(items: Sequence[str]) -> list[str]:
    unique: list[str] = []
    for item in items:
        cleaned = _research_brief_ui_text(item, max_chars=180)
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique


def _research_brief_fact_confirmed_text(fact_summary: ResearchFactSummary) -> str:
    parts: list[str] = []
    if fact_summary.business_overview:
        parts.append(
            "事業概要: "
            + _research_brief_ui_text(fact_summary.business_overview[0].value, max_chars=72)
        )
    if fact_summary.financial_snapshot:
        metrics = "、".join(
            f"{item.label} {item.value}" for item in fact_summary.financial_snapshot[:3]
        )
        parts.append(f"主要数値: {metrics}")
    if fact_summary.earnings_outlook:
        parts.append(
            "業績見通し: "
            + _research_brief_ui_text(fact_summary.earnings_outlook[0].value, max_chars=72)
        )
    if fact_summary.shareholder_return_policy:
        parts.append(
            "配当・株主還元: "
            + _research_brief_ui_text(
                fact_summary.shareholder_return_policy[0].value,
                max_chars=72,
            )
        )
    if fact_summary.recent_events:
        event = fact_summary.recent_events[0]
        title = _research_brief_ui_text(event.source_title, max_chars=44)
        parts.append(f"直近資料: {event.label}「{title}」")
    if not parts:
        return "確認済みの根拠はまだ少なめです。まず資料登録やAI調査の更新を確認します。"
    return "。".join(parts) + "。売買推奨ではなく、判断材料の整理です。"


def _research_brief_fact_items_card_html(
    title: str,
    items: Sequence[ResearchFactItem],
    *,
    limit: int,
) -> str:
    visible_items = [item for item in items[:limit] if item.value.strip()]
    body = "".join(_research_brief_fact_item_html(item) for item in visible_items)
    if len(items) > limit:
        body += (
            '<div class="research-brief-focus-more">'
            f"ほか {len(items) - limit}件は詳細データで確認できます。</div>"
        )
    if not body:
        body = '<div class="research-brief-focus-body">現時点では確認できた項目がありません。</div>'
    return (
        '<section class="research-brief-focus-card">'
        f'<div class="research-brief-focus-title">{html.escape(title)}</div>'
        f'<div class="research-brief-focus-list">{body}</div>'
        "</section>"
    )


def _research_brief_fact_item_html(item: ResearchFactItem) -> str:
    source_rank = _research_source_rank_label(item.source_type)
    confidence = _research_source_confidence_short_label(item.source_confidence)
    confidence_tone = _research_source_confidence_tone(item.source_confidence)
    source_type = _research_source_type_label(item.source_type)
    published = item.published_at.isoformat() if item.published_at else "日付未設定"
    value = _research_brief_ui_text(item.value, max_chars=118)
    source_title = _research_brief_ui_text(item.source_title, max_chars=64)
    return (
        '<div class="research-brief-focus-material">'
        '<div class="research-brief-focus-badge-row">'
        f'<span class="research-evidence-pill">{html.escape(source_rank)}</span>'
        f'<span class="research-evidence-pill confidence-{html.escape(confidence_tone)}">'
        f"{html.escape(confidence)}</span>"
        "</div>"
        f'<div class="research-brief-focus-body"><strong>{html.escape(item.label)}:</strong> '
        f"{html.escape(value)}</div>"
        '<div class="research-brief-focus-meta">'
        f"主な出典: {html.escape(source_title)} / {html.escape(source_type)} / "
        f"{html.escape(published)}</div>"
        "</div>"
    )


def _research_brief_materials_card_html(
    title: str,
    materials: Sequence[ResearchBriefMaterial],
    *,
    fallback_items: Sequence[str],
    limit: int = 2,
) -> str:
    if not materials:
        return _research_brief_focus_card_html(title, fallback_items, limit=limit)

    visible_materials = [material for material in materials[:limit] if material.summary.strip()]
    body = "".join(_research_brief_material_item_html(material) for material in visible_materials)
    if len(materials) > limit:
        body += (
            '<div class="research-brief-focus-more">'
            f"ほか {len(materials) - limit}件は詳細データで確認できます。</div>"
        )
    if not body:
        body = '<div class="research-brief-focus-body">現時点では目立つ材料は未確認です。</div>'
    return (
        '<section class="research-brief-focus-card">'
        f'<div class="research-brief-focus-title">{html.escape(title)}</div>'
        f'<div class="research-brief-focus-list">{body}</div>'
        "</section>"
    )


def _research_brief_material_item_html(material: ResearchBriefMaterial) -> str:
    source_rank = _research_source_rank_label(material.source_type)
    confidence = _research_source_confidence_short_label(material.source_confidence)
    confidence_tone = _research_source_confidence_tone(material.source_confidence)
    source_type = _research_source_type_label(material.source_type)
    published = material.published_at.isoformat() if material.published_at else "日付未設定"
    source_title = _research_brief_ui_text(material.source_title, max_chars=72)
    summary = _research_brief_ui_text(material.summary, max_chars=138)
    return (
        '<div class="research-brief-focus-material">'
        '<div class="research-brief-focus-badge-row">'
        f'<span class="research-evidence-pill">{html.escape(source_rank)}</span>'
        f'<span class="research-evidence-pill confidence-{html.escape(confidence_tone)}">'
        f"{html.escape(confidence)}</span>"
        "</div>"
        f'<div class="research-brief-focus-body">{html.escape(summary)}</div>'
        '<div class="research-brief-focus-meta">'
        f"主な出典: {html.escape(source_title)} / {html.escape(source_type)} / "
        f"{html.escape(published)} / 根拠 {material.source_count}件"
        "</div>"
        "</div>"
    )


def _research_brief_focus_card_html(
    title: str,
    items: Sequence[str],
    *,
    limit: int = 1,
) -> str:
    visible_items = [
        _research_brief_ui_text(item, max_chars=130) for item in items[:limit] if item.strip()
    ]
    body = "".join(
        f'<div class="research-brief-focus-body">{html.escape(item)}</div>'
        for item in visible_items
    )
    if len(items) > limit:
        body += (
            '<div class="research-brief-focus-more">'
            f"ほか {len(items) - limit}件は詳細データで確認できます。</div>"
        )
    if not body:
        body = '<div class="research-brief-focus-body">現時点では目立つ材料は未確認です。</div>'
    return (
        '<section class="research-brief-focus-card">'
        f'<div class="research-brief-focus-title">{html.escape(title)}</div>'
        f'<div class="research-brief-focus-list">{body}</div>'
        "</section>"
    )


def _research_brief_ui_text(text: str, *, max_chars: int) -> str:
    cleaned = " ".join(text.split())
    if cleaned.lower() in {"nan", "none", "null", "raw"}:
        return ""
    cleaned = re.sub(r"\bCompany Name:\s*", "", cleaned, flags=re.IGNORECASE)
    for label in ("Provider Symbol", "Quote Type", "Exchange", "Currency"):
        cleaned = re.sub(rf"\b{label}:\s*\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\bSector:\s*[^:]+?(?=\s+(?:Industry|Business Summary|Summary):|$)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bIndustry:\s*[^:]+?(?=\s+(?:Business Summary|Summary):|$)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.strip().lower() in {"nan", "none", "null", "raw"}:
        return ""
    return truncate_text(cleaned.strip(), max_chars=max_chars)


def _research_brief_metric_rows(brief: ResearchBrief) -> list[dict[str, str]]:
    return [
        {
            "指標": metric.label,
            "値": metric.value,
            "出典": metric.source_title,
            "資料種別": _research_source_type_label(metric.source_type),
            "情報源信頼度": _research_source_confidence_label(metric.source_confidence),
        }
        for metric in brief.metrics
    ]


def _research_brief_metric_cards_html(brief: ResearchBrief) -> str:
    if not brief.metrics:
        return ""
    cards = []
    for metric in brief.metrics:
        source_type = _research_source_type_label(metric.source_type)
        confidence = _research_source_confidence_label(metric.source_confidence)
        confidence_tone = _research_source_confidence_tone(metric.source_confidence)
        cards.append(
            '<div class="research-brief-metric-card">'
            '<div class="research-evidence-card-header">'
            f'<span class="research-evidence-pill">{html.escape(source_type)}</span>'
            f'<span class="research-evidence-pill confidence-{html.escape(confidence_tone)}">'
            f"{html.escape(confidence)}</span>"
            "</div>"
            f'<div class="research-brief-metric-label">{html.escape(metric.label)}</div>'
            f'<div class="research-brief-metric-value">{html.escape(metric.value)}</div>'
            '<div class="research-brief-metric-source">'
            f"出典: {html.escape(metric.source_title)}</div>"
            "</div>"
        )
    return f'<div class="research-brief-metric-grid">{"".join(cards)}</div>'


def _research_brief_gap_rows(brief: ResearchBrief) -> list[dict[str, str]]:
    return [
        {
            "確認項目": "不足根拠",
            "内容": _research_brief_gap_display_text(gap),
            "確認ポイント": "未確認は低評価ではなく、追加確認が必要な状態として扱います。",
        }
        for gap in brief.confirmation_gaps
    ]


def _research_brief_gap_panel_html(brief: ResearchBrief) -> str:
    if not brief.missing_metrics and not brief.confirmation_gaps:
        return ""
    items = []
    has_metric_gap = any(
        gap.strip().startswith("未確認の定量指標") for gap in brief.confirmation_gaps
    )
    if brief.missing_metrics and not has_metric_gap:
        missing = " / ".join(brief.missing_metrics)
        items.append(f"未確認の定量指標: {missing}")
    items.extend(brief.confirmation_gaps)
    item_markup = "".join(
        '<div class="research-brief-gap-item">'
        f"{html.escape(_research_brief_gap_display_text(item))}</div>"
        for item in items
        if item.strip()
    )
    return (
        '<section class="research-brief-gap-panel">'
        '<div class="research-brief-gap-title">まだ判断に足りない情報</div>'
        f"{item_markup}"
        "</section>"
    )


def _research_brief_gap_display_text(gap: str) -> str:
    cleaned = " ".join(gap.split())
    if cleaned.startswith("未確認の定量指標:"):
        metrics = cleaned.split(":", 1)[1].strip()
        return (
            f"まだ確認できていない数値: {metrics}。"
            "悪材料ではなく、公式資料で追加確認する項目です。"
        )
    if cleaned.startswith("ニュース確認:"):
        warning = cleaned.split(":", 1)[1].strip()
        return f"ニュース根拠の確認: {warning}"
    if "登録済みResearch資料がありません" in cleaned:
        return (
            "保存済みのResearch資料がまだありません。必要なら公式IRや決算資料を登録してください。"
        )
    if "検索できたResearch根拠がありません" in cleaned:
        return (
            "関連する根拠資料をまだ見つけられていません。検索語や資料の登録状況を確認してください。"
        )
    if "信頼度が低" in cleaned:
        return "見つかった根拠の信頼度が低めです。出典元と公開日を確認してください。"
    return cleaned


def _research_brief_next_action_rows(brief: ResearchBrief) -> list[dict[str, str]]:
    return [
        {
            "次に確認する資料": action,
            "扱い": "確認材料",
        }
        for action in brief.next_actions
    ]


def _research_brief_next_actions_html(brief: ResearchBrief) -> str:
    if not brief.next_actions:
        return ""
    items = "".join(
        '<div class="research-brief-next-item">'
        f"{html.escape(_research_brief_ui_text(action, max_chars=120))}</div>"
        for action in brief.next_actions[:3]
    )
    if len(brief.next_actions) > 3:
        items += (
            '<div class="research-brief-focus-more">'
            f"ほか {len(brief.next_actions) - 3}件は詳細データで確認できます。</div>"
        )
    return f'<div class="research-brief-next-list">{items}</div>'


def _research_brief_source_card_rows(brief: ResearchBrief) -> list[dict[str, str]]:
    return [
        {
            "sentiment": "確認材料",
            "category": _research_source_type_label(card.source_type),
            "title": card.title,
            "summary": card.note or "出典、公開日、URL、情報源信頼度を確認する資料です。",
            "investment_impact": (
                "情報源の信頼度や鮮度を確認し、スコアや価格予測とは分けて読みます。"
            ),
            "source": card.provider or _research_source_type_label(card.source_type),
            "published_at": card.published_at.isoformat() if card.published_at else "未取得",
            "confidence": _research_source_confidence_label(card.source_confidence),
            "confidence_tone": _research_source_confidence_tone(card.source_confidence),
            "url": card.source_url or "",
            "detail": _research_brief_source_card_detail(card),
            "action_label": "出典を開く",
        }
        for card in brief.source_cards
    ]


def _research_brief_source_card_detail(card: ResearchBriefSourceCard) -> str:
    fetched_at = card.fetched_at
    freshness_status = card.freshness_status
    details = [
        f"取得日時: {fetched_at.isoformat()}" if fetched_at is not None else "",
        f"鮮度: {freshness_status}" if freshness_status and freshness_status != "unknown" else "",
    ]
    return " / ".join(detail for detail in details if detail)


def _research_brief_items_html(items: Sequence[str], *, tone: str) -> str:
    if not items:
        return ""
    badge_label = "良材料候補" if tone == "positive" else "注意材料候補"
    item_markup = "".join(
        (
            '<div class="research-point-item">'
            '<div class="research-evidence-card-header">'
            f'<span class="research-evidence-pill {html.escape(tone)}">'
            f"{html.escape(badge_label)}</span>"
            "</div>"
            f'<div class="research-point-summary">{html.escape(item)}</div>'
            "</div>"
        )
        for item in items
    )
    return f'<div class="research-point-list">{item_markup}</div>'


def _research_source_confidence_label(confidence: str) -> str:
    labels = {
        "high": "高: 公式資料・開示中心",
        "medium": "中: 外部データ / ニュース由来",
        "low": "低: user note / keyword 抽出",
        "unknown": "未確認",
    }
    return labels.get(confidence, "未確認")


def _research_source_confidence_short_label(confidence: str) -> str:
    labels = {
        "high": "公式資料で確認",
        "medium": "補助情報として確認",
        "low": "メモ由来",
        "unknown": "出典未確認",
    }
    return labels.get(confidence, "出典未確認")


def _research_source_confidence_tone(confidence: str) -> str:
    tones = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "unknown": "unknown",
    }
    return tones.get(confidence, "unknown")


def _research_brief_status_badges_html(brief: ResearchBrief) -> str:
    high_count = sum(1 for card in brief.source_cards if card.source_confidence == "high")
    medium_count = sum(1 for card in brief.source_cards if card.source_confidence == "medium")
    low_count = sum(1 for card in brief.source_cards if card.source_confidence == "low")
    unknown_count = sum(
        1 for card in brief.source_cards if card.source_confidence not in {"high", "medium", "low"}
    )
    badges = [
        ("AI整理済み", "info"),
        ("売買推奨ではありません", "neutral"),
    ]
    if high_count:
        badges.append((f"高信頼の出典 {high_count}件", "info"))
    if medium_count:
        badges.append((f"中信頼の出典 {medium_count}件", "warning"))
    if low_count:
        badges.append((f"低信頼の出典 {low_count}件", "low"))
    if unknown_count:
        badges.append((f"信頼度未確認 {unknown_count}件", "neutral"))
    if brief.missing_metrics:
        badges.append((f"追加確認 {len(brief.missing_metrics)}指標", "warning"))
    badge_markup = "".join(
        f'<span class="research-brief-badge {css_class}">{html.escape(label)}</span>'
        for label, css_class in badges
    )
    return f'<div class="research-brief-badge-row">{badge_markup}</div>'


def _research_result_overview_html(report: CompanyResearchReport) -> str:
    latest_source = (
        report.data_quality.latest_document_date.isoformat()
        if report.data_quality.latest_document_date
        else "未取得"
    )
    coverage = (
        f"資料 {report.data_quality.document_count}件 / 根拠 {report.data_quality.evidence_count}件"
    )
    if report.data_quality.document_count <= 0:
        next_check = "SettingsでResearch資料を登録してから再実行してください。"
    elif report.data_quality.evidence_count <= 0:
        next_check = "資料の対象銘柄・日付・キーワードを確認してください。"
    elif report.data_quality.warnings:
        next_check = "注意点と根拠カードで資料の鮮度・抜粋元を確認してください。"
    else:
        next_check = "根拠カードで資料名・日付・抜粋を確認してください。"

    items = [
        ("資料カバレッジ", coverage),
        ("最新資料日", latest_source),
        ("確認状態", report.data_quality.status),
        ("次に見るところ", next_check),
    ]
    item_markup = "".join(
        (
            '<div class="research-result-brief-item">'
            f'<div class="research-result-brief-label">{html.escape(label)}</div>'
            f'<div class="research-result-brief-value">{html.escape(value)}</div>'
            "</div>"
        )
        for label, value in items
    )
    return (
        '<section class="research-result-brief">'
        '<div class="research-result-brief-title">AI整理メモ</div>'
        f'<div class="research-result-brief-summary">{html.escape(report.summary)}</div>'
        f'<div class="research-result-brief-grid">{item_markup}</div>'
        "</section>"
    )


def _cockpit_research_report_from_state(preview: MarketDataPreview) -> CompanyResearchReport | None:
    report = st.session_state.get(MARKET_DATA_RESEARCH_REPORT_STATE_KEY)
    if not isinstance(report, CompanyResearchReport):
        return None
    if report.symbol != _market_data_preview_symbol(preview):
        return None
    return report


def _build_cockpit_research_report(preview: MarketDataPreview) -> CompanyResearchReport | None:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return None
    return analyze_research_for_symbol(
        symbol, as_of=_date_from_iso_text(_market_data_as_of(preview))
    )


def _render_stock_news_cards_panel(report: StockNewsReport) -> None:
    st.markdown("##### 関連ニュース")
    st.markdown(
        _research_evidence_cards_html(_stock_news_card_rows(report)[:5]), unsafe_allow_html=True
    )
    if len(report.news) > 5:
        with st.expander(f"追加ニュースを表示（{len(report.news) - 5}件）", expanded=False):
            st.markdown(
                _research_evidence_cards_html(_stock_news_card_rows(report)[5:]),
                unsafe_allow_html=True,
            )


def _cockpit_stock_news_report_from_state(preview: MarketDataPreview) -> StockNewsReport | None:
    report = st.session_state.get(MARKET_DATA_STOCK_NEWS_REPORT_STATE_KEY)
    if not isinstance(report, StockNewsReport):
        return None
    if report.symbol != _market_data_preview_symbol(preview):
        return None
    return report


def _build_cockpit_stock_news_report(preview: MarketDataPreview) -> StockNewsReport | None:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return None
    company_name = symbol_name(symbol) or None
    related_keywords = [company_name] if company_name else []
    return analyze_stock_news_for_symbol(
        symbol,
        company_name=company_name,
        related_keywords=related_keywords,
        as_of=_date_from_iso_text(_market_data_as_of(preview)),
    )


def _ranking_research_report_from_state(symbol: str) -> CompanyResearchReport | None:
    reports = st.session_state.get(MARKET_DATA_RANKING_RESEARCH_REPORTS_STATE_KEY)
    if not isinstance(reports, dict):
        return None
    report = reports.get(symbol.strip().upper())
    if not isinstance(report, CompanyResearchReport):
        return None
    return report


def _store_ranking_research_report(report: CompanyResearchReport) -> None:
    reports = st.session_state.get(MARKET_DATA_RANKING_RESEARCH_REPORTS_STATE_KEY)
    if not isinstance(reports, dict):
        reports = {}
        st.session_state[MARKET_DATA_RANKING_RESEARCH_REPORTS_STATE_KEY] = reports
    reports[report.symbol.strip().upper()] = report


def _render_market_data_cockpit_header(
    preview: MarketDataPreview,
    symbol_label: str,
) -> int:
    st.subheader("銘柄コックピット")
    metadata_col, horizon_col = st.columns([4.0, 1.0])
    provider_name = _metadata_value(preview.provider_rows, "provider") or "unknown"
    as_of = _market_data_as_of(preview)
    with horizon_col:
        forecast_horizon_days = cast(
            int,
            st.number_input(
                "Forecast days",
                min_value=1,
                max_value=30,
                step=1,
                key=MARKET_DATA_FORECAST_DAYS_STATE_KEY,
                help="取得済みデータを使ってチャートと指標だけを再計算します。",
            ),
        )
    reference_period = forecast_reference_period(preview.bars, horizon_days=forecast_horizon_days)
    with metadata_col:
        st.caption(
            f"対象: {symbol_label} / データ取得元: {provider_name} / "
            f"基準日: {as_of or '未取得'} / 参照期間: {reference_period}日"
        )
    return forecast_horizon_days


def _render_price_forecast_hero(
    preview: MarketDataPreview,
    symbol_label: str,
    forecast_rows: list[dict[str, str]],
    consensus_rows: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
) -> None:
    st.subheader("02 価格・予測")
    _render_target_symbol_caption(symbol_label)
    st.caption(
        "価格の流れと予測レンジを最初に確認します。予測は将来の保証ではなく、比較・確認のための参考情報です。"
    )
    for index, message in enumerate(forecast_chart_summary(consensus_rows, metric_rows)):
        if index == 0:
            st.info(message)
        else:
            st.caption(message)
    chart_currency = preview.bars[0].symbol.currency if preview.bars else ""
    _render_market_chart(
        forecast_rows,
        currency=chart_currency,
        title="価格・予測",
    )
    st.caption("縦の点線は、実績価格から予測表示へ切り替わる位置です。")


def _render_investment_score_section(
    preview: MarketDataPreview,
    symbol_label: str,
    *,
    rows: list[dict[str, str]] | None = None,
) -> dict[str, str] | None:
    _ = preview
    _ = symbol_label
    rows = (
        rows if rows is not None else investment_score_display_rows(preview.investment_score_rows)
    )
    if not rows:
        st.info(EMPTY_STATE_MESSAGES["investment_score_rows"])
        return None

    row = rows[0]
    render_cockpit_kpi_cards(cockpit_kpi_cards(row))
    return row


def _render_cockpit_direction_signal_section(
    score_row: dict[str, str],
    consensus_rows: list[dict[str, str]],
) -> None:
    consensus_row = consensus_rows[0] if consensus_rows else {}
    render_section_heading("03 シグナル読み取り")
    st.caption(
        "主要KPIの方向シグナルを、価格チャート後の読み取りとして整理します。売買推奨ではありません。"
    )
    insight_tone: Literal["caution", "forecast"] = (
        "caution"
        if (_decimal_from_text(score_row.get("下降警戒")) or Decimal("0")) >= Decimal("65")
        else "forecast"
    )
    st.markdown(
        smai_insight_html(
            cockpit_direction_signal_summary(score_row, consensus_row),
            tone=insight_tone,
        ),
        unsafe_allow_html=True,
    )
    detail_rows = cockpit_direction_signal_detail_rows(score_row, consensus_row)
    if detail_rows:
        _render_symbol_detail_table(detail_rows)


def _render_score_breakdown_context(
    preview: MarketDataPreview,
    symbol_label: str,
    row: dict[str, str],
    rows: list[dict[str, str]],
) -> None:
    st.markdown("#### 04 評価の内訳")
    st.caption(
        "チャートを見たあとに、総合スコアを構成する観点を確認します。売買判断ではなく、深掘りする理由を整理するための表示です。"
    )
    _render_score_breakdown_chart(score_component_rows(row))

    warning = row.get("注意点", "")
    summary_lines = investment_score_summary_lines(row)
    st.markdown(
        smai_insight_html(
            " ".join(summary_lines[:2]),
            tone="caution" if warning else "forecast",
        ),
        unsafe_allow_html=True,
    )
    for line in summary_lines[2:]:
        st.caption(line)
    period_rows = cockpit_period_evaluation_rows(preview.bars)
    if period_rows:
        st.subheader("期間別評価")
        st.caption(
            "取得した期間の長さに合わせて、値動きの確認観点を整理しています。売買判断ではなく、深掘り前の整理です。"
        )
        _render_symbol_detail_table(period_rows)
    memo_rows = cockpit_investment_memo_rows(preview, row)
    if memo_rows:
        st.subheader("投資判断メモ")
        st.caption(
            "銘柄データ、スコア、取得期間の値動きを合わせた深掘り観点です。売買推奨ではありません。"
        )
        _render_symbol_detail_table(memo_rows)

    with st.expander("投資スコアの詳細・ダウンロード"):
        st.caption(
            "投資スコアの表示値とダウンロードです。スコア計算ロジックは既存の結果をそのまま使っています。"
        )
        _render_target_symbol_caption(symbol_label)
        _render_table(rows, EMPTY_STATE_MESSAGES["investment_score_rows"])
        col_json, col_csv = st.columns(2)
        col_json.download_button(
            "投資スコアJSONをダウンロード",
            data=investment_score_json_download(preview.investment_score_rows),
            file_name="investment_score.json",
            mime="application/json",
        )
        col_csv.download_button(
            "投資スコアCSVをダウンロード",
            data=investment_score_csv_download(preview.investment_score_rows),
            file_name="investment_score.csv",
            mime="text/csv",
        )


def cockpit_detail_summary_rows(
    preview: MarketDataPreview,
    consensus_rows: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    quote_row = preview.quote_rows[0] if preview.quote_rows else {}
    ohlcv_row = preview.ohlcv_rows[0] if preview.ohlcv_rows else {}
    feature_row = preview.feature_rows[0] if preview.feature_rows else {}
    screening_row = preview.screening_rows[0] if preview.screening_rows else {}
    consensus_row = consensus_rows[0] if consensus_rows else {}

    if quote_row:
        rows.append(
            {
                "観点": "直近価格",
                "内容": (
                    f"{quote_row.get('last', '未取得')} / "
                    f"{quote_row.get('ts', '')[:10] or '日時未取得'}"
                ),
                "確認ポイント": "以降のチャート、予測、スコアはこの終値を基準にします。基準日が想定より古い場合は再取得します。",
            }
        )
    if ohlcv_row:
        rows.append(
            {
                "観点": "取得期間",
                "内容": (
                    f"{ohlcv_row.get('first_ts', '')[:10]}〜"
                    f"{ohlcv_row.get('last_ts', '')[:10]} / "
                    f"{ohlcv_row.get('bars', '0')}本 / 出来高合計 "
                    f"{ohlcv_row.get('total_volume', '未取得')}"
                ),
                "確認ポイント": _cockpit_ohlcv_check(ohlcv_row),
            }
        )
    if consensus_row:
        rows.append(
            {
                "観点": "予測レンジ",
                "内容": (
                    f"平均 {consensus_row.get('ensemble_forecast_close', '未計算')}、"
                    f"下限〜上限 {consensus_row.get('min_forecast_close', '未計算')}〜"
                    f"{consensus_row.get('max_forecast_close', '未計算')}、"
                    f"開き {consensus_row.get('forecast_range_pct', '未計算')}"
                ),
                "確認ポイント": _cockpit_forecast_range_check(
                    consensus_row.get("forecast_range_pct")
                ),
            }
        )
    if screening_row:
        rows.append(
            {
                "観点": "スクリーニング",
                "内容": (
                    f"総合 {screening_row.get('total_score', '未計算')}、"
                    f"モメンタム {screening_row.get('momentum_score', '未計算')}、"
                    f"流動性 {screening_row.get('liquidity_score', '未計算')}、"
                    f"リスク {screening_row.get('risk_score', '未計算')}"
                ),
                "確認ポイント": screening_row.get("summary", "")
                or _cockpit_screening_check(screening_row),
            }
        )
    if feature_row:
        rows.append(
            {
                "観点": "短期特徴量",
                "内容": (
                    f"1日 {feature_row.get('return_1d', '未計算')}、"
                    f"5日 {feature_row.get('momentum_5d', '未計算')}、"
                    f"20日下落 {feature_row.get('drawdown_20d', '未計算')}、"
                    f"完全性 {feature_row.get('data_completeness', '未計算')}"
                ),
                "確認ポイント": _cockpit_feature_check(feature_row),
            }
        )
        rows.append(
            {
                "観点": "データ品質",
                "内容": (
                    f"{feature_row.get('data_quality', '未判定')} / "
                    f"欠損: {feature_row.get('missing_summary', '未取得')}"
                ),
                "確認ポイント": _cockpit_data_quality_check(feature_row),
            }
        )
    metric_messages = forecast_metric_summary(metric_rows)
    if metric_messages:
        rows.append(
            {
                "観点": "予測評価",
                "内容": metric_messages[0],
                "確認ポイント": "RMSEは価格予測の誤差、方向一致率は上下方向の当たり方です。予測線を読む時の信頼度補助として見ます。",
            }
        )
    return rows


def _cockpit_ohlcv_check(row: Mapping[str, str]) -> str:
    bars = _optional_int_from_text(row.get("bars"))
    if bars is None:
        return "取得本数が未確認です。参照期間、provider、欠損の有無を確認します。"
    if bars < 20:
        return "取得本数が少なめです。短期の値動きに寄りやすいため、期間を広げて再確認します。"
    if bars < 60:
        return "短中期の確認には使えます。急変日や欠損が結果を動かしていないか確認します。"
    return "参照期間は比較的そろっています。直近だけでなく期間全体のトレンドも確認します。"


def _cockpit_forecast_range_check(value: object) -> str:
    range_pct = _decimal_from_text(value)
    value_text = _display_table_value(value)
    if range_pct is None:
        return "予測の開きは未計算です。モデル別予測線と評価サンプル数を確認します。"
    if range_pct >= Decimal("10"):
        return f"予測の開きは{value_text}で大きめです。平均予測だけでなく、上下限とモデル別の前提を確認します。"
    if range_pct >= Decimal("5"):
        return f"予測の開きは{value_text}でやや大きめです。強い方向材料として読みすぎないようにします。"
    return f"予測の開きは{value_text}で小さめです。モデル間の見方は比較的近い状態です。"


def _cockpit_screening_check(row: Mapping[str, str]) -> str:
    momentum = _decimal_from_text(row.get("momentum_score"))
    liquidity = _decimal_from_text(row.get("liquidity_score"))
    risk = _decimal_from_text(row.get("risk_score"))
    checks: list[str] = []
    if momentum is not None and momentum >= Decimal("70"):
        checks.append("モメンタムは強め")
    if liquidity is not None and liquidity >= Decimal("70"):
        checks.append("流動性は確認しやすい")
    if risk is not None and risk < Decimal("50"):
        checks.append("リスク確認は優先")
    if checks:
        return "、".join(checks) + "です。候補として残った理由と注意点を分けて確認します。"
    return "候補として残った理由を、モメンタム・流動性・リスク確認に分けて確認します。"


def _cockpit_feature_check(row: Mapping[str, str]) -> str:
    momentum_5d = _decimal_from_text(row.get("momentum_5d"))
    drawdown_20d = _decimal_from_text(row.get("drawdown_20d"))
    if momentum_5d is not None and momentum_5d >= Decimal("5"):
        return (
            "5日モメンタムが強めです。短期反発か、継続トレンドかを20日下落幅と合わせて確認します。"
        )
    if drawdown_20d is not None and drawdown_20d <= Decimal("-10"):
        return "20日下落幅が大きめです。反発候補か下落継続かを価格チャートで確認します。"
    return "1日・5日リターンと20日下落幅を並べて、予測方向が直近の値動きだけに寄っていないか確認します。"


def _cockpit_data_quality_check(row: Mapping[str, str]) -> str:
    quality = str(row.get("data_quality", "")).strip().upper()
    completeness = _decimal_from_text(row.get("data_completeness"))
    missing = str(row.get("missing_summary", "")).strip()
    if quality == "OK" and (completeness is None or completeness >= Decimal("95")):
        return "欠損は少なめです。スコア解釈では、次に予測評価と直近トレンドを確認します。"
    if missing and missing not in {"なし", "-", "0"}:
        return "欠損があります。欠けている項目が予測、リスク確認、データ信頼度に影響していないか確認します。"
    return "品質警告がある場合は、詳細を展開して根拠データとproviderを確認します。"


def _optional_int_from_text(value: object) -> int | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _display_table_value(value: object) -> str:
    text = str(value or "").strip()
    return text or "未計算"


def cockpit_period_evaluation_rows(bars: list[Bar]) -> list[dict[str, str]]:
    closes = [bar.close for bar in bars if bar.close > 0]
    if len(closes) < 2 or not bars:
        return [
            {
                "評価軸": "期間評価",
                "見方": "終値データが不足しています。",
                "確認ポイント": "期間を広げるか、別providerで再取得してから評価します。",
            }
        ]

    sorted_bars = sorted(bars, key=lambda row: row.ts)
    first = sorted_bars[0]
    last = sorted_bars[-1]
    period_days = max((last.ts.date() - first.ts.date()).days, 1)
    first_close = closes[0]
    latest_close = closes[-1]
    change_pct = ((latest_close - first_close) / first_close * Decimal("100")).quantize(
        Decimal("0.1")
    )
    high = max(closes)
    low = min(closes)
    range_position_pct = _range_position_pct(latest_close, low, high)
    max_drawdown_pct = _max_drawdown_pct(closes)
    one_day_moves = [
        abs((closes[index] - closes[index - 1]) / closes[index - 1] * Decimal("100"))
        for index in range(1, len(closes))
        if closes[index - 1] > 0
    ]
    avg_abs_move_pct = (
        (sum(one_day_moves, Decimal("0")) / Decimal(len(one_day_moves))).quantize(Decimal("0.1"))
        if one_day_moves
        else Decimal("0")
    )
    horizon_label, horizon_check = _cockpit_period_horizon(period_days)
    position_label = _range_position_label(range_position_pct)
    momentum_label = _period_momentum_label(change_pct)
    drawdown_label = _drawdown_label(max_drawdown_pct)
    volatility_label = _volatility_label(avg_abs_move_pct)

    return [
        {
            "評価軸": "取得期間",
            "見方": f"{period_days}日間 / {horizon_label}",
            "確認ポイント": horizon_check,
        },
        {
            "評価軸": "期間リターン",
            "見方": f"{change_pct:+}% / {momentum_label}",
            "確認ポイント": "上昇率だけでなく、直近が高値圏か下落後の反発かを分けて見ます。",
        },
        {
            "評価軸": "終値の位置",
            "見方": f"期間レンジ内 {range_position_pct}% / {position_label}",
            "確認ポイント": "高値圏では追随リスク、安値圏では反転材料と下落継続リスクを確認します。",
        },
        {
            "評価軸": "下落耐性",
            "見方": f"最大下落 {max_drawdown_pct}% / {drawdown_label}",
            "確認ポイント": "想定保有期間で許容できる下落幅かを確認します。",
        },
        {
            "評価軸": "値動きの荒さ",
            "見方": f"平均日次変動 {avg_abs_move_pct}% / {volatility_label}",
            "確認ポイント": "短期で振れやすい銘柄は、ポジションサイズと確認頻度を控えめにします。",
        },
    ]


def _range_position_pct(latest_close: Decimal, low: Decimal, high: Decimal) -> Decimal:
    if high == low:
        return Decimal("50.0")
    return ((latest_close - low) / (high - low) * Decimal("100")).quantize(Decimal("0.1"))


def _max_drawdown_pct(closes: list[Decimal]) -> Decimal:
    peak = closes[0]
    max_drawdown = Decimal("0")
    for close in closes:
        peak = max(peak, close)
        if peak > 0:
            drawdown = (close - peak) / peak * Decimal("100")
            max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown.quantize(Decimal("0.1"))


def _cockpit_period_horizon(period_days: int) -> tuple[str, str]:
    if period_days <= 31:
        return (
            "短期反応の確認",
            "決算、ニュース、需給の反応を見ます。ノイズが大きいため単独判断に使いません。",
        )
    if period_days <= 183:
        return (
            "中期トレンドの確認",
            "材料が一過性か、数か月のトレンドとして続いているかを確認します。",
        )
    if period_days <= 730:
        return (
            "年次トレンドの確認",
            "業績期待、相場循環、下落耐性をまとめて確認する基準期間です。",
        )
    return (
        "長期耐性の確認",
        "複数決算期をまたいだ成長持続性、最大下落、回復力を確認します。",
    )


def _period_momentum_label(change_pct: Decimal) -> str:
    if change_pct >= Decimal("20"):
        return "強い上昇"
    if change_pct >= Decimal("5"):
        return "上昇優位"
    if change_pct <= Decimal("-20"):
        return "大きく下落"
    if change_pct <= Decimal("-5"):
        return "下落優位"
    return "横ばい"


def _range_position_label(range_position_pct: Decimal) -> str:
    if range_position_pct >= Decimal("80"):
        return "高値圏"
    if range_position_pct <= Decimal("20"):
        return "安値圏"
    return "中間圏"


def _drawdown_label(max_drawdown_pct: Decimal) -> str:
    if max_drawdown_pct <= Decimal("-30"):
        return "下落耐性は要確認"
    if max_drawdown_pct <= Decimal("-15"):
        return "下落幅はやや大きい"
    return "下落幅は限定的"


def _volatility_label(avg_abs_move_pct: Decimal) -> str:
    if avg_abs_move_pct >= Decimal("4"):
        return "値動きは大きめ"
    if avg_abs_move_pct >= Decimal("2"):
        return "値動きは中程度"
    return "値動きは比較的落ち着いています"


def investment_score_summary_lines(row: dict[str, str]) -> list[str]:
    lines = [
        f"{row.get('銘柄', 'この銘柄')} は「{row.get('見方', '要確認')}」として確認できます。",
    ]
    warning = row.get("注意点", "")
    if warning:
        lines.append(f"注意点: {warning}。")
    else:
        lines.append("大きな注意点はありません。")
    note = row.get("補足", "")
    if note:
        lines.append(note)
    return lines[:3]


def score_component_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"要素": "スクリーニング", "スコア": row.get("Screening", "")},
        {"要素": "上昇気配", "スコア": row.get("上昇気配", "")},
        {"要素": "下降警戒", "スコア": row.get("下降警戒", "")},
        {"要素": "リスク確認", "スコア": row.get("Risk", "")},
        {"要素": "データ品質", "スコア": row.get("データ品質", "")},
    ]


def _render_compact_dataframe(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    st.dataframe(
        pd.DataFrame(user_facing_table_rows(rows)),
        use_container_width=True,
        hide_index=True,
    )


def _research_investment_point_rows(report: CompanyResearchReport) -> list[dict[str, str]]:
    return [
        {
            "観点": point.label,
            "分類": _research_topic_category_label(point.category),
            "要点": point.summary,
            "根拠数": str(len(point.evidence)),
            "sentiment": _research_sentiment_for_category(point.category),
        }
        for point in report.points
    ]


_RESEARCH_SCORE_UI_COMPONENTS = (
    ("成長材料", "growth_score", "成長戦略や事業拡大の根拠を確認します。"),
    ("収益性", "profitability_score", "利益率、営業利益、ROEなどの根拠を確認します。"),
    ("株主還元", "shareholder_return_score", "配当方針や自社株買いの根拠を確認します。"),
    ("財務安全性", "financial_safety_score", "自己資本、現金、流動性の根拠を確認します。"),
    ("事業リスク確認", "business_risk_score", "リスク記述が確認できるかを見ます。"),
    ("根拠の充実度", "disclosure_quality_score", "資料数、根拠数、資料種別、信頼度を見ます。"),
    ("情報の鮮度", "freshness_score", "公開日が古すぎないかを見ます。"),
)


def _research_score_summary_rows(score: ResearchScore) -> list[dict[str, str]]:
    return [
        {
            "確認項目": "Research Score",
            "内容": str(score.total_score),
            "確認ポイント": "根拠資料の充実度・鮮度・信頼度を整理する参考スコアです。売買推奨ではありません。",
        },
        {
            "確認項目": "信頼度",
            "内容": str(score.confidence),
            "確認ポイント": "資料数、根拠数、資料の信頼度を踏まえて控えめに読みます。",
        },
        {
            "確認項目": "根拠数",
            "内容": f"{score.evidence_count}件",
            "確認ポイント": _research_score_next_check(score),
        },
    ]


def _research_score_component_rows(score: ResearchScore) -> list[dict[str, str]]:
    return [
        {
            "観点": label,
            "スコア": str(getattr(score, field_name)),
            "確認ポイント": review_point,
        }
        for label, field_name, review_point in _RESEARCH_SCORE_UI_COMPONENTS
    ]


def _research_score_warning_rows(score: ResearchScore) -> list[dict[str, str]]:
    return [
        {
            "確認項目": "Research Score",
            "注意点": warning,
        }
        for warning in score.warnings
    ]


def _research_score_next_check(score: ResearchScore) -> str:
    if score.evidence_count <= 0:
        return "資料が不足しています。対象銘柄のIR資料やニュース資料を追加確認します。"
    if score.warnings:
        return "注意点と内訳を見て、根拠が薄い観点を追加確認します。"
    return "内訳と根拠カードを見て、どの観点の資料が支えているか確認します。"


def _research_point_cards_html(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    items = []
    for row in rows:
        sentiment = row.get("sentiment", "中立材料")
        tone = _research_sentiment_css_class(sentiment)
        label = row.get("観点", "")
        category = row.get("分類", "")
        count = row.get("根拠数", "0")
        summary = row.get("要点", "")
        items.append(
            '<div class="research-point-item">'
            '<div class="research-evidence-card-header">'
            f'<span class="research-evidence-pill {tone}">{html.escape(sentiment)}</span>'
            f'<span class="research-evidence-pill">{html.escape(category)}</span>'
            f'<span class="research-evidence-pill">根拠 {html.escape(count)}件</span>'
            "</div>"
            f'<div class="research-point-label">{html.escape(label)}</div>'
            f'<div class="research-point-summary">{html.escape(summary)}</div>'
            "</div>"
        )
    return f'<div class="research-point-list">{"".join(items)}</div>'


def _research_evidence_card_rows(
    report: CompanyResearchReport | None,
    *,
    news_report: StockNewsReport | None = None,
    limit: int | None = 5,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if news_report is not None:
        rows.extend(_stock_news_card_rows(news_report))
    if report is not None:
        category_by_key = _research_category_by_evidence_key(report)
        for evidence in report.evidence:
            category = category_by_key.get(
                (evidence.document_id, evidence.chunk_id),
                "other",
            )
            sentiment = _research_sentiment_for_category(category)
            rows.append(
                {
                    "sentiment": sentiment,
                    "category": _research_topic_category_label(category),
                    "title": evidence.title,
                    "summary": truncate_text(evidence.excerpt, max_chars=150),
                    "investment_impact": _research_investment_impact(category),
                    "source": _research_source_type_label(evidence.source_type),
                    "published_at": (
                        evidence.published_at.isoformat() if evidence.published_at else "未取得"
                    ),
                    "confidence": str(evidence.reliability),
                    "url": "",
                    "detail": evidence.section_title or "",
                }
            )
    return rows if limit is None else rows[:limit]


def _stock_news_card_rows(report: StockNewsReport) -> list[dict[str, str]]:
    return [
        {
            "sentiment": _stock_news_sentiment_label(row.sentiment_for_investment),
            "category": _stock_news_viewpoint_label(row.investment_viewpoint),
            "title": row.title,
            "summary": truncate_text(row.summary, max_chars=150),
            "investment_impact": _stock_news_investment_impact(row.sentiment_for_investment),
            "source": row.source or "ニュース",
            "published_at": row.published_at.isoformat() if row.published_at else "未取得",
            "confidence": row.freshness_status,
            "url": row.url,
            "detail": row.investment_viewpoint,
        }
        for row in report.news
    ]


def _research_evidence_detail_rows(report: CompanyResearchReport) -> list[dict[str, str]]:
    return [
        {
            "sentiment": row.get("sentiment", ""),
            "category": row.get("category", ""),
            "title": row.get("title", ""),
            "source": row.get("source", ""),
            "published_at": row.get("published_at", ""),
            "confidence": row.get("confidence", ""),
        }
        for row in _research_evidence_card_rows(report, limit=None)
    ]


def _stock_news_detail_rows(report: StockNewsReport) -> list[dict[str, str]]:
    return [
        {
            "sentiment": row.get("sentiment", ""),
            "category": row.get("category", ""),
            "title": row.get("title", ""),
            "source": row.get("source", ""),
            "published_at": row.get("published_at", ""),
            "confidence": row.get("confidence", ""),
        }
        for row in _stock_news_card_rows(report)
    ]


def _research_category_by_evidence_key(
    report: CompanyResearchReport,
) -> dict[tuple[str, str], str]:
    categories: dict[tuple[str, str], str] = {}
    for point in report.points:
        for evidence in point.evidence:
            categories.setdefault((evidence.document_id, evidence.chunk_id), point.category)
    for claim in report.extracted_claims:
        for evidence in claim.supporting_evidence:
            categories.setdefault((evidence.document_id, evidence.chunk_id), claim.category)
    return categories


def _research_topic_category_label(category: str) -> str:
    labels = {
        "growth": "事業成長",
        "shareholder_return": "株主還元",
        "financial_safety": "業績・財務",
        "business_risk": "リスク材料",
        "confirmation_gap": "確認不足",
        "other": "その他",
    }
    return labels.get(category, "その他")


def _research_sentiment_for_category(category: str) -> str:
    if category in {"growth", "shareholder_return", "financial_safety"}:
        return "ポジティブ材料"
    if category in {"business_risk", "confirmation_gap"}:
        return "リスク材料"
    return "中立材料"


def _research_investment_impact(category: str) -> str:
    impacts = {
        "growth": "成長余地を確認する材料です。短期判断では価格トレンドと合わせて見ます。",
        "shareholder_return": "株主還元やインカム面の確認材料です。継続性も合わせて見ます。",
        "financial_safety": "財務・収益基盤の安定性を確認する材料です。",
        "business_risk": "外部環境や事業リスクを先に確認する材料です。",
        "confirmation_gap": "根拠不足の領域です。追加資料を確認してから判断材料にします。",
    }
    return impacts.get(category, "補足情報として、他のスコアや価格トレンドと合わせて確認します。")


def _research_source_type_label(source_type: str) -> str:
    labels = {
        "annual_report": "有価証券報告書",
        "earnings_report": "決算短信",
        "earnings_presentation": "決算説明資料",
        "medium_term_plan": "中期経営計画",
        "integrated_report": "統合報告書",
        "tdnet": "TDnet",
        "news": "ニュース",
        "provider_profile": "取得元プロフィール",
        "user_note": "ユーザーメモ",
    }
    return labels.get(source_type, source_type or "未確認")


def _research_source_rank_label(source_type: str) -> str:
    if source_type in {
        "annual_report",
        "earnings_report",
        "earnings_presentation",
        "medium_term_plan",
        "integrated_report",
        "tdnet",
    }:
        return "公式資料"
    if source_type == "provider_profile":
        return "外部データ"
    if source_type == "news":
        return "ニュース"
    if source_type == "user_note":
        return "ユーザーメモ"
    return "確認資料"


def _research_freshness_status_label(status: str) -> str:
    labels = {
        "latest": "最新",
        "recent": "最近",
        "stale": "古め",
        "unknown": "未確認",
    }
    return labels.get(status, "未確認")


def _stock_news_sentiment_label(sentiment: str) -> str:
    labels = {
        "positive": "ポジティブ材料",
        "negative": "リスク材料",
        "mixed": "中立材料",
        "neutral": "中立材料",
        "unknown": "中立材料",
    }
    return labels.get(sentiment, "中立材料")


def _stock_news_viewpoint_label(viewpoint: str) -> str:
    labels = {
        "earnings": "業績",
        "growth": "事業成長",
        "shareholder_return": "株主還元",
        "risk": "リスク材料",
        "macro": "マクロ環境",
        "other": "株価材料",
    }
    return labels.get(viewpoint, "その他")


def _stock_news_investment_impact(sentiment: str) -> str:
    if sentiment == "positive":
        return "評価を支える材料として確認します。価格に織り込まれているかも見ます。"
    if sentiment == "negative":
        return "短期の注意材料として確認します。業績や需要への影響を見ます。"
    if sentiment == "mixed":
        return "ポジティブ材料とリスク材料が混在しています。中身を分けて確認します。"
    return "補足ニュースとして、価格トレンドやスコアと合わせて確認します。"


def _research_sentiment_css_class(sentiment: str) -> str:
    if sentiment in {"Positive", "ポジティブ材料"}:
        return "positive"
    if sentiment in {"Risk", "リスク材料"}:
        return "risk"
    return "neutral"


def _research_evidence_display_rows(report: CompanyResearchReport) -> list[dict[str, str]]:
    return [
        {
            "資料名": evidence.title,
            "資料種別": _research_source_type_label(evidence.source_type),
            "公開日": evidence.published_at.isoformat() if evidence.published_at else "",
            "セクション": evidence.section_title or "",
            "抜粋": evidence.excerpt,
            "関連度": str(evidence.relevance_score),
            "信頼度": str(evidence.reliability),
        }
        for evidence in report.evidence[:10]
    ]


def _research_quality_warning_rows(report: CompanyResearchReport) -> list[dict[str, str]]:
    return [
        {
            "確認項目": "資料の状態",
            "状態": report.data_quality.status,
            "注意点": warning,
        }
        for warning in report.data_quality.warnings
        if warning.strip()
    ]


def _research_grounded_answer_rows(report: CompanyResearchReport) -> list[dict[str, str]]:
    answer = report.grounded_answer
    if answer is None:
        return []
    return [
        {
            "確認項目": "根拠付き要約",
            "AI整理メモ": answer.answer,
            "根拠数": str(answer.evidence_count),
            "次の確認": " / ".join(answer.warnings),
        }
    ]


def _research_retrieval_quality_rows(report: CompanyResearchReport) -> list[dict[str, str]]:
    quality = report.retrieval_quality
    if quality is None:
        return []
    return [
        {
            "確認項目": "検索品質",
            "検索方式": quality.backend,
            "検索した観点": quality.query,
            "関連語の一部": _research_terms_preview(quality.expanded_terms),
            "候補数": str(quality.candidate_count),
            "根拠数": str(quality.evidence_count),
            "注意点": " / ".join(quality.warnings),
        }
    ]


def _research_terms_preview(terms: Sequence[str], *, limit: int = 12) -> str:
    cleaned = [term.strip() for term in terms if term.strip()]
    if len(cleaned) <= limit:
        return " / ".join(cleaned)
    shown = " / ".join(cleaned[:limit])
    return f"{shown} / ... (+{len(cleaned) - limit})"


def _research_extracted_claim_rows(report: CompanyResearchReport) -> list[dict[str, str]]:
    return [
        {
            "観点": claim.category,
            "抽出内容": claim.claim,
            "要約": claim.summary,
            "信頼度": str(claim.confidence),
            "根拠数": str(len(claim.supporting_evidence)),
            "不足情報": " / ".join(claim.missing_information),
        }
        for claim in report.extracted_claims
    ]


def _research_document_display_rows(report: CompanyResearchReport) -> list[dict[str, str]]:
    document_rows: dict[tuple[str, str, str], dict[str, str]] = {}
    for evidence in report.evidence:
        published_at = evidence.published_at.isoformat() if evidence.published_at else "未取得"
        key = (evidence.title, evidence.source_type, published_at)
        row = document_rows.setdefault(
            key,
            {
                "根拠資料名": evidence.title,
                "資料種別": _research_source_type_label(evidence.source_type),
                "資料日": published_at,
                "根拠数": "0",
            },
        )
        row["根拠数"] = str(int(row["根拠数"]) + 1)
    return list(document_rows.values())


def _stock_news_display_rows(report: StockNewsReport) -> list[dict[str, str]]:
    return [
        {
            "タイトル": row.title,
            "URL": row.url,
            "出典": row.source or "未確認",
            "公開日": row.published_at.isoformat() if row.published_at else "未確認",
            "要約": row.summary,
            "確認観点": _stock_news_viewpoint_label(row.investment_viewpoint),
            "材料分類": _stock_news_sentiment_label(row.sentiment_for_investment),
            "鮮度": row.freshness_status,
        }
        for row in report.news
    ]


def _research_table_html(rows: list[dict[str, str]], *, class_name: str) -> str:
    if not rows:
        return ""
    columns = list(rows[0].keys())
    header_cells = "".join(
        f'<th class="{_research_column_class(column)}">{html.escape(column)}</th>'
        for column in columns
    )
    body_rows = []
    for row in rows:
        cells = "".join(
            (
                f'<td class="{_research_column_class(column)}">'
                f"{html.escape(str(row.get(column, '')))}</td>"
            )
            for column in columns
        )
        body_rows.append(f"<tr>{cells}</tr>")
    classes = f"symbol-detail-table {html.escape(class_name)}"
    return (
        f'<table class="{classes}">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def _research_evidence_cards_html(evidence_rows: list[dict[str, str]]) -> str:
    if not evidence_rows:
        return ""
    items = []
    for row in evidence_rows:
        sentiment = row.get("sentiment") or row.get("Sentiment") or "中立材料"
        category = row.get("category") or row.get("資料種別") or "その他"
        title = row.get("title") or row.get("資料名") or "根拠資料"
        summary = row.get("summary") or row.get("要約") or row.get("抜粋") or ""
        impact = (
            row.get("investment_impact")
            or row.get("投資判断への影響")
            or "スコアや価格予測と合わせて確認する補足材料です。"
        )
        source = row.get("source") or row.get("資料種別") or "未確認"
        published_at = row.get("published_at") or row.get("公開日") or "未取得"
        confidence = row.get("confidence") or row.get("信頼度") or ""
        confidence_tone = row.get("confidence_tone", "").strip()
        if confidence_tone not in {"high", "medium", "low", "unknown"}:
            confidence_tone = ""
        detail = row.get("detail") or row.get("セクション") or ""
        url = row.get("url", "").strip()
        meta_parts = [
            f"出典: {source}",
            f"公開日: {published_at}",
            f"信頼度: {confidence}" if confidence else "",
            detail,
        ]
        meta = " / ".join(html.escape(part) for part in meta_parts if part)
        action_parts = []
        if url:
            action_label = row.get("action_label") or "記事を開く"
            action_parts.append(
                f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">'
                f"{html.escape(action_label)}</a>"
            )
        action_parts.append('<span class="research-evidence-action-muted">詳細を見る</span>')
        actions = "".join(action_parts)
        tone = _research_sentiment_css_class(sentiment)
        confidence_pill = (
            f'<span class="research-evidence-pill confidence-{html.escape(confidence_tone)}">'
            f"{html.escape(confidence)}</span>"
            if confidence and confidence_tone
            else ""
        )
        items.append(
            '<div class="research-evidence-item">'
            '<div class="research-evidence-card-header">'
            f'<span class="research-evidence-pill {tone}">{html.escape(sentiment)}</span>'
            f'<span class="research-evidence-pill">{html.escape(category)}</span>'
            f"{confidence_pill}"
            "</div>"
            f'<div class="research-evidence-title">{html.escape(title)}</div>'
            '<div class="research-evidence-body">'
            '<span class="research-evidence-label">要約: </span>'
            f"{html.escape(summary)}</div>"
            '<div class="research-evidence-body">'
            '<span class="research-evidence-label">投資判断への影響: </span>'
            f"{html.escape(impact)}</div>"
            f'<div class="research-evidence-meta">{meta}</div>'
            f'<div class="research-evidence-actions">{actions}</div>'
            "</div>"
        )
    return f'<div class="research-evidence-list">{"".join(items)}</div>'


def _research_column_class(column: str) -> str:
    if column in {"観点", "確認項目"}:
        return "research-topic"
    if column == "根拠数":
        return "research-count"
    return ""


def _widget_key_fragment(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")


def _research_evidence_report_section(report: CompanyResearchReport) -> DecisionReportSection:
    return build_research_evidence_section(
        symbol=report.symbol,
        as_of=report.as_of,
        summary=report.summary,
        points=[
            {
                "category": point.category,
                "label": point.label,
                "summary": point.summary,
                "evidence_count": str(len(point.evidence)),
            }
            for point in report.points
        ],
        evidence_rows=[
            *[
                {
                    "row_type": "grounded_answer",
                    "provider": answer.provider,
                    "answer": answer.answer,
                    "claim_count": str(answer.claim_count),
                    "evidence_count": str(answer.evidence_count),
                    "warnings": " / ".join(answer.warnings),
                }
                for answer in [report.grounded_answer]
                if answer is not None
            ],
            *[
                {
                    "row_type": "retrieval_quality",
                    "backend": quality.backend,
                    "query": quality.query,
                    "expanded_terms": " / ".join(quality.expanded_terms),
                    "candidate_count": str(quality.candidate_count),
                    "evidence_count": str(quality.evidence_count),
                    "warnings": " / ".join(quality.warnings),
                }
                for quality in [report.retrieval_quality]
                if quality is not None
            ],
            *[
                {
                    "row_type": "extracted_claim",
                    "category": claim.category,
                    "claim": claim.claim,
                    "summary": claim.summary,
                    "confidence": str(claim.confidence),
                    "evidence_count": str(len(claim.supporting_evidence)),
                    "missing_information": " / ".join(claim.missing_information),
                }
                for claim in report.extracted_claims
            ],
            *[
                {
                    "title": evidence.title,
                    "source_type": evidence.source_type,
                    "published_at": (
                        evidence.published_at.isoformat() if evidence.published_at else ""
                    ),
                    "section_title": evidence.section_title or "",
                    "excerpt": evidence.excerpt,
                    "relevance_score": str(evidence.relevance_score),
                    "reliability": str(evidence.reliability),
                }
                for evidence in report.evidence[:20]
            ],
        ],
        data_quality={
            "status": report.data_quality.status,
            "document_count": str(report.data_quality.document_count),
            "latest_document_date": (
                report.data_quality.latest_document_date.isoformat()
                if report.data_quality.latest_document_date
                else ""
            ),
            "evidence_count": str(report.data_quality.evidence_count),
            "warnings": " / ".join(report.data_quality.warnings),
            "grounded_answer": report.grounded_answer.answer if report.grounded_answer else "",
            "retrieval_backend": (
                report.retrieval_quality.backend if report.retrieval_quality else ""
            ),
        },
    )


def _research_score_report_section(report: CompanyResearchReport) -> DecisionReportSection:
    score = ResearchScoreService().score_report(report)
    return build_research_score_section(
        symbol=score.symbol,
        as_of=score.as_of,
        total_score=str(score.total_score),
        confidence=str(score.confidence),
        evidence_count=str(score.evidence_count),
        summary=score.summary,
        component_scores={
            "growth_score": str(score.growth_score),
            "profitability_score": str(score.profitability_score),
            "shareholder_return_score": str(score.shareholder_return_score),
            "financial_safety_score": str(score.financial_safety_score),
            "business_risk_score": str(score.business_risk_score),
            "disclosure_quality_score": str(score.disclosure_quality_score),
            "freshness_score": str(score.freshness_score),
        },
        supporting_evidence_rows=_research_score_evidence_rows(score),
        warnings=score.warnings,
        notes=[score.decision_support_note],
    )


def _research_score_evidence_rows(score: ResearchScore) -> list[dict[str, str]]:
    return [
        {
            "title": evidence.title,
            "source_type": evidence.source_type,
            "published_at": evidence.published_at.isoformat() if evidence.published_at else "",
            "section_title": evidence.section_title or "",
            "excerpt": evidence.excerpt,
            "relevance_score": str(evidence.relevance_score),
            "reliability": str(evidence.reliability),
        }
        for evidence in score.supporting_evidence[:20]
    ]


def _external_research_trace_report_section(
    result: ExternalResearchFetchResult,
) -> DecisionReportSection:
    return build_external_research_trace_section(
        symbol=result.symbol,
        provider=result.provider,
        fetched_at=result.fetched_at,
        retention_policy=result.retention_policy,
        entries=[
            {
                "title": entry.title,
                "source_type": entry.source_type,
                "source_url": entry.source_url,
                "provider": entry.provider,
                "published_at": entry.published_at.isoformat() if entry.published_at else "",
                "fetched_at": _datetime_display_text(entry.fetched_at),
                "freshness_status": entry.freshness_status,
                "content_summary": _external_research_entry_summary_display_text(entry),
            }
            for entry in result.entries[:20]
        ],
        warnings=result.warnings,
    )


def build_cockpit_decision_report_context(
    preview: MarketDataPreview,
) -> DecisionReportContext:
    symbol = _market_data_preview_symbol(preview)
    symbol_row = _symbol_universe_row_for_symbol(symbol) if symbol else None
    provider = _metadata_value(preview.provider_rows, "provider") or None
    as_of = _date_from_iso_text(_market_data_as_of(preview))
    score_row = preview.investment_score_rows[0] if preview.investment_score_rows else {}
    sections = [
        build_data_confidence_section(
            provider=provider,
            symbol=symbol or None,
            as_of=as_of,
            price_period=_bars_period_label(preview.bars),
            data_quality=score_row.get("data_quality_score") or score_row.get("data_quality"),
            metadata_source=_symbol_report_value(symbol_row, "metadata_source"),
            metadata_as_of=_symbol_report_value(symbol_row, "metadata_as_of"),
            missing_fields=_missing_symbol_report_fields(symbol_row),
            coverage_rows=_symbol_report_coverage_rows(symbol_row),
            warnings=[row.get("message", "") for row in preview.error_rows],
        )
    ]
    if symbol_row is not None:
        sections.append(
            build_symbol_metadata_section(
                symbol=symbol,
                name=symbol_name(symbol),
                metadata=_symbol_report_metadata(symbol_row),
            )
        )
    if score_row:
        sections.append(
            _investment_score_report_section(
                score_row,
                source_kind="cockpit",
                provider=provider,
                symbol=symbol,
                as_of=as_of,
            )
        )
    if symbol_row is not None:
        sections.append(
            _valuation_income_risk_report_section(
                symbol_row,
                source_kind="cockpit",
                symbol=symbol,
                as_of=as_of,
            )
        )
    display_score_rows = investment_score_display_rows(preview.investment_score_rows)
    if display_score_rows:
        sections.append(
            build_decision_checkpoints_section(
                checkpoints=_cockpit_report_checkpoints(
                    display_score_rows[0],
                    symbol_row,
                    preview.bars,
                ),
                symbol=symbol or None,
                as_of=as_of,
            )
        )
    research_report = _cockpit_research_report_from_state(preview)
    if research_report is not None and (
        research_report.data_quality.document_count > 0
        or research_report.data_quality.evidence_count > 0
    ):
        sections.append(_research_evidence_report_section(research_report))
    external_research_result = _cockpit_external_research_fetch_result_from_state(preview)
    if external_research_result is not None and external_research_result.entries:
        sections.append(_external_research_trace_report_section(external_research_result))
    if research_report is not None and (
        research_report.data_quality.document_count > 0
        or research_report.data_quality.evidence_count > 0
    ):
        sections.append(_research_score_report_section(research_report))
    return build_decision_report_context(
        title=f"投資判断レポート - {symbol or '選択銘柄'}",
        sections=sections,
        tags=["cockpit", "phase-19", "local-first"],
    )


def build_ranking_decision_report_context(
    *,
    ranked_rows: list[dict[str, str]],
    provider: str,
    start: date,
    end: date,
    ranking_purpose: str,
    weight_preset: str,
    comparison_summary: str,
    error_rows: list[dict[str, str]] | None = None,
) -> DecisionReportContext:
    top_rows = ranked_rows[:20]
    sections = [
        build_data_confidence_section(
            provider=provider,
            as_of=end,
            price_period=f"{start.isoformat()} to {end.isoformat()}",
            data_quality=_average_ranking_metric(ranked_rows, "data_quality_score"),
            metadata_source="銘柄マスタ / live provider",
            metadata_as_of=end.isoformat(),
            missing_fields=_ranking_missing_metadata_fields(top_rows),
            coverage_rows=_ranking_metadata_coverage_rows(top_rows),
            warnings=[row.get("message", "") for row in error_rows or []],
            notes=[comparison_summary],
        ),
        build_report_section(
            title="ランキング文脈",
            source_kind="ranking",
            provider=provider,
            as_of=end,
            summary={
                "ranking_purpose": ranking_purpose,
                "display_weight": weight_preset,
                "comparison": comparison_summary,
                "reported_rows": f"{len(top_rows)} / {len(ranked_rows)}",
            },
            rows=[
                _ranking_report_row(
                    row,
                    _symbol_universe_row_for_symbol(row.get("symbol", "")),
                    ranking_purpose=ranking_purpose,
                )
                for row in top_rows
            ],
            notes=["上位候補メモは比較条件と確認観点の保存であり、売買推奨ではありません。"],
        ),
        build_report_section(
            title="上位候補スコア詳細",
            source_kind="ranking",
            provider=provider,
            as_of=end,
            rows=[_ranking_report_detail_row(row) for row in top_rows],
            notes=[
                "詳細スコアは要約メモと分けて確認します。"
                "横並びの数値だけでなく、確認観点と一緒に読みます。"
            ],
        ),
        build_report_section(
            title="ランキング分布",
            source_kind="ranking",
            provider=provider,
            as_of=end,
            summary=_ranking_distribution_summary(ranked_rows),
            rows=_ranking_distribution_rows(ranked_rows),
            notes=[
                "上位だけでなく、スコアの偏り、リスク確認、データ品質、上昇気配・下降警戒の分布を見て候補群を比較します。"
            ],
        ),
        build_report_section(
            title="ファクター別上位候補",
            source_kind="ranking",
            provider=provider,
            as_of=end,
            rows=_ranking_factor_leader_rows(ranked_rows),
            notes=[
                "総合順位だけでなく、スクリーニング、上昇気配、リスク確認、ROE、配当利回りなど別観点の上位候補を並べます。"
            ],
        ),
    ]
    if top_rows:
        sections.append(
            build_decision_checkpoints_section(
                checkpoints=_ranking_group_checkpoints(ranked_rows, ranking_purpose),
                as_of=end,
            )
        )
    return build_decision_report_context(
        title="投資判断レポート - ランキング結果",
        sections=sections,
        tags=["ranking", "phase-19", "local-first"],
    )


def decision_report_json_download(context: DecisionReportContext) -> str:
    return reporting_decision_report_json_download(context)


def decision_report_markdown_download(context: DecisionReportContext) -> str:
    return render_decision_report_markdown(context)


def cockpit_decision_report_overview(preview: MarketDataPreview) -> dict[str, str]:
    symbol = _market_data_preview_symbol(preview)
    symbol_row = _symbol_universe_row_for_symbol(symbol) if symbol else None
    score_rows = investment_score_display_rows(preview.investment_score_rows)
    score_row = score_rows[0] if score_rows else {}
    return {
        "symbol": symbol or "選択銘柄",
        "company_name": symbol_name(symbol) or score_row.get("銘柄名", "") or "未取得",
        "overall_judgement": _cockpit_overall_judgement(score_row),
        "total_score": _display_report_value(score_row.get("総合スコア"), "未計算"),
        "confidence": _cockpit_report_confidence(score_row),
        "investment_stance": _cockpit_investment_stance(score_row, symbol_row, preview.bars),
        "key_risks": _cockpit_key_risks(score_row, symbol_row),
    }


def cockpit_decision_report_summary_lines(
    preview: MarketDataPreview,
    research_report: CompanyResearchReport | None = None,
) -> list[str]:
    overview = cockpit_decision_report_overview(preview)
    symbol = overview["symbol"]
    trend = _cockpit_price_trend_summary(preview.bars)
    evidence_line = (
        f"根拠資料では{research_report.data_quality.evidence_count}件の確認材料があり、"
        "価格・スコアだけでは見えない背景を補足します。"
        if research_report is not None and research_report.data_quality.evidence_count > 0
        else "根拠資料は未取得または不足しています。必要に応じてAI調査を更新してください。"
    )
    return [
        f"{symbol}は総合スコア{overview['total_score']}で、現時点の見方は「{overview['overall_judgement']}」です。",
        trend["summary"],
        evidence_line,
    ]


def cockpit_decision_report_evidence_rows(
    preview: MarketDataPreview,
    *,
    research_report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
) -> list[dict[str, str]]:
    symbol = _market_data_preview_symbol(preview)
    symbol_row = _symbol_universe_row_for_symbol(symbol) if symbol else None
    score_rows = investment_score_display_rows(preview.investment_score_rows)
    score_row = score_rows[0] if score_rows else {}
    trend = _cockpit_price_trend_summary(preview.bars)
    news_rows = _stock_news_card_rows(news_report) if news_report is not None else []
    positive_news = sum(1 for row in news_rows if row.get("sentiment") == "Positive")
    risk_news = sum(1 for row in news_rows if row.get("sentiment") == "Risk")
    news_reading = (
        f"ポジティブ {positive_news}件 / リスク {risk_news}件"
        if news_rows
        else "ニュース根拠は未取得です"
    )
    research_count = (
        str(research_report.data_quality.evidence_count) if research_report is not None else "0"
    )
    return [
        {
            "根拠": "価格トレンド",
            "読み取り": trend["summary"],
            "確認ポイント": trend["check"],
        },
        {
            "根拠": "業績・財務",
            "読み取り": _cockpit_score_strength_summary(score_row, symbol_row),
            "確認ポイント": "スクリーニング、財務指標、データ品質を合わせて確認します。",
        },
        {
            "根拠": "ニュース",
            "読み取り": news_reading,
            "確認ポイント": f"根拠資料 {research_count}件と重ねて確認します。",
        },
        {
            "根拠": "リスク",
            "読み取り": _cockpit_key_risks(score_row, symbol_row),
            "確認ポイント": "短期の値動き、為替、需要、バリュエーションを分けて確認します。",
        },
    ]


def _display_report_value(value: object, fallback: str = "未取得") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _cockpit_overall_judgement(score_row: dict[str, str]) -> str:
    score = _decimal_from_text(score_row.get("総合スコア"))
    downside = _decimal_from_text(score_row.get("下降警戒")) or Decimal("0")
    if score is None:
        return "未判定"
    if score >= Decimal("75") and downside < Decimal("65"):
        return "前向き確認"
    if score >= Decimal("60"):
        return "中立〜やや前向き"
    if score >= Decimal("45"):
        return "中立"
    return "慎重確認"


def _cockpit_report_confidence(score_row: dict[str, str]) -> str:
    data_quality = _decimal_from_text(score_row.get("データ品質"))
    if data_quality is None:
        return "低め"
    if data_quality >= Decimal("90"):
        return "高め"
    if data_quality >= Decimal("70"):
        return "中くらい"
    return "低め"


def _cockpit_investment_stance(
    score_row: dict[str, str],
    symbol_row: dict[str, str] | None,
    bars: list[Bar],
) -> str:
    score = _decimal_from_text(score_row.get("総合スコア"))
    downside = _decimal_from_text(score_row.get("下降警戒")) or Decimal("0")
    trend = _cockpit_price_trend_summary(bars)["summary"]
    if downside >= Decimal("70"):
        return "慎重確認 / リスク優先"
    if score is not None and score >= Decimal("70") and "高値圏" not in trend:
        return "中長期向け / 押し目確認"
    dividend_yield = (
        ranking_dividend_yield_pct_value(symbol_row.get("dividend_yield_pct"))
        if symbol_row
        else None
    )
    if dividend_yield is not None and dividend_yield >= Decimal("3"):
        return "インカム候補 / 配当安定性確認"
    return "様子見 / 追加根拠確認"


def _cockpit_key_risks(
    score_row: dict[str, str],
    symbol_row: dict[str, str] | None,
) -> str:
    risks: list[str] = []
    warning = score_row.get("注意点", "")
    if warning:
        risks.append(warning)
    downside = _decimal_from_text(score_row.get("下降警戒"))
    if downside is not None and downside >= Decimal("65"):
        risks.append("短期の下降警戒")
    if symbol_row is not None:
        risk_band = symbol_universe_detail_display_value(symbol_row, "risk_band")
        if risk_band:
            risks.append(f"リスク帯: {risk_band}")
        per = ranking_fundamental_metric_value("per", symbol_row.get("per"))
        pbr = ranking_fundamental_metric_value("pbr", symbol_row.get("pbr"))
        if (per is not None and per >= Decimal("40")) or (pbr is not None and pbr >= Decimal("10")):
            risks.append("バリュエーション")
    if not risks:
        risks.append("価格トレンド・外部環境")
    return " / ".join(dict.fromkeys(risks[:4]))


def _decision_report_overview_card_html(overview: dict[str, str]) -> str:
    fields = [
        ("総合判断", overview.get("overall_judgement", "未判定")),
        ("スコア", f"{overview.get('total_score', '未計算')} / 100"),
        ("信頼度", overview.get("confidence", "低め")),
        ("投資スタンス", overview.get("investment_stance", "様子見 / 追加根拠確認")),
        ("注意材料", overview.get("key_risks", "価格トレンド・外部環境")),
    ]
    field_html = "".join(
        '<div class="decision-report-field">'
        f'<div class="decision-report-field-label">{html.escape(label)}</div>'
        f'<div class="decision-report-field-value">{html.escape(value)}</div>'
        "</div>"
        for label, value in fields
    )
    title = f"投資判断レポート - {overview.get('symbol', '選択銘柄')}"
    company_name = overview.get("company_name", "")
    if company_name and company_name != "未取得":
        title = f"{title} / {company_name}"
    return (
        '<section class="decision-report-card">'
        f'<div class="decision-report-title">{html.escape(title)}</div>'
        f'<div class="decision-report-grid">{field_html}</div>'
        "</section>"
    )


def _decision_summary_list_html(lines: list[str]) -> str:
    items = "".join(f"<li>{html.escape(line)}</li>" for line in lines[:3])
    return f'<ol class="decision-summary-list">{items}</ol>'


def _render_cockpit_decision_report_sections(
    preview: MarketDataPreview,
    *,
    context: DecisionReportContext,
    overview: dict[str, str],
    score_row: dict[str, str],
    symbol_row: dict[str, str] | None,
    research_report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
) -> None:
    st.markdown("#### 詳細レポート")
    with st.container(border=True):
        st.markdown("##### 1. 要約")
        st.markdown(
            _decision_summary_list_html(
                cockpit_decision_report_summary_lines(preview, research_report)
            ),
            unsafe_allow_html=True,
        )

    with st.expander("2. 投資判断", expanded=True):
        _render_symbol_detail_table(
            [
                {"項目": "総合判断", "内容": overview.get("overall_judgement", "")},
                {"項目": "投資スタンス", "内容": overview.get("investment_stance", "")},
                {"項目": "注意材料", "内容": overview.get("key_risks", "")},
            ]
        )

    with st.expander("3. スコア内訳", expanded=True):
        _render_symbol_detail_table(score_component_rows(score_row))

    with st.expander("4. 価格・予測", expanded=True):
        trend = _cockpit_price_trend_summary(preview.bars)
        _render_symbol_detail_table(
            [
                {
                    "観点": "価格トレンド",
                    "内容": trend["summary"],
                    "確認ポイント": trend["check"],
                },
                {
                    "観点": "予測変化率",
                    "内容": _display_report_value(score_row.get("予測変化率"), "未計算"),
                    "確認ポイント": "強い上昇シグナルか、横ばい圏の参考予測かを確認します。",
                },
                {
                    "観点": "モデル一致度",
                    "内容": _display_report_value(score_row.get("モデル一致度"), "未計算"),
                    "確認ポイント": "モデル方向が分散している場合は短期判断を控えめに見ます。",
                },
            ]
        )

    with st.expander("5. ファンダメンタル", expanded=False):
        _render_symbol_detail_table(_cockpit_fundamental_report_rows(symbol_row))

    with st.expander("6. バリュエーション", expanded=False):
        _render_symbol_detail_table(_cockpit_valuation_report_rows(symbol_row))

    with st.expander("7. リスク", expanded=True):
        _render_symbol_detail_table(_cockpit_risk_report_rows(score_row, symbol_row, preview.bars))

    with st.expander("8. 根拠資料との対応", expanded=False):
        _render_symbol_detail_table(
            cockpit_decision_report_evidence_rows(
                preview,
                research_report=research_report,
                news_report=news_report,
            )
        )
        card_rows = _research_evidence_card_rows(
            research_report,
            news_report=news_report,
            limit=3,
        )
        if card_rows:
            st.markdown(_research_evidence_cards_html(card_rows), unsafe_allow_html=True)
        else:
            st.info("根拠資料はまだ取得されていません。AI調査を更新すると確認できます。")

    with st.expander("9. 補足", expanded=False):
        _render_compact_dataframe(_decision_report_context_summary_rows(context))


def _cockpit_fundamental_report_rows(
    symbol_row: dict[str, str] | None,
) -> list[dict[str, str]]:
    if symbol_row is None:
        return [
            {
                "観点": "銘柄マスタ",
                "内容": "未登録",
                "確認ポイント": "財務・分類情報を確認してください。",
            }
        ]
    return [
        {
            "観点": "市場・通貨",
            "内容": " / ".join(
                part
                for part in [
                    symbol_universe_detail_display_value(symbol_row, "market"),
                    symbol_universe_detail_display_value(symbol_row, "currency"),
                ]
                if part
            ),
            "確認ポイント": "為替や市場特性の影響を確認します。",
        },
        {
            "観点": "資産分類",
            "内容": symbol_universe_detail_display_value(symbol_row, "asset_type") or "未取得",
            "確認ポイント": "個別株、ETFなど商品特性に合わせて見ます。",
        },
        {
            "観点": "時価総額",
            "内容": symbol_universe_detail_display_value(symbol_row, "market_cap_tier") or "未取得",
            "確認ポイント": "大型・中小型で値動きの前提を分けます。",
        },
    ]


def _cockpit_valuation_report_rows(
    symbol_row: dict[str, str] | None,
) -> list[dict[str, str]]:
    if symbol_row is None:
        return [
            {
                "観点": "バリュエーション",
                "内容": "未取得",
                "確認ポイント": "PER/PBR/ROEを確認してください。",
            }
        ]
    return [
        {
            "観点": "PER / PBR / ROE",
            "内容": _cockpit_valuation_summary(symbol_row),
            "確認ポイント": "割安・割高を断定せず、成長率と利益率を合わせて確認します。",
        },
        {
            "観点": "配当",
            "内容": _cockpit_income_summary(symbol_row),
            "確認ポイント": "利回りだけでなく、継続性と減配リスクを確認します。",
        },
    ]


def _cockpit_risk_report_rows(
    score_row: dict[str, str],
    symbol_row: dict[str, str] | None,
    bars: list[Bar],
) -> list[dict[str, str]]:
    trend = _cockpit_price_trend_summary(bars)
    return [
        {
            "観点": "注意材料",
            "内容": _cockpit_key_risks(score_row, symbol_row),
            "確認ポイント": "根拠資料やニュースで一時要因か継続要因かを確認します。",
        },
        {
            "観点": "下降警戒",
            "内容": _display_report_value(score_row.get("下降警戒"), "未計算"),
            "確認ポイント": "上昇気配と同時に高い場合は、短期判断を慎重にします。",
        },
        {
            "観点": "価格位置",
            "内容": trend["summary"],
            "確認ポイント": trend["check"],
        },
    ]


def _decision_report_context_summary_rows(
    context: DecisionReportContext,
) -> list[dict[str, str]]:
    return [
        {
            "セクション": section.title,
            "情報元": section.source.kind,
            "サマリ項目": str(len(section.summary)),
            "明細行": str(len(section.rows)),
            "注意点": str(len(section.warnings)),
        }
        for section in context.sections
    ]


def _render_cockpit_decision_report(preview: MarketDataPreview) -> None:
    context = build_cockpit_decision_report_context(preview)
    symbol = _market_data_preview_symbol(preview)
    score_rows = investment_score_display_rows(preview.investment_score_rows)
    score_row = score_rows[0] if score_rows else {}
    symbol_row = _symbol_universe_row_for_symbol(symbol) if symbol else None
    research_report = _cockpit_research_report_from_state(preview)
    news_report = _cockpit_stock_news_report_from_state(preview)
    overview = cockpit_decision_report_overview(preview)

    st.markdown("### 07 投資判断レポート")
    st.info(
        "取得済みデータ、スコア、価格トレンド、根拠資料を判断材料として整理しました。"
        "売買推奨ではなく、後から確認できる分析メモとして扱います。"
    )
    st.markdown(_decision_report_overview_card_html(overview), unsafe_allow_html=True)

    summary_lines = cockpit_decision_report_summary_lines(preview, research_report)
    st.markdown("#### AI要約")
    st.markdown(_decision_summary_list_html(summary_lines), unsafe_allow_html=True)

    evidence_rows = cockpit_decision_report_evidence_rows(
        preview,
        research_report=research_report,
        news_report=news_report,
    )
    st.markdown("#### 判断に使った主な根拠")
    _render_symbol_detail_table(evidence_rows)

    _render_cockpit_decision_report_sections(
        preview,
        context=context,
        overview=overview,
        score_row=score_row,
        symbol_row=symbol_row,
        research_report=research_report,
        news_report=news_report,
    )

    _render_decision_report_download_buttons(
        context,
        expander_label="投資判断レポート",
        json_file_name="decision_report_cockpit.json",
        markdown_file_name="decision_report_cockpit.md",
        heading_prefix="07",
    )


def _render_ranking_decision_report(
    *,
    ranked_rows: list[dict[str, str]],
    provider: str,
    start: date,
    end: date,
    ranking_purpose: str,
    weight_preset: str,
    comparison_summary: str,
    error_rows: list[dict[str, str]],
) -> None:
    context = build_ranking_decision_report_context(
        ranked_rows=ranked_rows,
        provider=provider,
        start=start,
        end=end,
        ranking_purpose=ranking_purpose,
        weight_preset=weight_preset,
        comparison_summary=comparison_summary,
        error_rows=error_rows,
    )
    _render_decision_report_downloads(
        context,
        expander_label="投資判断レポート",
        json_file_name="decision_report_ranking.json",
        markdown_file_name="decision_report_ranking.md",
    )


def _render_ranking_decision_report_lazy(
    *,
    ranked_rows: list[dict[str, str]],
    provider: str,
    start: date,
    end: date,
    ranking_purpose: str,
    weight_preset: str,
    comparison_summary: str,
    error_rows: list[dict[str, str]],
    report_state_key: str,
) -> None:
    cached_context = st.session_state.get(report_state_key)
    if not isinstance(cached_context, DecisionReportContext):
        st.markdown("### 投資判断レポート")
        render_mascot_panel(
            "report",
            message="深掘り候補を確認したあと、必要なときだけ分析メモとしてレポート化できます。",
            layout="compact",
        )
        st.info(
            "深掘り操作を先に使えるよう、ランキングの投資判断レポートは必要時に作成します。"
            "作成後は同じ評価方針の間、ダウンロード用データを再利用します。"
        )
        if st.button("投資判断レポートを作成", key=f"{report_state_key}_build"):
            with st.spinner("ランキングの比較レポートを作成しています。"):
                cached_context = build_ranking_decision_report_context(
                    ranked_rows=ranked_rows,
                    provider=provider,
                    start=start,
                    end=end,
                    ranking_purpose=ranking_purpose,
                    weight_preset=weight_preset,
                    comparison_summary=comparison_summary,
                    error_rows=error_rows,
                )
                st.session_state[report_state_key] = cached_context

    if isinstance(cached_context, DecisionReportContext):
        _render_decision_report_downloads(
            cached_context,
            expander_label="投資判断レポート",
            json_file_name="decision_report_ranking.json",
            markdown_file_name="decision_report_ranking.md",
        )
        if st.button("レポートを更新", key=f"{report_state_key}_refresh"):
            with st.spinner("ランキングの比較レポートを更新しています。"):
                st.session_state[report_state_key] = build_ranking_decision_report_context(
                    ranked_rows=ranked_rows,
                    provider=provider,
                    start=start,
                    end=end,
                    ranking_purpose=ranking_purpose,
                    weight_preset=weight_preset,
                    comparison_summary=comparison_summary,
                    error_rows=error_rows,
                )


def _ranking_decision_report_state_key(ranking_source: str, weight_preset: str) -> str:
    source_hash = hashlib.sha1(
        f"{ranking_source}|{weight_preset}|decision_report".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:12]
    return f"market_data_ranking_decision_report_{source_hash}"


def _render_decision_report_downloads(
    context: DecisionReportContext,
    *,
    expander_label: str,
    json_file_name: str,
    markdown_file_name: str,
    heading_prefix: str | None = None,
) -> None:
    markdown = decision_report_markdown_download(context)
    heading = f"{heading_prefix} {expander_label}" if heading_prefix else expander_label
    st.markdown(f"### {heading}")
    st.info(
        "取得済みデータ、銘柄メタデータ、スコア、根拠、確認ポイントを判断材料として整理しました。"
        "売買推奨ではなく、後から確認できる分析メモとして扱います。"
    )
    _render_decision_report_download_buttons(
        context,
        expander_label=expander_label,
        json_file_name=json_file_name,
        markdown_file_name=markdown_file_name,
        heading_prefix=None,
    )
    with st.expander("レポート本文を表示", expanded=False):
        preview_tab, raw_tab = st.tabs(["読みやすい表示", "Markdown本文"])
        with preview_tab:
            with st.container(border=True):
                st.markdown(markdown)
        with raw_tab:
            st.code(markdown, language="markdown")


def _render_decision_report_download_buttons(
    context: DecisionReportContext,
    *,
    expander_label: str,
    json_file_name: str,
    markdown_file_name: str,
    heading_prefix: str | None = None,
) -> None:
    markdown = decision_report_markdown_download(context)
    heading = f"{heading_prefix} {expander_label}" if heading_prefix else expander_label
    st.markdown(f"#### ダウンロード / {heading}")
    col_markdown, col_json, col_manifest, col_zip = st.columns(4)
    col_markdown.download_button(
        "Markdownをダウンロード",
        data=markdown,
        file_name=markdown_file_name,
        mime="text/markdown",
    )
    col_json.download_button(
        "JSONをダウンロード",
        data=decision_report_json_download(context),
        file_name=json_file_name,
        mime="application/json",
    )
    col_manifest.download_button(
        "manifestをダウンロード",
        data=decision_report_manifest_json_download(context),
        file_name="decision_report_manifest.json",
        mime="application/json",
    )
    col_zip.download_button(
        "一式ZIP",
        data=decision_report_zip_download(context),
        file_name="decision_report_package.zip",
        mime="application/zip",
    )


def _investment_score_report_section(
    row: dict[str, str],
    *,
    source_kind: ReportSourceKind,
    provider: str | None = None,
    symbol: str = "",
    as_of: date | None = None,
) -> DecisionReportSection:
    return build_report_section(
        title="スコア分解",
        source_kind=source_kind,
        provider=provider,
        symbol=symbol or None,
        as_of=as_of,
        summary={
            "total_score": row.get("total_score", ""),
            "score_band": row.get("score_band", ""),
            "screening_score": row.get("screening_score", ""),
            "forecast_agreement_score": row.get("forecast_agreement_score", ""),
            "upside_signal_score": row.get("upside_signal_score", ""),
            "downside_signal_score": row.get("downside_signal_score", ""),
            "forecast_return_pct": row.get("forecast_return_pct", ""),
            "data_quality_score": row.get("data_quality_score", ""),
            "risk_signal_score": row.get("risk_signal_score", ""),
            "warnings": row.get("warnings", ""),
            "reasons": row.get("reasons", ""),
        },
        rows=[
            {"component": "スクリーニング", "score": row.get("screening_score", "")},
            {
                "component": "上昇気配",
                "score": row.get("upside_signal_score", ""),
            },
            {
                "component": "下降警戒",
                "score": row.get("downside_signal_score", ""),
            },
            {"component": "データ品質", "score": row.get("data_quality_score", "")},
            {"component": "リスク確認", "score": row.get("risk_signal_score", "")},
        ],
    )


def _valuation_income_risk_report_section(
    symbol_row: dict[str, str],
    *,
    source_kind: ReportSourceKind,
    symbol: str,
    as_of: date | None = None,
) -> DecisionReportSection:
    return build_report_section(
        title="バリュエーション / インカム / リスク",
        source_kind=source_kind,
        symbol=symbol,
        as_of=as_of,
        rows=[
            {
                "area": "バリュエーション",
                "metric": "PER",
                "value": symbol_universe_detail_display_value(symbol_row, "per"),
            },
            {
                "area": "バリュエーション",
                "metric": "PBR",
                "value": symbol_universe_detail_display_value(symbol_row, "pbr"),
            },
            {
                "area": "バリュエーション",
                "metric": "ROE",
                "value": symbol_universe_detail_display_value(symbol_row, "roe_pct"),
            },
            {
                "area": "インカム",
                "metric": "配当利回り",
                "value": symbol_universe_detail_display_value(symbol_row, "dividend_yield_pct"),
            },
            {
                "area": "インカム",
                "metric": "配当カテゴリ",
                "value": symbol_universe_detail_display_value(symbol_row, "dividend_category"),
            },
            {
                "area": "ETF",
                "metric": "経費率",
                "value": symbol_universe_detail_display_value(
                    symbol_row,
                    "expense_ratio_pct",
                ),
            },
            {
                "area": "ETF",
                "metric": "連動指数",
                "value": symbol_universe_detail_display_value(
                    symbol_row,
                    "index_family",
                ),
            },
            {
                "area": "Risk",
                "metric": "リスク帯",
                "value": symbol_universe_detail_display_value(symbol_row, "risk_band"),
            },
        ],
    )


def _symbol_report_metadata(symbol_row: dict[str, str]) -> dict[str, str]:
    columns = [
        "market",
        "asset_type",
        "currency",
        "nisa_category",
        "investment_style",
        "market_cap_tier",
        "broker",
        "tradability",
        "is_sbi_supported",
        "metadata_source",
        "metadata_as_of",
        "metadata_updated_at",
    ]
    return {column: symbol_universe_detail_display_value(symbol_row, column) for column in columns}


def _symbol_report_coverage_rows(symbol_row: dict[str, str] | None) -> list[dict[str, str]]:
    if symbol_row is None:
        return [{"field": "symbol_metadata", "status": "missing", "value": ""}]
    rows = []
    for column in _symbol_report_fields(symbol_row):
        raw_value = _symbol_detail_raw_value(symbol_row, column)
        rows.append(
            {
                "field": column,
                "status": "available" if raw_value else "missing",
                "value": (
                    symbol_universe_detail_display_value(symbol_row, column) if raw_value else ""
                ),
            }
        )
    return rows


def _missing_symbol_report_fields(symbol_row: dict[str, str] | None) -> list[str]:
    if symbol_row is None:
        return ["symbol_metadata"]
    return [
        column
        for column in _symbol_report_fields(symbol_row)
        if not _symbol_detail_raw_value(symbol_row, column)
    ]


def _symbol_report_fields(symbol_row: dict[str, str]) -> list[str]:
    asset_type = _symbol_detail_raw_value(symbol_row, "asset_type")
    common = ["metadata_source", "metadata_as_of", "nisa_category", "investment_style"]
    if asset_type == "etf":
        return common + [
            "dividend_yield_pct",
            "index_family",
            "expense_ratio_pct",
            "complexity",
            "risk_band",
        ]
    return common + [
        "dividend_yield_pct",
        "dividend_category",
        "per",
        "pbr",
        "roe_pct",
        "market_cap_tier",
        "risk_band",
    ]


def _symbol_report_value(symbol_row: dict[str, str] | None, column: str) -> str | None:
    if symbol_row is None:
        return None
    value = symbol_universe_detail_display_value(symbol_row, column)
    return value if value else None


def _bars_period_label(bars: list[Bar]) -> str | None:
    if not bars:
        return None
    return f"{bars[0].ts.date().isoformat()} to {bars[-1].ts.date().isoformat()}"


def _date_from_iso_text(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _cockpit_report_checkpoints(
    display_score_row: dict[str, str],
    symbol_row: dict[str, str] | None,
    bars: list[Bar],
) -> list[dict[str, str]]:
    trend = _cockpit_price_trend_summary(bars)
    return [
        {
            "area": "スコア",
            "finding": _cockpit_score_strength_summary(display_score_row, symbol_row),
            "confirmation_point": "総合スコアだけでなく、構成要素を確認してから判断材料にします。",
        },
        {
            "area": "注意点",
            "finding": _cockpit_score_caution_summary(display_score_row, symbol_row),
            "confirmation_point": "警告とデータ欠損を先に確認します。",
        },
        {
            "area": "バリュエーション",
            "finding": _cockpit_valuation_summary(symbol_row),
            "confirmation_point": "利益成長や業績見通しが現在の評価を支えているか確認します。",
        },
        {
            "area": "インカム",
            "finding": _cockpit_income_summary(symbol_row),
            "confirmation_point": "利回りだけでなく、配当方針と安定性も確認します。",
        },
        {"area": "価格トレンド", "finding": trend["summary"], "confirmation_point": trend["check"]},
    ]


def _ranking_report_checkpoints(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
) -> list[dict[str, str]]:
    return [
        {
            "area": "ランキング",
            "finding": row.get("note", ""),
            "confirmation_point": "銘柄コックピットで価格トレンドと予測詳細を確認します。",
        },
        {
            "area": "バリュエーション",
            "finding": _cockpit_valuation_summary(symbol_row),
            "confirmation_point": "評価水準が業績や財務指標に支えられているか確認します。",
        },
        {
            "area": "インカム",
            "finding": _cockpit_income_summary(symbol_row),
            "confirmation_point": "配当方針と下落リスクを確認します。",
        },
        {
            "area": "次の確認",
            "finding": _ranking_next_action(row, symbol_row),
            "confirmation_point": "確認順の整理として使い、注文指示として扱いません。",
        },
    ]


def _ranking_distribution_summary(rows: list[dict[str, str]]) -> dict[str, str]:
    top_score = _decimal_from_text(rows[0].get("total_score")) if rows else None
    twentieth_score = _decimal_from_text(rows[19].get("total_score")) if len(rows) >= 20 else None
    return {
        "比較銘柄数": str(len(rows)),
        "表示上位": str(min(len(rows), 20)),
        "1位スコア": _format_report_decimal(top_score),
        "20位スコア": _format_report_decimal(twentieth_score),
        "上位20件の平均総合スコア": _average_ranking_metric(rows[:20], "total_score"),
        "平均スクリーニング": _average_ranking_metric(rows, "screening_score"),
        "平均上昇気配": _average_ranking_metric(rows, "upside_signal_score"),
        "平均下降警戒": _average_ranking_metric(rows, "downside_signal_score"),
        "平均データ品質": _average_ranking_metric(rows, "data_quality_score"),
        "平均リスク確認": _average_ranking_metric(rows, "risk_signal_score"),
    }


def _ranking_distribution_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "観点": "総合スコア 80以上",
            "件数": str(_count_rows_at_least(rows, "total_score", Decimal("80"))),
            "読み方": "上位候補群の厚みを確認します。",
        },
        {
            "観点": "上昇気配 75以上",
            "件数": str(_count_rows_at_least(rows, "upside_signal_score", Decimal("75"))),
            "読み方": "短期的な上向きシグナルが強い候補の多さを確認します。",
        },
        {
            "観点": "下降警戒 65以上",
            "件数": str(_count_rows_at_least(rows, "downside_signal_score", Decimal("65"))),
            "読み方": "上位候補内でもリスク確認を先にしたい候補数を確認します。",
        },
        {
            "観点": "データ品質 90以上",
            "件数": str(_count_rows_at_least(rows, "data_quality_score", Decimal("90"))),
            "読み方": "比較に使えるデータが十分な候補の多さを確認します。",
        },
        {
            "観点": "リスク確認 50未満",
            "件数": str(_count_rows_below(rows, "risk_signal_score", Decimal("50"))),
            "読み方": "上位候補内でも先に警戒すべき銘柄数を確認します。",
        },
        {
            "観点": "警告あり",
            "件数": str(sum(1 for row in rows if str(row.get("warnings", "")).strip())),
            "読み方": "高スコアでも確認順を下げるべき候補がないか見ます。",
        },
    ]


def _ranking_factor_leader_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    leaders: list[dict[str, str]] = []
    for label, metric, prefer_low in [
        ("総合スコア", "total_score", False),
        ("スクリーニング", "screening_score", False),
        ("上昇気配", "upside_signal_score", False),
        ("下降警戒", "downside_signal_score", True),
        ("データ品質", "data_quality_score", False),
        ("リスク確認", "risk_signal_score", False),
    ]:
        row = _best_ranking_row_by_metric(rows, metric, prefer_low=prefer_low)
        if row is not None:
            leaders.append(_ranking_factor_leader_row(label, row, row.get(metric, "")))

    for label, metric, prefer_low in [
        ("ROE", "roe_pct", False),
        ("配当利回り", "dividend_yield_pct", False),
        ("低PER", "per", True),
        ("低PBR", "pbr", True),
    ]:
        row = _best_ranking_row_by_symbol_metric(rows, metric, prefer_low=prefer_low)
        if row is not None:
            symbol_row = _symbol_universe_row_for_symbol(row.get("symbol", ""))
            if symbol_row is not None:
                leaders.append(
                    _ranking_factor_leader_row(
                        label,
                        row,
                        symbol_universe_detail_display_value(symbol_row, metric),
                    )
                )
    return leaders


def _ranking_factor_leader_row(
    label: str,
    row: dict[str, str],
    metric_value: object,
) -> dict[str, str]:
    symbol = row.get("symbol", "")
    return {
        "観点": label,
        "銘柄": symbol,
        "銘柄名": symbol_name(symbol) or "",
        "順位": row.get("rank", ""),
        "指標値": str(metric_value),
        "確認観点": ranking_investment_note(row, _symbol_universe_rows_by_symbol()),
    }


def _ranking_group_checkpoints(
    rows: list[dict[str, str]],
    ranking_purpose: str,
) -> list[dict[str, str]]:
    return [
        {
            "area": "上位群",
            "finding": f"{ranking_purpose}の条件で上位20件を比較対象として整理しています。",
            "confirmation_point": "1位だけでなく、上位候補に共通する強みと弱点を確認します。",
        },
        {
            "area": "分布",
            "finding": (
                f"平均上昇気配は{_average_ranking_metric(rows, 'upside_signal_score')}、"
                f"平均下降警戒は{_average_ranking_metric(rows, 'downside_signal_score')}、"
                f"平均リスク確認は{_average_ranking_metric(rows, 'risk_signal_score')}です。"
            ),
            "confirmation_point": "スコアの高さが一部要素だけに偏っていないか確認します。",
        },
        {
            "area": "ファクター",
            "finding": "総合順位とは別に、スクリーニング、上昇気配、リスク確認、ROE、配当利回りの上位候補を抽出しています。",
            "confirmation_point": "投資目的に近いファクターの候補から深掘り順を決めます。",
        },
        {
            "area": "次の確認",
            "finding": "ランキングは候補群の優先順位づけであり、個別判断はコックピットで確認します。",
            "confirmation_point": "銘柄ごとの価格トレンド、決算材料、配当方針、リスクを確認してから判断します。",
        },
    ]


def _ranking_metadata_coverage_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    fields = [
        "metadata_source",
        "metadata_as_of",
        "nisa_category",
        "investment_style",
        "dividend_yield_pct",
        "per",
        "pbr",
        "roe_pct",
        "market_cap_tier",
        "risk_band",
    ]
    return [
        {
            "項目": field,
            "状態": "取得あり" if available_count == len(rows) else "一部未取得",
            "内容": f"{available_count}/{len(rows)}件",
        }
        for field in fields
        for available_count in [_ranking_metadata_available_count(rows, field)]
    ]


def _ranking_missing_metadata_fields(rows: list[dict[str, str]]) -> list[str]:
    return [
        row["項目"] for row in _ranking_metadata_coverage_rows(rows) if row["状態"] != "取得あり"
    ]


def _ranking_metadata_available_count(rows: list[dict[str, str]], field: str) -> int:
    count = 0
    for row in rows:
        symbol_row = _symbol_universe_row_for_symbol(row.get("symbol", ""))
        if symbol_row is not None and _symbol_metadata_field_available(symbol_row, field):
            count += 1
    return count


def _symbol_metadata_field_available(symbol_row: dict[str, str], field: str) -> bool:
    value = _symbol_detail_raw_value(symbol_row, field)
    if not value:
        return False
    if ranking_fundamental_metric_is_abnormal(field, value):
        return False
    return True


def _best_ranking_row_by_metric(
    rows: list[dict[str, str]],
    metric: str,
    *,
    prefer_low: bool = False,
) -> dict[str, str] | None:
    return _best_row_by_decimal(
        rows,
        lambda row: _decimal_from_text(row.get(metric)),
        prefer_low=prefer_low,
    )


def _best_ranking_row_by_symbol_metric(
    rows: list[dict[str, str]],
    metric: str,
    *,
    prefer_low: bool = False,
) -> dict[str, str] | None:
    return _best_row_by_decimal(
        rows,
        lambda row: _symbol_metric_decimal(
            _symbol_universe_row_for_symbol(row.get("symbol", "")), metric
        ),
        prefer_low=prefer_low,
    )


def _symbol_metric_decimal(symbol_row: dict[str, str] | None, metric: str) -> Decimal | None:
    if symbol_row is None:
        return None
    metric_value = ranking_fundamental_metric_value(metric, symbol_row.get(metric))
    if metric_value is not None or metric in {"dividend_yield_pct", "per", "pbr", "roe_pct"}:
        return metric_value
    return _decimal_from_text(symbol_row.get(metric))


def _best_row_by_decimal(
    rows: list[dict[str, str]],
    value_getter: Callable[[dict[str, str]], Decimal | None],
    *,
    prefer_low: bool = False,
) -> dict[str, str] | None:
    best_row: dict[str, str] | None = None
    best_value: Decimal | None = None
    for row in rows:
        value = value_getter(row)
        if value is None:
            continue
        if best_value is None:
            best_row = row
            best_value = value
            continue
        if prefer_low and value < best_value:
            best_row = row
            best_value = value
        elif not prefer_low and value > best_value:
            best_row = row
            best_value = value
    return best_row


def _average_ranking_metric(rows: list[dict[str, str]], metric: str) -> str:
    values = [
        value
        for row in rows
        for value in [_decimal_from_text(row.get(metric))]
        if value is not None
    ]
    if not values:
        return "未計算"
    average = sum(values, Decimal("0")) / Decimal(len(values))
    return _format_report_decimal(average)


def _count_rows_at_least(rows: list[dict[str, str]], metric: str, threshold: Decimal) -> int:
    return sum(
        1
        for row in rows
        for value in [_decimal_from_text(row.get(metric))]
        if value is not None and value >= threshold
    )


def _count_rows_below(rows: list[dict[str, str]], metric: str, threshold: Decimal) -> int:
    return sum(
        1
        for row in rows
        for value in [_decimal_from_text(row.get(metric))]
        if value is not None and value < threshold
    )


def _format_report_decimal(value: Decimal | None) -> str:
    if value is None:
        return "未計算"
    formatted = format(value.quantize(Decimal("0.01")).normalize(), "f")
    return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted


def _ranking_report_row(
    row: dict[str, str],
    symbol_row: dict[str, str] | None = None,
    *,
    ranking_purpose: str = "",
) -> dict[str, str]:
    symbol = row.get("symbol", "")
    name = (
        row.get("name", "")
        or (symbol_row.get("name", "") if symbol_row is not None else "")
        or symbol_name(symbol)
        or ""
    )
    return {
        "rank": row.get("rank", ""),
        "symbol": symbol,
        "name": name,
        "ranking_purpose": ranking_purpose,
        "total_score": row.get("total_score", ""),
        "score_band": row.get("score_band", ""),
        "review_point": _ranking_report_review_point(row, symbol_row),
    }


def _ranking_report_detail_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "rank": row.get("rank", ""),
        "symbol": row.get("symbol", ""),
        "screening_score": row.get("screening_score", ""),
        "forecast_agreement_score": row.get("forecast_agreement_score", ""),
        "upside_signal_score": row.get("upside_signal_score", ""),
        "downside_signal_score": row.get("downside_signal_score", ""),
        "data_quality_score": row.get("data_quality_score", ""),
        "risk_signal_score": row.get("risk_signal_score", ""),
        "warnings": row.get("warnings", ""),
    }


def _ranking_report_review_point(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
) -> str:
    warning = str(row.get("warnings", "")).strip()
    if warning:
        return f"注意点: {warning}。スコアの強さより先に警告内容を確認します。"
    risk = _decimal_from_text(row.get("risk_signal_score"))
    if risk is not None and risk < Decimal("50"):
        return "リスク確認が低めです。値動き、下落耐性、ポジションサイズを先に確認します。"
    downside = _decimal_from_text(row.get("downside_signal_score"))
    if downside is not None and downside >= Decimal("65"):
        return "下降警戒が強めです。下向きシグナルと直近トレンドを先に確認します。"
    quality = _decimal_from_text(row.get("data_quality_score"))
    if quality is not None and quality < Decimal("80"):
        return "データ品質に確認余地があります。取得期間や欠損項目を確認します。"
    if symbol_row is not None:
        per = ranking_fundamental_metric_value("per", symbol_row.get("per"))
        pbr = ranking_fundamental_metric_value("pbr", symbol_row.get("pbr"))
        if (per is not None and per >= Decimal("40")) or (pbr is not None and pbr >= Decimal("10")):
            return "バリュエーションが高めです。成長期待と決算材料の裏付けを確認します。"
        dividend_yield = ranking_dividend_yield_pct_value(symbol_row.get("dividend_yield_pct"))
        if dividend_yield is not None and dividend_yield >= Decimal("3"):
            return "インカム面が目立ちます。配当方針、減配リスク、業績安定性を確認します。"
    return "スコアとデータ品質が比較的そろっています。価格トレンドと個別材料を確認します。"


def cockpit_investment_memo_rows(
    preview: MarketDataPreview,
    row: dict[str, str],
) -> list[dict[str, str]]:
    symbol = _market_data_preview_symbol(preview) or row.get("銘柄", "")
    symbol_row = _symbol_universe_row_for_symbol(symbol) if symbol else None
    return _cockpit_investment_memo_rows(row, symbol_row, preview.bars)


def _cockpit_investment_memo_rows(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
    bars: list[Bar],
) -> list[dict[str, str]]:
    strength = _cockpit_score_strength_summary(row, symbol_row)
    caution = _cockpit_score_caution_summary(row, symbol_row)
    valuation = _cockpit_valuation_summary(symbol_row)
    income = _cockpit_income_summary(symbol_row)
    trend = _cockpit_price_trend_summary(bars)
    next_action = _cockpit_next_action_summary(row, symbol_row, trend)
    return [
        {
            "観点": "スコア解釈",
            "評価": strength,
            "確認ポイント": "スコアは深掘り順の整理で、売買推奨ではありません。",
        },
        {
            "観点": "主な注意点",
            "評価": caution,
            "確認ポイント": "警告がない場合も、価格水準と決算材料は個別に確認してください。",
        },
        {
            "観点": "バリュエーション",
            "評価": valuation,
            "確認ポイント": "高PER/PBRなら成長期待の裏付け、低PER/PBRなら低評価の理由を確認します。",
        },
        {
            "観点": "インカム",
            "評価": income,
            "確認ポイント": "利回りだけでなく、配当性向、減配リスク、業績安定性を合わせて見ます。",
        },
        {
            "観点": "価格トレンド",
            "評価": trend["summary"],
            "確認ポイント": trend["check"],
        },
        {
            "観点": "次の確認",
            "評価": next_action,
            "確認ポイント": "銘柄データとチャートを往復し、根拠がそろう候補だけを深掘りします。",
        },
    ]


def _cockpit_score_strength_summary(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
) -> str:
    strengths: list[str] = []
    if (_decimal_from_text(row.get("上昇気配")) or Decimal("0")) >= Decimal("75"):
        strengths.append("上昇気配が比較的強く出ています")
    if (_decimal_from_text(row.get("データ品質")) or Decimal("0")) >= Decimal("90"):
        strengths.append("データ品質が高く、比較の土台が安定しています")
    if (_decimal_from_text(row.get("Screening")) or Decimal("0")) >= Decimal("80"):
        strengths.append("スクリーニング上位の条件に合っています")
    roe = (
        ranking_fundamental_metric_value("roe_pct", symbol_row.get("roe_pct"))
        if symbol_row
        else None
    )
    if roe is not None and roe >= Decimal("20"):
        strengths.append("ROEが高く、資本効率の強さが見えます")
    if (_decimal_from_text(row.get("Risk")) or Decimal("0")) >= Decimal("70"):
        strengths.append("短期のリスクシグナルは比較的落ち着いています")
    if not strengths:
        return "突出した強みより、各指標のバランスを確認する候補です。"
    return " / ".join(strengths[:3])


def _cockpit_score_caution_summary(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
) -> str:
    warning = row.get("注意点", "")
    if warning:
        return warning
    downside = _decimal_from_text(row.get("下降警戒"))
    if downside is not None and downside >= Decimal("75"):
        return "下降警戒が強めです。下向きシグナルと直近トレンドを先に確認してください。"
    if downside is not None and downside >= Decimal("65"):
        return "下降警戒があります。上昇気配だけでなく下向き材料も確認してください。"
    risk_score = _decimal_from_text(row.get("Risk"))
    if risk_score is not None and risk_score < Decimal("50"):
        return "値動きや下落耐性の確認を優先したい候補です。"
    data_quality = _decimal_from_text(row.get("データ品質"))
    if data_quality is not None and data_quality < Decimal("80"):
        return "データ品質が低めのため、取得元や期間を変えて再確認したい候補です。"
    if symbol_row is None:
        return "銘柄マスタの補足情報が少ないため、財務・分類・配当情報を別途確認してください。"
    per = ranking_fundamental_metric_value("per", symbol_row.get("per"))
    pbr = ranking_fundamental_metric_value("pbr", symbol_row.get("pbr"))
    if (per is not None and per >= Decimal("40")) or (pbr is not None and pbr >= Decimal("10")):
        return "PER/PBRが高めです。成長期待が株価にどこまで織り込まれているか確認してください。"
    dividend_yield = ranking_dividend_yield_pct_value(symbol_row.get("dividend_yield_pct"))
    if dividend_yield is not None and dividend_yield >= Decimal("5"):
        return "配当利回りが高いため、減配リスクや一時要因を確認してください。"
    return "大きな警告はありません。スコアの内訳とチャートの位置を確認してください。"


def _cockpit_valuation_summary(symbol_row: dict[str, str] | None) -> str:
    if symbol_row is None:
        return "PER/PBR/ROEは銘柄マスタ未登録です。"
    return (
        f"PER {symbol_universe_detail_display_value(symbol_row, 'per')}、"
        f"PBR {symbol_universe_detail_display_value(symbol_row, 'pbr')}、"
        f"ROE {symbol_universe_detail_display_value(symbol_row, 'roe_pct')}"
    )


def _cockpit_income_summary(symbol_row: dict[str, str] | None) -> str:
    if symbol_row is None:
        return "配当利回りと配当カテゴリは銘柄マスタ未登録です。"
    return (
        f"配当利回り {symbol_universe_detail_display_value(symbol_row, 'dividend_yield_pct')}、"
        f"分類 {symbol_universe_detail_display_value(symbol_row, 'dividend_category')}"
    )


def _cockpit_price_trend_summary(bars: list[Bar]) -> dict[str, str]:
    closes = [bar.close for bar in bars if bar.close > 0]
    if len(closes) < 2:
        return {
            "summary": "価格トレンドを判断するには取得期間の終値データが不足しています。",
            "check": "取得期間を広げるか、別providerで再取得してください。",
        }
    first_close = closes[0]
    latest_close = closes[-1]
    change_pct = ((latest_close - first_close) / first_close * Decimal("100")).quantize(
        Decimal("0.1")
    )
    high = max(closes)
    low = min(closes)
    if high == low:
        range_label = "横ばい圏"
    else:
        range_position = (latest_close - low) / (high - low)
        if range_position >= Decimal("0.8"):
            range_label = "期間レンジの高値圏"
        elif range_position <= Decimal("0.2"):
            range_label = "期間レンジの安値圏"
        else:
            range_label = "期間レンジの中間圏"
    if change_pct >= Decimal("3"):
        direction = "上昇基調"
    elif change_pct <= Decimal("-3"):
        direction = "下落基調"
    else:
        direction = "横ばい圏"
    return {
        "summary": f"取得期間で{change_pct:+}%。終値は{range_label}、価格トレンドは{direction}です。",
        "check": "高値圏では追随リスク、安値圏では反転材料と下落継続リスクを確認します。",
    }


def _cockpit_next_action_summary(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
    trend: dict[str, str],
) -> str:
    downside = _decimal_from_text(row.get("下降警戒"))
    if downside is not None and downside >= Decimal("65"):
        return "下降警戒が出ています。下向きシグナル、価格トレンド、警告を先に確認してください。"
    risk_score = _decimal_from_text(row.get("Risk"))
    if risk_score is not None and risk_score < Decimal("50"):
        return "まず下落耐性、損失許容幅、ポジションサイズを確認してください。"
    if "高値圏" in trend["summary"]:
        return "高値圏のため、出来高、押し目、決算予定を確認してから深掘りしてください。"
    per = ranking_fundamental_metric_value("per", symbol_row.get("per")) if symbol_row else None
    pbr = ranking_fundamental_metric_value("pbr", symbol_row.get("pbr")) if symbol_row else None
    if symbol_row and (
        (per is not None and per >= Decimal("40")) or (pbr is not None and pbr >= Decimal("10"))
    ):
        return "高バリュエーションのため、成長率、利益率、決算ガイダンスを確認してください。"
    dividend_yield = (
        ranking_dividend_yield_pct_value(symbol_row.get("dividend_yield_pct"))
        if symbol_row
        else None
    )
    if dividend_yield is not None and dividend_yield >= Decimal("3"):
        return "インカム候補として、配当性向、減配履歴、キャッシュフローを確認してください。"
    return "候補として残し、銘柄データ、チャート、決算材料の順に確認してください。"


def _render_score_breakdown_chart(rows: list[dict[str, str]]) -> None:
    frame = pd.DataFrame(rows)
    frame["score"] = pd.to_numeric(frame["スコア"], errors="coerce")
    frame = frame.dropna(subset=["score"])
    if frame.empty:
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadius=4)
        .encode(
            x=alt.X("score:Q", title="Score", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("要素:N", title=None, sort=None),
            color=alt.Color(
                "要素:N",
                legend=None,
                scale=alt.Scale(
                    range=[
                        CHART_COLORS["price"],
                        CHART_COLORS["prediction"],
                        THEME_COLORS["signal_buy"],
                        THEME_COLORS["signal_risk"],
                    ]
                ),
            ),
            tooltip=[
                alt.Tooltip("要素:N", title="要素"),
                alt.Tooltip("score:Q", title="スコア"),
            ],
        )
        .properties(height=150)
    )
    st.altair_chart(style_altair_chart(chart), use_container_width=True)


def _render_market_chart(
    rows: list[dict[str, str]],
    *,
    currency: str = "",
    title: str = "",
) -> None:
    if not rows:
        st.info(EMPTY_STATE_MESSAGES["chart_rows"])
        return
    y_axis_title = f"終値 ({currency})" if currency else "終値"
    chart_data = market_chart_long_frame(rows)
    boundary_data = forecast_boundary_frame(rows)
    latest_actual_data = latest_actual_price_frame(rows)
    color_domain = forecast_chart_color_domain(chart_data["series_label"].tolist())
    color_range = forecast_chart_color_range(color_domain)
    color_scale = alt.Scale(domain=color_domain, range=color_range)
    legend_data = chart_data[["series_label", "line_label"]].drop_duplicates().copy()
    line_type_legend_data = pd.DataFrame(
        [
            {"line_label": "実績", "description": "実線: 実績価格"},
            {"line_label": "予測", "description": "破線: 予測モデル"},
        ]
    )
    disabled_series = alt.selection_point(
        fields=["series_label"],
        on="click",
        toggle="true",
        empty=False,
    )
    forecast_data = chart_data[chart_data["series_label"] != FORECAST_ACTUAL_LABEL]
    actual_data = chart_data[chart_data["series_label"] == FORECAST_ACTUAL_LABEL]
    base_encoding = {
        "x": alt.X("date:T", title="Date", axis=alt.Axis(format="%m/%d", labelAngle=0)),
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
        "opacity": alt.condition(disabled_series, alt.value(0.18), alt.value(1.0)),
    }
    forecast_lines = (
        alt.Chart(forecast_data)
        .mark_line(
            point=alt.OverlayMarkDef(filled=True, size=34, opacity=0.92),
            strokeWidth=1.9,
            opacity=0.9,
        )
        .encode(**base_encoding)
        .properties(height=540, width=1400)
    )
    actual_line = (
        alt.Chart(actual_data)
        .mark_line(
            point=alt.OverlayMarkDef(filled=True, size=60),
            strokeWidth=3.4,
        )
        .encode(**base_encoding)
        .properties(height=540, width=1400)
    )
    chart = forecast_lines + actual_line
    if not latest_actual_data.empty:
        latest_marker = (
            alt.Chart(latest_actual_data)
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
                opacity=alt.condition(disabled_series, alt.value(0.18), alt.value(1.0)),
            )
        )
        chart = chart + latest_marker
    if not boundary_data.empty:
        boundary_rule = (
            alt.Chart(boundary_data)
            .mark_rule(color=THEME_COLORS["text_muted"], opacity=0.52, strokeDash=[4, 4])
            .encode(x="date:T")
        )
        chart = chart + boundary_rule
    series_legend_base = alt.Chart(legend_data).encode(
        y=alt.Y("series_label:N", title=None, axis=None, sort=None),
        color=alt.Color(
            "series_label:N",
            title="価格・モデル",
            legend=None,
            scale=color_scale,
        ),
        opacity=alt.condition(disabled_series, alt.value(0.25), alt.value(1.0)),
        tooltip=[
            alt.Tooltip("series_label:N", title="価格・モデル"),
            alt.Tooltip("line_label:N", title="実績/予測"),
        ],
    )
    series_legend = series_legend_base.mark_point(filled=True, size=95).encode(
        x=alt.value(12)
    ) + series_legend_base.mark_text(align="left", baseline="middle", dx=16, fontSize=12).encode(
        x=alt.value(12),
        text="series_label:N",
    )
    line_type_legend_base = alt.Chart(line_type_legend_data).encode(
        y=alt.Y("description:N", title=None, axis=None, sort=None),
        strokeDash=alt.StrokeDash(
            "line_label:N",
            scale=alt.Scale(domain=["実績", "予測"], range=[[1, 0], [6, 4]]),
            legend=None,
        ),
    )
    line_type_legend = line_type_legend_base.mark_rule(
        color=THEME_COLORS["text_secondary"], strokeWidth=2
    ).encode(
        x=alt.value(12),
        x2=alt.value(46),
    ) + line_type_legend_base.mark_text(
        align="left",
        baseline="middle",
        dx=52,
        fontSize=12,
        color=THEME_COLORS["text_secondary"],
    ).encode(
        x=alt.value(12),
        text="description:N",
    )
    legend = alt.vconcat(
        series_legend.properties(title="価格・モデル", height=190, width=190),
        line_type_legend.properties(title="実績/予測", height=60, width=190),
        spacing=10,
    )
    combined_chart = (
        alt.hconcat(chart, legend, spacing=10)
        .add_params(disabled_series)
        .resolve_scale(color="shared")
        .configure(background=THEME_COLORS["bg_surface"])
        .configure_view(fill=THEME_COLORS["bg_card"], stroke=THEME_COLORS["border_strong"])
        .configure_axis(
            domainColor=THEME_COLORS["border_strong"],
            gridColor="rgba(148, 163, 184, 0.14)",
            labelColor=THEME_COLORS["text_caption"],
            titleColor=THEME_COLORS["text_label"],
            tickColor=THEME_COLORS["border_strong"],
        )
        .configure_title(color=THEME_COLORS["text_heading"], fontSize=13, anchor="start", offset=8)
        .properties(title=title or None)
    )
    st.altair_chart(
        combined_chart,
        use_container_width=True,
    )


def _render_provider_error_summary(rows: list[dict[str, str]]) -> None:
    if not rows:
        st.warning(
            "データ取得元から詳細なエラー情報が返りませんでした。設定、銘柄、取得期間を確認してください。"
        )
        return

    for row in provider_error_summary_rows(rows):
        st.warning(f"{row['コード']}: {row['内容']}")
        st.caption(row["次の確認"])

    with st.expander("診断情報", expanded=False):
        st.dataframe(
            provider_error_summary_rows(rows),
            hide_index=True,
            use_container_width=True,
        )
        for row in rows:
            details = format_provider_error_details(row)
            if details:
                st.code(details, language="json")


def provider_error_summary_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [_provider_error_summary_row(row) for row in rows]


def _provider_error_summary_row(row: dict[str, str]) -> dict[str, str]:
    details = _provider_error_details(row)
    request = _provider_error_request(details)
    provider = str(details.get("provider") or row.get("provider") or "")
    symbol = str(request.get("symbol") or row.get("symbol") or "")

    return {
        "コード": row.get("code", "ERROR"),
        "データ取得元": provider or "-",
        "銘柄コード": symbol or "-",
        "内容": row.get("message", "データ取得に失敗しました。"),
        "次の確認": _provider_error_next_action(provider, details, request),
    }


def _provider_error_details(row: dict[str, str]) -> dict[str, object]:
    details = row.get("details", "")
    if not details:
        return {}
    try:
        parsed = json.loads(details)
    except json.JSONDecodeError:
        return {"raw": details}
    if isinstance(parsed, dict):
        return parsed
    return {"raw": parsed}


def _provider_error_request(details: dict[str, object]) -> dict[str, object]:
    request = details.get("request")
    if isinstance(request, dict):
        return request
    return {}


def _provider_error_next_action(
    provider: str,
    details: dict[str, object],
    request: dict[str, object],
) -> str:
    request_error = str(request.get("error", ""))
    provider_label = provider or "外部データ取得元"

    if "curl: (28)" in request_error or "Resolving timed out" in request_error:
        return (
            f"{provider_label} への外部通信がタイムアウトしています。"
            "ネットワーク/DNS を確認し、時間をおいて再実行してください。"
            "ランキングでは銘柄数や取得期間を絞ると安定しやすくなります。"
        )
    if details.get("reason") == "no_ohlcv_rows":
        return (
            "価格データが返っていないため、ランキングから除外しています。"
            f"{provider_label} 側の提供状況、銘柄コード、取得期間を確認してください。"
        )
    if details.get("requires_external_opt_in") or provider in {"yahoo", "polygon"}:
        return (
            f"{provider_label} はライブ取得元です。"
            "銘柄コード、取得期間、Yahoo 側の提供状況を確認し、必要に応じて再実行してください。"
        )
    return "データ取得元の設定、銘柄、取得期間を確認して再実行してください。"


def format_provider_error_details(row: dict[str, str]) -> str:
    details = _provider_error_details(row)
    if not details:
        return ""
    return json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True)


def market_chart_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows).set_index("ts")
    frame.index = pd.to_datetime(frame.index).date
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def market_chart_long_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = market_chart_frame(rows).reset_index(names="date")
    long_frame = frame.melt(id_vars="date", var_name="series", value_name="value")
    long_frame = long_frame.dropna(subset=["value"])
    long_frame["line_type"] = long_frame["series"].map(
        lambda series: "actual" if series == "close" else "forecast"
    )
    long_frame["line_label"] = long_frame["line_type"].map(
        lambda line_type: "実績" if line_type == "actual" else "予測"
    )
    long_frame["series_label"] = long_frame["series"].map(_forecast_series_label)
    return long_frame


def forecast_chart_color_domain(series_labels: Iterable[str]) -> list[str]:
    labels = [label for label in dict.fromkeys(series_labels) if label]
    if FORECAST_ACTUAL_LABEL not in labels:
        return labels
    return [FORECAST_ACTUAL_LABEL, *(label for label in labels if label != FORECAST_ACTUAL_LABEL)]


def forecast_chart_color_range(domain: Sequence[str]) -> list[str]:
    colors: list[str] = []
    model_index = 0
    for label in domain:
        if label == FORECAST_ACTUAL_LABEL:
            colors.append(FORECAST_ACTUAL_PRICE_COLOR)
            continue
        colors.append(FORECAST_MODEL_COLORS[model_index % len(FORECAST_MODEL_COLORS)])
        model_index += 1
    return colors


def latest_actual_price_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = market_chart_frame(rows).reset_index(names="date")
    if "close" not in frame:
        return pd.DataFrame(columns=["date", "value", "series_label", "line_label", "marker_label"])
    actual_rows = frame.dropna(subset=["close"])
    if actual_rows.empty:
        return pd.DataFrame(columns=["date", "value", "series_label", "line_label", "marker_label"])
    latest = actual_rows[actual_rows["date"] == actual_rows["date"].max()].tail(1).copy()
    latest = latest.rename(columns={"close": "value"})
    latest["series_label"] = FORECAST_ACTUAL_LABEL
    latest["line_label"] = "実績"
    latest["marker_label"] = "現在価格"
    return latest[["date", "value", "series_label", "line_label", "marker_label"]]


def forecast_boundary_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = market_chart_frame(rows).reset_index(names="date")
    actual_rows = frame.dropna(subset=["close"])
    if actual_rows.empty:
        return pd.DataFrame(columns=["date"])
    latest_actual_date = actual_rows["date"].max()
    return pd.DataFrame([{"date": latest_actual_date}])


def forecast_metric_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "モデル": _forecast_series_label(row.get("model", "")),
            "銘柄": row.get("symbol", ""),
            "予測日数": row.get("horizon_days", ""),
            "予測終値": row.get("forecast_close", ""),
            "MAE(小さいほど良い)": row.get("mae", ""),
            "RMSE(小さいほど良い)": row.get("rmse", ""),
            "方向一致率(高いほど良い)": row.get("direction_accuracy", ""),
            "評価サンプル数": row.get("sample_count", ""),
        }
        for row in rows
    ]


def forecast_chart_summary(
    consensus_rows: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
) -> list[str]:
    if not consensus_rows:
        return ["予測を表示するには、もう少し価格データが必要です。"]

    row = consensus_rows[0]
    range_pct = row.get("forecast_range_pct") or "未計算"
    forecast_return = row.get("forecast_return_pct") or "未計算"
    model_count = row.get("model_count") or "0"
    messages = [
        (
            f"{model_count} つの予測モデルを表示しています。"
            f"平均予測の変化率は {forecast_return}、予測の開きは {range_pct} です。"
        ),
        "実線はこれまでの価格、点線はモデルごとの予測です。方向シグナルは深掘り候補を整理する補助材料です。",
    ]
    metric_messages = forecast_metric_summary(metric_rows)
    if metric_messages:
        messages.append(metric_messages[0])
    return messages


def forecast_consensus_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "銘柄": row.get("symbol", ""),
            "予測日数": row.get("horizon_days", ""),
            "モデル数": row.get("model_count", ""),
            "平均予測": row.get("ensemble_forecast_close", ""),
            "中央値予測": row.get("median_forecast_close", ""),
            "予測下限": row.get("min_forecast_close", ""),
            "予測上限": row.get("max_forecast_close", ""),
            "予測の開き": row.get("forecast_range", ""),
            "予測の開き(%)": row.get("forecast_range_pct", ""),
            "上昇気配": row.get("upside_signal_score", ""),
            "下降警戒": row.get("downside_signal_score", ""),
            "予測変化率": row.get("forecast_return_pct", ""),
            "方向一致": (
                f"上昇 {row.get('up_model_count', '0')} / "
                f"下降 {row.get('down_model_count', '0')} / "
                f"横ばい {row.get('flat_model_count', '0')}"
            ),
            "モデル一致度(補助)": _forecast_agreement_label(row.get("agreement", "")),
        }
        for row in rows
    ]


def _decimal_from_text(value: object) -> Decimal | None:
    text = str(value or "").replace("%", "").replace(",", "").strip()
    if not text or text in {
        "-",
        "N/A",
        "未接続",
        "未登録",
        "未取得",
        "取得不可",
        RANKING_ABNORMAL_DIVIDEND_DISPLAY,
    }:
        return None
    try:
        decimal_value = Decimal(text)
    except Exception:
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _ranking_inverse_score_display(value: object) -> str:
    decimal_value = _decimal_from_text(value)
    if decimal_value is None:
        return ""
    inverse = max(Decimal("0"), min(Decimal("100"), Decimal("100") - decimal_value))
    return f"{inverse.quantize(Decimal('0.1'))}".rstrip("0").rstrip(".")


def _ranking_symbol_detail_display(
    symbol_row: dict[str, str] | None,
    column: str,
) -> str:
    if symbol_row is None:
        return "未登録"
    return symbol_universe_detail_display_value(symbol_row, column)


def _ranking_numeric_display(value: object, *, suffix: str = "") -> str:
    decimal_value = _decimal_from_text(value)
    if decimal_value is None:
        text = str(value or "").strip()
        if text and text not in {"-", "未登録", "未取得", "取得不可", "未計算"}:
            return text
        return RANKING_MISSING_DISPLAY
    text = f"{decimal_value:.2f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def _ranking_dividend_yield_display(value: object) -> str:
    if ranking_dividend_yield_pct_is_abnormal(value):
        return RANKING_ABNORMAL_DIVIDEND_DISPLAY
    return _ranking_numeric_display(value, suffix="%")


def _ranking_fundamental_metric_display(field: str, value: object, *, suffix: str = "") -> str:
    if ranking_fundamental_metric_is_abnormal(field, value):
        return RANKING_ABNORMAL_DIVIDEND_DISPLAY
    return _ranking_numeric_display(value, suffix=suffix)


def _ranking_row_or_symbol_metric_display(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
    column: str,
    *,
    suffix: str = "",
) -> str:
    raw_value = str(row.get(column, "")).strip()
    if column == "dividend_yield_pct":
        if raw_value:
            return _ranking_dividend_yield_display(raw_value)
        if symbol_row is not None:
            return _ranking_dividend_yield_display(_symbol_detail_raw_value(symbol_row, column))
        return RANKING_MISSING_DISPLAY
    if column in {"per", "pbr", "roe_pct"}:
        if raw_value:
            return _ranking_fundamental_metric_display(column, raw_value, suffix=suffix)
        if symbol_row is not None:
            return _ranking_fundamental_metric_display(
                column,
                _symbol_detail_raw_value(symbol_row, column),
                suffix=suffix,
            )
        return RANKING_MISSING_DISPLAY
    if raw_value:
        return _ranking_numeric_display(raw_value, suffix=suffix)
    if symbol_row is not None:
        return _ranking_numeric_display(_symbol_detail_raw_value(symbol_row, column), suffix=suffix)
    return RANKING_MISSING_DISPLAY


def _ranking_optional_display(value: object) -> str:
    text = str(value or "").strip()
    if not text or text in {"-", "未登録", "未取得", "取得不可", "未計算"}:
        return RANKING_MISSING_DISPLAY
    return text


def ranking_investment_note(
    row: dict[str, str],
    symbol_rows_by_symbol: dict[str, dict[str, str]] | None = None,
) -> str:
    symbol = row.get("symbol", "")
    symbol_row = (
        symbol_rows_by_symbol.get(symbol.strip().upper())
        if symbol_rows_by_symbol is not None
        else _symbol_universe_row_for_symbol(symbol)
    )
    strengths = _ranking_strength_phrases(row, symbol_row)
    caution = _ranking_primary_caution(row, symbol_row)
    action = _ranking_next_action(row, symbol_row)
    strength_text = "と".join(strengths[:2]) if strengths else "総合点"
    if caution:
        return f"{strength_text}が強みの候補で、{caution}ため、{action}。"
    return f"{strength_text}が強みの候補です。{action}。"


def _ranking_strength_phrases(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
) -> list[str]:
    strengths: list[str] = []
    if (_decimal_from_text(row.get("upside_signal_score")) or Decimal("0")) >= Decimal("75"):
        strengths.append("上昇気配")
    if (_decimal_from_text(row.get("data_quality_score")) or Decimal("0")) >= Decimal("90"):
        strengths.append("データ品質")
    if (_decimal_from_text(row.get("database_fit_score")) or Decimal("0")) >= Decimal("75"):
        strengths.append("条件適合度")
    if (_decimal_from_text(row.get("screening_score")) or Decimal("0")) >= Decimal("80"):
        strengths.append("スクリーニング")
    if (_decimal_from_text(row.get("risk_signal_score")) or Decimal("0")) >= Decimal("70"):
        strengths.append("リスク確認")
    roe = (
        ranking_fundamental_metric_value("roe_pct", symbol_row.get("roe_pct"))
        if symbol_row
        else None
    )
    if roe is not None and roe >= Decimal("20"):
        strengths.append("ROE")
    dividend_yield = (
        ranking_dividend_yield_pct_value(symbol_row.get("dividend_yield_pct"))
        if symbol_row
        else None
    )
    if dividend_yield is not None and dividend_yield >= Decimal("3"):
        strengths.append("配当利回り")
    return strengths


def _ranking_primary_caution(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
) -> str:
    warning = _investment_warning_label(row.get("warnings", ""))
    if warning:
        return f"{warning}がある"
    if (_decimal_from_text(row.get("downside_signal_score")) or Decimal("0")) >= Decimal("75"):
        return "下降警戒が強い"
    if (_decimal_from_text(row.get("downside_signal_score")) or Decimal("0")) >= Decimal("65"):
        return "下向きシグナルを確認したい"
    if (_decimal_from_text(row.get("risk_signal_score")) or Decimal("100")) < Decimal("50"):
        return "値動きや下落耐性の確認が必要な"
    if (_decimal_from_text(row.get("data_quality_score")) or Decimal("100")) < Decimal("80"):
        return "データ品質に確認余地がある"
    if symbol_row is None:
        return "銘柄マスタの補足情報が少ない"
    per = ranking_fundamental_metric_value("per", symbol_row.get("per"))
    pbr = ranking_fundamental_metric_value("pbr", symbol_row.get("pbr"))
    if (per is not None and per >= Decimal("40")) or (pbr is not None and pbr >= Decimal("10")):
        return "PER/PBRが高めな"
    dividend_yield = ranking_dividend_yield_pct_value(symbol_row.get("dividend_yield_pct"))
    if dividend_yield is not None and dividend_yield >= Decimal("5"):
        return "高配当の持続性を確認したい"
    if symbol_row.get("asset_type") == "etf" and (
        _decimal_from_text(symbol_row.get("expense_ratio_pct")) or Decimal("0")
    ) >= Decimal("0.5"):
        return "経費率が相対的に高めな"
    return ""


def _ranking_next_action(
    row: dict[str, str],
    symbol_row: dict[str, str] | None,
) -> str:
    if symbol_row and symbol_row.get("asset_type") == "etf":
        return "連動指数、経費率、分配方針を銘柄データで確認してください"
    if (_decimal_from_text(row.get("downside_signal_score")) or Decimal("0")) >= Decimal("65"):
        return "下降警戒と直近トレンドを銘柄コックピットで確認してください"
    if (_decimal_from_text(row.get("risk_signal_score")) or Decimal("100")) < Decimal("50"):
        return "ポジションサイズと損切り条件を先に確認してください"
    per = ranking_fundamental_metric_value("per", symbol_row.get("per")) if symbol_row else None
    pbr = ranking_fundamental_metric_value("pbr", symbol_row.get("pbr")) if symbol_row else None
    if symbol_row and (
        (per is not None and per >= Decimal("40")) or (pbr is not None and pbr >= Decimal("10"))
    ):
        return "成長期待の裏付けと決算材料を確認してください"
    dividend_yield = (
        ranking_dividend_yield_pct_value(symbol_row.get("dividend_yield_pct"))
        if symbol_row
        else None
    )
    if dividend_yield is not None and dividend_yield >= Decimal("3"):
        return "配当性向、減配リスク、業績安定性を確認してください"
    return "銘柄データとコックピットで価格トレンドを確認してください"


def _ranking_caution_sentence(caution: str) -> str:
    if not caution:
        return ""
    if caution.endswith("な"):
        return f"{caution[:-1]}です。"
    if caution.endswith("ある"):
        return f"{caution}ため、詳細確認が必要です。"
    return caution


def ranking_investment_detail_rows(
    ranking_row: dict[str, str],
    symbol_row: dict[str, str],
) -> list[dict[str, str]]:
    note = ranking_row.get("補足", "")
    warning = ranking_row.get("注意点", "")
    score_summary = (
        f"総合{ranking_row.get('総合スコア', '未計算')} / "
        f"上昇{ranking_row.get('上昇気配', '未計算')} / "
        f"下降警戒{ranking_row.get('下降警戒', '未計算')} / "
        f"品質{ranking_row.get('データ品質', '未計算')} / "
        f"リスク確認{ranking_row.get('Risk', '未接続')}"
    )
    valuation = (
        f"PER {symbol_universe_detail_display_value(symbol_row, 'per')}、"
        f"PBR {symbol_universe_detail_display_value(symbol_row, 'pbr')}、"
        f"ROE {symbol_universe_detail_display_value(symbol_row, 'roe_pct')}"
    )
    income = (
        f"配当利回り {symbol_universe_detail_display_value(symbol_row, 'dividend_yield_pct')}、"
        f"分類 {symbol_universe_detail_display_value(symbol_row, 'dividend_category')}"
    )
    caution = warning or _ranking_caution_sentence(_ranking_primary_caution({}, symbol_row))
    rows = [
        {
            "観点": "ランキング上位理由",
            "内容": note or "今回の条件で相対的に上位に入りました。",
            "確認ポイント": score_summary,
        },
        {
            "観点": "主な注意点",
            "内容": caution or "大きな警告はありません。",
            "確認ポイント": _ranking_next_action({}, symbol_row),
        },
        {
            "観点": "バリュエーション",
            "内容": valuation,
            "確認ポイント": "高PER/PBRなら成長期待の裏付け、低PBRなら低評価の理由を確認します。",
        },
        {
            "観点": "インカム",
            "内容": income,
            "確認ポイント": "高配当は利回りだけでなく、配当性向・減配リスク・業績安定性を確認します。",
        },
        *ranking_score_detail_rows(ranking_row),
        {
            "観点": "次の行動",
            "内容": _ranking_next_action(ranking_row, symbol_row),
            "確認ポイント": "売買推奨ではなく、深掘り順と確認観点の整理です。",
        },
    ]
    return rows


def ranking_score_detail_rows(ranking_row: dict[str, str]) -> list[dict[str, str]]:
    score_parts = [
        f"総合スコア {ranking_row.get('総合スコア', RANKING_MISSING_DISPLAY)}",
        f"見方 {ranking_row.get('見方', RANKING_MISSING_DISPLAY)}",
    ]
    component_parts = [
        f"スクリーニング {ranking_row.get('Screening', RANKING_MISSING_DISPLAY)}",
        f"上昇気配 {ranking_row.get('上昇気配', RANKING_MISSING_DISPLAY)}",
        f"下降警戒 {ranking_row.get('下降警戒', RANKING_MISSING_DISPLAY)}",
        f"リスク確認 {ranking_row.get('Risk', RANKING_MISSING_DISPLAY)}",
        f"データ品質 {ranking_row.get('データ品質', RANKING_MISSING_DISPLAY)}",
    ]
    fundamental_parts = [
        f"配当利回り {ranking_row.get('配当利回り', RANKING_MISSING_DISPLAY)}",
        f"PER {ranking_row.get('PER', RANKING_MISSING_DISPLAY)}",
        f"PBR {ranking_row.get('PBR', RANKING_MISSING_DISPLAY)}",
        f"ROE {ranking_row.get('ROE', RANKING_MISSING_DISPLAY)}",
    ]
    fetched_parts = [
        f"現在値 {ranking_row.get('現在値', RANKING_MISSING_DISPLAY)}",
        f"時価総額 {ranking_row.get('時価総額', RANKING_MISSING_DISPLAY)}",
        f"出来高 {ranking_row.get('出来高', RANKING_MISSING_DISPLAY)}",
        f"ボラティリティ {ranking_row.get('ボラティリティ', RANKING_MISSING_DISPLAY)}",
    ]
    missing_items = ranking_row.get("欠損項目", RANKING_MISSING_DISPLAY)
    return [
        {
            "観点": "総合スコア",
            "内容": " / ".join(score_parts),
            "確認ポイント": "複数材料を統合した比較用スコアです。単独で売買判断には使いません。",
        },
        {
            "観点": "スコア内訳",
            "内容": " / ".join(component_parts),
            "確認ポイント": "どの観点が順位に効いているかを確認します。",
        },
        {
            "観点": "基礎指標",
            "内容": " / ".join(fundamental_parts),
            "確認ポイント": "未取得の値は0ではなくN/Aとして扱い、スコアは参考値として確認します。",
        },
        {
            "観点": "取得データ",
            "内容": " / ".join(fetched_parts),
            "確認ポイント": (
                f"取得元 {ranking_row.get('取得元', RANKING_MISSING_DISPLAY)} / "
                f"更新 {ranking_row.get('取得日時', RANKING_MISSING_DISPLAY)} / "
                f"欠損 {missing_items or RANKING_MISSING_DISPLAY}"
            ),
        },
    ]


def investment_score_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    symbol_rows_by_symbol = _symbol_universe_rows_by_symbol()
    display_rows: list[dict[str, str]] = []
    for row in rows:
        symbol = row.get("symbol", "")
        symbol_row = symbol_rows_by_symbol.get(symbol.strip().upper())
        display_rows.append(
            {
                "順位": row.get("rank", ""),
                "銘柄": symbol,
                "銘柄名": symbol_name(symbol) or "",
                "総合スコア": row.get("total_score", ""),
                "見方": _investment_score_band_label(row.get("score_band", "")),
                "条件適合度": row.get("database_fit_score", ""),
                "Screening": row.get("screening_score", ""),
                "上昇気配": row.get("upside_signal_score", ""),
                "下降警戒": row.get("downside_signal_score", ""),
                "予測変化率": row.get("forecast_return_pct", ""),
                "方向一致": (
                    f"上昇 {row.get('up_model_count', '0')} / "
                    f"下降 {row.get('down_model_count', '0')} / "
                    f"横ばい {row.get('flat_model_count', '0')}"
                ),
                "モデル一致度": row.get("forecast_agreement_score", ""),
                "データ品質": row.get("data_quality_score", ""),
                "DB信頼度": row.get("metadata_confidence_score", ""),
                "Risk": row.get("risk_signal_score", "") or "未接続",
                "注意点": _investment_warning_label(row.get("warnings", "")),
                "補足": ranking_investment_note(row, symbol_rows_by_symbol),
                "PER": _ranking_row_or_symbol_metric_display(row, symbol_row, "per"),
                "PBR": _ranking_row_or_symbol_metric_display(row, symbol_row, "pbr"),
                "ROE": _ranking_row_or_symbol_metric_display(
                    row,
                    symbol_row,
                    "roe_pct",
                    suffix="%",
                ),
                "配当利回り": _ranking_row_or_symbol_metric_display(
                    row,
                    symbol_row,
                    "dividend_yield_pct",
                    suffix="%",
                ),
                "経費率": _ranking_symbol_detail_display(symbol_row, "expense_ratio_pct"),
                "NISA": symbol_universe_nisa_display(symbol_row) if symbol_row else "未登録",
                "投資スタイル": _ranking_symbol_detail_display(
                    symbol_row,
                    "investment_style",
                ),
                "現在値": _ranking_optional_display(row.get("current_price", "")),
                "時価総額": _ranking_optional_display(
                    row.get("market_cap", "")
                    or (
                        _ranking_symbol_detail_display(symbol_row, "market_cap_tier")
                        if symbol_row
                        else ""
                    )
                ),
                "出来高": _ranking_optional_display(row.get("volume", "")),
                "ボラティリティ": _ranking_optional_display(row.get("volatility", "")),
                "自己資本比率": _ranking_optional_display(row.get("equity_ratio", "")),
                "営業利益率": _ranking_optional_display(row.get("operating_margin", "")),
                "売上成長率": _ranking_optional_display(row.get("revenue_growth", "")),
                "取得日時": _ranking_optional_display(row.get("data_as_of", "")),
                "取得元": _ranking_optional_display(row.get("data_provider", "")),
                "欠損項目": _ranking_optional_display(row.get("missing_items", "")),
                "連動指数": _ranking_symbol_detail_display(symbol_row, "benchmark_index"),
                "通貨": _ranking_symbol_detail_display(symbol_row, "currency"),
                "複雑性": _ranking_symbol_detail_display(symbol_row, "complexity"),
            }
        )
    return display_rows


def forecast_metric_summary(rows: list[dict[str, str]]) -> list[str]:
    candidates: list[tuple[Decimal, dict[str, str]]] = []
    for row in rows:
        rmse = _optional_decimal_from_text(row.get("rmse", ""))
        sample_count = _int_from_text(row.get("sample_count", ""))
        if rmse is None or sample_count <= 0:
            continue
        candidates.append((rmse, row))

    if not candidates:
        return [
            "予測評価に必要なサンプルがまだ不足しています。日付範囲を広げるとモデル比較が安定します。"
        ]

    best_rmse, best_row = min(candidates, key=lambda item: item[0])
    best_label = _forecast_series_label(best_row.get("model", ""))
    direction = best_row.get("direction_accuracy") or "未計算"
    return [
        (
            f"今回の比較では「{best_label}」が RMSE {best_rmse} で最も誤差が小さいです。"
            f"方向一致率は {direction} です。"
        ),
        "誤差と方向一致率で、モデルの当たりやすさを比べます。",
    ]


def _forecast_series_label(series: str) -> str:
    if series == "close":
        return FORECAST_ACTUAL_LABEL
    return forecast_model_display_name(series)


def _forecast_agreement_label(value: str) -> str:
    labels = {
        "HIGH": "高い",
        "MEDIUM": "中くらい",
        "LOW": "低い",
        "UNKNOWN": "未判定",
    }
    return labels.get(value, value)


def _investment_score_band_label(value: str) -> str:
    labels = {
        "STRONG": "強め",
        "BALANCED": "バランス型",
        "CAUTION": "注意して確認",
        "REVIEW": "要確認",
    }
    return labels.get(value, value)


def _investment_warning_label(value: str) -> str:
    if not value:
        return ""
    labels = {
        "data_quality:warn": "データ品質に注意",
        "data_quality:block": "データ不足が大きい",
        "model_disagreement:high": "モデルの見方が割れています",
        "model_count:insufficient": "予測モデル数が少なめです",
    }
    return ", ".join(labels.get(item.strip(), item.strip()) for item in value.split(","))


def _int_from_text(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _metadata_value(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        if row.get("field") == field:
            return row.get("value", "")
    return ""


def _market_data_as_of(preview: MarketDataPreview) -> str:
    if preview.bars:
        return preview.bars[-1].ts.date().isoformat()
    for row in preview.ohlcv_rows:
        last_ts = row.get("last_ts", "")
        if last_ts:
            return last_ts[:10]
    for row in preview.quote_rows:
        ts = row.get("ts", "")
        if ts:
            return ts[:10]
    return ""


def _market_data_preview_symbol_label(preview: MarketDataPreview) -> str:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return "selected symbol"
    name = symbol_name(symbol)
    if name:
        return f"{symbol} - {name}"
    return symbol


def _market_data_preview_symbol(preview: MarketDataPreview) -> str:
    if preview.bars:
        return preview.bars[0].symbol.raw
    for rows in (
        getattr(preview, "investment_score_rows", []),
        preview.screening_rows,
        preview.ohlcv_rows,
        preview.quote_rows,
        preview.feature_rows,
    ):
        for row in rows:
            symbol = row.get("symbol", "").strip()
            if symbol:
                return symbol
    return ""


def _render_target_symbol_caption(symbol_label: str) -> None:
    st.caption(f"対象: {symbol_label}")


if __name__ == "__main__":
    main()
