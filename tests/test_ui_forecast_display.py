from datetime import date

from ui.app import (
    forecast_boundary_frame,
    forecast_metric_display_rows,
    forecast_metric_summary,
    market_chart_long_frame,
)


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

    assert frame.to_dict("records") == [
        {
            "date": date(2026, 5, 10),
            "label": "ここから先は将来予測",
        }
    ]


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
    assert "売買推奨ではありません" in summary[1]
