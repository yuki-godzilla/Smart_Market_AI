from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, cast

from backend.notifications.notification_client import (
    NotificationClientResult,
    NotificationDeliveryStatus,
    NotificationRequest,
    NotificationSeverity,
)

_DELIVERY_STATUSES = {"skipped", "disabled", "filtered", "sent", "failed"}


@dataclass(frozen=True, slots=True)
class GatewayNotificationSettings:
    """Minimal non-persistent settings needed by the Phase N3-A adapter."""

    ntfy_enabled: bool = False
    ntfy_server_url: str = "https://ntfy.sh"
    ntfy_topic: str | None = None
    severity_threshold: NotificationSeverity = "medium"
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None

    def __post_init__(self) -> None:
        if not self.ntfy_server_url.strip():
            raise ValueError("ntfy_server_url must not be blank")
        if self.quiet_hours_enabled and (not self.quiet_hours_start or not self.quiet_hours_end):
            raise ValueError("quiet hour start and end are required when enabled")


class GatewayDispatcher(Protocol):
    def dispatch_ntfy(self, event: object, setting: object) -> object:
        """Dispatch one converted event."""


@dataclass(frozen=True, slots=True)
class GatewayBindings:
    """Late-bound child gateway constructors used by the parent adapter."""

    event_factory: Callable[..., object]
    setting_factory: Callable[..., object]
    category_factory: Callable[[str], object]
    severity_factory: Callable[[str], object]
    dispatcher_factory: Callable[[], GatewayDispatcher]


GatewayBindingsLoader = Callable[[], GatewayBindings]


class NotificationGatewayAdapter:
    """Convert parent contracts to child gateway contracts without import coupling."""

    def __init__(
        self,
        settings: GatewayNotificationSettings,
        *,
        bindings_loader: GatewayBindingsLoader | None = None,
    ) -> None:
        self._settings = settings
        self._bindings_loader = bindings_loader or load_notification_gateway_bindings

    def send(self, request: NotificationRequest) -> NotificationClientResult:
        if request.user_id == "default":
            return NotificationClientResult(
                event_id=request.event_id,
                status="skipped",
                success=False,
                reason="default_user_notifications_disabled",
            )
        try:
            bindings = self._bindings_loader()
        except (ImportError, ModuleNotFoundError):
            return _failed(
                request,
                reason="gateway_unavailable",
                message="Notification gateway is unavailable.",
            )
        except Exception:
            return _failed(
                request,
                reason="gateway_load_error",
                message="Notification gateway could not be loaded.",
            )

        try:
            event = bindings.event_factory(
                event_id=request.event_id,
                user_id=request.user_id,
                event_type=request.event_type,
                category=bindings.category_factory(request.category),
                severity=bindings.severity_factory(request.severity),
                title=request.title,
                message=request.message,
                symbol=request.symbol,
                source=request.source,
                action_url=request.action_url,
                metadata=dict(request.metadata),
                created_at=request.created_at,
            )
            setting = bindings.setting_factory(
                user_id=request.user_id,
                ntfy_enabled=self._settings.ntfy_enabled,
                ntfy_server_url=self._settings.ntfy_server_url,
                ntfy_topic=self._settings.ntfy_topic,
                severity_threshold=bindings.severity_factory(self._settings.severity_threshold),
                quiet_hours_enabled=self._settings.quiet_hours_enabled,
                quiet_hours_start=self._settings.quiet_hours_start,
                quiet_hours_end=self._settings.quiet_hours_end,
            )
            gateway_result = bindings.dispatcher_factory().dispatch_ntfy(event, setting)
            return _convert_gateway_result(request, gateway_result)
        except Exception:
            return _failed(
                request,
                reason="gateway_error",
                message="Notification gateway failed.",
            )


def load_notification_gateway_bindings() -> GatewayBindings:
    """Load the independently packaged child gateway only when first used."""

    _ensure_local_gateway_import_path()
    channels = importlib.import_module("notification_gateway.channels")
    dispatcher_module = importlib.import_module("notification_gateway.dispatcher")
    models = importlib.import_module("notification_gateway.models")

    def dispatcher_factory() -> GatewayDispatcher:
        transport = channels.UrllibHttpTransport()
        channel = channels.NtfyChannel(transport)
        return cast(
            GatewayDispatcher,
            dispatcher_module.NotificationDispatcher(channel),
        )

    return GatewayBindings(
        event_factory=models.NotificationEvent,
        setting_factory=models.UserNotificationSetting,
        category_factory=models.NotificationCategory,
        severity_factory=models.Severity,
        dispatcher_factory=dispatcher_factory,
    )


def _ensure_local_gateway_import_path() -> None:
    """Expose the checked-out child package without requiring editable install."""

    try:
        importlib.import_module("notification_gateway")
        return
    except ModuleNotFoundError as exc:
        if exc.name != "notification_gateway":
            raise

    child_src = Path(__file__).resolve().parents[2] / "smai-notification-gateway" / "src"
    if not (child_src / "notification_gateway" / "__init__.py").is_file():
        raise ModuleNotFoundError("notification_gateway")
    child_src_value = str(child_src)
    if child_src_value not in sys.path:
        sys.path.insert(0, child_src_value)
    importlib.invalidate_caches()


def _convert_gateway_result(
    request: NotificationRequest,
    gateway_result: object,
) -> NotificationClientResult:
    event_id = str(_attribute(gateway_result, "event_id"))
    if event_id != request.event_id:
        return _failed(
            request,
            reason="invalid_response",
            message="Notification gateway returned an invalid response.",
        )

    status_value = _enum_value(_attribute(gateway_result, "status"))
    if status_value not in _DELIVERY_STATUSES:
        return _failed(
            request,
            reason="invalid_response",
            message="Notification gateway returned an invalid response.",
        )
    status = cast(NotificationDeliveryStatus, status_value)
    reason = _enum_value(_attribute(gateway_result, "reason"))
    channel = str(_attribute(gateway_result, "channel"))
    status_code_value = getattr(gateway_result, "status_code", None)
    status_code = status_code_value if isinstance(status_code_value, int) else None

    if status == "failed":
        return NotificationClientResult(
            event_id=request.event_id,
            channel=channel,
            status="failed",
            success=False,
            reason=reason,
            status_code=status_code,
            error_message="Notification delivery failed.",
        )
    return NotificationClientResult(
        event_id=request.event_id,
        channel=channel,
        status=status,
        success=status == "sent",
        reason=reason,
        status_code=status_code,
    )


def _attribute(value: object, name: str) -> Any:
    try:
        return getattr(value, name)
    except AttributeError as exc:
        raise ValueError("gateway response is missing a required field") from exc


def _enum_value(value: object) -> str:
    raw_value = getattr(value, "value", value)
    return str(raw_value)


def _failed(
    request: NotificationRequest,
    *,
    reason: str,
    message: str,
) -> NotificationClientResult:
    return NotificationClientResult(
        event_id=request.event_id,
        status="failed",
        success=False,
        reason=reason,
        error_message=message,
    )
