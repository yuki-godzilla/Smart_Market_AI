from __future__ import annotations

import argparse
import time

from backend.notifications.gateway_adapter import (
    GatewayNotificationSettings,
    NotificationGatewayAdapter,
)
from backend.notifications.history_repository import NotificationHistoryRepository
from backend.notifications.producer import CatalogNotificationProducer
from backend.notifications.scheduler import NotificationScheduler, NotificationScheduleRepository
from backend.notifications.settings_repository import NotificationSettingsRepository
from backend.notifications.trusted_devices import TrustedDeviceRepository


def run_once(database_path: str | None = None) -> int:
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
        client_factory=lambda user_id: _client_for_user(settings, user_id),
    )
    return scheduler.run_due(users)


def _client_for_user(
    repository: NotificationSettingsRepository, user_id: str
) -> NotificationGatewayAdapter | None:
    setting = repository.load(user_id)
    if not setting.ntfy_enabled or not setting.ntfy_topic:
        return None
    return NotificationGatewayAdapter(
        GatewayNotificationSettings(
            ntfy_enabled=setting.ntfy_enabled,
            ntfy_server_url=setting.ntfy_server_url,
            ntfy_topic=setting.ntfy_topic,
            severity_threshold=setting.severity_threshold,
            quiet_hours_enabled=setting.quiet_hours_enabled,
            quiet_hours_start=setting.quiet_hours_start,
            quiet_hours_end=setting.quiet_hours_end,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SMAI notification schedules.")
    parser.add_argument("--once", action="store_true", help="Check due jobs once and exit.")
    parser.add_argument("--interval", type=int, default=30, help="Polling seconds in loop mode.")
    args = parser.parse_args()
    if args.once:
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
