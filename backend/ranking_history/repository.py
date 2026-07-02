from __future__ import annotations

import gzip
import json
import os
import re
import secrets
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from pydantic import ValidationError

from backend.ranking_history.models import (
    SCHEMA_VERSION,
    RankingHistoryCorruptData,
    RankingHistoryIndex,
    RankingHistoryIndexItem,
    RankingHistoryLockTimeout,
    RankingHistorySnapshot,
)

SAFE_USER_ID = re.compile(r"^[A-Za-z0-9_-]+$")
SAFE_RUN_ID = re.compile(r"^rh_[A-Za-z0-9_-]{8,80}$")
SAFE_SNAPSHOT = re.compile(r"^rh_[A-Za-z0-9_-]{8,80}\.json\.gz$")


class RankingHistoryRepository:
    def __init__(
        self,
        profile_root: Path = Path("data/user/profiles"),
        *,
        lock_timeout: float = 2.0,
    ) -> None:
        self.profile_root = profile_root
        self.lock_timeout = lock_timeout

    def load_index(self, user_id: str) -> RankingHistoryIndex:
        path = self._history_root(user_id) / "index.json"
        if not path.exists():
            return RankingHistoryIndex(updated_at=datetime.now(UTC))
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            index = RankingHistoryIndex.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise RankingHistoryCorruptData("ランキング履歴の一覧を読み込めません。") from exc
        if index.schema_version != SCHEMA_VERSION:
            raise RankingHistoryCorruptData("未対応のランキング履歴形式です。")
        return index

    def save_index(self, user_id: str, index: RankingHistoryIndex) -> None:
        root = self._history_root(user_id)
        root.mkdir(parents=True, exist_ok=True)
        self._atomic_write(root / "index.json", index.model_dump_json(indent=2) + "\n")

    def write_snapshot(self, user_id: str, snapshot: RankingHistorySnapshot) -> None:
        self._validate_run(snapshot.run_id)
        if snapshot.user_id != user_id:
            raise ValueError("Snapshot user does not match repository scope.")
        path = self._snapshot_path(user_id, snapshot.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
        try:
            with gzip.open(temporary, "wt", encoding="utf-8") as stream:
                stream.write(snapshot.model_dump_json(indent=2))
                stream.flush()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def read_snapshot(self, user_id: str, run_id: str) -> RankingHistorySnapshot:
        path = self._snapshot_path(user_id, run_id)
        try:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                snapshot = RankingHistorySnapshot.model_validate_json(stream.read())
        except (OSError, EOFError, gzip.BadGzipFile, ValidationError) as exc:
            raise RankingHistoryCorruptData("ランキング履歴の詳細を読み込めません。") from exc
        if snapshot.schema_version != SCHEMA_VERSION or snapshot.user_id != user_id:
            raise RankingHistoryCorruptData("ランキング履歴の所有者または形式が一致しません。")
        return snapshot

    def delete_snapshot(self, user_id: str, run_id: str) -> None:
        self._snapshot_path(user_id, run_id).unlink(missing_ok=True)

    def list_items(self, user_id: str) -> list[RankingHistoryIndexItem]:
        index = self.load_index(user_id)
        items: list[RankingHistoryIndexItem] = []
        for item in index.items:
            status = "available"
            path = self._snapshot_path(user_id, item.run_id)
            if not path.exists():
                status = "missing"
            items.append(item.model_copy(update={"snapshot_status": status}))
        return items

    def get_item(self, user_id: str, run_id: str) -> RankingHistoryIndexItem | None:
        self._validate_run(run_id)
        return next(
            (item for item in self.load_index(user_id).items if item.run_id == run_id),
            None,
        )

    def update_item(
        self,
        user_id: str,
        run_id: str,
        patch: dict[str, object],
    ) -> RankingHistoryIndexItem | None:
        self._validate_run(run_id)
        with self.lock(user_id):
            index = self.load_index(user_id)
            current = next(
                (item for item in index.items if item.run_id == run_id),
                None,
            )
            if current is None:
                return None
            protected = {"run_id", "user_id", "snapshot_file", "signature"}
            updated = current.model_copy(
                update={key: value for key, value in patch.items() if key not in protected}
            )
            self.save_index(
                user_id,
                RankingHistoryIndex(
                    updated_at=datetime.now(UTC),
                    items=[updated if item.run_id == run_id else item for item in index.items],
                ),
            )
            return updated

    def delete_item(self, user_id: str, run_id: str) -> bool:
        self._validate_run(run_id)
        with self.lock(user_id):
            index = self.load_index(user_id)
            remaining = [item for item in index.items if item.run_id != run_id]
            if len(remaining) == len(index.items):
                return False
            self.save_index(
                user_id,
                RankingHistoryIndex(updated_at=datetime.now(UTC), items=remaining),
            )
            try:
                self.delete_snapshot(user_id, run_id)
            except OSError:
                pass
            return True

    @contextmanager
    def lock(self, user_id: str) -> Iterator[None]:
        root = self._history_root(user_id)
        root.mkdir(parents=True, exist_ok=True)
        lock_path = root / ".lock"
        deadline = time.monotonic() + self.lock_timeout
        while True:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(descriptor)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise RankingHistoryLockTimeout("ランキング履歴を更新中です。")
                time.sleep(0.02)
        try:
            yield
        finally:
            lock_path.unlink(missing_ok=True)

    def _history_root(self, user_id: str) -> Path:
        if user_id == "default" or not SAFE_USER_ID.fullmatch(user_id):
            raise ValueError("Invalid persistent user identifier.")
        return self.profile_root / user_id / "ranking_history"

    def _snapshot_path(self, user_id: str, run_id: str) -> Path:
        self._validate_run(run_id)
        filename = f"{run_id}.json.gz"
        if Path(filename).name != filename or not SAFE_SNAPSHOT.fullmatch(filename):
            raise ValueError("Invalid snapshot filename.")
        return self._history_root(user_id) / "snapshots" / filename

    @staticmethod
    def _validate_run(run_id: str) -> None:
        if not SAFE_RUN_ID.fullmatch(run_id):
            raise ValueError("Invalid ranking history identifier.")

    @staticmethod
    def _atomic_write(path: Path, payload: str) -> None:
        temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
