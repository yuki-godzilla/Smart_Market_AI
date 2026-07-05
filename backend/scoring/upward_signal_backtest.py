from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Mapping, Sequence

from backend.scoring.reversal import calculate_reversal_expectation


@dataclass(frozen=True)
class HistoricalPrice:
    trading_date: date
    close: Decimal
    benchmark_close: Decimal | None = None


@dataclass(frozen=True)
class UpwardSignalBacktestCase:
    symbol: str
    name: str
    market: str
    asset_type: str
    case_type: str
    as_of: date
    lookback_days: int
    forward_days: int
    upward_signal_score: Decimal
    upside_signal_score: Decimal
    downside_signal_score: Decimal
    risk_signal_score: Decimal
    chart_shape_label: str
    signal_reason: str
    forward_return_20d: Decimal | None
    forward_return_60d: Decimal | None
    forward_return_120d: Decimal | None
    max_drawdown_after_signal: Decimal | None
    benchmark_return: Decimal | None
    excess_return: Decimal | None
    success_flag: bool
    false_positive_flag: bool
    adjustment_note: str = ""

    def as_row(self) -> dict[str, object]:
        return asdict(self)


SignalRowBuilder = Callable[[Sequence[HistoricalPrice]], Mapping[str, object]]


def evaluate_upward_signal_case(
    *,
    symbol: str,
    prices: Sequence[HistoricalPrice],
    as_of: date,
    signal_row_builder: SignalRowBuilder,
    name: str = "",
    market: str = "",
    asset_type: str = "stock",
    case_type: str = "auto",
    lookback_days: int = 60,
    forward_days: int = 60,
) -> UpwardSignalBacktestCase:
    ordered = sorted(prices, key=lambda item: item.trading_date)
    history = [item for item in ordered if item.trading_date <= as_of]
    if not history or history[-1].trading_date != as_of:
        raise ValueError("as_of must match an available historical price")
    future = [item for item in ordered if item.trading_date > as_of]
    signal_row = {
        **signal_row_builder(tuple(history)),
        "symbol": symbol,
        "asset_type": asset_type,
    }
    signal = calculate_reversal_expectation(signal_row)
    return_20d = _forward_return(history[-1].close, future, 20)
    return_60d = _forward_return(history[-1].close, future, 60)
    return_120d = _forward_return(history[-1].close, future, 120)
    measured_return = {20: return_20d, 60: return_60d, 120: return_120d}.get(
        forward_days,
        _forward_return(history[-1].close, future, forward_days),
    )
    benchmark_return = _benchmark_return(history[-1], future, forward_days)
    excess_return = (
        measured_return - benchmark_return
        if measured_return is not None and benchmark_return is not None
        else None
    )
    success = measured_return is not None and measured_return >= Decimal("8")
    false_positive = signal.reversal_expectation_score >= Decimal("65") and not success
    return UpwardSignalBacktestCase(
        symbol=symbol,
        name=name,
        market=market,
        asset_type=asset_type,
        case_type=case_type,
        as_of=as_of,
        lookback_days=lookback_days,
        forward_days=forward_days,
        upward_signal_score=signal.reversal_expectation_score,
        upside_signal_score=_number(signal_row, "upside_signal_score"),
        downside_signal_score=_number(signal_row, "downside_signal_score"),
        risk_signal_score=_number(signal_row, "risk_signal_score"),
        chart_shape_label=signal.reversal_chart_shape_label,
        signal_reason=signal.reversal_expectation_reason,
        forward_return_20d=return_20d,
        forward_return_60d=return_60d,
        forward_return_120d=return_120d,
        max_drawdown_after_signal=_maximum_drawdown(history[-1].close, future, forward_days),
        benchmark_return=benchmark_return,
        excess_return=excess_return,
        success_flag=success,
        false_positive_flag=false_positive,
    )


def summarize_upward_signal_cases(
    cases: Sequence[UpwardSignalBacktestCase],
) -> dict[str, Decimal | int]:
    successful = [case for case in cases if case.success_flag]
    failed = [case for case in cases if not case.success_flag]
    measured = [case for case in cases if case.forward_return_60d is not None]
    excess = [case for case in cases if case.excess_return is not None]
    return {
        "case_count": len(cases),
        "success_count": len(successful),
        "failure_count": len(failed),
        "success_rate_pct": _ratio(len(successful), len(measured)),
        "market_outperformance_rate_pct": _ratio(
            sum(case.excess_return > 0 for case in excess if case.excess_return is not None),
            len(excess),
        ),
        "success_average_score": _average([case.upward_signal_score for case in successful]),
        "failure_average_score": _average([case.upward_signal_score for case in failed]),
    }


def write_upward_signal_backtest_outputs(
    cases: Sequence[UpwardSignalBacktestCase],
    output_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "backtest_upward_signal_cases.csv"
    summary_path = output_dir / "backtest_upward_signal_summary.md"
    false_positive_path = output_dir / "upward_signal_false_positive_cases.md"
    adjustments_path = output_dir / "upward_signal_logic_adjustments.md"
    rows = [case.as_row() for case in cases]
    fieldnames = list(UpwardSignalBacktestCase.__dataclass_fields__)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    summary = summarize_upward_signal_cases(cases)
    summary_path.write_text(
        "# 上向き兆候 ミニバックテスト集計\n\n"
        f"- ケース数: {summary['case_count']}\n"
        f"- 成功数: {summary['success_count']}\n"
        f"- 失敗数: {summary['failure_count']}\n"
        f"- 勝率: {summary['success_rate_pct']}%\n"
        f"- 市場平均超過率: {summary['market_outperformance_rate_pct']}%\n"
        f"- 成功例の平均スコア: {summary['success_average_score']}\n"
        f"- 失敗例の平均スコア: {summary['failure_average_score']}\n\n"
        "上向き兆候は売買推奨ではなく、深掘り確認の優先度です。\n",
        encoding="utf-8",
    )
    false_positives = [case for case in cases if case.false_positive_flag]
    false_positive_path.write_text(
        "# 上向き兆候 偽陽性ケース\n\n"
        + (
            "\n".join(
                f"- {case.symbol} / {case.as_of.isoformat()} / "
                f"{case.chart_shape_label} / score {case.upward_signal_score} / "
                f"60日 {case.forward_return_60d}"
                for case in false_positives
            )
            if false_positives
            else "該当なし"
        )
        + "\n",
        encoding="utf-8",
    )
    adjustments_path.write_text(
        "# 上向き兆候 ロジック調整メモ\n\n"
        "- 評価日時点までの価格だけをシグナル計算へ渡す。\n"
        "- 偽陽性は落ちるナイフ、上昇済み、高配当罠、材料不足の横ばいに分類する。\n"
        "- 調整後は同じ評価日で再計算し、未来リターンの閾値を後付けしない。\n",
        encoding="utf-8",
    )
    return csv_path, summary_path, false_positive_path, adjustments_path


def _forward_return(
    base_close: Decimal,
    future: Sequence[HistoricalPrice],
    days: int,
) -> Decimal | None:
    if days <= 0 or len(future) < days or base_close <= 0:
        return None
    return ((future[days - 1].close / base_close) - 1) * 100


def _benchmark_return(
    base: HistoricalPrice,
    future: Sequence[HistoricalPrice],
    days: int,
) -> Decimal | None:
    if (
        days <= 0
        or len(future) < days
        or base.benchmark_close is None
        or base.benchmark_close <= 0
        or future[days - 1].benchmark_close is None
    ):
        return None
    return ((future[days - 1].benchmark_close / base.benchmark_close) - 1) * 100


def _maximum_drawdown(
    base_close: Decimal,
    future: Sequence[HistoricalPrice],
    days: int,
) -> Decimal | None:
    window = future[:days]
    if not window or base_close <= 0:
        return None
    peak = base_close
    maximum_drawdown = Decimal("0")
    for item in window:
        peak = max(peak, item.close)
        drawdown = ((item.close / peak) - 1) * 100
        maximum_drawdown = min(maximum_drawdown, drawdown)
    return maximum_drawdown


def _number(row: Mapping[str, object], key: str) -> Decimal:
    try:
        return Decimal(str(row.get(key, "0")))
    except (ValueError, ArithmeticError):
        return Decimal("0")


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (Decimal(numerator) / Decimal(denominator) * 100).quantize(Decimal("0.01"))


def _average(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return (sum(values) / Decimal(len(values))).quantize(Decimal("0.01"))
