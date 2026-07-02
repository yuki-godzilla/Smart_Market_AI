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


def test_builtin_manifest_registers_twelve_repository_assets() -> None:
    assets = load_user_icon_assets()

    assert len(assets) == 12
    assert assets[0].asset_id == "smai_navi_default"
    assert all(asset.file_path.is_file() for asset in assets)
    assert {asset.category for asset in assets} == {"navi", "pet"}
    assert resolve_user_icon("missing").icon_id == "smai_navi_default"


def test_builtin_icons_use_lightweight_static_webp_urls() -> None:
    resolved = resolve_user_icon("smai_navi_default")
    source = user_icon_browser_source(resolved)

    assert source == "/app/static/assets/user_icons/smai_navi_default-256.webp"
    assert resolved.file_path is not None
    assert resolved.file_path.stat().st_size < 100_000
