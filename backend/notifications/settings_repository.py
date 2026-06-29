from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from backend.core.runtime_paths import USER_CONFIG_DIR_ENV, runtime_path_from_env
from backend.notifications.notification_client import NotificationSeverity

SCHEMA_VERSION = 1
NOTIFICATION_DB_FILENAME = "notifications.sqlite"


class NotificationSettingsError(Exception):
    """Safe domain error for notification setting persistence."""


@dataclass(frozen=True, slots=True)
class NotificationSetting:
    user_id: str
    app_enabled: bool = True
    ntfy_enabled: bool = False
    ntfy_server_url: str = "https://ntfy.sh"
    ntfy_topic: str | None = None
    severity_threshold: NotificationSeverity = "medium"
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    updated_at: datetime | None = None

    @property
    def topic_configured(self) -> bool:
        return bool(self.ntfy_topic)


def default_notification_database_path() -> Path:
    root = runtime_path_from_env(USER_CONFIG_DIR_ENV, Path("data/user"))
    return root / NOTIFICATION_DB_FILENAME


class NotificationSettingsRepository:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = Path(database_path or default_notification_database_path())

    def load(self, user_id: str) -> NotificationSetting:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT user_id, app_enabled, ntfy_enabled, ntfy_server_url,
                           ntfy_topic, severity_threshold, quiet_hours_enabled,
                           quiet_hours_start, quiet_hours_end, updated_at
                    FROM notification_settings
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise NotificationSettingsError("Notification settings could not be loaded.") from exc
        if row is None:
            return NotificationSetting(user_id=user_id)
        try:
            return _setting_from_row(row)
        except (TypeError, ValueError) as exc:
            raise NotificationSettingsError("Notification settings could not be loaded.") from exc

    def save(self, setting: NotificationSetting) -> NotificationSetting:
        updated_at = datetime.now(UTC)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO notification_settings (
                        user_id, app_enabled, ntfy_enabled, ntfy_server_url,
                        ntfy_topic, severity_threshold, quiet_hours_enabled,
                        quiet_hours_start, quiet_hours_end, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        app_enabled = excluded.app_enabled,
                        ntfy_enabled = excluded.ntfy_enabled,
                        ntfy_server_url = excluded.ntfy_server_url,
                        ntfy_topic = excluded.ntfy_topic,
                        severity_threshold = excluded.severity_threshold,
                        quiet_hours_enabled = excluded.quiet_hours_enabled,
                        quiet_hours_start = excluded.quiet_hours_start,
                        quiet_hours_end = excluded.quiet_hours_end,
                        updated_at = excluded.updated_at
                    """,
                    (
                        setting.user_id,
                        int(setting.app_enabled),
                        int(setting.ntfy_enabled),
                        setting.ntfy_server_url,
                        setting.ntfy_topic,
                        setting.severity_threshold,
                        int(setting.quiet_hours_enabled),
                        setting.quiet_hours_start,
                        setting.quiet_hours_end,
                        updated_at.isoformat(),
                    ),
                )
        except (OSError, sqlite3.Error) as exc:
            raise NotificationSettingsError("Notification settings could not be saved.") from exc
        return NotificationSetting(
            user_id=setting.user_id,
            app_enabled=setting.app_enabled,
            ntfy_enabled=setting.ntfy_enabled,
            ntfy_server_url=setting.ntfy_server_url,
            ntfy_topic=setting.ntfy_topic,
            severity_threshold=setting.severity_threshold,
            quiet_hours_enabled=setting.quiet_hours_enabled,
            quiet_hours_start=setting.quiet_hours_start,
            quiet_hours_end=setting.quiet_hours_end,
            updated_at=updated_at,
        )

    def clear_topic(self, user_id: str) -> NotificationSetting:
        current = self.load(user_id)
        return self.save(
            NotificationSetting(
                user_id=current.user_id,
                app_enabled=current.app_enabled,
                ntfy_enabled=False,
                ntfy_server_url=current.ntfy_server_url,
                ntfy_topic=None,
                severity_threshold=current.severity_threshold,
                quiet_hours_enabled=current.quiet_hours_enabled,
                quiet_hours_start=current.quiet_hours_start,
                quiet_hours_end=current.quiet_hours_end,
            )
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        try:
            _ensure_schema(connection)
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    row = connection.execute(
        "SELECT value FROM notification_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is not None and int(row["value"]) > SCHEMA_VERSION:
        raise ValueError("Unsupported notification database schema.")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_settings (
            user_id TEXT PRIMARY KEY,
            app_enabled INTEGER NOT NULL,
            ntfy_enabled INTEGER NOT NULL,
            ntfy_server_url TEXT NOT NULL,
            ntfy_topic TEXT,
            severity_threshold TEXT NOT NULL,
            quiet_hours_enabled INTEGER NOT NULL,
            quiet_hours_start TEXT,
            quiet_hours_end TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO notification_meta (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(SCHEMA_VERSION),),
    )


def _setting_from_row(row: sqlite3.Row) -> NotificationSetting:
    threshold = str(row["severity_threshold"])
    if threshold not in {"critical", "high", "medium", "low", "silent"}:
        raise ValueError("Invalid notification severity.")
    return NotificationSetting(
        user_id=str(row["user_id"]),
        app_enabled=bool(row["app_enabled"]),
        ntfy_enabled=bool(row["ntfy_enabled"]),
        ntfy_server_url=str(row["ntfy_server_url"]),
        ntfy_topic=str(row["ntfy_topic"]) if row["ntfy_topic"] else None,
        severity_threshold=threshold,  # type: ignore[arg-type]
        quiet_hours_enabled=bool(row["quiet_hours_enabled"]),
        quiet_hours_start=(str(row["quiet_hours_start"]) if row["quiet_hours_start"] else None),
        quiet_hours_end=str(row["quiet_hours_end"]) if row["quiet_hours_end"] else None,
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )
