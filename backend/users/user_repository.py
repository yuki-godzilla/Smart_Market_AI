from __future__ import annotations

import re
import secrets
import sqlite3
import unicodedata
from dataclasses import dataclass

from backend.notifications.settings_repository import (
    NotificationSetting,
    NotificationSettingsRepository,
)

DEFAULT_USER_ID = "default"
_USER_ID_PATTERN = re.compile(r"^u_[a-z0-9_-]{8,32}$")
_ICON_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True, slots=True)
class UserProfile:
    user_id: str
    display_name: str
    icon_asset_id: str
    is_system_user: bool = False
    deletable: bool = True


class UserRepository:
    """Manage local profiles independently from legacy trusted-device behavior."""

    def __init__(self, database_path: str | None = None) -> None:
        self._settings = NotificationSettingsRepository(database_path)
        self._settings.load("local_user")
        self.database_path = self._settings.database_path

    def list_users(self, *, include_system: bool = True) -> list[UserProfile]:
        clause = "" if include_system else "AND is_system_user = 0"
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT user_id, display_name, icon_asset_id, is_system_user, deletable "
                f"FROM users WHERE is_active = 1 {clause} "
                "ORDER BY is_system_user ASC, created_at"
            ).fetchall()
        return [UserProfile(row[0], row[1], row[2], bool(row[3]), bool(row[4])) for row in rows]

    def get_user(self, user_id: str) -> UserProfile | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT user_id, display_name, icon_asset_id, is_system_user, deletable "
                "FROM users WHERE user_id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()
        return UserProfile(row[0], row[1], row[2], bool(row[3]), bool(row[4])) if row else None

    def create_user(self, display_name: str, icon_asset_id: str) -> UserProfile:
        name = _validated_display_name(display_name)
        icon = _validated_icon_id(icon_asset_id)
        for _ in range(8):
            user_id = f"u_{secrets.token_hex(6)}"
            if _USER_ID_PATTERN.fullmatch(user_id) and self.get_user(user_id) is None:
                break
        else:
            raise RuntimeError("A safe user identifier could not be generated.")
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO users "
                "(user_id, display_name, mascot_key, icon_asset_id, is_active, created_at, "
                "is_system_user, deletable) VALUES (?, ?, ?, ?, 1, datetime('now'), 0, 1)",
                (user_id, name, icon, icon),
            )
        self._settings.save(NotificationSetting(user_id=user_id))
        return UserProfile(user_id, name, icon)

    def update_user_profile(
        self, user_id: str, display_name: str, icon_asset_id: str
    ) -> UserProfile:
        current = self.get_user(user_id)
        if current is None:
            raise ValueError("User was not found.")
        if current.is_system_user:
            raise ValueError("The default user cannot be edited.")
        name = _validated_display_name(display_name)
        icon = _validated_icon_id(icon_asset_id)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "UPDATE users SET display_name = ?, icon_asset_id = ?, mascot_key = ? "
                "WHERE user_id = ?",
                (name, icon, icon, user_id),
            )
        return UserProfile(user_id, name, icon, current.is_system_user, current.deletable)

    def is_system_user(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        return bool(user and user.is_system_user)


def _validated_display_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= 32:
        raise ValueError("表示名は1〜32文字で入力してください。")
    if any(unicodedata.category(character) == "Cc" for character in name):
        raise ValueError("表示名に制御文字は使用できません。")
    return name


def _validated_icon_id(value: str) -> str:
    icon_id = value.strip() or "smai_navi_default"
    if not _ICON_ID_PATTERN.fullmatch(icon_id):
        raise ValueError("有効なアイコンを選択してください。")
    return icon_id
