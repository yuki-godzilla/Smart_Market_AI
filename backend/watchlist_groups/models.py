from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WatchlistGroupTone = Literal["cyan", "blue", "purple", "green", "amber", "orange", "rose", "slate"]
WATCHLIST_GROUP_TONES: tuple[WatchlistGroupTone, ...] = (
    "cyan",
    "blue",
    "purple",
    "green",
    "amber",
    "orange",
    "rose",
    "slate",
)
GROUP_ID_PATTERN = re.compile(r"^wg_[a-z0-9_]{8,64}$")


def validate_group_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= 32:
        raise ValueError("グループ名は1〜32文字で入力してください。")
    if any(unicodedata.category(character) == "Cc" for character in name):
        raise ValueError("グループ名に制御文字は使用できません。")
    return name


class WatchlistGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str
    name: str
    description: str | None = Field(default=None, max_length=200)
    order: int = Field(ge=0)
    tone: WatchlistGroupTone
    is_system: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        if not GROUP_ID_PATTERN.fullmatch(value):
            raise ValueError("Invalid watchlist group identifier.")
        return value

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_group_name(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if any(unicodedata.category(character) == "Cc" for character in normalized):
            raise ValueError("説明に制御文字は使用できません。")
        return normalized or None

    @model_validator(mode="after")
    def reject_system_group(self) -> WatchlistGroup:
        if self.is_system:
            raise ValueError("System groups are not persisted.")
        return self


class WatchlistPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str
    order: int = Field(default=10, ge=0)
    updated_at: datetime

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        if not GROUP_ID_PATTERN.fullmatch(value):
            raise ValueError("Invalid watchlist group identifier.")
        return value


class WatchlistGroupsState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    updated_at: datetime
    groups: tuple[WatchlistGroup, ...] = ()
    placements: dict[str, WatchlistPlacement] = Field(default_factory=dict)

    @field_validator("placements", mode="before")
    @classmethod
    def normalize_placement_symbols(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized: dict[str, object] = {}
        for symbol, placement in value.items():
            clean_symbol = normalize_watchlist_symbol(str(symbol))
            if not clean_symbol:
                raise ValueError("Invalid placement symbol.")
            normalized[clean_symbol] = placement
        return normalized

    @model_validator(mode="after")
    def validate_state(self) -> WatchlistGroupsState:
        if len(self.groups) > 20:
            raise ValueError("ウォッチリストグループは20件まで作成できます。")
        ids = [group.group_id for group in self.groups]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate watchlist group identifier.")
        names = [group.name for group in self.groups]
        if len(names) != len(set(names)):
            raise ValueError("同じ名前のグループは作成できません。")
        for symbol in self.placements:
            if not normalize_watchlist_symbol(symbol):
                raise ValueError("Invalid placement symbol.")
        return self


def normalize_watchlist_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized or len(normalized) > 64:
        return ""
    if any(
        character.isspace() or unicodedata.category(character) == "Cc" for character in normalized
    ):
        return ""
    return normalized
