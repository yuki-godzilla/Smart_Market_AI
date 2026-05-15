from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from backend.core.data_contracts import Bar, Symbol
from backend.screening import ScreeningScore
from ui.app import (
    _market_data_preview_symbol_label,
    _name_from_candidate,
    _render_market_chart,
    _symbol_from_candidate,
    default_forecast_horizon_days,
    default_market_data_provider,
    forecast_boundary_frame,
    forecast_consensus_display_rows,
    forecast_metric_display_rows,
    forecast_metric_summary,
    investment_score_display_rows,
    market_chart_long_frame,
    merged_symbol_candidate_rows,
    symbol_candidate_labels,
)
from ui.rebalance_app import (
    forecast_consensus_rows_for_bars,
    forecast_metric_csv_download,
    forecast_metric_json_download,
    forecast_reference_period,
    screening_score_rows,
)


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
