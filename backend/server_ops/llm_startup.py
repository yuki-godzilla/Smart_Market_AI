"""Best-effort local LLM runtime startup for the SMAI service launcher.

This module deliberately lives beside the server launcher rather than in a
Streamlit view.  A Streamlit rerun must never own, restart, or block on the
Gateway/Ollama processes.  All work here is local-only and best-effort: a
failure is recorded in the server log and SMAI continues with its deterministic
features and existing Gateway fallbacks.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlparse

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATEWAY_ROOT = PROJECT_ROOT / "smai-ai-gateway"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:8088"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
STARTUP_WAIT_SECONDS = 15.0
STARTUP_PROBE_INTERVAL_SECONDS = 0.25
WARMUP_TIMEOUT_SECONDS = 120.0

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalLlmStartupConfig:
    """Local process settings derived from explicit, operator-owned environment values."""

    enabled: bool
    warmup_enabled: bool
    gateway_url: str
    ollama_url: str
    model: str | None
    profile: str

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> "LocalLlmStartupConfig":
        values = os.environ if environ is None else environ
        return cls(
            enabled=_env_enabled(values.get("SMAI_ASSISTANT_GATEWAY_AUTOSTART"), default=True),
            warmup_enabled=_env_enabled(values.get("SMAI_ASSISTANT_GATEWAY_WARMUP"), default=True),
            gateway_url=str(values.get("SMAI_ASSISTANT_GATEWAY_URL") or DEFAULT_GATEWAY_URL).rstrip(
                "/"
            ),
            ollama_url=str(values.get("SMAI_OLLAMA_BASE_URL") or DEFAULT_OLLAMA_URL).rstrip("/"),
            model=(str(values.get("SMAI_OLLAMA_MODEL") or "").strip() or None),
            profile=str(values.get("SMAI_LLM_PROFILE") or "notebook_dev").strip() or "notebook_dev",
        )


@dataclass(frozen=True)
class LocalLlmStartupResult:
    """Non-sensitive outcome retained in launcher logs for operations diagnosis."""

    ollama_ready: bool
    gateway_ready: bool
    model_warmup_requested: bool
    ollama_started: bool
    gateway_started: bool


def _env_enabled(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_local_http_url(url: str) -> bool:
    """Only launch processes for a loopback HTTP endpoint."""

    parsed = urlparse(url)
    return parsed.scheme == "http" and (parsed.hostname or "") in {
        "127.0.0.1",
        "localhost",
    }


def ollama_tags_url(config: LocalLlmStartupConfig) -> str:
    return f"{config.ollama_url}/api/tags"


def gateway_health_url(config: LocalLlmStartupConfig) -> str:
    return f"{config.gateway_url}/health"


def gateway_command(config: LocalLlmStartupConfig) -> list[str]:
    parsed = urlparse(config.gateway_url)
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        parsed.hostname or "127.0.0.1",
        "--port",
        str(parsed.port or 8088),
    ]


def ollama_command() -> list[str]:
    return ["ollama", "serve"]


def _probe_ok(url: str, *, timeout_seconds: float = 1.0) -> bool:
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            return client.get(url).status_code == 200
    except httpx.HTTPError:
        return False


def _wait_until_ready(
    url: str,
    *,
    probe: Callable[[str], bool] = _probe_ok,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> bool:
    deadline = monotonic() + STARTUP_WAIT_SECONDS
    while monotonic() < deadline:
        if probe(url):
            return True
        sleep(STARTUP_PROBE_INTERVAL_SECONDS)
    return probe(url)


def _creationflags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
        subprocess, "CREATE_NO_WINDOW", 0
    )


def _launch(command: list[str], *, cwd: Path | None, environ: Mapping[str, str]) -> bool:
    try:
        subprocess.Popen(  # noqa: S603
            command,
            cwd=cwd,
            env=dict(environ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=os.name != "nt",
            creationflags=_creationflags(),
        )
    except OSError as exc:
        LOGGER.warning("Local LLM startup command could not be launched: %s", exc)
        return False
    return True


def _request_model_warmup(config: LocalLlmStartupConfig) -> bool:
    """Load the selected Gateway route once without sending SMAI data to the model."""

    payload: dict[str, str] = {
        "message": "OK",
        "system_prompt": "Reply with only OK.",
        "profile": config.profile,
    }
    if config.model:
        payload["model"] = config.model
    try:
        with httpx.Client(timeout=WARMUP_TIMEOUT_SECONDS) as client:
            response = client.post(f"{config.gateway_url}/api/v1/chat", json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        LOGGER.info("Local LLM model warmup did not complete: %s", type(exc).__name__)
        return False
    return True


def run_local_llm_startup(
    config: LocalLlmStartupConfig,
    *,
    environ: Mapping[str, str] | None = None,
    probe: Callable[[str], bool] = _probe_ok,
    wait_until_ready: Callable[[str], bool] = _wait_until_ready,
    launch: Callable[[list[str], Path | None, Mapping[str, str]], bool] | None = None,
    warm_model: Callable[[LocalLlmStartupConfig], bool] = _request_model_warmup,
) -> LocalLlmStartupResult:
    """Start local Ollama/Gateway when needed, then warm the configured model.

    This routine is called only from a daemon thread.  It never raises to the
    SMAI launcher and it does not manage remote URLs.
    """

    if not config.enabled:
        return LocalLlmStartupResult(False, False, False, False, False)

    child_environ = dict(os.environ if environ is None else environ)
    launch_process = launch or (
        lambda command, cwd, environment: _launch(command, cwd=cwd, environ=environment)
    )
    local_ollama = is_local_http_url(config.ollama_url)
    local_gateway = is_local_http_url(config.gateway_url)

    ollama_ready = probe(ollama_tags_url(config)) if local_ollama else False
    ollama_started = False
    if local_ollama and not ollama_ready:
        ollama_started = launch_process(ollama_command(), None, child_environ)
        if ollama_started:
            ollama_ready = wait_until_ready(ollama_tags_url(config))

    gateway_ready = probe(gateway_health_url(config)) if local_gateway else False
    gateway_started = False
    if local_gateway and not gateway_ready and GATEWAY_ROOT.is_dir():
        gateway_started = launch_process(gateway_command(config), GATEWAY_ROOT, child_environ)
        if gateway_started:
            gateway_ready = wait_until_ready(gateway_health_url(config))

    model_warmup_requested = bool(
        config.warmup_enabled and local_ollama and local_gateway and ollama_ready and gateway_ready
    )
    if model_warmup_requested:
        warm_model(config)

    return LocalLlmStartupResult(
        ollama_ready=ollama_ready,
        gateway_ready=gateway_ready,
        model_warmup_requested=model_warmup_requested,
        ollama_started=ollama_started,
        gateway_started=gateway_started,
    )


class LocalLlmStartupManager:
    """One background startup cycle per persistent SMAI launcher process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = False

    def start(self, config: LocalLlmStartupConfig | None = None) -> bool:
        resolved = config or LocalLlmStartupConfig.from_environ()
        if not resolved.enabled:
            return False
        with self._lock:
            if self._started:
                return False
            self._started = True
        threading.Thread(
            target=self._run,
            args=(resolved,),
            name="smai-local-llm-startup",
            daemon=True,
        ).start()
        return True

    @staticmethod
    def _run(config: LocalLlmStartupConfig) -> None:
        try:
            result = run_local_llm_startup(config)
        except Exception:  # pragma: no cover - final containment for service startup
            LOGGER.exception("Local LLM startup failed unexpectedly; SMAI remains available.")
            return
        LOGGER.info(
            "Local LLM startup finished: ollama_ready=%s gateway_ready=%s warmup=%s",
            result.ollama_ready,
            result.gateway_ready,
            result.model_warmup_requested,
        )


_DEFAULT_MANAGER = LocalLlmStartupManager()


def start_local_llm_startup_in_background() -> bool:
    """Request one best-effort startup cycle without delaying SMAI availability."""

    return _DEFAULT_MANAGER.start()
