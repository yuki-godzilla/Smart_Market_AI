# PROJECT_CONTEXT.md

## Overview / ??

This file is the compact current-state summary for Smart Market AI.
??????? Smart Market AI ????????????????????

For historical work entries, see [Documents/99_Work_Log.md](Documents/99_Work_Log.md).
???????? [Documents/99_Work_Log.md](Documents/99_Work_Log.md) ???????

Last updated: 2026-05-17.
?????: 2026-05-16?

## Project Summary / ????????

Smart Market AI is a Python-based investment support project that combines market-data ingestion, feature generation, screening, forecasting, portfolio checks, planned Research RAG, and a Streamlit UI.
Smart Market AI ????????????????????????????????????????Streamlit UI ??????? Python ?????????????????

The current product direction is to help users compare symbols, inspect provider-backed data, review model signals, and make better-informed investment decisions without turning the app into an automated trading system.
??????????????????????????????provider ??????????????????????????????????????

Routine development should keep deterministic `mock` behavior available while allowing explicit opt-in use of live providers such as Yahoo/yfinance.
?????? deterministic ? `mock` ?????????Yahoo/yfinance ??? live provider ????? opt-in ????????

## Repository Layout / ???????

- `backend/app`: FastAPI entrypoints and application wiring / FastAPI ??????????????
- `backend/core`: shared contracts, settings, and domain errors / ???????????????
- `backend/marketdata`: market-data providers, feature snapshots, and provider registry / ???????? provider???? snapshot?provider registry
- `backend/risk`: pre-trade risk checks / ????????
- `backend/portfolio`: rebalance planning and portfolio-to-risk workflow / ???????? portfolio-to-risk workflow
- `backend/screening`: scoring for symbol screening / ????????????????
- `backend/forecast`: baseline forecast models and forecast evaluation / ????????????????
- `backend/scoring`: model-informed investment-support scoring / Investment Score ?????????
- `backend/research`: planned Research RAG for IR documents, evidence search, and Research Score / Research RAG ?????
- `ui`: Streamlit user interface / Streamlit UI
- `tests`: deterministic regression tests / ???????????
- `Documents`: human-facing design, roadmap, and operation documents / ??????????????????
- `Documents/98_Codex_Task_Template.md`: reusable task template for Codex work / Codex ?????????
- `Documents/99_Work_Log.md`: historical work log / ??????

## Current Implementation Status / ???????

Implemented or mostly implemented:
?????????????????:

- Core contracts, settings, and errors are available in `backend/core`.
  `backend/core` ? core ???????????????????
- MarketData supports deterministic `mock` and `csv` providers, plus an explicit Yahoo/yfinance adapter path.
  MarketData ? deterministic ? `mock` / `csv` provider ???????? Yahoo/yfinance adapter ????????
- Feature Store Lite builds reusable feature snapshots such as close, returns, momentum, volatility, drawdown, completeness, and missing summaries.
  Feature Store Lite ? close?return?momentum?volatility?drawdown?completeness?missing summary ?????? snapshot ???????
- Risk, portfolio rebalance, screening score, and forecast evaluation APIs are wired through FastAPI.
  risk?portfolio rebalance?screening score?forecast evaluation API ? FastAPI ?????????
- Streamlit UI exposes rebalance, market data, screening, and forecast-oriented workflows.
  Streamlit UI ?? rebalance?market data?screening?forecast ?? workflow ????????
- Reporting/export foundations exist for screening and forecast metrics.
  screening ? forecast metrics ??? reporting/export ??????
- Phase 15 is implementation-complete with a deterministic `backend/scoring` Investment Score contract/service, `POST /scoring/investment-score` API, configurable `scoring.weights`, screening risk-score integration, and Market Data tab preview/export without changing `ScreeningScore`.
  Phase 15 ? implementation complete: deterministic ? `backend/scoring` Investment Score contract/service ? `POST /scoring/investment-score` API ? configurable `scoring.weights` ? screening risk-score integration ? Market Data tab preview/export ??????`ScreeningScore` ??????????
- Phase 16 has started with a Streamlit Market Data mode split for `銘柄コックピット` / `銘柄ランキング`, a chart-first cockpit with Investment Score summary below it, score breakdown chart, and deterministic ranking MVP for selected symbols.
- Ranking results can now pass the selected symbol and provider into the single-symbol cockpit for deep-dive follow-up.
- Ranking supports deterministic preference presets for balance, forecast agreement, data quality, and lower-risk emphasis.
- Ranking candidate selection now has Fetch-before filters for period preset, market, asset type, currency, dividend category, minimum dividend yield, market-cap tier, ETF index family, max expense ratio, theme, keyword, and display count using static symbol metadata / curated tags.
- Ranking candidate filters now open in a modal, ranking rows show both ticker and company name, and current representative symbols have broader curated tags for market, asset type, theme, dividend category, and investing purpose.
- Ranking filter application resets the comparison selector per condition set and the filter modal shows candidate counts/examples with Japanese alias keyword matching for representative Japanese symbols. The former beginner-style investment-purpose control was replaced with database-style conditions such as dividend yield and ETF expense ratio.
- Rebalance Cockpit has started: JSON inputs are folded into advanced input, target allocations are percentage-formatted, allocation comparison has a chart, and risk breaches include beginner-friendly confirmation points.

Partial or intentionally deferred:
??????????????????:

- Live provider verification depends on local environment, installed packages, network availability, and cache/write settings.
  live provider ???????????????? package?network availability?cache/write ?????????
- Production-grade scoring, execution/order management, and automated trading are not current defaults.
  ???? scoring?execution/order management??????????????????????
- Research RAG, beginner-friendly symbol discovery, ranking UI, richer chart UX, and AI assistant features are roadmap items.
  ???????????????? UI?????????? UX?AI assistant ??????????????

## Likely Current Phase / ??????????

The completed roadmap through Phase 9 established the backend and portfolio/risk foundations.
Phase 9 ??? backend ? portfolio/risk ???????????

Phase 10 external data ingestion is functionally present with deterministic providers and an explicit Yahoo/yfinance path, but live verification can still be environment-dependent.
Phase 10 ????????? deterministic provider ? Yahoo/yfinance ????????????????live ?????????????

Phase 11 and Phase 12 introduced feature/screening-oriented workflows and UI visibility.
Phase 11 ? Phase 12 ?????????????? workflow ? UI ????????????

Phase 14 is implementation-complete: Forecast Summary, ensemble forecast, Model Registry Lite, and forecast-agreement signal are connected into Screening Score.
Phase 14 ?????????Forecast Summary?ensemble forecast?Model Registry Lite?forecast agreement ? Screening Score ?????????

Phase 15 is implementation-complete: Investment Score combines screening, forecast agreement, screening risk score, and data quality with configurable weights. Live-provider UI confirmation remains environment-dependent.
Phase 15 ? implementation complete: Investment Score ? screening / forecast agreement / screening risk score / data quality ? configurable weights ????????? live-provider UI confirmation ? environment-dependent.

Phase 16 has started: Market Data now separates single-symbol cockpit review from multi-symbol ranking, and the cockpit puts provider/as-of context and the forecast chart before the Investment Score, reasons, warnings, and score breakdown.
Ranking now has a basic deep-dive handoff into the cockpit by setting the selected symbol and provider.
Ranking preference presets now reweight existing Investment Score components without changing provider fetches.
Ranking candidate filters now separate Fetch-before static metadata conditions from Fetch-after scoring, forecast, data quality, and risk evaluation.
Dividend-style categories are currently curated metadata; a future symbol metadata refresh command should fetch provider fundamentals separately, produce a reviewable diff, and update the local DB only after confirmation.
Forecast chart now shows a beginner-friendly summary for model agreement, forecast spread, compared model count, and the best RMSE model before the chart.
Rebalance Cockpit has started with summary flow, percentage target weights, allocation comparison chart, and translated risk breach confirmation points.

## Next Good Targets / ??????

- Continue Phase 16 by polishing Rebalance Cockpit wording/layout and improving ranking-to-cockpit flow.
- Add a symbol metadata refresh path later for dividend yield, sector/theme, ETF/fund attributes, and metadata freshness tracking.
- Extend forecast reporting beyond metrics-only export when a richer saved report is needed.
  ????????????????????????? forecast reporting ???????
- Keep provider selection explicit and make fallback/error messages understandable in the UI.
  provider ??????????fallback/error message ? UI ????????????
- Prepare later UI Design work for symbol discovery, ranking, watchlists, and guided investment-support flows.
- Start Research RAG from `04-8_Onepager_Research_RAG.md`: local document ingestion -> chunk/search -> Research Summary -> optional Research Score integration.
  ??? UI Design ?????????????watchlist??????? flow ??????

## Known Documentation Mismatches / ???????????

- Some older documents may still describe earlier MVP assumptions that prioritized only local deterministic behavior.
  ??????????local deterministic behavior ??????????? MVP ?????????????????
- Current docs should treat live providers as explicit opt-in capabilities, not as the implicit default path.
  ????????live provider ?????????????????????????????
- If code and documents disagree, trust the code for current behavior and record the mismatch during the same work unit when practical.
  ????????????????????????????????????????????????

## Test And Verification Baseline / ?????????

Use the project virtual environment when available.
??????????????????????????

```powershell
.env_SMAI\Scripts\python.exe .	ools
un_local_checks.py
.env_SMAI\Scripts\python.exe -m pytest tests -q
.env_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.env_SMAI\Scripts\python.exe -m mypy backend
.env_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

For UI-affecting work, also confirm the relevant Streamlit screen manually and report what changed from a user's perspective.
UI ?????????????? Streamlit ??????????????????????????????

## Work Log Reference / ??????

Append new work-log entries to [Documents/99_Work_Log.md](Documents/99_Work_Log.md), not to this file.
?????????????????? [Documents/99_Work_Log.md](Documents/99_Work_Log.md) ???????

Update this file only when the current project state, likely phase, assumptions, verification baseline, or next good targets materially change.
?????????????????????????????????????????????????????
