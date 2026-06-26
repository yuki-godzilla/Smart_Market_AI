from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

LOGGER = logging.getLogger(__name__)
FAVORITES_FILE_PATH = Path("data/user/favorites.json")


@dataclass(frozen=True)
class FavoriteStock:
    symbol: str
    name: str | None = None
    market: str | None = None
    asset_type: str | None = None
    currency: str | None = None
    source_screen: str | None = None
    added_at: str | None = None
    memo: str = ""
    tags: tuple[str, ...] = ()


def normalize_favorite_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def load_favorites(path: Path | None = None) -> list[FavoriteStock]:
    favorites_path = path or FAVORITES_FILE_PATH
    if not favorites_path.exists():
        return []
    try:
        payload = json.loads(favorites_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Failed to load favorites from %s: %s", favorites_path, exc)
        return []
    raw_favorites = payload.get("favorites", []) if isinstance(payload, dict) else []
    if not isinstance(raw_favorites, list):
        return []
    favorites: list[FavoriteStock] = []
    seen: set[str] = set()
    for raw_item in raw_favorites:
        if not isinstance(raw_item, Mapping):
            continue
        favorite = _favorite_from_mapping(raw_item)
        if favorite is None or favorite.symbol in seen:
            continue
        seen.add(favorite.symbol)
        favorites.append(favorite)
    return favorites


def save_favorites(favorites: list[FavoriteStock], path: Path | None = None) -> None:
    favorites_path = path or FAVORITES_FILE_PATH
    favorites_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"favorites": [_favorite_to_json_item(favorite) for favorite in favorites]}
    favorites_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def is_favorite(symbol: str) -> bool:
    normalized = normalize_favorite_symbol(symbol)
    if not normalized:
        return False
    return any(favorite.symbol == normalized for favorite in load_favorites())


def add_favorite(
    symbol: str,
    metadata: Mapping[str, Any] | None = None,
) -> FavoriteStock:
    normalized = normalize_favorite_symbol(symbol)
    if not normalized:
        raise ValueError("symbol is required")
    favorites = load_favorites()
    existing = next((favorite for favorite in favorites if favorite.symbol == normalized), None)
    if existing is not None:
        return existing
    favorite = _favorite_from_metadata(normalized, metadata or {})
    save_favorites([*favorites, favorite])
    return favorite


def remove_favorite(symbol: str) -> bool:
    normalized = normalize_favorite_symbol(symbol)
    if not normalized:
        return False
    favorites = load_favorites()
    remaining = [favorite for favorite in favorites if favorite.symbol != normalized]
    if len(remaining) == len(favorites):
        return False
    save_favorites(remaining)
    return True


def toggle_favorite(
    symbol: str,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    if is_favorite(symbol):
        remove_favorite(symbol)
        return False
    add_favorite(symbol, metadata=metadata)
    return True


def favorite_metadata_from_row(
    row: Mapping[str, Any] | None,
    *,
    source_screen: str,
) -> dict[str, Any]:
    row = row or {}
    return {
        "name": row.get("name") or row.get("銘柄名") or row.get("company_name"),
        "market": row.get("market") or row.get("市場"),
        "asset_type": row.get("asset_type") or row.get("商品"),
        "currency": row.get("currency") or row.get("通貨"),
        "source_screen": source_screen,
    }


def render_favorite_button(
    symbol: str,
    *,
    name: str | None = None,
    market: str | None = None,
    asset_type: str | None = None,
    currency: str | None = None,
    source_screen: str = "unknown",
    key: str | None = None,
    use_container_width: bool = True,
) -> bool:
    normalized = normalize_favorite_symbol(symbol)
    if not normalized:
        st.button(
            "お気に入り",
            key=key,
            disabled=True,
            use_container_width=use_container_width,
        )
        return False
    active = is_favorite(normalized)
    label = "★ お気に入り中" if active else "☆ お気に入り"
    clicked = st.button(
        label,
        key=key or f"favorite_{source_screen}_{normalized}",
        use_container_width=use_container_width,
        help="Myウォッチリストに追加・解除します。",
    )
    if clicked:
        now_active = toggle_favorite(
            normalized,
            metadata={
                "name": name,
                "market": market,
                "asset_type": asset_type,
                "currency": currency,
                "source_screen": source_screen,
            },
        )
        st.toast(
            "Myウォッチリストに追加しました。" if now_active else "Myウォッチリストから解除しました。"
        )
        st.rerun()
        return now_active
    return active


def _favorite_from_mapping(raw_item: Mapping[str, Any]) -> FavoriteStock | None:
    symbol = normalize_favorite_symbol(str(raw_item.get("symbol", "")))
    if not symbol:
        return None
    tags = raw_item.get("tags", [])
    if not isinstance(tags, list | tuple):
        tags = []
    return FavoriteStock(
        symbol=symbol,
        name=_optional_text(raw_item.get("name")),
        market=_optional_text(raw_item.get("market")),
        asset_type=_optional_text(raw_item.get("asset_type")),
        currency=_optional_text(raw_item.get("currency")),
        source_screen=_optional_text(raw_item.get("source_screen")),
        added_at=_optional_text(raw_item.get("added_at")),
        memo=str(raw_item.get("memo", "") or ""),
        tags=tuple(str(tag) for tag in tags if str(tag).strip()),
    )


def _favorite_from_metadata(symbol: str, metadata: Mapping[str, Any]) -> FavoriteStock:
    tags = metadata.get("tags", ())
    if not isinstance(tags, list | tuple):
        tags = ()
    return FavoriteStock(
        symbol=symbol,
        name=_optional_text(metadata.get("name")),
        market=_optional_text(metadata.get("market")),
        asset_type=_optional_text(metadata.get("asset_type")),
        currency=_optional_text(metadata.get("currency")),
        source_screen=_optional_text(metadata.get("source_screen")),
        added_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        memo=str(metadata.get("memo", "") or ""),
        tags=tuple(str(tag) for tag in tags if str(tag).strip()),
    )


def _favorite_to_json_item(favorite: FavoriteStock) -> dict[str, Any]:
    item = asdict(favorite)
    item["tags"] = list(favorite.tags)
    return item


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
