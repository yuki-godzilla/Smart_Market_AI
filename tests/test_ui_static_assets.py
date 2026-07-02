from pathlib import Path

from PIL import Image


def test_optimized_decorative_assets_exist_without_replacing_sources() -> None:
    pairs = (
        (
            "ui/assets/mascot/smai-title-watchlist-transparent.png",
            "ui/static/assets/mascot/smai-title-watchlist-640.webp",
        ),
        (
            "ui/assets/brand/smai-logo.png",
            "ui/static/assets/brand/smai-logo-640.webp",
        ),
        (
            "ui/assets/mascot/smai-mascot-cutout.png",
            "ui/static/assets/mascot/smai-mascot-cutout-384.webp",
        ),
        (
            "ui/assets/mascot/smai-navi-chat-cutout.png",
            "ui/static/assets/mascot/smai-navi-chat-cutout-384.webp",
        ),
    )
    for source_name, optimized_name in pairs:
        source = Path(source_name)
        optimized = Path(optimized_name)
        assert source.is_file()
        assert optimized.is_file()
        assert optimized.stat().st_size < source.stat().st_size
        with Image.open(optimized) as image:
            assert image.format == "WEBP"


def test_mascot_component_has_no_bitmap_base64_encoder() -> None:
    source = Path("ui/components/mascot.py").read_text(encoding="utf-8")
    assert "base64.b64encode" not in source
    assert "/app/static/assets/" in source
