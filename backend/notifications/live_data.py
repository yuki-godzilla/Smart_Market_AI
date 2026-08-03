"""Read-only N6 inputs for notification schedules.

The notification scheduler runs outside Streamlit, so it must not import UI
session state.  This module is the narrow port from user-scoped persisted
favorites and the shared, already-cached News dashboard into catalog values.
It never refreshes providers, writes caches, or derives scores/rankings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping, Protocol

from backend.news.cache import NEWS_CACHE_DIR, load_cached_news_dashboard_snapshot
from backend.notifications.marketdata_measurements import (
    select_favorite_daily_measurements,
    select_favorite_move_measurements,
)

PROFILE_ROOT = Path("data/user/profiles")
_SAFE_USER_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_FRESH_NEWS_STATUSES = {"latest", "recent"}


@dataclass(frozen=True, slots=True)
class NotificationSourceValues:
    """Resolved catalog fields, or a safe reason for not producing an item."""

    values: Mapping[str, str] | None
    reason: str = "ok"
    dedupe_token: str | None = None


class NotificationDataSource(Protocol):
    """Stable N6 port used by the scheduler before it creates a notification."""

    def values_for(self, template_id: str, *, user_id: str) -> NotificationSourceValues:
        """Return bounded display values without performing network access."""


class CachedNotificationDataSource:
    """Build catalog values from persisted favorites and the News cache.

    Only custom profile files are read.  The session-only ``default`` user is
    intentionally unsupported because it is not a notification recipient.
    """

    def __init__(
        self,
        *,
        profile_root: Path | str = PROFILE_ROOT,
        news_cache_dir: Path | str = NEWS_CACHE_DIR,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.profile_root = Path(profile_root)
        self.news_cache_dir = Path(news_cache_dir)
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def values_for(self, template_id: str, *, user_id: str) -> NotificationSourceValues:
        if user_id == "default" or not _SAFE_USER_ID.fullmatch(user_id):
            return NotificationSourceValues(None, "unsupported_user")
        if template_id == "favorite_daily_report":
            return self._favorite_daily_values(user_id)
        if template_id == "favorite_move_alert":
            return self._favorite_move_values(user_id)
        if template_id == "favorite_news_digest":
            return self._favorite_news_values(user_id)
        if template_id == "investment_news_digest":
            return self._investment_news_values()
        if template_id == "sector_momentum_digest":
            return self._sector_momentum_values()
        return NotificationSourceValues(None, "unsupported_template")

    def _favorite_daily_values(self, user_id: str) -> NotificationSourceValues:
        favorites = self._favorite_symbols(user_id)
        measurements = select_favorite_daily_measurements(
            set(favorites),
            self._watchlist_snapshots(user_id),
            now=self.now_provider(),
        )
        if not measurements.measurements:
            return NotificationSourceValues(None, measurements.reason)
        displayed = "、".join(favorites[:3])
        suffix = " ほか" if len(favorites) > 3 else ""
        return NotificationSourceValues(
            {
                "count": str(measurements.favorite_count),
                "detail": (
                    "直近36時間以内に確認できた価格計測: "
                    f"{measurements.coverage_count}/{measurements.favorite_count}銘柄。"
                    f"登録済み: {displayed}{suffix}"
                ),
            }
        )

    def _favorite_move_values(self, user_id: str) -> NotificationSourceValues:
        favorites = set(self._favorite_symbols(user_id))
        measurements = select_favorite_move_measurements(
            favorites,
            self._watchlist_snapshots(user_id),
            now=self.now_provider(),
        )
        if not measurements.moves:
            return NotificationSourceValues(None, measurements.reason)
        detail = "、".join(
            f"{item.symbol} {item.change_1d_pct:+.1f}%" for item in measurements.moves[:3]
        )
        return NotificationSourceValues(
            {"count": str(len(measurements.moves)), "detail": detail},
            dedupe_token=measurements.dedupe_token,
        )

    def _favorite_news_values(self, user_id: str) -> NotificationSourceValues:
        favorites = set(self._favorite_symbols(user_id))
        if not favorites:
            return NotificationSourceValues(None, "no_favorites")
        snapshot = self._fresh_news_snapshot()
        if snapshot is None:
            return NotificationSourceValues(None, "news_cache_unavailable")
        matched_symbols: set[str] = set()
        count = 0
        for card in snapshot.stream_headlines:
            symbols = {symbol.strip().upper() for symbol in card.related_symbols if symbol.strip()}
            matched = favorites & symbols
            if matched:
                count += 1
                matched_symbols.update(matched)
        if not count:
            return NotificationSourceValues(None, "no_favorite_news")
        display_symbols = "、".join(sorted(matched_symbols)[:3])
        return NotificationSourceValues(
            {
                "count": str(count),
                "detail": f"{display_symbols} に関する確認材料を整理しました。",
            }
        )

    def _investment_news_values(self) -> NotificationSourceValues:
        snapshot = self._fresh_news_snapshot()
        if snapshot is None or not snapshot.stream_headlines:
            return NotificationSourceValues(None, "news_cache_unavailable")
        categories = sorted({card.category for card in snapshot.stream_headlines if card.category})
        category_text = "、".join(categories[:3])
        return NotificationSourceValues(
            {
                "count": str(len(snapshot.stream_headlines)),
                "detail": f"{category_text} のニュースキャッシュを確認できます。",
            }
        )

    def _sector_momentum_values(self) -> NotificationSourceValues:
        snapshot = self._fresh_news_snapshot()
        if snapshot is None or not snapshot.heatmap_cells:
            return NotificationSourceValues(None, "news_cache_unavailable")
        cells = sorted(
            snapshot.heatmap_cells,
            key=lambda cell: (-cell.heat_score, cell.category),
        )[:3]
        detail = "、".join(f"{cell.category}（材料{cell.news_count}件）" for cell in cells)
        return NotificationSourceValues({"count": str(len(cells)), "detail": detail})

    def _favorite_symbols(self, user_id: str) -> list[str]:
        payload = self._read_json(self.profile_root / user_id / "favorites.json")
        raw_favorites = payload.get("favorites") if isinstance(payload, dict) else None
        if not isinstance(raw_favorites, list):
            return []
        symbols: list[str] = []
        seen: set[str] = set()
        for item in raw_favorites:
            symbol = _normalized_symbol(item.get("symbol") if isinstance(item, dict) else None)
            if symbol and symbol not in seen:
                symbols.append(symbol)
                seen.add(symbol)
        return symbols

    def _watchlist_snapshots(self, user_id: str) -> dict[str, Mapping[str, object]]:
        payload = self._read_json(self.profile_root / user_id / "watchlist_snapshots.json")
        raw_snapshots = payload.get("snapshots") if isinstance(payload, dict) else None
        if not isinstance(raw_snapshots, dict):
            return {}
        snapshots: dict[str, Mapping[str, object]] = {}
        for raw_symbol, item in raw_snapshots.items():
            if isinstance(item, dict) and (symbol := _normalized_symbol(raw_symbol)):
                snapshots[symbol] = item
        return snapshots

    def _fresh_news_snapshot(self):
        snapshot = load_cached_news_dashboard_snapshot(cache_dir=self.news_cache_dir)
        if snapshot is None or snapshot.freshness_status not in _FRESH_NEWS_STATUSES:
            return None
        return snapshot

    @staticmethod
    def _read_json(path: Path) -> object:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}


def _normalized_symbol(value: object) -> str:
    symbol = str(value or "").strip().upper()
    return symbol[:32] if symbol else ""
