from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

from backend.notifications.delivery import configured_notification_client
from backend.notifications.history_repository import NotificationHistoryRepository
from backend.notifications.live_data import CachedNotificationDataSource
from backend.notifications.producer import CatalogNotificationProducer
from backend.notifications.scheduler import NotificationScheduler, NotificationScheduleRepository
from backend.notifications.settings_repository import NotificationSettingsRepository
from backend.notifications.trusted_devices import TrustedDeviceRepository


def run_once(
    database_path: str | None = None,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> int:
    settings = NotificationSettingsRepository(database_path)
    history = NotificationHistoryRepository(str(settings.database_path))
    schedules = NotificationScheduleRepository(str(settings.database_path))
    users = [
        user.user_id
        for user in TrustedDeviceRepository(str(settings.database_path)).users()
        if not user.is_system_user
    ]
    scheduler = NotificationScheduler(
        schedules,
        CatalogNotificationProducer(history, settings),
        client_factory=lambda user_id: configured_notification_client(settings, user_id),
        data_source=CachedNotificationDataSource(),
    )
    if dry_run:
        previews = scheduler.preview_due(users, now=now)
        print(
            json.dumps(
                [
                    {
                        "job_id": item.job_id,
                        "user_id": item.user_id,
                        "template_id": item.template_id,
                        "scheduled_slot": item.scheduled_slot,
                        "status": item.status,
                        "reason": item.reason,
                    }
                    for item in previews
                ],
                ensure_ascii=False,
            )
        )
        return 0
    return scheduler.run_due(users, now=now)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SMAI notification schedules.")
    parser.add_argument("--once", action="store_true", help="Check due jobs once and exit.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate due jobs without notification history, run-log, or delivery writes.",
    )
    parser.add_argument("--interval", type=int, default=30, help="Polling seconds in loop mode.")
    args = parser.parse_args()
    if args.once or args.dry_run:
        if args.dry_run:
            return run_once(dry_run=True)
        print(f"created={run_once()}")
        return 0
    interval = max(10, args.interval)
    try:
        while True:
            print(f"created={run_once()}", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
