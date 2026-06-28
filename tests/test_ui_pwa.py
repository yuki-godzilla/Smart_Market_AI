from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from ui.pwa import PWA_HEAD_ELEMENTS, pwa_head_injection_html


def test_pwa_manifest_uses_streamlit_static_asset_paths() -> None:
    manifest = json.loads(Path("static/pwa/manifest.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "Smart Market AI"
    assert manifest["short_name"] == "SMAI"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] == "#07111f"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}
    assert all(icon["src"].startswith("/app/static/pwa/") for icon in manifest["icons"])


def test_pwa_head_injection_is_idempotent_and_includes_ios_metadata() -> None:
    markup = pwa_head_injection_html()

    assert "window.parent.document.head" in markup
    assert 'data-smai-pwa="true"' in markup
    assert "apple-mobile-web-app-capable" in markup
    assert "apple-touch-icon.png" in markup
    assert "manifest.json" in markup
    assert {item["tag"] for item in PWA_HEAD_ELEMENTS} == {"meta", "link"}


def test_streamlit_static_serving_is_enabled() -> None:
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")

    assert "enableStaticServing = true" in config


def test_pwa_icons_exist_with_expected_square_dimensions() -> None:
    expected_sizes = {
        "icon-192.png": (192, 192),
        "icon-512.png": (512, 512),
        "apple-touch-icon.png": (180, 180),
        "favicon.png": (64, 64),
    }

    for filename, expected_size in expected_sizes.items():
        with Image.open(Path("static/pwa") / filename) as image:
            assert image.size == expected_size
            assert image.format == "PNG"
