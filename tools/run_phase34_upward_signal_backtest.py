from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scoring.upward_signal_backtest import (  # noqa: E402
    HistoricalPrice,
    SignalRowBuilder,
    evaluate_upward_signal_case,
    write_upward_signal_backtest_outputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Join point-in-time forecast predictions to actual chart shapes.",
    )
    parser.add_argument("--ohlcv", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--validation-points", required=True)
    parser.add_argument("--output", default="reports/phase34_upward_signal")
    parser.add_argument("--horizon", type=int, default=60)
    args = parser.parse_args(argv)
    cases = run_phase34_backtest(
        Path(args.ohlcv),
        Path(args.metadata),
        Path(args.validation_points),
        horizon_days=args.horizon,
    )
    paths = write_upward_signal_backtest_outputs(cases, Path(args.output))
    print(f"phase34 upward-signal cases: {len(cases)}")
    for path in paths:
        print(path)
    return 0 if cases else 2


def run_phase34_backtest(
    ohlcv_path: Path,
    metadata_path: Path,
    validation_points_path: Path,
    *,
    horizon_days: int = 60,
):
    metadata = _metadata(metadata_path)
    bars = _bars(ohlcv_path)
    predictions = _predictions(validation_points_path, horizon_days=horizon_days)
    cases = []
    for (symbol, origin), model_predictions in sorted(predictions.items()):
        consensus = model_predictions.get("forecast_consensus")
        symbol_bars = bars.get(symbol, [])
        if consensus is None or not symbol_bars:
            continue
        prices = [HistoricalPrice(trading_date=row[0], close=row[1]) for row in symbol_bars]
        history = [row for row in symbol_bars if row[0] <= origin]
        if len(history) < 80:
            continue
        signal_row = _signal_row(history, model_predictions)
        row = metadata.get(symbol, {})
        case = evaluate_upward_signal_case(
            symbol=symbol,
            name=row.get("name") or row.get("company_name") or symbol,
            market=row.get("market") or "unknown",
            asset_type=row.get("asset_type") or "unknown",
            case_type="auto",
            prices=prices,
            as_of=origin,
            forward_days=horizon_days,
            lookback_days=60,
            signal_row_builder=_fixed_signal_row_builder(signal_row),
        )
        cases.append(replace(case, case_type=_case_type(case.chart_shape_label, row)))
    return cases


def _fixed_signal_row_builder(values: Mapping[str, object]) -> SignalRowBuilder:
    def build(_history: Sequence[HistoricalPrice]) -> Mapping[str, object]:
        return values

    return build


def _signal_row(
    history: list[tuple[date, Decimal, Decimal]],
    predictions: dict[str, Decimal],
) -> dict[str, object]:
    closes = [row[1] for row in history]
    volumes = [row[2] for row in history]
    forecast = predictions["forecast_consensus"] * 100
    model_values = [value for name, value in predictions.items() if name != "forecast_consensus"]
    up_models = sum(value > 0 for value in model_values)
    down_models = sum(value < 0 for value in model_values)
    volatility = _annualized_volatility(closes[-21:])
    downside = min(
        Decimal("100"),
        max(
            Decimal("0"),
            Decimal("35")
            + Decimal(down_models - up_models) * Decimal("10")
            + max(Decimal("0"), volatility - Decimal("25")),
        ),
    )
    recent = closes[-20:]
    return {
        "drawdown_20d": _drawdown(recent),
        "drawdown_60d": _drawdown(closes[-60:]),
        "momentum_5d": _return(closes, 5),
        "return_20d": _return(closes, 20),
        "forecast_return_pct": forecast,
        "up_model_count": up_models,
        "down_model_count": down_models,
        "upside_signal_score": _scale(forecast, Decimal("-8"), Decimal("12")),
        "downside_signal_score": downside,
        "risk_signal_score": Decimal("100") - downside,
        "advanced_forecast_upside_score": _scale(forecast, Decimal("-8"), Decimal("12")),
        "advanced_forecast_quality_score": _agreement_score(model_values),
        "data_quality_score": "85",
        "volatility_20d": volatility,
        "rsi_14": _rsi(closes),
        "recent_low_break": closes[-1] <= min(closes[-21:-1]),
        "higher_low_flag": min(closes[-10:]) > min(closes[-20:-10]),
        "volume_recovery_flag": _volume_recovery(volumes),
    }


def _predictions(path: Path, *, horizon_days: int):
    grouped: dict[tuple[str, date], dict[str, Decimal]] = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["horizon_days"]) != horizon_days:
                continue
            origin = datetime.fromisoformat(row["origin_at"]).date()
            grouped[(row["symbol"], origin)][row["model_name"]] = Decimal(row["predicted_return"])
    return grouped


def _bars(path: Path):
    grouped: dict[str, list[tuple[date, Decimal, Decimal]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            grouped[row["symbol"]].append(
                (
                    datetime.fromisoformat(row["ts"]).date(),
                    Decimal(row["close"]),
                    Decimal(row["volume"]),
                )
            )
    for rows in grouped.values():
        rows.sort(key=lambda item: item[0])
    return grouped


def _metadata(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["symbol"]: row for row in csv.DictReader(handle)}


def _return(values: list[Decimal], days: int) -> Decimal:
    if len(values) <= days or values[-days - 1] <= 0:
        return Decimal("0")
    return ((values[-1] / values[-days - 1]) - 1) * 100


def _drawdown(values: list[Decimal]) -> Decimal:
    peak = max(values)
    return Decimal("0") if peak <= 0 else ((peak - values[-1]) / peak) * 100


def _annualized_volatility(values: list[Decimal]) -> Decimal:
    returns = [float(values[index] / values[index - 1] - 1) for index in range(1, len(values))]
    if len(returns) < 2:
        return Decimal("25")
    return Decimal(str(statistics.stdev(returns) * math.sqrt(252) * 100))


def _rsi(values: list[Decimal]) -> Decimal:
    changes = [
        values[index] - values[index - 1] for index in range(max(1, len(values) - 14), len(values))
    ]
    gains = sum((max(change, Decimal("0")) for change in changes), Decimal("0"))
    losses = sum((max(-change, Decimal("0")) for change in changes), Decimal("0"))
    if gains + losses <= 0:
        return Decimal("50")
    return gains / (gains + losses) * 100


def _volume_recovery(values: list[Decimal]) -> bool:
    if len(values) < 20:
        return False
    recent = sum(values[-5:]) / Decimal("5")
    prior = sum(values[-20:-5]) / Decimal("15")
    return prior > 0 and recent >= prior * Decimal("1.15")


def _agreement_score(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("50")
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    return Decimal(max(positive, negative)) / Decimal(len(values)) * 100


def _scale(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return min(Decimal("100"), max(Decimal("0"), (value - low) / (high - low) * 100))


def _case_type(label: str, metadata: dict[str, str]) -> str:
    if metadata.get("asset_type") == "etf":
        return "etf"
    if label == "落ちるナイフ注意":
        return "falling_knife"
    if "横ばい" in label or "蓄積" in label:
        return "sideways"
    if "上昇済み" in label:
        return "already_rising"
    return "chart_shape"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
