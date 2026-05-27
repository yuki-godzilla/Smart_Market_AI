import asyncio
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pandas as pd
import pytest

from backend.core.data_contracts import (
    Bar,
    DailySnapshot,
    FeatureSnapshot,
    FundamentalSnapshot,
    FxRate,
    Symbol,
)
from backend.core.errors import DataSourceError, ProviderUnavailableError
from backend.marketdata.providers import yahoo
from ui.app import (
    REBALANCE_REQUEST_STATE_KEY,
    REBALANCE_RESULT_STATE_KEY,
    allocation_chart_frame,
    default_as_of_date,
    default_market_data_end_date,
    default_market_data_start_date,
    market_chart_frame,
    market_chart_long_frame,
    rebalance_flow_rows,
    rebalance_result_from_state,
    risk_breach_display_rows,
    risk_breach_message,
)
from ui.rebalance_app import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_AS_OF,
    DEFAULT_CASH_JPY,
    DEFAULT_POSITIONS_JSON,
    DEFAULT_TARGETS_JSON,
    PROJECT_ROOT,
    SCENARIO_DIR_ENV,
    RebalanceScenarioError,
    allocation_comparison_rows,
    build_default_rebalance_request,
    build_market_data_preview,
    build_rebalance_decision_report_context,
    build_rebalance_report_context,
    build_rebalance_request,
    current_position_rows,
    feature_snapshot_rows,
    forecast_chart_rows,
    forecast_consensus_rows_for_bars,
    get_rebalance_sample,
    investment_score_csv_download,
    investment_score_json_download,
    investment_score_rows,
    load_rebalance_samples,
    ohlcv_summary_rows,
    price_chart_rows,
    proposed_trade_rows,
    provider_metadata_rows,
    rebalance_decision_report_json_download,
    rebalance_decision_report_manifest_download,
    rebalance_decision_report_markdown_download,
    rebalance_decision_report_zip_download,
    rebalance_sample_names,
    rebalance_scenario_dir,
    request_json_download,
    result_json_download,
    result_markdown_report_download,
    result_report_manifest_download,
    result_report_zip_download,
    result_summary,
    risk_breach_rows,
    run_rebalance_check,
    runtime_settings_summary,
    sample_widget_key,
    screening_score_csv_download,
    screening_score_json_download,
    screening_score_rows,
    symbol_display_name,
    symbol_reference_rows,
    table_csv_download,
    target_allocation_rows,
    target_allocations_json,
    yfinance_search_symbol_rows,
)

FIXTURE_ROOT = Path("tests/fixtures")


def test_build_rebalance_request_from_default_ui_json():
    request = build_rebalance_request(
        account_id=DEFAULT_ACCOUNT_ID,
        as_of=DEFAULT_AS_OF,
        cash_jpy=DEFAULT_CASH_JPY,
        positions_json=DEFAULT_POSITIONS_JSON,
        targets_json=DEFAULT_TARGETS_JSON,
    )

    assert request.account_id == DEFAULT_ACCOUNT_ID
    assert request.positions[0].symbol == "7203.T"
    assert request.targets[1].symbol == "AAPL"
    assert request.cash_jpy == DEFAULT_CASH_JPY


def test_app_date_defaults_use_current_date():
    today = date.today()

    assert default_as_of_date() == today
    assert default_market_data_end_date() == today
    assert default_market_data_start_date() == date(today.year - 1, today.month, today.day)


def test_market_chart_frame_uses_date_index_and_numeric_columns():
    frame = market_chart_frame(
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

    assert [value.isoformat() for value in frame.index] == ["2026-05-10", "2026-05-11"]
    assert frame["close"].iloc[0] == 185
    assert pd.isna(frame["close"].iloc[1])
    assert frame["naive"].iloc[1] == 186.5


def test_market_chart_long_frame_marks_actual_and_forecast_lines():
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

    assert frame[["series", "value", "line_type"]].to_dict("records") == [
        {"series": "close", "value": 185.0, "line_type": "actual"},
        {"series": "naive", "value": 186.5, "line_type": "forecast"},
    ]


def test_build_default_rebalance_request_matches_ui_defaults():
    request = build_default_rebalance_request()

    assert request.account_id == DEFAULT_ACCOUNT_ID
    assert request.as_of == DEFAULT_AS_OF
    assert request.cash_jpy == DEFAULT_CASH_JPY
    assert request.positions[0].symbol == "7203.T"
    assert request.targets[1].symbol == "AAPL"


def test_rebalance_samples_include_no_trades_case():
    sample_names = rebalance_sample_names()
    sample = get_rebalance_sample("No trades")

    assert sample_names == ["Default rebalance", "No trades"]
    assert sample.cash_jpy == Decimal("0")
    assert '"target_weight": "1.0"' in sample.targets_json


def test_load_rebalance_samples_from_json_files():
    samples = load_rebalance_samples()

    assert list(samples) == ["Default rebalance", "No trades"]
    assert samples["Default rebalance"].cash_jpy == Decimal("29000")
    assert samples["Default rebalance"].description.startswith("AAPL の配分見直し候補")
    assert samples["No trades"].cash_jpy == Decimal("0")


def test_rebalance_samples_can_use_configured_scenario_dir(monkeypatch):
    monkeypatch.setenv(
        SCENARIO_DIR_ENV,
        "tests/fixtures/rebalance_scenarios_custom",
    )

    assert rebalance_scenario_dir() == PROJECT_ROOT / "tests/fixtures/rebalance_scenarios_custom"
    assert rebalance_sample_names() == ["Custom cash scenario"]
    sample = get_rebalance_sample("Custom cash scenario")
    assert sample.cash_jpy == Decimal("1000")
    assert (
        sample.description == "設定されたシナリオディレクトリから読み込まれるテスト用シナリオです。"
    )


def test_configured_rebalance_scenario_dir_must_exist(monkeypatch):
    monkeypatch.setenv(
        SCENARIO_DIR_ENV,
        "tests/fixtures/rebalance_scenarios_missing",
    )

    with pytest.raises(RebalanceScenarioError) as exc_info:
        rebalance_sample_names()

    assert "Rebalance scenario directory does not exist" in str(exc_info.value)
    assert "rebalance_scenarios_missing" in str(exc_info.value)


def test_rebalance_scenario_path_must_be_directory(monkeypatch):
    monkeypatch.setenv(
        SCENARIO_DIR_ENV,
        "examples/rebalance_scenarios/default_rebalance.json",
    )

    with pytest.raises(RebalanceScenarioError) as exc_info:
        rebalance_sample_names()

    assert "Rebalance scenario path must be a directory" in str(exc_info.value)


def test_load_rebalance_samples_reports_invalid_files():
    with pytest.raises(RebalanceScenarioError) as exc_info:
        load_rebalance_samples(FIXTURE_ROOT / "rebalance_scenarios_invalid")

    message = str(exc_info.value)
    assert message.startswith("Invalid rebalance scenario file(s):")
    assert "bad_json.json" in message
    assert "invalid JSON" in message
    assert "invalid_request.json" in message
    assert "request does not match rebalance-check schema" in message
    assert "invalid_description.json" in message
    assert "scenario description must be a string" in message
    assert "missing_name.json" in message
    assert "scenario requires a non-empty name" in message


def test_load_rebalance_samples_reports_duplicate_names():
    with pytest.raises(RebalanceScenarioError) as exc_info:
        load_rebalance_samples(FIXTURE_ROOT / "rebalance_scenarios_duplicate")

    assert "Duplicate rebalance scenario name: Same scenario" in str(exc_info.value)


def test_get_rebalance_sample_rejects_unknown_name():
    with pytest.raises(ValueError) as exc_info:
        get_rebalance_sample("missing")

    assert str(exc_info.value) == "Unknown rebalance sample: missing"


def test_sample_widget_key_is_stable_and_sample_specific():
    assert sample_widget_key("Default rebalance", "cash_jpy") == (
        "sample_default_rebalance_cash_jpy"
    )
    assert sample_widget_key("No trades", "cash_jpy") == "sample_no_trades_cash_jpy"


def test_target_allocations_json_builds_current_mvp_symbol_targets():
    payload = target_allocations_json(
        toyota_weight=Decimal("0.75"),
        apple_weight=Decimal("0.25"),
    )

    assert '"symbol": "7203.T"' in payload
    assert '"target_weight": "0.75"' in payload
    assert '"symbol": "AAPL"' in payload
    assert '"target_weight": "0.25"' in payload


def test_symbol_display_helpers_explain_current_mvp_symbols():
    assert symbol_display_name("AAPL") == "AAPL (Apple Inc.)"
    assert symbol_display_name("7203.T") == "7203.T (Toyota Motor)"
    assert symbol_display_name("MSFT") == "MSFT (Microsoft)"
    rows = symbol_reference_rows()
    assert len(rows) >= 80
    assert {"symbol": "7203.T", "name": "Toyota Motor", "yahoo_symbol": ""} in rows
    assert {"symbol": "9983.T", "name": "Fast Retailing", "yahoo_symbol": ""} in rows
    assert {"symbol": "AAPL", "name": "Apple Inc.", "yahoo_symbol": ""} in rows
    assert {"symbol": "MSFT", "name": "Microsoft", "yahoo_symbol": ""} in rows
    assert {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "yahoo_symbol": ""} in rows


def test_yfinance_search_symbol_rows_returns_empty_for_blank_query():
    assert yfinance_search_symbol_rows("") == []


def test_yfinance_search_symbol_rows_maps_quote_candidates(monkeypatch):
    class FakeSearch:
        def __init__(self, query: str, **kwargs: object) -> None:
            assert query == "toyota"
            assert kwargs["session"] == "shared-session"
            self.quotes = [
                {"symbol": "TM", "shortname": "Toyota Motor ADR"},
                {"symbol": "7203.T", "longname": "Toyota Motor Corporation"},
                {"symbol": ""},
            ]

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Search=FakeSearch))
    monkeypatch.setattr("ui.rebalance_app.shared_yfinance_session", lambda: "shared-session")

    assert yfinance_search_symbol_rows("toyota") == [
        {"symbol": "TM", "name": "Toyota Motor ADR"},
        {"symbol": "7203.T", "name": "Toyota Motor Corporation"},
    ]


def test_build_rebalance_request_rejects_invalid_positions_json():
    with pytest.raises(ValueError) as exc_info:
        build_rebalance_request(
            account_id="acct-1",
            as_of=date(2026, 4, 9),
            cash_jpy=Decimal("29000"),
            positions_json="{invalid",
            targets_json=DEFAULT_TARGETS_JSON,
        )

    assert str(exc_info.value) == "現在保有は有効なJSONで入力してください。"


def test_build_rebalance_request_rejects_non_array_targets_json():
    with pytest.raises(ValueError) as exc_info:
        build_rebalance_request(
            account_id="acct-1",
            as_of=date(2026, 4, 9),
            cash_jpy=Decimal("29000"),
            positions_json=DEFAULT_POSITIONS_JSON,
            targets_json='{"symbol": "AAPL"}',
        )

    assert str(exc_info.value) == "目標配分はJSON配列で入力してください。"


def test_runtime_settings_summary_reports_default_provider(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)
    monkeypatch.delenv(SCENARIO_DIR_ENV, raising=False)

    summary = runtime_settings_summary()

    assert summary["provider"] == "mock"
    assert summary["config_file"] == "defaults"
    assert summary["csv_data_dir"] == "data/marketdata"
    assert summary["scenario_dir"] == str(PROJECT_ROOT / "examples/rebalance_scenarios")


def test_provider_metadata_rows_include_default_provider_details(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)

    assert provider_metadata_rows("mock") == [
        {"field": "provider", "value": "mock"},
        {"field": "registered", "value": "True"},
        {"field": "implemented", "value": "True"},
        {"field": "deterministic", "value": "True"},
        {"field": "requires_external_opt_in", "value": "False"},
        {"field": "supported_providers", "value": "mock, csv"},
        {"field": "implemented_live_providers", "value": "yahoo"},
        {"field": "planned_live_providers", "value": "polygon"},
        {"field": "adapter_registered", "value": "False"},
    ]


def test_provider_metadata_rows_reports_yahoo_live_adapter_as_implemented():
    rows = provider_metadata_rows("yahoo")

    assert {"field": "provider", "value": "yahoo"} in rows
    assert {"field": "implemented", "value": "True"} in rows
    assert {"field": "live_adapter", "value": "implemented_opt_in"} in rows
    assert {"field": "requires_external_opt_in", "value": "True"} in rows


def test_build_market_data_preview_returns_mock_rows(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)

    preview = asyncio.run(
        build_market_data_preview(
            symbol="AAPL",
            start=date(2026, 4, 7),
            end=date(2026, 4, 9),
        )
    )

    assert preview.status == "OK"
    assert preview.quote_rows[0]["symbol"] == "AAPL"
    assert preview.quote_rows[0]["last"] == "175"
    assert preview.ohlcv_rows == [
        {
            "symbol": "AAPL",
            "bars": "3",
            "first_ts": "2026-04-07T00:00:00+00:00",
            "last_ts": "2026-04-09T00:00:00+00:00",
            "first_close": "170",
            "last_close": "175",
            "total_volume": "182000000",
            "provider": "mock",
        }
    ]
    assert preview.price_chart_rows == [
        {"ts": "2026-04-07T00:00:00+00:00", "close": "170"},
        {"ts": "2026-04-08T00:00:00+00:00", "close": "173"},
        {"ts": "2026-04-09T00:00:00+00:00", "close": "175"},
    ]
    assert preview.forecast_chart_rows == [
        {"ts": "2026-04-07T00:00:00+00:00", "close": "170"},
        {"ts": "2026-04-08T00:00:00+00:00", "close": "173", "naive": "170"},
        {"ts": "2026-04-09T00:00:00+00:00", "close": "175", "naive": "173"},
        {
            "ts": "2026-04-10T00:00:00+00:00",
            "close": "",
            "naive": "175",
            "moving_average_3": "172.6667",
        },
    ]
    assert preview.forecast_metric_rows == [
        {
            "model": "naive",
            "symbol": "AAPL",
            "horizon_days": "1",
            "forecast_close": "175",
            "mae": "2.5",
            "rmse": "2.5495",
            "direction_accuracy": "0.00%",
            "sample_count": "2",
        },
        {
            "model": "moving_average_3",
            "symbol": "AAPL",
            "horizon_days": "1",
            "forecast_close": "172.6667",
            "mae": "0",
            "rmse": "0",
            "direction_accuracy": "0.00%",
            "sample_count": "0",
        },
    ]
    assert preview.fx_rows[0]["pair"] == "USDJPY"
    assert preview.feature_rows[0]["symbol"] == "AAPL"
    assert preview.feature_rows[0]["provider"] == "mock"
    assert preview.feature_rows[0]["feature_version"] == "feature-snapshot-v1"
    assert preview.feature_rows[0]["return_1d"] != ""
    assert preview.feature_rows[0]["momentum_5d"] == ""
    assert preview.feature_rows[0]["drawdown_20d"] != ""
    assert preview.feature_rows[0]["data_completeness"] != ""
    assert preview.feature_rows[0]["dividend_yield"] == "0.50%"
    assert preview.feature_rows[0]["market_cap_jpy"] == "450000000000000"
    assert preview.feature_rows[0]["data_quality"] == "WARN"
    assert preview.feature_rows[0]["data_quality_reasons"] == (
        "missing:momentum_5d, partial_data_completeness:0.14"
    )
    assert preview.feature_rows[0]["missing"] == "momentum_5d"
    assert len(preview.screening_rows) == 1
    assert preview.screening_rows[0]["rank"] == "1"
    assert preview.screening_rows[0]["symbol"] == "AAPL"
    assert preview.screening_rows[0]["total_score"] != ""
    assert preview.screening_rows[0]["data_quality"] == "WARN"
    assert len(preview.investment_score_rows) == 1
    assert preview.investment_score_rows[0]["rank"] == "1"
    assert preview.investment_score_rows[0]["symbol"] == "AAPL"
    assert preview.investment_score_rows[0]["total_score"] != ""
    assert preview.investment_score_rows[0]["note"] == (
        "売買推奨ではなく、判断材料を整理したスコアです。"
    )
    assert preview.error_rows == []


def test_build_market_data_preview_reuses_ohlcv_for_quote_and_features(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)
    adapter = _CountingMarketDataPreviewAdapter()
    monkeypatch.setattr(
        "ui.rebalance_app.create_market_data_provider_adapter",
        lambda _: adapter,
    )

    preview = asyncio.run(
        build_market_data_preview(
            symbol="AAPL",
            start=date(2026, 4, 7),
            end=date(2026, 4, 9),
        )
    )

    assert preview.status == "OK"
    assert adapter.fetch_ohlcv_calls == 1
    assert adapter.fetch_quotes_calls == 0
    assert adapter.get_fx_rates_calls == 1
    assert adapter.fetch_fundamentals_calls == 1
    assert preview.quote_rows[0]["last"] == "175"
    assert preview.feature_rows[0]["provider"] == "mock"
    assert preview.error_rows == []


def test_build_market_data_preview_skips_yahoo_aux_fetch_on_initial_fetch(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)
    adapter = _OptionalDataFailurePreviewAdapter()
    monkeypatch.setattr(
        "ui.rebalance_app.create_market_data_provider_adapter",
        lambda _: adapter,
    )

    preview = asyncio.run(
        build_market_data_preview(
            symbol="AAPL",
            start=date(2026, 4, 7),
            end=date(2026, 4, 9),
            provider_override="yahoo",
        )
    )

    assert preview.status == "OK"
    assert preview.price_chart_rows
    assert preview.quote_rows[0]["last"] == "175"
    assert preview.fx_rows == []
    assert preview.feature_rows[0]["provider"] == "yahoo"
    assert preview.screening_rows[0]["data_quality"] == "WARN"
    assert adapter.get_fx_rates_calls == 0
    assert adapter.fetch_fundamentals_calls == 0
    assert preview.error_rows == []


def test_build_market_data_preview_skips_yahoo_aux_fetch_for_japan_symbol(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)
    adapter = _OptionalDataFailurePreviewAdapter()
    monkeypatch.setattr(
        "ui.rebalance_app.create_market_data_provider_adapter",
        lambda _: adapter,
    )

    preview = asyncio.run(
        build_market_data_preview(
            symbol="7203.T",
            start=date(2026, 4, 7),
            end=date(2026, 4, 9),
            provider_override="yahoo",
        )
    )

    assert preview.status == "OK"
    assert preview.price_chart_rows
    assert preview.fx_rows == []
    assert preview.feature_rows[0]["provider"] == "yahoo"
    assert adapter.get_fx_rates_calls == 0
    assert adapter.fetch_fundamentals_calls == 0
    assert preview.error_rows == []


def test_build_market_data_preview_uses_selected_forecast_horizon(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)

    preview = asyncio.run(
        build_market_data_preview(
            symbol="AAPL",
            start=date(2026, 4, 7),
            end=date(2026, 4, 9),
            forecast_horizon_days=2,
        )
    )

    assert preview.forecast_chart_rows == [
        {"ts": "2026-04-07T00:00:00+00:00", "close": "170"},
        {"ts": "2026-04-08T00:00:00+00:00", "close": "173"},
        {"ts": "2026-04-09T00:00:00+00:00", "close": "175", "naive": "170"},
        {
            "ts": "2026-04-11T00:00:00+00:00",
            "close": "",
            "naive": "175",
            "moving_average_3": "172.6667",
        },
    ]
    assert preview.forecast_metric_rows[0]["horizon_days"] == "2"
    assert preview.forecast_metric_rows[0]["sample_count"] == "1"


def test_build_market_data_preview_returns_provider_error(monkeypatch):
    monkeypatch.setenv(
        "SMAI_CONFIG_FILE",
        "tests/fixtures/config/live_provider_no_opt_in.yaml",
    )

    preview = asyncio.run(
        build_market_data_preview(
            symbol="AAPL",
            start=date(2026, 4, 7),
            end=date(2026, 4, 9),
        )
    )

    assert preview.status == "ERROR"
    assert preview.quote_rows == []
    assert preview.ohlcv_rows == []
    assert preview.price_chart_rows == []
    assert preview.forecast_chart_rows == []
    assert preview.forecast_metric_rows == []
    assert preview.fx_rows == []
    assert preview.feature_rows == []
    assert preview.investment_score_rows == []
    assert preview.screening_rows == []
    assert preview.error_rows[0]["code"] == "APP-2000"
    assert preview.error_rows[0]["message"] == "Live market-data provider requires explicit opt-in"
    assert "explicit_config_required" in preview.error_rows[0]["details"]


def test_build_market_data_preview_returns_yahoo_live_rows(monkeypatch):
    monkeypatch.setenv(
        "SMAI_CONFIG_FILE",
        "tests/fixtures/config/live_provider_yahoo_opt_in.yaml",
    )
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: _FakeYFinance())

    preview = asyncio.run(
        build_market_data_preview(
            symbol="AAPL",
            start=date(2026, 4, 7),
            end=date(2026, 4, 9),
        )
    )

    assert preview.status == "OK"
    assert preview.quote_rows[0]["last"] == "175.25"
    assert preview.ohlcv_rows[0]["provider"] == "yahoo"
    assert preview.forecast_chart_rows[-1]["naive"] == "175.25"
    assert preview.forecast_metric_rows[0]["model"] == "naive"
    assert preview.fx_rows == []
    assert preview.feature_rows[0]["provider"] == "yahoo"
    assert preview.investment_score_rows[0]["total_score"] != ""
    assert preview.screening_rows[0]["total_score"] != ""
    assert preview.error_rows == []


def test_build_market_data_preview_can_override_provider_from_ui(monkeypatch):
    monkeypatch.delenv("SMAI_CONFIG_FILE", raising=False)
    monkeypatch.setattr(yahoo, "_load_yfinance", lambda: _FakeYFinance())

    preview = asyncio.run(
        build_market_data_preview(
            symbol="AAPL",
            start=date(2026, 4, 7),
            end=date(2026, 4, 9),
            provider_override="yahoo",
        )
    )

    assert preview.status == "OK"
    assert preview.provider_rows[0] == {"field": "provider", "value": "yahoo"}
    assert preview.ohlcv_rows[0]["provider"] == "yahoo"


def test_ohlcv_summary_rows_returns_empty_rows_for_no_bars():
    assert ohlcv_summary_rows([]) == []


def test_price_chart_rows_formats_close_history():
    rows = price_chart_rows(
        [
            _bar("AAPL", "2026-04-09T00:00:00Z", "175"),
            _bar("AAPL", "2026-04-08T00:00:00Z", "172"),
        ]
    )

    assert rows == [
        {"ts": "2026-04-08T00:00:00+00:00", "close": "172"},
        {"ts": "2026-04-09T00:00:00+00:00", "close": "175"},
    ]


def test_forecast_chart_rows_places_latest_point_on_selected_horizon():
    rows = forecast_chart_rows(
        [
            _bar("AAPL", "2026-04-07T00:00:00Z", "170"),
            _bar("AAPL", "2026-04-08T00:00:00Z", "173"),
            _bar("AAPL", "2026-04-09T00:00:00Z", "175"),
        ],
        horizon_days=3,
    )

    assert rows[-1] == {
        "ts": "2026-04-12T00:00:00+00:00",
        "close": "",
        "naive": "175",
        "moving_average_3": "172.6667",
    }


def test_forecast_consensus_rows_tolerates_cached_old_summarizer(monkeypatch):
    def old_summarizer(_evaluations: object) -> SimpleNamespace:
        return SimpleNamespace(
            symbol="AAPL",
            horizon_days=1,
            model_count=3,
            ensemble_forecast_close=Decimal("175"),
            median_forecast_close=Decimal("175"),
            min_forecast_close=Decimal("174"),
            max_forecast_close=Decimal("176"),
            forecast_range=Decimal("2"),
            forecast_range_pct=Decimal("0.0114"),
            agreement="MEDIUM",
        )

    monkeypatch.setattr("ui.rebalance_app._summarize_forecast_evaluations", old_summarizer)

    rows = forecast_consensus_rows_for_bars(
        [
            _bar("AAPL", "2026-04-07T00:00:00Z", "170"),
            _bar("AAPL", "2026-04-08T00:00:00Z", "173"),
            _bar("AAPL", "2026-04-09T00:00:00Z", "175"),
        ],
    )

    assert rows[0]["direction_signal_label"] == "NEUTRAL"
    assert rows[0]["latest_close"] == "175"
    assert rows[0]["up_model_count"] == "0"
    assert rows[0]["down_model_count"] == "1"
    assert rows[0]["direction_net_score"] == "43.34"


def _bar(symbol: str, ts: str, close: str) -> Bar:
    return Bar(
        symbol=Symbol(raw=symbol, exchange="NASDAQ", code=symbol, currency="USD"),
        ts=datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC),
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1000"),
        interval="1d",
        provider="test",
    )


def test_feature_snapshot_rows_formats_missing_summary():
    snapshot = FeatureSnapshot(
        as_of=date(2026, 4, 9),
        provider="mock",
        rows=[
            DailySnapshot(
                symbol="AAPL",
                as_of=date(2026, 4, 9),
                return_1d=Decimal("0.00564480874316939890710383"),
                momentum_5d=Decimal("0.027932960893854748603351955"),
                vol_20d=Decimal("0.06411361410463315"),
                drawdown_20d=Decimal("0.005405405405405405405405405405"),
                data_completeness=Decimal("0.619047619047619047619047619"),
                dividend_yield=Decimal("0.005"),
                market_cap_jpy=Decimal("450000000000000"),
                missing={"momentum_5d": True},
                data_quality="WARN",
                data_quality_reasons=[
                    "missing:momentum_5d",
                    "partial_data_completeness:0.62",
                ],
            )
        ],
        missing_summary={"momentum_5d": 1},
        quality_summary={"WARN": 1},
    )

    assert feature_snapshot_rows(snapshot) == [
        {
            "symbol": "AAPL",
            "as_of": "2026-04-09",
            "provider": "mock",
            "feature_version": "feature-snapshot-v1",
            "last": "",
            "close_1d": "",
            "return_1d": "0.56%",
            "momentum_5d": "2.79%",
            "adv_20d": "",
            "vol_20d": "6.41%",
            "drawdown_20d": "0.54%",
            "data_completeness": "61.90%",
            "dividend_yield": "0.50%",
            "market_cap_jpy": "450000000000000",
            "data_quality": "WARN",
            "data_quality_reasons": ("missing:momentum_5d, partial_data_completeness:0.62"),
            "missing": "momentum_5d",
            "missing_summary": "momentum_5d: 1",
        }
    ]


def test_screening_score_rows_formats_score_breakdown():
    from backend.screening import ScreeningScore

    rows = screening_score_rows(
        [
            ScreeningScore(
                rank=1,
                symbol="AAPL",
                total_score=Decimal("81.23"),
                momentum_score=Decimal("70.00"),
                liquidity_score=Decimal("100.00"),
                risk_score=Decimal("90.00"),
                data_quality_score=Decimal("60.00"),
                data_quality="WARN",
                summary="AAPL は中立寄りの候補です。",
                reason_labels=["期待する履歴データのうち 60% 程度しかそろっていません。"],
                reasons=["partial_data_completeness:0.60"],
            )
        ]
    )

    assert rows == [
        {
            "rank": "1",
            "symbol": "AAPL",
            "total_score": "81.23",
            "momentum_score": "70",
            "liquidity_score": "100",
            "risk_score": "90",
            "data_quality_score": "60",
            "forecast_score": "50",
            "forecast_agreement": "",
            "data_quality": "WARN",
            "summary": "AAPL は中立寄りの候補です。",
            "forecast_reason": "",
            "reason_labels": "期待する履歴データのうち 60% 程度しかそろっていません。",
            "reasons": "partial_data_completeness:0.60",
        }
    ]


def test_investment_score_rows_formats_score_breakdown():
    from backend.scoring import InvestmentScore, InvestmentScoreBreakdown

    rows = investment_score_rows(
        [
            InvestmentScore(
                rank=1,
                symbol="AAPL",
                total_score=Decimal("73.00"),
                score_band="BALANCED",
                screening_score=Decimal("80"),
                forecast_agreement_score=Decimal("40"),
                data_quality_score=Decimal("100"),
                forecast_agreement="LOW",
                data_quality="OK",
                breakdown=[
                    InvestmentScoreBreakdown(
                        component="screening",
                        input_score=Decimal("80"),
                        weight=Decimal("0.50"),
                        contribution=Decimal("40"),
                    ),
                    InvestmentScoreBreakdown(
                        component="forecast_agreement",
                        input_score=Decimal("40"),
                        weight=Decimal("0.20"),
                        contribution=Decimal("8"),
                    ),
                ],
                warnings=["model_disagreement:high"],
                reasons=["forecast_agreement:low", "model_disagreement:high"],
            )
        ]
    )

    assert rows == [
        {
            "rank": "1",
            "symbol": "AAPL",
            "total_score": "73",
            "score_band": "BALANCED",
            "screening_score": "80",
            "forecast_agreement_score": "40",
            "upside_signal_score": "50",
            "downside_signal_score": "50",
            "direction_net_score": "50",
            "direction_signal_label": "UNKNOWN",
            "forecast_return_pct": "0.00%",
            "up_model_count": "0",
            "down_model_count": "0",
            "flat_model_count": "0",
            "data_quality_score": "100",
            "risk_signal_score": "",
            "forecast_agreement": "LOW",
            "data_quality": "OK",
            "breakdown": (
                "screening: 80 x 0.5 = 40; forecast_agreement: 40 x 0.2 = 8"
            ),
            "warnings": "model_disagreement:high",
            "reasons": "forecast_agreement:low, model_disagreement:high",
            "note": "売買推奨ではなく、判断材料を整理したスコアです。",
        }
    ]


def test_screening_score_downloads_export_ranked_rows():
    rows = [
        {
            "rank": "1",
            "symbol": "AAPL",
            "total_score": "81.23",
            "momentum_score": "70",
            "liquidity_score": "100",
            "risk_score": "90",
            "data_quality_score": "60",
            "forecast_score": "",
            "forecast_agreement": "",
            "data_quality": "WARN",
            "summary": "AAPL は中立寄りの候補です。",
            "forecast_reason": "",
            "reason_labels": "期待する履歴データのうち 60% 程度しかそろっていません。",
            "reasons": "partial_data_completeness:0.60",
        }
    ]

    assert '"symbol": "AAPL"' in screening_score_json_download(rows)
    assert screening_score_csv_download(rows) == (
        "rank,symbol,total_score,momentum_score,liquidity_score,risk_score,"
        "data_quality_score,forecast_score,forecast_agreement,data_quality,summary,"
        "forecast_reason,reason_labels,reasons\n"
        "1,AAPL,81.23,70,100,90,60,,,WARN,AAPL は中立寄りの候補です。,,"
        "期待する履歴データのうち 60% 程度しかそろっていません。,"
        "partial_data_completeness:0.60\n"
    )


def test_investment_score_downloads_export_ranked_rows():
    rows = [
        {
            "rank": "1",
            "symbol": "AAPL",
            "total_score": "73",
            "score_band": "BALANCED",
            "screening_score": "80",
            "forecast_agreement_score": "40",
            "data_quality_score": "100",
            "risk_signal_score": "",
            "forecast_agreement": "LOW",
            "data_quality": "OK",
            "breakdown": "screening: 80 x 0.5 = 40",
            "warnings": "model_disagreement:high",
            "reasons": "forecast_agreement:low, model_disagreement:high",
            "note": "売買推奨ではなく、判断材料を整理したスコアです。",
        }
    ]

    assert '"symbol": "AAPL"' in investment_score_json_download(rows)
    assert investment_score_csv_download(rows) == (
        "rank,symbol,total_score,score_band,screening_score,forecast_agreement_score,"
        "upside_signal_score,downside_signal_score,direction_net_score,direction_signal_label,"
        "forecast_return_pct,up_model_count,down_model_count,flat_model_count,data_quality_score,"
        "database_fit_score,metadata_confidence_score,research_score,risk_signal_score,ranking_profile,"
        "forecast_agreement,data_quality,breakdown,warnings,reasons,note\n"
        "1,AAPL,73,BALANCED,80,40,,,,,,,,,100,,,,,,LOW,OK,screening: 80 x 0.5 = 40,"
        "model_disagreement:high,\"forecast_agreement:low, model_disagreement:high\","
        "売買推奨ではなく、判断材料を整理したスコアです。\n"
    )


class _FakeYFinance:
    def Ticker(self, raw_symbol: str, session: object | None = None) -> "_FakeTicker":
        del session
        return _FakeTicker(raw_symbol)

    def download(self, **kwargs: object) -> pd.DataFrame:
        tickers = str(kwargs["tickers"]).split()
        fields = ["Open", "High", "Low", "Close", "Volume"]
        columns = pd.MultiIndex.from_product([tickers, fields])
        rows = []
        for base in [Decimal("170"), Decimal("175")]:
            row = []
            for _ticker in tickers:
                row.extend(
                    [
                        base - Decimal("1"),
                        base + Decimal("1"),
                        base - Decimal("2"),
                        base + (Decimal("0.25") if base == 175 else Decimal("0.5")),
                        Decimal("60000000"),
                    ]
                )
            rows.append(row)
        return pd.DataFrame(
            rows,
            columns=columns,
            index=pd.to_datetime(["2026-04-08T00:00:00Z", "2026-04-09T00:00:00Z"]),
        )


class _CountingMarketDataPreviewAdapter:
    def __init__(self) -> None:
        self.fetch_ohlcv_calls = 0
        self.fetch_quotes_calls = 0
        self.get_fx_rates_calls = 0
        self.fetch_fundamentals_calls = 0

    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        interval: str = "1d",
    ) -> list[Bar]:
        assert len(symbols) == 1
        assert start <= datetime(2026, 4, 7, tzinfo=UTC)
        assert end >= datetime(2026, 4, 9, tzinfo=UTC)
        assert interval == "1d"
        self.fetch_ohlcv_calls += 1
        symbol = symbols[0]
        return [
            _bar(symbol, "2026-04-07T00:00:00Z", "170"),
            _bar(symbol, "2026-04-08T00:00:00Z", "173"),
            _bar(symbol, "2026-04-09T00:00:00Z", "175"),
        ]

    async def fetch_quotes(self, symbols: list[str], at: datetime | None = None) -> object:
        self.fetch_quotes_calls += 1
        raise AssertionError("build_market_data_preview should derive quotes from OHLCV bars")

    async def get_fx_rates(
        self,
        pairs: list[str],
        at: datetime | None = None,
        method: str = "spot",
    ) -> list[FxRate]:
        assert pairs == ["USDJPY"]
        assert method == "spot"
        self.get_fx_rates_calls += 1
        return [FxRate(pair="USDJPY", rate=Decimal("150"), ts=at or datetime.now(UTC))]

    async def fetch_fundamentals(
        self,
        symbols: list[str],
        as_of: date,
    ) -> list[FundamentalSnapshot]:
        assert len(symbols) == 1
        self.fetch_fundamentals_calls += 1
        symbol = symbols[0]
        return [
            FundamentalSnapshot(
                symbol=symbol,
                as_of=as_of,
                provider="mock",
                dividend_yield=Decimal("0.005"),
                market_cap_jpy=Decimal("450000000000000"),
            )
        ]

    def healthcheck(self) -> dict[str, str]:
        return {"provider": "mock", "status": "ok"}


class _OptionalDataFailurePreviewAdapter(_CountingMarketDataPreviewAdapter):
    async def get_fx_rates(
        self,
        pairs: list[str],
        at: datetime | None = None,
        method: str = "spot",
    ) -> list[FxRate]:
        self.get_fx_rates_calls += 1
        raise DataSourceError(
            "FX unavailable",
            details={"provider": "yahoo", "request": {"operation": "get_fx_rates"}},
        )

    async def fetch_fundamentals(
        self,
        symbols: list[str],
        as_of: date,
    ) -> list[FundamentalSnapshot]:
        self.fetch_fundamentals_calls += 1
        raise ProviderUnavailableError(
            "Fundamentals unavailable",
            details={
                "provider": "yahoo",
                "request": {"operation": "fetch_fundamentals", "symbol": symbols[0]},
            },
        )

    def healthcheck(self) -> dict[str, str]:
        return {"provider": "yahoo", "status": "ok"}


class _FakeTicker:
    def __init__(self, raw_symbol: str) -> None:
        self.raw_symbol = raw_symbol
        self.info = {
            "dividendYield": Decimal("0.006"),
            "marketCap": Decimal("3200000000000"),
            "currency": "USD",
        }

    def history(self, **_: object) -> pd.DataFrame:
        if self.raw_symbol == "JPY=X":
            return pd.DataFrame(
                {
                    "Open": [Decimal("149.80")],
                    "High": [Decimal("150.50")],
                    "Low": [Decimal("149.70")],
                    "Close": [Decimal("150.12")],
                    "Volume": [Decimal("0")],
                },
                index=pd.to_datetime(["2026-04-09T00:00:00Z"]),
            )
        return pd.DataFrame(
            {
                "Open": [Decimal("169.0"), Decimal("174.0")],
                "High": [Decimal("171.0"), Decimal("176.0")],
                "Low": [Decimal("168.0"), Decimal("173.0")],
                "Close": [Decimal("170.5"), Decimal("175.25")],
                "Volume": [Decimal("61000000"), Decimal("62000000")],
            },
            index=pd.to_datetime(["2026-04-08T00:00:00Z", "2026-04-09T00:00:00Z"]),
        )


def test_rebalance_result_formatters_create_table_rows():
    request = build_rebalance_request(
        account_id="acct-1",
        as_of=date(2026, 4, 9),
        cash_jpy=Decimal("29000"),
        positions_json=DEFAULT_POSITIONS_JSON,
        targets_json=DEFAULT_TARGETS_JSON,
    )
    result = asyncio.run(run_rebalance_check(request))

    summary = result_summary(result)
    assert summary["account_id"] == "acct-1"
    assert summary["trade_count"] == "1"
    assert summary["risk_status"] == "BLOCK"

    assert current_position_rows(result.proposal)[0]["symbol"] == "7203.T (Toyota Motor)"
    assert target_allocation_rows(result.proposal)[1]["symbol"] == "AAPL (Apple Inc.)"
    assert target_allocation_rows(result.proposal)[1]["target_weight"] == "50.00%"
    assert allocation_comparison_rows(result.proposal) == [
        {
            "symbol": "7203.T (Toyota Motor)",
            "current_weight": "50.00%",
            "target_weight": "50.00%",
            "drift": "0.00%",
        },
        {
            "symbol": "AAPL (Apple Inc.)",
            "current_weight": "0.00%",
            "target_weight": "50.00%",
            "drift": "50.00%",
        },
    ]
    assert proposed_trade_rows(result.proposal)[0]["side"] == "BUY"
    assert risk_breach_rows(result) == [
        {"breach": "R5:min_dividend_yield:AAPL"},
        {"breach": "R3:max_concentration"},
    ]


def test_rebalance_cockpit_helpers_translate_flow_and_risk_breaches():
    summary = {
        "total_value_jpy": "58076",
        "trade_count": "2",
        "risk_status": "BLOCK",
    }

    assert rebalance_flow_rows(summary) == [
        {"step": "現在", "value": "58076 JPY"},
        {"step": "目標", "value": "目標配分"},
        {"step": "見直し候補", "value": "2件"},
        {"step": "リスク判定", "value": "見直し優先"},
    ]
    assert risk_breach_message("R5:min_dividend_yield:AAPL") == (
        "AAPL は配当利回りの条件を満たしていない可能性があります。"
    )
    assert risk_breach_display_rows(
        [{"breach": "R3:max_concentration"}]
    ) == [
        {
            "確認事項": "R3:max_concentration",
            "確認ポイント": "1銘柄への集中度が高くなっています。目標配分を確認してください。",
        }
    ]


def test_allocation_chart_frame_converts_percent_rows():
    frame = allocation_chart_frame(
        [
            {
                "symbol": "AAPL (Apple Inc.)",
                "current_weight": "0.00%",
                "target_weight": "50.00%",
                "drift": "50.00%",
            }
        ]
    )

    assert frame.to_dict("records") == [
        {"symbol": "AAPL (Apple Inc.)", "type": "現在", "weight": 0.0},
        {"symbol": "AAPL (Apple Inc.)", "type": "目標", "weight": 50.0},
    ]


def test_build_rebalance_report_context_reuses_result_table_rows():
    request = build_default_rebalance_request()
    result = asyncio.run(run_rebalance_check(request))

    context = build_rebalance_report_context(result)

    assert context.summary["risk_status"] == "BLOCK"
    assert context.current_rows == current_position_rows(result.proposal)
    assert context.target_rows == target_allocation_rows(result.proposal)
    assert context.allocation_rows == allocation_comparison_rows(result.proposal)
    assert context.trade_rows == proposed_trade_rows(result.proposal)
    assert context.breach_rows == risk_breach_rows(result)


def test_build_rebalance_decision_report_context_uses_phase19_schema():
    request = build_default_rebalance_request()
    result = asyncio.run(run_rebalance_check(request))

    context = build_rebalance_decision_report_context(result, request=request)
    markdown = rebalance_decision_report_markdown_download(context)
    payload = rebalance_decision_report_json_download(context)
    manifest = rebalance_decision_report_manifest_download(context)
    archive = rebalance_decision_report_zip_download(context)

    assert context.title == "投資判断レポート - リバランス acct-1"
    assert [section.title for section in context.sections] == [
        "リバランス概要",
        "現在保有",
        "目標配分",
        "配分差分",
        "配分見直し候補",
        "リスク制約違反",
        "確認ポイント",
    ]
    assert context.sections[0].summary["risk_status"] == "BLOCK"
    assert context.sections[0].summary["positions"] == "1"
    assert "売買推奨ではありません" in markdown
    assert "リスク判定は BLOCK" in markdown
    assert '"rebalance"' in payload
    assert '"decision_report.md"' in manifest
    assert archive.startswith(b"PK")


def test_rebalance_result_from_state_returns_stored_result(monkeypatch):
    request = build_default_rebalance_request()
    result = asyncio.run(run_rebalance_check(request))
    monkeypatch.setattr(
        "ui.app.st.session_state",
        {
            REBALANCE_RESULT_STATE_KEY: result,
            REBALANCE_REQUEST_STATE_KEY: request,
        },
    )

    assert rebalance_result_from_state() == (result, request)


def test_rebalance_result_from_state_ignores_incomplete_state(monkeypatch):
    monkeypatch.setattr("ui.app.st.session_state", {REBALANCE_RESULT_STATE_KEY: object()})

    assert rebalance_result_from_state() is None


def test_result_json_download_contains_portfolio_risk_result():
    request = build_default_rebalance_request()
    result = asyncio.run(run_rebalance_check(request))

    payload = result_json_download(result)

    assert '"proposal"' in payload
    assert '"risk_decision"' in payload
    assert '"status": "BLOCK"' in payload


def test_request_json_download_contains_validated_rebalance_request():
    request = build_default_rebalance_request()

    payload = request_json_download(request)

    assert '"account_id": "acct-1"' in payload
    assert '"cash_jpy": "29000"' in payload
    assert '"positions"' in payload


def test_result_markdown_report_download_summarizes_result():
    request = build_default_rebalance_request()
    result = asyncio.run(run_rebalance_check(request))

    payload = result_markdown_report_download(result, request=request)

    assert payload.startswith("# リバランス確認レポート\n")
    assert "- 口座ID: acct-1" in payload
    assert "- リスク判定: BLOCK" in payload
    assert "- 現在保有: 1件" in payload
    assert "## 現在の保有" in payload
    assert "| 銘柄コード | 数量 | 通貨 | 現在値 | 為替レート(円) | 評価額(円) |" in payload
    assert "## 目標配分" in payload
    assert "| 銘柄コード | 通貨 | 目標比率 |" in payload
    assert "## 配分比較" in payload
    assert "| 銘柄コード | 現在比率 | 目標比率 | 差分 |" in payload
    assert "## 配分見直し候補" in payload
    assert "| AAPL (Apple Inc.) | BUY |" in payload
    assert "- R5:min_dividend_yield:AAPL" in payload


def test_table_csv_download_writes_stable_header_and_rows():
    payload = table_csv_download(
        [
            {"symbol": "7203.T", "qty": "10"},
            {"symbol": "AAPL", "qty": "1.5"},
        ]
    )

    assert payload == "symbol,qty\n7203.T,10\nAAPL,1.5\n"


def test_table_csv_download_can_write_header_for_empty_rows():
    payload = table_csv_download([], fieldnames=["symbol", "qty"])

    assert payload == "symbol,qty\n"


def test_result_report_zip_download_contains_json_and_csv_files():
    request = build_default_rebalance_request()
    result = asyncio.run(run_rebalance_check(request))

    payload = result_report_zip_download(result, request=request)

    with ZipFile(BytesIO(payload)) as archive:
        assert archive.namelist() == [
            "rebalance_allocation_comparison.csv",
            "rebalance_check_result.json",
            "rebalance_current_positions.csv",
            "rebalance_proposed_trades.csv",
            "rebalance_report.md",
            "rebalance_report_manifest.json",
            "rebalance_request.json",
            "rebalance_risk_breaches.csv",
            "rebalance_summary.csv",
            "rebalance_target_allocations.csv",
        ]
        assert '"status": "BLOCK"' in archive.read("rebalance_check_result.json").decode("utf-8")
        assert '"account_id": "acct-1"' in archive.read("rebalance_request.json").decode("utf-8")
        report_md = archive.read("rebalance_report.md").decode("utf-8")
        assert "# リバランス確認レポート" in report_md
        assert "- リスク判定: BLOCK" in report_md
        manifest = archive.read("rebalance_report_manifest.json").decode("utf-8")
        assert '"schema_version": "rebalance-report-v1"' in manifest
        assert '"risk_status": "BLOCK"' in manifest
        assert "rebalance_report.md" in manifest
        assert "rebalance_request.json" in manifest
        assert "rebalance_summary.csv" in manifest
        summary_csv = archive.read("rebalance_summary.csv").decode("utf-8")
        assert "risk_status" in summary_csv
        assert "BLOCK" in summary_csv


def test_result_report_manifest_download_describes_report_files():
    request = build_default_rebalance_request()
    result = asyncio.run(run_rebalance_check(request))

    payload = result_report_manifest_download(result)

    assert '"schema_version": "rebalance-report-v1"' in payload
    assert '"account_id": "acct-1"' in payload
    assert '"risk_status": "BLOCK"' in payload
    assert "rebalance_proposed_trades.csv" in payload
