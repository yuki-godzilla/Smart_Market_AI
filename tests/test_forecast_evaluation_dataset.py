import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.core.data_contracts import Bar, Symbol
from backend.forecast.dataset import (
    load_forecast_evaluation_dataset,
    write_forecast_dataset_coverage,
)
from backend.forecast.evaluation import ForecastEvaluationCase
from backend.forecast.tuning import (
    tune_forecast_adapters,
    write_forecast_tuning_artifacts,
)
from tools.evaluate_forecast_models import main


def test_dataset_loader_builds_cases_and_classifies_coverage(tmp_path):
    ohlcv = tmp_path / "ohlcv.csv"
    metadata = tmp_path / "symbols.csv"
    _write_metadata(metadata)
    _write_ohlcv(ohlcv, {"AAPL": 90, "7203.T": 20})

    result = load_forecast_evaluation_dataset(
        ohlcv,
        metadata,
        required_bar_count=80,
    )

    assert [case.symbol for case in result.cases] == ["AAPL"]
    assert result.cases[0].market == "us"
    assert result.cases[0].asset_type == "stock"
    coverage = {row.symbol: row for row in result.coverage}
    assert coverage["AAPL"].eligible is True
    assert coverage["7203.T"].eligible is False
    assert coverage["7203.T"].reason == "insufficient_bars:20/80"

    paths = write_forecast_dataset_coverage(result, tmp_path / "reports")
    assert "評価可能symbol数: 1" in paths["coverage_markdown"].read_text(encoding="utf-8")


def test_runner_reports_current_short_local_dataset_without_failure(tmp_path, capsys):
    output = tmp_path / "evaluation"

    exit_code = main(
        [
            "--ohlcv",
            "data/marketdata/ohlcv.csv",
            "--metadata",
            "data/marketdata/symbol_universe.csv",
            "--output",
            str(output),
            "--required-bars",
            "180",
        ]
    )

    assert exit_code == 0
    assert "0/2 symbols eligible" in capsys.readouterr().out
    assert (output / "forecast_model_dataset_coverage.md").is_file()
    assert (output / "forecast_model_evaluation_summary.md").is_file()


def test_dataset_loader_deduplicates_symbol_timestamp(tmp_path):
    ohlcv = tmp_path / "ohlcv.csv"
    metadata = tmp_path / "symbols.csv"
    _write_metadata(metadata)
    _write_ohlcv(ohlcv, {"AAPL": 80})
    with ohlcv.open("a", encoding="utf-8", newline="") as handle:
        handle.write("AAPL,2025-01-01T00:00:00+00:00,100,101,99,100,1000\n")

    result = load_forecast_evaluation_dataset(
        ohlcv,
        metadata,
        required_bar_count=80,
    )

    assert len(result.cases[0].bars) == 80


def test_tuning_compares_bounded_candidate_for_all_existing_adapters(tmp_path):
    bars = _bar_contracts("AAPL", 120)

    results = tune_forecast_adapters(
        [ForecastEvaluationCase(symbol="AAPL", bars=bars)],
        horizons=(20,),
        max_origins=2,
    )

    assert {result.adapter_name for result in results} == {
        "advanced_linear",
        "advanced_tree_sklearn",
        "advanced_gbdt_sklearn",
        "advanced_quantile",
    }
    assert all(result.horizon_days == 20 for result in results)
    assert all(result.reason for result in results)
    paths = write_forecast_tuning_artifacts(results, tmp_path / "tuning")
    assert "既存4モデル" in paths["tuning_markdown"].read_text(encoding="utf-8")


def _write_metadata(path):
    path.write_text(
        "symbol,market,asset_type,currency,exchange,local_symbol\n"
        "AAPL,us,stock,USD,NASDAQ,AAPL\n"
        "7203.T,jp,stock,JPY,TSE,7203\n",
        encoding="utf-8",
    )


def _write_ohlcv(path, counts):
    fieldnames = ["symbol", "ts", "open", "high", "low", "close", "volume"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for symbol, count in counts.items():
            start = datetime(2025, 1, 1, tzinfo=UTC)
            close = Decimal("100")
            for index in range(count):
                close += Decimal("0.2") + Decimal((index % 5) - 2) / Decimal("20")
                writer.writerow(
                    {
                        "symbol": symbol,
                        "ts": (start + timedelta(days=index)).isoformat(),
                        "open": close - Decimal("0.3"),
                        "high": close + Decimal("0.5"),
                        "low": close - Decimal("0.6"),
                        "close": close,
                        "volume": 1000 + index,
                    }
                )


def _bar_contracts(symbol_raw, count):
    symbol = Symbol(
        raw=symbol_raw,
        exchange="NASDAQ",
        code=symbol_raw,
        currency="USD",
    )
    start = datetime(2025, 1, 1, tzinfo=UTC)
    close = Decimal("100")
    rows = []
    for index in range(count):
        close += Decimal("0.2") + Decimal((index % 7) - 3) / Decimal("20")
        rows.append(
            Bar(
                symbol=symbol,
                ts=start + timedelta(days=index),
                open=close - Decimal("0.3"),
                high=close + Decimal("0.5"),
                low=close - Decimal("0.6"),
                close=close,
                volume=Decimal(1000 + index),
                interval="1d",
                provider="fixture",
            )
        )
    return rows
