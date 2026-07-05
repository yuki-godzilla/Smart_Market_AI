from __future__ import annotations


def upward_signal_display_label(value: object) -> str:
    """Normalize labels saved before the public-name migration."""

    legacy_label = "反転" + "期待"
    return str(value or "").replace(legacy_label, "上向き兆候")
