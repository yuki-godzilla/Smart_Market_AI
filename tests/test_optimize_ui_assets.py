from pathlib import Path

from scripts.optimize_ui_assets import inspect_assets, optimize_user_icons


def test_asset_inspection_finds_large_user_icons() -> None:
    assets = inspect_assets()
    assert any("user_icons" in str(asset.path) and asset.size > 300_000 for asset in assets)


def test_optimized_user_icons_are_retina_sized_static_webp() -> None:
    generated = optimize_user_icons()

    assert len(generated) == 12
    for _, target in generated:
        assert target.parent == Path("ui/static/assets/user_icons").resolve()
        assert target.suffix == ".webp"
        assert target.stat().st_size < 100_000
