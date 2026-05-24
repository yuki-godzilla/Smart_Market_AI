from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from pydantic import ValidationError

from backend.app.main import RebalanceCheckRequest, create_portfolio_risk_workflow
from backend.core.config import CONFIG_FILE_ENV, get_settings
from backend.core.data_contracts import (
    Bar,
    DailySnapshot,
    DataQuality,
    FeatureSnapshot,
    FundamentalSnapshot,
    Quote,
)
from backend.core.errors import AppError, DataSourceError
from backend.forecast import (
    ForecastEvaluation,
    ForecastModel,
    available_forecast_models,
    evaluate_models,
    summarize_forecast_evaluations,
)
from backend.marketdata import create_market_data_provider_adapter
from backend.marketdata.feature_builder import build_daily_snapshots_from_market_data
from backend.marketdata.live_provider_adapters import live_provider_adapter_details
from backend.marketdata.provider_registry import provider_capability_details
from backend.marketdata.providers.yahoo import shared_yfinance_session
from backend.portfolio.service import RebalanceProposal
from backend.portfolio.workflow import PortfolioRiskResult
from backend.reporting import (
    DecisionReportContext,
    build_decision_checkpoints_section,
    build_decision_report_context,
    build_report_section,
    decision_report_manifest_json_download,
    decision_report_zip_download,
    render_decision_report_markdown,
)
from backend.reporting import (
    decision_report_json_download as reporting_decision_report_json_download,
)
from backend.scoring import InvestmentScore, InvestmentScoringService
from backend.screening import ScreeningScore, ScreeningService
from ui.symbol_universe import (
    symbol_name as _symbol_name_from_csv,
)
from ui.symbol_universe import (
    symbol_provider_symbol as _symbol_provider_symbol_from_csv,
)
from ui.symbol_universe import (
    symbol_reference_rows as _symbol_reference_rows_from_csv,
)

DEFAULT_ACCOUNT_ID = "acct-1"
DEFAULT_AS_OF = date(2026, 4, 9)
DEFAULT_CASH_JPY = Decimal("29000")
_ONE_DAY = timedelta(days=1)
MARKET_DATA_FEATURE_LOOKBACK_DAYS = 90
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO_DIR = PROJECT_ROOT / "examples" / "rebalance_scenarios"
SCENARIO_DIR_ENV = "SMAI_REBALANCE_SCENARIO_DIR"
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

    name = symbol_name(symbol)
    if name is None:
        return symbol
    return f"{symbol} ({name})"


def symbol_name(symbol: str) -> str | None:
    """Return the known company name for a yfinance-compatible ticker."""

    return _symbol_name_from_csv(symbol)


def symbol_reference_rows() -> list[dict[str, str]]:
    """Return the MVP sample symbols with human-readable names."""

    return _symbol_reference_rows_from_csv()


def yfinance_search_symbol_rows(query: str, *, max_results: int = 12) -> list[dict[str, str]]:
    """Return symbol candidates from yfinance Search for the user's query."""

    normalized_query = query.strip()
    if not normalized_query:
        return []
    return [dict(row) for row in _cached_yfinance_search_symbol_rows(normalized_query, max_results)]


@lru_cache(maxsize=64)
def _cached_yfinance_search_symbol_rows(
    normalized_query: str,
    max_results: int,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    try:
        import yfinance as yf  # type: ignore[import-untyped]

        quotes = yf.Search(
            normalized_query,
            max_results=max_results,
            news_count=0,
            lists_count=0,
            include_cb=False,
            include_nav_links=False,
            include_research=False,
            include_cultural_assets=False,
            enable_fuzzy_query=True,
            session=shared_yfinance_session(),
            timeout=5,
            raise_errors=False,
        ).quotes
    except Exception:  # noqa: BLE001
        return tuple()

    rows: list[dict[str, str]] = []
    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        symbol = str(quote.get("symbol") or "").strip()
        if not symbol:
            continue
        name = str(
            quote.get("shortname")
            or quote.get("longname")
            or quote.get("name")
            or quote.get("exchange")
            or symbol
        ).strip()
        rows.append({"symbol": symbol, "name": name})
    return tuple(tuple(row.items()) for row in rows)


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
    investment_score_rows: list[dict[str, str]]
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
    provider_symbol = _symbol_provider_symbol_from_csv(symbol, provider)
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.max, tzinfo=UTC)
    provider_rows = provider_metadata_rows(provider)

    try:
        adapter = create_market_data_provider_adapter(dataaccess_cfg)
        feature_start = min(start, end - timedelta(days=MARKET_DATA_FEATURE_LOOKBACK_DAYS))
        feature_start_dt = datetime.combine(feature_start, time.min, tzinfo=UTC)
        provider_bars = await adapter.fetch_ohlcv(
            [provider_symbol],
            start=feature_start_dt,
            end=end_dt,
        )
        feature_bars = _bars_with_display_symbol(provider_bars, display_symbol=symbol)
        bars = _bars_in_period(feature_bars, start=start_dt, end=end_dt)
        quotes = _quotes_from_latest_bars([symbol], feature_bars)
        warning_rows: list[dict[str, str]] = []
        fx_rates: list[Any] = []
        if _should_fetch_market_data_preview_fx(provider=provider):
            try:
                fx_rates = await adapter.get_fx_rates([fx_pair], at=end_dt)
            except AppError as exc:
                warning_rows.append(_market_data_error_row(exc, component="fx"))
        if _should_fetch_market_data_preview_fundamentals(provider=provider):
            try:
                provider_fundamentals = await adapter.fetch_fundamentals(
                    [provider_symbol],
                    as_of=end,
                )
                fundamentals = _fundamentals_with_display_symbol(
                    provider_fundamentals,
                    display_symbol=symbol,
                )
            except AppError as exc:
                warning_rows.append(_market_data_error_row(exc, component="fundamentals"))
                fundamentals = [
                    _fallback_fundamental_snapshot(symbol, as_of=end, provider=provider)
                ]
        else:
            fundamentals = [_fallback_fundamental_snapshot(symbol, as_of=end, provider=provider)]
        feature_rows = build_daily_snapshots_from_market_data(
            symbols=[symbol],
            as_of=end,
            quotes=quotes,
            fundamentals=fundamentals,
            bars=feature_bars,
            cfg=settings.feature_builder,
        )
        feature_snapshot = FeatureSnapshot(
            as_of=end,
            provider=adapter.healthcheck().get("provider", provider),
            rows=feature_rows,
            missing_summary=_feature_missing_summary(feature_rows),
            quality_summary=_feature_quality_summary(feature_rows),
        )
        forecast_evaluations = _available_forecast_evaluations(
            bars,
            horizon_days=forecast_horizon_days,
        )
        forecast_consensus = summarize_forecast_evaluations(forecast_evaluations)
        forecast_consensus_by_symbol = (
            {forecast_consensus.symbol: forecast_consensus}
            if forecast_consensus is not None
            else {}
        )
        screening_scores = ScreeningService().score(
            feature_snapshot,
            forecast_consensus_by_symbol=forecast_consensus_by_symbol,
        )
        investment_scores = InvestmentScoringService(weights=settings.scoring.weights).score(
            screening_scores,
            forecast_consensus_by_symbol=forecast_consensus_by_symbol,
        )
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
            investment_score_rows=[],
            screening_rows=[],
            error_rows=[_market_data_error_row(exc)],
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
        forecast_metric_rows=forecast_metric_rows(forecast_evaluations),
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
        investment_score_rows=investment_score_rows(investment_scores),
        screening_rows=screening_score_rows(screening_scores),
        error_rows=warning_rows,
    )


def _should_fetch_market_data_preview_fx(*, provider: str) -> bool:
    return provider != "yahoo"


def _should_fetch_market_data_preview_fundamentals(*, provider: str) -> bool:
    return provider != "yahoo"


def _fallback_fundamental_snapshot(
    symbol: str,
    *,
    as_of: date,
    provider: str,
) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol=symbol,
        as_of=as_of,
        provider=provider,
        dividend_yield=None,
        market_cap_jpy=None,
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


def _bars_with_display_symbol(bars: list[Bar], *, display_symbol: str) -> list[Bar]:
    return [
        bar.model_copy(
            update={
                "symbol": bar.symbol.model_copy(
                    update={"raw": display_symbol, "code": display_symbol.removesuffix(".T")}
                )
            }
        )
        for bar in bars
    ]


def _fundamentals_with_display_symbol(
    fundamentals: list[FundamentalSnapshot],
    *,
    display_symbol: str,
) -> list[FundamentalSnapshot]:
    return [
        fundamental.model_copy(update={"symbol": display_symbol}) for fundamental in fundamentals
    ]


def _market_data_error_row(exc: AppError, *, component: str | None = None) -> dict[str, str]:
    details = dict(exc.details)
    if component is not None:
        details["component"] = component
    return {
        "code": exc.code,
        "message": exc.message,
        "details": json.dumps(details, ensure_ascii=False, sort_keys=True),
    }


def _bars_in_period(
    bars: list[Bar],
    *,
    start: datetime,
    end: datetime,
) -> list[Bar]:
    return sorted((bar for bar in bars if start <= bar.ts <= end), key=lambda row: row.ts)


def _quotes_from_latest_bars(symbols: list[str], bars: list[Bar]) -> list[Quote]:
    bars_by_symbol: dict[str, list[Bar]] = {symbol: [] for symbol in symbols}
    for bar in bars:
        if bar.symbol.raw in bars_by_symbol:
            bars_by_symbol[bar.symbol.raw].append(bar)

    quotes: list[Quote] = []
    for raw_symbol in symbols:
        symbol_bars = sorted(bars_by_symbol[raw_symbol], key=lambda row: row.ts)
        if not symbol_bars:
            raise DataSourceError(
                "No market-data bars available for quote",
                details={"symbol": raw_symbol},
            )
        latest = symbol_bars[-1]
        quotes.append(
            Quote(
                symbol=latest.symbol,
                bid=None,
                ask=None,
                last=latest.close,
                ts=latest.ts,
            )
        )
    return quotes


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

    models = _available_forecast_models(sorted_bars, horizon_days=horizon_days)
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


def forecast_consensus_rows_for_bars(
    bars: list[Bar],
    *,
    horizon_days: int = 1,
) -> list[dict[str, str]]:
    """Return forecast consensus rows recalculated from already fetched OHLCV bars."""

    consensus = summarize_forecast_evaluations(
        _available_forecast_evaluations(
            bars,
            horizon_days=horizon_days,
        )
    )
    if consensus is None:
        return []
    return [
        {
            "symbol": consensus.symbol,
            "horizon_days": str(consensus.horizon_days),
            "model_count": str(consensus.model_count),
            "ensemble_forecast_close": _format_decimal(consensus.ensemble_forecast_close),
            "median_forecast_close": _format_decimal(consensus.median_forecast_close),
            "min_forecast_close": _format_decimal(consensus.min_forecast_close),
            "max_forecast_close": _format_decimal(consensus.max_forecast_close),
            "forecast_range": _format_decimal(consensus.forecast_range),
            "forecast_range_pct": _format_optional_percent(consensus.forecast_range_pct),
            "agreement": consensus.agreement,
        }
    ]


def forecast_metric_json_download(rows: list[dict[str, str]]) -> str:
    """Return forecast metric rows as stable JSON text."""

    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def forecast_metric_csv_download(rows: list[dict[str, str]]) -> str:
    """Return forecast metric rows as CSV text."""

    return table_csv_download(
        rows,
        fieldnames=[
            "model",
            "symbol",
            "horizon_days",
            "forecast_close",
            "mae",
            "rmse",
            "direction_accuracy",
            "sample_count",
        ],
    )


def forecast_reference_period(
    bars: list[Bar],
    *,
    horizon_days: int = 1,
) -> int:
    """Return the automatically selected reference period for baseline models."""

    if horizon_days < 1 or horizon_days > 30:
        raise ValueError("horizon_days must be between 1 and 30")
    bar_count = len(bars)
    if bar_count <= 3:
        return 3
    period_from_horizon = max(3, horizon_days * 2)
    period_cap = max(3, bar_count // 3)
    return min(period_from_horizon, period_cap, 30, bar_count - 1)


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
            "forecast_score": _format_decimal(score.forecast_score),
            "forecast_agreement": score.forecast_agreement,
            "data_quality": score.data_quality,
            "summary": score.summary,
            "forecast_reason": score.forecast_reason,
            "reason_labels": _quality_reasons(score.reason_labels),
            "reasons": _quality_reasons(score.reasons),
        }
        for score in scores
    ]


def investment_score_rows(scores: list[InvestmentScore]) -> list[dict[str, str]]:
    """Return Investment Score rows for UI display."""

    return [
        {
            "rank": str(score.rank),
            "symbol": score.symbol,
            "total_score": _format_decimal(score.total_score),
            "score_band": score.score_band,
            "screening_score": _format_decimal(score.screening_score),
            "forecast_agreement_score": _format_decimal(score.forecast_agreement_score),
            "data_quality_score": _format_decimal(score.data_quality_score),
            "risk_signal_score": _format_optional_decimal(score.risk_signal_score),
            "forecast_agreement": score.forecast_agreement,
            "data_quality": score.data_quality,
            "breakdown": _investment_breakdown_text(score),
            "warnings": _quality_reasons(score.warnings),
            "reasons": _quality_reasons(score.reasons),
            "note": "売買推奨ではなく、判断材料を整理したスコアです。",
        }
        for score in scores
    ]


def investment_score_json_download(rows: list[dict[str, str]]) -> str:
    """Return Investment Score rows as stable JSON text."""

    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def investment_score_csv_download(rows: list[dict[str, str]]) -> str:
    """Return Investment Score rows as CSV text."""

    return table_csv_download(
        rows,
        fieldnames=[
            "rank",
            "symbol",
            "total_score",
            "score_band",
            "screening_score",
            "forecast_agreement_score",
            "data_quality_score",
            "database_fit_score",
            "metadata_confidence_score",
            "risk_signal_score",
            "ranking_profile",
            "forecast_agreement",
            "data_quality",
            "breakdown",
            "warnings",
            "reasons",
            "note",
        ],
    )


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
            "forecast_score",
            "forecast_agreement",
            "data_quality",
            "summary",
            "forecast_reason",
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


def build_rebalance_decision_report_context(
    result: PortfolioRiskResult,
    *,
    request: RebalanceCheckRequest | None = None,
) -> DecisionReportContext:
    """Build the shared Phase 19 Decision Report context for Rebalance Cockpit."""

    context = build_rebalance_report_context(result)
    summary = context.summary
    request_summary = {}
    if request is not None:
        request_summary = {
            "positions": str(len(request.positions)),
            "targets": str(len(request.targets)),
        }
    sections = [
        build_report_section(
            title="リバランス概要",
            source_kind="rebalance",
            as_of=result.proposal.as_of,
            summary={
                **summary,
                **request_summary,
            },
            rows=[
                {"項目": "現在資産", "内容": f"{summary['total_value_jpy']} JPY"},
                {"項目": "現金", "内容": f"{summary['cash_jpy']} JPY"},
                {"項目": "配分見直し候補", "内容": f"{summary['trade_count']}件"},
                {"項目": "Risk 判定", "内容": summary["risk_status"]},
            ],
            notes=["このレポートはリバランス確認の整理であり、売買実行や売買推奨ではありません。"],
        ),
        build_report_section(
            title="現在保有",
            source_kind="rebalance",
            as_of=result.proposal.as_of,
            rows=context.current_rows,
            notes=["現在の保有数量、通貨、評価額を確認します。"],
        ),
        build_report_section(
            title="目標配分",
            source_kind="rebalance",
            as_of=result.proposal.as_of,
            rows=context.target_rows,
            notes=["目標配分は入力条件です。投資方針に合っているか確認してください。"],
        ),
        build_report_section(
            title="配分差分",
            source_kind="rebalance",
            as_of=result.proposal.as_of,
            rows=context.allocation_rows,
            notes=["drift は目標配分と現在配分の差です。大きい行ほど確認優先度が上がります。"],
        ),
        build_report_section(
            title="配分見直し候補",
            source_kind="rebalance",
            as_of=result.proposal.as_of,
            rows=context.trade_rows
            or [{"symbol": "なし", "side": "-", "qty": "0", "price_hint": "-", "currency": "-"}],
            notes=["配分見直し候補は no-solver MVP の計算結果です。実注文は行いません。"],
        ),
    ]
    if context.breach_rows:
        sections.append(
            build_report_section(
                title="Risk 制約違反",
                source_kind="rebalance",
                as_of=result.proposal.as_of,
                rows=context.breach_rows,
                notes=["Risk 判定が BLOCK / REVIEW の場合は、制約違反の内容を先に確認します。"],
            )
        )
    sections.append(
        build_decision_checkpoints_section(
            checkpoints=_rebalance_decision_checkpoints(context),
            as_of=result.proposal.as_of,
        )
    )
    return build_decision_report_context(
        title=f"投資判断レポート - リバランス {summary['account_id']}",
        sections=sections,
        tags=["rebalance", "phase-19", "local-first"],
    )


def rebalance_decision_report_json_download(context: DecisionReportContext) -> str:
    return reporting_decision_report_json_download(context)


def rebalance_decision_report_markdown_download(context: DecisionReportContext) -> str:
    return render_decision_report_markdown(context)


def rebalance_decision_report_manifest_download(context: DecisionReportContext) -> str:
    return decision_report_manifest_json_download(context)


def rebalance_decision_report_zip_download(context: DecisionReportContext) -> bytes:
    return decision_report_zip_download(context)


def _rebalance_decision_checkpoints(
    context: RebalanceReportContext,
) -> list[dict[str, str]]:
    summary = context.summary
    risk_status = summary["risk_status"]
    trade_count = summary["trade_count"]
    largest_drift = _largest_abs_percent_row(context.allocation_rows, "drift")
    checkpoints = [
        {
            "area": "Risk",
            "finding": f"Risk 判定は {risk_status} です",
            "confirmation_point": "BLOCK / REVIEW の場合は、制約違反と目標配分を先に確認します。",
        },
        {
            "area": "Trades",
            "finding": f"配分見直し候補は {trade_count} 件です",
            "confirmation_point": "配分見直し候補は実注文ではありません。数量、価格前提、通貨を確認します。",
        },
    ]
    if largest_drift:
        checkpoints.append(
            {
                "area": "Allocation",
                "finding": (
                    f"最も大きい配分差は {largest_drift.get('symbol', '対象不明')} の "
                    f"{largest_drift.get('drift', '')} です"
                ),
                "confirmation_point": "差分が意図した投資方針や許容リスクに合うか確認します。",
            }
        )
    if context.breach_rows:
        checkpoints.append(
            {
                "area": "Risk Breach",
                "finding": f"Risk 制約違反が {len(context.breach_rows)} 件あります",
                "confirmation_point": "制約違反を解消するには、目標配分、対象銘柄、現金比率を見直します。",
            }
        )
    else:
        checkpoints.append(
            {
                "area": "Risk Breach",
                "finding": "大きなRisk制約違反はありません",
                "confirmation_point": "制約違反がなくても、集中度や価格前提は確認します。",
            }
        )
    return checkpoints


def _largest_abs_percent_row(
    rows: list[dict[str, str]],
    field: str,
) -> dict[str, str] | None:
    best_row: dict[str, str] | None = None
    best_value = Decimal("-1")
    for row in rows:
        raw_value = row.get(field, "").replace("%", "").strip()
        try:
            value = abs(Decimal(raw_value))
        except Exception:  # noqa: BLE001
            continue
        if value > best_value:
            best_value = value
            best_row = row
    return best_row


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
            "target_weight": _format_percent(target.target_weight),
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
                "current_weight": _format_percent(current_weight),
                "target_weight": _format_percent(target_weight),
                "drift": _format_percent(target_weight - current_weight),
            }
        )
    return rows


def proposed_trade_rows(proposal: RebalanceProposal) -> list[dict[str, str]]:
    """Format rebalance review candidates for table display."""

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
            "## Rebalance Review Candidates",
            "",
            _markdown_table(
                context.trade_rows,
                ["symbol", "side", "qty", "price_hint", "currency"],
                empty_message="No rebalance review candidates were generated.",
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
            "description": "Review candidates generated by the MVP rebalance calculation.",
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
    return _format_percent(value)


def _format_percent(value: Decimal) -> str:
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


def _feature_missing_summary(rows: list[DailySnapshot]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        for feature, is_missing in row.missing.items():
            if is_missing:
                summary[feature] = summary.get(feature, 0) + 1
    return summary


def _feature_quality_summary(rows: list[DailySnapshot]) -> dict[DataQuality, int]:
    summary: dict[DataQuality, int] = {}
    for row in rows:
        summary[row.data_quality] = summary.get(row.data_quality, 0) + 1
    return summary


def _quality_reasons(reasons: list[str]) -> str:
    if not reasons:
        return ""
    return ", ".join(reasons)


def _investment_breakdown_text(score: InvestmentScore) -> str:
    return "; ".join(
        (
            f"{component.component}: "
            f"{_format_decimal(component.input_score)} x {_format_decimal(component.weight)} "
            f"= {_format_decimal(component.contribution)}"
        )
        for component in score.breakdown
    )


def _available_forecast_evaluations(
    bars: list[Bar],
    *,
    horizon_days: int = 1,
) -> list[ForecastEvaluation]:
    models = _available_forecast_models(bars, horizon_days=horizon_days)
    if not models:
        return []
    return evaluate_models(bars, models=models, horizon_days=horizon_days)


def _available_forecast_models(
    bars: list[Bar],
    *,
    horizon_days: int = 1,
) -> list[ForecastModel]:
    reference_period = forecast_reference_period(bars, horizon_days=horizon_days)
    return available_forecast_models(len(bars), reference_period=reference_period)


def _next_forecast_ts(bar: Bar, *, horizon_days: int = 1) -> str:
    return (bar.ts + (_ONE_DAY * horizon_days)).isoformat()


def _slug(value: str) -> str:
    return "_".join(value.lower().split())
