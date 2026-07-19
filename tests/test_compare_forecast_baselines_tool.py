from decimal import Decimal

import pytest

from tools.compare_forecast_baselines import (
    ComparisonPoint,
    aggregate_comparison_points,
    render_comparison_markdown,
    rolling_origin_indexes,
)
from tools.evaluate_forecast_models import limit_recent_case_bars


def test_rolling_origin_indexes_matches_future_safe_bounds() -> None:
    assert rolling_origin_indexes(100, horizon_days=20, max_origins=3) == [43, 61, 79]
    assert rolling_origin_indexes(100, horizon_days=60, max_origins=3) == []


def test_rolling_origin_indexes_uses_latest_origin_when_one_is_requested() -> None:
    assert rolling_origin_indexes(120, horizon_days=20, max_origins=1) == [99]


def test_aggregate_comparison_points_calculates_rmse_and_direction() -> None:
    points = [
        _point(predicted="0.10", actual="0.20", symbol="AAA"),
        _point(predicted="-0.10", actual="0.10", symbol="BBB"),
    ]

    metrics = aggregate_comparison_points(points)
    overall = next(metric for metric in metrics if metric.group_type == "overall")

    assert overall.symbol_count == 2
    assert overall.sample_count == 2
    assert overall.mae == Decimal("0.1500")
    assert overall.rmse == Decimal("0.1581")
    assert overall.direction_accuracy == Decimal("0.5000")


def test_render_comparison_markdown_names_rmse_and_direction_winners() -> None:
    points = [
        _point(predicted="0.10", actual="0.20", model_name="alpha"),
        _point(predicted="-0.01", actual="0.20", model_name="beta"),
    ]
    markdown = render_comparison_markdown(aggregate_comparison_points(points))

    assert "lowest RMSE: `alpha`" in markdown
    assert "best direction: `alpha`" in markdown
    assert "単一指標だけで採用しない" in markdown


def test_rolling_origin_indexes_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError, match="horizon_days"):
        rolling_origin_indexes(100, horizon_days=0, max_origins=3)
    with pytest.raises(ValueError, match="max_origins"):
        rolling_origin_indexes(100, horizon_days=20, max_origins=0)


def test_limit_recent_case_bars_keeps_original_case_unchanged() -> None:
    class _Bar:
        def __init__(self, ts: int) -> None:
            self.ts = ts

    class _Case:
        def __init__(self) -> None:
            self.bars = [_Bar(index) for index in range(150)]

        def model_copy(self, *, update):
            copied = _Case()
            copied.bars = update["bars"]
            return copied

    case = _Case()
    limited = limit_recent_case_bars([case], 120)

    assert len(case.bars) == 150
    assert len(limited[0].bars) == 120
    assert limited[0].bars[0].ts == 30


def test_limit_recent_case_bars_rejects_too_small_window() -> None:
    with pytest.raises(ValueError, match="at least 120"):
        limit_recent_case_bars([], 119)


def _point(
    *,
    predicted: str,
    actual: str,
    symbol: str = "AAA",
    model_name: str = "model",
) -> ComparisonPoint:
    return ComparisonPoint(
        split="tuning",
        symbol=symbol,
        market="us",
        asset_type="stock",
        regime="sideways",
        model_name=model_name,
        horizon_days=20,
        origin_at="2025-01-01T00:00:00+00:00",
        target_at="2025-01-29T00:00:00+00:00",
        predicted_return=Decimal(predicted),
        actual_return=Decimal(actual),
    )
