from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Currency = Literal["JPY", "USD"]
Side = Literal["BUY", "SELL"]
OrderType = Literal["MKT", "LMT", "STP", "IOC"]
Interval = Literal["1m", "5m", "15m", "1h", "1d"]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Symbol(StrictBaseModel):
    raw: str = Field(min_length=1, examples=["7203.T", "AAPL"])
    exchange: str = Field(min_length=1, examples=["TSE", "NASDAQ"])
    code: str = Field(min_length=1, examples=["7203", "AAPL"])
    currency: Currency


class FxRate(StrictBaseModel):
    pair: Literal["USDJPY"]
    rate: Decimal = Field(gt=0)
    ts: datetime
    source: str = "mock"


class TradeIntent(StrictBaseModel):
    symbol: str = Field(min_length=1)
    side: Side
    qty: Decimal = Field(gt=0)
    price_hint: Decimal | None = Field(default=None, gt=0)
    currency: Currency


class Position(StrictBaseModel):
    symbol: str = Field(min_length=1)
    qty: Decimal = Field(ge=0)
    avg_price: Decimal = Field(ge=0)
    currency: Currency


class Bar(StrictBaseModel):
    symbol: Symbol
    ts: datetime
    open: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)
    low: Decimal = Field(ge=0)
    close: Decimal = Field(ge=0)
    volume: Decimal = Field(ge=0)
    interval: Interval
    provider: str


class Quote(StrictBaseModel):
    symbol: Symbol
    bid: Decimal | None = Field(default=None, ge=0)
    ask: Decimal | None = Field(default=None, ge=0)
    last: Decimal | None = Field(default=None, ge=0)
    ts: datetime


class DailySnapshot(StrictBaseModel):
    symbol: str = Field(min_length=1)
    as_of: date
    last: Decimal | None = Field(default=None, ge=0)
    close_1d: Decimal | None = Field(default=None, ge=0)
    adv_20d: Decimal | None = Field(default=None, ge=0)
    vol_20d: Decimal | None = Field(default=None, ge=0)
    dividend_yield: Decimal | None = Field(default=None, ge=0)
    market_cap_jpy: Decimal | None = Field(default=None, ge=0)
    missing: dict[str, bool] = Field(default_factory=dict)
