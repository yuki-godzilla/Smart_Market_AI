from __future__ import annotations

import html
from decimal import Decimal, InvalidOperation
from typing import Iterable

import altair as alt
import streamlit as st

SMAI_GLOBAL_CSS = """
<style>
:root {
    --smai-bg: #0b1020;
    --smai-panel: #111827;
    --smai-card: #151b2e;
    --smai-card-soft: #1f2937;
    --smai-border: rgba(148, 163, 184, 0.18);
    --smai-border-strong: rgba(148, 163, 184, 0.28);
    --smai-text: #e5e7eb;
    --smai-muted: #9ca3af;
    --smai-accent: #38bdf8;
    --smai-accent-soft: rgba(56, 189, 248, 0.12);
    --smai-green: #22c55e;
    --smai-amber: #f59e0b;
    --smai-rose: #fb7185;
    --smai-blue: #60a5fa;
    --smai-teal: #2dd4bf;
    --smai-gray: #64748b;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(56, 189, 248, 0.08), transparent 30rem),
        linear-gradient(180deg, #0b1020 0%, #111827 100%);
    color: var(--smai-text);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1020 0%, #111827 100%);
    border-right: 1px solid var(--smai-border);
}

[data-testid="stAppViewContainer"] .main .block-container {
    padding-top: 3.1rem;
}

[data-testid="stButton"] button {
    min-height: 2.35rem;
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.26);
    background: rgba(17, 24, 39, 0.88);
    color: #e5edf7;
    transition:
        border-color 120ms ease,
        background 120ms ease,
        box-shadow 120ms ease,
        transform 120ms ease;
}

[data-testid="stButton"] button:hover {
    border-color: rgba(45, 212, 191, 0.48);
    background: rgba(20, 184, 166, 0.12);
    box-shadow: 0 0 0 1px rgba(45, 212, 191, 0.12);
}

[data-testid="stButton"] button[kind="primary"] {
    border-color: rgba(45, 212, 191, 0.7);
    background:
        linear-gradient(135deg, rgba(14, 165, 233, 0.95), rgba(20, 184, 166, 0.92));
    color: #07111f;
    font-weight: 760;
}

[data-testid="stButton"] button[kind="primary"]:hover {
    background:
        linear-gradient(135deg, rgba(56, 189, 248, 1), rgba(45, 212, 191, 0.98));
    box-shadow: 0 10px 28px rgba(20, 184, 166, 0.18);
}

[data-baseweb="select"] > div,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input {
    border-color: rgba(148, 163, 184, 0.22);
    background-color: rgba(17, 24, 39, 0.82);
}

[data-baseweb="select"] > div:hover,
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stDateInput"] input:focus {
    border-color: rgba(56, 189, 248, 0.55);
    box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.16);
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
    background: linear-gradient(180deg, rgba(31, 41, 55, 0.88), rgba(17, 24, 39, 0.86));
}

[data-testid="stMetricLabel"] {
    color: var(--smai-muted);
}

[data-testid="stMetricValue"] {
    color: var(--smai-text);
    letter-spacing: 0;
}

[data-testid="stExpander"] {
    border-color: var(--smai-border);
    background: rgba(17, 24, 39, 0.42);
}

.smai-app-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 1.2rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.2);
    padding: 0.1rem 0 1.05rem;
    margin: 0 0 1rem;
}

.smai-app-title {
    color: #f8fafc;
    font-size: clamp(2rem, 3vw, 3rem);
    line-height: 1.12;
    font-weight: 860;
    letter-spacing: 0;
    margin: 0;
}

.smai-app-message {
    color: #b7c3d4;
    font-size: 0.92rem;
    line-height: 1.55;
    margin: 0.45rem 0 0;
}

.smai-app-mascot-wrap {
    position: relative;
    width: clamp(4.5rem, 8vw, 6.8rem);
    aspect-ratio: 1;
    display: grid;
    place-items: center;
    border: 1px solid rgba(56, 189, 248, 0.22);
    border-radius: 8px;
    background:
        linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(45, 212, 191, 0.07)),
        rgba(8, 13, 24, 0.28);
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
    border-bottom: 1px solid rgba(148, 163, 184, 0.16);
    padding: 0.05rem 0 0.9rem;
    margin: 0 0 1rem;
}

.smai-page-title--copilot {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(15rem, 20rem);
    align-items: center;
    gap: 1rem;
    padding-bottom: 1rem;
}

.smai-page-title-row {
    display: inline-flex;
    align-items: center;
    gap: 0.8rem;
    max-width: 100%;
    vertical-align: middle;
}

.smai-page-title-heading {
    color: #f8fafc;
    font-size: clamp(1.7rem, 2.3vw, 2.25rem);
    line-height: 1.16;
    font-weight: 840;
    letter-spacing: 0;
    margin: 0;
}

.smai-page-title-subtitle {
    color: #aeb9ca;
    font-size: 0.92rem;
    line-height: 1.55;
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
        linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(8, 13, 24, 0.96)),
        rgba(7, 11, 20, 0.82);
    box-shadow:
        0 10px 30px rgba(0, 0, 0, 0.28),
        0 0 24px rgba(34, 211, 238, 0.08);
    backdrop-filter: blur(8px);
    padding: 0.72rem 0.82rem;
}

.smai-copilot-panel::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
        radial-gradient(circle at 20% 30%, rgba(34, 211, 238, 0.16), transparent 34%),
        linear-gradient(90deg, rgba(34, 211, 238, 0.08), transparent 64%);
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
    border-radius: 999px;
    background: rgba(34, 211, 238, 0.11);
    filter: blur(12px);
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
    color: #e5e7eb;
    font-size: 0.9rem;
    font-weight: 820;
    line-height: 1.25;
}

.smai-copilot-status {
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    margin-top: 0.34rem;
    color: #94a3b8;
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1.35;
}

.smai-copilot-status-dot {
    width: 0.46rem;
    height: 0.46rem;
    border-radius: 999px;
    background: #34d399;
    box-shadow: 0 0 12px rgba(52, 211, 153, 0.42);
    animation: smai-status-breathe 3.8s ease-in-out infinite;
}

.smai-copilot-message {
    color: #94a3b8;
    font-size: 0.78rem;
    line-height: 1.5;
    margin: 0.48rem 0 0;
}

.smai-dashboard-header {
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(56, 189, 248, 0.24);
    border-radius: 8px;
    background:
        linear-gradient(90deg, rgba(45, 212, 191, 0.13), transparent 42%),
        linear-gradient(135deg, rgba(251, 113, 133, 0.08), transparent 56%),
        linear-gradient(135deg, rgba(17, 24, 39, 0.98), rgba(13, 24, 38, 0.96));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.05),
        0 18px 52px rgba(0, 0, 0, 0.22);
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
    color: #f8fafc;
    font-size: clamp(1.25rem, 1.5vw, 1.75rem);
    font-weight: 820;
    line-height: 1.2;
    margin: 0;
}

.smai-dashboard-subtitle {
    color: #b7c3d4;
    font-size: 0.92rem;
    line-height: 1.55;
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
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 999px;
    background: rgba(8, 13, 24, 0.55);
    color: #e2e8f0;
    font-size: 0.78rem;
    font-weight: 680;
    line-height: 1.35;
    padding: 0.28rem 0.62rem;
}

.smai-dashboard-chip .smai-chip-label {
    color: #8ea2ba;
    font-weight: 640;
}

.smai-section-title {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    color: #f8fafc;
    font-size: 1.05rem;
    font-weight: 760;
    line-height: 1.35;
    margin: 1rem 0 0.25rem;
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
        linear-gradient(135deg, rgba(17, 24, 39, 0.94), rgba(12, 18, 30, 0.92));
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
        linear-gradient(90deg, rgba(34, 211, 238, 0.1), transparent 56%),
        rgba(15, 23, 42, 0.72);
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
    border-radius: 999px;
    background: rgba(34, 211, 238, 0.1);
    filter: blur(9px);
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
    color: #e5e7eb;
    font-size: 0.86rem;
    font-weight: 780;
    line-height: 1.3;
}

.smai-insight-message {
    color: #b7c3d4;
    font-size: 0.82rem;
    line-height: 1.55;
    margin-top: 0.22rem;
}

.smai-mascot-title {
    color: #f8fafc;
    font-size: 0.94rem;
    font-weight: 780;
    line-height: 1.35;
}

.smai-mascot-message {
    color: #b7c3d4;
    font-size: 0.84rem;
    line-height: 1.55;
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
    font-size: 0.74rem;
    line-height: 1.45;
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
    background: linear-gradient(180deg, rgba(31, 41, 55, 0.72), rgba(17, 24, 39, 0.72));
    padding: 0.95rem 1rem;
    margin: 0.35rem 0 0.7rem 0;
}

.smai-metric-card {
    --smai-card-accent: var(--smai-gray);
    --smai-card-glow: rgba(100, 116, 139, 0.12);
    --smai-card-value: #f8fafc;
    position: relative;
    overflow: hidden;
    min-height: 9.2rem;
    border: 1px solid var(--smai-border);
    border-left: 3px solid var(--smai-card-accent);
    border-radius: 8px;
    background:
        linear-gradient(90deg, var(--smai-card-glow), transparent 58%),
        linear-gradient(180deg, rgba(31, 41, 55, 0.92), rgba(14, 21, 34, 0.9));
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.04),
        0 12px 26px rgba(0, 0, 0, 0.16);
    padding: 0.88rem 0.95rem;
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
    color: var(--smai-muted);
    font-size: 0.78rem;
    line-height: 1.3;
    margin-bottom: 0.35rem;
}

.smai-card-value {
    color: var(--smai-card-value);
    font-size: 1.28rem;
    line-height: 1.25;
    font-weight: 760;
    overflow-wrap: anywhere;
}

.smai-card-caption {
    color: var(--smai-muted);
    font-size: 0.82rem;
    line-height: 1.45;
    margin-top: 0.5rem;
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
    color: #bae6fd;
    background: rgba(56, 189, 248, 0.15);
    border-color: rgba(56, 189, 248, 0.28);
}

.smai-badge.success {
    color: #bbf7d0;
    background: rgba(34, 197, 94, 0.15);
    border-color: rgba(34, 197, 94, 0.28);
}

.smai-badge.caution {
    color: #fde68a;
    background: rgba(245, 158, 11, 0.16);
    border-color: rgba(245, 158, 11, 0.3);
}

.smai-badge.danger {
    color: #fecdd3;
    background: rgba(251, 113, 133, 0.15);
    border-color: rgba(251, 113, 133, 0.28);
}

.smai-badge.neutral {
    color: #cbd5e1;
    background: rgba(100, 116, 139, 0.14);
    border-color: rgba(148, 163, 184, 0.18);
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
    return (
        '<div class="smai-metric-card" '
        f'data-tone="{_safe_card_tone(tone)}" '
        f'data-emphasis="{_safe_card_emphasis(emphasis)}">'
        f'<div class="smai-card-label">{html.escape(label)}</div>'
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
        chart.configure(background="#0b1020")
        .configure_view(fill="#111827", stroke="rgba(148, 163, 184, 0.22)")
        .configure_axis(
            domainColor="rgba(148, 163, 184, 0.38)",
            gridColor="rgba(148, 163, 184, 0.12)",
            labelColor="#cbd5e1",
            titleColor="#e5e7eb",
            tickColor="rgba(148, 163, 184, 0.38)",
        )
        .configure_legend(labelColor="#cbd5e1", titleColor="#e5e7eb")
        .configure_title(color="#e5e7eb", fontSize=13, anchor="start", offset=8)
    )
