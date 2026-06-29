from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from backend.notifications.catalog import NOTIFICATION_TEMPLATES
from backend.notifications.notification_client import NotificationClient
from backend.notifications.producer import CatalogNotificationProducer
from backend.notifications.settings_repository import (
    NotificationSettingsError,
    NotificationSettingsRepository,
)


@dataclass(frozen=True, slots=True)
class NotificationScheduleSetting:
    user_id: str
    enabled: bool = False
    favorite_daily_time: str = "07:30"
    investment_news_time: str = "08:00"
    sector_momentum_time: str = "08:30"
    favorite_move_interval_minutes: int = 15
    favorite_news_interval_minutes: int = 60
    weekdays_only: bool = True


@dataclass(frozen=True, slots=True)
class NotificationRunLog:
    job_id: str
    user_id: str
    scheduled_slot: str
    status: str
    reason: str
    created_at: datetime


class NotificationScheduleRepository:
    def __init__(self, database_path: str | None = None) -> None:
        settings = NotificationSettingsRepository(database_path)
        settings.load("local_user")
        self.database_path = settings.database_path
        self._ensure_schema()

    def load(self, user_id: str) -> NotificationScheduleSetting:
        self._ensure_schema()
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """SELECT user_id, enabled, favorite_daily_time, investment_news_time,
                sector_momentum_time, favorite_move_interval_minutes,
                favorite_news_interval_minutes, weekdays_only
                FROM notification_schedule_settings WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
        if row is None:
            return NotificationScheduleSetting(user_id)
        return NotificationScheduleSetting(
            row[0], bool(row[1]), row[2], row[3], row[4], int(row[5]), int(row[6]), bool(row[7])
        )

    def save(self, setting: NotificationScheduleSetting) -> None:
        self._ensure_schema()
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """INSERT INTO notification_schedule_settings VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,
                favorite_daily_time=excluded.favorite_daily_time,
                investment_news_time=excluded.investment_news_time,
                sector_momentum_time=excluded.sector_momentum_time,
                favorite_move_interval_minutes=excluded.favorite_move_interval_minutes,
                favorite_news_interval_minutes=excluded.favorite_news_interval_minutes,
                weekdays_only=excluded.weekdays_only""",
                (
                    setting.user_id,
                    int(setting.enabled),
                    setting.favorite_daily_time,
                    setting.investment_news_time,
                    setting.sector_momentum_time,
                    setting.favorite_move_interval_minutes,
                    setting.favorite_news_interval_minutes,
                    int(setting.weekdays_only),
                ),
            )

    def claim(self, job_id: str, user_id: str, slot: str) -> bool:
        self._ensure_schema()
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO notification_run_logs
                (job_id, user_id, scheduled_slot, status, reason, created_at)
                VALUES (?, ?, ?, 'running', '', ?)""",
                (job_id, user_id, slot, datetime.now(UTC).isoformat()),
            )
        return cursor.rowcount == 1

    def finish(self, job_id: str, user_id: str, slot: str, status: str, reason: str) -> None:
        safe_reason = reason[:160].replace("http", "[redacted]")
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """UPDATE notification_run_logs SET status = ?, reason = ?
                WHERE job_id = ? AND user_id = ? AND scheduled_slot = ?""",
                (status, safe_reason, job_id, user_id, slot),
            )

    def logs(self, user_id: str) -> list[NotificationRunLog]:
        self._ensure_schema()
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                """SELECT job_id, user_id, scheduled_slot, status, reason, created_at
                FROM notification_run_logs WHERE user_id = ? ORDER BY created_at DESC""",
                (user_id,),
            ).fetchall()
        return [
            NotificationRunLog(
                row[0], row[1], row[2], row[3], row[4], datetime.fromisoformat(row[5])
            )
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS notification_schedule_settings (
                    user_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL,
                    favorite_daily_time TEXT NOT NULL, investment_news_time TEXT NOT NULL,
                    sector_momentum_time TEXT NOT NULL,
                    favorite_move_interval_minutes INTEGER NOT NULL,
                    favorite_news_interval_minutes INTEGER NOT NULL,
                    weekdays_only INTEGER NOT NULL)"""
                )
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS notification_run_logs (
                    job_id TEXT NOT NULL, user_id TEXT NOT NULL, scheduled_slot TEXT NOT NULL,
                    status TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(job_id, user_id, scheduled_slot))"""
                )
        except sqlite3.Error as exc:
            raise NotificationSettingsError("Notification schedule is unavailable.") from exc


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    job_id: str
    template_id: str
    schedule_field: str


SCHEDULED_JOBS = (
    ScheduledJob("favorite_daily", "favorite_daily_report", "favorite_daily_time"),
    ScheduledJob("investment_news", "investment_news_digest", "investment_news_time"),
    ScheduledJob("sector_momentum", "sector_momentum_digest", "sector_momentum_time"),
    ScheduledJob("favorite_move", "favorite_move_alert", "favorite_move_interval_minutes"),
    ScheduledJob("favorite_news", "favorite_news_digest", "favorite_news_interval_minutes"),
)


class NotificationScheduler:
    def __init__(
        self,
        schedules: NotificationScheduleRepository,
        producer: CatalogNotificationProducer,
        client_factory: Callable[[str], NotificationClient | None] | None = None,
    ) -> None:
        self.schedules = schedules
        self.producer = producer
        self.client_factory = client_factory

    def run_due(self, user_ids: list[str], *, now: datetime | None = None) -> int:
        current = now or datetime.now().astimezone()
        produced = 0
        for user_id in user_ids:
            setting = self.schedules.load(user_id)
            if not setting.enabled or (setting.weekdays_only and current.weekday() >= 5):
                continue
            for job in SCHEDULED_JOBS:
                schedule_value = getattr(setting, job.schedule_field)
                if job.schedule_field.endswith("_minutes"):
                    interval = max(1, int(schedule_value))
                    if current.minute % interval != 0:
                        continue
                    if job.job_id == "favorite_move" and not (9 <= current.hour <= 15):
                        continue
                elif schedule_value != current.strftime("%H:%M"):
                    continue
                slot = current.strftime("%Y-%m-%dT%H:%M")
                if not self.schedules.claim(job.job_id, user_id, slot):
                    continue
                try:
                    item = self.producer.produce(
                        job.template_id,
                        user_id=user_id,
                        dedupe_key=f"{job.template_id}:{user_id}:{slot}",
                        now=current.astimezone(UTC),
                        client=self.client_factory(user_id) if self.client_factory else None,
                    )
                except Exception:
                    self.schedules.finish(job.job_id, user_id, slot, "failed", "job_error")
                    continue
                status = "created" if item else "skipped"
                self.schedules.finish(job.job_id, user_id, slot, status, "ok")
                produced += int(item is not None)
        return produced


def registered_template_ids() -> tuple[str, ...]:
    return tuple(template.template_id for template in NOTIFICATION_TEMPLATES)
