from __future__ import annotations

import html
from decimal import Decimal, InvalidOperation
from typing import Iterable

import altair as alt
import streamlit as st

THEME_COLORS = {
    "bg_app": "#020510",
    "bg_surface": "#070D19",
    "bg_card": "#111F35",
    "bg_card_hover": "#17283F",
    "bg_elevated": "#1A2B45",
    "text_title": "#F8FBFF",
    "text_heading": "#EAF1FB",
    "text_primary": "#D7E2F0",
    "text_secondary": "#AEBBD0",
    "text_muted": "#7F8DA3",
    "text_disabled": "#596579",
    "text_value": "#F1F5F9",
    "text_label": "#91A3BA",
    "text_caption": "#8492A8",
    "text_ai_title": "#67E8F9",
    "text_ai_primary": "#D8F3FF",
    "text_ai_muted": "#9ACFE0",
    "text_positive": "#6EE7B7",
    "text_negative": "#FDA4AF",
    "text_warning": "#FCD34D",
    "text_info": "#93C5FD",
    "text_neutral": "#CBD5E1",
    "border_subtle": "#25344D",
    "border_default": "#31425F",
    "border_strong": "#49607F",
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
        "overflow-wrap": "anywhere",
        "white-space": "normal",
    },
    ".ag-cell-value": {
        "color": f"{THEME_COLORS['text_value']} !important",
        "overflow-wrap": "anywhere",
        "white-space": "normal",
    },
}

SMAI_GLOBAL_CSS = """
<style>
:root {
    /* Background */
    --bg-app: #020510;
    --bg-surface: #070D19;
    --bg-card: #111F35;
    --bg-card-hover: #17283F;
    --bg-elevated: #1A2B45;

    /* Text */
    --text-title: #F8FBFF;
    --text-heading: #EAF1FB;
    --text-primary: #D7E2F0;
    --text-secondary: #AEBBD0;
    --text-muted: #7F8DA3;
    --text-disabled: #596579;

    /* Text hierarchy */
    --text-value: #F1F5F9;
    --text-label: #91A3BA;
    --text-caption: #8492A8;

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
    --border-subtle: #25344D;
    --border-default: #31425F;
    --border-strong: #49607F;

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
    --table-row-bg: #070D19;
    --table-row-hover: #17283F;

    /* Button */
    --button-primary-bg: #0891B2;
    --button-primary-hover: #06B6D4;
    --button-secondary-bg: #111C2E;
    --button-secondary-border: #2C3B55;

    /* Surface treatment */
    --surface-glass: rgba(16, 26, 43, 0.78);
    --surface-raised: rgba(23, 35, 56, 0.82);
    --shadow-soft: 0 18px 46px rgba(0, 0, 0, 0.24);
    --shadow-subtle: 0 10px 26px rgba(0, 0, 0, 0.16);

    /* Backwards-compatible aliases for existing components. */
    --smai-bg: var(--bg-app);
    --smai-panel: var(--bg-surface);
    --smai-card: var(--bg-card);
    --smai-card-soft: var(--bg-elevated);
    --smai-border: rgba(49, 66, 95, 0.92);
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

.stApp {
    background:
        linear-gradient(90deg, rgba(30, 42, 62, 0.18) 1px, transparent 1px),
        linear-gradient(180deg, var(--bg-app) 0%, var(--bg-surface) 100%);
    background-size: 56px 56px, auto;
    color: var(--text-primary);
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
    background: rgba(5, 8, 18, 0.72);
    backdrop-filter: blur(10px);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--bg-app) 0%, var(--bg-surface) 100%);
    border-right: 1px solid var(--smai-border);
}

[data-testid="stAppViewContainer"] .main .block-container {
    padding-top: 2.2rem;
    padding-bottom: 3.8rem;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 500;
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
    font-weight: 520;
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
    min-height: 2.35rem;
    border-radius: 8px;
    border: 1px solid var(--button-secondary-border);
    background:
        linear-gradient(180deg, rgba(23, 35, 56, 0.88), rgba(17, 28, 46, 0.88));
    color: var(--text-primary);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
    transition:
        border-color 120ms ease,
        background 120ms ease,
        background-position 240ms ease,
        box-shadow 120ms ease,
        transform 120ms ease;
}

[data-testid="stButton"] button [data-testid="stMarkdownContainer"] p {
    color: inherit;
    font-weight: inherit;
    line-height: 1.2;
}

[data-testid="stButton"] button:hover {
    border-color: var(--ai-border);
    background: var(--bg-card-hover);
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.12);
    transform: translateY(-1px);
}

[data-testid="stButton"] button[kind="primary"] {
    border-color: rgba(45, 212, 191, 0.72);
    background:
        linear-gradient(
            135deg,
            rgba(14, 165, 233, 0.98) 0%,
            rgba(34, 211, 238, 0.96) 48%,
            rgba(20, 184, 166, 0.94) 100%
        );
    background-size: 180% 180%;
    background-position: 0% 50%;
    color: #04111F;
    font-weight: 820;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.14),
        0 12px 26px rgba(20, 184, 166, 0.18),
        0 0 0 1px rgba(34, 211, 238, 0.1);
}

[data-testid="stButton"] button[kind="primary"]:hover {
    background:
        linear-gradient(
            135deg,
            rgba(56, 189, 248, 1) 0%,
            rgba(34, 211, 238, 0.98) 45%,
            rgba(45, 212, 191, 0.98) 100%
        );
    background-size: 180% 180%;
    background-position: 100% 50%;
    color: #04111F;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.18),
        0 14px 34px rgba(20, 184, 166, 0.24),
        0 0 0 1px rgba(34, 211, 238, 0.18);
}

[data-baseweb="select"] > div,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input {
    border-color: var(--border-default);
    background-color: rgba(16, 26, 43, 0.92);
    color: var(--text-primary);
    border-radius: 8px;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
    min-height: 2.35rem;
}

[data-baseweb="select"] > div:hover,
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stDateInput"] input:focus {
    border-color: var(--ai-blue);
    box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.16);
}

[data-testid="stTextInput"] input:disabled,
[data-testid="stDateInput"] input:disabled,
[data-testid="stNumberInput"] input:disabled {
    background-color: rgba(16, 26, 43, 0.64);
    color: var(--text-disabled);
    opacity: 1;
}

[data-baseweb="select"] span,
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stDateInput"] label,
[data-testid="stCheckbox"] label {
    color: var(--text-label);
    font-weight: 720;
    letter-spacing: 0;
}

[data-testid="stSidebar"] [data-testid="stButton"] button {
    border-radius: 8px;
    border: 1px solid var(--smai-border);
    background: rgba(21, 27, 46, 0.78);
    color: var(--smai-text);
}

[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
    border-color: rgba(56, 189, 248, 0.45);
    background: rgba(56, 189, 248, 0.14);
}

[data-testid="stMetric"] {
    padding: 0.84rem 0.9rem;
    border: 1px solid var(--smai-border);
    border-radius: 8px;
    background: var(--bg-card);
}

[data-testid="stMetricLabel"] {
    color: var(--text-label);
}

[data-testid="stMetricValue"] {
    color: var(--text-value);
    letter-spacing: 0;
    font-weight: 720;
}

[data-testid="stExpander"] {
    border: 1px solid var(--border-default);
    border-radius: 8px;
    background:
        linear-gradient(180deg, rgba(16, 26, 43, 0.74), rgba(11, 18, 32, 0.72));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
    margin: 0.65rem 0 1rem;
}

[data-testid="stExpander"] details summary {
    color: var(--text-heading);
    min-height: 2.75rem;
    font-weight: 780;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border-default);
    border-radius: 8px;
    background:
        linear-gradient(180deg, rgba(16, 26, 43, 0.88), rgba(11, 18, 32, 0.86));
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
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 1.2rem;
    border-bottom: 1px solid var(--border-subtle);
    padding: 0.25rem 0 1.05rem;
    margin: 0 0 1.05rem;
}

.smai-app-header::after {
    content: "";
    position: absolute;
    left: 0;
    bottom: -1px;
    width: min(22rem, 42vw);
    height: 1px;
    background: linear-gradient(90deg, var(--ai-cyan), rgba(96, 165, 250, 0.42), transparent);
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

.smai-app-message {
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 650;
    line-height: 1.55;
    margin: 0.45rem 0 0;
}

.smai-app-mascot-wrap {
    position: relative;
    width: clamp(4.5rem, 8vw, 6.8rem);
    aspect-ratio: 1;
    display: grid;
    place-items: center;
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
    border-top: 1px solid rgba(49, 66, 95, 0.74);
    border-bottom: 1px solid var(--border-subtle);
    background: linear-gradient(90deg, rgba(17, 31, 53, 0.82), rgba(7, 13, 25, 0.36) 62%, transparent);
    padding: 1.05rem 1.1rem 1rem 1.35rem;
    margin: 0 0 1rem;
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
    padding: 0.66rem 0.78rem;
    margin: 0.55rem 0 0.85rem;
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
    .smai-insight-avatar img,
    .smai-mascot-image--loading,
    .smai-loading-pulse,
    .smai-loading-dots span {
        animation: none;
    }
}

@media (max-width: 720px) {
    .smai-app-header {
        grid-template-columns: 1fr;
        gap: 0.8rem;
    }

    .smai-app-mascot-wrap {
        width: 4.4rem;
    }

    .smai-page-title-row {
        gap: 0.55rem;
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
    font-weight: 560;
}

.table-value {
    color: var(--text-value);
    font-weight: 620;
}

.table-comment {
    color: var(--text-secondary);
}

.table-muted {
    color: var(--text-muted);
}

.card-title {
    color: var(--text-heading);
    font-weight: 700;
}

.card-label {
    color: var(--text-label);
    font-size: 0.85rem;
}

.card-value {
    color: var(--text-value);
    font-weight: 700;
}

.card-description {
    color: var(--text-secondary);
}

.card-meta {
    color: var(--text-muted);
}
</style>
"""

CARD_TONES = {"neutral", "info", "score", "success", "forecast", "caution", "risk"}
CARD_EMPHASIS = {"normal", "spotlight"}


def render_global_styles() -> None:
    st.markdown(SMAI_GLOBAL_CSS, unsafe_allow_html=True)


def compact_display_value(value: object, fallback: str = "-") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    suffix = "%" if text.endswith("%") else ""
    numeric_text = text.removesuffix("%").replace(",", "").strip()
    try:
        number = Decimal(numeric_text)
    except InvalidOperation:
        return text
    if not number.is_finite():
        return fallback
    if number == number.to_integral_value():
        formatted = f"{number:.0f}"
    else:
        formatted = f"{number:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}{suffix}"


def truncate_text(value: object, *, max_chars: int = 48, fallback: str = "-") -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return fallback
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def badge_html(label: str, tone: str = "neutral") -> str:
    safe_tone = tone if tone in {"info", "success", "caution", "danger", "neutral"} else "neutral"
    return f'<span class="smai-badge {safe_tone}">{html.escape(label)}</span>'


def _safe_card_tone(tone: str) -> str:
    return tone if tone in CARD_TONES else "neutral"


def _safe_card_emphasis(emphasis: str) -> str:
    return emphasis if emphasis in CARD_EMPHASIS else "normal"


def metric_progress_from_value(value: object) -> int | None:
    text = str(value or "").strip().removesuffix("%").replace(",", "")
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    clamped = min(Decimal("100"), max(Decimal("0"), number))
    return int(clamped.to_integral_value(rounding="ROUND_HALF_UP"))


def metric_card_html(
    label: str,
    value: object,
    *,
    caption: str = "",
    help_text: str = "",
    badges: tuple[str, ...] = (),
    tone: str = "neutral",
    emphasis: str = "normal",
    progress: int | None = None,
) -> str:
    badge_row = ""
    if badges:
        badge_row = f'<div class="smai-badge-row">{"".join(badges)}</div>'
    progress_bar = ""
    if progress is not None:
        safe_progress = min(100, max(0, int(progress)))
        progress_bar = (
            '<div class="smai-score-track" aria-hidden="true">'
            f'<div class="smai-score-fill" style="--smai-score-width: {safe_progress}%"></div>'
            "</div>"
        )
    caption_html = (
        f'<div class="smai-card-caption" title="{html.escape(caption)}">'
        f"{html.escape(truncate_text(caption, max_chars=82, fallback=''))}</div>"
        if caption
        else ""
    )
    if help_text:
        label_html = (
            '<div class="smai-card-label-row">'
            f'<div class="smai-card-label">{html.escape(label)}</div>'
            '<span class="smai-card-help" '
            f'title="{html.escape(help_text, quote=True)}" '
            f'aria-label="{html.escape(label, quote=True)} の説明">?</span>'
            "</div>"
        )
    else:
        label_html = f'<div class="smai-card-label">{html.escape(label)}</div>'
    return (
        '<div class="smai-metric-card" '
        f'data-tone="{_safe_card_tone(tone)}" '
        f'data-emphasis="{_safe_card_emphasis(emphasis)}">'
        f"{label_html}"
        f'<div class="smai-card-value">{html.escape(compact_display_value(value))}</div>'
        f"{progress_bar}"
        f"{caption_html}"
        f"{badge_row}"
        "</div>"
    )


def render_metric_card(
    label: str,
    value: object,
    *,
    caption: str = "",
    help_text: str = "",
    badges: tuple[str, ...] = (),
    tone: str = "neutral",
    emphasis: str = "normal",
    progress: int | None = None,
) -> None:
    st.markdown(
        metric_card_html(
            label,
            value,
            caption=caption,
            help_text=help_text,
            badges=badges,
            tone=tone,
            emphasis=emphasis,
            progress=progress,
        ),
        unsafe_allow_html=True,
    )


def dashboard_header_html(
    title: str,
    subtitle: str = "",
    *,
    chips: Iterable[tuple[str, str]] = (),
) -> str:
    chip_html = "".join(
        '<span class="smai-dashboard-chip">'
        f'<span class="smai-chip-label">{html.escape(label)}</span>'
        f"<span>{html.escape(value)}</span>"
        "</span>"
        for label, value in chips
        if str(value or "").strip()
    )
    chip_row = f'<div class="smai-dashboard-chip-row">{chip_html}</div>' if chip_html else ""
    subtitle_html = (
        f'<p class="smai-dashboard-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    )
    return (
        '<section class="smai-dashboard-header">'
        f'<h2 class="smai-dashboard-title">{html.escape(title)}</h2>'
        f"{subtitle_html}"
        f"{chip_row}"
        "</section>"
    )


def render_dashboard_header(
    title: str,
    subtitle: str = "",
    *,
    chips: Iterable[tuple[str, str]] = (),
) -> None:
    st.markdown(
        dashboard_header_html(title, subtitle, chips=chips),
        unsafe_allow_html=True,
    )


def section_heading_html(title: str) -> str:
    return f'<div class="smai-section-title">{html.escape(title)}</div>'


def render_section_heading(title: str) -> None:
    st.markdown(section_heading_html(title), unsafe_allow_html=True)


def style_altair_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure(background=THEME_COLORS["bg_surface"])
        .configure_view(fill=THEME_COLORS["bg_card"], stroke=THEME_COLORS["border_default"])
        .configure_axis(
            domainColor=THEME_COLORS["border_strong"],
            gridColor=THEME_COLORS["chart_grid"],
            labelColor=THEME_COLORS["text_caption"],
            titleColor=THEME_COLORS["text_label"],
            tickColor=THEME_COLORS["border_strong"],
        )
        .configure_legend(
            labelColor=THEME_COLORS["text_secondary"],
            titleColor=THEME_COLORS["text_heading"],
        )
        .configure_title(
            color=THEME_COLORS["text_heading"],
            fontSize=13,
            anchor="start",
            offset=8,
        )
    )
