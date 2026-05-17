# PROJECT_CONTEXT.md

## Overview

This file is the compact current-state summary for Smart Market AI.
Historical work entries belong in [Documents/99_Work_Log.md](Documents/99_Work_Log.md).

Last updated: 2026-05-17

## Project Summary

Smart Market AI is a Python-based investment support project that combines market-data ingestion, feature generation, screening, deterministic baseline forecasting, model-informed Investment Score, portfolio/risk checks, Streamlit UI, and planned Research RAG.

The product direction is to help users compare symbols, inspect provider-backed data, review model signals, understand warnings, and make better-informed investment decisions without turning the app into automated trading.

Routine development must keep deterministic `mock` / `csv` behavior available while allowing explicit opt-in use of live providers such as Yahoo/yfinance.

## Repository Layout

- `backend/app`: FastAPI entrypoints and application wiring
- `backend/core`: shared contracts, settings, and domain errors
- `backend/marketdata`: providers, provider registry/factory, live adapter metadata, feature snapshots
- `backend/forecast`: baseline models, model registry lite, evaluation, forecast consensus
- `backend/screening`: explainable symbol screening score
- `backend/scoring`: Investment Score contract/service
- `backend/reporting`: Decision Report context contracts and deterministic Markdown/manifest helpers
- `backend/risk`: deterministic pre-trade risk checks
- `backend/portfolio`: portfolio valuation, no-solver rebalance proposal, portfolio-to-risk workflow
- `ui`: Streamlit UI for Market Data / Rebalance workflows
- `tests`: deterministic regression tests
- `Documents`: requirements, design, roadmap, operation, UI, and work-log documents

## Current Implementation Status

Implemented or mostly implemented:

- Core contracts, settings, YAML loading, and domain errors.
- Deterministic `mock` / `csv` MarketData providers.
- Explicit opt-in `yahoo` live provider adapter path via `yfinance`.
- Provider registry / factory and error mapping for unavailable, timeout, rate-limit, and schema mismatch cases.
- Feature Store Lite style snapshots with last/close, returns, momentum, ADV, volatility, drawdown, missing summary, data quality, and completeness.
- FastAPI endpoints:
  - `GET /health`
  - `POST /risk/pre-trade-check`
  - `POST /portfolio/rebalance-check`
  - `POST /screening/score`
  - `POST /forecast/evaluate`
  - `POST /scoring/investment-score`
- Forecast baseline models: naive, moving average, momentum.
- Forecast consensus / model agreement / forecast range / best RMSE model support.
- Screening Score with reason labels and forecast agreement integration.
- Investment Score as a separate contract that combines screening, forecast agreement, data quality, and risk signal with configurable weights.
- Streamlit Market Data tab split into `銘柄コックピット` and `銘柄ランキング`.
- Ranking candidate filters using static/curated metadata before provider fetch.
- Ranking presets for balanced, forecast-agreement, data-quality, and lower-risk emphasis.
- Ranking-to-cockpit handoff for follow-up single-symbol review.
- Rebalance Cockpit summary flow, percentage target input, allocation comparison chart, and beginner-friendly risk breach confirmation points.
- JSON / CSV / Markdown / manifest / ZIP exports for implemented workflows.
- Decision Report context v1 in `backend/reporting` for reusing cockpit / ranking / rebalance outputs in local reports.
- `tools/run_black_check.py` as the routine Black check path for the Windows environment.

Partial or intentionally deferred:

- Live provider verification depends on local package, network, and cache/write conditions.
- `polygon` is reserved in provider metadata but adapter implementation is not complete.
- Symbol metadata refresh from provider fundamentals is not implemented; current ranking filters rely on curated/static metadata.
- Research RAG is designed but not implemented.
- Decision Report has a first backend context/rendering slice, but is not yet wired into API/UI exports.
- Execution / broker order submission is intentionally out of the current default path.
- PDF / Excel export is future scope.

## Likely Current Phase

- Phase 1〜9: MVP foundation complete.
- Phase 10: External data ingestion path is functionally present; live smoke remains environment-dependent.
- Phase 11〜12: Feature snapshots and Screening Score are implemented.
- Phase 13〜14: Forecast Lab / Multi-Model Forecasting are implementation-complete with deterministic baseline models and consensus.
- Phase 15: Model-Informed Scoring is implementation-complete with `backend/scoring`, API, UI preview/export, and configurable weights.
- Phase 16: Visualization Cockpit / UI improvement is implementation-complete; final Streamlit browser smoke is still recommended.
- Phase 18: Decision Report is in progress with an initial local-first context contract and deterministic Markdown/manifest helper.
- Research RAG roadmap: designed and planned, not implemented.

## Next Good Targets

- Wire Decision Report context into cockpit / ranking / rebalance UI/API exports.
- Add a symbol metadata refresh path for dividend yield, sector/theme, ETF/fund attributes, and metadata freshness tracking.
- Start Research RAG from local document ingestion, chunk/search, and deterministic Research Summary before optional vector/LLM adapters.
- Run a final Streamlit Phase 16 smoke when browser access is available: ranking conditions, ranking cache/progress, weight-preset resort, ranking-to-cockpit, and Rebalance wording.
- Keep provider selection explicit and error messages understandable in UI.

## Known Documentation Rules

- Treat code and tests as the source of truth for current behavior.
- Keep `PROJECT_CONTEXT.md` compact; put chronological detail in `Documents/99_Work_Log.md`.
- When implementation changes, update README, roadmap, operation guide, and affected design documents in the same work unit when practical.

## Test And Verification Baseline

Use the project virtual environment when available.

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy backend
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
.\venv_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

For UI-affecting work, also confirm the relevant Streamlit screen manually and report what changed from a user's perspective.
