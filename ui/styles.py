from __future__ import annotations

import altair as alt
import streamlit as st

from ui import style_components as _components

SMAI_STYLE_REVISION = "2026-07-14-radar-market-v4"

badge_html = _components.badge_html
compact_display_value = _components.compact_display_value
dashboard_header_html = _components.dashboard_header_html
metric_card_html = _components.metric_card_html
metric_progress_from_value = _components.metric_progress_from_value
render_dashboard_header = _components.render_dashboard_header
render_metric_card = _components.render_metric_card
render_section_heading = _components.render_section_heading
section_heading_html = _components.section_heading_html
truncate_text = _components.truncate_text

THEME_COLORS = {
    "bg_app": "#020510",
    "bg_surface": "#0A1220",
    "bg_card": "#111F35",
    "bg_card_hover": "#1B2E49",
    "bg_elevated": "#213550",
    "text_title": "#F8FBFF",
    "text_heading": "#EAF1FB",
    "text_primary": "#E5EDF7",
    "text_secondary": "#C8D4E3",
    "text_muted": "#AAB8C8",
    "text_disabled": "#77869A",
    "text_value": "#F1F5F9",
    "text_label": "#C0CDDC",
    "text_caption": "#B4C2D3",
    "text_ai_title": "#67E8F9",
    "text_ai_primary": "#D8F3FF",
    "text_ai_muted": "#9ACFE0",
    "text_positive": "#6EE7B7",
    "text_negative": "#FDA4AF",
    "text_warning": "#FCD34D",
    "text_info": "#93C5FD",
    "text_neutral": "#CBD5E1",
    "border_subtle": "#354763",
    "border_default": "#465B78",
    "border_strong": "#6680A2",
    "ai_cyan": "#22D3EE",
    "ai_blue": "#60A5FA",
    "ai_purple": "#A78BFA",
    "ai_bg": "#081B2A",
    "ai_border": "#164E63",
    "ai_text": "#D7EAF5",
    "signal_buy": "#34D399",
    "signal_hold": "#FBBF24",
    "signal_sell": "#F87171",
    "signal_risk": "#FB7185",
    "signal_info": "#60A5FA",
    "chart_price": "#60A5FA",
    "chart_prediction": "#22D3EE",
    "chart_positive": "#34D399",
    "chart_negative": "#F87171",
    "chart_volume": "#64748B",
    "chart_grid": "#1E2A3E",
    "table_header_bg": "#122038",
    "table_row_bg": "#070D19",
    "table_row_hover": "#17283F",
    "button_primary_bg": "#0891B2",
    "button_primary_hover": "#06B6D4",
    "button_secondary_bg": "#111C2E",
    "button_secondary_border": "#2C3B55",
}

CHART_COLORS = {
    "price": THEME_COLORS["chart_price"],
    "prediction": THEME_COLORS["chart_prediction"],
    "positive": THEME_COLORS["chart_positive"],
    "negative": THEME_COLORS["chart_negative"],
    "volume": THEME_COLORS["chart_volume"],
    "grid": THEME_COLORS["chart_grid"],
    "hold": THEME_COLORS["signal_hold"],
    "ai": THEME_COLORS["ai_cyan"],
    "ai_blue": THEME_COLORS["ai_blue"],
    "ai_purple": THEME_COLORS["ai_purple"],
}

FORECAST_ACTUAL_PRICE_COLOR = THEME_COLORS["signal_hold"]
FORECAST_MODEL_COLORS = (
    THEME_COLORS["chart_prediction"],
    THEME_COLORS["chart_price"],
    THEME_COLORS["signal_risk"],
    THEME_COLORS["ai_purple"],
    THEME_COLORS["signal_buy"],
    THEME_COLORS["signal_hold"],
)
RANKING_GRID_CUSTOM_CSS = {
    ".ag-root-wrapper": {
        "background-color": f"{THEME_COLORS['bg_surface']} !important",
        "border": f"1px solid {THEME_COLORS['border_default']}",
        "border-radius": "8px",
    },
    ".ag-root-wrapper-body": {"background-color": f"{THEME_COLORS['bg_surface']} !important"},
    ".ag-root": {"background-color": f"{THEME_COLORS['bg_surface']} !important"},
    ".ag-body": {"background-color": f"{THEME_COLORS['bg_surface']} !important"},
    ".ag-body-viewport": {"background-color": f"{THEME_COLORS['bg_surface']} !important"},
    ".ag-center-cols-viewport": {"background-color": f"{THEME_COLORS['bg_surface']} !important"},
    ".ag-center-cols-container": {"background-color": f"{THEME_COLORS['bg_surface']} !important"},
    ".ag-pinned-left-cols-container": {
        "background-color": f"{THEME_COLORS['bg_surface']} !important",
    },
    ".ag-header": {
        "background-color": f"{THEME_COLORS['table_header_bg']} !important",
        "border-bottom": f"1px solid {THEME_COLORS['border_strong']}",
    },
    ".ag-header-viewport": {
        "background-color": f"{THEME_COLORS['table_header_bg']} !important",
    },
    ".ag-header-container": {
        "background-color": f"{THEME_COLORS['table_header_bg']} !important",
    },
    ".ag-header-cell": {
        "background-color": f"{THEME_COLORS['table_header_bg']} !important",
        "border-right": f"1px solid {THEME_COLORS['border_default']}",
        "color": f"{THEME_COLORS['text_heading']} !important",
    },
    ".ag-header-cell-label": {
        "font-weight": "720",
        "color": f"{THEME_COLORS['text_heading']} !important",
    },
    ".ag-header-cell-text": {
        "color": f"{THEME_COLORS['text_heading']} !important",
        "font-weight": "720",
    },
    ".ag-icon": {"color": f"{THEME_COLORS['text_muted']} !important"},
    ".ag-row": {
        "background-color": f"{THEME_COLORS['table_row_bg']} !important",
        "border-bottom": f"1px solid {THEME_COLORS['border_subtle']}",
        "color": f"{THEME_COLORS['text_value']} !important",
        "cursor": "pointer",
    },
    ".ag-row-even": {"background-color": f"{THEME_COLORS['table_row_bg']} !important"},
    ".ag-row-odd": {"background-color": f"{THEME_COLORS['bg_card']} !important"},
    ".ag-row-hover": {"background-color": f"{THEME_COLORS['table_row_hover']} !important"},
    ".ag-row-selected": {"background-color": f"{THEME_COLORS['bg_elevated']} !important"},
    ".ag-cell": {
        "border-right": f"1px solid {THEME_COLORS['border_subtle']}",
        "color": f"{THEME_COLORS['text_value']} !important",
        "font-weight": "600",
        "line-height": "1.35",
        "overflow": "hidden",
        "overflow-wrap": "normal",
        "text-overflow": "ellipsis",
        "white-space": "nowrap",
    },
    ".ag-cell-value": {
        "color": f"{THEME_COLORS['text_value']} !important",
        "overflow": "hidden",
        "overflow-wrap": "normal",
        "text-overflow": "ellipsis",
        "white-space": "nowrap",
    },
}

SMAI_GLOBAL_CSS = """
<style>
.research-ai-cta--hero {
    padding: 0.2rem 0.1rem 0.1rem;
    margin: 0;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.research-ai-cta--hero) {
    border-color: rgba(34, 211, 238, 0.38);
    background:
        radial-gradient(circle at top left, rgba(34, 211, 238, 0.1), transparent 34%),
        linear-gradient(135deg, rgba(8, 27, 42, 0.96), rgba(17, 31, 53, 0.92));
    box-shadow: 0 12px 28px rgba(2, 8, 23, 0.2);
}
.research-ai-state-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.75rem;
}
.research-ai-state-chip {
    border: 1px solid rgba(103, 232, 249, 0.28);
    border-radius: 999px;
    background: rgba(8, 27, 42, 0.72);
    color: #c9f4fb;
    font-size: 0.78rem;
    line-height: 1.3;
    padding: 0.25rem 0.54rem;
}
.research-ai-materials {
    margin-top: 0.65rem;
}
.research-ai-materials-title {
    color: #d8f3ff;
    font-size: 0.82rem;
    font-weight: 780;
}
.research-ai-materials ul {
    color: #b9dbe7;
    font-size: 0.82rem;
    line-height: 1.45;
    margin: 0.18rem 0 0;
    padding-left: 1.1rem;
}
</style>
<style>
:root {
    /* Background */
    --bg-page: #070D19;
    --bg-app: #020510;
    --bg-surface: #0A1220;
    --bg-card: #111F35;
    --bg-card-hover: #1B2E49;
    --bg-elevated: #213550;

    /* Text */
    --text-title: #F8FBFF;
    --text-heading: #EAF1FB;
    --text-primary: #E5EDF7;
    --text-secondary: #C8D4E3;
    --text-muted: #AAB8C8;
    --text-disabled: #77869A;

    /* Text hierarchy */
    --text-value: #F1F5F9;
    --text-label: #C0CDDC;
    --text-caption: #B4C2D3;

    /* AI Text */
    --text-ai-title: #67E8F9;
    --text-ai-primary: #D8F3FF;
    --text-ai-muted: #9ACFE0;

    /* Financial Semantic Text */
    --text-positive: #6EE7B7;
    --text-negative: #FDA4AF;
    --text-warning: #FCD34D;
    --text-info: #93C5FD;
    --text-neutral: #CBD5E1;

    /* Border */
    --border-subtle: #354763;
    --border-default: #465B78;
    --border-strong: #6680A2;

    /* AI Accent */
    --ai-cyan: #22D3EE;
    --ai-blue: #60A5FA;
    --ai-purple: #A78BFA;
    --ai-bg: #081B2A;
    --ai-border: #164E63;
    --ai-text: #D7EAF5;

    /* Investment Signal */
    --signal-buy: #34D399;
    --signal-hold: #FBBF24;
    --signal-sell: #F87171;
    --signal-risk: #FB7185;
    --signal-info: #60A5FA;

    /* Chart */
    --chart-price: #60A5FA;
    --chart-prediction: #22D3EE;
    --chart-positive: #34D399;
    --chart-negative: #F87171;
    --chart-volume: #64748B;
    --chart-grid: #1E2A3E;

    /* Table */
    --table-header-bg: #122038;
    --table-row-bg: #0A1220;
    --table-row-hover: #1B2E49;

    /* Button */
    --button-primary-bg: #0891B2;
    --button-primary-hover: #06B6D4;
    --button-secondary-bg: #111C2E;
    --button-secondary-border: #2C3B55;

    /* Surface treatment */
    --surface-glass: rgba(20, 35, 58, 0.82);
    --surface-raised: rgba(27, 46, 73, 0.86);
    --shadow-soft: 0 18px 46px rgba(0, 0, 0, 0.24);
    --shadow-subtle: 0 10px 26px rgba(0, 0, 0, 0.16);

    /* Shared SMAI page geometry */
    --smai-page-max-width: 1440px;
    --smai-content-max-width: 1320px;
    --smai-chat-main-width: 1180px;
    --smai-side-panel-width: 280px;
    --smai-content-gutter: 48px;
    --smai-content-gutter-compact: 24px;

    /* Backwards-compatible aliases for existing components. */
    --smai-bg: var(--bg-app);
    --smai-panel: var(--bg-surface);
    --smai-card: var(--bg-card);
    --smai-card-soft: var(--bg-elevated);
    --smai-border: rgba(70, 91, 120, 0.95);
    --smai-border-strong: var(--border-strong);
    --smai-text: var(--text-title);
    --smai-body: var(--text-primary);
    --smai-muted: var(--text-muted);
    --smai-muted-readable: var(--text-secondary);
    --smai-accent: var(--ai-cyan);
    --smai-accent-soft: rgba(34, 211, 238, 0.12);
    --smai-green: var(--signal-buy);
    --smai-amber: var(--signal-hold);
    --smai-rose: var(--signal-risk);
    --smai-blue: var(--ai-blue);
    --smai-teal: var(--ai-cyan);
    --smai-gray: var(--chart-volume);
}

html {
    /* Scale rem-based UI typography down by 10% while preserving touch targets. */
    font-size: 90%;
}

html,
body,
#root,
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stAppViewContainer"] .main {
    background:
        linear-gradient(90deg, rgba(30, 42, 62, 0.18) 1px, transparent 1px),
        linear-gradient(180deg, var(--bg-page) 0%, var(--bg-surface) 100%);
    background-size: 56px 56px, auto;
    background-color: var(--bg-page);
}

.stApp {
    color: var(--text-primary);
}

.stApp,
.stApp p,
.stApp li,
.stApp span,
.stApp label {
    text-rendering: geometricPrecision;
}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stAppViewContainer"] .main {
    min-height: 100vh;
}

[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stAppViewContainer"] .main {
    background:
        linear-gradient(90deg, rgba(30, 42, 62, 0.18) 1px, transparent 1px),
        linear-gradient(180deg, var(--bg-page) 0%, var(--bg-surface) 100%) !important;
    background-size: 56px 56px, auto !important;
    background-color: var(--bg-page) !important;
}

.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background:
        linear-gradient(180deg, rgba(5, 8, 18, 0.05), rgba(5, 8, 18, 0.42)),
        repeating-linear-gradient(
            0deg,
            rgba(96, 165, 250, 0.045) 0,
            rgba(96, 165, 250, 0.045) 1px,
            transparent 1px,
            transparent 72px
        );
    opacity: 0.46;
}

[data-testid="stHeader"] {
    background: linear-gradient(180deg, rgba(2, 5, 16, 0.94), rgba(2, 5, 16, 0.72));
    backdrop-filter: blur(10px);
}

[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, rgba(6, 12, 27, 0.98) 0%, rgba(10, 18, 32, 0.98) 100%);
    border-right: 1px solid var(--smai-border);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: var(--text-secondary) !important;
    font-weight: 680;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    color: var(--text-title) !important;
}

[data-testid="stAppViewContainer"] .main .block-container {
    width: 100%;
    max-width: none;
    padding-top: 2.2rem;
    padding-bottom: 3.8rem;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    color: var(--text-primary);
    font-size: 0.95rem;
    font-weight: 580;
    line-height: 1.65;
    letter-spacing: 0;
}

[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2 {
    color: var(--text-title);
    letter-spacing: 0;
}

[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {
    color: var(--text-heading);
    letter-spacing: 0;
}

[data-testid="stMarkdownContainer"] a {
    color: #7DD3FC;
    text-decoration-color: rgba(96, 165, 250, 0.42);
    text-decoration-thickness: 1px;
    text-underline-offset: 0.16rem;
}

[data-testid="stMarkdownContainer"] a:hover {
    color: #BAE6FD;
    text-decoration: underline;
}

[data-testid="stMarkdownContainer"] hr {
    border-color: var(--border-subtle);
}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    color: var(--text-caption);
    font-size: 0.9rem;
    font-weight: 620;
    line-height: 1.6;
    letter-spacing: 0;
}

[data-testid="stTable"] {
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    overflow: hidden;
}

[data-testid="stTable"] table {
    border-collapse: collapse;
}

[data-testid="stTable"] table,
[data-testid="stDataFrame"] {
    font-size: 0.92rem;
}

[data-testid="stTable"] thead tr,
[data-testid="stTable"] thead th {
    background: var(--table-header-bg);
    color: var(--text-heading);
    font-weight: 700;
}

[data-testid="stTable"] tbody tr,
[data-testid="stTable"] tbody td {
    background: var(--table-row-bg);
    border-color: var(--border-subtle);
    color: var(--text-value);
    font-weight: 560;
}

[data-testid="stTable"] tbody td:first-child {
    color: var(--text-label);
    font-weight: 620;
}

[data-testid="stTable"] tbody tr:hover td {
    background: var(--table-row-hover);
}

[data-testid="stButton"] button {
    /* Preserve the desktop control baseline even when compact typography is enabled. */
    min-height: 36px;
    border-radius: 8px;
    border: 1px solid var(--button-secondary-border);
    background:
        linear-gradient(180deg, rgba(23, 35, 56, 0.88), rgba(17, 28, 46, 0.88));
    color: var(--text-value);
    font-family: "Inter", "Noto Sans JP", "BIZ UDPGothic", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 0.92rem;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: 0.01em;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
    text-shadow: 0 1px 0 rgba(0, 0, 0, 0.18);
    transition:
        border-color 120ms ease,
        background 120ms ease,
        background-position 240ms ease,
        box-shadow 120ms ease,
        color 120ms ease,
        transform 120ms ease;
}

[data-testid="stButton"] button * {
    color: inherit !important;
}

[data-testid="stButton"] button [data-testid="stMarkdownContainer"] p {
    color: inherit;
    font-family: inherit;
    font-size: inherit;
    font-weight: inherit;
    letter-spacing: inherit;
    line-height: inherit;
}

[data-testid="stButton"] button:hover {
    border-color: var(--ai-border);
    background: var(--bg-card-hover);
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.12);
    transform: translateY(-1px);
}

[data-testid="stButton"] button[kind="primary"] {
    border-color: rgba(125, 211, 252, 0.62);
    background:
        linear-gradient(
            135deg,
            rgba(11, 58, 102, 0.98) 0%,
            rgba(8, 145, 178, 0.98) 44%,
            rgba(20, 184, 166, 0.96) 100%
        );
    background-size: 180% 180%;
    background-position: 0% 50%;
    color: #F8FDFF;
    font-weight: 700;
    text-shadow:
        0 1px 1px rgba(3, 7, 18, 0.42),
        0 0 12px rgba(34, 211, 238, 0.32);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.18),
        0 12px 28px rgba(34, 211, 238, 0.2),
        0 0 0 1px rgba(103, 232, 249, 0.16);
}

[data-testid="stButton"] button[kind="primary"]:hover {
    border-color: rgba(186, 230, 253, 0.78);
    background:
        linear-gradient(
            135deg,
            rgba(56, 189, 248, 1) 0%,
            rgba(34, 211, 238, 0.98) 45%,
            rgba(103, 232, 249, 0.98) 100%
        );
    background-size: 180% 180%;
    background-position: 100% 50%;
    color: #F8FDFF;
    text-shadow:
        0 1px 1px rgba(3, 7, 18, 0.42),
        0 0 14px rgba(186, 230, 253, 0.42);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.22),
        0 16px 36px rgba(20, 184, 166, 0.28),
        0 0 0 1px rgba(103, 232, 249, 0.22);
}

[data-testid="stButton"] button:disabled,
[data-testid="stButton"] button[disabled] {
    color: var(--text-disabled);
    background: rgba(16, 26, 43, 0.56);
    box-shadow: none;
    text-shadow: none;
    transform: none;
}

.smai-favorite-button-anchor {
    height: 0;
}

.smai-favorite-button-anchor + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-favorite-button-anchor)
    + div[data-testid="stButton"] button,
.element-container:has(.smai-favorite-button-anchor)
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-favorite-button-anchor)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    border-color: #38BDF8 !important;
    background: linear-gradient(135deg, #075985 0%, #1D4ED8 100%) !important;
    color: #F0F9FF !important;
    font-weight: 800 !important;
    text-shadow: 0 1px 1px rgba(3, 7, 18, 0.34);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.2),
        0 6px 18px rgba(14, 165, 233, 0.24);
}

.smai-favorite-button-anchor + div[data-testid="stButton"] button:hover,
[data-testid="stMarkdownContainer"]:has(.smai-favorite-button-anchor)
    + div[data-testid="stButton"] button:hover,
.element-container:has(.smai-favorite-button-anchor)
    + .element-container div[data-testid="stButton"] button:hover,
div[data-testid="stElementContainer"]:has(.smai-favorite-button-anchor)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button:hover {
    border-color: #7DD3FC !important;
    background: linear-gradient(135deg, #0284C7 0%, #2563EB 100%) !important;
    color: #FFFFFF !important;
    transform: translateY(-1px);
    box-shadow:
        0 0 0 1px rgba(103, 232, 249, 0.2),
        0 10px 24px rgba(14, 165, 233, 0.3);
}

.smai-favorite-button-anchor[data-active="true"] + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-favorite-button-anchor[data-active="true"])
    + div[data-testid="stButton"] button,
.element-container:has(.smai-favorite-button-anchor[data-active="true"])
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(
        .smai-favorite-button-anchor[data-active="true"]
    )
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    border-color: #FDE047 !important;
    background: linear-gradient(135deg, #F59E0B 0%, #FACC15 100%) !important;
    color: #422006 !important;
    font-weight: 900 !important;
    text-shadow: none !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.42),
        0 0 16px rgba(250, 204, 21, 0.3),
        0 8px 22px rgba(245, 158, 11, 0.26);
}

.smai-favorite-button-anchor[data-active="true"] + div[data-testid="stButton"] button:hover,
[data-testid="stMarkdownContainer"]:has(.smai-favorite-button-anchor[data-active="true"])
    + div[data-testid="stButton"] button:hover,
.element-container:has(.smai-favorite-button-anchor[data-active="true"])
    + .element-container div[data-testid="stButton"] button:hover,
div[data-testid="stElementContainer"]:has(
        .smai-favorite-button-anchor[data-active="true"]
    )
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button:hover {
    border-color: #FEF08A !important;
    color: #422006 !important;
    background: linear-gradient(135deg, #FBBF24 0%, #FDE047 100%) !important;
    transform: translateY(-1px);
    box-shadow:
        0 0 0 1px rgba(250, 204, 21, 0.28),
        0 12px 28px rgba(245, 158, 11, 0.32);
}

.smai-favorite-button-anchor + div[data-testid="stButton"] button:focus-visible,
[data-testid="stMarkdownContainer"]:has(.smai-favorite-button-anchor)
    + div[data-testid="stButton"] button:focus-visible,
.element-container:has(.smai-favorite-button-anchor)
    + .element-container div[data-testid="stButton"] button:focus-visible,
div[data-testid="stElementContainer"]:has(.smai-favorite-button-anchor)
    + div[data-testid="stElementContainer"]
    div[data-testid="stButton"]
    button:focus-visible {
    outline: 3px solid rgba(125, 211, 252, 0.72) !important;
    outline-offset: 2px;
}

.smai-favorite-button-anchor[data-active="true"]
    + div[data-testid="stButton"] button:focus-visible,
[data-testid="stMarkdownContainer"]:has(.smai-favorite-button-anchor[data-active="true"])
    + div[data-testid="stButton"] button:focus-visible,
.element-container:has(.smai-favorite-button-anchor[data-active="true"])
    + .element-container div[data-testid="stButton"] button:focus-visible,
div[data-testid="stElementContainer"]:has(
        .smai-favorite-button-anchor[data-active="true"]
    )
    + div[data-testid="stElementContainer"]
    div[data-testid="stButton"]
    button:focus-visible {
    outline-color: rgba(253, 224, 71, 0.78) !important;
}

.smai-favorite-button-anchor + div[data-testid="stButton"] button *,
[data-testid="stMarkdownContainer"]:has(.smai-favorite-button-anchor)
    + div[data-testid="stButton"] button *,
.element-container:has(.smai-favorite-button-anchor)
    + .element-container div[data-testid="stButton"] button *,
div[data-testid="stElementContainer"]:has(.smai-favorite-button-anchor)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button * {
    color: inherit !important;
}

.smai-favorite-button-anchor[data-variant="prominent"] + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(
        .smai-favorite-button-anchor[data-variant="prominent"]
    )
    + div[data-testid="stButton"] button,
.element-container:has(
        .smai-favorite-button-anchor[data-variant="prominent"]
    )
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(
        .smai-favorite-button-anchor[data-variant="prominent"]
    )
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    min-height: 3.15rem;
    padding: 0.8rem 1.35rem !important;
    border-width: 2px !important;
    border-radius: 999px !important;
    font-size: 1rem !important;
    font-weight: 900 !important;
}

.smai-favorite-button-anchor[data-variant="prominent"][data-active="false"]
    + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(
        .smai-favorite-button-anchor[data-variant="prominent"][data-active="false"]
    )
    + div[data-testid="stButton"] button,
.element-container:has(
        .smai-favorite-button-anchor[data-variant="prominent"][data-active="false"]
    )
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(
        .smai-favorite-button-anchor[data-variant="prominent"][data-active="false"]
    )
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    border-color: rgba(56, 189, 248, 0.95) !important;
    background:
        linear-gradient(135deg, rgba(3, 105, 161, 0.98), rgba(29, 78, 216, 0.96)) !important;
    color: #F0F9FF !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.2),
        0 10px 28px rgba(14, 165, 233, 0.3) !important;
}

.smai-favorite-button-anchor[data-variant="prominent"][data-active="true"]
    + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(
        .smai-favorite-button-anchor[data-variant="prominent"][data-active="true"]
    )
    + div[data-testid="stButton"] button,
.element-container:has(
        .smai-favorite-button-anchor[data-variant="prominent"][data-active="true"]
    )
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(
        .smai-favorite-button-anchor[data-variant="prominent"][data-active="true"]
    )
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    border-color: #FDE047 !important;
    background:
        linear-gradient(135deg, #F59E0B 0%, #FACC15 100%) !important;
    color: #422006 !important;
    text-shadow: none !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.42),
        0 0 18px rgba(250, 204, 21, 0.38),
        0 12px 30px rgba(245, 158, 11, 0.3) !important;
}

[data-testid="column"]:has(.smai-cockpit-favorite-action-anchor)
    [data-testid="stButton"]
    button {
    min-height: 3.15rem !important;
    padding: 0.8rem 1.35rem !important;
    border: 2px solid rgba(56, 189, 248, 0.95) !important;
    border-radius: 999px !important;
    background:
        linear-gradient(135deg, #0369A1 0%, #1D4ED8 100%) !important;
    color: #F0F9FF !important;
    font-size: 1rem !important;
    font-weight: 900 !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.22),
        0 10px 28px rgba(14, 165, 233, 0.34) !important;
}

[data-testid="column"]:has(
        .smai-cockpit-favorite-action-anchor
    ):has(
        .smai-favorite-button-anchor[data-active="true"]
    )
    [data-testid="stButton"]
    button {
    border-color: #FDE047 !important;
    background:
        linear-gradient(135deg, #F59E0B 0%, #FACC15 100%) !important;
    color: #422006 !important;
    text-shadow: none !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.42),
        0 0 18px rgba(250, 204, 21, 0.42),
        0 12px 30px rgba(245, 158, 11, 0.34) !important;
}

.investment-news-symbol-chip-open-anchor + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.investment-news-symbol-chip-open-anchor)
    + div[data-testid="stButton"] button {
    min-height: 2.35rem;
    border-color: rgba(96, 165, 250, 0.34) !important;
    background: rgba(15, 23, 42, 0.44) !important;
    color: #EAF3FF !important;
    font-weight: 760;
    justify-content: flex-start;
    text-align: left;
}

.investment-news-symbol-chip-open-anchor + div[data-testid="stButton"] button:hover,
[data-testid="stMarkdownContainer"]:has(.investment-news-symbol-chip-open-anchor)
    + div[data-testid="stButton"] button:hover {
    border-color: rgba(103, 232, 249, 0.54) !important;
    background: rgba(8, 47, 73, 0.5) !important;
}

[data-baseweb="select"] > div,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea {
    border-color: rgba(102, 128, 162, 0.72);
    background-color: rgba(20, 31, 48, 0.96);
    color: var(--text-value);
    border-radius: 8px;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.055),
        0 0 0 1px rgba(2, 6, 23, 0.18);
    min-height: 2.35rem;
}

[data-baseweb="select"] > div:hover,
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stDateInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: rgba(125, 211, 252, 0.82);
    box-shadow:
        0 0 0 1px rgba(125, 211, 252, 0.22),
        0 0 0.85rem rgba(34, 211, 238, 0.08);
}

[data-baseweb="select"] [role="combobox"],
[data-baseweb="select"] span,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea {
    color: var(--text-value) !important;
    font-weight: 680;
}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stDateInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: var(--text-muted);
    opacity: 1;
    font-weight: 640;
}

[data-testid="stTextInput"] input:disabled,
[data-testid="stDateInput"] input:disabled,
[data-testid="stNumberInput"] input:disabled,
[data-testid="stTextArea"] textarea:disabled {
    background-color: rgba(20, 31, 48, 0.72);
    color: var(--text-disabled);
    opacity: 1;
}

[data-baseweb="select"] span,
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stDateInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stCheckbox"] label {
    color: var(--text-label);
    font-weight: 780;
    letter-spacing: 0;
}

[data-testid="stCheckbox"] label p,
[data-testid="stRadio"] label p {
    color: var(--text-secondary) !important;
    font-weight: 700;
}

[data-testid="stSidebar"] [data-testid="stButton"] button {
    border-radius: 8px;
    border: 1px solid rgba(102, 128, 162, 0.6);
    background: rgba(24, 35, 56, 0.9);
    color: var(--smai-text);
}

[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
    border-color: rgba(56, 189, 248, 0.7);
    background: rgba(8, 105, 130, 0.58);
    color: #FFFFFF;
}

[data-testid="stMetric"] {
    padding: 0.84rem 0.9rem;
    border: 1px solid var(--smai-border);
    border-radius: 8px;
    background: var(--bg-card);
}

[data-testid="stMetricLabel"] {
    color: var(--text-label);
    font-weight: 760;
}

[data-testid="stMetricValue"] {
    color: var(--text-value);
    letter-spacing: 0;
    font-weight: 820;
}

[data-testid="stExpander"] {
    border: 1px solid rgba(102, 128, 162, 0.72);
    border-radius: 8px;
    background:
        linear-gradient(180deg, rgba(20, 35, 58, 0.86), rgba(13, 24, 41, 0.84));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.055),
        var(--shadow-subtle);
    margin: 0.65rem 0 1rem;
}

[data-testid="stExpander"] details summary {
    color: var(--text-heading);
    min-height: 2.75rem;
    font-weight: 840;
}

[data-testid="stExpander"] details summary p {
    color: var(--text-heading) !important;
    font-weight: 840 !important;
}

[data-testid="stMarkdownContainer"]:has(.smai-cockpit-filter-expander-anchor)
    + [data-testid="stExpander"] details summary,
[data-testid="stMarkdownContainer"]:has(.smai-cockpit-filter-expander-anchor)
    + [data-testid="stExpander"] details summary p {
    color: #FFFFFF !important;
    font-weight: 840 !important;
}

[data-testid="stMarkdownContainer"]:has(.smai-cockpit-filter-expander-anchor)
    + [data-testid="stExpander"] details summary p {
    line-height: 1.55;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border-default);
    border-radius: 8px;
    background:
        linear-gradient(180deg, rgba(20, 35, 58, 0.9), rgba(13, 24, 41, 0.88));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.035),
        var(--shadow-subtle);
}

[data-testid="stTabs"] button {
    color: var(--text-label);
}

[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--text-ai-title);
    border-color: var(--ai-cyan);
}

[data-testid="stAlert"] {
    border-radius: 8px;
    border: 1px solid var(--border-default);
    background: var(--bg-card);
    color: var(--text-primary);
}

[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
    color: var(--text-secondary);
}

.smai-card,
.smai-ai-card,
.smai-ai-summary-box,
.smai-news-insight-card,
.smai-risk-alert-box,
.smai-source-link-list,
.smai-confidence-meter,
.smai-score-breakdown-table,
.smai-state-box {
    border-radius: 8px;
    border: 1px solid var(--border-subtle);
    background: var(--bg-card);
}

.smai-card {
    padding: 0.95rem 1rem;
}

.smai-card p,
.smai-ai-card p,
.smai-section-card p,
.smai-ranking-setup-block p,
.smai-ranking-builder-head p,
.smai-ranking-policy-builder p,
.smai-ranking-target-summary span,
.smai-state-box p {
    color: var(--text-secondary) !important;
    font-weight: 640;
}

.smai-card-label,
.smai-insight-kicker,
.smai-ranking-builder-subhead,
.smai-cockpit-prefetch-heading {
    color: var(--text-heading) !important;
    font-weight: 840 !important;
}

.smai-ranking-builder-caption,
.smai-cockpit-prefetch-caption,
.smai-ranking-policy-caution,
.smai-ranking-condition-load-message {
    color: var(--text-secondary) !important;
    font-weight: 680 !important;
}

.smai-card:hover {
    background: var(--bg-card-hover);
    border-color: var(--border-strong);
}

.smai-ai-card,
.smai-ai-summary-box,
.smai-news-insight-card {
    border-color: var(--ai-border);
    background: linear-gradient(180deg, rgba(8, 27, 42, 0.94), rgba(11, 18, 32, 0.94));
    color: var(--text-ai-primary);
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.04);
}

.smai-ai-card-title,
.smai-ai-summary-title,
.smai-news-insight-title {
    color: var(--text-ai-title);
    font-weight: 820;
}

.smai-ai-card-body,
.smai-ai-summary-body,
.smai-news-insight-body {
    color: var(--text-ai-primary);
    line-height: 1.62;
}

.investment-news-ticker {
    position: relative;
    min-height: 9.7rem;
    overflow: hidden;
    margin: 0.35rem 0 1rem;
    padding: 0.72rem 0.78rem 0.55rem;
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.13), rgba(251, 191, 36, 0.08)),
        linear-gradient(180deg, rgba(8, 27, 42, 0.95), rgba(11, 18, 32, 0.94));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.investment-news-ticker-flow {
    display: flex;
    align-items: center;
    gap: 0.45rem 0.72rem;
    min-height: 1.48rem;
    margin: 0 0 0.48rem;
    color: var(--text-muted);
    font-size: 0.67rem;
    font-weight: 720;
    letter-spacing: 0.015em;
}

.investment-news-ticker-flow-label {
    display: inline-flex;
    align-items: center;
    gap: 0.34rem;
    color: #a5f3fc;
    font-size: 0.7rem;
    font-weight: 850;
    letter-spacing: 0.07em;
    white-space: nowrap;
}

.investment-news-ticker-flow-label i {
    display: inline-block;
    width: 0.48rem;
    height: 0.48rem;
    border-radius: 50%;
    background: #34d399;
    box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.62);
    animation: investment-news-flow-pulse 1.8s ease-out infinite;
}

.investment-news-ticker-flow-count {
    padding-left: 0.7rem;
    border-left: 1px solid rgba(125, 211, 252, 0.2);
    white-space: nowrap;
}

.investment-news-ticker-flow-time {
    overflow: hidden;
    margin-left: auto;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-news-board-radio {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
}

.investment-news-board-viewport {
    position: relative;
    min-height: 5.55rem;
}

.investment-news-board-page {
    position: absolute;
    inset: 0;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    grid-template-rows: minmax(5.1rem, auto);
    gap: 0.55rem;
    opacity: 0;
    pointer-events: none;
    animation-duration: var(--investment-news-board-duration);
    animation-timing-function: ease-in-out;
    animation-iteration-count: infinite;
    will-change: opacity, transform;
}

.investment-news-board-page:first-child {
    opacity: 1;
}

.investment-news-ticker:hover .investment-news-board-page {
    animation-play-state: paused;
}

.investment-news-ticker:hover .investment-news-ticker-item,
.investment-news-ticker:hover .investment-news-ticker-flow-label i {
    animation-play-state: paused;
}

.investment-news-ticker-item {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-content: start;
    gap: 0.28rem 0.52rem;
    min-width: 0;
    padding: 0.52rem 0.62rem;
    border: 1px solid rgba(125, 211, 252, 0.18);
    border-radius: 9px;
    background: rgba(15, 23, 42, 0.5);
    color: var(--text-primary);
    font-size: 0.88rem;
    font-weight: 720;
    line-height: 1.42;
    text-decoration: none;
    transition:
        border-color 0.16s ease,
        background-color 0.16s ease,
        transform 0.16s ease;
    animation: investment-news-ticker-spotlight var(--investment-news-flow-duration) ease-in-out
        var(--investment-news-flow-delay) infinite;
}

.investment-news-ticker-item:hover {
    border-color: rgba(103, 232, 249, 0.42);
    background: rgba(8, 47, 73, 0.62);
    transform: translateY(-1px);
}

@keyframes investment-news-flow-pulse {
    0% {
        box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.62);
    }
    70%,
    100% {
        box-shadow: 0 0 0 0.42rem rgba(52, 211, 153, 0);
    }
}

@keyframes investment-news-ticker-spotlight {
    0%,
    18%,
    100% {
        border-color: rgba(125, 211, 252, 0.18);
        background: rgba(15, 23, 42, 0.5);
        box-shadow: none;
    }
    25%,
    43% {
        border-color: rgba(103, 232, 249, 0.62);
        background: rgba(8, 47, 73, 0.72);
        box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.08), 0 0.55rem 1.25rem rgba(8, 145, 178, 0.12);
    }
}

.investment-news-ticker-category {
    flex: 0 0 auto;
    border: 1px solid rgba(34, 211, 238, 0.28);
    border-radius: 999px;
    background: rgba(34, 211, 238, 0.09);
    color: var(--text-ai-title);
    font-size: 0.68rem;
    font-weight: 800;
    line-height: 1.2;
    padding: 0.11rem 0.4rem;
    white-space: nowrap;
}

.investment-news-ticker-title {
    min-width: 0;
    display: -webkit-box;
    overflow: hidden;
    overflow-wrap: anywhere;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}

.investment-news-ticker-item small {
    grid-column: 2;
    color: var(--text-muted);
    font-size: 0.68rem;
    font-weight: 620;
}

.investment-news-board-nav {
    position: relative;
    z-index: 3;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.42rem;
    min-height: 1.25rem;
    margin-top: 0.48rem;
}

.investment-news-board-nav label {
    display: grid;
    place-items: center;
    width: 0.48rem;
    height: 0.48rem;
    overflow: hidden;
    border-radius: 50%;
    background: rgba(148, 163, 184, 0.42);
    cursor: pointer;
    transition:
        background-color 0.16s ease,
        transform 0.16s ease;
}

.investment-news-board-nav label:hover {
    background: #67e8f9;
    transform: scale(1.18);
}

.investment-news-board-nav label span {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
}

.investment-news-board-nav-note {
    position: absolute;
    right: 0.1rem;
    color: var(--text-muted);
    font-size: 0.65rem;
}

@media (prefers-reduced-motion: reduce) {
    .investment-news-board-page {
        position: relative;
        display: none;
        animation: none;
    }

    .investment-news-board-page:first-child {
        display: grid;
        opacity: 1;
        pointer-events: auto;
    }

    .investment-news-ticker-item,
    .investment-news-ticker-flow-label i {
        animation: none;
    }
}

@media (max-width: 767px) {
    .investment-news-ticker {
        min-height: 16.25rem;
    }

    .investment-news-ticker-flow {
        align-items: flex-start;
        flex-wrap: wrap;
        gap: 0.22rem 0.52rem;
    }

    .investment-news-ticker-flow-count {
        padding-left: 0.52rem;
    }

    .investment-news-ticker-flow-time {
        width: 100%;
        margin-left: 0;
    }

    .investment-news-board-viewport {
        min-height: 12.1rem;
    }

    .investment-news-board-page {
        grid-template-columns: 1fr;
        grid-template-rows: repeat(3, minmax(3.45rem, auto));
    }

    .investment-news-board-nav-note {
        display: none;
    }
}

@media (min-width: 768px) and (max-width: 1200px) {
    .investment-news-ticker {
        min-height: 12.85rem;
    }

    .investment-news-board-viewport {
        min-height: 8.6rem;
    }

    .investment-news-board-page {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        grid-template-rows: repeat(2, minmax(3.75rem, auto));
    }
}

.investment-news-freshness-badge {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.12rem;
    max-width: 100%;
    border: 1px solid rgba(125, 211, 252, 0.22);
    border-radius: 8px;
    background: rgba(9, 20, 35, 0.68);
    padding: 0.3rem 0.58rem;
    box-shadow: 0 0.35rem 1rem rgba(2, 6, 23, 0.18);
    backdrop-filter: blur(8px);
}

.investment-news-freshness-status {
    display: inline-flex;
    align-items: baseline;
    gap: 0.38rem;
}

.investment-news-freshness-label {
    color: var(--text-caption);
    font-size: 0.68rem;
    font-weight: 720;
    line-height: 1.2;
    white-space: nowrap;
}

.investment-news-freshness-value {
    color: var(--text-value);
    font-size: 0.78rem;
    font-weight: 850;
    line-height: 1.2;
    white-space: nowrap;
}

.investment-news-freshness-time {
    color: var(--text-secondary);
    font-size: 0.68rem;
    font-weight: 680;
    line-height: 1.2;
    white-space: nowrap;
}

.investment-news-card {
    --news-accent: #22D3EE;
    --news-accent-soft: rgba(34, 211, 238, 0.1);
    --news-accent-border: rgba(34, 211, 238, 0.28);
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.78rem;
    min-height: 15.8rem;
    border: 1px solid var(--news-accent-border);
    border-radius: 8px;
    background:
        linear-gradient(180deg, var(--news-accent-soft), rgba(15, 23, 42, 0.02)),
        var(--bg-card);
    box-shadow: 0 0.8rem 1.5rem rgba(2, 6, 23, 0.16);
    padding: 0.86rem;
    margin-bottom: 0.75rem;
    overflow: hidden;
}

.investment-news-card::before {
    content: "";
    position: absolute;
    inset: 0 0 auto;
    height: 3px;
    background: linear-gradient(90deg, var(--news-accent), transparent);
    opacity: 0.9;
}

.investment-news-card.compact {
    height: auto;
    min-height: 17.2rem;
}

.investment-news-card.compact .investment-news-card-title,
.investment-news-card.compact .investment-news-card-summary,
.investment-news-card.compact .investment-news-card-comment {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.investment-news-card.compact .investment-news-card-title {
    -webkit-line-clamp: 3;
}

.investment-news-card.compact .investment-news-card-summary {
    -webkit-line-clamp: 2;
}

.investment-news-card.compact .investment-news-card-comment {
    -webkit-line-clamp: 3;
}

.investment-news-card.compact .investment-news-card-checkpoints {
    display: none;
}

.investment-news-card.news {
    --news-accent: #22D3EE;
    --news-accent-soft: rgba(34, 211, 238, 0.09);
    --news-accent-border: rgba(34, 211, 238, 0.28);
}

.investment-news-card.positive {
    --news-accent: #34D399;
    --news-accent-soft: rgba(52, 211, 153, 0.1);
    --news-accent-border: rgba(52, 211, 153, 0.3);
}

.investment-news-card.important {
    --news-accent: #FBBF24;
    --news-accent-soft: rgba(251, 191, 36, 0.1);
    --news-accent-border: rgba(251, 191, 36, 0.33);
}

.investment-news-card.risk {
    --news-accent: #FB7185;
    --news-accent-soft: rgba(251, 113, 133, 0.11);
    --news-accent-border: rgba(251, 113, 133, 0.36);
}

.investment-news-card-main {
    min-width: 0;
}

.investment-news-card-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.34rem;
    margin-bottom: 0.58rem;
}

.investment-news-chip {
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--border-default);
    border-radius: 999px;
    background: rgba(127, 151, 170, 0.08);
    color: var(--text-caption);
    font-size: 0.7rem;
    font-weight: 760;
    line-height: 1.25;
    padding: 0.13rem 0.44rem;
}

.investment-news-chip.primary {
    border-color: var(--news-accent-border);
    background: var(--news-accent-soft);
    color: var(--news-accent);
}

.investment-news-chip.official {
    border-color: rgba(167, 139, 250, 0.3);
    background: rgba(167, 139, 250, 0.1);
    color: #C4B5FD;
}

.investment-news-card-title {
    color: var(--text-heading);
    font-size: 1rem;
    line-height: 1.34;
    margin: 0 0 0.42rem;
    overflow-wrap: anywhere;
}

.investment-news-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.48rem;
    color: var(--text-caption);
    font-size: 0.72rem;
    font-weight: 680;
    margin-bottom: 0.55rem;
}

.investment-news-card-summary,
.investment-news-card-comment {
    color: var(--text-secondary);
    font-size: 0.82rem;
    line-height: 1.55;
    margin: 0.35rem 0;
    overflow-wrap: anywhere;
}

.investment-news-card-comment {
    color: var(--text-ai-primary);
}

.investment-news-card-checkpoints {
    margin: 0.45rem 0 0;
    padding-left: 1.05rem;
    color: var(--text-muted);
    font-size: 0.76rem;
    line-height: 1.46;
}

.investment-news-card-aside {
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
    min-width: 5.8rem;
}

.investment-news-source-link {
    color: var(--news-accent);
    font-size: 0.76rem;
    font-weight: 800;
    text-decoration: none;
    white-space: nowrap;
}

.investment-news-source-link:hover {
    color: var(--text-title);
    text-decoration: underline;
}

.investment-news-lane-heading {
    display: inline-flex;
    align-items: center;
    gap: 0.44rem;
    color: var(--text-heading);
    font-size: 0.94rem;
    font-weight: 850;
    margin: 0.18rem 0 0.46rem;
}

.investment-news-lane-dot {
    width: 0.58rem;
    height: 0.58rem;
    border-radius: 999px;
    background: linear-gradient(135deg, #22D3EE, #FBBF24);
    box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.12);
}

.investment-stock-heatmap {
    border: 1px solid rgba(125, 211, 252, 0.20);
    border-radius: 8px;
    background:
        linear-gradient(135deg, rgba(18, 29, 49, 0.94), rgba(4, 10, 24, 0.96)),
        linear-gradient(180deg, rgba(34, 211, 238, 0.05), rgba(251, 113, 133, 0.04)),
        var(--bg-card, #0B1120);
    padding: 0.62rem;
    margin: 0.25rem 0 0.85rem;
    box-shadow:
        0 1.1rem 2.4rem rgba(2, 6, 23, 0.24),
        inset 0 1px 0 rgba(255, 255, 255, 0.035);
}

.investment-stock-heatmap-topline {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
    gap: 0.5rem;
    color: rgba(178, 199, 216, 0.82);
    font-size: 0.75rem;
    font-weight: 760;
    margin: 0 0 0.42rem;
}

.investment-stock-heatmap-read {
    margin-right: auto;
    color: rgba(208, 230, 242, 0.82);
}

.investment-stock-heatmap-more {
    color: #BFDBFE;
    font-size: 0.72rem;
    font-weight: 820;
    white-space: nowrap;
}

.investment-stock-heatmap-click {
    display: inline-flex;
    align-items: center;
    border: 1px solid rgba(251, 191, 36, 0.32);
    border-radius: 999px;
    background: rgba(251, 191, 36, 0.10);
    color: #FDE68A;
    font-size: 0.72rem;
    font-weight: 850;
    line-height: 1.2;
    padding: 0.14rem 0.48rem;
}

.investment-stock-heatmap-legend {
    display: inline-flex;
    align-items: center;
    gap: 0.24rem;
}

.investment-stock-heatmap-legend::before {
    content: "";
    width: 0.58rem;
    height: 0.58rem;
    border-radius: 2px;
    background: #7C8AA0;
}

.investment-stock-heatmap-legend.negative::before {
    background: linear-gradient(135deg, #F9739A, #9F234A);
}

.investment-stock-heatmap-legend.neutral::before {
    background: linear-gradient(135deg, #B7C1D2, #667085);
}

.investment-stock-heatmap-legend.positive::before {
    background: linear-gradient(135deg, #5EEAD4, #0F9F80);
}

.investment-stock-heatmap-legend.evidence::before {
    background: linear-gradient(135deg, #38BDF8, #0E7490);
}

.investment-stock-heatmap-legend.freshness::before {
    background: linear-gradient(135deg, #1E3A5F, #67E8F9);
}

.investment-stock-heatmap-legend.direct::before {
    background: #2DD4BF;
}

.investment-stock-heatmap-legend.inferred::before {
    background: #A78BFA;
}

.investment-stock-heatmap-legend.market-metric::before {
    background: #FBBF24;
}

.investment-stock-heatmap-board {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    grid-auto-rows: 5.8rem;
    gap: 0.5rem;
}

.investment-stock-heatmap-group {
    --heatmap-group-accent: rgba(125, 211, 252, 0.42);
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 6px;
    background:
        linear-gradient(180deg, rgba(15, 23, 42, 0.86), rgba(5, 10, 24, 0.88));
    overflow: hidden;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.026);
}

.investment-stock-heatmap-group.market {
    --heatmap-group-accent: rgba(45, 212, 191, 0.72);
}

.investment-stock-heatmap-group.asset_class {
    --heatmap-group-accent: rgba(250, 204, 21, 0.72);
}

.investment-stock-heatmap-group.theme {
    --heatmap-group-accent: rgba(167, 139, 250, 0.72);
}

.investment-stock-heatmap-group.macro,
.investment-stock-heatmap-group.event {
    --heatmap-group-accent: rgba(251, 146, 60, 0.72);
}

.investment-stock-heatmap-group.mega {
    grid-column: span 4;
    grid-row: span 4;
}

.investment-stock-heatmap-group.large {
    grid-column: span 4;
    grid-row: span 3;
}

.investment-stock-heatmap-group.medium {
    grid-column: span 4;
    grid-row: span 3;
}

.investment-stock-heatmap-group-header {
    display: flex;
    flex-direction: column;
    gap: 0.22rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
    border-left: 3px solid var(--heatmap-group-accent);
    background:
        linear-gradient(115deg, rgba(8, 24, 44, 0.98), rgba(13, 47, 73, 0.92));
    color: #E6F6FF;
    padding: 0.35rem 0.5rem 0.35rem 0.42rem;
}

.investment-stock-heatmap-group-main,
.investment-stock-heatmap-group-sub {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-width: 0;
}

.investment-stock-heatmap-group-main {
    gap: 0.65rem;
}

.investment-stock-heatmap-group-sub {
    justify-content: flex-start;
    gap: 0.3rem;
}

.investment-stock-heatmap-group-title {
    min-width: 0;
    font-size: 1rem;
    font-weight: 900;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-stock-heatmap-group-meta {
    min-width: 0;
    color: rgba(51, 65, 85, 0.82);
    font-size: 0.72rem;
    font-weight: 760;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-stock-heatmap-group-score,
.investment-stock-heatmap-group-trend {
    font-weight: 850;
    white-space: nowrap;
}

.investment-stock-heatmap-group-score {
    color: #CBD5E1;
    font-size: 0.9rem;
}

.investment-stock-heatmap-group-badge {
    border: 1px solid rgba(125, 211, 252, 0.24);
    border-radius: 999px;
    background: rgba(14, 116, 144, 0.18);
    color: #BAE6FD;
    font-size: 0.68rem;
    font-weight: 760;
    line-height: 1.2;
    padding: 0.1rem 0.38rem;
}

.investment-stock-heatmap-group-kind {
    border: 1px solid rgba(196, 181, 253, 0.3);
    border-radius: 999px;
    background: rgba(109, 40, 217, 0.16);
    color: #DDD6FE;
    font-size: 0.66rem;
    font-weight: 820;
    line-height: 1.2;
    padding: 0.1rem 0.38rem;
    white-space: nowrap;
}

.investment-stock-heatmap-group-kind.market {
    border-color: rgba(94, 234, 212, 0.3);
    background: rgba(13, 148, 136, 0.16);
    color: #99F6E4;
}

.investment-stock-heatmap-group-kind.asset_class {
    border-color: rgba(253, 224, 71, 0.3);
    background: rgba(202, 138, 4, 0.16);
    color: #FEF08A;
}

.investment-stock-heatmap-group-kind.macro,
.investment-stock-heatmap-group-kind.event {
    border-color: rgba(251, 146, 60, 0.3);
    background: rgba(194, 65, 12, 0.16);
    color: #FED7AA;
}

.investment-stock-heatmap-group-trend {
    color: #CBD5E1;
    font-size: 0.72rem;
}

.investment-stock-heatmap-group-score.positive,
.investment-stock-heatmap-group-trend.positive {
    color: #86EFAC;
}

.investment-stock-heatmap-group-score.negative,
.investment-stock-heatmap-group-trend.negative {
    color: #FDA4AF;
}

.investment-stock-heatmap-tiles {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    grid-auto-flow: dense;
    grid-auto-rows: minmax(2.55rem, 1fr);
    gap: 0.16rem;
    flex: 1;
    min-height: 0;
    padding: 0.16rem;
}

.investment-stock-heatmap-tile {
    --heatmap-tile-bg: linear-gradient(145deg, #334155, #111827);
    --heatmap-tile-border: rgba(226, 232, 240, 0.28);
    --heatmap-tile-name: rgba(248, 250, 252, 0.96);
    --heatmap-tile-symbol: rgba(226, 232, 240, 0.82);
    --heatmap-tile-change: rgba(248, 250, 252, 0.95);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.22rem;
    min-width: 0;
    min-height: 42px;
    border: 1px solid var(--heatmap-tile-border);
    border-radius: 4px;
    background: var(--heatmap-tile-bg);
    color: var(--heatmap-tile-name);
    overflow: hidden;
    padding: 0.22rem 0.3rem;
    text-align: center;
    text-decoration: none;
    text-shadow: 0 1px 1px rgba(2, 6, 23, 0.34);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.14),
        inset 0 -1.2rem 2.4rem rgba(2, 6, 23, 0.10);
    transition:
        border-color 140ms ease,
        box-shadow 140ms ease,
        filter 140ms ease,
        transform 140ms ease;
}

.investment-stock-heatmap-tile:hover {
    border-color: rgba(226, 232, 240, 0.72);
    color: var(--heatmap-tile-name);
    filter: brightness(1.06) saturate(1.04);
    text-decoration: none;
    transform: translateY(-1px);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.18),
        0 0 0 1px rgba(226, 232, 240, 0.10),
        0 0.7rem 1.3rem rgba(2, 6, 23, 0.20);
}

.investment-stock-heatmap-tile:focus-visible {
    outline: 2px solid rgba(186, 230, 253, 0.92);
    outline-offset: -2px;
    text-decoration: none;
}

.investment-stock-heatmap-tile.minor {
    align-items: flex-start;
    justify-content: center;
    gap: 0.04rem;
    padding: 0.16rem 0.18rem;
    text-align: left;
}

.investment-stock-heatmap-tile.compact {
    align-items: flex-start;
    gap: 0.08rem;
    padding: 0.18rem 0.24rem;
    text-align: left;
}

.investment-stock-heatmap-group.count-1 .investment-stock-heatmap-tile {
    grid-column: span 6;
    grid-row: span 5;
}

.investment-stock-heatmap-group.count-2 .investment-stock-heatmap-tile {
    grid-column: span 3;
    grid-row: span 5;
}

.investment-stock-heatmap-group.count-3 .investment-stock-heatmap-tile.hero {
    grid-column: span 3;
    grid-row: span 5;
}

.investment-stock-heatmap-group.count-3 .investment-stock-heatmap-tile.major {
    grid-column: span 3;
    grid-row: span 2;
}

.investment-stock-heatmap-group.count-3 .investment-stock-heatmap-tile.major:nth-child(3) {
    grid-row: span 3;
}

.investment-stock-heatmap-group.count-4 .investment-stock-heatmap-tile {
    grid-column: span 3;
    grid-row: span 3;
}

.investment-stock-heatmap-tile.strong-positive {
    --heatmap-tile-bg:
        linear-gradient(145deg, #5EEAD4 0%, #14B8A6 38%, #075E55 100%);
    --heatmap-tile-border: rgba(153, 246, 228, 0.72);
    --heatmap-tile-name: #ECFEFF;
    --heatmap-tile-symbol: rgba(204, 251, 241, 0.88);
    --heatmap-tile-change: #D1FAE5;
}

.investment-stock-heatmap-tile.positive {
    --heatmap-tile-bg:
        linear-gradient(145deg, #34D399 0%, #0F9F80 48%, #064E3B 100%);
    --heatmap-tile-border: rgba(110, 231, 183, 0.62);
    --heatmap-tile-name: #F0FDFA;
    --heatmap-tile-symbol: rgba(204, 251, 241, 0.84);
    --heatmap-tile-change: #BBF7D0;
}

.investment-stock-heatmap-tile.neutral {
    --heatmap-tile-bg:
        linear-gradient(145deg, #AAB4C3 0%, #6B7789 45%, #334155 100%);
    --heatmap-tile-border: rgba(203, 213, 225, 0.50);
    --heatmap-tile-name: #F8FAFC;
    --heatmap-tile-symbol: rgba(226, 232, 240, 0.76);
    --heatmap-tile-change: #E2E8F0;
}

/* News-proxy tiles use one labelled freshness scale.  These colors never
   encode price direction, material sentiment, or investment attractiveness. */
.investment-stock-heatmap-tile.neutral.freshness-3 {
    --heatmap-tile-bg:
        linear-gradient(145deg, #235F7C 0%, #16475F 48%, #0B2638 100%);
    --heatmap-tile-border: rgba(103, 232, 249, 0.68);
    --heatmap-tile-name: #ECFEFF;
    --heatmap-tile-symbol: rgba(207, 250, 254, 0.86);
}

.investment-stock-heatmap-tile.neutral.freshness-2 {
    --heatmap-tile-bg:
        linear-gradient(145deg, #31536D 0%, #203A50 48%, #132A3B 100%);
    --heatmap-tile-border: rgba(125, 211, 252, 0.54);
    --heatmap-tile-name: #EFF6FF;
    --heatmap-tile-symbol: rgba(219, 234, 254, 0.80);
}

.investment-stock-heatmap-tile.neutral.freshness-1 {
    --heatmap-tile-bg:
        linear-gradient(145deg, #414B5A 0%, #2C3544 48%, #1B2532 100%);
    --heatmap-tile-border: rgba(148, 163, 184, 0.48);
}

.investment-stock-heatmap-tile.neutral.freshness-0 {
    --heatmap-tile-bg:
        linear-gradient(145deg, #3A4655 0%, #263342 48%, #162231 100%);
    --heatmap-tile-border: rgba(100, 116, 139, 0.52);
}

.investment-stock-heatmap-tile.negative {
    --heatmap-tile-bg:
        linear-gradient(145deg, #FB7185 0%, #D03861 45%, #7F1D3A 100%);
    --heatmap-tile-border: rgba(253, 164, 175, 0.66);
    --heatmap-tile-name: #FFF1F2;
    --heatmap-tile-symbol: rgba(255, 228, 230, 0.82);
    --heatmap-tile-change: #FFE4E6;
}

.investment-stock-heatmap-tile.strong-negative {
    --heatmap-tile-bg:
        linear-gradient(145deg, #F43F5E 0%, #B42348 44%, #5F1836 100%);
    --heatmap-tile-border: rgba(251, 113, 133, 0.76);
    --heatmap-tile-name: #FFF7ED;
    --heatmap-tile-symbol: rgba(255, 228, 230, 0.84);
    --heatmap-tile-change: #FFE4E6;
}

.investment-stock-heatmap-identity {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.16rem;
    min-width: 0;
    max-width: 100%;
    overflow: hidden;
}

.investment-stock-heatmap-symbol {
    max-width: 100%;
    border: 1px solid rgba(248, 250, 252, 0.24);
    border-radius: 999px;
    background: rgba(2, 6, 23, 0.18);
    color: var(--heatmap-tile-symbol);
    font-size: 0.56rem;
    font-weight: 860;
    line-height: 1.1;
    overflow: hidden;
    padding: 0.08rem 0.32rem;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-stock-heatmap-tile.hero .investment-stock-heatmap-symbol {
    font-size: 0.76rem;
}

.investment-stock-heatmap-tile.major .investment-stock-heatmap-symbol {
    font-size: 0.66rem;
}

.investment-stock-heatmap-tile.medium .investment-stock-heatmap-symbol {
    font-size: 0.62rem;
}

.investment-stock-heatmap-tile.compact .investment-stock-heatmap-symbol {
    font-size: 0.56rem;
}

.investment-stock-heatmap-tile.minor .investment-stock-heatmap-symbol {
    border-radius: 4px;
    font-size: 0.46rem;
    line-height: 1;
    padding: 0.04rem 0.12rem;
}

.investment-stock-heatmap-name {
    max-width: 100%;
    color: var(--heatmap-tile-name);
    display: -webkit-box;
    font-size: 0.78rem;
    font-weight: 900;
    line-height: 1.12;
    overflow: hidden;
    overflow-wrap: anywhere;
    text-overflow: ellipsis;
    white-space: normal;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}

.investment-stock-heatmap-tile.hero .investment-stock-heatmap-name {
    font-size: 1.5rem;
    line-height: 1.08;
}

.investment-stock-heatmap-tile.major .investment-stock-heatmap-name,
.investment-stock-heatmap-tile.medium .investment-stock-heatmap-name {
    font-size: 0.84rem;
    line-height: 1.12;
}

.investment-stock-heatmap-tile.compact .investment-stock-heatmap-identity {
    align-items: flex-start;
    gap: 0.03rem;
}

.investment-stock-heatmap-tile.compact .investment-stock-heatmap-name {
    font-size: 0.76rem;
    font-weight: 870;
    line-height: 1.06;
    -webkit-line-clamp: 2;
}

.investment-stock-heatmap-tile.minor .investment-stock-heatmap-identity {
    align-items: flex-start;
    gap: 0.03rem;
}

.investment-stock-heatmap-tile.minor .investment-stock-heatmap-name {
    font-size: 0.55rem;
    font-weight: 850;
    line-height: 1;
    -webkit-line-clamp: 1;
}

.investment-stock-heatmap-evidence-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 0.16rem;
    max-width: 100%;
}

.investment-stock-heatmap-evidence {
    border: 1px solid rgba(186, 230, 253, 0.36);
    border-radius: 999px;
    background: rgba(8, 47, 73, 0.38);
    color: #E0F2FE;
    font-size: 0.55rem;
    font-weight: 850;
    line-height: 1.1;
    padding: 0.08rem 0.26rem;
    white-space: nowrap;
}

.investment-stock-heatmap-evidence.direct {
    border-color: rgba(94, 234, 212, 0.48);
    background: rgba(13, 148, 136, 0.22);
    color: #CCFBF1;
}

.investment-stock-heatmap-evidence.inferred {
    border-color: rgba(196, 181, 253, 0.46);
    background: rgba(109, 40, 217, 0.20);
    color: #EDE9FE;
}

.investment-stock-heatmap-factors {
    max-width: 100%;
    color: rgba(226, 232, 240, 0.78);
    font-size: 0.58rem;
    font-weight: 760;
    line-height: 1.08;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-stock-heatmap-tile.hero .investment-stock-heatmap-factors {
    font-size: 0.72rem;
}

.investment-stock-heatmap-tile.major .investment-stock-heatmap-factors {
    font-size: 0.64rem;
}

.investment-stock-heatmap-tile.medium .investment-stock-heatmap-factors,
.investment-stock-heatmap-tile.compact .investment-stock-heatmap-factors,
.investment-stock-heatmap-tile.minor .investment-stock-heatmap-factors {
    font-size: 0.54rem;
}

.investment-market-heatmap {
    margin: 0.45rem 0 0.85rem;
    border: 1px solid rgba(125, 211, 252, 0.2);
    border-radius: 14px;
    background:
        radial-gradient(circle at 88% 0%, rgba(14, 165, 233, 0.1), transparent 34%),
        linear-gradient(145deg, rgba(8, 18, 34, 0.96), rgba(4, 9, 19, 0.985));
    padding: 0.8rem;
    box-shadow: 0 1.1rem 3rem rgba(2, 6, 23, 0.3), inset 0 1px rgba(255, 255, 255, 0.025);
    backdrop-filter: blur(8px);
}

.investment-market-heatmap-meta,
.investment-market-heatmap-scale {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.42rem 0.9rem;
    color: rgba(203, 220, 233, 0.78);
    font-size: 0.72rem;
}

.investment-market-heatmap-meta strong {
    margin-right: auto;
    color: #F8FAFC;
    font-size: 0.88rem;
}

.investment-radar-market-summary {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.55rem 1rem;
    margin: 0.35rem 0 0.5rem;
    border: 1px solid rgba(125, 211, 252, 0.16);
    border-radius: 12px;
    background:
        linear-gradient(110deg, rgba(14, 165, 233, 0.09), transparent 42%),
        rgba(15, 23, 42, 0.5);
    padding: 0.6rem 0.75rem;
}

.investment-radar-market-summary-counts,
.investment-radar-market-summary-pick {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.7rem;
}

.investment-radar-market-summary-counts span,
.investment-radar-market-summary-label {
    color: rgba(203, 220, 233, 0.82);
    font-size: 0.72rem;
}

.investment-radar-market-summary-counts span {
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: 999px;
    background: rgba(30, 41, 59, 0.48);
    padding: 0.2rem 0.48rem;
}

.investment-radar-market-summary-counts strong {
    color: #F8FAFC;
    font-size: 0.86rem;
}

.investment-radar-market-summary-pick > strong {
    color: #F8FAFC;
    font-size: 0.94rem;
    letter-spacing: 0.01em;
}
.investment-radar-market-summary-pick code { color: #7DD3FC; }
.investment-radar-market-summary-pick small { color: rgba(203, 220, 233, 0.72); }

.investment-market-heatmap-groups {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.6rem;
    margin: 0.65rem 0 0.5rem;
}

/* Wide desktop canvases can show three category maps without reducing the
   readable tile area.  Standard desktop widths keep the two-column map. */
@media (min-width: 1600px) {
    .investment-market-heatmap-groups {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

.investment-market-heatmap-group {
    min-width: 0;
    overflow: hidden;
    border: 1px solid rgba(125, 211, 252, 0.16);
    border-radius: 10px;
    background: linear-gradient(160deg, rgba(30, 41, 59, 0.62), rgba(8, 15, 29, 0.86));
    box-shadow: 0 0.45rem 1.2rem rgba(2, 6, 23, 0.2);
}

.investment-market-heatmap-group-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    min-height: 42px;
    min-width: 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    background: linear-gradient(90deg, rgba(14, 165, 233, 0.08), transparent 68%);
    padding: 0.52rem 0.65rem;
}

.investment-market-heatmap-group-header strong {
    flex: 0 1 45%;
    overflow: hidden;
    color: #F8FAFC;
    font-size: 0.9rem;
    letter-spacing: 0.015em;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-market-heatmap-group-header span {
    flex: 1 1 55%;
    min-width: 0;
    color: rgba(203, 220, 233, 0.72);
    font-size: 0.64rem;
    line-height: 1.35;
    overflow-wrap: anywhere;
    text-align: right;
}

/* Only the news-category view receives this context card.  It keeps the
   article evidence adjacent to, but visually distinct from, price movement. */
.investment-market-news-context {
    display: block;
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    background: linear-gradient(90deg, rgba(14, 116, 144, 0.18), rgba(15, 23, 42, 0.34));
    color: #E0F2FE;
    min-width: 0;
    padding: 0.42rem 0.62rem 0.46rem;
    text-decoration: none;
}

.investment-market-news-context.is-link {
    cursor: pointer;
}

.investment-market-news-context.is-link:hover,
.investment-market-news-context.is-link:focus-visible {
    background: linear-gradient(90deg, rgba(14, 165, 233, 0.28), rgba(30, 41, 59, 0.56));
    outline: 2px solid rgba(125, 211, 252, 0.78);
    outline-offset: -2px;
}

.investment-market-news-context-label {
    color: #7DD3FC;
    display: block;
    font-size: 0.59rem;
    font-weight: 850;
    letter-spacing: 0.04em;
}

.investment-market-news-context strong {
    color: #F8FAFC;
    display: -webkit-box;
    font-size: 0.73rem;
    line-height: 1.28;
    margin-top: 0.13rem;
    overflow: hidden;
    text-overflow: ellipsis;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}

.investment-market-news-context small {
    color: rgba(203, 220, 233, 0.78);
    display: block;
    font-size: 0.6rem;
    margin-top: 0.18rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* The news-list footer deliberately stays lighter than the main news lanes. */
.investment-radar-candidate-footer-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.38rem;
}

.investment-radar-candidate-footer-item {
    min-width: 0;
    border: 1px solid rgba(125, 211, 252, 0.18);
    border-radius: 7px;
    background: rgba(15, 23, 42, 0.46);
    color: #E0F2FE;
    padding: 0.44rem 0.56rem;
    text-decoration: none;
}

.investment-radar-candidate-footer-item:hover,
.investment-radar-candidate-footer-item:focus-visible {
    border-color: rgba(125, 211, 252, 0.68);
    background: rgba(14, 116, 144, 0.2);
    outline: none;
}

.investment-radar-candidate-footer-item strong,
.investment-radar-candidate-footer-item span {
    display: block;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-radar-candidate-footer-item strong {
    color: #F8FAFC;
    font-size: 0.76rem;
}

.investment-radar-candidate-footer-item span {
    color: rgba(203, 220, 233, 0.78);
    font-size: 0.63rem;
    margin-top: 0.12rem;
}

.investment-market-heatmap-canvas {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 6;
    margin: 0;
    overflow: hidden;
    background: rgba(8, 15, 29, 0.86);
}

/* The map receives more room as a category gains confirmed price tiles.
   These are readability bands, not different data granularity per device. */
.investment-market-heatmap-group.medium .investment-market-heatmap-canvas {
    aspect-ratio: 16 / 7.5;
}

.investment-market-heatmap-group.dense .investment-market-heatmap-canvas {
    aspect-ratio: 16 / 9.5;
}

.investment-market-heatmap-tile {
    position: absolute;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.16rem;
    min-width: 0;
    overflow: hidden;
    border: 2px solid rgba(5, 10, 20, 0.82);
    color: #F8FAFC;
    padding: clamp(0.32rem, 0.48vw, 0.58rem);
    text-align: center;
    text-shadow: 0 1px 3px rgba(2, 6, 23, 0.82);
    text-decoration: none;
}

.investment-market-heatmap-tile:hover,
.investment-market-heatmap-tile:focus-visible {
    z-index: 2;
    outline: 2px solid #7DD3FC;
    outline-offset: -3px;
}

.investment-market-heatmap-pick {
    position: absolute;
    top: 0.28rem;
    left: 0.32rem;
    border-radius: 999px;
    background: rgba(2, 6, 23, 0.72);
    color: #FDE68A;
    font-size: 0.54rem;
    font-weight: 800;
    padding: 0.1rem 0.32rem;
}

.investment-market-heatmap-tile.positive { box-shadow: inset 0 0 0 1px rgba(110, 231, 183, 0.32); }
.investment-market-heatmap-tile.negative { box-shadow: inset 0 0 0 1px rgba(253, 164, 175, 0.32); }
.investment-market-heatmap-tile.flat { box-shadow: inset 0 0 0 1px rgba(203, 213, 225, 0.25); }

.investment-market-heatmap-name {
    max-width: 100%;
    overflow: hidden;
    display: -webkit-box;
    font-size: clamp(0.74rem, 0.95vw, 1.06rem);
    font-weight: 850;
    letter-spacing: 0.01em;
    line-height: 1.12;
    overflow-wrap: anywhere;
    text-wrap: balance;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}

.investment-market-heatmap-symbol,
.investment-market-heatmap-tile small {
    max-width: 100%;
    overflow: hidden;
    color: rgba(241, 245, 249, 0.84);
    font-size: clamp(0.54rem, 0.64vw, 0.7rem);
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-market-heatmap-symbol {
    border-radius: 999px;
    background: rgba(2, 6, 23, 0.28);
    padding: 0.08rem 0.34rem;
    letter-spacing: 0.04em;
}

.investment-market-heatmap-tile strong {
    color: #F8FAFC;
    font-size: clamp(0.76rem, 1.02vw, 1.12rem);
}

.investment-market-heatmap-change {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.32rem;
    max-width: 100%;
    min-height: 1.65rem;
    border: 1px solid rgba(248, 250, 252, 0.24);
    border-radius: 999px;
    background: rgba(2, 6, 23, 0.32);
    box-shadow: inset 0 1px rgba(255, 255, 255, 0.08);
    padding: 0.14rem 0.46rem;
    white-space: nowrap;
}

.investment-market-heatmap-change-direction {
    display: inline-flex;
    align-items: center;
    gap: 0.12rem;
    font-size: 0.76em;
    font-weight: 760;
}

.investment-market-heatmap-change-arrow {
    font-size: 1.08em;
}

.investment-market-heatmap-change-value {
    font-variant-numeric: tabular-nums;
    font-weight: 900;
    letter-spacing: 0.02em;
}

.investment-market-heatmap-tile.positive .investment-market-heatmap-change {
    border-color: rgba(167, 243, 208, 0.54);
    background: rgba(6, 78, 59, 0.32);
    color: #ECFDF5;
}

.investment-market-heatmap-tile.negative .investment-market-heatmap-change {
    border-color: rgba(254, 205, 211, 0.52);
    background: rgba(136, 19, 55, 0.30);
    color: #FFF1F2;
}

.investment-market-heatmap-tile.flat .investment-market-heatmap-change {
    border-color: rgba(226, 232, 240, 0.42);
    background: rgba(51, 65, 85, 0.34);
    color: #F1F5F9;
}

.investment-market-heatmap-tile.compact small,
.investment-market-heatmap-tile.minimal small {
    display: none;
}

.investment-market-heatmap-tile.compact .investment-market-heatmap-change,
.investment-market-heatmap-tile.minimal .investment-market-heatmap-change {
    gap: 0.18rem;
    min-height: 0;
    padding: 0.1rem 0.28rem;
}

.investment-market-heatmap-tile.compact .investment-market-heatmap-change-word,
.investment-market-heatmap-tile.minimal .investment-market-heatmap-change-word {
    display: none;
}

.investment-market-heatmap-tile.minimal .investment-market-heatmap-name {
    display: none;
}

.investment-market-heatmap-tile.minimal .investment-market-heatmap-symbol {
    display: inline-block;
    max-width: 100%;
    font-size: clamp(0.54rem, 0.7vw, 0.72rem);
    font-weight: 850;
    overflow: hidden;
    text-overflow: ellipsis;
}

.investment-market-heatmap-tile.minimal strong {
    font-size: clamp(0.62rem, 0.8vw, 0.82rem);
}

.investment-market-heatmap-scale {
    justify-content: flex-end;
}

.investment-market-heatmap-scale .negative { color: #FDA4AF; }
.investment-market-heatmap-scale .flat { color: #CBD5E1; }
.investment-market-heatmap-scale .positive { color: #6EE7B7; }

.investment-market-heatmap-overflow {
    border-top: 1px solid rgba(148, 163, 184, 0.14);
    background: rgba(2, 6, 23, 0.22);
}

.investment-market-heatmap-overflow summary {
    cursor: pointer;
    display: flex;
    align-items: center;
    min-height: 44px;
    color: #BAE6FD;
    font-size: 0.72rem;
    font-weight: 750;
    padding: 0.48rem 0.65rem;
}

.investment-market-heatmap-overflow-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.35rem;
    padding: 0 0.65rem 0.6rem;
}

.investment-market-heatmap-overflow-item {
    min-width: 0;
    border: 1px solid rgba(125, 211, 252, 0.18);
    border-radius: 6px;
    background: rgba(15, 23, 42, 0.56);
    color: #E0F2FE;
    padding: 0.36rem 0.45rem;
    text-decoration: none;
}

.investment-market-heatmap-overflow-item:hover,
.investment-market-heatmap-overflow-item:focus-visible {
    border-color: rgba(125, 211, 252, 0.64);
    outline: none;
}

.investment-market-heatmap-overflow-item strong,
.investment-market-heatmap-overflow-item span {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.investment-market-heatmap-overflow-item strong {
    color: #F8FAFC;
    font-size: 0.72rem;
}

.investment-market-heatmap-overflow-item span {
    color: rgba(203, 220, 233, 0.8);
    font-size: 0.62rem;
    margin-top: 0.12rem;
}

.investment-radar-evidence-path {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
    margin: 0.55rem 0 0.75rem;
    color: rgba(203, 213, 225, 0.72);
    font-size: 0.72rem;
}

.investment-radar-evidence-path span {
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 999px;
    background: rgba(30, 41, 59, 0.56);
    padding: 0.16rem 0.46rem;
}

.investment-radar-evidence-path span.ready {
    border-color: rgba(45, 212, 191, 0.34);
    background: rgba(13, 148, 136, 0.14);
    color: #99F6E4;
}

.investment-radar-evidence-path span.pending { color: #CBD5E1; }
.investment-radar-evidence-path span.next {
    border-color: rgba(56, 189, 248, 0.34);
    color: #BAE6FD;
}

/* An iPad in landscape still reserves room for Streamlit's sidebar.  Treat
   the resulting main column as tablet-width rather than squeezing three
   theme groups into a desktop row. */
@media (min-width: 768px) and (max-width: 1200px) {
    .investment-market-heatmap-groups {
        grid-template-columns: 1fr;
    }
    .investment-stock-heatmap-board {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        grid-auto-rows: auto;
    }

    .investment-stock-heatmap-group,
    .investment-stock-heatmap-group.mega,
    .investment-stock-heatmap-group.large,
    .investment-stock-heatmap-group.medium {
        grid-column: span 1;
        grid-row: auto;
        min-height: 16rem;
    }
}

/* Portrait tablets retain the sidebar, so a two-column map becomes narrower
   than a phone card.  Keep each theme readable instead of squeezing labels
   into vertical fragments. */
@media (min-width: 768px) and (max-width: 900px) {
    .investment-stock-heatmap-board {
        grid-template-columns: 1fr;
    }

    .investment-stock-heatmap-group,
    .investment-stock-heatmap-group.mega,
    .investment-stock-heatmap-group.large,
    .investment-stock-heatmap-group.medium {
        grid-column: span 1;
        grid-row: auto;
        min-height: 14rem;
    }
}

@media (max-width: 767px) {
    .investment-radar-market-summary,
    .investment-radar-market-summary-pick {
        align-items: flex-start;
        flex-direction: column;
    }
    .investment-market-heatmap-groups {
        grid-template-columns: 1fr;
    }
    /* The fixed assistant remains reachable without covering the final theme
       tile: leave a scroll-safe tail and honour it for keyboard/programmatic
       focus as well as touch scrolling. */
    .investment-stock-heatmap {
        padding-bottom: 4.75rem;
    }
    .investment-stock-heatmap-tile {
        scroll-margin-bottom: 5rem;
    }
    .investment-news-card,
    .investment-news-card.compact {
        grid-template-columns: 1fr;
        min-height: auto;
    }
    .investment-news-card-aside {
        justify-content: flex-start;
    }
    .investment-stock-heatmap-board {
        grid-template-columns: 1fr;
        grid-auto-rows: auto;
    }
    .investment-stock-heatmap-group,
    .investment-stock-heatmap-group.mega,
    .investment-stock-heatmap-group.large,
    .investment-stock-heatmap-group.medium {
        grid-column: span 1;
        grid-row: auto;
        min-height: 12.5rem;
    }
    .investment-stock-heatmap-group-header {
        gap: 0.3rem;
        padding: 0.46rem 0.5rem;
    }
    .investment-stock-heatmap-group-title {
        font-size: 0.94rem;
    }
    .investment-stock-heatmap-group-sub {
        flex-wrap: wrap;
    }
    .investment-stock-heatmap-tiles {
        grid-template-columns: repeat(3, minmax(0, 1fr));
        grid-auto-rows: minmax(6.25rem, auto);
    }
    .investment-stock-heatmap-tile {
        min-height: 44px;
    }
    .investment-stock-heatmap-tile.compact .investment-stock-heatmap-name,
    .investment-stock-heatmap-tile.minor .investment-stock-heatmap-name,
    .investment-stock-heatmap-tile.medium .investment-stock-heatmap-name {
        font-size: 0.68rem;
        line-height: 1.15;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
    .investment-stock-heatmap-tile.hero,
    .investment-stock-heatmap-tile.major,
    .investment-stock-heatmap-tile.medium,
    .investment-stock-heatmap-tile.compact,
    .investment-stock-heatmap-tile.minor,
    .investment-stock-heatmap-group.count-3 .investment-stock-heatmap-tile.medium {
        grid-column: span 1 !important;
        grid-row: span 1 !important;
    }
    .investment-stock-heatmap-evidence {
        font-size: 0.5rem;
    }
    .investment-stock-heatmap-tile.medium .investment-stock-heatmap-factors,
    .investment-stock-heatmap-tile.compact .investment-stock-heatmap-factors,
    .investment-stock-heatmap-tile.minor .investment-stock-heatmap-factors {
        font-size: 0.5rem;
    }
    .investment-market-heatmap-canvas {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        aspect-ratio: auto;
        overflow: visible;
        background: transparent;
    }
    .investment-market-heatmap-tile {
        position: static;
        align-items: flex-start;
        width: 100% !important;
        height: auto !important;
        min-height: 4.4rem;
        border: 1px solid rgba(148, 163, 184, 0.28);
        border-radius: 6px;
        padding: 0.5rem 0.65rem;
        text-align: left;
    }
    .investment-market-heatmap-overflow-list {
        grid-template-columns: 1fr;
    }
    .investment-market-heatmap-tile.compact small,
    .investment-market-heatmap-tile.minimal small,
    .investment-market-heatmap-tile.minimal .investment-market-heatmap-symbol {
        display: block;
    }
    .investment-market-heatmap-tile.minimal .investment-market-heatmap-name,
    .investment-market-heatmap-tile.minimal strong {
        font-size: 0.9rem;
        -webkit-line-clamp: 2;
    }
    .investment-market-heatmap-pick {
        position: static;
    }
    .investment-market-heatmap-name,
    .investment-market-heatmap-tile strong {
        font-size: 0.9rem;
    }
    .investment-market-heatmap-symbol,
    .investment-market-heatmap-tile small {
        font-size: 0.68rem;
    }
}

.smai-investment-signal-badge {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    border: 1px solid var(--border-default);
    background: rgba(96, 165, 250, 0.12);
    color: var(--text-info);
    font-size: 0.74rem;
    font-weight: 760;
    line-height: 1.3;
    padding: 0.16rem 0.5rem;
}

.smai-investment-signal-badge.buy,
.smai-investment-signal-badge.positive {
    border-color: rgba(52, 211, 153, 0.34);
    background: rgba(52, 211, 153, 0.12);
    color: var(--text-positive);
}

.smai-investment-signal-badge.hold,
.smai-investment-signal-badge.neutral {
    border-color: rgba(251, 191, 36, 0.34);
    background: rgba(251, 191, 36, 0.12);
    color: var(--text-warning);
}

.smai-investment-signal-badge.sell,
.smai-investment-signal-badge.negative,
.smai-investment-signal-badge.risk {
    border-color: rgba(248, 113, 113, 0.34);
    background: rgba(248, 113, 113, 0.12);
    color: var(--text-negative);
}

.smai-risk-alert-box {
    border-color: rgba(251, 113, 133, 0.32);
    background: rgba(42, 14, 28, 0.72);
    color: var(--text-negative);
    padding: 0.8rem 0.9rem;
}

.smai-source-link-list {
    background: rgba(11, 18, 32, 0.72);
    padding: 0.72rem 0.82rem;
}

.smai-source-link-list a {
    color: #7DD3FC;
}

.smai-confidence-meter {
    background: var(--bg-card);
    padding: 0.72rem 0.82rem;
}

.smai-confidence-meter-track {
    height: 0.42rem;
    border-radius: 999px;
    background: rgba(116, 129, 153, 0.22);
    overflow: hidden;
}

.smai-confidence-meter-fill {
    height: 100%;
    width: var(--confidence-width, 0%);
    background: linear-gradient(90deg, var(--ai-blue), var(--ai-cyan));
}

.smai-score-breakdown-table {
    overflow: hidden;
}

.smai-score-breakdown-table table {
    width: 100%;
    border-collapse: collapse;
}

.smai-score-breakdown-table th {
    background: var(--table-header-bg);
    color: var(--text-heading);
}

.smai-score-breakdown-table td {
    background: var(--table-row-bg);
    border-top: 1px solid var(--border-subtle);
    color: var(--text-value);
}

.smai-state-box {
    padding: 0.82rem 0.92rem;
    color: var(--text-secondary);
}

.smai-state-box.loading,
.smai-state-box.info {
    color: var(--text-info);
}

.smai-state-box.success {
    color: var(--text-positive);
}

.smai-state-box.warning {
    color: var(--text-warning);
}

.smai-state-box.error {
    color: var(--text-negative);
}

.smai-state-box.loading,
.smai-state-box.info {
    border-color: var(--ai-border);
    background: rgba(8, 27, 42, 0.72);
}

.smai-state-box.success {
    border-color: rgba(52, 211, 153, 0.32);
    background: rgba(9, 38, 30, 0.72);
}

.smai-state-box.warning {
    border-color: rgba(251, 191, 36, 0.34);
    background: rgba(48, 34, 10, 0.72);
}

.smai-state-box.error {
    border-color: rgba(248, 113, 113, 0.34);
    background: rgba(49, 18, 26, 0.72);
}

.smai-app-header {
    position: relative;
    display: grid;
    grid-template-columns: 1fr;
    align-items: center;
    justify-items: center;
    overflow: hidden;
    border-top: 1px solid rgba(34, 211, 238, 0.22);
    border-bottom: 1px solid rgba(34, 211, 238, 0.42);
    background:
        linear-gradient(90deg, rgba(6, 18, 34, 0.52), rgba(17, 31, 53, 0.88) 50%, rgba(6, 18, 34, 0.52)),
        linear-gradient(180deg, rgba(34, 211, 238, 0.08), rgba(2, 5, 16, 0));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        0 18px 38px rgba(2, 8, 23, 0.24);
    padding: 1.05rem 7.2rem 1.15rem;
    margin: 0 0 1.2rem;
    text-align: center;
}

.smai-app-header::after {
    content: "";
    position: absolute;
    left: 50%;
    bottom: -1px;
    width: min(34rem, 54vw);
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--ai-cyan), rgba(45, 212, 191, 0.66), transparent);
    transform: translateX(-50%);
}

.smai-app-header-copy {
    position: relative;
    z-index: 1;
    display: grid;
    justify-items: center;
    width: min(58rem, 100%);
}

.smai-app-title {
    color: var(--text-title);
    font-size: clamp(2rem, 2.8vw, 2.85rem);
    line-height: 1.12;
    font-weight: 860;
    letter-spacing: 0;
    margin: 0;
    text-shadow: 0 12px 28px rgba(96, 165, 250, 0.14);
}

.smai-app-logo {
    display: block;
    width: min(43rem, 72vw);
    max-width: 100%;
    max-height: 8.6rem;
    object-fit: contain;
    object-position: center center;
    filter:
        drop-shadow(0 14px 28px rgba(0, 0, 0, 0.28))
        drop-shadow(0 0 18px rgba(34, 211, 238, 0.16));
}

.smai-app-message {
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 650;
    line-height: 1.55;
    margin: 0.55rem 0 0;
    max-width: 44rem;
}

.smai-app-mascot-wrap {
    position: absolute;
    top: 50%;
    right: 1.2rem;
    width: clamp(4.6rem, 6.2vw, 6.4rem);
    aspect-ratio: 1;
    display: grid;
    place-items: center;
    transform: translateY(-50%);
    border: 1px solid rgba(34, 211, 238, 0.28);
    border-radius: 8px;
    background:
        linear-gradient(180deg, rgba(8, 27, 42, 0.9), rgba(11, 18, 32, 0.92)),
        rgba(8, 13, 24, 0.28);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        0 16px 36px rgba(0, 0, 0, 0.22);
}

.smai-app-mascot {
    width: 82%;
    height: 82%;
    object-fit: cover;
    object-position: center top;
    border-radius: 8px;
    animation: smai-float 4.6s ease-in-out infinite;
}

.smai-page-title {
    position: relative;
    border-top: 1px solid rgba(49, 66, 95, 0.46);
    border-bottom: 1px solid rgba(37, 52, 77, 0.58);
    background: linear-gradient(90deg, rgba(17, 31, 53, 0.46), rgba(7, 13, 25, 0.16) 62%, transparent);
    padding: 1.05rem 1.1rem 1rem 1.35rem;
    margin: 0 0 1rem;
}

.smai-page-title--ranking-compact {
    padding: 0.55rem 0.8rem 0.56rem 0.95rem;
    margin: 0 0 0.45rem;
}

.smai-page-title--ranking-compact .smai-page-title-heading {
    font-size: 1.45rem;
    line-height: 1.12;
}

.smai-page-title--ranking-compact .smai-page-title-subtitle {
    font-size: 0.84rem;
    line-height: 1.35;
    margin-top: 0.24rem;
}

.smai-page-title-accessory {
    position: absolute;
    top: 0.82rem;
    right: 1rem;
    z-index: 2;
    max-width: min(18rem, calc(100% - 2rem));
}

.smai-page-title::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: linear-gradient(180deg, var(--ai-cyan), var(--ai-blue));
}

.smai-page-title--copilot {
    display: grid;
    grid-template-columns: minmax(24rem, 1fr) minmax(16rem, 20rem);
    align-items: center;
    gap: 1rem;
    padding-bottom: 1rem;
}

.smai-page-title-copy {
    min-width: 0;
}

.smai-page-title-row {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.8rem;
    max-width: 100%;
    vertical-align: middle;
}

.smai-page-title-heading {
    color: var(--text-title);
    font-size: clamp(1.7rem, 2.15vw, 2.2rem);
    line-height: 1.16;
    font-weight: 840;
    letter-spacing: 0;
    margin: 0;
}

.smai-page-title-subtitle {
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 620;
    line-height: 1.58;
    margin: 0.55rem 0 0;
}

.smai-page-title-art {
    width: clamp(5.2rem, 9vw, 8.2rem);
    height: clamp(3.2rem, 5.8vw, 5.1rem);
    flex: 0 0 auto;
    display: grid;
    place-items: center;
    pointer-events: none;
}

.smai-page-title-image {
    width: 100%;
    height: 100%;
    object-fit: contain;
    filter: drop-shadow(0 18px 24px rgba(0, 0, 0, 0.28));
    animation: smai-float 5.4s ease-in-out infinite;
}

.smai-copilot-panel {
    position: relative;
    overflow: hidden;
    display: grid;
    grid-template-columns: 5.4rem minmax(0, 1fr);
    align-items: center;
    gap: 0.78rem;
    min-height: 7rem;
    border: 1px solid rgba(34, 211, 238, 0.22);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(8, 27, 42, 0.84), rgba(16, 26, 43, 0.94)),
        var(--ai-bg);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.045),
        0 10px 30px rgba(0, 0, 0, 0.28),
        0 0 0 1px rgba(34, 211, 238, 0.035);
    backdrop-filter: blur(8px);
    padding: 0.72rem 0.82rem;
}

.smai-copilot-panel::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
        repeating-linear-gradient(
            90deg,
            rgba(34, 211, 238, 0.06) 0,
            rgba(34, 211, 238, 0.06) 1px,
            transparent 1px,
            transparent 38px
        ),
        linear-gradient(90deg, rgba(34, 211, 238, 0.08), transparent 64%);
    opacity: 0.72;
}

.smai-copilot-figure,
.smai-insight-avatar {
    position: relative;
    display: grid;
    place-items: center;
}

.smai-copilot-figure {
    min-width: 5.4rem;
    height: 6rem;
}

.smai-copilot-aura {
    position: absolute;
    width: 4.5rem;
    height: 4.5rem;
    border: 1px solid rgba(34, 211, 238, 0.18);
    border-radius: 8px;
    background:
        linear-gradient(180deg, rgba(34, 211, 238, 0.1), rgba(96, 165, 250, 0.045)),
        rgba(8, 27, 42, 0.42);
    animation: smai-soft-glow 4.8s ease-in-out infinite;
}

.smai-copilot-image {
    position: relative;
    z-index: 1;
    width: 5rem;
    height: 6rem;
    object-fit: contain;
    filter:
        drop-shadow(0 10px 18px rgba(0, 0, 0, 0.32))
        drop-shadow(0 0 12px rgba(34, 211, 238, 0.16));
    animation: smai-copilot-float 4.6s ease-in-out infinite;
}

.smai-copilot-copy {
    position: relative;
    z-index: 1;
    min-width: 0;
}

.smai-copilot-label {
    color: var(--text-ai-title);
    font-size: 0.9rem;
    font-weight: 820;
    line-height: 1.25;
}

.smai-copilot-status {
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    margin-top: 0.34rem;
    color: var(--text-ai-muted);
    font-size: 0.82rem;
    font-weight: 700;
    line-height: 1.35;
}

.smai-copilot-status-dot {
    width: 0.46rem;
    height: 0.46rem;
    border-radius: 999px;
    background: var(--signal-buy);
    box-shadow: 0 0 12px rgba(52, 211, 153, 0.42);
    animation: smai-status-breathe 3.8s ease-in-out infinite;
}

.smai-copilot-message {
    color: var(--text-ai-primary);
    font-size: 0.84rem;
    line-height: 1.58;
    margin: 0.48rem 0 0;
}

.smai-page-title--copilot[data-mascot="cockpit"] {
    grid-template-columns: minmax(22rem, 1fr) minmax(13rem, 17rem);
    padding-top: 0.84rem;
    padding-bottom: 0.82rem;
}

.smai-page-title--copilot[data-mascot="cockpit"] .smai-page-title-heading {
    font-size: clamp(1.55rem, 2vw, 2rem);
}

.smai-page-title--copilot[data-mascot="cockpit"] .smai-page-title-subtitle {
    margin-top: 0.42rem;
    font-size: 0.9rem;
}

.smai-page-title--copilot[data-mascot="cockpit"] .smai-page-title-art {
    width: clamp(4.4rem, 7vw, 6.6rem);
    height: clamp(2.8rem, 4.7vw, 4.2rem);
}

.smai-page-title--copilot[data-mascot="cockpit"] .smai-copilot-panel {
    grid-template-columns: 4.5rem minmax(0, 1fr);
    gap: 0.58rem;
    min-height: 5.85rem;
    padding: 0.58rem 0.68rem;
}

.smai-page-title--copilot[data-mascot="cockpit"] .smai-copilot-figure {
    min-width: 4.5rem;
    height: 4.95rem;
}

.smai-page-title--copilot[data-mascot="cockpit"] .smai-copilot-aura {
    width: 3.8rem;
    height: 3.8rem;
}

.smai-page-title--copilot[data-mascot="cockpit"] .smai-copilot-image {
    width: 4.15rem;
    height: 4.95rem;
}

.smai-page-title--copilot[data-mascot="cockpit"] .smai-copilot-message {
    margin-top: 0.36rem;
    font-size: 0.8rem;
    line-height: 1.45;
}

.smai-cockpit-prefetch-header,
.smai-cockpit-filter-summary {
    margin: 0.55rem 0 0.38rem;
}

.smai-cockpit-filter-summary {
    border: 1px solid rgba(49, 66, 95, 0.62);
    border-radius: 8px;
    background: rgba(17, 31, 53, 0.28);
    padding: 0.8rem 0.95rem;
}

.smai-cockpit-prefetch-heading {
    color: var(--text-heading);
    font-size: 0.98rem;
    font-weight: 820;
    line-height: 1.3;
}

.smai-cockpit-prefetch-caption {
    color: var(--text-caption);
    font-size: 0.83rem;
    font-weight: 620;
    line-height: 1.5;
    margin: 0.22rem 0 0;
}

.smai-cockpit-controls-anchor,
.smai-cockpit-favorites-toggle-anchor,
.smai-cockpit-detail-action-anchor {
    display: none;
}

[data-testid="stMarkdownContainer"]:has(.smai-cockpit-controls-anchor) {
    display: none;
}

[data-testid="stMarkdownContainer"]:has(.smai-cockpit-controls-anchor)
    + div[data-testid="stHorizontalBlock"]
    div[data-baseweb="select"] > div,
[data-testid="stMarkdownContainer"]:has(.smai-cockpit-controls-anchor)
    + div[data-testid="stHorizontalBlock"]
    [data-testid="stTextInput"] input,
[data-testid="stMarkdownContainer"]:has(.smai-cockpit-controls-anchor)
    + div[data-testid="stHorizontalBlock"]
    [data-testid="stButton"] button {
    min-height: 2.65rem;
}

.smai-cockpit-symbol-name-field {
    display: grid;
    grid-template-rows: 1.5rem 2.65rem;
    min-width: 0;
}

.smai-cockpit-symbol-name-label {
    display: flex;
    align-items: center;
    color: var(--text-label);
    font-size: 0.875rem;
    font-weight: 680;
    line-height: 1.25;
}

.smai-cockpit-symbol-name-value {
    display: flex;
    align-items: center;
    min-width: 0;
    overflow: hidden;
    border-bottom: 1px solid rgba(103, 232, 249, 0.34);
    color: var(--text-value);
    font-size: 0.93rem;
    font-weight: 760;
    line-height: 1.3;
    text-overflow: ellipsis;
    white-space: nowrap;
}

[data-testid="stMarkdownContainer"]:has(.smai-cockpit-favorites-toggle-anchor) {
    display: none;
}

div[data-testid="stColumn"]:has(.smai-cockpit-favorites-toggle-anchor) {
    min-height: 1.5rem;
}

div[data-testid="stColumn"]:has(.smai-cockpit-favorites-toggle-anchor)
    div[data-testid="stToggle"] {
    display: flex;
    justify-content: flex-end;
    min-height: 1.5rem;
    margin: 0.2rem 0 0;
}

div[data-testid="stColumn"]:has(.smai-cockpit-favorites-toggle-anchor)
    div[data-testid="stToggle"] label {
    width: auto;
    margin-left: auto;
    justify-content: flex-end;
}

[data-testid="stMarkdownContainer"]:has(.smai-cockpit-detail-action-anchor) {
    display: none;
}

[data-testid="stMarkdownContainer"]:has(.smai-cockpit-detail-action-anchor)
    + div[data-testid="stButton"] {
    margin-top: 1.5rem;
}

.smai-cockpit-filter-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.44rem;
    margin-top: 0.58rem;
}

.smai-cockpit-filter-chip {
    display: inline-flex;
    align-items: center;
    min-height: 1.72rem;
    border: 1px solid rgba(49, 66, 95, 0.78);
    border-radius: 999px;
    background: rgba(7, 13, 25, 0.76);
    color: var(--text-secondary);
    font-size: 0.78rem;
    font-weight: 720;
    line-height: 1.25;
    padding: 0.32rem 0.66rem;
    white-space: nowrap;
}

.smai-cockpit-filter-chip--active {
    border-color: rgba(34, 211, 238, 0.48);
    background: rgba(8, 81, 104, 0.28);
    color: var(--text-ai-primary);
}

.smai-cockpit-filter-chip--count {
    border-color: rgba(96, 165, 250, 0.46);
    background: rgba(29, 78, 216, 0.2);
    color: var(--text-info);
}

.smai-cockpit-filter-detail-anchor {
    height: 0.2rem;
}

.smai-floating-assistant {
    position: fixed;
    right: 0;
    bottom: 0;
    z-index: 9998;
    width: min(25.5rem, calc(100vw - 0.5rem));
    color: var(--text-primary);
}

.smai-floating-assistant-toggle {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
}

.smai-floating-assistant-trigger {
    position: relative;
    z-index: 4;
    display: grid;
    grid-template-columns: 3.95rem minmax(0, 1fr);
    align-items: center;
    gap: 0.62rem;
    min-width: 14.4rem;
    max-width: min(23rem, calc(100vw - 2rem));
    margin-left: auto;
    width: fit-content;
    border: 1px solid rgba(34, 211, 238, 0.24);
    border-radius: 999px;
    background:
        linear-gradient(90deg, rgba(8, 47, 73, 0.9), rgba(13, 24, 43, 0.94)),
        var(--ai-bg);
    box-shadow:
        0 16px 36px rgba(0, 0, 0, 0.34),
        0 0 18px rgba(34, 211, 238, 0.12);
    cursor: pointer;
    padding: 0.38rem 0.8rem 0.38rem 0.35rem;
    transition:
        transform 160ms ease,
        border-color 160ms ease,
        box-shadow 160ms ease;
}

.smai-floating-assistant-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 1;
    background: transparent;
    cursor: default;
}

.smai-floating-assistant-toggle:checked ~ .smai-floating-assistant-backdrop {
    display: block;
}

.smai-floating-assistant-trigger:hover {
    transform: translateY(-2px) scale(1.008);
    border-color: rgba(45, 212, 191, 0.52);
    box-shadow:
        0 20px 42px rgba(0, 0, 0, 0.38),
        0 0 22px rgba(45, 212, 191, 0.16);
}

.smai-floating-assistant-avatar {
    position: relative;
    display: grid;
    place-items: center;
    width: 3.76rem;
    height: 3.76rem;
    border: 1px solid rgba(34, 211, 238, 0.24);
    border-radius: 999px;
    background:
        radial-gradient(circle at 52% 20%, rgba(34, 211, 238, 0.24), transparent 58%),
        radial-gradient(circle at 76% 74%, rgba(16, 185, 129, 0.16), transparent 42%),
        rgba(2, 8, 23, 0.62);
    overflow: hidden;
    isolation: isolate;
}

.smai-floating-assistant-avatar::before {
    content: "";
    position: absolute;
    inset: 0.34rem;
    border-radius: 999px;
    background: rgba(34, 211, 238, 0.1);
    filter: blur(8px);
    animation: smai-soft-glow 4.8s ease-in-out infinite;
}

.smai-floating-assistant-avatar::after {
    content: "";
    position: absolute;
    z-index: 8;
    inset: 0.14rem;
    border: 1px solid rgba(103, 232, 249, 0.34);
    border-radius: inherit;
    box-shadow: inset 0 0 18px rgba(2, 8, 23, 0.34);
    pointer-events: none;
}

.smai-floating-assistant-stage {
    position: relative;
    display: grid;
    place-items: center;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    overflow: hidden;
    transform-origin: 50% 78%;
    animation: smai-buddy-presence 7.4s cubic-bezier(0.34, 0, 0.2, 1) infinite;
}

.smai-floating-assistant-trigger:hover .smai-floating-assistant-stage {
    animation:
        smai-buddy-notice 920ms cubic-bezier(0.2, 0.82, 0.22, 1) both,
        smai-buddy-presence 7.4s cubic-bezier(0.34, 0, 0.2, 1) 920ms infinite;
}

.smai-assistant-orbit {
    position: absolute;
    inset: 0.24rem;
    border: 1px solid rgba(125, 211, 252, 0.18);
    border-radius: 999px;
    background:
        linear-gradient(145deg, transparent 20%, rgba(34, 211, 238, 0.18) 42%, transparent 58%),
        radial-gradient(circle at 30% 22%, rgba(255, 255, 255, 0.12), transparent 18%);
    opacity: 0.48;
    transform-origin: 52% 54%;
    animation: smai-buddy-orbit 8.8s ease-in-out infinite;
}

.smai-floating-assistant-avatar--forecast .smai-assistant-orbit {
    border-color: rgba(34, 211, 238, 0.34);
}

.smai-floating-assistant-avatar--ranking .smai-assistant-orbit {
    border-color: rgba(167, 139, 250, 0.34);
}

.smai-floating-assistant-avatar--direction .smai-assistant-orbit {
    border-color: rgba(251, 191, 36, 0.36);
}

.smai-floating-assistant-character {
    position: relative;
    z-index: 4;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    object-fit: cover;
    object-position: center center;
    filter: saturate(1.06) contrast(1.04);
    transform-origin: 50% 72%;
    animation: smai-buddy-curious 8.4s cubic-bezier(0.32, 0, 0.18, 1) infinite;
}

.smai-assistant-holo-chart {
    position: absolute;
    z-index: 3;
    right: 0.28rem;
    bottom: 0.68rem;
    width: 2.12rem;
    height: 1.34rem;
    border: 1px solid rgba(34, 211, 238, 0.36);
    border-radius: 7px;
    background:
        linear-gradient(180deg, rgba(34, 211, 238, 0.16), rgba(15, 23, 42, 0.12)),
        repeating-linear-gradient(
            0deg,
            rgba(148, 163, 184, 0.12) 0,
            rgba(148, 163, 184, 0.12) 1px,
            transparent 1px,
            transparent 0.32rem
        );
    box-shadow:
        0 0 18px rgba(34, 211, 238, 0.22),
        inset 0 0 12px rgba(34, 211, 238, 0.12);
    opacity: 0;
    transform: translate(0.38rem, 0.18rem) scale(0.76) rotate(-5deg);
    transform-origin: 18% 100%;
    animation: smai-holo-peek 7.1s cubic-bezier(0.34, 0, 0.2, 1) infinite;
}

.smai-floating-assistant-avatar--forecast .smai-assistant-holo-chart {
    opacity: 0.86;
}

.smai-assistant-holo-range {
    position: absolute;
    right: 0.16rem;
    bottom: 0.14rem;
    width: 1.24rem;
    height: 0.8rem;
    border-radius: 999px 999px 6px 6px;
    background: linear-gradient(135deg, rgba(45, 212, 191, 0.14), rgba(251, 191, 36, 0.18));
    clip-path: polygon(0 58%, 100% 8%, 100% 100%, 0 76%);
    opacity: 0.68;
    animation: smai-holo-range-breathe 6.4s ease-in-out infinite;
}

.smai-assistant-holo-line {
    position: absolute;
    left: 0.24rem;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(34, 211, 238, 0.18), rgba(103, 232, 249, 0.92));
    box-shadow: 0 0 8px rgba(34, 211, 238, 0.5);
    transform-origin: left center;
}

.smai-assistant-holo-line.line-a {
    bottom: 0.38rem;
    width: 0.66rem;
    transform: rotate(-20deg);
    animation: smai-holo-line-a 6.5s ease-in-out infinite;
}

.smai-assistant-holo-line.line-b {
    bottom: 0.58rem;
    left: 0.78rem;
    width: 0.56rem;
    transform: rotate(25deg);
    animation: smai-holo-line-b 6.5s ease-in-out infinite;
}

.smai-assistant-holo-line.line-c {
    bottom: 0.83rem;
    left: 1.25rem;
    width: 0.72rem;
    transform: rotate(-12deg);
    animation: smai-holo-line-c 6.5s ease-in-out infinite;
}

.smai-assistant-rank-bars {
    position: absolute;
    z-index: 3;
    right: 0.48rem;
    bottom: 0.72rem;
    display: none;
    align-items: end;
    gap: 0.12rem;
    width: 1.22rem;
    height: 1.12rem;
    opacity: 0.76;
    transform: rotate(-5deg);
}

.smai-floating-assistant-avatar--ranking .smai-assistant-rank-bars {
    display: flex;
}

.smai-floating-assistant-avatar--ranking .smai-assistant-holo-chart {
    display: none;
}

.smai-assistant-rank-bars span {
    display: block;
    width: 0.24rem;
    border-radius: 999px 999px 4px 4px;
    background: linear-gradient(180deg, rgba(167, 139, 250, 0.9), rgba(34, 211, 238, 0.32));
    box-shadow: 0 0 8px rgba(167, 139, 250, 0.28);
    animation: smai-rank-bars 5.9s ease-in-out infinite;
}

.smai-assistant-rank-bars span:nth-child(1) {
    height: 0.48rem;
    animation-delay: -1.4s;
}

.smai-assistant-rank-bars span:nth-child(2) {
    height: 0.86rem;
    animation-delay: -0.5s;
}

.smai-assistant-rank-bars span:nth-child(3) {
    height: 0.64rem;
    animation-delay: -2.1s;
}

.smai-floating-assistant-trigger-copy {
    display: grid;
    gap: 0.12rem;
    min-width: 0;
}

.smai-floating-assistant-kicker {
    color: var(--text-ai-title);
    font-size: 0.76rem;
    font-weight: 820;
    letter-spacing: 0;
}

.smai-floating-assistant-trigger-copy strong {
    color: var(--text-value);
    font-size: 0.9rem;
    font-weight: 850;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.smai-floating-assistant-body {
    display: none;
    position: relative;
    z-index: 3;
    max-height: min(66vh, 34rem);
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    border: 1px solid rgba(34, 211, 238, 0.28);
    border-radius: 10px;
    background:
        linear-gradient(135deg, rgba(17, 31, 53, 0.98), rgba(8, 15, 29, 0.98)),
        var(--bg-card);
    box-shadow:
        0 22px 54px rgba(0, 0, 0, 0.44),
        inset 0 1px 0 rgba(255, 255, 255, 0.045);
    font-size: 0.84rem;
    margin-bottom: 0.62rem;
    padding: 0.92rem;
}

.smai-floating-assistant-toggle:checked ~ .smai-floating-assistant-body {
    display: block;
}

.smai-floating-assistant-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.16);
    padding-bottom: 0.72rem;
}

.smai-floating-assistant-head h3 {
    color: var(--text-title);
    font-size: 0.98rem;
    font-weight: 860;
    line-height: 1.2;
    margin: 0.12rem 0 0;
}

.smai-floating-assistant-head > span {
    flex: 0 0 auto;
    border: 1px solid rgba(45, 212, 191, 0.38);
    border-radius: 999px;
    color: var(--smai-teal);
    font-size: 0.72rem;
    font-weight: 800;
    line-height: 1.2;
    max-width: 11rem;
    overflow: hidden;
    padding: 0.3rem 0.52rem;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.smai-floating-assistant-lead {
    color: var(--text-secondary);
    font-size: 0.82rem;
    font-weight: 650;
    line-height: 1.55;
    margin: 0.74rem 0 0.68rem;
}

.smai-floating-assistant-localqa {
    display: grid;
    gap: 0.68rem;
}

.smai-floating-assistant-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.42rem;
}

.smai-floating-assistant-qa-item {
    display: inline-flex;
}

.smai-floating-assistant-chip,
.smai-floating-assistant-context-link {
    border: 1px solid rgba(34, 211, 238, 0.28);
    border-radius: 999px;
    background: rgba(8, 47, 73, 0.42);
    color: var(--text-ai-primary) !important;
    display: inline-flex;
    font-size: 0.75rem;
    font-weight: 780;
    list-style: none;
    line-height: 1.25;
    padding: 0.38rem 0.58rem;
    text-decoration: none !important;
}

.smai-floating-assistant-chip {
    cursor: pointer;
    user-select: none;
}

.smai-floating-assistant-chip::-webkit-details-marker {
    display: none;
}

.smai-floating-assistant-chip::marker {
    content: "";
}

.smai-floating-assistant-chip > span {
    pointer-events: none;
}

.smai-floating-assistant-chip:hover,
.smai-floating-assistant-context-link:hover {
    border-color: rgba(45, 212, 191, 0.64);
    background: rgba(13, 148, 136, 0.2);
    color: var(--text-value) !important;
}

.smai-floating-assistant-chip:focus-visible {
    outline: 2px solid rgba(103, 232, 249, 0.48);
    outline-offset: 2px;
}

.smai-floating-assistant-qa-item[open] > .smai-floating-assistant-chip {
    border-color: rgba(103, 232, 249, 0.72);
    background: rgba(8, 145, 178, 0.28);
    box-shadow: inset 0 0 0 1px rgba(103, 232, 249, 0.14);
    color: var(--text-value) !important;
}

.smai-floating-assistant-qa-item[open] > .smai-floating-assistant-chip {
    pointer-events: none;
}

.smai-floating-assistant-answer-panel {
    display: none;
}

.smai-floating-assistant-localqa:has(.smai-floating-assistant-qa-item--1[open])
    .smai-floating-assistant-answer-panel--1,
.smai-floating-assistant-localqa:has(.smai-floating-assistant-qa-item--2[open])
    .smai-floating-assistant-answer-panel--2,
.smai-floating-assistant-localqa:has(.smai-floating-assistant-qa-item--3[open])
    .smai-floating-assistant-answer-panel--3,
.smai-floating-assistant-localqa:has(.smai-floating-assistant-qa-item--4[open])
    .smai-floating-assistant-answer-panel--4,
.smai-floating-assistant-localqa:has(.smai-floating-assistant-qa-item--5[open])
    .smai-floating-assistant-answer-panel--5,
.smai-floating-assistant-localqa:has(.smai-floating-assistant-qa-item--6[open])
    .smai-floating-assistant-answer-panel--6 {
    display: block;
}

.smai-floating-assistant-chat {
    display: grid;
    gap: 0.58rem;
}

.smai-floating-assistant-user {
    justify-self: end;
    max-width: 92%;
    border: 1px solid rgba(96, 165, 250, 0.34);
    border-radius: 8px;
    background: rgba(30, 64, 175, 0.22);
    color: var(--text-value);
    font-size: 0.8rem;
    font-weight: 780;
    line-height: 1.45;
    padding: 0.58rem 0.68rem;
}

.smai-floating-assistant-answer {
    border: 1px solid rgba(45, 212, 191, 0.24);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.08), transparent 75%),
        rgba(2, 8, 23, 0.42);
    color: var(--text-secondary);
    font-size: 0.8rem;
    line-height: 1.55;
    padding: 0.76rem 0.82rem;
}

.smai-floating-assistant-answer > strong {
    color: var(--text-value);
    display: block;
    font-size: 0.84rem;
    line-height: 1.48;
    margin-bottom: 0.54rem;
}

.smai-floating-assistant-answer p {
    margin: 0.28rem 0 0;
}

.smai-floating-assistant-block {
    margin-top: 0.62rem;
}

.smai-floating-assistant-block span,
.smai-floating-assistant-contexts span {
    color: var(--text-ai-title);
    display: block;
    font-size: 0.73rem;
    font-weight: 820;
    margin-bottom: 0.26rem;
}

.smai-floating-assistant-block ul {
    margin: 0.24rem 0 0 1.05rem;
    padding: 0;
}

.smai-floating-assistant-block li {
    margin-bottom: 0.24rem;
}

.smai-floating-assistant-contexts {
    border-top: 1px solid rgba(148, 163, 184, 0.16);
    display: flex;
    flex-wrap: wrap;
    gap: 0.42rem;
    margin-top: 0.78rem;
    padding-top: 0.68rem;
}

.smai-floating-assistant-contexts span {
    flex: 0 0 100%;
}

.smai-copilot-chat-topbar {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 1.25rem;
    width: min(var(--smai-content-max-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-content-max-width);
    margin: 0.85rem auto 0.88rem;
    box-sizing: border-box;
    border: 1px solid rgba(34, 211, 238, 0.3);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.12), transparent 42%),
        linear-gradient(180deg, rgba(14, 25, 44, 0.94), rgba(5, 10, 20, 0.9)),
        var(--surface-base);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        0 18px 48px rgba(0, 0, 0, 0.22);
    padding: 1.05rem 1.28rem;
}

.smai-copilot-header-identity {
    grid-column: 1 / 3;
    display: flex;
    align-items: center;
    gap: 0.82rem;
    min-width: 0;
}

.smai-copilot-header-icon {
    flex: 0 0 auto;
    width: 4.3rem;
    height: 4.3rem;
    border-radius: 999px;
    background:
        radial-gradient(circle at 50% 40%, rgba(34, 211, 238, 0.18), transparent 62%),
        rgba(2, 8, 23, 0.38);
    border: 1px solid rgba(125, 211, 252, 0.34);
    box-shadow:
        0 0 24px rgba(34, 211, 238, 0.22),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
    overflow: hidden;
}

.smai-copilot-header-title {
    min-width: 0;
}

.smai-copilot-header-icon img {
    display: block;
    width: 118%;
    height: 118%;
    object-fit: contain;
    transform: translate(-7%, -8%);
}

.smai-copilot-eyebrow {
    display: block;
    color: var(--text-ai-title);
    font-size: 0.78rem;
    font-weight: 850;
    line-height: 1.3;
    margin-bottom: 0.18rem;
}

.smai-copilot-chat-topbar h1 {
    color: var(--text-title);
    font-size: 1.42rem;
    line-height: 1.15;
    margin: 0;
}

.smai-copilot-chat-topbar p {
    color: var(--text-secondary);
    font-size: 0.92rem;
    line-height: 1.55;
    margin: 0.24rem 0 0;
    max-width: 58rem;
}

.smai-copilot-statusbar {
    grid-column: 3;
    display: grid;
    grid-template-columns: auto auto;
    align-items: center;
    gap: 0.14rem 0.45rem;
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 8px;
    background:
        linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(2, 8, 23, 0.2)),
        rgba(8, 47, 73, 0.28);
    padding: 0.55rem 0.72rem;
    width: 13.75rem;
    max-width: 15rem;
    min-width: 0;
}

.smai-copilot-statusbar--ready {
    border-color: rgba(52, 211, 153, 0.36);
    background:
        linear-gradient(135deg, rgba(20, 184, 166, 0.12), rgba(2, 8, 23, 0.2)),
        rgba(8, 47, 73, 0.28);
}

.smai-copilot-statusbar--fallback,
.smai-copilot-statusbar--checking {
    border-color: rgba(56, 189, 248, 0.34);
    background:
        linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(2, 8, 23, 0.2)),
        rgba(15, 23, 42, 0.32);
}

.smai-copilot-statusbar--warning {
    border-color: rgba(251, 191, 36, 0.44);
    background:
        linear-gradient(135deg, rgba(251, 191, 36, 0.14), rgba(2, 8, 23, 0.22)),
        rgba(69, 26, 3, 0.24);
}

.smai-copilot-statusbar--error {
    border-color: rgba(248, 113, 113, 0.44);
    background:
        linear-gradient(135deg, rgba(248, 113, 113, 0.14), rgba(2, 8, 23, 0.22)),
        rgba(69, 10, 10, 0.22);
}

.smai-copilot-chat-status-dot {
    width: 0.58rem;
    height: 0.58rem;
    border-radius: 999px;
    background: #38bdf8;
    box-shadow: 0 0 0 0.2rem rgba(56, 189, 248, 0.12);
}

.smai-copilot-statusbar--ready .smai-copilot-chat-status-dot {
    background: #34d399;
    box-shadow: 0 0 0 0.2rem rgba(52, 211, 153, 0.12);
}

.smai-copilot-statusbar--warning .smai-copilot-chat-status-dot {
    background: #fbbf24;
    box-shadow: 0 0 0 0.2rem rgba(251, 191, 36, 0.16);
}

.smai-copilot-statusbar--error .smai-copilot-chat-status-dot {
    background: #fb7185;
    box-shadow: 0 0 0 0.2rem rgba(251, 113, 133, 0.16);
}

.smai-copilot-statusbar strong {
    color: var(--text-title);
    font-size: 0.92rem;
    line-height: 1.2;
}

.smai-copilot-statusbar small {
    grid-column: 2;
    color: var(--text-secondary);
    font-size: 0.72rem;
    font-weight: 760;
}

.smai-copilot-chat-actions-anchor {
    width: min(var(--smai-content-max-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-content-max-width);
    height: 0;
    margin: -0.3rem auto 0;
}

div[data-testid="stElementContainer"]:has(.smai-copilot-chat-actions-anchor)
    + div[data-testid="stElementContainer"]
    div[data-testid="stHorizontalBlock"],
div[data-testid="stElementContainer"]:has(.smai-copilot-chat-actions-anchor)
    + div[data-testid="stHorizontalBlock"] {
    width: min(var(--smai-content-max-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-content-max-width);
    margin: -0.3rem auto 0.62rem;
    box-sizing: border-box;
}

div[data-testid="stElementContainer"]:has(.smai-copilot-chat-actions-anchor)
    + div[data-testid="stElementContainer"]
    div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-copilot-chat-actions-anchor)
    + div[data-testid="stHorizontalBlock"]
    div[data-testid="stButton"] button {
    min-height: 2.15rem;
    border-radius: 8px;
    white-space: nowrap;
}

.smai-copilot-mode-label {
    width: min(var(--smai-content-max-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-content-max-width);
    margin: 0 auto 0.36rem;
    box-sizing: border-box;
    color: var(--text-ai-title);
    font-size: 0.8rem;
    font-weight: 840;
}

.smai-copilot-material-status {
    width: min(var(--smai-content-max-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-content-max-width);
    margin: 0 auto 0.72rem;
    box-sizing: border-box;
    border: 1px solid rgba(71, 85, 105, 0.44);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.46);
    padding: 0.68rem 0.76rem;
}

.smai-copilot-material-status > span {
    display: block;
    color: var(--text-ai-title);
    font-size: 0.78rem;
    font-weight: 840;
}

div[data-testid="stChatMessage"] {
    max-width: 64rem;
    margin-left: auto;
    margin-right: auto;
}

div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
    line-height: 1.72;
}

.smai-copilot-suggestions-title {
    width: min(var(--smai-content-max-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-content-max-width);
    margin: 0.86rem auto 0.44rem;
    box-sizing: border-box;
    color: var(--text-ai-title);
    font-size: 0.82rem;
    font-weight: 840;
}

.smai-copilot-composer-toolbar {
    height: 0;
    margin: 0;
    overflow: hidden;
}

[data-testid="stAppViewContainer"] .main .block-container:has(.smai-copilot-composer-toolbar) {
    padding-bottom: 8.5rem;
}

div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
        div[data-testid="stForm"]
    ),
div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
    + div[data-testid="stHorizontalBlock"],
div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
    + div[data-testid="stElementContainer"]
    div[data-testid="stHorizontalBlock"] {
    position: fixed;
    z-index: 850;
    right: 0;
    bottom: 0;
    left: 21rem;
    box-sizing: border-box;
    width: auto;
    margin: 0;
    padding: 0.62rem max(1.5rem, calc((100vw - 21rem - var(--smai-chat-main-width)) / 2));
    border-top: 1px solid rgba(71, 85, 105, 0.54);
    background: linear-gradient(180deg, rgba(3, 10, 24, 0.9), rgba(3, 10, 24, 0.98));
    box-shadow: 0 -16px 40px rgba(0, 0, 0, 0.24);
    backdrop-filter: blur(14px);
}

:is(
        .smai-copilot-composer-toolbar,
        div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
                div[data-testid="stForm"]
            ),
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stElementContainer"]
            div[data-testid="stHorizontalBlock"]
    )
    div[data-testid="stForm"] {
    border: 0;
    padding: 0;
    background: transparent;
}

:is(
        .smai-copilot-composer-toolbar,
        div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
                div[data-testid="stForm"]
            ),
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stElementContainer"]
            div[data-testid="stHorizontalBlock"]
    )
    div[data-testid="stTextInput"] input {
    min-width: 0;
    box-sizing: border-box;
    border-color: rgba(34, 211, 238, 0.28);
    background: rgba(15, 23, 42, 0.72);
}

:is(
        .smai-copilot-composer-toolbar,
        div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
                div[data-testid="stForm"]
            ),
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stElementContainer"]
            div[data-testid="stHorizontalBlock"]
    )
    div[data-testid="stTextInput"] input:is(:focus, :focus-visible) {
    border-color: rgba(45, 212, 191, 0.64) !important;
    outline: none !important;
    box-shadow:
        inset 0 0 0 1px rgba(45, 212, 191, 0.18),
        0 0 0 0.18rem rgba(34, 211, 238, 0.12) !important;
}

:is(
        .smai-copilot-composer-toolbar,
        div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
                div[data-testid="stForm"]
            ),
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stElementContainer"]
            div[data-testid="stHorizontalBlock"]
    )
    div[data-testid="stTextInput"] input[aria-invalid="true"] {
    border-color: rgba(251, 113, 133, 0.68) !important;
    box-shadow:
        inset 0 0 0 1px rgba(251, 113, 133, 0.16),
        0 0 0 0.18rem rgba(251, 113, 133, 0.12) !important;
}

:is(
        .smai-copilot-composer-toolbar,
        div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
                div[data-testid="stForm"]
            ),
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
            + div[data-testid="stElementContainer"]
            div[data-testid="stHorizontalBlock"]
    )
    :is(div[data-testid="stButton"], div[data-testid="stFormSubmitButton"])
    button {
    min-height: 2.45rem;
    white-space: nowrap;
    border-radius: 8px;
}

div[data-testid="stChatInput"] {
    width: min(var(--smai-chat-main-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-chat-main-width);
    margin-left: auto;
    margin-right: auto;
    box-sizing: border-box;
}

div[data-testid="stChatInput"] > div {
    box-sizing: border-box;
}

div[data-testid="stChatInput"] textarea {
    box-sizing: border-box !important;
    border-color: rgba(34, 211, 238, 0.28) !important;
    background:
        linear-gradient(180deg, rgba(15, 23, 42, 0.78), rgba(2, 6, 23, 0.74)),
        rgba(8, 47, 73, 0.18) !important;
    box-shadow:
        inset 0 0 0 1px rgba(34, 211, 238, 0.08),
        0 10px 24px rgba(0, 0, 0, 0.16) !important;
}

div[data-testid="stChatInput"] textarea:focus {
    border-color: rgba(45, 212, 191, 0.58) !important;
    box-shadow:
        inset 0 0 0 1px rgba(45, 212, 191, 0.18),
        0 0 22px rgba(34, 211, 238, 0.13) !important;
}

.smai-copilot-thread {
    display: flex;
    flex-direction: column;
    gap: 1.1rem;
    width: min(var(--smai-chat-main-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-chat-main-width);
    margin: 0.86rem auto 1.1rem;
    box-sizing: border-box;
}

.smai-copilot-message-row {
    display: flex;
    align-items: flex-start;
    gap: 0.72rem;
    width: 100%;
}

.smai-copilot-message-row--assistant {
    justify-content: flex-start;
}

.smai-copilot-message-row--user {
    justify-content: flex-end;
}

.smai-copilot-message-card {
    min-width: 0;
    max-width: min(64rem, 100%);
    border-radius: 8px;
    padding: 0.78rem 0.86rem;
}

.smai-copilot-message-card p {
    margin: 0.32rem 0 0;
    line-height: 1.62;
}

.smai-copilot-message-card p.smai-copilot-natural-lead {
    color: var(--text-value);
    font-size: 0.94rem;
    line-height: 1.72;
    white-space: pre-line;
}

.smai-copilot-inline-sections {
    display: grid;
    gap: 0.58rem;
    margin-top: 0.72rem;
}

.smai-copilot-inline-section {
    border-left: 2px solid rgba(45, 212, 191, 0.58);
    padding-left: 0.68rem;
}

.smai-copilot-inline-section span {
    display: block;
    color: var(--text-ai-title);
    font-size: 0.78rem;
    font-weight: 820;
    margin-bottom: 0.26rem;
}

.smai-copilot-inline-section ul {
    margin: 0;
    padding-left: 1rem;
    color: var(--text-secondary);
    font-size: 0.84rem;
    line-height: 1.55;
}

.smai-copilot-message-card--assistant {
    width: min(55rem, calc(100% - 3.8rem));
    min-height: 6.5rem;
    border: 1px solid var(--smai-border);
    border-left: 3px solid var(--smai-teal);
    background:
        linear-gradient(90deg, rgba(45, 212, 191, 0.14), transparent 62%),
        linear-gradient(180deg, rgba(23, 35, 56, 0.9), rgba(11, 18, 32, 0.9));
    color: var(--text-secondary);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        var(--shadow-subtle);
}

.smai-copilot-message-card--pending {
    min-height: 8.5rem;
    background:
        linear-gradient(90deg, rgba(45, 212, 191, 0.1), transparent 54%),
        linear-gradient(180deg, rgba(18, 29, 48, 0.82), rgba(8, 15, 28, 0.84));
}

.smai-copilot-message-card--pending .smai-copilot-natural-lead {
    color: var(--text-secondary);
}

.smai-copilot-pending-dots {
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    margin-top: 0.52rem;
}

.smai-copilot-pending-dots span {
    width: 0.36rem;
    height: 0.36rem;
    border-radius: 999px;
    background: var(--text-ai-title);
    opacity: 0.34;
    animation: smai-copilot-pending-dot 1.15s ease-in-out infinite;
}

.smai-copilot-pending-dots span:nth-child(2) {
    animation-delay: 140ms;
}

.smai-copilot-pending-dots span:nth-child(3) {
    animation-delay: 280ms;
}

.smai-copilot-pending-steps {
    margin-top: 0.72rem;
    border: 1px solid rgba(45, 212, 191, 0.24);
    border-radius: 8px;
    padding: 0.64rem 0.72rem;
    background: rgba(8, 47, 73, 0.22);
}

.smai-copilot-pending-caption {
    display: block;
    color: var(--text-ai-title);
    font-size: 0.76rem;
    font-weight: 850;
    line-height: 1.25;
}

.smai-copilot-pending-current {
    display: flex;
    align-items: center;
    gap: 0.52rem;
    min-height: 1.7rem;
    margin-top: 0.5rem;
}

.smai-copilot-pending-current-dot {
    flex: 0 0 auto;
    width: 0.46rem;
    height: 0.46rem;
    border-radius: 999px;
    background: var(--text-ai-title);
    box-shadow: 0 0 0 0 rgba(45, 212, 191, 0.34);
    animation: smai-copilot-pending-pulse 1.7s ease-in-out infinite;
}

.smai-copilot-pending-current-label {
    color: var(--text-secondary);
    font-size: 0.9rem;
    font-weight: 760;
    line-height: 1.35;
}

.smai-copilot-tool-progress {
    margin-top: 0.8rem;
    padding: 0.78rem 0.9rem;
    border: 1px solid rgba(45, 212, 191, 0.28);
    border-radius: 8px;
    background:
        linear-gradient(135deg, rgba(20, 184, 166, 0.1), rgba(15, 23, 42, 0.16)),
        rgba(8, 47, 73, 0.22);
}

.smai-copilot-tool-progress-lead {
    color: var(--text-title);
    font-size: 0.9rem;
    font-weight: 760;
    margin: 0.42rem 0 0.52rem;
}

.smai-copilot-tool-progress ul {
    display: grid;
    gap: 0.38rem;
    margin: 0;
    padding: 0;
    list-style: none;
}

.smai-copilot-tool-progress-item {
    display: grid;
    grid-template-columns: 1.15rem minmax(0, 1fr);
    align-items: start;
    gap: 0.42rem;
    color: var(--text-muted);
    font-size: 0.86rem;
    line-height: 1.35;
}

.smai-copilot-tool-progress-item span {
    color: var(--text-ai-title);
    font-weight: 900;
}

.smai-copilot-tool-progress-item b {
    color: inherit;
    font-weight: 760;
}

.smai-copilot-tool-progress-item--complete {
    color: rgba(216, 248, 255, 0.86);
}

.smai-copilot-tool-progress-item--current {
    color: var(--text-title);
}

.smai-copilot-message-card--user {
    max-width: min(38.75rem, 72%);
    border: 1px solid rgba(96, 165, 250, 0.26);
    background:
        linear-gradient(180deg, rgba(30, 41, 59, 0.72), rgba(15, 23, 42, 0.58)),
        rgba(30, 64, 175, 0.12);
    color: var(--text-value);
}

.smai-copilot-actions-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.42rem;
    width: 100%;
    margin-top: 0.72rem;
}

.smai-copilot-actions-row--inside {
    margin-left: 0;
}

.smai-copilot-action-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 5.8rem;
    max-width: 12.5rem;
    min-height: 2rem;
    border: 1px solid rgba(96, 165, 250, 0.34);
    border-radius: 7px;
    padding: 0.42rem 0.7rem;
    background: rgba(15, 23, 42, 0.74);
    color: var(--text-value);
    font-size: 0.8rem;
    font-weight: 780;
    line-height: 1.2;
    text-align: center;
    text-decoration: none;
    white-space: normal;
}

.smai-copilot-action-link:hover {
    border-color: rgba(45, 212, 191, 0.58);
    color: var(--text-ai-title);
    background: rgba(8, 47, 73, 0.46);
}

.smai-copilot-message-meta {
    color: var(--text-ai-title);
    font-size: 0.76rem;
    font-weight: 850;
    line-height: 1.25;
}

.smai-copilot-message-card--user .smai-copilot-message-meta {
    color: #bfdbfe;
}

.smai-copilot-message-context {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 720;
    line-height: 1.35;
    margin-top: 0.18rem;
}

.smai-copilot-assistant-avatar {
    flex: 0 0 auto;
    display: grid;
    place-items: center;
    width: 3rem;
    height: 3rem;
    margin-top: 0.1rem;
    overflow: hidden;
    border: 1px solid rgba(34, 211, 238, 0.36);
    border-radius: 999px;
    background:
        radial-gradient(circle at 48% 36%, rgba(34, 211, 238, 0.14), transparent 58%),
        rgba(8, 18, 32, 0.72);
    box-shadow:
        inset 0 0 0 1px rgba(255, 255, 255, 0.04),
        0 0 14px rgba(34, 211, 238, 0.14);
}

.smai-copilot-assistant-avatar-image {
    width: 2.52rem;
    height: 2.68rem;
    object-fit: contain;
    object-position: center bottom;
    filter: drop-shadow(0 6px 10px rgba(0, 0, 0, 0.24));
}

.smai-copilot-assistant-avatar-image--reply {
    transform: scaleX(-1) translateX(-0.02rem);
}

.smai-copilot-workspace-card {
    position: relative;
    overflow: hidden;
    width: min(var(--smai-content-max-width), calc(100% - var(--smai-content-gutter)));
    max-width: var(--smai-content-max-width);
    margin: 0.82rem auto 0;
    box-sizing: border-box;
    border: 1px solid var(--smai-border);
    border-left: 3px solid var(--smai-teal);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(45, 212, 191, 0.14), transparent 62%),
        linear-gradient(180deg, rgba(23, 35, 56, 0.9), rgba(11, 18, 32, 0.9));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        var(--shadow-subtle);
    padding: 1rem;
}

.smai-copilot-workspace-card::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    height: 1px;
    background: linear-gradient(90deg, var(--smai-teal), rgba(255, 255, 255, 0.08), transparent);
    opacity: 0.72;
}

.smai-copilot-card-kicker,
.smai-copilot-action-label {
    color: var(--text-ai-title);
    font-size: 0.76rem;
    font-weight: 850;
}

.smai-copilot-workspace-card h2 {
    color: var(--text-title);
    font-size: 1.08rem;
    line-height: 1.25;
    margin: 0.18rem 0 0;
}

.smai-copilot-workspace-card > p {
    color: var(--text-secondary);
    font-size: 0.9rem;
    line-height: 1.62;
    margin: 0.42rem 0 0;
}

.smai-copilot-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.74rem;
}

.smai-copilot-chip {
    border: 1px solid rgba(34, 211, 238, 0.28);
    border-radius: 999px;
    background: rgba(8, 47, 73, 0.32);
    color: var(--text-ai-primary);
    font-size: 0.76rem;
    font-weight: 760;
    line-height: 1.2;
    padding: 0.34rem 0.58rem;
}

.smai-copilot-action-card {
    min-height: 7.2rem;
    border: 1px solid var(--smai-border);
    border-left: 3px solid var(--smai-teal);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(45, 212, 191, 0.12), transparent 62%),
        linear-gradient(180deg, rgba(23, 35, 56, 0.9), rgba(11, 18, 32, 0.9));
    box-shadow: var(--shadow-subtle);
    padding: 0.74rem 0.78rem;
    transition:
        border-color 160ms ease,
        box-shadow 160ms ease,
        transform 160ms ease;
}

.smai-copilot-action-label {
    display: block;
    line-height: 1.32;
}

.smai-copilot-action-card:hover {
    border-color: var(--border-strong);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        var(--shadow-soft);
    transform: translateY(-1px);
}

.smai-copilot-action-card p {
    color: var(--text-secondary);
    font-size: 0.84rem;
    line-height: 1.5;
    margin: 0.34rem 0 0;
}

.smai-copilot-answer-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.62rem;
    margin-top: 0.8rem;
}

.smai-copilot-answer-grid--welcome {
    grid-template-columns: repeat(2, minmax(0, 1fr));
}

.smai-copilot-answer-grid--four {
    grid-template-columns: repeat(2, minmax(0, 1fr));
}

.smai-copilot-answer-block {
    min-width: 0;
    border: 1px solid rgba(71, 85, 105, 0.5);
    border-radius: 8px;
    background:
        linear-gradient(180deg, rgba(15, 23, 42, 0.62), rgba(2, 6, 23, 0.42)),
        rgba(8, 13, 24, 0.42);
    padding: 0.62rem 0.66rem;
}

.smai-copilot-answer-block span {
    display: block;
    color: var(--text-ai-title);
    font-size: 0.78rem;
    font-weight: 800;
    margin-bottom: 0.32rem;
}

.smai-copilot-answer-block ul {
    margin: 0;
    padding-left: 0.92rem;
    color: var(--text-secondary);
    line-height: 1.48;
    font-size: 0.82rem;
}

.smai-copilot-answer-block li {
    margin-bottom: 0.22rem;
}

.smai-copilot-tool-result {
    border-top: 1px solid rgba(71, 85, 105, 0.46);
    margin-top: 0.78rem;
    padding-top: 0.66rem;
}

.smai-copilot-tool-result span,
.smai-copilot-response-meta {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 760;
}

.smai-copilot-tool-result ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.34rem;
    list-style: none;
    margin: 0.42rem 0 0;
    padding: 0;
}

.smai-copilot-tool-result li {
    border: 1px solid rgba(45, 212, 191, 0.22);
    border-radius: 999px;
    background: rgba(8, 47, 73, 0.24);
    color: var(--text-secondary);
    font-size: 0.74rem;
    line-height: 1.2;
    padding: 0.28rem 0.48rem;
}

.smai-copilot-tool-plan {
    border-top: 1px solid rgba(71, 85, 105, 0.46);
    margin-top: 0.78rem;
    padding-top: 0.72rem;
}

.smai-copilot-tool-plan-title {
    color: var(--smai-teal);
    display: block;
    font-size: 0.76rem;
    font-weight: 820;
    margin-bottom: 0.36rem;
}

.smai-copilot-tool-plan p {
    color: var(--text-secondary);
    font-size: 0.8rem;
    line-height: 1.5;
    margin: 0.24rem 0;
}

.smai-copilot-tool-plan ul {
    display: grid;
    gap: 0.42rem;
    list-style: none;
    margin: 0.62rem 0 0;
    padding: 0;
}

.smai-copilot-tool-plan li {
    border: 1px solid rgba(45, 212, 191, 0.22);
    border-radius: 8px;
    background: rgba(8, 47, 73, 0.2);
    display: grid;
    gap: 0.16rem;
    padding: 0.52rem 0.62rem;
}

.smai-copilot-tool-plan li b {
    color: var(--text-primary);
    font-size: 0.82rem;
}

.smai-copilot-tool-plan li span,
.smai-copilot-tool-plan li small,
.smai-copilot-tool-plan-choice {
    color: var(--text-muted);
    font-size: 0.72rem;
}

.smai-copilot-tool-plan-link {
    align-self: start;
    border: 1px solid rgba(45, 212, 191, 0.32);
    border-radius: 999px;
    color: var(--smai-teal);
    display: inline-flex;
    font-size: 0.72rem;
    font-weight: 760;
    justify-self: start;
    line-height: 1;
    margin-top: 0.12rem;
    padding: 0.34rem 0.56rem;
    text-decoration: none;
}

.smai-copilot-tool-plan-link:hover {
    background: rgba(45, 212, 191, 0.12);
    color: var(--text-primary);
}

.smai-copilot-action-confirm,
.smai-copilot-action-result {
    border: 1px solid rgba(45, 212, 191, 0.22);
    border-radius: 8px;
    background: rgba(8, 47, 73, 0.24);
    margin: 0.72rem auto 0;
    max-width: 1180px;
    padding: 0.78rem 0.88rem;
}

.smai-copilot-action-confirm h4,
.smai-copilot-action-result h4 {
    color: var(--text-primary);
    font-size: 0.92rem;
    letter-spacing: 0;
    margin: 0.18rem 0 0.42rem;
}

.smai-copilot-action-confirm p,
.smai-copilot-action-result p,
.smai-copilot-action-result small {
    color: var(--text-secondary);
    font-size: 0.8rem;
    line-height: 1.5;
    margin: 0.28rem 0;
}

.smai-copilot-action-confirm strong,
.smai-copilot-action-result strong,
.smai-copilot-action-result > span {
    color: var(--smai-teal);
    font-size: 0.76rem;
    font-weight: 820;
}

.smai-copilot-action-confirm ul,
.smai-copilot-action-result ul {
    color: var(--text-secondary);
    font-size: 0.78rem;
    line-height: 1.48;
    margin: 0.3rem 0 0.52rem;
    padding-left: 1.08rem;
}

.smai-copilot-action-result {
    margin-top: 0.78rem;
}

.smai-copilot-action-result--failed,
.smai-copilot-action-result--validation_error,
.smai-copilot-action-result--not_available {
    border-color: rgba(251, 113, 133, 0.34);
    background: rgba(127, 29, 29, 0.18);
}

.smai-copilot-action-result--cancelled,
.smai-copilot-action-result--skipped {
    border-color: rgba(148, 163, 184, 0.32);
    background: rgba(15, 23, 42, 0.28);
}

.smai-copilot-action-result-error {
    color: #fecdd3 !important;
}

.smai-copilot-response-meta {
    margin-top: 0.56rem;
}

.smai-copilot-response-meta summary {
    cursor: pointer;
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 760;
    list-style-position: inside;
}

.smai-copilot-response-meta p {
    margin: 0.42rem 0 0;
    color: var(--text-muted);
    font-size: 0.72rem;
    line-height: 1.45;
}

.smai-copilot-response-meta ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.28rem;
    list-style: none;
    margin: 0.38rem 0 0;
    padding: 0;
}

.smai-copilot-response-meta li {
    border: 1px solid rgba(71, 85, 105, 0.42);
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.42);
    color: var(--text-muted);
    font-size: 0.68rem;
    line-height: 1.2;
    padding: 0.24rem 0.42rem;
}

.smai-copilot-response-meta li span {
    margin-right: 0.22rem;
}

.smai-copilot-response-meta li b {
    color: var(--text-secondary);
    font-weight: 760;
}

.smai-dashboard-header {
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(34, 211, 238, 0.26);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.11), transparent 48%),
        linear-gradient(180deg, rgba(23, 35, 56, 0.98), rgba(11, 18, 32, 0.96));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        var(--shadow-soft);
    padding: 1.2rem 1.25rem 1.05rem;
    margin: 0.35rem 0 1.1rem;
}

.smai-dashboard-header::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 4px;
    background: linear-gradient(180deg, var(--smai-teal), var(--smai-blue), var(--smai-rose));
}

.smai-dashboard-title {
    color: var(--text-title);
    font-size: clamp(1.25rem, 1.5vw, 1.75rem);
    font-weight: 820;
    line-height: 1.2;
    margin: 0;
}

.smai-dashboard-subtitle {
    color: var(--text-secondary);
    font-size: 0.95rem;
    line-height: 1.58;
    margin: 0.45rem 0 0;
    max-width: 76rem;
}

.smai-dashboard-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.85rem;
}

.smai-dashboard-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.32rem;
    border: 1px solid rgba(96, 165, 250, 0.22);
    border-radius: 999px;
    background: rgba(8, 27, 42, 0.58);
    color: var(--text-value);
    font-size: 0.78rem;
    font-weight: 680;
    line-height: 1.35;
    padding: 0.28rem 0.62rem;
}

.smai-dashboard-chip .smai-chip-label {
    color: var(--text-label);
    font-weight: 640;
}

.smai-section-title {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    color: var(--text-heading);
    font-size: 1.08rem;
    font-weight: 760;
    line-height: 1.35;
    margin: 1.2rem 0 0.32rem;
    padding-bottom: 0.28rem;
    border-bottom: 1px solid rgba(30, 42, 62, 0.56);
}

.smai-section-title::before {
    content: "";
    width: 0.45rem;
    height: 1.4rem;
    border-radius: 999px;
    background: linear-gradient(180deg, var(--smai-teal), var(--smai-blue));
    box-shadow: 0 0 20px rgba(45, 212, 191, 0.22);
}

.smai-mascot {
    --smai-mascot-accent: var(--smai-accent);
    --smai-mascot-glow: rgba(56, 189, 248, 0.13);
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 0.9rem;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-left: 3px solid var(--smai-mascot-accent);
    border-radius: 8px;
    background:
        linear-gradient(90deg, var(--smai-mascot-glow), transparent 58%),
        linear-gradient(180deg, rgba(16, 26, 43, 0.94), rgba(11, 18, 32, 0.92));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        0 14px 30px rgba(0, 0, 0, 0.16);
    padding: 0.78rem 0.9rem;
    margin: 0.75rem 0 1rem;
}

.smai-mascot[data-tone="success"] {
    --smai-mascot-accent: var(--smai-green);
    --smai-mascot-glow: rgba(34, 197, 94, 0.13);
}

.smai-mascot[data-tone="forecast"] {
    --smai-mascot-accent: var(--smai-teal);
    --smai-mascot-glow: rgba(45, 212, 191, 0.13);
}

.smai-mascot[data-tone="caution"] {
    --smai-mascot-accent: var(--smai-amber);
    --smai-mascot-glow: rgba(245, 158, 11, 0.13);
}

.smai-mascot[data-tone="risk"] {
    --smai-mascot-accent: var(--smai-rose);
    --smai-mascot-glow: rgba(251, 113, 133, 0.13);
}

.smai-mascot-image {
    width: 4.4rem;
    height: 4.4rem;
    object-fit: cover;
    object-position: center top;
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: rgba(8, 13, 24, 0.42);
}

.smai-insight {
    --smai-insight-accent: var(--smai-teal);
    display: grid;
    grid-template-columns: 3.15rem minmax(0, 1fr);
    align-items: center;
    gap: 0.72rem;
    border: 1px solid rgba(34, 211, 238, 0.18);
    border-left: 3px solid var(--smai-insight-accent);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.12), transparent 58%),
        rgba(8, 27, 42, 0.78);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.16);
    padding: 0.65rem 0.76rem;
    margin: 0.7rem 0 0.85rem;
}

.smai-insight[data-tone="caution"] {
    --smai-insight-accent: var(--smai-amber);
    border-color: rgba(245, 158, 11, 0.22);
    background:
        linear-gradient(90deg, rgba(245, 158, 11, 0.09), transparent 56%),
        rgba(15, 23, 42, 0.72);
}

.smai-insight-avatar {
    height: 3.2rem;
}

.smai-insight-avatar::before {
    content: "";
    position: absolute;
    width: 2.65rem;
    height: 2.65rem;
    border-radius: 8px;
    background: rgba(34, 211, 238, 0.1);
}

.smai-insight-avatar img {
    position: relative;
    width: 2.8rem;
    height: 3.2rem;
    object-fit: contain;
    filter: drop-shadow(0 8px 13px rgba(0, 0, 0, 0.28));
    animation: smai-copilot-float 5.2s ease-in-out infinite;
}

.smai-insight-title {
    color: var(--text-ai-title);
    font-size: 0.9rem;
    font-weight: 780;
    line-height: 1.3;
}

.smai-insight-message {
    color: var(--text-ai-primary);
    font-size: 0.9rem;
    font-weight: 520;
    line-height: 1.62;
    margin-top: 0.22rem;
}

.smai-mascot-title {
    color: var(--text-heading);
    font-size: 0.94rem;
    font-weight: 780;
    line-height: 1.35;
}

.smai-mascot-message {
    color: var(--text-secondary);
    font-size: 0.88rem;
    line-height: 1.58;
    margin-top: 0.26rem;
}

.smai-mascot--compact {
    grid-template-columns: auto 1fr;
    gap: 0.72rem;
    padding: 0.72rem 0.86rem;
    margin: 0.85rem 0 1rem;
}

.smai-mascot--compact .smai-mascot-image {
    width: 3.45rem;
    height: 3.45rem;
}

.smai-mascot--sidebar {
    grid-template-columns: 3.1rem 1fr;
    gap: 0.68rem;
    padding: 0.66rem 0.68rem;
    margin: 0.2rem 0 0.95rem;
}

.smai-mascot--sidebar .smai-mascot-image {
    width: 3.1rem;
    height: 3.1rem;
}

.smai-mascot--sidebar .smai-mascot-title {
    font-size: 0.86rem;
}

.smai-mascot--sidebar .smai-mascot-message {
    font-size: 0.78rem;
    line-height: 1.5;
}

.smai-mascot--loading {
    grid-template-columns: auto 1fr;
    border-color: rgba(45, 212, 191, 0.32);
}

.smai-loading-image-wrap {
    position: relative;
    display: grid;
    place-items: center;
}

.smai-mascot-image--loading {
    animation: smai-float 1.8s ease-in-out infinite;
}

.smai-loading-pulse {
    position: absolute;
    inset: -0.25rem;
    border: 1px solid var(--smai-mascot-accent);
    border-radius: 10px;
    opacity: 0.38;
    animation: smai-pulse 1.7s ease-out infinite;
}

.smai-loading-dots {
    display: inline-flex;
    align-items: center;
    gap: 0.28rem;
    margin-top: 0.55rem;
}

.smai-loading-dots span {
    width: 0.38rem;
    height: 0.38rem;
    border-radius: 999px;
    background: var(--smai-mascot-accent);
    opacity: 0.42;
    animation: smai-dot 1.1s ease-in-out infinite;
}

.smai-loading-dots span:nth-child(2) {
    animation-delay: 0.16s;
}

.smai-loading-dots span:nth-child(3) {
    animation-delay: 0.32s;
}

.smai-workflow-loading--blocking {
    position: fixed;
    z-index: 2000;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 1.5rem;
    background: rgba(2, 8, 23, 0.74);
    backdrop-filter: blur(5px);
    pointer-events: auto;
}

.smai-workflow-loading--inline {
    position: relative;
    margin: 0.55rem 0 0.9rem;
}

.smai-workflow-loading-panel {
    position: relative;
    isolation: isolate;
    display: grid;
    grid-template-columns: 6.4rem minmax(0, 1fr);
    align-items: center;
    gap: 1.15rem;
    width: min(46rem, calc(100vw - 3rem));
    max-height: calc(100vh - 6.5rem);
    overflow: hidden;
    overflow-y: auto;
    border: 1px solid rgba(56, 189, 248, 0.38);
    border-radius: 16px;
    background:
        radial-gradient(circle at 9% 50%, rgba(34, 211, 238, 0.14), transparent 28%),
        linear-gradient(135deg, rgba(7, 17, 31, 0.98), rgba(13, 42, 57, 0.95));
    box-shadow: 0 24px 70px rgba(2, 8, 23, 0.46);
    padding: 1.15rem 1.3rem;
}

.smai-workflow-loading--inline .smai-workflow-loading-panel {
    width: 100%;
    grid-template-columns: 5.1rem minmax(0, 1fr);
    border-radius: 12px;
    box-shadow: 0 14px 34px rgba(2, 8, 23, 0.28);
    padding: 0.85rem 1rem;
}

.smai-workflow-loading-visual {
    position: relative;
    display: grid;
    place-items: center;
    width: 5.8rem;
    height: 5.8rem;
}

.smai-workflow-loading--inline .smai-workflow-loading-visual {
    width: 4.6rem;
    height: 4.6rem;
}

.smai-workflow-loading-visual img {
    position: relative;
    z-index: 2;
    width: 4.7rem;
    height: 4.7rem;
    border-radius: 12px;
    object-fit: cover;
    filter: drop-shadow(0 0 12px rgba(34, 211, 238, 0.35));
    animation: smai-float 1.8s ease-in-out infinite;
}

.smai-workflow-loading--inline .smai-workflow-loading-visual img {
    width: 3.75rem;
    height: 3.75rem;
}

.smai-workflow-loading-orbit {
    position: absolute;
    inset: 0;
    border: 1px solid rgba(103, 232, 249, 0.42);
    border-radius: 50%;
    box-shadow: 0 0 20px rgba(34, 211, 238, 0.18);
    animation: smai-workflow-orbit 3.4s linear infinite;
}

.smai-workflow-loading-orbit::after {
    content: "";
    position: absolute;
    top: 0.35rem;
    left: 50%;
    width: 0.48rem;
    height: 0.48rem;
    border-radius: 50%;
    background: #67e8f9;
    box-shadow: 0 0 11px #22d3ee;
}

.smai-workflow-loading-scan {
    position: absolute;
    z-index: 3;
    width: 78%;
    height: 1px;
    background: linear-gradient(90deg, transparent, #67e8f9, transparent);
    box-shadow: 0 0 8px rgba(34, 211, 238, 0.76);
    animation: smai-workflow-scan 1.8s ease-in-out infinite;
}

.smai-workflow-loading-copy {
    min-width: 0;
}

.smai-workflow-loading-kicker {
    color: #67e8f9;
    font-size: 0.68rem;
    font-weight: 820;
    letter-spacing: 0.12em;
}

.smai-workflow-loading-title {
    margin-top: 0.15rem;
    color: #f8fafc;
    font-size: 1.15rem;
    font-weight: 840;
    line-height: 1.35;
}

.smai-workflow-loading-copy p {
    margin: 0.28rem 0 0.68rem;
    color: #b7c7d9;
    font-size: 0.84rem;
    line-height: 1.55;
}

.smai-workflow-loading-current {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.48rem;
    color: #a5f3fc;
    font-size: 0.78rem;
}

.smai-workflow-loading-current span:last-child {
    color: #94a3b8;
    font-variant-numeric: tabular-nums;
}

.smai-workflow-loading-dot {
    width: 0.48rem;
    height: 0.48rem;
    border-radius: 50%;
    background: #22d3ee;
    box-shadow: 0 0 0 0 rgba(34, 211, 238, 0.42);
    animation: smai-copilot-pending-pulse 1.4s ease-in-out infinite;
}

.smai-workflow-loading-track {
    height: 0.35rem;
    overflow: hidden;
    margin-top: 0.48rem;
    border-radius: 999px;
    background: rgba(71, 85, 105, 0.52);
}

.smai-workflow-loading-track i {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #0891b2, #67e8f9);
    box-shadow: 0 0 12px rgba(34, 211, 238, 0.52);
    transition: width 0.25s ease;
}

.smai-workflow-loading-news {
    grid-column: 1 / -1;
    margin-top: 0.95rem;
    padding-top: 0.82rem;
    border-top: 1px solid rgba(103, 232, 249, 0.14);
}

.smai-workflow-loading-news-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.8rem;
}

.smai-workflow-loading-news-head strong {
    color: #dbeafe;
    font-size: 0.82rem;
}

.smai-workflow-loading-news-head span {
    color: #7f96ad;
    font-size: 0.68rem;
}

.smai-workflow-loading-news-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.48rem;
    margin-top: 0.58rem;
}

.smai-workflow-loading-news-card {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.18rem 0.5rem;
    min-width: 0;
    padding: 0.58rem 0.68rem;
    border: 1px solid rgba(96, 165, 250, 0.15);
    border-radius: 9px;
    background: rgba(8, 29, 45, 0.58);
}

.smai-workflow-loading-news-card span {
    align-self: start;
    padding: 0.08rem 0.38rem;
    border: 1px solid rgba(34, 211, 238, 0.24);
    border-radius: 999px;
    color: #a5f3fc;
    background: rgba(8, 145, 178, 0.12);
    font-size: 0.62rem;
    font-weight: 760;
    white-space: nowrap;
}

.smai-workflow-loading-news-card strong {
    min-width: 0;
    overflow: hidden;
    color: #e6f2ff;
    font-size: 0.75rem;
    font-weight: 680;
    line-height: 1.45;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}

.smai-workflow-loading-news-card small {
    grid-column: 2;
    color: #7890a7;
    font-size: 0.64rem;
}

.smai-workflow-loading--inline .smai-workflow-loading-news-list {
    grid-template-columns: repeat(4, minmax(0, 1fr));
}

.smai-workflow-loading--inline .smai-workflow-loading-news-card {
    grid-template-columns: 1fr;
}

.smai-workflow-loading--inline .smai-workflow-loading-news-card strong,
.smai-workflow-loading--inline .smai-workflow-loading-news-card small {
    grid-column: 1;
}

@keyframes smai-workflow-orbit {
    to {
        transform: rotate(360deg);
    }
}

@keyframes smai-workflow-scan {
    0%,
    100% {
        opacity: 0.25;
        transform: translateY(-1.5rem);
    }
    50% {
        opacity: 0.92;
        transform: translateY(1.5rem);
    }
}

@keyframes smai-float {
    0%,
    100% {
        transform: translateY(0);
    }
    50% {
        transform: translateY(-0.28rem);
    }
}

@keyframes smai-copilot-float {
    0%,
    100% {
        transform: translateY(0) scale(1);
    }
    50% {
        transform: translateY(-3px) scale(1.012);
    }
}

@keyframes smai-copilot-pending-dot {
    0%,
    80%,
    100% {
        opacity: 0.28;
        transform: translateY(0);
    }
    40% {
        opacity: 0.9;
        transform: translateY(-0.18rem);
    }
}

@keyframes smai-copilot-pending-pulse {
    0%,
    100% {
        opacity: 0.48;
        transform: scale(0.88);
        box-shadow: 0 0 0 0 rgba(45, 212, 191, 0.28);
    }
    46% {
        opacity: 0.95;
        transform: scale(1);
        box-shadow: 0 0 0 0.28rem rgba(45, 212, 191, 0);
    }
}

@keyframes smai-soft-glow {
    0%,
    100% {
        opacity: 0.62;
        transform: scale(0.96);
    }
    50% {
        opacity: 0.92;
        transform: scale(1.04);
    }
}

@keyframes smai-buddy-presence {
    0%,
    100% {
        transform: translateY(0) rotate(0deg) scale(1);
    }
    14% {
        transform: translateY(-1px) rotate(-1.4deg) scale(1.006);
    }
    27% {
        transform: translateY(0.5px) rotate(0.8deg) scale(0.998);
    }
    46% {
        transform: translateY(-2px) rotate(-0.4deg) scale(1.01);
    }
    58% {
        transform: translateY(-1px) rotate(1.1deg) scale(1.004);
    }
    74% {
        transform: translateY(0.6px) rotate(-0.8deg) scale(0.999);
    }
}

@keyframes smai-buddy-notice {
    0% {
        transform: translateY(0) rotate(0deg) scale(1);
    }
    38% {
        transform: translateY(-4px) rotate(-3.8deg) scale(1.045);
    }
    66% {
        transform: translateY(-1px) rotate(1.8deg) scale(1.018);
    }
    100% {
        transform: translateY(0) rotate(0deg) scale(1);
    }
}

@keyframes smai-buddy-curious {
    0%,
    100% {
        transform: translateY(0) rotate(0deg) scale(1);
    }
    13% {
        transform: translateY(-1px) rotate(-2deg) scale(1.006);
    }
    24% {
        transform: translateY(0) rotate(-2deg) scale(1.002);
    }
    39% {
        transform: translateY(-2px) rotate(1.3deg) scale(1.01);
    }
    51% {
        transform: translateY(-1px) rotate(2.6deg) scale(1.012);
    }
    68% {
        transform: translateY(0) rotate(-0.8deg) scale(1.004);
    }
    82% {
        transform: translateY(-1px) rotate(0.8deg) scale(1.006);
    }
}

@keyframes smai-buddy-orbit {
    0%,
    100% {
        opacity: 0.58;
        transform: rotate(-8deg) scale(0.98);
    }
    28% {
        opacity: 0.78;
        transform: rotate(3deg) scale(1.02);
    }
    55% {
        opacity: 0.66;
        transform: rotate(-2deg) scale(1.005);
    }
    81% {
        opacity: 0.82;
        transform: rotate(6deg) scale(1.03);
    }
}

@keyframes smai-holo-peek {
    0%,
    100% {
        opacity: 0.18;
        transform: translate(0.34rem, 0.18rem) scale(0.76) rotate(-5deg);
    }
    18% {
        opacity: 0.78;
        transform: translate(0.08rem, 0.02rem) scale(0.96) rotate(-4deg);
    }
    42% {
        opacity: 0.86;
        transform: translate(0, 0) scale(1) rotate(-2deg);
    }
    62% {
        opacity: 0.58;
        transform: translate(0.12rem, 0.08rem) scale(0.92) rotate(-5deg);
    }
    76% {
        opacity: 0.82;
        transform: translate(0.02rem, 0.02rem) scale(0.98) rotate(-3deg);
    }
}

@keyframes smai-holo-range-breathe {
    0%,
    100% {
        opacity: 0.42;
        transform: scaleX(0.86) scaleY(0.92);
    }
    36% {
        opacity: 0.76;
        transform: scaleX(1.12) scaleY(1.02);
    }
    64% {
        opacity: 0.58;
        transform: scaleX(0.98) scaleY(1.06);
    }
}

@keyframes smai-holo-line-a {
    0%,
    100% {
        opacity: 0.38;
        transform: rotate(-26deg) scaleX(0.72);
    }
    38% {
        opacity: 0.9;
        transform: rotate(-18deg) scaleX(1);
    }
    68% {
        opacity: 0.58;
        transform: rotate(-22deg) scaleX(0.84);
    }
}

@keyframes smai-holo-line-b {
    0%,
    100% {
        opacity: 0.34;
        transform: rotate(16deg) scaleX(0.68);
    }
    44% {
        opacity: 0.88;
        transform: rotate(28deg) scaleX(1.08);
    }
    72% {
        opacity: 0.52;
        transform: rotate(22deg) scaleX(0.86);
    }
}

@keyframes smai-holo-line-c {
    0%,
    100% {
        opacity: 0.32;
        transform: rotate(-18deg) scaleX(0.7);
    }
    46% {
        opacity: 0.92;
        transform: rotate(-9deg) scaleX(1.06);
    }
    73% {
        opacity: 0.56;
        transform: rotate(-14deg) scaleX(0.88);
    }
}

@keyframes smai-rank-bars {
    0%,
    100% {
        opacity: 0.46;
        transform: scaleY(0.72);
    }
    36% {
        opacity: 0.92;
        transform: scaleY(1.08);
    }
    58% {
        opacity: 0.66;
        transform: scaleY(0.9);
    }
}

@keyframes smai-status-breathe {
    0%,
    100% {
        opacity: 0.76;
        transform: scale(1);
    }
    50% {
        opacity: 1;
        transform: scale(1.12);
    }
}

@keyframes smai-pulse {
    0% {
        transform: scale(0.88);
        opacity: 0.36;
    }
    100% {
        transform: scale(1.12);
        opacity: 0;
    }
}

@keyframes smai-dot {
    0%,
    100% {
        opacity: 0.34;
        transform: translateY(0);
    }
    50% {
        opacity: 1;
        transform: translateY(-0.18rem);
    }
}

@media (prefers-reduced-motion: reduce) {
    .smai-app-mascot,
    .smai-page-title-image,
    .smai-copilot-image,
    .smai-copilot-aura,
    .smai-copilot-status-dot,
    .smai-floating-assistant-avatar::before,
    .smai-floating-assistant-avatar::after,
    .smai-floating-assistant-stage,
    .smai-assistant-orbit,
    .smai-assistant-holo-chart,
    .smai-assistant-holo-range,
    .smai-assistant-holo-line,
    .smai-assistant-rank-bars span,
    .smai-floating-assistant-avatar img,
    .smai-insight-avatar img,
    .smai-mascot-image--loading,
    .smai-loading-pulse,
    .smai-loading-dots span,
    .smai-workflow-loading-visual img,
    .smai-workflow-loading-orbit,
    .smai-workflow-loading-scan,
    .smai-workflow-loading-dot,
    .smai-copilot-pending-dots span,
    .smai-copilot-pending-current-dot {
        animation: none;
    }
}

@media (max-width: 767px) {
    .smai-workflow-loading--blocking {
        inset: 3.75rem 0 0 0;
        padding: 0.75rem;
    }

    .smai-workflow-loading-panel,
    .smai-workflow-loading--inline .smai-workflow-loading-panel {
        grid-template-columns: 1fr;
        width: 100%;
    }

    .smai-workflow-loading-visual {
        justify-self: center;
    }

    .smai-workflow-loading-news-head {
        align-items: flex-start;
        flex-direction: column;
        gap: 0.2rem;
    }

    .smai-workflow-loading-news-list,
    .smai-workflow-loading--inline .smai-workflow-loading-news-list {
        grid-template-columns: 1fr;
    }

    .smai-app-header {
        grid-template-columns: 1fr;
        padding: 0.55rem 0.8rem 0.6rem;
        margin-top: -2rem;
        margin-bottom: 0.75rem;
    }

    .smai-app-mascot-wrap {
        display: none;
    }

    .smai-app-logo {
        width: min(92%, 18rem);
        max-height: 3.25rem;
    }

    .smai-app-message {
        display: none;
    }

    .smai-page-title-row {
        gap: 0.55rem;
    }

    .smai-copilot-chat-topbar {
        grid-template-columns: auto minmax(0, 1fr);
        align-items: center;
        width: min(
            var(--smai-content-max-width),
            calc(100% - var(--smai-content-gutter-compact))
        );
        gap: 0.82rem 0.92rem;
        padding: 0.9rem 0.86rem;
    }

    .smai-copilot-header-identity {
        grid-column: 1 / -1;
    }

    .smai-copilot-header-icon {
        width: 3.8rem;
        height: 3.8rem;
    }

    .smai-copilot-statusbar {
        grid-column: 1 / -1;
        width: 100%;
        max-width: none;
    }

    .smai-copilot-mode-label,
    .smai-copilot-chat-actions-anchor,
    .smai-copilot-material-status,
    .smai-copilot-suggestions-title,
    .smai-copilot-thread,
    .smai-copilot-workspace-card {
        width: min(
            var(--smai-content-max-width),
            calc(100% - var(--smai-content-gutter-compact))
        );
    }

    .smai-copilot-composer-toolbar,
    div[data-testid="stChatInput"] {
        width: min(
            var(--smai-chat-main-width),
            calc(100% - var(--smai-content-gutter-compact))
        );
    }

    div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
            div[data-testid="stForm"]
        ),
    div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
        + div[data-testid="stHorizontalBlock"],
    div[data-testid="stElementContainer"]:has(.smai-copilot-composer-toolbar)
        + div[data-testid="stElementContainer"]
        div[data-testid="stHorizontalBlock"] {
        left: 0;
        padding-right: 0.75rem;
        padding-left: 0.75rem;
    }

    div[data-testid="stElementContainer"]:has(.smai-copilot-chat-actions-anchor)
        + div[data-testid="stElementContainer"]
        div[data-testid="stHorizontalBlock"],
    div[data-testid="stElementContainer"]:has(.smai-copilot-chat-actions-anchor)
        + div[data-testid="stHorizontalBlock"] {
        width: min(
            var(--smai-content-max-width),
            calc(100% - var(--smai-content-gutter-compact))
        );
        margin-top: -0.14rem;
    }

    .smai-copilot-answer-grid {
        grid-template-columns: 1fr;
    }

    .smai-copilot-thread {
        margin: 0.74rem auto;
    }

    .smai-copilot-message-card {
        max-width: calc(100% - 3rem);
        padding: 0.72rem 0.76rem;
    }

    .smai-copilot-message-card--user {
        max-width: 92%;
    }

    .smai-copilot-actions-row {
        width: 100%;
        margin-left: 0;
    }

    .smai-copilot-assistant-avatar {
        width: 2.62rem;
        height: 2.62rem;
    }

    .smai-copilot-assistant-avatar-image {
        width: 2.16rem;
        height: 2.3rem;
    }

    .smai-page-title-accessory {
        position: static;
        width: fit-content;
        max-width: 100%;
        margin: 0 0 0.62rem auto;
    }

    .smai-page-title--copilot {
        grid-template-columns: 1fr;
    }

    .smai-copilot-panel {
        grid-template-columns: 4.6rem minmax(0, 1fr);
        min-height: 6.3rem;
    }

    .smai-copilot-figure {
        min-width: 4.6rem;
        height: 5.3rem;
    }

    .smai-copilot-image {
        width: 4.3rem;
        height: 5.3rem;
    }

    .smai-floating-assistant {
        right: 0;
        bottom: 0;
        width: min(22.5rem, calc(100vw - 0.5rem));
    }

    .smai-floating-assistant-trigger {
        grid-template-columns: 3.7rem minmax(0, 1fr);
        min-width: min(18rem, calc(100vw - 0.5rem));
        padding-right: 0.68rem;
    }

    .smai-floating-assistant-avatar {
        width: 3.55rem;
        height: 3.55rem;
    }

    .smai-floating-assistant-avatar img {
        width: 3.05rem;
        height: 3.35rem;
    }

    .smai-floating-assistant-body {
        max-height: min(72vh, 38rem);
        overflow-y: auto;
        padding: 0.88rem;
    }

    .smai-floating-assistant-head {
        display: grid;
    }

    .smai-floating-assistant-head > span {
        max-width: 100%;
        width: fit-content;
    }

    .smai-page-title-art {
        width: 4.8rem;
        height: 3.1rem;
    }
}

.smai-section-card {
    border: 1px solid var(--smai-border);
    border-radius: 8px;
    background: linear-gradient(180deg, rgba(23, 35, 56, 0.76), rgba(11, 18, 32, 0.76));
    padding: 0.95rem 1rem;
    margin: 0.35rem 0 0.7rem 0;
}

.smai-ranking-setup-block,
.smai-ranking-creation-conditions,
.smai-ranking-builder-head,
.smai-ranking-current-conditions,
.smai-ranking-policy-builder,
.smai-ranking-target-summary {
    border: 1px solid var(--smai-border);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.78);
    padding: 0.86rem 1rem;
    margin: 0.55rem 0 0.72rem;
}

.smai-ranking-creation-conditions {
    align-items: center;
    border-color: rgba(34, 211, 238, 0.22);
    background: rgba(8, 13, 25, 0.5);
    display: flex;
    gap: 0.65rem;
    padding: 0.52rem 0.75rem;
    margin: 0.4rem 0 0.35rem;
}

.smai-ranking-creation-conditions strong {
    color: var(--text-heading);
    font-size: 0.88rem;
    line-height: 1.3;
}

.smai-ranking-setup-block {
    background: rgba(8, 13, 25, 0.58);
}

.smai-ranking-policy-select-anchor {
    height: 0;
}

[data-testid="stMarkdownContainer"]:has(.smai-ranking-policy-select-anchor)
    + div[data-testid="stSelectbox"] {
    border: 1px solid rgba(34, 211, 238, 0.34);
    border-radius: 8px;
    background:
        linear-gradient(180deg, rgba(34, 211, 238, 0.12), rgba(15, 23, 42, 0.4)),
        rgba(15, 23, 42, 0.44);
    padding: 0.42rem 0.48rem 0.5rem;
}

[data-testid="stMarkdownContainer"]:has(.smai-ranking-policy-select-anchor)
    + div[data-testid="stSelectbox"]
    label {
    color: #FFFFFF !important;
    font-size: 0.95rem !important;
    font-weight: 860 !important;
}

[data-testid="stMarkdownContainer"]:has(.smai-ranking-policy-select-anchor)
    + div[data-testid="stSelectbox"]
    div[data-baseweb="select"] > div {
    border-color: rgba(34, 211, 238, 0.46) !important;
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.08);
}

.smai-ranking-builder-head {
    border-color: rgba(34, 211, 238, 0.3);
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.1), transparent 74%),
        rgba(15, 23, 42, 0.82);
    padding: 0.54rem 0.68rem;
    margin: 0.55rem 0 0.55rem;
}

.smai-ranking-builder-head--load-caution {
    border-color: rgba(250, 204, 21, 0.58);
    background:
        linear-gradient(90deg, rgba(250, 204, 21, 0.16), transparent 74%),
        rgba(22, 24, 32, 0.87);
}

.smai-ranking-builder-head--load-warning {
    border-color: rgba(251, 146, 60, 0.6);
    background:
        linear-gradient(90deg, rgba(251, 146, 60, 0.18), transparent 74%),
        rgba(25, 24, 32, 0.88);
}

.smai-ranking-builder-head--load-danger {
    border-color: rgba(248, 113, 113, 0.62);
    background:
        linear-gradient(90deg, rgba(248, 113, 113, 0.18), transparent 74%),
        rgba(28, 23, 31, 0.89);
}

.smai-ranking-builder-head--load-caution .smai-ranking-builder-title-row strong {
    color: var(--text-title);
}

.smai-ranking-builder-head--load-warning .smai-ranking-builder-title-row strong {
    color: #FEF3C7;
}

.smai-ranking-builder-head--load-danger .smai-ranking-builder-title-row strong {
    color: #FED7AA;
}

.smai-ranking-condition-load-message {
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-secondary) !important;
    font-size: 0.82rem !important;
    font-weight: 760;
    margin-top: 0.58rem !important;
    padding-top: 0.44rem;
}

.smai-ranking-builder-head--load-caution .smai-ranking-condition-load-message {
    color: var(--text-secondary) !important;
}

.smai-ranking-builder-head--load-warning .smai-ranking-condition-load-message {
    color: #D8C99E !important;
}

.smai-ranking-builder-head--load-danger .smai-ranking-condition-load-message {
    color: #DFAE84 !important;
}

.smai-ranking-setup-block h4,
.smai-ranking-builder-head h4,
.smai-ranking-policy-builder h4 {
    color: var(--text-title);
    font-size: 1.02rem;
    line-height: 1.35;
    margin: 0.16rem 0 0;
}

.smai-ranking-builder-head strong {
    color: var(--text-title);
    font-size: 0.98rem;
    line-height: 1.25;
}

.smai-ranking-setup-block p,
.smai-ranking-builder-head p,
.smai-ranking-policy-builder p,
.smai-ranking-current-conditions p,
.smai-ranking-target-summary p {
    color: var(--text-secondary);
    font-size: 0.84rem;
    line-height: 1.55;
    margin: 0.32rem 0 0;
}

.smai-ranking-builder-head p {
    font-size: 0.8rem;
    margin-top: 0.18rem;
}

.smai-ranking-current-conditions {
    border-color: rgba(34, 211, 238, 0.24);
    background: rgba(8, 47, 73, 0.38);
}

.smai-ranking-current-heading {
    color: var(--text-title);
    font-size: 0.88rem;
    font-weight: 820;
    line-height: 1.3;
}

.smai-ranking-current-inline {
    margin-top: 0.42rem;
}

.smai-ranking-condition-chip-row,
.smai-ranking-policy-weight-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.34rem;
    margin-top: 0.44rem;
}

.smai-ranking-condition-chip,
.smai-ranking-policy-weight-chips span {
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.74);
    color: var(--text-secondary);
    font-size: 0.76rem;
    font-weight: 760;
    line-height: 1.2;
    padding: 0.3rem 0.55rem;
}

.smai-ranking-condition-chip--active {
    border-color: rgba(16, 185, 129, 0.48);
    background: rgba(6, 95, 70, 0.28);
    color: #bbf7d0;
}

.smai-ranking-policy-beginner-note {
    margin-top: 0.38rem;
    padding: 0.42rem 0.58rem;
    border-left: 3px solid #22d3ee;
    border-radius: 0.45rem;
    background: rgba(8, 47, 73, 0.34);
}

.smai-ranking-policy-beginner-note > strong {
    color: #cffafe;
    font-size: 0.82rem;
}

.smai-ranking-policy-beginner-note p {
    margin: 0.18rem 0 0;
    color: #cbd5e1;
    font-size: 0.78rem;
    line-height: 1.38;
}

.smai-ranking-condition-chip--policy {
    border-color: rgba(34, 211, 238, 0.52);
    background: rgba(8, 145, 178, 0.22);
    color: #cffafe;
}

.smai-ranking-condition-chip--count {
    border-color: rgba(34, 211, 238, 0.58);
    background: rgba(8, 145, 178, 0.26);
    color: #cffafe;
}

.smai-ranking-condition-chip--warning {
    border-color: rgba(250, 204, 21, 0.58);
    background: rgba(113, 63, 18, 0.34);
    color: #fde68a;
}

.smai-ranking-policy-builder {
    border-color: rgba(34, 211, 238, 0.3);
    background:
        linear-gradient(90deg, rgba(8, 145, 178, 0.18), rgba(15, 23, 42, 0.84)),
        rgba(15, 23, 42, 0.84);
    padding: 0.54rem 0.68rem;
    margin: 0.35rem 0 0.52rem;
}

.smai-ranking-policy-builder h4 {
    font-size: 0.96rem;
    margin-top: 0.1rem;
}

.smai-ranking-policy-builder p {
    font-size: 0.8rem;
    line-height: 1.45;
}

.smai-ranking-policy-weight-chips span {
    border-color: rgba(34, 211, 238, 0.24);
    color: var(--text-heading);
}

.smai-ranking-policy-weight-chips strong {
    color: #67e8f9;
    margin-left: 0.24rem;
}

.smai-ranking-policy-caution {
    border-left: 3px solid rgba(250, 204, 21, 0.76);
    padding-left: 0.6rem;
    margin-top: 0.42rem !important;
}

.smai-ranking-builder-subhead {
    color: var(--text-title);
    font-size: 0.94rem;
    font-weight: 820;
    line-height: 1.35;
    margin: 0.66rem 0 0.14rem;
}

.smai-ranking-builder-caption {
    color: var(--text-muted);
    font-size: 0.8rem;
    line-height: 1.5;
    margin: 0 0 0.44rem;
}

.smai-ranking-target-summary {
    background: rgba(8, 47, 73, 0.42);
    display: flex;
    flex-wrap: wrap;
    gap: 0.38rem 0.8rem;
    align-items: center;
    padding: 0.54rem 0.72rem;
    margin: 0.42rem 0 0.36rem;
}

.smai-ranking-target-summary strong {
    color: var(--text-title);
    display: inline;
    font-size: 0.88rem;
    line-height: 1.35;
    margin-top: 0;
}

.smai-ranking-target-summary span {
    color: var(--text-secondary);
    font-size: 0.78rem;
    line-height: 1.35;
}

.smai-ranking-target-summary--ready {
    border-color: rgba(34, 211, 238, 0.38);
}

.smai-ranking-target-summary--warning {
    border-color: rgba(250, 204, 21, 0.48);
    background: rgba(113, 63, 18, 0.26);
}

.smai-watchlist-radar {
    border-block: 1px solid rgba(70, 91, 120, 0.5);
    margin: 0.25rem 0 0.55rem;
    padding: 0.7rem 0;
}

.smai-watchlist-radar-heading {
    color: var(--text-heading);
    font-size: 0.82rem;
    font-weight: 850;
    margin-bottom: 0.5rem;
}

.smai-watchlist-radar-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.42rem;
}

.smai-watchlist-radar-item {
    border-left: 2px solid rgba(34, 211, 238, 0.48);
    min-width: 0;
    padding: 0.12rem 0.5rem;
}

.smai-watchlist-radar-item span {
    color: var(--text-muted);
    display: block;
    font-size: 0.7rem;
    font-weight: 720;
    line-height: 1.2;
}

.smai-watchlist-radar-item strong {
    color: var(--text-value);
    display: block;
    font-size: 1.08rem;
    line-height: 1.3;
    margin-top: 0.08rem;
}

.smai-watchlist-filter-chip-anchor {
    height: 0;
}

div[data-testid="stRadio"]:has([role="radiogroup"] label:nth-child(6))
    [role="radiogroup"] {
    column-gap: 0.38rem;
    row-gap: 0.38rem;
}

div[data-testid="stRadio"]:has([role="radiogroup"] label:nth-child(6))
    [role="radiogroup"] label {
    border: 1px solid rgba(100, 116, 139, 0.52);
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.42);
    min-height: 1.85rem;
    padding: 0.28rem 0.58rem;
}

div[data-testid="stRadio"]:has([role="radiogroup"] label:nth-child(6))
    [role="radiogroup"] label > div:first-child {
    display: none;
}

div[data-testid="stRadio"]:has([role="radiogroup"] label:nth-child(6))
    [role="radiogroup"] label:has(input:checked) {
    border-color: rgba(34, 211, 238, 0.72);
    background: rgba(8, 145, 178, 0.25);
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.14);
}

.smai-watchlist-card {
    --watchlist-state-accent: #64748B;
    border: 1px solid rgba(70, 91, 120, 0.78);
    border-left: 4px solid var(--watchlist-state-accent);
    border-radius: 8px;
    background: linear-gradient(180deg, rgba(17, 31, 53, 0.96), rgba(7, 13, 25, 0.94));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.06),
        0 18px 38px rgba(0, 0, 0, 0.18);
    margin: 0 0 0.58rem;
    padding: 0.72rem 0.76rem;
}

.smai-watchlist-groups-toolbar {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin: 0.35rem 0 0.8rem;
    padding: 0.85rem 1rem;
    border: 1px solid rgba(34, 211, 238, 0.28);
    border-radius: 14px;
    background: rgba(8, 26, 46, 0.72);
}

.smai-watchlist-groups-toolbar strong {
    color: #E6FAFF;
}

.smai-watchlist-groups-toolbar span {
    color: #B8C8DB;
    font-size: 0.9rem;
}

.smai-watchlist-group-section {
    --watchlist-group-accent: #64748B;
    --watchlist-group-rgb: 100, 116, 139;
    margin: 1rem 0 0.55rem;
    padding: 0.9rem 1rem;
    border: 1px solid rgba(var(--watchlist-group-rgb), 0.48);
    border-left: 5px solid var(--watchlist-group-accent);
    border-radius: 14px;
    background:
        linear-gradient(135deg, rgba(var(--watchlist-group-rgb), 0.14), rgba(7, 13, 25, 0.78));
}

.smai-watchlist-group-section--tone-cyan {
    --watchlist-group-accent: #22D3EE;
    --watchlist-group-rgb: 34, 211, 238;
    background: linear-gradient(135deg, rgba(8, 67, 86, 0.72), rgba(7, 13, 25, 0.9));
    border-color: rgba(34, 211, 238, 0.62);
}
.smai-watchlist-group-section--tone-blue {
    --watchlist-group-accent: #60A5FA;
    --watchlist-group-rgb: 96, 165, 250;
    background: linear-gradient(135deg, rgba(18, 48, 94, 0.72), rgba(7, 13, 25, 0.9));
    border-color: rgba(96, 165, 250, 0.62);
}
.smai-watchlist-group-section--tone-purple {
    --watchlist-group-accent: #A78BFA;
    --watchlist-group-rgb: 167, 139, 250;
    background: linear-gradient(135deg, rgba(55, 37, 100, 0.72), rgba(7, 13, 25, 0.9));
    border-color: rgba(167, 139, 250, 0.62);
}
.smai-watchlist-group-section--tone-green {
    --watchlist-group-accent: #34D399;
    --watchlist-group-rgb: 52, 211, 153;
    background: linear-gradient(135deg, rgba(18, 69, 57, 0.72), rgba(7, 13, 25, 0.9));
    border-color: rgba(52, 211, 153, 0.62);
}
.smai-watchlist-group-section--tone-amber {
    --watchlist-group-accent: #FBBF24;
    --watchlist-group-rgb: 251, 191, 36;
    background: linear-gradient(135deg, rgba(87, 60, 13, 0.72), rgba(7, 13, 25, 0.9));
    border-color: rgba(251, 191, 36, 0.62);
}
.smai-watchlist-group-section--tone-orange {
    --watchlist-group-accent: #FB923C;
    --watchlist-group-rgb: 251, 146, 60;
    background: linear-gradient(135deg, rgba(93, 45, 16, 0.72), rgba(7, 13, 25, 0.9));
    border-color: rgba(251, 146, 60, 0.62);
}
.smai-watchlist-group-section--tone-rose {
    --watchlist-group-accent: #FB7185;
    --watchlist-group-rgb: 251, 113, 133;
    background: linear-gradient(135deg, rgba(91, 31, 48, 0.72), rgba(7, 13, 25, 0.9));
    border-color: rgba(251, 113, 133, 0.62);
}
.smai-watchlist-group-section--tone-slate {
    --watchlist-group-accent: #94A3B8;
    --watchlist-group-rgb: 148, 163, 184;
    background: linear-gradient(135deg, rgba(43, 53, 70, 0.72), rgba(7, 13, 25, 0.9));
    border-color: rgba(148, 163, 184, 0.56);
}

.smai-watchlist-group-header {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    justify-content: space-between;
}

.smai-watchlist-group-header strong {
    color: #F8FDFF;
    font-size: 1.05rem;
    overflow-wrap: anywhere;
}

.smai-watchlist-group-section p {
    margin: 0.35rem 0 0;
    color: #C2D2E3;
    overflow-wrap: anywhere;
}

.smai-watchlist-group-count-badge {
    flex: 0 0 auto;
    padding: 0.16rem 0.55rem;
    border: 1px solid rgba(var(--watchlist-group-rgb), 0.7);
    border-radius: 999px;
    background: rgba(var(--watchlist-group-rgb), 0.18);
    color: #F8FDFF;
    font-size: 0.8rem;
    font-weight: 700;
}

.smai-watchlist-group-header-marker {
    display: none;
}

.smai-watchlist-group-panel-marker {
    display: none;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker) {
    --watchlist-group-rgb: 100, 116, 139;
    margin: 0.9rem 0 0.7rem;
    padding: 0 0.85rem 0.8rem;
    border: 1px solid rgba(var(--watchlist-group-rgb), 0.42);
    border-left: 5px solid rgb(var(--watchlist-group-rgb));
    border-radius: 15px;
    background:
        linear-gradient(135deg, rgba(var(--watchlist-group-rgb), 0.16), rgba(7, 13, 25, 0.52));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker--tone-cyan) { --watchlist-group-rgb: 34, 211, 238; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker--tone-blue) { --watchlist-group-rgb: 96, 165, 250; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker--tone-purple) { --watchlist-group-rgb: 167, 139, 250; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker--tone-green) { --watchlist-group-rgb: 52, 211, 153; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker--tone-amber) { --watchlist-group-rgb: 251, 191, 36; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker--tone-orange) { --watchlist-group-rgb: 251, 146, 60; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker--tone-rose) { --watchlist-group-rgb: 251, 113, 133; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker--tone-slate) { --watchlist-group-rgb: 148, 163, 184; }

div[data-testid="stVerticalBlockBorderWrapper"]:has(.smai-watchlist-group-panel-marker)
    [class*="st-key-watchlist_group_tone_"] div[data-testid="stButton"] button {
    margin-top: 0.7rem;
}

[class*="st-key-watchlist_group_tone_"] div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    --watchlist-group-rgb: 100, 116, 139;
    min-height: 3.65rem;
    margin-top: 0.85rem;
    padding: 0.75rem 1rem;
    justify-content: flex-start;
    border: 1px solid rgba(var(--watchlist-group-rgb), 0.58);
    border-left: 5px solid rgb(var(--watchlist-group-rgb));
    border-radius: 14px;
    background:
        linear-gradient(135deg, rgba(var(--watchlist-group-rgb), 0.28), rgba(7, 13, 25, 0.9));
    color: #F8FDFF;
    font-size: 1.02rem;
    font-weight: 800;
    text-align: left;
}

[class*="st-key-watchlist_group_tone_"] div[data-testid="stButton"] button:hover,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker)
    + div[data-testid="stButton"] button:hover,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button:hover {
    border-color: rgba(var(--watchlist-group-rgb), 0.92);
    background:
        linear-gradient(135deg, rgba(var(--watchlist-group-rgb), 0.4), rgba(7, 13, 25, 0.88));
    transform: none;
}

[class*="st-key-watchlist_group_tone_cyan_"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker--tone-cyan)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker--tone-cyan)
    + div[data-testid="stElementContainer"] button { --watchlist-group-rgb: 34, 211, 238; }
[class*="st-key-watchlist_group_tone_blue_"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker--tone-blue)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker--tone-blue)
    + div[data-testid="stElementContainer"] button { --watchlist-group-rgb: 96, 165, 250; }
[class*="st-key-watchlist_group_tone_purple_"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker--tone-purple)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker--tone-purple)
    + div[data-testid="stElementContainer"] button { --watchlist-group-rgb: 167, 139, 250; }
[class*="st-key-watchlist_group_tone_green_"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker--tone-green)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker--tone-green)
    + div[data-testid="stElementContainer"] button { --watchlist-group-rgb: 52, 211, 153; }
[class*="st-key-watchlist_group_tone_amber_"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker--tone-amber)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker--tone-amber)
    + div[data-testid="stElementContainer"] button { --watchlist-group-rgb: 251, 191, 36; }
[class*="st-key-watchlist_group_tone_orange_"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker--tone-orange)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker--tone-orange)
    + div[data-testid="stElementContainer"] button { --watchlist-group-rgb: 251, 146, 60; }
[class*="st-key-watchlist_group_tone_rose_"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker--tone-rose)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker--tone-rose)
    + div[data-testid="stElementContainer"] button { --watchlist-group-rgb: 251, 113, 133; }
[class*="st-key-watchlist_group_tone_slate_"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-group-header-marker--tone-slate)
    + div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-group-header-marker--tone-slate)
    + div[data-testid="stElementContainer"] button { --watchlist-group-rgb: 148, 163, 184; }

.smai-watchlist-compact-card {
    min-height: 8.7rem;
    margin: 0.25rem 0 0.5rem;
    padding: 0.85rem;
    border: 1px solid rgba(100, 149, 190, 0.34);
    border-radius: 12px;
    background: rgba(7, 18, 34, 0.88);
}

.smai-watchlist-compact-card h4 {
    margin: 0;
    color: #F8FDFF;
    overflow-wrap: anywhere;
}

.smai-watchlist-compact-symbol {
    margin-top: 0.15rem;
    color: #8CDFF0;
    font-size: 0.83rem;
    font-weight: 700;
}

.smai-watchlist-compact-metrics {
    display: flex;
    gap: 0.4rem 0.75rem;
    flex-wrap: wrap;
    margin-top: 0.75rem;
    color: #B9C8DA;
    font-size: 0.82rem;
}

.smai-watchlist-compact-metrics strong {
    color: #F1F5F9;
}

.smai-watchlist-edit-mode-banner {
    display: flex;
    gap: 0.35rem 0.8rem;
    flex-wrap: wrap;
    margin: 0.8rem 0;
    padding: 0.75rem 0.9rem;
    border: 1px solid rgba(167, 139, 250, 0.62);
    border-radius: 12px;
    background: rgba(91, 33, 182, 0.16);
    color: #EDE9FE;
}

div[data-testid="stDialog"] div[role="dialog"]:has(.smai-watchlist-editor-marker) {
    width: min(72rem, calc(100vw - 2rem)) !important;
    max-width: min(72rem, calc(100vw - 2rem)) !important;
}

.smai-watchlist-group-representative {
    margin-top: 0.35rem;
    color: #9FB2C7;
    font-size: 0.82rem;
}

.smai-watchlist-editor-card {
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
    margin: 0.45rem 0 0.25rem;
    padding: 0.72rem 0.8rem;
    border: 1px solid rgba(100, 149, 190, 0.36);
    border-radius: 10px;
    background: rgba(7, 18, 34, 0.9);
}

.smai-watchlist-editor-card > div {
    display: grid;
    gap: 0.18rem;
    min-width: 0;
}

.smai-watchlist-editor-card strong {
    color: #F8FDFF;
    overflow-wrap: anywhere;
}

.smai-watchlist-editor-card small {
    color: #8CDFF0;
}

.smai-watchlist-editor-card span {
    color: #B9C8DA;
    font-size: 0.82rem;
}

.smai-watchlist-drag-handle {
    color: #7DD3FC !important;
    cursor: grab;
    font-size: 1rem !important;
    letter-spacing: -0.2rem;
}

.smai-watchlist-selected-group-title {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.6rem;
    margin-bottom: 0.55rem;
}

.smai-watchlist-selected-group-title strong {
    color: #F8FDFF;
}

.smai-watchlist-selected-group-title span {
    color: #9FB2C7;
    font-size: 0.78rem;
}

.smai-watchlist-action-primary + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-action-primary)
    + div[data-testid="stButton"] button,
.element-container:has(.smai-watchlist-action-primary)
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-action-primary)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button,
.element-container:has(.smai-watchlist-action-primary) + div[data-testid="stFormSubmitButton"] button {
    border-color: #22D3EE !important;
    background: linear-gradient(135deg, #0891B2, #2563EB) !important;
    color: #FFFFFF !important;
}

.smai-watchlist-action-edit + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-action-edit)
    + div[data-testid="stButton"] button,
.element-container:has(.smai-watchlist-action-edit)
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-action-edit)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    border-color: #8B5CF6 !important;
    background: linear-gradient(135deg, #4C1D95, #1D4ED8) !important;
    color: #FFFFFF !important;
}

.smai-watchlist-action-save + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-action-save)
    + div[data-testid="stButton"] button,
.element-container:has(.smai-watchlist-action-save)
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-action-save)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    border-color: #34D399 !important;
    background: linear-gradient(135deg, #047857, #0891B2) !important;
    color: #FFFFFF !important;
}

.smai-watchlist-action-danger + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-action-danger)
    + div[data-testid="stButton"] button,
.element-container:has(.smai-watchlist-action-danger)
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-action-danger)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    border-color: #FB7185 !important;
    background: linear-gradient(135deg, #991B1B, #C2410C) !important;
    color: #FFFFFF !important;
}

.smai-watchlist-action-secondary + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-watchlist-action-secondary)
    + div[data-testid="stButton"] button,
.element-container:has(.smai-watchlist-action-secondary)
    + .element-container div[data-testid="stButton"] button,
div[data-testid="stElementContainer"]:has(.smai-watchlist-action-secondary)
    + div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
    border-color: #64748B !important;
    background: #172033 !important;
    color: #E2E8F0 !important;
}

.smai-watchlist-card--upside {
    --watchlist-state-accent: #2DD4BF;
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.16), rgba(7, 13, 25, 0.96));
}

.smai-watchlist-card--short-upside {
    --watchlist-state-accent: #38BDF8;
    background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(7, 13, 25, 0.96));
}

.smai-watchlist-card--flat {
    --watchlist-state-accent: #7C8AA0;
    background: linear-gradient(135deg, rgba(51, 65, 85, 0.2), rgba(7, 13, 25, 0.96));
}

.smai-watchlist-card--downside {
    --watchlist-state-accent: #F59E0B;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.18), rgba(7, 13, 25, 0.96));
}

.smai-watchlist-card--sharp-downside {
    --watchlist-state-accent: #F87171;
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.16), rgba(7, 13, 25, 0.96));
}

.smai-watchlist-card--unknown {
    --watchlist-state-accent: #64748B;
    background: linear-gradient(135deg, rgba(100, 116, 139, 0.16), rgba(7, 13, 25, 0.97));
}

.smai-watchlist-card-header {
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
    justify-content: space-between;
}

.smai-watchlist-card-symbol {
    color: var(--text-title);
    font-size: 1.12rem;
    font-weight: 880;
    line-height: 1.25;
}

.smai-watchlist-card-name {
    color: var(--text-secondary);
    font-size: 0.9rem;
    font-weight: 680;
    line-height: 1.45;
    margin-top: 0.16rem;
}

.smai-watchlist-card-dates {
    display: grid;
    gap: 0.08rem;
    min-width: 8.4rem;
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 720;
    line-height: 1.35;
    text-align: right;
}

.smai-watchlist-card-dates strong {
    color: var(--text-heading);
    font-size: 0.74rem;
}

.smai-watchlist-card-meta {
    color: var(--text-caption);
    font-size: 0.78rem;
    font-weight: 650;
    line-height: 1.45;
    margin-top: 0.28rem;
}

.smai-watchlist-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.32rem;
    margin-top: 0.52rem;
}

.smai-watchlist-badge {
    border: 1px solid rgba(148, 163, 184, 0.42);
    border-radius: 999px;
    color: var(--text-heading);
    display: inline-flex;
    align-items: center;
    min-height: 1.4rem;
    padding: 0.18rem 0.52rem;
    font-size: 0.78rem;
    font-weight: 820;
    line-height: 1.1;
}

.smai-watchlist-status--upside {
    border-color: rgba(52, 211, 153, 0.48);
    background: rgba(6, 78, 59, 0.34);
    color: #BAF7DD;
}

.smai-watchlist-status--short-upside {
    border-color: rgba(56, 189, 248, 0.5);
    background: rgba(3, 105, 161, 0.28);
    color: #D8F2FE;
}

.smai-watchlist-status--downside {
    border-color: rgba(251, 113, 133, 0.5);
    background: rgba(127, 29, 29, 0.28);
    color: #FFD1D8;
}

.smai-watchlist-status--sharp-downside {
    border-color: rgba(248, 113, 113, 0.58);
    background: rgba(127, 29, 29, 0.28);
    color: #FFD5D5;
}

.smai-watchlist-status--flat {
    border-color: rgba(96, 165, 250, 0.48);
    background: rgba(30, 64, 175, 0.24);
    color: #D7EAFE;
}

.smai-watchlist-status--unknown,
.smai-watchlist-refresh--unknown {
    border-color: rgba(148, 163, 184, 0.42);
    background: rgba(71, 85, 105, 0.24);
    color: #DDE6F2;
}

.smai-watchlist-refresh--fresh {
    border-color: rgba(34, 211, 238, 0.54);
    background: rgba(8, 145, 178, 0.26);
    color: #CFFAFE;
}

.smai-watchlist-refresh--never-checked {
    border-color: rgba(100, 116, 139, 0.56);
    background: rgba(30, 41, 59, 0.44);
    color: #D7DEE9;
}

.smai-watchlist-refresh--stale {
    border-color: rgba(251, 191, 36, 0.54);
    background: rgba(113, 63, 18, 0.3);
    color: #FDE68A;
}

.smai-watchlist-refresh--needs-attention {
    border-color: rgba(251, 146, 60, 0.58);
    background: rgba(124, 45, 18, 0.3);
    color: #FED7AA;
}

.smai-watchlist-refresh--failed {
    border-color: rgba(248, 113, 113, 0.58);
    background: rgba(127, 29, 29, 0.3);
    color: #FECACA;
}

.smai-watchlist-refresh--partial {
    border-color: rgba(167, 139, 250, 0.58);
    background: rgba(49, 46, 129, 0.32);
    color: #DDD6FE;
}

.smai-watchlist-header-refresh-anchor {
    height: 0;
}

[data-testid="stMarkdownContainer"]:has(.smai-watchlist-header-refresh-anchor)
    + div[data-testid="stButton"] button {
    min-height: 2.75rem;
    border: 1px solid rgba(34, 211, 238, 0.72) !important;
    border-radius: 999px !important;
    background:
        linear-gradient(135deg, rgba(8, 145, 178, 0.96), rgba(29, 78, 216, 0.92)) !important;
    color: #F0FDFF !important;
    font-weight: 850 !important;
    letter-spacing: 0.01em;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.18),
        0 8px 24px rgba(8, 145, 178, 0.24) !important;
}

[data-testid="stMarkdownContainer"]:has(.smai-watchlist-header-refresh-anchor)
    + div[data-testid="stButton"] button:hover {
    border-color: rgba(165, 243, 252, 0.92) !important;
    filter: brightness(1.08);
    transform: translateY(-1px);
}

.smai-watchlist-decision-badge {
    border-color: rgba(148, 163, 184, 0.4);
    background: rgba(30, 41, 59, 0.38);
    color: #DCE6F2;
}

.smai-watchlist-movement {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border-block: 1px solid rgba(70, 91, 120, 0.36);
    color: var(--text-secondary);
    margin-top: 0.5rem;
    padding: 0.4rem 0;
}

.smai-watchlist-movement strong {
    color: var(--watchlist-state-accent);
    flex: 0 0 auto;
    font-size: 1.05rem;
    line-height: 1;
}

.smai-watchlist-movement span {
    font-size: 0.76rem;
    font-weight: 680;
    line-height: 1.35;
    overflow-wrap: anywhere;
}

.smai-watchlist-data-needed {
    border: 1px solid rgba(100, 116, 139, 0.38);
    border-radius: 6px;
    background: rgba(30, 41, 59, 0.32);
    display: grid;
    gap: 0.16rem;
    margin-top: 0.64rem;
    padding: 0.52rem 0.62rem;
}

.smai-watchlist-data-needed strong {
    color: var(--text-heading);
    font-size: 0.78rem;
}

.smai-watchlist-data-needed span {
    color: var(--text-muted);
    font-size: 0.72rem;
    line-height: 1.35;
}

.smai-watchlist-snapshot-notice {
    border-left: 2px solid rgba(245, 158, 11, 0.68);
    color: #FDE7B0;
    font-size: 0.72rem;
    line-height: 1.4;
    margin-top: 0.58rem;
    padding: 0.28rem 0.52rem;
}

.smai-watchlist-remove-anchor {
    height: 0;
}

.smai-watchlist-detail-anchor,
.smai-watchlist-cockpit-anchor {
    height: 0;
}

[data-testid="stMarkdownContainer"]:has(.smai-watchlist-detail-anchor)
    + div[data-testid="stButton"] button {
    border-color: rgba(34, 211, 238, 0.66) !important;
    background: rgba(8, 145, 178, 0.24) !important;
    color: #ECFEFF !important;
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.1) !important;
}

[data-testid="stMarkdownContainer"]:has(.smai-watchlist-cockpit-anchor)
    + div[data-testid="stButton"] button {
    border-color: rgba(96, 165, 250, 0.58) !important;
    background: rgba(30, 64, 175, 0.18) !important;
    color: #E0ECFF !important;
}

[data-testid="stMarkdownContainer"]:has(.smai-watchlist-remove-anchor)
    + div[data-testid="stButton"] button {
    border-color: rgba(100, 116, 139, 0.34) !important;
    background: rgba(15, 23, 42, 0.22) !important;
    box-shadow: none !important;
    opacity: 0.72;
}

[data-testid="stMarkdownContainer"]:has(.smai-watchlist-remove-anchor)
    + div[data-testid="stButton"] button:hover {
    opacity: 1;
}

.smai-watchlist-metric-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.36rem;
    margin-top: 0.58rem;
}

.smai-watchlist-metric {
    border: 1px solid rgba(70, 91, 120, 0.5);
    border-radius: 6px;
    background: rgba(2, 6, 23, 0.28);
    min-width: 0;
    padding: 0.38rem 0.46rem;
}

.smai-watchlist-metric--muted .smai-watchlist-metric-value {
    color: var(--text-muted);
    font-weight: 700;
}

.smai-watchlist-metric-label {
    color: var(--text-muted);
    display: block;
    font-size: 0.68rem;
    font-weight: 760;
    line-height: 1.25;
    margin-bottom: 0.18rem;
}

.smai-watchlist-metric-value {
    color: var(--text-value);
    display: block;
    font-size: 0.88rem;
    font-weight: 860;
    line-height: 1.25;
    overflow-wrap: anywhere;
}

.smai-watchlist-detail-title {
    border-top: 1px solid rgba(70, 91, 120, 0.4);
    color: var(--text-heading);
    font-size: 0.72rem;
    font-weight: 820;
    margin-top: 0.58rem;
    padding-top: 0.48rem;
}

.smai-watchlist-detail-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin-top: 0.18rem;
}

.smai-watchlist-detail-metric {
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
    gap: 0.28rem;
    min-width: 0;
    padding: 0.28rem 0.32rem;
    border-bottom: 1px solid rgba(70, 91, 120, 0.28);
}

.smai-watchlist-detail-metric span {
    color: var(--text-muted);
    font-size: 0.67rem;
    font-weight: 720;
}

.smai-watchlist-detail-metric strong {
    color: var(--text-secondary);
    font-size: 0.74rem;
    font-weight: 760;
    overflow-wrap: anywhere;
    text-align: right;
}

.smai-watchlist-info {
    border-top: 1px solid rgba(70, 91, 120, 0.44);
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.46rem 0.72rem;
    margin-top: 0.86rem;
    padding-top: 0.78rem;
}

.smai-watchlist-info-row {
    min-width: 0;
}

.smai-watchlist-info-row span {
    color: var(--text-muted);
    display: block;
    font-size: 0.7rem;
    font-weight: 780;
    line-height: 1.3;
    margin-bottom: 0.12rem;
}

.smai-watchlist-info-row strong {
    color: var(--text-secondary);
    display: block;
    font-size: 0.8rem;
    font-weight: 680;
    line-height: 1.45;
    overflow-wrap: anywhere;
}

.smai-watchlist-decision-title {
    border-top: 1px solid rgba(70, 91, 120, 0.44);
    color: var(--text-heading);
    font-size: 0.82rem;
    font-weight: 860;
    letter-spacing: 0;
    line-height: 1.3;
    margin-top: 0.86rem;
    padding-top: 0.78rem;
}

.smai-watchlist-decision {
    border-top: 0;
    margin-top: 0.42rem;
    padding-top: 0;
}

.smai-watchlist-decision-empty {
    border-top: 1px solid rgba(70, 91, 120, 0.44);
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 0.78rem;
    padding-top: 0.68rem;
}

.smai-watchlist-decision-empty span {
    color: var(--text-muted);
    font-size: 0.74rem;
    font-weight: 760;
}

.smai-watchlist-decision-empty strong {
    color: var(--text-secondary);
    font-size: 0.82rem;
    font-weight: 720;
}

@media (min-width: 768px) and (max-width: 1024px) {
    .smai-watchlist-radar-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .smai-watchlist-metric-grid,
    .smai-watchlist-info {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 767px) {
    .smai-watchlist-radar-grid {
        grid-template-columns: 1fr;
    }

    .smai-watchlist-card-header {
        flex-direction: column;
    }

    .smai-watchlist-card-dates {
        min-width: 0;
        text-align: left;
    }

    .smai-watchlist-metric-grid,
    .smai-watchlist-info {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .smai-watchlist-detail-grid {
        grid-template-columns: 1fr;
    }
}

/*
 * Streamlit places toasts at the upper-right edge by default.  On iPhone and
 * iPad that position overlaps the fixed user controls and obscures the page
 * the user is currently reading.  Keep the notification in the safe bottom
 * area, make it full-width within the device gutter, and use an opaque surface
 * so the success/error message remains legible over busy ranking cards.
 */
@media (max-width: 1024px) {
    [data-testid="stToastContainer"] {
        top: auto !important;
        right: max(0.85rem, env(safe-area-inset-right)) !important;
        bottom: max(0.85rem, env(safe-area-inset-bottom)) !important;
        left: max(0.85rem, env(safe-area-inset-left)) !important;
        width: auto !important;
        z-index: 5000 !important;
    }

    [data-testid="stToast"] {
        width: 100% !important;
        min-height: 3.4rem;
        padding: 0.8rem 0.95rem !important;
        border: 1px solid rgba(103, 232, 249, 0.82) !important;
        border-radius: 0.9rem !important;
        background: rgba(4, 18, 35, 0.98) !important;
        box-shadow: 0 0.8rem 2rem rgba(0, 0, 0, 0.48) !important;
        color: #F8FBFF !important;
        font-size: 1rem !important;
        font-weight: 750 !important;
        line-height: 1.45 !important;
    }

    [data-testid="stToast"] * {
        color: #F8FBFF !important;
        font-size: inherit !important;
        font-weight: inherit !important;
    }
}

.smai-ranking-build-action-anchor + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-ranking-build-action-anchor)
    + div[data-testid="stButton"] button {
    min-height: 3.85rem;
    border-width: 1px;
    border-color: rgba(103, 232, 249, 0.72) !important;
    background:
        linear-gradient(180deg, rgba(34, 211, 238, 0.92), rgba(8, 145, 178, 0.88)) !important;
    box-shadow:
        0 0 0 1px rgba(103, 232, 249, 0.18),
        0 14px 30px rgba(8, 145, 178, 0.28);
}

.smai-ranking-build-action-anchor + div[data-testid="stButton"] button *,
[data-testid="stMarkdownContainer"]:has(.smai-ranking-build-action-anchor)
    + div[data-testid="stButton"] button * {
    color: #FFFFFF !important;
    font-size: 1.16rem !important;
    font-weight: 880 !important;
}


.smai-ranking-deep-dive-select-anchor {
    height: 0;
}

[data-testid="stMarkdownContainer"]:has(.smai-ranking-deep-dive-select-anchor)
    + div[data-testid="stSelectbox"] {
    border: 1px solid rgba(34, 211, 238, 0.28);
    border-radius: 10px;
    background:
        linear-gradient(180deg, rgba(34, 211, 238, 0.08), rgba(15, 23, 42, 0.42)),
        rgba(8, 13, 25, 0.48);
    padding: 0.42rem 0.5rem 0.54rem;
}

[data-testid="stMarkdownContainer"]:has(.smai-ranking-deep-dive-select-anchor)
    + div[data-testid="stSelectbox"] label {
    color: #FFFFFF !important;
    font-size: 0.95rem !important;
    font-weight: 860 !important;
}

[data-testid="stMarkdownContainer"]:has(.smai-ranking-deep-dive-select-anchor)
    + div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    min-height: 3.2rem;
    border-color: rgba(103, 232, 249, 0.48) !important;
    background-color: rgba(15, 31, 52, 0.98) !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.07),
        0 0 0 1px rgba(34, 211, 238, 0.08);
}

.smai-ranking-deep-dive-cta-label {
    display: block;
    min-height: 1.5rem;
    color: var(--text-ai-title);
    font-size: 0.95rem;
    font-weight: 860;
    line-height: 1.45;
    margin: 0 0 0.42rem;
}

.smai-ranking-deep-dive-cta-anchor {
    height: 0;
}

.smai-ranking-deep-dive-cta-anchor + div[data-testid="stButton"] button,
[data-testid="stMarkdownContainer"]:has(.smai-ranking-deep-dive-cta-anchor)
    + div[data-testid="stButton"] button {
    min-height: 3.95rem;
    width: 100%;
    border-width: 1px;
    border-color: rgba(186, 230, 253, 0.88) !important;
    border-radius: 12px;
    background:
        linear-gradient(
            135deg,
            rgba(14, 116, 144, 1) 0%,
            rgba(8, 145, 178, 0.98) 38%,
            rgba(20, 184, 166, 0.98) 100%
        ) !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.22),
        0 0 0 1px rgba(103, 232, 249, 0.22),
        0 16px 34px rgba(8, 145, 178, 0.34),
        0 0 28px rgba(34, 211, 238, 0.16);
}

.smai-ranking-deep-dive-cta-anchor + div[data-testid="stButton"] button:hover,
[data-testid="stMarkdownContainer"]:has(.smai-ranking-deep-dive-cta-anchor)
    + div[data-testid="stButton"] button:hover {
    border-color: rgba(224, 242, 254, 0.98) !important;
    background:
        linear-gradient(
            135deg,
            rgba(56, 189, 248, 1) 0%,
            rgba(34, 211, 238, 0.98) 45%,
            rgba(45, 212, 191, 0.98) 100%
        ) !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.28),
        0 0 0 2px rgba(103, 232, 249, 0.28),
        0 18px 38px rgba(8, 145, 178, 0.4),
        0 0 34px rgba(34, 211, 238, 0.22);
    transform: translateY(-1px);
}

.smai-ranking-deep-dive-cta-anchor + div[data-testid="stButton"] button *,
[data-testid="stMarkdownContainer"]:has(.smai-ranking-deep-dive-cta-anchor)
    + div[data-testid="stButton"] button * {
    color: #FFFFFF !important;
    font-size: 1.1rem !important;
    font-weight: 900 !important;
    letter-spacing: 0.01em !important;
}

.smai-news-refresh-action-anchor {
    height: 0;
}

[data-testid="stMarkdownContainer"]:has(.smai-news-refresh-action-anchor)
    + div[data-testid="stButton"] button {
    min-height: 4rem;
    width: 100%;
    border: 1px solid rgba(103, 232, 249, 0.78) !important;
    border-radius: 10px;
    background:
        linear-gradient(180deg, rgba(34, 211, 238, 0.96), rgba(8, 145, 178, 0.9)) !important;
    box-shadow:
        0 0 0 1px rgba(103, 232, 249, 0.2),
        0 14px 30px rgba(8, 145, 178, 0.3);
}

[data-testid="stMarkdownContainer"]:has(.smai-news-refresh-action-anchor)
    + div[data-testid="stButton"] button:hover {
    border-color: rgba(165, 243, 252, 0.95) !important;
    background:
        linear-gradient(180deg, rgba(103, 232, 249, 0.98), rgba(6, 182, 212, 0.94)) !important;
    box-shadow:
        0 0 0 2px rgba(103, 232, 249, 0.24),
        0 16px 34px rgba(8, 145, 178, 0.36);
    transform: translateY(-1px);
}

[data-testid="stMarkdownContainer"]:has(.smai-news-refresh-action-anchor)
    + div[data-testid="stButton"] button * {
    color: #FFFFFF !important;
    font-size: 1.12rem !important;
    font-weight: 880 !important;
}

.smai-ranking-provider-note {
    border: 1px solid rgba(250, 204, 21, 0.28);
    border-radius: 8px;
    background: rgba(113, 63, 18, 0.18);
    color: var(--text-secondary);
    font-size: 0.78rem;
    line-height: 1.35;
    margin: 0.32rem 0 0.36rem;
    padding: 0.42rem 0.62rem;
}

.smai-ranking-condition-card {
    border-color: rgba(34, 211, 238, 0.34);
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.1), transparent 70%),
        linear-gradient(180deg, rgba(23, 35, 56, 0.88), rgba(11, 18, 32, 0.84));
}

.smai-ranking-condition-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: 0.72rem;
    margin-top: 0.48rem;
}

.smai-ranking-condition-grid strong {
    display: block;
    color: var(--text-title);
    font-size: 1.05rem;
    line-height: 1.25;
    margin-top: 0.12rem;
}

.smai-ranking-condition-grid p,
.smai-ranking-policy-summary,
.smai-ranking-condition-note {
    color: var(--text-secondary);
    font-size: 0.84rem;
    line-height: 1.55;
    margin: 0.32rem 0 0;
}

.smai-ranking-policy-summary {
    margin-top: 0.42rem;
}

.smai-ranking-focus-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.38rem;
    margin-top: 0.7rem;
}

.smai-ranking-focus-chips span {
    border: 1px solid rgba(34, 211, 238, 0.28);
    border-radius: 999px;
    color: var(--text-heading);
    background: rgba(8, 145, 178, 0.12);
    font-size: 0.76rem;
    font-weight: 760;
    line-height: 1.2;
    padding: 0.28rem 0.5rem;
}

.smai-ranking-weight-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
    gap: 0.42rem;
    margin-top: 0.75rem;
}

.smai-ranking-weight-grid > div {
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: rgba(7, 13, 25, 0.72);
    padding: 0.42rem 0.52rem;
}

.smai-ranking-weight-grid span {
    display: block;
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 780;
}

.smai-ranking-weight-grid strong {
    color: var(--text-heading);
    font-size: 0.96rem;
    line-height: 1.25;
}

.smai-metric-card {
    --smai-card-accent: var(--smai-gray);
    --smai-card-glow: rgba(100, 116, 139, 0.12);
    --smai-card-value: var(--text-title);
    position: relative;
    overflow: hidden;
    min-height: 9.2rem;
    border: 1px solid var(--smai-border);
    border-left: 3px solid var(--smai-card-accent);
    border-radius: 8px;
    background:
        linear-gradient(90deg, var(--smai-card-glow), transparent 62%),
        linear-gradient(180deg, rgba(23, 35, 56, 0.94), rgba(11, 18, 32, 0.93));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        var(--shadow-subtle);
    padding: 0.88rem 0.95rem;
    transition:
        border-color 140ms ease,
        background 140ms ease,
        transform 140ms ease,
        box-shadow 140ms ease;
}

.smai-metric-card::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 1px;
    background: linear-gradient(90deg, var(--smai-card-accent), rgba(255, 255, 255, 0.08), transparent);
    opacity: 0.72;
}

.smai-metric-card:hover {
    border-color: var(--border-strong);
    background:
        linear-gradient(90deg, var(--smai-card-glow), transparent 62%),
        linear-gradient(180deg, rgba(23, 35, 56, 1), rgba(16, 26, 43, 0.96));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        var(--shadow-soft);
    transform: translateY(-1px);
}

.smai-metric-card[data-emphasis="spotlight"] {
    min-height: 10.2rem;
    border-color: rgba(45, 212, 191, 0.36);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.06),
        0 18px 38px rgba(20, 184, 166, 0.12);
}

.smai-metric-card[data-tone="info"] {
    --smai-card-accent: var(--smai-accent);
    --smai-card-glow: rgba(56, 189, 248, 0.16);
}

.smai-metric-card[data-tone="score"] {
    --smai-card-accent: var(--smai-blue);
    --smai-card-glow: rgba(96, 165, 250, 0.18);
}

.smai-metric-card[data-tone="success"] {
    --smai-card-accent: var(--smai-green);
    --smai-card-glow: rgba(34, 197, 94, 0.16);
}

.smai-metric-card[data-tone="forecast"] {
    --smai-card-accent: var(--smai-teal);
    --smai-card-glow: rgba(45, 212, 191, 0.16);
}

.smai-metric-card[data-tone="caution"] {
    --smai-card-accent: var(--smai-amber);
    --smai-card-glow: rgba(245, 158, 11, 0.17);
}

.smai-metric-card[data-tone="risk"] {
    --smai-card-accent: var(--smai-rose);
    --smai-card-glow: rgba(251, 113, 133, 0.16);
}

.smai-card-label {
    color: var(--text-label);
    font-size: 0.82rem;
    font-weight: 620;
    line-height: 1.3;
    margin-bottom: 0.35rem;
}

.smai-card-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.35rem;
    margin-bottom: 0.35rem;
}

.smai-card-label-row .smai-card-label {
    margin-bottom: 0;
}

.smai-card-help {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1rem;
    height: 1rem;
    flex: 0 0 auto;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.28);
    color: var(--text-caption);
    background: rgba(15, 23, 42, 0.58);
    font-size: 0.68rem;
    font-weight: 760;
    line-height: 1;
}

.smai-card-value {
    color: var(--text-value);
    font-size: 1.32rem;
    line-height: 1.25;
    font-weight: 780;
    overflow-wrap: anywhere;
}

.smai-insight-hero {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
    margin-top: 0.1rem;
}

.smai-insight-kicker {
    color: var(--text-ai-muted);
    font-size: 0.78rem;
    font-weight: 820;
    line-height: 1.25;
}

.smai-insight-result {
    color: var(--text-title);
    font-size: 1.5rem;
    font-weight: 860;
    line-height: 1.16;
    margin-top: 0.12rem;
}

.smai-insight-forecast {
    color: var(--text-secondary);
    font-size: 0.82rem;
    font-weight: 760;
    text-align: right;
}

.smai-insight-forecast strong {
    display: block;
    color: var(--text-value);
    font-size: 1.22rem;
    line-height: 1.18;
}

.smai-insight-center-forecast {
    margin-top: 0.72rem;
    padding: 0.7rem 0.78rem;
    border: 1px solid rgba(34, 211, 238, 0.46);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(34, 211, 238, 0.14), rgba(34, 211, 238, 0.04)),
        rgba(7, 13, 25, 0.78);
}

.smai-insight-center-forecast span {
    display: block;
    color: var(--text-ai-title);
    font-size: 0.82rem;
    font-weight: 840;
}

.smai-insight-center-forecast strong {
    display: block;
    color: var(--smai-cyan);
    font-size: 1.78rem;
    line-height: 1.12;
    font-weight: 880;
    margin-top: 0.1rem;
}

.smai-insight-center-forecast small {
    display: block;
    color: var(--text-ai-muted);
    font-size: 0.76rem;
    font-weight: 760;
    margin-top: 0.18rem;
}

.smai-insight-price-row {
    display: grid;
    grid-template-columns: minmax(10rem, 0.62fr) minmax(14rem, 1fr);
    gap: 0.45rem;
    margin-top: 0.55rem;
}

.smai-insight-price-row > div {
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 0.8rem;
    padding: 0.46rem 0.55rem;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: rgba(7, 13, 25, 0.72);
}

.smai-insight-price-row span {
    flex: 0 0 auto;
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 820;
}

.smai-insight-price-row strong {
    min-width: 0;
    flex: 0 1 auto;
    color: var(--text-heading);
    font-size: 1rem;
    line-height: 1.25;
    text-align: left;
    overflow-wrap: anywhere;
}

.smai-insight-range {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.45rem;
    margin-top: 0.72rem;
}

.smai-insight-range > div {
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 0.8rem;
    padding: 0.5rem 0.62rem;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: rgba(7, 13, 25, 0.72);
}

.smai-insight-range span {
    flex: 0 0 auto;
    color: var(--text-muted);
    font-size: 0.84rem;
    font-weight: 820;
}

.smai-insight-range strong {
    min-width: 0;
    flex: 0 1 auto;
    color: var(--text-heading);
    font-size: 1.22rem;
    line-height: 1.25;
    text-align: left;
    overflow-wrap: anywhere;
}

.smai-insight-range > div[data-case="downside"] {
    border-color: rgba(251, 113, 133, 0.46);
    background:
        linear-gradient(180deg, rgba(251, 113, 133, 0.11), rgba(7, 13, 25, 0.74));
}

.smai-insight-range > div[data-case="downside"] strong {
    color: var(--text-negative);
}

.smai-insight-range > div[data-case="upside"] {
    border-color: rgba(52, 211, 153, 0.44);
    background:
        linear-gradient(180deg, rgba(52, 211, 153, 0.1), rgba(7, 13, 25, 0.74));
}

.smai-insight-range > div[data-case="upside"] strong {
    color: var(--text-positive);
}

.smai-insight-mini-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.45rem;
    margin-top: 0.65rem;
}

.smai-insight-mini-field {
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 0.8rem;
    padding: 0.5rem 0.62rem;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: rgba(7, 13, 25, 0.72);
}

.smai-insight-mini-label {
    flex: 0 0 auto;
    color: var(--text-muted);
    font-size: 0.76rem;
    font-weight: 820;
}

.smai-insight-mini-value {
    min-width: 0;
    flex: 0 1 auto;
    color: var(--text-heading);
    font-size: 1rem;
    font-weight: 840;
    line-height: 1.25;
    text-align: left;
    overflow-wrap: anywhere;
}

.smai-insight-two-col {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: 0.72rem;
    margin-top: 0.78rem;
}

.smai-insight-subtitle {
    color: var(--text-ai-title);
    font-size: 0.8rem;
    font-weight: 840;
    margin-bottom: 0.28rem;
}

.smai-insight-two-col ul {
    margin: 0;
    padding-left: 1rem;
    color: var(--text-secondary);
    font-size: 0.84rem;
    line-height: 1.55;
}

.smai-insight-two-col p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.84rem;
    line-height: 1.55;
}

.vega-embed {
    width: 100%;
}

.vega-bindings {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    align-items: center;
    order: -1 !important;
    align-self: stretch;
    margin: 0.2rem 0 0.5rem 0;
    padding: 0.5rem 0.65rem;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: rgba(7, 13, 25, 0.72);
}

.vega-bind {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--text-secondary);
    font-size: 0.82rem;
    font-weight: 780;
}

.vega-bind input[type="checkbox"] {
    accent-color: var(--smai-cyan);
}

@media (max-width: 720px) {
    .smai-insight-price-row,
    .smai-insight-range,
    .smai-insight-mini-grid {
        grid-template-columns: 1fr;
    }

    .smai-insight-price-row > div,
    .smai-insight-range > div,
    .smai-insight-mini-field {
        align-items: flex-start;
        flex-direction: column;
        gap: 0.22rem;
    }

    .smai-insight-price-row strong,
    .smai-insight-range strong,
    .smai-insight-mini-value {
        text-align: left;
    }
}

.smai-card-caption {
    color: var(--text-caption);
    font-size: 0.86rem;
    line-height: 1.52;
    margin-top: 0.5rem;
}

.smai-ranking-card {
    --smai-card-accent: var(--smai-teal);
    --smai-card-glow: rgba(45, 212, 191, 0.16);
    position: relative;
    min-height: 11.8rem;
    border: 1px solid var(--smai-border);
    border-left: 3px solid var(--smai-card-accent);
    border-radius: 8px;
    background:
        linear-gradient(90deg, var(--smai-card-glow), transparent 62%),
        linear-gradient(180deg, rgba(23, 35, 56, 0.94), rgba(11, 18, 32, 0.93));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        var(--shadow-subtle);
    padding: 0.86rem 0.95rem;
    overflow-wrap: anywhere;
    transition:
        border-color 140ms ease,
        background 140ms ease,
        transform 140ms ease,
        box-shadow 140ms ease;
}

.smai-ranking-card::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 1px;
    background: linear-gradient(90deg, var(--smai-card-accent), rgba(255, 255, 255, 0.08), transparent);
    opacity: 0.72;
}

.smai-ranking-card:hover {
    border-color: var(--border-strong);
    background:
        linear-gradient(90deg, var(--smai-card-glow), transparent 62%),
        linear-gradient(180deg, rgba(23, 35, 56, 1), rgba(16, 26, 43, 0.96));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        var(--shadow-soft);
    transform: translateY(-1px);
}

.smai-ranking-card[data-emphasis="spotlight"] {
    border-color: rgba(45, 212, 191, 0.36);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.06),
        0 18px 38px rgba(20, 184, 166, 0.12);
}

.smai-ranking-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.45rem;
    color: var(--text-label);
    font-size: 0.76rem;
    font-weight: 700;
    line-height: 1.25;
    margin-bottom: 0.3rem;
}

.smai-ranking-card-symbol {
    overflow-wrap: anywhere;
}

.smai-ranking-card-name {
    color: var(--text-heading);
    font-size: 1rem;
    line-height: 1.28;
    font-weight: 780;
    min-height: 2.55rem;
    margin-bottom: 0.56rem;
    overflow-wrap: anywhere;
}

.smai-ranking-card-metric {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
}

.smai-ranking-card-metric-label {
    color: var(--text-label);
    font-size: 0.78rem;
    line-height: 1.3;
    font-weight: 720;
    overflow-wrap: anywhere;
}

.smai-ranking-card-metric-value {
    color: var(--text-value);
    font-size: 1.18rem;
    line-height: 1.2;
    font-weight: 800;
    text-align: right;
    overflow-wrap: anywhere;
}

.smai-ranking-card-caption {
    color: var(--text-caption);
    font-size: 0.84rem;
    line-height: 1.5;
    margin-top: 0.55rem;
    overflow-wrap: anywhere;
}

.smai-score-track {
    height: 0.38rem;
    border-radius: 999px;
    background: rgba(148, 163, 184, 0.16);
    overflow: hidden;
    margin-top: 0.72rem;
}

.smai-score-fill {
    height: 100%;
    width: var(--smai-score-width);
    border-radius: inherit;
    background: linear-gradient(90deg, var(--smai-card-accent), var(--smai-teal));
    box-shadow: 0 0 18px var(--smai-card-glow);
}

.smai-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.32rem;
    margin-top: 0.58rem;
}

.smai-badge {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.14rem 0.48rem;
    border: 1px solid transparent;
    font-size: 0.72rem;
    font-weight: 680;
    line-height: 1.3;
}

.smai-badge.info {
    color: var(--text-info);
    background: rgba(56, 189, 248, 0.15);
    border-color: rgba(56, 189, 248, 0.28);
}

.smai-badge.success {
    color: var(--text-positive);
    background: rgba(34, 197, 94, 0.15);
    border-color: rgba(34, 197, 94, 0.28);
}

.smai-badge.caution {
    color: var(--text-warning);
    background: rgba(245, 158, 11, 0.16);
    border-color: rgba(245, 158, 11, 0.3);
}

.smai-badge.danger {
    color: var(--text-negative);
    background: rgba(251, 113, 133, 0.15);
    border-color: rgba(251, 113, 133, 0.28);
}

.smai-badge.neutral {
    color: var(--text-neutral);
    background: rgba(100, 116, 139, 0.14);
    border-color: rgba(148, 163, 184, 0.18);
}

.text-title,
.smai-text-title {
    color: var(--text-title);
    font-weight: 720;
}

.text-heading,
.smai-text-heading {
    color: var(--text-heading);
    font-weight: 700;
}

.text-value,
.smai-text-value {
    color: var(--text-value);
    font-weight: 700;
}

.text-label,
.smai-text-label {
    color: var(--text-label);
    font-weight: 560;
}

.text-caption,
.smai-text-caption {
    color: var(--text-caption);
}

.ai-title,
.smai-ai-title {
    color: var(--text-ai-title);
    font-weight: 720;
}

.ai-body,
.smai-ai-body {
    color: var(--text-ai-primary);
}

.ai-muted,
.smai-ai-muted {
    color: var(--text-ai-muted);
}

.positive,
.smai-text-positive {
    color: var(--text-positive);
}

.negative,
.smai-text-negative {
    color: var(--text-negative);
}

.warning,
.smai-text-warning {
    color: var(--text-warning);
}

.info,
.smai-text-info {
    color: var(--text-info);
}

.neutral,
.smai-text-neutral {
    color: var(--text-neutral);
}

@media print {
    .smai-metric-card,
    .smai-ranking-card,
    .smai-section-card,
    .smai-forecast-card {
        break-inside: avoid;
        page-break-inside: avoid;
        min-height: auto !important;
        box-shadow: none !important;
    }

    .smai-score-track,
    .smai-badge-row {
        margin-top: 0.36rem;
    }

    [data-testid="stVerticalBlock"] {
        gap: 0.45rem;
    }
}

.link,
.smai-link {
    color: #7DD3FC;
    text-decoration: none;
}

.link:hover,
.smai-link:hover {
    color: #BAE6FD;
    text-decoration: underline;
}

.table-header {
    background: var(--table-header-bg);
    color: var(--text-heading);
    font-weight: 700;
}

.table-label {
    color: var(--text-label);
    font-weight: 700;
}

.table-value {
    color: var(--text-value);
    font-weight: 620;
}

.table-comment {
    color: var(--text-secondary);
    font-weight: 620;
}

.table-muted {
    color: var(--text-muted);
    font-weight: 620;
}

.card-title {
    color: var(--text-heading);
    font-weight: 820;
}

.card-label {
    color: var(--text-label);
    font-size: 0.85rem;
    font-weight: 780;
}

.card-value {
    color: var(--text-value);
    font-weight: 700;
}

.card-description {
    color: var(--text-secondary);
    font-weight: 640;
}

.card-meta {
    color: var(--text-muted);
    font-weight: 620;
}

/* Final readability baseline: keep late component styles from fading text back out. */
.stApp small,
.stApp figcaption,
.stApp [class*="caption"],
.stApp [class*="Caption"],
.stApp [class*="muted"],
.stApp [class*="Muted"],
.stApp [class*="meta"],
.stApp [class*="Meta"] {
    color: var(--text-caption);
    font-weight: 620;
}

.stApp [class*="label"],
.stApp [class*="Label"],
.stApp [class*="kicker"],
.stApp [class*="Kicker"] {
    color: var(--text-label);
    font-weight: 760;
}

.stApp [class*="title"],
.stApp [class*="Title"],
.stApp [class*="heading"],
.stApp [class*="Heading"] {
    color: var(--text-heading);
}

/*
 * Responsive baseline for LAN clients.
 * Page-specific layouts may add a semantic class, but these shared rules own
 * breakpoints, safe wrapping, touch targets, charts, tables, and Streamlit
 * columns. Desktop information density remains unchanged above 1024px.
 */
.smai-responsive-grid,
.smai-card-grid-responsive {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.9rem;
    width: 100%;
}

.smai-responsive-grid > *,
.smai-card-grid-responsive > *,
.smai-metric-card,
.smai-ranking-card,
.smai-watchlist-card,
.investment-news-card,
[data-testid="stHorizontalBlock"] > [data-testid="column"] {
    min-width: 0;
    max-width: 100%;
}

.smai-metric-card,
.smai-ranking-card,
.smai-watchlist-card,
.investment-news-card,
.smai-section-card,
.smai-copilot-panel,
.smai-copilot-answer-grid,
.smai-dashboard-header {
    overflow-wrap: anywhere;
    word-break: break-word;
}

/*
 * Long result feeds are common on phones.  Reserving a realistic card size
 * lets the browser defer paint/layout work for cards outside the viewport
 * without changing the data, ordering, or accessibility of the feed.
 */
.smai-watchlist-card,
.investment-news-card,
.smai-ranking-history-card,
.research-evidence-item,
.smai-notification-row {
    content-visibility: auto;
    contain-intrinsic-size: auto 18rem;
}

[data-testid="stPlotlyChart"],
[data-testid="stVegaLiteChart"],
[data-testid="stDataFrame"],
[data-testid="stDataEditor"],
[data-testid="stTable"],
.js-plotly-plot,
.plot-container,
.plotly,
.vega-embed {
    min-width: 0;
    max-width: 100%;
}

[data-testid="stVegaLiteChart"] {
    contain: inline-size;
    overflow: hidden;
    width: 100%;
}

[data-testid="stVegaLiteChart"] .vega-embed,
[data-testid="stVegaLiteChart"] .vega-embed > div {
    max-width: 100%;
}

[data-testid="stVegaLiteChart"] canvas,
[data-testid="stVegaLiteChart"] svg {
    height: auto !important;
    max-width: 100% !important;
}

[data-testid="stDataFrame"],
[data-testid="stDataEditor"],
[data-testid="stTable"],
.ag-root-wrapper,
.smai-table-scroll {
    overflow-x: auto;
    overscroll-behavior-inline: contain;
    -webkit-overflow-scrolling: touch;
}

dialog[open] {
    max-width: min(44rem, calc(100vw - 2rem));
    max-height: calc(100dvh - 2rem);
    overflow: auto;
}

div[data-testid="stDialog"] {
    position: fixed !important;
    inset: 0 !important;
    z-index: 2000 !important;
    display: grid !important;
    place-items: center !important;
    box-sizing: border-box;
    padding: 1rem !important;
    background: rgba(2, 8, 23, 0.76);
    backdrop-filter: blur(6px);
}

div[data-testid="stDialog"] div[role="dialog"] {
    position: relative !important;
    inset: auto !important;
    top: auto !important;
    right: auto !important;
    bottom: auto !important;
    left: auto !important;
    transform: none !important;
    align-self: center !important;
    justify-self: center !important;
    width: min(44rem, calc(100vw - 2rem));
    max-width: min(44rem, calc(100vw - 2rem));
    max-height: calc(100dvh - 2rem);
    margin: 0 auto;
    overflow: auto;
}

@media (min-width: 768px) and (max-width: 1024px) {
    div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
            div[data-testid="stForm"]
        ) {
        left: 0;
        flex-wrap: nowrap;
        padding-right: 1.1rem;
        padding-left: 1.1rem;
    }

    div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
            div[data-testid="stForm"]
        )
        > [data-testid="column"]:first-child {
        flex: 0 1 30% !important;
        width: 30% !important;
    }

    div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar):has(
            div[data-testid="stForm"]
        )
        > [data-testid="column"]:last-child {
        flex: 1 1 70% !important;
        width: 70% !important;
    }

    div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar)
        div[data-testid="stForm"]
        div[data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap;
    }

    div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar)
        div[data-testid="stForm"]
        div[data-testid="stHorizontalBlock"]
        > [data-testid="column"]:first-child {
        flex: 1 1 82% !important;
        width: 82% !important;
    }

    div[data-testid="stHorizontalBlock"]:has(.smai-copilot-composer-toolbar)
        div[data-testid="stForm"]
        div[data-testid="stHorizontalBlock"]
        > [data-testid="column"]:last-child {
        flex: 0 1 18% !important;
        width: 18% !important;
    }

    [data-testid="stMainBlockContainer"] {
        padding-left: 1.1rem;
        padding-right: 1.1rem;
        padding-top: 1rem !important;
    }

    [data-testid="stAppViewContainer"] .main .block-container,
    [data-testid="stAppViewContainer"] [data-testid="stAppViewMain"] .block-container {
        padding-top: 1rem !important;
    }

    .smai-responsive-grid,
    .smai-card-grid-responsive {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
    }

    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 calc(50% - 0.5rem) !important;
        width: calc(50% - 0.5rem) !important;
    }

    [data-testid="stButton"] button,
    [data-testid="stDownloadButton"] button,
    [data-testid="stLinkButton"] a {
        /* Keep touch controls at least 44 CSS px after the compact root font scale. */
        min-height: 44px;
        touch-action: manipulation;
    }

    .smai-floating-assistant {
        right: 0.75rem;
        bottom: 0.75rem;
        max-width: calc(100vw - 1.5rem);
    }

    .smai-floating-assistant-stage {
        max-height: min(62vh, 31rem);
    }

    .investment-news-card,
    .smai-watchlist-card,
    .smai-ranking-card {
        max-width: 100%;
        overflow-wrap: anywhere;
    }
}

@media (max-width: 767px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        padding-top: 0.75rem !important;
    }

    [data-testid="stAppViewContainer"] .main .block-container,
    [data-testid="stAppViewContainer"] [data-testid="stAppViewMain"] .block-container {
        padding-top: 0.75rem !important;
    }

    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
    }

    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 100% !important;
        min-width: 100% !important;
        width: 100% !important;
    }

    /* Keep compact, scan-oriented KPI rows at two columns on a phone. */
    [data-testid="stMainBlockContainer"]
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] [data-testid="stMetric"])
        > [data-testid="column"] {
        flex: 1 1 calc(50% - 0.35rem) !important;
        min-width: calc(50% - 0.35rem) !important;
        width: calc(50% - 0.35rem) !important;
    }

    /* Two mutually exclusive actions stay together instead of creating a
       long one-button-per-row detour.  Input-bearing rows still stack. */
    [data-testid="stMainBlockContainer"]
        [data-testid="stHorizontalBlock"]:has(> [data-testid="column"]:first-child [data-testid="stButton"]):has(> [data-testid="column"]:nth-child(2) [data-testid="stButton"]):not(:has(> [data-testid="column"]:nth-child(3))):not(:has([data-testid="stTextInput"], [data-testid="stTextArea"], [data-testid="stSelectbox"], [data-testid="stMultiSelect"], [data-testid="stDateInput"], [data-testid="stNumberInput"]))
        > [data-testid="column"] {
        flex: 1 1 calc(50% - 0.35rem) !important;
        min-width: calc(50% - 0.35rem) !important;
        width: calc(50% - 0.35rem) !important;
    }

    .smai-responsive-grid,
    .smai-card-grid-responsive,
    .smai-copilot-answer-grid,
    .smai-ranking-weight-grid {
        grid-template-columns: 1fr;
    }

    [data-testid="stButton"],
    [data-testid="stDownloadButton"],
    [data-testid="stLinkButton"],
    [data-testid="stSelectbox"],
    [data-testid="stMultiSelect"] {
        width: 100%;
        min-width: 0;
    }

    [data-testid="stButton"] button,
    [data-testid="stDownloadButton"] button,
    [data-testid="stLinkButton"] a {
        width: 100%;
        /* Keep touch controls at least 44 CSS px after the compact root font scale. */
        min-height: 44px;
        white-space: normal;
        touch-action: manipulation;
    }

    [data-testid="stPlotlyChart"],
    [data-testid="stVegaLiteChart"] {
        width: 100%;
        overflow: hidden;
    }

    [data-testid="stTabs"] [role="tablist"] {
        overflow-x: auto;
        scrollbar-width: thin;
    }

    [data-testid="stMetric"],
    .smai-metric-card,
    .smai-ranking-card,
    .smai-watchlist-card,
    .investment-news-card {
        width: 100%;
    }

    .smai-floating-assistant {
        right: 0.5rem;
        bottom: 0.5rem;
        max-width: calc(100vw - 1rem);
    }

    /* A wide fixed launcher obscures the active card on a phone.  Keep the
       full assistant panel available after activation, while making its
       resting touch target a compact, accessible avatar button. */
    .smai-floating-assistant-trigger {
        grid-template-columns: 3.35rem;
        gap: 0;
        min-width: 3.75rem;
        max-width: 3.75rem;
        padding: 0.2rem;
    }

    .smai-floating-assistant-trigger-copy {
        display: none;
    }

    .smai-floating-assistant-avatar {
        width: 3.35rem;
        height: 3.35rem;
    }

    .smai-floating-assistant-avatar img {
        width: 2.85rem;
        height: 3.15rem;
    }

    .smai-floating-assistant-stage {
        max-height: min(58vh, 28rem);
    }

    .smai-page-title,
    .smai-page-title--copilot {
        overflow-wrap: anywhere;
    }
}

@media (min-width: 1025px) {
    .smai-responsive-grid,
    .smai-card-grid-responsive {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

.smai-ranking-history-card {
    display: grid;
    grid-template-columns:
        minmax(0, 0.8fr)
        minmax(0, 1.3fr)
        minmax(0, 1.65fr)
        minmax(0, 1.05fr)
        minmax(6.5rem, 0.7fr);
    align-items: center;
    gap: 1rem;
    width: 100%;
    min-width: 0;
    margin: 0 0 0.65rem;
    padding: 0.9rem 1rem;
    border: 1px solid rgba(96, 165, 250, 0.26);
    border-left: 4px solid #22d3ee;
    border-radius: 12px;
    background: linear-gradient(145deg, rgba(12, 28, 48, 0.98), rgba(8, 20, 36, 0.98));
    box-shadow: 0 8px 22px rgba(1, 8, 20, 0.18);
    color: #e5edf7;
    text-decoration: none !important;
    overflow-wrap: anywhere;
    transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

a.smai-ranking-history-card:hover,
a.smai-ranking-history-card:focus-visible {
    border-color: rgba(34, 211, 238, 0.72);
    background: linear-gradient(145deg, rgba(18, 43, 72, 0.99), rgba(10, 28, 49, 0.99));
    color: #f8fbff;
    outline: none;
    transform: translateY(-1px);
}

.smai-ranking-history-nav-anchor {
    display: block;
    height: 0;
}

[data-testid="element-container"]:has(.smai-ranking-history-nav-anchor)
    + [data-testid="element-container"] div[data-testid="stButton"] button {
    min-height: 3rem;
    border-radius: 10px;
    font-weight: 850 !important;
    letter-spacing: 0.01em;
    transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

[data-testid="element-container"]:has(.smai-ranking-history-nav-anchor--primary)
    + [data-testid="element-container"] div[data-testid="stButton"] button {
    border-color: rgba(103, 232, 249, 0.82) !important;
    background:
        linear-gradient(135deg, rgba(8, 145, 178, 0.98), rgba(20, 184, 166, 0.94))
        !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.2),
        0 10px 24px rgba(8, 145, 178, 0.26),
        0 0 20px rgba(34, 211, 238, 0.12);
}

[data-testid="element-container"]:has(.smai-ranking-history-nav-anchor--primary)
    + [data-testid="element-container"] div[data-testid="stButton"] button * {
    color: #ffffff !important;
    font-weight: 900 !important;
}

[data-testid="element-container"]:has(.smai-ranking-history-nav-anchor--secondary)
    + [data-testid="element-container"] div[data-testid="stButton"] button {
    border-color: rgba(34, 211, 238, 0.62) !important;
    background:
        linear-gradient(180deg, rgba(8, 78, 99, 0.38), rgba(15, 31, 52, 0.88))
        !important;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.08),
        0 8px 20px rgba(2, 12, 27, 0.22);
}

[data-testid="element-container"]:has(.smai-ranking-history-nav-anchor--secondary)
    + [data-testid="element-container"] div[data-testid="stButton"] button * {
    color: #a5f3fc !important;
    font-weight: 850 !important;
}

[data-testid="element-container"]:has(.smai-ranking-history-nav-anchor)
    + [data-testid="element-container"] div[data-testid="stButton"] button:hover {
    border-color: #cffafe !important;
    box-shadow:
        0 0 0 2px rgba(103, 232, 249, 0.2),
        0 14px 30px rgba(8, 145, 178, 0.3);
    transform: translateY(-1px);
}

.smai-ranking-history-card--alt {
    background: linear-gradient(145deg, rgba(14, 35, 61, 0.98), rgba(9, 25, 45, 0.98));
    border-left-color: #60a5fa;
}

.smai-ranking-history-card--pinned {
    border-color: rgba(250, 204, 21, 0.42);
    border-left-color: #facc15;
    background: linear-gradient(145deg, rgba(32, 35, 52, 0.98), rgba(10, 25, 43, 0.98));
}

.smai-ranking-history-list-primary,
.smai-ranking-history-list-meta,
.smai-ranking-history-list-conditions,
.smai-ranking-history-list-symbols {
    min-width: 0;
}

.smai-ranking-history-list-primary {
    display: grid;
    gap: 0.35rem;
}

.smai-ranking-history-list-primary time {
    color: #aab8c8;
    font-size: 0.78rem;
    font-weight: 700;
}

.smai-ranking-history-list-primary > strong {
    color: #f8fbff;
    font-size: 1rem;
}

.smai-ranking-history-card-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
}

.smai-ranking-history-card-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    min-height: 2.65rem;
    padding: 0.55rem 0.75rem;
    border: 1px solid rgba(34, 211, 238, 0.55);
    border-radius: 9px;
    color: #e9fbff;
    background: rgba(8, 78, 99, 0.4);
    font-size: 0.82rem;
    font-weight: 800;
    white-space: nowrap;
}

a.smai-ranking-history-card:hover .smai-ranking-history-card-action,
a.smai-ranking-history-card:focus-visible .smai-ranking-history-card-action {
    border-color: #67e8f9;
    background: rgba(14, 116, 144, 0.58);
}

.smai-ranking-history-card-header,
.smai-ranking-history-card-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
}

.smai-ranking-history-card-header time,
.smai-ranking-history-card-label {
    color: #aab8c8;
    font-size: 0.78rem;
    font-weight: 700;
}

.smai-ranking-history-card-title strong {
    color: #f8fbff;
    font-size: 1.08rem;
}

.smai-ranking-history-badge,
.smai-ranking-history-chip,
.smai-ranking-history-symbol-tag {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    padding: 0.25rem 0.55rem;
    border: 1px solid rgba(96, 165, 250, 0.34);
    border-radius: 999px;
    color: #d8f3ff;
    background: rgba(30, 64, 108, 0.5);
    font-size: 0.76rem;
    line-height: 1.35;
    white-space: normal;
}

.smai-ranking-history-badge--pinned {
    border-color: rgba(250, 204, 21, 0.42);
    color: #fef3c7;
    background: rgba(113, 63, 18, 0.34);
}

.smai-ranking-history-chip--condition {
    border-color: rgba(34, 211, 238, 0.28);
    background: rgba(8, 78, 99, 0.28);
}

.smai-ranking-history-chip-row,
.smai-ranking-history-symbol-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.45rem 0 0.8rem;
}

.smai-ranking-history-symbol-tag {
    color: #eaf1fb;
    background: rgba(17, 31, 53, 0.92);
}

.smai-ranking-history-detail-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
    margin: 1rem 0;
}

.smai-ranking-history-summary-card,
.smai-ranking-history-metric-card {
    min-width: 0;
    padding: 1rem;
    border: 1px solid rgba(70, 91, 120, 0.8);
    border-radius: 14px;
    background: rgba(11, 26, 45, 0.94);
}

.smai-ranking-history-summary-card strong,
.smai-ranking-history-metric-card > strong {
    display: block;
    margin: 0.3rem 0;
    color: #f8fbff;
}

.smai-ranking-history-summary-card p,
.smai-ranking-history-metric-card p,
.smai-ranking-history-metric-card small {
    color: #b4c2d3;
    overflow-wrap: anywhere;
}

.smai-ranking-history-metric-card {
    min-height: 13.5rem;
}

.smai-ranking-history-rank {
    display: block;
    color: #67e8f9;
    font-size: 0.78rem;
    font-weight: 800;
}

.smai-ranking-history-metrics {
    display: grid;
    gap: 0.3rem;
    margin: 0.7rem 0;
    color: #c8d4e3;
    font-size: 0.8rem;
}

@media (max-width: 1024px) {
    .smai-ranking-history-card {
        grid-template-columns: minmax(8rem, 0.8fr) minmax(0, 1.2fr);
    }

    .smai-ranking-history-list-symbols {
        grid-column: 1 / 2;
    }

    .smai-ranking-history-card-action {
        grid-column: 2;
        grid-row: auto;
    }

    .smai-ranking-history-detail-summary {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 767px) {
    .smai-ranking-history-card {
        grid-template-columns: 1fr;
        gap: 0.65rem;
        padding: 0.85rem;
    }

    .smai-ranking-history-list-symbols,
    .smai-ranking-history-card-action {
        grid-column: auto;
        grid-row: auto;
    }

    .smai-ranking-history-card-header,
    .smai-ranking-history-card-title {
        align-items: flex-start;
        flex-direction: column;
    }

}
</style>
"""


def render_global_styles() -> None:
    st.markdown(SMAI_GLOBAL_CSS, unsafe_allow_html=True)


def style_altair_chart(chart: alt.Chart) -> alt.Chart:
    return _components.style_altair_chart(chart, THEME_COLORS)
