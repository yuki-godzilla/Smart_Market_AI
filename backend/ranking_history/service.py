from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from backend.ranking_history.models import (
    RankingHistoryIndex,
    RankingHistoryIndexItem,
    RankingHistoryListResult,
    RankingHistoryMutationResult,
    RankingHistorySaveRequest,
    RankingHistorySaveResult,
    RankingHistorySnapshot,
    RankingHistorySnapshotResult,
)
from backend.ranking_history.repository import RankingHistoryRepository


class RankingHistoryService:
    def __init__(
        self,
        repository: RankingHistoryRepository | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository or RankingHistoryRepository()
        self._now = now or (lambda: datetime.now(UTC))

    def save_ranking_history(
        self, user_id: str, request: RankingHistorySaveRequest
    ) -> RankingHistorySaveResult:
        if user_id == "default":
            return RankingHistorySaveResult(
                status="skipped_default",
                message="ランキング履歴を保存するにはプロフィールを選択してください。",
            )
        if not request.result_rows:
            return RankingHistorySaveResult(
                status="skipped_empty",
                message="保存対象がありません。",
            )
        try:
            with self.repository.lock(user_id):
                index = self.repository.load_index(user_id)
                now = self._aware_now()
                signature = ranking_history_signature(user_id, request)
                duplicate = next(
                    (
                        item
                        for item in index.items
                        if item.signature == signature
                        and now - _aware(item.created_at) < timedelta(minutes=5)
                    ),
                    None,
                )
                if duplicate:
                    return RankingHistorySaveResult(
                        status="duplicate",
                        run_id=duplicate.run_id,
                        message="同じランキング結果は直近に保存済みです。",
                    )
                run_id = f"rh_{now.strftime('%Y%m%dT%H%M%SZ')}_{secrets.token_hex(4)}"
                top_symbols = [row.symbol for row in request.result_rows[:3]]
                snapshot = RankingHistorySnapshot(
                    run_id=run_id,
                    user_id=user_id,
                    created_at=now,
                    data_as_of=request.data_as_of,
                    provider=request.provider,
                    period=request.period,
                    ranking_type=request.ranking_type,
                    weight_preset=request.weight_preset,
                    target=request.target,
                    target_label=request.target_label,
                    filters=request.filters,
                    condition_summary=request.condition_summary,
                    candidate_count=request.candidate_count,
                    saved_row_count=len(request.result_rows),
                    top_symbols=top_symbols,
                    result_rows=request.result_rows,
                    ranking_logic_version=request.ranking_logic_version,
                    universe_version=request.universe_version,
                    signature=signature,
                )
                item = _item_from_snapshot(snapshot)
                self.repository.write_snapshot(user_id, snapshot)
                kept, removed = _pruned_items([item, *index.items])
                self.repository.save_index(
                    user_id,
                    RankingHistoryIndex(updated_at=now, items=kept),
                )
                for removed_item in removed:
                    try:
                        self.repository.delete_snapshot(user_id, removed_item.run_id)
                    except OSError:
                        pass
                return RankingHistorySaveResult(
                    status="saved",
                    run_id=run_id,
                    message="ランキング結果を履歴に保存しました。",
                )
        except Exception:
            return RankingHistorySaveResult(
                status="failed",
                message="ランキング結果は表示できますが、履歴保存に失敗しました。",
            )

    def list_ranking_history(self, user_id: str) -> RankingHistoryListResult:
        if user_id == "default":
            return RankingHistoryListResult()
        try:
            return RankingHistoryListResult(items=self.repository.list_items(user_id))
        except Exception as exc:
            return RankingHistoryListResult(error=str(exc))

    def get_ranking_history(self, user_id: str, run_id: str) -> RankingHistorySnapshotResult:
        if user_id == "default":
            return RankingHistorySnapshotResult(error="プロフィールを選択してください。")
        try:
            item = self.repository.get_item(user_id, run_id)
            if item is None:
                return RankingHistorySnapshotResult(error="履歴が見つかりません。")
            return RankingHistorySnapshotResult(
                snapshot=self.repository.read_snapshot(user_id, run_id)
            )
        except Exception as exc:
            return RankingHistorySnapshotResult(error=str(exc))

    def set_pinned(self, user_id: str, run_id: str, pinned: bool) -> RankingHistoryMutationResult:
        try:
            with self.repository.lock(user_id):
                index = self.repository.load_index(user_id)
                item = next(
                    (value for value in index.items if value.run_id == run_id),
                    None,
                )
                if item is None:
                    return RankingHistoryMutationResult(
                        success=False,
                        error="履歴が見つかりません。",
                    )
                snapshot = self.repository.read_snapshot(user_id, run_id)
                self.repository.write_snapshot(
                    user_id, snapshot.model_copy(update={"is_pinned": pinned})
                )
                updated = [
                    (
                        value.model_copy(update={"is_pinned": pinned})
                        if value.run_id == run_id
                        else value
                    )
                    for value in index.items
                ]
                kept, removed = _pruned_items(updated)
                self.repository.save_index(
                    user_id,
                    RankingHistoryIndex(updated_at=self._aware_now(), items=kept),
                )
                for removed_item in removed:
                    try:
                        self.repository.delete_snapshot(user_id, removed_item.run_id)
                    except OSError:
                        pass
            return RankingHistoryMutationResult(success=True)
        except Exception as exc:
            return RankingHistoryMutationResult(success=False, error=str(exc))

    def delete_ranking_history(self, user_id: str, run_id: str) -> RankingHistoryMutationResult:
        try:
            with self.repository.lock(user_id):
                index = self.repository.load_index(user_id)
                if not any(item.run_id == run_id for item in index.items):
                    return RankingHistoryMutationResult(
                        success=False,
                        error="履歴が見つかりません。",
                    )
                self.repository.save_index(
                    user_id,
                    RankingHistoryIndex(
                        updated_at=self._aware_now(),
                        items=[item for item in index.items if item.run_id != run_id],
                    ),
                )
                try:
                    self.repository.delete_snapshot(user_id, run_id)
                except OSError:
                    pass
            return RankingHistoryMutationResult(success=True)
        except Exception as exc:
            return RankingHistoryMutationResult(success=False, error=str(exc))

    def restore_payload_from_snapshot(self, snapshot: RankingHistorySnapshot) -> dict[str, Any]:
        return dict(snapshot.filters)

    def _aware_now(self) -> datetime:
        return _aware(self._now())


def ranking_history_signature(user_id: str, request: RankingHistorySaveRequest) -> str:
    payload = {
        "user_id": user_id,
        "filters": request.filters,
        "ranking_type": request.ranking_type,
        "weight_preset": request.weight_preset,
        "provider": request.provider,
        "data_as_of": request.data_as_of.isoformat(),
        "period": request.period.model_dump(mode="json"),
        "candidate_count": request.candidate_count,
        "saved_row_count": len(request.result_rows),
        "rows": [
            {
                "rank": row.rank,
                "symbol": row.symbol,
                "total_score": row.total_score,
                "upside_signal_score": row.upside_signal_score,
                "downside_signal_score": row.downside_signal_score,
            }
            for row in request.result_rows
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _item_from_snapshot(snapshot: RankingHistorySnapshot) -> RankingHistoryIndexItem:
    return RankingHistoryIndexItem(
        run_id=snapshot.run_id,
        user_id=snapshot.user_id,
        created_at=snapshot.created_at,
        data_as_of=snapshot.data_as_of,
        ranking_type=snapshot.ranking_type,
        target=snapshot.target,
        target_label=snapshot.target_label,
        condition_summary=snapshot.condition_summary,
        candidate_count=snapshot.candidate_count,
        saved_row_count=snapshot.saved_row_count,
        top_symbols=snapshot.top_symbols,
        is_pinned=snapshot.is_pinned,
        title=snapshot.title,
        memo=snapshot.memo,
        snapshot_file=f"{snapshot.run_id}.json.gz",
        signature=snapshot.signature,
    )


def _pruned_items(
    items: list[RankingHistoryIndexItem],
) -> tuple[list[RankingHistoryIndexItem], list[RankingHistoryIndexItem]]:
    ordered = sorted(items, key=lambda item: _aware(item.created_at), reverse=True)
    pinned = [item for item in ordered if item.is_pinned]
    normal = [item for item in ordered if not item.is_pinned]
    return [*pinned, *normal[:30]], normal[30:]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
