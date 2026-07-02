import gzip
from datetime import UTC, date, datetime

import pytest

from backend.ranking_history.models import (
    RankingHistoryCorruptData,
    RankingHistoryIndex,
    RankingHistoryIndexItem,
    RankingHistoryLockTimeout,
    RankingHistoryPeriod,
    RankingHistoryResultRow,
    RankingHistorySnapshot,
    RankingHistoryTarget,
)
from backend.ranking_history.repository import RankingHistoryRepository


def _snapshot(user_id: str = "u_abcdefgh", run_id: str = "rh_20260703T000000Z_abcd1234"):
    return RankingHistorySnapshot(
        run_id=run_id,
        user_id=user_id,
        created_at=datetime(2026, 7, 3, tzinfo=UTC),
        data_as_of=date(2026, 7, 2),
        provider="mock",
        period=RankingHistoryPeriod(start=date(2026, 1, 1), end=date(2026, 7, 2)),
        ranking_type="multi_factor",
        weight_preset="multi_factor",
        target=RankingHistoryTarget(product_type="stock"),
        target_label="株式",
        condition_summary="AI総合",
        candidate_count=1,
        saved_row_count=1,
        top_symbols=["AAPL"],
        result_rows=[RankingHistoryResultRow(rank=1, symbol="AAPL")],
        ranking_logic_version="test",
        signature="sha256:test",
    )


def _item(snapshot: RankingHistorySnapshot) -> RankingHistoryIndexItem:
    return RankingHistoryIndexItem(
        run_id=snapshot.run_id,
        user_id=snapshot.user_id,
        created_at=snapshot.created_at,
        data_as_of=snapshot.data_as_of,
        ranking_type=snapshot.ranking_type,
        target=snapshot.target,
        target_label=snapshot.target_label,
        condition_summary=snapshot.condition_summary,
        candidate_count=1,
        saved_row_count=1,
        top_symbols=["AAPL"],
        snapshot_file=f"{snapshot.run_id}.json.gz",
        signature=snapshot.signature,
    )


def test_repository_round_trip_and_user_isolation(tmp_path):
    repository = RankingHistoryRepository(tmp_path)
    snapshot = _snapshot()
    repository.write_snapshot(snapshot.user_id, snapshot)
    repository.save_index(
        snapshot.user_id,
        RankingHistoryIndex(updated_at=snapshot.created_at, items=[_item(snapshot)]),
    )

    assert repository.read_snapshot(snapshot.user_id, snapshot.run_id) == snapshot
    assert len(repository.list_items(snapshot.user_id)) == 1
    assert repository.list_items("u_otheruser") == []


def test_repository_marks_missing_snapshot_without_breaking_list(tmp_path):
    repository = RankingHistoryRepository(tmp_path)
    snapshot = _snapshot()
    repository.save_index(
        snapshot.user_id,
        RankingHistoryIndex(updated_at=snapshot.created_at, items=[_item(snapshot)]),
    )
    assert repository.list_items(snapshot.user_id)[0].snapshot_status == "missing"


def test_repository_rejects_corrupt_index_and_snapshot(tmp_path):
    repository = RankingHistoryRepository(tmp_path)
    root = tmp_path / "u_abcdefgh" / "ranking_history"
    root.mkdir(parents=True)
    (root / "index.json").write_text("{", encoding="utf-8")
    with pytest.raises(RankingHistoryCorruptData):
        repository.load_index("u_abcdefgh")

    snapshot = _snapshot()
    path = root / "snapshots" / f"{snapshot.run_id}.json.gz"
    path.parent.mkdir()
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write("{")
    with pytest.raises(RankingHistoryCorruptData):
        repository.read_snapshot(snapshot.user_id, snapshot.run_id)


@pytest.mark.parametrize("run_id", ["../secret", "rh_ok/../../secret", "bad"])
def test_repository_rejects_path_traversal(tmp_path, run_id):
    repository = RankingHistoryRepository(tmp_path)
    with pytest.raises(ValueError):
        repository.read_snapshot("u_abcdefgh", run_id)


def test_repository_lock_timeout_is_typed(tmp_path):
    repository = RankingHistoryRepository(tmp_path, lock_timeout=0.01)
    root = tmp_path / "u_abcdefgh" / "ranking_history"
    root.mkdir(parents=True)
    (root / ".lock").write_text("", encoding="utf-8")
    with pytest.raises(RankingHistoryLockTimeout):
        with repository.lock("u_abcdefgh"):
            pass
