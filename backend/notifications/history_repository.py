from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from backend.notifications.notification_client import NotificationClientResult
from backend.notifications.settings_repository import (
    NotificationSettingsError,
    NotificationSettingsRepository,
)

NotificationState = Literal["unread", "read", "archived"]


@dataclass(frozen=True, slots=True)
class AppNotification:
    event_id: str
    user_id: str
    technical_category: str
    presentation_category: str
    severity: str
    title: str
    summary: str
    created_at: datetime
    state: NotificationState = "unread"
    symbol: str | None = None
    source: str | None = None
    action_url: str | None = None
    metadata: dict[str, object] | None = None
    content_version: str = "notification_content.v1"
    read_at: datetime | None = None
    archived_at: datetime | None = None


class NotificationHistoryRepository:
    def __init__(self, database_path: str | None = None) -> None:
        self._settings = NotificationSettingsRepository(database_path)
        self.database_path = self._settings.database_path

    def save(self, item: AppNotification) -> bool:
        if item.user_id == "default":
            return False
        self._settings.load(item.user_id)
        try:
            with sqlite3.connect(self.database_path) as connection:
                cursor = connection.execute(
                    """INSERT OR IGNORE INTO app_notifications VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.event_id,
                        item.user_id,
                        item.technical_category,
                        item.presentation_category,
                        item.severity,
                        item.title,
                        item.summary,
                        item.symbol,
                        item.source,
                        item.action_url,
                        json.dumps(item.metadata or {}, ensure_ascii=False),
                        item.content_version,
                        item.created_at.isoformat(),
                        item.state,
                        item.read_at.isoformat() if item.read_at else None,
                        item.archived_at.isoformat() if item.archived_at else None,
                    ),
                )
                return cursor.rowcount == 1
        except (OSError, sqlite3.Error) as exc:
            raise NotificationSettingsError("Notification history could not be saved.") from exc

    def list(
        self,
        user_id: str,
        *,
        state: str | None = None,
        category: str | None = None,
        days: int | None = None,
        important_only: bool = False,
        severity: str | None = None,
    ) -> list[AppNotification]:
        if user_id == "default":
            return []
        self._settings.load(user_id)
        clauses, params = ["user_id = ?"], [user_id]
        if state:
            clauses.append("state = ?")
            params.append(state)
        if category:
            clauses.append("presentation_category = ?")
            params.append(category)
        if days:
            clauses.append("created_at >= ?")
            params.append((datetime.now(UTC) - timedelta(days=days)).isoformat())
        if important_only:
            clauses.append("severity IN ('critical', 'high')")
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        query = "SELECT * FROM app_notifications WHERE " + " AND ".join(clauses)
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(query + " ORDER BY created_at DESC", params).fetchall()
        except sqlite3.Error as exc:
            raise NotificationSettingsError("Notification history could not be loaded.") from exc
        return [_from_row(row) for row in rows]

    def mark_read(self, user_id: str, event_id: str) -> None:
        self._update_state(user_id, event_id, "read")

    def archive(self, user_id: str, event_id: str) -> None:
        self._update_state(user_id, event_id, "archived")

    def unread_count(self, user_id: str) -> int:
        return len(self.list(user_id, state="unread"))

    def get(self, user_id: str, event_id: str) -> AppNotification | None:
        self._settings.load(user_id)
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    "SELECT * FROM app_notifications WHERE user_id = ? AND event_id = ?",
                    (user_id, event_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise NotificationSettingsError("Notification history could not be loaded.") from exc
        return _from_row(row) if row else None

    def counts(self, user_id: str) -> dict[str, int]:
        items = self.list(user_id)
        now = datetime.now(UTC)
        return {
            "unread": sum(item.state == "unread" for item in items),
            "read": sum(item.state == "read" for item in items),
            "today": sum(item.created_at.date() == now.date() for item in items),
            "week": sum(item.created_at >= now - timedelta(days=7) for item in items),
        }

    def save_delivery(self, result: NotificationClientResult) -> None:
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.execute(
                    """INSERT INTO delivery_results
                    (event_id, channel, status, reason, http_status, delivered_at, sanitized_error)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.event_id,
                        result.channel,
                        result.status,
                        result.reason,
                        result.status_code,
                        datetime.now(UTC).isoformat() if result.success else None,
                        "Notification delivery failed." if result.status == "failed" else None,
                    ),
                )
        except sqlite3.Error as exc:
            raise NotificationSettingsError("Delivery result could not be saved.") from exc

    def _update_state(self, user_id: str, event_id: str, state: NotificationState) -> None:
        now = datetime.now(UTC).isoformat()
        column = "archived_at" if state == "archived" else "read_at"
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                f"UPDATE app_notifications SET state = ?, {column} = ? "  # noqa: S608
                "WHERE user_id = ? AND event_id = ?",
                (state, now, user_id, event_id),
            )


def _from_row(row: sqlite3.Row) -> AppNotification:
    return AppNotification(
        event_id=row["event_id"],
        user_id=row["user_id"],
        technical_category=row["technical_category"],
        presentation_category=row["presentation_category"],
        severity=row["severity"],
        title=row["title"],
        summary=row["summary"],
        symbol=row["symbol"],
        source=row["source"],
        action_url=row["action_url"],
        metadata=json.loads(row["metadata_json"]),
        content_version=row["content_version"],
        created_at=datetime.fromisoformat(row["created_at"]),
        state=row["state"],
        read_at=datetime.fromisoformat(row["read_at"]) if row["read_at"] else None,
        archived_at=datetime.fromisoformat(row["archived_at"]) if row["archived_at"] else None,
    )
