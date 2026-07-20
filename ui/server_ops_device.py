"""Privacy-safe browser device identity for local operations telemetry."""

from __future__ import annotations

import html
from typing import Any, Mapping
from uuid import UUID

DEVICE_QUERY_KEY = "smai_ops_device"
DEVICE_STORAGE_KEY = "smai_ops_device_id"


def normalize_device_id(value: object) -> str:
    """Return only canonical random UUIDs suitable for local aggregation."""

    try:
        parsed = UUID(str(value or "").strip())
    except (TypeError, ValueError, AttributeError):
        return ""
    return str(parsed) if parsed.version == 4 else ""


def device_id_from_query(params: Mapping[str, Any] | None) -> str:
    if params is None:
        return ""
    try:
        value = params.get(DEVICE_QUERY_KEY)
    except AttributeError:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return normalize_device_id(value)


def device_identity_bridge_html() -> str:
    """Keep one random ID per browser profile and reflect it in the local URL.

    The identifier is generated in same-origin browser storage.  It is not a
    user ID, fingerprint, IP address, cookie value, or external identifier.
    Streamlit receives it only through the local app URL so a heartbeat can
    group multiple tabs opened from the same browser profile.
    """

    query_key = html.escape(DEVICE_QUERY_KEY, quote=True)
    storage_key = html.escape(DEVICE_STORAGE_KEY, quote=True)
    return f"""
<script>
(() => {{
  const queryKey = "{query_key}";
  const storageKey = "{storage_key}";
  const uuidV4 = /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-4[0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/i;
  try {{
    const parentWindow = window.parent;
    let deviceId = parentWindow.localStorage.getItem(storageKey) || "";
    if (!uuidV4.test(deviceId)) {{
      deviceId = parentWindow.crypto.randomUUID();
      parentWindow.localStorage.setItem(storageKey, deviceId);
    }}
    const url = new URL(parentWindow.location.href);
    if (url.searchParams.get(queryKey) !== deviceId) {{
      url.searchParams.set(queryKey, deviceId);
      parentWindow.location.replace(url.toString());
    }}
  }} catch (_error) {{
    // Operations monitoring remains available as session-only evidence when
    // browser storage is unavailable or intentionally disabled.
  }}
}})();
</script>
"""
