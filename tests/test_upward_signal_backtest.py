from datetime import date, timedelta
from decimal import Decimal

from backend.scoring.upward_signal_backtest import (
    HistoricalPrice,
    evaluate_upward_signal_case,
    summarize_upward_signal_cases,
    write_upward_signal_backtest_outputs,
)


def _prices(*, rising: bool = True) -> list[HistoricalPrice]:
    start = date(2025, 1, 1)
    rows: list[HistoricalPrice] = []
    for index in range(181):
        before_signal = Decimal("100") - Decimal(index) / Decimal("10")
        after_signal = Decimal("94") + Decimal(index - 60) / Decimal("5")
        falling = Decimal("94") - Decimal(index - 60) / Decimal("10")
        close = before_signal if index <= 60 else (after_signal if rising else falling)
        rows.append(
            HistoricalPrice(
                trading_date=start + timedelta(days=index),
                close=close,
                benchmark_close=Decimal("100") + Decimal(index) / Decimal("20"),
            )
        )
    return rows


def _signal_row(history):
    assert history[-1].trading_date == date(2025, 3, 2)
    return {
        "drawdown_20d": "-8",
        "momentum_5d": "-1",
        "return_20d": "-3",
        "forecast_return_pct": "6",
        "up_model_count": "3",
        "down_model_count": "1",
        "upside_signal_score": "70",
        "downside_signal_score": "40",
        "risk_signal_score": "70",
        "data_quality_score": "85",
    }


def test_backtest_uses_only_prices_available_at_as_of_and_calculates_forward_metrics():
    case = evaluate_upward_signal_case(
        symbol="AAA",
        prices=_prices(),
        as_of=date(2025, 3, 2),
        signal_row_builder=_signal_row,
    )

    assert case.forward_return_20d is not None
    assert case.forward_return_60d is not None
    assert case.forward_return_120d is not None
    assert case.max_drawdown_after_signal is not None
    assert case.benchmark_return is not None
    assert case.excess_return == case.forward_return_60d - case.benchmark_return
    assert case.success_flag


def test_backtest_summary_separates_success_and_failure_scores():
    success = evaluate_upward_signal_case(
        symbol="UP",
        prices=_prices(),
        as_of=date(2025, 3, 2),
        signal_row_builder=_signal_row,
    )
    failure = evaluate_upward_signal_case(
        symbol="DOWN",
        prices=_prices(rising=False),
        as_of=date(2025, 3, 2),
        signal_row_builder=_signal_row,
    )

    summary = summarize_upward_signal_cases([success, failure])

    assert summary["case_count"] == 2
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["success_rate_pct"] == Decimal("50.00")
    assert summary["top_ten_success_count"] == 1
    assert failure.false_positive_flag


def test_backtest_writes_the_four_required_artifacts(tmp_path):
    case = evaluate_upward_signal_case(
        symbol="AAA",
        prices=_prices(),
        as_of=date(2025, 3, 2),
        signal_row_builder=_signal_row,
    )

    paths = write_upward_signal_backtest_outputs([case], tmp_path)

    assert [path.name for path in paths] == [
        "backtest_upward_signal_cases.csv",
        "backtest_upward_signal_summary.md",
        "upward_signal_false_positive_cases.md",
        "upward_signal_logic_adjustments.md",
    ]
    assert all(path.exists() for path in paths)
    assert "upward_signal_score" in paths[0].read_text(encoding="utf-8-sig")
