from __future__ import annotations

import os
from pathlib import Path

RUNTIME_DIR_ENV = "SMAI_RUNTIME_DIR"
CACHE_DIR_ENV = "SMAI_CACHE_DIR"
OUTPUT_DIR_ENV = "SMAI_OUTPUT_DIR"
LOG_DIR_ENV = "SMAI_LOG_DIR"
USER_CONFIG_DIR_ENV = "SMAI_USER_CONFIG_DIR"


def runtime_path_from_env(env_name: str, fallback: str | Path) -> Path:
    """Return a runtime path from an environment variable, or a local fallback."""

    raw_value = os.environ.get(env_name, "").strip()
    if raw_value:
        return Path(raw_value)
    return Path(fallback)
