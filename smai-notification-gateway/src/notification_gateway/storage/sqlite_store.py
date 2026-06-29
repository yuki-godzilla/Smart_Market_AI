from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from notification_gateway.models import DeliveryResult


@dataclass(slots=True)
class SQLiteDeliveryStore:
    """Phase N1 storage boundary; persistence is implemented in a later phase."""

    database_path: Path

    def save_delivery_result(self, result: DeliveryResult) -> None:
        raise NotImplementedError("SQLite delivery persistence is not implemented in Phase N1.")
