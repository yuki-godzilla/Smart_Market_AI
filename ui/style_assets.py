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
