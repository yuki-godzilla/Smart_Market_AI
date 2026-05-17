from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from backend.core.data_contracts import Bar, Symbol
from backend.screening import ScreeningScore
from ui.app import (
    _market_data_preview_symbol_label,
    _name_from_candidate,
    _rank_investment_score_rows,
    _render_market_chart,
    _symbol_from_candidate,
    apply_ranking_filter_state,
    apply_ranking_weight_preset,
    default_forecast_horizon_days,
    default_market_data_provider,
    filter_symbol_universe_rows,
    forecast_boundary_frame,
    forecast_chart_summary,
    forecast_consensus_display_rows,
    forecast_metric_display_rows,
    forecast_metric_summary,
    investment_score_display_rows,
    investment_score_summary_lines,
    market_chart_long_frame,
    merged_symbol_candidate_rows,
    ranking_filter_signature,
    ranking_period_dates,
    ranking_period_label,
    ranking_symbol_options,
    ranking_symbols_state_key,
    ranking_weight_preset_label,
    score_component_rows,
    symbol_candidate_label,
    symbol_candidate_labels,
    symbol_universe_rows,
    sync_ranking_selection_state,
    valid_ranking_selected_labels,
)
from ui.rebalance_app import (
    forecast_consensus_rows_for_bars,
    forecast_metric_csv_download,
    forecast_metric_json_download,
    forecast_reference_period,
    screening_score_rows,
)
from ui.symbol_universe import symbol_universe_csv_rows


def test_default_forecast_horizon_days_uses_chart_period():
    assert default_forecast_horizon_days(date(2026, 5, 1), date(2026, 5, 7)) == 1
    assert default_forecast_horizon_days(date(2026, 5, 1), date(2026, 5, 30)) == 3
    assert default_forecast_horizon_days(date(2026, 1, 1), date(2026, 12, 31)) == 30


def test_market_data_provider_defaults_to_yahoo():
    assert default_market_data_provider() == "yahoo"


def test_symbol_from_candidate_extracts_ticker_or_custom():
    assert _symbol_from_candidate("") is None
    assert _symbol_from_candidate("9983.T - Fast Retailing") == "9983.T"


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


def test_filter_symbol_universe_rows_finds_curated_dividend_candidates():
    rows = symbol_universe_rows(
        [
            {"symbol": "9432.T", "name": "Nippon Telegraph and Telephone"},
            {"symbol": "8058.T", "name": "Mitsubishi Corporation"},
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
    ] == ["9432.T", "8058.T"]


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
            min_dividend_yield_pct="3.0",
        )
    ] == ["PFE"]


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


def test_valid_ranking_selected_labels_keeps_only_available_options():
    assert valid_ranking_selected_labels(
        ["7203.T - Toyota Motor", "OLD - Removed"],
        ["7203.T - Toyota Motor", "9983.T - Fast Retailing"],
    ) == ["7203.T - Toyota Motor"]


def test_sync_ranking_selection_state_updates_widget_and_persistent_state(monkeypatch):
    session_state: dict[str, object] = {}
    monkeypatch.setattr("ui.app.st.session_state", session_state)

    sync_ranking_selection_state(
        "market_data_ranking_symbols_test",
        ["7203.T - Toyota Motor"],
    )

    assert session_state["market_data_ranking_selected_labels"] == ["7203.T - Toyota Motor"]
    assert session_state["market_data_ranking_symbols_test"] == ["7203.T - Toyota Motor"]


def test_apply_ranking_filter_state_selects_filtered_candidates(monkeypatch):
    session_state = {
        "market_data_ranking_rows": [{"symbol": "OLD"}],
        "market_data_ranking_error_rows": [{"symbol": "ERR"}],
        "market_data_ranking_filter_dialog_open": True,
    }
    monkeypatch.setattr("ui.app.st.session_state", session_state)
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

    assert ranking_period_label("short") == "短期: 1週間"
    assert ranking_period_dates("short", end) == (date(2026, 5, 10), end)
    assert ranking_period_dates("medium", end) == (date(2026, 4, 17), end)
    assert ranking_period_dates("long", end) == (date(2025, 5, 17), end)


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
            "モデル一致度": "中くらい",
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
                "agreement": "MEDIUM",
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

    assert messages[0] == "3 つの予測モデルの見方は「中くらい」です。予測の開きは 1.90% です。"
    assert messages[1] == (
        "実線はこれまでの価格、点線はモデルごとの予測です。"
        "点線同士が近いほど、モデルの見方が近い状態です。"
    )
    assert "予測: 直近値維持" in messages[2]


def test_investment_score_display_rows_are_beginner_friendly():
    assert investment_score_display_rows(
        [
            {
                "rank": "1",
                "symbol": "AAPL",
                "total_score": "73",
                "score_band": "BALANCED",
                "screening_score": "80",
                "forecast_agreement_score": "40",
                "data_quality_score": "100",
                "risk_signal_score": "",
                "warnings": "model_disagreement:high",
                "note": "売買推奨ではなく、判断材料を整理したスコアです。",
            }
        ]
    ) == [
        {
            "順位": "1",
            "銘柄": "AAPL",
            "銘柄名": "Apple Inc.",
            "総合スコア": "73",
            "見方": "バランス型",
            "Screening": "80",
            "予測一致": "40",
            "データ品質": "100",
            "Risk": "未接続",
            "注意点": "モデルの見方が割れています",
            "補足": "売買推奨ではなく、判断材料を整理したスコアです。",
        }
    ]


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
            "予測一致": "40",
            "Risk": "70",
            "データ品質": "100",
        }
    ) == [
        {"要素": "Screening", "スコア": "80"},
        {"要素": "Forecast", "スコア": "40"},
        {"要素": "Risk", "スコア": "70"},
        {"要素": "Data Quality", "スコア": "100"},
    ]


def test_rank_investment_score_rows_sorts_and_reassigns_rank():
    assert _rank_investment_score_rows(
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
                "data_quality_score": "50",
                "risk_signal_score": "60",
                "warnings": "",
            },
        ],
        "forecast",
    )

    assert rows[0]["symbol"] == "FORECAST"
    assert rows[0]["rank"] == "1"
    assert rows[0]["total_score"] == "74.5"
    assert rows[0]["score_band"] == "BALANCED"
    assert rows[0]["note"] == (
        "予測一致重視で並べ替えています。売買推奨ではなく、深掘り候補の整理です。"
    )
    assert rows[1]["symbol"] == "QUALITY"
    assert ranking_weight_preset_label("forecast") == "予測一致重視"


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


def test_render_market_chart_uses_currency_axis_title_and_compact_width(monkeypatch):
    captured: dict[str, object] = {}

    def fake_altair_chart(chart: object, *, use_container_width: bool = False) -> None:
        captured["spec"] = chart.to_dict(validate=True)  # type: ignore[attr-defined]
        captured["use_container_width"] = use_container_width

    monkeypatch.setattr("ui.app.st.altair_chart", fake_altair_chart)
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
    chart_spec = spec["hconcat"][0]  # type: ignore[index]
    assert spec["title"] == "Price and forecast"
    assert chart_spec["width"] == 1400
    assert chart_spec["layer"][0]["encoding"]["y"]["title"] == "終値 (USD)"
    assert captured["use_container_width"] is True


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
    assert forecast_metric_csv_download(rows) == (
        "model,symbol,horizon_days,forecast_close,mae,rmse,direction_accuracy,sample_count\n"
        "naive,AAPL,10,221.32,13.11,13.90,44.44%,55\n"
    )


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
