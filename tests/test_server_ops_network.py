from __future__ import annotations

import json
import subprocess

import pytest

from backend.core.config import Settings
from backend.server_ops.network import (
    MAIN_APPLICATION_PORT_ENV,
    MAIN_APPLICATION_SCHEME_ENV,
    TAILSCALE_HOSTNAME_ENV,
    MainApplicationNetworkError,
    MainApplicationURLs,
    build_main_application_url,
    discover_tailscale_hostname,
    main,
    main_application_settings,
    resolve_main_application_urls,
)


def test_magicdns_url_uses_explicit_configuration_and_localhost_stays_separate() -> None:
    settings = Settings.model_validate(
        {
            "network": {
                "tailscale_hostname": "SMAI-Server",
                "main_application": {"scheme": "http", "port": 8501},
            }
        }
    )

    urls = resolve_main_application_urls(
        settings=settings,
        environ={},
        tailscale_hostname_discoverer=lambda: "should-not-run",
        os_hostname_discoverer=lambda: "should-not-run",
    )

    assert urls.hostname == "smai-server"
    assert urls.hostname_source == "configured"
    assert urls.normal_access_url == "http://smai-server:8501"
    assert urls.local_access_url == "http://localhost:8501"


def test_environment_overrides_the_server_network_configuration() -> None:
    settings = Settings.model_validate(
        {
            "network": {
                "tailscale_hostname": "old-server",
                "main_application": {"scheme": "http", "port": 8501},
            }
        }
    )

    urls = resolve_main_application_urls(
        settings=settings,
        environ={
            TAILSCALE_HOSTNAME_ENV: "smai-server",
            MAIN_APPLICATION_PORT_ENV: "8521",
            MAIN_APPLICATION_SCHEME_ENV: "http",
        },
    )

    assert urls.normal_access_url == "http://smai-server:8521"
    assert urls.local_access_url == "http://localhost:8521"


@pytest.mark.parametrize("hostname", ["0.0.0.0", "localhost", "192.168.1.20", "bad/name"])
def test_magicdns_url_rejects_bind_addresses_ips_and_invalid_hostnames(hostname: str) -> None:
    with pytest.raises(MainApplicationNetworkError):
        build_main_application_url(hostname, 8501)


def test_tailscale_cli_failure_falls_back_to_os_hostname_without_stopping_startup() -> None:
    urls = resolve_main_application_urls(
        settings=Settings(),
        environ={},
        tailscale_hostname_discoverer=lambda: None,
        os_hostname_discoverer=lambda: "SMAI-SERVER",
    )

    assert urls.hostname_source == "os_hostname"
    assert urls.normal_access_url == "http://smai-server:8501"


def test_old_configuration_without_network_section_remains_valid() -> None:
    settings = Settings.model_validate({"dataaccess": {"provider": "mock"}})

    resolved = main_application_settings(settings=settings, environ={})

    assert resolved.port == 8501
    assert resolved.scheme == "http"
    assert resolved.configured_tailscale_hostname is None


def test_discover_tailscale_hostname_uses_own_host_name(monkeypatch) -> None:
    monkeypatch.setattr("backend.server_ops.network.shutil.which", lambda _name: "tailscale")
    observed: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.update(kwargs)
        return subprocess.CompletedProcess(
            args=["tailscale"],
            returncode=0,
            stdout='{"Self": {"HostName": "SMAI-SERVER"}}',
            stderr="",
        )

    monkeypatch.setattr(
        "backend.server_ops.network.subprocess.run",
        fake_run,
    )

    assert discover_tailscale_hostname() == "SMAI-SERVER"
    assert observed["encoding"] == "utf-8"
    assert observed["errors"] == "replace"


def test_discover_tailscale_hostname_handles_missing_cli(monkeypatch) -> None:
    monkeypatch.setattr("backend.server_ops.network.shutil.which", lambda _name: None)

    assert discover_tailscale_hostname() is None


def test_network_cli_emits_json_for_server_operation_scripts(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "backend.server_ops.network.resolve_main_application_urls",
        lambda: MainApplicationURLs(
            hostname="smai-server",
            hostname_source="configured",
            scheme="http",
            port=8501,
            normal_access_url="http://smai-server:8501",
            local_access_url="http://localhost:8501",
        ),
    )

    assert main(["--emit-json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "hostname": "smai-server",
        "hostname_source": "configured",
        "port": 8501,
        "normal_access_url": "http://smai-server:8501",
        "local_access_url": "http://localhost:8501",
    }
