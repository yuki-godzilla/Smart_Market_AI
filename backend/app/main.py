from datetime import date

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from backend.core.config import get_settings
from backend.core.data_contracts import StrictBaseModel, TradeIntent
from backend.core.errors import AppError
from backend.marketdata import DataAccess, FeatureBuilder
from backend.risk import RiskDecision, RiskService

app = FastAPI(title="Smart Market AI API")


class PreTradeCheckRequest(StrictBaseModel):
    """Request body for the Risk MVP pre-trade check endpoint."""

    account_id: str = Field(min_length=1)
    as_of: date
    basket: list[TradeIntent] = Field(min_length=1)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Return domain errors with their configured HTTP status."""

    return JSONResponse(status_code=int(exc.http_status), content=exc.to_dict())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/risk/pre-trade-check", response_model=RiskDecision)
async def pre_trade_check(request: PreTradeCheckRequest) -> RiskDecision:
    """Evaluate a basket through the deterministic Risk MVP service."""

    settings = get_settings()
    data_access = DataAccess(cfg=settings.dataaccess)
    feature_builder = FeatureBuilder(data_access, cfg=settings.feature_builder)
    service = RiskService(feature_builder, cfg=settings.risk)

    return await service.pre_trade_check(
        request.basket,
        request.as_of,
        request.account_id,
    )
