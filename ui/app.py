from __future__ import annotations

import asyncio
import gc
import hashlib
import html
import importlib
import inspect
import json
import logging
import math
import os
import re
import time as perf_time
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import (
    Any,
    Callable,
    Collection,
    Iterable,
    Literal,
    Mapping,
    MutableMapping,
    Protocol,
    Sequence,
    cast,
)
from uuid import uuid4

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from st_aggrid import AgGrid, DataReturnMode, JsCode
from zoneinfo import ZoneInfo

import backend.news.radar_market as _radar_market_module
import ui.styles as _ui_styles_module
from backend.core.config import get_settings, resolve_performance_profile
from backend.core.data_contracts import (
    Bar,
    DailySnapshot,
    DataQuality,
    FeatureSnapshot,
    FundamentalSnapshot,
    Quote,
)
from backend.core.errors import AppError, DataSourceError, ProviderTimeoutError
from backend.forecast import determine_forecast_horizon, forecast_model_display_name
from backend.forecast.batch import evaluate_advanced_forecasts_for_symbol
from backend.interpretation import (
    CockpitInterpretationResult,
    CockpitInterpretationServiceResult,
    InterpretationBullet,
    build_cockpit_interpretation_context,
    build_cockpit_interpretation_from_settings,
)
from backend.llm_factor import (
    LLM_FACTOR_FAKE_MODEL_NAME,
    EvidenceSource,
    LLMFactorCacheMetadata,
    LLMFactorRankingReference,
    LLMFactorResult,
    LLMFactorServiceResult,
    LLMFactorSourceType,
    build_llm_factor_reference_result_from_settings,
    build_llm_factor_references_for_ranking_items,
    llm_factor_ranking_candidate_key,
)
from backend.marketdata import create_market_data_provider_adapter
from backend.marketdata.feature_builder import build_daily_snapshots_from_market_data
from backend.news import RadarCandidate
from backend.news.background import start_news_background_refresh_worker

# A long-running Streamlit process can retain the first Radar market module
# revision across rolling updates. Reload only that stale revision before any
# view imports bind its contracts and builder.
if (
    getattr(_radar_market_module, "SMAI_RADAR_MARKET_REVISION", "")
    != "2026-07-15-dynamic-density-v3"
):
    importlib.reload(_radar_market_module)

from backend.news.radar_market import (
    RadarMarketSnapshot,
    build_radar_market_snapshot,
    radar_market_candidates,
)
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
from backend.scoring.reversal import calculate_reversal_expectation
from backend.screening import ScreeningService
from backend.server_ops import maintenance as maintenance_module
from backend.server_ops.maintenance import (
    classify_client_type,
    maintenance_operation,
)
from backend.symbols.background import (
    request_symbol_background_refresh,
    start_symbol_background_refresh_worker,
)
from backend.symbols.cache_sync import sync_symbol_cache_to_official_metrics
from backend.symbols.contracts import SymbolStartupRefreshSummary
from backend.symbols.startup import run_symbol_database_target_refresh
from ui.cockpit_filter_policy import (
    MARKET_DATA_COCKPIT_FILTER_DEFAULTS,
    cockpit_detail_filters_for_category,
    cockpit_filter_has_active_conditions_from_values,
    cockpit_filtered_symbol_rows_from_values,
    cockpit_keyword_filtered_symbol_rows,
    cockpit_symbol_search_rank,
)
from ui.components.assistant import (
    SmaiAssistantContext,
    register_assistant_context,
    render_floating_assistant,
    reset_assistant_contexts,
)
from ui.components.downloads import render_csv_download_button
from ui.components.mascot import (
    render_app_header,
    render_mascot_loading,
    render_mascot_panel,
    render_page_title,
    smai_insight_html,
    workflow_loading_headlines_from_cache,
    workflow_loading_html,
)
from ui.components.sidemenu import (
    SIDEMENU_PAGE_COCKPIT,
    SIDEMENU_PAGE_COPILOT,
    SIDEMENU_PAGE_LABELS,
    SIDEMENU_PAGE_NEWS,
    SIDEMENU_PAGE_RANKING,
    SIDEMENU_PAGE_REBALANCE,
    SIDEMENU_PAGE_SETTINGS,
    SIDEMENU_PAGE_WATCHLIST,
    SIDEMENU_STATE_KEY,
    render_sidemenu,
)
from ui.content.common_texts import (
    DECISION_REPORT_DOWNLOAD_GUIDE,
    DECISION_REPORT_JSON_DOWNLOAD_HELP,
    DECISION_REPORT_JSON_DOWNLOAD_LABEL,
    DECISION_REPORT_MANIFEST_DOWNLOAD_HELP,
    DECISION_REPORT_MANIFEST_DOWNLOAD_LABEL,
    DECISION_REPORT_MARKDOWN_DOWNLOAD_HELP,
    DECISION_REPORT_MARKDOWN_DOWNLOAD_LABEL,
    DECISION_REPORT_SUPPORT_MESSAGE,
    DECISION_REPORT_ZIP_DOWNLOAD_HELP,
    DECISION_REPORT_ZIP_DOWNLOAD_LABEL,
    EMPTY_STATE_MESSAGES,
    FORECAST_ACTUAL_LABEL,
    MARKET_DATA_PERIOD_CUSTOM,
    MARKET_DATA_PERIOD_HELP_TEXT,
    MARKET_DATA_PERIOD_PRESETS,
    NO_SYMBOL_CANDIDATE_LABEL,
    user_facing_table_rows,
)
from ui.content.research_texts import (
    RESEARCH_ADVANCED_DETAIL_EXPANDER_LABEL,
    RESEARCH_AI_READING_MEMO_TITLE,
    RESEARCH_COCKPIT_INTRO,
    RESEARCH_COCKPIT_SECTION_TITLE,
    RESEARCH_COMPANY_RESEARCH_TITLE,
    RESEARCH_DETAIL_EXPANDER_LABEL,
    RESEARCH_DOCUMENTS_OR_CHUNKS_MISSING,
    RESEARCH_EVIDENCE_CHECK_FALLBACK,
    RESEARCH_FETCH_BUTTON_LABEL,
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
    RESEARCH_QUANTITATIVE_SUMMARY_TITLE,
    RESEARCH_RANKING_FETCH_BUTTON_LABEL,
    RESEARCH_RANKING_LOOKUP_INTRO,
    RESEARCH_RANKING_LOOKUP_TITLE,
    RESEARCH_REGISTERED_EVIDENCE_NOTE,
    RESEARCH_RETRIEVAL_DOCUMENT_LABEL,
    RESEARCH_RETRIEVAL_EVIDENCE_LABEL,
    RESEARCH_RETRIEVAL_FALLBACK_NOTE,
    RESEARCH_RETRIEVAL_MODE_HYBRID,
    RESEARCH_RETRIEVAL_MODE_KEYWORD,
    RESEARCH_RETRIEVAL_MODE_LABEL,
    RESEARCH_RETRIEVAL_MODE_VECTOR,
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
from ui.favorites import (
    FAVORITE_DECISION_STATUS_OPTIONS,
    FavoriteStock,
    build_favorite_radar_items,
    evaluate_favorite_refresh_status,
    load_favorites,
    normalize_favorite_symbol,
    remove_favorite,
    render_favorite_button,
    toggle_favorite,
    update_favorite_decision_note,
    update_favorite_refresh_metadata,
)
from ui.last_session import (
    CLIENT_ID_STATE_KEY,
    RESTORE_NOTICE_KEY,
    save_client_session_if_changed,
)
from ui.notification_center import render_user_notification_area
from ui.pwa import inject_pwa_head_metadata
from ui.ranking import (
    LIVE_MARKET_DATA_PROVIDERS,
    MAX_RANKING_BUILD_CACHE_ENTRIES,
    MAX_RANKING_CONCURRENT_FETCHES,
    RANKING_BETA_RISK_LABELS,
    RANKING_COMPLEXITY_LABELS,
    RANKING_CRITERIA_GUIDE_ROWS,
    RANKING_CURRENCY_LABELS,
    RANKING_DEFAULT_PERIOD_PRESET,
    RANKING_DIVIDEND_LABELS,
    RANKING_FETCH_LIMIT_BALANCED,
    RANKING_FETCH_LIMIT_LABELS,
    RANKING_FETCH_LIMIT_PRESET,
    RANKING_FILTER_DEFAULTS,
    RANKING_FILTER_HELP_TEXTS,
    RANKING_INDEX_FAMILY_LABELS,
    RANKING_INVESTMENT_THEME_LABELS,
    RANKING_MARKET_CAP_LABELS,
    RANKING_METRIC_FILTER_DEFAULTS,
    RANKING_MVP_PRODUCT_TYPE_LABELS,
    RANKING_MVP_REGION_LABELS,
    RANKING_NISA_ELIGIBILITY_LABELS,
    RANKING_OFFICIAL_SECTOR_LABELS,
    RANKING_PERIOD_PRESETS,
    RANKING_PRODUCT_ALL,
    RANKING_PRODUCT_ETF,
    RANKING_PRODUCT_MUTUAL_FUND,
    RANKING_PRODUCT_STOCK,
    RANKING_PURPOSE_MULTI_FACTOR,
    RANKING_PURPOSE_REVERSAL_EXPECTATION,
    RANKING_THEME_LABELS,
    apply_ranking_weight_preset,
    filter_symbol_universe_rows,
    limited_ranking_selected_labels,
    normalize_dividend_filter_values,
    rank_investment_score_rows,
    ranking_build_cache_key,
    ranking_deep_dive_default_symbol,
    ranking_deep_dive_symbol_options,
    ranking_detail_filters_for_category,
    ranking_dividend_yield_pct_is_abnormal,
    ranking_dividend_yield_pct_value,
    ranking_fetch_limit_label,
    ranking_fetch_limit_value,
    ranking_filter_signature,
    ranking_fundamental_metric_is_abnormal,
    ranking_fundamental_metric_value,
    ranking_insufficient_bars_error_row,
    ranking_no_bars_error_row,
    ranking_period_dates,
    ranking_period_label,
    ranking_policy_description,
    ranking_policy_for_purpose,
    ranking_policy_label,
    ranking_policy_options,
    ranking_product_type_label,
    ranking_provider_error_rows,
    ranking_purpose_context_cards,
    ranking_purpose_focus_summary,
    ranking_purpose_label,
    ranking_purpose_primary_columns,
    ranking_region_label,
    ranking_symbol_chunks,
    ranking_symbols_state_key,
    ranking_weight_group_rows,
    ranking_weight_preset_for_purpose,
    ranking_weight_preset_label,
    symbol_candidate_labels,
    symbol_universe_filter_value_counts,
    symbol_universe_rows,
)
from ui.ranking_filter_chips import (
    applied_exploration_filters,
    apply_ranking_applied_exploration_filters,
    ranking_filter_dialog_is_open,
    render_active_ranking_filter_dialog,
    render_ranking_exploration_filter_cards,
    sync_ranking_exploration_legacy_state,
)
from ui.ranking_filter_chips import (
    exploration_filter_chip_labels as ranking_exploration_filter_chip_labels,
)
from ui.ranking_history import (
    RANKING_HISTORY_NOTICE_KEY,
    RANKING_HISTORY_VIEW_KEY,
    apply_ranking_history_open_query,
    build_ranking_history_save_request,
    prepare_ranking_history_view_for_page,
    render_ranking_history_detail,
    render_ranking_history_list,
    save_ranking_history_for_current_user,
    synchronize_ranking_history_user,
)
from ui.ranking_jobs import (
    RankingProgressCallback as BackgroundRankingProgressCallback,
)
from ui.ranking_jobs import get_ranking_job, ranking_job_is_running, start_ranking_job
from ui.ranking_policy_presenter import (
    ranking_condition_summary_chips_html,
    ranking_creation_target_summary_html,
    ranking_policy_builder_card_html,
    reversal_expectation_cap_rows,
    reversal_expectation_component_rows,
    reversal_expectation_pullback_rows,
)
from ui.ranking_presenter import (
    compact_confidence_summary as _ranking_compact_confidence_summary,
)
from ui.ranking_presenter import full_confirmation_note as _ranking_full_confirmation_note
from ui.ranking_state import (
    current_ranking_filter_state,
    ensure_ranking_selection_widget_state,
    persist_ranking_filter_state,
    ranking_filter_summary,
    sync_ranking_selection_state,
)
from ui.ranking_state import (
    ranking_filter_bool as _ranking_filter_bool,
)
from ui.ranking_state import (
    ranking_filter_value as _ranking_filter_value,
)
from ui.ranking_table import RankingTableConfig, build_ranking_aggrid_options
from ui.rebalance_app import (
    MarketDataPreview,
    _available_forecast_evaluations,
    advanced_forecast_consensus_rows_for_results,
    advanced_forecast_results_for_bars,
    advanced_forecast_rows_for_results,
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
from ui.server_ops_device import device_id_from_query, device_identity_bridge_html
from ui.state import (
    MARKET_DATA_EXTERNAL_RESEARCH_FETCH_STATE_KEY,
    MARKET_DATA_FORECAST_DAYS_STATE_KEY,
    MARKET_DATA_PREVIEW_STATE_KEY,
    MARKET_DATA_RANKING_DEEP_DIVE_SOURCE_STATE_KEY,
    MARKET_DATA_RANKING_ERROR_STATE_KEY,
    MARKET_DATA_RANKING_FILTERS_STATE_KEY,
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
from ui.symbol_universe import (
    SYMBOL_CACHE_FRESHNESS_STATUS_FIELD,
    SYMBOL_CACHE_LAST_FUNDAMENTAL_UPDATED_AT_FIELD,
    SYMBOL_CACHE_LAST_PRICE_UPDATED_AT_FIELD,
    SYMBOL_CACHE_PROVIDER_FIELD,
    SYMBOL_CACHE_UPDATED_AT_FIELD,
    symbol_provider_symbol,
    symbol_universe_csv_rows,
    symbol_universe_runtime_rows,
)
from ui.upward_signal import upward_signal_display_label
from ui.views.cockpit import (
    cockpit_direction_signal_detail_rows,
    cockpit_direction_signal_summary,
    cockpit_kpi_cards,
    cockpit_summary_items,
    render_cockpit_kpi_cards,
    render_cockpit_summary_header,
)
from ui.views.common import (
    _optional_decimal_from_text,
    _render_table,
    _single_date_from_input,
    default_as_of_date,
)
from ui.views.copilot import render_copilot_workspace_page
from ui.views.news import (
    NEWS_COCKPIT_QUERY_COCKPIT_VALUE,
    NEWS_COCKPIT_QUERY_PAGE_PARAM,
    NEWS_COCKPIT_QUERY_SYMBOL_PARAM,
    render_news_dashboard_page,
)
from ui.views.ranking_chart_profiles import (
    PROFILE_REVERSAL_EXPECTATION,
    RankingChartProfile,
    chart_profile_for_purpose,
    ranking_chart_frame,
    ranking_reversal_evidence_frame,
)
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
from ui.watchlist_groups import render_grouped_watchlist, render_watchlist_group_toolbar
from ui.watchlist_snapshots import (
    WatchlistSnapshot,
    build_watchlist_snapshot_for_symbol,
    load_watchlist_snapshots,
    mark_watchlist_snapshot_failed,
    prune_snapshots_for_removed_favorites,
    save_watchlist_snapshots,
)

# Streamlit reloads the page script without necessarily reloading imported
# modules. Refresh a stale style module once so a rolling Radar update cannot
# leave the new heatmap markup without its matching responsive CSS. Existing
# imported functions retain the module dictionary that reload updates.
if getattr(_ui_styles_module, "SMAI_STYLE_REVISION", "") != "2026-07-16-radar-market-v7":
    importlib.reload(_ui_styles_module)

LOGGER = logging.getLogger(__name__)

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


class _StreamlitEmptyContainer(Protocol):
    def empty(self) -> Any: ...


MARKET_DATA_PROVIDER_OPTIONS = ["yahoo", "csv", "mock"]
MARKET_DATA_PROVIDER_WIDGET_KEY = "market_data_provider_live_first"
MARKET_DATA_RANKING_PROVIDER_WIDGET_KEY = "market_data_ranking_provider_live_first"
MARKET_CHART_DISPLAY_CURRENCY_STATE_KEY = "market_chart_display_currency"
RANKING_BUILD_CACHE_VERSION = "signal-v5"
RANKING_PIPELINE_COHORT_SIZE = 100
RANKING_ADVANCED_FORECAST_CANDIDATE_LIMIT = 25
RANKING_CLIENT_SESSION_TOUCH_STATE_KEY = "market_data_ranking_client_session_touched_at"
RANKING_CLIENT_SESSION_TOUCH_INTERVAL_SECONDS = 300.0
RANKING_JOB_ADOPTED_STATE_KEY = "market_data_ranking_background_job_adopted"
RANKING_JOB_HISTORY_PENDING_STATE_KEY = "market_data_ranking_background_job_history_pending"
RANKING_FUNDAMENTAL_CONCURRENCY = 4
RANKING_FUNDAMENTAL_TIMEOUT_SECONDS = 15.0
RANKING_ADVANCED_FORECAST_MAX_WORKERS = 4
MAX_RANKING_OHLCV_CACHE_SYMBOLS = 500
MAX_RANKING_FUNDAMENTAL_CACHE_SYMBOLS = 1_000
MAX_RANKING_ADVANCED_FORECAST_CACHE_SYMBOLS = 2_000
RANKING_OHLCV_CACHE_TTL_SECONDS = 6 * 60 * 60
RANKING_FUNDAMENTAL_CACHE_TTL_SECONDS = 24 * 60 * 60
RANKING_ADVANCED_FORECAST_CACHE_TTL_SECONDS = 6 * 60 * 60
RANKING_BUILD_CACHE_TTL_SECONDS = 30 * 60
RESEARCH_SUMMARY_BUILD_CACHE_STATE_KEY = "market_data_research_summary_build_cache_v1"
RESEARCH_REFRESH_TRACE_STATE_KEY = "market_data_research_refresh_trace_v1"
MARKET_DATA_RANKING_STOCK_NEWS_REPORTS_STATE_KEY = "market_data_ranking_stock_news_reports"
MARKET_DATA_RANKING_EXTERNAL_RESEARCH_RESULTS_STATE_KEY = (
    "market_data_ranking_external_research_results"
)
RESEARCH_STALE_DAYS = 730
DEFAULT_MARKET_DATA_PERIOD_PRESET = MARKET_DATA_PERIOD_CUSTOM


@dataclass(frozen=True)
class ResearchSummaryBundle:
    brief: ResearchBrief
    insight: InvestmentInsight
    security_type: SecurityResearchType
    company_summary: CompanyResearchSummary | None
    etf_summary: ETFResearchSummary | None
    question_summary: InvestmentQuestionSummary | None
    research_score: ResearchScore


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
RANKING_GRID_NOWRAP_CELL_STYLE = {
    "overflow": "hidden",
    "textOverflow": "ellipsis",
    "whiteSpace": "nowrap",
}
RANKING_GRID_NUMERIC_CELL_STYLE = {
    **RANKING_GRID_NOWRAP_CELL_STYLE,
    "textAlign": "right",
}
RANKING_ABNORMAL_DIVIDEND_DISPLAY = "要確認"
RANKING_TABLE_BASE_COLUMNS = (
    "順位",
    "銘柄",
    "お気に入り",
    "銘柄名",
    "株価",
    "総合スコア",
    "判断方針",
    "配当利回り",
    "PER",
    "PBR",
    "ROE",
    "上昇気配",
    "上向き兆候",
    "下降警戒",
    "予測変化率",
    "予測確度",
    "SMAIメモ",
)
RANKING_TABLE_DETAIL_COLUMNS = (
    "ニュース材料",
    "材料件数",
    "材料信頼度",
    "材料の新しさ",
    "予測日数",
    "モデル方向",
    "予測根拠",
    "基礎評価",
    "リスク",
    "データ信頼度",
    "条件適合度",
    "DB信頼度",
    "根拠状態",
    "信頼度/根拠",
    "時価総額",
    "出来高",
    "ボラティリティ",
    "自己資本比率",
    "営業利益率",
    "売上成長率",
    "経費率",
    "NISA",
    "投資スタイル",
    "連動指数",
    "通貨",
    "複雑性",
    "注意点",
)
RANKING_TABLE_HIDDEN_COLUMNS = (
    "確認詳細",
    "並べ替え理由",
    "確認ポイント",
)
LLM_FACTOR_RANKING_COLUMNS = ("LLM強気材料", "LLM弱気材料", "LLM確信度", "材料鮮度")
LLM_FACTOR_RANKING_REFERENCE_NOTICE = (
    "ニュース材料はAI要約です。現在のランキング順位には反映していません。"
)
LLM_FACTOR_RANKING_COLUMN_TOOLTIPS = {
    "ニュース材料": "AI要約で確認したポジティブ/ネガティブ材料の参考値です。",
    "材料件数": "AI要約に使ったニュース・開示などの材料数です。",
    "材料信頼度": "材料抽出結果の信頼度を示す参考指標です。",
    "材料の新しさ": "高いほど新しい材料に基づくことを示す参考指標です。",
}
LLM_FACTOR_RANKING_DETAIL_COLUMNS = tuple(LLM_FACTOR_RANKING_COLUMN_TOOLTIPS)
LLM_FACTOR_RANKING_MISSING_DISPLAY = "—"
RANKING_NUMERIC_SORT_DIRECTIONS = {
    "総合スコア": "desc",
    "Screening": "desc",
    "上昇気配": "desc",
    "上向き兆候": "desc",
    "下降警戒": "asc",
    "配当利回り": "desc",
    "PER": "asc",
    "PBR": "asc",
    "ROE": "desc",
    "高度予測": "desc",
    "予測確度": "desc",
    "高度予測日数": "desc",
    "高度予測スコア": "desc",
    "株価": "desc",
    "時価総額": "desc",
    "出来高": "desc",
    "ボラティリティ": "asc",
    "自己資本比率": "desc",
    "営業利益率": "desc",
    "売上成長率": "desc",
    "Risk": "asc",
    "リスク": "asc",
    "データ品質": "desc",
    "データ信頼度": "desc",
    "経費率": "asc",
}
RANKING_TABLE_SORT_GUIDANCE = (
    "通常表示は、比較に使う列だけです。"
    "ニュース・モデル別情報は「詳細列を表示する」で開けます。"
    "ニュース材料は順位に反映していません。N/Aは未取得・未評価です。"
)
RANKING_LOW_VALUE_BETTER_COLUMNS = {
    "PER",
    "PBR",
    "ボラティリティ",
    "Risk",
    "リスク",
    "下降警戒",
}
SYMBOL_AUTO_REFRESH_REQUEST_STATE_KEY = "symbol_auto_refresh_requests"
SYMBOL_AUTO_REFRESH_REQUEST_KEY_LIMIT = 100
RANKING_AUTO_REFRESH_SYMBOL_LIMIT = 300
SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY = "symbol_preflight_refresh_last_error_type"
COCKPIT_SYMBOL_DB_PREFLIGHT_MAX_ITEMS = 1
COCKPIT_SYMBOL_DB_PREFLIGHT_REQUEST_STATE_KEY = "cockpit_symbol_db_preflight_requests"
COCKPIT_SYMBOL_DB_PREFLIGHT_TTL_SECONDS = 30 * 60
WATCHLIST_BACKGROUND_REFRESH_MAX_ITEMS = 3
WATCHLIST_BACKGROUND_REFRESH_TTL_SECONDS = 6 * 60 * 60
WATCHLIST_BACKGROUND_REFRESH_STATE_KEY = "watchlist_background_refresh"
WATCHLIST_AUTO_SNAPSHOT_STATE_KEY = "watchlist_auto_snapshot_summary"
WATCHLIST_AUTO_SNAPSHOT_MAX_ITEMS = 3
WATCHLIST_MANUAL_REFRESH_MAX_ITEMS = 10
RANKING_SYMBOL_DB_PREFLIGHT_DIRECT_THRESHOLD = 30
RANKING_SYMBOL_DB_PREFLIGHT_MAX_ITEMS = 50
RANKING_SYMBOL_DB_PREFLIGHT_SCAN_LIMIT = 300
MARKET_CHART_FULL_WIDTH = 1012
MARKET_CHART_FOCUS_WIDTH = 260
MARKET_CHART_COMBINED_SPACING = 8
MARKET_CHART_HEIGHT = 540
ADVANCED_FORECAST_CONSENSUS_LABEL = "AI予測インサイト"
ADVANCED_FORECAST_CONSENSUS_PREDICTION_LABEL = "統合予測"
FORECAST_DECISION_SUPPORT_NOTE = (
    "過去データから計算した参考予測です。予測レンジと根拠も見比べます。"
)
RANKING_DOWNSIDE_LOW_IS_BETTER_NOTE = (
    "下降警戒は低いほど良い指標です。ランキングでは、警戒が低いほど加点されます。"
    "AI下振れ警戒も同じ考え方で扱います。"
)
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
    var leadingNumber = text.match(/^[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)/);
    var numberValue = leadingNumber ? Number(leadingNumber[0]) : Number(text);
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
RANKING_TABLE_CONFIG = RankingTableConfig(
    nowrap_cell_style=RANKING_GRID_NOWRAP_CELL_STYLE,
    numeric_cell_style=RANKING_GRID_NUMERIC_CELL_STYLE,
    numeric_sort_directions=RANKING_NUMERIC_SORT_DIRECTIONS,
    numeric_sort_comparator=RANKING_NUMERIC_SORT_COMPARATOR,
    llm_factor_detail_columns=LLM_FACTOR_RANKING_DETAIL_COLUMNS,
    llm_factor_column_tooltips=LLM_FACTOR_RANKING_COLUMN_TOOLTIPS,
    hidden_columns=RANKING_TABLE_HIDDEN_COLUMNS,
)
SYMBOL_DETAIL_DIALOG_CSS = """
<style>
div[data-testid="stDialog"] div[role="dialog"] {
    width: min(94vw, 1500px);
    max-width: min(94vw, 1500px);
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
    font-size: 0.96rem;
    margin-bottom: 0.3rem;
}
.research-ai-cta-copy {
    color: var(--text-ai-primary);
    font-size: 0.86rem;
    line-height: 1.48;
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
.research-provider-status-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.38rem;
    margin-top: 0.7rem;
}
.research-provider-status-chip {
    border: 1px solid rgba(148, 163, 184, 0.34);
    border-radius: 999px;
    background: rgba(148, 163, 184, 0.08);
    color: var(--text-ai-primary);
    font-size: 0.78rem;
    font-weight: 780;
    line-height: 1.35;
    padding: 0.2rem 0.54rem;
}
.research-provider-status-chip.success {
    border-color: rgba(34, 197, 94, 0.48);
    background: rgba(34, 197, 94, 0.09);
}
.research-provider-status-chip.no_result {
    color: var(--text-caption);
}
.research-provider-status-chip.timeout,
.research-provider-status-chip.failed {
    border-color: rgba(245, 158, 11, 0.48);
    background: rgba(245, 158, 11, 0.1);
}
.research-result-status-warning {
    border-left: 3px solid rgba(245, 158, 11, 0.72);
    color: var(--text-ai-primary);
    font-size: 0.82rem;
    line-height: 1.55;
    margin-top: 0.65rem;
    padding-left: 0.7rem;
}
.research-result-status-warning ul {
    margin: 0;
    padding-left: 1rem;
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
.market-intelligence-panel {
    background:
        radial-gradient(circle at top left, rgba(73, 219, 230, 0.08), transparent 30%),
        linear-gradient(135deg, rgba(7, 21, 36, 0.98), rgba(11, 28, 46, 0.96));
    border: 1px solid rgba(73, 219, 230, 0.22);
    border-radius: 10px;
    box-shadow:
        0 0 28px rgba(73, 219, 230, 0.06),
        inset 0 1px 0 rgba(255, 255, 255, 0.035);
    margin: 0.85rem 0;
    padding: 0.92rem;
}
.market-intelligence-panel.spotlight {
    border-color: rgba(243, 197, 92, 0.28);
    background:
        radial-gradient(circle at top left, rgba(243, 197, 92, 0.11), transparent 31%),
        linear-gradient(135deg, rgba(14, 25, 38, 0.98), rgba(11, 27, 45, 0.96));
    box-shadow:
        0 0 26px rgba(243, 197, 92, 0.07),
        inset 0 1px 0 rgba(255, 255, 255, 0.035);
}
.market-intelligence-panel.sources {
    margin: 0;
}
.market-intelligence-header {
    align-items: flex-start;
    display: flex;
    gap: 0.85rem;
    justify-content: space-between;
}
.market-intelligence-kicker {
    color: var(--text-ai-primary);
    font-size: 0.72rem;
    font-weight: 850;
    letter-spacing: 0;
    line-height: 1.25;
    text-transform: uppercase;
}
.market-intelligence-title {
    color: rgba(235, 247, 255, 0.95);
    font-size: 1.05rem;
    font-weight: 880;
    line-height: 1.35;
    margin-top: 0.12rem;
}
.market-intelligence-subtitle {
    color: rgba(188, 210, 225, 0.78);
    font-size: 0.82rem;
    line-height: 1.55;
    margin-top: 0.25rem;
}
.market-intelligence-count {
    border: 1px solid rgba(73, 219, 230, 0.34);
    border-radius: 999px;
    background: rgba(73, 219, 230, 0.08);
    color: rgba(145, 245, 250, 0.95);
    flex: 0 0 auto;
    font-size: 0.74rem;
    font-weight: 830;
    line-height: 1.2;
    padding: 0.2rem 0.55rem;
}
.news-feed-list {
    display: grid;
    gap: 0.72rem;
    margin-top: 0.85rem;
}
.market-news-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
}
.market-news-grid .market-news-item.featured {
    grid-column: 1 / -1;
}
.news-feed-top-list,
.research-news-headline-list {
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}
.news-feed-item {
    background:
        radial-gradient(circle at top left, rgba(127, 151, 170, 0.08), transparent 28%),
        linear-gradient(135deg, rgba(15, 29, 43, 0.96), rgba(9, 22, 36, 0.95));
    border: 1px solid rgba(127, 151, 170, 0.18);
    border-left: 3px solid rgba(127, 151, 170, 0.78);
    border-radius: 14px;
    color: rgba(188, 210, 225, 0.78);
    display: grid;
    gap: 1rem;
    grid-template-columns: minmax(0, 1fr) auto;
    min-height: 118px;
    padding: 0.86rem 0.95rem;
    text-decoration: none;
    box-shadow:
        0 0 16px rgba(7, 21, 36, 0.14),
        inset 0 1px 0 rgba(255, 255, 255, 0.028);
    transition: background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}
.news-feed-item-clickable {
    cursor: pointer;
}
.news-feed-item-clickable.market-news-item:hover {
    background:
        radial-gradient(circle at top left, rgba(73, 219, 230, 0.14), transparent 30%),
        linear-gradient(135deg, rgba(18, 40, 57, 0.97), rgba(10, 25, 41, 0.96));
    border-color: rgba(90, 235, 240, 0.35);
    box-shadow:
        0 0 24px rgba(73, 219, 230, 0.10),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    transform: translateY(-1px);
}
.news-feed-item-clickable.market-news-item:focus-visible {
    border-color: rgba(90, 235, 240, 0.88);
    box-shadow:
        0 0 0 2px rgba(90, 235, 240, 0.22),
        0 0 18px rgba(90, 235, 240, 0.12);
    outline: none;
}
.market-news-item.news {
    background:
        radial-gradient(circle at top left, rgba(73, 219, 230, 0.10), transparent 28%),
        linear-gradient(135deg, rgba(15, 34, 51, 0.96), rgba(9, 23, 38, 0.95));
    border-color: rgba(73, 219, 230, 0.18);
    border-left-color: rgba(73, 219, 230, 0.88);
}
.market-news-item.news:hover {
    background:
        radial-gradient(circle at top left, rgba(73, 219, 230, 0.14), transparent 30%),
        linear-gradient(135deg, rgba(18, 40, 57, 0.97), rgba(10, 25, 41, 0.96));
    border-color: rgba(90, 235, 240, 0.36);
    box-shadow:
        0 0 24px rgba(73, 219, 230, 0.11),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.market-news-item.ir,
.market-news-item.disclosure {
    background:
        radial-gradient(circle at top left, rgba(155, 123, 255, 0.11), transparent 30%),
        linear-gradient(135deg, rgba(22, 27, 51, 0.96), rgba(10, 22, 40, 0.95));
    border-color: rgba(155, 123, 255, 0.20);
    border-left-color: rgba(155, 123, 255, 0.90);
}
.market-news-item.ir:hover,
.market-news-item.disclosure:hover {
    background:
        radial-gradient(circle at top left, rgba(155, 123, 255, 0.15), transparent 31%),
        linear-gradient(135deg, rgba(25, 30, 56, 0.97), rgba(11, 24, 43, 0.96));
    border-color: rgba(176, 153, 255, 0.38);
    box-shadow:
        0 0 24px rgba(155, 123, 255, 0.10),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.market-news-item.important {
    background:
        radial-gradient(circle at top left, rgba(243, 197, 92, 0.13), transparent 32%),
        linear-gradient(135deg, rgba(40, 34, 20, 0.90), rgba(10, 23, 38, 0.96));
    border-color: rgba(243, 197, 92, 0.26);
    border-left-color: rgba(243, 197, 92, 0.94);
}
.market-news-item.important:hover {
    background:
        radial-gradient(circle at top left, rgba(243, 197, 92, 0.17), transparent 33%),
        linear-gradient(135deg, rgba(44, 37, 22, 0.94), rgba(11, 25, 41, 0.97));
    border-color: rgba(243, 197, 92, 0.42);
    box-shadow:
        0 0 25px rgba(243, 197, 92, 0.11),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.market-news-item.risk {
    background:
        radial-gradient(circle at top left, rgba(255, 116, 116, 0.10), transparent 30%),
        linear-gradient(135deg, rgba(42, 22, 25, 0.90), rgba(10, 22, 36, 0.95));
    border-color: rgba(255, 116, 116, 0.22);
    border-left-color: rgba(255, 116, 116, 0.90);
}
.market-news-item.risk:hover {
    background:
        radial-gradient(circle at top left, rgba(255, 116, 116, 0.14), transparent 31%),
        linear-gradient(135deg, rgba(46, 24, 28, 0.94), rgba(11, 24, 40, 0.96));
    border-color: rgba(255, 142, 142, 0.36);
    box-shadow:
        0 0 24px rgba(255, 116, 116, 0.10),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.market-news-item.other {
    background:
        radial-gradient(circle at top left, rgba(127, 151, 170, 0.08), transparent 28%),
        linear-gradient(135deg, rgba(15, 29, 43, 0.96), rgba(9, 22, 36, 0.95));
    border-color: rgba(127, 151, 170, 0.18);
    border-left-color: rgba(127, 151, 170, 0.78);
}
.market-news-item.other:hover {
    background:
        radial-gradient(circle at top left, rgba(127, 151, 170, 0.12), transparent 30%),
        linear-gradient(135deg, rgba(18, 33, 49, 0.97), rgba(10, 24, 39, 0.96));
    border-color: rgba(150, 174, 192, 0.30);
    box-shadow:
        0 0 22px rgba(127, 151, 170, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.top-material-card {
    background:
        radial-gradient(circle at top left, rgba(243, 197, 92, 0.15), transparent 34%),
        linear-gradient(135deg, rgba(40, 34, 20, 0.92), rgba(10, 23, 38, 0.96));
    border: 1px solid rgba(243, 197, 92, 0.30);
    border-left: 3px solid rgba(243, 197, 92, 0.95);
    box-shadow:
        0 0 22px rgba(243, 197, 92, 0.07),
        inset 0 1px 0 rgba(255, 255, 255, 0.035);
}
.top-material-card:hover {
    background:
        radial-gradient(circle at top left, rgba(243, 197, 92, 0.18), transparent 34%),
        linear-gradient(135deg, rgba(44, 37, 22, 0.94), rgba(11, 25, 41, 0.97));
    border-color: rgba(243, 197, 92, 0.45);
    box-shadow:
        0 0 26px rgba(243, 197, 92, 0.12),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.market-news-main {
    max-width: 980px;
    min-width: 0;
}
.market-news-aside {
    align-items: flex-end;
    display: flex;
    flex-direction: column;
    gap: 0.42rem;
    justify-content: flex-start;
    min-width: 9.5rem;
    text-align: right;
}
.market-news-kind {
    background: rgba(73, 219, 230, 0.08);
    border: 1px solid rgba(73, 219, 230, 0.30);
    border-radius: 999px;
    color: rgba(145, 245, 250, 0.95);
    font-size: 0.72rem;
    font-weight: 800;
    line-height: 1.25;
    padding: 0.16rem 0.52rem;
}
.market-news-date {
    color: rgba(135, 165, 185, 0.68);
    font-size: 0.76rem;
    line-height: 1.35;
}
.news-item-top,
.research-news-headline-top {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.36rem;
    margin-bottom: 0.42rem;
}
.news-item-badge,
.research-news-headline-chip {
    background: rgba(127, 151, 170, 0.08);
    border: 1px solid rgba(127, 151, 170, 0.28);
    border-radius: 999px;
    color: rgba(188, 210, 225, 0.76);
    font-size: 0.72rem;
    font-weight: 820;
    line-height: 1.25;
    padding: 0.14rem 0.45rem;
}
.news-item-badge.primary,
.research-news-headline-chip.primary {
    background: rgba(73, 219, 230, 0.10);
    border-color: rgba(73, 219, 230, 0.35);
    color: rgba(145, 245, 250, 0.95);
}
.news-item-badge.positive,
.research-news-headline-chip.positive {
    background: rgba(52, 211, 153, 0.09);
    border-color: rgba(52, 211, 153, 0.52);
    color: var(--text-positive);
}
.news-item-badge.risk,
.research-news-headline-chip.risk {
    background: rgba(255, 116, 116, 0.10);
    border-color: rgba(255, 116, 116, 0.42);
    color: rgba(255, 186, 186, 0.95);
}
.market-news-item.ir .news-item-badge,
.market-news-item.ir .research-news-headline-chip,
.market-news-item.disclosure .news-item-badge,
.market-news-item.disclosure .research-news-headline-chip,
.market-news-item.ir .market-news-kind,
.market-news-item.disclosure .market-news-kind {
    background: rgba(155, 123, 255, 0.10);
    border-color: rgba(155, 123, 255, 0.34);
    color: rgba(205, 194, 255, 0.95);
}
.market-news-item.important .news-item-badge,
.market-news-item.important .research-news-headline-chip,
.market-news-item.important .market-news-kind,
.top-material-card .news-item-badge.primary,
.top-material-card .research-news-headline-chip.primary,
.top-material-card .market-news-kind {
    background: rgba(243, 197, 92, 0.12);
    border-color: rgba(243, 197, 92, 0.38);
    color: rgba(255, 224, 145, 0.96);
}
.market-news-item.risk .news-item-badge,
.market-news-item.risk .research-news-headline-chip,
.market-news-item.risk .market-news-kind {
    background: rgba(255, 116, 116, 0.10);
    border-color: rgba(255, 116, 116, 0.36);
    color: rgba(255, 190, 190, 0.94);
}
.top-material-card .news-item-badge:not(.risk):not(.positive),
.top-material-card .research-news-headline-chip:not(.risk):not(.positive),
.top-material-card .market-news-kind {
    background: rgba(243, 197, 92, 0.12);
    border-color: rgba(243, 197, 92, 0.38);
    color: rgba(255, 224, 145, 0.96);
}
.top-material-card .news-item-badge.risk,
.top-material-card .research-news-headline-chip.risk {
    background: rgba(255, 116, 116, 0.10);
    border-color: rgba(255, 116, 116, 0.40);
    color: rgba(255, 190, 190, 0.94);
}
.news-item-title,
.research-news-headline-title {
    color: rgba(235, 247, 255, 0.96);
    font-size: 0.98rem;
    font-weight: 850;
    line-height: 1.45;
    margin-bottom: 0.45rem;
    max-width: 920px;
    overflow-wrap: anywhere;
}
.news-item-meta,
.research-news-headline-meta {
    color: rgba(135, 165, 185, 0.68);
    display: flex;
    flex-wrap: wrap;
    font-size: 0.78rem;
    gap: 0.45rem 0.72rem;
    line-height: 1.45;
    margin-bottom: 0.42rem;
}
.news-item-meta strong,
.research-news-headline-meta strong {
    color: rgba(188, 210, 225, 0.86);
    font-weight: 830;
}
.news-item-summary,
.research-news-headline-summary {
    color: rgba(188, 210, 225, 0.78);
    font-size: 0.84rem;
    line-height: 1.7;
    max-width: 980px;
    overflow-wrap: anywhere;
}
.news-source-link,
.research-news-headline-action {
    color: rgba(90, 235, 240, 0.96);
    display: inline-block;
    font-size: 0.78rem;
    font-weight: 820;
    margin-top: 0.54rem;
    text-decoration: none;
}
.news-feed-item-clickable:hover .news-source-link {
    text-decoration: underline;
}
.news-source-citation-panel {
    border-top: 1px solid rgba(127, 151, 170, 0.20);
    color: rgba(158, 183, 200, 0.70);
    font-size: 0.78rem;
    line-height: 1.55;
    margin-top: 0.25rem;
    padding-top: 0.72rem;
}
.news-source-citation-header {
    align-items: baseline;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.7rem;
    justify-content: space-between;
    margin-bottom: 0.55rem;
}
.news-source-citation-title {
    color: rgba(188, 210, 225, 0.76);
    font-size: 0.82rem;
    font-weight: 780;
}
.news-source-citation-note,
.news-source-citation-count,
.news-source-citation-more {
    color: rgba(135, 165, 185, 0.62);
    font-size: 0.74rem;
}
.news-source-citation-list {
    counter-reset: source-citation;
    display: grid;
    gap: 0.38rem;
    margin: 0;
}
.news-source-citation-item {
    border-left: 2px solid rgba(127, 151, 170, 0.22);
    color: rgba(170, 195, 210, 0.72);
    display: grid;
    gap: 0.18rem;
    grid-template-columns: minmax(0, 1fr) auto;
    padding: 0.36rem 0 0.36rem 0.65rem;
    text-decoration: none;
}
.news-source-citation-item:hover {
    border-left-color: rgba(90, 235, 240, 0.42);
    color: rgba(208, 230, 242, 0.88);
}
.news-source-citation-main {
    min-width: 0;
}
.news-source-citation-title-line {
    color: rgba(208, 230, 242, 0.84);
    font-size: 0.8rem;
    font-weight: 760;
    line-height: 1.45;
    overflow-wrap: anywhere;
}
.news-source-citation-meta {
    color: rgba(135, 165, 185, 0.62);
    display: flex;
    flex-wrap: wrap;
    font-size: 0.72rem;
    gap: 0.24rem 0.58rem;
}
.news-source-citation-action {
    align-self: center;
    color: rgba(90, 235, 240, 0.78);
    font-size: 0.72rem;
    font-weight: 760;
    white-space: nowrap;
}
.news-source-citation-item:hover .news-source-citation-action {
    color: rgba(145, 245, 250, 0.96);
    text-decoration: underline;
}
.research-news-summary-list {
    display: grid;
    gap: 0.72rem;
    margin-top: 0.85rem;
}
.research-news-summary-card {
    color: var(--text-secondary);
    text-decoration: none;
}
@media (max-width: 1100px) {
    .market-news-grid,
    .news-feed-top-list,
    .research-news-headline-list {
        grid-template-columns: 1fr;
    }
    .news-feed-item {
        grid-template-columns: 1fr;
    }
    .market-news-aside {
        align-items: flex-start;
        min-width: 0;
        text-align: left;
    }
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
    st.set_page_config(
        page_title="Smart Market AI",
        page_icon="ui/static/pwa/favicon.png",
        layout="wide",
    )
    inject_pwa_head_metadata()
    render_global_styles()
    _render_maintenance_status()
    if not render_user_notification_area():
        return
    _start_symbol_background_refresh_worker_once()
    _start_news_background_refresh_worker_once()
    _apply_navigation_query_params()
    restored_symbol = str(st.session_state.get("market_data_ranking_handoff_symbol", ""))
    current_candidate = str(st.session_state.get("market_data_symbol_candidate", ""))
    if restored_symbol and current_candidate == restored_symbol:
        st.session_state["market_data_symbol_candidate"] = symbol_candidate_label(restored_symbol)

    selected_page = render_sidemenu(runtime_settings_summary())
    prepare_ranking_history_view_for_page(selected_page)
    restore_notice = st.session_state.pop(RESTORE_NOTICE_KEY, None)
    if isinstance(restore_notice, dict):
        restored_parts = [
            SIDEMENU_PAGE_LABELS.get(cast(Any, str(restore_notice.get("active_page", ""))), ""),
            str(restore_notice.get("selected_symbol", "")),
        ]
        detail = " / ".join(part for part in restored_parts if part)
        message = "前回の状態を復元しました"
        st.toast(f"{message}: {detail}" if detail else message)
    reset_assistant_contexts()
    # Investment Radar has its own concise task-oriented title.  Keeping the
    # global brand hero above it pushes the market overview and candidate queue
    # below the first viewport, especially on tablets and phones.
    if selected_page not in {
        SIDEMENU_PAGE_COCKPIT,
        SIDEMENU_PAGE_COPILOT,
        SIDEMENU_PAGE_RANKING,
        SIDEMENU_PAGE_NEWS,
    }:
        render_app_header()
    if selected_page == SIDEMENU_PAGE_COCKPIT:
        _render_market_data_cockpit()
    elif selected_page == SIDEMENU_PAGE_RANKING:
        _render_market_data_ranking()
    elif selected_page == SIDEMENU_PAGE_NEWS:
        render_news_dashboard_page(
            open_symbol_callback=_select_news_symbol_for_cockpit,
            market_snapshot_callback=_fetch_news_radar_market_snapshot,
        )
    elif selected_page == SIDEMENU_PAGE_WATCHLIST:
        _render_my_watchlist_page()
    elif selected_page == SIDEMENU_PAGE_COPILOT:
        render_copilot_workspace_page()
    elif selected_page == SIDEMENU_PAGE_REBALANCE:
        render_rebalance_page()
    else:
        render_settings_page()
    if selected_page != SIDEMENU_PAGE_COPILOT:
        render_floating_assistant(
            page_key=selected_page,
            page_label=SIDEMENU_PAGE_LABELS.get(selected_page, "SMAI"),
        )
    selected_symbol = (
        _symbol_from_candidate(str(st.session_state.get("market_data_symbol_candidate", ""))) or ""
    )
    client_id = str(st.session_state.get(CLIENT_ID_STATE_KEY) or "")
    save_client_session_if_changed(
        cast(Mapping[str, Any], st.session_state),
        client_id=client_id,
        selected_symbol=selected_symbol,
    )


def _render_maintenance_status() -> None:
    components.html(device_identity_bridge_html(), height=0, width=0)
    session_key = "smai_server_ops_session_id"
    session_id = str(st.session_state.get(session_key) or "")
    if not session_id:
        session_id = uuid4().hex
        st.session_state[session_key] = session_id
    _maintenance_heartbeat_fragment(
        session_id,
        _current_client_type(),
        device_id_from_query(getattr(st, "query_params", None)),
    )


def _current_client_type() -> str:
    """Derive a coarse client type without retaining a raw browser identifier."""

    user_agent = st.context.headers.get("User-Agent", "")
    return classify_client_type(user_agent)


@st.fragment(run_every=60)
def _maintenance_heartbeat_fragment(session_id: str, client_type: str, device_id: str) -> None:
    manager = maintenance_module.MaintenanceManager()
    if "device_id" not in inspect.signature(manager.heartbeat).parameters:
        # Streamlit can reload this UI module while retaining an older imported
        # maintenance module. Reload that local module once so a deployment
        # does not require a forced process restart merely to resume telemetry.
        manager = importlib.reload(maintenance_module).MaintenanceManager()
    manager.heartbeat(session_id, client_type=client_type, device_id=device_id)
    notice = manager.notice()
    if notice:
        st.warning(str(notice.get("message") or "30秒後にメンテナンス再起動を行います。"))


def _apply_navigation_query_params() -> None:
    params = getattr(st, "query_params", None)
    if params is None:
        return
    page = _query_param_value(_query_param_get(params, NEWS_COCKPIT_QUERY_PAGE_PARAM))
    symbol = _query_param_value(_query_param_get(params, NEWS_COCKPIT_QUERY_SYMBOL_PARAM))
    if page != NEWS_COCKPIT_QUERY_COCKPIT_VALUE:
        if _apply_sidemenu_page_query(page):
            _clear_navigation_query_params(params, (NEWS_COCKPIT_QUERY_PAGE_PARAM,))
        return
    if not symbol:
        if _apply_sidemenu_page_query(page):
            _clear_navigation_query_params(params, (NEWS_COCKPIT_QUERY_PAGE_PARAM,))
        return
    _select_news_symbol_for_cockpit(symbol.upper())
    _clear_navigation_query_params(
        params,
        (NEWS_COCKPIT_QUERY_PAGE_PARAM, NEWS_COCKPIT_QUERY_SYMBOL_PARAM),
    )


def _apply_sidemenu_page_query(page: str) -> bool:
    page_key = page.strip().lower()
    if page_key not in {
        SIDEMENU_PAGE_NEWS,
        SIDEMENU_PAGE_COPILOT,
        SIDEMENU_PAGE_COCKPIT,
        SIDEMENU_PAGE_RANKING,
        SIDEMENU_PAGE_REBALANCE,
        SIDEMENU_PAGE_SETTINGS,
        SIDEMENU_PAGE_WATCHLIST,
    }:
        return False
    st.session_state[SIDEMENU_STATE_KEY] = page_key
    return True


def _query_param_get(params: object, key: str) -> object:
    getter = getattr(params, "get", None)
    if callable(getter):
        return getter(key)
    try:
        return params[key]  # type: ignore[index]
    except (KeyError, TypeError):
        return None


def _query_param_value(value: object) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()


def _clear_navigation_query_params(params: object, keys: Iterable[str]) -> None:
    mutable_params = cast(MutableMapping[str, object], params)
    for key in keys:
        try:
            if key in mutable_params:
                del mutable_params[key]
        except (KeyError, TypeError, AttributeError):
            continue


def _register_cockpit_setup_assistant_context(symbol: str = "") -> None:
    register_assistant_context(
        SmaiAssistantContext(
            context_id="cockpit_setup",
            page_key=SIDEMENU_PAGE_COCKPIT,
            page_label=SIDEMENU_PAGE_LABELS[SIDEMENU_PAGE_COCKPIT],
            section_key="setup",
            section_label="データ取得前",
            lead="銘柄と期間を選び、価格・予測・スコアの確認材料をそろえます。",
            summary={"対象銘柄": symbol or "未選択"},
            suggested_questions=(
                "この画面でまず見る点は？",
                "取得期間はどう選ぶ？",
                "データ取得後に何を見る？",
            ),
            priority=10,
        )
    )


def _register_cockpit_forecast_assistant_context(
    symbol_label: str,
    rows: list[dict[str, str]],
    *,
    forecast_horizon_days: int,
) -> None:
    if not rows:
        return
    row = rows[0]
    warning = _advanced_forecast_warning_display(row.get("warnings", ""))
    register_assistant_context(
        SmaiAssistantContext(
            context_id="cockpit_forecast",
            page_key=SIDEMENU_PAGE_COCKPIT,
            page_label=SIDEMENU_PAGE_LABELS[SIDEMENU_PAGE_COCKPIT],
            section_key="ai_forecast_insight",
            section_label=ADVANCED_FORECAST_CONSENSUS_LABEL,
            lead="中心予測、下振れ、上振れ、信頼度を順番に確認するセクションです。",
            summary={
                "対象": symbol_label,
                "予測期間": f"{forecast_horizon_days}日",
                "中心予測": _signed_percent_from_text(row.get("predicted_return", "")) or "未計算",
                "予測価格": row.get("forecast_close", "") or "未計算",
                "予測レンジ": _advanced_forecast_range_display(row) or "未計算",
                "信頼度": _advanced_forecast_confidence_label(row.get("confidence", "")),
                "モデル合意度": _advanced_forecast_model_agreement_display(row),
            },
            warnings=(warning,) if warning else (),
            notes=(
                _advanced_forecast_caution_text(
                    row,
                    dispersion=_advanced_forecast_dispersion_label(row),
                ),
            ),
            suggested_questions=(
                "AI予測インサイトをどう読む？",
                "中心予測とは？",
                "下振れ・上振れはどう読む？",
                "Decision Reportに残す確認ポイントは？",
            ),
            priority=95,
        )
    )


def _register_cockpit_direction_assistant_context(
    score_row: dict[str, str],
    consensus_row: dict[str, str],
    detail_rows: list[dict[str, str]],
) -> None:
    warning = ""
    downside = _decimal_from_text(score_row.get("下降警戒") or "")
    if downside is not None and downside >= Decimal("65"):
        warning = "下降警戒が高めです。価格トレンドと予測下限を合わせて確認します。"
    register_assistant_context(
        SmaiAssistantContext(
            context_id="cockpit_direction",
            page_key=SIDEMENU_PAGE_COCKPIT,
            page_label=SIDEMENU_PAGE_LABELS[SIDEMENU_PAGE_COCKPIT],
            section_key="direction_signal",
            section_label="上昇気配・下降警戒",
            lead="上向きシグナルと下振れ警戒を分け、どちらを先に確認するか整理します。",
            summary={
                "上昇気配": score_row.get("上昇気配") or "未計算",
                "上向き兆候": score_row.get("上向き兆候") or "未計算",
                "上向き兆候ラベル": upward_signal_display_label(
                    score_row.get("reversal_expectation_label")
                )
                or "未計算",
                "上向き兆候理由": score_row.get("reversal_expectation_reason") or "未計算",
                "下降警戒": score_row.get("下降警戒") or "未計算",
                "読み取り": cockpit_direction_signal_summary(score_row, consensus_row),
            },
            rows=detail_rows,
            warnings=(warning,) if warning else (),
            suggested_questions=(
                "上昇気配・下降警戒の理由は？",
                "上昇気配と上向き兆候は何が違う？",
                "上向き兆候が高い理由は？",
                "AI予測インサイトとどう見比べる？",
                "下降警戒が高い時は？",
                "Decision Reportに残す確認ポイントは？",
            ),
            priority=85,
        )
    )


def _register_cockpit_report_assistant_context(
    context: DecisionReportContext,
    summary_lines: Sequence[str],
) -> None:
    register_assistant_context(
        SmaiAssistantContext(
            context_id="cockpit_report",
            page_key=SIDEMENU_PAGE_COCKPIT,
            page_label=SIDEMENU_PAGE_LABELS[SIDEMENU_PAGE_COCKPIT],
            section_key="decision_report",
            section_label="確認レポート",
            lead="確認した材料を、あとで見返せる分析メモとして整理します。",
            summary={
                "レポート": context.title,
                "セクション数": str(len(context.sections)),
                "AI要約": " / ".join(summary_lines[:2]) if summary_lines else "未作成",
            },
            rows=_decision_report_context_summary_rows(context),
            suggested_questions=(
                "確認レポートに残す確認ポイントは？",
                "レポートでは何を保存する？",
                "AI予測とリスクをどう書き分ける？",
            ),
            priority=70,
        )
    )


def _register_ranking_setup_assistant_context() -> None:
    register_assistant_context(
        SmaiAssistantContext(
            context_id="ranking_setup",
            page_key=SIDEMENU_PAGE_RANKING,
            page_label=SIDEMENU_PAGE_LABELS[SIDEMENU_PAGE_RANKING],
            section_key="setup",
            section_label="ランキング作成前",
            lead="評価方針と比較対象を選び、深掘り候補を整理する準備をします。",
            suggested_questions=(
                "評価方針はどう選ぶ？",
                "作成対象はどう決める？",
                "ランキング作成後に何を見る？",
            ),
            priority=10,
        )
    )


def _register_ranking_results_assistant_context(
    display_rows: list[dict[str, str]],
    *,
    ranking_policy: str,
    forecast_horizon_days: int,
) -> None:
    top_rows = display_rows[:5]
    register_assistant_context(
        SmaiAssistantContext(
            context_id="ranking_results",
            page_key=SIDEMENU_PAGE_RANKING,
            page_label=SIDEMENU_PAGE_LABELS[SIDEMENU_PAGE_RANKING],
            section_key="ranking_results",
            section_label="ランキング結果",
            lead="順位を深掘り候補の確認順として読み、スコアと警戒材料を見比べます。",
            summary={
                "評価方針": ranking_policy_label(ranking_policy),
                "表示件数": f"{len(display_rows)}件",
                "共通予測期間": f"{forecast_horizon_days}日",
            },
            rows=[
                {
                    "順位": row.get("順位", ""),
                    "銘柄": row.get("銘柄", ""),
                    "銘柄名": row.get("銘柄名", ""),
                    "総合スコア": row.get("総合スコア", ""),
                    "上昇気配": row.get("上昇気配", ""),
                    "上向き兆候": row.get("上向き兆候", ""),
                    "上向き兆候理由": row.get("上向き兆候理由", ""),
                    "下降警戒": row.get("下降警戒", ""),
                    "AI予測インサイト": _ranking_advanced_forecast_display(row),
                }
                for row in top_rows
            ],
            suggested_questions=(
                "なぜこの候補が上位？",
                "深掘り候補の比較ポイントは？",
                "AI総合・上昇気配・下降警戒の違いは？",
                "上向き兆候が高い銘柄を教えて",
                "上昇気配と上向き兆候は何が違う？",
                "低信頼データはどう読む？",
            ),
            priority=92,
        )
    )


def _register_ranking_deep_dive_assistant_context(
    selected_row: dict[str, str] | None,
    *,
    ranking_policy: str,
) -> None:
    if selected_row is None:
        return
    reason = ranking_purpose_row_reason(selected_row, ranking_policy)
    checkpoint = ranking_purpose_row_checkpoint(selected_row, ranking_policy)
    register_assistant_context(
        SmaiAssistantContext(
            context_id="ranking_deep_dive",
            page_key=SIDEMENU_PAGE_RANKING,
            page_label=SIDEMENU_PAGE_LABELS[SIDEMENU_PAGE_RANKING],
            section_key="deep_dive_candidate",
            section_label="深掘り候補",
            lead="選択中の候補について、上位にある理由と次に見る観点を整理します。",
            summary={
                "銘柄": selected_row.get("銘柄", ""),
                "銘柄名": selected_row.get("銘柄名", ""),
                "評価方針": ranking_policy_label(ranking_policy),
                "総合スコア": selected_row.get("総合スコア", ""),
                "上昇気配": selected_row.get("上昇気配", ""),
                "上向き兆候": selected_row.get("上向き兆候", ""),
                "上向き兆候理由": selected_row.get("上向き兆候理由", ""),
                "下降警戒": selected_row.get("下降警戒", ""),
                "AI予測インサイト": _ranking_advanced_forecast_display(selected_row),
                "上位理由": reason,
            },
            rows=[
                {"観点": "上位理由", "内容": reason},
                {"観点": "確認ポイント", "内容": checkpoint},
            ],
            warnings=(selected_row.get("注意点", ""),),
            suggested_questions=(
                "なぜこの候補が上位？",
                "コックピットで何を見る？",
                "下降警戒が高い時は？",
                "低信頼データはどう読む？",
            ),
            priority=88,
        )
    )


def _start_symbol_background_refresh_worker_once() -> None:
    state_key = "symbol_background_refresh_worker_started"
    if state_key in st.session_state:
        return
    if _background_workers_disabled():
        st.session_state[state_key] = {"disabled": True}
        return
    try:
        start_symbol_background_refresh_worker(delay_scale=_symbol_background_refresh_delay_scale())
        st.session_state[state_key] = True
    except Exception as exc:
        st.session_state[state_key] = {
            "failed": True,
            "error_type": type(exc).__name__,
        }


def _symbol_background_refresh_delay_scale() -> float:
    raw_value = os.environ.get("SMAI_SYMBOL_BACKGROUND_REFRESH_DELAY_SCALE", "").strip()
    if not raw_value:
        return 1.0
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return 1.0


def symbol_auto_refresh_request_key(
    symbols: Sequence[str],
    *,
    context: Literal["cockpit", "ranking"],
    source_key: str = "",
    max_symbols: int = RANKING_AUTO_REFRESH_SYMBOL_LIMIT,
) -> str:
    normalized_symbols = _symbol_auto_refresh_symbols(symbols, max_symbols=max_symbols)
    symbols_digest = hashlib.sha1(",".join(normalized_symbols).encode("utf-8")).hexdigest()[:16]
    source_digest = (
        hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:12] if source_key else "default"
    )
    return f"{context}|{source_digest}|{len(normalized_symbols)}|{symbols_digest}"


def _request_symbol_auto_refresh_once(
    symbols: Sequence[str],
    *,
    context: Literal["cockpit", "ranking"],
    source_key: str = "",
    max_symbols: int = RANKING_AUTO_REFRESH_SYMBOL_LIMIT,
) -> None:
    normalized_symbols = _symbol_auto_refresh_symbols(symbols, max_symbols=max_symbols)
    if not normalized_symbols:
        return
    request_key = symbol_auto_refresh_request_key(
        normalized_symbols,
        context=context,
        source_key=source_key,
        max_symbols=max_symbols,
    )
    raw_requested_keys = st.session_state.get(SYMBOL_AUTO_REFRESH_REQUEST_STATE_KEY, [])
    requested_keys = (
        [str(key) for key in raw_requested_keys]
        if isinstance(raw_requested_keys, (list, tuple, set))
        else []
    )
    if request_key in requested_keys:
        return
    try:
        request_symbol_background_refresh(normalized_symbols, source=context)
    except Exception as exc:  # noqa: BLE001
        st.session_state["symbol_auto_refresh_last_error_type"] = type(exc).__name__
        return
    requested_keys.append(request_key)
    st.session_state[SYMBOL_AUTO_REFRESH_REQUEST_STATE_KEY] = requested_keys[
        -SYMBOL_AUTO_REFRESH_REQUEST_KEY_LIMIT:
    ]


def _cockpit_symbol_db_preflight_request_times() -> dict[str, float]:
    raw_request_times = st.session_state.get(COCKPIT_SYMBOL_DB_PREFLIGHT_REQUEST_STATE_KEY, {})
    if not isinstance(raw_request_times, Mapping):
        return {}
    request_times: dict[str, float] = {}
    for raw_symbol, raw_requested_at in raw_request_times.items():
        try:
            request_times[str(raw_symbol)] = float(raw_requested_at)
        except (TypeError, ValueError):
            continue
    return request_times


def _request_cockpit_symbol_db_preflight_background(
    symbol: str,
    *,
    now: float | None = None,
) -> bool:
    target_symbols = _symbol_auto_refresh_symbols(
        [symbol],
        max_symbols=COCKPIT_SYMBOL_DB_PREFLIGHT_MAX_ITEMS,
    )
    if not target_symbols or _background_workers_disabled():
        return False

    current_time = perf_time.monotonic() if now is None else now
    target_symbol = target_symbols[0]
    request_times = _cockpit_symbol_db_preflight_request_times()
    last_requested_at = request_times.get(target_symbol)
    if (
        last_requested_at is not None
        and current_time - last_requested_at < COCKPIT_SYMBOL_DB_PREFLIGHT_TTL_SECONDS
    ):
        return False

    try:
        request_symbol_background_refresh(target_symbols, source="cockpit")
    except Exception as exc:  # noqa: BLE001
        st.session_state[SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY] = type(exc).__name__
        return False

    stale_cutoff = current_time - COCKPIT_SYMBOL_DB_PREFLIGHT_TTL_SECONDS
    request_times = {
        symbol_key: requested_at
        for symbol_key, requested_at in request_times.items()
        if requested_at >= stale_cutoff
    }
    request_times[target_symbol] = current_time
    st.session_state[COCKPIT_SYMBOL_DB_PREFLIGHT_REQUEST_STATE_KEY] = request_times
    st.session_state.pop(SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY, None)
    return True


def ranking_symbol_db_preflight_limit(symbol_count: int) -> int:
    if symbol_count <= 0:
        return 0
    if symbol_count <= RANKING_SYMBOL_DB_PREFLIGHT_DIRECT_THRESHOLD:
        return symbol_count
    return min(symbol_count, RANKING_SYMBOL_DB_PREFLIGHT_MAX_ITEMS)


def ranking_symbol_db_preflight_symbols(symbols: Sequence[str]) -> list[str]:
    return _symbol_auto_refresh_symbols(
        symbols,
        max_symbols=RANKING_SYMBOL_DB_PREFLIGHT_SCAN_LIMIT,
    )


def _run_symbol_database_preflight_refresh(
    symbols: Sequence[str],
    *,
    context: Literal["cockpit", "ranking"],
    max_items: int,
    update_session_state: bool = True,
) -> SymbolStartupRefreshSummary | None:
    max_symbols = RANKING_SYMBOL_DB_PREFLIGHT_SCAN_LIMIT if context == "ranking" else max_items
    target_symbols = _symbol_auto_refresh_symbols(symbols, max_symbols=max_symbols)
    if max_items <= 0 or not target_symbols:
        return None
    try:
        summary = run_symbol_database_target_refresh(
            target_symbols,
            max_items=max_items,
            currently_visible_symbols=target_symbols if context == "cockpit" else None,
            ranking_candidates=target_symbols if context == "ranking" else None,
        )
        try:
            sync_symbol_cache_to_official_metrics(max_items=max_items, symbols=target_symbols)
        except Exception:  # noqa: BLE001 - metric promotion must not block data fetch.
            pass
        if update_session_state:
            st.session_state.pop(SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY, None)
        return summary
    except Exception as exc:  # noqa: BLE001
        if update_session_state:
            st.session_state[SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY] = type(exc).__name__
        return None


def _symbol_auto_refresh_symbols(symbols: Sequence[str], *, max_symbols: int) -> list[str]:
    if max_symbols <= 0:
        return []
    normalized_symbols: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        normalized_symbols.append(normalized_symbol)
        if len(normalized_symbols) >= max(0, max_symbols):
            break
    return normalized_symbols


def _start_news_background_refresh_worker_once() -> None:
    state_key = "news_background_refresh_worker_started"
    if state_key in st.session_state:
        return
    if _background_workers_disabled():
        st.session_state[state_key] = {"disabled": True}
        return
    try:
        start_news_background_refresh_worker(delay_scale=_news_background_refresh_delay_scale())
        st.session_state[state_key] = True
    except Exception as exc:
        st.session_state[state_key] = {
            "failed": True,
            "error_type": type(exc).__name__,
        }


def _news_background_refresh_delay_scale() -> float:
    raw_value = os.environ.get("SMAI_NEWS_BACKGROUND_REFRESH_DELAY_SCALE", "").strip()
    if not raw_value:
        return 1.0
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return 1.0


def _background_workers_disabled() -> bool:
    raw_value = os.environ.get("SMAI_DISABLE_BACKGROUND_WORKERS", "").strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


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
    """Choose a stable trading-day horizon without a fixed upper ceiling."""

    return determine_forecast_horizon(start=start, end=end).horizon_days


def _provider_option_index(provider: str) -> int:
    try:
        return MARKET_DATA_PROVIDER_OPTIONS.index(provider)
    except ValueError:
        return 0


def default_market_data_provider() -> str:
    provider = get_settings().dataaccess.provider
    if provider in MARKET_DATA_PROVIDER_OPTIONS:
        return provider
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


def _ranking_label_from_row(row: Mapping[str, str]) -> str:
    symbol = str(row.get("symbol", ""))
    return f"{symbol} - {row.get('name', symbol)}"


def _default_effective_ranking_labels(
    candidate_rows: list[dict[str, str]],
    *,
    preset: str,
    limit_key: str,
) -> list[str]:
    """Return default ranking targets without materializing the multiselect labels.

    The comparison multiselect is optional and expensive to build for a 10k+
    universe.  In the default path we keep the user-facing meaning of "all
    candidates are selected" while only materializing the final fetch target set.
    """
    limit = ranking_fetch_limit_value(limit_key)
    if limit <= 0 or len(candidate_rows) <= limit:
        return [_ranking_label_from_row(row) for row in candidate_rows]
    # Keep the default route very cheap.  The previous multiselect route
    # materialized labels for the whole universe on every render; here we only
    # create the fetch-target labels needed by the current limit.
    return [_ranking_label_from_row(row) for row in candidate_rows[:limit]]


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


SYMBOL_CACHE_FRESHNESS_LABELS = {
    "fresh": "最新",
    "stale": "やや古い",
    "expired": "古い",
    "missing": "未取得",
}
SYMBOL_CACHE_COMMON_REQUIRED_FIELDS = ("metadata_source", "metadata_as_of")
SYMBOL_CACHE_STOCK_REQUIRED_FIELDS = (
    "per",
    "pbr",
    "roe_pct",
    "dividend_yield_pct",
    "market_cap_tier",
    "risk_band",
)
SYMBOL_CACHE_FUND_REQUIRED_FIELDS = (
    "index_family",
    "expense_ratio_pct",
    "dividend_yield_pct",
    "complexity",
)
SYMBOL_CACHE_MISSING_FIELD_DISPLAY_LIMIT = 6


def _symbol_universe_row_for_symbol(
    symbol: str,
    *,
    include_runtime_cache: bool = False,
) -> dict[str, str] | None:
    normalized_symbol = symbol.strip().upper()
    return _symbol_universe_rows_by_symbol(include_runtime_cache=include_runtime_cache).get(
        normalized_symbol
    )


def _symbol_universe_rows_by_symbol(
    rows: list[dict[str, str]] | None = None,
    *,
    include_runtime_cache: bool = False,
) -> dict[str, dict[str, str]]:
    if rows is not None:
        source_rows = rows
    elif include_runtime_cache:
        source_rows = symbol_universe_runtime_rows()
    else:
        source_rows = symbol_universe_csv_rows()
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


def _symbol_classification_list_display(value: str) -> str:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        return "未登録"
    labels = [
        RANKING_INVESTMENT_THEME_LABELS.get(
            part,
            RANKING_THEME_LABELS.get(part, part),
        )
        for part in parts
    ]
    return "、".join(labels)


def _symbol_detail_lookup_display(column: str, value: str) -> str:
    if not value.strip() or value.strip() == "-":
        return "未登録"
    if column in {"theme"}:
        return RANKING_INVESTMENT_THEME_LABELS.get(value, RANKING_THEME_LABELS.get(value, value))
    if column in {"smai_theme_tags", "tags"}:
        return _symbol_classification_list_display(value)
    if column == "sector":
        return RANKING_OFFICIAL_SECTOR_LABELS.get(value, value)
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
    if column == SYMBOL_CACHE_PROVIDER_FIELD:
        return (
            SYMBOL_UNIVERSE_DISPLAY_LABELS["metadata_source"].get(value, value)
            if value
            else "未登録"
        )
    if column == SYMBOL_CACHE_FRESHNESS_STATUS_FIELD:
        return SYMBOL_CACHE_FRESHNESS_LABELS.get(value, value) if value else "未取得"
    if column in {
        "metadata_as_of",
        "metadata_updated_at",
        SYMBOL_CACHE_UPDATED_AT_FIELD,
        SYMBOL_CACHE_LAST_PRICE_UPDATED_AT_FIELD,
        SYMBOL_CACHE_LAST_FUNDAMENTAL_UPDATED_AT_FIELD,
    }:
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


def symbol_universe_missing_key_fields(row: dict[str, str]) -> list[str]:
    required_fields = list(SYMBOL_CACHE_COMMON_REQUIRED_FIELDS)
    asset_type = _symbol_detail_raw_value(row, "asset_type")
    if asset_type == "etf":
        required_fields.extend(SYMBOL_CACHE_FUND_REQUIRED_FIELDS)
    elif asset_type in {"stock", "adr"} or not asset_type:
        required_fields.extend(SYMBOL_CACHE_STOCK_REQUIRED_FIELDS)
    else:
        required_fields.extend(("dividend_yield_pct", "risk_band"))
    return [
        _symbol_missing_field_label(field)
        for field in required_fields
        if not _symbol_detail_raw_value(row, field)
    ]


def symbol_universe_missing_key_fields_display(row: dict[str, str]) -> str:
    fields = symbol_universe_missing_key_fields(row)
    if not fields:
        return "主要項目は登録済み"
    visible = fields[:SYMBOL_CACHE_MISSING_FIELD_DISPLAY_LIMIT]
    suffix = ""
    remaining_count = len(fields) - len(visible)
    if remaining_count > 0:
        suffix = f" ほか{remaining_count}件"
    return "、".join(visible) + suffix


def _symbol_missing_field_label(field: str) -> str:
    label = SYMBOL_UNIVERSE_DETAIL_LABELS.get(field, field)
    return label.replace("(%)", "")


def symbol_universe_cache_status_text(row: dict[str, str]) -> str:
    status = symbol_universe_detail_display_value(row, SYMBOL_CACHE_FRESHNESS_STATUS_FIELD)
    updated_at = symbol_universe_detail_display_value(row, SYMBOL_CACHE_UPDATED_AT_FIELD)
    provider = symbol_universe_detail_display_value(row, SYMBOL_CACHE_PROVIDER_FIELD)
    if provider == "未登録":
        provider = symbol_universe_detail_display_value(row, "metadata_source")
    parts = [f"銘柄DB: {status}"]
    parts.append(f"最終更新 {updated_at if updated_at != '未登録' else '未取得'}")
    parts.append(f"取得元 {provider}")
    missing_fields = symbol_universe_missing_key_fields(row)
    if missing_fields:
        parts.append(f"不足 {len(missing_fields)}項目")
    return " / ".join(parts)


def symbol_universe_cache_notice(row: dict[str, str]) -> str:
    status = _symbol_detail_raw_value(row, SYMBOL_CACHE_FRESHNESS_STATUS_FIELD) or "missing"
    if status in {"stale", "expired"}:
        return (
            "一部データが古い可能性があります。前回保存値を表示しつつ、"
            "必要に応じてバックグラウンド更新を待ってください。"
        )
    if status == "missing":
        return (
            "保存済み銘柄DBの更新情報はまだありません。"
            "ローカル銘柄マスタの登録値を表示しています。"
        )
    if symbol_universe_missing_key_fields(row):
        return (
            "主要項目の一部が未登録です。"
            "スコアやランキングは取得済みの材料だけで確認してください。"
        )
    return ""


def symbol_universe_cache_status_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        _symbol_data_info_row(
            "銘柄DB鮮度",
            symbol_universe_detail_display_value(row, SYMBOL_CACHE_FRESHNESS_STATUS_FIELD),
            "保存済み銘柄データをそのまま読めるか、再確認が必要かを見ます。",
        ),
        _symbol_data_info_row(
            "銘柄DB最終更新",
            symbol_universe_detail_display_value(row, SYMBOL_CACHE_UPDATED_AT_FIELD),
            "バックグラウンド更新で最後に保存した日時です。",
        ),
        _symbol_data_info_row(
            "銘柄DB取得元",
            symbol_universe_detail_display_value(row, SYMBOL_CACHE_PROVIDER_FIELD),
            "保存済み銘柄DBを更新したproviderです。",
        ),
        _symbol_data_info_row(
            "価格データ更新",
            symbol_universe_detail_display_value(row, SYMBOL_CACHE_LAST_PRICE_UPDATED_AT_FIELD),
            "株価・出来高など価格系データの取得タイミングを確認します。",
        ),
        _symbol_data_info_row(
            "財務データ更新",
            symbol_universe_detail_display_value(
                row, SYMBOL_CACHE_LAST_FUNDAMENTAL_UPDATED_AT_FIELD
            ),
            "PER/PBR/ROE/配当など財務・分類系データの取得タイミングを確認します。",
        ),
        _symbol_data_info_row(
            "不足している主要項目",
            symbol_universe_missing_key_fields_display(row),
            "空欄が多い銘柄では評価材料が少ないため、追加確認が必要です。",
        ),
    ]


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
        _symbol_detail_row(
            "SMAIテーマタグ",
            symbol_universe_detail_display_value(row, "smai_theme_tags"),
        ),
        _symbol_detail_row("業種/セクター", symbol_universe_detail_display_value(row, "sector")),
        _symbol_detail_row(
            "JPX 33業種",
            symbol_universe_detail_display_value(row, "tse_33_industry"),
        ),
        _symbol_detail_row("TOPIX-17", symbol_universe_detail_display_value(row, "topix_17")),
        _symbol_detail_row(
            "GICSセクター",
            symbol_universe_detail_display_value(row, "sector_gics"),
        ),
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
            "値動きリスク",
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
        *symbol_universe_cache_status_rows(row),
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


def _ranking_result_public_column(column: str) -> str:
    return {
        "Screening": "基礎評価",
        "Risk": "リスク",
        "データ品質": "データ信頼度",
        "高度予測": "予測変化率",
        "高度予測日数": "予測日数",
        "高度予測信頼度": "予測確度",
        "方向一致": "モデル方向",
    }.get(column, column)


def _ranking_result_columns(ranking_purpose: str) -> list[str]:
    focus_columns = ranking_purpose_primary_columns(ranking_purpose)
    focus_set = set(focus_columns)
    support_columns: tuple[str, ...] = (
        () if {"条件適合度", "DB信頼度", "根拠状態"}.intersection(focus_set) else ("信頼度/根拠",)
    )
    standard_columns = set(RANKING_TABLE_BASE_COLUMNS).union(RANKING_TABLE_DETAIL_COLUMNS)
    secondary_focus_columns = tuple(
        public_column
        for column in focus_columns
        if (public_column := _ranking_result_public_column(column)) not in standard_columns
    )
    return _dedupe_columns(
        (
            *RANKING_TABLE_BASE_COLUMNS,
            *secondary_focus_columns,
            *support_columns,
            *RANKING_TABLE_HIDDEN_COLUMNS,
        )
    )


def _ranking_result_columns_with_optional_advanced_forecast(
    display_rows: list[dict[str, str]],
    ranking_purpose: str,
    *,
    include_detail_columns: bool = False,
) -> list[str]:
    if not include_detail_columns:
        return _dedupe_columns(
            (
                *RANKING_TABLE_BASE_COLUMNS,
                *RANKING_TABLE_HIDDEN_COLUMNS,
            )
        )
    columns = _ranking_result_columns_with_optional_llm_factor(
        _dedupe_columns(
            (
                *RANKING_TABLE_BASE_COLUMNS,
                *RANKING_TABLE_DETAIL_COLUMNS,
                *_ranking_result_columns(ranking_purpose),
            )
        ),
        display_rows,
    )
    if not _ranking_has_advanced_forecast(display_rows):
        return columns
    return columns


def _ranking_result_columns_with_optional_llm_factor(
    columns: list[str],
    display_rows: list[dict[str, str]],
) -> list[str]:
    if _ranking_has_llm_factor_reference(display_rows):
        return columns
    return [column for column in columns if column not in LLM_FACTOR_RANKING_DETAIL_COLUMNS]


def _ranking_has_advanced_forecast(display_rows: list[dict[str, str]]) -> bool:
    return any(
        _ranking_has_present_display_value(row.get("高度予測"))
        or _ranking_has_present_display_value(row.get("高度予測日数"))
        or _ranking_has_present_display_value(row.get("高度予測スコア"))
        or _ranking_has_present_display_value(row.get("高度予測信頼度"))
        for row in display_rows
    )


def _ranking_has_llm_factor_reference(display_rows: list[dict[str, str]]) -> bool:
    return any(any(column in row for column in LLM_FACTOR_RANKING_COLUMNS) for row in display_rows)


def _ranking_has_present_display_value(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text not in {
        RANKING_MISSING_DISPLAY,
        LLM_FACTOR_RANKING_MISSING_DISPLAY,
        "-",
        "未登録",
        "未取得",
        "取得不可",
        "未計算",
        "未接続",
    }


def normalize_llm_factor_score(score: object) -> Decimal | None:
    if score is None:
        return None
    if isinstance(score, float) and not math.isfinite(score):
        return None
    text = str(score).strip()
    if not text:
        return None
    try:
        value = Decimal(text)
    except Exception:
        return None
    if not value.is_finite():
        return None
    if Decimal("0") <= value <= Decimal("1"):
        value *= Decimal("100")
    value = max(Decimal("0"), min(Decimal("100"), value))
    return value.quantize(Decimal("1"))


def format_llm_factor_score(score: object) -> str:
    normalized = normalize_llm_factor_score(score)
    if normalized is None:
        return LLM_FACTOR_RANKING_MISSING_DISPLAY
    return str(normalized)


def build_llm_factor_reference_display(
    reference: LLMFactorRankingReference | Mapping[str, object] | None,
) -> dict[str, str]:
    values = {
        "bullish": format_llm_factor_score(_llm_factor_reference_value(reference, "bullish_score")),
        "bearish": format_llm_factor_score(_llm_factor_reference_value(reference, "bearish_score")),
        "confidence": format_llm_factor_score(
            _llm_factor_reference_value(reference, "confidence_score")
        ),
        "freshness": format_llm_factor_score(
            _llm_factor_reference_value(reference, "freshness_score")
        ),
    }
    source_count = str(_llm_factor_reference_value(reference, "source_count") or "").strip()
    return {
        "bullishLabel": values["bullish"],
        "bearishLabel": values["bearish"],
        "confidenceLabel": values["confidence"],
        "freshnessLabel": values["freshness"],
        "newsMaterialLabel": f"強気 {values['bullish']} / 弱気 {values['bearish']}",
        "sourceCountLabel": source_count if source_count else LLM_FACTOR_RANKING_MISSING_DISPLAY,
        "bullishAriaLabel": _llm_factor_reference_aria_label(
            "ニュース材料（強気）",
            values["bullish"],
        ),
        "bearishAriaLabel": _llm_factor_reference_aria_label(
            "ニュース材料（弱気）",
            values["bearish"],
        ),
        "confidenceAriaLabel": _llm_factor_reference_aria_label(
            "材料信頼度",
            values["confidence"],
        ),
        "freshnessAriaLabel": _llm_factor_reference_aria_label(
            "材料の新しさ",
            values["freshness"],
        ),
        "sourceLabel": _llm_factor_reference_source_label(reference),
        "warning": str(_llm_factor_reference_value(reference, "warning") or ""),
    }


def ranking_display_rows_with_llm_factor_references(
    display_rows: list[dict[str, str]],
    references: Mapping[str, LLMFactorRankingReference],
) -> list[dict[str, str]]:
    enriched_rows: list[dict[str, str]] = []
    for row in display_rows:
        key = llm_factor_ranking_candidate_key(row)
        display = build_llm_factor_reference_display(references.get(key))
        enriched_rows.append(
            {
                **row,
                "LLM強気材料": display["bullishLabel"],
                "LLM弱気材料": display["bearishLabel"],
                "LLM確信度": display["confidenceLabel"],
                "材料鮮度": display["freshnessLabel"],
                "LLM材料件数": display["sourceCountLabel"],
                "LLM材料元": display["sourceLabel"],
                "LLM材料補足": display["warning"],
            }
        )
    return enriched_rows


def _llm_factor_reference_value(
    reference: LLMFactorRankingReference | Mapping[str, object] | None,
    key: str,
) -> object:
    if reference is None:
        return None
    if isinstance(reference, Mapping):
        return reference.get(key)
    return getattr(reference, key)


def _llm_factor_reference_aria_label(label: str, value: str) -> str:
    if value == LLM_FACTOR_RANKING_MISSING_DISPLAY:
        return f"{label} 未評価 参考指標"
    return f"{label} {value}点 参考指標"


def _llm_factor_reference_source_label(
    reference: LLMFactorRankingReference | Mapping[str, object] | None,
) -> str:
    source_type = str(_llm_factor_reference_value(reference, "source_type") or "unavailable")
    return {
        "cache": "cache",
        "deterministic_fake": "deterministic fake",
        "unavailable": "未評価",
    }.get(source_type, "未評価")


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
        "Screening": "基礎評価",
        "Risk": "リスク",
        "データ品質": "データ信頼度",
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
    advanced_note = _ranking_advanced_forecast_reason_note(row)
    if not metrics:
        return f"{focus}{advanced_note}"
    return f"{' / '.join(metrics)}。{focus}{advanced_note}"


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
    advanced_checkpoint = _ranking_advanced_forecast_checkpoint(row)
    if advanced_checkpoint:
        return advanced_checkpoint
    if ranking_purpose in {"etf_core_cost", "etf_income"}:
        return "連動指数、経費率、分配方針をETF資料で確認します。"
    return "銘柄コックピットで価格・予測・リスクを確認します。"


def _ranking_compact_confirmation_note(reason: str, checkpoint: str) -> str:
    return truncate_text(_ranking_full_confirmation_note(reason, checkpoint), max_chars=96)


def _ranking_compact_smai_memo(row: Mapping[str, str], checkpoint: str) -> str:
    upside = _decimal_from_text(row.get("上昇気配"))
    downside = _decimal_from_text(row.get("下降警戒"))
    predicted_return = _decimal_from_text(row.get("予測変化率"))
    dividend = _decimal_from_text(row.get("配当利回り"))
    per = _decimal_from_text(row.get("PER"))
    roe = _decimal_from_text(row.get("ROE"))
    if (
        predicted_return is not None
        and predicted_return > 0
        and (downside is not None and downside >= Decimal("65"))
    ):
        return "予測は上向きだが、下降警戒が高め。"
    if upside is not None and upside >= Decimal("65"):
        if downside is not None and downside < Decimal("50"):
            return "上昇気配あり。下降警戒は低め。"
        if downside is not None and downside >= Decimal("65"):
            return "上昇気配あり。下降警戒も高め。"
        return "上昇気配あり。下降警戒は中程度。"
    if dividend is not None and dividend >= Decimal("4"):
        return "配当利回りは高め。持続性を確認。"
    if per is not None and per <= Decimal("12") and (roe is None or roe >= Decimal("8")):
        return "割安感あり。ROEと配当利回りを確認。"
    if downside is not None and downside >= Decimal("65"):
        return "下降警戒が高め。価格トレンドを確認。"
    if predicted_return is not None and predicted_return > 0:
        return "予測は上向き。根拠と下降警戒を確認。"
    return truncate_text(
        checkpoint or "銘柄コックピットで価格・予測・リスクを確認。",
        max_chars=42,
    )


def _ranking_news_material_display(row: Mapping[str, str]) -> str:
    bullish = str(row.get("LLM強気材料", "")).strip()
    bearish = str(row.get("LLM弱気材料", "")).strip()
    if not bullish and not bearish:
        return ""
    bullish = bullish or LLM_FACTOR_RANKING_MISSING_DISPLAY
    bearish = bearish or LLM_FACTOR_RANKING_MISSING_DISPLAY
    return f"強気 {bullish} / 弱気 {bearish}"


def _ranking_forecast_confidence_display(row: Mapping[str, str]) -> str:
    return (
        str(row.get("高度予測スコア", "")).strip()
        or str(row.get("高度予測信頼度", "")).strip()
        or RANKING_MISSING_DISPLAY
    )


def _ranking_forecast_basis(row: Mapping[str, str], checkpoint: str) -> str:
    advanced = _ranking_advanced_forecast_display(row)
    direction = str(row.get("方向一致", "")).strip()
    if advanced and direction:
        return f"{advanced} / {direction}"
    if advanced:
        return advanced
    if direction:
        return direction
    return truncate_text(checkpoint, max_chars=72)


def ranking_result_aggrid_frame(
    display_rows: list[dict[str, str]],
    ranking_purpose: str = "multi_factor",
    *,
    include_detail_columns: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    favorite_symbols = {favorite.symbol for favorite in load_favorites()}
    result_columns = _ranking_result_columns_with_optional_advanced_forecast(
        display_rows,
        ranking_purpose,
        include_detail_columns=include_detail_columns,
    )
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
            "お気に入り": (
                "★ 登録済"
                if normalize_favorite_symbol(str(row.get("銘柄", ""))) in favorite_symbols
                else "☆ 追加"
            ),
            "銘柄名": truncate_text(row.get("銘柄名", ""), max_chars=56),
            "総合スコア": row.get("総合スコア", ""),
            "判断方針": row.get("見方", ""),
            "ニュース材料": _ranking_news_material_display(row),
            "材料件数": row.get("LLM材料件数", ""),
            "材料信頼度": row.get("LLM確信度", ""),
            "材料の新しさ": row.get("材料鮮度", ""),
            "LLM強気材料": row.get("LLM強気材料", ""),
            "LLM弱気材料": row.get("LLM弱気材料", ""),
            "LLM確信度": row.get("LLM確信度", ""),
            "材料鮮度": row.get("材料鮮度", ""),
            "基礎評価": row.get("Screening", ""),
            "上昇気配": row.get("上昇気配", ""),
            "上向き兆候": row.get("上向き兆候", ""),
            "20日高値乖離": row.get("20日高値乖離", ""),
            "5日騰落率": row.get("5日騰落率", ""),
            "上向き兆候理由": row.get("上向き兆候理由", ""),
            "下降警戒": row.get("下降警戒", ""),
            "予測変化率": row.get("予測変化率", ""),
            "予測確度": _ranking_forecast_confidence_display(row),
            "予測日数": row.get("高度予測日数", ""),
            "モデル方向": row.get("方向一致", ""),
            "予測根拠": _ranking_forecast_basis(row, checkpoint),
            "高度予測": row.get("高度予測", ""),
            "高度予測日数": row.get("高度予測日数", ""),
            "高度予測スコア": row.get("高度予測スコア", ""),
            "高度予測信頼度": row.get("高度予測信頼度", ""),
            "方向一致": row.get("方向一致", ""),
            "Screening": row.get("Screening", ""),
            "Risk": row.get("Risk", ""),
            "リスク": row.get("Risk", ""),
            "データ品質": row.get("データ品質", ""),
            "データ信頼度": row.get("データ品質", ""),
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
            "株価": _ranking_table_display_value(row.get("株価", "")),
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
            "SMAIメモ": _ranking_compact_smai_memo(row, checkpoint),
            "確認詳細": _ranking_full_confirmation_note(reason, checkpoint),
            "並べ替え理由": reason,
            "確認ポイント": checkpoint,
        }
        rows.append({column: record.get(column, "") for column in result_columns})
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
    return build_ranking_aggrid_options(frame, RANKING_TABLE_CONFIG)


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


def ranking_favorite_symbol_from_aggrid_response(grid_response: object) -> str | None:
    event_data = _aggrid_event_data(grid_response)
    column_id = str(event_data.get("colId") or "").strip()
    column = event_data.get("column")
    if not column_id and isinstance(column, dict):
        column_id = str(column.get("colId") or "").strip()
    if column_id != "お気に入り":
        return None
    symbol = _ranking_symbol_from_row(event_data.get("data"))
    if symbol:
        return normalize_favorite_symbol(symbol)
    node = event_data.get("node")
    if isinstance(node, dict):
        symbol = _ranking_symbol_from_row(node.get("data"))
        if symbol:
            return normalize_favorite_symbol(symbol)
    return None


def ranking_favorite_event_token_from_aggrid_response(
    grid_response: object,
    favorite_symbol: str | None,
) -> str | None:
    if not favorite_symbol:
        return None
    event_data = _aggrid_event_data(grid_response)
    trigger_name = str(event_data.get("streamlitRerunEventTriggerName") or "cellClicked")
    row_index = event_data.get("rowIndex")
    mouse_event = event_data.get("event")
    timestamp = event_data.get("timeStamp")
    if timestamp is None and isinstance(mouse_event, dict):
        timestamp = mouse_event.get("timeStamp")
    return f"{trigger_name}|favorite|{favorite_symbol}|{row_index}|{timestamp}"


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


def _ensure_selectbox_state_value(
    key: str,
    options: list[str],
    *,
    default_value: str | None = None,
) -> None:
    default = default_value if default_value in options else options[0]
    value = _ranking_filter_value(key, default)
    if value not in options:
        value = default
    if key not in st.session_state or st.session_state.get(key) != value:
        st.session_state[key] = value


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
    compact: bool = False,
) -> tuple[bool, float, float]:
    min_input_value = _coerce_number_input_state(min_key, min_default)
    max_input_value = _coerce_number_input_state(max_key, max_default)
    if compact:
        enabled = st.checkbox(
            label,
            value=_ranking_filter_bool(enabled_key, False),
            key=enabled_key,
            help=help_text,
            disabled=disabled,
        )
        col_min, col_max = st.columns(2)
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
    _ensure_selectbox_state_value(key, options, default_value=default)
    return cast(
        str,
        st.selectbox(
            label,
            options,
            key=key,
            format_func=cast(Any, format_func),
            help=help_text,
            disabled=disabled,
        ),
    )


def _filter_options_with_available_counts(
    labels: Mapping[str, str],
    counts: Mapping[str, int],
) -> list[str]:
    options = ["all"] if "all" in labels else []
    options.extend(key for key in labels if key != "all" and int(counts.get(key, 0)) > 0)
    return options or list(labels)


def _counted_filter_label(
    labels: Mapping[str, str],
    counts: Mapping[str, int],
    value: str,
) -> str:
    label = labels.get(value, value)
    if value == "all":
        return label
    return f"{label}（{int(counts.get(value, 0)):,}件）"


def _classification_count_base_rows(
    rows: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
) -> list[dict[str, str]]:
    return filter_symbol_universe_rows(
        rows,
        region=region,
        product_type=product_type,
        limit=len(rows),
        active_detail_filters=(),
    )


def _ranking_detail_filter_mode_caption(product_type: str) -> str:
    if product_type == RANKING_PRODUCT_ETF:
        return (
            "ETF向け条件です。連動指数・経費率・分配金・複雑さを中心に表示し、"
            "PER/PBR/ROEなど個別株向け指標は表示しません。"
        )
    if product_type == RANKING_PRODUCT_STOCK:
        return (
            "株式向け条件です。公式業種、SMAI投資テーマ、時価総額、PER/PBR/ROE、"
            "配当利回りを中心に表示します。米国以外の外国株ではPER/PBR/ROEを抑え、"
            "通貨・データ品質・流動性確認を優先します。"
        )
    if product_type == RANKING_PRODUCT_MUTUAL_FUND:
        return "投信向け条件です。信託報酬、NISA、商品複雑性を中心に表示します。"
    return (
        "商品タイプ未指定のため、株式・ETFで共通して使いやすい条件を中心に表示します。"
        "PER/PBR/ROEは、株式を選んだ時だけ表示します。"
    )


def _ranking_filter_counts_by_category(
    rows: list[dict[str, str]],
    categories: Iterable[str],
) -> dict[str, dict[str, int]]:
    return {
        category: symbol_universe_filter_value_counts(rows, category) for category in categories
    }


def _ranking_counted_options(
    labels: Mapping[str, str],
    counts_by_category: Mapping[str, Mapping[str, int]],
    category: str,
) -> list[str]:
    return _filter_options_with_available_counts(labels, counts_by_category.get(category, {}))


def _ranking_counted_label(
    labels: Mapping[str, str],
    counts_by_category: Mapping[str, Mapping[str, int]],
    category: str,
    value: str,
) -> str:
    return _counted_filter_label(labels, counts_by_category.get(category, {}), value)


def _render_metric_filter_grid(
    filters: list[tuple[str, dict[str, object]]],
    *,
    columns_per_row: int = 2,
    compact: bool = False,
) -> None:
    for start_index in range(0, len(filters), columns_per_row):
        row_filters = filters[start_index : start_index + columns_per_row]
        columns = st.columns(len(row_filters))
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
                    compact=compact,
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
    row = _symbol_universe_row_for_symbol(symbol, include_runtime_cache=True)
    if row is None:
        st.warning("銘柄マスタに該当するデータが見つかりませんでした。")
        return
    st.markdown(SYMBOL_DETAIL_DIALOG_CSS, unsafe_allow_html=True)
    display_name = row.get("name") or symbol
    st.subheader(f"{symbol} - {display_name}")
    st.caption("ローカル銘柄マスタの登録値を、確認しやすい項目に整理しています。")
    st.caption(symbol_universe_cache_status_text(row))
    cache_notice = symbol_universe_cache_notice(row)
    if cache_notice:
        cache_status = _symbol_detail_raw_value(row, SYMBOL_CACHE_FRESHNESS_STATUS_FIELD)
        if cache_status in {"stale", "expired"}:
            st.warning(cache_notice)
        else:
            st.caption(cache_notice)

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
    # The ranking axis and scope already appear in the result header. Keep this
    # row focused on quantities that change after a ranking run.
    _ = ranking_axis, weight_preset, region, product_type
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
                "score": (
                    row.get("上向き兆候", "未計算")
                    if ranking_purpose == "reversal_expectation"
                    else row.get("総合スコア", "未計算")
                ),
                "score_label": (
                    "上向き兆候" if ranking_purpose == "reversal_expectation" else "総合スコア"
                ),
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
                "reversal": row.get("上向き兆候", ""),
                "reversal_reason": row.get("上向き兆候理由", ""),
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
    metric_label = _ranking_display_column_label(metric_column)
    return (
        f"{policy_label}のランキング基準に基づく上位候補です。"
        f"代表指標「{metric_label}」は{order_text}に表示します。"
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
            "観点": "基礎評価",
            "値": selected_row.get("Screening", "未計算"),
            "確認ポイント": "市場データ由来の基礎評価です。モメンタム、流動性、リスクの偏りを確認します。",
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
            "確認ポイント": (
                "投資魅力度ではなく、評価材料の充実度です。低い場合はスコア解釈を控えめにします。"
            ),
        },
        {
            "観点": "リスク",
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
    advanced_value = _ranking_advanced_forecast_display(selected_row)
    if advanced_value:
        rows.insert(
            3,
            {
                "観点": ADVANCED_FORECAST_CONSENSUS_LABEL,
                "値": advanced_value,
                "確認ポイント": (
                    "取得期間から決まる共通予測日数のAI予測シナリオです。"
                    "上昇気配・下降警戒へ25%まで反映し、信頼度で控えめに扱います。"
                ),
            },
        )
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
            f"信頼度 {confidence or '未計算'}。注意点があるため、根拠カードと内訳を確認します。",
            max_chars=56,
        )
    return truncate_text(
        f"信頼度 {confidence or '未計算'}。売買推奨ではなく、資料の充実度確認です。",
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


def _ranking_advanced_forecast_display(row: Mapping[str, str]) -> str:
    parts: list[str] = []
    horizon = _ranking_advanced_forecast_horizon_display(row)
    predicted_return = _ranking_advanced_forecast_return_display(row)
    if _ranking_has_present_display_value(predicted_return):
        prefix = f"{horizon} " if _ranking_has_present_display_value(horizon) else ""
        parts.append(f"{prefix}{predicted_return}")
    score = _ranking_advanced_forecast_score_display(row)
    if _ranking_has_present_display_value(score):
        parts.append(f"スコア {score}")
    confidence = _ranking_advanced_forecast_confidence_display(row)
    if _ranking_has_present_display_value(confidence):
        parts.append(f"信頼度 {confidence}")
    return " / ".join(parts)


def _ranking_advanced_forecast_horizon_display(row: Mapping[str, str]) -> str:
    value = row.get("高度予測日数") or row.get("advanced_forecast_horizon_days") or ""
    if not _ranking_has_present_display_value(value):
        return ""
    text = str(value).strip()
    return text if text.endswith("日") else f"{text}日"


def _ranking_advanced_forecast_return_display(row: Mapping[str, str]) -> str:
    value = row.get("高度予測") or row.get("advanced_forecast_predicted_return") or ""
    return str(value).strip()


def _ranking_advanced_forecast_score_display(row: Mapping[str, str]) -> str:
    value = row.get("高度予測スコア") or row.get("advanced_forecast_score") or ""
    return str(value).strip()


def _ranking_advanced_forecast_confidence_display(row: Mapping[str, str]) -> str:
    value = row.get("高度予測信頼度") or row.get("advanced_forecast_confidence") or ""
    text = str(value).strip()
    if not text:
        return ""
    normalized = text.lower()
    if normalized in {"high", "medium", "low"}:
        return _advanced_forecast_confidence_label(normalized)
    return _advanced_forecast_confidence_label(text)


def _ranking_advanced_forecast_confidence_key(row: Mapping[str, str]) -> str:
    value = row.get("advanced_forecast_confidence") or row.get("高度予測信頼度") or ""
    text = str(value).strip().lower()
    aliases = {
        "高め": "high",
        "中くらい": "medium",
        "低め": "low",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }
    return aliases.get(text, "")


def _ranking_advanced_forecast_reason_note(row: Mapping[str, str]) -> str:
    if not _ranking_advanced_forecast_display(row):
        return ""
    horizon = _ranking_advanced_forecast_horizon_display(row)
    predicted_return = _ranking_advanced_forecast_return_display(row)
    confidence = _ranking_advanced_forecast_confidence_display(row)
    target = f"{horizon} {predicted_return}".strip() or "中心予測"
    if confidence == "低め":
        confidence_note = "信頼度低めのため控えめに読みます。"
    elif confidence:
        confidence_note = f"信頼度は{confidence}です。"
    else:
        confidence_note = "信頼度もあわせて確認します。"
    return (
        f" AI予測インサイトは{target}を上昇気配・下降警戒へ25%まで反映しています。"
        f"{confidence_note}"
    )


def _ranking_advanced_forecast_checkpoint(row: Mapping[str, str]) -> str:
    if not _ranking_advanced_forecast_display(row):
        return ""
    if _ranking_advanced_forecast_confidence_key(row) == "low":
        return (
            "AI予測インサイトの信頼度が低めです。上昇気配・下降警戒は控えめに読み、"
            "価格レンジとモデル合意度を確認します。"
        )
    return (
        "AI予測インサイトを上昇気配・下降警戒へ25%まで反映しています。"
        "中心予測と予測レンジを銘柄コックピットで確認します。"
    )


def _ranking_advanced_forecast_report_summary(row: Mapping[str, str]) -> str:
    display = _ranking_advanced_forecast_display(row)
    if not display:
        return ""
    return f"{ADVANCED_FORECAST_CONSENSUS_LABEL}: {display}"


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
    if ranking_purpose == RANKING_PURPOSE_MULTI_FACTOR:
        context_cards = [
            {
                "label": row["group"],
                "value": row["weight"],
                "help": "このランキング基準での合計重みです。",
                "badge": "重み",
            }
            for row in ranking_weight_group_rows(weight_preset)
        ]
        column_count = 3
    else:
        context_cards = ranking_purpose_context_cards(ranking_purpose, limit=4)
        column_count = 4
    columns = st.columns(max(1, min(column_count, len(context_cards))))
    for index, card in enumerate(context_cards):
        value = card.get("value", "")
        progress = metric_progress_from_value(value) if value.endswith("%") else None
        with columns[index % len(columns)]:
            render_metric_card(
                card.get("label", ""),
                value,
                caption=card.get("help", ""),
                badges=(badge_html(card.get("badge", "重み"), "info"),),
                tone="info",
                progress=progress,
            )
    st.caption(
        f"評価プロファイル: {ranking_weight_preset_label(weight_preset)}。"
        "ランキング基準は売買推奨ではなく、比較・深掘り候補の採点軸です。"
    )


def _render_ranking_condition_card(
    ranking_purpose: str,
    weight_preset: str,
    *,
    forecast_horizon_days: int,
) -> None:
    st.markdown(
        _ranking_condition_card_html(
            ranking_purpose,
            weight_preset,
            forecast_horizon_days=forecast_horizon_days,
        ),
        unsafe_allow_html=True,
    )
    if ranking_purpose == "reversal_expectation":
        with st.expander("上向き兆候スコアの詳しい計算方法を見る", expanded=False):
            st.markdown(
                "上向き兆候は、単に「下がった銘柄」を高く評価する指標ではありません。"
                "下落・調整・横ばいから上向きに変わる兆しと、下落リスクを確認します。"
            )
            st.markdown("#### 6つの評価要素")
            st.dataframe(
                reversal_expectation_component_rows(),
                hide_index=True,
                use_container_width=True,
            )
            st.markdown("#### 押し目状態の点数表")
            st.dataframe(
                reversal_expectation_pullback_rows(),
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                "上の基礎点に、5日騰落率が -8%以下なら -25点、小幅マイナスなら +5点、"
                "+5%超なら上昇済みとして -15点を調整します。各内訳は0〜100点に収めます。"
            )
            st.markdown("#### 危険な状態は上限固定ではなく段階的に減点")
            st.dataframe(
                reversal_expectation_cap_rows(),
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                "最後に、上向き兆候 → 下落安全性 → 予測変化率 → 下降警戒の低さ → "
                "AI総合 → 銘柄コードの順で並べます。危険条件を減点した後、50点付近の差が"
                "読み取りやすくなるよう0〜100点へ滑らかに広げます。AI総合スコア自体は変更しません。"
            )


def _ranking_condition_card_html(
    ranking_purpose: str,
    weight_preset: str,
    *,
    forecast_horizon_days: int,
) -> str:
    description = ranking_policy_description(ranking_purpose)
    group_rows = ranking_weight_group_rows(weight_preset)
    group_items = "".join(
        "<div>"
        f"<span>{html.escape(row['group'])}</span>"
        f"<strong>{html.escape(row['weight'])}</strong>"
        "</div>"
        for row in group_rows
    )
    focus_items = "".join(
        f"<span>{html.escape(item)}</span>" for item in description["main_focus"][:6]
    )
    purpose = ranking_policy_label(ranking_purpose)
    profile = ranking_weight_preset_label(weight_preset)
    reversal_explanation = (
        '<div class="smai-ranking-condition-note">'
        "<strong>上向き兆候をひとことで</strong><br>"
        "まだ大きく上がっていない銘柄から、押し目反発・底打ち・横ばい上放れなど、"
        "上向きに変わる兆しを探します。買い時や底打ち確定を示すものではありません。"
        "<br>上昇気配は、すでに上向きの強さが出ている銘柄を評価します。"
        "<br><br><strong>計算式</strong><br>"
        "チャート形状 30% ＋ 予測上向き余地 25% ＋ 下落安全性 20% ＋ "
        "押し目・安定度 10% ＋ 企業・配当品質 10% ＋ 上向き材料 5%。"
        "データ品質は原則スコアに入れず、価格データ不足など致命的な場合だけ未評価にします。"
        "急落・高い下降警戒などは上限固定ではなく段階的に減点します。"
        "</div>"
        if ranking_purpose == "reversal_expectation"
        else ""
    )
    return (
        '<div class="smai-section-card smai-ranking-condition-card">'
        '<div class="smai-card-label">今回のランキング条件</div>'
        f'<p class="smai-ranking-policy-summary">{html.escape(description["short_summary"])}</p>'
        '<div class="smai-ranking-condition-grid">'
        "<div>"
        f'<div class="smai-insight-kicker">ランキング基準</div><strong>{html.escape(purpose)}</strong>'
        f"<p>{html.escape(description['suited_for'])}</p>"
        "</div>"
        "<div>"
        '<div class="smai-insight-kicker">ランキング評価用予測期間</div>'
        f"<strong>{forecast_horizon_days}日</strong>"
        "<p>同じランキング内では共通の予測期間で比較します。</p>"
        "</div>"
        "<div>"
        '<div class="smai-insight-kicker">AI予測の扱い</div>'
        "<strong>控えめに反映</strong>"
        "<p>AI予測インサイトは順位を直接支配せず、上昇気配・下降警戒・信頼度として使います。</p>"
        "</div>"
        "</div>"
        f'<div class="smai-ranking-focus-chips">{focus_items}</div>'
        '<div class="smai-ranking-weight-grid">'
        f"{group_items}"
        "</div>"
        f'<p class="smai-ranking-condition-note">評価プロファイル: {html.escape(profile)}。'
        f"{html.escape(RANKING_DOWNSIDE_LOW_IS_BETTER_NOTE)} "
        f"{html.escape(description['caution'])} "
        "この画面は比較候補を整理するためのもので、売買推奨ではありません。</p>"
        f"{reversal_explanation}"
        "</div>"
    )


def ranking_forecast_term_explanation_rows() -> list[dict[str, str]]:
    """Return beginner-friendly Ranking forecast signal explanations."""

    return [
        {
            "表示": "AI総合",
            "意味": "基礎評価、予測・上昇気配、リスク、データ信頼度、Research確認材料をまとめた比較用スコアです。",
            "ランキングでの扱い": "既定の総合比較です。AI予測は控えめに加味し、単独で順位を決めません。",
            "確認ポイント": "高順位でも、上昇気配・下降警戒・データ信頼度の偏りを一緒に確認します。",
        },
        {
            "表示": "上昇気配",
            "意味": "予測エッジ、直近トレンド、モデル方向感を合わせた上向き材料の強さです。",
            "ランキングでの扱い": "高いほど上向き候補として見ます。AI予測インサイトがある場合は25%までブレンドします。",
            "確認ポイント": "下降警戒も高い場合は、上下どちらにも振れやすい候補として慎重に読みます。",
        },
        {
            "表示": "下降警戒",
            "意味": "下向きシグナル、予測下限、価格変動リスクを合わせた注意度です。",
            "ランキングでの扱い": "低いほど良い指標です。AI予測インサイトの下振れ警戒も25%までブレンドします。",
            "確認ポイント": "高い場合は、価格トレンド、予測レンジ下限、Riskを先に確認します。",
        },
        {
            "表示": "AI予測インサイト",
            "意味": "複数の高度予測モデルを、信頼度・誤差改善・モデル合意度・検証数で重みづけした統合予測です。",
            "ランキングでの扱い": "上昇気配、下降警戒、高度予測信頼の材料として控えめに使います。",
            "確認ポイント": "予測日数、レンジの広さ、モデル合意度、注意点をコックピットで確認します。",
        },
        {
            "表示": "高度予測上昇",
            "意味": "AI予測インサイトの予測変化率とモデル合意度から見た上向き寄与です。",
            "ランキングでの扱い": "AI総合の一部として小さく加味します。低信頼時は中立50へ寄せます。",
            "確認ポイント": "単純な上昇予想ではなく、信頼度と検証指標込みの補助材料として読みます。",
        },
        {
            "表示": "高度予測下振れ警戒",
            "意味": "AI予測インサイトの予測下限、ばらつき、低信頼を反映した下振れ注意度です。",
            "ランキングでの扱い": "低いほど良い指標です。AI総合では警戒が低い候補を相対的に評価します。",
            "確認ポイント": "予測レンジが広い場合は、中央値よりも下限シナリオを優先して確認します。",
        },
        {
            "表示": "高度予測信頼",
            "意味": "モデル合意度、誤差改善、予測ばらつき、検証サンプルを合わせた予測材料のそろい方です。",
            "ランキングでの扱い": "高いほどAI予測を少し使いやすくします。低い場合は予測スコアを中立へ戻します。",
            "確認ポイント": "信頼度は投資魅力度ではなく、予測をどの程度参考にするかの目安です。",
        },
        {
            "表示": "予測日数",
            "意味": "取得期間から自動計算した共通の予測先です。",
            "ランキングでの扱い": "同じランキング内では共通の日数で比較し、銘柄間の見方をそろえます。",
            "確認ポイント": "短期取得では短期寄り、長期取得では中期寄りになります。",
        },
    ]


def _render_ranking_criteria_guide() -> None:
    with st.expander("ランキング基準・条件・信頼度の読み方", expanded=False):
        st.caption(
            "ランキング基準は取得後の並べ替え、詳細条件は取得前の候補絞り込みです。"
            "条件適合度とDB信頼度は、銘柄の良し悪しではなく評価材料のそろい方として読みます。"
        )
        st.markdown(SYMBOL_DETAIL_DIALOG_CSS, unsafe_allow_html=True)
        guide_rows = [
            {"表示": row["表示"], "使う場面": row["使う場面"], "読み方": row["読み方"]}
            for row in RANKING_CRITERIA_GUIDE_ROWS
        ]
        st.markdown(
            symbol_detail_table_html(guide_rows),
            unsafe_allow_html=True,
        )
        st.markdown("##### AI総合・予測/警戒指標の読み方")
        st.markdown(
            symbol_detail_table_html(ranking_forecast_term_explanation_rows()),
            unsafe_allow_html=True,
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
    primary_score_line = f"{primary_label} {primary_value}".strip()
    reason = card.get("reason", "")
    if reason.startswith(primary_score_line):
        reason = reason[len(primary_score_line) :].lstrip(" /\u3000")
    progress = metric_progress_from_value(primary_value)
    safe_progress = min(100, max(0, int(progress))) if progress is not None else 0
    badges = (
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
    caption = reason
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
    if requested_profile.key == PROFILE_REVERSAL_EXPECTATION:
        _render_ranking_reversal_evidence_map(display_rows, requested_profile)
        return
    selection = ranking_chart_frame(display_rows, requested_profile)
    if selection is None:
        return
    render_section_heading(selection.profile.title)
    if selection.used_fallback:
        st.caption(
            "指定条件向けの列が不足している、または同じ値に偏っているため、"
            f"代替チャート `{selection.profile.title}` を表示しています。"
        )
    st.caption("選択中のランキング基準とは別に、候補の期待・警戒バランスを確認する補助グラフです。")
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
    if selection.profile.key == "reversal_expectation":
        chart_tooltips = [
            alt.Tooltip("symbol:N", title="銘柄コード"),
            alt.Tooltip("name:N", title="銘柄名"),
            alt.Tooltip("upward_signal:N", title="上向き兆候スコア"),
            alt.Tooltip("shape_label:N", title="チャート形状"),
            alt.Tooltip("adjustment_stability:N", title="調整/安定度"),
            alt.Tooltip("upward_potential:N", title="上向き余地"),
            alt.Tooltip("downside_safety:N", title="下落安全性"),
            alt.Tooltip("downside_warning:N", title="下降警戒"),
            alt.Tooltip("dividend_trap:N", title="配当罠警戒"),
            alt.Tooltip("signal_reason:N", title="上向き兆候理由"),
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
            "下落安全性",
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
    if selection.size_column and selection.frame["size_value"].notna().any():
        encoding["size"] = alt.Size(
            "size_value:Q",
            title=selection.size_column,
            scale=alt.Scale(range=[45, 180]),
        )
    chart = (
        alt.Chart(selection.frame)
        .mark_circle(size=90, opacity=0.78)
        .encode(**encoding)
        .properties(height=320)
    )
    st.altair_chart(style_altair_chart(chart), use_container_width=True)


def _render_ranking_reversal_evidence_map(
    display_rows: list[dict[str, str]],
    profile: RankingChartProfile,
) -> None:
    frame = ranking_reversal_evidence_frame(display_rows)
    render_section_heading(profile.title)
    st.caption(profile.description)
    with st.expander("読み方", expanded=False):
        for item in profile.how_to_read:
            st.caption(f"- {item}")
        st.caption(profile.caution)
    if frame.empty:
        st.info("上向き兆候の構成スコアを表示できる候補がありません。")
        return

    tooltip = [
        alt.Tooltip("rank:N", title="順位"),
        alt.Tooltip("symbol:N", title="銘柄コード"),
        alt.Tooltip("name:N", title="銘柄名"),
        alt.Tooltip("component:N", title="評価要素"),
        alt.Tooltip("score:Q", title="構成スコア", format=".1f"),
        alt.Tooltip("quality_status:N", title="評価可否"),
        alt.Tooltip("data_quality:N", title="データ品質"),
        alt.Tooltip("shape_label:N", title="チャート形状"),
        alt.Tooltip("signal_reason:N", title="上向き兆候理由"),
        alt.Tooltip("trap_warning:N", title="警戒事項"),
    ]
    base = alt.Chart(frame)
    cells = base.mark_rect(cornerRadius=3).encode(
        x=alt.X(
            "component:N",
            title=None,
            sort=alt.SortField("component_order", order="ascending"),
            axis=alt.Axis(labelAngle=0, labelLimit=90),
        ),
        y=alt.Y(
            "candidate_label:N",
            title=None,
            sort=alt.SortField("rank_order", order="ascending"),
            axis=alt.Axis(labelLimit=190),
        ),
        color=alt.Color(
            "score:Q",
            title="構成スコア",
            scale=alt.Scale(
                domain=[0, 50, 100],
                range=[
                    THEME_COLORS["bg_elevated"],
                    THEME_COLORS["ai_blue"],
                    THEME_COLORS["ai_cyan"],
                ],
            ),
        ),
        tooltip=tooltip,
    )
    labels = base.mark_text(fontSize=12, fontWeight=600).encode(
        x=alt.X(
            "component:N",
            sort=alt.SortField("component_order", order="ascending"),
        ),
        y=alt.Y(
            "candidate_label:N",
            sort=alt.SortField("rank_order", order="ascending"),
        ),
        text=alt.Text("score_label:N"),
        color=alt.condition(
            "datum.score >= 72",
            alt.value(THEME_COLORS["bg_app"]),
            alt.value(THEME_COLORS["text_primary"]),
        ),
        tooltip=tooltip,
    )
    candidate_states = frame.drop_duplicates(subset=["candidate_label"])
    state_counts = candidate_states["quality_status"].value_counts().to_dict()
    chart = (cells + labels).properties(
        height=max(320, min(430, 34 * len(candidate_states))),
    )
    st.altair_chart(style_altair_chart(chart), use_container_width=True)
    st.caption(
        "データ品質（このマップでは魅力度軸に使わない評価可否）: "
        f"評価可能 {state_counts.get('評価可能', 0)}件 / "
        f"要確認 {state_counts.get('要確認', 0)}件 / "
        f"評価対象外 {state_counts.get('評価対象外', 0)}件"
    )


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


def _ranking_forecast_direction_text(row: Mapping[str, str]) -> str:
    predicted_return = _decimal_from_text(row.get("予測変化率"))
    if predicted_return is None:
        return "未判定"
    if predicted_return > Decimal("0"):
        return "上向き"
    if predicted_return < Decimal("0"):
        return "下向き"
    return "横ばい"


def ranking_selected_detail_memo_rows(
    display_rows: list[dict[str, str]],
    selected_symbol: str | None,
    *,
    ranking_purpose: str,
) -> list[dict[str, str]]:
    selected_row = _ranking_display_row_for_symbol(display_rows, selected_symbol or "")
    if selected_row is None:
        return []
    direction_limited = _ranking_direction_data_limited(display_rows)
    focus_columns = _ranking_reason_columns(display_rows, ranking_purpose)
    reason = ranking_purpose_row_reason(
        selected_row,
        ranking_purpose,
        focus_columns=focus_columns,
        direction_limited=direction_limited,
    )
    checkpoint = ranking_purpose_row_checkpoint(selected_row, ranking_purpose)
    forecast_return = _display_table_value(selected_row.get("予測変化率"))
    direction_text = _ranking_forecast_direction_text(selected_row)
    forecast_basis = _ranking_forecast_basis(selected_row, checkpoint)
    if not forecast_basis:
        forecast_basis = "複数指標の見方を銘柄コックピットで確認してください。"
    confirmation = checkpoint
    if not confirmation:
        confirmation = "PER、PBR、ROE、配当利回り、直近ニュース・開示を確認してください。"
    return [
        {
            "項目": "銘柄",
            "内容": f"{selected_row.get('銘柄', '')} {selected_row.get('銘柄名', '')}".strip(),
        },
        {
            "項目": "総合スコア",
            "内容": selected_row.get("総合スコア", RANKING_MISSING_DISPLAY),
        },
        {
            "項目": "判断方針",
            "内容": selected_row.get("見方", RANKING_MISSING_DISPLAY),
        },
        {
            "項目": "SMAI判断",
            "内容": (
                f"上昇気配 {selected_row.get('上昇気配', RANKING_MISSING_DISPLAY)} / "
                f"下降警戒 {selected_row.get('下降警戒', RANKING_MISSING_DISPLAY)}。"
                f"予測変化率 {forecast_return}、方向感は{direction_text}です。"
            ),
        },
        {
            "項目": "予測根拠",
            "内容": forecast_basis,
        },
        {
            "項目": "確認ポイント",
            "内容": truncate_text(f"{confirmation} {reason}", max_chars=140),
        },
    ]


def _render_ranking_selected_detail_memo(
    display_rows: list[dict[str, str]],
    selected_symbol: str | None,
    *,
    ranking_purpose: str,
) -> None:
    rows = ranking_selected_detail_memo_rows(
        display_rows,
        selected_symbol,
        ranking_purpose=ranking_purpose,
    )
    if not rows:
        return
    st.markdown("##### 選択銘柄の詳細メモ")
    st.caption("テーブル内に収めにくい判断理由と確認ポイントを、選択行に合わせて整理します。")
    st.markdown(SYMBOL_DETAIL_DIALOG_CSS, unsafe_allow_html=True)
    st.markdown(symbol_detail_table_html(rows), unsafe_allow_html=True)


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
        st.markdown("##### スコアと信頼度の読み分け")
        _render_score_confidence_hierarchy()


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
    if error_rows:
        total_count = len(display_rows) + len(error_rows)
        st.warning(
            f"対象 {total_count}件のうち {len(error_rows)}件は価格データを取得できませんでした。"
            "結果には取得できた銘柄のみ表示しています。"
        )
    with st.expander("データ状態", expanded=False):
        st.dataframe(detail_rows, hide_index=True, use_container_width=True)
        st.caption("テーブル内のソート、検索、絞り込みでは外部取得を実行しません。")


def _render_ranking_result_table(
    display_rows: list[dict[str, str]],
    *,
    ranking_source: str,
    weight_preset: str,
    ranking_purpose: str,
    mode: Literal["live", "history"] = "live",
) -> None:
    if not display_rows:
        st.info(EMPTY_STATE_MESSAGES["ranking_rows"])
        return
    table_base_key = _ranking_result_table_base_key(ranking_source, weight_preset)
    grid_key = _ranking_result_grid_key(table_base_key)
    st.caption(
        "カードやグラフで気になる候補を絞ったあと、詳細を確認するためのテーブルです。"
        "行をクリックすると、銘柄データや確認ポイントを確認できます。"
    )
    if mode == "history":
        st.caption("お気に入り操作は現在のプロフィール状態に反映されます。")
    show_detail_columns = st.checkbox(
        "詳細列を表示する",
        value=False,
        key=f"{table_base_key}_show_detail_columns",
        help="ニュース材料、モデル方向、予測根拠、データ信頼度などの補助列を追加表示します。",
    )
    if _ranking_has_llm_factor_reference(display_rows):
        st.caption(LLM_FACTOR_RANKING_REFERENCE_NOTICE)
    st.caption(RANKING_TABLE_SORT_GUIDANCE)
    frame = ranking_result_aggrid_frame(
        display_rows,
        ranking_purpose=ranking_purpose,
        include_detail_columns=show_detail_columns,
    )
    grid_response = AgGrid(
        frame,
        gridOptions=ranking_result_aggrid_options(frame, ranking_purpose=ranking_purpose),
        height=_ranking_result_grid_height(display_rows),
        update_on=["cellClicked"],
        data_return_mode=DataReturnMode.AS_INPUT,
        theme="dark",
        custom_css=RANKING_RESULT_GRID_CUSTOM_CSS,
        key=grid_key,
        show_toolbar=False,
        show_search=False,
        show_download_button=False,
        allow_unsafe_jscode=True,
    )
    favorite_symbol = ranking_favorite_symbol_from_aggrid_response(grid_response)
    if favorite_symbol:
        favorite_event_token = ranking_favorite_event_token_from_aggrid_response(
            grid_response,
            favorite_symbol,
        )
        favorite_event_state_key = f"{table_base_key}_last_favorite_event_token"
        if (
            favorite_event_token
            and st.session_state.get(favorite_event_state_key) == favorite_event_token
        ):
            return
        if favorite_event_token:
            st.session_state[favorite_event_state_key] = favorite_event_token
        universe_row = _symbol_universe_rows_by_symbol().get(favorite_symbol, {})
        now_active = toggle_favorite(
            favorite_symbol,
            metadata={
                "name": universe_row.get("name") or universe_row.get("銘柄名"),
                "market": universe_row.get("market") or universe_row.get("市場"),
                "asset_type": universe_row.get("asset_type") or universe_row.get("商品"),
                "currency": universe_row.get("currency") or universe_row.get("通貨"),
                "source_screen": "ranking_table",
            },
        )
        st.toast(
            "Myウォッチリストに追加しました。"
            if now_active
            else "Myウォッチリストから解除しました。"
        )
        st.rerun()
        return
    selected_symbol = ranking_detail_symbol_from_aggrid_response(grid_response)
    if mode == "history":
        return
    _render_ranking_selected_detail_memo(
        display_rows,
        selected_symbol,
        ranking_purpose=ranking_purpose,
    )
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


def _ranking_filter_state_snapshot() -> dict[str, str | bool]:
    return {
        "market_data_ranking_currency": _ranking_filter_value(
            "market_data_ranking_currency", "all"
        ),
        "market_data_ranking_dividend": _ranking_filter_value(
            "market_data_ranking_dividend", "all"
        ),
        "market_data_ranking_min_dividend": _ranking_filter_value(
            "market_data_ranking_min_dividend", "0.0"
        ),
        "market_data_ranking_market_cap": _ranking_filter_value(
            "market_data_ranking_market_cap", "all"
        ),
        "market_data_ranking_index_family": _ranking_filter_value(
            "market_data_ranking_index_family", "all"
        ),
        "market_data_ranking_max_expense": _ranking_filter_value(
            "market_data_ranking_max_expense", "1.00"
        ),
        "market_data_ranking_complexity": _ranking_filter_value(
            "market_data_ranking_complexity", "standard"
        ),
        "market_data_ranking_nisa": _ranking_filter_value("market_data_ranking_nisa", "all"),
        "market_data_ranking_risk_band": _ranking_filter_value(
            "market_data_ranking_risk_band", "all"
        ),
        "market_data_ranking_official_sector": _ranking_filter_value(
            "market_data_ranking_official_sector", "all"
        ),
        "market_data_ranking_theme": _ranking_filter_value("market_data_ranking_theme", "all"),
        "market_data_ranking_symbol_query": _ranking_filter_value(
            "market_data_ranking_symbol_query", ""
        ),
        "market_data_ranking_per_enabled": _ranking_filter_bool(
            "market_data_ranking_per_enabled", False
        ),
        "market_data_ranking_per_min": _ranking_filter_value("market_data_ranking_per_min", "2.0"),
        "market_data_ranking_per_max": _ranking_filter_value("market_data_ranking_per_max", "20.0"),
        "market_data_ranking_pbr_enabled": _ranking_filter_bool(
            "market_data_ranking_pbr_enabled", False
        ),
        "market_data_ranking_pbr_min": _ranking_filter_value("market_data_ranking_pbr_min", "0.5"),
        "market_data_ranking_pbr_max": _ranking_filter_value("market_data_ranking_pbr_max", "2.0"),
        "market_data_ranking_dividend_enabled": _ranking_filter_bool(
            "market_data_ranking_dividend_enabled", False
        ),
        "market_data_ranking_dividend_max": _ranking_filter_value(
            "market_data_ranking_dividend_max", "10.0"
        ),
        "market_data_ranking_roe_enabled": _ranking_filter_bool(
            "market_data_ranking_roe_enabled", False
        ),
        "market_data_ranking_roe_min": _ranking_filter_value("market_data_ranking_roe_min", "8.0"),
        "market_data_ranking_roe_max": _ranking_filter_value("market_data_ranking_roe_max", "30.0"),
        "market_data_ranking_consensus_enabled": _ranking_filter_bool(
            "market_data_ranking_consensus_enabled", False
        ),
        "market_data_ranking_consensus_min": _ranking_filter_value(
            "market_data_ranking_consensus_min", "2.5"
        ),
        "market_data_ranking_consensus_max": _ranking_filter_value(
            "market_data_ranking_consensus_max", "5.0"
        ),
    }


def ranking_condition_has_active_detail_from_values(values: Mapping[str, object]) -> bool:
    selector_defaults = {
        "market_data_ranking_currency": "all",
        "market_data_ranking_dividend": "all",
        "market_data_ranking_market_cap": "all",
        "market_data_ranking_index_family": "all",
        "market_data_ranking_complexity": "standard",
        "market_data_ranking_nisa": "all",
        "market_data_ranking_risk_band": "all",
        "market_data_ranking_official_sector": "all",
        "market_data_ranking_theme": "all",
        "market_data_ranking_symbol_query": "",
    }
    for key, default in selector_defaults.items():
        if str(values.get(key, default)).strip() != default:
            return True
    metric_enabled_keys = (
        "market_data_ranking_dividend_enabled",
        "market_data_ranking_per_enabled",
        "market_data_ranking_pbr_enabled",
        "market_data_ranking_roe_enabled",
        "market_data_ranking_consensus_enabled",
    )
    return any(_truthy_filter_value(values.get(key, False)) for key in metric_enabled_keys)


def clear_ranking_detail_condition_state() -> None:
    top_level_keys = {
        "market_data_ranking_region",
        "market_data_ranking_product_type",
        "market_data_ranking_policy",
        "market_data_ranking_purpose",
        "market_data_ranking_fetch_limit",
        "market_data_ranking_period",
    }
    detail_defaults = {
        key: default
        for key, default in {
            **RANKING_FILTER_DEFAULTS,
            **RANKING_METRIC_FILTER_DEFAULTS,
        }.items()
        if key not in top_level_keys
    }
    for key, default in detail_defaults.items():
        if isinstance(default, bool):
            st.session_state[key] = default
        elif key.endswith(("_min", "_max")) or key in {
            "market_data_ranking_min_dividend",
            "market_data_ranking_dividend_max",
            "market_data_ranking_max_expense",
        }:
            st.session_state[key] = float(default)
        else:
            st.session_state[key] = default
    st.session_state.pop(MARKET_DATA_RANKING_FILTERS_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_RANKING_SELECTED_LABELS_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_RANKING_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_RANKING_ERROR_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_RANKING_UPDATED_AT_STATE_KEY, None)


def ranking_condition_summary_chips_from_values(
    values: Mapping[str, object],
    *,
    region: str,
    product_type: str,
    ranking_policy: str,
    period_preset: str,
    candidate_count: int,
) -> list[dict[str, str]]:
    chips = [
        {"label": ranking_region_label(region), "tone": "neutral"},
        {"label": ranking_product_type_label(product_type), "tone": "neutral"},
        {"label": ranking_policy_label(ranking_policy), "tone": "policy"},
        {"label": ranking_period_label(period_preset), "tone": "neutral"},
    ]
    detail_chips = _ranking_detail_condition_chips(values, product_type=product_type)
    if detail_chips:
        chips.extend({"label": label, "tone": "active"} for label in detail_chips[:8])
    else:
        chips.append({"label": "詳細条件なし", "tone": "neutral"})
    if len(detail_chips) > 8:
        chips.append({"label": f"ほか{len(detail_chips) - 8}件", "tone": "active"})
    tone = "warning" if candidate_count == 0 else "count"
    chips.append({"label": f"候補 {candidate_count:,}件", "tone": tone})
    return chips


def _ranking_detail_condition_chips(
    values: Mapping[str, object],
    *,
    product_type: str,
) -> list[str]:
    chips: list[str] = []
    official_sector = str(values.get("market_data_ranking_official_sector", "all"))
    theme = str(values.get("market_data_ranking_theme", "all"))
    market_cap_tier = str(values.get("market_data_ranking_market_cap", "all"))
    risk_band = str(values.get("market_data_ranking_risk_band", "all"))
    nisa = str(values.get("market_data_ranking_nisa", "all"))
    dividend_category = str(values.get("market_data_ranking_dividend", "all"))
    currency = str(values.get("market_data_ranking_currency", "all"))
    index_family = str(values.get("market_data_ranking_index_family", "all"))
    complexity = str(values.get("market_data_ranking_complexity", "standard"))
    query = str(values.get("market_data_ranking_symbol_query", "")).strip()
    if nisa != "all":
        chips.append(_cockpit_nisa_chip_label(nisa))
    if official_sector != "all":
        label = _short_filter_label(
            RANKING_OFFICIAL_SECTOR_LABELS.get(official_sector, official_sector)
        )
        chips.append(f"業種: {label}")
    if theme != "all":
        label = _short_filter_label(RANKING_INVESTMENT_THEME_LABELS.get(theme, theme))
        chips.append(f"テーマ: {label}")
    if market_cap_tier != "all":
        label = _short_filter_label(RANKING_MARKET_CAP_LABELS.get(market_cap_tier, market_cap_tier))
        chips.append(f"規模: {label}")
    if risk_band != "all":
        label = _short_filter_label(RANKING_BETA_RISK_LABELS.get(risk_band, risk_band))
        chips.append(f"β: {label}")
    if dividend_category != "all":
        label = _dividend_category_option_label(dividend_category, product_type)
        chips.append(_short_filter_label(label))
    if currency != "all":
        chips.append(f"通貨: {RANKING_CURRENCY_LABELS.get(currency, currency)}")
    if index_family != "all":
        chips.append(f"指数: {RANKING_INDEX_FAMILY_LABELS.get(index_family, index_family)}")
    if complexity != "standard":
        chips.append(f"複雑さ: {RANKING_COMPLEXITY_LABELS.get(complexity, complexity)}")
    if query:
        chips.append(f"検索: {query}")
    if _truthy_filter_value(values.get("market_data_ranking_dividend_enabled", False)):
        chips.append(
            _range_filter_chip(
                _income_distribution_label(product_type) + "利回り",
                values.get("market_data_ranking_min_dividend", "0.0"),
                values.get("market_data_ranking_dividend_max", "10.0"),
                "%",
            )
        )
    stock_metrics_visible = product_type == RANKING_PRODUCT_STOCK
    if stock_metrics_visible and _truthy_filter_value(
        values.get("market_data_ranking_per_enabled", False)
    ):
        chips.append(
            _range_filter_chip(
                "PER",
                values.get("market_data_ranking_per_min", "2.0"),
                values.get("market_data_ranking_per_max", "20.0"),
            )
        )
    if stock_metrics_visible and _truthy_filter_value(
        values.get("market_data_ranking_pbr_enabled", False)
    ):
        chips.append(
            _range_filter_chip(
                "PBR",
                values.get("market_data_ranking_pbr_min", "0.5"),
                values.get("market_data_ranking_pbr_max", "2.0"),
            )
        )
    if stock_metrics_visible and _truthy_filter_value(
        values.get("market_data_ranking_roe_enabled", False)
    ):
        chips.append(
            _range_filter_chip(
                "ROE",
                values.get("market_data_ranking_roe_min", "8.0"),
                values.get("market_data_ranking_roe_max", "30.0"),
                "%",
            )
        )
    if _truthy_filter_value(values.get("market_data_ranking_consensus_enabled", False)):
        chips.append(
            _range_filter_chip(
                "市場評価",
                values.get("market_data_ranking_consensus_min", "2.5"),
                values.get("market_data_ranking_consensus_max", "5.0"),
            )
        )
    return chips


def _ranking_filtered_symbol_rows_from_state(
    symbol_options: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
    purpose: str,
) -> list[dict[str, str]]:
    values = _ranking_filter_state_snapshot()
    sync_ranking_exploration_legacy_state()
    base_rows = filter_symbol_universe_rows(
        symbol_options,
        region=region,
        product_type=product_type,
        ranking_purpose=RANKING_PURPOSE_MULTI_FACTOR,
        purpose=purpose,
        market="all",
        asset_type="all",
        currency=str(values["market_data_ranking_currency"]),
        dividend_category=str(values["market_data_ranking_dividend"]),
        min_dividend_yield_pct=str(values["market_data_ranking_min_dividend"]),
        market_cap_tier=str(values["market_data_ranking_market_cap"]),
        index_family=str(values["market_data_ranking_index_family"]),
        max_expense_ratio_pct=str(values["market_data_ranking_max_expense"]),
        complexity=str(values["market_data_ranking_complexity"]),
        nisa_eligibility=str(values["market_data_ranking_nisa"]),
        risk_band=str(values["market_data_ranking_risk_band"]),
        official_sector=str(values["market_data_ranking_official_sector"]),
        theme=str(values["market_data_ranking_theme"]),
        query=str(values["market_data_ranking_symbol_query"]),
        per_enabled=bool(values["market_data_ranking_per_enabled"]),
        per_min=str(values["market_data_ranking_per_min"]),
        per_max=str(values["market_data_ranking_per_max"]),
        pbr_enabled=bool(values["market_data_ranking_pbr_enabled"]),
        pbr_min=str(values["market_data_ranking_pbr_min"]),
        pbr_max=str(values["market_data_ranking_pbr_max"]),
        dividend_yield_enabled=bool(values["market_data_ranking_dividend_enabled"]),
        dividend_yield_max_pct=str(values["market_data_ranking_dividend_max"]),
        roe_enabled=bool(values["market_data_ranking_roe_enabled"]),
        roe_min_pct=str(values["market_data_ranking_roe_min"]),
        roe_max_pct=str(values["market_data_ranking_roe_max"]),
        consensus_enabled=bool(values["market_data_ranking_consensus_enabled"]),
        consensus_min=str(values["market_data_ranking_consensus_min"]),
        consensus_max=str(values["market_data_ranking_consensus_max"]),
        limit=len(symbol_options),
    )
    return apply_ranking_applied_exploration_filters(base_rows)


_RANKING_FILTER_ROWS_CACHE_KEY = "market_data_ranking_filter_rows_cache_v3"
_RANKING_CLASSIFICATION_COUNTS_CACHE_KEY = "market_data_ranking_classification_counts_cache_v3"
_RANKING_LAST_APPLIED_ROWS_STATE_KEY = "market_data_ranking_last_applied_filtered_rows_v1"
_RANKING_FILTER_COUNT_CATEGORIES = (
    "official_sector",
    "investment_theme",
    "market_cap",
    "risk_band",
    "nisa_eligibility",
    "benchmark_index",
    "complexity",
    "dividend_category",
    "currency",
)


def _symbol_options_signature(symbol_options: list[dict[str, str]]) -> tuple[object, ...]:
    if not symbol_options:
        return (0,)
    symbols = [str(row.get("symbol", "")) for row in symbol_options]
    return (
        len(symbol_options),
        tuple(symbols[:8]),
        tuple(symbols[-8:]),
    )


def _cacheable_filter_value(value: object) -> object:
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(k), _cacheable_filter_value(v)) for k, v in value.items()))
    return str(value)


def _ranking_filter_rows_signature(
    symbol_options: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
    purpose: str,
) -> tuple[object, ...]:
    values = _ranking_filter_state_snapshot()
    # Exploration filters are applied immediately to candidate rows, but ranking
    # results are rebuilt only after the explicit ランキング作成 button.
    applied_filters = applied_exploration_filters()
    return (
        _symbol_options_signature(symbol_options),
        region,
        product_type,
        purpose,
        tuple(sorted((str(k), _cacheable_filter_value(v)) for k, v in values.items())),
        tuple(sorted((str(k), tuple(v)) for k, v in applied_filters.items())),
    )


def _ranking_filtered_symbol_rows_cache_lookup(
    symbol_options: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
    purpose: str,
) -> list[dict[str, str]] | None:
    signature = _ranking_filter_rows_signature(
        symbol_options,
        region=region,
        product_type=product_type,
        purpose=purpose,
    )
    cache = st.session_state.setdefault(_RANKING_FILTER_ROWS_CACHE_KEY, {})
    cached = cache.get(signature)
    if isinstance(cached, list):
        return cast(list[dict[str, str]], cached)
    return None


def _ranking_filtered_symbol_rows_cached(
    symbol_options: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
    purpose: str,
) -> list[dict[str, str]]:
    cached = _ranking_filtered_symbol_rows_cache_lookup(
        symbol_options,
        region=region,
        product_type=product_type,
        purpose=purpose,
    )
    if cached is not None:
        return cached
    signature = _ranking_filter_rows_signature(
        symbol_options,
        region=region,
        product_type=product_type,
        purpose=purpose,
    )
    rows = _ranking_filtered_symbol_rows_from_state(
        symbol_options,
        region=region,
        product_type=product_type,
        purpose=purpose,
    )
    cache = st.session_state.setdefault(_RANKING_FILTER_ROWS_CACHE_KEY, {})
    cache.clear()
    cache[signature] = rows
    return rows


def _last_applied_filtered_rows() -> list[dict[str, str]]:
    cached = st.session_state.get(_RANKING_LAST_APPLIED_ROWS_STATE_KEY)
    return cast(list[dict[str, str]], cached) if isinstance(cached, list) else []


def _set_last_applied_filtered_rows(rows: list[dict[str, str]]) -> None:
    st.session_state[_RANKING_LAST_APPLIED_ROWS_STATE_KEY] = rows


def _ranking_classification_counts_cache_lookup(
    symbol_options: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
) -> dict[str, dict[str, int]] | None:
    signature = (_symbol_options_signature(symbol_options), region, product_type)
    cache = st.session_state.setdefault(_RANKING_CLASSIFICATION_COUNTS_CACHE_KEY, {})
    cached = cache.get(signature)
    if isinstance(cached, dict):
        return cast(dict[str, dict[str, int]], cached)
    return None


def _ranking_classification_counts_cached(
    symbol_options: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
) -> dict[str, dict[str, int]]:
    signature = (_symbol_options_signature(symbol_options), region, product_type)
    cache = st.session_state.setdefault(_RANKING_CLASSIFICATION_COUNTS_CACHE_KEY, {})
    cached = cache.get(signature)
    if cached is not None:
        return cached
    classification_base_rows = _classification_count_base_rows(
        symbol_options,
        region=region,
        product_type=product_type,
    )
    counts = _ranking_filter_counts_by_category(
        classification_base_rows,
        _RANKING_FILTER_COUNT_CATEGORIES,
    )
    cache.clear()
    cache[signature] = counts
    return counts


def _render_ranking_filter_panel_modal_backdrop(
    symbol_options: list[dict[str, str]],
    *,
    product_type: str,
) -> None:
    """Draw a lightweight non-interactive backdrop while a filter dialog is open.

    Streamlit reruns on every widget action, so the previous DOM cannot be kept
    literally frozen from Python. This backdrop intentionally avoids rebuilding
    selectboxes, numeric inputs, keyword inputs, candidate rows, and summary
    counts. It preserves the user's visual context behind the modal with static
    markup plus the exploration cards.
    """
    st.markdown(
        """
        <style>
        .smai-filter-backdrop-static {
            border: 1px solid rgba(105, 145, 190, 0.22);
            border-radius: 0.9rem;
            background: rgba(8, 23, 43, 0.54);
            padding: 0.8rem;
            margin-bottom: 0.75rem;
        }
        .smai-filter-backdrop-section-title {
            color: #e5f2ff;
            font-weight: 800;
            margin: 0.2rem 0 0.25rem;
        }
        .smai-filter-backdrop-caption {
            color: #a9bdd8;
            font-size: 0.86rem;
            margin: 0 0 0.65rem;
        }
        .smai-filter-backdrop-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.55rem;
            margin-bottom: 0.75rem;
        }
        .smai-filter-backdrop-field {
            min-height: 3.1rem;
            border: 1px solid rgba(130, 170, 220, 0.20);
            border-radius: 0.55rem;
            background: rgba(10, 26, 48, 0.58);
            padding: 0.45rem 0.6rem;
        }
        .smai-filter-backdrop-field span {
            display: block;
            color: #8fa7c7;
            font-size: 0.72rem;
            margin-bottom: 0.16rem;
        }
        .smai-filter-backdrop-field strong {
            color: #dcecff;
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("詳細条件で候補を絞り込む", expanded=True):
        render_ranking_exploration_filter_cards(
            symbol_options,
            product_type=product_type,
            render_dialog=False,
        )
        st.markdown(
            """
            <div class="smai-filter-backdrop-static">
              <div class="smai-filter-backdrop-section-title">属性条件</div>
              <p class="smai-filter-backdrop-caption">モーダル表示中は背景条件を固定表示しています。候補行・件数集計は再計算しません。</p>
              <div class="smai-filter-backdrop-grid">
                <div class="smai-filter-backdrop-field"><span>時価総額</span><strong>現在の設定を保持</strong></div>
                <div class="smai-filter-backdrop-field"><span>値動きリスク</span><strong>現在の設定を保持</strong></div>
                <div class="smai-filter-backdrop-field"><span>NISA</span><strong>現在の設定を保持</strong></div>
                <div class="smai-filter-backdrop-field"><span>配当カテゴリ</span><strong>現在の設定を保持</strong></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="smai-filter-backdrop-static">
              <div class="smai-filter-backdrop-section-title">数値条件・キーワード検索</div>
              <p class="smai-filter-backdrop-caption">モーダル表示中は入力欄を再生成せず、前回の条件を維持します。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_ranking_filter_panel(
    symbol_options: list[dict[str, str]],
    *,
    region: str,
    product_type: str,
    ranking_policy: str,
    period_preset: str,
    purpose: str,
    summary_container: _StreamlitEmptyContainer | None = None,
) -> list[dict[str, str]]:
    sync_ranking_exploration_legacy_state()
    modal_open = ranking_filter_dialog_is_open()

    if modal_open:
        # Fast path: opening a Streamlit dialog still reruns Python, but it should not
        # rebuild detail widgets, recalculate candidates, or regenerate summaries.
        # Draw only a static backdrop plus the active dialog. The dialog itself reads
        # product-only static option caches and updates draft state only.
        _render_ranking_filter_panel_modal_backdrop(
            symbol_options,
            product_type=product_type,
        )
        render_active_ranking_filter_dialog(
            symbol_options,
            product_type=product_type,
        )
        return _last_applied_filtered_rows()

    detail_filters = set(ranking_detail_filters_for_category(region, product_type))
    if "dividend_yield" in detail_filters:
        _normalize_dividend_filter_state()

    filtered_rows = _ranking_filtered_symbol_rows_cached(
        symbol_options,
        region=region,
        product_type=product_type,
        purpose=purpose,
    )
    _set_last_applied_filtered_rows(filtered_rows)

    summary_slot = summary_container.empty() if summary_container is not None else None
    if summary_slot is not None:
        summary_candidate_count = len(filtered_rows)
        summary_slot.markdown(
            _ranking_condition_summary_html(
                _ranking_filter_state_snapshot(),
                region=region,
                product_type=product_type,
                ranking_policy=ranking_policy,
                period_preset=period_preset,
                candidate_count=summary_candidate_count,
                extra_chips=ranking_exploration_filter_chip_labels(),
                draft=False,
            ),
            unsafe_allow_html=True,
        )

    with st.expander("詳細条件・キーワードで候補を絞り込む", expanded=False):
        render_ranking_exploration_filter_cards(
            symbol_options,
            product_type=product_type,
        )

        st.markdown(
            '<div class="smai-ranking-builder-subhead">属性条件</div>'
            '<p class="smai-ranking-builder-caption">銘柄の種類や投資スタイルで絞ります。</p>',
            unsafe_allow_html=True,
        )
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

        cached_detail_filter_counts = _ranking_classification_counts_cache_lookup(
            symbol_options,
            region=region,
            product_type=product_type,
        )
        if modal_open and cached_detail_filter_counts is not None:
            detail_filter_counts = cached_detail_filter_counts
        elif modal_open:
            detail_filter_counts = {}
        else:
            detail_filter_counts = _ranking_classification_counts_cached(
                symbol_options,
                region=region,
                product_type=product_type,
            )
        official_sector_options = _ranking_counted_options(
            RANKING_OFFICIAL_SECTOR_LABELS,
            detail_filter_counts,
            "official_sector",
        )
        investment_theme_options = _ranking_counted_options(
            RANKING_INVESTMENT_THEME_LABELS,
            detail_filter_counts,
            "investment_theme",
        )
        st.markdown(
            f'<p class="smai-ranking-builder-caption">{html.escape(_ranking_detail_filter_mode_caption(product_type))}</p>',
            unsafe_allow_html=True,
        )

        if False and "official_sector" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "業種・セクター",
                    options=official_sector_options,
                    key="market_data_ranking_official_sector",
                    format_func=lambda value: _ranking_counted_label(
                        RANKING_OFFICIAL_SECTOR_LABELS,
                        detail_filter_counts,
                        "official_sector",
                        value,
                    ),
                    help_text=RANKING_FILTER_HELP_TEXTS["official_sector"],
                )
        if False and "investment_theme" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "投資テーマ",
                    options=investment_theme_options,
                    key="market_data_ranking_theme",
                    format_func=lambda value: _ranking_counted_label(
                        RANKING_INVESTMENT_THEME_LABELS,
                        detail_filter_counts,
                        "investment_theme",
                        value,
                    ),
                    help_text=RANKING_FILTER_HELP_TEXTS["investment_theme"],
                )
        if "market_cap" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "時価総額",
                    options=_ranking_counted_options(
                        RANKING_MARKET_CAP_LABELS,
                        detail_filter_counts,
                        "market_cap",
                    ),
                    key="market_data_ranking_market_cap",
                    format_func=lambda value: _ranking_counted_label(
                        RANKING_MARKET_CAP_LABELS,
                        detail_filter_counts,
                        "market_cap",
                        value,
                    ),
                    help_text="大型株・中型株・小型株など、企業規模で候補を絞ります。",
                )
        if "risk_band" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "値動きリスク",
                    options=_ranking_counted_options(
                        RANKING_BETA_RISK_LABELS,
                        detail_filter_counts,
                        "risk_band",
                    ),
                    key="market_data_ranking_risk_band",
                    format_func=lambda value: _ranking_counted_label(
                        RANKING_BETA_RISK_LABELS,
                        detail_filter_counts,
                        "risk_band",
                        value,
                    ),
                    help_text=(
                        "取得元のbetaを低め・標準・高めの帯に整理した参考区分です。"
                        "厳密なβ値そのものではなく、値動きの確認材料として使います。"
                    ),
                )
        if "nisa_eligibility" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "NISA",
                    options=_ranking_counted_options(
                        RANKING_NISA_ELIGIBILITY_LABELS,
                        detail_filter_counts,
                        "nisa_eligibility",
                    ),
                    key="market_data_ranking_nisa",
                    format_func=lambda value: _ranking_counted_label(
                        RANKING_NISA_ELIGIBILITY_LABELS,
                        detail_filter_counts,
                        "nisa_eligibility",
                        value,
                    ),
                    help_text="NISA対象銘柄に絞る場合に使います。",
                )
        if "benchmark_index" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    "連動指数",
                    options=_ranking_counted_options(
                        RANKING_INDEX_FAMILY_LABELS,
                        detail_filter_counts,
                        "benchmark_index",
                    ),
                    key="market_data_ranking_index_family",
                    format_func=lambda value: _ranking_counted_label(
                        RANKING_INDEX_FAMILY_LABELS,
                        detail_filter_counts,
                        "benchmark_index",
                        value,
                    ),
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
                    options=_ranking_counted_options(
                        RANKING_COMPLEXITY_LABELS,
                        detail_filter_counts,
                        "complexity",
                    ),
                    key="market_data_ranking_complexity",
                    format_func=lambda value: _ranking_counted_label(
                        RANKING_COMPLEXITY_LABELS,
                        detail_filter_counts,
                        "complexity",
                        value,
                    ),
                    help_text=RANKING_FILTER_HELP_TEXTS["complexity"],
                )
        if "dividend_yield" in detail_filters:
            with next_column():
                _render_detail_selectbox(
                    _dividend_category_filter_label(product_type),
                    options=_ranking_counted_options(
                        RANKING_DIVIDEND_LABELS,
                        detail_filter_counts,
                        "dividend_category",
                    ),
                    key="market_data_ranking_dividend",
                    format_func=lambda value: _counted_filter_label(
                        {
                            key: _dividend_category_option_label(key, product_type)
                            for key in RANKING_DIVIDEND_LABELS
                        },
                        detail_filter_counts.get("dividend_category", {}),
                        value,
                    ),
                    help_text="配当・分配金の特徴で候補を絞ります。",
                    disabled=dividend_category_disabled,
                )
        with next_column():
            _render_detail_selectbox(
                "通貨",
                options=_ranking_counted_options(
                    RANKING_CURRENCY_LABELS,
                    detail_filter_counts,
                    "currency",
                ),
                key="market_data_ranking_currency",
                format_func=lambda value: _ranking_counted_label(
                    RANKING_CURRENCY_LABELS,
                    detail_filter_counts,
                    "currency",
                    value,
                ),
                help_text="銘柄やETFの通貨で候補を絞ります。",
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
                        "help_text": (
                            "高配当候補を探す時に使います。" "高すぎる利回りは注意が必要です。"
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
                        "help_text": (
                            "利益に対する株価の水準です。低いほど割安に見えますが、"
                            "業績悪化の可能性も確認してください。"
                        ),
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
                        "help_text": (
                            "純資産に対する株価の水準です。低いほど割安に見えますが、"
                            "低評価の理由も確認します。"
                        ),
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
                        "help_text": "資本効率を見る指標です。高いほど収益性が高い傾向があります。",
                    },
                )
            )
        if metric_filters:
            st.markdown(
                '<div class="smai-ranking-builder-subhead">数値条件</div>'
                '<p class="smai-ranking-builder-caption">'
                "PER・PBR・ROE・配当利回りなどで絞ります。"
                "</p>",
                unsafe_allow_html=True,
            )
            _render_metric_filter_grid(metric_filters, columns_per_row=4, compact=True)

        st.button(
            "詳細条件・検索をクリア",
            on_click=clear_ranking_detail_condition_state,
        )

    # The dedicated candidate breakdown card was removed from the main path.
    # Ranking candidates are summarized by _ranking_condition_summary_html instead,
    # avoiding a second dynamic summary that made the lower page appear to redraw.
    if summary_slot is not None:
        summary_candidate_count = len(filtered_rows)
        summary_slot.markdown(
            _ranking_condition_summary_html(
                _ranking_filter_state_snapshot(),
                region=region,
                product_type=product_type,
                ranking_policy=ranking_policy,
                period_preset=period_preset,
                candidate_count=summary_candidate_count,
                extra_chips=ranking_exploration_filter_chip_labels(),
                draft=False,
            ),
            unsafe_allow_html=True,
        )
    return filtered_rows


def _ranking_condition_summary_html(
    values: Mapping[str, object],
    *,
    region: str,
    product_type: str,
    ranking_policy: str,
    period_preset: str,
    candidate_count: int,
    load_state: Mapping[str, str] | None = None,
    extra_chips: Sequence[str] = (),
    draft: bool = False,
) -> str:
    chips = ranking_condition_summary_chips_from_values(
        values,
        region=region,
        product_type=product_type,
        ranking_policy=ranking_policy,
        period_preset=period_preset,
        candidate_count=candidate_count,
    )
    if extra_chips:
        insert_at = max(len(chips) - 1, 0)
        for label in reversed(list(extra_chips)[:6]):
            chips.insert(insert_at, {"label": label, "tone": "active"})
    load_tone = str((load_state or {}).get("tone", "ok"))
    load_suffix = str((load_state or {}).get("suffix", "")).strip()
    load_message = str((load_state or {}).get("message", "")).strip()
    load_class = f" smai-ranking-builder-head--load-{html.escape(load_tone)}"
    candidate_line = f"目安候補 {candidate_count:,}件" if draft else f"候補 {candidate_count:,}件"
    if load_suffix:
        candidate_line = f"{candidate_line}：{load_suffix}"
    load_message_html = (
        f'<p class="smai-ranking-condition-load-message">{html.escape(load_message)}</p>'
        if load_message
        else ""
    )
    description_html = (
        "<p>条件は変更されています。ランキング結果にはまだ反映していません。</p>"
        if draft
        else "<p>ここで絞った候補だけを、選択中のランキング基準で並べます。</p>"
    )
    return (
        f'<section class="smai-ranking-builder-head{load_class}">'
        '<div class="smai-card-label">ランキング候補</div>'
        '<div class="smai-ranking-builder-title-row">'
        f"<strong>{html.escape(candidate_line)}</strong>"
        "</div>"
        f"{description_html}"
        '<div class="smai-ranking-current-inline">'
        '<span class="smai-ranking-current-heading">現在の条件</span>'
        f"{ranking_condition_summary_chips_html(chips)}"
        "</div>"
        f"{load_message_html}"
        "</section>"
    )


def ranking_condition_load_state(build_target_count: int) -> dict[str, str]:
    if build_target_count <= 50:
        return {"tone": "ok", "suffix": "", "message": ""}
    if build_target_count <= 300:
        return {
            "tone": "caution",
            "suffix": "候補が少し多めです",
            "message": "作成に少し時間がかかる場合があります。",
        }
    if build_target_count <= 500:
        return {
            "tone": "warning",
            "suffix": "候補が多めです",
            "message": "作成に時間がかかる場合があります。",
        }
    return {
        "tone": "danger",
        "suffix": "候補が多めです",
        "message": "絞り込むと、作成時間を短くできます。",
    }


def _cockpit_filter_state_snapshot() -> dict[str, str | bool]:
    snapshot: dict[str, str | bool] = {}
    for key, default in MARKET_DATA_COCKPIT_FILTER_DEFAULTS.items():
        if isinstance(default, bool):
            snapshot[key] = _cockpit_filter_bool(key, default)
        else:
            snapshot[key] = _cockpit_filter_value(key, default)
    return snapshot


def cockpit_filter_summary_chips_from_values(
    values: Mapping[str, object],
    *,
    candidate_count: int,
) -> list[dict[str, str]]:
    region = str(values.get("market_data_cockpit_region", "all"))
    product_type = str(values.get("market_data_cockpit_product_type", "all"))
    nisa = str(values.get("market_data_cockpit_nisa", "all"))
    chips = [
        {"label": _cockpit_region_chip_label(region), "tone": "neutral"},
        {"label": _cockpit_nisa_chip_label(nisa), "tone": "neutral"},
        {"label": _cockpit_product_chip_label(product_type), "tone": "neutral"},
    ]
    detail_chips = _cockpit_filter_detail_chips_v2(values, product_type=product_type)
    if detail_chips:
        chips.extend({"label": label, "tone": "active"} for label in detail_chips)
    elif not cockpit_filter_has_active_conditions_from_values(values):
        chips.append({"label": "条件なし", "tone": "neutral"})
    chips.append({"label": f"候補 {candidate_count}件", "tone": "count"})
    return chips


def cockpit_filter_summary_chips_html(chips: Sequence[Mapping[str, str]]) -> str:
    chip_html = "".join(
        (
            '<span class="smai-cockpit-filter-chip '
            f'smai-cockpit-filter-chip--{html.escape(chip.get("tone", "neutral"))}">'
            f'{html.escape(chip.get("label", ""))}</span>'
        )
        for chip in chips
    )
    return f'<div class="smai-cockpit-filter-chip-row">{chip_html}</div>'


def cockpit_filter_expander_label(chips: Sequence[Mapping[str, str]]) -> str:
    labels = [str(chip.get("label", "")).strip() for chip in chips if chip.get("label")]
    summary = " / ".join(labels)
    if not summary:
        return "銘柄を絞り込む"
    return f"銘柄を絞り込む　現在の条件: {summary}"


def _truthy_filter_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _cockpit_region_chip_label(value: str) -> str:
    return RANKING_MVP_REGION_LABELS.get(value, value)


def _cockpit_product_chip_label(value: str) -> str:
    if value == "all":
        return "商品指定なし"
    return RANKING_MVP_PRODUCT_TYPE_LABELS.get(value, value)


def _cockpit_nisa_chip_label(value: str) -> str:
    if value == "all":
        return "NISA指定なし"
    if value == "eligible":
        return "NISA対象"
    if value == "none":
        return "NISA対象外"
    return _short_filter_label(RANKING_NISA_ELIGIBILITY_LABELS.get(value, value))


def _short_filter_label(label: str) -> str:
    return re.split(r"[（(]", label, maxsplit=1)[0].strip()


def _compact_filter_number(value: object) -> str:
    try:
        number = Decimal(str(value))
    except Exception:  # noqa: BLE001
        return str(value)
    if number == number.to_integral_value():
        return str(number.quantize(Decimal("1")))
    return format(number.normalize(), "f").rstrip("0").rstrip(".")


def _range_filter_chip(label: str, lower: object, upper: object, suffix: str = "") -> str:
    return f"{label} {_compact_filter_number(lower)}-" f"{_compact_filter_number(upper)}{suffix}"


def _cockpit_filter_detail_chips(
    values: Mapping[str, object],
    *,
    product_type: str,
) -> list[str]:
    chips: list[str] = []
    official_sector = str(values.get("market_data_cockpit_official_sector", "all"))
    theme = str(values.get("market_data_cockpit_theme", "all"))
    market_cap_tier = str(values.get("market_data_cockpit_market_cap", "all"))
    dividend_category = str(values.get("market_data_cockpit_dividend", "all"))
    currency = str(values.get("market_data_cockpit_currency", "all"))
    risk_band = str(values.get("market_data_cockpit_risk_band", "all"))
    if official_sector != "all":
        label = _short_filter_label(
            RANKING_OFFICIAL_SECTOR_LABELS.get(official_sector, official_sector)
        )
        chips.append(f"業種: {label}")
    if theme != "all":
        label = _short_filter_label(RANKING_INVESTMENT_THEME_LABELS.get(theme, theme))
        chips.append(f"テーマ: {label}")
    if market_cap_tier != "all":
        label = _short_filter_label(RANKING_MARKET_CAP_LABELS.get(market_cap_tier, market_cap_tier))
        chips.append(f"規模: {label}")
    if risk_band != "all":
        label = _short_filter_label(RANKING_BETA_RISK_LABELS.get(risk_band, risk_band))
        chips.append(f"β: {label}")
    if dividend_category != "all":
        label = _dividend_category_option_label(dividend_category, product_type)
        chips.append(f"配当: {_short_filter_label(label)}")
    if currency != "all":
        chips.append(f"通貨: {RANKING_CURRENCY_LABELS.get(currency, currency)}")
    if _truthy_filter_value(values.get("market_data_cockpit_dividend_enabled", False)):
        chips.append(
            _range_filter_chip(
                "配当利回り",
                values.get("market_data_cockpit_min_dividend", "0.0"),
                values.get("market_data_cockpit_dividend_max", "10.0"),
                "%",
            )
        )
    if _truthy_filter_value(values.get("market_data_cockpit_per_enabled", False)):
        chips.append(
            _range_filter_chip(
                "PER",
                values.get("market_data_cockpit_per_min", "2.0"),
                values.get("market_data_cockpit_per_max", "20.0"),
            )
        )
    if _truthy_filter_value(values.get("market_data_cockpit_pbr_enabled", False)):
        chips.append(
            _range_filter_chip(
                "PBR",
                values.get("market_data_cockpit_pbr_min", "0.5"),
                values.get("market_data_cockpit_pbr_max", "2.0"),
            )
        )
    if _truthy_filter_value(values.get("market_data_cockpit_roe_enabled", False)):
        chips.append(
            _range_filter_chip(
                "ROE",
                values.get("market_data_cockpit_roe_min", "8.0"),
                values.get("market_data_cockpit_roe_max", "30.0"),
                "%",
            )
        )
    return chips


def _cockpit_filter_detail_chips_v2(
    values: Mapping[str, object],
    *,
    product_type: str,
) -> list[str]:
    chips: list[str] = []
    region = str(values.get("market_data_cockpit_region", "all"))
    detail_filters = cockpit_detail_filters_for_category(region, product_type)
    official_sector = str(values.get("market_data_cockpit_official_sector", "all"))
    theme = str(values.get("market_data_cockpit_theme", "all"))
    market_cap_tier = str(values.get("market_data_cockpit_market_cap", "all"))
    index_family = str(values.get("market_data_cockpit_index_family", "all"))
    max_expense_ratio_pct = str(
        values.get(
            "market_data_cockpit_max_expense",
            MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_max_expense"],
        )
    )
    complexity = str(
        values.get(
            "market_data_cockpit_complexity",
            MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_complexity"],
        )
    )
    dividend_category = str(values.get("market_data_cockpit_dividend", "all"))
    currency = str(values.get("market_data_cockpit_currency", "all"))
    risk_band = str(values.get("market_data_cockpit_risk_band", "all"))
    if "official_sector" in detail_filters and official_sector != "all":
        label = _short_filter_label(
            RANKING_OFFICIAL_SECTOR_LABELS.get(official_sector, official_sector)
        )
        chips.append(f"業種: {label}")
    if "investment_theme" in detail_filters and theme != "all":
        label = _short_filter_label(RANKING_INVESTMENT_THEME_LABELS.get(theme, theme))
        chips.append(f"テーマ: {label}")
    if "market_cap" in detail_filters and market_cap_tier != "all":
        label = _short_filter_label(RANKING_MARKET_CAP_LABELS.get(market_cap_tier, market_cap_tier))
        chips.append(f"規模: {label}")
    if "risk_band" in detail_filters and risk_band != "all":
        label = _short_filter_label(RANKING_BETA_RISK_LABELS.get(risk_band, risk_band))
        chips.append(f"β: {label}")
    if "benchmark_index" in detail_filters and index_family != "all":
        index_label = RANKING_INDEX_FAMILY_LABELS.get(index_family, index_family)
        chips.append(f"指数: {index_label}")
    if "expense_ratio" in detail_filters and max_expense_ratio_pct != str(
        MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_max_expense"]
    ):
        chips.append(f"信託報酬 {_compact_filter_number(max_expense_ratio_pct)}%以下")
    if "complexity" in detail_filters and complexity != str(
        MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_complexity"]
    ):
        chips.append(f"商品特性: {RANKING_COMPLEXITY_LABELS.get(complexity, complexity)}")
    if "dividend_yield" in detail_filters and dividend_category != "all":
        label = _dividend_category_option_label(dividend_category, product_type)
        chips.append(f"配当: {_short_filter_label(label)}")
    if currency != "all":
        chips.append(f"通貨: {RANKING_CURRENCY_LABELS.get(currency, currency)}")
    if "dividend_yield" in detail_filters and _truthy_filter_value(
        values.get("market_data_cockpit_dividend_enabled", False)
    ):
        chips.append(
            _range_filter_chip(
                "配当利回り",
                values.get("market_data_cockpit_min_dividend", "3.0"),
                values.get("market_data_cockpit_dividend_max", "10.0"),
                "%",
            )
        )
    if "per" in detail_filters and _truthy_filter_value(
        values.get("market_data_cockpit_per_enabled", False)
    ):
        chips.append(
            _range_filter_chip(
                "PER",
                values.get("market_data_cockpit_per_min", "2.0"),
                values.get("market_data_cockpit_per_max", "20.0"),
            )
        )
    if "pbr" in detail_filters and _truthy_filter_value(
        values.get("market_data_cockpit_pbr_enabled", False)
    ):
        chips.append(
            _range_filter_chip(
                "PBR",
                values.get("market_data_cockpit_pbr_min", "0.5"),
                values.get("market_data_cockpit_pbr_max", "2.0"),
            )
        )
    if "roe" in detail_filters and _truthy_filter_value(
        values.get("market_data_cockpit_roe_enabled", False)
    ):
        chips.append(
            _range_filter_chip(
                "ROE",
                values.get("market_data_cockpit_roe_min", "8.0"),
                values.get("market_data_cockpit_roe_max", "30.0"),
                "%",
            )
        )
    return chips


def _render_cockpit_symbol_filter_panel(
    symbol_options: list[dict[str, str]],
) -> list[dict[str, str]]:
    filtered_rows = cockpit_filtered_symbol_rows(symbol_options)
    filter_values = _cockpit_filter_state_snapshot()
    chips = cockpit_filter_summary_chips_from_values(
        filter_values,
        candidate_count=len(filtered_rows),
    )
    filter_active = cockpit_filter_has_active_conditions_from_values(filter_values)
    st.markdown(
        '<div class="smai-cockpit-filter-expander-anchor"></div>',
        unsafe_allow_html=True,
    )
    with st.expander(cockpit_filter_expander_label(chips), expanded=False):
        if filter_active and st.button(
            "条件をクリア",
            key="market_data_cockpit_filter_clear",
        ):
            _clear_cockpit_symbol_filter_state()
            st.rerun()
        filtered_rows = _render_cockpit_symbol_filter_detail_fields_v2(symbol_options)

    if not filtered_rows:
        st.warning("条件に合う銘柄候補がありません。条件を緩めるか、クリアしてください。")
    return filtered_rows


def _render_cockpit_symbol_filter_detail_fields(
    symbol_options: list[dict[str, str]],
) -> list[dict[str, str]]:
    st.markdown('<div class="smai-cockpit-filter-detail-anchor"></div>', unsafe_allow_html=True)
    col_region, col_product, col_nisa = st.columns(3)
    with col_region:
        region = _render_detail_selectbox(
            "地域",
            options=list(RANKING_MVP_REGION_LABELS),
            key="market_data_cockpit_region",
            format_func=lambda value: RANKING_MVP_REGION_LABELS[value],
            default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_region"]),
            help_text="候補に含める市場地域です。国内、米国、中国/香港、韓国、ASEAN、その他海外から選びます。",
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

    classification_base_rows = _classification_count_base_rows(
        symbol_options,
        region=region,
        product_type=product_type,
    )
    official_sector_counts = symbol_universe_filter_value_counts(
        classification_base_rows,
        "official_sector",
    )
    investment_theme_counts = symbol_universe_filter_value_counts(
        classification_base_rows,
        "investment_theme",
    )
    official_sector_options = _filter_options_with_available_counts(
        RANKING_OFFICIAL_SECTOR_LABELS,
        official_sector_counts,
    )
    investment_theme_options = _filter_options_with_available_counts(
        RANKING_INVESTMENT_THEME_LABELS,
        investment_theme_counts,
    )

    st.markdown("**属性条件**")
    attr_cols = st.columns(6)
    with attr_cols[0]:
        official_sector = _render_detail_selectbox(
            "業種・セクター",
            options=official_sector_options,
            key="market_data_cockpit_official_sector",
            format_func=lambda value: _counted_filter_label(
                RANKING_OFFICIAL_SECTOR_LABELS,
                official_sector_counts,
                value,
            ),
            default_value=str(
                MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_official_sector"]
            ),
            help_text=RANKING_FILTER_HELP_TEXTS["official_sector"],
        )
    with attr_cols[1]:
        theme = _render_detail_selectbox(
            "投資テーマ",
            options=investment_theme_options,
            key="market_data_cockpit_theme",
            format_func=lambda value: _counted_filter_label(
                RANKING_INVESTMENT_THEME_LABELS,
                investment_theme_counts,
                value,
            ),
            default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_theme"]),
            help_text=RANKING_FILTER_HELP_TEXTS["investment_theme"],
        )
    with attr_cols[2]:
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
    with attr_cols[3]:
        risk_band = _render_detail_selectbox(
            "値動きリスク",
            options=list(RANKING_BETA_RISK_LABELS),
            key="market_data_cockpit_risk_band",
            format_func=lambda value: RANKING_BETA_RISK_LABELS[value],
            default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_risk_band"]),
            help_text=RANKING_FILTER_HELP_TEXTS["risk_band"],
        )
    with attr_cols[4]:
        dividend_category = _render_detail_selectbox(
            _dividend_category_filter_label(product_type),
            options=list(RANKING_DIVIDEND_LABELS),
            key="market_data_cockpit_dividend",
            format_func=lambda value: _dividend_category_option_label(value, product_type),
            default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_dividend"]),
            help_text=_dividend_filter_help_text(
                RANKING_FILTER_HELP_TEXTS["dividend_category"],
                product_type,
            ),
            disabled=_cockpit_filter_bool("market_data_cockpit_dividend_enabled", False),
        )
    with attr_cols[5]:
        currency = _render_detail_selectbox(
            "通貨",
            options=list(RANKING_CURRENCY_LABELS),
            key="market_data_cockpit_currency",
            format_func=lambda value: RANKING_CURRENCY_LABELS[value],
            default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_currency"]),
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
        official_sector=official_sector,
        theme=theme,
        index_family="all",
        max_expense_ratio_pct="100",
        complexity="all",
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
    if not filtered_rows:
        st.warning("条件に合う銘柄候補がありません。条件を緩めるか、クリアしてください。")
    return filtered_rows


def _render_cockpit_symbol_filter_detail_fields_v2(
    symbol_options: list[dict[str, str]],
) -> list[dict[str, str]]:
    st.markdown('<div class="smai-cockpit-filter-detail-anchor"></div>', unsafe_allow_html=True)
    col_region, col_product, col_nisa = st.columns(3)
    with col_region:
        region = _render_detail_selectbox(
            "地域",
            options=list(RANKING_MVP_REGION_LABELS),
            key="market_data_cockpit_region",
            format_func=lambda value: RANKING_MVP_REGION_LABELS[value],
            default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_region"]),
            help_text="候補に含める地域を選びます。",
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
            help_text="株式やETFなど、比較したい商品を選びます。",
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

    detail_filters = cockpit_detail_filters_for_category(region, product_type)
    classification_base_rows = _classification_count_base_rows(
        symbol_options,
        region=region,
        product_type=product_type,
    )
    official_sector_counts = symbol_universe_filter_value_counts(
        classification_base_rows,
        "official_sector",
    )
    investment_theme_counts = symbol_universe_filter_value_counts(
        classification_base_rows,
        "investment_theme",
    )
    benchmark_index_counts = symbol_universe_filter_value_counts(
        classification_base_rows,
        "benchmark_index",
    )
    complexity_counts = symbol_universe_filter_value_counts(
        classification_base_rows,
        "complexity",
    )
    dividend_category_counts = symbol_universe_filter_value_counts(
        classification_base_rows,
        "dividend_category",
    )
    currency_counts = symbol_universe_filter_value_counts(
        classification_base_rows,
        "currency",
    )

    official_sector = "all"
    theme = "all"
    market_cap_tier = "all"
    risk_band = "all"
    index_family = "all"
    max_expense_ratio_pct = _coerce_number_input_state("market_data_cockpit_max_expense", "2.00")
    complexity = "all"
    dividend_category = "all"
    currency = "all"

    st.markdown("**属性条件**")
    attr_cols = st.columns(4)
    attr_column_index = 0

    def next_attr_column():
        nonlocal attr_column_index
        column = attr_cols[attr_column_index % len(attr_cols)]
        attr_column_index += 1
        return column

    if "official_sector" in detail_filters:
        with next_attr_column():
            official_sector = _render_detail_selectbox(
                "業種・セクター",
                options=_filter_options_with_available_counts(
                    RANKING_OFFICIAL_SECTOR_LABELS,
                    official_sector_counts,
                ),
                key="market_data_cockpit_official_sector",
                format_func=lambda value: _counted_filter_label(
                    RANKING_OFFICIAL_SECTOR_LABELS,
                    official_sector_counts,
                    value,
                ),
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_official_sector"]
                ),
                help_text=RANKING_FILTER_HELP_TEXTS["official_sector"],
            )
    if "investment_theme" in detail_filters:
        with next_attr_column():
            theme = _render_detail_selectbox(
                "投資テーマ",
                options=_filter_options_with_available_counts(
                    RANKING_INVESTMENT_THEME_LABELS,
                    investment_theme_counts,
                ),
                key="market_data_cockpit_theme",
                format_func=lambda value: _counted_filter_label(
                    RANKING_INVESTMENT_THEME_LABELS,
                    investment_theme_counts,
                    value,
                ),
                default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_theme"]),
                help_text=RANKING_FILTER_HELP_TEXTS["investment_theme"],
            )
    if "market_cap" in detail_filters:
        with next_attr_column():
            market_cap_tier = _render_detail_selectbox(
                "時価総額帯",
                options=list(RANKING_MARKET_CAP_LABELS),
                key="market_data_cockpit_market_cap",
                format_func=lambda value: RANKING_MARKET_CAP_LABELS[value],
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_market_cap"]
                ),
                help_text=RANKING_FILTER_HELP_TEXTS["market_cap"],
            )
    if "risk_band" in detail_filters:
        with next_attr_column():
            risk_band = _render_detail_selectbox(
                "値動きリスク",
                options=list(RANKING_BETA_RISK_LABELS),
                key="market_data_cockpit_risk_band",
                format_func=lambda value: RANKING_BETA_RISK_LABELS[value],
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_risk_band"]
                ),
                help_text=RANKING_FILTER_HELP_TEXTS["risk_band"],
            )
    if "benchmark_index" in detail_filters:
        with next_attr_column():
            index_family = _render_detail_selectbox(
                "連動指数",
                options=_filter_options_with_available_counts(
                    RANKING_INDEX_FAMILY_LABELS,
                    benchmark_index_counts,
                ),
                key="market_data_cockpit_index_family",
                format_func=lambda value: _counted_filter_label(
                    RANKING_INDEX_FAMILY_LABELS,
                    benchmark_index_counts,
                    value,
                ),
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_index_family"]
                ),
                help_text=RANKING_FILTER_HELP_TEXTS["benchmark_index"],
            )
    if "expense_ratio" in detail_filters:
        with next_attr_column():
            max_expense_ratio_pct = st.number_input(
                "信託報酬/経費率(%)以下",
                min_value=0.0,
                max_value=2.0,
                value=max_expense_ratio_pct,
                step=0.01,
                format="%.2f",
                key="market_data_cockpit_max_expense",
                help=RANKING_FILTER_HELP_TEXTS["expense_ratio"],
            )
    if "complexity" in detail_filters:
        with next_attr_column():
            complexity = _render_detail_selectbox(
                "複雑さ",
                options=_filter_options_with_available_counts(
                    RANKING_COMPLEXITY_LABELS,
                    complexity_counts,
                ),
                key="market_data_cockpit_complexity",
                format_func=lambda value: _counted_filter_label(
                    RANKING_COMPLEXITY_LABELS,
                    complexity_counts,
                    value,
                ),
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_complexity"]
                ),
                help_text=RANKING_FILTER_HELP_TEXTS["complexity"],
            )
    if "dividend_yield" in detail_filters:
        with next_attr_column():
            dividend_labels = {
                key: _dividend_category_option_label(key, product_type)
                for key in RANKING_DIVIDEND_LABELS
            }
            dividend_category = _render_detail_selectbox(
                _dividend_category_filter_label(product_type),
                options=_filter_options_with_available_counts(
                    dividend_labels,
                    dividend_category_counts,
                ),
                key="market_data_cockpit_dividend",
                format_func=lambda value: _counted_filter_label(
                    dividend_labels,
                    dividend_category_counts,
                    value,
                ),
                default_value=str(
                    MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_dividend"]
                ),
                help_text=_dividend_filter_help_text(
                    RANKING_FILTER_HELP_TEXTS["dividend_category"],
                    product_type,
                ),
                disabled=_cockpit_filter_bool("market_data_cockpit_dividend_enabled", False),
            )
    with next_attr_column():
        currency = _render_detail_selectbox(
            "通貨",
            options=_filter_options_with_available_counts(
                RANKING_CURRENCY_LABELS,
                currency_counts,
            ),
            key="market_data_cockpit_currency",
            format_func=lambda value: _counted_filter_label(
                RANKING_CURRENCY_LABELS,
                currency_counts,
                value,
            ),
            default_value=str(MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_currency"]),
            help_text=RANKING_FILTER_HELP_TEXTS["currency"],
        )

    dividend_enabled = False
    min_dividend: float = 3.0
    max_dividend: float = 10.0
    per_enabled = False
    per_min: float = 2.0
    per_max: float = 20.0
    pbr_enabled = False
    pbr_min: float = 0.5
    pbr_max: float = 2.0
    roe_enabled = False
    roe_min: float = 8.0
    roe_max: float = 30.0

    metric_filters: list[tuple[str, dict[str, object]]] = []
    if "dividend_yield" in detail_filters:
        metric_filters.append(
            (
                _dividend_yield_filter_label(product_type),
                {
                    "enabled_key": "market_data_cockpit_dividend_enabled",
                    "min_key": "market_data_cockpit_min_dividend",
                    "max_key": "market_data_cockpit_dividend_max",
                    "min_default": "3.0",
                    "max_default": "10.0",
                    "max_value": 15.0,
                    "help_text": _dividend_filter_help_text(
                        RANKING_FILTER_HELP_TEXTS["dividend_yield"],
                        product_type,
                    ),
                    "disabled": dividend_category != "all",
                },
            )
        )
    if "per" in detail_filters:
        metric_filters.append(
            (
                "PER",
                {
                    "enabled_key": "market_data_cockpit_per_enabled",
                    "min_key": "market_data_cockpit_per_min",
                    "max_key": "market_data_cockpit_per_max",
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
                    "enabled_key": "market_data_cockpit_pbr_enabled",
                    "min_key": "market_data_cockpit_pbr_min",
                    "max_key": "market_data_cockpit_pbr_max",
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
                    "enabled_key": "market_data_cockpit_roe_enabled",
                    "min_key": "market_data_cockpit_roe_min",
                    "max_key": "market_data_cockpit_roe_max",
                    "min_default": "8.0",
                    "max_default": "30.0",
                    "max_value": 60.0,
                    "help_text": RANKING_FILTER_HELP_TEXTS["roe"],
                },
            )
        )

    if metric_filters:
        st.markdown("**数値条件**")
        for start_index in range(0, len(metric_filters), 2):
            metric_cols = st.columns(2)
            for column, (label, config) in zip(
                metric_cols, metric_filters[start_index : start_index + 2]
            ):
                with column:
                    enabled, lower, upper = _render_metric_range_filter(label, **cast(Any, config))
                if config["enabled_key"] == "market_data_cockpit_dividend_enabled":
                    dividend_enabled, min_dividend, max_dividend = enabled, lower, upper
                elif config["enabled_key"] == "market_data_cockpit_per_enabled":
                    per_enabled, per_min, per_max = enabled, lower, upper
                elif config["enabled_key"] == "market_data_cockpit_pbr_enabled":
                    pbr_enabled, pbr_min, pbr_max = enabled, lower, upper
                elif config["enabled_key"] == "market_data_cockpit_roe_enabled":
                    roe_enabled, roe_min, roe_max = enabled, lower, upper

    filtered_rows = cockpit_filtered_symbol_rows_from_values(
        symbol_options,
        region=region,
        product_type=product_type,
        currency=currency,
        dividend_category=dividend_category,
        market_cap_tier=market_cap_tier,
        nisa_eligibility=nisa_eligibility,
        risk_band=risk_band,
        official_sector=official_sector,
        theme=theme,
        index_family=index_family,
        max_expense_ratio_pct=max_expense_ratio_pct,
        complexity=complexity,
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
        active_detail_filters=detail_filters,
    )
    if not filtered_rows:
        st.warning("条件に合う銘柄候補がありません。条件をゆるめるか、クリアしてください。")
    return filtered_rows


def cockpit_filtered_symbol_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    region = _cockpit_filter_value("market_data_cockpit_region", "all")
    product_type = _cockpit_filter_value("market_data_cockpit_product_type", "all")
    return cockpit_filtered_symbol_rows_from_values(
        rows,
        region=region,
        product_type=product_type,
        currency=_cockpit_filter_value("market_data_cockpit_currency", "all"),
        dividend_category=_cockpit_filter_value("market_data_cockpit_dividend", "all"),
        market_cap_tier=_cockpit_filter_value("market_data_cockpit_market_cap", "all"),
        nisa_eligibility=_cockpit_filter_value("market_data_cockpit_nisa", "all"),
        risk_band=_cockpit_filter_value("market_data_cockpit_risk_band", "all"),
        official_sector=_cockpit_filter_value("market_data_cockpit_official_sector", "all"),
        theme=_cockpit_filter_value("market_data_cockpit_theme", "all"),
        index_family=_cockpit_filter_value("market_data_cockpit_index_family", "all"),
        max_expense_ratio_pct=_cockpit_filter_value("market_data_cockpit_max_expense", "2.00"),
        complexity=_cockpit_filter_value("market_data_cockpit_complexity", "all"),
        dividend_yield_enabled=_cockpit_filter_bool(
            "market_data_cockpit_dividend_enabled",
            False,
        ),
        min_dividend_yield_pct=_cockpit_filter_value(
            "market_data_cockpit_min_dividend",
            "3.0",
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
        active_detail_filters=cockpit_detail_filters_for_category(region, product_type),
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
    st.session_state.pop("market_data_cockpit_favorites_only", None)
    st.session_state.pop("market_data_symbol_candidate", None)


def _current_or_default_symbol_labels(symbol_options: list[dict[str, str]]) -> list[str]:
    labels = symbol_candidate_labels(symbol_options)
    return labels[:1] if labels else [NO_SYMBOL_CANDIDATE_LABEL]


def merged_symbol_candidate_rows(
    *candidate_groups: list[dict[str, str]],
    query: str = "",
) -> list[dict[str, str]]:
    """Merge all Cockpit candidate sources, deduplicate, and apply search ranking."""

    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in (row for group in candidate_groups for row in group):
        symbol = row.get("symbol", "").strip()
        name = row.get("name", "").strip() or symbol
        normalized_symbol = symbol.upper()
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        merged.append({**row, "symbol": symbol, "name": name})
    if not query.strip():
        return merged

    def sort_key(row: Mapping[str, object]) -> tuple[int, str]:
        rank = cockpit_symbol_search_rank(row, query)
        return (rank if rank is not None else 99, str(row.get("symbol", "")).upper())

    return sorted(
        merged,
        key=sort_key,
    )


def symbol_universe_rows_for_symbols(
    rows: list[dict[str, str]],
    symbols: Iterable[str],
) -> list[dict[str, str]]:
    """Resolve symbols against the full universe while preserving requested order."""

    rows_by_symbol = {
        row.get("symbol", "").strip().upper(): row for row in rows if row.get("symbol", "").strip()
    }
    resolved: list[dict[str, str]] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        row = rows_by_symbol.get(normalized_symbol)
        if row is not None:
            resolved.append(row)
    return resolved


def cockpit_preserved_candidate_symbols(
    query: str,
    ranking_handoff_symbol: str,
    current_selected_symbol: str,
) -> list[str]:
    """Preserve navigation/current choices only while no keyword search is active."""

    if query.strip():
        return []
    return [ranking_handoff_symbol, current_selected_symbol]


def favorite_prioritized_symbol_candidate_labels(
    rows: list[dict[str, str]],
    favorite_symbols: set[str],
    *,
    favorites_only: bool = False,
    query: str = "",
    required_symbols: Collection[str] = (),
) -> list[str]:
    normalized_favorites = {
        normalize_favorite_symbol(symbol) for symbol in favorite_symbols if symbol.strip()
    }
    normalized_required = {
        normalize_favorite_symbol(symbol) for symbol in required_symbols if symbol.strip()
    }
    if favorites_only:
        rows = [
            row
            for row in rows
            if normalize_favorite_symbol(row.get("symbol", ""))
            in normalized_favorites | normalized_required
        ]
    if query.strip():

        def sort_key(row: Mapping[str, object]) -> tuple[int, bool, str]:
            rank = cockpit_symbol_search_rank(row, query)
            symbol = str(row.get("symbol", ""))
            return (
                rank if rank is not None else 99,
                normalize_favorite_symbol(symbol) not in normalized_favorites,
                symbol.upper(),
            )

        rows = sorted(
            rows,
            key=sort_key,
        )
        return symbol_candidate_labels(rows)
    labels = symbol_candidate_labels(rows)
    return sorted(
        labels,
        key=lambda label: (
            normalize_favorite_symbol(_symbol_from_candidate(label) or "")
            not in normalized_favorites,
        ),
    )


def favorite_symbol_candidate_display_label(
    label: str,
    favorite_symbols: set[str],
) -> str:
    symbol = normalize_favorite_symbol(_symbol_from_candidate(label) or "")
    normalized_favorites = {normalize_favorite_symbol(favorite) for favorite in favorite_symbols}
    return f"★ {label}" if symbol and symbol in normalized_favorites else label


def _render_market_data_preview() -> None:
    _render_market_data_cockpit()


def _render_market_data_cockpit() -> None:
    render_page_title(
        "銘柄コックピット",
        "価格・予測・根拠を確認します。",
        "cockpit",
    )
    navigation_source = st.session_state.get("market_data_navigation_source")
    if isinstance(navigation_source, dict) and navigation_source.get("source_page") == "ranking":
        st.session_state.pop("market_data_navigation_source", None)
        period_label = str(navigation_source.get("period_label") or "ランキングの比較期間")
        st.info(
            "ランキングの比較候補から移動しました。ランキング時点の比較値を引き継いでいます。"
            f"{period_label}の価格・予測を最新データで確認するには、下の「データを取得」を実行してください。"
        )
    symbol_options = symbol_universe_rows()
    filtered_symbol_options = _render_cockpit_symbol_filter_panel(symbol_options)
    st.markdown(
        '<section class="smai-cockpit-prefetch-header">'
        '<div class="smai-cockpit-prefetch-heading">銘柄を探す</div>'
        '<p class="smai-cockpit-prefetch-caption">'
        "検索して、分析する銘柄を選びます。"
        "</p>"
        "</section>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<span class="smai-cockpit-controls-anchor"></span>',
        unsafe_allow_html=True,
    )
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
            "キーワード",
            value="",
            key="market_data_symbol_search",
            placeholder="銘柄コード、会社名、テーマ",
            help="会社名、銘柄コード、テーマ、業種などで候補を部分一致検索します。",
        )
    local_candidate_rows = cockpit_keyword_filtered_symbol_rows(
        filtered_symbol_options,
        symbol_query,
    )
    normalized_query = symbol_query.strip().upper()
    exact_symbol_rows = (
        symbol_universe_rows_for_symbols(symbol_options, [normalized_query])
        if normalized_query
        else []
    )
    ranking_handoff_symbol = str(st.session_state.get("market_data_ranking_handoff_symbol", ""))
    current_selected_symbol = (
        _symbol_from_candidate(str(st.session_state.get("market_data_symbol_candidate", ""))) or ""
    )
    preserved_symbols = cockpit_preserved_candidate_symbols(
        symbol_query,
        ranking_handoff_symbol,
        current_selected_symbol,
    )
    preserved_symbol_rows = symbol_universe_rows_for_symbols(
        symbol_options,
        preserved_symbols,
    )
    live_symbol_options = yfinance_search_symbol_rows(symbol_query) if symbol_query.strip() else []
    candidate_rows = merged_symbol_candidate_rows(
        local_candidate_rows,
        exact_symbol_rows,
        preserved_symbol_rows,
        live_symbol_options,
        query=symbol_query,
    )
    favorite_symbols = {favorite.symbol for favorite in load_favorites()}
    favorite_option_labels = favorite_prioritized_symbol_candidate_labels(
        candidate_rows,
        favorite_symbols,
        favorites_only=True,
    )
    favorites_only = bool(st.session_state.get("market_data_cockpit_favorites_only", False))
    with col_symbol:
        symbol_option_labels = favorite_prioritized_symbol_candidate_labels(
            candidate_rows,
            favorite_symbols,
            favorites_only=favorites_only,
            query=symbol_query,
            required_symbols=[
                *preserved_symbols,
                normalized_query,
            ],
        )
        if not symbol_option_labels:
            symbol_option_labels = [NO_SYMBOL_CANDIDATE_LABEL]
        _ensure_selectbox_state_value(
            "market_data_symbol_candidate",
            symbol_option_labels,
            default_value=symbol_option_labels[0],
        )
        symbol_candidate = cast(
            str,
            st.selectbox(
                "銘柄",
                symbol_option_labels,
                key="market_data_symbol_candidate",
                placeholder="銘柄コードまたは会社名",
                format_func=lambda label: favorite_symbol_candidate_display_label(
                    label,
                    favorite_symbols,
                ),
            ),
        )
        st.markdown(
            '<span class="smai-cockpit-favorites-toggle-anchor"></span>',
            unsafe_allow_html=True,
        )
        st.toggle(
            f"お気に入りのみ（{len(favorite_option_labels)}件）",
            key="market_data_cockpit_favorites_only",
        )
    if favorites_only and not favorite_option_labels:
        st.info(
            "現在の条件に合うお気に入りがありません。"
            "銘柄を選んで「お気に入りに追加」するか、キーワード・絞り込み条件を解除してください。"
        )
    symbol = _symbol_from_candidate(symbol_candidate) or ""
    with col_detail:
        st.markdown(
            '<span class="smai-cockpit-detail-action-anchor"></span>',
            unsafe_allow_html=True,
        )
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
        company_name_display = html.escape(company_name or "未登録")
        st.markdown(
            '<div class="smai-cockpit-symbol-name-field">'
            '<span class="smai-cockpit-symbol-name-label">銘柄名</span>'
            f'<span class="smai-cockpit-symbol-name-value">{company_name_display}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    symbol_detail_row = _symbol_universe_row_for_symbol(symbol) if symbol else None
    if symbol_detail_row is not None:
        st.caption(symbol_universe_cache_status_text(symbol_detail_row))
    col_period, col_start, col_end, _ = st.columns([1.65, 1.0, 1.0, 3.35])
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
        loading_headlines, loading_headline_note = workflow_loading_headlines_from_cache()
        progress_bar: Any | None = None
        progress_status: Any | None = None

        def update_cockpit_progress(message: str, ratio: float) -> None:
            loading_slot.markdown(
                workflow_loading_html(
                    title="市場データを取得中",
                    message="価格、予測、スコアの材料をまとめています。",
                    current_step=message,
                    progress=ratio,
                    mode="blocking",
                    headlines=loading_headlines,
                    headline_note=loading_headline_note,
                ),
                unsafe_allow_html=True,
            )
            if progress_status is not None:
                progress_status.caption(message)
            if progress_bar is not None:
                progress_bar.progress(max(0.0, min(1.0, ratio)))

        try:
            start_date = _single_date_from_input(start)
            end_date = _single_date_from_input(end)
            progress_bar = st.progress(0.0)
            progress_status = st.empty()
            update_cockpit_progress("入力条件と自動予測期間を確認しています。", 0.12)
            update_cockpit_progress("価格データと予測材料を取得しています。", 0.32)
            preview = asyncio.run(
                build_market_data_preview(
                    symbol=symbol.strip(),
                    start=start_date,
                    end=end_date,
                    provider_override=provider,
                    forecast_horizon_days=None,
                )
            )
            st.session_state[MARKET_DATA_FORECAST_DAYS_STATE_KEY] = preview.forecast_horizon_days
            update_cockpit_progress("予測モデル、スコア、チャート材料を整理しています。", 0.86)
        except ValueError as exc:
            loading_slot.empty()
            st.error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            loading_slot.empty()
            st.error(str(exc))
            return

        st.session_state[MARKET_DATA_PREVIEW_STATE_KEY] = preview
        st.session_state[MARKET_DATA_STATUS_STATE_KEY] = preview.status
        st.session_state.pop(MARKET_CHART_DISPLAY_CURRENCY_STATE_KEY, None)
        if preview.status == "OK":
            update_cockpit_progress("表示内容を更新しています。", 0.96)
            st.session_state[MARKET_DATA_TOAST_STATE_KEY] = "データを取得しました。"
            _request_cockpit_symbol_db_preflight_background(symbol)
            update_cockpit_progress("データ取得が完了しました。", 1.0)
        loading_slot.empty()

    stored_preview = _market_data_preview_from_state()
    if stored_preview is None:
        _register_cockpit_setup_assistant_context(symbol)
        render_mascot_panel(
            "empty",
            title="まずデータ取得",
            message="銘柄と期間を選ぶと、価格・予測材料を確認します。",
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
    ranking_history_user_id = str(st.session_state.get("smai_current_user_id") or "default")
    synchronize_ranking_history_user(ranking_history_user_id)
    apply_ranking_history_open_query(ranking_history_user_id)
    ranking_view_mode = str(st.session_state.get(RANKING_HISTORY_VIEW_KEY, "live"))
    if ranking_view_mode not in {"live", "history_list", "history_detail"}:
        ranking_view_mode = "live"
        st.session_state[RANKING_HISTORY_VIEW_KEY] = "live"
    if ranking_view_mode == "history_list":
        render_ranking_history_list(ranking_history_user_id)
        return
    if ranking_view_mode == "history_detail":
        render_ranking_history_detail(
            ranking_history_user_id,
            render_result_table=lambda rows, source, preset: _render_ranking_result_table(
                rows,
                ranking_source=source,
                weight_preset=preset,
                ranking_purpose=RANKING_PURPOSE_MULTI_FACTOR,
                mode="history",
            ),
            open_current_symbol=lambda symbol: _select_ranking_symbol_for_cockpit(
                symbol,
                default_market_data_provider(),
            ),
        )
        return
    render_page_title(
        "銘柄ランキング",
        "条件で絞り込み、比較する候補を並べます。",
        "ranking",
    )
    _, history_button_col = st.columns([4, 1.25])
    with history_button_col:
        if st.button(
            "📚 ランキング履歴",
            key="open_ranking_history",
            use_container_width=True,
        ):
            st.session_state[RANKING_HISTORY_VIEW_KEY] = "history_list"
            st.rerun()
    restore_notice = st.session_state.pop(RANKING_HISTORY_NOTICE_KEY, None)
    if restore_notice:
        st.info(str(restore_notice))
    _register_ranking_setup_assistant_context()
    symbol_options = symbol_universe_rows()
    purpose = "all"

    st.markdown(
        '<section class="smai-ranking-creation-conditions">'
        '<div class="smai-card-label">ランキング作成条件</div>'
        "<strong>ランキング基準・対象・取得元を選びます。</strong>"
        "</section>",
        unsafe_allow_html=True,
    )
    primary_conditions = st.container()
    detail_conditions = st.container()

    with detail_conditions:
        # 地域は探索条件の「国・市場」に統合する。ランキング基礎フィルタは全地域を対象にする。
        region = "all"
        st.session_state["market_data_ranking_region"] = region
        col_product, col_period, col_provider = st.columns(3)
        with col_product:
            product_options = list(RANKING_MVP_PRODUCT_TYPE_LABELS)
            _ensure_selectbox_state_value(
                "market_data_ranking_product_type",
                product_options,
                default_value=RANKING_PRODUCT_STOCK,
            )
            product_type = cast(
                str,
                st.selectbox(
                    "商品",
                    product_options,
                    key="market_data_ranking_product_type",
                    format_func=ranking_product_type_label,
                ),
            )

    _sync_ranking_policy_state(product_type)
    with primary_conditions:
        col_policy, col_limit = st.columns(2)
        with col_policy:
            policy_options = ranking_policy_options(product_type)
            _ensure_selectbox_state_value(
                "market_data_ranking_policy",
                policy_options,
                default_value=RANKING_PURPOSE_MULTI_FACTOR,
            )
            st.markdown(
                '<div class="smai-ranking-policy-select-anchor"></div>',
                unsafe_allow_html=True,
            )
            ranking_policy = cast(
                str,
                st.selectbox(
                    "ランキング基準",
                    policy_options,
                    key="market_data_ranking_policy",
                    format_func=ranking_policy_label,
                    help=(
                        "どの見方で候補を並べるかを選びます。"
                        "上位候補・グラフ・SMAIメモは、このランキング基準に基づいて表示されます。"
                    ),
                ),
            )
        with col_limit:
            fetch_limit_options = list(RANKING_FETCH_LIMIT_LABELS)
            _ensure_selectbox_state_value(
                "market_data_ranking_fetch_limit",
                fetch_limit_options,
                default_value=RANKING_FETCH_LIMIT_BALANCED,
            )
            st.markdown(
                '<div class="smai-ranking-policy-select-anchor"></div>',
                unsafe_allow_html=True,
            )
            fetch_limit = cast(
                str,
                st.selectbox(
                    "作成対象件数",
                    fetch_limit_options,
                    key="market_data_ranking_fetch_limit",
                    format_func=ranking_fetch_limit_label,
                    help=(
                        "候補が多い場合、外部取得前に総合マルチファクター基準で上位に絞ります。"
                        "全件取得も選べますが、Yahooライブデータでは時間がかかります。"
                    ),
                ),
            )
        st.text_input(
            "キーワード",
            value=_ranking_filter_value("market_data_ranking_symbol_query", ""),
            key="market_data_ranking_symbol_query",
            placeholder="銘柄コード、会社名、テーマ",
            help=RANKING_FILTER_HELP_TEXTS["keyword"],
        )
        st.caption("キーワードを入力してEnterを押すと、候補数と現在の条件へ反映されます。")

    with detail_conditions:
        with col_period:
            period_options = list(RANKING_PERIOD_PRESETS)
            _ensure_selectbox_state_value(
                "market_data_ranking_period",
                period_options,
                default_value=RANKING_DEFAULT_PERIOD_PRESET,
            )
            period_preset = cast(
                str,
                st.selectbox(
                    "取得期間",
                    period_options,
                    key="market_data_ranking_period",
                    format_func=ranking_period_label,
                    help=RANKING_FILTER_HELP_TEXTS["period"],
                ),
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
    policy_preset = ranking_weight_preset_for_purpose(ranking_policy)
    filtered_symbol_rows = _render_ranking_filter_panel(
        symbol_options,
        region=region,
        product_type=product_type,
        ranking_policy=ranking_policy,
        period_preset=period_preset,
        purpose=purpose,
    )
    if ranking_filter_dialog_is_open():
        st.caption(
            "探索条件モーダルを表示中です。ランキング候補・結果の再描画はスキップしています。"
        )
        return
    # Widget state is removed by Streamlit after navigating to Cockpit. Persist
    # the active values so a ranking-to-detail round trip keeps the comparison
    # conditions visible and reusable.
    persist_ranking_filter_state()
    filter_values = _ranking_filter_state_snapshot()
    market = "all"
    asset_type = "all"
    currency = str(filter_values["market_data_ranking_currency"])
    dividend_category = str(filter_values["market_data_ranking_dividend"])
    min_dividend_yield_pct = str(filter_values["market_data_ranking_min_dividend"])
    market_cap_tier = str(filter_values["market_data_ranking_market_cap"])
    index_family = str(filter_values["market_data_ranking_index_family"])
    max_expense_ratio_pct = str(filter_values["market_data_ranking_max_expense"])
    complexity = str(filter_values["market_data_ranking_complexity"])
    nisa_eligibility = str(filter_values["market_data_ranking_nisa"])
    risk_band = str(filter_values["market_data_ranking_risk_band"])
    official_sector = str(filter_values["market_data_ranking_official_sector"])
    theme = str(filter_values["market_data_ranking_theme"])
    symbol_query = str(filter_values["market_data_ranking_symbol_query"])
    per_enabled = bool(filter_values["market_data_ranking_per_enabled"])
    per_min = str(filter_values["market_data_ranking_per_min"])
    per_max = str(filter_values["market_data_ranking_per_max"])
    pbr_enabled = bool(filter_values["market_data_ranking_pbr_enabled"])
    pbr_min = str(filter_values["market_data_ranking_pbr_min"])
    pbr_max = str(filter_values["market_data_ranking_pbr_max"])
    dividend_yield_enabled = bool(filter_values["market_data_ranking_dividend_enabled"])
    dividend_yield_max_pct = str(filter_values["market_data_ranking_dividend_max"])
    roe_enabled = bool(filter_values["market_data_ranking_roe_enabled"])
    roe_min_pct = str(filter_values["market_data_ranking_roe_min"])
    roe_max_pct = str(filter_values["market_data_ranking_roe_max"])
    consensus_enabled = bool(filter_values["market_data_ranking_consensus_enabled"])
    consensus_min = str(filter_values["market_data_ranking_consensus_min"])
    consensus_max = str(filter_values["market_data_ranking_consensus_max"])
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
        official_sector=official_sector,
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
    end_date = default_market_data_end_date()
    start_date, end_date = ranking_period_dates(period_preset, end_date)
    display_candidate_count = len(filtered_symbol_rows)
    manual_selection_key = f"{selection_key}_manual_selection"
    manual_selection_enabled = bool(st.session_state.get(manual_selection_key, False))
    selected_count_for_summary = display_candidate_count
    load_state = ranking_condition_load_state(selected_count_for_summary)

    st.markdown(
        _ranking_condition_summary_html(
            filter_values,
            region=region,
            product_type=product_type,
            ranking_policy=ranking_policy,
            period_preset=period_preset,
            candidate_count=display_candidate_count,
            load_state=load_state,
            extra_chips=ranking_exploration_filter_chip_labels(),
            draft=False,
        ),
        unsafe_allow_html=True,
    )
    with st.expander("ランキング基準の内訳", expanded=False):
        st.markdown(
            ranking_policy_builder_card_html(ranking_policy, policy_preset),
            unsafe_allow_html=True,
        )

    st.toggle(
        "比較する銘柄を手動で選ぶ",
        key=manual_selection_key,
        help="開いた時だけ候補ラベルと multiselect を生成します。通常は現在の候補から取得上限まで自動選定します。",
    )
    manual_selection_enabled = bool(st.session_state.get(manual_selection_key, False))
    if manual_selection_enabled:
        labels = symbol_candidate_labels(filtered_symbol_rows)
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
        comparison_summary = ranking_comparison_summary(
            start=start_date,
            end=end_date,
            candidate_count=len(filtered_symbol_rows),
            selected_count=len(selected_labels_for_summary),
        )
        expander_label = f"比較する銘柄を確認・変更（{comparison_summary['selected']}）"
        with st.expander(expander_label, expanded=True):
            st.caption(
                "手動選択時だけ候補リストを生成しています。候補が多い場合は条件で絞ると軽くなります。"
            )
            selected_labels = cast(
                list[str],
                st.multiselect(
                    "比較する銘柄",
                    labels,
                    key=selection_key,
                ),
            )
        effective_selected_labels = limited_ranking_selected_labels(
            selected_labels,
            filtered_symbol_rows,
            preset=RANKING_FETCH_LIMIT_PRESET,
            limit_key=fetch_limit,
        )
        selected_count_for_summary = len(selected_labels)
    else:
        st.caption("候補は自動選定します。必要なときだけ手動選択を開いてください。")
        effective_selected_labels = _default_effective_ranking_labels(
            filtered_symbol_rows,
            preset=RANKING_FETCH_LIMIT_PRESET,
            limit_key=fetch_limit,
        )
        selected_labels = effective_selected_labels
        selected_count_for_summary = display_candidate_count
    if not filtered_symbol_rows:
        st.warning("この条件に合う候補がありません。候補条件を広げてください。")

    comparison_summary = ranking_comparison_summary(
        start=start_date,
        end=end_date,
        candidate_count=len(filtered_symbol_rows),
        selected_count=selected_count_for_summary,
    )
    ranking_symbols = _ranking_symbols_from_selected_labels(effective_selected_labels)
    current_ranking_source = _ranking_source_key_for_selection(
        provider=provider,
        selected_labels=effective_selected_labels,
        start=start_date,
        end=end_date,
    )
    ranking_forecast_horizon_days = default_forecast_horizon_days(start_date, end_date)
    has_detail_conditions = ranking_condition_has_active_detail_from_values(filter_values)
    action_button_col, action_summary_col = st.columns([0.95, 3.05])
    with action_button_col:
        st.markdown(
            '<div class="smai-ranking-build-action-anchor"></div>',
            unsafe_allow_html=True,
        )
        build_ranking_clicked = st.button(
            "ランキング作成",
            key="build_market_data_ranking",
            type="primary",
            disabled=(not ranking_symbols or ranking_job_is_running(current_ranking_source)),
            use_container_width=True,
        )
    with action_summary_col:
        st.markdown(
            ranking_creation_target_summary_html(
                candidate_count=display_candidate_count,
                selected_count=selected_count_for_summary,
                effective_count=len(effective_selected_labels),
                fetch_limit_label=ranking_fetch_limit_label(fetch_limit),
                ranking_policy=ranking_policy,
                period_preset=period_preset,
                provider=provider,
                has_detail_conditions=has_detail_conditions,
            ),
            unsafe_allow_html=True,
        )
    if build_ranking_clicked:
        sync_ranking_selection_state(selection_key, selected_labels)
        if not ranking_symbols:
            st.error("対象の銘柄を1件以上選んでください。")
            return
        cache_key = current_ranking_source
        _touch_ranking_client_session(force=True)
        start_ranking_job(
            cache_key,
            lambda progress: _execute_market_data_ranking_job(
                cache_key=cache_key,
                ranking_symbols=list(ranking_symbols),
                start=start_date,
                end=end_date,
                provider=provider,
                progress_callback=progress,
            ),
        )
        st.rerun()

    _render_ranking_background_job(current_ranking_source)

    completed_job = get_ranking_job(current_ranking_source)
    history_pending_job_id = str(st.session_state.get(RANKING_JOB_HISTORY_PENDING_STATE_KEY) or "")
    if (
        completed_job is not None
        and completed_job.status == "completed"
        and completed_job.job_id == history_pending_job_id
    ):
        st.session_state.pop(RANKING_JOB_HISTORY_PENDING_STATE_KEY, None)
        rows = completed_job.rows
        if rows:
            try:
                history_ranked_rows = apply_ranking_weight_preset(
                    cast(list[dict[str, str]], rows),
                    policy_preset,
                    _symbol_universe_rows_by_symbol(),
                )
                history_display_rows = investment_score_display_rows(history_ranked_rows)
                history_request = build_ranking_history_save_request(
                    rows=history_display_rows,
                    filters=current_ranking_filter_state(),
                    provider=provider,
                    data_as_of=end_date,
                    start=start_date,
                    end=end_date,
                    ranking_type=ranking_policy,
                    weight_preset=policy_preset,
                    product_type=product_type,
                    target_label=ranking_product_type_label(product_type),
                    condition_summary=ranking_filter_summary(),
                    candidate_count=len(filtered_symbol_rows),
                    ranking_logic_version=RANKING_BUILD_CACHE_VERSION,
                )
                st.session_state["ranking_history_last_save_result"] = (
                    save_ranking_history_for_current_user(
                        ranking_history_user_id,
                        history_request,
                    ).model_dump()
                )
            except Exception:
                st.session_state["ranking_history_last_save_result"] = {
                    "status": "failed",
                    "message": "ランキング結果は表示できますが、履歴保存に失敗しました。",
                }

    history_save_result = st.session_state.pop("ranking_history_last_save_result", None)
    if isinstance(history_save_result, dict):
        history_status = str(history_save_result.get("status", ""))
        history_message = str(history_save_result.get("message", ""))
        if history_status == "saved":
            st.success(f"✅ {history_message}")
        elif history_status == "failed":
            st.warning(history_message)
        elif history_status == "skipped_default":
            st.info(
                "SMAIデフォルトではランキング履歴を保存しません。履歴を残す場合は、"
                "ローカルプロフィールを選択または作成してください。"
            )
        else:
            st.info(history_message)

    _render_ranking_criteria_guide()

    if ranking_filter_dialog_is_open():
        st.caption("探索条件モーダルを表示中です。ランキング結果の再描画はスキップしています。")
        return
    if (
        not st.session_state.get(MARKET_DATA_RANKING_STATE_KEY)
        and current_ranking_source
        and not ranking_job_is_running(current_ranking_source)
    ):
        cached_build = get_cached_ranking_build(current_ranking_source)
        if cached_build is not None:
            cached_rows, cached_error_rows = cached_build
            st.session_state[MARKET_DATA_RANKING_STATE_KEY] = cached_rows
            st.session_state[MARKET_DATA_RANKING_ERROR_STATE_KEY] = cached_error_rows
            st.session_state[MARKET_DATA_RANKING_SOURCE_STATE_KEY] = current_ranking_source
            st.session_state[MARKET_DATA_RANKING_UPDATED_AT_STATE_KEY] = "再接続後に復元"
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
        st.info("条件が変わりました。ランキング作成で再作成してください。")
        render_mascot_panel(
            "guide",
            message="条件を変えた後は、ランキング作成でもう一度候補を整理しましょう。",
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
        display_rows = ranking_display_rows_with_llm_factor_references(
            display_rows,
            build_llm_factor_references_for_ranking_items(
                display_rows,
                as_of_date=end_date,
            ),
        )
        _register_ranking_results_assistant_context(
            display_rows,
            ranking_policy=ranking_policy,
            forecast_horizon_days=ranking_forecast_horizon_days,
        )
        render_dashboard_header(
            "ランキング候補ダッシュボード",
            "比較候補と深掘り候補を整理するための画面です。買う銘柄を決める画面ではありません。",
            chips=[
                ("ランキング基準", ranking_policy_label(ranking_policy)),
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
        if ranking_policy == RANKING_PURPOSE_REVERSAL_EXPECTATION:
            _render_ranking_profile_chart(display_rows, ranking_policy)
        else:
            chart_col, confidence_col = st.columns(2)
            with chart_col:
                _render_ranking_score_bar_chart(display_rows, ranking_policy)
            with confidence_col:
                _render_ranking_profile_chart(display_rows, ranking_policy)
        deep_dive_symbols = ranking_deep_dive_symbol_options(ranked_rows)
        deep_dive_rank_by_symbol = {
            symbol: index for index, symbol in enumerate(deep_dive_symbols, start=1)
        }
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
            st.markdown("#### ランキング結果を深掘り")
            st.caption(
                "気になる銘柄を1つ選び、銘柄コックピットで価格・予測・スコア理由を確認します。"
            )
            select_col, cta_col = st.columns([3.2, 1.15])
            with select_col:
                st.markdown(
                    '<span class="smai-ranking-deep-dive-select-anchor"></span>',
                    unsafe_allow_html=True,
                )
                selected_symbol = cast(
                    str,
                    st.selectbox(
                        "深掘りする銘柄",
                        deep_dive_symbols,
                        format_func=lambda symbol: (
                            f"{deep_dive_rank_by_symbol[symbol]}位｜{symbol_candidate_label(symbol)}"
                        ),
                        key="market_data_ranking_deep_dive_symbol",
                    ),
                )
            with cta_col:
                st.markdown(
                    '<span class="smai-ranking-deep-dive-cta-label">次のアクション</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<span class="smai-ranking-deep-dive-cta-anchor"></span>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "コックピットを開く →",
                    key="market_data_ranking_open_cockpit",
                    type="primary",
                    use_container_width=True,
                    on_click=_select_ranking_symbol_for_cockpit_with_period,
                    args=(selected_symbol, provider, start_date, end_date),
                )
                selected_universe_row = _symbol_universe_rows_by_symbol().get(
                    selected_symbol.strip().upper(),
                    {},
                )
                render_favorite_button(
                    selected_symbol,
                    name=str(selected_universe_row.get("name") or ""),
                    market=str(selected_universe_row.get("market") or ""),
                    asset_type=str(selected_universe_row.get("asset_type") or ""),
                    currency=str(selected_universe_row.get("currency") or ""),
                    source_screen="ranking",
                    key=f"market_data_ranking_favorite_{selected_symbol}",
                )
        selected_display_row = (
            _ranking_display_row_for_symbol(display_rows, selected_symbol)
            if selected_symbol
            else None
        )
        _register_ranking_deep_dive_assistant_context(
            selected_display_row,
            ranking_policy=ranking_policy,
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
        with col_csv:
            render_csv_download_button(
                label="ランキングCSVをダウンロード",
                data=investment_score_csv_download(ranked_rows),
                file_name="investment_score_ranking.csv",
            )
    elif error_rows:
        _clear_ranking_deep_dive_state()
        st.warning("ランキング対象の価格データを取得できませんでした。")
        _render_ranking_error_rows(cast(list[dict[str, str]], error_rows))
    else:
        _clear_ranking_deep_dive_state()
        st.caption("比較条件を選んで `ランキング作成` を押すと、候補を整理します。")


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


def _latest_currency_by_symbol(bars_by_symbol: dict[str, list[Bar]]) -> dict[str, str]:
    currencies: dict[str, str] = {}
    for symbol, bars in bars_by_symbol.items():
        if not bars:
            continue
        currencies[symbol.strip().upper()] = str(bars[-1].symbol.currency).strip().upper()
    return currencies


RANKING_JPY_FX_PAIRS_BY_CURRENCY: dict[str, str] = {
    "USD": "USDJPY",
    "HKD": "HKDJPY",
    "KRW": "KRWJPY",
    "VND": "VNDJPY",
    "IDR": "IDRJPY",
    "SGD": "SGDJPY",
    "THB": "THBJPY",
    "MYR": "MYRJPY",
    "CNY": "CNYJPY",
}


def _jpy_fx_pair_for_currency(currency: str) -> str:
    return RANKING_JPY_FX_PAIRS_BY_CURRENCY.get(currency.strip().upper(), "")


async def _ranking_jpy_fx_rates(
    adapter: object,
    currencies: Collection[str],
    *,
    at: datetime | None = None,
) -> dict[str, Decimal]:
    get_fx_rates = getattr(adapter, "get_fx_rates", None)
    if get_fx_rates is None:
        return {}
    requested_currencies = {currency.strip().upper() for currency in currencies}
    pairs_by_currency = {
        currency: pair
        for currency in requested_currencies
        if currency not in {"", "JPY"}
        for pair in [_jpy_fx_pair_for_currency(currency)]
        if pair
    }
    if not pairs_by_currency:
        return {}
    try:
        fx_rates = await get_fx_rates(sorted(set(pairs_by_currency.values())), at=at)
    except AppError:
        return {}
    currency_by_pair = {pair: currency for currency, pair in pairs_by_currency.items()}
    rates: dict[str, Decimal] = {}
    for rate in fx_rates:
        pair = str(getattr(rate, "pair", "")).strip().upper()
        currency = currency_by_pair.get(pair)
        if not currency:
            continue
        value = getattr(rate, "rate", None)
        if isinstance(value, Decimal) and value > 0:
            rates[currency] = value
            continue
        parsed = _decimal_from_text(value)
        if parsed is not None and parsed > 0:
            rates[currency] = parsed
    return rates


def _ranking_current_price_jpy(
    price: Decimal | None,
    *,
    source_currency: str,
    usd_jpy_rate: Decimal | None = None,
    jpy_fx_rates: Mapping[str, Decimal] | None = None,
) -> Decimal | None:
    if price is None:
        return None
    source = source_currency.strip().upper()
    if source in {"", "JPY"}:
        return price
    rate = (jpy_fx_rates or {}).get(source)
    if rate is None and source == "USD":
        rate = usd_jpy_rate
    if rate is None or rate <= 0:
        return None
    return price * rate


def _enrich_ranking_rows_with_feature_details(
    rows: list[dict[str, str]],
    feature_rows: list[DailySnapshot],
    *,
    latest_volume_by_symbol: dict[str, str] | None = None,
    source_currency_by_symbol: Mapping[str, str] | None = None,
    usd_jpy_rate: Decimal | None = None,
    jpy_fx_rates: Mapping[str, Decimal] | None = None,
    provider_name: str = "",
) -> list[dict[str, str]]:
    feature_by_symbol = {row.symbol.strip().upper(): row for row in feature_rows}
    latest_volumes = latest_volume_by_symbol or {}
    latest_currencies = source_currency_by_symbol or {}
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        feature = feature_by_symbol.get(symbol)
        if feature is None:
            enriched_rows.append(row)
            continue
        source_currency = latest_currencies.get(symbol) or (
            "JPY" if symbol.endswith(".T") else "USD"
        )
        enriched_rows.append(
            {
                **row,
                "current_price": _format_ranking_decimal_value(feature.last),
                "current_price_jpy": _format_ranking_decimal_value(
                    _ranking_current_price_jpy(
                        feature.last,
                        source_currency=source_currency,
                        usd_jpy_rate=usd_jpy_rate,
                        jpy_fx_rates=jpy_fx_rates,
                    )
                ),
                "current_price_currency": source_currency,
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
    *,
    source_currency: str = "",
    usd_jpy_rate: Decimal | None = None,
    jpy_fx_rates: Mapping[str, Decimal] | None = None,
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
                "current_price_jpy": _format_ranking_decimal_value(
                    _ranking_current_price_jpy(
                        _decimal_from_text(feature.get("last", "")),
                        source_currency=source_currency,
                        usd_jpy_rate=usd_jpy_rate,
                        jpy_fx_rates=jpy_fx_rates,
                    )
                ),
                "current_price_currency": source_currency,
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


def _advanced_forecast_rows_for_ranking(
    bars: list[Bar],
    *,
    horizon_days: int,
) -> list[dict[str, str]]:
    if not bars:
        return []
    results = advanced_forecast_results_for_bars(bars, horizon_days=horizon_days)
    return advanced_forecast_rows_for_results(results, bars)


def _ranking_advanced_forecast_fields(
    advanced_forecast_rows: list[dict[str, str]],
    advanced_forecast_consensus_rows: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    if not advanced_forecast_rows:
        return {}

    consensus_row = (
        advanced_forecast_consensus_rows[0] if advanced_forecast_consensus_rows else None
    )
    model_keys: list[str] = []
    seen_model_keys: set[str] = set()
    for row in advanced_forecast_rows:
        model_key = row.get("adapter", "").strip()
        if model_key and model_key not in seen_model_keys:
            model_keys.append(model_key)
            seen_model_keys.add(model_key)
    fields: dict[str, str] = {
        "advanced_forecast_model": ",".join(model_keys) or "advanced_forecast",
        "advanced_forecast_note": (
            "高度予測は参考シナリオです。AI総合では信頼度で中立寄せしながら控えめに加味します。"
        ),
    }
    if consensus_row is not None:
        horizon = str(consensus_row.get("horizon_days", "")).strip()
        predicted_return = str(consensus_row.get("predicted_return", "")).strip()
        direction_score = str(consensus_row.get("weighted_direction_score", "")).strip()
        confidence = str(consensus_row.get("confidence", "")).strip()
        if horizon:
            fields["advanced_forecast_horizons"] = horizon
            fields["advanced_forecast_horizon_days"] = horizon
        if predicted_return:
            fields["advanced_forecast_predicted_return"] = _signed_percent_from_text(
                predicted_return
            )
        direction_predicted_return = str(
            consensus_row.get("direction_predicted_return", "")
        ).strip()
        if direction_predicted_return:
            fields["advanced_forecast_direction_predicted_return"] = _signed_percent_from_text(
                direction_predicted_return
            )
        direction_score_value = _decimal_from_text(direction_score)
        if direction_score_value is not None:
            fields["advanced_forecast_score"] = _format_ranking_decimal_value(direction_score_value)
        fields.update(_advanced_forecast_ranking_signal_fields(consensus_row))
        if confidence:
            fields["advanced_forecast_confidence"] = confidence
        center_confidence = str(consensus_row.get("center_confidence", "")).strip()
        direction_confidence = str(consensus_row.get("direction_confidence", "")).strip()
        if center_confidence:
            fields["advanced_forecast_center_confidence"] = center_confidence
        if direction_confidence:
            fields["advanced_forecast_direction_confidence"] = direction_confidence
        if consensus_row.get("predicted_return_lower") or consensus_row.get(
            "predicted_return_upper"
        ):
            fields["advanced_forecast_range"] = _advanced_forecast_range_display(consensus_row)
        fields["advanced_forecast_agreement"] = consensus_row.get("agreement", "")
        fields["advanced_forecast_selection_policy"] = consensus_row.get(
            "selection_policy_version", ""
        )
        fields["advanced_forecast_selected_models"] = consensus_row.get("selected_models", "")
        fields["advanced_forecast_center_excluded_models"] = consensus_row.get(
            "center_excluded_models", ""
        )
        fields["advanced_forecast_selection_reason"] = consensus_row.get("selection_reason", "")
        fields["advanced_forecast_consensus_note"] = (
            "AI予測インサイトは、取得期間由来の予測期間と過去検証gateでモデルを選び、"
            "レンジモデルを保守的な中心として統合した参考値です。AI総合では補助材料として控えめに加味します。"
        )
        return fields

    horizons: list[str] = []
    predicted_returns: list[Decimal] = []
    direction_scores: list[Decimal] = []
    ranking_upside_scores: list[Decimal] = []
    ranking_downside_scores: list[Decimal] = []
    ranking_quality_scores: list[Decimal] = []
    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    confidences: list[str] = []
    for row in advanced_forecast_rows:
        horizon = str(row.get("horizon_days", "")).strip()
        if horizon:
            horizons.append(horizon)
        predicted_return = str(row.get("predicted_return", "")).strip()
        predicted_return_value = _decimal_from_text(predicted_return)
        if predicted_return_value is not None:
            predicted_returns.append(predicted_return_value)
        direction_score_value = _decimal_from_text(row.get("direction_score"))
        if direction_score_value is not None:
            direction_scores.append(direction_score_value)
        ranking_signal_fields = _advanced_forecast_ranking_signal_fields(row)
        upside_score = _decimal_from_text(
            ranking_signal_fields.get("advanced_forecast_upside_score")
        )
        if upside_score is not None:
            ranking_upside_scores.append(upside_score)
        downside_score = _decimal_from_text(
            ranking_signal_fields.get("advanced_forecast_downside_score")
        )
        if downside_score is not None:
            ranking_downside_scores.append(downside_score)
        quality_score = _decimal_from_text(
            ranking_signal_fields.get("advanced_forecast_quality_score")
        )
        if quality_score is not None:
            ranking_quality_scores.append(quality_score)
        confidence = str(row.get("confidence", "")).strip()
        if confidence in confidence_rank:
            confidences.append(confidence)

    if horizons:
        fields["advanced_forecast_horizons"] = ",".join(sorted(set(horizons), key=int))
        if len(set(horizons)) == 1:
            fields["advanced_forecast_horizon_days"] = horizons[0]
    if predicted_returns:
        average_return = sum(predicted_returns, Decimal("0")) / Decimal(len(predicted_returns))
        fields["advanced_forecast_predicted_return"] = (
            f"{_format_ranking_decimal_value(average_return)}%"
        )
    if direction_scores:
        average_score = sum(direction_scores, Decimal("0")) / Decimal(len(direction_scores))
        fields["advanced_forecast_score"] = _format_ranking_decimal_value(average_score)
    if ranking_upside_scores:
        fields["advanced_forecast_upside_score"] = _format_ranking_decimal_value(
            sum(ranking_upside_scores, Decimal("0")) / Decimal(len(ranking_upside_scores))
        )
    if ranking_downside_scores:
        fields["advanced_forecast_downside_score"] = _format_ranking_decimal_value(
            max(ranking_downside_scores)
        )
    if ranking_quality_scores:
        fields["advanced_forecast_quality_score"] = _format_ranking_decimal_value(
            sum(ranking_quality_scores, Decimal("0")) / Decimal(len(ranking_quality_scores))
        )
    if confidences:
        fields["advanced_forecast_confidence"] = min(
            confidences,
            key=lambda confidence: confidence_rank[confidence],
        )
    return fields


def _advanced_forecast_ranking_signal_fields(row: Mapping[str, str]) -> dict[str, str]:
    quality_score = _advanced_forecast_ranking_quality_score(row)
    quality_adjustment = min(
        max(quality_score / Decimal("100"), Decimal("0.60")),
        Decimal("1.00"),
    )
    center_return_pct = _decimal_from_text(row.get("predicted_return"))
    lower_return_pct = _decimal_from_text(row.get("predicted_return_lower"))
    direction_score = _decimal_from_text(row.get("weighted_direction_score"))
    if direction_score is None:
        direction_score = _decimal_from_text(row.get("direction_score"))
    upside_raw = (
        _clamp_ranking_score(direction_score)
        if direction_score is not None
        else _advanced_return_pct_to_upside_score(center_return_pct)
    )
    center_downside = _advanced_return_pct_to_downside_score(center_return_pct)
    lower_downside = _advanced_return_pct_to_downside_score(
        lower_return_pct if lower_return_pct is not None else center_return_pct
    )
    downside_raw = max(center_downside, lower_downside)
    upside_score = _neutral_adjusted_ranking_score(upside_raw, quality_adjustment)
    downside_score = _neutral_adjusted_ranking_score(downside_raw, quality_adjustment)
    return {
        "advanced_forecast_upside_score": _format_ranking_decimal_value(upside_score),
        "advanced_forecast_downside_score": _format_ranking_decimal_value(downside_score),
        "advanced_forecast_quality_score": _format_ranking_decimal_value(quality_score),
    }


def _advanced_forecast_ranking_quality_score(row: Mapping[str, str]) -> Decimal:
    confidence_score = {
        "high": Decimal("90"),
        "medium": Decimal("75"),
        "low": Decimal("55"),
    }.get(str(row.get("confidence", "")).strip(), Decimal("50"))
    agreement_score = {
        "HIGH": Decimal("90"),
        "MEDIUM": Decimal("75"),
        "LOW": Decimal("45"),
        "UNKNOWN": Decimal("50"),
    }.get(str(row.get("agreement", "")).strip(), Decimal("50"))
    direction_agreement = (
        _decimal_from_text(row.get("direction_agreement_score"))
        or _decimal_from_text(row.get("direction_accuracy"))
        or Decimal("50")
    )
    direction_accuracy = (
        _decimal_from_text(row.get("mean_direction_accuracy"))
        or _decimal_from_text(row.get("direction_accuracy"))
        or Decimal("50")
    )
    rmse_score = _advanced_forecast_rmse_quality_score(row.get("mean_rmse_improvement"))
    if rmse_score == Decimal("50"):
        rmse_score = _advanced_forecast_rmse_quality_score(row.get("rmse_improvement"))
    sample_score = _advanced_forecast_sample_quality_score(row.get("sample_count"))
    return _clamp_ranking_score(
        (confidence_score * Decimal("0.25"))
        + (agreement_score * Decimal("0.20"))
        + (_clamp_ranking_score(direction_agreement) * Decimal("0.20"))
        + (_clamp_ranking_score(direction_accuracy) * Decimal("0.15"))
        + (rmse_score * Decimal("0.10"))
        + (sample_score * Decimal("0.10"))
    )


def _advanced_forecast_rmse_quality_score(value: object) -> Decimal:
    improvement = _decimal_from_text(value)
    if improvement is None:
        return Decimal("50")
    if improvement > 0:
        return Decimal("65")
    if improvement < 0:
        return Decimal("45")
    return Decimal("50")


def _advanced_forecast_sample_quality_score(value: object) -> Decimal:
    sample_count = _decimal_from_text(value)
    if sample_count is None or sample_count <= 0:
        return Decimal("50")
    if sample_count >= Decimal("60"):
        return Decimal("85")
    if sample_count >= Decimal("24"):
        return Decimal("70")
    return Decimal("55")


def _advanced_return_pct_to_upside_score(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("50")
    return _clamp_ranking_score(Decimal("50") + (value * Decimal("7.5")))


def _advanced_return_pct_to_downside_score(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("50")
    return _clamp_ranking_score(Decimal("50") - (value * Decimal("7.5")))


def _neutral_adjusted_ranking_score(score: Decimal, factor: Decimal) -> Decimal:
    return _clamp_ranking_score(Decimal("50") + ((score - Decimal("50")) * factor))


def _clamp_ranking_score(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value))


def _enrich_ranking_rows_with_advanced_forecast(
    rows: list[dict[str, str]],
    advanced_fields_by_symbol: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    if not advanced_fields_by_symbol:
        return rows
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        advanced_fields = advanced_fields_by_symbol.get(symbol, {})
        if advanced_fields:
            enriched_rows.append(_ranking_row_with_advanced_forecast_signal(row, advanced_fields))
        else:
            enriched_rows.append(row)
    return enriched_rows


def _ranking_row_with_advanced_forecast_signal(
    row: dict[str, str],
    advanced_fields: dict[str, str],
) -> dict[str, str]:
    merged = {**row, **advanced_fields}
    advanced_upside = _decimal_from_text(advanced_fields.get("advanced_forecast_upside_score"))
    advanced_downside = _decimal_from_text(advanced_fields.get("advanced_forecast_downside_score"))
    if advanced_upside is None and advanced_downside is None:
        return merged

    base_upside = _decimal_from_text(row.get("upside_signal_score")) or Decimal("50")
    base_downside = _decimal_from_text(row.get("downside_signal_score")) or Decimal("50")
    blended_upside = _blend_advanced_direction_score(
        base_upside,
        advanced_upside if advanced_upside is not None else Decimal("50"),
    )
    blended_downside = _blend_advanced_direction_score(
        base_downside,
        advanced_downside if advanced_downside is not None else Decimal("50"),
    )
    direction_net = _clamp_ranking_score(
        Decimal("50") + ((blended_upside - blended_downside) / Decimal("2"))
    )
    merged.update(
        {
            "upside_signal_score": _format_ranking_decimal_value(blended_upside),
            "downside_signal_score": _format_ranking_decimal_value(blended_downside),
            "direction_net_score": _format_ranking_decimal_value(direction_net),
            "direction_signal_label": _ranking_direction_label_from_scores(
                blended_upside,
                blended_downside,
            ),
            "advanced_forecast_direction_note": (
                "上昇気配・下降警戒は通常方向シグナルにAI予測インサイトを25%までブレンドしています。"
            ),
        }
    )
    return merged


def _blend_advanced_direction_score(base_score: Decimal, advanced_score: Decimal) -> Decimal:
    return _clamp_ranking_score((base_score * Decimal("0.75")) + (advanced_score * Decimal("0.25")))


def _ranking_direction_label_from_scores(upside: Decimal, downside: Decimal) -> str:
    signal_gap = upside - downside
    if upside >= Decimal("80") and signal_gap >= Decimal("20"):
        return "STRONG_UPSIDE"
    if upside >= Decimal("65") and signal_gap >= Decimal("10"):
        return "MODERATE_UPSIDE"
    if downside >= Decimal("80") and signal_gap <= Decimal("-20"):
        return "STRONG_DOWNSIDE"
    if downside >= Decimal("65") and signal_gap <= Decimal("-10"):
        return "MODERATE_DOWNSIDE"
    return "NEUTRAL"


async def _build_market_data_ranking_rows(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if provider in LIVE_MARKET_DATA_PROVIDERS and len(symbols) > RANKING_PIPELINE_COHORT_SIZE:
        return await _build_large_market_data_ranking_rows(
            symbols,
            start=start,
            end=end,
            provider=provider,
            progress_callback=progress_callback,
        )
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


async def _build_large_market_data_ranking_rows(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Build large live rankings in bounded cohorts to cap peak memory."""

    cohorts = [
        symbols[index : index + RANKING_PIPELINE_COHORT_SIZE]
        for index in range(0, len(symbols), RANKING_PIPELINE_COHORT_SIZE)
    ]
    rows: list[dict[str, str]] = []
    error_rows: list[dict[str, str]] = []
    retained_top_rows: list[dict[str, str]] = []
    retained_cache_symbols: set[str] = set()
    for cohort_index, cohort in enumerate(cohorts):
        cohort_start = cohort_index / len(cohorts)
        cohort_width = 1 / len(cohorts)

        def cohort_progress(message: str, ratio: float) -> None:
            _report_ranking_progress(
                progress_callback,
                f"{message} ({cohort_index + 1}/{len(cohorts)} cohort)",
                min(0.99, cohort_start + (cohort_width * ratio)),
            )

        try:
            cohort_rows, cohort_errors = await _build_market_data_ranking_rows_fast(
                cohort,
                start=start,
                end=end,
                provider=provider,
                progress_callback=cohort_progress,
                include_advanced_forecast=False,
            )
        except AppError as exc:
            cohort_rows = []
            cohort_errors = ranking_provider_error_rows(provider, cohort, exc)
        except Exception as original_exc:  # noqa: BLE001 - keep later cohorts usable.
            cohort_rows = []
            cohort_errors = ranking_provider_error_rows(
                provider,
                cohort,
                DataSourceError(
                    "ランキングの一部候補を処理できませんでした。",
                    details={
                        "operation": "ranking_build_cohort",
                        "cohort": cohort_index + 1,
                        "cohort_count": len(cohorts),
                        "error_type": type(original_exc).__name__,
                    },
                ),
            )
        rows.extend(cohort_rows)
        error_rows.extend(cohort_errors)
        retained_top_rows = rank_investment_score_rows([*retained_top_rows, *cohort_rows])[
            :RANKING_ADVANCED_FORECAST_CANDIDATE_LIMIT
        ]
        next_retained_symbols = {
            str(row.get("symbol", "")).strip().upper()
            for row in retained_top_rows
            if str(row.get("symbol", "")).strip()
        }
        releasable_symbols = (
            {str(symbol).strip().upper() for symbol in cohort} | retained_cache_symbols
        ) - next_retained_symbols
        _release_ranking_cohort_cache(provider, sorted(releasable_symbols))
        retained_cache_symbols = next_retained_symbols
    _report_ranking_progress(progress_callback, "ランキングをまとめています。", 0.99)
    provisional_rows = rank_investment_score_rows(rows)
    advanced_symbols = [
        str(row.get("symbol", "")).strip().upper()
        for row in provisional_rows[:RANKING_ADVANCED_FORECAST_CANDIDATE_LIMIT]
        if str(row.get("symbol", "")).strip()
    ]
    if not advanced_symbols:
        return provisional_rows, error_rows
    _report_ranking_progress(
        progress_callback,
        "上位候補に高度予測を適用しています。",
        0.995,
    )
    try:
        advanced_rows, _advanced_errors = await _build_market_data_ranking_rows_fast(
            advanced_symbols,
            start=start,
            end=end,
            provider=provider,
            progress_callback=None,
            include_advanced_forecast=True,
        )
        advanced_fields_by_symbol = {
            str(row.get("symbol", ""))
            .strip()
            .upper(): {
                key: value for key, value in row.items() if key.startswith("advanced_forecast_")
            }
            for row in advanced_rows
            if str(row.get("symbol", "")).strip()
        }
        provisional_rows = _enrich_ranking_rows_with_advanced_forecast(
            provisional_rows,
            advanced_fields_by_symbol,
        )
    except Exception:  # noqa: BLE001 - advanced forecast is optional enrichment.
        pass
    finally:
        _release_ranking_cohort_cache(provider, advanced_symbols)
    return rank_investment_score_rows(provisional_rows), error_rows


async def _build_market_data_ranking_rows_fast(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
    progress_callback: RankingProgressCallback | None = None,
    include_advanced_forecast: bool = True,
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
    error_rows: list[dict[str, str]] = []
    provider_fetch_error_symbols: set[str] = set()
    provider_symbols_by_symbol = _provider_symbols_by_display_symbol(symbols, provider)
    fetch_symbols = _unique_provider_symbols(provider_symbols_by_symbol.values())
    symbol_chunks = ranking_symbol_chunks(fetch_symbols)
    display_symbols_by_provider_symbol = _display_symbols_by_provider_symbol(
        provider_symbols_by_symbol
    )
    for index, symbol_chunk in enumerate(symbol_chunks, start=1):
        _report_ranking_progress(
            progress_callback,
            f"価格データをまとめて取得しています ({index}/{len(symbol_chunks)})。",
            0.1 + (0.35 * (index - 1) / len(symbol_chunks)),
        )
        chunk_bars, chunk_errors, chunk_failed_symbols = await _fetch_ranking_ohlcv_tolerant(
            adapter,
            symbol_chunk,
            provider=provider,
            start=feature_start_dt,
            end=end_dt,
            display_symbols_by_provider_symbol=display_symbols_by_provider_symbol,
        )
        bars.extend(chunk_bars)
        error_rows.extend(chunk_errors)
        provider_fetch_error_symbols.update(chunk_failed_symbols)
    bars = _bars_with_display_symbols(
        bars,
        provider_symbols_by_symbol=provider_symbols_by_symbol,
    )
    _report_ranking_progress(progress_callback, "価格データを整理しています。", 0.45)
    bars_by_symbol = _ranking_bars_by_symbol(symbols, bars)
    source_currency_by_symbol = _latest_currency_by_symbol(bars_by_symbol)
    source_currencies = {
        currency or ("JPY" if symbol.endswith(".T") else "USD")
        for symbol, currency in source_currency_by_symbol.items()
    }
    jpy_fx_rates = await _ranking_jpy_fx_rates(adapter, source_currencies)
    usd_jpy_rate = jpy_fx_rates.get("USD")

    available_symbols: list[str] = []
    quotes: list[Quote] = []
    for symbol in symbols:
        symbol_bars = bars_by_symbol[symbol]
        if not symbol_bars:
            if symbol in provider_fetch_error_symbols:
                continue
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
        if len(symbol_bars) < 2:
            error_rows.append(
                ranking_insufficient_bars_error_row(
                    provider=provider,
                    symbol=symbol,
                    bar_count=len(symbol_bars),
                    display_start=start,
                    display_end=end,
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
    provider_fundamentals, fundamental_error_rows = await _fetch_ranking_fundamentals_tolerant(
        adapter,
        provider_available_symbols,
        provider=provider,
        as_of=end,
        display_symbols_by_provider_symbol=display_symbols_by_provider_symbol,
    )
    error_rows.extend(fundamental_error_rows)
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
        progress = 0.65 + (0.05 * index / len(available_symbols))
        _report_ranking_progress(
            progress_callback,
            f"基本予測を計算しています ({index}/{len(available_symbols)})。",
            progress,
        )

    advanced_forecast_fields_by_symbol: dict[str, dict[str, str]] = {}
    if include_advanced_forecast:
        advanced_forecast_fields_by_symbol = _ranking_advanced_forecast_fields_for_symbols(
            available_symbols,
            bars_by_symbol=bars_by_symbol,
            horizon_days=forecast_horizon_days,
            progress_callback=progress_callback,
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
        source_currency_by_symbol=source_currency_by_symbol,
        usd_jpy_rate=usd_jpy_rate,
        jpy_fx_rates=jpy_fx_rates,
        provider_name=provider_name,
    )
    score_rows = _enrich_ranking_rows_with_advanced_forecast(
        score_rows,
        advanced_forecast_fields_by_symbol,
    )
    ranked_rows = rank_investment_score_rows(score_rows)
    _report_ranking_progress(progress_callback, "ランキングを並べ替えています。", 0.98)
    return ranked_rows, error_rows


def _ranking_advanced_forecast_fields_for_symbols(
    symbols: Sequence[str],
    *,
    bars_by_symbol: Mapping[str, list[Bar]],
    horizon_days: int,
    progress_callback: RankingProgressCallback | None,
) -> dict[str, dict[str, str]]:
    fields_by_symbol: dict[str, dict[str, str]] = {}
    completed_fields_by_symbol: dict[str, dict[str, str]] = {}
    pending: list[tuple[str, list[Bar]]] = []
    for symbol in symbols:
        symbol_bars = bars_by_symbol[symbol]
        cached = _get_cached_ranking_advanced_forecast(
            symbol,
            symbol_bars,
            horizon_days=horizon_days,
        )
        if cached is None:
            pending.append((symbol, symbol_bars))
        elif cached:
            fields_by_symbol[symbol.strip().upper()] = cached

    if not pending:
        _report_ranking_progress(
            progress_callback,
            "高度予測は同日の計算結果を再利用しました。",
            0.85,
        )
        return fields_by_symbol

    def consume(
        completed: Iterable[tuple[str, list[Any], str | None]],
    ) -> None:
        for completed_count, (symbol, results, _error) in enumerate(completed, start=1):
            symbol_bars = bars_by_symbol[symbol]
            advanced_fields: dict[str, str] = {}
            if results:
                advanced_fields = _ranking_advanced_forecast_fields(
                    advanced_forecast_rows_for_results(results, symbol_bars),
                    advanced_forecast_consensus_rows_for_results(results),
                )
            completed_fields_by_symbol[symbol] = advanced_fields
            if advanced_fields:
                fields_by_symbol[symbol.strip().upper()] = advanced_fields
            if completed_count == 1 or completed_count % 10 == 0 or completed_count == len(pending):
                _report_ranking_progress(
                    progress_callback,
                    f"高度予測を計算しています ({completed_count}/{len(pending)})。",
                    0.70 + (0.15 * completed_count / len(pending)),
                )

    if len(pending) < 12:
        consume(
            evaluate_advanced_forecasts_for_symbol(symbol, bars, horizon_days)
            for symbol, bars in pending
        )
        _cache_completed_ranking_advanced_forecasts(
            completed_fields_by_symbol,
            bars_by_symbol=bars_by_symbol,
            horizon_days=horizon_days,
        )
        return fields_by_symbol

    from joblib import Parallel, delayed  # type: ignore[import-untyped]  # noqa: PLC0415

    profile = resolve_performance_profile()
    workers = max(
        1,
        min(RANKING_ADVANCED_FORECAST_MAX_WORKERS, profile.processing.forecast_workers),
    )
    completed = Parallel(
        n_jobs=workers,
        backend="threading",
        batch_size=1,
        pre_dispatch=workers,
        return_as="generator_unordered",
    )(
        delayed(evaluate_advanced_forecasts_for_symbol)(symbol, bars, horizon_days)
        for symbol, bars in pending
    )
    consume(completed)
    _cache_completed_ranking_advanced_forecasts(
        completed_fields_by_symbol,
        bars_by_symbol=bars_by_symbol,
        horizon_days=horizon_days,
    )
    return fields_by_symbol


def _cache_completed_ranking_advanced_forecasts(
    fields_by_symbol: Mapping[str, dict[str, str]],
    *,
    bars_by_symbol: Mapping[str, list[Bar]],
    horizon_days: int,
) -> None:
    """Publish per-symbol forecast cache entries only after the batch completed."""

    for symbol, fields in fields_by_symbol.items():
        _cache_ranking_advanced_forecast(
            symbol,
            bars_by_symbol[symbol],
            fields,
            horizon_days=horizon_days,
        )


async def _fetch_ranking_ohlcv_tolerant(
    adapter: Any,
    symbol_chunk: list[str],
    *,
    provider: str,
    start: datetime,
    end: datetime,
    display_symbols_by_provider_symbol: Mapping[str, list[str]],
) -> tuple[list[Bar], list[dict[str, str]], set[str]]:
    """Fetch ranking OHLCV without letting one unsupported ticker kill the whole ranking."""

    if not symbol_chunk:
        return [], [], set()
    cached_bars: list[Bar] = []
    missing_symbols: list[str] = []
    for provider_symbol in symbol_chunk:
        cached = _get_cached_ranking_ohlcv(
            provider,
            provider_symbol,
            start=start,
            end=end,
        )
        if cached is None:
            missing_symbols.append(provider_symbol)
        else:
            cached_bars.extend(cached)
    if not missing_symbols:
        return cached_bars, [], set()
    try:
        fetched_bars = await adapter.fetch_ohlcv(missing_symbols, start=start, end=end)
        _cache_ranking_ohlcv(
            provider,
            missing_symbols,
            fetched_bars,
            start=start,
            end=end,
        )
        return [*cached_bars, *fetched_bars], [], set()
    except AppError as exc:
        if len(missing_symbols) <= 1:
            display_symbols = display_symbols_by_provider_symbol.get(
                missing_symbols[0], missing_symbols
            )
            return (
                cached_bars,
                ranking_provider_error_rows(provider, display_symbols, exc),
                set(display_symbols),
            )

    bars: list[Bar] = list(cached_bars)
    error_rows: list[dict[str, str]] = []
    failed_display_symbols: set[str] = set()
    for provider_symbol in missing_symbols:
        display_symbols = display_symbols_by_provider_symbol.get(provider_symbol, [provider_symbol])
        try:
            symbol_bars = await adapter.fetch_ohlcv([provider_symbol], start=start, end=end)
            bars.extend(symbol_bars)
            _cache_ranking_ohlcv(
                provider,
                [provider_symbol],
                symbol_bars,
                start=start,
                end=end,
            )
        except AppError as exc:
            error_rows.extend(ranking_provider_error_rows(provider, display_symbols, exc))
            failed_display_symbols.update(display_symbols)
    return bars, error_rows, failed_display_symbols


async def _fetch_ranking_fundamentals_tolerant(
    adapter: Any,
    provider_symbols: list[str],
    *,
    provider: str,
    as_of: date,
    display_symbols_by_provider_symbol: Mapping[str, list[str]],
) -> tuple[list[FundamentalSnapshot], list[dict[str, str]]]:
    """Fetch optional fundamentals without failing an otherwise usable price ranking."""

    fundamentals: list[FundamentalSnapshot] = []
    error_rows: list[dict[str, str]] = []
    semaphore = asyncio.Semaphore(RANKING_FUNDAMENTAL_CONCURRENCY)

    async def fetch_one(
        provider_symbol: str,
    ) -> tuple[list[FundamentalSnapshot], list[dict[str, str]]]:
        cached = _get_cached_ranking_fundamentals(provider, provider_symbol, as_of=as_of)
        if cached is not None:
            return cached, []
        display_symbols = display_symbols_by_provider_symbol.get(provider_symbol, [provider_symbol])
        try:
            async with semaphore:
                async with asyncio.timeout(RANKING_FUNDAMENTAL_TIMEOUT_SECONDS):
                    fetched = await adapter.fetch_fundamentals([provider_symbol], as_of=as_of)
            _cache_ranking_fundamentals(
                provider,
                provider_symbol,
                fetched,
                as_of=as_of,
            )
            return fetched, []
        except TimeoutError:
            timeout_error = ProviderTimeoutError(
                "ファンダメンタル情報の取得がタイムアウトしました。",
                details={
                    "operation": "ranking_fetch_fundamentals",
                    "symbol": provider_symbol,
                },
            )
            return [], ranking_provider_error_rows(provider, display_symbols, timeout_error)
        except AppError as app_error:
            return [], ranking_provider_error_rows(provider, display_symbols, app_error)
        except Exception as original_exc:  # noqa: BLE001 - fundamentals are optional.
            data_source_error = DataSourceError(
                "ファンダメンタル情報を利用できませんでした。",
                details={
                    "operation": "ranking_fetch_fundamentals",
                    "symbol": provider_symbol,
                    "error_type": type(original_exc).__name__,
                },
            )
            return [], ranking_provider_error_rows(provider, display_symbols, data_source_error)

    results = await asyncio.gather(*(fetch_one(symbol) for symbol in provider_symbols))
    for fetched, errors in results:
        fundamentals.extend(fetched)
        error_rows.extend(errors)
    return fundamentals, error_rows


def _display_symbols_by_provider_symbol(
    provider_symbols_by_symbol: Mapping[str, str],
) -> dict[str, list[str]]:
    display_symbols: dict[str, list[str]] = {}
    for display_symbol, provider_symbol in provider_symbols_by_symbol.items():
        display_symbols.setdefault(provider_symbol, []).append(display_symbol)
    return display_symbols


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


def _execute_market_data_ranking_job(
    *,
    cache_key: str,
    ranking_symbols: list[str],
    start: date,
    end: date,
    provider: str,
    progress_callback: BackgroundRankingProgressCallback,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Run a ranking without reading or writing Streamlit session state."""

    progress_callback("ランキング対象と取得条件を確認しています。", 0.04)
    cached_build = get_cached_ranking_build(cache_key)
    if cached_build is not None and cached_build[0]:
        rows, error_rows = cached_build
        progress_callback("同じ条件の完成済みランキングを再利用しています。", 0.98)
    else:
        with maintenance_operation("ranking_build_preflight"):
            _run_symbol_database_preflight_refresh(
                ranking_symbol_db_preflight_symbols(ranking_symbols),
                context="ranking",
                max_items=ranking_symbol_db_preflight_limit(len(ranking_symbols)),
                update_session_state=False,
            )
        with maintenance_operation("ranking_build"):
            rows, error_rows = asyncio.run(
                _build_market_data_ranking_rows(
                    ranking_symbols,
                    start=start,
                    end=end,
                    provider=provider,
                    progress_callback=progress_callback,
                )
            )
    set_cached_ranking_build(cache_key, rows=rows, error_rows=error_rows)
    progress_callback("ランキング更新が完了しました。", 1.0)
    return rows, error_rows


@st.fragment(run_every=2)
def _render_ranking_background_job(cache_key: str) -> None:
    """Poll and adopt a process-wide ranking from any browser session."""

    if not cache_key:
        return
    job = get_ranking_job(cache_key)
    if job is None:
        return
    if job.status == "running":
        st.markdown(
            workflow_loading_html(
                title="ランキングを作成中",
                message=("画面を閉じたり通信が切り替わっても、サーバー側で作成を継続します。"),
                current_step=job.message,
                progress=job.ratio,
                mode="inline",
                headlines=workflow_loading_headlines_from_cache(max_items=4)[0],
                headline_note="取得済みの市場トピックを表示しています。",
            ),
            unsafe_allow_html=True,
        )
        return
    if job.status == "failed":
        error_suffix = f"（{job.error_type}）" if job.error_type else ""
        st.error(
            "ランキング作成が途中で終了しました。条件は保持されています。"
            f"もう一度実行してください。{error_suffix}"
        )
        return
    adopted = str(st.session_state.get(RANKING_JOB_ADOPTED_STATE_KEY) or "")
    if adopted == job.job_id:
        st.success("ランキング作成が完了しました。")
        return
    st.session_state[MARKET_DATA_RANKING_STATE_KEY] = job.rows
    st.session_state[MARKET_DATA_RANKING_ERROR_STATE_KEY] = job.error_rows
    st.session_state[MARKET_DATA_RANKING_SOURCE_STATE_KEY] = cache_key
    st.session_state[MARKET_DATA_RANKING_UPDATED_AT_STATE_KEY] = datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )
    st.session_state[RANKING_JOB_ADOPTED_STATE_KEY] = job.job_id
    st.session_state[RANKING_JOB_HISTORY_PENDING_STATE_KEY] = job.job_id
    st.rerun()


def _touch_ranking_client_session(*, force: bool = False) -> bool:
    now = perf_time.monotonic()
    previous = st.session_state.get(RANKING_CLIENT_SESSION_TOUCH_STATE_KEY, 0.0)
    try:
        previous_value = float(previous)
    except (TypeError, ValueError):
        previous_value = 0.0
    if not force and now - previous_value < RANKING_CLIENT_SESSION_TOUCH_INTERVAL_SECONDS:
        return False
    client_id = str(st.session_state.get(CLIENT_ID_STATE_KEY) or "")
    if not client_id:
        return False
    selected_symbol = (
        _symbol_from_candidate(str(st.session_state.get("market_data_symbol_candidate", ""))) or ""
    )
    saved = save_client_session_if_changed(
        cast(Mapping[str, Any], st.session_state),
        client_id=client_id,
        selected_symbol=selected_symbol,
        force_write=True,
    )
    st.session_state[RANKING_CLIENT_SESSION_TOUCH_STATE_KEY] = now
    return saved


def _report_ranking_progress(
    progress_callback: RankingProgressCallback | None,
    message: str,
    ratio: float,
) -> None:
    if progress_callback is not None:
        progress_callback(message, ratio)


@st.cache_resource(show_spinner=False)
def _ranking_build_cache() -> dict[str, dict[str, list[dict[str, str]]]]:
    """Share completed market-data rankings across reconnecting UI sessions."""

    return {}


@st.cache_resource(show_spinner=False)
def _ranking_build_cache_accessed_at() -> dict[str, float]:
    return {}


@st.cache_resource(show_spinner=False)
def _ranking_ohlcv_cache() -> dict[tuple[str, str, str, str], list[Bar]]:
    return {}


@st.cache_resource(show_spinner=False)
def _ranking_ohlcv_cache_accessed_at() -> dict[tuple[str, str, str, str], float]:
    return {}


def _ranking_ohlcv_cache_key(
    provider: str,
    symbol: str,
    *,
    start: datetime,
    end: datetime,
) -> tuple[str, str, str, str]:
    return (
        provider.strip().lower(),
        symbol.strip().upper(),
        start.isoformat(),
        end.isoformat(),
    )


def _get_cached_ranking_ohlcv(
    provider: str,
    symbol: str,
    *,
    start: datetime,
    end: datetime,
) -> list[Bar] | None:
    key = _ranking_ohlcv_cache_key(provider, symbol, start=start, end=end)
    cache = _ranking_ohlcv_cache()
    cached = cache.get(key)
    if cached is None:
        return None
    accessed_at = _ranking_ohlcv_cache_accessed_at()
    now = perf_time.monotonic()
    if now - accessed_at.get(key, now) > RANKING_OHLCV_CACHE_TTL_SECONDS:
        cache.pop(key, None)
        accessed_at.pop(key, None)
        return None
    accessed_at[key] = now
    return cached


def _cache_ranking_ohlcv(
    provider: str,
    symbols: Sequence[str],
    bars: Sequence[Bar],
    *,
    start: datetime,
    end: datetime,
) -> None:
    cache = _ranking_ohlcv_cache()
    accessed_at = _ranking_ohlcv_cache_accessed_at()
    bars_by_symbol: dict[str, list[Bar]] = {symbol.strip().upper(): [] for symbol in symbols}
    for bar in bars:
        raw_symbol = str(getattr(getattr(bar, "symbol", None), "raw", "")).strip().upper()
        if raw_symbol:
            bars_by_symbol.setdefault(raw_symbol, []).append(bar)
    for symbol in symbols:
        normalized = symbol.strip().upper()
        symbol_bars = bars_by_symbol.get(normalized, [])
        if not symbol_bars:
            continue
        key = _ranking_ohlcv_cache_key(provider, normalized, start=start, end=end)
        cache.pop(key, None)
        cache[key] = symbol_bars
        accessed_at[key] = perf_time.monotonic()
    while len(cache) > MAX_RANKING_OHLCV_CACHE_SYMBOLS:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key)
        accessed_at.pop(oldest_key, None)


@st.cache_resource(show_spinner=False)
def _ranking_fundamental_cache() -> dict[tuple[str, str, str], list[FundamentalSnapshot]]:
    return {}


@st.cache_resource(show_spinner=False)
def _ranking_fundamental_cache_accessed_at() -> dict[tuple[str, str, str], float]:
    return {}


def _ranking_fundamental_cache_key(
    provider: str,
    symbol: str,
    *,
    as_of: date,
) -> tuple[str, str, str]:
    return provider.strip().lower(), symbol.strip().upper(), as_of.isoformat()


def _get_cached_ranking_fundamentals(
    provider: str,
    symbol: str,
    *,
    as_of: date,
) -> list[FundamentalSnapshot] | None:
    key = _ranking_fundamental_cache_key(provider, symbol, as_of=as_of)
    cache = _ranking_fundamental_cache()
    cached = cache.get(key)
    if cached is None:
        return None
    accessed_at = _ranking_fundamental_cache_accessed_at()
    now = perf_time.monotonic()
    if now - accessed_at.get(key, now) > RANKING_FUNDAMENTAL_CACHE_TTL_SECONDS:
        cache.pop(key, None)
        accessed_at.pop(key, None)
        return None
    accessed_at[key] = now
    return cached


def _cache_ranking_fundamentals(
    provider: str,
    symbol: str,
    fundamentals: list[FundamentalSnapshot],
    *,
    as_of: date,
) -> None:
    if not fundamentals:
        return
    cache = _ranking_fundamental_cache()
    accessed_at = _ranking_fundamental_cache_accessed_at()
    key = _ranking_fundamental_cache_key(provider, symbol, as_of=as_of)
    cache.pop(key, None)
    cache[key] = fundamentals
    accessed_at[key] = perf_time.monotonic()
    while len(cache) > MAX_RANKING_FUNDAMENTAL_CACHE_SYMBOLS:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key)
        accessed_at.pop(oldest_key, None)


@st.cache_resource(show_spinner=False)
def _ranking_advanced_forecast_cache() -> dict[tuple[str, int, int, str, str], dict[str, str]]:
    return {}


@st.cache_resource(show_spinner=False)
def _ranking_advanced_forecast_cache_accessed_at() -> dict[tuple[str, int, int, str, str], float]:
    return {}


def _ranking_advanced_forecast_cache_key(
    symbol: str,
    bars: Sequence[Bar],
    *,
    horizon_days: int,
) -> tuple[str, int, int, str, str] | None:
    if not bars:
        return None
    latest = bars[-1]
    return (
        symbol.strip().upper(),
        horizon_days,
        len(bars),
        latest.ts.isoformat(),
        str(latest.close),
    )


def _get_cached_ranking_advanced_forecast(
    symbol: str,
    bars: Sequence[Bar],
    *,
    horizon_days: int,
) -> dict[str, str] | None:
    key = _ranking_advanced_forecast_cache_key(
        symbol,
        bars,
        horizon_days=horizon_days,
    )
    if key is None:
        return None
    cache = _ranking_advanced_forecast_cache()
    cached = cache.get(key)
    if cached is None:
        return None
    accessed_at = _ranking_advanced_forecast_cache_accessed_at()
    now = perf_time.monotonic()
    if now - accessed_at.get(key, now) > RANKING_ADVANCED_FORECAST_CACHE_TTL_SECONDS:
        cache.pop(key, None)
        accessed_at.pop(key, None)
        return None
    accessed_at[key] = now
    return cached


def _cache_ranking_advanced_forecast(
    symbol: str,
    bars: Sequence[Bar],
    fields: dict[str, str],
    *,
    horizon_days: int,
) -> None:
    key = _ranking_advanced_forecast_cache_key(
        symbol,
        bars,
        horizon_days=horizon_days,
    )
    if key is None:
        return
    cache = _ranking_advanced_forecast_cache()
    accessed_at = _ranking_advanced_forecast_cache_accessed_at()
    cache.pop(key, None)
    cache[key] = fields
    accessed_at[key] = perf_time.monotonic()
    while len(cache) > MAX_RANKING_ADVANCED_FORECAST_CACHE_SYMBOLS:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key)
        accessed_at.pop(oldest_key, None)


def _release_ranking_cohort_cache(provider: str, symbols: Sequence[str]) -> None:
    """Release raw per-symbol caches after a large ranking cohort completes."""

    provider_key = provider.strip().lower()
    display_symbols = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
    provider_symbols = {
        symbol_provider_symbol(symbol, provider).strip().upper() for symbol in display_symbols
    }
    cache_symbols = display_symbols | provider_symbols
    ohlcv_cache = _ranking_ohlcv_cache()
    ohlcv_accessed_at = _ranking_ohlcv_cache_accessed_at()
    for ohlcv_key in tuple(ohlcv_cache):
        if ohlcv_key[0] == provider_key and ohlcv_key[1] in cache_symbols:
            ohlcv_cache.pop(ohlcv_key, None)
            ohlcv_accessed_at.pop(ohlcv_key, None)
    fundamental_cache = _ranking_fundamental_cache()
    fundamental_accessed_at = _ranking_fundamental_cache_accessed_at()
    for fundamental_key in tuple(fundamental_cache):
        if fundamental_key[0] == provider_key and fundamental_key[1] in cache_symbols:
            fundamental_cache.pop(fundamental_key, None)
            fundamental_accessed_at.pop(fundamental_key, None)
    advanced_cache = _ranking_advanced_forecast_cache()
    advanced_accessed_at = _ranking_advanced_forecast_cache_accessed_at()
    for advanced_key in tuple(advanced_cache):
        if advanced_key[0] in display_symbols:
            advanced_cache.pop(advanced_key, None)
            advanced_accessed_at.pop(advanced_key, None)
    gc.collect()


def get_cached_ranking_build(
    cache_key: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]] | None:
    cached = _ranking_build_cache().get(cache_key)
    if cached is None:
        return None
    accessed_at = _ranking_build_cache_accessed_at()
    now = perf_time.monotonic()
    if now - accessed_at.get(cache_key, now) > RANKING_BUILD_CACHE_TTL_SECONDS:
        _ranking_build_cache().pop(cache_key, None)
        accessed_at.pop(cache_key, None)
        return None
    accessed_at[cache_key] = now
    return cached.get("rows", []), cached.get("error_rows", [])


def set_cached_ranking_build(
    cache_key: str,
    *,
    rows: list[dict[str, str]],
    error_rows: list[dict[str, str]],
) -> None:
    cache = _ranking_build_cache()
    accessed_at = _ranking_build_cache_accessed_at()
    if cache_key in cache:
        cache.pop(cache_key)
    cache[cache_key] = {"rows": rows, "error_rows": error_rows}
    accessed_at[cache_key] = perf_time.monotonic()
    while len(cache) > MAX_RANKING_BUILD_CACHE_ENTRIES:
        oldest_key = next(iter(cache))
        cache.pop(oldest_key)
        accessed_at.pop(oldest_key, None)


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
        preview_bars = getattr(preview, "bars", [])
        preview_currency = (
            str(preview_bars[0].symbol.currency).strip().upper() if preview_bars else ""
        )
        preview_fx_rate = chart_fx_rate_from_rows(
            getattr(preview, "fx_rows", []),
            source_currency=preview_currency,
        )
        preview_rows = _enrich_ranking_rows_with_feature_display_rows(
            preview.investment_score_rows,
            getattr(preview, "feature_rows", []),
            source_currency=preview_currency,
            usd_jpy_rate=preview_fx_rate,
            jpy_fx_rates={preview_currency: preview_fx_rate} if preview_fx_rate is not None else {},
        )
        advanced_fields = _ranking_advanced_forecast_fields(
            _advanced_forecast_rows_for_ranking(
                getattr(preview, "bars", []),
                horizon_days=forecast_horizon_days,
            )
        )
        if advanced_fields:
            preview_rows = [
                (
                    {**row, **advanced_fields}
                    if row.get("symbol", "").strip().upper() == symbol.strip().upper()
                    else row
                )
                for row in preview_rows
            ]
        return preview_rows, [
            {"symbol": symbol, **error_row} for error_row in getattr(preview, "error_rows", [])
        ]

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
    # A keyword left from a previous Cockpit visit filters the handoff symbol
    # out of the selectbox. Clear only this transient search state; the
    # Cockpit's other filters still apply and the handoff symbol is preserved.
    st.session_state.pop("market_data_symbol_search", None)
    st.session_state["market_data_symbol_candidate"] = symbol_candidate_label(symbol)
    st.session_state["market_data_ranking_handoff_symbol"] = symbol.strip().upper()
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
    st.session_state["market_data_navigation_source"] = {
        "source_page": "ranking",
        "source_label": "銘柄ランキング",
        "symbol": symbol.strip().upper(),
        "period_label": f"{start.isoformat()}〜{end.isoformat()}",
    }


def _select_news_symbol_for_cockpit(symbol: str) -> None:
    st.session_state["sidemenu_page"] = SIDEMENU_PAGE_COCKPIT
    st.session_state["market_data_mode"] = MARKET_DATA_MODE_COCKPIT
    st.session_state[MARKET_DATA_PROVIDER_WIDGET_KEY] = default_market_data_provider()
    st.session_state["market_data_symbol_candidate"] = symbol_candidate_label(symbol)
    st.session_state["market_data_navigation_source"] = {
        "source_page": "investment_radar",
        "source_label": "投資レーダー",
        "symbol": symbol.strip().upper(),
    }
    st.session_state.pop(MARKET_DATA_PREVIEW_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_STATUS_STATE_KEY, None)


def _fetch_news_radar_market_snapshot(
    candidates: Sequence[RadarCandidate],
    lookback_sessions: int,
) -> RadarMarketSnapshot:
    """Fetch a bounded live-price set only after the Radar's explicit action."""

    settings = get_settings()
    dataaccess = settings.dataaccess
    provider = dataaccess.provider
    selected = radar_market_candidates(candidates)
    symbols = [candidate.symbol for candidate in selected]
    provider_symbols_by_symbol = _provider_symbols_by_display_symbol(symbols, provider)
    now = datetime.now(UTC)
    bars: list[Bar] = []
    try:
        adapter = create_market_data_provider_adapter(dataaccess)
        bars = asyncio.run(
            adapter.fetch_ohlcv(
                _unique_provider_symbols(provider_symbols_by_symbol.values()),
                start=now - timedelta(days=90),
                end=now + timedelta(days=1),
                interval="1d",
            )
        )
        bars = _bars_with_display_symbols(
            bars,
            provider_symbols_by_symbol=provider_symbols_by_symbol,
        )
    except (AppError, OSError, RuntimeError, ValueError) as exc:
        # The snapshot explicitly records every requested symbol as unavailable;
        # the UI must not turn a provider failure into neutral or invented prices.
        LOGGER.warning("Investment Radar market price fetch failed: %s", type(exc).__name__)
        bars = []
    return build_radar_market_snapshot(
        selected,
        bars,
        provider=provider,
        lookback_sessions=lookback_sessions,
        generated_at=now,
        symbol_metadata_by_symbol=_symbol_universe_rows_by_symbol(),
    )


def _select_favorite_symbol_for_cockpit(symbol: str, action: str = "cockpit") -> None:
    _select_news_symbol_for_cockpit(symbol)
    st.session_state["market_data_favorite_next_action"] = action
    favorite = next(
        (item for item in load_favorites() if item.symbol == normalize_favorite_symbol(symbol)),
        None,
    )
    if favorite is not None:
        st.session_state["watchlist_context"] = {
            "symbol": favorite.symbol,
            "watch_reason": favorite.watch_reason,
            "decision_status": favorite.decision_status,
            "decision_note": favorite.decision_note,
            "next_check_label": favorite.next_check_label,
        }
    if action == "research":
        st.session_state["smai_next_action_hint"] = "research"
    elif action == "report":
        st.session_state["smai_next_action_hint"] = "decision_report"


def _render_my_watchlist_page() -> None:
    render_page_title(
        "Myウォッチリスト",
        "気になる銘柄をまとめて追跡します。",
        "watchlist",
    )
    if st.session_state.get("smai_current_user_id") == "default":
        st.caption(
            "SMAIデフォルトの登録はこのセッション限りです。保存する場合はカスタムユーザーを作成してください。"
        )
    group_view_mode, groups_state = render_watchlist_group_toolbar()
    favorites = load_favorites()
    prune_snapshots_for_removed_favorites({favorite.symbol for favorite in favorites})
    if not favorites:
        st.info(
            "まだお気に入り銘柄はありません。ランキング、銘柄コックピット、投資レーダーで「☆ お気に入り」を押すと、ここに表示されます。"
        )
        col_ranking, col_news = st.columns(2)
        with col_ranking:
            if st.button("銘柄ランキングで探す", use_container_width=True):
                st.session_state[SIDEMENU_STATE_KEY] = SIDEMENU_PAGE_RANKING
                st.rerun()
        with col_news:
            if st.button("投資レーダーを見る", use_container_width=True):
                st.session_state[SIDEMENU_STATE_KEY] = SIDEMENU_PAGE_NEWS
                st.rerun()
        return

    universe_by_symbol = _watchlist_computed_rows()
    snapshots = load_watchlist_snapshots()
    enriched = [
        _favorite_display_payload(
            favorite,
            universe_by_symbol,
            snapshot=snapshots.get(favorite.symbol),
        )
        for favorite in favorites
    ]
    if _run_watchlist_auto_snapshot_once(
        enriched,
        favorites=favorites,
        computed_rows=universe_by_symbol,
        snapshots=snapshots,
    ):
        st.rerun()
    enriched_by_symbol = {item["symbol"]: item for item in enriched}
    radar_items = build_favorite_radar_items(favorites, enriched_by_symbol)
    radar_by_symbol = {item.favorite.symbol: item for item in radar_items}
    for item in enriched:
        radar_item = radar_by_symbol.get(item["symbol"])
        if radar_item is None:
            continue
        item["radar_priority"] = str(radar_item.priority)
        item["radar_categories"] = " / ".join(radar_item.categories)
        item["radar_reasons"] = " / ".join(radar_item.reasons)
        item["radar_next_action"] = radar_item.next_action
    _request_watchlist_background_refresh_once(enriched)
    _header_spacer, update_col = st.columns([4.0, 1.35])
    with update_col:
        st.markdown(
            '<div class="smai-watchlist-header-refresh-anchor"></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "↻ ウォッチリストを更新",
            key="watchlist_header_refresh",
            use_container_width=True,
        ):
            checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
            targets = _watchlist_all_refresh_targets(enriched)
            refresh_result = asyncio.run(
                _refresh_watchlist_snapshots(
                    targets,
                    favorites=favorites,
                    computed_rows=universe_by_symbol,
                    previous_snapshots=snapshots,
                    include_scores=True,
                )
            )
            success_symbols = refresh_result["success_symbols"]
            failed_symbols = refresh_result["failed_symbols"]
            previous_data_symbols = refresh_result["previous_data_symbols"]
            skipped_symbols: list[str] = []
            _update_watchlist_refresh_metadata_from_result(
                refresh_result,
                checked_at=checked_at,
                favorites=favorites,
            )
            st.session_state["watchlist_refresh_summary"] = {
                "updated_at": checked_at,
                "success_count": len(success_symbols),
                "failed_count": len(failed_symbols),
                "skipped_count": len(skipped_symbols),
                "next_candidates_count": max(
                    0,
                    len(enriched) - len(success_symbols) - len(failed_symbols),
                ),
                "success_symbols": success_symbols,
                "failed_symbols": failed_symbols,
                "skipped_symbols": skipped_symbols[:10],
                "previous_data_count": len(previous_data_symbols),
                "previous_data_symbols": previous_data_symbols,
            }
            st.success(
                "ウォッチリスト更新結果: "
                f"成功 {len(success_symbols)}件 / 失敗 {len(failed_symbols)}件"
            )
            st.rerun()

    _render_watchlist_auto_snapshot_status()
    _render_watchlist_background_refresh_status()
    _render_watchlist_refresh_summary()

    filtered_enriched = _favorite_filter_and_sort_rows(enriched)
    if group_view_mode == "グループ別":
        render_grouped_watchlist(
            filtered_enriched,
            groups_state,
            render_card=_render_favorite_card,
        )
    else:
        display_mode = _render_segmented_or_radio(
            "表示形式",
            ["カード表示", "テーブル表示"],
            default="カード表示",
            key="market_data_watchlist_display_mode",
        )
        if display_mode == "テーブル表示":
            _render_favorite_table(filtered_enriched)
        else:
            for row_start in range(0, len(filtered_enriched), 3):
                cols = st.columns(3)
                for column, payload in zip(cols, filtered_enriched[row_start : row_start + 3]):
                    with column:
                        _render_favorite_card(payload)


def _render_my_radar_summary(radar_items: Sequence[Any]) -> None:
    summary_items = (
        ("今日見る", "今日見る候補"),
        ("要確認", "注意候補"),
        ("更新推奨", "更新候補"),
        ("メモ未入力", "メモ未入力候補"),
        ("下落注意", "下落注意"),
    )
    counts = []
    for label, category in summary_items:
        if category == "下落注意":
            count = sum(1 for item in radar_items if "下振れ警戒が高め" in item.reasons)
        else:
            count = sum(1 for item in radar_items if category in item.categories)
        counts.append((label, count))
    st.markdown(_favorite_radar_summary_html(counts), unsafe_allow_html=True)


def _favorite_radar_summary_html(summary_items: Sequence[tuple[str, int]]) -> str:
    items = "".join(
        '<div class="smai-watchlist-radar-item">'
        f"<span>{html.escape(label)}</span>"
        f"<strong>{count}</strong>"
        "</div>"
        for label, count in summary_items
    )
    return (
        '<section class="smai-watchlist-radar">'
        '<div class="smai-watchlist-radar-heading">My Radar</div>'
        f'<div class="smai-watchlist-radar-grid">{items}</div>'
        "</section>"
    )


def _render_segmented_or_radio(
    label: str,
    options: list[str],
    *,
    key: str,
    default: str | None = None,
    horizontal: bool = True,
    format_func: Callable[[str], str] | None = None,
) -> str:
    if not options:
        return ""

    selected_default = default if default in options else options[0]
    if key in st.session_state and st.session_state.get(key) not in options:
        st.session_state[key] = selected_default
    segmented_control = getattr(st, "segmented_control", None)
    if callable(segmented_control):
        if format_func is None:
            selected = segmented_control(
                label,
                options,
                default=selected_default,
                key=key,
            )
        else:
            selected = segmented_control(
                label,
                options,
                default=selected_default,
                key=key,
                format_func=format_func,
            )
    else:
        radio_kwargs: dict[str, Any] = {
            "index": options.index(selected_default),
            "horizontal": horizontal,
            "key": key,
        }
        if format_func is not None:
            radio_kwargs["format_func"] = format_func
        selected = st.radio(label, options, **radio_kwargs)
    return selected if selected in options else selected_default


def _favorite_filter_and_sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    filter_options = [
        "すべて",
        "更新推奨",
        "上昇傾向",
        "下落注意",
        "未取得",
        "メモ未入力",
    ]
    sort_options = [
        "追加日が新しい順",
        "AI総合が高い順",
        "上昇気配が高い順",
        "下振れ警戒が高い順",
        "更新が古い順",
        "確認優先度順",
        "銘柄コード順",
    ]
    st.markdown("##### ウォッチ銘柄を絞り込む")
    filter_col, sort_col = st.columns([2, 1])
    with filter_col:
        st.markdown(
            '<div class="smai-watchlist-filter-chip-anchor"></div>',
            unsafe_allow_html=True,
        )
        filter_counts = {option: _favorite_filter_count(rows, option) for option in filter_options}
        selected_filter = _render_segmented_or_radio(
            "表示フィルター",
            filter_options,
            default=filter_options[0],
            key="market_data_watchlist_filter",
            format_func=lambda option: f"{option} {filter_counts[option]}",
        )
    with sort_col:
        selected_sort = st.selectbox(
            "並び順",
            sort_options,
            key="market_data_watchlist_sort",
        )
    filtered = [row for row in rows if _favorite_row_matches_filter(row, selected_filter)]
    sorted_rows = sorted(filtered, key=lambda row: _favorite_sort_key(row, selected_sort))
    st.caption(f"表示中: {len(sorted_rows)}件 / 全体 {len(rows)}件")
    return sorted_rows


def _favorite_filter_count(rows: Sequence[Mapping[str, str]], filter_name: str) -> int:
    return sum(1 for row in rows if _favorite_row_matches_filter(row, filter_name))


def _favorite_row_matches_filter(row: Mapping[str, str], selected_filter: str | None) -> bool:
    if not selected_filter or selected_filter == "すべて":
        return True
    if selected_filter == "要確認":
        return row.get("refresh_status") == "needs_attention"
    if selected_filter == "更新推奨":
        return (
            row.get("snapshot_status") in {"missing", "failed"}
            or row.get("refresh_status")
            in {
                "needs_attention",
                "never_checked",
                "stale",
                "failed",
            }
            or _watchlist_snapshot_row_is_stale(row)
        )
    if selected_filter == "上昇傾向":
        return row.get("status") in {"上昇候補", "上昇傾向", "短期上昇"}
    if selected_filter == "下落注意":
        return row.get("status") in {"下振れ注意", "下落注意", "急落警戒"}
    if selected_filter == "未確認":
        return row.get("refresh_status") == "never_checked"
    if selected_filter == "未取得":
        return _favorite_metrics_missing(row)
    if selected_filter == "古い":
        return row.get("refresh_status") == "stale"
    if selected_filter == "前回失敗":
        return row.get("refresh_status") == "failed"
    if selected_filter == "メモ未入力":
        return "メモ未入力候補" in row.get("radar_categories", "")
    if selected_filter == "AI調査候補":
        return "調査候補" in row.get("radar_categories", "")
    if selected_filter == "レポート候補":
        return bool(row.get("decision_note") and row.get("watch_reason"))
    return True


def _favorite_sort_key(row: Mapping[str, str], selected_sort: str) -> tuple[Any, ...]:
    if selected_sort == "更新が古い順":
        return (_date_sort_value(row.get("last_checked_at")), row.get("symbol", ""))
    if selected_sort == "追加日が新しい順":
        return (-_date_sort_value(row.get("added_at")), row.get("symbol", ""))
    if selected_sort == "AI総合が高い順":
        return (-_decimal_sort_value(row.get("ai_score")), row.get("symbol", ""))
    if selected_sort == "上昇気配が高い順":
        return (-_decimal_sort_value(row.get("upside")), row.get("symbol", ""))
    if selected_sort == "下振れ警戒が高い順":
        return (-_decimal_sort_value(row.get("downside")), row.get("symbol", ""))
    if selected_sort == "銘柄コード順":
        return (row.get("symbol", ""),)
    return (-int(row.get("radar_priority") or "0"), row.get("symbol", ""))


def _render_favorite_next_action_hint() -> None:
    action = st.session_state.pop("market_data_favorite_next_action", "")
    if action == "research":
        st.info(
            "MyウォッチリストからAI調査を確認しに来ました。"
            "下の「03 AI調査・材料分析」にある「AI調査を開始・更新」から、最新情報を確認できます。"
        )
    elif action == "report":
        st.info(
            "Myウォッチリストから確認レポートを確認しに来ました。"
            "下の「05 確認レポート」で、この銘柄の確認メモを作成・更新できます。"
        )


def _watchlist_all_refresh_targets(rows: Sequence[Mapping[str, object]]) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for row in rows:
        symbol = normalize_favorite_symbol(str(row.get("symbol") or ""))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        targets.append(symbol)
    return targets


def _watchlist_refresh_target_fingerprint(targets: Sequence[str]) -> str:
    return "|".join(normalize_favorite_symbol(symbol) for symbol in targets)


def _update_watchlist_refresh_metadata_from_result(
    refresh_result: Mapping[str, Sequence[str]],
    *,
    checked_at: str,
    favorites: Sequence[FavoriteStock],
) -> None:
    favorite_symbols = {favorite.symbol for favorite in favorites}
    if not favorite_symbols:
        return
    for symbol in refresh_result.get("success_symbols", []):
        normalized = normalize_favorite_symbol(str(symbol))
        if normalized not in favorite_symbols:
            continue
        update_favorite_refresh_metadata(
            normalized,
            refresh_status="fresh",
            refresh_error="",
            last_checked_at=checked_at,
            last_price_checked_at=checked_at,
        )
    for symbol in refresh_result.get("failed_symbols", []):
        normalized = normalize_favorite_symbol(str(symbol))
        if normalized not in favorite_symbols:
            continue
        update_favorite_refresh_metadata(
            normalized,
            refresh_status="failed",
            refresh_error="snapshot update failed",
            last_checked_at=checked_at,
        )


def _render_watchlist_refresh_summary() -> None:
    summary = st.session_state.get("watchlist_refresh_summary")
    if not isinstance(summary, Mapping):
        return
    result_parts = [
        f"成功 {summary.get('success_count', 0)}件",
        f"失敗 {summary.get('failed_count', 0)}件",
    ]
    skipped_count = int(summary.get("skipped_count", 0) or 0)
    next_candidates_count = int(summary.get("next_candidates_count", 0) or 0)
    if skipped_count:
        result_parts.append(f"見送り {skipped_count}件")
    if next_candidates_count:
        result_parts.append(f"次回候補 {next_candidates_count}件")
    st.info("ウォッチリスト更新結果: " + " / ".join(result_parts))
    success_symbols = summary.get("success_symbols") or []
    skipped_symbols = summary.get("skipped_symbols") or []
    if success_symbols:
        st.caption(f"更新済み: {', '.join(str(symbol) for symbol in success_symbols[:10])}")
    if skipped_symbols:
        st.caption(f"今回は見送り: {', '.join(str(symbol) for symbol in skipped_symbols[:10])}")
    previous_data_count = int(summary.get("previous_data_count", 0) or 0)
    if previous_data_count:
        st.caption(f"前回データを表示中: {previous_data_count}件")


def _run_watchlist_auto_snapshot_once(
    rows: Sequence[Mapping[str, str]],
    *,
    favorites: Sequence[FavoriteStock],
    computed_rows: Mapping[str, Mapping[str, Any]],
    snapshots: Mapping[str, WatchlistSnapshot],
) -> bool:
    targets = _watchlist_all_refresh_targets(rows)
    target_fingerprint = _watchlist_refresh_target_fingerprint(targets)
    existing = st.session_state.get(WATCHLIST_AUTO_SNAPSHOT_STATE_KEY)
    if isinstance(existing, Mapping) and existing.get("target_fingerprint") == target_fingerprint:
        return False
    if _background_workers_disabled():
        st.session_state[WATCHLIST_AUTO_SNAPSHOT_STATE_KEY] = {
            "status": "disabled",
            "requested": 0,
            "success": 0,
            "failed": 0,
            "target_fingerprint": target_fingerprint,
        }
        return False
    if not targets:
        st.session_state[WATCHLIST_AUTO_SNAPSHOT_STATE_KEY] = {
            "status": "no_targets",
            "requested": 0,
            "success": 0,
            "failed": 0,
            "target_fingerprint": target_fingerprint,
        }
        return False
    st.session_state["watchlist_auto_snapshot_started"] = True
    loading_slot = st.empty()
    with loading_slot.container():
        render_mascot_loading(
            "guide",
            title="ウォッチ銘柄を全件確認中",
            message=f"Myウォッチリスト {len(targets)}件の価格・スコアを更新しています。",
            tone="info",
        )
    result = asyncio.run(
        _refresh_watchlist_snapshots(
            targets,
            favorites=favorites,
            computed_rows=computed_rows,
            previous_snapshots=snapshots,
            include_scores=True,
        )
    )
    if hasattr(loading_slot, "empty"):
        loading_slot.empty()
    completed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    _update_watchlist_refresh_metadata_from_result(
        result,
        checked_at=completed_at,
        favorites=favorites,
    )
    st.session_state["watchlist_auto_snapshot_completed_at"] = completed_at
    st.session_state[WATCHLIST_AUTO_SNAPSHOT_STATE_KEY] = {
        "status": "completed",
        "requested": len(targets),
        "success": len(result["success_symbols"]),
        "failed": len(result["failed_symbols"]),
        "previous_data": len(result["previous_data_symbols"]),
        "completed_at": completed_at,
        "target_fingerprint": target_fingerprint,
    }
    return True


def _render_watchlist_auto_snapshot_status() -> None:
    summary = st.session_state.get(WATCHLIST_AUTO_SNAPSHOT_STATE_KEY)
    if not isinstance(summary, Mapping) or summary.get("status") != "completed":
        return
    st.caption(
        "ウォッチ銘柄の確認完了: "
        f"{summary.get('success', 0)}件更新 / "
        f"{summary.get('previous_data', 0)}件は前回データを表示中"
    )


def _watchlist_computed_rows() -> dict[str, dict[str, str]]:
    rows = _symbol_universe_rows_by_symbol(include_runtime_cache=True)
    ranking_rows = st.session_state.get(MARKET_DATA_RANKING_STATE_KEY, [])
    if isinstance(ranking_rows, list):
        for raw_row in ranking_rows:
            if not isinstance(raw_row, Mapping):
                continue
            symbol = str(raw_row.get("symbol") or raw_row.get("銘柄") or "").strip().upper()
            if not symbol:
                continue
            current = rows.setdefault(symbol, {"symbol": symbol})
            current.update(
                {
                    "price": str(
                        raw_row.get("price")
                        or raw_row.get("last_price")
                        or raw_row.get("現在株価")
                        or ""
                    ),
                    "ai_score": str(
                        raw_row.get("ai_score")
                        or raw_row.get("investment_score")
                        or raw_row.get("total_score")
                        or raw_row.get("総合スコア")
                        or ""
                    ),
                    "upside_score": str(
                        raw_row.get("upside_score")
                        or raw_row.get("upside_signal_score")
                        or raw_row.get("上昇気配")
                        or ""
                    ),
                    "reversal_expectation_score": str(
                        raw_row.get("reversal_expectation_score") or raw_row.get("上向き兆候") or ""
                    ),
                    "reversal_expectation_label": str(
                        raw_row.get("reversal_expectation_label")
                        or raw_row.get("上向き兆候ラベル")
                        or ""
                    ),
                    "reversal_expectation_reason": str(
                        raw_row.get("reversal_expectation_reason")
                        or raw_row.get("上向き兆候理由")
                        or ""
                    ),
                    "reversal_chart_shape_label": str(
                        raw_row.get("reversal_chart_shape_label")
                        or raw_row.get("チャート形状")
                        or ""
                    ),
                    "downside_risk_score": str(
                        raw_row.get("downside_risk_score")
                        or raw_row.get("downside_signal_score")
                        or raw_row.get("下降警戒")
                        or raw_row.get("下振れ警戒")
                        or ""
                    ),
                    "forecast_return_pct": str(
                        raw_row.get("forecast_return_pct") or raw_row.get("予測変化率") or ""
                    ),
                    "up_model_count": str(raw_row.get("up_model_count") or ""),
                    "down_model_count": str(raw_row.get("down_model_count") or ""),
                    "flat_model_count": str(raw_row.get("flat_model_count") or ""),
                    "risk_signal_score": str(
                        raw_row.get("risk_signal_score")
                        or raw_row.get("risk_score")
                        or raw_row.get("Risk")
                        or ""
                    ),
                    "data_quality_score": str(
                        raw_row.get("data_quality_score") or raw_row.get("データ品質") or ""
                    ),
                    "drawdown_20d": str(
                        raw_row.get("drawdown_20d") or raw_row.get("20日高値乖離") or ""
                    ),
                    "momentum_5d": str(
                        raw_row.get("momentum_5d")
                        or raw_row.get("return_5d")
                        or raw_row.get("5日騰落率")
                        or ""
                    ),
                }
            )
    preview = st.session_state.get(MARKET_DATA_PREVIEW_STATE_KEY)
    if isinstance(preview, MarketDataPreview):
        for feature_row in preview.feature_rows:
            symbol = str(feature_row.get("symbol") or "").strip().upper()
            if symbol:
                rows.setdefault(symbol, {"symbol": symbol}).update(feature_row)
        for score_row in preview.investment_score_rows:
            symbol = str(score_row.get("symbol") or "").strip().upper()
            if symbol:
                rows.setdefault(symbol, {"symbol": symbol}).update(score_row)
        preview_bars_by_symbol = _ranking_bars_by_symbol(
            sorted({bar.symbol.raw for bar in preview.bars}),
            preview.bars,
        )
        for symbol, bars in preview_bars_by_symbol.items():
            if not bars:
                continue
            local_snapshot = build_watchlist_snapshot_for_symbol(
                symbol,
                row=rows.get(symbol, {}),
                bars=bars,
                source="cockpit_session",
            )
            rows.setdefault(symbol, {"symbol": symbol}).update(
                {
                    "price": _watchlist_optional_number_text(local_snapshot.price),
                    "price_change_1d": _watchlist_optional_number_text(
                        local_snapshot.price_change_1d
                    ),
                    "price_change_5d": _watchlist_optional_number_text(
                        local_snapshot.price_change_5d
                    ),
                    "price_change_1m": _watchlist_optional_number_text(
                        local_snapshot.price_change_1m
                    ),
                    "reversal_expectation_score": _watchlist_optional_number_text(
                        local_snapshot.reversal_expectation_score
                    ),
                    "reversal_expectation_label": local_snapshot.reversal_expectation_label or "",
                    "reversal_expectation_reason": local_snapshot.reversal_expectation_reason or "",
                    "reversal_chart_shape_label": local_snapshot.reversal_chart_shape_label or "",
                    "reversal_trap_warning": local_snapshot.reversal_trap_warning or "",
                    "dividend_trap_warning": local_snapshot.dividend_trap_warning or "",
                    "dividend_safety_score": _watchlist_optional_number_text(
                        local_snapshot.dividend_safety_score
                    ),
                    "downside_risk_score": _watchlist_optional_number_text(
                        local_snapshot.downside_risk_score
                    ),
                }
            )
    return rows


def _watchlist_optional_number_text(value: float | None) -> str:
    return "" if value is None else str(value)


def _watchlist_snapshot_refresh_targets(
    rows: Sequence[Mapping[str, str]],
    snapshots: Mapping[str, WatchlistSnapshot],
    *,
    max_items: int,
    now: datetime | None = None,
) -> list[str]:
    current_time = now or datetime.now(UTC)

    def priority(row: Mapping[str, str]) -> tuple[int, float, str]:
        symbol = str(row.get("symbol") or "")
        snapshot = snapshots.get(symbol)
        if snapshot is None:
            rank = 0
        elif snapshot.status == "failed":
            rank = 1
        elif _watchlist_snapshot_is_stale(snapshot, now=current_time):
            rank = 2
        elif row.get("refresh_status") == "failed":
            rank = 3
        elif row.get("refresh_status") in {"stale", "never_checked"}:
            rank = 4
        else:
            rank = 5
        return rank, _date_sort_value(snapshot.last_snapshot_at if snapshot else None), symbol

    ordered = sorted(rows, key=priority)
    return [str(row.get("symbol") or "") for row in ordered[: max(0, max_items)]]


def _watchlist_snapshot_is_stale(
    snapshot: WatchlistSnapshot,
    *,
    now: datetime | None = None,
    ttl_hours: int = 6,
) -> bool:
    snapshot_at = _parse_watchlist_datetime(snapshot.last_snapshot_at)
    if snapshot_at is None:
        return True
    current_time = now or datetime.now(UTC)
    return snapshot_at.astimezone(UTC) + timedelta(hours=ttl_hours) < current_time.astimezone(UTC)


async def _refresh_watchlist_snapshots(
    symbols: Sequence[str],
    *,
    favorites: Sequence[FavoriteStock],
    computed_rows: Mapping[str, Mapping[str, Any]],
    previous_snapshots: Mapping[str, WatchlistSnapshot],
    include_scores: bool = False,
) -> dict[str, list[str]]:
    settings = get_settings()
    dataaccess = settings.dataaccess
    provider = dataaccess.provider
    allow_fetch = provider not in LIVE_MARKET_DATA_PROVIDERS or dataaccess.allow_external_providers
    adapter = create_market_data_provider_adapter(dataaccess) if allow_fetch else None
    favorite_by_symbol = {favorite.symbol: favorite for favorite in favorites}
    updated = dict(previous_snapshots)
    success_symbols: list[str] = []
    failed_symbols: list[str] = []
    previous_data_symbols: list[str] = []
    fx_rates_by_currency: dict[str, Decimal] = {}
    end = datetime.now(UTC)
    start = end - timedelta(days=45)
    for symbol in symbols:
        normalized = normalize_favorite_symbol(symbol)
        previous = previous_snapshots.get(normalized)
        row = computed_rows.get(normalized, {})
        bars: list[Bar] = []
        try:
            if adapter is not None:
                if include_scores:
                    preview = await build_market_data_preview(
                        symbol=normalized,
                        start=start.date(),
                        end=end.date(),
                        provider_override=provider,
                        forecast_horizon_days=default_forecast_horizon_days(
                            start.date(),
                            end.date(),
                        ),
                    )
                    bars = preview.bars
                    score_rows = getattr(preview, "investment_score_rows", [])
                    feature_rows = getattr(preview, "feature_rows", [])
                    score_row: Mapping[str, object] = next(
                        (
                            item
                            for item in score_rows
                            if str(item.get("symbol") or "").upper() == normalized
                        ),
                        {},
                    )
                    feature_row: Mapping[str, object] = next(
                        (
                            item
                            for item in feature_rows
                            if str(item.get("symbol") or "").upper() == normalized
                        ),
                        {},
                    )
                    row = {**row, **feature_row, **score_row}
                else:
                    provider_symbol = symbol_provider_symbol(normalized, provider)
                    provider_bars = await adapter.fetch_ohlcv(
                        [provider_symbol],
                        start=start,
                        end=end,
                    )
                    bars = [
                        _bar_with_display_symbol(bar, display_symbol=normalized)
                        for bar in provider_bars
                    ]
            favorite = favorite_by_symbol.get(normalized)
            source_currency = (
                str(bars[-1].symbol.currency).strip().upper()
                if bars
                else str(row.get("currency") or (favorite.currency if favorite else ""))
                .strip()
                .upper()
            )
            if (
                bars
                and adapter is not None
                and source_currency not in {"", "JPY"}
                and source_currency not in fx_rates_by_currency
            ):
                fx_rates_by_currency.update(
                    await _ranking_jpy_fx_rates(adapter, [source_currency], at=end)
                )
            if bars:
                fx_rate = fx_rates_by_currency.get(source_currency)
                current_price_jpy = _ranking_current_price_jpy(
                    bars[-1].close,
                    source_currency=source_currency,
                    jpy_fx_rates=fx_rates_by_currency,
                )
                row = {
                    **row,
                    "currency": source_currency,
                    "current_price_jpy": (
                        str(current_price_jpy) if current_price_jpy is not None else ""
                    ),
                    "fx_rate_jpy": str(fx_rate) if fx_rate is not None else "",
                }
            snapshot = build_watchlist_snapshot_for_symbol(
                normalized,
                favorite=favorite_by_symbol.get(normalized),
                row=row,
                bars=bars,
                previous=previous,
                source=provider if bars else "local_cache",
            )
            if snapshot.status == "missing" and previous is not None:
                snapshot = mark_watchlist_snapshot_failed(
                    normalized,
                    previous=previous,
                    error="更新データを取得できませんでした。",
                )
                failed_symbols.append(normalized)
                previous_data_symbols.append(normalized)
            elif snapshot.status == "missing":
                failed_symbols.append(normalized)
            else:
                success_symbols.append(normalized)
            updated[normalized] = snapshot
        except Exception as exc:  # noqa: BLE001
            snapshot = mark_watchlist_snapshot_failed(
                normalized,
                previous=previous,
                error=type(exc).__name__,
            )
            updated[normalized] = snapshot
            failed_symbols.append(normalized)
            if previous is not None:
                previous_data_symbols.append(normalized)
    save_watchlist_snapshots(updated)
    return {
        "success_symbols": success_symbols,
        "failed_symbols": failed_symbols,
        "previous_data_symbols": previous_data_symbols,
    }


def _watchlist_background_refresh_candidates(
    rows: Sequence[Mapping[str, str]],
    *,
    now: datetime | None = None,
    max_items: int = WATCHLIST_BACKGROUND_REFRESH_MAX_ITEMS,
    ttl_seconds: int = WATCHLIST_BACKGROUND_REFRESH_TTL_SECONDS,
) -> list[str]:
    current_time = now or datetime.now(UTC)

    def priority(row: Mapping[str, str]) -> tuple[int, str]:
        if _favorite_metrics_missing(row):
            rank = 0
        elif row.get("snapshot_status") == "failed":
            rank = 1
        else:
            rank = {
                "failed": 2,
                "stale": 3,
                "never_checked": 4,
                "needs_attention": 5,
            }.get(str(row.get("refresh_status") or ""), 9)
        return rank, str(row.get("symbol") or "")

    candidates: list[Mapping[str, str]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        last_checked = _parse_watchlist_datetime(str(row.get("last_checked_at") or ""))
        if (
            last_checked is not None
            and (current_time - last_checked.astimezone(UTC)).total_seconds() < ttl_seconds
        ):
            continue
        if (
            not _favorite_metrics_missing(row)
            and row.get("snapshot_status") not in {"missing", "failed"}
            and not _watchlist_snapshot_row_is_stale(
                row,
                now=current_time,
                ttl_seconds=ttl_seconds,
            )
            and row.get("refresh_status")
            not in {
                "failed",
                "stale",
                "never_checked",
                "needs_attention",
            }
        ):
            continue
        candidates.append(row)
    return [str(row["symbol"]).strip().upper() for row in sorted(candidates, key=priority)][
        : max(0, max_items)
    ]


def _watchlist_snapshot_row_is_stale(
    row: Mapping[str, object],
    *,
    now: datetime | None = None,
    ttl_seconds: int = WATCHLIST_BACKGROUND_REFRESH_TTL_SECONDS,
) -> bool:
    snapshot_at = _parse_watchlist_datetime(str(row.get("last_snapshot_at") or ""))
    if snapshot_at is None:
        return True
    current_time = now or datetime.now(UTC)
    return (
        current_time.astimezone(UTC) - snapshot_at.astimezone(UTC)
    ).total_seconds() >= ttl_seconds


def _request_watchlist_background_refresh_once(rows: Sequence[Mapping[str, str]]) -> None:
    if WATCHLIST_BACKGROUND_REFRESH_STATE_KEY in st.session_state:
        return
    if _background_workers_disabled():
        st.session_state[WATCHLIST_BACKGROUND_REFRESH_STATE_KEY] = {
            "status": "disabled",
            "symbols": [],
        }
        return
    symbols = _watchlist_background_refresh_candidates(rows)
    if not symbols:
        st.session_state[WATCHLIST_BACKGROUND_REFRESH_STATE_KEY] = {
            "status": "up_to_date",
            "symbols": [],
        }
        return
    provider_config = get_settings().dataaccess
    try:
        requested = request_symbol_background_refresh(
            symbols,
            source="watchlist",
            max_items=WATCHLIST_BACKGROUND_REFRESH_MAX_ITEMS,
        )
    except Exception as exc:  # noqa: BLE001
        st.session_state[WATCHLIST_BACKGROUND_REFRESH_STATE_KEY] = {
            "status": "failed",
            "symbols": symbols,
            "error_type": type(exc).__name__,
        }
        return
    st.session_state[WATCHLIST_BACKGROUND_REFRESH_STATE_KEY] = {
        "status": ("queued" if provider_config.allow_external_providers else "local_only"),
        "symbols": requested,
    }


def _render_watchlist_background_refresh_status() -> None:
    state = st.session_state.get(WATCHLIST_BACKGROUND_REFRESH_STATE_KEY)
    if not isinstance(state, Mapping):
        return
    status = str(state.get("status") or "")
    count = len(state.get("symbols") or [])
    message = {
        "disabled": "バックグラウンド確認: 無効",
        "up_to_date": "バックグラウンド確認: 対象なし",
        "queued": f"バックグラウンド確認: 待機中（最大{count}件）",
        "local_only": "バックグラウンド確認: provider無効のためローカル情報のみ確認",
        "failed": "バックグラウンド確認: 前回データを表示中",
    }.get(status)
    if message:
        st.caption(message)


def _favorite_display_payload(
    favorite: FavoriteStock,
    universe_by_symbol: Mapping[str, Mapping[str, str]],
    *,
    snapshot: WatchlistSnapshot | None = None,
) -> dict[str, str]:
    symbol = favorite.symbol
    row = dict(universe_by_symbol.get(symbol, {}))
    if snapshot is not None:
        snapshot_values: dict[str, str | float | None] = {
            "name": snapshot.name,
            "market": snapshot.market,
            "asset_type": snapshot.asset_type,
            "currency": snapshot.currency,
            "price": snapshot.price_display or snapshot.price,
            "price_jpy": snapshot.price_jpy,
            "fx_rate_jpy": snapshot.fx_rate_jpy,
            "ai_score": snapshot.ai_score,
            "upside_score": snapshot.upside_score,
            "reversal_expectation_score": snapshot.reversal_expectation_score,
            "reversal_expectation_label": snapshot.reversal_expectation_label,
            "reversal_expectation_reason": snapshot.reversal_expectation_reason,
            "reversal_chart_shape_label": snapshot.reversal_chart_shape_label,
            "reversal_trap_warning": snapshot.reversal_trap_warning,
            "dividend_trap_warning": snapshot.dividend_trap_warning,
            "dividend_safety_score": snapshot.dividend_safety_score,
            "dividend_yield_spike_flag": snapshot.dividend_yield_spike_flag,
            "dividend_sustainability_label": snapshot.dividend_sustainability_label,
            "downside_risk_score": snapshot.downside_risk_score,
            "price_change_1d": snapshot.price_change_1d,
            "price_change_5d": snapshot.price_change_5d,
            "price_change_1m": snapshot.price_change_1m,
        }
        row.update({key: str(value) for key, value in snapshot_values.items() if value is not None})
    name = str(row.get("name") or favorite.name or symbol)
    market = str(row.get("market") or favorite.market or "未取得")
    asset_type = str(row.get("asset_type") or favorite.asset_type or "未取得")
    currency = str(row.get("currency") or favorite.currency or "未取得")
    original_price = str(row.get("price") or row.get("last_price") or row.get("close") or "")
    price = _favorite_price_display(
        original_price,
        currency=currency,
        price_jpy=_favorite_first_value(row, "price_jpy", "current_price_jpy"),
    )
    ai_score = str(row.get("ai_score") or row.get("investment_score") or "")
    upside = str(row.get("upside_score") or row.get("forecast_agreement") or "")
    reversal = str(row.get("reversal_expectation_score") or "")
    downside = str(row.get("downside_risk_score") or "")
    price_change_1d = _favorite_change_value(row, "price_change_1d", "return_1d")
    price_change_5d = _favorite_change_value(row, "price_change_5d", "return_5d")
    price_change_1m = _favorite_change_value(
        row,
        "price_change_1m",
        "return_1m",
        "return_20d",
    )
    movement_status = (
        snapshot.trend_label
        if snapshot is not None and snapshot.trend_label
        else _favorite_movement_status(
            price_change_1d,
            price_change_5d,
            price_change_1m,
        )
    )
    status = _favorite_status_label(
        price=price,
        ai_score=ai_score,
        upside=upside,
        reversal=reversal,
        downside=downside,
        movement_status=movement_status,
    )
    refresh_state = evaluate_favorite_refresh_status(favorite)
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "asset_type": asset_type,
        "currency": currency,
        "added_at": favorite.added_at or "未取得",
        "last_checked_at": (
            snapshot.last_snapshot_at
            if snapshot is not None and snapshot.last_snapshot_at
            else favorite.last_checked_at or "未確認"
        ),
        "refresh_status": refresh_state.status,
        "refresh_label": refresh_state.label,
        "refresh_reason": refresh_state.reason,
        "refresh_priority": str(refresh_state.priority),
        "refresh_next_action": refresh_state.next_action,
        "refresh_error": favorite.refresh_error or "",
        "reversal": reversal or "未計算",
        "reversal_label": upward_signal_display_label(row.get("reversal_expectation_label")),
        "reversal_reason": str(row.get("reversal_expectation_reason") or ""),
        "source_screen": favorite.source_screen or "unknown",
        "price": price or "未取得",
        "ai_score": ai_score or "未取得",
        "upside": upside or "未取得",
        "downside": downside or "未取得",
        "dividend_yield": _favorite_fundamental_value(
            row,
            "dividend_yield_pct",
            "dividend_yield",
            "dividendYield",
            "yield",
            suffix="%",
        ),
        "per": _favorite_fundamental_value(row, "per", "trailing_pe", "forward_pe"),
        "pbr": _favorite_fundamental_value(row, "pbr", "price_to_book"),
        "roe": _favorite_fundamental_value(
            row,
            "roe_pct",
            "roe",
            "return_on_equity",
            suffix="%",
        ),
        "market_cap": _format_favorite_market_cap(
            _favorite_first_value(row, "market_cap", "market_cap_jpy", "marketCapitalization"),
            currency=currency,
        ),
        "sector": _favorite_sector_value(row),
        "price_change_1d": price_change_1d or "",
        "price_change_5d": price_change_5d or "",
        "price_change_1m": price_change_1m or "",
        "movement_status": movement_status or "unknown",
        "snapshot_status": snapshot.status or "missing" if snapshot is not None else "missing",
        "snapshot_error": snapshot.error or "" if snapshot is not None else "",
        "last_snapshot_at": snapshot.last_snapshot_at or "" if snapshot is not None else "",
        "research_status": "未調査",
        "latest_news": "投資レーダーで確認" if favorite.last_news_checked_at else "未確認",
        "related_news": "あり" if favorite.last_news_checked_at else "未確認",
        "checkpoint": _favorite_checkpoint_label(status),
        "memo": favorite.memo or "メモなし",
        "tags": " / ".join(favorite.tags) if favorite.tags else "タグなし",
        "status": status,
        "status_label": _favorite_status_display_label(status),
        "watch_reason": favorite.watch_reason or "未入力",
        "decision_status": favorite.decision_status or "未設定",
        "decision_note": favorite.decision_note or "未入力",
        "next_check_at": favorite.next_check_at or "",
        "next_check_label": favorite.next_check_label or "未設定",
        "decision_updated_at": favorite.decision_updated_at or "",
        "decision_updated_label": _format_watchlist_date_label(
            favorite.decision_updated_at,
            fallback="未更新",
        ),
    }


def _favorite_status_label(
    *,
    price: str,
    ai_score: str,
    upside: str,
    downside: str,
    reversal: str = "",
    movement_status: str = "未取得",
) -> str:
    if movement_status in {"上昇傾向", "短期上昇", "下落注意", "急落警戒", "横ばい"}:
        return movement_status
    if not any([price, ai_score, upside, downside]):
        return "未取得"
    try:
        upside_value = Decimal(str(upside))
    except Exception:  # noqa: BLE001
        upside_value = Decimal("0")
    try:
        downside_value = Decimal(str(downside))
    except Exception:  # noqa: BLE001
        downside_value = Decimal("0")
    try:
        reversal_value = Decimal(str(reversal))
    except Exception:  # noqa: BLE001
        reversal_value = Decimal("0")
    if reversal_value >= Decimal("65") and downside_value < Decimal("65"):
        return "上向き兆候"
    if reversal_value >= Decimal("50") and downside_value >= Decimal("70"):
        return "落ちるナイフ注意"
    if reversal_value >= Decimal("50"):
        return "押し目観察"
    if reversal:
        return "反転材料弱め"
    if upside_value >= Decimal("70"):
        return "上昇候補"
    if downside_value >= Decimal("60"):
        return "下振れ注意"
    return "横ばい"


def _favorite_checkpoint_label(status: str) -> str:
    if status == "上向き兆候":
        return "上向き兆候が高めです。直近下落が連れ安か、個別悪材料かを確認します。"
    if status == "押し目観察":
        return "調整後の戻り候補です。予測と下落理由を継続確認します。"
    if status == "落ちるナイフ注意":
        return "反転材料はありますが下降警戒も高いため、悪材料と下振れ余地を確認します。"
    if status == "反転材料弱め":
        return "反転材料はまだ弱めです。価格と予測の変化を観察します。"
    if status in {"上昇候補", "上昇傾向"}:
        return "上昇気配は強めです。決算・ニュース変化を確認します。"
    if status == "短期上昇":
        return "短期の値動きは上向きです。継続性を確認します。"
    if status in {"下振れ注意", "下落注意"}:
        return "下振れ警戒が高めです。価格下落や材料悪化を確認します。"
    if status == "急落警戒":
        return "直近の下落が大きいため、価格変化と材料を確認します。"
    if status == "未取得":
        return "データ更新が必要です。"
    return "横ばいです。次の材料や価格変化を確認します。"


def _favorite_status_display_label(status: str) -> str:
    if status in {"上向き兆候", "押し目観察", "落ちるナイフ注意", "反転材料弱め"}:
        return status
    if status in {"上昇候補", "上昇傾向"}:
        return "上昇傾向"
    if status == "短期上昇":
        return "短期上昇"
    if status == "下振れ注意":
        return "下落注意"
    if status in {"下落注意", "急落警戒"}:
        return status
    if status == "未取得":
        return "判定保留"
    return "横ばい"


def _favorite_status_tone(status: str) -> str:
    if status == "上向き兆候":
        return "reversal"
    if status == "押し目観察":
        return "watch"
    if status == "落ちるナイフ注意":
        return "downside"
    if status == "反転材料弱め":
        return "neutral"
    if status in {"上昇候補", "上昇傾向"}:
        return "upside"
    if status == "短期上昇":
        return "short-upside"
    if status in {"下振れ注意", "下落注意"}:
        return "downside"
    if status == "急落警戒":
        return "sharp-downside"
    if status == "未取得":
        return "unknown"
    return "flat"


def _favorite_refresh_tone(refresh_status: str) -> str:
    return {
        "fresh": "fresh",
        "never_checked": "never-checked",
        "stale": "stale",
        "needs_attention": "needs-attention",
        "failed": "failed",
        "partial": "partial",
    }.get(refresh_status, "unknown")


def _favorite_display_value(value: object, *, fallback: str = "未取得") -> str:
    text = str(value or "").strip()
    if not text or text in {"-", "None", "null"}:
        return fallback
    return text


def _favorite_first_value(row: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        value = row.get(key)
        if str(value or "").strip() not in {"", "-", "None", "null", "nan", "NaN"}:
            return value
    return ""


def _favorite_fundamental_value(
    row: Mapping[str, object],
    *keys: str,
    suffix: str = "",
) -> str:
    value = _favorite_first_value(row, *keys)
    if value == "":
        return "—"
    text = str(value).replace("%", "").strip()
    try:
        number = Decimal(text)
    except Exception:  # noqa: BLE001
        return str(value)
    if not number.is_finite():
        return "—"
    formatted = f"{number:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}{suffix}"


def _favorite_price_display(price: object, *, currency: str, price_jpy: object = "") -> str:
    original = _favorite_price_number(price)
    if original is None:
        return "未取得"
    normalized_currency = currency.strip().upper()
    if normalized_currency in {"", "JPY"}:
        return f"{original:,.2f}".rstrip("0").rstrip(".") + "円"
    converted = _favorite_price_number(price_jpy)
    yen_display = f"{converted:,.0f}円" if converted is not None else "—円"
    original_display = f"{original:,.2f}".rstrip("0").rstrip(".")
    return f"{yen_display}（{original_display} {normalized_currency}）"


def _favorite_price_number(value: object) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[,\s]", "", text)
    normalized = re.sub(r"(?:円|[A-Za-z]{3})$", "", normalized)
    try:
        number = Decimal(normalized)
    except Exception:  # noqa: BLE001
        return None
    return number if number.is_finite() else None


def _format_favorite_market_cap(value: object, *, currency: str) -> str:
    text = str(value or "").replace(",", "").strip()
    if text in {"", "-", "None", "null", "nan", "NaN"}:
        return "—"
    try:
        amount = Decimal(text)
    except Exception:  # noqa: BLE001
        return str(value)
    if not amount.is_finite():
        return "—"
    if currency.upper() == "JPY":
        if amount >= Decimal("1000000000000"):
            return f"{amount / Decimal('1000000000000'):.1f}".rstrip("0").rstrip(".") + "兆円"
        if amount >= Decimal("100000000"):
            return f"{amount / Decimal('100000000'):.0f}億円"
        return f"{amount:,.0f}円"
    if amount >= Decimal("1000000000"):
        return f"${amount / Decimal('1000000000'):.1f}".rstrip("0").rstrip(".") + "B"
    if amount >= Decimal("1000000"):
        return f"${amount / Decimal('1000000'):.1f}".rstrip("0").rstrip(".") + "M"
    return f"{amount:,.0f} {currency}"


def _favorite_sector_value(row: Mapping[str, object]) -> str:
    value = str(_favorite_first_value(row, "sector", "industry") or "").strip()
    if not value:
        return "—"
    return {"insurance": "保険"}.get(value, RANKING_OFFICIAL_SECTOR_LABELS.get(value, value))


def _format_watchlist_added_date(value: str | None) -> str:
    parsed = _parse_watchlist_datetime(value)
    if parsed is None:
        return "—"
    return parsed.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y/%m/%d")


def _format_watchlist_updated_at(value: str | None) -> str:
    parsed = _parse_watchlist_datetime(value)
    if parsed is None:
        return "—"
    localized = parsed.astimezone(ZoneInfo("Asia/Tokyo"))
    return f"{localized.month}/{localized.day} {localized:%H:%M} JST"


def _favorite_change_value(row: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None or str(value).strip() in {"", "-", "None", "null", "nan", "NaN"}:
            continue
        try:
            number = Decimal(str(value).replace("%", "").strip())
        except Exception:  # noqa: BLE001
            continue
        if key.startswith("return_") and "%" not in str(value):
            number *= Decimal("100")
        return f"{number:.2f}".rstrip("0").rstrip(".")
    return ""


def _favorite_movement_status(
    price_change_1d: object,
    price_change_5d: object,
    price_change_1m: object,
) -> str:
    one_day = _favorite_optional_decimal(price_change_1d)
    five_day = _favorite_optional_decimal(price_change_5d)
    one_month = _favorite_optional_decimal(price_change_1m)
    has_one_day = one_day is not None
    has_five_day = five_day is not None
    has_one_month = one_month is not None
    if not any((has_one_day, has_five_day, has_one_month)):
        return "未取得"
    if one_day is not None and one_day <= Decimal("-5"):
        return "急落警戒"
    if (five_day is not None and five_day <= Decimal("-3")) or (
        one_month is not None and one_month <= Decimal("-5")
    ):
        return "下落注意"
    if (
        five_day is not None
        and one_month is not None
        and five_day >= Decimal("3")
        and one_month >= Decimal("5")
    ):
        return "上昇傾向"
    if five_day is not None and five_day >= Decimal("0.5"):
        return "短期上昇"
    return "横ばい"


def _favorite_optional_decimal(value: object) -> Decimal | None:
    text = str(value or "").replace("%", "").strip()
    if not text or text in {"-", "None", "null", "nan", "NaN"}:
        return None
    try:
        number = Decimal(text)
    except Exception:  # noqa: BLE001
        return None
    return number if number.is_finite() else None


def _favorite_movement_html(payload: Mapping[str, str]) -> str:
    status = str(payload.get("movement_status") or "未取得")
    marker = {
        "上昇傾向": "↗",
        "短期上昇": "↑",
        "横ばい": "→",
        "下落注意": "↘",
        "急落警戒": "↓",
        "判定保留": "?",
    }.get(status, "…")
    values = [
        ("1日", payload.get("price_change_1d")),
        ("5日", payload.get("price_change_5d")),
        ("1か月", payload.get("price_change_1m")),
    ]
    if not any(value for _, value in values):
        detail = "値動きデータなし"
    else:
        detail = " / ".join(
            f"{label} {_signed_percent_from_text(str(value or '')) or '未取得'}"
            for label, value in values
        )
    return (
        f'<div class="smai-watchlist-movement smai-watchlist-movement--{html.escape(_favorite_status_tone(status))}">'
        f'<strong aria-hidden="true">{marker}</strong>'
        f"<span>{html.escape(detail)}</span>"
        "</div>"
    )


def _favorite_metrics_missing(payload: Mapping[str, object]) -> bool:
    return all(
        _favorite_display_value(payload.get(key), fallback="") == ""
        or _favorite_display_value(payload.get(key)) == "未取得"
        for key in ("price", "ai_score", "upside", "downside")
    )


def _format_watchlist_date_label(value: str | None, *, fallback: str = "未設定") -> str:
    parsed = _parse_watchlist_datetime(value)
    if parsed is None:
        return fallback
    if "T" not in str(value):
        return parsed.strftime("%Y/%m/%d")
    return parsed.astimezone().strftime("%Y/%m/%d %H:%M")


def _parse_watchlist_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(str(value))
        except ValueError:
            return None
        return datetime.combine(parsed_date, time.min).replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _date_sort_value(value: str | None) -> float:
    parsed = _parse_watchlist_datetime(value)
    if parsed is None:
        return 0.0
    return parsed.timestamp()


def _decimal_sort_value(value: str | None) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return Decimal("-1")


def _favorite_metric_html(label: str, value: object, *, fallback: str = "未取得") -> str:
    display_value = _favorite_display_value(value, fallback=fallback)
    muted_class = (
        " smai-watchlist-metric--muted"
        if display_value in {"未取得", "未確認", "未設定", "未更新"}
        else ""
    )
    return (
        f'<div class="smai-watchlist-metric{muted_class}">'
        f'<span class="smai-watchlist-metric-label">{html.escape(label)}</span>'
        f'<strong class="smai-watchlist-metric-value">{html.escape(display_value)}</strong>'
        "</div>"
    )


def _favorite_info_row_html(label: str, value: object, *, fallback: str = "未確認") -> str:
    display_value = _favorite_display_value(value, fallback=fallback)
    return (
        '<div class="smai-watchlist-info-row">'
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(display_value)}</strong>"
        "</div>"
    )


def _favorite_card_html(payload: Mapping[str, str]) -> str:
    symbol = _favorite_display_value(payload.get("symbol"), fallback="未取得")
    name = _favorite_display_value(payload.get("name"), fallback=symbol)
    status = payload.get("status", "")
    status_label = _favorite_display_value(
        payload.get("status_label") or _favorite_status_display_label(status),
        fallback="判定保留",
    )
    refresh_status = payload.get("refresh_status", "")
    refresh_label = _favorite_display_value(payload.get("refresh_label"), fallback="未確認")
    meta = " / ".join(
        html.escape(_favorite_display_value(payload.get(key), fallback="未取得"))
        for key in ("market", "asset_type", "currency")
    )
    added_at = html.escape(_format_watchlist_added_date(payload.get("added_at")))
    updated_at = html.escape(_format_watchlist_updated_at(payload.get("last_checked_at")))
    has_decision_details = _favorite_has_decision_details(payload)
    metrics_missing = _favorite_metrics_missing(payload)
    decision_badge = (
        _favorite_display_value(payload.get("decision_status"), fallback="判断メモあり")
        if has_decision_details
        else "メモ未入力"
    )
    metrics = "".join(
        [
            _favorite_metric_html("価格", payload.get("price"), fallback="価格データなし"),
            _favorite_metric_html("AI総合", payload.get("ai_score"), fallback="AI評価なし"),
            _favorite_metric_html("上昇気配", payload.get("upside"), fallback="AI評価なし"),
            _favorite_metric_html("上向き兆候", payload.get("reversal"), fallback="未計算"),
            _favorite_metric_html("下振れ警戒", payload.get("downside"), fallback="AI評価なし"),
        ]
    )
    fundamentals = "".join(
        _favorite_detail_metric_html(label, payload.get(key))
        for label, key in (
            ("配当利回り", "dividend_yield"),
            ("PER", "per"),
            ("PBR", "pbr"),
            ("ROE", "roe"),
            ("時価総額", "market_cap"),
            ("セクター", "sector"),
        )
    )
    data_update_content = (
        '<div class="smai-watchlist-data-needed">'
        "<strong>データ更新が必要です</strong>"
        "<span>ウォッチリスト更新で価格・AI評価・ニュース状態を確認できます。</span>"
        "</div>"
        if metrics_missing
        else ""
    )
    snapshot_notice = (
        '<div class="smai-watchlist-snapshot-notice">'
        "取得に失敗しました。前回データを表示しています。"
        "</div>"
        if payload.get("snapshot_status") == "failed" and not metrics_missing
        else ""
    )
    return (
        f'<section class="smai-watchlist-card smai-watchlist-card--{html.escape(_favorite_status_tone(status))}">'
        '<div class="smai-watchlist-card-header">'
        "<div>"
        f'<div class="smai-watchlist-card-symbol">{html.escape(name)}</div>'
        f'<div class="smai-watchlist-card-name">{html.escape(symbol)}</div>'
        "</div>"
        '<div class="smai-watchlist-card-dates">'
        f"<span>追加日: <strong>{added_at}</strong></span>"
        f"<span>更新: <strong>{updated_at}</strong></span>"
        "</div>"
        "</div>"
        f'<div class="smai-watchlist-card-meta">{meta}</div>'
        '<div class="smai-watchlist-badge-row">'
        f'<span class="smai-watchlist-badge smai-watchlist-status--{html.escape(_favorite_status_tone(status))}">'
        f"{html.escape(status_label)}</span>"
        f'<span class="smai-watchlist-badge smai-watchlist-refresh--{html.escape(_favorite_refresh_tone(refresh_status))}">'
        f"{html.escape(refresh_label)}</span>"
        '<span class="smai-watchlist-badge smai-watchlist-decision-badge">'
        f"{html.escape(decision_badge)}</span>"
        "</div>"
        f"{_favorite_movement_html(payload)}"
        f"{snapshot_notice}"
        f"{data_update_content}"
        f'<div class="smai-watchlist-metric-grid">{metrics}</div>'
        '<div class="smai-watchlist-detail-title">詳細指標</div>'
        f'<div class="smai-watchlist-detail-grid">{fundamentals}</div>'
        "</section>"
    )


def _favorite_detail_metric_html(label: str, value: object) -> str:
    display_value = _favorite_display_value(value, fallback="—")
    return (
        '<div class="smai-watchlist-detail-metric">'
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(display_value)}</strong>"
        "</div>"
    )


def _favorite_has_decision_details(payload: Mapping[str, str]) -> bool:
    empty_values = {"", "未入力", "未設定", "未更新", "None", "null"}
    return any(
        str(payload.get(key) or "").strip() not in empty_values
        for key in ("watch_reason", "decision_note", "next_check_at", "next_check_label")
    )


def _favorite_table_rows(rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "ウォッチ": "★",
            "銘柄": row["symbol"],
            "銘柄名": row["name"],
            "価格": row["price"],
            "1日": _signed_percent_from_text(row.get("price_change_1d", "")) or "未取得",
            "5日": _signed_percent_from_text(row.get("price_change_5d", "")) or "未取得",
            "1か月": _signed_percent_from_text(row.get("price_change_1m", "")) or "未取得",
            "AI総合": row["ai_score"],
            "上昇気配": row["upside"],
            "上向き兆候": row.get("reversal", ""),
            "下振れ警戒": row["downside"],
            "状態": row["status_label"],
            "更新": row["refresh_label"],
            "最終確認": row["last_checked_at"],
            "確認ポイント": row["checkpoint"],
        }
        for row in rows
    ]


def _render_favorite_table(rows: list[dict[str, str]]) -> None:
    st.dataframe(
        _favorite_table_rows(rows),
        hide_index=True,
        use_container_width=True,
        column_config={
            "ウォッチ": st.column_config.TextColumn("★", width="small"),
            "銘柄": st.column_config.TextColumn("銘柄", width="small"),
            "銘柄名": st.column_config.TextColumn("銘柄名", width="medium"),
            "価格": st.column_config.TextColumn("価格", width="small"),
            "確認ポイント": st.column_config.TextColumn("確認ポイント", width="large"),
        },
    )
    st.caption("詳細確認・メモ編集・解除はカード表示から行えます。")


def _render_favorite_card(payload: Mapping[str, str]) -> None:
    symbol = payload["symbol"]
    st.markdown(_favorite_card_html(payload), unsafe_allow_html=True)
    col_detail, col_cockpit, col_remove = st.columns([1.1, 1.25, 0.65])
    with col_detail:
        st.markdown(
            '<div class="smai-watchlist-detail-anchor"></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "銘柄を詳しく見る",
            key=f"watchlist_detail_{symbol}",
            use_container_width=True,
        ):
            _render_symbol_universe_detail_dialog(
                symbol,
                ranking_row=_watchlist_ranking_detail_row(payload),
            )
    with col_cockpit:
        st.markdown(
            '<div class="smai-watchlist-cockpit-anchor"></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Cockpit画面で確認",
            key=f"watchlist_cockpit_{symbol}",
            use_container_width=True,
        ):
            _select_favorite_symbol_for_cockpit(symbol, "cockpit")
            st.rerun()
    with col_remove:
        st.markdown(
            '<div class="smai-watchlist-remove-anchor"></div>',
            unsafe_allow_html=True,
        )
        if st.button("解除", key=f"watchlist_remove_{symbol}", use_container_width=True):
            remove_favorite(symbol)
            st.toast("Myウォッチリストから解除しました。")
            st.rerun()
    if _favorite_has_decision_details(payload):
        with st.expander("判断メモを編集"):
            _render_favorite_decision_form(payload)


def _watchlist_ranking_detail_row(payload: Mapping[str, str]) -> dict[str, str]:
    return {
        "銘柄": str(payload.get("symbol") or ""),
        "銘柄名": str(payload.get("name") or ""),
        "現在株価": str(payload.get("price") or ""),
        "総合スコア": str(payload.get("ai_score") or ""),
        "上昇気配": str(payload.get("upside") or ""),
        "下降警戒": str(payload.get("downside") or ""),
        "データ品質": (
            "前回データ"
            if payload.get("snapshot_status") == "failed"
            else str(payload.get("snapshot_status") or "未取得")
        ),
        "確認ポイント": str(payload.get("checkpoint") or ""),
    }


def _render_favorite_decision_form(payload: Mapping[str, str]) -> None:
    symbol = payload["symbol"]
    status_options = ["未設定", *FAVORITE_DECISION_STATUS_OPTIONS]
    current_status = payload.get("decision_status") or "未設定"
    status_index = status_options.index(current_status) if current_status in status_options else 0
    with st.form(f"watchlist_decision_form_{symbol}", clear_on_submit=False):
        decision_status = st.selectbox(
            "判断状態",
            status_options,
            index=status_index,
            key=f"watchlist_decision_status_{symbol}",
        )
        watch_reason = st.text_area(
            "Watch理由",
            value=(
                "" if payload.get("watch_reason") == "未入力" else payload.get("watch_reason", "")
            ),
            height=84,
            key=f"watchlist_watch_reason_{symbol}",
        )
        decision_note = st.text_area(
            "現在の判断メモ",
            value=(
                "" if payload.get("decision_note") == "未入力" else payload.get("decision_note", "")
            ),
            height=84,
            key=f"watchlist_decision_note_{symbol}",
        )
        next_check_label = st.text_input(
            "次の確認",
            value=(
                ""
                if payload.get("next_check_label") == "未設定"
                else payload.get("next_check_label", "")
            ),
            key=f"watchlist_next_check_label_{symbol}",
        )
        next_check_at = st.text_input(
            "次回確認日",
            value=payload.get("next_check_at", ""),
            placeholder="2026-07-01",
            key=f"watchlist_next_check_at_{symbol}",
        )
        submitted = st.form_submit_button("保存", use_container_width=True)
    if not submitted:
        return
    updated = update_favorite_decision_note(
        symbol,
        watch_reason=watch_reason,
        decision_status="" if decision_status == "未設定" else decision_status,
        decision_note=decision_note,
        next_check_at=next_check_at,
        next_check_label=next_check_label,
    )
    if updated is None:
        st.warning("判断メモを保存できませんでした。対象銘柄を確認してください。")
        return
    st.toast("判断メモを保存しました。")
    st.rerun()


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


def _market_data_preview_advanced_forecast_rows(
    preview: MarketDataPreview,
    *,
    horizon_days: int | None = None,
) -> list[dict[str, str]]:
    rows = getattr(preview, "advanced_forecast_rows", [])
    if not isinstance(rows, list):
        rows = []
    if horizon_days is None or _advanced_forecast_rows_match_horizon(rows, horizon_days):
        return rows

    bars = getattr(preview, "bars", [])
    if not bars:
        return rows
    results = advanced_forecast_results_for_bars(bars, horizon_days=horizon_days)
    return advanced_forecast_rows_for_results(results, bars)


def _market_data_preview_advanced_forecast_consensus_rows(
    preview: MarketDataPreview,
    advanced_forecast_rows: list[dict[str, str]],
    *,
    horizon_days: int | None = None,
) -> list[dict[str, str]]:
    rows = getattr(preview, "advanced_forecast_consensus_rows", [])
    if not isinstance(rows, list):
        rows = []
    if horizon_days is None or _advanced_forecast_rows_match_horizon(rows, horizon_days):
        return rows

    bars = getattr(preview, "bars", [])
    if not bars:
        return rows
    results = advanced_forecast_results_for_bars(bars, horizon_days=horizon_days)
    if results:
        return advanced_forecast_consensus_rows_for_results(results)
    return rows


def _advanced_forecast_rows_match_horizon(
    rows: list[dict[str, str]],
    horizon_days: int,
) -> bool:
    if not rows:
        return False
    return all(_int_from_text(row.get("horizon_days", "")) == horizon_days for row in rows)


def _render_market_data_preview_result(preview: MarketDataPreview) -> None:
    symbol_label = _market_data_preview_symbol_label(preview)
    forecast_horizon_days = _render_market_data_cockpit_header(preview, symbol_label)
    advanced_forecast_rows = _market_data_preview_advanced_forecast_rows(
        preview,
        horizon_days=forecast_horizon_days,
    )
    advanced_forecast_consensus_rows = _market_data_preview_advanced_forecast_consensus_rows(
        preview,
        advanced_forecast_rows,
        horizon_days=forecast_horizon_days,
    )
    forecast_rows = forecast_chart_rows(
        preview.bars,
        horizon_days=forecast_horizon_days,
        advanced_forecast_rows=advanced_forecast_rows,
        advanced_forecast_consensus_rows=advanced_forecast_consensus_rows,
    )
    consensus_rows = forecast_consensus_rows_for_bars(
        preview.bars,
        horizon_days=forecast_horizon_days,
    )
    metric_rows = forecast_metric_rows_for_bars(preview.bars, horizon_days=forecast_horizon_days)

    symbol = _market_data_preview_symbol(preview)
    provider_name = _metadata_value(preview.provider_rows, "provider") or "unknown"
    reference_period = forecast_reference_period(preview.bars, horizon_days=forecast_horizon_days)
    score_display_rows = investment_score_display_rows(preview.investment_score_rows)
    summary_items = cockpit_summary_items(
        symbol=symbol,
        name=symbol_name(symbol) or "",
        provider=provider_name,
        as_of=_market_data_as_of(preview),
        reference_period_days=reference_period,
        forecast_horizon_days=forecast_horizon_days,
        score_row=score_display_rows[0] if score_display_rows else None,
        symbol_metadata=_symbol_universe_row_for_symbol(symbol) if symbol else None,
    )

    def render_cockpit_favorite_action() -> None:
        if symbol:
            universe_row = _symbol_universe_rows_by_symbol().get(symbol.upper(), {})
            render_favorite_button(
                symbol,
                name=str(universe_row.get("name") or symbol_label),
                market=str(universe_row.get("market") or ""),
                asset_type=str(universe_row.get("asset_type") or ""),
                currency=str(universe_row.get("currency") or ""),
                source_screen="cockpit",
                key=f"market_data_cockpit_favorite_{symbol}",
                prominent=True,
            )

    render_cockpit_summary_header(
        summary_items,
        header_action=render_cockpit_favorite_action if symbol else None,
    )
    _render_favorite_next_action_hint()
    score_row = _render_investment_score_section(
        preview,
        symbol_label,
        rows=score_display_rows,
    )
    if score_row is not None:
        _render_cockpit_direction_signal_section(score_row, consensus_rows)
    _render_price_forecast_hero(
        preview,
        symbol_label,
        forecast_rows,
        consensus_rows,
        metric_rows,
        advanced_forecast_rows,
        advanced_forecast_consensus_rows,
        forecast_horizon_days=forecast_horizon_days,
    )
    summary_rows = cockpit_detail_summary_rows(preview, consensus_rows, metric_rows)
    llm_factor_response = _cockpit_llm_factor_result(preview) if symbol else None
    _render_cockpit_research_summary(preview)
    _render_cockpit_llm_factor(preview, response=llm_factor_response)
    _render_cockpit_interpretation(
        preview,
        llm_factor_result=llm_factor_response.result if llm_factor_response else None,
        price_summary=summary_rows,
        forecast_summary=forecast_consensus_display_rows(consensus_rows),
        advanced_forecast_summary=(
            advanced_forecast_consensus_display_rows(advanced_forecast_consensus_rows)
            if advanced_forecast_consensus_rows
            else []
        ),
        investment_score_summary=[score_row] if score_row is not None else score_display_rows[:1],
    )
    if score_row is not None:
        _render_score_breakdown_context(preview, symbol_label, score_row, score_display_rows)
    _render_cockpit_decision_report(preview)
    _render_cockpit_technical_detail_expander(
        preview,
        symbol_label=symbol_label,
        score_display_rows=score_display_rows,
        score_row=score_row,
        consensus_rows=consensus_rows,
        metric_rows=metric_rows,
        advanced_forecast_rows=advanced_forecast_rows,
        advanced_forecast_consensus_rows=advanced_forecast_consensus_rows,
        summary_rows=summary_rows,
    )

    if preview.error_rows:
        st.subheader("補助データの取得警告")
        _render_provider_error_summary(preview.error_rows)


def _render_cockpit_technical_detail_expander(
    preview: MarketDataPreview,
    *,
    symbol_label: str,
    score_display_rows: list[dict[str, str]],
    score_row: dict[str, str] | None,
    consensus_rows: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
    advanced_forecast_rows: list[dict[str, str]],
    advanced_forecast_consensus_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
) -> None:
    with st.expander("詳細データ・開発者向け", expanded=False):
        tabs = st.tabs(["予測", "スコア", "取得元", "特徴量", "エクスポート"])
        with tabs[0]:
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
            if advanced_forecast_consensus_rows:
                st.subheader(ADVANCED_FORECAST_CONSENSUS_LABEL)
                _render_table(
                    advanced_forecast_consensus_display_rows(advanced_forecast_consensus_rows),
                    f"{ADVANCED_FORECAST_CONSENSUS_LABEL}を表示するには、もう少し長い価格データが必要です。",
                )
            if advanced_forecast_rows:
                st.subheader("高度予測モデル")
                st.caption(
                    "高度予測は取得期間に合わせた予測先で表示します。売買判断ではなく、価格レンジと注意点の確認に使います。"
                )
                _render_table(
                    advanced_forecast_display_rows(advanced_forecast_rows),
                    "高度予測を表示するには、もう少し長い価格データが必要です。",
                )
        with tabs[1]:
            st.markdown("#### スコア・リスク詳細")
            if score_row is not None:
                detail_rows = cockpit_direction_signal_detail_rows(
                    score_row, consensus_rows[0] if consensus_rows else {}
                )
                _render_symbol_detail_table(detail_rows)
                _render_score_breakdown_chart(score_component_rows(score_row))
                period_rows = cockpit_period_evaluation_rows(preview.bars)
                memo_rows = cockpit_investment_memo_rows(preview, score_row)
                st.markdown("#### 期間別の見方")
                _render_symbol_detail_table(period_rows)
                st.markdown("#### 確認メモ（詳細）")
                _render_symbol_detail_table(memo_rows)
            st.markdown("#### 主要確認サマリー")
            _render_symbol_detail_table(summary_rows)
            st.markdown("#### 投資スコア")
            _render_table(score_display_rows, EMPTY_STATE_MESSAGES["investment_score_rows"])
            st.markdown("#### スクリーニング")
            _render_table(preview.screening_rows, EMPTY_STATE_MESSAGES["screening_score_rows"])

        with tabs[2]:
            st.markdown("#### データ取得元")
            _render_table(preview.provider_rows, EMPTY_STATE_MESSAGES["provider_metadata"])
            st.markdown("#### 現在値")
            _render_table(preview.quote_rows, EMPTY_STATE_MESSAGES["quote_rows"])
            st.markdown("#### 価格データ概要")
            _render_table(preview.ohlcv_rows, EMPTY_STATE_MESSAGES["ohlcv_rows"])

        with tabs[3]:
            st.markdown("#### 為替")
            _render_table(preview.fx_rows, EMPTY_STATE_MESSAGES["fx_rows"])
            st.markdown("#### 特徴量データ")
            _render_table(preview.feature_rows, EMPTY_STATE_MESSAGES["feature_snapshot_rows"])

        with tabs[4]:
            st.caption("JSON / CSVは保存・再確認が必要な場合に利用します。")
            if metric_rows:
                col_json, col_csv = st.columns(2)
                col_json.download_button(
                    "予測JSONをダウンロード",
                    data=forecast_metric_json_download(metric_rows),
                    file_name="forecast_metrics.json",
                    mime="application/json",
                )
                with col_csv:
                    render_csv_download_button(
                        label="予測CSVをダウンロード",
                        data=forecast_metric_csv_download(metric_rows),
                        file_name="forecast_metrics.csv",
                    )
            if preview.investment_score_rows:
                col_json, col_csv = st.columns(2)
                col_json.download_button(
                    "投資スコアJSONをダウンロード",
                    data=investment_score_json_download(preview.investment_score_rows),
                    file_name="investment_score.json",
                    mime="application/json",
                )
                with col_csv:
                    render_csv_download_button(
                        label="投資スコアCSVをダウンロード",
                        data=investment_score_csv_download(preview.investment_score_rows),
                        file_name="investment_score.csv",
                    )
            if preview.screening_rows:
                col_json, col_csv = st.columns(2)
                col_json.download_button(
                    "スクリーニングJSONをダウンロード",
                    data=screening_score_json_download(preview.screening_rows),
                    file_name="screening_score.json",
                    mime="application/json",
                )
                with col_csv:
                    render_csv_download_button(
                        label="スクリーニングCSVをダウンロード",
                        data=screening_score_csv_download(preview.screening_rows),
                        file_name="screening_score.csv",
                    )


def _render_cockpit_research_summary(preview: MarketDataPreview) -> None:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return
    st.subheader(RESEARCH_COCKPIT_SECTION_TITLE)
    st.caption(RESEARCH_COCKPIT_INTRO)
    report = _cockpit_research_report_from_state(preview)
    news_report = _cockpit_stock_news_report_from_state(preview)
    external_research_result = _cockpit_external_research_fetch_result_from_state(preview)
    fetch_clicked = _render_research_operation_card(
        preview,
        report=report,
        news_report=news_report,
        external_result=external_research_result,
    )
    should_rerun_after_refresh = False
    if fetch_clicked:
        loading_slot = st.empty()
        with loading_slot.container():
            render_mascot_loading(
                "report",
                title="AI調査を整理中",
                message=(
                    "外部参照ソース、ニュース、保存済み資料を読み込み、"
                    "企業リサーチレポートにまとめています。"
                ),
                tone="info",
            )
        loading_headlines, loading_headline_note = workflow_loading_headlines_from_cache()
        progress_bar: Any | None = None
        progress_status: Any | None = None

        def update_research_progress(message: str, ratio: float) -> None:
            if hasattr(loading_slot, "markdown"):
                loading_slot.markdown(
                    workflow_loading_html(
                        title="AI調査データを取得中",
                        message=(
                            "外部参照ソース、ニュース、保存済み資料を確認し、企業リサーチに整理しています。"
                        ),
                        current_step=message,
                        progress=ratio,
                        mode="blocking",
                        headlines=loading_headlines,
                        headline_note=loading_headline_note,
                    ),
                    unsafe_allow_html=True,
                )
            if progress_status is not None:
                progress_status.caption(message)
            if progress_bar is not None:
                progress_bar.progress(max(0.0, min(1.0, ratio)))

        progress_bar = st.progress(0.0)
        progress_status = st.empty()
        update_research_progress("調査対象と取得元を確認しています。", 0.08)
        try:
            refresh_started = perf_time.perf_counter()
            trace_rows: list[tuple[str, float]] = []
            try:
                update_research_progress("外部参照ソースとニュースを取得しています。", 0.24)
                step_started = perf_time.perf_counter()
                external_result = _fetch_external_research_for_preview(preview)
                trace_rows.append(("外部取得", perf_time.perf_counter() - step_started))
                update_research_progress("外部参照ソースをAI調査に反映しています。", 0.52)
                if external_result.entries:
                    st.success(
                        f"外部参照ソース {len(external_result.entries)}件をAI調査に反映しました。"
                    )
                cache_info = external_research_fetch_cache_info()
                if cache_info.get("cache_hit") is True:
                    st.info(
                        "直近の外部参照ソースを再利用しました。表示内容は同じ品質で更新します。"
                    )
                st.markdown(
                    _external_research_fetch_overview_html(external_result),
                    unsafe_allow_html=True,
                )
                for warning in external_result.warnings[3:]:
                    st.warning(warning)
            except AppError as exc:
                st.warning(
                    "外部参照ソースを取得できませんでした。保存済み資料と既存データでAI調査を続行します。"
                )
                st.caption(_external_research_fetch_failure_caption(exc))
                with st.expander("取得失敗の技術詳細", expanded=False):
                    st.caption(exc.message)
                    if exc.details:
                        st.json(exc.details)
                update_research_progress("保存済み資料と既存データで調査を続行しています。", 0.52)
            update_research_progress("企業リサーチレポートを生成しています。", 0.70)
            step_started = perf_time.perf_counter()
            st.session_state[MARKET_DATA_RESEARCH_REPORT_STATE_KEY] = (
                _build_cockpit_research_report(preview)
            )
            trace_rows.append(("企業レポート生成", perf_time.perf_counter() - step_started))
            update_research_progress("ニュースと開示材料を整理しています。", 0.86)
            step_started = perf_time.perf_counter()
            st.session_state[MARKET_DATA_STOCK_NEWS_REPORT_STATE_KEY] = (
                _build_cockpit_stock_news_report(preview)
            )
            trace_rows.append(("ニュース整理", perf_time.perf_counter() - step_started))
            trace_rows.append(("合計", perf_time.perf_counter() - refresh_started))
            st.session_state[RESEARCH_REFRESH_TRACE_STATE_KEY] = trace_rows
            update_research_progress("表示内容を更新しています。", 0.96)
            st.caption(_research_refresh_trace_caption(trace_rows))
            update_research_progress("AI調査の更新が完了しました。", 1.0)
            should_rerun_after_refresh = True
        finally:
            loading_slot.empty()
        if should_rerun_after_refresh:
            st.rerun()

    report = _cockpit_research_report_from_state(preview)
    news_report = _cockpit_stock_news_report_from_state(preview)
    external_research_result = _cockpit_external_research_fetch_result_from_state(preview)
    if report is None:
        if external_research_result is not None:
            st.markdown(
                _external_research_fetch_overview_html(external_research_result),
                unsafe_allow_html=True,
            )
        if news_report is not None and news_report.news:
            _render_stock_news_cards_panel(news_report)
    else:
        _render_research_summary_panel(
            report,
            detail_expanded=False,
            news_report=news_report,
            external_research_result=external_research_result,
            display_context="cockpit",
        )


def _render_cockpit_llm_factor(
    preview: MarketDataPreview,
    *,
    response: LLMFactorServiceResult | None = None,
) -> LLMFactorServiceResult | None:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return None
    response = response or _cockpit_llm_factor_result(preview)
    result = response.result
    source_rows = _llm_factor_evidence_display_rows(result)
    st.markdown("#### AI調査から見た材料分析")
    if not source_rows:
        st.info(
            "出典付きのAI調査材料はまだありません。上の「AI調査を開始・更新」で"
            "資料・ニュースを取得してから確認してください。"
        )
        return response
    st.caption(
        "根拠資料をLLMで上昇材料・注意材料へ整理する補助メモです。"
        "スコアやランキングには反映しません。"
    )
    st.markdown(_llm_factor_panel_html(result), unsafe_allow_html=True)
    with st.expander("AI材料分析の詳細（出典・実行情報）", expanded=False):
        st.caption(_llm_factor_cache_caption(response.cache))
        st.markdown(_llm_factor_runtime_html(result), unsafe_allow_html=True)
        if source_rows:
            _render_compact_dataframe(source_rows)
        else:
            st.caption("出典付きの材料はまだ表示できません。")
    return response


def _render_cockpit_interpretation(
    preview: MarketDataPreview,
    *,
    llm_factor_result: LLMFactorResult | None,
    price_summary: list[dict[str, str]],
    forecast_summary: list[dict[str, str]],
    advanced_forecast_summary: list[dict[str, str]],
    investment_score_summary: list[dict[str, str]],
) -> None:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return
    report = _cockpit_research_report_from_state(preview)
    news_report = _cockpit_stock_news_report_from_state(preview)
    external_result = _cockpit_external_research_fetch_result_from_state(preview)
    research_evidence = _cockpit_interpretation_research_evidence_rows(
        report=report,
        news_report=news_report,
        external_result=external_result,
    )
    st.subheader("04 確認メモ")
    if not research_evidence:
        st.info(
            "AI調査の出典がまだないため、確認メモは表示していません。"
            "先に「AI調査を開始・更新」で材料を取得してください。"
        )
        return
    response = _cockpit_interpretation_result(
        preview,
        llm_factor_result=llm_factor_result,
        price_summary=price_summary,
        forecast_summary=forecast_summary,
        advanced_forecast_summary=advanced_forecast_summary,
        investment_score_summary=investment_score_summary,
    )
    st.caption("価格・予測・AI調査を合わせ、次に見ることを短い確認メモに整理します。")
    st.markdown(_cockpit_interpretation_panel_html(response.result), unsafe_allow_html=True)
    with st.expander("AI解釈メモの詳細（実行情報）", expanded=False):
        st.caption(_cockpit_interpretation_cache_caption(response.cache))
        st.markdown(_cockpit_interpretation_runtime_html(response.result), unsafe_allow_html=True)


def _cockpit_interpretation_result(
    preview: MarketDataPreview,
    *,
    llm_factor_result: LLMFactorResult | None,
    price_summary: list[dict[str, str]],
    forecast_summary: list[dict[str, str]],
    advanced_forecast_summary: list[dict[str, str]],
    investment_score_summary: list[dict[str, str]],
) -> CockpitInterpretationServiceResult:
    symbol = _market_data_preview_symbol(preview)
    as_of = _date_from_iso_text(_market_data_as_of(preview)) or default_as_of_date()
    report = _cockpit_research_report_from_state(preview)
    news_report = _cockpit_stock_news_report_from_state(preview)
    external_result = _cockpit_external_research_fetch_result_from_state(preview)
    context = build_cockpit_interpretation_context(
        symbol=symbol,
        company_name=symbol_name(symbol) or None,
        as_of=as_of,
        price_summary=_summary_from_rows(price_summary),
        forecast_summary=_summary_from_rows(
            [*forecast_summary[:2], *advanced_forecast_summary[:2]]
        ),
        investment_score=_summary_from_rows(investment_score_summary[:1]),
        research_evidence=_cockpit_interpretation_research_evidence_rows(
            report=report,
            news_report=news_report,
            external_result=external_result,
        ),
        llm_factor=llm_factor_result,
        warnings=_cockpit_interpretation_warnings(preview),
    )
    return build_cockpit_interpretation_from_settings(context)


def _cockpit_llm_factor_result(preview: MarketDataPreview) -> LLMFactorServiceResult:
    symbol = _market_data_preview_symbol(preview)
    as_of = _date_from_iso_text(_market_data_as_of(preview)) or default_as_of_date()
    report = _cockpit_research_report_from_state(preview)
    news_report = _cockpit_stock_news_report_from_state(preview)
    external_result = _cockpit_external_research_fetch_result_from_state(preview)
    evidence_sources = _llm_factor_evidence_sources(
        symbol=symbol,
        as_of=as_of,
        report=report,
        news_report=news_report,
        external_result=external_result,
    )
    return build_llm_factor_reference_result_from_settings(
        ticker=symbol,
        as_of=as_of,
        evidence_sources=evidence_sources,
        company_name=symbol_name(symbol) or None,
    )


def _summary_from_rows(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        return {}
    result: dict[str, str] = {}
    for row in rows[:3]:
        for key, value in row.items():
            normalized = str(value).strip()
            if not normalized or key in result:
                continue
            result[str(key)] = normalized
    return result


def _cockpit_interpretation_research_evidence_rows(
    *,
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
    external_result: ExternalResearchFetchResult | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if report is not None:
        for index, evidence in enumerate(report.evidence[:3], start=1):
            rows.append(
                {
                    "evidence_id": f"research_{index:03d}",
                    "source_type": evidence.source_type,
                    "title": evidence.title,
                    "summary": evidence.excerpt,
                    "published_at": (
                        evidence.published_at.isoformat() if evidence.published_at else ""
                    ),
                }
            )
    if news_report is not None:
        for index, item in enumerate(news_report.news[:3], start=1):
            rows.append(
                {
                    "evidence_id": f"news_{index:03d}",
                    "source_type": "news",
                    "title": item.title,
                    "summary": item.summary,
                    "published_at": item.published_at.isoformat() if item.published_at else "",
                    "url": item.url or "",
                }
            )
    if external_result is not None:
        for index, entry in enumerate(external_result.entries[:3], start=1):
            rows.append(
                {
                    "evidence_id": f"external_{index:03d}",
                    "source_type": entry.source_type,
                    "title": entry.title,
                    "summary": entry.content_summary,
                    "published_at": (entry.published_at.isoformat() if entry.published_at else ""),
                    "url": entry.source_url,
                }
            )
    return rows[:8]


def _cockpit_interpretation_warnings(preview: MarketDataPreview) -> list[str]:
    warnings: list[str] = []
    for row in preview.error_rows[:4]:
        message = row.get("エラー") or row.get("message") or row.get("詳細") or ""
        if message:
            warnings.append(str(message))
    return warnings


def _llm_factor_evidence_sources(
    *,
    symbol: str,
    as_of: date,
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
    external_result: ExternalResearchFetchResult | None = None,
) -> list[EvidenceSource]:
    sources: list[EvidenceSource] = []
    if external_result is not None:
        for entry in external_result.entries[:8]:
            sources.append(_llm_factor_source_from_external_entry(entry, as_of=as_of))
    if news_report is not None:
        for news_item in news_report.news[:5]:
            sources.append(_llm_factor_source_from_news(news_item, as_of=as_of))
    if report is not None:
        for evidence_item in report.evidence[:5]:
            sources.append(
                _llm_factor_source_from_research_evidence(
                    evidence_item,
                    symbol=symbol,
                    as_of=as_of,
                )
            )
    # Keep all candidates here.  The backend applies entity matching and
    # canonical duplicate removal, then returns the audit counts for the UI.
    return sources


def _llm_factor_source_from_external_entry(
    entry: ExternalResearchFetchManifestEntry,
    *,
    as_of: date,
) -> EvidenceSource:
    source_date = entry.published_at or entry.fetched_at.date() or as_of
    return EvidenceSource(
        title=entry.title,
        source_type=_llm_factor_source_type(entry.source_type),
        source_url=entry.source_url,
        source_date=source_date,
        fetched_at=entry.fetched_at,
        provider=entry.provider,
        summary=entry.content_summary or None,
        reliability_score=_llm_factor_source_reliability(
            entry.source_type,
            provider=entry.provider,
        ),
    )


def _llm_factor_source_from_news(
    item: Any,
    *,
    as_of: date,
) -> EvidenceSource:
    return EvidenceSource(
        title=item.title,
        source_type="news",
        source_url=item.url,
        source_date=item.published_at or as_of,
        provider=item.source or "news",
        summary=item.summary,
        reliability_score=Decimal("62"),
    )


def _llm_factor_source_from_research_evidence(
    item: Any,
    *,
    symbol: str,
    as_of: date,
) -> EvidenceSource:
    source_url = f"smai://research-evidence/{symbol}/{item.document_id}/{item.chunk_id}"
    return EvidenceSource(
        title=item.title,
        source_type=_llm_factor_source_type(item.source_type),
        source_url=source_url,
        source_date=item.published_at or as_of,
        provider="research",
        summary=item.excerpt,
        reliability_score=_percent_from_unit_decimal(item.reliability),
    )


def _llm_factor_source_type(source_type: str) -> LLMFactorSourceType:
    if source_type == "tdnet":
        return "tdnet"
    if source_type == "news":
        return "news"
    if source_type == "provider_profile":
        return "provider_profile"
    if source_type == "company_ir":
        return "company_ir"
    if source_type in {
        "annual_report",
        "earnings_report",
        "earnings_presentation",
        "medium_term_plan",
        "integrated_report",
    }:
        return "company_ir"
    if source_type == "user_note":
        return "local_reference"
    return "other"


def _llm_factor_source_reliability(source_type: str, *, provider: str | None) -> Decimal:
    if source_type in {
        "tdnet",
        "company_ir",
        "annual_report",
        "earnings_report",
        "edinet",
    }:
        return Decimal("82")
    if source_type == "provider_profile":
        return Decimal("68")
    if source_type == "news":
        return Decimal("60")
    if provider:
        return Decimal("55")
    return Decimal("45")


def _percent_from_unit_decimal(value: Decimal) -> Decimal:
    return max(
        Decimal("0"),
        min(Decimal("100"), (value * Decimal("100")).quantize(Decimal("1"))),
    )


def _llm_factor_panel_html(result: LLMFactorResult) -> str:
    scores = [
        ("上昇材料", result.llm_bullish_score, "positive"),
        ("下降材料", result.llm_bearish_score, "warning"),
        ("カタリスト", result.llm_catalyst_score, "info"),
        ("リスク", result.llm_risk_score, "warning"),
        ("確信度", result.llm_confidence_score, _llm_factor_confidence_tone(result)),
    ]
    score_cards = "".join(
        '<section class="research-brief-metric-card">'
        '<div class="research-evidence-card-header">'
        f'<span class="research-evidence-pill {html.escape(tone)}">'
        f"{html.escape(label)}</span>"
        "</div>"
        f"<strong>{html.escape(_llm_factor_score_display(score))}</strong>"
        f"<p>{html.escape(_llm_factor_score_note(label, score))}</p>"
        "</section>"
        for label, score, tone in scores
    )
    bullish_items = _llm_factor_items_html(
        result.bullish_factors,
        empty_text="上昇材料として表示できる出典付き候補はまだ少なめです。",
    )
    bearish_items = _llm_factor_items_html(
        result.bearish_factors,
        empty_text="下降材料として表示できる出典付き候補はまだ少なめです。",
    )
    warnings = "".join(f"<li>{html.escape(warning)}</li>" for warning in result.warnings)
    warning_html = f"<ul>{warnings}</ul>" if warnings else "<p>特記事項なし</p>"
    missing_html = ""
    if result.missing_fields:
        missing = "、".join(result.missing_fields)
        missing_html = f"<p>不足項目: {html.escape(missing)}</p>"
    evidence_summary = _llm_factor_evidence_selection_display(result)
    runtime_state = _llm_factor_runtime_state_label(_llm_factor_runtime_state(result))
    return (
        '<section class="research-result-brief hero">'
        '<div class="research-result-brief-header">'
        '<span class="research-evidence-pill positive">参考表示</span>'
        '<span class="research-evidence-pill">根拠資料の補助</span>'
        f'<span class="research-evidence-pill">実行方式: {html.escape(runtime_state)}</span>'
        "</div>"
        "<h4>AI材料分析</h4>"
        f"<p>{html.escape(result.summary)}</p>"
        "<p>このAI材料分析は根拠資料の読み取り補助です。Ranking・予測・Investment Scoreには反映していません。</p>"
        f"<p>{html.escape(evidence_summary)}</p>"
        f'<div class="research-brief-metric-grid">{score_cards}</div>'
        '<div class="research-brief-reading-grid">'
        '<section class="research-brief-reading-item tone-positive">'
        "<h5>上昇材料候補 Top 3</h5>"
        f"{bullish_items}"
        "</section>"
        '<section class="research-brief-reading-item tone-warning">'
        "<h5>注意材料候補 Top 3</h5>"
        f"{bearish_items}"
        "</section>"
        '<section class="research-brief-reading-item tone-warning">'
        "<h5>確認メモ</h5>"
        f"{warning_html}"
        f"{missing_html}"
        f"<p>{html.escape(result.disclaimer)}</p>"
        "</section>"
        "</div>"
        "</section>"
    )


def _llm_factor_runtime_label(result: LLMFactorResult) -> str:
    return f"LLM接続: {_llm_factor_runtime_state(result)}"


def _llm_factor_runtime_html(result: LLMFactorResult) -> str:
    state = _llm_factor_runtime_state(result)
    items: list[str] = [f"状態: {_llm_factor_runtime_state_label(state)}"]
    if state in {"live", "fallback"} and result.provider:
        items.append(f"provider: {result.provider}")
    if state in {"live", "fallback"} and result.model_name:
        items.append(f"model: {result.model_name}")
    if state in {"live", "fallback"} and result.gateway_profile:
        items.append(f"profile: {result.gateway_profile}")
    if state in {"fallback", "disabled"}:
        items.append(f"理由: {_llm_factor_fallback_reason_label(result.fallback_reason)}")
    if state == "live":
        items.append(f"生成: {_llm_factor_datetime_display(result.generated_at)}")
    return f"<p>{html.escape(' / '.join(items))}</p>"


def _llm_factor_runtime_state(result: LLMFactorResult) -> str:
    if result.fallback_reason == "disabled":
        return "disabled"
    if result.gateway_status == "fallback" or result.fallback_reason:
        return "fallback"
    if result.provider == "deterministic":
        return "fallback"
    if result.model_name == LLM_FACTOR_FAKE_MODEL_NAME and not result.provider:
        return "disabled"
    if result.provider:
        return "live"
    return "disabled"


def _llm_factor_runtime_state_label(state: str) -> str:
    return {
        "live": "live生成を利用",
        "fallback": "ローカル参考表示へ切替",
        "disabled": "live生成は無効",
    }.get(state, "状態未確認")


def _llm_factor_fallback_reason_label(reason: str | None) -> str:
    if not reason:
        return "未確認"
    labels = {
        "disabled": "設定で無効",
        "gateway_unavailable": "LLM Gatewayに接続できません",
        "gateway_timeout": "LLM Gatewayタイムアウト",
        "gateway_http_error": "LLM Gateway HTTPエラー",
        "malformed_json": "JSON形式エラー",
        "validation_error": "応答検証エラー",
        "wrong_symbol": "銘柄不一致",
        "unknown_evidence": "未提供の出典ID",
        "stale_source": "古い、または未来日付の出典",
        "cache_miss": "cache未取得",
        "cache_corrupt": "cache読込失敗",
        "provider_error": "LLM providerエラー",
        "insufficient_evidence": "対象銘柄に紐づく根拠が不足",
    }
    return f"{labels.get(reason, '応答検証エラー')} ({reason})"


def _llm_factor_items_html(
    factors: Sequence[Any],
    *,
    empty_text: str,
) -> str:
    if not factors:
        return f"<p>{html.escape(empty_text)}</p>"
    items = "".join(
        "<li>"
        f"<strong>{html.escape(factor.title)}</strong>"
        f" <span>{html.escape(_llm_factor_score_display(factor.score))}</span>"
        f"<br><small>{html.escape(factor.reason)}</small>"
        f"<br><small>出典日: {html.escape(factor.source_date.isoformat())}</small>"
        "</li>"
        for factor in factors[:3]
    )
    return f"<ul>{items}</ul>"


def _cockpit_interpretation_panel_html(result: CockpitInterpretationResult) -> str:
    warnings = "".join(f"<li>{html.escape(warning)}</li>" for warning in result.warnings)
    warning_html = f"<ul>{warnings}</ul>" if warnings else "<p>特記事項なし</p>"
    missing_html = ""
    if result.missing_fields:
        missing_html = f"<p>不足項目: {html.escape('、'.join(result.missing_fields))}</p>"
    return (
        '<section class="research-result-brief hero">'
        '<div class="research-result-brief-header">'
        '<span class="research-evidence-pill positive">参考表示</span>'
        '<span class="research-evidence-pill">確認メモ</span>'
        "</div>"
        "<h4>AI解釈メモ</h4>"
        f"<p>{html.escape(result.overall_reading)}</p>"
        "<p>このAI解釈メモは、価格・予測・根拠資料・AI材料分析を読み解くための参考情報です。"
        "SMAIの表示は売買を推奨するものではなく、Ranking・予測・Investment Scoreには反映していません。</p>"
        '<div class="research-brief-reading-grid">'
        '<section class="research-brief-reading-item tone-positive">'
        "<h5>強材料</h5>"
        f"{_interpretation_bullets_html(result.positive_points, empty_text='強材料として整理できる材料はまだ少なめです。')}"
        "</section>"
        '<section class="research-brief-reading-item tone-warning">'
        "<h5>注意材料</h5>"
        f"{_interpretation_bullets_html(result.caution_points, empty_text='注意材料として整理できる材料はまだ少なめです。')}"
        "</section>"
        '<section class="research-brief-reading-item tone-warning">'
        "<h5>矛盾・不確実性</h5>"
        f"{_interpretation_bullets_html([*result.contradictions, *result.uncertainties], empty_text='目立つ矛盾や不確実性はまだ少なめです。')}"
        "</section>"
        '<section class="research-brief-reading-item tone-neutral">'
        "<h5>次に確認すべき材料</h5>"
        f"{_interpretation_bullets_html(result.next_checks, empty_text='次に確認すべき材料は、価格・予測・根拠資料から順に確認してください。')}"
        "</section>"
        '<section class="research-brief-reading-item tone-warning">'
        "<h5>確認メモ</h5>"
        f"{warning_html}"
        f"{missing_html}"
        "</section>"
        "</div>"
        "</section>"
    )


def _interpretation_bullets_html(
    bullets: Sequence[InterpretationBullet],
    *,
    empty_text: str,
) -> str:
    if not bullets:
        return f"<p>{html.escape(empty_text)}</p>"
    items = "".join(
        "<li>"
        f"<strong>{html.escape(bullet.title)}</strong>"
        f"<br><small>{html.escape(bullet.summary)}</small>"
        f"<br><small>参考度: {html.escape(_interpretation_confidence_display(bullet.confidence))}</small>"
        "</li>"
        for bullet in bullets[:4]
    )
    return f"<ul>{items}</ul>"


def _cockpit_interpretation_status_label(result: CockpitInterpretationResult) -> str:
    return f"LLM接続: {result.status.replace('_', ' ')}"


def _cockpit_interpretation_runtime_html(result: CockpitInterpretationResult) -> str:
    items: list[str] = [f"状態: {_cockpit_interpretation_status_display(result.status)}"]
    if result.provider:
        items.append(f"provider: {result.provider}")
    if result.model:
        items.append(f"model: {result.model}")
    if result.gateway_profile:
        items.append(f"profile: {result.gateway_profile}")
    if result.generated_at:
        items.append(f"生成: {_llm_factor_datetime_display(result.generated_at)}")
    if result.fallback_reason:
        items.append(
            f"理由: {_cockpit_interpretation_fallback_reason_label(result.fallback_reason)}"
        )
    return f"<p>{html.escape(' / '.join(items))}</p>"


def _cockpit_interpretation_status_display(status: str) -> str:
    return {
        "live": "live生成を利用",
        "fallback": "ローカル参考表示へ切替",
        "disabled": "live生成は無効",
        "validation_error": "検証エラーのため簡易表示",
    }.get(status, "状態未確認")


def _cockpit_interpretation_fallback_reason_label(reason: str) -> str:
    labels = {
        "disabled": "設定で無効",
        "gateway_unavailable": "LLM Gatewayに接続できません",
        "gateway_timeout": "LLM Gatewayタイムアウト",
        "gateway_http_error": "LLM Gateway HTTPエラー",
        "malformed_json": "JSON形式エラー",
        "validation_error": "応答検証エラー",
        "wrong_symbol": "銘柄不一致",
        "unknown_evidence": "未提供の出典ID",
        "policy_violation": "売買推奨などの禁止表現",
        "cache_miss": "cache未取得",
        "cache_corrupt": "cache読込失敗",
        "provider_error": "LLM providerエラー",
    }
    return f"{labels.get(reason, '応答検証エラー')} ({reason})"


def _interpretation_confidence_display(value: float) -> str:
    if value >= 0.7:
        return "高め"
    if value >= 0.45:
        return "中程度"
    return "控えめ"


def _cockpit_interpretation_cache_caption(cache: Any) -> str:
    status_label = {
        "hit": "cache利用",
        "miss": "新規生成",
        "disabled": "live生成無効",
        "invalid": "cacheまたは応答検証エラー",
    }.get(getattr(cache, "status", ""), "cache状態未確認")
    generated_at = _llm_factor_datetime_display(getattr(cache, "generated_at", None))
    expires_at = _llm_factor_datetime_display(getattr(cache, "expires_at", None))
    model = getattr(cache, "model", None) or "fallback"
    source_hash = str(getattr(cache, "context_hash", "") or "")
    return (
        f"{status_label} / 生成: {generated_at} / 有効期限: {expires_at} / "
        f"model: {model} / source: {source_hash[:8] or '未確認'}"
    )


def _llm_factor_score_display(score: Decimal) -> str:
    return f"{int(score.to_integral_value())}/100"


def _llm_factor_score_note(label: str, score: Decimal) -> str:
    if label == "確信度":
        if score < Decimal("35"):
            return "出典が少ないため低信頼です。"
        if score < Decimal("75"):
            return "参考材料として確認します。"
        return "複数の根拠を確認しています。一次開示も本文で確認します。"
    if score >= Decimal("70"):
        return "強めに確認したい材料です。"
    if score >= Decimal("45"):
        return "中立からやや注目の材料です。"
    return "現時点では控えめに読みます。"


def _llm_factor_confidence_tone(result: LLMFactorResult) -> str:
    if result.llm_confidence_score < Decimal("35"):
        return "warning"
    if result.llm_confidence_score >= Decimal("75"):
        return "positive"
    return "info"


def _llm_factor_evidence_display_rows(result: LLMFactorResult) -> list[dict[str, str]]:
    return [
        {
            "出典": source.title,
            "種別": _research_source_type_label(source.source_type),
            "日付": source.source_date.isoformat(),
            "取得元": source.provider or "",
            "URL": source.source_url,
        }
        for source in result.evidence_sources
    ]


def _llm_factor_evidence_selection_display(result: LLMFactorResult) -> str:
    selection = result.evidence_selection
    input_count = max(selection.input_count, len(result.evidence_sources))
    retained_count = max(selection.retained_count, len(result.evidence_sources))
    items = [f"根拠候補 {input_count}件", f"採用 {retained_count}件"]
    if selection.duplicate_count:
        items.append(f"重複除外 {selection.duplicate_count}件")
    if selection.unrelated_count:
        items.append(f"対象外除外 {selection.unrelated_count}件")
    if selection.fallback_used:
        items.append("ローカル参考表示")
    return " / ".join(items)


def _llm_factor_cache_caption(cache: LLMFactorCacheMetadata) -> str:
    status_label = {
        "hit": "cache利用",
        "miss": "新規生成",
        "expired": "期限切れのため再生成",
        "invalid": "cache読込失敗のため再生成",
    }.get(cache.status, "cache状態未確認")
    generated_at = _llm_factor_datetime_display(cache.generated_at)
    expires_at = _llm_factor_datetime_display(cache.expires_at)
    return (
        f"{status_label} / 生成: {generated_at} / 有効期限: {expires_at} / "
        f"model: {cache.model_name} / prompt: {cache.prompt_version} / "
        f"source: {cache.source_hash[:8]}"
    )


def _llm_factor_datetime_display(value: datetime | None) -> str:
    if value is None:
        return "未確認"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _fetch_external_research_for_preview(
    preview: MarketDataPreview,
) -> ExternalResearchFetchResult:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        raise AppError("AI調査の対象銘柄が選択されていません。")
    result = _fetch_external_research_for_symbol(
        symbol,
        as_of=_date_from_iso_text(_market_data_as_of(preview)),
    )
    st.session_state[MARKET_DATA_EXTERNAL_RESEARCH_FETCH_STATE_KEY] = result
    return result


def _fetch_external_research_for_symbol(
    symbol: str,
    *,
    as_of: date | None,
) -> ExternalResearchFetchResult:
    company_name = symbol_name(symbol) or None
    related_keywords = [company_name] if company_name else []
    return fetch_external_research_for_symbol(
        symbol,
        company_name=company_name,
        related_keywords=related_keywords,
        as_of=as_of,
        allow_network=True,
    )


def _cockpit_external_research_fetch_result_from_state(
    preview: MarketDataPreview,
) -> ExternalResearchFetchResult | None:
    result = st.session_state.get(MARKET_DATA_EXTERNAL_RESEARCH_FETCH_STATE_KEY)
    if not isinstance(result, ExternalResearchFetchResult):
        return None
    if result.symbol.strip().upper() != _market_data_preview_symbol(preview).strip().upper():
        return None
    return result


def _external_research_fetch_failure_caption(_exc: AppError) -> str:
    return (
        "外部取得元に接続できなかったため、保存済み資料と既存データだけで要約しました。"
        "必要に応じてネットワーク設定、銘柄コード、外部取得元の状態を確認してください。"
    )


def _external_research_fetch_summary_rows(
    result: ExternalResearchFetchResult,
) -> list[dict[str, str]]:
    warnings = " / ".join(result.warnings) if result.warnings else "なし"
    rows = [
        {"項目": "取得元", "内容": result.provider},
        {"項目": "取得日時", "内容": _datetime_display_text(result.fetched_at)},
        {"項目": "登録資料数", "内容": f"{len(result.entries)}件"},
        {"項目": "取得元別状況", "内容": _external_research_provider_status_summary(result)},
        {
            "項目": "保持方針",
            "内容": "このセッションのみ" if result.retention_policy == "session" else "保存済み",
        },
        {"項目": "注意", "内容": warnings},
    ]
    for status in result.provider_statuses:
        status_label = _external_research_status_label(status.status)
        provider_status_detail = (
            f"{status_label} / {status.result_count}件 / " f"{status.elapsed_ms / 1000:.1f}秒"
        )
        if status.error_message_short and status.status in {"failed", "timeout"}:
            provider_status_detail = f"{provider_status_detail} / {status.error_message_short}"
        rows.append(
            {
                "項目": _external_research_provider_label(status.provider),
                "内容": provider_status_detail,
            }
        )
    return rows


def _external_research_fetch_overview_html(result: ExternalResearchFetchResult) -> str:
    latest_dates = [entry.published_at for entry in result.entries if entry.published_at]
    latest_text = max(latest_dates).isoformat() if latest_dates else "未確認"
    official_source_types = {
        "annual_report",
        "earnings_report",
        "earnings_presentation",
        "medium_term_plan",
        "integrated_report",
        "company_ir",
        "tdnet",
    }
    official_count = sum(
        1 for entry in result.entries if entry.source_type in official_source_types
    )
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
    status_markup = _external_research_provider_status_chips_html(result)
    warning_markup = ""
    if result.warnings:
        warning_items = "".join(
            f"<li>{html.escape(warning)}</li>" for warning in result.warnings[:3]
        )
        warning_markup = (
            '<div class="research-result-status-warning">' f"<ul>{warning_items}</ul>" "</div>"
        )
    return (
        '<section class="research-result-brief">'
        '<div class="research-result-brief-title">外部参照ソースの確認メモ</div>'
        f'<div class="research-result-brief-summary">{html.escape(summary)}</div>'
        f'<div class="research-result-brief-grid">{item_markup}</div>'
        f"{status_markup}"
        f"{warning_markup}"
        "</section>"
    )


def _external_research_provider_status_summary(
    result: ExternalResearchFetchResult,
) -> str:
    if not result.provider_statuses:
        return f"{len(result.entries)}件取得"
    parts = [f"{len(result.entries)}件取得"]
    for status in result.provider_statuses:
        label = _external_research_provider_label(status.provider)
        if status.status == "success":
            parts.append(f"{label} {status.result_count}")
        elif status.status == "no_result":
            parts.append(f"{label} 0")
        else:
            parts.append(f"{label} {_external_research_status_label(status.status)}")
    return " / ".join(parts)


def _external_research_provider_status_chips_html(
    result: ExternalResearchFetchResult,
) -> str:
    if not result.provider_statuses:
        return ""
    chips: list[str] = [
        (
            '<span class="research-provider-status-chip success">'
            f"{html.escape(str(len(result.entries)))}件取得</span>"
        )
    ]
    for status in result.provider_statuses:
        label = _external_research_provider_label(status.provider)
        status_text = (
            f"{status.result_count}件"
            if status.status == "success"
            else _external_research_status_label(status.status)
        )
        chips.append(
            f'<span class="research-provider-status-chip {html.escape(status.status)}">'
            f"{html.escape(label)} {html.escape(status_text)}</span>"
        )
    return f'<div class="research-provider-status-list">{"".join(chips)}</div>'


def _external_research_status_label(status: str) -> str:
    return {
        "success": "取得",
        "no_result": "0件",
        "timeout": "時間切れ",
        "failed": "失敗",
        "skipped": "未実行",
        "cache_hit": "再利用",
    }.get(status, status or "未確認")


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


def _render_news_source_links_panel(
    summary_items: Sequence[NewsSummaryItem],
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
    security_type: SecurityResearchType = "domestic_stock",
) -> None:
    if not summary_items and news_report is None and external_research_result is None:
        return
    rows = _news_source_link_rows(
        summary_items,
        news_report=news_report,
        external_research_result=external_research_result,
        security_type=security_type,
    )
    all_rows = _news_source_link_rows(
        summary_items,
        news_report=news_report,
        external_research_result=external_research_result,
        security_type=security_type,
        limit=None,
    )
    total_url_count = len(all_rows)
    news_url_count = sum(1 for row in all_rows if row["source_kind"] == "news")
    with st.expander(
        _news_source_links_expander_label(total_url_count),
        expanded=_news_source_links_expander_expanded(total_url_count),
    ):
        st.caption(
            "サマリ本文の補足として、確認元のURLだけを控えめに表示します。"
            "本文や詳細な根拠はリンク先と下部の外部参照ソースで確認します。"
        )
        st.markdown(
            _news_source_links_panel_html(
                rows,
                total_url_count=total_url_count,
                news_url_count=news_url_count,
            ),
            unsafe_allow_html=True,
        )


def _news_source_links_expander_label(total_url_count: int) -> str:
    if total_url_count <= 0:
        return "ニュース・開示の出典を表示（URL付き0件）"
    return f"ニュース・開示の出典を表示（URL付き{total_url_count}件）"


def _news_source_links_expander_expanded(total_url_count: int) -> bool:
    _ = total_url_count
    return False


def _news_source_link_rows(
    summary_items: Sequence[NewsSummaryItem],
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
    security_type: SecurityResearchType = "domestic_stock",
    limit: int | None = 5,
) -> list[dict[str, str]]:
    candidates: list[tuple[int, int, dict[str, str]]] = []
    seen_urls: set[str] = set()

    def add_row(row: dict[str, str]) -> None:
        url = row["url"]
        normalized_url = url.strip().lower()
        if normalized_url in seen_urls:
            return
        seen_urls.add(normalized_url)
        candidates.append(
            (
                _news_source_priority(row["source_kind"]),
                len(candidates),
                row,
            )
        )

    for item in summary_items:
        url = _displayable_source_url(item.source_url)
        if not url:
            continue
        source_type = _news_summary_item_source_type(item)
        source_kind = _news_source_kind(source_type, item.source_title)
        date_label, date_text = _news_source_date_text(item.published_at, None)
        add_row(
            {
                "source_kind": source_kind,
                "source_label": _news_source_display_label(source_type, item.source_title),
                "provider": _latest_topic_source_label(item, security_type=security_type),
                "date_label": date_label,
                "date_text": date_text,
                "freshness": _information_status_label(item.information_status),
                "title": item.title,
                "summary": _research_brief_ui_text(item.summary, max_chars=180),
                "url": url,
                "link_label": _news_source_link_label(source_kind),
            }
        )

    if news_report is not None:
        for news in news_report.news:
            url = _displayable_source_url(news.url)
            if not url:
                continue
            date_label, date_text = _news_source_date_text(news.published_at, None)
            add_row(
                {
                    "source_kind": "news",
                    "source_label": "ニュース",
                    "provider": news.source or "ニュース",
                    "date_label": date_label,
                    "date_text": date_text,
                    "freshness": _research_freshness_status_label(news.freshness_status),
                    "title": news.title,
                    "summary": _research_brief_ui_text(news.summary, max_chars=180),
                    "url": url,
                    "link_label": _news_source_link_label("news"),
                }
            )

    if external_research_result is not None:
        for entry in external_research_result.entries:
            url = _displayable_source_url(entry.source_url)
            if not url:
                continue
            source_kind = _news_source_kind(entry.source_type, entry.provider)
            date_label, date_text = _news_source_date_text(entry.published_at, entry.fetched_at)
            add_row(
                {
                    "source_kind": source_kind,
                    "source_label": _news_source_display_label(entry.source_type, entry.provider),
                    "provider": _external_research_provider_label(entry.provider),
                    "date_label": date_label,
                    "date_text": date_text,
                    "freshness": _research_freshness_status_label(entry.freshness_status),
                    "title": entry.title,
                    "summary": _research_brief_ui_text(
                        _external_research_entry_summary_display_text(entry),
                        max_chars=180,
                    ),
                    "url": url,
                    "link_label": _news_source_link_label(source_kind),
                }
            )

    candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
    rows = [row for _, _, row in candidates]
    return rows if limit is None else rows[:limit]


def _news_source_links_panel_html(
    rows: Sequence[dict[str, str]],
    *,
    total_url_count: int,
    news_url_count: int,
) -> str:
    if not rows:
        return (
            '<section class="news-source-citation-panel">'
            '<div class="news-source-citation-header">'
            '<div class="news-source-citation-title">ニュース・開示の出典</div>'
            '<div class="news-source-citation-count">URL 0件</div>'
            "</div>"
            '<div class="news-source-citation-note">'
            "ニュース専用のURL付き根拠は見つかりませんでした。"
            "関連する公式開示・企業IR・provider情報は外部参照ソースも確認してください。"
            "</div>"
            "</section>"
        )

    if news_url_count:
        notice = (
            "URL付きのニュース・開示を簡易表示します。"
            "取得本文は表示せず、リンク先で公開日や本文を確認してください。"
        )
    else:
        notice = (
            "ニュース専用のURL付き根拠は見つかりませんでした。"
            "外部参照ソースにURL付きの公式資料・provider情報があります。"
        )
    items = "".join(_news_source_link_item_html(row) for row in rows)
    more = ""
    if total_url_count > len(rows):
        more = (
            '<div class="news-source-citation-more">'
            f"ほか {total_url_count - len(rows)}件は下部の外部参照ソースで確認できます。"
            "</div>"
        )
    return (
        '<section class="news-source-citation-panel">'
        '<div class="news-source-citation-header">'
        '<div class="news-source-citation-title">ニュース・開示の出典</div>'
        f'<div class="news-source-citation-count">URL {total_url_count}件</div>'
        "</div>"
        f'<div class="news-source-citation-note">{html.escape(notice)}</div>'
        f'<div class="news-source-citation-list">{items}</div>'
        f"{more}"
        "</section>"
    )


def _news_source_link_item_html(row: dict[str, str]) -> str:
    freshness = f"鮮度 {row['freshness']}" if row["freshness"] else ""
    meta_parts = [
        row["source_label"],
        row["provider"],
        f"{row['date_label']} {row['date_text']}",
        freshness,
    ]
    meta_markup = "".join(
        f"<span>{html.escape(part)}</span>" for part in meta_parts if part.strip()
    )
    return (
        '<a class="news-source-citation-item" '
        f'href="{html.escape(row["url"], quote=True)}" target="_blank" rel="noopener noreferrer" '
        f'aria-label="{html.escape(row["title"], quote=True)}">'
        '<div class="news-source-citation-main">'
        f'<div class="news-source-citation-title-line">{html.escape(row["title"])}</div>'
        f'<div class="news-source-citation-meta">{meta_markup}</div>'
        "</div>"
        f'<span class="news-source-citation-action">{html.escape(row["link_label"])} ↗</span>'
        "</a>"
    )


def _displayable_source_url(source_url: str | None) -> str:
    url = str(source_url or "").strip()
    if not url:
        return ""
    if url.lower() in {"nan", "none", "null"}:
        return ""
    if not url.lower().startswith(("http://", "https://")):
        return ""
    return url


def _news_summary_item_source_type(item: NewsSummaryItem) -> str:
    topic_type = getattr(item, "topic_type", "news")
    if topic_type in {
        "tdnet",
        "ir_disclosure",
        "earnings",
        "forecast_revision",
        "shareholder_return",
    }:
        return "tdnet"
    return "news"


def _news_source_kind(source_type: str, provider: str | None = None) -> str:
    source_type_key = str(source_type or "").strip().lower()
    provider_key = str(provider or "").strip().lower()
    if source_type_key in {"news", "external_news"}:
        return "news"
    if source_type_key == "tdnet" or provider_key == "tdnet":
        return "tdnet"
    if source_type_key == "company_ir" or provider_key == "company_ir_site":
        return "company_ir"
    if source_type_key in {"edinet", "annual_report"} or provider_key == "edinet":
        return "edinet"
    if source_type_key in {"yahoo_finance", "provider_profile"} or provider_key == "yahoo_finance":
        return "yahoo_finance"
    return "other"


def _news_source_display_label(source_type: str, provider: str | None = None) -> str:
    source_kind = _news_source_kind(source_type, provider)
    labels = {
        "news": "ニュース",
        "tdnet": "TDnet適時開示",
        "company_ir": "企業IRサイト",
        "edinet": "EDINET",
        "yahoo_finance": "Yahoo Finance",
        "other": "外部参照ソース",
    }
    return labels[source_kind]


def _news_source_priority(source_kind: str) -> int:
    priorities = {
        "news": 0,
        "tdnet": 1,
        "company_ir": 2,
        "edinet": 3,
        "yahoo_finance": 4,
        "other": 5,
    }
    return priorities.get(source_kind, priorities["other"])


def _news_source_link_label(source_kind: str) -> str:
    if source_kind == "news":
        return "元記事を見る"
    if source_kind == "tdnet":
        return "TDnetで見る"
    if source_kind == "company_ir":
        return "企業IRで見る"
    if source_kind == "edinet":
        return "EDINETで見る"
    if source_kind == "yahoo_finance":
        return "Yahoo Financeで見る"
    return "出典を開く"


def _news_source_feed_kind(source_kind: str) -> str:
    if source_kind == "news":
        return "news"
    if source_kind in {"tdnet", "company_ir", "edinet"}:
        return "disclosure"
    return "other"


def _news_source_date_text(
    published_at: date | None,
    fetched_at: datetime | None,
) -> tuple[str, str]:
    if published_at is not None:
        return "公開日", published_at.isoformat()
    if fetched_at is not None:
        return "取得日", _datetime_display_text(fetched_at)
    return "日付", "未確認"


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
        "edinet": "EDINET",
        "tdnet": "TDnet（適時開示）",
        "company_ir_site": "企業IRサイト",
        "google_news_rss": "Google News",
        "yahoo_finance": "Yahoo Finance",
        "edinet_tdnet_yahoo_finance": "EDINET / TDnet / Yahoo Finance",
        "edinet_tdnet_company_ir_yahoo_finance": ("EDINET / TDnet / 企業IR / Yahoo Finance"),
        "edinet_tdnet_company_ir_google_news_yahoo_finance": (
            "EDINET / TDnet / 企業IR / Google News / Yahoo Finance"
        ),
        "tdnet_yahoo_finance": "TDnet / Yahoo Finance",
    }
    return labels.get(provider, provider)


def _external_research_entry_check_note(entry: ExternalResearchFetchManifestEntry) -> str:
    if entry.source_type == "annual_report":
        return "EDINETなどの公式開示です。対象期間、提出会社、本文の該当箇所を確認してください。"
    if entry.source_type == "tdnet":
        return "公式開示です。PDF本文で対象期間、数値、会社発表の前提を確認してください。"
    if entry.source_type == "company_ir":
        return "企業公式IRサイトです。掲載資料の公開日、PDF本文、対象期間を確認してください。"
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
    external_result: ExternalResearchFetchResult | None = None,
) -> bool:
    symbol = _market_data_preview_symbol(preview)
    status_chips = _research_operation_status_chips(report, news_report, external_result)
    status_chips_html = "".join(
        f'<span class="research-ai-state-chip">{html.escape(label)}: '
        f"{html.escape(value)}</span>"
        for label, value in status_chips
    )
    title, summary, materials_html = _research_operation_card_content(
        report,
        news_report,
        external_result,
    )
    with st.container(border=True):
        st.markdown(
            (
                '<div class="research-ai-cta research-ai-cta--hero">'
                f'<div class="research-ai-cta-title">{html.escape(title)}</div>'
                f'<div class="research-ai-cta-copy">{html.escape(summary)}</div>'
                f"{materials_html}"
                '<div class="research-ai-state-row">'
                f"{status_chips_html}"
                '<span class="research-ai-state-chip">次に見る: 決算 / 株主還元 / リスク材料</span>'
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        return st.button(
            RESEARCH_FETCH_BUTTON_LABEL if report is None else "AI調査を更新",
            key=f"research_ai_fetch_{symbol}",
            help="ニュース・IR・開示・外部データをまとめて確認します。",
            type="primary",
            use_container_width=True,
        )


def _research_operation_card_content(
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
    external_result: ExternalResearchFetchResult | None = None,
) -> tuple[str, str, str]:
    if report is None:
        return (
            "AI調査はまだ未取得です",
            "ニュース、IR、開示、保存済み資料を確認し、注目材料と注意材料を整理します。",
            "",
        )

    brief = ResearchBriefBuilder().build(report, news_report=news_report)
    status = dict(_research_operation_status_chips(report, news_report, external_result))
    if external_result is not None:
        summary = (
            f"重複なしの根拠候補{status['根拠候補']}（公式{status['公式']} / "
            f"ニュース{status['ニュース']} / 外部プロファイル{status['外部プロファイル']}）を確認"
        )
    else:
        summary = (
            f"ニュース{status['ニュース']} / IR・開示{status['IR/開示']} / "
            f"外部データ{status['外部データ']}を確認"
        )
    positive = [
        _research_brief_ui_text(item.summary, max_chars=88) for item in brief.positive_materials[:3]
    ] or [_research_brief_ui_text(item, max_chars=88) for item in brief.positive_candidates[:3]]
    caution = [
        _research_brief_ui_text(item.summary, max_chars=88) for item in brief.caution_materials[:3]
    ] or [_research_brief_ui_text(item, max_chars=88) for item in brief.caution_candidates[:3]]
    materials_html = "".join(
        _research_operation_material_list_html(label, items)
        for label, items in (("注目材料", positive), ("注意材料", caution))
        if items
    )
    return "AI調査結果", summary, materials_html


def _research_operation_material_list_html(label: str, items: list[str]) -> str:
    list_html = "".join(f"<li>{html.escape(item)}</li>" for item in items)
    return (
        '<div class="research-ai-materials">'
        f'<div class="research-ai-materials-title">{html.escape(label)}</div>'
        f"<ul>{list_html}</ul>"
        "</div>"
    )


def _research_operation_status_chips(
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
    external_result: ExternalResearchFetchResult | None = None,
) -> list[tuple[str, str]]:
    if external_result is not None:
        official_source_types = {
            "annual_report",
            "earnings_report",
            "earnings_presentation",
            "medium_term_plan",
            "integrated_report",
            "company_ir",
            "tdnet",
        }
        official_count = sum(
            1 for entry in external_result.entries if entry.source_type in official_source_types
        )
        news_count = sum(1 for entry in external_result.entries if entry.source_type == "news")
        profile_count = sum(
            1 for entry in external_result.entries if entry.source_type == "provider_profile"
        )
        return [
            ("レポート", "作成済み" if report is not None else "未取得"),
            ("根拠候補", f"{len(external_result.entries)}件"),
            ("公式", f"{official_count}件"),
            ("ニュース", f"{news_count}件"),
            ("外部プロファイル", f"{profile_count}件"),
            ("最終取得", _datetime_display_text(external_result.fetched_at)),
        ]
    source_types = {
        evidence.source_type.strip().lower()
        for evidence in (report.evidence if report is not None else [])
    }
    ir_source_types = {
        "annual_report",
        "earnings_report",
        "financial_results",
        "tdnet",
        "company_ir",
    }
    ir_count = sum(
        1
        for evidence in (report.evidence if report is not None else [])
        if evidence.source_type.strip().lower() in ir_source_types
    )
    external_data_count = sum(
        1
        for evidence in (report.evidence if report is not None else [])
        if evidence.source_type.strip().lower() == "provider_profile"
    )
    return [
        ("レポート", "作成済み" if report is not None else "未取得"),
        ("ニュース", f"{len(news_report.news) if news_report is not None else 0}件"),
        ("IR/開示", f"{ir_count}件" if source_types & ir_source_types else "未確認"),
        (
            "外部データ",
            f"{external_data_count}件" if external_data_count else "未確認",
        ),
    ]


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
                "next_step": "確認方針: IR・開示・外部データを合わせて確認します。",
            }
        return {
            "title": "AI調査で確認すること",
            "summary": (
                "まだ企業リサーチレポートは整理されていません。"
                "AI調査を更新すると、外部情報・ニュース・保存済み資料を企業理解の材料に変換します。"
            ),
            "source_summary": "確認済み: 未取得",
            "next_step": "確認方針: 外部情報・ニュース・保存済み資料を根拠資料として整理します。",
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
        as_of = date.today()
        loading_slot = st.empty()
        with loading_slot.container():
            render_mascot_loading(
                "report",
                title="AI調査を整理中",
                message=(
                    "外部参照ソース、ニュース、保存済み資料を読み込み、"
                    "企業リサーチレポートにまとめています。"
                ),
                tone="info",
            )
        loading_headlines, loading_headline_note = workflow_loading_headlines_from_cache()
        if hasattr(loading_slot, "markdown"):
            loading_slot.markdown(
                workflow_loading_html(
                    title="AI調査データを取得中",
                    message="外部情報と保存済み資料を、根拠付きの企業リサーチメモに整理しています。",
                    current_step="外部参照ソースを確認しています。",
                    progress=0.18,
                    mode="inline",
                    headlines=loading_headlines,
                    headline_note=loading_headline_note,
                ),
                unsafe_allow_html=True,
            )
        try:
            try:
                external_result = _fetch_external_research_for_symbol(
                    symbol,
                    as_of=as_of,
                )
                _store_ranking_external_research_result(external_result)
                if external_result.entries:
                    st.success(
                        f"外部参照ソース {len(external_result.entries)}件をAI調査に反映しました。"
                    )
                for warning in external_result.warnings:
                    st.warning(warning)
            except AppError as exc:
                st.warning(
                    "外部参照ソースを取得できませんでした。保存済み資料と既存データでAI調査を続行します。"
                )
                st.caption(_external_research_fetch_failure_caption(exc))
            if hasattr(loading_slot, "markdown"):
                loading_slot.markdown(
                    workflow_loading_html(
                        title="AI調査データを取得中",
                        message=(
                            "外部情報と保存済み資料を、根拠付きの企業リサーチメモに整理しています。"
                        ),
                        current_step="企業リサーチメモを生成しています。",
                        progress=0.72,
                        mode="inline",
                        headlines=loading_headlines,
                        headline_note=loading_headline_note,
                    ),
                    unsafe_allow_html=True,
                )
            fetched_report = _build_research_report_for_symbol(
                symbol,
                as_of=as_of,
            )
            _store_ranking_research_report(fetched_report)
            stock_news_report = _build_stock_news_report_for_symbol(
                symbol,
                as_of=as_of,
            )
            _store_ranking_stock_news_report(stock_news_report)
        finally:
            loading_slot.empty()

    report = _ranking_research_report_from_state(symbol)
    if report is None:
        st.info("資料確認は未実行です。必要な場合は「AIで資料を確認」を押してください。")
        return
    _render_research_summary_panel(
        report,
        detail_expanded=False,
        news_report=_ranking_stock_news_report_from_state(symbol),
        external_research_result=_ranking_external_research_result_from_state(symbol),
        display_context="ranking",
    )


def _render_research_summary_panel(
    report: CompanyResearchReport,
    *,
    detail_expanded: bool,
    news_report: StockNewsReport | None = None,
    external_research_result: ExternalResearchFetchResult | None = None,
    display_context: Literal["cockpit", "ranking"] = "cockpit",
) -> None:
    summary_bundle = _research_summary_bundle(
        report,
        news_report=news_report,
        external_research_result=external_research_result,
    )
    company_summary = summary_bundle.company_summary
    etf_summary = summary_bundle.etf_summary
    question_summary = summary_bundle.question_summary
    security_type = summary_bundle.security_type
    research_score = summary_bundle.research_score
    if external_research_result is not None:
        st.markdown(
            _external_research_fetch_overview_html(external_research_result),
            unsafe_allow_html=True,
        )
    if security_type in {"etf", "fund"} and etf_summary is not None:
        _render_etf_research_summary_panel(etf_summary)
        _render_etf_metric_summary_panel(etf_summary)
        _render_etf_holdings_panel(etf_summary)
        _render_etf_distribution_cost_panel(etf_summary)
        _render_news_summary_panel(etf_summary.news_items, security_type=security_type)
        _render_investment_hint_news_panel(news_report)
        _render_news_source_links_panel(
            etf_summary.news_items,
            news_report=news_report,
            external_research_result=external_research_result,
            security_type=security_type,
        )
        _render_etf_question_summary_panel(etf_summary)
    elif company_summary is not None and question_summary is not None:
        _render_company_research_summary_panel(
            company_summary,
            security_type=security_type,
        )
        _render_quantitative_summary_panel(company_summary.quantitative)
        _render_ir_summary_panel(company_summary.ir_items, security_type=security_type)
        _render_news_summary_panel(company_summary.news_items, security_type=security_type)
        _render_investment_hint_news_panel(news_report)
        _render_news_source_links_panel(
            company_summary.news_items,
            news_report=news_report,
            external_research_result=external_research_result,
            security_type=security_type,
        )
        _render_investment_question_summary_panel(
            question_summary,
            security_type=security_type,
            include_secondary=False,
        )

    has_external_source_urls = _external_research_result_has_displayable_source_urls(
        external_research_result
    )
    if news_report is not None and news_report.warnings:
        for warning in news_report.warnings:
            warning_text = _research_news_warning_display_text(
                warning,
                has_external_source_urls=has_external_source_urls,
            )
            if _is_research_news_url_gap_warning(warning):
                st.info(warning_text)
            else:
                st.warning(warning_text)

    retrieval_caption = _research_retrieval_quality_caption(report)
    if retrieval_caption:
        st.caption(retrieval_caption)

    score_rows = _research_score_summary_rows(research_score)
    with st.expander(RESEARCH_ADVANCED_DETAIL_EXPANDER_LABEL, expanded=detail_expanded):
        st.caption(
            "通常は上のサマリと確認ポイントを先に確認します。"
            "ここでは通常画面と用途が重ならないスコア内訳、検索品質、抽出データ、取得トレースを確認できます。"
        )

        if score_rows:
            st.markdown(f"###### {_research_score_expander_label(display_context)}")
            st.caption(_research_score_context_caption(display_context))
            st.caption("低い値は銘柄評価ではなく、根拠確認不足のサインとして扱います。")
            _render_compact_dataframe(_research_score_guidance_rows(display_context))
            st.markdown("###### Research Score要約")
            _render_compact_dataframe(score_rows)
            research_score_component_rows = _research_score_component_rows(research_score)
            if research_score_component_rows:
                st.markdown("###### 観点別の内訳")
                st.caption(
                    "どの観点の根拠が薄いかを見て、次に確認するIR・開示・ニュースを決めます。"
                )
                _render_compact_dataframe(research_score_component_rows)
            score_warning_rows = _research_score_warning_rows(research_score)
            if score_warning_rows:
                st.markdown("###### 注意点")
                _render_compact_dataframe(score_warning_rows)
            st.divider()

        st.markdown(f"###### {RESEARCH_DETAIL_EXPANDER_LABEL}")
        if report.data_quality.status == "OK":
            st.caption("通常画面と重複するサマリを除き、検証用の行データだけを表示します。")
        else:
            st.caption("登録資料または検索できた根拠が少ないため、詳細は確認材料として扱います。")
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
        claim_rows = _research_extracted_claim_rows(report)
        if claim_rows:
            st.markdown("###### 抽出した主張")
            _render_compact_dataframe(claim_rows)
        evidence_detail_rows = _research_evidence_detail_rows(report)
        if evidence_detail_rows:
            st.markdown("###### 根拠資料の詳細")
            _render_compact_dataframe(evidence_detail_rows)
        if external_research_result is not None:
            st.markdown("###### 外部参照ソース取得状況")
            _render_compact_dataframe(
                _external_research_fetch_summary_rows(external_research_result)
            )


def _is_research_news_url_gap_warning(warning: str) -> bool:
    return (
        "URL付きのニュース根拠" in warning
        or "source_type=news" in warning
        or "source URL がない" in warning
        or "source URL is missing" in warning
    )


def _research_news_warning_display_text(
    warning: str,
    *,
    has_external_source_urls: bool = False,
) -> str:
    if _is_research_news_url_gap_warning(warning):
        if has_external_source_urls:
            return (
                "ニュース専用のURL付き根拠は見つかりませんでしたが、"
                "公式資料・企業IR・provider情報のURLは上の「ニュース・開示の出典」"
                "または外部参照ソースで確認できます。"
            )
        return (
            "ニュース専用のURL付き根拠は見つかりませんでした。"
            "関連する公式開示・企業IR・provider情報は外部参照ソースも確認してください。"
        )
    return warning


def _external_research_result_has_displayable_source_urls(
    external_research_result: ExternalResearchFetchResult | None,
) -> bool:
    if external_research_result is None:
        return False
    return any(
        _displayable_source_url(entry.source_url) for entry in external_research_result.entries
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


def _render_investment_hint_news_panel(news_report: StockNewsReport | None) -> None:
    html_text = _investment_hint_news_panel_html(news_report)
    if html_text:
        st.markdown(html_text, unsafe_allow_html=True)


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
    item_count_label = f"{len(items)}件" if items else "未取得"
    if not items:
        missing_text = (
            "ニュース・開示は取得できていません。必要に応じて外部ニュース、公式IR、SEC Filingを追加確認してください。"
            if security_type == "foreign_stock"
            else "ニュース・適時開示は取得できていません。必要に応じて外部ニュースや公式IRを追加確認してください。"
        )
        body = (
            '<article class="news-feed-item other market-news-item featured">'
            '<div class="market-news-main">'
            f'<div class="news-item-summary market-news-summary">{html.escape(missing_text)}</div>'
            "</div>"
            "</article>"
        )
    else:
        body = "".join(
            _news_summary_item_html(index, item, security_type=security_type)
            for index, item in enumerate(items, 1)
        )
    return (
        '<section class="market-intelligence-panel" aria-label="ニュース・開示インテリジェンス">'
        '<div class="market-intelligence-header">'
        "<div>"
        '<div class="market-intelligence-kicker">Market Intelligence</div>'
        f'<div class="market-intelligence-title">{html.escape(RESEARCH_NEWS_SUMMARY_TITLE)}</div>'
        '<div class="market-intelligence-subtitle">'
        "外部ニュース、IR、開示をニュースフィードとして整理します。"
        "気になる項目はカードから元資料を確認してください。"
        "</div>"
        "</div>"
        f'<div class="market-intelligence-count">{html.escape(item_count_label)}</div>'
        "</div>"
        f'<div class="research-news-summary-list news-feed-list market-news-grid">{body}</div>'
        "</section>"
    )


def _investment_hint_news_panel_html(
    news_report: StockNewsReport | None,
    *,
    limit: int = 3,
) -> str:
    all_rows = _investment_hint_news_rows(news_report, limit=None)
    rows = all_rows[:limit]
    if not rows:
        return ""
    cards = "".join(_investment_hint_news_card_html(row) for row in rows)
    more = ""
    total_count = len(all_rows)
    if total_count > len(rows):
        more = (
            '<div class="research-brief-focus-more">'
            f"ほか {total_count - len(rows)}件は下部の外部参照ソースまたは詳細データで確認できます。"
            "</div>"
        )
    return (
        '<section class="market-intelligence-panel spotlight" aria-label="注目材料 Top 3">'
        '<div class="market-intelligence-header">'
        "<div>"
        '<div class="market-intelligence-kicker">Market Intelligence</div>'
        '<div class="market-intelligence-title">注目材料 Top 3</div>'
        '<div class="market-intelligence-subtitle">'
        "投資ヒントとなるニュースを外部ニュースの見出しだけで整理します。"
        "気になるカードをクリックして、本文と一次情報を確認してください。"
        "</div>"
        "</div>"
        f'<div class="market-intelligence-count">{len(rows)}件</div>'
        "</div>"
        f'<div class="research-news-headline-list news-feed-list news-feed-top-list">{cards}</div>'
        f"{more}"
        "</section>"
    )


def _investment_hint_news_rows(
    news_report: StockNewsReport | None,
    *,
    limit: int | None = 3,
) -> list[dict[str, str]]:
    if news_report is None or not news_report.news:
        return []
    rows: list[dict[str, str]] = []
    for news in news_report.news:
        url = _displayable_source_url(news.url)
        if not url:
            continue
        rows.append(
            {
                "sentiment": _stock_news_sentiment_label(news.sentiment_for_investment),
                "category": _stock_news_viewpoint_label(news.investment_viewpoint),
                "title": news.title,
                "summary": _research_brief_ui_text(news.summary, max_chars=140),
                "source": news.source or "ニュース",
                "published_at": news.published_at.isoformat() if news.published_at else "未確認",
                "freshness": _research_freshness_status_label(news.freshness_status),
                "url": url,
            }
        )
    return rows if limit is None else rows[:limit]


def _investment_hint_news_card_html(row: dict[str, str]) -> str:
    sentiment = row.get("sentiment", "中立材料")
    tone = _research_sentiment_css_class(sentiment)
    feed_kind = _investment_hint_news_feed_kind(sentiment, row.get("category", ""))
    url = row.get("url", "")
    title = row.get("title", "ニュース")
    published_at = row.get("published_at", "未確認")
    freshness = row.get("freshness", "未確認")
    source = row.get("source", "ニュース")
    summary = row.get("summary", "")
    return (
        f'<a class="research-news-headline-card news-feed-item news-feed-item-clickable {feed_kind} '
        'market-news-item top-material-card" '
        f'href="{html.escape(url, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer" aria-label="{html.escape(title, quote=True)}">'
        '<div class="market-news-main">'
        '<div class="research-news-headline-top news-item-top">'
        '<span class="research-news-headline-chip news-item-badge primary">AI注目</span>'
        '<span class="research-news-headline-chip news-item-badge">外部ニュース</span>'
        f'<span class="research-news-headline-chip news-item-badge {tone}">{html.escape(sentiment)}</span>'
        f'<span class="research-news-headline-chip news-item-badge">{html.escape(row.get("category", "ニュース材料"))}</span>'
        "</div>"
        f'<div class="research-news-headline-title news-item-title market-news-title">{html.escape(title)}</div>'
        '<div class="research-news-headline-meta news-item-meta market-news-meta">'
        f"<span>公開日 <strong>{html.escape(published_at)}</strong></span>"
        f"<span>鮮度 <strong>{html.escape(freshness)}</strong></span>"
        f"<span>出典 <strong>{html.escape(source)}</strong></span>"
        "</div>"
        f'<div class="research-news-headline-summary news-item-summary market-news-summary">{html.escape(summary)}</div>'
        "</div>"
        '<div class="market-news-aside">'
        '<span class="market-news-kind">優先確認</span>'
        f'<span class="market-news-date">公開日 {html.escape(published_at)}</span>'
        f'<span class="market-news-date">{html.escape(freshness)}</span>'
        '<span class="research-news-headline-action news-source-link market-news-link">元記事を見る ↗</span>'
        "</div>"
        "</a>"
    )


def _investment_hint_news_feed_kind(sentiment: str, category: str) -> str:
    text = f"{sentiment} {category}"
    if "リスク" in text or "ネガティブ" in text:
        return "risk"
    if "ポジティブ" in text or "成長" in text or "業績" in text or "株主還元" in text:
        return "important"
    return "news"


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
    status_text = _news_summary_short_status(item, security_type=security_type)
    url = _displayable_source_url(item.source_url)
    action_label = _news_summary_action_label(item, security_type=security_type)
    feed_kind = _news_summary_feed_kind(item)
    featured_class = " featured" if index == 1 else ""
    content = (
        '<div class="market-news-main">'
        '<div class="research-news-headline-top news-item-top">'
        f'<span class="research-news-headline-chip news-item-badge primary">{html.escape(topic_type)} {index}</span>'
        f'<span class="research-news-headline-chip news-item-badge">{html.escape(impact)}</span>'
        f'<span class="research-news-headline-chip news-item-badge">{html.escape(status_text)}</span>'
        "</div>"
        f'<div class="research-news-headline-title news-item-title market-news-title">{html.escape(item.title)}</div>'
        '<div class="research-news-headline-meta news-item-meta market-news-meta">'
        f"<span>公開日 <strong>{html.escape(published)}</strong></span>"
        f"<span>出典 <strong>{html.escape(source)}</strong></span>"
        "</div>"
        f'<div class="research-news-headline-summary news-item-summary market-news-summary">{html.escape(_research_brief_ui_text(item.summary, max_chars=140))}</div>'
        "</div>"
    )
    if url:
        return (
            f'<a class="research-news-summary-card news-feed-item news-feed-item-clickable {feed_kind} '
            f'market-news-item{featured_class}" '
            f'href="{html.escape(url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer" aria-label="{html.escape(item.title, quote=True)}">'
            f"{content}"
            '<div class="market-news-aside">'
            f'<span class="market-news-kind">{html.escape(topic_type)}</span>'
            f'<span class="market-news-date">{html.escape(published)}</span>'
            f'<span class="research-news-headline-action news-source-link market-news-link">{html.escape(action_label)} ↗</span>'
            "</div>"
            "</a>"
        )
    return (
        f'<article class="research-news-summary-card news-feed-item {feed_kind} '
        f'market-news-item{featured_class}">{content}'
        '<div class="market-news-aside">'
        f'<span class="market-news-kind">{html.escape(topic_type)}</span>'
        f'<span class="market-news-date">{html.escape(published)}</span>'
        '<span class="news-source-link market-news-link">URL未取得</span>'
        "</div>"
        "</article>"
    )


def _news_summary_feed_kind(item: NewsSummaryItem) -> str:
    topic_type = str(getattr(item, "topic_type", "news") or "news").lower()
    impact_hint = str(getattr(item, "impact_hint", "") or "").lower()
    text = f"{item.title} {item.summary}".lower()
    if "risk" in impact_hint or "リスク" in text or "警戒" in text:
        return "risk"
    if topic_type in {"tdnet", "ir_disclosure"}:
        return "disclosure"
    if topic_type in {"earnings", "forecast_revision", "shareholder_return"}:
        return "important"
    if "重要" in text or "業績" in text or "上方修正" in text or "増配" in text:
        return "important"
    if topic_type in {"business_reorganization", "product", "governance"}:
        return "ir"
    if topic_type == "news":
        return "news"
    return "other"


def _news_summary_short_status(
    item: NewsSummaryItem,
    *,
    security_type: SecurityResearchType,
) -> str:
    if not getattr(item, "official_confirmation_required", True):
        return "公式確認済み"
    status = getattr(item, "information_status", "unverified")
    if status == "unparsed":
        return "本文未解析"
    if security_type == "foreign_stock":
        return "公式IR/SEC確認"
    return "公式確認が必要"


def _news_summary_action_label(
    item: NewsSummaryItem,
    *,
    security_type: SecurityResearchType,
) -> str:
    topic_type = getattr(item, "topic_type", "news")
    if security_type == "foreign_stock" and topic_type in {
        "tdnet",
        "ir_disclosure",
        "earnings",
        "forecast_revision",
        "shareholder_return",
    }:
        return "資料を開く"
    if topic_type in {
        "tdnet",
        "ir_disclosure",
        "earnings",
        "forecast_revision",
        "shareholder_return",
    }:
        return "TDnetで見る"
    return "元記事を見る"


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
        "found": "関連候補あり",
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
    include_secondary: bool = True,
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
    secondary_answers = _investment_question_secondary_answers(summary)
    if include_secondary and secondary_answers:
        with st.expander(RESEARCH_INVESTMENT_QUESTION_MORE_LABEL, expanded=False):
            st.markdown(
                _investment_question_answers_html(secondary_answers, security_type=security_type),
                unsafe_allow_html=True,
            )


def _investment_question_secondary_answers(
    summary: InvestmentQuestionSummary,
) -> list[InvestmentQuestionAnswer]:
    primary_answer_ids = {id(answer) for answer in _investment_question_primary_answers(summary)}
    return [
        answer for answer in getattr(summary, "answers", []) if id(answer) not in primary_answer_ids
    ]


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
    return _build_research_report_for_symbol(
        symbol,
        as_of=_date_from_iso_text(_market_data_as_of(preview)),
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
    return _build_stock_news_report_for_symbol(
        symbol,
        as_of=_date_from_iso_text(_market_data_as_of(preview)),
    )


def _build_research_report_for_symbol(
    symbol: str,
    *,
    as_of: date | None,
) -> CompanyResearchReport:
    return analyze_research_for_symbol(symbol, as_of=as_of)


def _build_stock_news_report_for_symbol(
    symbol: str,
    *,
    as_of: date | None,
) -> StockNewsReport:
    company_name = symbol_name(symbol) or None
    related_keywords = [company_name] if company_name else []
    return analyze_stock_news_for_symbol(
        symbol,
        company_name=company_name,
        related_keywords=related_keywords,
        as_of=as_of,
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


def _ranking_stock_news_report_from_state(symbol: str) -> StockNewsReport | None:
    reports = st.session_state.get(MARKET_DATA_RANKING_STOCK_NEWS_REPORTS_STATE_KEY)
    if not isinstance(reports, dict):
        return None
    report = reports.get(symbol.strip().upper())
    if not isinstance(report, StockNewsReport):
        return None
    return report


def _store_ranking_stock_news_report(report: StockNewsReport) -> None:
    reports = st.session_state.get(MARKET_DATA_RANKING_STOCK_NEWS_REPORTS_STATE_KEY)
    if not isinstance(reports, dict):
        reports = {}
        st.session_state[MARKET_DATA_RANKING_STOCK_NEWS_REPORTS_STATE_KEY] = reports
    reports[report.symbol.strip().upper()] = report


def _ranking_external_research_result_from_state(
    symbol: str,
) -> ExternalResearchFetchResult | None:
    results = st.session_state.get(MARKET_DATA_RANKING_EXTERNAL_RESEARCH_RESULTS_STATE_KEY)
    if not isinstance(results, dict):
        return None
    result = results.get(symbol.strip().upper())
    if not isinstance(result, ExternalResearchFetchResult):
        return None
    return result


def _store_ranking_external_research_result(result: ExternalResearchFetchResult) -> None:
    results = st.session_state.get(MARKET_DATA_RANKING_EXTERNAL_RESEARCH_RESULTS_STATE_KEY)
    if not isinstance(results, dict):
        results = {}
        st.session_state[MARKET_DATA_RANKING_EXTERNAL_RESEARCH_RESULTS_STATE_KEY] = results
    results[result.symbol.strip().upper()] = result


def _render_market_data_cockpit_header(
    preview: MarketDataPreview,
    symbol_label: str,
) -> int:
    _ = symbol_label
    horizon_days = int(getattr(preview, "forecast_horizon_days", 0) or 0)
    if horizon_days < 1:
        horizon_days = determine_forecast_horizon(
            start=preview.bars[0].ts.date(),
            end=preview.bars[-1].ts.date(),
            bars=preview.bars,
        ).horizon_days
    st.session_state[MARKET_DATA_FORECAST_DAYS_STATE_KEY] = horizon_days
    return horizon_days


def _render_price_forecast_hero(
    preview: MarketDataPreview,
    symbol_label: str,
    forecast_rows: list[dict[str, str]],
    consensus_rows: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
    advanced_forecast_rows: list[dict[str, str]],
    advanced_forecast_consensus_rows: list[dict[str, str]],
    *,
    forecast_horizon_days: int,
) -> None:
    st.subheader("02 価格・AI予測")
    horizon_summary = str(getattr(preview, "forecast_horizon_summary", "") or "").strip()
    st.caption(
        f"予測期間: {forecast_horizon_days}営業日相当（取得履歴から自動計算）"
        + (f" / {horizon_summary}" if horizon_summary else "")
    )
    for warning in getattr(preview, "forecast_horizon_warnings", []):
        st.warning(str(warning))
    chart_currency = str(preview.bars[0].symbol.currency if preview.bars else "").upper()
    _render_advanced_forecast_status(advanced_forecast_rows, horizon_days=forecast_horizon_days)
    _render_advanced_forecast_consensus_cards(advanced_forecast_consensus_rows)
    _register_cockpit_forecast_assistant_context(
        symbol_label,
        advanced_forecast_consensus_rows,
        forecast_horizon_days=forecast_horizon_days,
    )
    selected_chart_series = _render_forecast_chart_filters(forecast_rows)
    display_forecast_rows = filter_forecast_chart_rows(forecast_rows, selected_chart_series)
    display_currency = _render_market_chart_currency_selector(chart_currency, preview.fx_rows)
    display_forecast_rows = convert_market_chart_rows_currency(
        display_forecast_rows,
        source_currency=chart_currency,
        display_currency=display_currency,
        usd_jpy_rate=chart_fx_rate_from_rows(preview.fx_rows, source_currency=chart_currency),
    )
    _render_market_chart(
        display_forecast_rows,
        currency=display_currency,
        title="",
        color_series_labels=forecast_chart_series_labels(forecast_rows),
        legend_series_labels=forecast_chart_series_labels(display_forecast_rows),
    )
    latest_close = preview.bars[-1].close if preview.bars else None
    latest_date = preview.bars[-1].ts.date() if preview.bars else None
    _render_forecast_model_detail_expanders(
        metric_rows,
        advanced_forecast_rows,
        advanced_forecast_consensus_rows,
        latest_close=latest_close,
        latest_date=latest_date,
    )


def forecast_horizon_notice_text(horizon_days: int) -> str:
    return (
        f"今回の予測期間: {horizon_days}日。"
        "取得期間から自動計算され、短い取得期間では短期寄り、長い取得期間では中期寄りの見方になります。"
    )


def _render_forecast_model_detail_expanders(
    metric_rows: list[dict[str, str]],
    advanced_forecast_rows: list[dict[str, str]],
    advanced_forecast_consensus_rows: list[dict[str, str]],
    *,
    latest_close: Decimal | None,
    latest_date: date | None,
) -> None:
    advanced_model_cards = forecast_model_card_rows(
        metric_rows,
        advanced_forecast_rows,
        latest_close=latest_close,
        latest_date=latest_date,
        include_standard_models=False,
    )
    if advanced_model_cards:
        st.markdown("##### 高度予測モデル")
        st.caption(
            "個別モデルの見方です。AI予測インサイトの内訳として、方向やレンジの割れ方を確認します。"
        )
        _render_forecast_model_comparison_cards(
            forecast_model_comparison_rows(advanced_model_cards)
        )
        st.markdown(forecast_model_cards_html(advanced_model_cards), unsafe_allow_html=True)
    with st.expander("高度予測モデルの詳細を見る", expanded=False):
        st.caption(
            "モデル別の予測変化率、検証指標、特徴量メモです。"
            "カードで気になった点を表で分解して確認します。"
        )
        _render_table(
            advanced_forecast_display_rows(advanced_forecast_rows),
            "高度予測を表示するには、もう少し長い価格データが必要です。",
        )
    with st.expander("検証指標を見る", expanded=False):
        st.caption(
            "初期表示から外した検証指標です。数値は将来精度の保証ではなく、予測の読み方を補助します。"
        )
        _render_table(
            advanced_forecast_validation_detail_rows(advanced_forecast_consensus_rows),
            "検証指標を表示できるAI予測インサイトがありません。",
        )
    with st.expander("単純予測との比較を見る", expanded=False):
        st.caption(
            "単純予測は基準・保険です。高度予測との差が小さい場合は、AI予測を強く読みすぎないよう確認します。"
        )
        _render_table(
            simple_forecast_baseline_comparison_rows(
                metric_rows,
                advanced_forecast_consensus_rows,
            ),
            "比較に使える予測検証データがありません。",
        )


def simple_forecast_baseline_comparison_rows(
    metric_rows: list[dict[str, str]],
    advanced_forecast_consensus_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if advanced_forecast_consensus_rows:
        consensus = advanced_forecast_consensus_rows[0]
        rows.append(
            {
                "区分": ADVANCED_FORECAST_CONSENSUS_LABEL,
                "予測変化": _signed_percent_from_text(consensus.get("predicted_return", ""))
                or "未計算",
                "RMSE": consensus.get("mean_rmse", "") or "未計算",
                "方向一致率": consensus.get("mean_direction_accuracy", "") or "未計算",
                "検証メモ": _advanced_forecast_validation_summary(consensus),
            }
        )
    for row in metric_rows:
        model = row.get("model", "")
        if model == "naive" or model.startswith(("moving_average_", "momentum_")):
            rows.append(
                {
                    "区分": _forecast_series_label(model),
                    "予測変化": "-",
                    "RMSE": row.get("rmse", "") or "未計算",
                    "方向一致率": row.get("direction_accuracy", "") or "未計算",
                    "検証メモ": "基準モデルです。高度予測の参考度を確認するために残しています。",
                }
            )
    return rows


def advanced_forecast_validation_detail_rows(
    advanced_forecast_consensus_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not advanced_forecast_consensus_rows:
        return []
    row = advanced_forecast_consensus_rows[0]
    return [
        {
            "項目": "過去検証の方向一致率",
            "値": row.get("mean_direction_accuracy", "") or "未計算",
            "読み方": "過去の評価サンプルで上下方向が合った割合です。将来保証ではありません。",
        },
        {
            "項目": "平均RMSE",
            "値": row.get("mean_rmse", "") or "未計算",
            "読み方": "価格予測の平均的な誤差です。小さいほど過去検証では安定しています。",
        },
        {
            "項目": "誤差改善",
            "値": _advanced_forecast_error_improvement_display(row),
            "読み方": "単純基準と比べた誤差改善の大きさです。詳細確認用の数値です。",
        },
        {
            "項目": "相対的に安定",
            "値": _advanced_forecast_best_model_display(row) or "未計算",
            "読み方": "今回の高度予測モデル群の中で相対的に誤差が小さいモデルです。",
        },
        {
            "項目": "注意点",
            "値": _advanced_forecast_warning_display(row.get("warnings", "")) or "特記事項なし",
            "読み方": "低信頼やモデル間の見方の差がある場合に確認します。",
        },
    ]


def _advanced_forecast_validation_summary(row: Mapping[str, str]) -> str:
    improvement = _decimal_from_text(row.get("mean_rmse_improvement"))
    confidence = _advanced_forecast_confidence_label(row.get("confidence", ""))
    if improvement is None:
        return f"信頼度は{confidence}です。単純予測との差は詳細指標と合わせて確認します。"
    if improvement > 0:
        return f"過去検証では単純なゼロリターン基準より改善傾向です。信頼度は{confidence}です。"
    if improvement < 0:
        return f"過去検証では単純基準を上回らない場面があります。信頼度は{confidence}です。"
    return f"単純基準との差は小さめです。信頼度は{confidence}です。"


def _render_advanced_forecast_status(
    rows: list[dict[str, str]],
    *,
    horizon_days: int,
) -> None:
    if rows:
        return
    st.warning(
        f"高度予測は{horizon_days}日先で再計算を試みましたが、現在の取得データでは表示できません。"
        "期間を少し長くするか、取得データを更新すると表示される場合があります。"
    )


def _render_advanced_forecast_consensus_cards(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    st.markdown(
        _advanced_forecast_insight_card_html(rows[0]),
        unsafe_allow_html=True,
    )


def _advanced_forecast_insight_summary(row: Mapping[str, str]) -> dict[str, object]:
    conclusion = _advanced_forecast_conclusion_label(row)
    agreement_count = _advanced_forecast_model_agreement_display(row)
    dispersion = _advanced_forecast_dispersion_label(row)
    range_display = _advanced_forecast_range_display(row) or "未計算"
    reasons = _advanced_forecast_reason_lines(row, conclusion=conclusion, dispersion=dispersion)
    caution = _advanced_forecast_caution_text(row, dispersion=dispersion)
    return {
        "conclusion": conclusion,
        "agreement_count": agreement_count,
        "dispersion": dispersion,
        "range_display": range_display,
        "reasons": reasons,
        "caution": caution,
    }


def _advanced_forecast_conclusion_label(row: Mapping[str, str]) -> str:
    predicted_return = _decimal_from_text(row.get("direction_predicted_return"))
    if predicted_return is None:
        predicted_return = _decimal_from_text(row.get("predicted_return"))
    confidence = str(row.get("confidence", "")).strip()
    dispersion = _advanced_forecast_dispersion_label(row)
    if predicted_return is None:
        return "判断材料不足"
    if confidence == "low" or dispersion == "大きめ":
        if predicted_return > Decimal("1"):
            return "上昇寄りだが、信頼度は低め"
        if predicted_return < Decimal("-1"):
            return "下振れ警戒。短期変動に注意"
        return "中立寄り。予測レンジが広く判断保留"
    if predicted_return > Decimal("5"):
        return "強い上昇寄り"
    if predicted_return > Decimal("1"):
        return "やや上昇寄り。モデル方向はおおむね一致"
    if predicted_return < Decimal("-1"):
        return "下振れ警戒"
    return "中立寄り"


def _advanced_forecast_model_agreement_count(row: Mapping[str, str]) -> str:
    model_count = _int_from_text(row.get("model_count", ""))
    agreement_score = _decimal_from_text(row.get("direction_agreement_score"))
    if model_count <= 0 or agreement_score is None:
        return _forecast_agreement_label(row.get("agreement", ""))
    agreed = int((agreement_score * Decimal(model_count) / Decimal("100")).to_integral_value())
    agreed = max(0, min(model_count, agreed))
    return f"{agreed}/{model_count}"


def _advanced_forecast_model_agreement_display(row: Mapping[str, str]) -> str:
    model_count = _int_from_text(row.get("model_count", ""))
    agreement_score = _decimal_from_text(row.get("direction_agreement_score"))
    if model_count <= 0 or agreement_score is None:
        return _forecast_agreement_label(row.get("agreement", "")) or "未計算"
    agreed = int((agreement_score * Decimal(model_count) / Decimal("100")).to_integral_value())
    agreed = max(0, min(model_count, agreed))
    predicted_return = _decimal_from_text(row.get("direction_predicted_return"))
    if predicted_return is None:
        predicted_return = _decimal_from_text(row.get("predicted_return"))
    if predicted_return is None or abs(predicted_return) < Decimal("0.5"):
        direction_label = "中立寄り"
    elif predicted_return > 0:
        direction_label = "上昇寄り"
    else:
        direction_label = "下振れ寄り"
    return f"{model_count}モデル中{agreed}モデルが{direction_label}"


def _advanced_forecast_selection_display(row: Mapping[str, str]) -> str:
    band_labels = {"short": "短期", "medium": "中期", "long": "長期・監査外"}
    mode_labels = {
        "validated_consensus": "検証通過モデルを統合",
        "quantile_anchor": "レンジモデル中心",
        "best_available_fallback": "単一モデルへ縮退",
        "range_first_long_horizon": "レンジ優先",
    }
    band = band_labels.get(str(row.get("horizon_band", "")).strip(), "期間判定未取得")
    mode = mode_labels.get(str(row.get("selection_mode", "")).strip(), "選択結果未取得")
    center_models = str(row.get("center_models", "")).strip()
    center_count = len([name for name in center_models.split(",") if name.strip()])
    return f"{band} / {mode}" + (f"（中心{center_count}モデル）" if center_count else "")


def _advanced_forecast_dispersion_label(row: Mapping[str, str]) -> str:
    lower = _decimal_from_text(row.get("predicted_return_lower"))
    upper = _decimal_from_text(row.get("predicted_return_upper"))
    if lower is None or upper is None:
        return _forecast_agreement_label(row.get("agreement", "")) or "未計算"
    spread = upper - lower
    if spread < Decimal("5"):
        return "コンパクト"
    if spread < Decimal("10"):
        return "やや広い"
    return "大きめ"


def _advanced_forecast_reason_lines(
    row: Mapping[str, str],
    *,
    conclusion: str,
    dispersion: str,
) -> list[str]:
    agreement_count = _advanced_forecast_model_agreement_display(row)
    confidence = _advanced_forecast_confidence_label(row.get("confidence", ""))
    lines = [
        f"複数の高度予測モデルを統合した結論は「{conclusion}」です。",
        f"モデル合意度は {agreement_count}、信頼度は{confidence}です。",
    ]
    selection_reason = str(row.get("selection_reason", "")).strip()
    if selection_reason:
        lines.append(selection_reason)
    if dispersion in {"やや広い", "大きめ"}:
        lines.append(f"予測ばらつきは{dispersion}で、過信せず確認します。")
    improvement = _decimal_from_text(row.get("mean_rmse_improvement"))
    if improvement is not None:
        if improvement > 0:
            lines.append("過去検証では単純基準より改善傾向があります。")
        elif improvement < 0:
            lines.append("過去検証では単純基準を上回らないモデルもあります。")
    return lines


def _advanced_forecast_caution_text(row: Mapping[str, str], *, dispersion: str) -> str:
    warning_text = _advanced_forecast_warning_display(row.get("warnings", ""))
    if dispersion == "大きめ":
        return "予測レンジが広いため、強い方向表示としては読みすぎないでください。"
    if warning_text:
        return warning_text
    return FORECAST_DECISION_SUPPORT_NOTE


def _advanced_forecast_confidence_reason(row: Mapping[str, str], *, dispersion: str) -> str:
    confidence = str(row.get("confidence", "")).strip()
    improvement = _decimal_from_text(row.get("mean_rmse_improvement"))
    agreement_score = _decimal_from_text(row.get("direction_agreement_score"))
    if confidence == "low":
        if dispersion == "大きめ":
            return "信頼度低め: 予測レンジが広く、不確実性が高めです。"
        return "信頼度低め: 検証データまたはモデル間の見方に注意が必要です。"
    if confidence == "high":
        if (
            agreement_score is not None
            and agreement_score >= Decimal("75")
            and (improvement is None or improvement >= 0)
        ):
            return "信頼度高め: モデル方向がそろい、過去検証でも改善傾向があります。"
        return "信頼度高め: 予測材料は比較的そろっています。"
    if improvement is not None and improvement <= 0:
        return "信頼度中: モデル方向は確認できますが、誤差改善は限定的です。"
    return "信頼度中: モデル方向はおおむね一致していますが、レンジも合わせて確認します。"


def _advanced_forecast_price_range_display(row: Mapping[str, str]) -> str:
    lower = str(row.get("forecast_close_lower", "")).strip()
    upper = str(row.get("forecast_close_upper", "")).strip()
    if lower and upper:
        return f"{lower}〜{upper}"
    return ""


def _advanced_forecast_error_improvement_display(row: Mapping[str, str]) -> str:
    improvement = _decimal_from_text(row.get("mean_rmse_improvement"))
    if improvement is None:
        return "未計算"
    magnitude = abs(improvement)
    if magnitude < Decimal("0.01"):
        label = "小"
    elif magnitude < Decimal("0.05"):
        label = "中"
    else:
        label = "大"
    if improvement < 0:
        label = f"{label}（悪化）"
    return f"{label} / RMSE改善値 {row.get('mean_rmse_improvement', '')}"


def _advanced_forecast_insight_card_html(row: Mapping[str, str]) -> str:
    summary = _advanced_forecast_insight_summary(row)
    value = _signed_percent_from_text(row.get("predicted_return", "")) or "未計算"
    range_display = str(summary["range_display"])
    confidence = _advanced_forecast_confidence_label(row.get("confidence", ""))
    center_confidence = _advanced_forecast_confidence_label(
        row.get("center_confidence", row.get("confidence", ""))
    )
    direction_confidence = _advanced_forecast_confidence_label(
        row.get("direction_confidence", row.get("confidence", ""))
    )
    horizon = row.get("horizon_days", "").strip()
    progress = metric_progress_from_value(row.get("weighted_direction_score", "")) or 0
    safe_progress = min(100, max(0, int(progress)))
    tone = _advanced_forecast_card_tone(dict(row))
    conclusion = str(summary["conclusion"])
    agreement_count = str(summary["agreement_count"])
    dispersion = str(summary["dispersion"])
    confidence_reason = _advanced_forecast_confidence_reason(row, dispersion=dispersion)
    reason_items = "".join(
        f"<li>{html.escape(reason)}</li>" for reason in cast(list[str], summary["reasons"])
    )
    caution = str(summary["caution"])
    lower = _signed_percent_from_text(row.get("predicted_return_lower", "")) or "未計算"
    upper = _signed_percent_from_text(row.get("predicted_return_upper", "")) or "未計算"
    price_range = _advanced_forecast_price_range_display(row) or "未計算"
    help_text = _advanced_forecast_consensus_help_text(row) + (
        f"モデル合意度 {agreement_count}、予測ばらつき {dispersion}。"
        "AI総合と方向シグナルでは、信頼度を見ながら控えめに使います。"
    )
    metrics = (
        ("中心予測の信頼度", center_confidence),
        ("方向判定の信頼度", direction_confidence),
        ("モデル合意度", agreement_count),
        ("予測ばらつき", dispersion),
        ("予測期間", f"{horizon}日" if horizon else "未計算"),
        ("モデル選択", _advanced_forecast_selection_display(row)),
    )
    metric_html = "".join(
        '<div class="smai-insight-mini-field">'
        f'<span class="smai-insight-mini-label">{html.escape(label)}</span>'
        f'<strong class="smai-insight-mini-value" title="{html.escape(value, quote=True)}">'
        f"{html.escape(value)}</strong>"
        "</div>"
        for label, value in metrics
    )
    badge_row = "".join(
        (
            badge_html(ADVANCED_FORECAST_CONSENSUS_LABEL, "info"),
            badge_html(f"信頼度 {confidence}", _advanced_forecast_confidence_tone(dict(row))),
            badge_html(f"予測期間 {horizon}日" if horizon else "予測期間 未計算", "neutral"),
            badge_html(_advanced_forecast_selection_display(row), "neutral"),
        )
    )
    return (
        '<div class="smai-metric-card" '
        f'data-tone="{html.escape(tone)}" data-emphasis="strong">'
        '<div class="smai-card-label-row">'
        f'<div class="smai-card-label">{html.escape(ADVANCED_FORECAST_CONSENSUS_LABEL)}</div>'
        '<span class="smai-card-help" '
        f'title="{html.escape(help_text, quote=True)}" '
        f'aria-label="{html.escape(ADVANCED_FORECAST_CONSENSUS_LABEL, quote=True)} の説明">?</span>'
        "</div>"
        '<div class="smai-insight-hero">'
        "<div>"
        '<div class="smai-insight-kicker">結論</div>'
        f'<div class="smai-insight-result">{html.escape(conclusion)}</div>'
        "</div>"
        "</div>"
        '<div class="smai-insight-center-forecast" '
        'title="複数の高度予測モデルを統合した中心的な見通しです。将来の値動きを保証するものではありません。">'
        "<span>中心予測</span>"
        f"<strong>{html.escape(value)}</strong>"
        "<small>高度予測モデルの統合結果</small>"
        "</div>"
        f'<div class="smai-insight-range" aria-label="予測レンジ {html.escape(range_display, quote=True)}">'
        '<div data-case="downside" '
        'title="過去のばらつきやモデル差を考慮した慎重側の見方です。">'
        f"<span>下振れ予測</span><strong>{html.escape(lower)}</strong></div>"
        '<div data-case="upside" '
        'title="モデル上の上方向シナリオです。実現を保証するものではありません。">'
        f"<span>上振れ予測</span><strong>{html.escape(upper)}</strong></div>"
        "</div>"
        '<div class="smai-insight-price-row">'
        f'<div><span>予測価格</span><strong>{html.escape(row.get("forecast_close") or "未計算")}</strong></div>'
        f"<div><span>予測レンジ</span><strong>{html.escape(price_range)}</strong></div>"
        "</div>"
        '<div class="smai-score-track" aria-hidden="true">'
        f'<div class="smai-score-fill" style="--smai-score-width: {safe_progress}%"></div>'
        "</div>"
        f'<div class="smai-insight-mini-grid">{metric_html}</div>'
        f'<div style="color:{THEME_COLORS["text_secondary"]};font-size:0.84rem;'
        'font-weight:760;line-height:1.45;margin-top:0.55rem;">'
        f"{html.escape(confidence_reason)}</div>"
        '<div class="smai-insight-two-col">'
        '<div><div class="smai-insight-subtitle">主な理由</div>'
        f"<ul>{reason_items}</ul></div>"
        '<div><div class="smai-insight-subtitle">注意点</div>'
        f"<p>{html.escape(caution)}</p></div>"
        "</div>"
        f'<div class="smai-badge-row" style="margin-top:0.55rem;">{badge_row}</div>'
        "</div>"
    )


def _render_advanced_forecast_cards(rows: list[dict[str, str]]) -> None:
    cards = advanced_forecast_card_rows(rows)
    if not cards:
        return
    columns = st.columns(min(2, len(cards)))
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            render_metric_card(
                card["label"],
                card["value"],
                caption=card["caption"],
                help_text=card["help"],
                badges=tuple(card["badges"]),
                tone=card["tone"],
                emphasis="strong",
                progress=metric_progress_from_value(card["progress"]),
            )


def _render_forecast_chart_filters(rows: list[dict[str, str]]) -> set[str]:
    options = forecast_chart_series_options(rows)
    if not options:
        return set()
    selected_series = default_forecast_chart_series(options)
    advanced_series = [
        str(option["series"]) for option in options if option.get("kind") == "advanced"
    ]
    simple_series = [
        str(option["series"])
        for option in options
        if _is_simple_forecast_series(str(option["series"]))
    ]
    if not advanced_series and not simple_series:
        return selected_series
    st.markdown("#### 価格チャート / 予測スコープ")
    st.caption(
        "チェックで高度予測モデル / 単純予測モデルをまとめて追加します。"
        "データ取得や予測計算は走らず、取得済みチャートデータの表示だけを切り替えます。"
    )
    columns = st.columns(2)
    if advanced_series:
        with columns[0]:
            if st.checkbox(
                "高度予測モデル",
                value=False,
                key="market_chart_show_advanced_models",
                help="AI予測インサイトの内訳となる個別高度予測モデルをチャートへ追加します。",
            ):
                selected_series.update(advanced_series)
    if simple_series:
        with columns[1 if advanced_series else 0]:
            if st.checkbox(
                "単純予測モデル",
                value=False,
                key="market_chart_show_simple_models",
                help="直近値維持、移動平均、モメンタムなどの比較用モデルをチャートへ追加します。",
            ):
                selected_series.update(simple_series)
    return selected_series


def _render_forecast_model_comparison_cards(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    columns = st.columns(min(3, len(rows)))
    for index, row in enumerate(rows):
        with columns[index % len(columns)]:
            render_metric_card(
                row["label"],
                row["value"],
                caption=row["caption"],
                help_text=row["help"],
                badges=(badge_html("予測比較", row["tone"]),),
                tone=row["tone"],
                emphasis="normal",
            )


def forecast_horizon_label(horizon_days: str) -> str:
    if not horizon_days:
        return "予測日未設定"
    return f"{horizon_days}日先"


def forecast_horizon_display(
    horizon_days: str,
    *,
    latest_date: date | None,
) -> str:
    label = forecast_horizon_label(horizon_days)
    days = _int_from_text(horizon_days)
    if latest_date is None or days <= 0:
        return label
    forecast_date = latest_date + timedelta(days=days)
    return f"{label} ({forecast_date.strftime('%Y/%m/%d')})"


def forecast_chart_series_options(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    series_keys = dict.fromkeys(
        key
        for row in rows
        for key in row
        if key not in {"ts", "close"} and not _is_forecast_range_bound_series(key)
    )
    ordered_series = [
        series for series in series_keys if any(str(row.get(series, "")).strip() for row in rows)
    ]
    options: list[dict[str, Any]] = []
    for series in ordered_series:
        kind = forecast_chart_series_kind(series)
        options.append(
            {
                "series": series,
                "label": _forecast_series_label(series),
                "kind": kind,
                "default": _forecast_chart_series_default(series),
                "help": forecast_chart_series_help(series),
            }
        )
    return options


def forecast_chart_series_labels(rows: list[dict[str, str]]) -> list[str]:
    labels = [FORECAST_ACTUAL_LABEL]
    labels.extend(option["label"] for option in forecast_chart_series_options(rows))
    return labels


def default_forecast_chart_series(options: list[dict[str, Any]]) -> set[str]:
    return {option["series"] for option in options if option.get("default")}


def forecast_chart_runtime_series(options: list[dict[str, Any]]) -> set[str]:
    return {
        option["series"]
        for option in options
        if option.get("default")
        or option.get("kind") == "advanced"
        or _is_simple_forecast_series(option["series"])
    }


def _is_simple_forecast_series(series: str) -> bool:
    return (
        series == "naive" or series.startswith("moving_average_") or series.startswith("momentum_")
    )


def forecast_chart_series_kind(series: str) -> str:
    if series == "naive":
        return "baseline"
    if re.fullmatch(r"advanced_consensus_\d+d", series):
        return "advanced_consensus"
    if re.fullmatch(r"advanced_[a-z_]+_\d+d", series):
        return "advanced"
    return "standard"


def _forecast_chart_series_default(series: str) -> bool:
    if series == "naive":
        return False
    if series.startswith("moving_average_"):
        return False
    if series.startswith("momentum_"):
        return False
    if re.fullmatch(r"advanced_consensus_\d+d", series):
        return True
    advanced_match = re.fullmatch(r"advanced_[a-z_]+_(\d+)d", series)
    if advanced_match:
        return False
    return False


def forecast_chart_series_help(series: str) -> str:
    kind = forecast_chart_series_kind(series)
    if kind == "baseline":
        return "直近値維持です。計算式: 予測価格 = 最新終値。変化しない場合の比較基準です。"
    if kind == "advanced_consensus":
        return (
            "AI予測インサイトです。計算式: 統合予測 = "
            "Σ(各高度予測の変化率 × 重み) ÷ Σ重み。"
            "重みは信頼度・誤差改善・モデル合意度・検証数を見て0.70〜1.30に丸めます。"
        )
    if kind == "advanced":
        if series.startswith("advanced_quantile_"):
            return (
                "レンジモデルです。計算式: 過去の予測日数後リターン = "
                "(予測日数後の価格 ÷ 当日の価格) - 1。"
                "中央値を中心予測、20%点と80%点を下振れ・上振れとして見ます。"
            )
        if series.startswith("advanced_gbdt_sklearn_"):
            return (
                "ブースティングモデルです。過去の特徴量から小さな決定木を順番に足し、"
                "前の誤差を補う形で予測変化率を推定します。"
            )
        if series.startswith("advanced_tree_sklearn_"):
            return (
                "ツリーモデルです。過去の特徴量を条件分岐で似た局面に分け、"
                "その局面の予測日数後リターンから参考推定します。"
            )
        return (
            "線形モデルです。計算式イメージ: 予測変化率 = 切片 + "
            "Σ(特徴量 × 係数)。予測価格 = 最新価格 × (1 + 予測変化率)。"
        )
    return _forecast_model_logic_help(series)


def filter_forecast_chart_rows(
    rows: list[dict[str, str]],
    selected_series: set[str],
) -> list[dict[str, str]]:
    if not selected_series:
        selected_series = default_forecast_chart_series(forecast_chart_series_options(rows))
    range_series = {
        key
        for series in selected_series
        for key in (f"{series}_lower", f"{series}_upper")
        if any(str(row.get(key, "")).strip() for row in rows)
    }
    allowed = {"ts", "close", *selected_series, *range_series}
    return [{key: value for key, value in row.items() if key in allowed} for row in rows]


def forecast_model_card_rows(
    metric_rows: list[dict[str, str]],
    advanced_rows: list[dict[str, str]],
    *,
    latest_close: Decimal | None,
    latest_date: date | None = None,
    include_standard_models: bool = True,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if include_standard_models:
        for row in metric_rows:
            model = row.get("model", "")
            if model == "naive":
                continue
            forecast_close = row.get("forecast_close", "")
            forecast_return = _forecast_return_display(
                forecast_close,
                latest_close=latest_close,
            )
            cards.append(
                {
                    "model": _forecast_series_label(model),
                    "kind": "通常予測",
                    "horizon": forecast_horizon_display(
                        row.get("horizon_days", ""),
                        latest_date=latest_date,
                    ),
                    "value": forecast_return or "未計算",
                    "forecast_close": forecast_close or "未計算",
                    "sub": (
                        f"予測値 {forecast_close or '未計算'} / "
                        f"方向一致 {row.get('direction_accuracy', '') or '未計算'}"
                    ),
                    "help": _forecast_model_logic_help(model),
                    "tone": _forecast_card_tone(forecast_return),
                    "badges": (
                        badge_html("通常予測", "info"),
                        badge_html(
                            forecast_horizon_label(row.get("horizon_days", "")),
                            "neutral",
                        ),
                    ),
                }
            )
    for row in advanced_rows:
        horizon_days = row.get("horizon_days", "")
        forecast_return = _signed_percent_from_text(row.get("predicted_return", ""))
        forecast_close = row.get("forecast_close", "")
        range_display = _advanced_forecast_range_display(row)
        direction_display = _advanced_forecast_direction_display(row.get("direction_score", ""))
        confidence = _advanced_forecast_confidence_label(row.get("confidence", ""))
        cards.append(
            {
                "model": _advanced_forecast_model_title(row),
                "kind": "高度予測",
                "horizon": forecast_horizon_display(
                    horizon_days,
                    latest_date=latest_date,
                ),
                "value": forecast_return or "未計算",
                "forecast_close": forecast_close or "未計算",
                "sub": (
                    f"予測値 {forecast_close or '未計算'} / "
                    f"{'レンジ ' + range_display if range_display else '方向感 ' + direction_display}"
                ),
                "help": _advanced_forecast_model_help(row),
                "tone": _forecast_card_tone(forecast_return),
                "badges": (
                    badge_html("高度予測", "info"),
                    badge_html(
                        f"信頼度 {confidence}",
                        _advanced_forecast_confidence_tone(row),
                    ),
                ),
            }
        )
    return cards


def forecast_model_cards_intro_text(cards: list[dict[str, Any]]) -> str:
    values = [
        f"{card.get('model', '')}: {card.get('value', '')}"
        for card in cards
        if card.get("model") and card.get("value") and card.get("value") != "未計算"
    ]
    if not values:
        return "各モデルの予測値と予測ロジックをカードで確認します。将来の値動きを保証するものではありません。"
    return (
        "各モデルの予測値と予測ロジックをカードで確認します。"
        f"今回の変化率は {' / '.join(values[:5])}。"
        "将来の値動きを保証するものではありません。"
    )


def forecast_model_comparison_rows(cards: list[dict[str, Any]]) -> list[dict[str, str]]:
    values = [
        value for card in cards if (value := _decimal_from_text(card.get("value", ""))) is not None
    ]
    if not values:
        return []
    up_count = sum(1 for value in values if value > 0)
    down_count = sum(1 for value in values if value < 0)
    flat_count = len(values) - up_count - down_count
    spread = max(values) - min(values) if len(values) >= 2 else Decimal("0")
    if up_count and down_count:
        direction_value = "見方が割れています"
        direction_caption = "上方向と下方向のモデルが混在しています。理由を分けて確認します。"
        direction_tone = "caution"
    elif up_count:
        direction_value = "上方向が多め"
        direction_caption = "表示中のモデルは上方向の見方が中心です。過熱感も確認します。"
        direction_tone = "success"
    elif down_count:
        direction_value = "下方向が多め"
        direction_caption = "表示中のモデルは下方向の見方が中心です。下落理由を確認します。"
        direction_tone = "caution"
    else:
        direction_value = "横ばい中心"
        direction_caption = "表示中のモデルは大きな方向感を出していません。"
        direction_tone = "neutral"
    spread_text = _plain_percent_display(spread)
    return [
        {
            "label": "上方向 / 下方向",
            "value": f"{up_count}件 / {down_count}件",
            "caption": f"横ばい {flat_count}件。方向の偏りを見るための件数です。",
            "help": "プラス予測を上方向、マイナス予測を下方向として数えています。",
            "tone": "info",
        },
        {
            "label": "モデル間の開き",
            "value": spread_text,
            "caption": "最大の予測変化率と最小の予測変化率の差です。",
            "help": "開きが大きいほど、モデルごとの見方に差があります。",
            "tone": "caution" if spread >= Decimal("10") else "info",
        },
        {
            "label": "方向感",
            "value": direction_value,
            "caption": direction_caption,
            "help": "売買判断ではなく、次に確認する観点を整理するための補助表示です。",
            "tone": direction_tone,
        },
    ]


def forecast_model_cards_html(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    card_html = "\n".join(_forecast_model_card_html(card) for card in cards)
    return (
        "<style>"
        ".smai-forecast-card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:10px 0 8px;}"
        ".smai-forecast-card{border:1px solid rgba(148,163,184,.35);border-radius:8px;padding:14px 16px;background:rgba(15,23,42,.72);box-shadow:inset 0 1px 0 rgba(255,255,255,.04);}"
        ".smai-forecast-card[data-tone='success']{border-color:rgba(45,212,191,.75);background:linear-gradient(180deg,rgba(20,83,78,.42),rgba(15,23,42,.75));}"
        ".smai-forecast-card[data-tone='caution']{border-color:rgba(251,113,133,.72);background:linear-gradient(180deg,rgba(127,29,29,.34),rgba(15,23,42,.75));}"
        ".smai-forecast-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;}"
        ".smai-forecast-model-name{font-size:1.02rem;font-weight:800;line-height:1.25;color:#7dd3fc;letter-spacing:0;}"
        ".smai-forecast-card[data-tone='success'] .smai-forecast-model-name{color:#5eead4;}"
        ".smai-forecast-card[data-tone='caution'] .smai-forecast-model-name{color:#fda4af;}"
        ".smai-forecast-help{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:1px solid rgba(148,163,184,.45);border-radius:999px;color:#cbd5e1;font-size:.72rem;cursor:help;flex:0 0 auto;}"
        ".smai-forecast-horizon{margin-top:6px;color:#94a3b8;font-size:.82rem;font-weight:700;}"
        ".smai-forecast-value{margin-top:6px;font-size:1.58rem;font-weight:850;color:#f8fafc;line-height:1.1;}"
        ".smai-forecast-sub{margin-top:8px;color:#cbd5e1;font-size:.86rem;line-height:1.4;overflow-wrap:anywhere;}"
        ".smai-forecast-card .smai-badge-row{margin-top:10px;}"
        "</style>"
        f'<div class="smai-forecast-card-grid">{card_html}</div>'
    )


def _forecast_model_card_html(card: dict[str, Any]) -> str:
    tone = str(card.get("tone") or "neutral")
    safe_tone = tone if tone in {"success", "caution", "info", "neutral"} else "neutral"
    model = str(card.get("model") or "予測モデル")
    help_text = str(card.get("help") or "")
    badges = "".join(card.get("badges") or ())
    return (
        '<div class="smai-forecast-card" '
        f'data-tone="{html.escape(safe_tone, quote=True)}">'
        '<div class="smai-forecast-card-head">'
        f'<div class="smai-forecast-model-name">{html.escape(model)}</div>'
        f'<span class="smai-forecast-help" title="{html.escape(help_text, quote=True)}">?</span>'
        "</div>"
        f'<div class="smai-forecast-horizon">{html.escape(str(card.get("horizon") or ""))}</div>'
        f'<div class="smai-forecast-value">{html.escape(str(card.get("value") or "未計算"))}</div>'
        f'<div class="smai-forecast-sub">{html.escape(str(card.get("sub") or ""))}</div>'
        f'<div class="smai-badge-row">{badges}</div>'
        "</div>"
    )


def _forecast_return_display(
    forecast_close: str,
    *,
    latest_close: Decimal | None,
) -> str:
    forecast_value = _decimal_from_text(forecast_close)
    if forecast_value is None or latest_close is None or latest_close <= 0:
        return ""
    percent_value = ((forecast_value / latest_close) - Decimal("1")) * Decimal("100")
    return _signed_percent_display(percent_value)


def _signed_percent_from_text(value: str) -> str:
    percent_value = _decimal_from_text(value)
    if percent_value is None:
        return ""
    return _signed_percent_display(percent_value)


def _signed_percent_display(percent_value: Decimal) -> str:
    text = f"{percent_value.quantize(Decimal('0.01'))}".rstrip("0").rstrip(".")
    if percent_value > 0:
        return f"+{text}%"
    return f"{text}%"


def _plain_percent_display(percent_value: Decimal) -> str:
    text = f"{percent_value.quantize(Decimal('0.01'))}".rstrip("0").rstrip(".")
    return f"{text}%"


def _forecast_card_tone(value: str) -> str:
    decimal_value = _decimal_from_text(value)
    if decimal_value is None:
        return "neutral"
    if decimal_value > 0:
        return "success"
    if decimal_value < 0:
        return "caution"
    return "neutral"


def _forecast_model_logic_help(model: str) -> str:
    moving_average = re.fullmatch(r"moving_average_(\d+)", model)
    if moving_average:
        window = moving_average.group(1)
        return (
            f"移動平均モデルです。計算式: 予測価格 = 直近{window}日間の終値の平均。"
            "短期の上下に振られにくく、今の価格が平均より高いか低いかを見る基準になります。"
        )
    momentum = re.fullmatch(r"momentum_(\d+)", model)
    if momentum:
        lookback = momentum.group(1)
        return (
            f"モメンタムモデルです。計算式: 直近{lookback}日変化率 = 最新価格 ÷ "
            f"{lookback}日前価格 - 1。"
            "1日あたり変化率に直し、予測日数分だけ最新価格へかけ合わせます。"
            "強い流れが続くかを確認する材料ですが、急反転には弱いことがあります。"
        )
    if model == "naive":
        return (
            "直近値維持モデルです。計算式: 予測価格 = 最新終値。"
            "カードの0%は、最新価格から最終予測値への変化がないという意味です。"
            "チャートの点線は過去の各時点でも同じ基準を置くため、価格の流れの中では下がって見える区間があります。"
        )
    return "価格データから作った予測モデルです。予測値は投資判断ではなく、比較用の参考材料です。"


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
    detail_rows = cockpit_direction_signal_detail_rows(score_row, consensus_row)
    _register_cockpit_direction_assistant_context(score_row, consensus_row, detail_rows)
    render_section_heading("判断シグナル")
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


def _render_score_breakdown_context(
    preview: MarketDataPreview,
    symbol_label: str,
    row: dict[str, str],
    rows: list[dict[str, str]],
) -> None:
    warning = row.get("注意点", "")
    summary_lines = investment_score_summary_lines(row)
    memo_rows = cockpit_investment_memo_rows(preview, row)
    memo_text = " ".join(
        str(item.get("見方") or item.get("内容") or item.get("確認ポイント") or "")
        for item in memo_rows[:3]
    )
    st.markdown("#### スコアから見た注意点")
    st.markdown(
        smai_insight_html(
            " ".join(part for part in [" ".join(summary_lines[:2]), memo_text] if part),
            tone="caution" if warning else "forecast",
        ),
        unsafe_allow_html=True,
    )


def _render_cockpit_check_summary(summary_rows: list[dict[str, str]]) -> None:
    if not summary_rows:
        return
    st.markdown("#### 主要確認サマリー")
    st.caption(
        "価格・予測・データ品質の代表項目だけを抜き出しています。"
        "元データは下部の詳細データで確認できます。"
    )
    _render_symbol_detail_table(summary_rows)


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
                "確認ポイント": "RMSEは価格予測の誤差、方向一致率は過去評価サンプル内で上下方向が合った割合です。将来保証ではなく、予測線を読む時の補助材料として見ます。",
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
        checks.append("リスク確認を優先")
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
        lines.append("目立つ注意点は表示されていません。")
    note = row.get("補足", "")
    if note:
        lines.append(note)
    return lines[:3]


def score_component_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "要素": "スクリーニング",
            "スコア": row.get("Screening", ""),
            "読み方": "市場データ由来の候補評価です。投資スコアの一部で、単独の売買判断には使いません。",
        },
        {
            "要素": "上昇気配",
            "スコア": row.get("上昇気配", ""),
            "読み方": "予測と直近値動きから見た上向き材料の確認値です。上昇を保証する値ではありません。",
        },
        {
            "要素": "下降警戒",
            "スコア": row.get("下降警戒", ""),
            "読み方": "下向き材料の警戒値です。売り指示ではなく、高いほど追加確認します。",
        },
        {
            "要素": "予測・モデル一致",
            "スコア": row.get("モデル一致度", "") or row.get("予測変化率", ""),
            "読み方": "予測モデルの見方がどの程度近いかを見る補助材料です。的中率や将来保証ではありません。",
        },
        {
            "要素": "リスク確認",
            "スコア": row.get("Risk", ""),
            "読み方": "価格変動や下落幅を確認する材料で、安全保証ではありません。",
        },
        {
            "要素": "データ品質",
            "スコア": row.get("データ品質", ""),
            "読み方": "評価に使える価格・特徴量データの充実度です。投資魅力度ではありません。",
        },
    ]


def score_confidence_hierarchy_rows() -> list[dict[str, str]]:
    return [
        {
            "表示": "投資スコア / 総合スコア",
            "役割": "複数材料を統合した比較・分析用スコア",
            "順位への影響": "通常のRanking表示順に使います",
            "読み方": "高くても売買指示ではなく、内訳と注意点を確認します。",
        },
        {
            "表示": "Forecast / 予測",
            "役割": "baseline model の見方、予測レンジ、モデル間のばらつき",
            "順位への影響": "上昇気配・下降警戒や投資スコアの一部として補助的に使います",
            "読み方": "予測線は確定未来ではなく、価格チャートとモデル差を確認する材料です。",
        },
        {
            "表示": "リスク確認",
            "役割": "価格変動、下落幅、制約警告などの確認材料",
            "順位への影響": "一部の評価方針や投資スコアの確認材料として使います",
            "読み方": "高い値でも安全保証ではなく、低い値は値動きや警告を先に確認します。",
        },
        {
            "表示": "Research Score",
            "役割": "根拠資料の充実度・鮮度・信頼度",
            "順位への影響": "既定では総合スコアやランキング順位を変えません",
            "読み方": "低い値は銘柄評価ではなく、根拠確認不足のサインとして扱います。",
        },
        {
            "表示": "LLM材料（参考）",
            "役割": "RAG・ニュース・IR情報を材料スコアへ構造化した参考指標",
            "順位への影響": "総合スコア、ランキング順位、Forecast、Investment Scoreには反映しません",
            "読み方": "強気材料・弱気材料・確信度・鮮度を並べて確認します。売買推奨ではありません。",
        },
        {
            "表示": "データ品質",
            "役割": "価格・特徴量データの欠損や取得品質",
            "順位への影響": "スコア解釈の信頼度を補助します",
            "読み方": "低い場合は取得期間、provider、欠損項目を確認します。",
        },
        {
            "表示": "条件適合度 / DB信頼度",
            "役割": "銘柄マスタやメタデータの充実度",
            "順位への影響": "一部の評価方針で補助的に使います",
            "読み方": "投資魅力度ではなく、評価材料がそろっているかの確認値です。",
        },
    ]


def _render_score_confidence_hierarchy() -> None:
    st.markdown(SYMBOL_DETAIL_DIALOG_CSS, unsafe_allow_html=True)
    st.markdown(symbol_detail_table_html(score_confidence_hierarchy_rows()), unsafe_allow_html=True)


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


def _research_score_expander_label(
    display_context: Literal["cockpit", "ranking"],
) -> str:
    if display_context == "cockpit":
        return "Research Score（根拠資料の確認材料）を表示"
    return "Research Score（参考情報）を表示"


def _research_score_context_caption(
    display_context: Literal["cockpit", "ranking"],
) -> str:
    if display_context == "cockpit":
        return (
            "銘柄コックピットで深掘りするときの確認材料です。"
            "根拠資料の充実度・鮮度・信頼度を整理し、売買推奨や順位付けは行いません。"
        )
    return (
        "ランキングから深掘り候補を確認するときの参考情報です。"
        "Research Scoreは順位計算ではなく、コックピットで追加確認する材料として扱います。"
    )


def _research_score_guidance_rows(
    display_context: Literal["cockpit", "ranking"],
) -> list[dict[str, str]]:
    usage = (
        "内訳と根拠資料の詳細を見て、公式IR・開示・ニュースで追加確認する観点を選びます。"
        if display_context == "cockpit"
        else "候補比較後に、コックピットで深掘りする観点を選ぶために使います。"
    )
    return [
        {
            "確認項目": "役割",
            "内容": "根拠資料の充実度・鮮度・信頼度を整理する参考スコア",
        },
        {
            "確認項目": "使い方",
            "内容": usage,
        },
        {
            "確認項目": "順位への影響",
            "内容": "既定では総合スコアやランキング順位を変更しません。",
        },
    ]


def _research_score_summary_rows(score: ResearchScore) -> list[dict[str, str]]:
    return [
        {
            "確認項目": "Research Score",
            "内容": str(score.total_score),
            "確認ポイント": (
                "根拠資料の充実度・鮮度・信頼度を整理する参考スコアです。"
                "売買推奨ではありません。既定では総合スコアやランキング順位を変えません。"
            ),
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
    return "内訳と根拠資料の詳細を見て、どの観点の資料が支えているか確認します。"


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
        "company_ir": "企業IRサイト",
        "tdnet": "TDnet",
        "news": "ニュース",
        "provider_profile": "取得元プロフィール",
        "research_summary": "Research Summary",
        "edinet": "EDINET",
        "symbol_db": "銘柄DB",
        "local_reference": "ローカル参考情報",
        "other": "確認資料",
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
        "company_ir",
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
    row = {
        "確認項目": "検索品質",
        "検索方式": quality.backend,
        "検索した観点": quality.query,
        "関連語の一部": _research_terms_preview(quality.expanded_terms),
        "候補数": str(quality.candidate_count),
        "根拠数": str(quality.evidence_count),
        "資料数": str(quality.document_count),
        "処理時間": f"{quality.latency_ms} ms",
        "注意点": " / ".join(quality.warnings),
    }
    if quality.backend == "hybrid":
        row["キーワード候補"] = str(quality.keyword_candidate_count)
        row["ベクトル候補"] = str(quality.vector_candidate_count)
    return [row]


def _research_retrieval_quality_caption(report: CompanyResearchReport) -> str:
    """Keep the active retrieval mode visible without exposing implementation detail."""

    quality = report.retrieval_quality
    if quality is None:
        return ""
    backend_label = {
        "keyword": RESEARCH_RETRIEVAL_MODE_KEYWORD,
        "vector": RESEARCH_RETRIEVAL_MODE_VECTOR,
        "hybrid": RESEARCH_RETRIEVAL_MODE_HYBRID,
    }.get(quality.backend, "検索方式未確認")
    caption = (
        f"{RESEARCH_RETRIEVAL_MODE_LABEL}: {backend_label}"
        f" / {RESEARCH_RETRIEVAL_EVIDENCE_LABEL}: {quality.evidence_count}件"
        f" / {RESEARCH_RETRIEVAL_DOCUMENT_LABEL}: {quality.document_count}件"
    )
    if quality.backend == "hybrid" and quality.vector_candidate_count == 0:
        caption += f" / {RESEARCH_RETRIEVAL_FALLBACK_NOTE}"
    return caption


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
        title=f"確認レポート - {symbol or '選択銘柄'}",
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
            notes=["上位候補メモは、比較条件と確認観点をあとから見返すための確認メモです。"],
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
                "総合順位だけでなく、基礎評価、上昇気配、リスク、ROE、配当利回りなど別観点の上位候補を並べます。"
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
        title="確認レポート - ランキング結果",
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
        ("確認スタンス", overview.get("investment_stance", "様子見 / 追加根拠確認")),
        ("注意材料", overview.get("key_risks", "価格トレンド・外部環境")),
    ]
    field_html = "".join(
        '<div class="decision-report-field">'
        f'<div class="decision-report-field-label">{html.escape(label)}</div>'
        f'<div class="decision-report-field-value">{html.escape(value)}</div>'
        "</div>"
        for label, value in fields
    )
    title = f"確認レポート - {overview.get('symbol', '選択銘柄')}"
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
    st.markdown("#### 確認項目の詳細")
    with st.container(border=True):
        st.markdown("##### 1. 要約")
        st.markdown(
            _decision_summary_list_html(
                cockpit_decision_report_summary_lines(preview, research_report)
            ),
            unsafe_allow_html=True,
        )

    with st.expander("2. 確認方針", expanded=True):
        _render_symbol_detail_table(
            [
                {"項目": "総合判断", "内容": overview.get("overall_judgement", "")},
                {"項目": "確認スタンス", "内容": overview.get("investment_stance", "")},
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

    st.markdown("### 05 確認レポート")
    st.info(DECISION_REPORT_SUPPORT_MESSAGE)
    st.markdown(_decision_report_overview_card_html(overview), unsafe_allow_html=True)

    summary_lines = cockpit_decision_report_summary_lines(preview, research_report)
    _register_cockpit_report_assistant_context(context, summary_lines)
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
        expander_label="確認レポート",
        json_file_name="decision_report_cockpit.json",
        markdown_file_name="decision_report_cockpit.md",
        heading_prefix="06",
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
        expander_label="確認レポート",
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
        st.markdown("### 確認レポート")
        render_mascot_panel(
            "report",
            message="深掘り候補を確認したあと、必要なときだけ分析メモとしてレポート化できます。",
            layout="compact",
        )
        st.info(
            "上位候補をあとから見返すために、比較条件、分布、確認ポイントを確認メモとして整理します。"
            "作成後は同じ評価方針の間、ダウンロード用データを再利用します。"
        )
        if st.button("確認レポートを作成", key=f"{report_state_key}_build"):
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
            expander_label="確認レポート",
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
    st.info(DECISION_REPORT_SUPPORT_MESSAGE)
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
    st.caption(DECISION_REPORT_DOWNLOAD_GUIDE)
    col_markdown, col_json, col_manifest, col_zip = st.columns(4)
    col_markdown.download_button(
        DECISION_REPORT_MARKDOWN_DOWNLOAD_LABEL,
        data=markdown,
        file_name=markdown_file_name,
        mime="text/markdown",
        help=DECISION_REPORT_MARKDOWN_DOWNLOAD_HELP,
    )
    col_json.download_button(
        DECISION_REPORT_JSON_DOWNLOAD_LABEL,
        data=decision_report_json_download(context),
        file_name=json_file_name,
        mime="application/json",
        help=DECISION_REPORT_JSON_DOWNLOAD_HELP,
    )
    col_manifest.download_button(
        DECISION_REPORT_MANIFEST_DOWNLOAD_LABEL,
        data=decision_report_manifest_json_download(context),
        file_name="decision_report_manifest.json",
        mime="application/json",
        help=DECISION_REPORT_MANIFEST_DOWNLOAD_HELP,
    )
    col_zip.download_button(
        DECISION_REPORT_ZIP_DOWNLOAD_LABEL,
        data=decision_report_zip_download(context),
        file_name="decision_report_package.zip",
        mime="application/zip",
        help=DECISION_REPORT_ZIP_DOWNLOAD_HELP,
    )


def _investment_score_report_section(
    row: dict[str, str],
    *,
    source_kind: ReportSourceKind,
    provider: str | None = None,
    symbol: str = "",
    as_of: date | None = None,
) -> DecisionReportSection:
    summary = {
        "total_score": row.get("total_score", ""),
        "score_band": row.get("score_band", ""),
        "screening_score": row.get("screening_score", ""),
        "forecast_agreement_score": row.get("forecast_agreement_score", ""),
        "upside_signal_score": row.get("upside_signal_score", ""),
        "reversal_expectation_score": row.get("reversal_expectation_score", ""),
        "reversal_expectation_label": row.get("reversal_expectation_label", ""),
        "reversal_expectation_reason": row.get("reversal_expectation_reason", ""),
        "reversal_chart_shape_score": row.get("reversal_chart_shape_score", ""),
        "reversal_chart_shape_label": row.get("reversal_chart_shape_label", ""),
        "reversal_forecast_score": row.get("reversal_forecast_score", ""),
        "reversal_safety_score": row.get("reversal_safety_score", ""),
        "reversal_pullback_score": row.get("reversal_pullback_score", ""),
        "reversal_quality_score": row.get("reversal_quality_score", ""),
        "reversal_material_score": row.get("reversal_material_score", ""),
        "reversal_trap_warning": row.get("reversal_trap_warning", ""),
        "dividend_trap_warning": row.get("dividend_trap_warning", ""),
        "dividend_safety_score": row.get("dividend_safety_score", ""),
        "dividend_yield_spike_flag": row.get("dividend_yield_spike_flag", ""),
        "dividend_sustainability_label": row.get("dividend_sustainability_label", ""),
        "downside_signal_score": row.get("downside_signal_score", ""),
        "forecast_return_pct": row.get("forecast_return_pct", ""),
        "data_quality_score": row.get("data_quality_score", ""),
        "risk_signal_score": row.get("risk_signal_score", ""),
        "warnings": row.get("warnings", ""),
        "reasons": row.get("reasons", ""),
    }
    advanced_summary = _ranking_advanced_forecast_report_summary(row)
    if advanced_summary:
        summary["ai_forecast_insight"] = advanced_summary
        summary["ai_forecast_direction_usage"] = (
            "上昇気配・下降警戒へ25%まで反映。信頼度が低い場合は控えめに読む。"
        )
    rows = [
        {"component": "基礎評価", "score": row.get("screening_score", "")},
        {
            "component": "上昇気配",
            "score": row.get("upside_signal_score", ""),
        },
        {
            "component": "下降警戒",
            "score": row.get("downside_signal_score", ""),
        },
    ]
    if advanced_summary:
        rows.append(
            {
                "component": ADVANCED_FORECAST_CONSENSUS_LABEL,
                "score": _ranking_advanced_forecast_display(row),
                "confirmation_point": _ranking_advanced_forecast_checkpoint(row),
            }
        )
    rows.extend(
        [
            {"component": "データ信頼度", "score": row.get("data_quality_score", "")},
            {"component": "リスク", "score": row.get("risk_signal_score", "")},
        ]
    )
    return build_report_section(
        title="スコア分解",
        source_kind=source_kind,
        provider=provider,
        symbol=symbol or None,
        as_of=as_of,
        summary=summary,
        rows=rows,
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
    rows = [
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
    advanced_summary = _ranking_advanced_forecast_report_summary(display_score_row)
    if advanced_summary:
        rows.insert(
            2,
            {
                "area": ADVANCED_FORECAST_CONSENSUS_LABEL,
                "finding": advanced_summary,
                "confirmation_point": _ranking_advanced_forecast_checkpoint(display_score_row),
            },
        )
    return rows


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
    advanced_count = _count_rows_with_advanced_forecast(rows)
    return {
        "比較銘柄数": str(len(rows)),
        "表示上位": str(min(len(rows), 20)),
        "1位スコア": _format_report_decimal(top_score),
        "20位スコア": _format_report_decimal(twentieth_score),
        "上位20件の平均総合スコア": _average_ranking_metric(rows[:20], "total_score"),
        "平均基礎評価": _average_ranking_metric(rows, "screening_score"),
        "平均上昇気配": _average_ranking_metric(rows, "upside_signal_score"),
        "平均下降警戒": _average_ranking_metric(rows, "downside_signal_score"),
        "平均データ信頼度": _average_ranking_metric(rows, "data_quality_score"),
        "平均リスク": _average_ranking_metric(rows, "risk_signal_score"),
        "AI予測インサイトあり": f"{advanced_count}/{len(rows)}",
        "平均AI予測信頼スコア": _average_ranking_metric(
            rows,
            "advanced_forecast_quality_score",
        ),
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
            "観点": "データ信頼度 90以上",
            "件数": str(_count_rows_at_least(rows, "data_quality_score", Decimal("90"))),
            "読み方": "比較に使えるデータが十分な候補の多さを確認します。",
        },
        {
            "観点": "リスク 50未満",
            "件数": str(_count_rows_below(rows, "risk_signal_score", Decimal("50"))),
            "読み方": "上位候補内でも先に警戒すべき銘柄数を確認します。",
        },
        {
            "観点": "警告あり",
            "件数": str(sum(1 for row in rows if str(row.get("warnings", "")).strip())),
            "読み方": "高スコアでも確認順を下げるべき候補がないか見ます。",
        },
        {
            "観点": "AI予測インサイトあり",
            "件数": str(_count_rows_with_advanced_forecast(rows)),
            "読み方": "高度予測を上昇気配・下降警戒の補助材料として使える候補数です。",
        },
        {
            "観点": "AI予測信頼度 低め",
            "件数": str(_count_rows_with_advanced_forecast_confidence(rows, "low")),
            "読み方": "予測レンジやモデル合意度を特に慎重に確認したい候補数です。",
        },
    ]


def _ranking_factor_leader_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    leaders: list[dict[str, str]] = []
    for label, metric, prefer_low in [
        ("総合スコア", "total_score", False),
        ("基礎評価", "screening_score", False),
        ("上昇気配", "upside_signal_score", False),
        ("下降警戒", "downside_signal_score", True),
        ("AI予測上昇", "advanced_forecast_upside_score", False),
        ("AI予測下振れ警戒", "advanced_forecast_downside_score", True),
        ("データ信頼度", "data_quality_score", False),
        ("リスク", "risk_signal_score", False),
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
    checkpoints = [
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
                f"平均リスクは{_average_ranking_metric(rows, 'risk_signal_score')}です。"
            ),
            "confirmation_point": "スコアの高さが一部要素だけに偏っていないか確認します。",
        },
        {
            "area": "ファクター",
            "finding": "総合順位とは別に、基礎評価、上昇気配、リスク、ROE、配当利回りの上位候補を抽出しています。",
            "confirmation_point": "投資目的に近いファクターの候補から深掘り順を決めます。",
        },
        {
            "area": "次の確認",
            "finding": "ランキングは候補群の優先順位づけであり、個別判断はコックピットで確認します。",
            "confirmation_point": "銘柄ごとの価格トレンド、決算材料、配当方針、リスクを確認してから判断します。",
        },
    ]
    advanced_count = _count_rows_with_advanced_forecast(rows)
    if advanced_count:
        checkpoints.insert(
            2,
            {
                "area": ADVANCED_FORECAST_CONSENSUS_LABEL,
                "finding": (
                    f"{advanced_count}/{len(rows)}件にAI予測インサイトがあります。"
                    "上昇気配・下降警戒へ25%まで反映しています。"
                ),
                "confirmation_point": (
                    "信頼度が低い候補は順位を過信せず、中心予測、予測レンジ、モデル合意度を確認します。"
                ),
            },
        )
    return checkpoints


def _count_rows_with_advanced_forecast(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if _ranking_advanced_forecast_display(row))


def _count_rows_with_advanced_forecast_confidence(
    rows: list[dict[str, str]],
    confidence_key: str,
) -> int:
    return sum(
        1 for row in rows if _ranking_advanced_forecast_confidence_key(row) == confidence_key
    )


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
    report_row = {
        "rank": row.get("rank", ""),
        "symbol": symbol,
        "name": name,
        "ranking_purpose": ranking_purpose,
        "total_score": row.get("total_score", ""),
        "score_band": row.get("score_band", ""),
        "review_point": _ranking_report_review_point(row, symbol_row),
    }
    advanced_summary = _ranking_advanced_forecast_report_summary(row)
    if advanced_summary:
        report_row["ai_forecast_insight"] = advanced_summary
    return report_row


def _ranking_report_detail_row(row: dict[str, str]) -> dict[str, str]:
    detail_row = {
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
    advanced_summary = _ranking_advanced_forecast_report_summary(row)
    if advanced_summary:
        detail_row.update(
            {
                "ai_forecast_insight": advanced_summary,
                "advanced_forecast_upside_score": row.get(
                    "advanced_forecast_upside_score",
                    "",
                ),
                "advanced_forecast_downside_score": row.get(
                    "advanced_forecast_downside_score",
                    "",
                ),
                "advanced_forecast_quality_score": row.get(
                    "advanced_forecast_quality_score",
                    "",
                ),
                "advanced_forecast_direction_note": row.get(
                    "advanced_forecast_direction_note",
                    "",
                ),
            }
        )
    return detail_row


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
    advanced_checkpoint = _ranking_advanced_forecast_checkpoint(row)
    if advanced_checkpoint:
        return advanced_checkpoint
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


def _render_market_chart_currency_selector(
    source_currency: str,
    fx_rows: list[dict[str, str]],
) -> str:
    source = source_currency.strip().upper()
    jpy_fx_rate = chart_fx_rate_from_rows(fx_rows, source_currency=source)
    if source == "JPY":
        return "JPY"
    if jpy_fx_rate is None:
        return _default_market_chart_display_currency(source)
    options = [source, "JPY"]
    default_currency = _default_market_chart_display_currency(source)

    current_value = st.session_state.get(MARKET_CHART_DISPLAY_CURRENCY_STATE_KEY)
    if current_value not in options:
        st.session_state[MARKET_CHART_DISPLAY_CURRENCY_STATE_KEY] = default_currency

    currency_col, rate_col = st.columns([0.34, 0.66])
    with currency_col:
        selected = cast(
            str,
            st.radio(
                "表示通貨",
                options=options,
                key=MARKET_CHART_DISPLAY_CURRENCY_STATE_KEY,
                horizontal=True,
                format_func=lambda option: _market_chart_currency_option_label(str(option)),
                help="価格チャートの表示通貨だけを現地通貨/円換算で切り替えます。スコアや予測計算は変更しません。",
            ),
        )
    with rate_col:
        pair = _jpy_fx_pair_for_currency(source)
        st.markdown(
            (
                "<div style='padding-top:2.15rem;font-size:0.82rem;"
                "font-weight:700;color:#b9c7da;'>"
                f"{html.escape(pair or source + 'JPY')} {_format_market_chart_fx_rate(jpy_fx_rate)}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    return selected


def _default_market_chart_display_currency(source_currency: str) -> str:
    source = source_currency.strip().upper()
    return source if source in {"JPY", *RANKING_JPY_FX_PAIRS_BY_CURRENCY} else "JPY"


def _market_chart_currency_option_label(option: str) -> str:
    labels = {
        "JPY": "円 (JPY)",
        "USD": "$ (USD)",
        "HKD": "香港ドル (HKD)",
        "KRW": "韓国ウォン (KRW)",
        "VND": "ベトナムドン (VND)",
        "IDR": "インドネシアルピア (IDR)",
        "SGD": "シンガポールドル (SGD)",
        "THB": "タイバーツ (THB)",
        "MYR": "マレーシアリンギット (MYR)",
        "CNY": "人民元 (CNY)",
    }
    return labels.get(option, option)


def _format_market_chart_fx_rate(rate: Decimal) -> str:
    if rate < Decimal("0.1"):
        return f"{rate:.4f}"
    return f"{rate:.2f}"


def chart_fx_rate_from_rows(
    fx_rows: list[dict[str, str]],
    *,
    source_currency: str = "USD",
) -> Decimal | None:
    row = _market_chart_jpy_fx_row(fx_rows, source_currency=source_currency)
    if row is None:
        return None
    rate = _decimal_from_text(row.get("rate"))
    if rate is None or rate <= 0:
        return None
    return rate


def _market_chart_jpy_fx_row(
    fx_rows: list[dict[str, str]],
    *,
    source_currency: str,
) -> dict[str, str] | None:
    pair = _jpy_fx_pair_for_currency(source_currency) or "USDJPY"
    for row in reversed(fx_rows):
        if str(row.get("pair", "")).strip().upper() != pair:
            continue
        rate = _decimal_from_text(row.get("rate"))
        if rate is not None and rate > 0:
            return row
    return None


def convert_market_chart_rows_currency(
    rows: list[dict[str, str]],
    *,
    source_currency: str,
    display_currency: str,
    usd_jpy_rate: Decimal | None,
) -> list[dict[str, str]]:
    factor = _market_chart_currency_factor(
        source_currency=source_currency,
        display_currency=display_currency,
        usd_jpy_rate=usd_jpy_rate,
    )
    if factor is None or factor == Decimal("1"):
        return [dict(row) for row in rows]

    converted_rows: list[dict[str, str]] = []
    for row in rows:
        converted_row: dict[str, str] = {}
        for key, value in row.items():
            if key == "ts":
                converted_row[key] = value
                continue
            decimal_value = _decimal_from_text(value)
            if decimal_value is None:
                converted_row[key] = value
                continue
            converted_row[key] = _format_market_chart_decimal(decimal_value * factor)
        converted_rows.append(converted_row)
    return converted_rows


def _market_chart_currency_factor(
    *,
    source_currency: str,
    display_currency: str,
    usd_jpy_rate: Decimal | None,
) -> Decimal | None:
    source = _default_market_chart_display_currency(source_currency)
    target = display_currency.strip().upper()
    if source == target or not target:
        return Decimal("1")
    if usd_jpy_rate is None or usd_jpy_rate <= 0:
        return None
    if source != "JPY" and target == "JPY":
        return usd_jpy_rate
    if source == "JPY" and target in RANKING_JPY_FX_PAIRS_BY_CURRENCY:
        return Decimal("1") / usd_jpy_rate
    return None


def _format_market_chart_decimal(value: Decimal) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _render_market_chart(
    rows: list[dict[str, str]],
    *,
    currency: str = "",
    title: str = "",
    color_series_labels: Iterable[str] | None = None,
    legend_series_labels: Iterable[str] | None = None,
) -> None:
    if not _market_chart_has_displayable_data(rows):
        st.info(
            "表示できる期間データが不足しています。"
            "データ取得後、または期間を広げるとチャートが表示されます。"
        )
        return
    y_axis_title = f"終値 ({currency})" if currency else "終値"
    chart_data = market_chart_long_frame(rows)
    if chart_data.empty:
        st.info(
            "表示できる期間データが不足しています。"
            "データ取得後、または期間を広げるとチャートが表示されます。"
        )
        return
    color_domain = forecast_chart_color_domain(
        color_series_labels
        if color_series_labels is not None
        else chart_data["series_label"].tolist()
    )
    color_range = forecast_chart_color_range(color_domain)
    color_scale = alt.Scale(domain=color_domain, range=color_range)
    disabled_series = alt.selection_point(
        fields=["series_label"],
        on="click",
        toggle="true",
        empty=False,
    )
    group_visibility_params, group_hidden_expr = _market_chart_group_visibility_controls(rows)
    chart = _market_chart_layers(
        rows,
        y_axis_title=y_axis_title,
        color_scale=color_scale,
        disabled_series=disabled_series,
        group_hidden_expr=group_hidden_expr,
        height=MARKET_CHART_HEIGHT,
        width=MARKET_CHART_FULL_WIDTH,
        title="価格チャート",
        show_all_points=True,
        compact_points=True,
    )
    focus_rows = forecast_focus_chart_rows(rows)
    focus_chart = _market_chart_layers(
        focus_rows,
        y_axis_title=y_axis_title,
        color_scale=color_scale,
        disabled_series=disabled_series,
        group_hidden_expr=group_hidden_expr,
        height=MARKET_CHART_HEIGHT,
        width=MARKET_CHART_FOCUS_WIDTH,
        title=forecast_focus_chart_title(rows),
        show_all_points=True,
        compact_points=False,
    )
    main_chart = alt.hconcat(chart, focus_chart, spacing=MARKET_CHART_COMBINED_SPACING)
    legend_chart = _market_chart_interactive_legend(
        forecast_chart_color_domain(
            legend_series_labels
            if legend_series_labels is not None
            else chart_data["series_label"].tolist()
        ),
        color_scale=color_scale,
        disabled_series=disabled_series,
        group_hidden_expr=group_hidden_expr,
    )
    combined_chart = (
        alt.vconcat(main_chart, legend_chart, spacing=4)
        .add_params(disabled_series, *group_visibility_params)
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
    if title:
        combined_chart = combined_chart.properties(title=title)
    st.altair_chart(
        combined_chart,
        use_container_width=False,
    )


def _market_chart_has_displayable_data(rows: list[dict[str, str]]) -> bool:
    if len(rows) < 2:
        return False
    frame = market_chart_long_frame(rows)
    if frame.empty or "date" not in frame or "value" not in frame:
        return False
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["date", "value"])
    if len(frame) < 2:
        return False
    if frame["date"].nunique() < 2:
        return False
    minimum = frame["value"].min()
    maximum = frame["value"].max()
    return bool(pd.notna(minimum) and pd.notna(maximum))


def _market_chart_group_visibility_controls(
    rows: list[dict[str, str]],
) -> tuple[list[alt.Parameter], str]:
    return [], ""


def _with_group_visibility_filter(chart: alt.Chart, hidden_expr: str) -> alt.Chart:
    if not hidden_expr:
        return chart
    return chart.transform_filter(f"!({hidden_expr})")


def _market_chart_interactive_legend(
    labels: Sequence[str],
    *,
    color_scale: alt.Scale,
    disabled_series: alt.Parameter,
    group_hidden_expr: str,
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
    base = _with_group_visibility_filter(alt.Chart(legend_data), group_hidden_expr).encode(
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
        width=MARKET_CHART_FULL_WIDTH + MARKET_CHART_FOCUS_WIDTH + MARKET_CHART_COMBINED_SPACING,
        height=max(38, row_count * 30),
        title="価格・モデル",
    )


def _market_chart_model_legend_html(
    labels: Sequence[str],
    colors: Sequence[str],
) -> str:
    items = []
    for label, color in zip(labels, colors, strict=False):
        items.append(
            '<span style="display:inline-flex;align-items:center;gap:0.42rem;'
            'min-width:13.5rem;margin:0.18rem 0.75rem 0.18rem 0;">'
            f'<span style="width:0.68rem;height:0.68rem;border-radius:999px;'
            f'background:{html.escape(color)};box-shadow:0 0 0 1px rgba(226,232,240,0.32);">'
            "</span>"
            f'<span style="color:{THEME_COLORS["text_secondary"]};font-size:0.82rem;'
            'font-weight:700;line-height:1.35;">'
            f"{html.escape(label)}</span></span>"
        )
    return (
        '<div style="margin:0.35rem 0 0.55rem 0;padding:0.55rem 0.7rem;'
        f'background:{THEME_COLORS["bg_surface"]};'
        f'border-top:1px solid {THEME_COLORS["border_subtle"]};">'
        f'<div style="color:{THEME_COLORS["text_heading"]};font-size:0.8rem;'
        'font-weight:800;margin-bottom:0.25rem;">価格・モデル</div>'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;">'
        f'{"".join(items)}</div></div>'
    )


def _market_chart_layers(
    rows: list[dict[str, str]],
    *,
    y_axis_title: str,
    color_scale: alt.Scale,
    disabled_series: alt.Parameter,
    group_hidden_expr: str,
    height: int,
    width: int,
    title: str,
    show_all_points: bool,
    compact_points: bool,
) -> alt.LayerChart:
    chart_data = market_chart_long_frame(rows)
    range_band_data = forecast_range_band_frame(rows)
    boundary_data = forecast_boundary_frame(rows)
    latest_actual_data = latest_actual_price_frame(rows)
    forecast_data = chart_data[chart_data["series_label"] != FORECAST_ACTUAL_LABEL]
    actual_data = chart_data[chart_data["series_label"] == FORECAST_ACTUAL_LABEL]
    base_x = alt.X("date:T", title="Date", axis=alt.Axis(format="%m/%d", labelAngle=0))
    base_encoding = {
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
    forecast_point = (
        alt.OverlayMarkDef(
            filled=True,
            size=22 if compact_points else 36,
            opacity=0.58 if compact_points else 0.92,
        )
        if show_all_points
        else False
    )
    actual_point = (
        alt.OverlayMarkDef(
            filled=True,
            size=24 if compact_points else 52,
            opacity=0.62 if compact_points else 0.92,
        )
        if show_all_points
        else False
    )
    range_band = (
        _with_group_visibility_filter(alt.Chart(range_band_data), group_hidden_expr)
        .mark_area(opacity=0.18)
        .encode(
            x=base_x,
            y=alt.Y("lower:Q", title=y_axis_title, scale=alt.Scale(zero=False)),
            y2=alt.Y2("upper:Q"),
            color=alt.Color(
                "series_label:N",
                title="価格・モデル",
                legend=None,
                scale=color_scale,
            ),
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
        _with_group_visibility_filter(alt.Chart(forecast_data), group_hidden_expr)
        .mark_line(
            point=forecast_point,
            strokeWidth=1.9,
            opacity=0.9,
        )
        .encode(**base_encoding)
        .properties(height=height, width=width)
    )
    actual_line = (
        _with_group_visibility_filter(alt.Chart(actual_data), group_hidden_expr)
        .mark_line(
            point=actual_point,
            strokeWidth=2.8,
        )
        .encode(**base_encoding)
        .properties(height=height, width=width)
    )
    chart = range_band + forecast_lines + actual_line
    if not show_all_points and not forecast_data.empty:
        forecast_endpoint_data = (
            forecast_data.sort_values("date").groupby("series_label", as_index=False).tail(1)
        )
        forecast_endpoint_marker = (
            _with_group_visibility_filter(
                alt.Chart(forecast_endpoint_data),
                group_hidden_expr,
            )
            .mark_point(filled=True, size=58, opacity=0.95)
            .encode(**base_encoding)
            .properties(height=height, width=width)
        )
        chart = chart + forecast_endpoint_marker
    if not latest_actual_data.empty:
        latest_marker = (
            _with_group_visibility_filter(alt.Chart(latest_actual_data), group_hidden_expr)
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
    if not boundary_data.empty:
        boundary_rule = (
            alt.Chart(boundary_data)
            .mark_rule(color=THEME_COLORS["text_muted"], opacity=0.52, strokeDash=[4, 4])
            .encode(x="date:T")
        )
        chart = chart + boundary_rule
    return chart.properties(height=height, width=width, title=title)


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
    range_bound_columns = [
        column for column in frame.columns if _is_forecast_range_bound_series(str(column))
    ]
    if range_bound_columns:
        frame = frame.drop(columns=range_bound_columns)
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


def forecast_range_band_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = market_chart_frame(rows).reset_index(names="date")
    range_rows: list[pd.DataFrame] = []
    for column in frame.columns:
        match = re.fullmatch(
            r"((?:advanced_quantile|advanced_consensus)_\d+d)_lower",
            str(column),
        )
        if not match:
            continue
        series = match.group(1)
        upper_column = f"{series}_upper"
        if upper_column not in frame:
            continue
        band = frame[["date", column, upper_column]].copy()
        band = band.rename(columns={column: "lower", upper_column: "upper"})
        band = band.dropna(subset=["lower", "upper"])
        if band.empty:
            continue
        band["series"] = series
        band["series_label"] = _forecast_series_label(series)
        range_rows.append(band[["date", "lower", "upper", "series", "series_label"]])
    if not range_rows:
        return pd.DataFrame(columns=["date", "lower", "upper", "series", "series_label"])
    return pd.concat(range_rows, ignore_index=True)


def forecast_focus_chart_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return rows around the latest actual price and the forward forecast area."""

    dated_rows: list[tuple[date, dict[str, str]]] = []
    for row in rows:
        ts = row.get("ts", "")
        if not ts:
            continue
        parsed = pd.to_datetime(ts, errors="coerce")
        if pd.isna(parsed):
            continue
        dated_rows.append((parsed.date(), row))
    if not dated_rows:
        return rows

    actual_dates = [row_date for row_date, row in dated_rows if str(row.get("close", "")).strip()]
    if not actual_dates:
        return rows

    latest_actual_date = max(actual_dates)
    future_forecast_dates = [
        row_date
        for row_date, row in dated_rows
        if row_date > latest_actual_date and _row_has_forecast_value(row)
    ]
    latest_forecast_date = (
        max(future_forecast_dates) if future_forecast_dates else latest_actual_date
    )
    forecast_span_days = max(1, (latest_forecast_date - latest_actual_date).days)
    lookback_days = max(3, min(14, (forecast_span_days // 2) + 2))
    focus_start = latest_actual_date - timedelta(days=lookback_days)
    return [row for row_date, row in dated_rows if row_date >= focus_start]


def forecast_focus_chart_title(rows: list[dict[str, str]]) -> str:
    for row in rows:
        for key, value in row.items():
            if not str(value).strip() or _is_forecast_range_bound_series(str(key)):
                continue
            match = re.fullmatch(r".+_(\d+)d", str(key))
            if match:
                return f"予測スコープ（{match.group(1)}日）"
    return "予測スコープ"


def _row_has_forecast_value(row: Mapping[str, str]) -> bool:
    return any(
        key != "ts"
        and key != "close"
        and not _is_forecast_range_bound_series(key)
        and str(value).strip()
        for key, value in row.items()
    )


def _is_forecast_range_bound_series(series: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:advanced_quantile|advanced_consensus)_\d+d_(lower|upper)",
            series,
        )
    )


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


def advanced_forecast_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    confidence_labels = {
        "high": "高め",
        "medium": "中くらい",
        "low": "低め",
    }
    return [
        {
            "モデル": _advanced_forecast_model_title(row),
            "予測変化": _signed_percent_from_text(row.get("predicted_return", "")),
            "予測価格": row.get("forecast_close", ""),
            "想定レンジ": _advanced_forecast_range_display(row),
            "方向感": _advanced_forecast_direction_display(row.get("direction_score", "")),
            "信頼度": confidence_labels.get(row.get("confidence", ""), row.get("confidence", "")),
            "RMSE": row.get("rmse", ""),
            "方向一致": row.get("direction_accuracy", ""),
            "検証数": row.get("sample_count", ""),
            "効いた特徴": _advanced_forecast_feature_display(row.get("top_features", "")),
            "注意点": _advanced_forecast_warning_display(row.get("warnings", "")),
        }
        for row in rows
    ]


def advanced_forecast_consensus_display_rows(
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    return [
        {
            "銘柄": row.get("symbol", ""),
            "予測日数": row.get("horizon_days", ""),
            "モデル数": row.get("model_count", ""),
            ADVANCED_FORECAST_CONSENSUS_PREDICTION_LABEL: _signed_percent_from_text(
                row.get("predicted_return", "")
            ),
            "方向判定用変化率": _signed_percent_from_text(
                row.get("direction_predicted_return", "")
            ),
            "予測価格": row.get("forecast_close", ""),
            "想定レンジ": _advanced_forecast_range_display(row),
            "予測ばらつき": _advanced_forecast_dispersion_label(row),
            "モデル合意度": _advanced_forecast_model_agreement_display(row),
            "モデル選択": _advanced_forecast_selection_display(row),
            "中心モデル": row.get("center_models", ""),
            "方向モデル": row.get("direction_models", ""),
            "中心値から除外": row.get("center_excluded_models", ""),
            "選択理由": row.get("selection_reason", ""),
            "信頼度": _advanced_forecast_confidence_label(row.get("confidence", "")),
            "過去検証の方向一致率": row.get("mean_direction_accuracy", ""),
            "平均RMSE": row.get("mean_rmse", ""),
            "誤差改善": _advanced_forecast_error_improvement_display(row),
            "相対的に安定": _advanced_forecast_best_model_display(row),
            "注意点": _advanced_forecast_warning_display(row.get("warnings", "")),
        }
        for row in rows
    ]


def advanced_forecast_card_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in rows:
        horizon_days = row.get("horizon_days", "")
        predicted_return = row.get("predicted_return", "")
        forecast_close = row.get("forecast_close", "")
        range_display = _advanced_forecast_range_display(row)
        direction_score = _advanced_forecast_direction_display(row.get("direction_score", ""))
        confidence = _advanced_forecast_confidence_label(row.get("confidence", ""))
        direction_accuracy = row.get("direction_accuracy", "")
        sample_count = row.get("sample_count", "")
        cards.append(
            {
                "label": f"{horizon_days}日予測",
                "value": _signed_percent_from_text(predicted_return) or "未計算",
                "caption": (
                    f"予測価格 {forecast_close or '未計算'} / "
                    f"{'レンジ ' + range_display if range_display else '方向感 ' + direction_score}"
                ),
                "help": (
                    _advanced_forecast_model_help(row)
                    + (
                        f"方向一致 {direction_accuracy or '未計算'}、検証数 {sample_count or '0'}。"
                        "売買判断ではなく、価格シナリオの確認材料です。"
                    )
                ),
                "badges": (
                    badge_html("高度予測", "info"),
                    badge_html(
                        f"信頼度 {confidence}",
                        _advanced_forecast_confidence_tone(row),
                    ),
                ),
                "tone": _advanced_forecast_card_tone(row),
                "progress": direction_score,
            }
        )
    return cards


def advanced_forecast_intro_text(rows: list[dict[str, str]]) -> str:
    parts = [
        (
            f"{_advanced_forecast_model_title(row)} "
            f"{_signed_percent_from_text(row.get('predicted_return', ''))}"
        ).strip()
        for row in rows
        if row.get("horizon_days") and row.get("predicted_return")
    ]
    if parts:
        return (
            "高度予測は取得期間に合わせた予測先でそろえた参考シナリオです。"
            f"今回の参考変化率は {' / '.join(parts)}。"
            "将来の値動きを保証するものではありません。"
        )
    return "高度予測は取得期間に合わせた予測先の参考シナリオです。将来の値動きを保証するものではありません。"


def _advanced_forecast_model_title(row: Mapping[str, str]) -> str:
    model_label = row.get("model_label", "").strip()
    if not model_label:
        adapter = row.get("adapter", "").strip()
        if adapter == "advanced_quantile":
            model_label = "高度予測: レンジモデル"
        elif adapter == "advanced_gbdt_sklearn":
            model_label = "高度予測: ブースティングモデル"
        elif adapter == "advanced_tree_sklearn":
            model_label = "高度予測: ツリーモデル"
        elif adapter == "advanced_linear" or not adapter:
            model_label = "高度予測: 線形モデル"
        else:
            model_label = f"高度予測: {adapter or row.get('model', '')}".strip()
    horizon_days = row.get("horizon_days", "").strip()
    return f"{model_label} {horizon_days}日".strip()


def _advanced_forecast_range_display(row: Mapping[str, str]) -> str:
    lower = _signed_percent_from_text(row.get("predicted_return_lower", ""))
    upper = _signed_percent_from_text(row.get("predicted_return_upper", ""))
    if lower and upper:
        return f"{lower}〜{upper}"
    return ""


def _advanced_forecast_direction_display(value: str) -> str:
    score = _decimal_from_text(value)
    if score is None:
        return "未計算"
    if abs(score) <= Decimal("1"):
        score *= Decimal("100")
    percent = _signed_percent_display(score).lstrip("+")
    if score > Decimal("55"):
        return f"上向き寄り {percent}"
    if score < Decimal("45"):
        return f"下向き寄り {percent}"
    return f"中立 {percent}"


def _advanced_forecast_model_help(row: Mapping[str, str]) -> str:
    horizon_days = row.get("horizon_days", "")
    adapter = row.get("adapter", "")
    if adapter == "advanced_quantile":
        return (
            f"レンジモデルです。計算式: 過去の{horizon_days}日後リターン = "
            f"({horizon_days}日後の価格 ÷ 当日の価格) - 1。"
            "中央値を中心予測、20%点と80%点を下振れ・上振れとして表示します。"
            "売買判断ではなく価格レンジ確認用です。"
        )
    if adapter == "advanced_tree_sklearn":
        return (
            "ツリーモデルです。入力はリターン、移動平均との差、値動きの大きさ、下落幅、出来高など。"
            f"過去データを条件分岐で似た局面に分け、その局面の{horizon_days}日後リターンから"
            "参考推定します。予測価格 = 最新価格 × (1 + 推定リターン)。"
            "売買判断ではなく価格シナリオ確認用です。"
        )
    if adapter == "advanced_gbdt_sklearn":
        return (
            "ブースティングモデルです。入力はリターン、移動平均との差、値動きの大きさ、下落幅、出来高など。"
            "小さな決定木を順番に足し、前の誤差を補いながら予測変化率を推定します。"
            "予測価格 = 最新価格 × (1 + 推定リターン)。"
            "売買判断ではなく価格シナリオ確認用です。"
        )
    return (
        "線形モデルです。入力はリターン、移動平均との差、値動きの大きさ、下落幅、出来高など。"
        "計算式イメージ: 予測変化率 = 切片 + Σ(特徴量 × 係数)。"
        f"これを{horizon_days}日後の参考変化率として、予測価格 = 最新価格 × (1 + 予測変化率)で表示します。"
        "売買判断ではなく価格シナリオ確認用です。"
    )


def _advanced_forecast_consensus_help_text(row: Mapping[str, str]) -> str:
    model_count = row.get("model_count") or "0"
    center_models = row.get("center_models") or "未取得"
    direction_models = row.get("direction_models") or "未取得"
    selection_reason = row.get("selection_reason") or "取得期間と過去検証から自動選択します。"
    return (
        f"方向確認には{model_count}モデルを使う参考シナリオです。"
        f"中心モデル: {center_models}。方向モデル: {direction_models}。{selection_reason}"
        "計算式: 中心予測 = Σ(選択モデルの予測変化率 × 検証重み) ÷ Σ重み。"
        "重み = 信頼度 × 誤差改善 × 方向一致 × 検証数を保守的に制限し、"
        "レンジモデルがある場合は中心重みを50%以上にします。"
        "予測価格 = 最新価格 × (1 + 統合予測)。"
        "方向判定は60日以内では監査済みの従来合議を維持し、中心価格とは別に評価します。"
        "60日超120日以下は、長期historical backtestに基づき中心予測の信頼度を低めに維持しつつ、"
        "Quantile方向判定は個別検証が中以上の場合だけ中くらいまで表示します。"
        "レンジは選択モデルの最小〜最大とレンジモデルの下振れ〜上振れを合わせて見ます。"
    )


def _advanced_forecast_confidence_label(value: str) -> str:
    labels = {
        "high": "高め",
        "medium": "中くらい",
        "low": "低め",
    }
    return labels.get(value, value or "未計算")


def _advanced_forecast_card_tone(row: dict[str, str]) -> str:
    confidence = str(row.get("confidence", "")).strip()
    dispersion = _advanced_forecast_dispersion_label(row)
    if confidence == "low" or dispersion == "大きめ":
        return "caution"
    predicted_return = _decimal_from_text(row.get("predicted_return", ""))
    if predicted_return is None:
        return "caution"
    if predicted_return > 0:
        return "success"
    if predicted_return < 0:
        return "caution"
    return "neutral"


def _advanced_forecast_confidence_tone(row: dict[str, str]) -> str:
    confidence = row.get("confidence", "")
    if confidence == "high":
        return "success"
    if confidence == "low":
        return "caution"
    return "info"


def _advanced_forecast_best_model_display(row: Mapping[str, str]) -> str:
    adapter = row.get("best_adapter", "").strip()
    model = row.get("best_model", "").strip()
    if not adapter and not model:
        return ""
    label = _advanced_forecast_model_title(
        {"adapter": adapter, "model": model, "horizon_days": row.get("horizon_days", "")}
    )
    if model and model not in label:
        return f"{label} / {model}"
    return label


def _advanced_forecast_feature_display(value: str) -> str:
    if not value:
        return ""
    replacements = {
        "positive": "押し上げ",
        "negative": "押し下げ",
    }
    text = value
    for source, target in replacements.items():
        text = text.replace(source, target)
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return " / ".join(parts[:3])


def _advanced_forecast_warning_display(value: str) -> str:
    if not value:
        return ""
    warning_map = {
        "This advanced forecast is experimental reference information, not investment advice.": (
            "実験的な参考予測です。売買判断ではなく、価格シナリオ確認に使ってください。"
        ),
        "Feature contributions describe model coefficients and are not causal explanations.": (
            "効いた特徴はモデル上の係数であり、因果関係の説明ではありません。"
        ),
        "Tree feature importance is model importance and not a causal explanation.": (
            "効いた特徴はツリーモデル上の重要度であり、因果関係の説明ではありません。"
        ),
        "ExtraTreesRegressor uses a fixed random_state for deterministic local checks.": (
            "ツリーモデルは通常確認で再現しやすいよう乱数を固定しています。"
        ),
        "RandomForestRegressor uses a fixed random_state for deterministic local checks.": (
            "ツリーモデルは通常確認で再現しやすいよう乱数を固定しています。"
        ),
        "Validation data is limited or unstable; treat this forecast as low confidence.": (
            "検証データが少ない、または不安定です。信頼度は低めに見てください。"
        ),
        "Validation RMSE did not improve over the zero-return baseline.": (
            "ゼロリターン基準よりRMSEが改善していません。慎重に確認してください。"
        ),
        "Advanced forecast consensus is reference information, not investment advice.": (
            "AI予測インサイトは参考情報です。売買判断そのものではありません。"
        ),
        "Consensus weights are capped; validation metrics support comparison but do not guarantee future accuracy.": (
            "重みは保守的に制限しています。検証指標は比較材料であり、将来精度の保証ではありません。"
        ),
        "Consensus confidence is low; check model-by-model reasons before using it.": (
            "AI予測インサイトの信頼度は低めです。個別モデルの理由も確認してください。"
        ),
        "Advanced models have a wide forecast spread.": (
            "高度予測モデル間の開きが大きい状態です。"
        ),
        "Advanced model directions are mixed.": ("高度予測モデルの方向感が割れています。"),
        "At least one advanced model did not improve RMSE over the zero-return baseline.": (
            "少なくとも1つの高度予測モデルはゼロリターン基準よりRMSEが改善していません。"
        ),
        "The audited quantile anchor was unavailable for this forecast.": (
            "監査済みのレンジモデルを利用できないため、別モデルへ縮退しています。"
        ),
        "No model passed the validation gate; the consensus used one fallback model.": (
            "検証条件を通過したモデルがなく、利用可能な1モデルへ縮退しています。"
        ),
        "This horizon is routed by interpolation between the sealed 20-day and 60-day audits.": (
            "20日・60日の封印監査間を補間した予測期間です。信頼度を上限付きで扱います。"
        ),
        "This horizon is outside the sealed 20-day and 60-day audits; confidence is capped low.": (
            "20日・60日の封印監査外の予測期間なので、信頼度を低めに制限しています。"
        ),
        "Some available adapters were excluded from the price-center consensus by the horizon validation policy.": (
            "取得期間と過去検証の条件により、一部モデルを価格中心値の統合から除外しました。"
        ),
    }
    localized_value = value
    for source, target in warning_map.items():
        localized_value = localized_value.replace(source, target)
    warnings = [part.strip() for part in localized_value.split(";") if part.strip()]
    return " / ".join(warning_map.get(warning, warning) for warning in warnings)


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
    confidence_parts = [
        f"データ品質 {ranking_row.get('データ品質', RANKING_MISSING_DISPLAY)}",
        f"条件適合度 {ranking_row.get('条件適合度', RANKING_MISSING_DISPLAY)}",
        f"DB信頼度 {ranking_row.get('DB信頼度', RANKING_MISSING_DISPLAY)}",
    ]
    fundamental_parts = [
        f"配当利回り {ranking_row.get('配当利回り', RANKING_MISSING_DISPLAY)}",
        f"PER {ranking_row.get('PER', RANKING_MISSING_DISPLAY)}",
        f"PBR {ranking_row.get('PBR', RANKING_MISSING_DISPLAY)}",
        f"ROE {ranking_row.get('ROE', RANKING_MISSING_DISPLAY)}",
    ]
    fetched_parts = [
        f"現在株価（円） {ranking_row.get('現在株価（円）', RANKING_MISSING_DISPLAY)}",
        f"時価総額 {ranking_row.get('時価総額', RANKING_MISSING_DISPLAY)}",
        f"出来高 {ranking_row.get('出来高', RANKING_MISSING_DISPLAY)}",
        f"ボラティリティ {ranking_row.get('ボラティリティ', RANKING_MISSING_DISPLAY)}",
    ]
    advanced_value = _ranking_advanced_forecast_display(ranking_row)
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
        *(
            [
                {
                    "観点": ADVANCED_FORECAST_CONSENSUS_LABEL,
                    "内容": advanced_value,
                    "確認ポイント": (
                        "取得期間から決まる共通予測日数のAI予測シナリオです。"
                        "上昇気配・下降警戒へ25%まで反映し、Cockpitの価格レンジと合わせて確認します。"
                    ),
                }
            ]
            if advanced_value
            else []
        ),
        {
            "観点": "評価材料の信頼度",
            "内容": " / ".join(confidence_parts),
            "確認ポイント": "投資魅力度ではなく、評価材料がどれだけそろっているかを確認します。",
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


def _ranking_display_current_price_jpy(
    row: Mapping[str, str],
    symbol_row: Mapping[str, str] | None,
) -> str:
    current_price_jpy = str(row.get("current_price_jpy", "")).strip()
    if current_price_jpy:
        return _ranking_optional_display(current_price_jpy)
    source_currency = str(row.get("current_price_currency", "")).strip().upper()
    if not source_currency and symbol_row is not None:
        source_currency = str(symbol_row.get("currency", "")).strip().upper()
    if source_currency == "JPY":
        return _ranking_optional_display(row.get("current_price", ""))
    return RANKING_MISSING_DISPLAY


def _ranking_display_stock_price(
    row: Mapping[str, str],
    symbol_row: Mapping[str, str] | None,
) -> str:
    source_currency = str(row.get("current_price_currency", "")).strip().upper()
    if not source_currency and symbol_row is not None:
        source_currency = str(symbol_row.get("currency", "")).strip().upper()
    current_price = str(row.get("current_price", "")).strip()
    current_price_jpy = str(row.get("current_price_jpy", "")).strip()
    if not current_price and source_currency == "JPY":
        current_price = current_price_jpy
    if not current_price:
        return RANKING_MISSING_DISPLAY
    return _favorite_price_display(
        current_price,
        currency=source_currency,
        price_jpy=current_price_jpy,
    )


def investment_score_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    symbol_rows_by_symbol = _symbol_universe_rows_by_symbol()
    display_rows: list[dict[str, str]] = []
    for source_row in rows:
        row: dict[str, str] = {
            **source_row,
            **{
                key: str(value)
                for key, value in calculate_reversal_expectation(source_row).as_row().items()
            },
        }
        symbol = row.get("symbol", "")
        symbol_row = symbol_rows_by_symbol.get(symbol.strip().upper())
        display_rows.append(
            {
                "reversal_chart_shape_score": row.get("reversal_chart_shape_score", ""),
                "reversal_forecast_score": row.get("reversal_forecast_score", ""),
                "reversal_safety_score": row.get("reversal_safety_score", ""),
                "reversal_pullback_score": row.get("reversal_pullback_score", ""),
                "reversal_quality_score": row.get("reversal_quality_score", ""),
                "reversal_material_score": row.get("reversal_material_score", ""),
                "pullback_rebound_score": row.get("pullback_rebound_score", ""),
                "bottoming_score": row.get("bottoming_score", ""),
                "range_breakout_score": row.get("range_breakout_score", ""),
                "accumulation_setup_score": row.get("accumulation_setup_score", ""),
                "reversal_expectation_label": row.get("reversal_expectation_label", ""),
                "warnings_raw": row.get("warnings", ""),
                "チャート形状評価": row.get("reversal_chart_shape_score", ""),
                "reversal_pullback_depth": _absolute_numeric_text(row.get("drawdown_20d", "")),
                "調整/安定度": _absolute_numeric_text(row.get("drawdown_20d", "")),
                "調整度スコア": row.get("reversal_pullback_score", ""),
                "上向き余地": row.get("reversal_forecast_score", ""),
                "下落安全性": row.get("reversal_safety_score", ""),
                "data_quality_score": row.get("data_quality_score", ""),
                "reversal_chart_shape_label": row.get("reversal_chart_shape_label", ""),
                "チャート形状": row.get("reversal_chart_shape_label", ""),
                "配当罠警戒": row.get("dividend_trap_warning", ""),
                "reversal_trap_warning": row.get("reversal_trap_warning", ""),
                "dividend_trap_warning": row.get("dividend_trap_warning", ""),
                "dividend_safety_score": row.get("dividend_safety_score", ""),
                "dividend_yield_spike_flag": row.get("dividend_yield_spike_flag", ""),
                "dividend_sustainability_label": row.get("dividend_sustainability_label", ""),
                "順位": row.get("rank", ""),
                "銘柄": symbol,
                "銘柄名": symbol_name(symbol) or "",
                "総合スコア": row.get("total_score", ""),
                "見方": _investment_score_band_label(row.get("score_band", "")),
                "条件適合度": row.get("database_fit_score", ""),
                "Screening": row.get("screening_score", ""),
                "上昇気配": row.get("upside_signal_score", ""),
                "上向き兆候": row.get("reversal_expectation_score", ""),
                "上向き兆候理由": row.get("reversal_expectation_reason", ""),
                "20日高値乖離": row.get("drawdown_20d", ""),
                "5日騰落率": row.get("momentum_5d") or row.get("return_5d", ""),
                "下降警戒": row.get("downside_signal_score", ""),
                "予測変化率": row.get("forecast_return_pct", ""),
                "高度予測": _ranking_optional_display(
                    row.get("advanced_forecast_predicted_return", "")
                ),
                "高度予測日数": (
                    f"{row.get('advanced_forecast_horizon_days')}日"
                    if row.get("advanced_forecast_horizon_days", "")
                    else ""
                ),
                "高度予測スコア": _ranking_optional_display(row.get("advanced_forecast_score", "")),
                "高度予測信頼度": (
                    _advanced_forecast_confidence_label(row.get("advanced_forecast_confidence", ""))
                    if row.get("advanced_forecast_confidence", "")
                    else ""
                ),
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
                "現在株価（円）": _ranking_display_current_price_jpy(row, symbol_row),
                "株価": _ranking_display_stock_price(row, symbol_row),
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


def _absolute_numeric_text(value: object) -> str:
    text = str(value or "").replace("%", "").replace(",", "").strip()
    if not text:
        return ""
    try:
        return format(abs(Decimal(text)).normalize(), "f")
    except (InvalidOperation, ValueError):
        return ""


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
    consensus_match = re.fullmatch(r"advanced_consensus_(\d+)d", series)
    if consensus_match:
        return f"{ADVANCED_FORECAST_CONSENSUS_LABEL} {consensus_match.group(1)}日"
    advanced_match = re.fullmatch(r"(advanced_[a-z_]+)_(\d+)d", series)
    if advanced_match:
        adapter_name = advanced_match.group(1)
        horizon_days = advanced_match.group(2)
        if adapter_name == "advanced_quantile":
            return f"高度予測: レンジモデル {horizon_days}日"
        if adapter_name == "advanced_gbdt_sklearn":
            return f"高度予測: ブースティングモデル {horizon_days}日"
        if adapter_name == "advanced_tree_sklearn":
            return f"高度予測: ツリーモデル {horizon_days}日"
        if adapter_name == "advanced_linear":
            return f"高度予測: 線形モデル {horizon_days}日"
        return f"高度予測: {adapter_name} {horizon_days}日"
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
