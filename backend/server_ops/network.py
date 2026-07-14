"""Resolve the SMAI Main Application URLs without exposing network addresses.

The Streamlit listener may bind to every local interface, but users should use
the one MagicDNS hostname configured for this server.  This module keeps that
public URL separate from the localhost URL used by server-side health checks
and browser launch operations.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from backend.core.config import Settings, get_settings

TAILSCALE_HOSTNAME_ENV = "SMAI_TAILSCALE_HOSTNAME"
MAIN_APPLICATION_PORT_ENV = "SMAI_MAIN_PORT"
MAIN_APPLICATION_SCHEME_ENV = "SMAI_MAIN_SCHEME"
DEFAULT_MAIN_APPLICATION_PORT = 8501
DEFAULT_MAIN_APPLICATION_SCHEME = "http"
_HOSTNAME_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class MainApplicationNetworkError(ValueError):
    """Raised when SMAI cannot build a safe user-facing application URL."""


@dataclass(frozen=True, slots=True)
class MainApplicationSettings:
    scheme: str
    port: int
    configured_tailscale_hostname: str | None


@dataclass(frozen=True, slots=True)
class MainApplicationURLs:
    """User-facing MagicDNS and server-local SMAI URLs."""

    hostname: str
    hostname_source: str
    scheme: str
    port: int
    normal_access_url: str
    local_access_url: str


def build_main_application_url(
    hostname: str,
    port: int,
    scheme: str = DEFAULT_MAIN_APPLICATION_SCHEME,
) -> str:
    """Build a safe MagicDNS URL for people using SMAI from another device."""

    normalized_hostname = _validate_hostname(hostname)
    normalized_port = _validate_port(port)
    normalized_scheme = _validate_scheme(scheme)
    return f"{normalized_scheme}://{normalized_hostname}:{normalized_port}"


def build_local_main_application_url(
    port: int,
    scheme: str = DEFAULT_MAIN_APPLICATION_SCHEME,
) -> str:
    """Build the server-local URL, deliberately independent of MagicDNS."""

    normalized_port = _validate_port(port)
    normalized_scheme = _validate_scheme(scheme)
    return f"{normalized_scheme}://localhost:{normalized_port}"


def main_application_settings(
    *,
    settings: Settings | None = None,
    environ: Mapping[str, str] | None = None,
) -> MainApplicationSettings:
    """Return common URL settings, allowing explicit environment overrides."""

    resolved_settings = settings or get_settings()
    values = os.environ if environ is None else environ
    application = resolved_settings.network.main_application
    scheme = _validate_scheme(values.get(MAIN_APPLICATION_SCHEME_ENV, application.scheme))
    port = _validate_port(values.get(MAIN_APPLICATION_PORT_ENV, application.port))
    configured_hostname = values.get(TAILSCALE_HOSTNAME_ENV)
    if configured_hostname is None:
        configured_hostname = resolved_settings.network.tailscale_hostname
    return MainApplicationSettings(
        scheme=scheme,
        port=port,
        configured_tailscale_hostname=(
            str(configured_hostname).strip() if configured_hostname else None
        ),
    )


def resolve_main_application_urls(
    *,
    settings: Settings | None = None,
    environ: Mapping[str, str] | None = None,
    tailscale_hostname_discoverer: Callable[[], str | None] | None = None,
    os_hostname_discoverer: Callable[[], str] | None = None,
) -> MainApplicationURLs:
    """Resolve the normal MagicDNS URL with deterministic, safe fallbacks.

    Explicit SMAI configuration is preferred, followed by a local Tailscale
    query and finally the OS hostname.  Tailscale discovery is best-effort so
    an unavailable CLI or service never prevents SMAI from starting.
    """

    resolved = main_application_settings(settings=settings, environ=environ)
    if resolved.configured_tailscale_hostname:
        return _urls_for_hostname(
            resolved.configured_tailscale_hostname,
            source="configured",
            settings=resolved,
        )

    for source, candidate in (
        (
            "tailscale_cli",
            (tailscale_hostname_discoverer or discover_tailscale_hostname)(),
        ),
        ("os_hostname", (os_hostname_discoverer or socket.gethostname)()),
    ):
        if not candidate:
            continue
        try:
            return _urls_for_hostname(candidate, source=source, settings=resolved)
        except MainApplicationNetworkError:
            continue
    raise MainApplicationNetworkError(
        "SMAIのMagicDNSホスト名を取得できませんでした。"
        f"{TAILSCALE_HOSTNAME_ENV} または network.tailscale_hostname を設定してください。"
    )


def _urls_for_hostname(
    hostname: str,
    *,
    source: str,
    settings: MainApplicationSettings,
) -> MainApplicationURLs:
    normalized_hostname = _validate_hostname(hostname)
    return MainApplicationURLs(
        hostname=normalized_hostname,
        hostname_source=source,
        scheme=settings.scheme,
        port=settings.port,
        normal_access_url=build_main_application_url(
            normalized_hostname,
            settings.port,
            settings.scheme,
        ),
        local_access_url=build_local_main_application_url(
            settings.port,
            settings.scheme,
        ),
    )


def discover_tailscale_hostname() -> str | None:
    """Return this device's Tailscale hostname without requiring the CLI."""

    executable = shutil.which("tailscale")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    self_payload = payload.get("Self")
    if not isinstance(self_payload, dict):
        return None
    hostname = self_payload.get("HostName")
    if isinstance(hostname, str) and hostname.strip():
        return hostname
    dns_name = self_payload.get("DNSName")
    if isinstance(dns_name, str) and dns_name.strip():
        return dns_name.rstrip(".").split(".", 1)[0]
    return None


def _validate_scheme(value: object) -> str:
    scheme = str(value).strip().lower()
    if scheme != DEFAULT_MAIN_APPLICATION_SCHEME:
        raise MainApplicationNetworkError("SMAI Main Applicationのschemeはhttpだけを使用できます。")
    return scheme


def _validate_port(value: object) -> int:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise MainApplicationNetworkError(
            "SMAI Main Applicationのportは1〜65535の整数で指定してください。"
        ) from exc
    if not 1 <= port <= 65535:
        raise MainApplicationNetworkError(
            "SMAI Main Applicationのportは1〜65535の整数で指定してください。"
        )
    return port


def _validate_hostname(value: object) -> str:
    hostname = str(value).strip().rstrip(".").lower()
    if not hostname:
        raise MainApplicationNetworkError("MagicDNSホスト名が空です。")
    if hostname in {"localhost", "0.0.0.0"}:
        raise MainApplicationNetworkError(
            "MagicDNSホスト名にlocalhostまたは0.0.0.0は使用できません。"
        )
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise MainApplicationNetworkError("MagicDNSホスト名にIPアドレスは使用できません。")
    labels = hostname.split(".")
    if len(hostname) > 253 or any(not _HOSTNAME_LABEL_PATTERN.fullmatch(label) for label in labels):
        raise MainApplicationNetworkError("MagicDNSホスト名は有効なDNS名で指定してください。")
    return hostname


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve SMAI Main Application URLs.")
    parser.add_argument(
        "--emit-batch",
        action="store_true",
        help="Emit Windows batch SET commands for the resolved URLs.",
    )
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="Emit a JSON document for PowerShell server-operation scripts.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        urls = resolve_main_application_urls()
    except MainApplicationNetworkError as exc:
        print(f"[SMAI] {exc}", file=sys.stderr)
        return 2
    if args.emit_batch:
        print(f'set "SMAI_MAIN_PORT={urls.port}"')
        print(f'set "SMAI_TAILSCALE_HOSTNAME={urls.hostname}"')
        print(f'set "SMAI_MAIN_APPLICATION_URL={urls.normal_access_url}"')
        print(f'set "SMAI_LOCAL_APPLICATION_URL={urls.local_access_url}"')
        return 0
    if args.emit_json:
        print(
            json.dumps(
                {
                    "hostname": urls.hostname,
                    "hostname_source": urls.hostname_source,
                    "port": urls.port,
                    "normal_access_url": urls.normal_access_url,
                    "local_access_url": urls.local_access_url,
                },
                ensure_ascii=False,
            )
        )
        return 0
    print(urls.normal_access_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
