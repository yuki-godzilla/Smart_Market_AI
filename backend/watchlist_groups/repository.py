from __future__ import annotations

import json
import logging
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from backend.watchlist_groups.models import WatchlistGroupsState

LOGGER = logging.getLogger(__name__)
SAFE_USER_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class WatchlistGroupsRepository:
    def __init__(self, profile_root: Path = Path("data/user/profiles")) -> None:
        self.profile_root = profile_root

    def load(self, user_id: str) -> WatchlistGroupsState:
        path = self._path(user_id)
        if not path.exists():
            return self.empty_state()
        try:
            payload = path.read_text(encoding="utf-8")
            return WatchlistGroupsState.model_validate_json(payload)
        except (OSError, ValidationError, ValueError, json.JSONDecodeError) as exc:
            LOGGER.warning("Failed to load watchlist groups for user %s: %s", user_id, exc)
            return self.empty_state()

    def save(self, user_id: str, state: WatchlistGroupsState) -> None:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, state.model_dump_json(indent=2) + "\n")

    @staticmethod
    def empty_state() -> WatchlistGroupsState:
        return WatchlistGroupsState(updated_at=datetime.now(UTC))

    def _path(self, user_id: str) -> Path:
        if user_id == "default" or not SAFE_USER_ID.fullmatch(user_id):
            raise ValueError("Invalid persistent user identifier.")
        return self.profile_root / user_id / "watchlist_groups.json"

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
