from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from pydantic import ValidationError

from backend.app.main import RebalanceCheckRequest, create_portfolio_risk_workflow
from backend.core.config import CONFIG_FILE_ENV, get_settings, resolve_performance_profile
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
    AdvancedForecastEvaluation,
    ForecastEvaluation,
    ForecastModel,
    advanced_forecast_adapter_specs,
    available_forecast_models,
    evaluate_advanced_forecast,
    evaluate_models,
    summarize_advanced_forecast_evaluations,
)
from backend.forecast import (
    summarize_forecast_evaluations as _summarize_forecast_evaluations,
)
from backend.forecast.adapters import ADVANCED_LINEAR_ADAPTER_NAME
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
from ui.content.common_texts import user_facing_column_label
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
JPY_FX_PAIRS_BY_CURRENCY = {
    "USD": "USDJPY",
    "HKD": "HKDJPY",
    "KRW": "KRWJPY",
    "VND": "VNDJPY",
    "IDR": "IDRJPY",
    "SGD": "SGDJPY",
    "THB": "THBJPY",
    "MYR": "MYRJPY",
    "CNY": "CNYJPY",
}


def _jpy_fx_pair_for_currency(currency: str) -> str:
    return JPY_FX_PAIRS_BY_CURRENCY.get(currency.strip().upper(), "")


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


def summarize_forecast_evaluations_for_ui(
    evaluations: list[ForecastEvaluation],
    *,
    history: list[Bar] | None = None,
) -> Any | None:
    """Summarize forecasts while tolerating a stale Streamlit backend module cache."""

    if history is None:
        return _summarize_forecast_evaluations(evaluations)
    try:
        return _summarize_forecast_evaluations(evaluations, history=history)
    except TypeError as exc:
        if "history" not in str(exc):
            raise
        consensus = _summarize_forecast_evaluations(evaluations)
        return _consensus_with_direction_fallback(consensus, evaluations, history)


def _consensus_with_direction_fallback(
    consensus: Any | None,
    evaluations: list[ForecastEvaluation],
    history: list[Bar] | None,
) -> Any | None:
    """Fill direction fields when Streamlit keeps an older backend module loaded."""

    if consensus is None or not evaluations or not history:
        return consensus
    forecasts = sorted(evaluation.latest_forecast.forecast_close for evaluation in evaluations)
    if len(forecasts) < 2:
        return consensus
    sorted_history = sorted(history, key=lambda bar: bar.ts)
    if not sorted_history:
        return consensus
    latest_close = sorted_history[-1].close
    if latest_close <= 0:
        return consensus
    ensemble = sum(forecasts, Decimal("0")) / Decimal(len(forecasts))
    median = forecasts[len(forecasts) // 2]
    if len(forecasts) % 2 == 0:
        median = (forecasts[(len(forecasts) // 2) - 1] + median) / Decimal("2")
    forecast_range_pct = (forecasts[-1] - forecasts[0]) / median if median > 0 else Decimal("0")
    signal = _fallback_forecast_direction_signal(
        latest_close=latest_close,
        ensemble_forecast_close=ensemble,
        model_forecast_closes=forecasts,
        model_forecast_weights=_fallback_model_signal_weights(evaluations),
        momentum_5d=_history_return(sorted_history, 5),
        momentum_20d=_history_return(sorted_history, 20),
        forecast_range_pct=forecast_range_pct,
    )
    updates = {
        "latest_close": _round_decimal(latest_close, "0.0001"),
        "forecast_return_pct": signal["forecast_return_pct"],
        "up_model_count": int(signal["up_model_count"]),
        "down_model_count": int(signal["down_model_count"]),
        "flat_model_count": int(signal["flat_model_count"]),
        "up_direction_ratio": signal["up_direction_ratio"],
        "down_direction_ratio": signal["down_direction_ratio"],
        "model_upside_strength_score": signal["model_upside_strength_score"],
        "model_downside_strength_score": signal["model_downside_strength_score"],
        "upside_signal_score": signal["upside_signal_score"],
        "downside_signal_score": signal["downside_signal_score"],
        "direction_net_score": signal["direction_net_score"],
        "direction_signal_label": signal["direction_signal_label"],
    }
    if hasattr(consensus, "model_copy"):
        return consensus.model_copy(update=updates)
    for key, value in updates.items():
        try:
            setattr(consensus, key, value)
        except Exception:  # noqa: BLE001
            object.__setattr__(consensus, key, value)
    return consensus


def _fallback_forecast_direction_signal(
    *,
    latest_close: Decimal,
    ensemble_forecast_close: Decimal,
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None,
    momentum_5d: Decimal | None,
    momentum_20d: Decimal | None,
    forecast_range_pct: Decimal,
) -> dict[str, Decimal | int | str]:
    model_count = len(model_forecast_closes)
    forecast_return_pct = (ensemble_forecast_close / latest_close) - Decimal("1")
    up_model_count = sum(1 for close in model_forecast_closes if close > latest_close)
    down_model_count = sum(1 for close in model_forecast_closes if close < latest_close)
    flat_model_count = model_count - up_model_count - down_model_count
    model_upside_strength_score = _fallback_model_forecast_strength_score(
        latest_close=latest_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        side="upside",
    )
    model_downside_strength_score = _fallback_model_forecast_strength_score(
        latest_close=latest_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        side="downside",
    )
    upside_signal_score = _fallback_upside_score(
        latest_close=latest_close,
        ensemble_forecast_close=ensemble_forecast_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        momentum_5d=momentum_5d,
        momentum_20d=momentum_20d,
        forecast_range_pct=forecast_range_pct,
    )
    downside_signal_score = _fallback_downside_score(
        latest_close=latest_close,
        ensemble_forecast_close=ensemble_forecast_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        momentum_5d=momentum_5d,
        momentum_20d=momentum_20d,
        forecast_range_pct=forecast_range_pct,
    )
    return {
        "forecast_return_pct": _round_decimal(forecast_return_pct, "0.0001"),
        "up_model_count": up_model_count,
        "down_model_count": down_model_count,
        "flat_model_count": flat_model_count,
        "up_direction_ratio": _round_decimal(
            Decimal(up_model_count) / Decimal(model_count),
            "0.0001",
        ),
        "down_direction_ratio": _round_decimal(
            Decimal(down_model_count) / Decimal(model_count),
            "0.0001",
        ),
        "model_upside_strength_score": model_upside_strength_score,
        "model_downside_strength_score": model_downside_strength_score,
        "upside_signal_score": upside_signal_score,
        "downside_signal_score": downside_signal_score,
        "direction_net_score": _fallback_clamp_score(
            Decimal("50") + ((upside_signal_score - downside_signal_score) / 2)
        ),
        "direction_signal_label": _fallback_direction_label(
            upside_signal_score,
            downside_signal_score,
        ),
    }


def _fallback_upside_score(
    *,
    latest_close: Decimal,
    ensemble_forecast_close: Decimal,
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None,
    momentum_5d: Decimal | None,
    momentum_20d: Decimal | None,
    forecast_range_pct: Decimal,
) -> Decimal:
    forecast_return_pct = (ensemble_forecast_close / latest_close) - Decimal("1")
    forecast_return_score = _fallback_linear_score(
        forecast_return_pct,
        low=Decimal("-0.03"),
        mid=Decimal("0"),
        high=Decimal("0.10"),
    )
    model_strength_score = _fallback_model_forecast_strength_score(
        latest_close=latest_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        side="upside",
    )
    momentum_score = Decimal("50")
    if momentum_5d is not None and momentum_5d > 0:
        momentum_score += Decimal("25")
    if momentum_20d is not None and momentum_20d > 0:
        momentum_score += Decimal("25")
    raw_score = (
        forecast_return_score * Decimal("0.40")
        + model_strength_score * Decimal("0.45")
        + momentum_score * Decimal("0.15")
    )
    return _fallback_confidence_adjusted_direction_score(raw_score, forecast_range_pct)


def _fallback_downside_score(
    *,
    latest_close: Decimal,
    ensemble_forecast_close: Decimal,
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None,
    momentum_5d: Decimal | None,
    momentum_20d: Decimal | None,
    forecast_range_pct: Decimal,
) -> Decimal:
    forecast_return_pct = (ensemble_forecast_close / latest_close) - Decimal("1")
    forecast_decline_score = Decimal("100") - _fallback_linear_score(
        forecast_return_pct,
        low=Decimal("-0.10"),
        mid=Decimal("0"),
        high=Decimal("0.03"),
    )
    model_strength_score = _fallback_model_forecast_strength_score(
        latest_close=latest_close,
        model_forecast_closes=model_forecast_closes,
        model_forecast_weights=model_forecast_weights,
        side="downside",
    )
    momentum_score = Decimal("50")
    if momentum_5d is not None and momentum_5d < 0:
        momentum_score += Decimal("25")
    if momentum_20d is not None and momentum_20d < 0:
        momentum_score += Decimal("25")
    raw_score = (
        forecast_decline_score * Decimal("0.40")
        + model_strength_score * Decimal("0.45")
        + momentum_score * Decimal("0.15")
    )
    return _fallback_confidence_adjusted_direction_score(raw_score, forecast_range_pct)


def _fallback_model_forecast_strength_score(
    *,
    latest_close: Decimal,
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None,
    side: str,
) -> Decimal:
    if latest_close <= 0 or not model_forecast_closes:
        return Decimal("50")
    weights = _fallback_model_weights_for_closes(
        model_forecast_closes,
        model_forecast_weights,
    )
    weighted_total = Decimal("0")
    total_weight = Decimal("0")
    for forecast_close, weight in zip(model_forecast_closes, weights):
        forecast_return_pct = (forecast_close / latest_close) - Decimal("1")
        if side == "upside":
            model_score = _fallback_linear_score(
                forecast_return_pct,
                low=Decimal("-0.02"),
                mid=Decimal("0"),
                high=Decimal("0.20"),
            )
        else:
            model_score = Decimal("100") - _fallback_linear_score(
                forecast_return_pct,
                low=Decimal("-0.20"),
                mid=Decimal("0"),
                high=Decimal("0.02"),
            )
        weighted_total += model_score * weight
        total_weight += weight
    if total_weight <= 0:
        return Decimal("50")
    return _fallback_clamp_score(weighted_total / total_weight)


def _fallback_model_signal_weights(evaluations: list[ForecastEvaluation]) -> list[Decimal]:
    weights: list[Decimal] = []
    for evaluation in evaluations:
        sample_count = evaluation.metrics.sample_count
        if sample_count <= 0:
            weights.append(Decimal("1"))
            continue
        direction_accuracy = min(
            max(evaluation.metrics.direction_accuracy, Decimal("0")),
            Decimal("1"),
        )
        raw_weight = Decimal("0.80") + (direction_accuracy * Decimal("0.40"))
        sample_confidence = min(Decimal(sample_count) / Decimal("20"), Decimal("1"))
        blended_weight = Decimal("1") + ((raw_weight - Decimal("1")) * sample_confidence)
        weights.append(
            _round_decimal(
                min(max(blended_weight, Decimal("0.80")), Decimal("1.20")),
                "0.0001",
            )
        )
    return weights


def _fallback_model_weights_for_closes(
    model_forecast_closes: list[Decimal],
    model_forecast_weights: list[Decimal] | None,
) -> list[Decimal]:
    model_count = len(model_forecast_closes)
    if not model_forecast_weights:
        return [Decimal("1") for _ in model_forecast_closes]
    normalized = [
        min(max(weight, Decimal("0.10")), Decimal("3.00"))
        for weight in model_forecast_weights[:model_count]
    ]
    if len(normalized) < model_count:
        normalized.extend(Decimal("1") for _ in range(model_count - len(normalized)))
    return normalized


def _history_return(history: list[Bar], periods: int) -> Decimal | None:
    if len(history) <= periods:
        return None
    base = history[-(periods + 1)].close
    if base <= 0:
        return None
    return (history[-1].close / base) - Decimal("1")


def _fallback_linear_score(
    value: Decimal,
    *,
    low: Decimal,
    mid: Decimal,
    high: Decimal,
) -> Decimal:
    if value <= low:
        return Decimal("0")
    if value >= high:
        return Decimal("100")
    if value <= mid:
        return Decimal("50") * ((value - low) / (mid - low))
    return Decimal("50") + (Decimal("50") * ((value - mid) / (high - mid)))


def _fallback_agreement_confidence(forecast_range_pct: Decimal) -> Decimal:
    if forecast_range_pct <= Decimal("0.01"):
        return Decimal("100")
    if forecast_range_pct <= Decimal("0.03"):
        return Decimal("70")
    return Decimal("40")


def _fallback_confidence_adjusted_direction_score(
    raw_score: Decimal,
    forecast_range_pct: Decimal,
) -> Decimal:
    confidence = _fallback_agreement_confidence(forecast_range_pct) / Decimal("100")
    factor = Decimal("0.85") + (confidence * Decimal("0.15"))
    return _fallback_clamp_score(Decimal("50") + ((raw_score - Decimal("50")) * factor))


def _fallback_direction_label(upside: Decimal, downside: Decimal) -> str:
    gap = upside - downside
    if upside >= Decimal("80") and gap >= Decimal("20"):
        return "STRONG_UPSIDE"
    if upside >= Decimal("65") and gap >= Decimal("10"):
        return "MODERATE_UPSIDE"
    if downside >= Decimal("80") and gap <= Decimal("-20"):
        return "STRONG_DOWNSIDE"
    if downside >= Decimal("65") and gap <= Decimal("-10"):
        return "MODERATE_DOWNSIDE"
    return "NEUTRAL"


def _fallback_clamp_score(value: Decimal) -> Decimal:
    return _round_decimal(min(max(value, Decimal("0")), Decimal("100")), "0.01")


def _round_decimal(value: Decimal, exponent: str) -> Decimal:
    return value.quantize(Decimal(exponent))


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
    advanced_forecast_rows: list[dict[str, str]] = field(default_factory=list)
    advanced_forecast_consensus_rows: list[dict[str, str]] = field(default_factory=list)


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
    performance_profile = resolve_performance_profile(settings)
    return {
        "provider": settings.dataaccess.provider,
        "csv_data_dir": settings.dataaccess.csv_data_dir,
        "config_file": os.getenv(CONFIG_FILE_ENV) or "defaults",
        "scenario_dir": str(rebalance_scenario_dir()),
        "performance_profile": performance_profile.selected_profile,
        "performance_requested_profile": performance_profile.requested_profile,
        "performance_fallback_used": str(performance_profile.fallback_used),
        "external_fetch_max_workers": str(performance_profile.external_fetch.max_workers),
        "external_fetch_timeout_sec": str(performance_profile.external_fetch.request_timeout_sec),
        "external_fetch_global_timeout_sec": str(
            performance_profile.external_fetch.global_timeout_sec
        ),
        "external_fetch_cache_ttl_minutes": str(
            performance_profile.external_fetch.cache_ttl_minutes
        ),
        "llm_workers": str(performance_profile.processing.llm_workers),
    }


async def _fetch_market_data_preview_provider_bars(
    adapter: Any,
    *,
    provider_symbol: str,
    display_symbol: str,
    provider: str,
    start: datetime,
    end: datetime,
    warning_rows: list[dict[str, str]],
) -> list[Bar]:
    try:
        return await adapter.fetch_ohlcv([provider_symbol], start=start, end=end)
    except AppError as exc:
        if not _should_retry_yahoo_domestic_price_fetch(
            exc,
            provider=provider,
            provider_symbol=provider_symbol,
        ):
            raise
        retry_end = end - timedelta(days=1)
        if retry_end <= start:
            raise
        retry_bars = await adapter.fetch_ohlcv([provider_symbol], start=start, end=retry_end)
        warning_rows.append(
            {
                "code": "APP-WARN-YAHOO-DOMESTIC-RETRY",
                "message": (
                    "Yahoo国内株の当日価格行に空値があったため、"
                    "終了日を1日前にずらして再取得しました。"
                ),
                "details": json.dumps(
                    {
                        "symbol": display_symbol,
                        "provider_symbol": provider_symbol,
                        "original_end": end.isoformat(),
                        "retry_end": retry_end.isoformat(),
                        "cause": exc.message,
                        "details": exc.details,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
        return retry_bars


def _should_retry_yahoo_domestic_price_fetch(
    exc: AppError,
    *,
    provider: str,
    provider_symbol: str,
) -> bool:
    if provider != "yahoo" or not provider_symbol.endswith(".T"):
        return False
    details_text = json.dumps(exc.details, ensure_ascii=False, sort_keys=True).lower()
    message_text = exc.message.lower()
    return (
        "empty numeric value" in message_text
        or "empty numeric value" in details_text
        or "no valid numeric data" in message_text
        or "no valid numeric data" in details_text
        or '"column": "close"' in details_text
    )


async def build_market_data_preview(
    *,
    symbol: str,
    start: date,
    end: date,
    provider_override: str | None = None,
    forecast_horizon_days: int = 1,
    fx_pair: str = "",
) -> MarketDataPreview:
    """Fetch a small market-data preview for the configured provider."""

    if forecast_horizon_days < 1 or forecast_horizon_days > 60:
        raise ValueError("forecast_horizon_days must be between 1 and 60")

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
        warning_rows: list[dict[str, str]] = []
        provider_bars = await _fetch_market_data_preview_provider_bars(
            adapter,
            provider_symbol=provider_symbol,
            display_symbol=symbol,
            provider=provider,
            start=feature_start_dt,
            end=end_dt,
            warning_rows=warning_rows,
        )
        feature_bars = _bars_with_display_symbol(provider_bars, display_symbol=symbol)
        bars = _bars_in_period(feature_bars, start=start_dt, end=end_dt)
        quotes = _quotes_from_latest_bars([symbol], feature_bars)
        fx_rates: list[Any] = []
        if _should_fetch_market_data_preview_fx(provider=provider):
            source_currency = (
                str(feature_bars[-1].symbol.currency).strip().upper() if feature_bars else ""
            )
            effective_fx_pair = (
                fx_pair.strip().upper() if fx_pair else _jpy_fx_pair_for_currency(source_currency)
            )
            try:
                fx_rates = (
                    await adapter.get_fx_rates([effective_fx_pair], at=end_dt)
                    if effective_fx_pair
                    else []
                )
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
            feature_bars,
            horizon_days=forecast_horizon_days,
        )
        forecast_consensus = summarize_forecast_evaluations_for_ui(
            forecast_evaluations,
            history=feature_bars,
        )
        forecast_consensus_by_symbol = (
            {forecast_consensus.symbol: forecast_consensus}
            if forecast_consensus is not None
            else {}
        )
        advanced_forecast_results = advanced_forecast_results_for_bars(
            feature_bars,
            horizon_days=forecast_horizon_days,
        )
        advanced_forecast_rows = advanced_forecast_rows_for_results(
            advanced_forecast_results,
            feature_bars,
        )
        advanced_forecast_consensus_rows = advanced_forecast_consensus_rows_for_results(
            advanced_forecast_results,
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
            advanced_forecast_rows=advanced_forecast_rows,
            advanced_forecast_consensus_rows=advanced_forecast_consensus_rows,
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
        advanced_forecast_rows=advanced_forecast_rows,
        advanced_forecast_consensus_rows=advanced_forecast_consensus_rows,
    )


def _should_fetch_market_data_preview_fx(*, provider: str) -> bool:
    _ = provider
    return True


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
    advanced_forecast_rows: list[dict[str, str]] | None = None,
    advanced_forecast_consensus_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Return actual close and model forecast rows for chart display."""

    if horizon_days < 1 or horizon_days > 60:
        raise ValueError("horizon_days must be between 1 and 60")

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

    latest_bar = sorted_bars[-1]
    latest_ts = latest_bar.ts.isoformat()
    if advanced_forecast_consensus_rows:
        for row in advanced_forecast_consensus_rows:
            advanced_horizon = _int_from_text(row.get("horizon_days", ""))
            forecast_close = row.get("forecast_close", "")
            if advanced_horizon <= 0 or not forecast_close:
                continue
            series_key = advanced_forecast_consensus_chart_series_key(advanced_horizon)
            rows_by_ts[latest_ts][series_key] = _format_decimal(latest_bar.close)
            forecast_ts = _next_forecast_ts(latest_bar, horizon_days=advanced_horizon)
            forecast_row = rows_by_ts.setdefault(forecast_ts, {"ts": forecast_ts, "close": ""})
            forecast_row[series_key] = forecast_close
            forecast_close_lower = row.get("forecast_close_lower", "")
            forecast_close_upper = row.get("forecast_close_upper", "")
            if forecast_close_lower and forecast_close_upper:
                rows_by_ts[latest_ts][f"{series_key}_lower"] = _format_decimal(latest_bar.close)
                rows_by_ts[latest_ts][f"{series_key}_upper"] = _format_decimal(latest_bar.close)
                forecast_row[f"{series_key}_lower"] = forecast_close_lower
                forecast_row[f"{series_key}_upper"] = forecast_close_upper

    if advanced_forecast_rows:
        for row in advanced_forecast_rows:
            advanced_horizon = _int_from_text(row.get("horizon_days", ""))
            forecast_close = row.get("forecast_close", "")
            if advanced_horizon <= 0 or not forecast_close:
                continue
            adapter_name = row.get("adapter", ADVANCED_LINEAR_ADAPTER_NAME)
            series_key = advanced_forecast_chart_series_key(adapter_name, advanced_horizon)
            rows_by_ts[latest_ts][series_key] = _format_decimal(latest_bar.close)
            forecast_ts = _next_forecast_ts(latest_bar, horizon_days=advanced_horizon)
            forecast_row = rows_by_ts.setdefault(forecast_ts, {"ts": forecast_ts, "close": ""})
            forecast_row[series_key] = forecast_close
            if adapter_name == "advanced_quantile":
                forecast_close_lower = row.get("forecast_close_lower", "")
                forecast_close_upper = row.get("forecast_close_upper", "")
                if forecast_close_lower and forecast_close_upper:
                    rows_by_ts[latest_ts][f"{series_key}_lower"] = _format_decimal(latest_bar.close)
                    rows_by_ts[latest_ts][f"{series_key}_upper"] = _format_decimal(latest_bar.close)
                    forecast_row[f"{series_key}_lower"] = forecast_close_lower
                    forecast_row[f"{series_key}_upper"] = forecast_close_upper

    return [rows_by_ts[key] for key in sorted(rows_by_ts)]


def advanced_forecast_results_for_bars(
    bars: list[Bar],
    *,
    horizon_days: int | None = None,
) -> list[AdvancedForecastEvaluation]:
    """Return supported advanced forecasts when enough local history exists."""

    if not bars:
        return []
    results: list[AdvancedForecastEvaluation] = []
    for spec in advanced_forecast_adapter_specs():
        target_horizons = (
            (horizon_days,)
            if horizon_days is not None
            else _legacy_ranking_advanced_forecast_horizons(spec.supported_horizons)
        )
        for target_horizon_days in target_horizons:
            try:
                results.append(
                    evaluate_advanced_forecast(
                        bars,
                        adapter_name=spec.key,
                        horizon_days=target_horizon_days,
                    )
                )
            except ValueError:
                continue
    return results


def advanced_linear_forecast_results_for_bars(
    bars: list[Bar],
    *,
    horizon_days: int | None = None,
) -> list[Any]:
    """Return supported advanced-linear forecasts when enough local history exists."""

    return [
        result
        for result in advanced_forecast_results_for_bars(bars, horizon_days=horizon_days)
        if getattr(result, "adapter_name", "") == ADVANCED_LINEAR_ADAPTER_NAME
    ]


def _legacy_ranking_advanced_forecast_horizons(
    supported_horizons: tuple[int, ...],
) -> tuple[int, ...]:
    """Return the historical multi-horizon default when a caller does not choose one."""

    legacy_horizons = tuple(horizon for horizon in (5, 20) if horizon in supported_horizons)
    return legacy_horizons or supported_horizons


def advanced_forecast_rows_for_results(
    results: list[Any],
    bars: list[Bar],
) -> list[dict[str, str]]:
    """Return advanced forecast rows for Streamlit detail display."""

    sorted_bars = sorted(bars, key=lambda row: row.ts)
    if not sorted_bars:
        return []

    latest_close = sorted_bars[-1].close
    rows: list[dict[str, str]] = []
    for result in results:
        metrics = result.validation_metrics
        forecast_close = latest_close * (Decimal("1") + result.predicted_return)
        predicted_return_lower = getattr(result, "predicted_return_lower", None)
        predicted_return_upper = getattr(result, "predicted_return_upper", None)
        forecast_close_lower = (
            latest_close * (Decimal("1") + predicted_return_lower)
            if predicted_return_lower is not None
            else None
        )
        forecast_close_upper = (
            latest_close * (Decimal("1") + predicted_return_upper)
            if predicted_return_upper is not None
            else None
        )
        rows.append(
            {
                "adapter": result.adapter_name,
                "model": result.model_name,
                "model_label": advanced_forecast_model_label(result.adapter_name),
                "symbol": result.symbol,
                "horizon_days": str(result.horizon_days),
                "predicted_return": _format_percent(result.predicted_return),
                "predicted_return_lower": _format_optional_percent(predicted_return_lower),
                "predicted_return_upper": _format_optional_percent(predicted_return_upper),
                "forecast_close": _format_decimal(forecast_close),
                "forecast_close_lower": _format_optional_decimal(forecast_close_lower),
                "forecast_close_upper": _format_optional_decimal(forecast_close_upper),
                "direction_score": _format_percent(result.direction_score),
                "confidence": result.confidence,
                "mae": _format_decimal(metrics.mae),
                "rmse": _format_decimal(metrics.rmse),
                "direction_accuracy": _format_percent(metrics.direction_accuracy),
                "fold_count": str(metrics.fold_count),
                "sample_count": str(metrics.sample_count),
                "baseline_zero_rmse": _format_optional_decimal(metrics.baseline_zero_rmse),
                "rmse_improvement": _format_optional_decimal(metrics.rmse_improvement),
                "top_features": _feature_contribution_text(
                    result.feature_contribution_summary,
                ),
                "warnings": "; ".join(result.warnings),
            }
        )
    return rows


def advanced_forecast_consensus_rows_for_results(
    results: list[AdvancedForecastEvaluation],
) -> list[dict[str, str]]:
    """Return advanced forecast consensus rows for Streamlit summary display."""

    consensus = summarize_advanced_forecast_evaluations(results)
    if consensus is None:
        return []
    return [
        {
            "symbol": consensus.symbol,
            "horizon_days": str(consensus.horizon_days),
            "model_count": str(consensus.model_count),
            "predicted_return": _format_percent(consensus.consensus_predicted_return),
            "forecast_close": _format_decimal(consensus.consensus_forecast_close),
            "predicted_return_lower": _format_optional_percent(consensus.predicted_return_lower),
            "predicted_return_upper": _format_optional_percent(consensus.predicted_return_upper),
            "forecast_close_lower": _format_optional_decimal(consensus.forecast_close_lower),
            "forecast_close_upper": _format_optional_decimal(consensus.forecast_close_upper),
            "predicted_return_range": _format_percent(consensus.predicted_return_range),
            "agreement": consensus.agreement,
            "confidence": consensus.confidence,
            "direction_agreement_score": _format_decimal(consensus.direction_agreement_score),
            "weighted_direction_score": _format_percent(consensus.weighted_direction_score),
            "mean_direction_accuracy": _format_percent(consensus.mean_direction_accuracy),
            "mean_rmse": _format_decimal(consensus.mean_rmse),
            "mean_rmse_improvement": _format_optional_decimal(consensus.mean_rmse_improvement),
            "best_adapter": consensus.best_adapter_name,
            "best_model": consensus.best_model_name,
            "warnings": "; ".join(consensus.warnings),
        }
    ]


def advanced_forecast_consensus_rows_for_bars(
    bars: list[Bar],
    *,
    horizon_days: int,
) -> list[dict[str, str]]:
    """Return advanced forecast consensus rows recalculated from fetched bars."""

    return advanced_forecast_consensus_rows_for_results(
        advanced_forecast_results_for_bars(bars, horizon_days=horizon_days)
    )


def advanced_linear_forecast_rows(
    results: list[Any],
    bars: list[Bar],
) -> list[dict[str, str]]:
    """Return advanced-linear forecast rows for Streamlit detail display."""

    return advanced_forecast_rows_for_results(results, bars)


def advanced_forecast_chart_series_key(adapter_name: str, horizon_days: int) -> str:
    return f"{adapter_name}_{horizon_days}d"


def advanced_forecast_consensus_chart_series_key(horizon_days: int) -> str:
    return f"advanced_consensus_{horizon_days}d"


def advanced_forecast_model_label(adapter_name: str) -> str:
    if adapter_name == "advanced_linear":
        return "高度予測: 線形モデル"
    if adapter_name == "advanced_tree_sklearn":
        return "高度予測: ツリーモデル"
    if adapter_name == "advanced_gbdt_sklearn":
        return "高度予測: ブースティングモデル"
    if adapter_name == "advanced_quantile":
        return "高度予測: レンジモデル"
    return f"高度予測: {adapter_name}"


def _feature_contribution_text(contributions: list[Any]) -> str:
    labels = {"positive": "押し上げ", "negative": "押し下げ"}
    parts: list[str] = []
    for contribution in contributions:
        effect = labels.get(str(contribution.effect), str(contribution.effect))
        parts.append(f"{contribution.feature}: {effect} {_format_decimal(contribution.weight)}")
    return ", ".join(parts)


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

    consensus = summarize_forecast_evaluations_for_ui(
        _available_forecast_evaluations(
            bars,
            horizon_days=horizon_days,
        ),
        history=bars,
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
            "latest_close": _format_optional_decimal(getattr(consensus, "latest_close", None)),
            "forecast_return_pct": _format_optional_percent(
                getattr(consensus, "forecast_return_pct", Decimal("0"))
            ),
            "up_model_count": str(getattr(consensus, "up_model_count", 0)),
            "down_model_count": str(getattr(consensus, "down_model_count", 0)),
            "flat_model_count": str(getattr(consensus, "flat_model_count", 0)),
            "up_direction_ratio": _format_optional_percent(
                getattr(consensus, "up_direction_ratio", Decimal("0"))
            ),
            "down_direction_ratio": _format_optional_percent(
                getattr(consensus, "down_direction_ratio", Decimal("0"))
            ),
            "upside_signal_score": _format_decimal(
                getattr(consensus, "upside_signal_score", Decimal("50"))
            ),
            "downside_signal_score": _format_decimal(
                getattr(consensus, "downside_signal_score", Decimal("50"))
            ),
            "direction_net_score": _format_decimal(
                getattr(consensus, "direction_net_score", Decimal("50"))
            ),
            "direction_signal_label": str(getattr(consensus, "direction_signal_label", "UNKNOWN")),
        }
    ]


def forecast_metric_json_download(rows: list[dict[str, str]]) -> str:
    """Return forecast metric rows as stable JSON text."""

    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def forecast_metric_csv_download(rows: list[dict[str, str]]) -> bytes:
    """Return forecast metric rows as UTF-8 BOM CSV bytes."""

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

    if horizon_days < 1 or horizon_days > 60:
        raise ValueError("horizon_days must be between 1 and 60")
    bar_count = len(bars)
    if bar_count <= 3:
        return 3
    period_from_horizon = max(3, horizon_days * 2)
    period_cap = max(3, bar_count // 3)
    return min(period_from_horizon, period_cap, 60, bar_count - 1)


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
            "upside_signal_score": _format_decimal(
                getattr(score, "upside_signal_score", Decimal("50"))
            ),
            "downside_signal_score": _format_decimal(
                getattr(score, "downside_signal_score", Decimal("50"))
            ),
            "direction_net_score": _format_decimal(
                getattr(score, "direction_net_score", Decimal("50"))
            ),
            "direction_signal_label": str(getattr(score, "direction_signal_label", "UNKNOWN")),
            "forecast_return_pct": _format_optional_percent(
                getattr(score, "forecast_return_pct", Decimal("0"))
            ),
            "up_model_count": str(getattr(score, "up_model_count", 0)),
            "down_model_count": str(getattr(score, "down_model_count", 0)),
            "flat_model_count": str(getattr(score, "flat_model_count", 0)),
            "data_quality_score": _format_decimal(score.data_quality_score),
            "research_score": _format_optional_decimal(getattr(score, "research_score", None)),
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


def investment_score_csv_download(rows: list[dict[str, str]]) -> bytes:
    """Return Investment Score rows as UTF-8 BOM CSV bytes."""

    return table_csv_download(
        rows,
        fieldnames=[
            "rank",
            "symbol",
            "total_score",
            "score_band",
            "screening_score",
            "forecast_agreement_score",
            "upside_signal_score",
            "downside_signal_score",
            "direction_net_score",
            "direction_signal_label",
            "forecast_return_pct",
            "advanced_forecast_horizon_days",
            "advanced_forecast_predicted_return",
            "advanced_forecast_score",
            "advanced_forecast_confidence",
            "up_model_count",
            "down_model_count",
            "flat_model_count",
            "data_quality_score",
            "database_fit_score",
            "metadata_confidence_score",
            "research_score",
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


def screening_score_csv_download(rows: list[dict[str, str]]) -> bytes:
    """Return screening score rows as UTF-8 BOM CSV bytes."""

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
                {"項目": "リスク判定", "内容": summary["risk_status"]},
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
                title="リスク制約違反",
                source_kind="rebalance",
                as_of=result.proposal.as_of,
                rows=context.breach_rows,
                notes=["リスク判定が BLOCK / REVIEW の場合は、制約違反の内容を先に確認します。"],
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
            "area": "リスク判定",
            "finding": f"リスク判定は {risk_status} です",
            "confirmation_point": "BLOCK / REVIEW の場合は、制約違反と目標配分を先に確認します。",
        },
        {
            "area": "配分見直し候補",
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
                "area": "リスク制約違反",
                "finding": f"リスク制約違反が {len(context.breach_rows)} 件あります",
                "confirmation_point": "制約違反を解消するには、目標配分、対象銘柄、現金比率を見直します。",
            }
        )
    else:
        checkpoints.append(
            {
                "area": "リスク制約違反",
                "finding": "大きなリスク制約違反はありません",
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
        "# リバランス確認レポート",
        "",
        "## サマリー",
        "",
        f"- 口座ID: {summary['account_id']}",
        f"- 基準日: {summary['as_of']}",
        f"- 現在資産(円): {summary['total_value_jpy']}",
        f"- 現金(円): {summary['cash_jpy']}",
        f"- 配分見直し候補: {summary['trade_count']}",
        f"- リスク判定: {summary['risk_status']}",
    ]
    if request is not None:
        lines.extend(
            [
                "",
                "## 入力条件",
                "",
                f"- 現在保有: {len(request.positions)}件",
                f"- 目標配分: {len(request.targets)}件",
            ]
        )

    lines.extend(
        [
            "",
            "## 現在の保有",
            "",
            _markdown_table(
                context.current_rows,
                ["symbol", "qty", "currency", "last", "fx_rate_jpy", "value_jpy"],
                empty_message="現在の保有データはまだありません。",
            ),
            "",
            "## 目標配分",
            "",
            _markdown_table(
                context.target_rows,
                ["symbol", "currency", "target_weight"],
                empty_message="目標配分はまだありません。",
            ),
            "",
            "## 配分比較",
            "",
            _markdown_table(
                context.allocation_rows,
                ["symbol", "current_weight", "target_weight", "drift"],
            ),
            "",
            "## 配分見直し候補",
            "",
            _markdown_table(
                context.trade_rows,
                ["symbol", "side", "qty", "price_hint", "currency"],
                empty_message="配分見直し候補はありません。",
            ),
        ]
    )

    lines.extend(
        [
            "",
            "## リスク確認事項",
            "",
        ]
    )
    if context.breach_rows:
        lines.extend(f"- {row['breach']}" for row in context.breach_rows)
    else:
        lines.append("- なし")
    return "\n".join(lines) + "\n"


def result_table_downloads(result: PortfolioRiskResult) -> dict[str, bytes]:
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

    files: dict[str, str | bytes] = {
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
) -> bytes:
    """Return stable UTF-8 BOM CSV bytes for UI table downloads."""

    resolved_fieldnames = fieldnames or (list(rows[0]) if rows else [])
    if not resolved_fieldnames:
        return b""
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=resolved_fieldnames, lineterminator="\n")
    writer.writeheader()
    filtered_rows = (
        {fieldname: row.get(fieldname, "") for fieldname in resolved_fieldnames} for row in rows
    )
    writer.writerows(filtered_rows)
    return buffer.getvalue().encode("utf-8-sig")


def zip_text_downloads(files: dict[str, str | bytes]) -> bytes:
    """Return a deterministic ZIP archive for text or byte download payloads."""

    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as archive:
        for filename in sorted(files):
            info = ZipInfo(filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            payload = files[filename]
            archive.writestr(
                info,
                payload if isinstance(payload, bytes) else payload.encode("utf-8"),
            )
    return buffer.getvalue()


def _markdown_table(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    *,
    empty_message: str = "表示できる行はありません。",
) -> str:
    if not rows:
        return empty_message
    header = "| " + " | ".join(user_facing_column_label(field) for field in fieldnames) + " |"
    separator = "| " + " | ".join("---" for _ in fieldnames) + " |"
    body = [
        "| " + " | ".join(_markdown_cell(row.get(field, "")) for field in fieldnames) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|")


def _load_json_list(value: str, field_name: str) -> list[dict[str, Any]]:
    field_label = {
        "positions": "現在保有",
        "targets": "目標配分",
    }.get(field_name, field_name)
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_label}は有効なJSONで入力してください。") from exc
    if not isinstance(data, list):
        raise ValueError(f"{field_label}はJSON配列で入力してください。")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{field_label}はJSONオブジェクトの配列で入力してください。")
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


def _int_from_text(value: object) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


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
