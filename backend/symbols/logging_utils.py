from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.core.runtime_paths import LOG_DIR_ENV, runtime_path_from_env

SYMBOL_LOG_DIR = runtime_path_from_env(LOG_DIR_ENV, "logs")
SYMBOL_REFRESH_LOG_FILENAME = "symbol_refresh.log"
SYMBOL_REFRESH_LOG_MAX_BYTES = 1_000_000
SYMBOL_REFRESH_LOG_BACKUP_COUNT = 3


def configure_symbol_refresh_logger(
    *,
    log_dir: Path | str = SYMBOL_LOG_DIR,
    logger_name: str = "smart_market_ai.symbols.refresh",
    max_bytes: int = SYMBOL_REFRESH_LOG_MAX_BYTES,
    backup_count: int = SYMBOL_REFRESH_LOG_BACKUP_COUNT,
) -> logging.Logger:
    """Configure a bounded symbol-refresh logger with rotating file storage."""

    logger = logging.getLogger(logger_name)
    if _should_use_test_null_logger(log_dir=log_dir, logger_name=logger_name):
        logger.setLevel(logging.INFO)
        logger.propagate = False
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        logger.addHandler(logging.NullHandler())
        return logger

    log_root = Path(log_dir)
    log_root.mkdir(parents=True, exist_ok=True)
    log_file = log_root / SYMBOL_REFRESH_LOG_FILENAME
    logger.setLevel(logging.INFO)
    logger.propagate = False

    resolved_log_file = log_file.resolve()
    for handler in logger.handlers:
        if (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == resolved_log_file
        ):
            return logger

    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _should_use_test_null_logger(*, log_dir: Path | str, logger_name: str) -> bool:
    return (
        os.environ.get("PYTEST_CURRENT_TEST") is not None
        and Path(log_dir) == SYMBOL_LOG_DIR
        and logger_name == "smart_market_ai.symbols.refresh"
    )
