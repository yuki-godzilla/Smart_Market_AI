from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from pydantic import Field

from backend.core.data_contracts import Bar, Currency, StrictBaseModel, Symbol
from backend.forecast.evaluation import ForecastEvaluationCase


class ForecastDatasetCoverageRow(StrictBaseModel):
    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    bar_count: int = Field(ge=0)
    eligible: bool
    regime: str = Field(min_length=1)
    reason: str = Field(min_length=1)


MAX_ABSOLUTE_DAILY_RETURN = Decimal("0.55")


class ForecastDatasetLoadResult(StrictBaseModel):
    cases: list[ForecastEvaluationCase]
    coverage: list[ForecastDatasetCoverageRow]
    required_bar_count: int = Field(ge=1)


def load_forecast_evaluation_dataset(
    ohlcv_path: Path,
    metadata_path: Path,
    *,
    required_bar_count: int = 180,
    end_at: datetime | None = None,
) -> ForecastDatasetLoadResult:
    """Load deterministic local CSV evaluation cases without provider access.

    When ``end_at`` is supplied, future bars are removed before eligibility,
    regime, and price-discontinuity checks.  This keeps historical replication
    cohorts independent from data that was not available at their cutoff.
    """

    if required_bar_count < 80:
        raise ValueError("required_bar_count must be at least 80")
    if end_at is not None and end_at.tzinfo is None:
        raise ValueError("end_at must be timezone-aware")
    metadata = _load_metadata(metadata_path)
    bars_by_symbol = _load_bars(ohlcv_path, metadata, end_at=end_at)
    cases: list[ForecastEvaluationCase] = []
    coverage: list[ForecastDatasetCoverageRow] = []
    for raw_symbol in sorted(bars_by_symbol):
        row = metadata.get(raw_symbol, {})
        market = row.get("market") or "unknown"
        asset_type = row.get("asset_type") or "unknown"
        bars = sorted(bars_by_symbol.get(raw_symbol, []), key=lambda bar: bar.ts)
        regime = _classify_regime(bars)
        extreme_jump = _maximum_absolute_daily_return(bars)
        eligible = len(bars) >= required_bar_count and extreme_jump <= MAX_ABSOLUTE_DAILY_RETURN
        if len(bars) < required_bar_count:
            reason = f"insufficient_bars:{len(bars)}/{required_bar_count}"
        elif extreme_jump > MAX_ABSOLUTE_DAILY_RETURN:
            reason = f"extreme_price_jump:{extreme_jump}"
        else:
            reason = "eligible"
        coverage.append(
            ForecastDatasetCoverageRow(
                symbol=raw_symbol,
                market=market,
                asset_type=asset_type,
                bar_count=len(bars),
                eligible=eligible,
                regime=regime,
                reason=reason,
            )
        )
        if eligible:
            cases.append(
                ForecastEvaluationCase(
                    symbol=raw_symbol,
                    bars=bars,
                    market=market,
                    asset_type=asset_type,
                    regime=regime,
                )
            )
    return ForecastDatasetLoadResult(
        cases=cases,
        coverage=coverage,
        required_bar_count=required_bar_count,
    )


def write_forecast_dataset_coverage(
    result: ForecastDatasetLoadResult,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "forecast_model_dataset_coverage.csv"
    markdown_path = output_dir / "forecast_model_dataset_coverage.md"
    fieldnames = list(ForecastDatasetCoverageRow.model_fields)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in result.coverage:
            writer.writerow(row.model_dump(mode="json"))
    eligible = sum(1 for row in result.coverage if row.eligible)
    lines = [
        "# Forecast Model Dataset Coverage",
        "",
        f"- 必要bar数: {result.required_bar_count}",
        f"- 確認symbol数: {len(result.coverage)}",
        f"- 評価可能symbol数: {eligible}",
        f"- 評価不足symbol数: {len(result.coverage) - eligible}",
        "",
        "| Symbol | Market | Asset type | Bars | Regime | Status |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    lines.extend(
        f"| {row.symbol} | {row.market} | {row.asset_type} | {row.bar_count} | "
        f"{row.regime} | {row.reason} |"
        for row in result.coverage
    )
    markdown_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {"coverage_csv": csv_path, "coverage_markdown": markdown_path}


def _load_metadata(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"metadata CSV not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["symbol"].strip(): row
            for row in csv.DictReader(handle)
            if row.get("symbol", "").strip()
        }


def _load_bars(
    path: Path,
    metadata: dict[str, dict[str, str]],
    *,
    end_at: datetime | None = None,
) -> dict[str, list[Bar]]:
    if not path.is_file():
        raise ValueError(f"OHLCV CSV not found: {path}")
    bars: dict[str, list[Bar]] = defaultdict(list)
    seen: set[tuple[str, datetime]] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"symbol", "ts", "open", "high", "low", "close", "volume"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("OHLCV CSV is missing required columns")
        for row in reader:
            raw_symbol = row["symbol"].strip()
            ts = datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
            if end_at is not None and ts > end_at:
                continue
            key = (raw_symbol, ts)
            if key in seen:
                continue
            seen.add(key)
            meta = metadata.get(raw_symbol, {})
            currency = (meta.get("currency") or "USD").upper()
            if currency not in {
                "JPY",
                "USD",
                "HKD",
                "KRW",
                "VND",
                "IDR",
                "SGD",
                "THB",
                "MYR",
                "CNY",
            }:
                currency = "USD"
            bars[raw_symbol].append(
                Bar(
                    symbol=Symbol(
                        raw=raw_symbol,
                        exchange=meta.get("exchange") or meta.get("market") or "unknown",
                        code=meta.get("local_symbol") or raw_symbol,
                        currency=cast(Currency, currency),
                    ),
                    ts=ts,
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=Decimal(row["volume"]),
                    interval="1d",
                    provider="local_csv_evaluation",
                )
            )
    return bars


def _classify_regime(bars: list[Bar]) -> str:
    if len(bars) < 21:
        return "unknown"
    selected = bars[-61:]
    closes = [bar.close for bar in selected]
    returns = [
        (closes[index] / closes[index - 1]) - Decimal("1")
        for index in range(1, len(closes))
        if closes[index - 1] > 0
    ]
    if not returns or closes[0] <= 0:
        return "unknown"
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    variance = sum(((value - mean) ** 2 for value in returns), Decimal("0")) / Decimal(len(returns))
    volatility = variance.sqrt()
    period_return = (closes[-1] / closes[0]) - Decimal("1")
    if volatility >= Decimal("0.03"):
        return "high_volatility"
    if period_return >= Decimal("0.08"):
        return "uptrend"
    if period_return <= Decimal("-0.08"):
        return "downtrend"
    return "sideways"


def _maximum_absolute_daily_return(bars: list[Bar]) -> Decimal:
    maximum = Decimal("0")
    for previous, current in zip(bars, bars[1:]):
        if previous.close <= 0:
            continue
        maximum = max(maximum, abs((current.close / previous.close) - Decimal("1")))
    return maximum.quantize(Decimal("0.0001"))
