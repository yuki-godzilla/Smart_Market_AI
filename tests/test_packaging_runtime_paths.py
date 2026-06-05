from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from backend.core.runtime_paths import runtime_path_from_env


def test_runtime_path_from_env_uses_env_value(monkeypatch, tmp_path) -> None:
    cache_dir = tmp_path / "runtime" / "cache"
    monkeypatch.setenv("SMAI_CACHE_DIR", str(cache_dir))

    assert runtime_path_from_env("SMAI_CACHE_DIR", "data/cache") == cache_dir


def test_runtime_path_from_env_falls_back_to_local_path(monkeypatch) -> None:
    monkeypatch.delenv("SMAI_CACHE_DIR", raising=False)

    assert runtime_path_from_env("SMAI_CACHE_DIR", "data/cache") == Path("data/cache")


def test_launcher_sets_crud_runtime_environment(tmp_path) -> None:
    launcher = runpy.run_path(str(Path("packaging/smai_launcher.py").resolve()))
    prepare_runtime_dirs = cast(Callable[[Path], None], launcher["_prepare_runtime_dirs"])
    configure_environment = cast(Callable[[Path, Path], None], launcher["_configure_environment"])
    runtime_root = tmp_path / "runtime"
    app_root = tmp_path / "app"
    config_dir = app_root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "example.yaml").write_text("marketdata:\n  provider: mock\n", encoding="utf-8")
    runtime_env_names = (
        "SMAI_RUNTIME_DIR",
        "SMAI_CACHE_DIR",
        "SMAI_OUTPUT_DIR",
        "SMAI_LOG_DIR",
        "SMAI_USER_CONFIG_DIR",
        "SMAI_YFINANCE_CACHE_DIR",
        "YFINANCE_CACHE_DIR",
        "SMAI_CONFIG_FILE",
    )
    original_env = {env_name: os.environ.get(env_name) for env_name in runtime_env_names}
    try:
        for env_name in runtime_env_names:
            os.environ.pop(env_name, None)

        prepare_runtime_dirs(runtime_root)
        configure_environment(app_root, runtime_root)

        assert os.environ["SMAI_RUNTIME_DIR"] == str(runtime_root)
        assert os.environ["SMAI_CACHE_DIR"] == str(runtime_root / "cache")
        assert os.environ["SMAI_OUTPUT_DIR"] == str(runtime_root / "outputs")
        assert os.environ["SMAI_LOG_DIR"] == str(runtime_root / "logs")
        assert os.environ["SMAI_USER_CONFIG_DIR"] == str(runtime_root / "user_config")
        assert os.environ["SMAI_YFINANCE_CACHE_DIR"] == str(runtime_root / "cache" / "yfinance")
        assert os.environ["YFINANCE_CACHE_DIR"] == str(runtime_root / "cache" / "yfinance")
        assert os.environ["SMAI_CONFIG_FILE"] == str(config_dir / "example.yaml")
        assert (runtime_root / "cache").is_dir()
        assert (runtime_root / "outputs").is_dir()
        assert (runtime_root / "logs").is_dir()
        assert (runtime_root / "user_config").is_dir()
    finally:
        for env_name, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = original_value


def test_cache_and_log_defaults_can_be_redirected_for_exe_runtime(tmp_path) -> None:
    cache_dir = tmp_path / "runtime" / "cache"
    log_dir = tmp_path / "runtime" / "logs"
    script = (
        "import json\n"
        "from backend.news.cache import NEWS_CACHE_DIR\n"
        "from backend.news.logging_utils import NEWS_LOG_DIR\n"
        "from backend.symbols.cache import SYMBOL_CACHE_DIR\n"
        "from backend.symbols.logging_utils import SYMBOL_LOG_DIR\n"
        "print(json.dumps({\n"
        "    'news_cache': str(NEWS_CACHE_DIR),\n"
        "    'symbol_cache': str(SYMBOL_CACHE_DIR),\n"
        "    'news_log': str(NEWS_LOG_DIR),\n"
        "    'symbol_log': str(SYMBOL_LOG_DIR),\n"
        "}))\n"
    )
    env = os.environ.copy()
    env["SMAI_CACHE_DIR"] = str(cache_dir)
    env["SMAI_LOG_DIR"] = str(log_dir)

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    actual = cast(dict[str, Any], json.loads(result.stdout))

    assert actual == {
        "news_cache": str(cache_dir),
        "symbol_cache": str(cache_dir),
        "news_log": str(log_dir),
        "symbol_log": str(log_dir),
    }
