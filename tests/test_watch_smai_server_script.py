from pathlib import Path


def test_watcher_does_not_restart_when_listener_ownership_is_unknown() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "server_ops"
        / "watch_smai_server.ps1"
    ).read_text(encoding="utf-8")

    assert 'if ($listenerState -eq "down")' in script
    assert "Recovery skipped." in script
    assert 'if ([string]::IsNullOrWhiteSpace($commandLine)) { return "unknown" }' in script
