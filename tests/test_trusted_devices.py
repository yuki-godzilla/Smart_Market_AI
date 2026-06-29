from uuid import uuid4

from backend.notifications.trusted_devices import (
    TrustedDeviceRepository,
    normalize_device_id,
)
from ui.notification_center import trusted_device_bootstrap_html


def test_trusted_device_bind_resolve_revoke_and_mascot(tmp_path) -> None:
    repository = TrustedDeviceRepository(str(tmp_path / "notifications.sqlite"))
    device_id = str(uuid4())

    repository.trust(device_id, "local_user", "Windows Chrome")
    resolved = repository.resolve(device_id)
    assert resolved is not None
    assert resolved.display_name == "Yuki"
    assert repository.list("local_user")[0].device_name == "Windows Chrome"
    repository.rename("local_user", device_id, "Desk PC")
    assert repository.list("local_user")[0].device_name == "Desk PC"
    repository.set_icon("local_user", "smai_pet_cat")
    users = repository.users()
    local_user = next(user for user in users if user.user_id == "local_user")
    default_user = next(user for user in users if user.user_id == "default")
    assert local_user.icon_id == "smai_pet_cat"
    assert default_user.display_name == "SMAIデフォルト"
    assert default_user.icon_id == "smai_navi_default"
    assert default_user.is_system_user is True
    assert default_user.deletable is False
    repository.revoke("local_user", device_id)
    assert repository.resolve(device_id) is None


def test_device_id_validation_and_browser_bridge() -> None:
    assert normalize_device_id("not-a-uuid") is None
    html = trusted_device_bootstrap_html()
    assert "localStorage" in html
    assert "crypto.randomUUID" in html
    assert "smai_device_id" in html
    assert "navigator.userAgent" in html
    assert "location.replace" in html
    assert "clientIP" not in html
