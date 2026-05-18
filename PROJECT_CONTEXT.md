# PROJECT_CONTEXT.md

## Overview

This file is the compact current-state summary for Smart Market AI.
Historical work entries belong in [Documents/99_Work_Log.md](Documents/99_Work_Log.md).

Last updated: 2026-05-18

## Project Summary

Smart Market AI is a Python-based investment support project that combines market-data ingestion, feature generation, screening, deterministic baseline forecasting, model-informed Investment Score, portfolio/risk checks, Streamlit UI, and planned Research RAG.

The product direction is to help users compare symbols, inspect provider-backed data, review model signals, understand warnings, and make better-informed investment decisions without turning the app into automated trading.

Routine development must keep deterministic `mock` / `csv` behavior available while allowing explicit opt-in use of live providers such as Yahoo/yfinance.
The configured default provider remains `mock` for local checks and APIs; the Streamlit Market Data provider selector is live-first with `yahoo` as the first/default option and explicit per-fetch opt-in.

## Repository Layout

- `backend/app`: FastAPI entrypoints and application wiring
- `backend/core`: shared contracts, settings, and domain errors
- `backend/marketdata`: providers, provider registry/factory, live adapter metadata, feature snapshots
- `backend/forecast`: baseline models, model registry lite, evaluation, forecast consensus
- `backend/screening`: explainable symbol screening score
- `backend/scoring`: Investment Score contract/service
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
- Streamlit left side menu for `銘柄コックピット`, `銘柄ランキング`, `リバランス`, and `設定 / データ情報`.
- Streamlit Market Data provider selector defaults to `yahoo` and shows it first; large live ranking requests warn users instead of hard-blocking them.
- Ranking candidate filters using static/curated metadata before provider fetch.
- Symbol universe source import for local curated / JPX seed expansion; current candidate master carries SBI policy columns but is not yet an SBI-verified tradable universe. SBI acquisition policy is local-master first, not direct site scraping.
- Ranking condition classification first slice: region, product type, ranking purpose, and dynamic detail filters are wired into the Streamlit ranking UI.
- Ranking presets for balanced, forecast-agreement, data-quality, and lower-risk emphasis.
- Ranking-to-cockpit handoff for follow-up single-symbol review.
- Rebalance Cockpit page with in-page sample/account inputs, percentage target input, allocation comparison chart, result persistence, and beginner-friendly risk breach confirmation points.
- JSON / CSV / Markdown / manifest / ZIP exports for implemented workflows.
- `tools/run_black_check.py` as the routine Black check path for the Windows environment.

Partial or intentionally deferred:

- Live provider verification depends on local package, network, and cache/write conditions.
- `polygon` is reserved in provider metadata but adapter implementation is not complete.
- Symbol metadata refresh has a provider-neutral command and an opt-in Yahoo adapter; ranking filters still rely on local symbol-universe metadata before provider fetch.
- SBI Securities ranking-universe policy columns and default exclusion helper are wired into ranking candidate extraction. `tradability=unknown` is allowed for current seed rows; explicit out-of-scope products, not-tradable rows, inactive rows, non-SBI rows, leveraged rows, and inverse rows are excluded.
- Research RAG is designed but not implemented.
- Decision Report is not yet the main report workflow.
- Execution / broker order submission is intentionally out of the current default path.
- PDF / Excel export is future scope.

## Likely Current Phase

- Phase 1〜9: MVP foundation complete.
- Phase 10: External data ingestion path is functionally present; live smoke remains environment-dependent.
- Phase 11〜12: Feature snapshots and Screening Score are implemented.
- Phase 13〜14: Forecast Lab / Multi-Model Forecasting are implementation-complete with deterministic baseline models and consensus.
- Phase 15: Model-Informed Scoring is implementation-complete with `backend/scoring`, API, UI preview/export, and configurable weights.
- Phase 16: Visualization Cockpit / UI improvement is implementation-complete; final cross-flow Streamlit browser smoke remains useful before larger backend work.
- Phase 16S: Stabilization smoke has been partially covered through ranking-condition visual checks; broader cockpit/ranking/rebalance smoke remains optional before handoff.
- Phase 17: UI Polish and ranking-condition redesign is implementation-complete with user visual confirmation.
- Phase 18: Symbol universe metadata refresh is in progress. The network-free slices define CSV schema / enum / decimal / duplicate ticker validation, metadata tier/storage/freshness policy, metadata source/as-of/update timestamps in `symbol_universe.csv`, compact metadata status in Settings, a provider-neutral dry-run/manifest refresh command, a local source-import command with JPX code normalization, and SBI ranking-universe policy columns/default exclusion. Yahoo metadata refresh is implemented behind `--provider yahoo --allow-live`; normal checks remain network-free. Ranking UI can filter mutual-fund seed rows by management style, trust fee, NISA eligibility, and installment availability, while guarding mutual-fund placeholders from price-provider ranking fetch.
- Phase 19〜24: Decision Report, Research RAG, Research Score, assistant, optional adapters, and execution gate are ordered in the implementation roadmap.

## Next Good Targets

- Continue Phase 18 by expanding official/curated source ingestion with broader JPX coverage, FSA/IMAJ fund metadata, and NISA lists. The current candidate master has 146 rows after SBI US stock/ETF and mutual-fund seed import.
- Keep a final cross-flow Streamlit smoke available before handoff when browser access is useful: ranking cache/progress, purpose-based resort, ranking-to-cockpit, and Rebalance wording.
- Prepare Phase 19 Decision Report context so cockpit / ranking / rebalance outputs can be saved consistently.
- Start Phase 20 Research RAG from local document ingestion, chunk/search, and deterministic Research Summary before optional vector/LLM adapters.
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
