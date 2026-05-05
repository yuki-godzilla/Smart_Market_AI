from datetime import date
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from backend.core.config import get_settings
from backend.core.data_contracts import Position, StrictBaseModel, TradeIntent
from backend.core.errors import AppError
from backend.marketdata import DataAccess, FeatureBuilder
from backend.portfolio import (
    PortfolioRiskResult,
    PortfolioRiskWorkflow,
    PortfolioService,
    TargetAllocation,
)
from backend.risk import RiskDecision, RiskService

app = FastAPI(title="Smart Market AI API")


class PreTradeCheckRequest(StrictBaseModel):
    """Request body for the Risk MVP pre-trade check endpoint."""

    account_id: str = Field(min_length=1)
    as_of: date
    basket: list[TradeIntent] = Field(min_length=1)


class RebalanceCheckRequest(StrictBaseModel):
    """Request body for the Portfolio-to-Risk rebalance check endpoint."""

    account_id: str = Field(min_length=1)
    as_of: date
    positions: list[Position] = Field(default_factory=list)
    targets: list[TargetAllocation] = Field(default_factory=list)
    cash_jpy: Decimal = Field(default=Decimal("0"), ge=0)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Return domain errors with their configured HTTP status."""

    return JSONResponse(status_code=int(exc.http_status), content=exc.to_dict())


@app.get("/health")
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


@app.post("/risk/pre-trade-check", response_model=RiskDecision)
async def pre_trade_check(request: PreTradeCheckRequest) -> RiskDecision:
    """Evaluate a basket through the deterministic Risk MVP service."""

    return await create_risk_service().pre_trade_check(
        request.basket,
        request.as_of,
        request.account_id,
    )


@app.post("/portfolio/rebalance-check", response_model=PortfolioRiskResult)
async def rebalance_check(request: RebalanceCheckRequest) -> PortfolioRiskResult:
    """Generate a rebalance proposal and evaluate its trades through Risk."""

    return await create_portfolio_risk_workflow().propose_and_check(
        account_id=request.account_id,
        positions=request.positions,
        targets=request.targets,
        as_of=request.as_of,
        cash_jpy=request.cash_jpy,
    )
