from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

APP_NAME = "SmartMarketAI"
DEFAULT_PORT = 8501


def main() -> int:
    app_root = _app_root()
    runtime_root = _runtime_root()
    _prepare_runtime_dirs(runtime_root)
    _configure_environment(app_root, runtime_root)

    os.chdir(app_root)
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    app_file = app_root / "ui" / "app.py"
    if not app_file.exists():
        print(f"[SMAI] Streamlit app file was not found: {app_file}", file=sys.stderr)
        return 1

    port = _available_port(_configured_port())
    url = f"http://127.0.0.1:{port}"
    print("[SMAI] Starting Smart Market AI")
    print(f"[SMAI] App root: {app_root}")
    print(f"[SMAI] Runtime data: {runtime_root}")
    print(f"[SMAI] URL: {url}")
    print("[SMAI] Close this console window to stop the app.")

    _open_browser_later(url)

    from streamlit.web import cli as streamlit_cli

    sys.argv = [
        "streamlit",
        "run",
        str(app_file),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]
    return int(streamlit_cli.main() or 0)


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return Path(__file__).resolve().parents[1]


def _runtime_root() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def _prepare_runtime_dirs(runtime_root: Path) -> None:
    for name in ("cache", "outputs", "logs", "user_config"):
        (runtime_root / name).mkdir(parents=True, exist_ok=True)


def _configure_environment(app_root: Path, runtime_root: Path) -> None:
    cache_dir = runtime_root / "cache"
    outputs_dir = runtime_root / "outputs"
    logs_dir = runtime_root / "logs"
    user_config_dir = runtime_root / "user_config"

    os.environ.setdefault("SMAI_RUNTIME_DIR", str(runtime_root))
    os.environ.setdefault("SMAI_CACHE_DIR", str(cache_dir))
    os.environ.setdefault("SMAI_OUTPUT_DIR", str(outputs_dir))
    os.environ.setdefault("SMAI_LOG_DIR", str(logs_dir))
    os.environ.setdefault("SMAI_USER_CONFIG_DIR", str(user_config_dir))
    os.environ.setdefault("SMAI_YFINANCE_CACHE_DIR", str(cache_dir / "yfinance"))
    os.environ.setdefault("YFINANCE_CACHE_DIR", str(cache_dir / "yfinance"))
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")

    default_config = app_root / "config" / "example.yaml"
    if "SMAI_CONFIG_FILE" not in os.environ and default_config.exists():
        os.environ["SMAI_CONFIG_FILE"] = str(default_config)


def _configured_port() -> int:
    raw_port = os.getenv("SMAI_STREAMLIT_PORT", "").strip()
    if not raw_port:
        return DEFAULT_PORT
    try:
        port = int(raw_port)
    except ValueError:
        return DEFAULT_PORT
    if 1 <= port <= 65535:
        return port
    return DEFAULT_PORT


def _available_port(start_port: int) -> int:
    for port in range(start_port, min(start_port + 50, 65536)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def _open_browser_later(url: str) -> None:
    if os.getenv("SMAI_NO_BROWSER", "").strip() in {"1", "true", "TRUE", "yes"}:
        return

    def open_browser() -> None:
        time.sleep(3)
        try:
            webbrowser.open(url)
        except Exception as exc:  # pragma: no cover - depends on Windows shell state.
            print(f"[SMAI] Browser open skipped: {exc}", file=sys.stderr)

    threading.Thread(target=open_browser, daemon=True).start()


if __name__ == "__main__":
    raise SystemExit(main())
