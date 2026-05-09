import asyncio
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from backend.core.data_contracts import DailySnapshot, FeatureSnapshot
from backend.marketdata.providers import yahoo
from ui.app import (
    default_as_of_date,
    default_market_data_end_date,
    default_market_data_start_date,
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
    build_rebalance_report_context,
    build_rebalance_request,
    current_position_rows,
    feature_snapshot_rows,
    get_rebalance_sample,
    load_rebalance_samples,
    ohlcv_summary_rows,
    proposed_trade_rows,
    provider_metadata_rows,
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
    symbol_display_name,
    symbol_reference_rows,
    table_csv_download,
    target_allocation_rows,
    target_allocations_json,
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
    assert default_market_data_start_date() == today - timedelta(days=7)


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
    assert samples["Default rebalance"].description.startswith("AAPL の買い提案")
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
    assert symbol_display_name("MSFT") == "MSFT"
    assert symbol_reference_rows() == [
        {"symbol": "7203.T", "name": "Toyota Motor"},
        {"symbol": "AAPL", "name": "Apple Inc."},
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

    assert str(exc_info.value) == "positions must be valid JSON"


def test_build_rebalance_request_rejects_non_array_targets_json():
    with pytest.raises(ValueError) as exc_info:
        build_rebalance_request(
            account_id="acct-1",
            as_of=date(2026, 4, 9),
            cash_jpy=Decimal("29000"),
            positions_json=DEFAULT_POSITIONS_JSON,
            targets_json='{"symbol": "AAPL"}',
        )

    assert str(exc_info.value) == "targets must be a JSON array"


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
        {"field": "planned_live_providers", "value": "yahoo, polygon"},
        {"field": "adapter_registered", "value": "False"},
    ]


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
    assert preview.fx_rows[0]["pair"] == "USDJPY"
    assert preview.feature_rows[0]["symbol"] == "AAPL"
    assert preview.feature_rows[0]["provider"] == "mock"
    assert preview.feature_rows[0]["feature_version"] == "feature-snapshot-v1"
    assert preview.feature_rows[0]["return_1d"] != ""
    assert preview.feature_rows[0]["momentum_5d"] == ""
    assert preview.feature_rows[0]["drawdown_20d"] != ""
    assert preview.feature_rows[0]["data_completeness"] != ""
    assert preview.feature_rows[0]["data_quality"] == "WARN"
    assert "missing:dividend_yield" in preview.feature_rows[0]["data_quality_reasons"]
    assert preview.feature_rows[0]["missing"] == "dividend_yield, market_cap_jpy, momentum_5d"
    assert preview.error_rows == []


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
    assert preview.fx_rows == []
    assert preview.feature_rows == []
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
    assert preview.fx_rows[0]["rate"] == "150.12"
    assert preview.feature_rows[0]["provider"] == "yahoo"
    assert preview.error_rows == []


def test_ohlcv_summary_rows_returns_empty_rows_for_no_bars():
    assert ohlcv_summary_rows([]) == []


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
                missing={"dividend_yield": True, "market_cap_jpy": True},
                data_quality="WARN",
                data_quality_reasons=[
                    "missing:dividend_yield",
                    "missing:market_cap_jpy",
                    "partial_data_completeness:0.62",
                ],
            )
        ],
        missing_summary={"dividend_yield": 1, "market_cap_jpy": 1},
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
            "data_quality": "WARN",
            "data_quality_reasons": (
                "missing:dividend_yield, missing:market_cap_jpy, " "partial_data_completeness:0.62"
            ),
            "missing": "dividend_yield, market_cap_jpy",
            "missing_summary": "dividend_yield: 1, market_cap_jpy: 1",
        }
    ]


class _FakeYFinance:
    def Ticker(self, raw_symbol: str) -> "_FakeTicker":
        return _FakeTicker(raw_symbol)


class _FakeTicker:
    def __init__(self, raw_symbol: str) -> None:
        self.raw_symbol = raw_symbol

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
    assert allocation_comparison_rows(result.proposal) == [
        {
            "symbol": "7203.T (Toyota Motor)",
            "current_weight": "0.5",
            "target_weight": "0.5",
            "drift": "0",
        },
        {
            "symbol": "AAPL (Apple Inc.)",
            "current_weight": "0",
            "target_weight": "0.5",
            "drift": "0.5",
        },
    ]
    assert proposed_trade_rows(result.proposal)[0]["side"] == "BUY"
    assert risk_breach_rows(result) == [
        {"breach": "R5:min_dividend_yield:AAPL"},
        {"breach": "R3:max_concentration"},
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

    assert payload.startswith("# Rebalance Check Report\n")
    assert "- Account: acct-1" in payload
    assert "- Risk status: BLOCK" in payload
    assert "- Positions: 1" in payload
    assert "## Current Positions" in payload
    assert "| symbol | qty | currency | last | fx_rate_jpy | value_jpy |" in payload
    assert "## Target Allocations" in payload
    assert "| symbol | currency | target_weight |" in payload
    assert "## Allocation Comparison" in payload
    assert "| symbol | current_weight | target_weight | drift |" in payload
    assert "## Proposed Trades" in payload
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
        assert "# Rebalance Check Report" in report_md
        assert "- Risk status: BLOCK" in report_md
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
