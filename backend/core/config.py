from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AppConfig(StrictConfigModel):
    timezone: str = "UTC"
    base_currency: Literal["JPY"] = "JPY"
    log_json: bool = True


class CacheConfig(StrictConfigModel):
    backend: Literal["memory", "redis"] = "memory"
    ttl_intraday_sec: int = Field(default=60, gt=0)
    ttl_daily_sec: int = Field(default=86400, gt=0)


class TimeoutConfig(StrictConfigModel):
    connect: int = Field(default=1000, gt=0)
    read: int = Field(default=5000, gt=0)


class DataAccessConfig(StrictConfigModel):
    provider: Literal["mock", "csv", "yahoo", "polygon"] = "mock"
    cache: CacheConfig = Field(default_factory=CacheConfig)
    timeouts_ms: TimeoutConfig = Field(default_factory=TimeoutConfig)


class FeatureBuilderConfig(StrictConfigModel):
    adv_window: int = Field(default=20, gt=1)
    vol_window: int = Field(default=20, gt=1)
    vol_method: Literal["close2close", "parkinson"] = "close2close"


class RiskThresholdsConfig(StrictConfigModel):
    max_notional_per_symbol: int = Field(default=3_000_000, gt=0)
    max_notional_per_basket: int = Field(default=10_000_000, gt=0)
    max_concentration: float = Field(default=0.25, gt=0, le=1)
    min_dividend_yield: float = Field(default=0.03, ge=0)


class RiskConfig(StrictConfigModel):
    thresholds: RiskThresholdsConfig = Field(default_factory=RiskThresholdsConfig)


class PortfolioSolverConfig(StrictConfigModel):
    backend: Literal["none", "pulp", "ortools"] = "none"
    tolerance: float = Field(default=1e-6, gt=0)


class PortfolioConfig(StrictConfigModel):
    solver: PortfolioSolverConfig = Field(default_factory=PortfolioSolverConfig)


class ExecutionWebhookConfig(StrictConfigModel):
    secret: str = ""


class ExecutionIdempotencyConfig(StrictConfigModel):
    storage: Literal["memory", "redis", "db"] = "memory"
    ttl_hours: int = Field(default=24, gt=0)


class ExecutionConfig(StrictConfigModel):
    webhook: ExecutionWebhookConfig = Field(default_factory=ExecutionWebhookConfig)
    idempotency: ExecutionIdempotencyConfig = Field(default_factory=ExecutionIdempotencyConfig)


class Settings(StrictConfigModel):
    app: AppConfig = Field(default_factory=AppConfig)
    dataaccess: DataAccessConfig = Field(default_factory=DataAccessConfig)
    feature_builder: FeatureBuilderConfig = Field(default_factory=FeatureBuilderConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)


def get_settings() -> Settings:
    return Settings()
