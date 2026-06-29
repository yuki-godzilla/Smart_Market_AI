from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from notification_gateway.models import DeliveryResult, NotificationEvent


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int


class HttpTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        data: bytes,
        headers: Mapping[str, str],
        timeout: float,
    ) -> HttpResponse: ...


class NotificationChannel(Protocol):
    name: str

    def send(self, event: NotificationEvent, *, server_url: str, topic: str) -> DeliveryResult:
        ...
