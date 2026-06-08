from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ConfigDict, Field

from backend.core.config import get_settings
from backend.core.data_contracts import Bar, Position, StrictBaseModel, TradeIntent
from backend.core.errors import AppError, ComputationError
from backend.forecast import (
    AdvancedForecastEvaluation,
    ForecastConsensus,
    ForecastEvaluation,
    ForecastModel,
    advanced_forecast_adapter_keys,
    advanced_forecast_adapter_spec,
    advanced_forecast_supported_horizons,
    available_forecast_models,
    evaluate_advanced_forecast,
    evaluate_models,
    summarize_forecast_evaluations,
)
from backend.marketdata import FeatureBuilder, create_market_data_provider_adapter
from backend.portfolio import (
    PortfolioRiskResult,
    PortfolioRiskWorkflow,
    PortfolioService,
    TargetAllocation,
)
from backend.risk import RiskDecision, RiskService
from backend.scoring import InvestmentScore, InvestmentScoringService
from backend.screening import ScreeningScore, ScreeningService

APP_DESCRIPTION = """
Smart Market AI MVP API for deterministic local investment-support workflows.

The current API uses deterministic market-data providers and does not submit orders to a broker.
Decimal values are accepted as JSON strings in examples to avoid floating-point ambiguity.
"""


class AppErrorResponse(StrictBaseModel):
    """Structured domain error returned by application exception handlers."""

    code: str = Field(examples=["APP-2002"])
    message: str = Field(examples=["Target weights must not exceed 1"])
    details: dict[str, object] = Field(default_factory=dict)


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    429: {
        "description": "Market-data provider rate limit.",
        "model": AppErrorResponse,
    },
    422: {
        "description": "Domain computation error or request validation error.",
        "model": AppErrorResponse,
    },
    502: {
        "description": "Market-data source error.",
        "model": AppErrorResponse,
    },
    503: {
        "description": "Market-data provider unavailable.",
        "model": AppErrorResponse,
    },
    504: {
        "description": "Market-data provider timeout.",
        "model": AppErrorResponse,
    },
}

app = FastAPI(
    title="Smart Market AI API",
    version="0.1.0",
    description=APP_DESCRIPTION,
    openapi_tags=[
        {
            "name": "Health",
            "description": "Operational readiness checks.",
        },
        {
            "name": "Risk",
            "description": "Pre-trade risk checks for proposed order baskets.",
        },
        {
            "name": "Portfolio",
            "description": "Portfolio valuation and rebalance proposal workflows.",
        },
        {
            "name": "Screening",
            "description": "Explainable symbol ranking from Feature Store Lite snapshots.",
        },
        {
            "name": "Forecast",
            "description": "Deterministic baseline forecasts and walk-forward metrics.",
        },
        {
            "name": "Scoring",
            "description": "Model-informed investment-support scores.",
        },
    ],
)


class PreTradeCheckRequest(StrictBaseModel):
    """Request body for the Risk MVP pre-trade check endpoint."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "account_id": "acct-1",
                    "as_of": "2026-04-09",
                    "basket": [
                        {
                            "symbol": "AAPL",
                            "side": "BUY",
                            "qty": "10",
                            "price_hint": "175",
                            "currency": "USD",
                        }
                    ],
                }
            ]
        },
    )

    account_id: str = Field(min_length=1)
    as_of: date
    basket: list[TradeIntent] = Field(min_length=1)


class RebalanceCheckRequest(StrictBaseModel):
    """Request body for the Portfolio-to-Risk rebalance check endpoint."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "account_id": "acct-1",
                    "as_of": "2026-04-09",
                    "positions": [
                        {
                            "symbol": "7203.T",
                            "qty": "10",
                            "avg_price": "2800",
                            "currency": "JPY",
                        }
                    ],
                    "targets": [
                        {
                            "symbol": "7203.T",
                            "currency": "JPY",
                            "target_weight": "0.5",
                        },
                        {
                            "symbol": "AAPL",
                            "currency": "USD",
                            "target_weight": "0.5",
                        },
                    ],
                    "cash_jpy": "29000",
                }
            ]
        },
    )

    account_id: str = Field(min_length=1)
    as_of: date
    positions: list[Position] = Field(default_factory=list)
    targets: list[TargetAllocation] = Field(default_factory=list)
    cash_jpy: Decimal = Field(default=Decimal("0"), ge=0)


class ScreeningScoreRequest(StrictBaseModel):
    """Request body for explainable screening score ranking."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "symbols": ["AAPL", "7203.T"],
                    "as_of": "2026-04-09",
                }
            ]
        },
    )

    symbols: list[str] = Field(min_length=1)
    as_of: date


class ForecastEvaluateRequest(StrictBaseModel):
    """Request body for deterministic forecast evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "symbol": "AAPL",
                    "start": "2026-04-07",
                    "end": "2026-04-09",
                    "horizon_days": 1,
                    "adapter": "baseline",
                },
                {
                    "symbol": "AAPL",
                    "start": "2026-04-01",
                    "end": "2026-06-06",
                    "horizon_days": 5,
                    "adapter": "advanced_linear",
                },
                {
                    "symbol": "AAPL",
                    "start": "2026-04-01",
                    "end": "2026-06-06",
                    "horizon_days": 20,
                    "adapter": "advanced_quantile",
                },
            ]
        },
    )

    symbol: str = Field(min_length=1)
    start: date
    end: date
    horizon_days: int = Field(default=1, ge=1, le=30)
    adapter: str = Field(default="baseline", min_length=1)


class InvestmentScoreRequest(StrictBaseModel):
    """Request body for model-informed investment-support scoring."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "symbols": ["AAPL", "7203.T"],
                    "as_of": "2026-04-09",
                    "horizon_days": 1,
                    "research_scores_by_symbol": {"AAPL": "60"},
                }
            ]
        },
    )

    symbols: list[str] = Field(min_length=1)
    as_of: date
    horizon_days: int = Field(default=1, ge=1, le=30)
    research_scores_by_symbol: dict[str, Decimal] = Field(default_factory=dict)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Return domain errors with their configured HTTP status."""

    return JSONResponse(status_code=int(exc.http_status), content=exc.to_dict())


@app.get(
    "/health",
    tags=["Health"],
    summary="Check API health",
    description="Returns a small readiness response for local smoke checks.",
)
def health():
    return {"status": "ok"}


def create_risk_service() -> RiskService:
    """Create the default Risk MVP service for API requests."""
    settings = get_settings()
    adapter = create_market_data_provider_adapter(settings.dataaccess)
    feature_builder = FeatureBuilder(adapter, cfg=settings.feature_builder)
    return RiskService(feature_builder, cfg=settings.risk)


def create_portfolio_risk_workflow() -> PortfolioRiskWorkflow:
    """Create the default Portfolio-to-Risk workflow for API requests."""

    settings = get_settings()
    adapter = create_market_data_provider_adapter(settings.dataaccess)
    feature_builder = FeatureBuilder(adapter, cfg=settings.feature_builder)
    return PortfolioRiskWorkflow(
        PortfolioService(feature_builder, cfg=settings.portfolio),
        RiskService(feature_builder, cfg=settings.risk),
    )


def create_screening_service() -> ScreeningService:
    """Create the default Screening Score MVP service for API requests."""

    return ScreeningService()


def create_investment_scoring_service() -> InvestmentScoringService:
    """Create the default Investment Score service for API requests."""

    return InvestmentScoringService(weights=get_settings().scoring.weights)


async def build_screening_scores(request: ScreeningScoreRequest) -> list[ScreeningScore]:
    """Build feature snapshots and rank requested symbols through ScreeningService."""

    settings = get_settings()
    adapter = create_market_data_provider_adapter(settings.dataaccess)
    feature_builder = FeatureBuilder(adapter, cfg=settings.feature_builder)
    snapshot = await feature_builder.build_feature_snapshot(request.symbols, request.as_of)
    return create_screening_service().score(snapshot)


async def build_investment_scores(request: InvestmentScoreRequest) -> list[InvestmentScore]:
    """Build screening and forecast signals, then return Investment Score rows."""

    settings = get_settings()
    adapter = create_market_data_provider_adapter(settings.dataaccess)
    feature_builder = FeatureBuilder(adapter, cfg=settings.feature_builder)
    snapshot = await feature_builder.build_feature_snapshot(request.symbols, request.as_of)
    forecast_consensus_by_symbol = await _build_forecast_consensus_by_symbol(
        request.symbols,
        request.as_of,
        request.horizon_days,
    )
    screening_scores = create_screening_service().score(
        snapshot,
        forecast_consensus_by_symbol=forecast_consensus_by_symbol,
    )
    return create_investment_scoring_service().score(
        screening_scores,
        forecast_consensus_by_symbol=forecast_consensus_by_symbol,
        research_score_by_symbol=request.research_scores_by_symbol,
    )


async def build_forecast_evaluations(
    request: ForecastEvaluateRequest,
) -> list[ForecastEvaluation] | list[AdvancedForecastEvaluation]:
    """Fetch OHLCV bars and evaluate the requested deterministic forecast adapter."""

    if request.start > request.end:
        raise ComputationError(
            "Forecast start date must be on or before end date",
            details={"start": request.start.isoformat(), "end": request.end.isoformat()},
        )

    settings = get_settings()
    adapter = create_market_data_provider_adapter(settings.dataaccess)
    bars = await adapter.fetch_ohlcv(
        [request.symbol],
        start=datetime.combine(request.start, time.min, tzinfo=UTC),
        end=datetime.combine(request.end, time.max, tzinfo=UTC),
    )
    if request.adapter != "baseline":
        return [_build_advanced_forecast_evaluation(request, bars)]

    models = _available_forecast_models(len(bars))
    if not bars or not models:
        raise ComputationError(
            "Not enough OHLCV bars for forecast evaluation",
            details={
                "symbol": request.symbol,
                "bar_count": len(bars),
                "minimum_bars": 1,
            },
        )
    return evaluate_models(bars, models=models, horizon_days=request.horizon_days)


def _build_advanced_forecast_evaluation(
    request: ForecastEvaluateRequest,
    bars: list[Bar],
) -> AdvancedForecastEvaluation:
    spec = advanced_forecast_adapter_spec(request.adapter)
    if spec is None:
        raise ComputationError(
            "Unsupported forecast adapter",
            details={
                "adapter": request.adapter,
                "supported_adapters": ["baseline", *advanced_forecast_adapter_keys()],
            },
        )
    supported_horizons = advanced_forecast_supported_horizons(request.adapter)
    if request.horizon_days not in supported_horizons:
        raise ComputationError(
            f"{request.adapter} supports only 5 or 20 day horizons",
            details={
                "adapter": request.adapter,
                "horizon_days": request.horizon_days,
                "supported_horizons": list(supported_horizons),
            },
        )
    try:
        return evaluate_advanced_forecast(
            bars,
            adapter_name=request.adapter,
            horizon_days=request.horizon_days,
        )
    except ValueError as exc:
        raise ComputationError(
            f"Not enough OHLCV bars for {request.adapter} forecast evaluation",
            details={
                "symbol": request.symbol,
                "bar_count": len(bars),
                "adapter": request.adapter,
                "horizon_days": request.horizon_days,
            },
        ) from exc


async def _build_forecast_consensus_by_symbol(
    symbols: list[str],
    as_of: date,
    horizon_days: int,
) -> dict[str, ForecastConsensus]:
    settings = get_settings()
    adapter = create_market_data_provider_adapter(settings.dataaccess)
    consensus_by_symbol: dict[str, ForecastConsensus] = {}
    for symbol in symbols:
        bars = await adapter.fetch_ohlcv(
            [symbol],
            start=datetime(1900, 1, 1, tzinfo=UTC),
            end=datetime.combine(as_of, time.max, tzinfo=UTC),
        )
        models = _available_forecast_models(len(bars))
        if not bars or not models:
            continue
        consensus = summarize_forecast_evaluations(
            evaluate_models(bars, models=models, horizon_days=horizon_days),
            history=bars,
        )
        if consensus is not None:
            consensus_by_symbol[symbol] = consensus
    return consensus_by_symbol


def _available_forecast_models(bar_count: int) -> list[ForecastModel]:
    return available_forecast_models(bar_count)


@app.post(
    "/risk/pre-trade-check",
    response_model=RiskDecision,
    tags=["Risk"],
    summary="Run a pre-trade risk check",
    description=(
        "Evaluates a proposed basket through deterministic MVP rules. "
        "The endpoint uses configured deterministic market data and returns ALLOW, REVIEW, or BLOCK."
    ),
    responses=ERROR_RESPONSES,
)
async def pre_trade_check(request: PreTradeCheckRequest) -> RiskDecision:
    """Evaluate a basket through the deterministic Risk MVP service."""

    return await create_risk_service().pre_trade_check(
        request.basket,
        request.as_of,
        request.account_id,
    )


@app.post(
    "/portfolio/rebalance-check",
    response_model=PortfolioRiskResult,
    tags=["Portfolio"],
    summary="Generate a rebalance proposal and check risk",
    description=(
        "Values current positions, generates no-solver rebalance trades from target "
        "allocations, and sends generated trades through the Risk pre-trade check. "
        "If no trades are generated, risk_decision is null."
    ),
    responses=ERROR_RESPONSES,
)
async def rebalance_check(request: RebalanceCheckRequest) -> PortfolioRiskResult:
    """Generate a rebalance proposal and evaluate its trades through Risk."""

    return await create_portfolio_risk_workflow().propose_and_check(
        account_id=request.account_id,
        positions=request.positions,
        targets=request.targets,
        as_of=request.as_of,
        cash_jpy=request.cash_jpy,
    )


@app.post(
    "/screening/score",
    response_model=list[ScreeningScore],
    tags=["Screening"],
    summary="Rank symbols with explainable screening scores",
    description=(
        "Builds Feature Store Lite snapshots for requested symbols and returns deterministic "
        "screening rankings with sub-score breakdowns and data-quality reasons."
    ),
    responses=ERROR_RESPONSES,
)
async def screening_score(request: ScreeningScoreRequest) -> list[ScreeningScore]:
    """Rank requested symbols using the configured market-data provider."""

    return await build_screening_scores(request)


@app.post(
    "/forecast/evaluate",
    response_model=list[ForecastEvaluation] | list[AdvancedForecastEvaluation],
    tags=["Forecast"],
    summary="Evaluate deterministic forecasts for a symbol",
    description=(
        "Fetches configured OHLCV data for one symbol and evaluates deterministic baseline "
        "models by default. Set adapter=advanced_linear to evaluate the lightweight "
        "5 / 20 day advanced forecast adapter."
    ),
    responses=ERROR_RESPONSES,
)
async def forecast_evaluate(
    request: ForecastEvaluateRequest,
) -> list[ForecastEvaluation] | list[AdvancedForecastEvaluation]:
    """Evaluate the requested deterministic forecast adapter for one symbol."""

    return await build_forecast_evaluations(request)


@app.post(
    "/scoring/investment-score",
    response_model=list[InvestmentScore],
    tags=["Scoring"],
    summary="Score symbols with model-informed investment-support signals",
    description=(
        "Builds deterministic screening and forecast-agreement signals, then returns "
        "Investment Score rows with score breakdowns, warnings, and reasons. "
        "The output is decision support, not buy/sell advice."
    ),
    responses=ERROR_RESPONSES,
)
async def investment_score(request: InvestmentScoreRequest) -> list[InvestmentScore]:
    """Score requested symbols with the Phase 15 Investment Score contract."""

    return await build_investment_scores(request)
