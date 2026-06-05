from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.core.runtime_paths import LOG_DIR_ENV, runtime_path_from_env

NEWS_LOG_DIR = runtime_path_from_env(LOG_DIR_ENV, "logs")
NEWS_UPDATE_LOG_FILENAME = "news_update.log"
NEWS_UPDATE_LOG_MAX_BYTES = 1_000_000
NEWS_UPDATE_LOG_BACKUP_COUNT = 3


def configure_news_update_logger(
    *,
    log_dir: Path | str = NEWS_LOG_DIR,
    logger_name: str = "smart_market_ai.news.update",
    max_bytes: int = NEWS_UPDATE_LOG_MAX_BYTES,
    backup_count: int = NEWS_UPDATE_LOG_BACKUP_COUNT,
) -> logging.Logger:
    """Configure a bounded news-update logger with rotating file storage."""

    log_root = Path(log_dir)
    log_root.mkdir(parents=True, exist_ok=True)
    log_file = log_root / NEWS_UPDATE_LOG_FILENAME
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == log_file:
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
