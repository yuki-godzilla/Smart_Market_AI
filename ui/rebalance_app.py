from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from pydantic import ValidationError

from backend.app.main import RebalanceCheckRequest, create_portfolio_risk_workflow
from backend.core.config import CONFIG_FILE_ENV, get_settings
from backend.core.data_contracts import Bar, FeatureSnapshot
from backend.core.errors import AppError
from backend.forecast import (
    ForecastEvaluation,
    ForecastModel,
    MomentumForecastModel,
    MovingAverageForecastModel,
    NaiveForecastModel,
    evaluate_models,
)
from backend.marketdata import FeatureBuilder, create_market_data_provider_adapter
from backend.marketdata.live_provider_adapters import live_provider_adapter_details
from backend.marketdata.provider_registry import provider_capability_details
from backend.portfolio.service import RebalanceProposal
from backend.portfolio.workflow import PortfolioRiskResult
from backend.screening import ScreeningScore, ScreeningService

DEFAULT_ACCOUNT_ID = "acct-1"
DEFAULT_AS_OF = date(2026, 4, 9)
DEFAULT_CASH_JPY = Decimal("29000")
_ONE_DAY = timedelta(days=1)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO_DIR = PROJECT_ROOT / "examples" / "rebalance_scenarios"
SCENARIO_DIR_ENV = "SMAI_REBALANCE_SCENARIO_DIR"
SYMBOL_DISPLAY_NAMES = {
    "7203.T": "Toyota Motor",
    "AAPL": "Apple Inc.",
}
DEFAULT_POSITIONS_JSON = """[
  {
    "symbol": "7203.T",
    "qty": "10",
    "avg_price": "2800",
    "currency": "JPY"
  }
]"""

DEFAULT_TARGETS_JSON = """[
  {
    "symbol": "7203.T",
    "currency": "JPY",
    "target_weight": "0.5"
  },
  {
    "symbol": "AAPL",
    "currency": "USD",
    "target_weight": "0.5"
  }
]"""


NO_TRADES_POSITIONS_JSON = """[
  {
    "symbol": "7203.T",
    "qty": "10",
    "avg_price": "2800",
    "currency": "JPY"
  }
]"""

NO_TRADES_TARGETS_JSON = """[
  {
    "symbol": "7203.T",
    "currency": "JPY",
    "target_weight": "1.0"
  }
]"""


def target_allocations_json(*, toyota_weight: Decimal, apple_weight: Decimal) -> str:
    """Build pretty target-allocation JSON for the current MVP symbols."""

    return json.dumps(
        [
            {
                "symbol": "7203.T",
                "currency": "JPY",
                "target_weight": _format_decimal(toyota_weight),
            },
            {
                "symbol": "AAPL",
                "currency": "USD",
                "target_weight": _format_decimal(apple_weight),
            },
        ],
        indent=2,
    )


def symbol_display_name(symbol: str) -> str:
    """Return a human-readable symbol label for UI display."""

    name = SYMBOL_DISPLAY_NAMES.get(symbol)
    if name is None:
        return symbol
    return f"{symbol} ({name})"


def symbol_reference_rows() -> list[dict[str, str]]:
    """Return the MVP sample symbols with human-readable names."""

    return [{"symbol": symbol, "name": name} for symbol, name in SYMBOL_DISPLAY_NAMES.items()]


@dataclass(frozen=True)
class RebalanceSample:
    """Deterministic sample inputs offered by the Streamlit UI."""

    account_id: str
    as_of: date
    cash_jpy: Decimal
    positions_json: str
    targets_json: str
    description: str = ""


@dataclass(frozen=True)
class RebalanceReportContext:
    """Table rows shared by Streamlit result rendering and local report exports."""

    summary: dict[str, str]
    current_rows: list[dict[str, str]]
    target_rows: list[dict[str, str]]
    allocation_rows: list[dict[str, str]]
    trade_rows: list[dict[str, str]]
    breach_rows: list[dict[str, str]]


@dataclass(frozen=True)
class MarketDataPreview:
    """Market-data provider preview rows used by the Streamlit UI."""

    status: str
    bars: list[Bar]
    provider_rows: list[dict[str, str]]
    quote_rows: list[dict[str, str]]
    ohlcv_rows: list[dict[str, str]]
    price_chart_rows: list[dict[str, str]]
    forecast_chart_rows: list[dict[str, str]]
    forecast_metric_rows: list[dict[str, str]]
    fx_rows: list[dict[str, str]]
    feature_rows: list[dict[str, str]]
    screening_rows: list[dict[str, str]]
    error_rows: list[dict[str, str]]


class RebalanceScenarioError(ValueError):
    """Raised when file-backed rebalance scenarios cannot be loaded."""


SAMPLE_DEFAULT_REBALANCE = "Default rebalance"
SAMPLE_NO_TRADES = "No trades"

_FALLBACK_REBALANCE_SAMPLES: dict[str, RebalanceSample] = {
    SAMPLE_DEFAULT_REBALANCE: RebalanceSample(
        account_id=DEFAULT_ACCOUNT_ID,
        as_of=DEFAULT_AS_OF,
        cash_jpy=DEFAULT_CASH_JPY,
        positions_json=DEFAULT_POSITIONS_JSON,
        targets_json=DEFAULT_TARGETS_JSON,
    ),
    SAMPLE_NO_TRADES: RebalanceSample(
        account_id=DEFAULT_ACCOUNT_ID,
        as_of=DEFAULT_AS_OF,
        cash_jpy=Decimal("0"),
        positions_json=NO_TRADES_POSITIONS_JSON,
        targets_json=NO_TRADES_TARGETS_JSON,
    ),
}


def rebalance_scenario_dir() -> Path:
    """Return the configured scenario directory used by the Streamlit UI."""

    raw_path = os.getenv(SCENARIO_DIR_ENV)
    if not raw_path:
        return DEFAULT_SCENARIO_DIR

    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_rebalance_samples(scenario_dir: Path | None = None) -> dict[str, RebalanceSample]:
    """Load deterministic rebalance samples from JSON files."""

    uses_default_dir = scenario_dir is None and not os.getenv(SCENARIO_DIR_ENV)
    scenario_dir = scenario_dir or rebalance_scenario_dir()
    if not scenario_dir.exists():
        if not uses_default_dir:
            raise RebalanceScenarioError(
                f"Rebalance scenario directory does not exist: {scenario_dir}"
            )
        return dict(_FALLBACK_REBALANCE_SAMPLES)
    if not scenario_dir.is_dir():
        raise RebalanceScenarioError(f"Rebalance scenario path must be a directory: {scenario_dir}")

    samples: dict[str, RebalanceSample] = {}
    errors: list[str] = []
    for path in sorted(scenario_dir.glob("*.json")):
        try:
            name, sample = _load_rebalance_sample_file(path)
        except RebalanceScenarioError as exc:
            errors.append(str(exc))
            continue

        if name in samples:
            errors.append(f"{path}: Duplicate rebalance scenario name: {name}")
            continue
        samples[name] = sample

    if errors:
        raise RebalanceScenarioError("Invalid rebalance scenario file(s): " + "; ".join(errors))

    if not samples:
        return dict(_FALLBACK_REBALANCE_SAMPLES)
    return samples


def rebalance_sample_names() -> list[str]:
    """Return sample names in the order they should appear in the UI."""

    return list(load_rebalance_samples())


def get_rebalance_sample(name: str) -> RebalanceSample:
    """Return a deterministic UI sample by name."""

    samples = load_rebalance_samples()
    try:
        return samples[name]
    except KeyError as exc:
        raise ValueError(f"Unknown rebalance sample: {name}") from exc


def sample_widget_key(sample_name: str, field_name: str) -> str:
    """Build a stable Streamlit widget key for sample-specific inputs."""

    return f"sample_{_slug(sample_name)}_{_slug(field_name)}"


def build_default_rebalance_request() -> RebalanceCheckRequest:
    """Build the deterministic sample request used by docs, tests, and the UI."""

    sample = get_rebalance_sample(SAMPLE_DEFAULT_REBALANCE)
    return build_rebalance_request(
        account_id=sample.account_id,
        as_of=sample.as_of,
        cash_jpy=sample.cash_jpy,
        positions_json=sample.positions_json,
        targets_json=sample.targets_json,
    )


def build_rebalance_request(
    *,
    account_id: str,
    as_of: date,
    cash_jpy: Decimal,
    positions_json: str,
    targets_json: str,
) -> RebalanceCheckRequest:
    """Build and validate a rebalance-check request from UI text inputs."""

    return RebalanceCheckRequest.model_validate(
        {
            "account_id": account_id,
            "as_of": as_of,
            "positions": _load_json_list(positions_json, "positions"),
            "targets": _load_json_list(targets_json, "targets"),
            "cash_jpy": cash_jpy,
        }
    )


def runtime_settings_summary() -> dict[str, str]:
    """Return the active local runtime settings relevant to the UI."""

    settings = get_settings()
    return {
        "provider": settings.dataaccess.provider,
        "csv_data_dir": settings.dataaccess.csv_data_dir,
        "config_file": os.getenv(CONFIG_FILE_ENV) or "defaults",
        "scenario_dir": str(rebalance_scenario_dir()),
    }


async def build_market_data_preview(
    *,
    symbol: str,
    start: date,
    end: date,
    provider_override: str | None = None,
    forecast_horizon_days: int = 1,
    fx_pair: str = "USDJPY",
) -> MarketDataPreview:
    """Fetch a small market-data preview for the configured provider."""

    if forecast_horizon_days < 1 or forecast_horizon_days > 30:
        raise ValueError("forecast_horizon_days must be between 1 and 30")

    settings = get_settings()
    dataaccess_cfg = settings.dataaccess
    if provider_override:
        dataaccess_cfg = dataaccess_cfg.model_copy(
            update={
                "provider": provider_override,
                "allow_external_providers": provider_override == "yahoo"
                or dataaccess_cfg.allow_external_providers,
            }
        )
    provider = dataaccess_cfg.provider
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.max, tzinfo=UTC)
    provider_rows = provider_metadata_rows(provider)

    try:
        adapter = create_market_data_provider_adapter(dataaccess_cfg)
        quotes = await adapter.fetch_quotes([symbol], at=end_dt)
        bars = await adapter.fetch_ohlcv([symbol], start=start_dt, end=end_dt)
        fx_rates = await adapter.get_fx_rates([fx_pair], at=end_dt)
        feature_snapshot = await FeatureBuilder(
            adapter,
            cfg=settings.feature_builder,
        ).build_feature_snapshot([symbol], end)
        screening_scores = ScreeningService().score(feature_snapshot)
    except AppError as exc:
        return MarketDataPreview(
            status="ERROR",
            bars=[],
            provider_rows=provider_rows,
            quote_rows=[],
            ohlcv_rows=[],
            price_chart_rows=[],
            forecast_chart_rows=[],
            forecast_metric_rows=[],
            fx_rows=[],
            feature_rows=[],
            screening_rows=[],
            error_rows=[
                {
                    "code": exc.code,
                    "message": exc.message,
                    "details": json.dumps(exc.details, ensure_ascii=False, sort_keys=True),
                }
            ],
        )

    return MarketDataPreview(
        status="OK",
        bars=bars,
        provider_rows=provider_rows,
        quote_rows=[
            {
                "symbol": quote.symbol.raw,
                "exchange": quote.symbol.exchange,
                "bid": _format_optional_decimal(quote.bid),
                "ask": _format_optional_decimal(quote.ask),
                "last": _format_optional_decimal(quote.last),
                "ts": quote.ts.isoformat(),
            }
            for quote in quotes
        ],
        ohlcv_rows=ohlcv_summary_rows(bars),
        price_chart_rows=price_chart_rows(bars),
        forecast_chart_rows=forecast_chart_rows(
            bars,
            horizon_days=forecast_horizon_days,
        ),
        forecast_metric_rows=forecast_metric_rows(
            _available_forecast_evaluations(
                bars,
                horizon_days=forecast_horizon_days,
            )
        ),
        fx_rows=[
            {
                "pair": rate.pair,
                "rate": _format_decimal(rate.rate),
                "ts": rate.ts.isoformat(),
                "source": rate.source,
            }
            for rate in fx_rates
        ],
        feature_rows=feature_snapshot_rows(feature_snapshot),
        screening_rows=screening_score_rows(screening_scores),
        error_rows=[],
    )


def provider_metadata_rows(provider: str) -> list[dict[str, str]]:
    """Return provider metadata rows for UI display."""

    details = provider_capability_details(provider)
    details.update(live_provider_adapter_details(provider))
    if details.get("smoke_check_status") == "implemented_live_opt_in":
        details["implemented"] = True
        details["live_adapter"] = "implemented_opt_in"
    return [
        {"field": key, "value": _stringify_metadata_value(value)} for key, value in details.items()
    ]


def ohlcv_summary_rows(bars: list[Bar]) -> list[dict[str, str]]:
    """Return compact OHLCV summary rows grouped for UI display."""

    if not bars:
        return []
    first = bars[0]
    last = bars[-1]
    volume = sum((bar.volume for bar in bars), Decimal("0"))
    return [
        {
            "symbol": first.symbol.raw,
            "bars": str(len(bars)),
            "first_ts": first.ts.isoformat(),
            "last_ts": last.ts.isoformat(),
            "first_close": _format_decimal(first.close),
            "last_close": _format_decimal(last.close),
            "total_volume": _format_decimal(volume),
            "provider": last.provider,
        }
    ]


def price_chart_rows(bars: list[Bar]) -> list[dict[str, str]]:
    """Return close-price rows for Streamlit chart display."""

    return [
        {
            "ts": bar.ts.isoformat(),
            "close": _format_decimal(bar.close),
        }
        for bar in sorted(bars, key=lambda row: row.ts)
    ]


def forecast_chart_rows(
    bars: list[Bar],
    *,
    horizon_days: int = 1,
) -> list[dict[str, str]]:
    """Return actual close and model forecast rows for chart display."""

    if horizon_days < 1 or horizon_days > 30:
        raise ValueError("horizon_days must be between 1 and 30")

    sorted_bars = sorted(bars, key=lambda row: row.ts)
    if not sorted_bars:
        return []

    models = _available_forecast_models(sorted_bars)
    rows_by_ts: dict[str, dict[str, str]] = {
        bar.ts.isoformat(): {"ts": bar.ts.isoformat(), "close": _format_decimal(bar.close)}
        for bar in sorted_bars
    }
    for model in models:
        for target_index in range(model.min_history + horizon_days - 1, len(sorted_bars)):
            history_end = target_index - horizon_days + 1
            history = sorted_bars[:history_end]
            target_bar = sorted_bars[target_index]
            forecast = model.predict(history, horizon_days=horizon_days)
            rows_by_ts[target_bar.ts.isoformat()][model.name] = _format_decimal(
                forecast.forecast_close
            )

        latest_forecast = model.predict(sorted_bars, horizon_days=horizon_days)
        forecast_ts = _next_forecast_ts(sorted_bars[-1], horizon_days=horizon_days)
        forecast_row = rows_by_ts.setdefault(forecast_ts, {"ts": forecast_ts, "close": ""})
        forecast_row[model.name] = _format_decimal(latest_forecast.forecast_close)

    return [rows_by_ts[key] for key in sorted(rows_by_ts)]


def forecast_metric_rows(evaluations: list[ForecastEvaluation]) -> list[dict[str, str]]:
    """Return forecast metrics for UI display."""

    return [
        {
            "model": evaluation.model_name,
            "symbol": evaluation.symbol,
            "horizon_days": str(evaluation.horizon_days),
            "forecast_close": _format_decimal(evaluation.latest_forecast.forecast_close),
            "mae": _format_decimal(evaluation.metrics.mae),
            "rmse": _format_decimal(evaluation.metrics.rmse),
            "direction_accuracy": _format_optional_percent(evaluation.metrics.direction_accuracy),
            "sample_count": str(evaluation.metrics.sample_count),
        }
        for evaluation in evaluations
    ]


def forecast_metric_rows_for_bars(
    bars: list[Bar],
    *,
    horizon_days: int = 1,
) -> list[dict[str, str]]:
    """Return forecast metric rows recalculated from already fetched OHLCV bars."""

    return forecast_metric_rows(
        _available_forecast_evaluations(
            bars,
            horizon_days=horizon_days,
        )
    )


def feature_snapshot_rows(snapshot: FeatureSnapshot) -> list[dict[str, str]]:
    """Return feature snapshot rows for UI display."""

    return [
        {
            "symbol": row.symbol,
            "as_of": row.as_of.isoformat(),
            "provider": snapshot.provider,
            "feature_version": snapshot.feature_version,
            "last": _format_optional_decimal(row.last),
            "close_1d": _format_optional_decimal(row.close_1d),
            "return_1d": _format_optional_percent(row.return_1d),
            "momentum_5d": _format_optional_percent(row.momentum_5d),
            "adv_20d": _format_optional_decimal(row.adv_20d),
            "vol_20d": _format_optional_percent(row.vol_20d),
            "drawdown_20d": _format_optional_percent(row.drawdown_20d),
            "data_completeness": _format_optional_percent(row.data_completeness),
            "dividend_yield": _format_optional_percent(row.dividend_yield),
            "market_cap_jpy": _format_optional_decimal(row.market_cap_jpy),
            "data_quality": row.data_quality,
            "data_quality_reasons": _quality_reasons(row.data_quality_reasons),
            "missing": _missing_flags(row.missing),
            "missing_summary": _missing_summary_text(snapshot.missing_summary),
        }
        for row in snapshot.rows
    ]


def screening_score_rows(scores: list[ScreeningScore]) -> list[dict[str, str]]:
    """Return screening score rows for UI display."""

    return [
        {
            "rank": str(score.rank),
            "symbol": score.symbol,
            "total_score": _format_decimal(score.total_score),
            "momentum_score": _format_decimal(score.momentum_score),
            "liquidity_score": _format_decimal(score.liquidity_score),
            "risk_score": _format_decimal(score.risk_score),
            "data_quality_score": _format_decimal(score.data_quality_score),
            "data_quality": score.data_quality,
            "summary": score.summary,
            "reason_labels": _quality_reasons(score.reason_labels),
            "reasons": _quality_reasons(score.reasons),
        }
        for score in scores
    ]


def screening_score_json_download(rows: list[dict[str, str]]) -> str:
    """Return screening score rows as stable JSON text."""

    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def screening_score_csv_download(rows: list[dict[str, str]]) -> str:
    """Return screening score rows as CSV text."""

    return table_csv_download(
        rows,
        fieldnames=[
            "rank",
            "symbol",
            "total_score",
            "momentum_score",
            "liquidity_score",
            "risk_score",
            "data_quality_score",
            "data_quality",
            "summary",
            "reason_labels",
            "reasons",
        ],
    )


async def run_rebalance_check(request: RebalanceCheckRequest) -> PortfolioRiskResult:
    """Run the same Portfolio-to-Risk workflow used by the FastAPI endpoint."""

    return await create_portfolio_risk_workflow().propose_and_check(
        account_id=request.account_id,
        positions=request.positions,
        targets=request.targets,
        as_of=request.as_of,
        cash_jpy=request.cash_jpy,
    )


def result_summary(result: PortfolioRiskResult) -> dict[str, str]:
    """Return a compact summary row for the Streamlit result header."""

    proposal = result.proposal
    return {
        "account_id": proposal.account_id,
        "as_of": proposal.as_of.isoformat(),
        "total_value_jpy": _format_decimal(proposal.current.total_value_jpy),
        "cash_jpy": _format_decimal(proposal.current.cash_jpy),
        "trade_count": str(len(proposal.trades)),
        "risk_status": result.risk_decision.status if result.risk_decision else "NO_TRADES",
    }


def build_rebalance_report_context(result: PortfolioRiskResult) -> RebalanceReportContext:
    """Build shared table rows for UI rendering and local report exports."""

    proposal = result.proposal
    return RebalanceReportContext(
        summary=result_summary(result),
        current_rows=current_position_rows(proposal),
        target_rows=target_allocation_rows(proposal),
        allocation_rows=allocation_comparison_rows(proposal),
        trade_rows=proposed_trade_rows(proposal),
        breach_rows=risk_breach_rows(result),
    )


def current_position_rows(proposal: RebalanceProposal) -> list[dict[str, str]]:
    """Format valued current positions for table display."""

    return [
        {
            "symbol": symbol_display_name(position.symbol),
            "qty": _format_decimal(position.qty),
            "currency": position.currency,
            "last": _format_decimal(position.last),
            "fx_rate_jpy": _format_decimal(position.fx_rate_jpy),
            "value_jpy": _format_decimal(position.value_jpy),
        }
        for position in proposal.current.positions
    ]


def target_allocation_rows(proposal: RebalanceProposal) -> list[dict[str, str]]:
    """Format target allocations for table display."""

    return [
        {
            "symbol": symbol_display_name(target.symbol),
            "currency": target.currency,
            "target_weight": _format_decimal(target.target_weight),
        }
        for target in proposal.targets
    ]


def allocation_comparison_rows(proposal: RebalanceProposal) -> list[dict[str, str]]:
    """Format current-vs-target weights for table display."""

    total_value = proposal.current.total_value_jpy
    current_values = {
        position.symbol: position.value_jpy for position in proposal.current.positions
    }
    target_weights = {target.symbol: target.target_weight for target in proposal.targets}
    symbols = sorted(set(current_values) | set(target_weights))

    rows: list[dict[str, str]] = []
    for symbol in symbols:
        current_weight = (
            current_values.get(symbol, Decimal("0")) / total_value
            if total_value > 0
            else Decimal("0")
        )
        target_weight = target_weights.get(symbol, Decimal("0"))
        rows.append(
            {
                "symbol": symbol_display_name(symbol),
                "current_weight": _format_decimal(current_weight),
                "target_weight": _format_decimal(target_weight),
                "drift": _format_decimal(target_weight - current_weight),
            }
        )
    return rows


def proposed_trade_rows(proposal: RebalanceProposal) -> list[dict[str, str]]:
    """Format proposed trades for table display."""

    return [
        {
            "symbol": symbol_display_name(trade.symbol),
            "side": trade.side,
            "qty": _format_decimal(trade.qty),
            "price_hint": _format_optional_decimal(trade.price_hint),
            "currency": trade.currency,
        }
        for trade in proposal.trades
    ]


def risk_breach_rows(result: PortfolioRiskResult) -> list[dict[str, str]]:
    """Format risk rule breaches for table display."""

    if result.risk_decision is None:
        return []
    return [{"breach": breach} for breach in result.risk_decision.breaches]


def result_json_download(result: PortfolioRiskResult) -> str:
    """Return a stable JSON payload for local UI result downloads."""

    return result.model_dump_json(indent=2)


def request_json_download(request: RebalanceCheckRequest) -> str:
    """Return the validated rebalance request used to produce a report."""

    return request.model_dump_json(indent=2)


def result_markdown_report_download(
    result: PortfolioRiskResult,
    *,
    request: RebalanceCheckRequest | None = None,
) -> str:
    """Return a human-readable local Markdown report for a rebalance result."""

    context = build_rebalance_report_context(result)
    summary = context.summary
    lines = [
        "# Rebalance Check Report",
        "",
        "## Summary",
        "",
        f"- Account: {summary['account_id']}",
        f"- As of: {summary['as_of']}",
        f"- Total value JPY: {summary['total_value_jpy']}",
        f"- Cash JPY: {summary['cash_jpy']}",
        f"- Proposed trades: {summary['trade_count']}",
        f"- Risk status: {summary['risk_status']}",
    ]
    if request is not None:
        lines.extend(
            [
                "",
                "## Request",
                "",
                f"- Positions: {len(request.positions)}",
                f"- Targets: {len(request.targets)}",
            ]
        )

    lines.extend(
        [
            "",
            "## Current Positions",
            "",
            _markdown_table(
                context.current_rows,
                ["symbol", "qty", "currency", "last", "fx_rate_jpy", "value_jpy"],
                empty_message="No current positions.",
            ),
            "",
            "## Target Allocations",
            "",
            _markdown_table(
                context.target_rows,
                ["symbol", "currency", "target_weight"],
                empty_message="No target allocations.",
            ),
            "",
            "## Allocation Comparison",
            "",
            _markdown_table(
                context.allocation_rows,
                ["symbol", "current_weight", "target_weight", "drift"],
            ),
            "",
            "## Proposed Trades",
            "",
            _markdown_table(
                context.trade_rows,
                ["symbol", "side", "qty", "price_hint", "currency"],
                empty_message="No rebalance trades were proposed.",
            ),
        ]
    )

    lines.extend(
        [
            "",
            "## Risk Breaches",
            "",
        ]
    )
    if context.breach_rows:
        lines.extend(f"- {row['breach']}" for row in context.breach_rows)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def result_table_downloads(result: PortfolioRiskResult) -> dict[str, str]:
    """Return table-friendly CSV downloads for a rebalance result."""

    context = build_rebalance_report_context(result)
    return {
        "rebalance_summary.csv": table_csv_download([context.summary]),
        "rebalance_current_positions.csv": table_csv_download(
            context.current_rows,
            fieldnames=["symbol", "qty", "currency", "last", "fx_rate_jpy", "value_jpy"],
        ),
        "rebalance_target_allocations.csv": table_csv_download(
            context.target_rows,
            fieldnames=["symbol", "currency", "target_weight"],
        ),
        "rebalance_allocation_comparison.csv": table_csv_download(
            context.allocation_rows,
            fieldnames=["symbol", "current_weight", "target_weight", "drift"],
        ),
        "rebalance_proposed_trades.csv": table_csv_download(
            context.trade_rows,
            fieldnames=["symbol", "side", "qty", "price_hint", "currency"],
        ),
        "rebalance_risk_breaches.csv": table_csv_download(
            context.breach_rows,
            fieldnames=["breach"],
        ),
    }


def result_report_zip_download(
    result: PortfolioRiskResult,
    *,
    request: RebalanceCheckRequest | None = None,
) -> bytes:
    """Return a deterministic ZIP report containing JSON and CSV downloads."""

    files = {
        "rebalance_report_manifest.json": result_report_manifest_download(
            result,
            includes_request=request is not None,
        ),
        "rebalance_report.md": result_markdown_report_download(result, request=request),
        "rebalance_check_result.json": result_json_download(result),
        **result_table_downloads(result),
    }
    if request is not None:
        files["rebalance_request.json"] = request_json_download(request)
    return zip_text_downloads(files)


def result_report_manifest_download(
    result: PortfolioRiskResult,
    *,
    includes_request: bool = False,
) -> str:
    """Return report metadata that explains the local export contents."""

    summary = result_summary(result)
    files = [
        {
            "filename": "rebalance_check_result.json",
            "description": "Portfolio-to-Risk workflow result payload.",
        },
        {
            "filename": "rebalance_report.md",
            "description": "Human-readable Markdown summary of the rebalance check.",
        },
        {
            "filename": "rebalance_summary.csv",
            "description": "One-row summary of account, valuation, trades, and risk status.",
        },
        {
            "filename": "rebalance_current_positions.csv",
            "description": "Current positions valued in JPY.",
        },
        {
            "filename": "rebalance_target_allocations.csv",
            "description": "Target allocation weights used by the rebalance check.",
        },
        {
            "filename": "rebalance_allocation_comparison.csv",
            "description": "Current weights, target weights, and drift by symbol.",
        },
        {
            "filename": "rebalance_proposed_trades.csv",
            "description": "Proposed rebalance trades generated by the MVP solver.",
        },
        {
            "filename": "rebalance_risk_breaches.csv",
            "description": "Risk rule breaches returned by the pre-trade check.",
        },
    ]
    if includes_request:
        files.insert(
            0,
            {
                "filename": "rebalance_request.json",
                "description": "Validated request payload used to run the rebalance check.",
            },
        )

    manifest = {
        "schema_version": "rebalance-report-v1",
        "account_id": summary["account_id"],
        "as_of": summary["as_of"],
        "risk_status": summary["risk_status"],
        "trade_count": summary["trade_count"],
        "files": files,
    }
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def table_csv_download(
    rows: list[dict[str, str]],
    *,
    fieldnames: list[str] | None = None,
) -> str:
    """Return stable CSV text for UI table downloads."""

    resolved_fieldnames = fieldnames or (list(rows[0]) if rows else [])
    if not resolved_fieldnames:
        return ""
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=resolved_fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def zip_text_downloads(files: dict[str, str]) -> bytes:
    """Return a deterministic ZIP archive for text download payloads."""

    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as archive:
        for filename in sorted(files):
            info = ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, files[filename].encode("utf-8"))
    return buffer.getvalue()


def _markdown_table(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    *,
    empty_message: str = "No rows.",
) -> str:
    if not rows:
        return empty_message
    header = "| " + " | ".join(fieldnames) + " |"
    separator = "| " + " | ".join("---" for _ in fieldnames) + " |"
    body = [
        "| " + " | ".join(_markdown_cell(row.get(field, "")) for field in fieldnames) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")


def _load_json_list(value: str, field_name: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON") from exc
    if not isinstance(data, list):
        raise ValueError(f"{field_name} must be a JSON array")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{field_name} must contain JSON objects")
    return data


def _load_rebalance_sample_file(path: Path) -> tuple[str, RebalanceSample]:
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise RebalanceScenarioError(f"{path}: invalid JSON ({exc.msg})") from exc

    if not isinstance(data, dict):
        raise RebalanceScenarioError(f"{path}: scenario must be a JSON object")
    name = data.get("name")
    description = data.get("description", "")
    request = data.get("request")
    if not isinstance(name, str) or not name:
        raise RebalanceScenarioError(f"{path}: scenario requires a non-empty name")
    if not isinstance(description, str):
        raise RebalanceScenarioError(f"{path}: scenario description must be a string")
    if not isinstance(request, dict):
        raise RebalanceScenarioError(f"{path}: scenario requires a request object")

    try:
        validated = RebalanceCheckRequest.model_validate(request)
    except ValidationError as exc:
        raise RebalanceScenarioError(
            f"{path}: request does not match rebalance-check schema"
        ) from exc

    payload = validated.model_dump(mode="json")
    return (
        name,
        RebalanceSample(
            account_id=validated.account_id,
            as_of=validated.as_of,
            cash_jpy=validated.cash_jpy,
            positions_json=json.dumps(payload["positions"], indent=2),
            targets_json=json.dumps(payload["targets"], indent=2),
            description=description,
        ),
    )


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _format_optional_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return _format_decimal(value)


def _format_optional_percent(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{(value * Decimal('100')).quantize(Decimal('0.01'))}%"


def _stringify_metadata_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _missing_flags(missing: dict[str, bool]) -> str:
    flags = [feature for feature, is_missing in sorted(missing.items()) if is_missing]
    if not flags:
        return ""
    return ", ".join(flags)


def _missing_summary_text(summary: dict[str, int]) -> str:
    if not summary:
        return ""
    return ", ".join(f"{feature}: {count}" for feature, count in sorted(summary.items()))


def _quality_reasons(reasons: list[str]) -> str:
    if not reasons:
        return ""
    return ", ".join(reasons)


def _available_forecast_evaluations(
    bars: list[Bar],
    *,
    horizon_days: int = 1,
) -> list[ForecastEvaluation]:
    models = _available_forecast_models(bars)
    if not models:
        return []
    return evaluate_models(bars, models=models, horizon_days=horizon_days)


def _available_forecast_models(bars: list[Bar]) -> list[ForecastModel]:
    models: list[ForecastModel] = [
        NaiveForecastModel(),
        MovingAverageForecastModel(),
        MomentumForecastModel(),
    ]
    return [model for model in models if len(bars) >= model.min_history]


def _next_forecast_ts(bar: Bar, *, horizon_days: int = 1) -> str:
    return (bar.ts + (_ONE_DAY * horizon_days)).isoformat()


def _slug(value: str) -> str:
    return "_".join(value.lower().split())
