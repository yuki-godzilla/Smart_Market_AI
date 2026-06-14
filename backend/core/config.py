import os
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator

CONFIG_FILE_ENV = "SMAI_CONFIG_FILE"


class StrictConfigModel(BaseModel):
    """Base settings model that rejects unknown config keys."""

    model_config = ConfigDict(extra="forbid")


class AppConfig(StrictConfigModel):
    """Top-level application defaults shared by all services."""

    timezone: str = "UTC"
    base_currency: Literal["JPY"] = "JPY"
    log_json: bool = True


class CacheConfig(StrictConfigModel):
    """Cache backend and TTL settings for data-heavy services."""

    backend: Literal["memory", "redis"] = "memory"
    ttl_intraday_sec: int = Field(default=60, gt=0)
    ttl_daily_sec: int = Field(default=86400, gt=0)


class TimeoutConfig(StrictConfigModel):
    """Network timeout settings in milliseconds."""

    connect: int = Field(default=1000, gt=0)
    read: int = Field(default=5000, gt=0)


class DataAccessConfig(StrictConfigModel):
    """Market-data provider settings."""

    provider: Literal["mock", "csv", "yahoo", "polygon"] = "mock"
    csv_data_dir: str = "data/marketdata"
    allow_external_providers: bool = False
    cache: CacheConfig = Field(default_factory=CacheConfig)
    timeouts_ms: TimeoutConfig = Field(default_factory=TimeoutConfig)


class FeatureBuilderConfig(StrictConfigModel):
    """Feature calculation windows and method choices."""

    adv_window: int = Field(default=20, gt=1)
    vol_window: int = Field(default=20, gt=1)
    vol_method: Literal["close2close", "parkinson"] = "close2close"


class RiskThresholdsConfig(StrictConfigModel):
    """Risk-rule thresholds used by the pre-trade MVP."""

    max_notional_per_symbol: int = Field(default=3_000_000, gt=0)
    max_notional_per_basket: int = Field(default=10_000_000, gt=0)
    max_concentration: float = Field(default=0.25, gt=0, le=1)
    min_adv: int = Field(default=50_000_000, gt=0)
    min_dividend_yield: float = Field(default=0.03, ge=0)
    max_volatility: float = Field(default=0.6, gt=0)


class RiskConfig(StrictConfigModel):
    """Risk-service configuration."""

    thresholds: RiskThresholdsConfig = Field(default_factory=RiskThresholdsConfig)


class PortfolioSolverConfig(StrictConfigModel):
    """Portfolio solver selection and numerical tolerance."""

    backend: Literal["none", "pulp", "ortools"] = "none"
    tolerance: float = Field(default=1e-6, gt=0)


class PortfolioConfig(StrictConfigModel):
    """Portfolio-service configuration."""

    solver: PortfolioSolverConfig = Field(default_factory=PortfolioSolverConfig)


class ScoringWeightsConfig(StrictConfigModel):
    """Weights for the deterministic Investment Score."""

    screening: float = Field(default=0.50, ge=0, le=1)
    forecast_agreement: float = Field(default=0.20, ge=0, le=1)
    data_quality: float = Field(default=0.20, ge=0, le=1)
    research: float = Field(default=0.0, ge=0, le=1)
    risk_signal: float = Field(default=0.10, ge=0, le=1)

    @model_validator(mode="after")
    def validate_total(self) -> "ScoringWeightsConfig":
        total = (
            self.screening
            + self.forecast_agreement
            + self.data_quality
            + self.research
            + self.risk_signal
        )
        if abs(total - 1.0) > 0.000001:
            raise ValueError("Scoring weights must sum to 1.0")
        return self


class ScoringConfig(StrictConfigModel):
    """Investment scoring configuration."""

    weights: ScoringWeightsConfig = Field(default_factory=ScoringWeightsConfig)


class ExecutionWebhookConfig(StrictConfigModel):
    """Webhook settings for future broker execution callbacks."""

    secret: str = ""


class ExecutionIdempotencyConfig(StrictConfigModel):
    """Idempotency storage settings for future execution workflows."""

    storage: Literal["memory", "redis", "db"] = "memory"
    ttl_hours: int = Field(default=24, gt=0)


class ExecutionConfig(StrictConfigModel):
    """Execution-service configuration."""

    webhook: ExecutionWebhookConfig = Field(default_factory=ExecutionWebhookConfig)
    idempotency: ExecutionIdempotencyConfig = Field(default_factory=ExecutionIdempotencyConfig)


class AssistantGatewayConfig(StrictConfigModel):
    """Optional HTTP Gateway settings for LLM-backed assistant answers."""

    enabled: bool = False
    base_url: str = Field(default="http://127.0.0.1:8088", min_length=1)
    context_answer_path: str = Field(default="/api/v1/context-answer", min_length=1)
    timeout_seconds: float = Field(default=90.0, gt=0)
    model: str | None = Field(default=None, min_length=1)
    execution_mode: Literal["auto", "light", "quality", "off"] = "auto"
    environment_profile: Literal["notebook", "desktop", "server", "offline"] = "notebook"
    preferred_profile: (
        Literal[
            "notebook_dev",
            "desktop_fast",
            "desktop_analysis",
            "desktop_heavy",
            "assistant_fast",
            "assistant_standard",
            "assistant_quality",
            "report_quality",
            "fallback",
        ]
        | None
    ) = None


class AssistantConfig(StrictConfigModel):
    """Assistant runtime settings."""

    gateway: AssistantGatewayConfig = Field(default_factory=AssistantGatewayConfig)


class Settings(StrictConfigModel):
    """Root settings object for Smart Market AI."""

    app: AppConfig = Field(default_factory=AppConfig)
    dataaccess: DataAccessConfig = Field(default_factory=DataAccessConfig)
    feature_builder: FeatureBuilderConfig = Field(default_factory=FeatureBuilderConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    assistant: AssistantConfig = Field(default_factory=AssistantConfig)


def get_settings() -> Settings:
    """Return application settings from defaults plus optional YAML config.

    Set SMAI_CONFIG_FILE to a YAML file path to override default values.
    """

    config_file = os.getenv(CONFIG_FILE_ENV)
    if not config_file:
        return Settings()
    return Settings.model_validate(_load_yaml_config(Path(config_file)))


def _load_yaml_config(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("Settings YAML must contain a mapping at the document root")
    return data
