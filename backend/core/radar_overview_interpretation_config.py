from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RadarOverviewInterpretationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    prompt_version: str = Field(default="radar_overview_interpretation_mvp.v1", min_length=1)
    schema_version: str = Field(default="radar_overview_interpretation.v1", min_length=1)
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=21600, gt=0, le=86400)
    max_themes: int = Field(default=3, gt=0, le=3)
    max_sector_groups: int = Field(default=4, gt=0, le=4)
    max_deep_dive_candidates: int = Field(default=2, gt=0, le=2)
    max_context_text_chars: int = Field(default=240, gt=40, le=600)
