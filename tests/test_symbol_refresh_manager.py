from __future__ import annotations

import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from backend.symbols.cache import load_symbol_refresh_queue
from backend.symbols.contracts import SymbolRecord, SymbolRefreshTask
from backend.symbols.logging_utils import configure_symbol_refresh_logger
from backend.symbols.refresh_manager import refresh_symbols_if_needed
from backend.symbols.repository import load_symbol_records, save_symbol_record


def test_refresh_manager_saves_each_symbol_and_preserves_data_on_failure(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    save_symbol_record(
        SymbolRecord(
            symbol="AAPL",
            provider="existing",
            updated_at=now,
            normalized_fields={"per": 30},
        ),
        cache_dir=tmp_path,
    )
    tasks = [_task("7203", now), _task("AAPL", now)]

    def provider(task: SymbolRefreshTask) -> SymbolRecord:
        if task.symbol == "AAPL":
            raise RuntimeError("provider raw response should not be logged")
        return SymbolRecord(
            symbol=task.symbol,
            provider="fake",
            updated_at=now,
            normalized_fields={"price": 1000},
        )

    result = refresh_symbols_if_needed(
        provider=provider,
        tasks=tasks,
        cache_dir=tmp_path,
        now=now,
        logger=logging.getLogger("test.symbol.refresh.manager"),
    )

    records = load_symbol_records(cache_dir=tmp_path)
    queue = load_symbol_refresh_queue(cache_dir=tmp_path)

    assert result.attempted_count == 2
    assert result.succeeded_count == 1
    assert result.failed_count == 1
    assert records["7203"].normalized_fields["price"] == 1000
    assert records["AAPL"].normalized_fields["per"] == 30
    assert {task.symbol: task.status for task in queue}["AAPL"] == "retryable"


def test_refresh_manager_skips_when_lock_is_active(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    (tmp_path / "symbol_refresh.lock").write_text(now.isoformat(), encoding="utf-8")

    result = refresh_symbols_if_needed(
        provider=lambda task: None,
        tasks=[_task("7203", now)],
        cache_dir=tmp_path,
        now=now,
        logger=logging.getLogger("test.symbol.refresh.lock"),
    )

    assert result.skipped_count == 1
    assert result.items[0].skipped_reason == "lock_active"


def test_symbol_refresh_logger_uses_rotating_file_handler(tmp_path) -> None:
    logger = configure_symbol_refresh_logger(
        log_dir=tmp_path,
        logger_name="test.symbol.refresh.logger",
        max_bytes=1024,
        backup_count=2,
    )

    handlers = [handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)]

    assert handlers
    assert handlers[0].maxBytes == 1024
    assert handlers[0].backupCount == 2


def _task(symbol: str, requested_at: datetime) -> SymbolRefreshTask:
    return SymbolRefreshTask(
        symbol=symbol,
        priority=10,
        refresh_priority_score=10,
        reason="startup_refresh",
        status="pending",
        requested_at=requested_at,
    )
