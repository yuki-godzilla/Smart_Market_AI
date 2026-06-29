import json

from ui.user_icon_assets import (
    load_user_icon_assets,
    resolve_user_icon,
    user_icon_browser_source,
)


def test_manifest_controls_enabled_existing_assets(tmp_path) -> None:
    existing = tmp_path / "icon.png"
    existing.write_bytes(b"image")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "icons": [
                    {
                        "icon_id": "outside_test",
                        "display_name": "Outside",
                        "file_path": str(existing),
                        "enabled": True,
                    },
                    {
                        "icon_id": "disabled",
                        "display_name": "Disabled",
                        "file_path": "ui/static/pwa/icon-192.png",
                        "enabled": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert load_user_icon_assets(manifest) == ()


def test_broken_manifest_uses_safe_local_fallback(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{broken", encoding="utf-8")

    resolved = resolve_user_icon("missing", manifest_path=manifest)

    assert resolved.fallback_level in {"placeholder", "silhouette"}
    source = user_icon_browser_source(resolved)
    if resolved.fallback_level == "placeholder":
        assert source is not None and source.startswith("data:image/webp;base64,")
