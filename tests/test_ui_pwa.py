from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from ui.pwa import PWA_HEAD_ELEMENTS, pwa_head_injection_html


def test_pwa_manifest_uses_streamlit_static_asset_paths() -> None:
    manifest = json.loads(Path("ui/static/pwa/manifest.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "Smart Market AI"
    assert manifest["short_name"] == "SMAI"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] == "#07111f"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
    assert all(icon["src"].startswith("/app/static/pwa/") for icon in manifest["icons"])


def test_pwa_head_injection_is_idempotent_and_includes_ios_metadata() -> None:
    markup = pwa_head_injection_html()

    assert "window.parent.document.head" in markup
    assert 'setAttribute("data-smai-pwa", "true")' in markup
    assert "apple-mobile-web-app-capable" in markup
    assert "apple-touch-icon-v2.png" in markup
    assert "apple-touch-icon-precomposed" in markup
    assert '"sizes": "180x180"' in markup
    assert "manifest.json" in markup
    assert {item["tag"] for item in PWA_HEAD_ELEMENTS} == {"meta", "link"}


def test_streamlit_static_serving_is_enabled() -> None:
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")

    assert "enableStaticServing = true" in config
    assert "enableWebsocketCompression = true" in config
    assert "disconnectedSessionTTL" not in config
    assert "websocketPingInterval" not in config
    assert "gatherUsageStats = false" in config
    assert 'toolbarMode = "viewer"' in config


def test_pwa_icons_exist_with_expected_square_dimensions() -> None:
    expected_sizes = {
        "icon-192.png": (192, 192),
        "icon-512.png": (512, 512),
        "apple-touch-icon.png": (180, 180),
        "apple-touch-icon-v2.png": (180, 180),
        "favicon.png": (64, 64),
    }

    for filename, expected_size in expected_sizes.items():
        with Image.open(Path("ui/static/pwa") / filename) as image:
            assert image.size == expected_size
            assert image.format == "PNG"


def test_pwa_assets_live_beside_the_streamlit_entrypoint() -> None:
    assert Path("ui/app.py").is_file()
    assert Path("ui/static/pwa/apple-touch-icon-v2.png").is_file()
    assert not Path("static/pwa/manifest.json").exists()
