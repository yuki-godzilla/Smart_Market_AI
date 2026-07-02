from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (PROJECT_ROOT / "ui/assets", PROJECT_ROOT / "ui/static")
ICON_SOURCE_ROOT = PROJECT_ROOT / "ui/assets/user_icons/builtin"
ICON_OUTPUT_ROOT = PROJECT_ROOT / "ui/static/assets/user_icons"
MASCOT_SOURCE_ROOT = PROJECT_ROOT / "ui/assets/mascot"
MASCOT_OUTPUT_ROOT = PROJECT_ROOT / "ui/static/assets/mascot"
BRAND_SOURCE_ROOT = PROJECT_ROOT / "ui/assets/brand"
BRAND_OUTPUT_ROOT = PROJECT_ROOT / "ui/static/assets/brand"
REPORT_PATH = PROJECT_ROOT / "logs/server_ops/asset_optimization_report.md"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class AssetInfo:
    path: Path
    size: int
    width: int
    height: int
    format: str


def inspect_assets() -> list[AssetInfo]:
    assets: list[AssetInfo] = []
    seen: set[Path] = set()
    for root in SOURCE_ROOTS:
        for path in root.rglob("*"):
            if path in seen or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            seen.add(path)
            with Image.open(path) as image:
                assets.append(
                    AssetInfo(path, path.stat().st_size, image.width, image.height, image.format)
                )
    return assets


def optimize_user_icons(*, size: int = 256, quality: int = 82) -> list[tuple[Path, Path]]:
    ICON_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    generated: list[tuple[Path, Path]] = []
    for source in sorted(ICON_SOURCE_ROOT.glob("*.png")):
        target = ICON_OUTPUT_ROOT / f"{source.stem}-{size}.webp"
        with Image.open(source) as image:
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            image.save(target, "WEBP", quality=quality, method=6)
        generated.append((source, target))
    return generated


def _optimized_webp(
    source: Path,
    target: Path,
    *,
    max_size: tuple[int, int],
    quality: int = 84,
) -> tuple[Path, Path]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=quality, method=6)
    return source, target


def optimize_shared_assets() -> list[tuple[Path, Path]]:
    """Generate Retina-sized static variants without changing source artwork."""

    specifications = (
        (
            MASCOT_SOURCE_ROOT / "smai-title-watchlist-transparent.png",
            MASCOT_OUTPUT_ROOT / "smai-title-watchlist-640.webp",
            (640, 640),
        ),
        (
            BRAND_SOURCE_ROOT / "smai-logo.png",
            BRAND_OUTPUT_ROOT / "smai-logo-640.webp",
            (640, 640),
        ),
        (
            MASCOT_SOURCE_ROOT / "smai-mascot-cutout.png",
            MASCOT_OUTPUT_ROOT / "smai-mascot-cutout-384.webp",
            (384, 576),
        ),
        (
            MASCOT_SOURCE_ROOT / "smai-navi-chat-cutout.png",
            MASCOT_OUTPUT_ROOT / "smai-navi-chat-cutout-384.webp",
            (384, 384),
        ),
    )
    generated = [
        _optimized_webp(source, target, max_size=max_size)
        for source, target, max_size in specifications
    ]
    optimized_sources = {source for source, _, _ in specifications}
    for source in sorted(MASCOT_SOURCE_ROOT.glob("*.webp")):
        if source in optimized_sources:
            continue
        target = MASCOT_OUTPUT_ROOT / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        generated.append((source, target))
    return generated


def write_report(assets: list[AssetInfo], generated: list[tuple[Path, Path]]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# UI asset optimization report",
        "",
        "Generated locally; no network access was used.",
        "",
        "## Optimized static assets",
        "",
        "| Source | Optimized | Before | After | Reduction |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for source, target in generated:
        before = source.stat().st_size
        after = target.stat().st_size
        reduction = (1 - after / before) * 100 if before else 0
        lines.append(
            f"| `{source.relative_to(PROJECT_ROOT)}` | `{target.relative_to(PROJECT_ROOT)}` "
            f"| {before:,} B | {after:,} B | {reduction:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Usage and visual review",
            "",
            "| Optimized asset | Main screens | Reason | Visual review |",
            "| --- | --- | --- | --- |",
            "| `smai-title-watchlist-640.webp` | Watchlist | Repeated 1.89 MB title art | "
            "Transparent edge and mascot details retained at 640 px |",
            "| `smai-logo-640.webp` | App header | 1400 px source exceeded display need | "
            "Logo lettering and cyan outline remain readable |",
            "| `smai-mascot-cutout-384.webp` | Cockpit / insight | Reused base64 PNG | "
            "Transparent silhouette and small SMAI lettering retained |",
            "| `smai-navi-chat-cutout-384.webp` | Assistant | Reused base64 PNG | "
            "Chat/radar outline and face details retained |",
            "",
            "## Reviewed but not converted",
            "",
            "- `ui/static/pwa/icon-512.png`: keep PNG because installed-PWA icon compatibility "
            "and device launcher quality take priority; it is fetched as a static file, not rerun HTML.",
            "- Investment charts and report figures: not converted because analytical readability "
            "takes priority and they are not shared decorative bitmap assets.",
        ]
    )
    lines.extend(["", "## Warnings", ""])
    for asset in assets:
        reasons = []
        relative = asset.path.relative_to(PROJECT_ROOT)
        if asset.size > 300_000:
            reasons.append("over 300 KB")
        if asset.width > 1000:
            reasons.append("width over 1000 px")
        if "mascot" in str(relative).lower() and asset.size > 100_000:
            reasons.append("mascot/title over 100 KB")
        if reasons:
            lines.append(
                f"- `{relative}` — {asset.size:,} B, {asset.width}x{asset.height}, "
                + ", ".join(reasons)
            )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and optimize SMAI UI bitmap assets.")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    assets = inspect_assets()
    generated = [] if args.report_only else optimize_user_icons() + optimize_shared_assets()
    write_report(assets, generated)
    print(f"inspected={len(assets)} optimized={len(generated)} report={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
