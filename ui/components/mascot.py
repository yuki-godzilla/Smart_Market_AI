from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path
from typing import Literal

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
TitleMascot = Literal["cockpit", "ranking", "investment_radar", "rebalance"]
CopilotState = Literal["ready", "analyzing", "updated", "warning"]

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
BRAND_ASSET_DIR = ASSET_DIR / "brand"
MASCOT_ASSET_DIR = ASSET_DIR / "mascot"
APP_LOGO_ASSET = "smai-logo.png"
MASCOT_REFERENCE_ASSET = "smai-mascot-reference.webp"
MASCOT_CUTOUT_ASSET = "smai-mascot-cutout.png"
MASCOT_THUMB_ASSET = "smai-mascot-thumb.webp"
MASCOT_PANEL_ASSET = "smai-mascot-panel.webp"
MASCOT_LOADING_ASSET = "smai-mascot-loading.webp"
MASCOT_TITLE_ASSETS: dict[TitleMascot, str] = {
    "cockpit": "smai-title-cockpit.webp",
    "ranking": "smai-title-ranking.webp",
    "investment_radar": "smai-title-investment-radar.webp",
    "rebalance": "smai-title-rebalance.webp",
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
        '<div class="smai-copilot-label">SMAI Copilot</div>'
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
        title_art = _asset_data_uri(MASCOT_TITLE_ASSETS[mascot])
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
    image = _asset_data_uri(MASCOT_TITLE_ASSETS[mascot])
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
