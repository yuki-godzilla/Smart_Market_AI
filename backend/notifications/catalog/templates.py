from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.notifications.content_models import PresentationCategory
from backend.notifications.notification_client import NotificationCategory, NotificationSeverity

TriggerType = Literal["daily", "interval", "event"]


@dataclass(frozen=True, slots=True)
class NotificationTemplate:
    template_id: str
    display_name: str
    technical_category: NotificationCategory
    presentation_category: PresentationCategory
    enabled_channels: tuple[str, ...]
    icon_asset_id: str
    thumbnail_asset_id: str | None
    hero_asset_id: str | None
    trigger_type: TriggerType
    default_schedule: str | None
    default_severity: NotificationSeverity
    title_template: str
    summary_template: str
    body_layout: tuple[str, ...]
    cta_label: str
    cta_page: str
    sample_data: dict[str, str]
    content_version: str = "notification_catalog.v1"


NOTIFICATION_TEMPLATES: tuple[NotificationTemplate, ...] = (
    NotificationTemplate(
        "favorite_daily_report",
        "お気に入り日次レポート",
        "MY_RADAR",
        "FAVORITE",
        ("in_app", "ntfy"),
        "smai_pet_cat",
        "smai_pet_cat",
        None,
        "daily",
        "07:30",
        "medium",
        "今日のMy Favoriteレポート",
        "お気に入り{count}銘柄を確認しました。",
        ("what_happened", "metrics", "next_check"),
        "Myウォッチリストへ",
        "my_radar",
        {"count": "8", "detail": "上昇上位 NVDA +3.2%、下落注意 7203.T -1.4%"},
    ),
    NotificationTemplate(
        "favorite_move_alert",
        "お気に入り急変通知",
        "PRICE_ALERT",
        "FAVORITE",
        ("in_app", "ntfy"),
        "smai_navi_alert",
        "smai_navi_alert",
        None,
        "interval",
        "15m",
        "high",
        "お気に入り銘柄に大きな動きがあります",
        "{count}銘柄で大きな変化を検出しました。",
        ("what_happened", "why_it_matters", "metrics", "next_check"),
        "銘柄コックピットへ",
        "cockpit",
        {"count": "3", "detail": "NVDA +5.4%、TSLA -6.1%、7203.T 出来高2.3倍"},
    ),
    NotificationTemplate(
        "favorite_news_digest",
        "お気に入りニュース",
        "NEWS",
        "FAVORITE",
        ("in_app", "ntfy"),
        "smai_navi_support",
        "smai_navi_support",
        None,
        "interval",
        "60m",
        "medium",
        "お気に入り銘柄ニュース",
        "{count}件の関連材料があります。",
        ("what_happened", "next_check"),
        "ニュースを見る",
        "news",
        {"count": "4", "detail": "NVDA AI関連2件、7203.T 開示1件、TSMC 半導体投資1件"},
    ),
    NotificationTemplate(
        "investment_news_digest",
        "投資トレンドニュース",
        "NEWS",
        "INVESTMENT_NEWS",
        ("in_app", "ntfy"),
        "smai_navi_explorer",
        "smai_navi_explorer",
        None,
        "daily",
        "08:00",
        "medium",
        "今日の投資トレンド",
        "AI・半導体、金利、為替の確認材料があります。",
        ("what_happened", "smai_assessment", "next_check"),
        "投資レーダーへ",
        "investment_radar",
        {"count": "6", "detail": "AI・半導体関連ニュースが増加しています"},
    ),
    NotificationTemplate(
        "sector_momentum_digest",
        "セクター動向",
        "MARKET",
        "MARKET_TREND",
        ("in_app", "ntfy"),
        "smai_navi_analyst",
        "smai_pet_owl",
        None,
        "daily",
        "08:30",
        "medium",
        "上昇気配セクター",
        "セクターとテーマに変化があります。",
        ("what_happened", "smai_assessment", "metrics", "next_check"),
        "銘柄ランキングへ",
        "ranking",
        {"count": "3", "detail": "半導体、AI、防衛テーマの上昇気配が強まっています"},
    ),
    NotificationTemplate(
        "smai_analysis_complete",
        "AI調査完了",
        "RESEARCH",
        "SMAI_INSIGHT",
        ("in_app", "ntfy"),
        "smai_navi_support",
        "smai_navi_analyst",
        None,
        "event",
        None,
        "medium",
        "AI調査が完了しました",
        "{symbol}の確認材料を整理しました。",
        ("what_happened", "smai_assessment", "next_check"),
        "レポートを確認",
        "copilot",
        {"symbol": "AAPL", "detail": "中長期見通しのAI調査が完了しました"},
    ),
    NotificationTemplate(
        "smai_report_ready",
        "レポート作成完了",
        "RESEARCH",
        "SMAI_INSIGHT",
        ("in_app", "ntfy"),
        "smai_navi_analyst",
        "smai_navi_support",
        None,
        "event",
        None,
        "medium",
        "レポートを確認できます",
        "{symbol}のレポートを作成しました。",
        ("what_happened", "next_check"),
        "レポートを確認",
        "copilot",
        {"symbol": "NVDA", "detail": "投資判断レポートを作成しました"},
    ),
    NotificationTemplate(
        "system_notice",
        "システム通知",
        "SYSTEM",
        "SYSTEM",
        ("in_app", "ntfy"),
        "smai_navi_default",
        "smai_navi_smile",
        None,
        "event",
        None,
        "low",
        "SMAIからのお知らせ",
        "{detail}",
        ("what_happened", "next_check"),
        "設定を確認",
        "settings",
        {"detail": "通知設定の変更を保存しました"},
    ),
)


def get_notification_template(template_id: str) -> NotificationTemplate:
    template = next(
        (item for item in NOTIFICATION_TEMPLATES if item.template_id == template_id),
        None,
    )
    if template is None:
        raise KeyError(template_id)
    return template
