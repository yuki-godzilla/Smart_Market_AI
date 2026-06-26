from __future__ import annotations

import html
import json
import logging
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

LOGGER = logging.getLogger(__name__)
FAVORITES_FILE_PATH = Path("data/user/favorites.json")
FAVORITE_REFRESH_STATUS_NEVER_CHECKED = "never_checked"
FAVORITE_REFRESH_STATUS_FRESH = "fresh"
FAVORITE_REFRESH_STATUS_STALE = "stale"
FAVORITE_REFRESH_STATUS_NEEDS_ATTENTION = "needs_attention"
FAVORITE_REFRESH_STATUS_FAILED = "failed"
FAVORITE_REFRESH_STATUS_PARTIAL = "partial"
FAVORITE_REFRESH_STATUS_UNKNOWN = "unknown"
FAVORITE_REFRESH_STATUS_VALUES = {
    FAVORITE_REFRESH_STATUS_NEVER_CHECKED,
    FAVORITE_REFRESH_STATUS_FRESH,
    FAVORITE_REFRESH_STATUS_STALE,
    FAVORITE_REFRESH_STATUS_NEEDS_ATTENTION,
    FAVORITE_REFRESH_STATUS_FAILED,
    FAVORITE_REFRESH_STATUS_PARTIAL,
    FAVORITE_REFRESH_STATUS_UNKNOWN,
}


@dataclass(frozen=True)
class FavoriteRefreshState:
    status: str
    label: str
    reason: str
    priority: int
    next_action: str


@dataclass(frozen=True)
class FavoriteStock:
    symbol: str
    name: str | None = None
    market: str | None = None
    asset_type: str | None = None
    currency: str | None = None
    source_screen: str | None = None
    added_at: str | None = None
    refresh_status: str | None = None
    refresh_error: str | None = None
    last_checked_at: str | None = None
    last_price_checked_at: str | None = None
    last_news_checked_at: str | None = None
    last_research_at: str | None = None
    last_research_hint_at: str | None = None
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


def favorite_symbols() -> list[str]:
    return [favorite.symbol for favorite in load_favorites()]


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


def update_favorite(
    symbol: str,
    *,
    memo: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    last_checked_at: str | None = None,
    last_research_at: str | None = None,
) -> FavoriteStock | None:
    normalized = normalize_favorite_symbol(symbol)
    if not normalized:
        return None
    favorites = load_favorites()
    updated: list[FavoriteStock] = []
    result: FavoriteStock | None = None
    for favorite in favorites:
        if favorite.symbol != normalized:
            updated.append(favorite)
            continue
        result = replace(
            favorite,
            memo=favorite.memo if memo is None else memo,
            tags=favorite.tags
            if tags is None
            else tuple(str(tag).strip() for tag in tags if str(tag).strip()),
            last_checked_at=favorite.last_checked_at
            if last_checked_at is None
            else last_checked_at,
            last_research_at=favorite.last_research_at
            if last_research_at is None
            else last_research_at,
        )
        updated.append(result)
    if result is None:
        return None
    save_favorites(updated)
    return result


def update_favorite_refresh_metadata(
    symbol: str,
    *,
    refresh_status: str | None = None,
    refresh_error: str | None = None,
    last_checked_at: str | None = None,
    last_price_checked_at: str | None = None,
    last_news_checked_at: str | None = None,
    last_research_hint_at: str | None = None,
) -> FavoriteStock | None:
    normalized = normalize_favorite_symbol(symbol)
    if not normalized:
        return None
    favorites = load_favorites()
    updated: list[FavoriteStock] = []
    result: FavoriteStock | None = None
    for favorite in favorites:
        if favorite.symbol != normalized:
            updated.append(favorite)
            continue
        result = replace(
            favorite,
            refresh_status=(
                favorite.refresh_status if refresh_status is None else refresh_status
            ),
            refresh_error=favorite.refresh_error
            if refresh_error is None
            else refresh_error[:240],
            last_checked_at=favorite.last_checked_at
            if last_checked_at is None
            else last_checked_at,
            last_price_checked_at=favorite.last_price_checked_at
            if last_price_checked_at is None
            else last_price_checked_at,
            last_news_checked_at=favorite.last_news_checked_at
            if last_news_checked_at is None
            else last_news_checked_at,
            last_research_hint_at=favorite.last_research_hint_at
            if last_research_hint_at is None
            else last_research_hint_at,
        )
        updated.append(result)
    if result is None:
        return None
    save_favorites(updated)
    return result


def evaluate_favorite_refresh_status(
    favorite: FavoriteStock,
    *,
    now: datetime | None = None,
    stale_after_hours: int = 24,
    news_stale_after_hours: int = 24,
    research_hint_stale_after_hours: int = 72,
) -> FavoriteRefreshState:
    current_time = now or datetime.now(UTC)
    explicit_status = (favorite.refresh_status or "").strip()
    if explicit_status == FAVORITE_REFRESH_STATUS_FAILED:
        return FavoriteRefreshState(
            status=FAVORITE_REFRESH_STATUS_FAILED,
            label="前回失敗",
            reason=favorite.refresh_error or "前回更新に失敗しました。",
            priority=100,
            next_action="前回失敗を再確認",
        )
    if explicit_status == FAVORITE_REFRESH_STATUS_PARTIAL:
        return FavoriteRefreshState(
            status=FAVORITE_REFRESH_STATUS_PARTIAL,
            label="一部更新",
            reason="前回は一部だけ更新されました。",
            priority=80,
            next_action="不足データを確認",
        )

    checked_at = _parse_datetime(favorite.last_checked_at)
    if checked_at is None:
        return FavoriteRefreshState(
            status=FAVORITE_REFRESH_STATUS_NEVER_CHECKED,
            label="未確認",
            reason="まだウォッチリスト上で確認されていません。",
            priority=90,
            next_action="初回データ確認",
        )
    if checked_at + timedelta(hours=stale_after_hours) < current_time:
        return FavoriteRefreshState(
            status=FAVORITE_REFRESH_STATUS_STALE,
            label="古い",
            reason="前回確認から時間が経っています。",
            priority=70,
            next_action="価格・ニュースを確認",
        )

    news_checked_at = _parse_datetime(favorite.last_news_checked_at)
    if news_checked_at is None or news_checked_at + timedelta(
        hours=news_stale_after_hours
    ) < current_time:
        return FavoriteRefreshState(
            status=FAVORITE_REFRESH_STATUS_NEEDS_ATTENTION,
            label="要確認",
            reason="ニュース確認が未実施または古くなっています。",
            priority=60,
            next_action="ニュースを確認",
        )

    research_hint_at = _parse_datetime(favorite.last_research_hint_at)
    if research_hint_at is None or research_hint_at + timedelta(
        hours=research_hint_stale_after_hours
    ) < current_time:
        return FavoriteRefreshState(
            status=FAVORITE_REFRESH_STATUS_NEEDS_ATTENTION,
            label="要確認",
            reason="AI調査の確認ヒントが未確認または古くなっています。",
            priority=50,
            next_action="AI調査の確認準備",
        )

    if explicit_status and explicit_status not in FAVORITE_REFRESH_STATUS_VALUES:
        return FavoriteRefreshState(
            status=FAVORITE_REFRESH_STATUS_UNKNOWN,
            label="判定保留",
            reason="更新状態を判定できませんでした。",
            priority=40,
            next_action="状態を確認",
        )
    return FavoriteRefreshState(
        status=FAVORITE_REFRESH_STATUS_FRESH,
        label="最新",
        reason="直近で確認されています。",
        priority=10,
        next_action="最新状態です",
    )


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
        st.markdown(
            '<span class="smai-favorite-button-anchor" data-active="false"></span>',
            unsafe_allow_html=True,
        )
        st.button(
            "☆ お気に入り",
            key=key,
            disabled=True,
            use_container_width=use_container_width,
        )
        return False
    active = is_favorite(normalized)
    label = "★ お気に入り中" if active else "☆ お気に入り"
    st.markdown(
        favorite_button_anchor_html(active=active, symbol=normalized),
        unsafe_allow_html=True,
    )
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


def favorite_button_anchor_html(*, active: bool, symbol: str) -> str:
    return (
        '<span class="smai-favorite-button-anchor" '
        f'data-active="{str(active).lower()}" '
        f'data-symbol="{html.escape(symbol)}"></span>'
    )


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
        refresh_status=_normalize_refresh_status(raw_item.get("refresh_status")),
        refresh_error=_optional_text(raw_item.get("refresh_error")),
        last_checked_at=_optional_text(raw_item.get("last_checked_at")),
        last_price_checked_at=_optional_text(raw_item.get("last_price_checked_at")),
        last_news_checked_at=_optional_text(raw_item.get("last_news_checked_at")),
        last_research_at=_optional_text(raw_item.get("last_research_at")),
        last_research_hint_at=_optional_text(raw_item.get("last_research_hint_at")),
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
        refresh_status=_normalize_refresh_status(metadata.get("refresh_status")),
        refresh_error=_optional_text(metadata.get("refresh_error")),
        last_checked_at=_optional_text(metadata.get("last_checked_at")),
        last_price_checked_at=_optional_text(metadata.get("last_price_checked_at")),
        last_news_checked_at=_optional_text(metadata.get("last_news_checked_at")),
        last_research_at=_optional_text(metadata.get("last_research_at")),
        last_research_hint_at=_optional_text(metadata.get("last_research_hint_at")),
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


def _normalize_refresh_status(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    return text if text in FAVORITE_REFRESH_STATUS_VALUES else FAVORITE_REFRESH_STATUS_UNKNOWN


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
