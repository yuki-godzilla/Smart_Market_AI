from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (PROJECT_ROOT / "ui/assets", PROJECT_ROOT / "ui/static")
ICON_SOURCE_ROOT = PROJECT_ROOT / "ui/assets/user_icons/builtin"
ICON_OUTPUT_ROOT = PROJECT_ROOT / "ui/static/assets/user_icons"
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


def write_report(assets: list[AssetInfo], generated: list[tuple[Path, Path]]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# UI asset optimization report",
        "",
        "Generated locally; no network access was used.",
        "",
        "## Optimized user icons",
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
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and optimize SMAI UI bitmap assets.")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    assets = inspect_assets()
    generated = [] if args.report_only else optimize_user_icons()
    write_report(assets, generated)
    print(f"inspected={len(assets)} optimized={len(generated)} report={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
