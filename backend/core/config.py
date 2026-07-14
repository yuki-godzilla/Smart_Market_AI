import logging
import os
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator

CONFIG_FILE_ENV = "SMAI_CONFIG_FILE"
PERFORMANCE_PROFILE_ENV = "SMAI_PERFORMANCE_PROFILE"
DEFAULT_PERFORMANCE_PROFILE = "notebook"

LOGGER = logging.getLogger(__name__)


class StrictConfigModel(BaseModel):
    """Base settings model that rejects unknown config keys."""

    model_config = ConfigDict(extra="forbid")


class AppConfig(StrictConfigModel):
    """Top-level application defaults shared by all services."""

    timezone: str = "UTC"
    base_currency: Literal["JPY"] = "JPY"
    log_json: bool = True


class MainApplicationNetworkConfig(StrictConfigModel):
    """Network settings for the user-facing Streamlit application."""

    scheme: Literal["http"] = "http"
    port: int = Field(default=8501, ge=1, le=65535)


class NetworkConfig(StrictConfigModel):
    """Stable names and ports used to reach SMAI from another device."""

    tailscale_hostname: str | None = Field(default=None, min_length=1)
    main_application: MainApplicationNetworkConfig = Field(
        default_factory=MainApplicationNetworkConfig
    )


class CacheConfig(StrictConfigModel):
    """Cache backend and TTL settings for data-heavy services."""

    backend: Literal["memory", "redis"] = "memory"
    ttl_intraday_sec: int = Field(default=60, gt=0)
    ttl_daily_sec: int = Field(default=86400, gt=0)


class TimeoutConfig(StrictConfigModel):
    """Network timeout settings in milliseconds."""

    connect: int = Field(default=1000, gt=0)
    read: int = Field(default=5000, gt=0)


class ExternalFetchPerformanceConfig(StrictConfigModel):
    """External research/source fetch concurrency and timeout settings."""

    max_workers: int = Field(default=4, gt=0)
    per_source_workers: dict[str, int] = Field(default_factory=dict)
    request_timeout_sec: float = Field(default=12.0, gt=0)
    global_timeout_sec: float = Field(default=30.0, gt=0)
    retry_count: int = Field(default=1, ge=0)
    retry_backoff_sec: float = Field(default=1.5, ge=0)
    cache_ttl_minutes: int = Field(default=30, gt=0)
    batch_size: int = Field(default=8, gt=0)
    max_symbols_per_refresh: int = Field(default=12, gt=0)


class ProcessingPerformanceConfig(StrictConfigModel):
    """Local processing concurrency settings for future staged profile use."""

    rag_workers: int = Field(default=2, gt=0)
    forecast_workers: int = Field(default=2, gt=0)
    background_refresh_workers: int = Field(default=2, gt=0)
    llm_workers: int = Field(default=1, gt=0)


class PerformanceProfileConfig(StrictConfigModel):
    """Named performance profile settings."""

    external_fetch: ExternalFetchPerformanceConfig = Field(
        default_factory=ExternalFetchPerformanceConfig
    )
    processing: ProcessingPerformanceConfig = Field(default_factory=ProcessingPerformanceConfig)


class PerformanceProfileSelection(StrictConfigModel):
    """Resolved performance profile and effective settings."""

    requested_profile: str
    selected_profile: str
    available_profiles: list[str]
    fallback_used: bool = False
    fallback_reason: str | None = None
    external_fetch: ExternalFetchPerformanceConfig
    processing: ProcessingPerformanceConfig


class DataAccessConfig(StrictConfigModel):
    """Market-data provider settings."""

    provider: Literal["mock", "csv", "yahoo", "polygon"] = "yahoo"
    csv_data_dir: str = "data/marketdata"
    allow_external_providers: bool = True
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
            "notebook_standard",
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


class AssistantLLMPlannerConfig(StrictConfigModel):
    """Optional HTTP Gateway settings for LLM-suggested assistant plans."""

    enabled: bool = False
    gateway_url: str = Field(default="http://127.0.0.1:8088", min_length=1)
    endpoint_path: str = Field(default="/api/v1/assistant/tool-plan", min_length=1)
    timeout_seconds: float = Field(default=15.0, gt=0)
    max_steps: int = Field(default=5, gt=0, le=6)
    fallback_to_deterministic: bool = True
    show_source_details: bool = False
    model: str | None = Field(default=None, min_length=1)
    execution_mode: Literal["auto", "light", "quality", "off"] = "auto"
    environment_profile: Literal["notebook", "desktop", "server", "offline"] = "notebook"
    preferred_profile: (
        Literal[
            "notebook_dev",
            "notebook_standard",
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
    ) = "assistant_fast"


class AssistantWarmupConfig(StrictConfigModel):
    """Non-blocking Assistant LLM startup and loading-panel settings."""

    enabled: bool = True
    chat_enabled: bool = False
    health_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    retry_count: int = Field(default=2, ge=0, le=3)
    retry_backoff_seconds: float = Field(default=2.0, ge=0, le=5)
    loading_headlines_enabled: bool = True
    loading_headline_max_items: int = Field(default=5, ge=1, le=5)
    loading_headline_cache_max_age_hours: int = Field(default=24, gt=0)


class AssistantConfig(StrictConfigModel):
    """Assistant runtime settings."""

    gateway: AssistantGatewayConfig = Field(default_factory=AssistantGatewayConfig)
    llm_planner: AssistantLLMPlannerConfig = Field(default_factory=AssistantLLMPlannerConfig)
    warmup: AssistantWarmupConfig = Field(default_factory=AssistantWarmupConfig)


class LLMFactorLiveConfig(StrictConfigModel):
    """Optional HTTP Gateway settings for live LLM Factor generation."""

    enabled: bool = False
    base_url: str = Field(default="http://127.0.0.1:8088", min_length=1)
    endpoint_path: str = Field(default="/api/v1/llm-factor/generate", min_length=1)
    timeout_seconds: float = Field(default=90.0, gt=0)
    model: str | None = Field(default=None, min_length=1)
    execution_mode: Literal["auto", "light", "quality", "off"] = "auto"
    environment_profile: Literal["notebook", "desktop", "server", "offline"] = "notebook"
    preferred_profile: (
        Literal[
            "notebook_dev",
            "notebook_standard",
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
    ) = "desktop_analysis"
    prompt_version: str = Field(default="llm_factor_live_mvp.v1", min_length=1)
    response_schema_version: str = Field(default="llm_factor.v1", min_length=1)
    max_evidence_items: int = Field(default=8, gt=0, le=20)
    max_context_text_chars: int = Field(default=280, gt=40, le=1000)
    cache_enabled: bool = True


class LLMFactorConfig(StrictConfigModel):
    """LLM Factor runtime settings."""

    live: LLMFactorLiveConfig = Field(default_factory=LLMFactorLiveConfig)


class CockpitInterpretationConfig(StrictConfigModel):
    """Optional Gateway settings for Cockpit LLM interpretation."""

    enabled: bool = False
    base_url: str = Field(default="http://127.0.0.1:8088", min_length=1)
    context_answer_path: str = Field(default="/api/v1/context-answer", min_length=1)
    timeout_seconds: float = Field(default=45.0, gt=0)
    model: str | None = Field(default=None, min_length=1)
    execution_mode: Literal["auto", "light", "quality", "off"] = "auto"
    environment_profile: Literal["notebook", "desktop", "server", "offline"] = "notebook"
    preferred_profile: (
        Literal[
            "notebook_dev",
            "notebook_standard",
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
    ) = "desktop_fast"
    prompt_version: str = Field(default="cockpit_interpretation_mvp.v1", min_length=1)
    schema_version: str = Field(default="cockpit_interpretation.v1", min_length=1)
    cache_enabled: bool = True
    max_research_evidence: int = Field(default=6, gt=0, le=12)
    max_context_text_chars: int = Field(default=260, gt=40, le=800)


class RadarInterpretationConfig(StrictConfigModel):
    """Optional Gateway settings for evidence-bound Radar interpretation."""

    enabled: bool = False
    base_url: str = Field(default="http://127.0.0.1:8088", min_length=1)
    context_answer_path: str = Field(default="/api/v1/context-answer", min_length=1)
    timeout_seconds: float = Field(default=30.0, gt=0)
    model: str | None = Field(default=None, min_length=1)
    execution_mode: Literal["auto", "light", "quality", "off"] = "auto"
    environment_profile: Literal["notebook", "desktop", "server", "offline"] = "notebook"
    preferred_profile: (
        Literal[
            "notebook_dev",
            "notebook_standard",
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
    ) = "desktop_fast"
    prompt_version: str = Field(default="radar_interpretation_mvp.v1", min_length=1)
    schema_version: str = Field(default="radar_interpretation.v1", min_length=1)
    max_citations: int = Field(default=5, gt=0, le=8)
    max_context_text_chars: int = Field(default=320, gt=40, le=800)


class LLMInterpretationConfig(StrictConfigModel):
    """LLM interpretation runtime settings."""

    cockpit: CockpitInterpretationConfig = Field(default_factory=CockpitInterpretationConfig)
    radar: RadarInterpretationConfig = Field(default_factory=RadarInterpretationConfig)


def _default_performance_profiles() -> dict[str, PerformanceProfileConfig]:
    return {
        "notebook": PerformanceProfileConfig(
            external_fetch=ExternalFetchPerformanceConfig(
                max_workers=4,
                per_source_workers={
                    "yahoo_finance": 2,
                    "news": 3,
                    "tdnet": 2,
                    "edinet": 1,
                    "ir_pages": 2,
                },
                request_timeout_sec=12.0,
                global_timeout_sec=30.0,
                retry_count=1,
                retry_backoff_sec=1.5,
                cache_ttl_minutes=30,
                batch_size=8,
                max_symbols_per_refresh=12,
            ),
            processing=ProcessingPerformanceConfig(
                rag_workers=2,
                forecast_workers=2,
                background_refresh_workers=2,
                llm_workers=1,
            ),
        ),
        "workstation": PerformanceProfileConfig(
            external_fetch=ExternalFetchPerformanceConfig(
                max_workers=10,
                per_source_workers={
                    "yahoo_finance": 4,
                    "news": 6,
                    "tdnet": 3,
                    "edinet": 2,
                    "ir_pages": 4,
                },
                request_timeout_sec=15.0,
                global_timeout_sec=45.0,
                retry_count=2,
                retry_backoff_sec=1.2,
                cache_ttl_minutes=20,
                batch_size=16,
                max_symbols_per_refresh=30,
            ),
            processing=ProcessingPerformanceConfig(
                rag_workers=4,
                forecast_workers=4,
                background_refresh_workers=6,
                llm_workers=1,
            ),
        ),
    }


class Settings(StrictConfigModel):
    """Root settings object for Smart Market AI."""

    app: AppConfig = Field(default_factory=AppConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    dataaccess: DataAccessConfig = Field(default_factory=DataAccessConfig)
    feature_builder: FeatureBuilderConfig = Field(default_factory=FeatureBuilderConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    assistant: AssistantConfig = Field(default_factory=AssistantConfig)
    llm_factor: LLMFactorConfig = Field(default_factory=LLMFactorConfig)
    llm_interpretation: LLMInterpretationConfig = Field(default_factory=LLMInterpretationConfig)
    performance_profiles: dict[str, PerformanceProfileConfig] = Field(
        default_factory=_default_performance_profiles,
        min_length=1,
    )


def get_settings() -> Settings:
    """Return application settings from defaults plus optional YAML config.

    Set SMAI_CONFIG_FILE to a YAML file path to override default values.
    """

    config_file = os.getenv(CONFIG_FILE_ENV)
    if not config_file:
        return Settings()
    return Settings.model_validate(_load_yaml_config(Path(config_file)))


def resolve_performance_profile(settings: Settings | None = None) -> PerformanceProfileSelection:
    """Resolve the active performance profile from settings and environment."""

    resolved_settings = settings or get_settings()
    available_profiles = sorted(resolved_settings.performance_profiles)
    requested_profile = (
        os.getenv(PERFORMANCE_PROFILE_ENV, DEFAULT_PERFORMANCE_PROFILE).strip()
        or DEFAULT_PERFORMANCE_PROFILE
    )
    fallback_used = False
    fallback_reason = None
    if requested_profile in resolved_settings.performance_profiles:
        selected_profile = requested_profile
    else:
        fallback_used = True
        selected_profile = (
            DEFAULT_PERFORMANCE_PROFILE
            if DEFAULT_PERFORMANCE_PROFILE in resolved_settings.performance_profiles
            else available_profiles[0]
        )
        fallback_reason = (
            f"Unknown performance profile '{requested_profile}'. "
            f"Available profiles: {', '.join(available_profiles)}"
        )
        LOGGER.warning("%s Falling back to '%s'.", fallback_reason, selected_profile)

    profile = resolved_settings.performance_profiles[selected_profile]
    LOGGER.info(
        "Performance profile selected: requested=%s selected=%s "
        "external_fetch_max_workers=%s llm_workers=%s available=%s",
        requested_profile,
        selected_profile,
        profile.external_fetch.max_workers,
        profile.processing.llm_workers,
        ",".join(available_profiles),
    )
    return PerformanceProfileSelection(
        requested_profile=requested_profile,
        selected_profile=selected_profile,
        available_profiles=available_profiles,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        external_fetch=profile.external_fetch,
        processing=profile.processing,
    )


def _load_yaml_config(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("Settings YAML must contain a mapping at the document root")
    return data
