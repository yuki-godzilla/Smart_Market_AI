from __future__ import annotations

from datetime import time
from typing import cast

import streamlit as st

from backend.notifications.notification_client import NotificationSeverity
from backend.notifications.scheduler import (
    NotificationScheduleRepository,
    NotificationScheduleSetting,
)
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


def render_notification_preferences(
    user_id: str = DEFAULT_NOTIFICATION_USER_ID,
) -> str | None:
    """Render the complete per-user notification settings surface."""
    repository = NotificationSettingsRepository()
    schedule_repository = NotificationScheduleRepository(str(repository.database_path))
    loaded = load_notification_setting_safe(repository, user_id=user_id)
    setting = loaded.setting
    schedule = schedule_repository.load(user_id)
    if loaded.warning:
        st.warning("通知設定を読み込めなかったため、安全な初期設定を表示しています。")

    with st.container(border=True):
        st.subheader("1. 通知の種類")
        st.caption("必要な通知の種類を選択します。")
        selected_categories = tuple(
            category
            for category in DEFAULT_NOTIFICATION_CATEGORIES
            if st.checkbox(
                CATEGORY_LABELS[category],
                value=category in setting.enabled_categories,
                key=f"notification_category_{category.lower()}",
            )
        )

    with st.container(border=True):
        st.subheader("2. 通知方法")
        app_enabled = st.checkbox(
            "アプリ内通知を有効にする",
            value=setting.app_enabled,
            key="notification_app_enabled",
        )
        ntfy_enabled = st.checkbox(
            "スマホ通知（ntfy）を有効にする",
            value=setting.ntfy_enabled,
            key="notification_ntfy_enabled",
        )
        st.caption("ntfyを有効にした場合だけ、以下の通知先を使用します。")
        server_url = st.text_input(
            "ntfy server URL",
            value=setting.ntfy_server_url,
            key="notification_ntfy_server_url",
            disabled=not ntfy_enabled,
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
            disabled=not ntfy_enabled,
        )
        st.caption("topicは平文で再表示しません。空欄のまま保存すると保存済みtopicを維持します。")
        st.caption(f"保存状態: {'設定済み' if setting.topic_configured else '未設定'}")
        test_col, delete_col = st.columns(2)
        test_clicked = test_col.button(
            "テスト通知を送る",
            key="notification_send_test",
            disabled=not setting.ntfy_enabled or not setting.topic_configured,
        )
        delete_clicked = delete_col.button(
            "保存済みtopicを削除",
            key="notification_delete_topic",
            disabled=not setting.topic_configured,
        )

    with st.container(border=True):
        st.subheader("3. 通知条件")
        severity_values = list(SEVERITY_LABELS)
        severity_threshold = st.selectbox(
            "通知する重要度",
            severity_values,
            index=severity_values.index(setting.severity_threshold),
            format_func=lambda value: SEVERITY_LABELS[value],
            key="notification_severity_threshold",
        )
        quiet_enabled = st.checkbox(
            "通知しない時間帯を設定する",
            value=setting.quiet_hours_enabled,
            key="notification_quiet_enabled",
        )
        start_col, end_col = st.columns(2)
        quiet_start = start_col.time_input(
            "開始",
            value=_time_value(setting.quiet_hours_start, time(22, 0)),
            key="notification_quiet_start",
            disabled=not quiet_enabled,
        )
        quiet_end = end_col.time_input(
            "終了",
            value=_time_value(setting.quiet_hours_end, time(7, 0)),
            key="notification_quiet_end",
            disabled=not quiet_enabled,
        )

    with st.container(border=True):
        st.subheader("4. スケジュール")
        schedule_enabled = st.checkbox(
            "定時通知を有効にする",
            value=schedule.enabled,
            key="notification_schedule_enabled",
        )
        weekdays_only = st.checkbox(
            "平日のみ実行する",
            value=schedule.weekdays_only,
            key="notification_schedule_weekdays",
            disabled=not schedule_enabled,
        )
        daily_col, news_col, sector_col = st.columns(3)
        favorite_daily_time = daily_col.time_input(
            "お気に入り日次",
            value=_time_value(schedule.favorite_daily_time, time(7, 30)),
            key="notification_schedule_favorite_daily",
            disabled=not schedule_enabled,
        )
        investment_news_time = news_col.time_input(
            "投資ニュース",
            value=_time_value(schedule.investment_news_time, time(8, 0)),
            key="notification_schedule_investment_news",
            disabled=not schedule_enabled,
        )
        sector_momentum_time = sector_col.time_input(
            "市場動向",
            value=_time_value(schedule.sector_momentum_time, time(8, 30)),
            key="notification_schedule_sector",
            disabled=not schedule_enabled,
        )

    save_col, cancel_col = st.columns(2)
    save_clicked = save_col.button("通知設定を保存", key="notification_save", type="primary")
    cancel_clicked = cancel_col.button("キャンセル", key="notification_cancel")
    if cancel_clicked:
        return "cancelled"
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
                    enabled_categories=selected_categories,
                ),
            )
            schedule_repository.save(
                NotificationScheduleSetting(
                    user_id=user_id,
                    enabled=schedule_enabled,
                    favorite_daily_time=favorite_daily_time.strftime("%H:%M"),
                    investment_news_time=investment_news_time.strftime("%H:%M"),
                    sector_momentum_time=sector_momentum_time.strftime("%H:%M"),
                    favorite_move_interval_minutes=schedule.favorite_move_interval_minutes,
                    favorite_news_interval_minutes=schedule.favorite_news_interval_minutes,
                    weekdays_only=weekdays_only,
                )
            )
        except NotificationSettingValidationError as exc:
            st.warning(str(exc))
        except NotificationSettingsError:
            st.error("通知設定を保存できませんでした。時間をおいて再度お試しください。")
        else:
            return "saved"

    if delete_clicked:
        try:
            clear_saved_topic(repository, user_id=user_id)
        except NotificationSettingsError:
            st.error("保存済みtopicを削除できませんでした。")
        else:
            st.rerun()

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
    return None


def _time_value(value: str | None, fallback: time) -> time:
    if not value:
        return fallback
    try:
        return time.fromisoformat(value)
    except ValueError:
        return fallback
