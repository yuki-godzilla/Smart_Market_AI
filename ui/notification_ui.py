from __future__ import annotations

from datetime import time
from typing import cast

import streamlit as st

from backend.notifications.notification_client import NotificationSeverity
from backend.notifications.settings_repository import (
    DEFAULT_NOTIFICATION_CATEGORIES,
    NotificationSettingsError,
    NotificationSettingsRepository,
)
from backend.notifications.settings_service import (
    NotificationSettingUpdate,
    NotificationSettingValidationError,
    clear_saved_topic,
    load_notification_setting_safe,
    notification_result_message,
    save_notification_setting,
    send_saved_test_notification,
)

DEFAULT_NOTIFICATION_USER_ID = "local_user"
SEVERITY_LABELS = {
    "critical": "Critical以上",
    "high": "High以上",
    "medium": "Medium以上",
    "low": "Low以上",
    "silent": "Silent以上",
}
CATEGORY_LABELS = {
    "FAVORITE": "お気に入り銘柄",
    "MARKET_TREND": "市場動向",
    "INVESTMENT_NEWS": "投資ニュース",
    "SMAI_INSIGHT": "SMAI分析",
    "SYSTEM": "システム",
}


def render_notification_settings(user_id: str = DEFAULT_NOTIFICATION_USER_ID) -> None:
    """Render the legacy combined destination settings surface."""
    render_notification_destination(user_id)


def render_notification_destination(user_id: str = DEFAULT_NOTIFICATION_USER_ID) -> None:
    """Render ntfy destination and delivery-window settings."""

    repository = NotificationSettingsRepository()
    loaded = load_notification_setting_safe(
        repository,
        user_id=user_id,
    )
    setting = loaded.setting

    with st.expander("通知先", expanded=False):
        st.caption(
            "スマホ通知（ntfy）はオプション機能です。ntfy通知をONにしてtopicを設定し、"
            "テスト通知ボタンを押した場合だけ送信します。"
            "既存の分析やデータ更新から自動送信は行いません。"
        )
        if loaded.warning:
            st.warning("通知設定を読み込めなかったため、安全な初期設定を表示しています。")

        app_enabled = st.checkbox(
            "アプリ内通知を有効にする",
            value=setting.app_enabled,
            key="notification_app_enabled",
        )
        ntfy_enabled = st.checkbox(
            "ntfyスマホ通知を有効にする",
            value=setting.ntfy_enabled,
            key="notification_ntfy_enabled",
        )
        server_url = st.text_input(
            "ntfy server URL",
            value=setting.ntfy_server_url,
            key="notification_ntfy_server_url",
        )
        topic_input = st.text_input(
            "ntfy topic",
            value="",
            type="password",
            placeholder=(
                "保存済み（変更しない場合は空欄）"
                if setting.topic_configured
                else "推測困難なtopicを入力"
            ),
            key="notification_ntfy_topic",
        )
        st.caption(
            "topicはSQLiteに保存されます。完全な暗号化秘匿ではありません。"
            "空欄のまま保存すると、保存済みtopicを維持します。"
        )
        st.caption(f"保存状態: {'設定済み' if setting.topic_configured else '未設定'}")

        severity_values = list(SEVERITY_LABELS)
        severity_threshold = st.selectbox(
            "外部通知する重要度",
            severity_values,
            index=severity_values.index(setting.severity_threshold),
            format_func=lambda value: SEVERITY_LABELS[value],
            key="notification_severity_threshold",
        )
        quiet_enabled = st.checkbox(
            "Quiet hoursを有効にする",
            value=setting.quiet_hours_enabled,
            key="notification_quiet_enabled",
        )
        quiet_start = st.time_input(
            "開始",
            value=_time_value(setting.quiet_hours_start, time(22, 0)),
            key="notification_quiet_start",
            disabled=not quiet_enabled,
        )
        quiet_end = st.time_input(
            "終了",
            value=_time_value(setting.quiet_hours_end, time(7, 0)),
            key="notification_quiet_end",
            disabled=not quiet_enabled,
        )

        save_col, delete_col, test_col = st.columns(3)
        save_clicked = save_col.button(
            "通知設定を保存",
            key="notification_save",
            type="primary",
        )
        delete_clicked = delete_col.button(
            "保存済みtopicを削除",
            key="notification_delete_topic",
            disabled=not setting.topic_configured,
        )
        test_clicked = test_col.button(
            "テスト通知を送る",
            key="notification_send_test",
        )

        if save_clicked:
            try:
                save_notification_setting(
                    repository,
                    user_id=user_id,
                    update=NotificationSettingUpdate(
                        app_enabled=app_enabled,
                        ntfy_enabled=ntfy_enabled,
                        ntfy_server_url=server_url,
                        topic_input=topic_input,
                        severity_threshold=cast(NotificationSeverity, severity_threshold),
                        quiet_hours_enabled=quiet_enabled,
                        quiet_hours_start=quiet_start,
                        quiet_hours_end=quiet_end,
                        enabled_categories=setting.enabled_categories,
                    ),
                )
            except NotificationSettingValidationError as exc:
                st.warning(str(exc))
            except NotificationSettingsError:
                st.error("通知設定を保存できませんでした。時間をおいて再度お試しください。")
            else:
                st.success("通知設定を保存しました。")

        if delete_clicked:
            try:
                clear_saved_topic(
                    repository,
                    user_id=user_id,
                )
            except NotificationSettingsError:
                st.error("保存済みtopicを削除できませんでした。")
            else:
                st.success("保存済みtopicを削除し、ntfy通知をOFFにしました。")

        if test_clicked:
            try:
                current = repository.load(user_id)
            except NotificationSettingsError:
                st.error("通知設定を確認できないため、テスト通知を実行できませんでした。")
            else:
                try:
                    with st.spinner("テスト通知を確認しています…"):
                        result = send_saved_test_notification(current)
                except NotificationSettingsError:
                    st.error("テスト通知を実行できませんでした。")
                else:
                    level, message = notification_result_message(result)
                    getattr(st, level)(message)


def render_notification_preferences(user_id: str = DEFAULT_NOTIFICATION_USER_ID) -> None:
    """Render per-category notification preferences."""
    repository = NotificationSettingsRepository()
    loaded = load_notification_setting_safe(repository, user_id=user_id)
    setting = loaded.setting
    st.subheader("受け取る通知")
    st.caption("必要な通知の種類を選択します。設定はユーザーごとに保存されます。")
    selected_categories = tuple(
        category
        for category in DEFAULT_NOTIFICATION_CATEGORIES
        if st.checkbox(
            CATEGORY_LABELS[category],
            value=category in setting.enabled_categories,
            key=f"notification_category_{category.lower()}",
        )
    )
    if st.button("通知内容を保存", key="notification_categories_save", type="primary"):
        try:
            save_notification_setting(
                repository,
                user_id=user_id,
                update=NotificationSettingUpdate(
                    app_enabled=setting.app_enabled,
                    ntfy_enabled=setting.ntfy_enabled,
                    ntfy_server_url=setting.ntfy_server_url,
                    severity_threshold=setting.severity_threshold,
                    quiet_hours_enabled=setting.quiet_hours_enabled,
                    quiet_hours_start=setting.quiet_hours_start,
                    quiet_hours_end=setting.quiet_hours_end,
                    enabled_categories=selected_categories,
                ),
            )
        except NotificationSettingsError:
            st.error("通知内容を保存できませんでした。時間をおいて再度お試しください。")
        else:
            st.success("通知内容を保存しました。")


def _time_value(value: str | None, fallback: time) -> time:
    if not value:
        return fallback
    try:
        return time.fromisoformat(value)
    except ValueError:
        return fallback
