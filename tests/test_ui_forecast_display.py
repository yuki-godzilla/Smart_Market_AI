import asyncio
import inspect
import json
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

import ui.app as app_module
from backend.core.config import CONFIG_FILE_ENV
from backend.core.data_contracts import Bar, DailySnapshot, FundamentalSnapshot, FxRate, Symbol
from backend.core.errors import DataSourceError, ProviderUnavailableError
from backend.llm_factor import (
    FakeLLMFactorService,
    LLMFactorCacheMetadata,
    LLMFactorRankingReference,
)
from backend.reporting import build_decision_report_context, build_report_section
from backend.research import (
    CompanyBusinessProfile,
    CompanyOverviewSummary,
    CompanyResearchReport,
    CompanyResearchSummary,
    ETFResearchSummary,
    ExternalResearchFetchManifestEntry,
    ExternalResearchFetchRequest,
    ExternalResearchFetchResult,
    ExternalResearchSourcePayload,
    InvestmentQuestionAnswer,
    InvestmentQuestionSummary,
    IRSummaryItem,
    NewsSummaryItem,
    QuantitativeSummary,
    ResearchBrief,
    ResearchBriefMaterial,
    ResearchBriefSourceCard,
    ResearchDataQuality,
    ResearchDocument,
    ResearchEvidence,
    ResearchExtractedClaim,
    ResearchFactItem,
    ResearchFactSummary,
    ResearchGroundedAnswer,
    ResearchMetric,
    ResearchRetrievalQuality,
    ResearchScoreService,
    ResearchSourceTrace,
    ResearchSummaryPoint,
    StockNewsEvidence,
    StockNewsReport,
)
from backend.screening import ScreeningScore
from ui.app import (
    COCKPIT_SYMBOL_DB_PREFLIGHT_REQUEST_STATE_KEY,
    COCKPIT_SYMBOL_DB_PREFLIGHT_TTL_SECONDS,
    DEFAULT_MARKET_DATA_PERIOD_PRESET,
    LLM_FACTOR_RANKING_COLUMN_TOOLTIPS,
    LLM_FACTOR_RANKING_REFERENCE_NOTICE,
    MARKET_CHART_COMBINED_SPACING,
    MARKET_CHART_FOCUS_WIDTH,
    MARKET_CHART_FULL_WIDTH,
    MARKET_CHART_HEIGHT,
    MARKET_DATA_COCKPIT_FILTER_DEFAULTS,
    MARKET_DATA_EXTERNAL_RESEARCH_FETCH_STATE_KEY,
    MARKET_DATA_PERIOD_CUSTOM,
    MARKET_DATA_PERIOD_PRESETS,
    NO_SYMBOL_CANDIDATE_LABEL,
    RANKING_RESULT_GRID_CUSTOM_CSS,
    RANKING_SYMBOL_DB_PREFLIGHT_SCAN_LIMIT,
    RANKING_TABLE_SORT_GUIDANCE,
    SYMBOL_AUTO_REFRESH_REQUEST_STATE_KEY,
    SYMBOL_DETAIL_DIALOG_CSS,
    SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY,
    RankingResearchStatus,
    _advanced_forecast_consensus_help_text,
    _advanced_forecast_insight_card_html,
    _advanced_forecast_model_help,
    _advanced_forecast_ranking_signal_fields,
    _advanced_forecast_rows_for_ranking,
    _apply_navigation_query_params,
    _background_workers_disabled,
    _build_market_data_ranking_rows,
    _coerce_number_input_state,
    _company_research_ai_notes_html,
    _company_research_summary_html,
    _current_or_default_symbol_labels,
    _default_market_chart_display_currency,
    _dividend_category_filter_label,
    _dividend_category_option_label,
    _dividend_filter_help_text,
    _dividend_yield_filter_label,
    _enrich_ranking_rows_with_advanced_forecast,
    _enrich_ranking_rows_with_feature_details,
    _ensure_selectbox_state_value,
    _etf_question_summary_html,
    _etf_research_summary_html,
    _external_research_fetch_failure_caption,
    _external_research_fetch_overview_html,
    _external_research_fetch_result_rows,
    _external_research_fetch_summary_rows,
    _external_research_source_cards_html,
    _favorite_card_html,
    _fetch_external_research_for_preview,
    _fetch_ranking_ohlcv_tolerant,
    _forecast_model_logic_help,
    _format_market_chart_fx_rate,
    _investment_hint_news_panel_html,
    _investment_insight_panel_html,
    _investment_question_answers_html,
    _investment_question_primary_answers,
    _investment_question_secondary_answers,
    _investment_question_summary_intro_html,
    _ir_summary_html,
    _llm_factor_cache_caption,
    _llm_factor_evidence_display_rows,
    _llm_factor_evidence_sources,
    _llm_factor_panel_html,
    _llm_factor_runtime_html,
    _market_chart_currency_option_label,
    _market_chart_has_displayable_data,
    _market_data_preview_advanced_forecast_consensus_rows,
    _market_data_preview_advanced_forecast_rows,
    _market_data_preview_symbol_label,
    _name_from_candidate,
    _news_source_link_rows,
    _news_source_links_expander_expanded,
    _news_source_links_expander_label,
    _news_source_links_panel_html,
    _news_summary_html,
    _normalize_dividend_filter_state,
    _quantitative_summary_html,
    _ranking_advanced_forecast_fields,
    _ranking_candidate_card_html,
    _ranking_condition_card_html,
    _ranking_condition_summary_html,
    _ranking_data_state_text,
    _ranking_decision_report_state_key,
    _ranking_result_grid_height,
    _ranking_result_grid_key,
    _ranking_result_matches_current_selection,
    _ranking_result_table_base_key,
    _ranking_source_key_for_selection,
    _ranking_symbols_from_selected_labels,
    _render_cockpit_research_summary,
    _render_cockpit_symbol_filter_panel,
    _render_company_research_summary_panel,
    _render_decision_report_download_buttons,
    _render_forecast_chart_filters,
    _render_forecast_model_detail_expanders,
    _render_market_chart,
    _render_price_forecast_hero,
    _render_research_operation_card,
    _render_research_summary_panel,
    _render_score_confidence_hierarchy,
    _request_cockpit_symbol_db_preflight_background,
    _request_symbol_auto_refresh_once,
    _research_brief_focus_html,
    _research_brief_gap_panel_html,
    _research_brief_gap_rows,
    _research_brief_items_html,
    _research_brief_metric_cards_html,
    _research_brief_metric_rows,
    _research_brief_next_action_rows,
    _research_brief_next_actions_html,
    _research_brief_overview_html,
    _research_brief_reading_guide_html,
    _research_brief_reading_guide_rows,
    _research_brief_source_card_rows,
    _research_evidence_card_rows,
    _research_evidence_cards_html,
    _research_evidence_report_section,
    _research_extracted_claim_rows,
    _research_grounded_answer_rows,
    _research_news_warning_display_text,
    _research_operation_insight,
    _research_quality_warning_rows,
    _research_result_overview_html,
    _research_retrieval_quality_rows,
    _research_score_component_rows,
    _research_score_context_caption,
    _research_score_expander_label,
    _research_score_guidance_rows,
    _research_score_report_section,
    _research_score_summary_rows,
    _research_score_warning_rows,
    _research_table_html,
    _research_terms_preview,
    _run_symbol_database_preflight_refresh,
    _select_ranking_symbol_for_cockpit_with_period,
    _stock_news_display_rows,
    _symbol_from_candidate,
    advanced_forecast_consensus_display_rows,
    advanced_forecast_display_rows,
    advanced_forecast_intro_text,
    advanced_forecast_validation_detail_rows,
    build_cockpit_decision_report_context,
    build_llm_factor_reference_display,
    build_ranking_decision_report_context,
    chart_fx_rate_from_rows,
    clear_ranking_detail_condition_state,
    cockpit_decision_report_evidence_rows,
    cockpit_decision_report_overview,
    cockpit_decision_report_summary_lines,
    cockpit_detail_summary_rows,
    cockpit_filter_expander_label,
    cockpit_filter_has_active_conditions_from_values,
    cockpit_filter_summary_chips_from_values,
    cockpit_filter_summary_chips_html,
    cockpit_filtered_symbol_rows,
    cockpit_investment_memo_rows,
    cockpit_keyword_filtered_symbol_rows,
    cockpit_period_evaluation_rows,
    convert_market_chart_rows_currency,
    decision_report_json_download,
    decision_report_markdown_download,
    default_forecast_horizon_days,
    default_market_data_provider,
    filter_forecast_chart_rows,
    forecast_boundary_frame,
    forecast_chart_color_domain,
    forecast_chart_color_range,
    forecast_chart_runtime_series,
    forecast_chart_series_labels,
    forecast_chart_series_options,
    forecast_chart_summary,
    forecast_consensus_display_rows,
    forecast_focus_chart_rows,
    forecast_focus_chart_title,
    forecast_horizon_notice_text,
    forecast_metric_display_rows,
    forecast_metric_summary,
    forecast_model_card_rows,
    forecast_model_cards_html,
    forecast_model_comparison_rows,
    forecast_range_band_frame,
    format_llm_factor_score,
    format_provider_error_details,
    get_cached_ranking_build,
    investment_score_display_rows,
    investment_score_summary_lines,
    latest_actual_price_frame,
    market_chart_long_frame,
    market_data_period_dates,
    market_data_period_help,
    merged_symbol_candidate_rows,
    provider_error_summary_rows,
    ranking_candidate_breakdown_rows,
    ranking_comparison_summary,
    ranking_condition_has_active_detail_from_values,
    ranking_condition_load_state,
    ranking_condition_summary_chips_from_values,
    ranking_condition_summary_chips_html,
    ranking_creation_target_summary_html,
    ranking_detail_event_token_from_aggrid_response,
    ranking_detail_symbol_from_aggrid_response,
    ranking_detail_symbol_to_open,
    ranking_display_rows_with_llm_factor_references,
    ranking_display_rows_with_research_status,
    ranking_favorite_symbol_from_aggrid_response,
    ranking_forecast_term_explanation_rows,
    ranking_investment_detail_rows,
    ranking_investment_note,
    ranking_policy_builder_card_html,
    ranking_research_status_from_documents,
    ranking_research_status_from_report,
    ranking_result_aggrid_frame,
    ranking_result_aggrid_options,
    ranking_score_bar_chart_caption,
    ranking_score_bar_chart_frame,
    ranking_score_confidence_frame,
    ranking_score_detail_rows,
    ranking_selected_detail_memo_rows,
    ranking_summary_cards,
    ranking_symbol_db_preflight_limit,
    ranking_symbol_db_preflight_symbols,
    ranking_top_candidate_cards,
    reversal_expectation_cap_rows,
    reversal_expectation_component_rows,
    reversal_expectation_pullback_rows,
    score_component_rows,
    score_confidence_hierarchy_rows,
    selected_symbol_has_universe_detail,
    set_cached_ranking_build,
    simple_forecast_baseline_comparison_rows,
    symbol_auto_refresh_request_key,
    symbol_candidate_label,
    symbol_detail_table_html,
    symbol_universe_cache_notice,
    symbol_universe_cache_status_text,
    symbol_universe_data_info_rows,
    symbol_universe_detail_display_value,
    symbol_universe_detail_rows,
    symbol_universe_fund_detail_rows,
    symbol_universe_investment_metric_rows,
    symbol_universe_key_metric_rows,
    symbol_universe_missing_key_fields_display,
    symbol_universe_nisa_display,
    symbol_universe_overview_rows,
)
from ui.ranking import (
    RANKING_BETA_RISK_LABELS,
    RANKING_BETA_RISK_STANDARD_OR_LOWER,
    RANKING_CRITERIA_GUIDE_ROWS,
    RANKING_DIVIDEND_LABELS,
    RANKING_FETCH_LIMIT_BALANCED,
    RANKING_FETCH_LIMIT_FAST,
    RANKING_FETCH_LIMIT_PRESET,
    RANKING_FILTER_HELP_TEXTS,
    RANKING_INDEX_FAMILY_LABELS,
    RANKING_INVESTMENT_STYLE_METRICS,
    RANKING_INVESTMENT_THEME_LABELS,
    RANKING_MARKET_CAP_LABELS,
    RANKING_MVP_PRODUCT_TYPE_LABELS,
    RANKING_NISA_ELIGIBILITY_LABELS,
    RANKING_OFFICIAL_SECTOR_LABELS,
    RANKING_PERIOD_PRESETS,
    RANKING_PRESET_ETF_CORE_COST,
    RANKING_PRESET_ETF_INCOME,
    RANKING_PRESET_MIN_VOLATILITY,
    RANKING_PRESET_MULTI_FACTOR,
    RANKING_PRESET_NISA_LONG_TERM,
    RANKING_PRESET_QUALITY_GROWTH,
    RANKING_PRESET_QUALITY_VALUE,
    RANKING_PRESET_REVERSAL_EXPECTATION,
    RANKING_PRESET_RISK_ADJUSTED,
    RANKING_PRESET_SMALL_GROWTH,
    RANKING_PRESET_SORT_DIVIDEND_YIELD,
    RANKING_PRESET_SORT_PBR,
    RANKING_PRESET_SORT_PER,
    RANKING_PRESET_SUSTAINABLE_INCOME,
    RANKING_PRESET_UPSIDE_SIGNAL,
    RANKING_PRODUCT_ETF,
    RANKING_PURPOSE_DATA_CONFIDENCE,
    RANKING_PURPOSE_DIVIDEND,
    RANKING_PURPOSE_DOWNSIDE_SIGNAL,
    RANKING_PURPOSE_ETF_CORE_COST,
    RANKING_PURPOSE_ETF_INCOME,
    RANKING_PURPOSE_GROWTH,
    RANKING_PURPOSE_MIN_VOLATILITY,
    RANKING_PURPOSE_MOMENTUM,
    RANKING_PURPOSE_MULTI_FACTOR,
    RANKING_PURPOSE_NISA_LONG_TERM,
    RANKING_PURPOSE_QUALITY_GROWTH,
    RANKING_PURPOSE_QUALITY_VALUE,
    RANKING_PURPOSE_REVERSAL_EXPECTATION,
    RANKING_PURPOSE_RISK_ADJUSTED,
    RANKING_PURPOSE_SMALL_GROWTH,
    RANKING_PURPOSE_SORT_DATA_QUALITY,
    RANKING_PURPOSE_SORT_DIVIDEND_YIELD,
    RANKING_PURPOSE_SORT_MARKET_CAP,
    RANKING_PURPOSE_SORT_PBR,
    RANKING_PURPOSE_SORT_PER,
    RANKING_PURPOSE_SORT_RISK,
    RANKING_PURPOSE_SORT_ROE,
    RANKING_PURPOSE_SORT_TOTAL_SCORE,
    RANKING_PURPOSE_SORT_VOLATILITY,
    RANKING_PURPOSE_SORT_VOLUME,
    RANKING_PURPOSE_STABILITY,
    RANKING_PURPOSE_SUSTAINABLE_INCOME,
    RANKING_PURPOSE_TREND,
    RANKING_PURPOSE_UPSIDE_SIGNAL,
    RANKING_PURPOSE_VALUE,
    RANKING_THEME_LABELS,
    RANKING_WEIGHT_PRESETS,
    apply_ranking_weight_preset,
    filter_symbol_universe_rows,
    initial_ranking_selected_labels,
    limited_ranking_selected_labels,
    live_ranking_symbol_warning_message,
    normalize_dividend_filter_values,
    rank_investment_score_rows,
    ranking_build_cache_key,
    ranking_database_fit_score,
    ranking_deep_dive_default_symbol,
    ranking_deep_dive_symbol_options,
    ranking_detail_filters_for_category,
    ranking_filter_signature,
    ranking_metadata_confidence_score,
    ranking_no_bars_error_row,
    ranking_period_dates,
    ranking_period_label,
    ranking_policy_description,
    ranking_policy_for_purpose,
    ranking_policy_label,
    ranking_policy_options,
    ranking_product_type_label,
    ranking_provider_error_rows,
    ranking_purpose_focus_summary,
    ranking_purpose_help,
    ranking_purpose_options,
    ranking_purpose_primary_columns,
    ranking_purpose_weight_summary,
    ranking_symbol_chunks,
    ranking_symbol_options,
    ranking_symbols_state_key,
    ranking_weight_group_rows,
    ranking_weight_preset_for_purpose,
    ranking_weight_preset_label,
    symbol_candidate_labels,
    symbol_universe_filter_value_counts,
    symbol_universe_rows,
    valid_ranking_selected_labels,
)
from ui.ranking_state import (
    apply_ranking_filter_state,
    clear_ranking_filter_state,
    current_ranking_filter_state,
    ensure_ranking_selection_widget_state,
    initial_ranking_selected_labels_for_key,
    persist_ranking_filter_state,
    sync_ranking_selection_state,
)
from ui.rebalance_app import (
    MarketDataPreview,
    forecast_consensus_rows_for_bars,
    forecast_metric_csv_download,
    forecast_metric_json_download,
    forecast_reference_period,
    investment_score_csv_download,
    screening_score_rows,
)
from ui.research_state import (
    _source_type_from_research_filename,
    _symbol_from_research_filename,
    external_research_fetch_cache_info,
    external_research_fetch_last_summary,
    fetch_external_research_for_symbol,
)
from ui.styles import FORECAST_ACTUAL_PRICE_COLOR, FORECAST_MODEL_COLORS, THEME_COLORS
from ui.symbol_universe import symbol_universe_csv_rows


class _FakeExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


pytest = __import__("pytest")


def test_favorite_card_html_groups_watchlist_fields_and_handles_missing_values():
    markup = _favorite_card_html(
        {
            "symbol": "NVDA",
            "name": "NVIDIA",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
            "added_at": "2026-06-27",
            "last_checked_at": "2026-06-27T20:00:00+09:00",
            "status": "上昇候補",
            "status_label": "上昇傾向",
            "refresh_status": "failed",
            "refresh_label": "前回失敗",
            "refresh_next_action": "",
            "checkpoint": "",
            "tags": "",
            "memo": "",
            "watch_reason": "AI関連として確認",
            "decision_status": "監視中",
            "decision_note": "決算前後の値動きを確認",
            "next_check_label": "次回決算",
            "decision_updated_label": "2026/06/27 20:00",
            "related_news": "あり",
            "dividend_yield": "0.03%",
            "per": "42.1",
            "pbr": "38.4",
            "roe": "91.2%",
            "market_cap": "$3.8T",
            "sector": "Technology",
        }
    )

    assert 'class="smai-watchlist-card ' in markup
    assert "NVDA" in markup
    assert markup.index("NVIDIA") < markup.index("NVDA")
    assert "上昇傾向" in markup
    assert "前回失敗" in markup
    assert "判断メモ" not in markup
    assert "AI関連として確認" not in markup
    assert "smai-watchlist-status--upside" in markup
    assert "smai-watchlist-refresh--failed" in markup
    assert "価格" in markup
    assert "AI総合" in markup
    assert "価格データなし" in markup
    assert "AI評価なし" in markup
    assert "更新: <strong>6/27 20:00 JST" in markup
    assert "詳細指標" in markup
    assert all(
        label in markup for label in ("配当利回り", "PER", "PBR", "ROE", "時価総額", "セクター")
    )
    assert "次の確認" not in markup
    assert "確認ポイント" not in markup


def test_favorite_display_payload_formats_fundamentals_and_jst_dates():
    favorite = app_module.FavoriteStock(
        symbol="8750.T",
        name="第一生命グループ",
        market="jp",
        asset_type="stock",
        currency="JPY",
        added_at="2026-07-02T21:35:48+09:00",
        last_checked_at="2026-07-04T16:58:36+09:00",
    )

    payload = app_module._favorite_display_payload(
        favorite,
        {
            "8750.T": {
                "dividend_yield_pct": "3.80",
                "per": "12.40",
                "pbr": "0.92",
                "roe_pct": "8.20",
                "market_cap": "4300000000000",
                "sector": "insurance",
            }
        },
    )

    assert app_module._format_watchlist_added_date(payload["added_at"]) == "2026/07/02"
    assert app_module._format_watchlist_updated_at(payload["last_checked_at"]) == "7/4 16:58 JST"
    assert payload["dividend_yield"] == "3.8%"
    assert payload["per"] == "12.4"
    assert payload["pbr"] == "0.92"
    assert payload["roe"] == "8.2%"
    assert payload["market_cap"] == "4.3兆円"
    assert payload["sector"] == "保険"


def test_favorite_display_payload_prefers_jpy_and_keeps_original_currency():
    favorite = app_module.FavoriteStock(
        symbol="NVDA",
        name="NVIDIA",
        market="us",
        asset_type="stock",
        currency="USD",
    )

    payload = app_module._favorite_display_payload(
        favorite,
        {"NVDA": {"price": "182.45", "current_price_jpy": "27367.5", "currency": "USD"}},
    )

    assert payload["price"] == "27,368円（182.45 USD）"


def test_favorite_display_payload_marks_missing_fx_without_hiding_original_price():
    favorite = app_module.FavoriteStock(
        symbol="NVDA",
        name="NVIDIA",
        market="us",
        asset_type="stock",
        currency="USD",
    )

    payload = app_module._favorite_display_payload(
        favorite,
        {"NVDA": {"price": "182.45", "currency": "USD"}},
    )

    assert payload["price"] == "—円（182.45 USD）"


def test_favorite_card_html_compacts_empty_decision_trail():
    markup = _favorite_card_html(
        {
            "symbol": "5932.T",
            "name": "三協立山",
            "market": "jp",
            "asset_type": "stock",
            "currency": "JPY",
            "added_at": "2026-06-27",
            "status": "未取得",
            "refresh_status": "never_checked",
            "refresh_label": "未確認",
            "watch_reason": "未入力",
            "decision_status": "未設定",
            "decision_note": "未入力",
            "next_check_at": "",
            "next_check_label": "未設定",
            "decision_updated_label": "未更新",
        }
    )

    assert "smai-watchlist-decision-empty" not in markup
    assert "判断メモ</span><strong>未入力" not in markup
    assert "Watch理由" not in markup
    assert "現在の見方" not in markup
    assert "最終更新" not in markup


def test_favorite_radar_summary_html_renders_compact_counts():
    markup = app_module._favorite_radar_summary_html(
        [
            ("今日見る", 3),
            ("要確認", 1),
            ("更新推奨", 2),
            ("メモ未入力", 3),
            ("下落注意", 0),
        ]
    )

    assert 'class="smai-watchlist-radar-grid"' in markup
    assert markup.count('class="smai-watchlist-radar-item"') == 5
    assert "今日見る" in markup
    assert "更新推奨" in markup
    assert "下落注意" in markup


@pytest.mark.parametrize(
    ("one_day", "five_day", "one_month", "expected"),
    [
        ("2.1", "4.8", "9.2", "上昇傾向"),
        ("0.2", "1.2", "2.0", "短期上昇"),
        ("0.1", "-0.3", "0.8", "横ばい"),
        ("-1.4", "-3.2", "-5.6", "下落注意"),
        ("-5.1", "-2.0", "-3.0", "急落警戒"),
        ("", None, "NaN", "未取得"),
    ],
)
def test_favorite_movement_status_handles_changes_and_missing_values(
    one_day,
    five_day,
    one_month,
    expected,
):
    assert app_module._favorite_movement_status(one_day, five_day, one_month) == expected


def test_favorite_change_value_distinguishes_ratio_and_percent_fields():
    assert (
        app_module._favorite_change_value(
            {"return_5d": "0.048"},
            "price_change_5d",
            "return_5d",
        )
        == "4.8"
    )
    assert (
        app_module._favorite_change_value(
            {"price_change_5d": "0.4"},
            "price_change_5d",
            "return_5d",
        )
        == "0.4"
    )


def test_favorite_card_html_adds_movement_accent_and_missing_data_hint():
    markup = _favorite_card_html(
        {
            "symbol": "5932.T",
            "name": "三協立山",
            "status": "未取得",
            "status_label": "判定保留",
            "refresh_status": "never_checked",
            "movement_status": "未取得",
            "price": "未取得",
            "ai_score": "未取得",
            "upside": "未取得",
            "downside": "未取得",
        }
    )

    assert "smai-watchlist-card--unknown" in markup
    assert "…</strong><span>値動きデータなし" in markup
    assert "データ更新が必要です" in markup
    assert "ウォッチリスト更新で価格・AI評価・ニュース状態を確認できます。" in markup


def test_watchlist_ranking_detail_row_reuses_snapshot_values():
    row = app_module._watchlist_ranking_detail_row(
        {
            "symbol": "9432.T",
            "name": "NTT",
            "price": "144.3円",
            "ai_score": "68.63",
            "upside": "44.36",
            "downside": "57.39",
            "snapshot_status": "ok",
            "checkpoint": "ニュースを確認",
        }
    )

    assert row == {
        "銘柄": "9432.T",
        "銘柄名": "NTT",
        "現在株価": "144.3円",
        "総合スコア": "68.63",
        "上昇気配": "44.36",
        "下降警戒": "57.39",
        "データ品質": "ok",
        "確認ポイント": "ニュースを確認",
    }


def test_watchlist_background_refresh_candidates_prioritize_and_limit_with_ttl():
    now = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
    rows = [
        {
            "symbol": "FRESH",
            "price": "100",
            "ai_score": "50",
            "upside": "50",
            "downside": "20",
            "refresh_status": "fresh",
            "last_checked_at": "2026-06-27T10:00:00+00:00",
        },
        {
            "symbol": "STALE",
            "price": "100",
            "ai_score": "50",
            "upside": "50",
            "downside": "20",
            "refresh_status": "stale",
            "last_checked_at": "2026-06-26T00:00:00+00:00",
        },
        {
            "symbol": "FAILED",
            "price": "100",
            "ai_score": "50",
            "upside": "50",
            "downside": "20",
            "refresh_status": "failed",
            "last_checked_at": "",
        },
        {
            "symbol": "MISSING",
            "price": "未取得",
            "ai_score": "未取得",
            "upside": "未取得",
            "downside": "未取得",
            "refresh_status": "never_checked",
            "last_checked_at": "",
        },
        {
            "symbol": "ATTENTION",
            "price": "100",
            "ai_score": "50",
            "upside": "50",
            "downside": "20",
            "refresh_status": "needs_attention",
            "last_checked_at": "2026-06-26T00:00:00+00:00",
        },
    ]

    assert app_module._watchlist_background_refresh_candidates(
        rows,
        now=now,
        max_items=3,
    ) == ["MISSING", "FAILED", "STALE"]


def test_favorite_filter_counts_match_the_same_filter_predicates():
    rows = [
        {
            "symbol": "UP",
            "status": "短期上昇",
            "refresh_status": "fresh",
            "radar_categories": "",
        },
        {
            "symbol": "DOWN",
            "status": "急落警戒",
            "refresh_status": "failed",
            "radar_categories": "調査候補 / メモ未入力候補",
        },
    ]

    assert app_module._favorite_filter_count(rows, "すべて") == 2
    assert app_module._favorite_filter_count(rows, "上昇傾向") == 1
    assert app_module._favorite_filter_count(rows, "下落注意") == 1
    assert app_module._favorite_filter_count(rows, "前回失敗") == 1
    assert app_module._favorite_filter_count(rows, "メモ未入力") == 1
    assert app_module._favorite_filter_count(rows, "AI調査候補") == 1


def test_request_watchlist_background_refresh_runs_once_and_respects_provider(monkeypatch):
    session_state = {}
    requests: list[tuple[list[str], str, int]] = []
    rows = [
        {
            "symbol": "MISSING",
            "price": "未取得",
            "ai_score": "未取得",
            "upside": "未取得",
            "downside": "未取得",
            "refresh_status": "never_checked",
            "last_checked_at": "",
        }
    ]

    monkeypatch.setattr(app_module.st, "session_state", session_state)
    monkeypatch.setattr(app_module, "_background_workers_disabled", lambda: False)
    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(dataaccess=SimpleNamespace(allow_external_providers=False)),
    )
    monkeypatch.setattr(
        app_module,
        "request_symbol_background_refresh",
        lambda symbols, *, source, max_items: (
            requests.append((list(symbols), source, max_items)) or list(symbols)
        ),
    )

    app_module._request_watchlist_background_refresh_once(rows)
    app_module._request_watchlist_background_refresh_once(rows)

    assert requests == [(["MISSING"], "watchlist", 3)]
    assert session_state[app_module.WATCHLIST_BACKGROUND_REFRESH_STATE_KEY] == {
        "status": "local_only",
        "symbols": ["MISSING"],
    }


def test_request_watchlist_background_refresh_stays_off_when_workers_disabled(monkeypatch):
    session_state = {}
    monkeypatch.setattr(app_module.st, "session_state", session_state)
    monkeypatch.setattr(app_module, "_background_workers_disabled", lambda: True)
    monkeypatch.setattr(
        app_module,
        "request_symbol_background_refresh",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("queue should not run")),
    )

    app_module._request_watchlist_background_refresh_once(
        [{"symbol": "NVDA", "refresh_status": "never_checked"}]
    )

    assert session_state[app_module.WATCHLIST_BACKGROUND_REFRESH_STATE_KEY] == {
        "status": "disabled",
        "symbols": [],
    }


def test_watchlist_snapshot_refresh_targets_prioritize_missing_failed_and_stale():
    now = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
    rows = [
        {"symbol": "FRESH", "refresh_status": "fresh"},
        {"symbol": "STALE", "refresh_status": "fresh"},
        {"symbol": "FAILED", "refresh_status": "fresh"},
        {"symbol": "MISSING", "refresh_status": "fresh"},
    ]
    snapshots = {
        "FRESH": app_module.WatchlistSnapshot(
            symbol="FRESH",
            status="ok",
            last_snapshot_at="2026-06-27T10:00:00+00:00",
        ),
        "STALE": app_module.WatchlistSnapshot(
            symbol="STALE",
            status="ok",
            last_snapshot_at="2026-06-26T10:00:00+00:00",
        ),
        "FAILED": app_module.WatchlistSnapshot(
            symbol="FAILED",
            status="failed",
            last_snapshot_at="2026-06-27T10:00:00+00:00",
        ),
    }

    assert app_module._watchlist_snapshot_refresh_targets(
        rows,
        snapshots,
        max_items=3,
        now=now,
    ) == ["MISSING", "FAILED", "STALE"]


def test_refresh_watchlist_snapshots_uses_local_rows_when_live_provider_disabled(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(
            dataaccess=SimpleNamespace(
                provider="yahoo",
                allow_external_providers=False,
            )
        ),
    )
    monkeypatch.setattr(
        app_module,
        "create_market_data_provider_adapter",
        lambda *_: (_ for _ in ()).throw(AssertionError("live provider should not run")),
    )
    monkeypatch.setattr(
        app_module,
        "save_watchlist_snapshots",
        lambda snapshots: saved.update(snapshots),
    )

    result = asyncio.run(
        app_module._refresh_watchlist_snapshots(
            ["7203.T"],
            favorites=[app_module.FavoriteStock(symbol="7203.T", name="トヨタ自動車")],
            computed_rows={
                "7203.T": {
                    "symbol": "7203.T",
                    "currency": "JPY",
                    "price": "3120",
                    "総合スコア": "74",
                    "上昇気配": "61",
                    "下降警戒": "45",
                }
            },
            previous_snapshots={},
        )
    )

    assert result == {
        "success_symbols": ["7203.T"],
        "failed_symbols": [],
        "previous_data_symbols": [],
    }
    assert saved["7203.T"].price == 3120.0
    assert saved["7203.T"].ai_score == 74.0


def test_refresh_watchlist_snapshots_fetches_ohlcv_when_live_provider_enabled(monkeypatch):
    saved = {}
    fetched: list[tuple[list[str], datetime, datetime]] = []

    class FakeAdapter:
        async def fetch_ohlcv(self, symbols, *, start, end):
            fetched.append((list(symbols), start, end))
            return [
                _bar(f"2026-06-{day:02d}", close=100 + day, symbol="7203.T") for day in range(1, 22)
            ]

    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(
            dataaccess=SimpleNamespace(
                provider="yahoo",
                allow_external_providers=True,
            )
        ),
    )
    monkeypatch.setattr(
        app_module,
        "create_market_data_provider_adapter",
        lambda *_: FakeAdapter(),
    )
    monkeypatch.setattr(
        app_module,
        "save_watchlist_snapshots",
        lambda snapshots: saved.update(snapshots),
    )

    result = asyncio.run(
        app_module._refresh_watchlist_snapshots(
            ["7203.T"],
            favorites=[app_module.FavoriteStock(symbol="7203.T", currency="JPY")],
            computed_rows={"7203.T": {"symbol": "7203.T", "currency": "JPY"}},
            previous_snapshots={},
        )
    )

    assert result["success_symbols"] == ["7203.T"]
    assert fetched and fetched[0][0] == ["7203.T"]
    assert saved["7203.T"].price == 121.0
    assert saved["7203.T"].price_change_1m == pytest.approx(19.802, abs=0.0001)
    assert saved["7203.T"].source == "yahoo"


def test_refresh_watchlist_snapshots_reuses_cockpit_preview_for_scores(monkeypatch):
    saved = {}

    async def fake_preview(**_):
        return SimpleNamespace(
            bars=[
                _bar(f"2026-06-{day:02d}", close=100 + day, symbol="6367.T") for day in range(1, 22)
            ],
            investment_score_rows=[
                {
                    "symbol": "6367.T",
                    "total_score": "72.5",
                    "upside_signal_score": "64",
                    "downside_signal_score": "38",
                }
            ],
        )

    monkeypatch.setattr(
        app_module,
        "get_settings",
        lambda: SimpleNamespace(
            dataaccess=SimpleNamespace(
                provider="yahoo",
                allow_external_providers=True,
            )
        ),
    )
    monkeypatch.setattr(
        app_module,
        "create_market_data_provider_adapter",
        lambda *_: object(),
    )
    monkeypatch.setattr(app_module, "build_market_data_preview", fake_preview)
    monkeypatch.setattr(
        app_module,
        "save_watchlist_snapshots",
        lambda snapshots: saved.update(snapshots),
    )

    result = asyncio.run(
        app_module._refresh_watchlist_snapshots(
            ["6367.T"],
            favorites=[app_module.FavoriteStock(symbol="6367.T", currency="JPY")],
            computed_rows={"6367.T": {"symbol": "6367.T", "currency": "JPY"}},
            previous_snapshots={},
            include_scores=True,
        )
    )

    assert result["success_symbols"] == ["6367.T"]
    assert saved["6367.T"].price == 121.0
    assert saved["6367.T"].ai_score == 72.5
    assert saved["6367.T"].upside_score == 64.0
    assert saved["6367.T"].downside_risk_score == 38.0


def test_watchlist_all_refresh_targets_keeps_all_unique_symbols_in_display_order():
    rows = [
        {"symbol": " aaa "},
        {"symbol": "BBB"},
        {"symbol": "AAA"},
        {"symbol": ""},
        {"symbol": "ccc"},
    ]

    assert app_module._watchlist_all_refresh_targets(rows) == ["AAA", "BBB", "CCC"]


def test_run_watchlist_auto_snapshot_once_refreshes_all_targets_and_runs_once(monkeypatch):
    session_state = {}
    refresh_calls: list[list[str]] = []
    slot = SimpleNamespace(container=lambda: nullcontext(), empty=lambda: None)

    async def fake_refresh(symbols, **_):
        refresh_calls.append(list(symbols))
        return {
            "success_symbols": list(symbols[:2]),
            "failed_symbols": list(symbols[2:]),
            "previous_data_symbols": list(symbols[2:]),
        }

    monkeypatch.setattr(app_module.st, "session_state", session_state)
    monkeypatch.setattr(app_module.st, "empty", lambda: slot)
    monkeypatch.setattr(app_module, "_background_workers_disabled", lambda: False)
    monkeypatch.setattr(app_module, "_refresh_watchlist_snapshots", fake_refresh)
    monkeypatch.setattr(app_module, "render_mascot_loading", lambda *_, **__: None)

    rows = [{"symbol": symbol} for symbol in ["AAA", "BBB", "CCC", "DDD"]]
    first = app_module._run_watchlist_auto_snapshot_once(
        rows,
        favorites=[],
        computed_rows={},
        snapshots={},
    )
    second = app_module._run_watchlist_auto_snapshot_once(
        rows,
        favorites=[],
        computed_rows={},
        snapshots={},
    )

    assert first is True
    assert second is False
    assert refresh_calls == [["AAA", "BBB", "CCC", "DDD"]]
    assert session_state[app_module.WATCHLIST_AUTO_SNAPSHOT_STATE_KEY]["requested"] == 4
    assert session_state[app_module.WATCHLIST_AUTO_SNAPSHOT_STATE_KEY]["success"] == 2


def test_render_segmented_or_radio_uses_segmented_control_when_available(monkeypatch):
    calls: list[tuple[str, list[str], str, str]] = []

    def fake_segmented(label, options, *, default, key):
        calls.append((label, options, default, key))
        return "要確認"

    monkeypatch.setattr(app_module.st, "segmented_control", fake_segmented, raising=False)
    monkeypatch.setattr(
        app_module.st,
        "radio",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("radio should not run")),
    )

    selected = app_module._render_segmented_or_radio(
        "表示フィルター",
        ["すべて", "要確認"],
        default="すべて",
        key="favorite_filter",
    )

    assert selected == "要確認"
    assert calls == [("表示フィルター", ["すべて", "要確認"], "すべて", "favorite_filter")]


def test_render_segmented_or_radio_falls_back_to_radio(monkeypatch):
    calls: list[tuple[str, list[str], int, bool, str]] = []

    def fake_radio(label, options, *, index, horizontal, key):
        calls.append((label, options, index, horizontal, key))
        return options[index]

    monkeypatch.delattr(app_module.st, "segmented_control", raising=False)
    monkeypatch.setattr(app_module.st, "radio", fake_radio)

    selected = app_module._render_segmented_or_radio(
        "表示フィルター",
        ["すべて", "要確認"],
        default="存在しない値",
        horizontal=True,
        key="favorite_filter",
    )

    assert selected == "すべて"
    assert calls == [("表示フィルター", ["すべて", "要確認"], 0, True, "favorite_filter")]


def test_favorite_filter_and_sort_rows_applies_selected_controls(monkeypatch):
    captions: list[str] = []
    rows = [
        {"symbol": "ZZZ", "refresh_status": "fresh"},
        {"symbol": "BBB", "refresh_status": "needs_attention"},
        {"symbol": "AAA", "refresh_status": "needs_attention"},
    ]

    monkeypatch.setattr(
        app_module.st,
        "columns",
        lambda _: [_FakeExpander(), _FakeExpander()],
    )
    monkeypatch.setattr(
        app_module,
        "_render_segmented_or_radio",
        lambda *_, **__: "要確認",
    )
    monkeypatch.setattr(
        app_module.st,
        "selectbox",
        lambda *_, **__: "銘柄コード順",
    )
    monkeypatch.setattr(
        app_module.st,
        "caption",
        lambda text: captions.append(text),
    )

    selected = app_module._favorite_filter_and_sort_rows(rows)

    assert [row["symbol"] for row in selected] == ["AAA", "BBB"]
    assert captions[-1] == "表示中: 2件 / 全体 3件"


def test_default_forecast_horizon_days_uses_chart_period():
    assert default_forecast_horizon_days(date(2026, 5, 1), date(2026, 5, 7)) == 1
    assert default_forecast_horizon_days(date(2026, 5, 1), date(2026, 5, 30)) == 3
    assert default_forecast_horizon_days(date(2026, 1, 1), date(2026, 12, 31)) == 30
    assert default_forecast_horizon_days(date(2021, 5, 23), date(2026, 5, 23)) == 60


def test_market_data_period_dates_support_decision_review_presets():
    end = date(2026, 5, 23)

    assert DEFAULT_MARKET_DATA_PERIOD_PRESET == MARKET_DATA_PERIOD_CUSTOM
    assert next(iter(MARKET_DATA_PERIOD_PRESETS)) == MARKET_DATA_PERIOD_CUSTOM
    assert market_data_period_dates(MARKET_DATA_PERIOD_CUSTOM, end) == (
        date(2025, 5, 23),
        end,
    )
    assert market_data_period_dates("short_1w", end) == (date(2026, 5, 16), end)
    assert market_data_period_dates("short_1m", end) == (date(2026, 4, 23), end)
    assert market_data_period_dates("medium_3m", end) == (date(2026, 2, 23), end)
    assert market_data_period_dates("medium_6m", end) == (date(2025, 11, 23), end)
    assert market_data_period_dates("ytd", end) == (date(2026, 1, 1), end)
    assert market_data_period_dates("long_1y", end) == (date(2025, 5, 23), end)
    assert market_data_period_dates("long_3y", end) == (date(2023, 5, 23), end)
    assert market_data_period_dates("long_5y", end) == (date(2021, 5, 23), end)


def test_market_data_period_dates_clamp_month_end_and_leap_day():
    assert market_data_period_dates("short_1m", date(2026, 3, 31))[0] == date(
        2026,
        2,
        28,
    )
    assert market_data_period_dates("long_1y", date(2024, 2, 29))[0] == date(
        2023,
        2,
        28,
    )


def test_market_data_period_help_explains_review_basis():
    assert "任意の期間" in market_data_period_help(MARKET_DATA_PERIOD_CUSTOM)
    assert "決算" in market_data_period_help("medium_3m")
    assert "長期保有" in market_data_period_help("long_5y")
    assert "任意の期間" in market_data_period_help("unknown")


def test_market_data_provider_defaults_to_yahoo_without_config(monkeypatch):
    monkeypatch.delenv(CONFIG_FILE_ENV, raising=False)

    assert default_market_data_provider() == "yahoo"


def test_market_data_provider_uses_configured_mock(monkeypatch):
    monkeypatch.setattr(
        "ui.app.get_settings",
        lambda: SimpleNamespace(dataaccess=SimpleNamespace(provider="mock")),
    )

    assert default_market_data_provider() == "mock"


def test_market_data_provider_defaults_to_configured_live_provider(monkeypatch):
    monkeypatch.setattr(
        "ui.app.get_settings",
        lambda: SimpleNamespace(dataaccess=SimpleNamespace(provider="yahoo")),
    )

    assert default_market_data_provider() == "yahoo"


def test_symbol_from_candidate_extracts_ticker_or_custom():
    assert _symbol_from_candidate("") is None
    assert _symbol_from_candidate("9983.T - Fast Retailing") == "9983.T"


def test_selected_symbol_has_universe_detail_uses_local_master(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [{"symbol": "9983.T", "name": "Fast Retailing"}],
    )

    assert selected_symbol_has_universe_detail("9983.t")
    assert not selected_symbol_has_universe_detail("MSFT")


def test_ranking_symbols_from_selected_labels_extracts_fetch_symbols():
    assert _ranking_symbols_from_selected_labels(
        ["9983.T - Fast Retailing", "", "AAPL - Apple Inc."]
    ) == ["9983.T", "AAPL"]


def test_name_from_candidate_extracts_display_name():
    assert _name_from_candidate("9983.T - Fast Retailing") == "Fast Retailing"
    assert _name_from_candidate("AAPL") is None


def test_market_data_preview_symbol_label_uses_symbol_and_known_name():
    preview = SimpleNamespace(
        bars=[
            _bar("2026-05-10", symbol="9983.T"),
        ],
        screening_rows=[],
        ohlcv_rows=[],
        quote_rows=[],
        feature_rows=[],
    )

    assert _market_data_preview_symbol_label(preview) == "9983.T - Fast Retailing"


def test_market_data_preview_symbol_label_falls_back_to_rows():
    preview = SimpleNamespace(
        bars=[],
        screening_rows=[{"symbol": "CUSTOM"}],
        ohlcv_rows=[],
        quote_rows=[],
        feature_rows=[],
    )

    assert _market_data_preview_symbol_label(preview) == "CUSTOM"


def test_market_data_preview_advanced_forecast_rows_tolerates_legacy_state():
    legacy_preview = SimpleNamespace(bars=[])
    current_preview = SimpleNamespace(
        advanced_forecast_rows=[{"horizon_days": "5", "forecast_close": "101"}]
    )

    assert _market_data_preview_advanced_forecast_rows(legacy_preview) == []
    assert _market_data_preview_advanced_forecast_rows(current_preview) == [
        {"horizon_days": "5", "forecast_close": "101"}
    ]
    assert _market_data_preview_advanced_forecast_rows(current_preview, horizon_days=5) == [
        {"horizon_days": "5", "forecast_close": "101"}
    ]


def test_market_data_preview_advanced_forecast_rows_recomputes_for_common_horizon():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = [
        _bar((start + timedelta(days=index)).date().isoformat(), close=100 + index)
        for index in range(90)
    ]
    preview = SimpleNamespace(
        bars=bars,
        advanced_forecast_rows=[{"horizon_days": "5", "forecast_close": "101"}],
    )

    rows = _market_data_preview_advanced_forecast_rows(preview, horizon_days=10)

    assert {row["adapter"] for row in rows} == {
        "advanced_linear",
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
        "advanced_quantile",
    }
    assert {row["horizon_days"] for row in rows} == {"10"}


def test_market_data_preview_advanced_forecast_consensus_rows_recompute_common_horizon():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = [
        _bar((start + timedelta(days=index)).date().isoformat(), close=100 + index)
        for index in range(90)
    ]
    preview = SimpleNamespace(
        bars=bars,
        advanced_forecast_consensus_rows=[{"horizon_days": "5", "predicted_return": "1%"}],
    )

    rows = _market_data_preview_advanced_forecast_consensus_rows(
        preview,
        [],
        horizon_days=10,
    )

    assert rows[0]["horizon_days"] == "10"
    assert rows[0]["model_count"] == "4"
    assert rows[0]["predicted_return"]
    assert rows[0]["forecast_close"]
    assert rows[0]["direction_agreement_score"]
    assert rows[0]["confidence"] in {"low", "medium", "high"}


def test_merged_symbol_candidate_rows_deduplicates_representative_first():
    rows = merged_symbol_candidate_rows(
        [{"symbol": "AAPL", "name": "Apple Inc."}],
        [
            {"symbol": "aapl", "name": "Apple"},
            {"symbol": "MSFT", "name": "Microsoft"},
        ],
    )

    assert rows == [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "MSFT", "name": "Microsoft"},
    ]


def test_cockpit_search_exact_symbol_ranks_above_partial_matches():
    rows = [
        {"symbol": "RYAAY", "name": "Ryanair"},
        {"symbol": "RY", "name": "Royal Bank of Canada"},
        {"symbol": "ARRY", "name": "Array Technologies", "aliases": "RY"},
    ]

    assert [row["symbol"] for row in cockpit_keyword_filtered_symbol_rows(rows, "RY")] == [
        "RY",
        "RYAAY",
        "ARRY",
    ]


@pytest.mark.parametrize(
    ("symbol", "expected_name"),
    [
        ("RY", "Royal Bank of Canada"),
        ("TD", "Toronto-Dominion Bank"),
        ("CM", "Canadian Imperial Bank of Commerce"),
        ("BMO", "Bank of Montreal"),
        ("D", "Dominion Energy"),
        ("PNW", "Pinnacle West Capital"),
        ("PEG", "Public Service Enterprise Group"),
        ("DUK", "Duke Energy"),
        ("ED", "Consolidated Edison"),
        ("UL", "Unilever"),
        ("BTI", "British American Tobacco"),
        ("TROW", "T. Rowe Price"),
        ("BMY", "Bristol-Myers Squibb"),
        ("REYN", "Reynolds Consumer Products"),
    ],
)
def test_cockpit_search_finds_exact_symbols_in_full_universe(symbol, expected_name):
    rows = symbol_universe_rows()

    matches = cockpit_keyword_filtered_symbol_rows(rows, symbol)

    assert matches[0]["symbol"] == symbol
    assert expected_name in matches[0]["name"]


def test_merged_cockpit_candidates_include_rescued_ranking_and_selected_symbols():
    filtered = [{"symbol": "7203.T", "name": "Toyota Motor"}]
    rescued = [{"symbol": "RY", "name": "Royal Bank of Canada"}]
    ranking = [{"symbol": "UL", "name": "Unilever"}]
    selected = [{"symbol": "D", "name": "Dominion Energy"}]

    rows = merged_symbol_candidate_rows(
        filtered,
        rescued,
        ranking,
        selected,
        query="RY",
    )

    assert [row["symbol"] for row in rows] == ["RY", "7203.T", "D", "UL"]


def test_symbol_universe_rows_for_symbols_rescues_outside_filter_and_keeps_order():
    universe = [
        {"symbol": "7203.T", "name": "Toyota Motor"},
        {"symbol": "RY", "name": "Royal Bank of Canada"},
        {"symbol": "D", "name": "Dominion Energy"},
    ]

    assert app_module.symbol_universe_rows_for_symbols(
        universe,
        ["D", "RY", "D"],
    ) == [universe[2], universe[1]]


def test_symbol_candidate_labels_filter_by_symbol_or_name():
    rows = [
        {"symbol": "9983.T", "name": "Fast Retailing"},
        {"symbol": "AAPL", "name": "Apple Inc."},
    ]

    assert symbol_candidate_labels(rows, "") == [
        "9983.T - Fast Retailing",
        "AAPL - Apple Inc.",
    ]
    assert symbol_candidate_labels(rows, "retail") == ["9983.T - Fast Retailing"]
    assert symbol_candidate_labels(rows, "AAPL") == ["AAPL - Apple Inc."]
    assert symbol_candidate_labels(rows, "missing") == []


def test_cockpit_filtered_symbol_rows_applies_preference_filters(monkeypatch):
    monkeypatch.setattr(
        "ui.app.st.session_state",
        {
            "market_data_cockpit_region": "japan",
            "market_data_cockpit_product_type": "stock",
            "market_data_cockpit_market_cap": "large",
            "market_data_cockpit_nisa": "eligible",
            "market_data_cockpit_per_enabled": True,
            "market_data_cockpit_per_min": "10",
            "market_data_cockpit_per_max": "30",
        },
    )
    rows = [
        {
            "symbol": "7203.T",
            "name": "Toyota",
            "market": "jp",
            "asset_type": "stock",
            "market_cap_tier": "large",
            "nisa_growth_eligible": "true",
            "per": "12",
        },
        {
            "symbol": "9983.T",
            "name": "Fast Retailing",
            "market": "jp",
            "asset_type": "stock",
            "market_cap_tier": "large",
            "nisa_growth_eligible": "true",
            "per": "45",
        },
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "us",
            "asset_type": "stock",
            "market_cap_tier": "mega",
            "nisa_growth_eligible": "true",
            "per": "28",
        },
    ]

    assert [row["symbol"] for row in cockpit_filtered_symbol_rows(rows)] == ["7203.T"]


def test_cockpit_filtered_symbol_rows_default_keeps_full_candidate_master(monkeypatch):
    monkeypatch.setattr("ui.app.st.session_state", {})
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc.", "asset_type": "stock"},
            {
                "symbol": "SQQQ",
                "name": "ProShares UltraPro Short QQQ",
                "asset_type": "etf",
                "is_inverse": "true",
            },
            {
                "symbol": "GLD",
                "name": "Gold ETF",
                "asset_type": "etf",
                "theme": "commodity",
            },
            {
                "symbol": "ADV",
                "name": "Advanced ETF",
                "asset_type": "etf",
                "complexity": "advanced",
                "expense_ratio_pct": "1.50",
            },
            {"symbol": "8951.T", "name": "Nippon Building Fund", "asset_type": "reit"},
            {"symbol": "MF-ACWI", "name": "Mutual Fund", "asset_type": "mutual_fund"},
        ]
    )

    assert [row["symbol"] for row in cockpit_filtered_symbol_rows(rows)] == [
        "AAPL",
        "SQQQ",
        "GLD",
        "ADV",
        "8951.T",
        "MF-ACWI",
    ]


def test_cockpit_filtered_symbol_rows_supports_etf_detail_filters(monkeypatch):
    monkeypatch.setattr(
        "ui.app.st.session_state",
        {
            "market_data_cockpit_region": "all",
            "market_data_cockpit_product_type": "etf",
            "market_data_cockpit_index_family": "sp500",
            "market_data_cockpit_max_expense": "0.10",
            "market_data_cockpit_complexity": "beginner",
        },
    )
    rows = symbol_universe_rows(
        [
            {
                "symbol": "SPY",
                "name": "SPDR S&P 500 ETF",
                "market": "us",
                "asset_type": "etf",
                "index_family": "sp500",
                "expense_ratio_pct": "0.03",
                "complexity": "beginner",
            },
            {
                "symbol": "IVV",
                "name": "iShares Core S&P 500 ETF",
                "market": "us",
                "asset_type": "etf",
                "index_family": "sp500",
                "expense_ratio_pct": "0.03",
                "complexity": "standard",
            },
            {
                "symbol": "QQQ",
                "name": "Invesco QQQ Trust",
                "market": "us",
                "asset_type": "etf",
                "index_family": "nasdaq100",
                "expense_ratio_pct": "0.20",
                "complexity": "beginner",
            },
        ]
    )

    assert [row["symbol"] for row in cockpit_filtered_symbol_rows(rows)] == ["SPY"]


def test_cockpit_keyword_filtered_symbol_rows_matches_theme_and_alias():
    rows = [
        {
            "symbol": "7203.T",
            "name": "Toyota Motor",
            "theme": "automobile",
            "aliases": "トヨタ 自動車",
        },
        {
            "symbol": "NVDA",
            "name": "NVIDIA",
            "theme": "semiconductor",
            "aliases": "GPU AI",
        },
    ]

    assert [row["symbol"] for row in cockpit_keyword_filtered_symbol_rows(rows, "半導体")] == [
        "NVDA"
    ]
    assert [
        row["symbol"] for row in cockpit_keyword_filtered_symbol_rows(rows, "semiconductor")
    ] == ["NVDA"]
    assert [row["symbol"] for row in cockpit_keyword_filtered_symbol_rows(rows, "トヨタ")] == [
        "7203.T"
    ]


def test_favorite_prioritized_symbol_candidate_labels_can_show_only_favorites():
    rows = [
        {"symbol": "AAPL", "name": "Apple"},
        {"symbol": "7203.T", "name": "Toyota"},
        {"symbol": "MSFT", "name": "Microsoft"},
    ]

    assert app_module.favorite_prioritized_symbol_candidate_labels(
        rows,
        {"7203.t"},
        favorites_only=True,
    ) == ["7203.T - Toyota"]
    assert app_module.favorite_prioritized_symbol_candidate_labels(
        rows,
        {"7203.t"},
    ) == ["7203.T - Toyota", "AAPL - Apple", "MSFT - Microsoft"]


def test_exact_symbol_precedes_favorite_and_required_survives_favorites_filter():
    rows = [
        {"symbol": "RYAAY", "name": "Ryanair"},
        {"symbol": "RY", "name": "Royal Bank of Canada"},
        {"symbol": "7203.T", "name": "Toyota"},
    ]

    assert app_module.favorite_prioritized_symbol_candidate_labels(
        rows,
        {"RYAAY"},
        query="RY",
    )[
        :2
    ] == ["RY - Royal Bank of Canada", "RYAAY - Ryanair"]
    assert app_module.favorite_prioritized_symbol_candidate_labels(
        rows,
        {"7203.T"},
        favorites_only=True,
        required_symbols={"RY"},
    ) == ["7203.T - Toyota", "RY - Royal Bank of Canada"]


def test_cockpit_filter_summary_chips_show_default_state():
    chips = cockpit_filter_summary_chips_from_values(
        dict(MARKET_DATA_COCKPIT_FILTER_DEFAULTS),
        candidate_count=9197,
    )

    assert [chip["label"] for chip in chips] == [
        "全体",
        "NISA指定なし",
        "商品指定なし",
        "条件なし",
        "候補 9197件",
    ]
    assert chips[-1]["tone"] == "count"
    assert not cockpit_filter_has_active_conditions_from_values(
        dict(MARKET_DATA_COCKPIT_FILTER_DEFAULTS)
    )


def test_cockpit_filter_expander_label_summarizes_current_conditions():
    chips = cockpit_filter_summary_chips_from_values(
        dict(MARKET_DATA_COCKPIT_FILTER_DEFAULTS),
        candidate_count=9197,
    )

    assert (
        cockpit_filter_expander_label(chips)
        == "銘柄を絞り込む　現在の条件: 全体 / NISA指定なし / 商品指定なし / 条件なし / 候補 9197件"
    )


def test_cockpit_filter_panel_stays_closed_when_filter_active(monkeypatch):
    values = {
        **MARKET_DATA_COCKPIT_FILTER_DEFAULTS,
        "market_data_cockpit_region": "japan",
    }
    expander_calls: list[dict[str, object]] = []

    monkeypatch.setattr("ui.app._cockpit_filter_state_snapshot", lambda: values)
    monkeypatch.setattr(
        "ui.app.cockpit_filtered_symbol_rows",
        lambda rows: list(rows),
    )
    monkeypatch.setattr(
        "ui.app._render_cockpit_symbol_filter_detail_fields",
        lambda rows: list(rows),
    )
    monkeypatch.setattr("ui.app.st.markdown", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.button", lambda *_, **__: False)
    monkeypatch.setattr("ui.app.st.warning", lambda *_, **__: None)

    def fake_expander(label: str, *, expanded: bool = False):
        expander_calls.append({"label": label, "expanded": expanded})
        return _FakeExpander()

    monkeypatch.setattr("ui.app.st.expander", fake_expander)

    _render_cockpit_symbol_filter_panel([{"symbol": "7203.T", "name": "Toyota"}])

    assert expander_calls == [
        {
            "label": "銘柄を絞り込む　現在の条件: 国内 / NISA指定なし / 商品指定なし / 候補 1件",
            "expanded": False,
        }
    ]


def test_cockpit_filter_summary_chips_show_active_conditions():
    values = {
        **MARKET_DATA_COCKPIT_FILTER_DEFAULTS,
        "market_data_cockpit_region": "japan",
        "market_data_cockpit_product_type": "stock",
        "market_data_cockpit_nisa": "eligible",
        "market_data_cockpit_market_cap": "large",
        "market_data_cockpit_per_enabled": True,
        "market_data_cockpit_per_min": "10.0",
        "market_data_cockpit_per_max": "20.0",
    }
    chips = cockpit_filter_summary_chips_from_values(values, candidate_count=124)
    labels = [chip["label"] for chip in chips]

    assert labels[:3] == ["国内", "NISA対象", "株式"]
    assert "規模: 大型" in labels
    assert any(":" in label and "PER" not in label for label in labels[3:-1])
    assert "PER 10-20" in labels
    assert "条件なし" not in labels
    assert labels[-1] == "候補 124件"
    assert cockpit_filter_has_active_conditions_from_values(values)


def test_cockpit_filter_hidden_stock_metric_does_not_activate_etf_conditions():
    values = {
        **MARKET_DATA_COCKPIT_FILTER_DEFAULTS,
        "market_data_cockpit_pbr_enabled": True,
    }

    labels = [
        chip["label"]
        for chip in cockpit_filter_summary_chips_from_values(values, candidate_count=12)
    ]

    assert not any("PBR" in label for label in labels)
    assert not cockpit_filter_has_active_conditions_from_values(values)


def test_cockpit_filter_summary_chips_include_active_detail_and_metric_labels():
    values = {
        **MARKET_DATA_COCKPIT_FILTER_DEFAULTS,
        "market_data_cockpit_region": "japan",
        "market_data_cockpit_product_type": "stock",
        "market_data_cockpit_market_cap": "large",
        "market_data_cockpit_per_enabled": True,
        "market_data_cockpit_per_min": "10.0",
        "market_data_cockpit_per_max": "20.0",
    }

    labels = [
        chip["label"]
        for chip in cockpit_filter_summary_chips_from_values(values, candidate_count=124)
    ]

    assert "124" in labels[-1]
    assert "PER 10-20" in labels
    assert any(":" in label and "PER" not in label for label in labels[3:-1])


def test_cockpit_filter_summary_chips_show_readable_etf_expense_condition():
    values = {
        **MARKET_DATA_COCKPIT_FILTER_DEFAULTS,
        "market_data_cockpit_product_type": "etf",
        "market_data_cockpit_max_expense": "2.0",
    }

    labels = [
        chip["label"]
        for chip in cockpit_filter_summary_chips_from_values(values, candidate_count=12)
    ]

    assert "信託報酬 2%以下" in labels


def test_cockpit_filter_summary_chips_html_escapes_labels():
    rendered = cockpit_filter_summary_chips_html([{"label": "<条件>", "tone": "active"}])

    assert "&lt;条件&gt;" in rendered
    assert "<条件>" not in rendered


def test_coerce_number_input_state_recovers_string_values(monkeypatch):
    session_state: dict[str, object] = {"market_data_cockpit_per_min": "2.0"}
    monkeypatch.setattr("ui.app.st.session_state", session_state)

    assert _coerce_number_input_state("market_data_cockpit_per_min", "1.0") == 2.0
    assert session_state["market_data_cockpit_per_min"] == 2.0


def test_current_or_default_symbol_labels_uses_first_available_candidate():
    assert _current_or_default_symbol_labels([{"symbol": "9983.T", "name": "Fast Retailing"}]) == [
        "9983.T - Fast Retailing"
    ]
    assert _current_or_default_symbol_labels([]) == [NO_SYMBOL_CANDIDATE_LABEL]


def test_symbol_universe_detail_rows_show_column_labels_and_blank_values():
    assert symbol_universe_detail_rows(
        {
            "symbol": "7203.T",
            "name": "Toyota Motor",
            "dividend_yield_pct": "",
            "custom_field": "custom",
        }
    ) == [
        {"項目": "銘柄コード", "表示値": "7203.T", "CSV列": "symbol", "登録値": "7203.T"},
        {"項目": "銘柄名", "表示値": "Toyota Motor", "CSV列": "name", "登録値": "Toyota Motor"},
        {
            "項目": "配当利回り(%)",
            "表示値": "未登録",
            "CSV列": "dividend_yield_pct",
            "登録値": "-",
        },
        {"項目": "custom_field", "表示値": "custom", "CSV列": "custom_field", "登録値": "custom"},
    ]


def test_symbol_universe_detail_display_value_translates_internal_codes():
    row = {
        "broker": "sbi_securities",
        "metadata_source": "yahoo",
        "dividend_yield_pct": "2.840",
        "market_cap_tier": "large",
        "risk_band": "LOW",
        "yahoo_symbol": "",
    }

    assert symbol_universe_detail_display_value(row, "broker") == "SBI証券"
    assert symbol_universe_detail_display_value(row, "metadata_source") == "Yahoo Finance"
    assert symbol_universe_detail_display_value(row, "dividend_yield_pct") == "2.84%"
    assert symbol_universe_detail_display_value(row, "market_cap_tier").startswith("大型")
    assert symbol_universe_detail_display_value(row, "risk_band") == "低め"
    assert symbol_universe_detail_display_value(row, "yahoo_symbol") == "表示銘柄と同じ"


def test_symbol_universe_detail_display_value_marks_abnormal_dividend_yield():
    row = {"dividend_yield_pct": "293.19"}

    assert symbol_universe_detail_display_value(row, "dividend_yield_pct") == "要確認"


def test_symbol_universe_detail_display_value_marks_abnormal_valuation_metrics():
    row = {"per": "0", "pbr": "624.11", "roe_pct": "101"}

    assert symbol_universe_detail_display_value(row, "per") == "要確認"
    assert symbol_universe_detail_display_value(row, "pbr") == "要確認"
    assert symbol_universe_detail_display_value(row, "roe_pct") == "要確認"


def test_symbol_universe_overview_rows_use_user_friendly_values():
    row = {
        "market": "jp",
        "asset_type": "stock",
        "currency": "JPY",
        "broker": "sbi_securities",
        "tradability": "unknown",
        "nisa_category": "growth",
        "nisa_growth_eligible": "true",
        "nisa_tsumitate_eligible": "false",
        "investment_style": "lump_sum",
        "theme": "financial",
        "sector": "financial",
        "is_leveraged": "false",
        "is_inverse": "false",
    }

    rows = symbol_universe_overview_rows(row)

    assert {"項目": "取扱元", "内容": "SBI証券"} in rows
    assert {"項目": "NISA", "内容": "成長投資枠"} in rows
    assert {"項目": "投資スタイル", "内容": "一括投資向き"} in rows
    assert {"項目": "レバレッジ/インバース", "内容": "該当なし"} in rows


def test_symbol_universe_investment_and_fund_rows_are_sectioned():
    stock_row = {
        "dividend_yield_pct": "2.61",
        "dividend_category": "dividend",
        "per": "9.05",
        "pbr": "0.66",
        "roe_pct": "7.74",
        "market_cap_tier": "large",
        "risk_band": "LOW",
        "data_quality": "OK",
        "asset_type": "stock",
        "nisa_growth_eligible": "true",
    }
    etf_row = {
        "asset_type": "etf",
        "index_family": "sp500",
        "expense_ratio_pct": "0.09",
        "complexity": "beginner",
        "nisa_growth_eligible": "true",
    }

    assert {"項目": "配当利回り", "内容": "2.61%"} in symbol_universe_investment_metric_rows(
        stock_row
    )
    assert symbol_universe_fund_detail_rows(stock_row) == []
    assert {"項目": "連動指数", "内容": "S&P 500"} in symbol_universe_fund_detail_rows(etf_row)
    assert {"項目": "成長投資枠", "内容": "はい"} in symbol_universe_fund_detail_rows(etf_row)


def test_symbol_universe_nisa_display_combines_category_and_flags():
    assert (
        symbol_universe_nisa_display(
            {
                "nisa_category": "unknown",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
            }
        )
        == "成長投資枠"
    )


def test_symbol_universe_key_metric_rows_use_compact_values():
    rows = symbol_universe_key_metric_rows(
        {
            "asset_type": "stock",
            "nisa_category": "both",
            "dividend_yield_pct": "4.79",
            "market_cap_tier": "mid",
            "risk_band": "LOW",
            "nisa_growth_eligible": "true",
            "nisa_tsumitate_eligible": "true",
        }
    )

    assert {"項目": "NISA", "内容": "両枠"} in rows
    assert {"項目": "時価総額", "内容": "中型（JP 1,000億〜1兆円 / US $2B〜$10B）"} in rows
    assert {"項目": "配当利回り", "内容": "4.79%"} in rows


def test_symbol_universe_data_info_rows_explain_how_values_are_used():
    rows = symbol_universe_data_info_rows(
        {
            "metadata_source": "yahoo",
            "metadata_as_of": "2026-05-21",
            "metadata_updated_at": "2026-05-21T00:00:00+09:00",
            "yahoo_symbol": "",
        }
    )

    assert {
        "項目": "データ出所",
        "内容": "Yahoo Finance",
        "使い道": "指標や分類をどの情報源で補完したかを確認します。",
    } in rows
    assert rows[-1]["項目"] == "価格取得用ticker"
    assert rows[-1]["内容"] == "表示銘柄と同じ"
    assert "Yahoo取得時" in rows[-1]["使い道"]


def test_symbol_universe_data_info_rows_include_runtime_cache_freshness():
    rows = symbol_universe_data_info_rows(
        {
            "asset_type": "stock",
            "metadata_source": "yahoo",
            "metadata_as_of": "2026-06-01",
            "metadata_updated_at": "2026-06-01T13:00:00+09:00",
            "symbol_cache_provider": "yahoo",
            "symbol_cache_updated_at": "2026-06-04T09:00:00",
            "symbol_cache_last_price_updated_at": "2026-06-04T08:30:00",
            "symbol_cache_last_fundamental_updated_at": "2026-06-04T08:45:00",
            "symbol_cache_freshness_status": "fresh",
            "per": "28.1",
            "pbr": "7.2",
            "roe_pct": "24",
            "dividend_yield_pct": "0.5",
            "market_cap_tier": "large",
            "risk_band": "LOW",
            "yahoo_symbol": "",
        }
    )

    assert rows[0] == {
        "項目": "銘柄DB鮮度",
        "内容": "最新",
        "使い道": "保存済み銘柄データをそのまま読めるか、再確認が必要かを見ます。",
    }
    assert {
        "項目": "銘柄DB取得元",
        "内容": "Yahoo Finance",
        "使い道": "保存済み銘柄DBを更新したproviderです。",
    } in rows
    assert {
        "項目": "不足している主要項目",
        "内容": "主要項目は登録済み",
        "使い道": "空欄が多い銘柄では評価材料が少ないため、追加確認が必要です。",
    } in rows


def test_symbol_universe_cache_status_text_and_notice_show_stale_missing_fields():
    row = {
        "asset_type": "stock",
        "metadata_source": "yahoo",
        "metadata_as_of": "2026-06-01",
        "symbol_cache_provider": "yahoo",
        "symbol_cache_updated_at": "2026-06-04T09:00:00",
        "symbol_cache_freshness_status": "stale",
        "per": "28.1",
    }

    assert symbol_universe_cache_status_text(row) == (
        "銘柄DB: やや古い / 最終更新 2026-06-04 09:00 / " "取得元 Yahoo Finance / 不足 5項目"
    )
    assert symbol_universe_missing_key_fields_display(row).startswith("PBR、ROE")
    assert "一部データが古い可能性" in symbol_universe_cache_notice(row)


def test_symbol_universe_cache_status_text_falls_back_to_local_master_when_cache_missing():
    row = {
        "asset_type": "etf",
        "metadata_source": "curated_csv",
        "metadata_as_of": "2026-06-01",
        "index_family": "sp500",
        "expense_ratio_pct": "0.09",
        "dividend_yield_pct": "1.1",
        "complexity": "beginner",
    }

    assert symbol_universe_cache_status_text(row) == (
        "銘柄DB: 未取得 / 最終更新 未取得 / 取得元 手動整備CSV"
    )
    assert symbol_universe_missing_key_fields_display(row) == "主要項目は登録済み"
    assert "ローカル銘柄マスタ" in symbol_universe_cache_notice(row)


def test_symbol_auto_refresh_request_key_normalizes_symbols():
    first = symbol_auto_refresh_request_key(
        [" aapl ", "AAPL", "7203.t"],
        context="ranking",
        source_key="ranking-source",
    )
    second = symbol_auto_refresh_request_key(
        ["AAPL", "7203.T"],
        context="ranking",
        source_key="ranking-source",
    )

    assert first == second
    assert first.startswith("ranking|")


def test_symbol_auto_refresh_once_dedupes_session_requests(monkeypatch):
    session_state: dict[str, object] = {}
    calls: list[tuple[list[str], str]] = []

    def fake_request(symbols: list[str], *, source: str) -> list[str]:
        calls.append((list(symbols), source))
        return list(symbols)

    monkeypatch.setattr("ui.app.st.session_state", session_state)
    monkeypatch.setattr("ui.app.request_symbol_background_refresh", fake_request)

    _request_symbol_auto_refresh_once(
        [" aapl ", "AAPL", ""],
        context="cockpit",
        source_key="aapl",
        max_symbols=5,
    )
    _request_symbol_auto_refresh_once(
        ["AAPL"],
        context="cockpit",
        source_key="aapl",
        max_symbols=5,
    )

    requested_keys = session_state[SYMBOL_AUTO_REFRESH_REQUEST_STATE_KEY]
    assert calls == [(["AAPL"], "cockpit")]
    assert isinstance(requested_keys, list)
    assert len(requested_keys) == 1


def test_cockpit_symbol_db_preflight_background_uses_session_ttl(monkeypatch):
    session_state: dict[str, object] = {}
    calls: list[tuple[list[str], str]] = []

    def fake_request(symbols: list[str], *, source: str) -> list[str]:
        calls.append((list(symbols), source))
        return list(symbols)

    monkeypatch.delenv("SMAI_DISABLE_BACKGROUND_WORKERS", raising=False)
    monkeypatch.setattr("ui.app.st.session_state", session_state)
    monkeypatch.setattr("ui.app.request_symbol_background_refresh", fake_request)

    assert _request_cockpit_symbol_db_preflight_background(" aapl ", now=100.0) is True
    assert _request_cockpit_symbol_db_preflight_background("AAPL", now=160.0) is False
    assert (
        _request_cockpit_symbol_db_preflight_background(
            "AAPL",
            now=100.0 + COCKPIT_SYMBOL_DB_PREFLIGHT_TTL_SECONDS + 1,
        )
        is True
    )

    assert calls == [(["AAPL"], "cockpit"), (["AAPL"], "cockpit")]
    assert session_state[COCKPIT_SYMBOL_DB_PREFLIGHT_REQUEST_STATE_KEY] == {
        "AAPL": 100.0 + COCKPIT_SYMBOL_DB_PREFLIGHT_TTL_SECONDS + 1
    }


def test_cockpit_symbol_db_preflight_background_respects_disabled_workers(monkeypatch):
    session_state: dict[str, object] = {}
    calls: list[tuple[list[str], str]] = []

    def fake_request(symbols: list[str], *, source: str) -> list[str]:
        calls.append((list(symbols), source))
        return list(symbols)

    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "true")
    monkeypatch.setattr("ui.app.st.session_state", session_state)
    monkeypatch.setattr("ui.app.request_symbol_background_refresh", fake_request)

    assert _request_cockpit_symbol_db_preflight_background("AAPL", now=100.0) is False
    assert calls == []
    assert COCKPIT_SYMBOL_DB_PREFLIGHT_REQUEST_STATE_KEY not in session_state


def test_cockpit_symbol_db_preflight_background_suppresses_failure(monkeypatch):
    session_state: dict[str, object] = {}

    def fake_request(symbols: list[str], *, source: str) -> list[str]:
        raise RuntimeError("locked")

    monkeypatch.delenv("SMAI_DISABLE_BACKGROUND_WORKERS", raising=False)
    monkeypatch.setattr("ui.app.st.session_state", session_state)
    monkeypatch.setattr("ui.app.request_symbol_background_refresh", fake_request)

    assert _request_cockpit_symbol_db_preflight_background("AAPL", now=100.0) is False
    assert session_state[SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY] == "RuntimeError"
    assert COCKPIT_SYMBOL_DB_PREFLIGHT_REQUEST_STATE_KEY not in session_state


def test_background_workers_disabled_env_flag(monkeypatch):
    monkeypatch.delenv("SMAI_DISABLE_BACKGROUND_WORKERS", raising=False)
    assert _background_workers_disabled() is False

    monkeypatch.setenv("SMAI_DISABLE_BACKGROUND_WORKERS", "true")
    assert _background_workers_disabled() is True


def test_ranking_symbol_db_preflight_limit_bounds_large_requests():
    assert ranking_symbol_db_preflight_limit(0) == 0
    assert ranking_symbol_db_preflight_limit(12) == 12
    assert ranking_symbol_db_preflight_limit(30) == 30
    assert ranking_symbol_db_preflight_limit(31) == 31
    assert ranking_symbol_db_preflight_limit(300) == 50
    assert ranking_symbol_db_preflight_limit(1200) == 50


def test_ranking_symbol_db_preflight_symbols_dedupes_and_caps_scan_set():
    symbols = [" aapl ", "AAPL", *[f"T{index:04d}" for index in range(400)]]

    result = ranking_symbol_db_preflight_symbols(symbols)

    assert result[:2] == ["AAPL", "T0000"]
    assert len(result) == RANKING_SYMBOL_DB_PREFLIGHT_SCAN_LIMIT
    assert len(set(result)) == len(result)


def test_symbol_database_preflight_refresh_passes_ranking_context(monkeypatch):
    session_state: dict[str, object] = {
        SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY: "RuntimeError",
    }
    calls: list[dict[str, object]] = []
    sync_calls: list[dict[str, object]] = []
    summary = SimpleNamespace(succeeded_count=1)

    def fake_target_refresh(symbols: list[str], **kwargs: object) -> object:
        calls.append({"symbols": list(symbols), **kwargs})
        return summary

    def fake_sync(**kwargs: object) -> object:
        sync_calls.append(dict(kwargs))
        return SimpleNamespace(promoted_count=1)

    monkeypatch.setattr("ui.app.st.session_state", session_state)
    monkeypatch.setattr("ui.app.run_symbol_database_target_refresh", fake_target_refresh)
    monkeypatch.setattr("ui.app.sync_symbol_cache_to_official_metrics", fake_sync)

    result = _run_symbol_database_preflight_refresh(
        [" aapl ", "AAPL", "7203.t"],
        context="ranking",
        max_items=31,
    )

    assert result is summary
    assert calls == [
        {
            "symbols": ["AAPL", "7203.T"],
            "max_items": 31,
            "currently_visible_symbols": None,
            "ranking_candidates": ["AAPL", "7203.T"],
        }
    ]
    assert sync_calls == [{"max_items": 31, "symbols": ["AAPL", "7203.T"]}]
    assert SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY not in session_state


def test_symbol_database_preflight_refresh_suppresses_failure(monkeypatch):
    session_state: dict[str, object] = {}

    def fake_target_refresh(symbols: list[str], **kwargs: object) -> object:
        raise RuntimeError("locked")

    monkeypatch.setattr("ui.app.st.session_state", session_state)
    monkeypatch.setattr("ui.app.run_symbol_database_target_refresh", fake_target_refresh)
    monkeypatch.setattr(
        "ui.app.sync_symbol_cache_to_official_metrics",
        lambda **kwargs: None,
    )

    result = _run_symbol_database_preflight_refresh(
        ["7203.t"],
        context="cockpit",
        max_items=1,
    )

    assert result is None
    assert session_state[SYMBOL_PREFLIGHT_REFRESH_ERROR_STATE_KEY] == "RuntimeError"


def test_symbol_detail_dialog_css_expands_width_and_wraps_metric_values():
    assert "94vw" in SYMBOL_DETAIL_DIALOG_CSS
    assert "1500px" in SYMBOL_DETAIL_DIALOG_CSS
    assert '[data-testid="stMetricValue"]' in SYMBOL_DETAIL_DIALOG_CSS
    assert "overflow-wrap: anywhere" in SYMBOL_DETAIL_DIALOG_CSS
    assert ".symbol-detail-table" in SYMBOL_DETAIL_DIALOG_CSS
    assert "table-layout: fixed" in SYMBOL_DETAIL_DIALOG_CSS
    assert "font-size: 0.95rem" in SYMBOL_DETAIL_DIALOG_CSS
    assert "line-height: 1.6" in SYMBOL_DETAIL_DIALOG_CSS


def test_symbol_detail_research_loading_stays_inside_dialog():
    source = inspect.getsource(app_module._render_ranking_symbol_research_lookup)

    assert source.count('mode="inline"') == 2
    assert 'mode="blocking"' not in source


def test_symbol_detail_table_html_wraps_and_escapes_long_text():
    markup = symbol_detail_table_html(
        [
            {
                "観点": "次の行動",
                "内容": "銘柄データとコックピットで価格トレンドを確認してください",
                "確認ポイント": "<script>売買推奨ではありません</script>",
            }
        ]
    )

    assert 'class="symbol-detail-table"' in markup
    assert "銘柄データとコックピット" in markup
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_research_table_html_wraps_and_escapes_long_summary_text():
    markup = _research_table_html(
        [
            {
                "観点": "成長材料",
                "要約": "長いResearch Summaryをモーダル幅の中で折り返して確認します",
                "根拠数": "<3>",
            }
        ],
        class_name="research-summary-table",
    )

    assert "research-summary-table" in markup
    assert "research-topic" in markup
    assert "research-count" in markup
    assert "&lt;3&gt;" in markup


def test_research_quality_warning_rows_feed_escaped_warning_table():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research warning summary",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=1,
            warnings=["信頼度が低い <check source>"],
        ),
    )

    rows = _research_quality_warning_rows(report)
    markup = _research_table_html(rows, class_name="research-summary-table")

    assert rows == [
        {
            "確認項目": "資料の状態",
            "状態": "WARN",
            "注意点": "信頼度が低い <check source>",
        }
    ]
    assert "<check source>" not in markup
    assert "&lt;check source&gt;" in markup


def test_research_result_overview_html_explains_coverage_and_escapes_summary():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="資料から確認できる範囲です <script>",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=["資料がありません。"],
        ),
    )

    markup = _research_result_overview_html(report)

    assert "AI整理メモ" in markup
    assert "資料 0件 / 根拠 0件" in markup
    assert "SettingsでResearch資料を登録" in markup
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


def test_research_brief_helpers_render_readable_rows_and_escape_markup():
    brief = ResearchBrief(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        memo="確認できた情報です <script>",
        metrics=[
            ResearchMetric(
                key="revenue",
                label="売上高",
                value="45兆円",
                source_title="7203 決算短信",
                source_type="earnings_report",
                source_confidence="high",
            )
        ],
        missing_metrics=["EPS"],
        business_overview=(
            "Company Name: Toyota Motor Corporation Provider Symbol: 7203.T "
            "Quote Type: EQUITY Toyota sells vehicles globally."
        ),
        positive_candidates=["成長材料: software revenue"],
        caution_candidates=["注意材料: supply constraint"],
        positive_materials=[
            ResearchBriefMaterial(
                label="成長材料",
                summary="成長材料: software revenueに関する記述を1件確認しました。",
                source_title="7203 決算短信",
                source_type="earnings_report",
                source_confidence="high",
                source_count=1,
                published_at=date(2026, 5, 20),
            )
        ],
        caution_materials=[
            ResearchBriefMaterial(
                label="ニュース",
                summary="ニュース: 「Supply constraint」を確認しました。要約: 部品供給に注意。",
                source_title="Supply constraint",
                source_type="news",
                source_confidence="medium",
                source_count=1,
                published_at=date(2026, 5, 22),
            )
        ],
        confirmation_gaps=["未確認の定量指標: EPS"],
        next_actions=["公式資料でEPSを確認します。"],
        source_cards=[
            ResearchBriefSourceCard(
                title="7203 決算短信",
                source_type="earnings_report",
                published_at=date(2026, 5, 20),
                source_confidence="high",
            ),
            ResearchBriefSourceCard(
                title="TDnet 7203",
                source_type="tdnet",
                provider="tdnet",
                source_url="https://example.com/tdnet",
                published_at=date(2026, 5, 22),
                fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
                freshness_status="latest",
                source_confidence="high",
                note="AI調査で一時参照した外部ソースです。",
            ),
        ],
        fact_summary=ResearchFactSummary(
            symbol="7203.T",
            as_of=date(2026, 5, 25),
            business_regions=[
                ResearchFactItem(
                    label="地域展開",
                    value="日本、北米、欧州",
                    source_title="7203 決算短信",
                    source_type="earnings_report",
                    source_confidence="high",
                    published_at=date(2026, 5, 20),
                )
            ],
            revenue_drivers=[
                ResearchFactItem(
                    label="収益源",
                    value="製品・車両販売、ソフトウェア・サービス",
                    source_title="7203 決算短信",
                    source_type="earnings_report",
                    source_confidence="high",
                    published_at=date(2026, 5, 20),
                )
            ],
            earnings_outlook=[
                ResearchFactItem(
                    label="業績見通し",
                    value="通期予想は売上高46兆円です。",
                    source_title="7203 決算短信",
                    source_type="earnings_report",
                    source_confidence="high",
                    published_at=date(2026, 5, 20),
                )
            ],
            shareholder_return_policy=[
                ResearchFactItem(
                    label="配当・株主還元方針",
                    value="配当方針は安定配当を重視します。",
                    source_title="7203 決算短信",
                    source_type="earnings_report",
                    source_confidence="high",
                    published_at=date(2026, 5, 20),
                )
            ],
        ),
    )

    markup = _research_brief_overview_html(brief)
    reading_markup = _research_brief_reading_guide_html(brief)
    reading_rows = _research_brief_reading_guide_rows(brief)
    focus_markup = _research_brief_focus_html(brief)
    metric_markup = _research_brief_metric_cards_html(brief)
    metric_rows = _research_brief_metric_rows(brief)
    gap_markup = _research_brief_gap_panel_html(brief)
    gap_rows = _research_brief_gap_rows(brief)
    next_action_markup = _research_brief_next_actions_html(brief)
    action_rows = _research_brief_next_action_rows(brief)
    source_rows = _research_brief_source_card_rows(brief)
    source_markup = _research_evidence_cards_html(source_rows)
    item_markup = _research_brief_items_html(["<growth>"], tone="positive")

    assert "AI整理メモ" in markup
    assert "research-result-brief hero" in markup
    assert "売買推奨ではありません" in markup
    assert "追加確認 1指標" in markup
    assert "抽出指標" not in markup
    assert "指標件数、出典カード、Research Score" in markup
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup
    assert "research-brief-reading-grid" in reading_markup
    assert "確認できたこと" in reading_markup
    assert "注意して見ること" in reading_markup
    assert "まだ足りないこと" in reading_markup
    assert "次にやること" in reading_markup
    assert "業績見通し" in reading_markup
    assert "配当・株主還元" in reading_markup
    assert "注意材料候補1件" not in reading_markup
    assert "まだ確認できていない数値: EPS" in reading_markup
    assert reading_rows[0]["label"] == "確認できたこと"
    assert reading_rows[2]["body"].startswith("まだ確認できていない数値")
    assert "research-brief-focus-grid" in focus_markup
    assert "会社概要" in focus_markup
    assert "確認できた事実" in focus_markup
    assert "公式資料で未確認" in focus_markup
    assert "日本、北米、欧州" in focus_markup
    assert "業績見通し" in focus_markup
    assert "通期予想は売上高46兆円" in focus_markup
    assert "配当・株主還元" in focus_markup
    assert "Provider Symbol" not in focus_markup
    assert "Toyota sells vehicles" in focus_markup
    assert "良材料候補" not in focus_markup
    assert "注意材料候補" not in focus_markup
    assert "情報源信頼度" not in focus_markup
    assert "主な出典" not in focus_markup
    assert "research-brief-metric-grid" in metric_markup
    assert "45兆円" in metric_markup
    assert "confidence-high" in metric_markup
    assert "research-brief-gap-panel" in gap_markup
    assert "まだ確認できていない数値: EPS" in gap_markup
    assert "悪材料ではなく" in gap_markup
    assert "research-brief-next-list" in next_action_markup
    assert "公式資料でEPSを確認" in next_action_markup
    assert metric_rows[0]["指標"] == "売上高"
    assert metric_rows[0]["情報源信頼度"].startswith("高")
    assert gap_rows[0]["確認項目"] == "不足根拠"
    assert gap_rows[0]["内容"].startswith("まだ確認できていない数値")
    assert action_rows[0]["扱い"] == "確認材料"
    assert source_rows[0]["category"] == "決算短信"
    assert source_rows[0]["confidence_tone"] == "high"
    assert source_rows[1]["url"] == "https://example.com/tdnet"
    assert "出典を開く" in source_markup
    assert "情報源の信頼度" in source_markup
    assert "confidence-high" in source_markup
    assert "<growth>" not in item_markup
    assert "&lt;growth&gt;" in item_markup


def test_research_operation_card_keeps_single_primary_action(monkeypatch):
    provider_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Toyota Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Toyota Motor Corporation Provider Symbol: 7203.T "
            "Toyota sells vehicles globally and invests in software services."
        ),
        relevance_score=Decimal("0.70"),
        reliability=Decimal("0.70"),
    )
    official_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-ir",
        chunk_id="chunk-ir",
        title="7203 決算短信",
        source_type="earnings_report",
        published_at=date(2026, 5, 20),
        section_title="業績",
        excerpt=(
            "売上高 45兆円。通期予想は売上高46兆円です。"
            "配当方針は安定配当を重視します。"
            "日本、北米、欧州で車両販売を展開しています。"
            "成長戦略と株主還元を説明しています。"
        ),
        relevance_score=Decimal("0.88"),
        reliability=Decimal("0.94"),
    )
    risk_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-risk",
        chunk_id="chunk-risk",
        title="TDnet 適時開示",
        source_type="tdnet",
        published_at=date(2026, 5, 22),
        section_title="Risk",
        excerpt="供給制約と為替変動が事業リスクとして説明されています。",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.90"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="3件の根拠から確認材料を整理しました。",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="成長戦略を確認材料として整理します。",
                evidence=[official_evidence],
            ),
            ResearchSummaryPoint(
                category="business_risk",
                label="事業リスク",
                summary="供給制約と為替変動を注意材料候補として見ます。",
                evidence=[risk_evidence],
            ),
        ],
        evidence=[official_evidence, provider_evidence, risk_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=3,
            evidence_count=3,
            warnings=[],
        ),
    )
    preview = MarketDataPreview(
        status="ok",
        bars=[],
        provider_rows=[],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[],
        screening_rows=[{"symbol": "7203.T"}],
        error_rows=[],
    )
    button_calls: list[tuple[str, dict[str, object]]] = []
    markdown_calls: list[str] = []

    def fake_button(label: str, **kwargs: object) -> bool:
        button_calls.append((label, kwargs))
        return True

    def fake_download_button(*args: object, **kwargs: object) -> None:
        raise AssertionError("Research operation card should not show CSV export.")

    monkeypatch.setattr("ui.app.st.container", lambda **kwargs: nullcontext())
    monkeypatch.setattr(
        "ui.app.st.markdown",
        lambda body, *args, **kwargs: markdown_calls.append(str(body)),
    )
    monkeypatch.setattr("ui.app.st.button", fake_button)
    monkeypatch.setattr("ui.app.st.download_button", fake_download_button)

    clicked = _render_research_operation_card(preview, report=report, news_report=None)
    markup = "\n".join(markdown_calls)

    assert clicked is True
    assert [label for label, _ in button_calls] == ["AI調査を更新"]
    assert button_calls[0][1]["type"] == "primary"
    assert button_calls[0][1]["use_container_width"] is True
    assert "AI調査結果" in markup
    assert "レポート: 作成済み" in markup
    assert "ニュース: 0件" in markup
    assert "IR/開示: 2件" in markup
    assert "外部データ: 1件" in markup
    assert "注目材料" in markup
    assert "注意材料" in markup
    assert "調査アクション" not in markup
    assert "売買推奨ではありません" not in markup
    assert "企業理解のための情報整理" not in markup
    assert "JSON" not in markup
    assert "CSV" not in markup

    button_calls.clear()
    markdown_calls.clear()
    clicked = _render_research_operation_card(preview, report=None, news_report=None)
    markup = "\n".join(markdown_calls)

    assert clicked is True
    assert [label for label, _ in button_calls] == ["AI調査を開始・更新"]
    assert "AI調査はまだ未取得です" in markup
    assert "未取得通知" not in markup
    assert "確認方針" not in markup


def test_research_operation_insight_uses_neutral_prefetch_guidance():
    insight = _research_operation_insight(None, None)

    assert insight["title"] == "AI調査で確認すること"
    assert "確認方針:" in insight["next_step"]
    assert "AI調査を更新して" not in insight["next_step"]


def test_investment_insight_panel_html_accepts_cached_legacy_insight():
    legacy_insight = SimpleNamespace(
        short_summary=(
            "外部ニュースや補助データから、一部の判断材料を確認できます。"
            "一方で、公式IRで裏取りできていません。"
            "現時点では、売買判断ではなく追加確認向きです。"
        ),
        positive_points=[],
        negative_points=[],
        neutral_points=[],
        confirmation_gaps=["ニュースはありますが、公式IRで裏取りできていません。"],
        action_hints=["wait_for_confirmation"],
        confidence="medium",
    )

    markup = _investment_insight_panel_html(legacy_insight)

    assert "AI読み取りメモ" in markup
    assert "ステータス: ニュース先行" in markup
    assert "信頼度: 低" in markup
    assert "次のアクション: 公式IRで裏取り" in markup


def test_company_research_summary_html_prioritizes_company_understanding():
    summary = CompanyResearchSummary(
        symbol="7203.T",
        overview=CompanyOverviewSummary(
            company_name="Toyota Motor Corporation",
            symbol="7203.T",
            business_profile=CompanyBusinessProfile(
                company_name="Toyota Motor Corporation",
                symbol="7203.T",
                sector="Consumer Cyclical",
                industry="Auto Manufacturers",
            ),
            business_overview="自動車の製造・販売を中心とするグローバル企業です。",
            business_segments=["自動車", "金融サービス"],
            regions=["日本", "北米"],
            scale_summary="売上高 45兆円、時価総額 35兆円を確認できます。",
            recent_focus="直近ニュースからソフトウェア領域の材料を確認しています。",
            evidence_level="medium",
            source_titles=["Yahoo Finance Profile"],
        ),
        quantitative=QuantitativeSummary(
            revenue="45兆円",
            operating_profit="5兆円",
            net_income="4兆円",
            eps="320円",
            per="12.5倍",
            pbr="1.1倍",
            roe="9.8%",
            dividend_yield=None,
            market_cap="35兆円",
            summary="確認できた主要指標があります。",
            missing_items=["配当利回り"],
            evidence_level="high",
            source_titles=["7203 決算短信"],
        ),
        ir_items=[
            IRSummaryItem(
                document_type="決算短信",
                title="取得済み",
                availability="found",
                information_status="found",
                summary="決算短信から確認できる要点があります。",
                key_points=["通期予想を確認できます。"],
                source_title="7203 決算短信",
                evidence_level="high",
            )
        ],
        news_items=[
            NewsSummaryItem(
                title="Toyota expands software services",
                summary="ソフトウェア領域のニュースです。",
                source_title="Example News",
                source_url="https://example.com/news",
                published_at=date(2026, 6, 1),
                impact_hint="business",
                evidence_level="low",
            )
        ],
        ai_reading_notes=["確認できたこと: 事業概要を確認できます。"],
        missing_critical_items=["配当利回り"],
    )

    markup = _company_research_summary_html(summary)
    markup += _quantitative_summary_html(summary.quantitative)
    markup += _ir_summary_html(summary.ir_items)
    markup += _news_summary_html(summary.news_items)

    assert "企業リサーチサマリー" in markup
    assert "企業概要" in markup
    assert "事業内容" in markup
    assert "セクター: 一般消費財" in markup
    assert "業種: 自動車メーカー" in markup
    assert "Consumer Cyclical" not in markup
    assert "Auto Manufacturers" not in markup
    assert "定量情報サマリー" in markup
    assert "売上高" in markup
    assert "IR情報サマリー" in markup
    assert "関連候補あり" in markup
    assert "取得済み・要約済み" not in markup
    assert "最新ニュース・開示サマリー" in markup
    assert "market-intelligence-panel" in markup
    assert "Market Intelligence" in markup
    assert "market-news-grid" in markup
    assert "market-news-item featured" in markup
    assert "market-news-main" in markup
    assert "market-news-aside" in markup
    assert "research-news-summary-card" in markup
    assert "news-feed-item-clickable" in markup
    assert "news-source-link" in markup
    assert "market-news-link" in markup
    assert 'href="https://example.com/news"' in markup
    assert 'target="_blank"' in markup
    assert 'rel="noopener noreferrer"' in markup
    assert "元記事を見る" in markup
    assert "公開日" in markup
    assert "2026-06-01" in markup
    assert "事業影響あり" in markup
    assert "公式確認が必要" in markup
    assert "URL: https://example.com/news" not in markup
    assert "SMAI 投資判断サマリー" not in markup


def test_company_research_summary_panel_hides_ai_reading_notes_initially(monkeypatch):
    summary = CompanyResearchSummary(
        symbol="7203.T",
        overview=CompanyOverviewSummary(
            company_name="Toyota Motor Corporation",
            symbol="7203.T",
            business_overview="自動車の製造・販売を中心とする企業です。",
            business_segments=["自動車"],
            regions=["日本"],
            scale_summary="規模情報は追加確認が必要です。",
            recent_focus="直近ニュースは未取得です。",
            evidence_level="medium",
        ),
        quantitative=QuantitativeSummary(),
        ai_reading_notes=["AI内部メモです。"],
    )
    markdown_calls: list[str] = []

    monkeypatch.setattr(
        st,
        "markdown",
        lambda body, **_: markdown_calls.append(str(body)),
    )

    _render_company_research_summary_panel(summary)

    markup = "".join(markdown_calls)
    assert "企業リサーチサマリー" in markup
    assert "AI読み取りメモ" not in markup
    assert "AI内部メモです。" not in markup


def test_etf_research_summary_html_uses_fund_sections_and_avoids_company_ir_terms():
    summary = ETFResearchSummary(
        symbol="SPY",
        fund_name="SPDR S&P 500 ETF Trust",
        provider_name="State Street",
        fund_overview=(
            "外部プロフィールから、SPDR S&P 500 ETF Trustは米国・株式・S&P 500を"
            "確認対象とするETFとして整理できます。"
        ),
        investment_target="S&P 500などの米国大型株指数に連動する投資対象です。",
        asset_class="株式",
        region_focus="米国",
        expense_ratio="0.09%",
        dividend_yield="1.2%",
        aum="500B USD",
        nav="540.25 USD",
        top_holdings=["Apple", "Microsoft", "NVIDIA"],
        benchmark_index="S&P 500",
        missing_items=["月次レポート"],
        evidence_level="medium",
    )

    markup = _etf_research_summary_html(summary) + _etf_question_summary_html(summary)

    assert "ETFリサーチサマリー" in markup
    assert "ファンド概要" in markup
    assert "ETF理解の確認ポイント" in markup
    assert "経費率" in markup
    assert "分配金利回り" in markup
    assert "上位保有銘柄" in markup
    assert "企業リサーチサマリー" not in markup
    assert "決算短信" not in markup
    assert "有価証券報告書" not in markup


def test_foreign_stock_ir_and_questions_avoid_domestic_disclosure_terms():
    items = [
        IRSummaryItem(
            document_type="決算短信",
            title="未取得",
            availability="missing",
            information_status="missing",
            summary="決算短信は未取得です。公式IR、TDnet、EDINETで追加確認してください。",
            evidence_level="missing",
        ),
        IRSummaryItem(
            document_type="有価証券報告書",
            title="未取得",
            availability="missing",
            information_status="missing",
            summary="有価証券報告書は未取得です。公式IR、TDnet、EDINETで追加確認してください。",
            evidence_level="missing",
        ),
    ]
    summary = InvestmentQuestionSummary(
        symbol="MSFT",
        answers=[
            InvestmentQuestionAnswer(
                category="key_takeaway",
                question="この銘柄を見るうえで一番重要な論点は何か？",
                answer="決算短信・有価証券報告書・決算説明資料を確認してください。TDnetとEDINETも確認します。",
                evidence_level="missing",
                missing_reason="決算短信が未取得です。",
            )
        ],
        top_takeaway="決算短信と有価証券報告書が未取得です。",
        missing_critical_items=["決算短信"],
    )

    markup = _ir_summary_html(items, security_type="foreign_stock")
    markup += _news_summary_html(
        [
            NewsSummaryItem(
                topic_type="tdnet",
                title="Company release",
                summary="Official company release.",
                source_title="Company IR",
                official_confirmation_required=False,
                information_status="unparsed",
            )
        ],
        security_type="foreign_stock",
    )
    markup += _investment_question_summary_intro_html(summary, security_type="foreign_stock")
    markup += _investment_question_answers_html(summary.answers, security_type="foreign_stock")

    assert "海外IR情報サマリー" in markup
    assert "Earnings Release" in markup
    assert "Annual Report / 10-K" in markup
    assert "10-K / 10-Q" in markup
    assert "SEC Filing" in markup
    assert "Company Release" in markup
    assert "TDnet" not in markup
    assert "EDINET" not in markup
    assert "決算短信" not in markup
    assert "有価証券報告書" not in markup


def test_foreign_stock_ai_notes_avoid_domestic_disclosure_terms():
    markup = _company_research_ai_notes_html(
        [
            "追加確認する資料: 決算短信、有価証券報告書、決算説明資料を公式IRまたはTDnetで確認してください。",
            "不足している情報: 売上高、営業利益は追加確認が必要です。",
        ],
        security_type="foreign_stock",
    )

    assert "Earnings Release" in markup
    assert "Annual Report" in markup
    assert "Investor Presentation" in markup
    assert "公式IR" in markup
    assert "TDnet" not in markup
    assert "決算短信" not in markup
    assert "有価証券報告書" not in markup


def test_foreign_stock_company_summary_avoids_domestic_terms_and_nan_url():
    company_summary = CompanyResearchSummary(
        symbol="TSLA",
        overview=CompanyOverviewSummary(
            symbol="TSLA",
            company_name="Tesla, Inc.",
            business_overview="外部プロフィールから自動車事業を確認できます。",
            main_businesses=["自動車事業"],
            recent_focus="直近ニュースやTDnet情報から確認できる注目点はまだ限定的です。",
        ),
        quantitative=QuantitativeSummary(),
        ir_items=[],
        news_items=[],
        missing_critical_items=["決算短信", "適時開示"],
    )
    ir_markup = _ir_summary_html(
        [
            IRSummaryItem(
                document_type="有価証券報告書",
                title="Tesla Yahoo Finance Profile",
                availability="found",
                information_status="unparsed",
                source_url="nan",
            )
        ],
        security_type="foreign_stock",
    )

    markup = _company_research_summary_html(
        company_summary,
        security_type="foreign_stock",
    )
    markup += ir_markup

    assert "公式IR情報" in markup
    assert "Earnings Release" in markup
    assert "Company Release" in markup
    assert "URL:" not in markup
    assert ">nan<" not in markup
    assert "TDnet" not in markup
    assert "決算短信" not in markup
    assert "適時開示" not in markup


def test_investment_question_summary_html_prioritizes_initial_questions():
    categories = [
        ("business_model", "この会社は何で稼いでいるか？", "事業概要を確認できます。", "medium"),
        (
            "financial_trend",
            "売上・利益は伸びているか？",
            "業績トレンドは追加確認が必要です。",
            "missing",
        ),
        ("profitability", "利益率は良いか？", "収益性は判断できません。", "missing"),
        ("forecast", "今期見通しは強いか？", "通期予想は未取得です。", "missing"),
        ("growth_driver", "成長ドライバーは何か？", "成長材料は追加確認が必要です。", "low"),
        ("risk", "注意すべきリスクは何か？", "リスク情報は未取得です。", "missing"),
        ("shareholder_return", "株主還元はどうか？", "配当方針は未取得です。", "missing"),
        ("valuation", "割高・割安感はあるか？", "PER/PBR/ROEは未取得です。", "missing"),
        (
            "recent_news_impact",
            "直近ニュースは業績に影響しそうか？",
            "ニュースは未取得です。",
            "missing",
        ),
        (
            "key_takeaway",
            "この銘柄を見るうえで一番重要な論点は何か？",
            "主要な定量情報を確認することが最重要です。",
            "missing",
        ),
    ]
    summary = InvestmentQuestionSummary(
        symbol="7203.T",
        answers=[
            InvestmentQuestionAnswer(
                category=category,
                question=question,
                answer=answer,
                evidence_level=evidence_level,
                source_titles=["Yahoo Finance Profile"] if category == "business_model" else [],
            )
            for category, question, answer, evidence_level in categories
        ],
        top_takeaway="主要な定量情報を確認することが最重要です。",
        missing_critical_items=["売上高", "PER / PBR / ROE"],
    )

    primary_answers = _investment_question_primary_answers(summary)
    secondary_answers = _investment_question_secondary_answers(summary)
    markup = _investment_question_summary_intro_html(summary)
    markup += _investment_question_answers_html(primary_answers)

    assert [answer.category for answer in primary_answers] == [
        "business_model",
        "financial_trend",
        "forecast",
        "growth_driver",
        "key_takeaway",
    ]
    assert [answer.category for answer in secondary_answers] == [
        "profitability",
        "risk",
        "shareholder_return",
        "valuation",
        "recent_news_impact",
    ]
    assert "企業理解の確認ポイント" in markup
    assert "Q. この会社は何で稼いでいるか？" in markup
    assert "根拠: 中" in markup
    assert "根拠: 不足" in markup
    assert "利益率は良いか？" not in markup


def test_research_summary_advanced_detail_omits_duplicate_reading_sections(monkeypatch):
    evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-1",
        chunk_id="chunk-1",
        title="7203 Research Note",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Growth",
        excerpt="Growth strategy and shareholder returns are discussed.",
        relevance_score=Decimal("0.82"),
        reliability=Decimal("0.88"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="成長戦略を確認材料として整理します。",
                evidence=[evidence],
            )
        ],
        evidence=[evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    research_score = ResearchScoreService().score_report(report)
    monkeypatch.setattr(
        "ui.app._research_summary_bundle",
        lambda *args, **kwargs: SimpleNamespace(
            company_summary=None,
            etf_summary=None,
            question_summary=None,
            security_type="domestic_stock",
            research_score=research_score,
        ),
    )
    rendered: list[str] = []
    monkeypatch.setattr(
        st,
        "expander",
        lambda label, expanded=False: rendered.append(str(label)) or _FakeExpander(),
    )
    monkeypatch.setattr(st, "caption", lambda text, *args, **kwargs: rendered.append(str(text)))
    monkeypatch.setattr(st, "markdown", lambda text, *args, **kwargs: rendered.append(str(text)))
    monkeypatch.setattr(st, "warning", lambda text, *args, **kwargs: rendered.append(str(text)))
    monkeypatch.setattr(st, "divider", lambda *args, **kwargs: rendered.append("---"))
    monkeypatch.setattr(
        "ui.app._render_compact_dataframe",
        lambda rows: rendered.append(json.dumps(rows, ensure_ascii=False)),
    )

    _render_research_summary_panel(report, detail_expanded=False)

    rendered_text = "\n".join(rendered)
    assert "詳細情報・開発者向け" in rendered_text
    assert "Research Score" in rendered_text
    assert "検索品質" in rendered_text or "根拠資料の詳細" in rendered_text
    assert "AI読み取りメモ" not in rendered_text
    assert "根拠確認（会社概要・確認できた事実）" not in rendered_text
    assert "出典カード" not in rendered_text
    assert "その他の確認ポイント" not in rendered_text


def test_research_score_rows_explain_optional_context_without_advice():
    evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-1",
        chunk_id="chunk-1",
        title="7203 Research Note",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Growth",
        excerpt=(
            "Growth strategy, profitability margin, dividend policy, cash, "
            "and regulation risk are discussed."
        ),
        relevance_score=Decimal("0.82"),
        reliability=Decimal("0.88"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="成長戦略を確認材料として整理します。",
                evidence=[evidence],
            )
        ],
        evidence=[evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    score = ResearchScoreService().score_report(report)

    summary_rows = _research_score_summary_rows(score)
    component_rows = _research_score_component_rows(score)
    warning_rows = _research_score_warning_rows(score)
    cockpit_guidance_rows = _research_score_guidance_rows("cockpit")

    assert summary_rows[0]["確認項目"] == "Research Score"
    assert "売買推奨ではありません" in summary_rows[0]["確認ポイント"]
    assert "ランキング順位を変えません" in summary_rows[0]["確認ポイント"]
    assert summary_rows[2]["内容"] == "1件"
    assert "根拠資料の確認材料" in _research_score_expander_label("cockpit")
    assert "深掘り" in _research_score_context_caption("cockpit")
    assert "順位計算ではなく" in _research_score_context_caption("ranking")
    assert cockpit_guidance_rows[-1]["確認項目"] == "順位への影響"
    assert "ランキング順位を変更しません" in cockpit_guidance_rows[-1]["内容"]
    assert component_rows[0]["観点"] == "成長材料"
    assert component_rows[-1]["観点"] == "情報の鮮度"
    assert any("根拠が不足" in row["注意点"] for row in warning_rows)


def test_research_terms_preview_keeps_search_quality_table_compact():
    terms = [f"term{i}" for i in range(14)]

    assert (
        _research_terms_preview(terms, limit=5)
        == "term0 / term1 / term2 / term3 / term4 / ... (+9)"
    )


def test_stock_news_display_rows_keep_traceable_news_fields():
    report = StockNewsReport(
        symbol="7203.T",
        company_name="Toyota",
        as_of=date(2026, 5, 25),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                company_name="Toyota",
                title="7203 raises guidance",
                url="https://example.com/7203",
                source="Example News",
                published_at=date(2026, 5, 24),
                summary="Guidance was raised after revenue growth.",
                investment_viewpoint="earnings",
                sentiment_for_investment="positive",
                freshness_status="latest",
            )
        ],
    )

    rows = _stock_news_display_rows(report)
    markup = _research_table_html(rows, class_name="research-summary-table")

    assert rows == [
        {
            "タイトル": "7203 raises guidance",
            "URL": "https://example.com/7203",
            "出典": "Example News",
            "公開日": "2026-05-24",
            "要約": "Guidance was raised after revenue growth.",
            "確認観点": "業績",
            "材料分類": "ポジティブ材料",
            "鮮度": "latest",
        }
    ]
    assert "https://example.com/7203" in markup


def test_external_research_fetch_rows_show_transient_sources_without_storage_paths():
    result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="yahoo_finance",
        fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="7203.T Yahoo Finance Profile",
                symbol="7203.T",
                source_type="provider_profile",
                source_url="https://finance.yahoo.com/quote/7203.T/profile",
                provider="yahoo_finance",
                published_at=None,
                fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
                freshness_status="unknown",
                document_id="research-doc-abc123",
                retention_policy="session",
                content_summary="Toyota sells vehicles globally and invests in growth.",
            )
        ],
        retention_policy="session",
        warnings=["追加ニュースは見つかりませんでした。"],
    )

    summary_rows = _external_research_fetch_summary_rows(result)
    entry_rows = _external_research_fetch_result_rows(result)

    assert summary_rows == [
        {"項目": "取得元", "内容": "yahoo_finance"},
        {"項目": "取得日時", "内容": "2026-05-27T12:30+00:00"},
        {"項目": "登録資料数", "内容": "1件"},
        {"項目": "取得元別状況", "内容": "1件取得"},
        {"項目": "保持方針", "内容": "このセッションのみ"},
        {"項目": "注意", "内容": "追加ニュースは見つかりませんでした。"},
    ]
    assert entry_rows == [
        {
            "資料名": "7203.T Yahoo Finance Profile",
            "資料種別": "取得元プロフィール",
            "取得元": "yahoo_finance",
            "公開日": "未確認",
            "鮮度": "未確認",
            "取得日時": "2026-05-27T12:30+00:00",
            "URL": "https://finance.yahoo.com/quote/7203.T/profile",
            "要約": "Toyota sells vehicles globally and invests in growth.",
        }
    ]


def test_external_research_source_cards_explain_how_to_read_each_source():
    edinet_source_url = "https://disclosure.edinet-fsa.go.jp/api/v2/documents/S100TOYOTA?type=2"
    result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="edinet_tdnet_company_ir_google_news_yahoo_finance",
        fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="7203 EDINET 有価証券報告書",
                symbol="7203.T",
                source_type="annual_report",
                source_url=edinet_source_url,
                provider="edinet",
                published_at=date(2026, 5, 27),
                fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
                freshness_status="latest",
                document_id="research-doc-edinet",
                retention_policy="session",
                content_summary="EDINET official filing metadata.",
            ),
            ExternalResearchFetchManifestEntry(
                title="7203 TDnet 決算短信",
                symbol="7203.T",
                source_type="tdnet",
                source_url="https://www.release.tdnet.info/inbs/example.pdf",
                provider="tdnet",
                published_at=date(2026, 5, 27),
                fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
                freshness_status="latest",
                document_id="research-doc-tdnet",
                retention_policy="session",
                content_summary="2026年3月期の決算短信です。",
            ),
            ExternalResearchFetchManifestEntry(
                title="Toyota 公式IRサイト",
                symbol="7203.T",
                source_type="company_ir",
                source_url="https://global.toyota/jp/ir/",
                provider="company_ir_site",
                published_at=None,
                fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
                freshness_status="unknown",
                document_id="research-doc-company-ir",
                retention_policy="session",
                content_summary="公式IRサイトのInvestor Relationsページです。",
            ),
            ExternalResearchFetchManifestEntry(
                title="7203 Yahoo Finance Profile",
                symbol="7203.T",
                source_type="provider_profile",
                source_url="https://finance.yahoo.com/quote/7203.T/profile",
                provider="yahoo_finance",
                published_at=None,
                fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
                freshness_status="unknown",
                document_id="research-doc-profile",
                retention_policy="session",
                content_summary=(
                    "Company Name: Toyota Motor Corporation Provider Symbol: 7203.T "
                    "Quote Type: EQUITY Website: https://example.com "
                    "Business Summary: Toyota sells vehicles globally."
                ),
            ),
        ],
        retention_policy="session",
    )

    overview = _external_research_fetch_overview_html(result)
    cards = _external_research_source_cards_html(result)

    assert "外部参照ソースの確認メモ" in overview
    assert "EDINET / TDnet / 企業IR / Google News / Yahoo Finance" in overview
    assert "公式開示" in overview
    assert "4件" in overview
    assert "EDINET" in cards
    assert "EDINETなどの公式開示" in cards
    assert "TDnet（適時開示）" in cards
    assert "PDF本文で対象期間" in cards
    assert "企業IRサイト" in cards
    assert "掲載資料の公開日" in cards
    assert "外部データ" in cards
    assert "Toyota sells vehicles globally" in cards
    assert "Provider Symbol" not in cards
    assert "Quote Type" not in cards
    assert "Website:" not in cards
    assert "https://example.com" not in cards
    assert "出典を開く" in cards
    assert "external://" not in cards


def test_external_research_overview_shows_provider_status_chips_and_timeout_warning():
    result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="edinet_tdnet_company_ir_google_news_yahoo_finance",
        fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="7203 TDnet 決算短信",
                symbol="7203.T",
                source_type="tdnet",
                source_url="https://www.release.tdnet.info/inbs/example.pdf",
                provider="tdnet",
                published_at=date(2026, 5, 27),
                fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
                freshness_status="latest",
                document_id="research-doc-tdnet",
                retention_policy="session",
                content_summary="2026年3月期の決算短信です。",
            )
        ],
        retention_policy="session",
        warnings=["一部の取得元は時間切れになりました。取得済みの情報のみ表示しています。"],
        provider_statuses=[
            ResearchSourceTrace(
                source="tdnet",
                provider="tdnet",
                status="success",
                elapsed_ms=1200,
                result_count=1,
                timestamp=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
            ),
            ResearchSourceTrace(
                source="yahoo_finance",
                provider="yahoo_finance",
                status="timeout",
                elapsed_ms=30000,
                error_type="TimeoutError",
                error_message_short="Yahoo did not finish in time.",
                result_count=0,
                timestamp=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
            ),
        ],
    )

    overview = _external_research_fetch_overview_html(result)
    rows = _external_research_fetch_summary_rows(result)

    assert "1件取得" in overview
    assert "TDnet（適時開示） 1件" in overview
    assert "Yahoo Finance 時間切れ" in overview
    assert "一部の取得元は時間切れ" in overview
    expected_status_row = {
        "項目": "取得元別状況",
        "内容": "1件取得 / TDnet（適時開示） 1 / Yahoo Finance 時間切れ",
    }
    assert expected_status_row in rows
    assert any(row["項目"] == "Yahoo Finance" and "TimeoutError" not in row["内容"] for row in rows)


def test_news_source_link_rows_prioritize_url_sources_and_hide_raw_fields():
    result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="edinet_tdnet_company_ir_google_news_yahoo_finance",
        fetched_at=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="7203 EDINET 有価証券報告書",
                symbol="7203.T",
                source_type="annual_report",
                source_url="https://disclosure.edinet-fsa.go.jp/example",
                provider="edinet",
                published_at=date(2026, 5, 30),
                fetched_at=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
                freshness_status="latest",
                document_id="research-doc-edinet",
                retention_policy="session",
                content_summary="EDINET official filing metadata.",
            ),
            ExternalResearchFetchManifestEntry(
                title="7203 TDnet 決算短信",
                symbol="7203.T",
                source_type="tdnet",
                source_url="https://www.release.tdnet.info/inbs/example.pdf",
                provider="tdnet",
                published_at=date(2026, 5, 31),
                fetched_at=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
                freshness_status="latest",
                document_id="research-doc-tdnet",
                retention_policy="session",
                content_summary="決算短信のPDFです。",
            ),
            ExternalResearchFetchManifestEntry(
                title="Toyota 公式IRサイト",
                symbol="7203.T",
                source_type="company_ir",
                source_url="https://global.toyota/jp/ir/",
                provider="company_ir_site",
                published_at=None,
                fetched_at=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
                freshness_status="unknown",
                document_id="research-doc-company-ir",
                retention_policy="session",
                content_summary="公式IRサイトです。",
            ),
            ExternalResearchFetchManifestEntry(
                title="7203 Yahoo Finance Profile",
                symbol="7203.T",
                source_type="provider_profile",
                source_url="https://finance.yahoo.com/quote/7203.T/profile",
                provider="yahoo_finance",
                published_at=None,
                fetched_at=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
                freshness_status="unknown",
                document_id="research-doc-yahoo",
                retention_policy="session",
                content_summary=(
                    "Company Name: Toyota Provider Symbol: 7203.T Quote Type: EQUITY "
                    "Website: https://example.com Business Summary: Toyota sells vehicles globally."
                ),
            ),
            ExternalResearchFetchManifestEntry(
                title="7203 決算説明資料",
                symbol="7203.T",
                source_type="earnings_presentation",
                source_url="https://example.com/presentation.pdf",
                provider="example_provider",
                published_at=date(2026, 5, 29),
                fetched_at=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
                freshness_status="recent",
                document_id="research-doc-presentation",
                retention_policy="session",
                content_summary="決算説明資料です。",
            ),
        ],
        retention_policy="session",
    )
    summary_items = [
        NewsSummaryItem(
            topic_type="news",
            title="Toyota expands software services",
            summary="ソフトウェア領域のニュースです。",
            source_title="Example News",
            source_url="https://example.com/news",
            published_at=date(2026, 6, 1),
            impact_hint="business",
            information_status="unverified",
        ),
    ]

    rows = _news_source_link_rows(
        summary_items,
        news_report=None,
        external_research_result=result,
    )
    panel_html = _news_source_links_panel_html(rows, total_url_count=6, news_url_count=1)

    assert len(rows) == 5
    assert [row["source_label"] for row in rows] == [
        "ニュース",
        "TDnet適時開示",
        "企業IRサイト",
        "EDINET",
        "Yahoo Finance",
    ]
    assert "元記事を見る" in panel_html
    assert "TDnetで見る" in panel_html
    assert "企業IRで見る" in panel_html
    assert "EDINETで見る" in panel_html
    assert "Yahoo Financeで見る" in panel_html
    assert "news-source-citation-panel" in panel_html
    assert "news-source-citation-list" in panel_html
    assert "news-source-citation-item" in panel_html
    assert "news-source-citation-title-line" in panel_html
    assert "news-source-citation-meta" in panel_html
    assert "news-source-citation-action" in panel_html
    assert "Market Intelligence" not in panel_html
    assert "market-news-grid" not in panel_html
    assert "market-news-item" not in panel_html
    assert 'href="https://example.com/news"' in panel_html
    assert 'target="_blank"' in panel_html
    assert 'rel="noopener noreferrer"' in panel_html
    assert "ほか 1件は下部の外部参照ソース" in panel_html
    assert "Provider Symbol" not in panel_html
    assert "Quote Type" not in panel_html
    assert "Website:" not in panel_html
    assert "https://example.com Business Summary" not in panel_html


def test_news_source_links_panel_guides_to_external_urls_when_news_url_is_missing():
    result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="yahoo_finance",
        fetched_at=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="7203 Yahoo Finance Profile",
                symbol="7203.T",
                source_type="provider_profile",
                source_url="https://finance.yahoo.com/quote/7203.T/profile",
                provider="yahoo_finance",
                published_at=None,
                fetched_at=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
                freshness_status="unknown",
                document_id="research-doc-yahoo",
                retention_policy="session",
                content_summary="Toyota sells vehicles globally.",
            ),
        ],
        retention_policy="session",
    )

    rows = _news_source_link_rows(
        [],
        news_report=StockNewsReport(symbol="7203.T", as_of=date(2026, 6, 2)),
        external_research_result=result,
    )
    panel_html = _news_source_links_panel_html(rows, total_url_count=len(rows), news_url_count=0)

    assert "ニュース専用のURL付き根拠は見つかりませんでした。" in panel_html
    assert "外部参照ソースにURL付きの公式資料・provider情報があります。" in panel_html
    assert "Yahoo Finance" in panel_html
    assert "Yahoo Financeで見る" in panel_html
    assert "URL表示は未実装" not in panel_html


def test_investment_hint_news_panel_html_surfaces_news_only_cards():
    report = StockNewsReport(
        symbol="7203.T",
        as_of=date(2026, 6, 2),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                title="Toyota raises software investment",
                url="https://example.com/toyota-growth",
                source="Example News",
                published_at=date(2026, 6, 1),
                summary="Toyota increased software investment for new services.",
                investment_viewpoint="growth",
                sentiment_for_investment="positive",
                freshness_status="latest",
            ),
            StockNewsEvidence(
                symbol="7203.T",
                title="Tariff risk rises",
                url="https://example.com/toyota-risk",
                source="Example News",
                published_at=date(2026, 6, 2),
                summary="Tariff headline adds export uncertainty.",
                investment_viewpoint="risk",
                sentiment_for_investment="negative",
                freshness_status="recent",
            ),
        ],
    )

    panel_html = _investment_hint_news_panel_html(report)

    assert "投資ヒントとなるニュース" in panel_html
    assert "注目材料 Top 3" in panel_html
    assert "外部ニュースの見出しだけ" in panel_html
    assert "クリックして" in panel_html
    assert "market-intelligence-panel spotlight" in panel_html
    assert "news-feed-top-list" in panel_html
    assert "news-feed-item-clickable" in panel_html
    assert "top-material-card" in panel_html
    assert "market-news-main" in panel_html
    assert "market-news-aside" in panel_html
    assert "research-news-headline-card" in panel_html
    assert "Toyota raises software investment" in panel_html
    assert "Tariff risk rises" in panel_html
    assert "事業成長" in panel_html
    assert "リスク材料" in panel_html
    assert "公開日" in panel_html
    assert "2026-06-01" in panel_html
    assert "鮮度" in panel_html
    assert "最新" in panel_html
    assert "最近" in panel_html
    assert "https://example.com/toyota-growth" in panel_html
    assert "https://example.com/toyota-risk" in panel_html
    assert 'href="https://example.com/toyota-growth"' in panel_html
    assert 'target="_blank"' in panel_html
    assert 'rel="noopener noreferrer"' in panel_html
    assert "news-feed-item-clickable important" in panel_html
    assert "news-feed-item-clickable risk" in panel_html
    assert panel_html.count("元記事を見る") == 2
    assert "なぜ見るか" not in panel_html
    assert "追加確認:" not in panel_html
    assert "TDnet" not in panel_html
    assert "Provider Symbol" not in panel_html


def test_investment_hint_news_panel_html_skips_news_without_displayable_url_and_limits():
    report = StockNewsReport(
        symbol="AAPL",
        as_of=date(2026, 6, 2),
        news=[
            StockNewsEvidence(
                symbol="AAPL",
                title="Apple url missing",
                url="nan",
                source="Example News",
                summary="URLなしのニュースです。",
            ),
            *[
                StockNewsEvidence(
                    symbol="AAPL",
                    title=f"Apple news {index}",
                    url=f"https://example.com/apple-{index}",
                    source="Example News",
                    summary="Apple product and service update.",
                    investment_viewpoint="growth",
                    sentiment_for_investment="neutral",
                    freshness_status="recent",
                )
                for index in range(1, 5)
            ],
        ],
    )

    panel_html = _investment_hint_news_panel_html(report, limit=3)

    assert "Apple url missing" not in panel_html
    assert "https://example.com/apple-1" in panel_html
    assert "https://example.com/apple-3" in panel_html
    assert "https://example.com/apple-4" not in panel_html
    assert "ほか 1件" in panel_html
    assert panel_html.count("元記事を見る") == 3


def test_investment_hint_news_panel_html_is_empty_without_url_backed_news():
    report = StockNewsReport(
        symbol="NOURL",
        as_of=date(2026, 6, 2),
        news=[
            StockNewsEvidence(
                symbol="NOURL",
                title="No URL news",
                url="none",
                source="Example News",
                summary="URLなしです。",
            )
        ],
    )

    assert _investment_hint_news_panel_html(None) == ""
    assert _investment_hint_news_panel_html(report) == ""


def test_news_source_links_expander_label_shows_url_count():
    assert _news_source_links_expander_label(3) == "ニュース・開示の出典を表示（URL付き3件）"
    assert _news_source_links_expander_label(0) == "ニュース・開示の出典を表示（URL付き0件）"
    assert _news_source_links_expander_expanded(3) is False
    assert _news_source_links_expander_expanded(0) is False


def test_news_source_links_panel_fallback_is_not_implementation_gap_wording():
    panel_html = _news_source_links_panel_html([], total_url_count=0, news_url_count=0)

    assert "ニュース専用のURL付き根拠は見つかりませんでした。" in panel_html
    assert "news-source-citation-panel" in panel_html
    assert (
        "関連する公式開示・企業IR・provider情報は外部参照ソースも確認してください。" in panel_html
    )
    assert "URL表示は未実装" not in panel_html
    assert "情報が存在しません" not in panel_html


def test_news_source_link_rows_cover_broad_symbol_case_matrix():
    fetched_at = datetime(2026, 6, 2, 12, 30, tzinfo=UTC)
    cases = [
        {
            "label": "国内大型株",
            "symbol": "7203.T",
            "summary_items": [
                NewsSummaryItem(
                    title="Toyota software news",
                    summary="ソフトウェア領域のニュースです。",
                    source_title="Example News",
                    source_url="https://example.com/7203-news",
                    published_at=date(2026, 6, 1),
                )
            ],
            "entries": [
                ExternalResearchFetchManifestEntry(
                    title="7203 TDnet 決算短信",
                    symbol="7203.T",
                    source_type="tdnet",
                    source_url="https://www.release.tdnet.info/inbs/7203.pdf",
                    provider="tdnet",
                    published_at=date(2026, 5, 31),
                    fetched_at=fetched_at,
                    freshness_status="latest",
                    document_id="doc-7203-tdnet",
                    retention_policy="session",
                    content_summary="決算短信のPDFです。",
                )
            ],
            "expected_label": "ニュース",
            "expected_text": "元記事を見る",
        },
        {
            "label": "国内大型株 大阪ガス",
            "symbol": "9532.T",
            "summary_items": [],
            "entries": [
                ExternalResearchFetchManifestEntry(
                    title="大阪ガス 企業IRサイト",
                    symbol="9532.T",
                    source_type="company_ir",
                    source_url="https://www.osakagas.co.jp/ir/",
                    provider="company_ir_site",
                    published_at=None,
                    fetched_at=fetched_at,
                    freshness_status="unknown",
                    document_id="doc-9532-ir",
                    retention_policy="session",
                    content_summary="公式IRサイトです。",
                )
            ],
            "expected_label": "企業IRサイト",
            "expected_text": "外部参照ソースにURL付きの公式資料・provider情報があります。",
        },
        {
            "label": "国内中小型株",
            "symbol": "4493.T",
            "summary_items": [],
            "entries": [
                ExternalResearchFetchManifestEntry(
                    title="4493 Yahoo Finance Profile",
                    symbol="4493.T",
                    source_type="provider_profile",
                    source_url="https://finance.yahoo.com/quote/4493.T/profile",
                    provider="yahoo_finance",
                    published_at=None,
                    fetched_at=fetched_at,
                    freshness_status="unknown",
                    document_id="doc-4493-yahoo",
                    retention_policy="session",
                    content_summary="Business Summary: クラウド関連サービスです。",
                )
            ],
            "expected_label": "Yahoo Finance",
            "expected_text": "Yahoo Financeで見る",
        },
        {
            "label": "米国大型株",
            "symbol": "AAPL",
            "summary_items": [
                NewsSummaryItem(
                    title="Apple product news",
                    summary="製品サービスに関するニュースです。",
                    source_title="Example News",
                    source_url="https://example.com/aapl-news",
                    published_at=date(2026, 6, 1),
                )
            ],
            "entries": [
                ExternalResearchFetchManifestEntry(
                    title="AAPL Yahoo Finance Profile",
                    symbol="AAPL",
                    source_type="provider_profile",
                    source_url="https://finance.yahoo.com/quote/AAPL/profile",
                    provider="yahoo_finance",
                    published_at=None,
                    fetched_at=fetched_at,
                    freshness_status="unknown",
                    document_id="doc-aapl-yahoo",
                    retention_policy="session",
                    content_summary="Business Summary: Consumer electronics.",
                )
            ],
            "expected_label": "ニュース",
            "expected_text": "元記事を見る",
        },
        {
            "label": "ETF",
            "symbol": "SPY",
            "summary_items": [],
            "entries": [
                ExternalResearchFetchManifestEntry(
                    title="SPY Yahoo Finance Profile",
                    symbol="SPY",
                    source_type="provider_profile",
                    source_url="https://finance.yahoo.com/quote/SPY/profile",
                    provider="yahoo_finance",
                    published_at=None,
                    fetched_at=fetched_at,
                    freshness_status="unknown",
                    document_id="doc-spy-yahoo",
                    retention_policy="session",
                    content_summary="Business Summary: ETF profile.",
                )
            ],
            "expected_label": "Yahoo Finance",
            "expected_text": "Yahoo Financeで見る",
        },
        {
            "label": "URLなし",
            "symbol": "NOURL",
            "summary_items": [
                NewsSummaryItem(
                    title="URL missing news",
                    summary="URLなしのニュースです。",
                    source_title="Example News",
                    source_url=None,
                )
            ],
            "entries": [],
            "expected_label": None,
            "expected_text": "関連する公式開示・企業IR・provider情報は外部参照ソースも確認してください。",
        },
    ]

    for case in cases:
        result = ExternalResearchFetchResult(
            symbol=str(case["symbol"]),
            provider="fixture",
            fetched_at=fetched_at,
            entries=case["entries"],
            retention_policy="session",
        )
        rows = _news_source_link_rows(
            case["summary_items"],
            news_report=None,
            external_research_result=result,
        )
        panel_html = _news_source_links_panel_html(
            rows,
            total_url_count=len(rows),
            news_url_count=sum(1 for row in rows if row["source_kind"] == "news"),
        )

        if case["expected_label"] is not None:
            assert any(row["source_label"] == case["expected_label"] for row in rows), case["label"]
        else:
            assert rows == [], case["label"]
        assert str(case["expected_text"]) in panel_html, case["label"]
        assert "Provider Symbol" not in panel_html
        assert "取得本文全文" not in panel_html


def test_external_research_fetch_result_rows_clean_provider_raw_summary():
    result = ExternalResearchFetchResult(
        symbol="ACME",
        provider="yahoo_finance",
        fetched_at=datetime(2026, 6, 1, 12, 30, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="ACME Yahoo Finance Profile",
                symbol="ACME",
                source_type="provider_profile",
                source_url="https://finance.yahoo.com/quote/ACME/profile",
                provider="yahoo_finance",
                published_at=date(2026, 6, 1),
                fetched_at=datetime(2026, 6, 1, 12, 30, tzinfo=UTC),
                freshness_status="latest",
                document_id="research-doc-profile",
                retention_policy="session",
                content_summary=(
                    "Company Name: Acme Corporation Provider Symbol: ACME Quote Type: EQUITY "
                    "Exchange: NMS Currency: USD Website: https://example.com "
                    "Business Summary: Acme provides cloud platform services."
                ),
            )
        ],
        retention_policy="session",
    )

    rows = _external_research_fetch_result_rows(result)

    assert rows[0]["要約"] == "Acme provides cloud platform services."
    assert "Provider Symbol" not in rows[0]["要約"]
    assert "Quote Type" not in rows[0]["要約"]
    assert "Website:" not in rows[0]["要約"]
    assert "https://example.com" not in rows[0]["要約"]


def test_external_research_fetch_failure_caption_hides_provider_raw_details():
    exc = DataSourceError(
        "Yahoo Finance profile fetch failed.",
        details={"provider": "yahoo_finance"},
    )

    caption = _external_research_fetch_failure_caption(exc)

    assert "保存済み資料と既存データ" in caption
    assert "ネットワーク設定" in caption
    assert "Yahoo Finance profile fetch failed" not in caption
    assert "provider" not in caption


def test_research_news_warning_display_text_hides_internal_source_type():
    warning = (
        "URL付きのニュース根拠が見つかりませんでした。"
        "必要な場合は source_type=news の資料に URL を含めて登録してください。"
    )

    text = _research_news_warning_display_text(warning)

    assert "ニュース専用のURL付き根拠" in text
    assert "外部参照ソースも確認" in text
    assert "source_type" not in text
    assert "売買" not in text


def test_research_news_warning_display_text_points_to_url_panel_when_external_urls_exist():
    warning = "URL付きのニュース根拠が見つかりませんでした。"

    text = _research_news_warning_display_text(warning, has_external_source_urls=True)

    assert "ニュース・開示の出典" in text
    assert "公式資料・企業IR・provider情報のURL" in text
    assert "外部参照ソースも確認してください" not in text
    assert "source_type" not in text


def test_fetch_external_research_for_preview_uses_external_source_and_stores(monkeypatch):
    captured: dict[str, object] = {}
    result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="yahoo_finance",
        fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
        entries=[],
        retention_policy="session",
    )

    def fake_fetch_external_research_for_symbol(
        symbol: str,
        *,
        company_name: str | None,
        related_keywords: list[str] | None,
        as_of: date | None,
        allow_network: bool,
    ) -> ExternalResearchFetchResult:
        captured.update(
            {
                "symbol": symbol,
                "company_name": company_name,
                "related_keywords": related_keywords,
                "as_of": as_of,
                "allow_network": allow_network,
            }
        )
        return result

    monkeypatch.setattr("ui.app.symbol_name", lambda _symbol: "Toyota Motor")
    monkeypatch.setattr(
        "ui.app.fetch_external_research_for_symbol",
        fake_fetch_external_research_for_symbol,
    )
    st.session_state.clear()
    preview = MarketDataPreview(
        status="ok",
        bars=[_bar("2026-05-22", close=101, symbol="7203.T")],
        provider_rows=[],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[],
        screening_rows=[],
        error_rows=[],
    )

    fetched = _fetch_external_research_for_preview(preview)

    assert fetched is result
    assert captured == {
        "symbol": "7203.T",
        "company_name": "Toyota Motor",
        "related_keywords": ["Toyota Motor"],
        "as_of": date(2026, 5, 22),
        "allow_network": True,
    }
    assert st.session_state[MARKET_DATA_EXTERNAL_RESEARCH_FETCH_STATE_KEY] is result


def test_cockpit_research_refresh_uses_mascot_loading(monkeypatch):
    progress_messages: list[str] = []
    progress_values: list[float] = []

    class FakeLoadingSlot:
        def __init__(self) -> None:
            self.cleared = False

        def container(self):
            return nullcontext()

        def caption(self, message: str) -> None:
            progress_messages.append(message)

        def empty(self) -> None:
            self.cleared = True

    class FakeProgressBar:
        def progress(self, value: float) -> None:
            progress_values.append(value)

    slot = FakeLoadingSlot()
    loading_calls: list[tuple[str, dict[str, object]]] = []
    rerun_calls: list[bool] = []
    session_state: dict[str, object] = {}
    external_result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="fake",
        fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
        entries=[],
        retention_policy="session",
    )
    preview = MarketDataPreview(
        status="ok",
        bars=[],
        provider_rows=[],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[],
        screening_rows=[{"symbol": "7203.T"}],
        error_rows=[],
    )

    monkeypatch.setattr("ui.app.st.session_state", session_state)
    monkeypatch.setattr("ui.app.st.empty", lambda: slot)
    monkeypatch.setattr(
        "ui.app.st.progress",
        lambda value: progress_values.append(value) or FakeProgressBar(),
    )
    monkeypatch.setattr("ui.app.st.subheader", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.caption", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.info", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.rerun", lambda: rerun_calls.append(True))
    monkeypatch.setattr(
        "ui.app.render_mascot_loading",
        lambda variant, **kwargs: loading_calls.append((variant, kwargs)),
    )
    monkeypatch.setattr(
        "ui.app._render_research_operation_card",
        lambda *_, **__: True,
    )
    monkeypatch.setattr("ui.app._cockpit_research_report_from_state", lambda _: None)
    monkeypatch.setattr("ui.app._cockpit_stock_news_report_from_state", lambda _: None)
    monkeypatch.setattr(
        "ui.app._fetch_external_research_for_preview",
        lambda _: external_result,
    )
    monkeypatch.setattr(
        "ui.app._build_cockpit_research_report",
        lambda _: object(),
    )
    monkeypatch.setattr(
        "ui.app._build_cockpit_stock_news_report",
        lambda _: object(),
    )
    monkeypatch.setattr(
        "ui.app.external_research_fetch_cache_info",
        lambda: {"cache_hit": False},
    )

    _render_cockpit_research_summary(preview)

    assert loading_calls == [
        (
            "report",
            {
                "title": "AI調査を整理中",
                "message": (
                    "外部参照ソース、ニュース、保存済み資料を読み込み、"
                    "企業リサーチレポートにまとめています。"
                ),
                "tone": "info",
            },
        )
    ]
    assert slot.cleared is True
    assert rerun_calls == [True]
    assert progress_values == [0.0, 0.08, 0.24, 0.52, 0.70, 0.86, 0.96, 1.0]
    assert progress_messages == [
        "調査対象と取得元を確認しています。",
        "外部参照ソースとニュースを取得しています。",
        "外部参照ソースをAI調査に反映しています。",
        "企業リサーチレポートを生成しています。",
        "ニュースと開示材料を整理しています。",
        "表示内容を更新しています。",
        "AI調査の更新が完了しました。",
    ]


def test_ranking_symbol_research_lookup_reuses_cockpit_research_flow(monkeypatch):
    class FakeLoadingSlot:
        def __init__(self) -> None:
            self.cleared = False

        def container(self):
            return nullcontext()

        def empty(self) -> None:
            self.cleared = True

    slot = FakeLoadingSlot()
    calls: list[tuple[str, object]] = []
    stored: dict[str, object] = {}
    fake_report = object()
    fake_news_report = object()
    fake_external_result = SimpleNamespace(
        symbol="7751.T",
        entries=[object(), object()],
        warnings=[],
    )
    rendered: dict[str, object] = {}

    monkeypatch.setattr("ui.app.st.subheader", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.caption", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.success", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.warning", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.info", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.button", lambda *_, **__: True)
    monkeypatch.setattr("ui.app.st.empty", lambda: slot)
    monkeypatch.setattr("ui.app.render_mascot_loading", lambda *_, **__: None)

    def fake_fetch(symbol: str, *, as_of: date | None):
        calls.append(("external", (symbol, as_of)))
        return fake_external_result

    def fake_build_report(symbol: str, *, as_of: date | None):
        calls.append(("report", (symbol, as_of)))
        return fake_report

    def fake_build_news(symbol: str, *, as_of: date | None):
        calls.append(("news", (symbol, as_of)))
        return fake_news_report

    monkeypatch.setattr("ui.app._fetch_external_research_for_symbol", fake_fetch)
    monkeypatch.setattr("ui.app._build_research_report_for_symbol", fake_build_report)
    monkeypatch.setattr("ui.app._build_stock_news_report_for_symbol", fake_build_news)
    monkeypatch.setattr(
        "ui.app._store_ranking_external_research_result",
        lambda result: stored.__setitem__("external", result),
    )
    monkeypatch.setattr(
        "ui.app._store_ranking_research_report",
        lambda report: stored.__setitem__("report", report),
    )
    monkeypatch.setattr(
        "ui.app._store_ranking_stock_news_report",
        lambda report: stored.__setitem__("news", report),
    )
    monkeypatch.setattr("ui.app._ranking_research_report_from_state", lambda symbol: fake_report)
    monkeypatch.setattr(
        "ui.app._ranking_stock_news_report_from_state",
        lambda symbol: stored.get("news"),
    )
    monkeypatch.setattr(
        "ui.app._ranking_external_research_result_from_state",
        lambda symbol: stored.get("external"),
    )

    def fake_render_panel(report, **kwargs):
        rendered["report"] = report
        rendered.update(kwargs)

    monkeypatch.setattr("ui.app._render_research_summary_panel", fake_render_panel)

    app_module._render_ranking_symbol_research_lookup("7751.T")

    assert [name for name, _ in calls] == ["external", "report", "news"]
    assert all(args[0] == "7751.T" for _, args in calls)
    assert all(isinstance(args[1], date) for _, args in calls)
    assert stored == {
        "external": fake_external_result,
        "report": fake_report,
        "news": fake_news_report,
    }
    assert rendered["report"] is fake_report
    assert rendered["news_report"] is fake_news_report
    assert rendered["external_research_result"] is fake_external_result
    assert rendered["display_context"] == "ranking"
    assert slot.cleared is True


def test_fetch_external_research_for_symbol_reuses_session_ttl_cache(monkeypatch, tmp_path):
    class CountingResearchAdapter:
        provider = "fake_external"
        requires_network = False

        def __init__(self) -> None:
            self.calls = 0

        def fetch_sources(
            self, request: ExternalResearchFetchRequest
        ) -> list[ExternalResearchSourcePayload]:
            self.calls += 1
            return [
                ExternalResearchSourcePayload(
                    symbol=request.symbol,
                    title="7203 Cached Profile",
                    content="Company profile content.",
                    source_type="provider_profile",
                    source_url="https://example.com/profile",
                    provider=self.provider,
                    company_name=request.company_name,
                    published_at=request.as_of,
                    fetched_at=datetime(2026, 5, 27, 12, self.calls, tzinfo=UTC),
                    reliability=Decimal("0.65"),
                )
            ]

    session_state: dict[str, object] = {}
    monkeypatch.delenv("SMAI_PERFORMANCE_PROFILE", raising=False)
    monkeypatch.setattr("ui.research_state.st.session_state", session_state)
    monkeypatch.setattr("ui.research_state.autoload_local_research_documents", lambda: 0)
    monkeypatch.setattr("ui.research_state.research_document_dirs", lambda: [tmp_path])
    adapter = CountingResearchAdapter()

    first = fetch_external_research_for_symbol(
        "7203.T",
        company_name="Toyota",
        related_keywords=["Toyota"],
        as_of=date(2026, 5, 27),
        allow_network=False,
        adapter=adapter,
    )
    assert adapter.calls == 1
    assert external_research_fetch_cache_info()["cache_hit"] is False
    first_summary = external_research_fetch_last_summary()
    assert first_summary["performance_profile"] == "notebook"
    assert first_summary["symbol"] == "7203.T"
    assert first_summary["success_count"] == 1
    assert first_summary["failed_count"] == 0
    assert first_summary["no_result_count"] == 0
    assert first_summary["cache_hit_count"] == 0
    assert first_summary["source_count"] == 1
    assert first_summary["sources"][0]["status"] == "success"
    assert first_summary["sources"][0]["result_count"] == 1

    second = fetch_external_research_for_symbol(
        "7203.T",
        company_name="Toyota",
        related_keywords=["Toyota"],
        as_of=date(2026, 5, 27),
        allow_network=False,
        adapter=adapter,
    )

    assert adapter.calls == 1
    assert second is first
    assert external_research_fetch_cache_info()["cache_hit"] is True
    assert external_research_fetch_last_summary()["cache_hit_count"] == 1
    assert external_research_fetch_last_summary()["sources"][0]["status"] == "cache_hit"


def test_research_state_recognizes_dotted_symbol_and_source_type():
    provider_profile_path = Path("data/research_docs/7203.T_provider_profile_yahoo_finance.md")
    news_path = Path("data/research_docs/AAPL_news_yahoo_finance.md")

    assert _symbol_from_research_filename(provider_profile_path) == "7203.T"
    assert _source_type_from_research_filename(provider_profile_path) == "provider_profile"
    assert _symbol_from_research_filename(news_path) == "AAPL"
    assert _source_type_from_research_filename(news_path) == "news"


def test_research_phase21_rows_expose_grounded_answer_retrieval_and_claims():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary",
        points=[],
        evidence=[],
        extracted_claims=[
            ResearchExtractedClaim(
                symbol="7203.T",
                category="growth",
                claim="成長材料に関する確認材料があります。",
                summary="中期計画の記述を確認材料として整理します。",
                supporting_evidence=[],
                confidence=Decimal("0.75"),
            )
        ],
        grounded_answer=ResearchGroundedAnswer(
            symbol="7203.T",
            answer="登録済み資料から確認できる範囲の説明です。売買推奨ではありません。",
            referenced_evidence=[],
            claim_count=1,
            evidence_count=0,
            warnings=["追加確認が必要です。"],
        ),
        retrieval_quality=ResearchRetrievalQuality(
            backend="keyword",
            query="growth | risk",
            expanded_terms=["growth", "strategy"],
            candidate_count=4,
            evidence_count=2,
            warnings=[],
        ),
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=2,
            warnings=[],
        ),
    )

    grounded_rows = _research_grounded_answer_rows(report)
    retrieval_rows = _research_retrieval_quality_rows(report)
    claim_rows = _research_extracted_claim_rows(report)

    assert grounded_rows[0]["確認項目"] == "根拠付き要約"
    assert "売買推奨ではありません" in grounded_rows[0]["AI整理メモ"]
    assert retrieval_rows[0]["検索方式"] == "keyword"
    assert retrieval_rows[0]["確認項目"] == "検索品質"
    assert retrieval_rows[0]["関連語の一部"] == "growth / strategy"
    assert claim_rows[0]["観点"] == "growth"
    assert claim_rows[0]["信頼度"] == "0.75"


def test_research_evidence_report_section_carries_data_quality_warnings():
    warning = "検索できたResearch根拠の信頼度が低いため、出所を確認してください。"
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research warning summary",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=1,
            warnings=[warning],
        ),
    )

    section = _research_evidence_report_section(report)

    assert section.source.kind == "research"
    assert section.summary["warnings"] == warning
    assert warning in section.warnings


def test_research_evidence_report_section_carries_phase21_rows():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary",
        points=[],
        evidence=[],
        extracted_claims=[
            ResearchExtractedClaim(
                symbol="7203.T",
                category="business_risk",
                claim="事業リスクに関する確認材料があります。",
                summary="為替影響の記述を確認材料として整理します。",
                supporting_evidence=[],
                confidence=Decimal("0.64"),
            )
        ],
        grounded_answer=ResearchGroundedAnswer(
            symbol="7203.T",
            answer="根拠付き説明です。売買推奨ではありません。",
            referenced_evidence=[],
            claim_count=1,
            evidence_count=0,
            warnings=[],
        ),
        retrieval_quality=ResearchRetrievalQuality(
            backend="keyword",
            query="business risk",
            expanded_terms=["business", "risk"],
            candidate_count=2,
            evidence_count=1,
            warnings=[],
        ),
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    section = _research_evidence_report_section(report)

    assert section.summary["grounded_answer"] == "根拠付き説明です。売買推奨ではありません。"
    assert section.summary["retrieval_backend"] == "keyword"
    row_types = [row["row_type"] for row in section.rows]
    assert "grounded_answer" in row_types
    assert "retrieval_quality" in row_types
    assert "extracted_claim" in row_types


def test_research_score_report_section_carries_components_evidence_and_note():
    evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-1",
        chunk_id="chunk-1",
        title="7203 Integrated Report",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Growth",
        excerpt=(
            "Growth strategy, profitability margin, dividend policy, cash, "
            "and regulation risk are discussed."
        ),
        relevance_score=Decimal("0.84"),
        reliability=Decimal("0.90"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="成長戦略を確認材料として整理します。",
                evidence=[evidence],
            )
        ],
        evidence=[evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    section = _research_score_report_section(report)

    assert section.title == "Research Score"
    assert section.summary["symbol"] == "7203.T"
    assert section.summary["evidence_count"] == "1"
    row_types = [row["row_type"] for row in section.rows]
    assert "research_score_component" in row_types
    assert "research_score_evidence" in row_types
    assert any("売買推奨ではありません" in note for note in section.notes)


def test_research_evidence_cards_html_escapes_excerpt_and_uses_vertical_cards():
    markup = _research_evidence_cards_html(
        [
            {
                "資料名": "7203 profile",
                "公開日": "2026-05-23",
                "セクション": "Business Summary",
                "抜粋": "<script>not advice</script>",
                "関連度": "0.50",
                "信頼度": "0.70",
            }
        ]
    )

    assert "research-evidence-list" in markup
    assert "Business Summary" in markup
    assert "<script>" not in markup
    assert "&lt;script&gt;not advice&lt;/script&gt;" in markup


def test_research_evidence_card_rows_merge_news_and_local_evidence_for_cards():
    evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-growth",
        chunk_id="chunk-growth",
        title="7203 growth profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        excerpt="Toyota expands hybrid and software investment.",
        relevance_score=Decimal("0.82"),
        reliability=Decimal("0.74"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="成長材料を確認します。",
                evidence=[evidence],
            )
        ],
        evidence=[evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    news_report = StockNewsReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                title="Tariff risk rises",
                url="https://example.com/risk",
                source="Example News",
                published_at=date(2026, 5, 25),
                summary="Tariff headline adds export uncertainty.",
                investment_viewpoint="risk",
                sentiment_for_investment="negative",
                freshness_status="latest",
            )
        ],
    )

    rows = _research_evidence_card_rows(report, news_report=news_report, limit=None)
    markup = _research_evidence_cards_html(rows)

    assert rows[0]["sentiment"] == "リスク材料"
    assert rows[0]["category"] == "リスク材料"
    assert rows[0]["url"] == "https://example.com/risk"
    assert rows[1]["sentiment"] == "ポジティブ材料"
    assert rows[1]["category"] == "事業成長"
    assert "記事を開く" in markup
    assert "投資判断への影響" in markup


def test_ranking_result_aggrid_options_enable_single_row_click_selection():
    options = ranking_result_aggrid_options(
        [
            {
                "順位": "1",
                "銘柄": "8174.T",
                "銘柄名": "日本瓦斯",
                "総合スコア": "80.1",
                "補足": "深掘り候補です",
            }
        ]
    )

    assert options["rowSelection"] == "single"
    assert options["suppressRowClickSelection"] is False
    assert options["suppressCellFocus"] is True
    column_defs = {column["field"]: column for column in options["columnDefs"]}
    assert column_defs["順位"]["pinned"] == "left"
    assert column_defs["銘柄"]["pinned"] == "left"
    assert column_defs["お気に入り"]["pinned"] == "left"
    assert column_defs["お気に入り"]["sortable"] is False
    assert column_defs["総合スコア"]["sortingOrder"] == ["desc", "asc", None]
    assert column_defs["配当利回り"]["sortingOrder"] == ["desc", "asc", None]
    assert column_defs["PER"]["sortingOrder"] == ["asc", "desc", None]
    assert column_defs["PBR"]["sortingOrder"] == ["asc", "desc", None]
    assert column_defs["ROE"]["sortingOrder"] == ["desc", "asc", None]
    assert column_defs["PER"]["unSortIcon"] is True
    assert "comparator" in column_defs["PER"]
    assert "SMAIメモ" in column_defs
    assert column_defs["SMAIメモ"]["tooltipField"] == "確認詳細"
    assert column_defs["確認詳細"]["hide"] is True
    assert "並べ替え理由" in column_defs
    assert column_defs["並べ替え理由"]["hide"] is True
    assert column_defs["並べ替え理由"]["tooltipField"] == "並べ替え理由"


def test_ranking_result_aggrid_options_keep_detail_table_cells_compact():
    options = ranking_result_aggrid_options(
        pd.DataFrame(
            [
                {
                    "順位": "1",
                    "銘柄": "7203.T",
                    "銘柄名": "トヨタ自動車",
                    "総合スコア": "82.16",
                    "PER": "8.2",
                    "PBR": "1.0",
                    "ROE": "11.7%",
                    "SMAIメモ": "上昇気配あり。下降警戒は中程度。",
                    "確認詳細": "詳細な確認メモです。",
                }
            ]
        )
    )

    column_defs = {column["field"]: column for column in options["columnDefs"]}
    assert column_defs["順位"]["width"] == 58
    assert column_defs["銘柄名"]["wrapText"] is False
    assert column_defs["銘柄名"]["autoHeight"] is False
    assert column_defs["総合スコア"]["width"] == 92
    assert column_defs["PER"]["cellStyle"]["whiteSpace"] == "nowrap"
    assert column_defs["PER"]["cellStyle"]["textAlign"] == "right"
    assert column_defs["SMAIメモ"]["width"] == 280
    assert "flex" not in column_defs["SMAIメモ"]
    assert column_defs["SMAIメモ"]["wrapText"] is False
    assert column_defs["SMAIメモ"]["autoHeight"] is False
    assert column_defs["SMAIメモ"]["cellStyle"]["textOverflow"] == "ellipsis"


def test_ranking_result_aggrid_options_assigns_metric_sort_directions():
    frame = pd.DataFrame(
        [
            {
                "総合スコア": "80.1",
                "Screening": "75",
                "上昇気配": "68",
                "下降警戒": "32",
                "配当利回り": "3.2%",
                "PER": "12.4",
                "PBR": "1.1",
                "ROE": "14.0%",
                "時価総額": "1,000,000",
                "出来高": "120,000",
                "ボラティリティ": "18.5%",
                "Risk": "42",
                "データ品質": "88",
            }
        ]
    )

    options = ranking_result_aggrid_options(frame)
    column_defs = {column["field"]: column for column in options["columnDefs"]}
    expected_sorting_orders = {
        "総合スコア": ["desc", "asc", None],
        "Screening": ["desc", "asc", None],
        "上昇気配": ["desc", "asc", None],
        "下降警戒": ["asc", "desc", None],
        "配当利回り": ["desc", "asc", None],
        "PER": ["asc", "desc", None],
        "PBR": ["asc", "desc", None],
        "ROE": ["desc", "asc", None],
        "時価総額": ["desc", "asc", None],
        "出来高": ["desc", "asc", None],
        "ボラティリティ": ["asc", "desc", None],
        "Risk": ["asc", "desc", None],
        "データ品質": ["desc", "asc", None],
    }

    for column, sorting_order in expected_sorting_orders.items():
        assert column_defs[column]["sortingOrder"] == sorting_order
        assert column_defs[column]["unSortIcon"] is True
        assert "comparator" in column_defs[column]
    assert column_defs["Screening"]["headerName"] == "基礎評価"
    assert column_defs["Risk"]["headerName"] == "リスク"
    assert column_defs["データ品質"]["headerName"] == "データ信頼度"


def test_ranking_table_sort_guidance_explains_low_sort_and_missing_values():
    assert "通常表示では投資判断に必要な列だけ" in RANKING_TABLE_SORT_GUIDANCE
    assert "詳細列を表示する" in RANKING_TABLE_SORT_GUIDANCE
    assert "ニュース材料はAI要約による参考情報" in RANKING_TABLE_SORT_GUIDANCE
    assert "ランキング順位には反映していません" in RANKING_TABLE_SORT_GUIDANCE
    assert "N/Aは未取得または未評価" in RANKING_TABLE_SORT_GUIDANCE


def test_ranking_result_grid_custom_css_keeps_dark_table_readable():
    assert RANKING_RESULT_GRID_CUSTOM_CSS[".ag-root-wrapper"]["background-color"] == (
        f"{THEME_COLORS['bg_surface']} !important"
    )
    assert RANKING_RESULT_GRID_CUSTOM_CSS[".ag-header-cell-text"]["color"] == (
        f"{THEME_COLORS['text_heading']} !important"
    )
    assert RANKING_RESULT_GRID_CUSTOM_CSS[".ag-row-even"]["background-color"] == (
        f"{THEME_COLORS['table_row_bg']} !important"
    )
    assert RANKING_RESULT_GRID_CUSTOM_CSS[".ag-row-odd"]["background-color"] == (
        f"{THEME_COLORS['bg_card']} !important"
    )


def test_ranking_detail_symbol_from_aggrid_response_handles_dataframe_and_dict():
    selected_rows = pd.DataFrame([{"銘柄": "8174.T", "銘柄名": "日本瓦斯"}])
    response = SimpleNamespace(selected_rows=selected_rows)

    assert ranking_detail_symbol_from_aggrid_response(response) == "8174.T"
    assert ranking_detail_symbol_from_aggrid_response({"selected_rows": [{"銘柄": "5015.T"}]}) == (
        "5015.T"
    )
    assert (
        ranking_detail_symbol_from_aggrid_response({"eventData": {"data": {"銘柄": "9502.T"}}})
        == "9502.T"
    )
    assert ranking_detail_symbol_from_aggrid_response(SimpleNamespace(selected_rows=None)) is None
    assert ranking_detail_symbol_from_aggrid_response({"selected_rows": []}) is None


def test_ranking_favorite_symbol_from_aggrid_response_only_accepts_favorite_cell():
    favorite_click = {
        "eventData": {
            "colId": "お気に入り",
            "data": {"銘柄": " 7203.t "},
        }
    }

    assert ranking_favorite_symbol_from_aggrid_response(favorite_click) == "7203.T"
    assert (
        ranking_favorite_symbol_from_aggrid_response(
            {"eventData": {"colId": "銘柄", "data": {"銘柄": "7203.T"}}}
        )
        is None
    )


def test_ranking_detail_event_token_tracks_row_clicks():
    response = {
        "eventData": {
            "streamlitRerunEventTriggerName": "rowClicked",
            "rowIndex": 3,
            "event": {"timeStamp": 12345},
        }
    }

    assert ranking_detail_event_token_from_aggrid_response(response, "8174.T") == (
        "rowClicked|8174.T|3|12345"
    )
    assert ranking_detail_event_token_from_aggrid_response({}, "8174.T") == ("selection|8174.T")
    assert ranking_detail_event_token_from_aggrid_response(response, None) is None


def test_ranking_detail_symbol_to_open_only_changes_on_new_click_event():
    assert ranking_detail_symbol_to_open("8174.T", "event-1", None) == "8174.T"
    assert ranking_detail_symbol_to_open("8174.T", "event-1", "event-1") is None
    assert ranking_detail_symbol_to_open("8174.T", "event-2", "event-1") == "8174.T"
    assert ranking_detail_symbol_to_open(None, "event-2", "event-1") is None


def test_ranking_result_grid_key_and_height_are_stable():
    assert _ranking_result_grid_key("ranking") == "market_data_ranking_result_grid"
    assert _ranking_result_grid_key("ranking|other-weight") == "market_data_ranking_result_grid"
    assert _ranking_result_grid_height([{"銘柄": "8174.T"}]) == 150
    assert _ranking_result_grid_height([{"銘柄": str(index)} for index in range(20)]) == 520


def test_ranking_result_table_base_key_changes_with_result_source():
    assert _ranking_result_table_base_key("source-a", "balanced") == (
        _ranking_result_table_base_key("source-a", "balanced")
    )
    assert _ranking_result_table_base_key("source-a", "balanced") != (
        _ranking_result_table_base_key("source-b", "balanced")
    )


def test_ranking_decision_report_state_key_changes_with_sort_condition():
    assert _ranking_decision_report_state_key("source-a", "balanced") == (
        _ranking_decision_report_state_key("source-a", "balanced")
    )
    assert _ranking_decision_report_state_key("source-a", "balanced") != (
        _ranking_decision_report_state_key("source-a", "growth")
    )


def test_select_ranking_symbol_for_cockpit_with_period_carries_ranking_window(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_preview": object(),
        "market_data_status_message": "ok",
        "market_data_ranking_deep_dive_symbol": "old",
    }
    monkeypatch.setattr("ui.app.st.session_state", session_state)

    _select_ranking_symbol_for_cockpit_with_period(
        "7203.T",
        "yahoo",
        date(2026, 5, 17),
        date(2026, 5, 24),
    )

    assert session_state["sidemenu_page"] == "cockpit"
    assert session_state["market_data_provider_live_first"] == "yahoo"
    assert session_state["market_data_symbol_candidate"] == "7203.T - Toyota Motor"
    assert session_state["market_data_ranking_handoff_symbol"] == "7203.T"
    assert session_state["market_data_period_preset"] == MARKET_DATA_PERIOD_CUSTOM
    assert session_state["market_data_start"] == date(2026, 5, 17)
    assert session_state["market_data_end"] == date(2026, 5, 24)
    assert "market_data_preview" not in session_state
    assert "market_data_status_message" not in session_state
    assert "market_data_ranking_deep_dive_symbol" not in session_state


def test_navigation_query_params_open_news_symbol_in_cockpit(monkeypatch):
    monkeypatch.delenv(CONFIG_FILE_ENV, raising=False)
    session_state: dict[str, object] = {
        "market_data_preview": object(),
        "market_data_status_message": "old",
    }
    query_params = {
        "smai_page": ["cockpit"],
        "smai_symbol": ["7203.t"],
    }
    monkeypatch.setattr(app_module.st, "session_state", session_state)
    monkeypatch.setattr(app_module.st, "query_params", query_params, raising=False)

    _apply_navigation_query_params()

    assert session_state["sidemenu_page"] == "cockpit"
    assert session_state["market_data_mode"] == "cockpit"
    assert session_state["market_data_provider_live_first"] == "yahoo"
    assert session_state["market_data_symbol_candidate"] == "7203.T - Toyota Motor"
    assert "market_data_preview" not in session_state
    assert "market_data_status_message" not in session_state
    assert query_params == {}


def test_cockpit_preserved_candidate_symbols_drops_current_choice_during_search():
    assert app_module.cockpit_preserved_candidate_symbols(
        "",
        "7203.T",
        "6367.T",
    ) == ["7203.T", "6367.T"]
    assert (
        app_module.cockpit_preserved_candidate_symbols(
            "1938",
            "7203.T",
            "6367.T",
        )
        == []
    )


def test_symbol_universe_rows_adds_static_selection_metadata():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
        ]
    )

    assert rows[0]["market"] == "jp"
    assert rows[0]["currency"] == "JPY"
    assert rows[1]["asset_type"] == "etf"
    assert rows[1]["theme"] == "index"
    assert "installment" in rows[1]["tags"]


def test_symbol_universe_csv_rows_provide_extensible_selection_metadata():
    rows = symbol_universe_rows()
    row_by_symbol = {row["symbol"]: row for row in rows}

    assert len(symbol_universe_csv_rows()) >= 80
    assert row_by_symbol["7203.T"]["market"] == "jp"
    assert row_by_symbol["7203.T"]["currency"] == "JPY"
    assert row_by_symbol["AAPL"]["theme"] == "technology"
    assert "growth" in row_by_symbol["AAPL"]["tags"]
    assert row_by_symbol["SPY"]["asset_type"] == "etf"
    assert row_by_symbol["SPY"]["index_family"] == "sp500"
    assert row_by_symbol["AAPL"]["per"]
    assert row_by_symbol["AAPL"]["pbr"]
    assert row_by_symbol["AAPL"]["roe_pct"]
    assert row_by_symbol["AAPL"]["consensus_rating"]
    assert row_by_symbol["AAPL"]["risk_band"]


def test_filter_symbol_universe_rows_uses_fetch_before_conditions():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            purpose="installment",
            market="etf",
            asset_type="etf",
            currency="USD",
            theme="index",
        )
    ] == ["SPY"]
    assert [
        row["symbol"] for row in filter_symbol_universe_rows(rows, purpose="growth", limit=2)
    ] == ["AAPL", "NVDA"]
    assert [row["symbol"] for row in filter_symbol_universe_rows(rows, query="toyota")] == [
        "7203.T"
    ]


def test_filter_symbol_universe_rows_applies_ranking_universe_policy():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_type": "stock",
                "broker": "sbi_securities",
                "tradability": "unknown",
                "is_sbi_supported": "true",
                "is_active": "true",
                "is_leveraged": "false",
                "is_inverse": "false",
            },
            {"symbol": "BADFX", "name": "FX Product", "asset_type": "fx"},
            {
                "symbol": "LEVER",
                "name": "Leveraged ETF",
                "asset_type": "etf",
                "is_leveraged": "true",
            },
            {
                "symbol": "UNTRAD",
                "name": "Unavailable Stock",
                "asset_type": "stock",
                "tradability": "not_tradable",
            },
            {
                "symbol": "NOSBI",
                "name": "Unsupported Stock",
                "asset_type": "stock",
                "is_sbi_supported": "false",
            },
        ]
    )

    assert [row["symbol"] for row in filter_symbol_universe_rows(rows)] == ["AAPL"]


def test_filter_symbol_universe_rows_finds_curated_dividend_candidates():
    rows = symbol_universe_rows(
        [
            {"symbol": "9432.T", "name": "Nippon Telegraph and Telephone"},
            {"symbol": "2914.T", "name": "Japan Tobacco"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            purpose="dividend",
            market="jp",
            dividend_category="high_dividend",
        )
    ] == ["9432.T", "2914.T"]


def test_filter_symbol_universe_rows_finds_us_dividend_candidates():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "PFE", "name": "Pfizer"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            purpose="dividend",
            market="us",
            asset_type="stock",
        )
    ] == ["AAPL", "PFE"]


def test_filter_symbol_universe_rows_filters_by_dividend_yield_database_value():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "PFE", "name": "Pfizer"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            market="us",
            asset_type="stock",
            dividend_yield_enabled=True,
            min_dividend_yield_pct="3.0",
        )
    ] == ["PFE"]


def test_filter_symbol_universe_rows_uses_explicit_dividend_range_over_category():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "RANGE",
                "name": "Range Match",
                "dividend_category": "dividend",
                "dividend_yield_pct": "4.0",
            },
            {
                "symbol": "CATEGORY",
                "name": "Category Only",
                "dividend_category": "high_dividend",
                "dividend_yield_pct": "2.5",
            },
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            dividend_category="high_dividend",
            dividend_yield_enabled=True,
            min_dividend_yield_pct="3.0",
            dividend_yield_max_pct="5.0",
        )
    ] == ["RANGE"]


def test_filter_symbol_universe_rows_ignores_dividend_range_when_disabled():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "PFE", "name": "Pfizer"},
            {"symbol": "NVDA", "name": "NVIDIA"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            market="us",
            asset_type="stock",
            dividend_yield_enabled=False,
            min_dividend_yield_pct="3.0",
        )
    ] == ["AAPL", "PFE", "NVDA"]


def test_filter_symbol_universe_rows_filters_by_metric_ranges():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "7203.T",
                "name": "Toyota Motor",
                "per": "12",
                "pbr": "1.1",
                "dividend_yield_pct": "2.5",
                "roe_pct": "12",
                "consensus_rating": "3.2",
            },
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "per": "30",
                "pbr": "2.0",
                "dividend_yield_pct": "1.0",
                "roe_pct": "15",
                "consensus_rating": "3.5",
            },
            {
                "symbol": "PFE",
                "name": "Pfizer",
                "per": "15",
                "pbr": "1.5",
                "dividend_yield_pct": "4.0",
                "roe_pct": "10",
                "consensus_rating": "3.0",
            },
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            per_enabled=True,
            per_min="2.0",
            per_max="20.0",
            pbr_enabled=True,
            pbr_min="0.5",
            pbr_max="3.0",
            dividend_yield_enabled=True,
            min_dividend_yield_pct="0.0",
            dividend_yield_max_pct="10.0",
            roe_enabled=True,
            roe_min_pct="8.0",
            roe_max_pct="30.0",
            consensus_enabled=True,
            consensus_min="2.5",
            consensus_max="5.0",
            active_detail_filters={"per", "pbr", "dividend_yield", "roe", "consensus"},
        )
    ] == ["7203.T", "PFE"]


def test_filter_symbol_universe_rows_filters_etf_database_values():
    rows = symbol_universe_rows(
        [
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
            {"symbol": "QQQ", "name": "Invesco QQQ Trust"},
            {"symbol": "VOO", "name": "Vanguard S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            market="etf",
            asset_type="etf",
            index_family="sp500",
            max_expense_ratio_pct="0.05",
        )
    ] == ["VOO"]


def test_filter_symbol_universe_rows_filters_by_official_sector_and_jpx_market_cap():
    rows = symbol_universe_rows(
        [
            {"symbol": "1301.T", "name": "極洋"},
            {"symbol": "1332.T", "name": "ニッスイ"},
            {"symbol": "1414.T", "name": "ショーボンドホールディングス"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            official_sector="industrial",
        )
    ] == ["1414.T"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            market_cap_tier="small",
        )
    ] == ["1301.T"]
    assert "small" in RANKING_MARKET_CAP_LABELS
    assert "industrial" in RANKING_OFFICIAL_SECTOR_LABELS


def test_filter_symbol_universe_rows_uses_smai_theme_tags_for_theme_filter():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "8035.T",
                "name": "Tokyo Electron",
                "theme": "technology",
                "sector": "technology",
                "smai_theme_tags": "semiconductor,technology",
            },
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "theme": "technology",
                "sector": "technology",
                "smai_theme_tags": "technology",
            },
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            theme="semiconductor",
        )
    ] == ["8035.T"]


def test_symbol_universe_filter_value_counts_uses_ui_filter_sources():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "8035.T",
                "name": "Tokyo Electron",
                "theme": "technology",
                "sector": "technology",
                "smai_theme_tags": "semiconductor,technology",
                "tse_33_industry": "電気機器",
            },
            {
                "symbol": "8306.T",
                "name": "Mitsubishi UFJ Financial Group",
                "theme": "financial",
                "sector": "financial",
                "smai_theme_tags": "bank,financial,high_dividend",
                "tse_33_industry": "銀行業",
            },
        ]
    )

    theme_counts = symbol_universe_filter_value_counts(rows, "investment_theme")
    sector_counts = symbol_universe_filter_value_counts(rows, "official_sector")

    assert theme_counts["semiconductor"] == 1
    assert theme_counts["bank"] == 1
    assert theme_counts["high_dividend"] == 1
    assert sector_counts["technology"] == 1
    assert sector_counts["financial"] == 1
    assert sector_counts["電気機器"] == 1
    assert sector_counts["銀行業"] == 1


def test_filter_symbol_universe_rows_filters_by_raw_official_industry_values():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "6758.T",
                "name": "Sony Group",
                "theme": "technology",
                "sector": "technology",
                "tse_33_industry": "電気機器",
                "topix_17": "電機・精密",
            },
            {
                "symbol": "8306.T",
                "name": "Mitsubishi UFJ Financial Group",
                "theme": "bank",
                "sector": "financial",
                "tse_33_industry": "銀行業",
                "topix_17": "銀行",
            },
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            official_sector="電気機器",
        )
    ] == ["6758.T"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            official_sector="銀行",
        )
    ] == ["8306.T"]


def test_filter_symbol_universe_rows_keeps_sector_out_of_investment_theme_filter():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "1414.T",
                "name": "ショーボンドホールディングス",
                "theme": "balanced",
                "sector": "industrial",
                "smai_theme_tags": "balanced",
            },
            {
                "symbol": "8035.T",
                "name": "Tokyo Electron",
                "theme": "technology",
                "sector": "technology",
                "smai_theme_tags": "semiconductor,technology",
            },
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            theme="industrial",
        )
    ] == []


def test_ranking_filter_labels_show_quantitative_thresholds():
    assert RANKING_MARKET_CAP_LABELS["mega"] == "超大型（JP 10兆円以上 / US $200B以上）"
    assert RANKING_MARKET_CAP_LABELS["small"] == "小型（JP 100億〜1,000億円 / US $300M〜$2B）"
    assert RANKING_DIVIDEND_LABELS["high_dividend"] == "配当利回り 3%以上"
    assert RANKING_DIVIDEND_LABELS["dividend"] == "配当利回り 0%超〜3%未満"
    assert "bond" in RANKING_THEME_LABELS
    assert "industrial" in RANKING_OFFICIAL_SECTOR_LABELS
    assert "電気機器" in RANKING_OFFICIAL_SECTOR_LABELS
    assert "Information Technology" in RANKING_OFFICIAL_SECTOR_LABELS
    assert "semiconductor" in RANKING_INVESTMENT_THEME_LABELS
    assert "balanced" in RANKING_INVESTMENT_THEME_LABELS
    assert "bank" in RANKING_INVESTMENT_THEME_LABELS
    assert "sp500" in RANKING_INVESTMENT_THEME_LABELS
    assert "insurance" in RANKING_INVESTMENT_THEME_LABELS
    assert "dividend" not in RANKING_THEME_LABELS
    assert "$200B/$10B/$2B/$300M" in RANKING_FILTER_HELP_TEXTS["market_cap"]
    assert "0%超〜3%未満" in RANKING_FILTER_HELP_TEXTS["dividend_category"]


def test_product_filter_options_include_unspecified_default_for_cockpit():
    assert list(RANKING_MVP_PRODUCT_TYPE_LABELS) == ["stock", "etf", "all"]
    assert RANKING_MVP_PRODUCT_TYPE_LABELS["all"] == "指定なし"
    assert ranking_product_type_label("all") == "指定なし"
    assert MARKET_DATA_COCKPIT_FILTER_DEFAULTS["market_data_cockpit_product_type"] == "all"


def test_dividend_filter_labels_adapt_to_product_type():
    assert _dividend_category_filter_label("stock") == "配当カテゴリ"
    assert _dividend_yield_filter_label("stock") == "配当利回り(%)"
    assert _dividend_category_filter_label("etf") == "分配金カテゴリ"
    assert _dividend_yield_filter_label("etf") == "分配金利回り(%)"
    assert _dividend_category_filter_label("all") == "配当/分配金カテゴリ"
    assert _dividend_yield_filter_label("all") == "配当/分配金利回り(%)"
    assert _dividend_category_option_label("high_dividend", "etf") == "分配金利回り 3%以上"
    assert _dividend_category_option_label("high_dividend", "all") == "配当/分配金利回り 3%以上"
    assert "年間分配金" in _dividend_filter_help_text(
        RANKING_FILTER_HELP_TEXTS["dividend_yield"],
        "etf",
    )


def test_normalize_dividend_filter_values_keeps_conditions_mutually_exclusive():
    assert normalize_dividend_filter_values(
        dividend_category="high_dividend",
        dividend_yield_enabled=True,
        min_dividend_yield_pct="3.2",
        dividend_yield_max_pct="8.0",
    ) == ("all", "3.2", True, "8.0")
    assert normalize_dividend_filter_values(
        dividend_category="high_dividend",
        dividend_yield_enabled=False,
        min_dividend_yield_pct="3.2",
        dividend_yield_max_pct="8.0",
    ) == ("high_dividend", "0.0", False, "10.0")


def test_ranking_etf_filter_labels_cover_imported_index_families():
    assert {
        "bond",
        "commodity",
        "dividend",
        "dow_jones",
        "emerging",
        "msci_world",
        "reit",
        "sector",
        "topix",
        "nikkei225",
    } <= set(RANKING_INDEX_FAMILY_LABELS)


def test_filter_symbol_universe_rows_ignores_hidden_etf_filters_for_stock():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="all",
            product_type="stock",
            index_family="sp500",
            max_expense_ratio_pct="0.05",
            complexity="beginner",
        )
    ] == ["AAPL"]


def test_filter_symbol_universe_rows_ignores_hidden_stock_filters_for_etf():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="all",
            product_type="etf",
            theme="all",
            market_cap_tier="large",
            per_enabled=True,
            per_min="2.0",
            per_max="3.0",
            pbr_enabled=True,
            pbr_min="0.5",
            pbr_max="0.6",
            roe_enabled=True,
            roe_min_pct="20.0",
            roe_max_pct="30.0",
        )
    ] == ["SPY"]


def test_filter_symbol_universe_rows_product_all_keeps_stocks_and_etfs():
    rows = symbol_universe_rows(
        [
            {"symbol": "AAPL", "name": "Apple Inc.", "asset_type": "stock"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "asset_type": "etf"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="all",
            product_type="all",
        )
    ] == ["AAPL", "SPY"]


def test_filter_symbol_universe_rows_preserves_etf_region():
    rows = symbol_universe_rows(
        [
            {"symbol": "1306.T", "name": "NEXT FUNDS TOPIX ETF"},
            {"symbol": "VOO", "name": "Vanguard S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="etf",
        )
    ] == ["1306.T"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="etf",
        )
    ] == ["VOO"]


def test_filter_symbol_universe_rows_filters_by_nisa_eligibility():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "6861.T", "name": "Keyence"},
            {"symbol": "TSLA", "name": "Tesla"},
            {"symbol": "VOO", "name": "Vanguard S&P 500 ETF"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            nisa_eligibility="growth",
        )
    ] == ["7203.T", "6861.T", "TSLA", "VOO"]


def test_filter_symbol_universe_rows_filters_nisa_non_eligible_etfs():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "GROWTH",
                "name": "Growth ETF",
                "market": "us",
                "asset_type": "etf",
                "theme": "index",
                "nisa_category": "growth",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
            },
            {
                "symbol": "OUT",
                "name": "Non NISA ETF",
                "market": "us",
                "asset_type": "etf",
                "theme": "index",
                "nisa_category": "none",
                "nisa_growth_eligible": "false",
                "nisa_tsumitate_eligible": "false",
            },
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="etf",
            nisa_eligibility="none",
        )
    ] == ["OUT"]


def test_ranking_nisa_labels_match_stock_etf_scope():
    assert RANKING_NISA_ELIGIBILITY_LABELS == {
        "all": "指定なし（NISAで絞らない）",
        "eligible": "NISA対象のみ（成長投資枠）",
        "none": "NISA対象外のみ",
    }
    assert "growth" not in RANKING_NISA_ELIGIBILITY_LABELS
    assert "tsumitate" not in RANKING_NISA_ELIGIBILITY_LABELS
    assert "both" not in RANKING_NISA_ELIGIBILITY_LABELS


def test_selectbox_state_resets_legacy_nisa_choice_from_saved_filters(monkeypatch):
    for legacy_value in ("growth", "tsumitate", "both"):
        session_state = {
            "market_data_ranking_filters": {
                "market_data_ranking_nisa": legacy_value,
            }
        }
        monkeypatch.setattr("ui.app.st.session_state", session_state)

        _ensure_selectbox_state_value(
            "market_data_ranking_nisa",
            list(RANKING_NISA_ELIGIBILITY_LABELS),
        )

        assert session_state["market_data_ranking_nisa"] == "all"


def test_dividend_filter_state_prefers_explicit_range_when_both_saved(monkeypatch):
    session_state = {
        "market_data_ranking_filters": {
            "market_data_ranking_dividend": "high_dividend",
            "market_data_ranking_dividend_enabled": "true",
        }
    }
    monkeypatch.setattr("ui.app.st.session_state", session_state)

    _normalize_dividend_filter_state()

    assert session_state["market_data_ranking_dividend"] == "all"
    assert "market_data_ranking_dividend_enabled" not in session_state


def test_filter_symbol_universe_rows_excludes_commodity_etfs_from_mvp_ranking():
    rows = symbol_universe_rows([{"symbol": "1540.T", "name": "Japan Physical Gold ETF"}])

    assert filter_symbol_universe_rows(rows, product_type="etf") == []


def test_filter_symbol_universe_rows_excludes_mutual_funds_from_mvp_ranking():
    rows = symbol_universe_rows()

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            product_type="mutual_fund",
        )
    ] == []
    assert all(row["asset_type"] != "mutual_fund" for row in filter_symbol_universe_rows(rows))


def test_filter_symbol_universe_rows_supports_internal_risk_metadata_filter():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor", "risk_band": "LOW"},
            {"symbol": "AAPL", "name": "Apple Inc.", "risk_band": "MEDIUM"},
            {"symbol": "TM", "name": "Toyota Motor ADR"},
            {"symbol": "NVDA", "name": "NVIDIA", "risk_band": "HIGH"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "risk_band": "MEDIUM"},
        ]
    )

    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="japan",
            product_type="stock",
            risk_band="LOW",
        )
    ] == ["7203.T"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="stock",
            risk_band=RANKING_BETA_RISK_STANDARD_OR_LOWER,
        )
    ] == ["AAPL"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="stock",
        )
    ] == ["AAPL", "NVDA"]
    assert [
        row["symbol"]
        for row in filter_symbol_universe_rows(
            rows,
            region="us",
            product_type="etf",
        )
    ] == ["SPY"]
    assert (
        filter_symbol_universe_rows(
            rows,
            region="other_global",
            product_type="stock",
        )
        == []
    )


def test_ranking_detail_filters_change_by_region_and_product():
    japan_stock = ranking_detail_filters_for_category("japan", "stock")
    us_stock = ranking_detail_filters_for_category("us", "stock")
    etf = ranking_detail_filters_for_category("japan", "etf")
    all_product = ranking_detail_filters_for_category("japan", "all")
    mutual_fund = ranking_detail_filters_for_category("japan", "mutual_fund")

    assert "pbr" in japan_stock
    assert "risk_band" in japan_stock
    assert "benchmark_index" not in japan_stock
    assert "expense_ratio" not in japan_stock
    assert "risk_band" in us_stock
    assert "nisa_eligibility" in us_stock
    assert "benchmark_index" in etf
    assert "expense_ratio" in etf
    assert "per" not in etf
    assert "pbr" not in etf
    assert {"official_sector", "investment_theme", "market_cap", "risk_band"} <= set(all_product)
    assert {"benchmark_index", "expense_ratio", "complexity"} <= set(all_product)
    assert {"per", "pbr", "roe"}.isdisjoint(all_product)
    assert mutual_fund == ["expense_ratio", "nisa_eligibility", "complexity"]
    assert ranking_weight_preset_for_purpose("stability") == "stability_profile"
    assert "moving_average_signal" in RANKING_INVESTMENT_STYLE_METRICS["trend"]


def test_advanced_ranking_purposes_have_profiles_and_help_text():
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_MULTI_FACTOR) == (
        "multi_factor_profile"
    )
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_QUALITY_GROWTH) == (
        RANKING_PRESET_QUALITY_GROWTH
    )
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_ETF_CORE_COST) == (
        RANKING_PRESET_ETF_CORE_COST
    )
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_SUSTAINABLE_INCOME) == (
        RANKING_PRESET_SUSTAINABLE_INCOME
    )
    assert ranking_weight_preset_for_purpose(RANKING_PURPOSE_UPSIDE_SIGNAL) == (
        RANKING_PRESET_UPSIDE_SIGNAL
    )
    assert "ROE" in ranking_purpose_help(RANKING_PURPOSE_QUALITY_GROWTH)
    assert "PERが低い順" in ranking_purpose_help(RANKING_PURPOSE_SORT_PER)
    assert "安全を保証" in ranking_purpose_help(RANKING_PURPOSE_SORT_RISK)
    assert "減配リスク" in ranking_purpose_help(RANKING_PURPOSE_SUSTAINABLE_INCOME)
    assert "経費率" in ranking_purpose_help(RANKING_PURPOSE_ETF_CORE_COST)
    assert "上昇気配" in ranking_purpose_help(RANKING_PURPOSE_UPSIDE_SIGNAL)
    assert "roe" in RANKING_INVESTMENT_STYLE_METRICS[RANKING_PURPOSE_QUALITY_GROWTH]
    assert "expense_ratio" in RANKING_INVESTMENT_STYLE_METRICS[RANKING_PURPOSE_ETF_CORE_COST]
    assert ranking_purpose_primary_columns(RANKING_PURPOSE_UPSIDE_SIGNAL)[:3] == (
        "上昇気配",
        "下降警戒",
        "予測変化率",
    )
    assert ranking_purpose_primary_columns(RANKING_PURPOSE_ETF_CORE_COST)[:2] == (
        "経費率",
        "連動指数",
    )
    assert "予測・上昇気配 25%" in ranking_purpose_weight_summary(RANKING_PURPOSE_UPSIDE_SIGNAL)
    assert "下振れ警戒 10%" in ranking_purpose_weight_summary(RANKING_PURPOSE_UPSIDE_SIGNAL)
    assert ranking_purpose_weight_summary(RANKING_PURPOSE_SORT_PER) == (
        "PER低い順 100%",
        "N/A 末尾",
        "同値は総合スコア補助",
    )
    assert "上向きシグナル" in ranking_purpose_focus_summary(RANKING_PURPOSE_UPSIDE_SIGNAL)
    assert "低い順" in ranking_purpose_focus_summary(RANKING_PURPOSE_SORT_PER)


def test_ranking_policy_options_restore_composite_profiles_without_metric_sorts():
    assert ranking_policy_options() == [
        RANKING_PURPOSE_MULTI_FACTOR,
        RANKING_PURPOSE_UPSIDE_SIGNAL,
        RANKING_PURPOSE_REVERSAL_EXPECTATION,
        RANKING_PURPOSE_DOWNSIDE_SIGNAL,
        RANKING_PURPOSE_MOMENTUM,
        RANKING_PURPOSE_QUALITY_GROWTH,
        RANKING_PURPOSE_QUALITY_VALUE,
        RANKING_PURPOSE_SUSTAINABLE_INCOME,
        RANKING_PURPOSE_MIN_VOLATILITY,
        RANKING_PURPOSE_RISK_ADJUSTED,
        RANKING_PURPOSE_SMALL_GROWTH,
        RANKING_PURPOSE_NISA_LONG_TERM,
        RANKING_PURPOSE_DATA_CONFIDENCE,
        RANKING_PURPOSE_ETF_CORE_COST,
        RANKING_PURPOSE_ETF_INCOME,
    ]
    assert [ranking_policy_label(option) for option in ranking_policy_options()] == [
        "AI総合",
        "上昇気配重視",
        "上向き兆候",
        "下降警戒",
        "モメンタム・トレンド",
        "成長クオリティ",
        "割安クオリティ",
        "高配当の持続性",
        "低ボラ・安定",
        "安定成長",
        "小型・成長探索",
        "NISA長期適合",
        "データ信頼度優先",
        "ETF低コスト・コア",
        "ETFインカム・分散",
    ]
    assert ranking_purpose_options() == ranking_policy_options()

    etf_options = ranking_purpose_options(RANKING_PRODUCT_ETF)
    assert etf_options == ranking_policy_options()
    assert RANKING_PURPOSE_SORT_TOTAL_SCORE not in ranking_policy_options()
    assert RANKING_PURPOSE_SORT_DIVIDEND_YIELD not in ranking_policy_options()
    assert RANKING_PURPOSE_SORT_PER not in ranking_policy_options()
    assert RANKING_PURPOSE_SORT_PBR not in ranking_policy_options()
    assert RANKING_PURPOSE_SORT_ROE not in ranking_policy_options()
    assert RANKING_PURPOSE_SORT_MARKET_CAP not in ranking_policy_options()
    assert RANKING_PURPOSE_SORT_VOLUME not in ranking_policy_options()
    assert RANKING_PURPOSE_SORT_VOLATILITY not in ranking_policy_options()


def test_ranking_policy_descriptions_cover_all_composite_options():
    for purpose in ranking_policy_options():
        description = ranking_policy_description(purpose)
        assert description["short_summary"]
        assert description["suited_for"]
        assert description["main_focus"]
        assert description["caution"]

    risk_adjusted = ranking_policy_description(RANKING_PURPOSE_RISK_ADJUSTED)
    assert "安定" in risk_adjusted["short_summary"]
    assert "リスク" in risk_adjusted["main_focus"]
    assert "売買推奨" in ranking_policy_description("unknown_policy")["caution"]
    assert RANKING_PURPOSE_SORT_RISK not in ranking_policy_options()
    assert RANKING_PURPOSE_SORT_DATA_QUALITY not in ranking_policy_options()
    assert ranking_policy_for_purpose(RANKING_PURPOSE_DIVIDEND) == (
        RANKING_PURPOSE_SUSTAINABLE_INCOME
    )
    assert ranking_policy_for_purpose(RANKING_PURPOSE_GROWTH) == RANKING_PURPOSE_QUALITY_GROWTH
    assert ranking_policy_for_purpose(RANKING_PURPOSE_VALUE) == RANKING_PURPOSE_QUALITY_VALUE
    assert ranking_policy_for_purpose(RANKING_PURPOSE_STABILITY) == (RANKING_PURPOSE_MIN_VOLATILITY)
    assert ranking_policy_for_purpose(RANKING_PURPOSE_TREND) == RANKING_PURPOSE_MOMENTUM


def test_beta_risk_filter_labels_explain_thresholds():
    assert RANKING_BETA_RISK_LABELS[RANKING_BETA_RISK_STANDARD_OR_LOWER] == "標準以下"
    assert "値動きリスク" in RANKING_FILTER_HELP_TEXTS["risk_band"]
    assert "厳密なβ値そのものではなく" in RANKING_FILTER_HELP_TEXTS["risk_band"]


def test_filter_symbol_universe_rows_searches_japanese_aliases():
    rows = symbol_universe_rows(
        [
            {"symbol": "7203.T", "name": "Toyota Motor"},
            {"symbol": "AAPL", "name": "Apple Inc."},
        ]
    )

    assert [row["symbol"] for row in filter_symbol_universe_rows(rows, query="トヨタ")] == [
        "7203.T"
    ]


def test_ranking_filter_signature_changes_when_conditions_change():
    base = ranking_filter_signature(
        region="us",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="dividend",
        period_preset="short",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="dividend",
        period_preset="short",
        market="jp",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_includes_ranking_classification():
    base = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="growth",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_includes_official_sector_filter():
    base = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        official_sector="all",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        official_sector="industrial",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_includes_investment_style():
    base = ranking_filter_signature(
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        product_type="stock",
        ranking_purpose="trend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_includes_nisa_filter():
    base = ranking_filter_signature(
        purpose="dividend",
        period_preset="short",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        nisa_eligibility="all",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        purpose="dividend",
        period_preset="short",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        nisa_eligibility="growth",
        theme="all",
        query="",
        limit=6,
    )

    assert base != changed


def test_ranking_filter_signature_ignores_hidden_etf_filters_for_stock():
    base = ranking_filter_signature(
        region="all",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        index_family="all",
        max_expense_ratio_pct="1.00",
        complexity="standard",
        theme="all",
        query="",
        limit=0,
    )
    changed = ranking_filter_signature(
        region="all",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        index_family="sp500",
        max_expense_ratio_pct="0.05",
        complexity="beginner",
        theme="all",
        query="",
        limit=0,
    )

    assert base == changed


def test_ranking_filter_signature_ignores_hidden_stock_filters_for_etf():
    base = ranking_filter_signature(
        region="all",
        product_type="etf",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        market_cap_tier="all",
        complexity="standard",
        theme="all",
        query="",
        limit=0,
    )
    changed = ranking_filter_signature(
        region="all",
        product_type="etf",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="all",
        market_cap_tier="large",
        complexity="standard",
        theme="all",
        query="",
        per_enabled=True,
        per_min="2.0",
        per_max="3.0",
        pbr_enabled=True,
        pbr_min="0.5",
        pbr_max="0.6",
        roe_enabled=True,
        roe_min_pct="20.0",
        roe_max_pct="30.0",
        limit=0,
    )

    assert base == changed


def test_ranking_filter_signature_ignores_period_preset():
    base = ranking_filter_signature(
        purpose="dividend",
        period_preset="short",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )
    changed = ranking_filter_signature(
        purpose="dividend",
        period_preset="long",
        market="us",
        asset_type="stock",
        currency="all",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="",
        limit=6,
    )

    assert base == changed


def test_ranking_filter_signature_normalizes_inactive_dividend_side():
    category_only = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="high_dividend",
        min_dividend_yield_pct="3.2",
        dividend_yield_enabled=False,
        dividend_yield_max_pct="8.0",
        complexity="standard",
        theme="all",
        query="",
        limit=0,
    )
    explicit_range = ranking_filter_signature(
        region="japan",
        product_type="stock",
        ranking_purpose="dividend",
        purpose="all",
        period_preset="short",
        market="all",
        asset_type="all",
        currency="all",
        dividend_category="high_dividend",
        min_dividend_yield_pct="3.2",
        dividend_yield_enabled=True,
        dividend_yield_max_pct="8.0",
        complexity="standard",
        theme="all",
        query="",
        limit=0,
    )

    assert "high_dividend|0.0" in category_only
    assert "|all|3.2|" in explicit_range


def test_ranking_comparison_summary_shows_period_and_selection_status():
    assert ranking_comparison_summary(
        start=date(2026, 5, 11),
        end=date(2026, 5, 18),
        candidate_count=46,
        selected_count=46,
    ) == {
        "period": "2026-05-11 〜 2026-05-18",
        "candidate": "46件",
        "selected": "46 / 46件",
        "status": "全候補を比較",
        "inline": "取得期間: 2026-05-11 〜 2026-05-18 / 候補: 46件 / 選択: 46 / 46件（全候補を比較）",
    }
    assert (
        ranking_comparison_summary(
            start=date(2026, 5, 11),
            end=date(2026, 5, 18),
            candidate_count=46,
            selected_count=12,
        )["status"]
        == "一部を比較"
    )
    assert (
        ranking_comparison_summary(
            start=date(2026, 5, 11),
            end=date(2026, 5, 18),
            candidate_count=0,
            selected_count=0,
        )["status"]
        == "候補なし"
    )


def test_ranking_data_state_text_separates_refresh_from_local_sorting():
    text, detail_rows = _ranking_data_state_text(
        provider="yahoo",
        rows=[
            {"銘柄": "7203.T", "取得元": "yahoo"},
            {"銘柄": "9983.T", "取得元": "N/A"},
        ],
        error_rows=[{"symbol": "NO_DATA"}],
        updated_at="2026-06-01 22:30",
    )

    assert "一部銘柄は最新取得データを反映済み" in text
    assert "2026-06-01 22:30" in text
    assert detail_rows[:3] == [
        {"区分": "保存済み", "件数": "1"},
        {"区分": "最新反映", "件数": "1"},
        {"区分": "取得失敗", "件数": "1"},
    ]


def test_ranking_symbols_state_key_uses_filter_signature():
    signature = ranking_filter_signature(
        purpose="all",
        period_preset="short",
        market="jp",
        asset_type="stock",
        currency="JPY",
        dividend_category="all",
        complexity="standard",
        theme="all",
        query="toyota",
        limit=6,
    )

    assert ranking_symbols_state_key(signature) == f"market_data_ranking_symbols_{signature}"


def test_ranking_build_cache_key_ignores_weight_preset():
    first = ranking_build_cache_key(
        provider="yahoo",
        symbols=["AAPL", "MSFT"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    second = ranking_build_cache_key(
        provider="yahoo",
        symbols=["AAPL", "MSFT"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )

    assert first == second


def test_ranking_source_key_for_selection_matches_actual_fetch_symbols():
    source_key = _ranking_source_key_for_selection(
        provider="yahoo",
        selected_labels=["AAPL - Apple Inc.", "MSFT - Microsoft"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )

    assert source_key.endswith(
        ranking_build_cache_key(
            provider="yahoo",
            symbols=["AAPL", "MSFT"],
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
        )
    )
    assert source_key.startswith("signal-v4|")
    assert (
        _ranking_source_key_for_selection(
            provider="yahoo",
            selected_labels=[],
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
        )
        == ""
    )


def test_ranking_result_matches_current_selection_detects_stale_results():
    old_unversioned_source = ranking_build_cache_key(
        provider="yahoo",
        symbols=["AAPL"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    stored_source = _ranking_source_key_for_selection(
        provider="yahoo",
        selected_labels=["AAPL - Apple Inc."],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )

    assert _ranking_result_matches_current_selection(
        stored_source,
        provider="yahoo",
        selected_labels=["AAPL - Apple Inc."],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    assert not _ranking_result_matches_current_selection(
        old_unversioned_source,
        provider="yahoo",
        selected_labels=["AAPL - Apple Inc."],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    assert not _ranking_result_matches_current_selection(
        stored_source,
        provider="yahoo",
        selected_labels=["MSFT - Microsoft"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    assert not _ranking_result_matches_current_selection(
        stored_source,
        provider="yahoo",
        selected_labels=[],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )


def test_ranking_build_cache_reuses_rows_for_same_market_data_request(monkeypatch):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.app.st.session_state", session_state)
    cache_key = ranking_build_cache_key(
        provider="mock",
        symbols=["AAPL"],
        start=date(2026, 5, 10),
        end=date(2026, 5, 17),
    )
    rows = [{"symbol": "AAPL", "total_score": "70"}]
    error_rows = [{"symbol": "ERR", "message": "failed"}]

    set_cached_ranking_build(cache_key, rows=rows, error_rows=error_rows)

    assert get_cached_ranking_build(cache_key) == (rows, error_rows)
    assert get_cached_ranking_build("missing") is None


def test_ranking_build_job_state_blocks_restore_only_while_running():
    cache_key = "test-running-ranking-build"

    app_module.begin_ranking_build(cache_key)
    assert app_module.ranking_build_is_running(cache_key)

    app_module.complete_ranking_build(cache_key)
    assert not app_module.ranking_build_is_running(cache_key)

    app_module.begin_ranking_build(cache_key)
    app_module.fail_ranking_build(cache_key)
    assert not app_module.ranking_build_is_running(cache_key)


def test_ranking_symbol_db_preflight_is_protected_from_maintenance_restart():
    source = inspect.getsource(app_module._render_market_data_ranking)

    preflight_start = source.index("_run_symbol_database_preflight_refresh(")
    preflight_guard = source.index('maintenance_operation("ranking_build_preflight")')
    market_data_guard = source.index('maintenance_operation("ranking_build")')

    assert preflight_guard < preflight_start < market_data_guard


def test_ranking_widgets_use_session_state_without_conflicting_index_defaults():
    source = inspect.getsource(app_module._render_market_data_ranking)
    detail_source = inspect.getsource(app_module._render_detail_selectbox)

    assert 'key="market_data_ranking_fetch_limit"' in source
    assert 'key="market_data_ranking_fetch_limit",\n                    index=' not in source
    assert "index=_selectbox_index" not in detail_source


def test_large_live_ranking_uses_bounded_cohorts(monkeypatch):
    calls: list[tuple[int, bool]] = []
    released: list[list[str]] = []

    async def fake_fast(symbols, **kwargs):
        calls.append((len(symbols), bool(kwargs["include_advanced_forecast"])))
        return ([{"symbol": symbol} for symbol in symbols], [])

    monkeypatch.setattr(app_module, "_build_market_data_ranking_rows_fast", fake_fast)
    monkeypatch.setattr(
        app_module,
        "_release_ranking_cohort_cache",
        lambda _provider, symbols: released.append(list(symbols)),
    )
    symbols = [f"{index:05d}.T" for index in range(10_001)]

    rows, errors = asyncio.run(
        app_module._build_market_data_ranking_rows(
            symbols,
            start=date(2023, 1, 1),
            end=date(2026, 1, 1),
            provider="yahoo",
        )
    )

    assert calls[:-1] == [(100, False)] * 100 + [(1, False)]
    assert calls[-1] == (100, True)
    assert [len(batch) for batch in released] == [100] * 100 + [1, 100]
    assert len(rows) == len(symbols)
    assert errors == []


def test_large_ranking_releases_only_completed_cohort_caches(monkeypatch):
    ohlcv_cache = {
        ("yahoo", "AAA", "start", "end"): [object()],
        ("yahoo", "BBB", "start", "end"): [object()],
        ("mock", "AAA", "start", "end"): [object()],
    }
    fundamental_cache = {
        ("yahoo", "AAA", "2026-01-01"): [object()],
        ("yahoo", "BBB", "2026-01-01"): [object()],
    }
    advanced_cache = {
        ("AAA", 20, 100, "latest", "100"): {"score": "70"},
        ("BBB", 20, 100, "latest", "100"): {"score": "70"},
    }
    monkeypatch.setattr(app_module, "_ranking_ohlcv_cache", lambda: ohlcv_cache)
    monkeypatch.setattr(app_module, "_ranking_fundamental_cache", lambda: fundamental_cache)
    monkeypatch.setattr(app_module, "_ranking_advanced_forecast_cache", lambda: advanced_cache)
    monkeypatch.setattr(app_module.gc, "collect", lambda: 0)

    app_module._release_ranking_cohort_cache("yahoo", ["AAA"])

    assert ("yahoo", "AAA", "start", "end") not in ohlcv_cache
    assert ("yahoo", "BBB", "start", "end") in ohlcv_cache
    assert ("mock", "AAA", "start", "end") in ohlcv_cache
    assert ("yahoo", "AAA", "2026-01-01") not in fundamental_cache
    assert ("yahoo", "BBB", "2026-01-01") in fundamental_cache
    assert all(key[0] != "AAA" for key in advanced_cache)
    assert any(key[0] == "BBB" for key in advanced_cache)


def test_advanced_forecast_cache_is_not_published_from_failed_batch(monkeypatch):
    cache_calls: list[str] = []

    def fake_evaluate(symbol, bars, horizon_days):
        if symbol == "BBB":
            raise RuntimeError("forecast failed")
        return symbol, [], None

    monkeypatch.setattr(
        app_module,
        "evaluate_advanced_forecasts_for_symbol",
        fake_evaluate,
    )
    monkeypatch.setattr(
        app_module,
        "_get_cached_ranking_advanced_forecast",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        app_module,
        "_cache_ranking_advanced_forecast",
        lambda symbol, *args, **kwargs: cache_calls.append(symbol),
    )

    with pytest.raises(RuntimeError, match="forecast failed"):
        app_module._ranking_advanced_forecast_fields_for_symbols(
            ["AAA", "BBB"],
            bars_by_symbol={"AAA": [object()], "BBB": [object()]},
            horizon_days=5,
            progress_callback=None,
        )

    assert cache_calls == []


def test_ranking_filter_state_persists_modal_values_after_widget_cleanup(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_min_dividend": "3.0",
        "market_data_ranking_market": "jp",
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    filters = persist_ranking_filter_state()
    session_state.pop("market_data_ranking_min_dividend")
    session_state.pop("market_data_ranking_market")

    assert filters["market_data_ranking_min_dividend"] == "3.0"
    assert current_ranking_filter_state()["market_data_ranking_min_dividend"] == "3.0"
    assert current_ranking_filter_state()["market_data_ranking_market"] == "jp"


def test_clear_ranking_filter_state_resets_visible_filters_and_result_state(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_currency": "USD",
        "market_data_ranking_nisa": "growth",
        "market_data_ranking_symbol_query": "toyota",
        "market_data_ranking_rows": [{"symbol": "AAPL"}],
        "market_data_ranking_error_rows": [{"symbol": "ERR"}],
        "market_data_ranking_selected_labels": ["AAPL - Apple Inc."],
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    clear_ranking_filter_state()

    assert session_state["market_data_ranking_currency"] == "all"
    assert session_state["market_data_ranking_nisa"] == "all"
    assert session_state["market_data_ranking_symbol_query"] == ""
    assert "market_data_ranking_rows" not in session_state
    assert "market_data_ranking_error_rows" not in session_state
    assert "market_data_ranking_selected_labels" not in session_state


def test_clear_ranking_detail_condition_state_keeps_top_level_controls(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_region": "us",
        "market_data_ranking_product_type": "stock",
        "market_data_ranking_policy": RANKING_PURPOSE_QUALITY_GROWTH,
        "market_data_ranking_period": "medium",
        "market_data_ranking_fetch_limit": "fast_100",
        "market_data_ranking_currency": "USD",
        "market_data_ranking_nisa": "growth",
        "market_data_ranking_symbol_query": "toyota",
        "market_data_ranking_per_enabled": True,
        "market_data_ranking_rows": [{"symbol": "AAPL"}],
        "market_data_ranking_error_rows": [{"symbol": "ERR"}],
        "market_data_ranking_selected_labels": ["AAPL - Apple Inc."],
    }
    monkeypatch.setattr("ui.app.st.session_state", session_state)

    clear_ranking_detail_condition_state()

    assert session_state["market_data_ranking_region"] == "us"
    assert session_state["market_data_ranking_product_type"] == "stock"
    assert session_state["market_data_ranking_policy"] == RANKING_PURPOSE_QUALITY_GROWTH
    assert session_state["market_data_ranking_period"] == "medium"
    assert session_state["market_data_ranking_fetch_limit"] == "fast_100"
    assert session_state["market_data_ranking_currency"] == "all"
    assert session_state["market_data_ranking_nisa"] == "all"
    assert session_state["market_data_ranking_symbol_query"] == ""
    assert session_state["market_data_ranking_per_enabled"] is False
    assert "market_data_ranking_rows" not in session_state
    assert "market_data_ranking_error_rows" not in session_state
    assert "market_data_ranking_selected_labels" not in session_state


def test_valid_ranking_selected_labels_keeps_only_available_options():
    assert valid_ranking_selected_labels(
        ["7203.T - Toyota Motor", "OLD - Removed"],
        ["7203.T - Toyota Motor", "9983.T - Fast Retailing"],
    ) == ["7203.T - Toyota Motor"]


def test_initial_ranking_selected_labels_defaults_to_all_matching_candidates():
    labels = ["7203.T - Toyota Motor", "9983.T - Fast Retailing"]

    assert initial_ranking_selected_labels(labels, []) == labels
    assert initial_ranking_selected_labels(labels, ["7203.T - Toyota Motor"]) == [
        "7203.T - Toyota Motor"
    ]


def test_initial_ranking_selected_labels_for_new_filter_key_uses_all_candidates(monkeypatch):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    labels = ["7203.T - Toyota Motor", "9983.T - Fast Retailing"]

    assert (
        initial_ranking_selected_labels_for_key(
            selection_key="market_data_ranking_symbols_new",
            labels=labels,
            stored_selected_labels=["7203.T - Toyota Motor"],
        )
        == labels
    )


def test_initial_ranking_selected_labels_for_existing_key_keeps_user_selection(monkeypatch):
    session_state: dict[str, object] = {"market_data_ranking_symbols_existing": []}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    labels = ["7203.T - Toyota Motor", "9983.T - Fast Retailing"]

    assert initial_ranking_selected_labels_for_key(
        selection_key="market_data_ranking_symbols_existing",
        labels=labels,
        stored_selected_labels=["7203.T - Toyota Motor"],
    ) == ["7203.T - Toyota Motor"]


def test_ensure_ranking_selection_widget_state_initializes_new_key_with_all_candidates(
    monkeypatch,
):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    labels = ["7203.T - Toyota Motor", "9983.T - Fast Retailing"]

    ensure_ranking_selection_widget_state(
        selection_key="market_data_ranking_symbols_new",
        labels=labels,
        stored_selected_labels=[],
    )

    assert session_state["market_data_ranking_symbols_new"] == labels
    assert session_state["market_data_ranking_selected_labels"] == labels


def test_ensure_ranking_selection_widget_state_preserves_existing_user_selection(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_symbols_existing": ["7203.T - Toyota Motor"]
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    ensure_ranking_selection_widget_state(
        selection_key="market_data_ranking_symbols_existing",
        labels=["7203.T - Toyota Motor", "9983.T - Fast Retailing"],
        stored_selected_labels=[],
    )

    assert session_state["market_data_ranking_symbols_existing"] == ["7203.T - Toyota Motor"]
    assert "market_data_ranking_selected_labels" not in session_state


def test_ensure_ranking_selection_widget_state_removes_stale_options(monkeypatch):
    session_state: dict[str, object] = {
        "market_data_ranking_symbols_existing": [
            "7203.T - Toyota Motor",
            "OLD - Removed",
        ]
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    ensure_ranking_selection_widget_state(
        selection_key="market_data_ranking_symbols_existing",
        labels=["7203.T - Toyota Motor", "9983.T - Fast Retailing"],
        stored_selected_labels=[],
    )

    assert session_state["market_data_ranking_symbols_existing"] == ["7203.T - Toyota Motor"]


def test_sync_ranking_selection_state_updates_widget_and_persistent_state(monkeypatch):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    sync_ranking_selection_state(
        "market_data_ranking_symbols_test",
        ["7203.T - Toyota Motor"],
        update_widget_state=True,
    )

    assert session_state["market_data_ranking_selected_labels"] == ["7203.T - Toyota Motor"]
    assert session_state["market_data_ranking_symbols_test"] == ["7203.T - Toyota Motor"]


def test_sync_ranking_selection_state_can_skip_widget_state(monkeypatch):
    session_state: dict[str, object] = {"market_data_ranking_symbols_test": ["OLD"]}
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)

    sync_ranking_selection_state(
        "market_data_ranking_symbols_test",
        ["7203.T - Toyota Motor"],
    )

    assert session_state["market_data_ranking_selected_labels"] == ["7203.T - Toyota Motor"]
    assert session_state["market_data_ranking_symbols_test"] == ["OLD"]


def test_apply_ranking_filter_state_selects_filtered_candidates(monkeypatch):
    session_state = {
        "market_data_ranking_rows": [{"symbol": "OLD"}],
        "market_data_ranking_error_rows": [{"symbol": "ERR"}],
        "market_data_ranking_filter_dialog_open": True,
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    preview_rows = [
        {"symbol": "7203.T", "name": "Toyota Motor"},
        {"symbol": "9983.T", "name": "Fast Retailing"},
    ]
    signature = "all|short|jp|stock|JPY|all|0.0|all|all|1.00|standard|all||2"

    apply_ranking_filter_state(preview_rows, signature)

    assert session_state["market_data_ranking_filter_signature"] == signature
    assert session_state["market_data_ranking_selected_labels"] == [
        "7203.T - Toyota Motor",
        "9983.T - Fast Retailing",
    ]
    assert session_state[ranking_symbols_state_key(signature)] == [
        "7203.T - Toyota Motor",
        "9983.T - Fast Retailing",
    ]
    assert "market_data_ranking_rows" not in session_state
    assert "market_data_ranking_error_rows" not in session_state
    assert session_state["market_data_ranking_filter_dialog_open"] is False


def test_ranking_period_dates_use_beginner_presets():
    end = date(2026, 5, 17)

    assert list(RANKING_PERIOD_PRESETS) == [
        "short",
        "standard",
        "medium",
        "long",
        "long_3y",
        "long_5y",
    ]
    assert ranking_period_label("standard") == "標準: 3か月"
    assert ranking_period_label("short") == "短期: 1か月"
    assert ranking_period_label("medium") == "中期: 6か月"
    assert ranking_period_label("long_3y") == "長期: 3年"
    assert ranking_period_label("long_5y") == "長期: 5年"
    assert ranking_period_dates("standard", end) == (date(2026, 2, 16), end)
    assert ranking_period_dates("short", end) == (date(2026, 4, 17), end)
    assert ranking_period_dates("medium", end) == (date(2025, 11, 18), end)
    assert ranking_period_dates("long", end) == (date(2025, 5, 17), end)
    assert ranking_period_dates("long_3y", end) == (date(2023, 5, 17), end)
    assert ranking_period_dates("long_5y", end) == (date(2021, 5, 17), end)
    assert "標準は3か月" in RANKING_FILTER_HELP_TEXTS["period"]
    assert "1か月は直近反応" in RANKING_FILTER_HELP_TEXTS["period"]
    assert "3年/5年は長期トレンド" in RANKING_FILTER_HELP_TEXTS["period"]


def test_build_market_data_ranking_rows_fetches_symbols_concurrently(monkeypatch):
    async def fail_fast_path(*args, **kwargs):
        raise DataSourceError("batch unavailable")

    active_count = 0
    max_active_count = 0

    monkeypatch.setattr("ui.app._build_market_data_ranking_rows_fast", fail_fast_path)

    async def fake_build_market_data_preview(
        *,
        symbol,
        start,
        end,
        provider_override,
        forecast_horizon_days,
    ):
        nonlocal active_count, max_active_count
        active_count += 1
        max_active_count = max(max_active_count, active_count)
        await asyncio.sleep(0)
        active_count -= 1
        return SimpleNamespace(
            investment_score_rows=[
                {
                    "symbol": symbol,
                    "total_score": "70",
                    "screening_score": "70",
                    "forecast_agreement": "70",
                    "data_quality": "100",
                }
            ],
            error_rows=[],
        )

    monkeypatch.setattr(
        "ui.app.build_market_data_preview",
        fake_build_market_data_preview,
    )
    progress_messages: list[str] = []

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["7203.T", "9983.T", "6758.T"],
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
            provider="mock",
            progress_callback=lambda message, _ratio: progress_messages.append(message),
        )
    )

    assert [row["symbol"] for row in rows] == ["7203.T", "9983.T", "6758.T"]
    assert error_rows == []
    assert max_active_count > 1
    assert any("銘柄別に取得しています" in message for message in progress_messages)


def test_build_market_data_ranking_rows_throttles_preview_progress(monkeypatch):
    async def fail_fast_path(*args, **kwargs):
        raise DataSourceError("batch unavailable")

    monkeypatch.setattr("ui.app._build_market_data_ranking_rows_fast", fail_fast_path)

    async def fake_build_market_data_preview(
        *,
        symbol,
        start,
        end,
        provider_override,
        forecast_horizon_days,
    ):
        await asyncio.sleep(0)
        return SimpleNamespace(
            investment_score_rows=[
                {
                    "symbol": symbol,
                    "total_score": "70",
                    "screening_score": "70",
                    "forecast_agreement": "70",
                    "data_quality": "100",
                }
            ],
            error_rows=[],
        )

    monkeypatch.setattr(
        "ui.app.build_market_data_preview",
        fake_build_market_data_preview,
    )
    progress_messages: list[str] = []
    symbols = [f"SYM{i}" for i in range(21)]

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            symbols,
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
            provider="mock",
            progress_callback=lambda message, _ratio: progress_messages.append(message),
        )
    )

    assert len(rows) == 21
    assert error_rows == []
    assert any("(1/21)" in message for message in progress_messages)
    assert any("(10/21)" in message for message in progress_messages)
    assert any("(20/21)" in message for message in progress_messages)
    assert any("(21/21)" in message for message in progress_messages)
    assert not any("(2/21)" in message for message in progress_messages)


def test_build_market_data_ranking_rows_does_not_retry_live_batch_failure(monkeypatch):
    async def fail_fast_path(*args, **kwargs):
        raise DataSourceError("batch unavailable", details={"provider": "yahoo"})

    async def fail_preview(*args, **kwargs):
        raise AssertionError("live provider failures should not retry per-symbol previews")

    monkeypatch.setattr("ui.app._build_market_data_ranking_rows_fast", fail_fast_path)
    monkeypatch.setattr("ui.app.build_market_data_preview", fail_preview)
    progress_messages: list[str] = []

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["7203.T", "9983.T"],
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
            provider="yahoo",
            progress_callback=lambda message, _ratio: progress_messages.append(message),
        )
    )

    assert rows == []
    assert error_rows == [
        {
            "symbol": "7203.T, 9983.T",
            "code": "APP-2000",
            "message": "batch unavailable",
            "details": '{"provider": "yahoo", "symbols": ["7203.T", "9983.T"]}',
        }
    ]
    assert progress_messages[-1] == "Yahoo live data の一括取得に失敗しました。"


def test_large_live_ranking_uses_one_continuous_pipeline(monkeypatch):
    calls: list[list[str]] = []

    async def fake_fast(symbols, **kwargs):
        calls.append(symbols)
        return (
            [
                {
                    "symbol": symbol,
                    "total_score": str(80 - (index % 10)),
                }
                for index, symbol in enumerate(symbols)
            ],
            [],
        )

    monkeypatch.setattr("ui.app._build_market_data_ranking_rows_fast", fake_fast)
    symbols = [f"SYM{index}" for index in range(205)]

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            symbols,
            start=date(2026, 5, 10),
            end=date(2026, 5, 17),
            provider="yahoo",
        )
    )

    assert [len(call) for call in calls] == [205]
    assert len(rows) == 205
    assert {row["symbol"] for row in rows} == set(symbols)
    assert error_rows == []


def test_ranking_provider_error_rows_summarizes_many_symbols():
    rows = ranking_provider_error_rows(
        "yahoo",
        [f"SYM{i}" for i in range(10)],
        DataSourceError("failed", details={"request": {"operation": "fetch_ohlcv"}}),
    )

    assert rows[0]["symbol"] == "SYM0, SYM1, SYM2, SYM3, SYM4, SYM5, SYM6, SYM7, ... (+2)"
    details = json.loads(rows[0]["details"])
    assert details["provider"] == "yahoo"
    assert details["request"]["operation"] == "fetch_ohlcv"


def test_ranking_batch_failure_retries_symbols_and_keeps_partial_results():
    class PartiallyAvailableAdapter:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        async def fetch_ohlcv(self, symbols, start, end):
            self.calls.append(symbols)
            if len(symbols) > 1 or symbols == ["9432.T"]:
                raise ProviderUnavailableError(
                    "Yahoo market-data provider returned no batch data",
                    details={"request": {"symbols": symbols}},
                )
            return [object()]

    adapter = PartiallyAvailableAdapter()
    symbols = ["7203.T", "9432.T", "7974.T"]
    bars, errors, failed = asyncio.run(
        _fetch_ranking_ohlcv_tolerant(
            adapter,
            symbols,
            provider="yahoo",
            start=datetime(2025, 7, 5, tzinfo=UTC),
            end=datetime(2026, 7, 5, tzinfo=UTC),
            display_symbols_by_provider_symbol={symbol: [symbol] for symbol in symbols},
        )
    )

    assert adapter.calls == [symbols, ["7203.T"], ["9432.T"], ["7974.T"]]
    assert len(bars) == 2
    assert len(errors) == 1
    assert failed == {"9432.T"}


def test_build_market_data_ranking_rows_uses_batch_fast_path(monkeypatch):
    class FakeBatchAdapter:
        def __init__(self) -> None:
            self.ohlcv_calls = 0
            self.fundamental_calls = 0
            self.healthcheck_calls = 0

        async def fetch_ohlcv(self, symbols, start, end, interval="1d"):
            self.ohlcv_calls += 1
            bars = []
            for symbol in symbols:
                contract = Symbol(
                    raw=symbol,
                    exchange="NASDAQ",
                    code=symbol,
                    currency="USD",
                )
                bar_count = 1 if symbol == "BBB" else 30
                for day in range(bar_count):
                    close = Decimal("100") + Decimal(day)
                    bars.append(
                        Bar(
                            symbol=contract,
                            ts=datetime(2026, 4, day + 1, tzinfo=UTC),
                            open=close,
                            high=close + Decimal("1"),
                            low=close - Decimal("1"),
                            close=close,
                            volume=Decimal("1000000"),
                            interval=interval,
                            provider="fake",
                        )
                    )
            return bars

        async def fetch_fundamentals(self, symbols, as_of):
            self.fundamental_calls += 1
            return [
                FundamentalSnapshot(
                    symbol=symbol,
                    as_of=as_of,
                    provider="fake",
                    dividend_yield=Decimal("0.03"),
                    market_cap_jpy=Decimal("1000000000000"),
                )
                for symbol in symbols
            ]

        def healthcheck(self):
            self.healthcheck_calls += 1
            return {"provider": "fake", "status": "ok"}

    adapter = FakeBatchAdapter()

    async def fail_preview(*args, **kwargs):
        raise AssertionError("slow preview path should not be used")

    monkeypatch.setattr(
        "ui.app.create_market_data_provider_adapter",
        lambda _: adapter,
    )
    monkeypatch.setattr("ui.app.build_market_data_preview", fail_preview)

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["AAA", "BBB"],
            start=date(2026, 4, 20),
            end=date(2026, 4, 30),
            provider="mock",
        )
    )

    assert adapter.ohlcv_calls == 1
    assert adapter.fundamental_calls == 1
    assert adapter.healthcheck_calls == 1
    assert [row["symbol"] for row in rows] == ["AAA"]
    assert error_rows == [
        {
            "symbol": "BBB",
            "code": "RANKING-INSUFFICIENT-BARS",
            "message": "価格データが2本未満のため、ランキングから除外しました。",
            "details": (
                '{"bar_count": 1, "display_end": "2026-04-30", '
                '"display_start": "2026-04-20", "provider": "mock", '
                '"reason": "insufficient_ohlcv_rows", "symbol": "BBB"}'
            ),
        }
    ]


def test_build_market_data_ranking_rows_adds_current_price_jpy_for_usd(monkeypatch):
    class FakeBatchAdapter:
        def __init__(self) -> None:
            self.fx_calls = 0

        async def fetch_ohlcv(self, symbols, start, end, interval="1d"):
            bars = []
            for symbol in symbols:
                contract = Symbol(raw=symbol, exchange="NASDAQ", code=symbol, currency="USD")
                for day in range(30):
                    close = Decimal("100") + Decimal(day)
                    bars.append(
                        Bar(
                            symbol=contract,
                            ts=datetime(2026, 4, day + 1, tzinfo=UTC),
                            open=close,
                            high=close + Decimal("1"),
                            low=close - Decimal("1"),
                            close=close,
                            volume=Decimal("1000000"),
                            interval=interval,
                            provider="fake",
                        )
                    )
            return bars

        async def get_fx_rates(self, pairs, at=None, method="spot"):
            self.fx_calls += 1
            assert pairs == ["USDJPY"]
            assert method == "spot"
            return [FxRate(pair="USDJPY", rate=Decimal("150"), ts=at or datetime.now(UTC))]

        async def fetch_fundamentals(self, symbols, as_of):
            return [
                FundamentalSnapshot(
                    symbol=symbol,
                    as_of=as_of,
                    provider="fake",
                    dividend_yield=Decimal("0.03"),
                    market_cap_jpy=Decimal("1000000000000"),
                )
                for symbol in symbols
            ]

        def healthcheck(self):
            return {"provider": "fake", "status": "ok"}

    adapter = FakeBatchAdapter()
    monkeypatch.setattr(
        "ui.app.create_market_data_provider_adapter",
        lambda _: adapter,
    )

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["AAPL"],
            start=date(2026, 4, 20),
            end=date(2026, 4, 30),
            provider="mock",
        )
    )
    display_rows = investment_score_display_rows(rows)
    frame = ranking_result_aggrid_frame(display_rows)

    assert adapter.fx_calls == 1
    assert error_rows == []
    assert rows[0]["current_price"] == "129"
    assert rows[0]["current_price_currency"] == "USD"
    assert rows[0]["current_price_jpy"] == "19350"
    assert display_rows[0]["現在株価（円）"] == "19350"
    assert display_rows[0]["株価"] == "19,350円（129 USD）"
    assert display_rows[0]["現在値"] == "129"
    assert frame.loc[0, "株価"] == "19,350円（129 USD）"


def test_ranking_stock_price_keeps_jpy_primary_for_domestic_symbol():
    display_rows = investment_score_display_rows(
        [
            {
                "symbol": "7203.T",
                "current_price": "2845.5",
                "current_price_jpy": "2845.5",
                "current_price_currency": "JPY",
            }
        ]
    )

    assert display_rows[0]["株価"] == "2,845.5円"


def test_build_market_data_ranking_rows_uses_feature_history_for_direction_signal(monkeypatch):
    class FakeBatchAdapter:
        async def fetch_ohlcv(self, symbols, start, end, interval="1d"):
            bars = []
            for symbol in symbols:
                contract = Symbol(raw=symbol, exchange="NASDAQ", code=symbol, currency="USD")
                for day in range(30):
                    close = Decimal("100") + Decimal(day)
                    bars.append(
                        Bar(
                            symbol=contract,
                            ts=datetime(2026, 4, day + 1, tzinfo=UTC),
                            open=close,
                            high=close + Decimal("1"),
                            low=close - Decimal("1"),
                            close=close,
                            volume=Decimal("1000000"),
                            interval=interval,
                            provider="fake",
                        )
                    )
            return bars

        async def fetch_fundamentals(self, symbols, as_of):
            return [
                FundamentalSnapshot(
                    symbol=symbol,
                    as_of=as_of,
                    provider="fake",
                    dividend_yield=Decimal("0.03"),
                    market_cap_jpy=Decimal("1000000000000"),
                )
                for symbol in symbols
            ]

        def healthcheck(self):
            return {"provider": "fake", "status": "ok"}

    monkeypatch.setattr(
        "ui.app.create_market_data_provider_adapter",
        lambda _: FakeBatchAdapter(),
    )

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["AAA"],
            start=date(2026, 4, 30),
            end=date(2026, 4, 30),
            provider="mock",
        )
    )

    assert error_rows == []
    assert rows[0]["direction_signal_label"] != "UNKNOWN"
    assert rows[0]["upside_signal_score"] != "50"
    assert rows[0]["downside_signal_score"] != "50"
    assert rows[0]["up_model_count"] == "1"
    assert rows[0]["down_model_count"] == "1"


def test_build_market_data_ranking_rows_reports_no_bars_details(monkeypatch):
    class FakePartialBatchAdapter:
        async def fetch_ohlcv(self, symbols, start, end, interval="1d"):
            bars = []
            for symbol in symbols:
                if symbol == "MISSING":
                    continue
                contract = Symbol(raw=symbol, exchange="NASDAQ", code=symbol, currency="USD")
                for day in range(30):
                    close = Decimal("100") + Decimal(day)
                    bars.append(
                        Bar(
                            symbol=contract,
                            ts=datetime(2026, 4, day + 1, tzinfo=UTC),
                            open=close,
                            high=close + Decimal("1"),
                            low=close - Decimal("1"),
                            close=close,
                            volume=Decimal("1000000"),
                            interval=interval,
                            provider="fake",
                        )
                    )
            return bars

        async def fetch_fundamentals(self, symbols, as_of):
            return [
                FundamentalSnapshot(
                    symbol=symbol,
                    as_of=as_of,
                    provider="fake",
                    dividend_yield=Decimal("0.03"),
                    market_cap_jpy=Decimal("1000000000000"),
                )
                for symbol in symbols
            ]

        def healthcheck(self):
            return {"provider": "fake", "status": "ok"}

    monkeypatch.setattr(
        "ui.app.create_market_data_provider_adapter",
        lambda _: FakePartialBatchAdapter(),
    )

    rows, error_rows = asyncio.run(
        _build_market_data_ranking_rows(
            ["AAA", "MISSING"],
            start=date(2026, 4, 20),
            end=date(2026, 4, 30),
            provider="mock",
        )
    )

    assert [row["symbol"] for row in rows] == ["AAA"]
    assert error_rows[0]["symbol"] == "MISSING"
    assert error_rows[0]["code"] == "RANKING-NO-BARS"
    assert error_rows[0]["message"] == (
        "価格データを取得できなかったため、ランキングから除外しました。"
    )
    details = json.loads(error_rows[0]["details"])
    assert details["provider"] == "mock"
    assert details["symbol"] == "MISSING"
    assert details["request"]["display_start"] == "2026-04-20"
    assert details["request"]["display_end"] == "2026-04-30"
    assert details["request"]["operation"] == "ranking_fetch_ohlcv"
    assert details["reason"] == "no_ohlcv_rows"


def test_ranking_symbol_chunks_split_large_builds():
    symbols = [f"SYM{i}" for i in range(53)]

    chunks = ranking_symbol_chunks(symbols)

    assert [len(chunk) for chunk in chunks] == [25, 25, 3]
    assert [symbol for chunk in chunks for symbol in chunk] == symbols


def test_live_ranking_symbol_warning_message_only_warns_for_large_live_requests():
    assert live_ranking_symbol_warning_message("mock", 80) is None
    assert live_ranking_symbol_warning_message("yahoo", 30) is None
    assert live_ranking_symbol_warning_message("yahoo", 31) == (
        "yahoo の 31 銘柄ランキングは時間がかかる場合があります。"
        "遅い場合は期間や対象を絞ってください。"
    )


def test_ranking_symbol_options_and_label_support_deep_dive():
    rows = [
        {"symbol": "AAPL", "total_score": "80"},
        {"symbol": "aapl", "total_score": "70"},
        {"symbol": "7203.T", "total_score": "60"},
        {"symbol": "", "total_score": "50"},
    ]

    assert ranking_symbol_options(rows) == ["AAPL", "7203.T"]
    assert symbol_candidate_label("AAPL") == "AAPL - Apple Inc."
    assert symbol_candidate_label("UNKNOWN") == "UNKNOWN"


def test_ranking_deep_dive_symbol_options_follow_displayed_rank():
    rows = [
        {"symbol": "THIRD", "rank": "3"},
        {"symbol": "FIRST", "rank": "1"},
        {"symbol": "SECOND", "rank": "2"},
    ]

    assert ranking_deep_dive_symbol_options(rows) == ["FIRST", "SECOND", "THIRD"]


def test_ranking_deep_dive_default_symbol_resets_for_new_result_source():
    rows = [
        {"symbol": "TOP", "total_score": "90"},
        {"symbol": "OLD", "total_score": "70"},
    ]

    assert (
        ranking_deep_dive_default_symbol(
            rows,
            current_symbol="OLD",
            source_key="new-ranking",
            current_source_key="old-ranking",
        )
        == "TOP"
    )
    assert (
        ranking_deep_dive_default_symbol(
            rows,
            current_symbol="OLD",
            source_key="same-ranking",
            current_source_key="same-ranking",
        )
        == "OLD"
    )
    assert (
        ranking_deep_dive_default_symbol(
            rows,
            current_symbol="REMOVED",
            source_key="same-ranking",
            current_source_key="same-ranking",
        )
        == "TOP"
    )


def test_forecast_reference_period_uses_horizon_and_bar_count():
    bars = [_bar(f"2026-05-{day:02d}") for day in range(1, 31)]

    assert forecast_reference_period(bars, horizon_days=1) == 3
    assert forecast_reference_period(bars, horizon_days=5) == 10
    assert forecast_reference_period(bars[:3], horizon_days=5) == 3


def test_forecast_consensus_rows_and_display_are_beginner_friendly():
    rows = forecast_consensus_rows_for_bars(
        [_bar(f"2026-05-{day:02d}", close=100 + day) for day in range(1, 8)]
    )

    assert rows == [
        {
            "symbol": "AAPL",
            "horizon_days": "1",
            "model_count": "3",
            "ensemble_forecast_close": "107.0096",
            "median_forecast_close": "107",
            "min_forecast_close": "106",
            "max_forecast_close": "108.0288",
            "forecast_range": "2.0288",
            "forecast_range_pct": "1.90%",
            "agreement": "MEDIUM",
            "latest_close": "107",
            "forecast_return_pct": "0.01%",
            "up_model_count": "1",
            "down_model_count": "1",
            "flat_model_count": "1",
            "up_direction_ratio": "33.33%",
            "down_direction_ratio": "33.33%",
            "upside_signal_score": "53.41",
            "downside_signal_score": "46.59",
            "direction_net_score": "53.41",
            "direction_signal_label": "NEUTRAL",
        }
    ]
    assert forecast_consensus_display_rows(rows) == [
        {
            "銘柄": "AAPL",
            "予測日数": "1",
            "モデル数": "3",
            "平均予測": "107.0096",
            "中央値予測": "107",
            "予測下限": "106",
            "予測上限": "108.0288",
            "予測の開き": "2.0288",
            "予測の開き(%)": "1.90%",
            "上昇気配": "53.41",
            "下降警戒": "46.59",
            "予測変化率": "0.01%",
            "方向一致": "上昇 1 / 下降 1 / 横ばい 1",
            "モデル一致度(補助)": "中くらい",
        }
    ]


def test_forecast_chart_summary_explains_agreement_and_range():
    messages = forecast_chart_summary(
        [
            {
                "symbol": "AAPL",
                "horizon_days": "1",
                "model_count": "3",
                "forecast_range_pct": "1.90%",
                "forecast_return_pct": "0.01%",
                "agreement": "MEDIUM",
                "upside_signal_score": "54.65",
                "downside_signal_score": "49.26",
                "direction_signal_label": "NEUTRAL",
            }
        ],
        [
            {
                "model": "naive",
                "symbol": "AAPL",
                "horizon_days": "1",
                "forecast_close": "107",
                "mae": "1.23",
                "rmse": "1.50",
                "direction_accuracy": "50.00%",
                "sample_count": "6",
            }
        ],
    )

    assert messages[0] == (
        "3 つの予測モデルを表示しています。" "平均予測の変化率は 0.01%、予測の開きは 1.90% です。"
    )
    assert messages[1] == (
        "実線はこれまでの価格、点線はモデルごとの予測です。"
        "方向シグナルは深掘り候補を整理する補助材料です。"
    )
    assert "予測: 直近値維持" in messages[2]


def test_investment_score_display_rows_are_beginner_friendly():
    rows = investment_score_display_rows(
        [
            {
                "rank": "1",
                "symbol": "AAPL",
                "total_score": "73",
                "score_band": "BALANCED",
                "screening_score": "80",
                "forecast_agreement_score": "40",
                "upside_signal_score": "50",
                "downside_signal_score": "50",
                "data_quality_score": "100",
                "risk_signal_score": "",
                "warnings": "model_disagreement:high",
                "note": "売買推奨ではなく、判断材料を整理したスコアです。",
            }
        ]
    )

    assert rows[0]["順位"] == "1"
    assert rows[0]["銘柄"] == "AAPL"
    assert rows[0]["銘柄名"] == "Apple Inc."
    assert rows[0]["総合スコア"] == "73"
    assert rows[0]["見方"] == "バランス型"
    assert rows[0]["上昇気配"] == "50"
    assert rows[0]["下降警戒"] == "50"
    assert rows[0]["方向一致"] == "上昇 0 / 下降 0 / 横ばい 0"
    assert rows[0]["モデル一致度"] == "40"
    assert rows[0]["データ品質"] == "100"
    assert rows[0]["Risk"] == "未接続"
    assert rows[0]["注意点"] == "モデルの見方が割れています"
    assert "方向感" not in rows[0]
    assert "方向スコア" not in rows[0]
    assert "PER" in rows[0]
    assert "経費率" in rows[0]
    assert "モデルの見方が割れています" in rows[0]["補足"]


def test_investment_score_display_rows_reuses_symbol_universe_lookup(monkeypatch):
    calls = 0

    def fake_symbol_universe_rows() -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return [{"symbol": "6857.T", "asset_type": "stock", "roe_pct": "25"}]

    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", fake_symbol_universe_rows)

    rows = investment_score_display_rows(
        [
            {"symbol": "6857.T", "forecast_agreement_score": "90"},
            {"symbol": "9983.T", "forecast_agreement_score": "90"},
        ]
    )

    assert len(rows) == 2
    assert calls == 1


def test_ranking_summary_cards_describe_current_screening_scope():
    rows = [
        {
            "銘柄": "7203.T",
            "総合スコア": "80",
            "DB信頼度": "90",
            "DB適合": "88",
        },
        {
            "銘柄": "6758.T",
            "総合スコア": "70",
            "DB信頼度": "65",
            "DB適合": "72",
        },
    ]

    cards = ranking_summary_cards(
        rows,
        ranking_axis="成長投資枠",
        weight_preset="バランス",
        region="日本",
        product_type="個別株",
        selected_count=10,
    )

    assert cards[0]["value"] == "10"
    assert cards[1]["value"] == "2"
    assert cards[2]["value"] == "75.0"
    assert cards[3]["value"] == "1"
    assert cards[4]["value"] == "成長投資枠"
    assert cards[5]["value"] == "日本 / 個別株"


def test_ranking_visualization_frames_skip_missing_scores():
    rows = [
        {
            "順位": "1",
            "銘柄": "7203.T",
            "銘柄名": "Toyota Motor",
            "総合スコア": "82.5",
            "DB信頼度": "88",
            "DB適合": "90",
            "注意点": "",
        },
        {
            "順位": "2",
            "銘柄": "MISS",
            "銘柄名": "Missing Score",
            "総合スコア": "",
            "DB信頼度": "91",
            "DB適合": "91",
            "注意点": "",
        },
    ]

    score_frame = ranking_score_bar_chart_frame(rows)
    confidence_frame = ranking_score_confidence_frame(rows)

    assert score_frame["symbol"].tolist() == ["7203.T"]
    assert score_frame["score"].tolist() == [82.5]
    assert score_frame.attrs["metric_column"] == "総合スコア"
    assert confidence_frame["symbol"].tolist() == ["7203.T"]
    assert confidence_frame["confidence_band"].tolist() == ["信頼度高め"]


def test_ranking_score_bar_chart_frame_uses_purpose_metric():
    rows = [
        {
            "順位": "1",
            "銘柄": "AAA",
            "銘柄名": "Alpha",
            "総合スコア": "82",
            "上昇気配": "76",
            "下降警戒": "42",
        },
        {
            "順位": "2",
            "銘柄": "BBB",
            "銘柄名": "Beta",
            "総合スコア": "80",
            "上昇気配": "70",
            "下降警戒": "44",
        },
        {
            "順位": "3",
            "銘柄": "CCC",
            "銘柄名": "Gamma",
            "総合スコア": "78",
            "上昇気配": "82",
            "下降警戒": "30",
        },
    ]

    frame = ranking_score_bar_chart_frame(
        rows,
        ranking_purpose=RANKING_PURPOSE_UPSIDE_SIGNAL,
    )

    assert frame.attrs["metric_column"] == "上昇気配"
    assert frame["symbol"].tolist() == ["CCC", "AAA", "BBB"]
    assert frame["score"].tolist() == [82.0, 76.0, 70.0]


def test_ranking_score_bar_chart_frame_uses_fit_for_etf_core_cost():
    rows = [
        {
            "順位": "1",
            "銘柄": "HIGHCOST",
            "銘柄名": "High Cost ETF",
            "総合スコア": "80",
            "経費率": "1.20",
            "条件適合度": "70",
            "データ品質": "92",
        },
        {
            "順位": "2",
            "銘柄": "LOWCOST",
            "銘柄名": "Low Cost ETF",
            "総合スコア": "78",
            "経費率": "0.10",
            "条件適合度": "92",
            "データ品質": "90",
        },
    ]

    frame = ranking_score_bar_chart_frame(
        rows,
        ranking_purpose=RANKING_PURPOSE_ETF_CORE_COST,
    )

    assert frame.attrs["metric_column"] == "条件適合度"
    assert frame["symbol"].tolist() == ["LOWCOST", "HIGHCOST"]
    assert frame["score"].tolist() == [92.0, 70.0]


def test_ranking_score_bar_chart_frame_matches_required_single_metric_sort_order():
    rows = [
        {
            "順位": "1",
            "銘柄": "AAA",
            "銘柄名": "Alpha",
            "総合スコア": "80",
            "配当利回り": "1.0%",
            "PER": "18",
            "PBR": "2.0",
            "ROE": "10%",
            "時価総額": "1000",
            "出来高": "100",
            "ボラティリティ": "20%",
            "Risk": "80",
            "データ品質": "70",
        },
        {
            "順位": "2",
            "銘柄": "BBB",
            "銘柄名": "Beta",
            "総合スコア": "70",
            "配当利回り": "4.0%",
            "PER": "8",
            "PBR": "1.0",
            "ROE": "15%",
            "時価総額": "5000",
            "出来高": "900",
            "ボラティリティ": "10%",
            "Risk": "60",
            "データ品質": "90",
        },
        {
            "順位": "3",
            "銘柄": "MISS",
            "銘柄名": "Missing",
            "総合スコア": "90",
            "配当利回り": "N/A",
            "PER": "N/A",
            "PBR": "N/A",
            "ROE": "N/A",
            "時価総額": "N/A",
            "出来高": "N/A",
            "ボラティリティ": "N/A",
            "Risk": "40",
            "データ品質": "50",
        },
    ]
    expectations = {
        RANKING_PURPOSE_SORT_TOTAL_SCORE: ("総合スコア", "desc", ["MISS", "AAA", "BBB"]),
        RANKING_PURPOSE_SORT_DIVIDEND_YIELD: ("配当利回り", "desc", ["BBB", "AAA"]),
        RANKING_PURPOSE_SORT_PER: ("PER", "asc", ["BBB", "AAA"]),
        RANKING_PURPOSE_SORT_PBR: ("PBR", "asc", ["BBB", "AAA"]),
        RANKING_PURPOSE_SORT_ROE: ("ROE", "desc", ["BBB", "AAA"]),
        RANKING_PURPOSE_SORT_MARKET_CAP: ("時価総額", "desc", ["BBB", "AAA"]),
        RANKING_PURPOSE_SORT_VOLUME: ("出来高", "desc", ["BBB", "AAA"]),
        RANKING_PURPOSE_SORT_VOLATILITY: ("ボラティリティ", "asc", ["BBB", "AAA"]),
        RANKING_PURPOSE_SORT_RISK: ("Risk", "asc", ["MISS", "BBB", "AAA"]),
        RANKING_PURPOSE_SORT_DATA_QUALITY: ("データ品質", "desc", ["BBB", "AAA", "MISS"]),
    }

    for purpose, (metric_column, sort_direction, expected_symbols) in expectations.items():
        frame = ranking_score_bar_chart_frame(rows, ranking_purpose=purpose)
        assert frame.attrs["metric_column"] == metric_column
        assert frame.attrs["sort_direction"] == sort_direction
        assert frame["symbol"].tolist() == expected_symbols


def test_ranking_score_bar_chart_caption_separates_chart_metric_from_table_sort():
    caption = ranking_score_bar_chart_caption(RANKING_PURPOSE_QUALITY_VALUE, "PER", "asc")

    assert "割安クオリティのランキング基準" in caption
    assert "代表指標「PER」" in caption
    assert "低い順" in caption
    assert "詳細テーブルの列ヘッダー" in caption
    assert "自動では切り替わりません" in caption


def test_ranking_candidate_cards_and_breakdown_use_existing_display_values():
    rows = [
        {
            "順位": "1",
            "銘柄": "7203.T",
            "銘柄名": "Toyota Motor",
            "総合スコア": "82",
            "見方": "比較候補",
            "DB信頼度": "88",
            "条件適合度": "90",
            "Screening": "79",
            "上昇気配": "76",
            "下降警戒": "42",
            "Risk": "55",
            "注意点": "確認材料あり",
            "補足": "価格と資料を確認します。",
            "根拠状態": "根拠あり",
            "根拠トーン": "success",
            "根拠補足": "AI Researchで3件の根拠を確認済みです。",
            "根拠数": "3",
            "根拠スコア": "72.00",
            "根拠信頼度": "0.6400",
            "根拠スコア注意": "1",
        }
    ]

    cards = ranking_top_candidate_cards(rows)
    breakdown = ranking_candidate_breakdown_rows(rows, "7203.T")

    assert cards[0]["symbol"] == "7203.T"
    assert cards[0]["name"] == "Toyota Motor"
    assert cards[0]["score"] == "82"
    assert cards[0]["confidence"] == "88"
    assert cards[0]["research_status"] == "根拠あり"
    card_html = _ranking_candidate_card_html(cards[0], index=0)
    assert "Toyota Motor" in card_html
    assert "総合スコア 82" in card_html
    assert [row["観点"] for row in breakdown] == [
        "投資スコア",
        "基礎評価",
        "上昇気配・下降警戒",
        "データ信頼度",
        "リスク",
        "根拠資料",
        "根拠スコア",
    ]
    assert breakdown[2]["値"] == "上昇気配 76 / 下降警戒 42"
    assert breakdown[3]["確認ポイント"] == (
        "投資魅力度ではなく、評価材料の充実度です。低い場合はスコア解釈を控えめにします。"
    )
    assert breakdown[5]["値"] == "根拠あり"
    assert breakdown[6]["値"] == "72.00"
    assert "注意点" in breakdown[6]["確認ポイント"]
    assert "confidence" not in breakdown[6]["確認ポイント"]


def test_ranking_selected_detail_memo_rows_summarize_clicked_candidate():
    rows = [
        {
            "順位": "1",
            "銘柄": "6856.T",
            "銘柄名": "Horiba",
            "総合スコア": "77.07",
            "見方": "バランス型",
            "上昇気配": "62.72",
            "下降警戒": "44.43",
            "予測変化率": "+1.17%",
            "高度予測": "+1.30%",
            "高度予測日数": "8日",
            "高度予測スコア": "58.20",
            "高度予測信頼度": "中くらい",
            "方向一致": "上昇 3 / 下降 1 / 横ばい 0",
            "PER": "14.2",
            "PBR": "1.4",
            "ROE": "11.8%",
            "配当利回り": "2.2%",
        }
    ]

    memo_rows = ranking_selected_detail_memo_rows(
        rows,
        "6856.T",
        ranking_purpose=RANKING_PURPOSE_MULTI_FACTOR,
    )

    assert [row["項目"] for row in memo_rows] == [
        "銘柄",
        "総合スコア",
        "判断方針",
        "SMAI判断",
        "予測根拠",
        "確認ポイント",
    ]
    assert memo_rows[0]["内容"] == "6856.T Horiba"
    assert memo_rows[1]["内容"] == "77.07"
    assert memo_rows[2]["内容"] == "バランス型"
    assert "上昇気配 62.72 / 下降警戒 44.43" in memo_rows[3]["内容"]
    assert "方向感は上向き" in memo_rows[3]["内容"]
    assert "+1.30%" in memo_rows[4]["内容"]
    assert "上昇 3" in memo_rows[4]["内容"]


def test_ranking_candidate_cards_fallback_when_direction_data_is_limited():
    rows = [
        {
            "順位": "1",
            "銘柄": "7203.T",
            "銘柄名": "Toyota Motor",
            "総合スコア": "82",
            "見方": "比較候補",
            "DB信頼度": "88",
            "条件適合度": "90",
            "Screening": "79",
            "上昇気配": "50",
            "下降警戒": "50",
            "方向一致": "上昇 0 / 下降 0 / 横ばい 0",
            "Risk": "55",
            "データ品質": "90",
        },
        {
            "順位": "2",
            "銘柄": "6752.T",
            "銘柄名": "Panasonic Holdings",
            "総合スコア": "71",
            "見方": "バランス型",
            "DB信頼度": "90",
            "条件適合度": "85",
            "Screening": "74",
            "上昇気配": "50",
            "下降警戒": "50",
            "方向一致": "上昇 0 / 下降 0 / 横ばい 0",
            "Risk": "62",
            "データ品質": "92",
        },
    ]

    cards = ranking_top_candidate_cards(rows, ranking_purpose=RANKING_PURPOSE_UPSIDE_SIGNAL)
    breakdown = ranking_candidate_breakdown_rows(
        rows,
        "7203.T",
        ranking_purpose=RANKING_PURPOSE_UPSIDE_SIGNAL,
    )

    assert cards[0]["primary_label"] == "総合スコア"
    assert cards[0]["primary_value"] == "82"
    assert "方向データが不足" in cards[0]["reason"]
    frame = ranking_score_bar_chart_frame(rows, ranking_purpose=RANKING_PURPOSE_UPSIDE_SIGNAL)
    assert frame.attrs["metric_column"] == "Screening"
    assert frame["score"].tolist() == [79.0, 74.0]
    assert breakdown[0]["値"] == "総合スコア 82"
    assert "方向データが不足" in breakdown[0]["確認ポイント"]


def test_ranking_display_rows_with_research_status_adds_lightweight_status_columns():
    rows = [{"銘柄": "7203.T", "銘柄名": "Toyota Motor", "総合スコア": "82"}]
    enriched = ranking_display_rows_with_research_status(
        rows,
        {
            "7203.T": RankingResearchStatus(
                label="最新資料が古い",
                tone="caution",
                note="最新資料日が2年以上前です。",
                document_count=1,
                evidence_count=2,
                latest_document_date=date(2023, 1, 1),
                research_score=Decimal("55.25"),
                research_confidence=Decimal("0.4200"),
                research_score_warning_count=1,
            )
        },
    )

    assert enriched[0]["根拠状態"] == "最新資料が古い"
    assert enriched[0]["根拠トーン"] == "caution"
    assert enriched[0]["根拠資料数"] == "1"
    assert enriched[0]["根拠数"] == "2"
    assert enriched[0]["最新資料日"] == "2023-01-01"
    assert enriched[0]["根拠スコア"] == "55.25"
    assert enriched[0]["根拠信頼度"] == "0.4200"
    assert enriched[0]["根拠スコア注意"] == "1"


def test_ranking_research_status_from_documents_marks_ready_old_and_missing():
    document = ResearchDocument(
        document_id="research-doc-1",
        symbol="7203.T",
        title="7203 Research Note",
        source_type="user_note",
        published_at=date(2026, 5, 1),
        collected_at=datetime(2026, 5, 2, tzinfo=UTC),
        local_path="data/research_docs/7203_T_note.md",
        reliability=Decimal("0.80"),
        document_hash="abc123",
    )

    ready = ranking_research_status_from_documents(
        [document],
        {"research-doc-1": [object()]},
        as_of=date(2026, 5, 25),
    )
    old = ranking_research_status_from_documents(
        [document.model_copy(update={"published_at": date(2023, 1, 1)})],
        {"research-doc-1": [object()]},
        as_of=date(2026, 5, 25),
    )
    missing = ranking_research_status_from_documents([], {}, as_of=date(2026, 5, 25))

    assert ready.label == "根拠あり"
    assert old.label == "最新資料が古い"
    assert missing.label == "根拠不足"


def test_ranking_research_status_from_report_prefers_analyzed_evidence_count():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="3件の根拠から、長期企業分析の確認材料を整理しました。",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=3,
        ),
    )

    status = ranking_research_status_from_report(report)

    assert status.label == "根拠あり"
    assert status.evidence_count == 3
    assert status.research_score == Decimal("14.29")
    assert status.research_confidence == Decimal("0")
    assert status.research_score_warning_count >= 1
    assert "3件" in status.note


def test_ranking_result_aggrid_frame_keeps_display_table_compact():
    frame = ranking_result_aggrid_frame(
        [
            {
                "順位": "1",
                "銘柄": "7203.T",
                "銘柄名": "Toyota Motor Corporation Long Name",
                "総合スコア": "82",
                "上昇気配": "78",
                "下降警戒": "42",
                "Risk": "55",
                "データ品質": "90",
                "条件適合度": "86",
                "Screening": "80",
                "DB信頼度": "88",
                "根拠状態": "根拠あり",
                "見方": "比較候補",
                "補足": "長い理由です。" * 20,
            }
        ]
    )

    assert frame.columns.tolist() == [
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
        "確認詳細",
        "並べ替え理由",
        "確認ポイント",
    ]
    assert frame.loc[0, "銘柄名"] == "Toyota Motor Corporation Long Name"
    assert frame.loc[0, "お気に入り"] in {"☆ 追加", "★ 登録済"}
    assert frame.loc[0, "株価"] == "N/A"
    assert frame.loc[0, "判断方針"] == "比較候補"
    assert frame.loc[0, "PER"] == "N/A"
    assert frame.loc[0, "PBR"] == "N/A"
    assert frame.loc[0, "ROE"] == "N/A"
    assert frame.loc[0, "配当利回り"] == "N/A"
    assert frame.loc[0, "予測確度"] == "N/A"
    assert "信頼度/根拠" not in frame.columns
    assert "Risk" not in frame.columns
    assert "データ品質" not in frame.columns
    assert "総合スコア 82" in frame.loc[0, "並べ替え理由"]
    assert frame.loc[0, "SMAIメモ"] == "上昇気配あり。下降警戒は低め。"
    assert len(frame.loc[0, "SMAIメモ"]) <= 42
    assert frame.loc[0, "確認詳細"].startswith("総合スコア 82")


def test_ranking_result_aggrid_frame_adds_detail_columns_on_request():
    frame = ranking_result_aggrid_frame(
        [
            {
                "順位": "1",
                "銘柄": "7203.T",
                "銘柄名": "Toyota Motor",
                "総合スコア": "82",
                "上昇気配": "78",
                "下降警戒": "42",
                "Risk": "55",
                "データ品質": "90",
                "条件適合度": "86",
                "Screening": "80",
                "DB信頼度": "88",
                "根拠状態": "根拠あり",
                "見方": "比較候補",
                "予測変化率": "1.25%",
                "高度予測日数": "10日",
                "高度予測スコア": "54.32",
                "高度予測信頼度": "中くらい",
                "方向一致": "上昇 2 / 下降 1 / 横ばい 1",
            }
        ],
        include_detail_columns=True,
    )

    assert frame.columns.tolist()[:17] == [
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
    ]
    assert "基礎評価" in frame.columns
    assert "リスク" in frame.columns
    assert "データ信頼度" in frame.columns
    assert "モデル方向" in frame.columns
    assert "予測根拠" in frame.columns
    assert frame.loc[0, "基礎評価"] == "80"
    assert frame.loc[0, "リスク"] == "55"
    assert frame.loc[0, "データ信頼度"] == "90"
    assert frame.loc[0, "予測確度"] == "54.32"
    assert frame.loc[0, "予測日数"] == "10日"
    assert "上昇 2" in frame.loc[0, "予測根拠"]


def test_ranking_table_renders_llm_reference_columns():
    display_rows = ranking_display_rows_with_llm_factor_references(
        [
            {
                "順位": "1",
                "銘柄": "7203.T",
                "銘柄名": "トヨタ自動車",
                "総合スコア": "82",
            }
        ],
        {
            "7203.T": LLMFactorRankingReference(
                bullish_score=Decimal("72"),
                bearish_score=Decimal("18"),
                confidence_score=Decimal("84"),
                freshness_score=Decimal("91"),
                evidence_quality_score=Decimal("80"),
                source_count=3,
                result_id="7203.T:fixture",
                source_type="cache",
            )
        },
    )

    frame = ranking_result_aggrid_frame(display_rows)
    detail_frame = ranking_result_aggrid_frame(display_rows, include_detail_columns=True)

    assert "ニュース材料" not in frame.columns
    for column in ("ニュース材料", "材料件数", "材料信頼度", "材料の新しさ"):
        assert column in detail_frame.columns
    assert detail_frame.loc[0, "ニュース材料"] == "強気 72 / 弱気 18"
    assert detail_frame.loc[0, "材料件数"] == "3"
    assert detail_frame.loc[0, "材料信頼度"] == "84"
    assert detail_frame.loc[0, "材料の新しさ"] == "91"


def test_llm_reference_disclaimer_is_visible():
    assert "ニュース材料はAI要約による参考情報" in LLM_FACTOR_RANKING_REFERENCE_NOTICE
    assert "売買推奨ではありません" in LLM_FACTOR_RANKING_REFERENCE_NOTICE
    assert "ランキング順位には反映していません" in LLM_FACTOR_RANKING_REFERENCE_NOTICE


def test_format_llm_factor_score():
    assert format_llm_factor_score(Decimal("0.734")) == "73"
    assert format_llm_factor_score(Decimal("1.0")) == "100"
    assert format_llm_factor_score(Decimal("0.0")) == "0"
    assert format_llm_factor_score(Decimal("73.4")) == "73"
    assert format_llm_factor_score(None) == "—"
    assert format_llm_factor_score(float("nan")) == "—"
    assert format_llm_factor_score("invalid") == "—"


def test_ranking_default_order_is_unchanged_with_llm_columns():
    display_rows = ranking_display_rows_with_llm_factor_references(
        [
            {"順位": "1", "銘柄": "AAA", "銘柄名": "Alpha", "総合スコア": "90"},
            {"順位": "2", "銘柄": "BBB", "銘柄名": "Beta", "総合スコア": "80"},
        ],
        {
            "AAA": LLMFactorRankingReference(
                bullish_score=Decimal("10"),
                bearish_score=Decimal("90"),
                confidence_score=Decimal("60"),
                freshness_score=Decimal("60"),
                source_type="cache",
            ),
            "BBB": LLMFactorRankingReference(
                bullish_score=Decimal("99"),
                bearish_score=Decimal("1"),
                confidence_score=Decimal("60"),
                freshness_score=Decimal("60"),
                source_type="cache",
            ),
        },
    )

    frame = ranking_result_aggrid_frame(display_rows)
    detail_frame = ranking_result_aggrid_frame(display_rows, include_detail_columns=True)

    assert frame["銘柄"].tolist() == ["AAA", "BBB"]
    assert frame["順位"].tolist() == ["1", "2"]
    assert detail_frame["銘柄"].tolist() == ["AAA", "BBB"]
    assert detail_frame["順位"].tolist() == ["1", "2"]


def test_llm_columns_do_not_change_rank_labels():
    display_rows = ranking_display_rows_with_llm_factor_references(
        [{"順位": "3", "銘柄": "AAPL", "銘柄名": "Apple", "総合スコア": "70"}],
        {
            "AAPL": LLMFactorRankingReference(
                bullish_score=Decimal("100"),
                bearish_score=Decimal("0"),
                confidence_score=Decimal("80"),
                freshness_score=Decimal("80"),
                source_type="cache",
            )
        },
    )

    frame = ranking_result_aggrid_frame(display_rows)
    detail_frame = ranking_result_aggrid_frame(display_rows, include_detail_columns=True)

    assert display_rows[0]["順位"] == "3"
    assert frame.loc[0, "順位"] == "3"
    assert detail_frame.loc[0, "順位"] == "3"


def test_missing_llm_reference_renders_dash():
    display_rows = ranking_display_rows_with_llm_factor_references(
        [{"順位": "1", "銘柄": "MISS", "銘柄名": "Missing", "総合スコア": "50"}],
        {},
    )

    frame = ranking_result_aggrid_frame(display_rows, include_detail_columns=True)

    assert frame.loc[0, "ニュース材料"] == "強気 — / 弱気 —"
    assert frame.loc[0, "材料件数"] == "—"
    assert frame.loc[0, "材料信頼度"] == "—"
    assert frame.loc[0, "材料の新しさ"] == "—"


def test_no_buy_sell_recommendation_text_in_llm_column_labels():
    display = build_llm_factor_reference_display(
        LLMFactorRankingReference(
            bullish_score=Decimal("72"),
            bearish_score=Decimal("18"),
            confidence_score=Decimal("84"),
            freshness_score=Decimal("91"),
            source_type="cache",
        )
    )
    visible_text = " ".join(
        [
            "ニュース材料",
            "材料件数",
            "材料信頼度",
            "材料の新しさ",
            *LLM_FACTOR_RANKING_COLUMN_TOOLTIPS.values(),
            display["bullishAriaLabel"],
            display["bearishAriaLabel"],
            display["confidenceAriaLabel"],
            display["freshnessAriaLabel"],
        ]
    )

    for forbidden in ("買い", "売り", "Strong Buy", "Strong Sell", "Buy", "Sell"):
        assert forbidden not in visible_text


def test_llm_reference_tooltip_or_aria_label_mentions_reference():
    display = build_llm_factor_reference_display(
        LLMFactorRankingReference(
            bullish_score=Decimal("72"),
            bearish_score=Decimal("18"),
            confidence_score=Decimal("84"),
            freshness_score=Decimal("91"),
            source_type="cache",
        )
    )

    assert "参考値" in LLM_FACTOR_RANKING_COLUMN_TOOLTIPS["ニュース材料"]
    assert display["bullishAriaLabel"] == "ニュース材料（強気） 72点 参考指標"


def test_llm_columns_are_not_sortable_first_slice():
    display_rows = ranking_display_rows_with_llm_factor_references(
        [{"順位": "1", "銘柄": "7203.T", "銘柄名": "トヨタ自動車", "総合スコア": "82"}],
        {
            "7203.T": LLMFactorRankingReference(
                bullish_score=Decimal("72"),
                bearish_score=Decimal("18"),
                confidence_score=Decimal("84"),
                freshness_score=Decimal("91"),
                source_type="cache",
            )
        },
    )
    options = ranking_result_aggrid_options(
        ranking_result_aggrid_frame(display_rows, include_detail_columns=True),
    )
    column_defs = {column["field"]: column for column in options["columnDefs"]}

    for column in ("ニュース材料", "材料件数", "材料信頼度", "材料の新しさ"):
        assert column_defs[column]["sortable"] is False
        assert "comparator" not in column_defs[column]


def test_ranking_display_rows_surface_advanced_forecast_as_auxiliary_context(monkeypatch):
    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", lambda: [])
    display_rows = investment_score_display_rows(
        [
            {
                "rank": "1",
                "symbol": "AAPL",
                "total_score": "82",
                "score_band": "BALANCED",
                "screening_score": "80",
                "upside_signal_score": "78",
                "downside_signal_score": "42",
                "forecast_return_pct": "1.1%",
                "advanced_forecast_horizon_days": "10",
                "advanced_forecast_predicted_return": "1.25%",
                "advanced_forecast_score": "54.32",
                "advanced_forecast_confidence": "medium",
                "data_quality_score": "90",
                "metadata_confidence_score": "88",
                "risk_signal_score": "55",
            }
        ]
    )

    frame = ranking_result_aggrid_frame(display_rows)
    detail_frame = ranking_result_aggrid_frame(display_rows, include_detail_columns=True)
    detail_rows = ranking_score_detail_rows(display_rows[0])
    breakdown = ranking_candidate_breakdown_rows(display_rows, "AAPL")

    assert display_rows[0]["高度予測"] == "1.25%"
    assert display_rows[0]["高度予測日数"] == "10日"
    assert display_rows[0]["高度予測スコア"] == "54.32"
    assert display_rows[0]["高度予測信頼度"] == "中くらい"
    assert "高度予測" not in frame.columns
    assert "高度予測日数" not in frame.columns
    assert "高度予測スコア" not in frame.columns
    assert frame.loc[0, "予測変化率"] == "1.1%"
    assert frame.loc[0, "予測確度"] == "54.32"
    assert detail_frame.loc[0, "予測日数"] == "10日"
    assert detail_frame.loc[0, "モデル方向"] == "上昇 0 / 下降 0 / 横ばい 0"
    assert "1.25%" in detail_frame.loc[0, "予測根拠"]
    assert "54.32" in detail_frame.loc[0, "予測根拠"]
    assert any(row["観点"] == "AI予測インサイト" for row in detail_rows)
    assert [row["観点"] for row in detail_rows][2] == "AI予測インサイト"
    assert [row["観点"] for row in breakdown][3] == "AI予測インサイト"
    assert any(
        row["観点"] == "AI予測インサイト"
        and "10日 1.25%" in row["値"]
        and "スコア 54.32" in row["値"]
        for row in breakdown
    )
    assert "AI予測インサイト" in frame.loc[0, "並べ替え理由"]
    assert "25%" in frame.loc[0, "並べ替え理由"]


def test_ranking_advanced_forecast_rows_use_common_period_horizon():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = [
        _bar((start + timedelta(days=index)).date().isoformat(), close=100 + index)
        for index in range(90)
    ]

    rows = _advanced_forecast_rows_for_ranking(bars, horizon_days=10)
    fields = _ranking_advanced_forecast_fields(rows)

    assert {row["adapter"] for row in rows} == {
        "advanced_linear",
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
        "advanced_quantile",
    }
    assert {row["horizon_days"] for row in rows} == {"10"}
    assert (
        fields["advanced_forecast_model"]
        == "advanced_linear,advanced_tree_sklearn,advanced_gbdt_sklearn,advanced_quantile"
    )
    assert fields["advanced_forecast_horizons"] == "10"
    assert fields["advanced_forecast_horizon_days"] == "10"
    assert fields["advanced_forecast_predicted_return"]
    assert fields["advanced_forecast_score"]


def test_ranking_advanced_forecast_fields_use_consensus_when_available():
    advanced_rows = [
        {
            "adapter": "advanced_linear",
            "horizon_days": "10",
            "predicted_return": "9.00%",
            "direction_score": "90.00%",
            "confidence": "high",
        },
        {
            "adapter": "advanced_quantile",
            "horizon_days": "10",
            "predicted_return": "-1.00%",
            "direction_score": "40.00%",
            "confidence": "low",
        },
    ]
    consensus_rows = [
        {
            "horizon_days": "10",
            "predicted_return": "2.50%",
            "predicted_return_lower": "-1.00%",
            "predicted_return_upper": "4.00%",
            "weighted_direction_score": "61.25%",
            "confidence": "medium",
            "agreement": "MEDIUM",
        }
    ]

    fields = _ranking_advanced_forecast_fields(advanced_rows, consensus_rows)

    assert fields["advanced_forecast_model"] == "advanced_linear,advanced_quantile"
    assert fields["advanced_forecast_horizon_days"] == "10"
    assert fields["advanced_forecast_predicted_return"] == "+2.5%"
    assert fields["advanced_forecast_score"] == "61.25"
    assert fields["advanced_forecast_upside_score"]
    assert fields["advanced_forecast_downside_score"]
    assert fields["advanced_forecast_quality_score"]
    assert fields["advanced_forecast_confidence"] == "medium"
    assert fields["advanced_forecast_range"] == "-1%〜+4%"
    assert fields["advanced_forecast_agreement"] == "MEDIUM"


def test_advanced_forecast_ranking_signal_fields_neutralize_low_quality():
    strong_low_quality = _advanced_forecast_ranking_signal_fields(
        {
            "predicted_return": "8%",
            "predicted_return_lower": "-12%",
            "weighted_direction_score": "92%",
            "confidence": "low",
            "agreement": "LOW",
            "direction_agreement_score": "50",
            "mean_direction_accuracy": "48%",
            "mean_rmse_improvement": "-0.02",
        }
    )

    assert Decimal(strong_low_quality["advanced_forecast_upside_score"]) < Decimal("80")
    assert Decimal(strong_low_quality["advanced_forecast_downside_score"]) > Decimal("70")
    assert Decimal(strong_low_quality["advanced_forecast_quality_score"]) < Decimal("60")


def test_ranking_display_rows_hide_advanced_forecast_when_not_available(monkeypatch):
    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", lambda: [])
    display_rows = investment_score_display_rows(
        [
            {
                "rank": "1",
                "symbol": "AAPL",
                "total_score": "82",
                "score_band": "BALANCED",
                "screening_score": "80",
                "upside_signal_score": "78",
                "downside_signal_score": "42",
                "forecast_return_pct": "1.1%",
                "data_quality_score": "90",
                "metadata_confidence_score": "88",
                "risk_signal_score": "55",
            }
        ]
    )

    frame = ranking_result_aggrid_frame(display_rows)
    detail_rows = ranking_score_detail_rows(display_rows[0])
    breakdown = ranking_candidate_breakdown_rows(display_rows, "AAPL")

    assert display_rows[0]["高度予測"] == "N/A"
    assert display_rows[0]["高度予測スコア"] == "N/A"
    assert "高度予測" not in frame.columns
    assert "高度予測スコア" not in frame.columns
    assert not any(row["観点"] == "AI予測インサイト" for row in detail_rows)
    assert not any(row["観点"] == "AI予測インサイト" for row in breakdown)


def test_ranking_result_aggrid_frame_prioritizes_upside_columns_for_upside_purpose():
    frame = ranking_result_aggrid_frame(
        [
            {
                "順位": "1",
                "銘柄": "7203.T",
                "銘柄名": "Toyota Motor",
                "総合スコア": "82",
                "Screening": "80",
                "上昇気配": "78",
                "下降警戒": "42",
                "予測変化率": "+3.2%",
                "方向一致": "上昇 3 / 下降 0 / 横ばい 0",
                "Risk": "55",
                "データ品質": "90",
            }
        ],
        ranking_purpose=RANKING_PURPOSE_UPSIDE_SIGNAL,
    )

    assert frame.columns.tolist()[:17] == [
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
    ]
    assert "モデル方向" not in frame.columns
    assert "上昇気配 78" in frame.loc[0, "並べ替え理由"]


def test_ranking_result_aggrid_frame_moves_confidence_columns_to_detail_mode():
    rows = [
        {
            "順位": "1",
            "銘柄": "7203.T",
            "銘柄名": "Toyota Motor",
            "総合スコア": "82",
            "データ品質": "90",
            "DB信頼度": "88",
            "条件適合度": "86",
            "根拠状態": "根拠あり",
            "注意点": "",
            "Risk": "55",
        }
    ]
    normal_frame = ranking_result_aggrid_frame(
        rows,
        ranking_purpose=RANKING_PURPOSE_DATA_CONFIDENCE,
    )
    frame = ranking_result_aggrid_frame(
        rows,
        ranking_purpose=RANKING_PURPOSE_DATA_CONFIDENCE,
        include_detail_columns=True,
    )

    assert "信頼度/根拠" not in normal_frame.columns
    assert "データ信頼度" not in normal_frame.columns
    assert "信頼度/根拠" in frame.columns
    assert frame.columns.tolist()[:17] == [
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
    ]
    assert "データ信頼度" in frame.columns
    assert "DB信頼度" in frame.columns
    assert "根拠状態" in frame.columns
    assert "条件適合度" in frame.columns
    assert "注意点" in frame.columns


def test_ranking_result_aggrid_frame_keeps_zero_and_missing_fundamentals_distinct():
    frame = ranking_result_aggrid_frame(
        [
            {
                "順位": "1",
                "銘柄": "ZERO",
                "銘柄名": "Zero Dividend",
                "総合スコア": "70",
                "配当利回り": "0%",
                "PER": "",
                "PBR": "-",
                "ROE": "未登録",
                "見方": "比較候補",
            }
        ]
    )

    assert frame.loc[0, "配当利回り"] == "0%"
    assert frame.loc[0, "PER"] == "N/A"
    assert frame.loc[0, "PBR"] == "N/A"
    assert frame.loc[0, "ROE"] == "N/A"


def test_investment_score_display_rows_keeps_feature_dividend_yield_as_percent(monkeypatch):
    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", lambda: [])
    feature = DailySnapshot(
        symbol="6479.T",
        as_of=date(2026, 6, 1),
        last=Decimal("3200"),
        close_1d=Decimal("3180"),
        dividend_yield=Decimal("0.0132"),
        missing={},
    )

    enriched = _enrich_ranking_rows_with_feature_details(
        [{"rank": "1", "symbol": "6479.T", "total_score": "72"}],
        [feature],
        provider_name="yahoo",
    )
    display_rows = investment_score_display_rows(enriched)

    assert enriched[0]["dividend_yield_pct"] == "1.32"
    assert display_rows[0]["配当利回り"] == "1.32%"


def test_investment_score_display_rows_marks_abnormal_dividend_yield(monkeypatch):
    symbol_rows = [
        {
            "symbol": "GMEX",
            "asset_type": "stock",
            "dividend_yield_pct": "293.19",
            "per": "12",
            "pbr": "1.1",
            "roe_pct": "8",
        }
    ]
    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", lambda: symbol_rows)

    display_rows = investment_score_display_rows(
        [{"rank": "1", "symbol": "GMEX", "total_score": "72"}]
    )
    frame = ranking_result_aggrid_frame(display_rows)
    detail_rows = ranking_score_detail_rows(display_rows[0])

    assert display_rows[0]["配当利回り"] == "要確認"
    assert frame.loc[0, "配当利回り"] == "要確認"
    assert any("配当利回り 要確認" in row["内容"] for row in detail_rows)


def test_investment_score_display_rows_shows_missing_dividend_yield_as_na(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [{"symbol": "NODIV", "asset_type": "stock", "dividend_yield_pct": ""}],
    )

    display_rows = investment_score_display_rows(
        [{"rank": "1", "symbol": "NODIV", "total_score": "72"}]
    )

    assert display_rows[0]["配当利回り"] == "N/A"


def test_investment_score_display_rows_marks_abnormal_per_pbr(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "BA",
                "asset_type": "stock",
                "per": "0",
                "pbr": "0",
                "roe_pct": "0",
            }
        ],
    )

    display_rows = investment_score_display_rows(
        [{"rank": "1", "symbol": "BA", "total_score": "72"}]
    )

    assert display_rows[0]["PER"] == "要確認"
    assert display_rows[0]["PBR"] == "要確認"
    assert display_rows[0]["ROE"] == "0%"


def test_ranking_investment_note_uses_scores_and_symbol_metadata(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "6857.T",
                "asset_type": "stock",
                "per": "52.42",
                "pbr": "28.93",
                "roe_pct": "57.65",
                "dividend_yield_pct": "0.23",
            }
        ],
    )

    note = ranking_investment_note(
        {
            "symbol": "6857.T",
            "screening_score": "88",
            "direction_net_score": "76",
            "upside_signal_score": "82",
            "downside_signal_score": "35",
            "data_quality_score": "100",
            "risk_signal_score": "60",
            "warnings": "",
        }
    )

    assert "上昇気配" in note
    assert "方向感" not in note
    assert "PER/PBR" in note
    assert "成長期待" in note


def test_ranking_investment_detail_rows_adds_modal_guidance():
    rows = ranking_investment_detail_rows(
        {
            "総合スコア": "84.69",
            "上昇気配": "82",
            "下降警戒": "35",
            "データ品質": "100",
            "Risk": "72.44",
            "注意点": "",
            "補足": "上昇気配とデータ品質が強みの候補です。",
        },
        {
            "asset_type": "stock",
            "dividend_yield_pct": "0.23",
            "dividend_category": "dividend",
            "per": "52.42",
            "pbr": "28.93",
            "roe_pct": "57.65",
        },
    )

    assert rows[0]["観点"] == "ランキング上位理由"
    assert any(row["観点"] == "バリュエーション" and "PER" in row["内容"] for row in rows)
    assert any(row["観点"] == "スコア内訳" and "データ品質 100" in row["内容"] for row in rows)
    assert any(row["観点"] == "基礎指標" and "配当利回り" in row["内容"] for row in rows)
    assert rows[-1]["確認ポイント"] == "売買推奨ではなく、深掘り順と確認観点の整理です。"


def test_ranking_score_detail_rows_show_missing_as_na():
    rows = ranking_score_detail_rows(
        {
            "総合スコア": "82",
            "見方": "比較候補",
            "Screening": "80",
            "上昇気配": "76",
            "下降警戒": "42",
            "Risk": "55",
            "データ品質": "90",
            "配当利回り": "N/A",
            "PER": "N/A",
            "PBR": "1.2",
            "ROE": "12%",
            "取得元": "yahoo",
            "取得日時": "2026-06-01",
            "欠損項目": "dividend_yield",
        }
    )

    assert rows[1]["観点"] == "スコア内訳"
    assert rows[2]["観点"] == "評価材料の信頼度"
    assert "投資魅力度ではなく" in rows[2]["確認ポイント"]
    assert "PER N/A" in rows[3]["内容"]
    assert "欠損 dividend_yield" in rows[4]["確認ポイント"]


def test_investment_score_summary_lines_explain_score_without_recommendation():
    lines = investment_score_summary_lines(
        {
            "銘柄": "AAPL",
            "見方": "バランス型",
            "注意点": "モデルの見方が割れています",
            "補足": "売買推奨ではなく、判断材料を整理したスコアです。",
        }
    )

    assert lines == [
        "AAPL は「バランス型」として確認できます。",
        "注意点: モデルの見方が割れています。",
        "売買推奨ではなく、判断材料を整理したスコアです。",
    ]


def test_score_component_rows_builds_cockpit_breakdown():
    assert score_component_rows(
        {
            "Screening": "80",
            "上昇気配": "68",
            "下降警戒": "42",
            "モデル一致度": "64",
            "Risk": "70",
            "データ品質": "100",
        }
    ) == [
        {
            "要素": "スクリーニング",
            "スコア": "80",
            "読み方": "市場データ由来の候補評価です。投資スコアの一部で、単独の売買判断には使いません。",
        },
        {
            "要素": "上昇気配",
            "スコア": "68",
            "読み方": "予測と直近値動きから見た上向き材料の確認値です。上昇を保証する値ではありません。",
        },
        {
            "要素": "下降警戒",
            "スコア": "42",
            "読み方": "下向き材料の警戒値です。売り指示ではなく、高いほど追加確認します。",
        },
        {
            "要素": "予測・モデル一致",
            "スコア": "64",
            "読み方": "予測モデルの見方がどの程度近いかを見る補助材料です。的中率や将来保証ではありません。",
        },
        {
            "要素": "リスク確認",
            "スコア": "70",
            "読み方": "価格変動や下落幅を確認する材料で、安全保証ではありません。",
        },
        {
            "要素": "データ品質",
            "スコア": "100",
            "読み方": "評価に使える価格・特徴量データの充実度です。投資魅力度ではありません。",
        },
    ]


def test_score_confidence_hierarchy_rows_distinguish_score_roles():
    rows = score_confidence_hierarchy_rows()

    research_row = next(row for row in rows if row["表示"] == "Research Score")
    forecast_row = next(row for row in rows if row["表示"] == "Forecast / 予測")
    risk_row = next(row for row in rows if row["表示"] == "リスク確認")
    llm_row = next(row for row in rows if row["表示"] == "LLM材料（参考）")
    confidence_row = next(row for row in rows if row["表示"] == "条件適合度 / DB信頼度")

    assert "総合スコアやランキング順位を変えません" in research_row["順位への影響"]
    assert "根拠確認不足" in research_row["読み方"]
    assert "確定未来ではなく" in forecast_row["読み方"]
    assert "安全保証ではなく" in risk_row["読み方"]
    assert "総合スコア、ランキング順位、Forecast、Investment Scoreには反映しません" in (
        llm_row["順位への影響"]
    )
    assert "投資魅力度ではなく" in confidence_row["読み方"]


def test_ranking_criteria_guide_rows_render_as_wrapping_table():
    rows = [dict(row) for row in RANKING_CRITERIA_GUIDE_ROWS]

    table_html = symbol_detail_table_html(rows)

    assert "symbol-detail-table" in table_html
    assert "ランキング基準" in table_html
    assert "詳細条件" in table_html
    assert "条件適合度" in table_html
    assert "DB信頼度" in table_html
    assert "NISA" in table_html
    assert "配当 / 分配金" in table_html
    assert "投資魅力度ではなく" in table_html
    assert "万能評価や商品適合性" in table_html


def test_ranking_forecast_term_explanation_rows_cover_ai_signals():
    rows = ranking_forecast_term_explanation_rows()
    labels = {row["表示"] for row in rows}

    assert {
        "AI総合",
        "上昇気配",
        "下降警戒",
        "AI予測インサイト",
        "高度予測上昇",
        "高度予測下振れ警戒",
        "高度予測信頼",
        "予測日数",
    } <= labels
    downside_row = next(row for row in rows if row["表示"] == "下降警戒")
    advanced_quality_row = next(row for row in rows if row["表示"] == "高度予測信頼")
    assert "低いほど良い" in downside_row["ランキングでの扱い"]
    assert "投資魅力度ではなく" in advanced_quality_row["確認ポイント"]


def test_ranking_weight_group_rows_summarize_ai_composite_profile():
    rows = ranking_weight_group_rows(RANKING_PRESET_MULTI_FACTOR)

    assert rows == [
        {"group": "基礎評価", "weight": "30%"},
        {"group": "予測・上昇気配", "weight": "30%"},
        {"group": "リスク・下振れ警戒", "weight": "25%"},
        {"group": "データ信頼度", "weight": "10%"},
        {"group": "Research確認材料", "weight": "5%"},
    ]


def test_ranking_condition_card_html_explains_common_horizon_and_ai_weighting():
    markup = _ranking_condition_card_html(
        RANKING_PURPOSE_MULTI_FACTOR,
        RANKING_PRESET_MULTI_FACTOR,
        forecast_horizon_days=31,
    )

    assert "今回のランキング条件" in markup
    assert "ランキング評価用予測期間" in markup
    assert "31日" in markup
    assert "同じランキング内では共通の予測期間で比較します" in markup
    assert "AI予測インサイトは順位を直接支配せず" in markup
    assert "予測・上昇気配" in markup
    assert "30%" in markup
    assert "下降警戒は低いほど良い指標です" in markup
    assert "警戒が低いほど加点" in markup
    assert "売買推奨ではありません" in markup


def test_reversal_condition_card_explains_formula_and_guardrails():
    markup = _ranking_condition_card_html(
        RANKING_PURPOSE_REVERSAL_EXPECTATION,
        RANKING_PRESET_REVERSAL_EXPECTATION,
        forecast_horizon_days=20,
    )
    components = reversal_expectation_component_rows()
    pullbacks = reversal_expectation_pullback_rows()
    caps = reversal_expectation_cap_rows()

    assert "上向き兆候をひとことで" in markup
    assert "チャート形状 35%" in markup
    assert "予測上向き余地 25%" in markup
    assert "上限固定ではなく段階的に減点" in markup
    assert [row["配点"] for row in components] == [
        "35%",
        "25%",
        "20%",
        "10%",
        "10%",
    ]
    assert next(row for row in pullbacks if row["基礎点"] == "90")["20日高値からの下落"] == (
        "6%以上〜12%未満"
    )
    assert any(row["危険条件"] == "下降警戒 70以上" and row["扱い"] == "-6〜-18点" for row in caps)
    assert any(row["危険条件"] == "データ品質BLOCK" and row["扱い"] == "未評価" for row in caps)


def test_ranking_condition_summary_chips_show_default_builder_state():
    chips = ranking_condition_summary_chips_from_values(
        {},
        region="japan",
        product_type="stock",
        ranking_policy=RANKING_PURPOSE_MULTI_FACTOR,
        period_preset="standard",
        candidate_count=9197,
    )

    assert [chip["label"] for chip in chips] == [
        "国内",
        "株式",
        "AI総合",
        "標準: 3か月",
        "詳細条件なし",
        "候補 9,197件",
    ]
    assert chips[2]["tone"] == "policy"
    assert chips[-1]["tone"] == "count"
    assert not ranking_condition_has_active_detail_from_values({})


def test_ranking_condition_summary_chips_surface_active_detail_conditions():
    values = {
        "market_data_ranking_nisa": "eligible",
        "market_data_ranking_dividend": "high_dividend",
        "market_data_ranking_per_enabled": True,
        "market_data_ranking_per_min": "10.0",
        "market_data_ranking_per_max": "20.0",
        "market_data_ranking_symbol_query": "半導体",
    }

    chips = ranking_condition_summary_chips_from_values(
        values,
        region="japan",
        product_type="stock",
        ranking_policy=RANKING_PURPOSE_MULTI_FACTOR,
        period_preset="standard",
        candidate_count=248,
    )
    labels = [chip["label"] for chip in chips]

    assert "NISA対象" in labels
    assert "配当利回り 3%以上" in labels
    assert "PER 10-20" in labels
    assert "検索: 半導体" in labels
    assert "詳細条件なし" not in labels
    assert chips[-1] == {"label": "候補 248件", "tone": "count"}
    assert ranking_condition_has_active_detail_from_values(values)


def test_ranking_condition_summary_chips_html_escapes_labels():
    markup = ranking_condition_summary_chips_html(
        [{"label": "<script>bad</script>", "tone": "active"}]
    )

    assert "&lt;script&gt;bad&lt;/script&gt;" in markup
    assert "<script>bad</script>" not in markup
    assert "smai-ranking-condition-chip--active" in markup


def test_ranking_condition_summary_html_is_embedded_in_condition_builder():
    markup = _ranking_condition_summary_html(
        {},
        region="japan",
        product_type="stock",
        ranking_policy=RANKING_PURPOSE_MULTI_FACTOR,
        period_preset="standard",
        candidate_count=9197,
    )

    assert "smai-ranking-builder-head" in markup
    assert "smai-ranking-current-conditions" not in markup
    assert "ランキング候補" in markup
    assert "現在の条件" in markup
    assert "候補 9,197件" in markup


def test_ranking_condition_summary_html_softly_warns_for_medium_build_target():
    markup = _ranking_condition_summary_html(
        {},
        region="japan",
        product_type="stock",
        ranking_policy=RANKING_PURPOSE_MULTI_FACTOR,
        period_preset="standard",
        candidate_count=9197,
        load_state=ranking_condition_load_state(300),
    )

    assert "smai-ranking-builder-head--load-caution" in markup
    assert "候補 9,197件：候補が少し多めです" in markup
    assert "作成に少し時間がかかる場合があります。" in markup


def test_ranking_policy_builder_card_html_summarizes_policy_weights():
    markup = ranking_policy_builder_card_html(
        RANKING_PURPOSE_MULTI_FACTOR,
        RANKING_PRESET_MULTI_FACTOR,
    )

    assert "ランキング基準" in markup
    assert "AI総合" in markup
    assert "基礎評価" in markup
    assert "30%" in markup
    assert "上位銘柄は、まず詳しく確認したい候補として見てください。" in markup


def test_reversal_policy_builder_card_explains_formula_without_opening_details():
    markup = ranking_policy_builder_card_html(
        RANKING_PURPOSE_REVERSAL_EXPECTATION,
        RANKING_PRESET_REVERSAL_EXPECTATION,
    )

    assert "計算の考え方" in markup
    assert "下がっただけでは評価せず" in markup
    assert "押し目状態" in markup
    assert "予測上向き余地" in markup
    assert "下落安全性" in markup
    assert "上向き材料" in markup
    assert "チャート形状" in markup
    assert "上向き材料" in markup
    assert "25%" in markup
    assert "5%" in markup
    assert "20%" in markup
    assert "10%" in markup
    assert "最終スコアに上限" in markup
    assert "上位は反発の断定ではなく" in markup
    assert "計算式：" not in markup


def test_ranking_creation_target_summary_html_explains_effective_target_count():
    markup = ranking_creation_target_summary_html(
        candidate_count=9197,
        selected_count=9197,
        effective_count=300,
        fetch_limit_label="標準: 上位300件",
        ranking_policy=RANKING_PURPOSE_MULTI_FACTOR,
        period_preset="standard",
        provider="yahoo",
        has_detail_conditions=True,
    )
    empty_markup = ranking_creation_target_summary_html(
        candidate_count=0,
        selected_count=0,
        effective_count=0,
        fetch_limit_label="標準: 上位300件",
        ranking_policy=RANKING_PURPOSE_MULTI_FACTOR,
        period_preset="standard",
        provider="yahoo",
        has_detail_conditions=False,
    )

    assert "候補 9,197件から、300件を作成します" in markup
    assert "ランキング基準: AI総合" in markup
    assert "期間: 標準: 3か月" in markup
    assert "取得元: yahoo" in markup
    assert "詳細条件あり" in markup
    assert "現在の条件では候補がありません" in empty_markup
    assert "smai-ranking-target-summary--warning" in empty_markup


def test_render_score_confidence_hierarchy_uses_wrapping_html_table(monkeypatch):
    markdown_calls: list[str] = []

    def fake_markdown(body: str, **_: object) -> None:
        markdown_calls.append(body)

    monkeypatch.setattr("ui.app.st.markdown", fake_markdown)

    _render_score_confidence_hierarchy()

    table_html = markdown_calls[-1]
    assert "symbol-detail-table" in table_html
    assert "Forecast / 予測" in table_html
    assert "Research Score" in table_html
    assert "安全保証ではなく" in table_html
    assert "既定では総合スコアやランキング順位を変えません" in table_html
    assert "投資魅力度ではなく" in table_html


def test_cockpit_detail_summary_rows_lift_key_closed_details():
    preview = MarketDataPreview(
        status="ok",
        bars=[_bar("2026-05-01", close=100), _bar("2026-05-02", close=105)],
        provider_rows=[],
        quote_rows=[
            {
                "symbol": "AAPL",
                "exchange": "NASDAQ",
                "bid": "-",
                "ask": "-",
                "last": "105",
                "ts": "2026-05-02T00:00:00+00:00",
            }
        ],
        ohlcv_rows=[
            {
                "symbol": "AAPL",
                "bars": "2",
                "first_ts": "2026-05-01T00:00:00+00:00",
                "last_ts": "2026-05-02T00:00:00+00:00",
                "total_volume": "2000",
            }
        ],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[
            {
                "return_1d": "5%",
                "momentum_5d": "8%",
                "drawdown_20d": "-3%",
                "data_completeness": "100%",
                "data_quality": "OK",
                "missing_summary": "なし",
            }
        ],
        investment_score_rows=[],
        screening_rows=[
            {
                "total_score": "82",
                "momentum_score": "75",
                "liquidity_score": "90",
                "risk_score": "70",
                "summary": "モメンタムと流動性が確認できます。",
            }
        ],
        error_rows=[],
    )

    rows = cockpit_detail_summary_rows(
        preview,
        [
            {
                "ensemble_forecast_close": "108",
                "min_forecast_close": "102",
                "max_forecast_close": "112",
                "forecast_range_pct": "9.5%",
            }
        ],
        [{"model": "moving_average", "rmse": "1.2", "sample_count": "5"}],
    )

    assert [row["観点"] for row in rows] == [
        "直近価格",
        "取得期間",
        "予測レンジ",
        "スクリーニング",
        "短期特徴量",
        "データ品質",
        "予測評価",
    ]
    assert "105" in rows[0]["内容"]
    assert "2本" in rows[1]["内容"]
    assert "9.5%" in rows[2]["内容"]
    assert rows[3]["確認ポイント"] == "モメンタムと流動性が確認できます。"


def test_cockpit_period_evaluation_rows_change_by_period_length():
    short_rows = cockpit_period_evaluation_rows(
        [_bar("2026-05-01", close=100), _bar("2026-05-08", close=108)]
    )
    long_rows = cockpit_period_evaluation_rows(
        [_bar("2023-05-01", close=100), _bar("2026-05-01", close=130)]
    )

    assert short_rows[0]["見方"] == "7日間 / 短期反応の確認"
    assert "ノイズ" in short_rows[0]["確認ポイント"]
    assert short_rows[1]["見方"] == "+8.0% / 上昇優位"
    assert short_rows[2]["見方"] == "期間レンジ内 100.0% / 高値圏"
    assert long_rows[0]["見方"] == "1096日間 / 長期耐性の確認"
    assert "複数決算期" in long_rows[0]["確認ポイント"]


def test_cockpit_investment_memo_rows_combines_score_master_and_price(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "6857.T",
                "asset_type": "stock",
                "dividend_yield_pct": "0.23",
                "dividend_category": "dividend",
                "per": "52.42",
                "pbr": "28.93",
                "roe_pct": "57.65",
            }
        ],
    )
    preview = MarketDataPreview(
        status="ok",
        bars=[
            _bar("2026-05-01", close=100, symbol="6857.T"),
            _bar("2026-05-02", close=112, symbol="6857.T"),
        ],
        provider_rows=[],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[],
        screening_rows=[],
        error_rows=[],
    )

    rows = cockpit_investment_memo_rows(
        preview,
        {
            "銘柄": "6857.T",
            "総合スコア": "84.69",
            "見方": "強め",
            "Screening": "78.9",
            "上昇気配": "82",
            "下降警戒": "35",
            "データ品質": "100",
            "Risk": "72.44",
            "注意点": "",
        },
    )

    assert [row["観点"] for row in rows] == [
        "スコア解釈",
        "主な注意点",
        "バリュエーション",
        "インカム",
        "価格トレンド",
        "次の確認",
    ]
    assert "上昇気配が比較的強く" in rows[0]["評価"]
    assert "PER 52.42" in rows[2]["評価"]
    assert "配当利回り 0.23%" in rows[3]["評価"]
    assert "高値圏" in rows[4]["評価"]
    assert rows[0]["確認ポイント"] == "スコアは深掘り順の整理で、売買推奨ではありません。"


def test_decision_report_download_buttons_explain_export_roles(monkeypatch):
    context = build_decision_report_context(
        title="投資判断レポート - テスト",
        sections=[
            build_report_section(
                title="確認材料",
                source_kind="cockpit",
                summary={"symbol": "7203.T"},
            )
        ],
        created_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
    )
    captions: list[str] = []
    button_calls: list[tuple[str, dict[str, object]]] = []

    class FakeColumn:
        def download_button(self, label: str, **kwargs: object) -> None:
            button_calls.append((label, kwargs))

    monkeypatch.setattr("ui.app.st.markdown", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.caption", lambda body, **_: captions.append(str(body)))
    monkeypatch.setattr("ui.app.st.columns", lambda _: [FakeColumn() for _ in range(4)])

    _render_decision_report_download_buttons(
        context,
        expander_label="投資判断レポート",
        json_file_name="decision_report_test.json",
        markdown_file_name="decision_report_test.md",
    )

    assert captions == [
        "Markdownは読む用、JSONは再現用、manifestは同梱内容の確認用、ZIPは一式保存用です。"
    ]
    assert [label for label, _ in button_calls] == [
        "Markdown（読む用）をダウンロード",
        "JSON（再現用）をダウンロード",
        "manifest（内容確認）をダウンロード",
        "一式ZIP（保存用）をダウンロード",
    ]
    assert "人が読むため" in str(button_calls[0][1]["help"])
    assert "再現確認" in str(button_calls[1][1]["help"])
    assert "ファイル" in str(button_calls[2][1]["help"])
    assert "保存用パッケージ" in str(button_calls[3][1]["help"])


def test_cockpit_decision_report_context_includes_metadata_confidence(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "6857.T",
                "name": "Advantest",
                "asset_type": "stock",
                "market": "jp",
                "currency": "JPY",
                "nisa_category": "growth",
                "investment_style": "lump_sum",
                "metadata_source": "yahoo",
                "metadata_as_of": "2026-05-22",
                "dividend_yield_pct": "0.22",
                "dividend_category": "low",
                "per": "52.42",
                "pbr": "28.93",
                "roe_pct": "57.65",
                "market_cap_tier": "mega",
            }
        ],
    )
    preview = MarketDataPreview(
        status="ok",
        bars=[
            _bar("2026-05-21", close=100, symbol="6857.T"),
            _bar("2026-05-22", close=101, symbol="6857.T"),
        ],
        provider_rows=[{"field": "provider", "value": "yahoo"}],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[
            {
                "symbol": "6857.T",
                "total_score": "84.69",
                "score_band": "strong",
                "screening_score": "78.9",
                "forecast_agreement_score": "90",
                "data_quality_score": "100",
                "risk_signal_score": "72.44",
            }
        ],
        screening_rows=[],
        error_rows=[],
    )

    context = build_cockpit_decision_report_context(preview)
    markdown = decision_report_markdown_download(context)
    payload = decision_report_json_download(context)

    assert context.title == "確認レポート - 6857.T"
    assert [section.title for section in context.sections] == [
        "データ取得状況と信頼性",
        "銘柄メタデータ",
        "スコア分解",
        "バリュエーション / インカム / リスク",
        "確認ポイント",
    ]
    assert "risk_band" in context.sections[0].summary["missing_fields"]
    assert "データ取得状況と信頼性" in markdown
    assert '"schema_version": "decision-report-context-v1"' in payload


def test_cockpit_decision_report_context_adds_research_score_section(monkeypatch):
    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", lambda: [])
    evidence = ResearchEvidence(
        symbol="6857.T",
        document_id="doc-1",
        chunk_id="chunk-1",
        title="6857 Research Note",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Business",
        excerpt=("Growth strategy, profitability margin, cash, " "and business risk are covered."),
        relevance_score=Decimal("0.82"),
        reliability=Decimal("0.88"),
    )
    research_report = CompanyResearchReport(
        symbol="6857.T",
        as_of=date(2026, 5, 25),
        summary="Research summary",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="成長戦略を確認材料として整理します。",
                evidence=[evidence],
            )
        ],
        evidence=[evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 1),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        "ui.app._cockpit_research_report_from_state",
        lambda _preview: research_report,
    )
    preview = MarketDataPreview(
        status="ok",
        bars=[_bar("2026-05-22", close=101, symbol="6857.T")],
        provider_rows=[{"field": "provider", "value": "yahoo"}],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[
            {
                "symbol": "6857.T",
                "total_score": "72.00",
                "score_band": "balanced",
                "screening_score": "70",
                "forecast_agreement_score": "80",
                "data_quality_score": "100",
                "risk_signal_score": "65",
            }
        ],
        screening_rows=[],
        error_rows=[],
    )

    context = build_cockpit_decision_report_context(preview)
    section_titles = [section.title for section in context.sections]
    score_section = next(
        section for section in context.sections if section.title == "Research Score"
    )

    assert "Research Evidence" in section_titles
    assert "Research Score" in section_titles
    assert score_section.summary["evidence_count"] == "1"
    assert any(row["row_type"] == "research_score_component" for row in score_section.rows)


def test_cockpit_decision_report_context_adds_external_research_trace(monkeypatch):
    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", lambda: [])
    monkeypatch.setattr("ui.app._cockpit_research_report_from_state", lambda _preview: None)
    fetch_result = ExternalResearchFetchResult(
        symbol="6857.T",
        provider="yahoo_finance",
        fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="6857.T Yahoo Finance Profile",
                symbol="6857.T",
                source_type="provider_profile",
                source_url="https://finance.yahoo.com/quote/6857.T/profile",
                provider="yahoo_finance",
                published_at=None,
                fetched_at=datetime(2026, 5, 27, 12, 30, tzinfo=UTC),
                freshness_status="unknown",
                document_id="research-doc-6857",
                retention_policy="session",
                content_summary="Advantest provider profile snapshot.",
            )
        ],
        retention_policy="session",
        warnings=["追加ニュースは見つかりませんでした。"],
    )
    monkeypatch.setattr(
        "ui.app._cockpit_external_research_fetch_result_from_state",
        lambda _preview: fetch_result,
    )
    preview = MarketDataPreview(
        status="ok",
        bars=[_bar("2026-05-22", close=101, symbol="6857.T")],
        provider_rows=[{"field": "provider", "value": "yahoo"}],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[
            {
                "symbol": "6857.T",
                "total_score": "72.00",
                "score_band": "balanced",
                "screening_score": "70",
                "forecast_agreement_score": "80",
                "data_quality_score": "100",
                "risk_signal_score": "65",
            }
        ],
        screening_rows=[],
        error_rows=[],
    )

    context = build_cockpit_decision_report_context(preview)
    section = next(section for section in context.sections if section.title == "外部参照ソース")
    markdown = decision_report_markdown_download(context)
    payload = decision_report_json_download(context)

    assert section.summary["retention_policy"] == "session"
    assert section.rows[0]["row_type"] == "external_research_source"
    assert section.rows[0]["source_url"] == "https://finance.yahoo.com/quote/6857.T/profile"
    assert "外部参照ソース" in markdown
    assert "このセッションのみ" in markdown
    assert '"freshness_status": "unknown"' in payload


def test_cockpit_decision_report_helpers_build_structured_summary(monkeypatch):
    monkeypatch.setattr("ui.app.symbol_universe_csv_rows", lambda: [])
    preview = MarketDataPreview(
        status="ok",
        bars=[
            _bar("2026-05-21", close=100, symbol="6857.T"),
            _bar("2026-05-22", close=104, symbol="6857.T"),
        ],
        provider_rows=[{"field": "provider", "value": "yahoo"}],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[
            {
                "symbol": "6857.T",
                "total_score": "68.2",
                "score_band": "watch",
                "screening_score": "72",
                "upside_signal_score": "66",
                "downside_signal_score": "52",
                "forecast_return_pct": "+1.2%",
                "forecast_agreement_score": "80",
                "data_quality_score": "92",
                "risk_signal_score": "70",
            }
        ],
        screening_rows=[],
        error_rows=[],
    )

    overview = cockpit_decision_report_overview(preview)
    lines = cockpit_decision_report_summary_lines(preview)
    evidence_rows = cockpit_decision_report_evidence_rows(
        preview,
        research_report=None,
        news_report=None,
    )

    assert overview["symbol"] == "6857.T"
    assert overview["overall_judgement"] == "中立〜やや前向き"
    assert overview["confidence"] == "高め"
    assert len(lines) == 3
    assert "根拠資料は未取得" in lines[2]
    assert [row["根拠"] for row in evidence_rows] == [
        "価格トレンド",
        "業績・財務",
        "ニュース",
        "リスク",
    ]


def test_ranking_decision_report_context_limits_rows_and_uses_top_symbol(monkeypatch):
    monkeypatch.setattr(
        "ui.app.symbol_universe_csv_rows",
        lambda: [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_type": "stock",
                "market": "us",
                "currency": "USD",
                "nisa_category": "growth",
                "investment_style": "lump_sum",
                "metadata_source": "yahoo",
                "metadata_as_of": "2026-05-22",
                "dividend_yield_pct": "0.5",
                "dividend_category": "low",
                "per": "28",
                "pbr": "5",
                "roe_pct": "22",
                "market_cap_tier": "mega",
                "risk_band": "standard",
            }
        ],
    )
    rows = [
        {
            "rank": str(index + 1),
            "symbol": "AAPL" if index == 0 else f"TEST{index}",
            "total_score": "80",
            "score_band": "strong",
            "screening_score": "70",
            "forecast_agreement_score": "90",
            "direction_net_score": "72",
            "upside_signal_score": "78",
            "downside_signal_score": "34",
            "direction_signal_label": "MODERATE_UPSIDE",
            "data_quality_score": "100",
            "risk_signal_score": "60",
            "note": "review candidate",
        }
        for index in range(25)
    ]
    rows[0].update(
        {
            "advanced_forecast_horizon_days": "31",
            "advanced_forecast_predicted_return": "+2.5%",
            "advanced_forecast_score": "61.25",
            "advanced_forecast_confidence": "low",
            "advanced_forecast_upside_score": "68.75",
            "advanced_forecast_downside_score": "43.25",
            "advanced_forecast_quality_score": "58.5",
            "advanced_forecast_direction_note": (
                "上昇気配・下降警戒は通常方向シグナルにAI予測インサイトを25%までブレンドしています。"
            ),
        }
    )

    context = build_ranking_decision_report_context(
        ranked_rows=rows,
        provider="yahoo",
        start=date(2026, 5, 1),
        end=date(2026, 5, 22),
        ranking_purpose="成長重視",
        weight_preset="上昇気配重視",
        comparison_summary="候補: 25件",
    )

    ranking_section = next(
        section for section in context.sections if section.title == "ランキング文脈"
    )
    distribution_section = next(
        section for section in context.sections if section.title == "ランキング分布"
    )
    factor_section = next(
        section for section in context.sections if section.title == "ファクター別上位候補"
    )
    detail_section = next(
        section for section in context.sections if section.title == "上位候補スコア詳細"
    )
    assert ranking_section.summary["reported_rows"] == "20 / 25"
    assert ranking_section.rows[0]["symbol"] == "AAPL"
    assert ranking_section.rows[0]["name"] == "Apple Inc."
    assert ranking_section.rows[0]["ranking_purpose"] == "成長重視"
    assert "note" not in ranking_section.rows[0]
    assert "screening_score" not in ranking_section.rows[0]
    assert ranking_section.rows[0]["review_point"].startswith("AI予測インサイトの信頼度")
    assert "AI予測インサイト: 31日 +2.5%" in ranking_section.rows[0]["ai_forecast_insight"]
    assert detail_section.rows[0]["upside_signal_score"] == "78"
    assert detail_section.rows[0]["downside_signal_score"] == "34"
    assert "31日 +2.5%" in detail_section.rows[0]["ai_forecast_insight"]
    assert detail_section.rows[0]["advanced_forecast_quality_score"] == "58.5"
    assert distribution_section.summary["比較銘柄数"] == "25"
    assert distribution_section.summary["AI予測インサイトあり"] == "1/25"
    assert any(
        row["観点"] == "AI予測信頼度 低め" and row["件数"] == "1"
        for row in distribution_section.rows
    )
    assert factor_section.rows[0]["観点"] == "総合スコア"
    assert any(row["観点"] == "AI予測上昇" for row in factor_section.rows)
    assert "銘柄メタデータ" not in [section.title for section in context.sections]
    assert "スコア分解" not in [section.title for section in context.sections]
    assert "ランキング結果" in context.title


def test_rank_investment_score_rows_sorts_and_reassigns_rank():
    assert rank_investment_score_rows(
        [
            {"rank": "1", "symbol": "LOW", "total_score": "50"},
            {"rank": "1", "symbol": "HIGH", "total_score": "90"},
        ]
    ) == [
        {"rank": "1", "symbol": "HIGH", "total_score": "90"},
        {"rank": "2", "symbol": "LOW", "total_score": "50"},
    ]


def test_apply_ranking_weight_preset_reweights_and_sorts_rows():
    rows = apply_ranking_weight_preset(
        [
            {
                "rank": "1",
                "symbol": "QUALITY",
                "total_score": "70",
                "score_band": "BALANCED",
                "screening_score": "60",
                "forecast_agreement_score": "50",
                "direction_net_score": "55",
                "upside_signal_score": "58",
                "downside_signal_score": "52",
                "data_quality_score": "100",
                "risk_signal_score": "60",
                "warnings": "",
            },
            {
                "rank": "2",
                "symbol": "FORECAST",
                "total_score": "70",
                "score_band": "BALANCED",
                "screening_score": "60",
                "forecast_agreement_score": "100",
                "direction_net_score": "90",
                "upside_signal_score": "85",
                "downside_signal_score": "35",
                "data_quality_score": "50",
                "risk_signal_score": "60",
                "warnings": "",
            },
        ],
        "forecast",
        {
            "QUALITY": {
                "symbol": "QUALITY",
                "metadata_source": "curated_csv",
                "metadata_as_of": "2026-05-18",
                "asset_type": "stock",
                "nisa_category": "growth",
                "market_cap_tier": "large",
                "dividend_yield_pct": "1.2",
                "dividend_category": "dividend",
                "risk_band": "MEDIUM",
                "per": "18",
                "pbr": "1.4",
                "roe_pct": "12",
            },
            "FORECAST": {
                "symbol": "FORECAST",
                "metadata_source": "curated_csv",
                "metadata_as_of": "2026-05-18",
                "asset_type": "stock",
                "nisa_category": "growth",
                "market_cap_tier": "large",
                "dividend_yield_pct": "1.2",
                "dividend_category": "dividend",
                "risk_band": "MEDIUM",
                "per": "18",
                "pbr": "1.4",
                "roe_pct": "12",
            },
        },
    )

    assert rows[0]["symbol"] == "FORECAST"
    assert rows[0]["rank"] == "1"
    assert rows[0]["total_score"] == "70.5"
    assert rows[0]["score_band"] == "BALANCED"
    assert rows[0]["database_fit_score"] == "85"
    assert rows[0]["metadata_confidence_score"] == "100"
    assert rows[0]["note"] == (
        "上昇気配重視の条件に合いやすい候補です。売買推奨ではなく、根拠確認の優先順です。"
    )
    assert rows[1]["symbol"] == "QUALITY"
    assert ranking_weight_preset_label("forecast") == "上昇気配重視"
    assert ranking_weight_preset_label(RANKING_PRESET_UPSIDE_SIGNAL) == "上昇気配重視"


def test_apply_ranking_weight_preset_supports_required_single_metric_sorts():
    rows = [
        {
            **_ranking_score_row("AAA"),
            "total_score": "80",
            "dividend_yield_pct": "1.0",
            "per": "18",
            "pbr": "2.0",
            "roe_pct": "10",
            "market_cap": "1000",
            "volume": "100",
            "volatility": "20%",
            "risk_signal_score": "80",
            "data_quality_score": "70",
        },
        {
            **_ranking_score_row("BBB"),
            "total_score": "70",
            "dividend_yield_pct": "4.0",
            "per": "8",
            "pbr": "1.0",
            "roe_pct": "15",
            "market_cap": "5000",
            "volume": "900",
            "volatility": "10%",
            "risk_signal_score": "60",
            "data_quality_score": "90",
        },
        {
            **_ranking_score_row("MISS"),
            "total_score": "90",
            "dividend_yield_pct": "",
            "per": "",
            "pbr": "",
            "roe_pct": "",
            "market_cap": "",
            "volume": "",
            "volatility": "",
            "risk_signal_score": "40",
            "data_quality_score": "50",
        },
    ]
    expectations = {
        RANKING_PURPOSE_SORT_TOTAL_SCORE: ["MISS", "AAA", "BBB"],
        RANKING_PURPOSE_SORT_DIVIDEND_YIELD: ["BBB", "AAA", "MISS"],
        RANKING_PURPOSE_SORT_PER: ["BBB", "AAA", "MISS"],
        RANKING_PURPOSE_SORT_PBR: ["BBB", "AAA", "MISS"],
        RANKING_PURPOSE_SORT_ROE: ["BBB", "AAA", "MISS"],
        RANKING_PURPOSE_SORT_MARKET_CAP: ["BBB", "AAA", "MISS"],
        RANKING_PURPOSE_SORT_VOLUME: ["BBB", "AAA", "MISS"],
        RANKING_PURPOSE_SORT_VOLATILITY: ["BBB", "AAA", "MISS"],
        RANKING_PURPOSE_SORT_RISK: ["AAA", "BBB", "MISS"],
        RANKING_PURPOSE_SORT_DATA_QUALITY: ["BBB", "AAA", "MISS"],
    }

    for purpose, expected_symbols in expectations.items():
        preset = ranking_weight_preset_for_purpose(purpose)
        ranked = apply_ranking_weight_preset(rows, preset, {})
        assert [row["symbol"] for row in ranked] == expected_symbols
        assert [row["rank"] for row in ranked] == ["1", "2", "3"]


def test_ranking_weight_presets_prefer_direction_signal_over_forecast_agreement():
    for weights in RANKING_WEIGHT_PRESETS.values():
        assert "forecast_agreement_score" not in weights
        assert "direction_net_score" not in weights

    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_UPSIDE_SIGNAL]["upside_signal_score"] == Decimal(
        "0.25"
    )
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_UPSIDE_SIGNAL]["downside_signal_score"] == Decimal(
        "0.10"
    )
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_SUSTAINABLE_INCOME][
        "upside_signal_score"
    ] == Decimal("0.05")
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_MULTI_FACTOR][
        "advanced_forecast_upside_score"
    ] == Decimal("0.07")
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_MULTI_FACTOR][
        "advanced_forecast_downside_score"
    ] == Decimal("0.03")


def test_ranking_weight_presets_use_tuned_policy_weights():
    for weights in RANKING_WEIGHT_PRESETS.values():
        assert sum(weights.values(), Decimal("0")) == Decimal("1.00")
        assert weights.get("research_score", Decimal("0")) <= Decimal("0.05")

    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_MULTI_FACTOR]["screening_score"] == Decimal("0.30")
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_MULTI_FACTOR]["research_score"] == Decimal("0.05")
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_SMALL_GROWTH]["risk_signal_score"] == Decimal(
        "0.15"
    )
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_RISK_ADJUSTED]["risk_signal_score"] == Decimal(
        "0.20"
    )
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_RISK_ADJUSTED]["downside_signal_score"] == Decimal(
        "0.05"
    )
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_NISA_LONG_TERM]["research_score"] == Decimal(
        "0.05"
    )
    assert (
        RANKING_WEIGHT_PRESETS[RANKING_PRESET_ETF_CORE_COST]
        != RANKING_WEIGHT_PRESETS[RANKING_PRESET_ETF_INCOME]
    )
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_ETF_CORE_COST]["database_fit_score"] == Decimal(
        "0.30"
    )
    assert RANKING_WEIGHT_PRESETS[RANKING_PRESET_ETF_INCOME]["database_fit_score"] == Decimal(
        "0.35"
    )


def test_ai_multi_factor_profile_uses_advanced_forecast_without_penalizing_missing_data():
    rows = [
        {
            **_ranking_score_row("ADVANCED"),
            "advanced_forecast_upside_score": "80",
            "advanced_forecast_downside_score": "35",
            "advanced_forecast_quality_score": "75",
        },
        _ranking_score_row("MISSING_ADVANCED"),
    ]
    symbol_rows = {
        "ADVANCED": _stock_symbol_metadata("ADVANCED"),
        "MISSING_ADVANCED": _stock_symbol_metadata("MISSING_ADVANCED"),
    }

    ranked = apply_ranking_weight_preset(rows, RANKING_PRESET_MULTI_FACTOR, symbol_rows)

    assert ranked[0]["symbol"] == "ADVANCED"
    assert ranked[0]["rank"] == "1"
    assert ranked[1]["symbol"] == "MISSING_ADVANCED"
    assert ranked[1]["advanced_forecast_upside_score"] == "50"
    assert ranked[1]["advanced_forecast_downside_score"] == "50"
    assert ranked[1]["advanced_forecast_quality_score"] == "50"


def test_ai_multi_factor_profile_rewards_lower_downside_warning():
    rows = [
        {
            **_ranking_score_row("LOW_WARNING"),
            "upside_signal_score": "55",
            "downside_signal_score": "20",
            "advanced_forecast_downside_score": "25",
        },
        {
            **_ranking_score_row("HIGH_WARNING"),
            "upside_signal_score": "55",
            "downside_signal_score": "80",
            "advanced_forecast_downside_score": "75",
        },
    ]
    symbol_rows = {
        "LOW_WARNING": _stock_symbol_metadata("LOW_WARNING"),
        "HIGH_WARNING": _stock_symbol_metadata("HIGH_WARNING"),
    }

    ranked = apply_ranking_weight_preset(rows, RANKING_PRESET_MULTI_FACTOR, symbol_rows)

    assert ranked[0]["symbol"] == "LOW_WARNING"
    assert ranked[1]["symbol"] == "HIGH_WARNING"


def test_advanced_forecast_enrichment_blends_upside_and_downside_signals():
    rows = [
        {
            **_ranking_score_row("ADVANCED"),
            "upside_signal_score": "60",
            "downside_signal_score": "40",
            "direction_net_score": "60",
            "direction_signal_label": "MODERATE_UPSIDE",
        }
    ]

    enriched = _enrich_ranking_rows_with_advanced_forecast(
        rows,
        {
            "ADVANCED": {
                "advanced_forecast_predicted_return": "+3%",
                "advanced_forecast_upside_score": "80",
                "advanced_forecast_downside_score": "70",
                "advanced_forecast_quality_score": "75",
            }
        },
    )

    assert enriched[0]["upside_signal_score"] == "65"
    assert enriched[0]["downside_signal_score"] == "47.5"
    assert enriched[0]["direction_net_score"] == "58.75"
    assert enriched[0]["direction_signal_label"] == "MODERATE_UPSIDE"
    assert "25%" in enriched[0]["advanced_forecast_direction_note"]


def test_upside_signal_profile_keeps_high_downside_warning_from_top_rank():
    rows = [
        {
            **_ranking_score_row("SOLID"),
            "direction_net_score": "78",
            "upside_signal_score": "82",
            "downside_signal_score": "30",
        },
        {
            **_ranking_score_row("CAUTION"),
            "direction_net_score": "45",
            "upside_signal_score": "78",
            "downside_signal_score": "88",
        },
    ]
    symbol_rows = {
        "SOLID": _stock_symbol_metadata("SOLID"),
        "CAUTION": _stock_symbol_metadata("CAUTION"),
    }

    ranked = apply_ranking_weight_preset(rows, RANKING_PRESET_UPSIDE_SIGNAL, symbol_rows)

    assert ranked[0]["symbol"] == "SOLID"
    assert ranked[1]["symbol"] == "CAUTION"
    assert ranked[1]["downside_signal_score"] == "88"


def _ranking_score_row(symbol: str) -> dict[str, str]:
    return {
        "rank": "1",
        "symbol": symbol,
        "total_score": "50",
        "score_band": "BALANCED",
        "screening_score": "50",
        "forecast_agreement_score": "50",
        "direction_net_score": "50",
        "upside_signal_score": "50",
        "downside_signal_score": "50",
        "direction_signal_label": "NEUTRAL",
        "data_quality_score": "50",
        "risk_signal_score": "50",
        "warnings": "",
    }


def _stock_symbol_metadata(
    symbol: str,
    *,
    dividend_yield_pct: str = "1.0",
    market_cap_tier: str = "large",
    per: str = "25",
    pbr: str = "2.5",
    roe_pct: str = "8",
    risk_band: str = "MEDIUM",
    nisa_category: str = "growth",
) -> dict[str, str]:
    return {
        "symbol": symbol,
        "metadata_source": "curated_csv",
        "metadata_as_of": "2026-05-18",
        "asset_type": "stock",
        "is_active": "true",
        "nisa_category": nisa_category,
        "market_cap_tier": market_cap_tier,
        "dividend_yield_pct": dividend_yield_pct,
        "dividend_category": (
            "high_dividend" if Decimal(dividend_yield_pct) >= Decimal("3") else "dividend"
        ),
        "risk_band": risk_band,
        "per": per,
        "pbr": pbr,
        "roe_pct": roe_pct,
    }


def _etf_symbol_metadata(
    symbol: str,
    *,
    dividend_yield_pct: str = "0",
    expense_ratio_pct: str = "0.50",
    complexity: str = "standard",
    index_family: str = "sp500",
    nisa_category: str = "growth",
) -> dict[str, str]:
    return {
        "symbol": symbol,
        "metadata_source": "curated_csv",
        "metadata_as_of": "2026-05-18",
        "asset_type": "etf",
        "is_active": "true",
        "nisa_category": nisa_category,
        "dividend_yield_pct": dividend_yield_pct,
        "dividend_category": (
            "high_dividend" if Decimal(dividend_yield_pct) >= Decimal("3") else "dividend"
        ),
        "risk_band": "MEDIUM",
        "index_family": index_family,
        "expense_ratio_pct": expense_ratio_pct,
        "complexity": complexity,
    }


def test_advanced_stock_ranking_profiles_change_order_by_metadata_fit():
    symbol_rows = {
        "GROWTH": _stock_symbol_metadata(
            "GROWTH", roe_pct="24", per="32", pbr="5", risk_band="HIGH"
        ),
        "VALUE": _stock_symbol_metadata(
            "VALUE", market_cap_tier="small", roe_pct="12", per="10", pbr="0.9", risk_band="MEDIUM"
        ),
        "INCOME": _stock_symbol_metadata(
            "INCOME",
            market_cap_tier="small",
            dividend_yield_pct="4.0",
            per="18",
            pbr="1.1",
            risk_band="MEDIUM",
        ),
        "LOWVOL": _stock_symbol_metadata(
            "LOWVOL", market_cap_tier="mega", dividend_yield_pct="2.0", risk_band="LOW"
        ),
        "SMALL": _stock_symbol_metadata(
            "SMALL", market_cap_tier="small", roe_pct="18", per="28", risk_band="MEDIUM"
        ),
    }
    rows = [_ranking_score_row(symbol) for symbol in symbol_rows]

    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_QUALITY_GROWTH, symbol_rows)[0]["symbol"]
        == "GROWTH"
    )
    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_QUALITY_VALUE, symbol_rows)[0]["symbol"]
        == "VALUE"
    )
    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_SUSTAINABLE_INCOME, symbol_rows)[0][
            "symbol"
        ]
        == "INCOME"
    )
    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_MIN_VOLATILITY, symbol_rows)[0]["symbol"]
        == "LOWVOL"
    )
    assert (
        apply_ranking_weight_preset(rows, RANKING_PRESET_SMALL_GROWTH, symbol_rows)[0]["symbol"]
        == "SMALL"
    )


def test_advanced_etf_ranking_profiles_change_order_by_cost_or_income():
    core_rows = {
        "CORE": _etf_symbol_metadata(
            "CORE", expense_ratio_pct="0.03", complexity="beginner", index_family="sp500"
        ),
        "COMPLEX": _etf_symbol_metadata(
            "COMPLEX",
            expense_ratio_pct="0.95",
            complexity="advanced",
            index_family="",
            nisa_category="none",
        ),
    }
    income_rows = {
        "ETF_INCOME": _etf_symbol_metadata(
            "ETF_INCOME", dividend_yield_pct="4.0", expense_ratio_pct="0.30"
        ),
        "ETF_WEAK": _etf_symbol_metadata(
            "ETF_WEAK",
            dividend_yield_pct="0",
            expense_ratio_pct="0.90",
            complexity="advanced",
            index_family="",
            nisa_category="none",
        ),
    }

    assert (
        apply_ranking_weight_preset(
            [_ranking_score_row(symbol) for symbol in core_rows],
            RANKING_PRESET_ETF_CORE_COST,
            core_rows,
        )[0]["symbol"]
        == "CORE"
    )
    assert (
        apply_ranking_weight_preset(
            [_ranking_score_row(symbol) for symbol in income_rows],
            RANKING_PRESET_ETF_INCOME,
            income_rows,
        )[0]["symbol"]
        == "ETF_INCOME"
    )


def test_ranking_weight_presets_are_normalized():
    for weights in RANKING_WEIGHT_PRESETS.values():
        assert sum(weights.values(), Decimal("0")) == Decimal("1.00")


def test_limited_ranking_selected_labels_prefers_database_fit_before_fetch():
    low_rows = [
        _stock_symbol_metadata(f"LOW{index}", roe_pct="4", per="45", pbr="5", risk_band="HIGH")
        for index in range(100)
    ]
    rows = [
        *low_rows,
        _stock_symbol_metadata("HIGH", roe_pct="24", per="30", pbr="4", risk_band="MEDIUM"),
    ]
    selected_labels = [f"LOW{index} - LOW{index}" for index in range(100)] + ["HIGH - HIGH"]

    limited = limited_ranking_selected_labels(
        selected_labels,
        rows,
        preset=RANKING_PRESET_QUALITY_GROWTH,
        limit_key=RANKING_FETCH_LIMIT_FAST,
    )
    assert len(limited) == 100
    assert limited[0] == "HIGH - HIGH"
    assert (
        limited_ranking_selected_labels(
            selected_labels,
            rows,
            preset=RANKING_PRESET_QUALITY_GROWTH,
            limit_key=RANKING_FETCH_LIMIT_BALANCED,
        )
        == selected_labels
    )


def test_ranking_fetch_limit_baseline_is_independent_from_sort_profile():
    assert RANKING_FETCH_LIMIT_PRESET == RANKING_PRESET_MULTI_FACTOR


def test_ranking_database_scores_use_symbol_metadata():
    high_dividend = {
        "symbol": "9434.T",
        "asset_type": "stock",
        "is_active": "true",
        "nisa_category": "growth",
        "dividend_yield_pct": "3.8",
        "pbr": "1.2",
        "risk_band": "MEDIUM",
        "metadata_source": "yahoo",
        "metadata_as_of": "2026-05-22",
        "market_cap_tier": "large",
        "dividend_category": "high_dividend",
        "per": "14",
        "roe_pct": "12",
    }

    assert ranking_database_fit_score(high_dividend, "income") == Decimal("100")
    assert ranking_metadata_confidence_score(high_dividend) == Decimal("100")


def test_ranking_scores_do_not_treat_abnormal_dividend_yield_as_income_fit():
    normal_dividend = {
        "symbol": "7203.T",
        "asset_type": "stock",
        "is_active": "true",
        "nisa_category": "growth",
        "dividend_yield_pct": "3.29",
        "pbr": "1.1",
        "risk_band": "MEDIUM",
        "metadata_source": "yahoo",
        "metadata_as_of": "2026-06-01",
    }
    abnormal_dividend = {
        **normal_dividend,
        "symbol": "GMEX",
        "dividend_yield_pct": "293.19",
    }

    assert ranking_database_fit_score(abnormal_dividend, "income") < ranking_database_fit_score(
        normal_dividend, "income"
    )
    assert ranking_metadata_confidence_score(abnormal_dividend) < ranking_metadata_confidence_score(
        normal_dividend
    )


def test_ranking_scores_do_not_treat_invalid_per_pbr_as_value_fit():
    valid_value = {
        "symbol": "VALUE",
        "asset_type": "stock",
        "is_active": "true",
        "nisa_category": "growth",
        "per": "10",
        "pbr": "0.9",
        "roe_pct": "12",
        "risk_band": "MEDIUM",
        "metadata_source": "yahoo",
        "metadata_as_of": "2026-06-01",
    }
    invalid_value = {
        **valid_value,
        "symbol": "BA",
        "per": "0",
        "pbr": "0",
    }

    assert ranking_database_fit_score(invalid_value, "value_profile") < ranking_database_fit_score(
        valid_value, "value_profile"
    )
    assert ranking_metadata_confidence_score(invalid_value) < ranking_metadata_confidence_score(
        valid_value
    )


def test_dividend_yield_sort_places_abnormal_values_after_valid_values():
    rows = [
        {"symbol": "GMEX", "total_score": "90"},
        {"symbol": "7203.T", "total_score": "70"},
        {"symbol": "AAPL", "total_score": "60"},
    ]
    symbol_rows = {
        "GMEX": {"symbol": "GMEX", "asset_type": "stock", "dividend_yield_pct": "293.19"},
        "7203.T": {"symbol": "7203.T", "asset_type": "stock", "dividend_yield_pct": "3.29"},
        "AAPL": {"symbol": "AAPL", "asset_type": "stock", "dividend_yield_pct": "0.35"},
    }

    ranked = apply_ranking_weight_preset(
        rows,
        RANKING_PRESET_SORT_DIVIDEND_YIELD,
        symbol_rows,
    )

    assert [row["symbol"] for row in ranked] == ["7203.T", "AAPL", "GMEX"]


def test_per_and_pbr_sort_place_invalid_values_after_valid_values():
    rows = [
        {"symbol": "NEG", "total_score": "90"},
        {"symbol": "LOW", "total_score": "70"},
        {"symbol": "HIGH", "total_score": "60"},
    ]
    symbol_rows = {
        "NEG": {"symbol": "NEG", "asset_type": "stock", "per": "-24.84", "pbr": "0"},
        "LOW": {"symbol": "LOW", "asset_type": "stock", "per": "8", "pbr": "0.9"},
        "HIGH": {"symbol": "HIGH", "asset_type": "stock", "per": "30", "pbr": "5"},
    }

    per_ranked = apply_ranking_weight_preset(rows, RANKING_PRESET_SORT_PER, symbol_rows)
    pbr_ranked = apply_ranking_weight_preset(rows, RANKING_PRESET_SORT_PBR, symbol_rows)

    assert [row["symbol"] for row in per_ranked] == ["LOW", "HIGH", "NEG"]
    assert [row["symbol"] for row in pbr_ranked] == ["LOW", "HIGH", "NEG"]


def test_investment_score_csv_download_accepts_ranking_metadata_scores():
    csv_bytes = investment_score_csv_download(
        [
            {
                "rank": "1",
                "symbol": "9434.T",
                "total_score": "82",
                "score_band": "STRONG",
                "screening_score": "75",
                "forecast_agreement_score": "70",
                "data_quality_score": "100",
                "database_fit_score": "95",
                "metadata_confidence_score": "100",
                "research_score": "50",
                "risk_signal_score": "60",
                "ranking_profile": "配当・インカム重視",
                "warnings": "",
                "note": "売買推奨ではなく、根拠確認の優先順です。",
            }
        ]
    )

    csv_text = csv_bytes.decode("utf-8-sig")
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    assert "database_fit_score" in csv_text
    assert "metadata_confidence_score" in csv_text
    assert "research_score" in csv_text
    assert "ranking_profile" in csv_text


def test_screening_score_rows_include_forecast_signal():
    rows = screening_score_rows(
        [
            ScreeningScore(
                rank=1,
                symbol="AAPL",
                total_score=Decimal("84.35"),
                momentum_score=Decimal("80"),
                liquidity_score=Decimal("100"),
                risk_score=Decimal("88"),
                data_quality_score=Decimal("100"),
                forecast_score=Decimal("45"),
                forecast_agreement="LOW",
                data_quality="OK",
                summary="AAPL は今回の条件では上位候補です。",
                forecast_reason="予測モデル同士の見方が割れています。",
                reason_labels=["予測モデル同士の見方が割れています。"],
                reasons=["forecast_agreement:low"],
            )
        ]
    )

    assert rows == [
        {
            "rank": "1",
            "symbol": "AAPL",
            "total_score": "84.35",
            "momentum_score": "80",
            "liquidity_score": "100",
            "risk_score": "88",
            "data_quality_score": "100",
            "forecast_score": "45",
            "forecast_agreement": "LOW",
            "data_quality": "OK",
            "summary": "AAPL は今回の条件では上位候補です。",
            "forecast_reason": "予測モデル同士の見方が割れています。",
            "reason_labels": "予測モデル同士の見方が割れています。",
            "reasons": "forecast_agreement:low",
        }
    ]


def test_market_chart_long_frame_adds_beginner_friendly_labels():
    frame = market_chart_long_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "naive": "",
            },
            {
                "ts": "2026-05-11T00:00:00+00:00",
                "close": "",
                "naive": "186.5",
            },
        ]
    )

    assert frame[["series", "line_label", "series_label"]].to_dict("records") == [
        {
            "series": "close",
            "line_label": "実績",
            "series_label": "実績価格",
        },
        {
            "series": "naive",
            "line_label": "予測",
            "series_label": "予測: 直近値維持",
        },
    ]


def test_market_chart_long_frame_labels_advanced_linear_forecast():
    frame = market_chart_long_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "advanced_linear_5d": "185",
            },
            {
                "ts": "2026-05-15T00:00:00+00:00",
                "close": "",
                "advanced_linear_5d": "191.5",
            },
        ]
    )

    advanced_rows = frame[frame["series"] == "advanced_linear_5d"]

    assert advanced_rows["line_label"].unique().tolist() == ["予測"]
    assert advanced_rows["series_label"].unique().tolist() == ["高度予測: 線形モデル 5日"]


def test_market_chart_long_frame_labels_advanced_quantile_forecast():
    frame = market_chart_long_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "advanced_quantile_5d": "185",
                "advanced_quantile_5d_lower": "185",
                "advanced_quantile_5d_upper": "185",
            },
            {
                "ts": "2026-05-15T00:00:00+00:00",
                "close": "",
                "advanced_quantile_5d": "191.5",
                "advanced_quantile_5d_lower": "178.2",
                "advanced_quantile_5d_upper": "202.4",
            },
        ]
    )
    band_frame = forecast_range_band_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "advanced_quantile_5d": "185",
                "advanced_quantile_5d_lower": "185",
                "advanced_quantile_5d_upper": "185",
            },
            {
                "ts": "2026-05-15T00:00:00+00:00",
                "close": "",
                "advanced_quantile_5d": "191.5",
                "advanced_quantile_5d_lower": "178.2",
                "advanced_quantile_5d_upper": "202.4",
            },
        ]
    )

    advanced_rows = frame[frame["series"] == "advanced_quantile_5d"]

    assert advanced_rows["line_label"].unique().tolist() == ["予測"]
    assert advanced_rows["series_label"].unique().tolist() == ["高度予測: レンジモデル 5日"]
    assert "advanced_quantile_5d_lower" not in set(frame["series"])
    assert band_frame["series"].unique().tolist() == ["advanced_quantile_5d"]
    assert band_frame.iloc[-1]["lower"] == 178.2
    assert band_frame.iloc[-1]["upper"] == 202.4


def test_forecast_range_band_frame_includes_advanced_consensus_range():
    band_frame = forecast_range_band_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "advanced_consensus_10d": "185",
                "advanced_consensus_10d_lower": "185",
                "advanced_consensus_10d_upper": "185",
            },
            {
                "ts": "2026-05-20T00:00:00+00:00",
                "close": "",
                "advanced_consensus_10d": "191.5",
                "advanced_consensus_10d_lower": "178.2",
                "advanced_consensus_10d_upper": "202.4",
            },
        ]
    )

    assert band_frame["series"].unique().tolist() == ["advanced_consensus_10d"]
    assert band_frame["series_label"].unique().tolist() == ["AI予測インサイト 10日"]
    assert band_frame.iloc[-1]["lower"] == 178.2
    assert band_frame.iloc[-1]["upper"] == 202.4


def test_forecast_model_cards_include_baseline_and_advanced_logic_help():
    metric_rows = [
        {
            "model": "naive",
            "symbol": "AAPL",
            "horizon_days": "1",
            "forecast_close": "100",
            "mae": "1.2",
            "rmse": "1.5",
            "direction_accuracy": "50.00%",
            "sample_count": "30",
        },
        {
            "model": "moving_average_20",
            "symbol": "AAPL",
            "horizon_days": "1",
            "forecast_close": "98.3",
            "mae": "1.2",
            "rmse": "1.5",
            "direction_accuracy": "45.00%",
            "sample_count": "30",
        },
    ]
    advanced_rows = [
        {
            "horizon_days": "5",
            "predicted_return": "1.40%",
            "forecast_close": "2889.9",
            "direction_score": "63.67%",
            "confidence": "medium",
            "rmse": "0.0618",
            "direction_accuracy": "49.74%",
            "sample_count": "238",
            "top_features": (
                "ma_gap_20d: 押し下げ -0.0123, "
                "drawdown_20d: 押し下げ -0.0085, "
                "rolling_volume_20d: 押し上げ 0.004"
            ),
            "warnings": (
                "This advanced forecast is experimental reference information, not investment advice.; "
                "Feature contributions describe model coefficients and are not causal explanations."
            ),
        }
    ]

    cards = forecast_model_card_rows(
        metric_rows,
        advanced_rows,
        latest_close=Decimal("100"),
        latest_date=date(2026, 6, 7),
    )
    cards_html = forecast_model_cards_html(cards)
    display_rows = advanced_forecast_display_rows(advanced_rows)
    intro = advanced_forecast_intro_text(advanced_rows)

    assert [card["model"] for card in cards] == [
        "予測: 20日移動平均",
        "高度予測: 線形モデル 5日",
    ]
    assert cards[0]["value"] == "-1.7%"
    assert cards[1]["value"] == "+1.4%"
    assert cards[0]["horizon"] == "1日先 (2026/06/08)"
    assert cards[1]["horizon"] == "5日先 (2026/06/12)"
    assert "直近値維持" not in cards_html
    assert "予測価格 = 直近20日間の終値の平均" in cards[0]["help"]
    assert "予測変化率 = 切片 + Σ(特徴量 × 係数)" in cards[1]["help"]
    assert "予測価格 = 最新価格 × (1 + 予測変化率)" in cards[1]["help"]
    assert "smai-forecast-model-name" in cards_html
    assert display_rows[0]["信頼度"] == "中くらい"
    assert display_rows[0]["予測変化"] == "+1.4%"
    assert "5日 +1.4%" in intro
    assert "実験的な参考予測" in display_rows[0]["注意点"]
    assert "因果関係の説明ではありません" in display_rows[0]["注意点"]


def test_forecast_logic_help_uses_beginner_friendly_formulas():
    moving_average_help = _forecast_model_logic_help("moving_average_20")
    momentum_help = _forecast_model_logic_help("momentum_30")
    naive_help = _forecast_model_logic_help("naive")

    assert "予測価格 = 直近20日間の終値の平均" in moving_average_help
    assert "直近30日変化率 = 最新価格 ÷ 30日前価格 - 1" in momentum_help
    assert "予測価格 = 最新終値" in naive_help


def test_forecast_model_cards_can_focus_on_advanced_models_only():
    metric_rows = [
        {
            "model": "moving_average_20",
            "symbol": "AAPL",
            "horizon_days": "10",
            "forecast_close": "98.3",
            "mae": "1.2",
            "rmse": "1.5",
            "direction_accuracy": "45.00%",
            "sample_count": "30",
        }
    ]
    advanced_rows = [
        {
            "horizon_days": "10",
            "predicted_return": "1.40%",
            "forecast_close": "101.4",
            "direction_score": "63.67%",
            "confidence": "medium",
            "rmse": "0.0618",
            "direction_accuracy": "49.74%",
            "sample_count": "238",
            "top_features": "",
            "warnings": "",
        }
    ]

    cards = forecast_model_card_rows(
        metric_rows,
        advanced_rows,
        latest_close=Decimal("100"),
        latest_date=date(2026, 6, 7),
        include_standard_models=False,
    )

    assert [card["kind"] for card in cards] == ["高度予測"]
    assert cards[0]["model"] == "高度予測: 線形モデル 10日"


def test_forecast_model_cards_show_quantile_range_context():
    advanced_rows = [
        {
            "adapter": "advanced_quantile",
            "model_label": "高度予測: レンジモデル",
            "horizon_days": "5",
            "predicted_return": "1.40%",
            "predicted_return_lower": "-2.50%",
            "predicted_return_upper": "4.20%",
            "forecast_close": "101.4",
            "direction_score": "63.67%",
            "confidence": "medium",
            "rmse": "0.0618",
            "direction_accuracy": "49.74%",
            "sample_count": "238",
            "top_features": "",
            "warnings": (
                "This advanced forecast is experimental reference information, not investment advice.; "
                "Quantile range is based on historical forward returns and is not a guaranteed interval."
            ),
        }
    ]

    cards = forecast_model_card_rows(
        [],
        advanced_rows,
        latest_close=Decimal("100"),
        latest_date=date(2026, 6, 7),
    )
    display_rows = advanced_forecast_display_rows(advanced_rows)
    intro = advanced_forecast_intro_text(advanced_rows)

    assert cards[0]["model"] == "高度予測: レンジモデル 5日"
    assert "レンジ -2.5%〜+4.2%" in cards[0]["sub"]
    assert "過去の5日後リターン = (5日後の価格 ÷ 当日の価格) - 1" in cards[0]["help"]
    assert "20%点と80%点を下振れ・上振れ" in cards[0]["help"]
    assert display_rows[0]["想定レンジ"] == "-2.5%〜+4.2%"
    assert display_rows[0]["方向感"] == "上向き寄り 63.67%"
    assert "高度予測: レンジモデル 5日 +1.4%" in intro


def test_advanced_forecast_model_help_explains_tree_and_boosting_logic():
    tree_help = _advanced_forecast_model_help(
        {"adapter": "advanced_tree_sklearn", "horizon_days": "10"}
    )
    gbdt_help = _advanced_forecast_model_help(
        {"adapter": "advanced_gbdt_sklearn", "horizon_days": "10"}
    )

    assert "条件分岐で似た局面に分け" in tree_help
    assert "予測価格 = 最新価格 × (1 + 推定リターン)" in tree_help
    assert "小さな決定木を順番に足し" in gbdt_help
    assert "予測価格 = 最新価格 × (1 + 推定リターン)" in gbdt_help


def test_advanced_forecast_consensus_display_rows_are_beginner_friendly():
    rows = [
        {
            "symbol": "AAPL",
            "horizon_days": "10",
            "model_count": "4",
            "predicted_return": "2.35%",
            "forecast_close": "104.2",
            "predicted_return_lower": "-1.20%",
            "predicted_return_upper": "4.80%",
            "agreement": "MEDIUM",
            "confidence": "medium",
            "direction_agreement_score": "75",
            "weighted_direction_score": "62.50%",
            "mean_direction_accuracy": "54.20%",
            "mean_rmse": "0.0412",
            "mean_rmse_improvement": "0.0031",
            "best_adapter": "advanced_gbdt_sklearn",
            "best_model": "HistGradientBoostingRegressor",
            "warnings": (
                "Advanced forecast consensus is reference information, not investment advice.; "
                "Advanced model directions are mixed."
            ),
        }
    ]

    display_rows = advanced_forecast_consensus_display_rows(rows)
    help_text = _advanced_forecast_consensus_help_text(rows[0])

    assert display_rows == [
        {
            "銘柄": "AAPL",
            "予測日数": "10",
            "モデル数": "4",
            "統合予測": "+2.35%",
            "予測価格": "104.2",
            "想定レンジ": "-1.2%〜+4.8%",
            "予測ばらつき": "やや広い",
            "モデル合意度": "4モデル中3モデルが上昇寄り",
            "信頼度": "中くらい",
            "過去検証の方向一致率": "54.20%",
            "平均RMSE": "0.0412",
            "誤差改善": "小 / RMSE改善値 0.0031",
            "相対的に安定": ("高度予測: ブースティングモデル 10日 / HistGradientBoostingRegressor"),
            "注意点": (
                "AI予測インサイトは参考情報です。売買判断そのものではありません。 / "
                "高度予測モデルの方向感が割れています。"
            ),
        }
    ]
    assert "統合予測 = Σ(各モデルの予測変化率 × 重み) ÷ Σ重み" in help_text
    assert "重み = 信頼度 × 誤差改善 × モデル合意度 × 検証数" in help_text
    assert "予測価格 = 最新価格 × (1 + 統合予測)" in help_text


def test_advanced_forecast_insight_card_html_is_information_dense():
    html = _advanced_forecast_insight_card_html(
        {
            "horizon_days": "31",
            "model_count": "4",
            "predicted_return": "-0.30%",
            "forecast_close": "2812.865",
            "predicted_return_lower": "-8.58%",
            "predicted_return_upper": "10.48%",
            "forecast_close_lower": "2580.3",
            "forecast_close_upper": "3120.1",
            "agreement": "MEDIUM",
            "confidence": "low",
            "direction_agreement_score": "50",
            "mean_direction_accuracy": "54.20%",
            "mean_rmse": "0.0412",
            "mean_rmse_improvement": "0.0031",
            "best_adapter": "advanced_gbdt_sklearn",
            "best_model": "HistGradientBoostingRegressor",
            "weighted_direction_score": "48",
        }
    )

    assert "AI予測インサイト" in html
    assert 'data-tone="caution"' in html
    assert "統合予測" in _advanced_forecast_consensus_help_text({"model_count": "4"})
    assert "結論" in html
    assert "中立寄り。予測レンジが広く判断保留" in html
    assert "主な理由" in html
    assert "注意点" in html
    assert "予測期間" in html
    assert "モデル合意度" in html
    assert "4モデル中2モデルが中立寄り" in html
    assert "smai-insight-mini-grid" in html
    assert "smai-insight-mini-field" in html
    assert "予測ばらつき" in html
    assert "大きめ" in html
    assert "中心予測" in html
    assert "高度予測モデルの統合結果" in html
    assert "予測価格" in html
    assert "予測レンジ" in html
    assert "2580.3〜3120.1" in html
    assert "下振れ予測" in html
    assert "上振れ予測" in html
    assert "過去のばらつきやモデル差を考慮した慎重側の見方" in html
    assert "複数の高度予測モデルを統合した中心的な見通し" in html
    assert "モデル上の上方向シナリオ" in html
    assert 'data-case="center"' not in html
    assert html.index("smai-insight-center-forecast") < html.index("smai-insight-range")
    assert html.index("smai-insight-range") < html.index("smai-insight-price-row")
    assert "弱気" not in html
    assert "中央値" not in html
    assert "強気" not in html
    assert "信頼度低め" in html
    assert "レンジ -8.58%〜+10.48%" in html
    assert "平均RMSE" not in html
    assert "RMSE改善" not in html
    assert "相対的に安定" not in html


def test_forecast_horizon_notice_text_explains_period_derived_horizon():
    text = forecast_horizon_notice_text(31)

    assert "今回の予測期間: 31日" in text
    assert "取得期間から自動計算" in text
    assert "短期寄り" in text
    assert "中期寄り" in text


def test_price_forecast_hero_keeps_guidance_inside_cards(monkeypatch):
    preview = MarketDataPreview(
        status="ok",
        bars=[_bar("2026-06-01", close=100), _bar("2026-06-02", close=102)],
        provider_rows=[],
        quote_rows=[],
        ohlcv_rows=[],
        price_chart_rows=[],
        forecast_chart_rows=[],
        forecast_metric_rows=[],
        fx_rows=[],
        feature_rows=[],
        investment_score_rows=[],
        screening_rows=[],
        error_rows=[],
    )
    forecast_rows = [
        {"ts": "2026-06-02T00:00:00+00:00", "close": "102"},
        {
            "ts": "2026-07-03T00:00:00+00:00",
            "close": "",
            "advanced_consensus_31d": "105",
        },
    ]
    advanced_rows = [
        {
            "model": "advanced_linear",
            "horizon_days": "31",
            "forecast_close": "105",
        }
    ]
    consensus_rows = [
        {
            "horizon_days": "31",
            "model_count": "4",
            "predicted_return": "2.35%",
            "forecast_close": "105",
            "predicted_return_lower": "-1.20%",
            "predicted_return_upper": "4.80%",
            "agreement": "HIGH",
            "confidence": "medium",
            "direction_agreement_score": "75",
            "mean_direction_accuracy": "54.20%",
            "mean_rmse": "0.0412",
            "mean_rmse_improvement": "0.0031",
            "weighted_direction_score": "72",
        }
    ]
    caption_calls: list[str] = []
    warning_calls: list[str] = []

    monkeypatch.setattr("ui.app.st.caption", lambda text, *_, **__: caption_calls.append(text))
    monkeypatch.setattr("ui.app.st.warning", lambda text, *_, **__: warning_calls.append(text))
    monkeypatch.setattr("ui.app.st.subheader", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.markdown", lambda *_, **__: None)
    monkeypatch.setattr(app_module, "_render_market_chart", lambda *_, **__: None)
    monkeypatch.setattr(
        app_module,
        "_render_forecast_model_detail_expanders",
        lambda *_, **__: None,
    )

    _render_price_forecast_hero(
        preview,
        "AAPL - Apple Inc.",
        forecast_rows,
        [],
        [],
        advanced_rows,
        consensus_rows,
        forecast_horizon_days=31,
    )

    assert caption_calls == ["予測期間: 31日"]
    assert warning_calls == []


def test_simple_forecast_baseline_comparison_rows_include_consensus_and_baselines():
    rows = simple_forecast_baseline_comparison_rows(
        [
            {"model": "naive", "rmse": "0.0800", "direction_accuracy": "50.0%"},
            {
                "model": "moving_average_30",
                "rmse": "0.0610",
                "direction_accuracy": "52.0%",
            },
            {
                "model": "advanced_linear_31d",
                "rmse": "0.0550",
                "direction_accuracy": "58.0%",
            },
        ],
        [
            {
                "predicted_return": "2.35%",
                "mean_rmse": "0.0412",
                "mean_direction_accuracy": "54.20%",
                "mean_rmse_improvement": "0.0031",
                "confidence": "medium",
            }
        ],
    )

    assert rows[0]["区分"] == "AI予測インサイト"
    assert rows[0]["予測変化"] == "+2.35%"
    assert "改善傾向" in rows[0]["検証メモ"]
    assert [row["区分"] for row in rows[1:]] == ["予測: 直近値維持", "予測: 30日移動平均"]
    assert all("基準モデル" in row["検証メモ"] for row in rows[1:])


def test_advanced_forecast_validation_detail_rows_keep_metrics_folded():
    rows = advanced_forecast_validation_detail_rows(
        [
            {
                "mean_direction_accuracy": "73.38%",
                "mean_rmse": "0.0962",
                "mean_rmse_improvement": "0.0252",
                "best_adapter": "advanced_tree_sklearn",
                "best_model": "ExtraTreesRegressor",
                "horizon_days": "31",
                "warnings": "Advanced models have a wide forecast spread.",
            }
        ]
    )

    assert [row["項目"] for row in rows] == [
        "過去検証の方向一致率",
        "平均RMSE",
        "誤差改善",
        "相対的に安定",
        "注意点",
    ]
    assert rows[2]["値"] == "中 / RMSE改善値 0.0252"
    assert "高度予測: ツリーモデル 31日 / ExtraTreesRegressor" in rows[3]["値"]
    assert "高度予測モデル間の開きが大きい状態です" in rows[4]["値"]


def test_forecast_chart_filter_options_hide_naive_by_default():
    rows = [
        {
            "ts": "2026-06-07T00:00:00+00:00",
            "close": "100",
        },
        {
            "ts": "2026-06-12T00:00:00+00:00",
            "close": "",
            "naive": "100",
            "moving_average_20": "102",
            "momentum_30": "106",
            "advanced_consensus_5d": "102.5",
            "advanced_consensus_5d_lower": "98",
            "advanced_consensus_5d_upper": "108",
            "advanced_linear_5d": "103",
            "advanced_quantile_5d": "104",
            "advanced_quantile_5d_lower": "99",
            "advanced_quantile_5d_upper": "109",
            "advanced_quantile_20d": "110",
        },
    ]

    options = forecast_chart_series_options(rows)
    runtime_series = forecast_chart_runtime_series(options)
    filtered = filter_forecast_chart_rows(
        rows,
        {"moving_average_20", "advanced_linear_5d", "advanced_quantile_5d"},
    )
    fallback_filtered = filter_forecast_chart_rows(rows, set())

    assert [(option["series"], option["default"]) for option in options] == [
        ("naive", False),
        ("moving_average_20", False),
        ("momentum_30", False),
        ("advanced_consensus_5d", True),
        ("advanced_linear_5d", False),
        ("advanced_quantile_5d", False),
        ("advanced_quantile_20d", False),
    ]
    assert runtime_series == {
        "naive",
        "moving_average_20",
        "momentum_30",
        "advanced_consensus_5d",
        "advanced_linear_5d",
        "advanced_quantile_5d",
        "advanced_quantile_20d",
    }
    assert "直近値維持" in options[0]["label"]
    assert "naive" not in filtered[0]
    assert filtered[0]["close"] == "100"
    assert filtered[1]["advanced_linear_5d"] == "103"
    assert filtered[1]["advanced_quantile_5d"] == "104"
    assert filtered[1]["advanced_quantile_5d_lower"] == "99"
    assert filtered[1]["advanced_quantile_5d_upper"] == "109"
    assert "naive" not in fallback_filtered[0]
    assert "moving_average_20" not in fallback_filtered[0]
    assert "moving_average_20" not in fallback_filtered[1]
    assert "momentum_30" not in fallback_filtered[1]
    assert fallback_filtered[1]["advanced_consensus_5d"] == "102.5"
    assert fallback_filtered[1]["advanced_consensus_5d_lower"] == "98"
    assert fallback_filtered[1]["advanced_consensus_5d_upper"] == "108"
    assert "advanced_linear_5d" not in fallback_filtered[1]
    assert "advanced_quantile_5d" not in fallback_filtered[1]
    assert "advanced_quantile_20d" not in fallback_filtered[1]


def test_render_forecast_chart_filters_adds_groups_without_fetching_again(
    monkeypatch,
):
    rows = [
        {
            "ts": "2026-06-07T00:00:00+00:00",
            "close": "100",
        },
        {
            "ts": "2026-06-12T00:00:00+00:00",
            "close": "",
            "naive": "100",
            "moving_average_20": "101",
            "momentum_30": "106",
            "advanced_consensus_5d": "102.5",
            "advanced_linear_5d": "103",
            "advanced_tree_sklearn_5d": "104",
            "advanced_quantile_5d": "105",
        },
    ]
    markdown_calls: list[str] = []
    caption_calls: list[str] = []
    checkbox_calls: list[str] = []

    monkeypatch.setattr(
        "ui.app.st.markdown",
        lambda text, *_, **__: markdown_calls.append(text),
    )
    monkeypatch.setattr(
        "ui.app.st.caption",
        lambda text, *_, **__: caption_calls.append(text),
    )
    monkeypatch.setattr(
        "ui.app.st.columns",
        lambda count, *_, **__: [_FakeExpander() for _ in range(count)],
    )
    monkeypatch.setattr(
        "ui.app.st.checkbox",
        lambda label, *_, **__: checkbox_calls.append(label) or True,
    )

    selected = _render_forecast_chart_filters(rows)

    assert selected == {
        "naive",
        "moving_average_20",
        "momentum_30",
        "advanced_consensus_5d",
        "advanced_linear_5d",
        "advanced_tree_sklearn_5d",
        "advanced_quantile_5d",
    }
    assert checkbox_calls == ["高度予測モデル", "単純予測モデル"]
    assert markdown_calls == ["#### 価格チャート / 予測スコープ"]
    assert "高度予測モデル / 単純予測モデル" in caption_calls[0]
    assert "データ取得や予測計算は走らず" in caption_calls[0]


def test_render_forecast_chart_filters_defaults_to_consensus_only(monkeypatch):
    rows = [
        {
            "ts": "2026-06-07T00:00:00+00:00",
            "close": "100",
        },
        {
            "ts": "2026-06-12T00:00:00+00:00",
            "close": "",
            "naive": "100",
            "moving_average_20": "101",
            "advanced_consensus_5d": "102.5",
            "advanced_linear_5d": "103",
        },
    ]

    monkeypatch.setattr("ui.app.st.markdown", lambda *_, **__: None)
    monkeypatch.setattr("ui.app.st.caption", lambda *_, **__: None)
    monkeypatch.setattr(
        "ui.app.st.columns",
        lambda count, *_, **__: [_FakeExpander() for _ in range(count)],
    )
    monkeypatch.setattr("ui.app.st.checkbox", lambda *_, **__: False)

    selected = _render_forecast_chart_filters(rows)

    assert selected == {"advanced_consensus_5d"}


def test_render_forecast_model_detail_keeps_advanced_cards_visible(monkeypatch):
    advanced_rows = [
        {
            "adapter": "advanced_linear",
            "horizon_days": "31",
            "forecast_close": "105",
            "predicted_return": "5.00%",
            "direction_agreement_score": "75",
            "confidence": "medium",
        },
        {
            "adapter": "advanced_tree_sklearn",
            "horizon_days": "31",
            "forecast_close": "101",
            "predicted_return": "1.00%",
            "direction_agreement_score": "60",
            "confidence": "high",
        },
    ]
    markdown_calls: list[str] = []
    caption_calls: list[str] = []
    table_labels: list[str] = []
    metric_labels: list[str] = []

    monkeypatch.setattr(
        "ui.app.st.markdown",
        lambda text, *_, **__: markdown_calls.append(text),
    )
    monkeypatch.setattr(
        "ui.app.st.caption",
        lambda text, *_, **__: caption_calls.append(text),
    )
    monkeypatch.setattr("ui.app.st.expander", lambda *_, **__: _FakeExpander())
    monkeypatch.setattr(
        "ui.app.st.columns",
        lambda count, *_, **__: [_FakeExpander() for _ in range(count)],
    )
    monkeypatch.setattr(
        "ui.app.render_metric_card",
        lambda label, *_, **__: metric_labels.append(label),
    )
    monkeypatch.setattr(
        "ui.app._render_table",
        lambda *args, **__: table_labels.append(args[1] if len(args) > 1 else ""),
    )

    _render_forecast_model_detail_expanders(
        [],
        advanced_rows,
        [],
        latest_close=Decimal("100"),
        latest_date=date(2026, 6, 8),
    )

    assert "##### 高度予測モデル" in markdown_calls
    assert any("AI予測インサイトの内訳" in text for text in caption_calls)
    assert any("高度予測: 線形モデル 31日" in text for text in markdown_calls)
    assert {"上方向 / 下方向", "モデル間の開き", "方向感"}.issubset(metric_labels)
    assert table_labels == [
        "高度予測を表示するには、もう少し長い価格データが必要です。",
        "検証指標を表示できるAI予測インサイトがありません。",
        "比較に使える予測検証データがありません。",
    ]


def test_forecast_focus_chart_rows_keeps_recent_actual_and_forecast_area():
    rows = [
        {
            "ts": "2026-04-20T00:00:00+00:00",
            "close": "90",
            "advanced_quantile_30d": "",
        },
        {
            "ts": "2026-05-01T00:00:00+00:00",
            "close": "96",
            "advanced_quantile_30d": "",
        },
        {
            "ts": "2026-05-10T00:00:00+00:00",
            "close": "100",
            "advanced_quantile_30d": "100",
            "advanced_quantile_30d_lower": "100",
            "advanced_quantile_30d_upper": "100",
        },
        {
            "ts": "2026-06-09T00:00:00+00:00",
            "close": "",
            "advanced_quantile_30d": "108",
            "advanced_quantile_30d_lower": "95",
            "advanced_quantile_30d_upper": "115",
        },
    ]

    focus_rows = forecast_focus_chart_rows(rows)

    assert [row["ts"] for row in focus_rows] == [
        "2026-05-01T00:00:00+00:00",
        "2026-05-10T00:00:00+00:00",
        "2026-06-09T00:00:00+00:00",
    ]


def test_forecast_focus_chart_title_uses_forecast_horizon():
    assert (
        forecast_focus_chart_title(
            [
                {
                    "ts": "2026-06-07T00:00:00+00:00",
                    "close": "100",
                    "advanced_consensus_31d": "105",
                }
            ]
        )
        == "予測スコープ（31日）"
    )
    assert forecast_focus_chart_title([{"ts": "2026-06-07T00:00:00+00:00"}]) == "予測スコープ"


def test_forecast_model_comparison_rows_summarize_direction_and_spread():
    rows = forecast_model_comparison_rows(
        [
            {"model": "予測: 20日移動平均", "value": "+4.99%"},
            {"model": "予測: 30日モメンタム", "value": "-14.76%"},
            {"model": "高度予測: 線形モデル 5日", "value": "+1.42%"},
        ]
    )

    assert rows[0]["value"] == "2件 / 1件"
    assert rows[1]["value"] == "19.75%"
    assert rows[1]["tone"] == "caution"
    assert rows[2]["value"] == "見方が割れています"
    assert rows[2]["tone"] == "caution"


def test_forecast_chart_palette_highlights_actual_price_first():
    domain = forecast_chart_color_domain(
        ["予測: 直近値維持", "実績価格", "予測: 30日移動平均", "実績価格"]
    )
    color_range = forecast_chart_color_range(domain)

    assert domain == ["実績価格", "予測: 直近値維持", "予測: 30日移動平均"]
    assert color_range[0] == FORECAST_ACTUAL_PRICE_COLOR
    assert color_range[1:] == list(FORECAST_MODEL_COLORS[:2])


def test_market_chart_display_guard_rejects_insufficient_or_invalid_rows():
    assert _market_chart_has_displayable_data([]) is False
    assert _market_chart_has_displayable_data([{"ts": "2026-06-18", "close": "100"}]) is False
    assert (
        _market_chart_has_displayable_data(
            [
                {"ts": "2026-06-18", "close": ""},
                {"ts": "2026-06-19", "close": "N/A"},
            ]
        )
        is False
    )
    assert (
        _market_chart_has_displayable_data(
            [
                {"ts": "2026-06-18", "close": "100"},
                {"ts": "2026-06-19", "close": "101"},
            ]
        )
        is True
    )


def test_forecast_chart_color_labels_keep_model_colors_stable_when_filtered():
    rows = [
        {
            "ts": "2026-06-07T00:00:00+00:00",
            "close": "100",
        },
        {
            "ts": "2026-06-12T00:00:00+00:00",
            "close": "",
            "naive": "100",
            "moving_average_20": "102",
            "advanced_linear_5d": "103",
        },
    ]

    full_domain = forecast_chart_color_domain(forecast_chart_series_labels(rows))
    full_colors = forecast_chart_color_range(full_domain)
    filtered_domain = forecast_chart_color_domain(
        ["実績価格", "予測: 20日移動平均", "高度予測: 線形モデル 5日"]
    )
    filtered_colors = forecast_chart_color_range(filtered_domain)

    assert full_domain == [
        "実績価格",
        "予測: 直近値維持",
        "予測: 20日移動平均",
        "高度予測: 線形モデル 5日",
    ]
    assert full_domain.index("予測: 20日移動平均") != filtered_domain.index("予測: 20日移動平均")
    assert (
        full_colors[full_domain.index("予測: 20日移動平均")]
        != filtered_colors[filtered_domain.index("予測: 20日移動平均")]
    )


def test_market_chart_currency_conversion_uses_usd_jpy_for_all_price_series():
    rows = [
        {
            "ts": "2026-06-07T00:00:00+00:00",
            "close": "100",
            "advanced_consensus_5d": "101.5",
            "advanced_consensus_5d_lower": "95",
            "advanced_consensus_5d_upper": "110",
        },
        {
            "ts": "2026-06-12T00:00:00+00:00",
            "close": "",
            "advanced_consensus_5d": "102",
            "advanced_consensus_5d_lower": "96",
            "advanced_consensus_5d_upper": "112",
        },
    ]
    fx_rows = [
        {
            "pair": "USDJPY",
            "rate": "150",
            "ts": "2026-06-07T00:00:00+00:00",
            "source": "mock",
        }
    ]

    converted = convert_market_chart_rows_currency(
        rows,
        source_currency="USD",
        display_currency="JPY",
        usd_jpy_rate=chart_fx_rate_from_rows(fx_rows),
    )

    assert converted[0]["close"] == "15000"
    assert converted[0]["advanced_consensus_5d"] == "15225"
    assert converted[0]["advanced_consensus_5d_lower"] == "14250"
    assert converted[0]["advanced_consensus_5d_upper"] == "16500"
    assert converted[1]["close"] == ""
    assert converted[1]["advanced_consensus_5d"] == "15300"


def test_market_chart_currency_conversion_can_show_jpy_source_as_usd():
    rows = [
        {"ts": "2026-06-07T00:00:00+00:00", "close": "15000", "naive": ""},
        {"ts": "2026-06-12T00:00:00+00:00", "close": "", "naive": "15150"},
    ]

    converted = convert_market_chart_rows_currency(
        rows,
        source_currency="JPY",
        display_currency="USD",
        usd_jpy_rate=Decimal("150"),
    )

    assert converted == [
        {"ts": "2026-06-07T00:00:00+00:00", "close": "100", "naive": ""},
        {"ts": "2026-06-12T00:00:00+00:00", "close": "", "naive": "101"},
    ]


def test_market_chart_currency_selector_uses_jpy_usd_only_defaults():
    assert _market_chart_currency_option_label("JPY") == "円 (JPY)"
    assert _market_chart_currency_option_label("USD") == "$ (USD)"
    assert _default_market_chart_display_currency("JPY") == "JPY"
    assert _default_market_chart_display_currency("usd") == "USD"
    assert _default_market_chart_display_currency("") == "JPY"
    assert _default_market_chart_display_currency("EUR") == "JPY"
    assert _format_market_chart_fx_rate(Decimal("161.46499633789062")) == "161.46"


def test_market_chart_currency_conversion_treats_unknown_source_as_jpy():
    rows = [{"ts": "2026-06-07T00:00:00+00:00", "close": "15000"}]

    converted = convert_market_chart_rows_currency(
        rows,
        source_currency="",
        display_currency="USD",
        usd_jpy_rate=Decimal("150"),
    )

    assert converted == [{"ts": "2026-06-07T00:00:00+00:00", "close": "100"}]


def test_market_chart_currency_conversion_keeps_values_without_fx_rate():
    rows = [{"ts": "2026-06-07T00:00:00+00:00", "close": "100"}]

    converted = convert_market_chart_rows_currency(
        rows,
        source_currency="USD",
        display_currency="JPY",
        usd_jpy_rate=None,
    )

    assert converted == rows
    assert converted is not rows


def test_latest_actual_price_frame_marks_current_price_point():
    frame = latest_actual_price_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "naive": "",
            },
            {
                "ts": "2026-05-11T00:00:00+00:00",
                "close": "188.5",
                "naive": "186.5",
            },
            {
                "ts": "2026-05-12T00:00:00+00:00",
                "close": "",
                "naive": "187",
            },
        ]
    )

    assert frame[["date", "value", "series_label", "marker_label"]].to_dict("records") == [
        {
            "date": date(2026, 5, 11),
            "value": 188.5,
            "series_label": "実績価格",
            "marker_label": "現在価格",
        }
    ]


def test_provider_error_summary_rows_explain_yahoo_dns_timeout():
    row = {
        "code": "APP-2003",
        "message": "Yahoo market-data provider request failed",
        "details": json.dumps(
            {
                "provider": "yahoo",
                "request": {
                    "error": "Failed to perform, curl: (28) Resolving timed out after 5002 milliseconds.",
                    "operation": "fetch_quotes",
                    "symbol": "9983.T",
                },
                "requires_external_opt_in": True,
                "supported_providers": ["mock", "csv"],
            },
            ensure_ascii=False,
        ),
    }

    assert provider_error_summary_rows([row]) == [
        {
            "コード": "APP-2003",
            "データ取得元": "yahoo",
            "銘柄コード": "9983.T",
            "内容": "Yahoo market-data provider request failed",
            "次の確認": (
                "yahoo への外部通信がタイムアウトしています。"
                "ネットワーク/DNS を確認し、時間をおいて再実行してください。"
                "ランキングでは銘柄数や取得期間を絞ると安定しやすくなります。"
            ),
        }
    ]

    details = json.loads(format_provider_error_details(row))
    assert details["request"]["operation"] == "fetch_quotes"
    assert details["request"]["symbol"] == "9983.T"


def test_provider_error_summary_rows_explain_ranking_no_bars():
    row = ranking_no_bars_error_row(
        provider="yahoo",
        symbol="9613.T",
        display_start=date(2026, 5, 11),
        display_end=date(2026, 5, 18),
        fetch_start=datetime(2026, 2, 17, tzinfo=UTC),
        fetch_end=datetime(2026, 5, 18, 23, 59, 59, tzinfo=UTC),
    )

    assert provider_error_summary_rows([row]) == [
        {
            "コード": "RANKING-NO-BARS",
            "データ取得元": "yahoo",
            "銘柄コード": "9613.T",
            "内容": "価格データを取得できなかったため、ランキングから除外しました。",
            "次の確認": (
                "価格データが返っていないため、ランキングから除外しています。"
                "yahoo 側の提供状況、銘柄コード、取得期間を確認してください。"
            ),
        }
    ]

    details = json.loads(format_provider_error_details(row))
    assert details["reason"] == "no_ohlcv_rows"
    assert details["request"]["display_end"] == "2026-05-18"


def test_render_market_chart_uses_currency_axis_title_and_expanded_width(monkeypatch):
    captured: dict[str, object] = {}
    markdown_calls: list[str] = []

    def fake_altair_chart(chart: object, *, use_container_width: bool = False) -> None:
        captured["spec"] = chart.to_dict(validate=True)  # type: ignore[attr-defined]
        captured["use_container_width"] = use_container_width

    monkeypatch.setattr("ui.app.st.altair_chart", fake_altair_chart)
    monkeypatch.setattr(
        "ui.app.st.markdown",
        lambda body, *args, **kwargs: markdown_calls.append(str(body)),
    )
    monkeypatch.setattr("ui.app.st.info", lambda message: None)

    _render_market_chart(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "naive": "",
            },
            {
                "ts": "2026-05-11T00:00:00+00:00",
                "close": "",
                "naive": "186.5",
            },
        ],
        currency="USD",
        title="Price and forecast",
    )

    spec = captured["spec"]
    main_spec = spec["vconcat"][0]  # type: ignore[index]
    legend_spec = spec["vconcat"][1]  # type: ignore[index]
    chart_spec = main_spec["hconcat"][0]
    focus_spec = main_spec["hconcat"][1]
    assert spec["title"] == "Price and forecast"
    assert len(spec["vconcat"]) == 2
    assert len(main_spec["hconcat"]) == 2
    assert (
        MARKET_CHART_FULL_WIDTH + MARKET_CHART_FOCUS_WIDTH + MARKET_CHART_COMBINED_SPACING <= 1280
    )
    assert chart_spec["width"] == MARKET_CHART_FULL_WIDTH
    assert focus_spec["width"] == MARKET_CHART_FOCUS_WIDTH
    assert chart_spec["height"] == MARKET_CHART_HEIGHT
    assert focus_spec["height"] == MARKET_CHART_HEIGHT
    assert chart_spec["title"] == "価格チャート"
    assert focus_spec["title"] == "予測スコープ"
    assert chart_spec["layer"][1]["mark"]["point"]["filled"] is True
    assert (
        chart_spec["layer"][1]["mark"]["point"]["size"]
        < focus_spec["layer"][1]["mark"]["point"]["size"]
    )
    assert focus_spec["layer"][1]["mark"]["point"]["filled"] is True
    assert chart_spec["layer"][2]["mark"]["strokeWidth"] == 2.8
    assert chart_spec["layer"][1]["encoding"]["color"]["legend"] is None
    assert chart_spec["layer"][1]["encoding"]["color"]["scale"]["domain"] == [
        "実績価格",
        "予測: 直近値維持",
    ]
    assert chart_spec["layer"][1]["encoding"]["strokeDash"]["legend"] is None
    assert focus_spec["layer"][1]["encoding"]["color"]["legend"] is None
    assert legend_spec["title"] == "価格・モデル"
    assert legend_spec["layer"][0]["encoding"]["color"]["scale"]["domain"] == [
        "実績価格",
        "予測: 直近値維持",
    ]
    assert chart_spec["layer"][0]["encoding"]["y"]["title"] == "終値 (USD)"
    assert captured["use_container_width"] is False
    assert markdown_calls == []
    assert any(param.get("select", {}).get("on") == "click" for param in spec["params"])


def test_render_market_chart_can_shrink_legend_without_changing_palette(monkeypatch):
    captured: dict[str, object] = {}

    def fake_altair_chart(chart: object, *, use_container_width: bool = False) -> None:
        captured["spec"] = chart.to_dict(validate=True)  # type: ignore[attr-defined]

    monkeypatch.setattr("ui.app.st.altair_chart", fake_altair_chart)
    monkeypatch.setattr("ui.app.st.markdown", lambda *_, **__: None)

    rows = [
        {
            "ts": "2026-06-07T00:00:00+00:00",
            "close": "100",
            "naive": "",
            "moving_average_20": "",
            "advanced_consensus_5d": "100",
            "advanced_linear_5d": "100",
        },
        {
            "ts": "2026-06-12T00:00:00+00:00",
            "close": "",
            "naive": "100",
            "moving_average_20": "101",
            "advanced_consensus_5d": "102.5",
            "advanced_linear_5d": "103",
        },
    ]
    _render_market_chart(
        rows,
        currency="JPY",
        color_series_labels=forecast_chart_series_labels(rows),
        legend_series_labels=["実績価格", "AI予測インサイト 5日"],
    )

    spec = captured["spec"]
    spec_text = json.dumps(spec, ensure_ascii=False, default=str)
    main_spec = spec["vconcat"][0]
    legend_spec = spec["vconcat"][1]
    chart_spec = main_spec["hconcat"][0]
    assert "smai_show_advanced_forecast_models" not in spec_text
    assert "smai_show_simple_forecast_models" not in spec_text
    assert chart_spec["layer"][1]["encoding"]["color"]["scale"]["domain"] == [
        "実績価格",
        "予測: 直近値維持",
        "予測: 20日移動平均",
        "AI予測インサイト 5日",
        "高度予測: 線形モデル 5日",
    ]
    legend_data_name = legend_spec["data"]["name"]
    assert [row["series_label"] for row in spec["datasets"][legend_data_name]] == [
        "実績価格",
        "AI予測インサイト 5日",
    ]
    assert "高度予測: 線形モデル 5日" in spec_text
    assert "予測: 直近値維持" in spec_text
    assert spec["vconcat"][1]["title"] == "価格・モデル"
    assert any(
        param.get("select", {}).get("fields") == ["series_label"] for param in spec["params"]
    )
    assert any(param.get("select", {}).get("on") == "click" for param in spec["params"])


def test_forecast_boundary_frame_marks_latest_actual_date():
    frame = forecast_boundary_frame(
        [
            {
                "ts": "2026-05-10T00:00:00+00:00",
                "close": "185",
                "naive": "",
            },
            {
                "ts": "2026-05-11T00:00:00+00:00",
                "close": "",
                "naive": "186.5",
            },
        ]
    )

    assert frame.to_dict("records") == [{"date": date(2026, 5, 10)}]


def test_forecast_metric_display_rows_and_summary_are_beginner_friendly():
    rows = [
        {
            "model": "naive",
            "symbol": "AAPL",
            "horizon_days": "10",
            "forecast_close": "221.32",
            "mae": "13.11",
            "rmse": "13.90",
            "direction_accuracy": "44.44%",
            "sample_count": "55",
        },
        {
            "model": "moving_average_3",
            "symbol": "AAPL",
            "horizon_days": "10",
            "forecast_close": "224.43",
            "mae": "13.68",
            "rmse": "14.14",
            "direction_accuracy": "46.29%",
            "sample_count": "55",
        },
    ]

    assert forecast_metric_display_rows(rows)[0] == {
        "モデル": "予測: 直近値維持",
        "銘柄": "AAPL",
        "予測日数": "10",
        "予測終値": "221.32",
        "MAE(小さいほど良い)": "13.11",
        "RMSE(小さいほど良い)": "13.90",
        "方向一致率(高いほど良い)": "44.44%",
        "評価サンプル数": "55",
    }
    summary = forecast_metric_summary(rows)
    assert "予測: 直近値維持" in summary[0]
    assert summary[1] == "誤差と方向一致率で、モデルの当たりやすさを比べます。"


def test_forecast_metric_downloads_are_stable_json_and_csv():
    rows = [
        {
            "model": "naive",
            "symbol": "AAPL",
            "horizon_days": "10",
            "forecast_close": "221.32",
            "mae": "13.11",
            "rmse": "13.90",
            "direction_accuracy": "44.44%",
            "sample_count": "55",
        }
    ]

    assert forecast_metric_json_download(rows) == (
        "[\n"
        "  {\n"
        '    "model": "naive",\n'
        '    "symbol": "AAPL",\n'
        '    "horizon_days": "10",\n'
        '    "forecast_close": "221.32",\n'
        '    "mae": "13.11",\n'
        '    "rmse": "13.90",\n'
        '    "direction_accuracy": "44.44%",\n'
        '    "sample_count": "55"\n'
        "  }\n"
        "]\n"
    )
    assert forecast_metric_csv_download(rows).decode("utf-8-sig") == (
        "model,symbol,horizon_days,forecast_close,mae,rmse,direction_accuracy,sample_count\n"
        "naive,AAPL,10,221.32,13.11,13.90,44.44%,55\n"
    )


def test_llm_factor_evidence_sources_convert_external_and_news_entries() -> None:
    fetched_at = datetime(2026, 6, 12, 9, 0, tzinfo=UTC)
    external_result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="fixture",
        fetched_at=fetched_at,
        entries=[
            ExternalResearchFetchManifestEntry(
                title="トヨタ、AIデータセンター向け成長投資を説明",
                symbol="7203.T",
                source_type="company_ir",
                source_url="https://example.com/ir/7203",
                provider="fixture",
                published_at=date(2026, 6, 12),
                fetched_at=fetched_at,
                freshness_status="latest",
                document_id="doc-1",
                content_summary="AIとデータセンター需要への対応を説明しています。",
            )
        ],
    )
    news_report = StockNewsReport(
        symbol="7203.T",
        as_of=date(2026, 6, 12),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                title="自社株買いと増配への期待が市場で注目",
                url="https://example.com/news/7203",
                source="fixture-news",
                published_at=date(2026, 6, 11),
                summary="増配と自社株買いへの期待が材料として扱われています。",
                investment_viewpoint="shareholder_return",
                sentiment_for_investment="positive",
                freshness_status="latest",
            )
        ],
    )

    sources = _llm_factor_evidence_sources(
        symbol="7203.T",
        as_of=date(2026, 6, 12),
        report=None,
        news_report=news_report,
        external_result=external_result,
    )
    result = FakeLLMFactorService().build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        evidence_sources=sources,
        generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )
    rows = _llm_factor_evidence_display_rows(result)

    assert [source.source_type for source in sources] == ["company_ir", "news"]
    assert result.bullish_factors
    assert rows[0]["種別"] == "企業IRサイト"
    assert rows[1]["種別"] == "ニュース"
    assert rows[1]["URL"] == "https://example.com/news/7203"


def test_llm_factor_panel_html_is_reference_display_and_escapes_source_text() -> None:
    source = app_module.EvidenceSource(
        title="<script>増配</script>",
        source_type="news",
        source_url="https://example.com/news/escape",
        source_date=date(2026, 6, 12),
        provider="fixture",
        summary="<b>好決算</b>と増配が確認できます。",
        reliability_score=Decimal("70"),
    )
    result = FakeLLMFactorService().build_reference_result(
        ticker="7203.T",
        as_of=date(2026, 6, 12),
        evidence_sources=[source],
        generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
    )

    html = _llm_factor_panel_html(result)

    assert "AI材料分析" in html
    assert "参考表示" in html
    assert "根拠資料の補助" in html
    assert "Ranking・予測・Investment Scoreには反映していません" in html
    assert "売買推奨ではありません" in html
    assert "&lt;script&gt;増配&lt;/script&gt;" in html
    assert "<script>増配</script>" not in html


def test_llm_factor_panel_html_shows_live_gateway_metadata() -> None:
    source = app_module.EvidenceSource(
        title="増配と自社株買いを発表",
        source_type="company_ir",
        source_url="https://example.com/ir/7203",
        source_date=date(2026, 6, 12),
        provider="fixture",
        summary="増配と自社株買いが確認できます。",
        reliability_score=Decimal("82"),
    )
    result = (
        FakeLLMFactorService()
        .build_reference_result(
            ticker="7203.T",
            as_of=date(2026, 6, 12),
            evidence_sources=[source],
            generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
        )
        .model_copy(
            update={
                "model_name": "qwen3:14b",
                "prompt_version": "llm_factor_live_mvp.v1",
                "provider": "ollama",
                "gateway_profile": "desktop_analysis",
                "sentiment_label": "positive",
                "missing_fields": ["forecast_summary"],
                "warnings": ["要確認"],
            }
        )
    )

    html = _llm_factor_panel_html(result)
    runtime_html = _llm_factor_runtime_html(result)

    assert "provider: ollama / model: qwen3:14b / profile: desktop_analysis" not in html
    assert "provider: ollama / model: qwen3:14b / profile: desktop_analysis" in runtime_html
    assert "不足項目: forecast_summary" in html


def test_llm_factor_panel_html_shows_fallback_reason() -> None:
    source = app_module.EvidenceSource(
        title="増配と自社株買いを発表",
        source_type="company_ir",
        source_url="https://example.com/ir/7203",
        source_date=date(2026, 6, 12),
        provider="fixture",
        summary="増配と自社株買いが確認できます。",
        reliability_score=Decimal("82"),
    )
    result = (
        FakeLLMFactorService()
        .build_reference_result(
            ticker="7203.T",
            as_of=date(2026, 6, 12),
            evidence_sources=[source],
            generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
        )
        .model_copy(
            update={
                "provider": "deterministic",
                "gateway_status": "fallback",
                "fallback_reason": "gateway_unavailable",
            }
        )
    )

    html = _llm_factor_panel_html(result)
    runtime_html = _llm_factor_runtime_html(result)

    assert "LLM接続: fallback" not in html
    assert "LLM Gatewayに接続できません (gateway_unavailable)" in runtime_html


def test_llm_factor_cache_caption_shows_reproducibility_metadata() -> None:
    caption = _llm_factor_cache_caption(
        LLMFactorCacheMetadata(
            status="hit",
            cache_hit=True,
            cache_key="cache-key",
            source_hash="abcdef123456",
            model_name="deterministic_fake_llm_factor",
            prompt_version="llm-factor-reference-v0",
            generated_at=datetime(2026, 6, 12, 10, 0, tzinfo=UTC),
            expires_at=datetime(2026, 6, 12, 16, 0, tzinfo=UTC),
        )
    )

    assert "cache利用" in caption
    assert "生成: 2026-06-12 10:00 UTC" in caption
    assert "model: deterministic_fake_llm_factor" in caption
    assert "prompt: llm-factor-reference-v0" in caption
    assert "source: abcdef12" in caption


def _bar(ts: str, *, close: int = 100, symbol: str = "AAPL") -> Bar:
    return Bar(
        symbol=Symbol(raw=symbol, exchange="NASDAQ", code=symbol, currency="USD"),
        ts=datetime.fromisoformat(f"{ts}T00:00:00+00:00").astimezone(UTC),
        open=Decimal(str(close)),
        high=Decimal(str(close)),
        low=Decimal(str(close)),
        close=Decimal(str(close)),
        volume=Decimal("1000"),
        interval="1d",
        provider="test",
    )


def test_ranking_detail_filters_switch_by_product_type():
    stock_filters = set(ranking_detail_filters_for_category("japan", "stock"))
    etf_filters = set(ranking_detail_filters_for_category("all", "etf"))
    mixed_filters = set(ranking_detail_filters_for_category("all", "all"))

    assert {"per", "pbr", "roe", "market_cap", "official_sector"} <= stock_filters
    assert {"benchmark_index", "expense_ratio", "complexity", "investment_theme"} <= etf_filters
    assert {"per", "pbr", "roe", "official_sector"}.isdisjoint(etf_filters)
    assert {"per", "pbr", "roe"}.isdisjoint(mixed_filters)


def test_symbol_universe_filter_value_counts_supports_detail_conditions():
    rows = symbol_universe_rows(
        [
            {
                "symbol": "7203.T",
                "name": "Toyota Motor",
                "market": "jp",
                "asset_type": "stock",
                "theme": "automotive",
                "sector": "consumer",
                "market_cap_tier": "large",
                "risk_band": "MEDIUM",
                "nisa_category": "growth",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
                "dividend_category": "dividend",
                "currency": "JPY",
                "complexity": "standard",
            },
            {
                "symbol": "SPY",
                "name": "SPDR S&P 500 ETF",
                "market": "us",
                "asset_type": "etf",
                "theme": "index",
                "sector": "index",
                "index_family": "sp500",
                "risk_band": "LOW",
                "nisa_category": "growth",
                "nisa_growth_eligible": "true",
                "nisa_tsumitate_eligible": "false",
                "dividend_category": "dividend",
                "currency": "USD",
                "complexity": "beginner",
            },
        ]
    )

    assert symbol_universe_filter_value_counts(rows, "market_cap")["large"] == 1
    assert symbol_universe_filter_value_counts(rows, "risk_band")["standard_or_lower"] == 2
    assert symbol_universe_filter_value_counts(rows, "nisa_eligibility")["eligible"] == 2
    assert symbol_universe_filter_value_counts(rows, "benchmark_index")["sp500"] == 1
    assert symbol_universe_filter_value_counts(rows, "complexity")["standard"] == 2
    assert symbol_universe_filter_value_counts(rows, "dividend_category")["dividend"] == 2
    assert symbol_universe_filter_value_counts(rows, "currency")["JPY"] == 1
    assert symbol_universe_filter_value_counts(rows, "currency")["USD"] == 1
