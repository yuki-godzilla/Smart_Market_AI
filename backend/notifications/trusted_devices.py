from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterator
from uuid import UUID

from backend.notifications.settings_repository import (
    NotificationSettingsError,
    NotificationSettingsRepository,
)


@dataclass(frozen=True, slots=True)
class SmaiUser:
    user_id: str
    display_name: str
    mascot_key: str = "smai"


@dataclass(frozen=True, slots=True)
class TrustedDevice:
    device_id: str
    user_id: str
    device_name: str
    last_seen_at: datetime
    created_at: datetime
    is_trusted: bool = True


def normalize_device_id(value: str) -> str | None:
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        return None


class TrustedDeviceRepository:
    def __init__(self, database_path: str | None = None) -> None:
        settings = NotificationSettingsRepository(database_path)
        settings.load("local_user")
        self.database_path = settings.database_path

    def users(self) -> list[SmaiUser]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT user_id, display_name, mascot_key FROM users "
                "WHERE is_active = 1 ORDER BY created_at"
            ).fetchall()
        return [SmaiUser(*row) for row in rows]

    def resolve(self, device_id: str) -> SmaiUser | None:
        normalized = normalize_device_id(device_id)
        if not normalized:
            return None
        with self._connect() as connection:
            row = connection.execute(
                """SELECT u.user_id, u.display_name, u.mascot_key
                FROM trusted_devices d JOIN users u ON u.user_id = d.user_id
                WHERE d.device_id = ? AND d.is_trusted = 1 AND u.is_active = 1""",
                (normalized,),
            ).fetchone()
            if row:
                connection.execute(
                    "UPDATE trusted_devices SET last_seen_at = ? WHERE device_id = ?",
                    (datetime.now(UTC).isoformat(), normalized),
                )
        return SmaiUser(*row) if row else None

    def trust(self, device_id: str, user_id: str, device_name: str) -> TrustedDevice:
        normalized = normalize_device_id(device_id)
        if not normalized:
            raise ValueError("Invalid device identifier.")
        now = datetime.now(UTC)
        safe_name = device_name.strip()[:80] or "この端末"
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO trusted_devices
                (device_id, user_id, device_name, last_seen_at, created_at, is_trusted)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(device_id) DO UPDATE SET user_id=excluded.user_id,
                device_name=excluded.device_name, last_seen_at=excluded.last_seen_at,
                is_trusted=1""",
                (normalized, user_id, safe_name, now.isoformat(), now.isoformat()),
            )
        return TrustedDevice(normalized, user_id, safe_name, now, now)

    def list(self, user_id: str) -> list[TrustedDevice]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT device_id, user_id, device_name, last_seen_at, created_at, is_trusted
                FROM trusted_devices WHERE user_id = ? ORDER BY last_seen_at DESC""",
                (user_id,),
            ).fetchall()
        return [
            TrustedDevice(
                row[0],
                row[1],
                row[2],
                datetime.fromisoformat(row[3]),
                datetime.fromisoformat(row[4]),
                bool(row[5]),
            )
            for row in rows
        ]

    def revoke(self, user_id: str, device_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE trusted_devices SET is_trusted = 0 WHERE user_id = ? AND device_id = ?",
                (user_id, device_id),
            )

    def rename(self, user_id: str, device_id: str, device_name: str) -> None:
        safe_name = device_name.strip()[:80]
        if not safe_name:
            raise ValueError("Device name is required.")
        with self._connect() as connection:
            connection.execute(
                "UPDATE trusted_devices SET device_name = ? WHERE user_id = ? AND device_id = ?",
                (safe_name, user_id, device_id),
            )

    def set_mascot(self, user_id: str, mascot_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET mascot_key = ? WHERE user_id = ?",
                (mascot_key[:32], user_id),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        try:
            with sqlite3.connect(self.database_path) as connection:
                yield connection
        except sqlite3.Error as exc:
            raise NotificationSettingsError("Device settings are unavailable.") from exc
