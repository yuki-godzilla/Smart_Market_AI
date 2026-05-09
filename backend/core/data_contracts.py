from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Currency = Literal["JPY", "USD"]
Side = Literal["BUY", "SELL"]
OrderType = Literal["MKT", "LMT", "STP", "IOC"]
Interval = Literal["1m", "5m", "15m", "1h", "1d"]


class StrictBaseModel(BaseModel):
    """Base model for application data contracts that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class Symbol(StrictBaseModel):
    """Normalized market symbol used across data access, risk, and portfolio logic."""

    raw: str = Field(min_length=1, examples=["7203.T", "AAPL"])
    exchange: str = Field(min_length=1, examples=["TSE", "NASDAQ"])
    code: str = Field(min_length=1, examples=["7203", "AAPL"])
    currency: Currency


class FxRate(StrictBaseModel):
    """Foreign-exchange rate normalized to UTC and a named source."""

    pair: Literal["USDJPY"]
    rate: Decimal = Field(gt=0)
    ts: datetime
    source: str = "mock"


class TradeIntent(StrictBaseModel):
    """Order-like intent produced before risk checks and broker execution."""

    symbol: str = Field(min_length=1)
    side: Side
    qty: Decimal = Field(gt=0)
    price_hint: Decimal | None = Field(default=None, gt=0)
    currency: Currency


class Position(StrictBaseModel):
    """Current holding for one symbol in an investment account."""

    symbol: str = Field(min_length=1)
    qty: Decimal = Field(ge=0)
    avg_price: Decimal = Field(ge=0)
    currency: Currency


class Bar(StrictBaseModel):
    """OHLCV price bar returned by market-data providers."""

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
    """Point-in-time market quote for a normalized symbol."""

    symbol: Symbol
    bid: Decimal | None = Field(default=None, ge=0)
    ask: Decimal | None = Field(default=None, ge=0)
    last: Decimal | None = Field(default=None, ge=0)
    ts: datetime


class DailySnapshot(StrictBaseModel):
    """Feature row consumed by risk, portfolio, and screening services."""

    symbol: str = Field(min_length=1)
    as_of: date
    last: Decimal | None = Field(default=None, ge=0)
    close_1d: Decimal | None = Field(default=None, ge=0)
    adv_20d: Decimal | None = Field(default=None, ge=0)
    vol_20d: Decimal | None = Field(default=None, ge=0)
    dividend_yield: Decimal | None = Field(default=None, ge=0)
    market_cap_jpy: Decimal | None = Field(default=None, ge=0)
    missing: dict[str, bool] = Field(default_factory=dict)


class FeatureSnapshot(StrictBaseModel):
    """Reusable feature snapshot with provider and version metadata."""

    as_of: date
    provider: str = Field(min_length=1)
    feature_version: str = Field(default="feature-snapshot-v1", min_length=1)
    rows: list[DailySnapshot]
    missing_summary: dict[str, int] = Field(default_factory=dict)
