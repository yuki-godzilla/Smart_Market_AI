# Windows Web Workspace Startup

## Purpose

Smart Market AI runs as a background runtime on Windows. The runtime must not expose CMD, PowerShell, Python, Streamlit, watcher, or duplicate-instance console windows to the interactive user.

The only user-facing local workspace is the pair of browser applications:

- Smart Market AI: `http://localhost:8501`
- SMAI Analytics: `http://localhost:8502`

The Analytics repository owns browser-window opening and placement. This repository owns the main SMAI runtime and its recovery watcher.

## Runtime architecture

`SmartMarketAI-Runtime` is the canonical Scheduled Task. It launches `scripts/start_smai_runtime.ps1` through hidden, non-interactive PowerShell. The script starts the duplicate-safe Python supervisor in `backend.server_ops.launcher` and writes runtime output to `logs/server_ops/runtime.log`.

The runtime preserves:

- `0.0.0.0:8501` LAN binding
- Tailscale/LAN reachability
- duplicate-safe startup lock and health reuse
- maintenance startup state
- resilient Streamlit restart
- Assistant Gateway autostart

The watcher is also registered as a hidden PowerShell task. Recovery starts `scripts/start_smai_runtime.ps1`; it no longer goes through the legacy `start_smai_server.bat`/CMD path.

## Lifecycle telemetry

The runtime publishes `data/ops/server_ops/runtime_lifecycle.json` atomically. Supported phases are:

- `STARTING`
- `READY`
- `DEGRADED`
- `CRITICAL`
- `STOPPING`

SMAI Analytics reads this file so a normal startup or explicit stop/restart is not confused with a service-continuity incident.

## Registering the runtime

From a PowerShell session in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\server_ops\register_smai_autostart_task.ps1
```

The registration disables the legacy `SmartMarketAI-LAN-Server` and `SmartMarketAI-Server-Autostart` tasks when present and registers:

- `SmartMarketAI-Runtime`
- `SmartMarketAI-Server-Watch`

Both actions use hidden PowerShell and `MultipleInstances IgnoreNew`.

## Logs

Operational output is written under `logs/server_ops/`, including:

- `runtime.log`
- `watch_server.log`
- `maintenance.log`

Console UI is not an operational dependency.

## Validation after deployment

On the Windows server PC, verify after logoff/logon or reboot:

1. No CMD, PowerShell, Python, or Streamlit console is visible.
2. `http://localhost:8501/_stcore/health` returns healthy.
3. LAN and Tailscale access to the existing port 8501 remain available.
4. Re-running the runtime registration/start path does not create a second Streamlit server.
5. Stopping the Streamlit child for a controlled recovery test causes the watcher to recover through the hidden runtime launcher.
6. `runtime_lifecycle.json` progresses through startup to `READY`.

The browser workspace and rightmost-monitor 50/50 layout are documented and registered from the `SMAI_Server_Analytics` repository.
