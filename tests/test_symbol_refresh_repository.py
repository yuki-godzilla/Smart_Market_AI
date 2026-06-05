from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.symbols.contracts import SymbolRecord
from backend.symbols.repository import (
    load_symbol_record,
    load_symbol_records,
    normalize_symbol_record,
    save_symbol_record,
)


def test_save_symbol_record_is_atomic_and_preserves_existing_records(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)

    save_symbol_record(
        SymbolRecord(
            symbol="7203",
            provider="fake",
            updated_at=now,
            normalized_fields={"per": 12.3},
        ),
        cache_dir=tmp_path,
    )
    saved_aapl = save_symbol_record(
        SymbolRecord(
            symbol="aapl",
            provider="fake",
            updated_at=now,
            normalized_fields={"roe": 0.21},
        ),
        cache_dir=tmp_path,
    )

    records = load_symbol_records(cache_dir=tmp_path)

    assert sorted(records) == ["7203", "AAPL"]
    assert saved_aapl.normalized_fields["roe"] == 0.21
    assert load_symbol_record("aapl", cache_dir=tmp_path) is not None
    assert not (tmp_path / "symbols_cache.tmp.json").exists()


def test_load_symbol_records_treats_temporary_read_error_as_empty(
    tmp_path,
    monkeypatch,
) -> None:
    records_file = tmp_path / "symbols_cache.json"
    records_file.write_text("{}", encoding="utf-8")
    original_read_text = type(records_file).read_text

    def fake_read_text(path, *args, **kwargs):
        if path == records_file:
            raise PermissionError("temporarily locked")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(type(records_file), "read_text", fake_read_text)

    assert load_symbol_records(cache_dir=tmp_path) == {}


def test_normalize_symbol_record_removes_raw_fields_and_bounds_text() -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    record = SymbolRecord(
        symbol=" nvda ",
        provider=" fake ",
        updated_at=now,
        normalized_fields={
            "summary": "x" * 400,
            "raw_response": "provider payload",
            "html_body": "<html>",
            "api_key": "secret",
        },
    )

    normalized = normalize_symbol_record(record)

    assert normalized.symbol == "NVDA"
    assert normalized.provider == "fake"
    assert "raw_response" not in normalized.normalized_fields
    assert "html_body" not in normalized.normalized_fields
    assert "api_key" not in normalized.normalized_fields
    summary = normalized.normalized_fields["summary"]
    assert isinstance(summary, str)
    assert len(summary) == 300


def test_symbol_record_rejects_extra_raw_response_field() -> None:
    with pytest.raises(ValidationError):
        SymbolRecord.model_validate(
            {
                "symbol": "7203",
                "provider": "fake",
                "updated_at": datetime(2026, 6, 3, 12, 0, 0),
                "raw_response": {"huge": True},
            }
        )
