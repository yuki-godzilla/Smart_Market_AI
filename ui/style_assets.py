"""Ordered static CSS assets used by the Streamlit style loader."""

from __future__ import annotations

SMAI_RESEARCH_AI_CTA_CSS = """
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
"""

SMAI_BASE_TOKEN_CSS = """
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
</style>
"""
