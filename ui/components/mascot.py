from __future__ import annotations

import base64
import html
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast

import streamlit as st

MascotVariant = Literal[
    "brand",
    "guide",
    "cockpit",
    "ranking",
    "empty",
    "caution",
    "report",
]
MascotLayout = Literal["sidebar", "compact", "panel"]
MascotTone = Literal["info", "success", "forecast", "caution", "risk"]
WorkflowLoadingMode = Literal["blocking", "inline"]
TitleMascot = Literal["cockpit", "ranking", "investment_radar", "rebalance", "watchlist"]
CopilotState = Literal["ready", "analyzing", "updated", "warning"]

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
BRAND_ASSET_DIR = ASSET_DIR / "brand"
MASCOT_ASSET_DIR = ASSET_DIR / "mascot"
APP_LOGO_ASSET = "smai-logo.png"
MASCOT_REFERENCE_ASSET = "smai-mascot-reference.webp"
MASCOT_CUTOUT_ASSET = "smai-mascot-cutout.png"
MASCOT_NAVI_CHAT_ASSET = "smai-navi-chat-cutout.png"
MASCOT_THUMB_ASSET = "smai-mascot-thumb.webp"
MASCOT_PANEL_ASSET = "smai-mascot-panel.webp"
MASCOT_LOADING_ASSET = "smai-mascot-loading.webp"
MASCOT_WATCHLIST_TITLE_ASSET = "smai-title-watchlist-transparent.png"
MASCOT_TITLE_ASSETS: dict[TitleMascot, str] = {
    "cockpit": "smai-title-cockpit.webp",
    "ranking": "smai-title-ranking.webp",
    "investment_radar": "smai-title-investment-radar.webp",
    "rebalance": "smai-title-rebalance.webp",
    "watchlist": MASCOT_WATCHLIST_TITLE_ASSET,
}
MASCOT_VARIANT_ASSETS: dict[MascotVariant, str] = {
    "brand": MASCOT_PANEL_ASSET,
    "guide": MASCOT_PANEL_ASSET,
    "cockpit": MASCOT_PANEL_ASSET,
    "ranking": "smai-mascot-ranking.webp",
    "empty": MASCOT_PANEL_ASSET,
    "caution": "smai-mascot-caution.webp",
    "report": "smai-mascot-report.webp",
}

MASCOT_VARIANT_DEFAULTS: dict[MascotVariant, dict[str, str]] = {
    "brand": {
        "title": "SMAIナビ",
        "message": "候補探しから確認ポイントまで、売買推奨ではなく深掘りの順番を案内します。",
        "tone": "info",
    },
    "guide": {
        "title": "次に見るポイント",
        "message": "価格、予測、Risk、データ品質の順に確認すると、判断材料を整理しやすくなります。",
        "tone": "forecast",
    },
    "cockpit": {
        "title": "コックピット案内",
        "message": "まず全体KPIを見てから、チャートと評価の内訳を確認しましょう。",
        "tone": "forecast",
    },
    "ranking": {
        "title": "SMAIの注目候補",
        "message": "上位候補を深掘り入口として整理しました。スコアだけでなくRiskとデータ品質も見比べます。",
        "tone": "success",
    },
    "empty": {
        "title": "分析を始めましょう",
        "message": "銘柄と期間を選ぶと、SMAIが確認材料をまとめます。",
        "tone": "info",
    },
    "caution": {
        "title": "確認メモ",
        "message": "注意が出ているときは、ポジションサイズ、下落耐性、データ不足を先に確認します。",
        "tone": "caution",
    },
    "report": {
        "title": "レポート整理",
        "message": "確認した材料を、あとで見返せる分析メモとしてまとめます。",
        "tone": "info",
    },
}


APP_HEADER_MESSAGE = "SMAIナビが、候補探しと確認ポイントの整理をお手伝いします。"


@lru_cache(maxsize=32)
def _asset_data_uri(filename: str, asset_dir: Path = MASCOT_ASSET_DIR) -> str:
    path = asset_dir / filename
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    suffix = path.suffix.lower()
    mime = "image/webp" if suffix == ".webp" else "image/png"
    return f"data:{mime};base64,{encoded}"


def mascot_panel_html(
    variant: MascotVariant,
    *,
    title: str | None = None,
    message: str | None = None,
    layout: MascotLayout = "panel",
    tone: MascotTone | None = None,
) -> str:
    defaults = MASCOT_VARIANT_DEFAULTS[variant]
    display_title = title if title is not None else defaults["title"]
    display_message = message if message is not None else defaults["message"]
    display_tone = tone if tone is not None else defaults["tone"]
    image_asset = MASCOT_THUMB_ASSET if layout == "sidebar" else MASCOT_VARIANT_ASSETS[variant]
    image = _asset_data_uri(image_asset)
    return (
        f'<aside class="smai-mascot smai-mascot--{layout}" '
        f'data-variant="{html.escape(variant)}" data-tone="{html.escape(display_tone)}">'
        f'<img class="smai-mascot-image" src="{image}" alt="SMAI mascot" loading="lazy" />'
        '<div class="smai-mascot-copy">'
        f'<div class="smai-mascot-title">{html.escape(display_title)}</div>'
        f'<div class="smai-mascot-message">{html.escape(display_message)}</div>'
        "</div>"
        "</aside>"
    )


def copilot_presence_panel_html(
    *,
    status: str = "Market Ready",
    message: str = "価格・予測・根拠を横で整理します。",
    state: CopilotState = "ready",
) -> str:
    image = _asset_data_uri(MASCOT_CUTOUT_ASSET)
    return (
        f'<aside class="smai-copilot-panel" data-state="{html.escape(state)}">'
        '<div class="smai-copilot-figure" aria-hidden="true">'
        '<span class="smai-copilot-aura"></span>'
        f'<img class="smai-copilot-image" src="{image}" alt="" loading="lazy" />'
        "</div>"
        '<div class="smai-copilot-copy">'
        '<div class="smai-copilot-label">SMAIアシスタント</div>'
        '<div class="smai-copilot-status">'
        '<span class="smai-copilot-status-dot"></span>'
        f"<span>{html.escape(status)}</span>"
        "</div>"
        f'<p class="smai-copilot-message">{html.escape(message)}</p>'
        "</div>"
        "</aside>"
    )


def smai_insight_html(
    message: str,
    *,
    title: str = "SMAI Insight",
    tone: MascotTone = "forecast",
) -> str:
    image = _asset_data_uri(MASCOT_CUTOUT_ASSET)
    return (
        f'<aside class="smai-insight" data-tone="{html.escape(tone)}">'
        '<div class="smai-insight-avatar" aria-hidden="true">'
        f'<img src="{image}" alt="" loading="lazy" />'
        "</div>"
        '<div class="smai-insight-copy">'
        f'<div class="smai-insight-title">{html.escape(title)}</div>'
        f'<div class="smai-insight-message">{html.escape(message)}</div>'
        "</div>"
        "</aside>"
    )


def app_header_html(
    title: str = "Smart Market AI",
    *,
    message: str = APP_HEADER_MESSAGE,
) -> str:
    image = _asset_data_uri(MASCOT_THUMB_ASSET)
    logo = _asset_data_uri(APP_LOGO_ASSET, BRAND_ASSET_DIR)
    return (
        '<header class="smai-app-header">'
        '<div class="smai-app-header-copy">'
        f'<img class="smai-app-logo" src="{logo}" '
        f'alt="{html.escape(title)}" loading="eager" />'
        f'<p class="smai-app-message">{html.escape(message)}</p>'
        "</div>"
        '<div class="smai-app-mascot-wrap" aria-hidden="true">'
        f'<img class="smai-app-mascot" src="{image}" alt="" loading="lazy" />'
        "</div>"
        "</header>"
    )


def render_app_header(
    title: str = "Smart Market AI",
    *,
    message: str = APP_HEADER_MESSAGE,
) -> None:
    st.markdown(app_header_html(title, message=message), unsafe_allow_html=True)


def _title_asset_data_uri(mascot: str) -> str:
    mascot_key = cast(TitleMascot, mascot) if mascot in MASCOT_TITLE_ASSETS else "investment_radar"
    asset_name = MASCOT_TITLE_ASSETS[mascot_key]
    if not (MASCOT_ASSET_DIR / asset_name).is_file():
        asset_name = MASCOT_TITLE_ASSETS["investment_radar"]
    return _asset_data_uri(asset_name)


def page_title_html(
    title: str,
    subtitle: str,
    mascot: TitleMascot,
    *,
    accessory_html: str | None = None,
) -> str:
    accessory = (
        f'<div class="smai-page-title-accessory">{accessory_html}</div>' if accessory_html else ""
    )
    if mascot == "cockpit":
        title_art = _title_asset_data_uri(mascot)
        return (
            '<section class="smai-page-title smai-page-title--copilot" data-mascot="cockpit">'
            f"{accessory}"
            '<div class="smai-page-title-copy">'
            '<div class="smai-page-title-row">'
            f'<h2 class="smai-page-title-heading">{html.escape(title)}</h2>'
            '<div class="smai-page-title-art" aria-hidden="true">'
            f'<img class="smai-page-title-image" src="{title_art}" alt="" loading="lazy" />'
            "</div>"
            "</div>"
            f'<p class="smai-page-title-subtitle">{html.escape(subtitle)}</p>'
            "</div>" + copilot_presence_panel_html() + "</section>"
        )
    image = _title_asset_data_uri(mascot)
    return (
        f'<section class="smai-page-title" data-mascot="{html.escape(mascot)}">'
        f"{accessory}"
        '<div class="smai-page-title-copy">'
        '<div class="smai-page-title-row">'
        f'<h2 class="smai-page-title-heading">{html.escape(title)}</h2>'
        '<div class="smai-page-title-art" aria-hidden="true">'
        f'<img class="smai-page-title-image" src="{image}" alt="" loading="lazy" />'
        "</div>"
        "</div>"
        f'<p class="smai-page-title-subtitle">{html.escape(subtitle)}</p>'
        "</div>"
        "</section>"
    )


def render_page_title(
    title: str,
    subtitle: str,
    mascot: TitleMascot,
    *,
    accessory_html: str | None = None,
) -> None:
    st.markdown(
        page_title_html(title, subtitle, mascot, accessory_html=accessory_html),
        unsafe_allow_html=True,
    )


def mascot_loading_html(
    variant: MascotVariant,
    *,
    title: str | None = None,
    message: str | None = None,
    tone: MascotTone | None = None,
) -> str:
    defaults = MASCOT_VARIANT_DEFAULTS[variant]
    display_title = title if title is not None else defaults["title"]
    display_message = message if message is not None else defaults["message"]
    display_tone = tone if tone is not None else defaults["tone"]
    image = _asset_data_uri(MASCOT_LOADING_ASSET)
    return (
        f'<aside class="smai-mascot smai-mascot--loading" '
        f'data-variant="{html.escape(variant)}" data-tone="{html.escape(display_tone)}">'
        '<div class="smai-loading-image-wrap" aria-hidden="true">'
        f'<img class="smai-mascot-image smai-mascot-image--loading" '
        f'src="{image}" alt="" loading="eager" />'
        '<span class="smai-loading-pulse"></span>'
        "</div>"
        '<div class="smai-mascot-copy">'
        f'<div class="smai-mascot-title">{html.escape(display_title)}</div>'
        f'<div class="smai-mascot-message">{html.escape(display_message)}</div>'
        '<div class="smai-loading-dots" aria-hidden="true">'
        "<span></span><span></span><span></span>"
        "</div>"
        "</div>"
        "</aside>"
    )


def render_mascot_loading(
    variant: MascotVariant,
    *,
    title: str | None = None,
    message: str | None = None,
    tone: MascotTone | None = None,
) -> None:
    st.markdown(
        mascot_loading_html(variant, title=title, message=message, tone=tone),
        unsafe_allow_html=True,
    )


def workflow_loading_html(
    *,
    title: str,
    message: str,
    current_step: str,
    progress: float,
    mode: WorkflowLoadingMode = "blocking",
    headlines: Sequence[Mapping[str, str]] = (),
    headline_note: str = "前回取得したニュース",
) -> str:
    normalized_progress = max(0.0, min(1.0, progress))
    progress_percent = round(normalized_progress * 100)
    image = _asset_data_uri(MASCOT_LOADING_ASSET)
    headline_cards = "".join(
        (
            '<article class="smai-workflow-loading-news-card">'
            f'<span>{html.escape(str(item.get("category", "市場ニュース")))}</span>'
            f'<strong>{html.escape(str(item.get("title", "")))}</strong>'
            f'<small>{html.escape(str(item.get("source", "取得元未確認")))}</small>'
            "</article>"
        )
        for item in headlines[:5]
        if str(item.get("title", "")).strip()
    )
    news_html = (
        '<div class="smai-workflow-loading-news">'
        '<div class="smai-workflow-loading-news-head">'
        "<strong>市場トピック</strong>"
        f"<span>{html.escape(headline_note)}</span>"
        "</div>"
        f'<div class="smai-workflow-loading-news-list">{headline_cards}</div>'
        "</div>"
        if headline_cards
        else ""
    )
    return (
        f'<div class="smai-workflow-loading smai-workflow-loading--{mode}" '
        f'data-testid="smai-workflow-loading-{mode}" '
        f'role="{("dialog" if mode == "blocking" else "status")}" '
        f'aria-modal="{("true" if mode == "blocking" else "false")}">'
        '<section class="smai-workflow-loading-panel">'
        '<div class="smai-workflow-loading-visual" aria-hidden="true">'
        '<span class="smai-workflow-loading-orbit"></span>'
        f'<img src="{image}" alt="" loading="eager" />'
        '<span class="smai-workflow-loading-scan"></span>'
        '</div><div class="smai-workflow-loading-copy">'
        '<div class="smai-workflow-loading-kicker">SMAI PROCESS</div>'
        f'<div class="smai-workflow-loading-title">{html.escape(title)}</div>'
        f"<p>{html.escape(message)}</p>"
        '<div class="smai-workflow-loading-current">'
        '<span class="smai-workflow-loading-dot"></span>'
        f"<strong>{html.escape(current_step)}</strong>"
        f"<span>{progress_percent}%</span>"
        '</div><div class="smai-workflow-loading-track" aria-hidden="true">'
        f'<i style="width:{progress_percent}%"></i>'
        f"</div>{news_html}</div></section></div>"
    )


def workflow_loading_headlines_from_cache(
    *,
    max_items: int = 5,
    max_age_hours: int = 24,
) -> tuple[tuple[dict[str, str], ...], str]:
    from backend.assistant.loading_headlines import (  # noqa: PLC0415
        load_assistant_loading_headlines,
    )

    cached = load_assistant_loading_headlines(
        max_items=max_items,
        max_age_hours=max_age_hours,
    )
    rows = tuple(
        {
            "title": item.title,
            "category": item.category,
            "source": item.source,
        }
        for item in cached.items
    )
    if not rows:
        return (), "保存済みニュースはありません"
    timestamp = cached.updated_at.astimezone().strftime("%Y-%m-%d %H:%M")
    stale_label = "・古い可能性あり" if cached.stale else ""
    return rows, f"前回取得 {timestamp}{stale_label}"


def render_mascot_panel(
    variant: MascotVariant,
    *,
    title: str | None = None,
    message: str | None = None,
    layout: MascotLayout = "panel",
    tone: MascotTone | None = None,
) -> None:
    st.markdown(
        mascot_panel_html(
            variant,
            title=title,
            message=message,
            layout=layout,
            tone=tone,
        ),
        unsafe_allow_html=True,
    )
