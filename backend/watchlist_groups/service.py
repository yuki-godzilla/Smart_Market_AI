from __future__ import annotations

import secrets
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict

from backend.watchlist_groups.models import (
    WATCHLIST_GROUP_TONES,
    WatchlistGroup,
    WatchlistGroupsState,
    WatchlistGroupTone,
    WatchlistPlacement,
    normalize_watchlist_symbol,
    validate_group_name,
)
from backend.watchlist_groups.repository import WatchlistGroupsRepository


class GroupedWatchlistSection(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    group_id: str | None
    name: str
    description: str | None
    tone: str
    is_system: bool
    items: tuple[Any, ...]


class WatchlistGroupsStore(Protocol):
    def load(self, user_id: str) -> WatchlistGroupsState: ...

    def save(self, user_id: str, state: WatchlistGroupsState) -> None: ...


def assign_default_tone(state: WatchlistGroupsState) -> WatchlistGroupTone:
    counts: Counter[WatchlistGroupTone] = Counter(group.tone for group in state.groups)
    unused = [tone for tone in WATCHLIST_GROUP_TONES if counts[tone] == 0]
    if unused:
        return unused[0]
    return min(
        WATCHLIST_GROUP_TONES, key=lambda tone: (counts[tone], WATCHLIST_GROUP_TONES.index(tone))
    )


def build_grouped_watchlist(
    favorites: Sequence[Any],
    state: WatchlistGroupsState,
) -> list[GroupedWatchlistSection]:
    groups = sorted(state.groups, key=lambda group: (group.order, group.created_at, group.group_id))
    group_by_id = {group.group_id: group for group in groups}
    items_by_group: dict[str, list[Any]] = {group.group_id: [] for group in groups}
    unclassified: list[Any] = []
    for favorite in favorites:
        symbol = _favorite_symbol(favorite)
        placement = state.placements.get(symbol)
        if placement is None or placement.group_id not in group_by_id:
            unclassified.append(favorite)
        else:
            items_by_group[placement.group_id].append(favorite)
    sections = [
        GroupedWatchlistSection(
            group_id=group.group_id,
            name=group.name,
            description=group.description,
            tone=group.tone,
            is_system=False,
            items=tuple(items_by_group[group.group_id]),
        )
        for group in groups
    ]
    for section_index, section in enumerate(sections):
        section_items = list(section.items)
        section_items.sort(key=lambda item: _placement_order(state, item))
        sections[section_index] = section.model_copy(update={"items": tuple(section_items)})
    sections.append(
        GroupedWatchlistSection(
            group_id=None,
            name="未分類",
            description="まだグループに配置していないお気に入り銘柄です。",
            tone="slate",
            is_system=True,
            items=tuple(unclassified),
        )
    )
    return sections


class WatchlistGroupsService:
    def __init__(self, repository: WatchlistGroupsStore | None = None) -> None:
        self.repository = repository or WatchlistGroupsRepository()

    def list_groups(self, user_id: str) -> WatchlistGroupsState:
        return self.repository.load(user_id)

    def save_state(self, user_id: str, state: WatchlistGroupsState) -> None:
        """Persist a fully validated editor draft in one atomic repository write."""
        self.repository.save(
            user_id,
            WatchlistGroupsState.model_validate(state.model_dump(mode="python")),
        )

    def create_group(
        self,
        user_id: str,
        name: str,
        description: str | None = None,
        tone: WatchlistGroupTone | None = None,
    ) -> WatchlistGroup:
        state = self.repository.load(user_id)
        if len(state.groups) >= 20:
            raise ValueError("ウォッチリストグループは20件まで作成できます。")
        normalized_name = validate_group_name(name)
        self._ensure_unique_name(state, normalized_name)
        now = datetime.now(UTC)
        group = WatchlistGroup(
            group_id=self._new_group_id(state),
            name=normalized_name,
            description=description,
            order=(max((item.order for item in state.groups), default=0) + 10),
            tone=tone or assign_default_tone(state),
            created_at=now,
            updated_at=now,
        )
        self.repository.save(
            user_id,
            state.model_copy(update={"updated_at": now, "groups": (*state.groups, group)}),
        )
        return group

    def update_group(
        self,
        user_id: str,
        group_id: str,
        *,
        name: str,
        description: str | None,
        tone: WatchlistGroupTone,
    ) -> WatchlistGroup:
        state = self.repository.load(user_id)
        current = self._find_group(state, group_id)
        normalized_name = validate_group_name(name)
        self._ensure_unique_name(state, normalized_name, exclude_group_id=group_id)
        now = datetime.now(UTC)
        updated = current.model_copy(
            update={
                "name": normalized_name,
                "description": description,
                "tone": tone,
                "updated_at": now,
            }
        )
        self.repository.save(
            user_id,
            state.model_copy(
                update={
                    "updated_at": now,
                    "groups": tuple(
                        updated if group.group_id == group_id else group for group in state.groups
                    ),
                }
            ),
        )
        return updated

    def delete_group(self, user_id: str, group_id: str) -> None:
        state = self.repository.load(user_id)
        self._find_group(state, group_id)
        now = datetime.now(UTC)
        self.repository.save(
            user_id,
            state.model_copy(
                update={
                    "updated_at": now,
                    "groups": tuple(group for group in state.groups if group.group_id != group_id),
                    "placements": {
                        symbol: placement
                        for symbol, placement in state.placements.items()
                        if placement.group_id != group_id
                    },
                }
            ),
        )

    def move_group(self, user_id: str, group_id: str, direction: int) -> None:
        state = self.repository.load(user_id)
        groups = list(sorted(state.groups, key=lambda group: group.order))
        index = next(
            (position for position, group in enumerate(groups) if group.group_id == group_id),
            None,
        )
        if index is None:
            raise ValueError("グループが見つかりません。")
        target = index + direction
        if target < 0 or target >= len(groups):
            return
        groups[index], groups[target] = groups[target], groups[index]
        now = datetime.now(UTC)
        groups = [
            group.model_copy(update={"order": (position + 1) * 10, "updated_at": now})
            for position, group in enumerate(groups)
        ]
        self.repository.save(
            user_id,
            state.model_copy(update={"updated_at": now, "groups": tuple(groups)}),
        )

    def move_symbol(self, user_id: str, symbol: str, group_id: str | None) -> None:
        state = self.repository.load(user_id)
        normalized = normalize_watchlist_symbol(symbol)
        if not normalized:
            raise ValueError("銘柄コードが不正です。")
        placements = dict(state.placements)
        now = datetime.now(UTC)
        if group_id is None:
            placements.pop(normalized, None)
        else:
            self._find_group(state, group_id)
            placements[normalized] = WatchlistPlacement(
                group_id=group_id,
                order=placements.get(
                    normalized,
                    WatchlistPlacement(group_id=group_id, updated_at=now),
                ).order,
                updated_at=now,
            )
        self.repository.save(
            user_id,
            state.model_copy(update={"updated_at": now, "placements": placements}),
        )

    @staticmethod
    def _find_group(state: WatchlistGroupsState, group_id: str) -> WatchlistGroup:
        group = next((item for item in state.groups if item.group_id == group_id), None)
        if group is None:
            raise ValueError("グループが見つかりません。")
        return group

    @staticmethod
    def _ensure_unique_name(
        state: WatchlistGroupsState,
        name: str,
        *,
        exclude_group_id: str | None = None,
    ) -> None:
        if any(group.name == name and group.group_id != exclude_group_id for group in state.groups):
            raise ValueError("同じ名前のグループは作成できません。")

    @staticmethod
    def _new_group_id(state: WatchlistGroupsState) -> str:
        existing = {group.group_id for group in state.groups}
        for _ in range(8):
            candidate = f"wg_{secrets.token_hex(6)}"
            if candidate not in existing:
                return candidate
        raise RuntimeError("安全なグループIDを生成できませんでした。")


def _favorite_symbol(favorite: Any) -> str:
    if isinstance(favorite, Mapping):
        value = favorite.get("symbol", "")
    else:
        value = getattr(favorite, "symbol", "")
    return normalize_watchlist_symbol(str(value))


def _placement_order(state: WatchlistGroupsState, favorite: Any) -> int:
    placement = state.placements.get(_favorite_symbol(favorite))
    return placement.order if placement is not None else 10**9
