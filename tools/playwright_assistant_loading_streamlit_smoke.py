from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal

import yaml
from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs/work/playwright_assistant_loading_streamlit"


class _GatewayHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        server = self.server
        time.sleep(float(getattr(server, "response_delay", 0.0)))
        if self.path != "/models":
            self.send_error(404)
            return
        server.request_count = getattr(server, "request_count", 0) + 1
        mode = getattr(server, "response_mode", "ready")
        if mode == "failed" or (mode == "recover" and server.request_count <= 4):
            self._json_response(503, {"detail": "fake gateway unavailable"})
            return
        self._json_response(
            200,
            {
                "provider": "ollama",
                "base_url": "http://127.0.0.1:11434",
                "default_profile": "notebook_dev",
                "default_model": "qwen3:1.7b",
                "installed_models": ["qwen3:1.7b", "qwen3:8b"],
                "models": [
                    {
                        "name": "qwen3:1.7b",
                        "modified_at": "2026-06-19T10:00:00Z",
                        "size": 1800000000,
                    },
                    {
                        "name": "qwen3:8b",
                        "modified_at": "2026-06-20T10:00:00Z",
                        "size": 8000000000,
                    },
                ],
                "configured_model_installed": True,
            },
        )

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _json_response(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live Streamlit Playwright smoke for Assistant loading auto transition."
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, object] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        results["ready"] = _run_scenario(
            browser=browser,
            output_dir=output_dir,
            mode="ready",
            response_delay=4.0,
        )
        results["failed"] = _run_scenario(
            browser=browser,
            output_dir=output_dir,
            mode="failed",
            response_delay=2.0,
        )
        results["recovered"] = _run_scenario(
            browser=browser,
            output_dir=output_dir,
            mode="recover",
            response_delay=0.2,
        )
        results["no_cache"] = _run_scenario(
            browser=browser,
            output_dir=output_dir,
            mode="no_cache",
            response_delay=4.0,
        )
        browser.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))


def _run_scenario(
    *,
    browser,
    output_dir: Path,
    mode: Literal["ready", "failed", "recover", "no_cache"],
    response_delay: float,
) -> dict[str, str]:
    gateway_port = _free_port()
    app_port = _free_port()
    gateway = ThreadingHTTPServer(("127.0.0.1", gateway_port), _GatewayHandler)
    gateway.response_mode = mode  # type: ignore[attr-defined]
    gateway.response_delay = response_delay  # type: ignore[attr-defined]
    gateway_thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    gateway_thread.start()

    config_path = output_dir / f"assistant_loading_{mode}.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "assistant": {
                    "gateway": {
                        "enabled": True,
                        "base_url": f"http://127.0.0.1:{gateway_port}",
                        "model": "qwen3:1.7b",
                        "preferred_profile": "notebook_dev",
                    },
                    "warmup": {
                        "enabled": True,
                        "chat_enabled": False,
                        "health_timeout_seconds": 8,
                        "timeout_seconds": 12,
                        "retry_count": 2,
                        "retry_backoff_seconds": 0.2,
                    },
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    log_path = output_dir / f"streamlit_{mode}.log"
    log_file = log_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "SMAI_CONFIG_FILE": str(config_path),
            "SMAI_ASSISTANT_GATEWAY_AUTOSTART": "0",
            "SMAI_SKIP_ASSISTANT_GATEWAY_STATUS_CHECK": "1",
            "SMAI_SYMBOL_STARTUP_REFRESH_ENABLED": "0",
        }
    )
    if mode == "no_cache":
        empty_cache_dir = output_dir / "no_cache_empty"
        empty_cache_dir.mkdir(parents=True, exist_ok=True)
        env["SMAI_CACHE_DIR"] = str(empty_cache_dir)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "ui/app.py",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(app_port),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    page: Page | None = None
    try:
        base_url = f"http://127.0.0.1:{app_port}"
        _wait_for_http(base_url)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(f"{base_url}/?smai_page=copilot", wait_until="domcontentloaded", timeout=60000)
        page.get_by_text("SMAIアシスタント", exact=True).first.wait_for(timeout=60000)
        loading = page.locator(".smai-warmup-panel")
        loading.get_by_text("LLM起動確認中", exact=False).wait_for(timeout=30000)
        loading.locator('[data-testid="assistant-loading-radar-icon"]').wait_for()
        loading.locator('[data-testid="assistant-loading-animation"]').wait_for()
        if mode == "no_cache":
            loading.locator('[data-testid="assistant-loading-headlines-empty"]').wait_for()
            assert loading.locator('[data-testid="assistant-loading-news-card"]').count() == 0
        else:
            news_cards = loading.locator('[data-testid="assistant-loading-news-card"]')
            news_cards.first.wait_for()
            assert 3 <= news_cards.count() <= 5
            assert news_cards.first.locator(
                '[data-testid="assistant-loading-news-category"]'
            ).is_visible()
            assert news_cards.first.locator(
                '[data-testid="assistant-loading-news-title"]'
            ).is_visible()
            assert news_cards.first.locator(
                '[data-testid="assistant-loading-news-meta"]'
            ).is_visible()
            assert (news_cards.first.bounding_box() or {"width": 0})["width"] >= 480
        modal = page.locator('[data-testid="assistant-loading-modal"]')
        modal.wait_for()
        sidebar = page.locator('section[data-testid="stSidebar"]')
        assert sidebar.is_visible()
        assert (sidebar.bounding_box() or {"x": 999})["x"] < (modal.bounding_box() or {"x": 0})["x"]
        draft = page.get_by_placeholder(
            "価格・予測・ニュース・根拠資料について確認したいことを入力..."
        )
        try:
            draft.click(timeout=1000)
            raise AssertionError("main composer must be blocked while loading modal is open")
        except Exception as exc:  # Playwright actionability timeout is expected
            if isinstance(exc, AssertionError):
                raise
        page.screenshot(path=str(output_dir / f"streamlit_{mode}_loading.png"), full_page=True)

        if mode in {"ready", "no_cache"}:
            page.get_by_text("準備完了", exact=True).first.wait_for(timeout=30000)
            loading.wait_for(state="hidden", timeout=30000)
            draft.fill("通常画面で入力できます")
            if mode == "ready":
                page.get_by_role("button", name="モデルを変更").click()
                page.get_by_text("利用可能モデル", exact=True).wait_for(timeout=5000)
                page.get_by_text("qwen3:8b", exact=False).last.wait_for(timeout=5000)
                assert page.get_by_text("用途プロファイル", exact=True).count() == 0
                assert page.get_by_role("combobox").count() == 0
                page.get_by_text("qwen3:8b", exact=False).last.click()
                page.get_by_text("AIモデル: qwen3:8b / バランス", exact=True).wait_for(
                    timeout=30000
                )
                page.get_by_role("button", name="モデルを変更").click()
                page.get_by_text("qwen3:8b  [選択中]", exact=False).wait_for(timeout=5000)
                assert "desktop_fast" not in page.locator("body").inner_text()
        else:
            fallback_panel = page.locator('[data-testid="assistant-fallback-panel"]')
            fallback_panel.wait_for(timeout=30000)
            modal.wait_for(state="hidden", timeout=30000)
            assert draft.is_enabled()
            assert "Traceback" not in page.locator("body").inner_text()
            if mode == "recover":
                page.get_by_role("button", name="LLM接続を再確認").first.click()
                page.get_by_text("準備完了", exact=True).first.wait_for(timeout=30000)
                fallback_panel.wait_for(state="hidden", timeout=30000)
        page.screenshot(path=str(output_dir / f"streamlit_{mode}_final.png"), full_page=True)
        return {"status": "ok", "url": base_url, "log": str(log_path)}
    finally:
        if page is not None:
            page.close()
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log_file.close()
        gateway.shutdown()
        gateway.server_close()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(url: str, *, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:  # noqa: S310
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Streamlit did not start: {last_error}")


if __name__ == "__main__":
    main()
