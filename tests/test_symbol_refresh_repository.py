from __future__ import annotations

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.symbols.contracts import SymbolRecord
from backend.symbols.repository import (
    delete_symbol_record,
    delete_symbol_records,
    load_symbol_record,
    load_symbol_records,
    normalize_symbol_record,
    purge_symbol_records_by_status,
    save_symbol_record,
    save_symbol_records,
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


def test_save_symbol_records_upserts_multiple_records_without_legacy_json_read(
    tmp_path,
    monkeypatch,
) -> None:
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
    records_file = tmp_path / "symbols_cache.json"
    original_read_text = type(records_file).read_text
    read_count = 0

    def counting_read_text(path, *args, **kwargs):
        nonlocal read_count
        if path == records_file:
            read_count += 1
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(type(records_file), "read_text", counting_read_text)

    saved = save_symbol_records(
        [
            SymbolRecord(
                symbol="AAPL",
                provider="fake",
                updated_at=now,
                normalized_fields={"roe": 0.21},
            ),
            SymbolRecord(
                symbol="NVDA",
                provider="fake",
                updated_at=now,
                normalized_fields={"pbr": 14.2},
            ),
        ],
        cache_dir=tmp_path,
    )
    reads_after_save = read_count

    records = load_symbol_records(cache_dir=tmp_path)

    assert [record.symbol for record in saved] == ["AAPL", "NVDA"]
    assert sorted(records) == ["7203", "AAPL", "NVDA"]
    assert reads_after_save == 0
    assert (tmp_path / "symbols_cache.sqlite").exists()
    assert not (tmp_path / "symbols_cache.tmp.json").exists()


def test_delete_symbol_records_removes_only_requested_records(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    save_symbol_records(
        [
            SymbolRecord(symbol="AAPL", provider="fake", updated_at=now),
            SymbolRecord(symbol="NVDA", provider="fake", updated_at=now),
        ],
        cache_dir=tmp_path,
    )

    assert delete_symbol_record("aapl", cache_dir=tmp_path) is True
    assert delete_symbol_records(["missing", "NVDA"], cache_dir=tmp_path) == 1

    assert load_symbol_records(cache_dir=tmp_path) == {}


def test_purge_symbol_records_by_status_removes_missing_records(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    save_symbol_records(
        [
            SymbolRecord(
                symbol="MISS",
                provider="fake",
                updated_at=now,
                data_freshness_status="missing",
            ),
            SymbolRecord(symbol="FRESH", provider="fake", updated_at=now),
        ],
        cache_dir=tmp_path,
    )

    assert purge_symbol_records_by_status(["missing"], cache_dir=tmp_path) == 1

    assert sorted(load_symbol_records(cache_dir=tmp_path)) == ["FRESH"]


def test_load_symbol_records_migrates_legacy_json_to_sqlite(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    records_file = tmp_path / "symbols_cache.json"
    records_file.write_text(
        json.dumps(
            {
                "aapl": {
                    "symbol": "aapl",
                    "provider": "legacy",
                    "updated_at": now.isoformat(),
                    "normalized_fields": {"name": "Apple Inc."},
                }
            }
        ),
        encoding="utf-8",
    )

    records = load_symbol_records(cache_dir=tmp_path)
    loaded = load_symbol_record("AAPL", cache_dir=tmp_path)

    assert sorted(records) == ["AAPL"]
    assert loaded is not None
    assert loaded.symbol == "AAPL"
    assert loaded.provider == "legacy"
    assert (tmp_path / "symbols_cache.sqlite").exists()
    assert records_file.exists()


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
