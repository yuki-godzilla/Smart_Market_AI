from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
USER_ICON_MANIFEST_PATH = PROJECT_ROOT / "ui/assets/user_icons/manifest.json"
DEFAULT_ICON_ID = "smai_navi_default"
PLACEHOLDER_PATH = PROJECT_ROOT / "ui/assets/mascot/smai-mascot-thumb.webp"


@dataclass(frozen=True, slots=True)
class UserIconAsset:
    asset_id: str
    display_name: str
    file_path: Path
    public_path: str | None
    category: str
    role: str
    background_color_hint: str
    is_builtin: bool

    @property
    def icon_id(self) -> str:
        """Compatibility alias while persisted values move to icon_asset_id wording."""
        return self.asset_id


@dataclass(frozen=True, slots=True)
class ResolvedUserIcon:
    icon_id: str
    display_name: str
    file_path: Path | None
    public_path: str | None
    fallback_level: str


def load_user_icon_assets(
    manifest_path: Path | None = None,
) -> tuple[UserIconAsset, ...]:
    path = manifest_path or USER_ICON_MANIFEST_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    icons = payload.get("icons") if isinstance(payload, dict) else None
    if not isinstance(icons, list):
        return ()
    results: list[UserIconAsset] = []
    seen: set[str] = set()
    for raw in icons:
        if not isinstance(raw, dict) or raw.get("enabled") is not True:
            continue
        asset = _asset_from_mapping(raw)
        if asset is None or asset.icon_id in seen or not asset.file_path.is_file():
            continue
        seen.add(asset.icon_id)
        results.append(asset)
    return tuple(results)


def resolve_user_icon(
    icon_id: str | None,
    *,
    manifest_path: Path | None = None,
) -> ResolvedUserIcon:
    assets = load_user_icon_assets(manifest_path)
    selected = next((asset for asset in assets if asset.icon_id == icon_id), None)
    if selected is not None:
        return _resolved(selected, "selected")
    default = next((asset for asset in assets if asset.icon_id == DEFAULT_ICON_ID), None)
    if default is not None:
        return _resolved(default, "default")
    if PLACEHOLDER_PATH.is_file():
        return ResolvedUserIcon(
            icon_id="local_placeholder",
            display_name="SMAI placeholder",
            file_path=PLACEHOLDER_PATH,
            public_path=None,
            fallback_level="placeholder",
        )
    return ResolvedUserIcon(
        icon_id="css_silhouette",
        display_name="ユーザー",
        file_path=None,
        public_path=None,
        fallback_level="silhouette",
    )


def user_icon_browser_source(icon: ResolvedUserIcon) -> str | None:
    if icon.public_path:
        return icon.public_path
    if icon.file_path is None:
        return None
    suffix = icon.file_path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix)
    if not mime:
        return None
    try:
        payload = icon.file_path.read_bytes()
    except OSError:
        return None
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"


def _asset_from_mapping(raw: dict[str, Any]) -> UserIconAsset | None:
    icon_id = str(raw.get("asset_id", raw.get("icon_id", ""))).strip()
    display_name = str(raw.get("display_name", "")).strip()
    raw_file_path = str(raw.get("file_path", "")).strip()
    if not icon_id or not display_name or not raw_file_path:
        return None
    file_path = (PROJECT_ROOT / raw_file_path).resolve()
    if not file_path.is_relative_to(PROJECT_ROOT):
        return None
    public_path = raw.get("public_path")
    return UserIconAsset(
        asset_id=icon_id,
        display_name=display_name,
        file_path=file_path,
        public_path=str(public_path) if public_path else None,
        category=str(raw.get("category", "default")),
        role=str(raw.get("role", "custom_user")),
        background_color_hint=str(raw.get("background_color_hint", "cyan")),
        is_builtin=bool(raw.get("is_builtin", True)),
    )


def _resolved(asset: UserIconAsset, fallback_level: str) -> ResolvedUserIcon:
    return ResolvedUserIcon(
        icon_id=asset.icon_id,
        display_name=asset.display_name,
        file_path=asset.file_path,
        public_path=asset.public_path,
        fallback_level=fallback_level,
    )
