from datetime import UTC, date, datetime, timedelta

from backend.ranking_history.models import (
    RankingHistoryPeriod,
    RankingHistoryResultRow,
    RankingHistorySaveRequest,
    RankingHistoryTarget,
)
from backend.ranking_history.repository import RankingHistoryRepository
from backend.ranking_history.service import RankingHistoryService


def _request(symbol: str = "AAPL") -> RankingHistorySaveRequest:
    return RankingHistorySaveRequest(
        data_as_of=date(2026, 7, 2),
        provider="mock",
        period=RankingHistoryPeriod(start=date(2026, 1, 1), end=date(2026, 7, 2)),
        ranking_type="multi_factor",
        weight_preset="multi_factor",
        target=RankingHistoryTarget(product_type="stock"),
        target_label="株式",
        condition_summary="AI総合",
        candidate_count=1,
        result_rows=[RankingHistoryResultRow(rank=1, symbol=symbol, total_score=80)],
        ranking_logic_version="test",
    )


def test_service_skips_default_and_empty(tmp_path):
    service = RankingHistoryService(RankingHistoryRepository(tmp_path))
    assert service.save_ranking_history("default", _request()).status == "skipped_default"
    empty = _request().model_copy(update={"result_rows": []})
    assert service.save_ranking_history("u_abcdefgh", empty).status == "skipped_empty"


def test_service_dedupes_within_five_minutes_but_allows_later(tmp_path):
    current = [datetime(2026, 7, 3, tzinfo=UTC)]
    service = RankingHistoryService(RankingHistoryRepository(tmp_path), now=lambda: current[0])
    first = service.save_ranking_history("u_abcdefgh", _request())
    assert first.status == "saved"
    assert service.save_ranking_history("u_abcdefgh", _request()).status == "duplicate"
    current[0] += timedelta(minutes=5)
    assert service.save_ranking_history("u_abcdefgh", _request()).status == "saved"


def test_service_prunes_normal_history_and_keeps_pinned(tmp_path):
    current = [datetime(2026, 7, 3, tzinfo=UTC)]
    service = RankingHistoryService(RankingHistoryRepository(tmp_path), now=lambda: current[0])
    first = service.save_ranking_history("u_abcdefgh", _request("PIN"))
    assert first.run_id
    assert service.set_pinned("u_abcdefgh", first.run_id, True).success
    for index in range(31):
        current[0] += timedelta(minutes=5)
        assert (
            service.save_ranking_history("u_abcdefgh", _request(f"S{index:02}")).status == "saved"
        )
    items = service.list_ranking_history("u_abcdefgh").items
    assert len([item for item in items if not item.is_pinned]) == 30
    assert any(item.run_id == first.run_id and item.is_pinned for item in items)


def test_unpin_prunes_and_pin_metadata_stays_in_sync(tmp_path):
    current = [datetime(2026, 7, 3, tzinfo=UTC)]
    repository = RankingHistoryRepository(tmp_path)
    service = RankingHistoryService(repository, now=lambda: current[0])
    first = service.save_ranking_history("u_abcdefgh", _request("PIN"))
    assert first.run_id
    assert service.set_pinned("u_abcdefgh", first.run_id, True).success
    snapshot = service.get_ranking_history("u_abcdefgh", first.run_id).snapshot
    assert snapshot and snapshot.is_pinned
    assert service.set_pinned("u_abcdefgh", first.run_id, False).success
    snapshot = service.get_ranking_history("u_abcdefgh", first.run_id).snapshot
    assert snapshot and not snapshot.is_pinned


def test_delete_removes_index_and_snapshot(tmp_path):
    service = RankingHistoryService(RankingHistoryRepository(tmp_path))
    saved = service.save_ranking_history("u_abcdefgh", _request())
    assert saved.run_id
    assert service.delete_ranking_history("u_abcdefgh", saved.run_id).success
    assert service.list_ranking_history("u_abcdefgh").items == []
    assert service.get_ranking_history("u_abcdefgh", saved.run_id).snapshot is None
