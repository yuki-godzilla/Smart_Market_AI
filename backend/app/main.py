from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ConfigDict, Field

from backend.core.config import get_settings
from backend.core.data_contracts import Position, StrictBaseModel, TradeIntent
from backend.core.errors import AppError
from backend.marketdata import DataAccess, FeatureBuilder, create_market_data_provider_adapter
from backend.portfolio import (
    PortfolioRiskResult,
    PortfolioRiskWorkflow,
    PortfolioService,
    TargetAllocation,
)
from backend.risk import RiskDecision, RiskService
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
    data_access = DataAccess(cfg=settings.dataaccess)
    feature_builder = FeatureBuilder(data_access, cfg=settings.feature_builder)
    return RiskService(feature_builder, cfg=settings.risk)


def create_portfolio_risk_workflow() -> PortfolioRiskWorkflow:
    """Create the default Portfolio-to-Risk workflow for API requests."""

    settings = get_settings()
    data_access = DataAccess(cfg=settings.dataaccess)
    feature_builder = FeatureBuilder(data_access, cfg=settings.feature_builder)
    return PortfolioRiskWorkflow(
        PortfolioService(feature_builder, cfg=settings.portfolio),
        RiskService(feature_builder, cfg=settings.risk),
    )


def create_screening_service() -> ScreeningService:
    """Create the default Screening Score MVP service for API requests."""

    return ScreeningService()


async def build_screening_scores(request: ScreeningScoreRequest) -> list[ScreeningScore]:
    """Build feature snapshots and rank requested symbols through ScreeningService."""

    settings = get_settings()
    adapter = create_market_data_provider_adapter(settings.dataaccess)
    feature_builder = FeatureBuilder(adapter, cfg=settings.feature_builder)
    snapshot = await feature_builder.build_feature_snapshot(request.symbols, request.as_of)
    return create_screening_service().score(snapshot)


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
