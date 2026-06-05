# 99_Work_Log

#### [BACK TO README](../README.md)

## Purpose / 目的

This file stores historical work-log entries for Smart Market AI.
このファイルは Smart Market AI の履歴作業ログを保存します。

`PROJECT_CONTEXT.md` should stay compact and focused on the current project state.
`PROJECT_CONTEXT.md` はコンパクトな現在地サマリに保ちます。

Read this file only when historical investigation is needed.
履歴調査が必要な場合だけ読みます。

When adding a new work-log entry, append it to the top of the Work Log section.
新しい作業ログは Work Log セクションの先頭に追加します。

## Work Log / 作業ログ

- 2026-06-05: Cleaned local ignored temporary artifacts after verification work, including pytest tmp, mypy / ruff / black caches, coverage files, Python `__pycache__` directories, build / dist outputs, VSCodeCounter output, and a symbol metadata probe work directory. `.pytest_cache` remained as an ACL-denied local directory and is not tracked.
- 2026-06-05: Connected the Symbol DB background refresh cache to visible Cockpit / Ranking UI. `symbol_universe_runtime_rows()` now carries saved `SymbolRecord` provider, update timestamps, and freshness; Cockpit shows a compact selected-symbol `銘柄DB` status line, and the shared `銘柄データ` modal shows freshness, source, price/fundamental update times, and missing key fields in `データ情報`.
- 2026-06-05: Restored the animated Investment Radar market headline strip while keeping the anti-clipping layout. Headlines now scroll again as two-line pills, duplicate items are hidden from assistive tech with `aria-hidden`, and reduced-motion users still get a wrapped static layout.
- 2026-06-05: Adjusted Investment Radar news layout after longer wording caused visible clipping. The market headline strip now uses wrappable headline pills instead of a single scrolling line, and compact news cards no longer use a fixed height; title / summary / comment text is line-clamped within a taller auto-height card so symbol handoff controls stay below readable card content.
- 2026-06-05: Switched Investment Radar news time labels from UTC to JST after the compact freshness badge made fresh morning updates look like the previous day. Added a date-rollover regression test for `2026-06-04 23:13 UTC` displaying as `2026-06-05 08:13 JST`.
- 2026-06-05: Added acquisition time back into the Investment Radar title-right freshness badge. The compact header still avoids the old status-card block, but now shows `情報鮮度` plus `取得 ... UTC` so users can see when the dashboard data was fetched.
- 2026-06-05: Rebalanced Investment Radar related-symbol extraction/display. Google News cards now keep text-mentioned symbols up to 8 direct display slots, fill remaining space with `SMAI推測候補`, use local Japanese symbol-universe aliases plus selected short-name patterns for direct extraction, and avoid short-katakana substring false positives such as splitting unknown compound names. Verified deterministic extraction/UI tests and ran a live 300-news / 30-item-batch RSS validation; direct extraction improved from 128/300 to 160/300 while every card retained either direct symbols or inferred candidates.
- 2026-06-05: Simplified the Investment Radar header status UI per visual feedback. The large `ニュース表示の状態` panel was removed from the normal top area, and only a subtle title-right `情報鮮度` badge remains visible; cache-size/update-state details stay out of the initial screen while refresh warnings still surface when needed. Updated Streamlit/UI helper tests and synchronized roadmap, operations guide, and project context wording.
- 2026-06-04: Fixed Investment Radar heatmap tile navigation so symbol clicks stay in the same Streamlit app session. Heatmap tiles now target the current window with the existing `smai_page=cockpit` / `smai_symbol` handoff, letting `_apply_navigation_query_params` switch to `銘柄コックピット` and select the clicked symbol instead of behaving like a separate web-page link.
- 2026-06-04: Slightly increased Investment Radar heatmap typography after live review showed tile text was still hard to read. Sector headers, primary tile names, symbol badges, movement labels, and compact tail-tile names now use a modestly larger scale without changing tile counts, sector sizing, or Cockpit navigation.
- 2026-06-04: Refined the Investment Radar heatmap layout after the 96-tile universe expansion made dense sectors hard to read. Sector blocks now use a taller three-column layout, top / major / medium tiles allow two-line names, tail tiles shorten long names and hide secondary badge/change text to avoid cramped multi-line overlap, while preserving the 8-sector / 96-tile breadth and same-app Symbol Cockpit links.
- 2026-06-04: Upgraded the Investment Radar heatmap from related-symbol-only tiles to a broader local symbol-universe scoring surface. The top status-card row was removed, the heatmap now communicates density in its own top-line (`8セクター / 96銘柄タイル` in the demo snapshot), and each sector blends direct news symbols with `symbol_universe.csv` candidates scored by category profile, market-cap tier, data quality, news freshness/material, and market signal. Demo / Standard Mode related-symbol fallbacks were widened, while news fetch limits, Investment Score, Research Score, and ranking behavior remain unchanged.
- 2026-06-04: Clarified the Investment Radar news-count status card after sample data made `8件` look unexpectedly small. The card now reads `表示中ニュース`, and sample mode uses `サンプル見出し数` while saved data keeps `重複を除いた見出し数`, making it clear that the 8-item state is the built-in demo snapshot before manual Standard Mode refresh.
- 2026-06-04: Renamed the Investment Radar status card from the ambiguous `表示元` / `デモ` wording to user-facing `データ状態` with `サンプル表示` or `保存データ`. The sample-state caption now explains that it is example data before manual refresh, reducing confusion without changing news fetch, cache, scoring, or ranking behavior.
- 2026-06-04: Ran five Investment Radar UI/UX review loops against the launched Streamlit app on port 8505. Refined heatmap top-line context with sector/tile counts and a compact Cockpit-link status chip, reduced compact news-card height by showing one key checkpoint in list cards, added short display names for major heatmap symbols, improved narrow-screen heatmap tile layout, and expanded category lanes from six to up to nine visible categories. In-app Browser automation was unavailable in this session, so validation used the live Streamlit HTTP endpoint, Streamlit AppTest, HTML/CSS helper checks, targeted tests, ruff, mypy, and Black helper.
- 2026-06-04: Added the first Investment Radar Standard Mode sourcing layer. Manual `ニュース表示を更新` now uses a bounded Google News RSS dashboard adapter across 12 market categories, targets roughly 150-250 raw candidates, dedupes URL/title matches, saves up to 100 normalized `NewsHeadlineCard` items, and keeps UI initial rendering compact. Network-free defaults remain through demo snapshots, Static adapter tests, and RSS fixtures; failures fall back to existing cache/demo and do not affect Investment Score, Research Score, or Ranking order.
- 2026-06-04: Polished Investment Radar heatmap readability and handoff. Stock heatmap tiles now prioritize company / security names over symbols, render symbols as compact supporting tags, use a less flat teal / slate / rose finance palette with stronger text hierarchy, and link each symbol tile to the same-app Symbol Cockpit via query-parameter handoff. Updated roadmap, operations, UI wording policy, README, and project context; verified with targeted unit tests, Streamlit AppTest, live validation server HTTP checks on port 8504, ruff, Black helper, and UTF-8 / diff checks.
- 2026-06-04: Further polished the Investment Radar stock heatmap after UI feedback. Heatmap tiles now consistently expose `symbol / company name` in the visible tile and hover title, use clearer text hierarchy for symbol / name / movement, add density-specific layouts for low-symbol categories, and include a compact legend explaining the tile reading order and red / gray / green material colors. Verified with five local review loops using the validation Streamlit app, AppTest, targeted helper checks, ruff, and Black helper.
- 2026-06-04: Reworked the Investment Radar heatmap from an Altair matrix into a stock-heatmap-style HTML/CSS surface. Investment categories now render as sector blocks and related symbols as sized tiles with red / gray / green movement or material-signal colors, while retaining `ニュース代理` labels when market metrics are inferred. Added tests for the stock heatmap HTML and verified the Streamlit validation app returned HTTP 200.
- 2026-06-04: Polished the Investment Radar UI after live Streamlit review. The investment heatmap now falls back to clearly labeled `ニュース代理` material signals when market price / volume metrics are missing, preventing all-`未取得` tiles in old-cache or unknown-category cases. Category lanes now render as bounded three-column news cards with lane-specific vertical related-symbol buttons for readable company-name handoff, and investment news cards gained tone-specific accents for news / positive / important / risk materials. Verified with targeted Streamlit AppTest, HTTP 200 on the validation app, ruff, and Black helper.
- 2026-06-03: Refined the `Market Intelligence` visual treatment into a restrained neon finance-dashboard style while keeping URL navigation intact. News cards now use type-linked radial / linear gradients, borders, badges, and hover glow: cyan for ordinary news, violet for IR / disclosure, amber-gold for priority materials / Top 3, soft red for risk materials, and blue-gray for other items. No news fetching, RAG, source generation, storage, API response, Research Score, Investment Score, or ranking behavior was changed.
- 2026-06-03: Refined the `Market Intelligence` news layout without changing external source fetching. `最新ニュース・開示サマリー` and `ニュース・開示の出典` now render as responsive news-report rows with 2-column desktop layout, first-item featured emphasis, max-width text blocks, stronger type-specific backgrounds, source/date/action areas on the right, and clearer hover / focus affordance. `注目材料 Top 3` now uses stronger top-material cards with a right-side `元記事を見る` action. Existing URL hrefs, `target="_blank"`, `rel="noopener noreferrer"`, source/provider/source_type data, RAG behavior, storage behavior, Research Score, Investment Score, and ranking order were unchanged.
- 2026-06-03: Polished Cockpit Research Summary news / disclosure display as a `Market Intelligence` UI slice. `最新ニュース・開示サマリー`, `投資ヒントとなるニュース` / `注目材料 Top 3`, and `ニュース・開示の出典` now use dedicated news-feed cards with source-type accents, hover / focus-visible affordance, full-card external links, and source-specific labels such as `元記事を見る`, `TDnetで見る`, `企業IRで見る`, `EDINETで見る`, and `Yahoo Financeで見る`. Existing URL hrefs, `target="_blank"`, `rel="noopener noreferrer"`, source/provider data structures, fetch logic, storage behavior, Research Score, Investment Score, and ranking order were unchanged.
- 2026-06-02: Polished the Cockpit news UI after live-screen feedback. `投資ヒントとなるニュース` now uses a separate lightweight headline-card style from IR / disclosure evidence cards, prioritizing title, published date, freshness, source, viewpoint / sentiment, and short summary. The entire card opens the external news URL, while raw URL text and long why-to-check / next-check explanations are removed from the normal card. `最新ニュース・開示サマリー` cards are also compact clickable summary cards when a source URL exists.
- 2026-06-02: Added a Google News RSS headline adapter to the default `AI調査を更新` external-source set. The adapter builds investment-context search queries from company name / related keywords / symbol, parses URL-backed RSS headlines into `source_type=news` payloads, and feeds the existing `StockNewsEvidence` normalization / `投資ヒントとなるニュース` cards without changing Research Score, Investment Score, ranking order, source retention, or normal network-free checks.
- 2026-06-02: Added the first Cockpit `投資ヒントとなるニュース` Research Summary UI slice. URL-backed `StockNewsEvidence` general news now appears as dedicated cards with sentiment, viewpoint, freshness, summary, why-to-check, next-check, and `ニュースを開く` links, while TDnet / company IR / EDINET / provider profile and URL-missing items stay in the source-link / external-source / detail layers. News provider breadth, Research Score, Investment Score, ranking order, and source retention behavior were unchanged.
- 2026-06-02: Adjusted the Research Summary source-link panel after user screenshot feedback showed URL links still looked hidden. `ニュース・開示の出典を表示（URL付きN件）` now starts expanded when URL-backed sources exist, so clickable `ニュースを開く` / `開示資料を開く` / `出典を開く` links are visible immediately below `最新ニュース・開示サマリー`; zero-URL cases remain folded.
- 2026-06-02: Followed up on Research Summary URL / scale wording after Sony screen review. Company overview scale text now reuses context-backed quantitative extraction so truncated provider metrics such as `時価総額 21です` become unit-bearing values such as `時価総額 21.58兆円`; `ニュース・開示の出典` now shows `URL付きN件` and the URL-gap message points to nearby official / IR / provider source links when available; Research Yahoo Finance / company IR adapters now share the MarketData yfinance cache/session setup, and a live Sony external fetch returned the Yahoo Finance profile URL with network access allowed.
- 2026-06-02: Implemented Phase 22 News Source URL UX polish for Cockpit Research Summary. `最新ニュース・開示サマリー` now has a nearby folded `ニュース・開示の出典を表示` panel that lists up to five URL-backed news / TDnet / company IR / EDINET / Yahoo Finance sources with natural labels and link actions, while keeping the existing external-source full list and detail rows intact. Updated the news URL gap fallback wording so it no longer looks like URL display is unimplemented, and kept news fetch logic, external source normalization, Research Score, ranking order, score calculation, source retention, and archive UI unchanged.
- 2026-06-02: Completed the Phase 22 Research Score UX regression sprint for Cockpit / Ranking context wording. Random-seed `20260602` selected 24 symbols across domestic large/mid-small stocks, US large/mid-small stocks, domestic ETFs, overseas ETFs, and insufficient-source cases, with Osaka Gas (`9532.T`) included. Confirmed Cockpit shows `Research Score（根拠資料の確認材料）を表示`, Ranking AI Research lookup shows `Research Score（参考情報）を表示`, old `Ranking順位` wording is absent, Research Score explanation stays folded with reading / summary / component / warning rows, detail data does not duplicate Research Score component / warning headings, and ranking / scoring / ResearchScore calculation logic was not changed.
- 2026-06-02: Fixed the full `mypy .` check after the pre-release `dist/` tree caused duplicate `backend` module discovery. Added a mypy exclude for generated build/cache directories (`build`, `dist`, `venv_*`, `.mypy_cache`, `.pytest_cache`) in `pyproject.toml`; `mypy .` now reports no issues.
- 2026-06-02: Implemented the first Phase 22 Cockpit ResearchScore UX polish slice. Cockpit Research Summary now groups Research Score reading guidance, summary, component breakdown, and warnings inside the Research Score expander, keeps the default ranking order unchanged, and removes duplicate score component/warning tables from the technical detail expander. Updated UI wording policy, roadmap/context, UX checklist, and FS-013 notes; real-screen regression is intentionally left for the next sprint.
- 2026-06-02: Synced roadmap/current-state docs after deciding not to integrate ResearchScore into Ranking order for now. Phase 22 is reframed around Cockpit deep-dive ResearchScore confirmation and Cockpit Decision Report display, with Ranking kept as the comparison entry point. Also translated the most visible roadmap status/scope/completion labels and current Phase 22 wording to Japanese-first documentation.
- 2026-06-02: Ran the Phase 21.6 / 21.7 Cockpit Research Summary real-screen regression across domestic stock, foreign stock, domestic / foreign ETF, and limited-source cases (`7203.T`, `9532.T`, `4493.T`, `AAPL`, `SPY`, `1306.T`). Fixed the post-`AI調査を更新` UI rerender so the operation card immediately switches from pre-fetch guidance to the updated research-report state while preserving the mascot loading UI and transient external-source display.
- 2026-06-02: Added the first company IR site external Research adapter slice. `AI調査を更新` now includes company official IR page discovery from website metadata in the default EDINET / TDnet / company IR / Yahoo Finance composite source set, shows `企業IRサイト` as official-source evidence in the UI, and keeps normal checks network-free through fake ticker / HTTP tests.
- 2026-06-01: Completed the symbol universe metadata refresh closeout. All 9,197 rows in `symbol_universe.csv` now have Yahoo metadata dated 2026-06-01 after retrying PARR / PASG; dividend yield, PER, PBR, and ROE abnormal-count checks are 0; coverage/manifest baselines were regenerated and provider-vs-Web definition differences were documented as sanity-check references rather than exact parity requirements.
- 2026-05-30: Added manual coverage for Ranking sort-condition usage and symbol-detail entry points from both Ranking and Cockpit, with live UI screenshots for sort controls, ranking row-click detail, and cockpit `銘柄データを見る`.
- 2026-05-30: Expanded the root-level SMAI user manual with external Yahoo live-data screenshots for ranking results, cockpit chart/data retrieval, AI Research refresh, Decision Report reading, and report downloads; added bordered/responsive screenshot presentation and per-image viewing points.
- 2026-05-30: Added a root-level `manual/` user guide for the main SMAI flow, covering `銘柄ランキング` candidate narrowing and `銘柄コックピット` deep-dive usage with actual Streamlit screenshots captured via local Edge headless automation.
- 2026-05-29: Added the Windows pre-release EXE packaging slice for Smart Market AI: PyInstaller `onedir` launcher/spec/build script, pre-release README, build-only dependency pin, `build/` / `dist/` gitignore entries, operations-guide build notes, and smoke-checked the generated `dist/SMAI/SMAI.exe` through Streamlit startup, cockpit/ranking/rebalance/settings rendering, cockpit `06 根拠資料`, Decision Report downloads, sample rebalance, and live Yahoo / AI調査更新 paths.
- 2026-05-29: Ran the final stabilization sprint for the `06 根拠資料` Research screen across domestic stocks (`9983.T`, `7974.T`), foreign stocks (`TSLA`, `AMZN`), and ETFs (`QQQ`, `BND`); confirmed security-type routing, compact money units, ETF-specific missing-data guidance, and removed the remaining foreign-stock company-summary path that could surface domestic disclosure wording or `nan` URL text in UI HTML.
- 2026-05-29: Ran the fourth bounded live Research regression sprint across domestic stocks (`9983.T`, `7974.T`, `8058.T`), foreign stocks (`TSLA`, `AMZN`, `V`), and ETFs (`QQQ`, `BND`, `VNQ`); tightened communication-services-vs-telecom classification, Amazon-style retail / cloud / advertising ordering, payment-network noise suppression, and foreign-stock folded AI memo wording while preserving ETF asset-specific missing-data guidance and compact USD displays.
- 2026-05-29: Ran the third bounded live Research regression sprint across domestic stocks (`9983.T`, `6098.T`, `8058.T`, `7974.T`), foreign stocks (`TSLA`, `NVDA`, `AMZN`, `V`), and ETFs (`QQQ`, `VTI`, `BND`, `VNQ`); fixed compact `T` / `B` / `M` USD re-extraction, reduced main/supporting business noise for auto, apparel retail, HR services, trading companies, semiconductor, and payment-network profiles, and added ETF asset-type-specific missing-data guidance for equity, bond, and REIT ETFs.
- 2026-05-29: Compacted Research quantitative money display for non-JPY currencies so large USD values render as readable `T` / `B` / `M` amounts (for example `1.66T USD` and `97.88B USD`) across provider exports, company quantitative summaries, and ETF AUM display tests while preserving existing JPY `兆円` / `億円` formatting.
- 2026-05-29: Ran the second bounded live Research regression sprint across domestic non-manufacturing stocks (`8306.T`, `9432.T`, `4502.T`), foreign stocks (`MSFT`, `JPM`, `XOM`), and ETFs (`SPY`, `TLT`, `GLD`); added ETF metric candidate export / mapping for AUM, NAV, yield, expense ratio, fund family, category, and holdings, suppressed equity valuation ratios for bond / commodity ETFs, and tightened sector-led business classification for financial, healthcare, energy, telecom, and software-cloud profiles.
- 2026-05-29: Ran a bounded live Research regression sprint across domestic stocks (`7203.T`, `6758.T`), foreign stocks (`MSFT`, `NVDA`), and ETFs (`SPY`, `QQQ`); improved session provider-profile summaries so quantitative fields survive mapping, removed ETF raw provider label leakage, expanded ETF PER/PBR parsing, corrected percent-style dividend yield display, and refined business classification for semiconductor / AI data-center and software-cloud companies.
- 2026-05-29: Added security-type-aware Research display routing: provider metadata now detects domestic stock, foreign stock, ETF / fund, or unknown; ETF / fund symbols use `ETFResearchSummary` with fund overview, target assets, AUM/NAV, expense ratio, distribution yield, holdings, and ETF-specific checkpoints, while foreign stocks keep the company layout with Annual Report / 10-K / 10-Q / Earnings Release / SEC Filing wording instead of domestic TDnet / EDINET prompts.
- 2026-05-29: Refined Research quantitative provider mapping so camelCase raw provider fields populate `QuantitativeSummary`, `Currency: JPY` context formats money / EPS in yen, and TDnet title/URL-only latest disclosure rows avoid weak content memos while preserving official disclosure / unparsed status.
- 2026-05-29: Improved the Research Summary extraction layer for the company research report: added `CompanyResearchEvidence` normalization, structured business profile fields, employee count / missing metric status, IR document type classification with found / missing / unparsed status, news official-confirmation status, and moved AI読み取りメモ out of the initial view into a folded detail memo.
- 2026-05-29: Refocused the Cockpit / Ranking Research Summary from an investment-decision memo into a company research report: added `CompanyResearchSummary` models and builder, moved `企業リサーチサマリー` / `定量情報サマリー` / `IR情報サマリー` / `最新ニュースサマリー` to the top of the UI, and kept AI読み取りメモ, confirmation points, source cards, Research Score, and detail data as secondary company-understanding context.
- 2026-05-28: Reworked the Research Summary primary UI hierarchy: the operation card now reads as `事業` / `確認済み` / `次に見る`, the main confirmation area is reduced to `会社概要` / `確認できた事実` / `公式資料で未確認`, provider wording is softened to `外部データ`, and source counts / Research Score / confidence labels are pushed toward detail views.
- 2026-05-28: Expanded `ResearchFactSummary` extraction and UI display with source-backed business regions, revenue drivers, earnings outlook, and shareholder return / dividend policy facts. The Cockpit Research operation card and focus cards now surface these concrete facts alongside core metrics and recent events, while normal checks remain deterministic.
- 2026-05-28: Implemented the first `ResearchFactSummary` slice: backend `ResearchBriefBuilder` now produces source-backed business overview, business segment, financial metric, recent-event, material, and missing-item facts; the Cockpit Research operation card and reading guide prioritize actual business / metric / event facts over acquisition status or raw source counts. Targeted Research service/UI tests, ruff, mypy, and Black helper checks passed.
- 2026-05-28: Documented the next Research Summary maturity slice: introduce `ResearchFactSummary` between evidence/news/provider payloads and `ResearchBrief` so the UI shows source-backed business overview, IR / official disclosures, key metrics, recent events, positive/caution materials, and missing items instead of acquisition status or raw source counts. The design keeps local rule-based generation first and local lightweight LLM synthesis as optional/future with deterministic fallback.
- 2026-05-28: Connected ResearchBrief source cards to the Research Summary `出典カード` UI so cards now use `ResearchBrief.source_cards`, show source type, provider / URL where available, freshness, and source-confidence wording. Research Score and ranking behavior remain unchanged.
- 2026-05-28: Implemented the first local ResearchBrief readability slice: added `ResearchBrief`, `ResearchMetric`, source cards, and `ResearchBriefBuilder`; the Cockpit / Ranking Research Summary now starts with AI整理メモ, quantitative metrics, business overview, positive/caution candidates, missing evidence, next actions, and source cards before Research Score/detail rows. Provider raw fields are filtered out of the normal brief view, and tests cover deterministic metric extraction, missing metrics, source confidence, and UI escaping.
- 2026-05-28: Audited project Markdown docs for Research RAG / ResearchBrief direction mismatches and aligned requirements, system/functional design, class diagram notes/UML, Research RAG detail design, roadmap, and project context with the current policy: AI調査 uses external fresh sources as the standard user flow, local documents are fixtures/archive/fallback, TDnet + Yahoo Finance first slice is implemented, Research Score first slices are implemented, and the next readability slice is local rule-based ResearchBrief before external LLMs.
- 2026-05-27: Documented the local ResearchBrief direction for Research Summary readability: defer external LLMs, convert RAG evidence / provider profile / news / TDnet traces into a deterministic AI整理メモ, quantitative summary, business overview, positive/caution candidates, missing evidence, next actions, and source cards; keep provider raw fields in detail data only.
- 2026-05-27: Reworked Cockpit external Research source display from a compact table into user-readable overview and source cards: the UI now highlights source set, latest published date, official TDnet count, freshness warnings, per-source check guidance, and source links while keeping raw trace rows in detail data.
- 2026-05-27: Added TDnet timely-disclosure external Research adapter and default composite external source set for `AI調査を更新`: the Cockpit AI refresh now uses TDnet official disclosure links plus Yahoo Finance profile/news as transient session-local evidence, with fake HTTP / fake ticker tests preserving network-free normal checks.
- 2026-05-27: Integrated Cockpit external Research fetch into the standard `AI調査を更新` flow: removed the separate external-permission panel from the UI path, fetches external source adapters with the backend safety gate when AI Research runs, stores source trace rows in session state, continues with saved/local fallback if external fetch fails, and displays external source trace rows inside the Research Summary panel / Decision Report without retaining fetched source text.
- 2026-05-27: Updated Research RAG documentation direction from local-documents-first / explicit external permission toward external-fresh-sources-first: `AI調査を更新` should become the standard external IR / disclosure / news / provider evidence search action, while local registered documents remain deterministic fixtures, demo seeds, user-saved archives, private notes, and fallback. Normal checks remain network-free with fake adapters / fixtures, and fetched source text remains transient-by-default.
- 2026-05-27: Aligned Research Score maturity docs with the current implementation: FS-013 now reflects the implemented optional disabled-by-default Research Score integration, UX review rows cover evidence-backed and missing-evidence Research Score cases, and the UI wording policy clarifies that Research Score is evidence coverage / freshness / reliability context, not a buy/sell signal or default ranking input.
- 2026-05-27: Added Cockpit Decision Report external source trace support: opt-in external Research / News fetch results now render an `外部参照ソース` section with provider / fetched_at / published_at / source URL / freshness_status / short summary / warnings, while still excluding fetched source text, local paths, document hashes, and manifests.
- 2026-05-27: Added freshness_status trace rows to opt-in external Research / News fetch, with stale-source warnings and Cockpit result-table freshness labels while keeping fetched payload text transient-by-default.
- 2026-05-27: Changed opt-in external Research / News fetch to transient-by-default implementation: fetched Yahoo Finance profile/news text is registered into the session-local RAG store for the current analysis pass without writing payload Markdown or manifest files, and the Cockpit UI now shows provider / fetched_at / source URL / summary instead of local storage paths.
- 2026-05-27: Updated Research RAG external-fetch documentation to set transient-by-default live evidence as the product policy: external source text should be used for the current summary / score / display pass without default document or manifest retention; the existing `external_cache` persistence path is now documented as implementation debt for the next code slice.
- 2026-05-27: Added a first opt-in Cockpit UI slice for external Research / News fetch: users must allow external communication before Yahoo Finance profile/news fetch runs, fetched Markdown + manifest JSON are saved under `data/research_docs/external_cache/`, the session-local Research RAG store is updated/re-chunked, and source URL / provider / fetched_at / local path / manifest rows are visible without changing ranking order or default scoring.
- 2026-05-27: Added report-derived Research Score context to ranking selected-candidate breakdown and ranking research-status rows; it remains confirmation-only and does not change ranking order or default Investment Score behavior.
- 2026-05-27: Added Research Score reference rows to the shared Cockpit / Ranking Research Summary panel, including summary, component, and warning rows, while preserving unchanged ranking order and default Investment Score behavior.
- 2026-05-27: Added a Cockpit Decision Report Research Score section: reports with Research evidence now export Research Score components, confidence, supporting evidence, warnings, and non-advice notes alongside Research Evidence without changing default ranking order or Investment Score behavior.
- 2026-05-27: Connected Research Score to Investment Score as an optional disabled-by-default backend input: `research_scores_by_symbol` can carry precomputed Research Score values, `scoring.weights.research` defaults to 0.0, and default totals / bands / breakdowns / ranking order remain unchanged.
- 2026-05-27: Added the first backend-only Research Score MVP slice with `ResearchScore` and `ResearchScoreService`; it scores evidence coverage, freshness, disclosure quality, confidence, warnings, and supporting evidence from `CompanyResearchReport` without changing Investment Score, ranking order, or UI defaults.
- 2026-05-27: Added `ResearchVectorIndexService` and `ResearchVectorIndexSummary` as an explicit optional vector-index build workflow; it rebuilds writable vector stores from already chunked Research documents, reports chunk / embedded counts and missing text-index warnings, and keeps default keyword retrieval unchanged.
- 2026-05-27: Added `ResearchEmbeddingService` for deterministic local hash-based Research RAG embeddings; it builds chunk/query vectors, keeps `text_hash` and `embedding_model` cache-key fields, and can explicitly upsert generated embeddings into writable vector stores without external embedding APIs or changing default keyword retrieval.
- 2026-05-27: Added `ResearchFileVectorStore` as a UTF-8 JSONL-backed optional vector cache; persisted and reloaded `ResearchRetrievalCandidate` + `ResearchEmbedding` pairs across service instances with deterministic tests for persisted search, empty-cache warnings, and invalid-cache errors while keeping default keyword retrieval unchanged.
- 2026-05-27: Reworked Symbol Cockpit `06 Research Evidence` into an AI調査ステータス operation card with clearer next-step / primary / secondary action hierarchy, decision-oriented summary metrics, vertical evidence/news cards, and collapsed detail-data tables; reworked cockpit `07 投資判断レポート` into a structured judgement card, 3-line summary, evidence block, sectioned detail report, and downloads without showing raw Markdown as the main UI.
- 2026-05-26: Expanded Symbol Cockpit `SMAI Insight` direction wording for upside-dominant, downside-caution, both-high, both-low, model-split, forecast-spread, and data-limited states; further compacted Ranking detailed-table columns by purpose; split Ranking Decision Report rows into candidate memo and score-detail sections.
- 2026-05-26: Adjusted shared SMAI typography so body copy, captions, insight text, cards, and confirmation tables are slightly larger/brighter with roomier line-height without changing the dense dashboard layout.
- 2026-05-26: Refined Ranking detailed table readability by combining confidence/source columns into `信頼度/根拠`, wrapping the visible confirmation memo, hiding long reason/checkpoint detail columns, and adding symbol names to Ranking Decision Report rows.
- 2026-05-26: Updated Ranking acquisition periods to `短期: 1か月`, default `標準: 3か月`, `中期: 6か月`, and `長期: 1年` so direction-signal v2 has enough history for 20日/60日 momentum, volatility, and trend checks.
- 2026-05-26: Reworked Symbol Cockpit `SMAI Insight`, `Signal Reading`, and confirmation-point tables so chart copy avoids duplicate direction-score cards and table rows describe actual value bands, model split, forecast spread, and next verification points.
- 2026-05-26: Split Symbol Cockpit card wording into visible `今回:` value readings and `?` metric-help tooltips, and renamed the displayed `方向スコア` card to `方向バランス`.
- 2026-05-26: Added value-band wording tables for Symbol Cockpit cards so KPI and direction-signal descriptions explain both metric meaning and how to read the current score.
- 2026-05-26: Added a Symbol Cockpit `Direction Signal / 上昇気配・下降警戒` section so single-symbol review shows the same direction label, upside signal, downside warning, forecast return, model direction counts, and forecast spread used by ranking.
- 2026-05-26: Changed the multi-factor / upside ranking scatter chart to `上昇気配 x 下降警戒` with direction-score color, and made scatter axes focus on the visible candidate range so tightly clustered upside scores are easier to compare.
- 2026-05-26: Changed forecast direction scoring so model agreement acts as a neutral confidence adjustment rather than an additive upside/downside bonus, widened ensemble return thresholds, and made the upside ranking watch map use raw `下降警戒` on the y-axis.
- 2026-05-26: Refined forecast direction scoring so upside / downside signals use weighted model-by-model forecast return strength instead of only counting how many models point up or down.
- 2026-05-26: Corrected ranking bar charts to sort by the selected metric value instead of overall rank order, and mapped ETF low-cost bars to `条件適合度` so high expense ratios do not look favorable.
- 2026-05-26: Updated ranking top cards to feature larger company names with wrapping text, and made the top-10 bar chart use the selected ranking purpose metric instead of always showing total Investment Score.
- 2026-05-26: Hardened ranking direction-signal recovery for stale Streamlit backend module caches, bumped the ranking build cache key, and changed direction-data-limited chart fallback from `Score x Risk` to `Screening x Risk`.
- 2026-05-26: Restored the Symbol Cockpit title art alongside the new `SMAI Copilot` panel so the cockpit header keeps its original visual identity while retaining the assistant presence.
- 2026-05-26: Reworked the Symbol Cockpit mascot from a static header image into a transparent `SMAI Copilot` presence panel with subtle CSS float / glow motion, and connected score commentary to a matching `SMAI Insight` context without changing analysis logic.
- 2026-05-26: Refreshed `symbol_universe.csv` from JPX ETF/NISA, IMAJ NISA, and SBI US stock/ETF official sources; added 3 JPX ETFs, 6 SBI US stocks, and 9 SBI US ETFs; marked 24 symbols missing from the latest SBI lists as not tradable; rechecked 16 extreme Yahoo metric outliers and flagged them as `data_quality=WARN`.
- 2026-05-24: Added project maturity documentation: manual UX review checklist, functional spec issue register, feature-role clarification, wording guardrails, score hierarchy notes, and roadmap/context guidance to review confusing behavior before feature expansion.
- 2026-05-24: Renamed ranking detail modal `Research` tab to `AI Research` and changed the action button to the primary `AIで資料を確認` label so users understand it checks registered materials before investment review.
- 2026-05-24: Improved Research RAG modal readability by replacing horizontal dataframes with wrapping HTML summary tables and vertical evidence excerpts, and reduced oversized metric text in the symbol-detail modal.
- 2026-05-24: Added shared Research Summary display for cockpit and ranking detail flows; ranking row-click `銘柄データ` modal now has a `Research` tab with `根拠を見る`, and both flows show source document names, dates, evidence counts, topic summaries, and evidence details.
- 2026-05-24: Changed cockpit Research RAG to explicit `AIデータ取得` execution beside the Research section header, keeping detailed evidence rows inside a separate expander; price-data fetch does not automatically run Research Summary.
- 2026-05-24: Documented the future migration path where `data/research_docs/` is demoted from manual primary input to cache / audit archive / offline fixture storage after external Research source adapters become stable.
- 2026-05-24: Added a yfinance profile fetch helper and saved a real `7203.T` Yahoo Finance provider-profile Markdown under `data/research_docs/` for local Research RAG confirmation.
- 2026-05-24: Connected Phase 20 Research RAG to the UI/report path with Settings session-local document upload, cockpit Research Summary display, and Cockpit Decision Report Research Evidence sections when documents/evidence exist.
- 2026-05-24: Started Phase 20 Research RAG backend slice with local UTF-8 document ingestion, hash dedupe, chunking, keyword evidence search, deterministic Research Summary, data-quality warnings, tests, and design-doc baseline.
- 2026-05-24: Expanded Phase 20 / 21 roadmap direction so Research RAG starts as a local-first evidence layer for cockpit, ranking, and Decision Report, with Research Score and Investment Score / ranking integration deferred to Phase 21.
- 2026-05-24: Closed Phase 19 scope by keeping UI-rich PDF / Excel reports as future Advanced Export work; current Decision Report exports remain Markdown / JSON / manifest / ZIP.
- 2026-05-24: Stabilized ranking resort rendering by using a stable AgGrid key, carrying the ranking date window into cockpit handoff, removing callback rerun, moving deep-dive controls above the report, and making ranking report generation lazy/cached by ranking source and sort profile.
- 2026-05-24: Reworked ranking Decision Reports to emphasize ranking-specific comparison value: distribution, factor leaders, and group-level checkpoints instead of top-symbol metadata / valuation / score sections.
- 2026-05-24: Made the Decision Report UI more prominent by moving cockpit/ranking/rebalance report downloads out of a fully collapsed expander and keeping only the Markdown body preview collapsed.
- 2026-05-23: Completed Phase 19 by adding the shared Decision Report export package helpers and wiring cockpit / ranking / rebalance report expanders to Markdown, JSON, manifest, and ZIP downloads.
- 2026-05-23: Wired the Rebalance result screen into Phase 19 Decision Report with Markdown / JSON downloads and a preview covering current holdings, target allocation, allocation drift, proposed trades, Risk breaches, and confirmation checkpoints.
- 2026-05-23: Advanced Phase 19 report design by fixing the roadmap output policy around data confidence, symbol metadata, score/valuation/income/risk context, ranking/rebalance context, and decision checkpoints; added standard `backend/reporting` section builders for data confidence, symbol metadata, and decision checkpoints with targeted tests.
- 2026-05-23: Added cockpit and ranking UI Decision Report expanders with Markdown / JSON downloads and Markdown preview, reusing Phase 19 report context sections.
- 2026-05-23: Localized Decision Report Markdown output to Japanese-first labels, section titles, notes, table headers, and confirmation wording while keeping JSON schema keys stable.
- 2026-05-23: Added cockpit period presets for short/mid/long/YTD/custom review windows and replaced repetitive ranking report row notes with per-symbol review points.
- 2026-05-23: Added cockpit period preset help text so each window explains its investment review basis before data fetch.
- 2026-05-23: Moved cockpit period `カスタム` to the top of the preset list and made it the default selection.
- 2026-05-23: Added a cockpit confirmation summary that lifts key closed-detail values into the main result view.
- 2026-05-23: Added period-aware cockpit evaluation for fetched windows, covering return, range position, drawdown, volatility, and short/mid/long review basis.
- 2026-05-23: Added a collapsible cockpit symbol preference filter for narrowing Symbol候補 by region, product, metadata attributes, and valuation/income ranges.
- 2026-05-23: Removed the redundant cockpit `銘柄候補` list expander and renamed the market-data fetch button to a clearer Japanese primary action.

- 2026-05-17: Started Phase 19 by adding `backend/reporting` Decision Report context v1, deterministic Markdown rendering, local export manifest metadata, and tests covering cockpit / ranking / rebalance context composition. / Phase 19 を開始し、`backend/reporting` に Decision Report context v1、deterministic Markdown rendering、local export manifest metadata、cockpit / ranking / rebalance context composition tests を追加した。

## 2026-05-22 - Ranking symbol detail modal readability

- Enlarged the ranking symbol detail modal and reorganized symbol master data into user-facing overview, investment metric, ETF/fund, data-info, and raw registration tabs.
- Added display-label conversion for internal symbol-universe values such as `sbi_securities`, `yahoo`, NISA categories, market-cap tiers, and risk bands.
- Added dialog CSS for a wider modal and wrapped metric values to avoid text clipping.
- Moved raw CSV column/value details into a collapsed confirmation expander with both display values and registered raw values.
- Added short usage notes to data-info rows so users can see why source, freshness, and provider ticker fields matter.

## 2026-05-22 - Ranking result modal rerun stabilization

- Stabilized the ranking-result AgGrid key so closing a detail modal does not remount/repaint the result table.
- Changed the modal trigger to process row-click event tokens, preventing the previous click from reopening on modal-close reruns while allowing the same row to be clicked again.
- Kept the AgGrid update trigger scoped to row-click events.

## 2026-05-22 - Ranking symbol master detail modal

- Added a ranking-result row click flow that opens a modal with the selected symbol's local `symbol_universe.csv` data.
- Replaced the temporary full-width button rows with an AgGrid ranking result table so row-click detail opening, hover/selection state, horizontal scrolling, sorting, filtering, and column resizing can coexist with a table-like layout.
- Tuned the AgGrid ranking table dark styling so headers stay readable and the grid surface is visually distinct from the surrounding page.
- Rendered symbol master fields as `項目 / 列 / 値` rows so UI labels and raw CSV column names can be checked together.
- Added investment-use help text to the ranking acquisition period selector, explaining short, medium, and long lookback use cases.
- Added regression tests for AgGrid options, selected-row extraction, stable table keys, and symbol master detail row formatting.

## 2026-05-22 - Ranking dividend filter mutual exclusion

- Made ranking dividend category and explicit dividend-yield range mutually exclusive; explicit range wins if both are restored from older saved state.
- Reworded dividend category labels as numeric yield bands and removed the duplicate high-dividend theme choice from the industry/theme dropdown.
- Renamed the ETF dividend index family label to `配当系指数` so it is not confused with a yield screening condition.
- Added regression tests for dividend filter normalization, label wording, and cache-signature normalization.

## 2026-05-22 - Ranking NISA filter wording

- Simplified the ranking NISA dropdown for the current stock / ETF scope to `指定なし（NISAで絞らない）`, `NISA対象のみ（成長投資枠）`, and `NISA対象外のみ`.
- Removed confusing visible choices such as `つみたて投資枠` and `両方`; legacy saved values now reset to the safe default.
- Added `NISA対象外のみ` filtering so ETF candidates can be narrowed by confirmed non-eligible rows.
- Documented that stock candidates are currently stored as growth-NISA eligible, so the NISA target filter does not reduce domestic or US stock counts.

## 2026-05-22 - NISA and ETF metadata horizontal cleanup

- Backfilled 4,334 US stock rows as NISA growth eligible, matching the stock-level treatment already applied to JP listed stocks.
- Normalized NISA boolean flags from `nisa_category` so `growth`, `both`, and `none` rows now have consistent `nisa_growth_eligible` / `nisa_tsumitate_eligible` values.
- Tightened ETF leveraged detection so ordinary names containing `ブルームバーグ`, `サステナブル`, `コンバーチブル`, or `FTSEブルサ` are not misclassified as leveraged products.
- Reclassified confirmed leveraged / inverse ETFs as NISA `none` where they had remained `unknown`, while leaving ordinary unconfirmed ETF rows for official source review.

## 2026-05-22 - JP stock NISA metadata backfill

- Confirmed the ranking NISA filter was working as designed, but the domestic-stock universe only had 8 JP stock rows marked NISA eligible.
- Backfilled JP stock rows in `symbol_universe.csv` so 3,747 domestic stock rows now carry `nisa_category=growth`, `nisa_growth_eligible=true`, and `nisa_tsumitate_eligible=false`.
- Updated the JPX stock import profiles so future JPX listed-stock imports keep domestic listed stocks aligned with the NISA growth-investment default.
- Added tests covering the JPX profile defaults, the current JP stock NISA coverage floor, and the ranking NISA filter behavior.

## 2026-05-22 - Ranking filter wording and beta risk UI

- Added beginner-friendly help text to the ranking detail filters for sector/theme, market cap, NISA, ETF index, expense ratio, complexity, dividend, currency, PER, PBR, ROE, and keyword search.
- Expanded/clarified sector/theme labels, including the observed bond category and clearer sector wording for communication, consumer, industrial, and index ETF rows.
- Reworded market-cap and dividend-category choices with quantitative thresholds, including separate JP/US market-cap cutoffs and dividend-yield bands.
- Exposed stock `risk_band` as `市場感応度（β）` with threshold-based choices such as `低変動のみ（β < 0.8）`, `標準以下（β <= 1.2）`, and `高変動のみ（β > 1.2）`.
- Kept legacy `LOW` / `MEDIUM` / `HIGH` filter compatibility while routing the UI through quantitative beta labels.
- Updated UI wording and operations docs to distinguish pre-fetch beta filtering from post-fetch ranking Risk / risk score checks.

- 2026-05-21: Imported the JPX ETF/ETN official HTML source and IMAJ NISA growth listed-fund Excel into the local symbol universe flow, expanding ETF candidates to 449 and updating 232 existing ETF rows with NISA growth metadata while leaving REIT / infrastructure-fund rows as update-only failures outside the MVP universe. / JPX ETF/ETN 公式 HTML source と IMAJ NISA 成長投資枠 listed-fund Excel を local symbol universe flow に取り込み、ETF 候補を449件へ拡張し、既存 ETF 232件へ NISA 成長投資枠 metadata を反映した。REIT / インフラファンド行は MVP 対象外として update-only failure に残した。
- 2026-05-21: Added `tools/check_symbol_universe_yahoo_coverage.py` for explicit live Yahoo OHLCV coverage checks, ran sample and full checks for JPX listed-stock additions, and stored JSON/CSV outputs under `data/marketdata/live_checks/`. Sample 30/30 succeeded; full 3,645-symbol check succeeded for 3,641 symbols, with four short-period no-bar symbols investigated separately. / 明示的な live Yahoo OHLCV coverage check 用に `tools/check_symbol_universe_yahoo_coverage.py` を追加し、JPX 東証上場銘柄追加分のサンプル・全数確認を実行して `data/marketdata/live_checks/` に JSON/CSV を保存した。サンプルは 30/30 成功、全数 3,645件は 3,641件成功し、短期期間で no-bar だった4件は個別に確認した。
- 2026-05-20: Added `.xls` raw-file support to `tools/build_symbol_universe_source.py` via `xlrd`, imported the JPX listed-stock 2026-05-20 raw file into `symbol_universe.csv`, and expanded the local candidate master to 3,872 rows while keeping JPX tradability as `unknown`. / `tools/build_symbol_universe_source.py` に `xlrd` による `.xls` raw file 対応を追加し、2026-05-20 の JPX 東証上場銘柄一覧を `symbol_universe.csv` に取り込み、JPX 由来の tradability は `unknown` のまま local candidate master を 3,872件へ拡張した。
- 2026-05-18: Added the first live symbol metadata adapter for Yahoo behind explicit `--provider yahoo --allow-live`, mapping selected ticker metadata into the catalog fields and recording per-symbol failures in the refresh manifest while keeping normal checks network-free. / 初の live symbol metadata adapter として Yahoo を `--provider yahoo --allow-live` の明示 opt-in 配下に追加し、取得できた ticker metadata を catalog fields へ正規化。失敗銘柄は refresh manifest に残し、通常 checks は network 非依存のまま維持した。
- 2026-05-18: Added the Phase 18 symbol metadata catalog to define core / ranking-filter / fund-extended tiers, storage policy, source and freshness requirements, and future fund metadata boundaries before adding live provider updates. / live provider 更新を追加する前に、Phase 18 の symbol metadata catalog を追加し、core / ranking-filter / fund-extended の tier、保存方針、source/freshness 要件、将来の投信 metadata 境界を定義した。
- 2026-05-18: Implemented the Phase 18 provider-neutral symbol metadata refresh path with a deterministic `curated_csv` provider, dry-run-first CLI, manifest summary, guarded `--write` path, provider diagnostics, and tests for the service and tool. / Phase 18 の provider-neutral な symbol metadata refresh 経路を実装。deterministic な `curated_csv` provider、dry-run first CLI、manifest summary、validation 付き `--write`、provider diagnostics、service/tool test を追加した。
- 2026-05-18: Updated the Phase 18 roadmap with the provider strategy: Yahoo remains the default live provider, but metadata refresh must be implemented behind a provider-neutral contract with dry-run/manifest first and live adapters kept opt-in. / Phase 18 ロードマップに provider 方針を追記。Yahoo は既定 live provider としつつ、metadata refresh は provider-neutral contract、dry-run/manifest 先行、live adapter 明示 opt-in として進める。
- 2026-05-18: Continued Phase 18 by adding metadata source/as-of/update columns to `symbol_universe.csv`, summarizing metadata source and freshness in Settings, warning on missing metadata fields, and testing the curated CSV metadata baseline. / Phase 18 を継続し、`symbol_universe.csv` に metadata source/as-of/update 列を追加。Settings で metadata 出所と鮮度を要約表示し、metadata 欠損 warning と curated CSV baseline の test を追加した。
- 2026-05-18: Started Phase 18 symbol metadata refresh with a network-free schema slice: added `symbol_universe.csv` required/optional column definitions, enum/decimal/duplicate ticker validation, Settings validation display, and tests covering the current curated CSV. / Phase 18 の symbol metadata refresh を network 非依存の schema から開始し、`symbol_universe.csv` の必須/任意列、enum/decimal/重複 ticker validation、Settings での確認表示、現在の curated CSV を検証する test を追加した。
- 2026-05-18: Marked Phase 17 ranking-condition UI polish as implementation-complete after user visual confirmation, and updated the roadmap/current context so Phase 18 symbol metadata refresh is the next implementation target. / ユーザーの目視確認完了を受けて Phase 17 ranking-condition UI polish を実装完了扱いにし、ロードマップと現在地を更新して Phase 18 symbol metadata refresh を次の実装対象にした。
- 2026-05-18: Added a compact ranking comparison status line for acquisition period, candidate count, selected count, and all/partial selection status so the collapsed comparison-symbol selector remains understandable without adding a bulky section. / ranking の比較状態を1行で表示し、取得期間・候補数・選択数・全候補/一部選択の状態を、比較銘柄 selector を閉じたままでも分かるようにした。
- 2026-05-18: Polished the Phase 17 ranking condition layout by shortening detail-filter wording, grouping filters into attribute / numeric / keyword sections, moving the all-selected comparison-symbol multiselect into a collapsed expander, and removing the unused legacy ranking-filter dialog from `ui/app.py`. / Phase 17 ranking 条件 UI を調整し、詳細条件の文言を短くし、属性条件・数値条件・キーワード検索に分け、全件選択の比較銘柄 multiselect は折りたたみへ移動。未使用の旧 ranking filter dialog を `ui/app.py` から削除した。
- 2026-05-18: Started Phase 17 ranking-condition UI polish by adding region / product type / ranking purpose classification, wiring dynamic detail filters into the Streamlit ranking page, deriving display weight presets from ranking purpose, and keeping only `symbol_universe.csv`-backed filters active while marking mutual-fund metadata as future scope. / Phase 17 の ranking-condition UI polish として、地域・商品・ランキング目的の分類を追加し、Streamlit の銘柄ランキングへ動的な詳細条件を接続。ランキング目的から表示順の重み付けを決めるようにし、実フィルタは `symbol_universe.csv` で判定できる条件に限定しつつ、投信 metadata は将来拡張として扱った。
- 2026-05-18: Shared one curl_cffi-backed yfinance session across Yahoo `Search`, `download`, and `Ticker` calls to keep cookie / crumb state attached to the same HTTP session and improve first-call live fetch stability. / Yahoo の `Search`、`download`、`Ticker` 呼び出しで curl_cffi backed の yfinance session を共有し、cookie / crumb 状態と HTTP session がズレにくいようにして初回 live fetch の安定性を改善した。
- 2026-05-18: Added a short one-time retry for empty Yahoo yfinance download batch responses so first-call warm-up or transient empty responses are retried inside the provider instead of requiring the user to press Fetch again. / Yahoo yfinance download の batch response が空だった場合に短い 1 回リトライを追加し、初回 warm-up や一時的な空レスポンスでユーザーが Fetch を押し直さなくても provider 内で吸収できるようにした。
- 2026-05-18: Made Yahoo cockpit fetch more price-first by skipping live FX and fundamentals during the initial single-symbol fetch, reducing auxiliary Yahoo calls that can add timeout latency while keeping price/forecast/score rendering available. / Yahoo cockpit の初期取得を価格優先にし、単一銘柄 fetch では live FX / fundamentals を取得しないようにして、timeout 待ちになりやすい補助 Yahoo call を減らしつつ価格・予測・score 表示を維持した。
- 2026-05-18: Hardened Yahoo cockpit fetching by routing single-symbol OHLCV through the same non-threaded yfinance download path as ranking and treating FX/fundamentals as auxiliary data so price/forecast/score can still render with structured warnings when auxiliary live requests fail. / Yahoo cockpit の取得安定性を上げるため、単一銘柄 OHLCV も ranking と同じ非 threaded yfinance download 経路へ寄せ、FX / fundamentals は補助データとして扱い、補助 live request が失敗しても価格・予測・score は表示し structured warning を出すようにした。
- 2026-05-18: Simplified the roadmap chapter structure by grouping completed work into Phase 1-9 MVP foundation and Phase 10-16 investment/UI foundation, numbering the next implementation sequence as Phase 16S through Phase 24, and consolidating future AI/RAG/execution details into a single backlog section without a duplicated appendix. / ロードマップの章立てを整理し、完了済みを Phase 1-9 MVP foundation と Phase 10-16 investment/UI foundation に分け、次期実装順を Phase 16S から Phase 24 まで番号付きで並べ、重複していた appendix を削って future AI/RAG/execution の詳細を backlog に集約した。
- 2026-05-18: Reordered the implementation roadmap around the actual next build sequence: Phase 16S stabilization, Phase 17 ranking-condition UI polish, Phase 18 symbol metadata refresh, Phase 19 Decision Report context, Phase 20/21 Research RAG and Research Score, Phase 22 assistant, Phase 23 optional adapters, and Phase 24 export/execution gate. / 実装ロードマップを実際の次期実装順に並び替え、Phase 16S stabilization、Phase 17 ranking-condition UI polish、Phase 18 symbol metadata refresh、Phase 19 Decision Report context、Phase 20/21 Research RAG / Research Score、Phase 22 assistant、Phase 23 optional adapters、Phase 24 export/execution gate として整理した。
- 2026-05-18: Clarified Market Data ranking partial-failure handling by marking no-price symbols as excluded with provider/request diagnostics and resetting the deep-dive selector to the current top-ranked symbol when the ranking source or weight preset changes. / Market Data ranking の部分失敗時に、価格未取得銘柄をランキング除外として provider/request 診断付きで表示し、ranking source や重視条件が変わった場合は深掘り候補を現在の上位銘柄へ戻すようにした。
- 2026-05-18: Suppressed yfinance warning/error logger output inside the Yahoo provider call boundary so repeated live-provider failures remain visible as structured SMAI diagnostics instead of raw console spam. / Yahoo provider の呼び出し境界で yfinance の warning/error logger 出力も抑制し、live provider の取得失敗は生ログではなく SMAI の structured diagnostics として見えるようにした。
- 2026-05-18: Further separated ranking state and scoring helpers by adding `ui/ranking_state.py` for Streamlit session-state handling and moving ranking score reweighting/sorting into `ui/ranking.py`, leaving `ui/app.py` closer to page rendering and provider execution. / ranking の状態管理と score helper をさらに分離し、Streamlit session-state 操作は `ui/ranking_state.py`、ranking score の重み付け・並べ替えは `ui/ranking.py` へ移動。`ui/app.py` は page rendering と provider execution に寄せた。
- 2026-05-18: Continued the Streamlit lightweight refactor by extracting ranking constants, symbol-universe filtering, ranking filter signatures, chunking, cache keys, live-warning text, and provider error row helpers into `ui/ranking.py` while keeping `ui/app.py` focused on rendering and execution flow. / Streamlit 軽量化リファクタを継続し、ranking 定数、symbol universe filtering、filter signature、chunking、cache key、live warning、provider error row helper を `ui/ranking.py` へ切り出し、`ui/app.py` は表示と実行 flow に寄せた。
- 2026-05-18: Added the ranking-condition classification work to Phase 19 UI Polish, scoped as region/product/purpose selectors plus data-backed dynamic detail filters, with future-only metadata kept separate from currently enforceable filters. / ランキング作成条件 UI の分類整理を Phase 19 UI Polish に追加し、地域・商品・ランキング目的の選択と、既存データで判定できる動的詳細条件を初期範囲に整理。将来用 metadata 条件は現時点で有効な filter と分けて扱う方針にした。
- 2026-05-18: Reduced repeated Yahoo fetch failures by reporting live ranking batch errors once, reusing one OHLCV range for single-symbol cockpit quote/features, and suppressing noisy yfinance stdout/stderr messages while keeping structured UI diagnostics. / Yahoo 取得失敗の繰り返しを抑えるため、ranking の live provider batch error は銘柄別再試行せず 1 回の structured error として表示し、単一銘柄 cockpit は 1 回取得した OHLCV を quote/features に再利用し、yfinance の stdout/stderr 生ログは抑制して UI の診断情報に寄せた。
- 2026-05-18: Reaffirmed Streamlit Market Data as Yahoo live-first by keeping `yahoo` first/default in provider selectors, replacing the temporary 10-symbol Yahoo ranking hard limit with a warning above 30 symbols, while retaining smaller non-threaded Yahoo download chunks and cached yfinance search results. / Streamlit Market Data を Yahoo live-first として整理し、provider selector は `yahoo` を先頭・初期表示に維持。暫定的な Yahoo ranking 10 銘柄 hard limit は撤廃して 30 銘柄超の警告に置き換えつつ、小さめの非 threaded Yahoo download chunk と yfinance 検索 cache は維持した。
- 2026-05-18: Improved Streamlit Market Data provider error handling so live-provider failures stop before empty cockpit sections, show beginner-friendly next actions, keep raw provider details inside a diagnostics expander, and report the Yahoo opt-in adapter as implemented in Yahoo adapter diagnostics. / Streamlit Market Data の provider エラー表示を改善し、live provider 失敗時は空のコックピット表示へ進まず、次の確認手順を初心者向けに示し、raw provider details は診断情報 expander に畳み、Yahoo adapter の診断情報では opt-in adapter を実装済みとして表示するようにした。
- 2026-05-18: Started the Streamlit refactor/lightweight pass by extracting Rebalance rendering into `ui/views/rebalance.py`, shared UI helpers into `ui/views/common.py`, and MarketData session-state keys into `ui/state.py` while keeping `ui/app.py` as a compatibility entrypoint for existing tests. / Streamlit のリファクタ・軽量化として、Rebalance 表示を `ui/views/rebalance.py`、共通 UI helper を `ui/views/common.py`、MarketData の session state key を `ui/state.py` へ切り出し、既存テスト互換の入口として `ui/app.py` から再公開する形にした。
- 2026-05-18: Replaced the Streamlit sidebar radio selector with a button-style side menu panel and moved settings view code out of the reserved `ui/pages` directory to avoid Streamlit native multipage navigation. / Streamlit サイドバーの radio 選択をボタン型のサイドメニューパネルへ変更し、Streamlit の標準マルチページナビが出ないよう設定画面コードを予約ディレクトリ `ui/pages` から移動した。
- 2026-05-18: Reworked the Streamlit layout from broad top tabs and heavy sidebar controls into a compact `sidemenu.py` driven screen switcher, with Rebalance inputs moved into the Rebalance page and symbol references moved into cockpit/settings views. / Streamlit の画面構成を、上部タブと重いサイドバー入力から、`sidemenu.py` による軽量な画面切り替えへ整理し、Rebalance 入力を Rebalance 画面内へ、銘柄候補をコックピット/設定画面側へ移動した。
- 2026-05-18: Synchronized current-state documentation with implementation after a project-wide doc/code consistency review, clarifying Phase 16 completion, Streamlit provider defaults, Yahoo opt-in adapter status, setup Python expectations, and future-scope technology/reporting items. / プロジェクト全体のドキュメントと実装の整合性を確認し、Phase 16 完了扱い、Streamlit provider 初期表示、Yahoo opt-in adapter 状態、setup の Python 前提、future scope の技術・レポート項目を現在実装に合わせて整理した。
- 2026-05-17: Marked Phase 16 as implementation-complete with final Streamlit browser smoke recommended, and added the Phase 16 final UI smoke checklist to the roadmap and operations guide. / Phase 16 を実装完了扱いに更新し、最終 Streamlit browser smoke 推奨として、Phase 16 最終 UI 確認チェックリストをロードマップと運用ガイドへ追加した。
- 2026-05-17: Documented the current Phase 16 ranking workflow in the operations guide, including `symbol_universe.csv`, the in-page screening condition panel, ranking cache, Yahoo batch OHLCV fetch, progress display, and the ranking-to-cockpit deep-dive flow. / Phase 16 の銘柄ランキング workflow について、`symbol_universe.csv`、画面内スクリーニング条件パネル、ranking cache、Yahoo 一括 OHLCV 取得、進捗表示、銘柄コックピットへの深掘り導線を運用ガイドへ記録した。
- 2026-05-17: Polished the Phase 16 Market Data ranking UI wording by clarifying that screening conditions filter candidates while acquisition period / weight preset control ranking calculation and display ordering. / Phase 16 Market Data ranking の UI 文言を調整し、スクリーニング条件は候補絞り込み、取得期間と重視条件は ranking 計算・表示順の設定であることを明確化した。
- 2026-05-17: Added a Phase 16 in-page screening condition panel to Market Data ranking, expanded `symbol_universe.csv` with deterministic PER/PBR/ROE/consensus/risk metadata, and supported ON/OFF range filters for comparison candidates. / Market Data ranking に Phase 16 の画面内スクリーニング条件パネルを追加し、`symbol_universe.csv` に deterministic な PER/PBR/ROE/コンセンサス/risk metadata を拡張。比較候補向けに ON/OFF 付き範囲条件を使えるようにした。
- 2026-05-17: Moved the Phase 16 Market Data ranking symbol universe into `data/marketdata/symbol_universe.csv`, added a CSV loader for UI symbol names/metadata, and fixed the candidate-condition modal so applying filters selects the filtered candidates in the comparison list. / Phase 16 Market Data ranking の銘柄候補マスタを `data/marketdata/symbol_universe.csv` に移し、UI の銘柄名・属性を CSV から読む loader を追加。「候補条件」modal の適用時に、絞り込み候補が比較リストへ選択反映されるよう修正した。
- 2026-05-17: Synchronized documentation with the current implementation state after Phase 15 and Phase 16 UI work: refreshed README, PROJECT_CONTEXT, roadmap, operations guide, requirements/design/function docs, UI wording, Phase 16 plan, detail-design index/class diagram, and added an Investment Scoring / UI onepager. / Phase 15 と Phase 16 UI 実装後の現在地に合わせて、README、PROJECT_CONTEXT、ロードマップ、運用ガイド、要件・設計・機能設計、UI文言、Phase 16計画、詳細設計index/クラス図を同期し、Investment Scoring / UI onepager を追加した。

- 2026-05-17: Added Research RAG planning documents and synchronized requirements, architecture, functional design, detailed design index, roadmap, UI wording policy, operations guide, README, AGENTS, and project context for local-first IR evidence search and Research Score integration. / Research RAG の計画文書を追加し、local-first なIR根拠検索と Research Score 統合に向けて要件、アーキテクチャ、機能設計、詳細設計index、ロードマップ、UI文言、運用ガイド、README、AGENTS、現在地文書を同期した。

- 2026-05-10: Added a `Symbol search` text filter to the Streamlit Market Data symbol selector so yfinance-compatible candidate tickers can be narrowed by ticker or company-name partial matches while preserving Custom input. / Streamlit Market Data の symbol selector に `Symbol search` テキスト絞り込みを追加し、yfinance 形式の候補 ticker を ticker / company name の部分一致で絞り込めるようにしつつ Custom 入力を維持した。
- 2026-05-10: Added a yfinance-compatible representative symbol selector and adjacent company-name display to the Streamlit Market Data form while keeping custom symbol input available. / Streamlit Market Data form に yfinance 形式の代表銘柄候補 selector と横並びの会社名表示を追加しつつ、custom symbol 入力も維持した。
- 2026-05-10: Improved the Streamlit Forecast / Market Data UI by moving Market Data to the left tab, adding legend-click series visibility for the forecast chart, and deriving forecast reference periods automatically from the fetched period and horizon. / Streamlit Forecast / Market Data UI を改善し、Market Data tab を左側へ移動、forecast chart の凡例クリックによる系列表示切替、取得期間と horizon からの参照期間自動算出を追加した。
- 2026-05-10: Added symbol resolver and market-selection requirements to the beginner-friendly UI roadmap so Japanese equity codes, Yahoo suffixes, and provider-specific symbol normalization are handled deliberately later. / 日本株コード、Yahoo suffix、provider 固有の symbol 正規化を後で意図的に扱えるよう、初心者向け UI roadmap に symbol resolver と市場選択の要件を追加した。
- 2026-05-10: Moved Streamlit `Forecast days` out of the Market Data fetch header and into the forecast result area so changing the horizon recalculates only chart and metric rows from already fetched bars. / Streamlit の `Forecast days` を Market Data 取得ヘッダーから forecast 結果エリアへ移し、horizon 変更時は取得済み bars から chart / metric 行だけを再計算するようにした。
- 2026-05-10: Added `Documents/07_UI_Wording_Policy.md` to define concise Japanese UI wording, chart legend labels, metric explanation tone, and investment-support phrasing for future UI/report work. / 今後の UI / report 作業に向けて、簡潔な日本語 UI 文言、チャート凡例、指標説明の温度感、投資判断補助としての表現方針を定義する `Documents/07_UI_Wording_Policy.md` を追加した。
- 2026-05-10: Replaced the pre-commit Black hook with the local single-process `tools/run_black_check.py` helper and documented that direct multi-file `python -m black --check .` is not the routine check path in this Windows environment. / pre-commit の Black hook を単一プロセスの `tools/run_black_check.py` helper に置き換え、この Windows 環境では複数ファイル対象の `python -m black --check .` を通常確認経路にしないことを明記した。
- 2026-05-10: Improved the Streamlit Market Data forecast view by making the forecast chart primary, adding beginner-friendly model labels and metric summaries, marking the future forecast boundary, and folding provider/feature details into expanders. / Streamlit Market Data の forecast 表示を主役化し、初心者向けのモデル名・指標要約、将来予測の境界表示、provider/feature 補助情報の折りたたみを追加した。
- 2026-05-10: Split the historical work log out of `PROJECT_CONTEXT.md` into `Documents/99_Work_Log.md`, rewrote `PROJECT_CONTEXT.md` as a compact current-state summary, and added a Codex task template. / `PROJECT_CONTEXT.md` から過去作業ログを `Documents/99_Work_Log.md` へ分離し、`PROJECT_CONTEXT.md` を軽量な現在地サマリへ整理し、Codex 用タスクテンプレートを追加した。
- 2026-05-08: Added a `yahoo` opt-in live-provider stub and connected it through the market-data provider factory without importing external provider libraries. / external provider library を import せずに `yahoo` opt-in live-provider stub を追加し、market-data provider factory へ接続した。
- 2026-05-08: Added a Streamlit Market Data preview tab that shows provider metadata, quote rows, OHLCV summary, FX rates, and provider error details for the configured provider. / 設定中 provider の provider metadata、quote rows、OHLCV summary、FX rates、provider error details を表示する Streamlit Market Data preview tab を追加した。
- 2026-05-08: Expanded the Phase 10 completion target to include Streamlit UI confirmation of live-provider data and provider status. / Phase 10 の完了目標を拡張し、live provider の取得データと provider 状態を Streamlit UI で確認できることを含めた。
- 2026-05-08: Added `create_market_data_provider_adapter()` as the configured factory entrypoint for deterministic and future live market-data adapters. / deterministic provider と将来の live market-data adapter の設定済み factory 入口として `create_market_data_provider_adapter()` を追加した。
- 2026-05-08: Added the shared `MarketDataProviderAdapter` protocol and linked planned live-provider adapter metadata to that interface. / 共通 `MarketDataProviderAdapter` protocol を追加し、planned live-provider adapter metadata をその interface に紐づけた。
- 2026-05-08: Started Phase 10 by adding planned live-provider adapter metadata for `yahoo` and `polygon` without importing network-dependent libraries. / network-dependent library を import せずに、`yahoo` と `polygon` の planned live-provider adapter metadata を追加して Phase 10 に着手した。
- 2026-05-08: Checked project-wide consistency after document consolidation and aligned current context/agent guidance with the new roadmap and operations-guide files. / 文書統合後にプロジェクト全体の整合性を確認し、現在地コンテキストと agent 向け方針を新しい roadmap / operations guide 構成に合わせた。
- 2026-05-08: Reorganized `Documents/05_Implementation_Roadmap.md` into a cleaner Japanese structure with current state, completed phases, next roadmap, verification commands, and open items. / `Documents/05_Implementation_Roadmap.md` を、現在地、完了済みフェーズ、次期ロードマップ、検証コマンド、未決事項が見やすい日本語構成へ整理した。
- 2026-05-08: Consolidated post-05 documents by merging API, CSV, manual workflow, UI, external provider, and next-roadmap notes into `Documents/05_Implementation_Roadmap.md` and `Documents/06_MVP_Operations_Guide.md`. / 05 以降の文書を整理し、API、CSV、manual workflow、UI、external provider、次期 roadmap の説明を `Documents/05_Implementation_Roadmap.md` と `Documents/06_MVP_Operations_Guide.md` に統合した。
- 2026-05-08: Documented the next Multi-Model Investment Intelligence roadmap across requirements, system design, functional design, roadmap, README, AGENTS, and project context. / 次期 Multi-Model Investment Intelligence roadmap を、要件定義、システム設計、機能設計、ロードマップ、README、AGENTS、project context に反映した。
- 2026-05-08: Added local CSV downloads for Streamlit rebalance result tables. / Streamlit rebalance 結果テーブル向けのローカル CSV ダウンロードを追加した。
- 2026-05-08: Added a deterministic local ZIP download for Streamlit rebalance JSON and CSV report files. / Streamlit rebalance の JSON と CSV レポートファイルをまとめる deterministic なローカル ZIP ダウンロードを追加した。
- 2026-05-08: Added a deterministic report manifest to the Streamlit rebalance ZIP export. / Streamlit rebalance の ZIP export に deterministic な report manifest を追加した。
- 2026-05-08: Added validated request JSON to the Streamlit rebalance downloads and report ZIP. / Streamlit rebalance の download と report ZIP に validated request JSON を追加した。
- 2026-05-08: Added a human-readable Markdown report summary to Streamlit rebalance downloads and report ZIP. / Streamlit rebalance の download と report ZIP に人が読みやすい Markdown report summary を追加した。
- 2026-05-08: Added allocation-comparison and proposed-trade tables to the Streamlit rebalance Markdown report. / Streamlit rebalance Markdown report に allocation comparison と proposed trade の表を追加した。
- 2026-05-08: Added current-position and target-allocation tables to the Streamlit rebalance Markdown report. / Streamlit rebalance Markdown report に current position と target allocation の表を追加した。
- 2026-05-08: Completed Reporting MVP scope by sharing report rows through `RebalanceReportContext` and documenting the JSON/CSV/Markdown/manifest/ZIP boundary for MVP exports. / `RebalanceReportContext` で report rows を共有し、MVP export の範囲を JSON/CSV/Markdown/manifest/ZIP として文書化して Reporting MVP の範囲を完了扱いにした。
- 2026-05-08: Clarified planned live market-data provider failures with explicit `DataSourceError` details for future opt-in support. / 将来の opt-in 対応に向けて、予定されている live market-data provider の失敗を明示的な `DataSourceError` details で分かるようにした。
- 2026-05-08: Added provider unavailable and timeout domain errors for future live market-data API mapping. / 将来の live market-data API mapping に向けて、provider unavailable と timeout のドメインエラーを追加した。
- 2026-05-08: Added `dataaccess.allow_external_providers` as an explicit opt-in gate before future live provider implementation paths. / 将来の live provider 実装経路へ進む前の明示 opt-in gate として `dataaccess.allow_external_providers` を追加した。
- 2026-05-08: Added structured API response coverage and OpenAPI metadata for live-provider opt-in, unavailable, and timeout failures. / live provider の opt-in、unavailable、timeout 失敗に対する構造化 API レスポンスのカバレッジと OpenAPI metadata を追加した。
- 2026-05-08: Added structured API response tests for provider rate-limit and schema-mismatch failures. / provider rate limit と schema mismatch 失敗に対する構造化 API レスポンステストを追加した。
- 2026-05-08: Centralized market-data provider capability metadata in a registry for future live adapter implementation. / 将来の live adapter 実装に向けて、market-data provider の capability metadata を registry に集約した。
- 2026-05-08: Completed Phase 9 preparation by documenting external provider setup, limitations, failure modes, and offline default behavior. / external provider の setup、制約、failure mode、offline default behavior を文書化して Phase 9 の準備作業を完了扱いにした。
- 2026-05-08: Checked project-wide documentation consistency after Phase 9 and corrected stale status wording. / Phase 9 後にプロジェクト全体のドキュメント整合性を確認し、古い状態表現を修正した。
- 2026-05-07: Added explicit `RebalanceScenarioError` handling for malformed file-backed rebalance scenarios and covered invalid JSON, invalid request schema, and duplicate scenario names with tests. / 壊れた file-backed rebalance scenario 向けに明示的な `RebalanceScenarioError` 処理を追加し、不正 JSON、不正 request schema、重複 scenario 名をテストでカバーした。
- 2026-05-07: Added file-backed rebalance scenarios under `examples/rebalance_scenarios/` and made the Streamlit UI sample selector load them. / `examples/rebalance_scenarios/` に file-backed rebalance scenario を追加し、Streamlit UI の sample selector から読み込むようにした。

- 2026-05-07: Added Black exclude settings for local virtualenv and cache directories, then moved routine local checks to `tools/run_black_check.py` to avoid direct `black --check .` scans. / ローカル仮想環境と cache ディレクトリの Black 除外設定を追加し、その後の通常ローカル確認は `black --check .` 直接実行ではなく `tools/run_black_check.py` に寄せた。

- 2026-05-07: Added cache-free local Black and MVP verification helpers, then covered command construction and file discovery with tests. / cache-free のローカル Black 確認 helper と MVP 確認 helper を追加し、コマンド生成とファイル探索をテストでカバー。

- 2026-05-07: Updated `AGENTS.md` to clarify that diff review and verification are checkpoints, not automatic stopping points, when the implementation direction is already approved. / 実装方針が承認済みの場合、差分確認と検証は自動停止地点ではなくチェックポイントとして扱うよう `AGENTS.md` に明記。

- 2026-05-07: Clarified documentation language policy in `AGENTS.md`: human-facing docs are Japanese-first, while AI-facing operating/context docs are bilingual English/Japanese. / `AGENTS.md` のドキュメント言語方針を明確化し、人向け文書は日本語中心、AI 向け運用・文脈文書は英日併記と定義。

- 2026-05-07: Synchronized README, manual workflow docs, and UI guide with the current deterministic Portfolio-to-Risk MVP. / README、手動確認手順、UI ガイドを現在の deterministic な Portfolio-to-Risk MVP に合わせて同期。

- 2026-05-05: Extended the implementation roadmap through MVP stabilization, CSV/scenario expansion, configurable scenarios, reporting MVP, and explicit opt-in external data provider preparation. / 実装ロードマップを MVP stabilization、CSV/scenario expansion、configurable scenarios、reporting MVP、明示 opt-in の外部データ provider 準備まで拡張。

- 2026-05-05: Rechecked project-wide implementation direction against roadmap and context documents, then removed stale Streamlit/UI next-step wording. / プロジェクト全体の実装方針を roadmap と context 文書に照らして再確認し、古い Streamlit/UI の次ステップ表現を削除。

- 2026-05-05: Added Streamlit sample-symbol explanations and human-readable symbol labels in rebalance result tables. / Streamlit にサンプル銘柄の説明と rebalance 結果テーブル向けの読みやすい銘柄ラベルを追加。

- 2026-05-05: Added Streamlit allocation comparison rows showing current weights, target weights, and drift by symbol. / 銘柄ごとの current weight、target weight、drift を表示する Streamlit allocation comparison 行を追加。

- 2026-05-05: Added a Streamlit AAPL target-weight slider that regenerates deterministic MVP target-allocation JSON. / deterministic な MVP target-allocation JSON を再生成する Streamlit の AAPL target-weight slider を追加。

- 2026-05-05: Added a Streamlit local JSON download for rebalance-check results and covered the payload helper with tests. / Streamlit に rebalance-check 結果のローカル JSON ダウンロードを追加し、payload helper をテストでカバー。

- 2026-05-05: Made Streamlit rebalance sample inputs use sample-specific widget keys so sample switching refreshes form values reliably. / Streamlit rebalance サンプル入力にサンプル別 widget key を使い、サンプル切り替え時にフォーム値が確実に切り替わるようにした。

- 2026-05-05: Checked recent Streamlit UI changes against design documents and synchronized the roadmap, UI guide, and contributor documentation policy. / 最近の Streamlit UI 変更を設計ドキュメントと照合し、roadmap、UI guide、contributor 向けドキュメント方針を同期。

- 2026-05-05: Added deterministic Streamlit rebalance sample selection with default and no-trades scenarios. / Streamlit の rebalance 入力に default と no-trades の決定的なサンプル切り替えを追加。

- 2026-05-05: Added Streamlit UI runtime settings display, shared default request helpers, and deterministic UI helper tests. / Streamlit UI に実行時設定表示、共通デフォルト request helper、決定的な UI helper テストを追加。

- 2026-05-05: Verified repository Markdown files are valid UTF-8 without BOM and documented the encoding check rule in `AGENTS.md`. / リポジトリ内 Markdown が UTF-8 without BOM として正常であることを確認し、文字コード確認ルールを `AGENTS.md` に追記。

- 2026-05-05: Aligned the Streamlit UI helper test expectations with current Risk MVP breach rules and fixed import ordering. / Streamlit UI helper テストの期待値を現在の Risk MVP 違反ルールに合わせ、import 順を修正。

- 2026-05-05: Exposed the Portfolio-to-Risk workflow through `POST /portfolio/rebalance-check` and added deterministic API tests. / `POST /portfolio/rebalance-check` で Portfolio-to-Risk workflow を公開し、決定的な API テストを追加。
- 2026-05-05: Improved Swagger/OpenAPI metadata and added Japanese API specification notes, now consolidated into `Documents/06_MVP_Operations_Guide.md`. / Swagger/OpenAPI メタデータを整備し、日本語 API 仕様メモを追加した。現在は `Documents/06_MVP_Operations_Guide.md` に統合済み。
- 2026-05-05: Added optional YAML settings loading via `SMAI_CONFIG_FILE`, PyYAML dependency, example config, and deterministic config tests. / `SMAI_CONFIG_FILE` による任意の YAML 設定読み込み、PyYAML 依存、設定例、決定的な config テストを追加。
- 2026-05-05: Updated `AGENTS.md` to require beginner-friendly implementation explanations after each work unit. / 各作業単位の完了後に初学者向け説明を行うルールを `AGENTS.md` に追記。
- 2026-05-05: Added `types-PyYAML` to development and pre-commit mypy dependencies so YAML imports have type stubs. / YAML import の型スタブを使えるように、開発依存と pre-commit mypy 依存へ `types-PyYAML` を追加。
- 2026-05-05: Added deterministic CSV market-data provider support for symbols, OHLCV bars, quotes, and USDJPY FX rates. / symbols、OHLCV、quotes、USDJPY FX rates に対応する決定的な CSV market-data provider を追加。
- 2026-05-05: Synchronized current-state documents with implemented APIs/providers and added CSV required-column validation. / 実装済み API/provider に合わせて現在地ドキュメントを同期し、CSV 必須列検証を追加。
- 2026-05-05: Updated `AGENTS.md` to require commit message suggestions after each completed work unit. / 各作業単位の完了後にコミットメッセージ案を提示するルールを `AGENTS.md` に追記。
- 2026-05-05: Added deterministic manual workflow docs, example request, and serverless demo script for `POST /portfolio/rebalance-check`. / `POST /portfolio/rebalance-check` 向けの決定的な手動確認手順、サンプル request、サーバー不要の demo script を追加。
- 2026-05-05: Fixed CI mypy issues for PyYAML imports, FastAPI response metadata typing, and CSV currency parsing. / PyYAML import、FastAPI response metadata の型、CSV currency parsing に関する CI mypy 問題を修正。
- 2026-05-05: Added local sample CSV market-data files, `config/csv_example.yaml`, and CSV-provider manual workflow coverage. / ローカル CSV market-data サンプル、`config/csv_example.yaml`、CSV provider 手動確認フローのカバレッジを追加。
- 2026-05-05: Added a minimal Streamlit UI for the Portfolio-to-Risk rebalance-check workflow and UI helper tests. / Portfolio-to-Risk rebalance-check workflow 向けの最小 Streamlit UI と UI helper テストを追加。
- 2026-04-29: Added `AGENTS.md` and `PROJECT_CONTEXT.md` as root-level shared context documents. / ルート共有文書として `AGENTS.md` と `PROJECT_CONTEXT.md` を追加。
- 2026-04-29: Updated both root documents to bilingual English/Japanese format. / ルート文書2点を英日併記に更新。
- 2026-04-29: Updated `AGENTS.md` to require diff-first review and work-log updates per task unit. / `AGENTS.md` に差分先出しレビューと作業単位ごとのログ更新ルールを追記。
- 2026-04-29: Started Phase 3 Risk MVP by adding `backend/risk/` with minimal `RiskService` and decision tests. / `backend/risk/` の最小 `RiskService` と判定テストを追加し、Phase 3 Risk MVP に着手。
- 2026-04-29: Exposed Risk MVP through `POST /risk/pre-trade-check` with deterministic API tests. / `POST /risk/pre-trade-check` で Risk MVP を公開し、決定的な API テストを追加。
- 2026-04-29: Synchronized project documents with the implemented Risk service and API state. / 実装済みの Risk サービスと API の状態に合わせてドキュメントを同期。
- 2026-04-29: Hardened Risk API error-response tests for data-source and computation failures. / データソース失敗と計算失敗に対する Risk API エラー応答テストを強化。
- 2026-04-29: Started Phase 4 Portfolio MVP with deterministic snapshot valuation and no-solver rebalance proposals. / deterministic な評価スナップショットと solver なしのリバランス提案で Phase 4 Portfolio MVP に着手。
- 2026-04-29: Connected Portfolio rebalance proposals to Risk pre-trade checks through a service-level workflow. / service-level workflow で Portfolio リバランス提案を Risk 取引前判定へ接続。
- 2026-05-08: Added `SMAI_REBALANCE_SCENARIO_DIR` so the Streamlit rebalance UI can load file-backed scenarios from a configured local directory. / `SMAI_REBALANCE_SCENARIO_DIR` を追加し、Streamlit rebalance UI が設定されたローカルディレクトリから file-backed scenario を読み込めるようにした。
- 2026-05-08: Added explicit errors for missing or non-directory `SMAI_REBALANCE_SCENARIO_DIR` paths while preserving the default fallback scenarios. / `SMAI_REBALANCE_SCENARIO_DIR` の指定先が存在しない場合やディレクトリでない場合の明示エラーを追加しつつ、既定 scenario の fallback は維持した。
- 2026-05-08: Added optional rebalance scenario descriptions and displayed them under the Streamlit sample selector. / 任意の rebalance scenario 説明を追加できるようにし、Streamlit の sample selector 下に表示するようにした。
- 2026-05-08: Localized the default user-facing rebalance scenario descriptions to Japanese. / 既定のユーザー向け rebalance scenario 説明を日本語化した。
- 2026-05-08: Clarified that future roadmap phases affecting UI behavior must include UI-level completion criteria, and that external-provider features should prefer live-data UI confirmation when available. / 今後のロードマップで UI に影響するフェーズは UI 上の確認を完了条件に含め、外部 provider 機能では可能な限り live data による UI 確認を優先する方針を明確化した。
- 2026-05-08: Expanded the Yahoo market-data provider from an opt-in stub to a `yfinance`-backed live adapter for OHLCV, quotes, and USDJPY FX, with deterministic fake-provider tests and Streamlit Market Data preview coverage. / Yahoo market-data provider を opt-in stub から `yfinance` を使う live adapter へ拡張し、OHLCV、quote、USDJPY FX の取得、deterministic fake-provider test、Streamlit Market Data preview の検証を追加した。
- 2026-05-09: Updated Streamlit date input defaults so rebalance `As of` and Market Data `End` use the current date, while Market Data `Start` defaults to seven days before today. / Streamlit の日付入力初期値を更新し、rebalance の `As of` と Market Data の `End` は現在日付、Market Data の `Start` は現在日付の 7 日前を使うようにした。
- 2026-05-09: Started Feature Store Lite by adding a `FeatureSnapshot` contract, `FeatureBuilder.build_feature_snapshot()`, and Streamlit Market Data feature snapshot rows with provider/version/missing metadata. / `FeatureSnapshot` contract、`FeatureBuilder.build_feature_snapshot()`、provider/version/missing metadata 付きの Streamlit Market Data feature snapshot 行を追加し、Feature Store Lite に着手した。
- 2026-05-09: Added rolling recent OHLCV rows to the mock market-data provider so current-date Streamlit defaults can show an OHLCV summary without losing fixed historical fixture rows. / Streamlit の現在日付デフォルトでも OHLCV summary を表示できるように、固定の historical fixture 行を残したまま mock market-data provider に直近日付の rolling OHLCV 行を追加した。
- 2026-05-09: Extended Feature Store Lite snapshots with return, momentum, drawdown, volatility, ADV, and data-completeness fields, and exposed those values in the Streamlit Market Data feature snapshot table. / Feature Store Lite snapshot に return、momentum、drawdown、volatility、ADV、data completeness を追加し、Streamlit Market Data の feature snapshot table で確認できるようにした。
- 2026-05-09: Formatted Streamlit Feature Snapshot ratio fields as percentages for easier UI inspection. / Streamlit Feature Snapshot の比率系項目を UI で読みやすい percentage 表示に整えた。
- 2026-05-09: Updated `AGENTS.md` current-state wording so deterministic local defaults and explicit opt-in live-provider support are both represented accurately. / deterministic な local default と明示 opt-in の live-provider support の両方が正確に伝わるように、`AGENTS.md` の現在地表現を更新した。
- 2026-05-10: Added Feature Store Lite data-quality judgement to `DailySnapshot` / `FeatureSnapshot`, computed `OK` / `WARN` / `BLOCK` from missing features and data completeness, and exposed the result in the Streamlit Market Data Feature Snapshot table. / `DailySnapshot` / `FeatureSnapshot` に Feature Store Lite の data quality 判定を追加し、欠損特徴量と data completeness から `OK` / `WARN` / `BLOCK` を計算して Streamlit Market Data の Feature Snapshot 表で確認できるようにした。
- 2026-05-10: Confirmed that direct multi-file `python -m black` can leave worker processes stuck in the current local PowerShell environment, stopped the leftover processes, and aligned CI/setup docs with the cache-free `tools/run_black_check.py` helper. / 現在のローカル PowerShell 環境では複数ファイル指定の `python -m black` が worker process を残して固まる場合があることを確認し、残存 process を停止したうえで、CI と setup docs を cache-free の `tools/run_black_check.py` helper に合わせた。
- 2026-05-10: Added provider-level fundamentals through `FundamentalSnapshot` and `fetch_fundamentals()`, wired `dividend_yield` and `market_cap_jpy` into Feature Store Lite, and exposed those fields in the Streamlit Market Data Feature Snapshot table. / `FundamentalSnapshot` と `fetch_fundamentals()` で provider-level fundamentals を追加し、Feature Store Lite に `dividend_yield` と `market_cap_jpy` を接続して Streamlit Market Data の Feature Snapshot 表で確認できるようにした。
- 2026-05-10: Started Screening Score MVP by adding `ScreeningService`, explainable score breakdowns for momentum, liquidity, risk, and data quality, and Streamlit Market Data ranking rows. / `ScreeningService`、momentum、liquidity、risk、data quality の説明可能な score breakdown、Streamlit Market Data の ranking 行を追加して Screening Score MVP に着手した。
- 2026-05-10: Exposed Screening Score MVP through `POST /screening/score` with deterministic API coverage for ranked score breakdowns. / `POST /screening/score` で Screening Score MVP を公開し、ranking と score breakdown の deterministic API テストを追加した。
- 2026-05-10: Added Streamlit Screening Score JSON / CSV downloads so ranking, sub-scores, and reasons can be saved from the UI. / Streamlit Screening Score に JSON / CSV download を追加し、ranking、sub score、理由を UI から保存できるようにした。
- 2026-05-10: Added beginner-friendly Screening Score summaries and Japanese reason labels to the service, API, Streamlit preview, and JSON / CSV exports. / Screening Score の summary と日本語 reason label を初心者向けに追加し、service、API、Streamlit preview、JSON / CSV export で確認できるようにした。
- 2026-05-10: Changed the Streamlit Market Data Screening Score preview to score only the input symbol, while keeping multi-symbol ranking available through `POST /screening/score`. / Streamlit Market Data の Screening Score preview は入力銘柄だけを score 表示するように変更し、複数銘柄 ranking は `POST /screening/score` 側に残した。
- 2026-05-10: Documented that multi-symbol ranking UI should be designed in the beginner-friendly UI phase instead of the current Market Data preview. / 複数銘柄 ranking UI は現在の Market Data preview ではなく、初心者向け UI phase で設計する方針として文書化した。
- 2026-05-10: Started Forecast Lab Baseline by adding deterministic naive, moving-average, and momentum forecast models with walk-forward MAE, RMSE, and direction-accuracy metrics. / deterministic な naive、moving-average、momentum forecast model と walk-forward の MAE、RMSE、direction accuracy metrics を追加して Forecast Lab Baseline に着手した。
- 2026-05-10: Added Streamlit Market Data chart rows for selected-symbol close prices, baseline forecast lines, and model-level forecast metrics. / Streamlit Market Data に、選択銘柄の終値 chart、baseline forecast line、model 別 forecast metrics を表示する行を追加した。
- 2026-05-10: Improved the Forecast chart UI by rendering actual closes as solid lines and forecast models as dashed lines, added Market Data provider selection, and made recent mock OHLCV rows less linear. / Forecast chart UI を改善し、実績終値を実線、forecast model を破線で表示するようにした。Market Data provider 選択を追加し、直近 mock OHLCV 行を単調すぎない系列にした。
- 2026-05-10: Made Yahoo live-provider failures easier to diagnose in the Streamlit Market Data tab by showing the error code, message, and JSON details immediately after a failed fetch. / Yahoo live-provider の取得失敗を Streamlit Market Data tab で診断しやすくするため、失敗直後に error code、message、JSON details を表示するようにした。
- 2026-05-10: Added `POST /forecast/evaluate` for deterministic baseline forecast evaluations and aligned local Ruff checks with `backend ui tests`. / deterministic な baseline forecast evaluation を返す `POST /forecast/evaluate` を追加し、local Ruff check の対象を `backend ui tests` に揃えた。
- 2026-05-10: Added Streamlit forecast horizon selection for 1-30 days, aligned chart forecast dates and walk-forward metrics with the selected horizon, and documented the UI workflow. / Streamlit で forecast horizon を 1〜30 日から選べるようにし、chart の予測日付と walk-forward metrics を選択 horizon に合わせ、UI workflow を文書化した。
- 2026-05-10: Added a dedicated roadmap phase for beginner-friendly UI design, including watchlists, symbol search, Japanese score explanations, comparison flows, and UI verification criteria. / watchlist、銘柄検索、日本語の score 説明、比較 flow、UI 確認観点を含む初心者向け UI design の専用 roadmap phase を追加した。
- 2026-05-10: Added a dedicated roadmap phase for a low-cost AI assistant experience that starts with deterministic rule-based explanations and leaves optional LLM adapters for later. / deterministic な rule-based 説明から始め、optional LLM adapter は後から差し替えられる形にする低コスト AI assistant 体験の専用 roadmap phase を追加した。
- 2026-05-10: Adjusted the Streamlit Forecast chart so clicking a price/model legend item greys out only that legend item and its matching series, clicking it again restores it, and the chart body is about 1.5x taller for easier inspection. / Streamlit Forecast chart で価格・モデル凡例をクリックしたとき、その凡例項目と対応する系列だけを薄くし、再クリックで戻るように調整し、チャート本体を約 1.5 倍の高さにして確認しやすくした。
- 2026-05-10: Changed the Forecast chart legend selection to support multiple inactive price/model series at the same time instead of reactivating the previously inactive series when another legend item is clicked. / Forecast chart の凡例選択を、別の凡例項目をクリックしても以前の非活性系列が勝手に戻らず、複数の価格・モデル系列を同時に非活性にできる挙動へ変更した。
- 2026-05-10: Consolidated the Streamlit Market Data symbol picker from separate search and candidate widgets into one searchable `Symbol` dropdown, keeping adjacent company-name display for the selected candidate. / Streamlit Market Data の symbol picker を search と candidate の2要素から、検索可能な1つの `Symbol` プルダウンへ統合し、選択候補の会社名表示は横に残した。
- 2026-05-10: Improved Forecast chart readability by changing successful Market Data fetch feedback to a transient toast, reducing persistent explanatory banners, grouping forecast controls with the chart header, and applying explicit dark chart / legend styling. / Market Data 取得成功の表示を一時的な toast に変更し、常設の説明帯を減らし、予測期間コントロールをチャート見出し付近へ整理し、チャートと凡例に明示的なダーク背景スタイルを適用して Forecast chart の視認性を改善した。
- 2026-05-10: Moved the Forecast chart legend into a right-side panel with explicit dark styling, kept the main chart responsive, and included a compact actual/forecast line-style legend in the same panel. / Forecast chart の凡例を右側パネルへ移動し、明示的なダーク背景スタイルを付け、チャート本体は横幅に追従するよう維持し、実績/予測の線種凡例も同じパネル内にまとめた。
- 2026-05-10: Changed the Streamlit Market Data provider UI default to `yahoo` and made `Symbol` a free text input again while keeping partial-match candidate completion as an optional helper. / Streamlit Market Data の provider UI 既定値を `yahoo` に変更し、`Symbol` は候補にない ticker も指定できる自由入力へ戻しつつ、部分一致する候補補完を補助として残した。
- 2026-05-10: Reverted the Streamlit Market Data `Symbol` control from free text plus matching candidates back to the single searchable candidate dropdown, while keeping the `yahoo` provider UI default. / Streamlit Market Data の `Symbol` control を自由入力 + 候補補完から、検索可能な単一候補プルダウンへ戻し、provider UI 既定値 `yahoo` は維持した。
- 2026-05-10: Expanded representative Streamlit Market Data symbol candidates across Japanese and US equities / ETFs, and added optional yfinance `Search` completion for the user's `Symbol search` query with deterministic fallback to representative candidates. / Streamlit Market Data の代表 symbol 候補を日本株・米国株・ETF で拡充し、ユーザーの `Symbol search` 入力に対して任意の yfinance `Search` 補完を追加しつつ、失敗時は代表候補だけで動く deterministic fallback を維持した。
- 2026-05-10: Added currency-aware y-axis labeling to the Forecast chart and tightened the chart / legend widths so the right-side legend remains visible within the Streamlit page. / Forecast chart の縦軸に通貨を含む価格ラベルを追加し、右側凡例が Streamlit 画面内に収まりやすいようチャート本体と凡例の横幅を調整した。

## 2026-05-15

- `Documents/future_roadmap/` の将来構想を、`Documents/05_Implementation_Roadmap.md` に実装可能な粒度の Future Implementation Candidates として追記。
- Chat AI Assistant MVP、News & Sentiment Intelligence MVP、Assistant x News Integration を、Goal / Scope / Non-goals / Implementation slices / Acceptance criteria の形に整理。
- LLM 活用を Optional LLM Adapter と LLM-assisted Report Generation に分離し、deterministic/local-first を維持した実装順として `Documents/05_Implementation_Roadmap.md` に追記。
- Forecast Metrics の JSON / CSV download helper と Streamlit Market Data tab の download button を追加し、Phase 13 の forecast result export を完了扱いに更新。
- Phase 14 の入口として、複数 forecast model の median forecast、予測レンジ、model agreement を計算する Forecast Summary を追加し、Streamlit Market Data tab で確認できるようにした。
- Forecast Model Registry Lite を追加し、API / UI の forecast model 選択と表示ラベルを registry 経由に寄せた。
- Streamlit Market Data tab の各結果 section で、見出しとは別に評価中の symbol / 銘柄名を小さく表示するようにした。
- Forecast Summary に複数 baseline model の平均予測である ensemble forecast を追加した。
- Forecast Summary の model agreement を Screening Score の forecast_score / forecast_reason として接続し、Phase 14 の scoring 接続を完了扱いにした。

## 2026-05-16

- Completed Phase 15 implementation by adding configurable `scoring.weights`, validating weight totals, connecting the existing Screening risk score as the first risk signal, and marking live-provider UI confirmation as environment-dependent.
- Polished the Streamlit UI by changing Investment Score from a wide one-row table into compact metrics with details/downloads, and formatting rebalance allocation weights as percentages.
- Added Market Data tab Investment Score preview rows and JSON / CSV downloads, using the Phase 15 scoring service while keeping the output framed as decision support rather than buy/sell advice.
- Added `POST /scoring/investment-score` so the Phase 15 Investment Score contract can be used from FastAPI with deterministic API/OpenAPI tests and operations-guide documentation.
- Added the first Phase 15 backend slice: `backend/scoring` now defines a deterministic Investment Score contract/service that combines Screening Score, forecast agreement, and data quality, with tests for data quality warnings and model disagreement reasons.
- Phase 14 を implementation complete として整理し、Phase 15 の最初の実装スライスを `backend/scoring` の Investment Score contract と deterministic tests に定義した。
- Started Phase 16 by splitting the Streamlit Market Data tab into `銘柄コックピット` / `銘柄ランキング`, moving Investment Score into the cockpit summary, adding a score breakdown chart, and adding deterministic selected-symbol ranking.
- Continued Phase 16 by moving Rebalance JSON inputs into advanced input, adding Rebalance Cockpit summary flow, percentage target weights, allocation comparison chart, and beginner-friendly risk breach confirmation points.
- Connected Phase 16 ranking to the single-symbol cockpit by letting selected ranking symbols pass their symbol/provider into the cockpit state for follow-up review.
- Added deterministic ranking preference presets for balance, forecast agreement, data quality, and lower-risk emphasis by reweighting existing Investment Score components in the UI.
- Moved the single-symbol cockpit to a chart-first layout and added beginner-friendly forecast chart summary text for model agreement, forecast spread, compared model count, and the best RMSE model.
- Documented the agreed Phase 16 UI improvement direction in `Documents/08_Phase16_UI_Improvement_Plan.md`, including chart/score layout, ranking candidate filters, Fetch-before/after condition separation, and staged implementation order.
- Added Fetch-before ranking candidate filters for purpose, period preset, market, asset type, currency, dividend category, simplicity, theme, keyword, and display count using static symbol metadata / curated tags.
- Changed ranking candidate filters to open in a modal, broadened curated tags across the current representative symbol DB, and added company names to Investment Score ranking rows.
- Fixed ranking filter application so the comparison selector resets per condition set, and added modal candidate counts/examples plus Japanese alias keyword matching.
- Replaced the ranking investment-purpose control with database-style filters for minimum dividend yield, market-cap tier, ETF index family, and max expense ratio, backed by curated symbol metadata.

## 2026-05-17 - Final documentation sync pass

- Synced detail design One-Pagers 04-1 through 04-6 with current implementation status.
- Marked Execution / broker order sending as deferred and Portfolio optimizer solver as future scope.
- Updated Detail Design README, AGENTS.md, setup guide, and Codex task template to match Phase 15 complete / Phase 16 UI improving / Research RAG planned status.
- Added implementation-status note to the class diagram reference and clarified roadmap appendix as future candidates.

## 2026-05-17 - Phase 16 Rebalance Cockpit persistence

- Kept the latest Rebalance Cockpit result in Streamlit session state so the summary, allocation comparison, risk confirmation points, and downloads remain visible across reruns after a successful check.
- Added deterministic UI helper tests for reading the stored rebalance result/request and ignoring incomplete session state.

## 2026-05-18 - Phase 18 Symbol universe source import

- Added a local source-import path for `symbol_universe.csv`, including append-only default merge, optional existing-symbol update, validation-before/write, and manifest output.
- Added a JPX ETF seed source and imported 8 domestic ETF rows into the ranking candidate master without adding network dependency.
- Extended source import for JPX-style numeric codes by adding import defaults and `.T` suffix normalization, then imported 24 domestic stock seed rows.
- Documented the SBI Securities based ranking-universe policy, including initial target products, default exclusions, metadata columns, and the next Phase 18 implementation slice.

## 2026-05-18 - Phase 18 SBI ranking universe policy

- Added SBI policy columns to `symbol_universe.csv` and schema, with conservative defaults for the current 127-row seed universe.
- Added the default ranking-universe policy helper and wired it into ranking candidate extraction before provider fetch.
- Kept `tradability=unknown` eligible for initial ranking while excluding explicit out-of-scope products, not-tradable rows, inactive rows, non-SBI rows, leveraged rows, and inverse rows.
- Added deterministic tests for the policy helper, schema fields, CSV validation, and ranking candidate filtering.
- Tuned the SBI symbol master acquisition policy documentation to match the current implementation: local source CSV / master first, no direct SBI scraping, future repository separation only when the existing symbol-universe helpers become too broad.
- Added source profiles for SBI US stock, SBI US ETF, and mutual fund seeds, plus seed CSV files and import tests for SBI policy defaults, leveraged/inverse ETF flags, and minimal mutual-fund metadata.
- Wrote the SBI US stock / ETF / mutual fund seeds into `symbol_universe.csv`, increasing the candidate master to 146 rows with stock, ETF, mutual fund, and ADR coverage.
- Connected mutual-fund metadata to the ranking condition UI, using management style, trust fee, NISA eligibility, and installment availability as pre-fetch filters.
- Added a ranking UI guard so mutual-fund placeholder symbols stay visible as candidates but are not sent to price-provider ranking fetch until fund price/ranking support is implemented.
- Re-scoped the MVP ranking universe to stock / ETF only, hiding mutual funds from the main ranking UI and keeping mutual-fund seed/profile data as a future extension rather than an MVP dependency.

## 2026-05-19 - Phase 18 ETF region filtering fix

- Fixed ranking candidate normalization so domestic ETF rows keep their `jp` market instead of being forced to `us`.
- Added a deterministic ranking UI helper test that confirms domestic ETF and US ETF candidates are separated by region.

## 2026-05-19 - Phase 18 source profile expansion

- Added JPX stock / ETF source profiles so local JPX seed import can use named defaults instead of repeated command-line default arguments.
- Added a NISA eligibility source profile that updates only NISA metadata fields and preserves existing symbol name, market, product type, and currency.
- Added deterministic tests for JPX profile defaults, NISA-only update behavior, and the import command `--source-profile nisa_eligibility --update-existing` path.

## 2026-05-19 - Phase 18 NISA seed integration

- Added `nisa_eligibility_seed.csv` and imported 31 existing stock / ETF rows into `symbol_universe.csv` with NISA metadata.
- Added the NISA pre-fetch condition to the ranking detail panel and connected it to ranking filter state/signature.
- Strengthened update-only source import so NISA metadata sources cannot append unknown symbols as incomplete master rows.
- Excluded commodity-themed ETF rows from the default MVP ranking universe while keeping them in the local master for metadata coverage.

## 2026-05-19 - Ranking condition wording polish

- Renamed the ranking purpose control label to `重視して並べ替え` so it is clear that it changes display order, not candidate eligibility.
- Added short detail-panel caption text to distinguish candidate filters from ranking-order settings.
- Removed the risk selector from pre-fetch ranking detail conditions because period-based price movement belongs in ranking results and score breakdown after data retrieval.

## 2026-05-19 - Phase 18 stock ETF universe expansion

- Expanded local JPX stock / ETF, SBI US stock, and SBI US ETF source seeds and imported them into `symbol_universe.csv`.
- Increased the local candidate master to 227 rows: stock 172, ETF 49, mutual fund 4, ADR 2.
- Kept mutual funds as future-extension metadata and kept MVP ranking focused on stock / ETF rows through the existing ranking-universe policy.

## 2026-05-19 - Phase 18 JPX listed stock source builder

- Added `tools/build_symbol_universe_source.py` and a JPX listed-stock builder that converts official raw Excel/CSV rows into SMAI source CSV rows.
- Added the `jpx_listed_stock` import profile so generated JPX domestic stock sources can be imported with `.T` symbol normalization and conservative SBI policy defaults.
- Added deterministic tests for JPX listed-stock row mapping, ETF/REIT skip behavior, and the builder CLI dry-run/write paths.

## 2026-05-19 - Phase 18 SBI US source builders

- Extended `tools/build_symbol_universe_source.py` with `sbi_us_stock` and `sbi_us_etf` source builders for local SBI raw CSV/Excel files.
- Added US ticker normalization, stock sector/theme mapping, ETF index-family inference, fee percent normalization, and leveraged/inverse ETF flag detection.
- Documented the SBI raw-file-to-source workflow while keeping official-site auto-download and scraping outside the normal deterministic path.

## 2026-05-19 - Phase 18 JPX ETF source builder

- Added a `jpx_etf` source builder for local JPX ETF / ETN raw CSV/Excel files.
- Added ETF/ETN scope detection, `.T` symbol output, index-family inference, trust-fee percent normalization, commodity / REIT theme mapping, and leveraged/inverse/ETN flags.
- Documented the JPX ETF raw-file-to-source workflow and kept official download automation outside the normal deterministic path.

## 2026-05-19 - Phase 18 NISA eligibility source builder

- Added a `nisa_eligibility` source builder for local NISA raw CSV/Excel files.
- Normalized domestic 4-digit codes to `.T` symbols and mapped growth / tsumitate / both / none eligibility into canonical NISA metadata fields.
- Kept ambiguous generic NISA rows as `unknown` rather than inferring a category that the source did not provide.

## 2026-05-19 - Ranking filter stale state fix

- Scoped ranking candidate filters to the detail conditions visible for the selected product / region.
- Prevented hidden ETF filters such as benchmark index, expense ratio, and complexity from excluding stock candidates after switching product type.
- Prevented hidden stock filters such as industry/theme, market cap, PER, PBR, and ROE from excluding ETF candidates after switching product type.
- Added regression tests for candidate rows and filter signatures with stale product-specific filter state.
- Pruned stale selection labels against the current candidate list and hid stale ranking results when the visible selection no longer matches the stored result source.

## 2026-05-21 - Phase 18 JPX NISA ETF/ETN source import

- Added support for JPX growth-NISA Excel files whose headers include furigana such as `銘柄コードメイガラ`.
- Extended JPX ETF/ETN detection for full-width `ＥＴＦ` / `ＥＴＮ` and commodity labels such as gold/silver variants.
- Built `jpx_etf_nisa_growth_20260521.csv` and `nisa_eligibility_jpx_etf_20260521.csv` from `jpx_etf_20260521_NISA.xlsx`.
- Imported 26 new JPX NISA ETF/ETN rows and updated 27 rows with `metadata_source=jpx_nisa_growth` NISA growth metadata.
- Increased the candidate master to 3,898 rows: stock 3,817, ETF 75, mutual fund 4, ADR 2.
- Kept PDF raw files outside the routine import path; use Excel/CSV/source CSV for deterministic imports.

## 2026-05-21 - Ranking detail condition coverage

- Extended ranking detail labels so all current `theme`, `sector`, `index_family`, and `market_cap_tier` values in `symbol_universe.csv` have UI choices.
- Changed the stock `業種/テーマ` condition to match `theme`, `sector`, or `tags`, so JPX-derived sector classifications such as industrial/materials/real estate can be used.
- Mapped JPX listed-stock `規模区分` into `market_cap_tier` and updated JPX listed-stock rows in `symbol_universe.csv`.
- Added regression tests for JPX market-cap filtering, sector filtering, and ETF index-family label coverage.

## 2026-05-21 - Ranking metadata coverage and update profile

- Added a `ranking_metadata` source profile for updating existing symbols' ranking filter metadata without changing name, market, or asset type.
- Added source aliases for data-side ranking metadata such as `pe_ratio`, `price_to_book`, `roe`, `dividend_yield`, and `risk`.
- Added `ranking_metadata_template.csv` as a safe header-only template for confirmed PER/PBR/ROE/dividend-yield imports.
- Added `tools/check_symbol_universe_metadata_coverage.py` and generated `data/marketdata/symbol_universe_metadata_coverage.json` as the current coverage baseline.
- Documented that JPX listed-stock imports provide scale classification for `market_cap_tier`, while PER/PBR/ROE/dividend yield require confirmed supplemental sources or explicit opt-in metadata refresh.

## 2026-05-21 - Scoped metadata refresh

- Added scoped options to `tools/refresh_symbol_universe_metadata.py`: `--symbols`, `--asset-type`, `--market`, `--metadata-source`, `--missing-any`, and `--limit`.
- Added manifest `selection` details so live metadata refresh runs record which rows were targeted.
- Avoided double provider calls during metadata refresh validation, which matters for opt-in live providers such as Yahoo.

## 2026-05-21 - Yahoo metadata refresh for JPX stocks

- Ran a 50-row Yahoo metadata refresh dry-run for JPX listed-stock rows, fixed sector/theme normalization, and confirmed validation stays clean before writing.
- Refreshed JPX listed-stock additions plus the older JPX stock seed rows with explicit `--provider yahoo --allow-live`, applying metadata to 3,701 stock rows without validation errors or per-symbol failures.
- Hardened Yahoo metadata normalization so non-finite, invalid, or negative numeric values are skipped instead of breaking the full refresh.
- Changed the Yahoo OHLCV coverage check default to filter by asset type / market instead of the pre-refresh `jpx_listed_stock` metadata source.
- Regenerated `data/marketdata/symbol_universe_metadata_coverage.json`; stock coverage is now dividend yield 3,817/3,817, PBR 3,793/3,817, ROE 3,636/3,817, and PER 3,499/3,817.

## 2026-05-21 - SBI official HTML and JPX REIT source import

- Added CP932 HTML handling for SBI official US stock / ETF raw pages and a `jpx_reit` source builder/profile for JPX listed REIT HTML.
- Built `sbi_us_stock_20260521.csv`, `sbi_us_etf_20260521.csv`, and `jpx_reit_20260521.csv` from local official raw files.
- Imported 4,293 SBI US stock rows, 607 SBI US ETF rows, and 58 JPX REIT rows into `symbol_universe.csv`.
- Reapplied IMAJ NISA listed-fund metadata after REIT import; 57 REIT rows gained NISA growth metadata, while 5 infrastructure/other rows remain update-only failures.
- Kept REIT rows and leveraged/inverse ETF rows stored in the local master but excluded from the default MVP ranking universe.

## 2026-05-21 - SBI US coverage and metadata refresh

- Ran live Yahoo OHLCV coverage checks for the SBI official US stock / ETF additions and stored JSON/CSV outputs under `data/marketdata/live_checks/`.
- Confirmed US stock coverage at 4,240/4,293 and US ETF coverage at 593/607 for the 2026-05-12 to 2026-05-20 period; all failures were short-period `YAHOO-NO-BARS`.
- Refreshed SBI US stock metadata with explicit `--provider yahoo --allow-live`, applying metadata to 4,265 stock rows after a successful 50-row write check.
- Refreshed SBI US ETF metadata with explicit `--provider yahoo --allow-live`, applying metadata to 607 ETF rows.
- Fixed Yahoo metadata dividend-yield normalization so yfinance `dividendYield` is treated as a percentage value, while `trailingAnnualDividendYield` remains ratio-to-percent fallback; re-ran the US stock / ETF refresh after the fix.
- Normalized SBI source class-share symbols `BRKB` / `UHALB` to Yahoo-compatible `BRK-B` / `UHAL-B`, kept the original source forms as aliases, and confirmed the corrected symbols with a 2/2 Yahoo coverage retry.
- Regenerated `data/marketdata/symbol_universe_metadata_coverage.json`; stock coverage is now dividend yield 8,033/8,081, PBR 7,630/8,081, ROE 7,466/8,081, and PER 7,457/8,081. ETF dividend-yield coverage is now 601/1,034 and ETF expense-ratio coverage remains 1,013/1,034.

## 2026-05-22 - ETF metadata enrichment and Yahoo failure analysis

- Added deterministic ETF metadata enrichment for index-family inference and existing Yahoo ETF expense-ratio scale correction.
- Expanded ETF index-family values for Dow Jones, emerging markets, dividend, REIT, bond, commodity, and sector/theme categories.
- Ran ETF metadata enrichment against `symbol_universe.csv`; ETF index-family coverage improved to 639/1,034 and 594 Yahoo ETF expense-ratio values were corrected from over-scaled values.
- Added saved Yahoo coverage failure analysis for SBI US stock / ETF checks. Current SBI US stock failures are 51 no-bars/Yahoo-unsupported plus 2 resolved aliases; current SBI US ETF failures are 2 leveraged exclusions plus 12 rows requiring market-specific symbol mapping or a non-Yahoo source.

## 2026-05-22 - ETF override mapping and provider symbol support

- Added `symbol_universe_etf_metadata_overrides.csv` for ETF rows that need issuer/official-source confirmation instead of name-only inference.
- Added optional `yahoo_symbol` metadata so display/source symbols can stay stable while Yahoo requests use mapped provider tickers.
- Curated the current failed SBI US ETF coverage set into 3 leveraged default exclusions and 11 Yahoo symbol mappings.
- Re-ran ETF metadata enrichment and coverage aggregation; ETF index-family coverage is now 858/1,034, with 176 rows left for official index / issuer confirmation.
- Wired Yahoo provider symbol mapping into ranking and rebalance preview fetch paths, then remapped returned bars/fundamentals back to display symbols for downstream scoring.

## 2026-05-22 - Official-source NISA and ETF index cleanup

- Backfilled stock `investment_style` to `lump_sum` for all 8,081 stock rows and changed JPX stock import defaults to keep future stock imports aligned.
- Extended ETF enrichment so local JPX / IMAJ / SBI official source CSVs reconcile ETF NISA categories without name-based inference; ETF NISA is now 563 growth / 471 none / 0 unknown.
- Expanded deterministic ETF index-family inference from official index/name/alias text and brought ETF `index_family` coverage to 1,034/1,034.
- Regenerated `symbol_universe_metadata_coverage.json`; remaining stock gaps are provider/source-dependent: risk band 1,850, market-cap tier 39, and dividend yield/category 48.

## 2026-05-23 - Documentation sync for Phase 16 UI and symbol metadata status

- Synchronized `PROJECT_CONTEXT.md`, roadmap, operations guide, UI wording policy, and Phase 16 UI plan with the current ranking/cockpit symbol-detail modal behavior.
- Documented the cockpit `銘柄データを見る` placement, wrapped date controls, and post-fetch `投資判断メモ`.
- Documented the ranking modal performance fix that reuses a symbol lookup map instead of repeatedly scanning the symbol master while building display rows.
- Updated verification guidance to match CI-style `ruff check .` and `mypy .`.

## 2026-05-23 - Phase 18 completion boundary

- Marked Phase 18 symbol universe / metadata refresh as implementation-complete in roadmap-facing docs.
- Moved ongoing NISA / ETF / stock metadata source refreshes, remaining provider/source metadata gaps, and additional live `yahoo_symbol` smoke checks into operational maintenance instead of Phase 18 completion blockers.
- Kept confirmed-source-only metadata updates as the standing rule: blanks remain blank until an explicit opt-in refresh or verified source provides values.

## 2026-05-23 - Ranking sort logic uses symbol metadata

- Updated ranking sort profiles so `配当重視` / `成長重視` / `割安重視` / `安定重視` / `トレンド重視` map to purpose-specific evaluation profiles instead of only reweighting the original four score columns.
- Added `database_fit_score` and `metadata_confidence_score` to ranking reweighting. These use Phase 18 symbol metadata such as NISA, market-cap tier, dividend yield/category, PER/PBR/ROE, risk band, ETF expense ratio, complexity, metadata source, and metadata date.
- Reorganized the ranking screen header into `比較対象` and `評価条件`, moving the sort condition beside period/provider controls.
- Added visible `DB適合` and `DB信頼度` columns to ranking results and refreshed ranking notes to explain that the order is a decision-support review priority, not a buy/sell recommendation.

## 2026-05-23 - Ranking CSV and sort control placement fix

- Fixed ranking CSV download after metadata-aware sorting by adding `database_fit_score`, `metadata_confidence_score`, and `ranking_profile` to the stable Investment Score CSV field list.
- Moved the ranking sort control beside the `ランキング作成` button so the sort profile is chosen at the point where the user runs or re-views the ranking result.

## 2026-05-23 - Advanced ranking purpose profiles

- Added external factor-informed ranking purposes: multi-factor, quality growth, quality value, sustainable income, minimum volatility, momentum, risk-adjusted, small-growth, NISA long-term, data-confidence, ETF core-cost, and ETF income.
- Added purpose-specific help text so the ranking UI explains the selected logic, key metrics, and risk checks beside the `ランキング作成` action.
- Extended local symbol database fit scoring so stock / ETF metadata contributes differently for growth, value, income, low-volatility, NISA, data-confidence, and ETF-specific profiles.
- Updated operations and UI wording docs to treat `並べ替え条件` as the standard label and describe the new profiles.

## 2026-05-23 - Ranking deep-dive cleanup and build limit

- Added a `作成対象` control to cap expensive provider ranking builds at DB-fit-ranked top 100 / 300 / 800 candidates, with all-candidates still available by explicit selection.
- Kept ranking fetch cache keys based on the effective candidate list so changing the build limit invalidates stale results correctly.
- Cleared stale ranking deep-dive widget state when results become stale or unavailable, and rerun immediately after opening a ranking symbol in the cockpit to avoid duplicated navigation buttons.

## 2026-05-23 - Ranking sort reuse after build limit

- Changed the pre-fetch `作成対象` candidate limit to use a fixed multi-factor DB-fit baseline instead of the currently selected sort profile.
- This keeps the fetched symbol set stable when only `並べ替え条件` changes, so cached ranking data can be re-sorted without another provider fetch.

## 2026-05-25 - Documentation and provider status alignment

- Aligned README, PROJECT_CONTEXT, roadmap, and operations guide with implemented Phase 19 Decision Report and Phase 20 local Research RAG evidence slice.
- Clarified that Research Score, external RAG adapters, assistant, fund ranking, PDF/Excel, and execution remain future scope.
- Updated the Research RAG onepager so current Phase 20 contracts are separated from Phase 21+ Research Score sketches.
- Changed market-data provider diagnostics so Yahoo is reported as an implemented opt-in live adapter, while deterministic supported providers remain `mock` / `csv` and `polygon` remains planned.

## 2026-05-25 - Phase 20 Research RAG local evidence completion

- Completed the Phase 20 local Research RAG evidence slice boundary: ingestion, hash dedupe, chunking, keyword retrieval, deterministic Research Summary, data-quality warnings, cockpit / ranking modal display, lightweight ranking evidence status, and Cockpit Decision Report Research Evidence export.
- Added freshness-aware retrieval scoring, source-type filtered search coverage, and low-reliability evidence warnings while keeping Research Score, external adapters, vector / hybrid search, and Assistant integration in Phase 21+ or future scope.
- Surfaced Research data-quality warnings in the Cockpit Research Summary panel as table rows so missing, stale, or low-reliability evidence remains visible as decision-support context rather than advice.

## 2026-05-25 - Phase 21 Advanced Research RAG roadmap planning

- Added Phase 21 as `Advanced Research RAG - Evidence Extraction And Grounded Answers`, positioned between the completed Phase 20 local evidence slice and later Research Score integration.
- Defined Phase 21 scope for structured evidence extraction, deterministic query expansion, optional embedding / vector / hybrid retrieval, evidence reranking, template-based grounded answers, Retrieval Quality, UI / Decision Report display, and safety guardrails.
- Moved Research Score / Investment Score integration to Phase 22+ in docs so Phase 21 can improve RAG quality without changing ranking order or investment scoring by default.

## 2026-05-25 - Phase 21 Research query expansion first slice

- Added `config/research_query_terms.yml` as the deterministic category dictionary for growth, shareholder return, financial safety, business risk, and confirmation gap terms.
- Added `ResearchQueryExpansionService` / `ResearchQueryExpansionResult` and category-aware `ResearchSearchRequest` fields while preserving Phase 20 keyword search behavior by default.
- Wired `ResearchAnalysisService` topic searches through query expansion and covered config loading, category search expansion, and analysis integration with deterministic tests.

## 2026-05-25 - Phase 21 structured extraction first slice

- Added `ResearchExtractedClaim` and `CompanyResearchReport.extracted_claims` as the first structured evidence extraction contract.
- Generated non-gap claims only when supporting `ResearchEvidence` exists, and represented missing category evidence as `confirmation_gap` with zero confidence.
- Kept extracted claims as decision-support context only; scoring, ranking order, and Investment Score integration remain unchanged.

## 2026-05-25 - Phase 21 grounded answer first slice

- Added `ResearchGroundedAnswer` and `ResearchGroundedAnswerService` as the first template-based grounded answer contract/service.
- Wired `CompanyResearchReport.grounded_answer` so answers are generated only from extracted claims and referenced `ResearchEvidence`, with warnings carried through for confirmation gaps.
- Kept the answer wording explicitly non-recommendational; no LLM, external API, ranking, or Investment Score behavior was added.

## 2026-05-25 - Phase 21 retrieval quality first slice

- Added `ResearchRetrievalQuality` and `CompanyResearchReport.retrieval_quality` as the first retrieval transparency contract.
- Recorded the keyword backend, category query set, expanded terms, retrieved candidate count, deduped evidence count, and warnings for future UI / Decision Report display.
- Kept vector / hybrid retrieval, external embeddings, ranking, and Investment Score behavior unchanged.

## 2026-05-25 - Phase 21 evidence reranker first slice

- Added `ResearchEvidenceReranker` as a deterministic reranker that keeps `ResearchEvidence` output compatible.
- Wired reranking into keyword retrieval and company-level evidence ordering using relevance, reliability, freshness, source-type priority, and duplicate suppression.
- Kept vector / hybrid retrieval, scoring, ranking, and Investment Score behavior unchanged.

## 2026-05-26 - Ranking direction signal first slice

- Added forecast direction signal fields: `upside_signal_score`, `downside_signal_score`, `direction_net_score`, and `direction_signal_label`, while keeping `forecast_agreement_score` as a compatibility / model-consistency metric.
- Reweighted ranking presets so direction signal is the main forecast-derived ranking input, added the `上昇気配重視` profile, and kept income / value / low-volatility profiles from over-weighting direction.
- Updated Ranking / Cockpit UI wording and chart profiles to show `方向感`, `上昇気配`, and `下降警戒` as decision-support signals rather than buy/sell recommendations.

## 2026-05-26 - Ranking purpose order and Streamlit reload guard

- Reordered ranking purpose options so common choices appear first, with ETF-specific options promoted when ETF is selected.
- Added a Streamlit UI compatibility wrapper for forecast consensus summarization so a cached older backend module does not crash on the new `history` argument.
- Kept direction signal fallback values neutral when older cached score / consensus objects do not yet carry the new direction fields.

## 2026-05-26 - Ranking purpose-specific display polish

- Added purpose-specific Ranking Focus summaries, top-weight chips, result-table leading columns, and row-level sorting reasons / checkpoints so the chosen `並べ替え条件` is visible in each result.
- Added `上昇気配重視` charting as `上昇気配 x 下降警戒の低さ`, plus fit/risk, fit/direction, data-confidence, and ETF-focused chart profiles.
- Enriched ranking display rows with symbol-master metrics such as PER, PBR, ROE, dividend yield, expense ratio, NISA, investment style, and market-cap tier for purpose-specific tables.

## 2026-05-26 - Direction signal history fix

- Fixed ranking / preview direction-signal inputs so forecast consensus uses the fetched feature-history bars instead of only the short display period.
- This prevents one-week / one-day ranking periods from causing every symbol to fall back to `UNKNOWN` and neutral 50 / 50 direction scores.
- Clarified UI fallback wording as `方向データ不足` and made overlapping upside/downside charts fall back to a more informative score/risk map.
- Bumped the ranking build cache key so existing Streamlit sessions recompute ranking rows with the corrected direction-signal inputs.

## 2026-05-26 - Upside / downside signal v2

- Updated forecast signal scoring to use volatility-adjusted forecast edge, model direction edge, continuous momentum scoring, trend confirmation, and a confidence-factor floor.
- Kept Ranking and Symbol Cockpit primary direction-support UI to the two existing indicators: `上昇気配` and `下降警戒`; older direction net / label fields remain backend compatibility details, not main UI indicators.
- Changed ranking preset scoring so higher `下降警戒` lowers the ranking contribution internally while the raw warning score remains visible to users.
- Refreshed UI wording, chart profiles, tests, and current-state docs to avoid adding direction balance / direction score style public indicators.

## 2026-05-26 - Phase 21 Research RAG UI / report display first slice

- Added UI helper rows for Phase 21 Research RAG outputs: grounded answer, retrieval quality, and extracted claims.
- Displayed grounded answer and retrieval quality in the cockpit / ranking Research Summary panel, and extracted claims inside the Research RAG detail expander.
- Added grounded answer, retrieval quality, and extracted claim rows to the Cockpit Decision Report Research Evidence section without changing ranking, Investment Score, Research Score, or retrieval behavior.

## 2026-05-26 - Phase 21 optional vector / hybrid retrieval contract first slice

- Added optional Research RAG vector / hybrid intermediate contracts: `ResearchEmbedding` and `ResearchRetrievalCandidate`.
- Added `ResearchDisabledVectorStore` so the default vector path is explicit, deterministic, and reports a retrieval-quality warning instead of silently attempting vector search.
- Added `ResearchHybridScorer` and `ResearchHybridScoreWeights` to combine keyword, vector, freshness, reliability, and source-type priority scores without wiring hybrid retrieval into the default keyword path yet.

## 2026-05-26 - Phase 21 keyword-fallback hybrid retrieval wrapper

- Added `HybridResearchRetrievalService` as an optional wrapper around the existing keyword retrieval service and optional vector store.
- Converted hybrid-scored vector candidates back to `ResearchEvidence` so downstream Research Summary / Decision Report contracts stay compatible.
- Kept the default keyword retrieval path unchanged; when vector search is disabled or empty, hybrid retrieval falls back to keyword results and records retrieval-quality warnings.

## 2026-05-26 - Phase 21 in-memory local vector store first slice

- Added `ResearchInMemoryVectorStore` for deterministic local vector retrieval without external dependencies.
- Added optional `ResearchSearchRequest.query_vector` and cosine-similarity candidate search over stored `ResearchRetrievalCandidate` + `ResearchEmbedding` pairs.
- Kept the default keyword retrieval path unchanged; vector search is only used when an explicit query vector and vector store entries are supplied.

## 2026-05-28 - Global UI theme token foundation

- Centralized the dark navy financial SaaS palette, AI accent colors, investment signal colors, chart colors, and ranking grid theme tokens in `ui/styles.py`.
- Updated global Streamlit surfaces, tables, cards, buttons, alerts, AI / Research / Decision Report components, and key chart colors to use the shared theme without changing scoring, ranking, forecast, Research RAG, or provider behavior.
- Documented the UI theme source of truth and added a regression test for the reusable theme tokens.

## 2026-05-28 - Global UI visual depth pass

- Refined the shared Streamlit CSS for a denser financial cockpit feel: subtle navy grid background, stronger header/page-title bands, raised input/expander/container surfaces, premium button treatment, and more polished metric/ranking cards.
- Adjusted Copilot / Insight accents to use controlled linear AI treatments instead of broad glow-heavy decoration.
- Kept the change display-only; data fetch, forecast, scoring, ranking, Research RAG, and report behavior remain unchanged.

## 2026-05-28 - UI contrast and cockpit title spacing fix

- Increased contrast in the shared palette by darkening app / surface backgrounds and brightening title / primary / secondary text tokens.
- Added left padding and safer wrapping to the page-title band so the cockpit title no longer collides with the accent line or title art.
- Kept this as CSS / token-only polish with no workflow or investment logic changes.

## 2026-05-28 - UI text hierarchy polish

- Added role-based text tokens for heading, value, label, caption, AI title/body/muted, and financial semantic positive / negative / warning / info / neutral colors.
- Applied the text hierarchy to global Markdown, captions, forms, tables, metrics, cards, AI / Research surfaces, Decision Report snippets, badges, and chart labels.
- Kept the work display-only; forecast, scoring, ranking, Research RAG, provider, and report logic remain unchanged.

## 2026-05-28 - Primary button contrast restore

- Restored primary button readability by preventing global Markdown text rules from overriding button labels.
- Switched primary button text back to dark navy on cyan so action buttons keep the clearer previous contrast.
- Kept the change CSS-only with no workflow or logic changes.

## 2026-05-28 - Primary button blue-green glow restore

- Restored the brighter blue-to-green primary button gradient with a hover background-position shift and slightly stronger cyan / teal glow.
- Kept dark navy button text from the contrast fix so primary actions remain readable.
- Kept the change CSS-only with no workflow or logic changes.

## 2026-05-28 - Button label readability polish

- Forced button descendants to inherit the button text color so Streamlit Markdown text rules cannot wash out labels.
- Tuned secondary, primary, hover, and disabled button label colors / text shadows for readable contrast on both dark and cyan-green backgrounds.
- Kept the change CSS-only with no workflow or logic changes.

## 2026-05-28 - Button typography and background continuity polish

- Refined Streamlit button typography with a tighter button-only font stack, calmer weight, inherited Markdown label styling, and less black-looking primary button text.
- Extended the shared navy background treatment to the main Streamlit container and full-width block area so the page no longer looks visually cut off outside the content band.
- Kept the change CSS-only with no workflow, data, forecast, scoring, ranking, Research RAG, or report behavior changes.

## 2026-05-28 - Research operation insight summary

- Replaced the Cockpit Research operation card's status chips with an `AI調査でわかったこと` summary.
- The card now summarizes business overview, checked source types, good / caution material counts, and next confirmation from existing `ResearchBrief` data before the primary AI refresh action.
- Kept the implementation local rule-based and deterministic; local lightweight LLM summarization remains a later option if rule-based shaping is not enough.

## 2026-05-28 - Research operation card single action

- Simplified the Cockpit Research operation card so `AI調査を更新` is the only always-visible action.
- Removed the news-only refresh, evidence CSV export, and detail-toggle controls from the main Research operation card to reduce decision noise.
- Updated Research RAG docs and UI wording policy so external news remains part of the standard AI調査 flow instead of a separate primary user action.

## 2026-05-28 - Primary button B+C hybrid style

- Changed primary action buttons to a deeper AI blue / teal hybrid gradient with off-white text and subtle cyan glow instead of dark navy text.
- Kept hover motion as a blue-green background-position shift with stronger but restrained cyan / teal elevation.
- Kept the change CSS-only with no workflow, data, forecast, scoring, ranking, Research RAG, or report behavior changes.

## 2026-05-28 - Main background blending fix

- Removed the extra main-content background layer so the Streamlit content area blends back into the app-level dark navy background instead of reading as a separate panel.
- Softened the app header and page-title band borders / fills so they keep structure without visually separating from the surrounding background.
- Kept the change CSS-only with no workflow, data, forecast, scoring, ranking, Research RAG, or report behavior changes.

## 2026-05-28 - ResearchBrief reading guide

- Added a compact ResearchBrief reading guide between AI整理メモ and confirmation points.
- The guide summarizes `確認できたこと`, `注意して見ること`, `まだ足りないこと`, and `次にやること` from existing local ResearchBrief data.
- Kept the guide display-only and decision-support oriented; detailed source cards, Research Score, and raw data remain behind expanders.

## 2026-05-28 - ResearchBrief source-rank focus cards

- Added structured ResearchBrief material candidates so good / caution materials keep source type, source confidence, source count, and published date alongside the readable summary.
- Updated the Research Summary confirmation-point cards to show `公式資料` / `ニュース` style source-rank badges and short `情報源信頼度` labels near each material.
- Reworded ResearchBrief confirmation gaps so missing metrics read as `まだ確認できていない数値` and are framed as additional confirmation items, not bad news.

## 2026-05-28 - App header logo asset

- Added a transparent, cropped SMAI brand logo asset under `ui/assets/brand/` for the Streamlit app header.
- Replaced the visible `Smart Market AI` text heading with the logo image while keeping accessible alt text and the existing header guidance message.
- Tuned the logo sizing and drop shadow so it sits naturally on the dark navy header without adding a separate card or background.

## 2026-05-28 - Unified app background base

- Added a shared `--bg-page` base color and applied the same dark navy grid / gradient treatment to body, root, Streamlit app, and main containers.
- Reduced the visual mismatch where content margins looked nearly black beside the central navy content area.
- Kept the change CSS-only with no workflow, data, forecast, scoring, ranking, Research RAG, or report behavior changes.

## 2026-05-28 - ResearchBrief visible UI polish

- Made the Research Summary `AI整理メモ` visually prominent with non-advice, source-confidence, and missing-metric badges.
- Replaced the normal ResearchBrief metric table in the primary view with compact metric cards and moved missing metrics into a warning-style confirmation panel.
- Added source-confidence badges to ResearchBrief source cards while keeping Research Score and ranking order behavior unchanged.

## 2026-05-28 - ResearchBrief information density reduction

- Reduced the Research Summary first view to AI整理メモ, focused confirmation-point cards, optional metric cards, confirmation gaps, and next actions.
- Moved source cards, Research Score rows, external source trace cards, and detailed evidence summary into expanders so they remain available without dominating the main reading path.
- Trimmed provider-style raw labels from primary ResearchBrief text while keeping detailed source data available behind the detail controls.

## 2026-05-28 - App header brand emphasis

- Enlarged and centered the Smart Market AI logo in the main app header so the brand reads as the primary first-viewport element.
- Added a stronger header band, centered accent line, and larger logo glow while keeping the mascot as a right-side supporting element.
- Kept the change CSS-only with no workflow, data, forecast, scoring, ranking, Research RAG, or report behavior changes.

## 2026-05-28 - ResearchBrief readable copy shaping

- Changed ResearchBrief business overview and material candidates to explain the confirmed topic, source count, and lead source instead of showing raw provider snippets.
- Added rule-based business-domain wording for provider profile text so vehicle/software/etc. descriptions become Japanese confirmation text in the primary view.
- Moved news/source retrieval warnings out of caution-material candidates and into confirmation gaps so they read as missing evidence, not investment risk.

## 2026-05-29 - InvestmentInsight decision memo layer

- Added display-only `InvestmentInsight` models and a deterministic `InvestmentInsightBuilder` for Research RAG outputs.
- The builder reclassifies existing Research evidence, stock news, external fetch traces, and ResearchBrief facts into good materials, caution materials, neutral context, confirmation gaps, action hints, and source confidence without changing scores or ranking order.
- Added the Cockpit / Ranking Research Summary `SMAI 投資判断メモ` panel above AI整理メモ and updated AI調査 wording toward `判断材料に変換しました` / `判断前に確認`.

## 2026-05-29 - InvestmentInsight summary hierarchy polish

- Promoted the Research Summary top block to `SMAI 投資判断サマリー` with status, confidence, primary action, and a short current-view summary.
- Reorganized the initial view into 3 columns: good materials, caution materials, and still-missing information, each capped at 3 visible items.
- Moved AI整理メモ / ResearchBrief confirmation cards into a folded `根拠確認` layer so source cards, Research Score, external traces, and detail tables stay secondary.

## 2026-05-29 - InvestmentQuestionSummary review questions

- Added rule-based `InvestmentQuestionSummary` / `InvestmentQuestionSummaryBuilder` to map existing Research RAG facts, provider data, news, and InvestmentInsight into 10 fixed investment-review questions.
- Added the `投資判断で知りたいこと` UI section between `SMAI 投資判断サマリー` and the 3-column material cards, showing the first five questions up front and the remaining questions in an expander.
- Each answer now carries a root evidence label (`高` / `中` / `低` / `不足`) and explicitly says `未取得` / `判断できません` when core information is missing, without changing scores or ranking order.

## 2026-05-29 - CompanyResearchSummary mapping precision

- Expanded Yahoo Finance provider-profile field mapping so market cap, revenue, operating income, net income, EPS, PER/PBR/ROE, dividend yield, and employee count can populate `QuantitativeSummary` instead of staying `未取得` when present.
- Improved business-profile extraction for main businesses, products/services, regions, and customer segments while keeping news titles out of business-profile evidence.
- Reflected TDnet entries in both IR summary and latest-news/disclosure summary, distinguishing `取得済み・本文未解析` title/URL evidence from missing or unverified information.

## 2026-05-29 - CompanyResearchSummary classification refinement

- Split business-profile mapping into main businesses, supporting businesses, products/services, regions, and customer segments, with conservative `補完候補` product labels when provider profiles lack explicit product/service details.
- Added enterprise value and improved provider metric formatting for JPY scale, PER/PBR, ROE/dividend yield, employee count, zero values, and empty / None / NaN-like missing values.
- Renamed the visible news section to `最新ニュース・開示サマリー` and added latest-topic classification so TDnet, forecast revisions, shareholder returns, governance topics, products, and ordinary news keep distinct status and confirmation flags.

## 2026-05-29 - Research summary wording and raw-provider cleanup

- Tightened provider-profile cleanup so `Provider Symbol`, `Quote Type`, `Website`, raw `Industry:` / `Country:` style fields, and internal source identifiers do not leak into company summaries or fixed-question answers.
- Improved latest news / disclosure summaries so TDnet rows read as official disclosures with body-unparsed status, while news rows clearly state that official IR confirmation is still needed.
- Added Japanese display labels for common sector / industry values in the company summary UI and regression tests for raw-provider cleanup, Q&A wording, and news/disclosure confirmation text.

## 2026-05-29 - AI research refresh performance pass

- Added session-level TTL caching for repeated external research fetches and a small timing trace caption for the AI調査 refresh path.
- Parallelized the composite TDnet / Yahoo Finance adapter and avoided re-registering / re-chunking identical external payload content in the session-local Research store.
- Cached the rendered research summary bundle for unchanged report/news/external-source inputs so Streamlit reruns do not rebuild every summary layer.

## 2026-05-29 - Company research summary wording and topic quality

- Reworked company overview wording so provider-profile summaries lead with the company name and confirmed business context before listing missing segment / profit-composition checks.
- Improved latest news / disclosure summaries into an `概要 / 企業理解上の意味 / 追加確認` shape, avoiding title-only repetition for TDnet rows.
- Expanded latest-topic classification for forecast revisions, shareholder returns, business reorganizations, governance, and product/service topics while deduping repeated disclosure rows.

## 2026-06-01 - Ranking rich sort table

- Added always-visible ranking detail columns for `配当利回り`, `PER`, `PBR`, and `ROE`, with missing values displayed as `N/A` instead of zero-like placeholders.
- Added local AgGrid numeric sort settings for total score, dividend yield, PER, PBR, ROE, and related detail metrics, keeping missing values at the end for both ascending and descending sorts.
- Added ranking data-state and score-explanation expanders, refreshed ranking via the explicit `最新データを取得して更新` action, and moved score/detail/fetch context into row-click detail rows.

## 2026-06-01 - Ranking rich sort regression check

- Added short UI guidance that explains table column sort directions, including low-value checks for `PER`, `PBR`, `Risk`, and `ボラティリティ`, while keeping missing `N/A` values at the end.
- Clarified that the top-10 chart compares the representative metric for the selected ranking condition and does not automatically switch when the detail table is locally re-sorted.
- Added regression tests for required metric sort directions, chart/table context wording, and missing-value guidance.

## 2026-06-01 - Ranking all-sort regression sprint

- Added simple single-metric ranking conditions for `総合スコア`, `配当利回り`, `PER`, `PBR`, `ROE`, `時価総額`, `出来高`, `ボラティリティ`, `低リスク候補`, and `データ品質` without adding an advanced condition builder.
- Aligned top candidate cards, the Top 10 bar chart, row reasons, and the detailed table with the selected single-metric sort; low-better metrics use low-first ordering and missing values remain at the end.
- Clarified the scatter chart as a supplementary risk/expectation view and added regression coverage for all required sort conditions.

## 2026-06-01 - Ranking sort information architecture cleanup

- Split the top Ranking UI into `評価方針` and `並び替え`, so composite evaluation profiles and single-metric sort conditions are no longer mixed in one large dropdown.
- Reduced visible evaluation policies to beginner-facing options (`AI総合`, `高配当`, `割安`, `成長`, `安定`, `NISA長期`, `ETF`) and mapped legacy / detailed profiles to representative composite profiles.
- Limited the top-level single-metric sort to `総合スコア順`, `配当利回り順`, `PER低い順`, `PBR低い順`, and `ROE高い順`; kept `時価総額`, `出来高`, `ボラティリティ`, `Risk`, and `データ品質` available through detailed-table column sort.
- Renamed the `risk_signal_score` high-first sort wording from low-risk language to `リスク確認しやすい順` / 安定性確認 wording to avoid implying guaranteed low risk.

## 2026-06-01 - Ranking composite policy path restore

- Removed the top-level single-metric `並び替え` selectbox from the Ranking main flow and moved single-metric sorting fully into detailed-table column sorting.
- Restored SMAI composite evaluation profiles in `評価方針`, including `上昇気配重視`, `モメンタム・トレンド`, `成長クオリティ`, `割安クオリティ`, `高配当の持続性`, `低ボラ・安定`, `リスク調整パフォーマンス`, `小型・成長探索`, `データ信頼度優先`, and ETF profiles.
- Re-aligned top candidate cards, the Top 10 chart, selected-candidate breakdown, and Decision Report context with the selected evaluation policy instead of a single metric sort.
- Expanded detailed-table sort guidance to cover Screening, upside/downside signals, risk, and missing-value handling.

## 2026-06-01 - Research Summary UX review

- Checked the `AI調査を更新` Cockpit flow for a domestic stock, foreign stock, ETF, and external-source failure path with Streamlit's UI test runner because the in-app browser backend was unavailable in this session.
- Confirmed the primary Research Summary order: company / ETF summary, quantitative or fund metrics, IR or ETF-specific sections, latest news / disclosure summary, and confirmation questions, with AI reading notes, evidence details, source cards, Research Score, and external-source traces behind expanders.
- Softened the news-URL gap message in the UI so internal `source_type=news` wording no longer appears in the main Research Summary; it now reads as supplemental confirmation guidance instead of a warning.

## 2026-06-01 - Score hierarchy UX slice

- Added a shared score / confidence hierarchy table for Cockpit and Ranking so `投資スコア / 総合スコア`, `Research Score`, `データ品質`, and `条件適合度 / DB信頼度` have distinct roles.
- Clarified that Research Score is evidence coverage / freshness / confidence context and does not change the default total score or Ranking order.
- Expanded Cockpit score component rows and Ranking detail rows with beginner-facing reading guidance, especially that data quality and DB confidence are not investment attractiveness.

## 2026-06-01 - Score hierarchy browser validation fix

- Rechecked the Cockpit and Ranking score hierarchy sections in an actual Chrome / Streamlit screen after the in-app browser backend was unavailable.
- Found that the hierarchy table was readable but too cramped when rendered through Streamlit's dataframe grid; switched this hierarchy-only display to the existing wrapping HTML table style.
- Confirmed the refreshed Cockpit and Ranking screens with `mock` market data: the score hierarchy text is visible, wraps in place, and no longer uses the dataframe grid for this explanation block.

## 2026-06-01 - Research Summary actual-screen validation polish

- Rechecked `AI調査を更新` Research Summary in actual Chrome / Streamlit screens for domestic stock, foreign stock, ETF, and external-source failure / material-insufficient states.
- Confirmed the primary summary order and folding boundary: company / ETF summary, quantitative or fund metrics, IR or ETF-specific sections, latest news / disclosure, and confirmation questions appear first; AI notes, evidence/source cards, Research Score, external-source traces, and technical failure details stay behind expanders.
- Changed the pre-refresh operation-card wording to neutral `確認方針` / `調査アクション` text so the immediate post-refresh screen does not keep stale `AI調査を更新して...` guidance above the refreshed summary.
- Moved raw external-fetch failure details out of the normal warning area and into a collapsed technical-details expander, keeping the visible failure message beginner-friendly.

## 2026-06-01 - Research Summary docs / implementation sync

- Synchronized current docs with the implemented Research Summary UI: `最新ニュース・開示サマリー`, pre-fetch `確認方針`, `調査アクション`, and collapsed `取得失敗の技術詳細`.
- Updated the manual UX checklist and functional-spec issue register to mark the CompanyResearchSummary readability and external-fetch failure / material-insufficient checks as resolved after actual-screen validation.

## 2026-06-01 - EDINET external research adapter slice

- Added an optional EDINET metadata/link adapter to the default `AI調査を更新` external research source set; it live-fetches only when `EDINET_API_KEY` is configured and otherwise returns no payloads.
- Kept normal checks network-free with fixture/fake JSON tests for EDINET matching, source URLs, reliability, and default adapter ordering.
- Updated Cockpit external-source labels/check notes and synced Research RAG roadmap/operations docs so EDINET is no longer described only as future scope.

## 2026-06-02 - External stock news adapter normalization slice

- Added `ExternalStockNewsAdapter`, `ExternalStockNewsFetchService`, and `ExternalResearchStockNewsAdapter` as the first Phase 21.7 backend slice for URL-backed external news normalization.
- Normalized external news into `StockNewsEvidence` with selected-symbol filtering, URL dedupe, freshness status, stale-news warnings, viewpoint / sentiment classification, and explicit network opt-in gating.
- Added fake-adapter tests and synced Research RAG roadmap / operations docs so Phase 21.7 has a concrete backend contract while normal checks remain network-free.

## 2026-06-03 - Cockpit score / forecast / risk wording slice

- Clarified Symbol Cockpit wording for Investment Score, Screening, Forecast, Risk, and Data Quality without changing scoring or forecast logic.
- Added a Forecast / Risk reading distinction to the Cockpit score hierarchy table, including explicit non-guarantee and non-advice wording.
- Updated UX / functional-spec trackers so the score, forecast, screening, and risk wording issues are in review pending real-screen confirmation.
- Checked the fetched Cockpit screen with Chrome headless on `mock` / `7203.T`, including `04 評価の内訳` and the opened `投資スコアの詳細・ダウンロード` expander. Screenshots were saved under `outputs/work/cockpit_score_breakdown_check_04.png` and `outputs/work/cockpit_score_detail_expander_check_open.png`.

## 2026-06-03 - Ranking criteria / confidence wording slice

- Added a folded `評価方針・条件・信頼度の読み方` guide to the Ranking flow before data fetch, distinguishing evaluation policy from pre-fetch detail filters.
- Clarified that `条件適合度` and `DB信頼度` are data / coverage checks rather than investment attractiveness, and that NISA, dividend / distribution yield, and ETF cost / income criteria are comparison conditions rather than safety or product-suitability judgments.
- Updated Ranking help texts, UX checklist, functional-spec issue register, roadmap, and current-state context without changing ranking score logic or provider fetch behavior.
- Checked the Ranking screen in actual Chrome headless against the fresh Streamlit server on `http://localhost:8502`; the guide opened, the table text was visible, and the screenshot was saved under `outputs/work/ranking_criteria_guide_check_open.png`.

## 2026-06-03 - Research source citation UI de-emphasis

- Changed `ニュース・開示の出典を表示（URL付きN件）` from a Market Intelligence card grid into a folded, small citation-style list so it reads as supporting references rather than another summary block.
- Kept external link behavior (`href`, `target="_blank"`, `rel="noopener noreferrer"`) and source-specific labels while removing the prominent summary-card visual treatment from the source panel.
- Updated Research Summary UX / spec tracking to reflect that summaries and top news remain the primary cards, while source links are secondary reference material.

## 2026-06-03 - Research Summary advanced detail consolidation

- Consolidated the stacked Research Summary detail expanders into a single `詳細情報・開発者向け` panel.
- Kept the normal user path focused on company / metric / IR / news summaries, citation-style source links, and primary company-understanding checkpoints.
- Removed advanced sections whose purpose overlapped with the already-visible summaries, citations, and confirmation points; the panel now keeps Research Score, data quality, retrieval quality, extracted claims, evidence detail, and external-source fetch status without changing fetch logic, Research Score calculation, Investment Score, or ranking order.

## 2026-06-03 - Phase 23 low-cost Assistant backend slice

- Added `backend/assistant` with `AssistantRequest`, `AssistantResponse`, citations, intent classification, and `TemplateAssistantService`.
- Kept the first Assistant slice deterministic and network-free: it reads existing `DecisionReportContext` sections and returns reasons, cautions, next checkpoints, and cited sections without LLM calls.
- Added an explicit advice-boundary path for buy / sell / hold style questions, so the Assistant explains confirmation materials without giving trade instructions.
- Updated the roadmap, project context, and FS-014 tracking to mark Phase 23 as an initial backend slice with API / Streamlit UI still pending.

## 2026-06-03 - Phase 22.x Investment News dashboard MVP planning

- Updated the roadmap for a planned independent `投資ニュース` market-news cockpit screen.
- Defined MVP-priority UI blocks: flowing market news stream, news-heat theme heatmap, investment-category news lanes, deterministic AI comment / confirmation checkpoints, and related-symbol handoff to Symbol Cockpit.
- Clarified MVP exclusions: right-side filters, detailed search, Watchlist notifications, SNS sentiment, advanced clustering, News Score, score/ranking integration, buy/sell/hold judgement, and automation.
- Added FS-021 to track the product-safety boundary that investment news must remain a confirmation-material entry point rather than a recommendation engine.

## 2026-06-03 - Phase 22.y News refresh and cache planning

- Added Phase 22.y for the Investment News dashboard background refresh and cache layer.
- Required bounded local storage from MVP: latest snapshot only, one previous backup, no raw source persistence by default, atomic save, tmp cleanup, and cache normalization limits.
- Added rotating news update log requirements with `RotatingFileHandler`, summary-only INFO logs, bounded ERROR behavior, TTL / retry controls, and lightweight update status.
- Added FS-022 to track storage / operations risk for news cache, logs, raw data, debug dumps, and refresh retry behavior.

## 2026-06-03 - Phase 22.y news contracts and cache limits slice

- Added `backend/news` contracts for `NewsHeadlineCard`, `NewsHeatmapCell`, `NewsCategoryLane`, and `NewsDashboardSnapshot`.
- Added cache normalization limits for stream headlines, category lanes, heatmap cells, summary text, AI comments, checkpoints, and related-symbol dedupe.
- Kept raw provider payloads out of the contract by using strict models, and added a helper to detect recommendation-like prohibited wording.
- Added network-free cache-limit tests for collection caps, text truncation, checkpoint limiting, symbol dedupe, raw-field rejection, and prohibited wording detection.

## 2026-06-03 - Phase 22.y cache persistence and refresh manager completion

- Completed the Phase 22.y backend cache/update foundation for Investment News.
- Added latest snapshot load/save, one-generation `.prev` backup, `.tmp` atomic save, news-dashboard-only cleanup, cache-size helper, and latest-only update status persistence.
- Added rotating news-update logger configuration and refresh manager behavior for TTL/minimum-interval skip, force refresh, bounded retry, failure fallback, and summary-only logging.
- Added network-free tests for atomic save, cleanup, status persistence, log rotation, TTL skip, success refresh, failure fallback, and prevention of huge raw error text in logs.

## 2026-06-03 - Phase 22.z symbol database background refresh foundation

- Added the Phase 22.z backend foundation in three committed slices: refresh contracts / priority queue, queue persistence / recovery / lock, and repository / refresh manager / rotating logging.
- Implemented deterministic freshness classification, usage / importance / stale / recent view / ranking / manual refresh priority scoring, bounded queue sorting, and fresh-symbol skip behavior.
- Added atomic queue/status persistence, in-progress recovery, stale lock cleanup, latest-only normalized symbol record storage, raw/debug field filtering, and failure-safe one-symbol refresh execution that preserves existing data.
- Kept the slice network-free with targeted tests for priority, cache/lock recovery, repository atomic save, manager success/failure behavior, and logger rotation.

## 2026-06-03 - Symbol DB startup refresh verification / hookup

- Confirmed that the first Phase 22.z foundation was not yet called from the app startup path: launching the app initially produced no `symbol_refresh_queue.json`, `symbol_refresh_status.json`, or `symbols_cache.json`.
- Added `backend/symbols/startup.py` and a Streamlit startup hook that runs a bounded local-first refresh from `data/marketdata/symbol_universe.csv` without network access.
- Verified startup execution in bare Streamlit mode: first run created 20 normalized symbol records with `pending_like_count=0`; second run advanced to 40 records, kept `refresh_queue_size=0`, and left no `pending` / `retryable` / `in_progress` tasks.

## 2026-06-03 - Symbol DB startup refresh TTL and CSV cleanup

- Added a 24-hour minimum interval to the Streamlit startup symbol refresh so repeated app restarts do not keep processing additional batches.
- Fixed refresh status persistence so `last_attempt_at` survives the final status save and can be used for interval checks.
- Corrected the `ORR` ETF row in `symbol_universe.csv`: kept the high `expense_ratio_pct=10.91` value, changed `complexity` to `advanced`, removed the inconsistent `low_cost` tag, and marked `data_quality=WARN`.
- Revalidated `symbol_universe.csv`; schema validation remained OK with 0 issues.

## 2026-06-03 - Symbol DB background worker cadence

- Replaced the visible-startup path with a daemon background worker so Streamlit rendering is not blocked by symbol DB maintenance.
- Set the short-session cadence to 80 symbols immediately, 40 after 3 minutes, 40 after 8 minutes, then 30 every 5 minutes.
- Kept fresh-symbol skip behavior and added a 500-symbol per-session safety cap to avoid runaway background work.
- Added network-free tests for the short-session plan, recurring batch behavior, and early stop when no missing/stale symbols remain.

## 2026-06-04 - Symbol DB background worker cadence increase

- Increased the symbol DB background refresh cadence after app smoke indicated low runtime load.
- Updated the short-session plan to 150 symbols immediately, 75 after 3 minutes, 75 after 8 minutes, then 50 every 5 minutes.
- Raised the per-session safety cap from 500 to 1000 symbols while keeping fresh-symbol skip, lock, and bounded batch behavior.

## 2026-06-04 - Phase 22.x pre-implementation documentation sync

- Reviewed the current implementation boundary before starting the Investment News dashboard MVP.
- Updated README, operations guide, roadmap, project context, functional spec issues, and manual UX checklist so news cache / symbol DB refresh foundations are no longer described as future work.
- Clarified that Phase 22.x is the next recommended UI slice, while `backend/news` cache/update foundation, `backend/symbols` background refresh foundation, and `backend/assistant` deterministic template service already exist.
- Kept the next implementation target network-free by documenting fake snapshot / fixture regression, non-advice wording, URL/freshness/source visibility, and related-symbol handoff review points.

## 2026-06-04 - Phase 22.x Investment News dashboard MVP

- Added deterministic Investment News dashboard snapshot building in `backend/news/dashboard.py`, including demo snapshot, heatmap aggregation, category lanes, and stream headline ordering.
- Added the Streamlit `投資ニュース` screen with market news ticker, status cards, news heatmap, category news lanes, safe source links, and related-symbol handoff to Symbol Cockpit.
- Added `投資ニュース` to the sidebar routing and kept the screen network-free by default with cached snapshot / demo snapshot fallback.
- Added regression tests for dashboard snapshot generation, prohibited recommendation wording, UI status items, heatmap frame, safe source-link HTML, and related-symbol handoff.

## 2026-06-04 - Investment Radar mascot title art

- Renamed the user-facing Investment News screen label to `投資レーダー` while keeping the internal `news` route key and backend Investment News contracts.
- Generated and added `ui/assets/mascot/smai-title-investment-radar.webp`, a mascot title art with radar and news-card motifs.
- Wired the new title art into `render_page_title` and updated sidebar labels, UI regression expectations, docs, wording policy, and review checklists.

## 2026-06-04 - Investment Radar headline and heatmap UX

- Renamed `マーケットニュースストリーム` to `市場ニュースヘッドライン` and enlarged / slowed the ticker text for readability.
- Renamed `ニュース加熱テーマ` to `投資ヒートマップ` and added category price-change / volume-activity fields so tile color, opacity, and text prioritize visual market movement.
- Updated related-symbol handoff buttons to include known local symbol names / company names before opening `銘柄コックピット`.

## 2026-06-05 - Investment Radar cache status UI

- Added a compact `ニュース表示の状態` panel to `投資レーダー` showing cached/demo source, freshness, generated time, last successful refresh, headline count, heatmap category count, cache size, and refresh state.
- Added `?smai_page=news|ranking|rebalance|settings` routing support so the implemented app screen can be opened directly while preserving the existing cockpit symbol handoff query path.
- Tightened compact news-card display with fixed height, line clamps, and hidden checkpoint bullets so the first viewport reaches the heatmap more quickly.
- Verified the screen through Streamlit AppTest and headless Chrome desktop / mobile captures; desktop reached the status panel, three headline cards, and the heatmap, while mobile kept the status grid within the viewport.
## 2026-06-05 - Investment Radar filters and Watchlist linkage

- Added category / freshness / related-symbol type / source filters to the Investment Radar screen.
- Added Watchlist parsing, Watchlist match prioritization, and Watchlist-only display across the headline stream, heatmap-visible categories, and category lanes.
- Reworked standard news comments / checkpoints into deterministic RAG-style reading notes that distinguish direct article mentions from SMAI inferred candidates.
- Added UI helper tests for filter behavior, Watchlist ordering, Watchlist parsing, and Streamlit control rendering.
- Revalidated the 100-case related-symbol extraction sprint in 10-case batches; all batches passed at 100.0%.
