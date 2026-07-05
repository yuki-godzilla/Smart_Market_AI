# MVP Operations Guide

#### [BACK TO README](../README.md)

## 通知基盤（N1〜N3-B実装済み）

Phase N1〜N5-Cで、アプリ内通知、ntfy Push、通知カタログ、専用通知センター、オプトインscheduler基盤を段階導入した。通常確認はnetwork-freeで、実ntfy送信は明示テストまたは将来client接続済みProducerだけに限定する。

設定保存:

- 既定保存先は`data/user/notifications.sqlite`
- `SMAI_USER_CONFIG_DIR`指定時はそのdirectoryの`notifications.sqlite`
- DBが無い場合は自動作成
- `notification_meta.schema_version`でmigration versionを管理
- ntfy既定OFF、server URL既定値は`https://ntfy.sh`
- topic入力を空欄で保存した場合は既存値を維持
- topic削除は`保存済みtopicを削除`だけで行い、同時にntfyをOFFにする
- topicはSQLiteへ平文相当で保存され、完全な暗号化秘匿ではない
- UIはtopicをpassword入力にし、保存値を平文再表示しない

ユーザープロフィール:

- 起動時にローカルプロフィールを選択し、`ユーザー追加`から表示名とアイコンを登録できる
- カスタムユーザーのお気に入りとsnapshotは`data/user/profiles/<user_id>/`へ分離保存する
- `SMAIデフォルト`のお気に入りとsnapshotはStreamlit session内だけに保持し、ファイル保存しない
- `SMAIデフォルト`では通知UI、履歴生成、設定保存、外部送信を利用できない
- プロフィール選択は認証ではないため、信頼できるLAN内でのみ運用する

Phase U1検証用smoke:

```powershell
$env:SMAI_RUN_USER_PROFILE_SMOKE = "1"
$env:SMAI_STREAMLIT_URL = "http://127.0.0.1:8503"
.\venv_SMAI\Scripts\python.exe -m pytest tests\ui\test_user_profiles_smoke.py -q
Remove-Item Env:SMAI_RUN_USER_PROFILE_SMOKE
Remove-Item Env:SMAI_STREAMLIT_URL
```

Python本体が削除されてvenvの`home`参照が切れた場合は、旧venvを直接書き換えない。
Python 3.11/3.12を用意し、旧`venv_SMAI`を退避してから新規作成し、
`setup/requirements.txt`と`setup/requirements-dev.txt`を再導入する。
本環境のU1-Verifyでは公式Python 3.11.9をworkspace-local `.python311/`へ隔離導入し、
`venv_SMAI_broken_20260630/`へ旧環境を退避して復旧した。両directoryはGit管理外である。

server URL:

- `https`を許可
- `http`は`localhost`、`127.0.0.1`、`::1`だけ許可
- userinfo、query、fragmentを持つURLは拒否
- 末尾slashは正規化

Quiet hours:

- 日跨ぎ設定を保存可能
- 開始と終了が同じ場合はvalidation error

テスト通知:

1. 右上ユーザータグから`通知設定`を開く。
2. ntfyをONにしてserver URLとtopicを保存する。
3. ntfyアプリ側で同じtopicを購読する。
4. `テスト通知を送る`を1回押す。
5. sent / disabled / filtered / failedの一般化された日本語結果を確認する。

設定画面の初期表示、通常rerun、設定保存、topic削除では外部送信しない。通常テスト/CIはfake client/adapterだけを使い、実ntfyへ接続しない。

Phase N4:

- テスト通知はアプリ内履歴へ先に保存し、その後に必要な場合だけntfyへ送信する。
- 通知センターはサイドメニューではなく全画面共通の右上ユーザーエリアから開く。
- 未読件数、重要件数、カテゴリ、未読/既読/archive、1日/7日/30日、重要のみを確認できる。
- CTAは内部画面への遷移だけで、AI調査や注文などの処理を開始しない。
- ブラウザごとのUUIDはlocalStorageへ保持し、SQLiteの`trusted_devices`と関連付ける。IPアドレスは識別に使わない。
- 新しいbrowser sessionではプロフィール画像を選び、`このユーザーで開始`を押す。
- 右上ユーザーメニューは`ユーザー設定`、`通知設定`、`ユーザー切替`の3項目。ユーザー設定はプロフィールとアイコン、通知設定は通知種類、アプリ内/ntfy通知先、重要度、通知しない時間帯をまとめる。
- Trusted Deviceによる自動選択と登録端末管理は使用しない。`ユーザー切替`はプロフィール選択画面へ戻る。
- 右上ユーザータグの`通知センター`はサイドメニューを隠した専用画面。縦スクロールで通知を確認し、既読、archive、カテゴリ/状態/期間/重要度順を操作する。
- 定時通知は初期OFF。通知設定の`定時通知を有効にする`を明示選択し、別プロセスで`scripts\run_notification_scheduler.bat`を起動した場合だけdue jobを確認する。
- 1回だけ確認する場合: `.\venv_SMAI\Scripts\python.exe -m backend.notifications.scheduler_runner --once`
- 通知カタログと手動生成は`SMAI_NOTIFICATION_DEBUG=1`で起動した通知センター内だけに表示する。
- ユーザーicon候補は`ui/assets/user_icons/manifest.json`の`enabled=true`かつ実在するlocal Assetだけ。ユーザーDBにはicon IDのみ保存する。
- 現在のbuilt-inは既存公式`ui/static/pwa/icon-192.png`。後続Assetはmanifestへ追加し、画像配置後にenabledへ変更する。
- 選択画像が無い場合はdefault、local placeholder、CSS silhouetteの順でfallbackし、外部画像URLは参照しない。

予定する運用境界:

- アプリ内通知履歴を先に保存し、その後に必要な場合だけ ntfy へ送信する。
- ntfy 通知は既定 OFF。ユーザーが設定画面で有効化し、server URL と topic を設定した場合だけ使う。
- `silent`、severity threshold 未満、quiet hours 中は ntfy へ送信しない。
- ntfy 送信失敗は通知履歴と delivery result に残すが、SMAI 本体処理を止めない。
- テスト通知は明示ボタンからのみ送信し、画面表示や Streamlit rerun では送信しない。
- topic は実質的な秘密情報であるため、推測困難な値を使い、ログやスクリーンショットへ平文で残さない。
- 通常の自動テストと CI は fake transport を使い、ntfy.sh へ接続しない。

実装後の ntfy 初期設定手順:

1. ntfy アプリを端末へ導入する。
2. 推測困難な topic を作り、ntfy アプリ側で購読する。
3. SMAI の通知設定で ntfy を有効にする。
4. server URL は通常 `https://ntfy.sh`、セルフホスト時だけ管理対象 URL を指定する。
5. topic、severity threshold、quiet hours を設定する。
6. `テスト通知を送る` を1回実行し、アプリ内履歴と端末受信の両方を確認する。
7. 失敗時は topic 自体をログへ貼らず、server URL、時刻、HTTP status、短縮されたエラーだけで調査する。

詳細設計は `Documents/04_Detail_Design/04-10_Onepager_Notification_Platform.md` を参照する。

## 2026-06-27 Myウォッチリスト MVP

- `Myウォッチリスト` is available in the Streamlit side menu between `投資レーダー` and `SMAIアシスタント`.
- Favorites are stored locally in `data/user/favorites.json`. The app creates `data/user/` when saving, writes UTF-8 JSON with `ensure_ascii=false` / `indent=2`, and treats missing or broken JSON as an empty list with a warning instead of crashing.
- `☆ お気に入り` / `★ お気に入り中` buttons are shared by Ranking, Cockpit, and 投資レーダー related-symbol actions. Symbols are normalized by trim + uppercase and duplicates are ignored.
- The watchlist page shows saved symbol cards with local symbol metadata when available. Missing price / score / status-like fields are shown as `未取得`.
- Card actions move the selected symbol to Cockpit. `AI調査` and `レポート` keep external fetch / report generation as explicit follow-up actions in Cockpit rather than auto-running them.
- `data/user/favorites.json` is ignored by Git because it is user-local state.
- Phase 32-B connects favorites to 投資レーダー `Watchlist source`. Users can choose `Myウォッチリスト`, `My + 手入力`, or `手入力のみ`; combined mode de-duplicates symbols while preserving manual watchlist compatibility.
- Myウォッチリスト now supports `カード表示` / `テーブル表示`, local `ウォッチリストを更新` for last-checked timestamps, and memo / tags display. The update button is local-first and does not automatically run external fetch, AI調査, or Decision Report generation.
- Phase 32-C adds refresh metadata fields (`refresh_status`, `refresh_error`, `last_price_checked_at`, `last_news_checked_at`, `last_research_hint_at`) and status labels such as `未確認`, `古い`, `要確認`, `最新`, `前回失敗`.
- `ウォッチリストを更新` now updates prioritized non-fresh favorites up to the selected maximum count and stores a short `watchlist_refresh_summary` in session state. It remains local-first and does not auto-run provider fetch, AI調査, or Decision Report generation.
- The page-title mascot now supports `watchlist`; unknown title mascot keys fall back to the Investment Radar title asset instead of raising `KeyError`.
- Phase 32-C2 makes the shared favorite button state visually explicit: unregistered symbols use `☆ お気に入り` with a navy/blue-gray treatment, and registered symbols use `★ お気に入り中` with a restrained gold/amber treatment across Ranking / Cockpit / 投資レーダー / Myウォッチリスト entry points.
- Myウォッチリスト card display is now grouped into header, status badge row, refresh badge, metric cards (`価格`, `AI総合`, `上昇気配`, `下振れ警戒`, `最終確認`), confirmation information, and action buttons. Missing values remain non-fatal and display as `未取得` or `未確認`.
- The `watchlist` title mascot points to replaceable `smai-title-watchlist.webp`; if the file is not present yet, title rendering falls back to the Investment Radar mascot art.
- Investment Radar news-card related symbols now use one horizontal chip per symbol for `本文に出た銘柄` and `SMAI推測候補`: left side opens the symbol in Cockpit, right side uses the existing `☆ お気に入り` / `★ お気に入り中` favorite toggle. Empty / unclear symbols are skipped.
- Phase 32-D adds Decision Trail fields to `favorites.json` with backward compatibility: `watch_reason`, `decision_status`, `decision_note`, `next_check_at`, `next_check_label`, `decision_updated_at`, and `decision_trail`. Myウォッチリスト cards and tables show these fields, and each card has a compact `判断メモを編集` form.
- Phase 32-E adds a display-only `My Radar` summary and filter/sort controls. Radar priority uses refresh state, note completeness, tags, next-check date, and displayed local metrics only; it does not change Ranking score, AI総合, Research Score, provider fetch behavior, or the saved order in `favorites.json`.
- Phase 32-E2 keeps that logic and storage contract unchanged while compacting the daily workflow. My Radar shows five summary counts and keeps candidate reasons in `My Radarの判定理由を見る`; `最大更新件数` is under `更新オプション`; update/news actions remain explicit; empty Decision Trail cards show one `判断メモ: 未入力` state and an add form, while populated cards show the full decision details.
- Phase 32-F adds count-aware chip-style display filters and card state accents. When local rows contain `price_change_1d` / `price_change_5d` / `price_change_1m` or compatible `return_*` fields, cards show 1-day / 5-day / 1-month movement and classify `上昇傾向`, `短期上昇`, `横ばい`, `下落注意`, or `急落警戒`; missing / NaN values remain non-fatal.
- On the first Myウォッチリスト render in a session, up to three missing, failed, stale, or attention-needed favorites are registered once with the existing symbol DB background target queue. A six-hour `last_checked_at` TTL skips recent items. This path is daemon/non-blocking and local-cache-first; it does not automatically fetch live market prices, run AI調査, refresh external news, or generate a Decision Report. When external providers are disabled, the UI explicitly reports local-information-only confirmation.
- Through Phase 32-F, the explicit `ウォッチリストを更新` action remained a local refresh-metadata update. Phase 32-G replaces that implementation with the bounded snapshot update described below while keeping the same user-selected maximum and explicit-click requirement.
- Phase 32-G adds the user-local display cache `data/user/watchlist_snapshots.json` (`version: 1`, normalized symbol-keyed `snapshots`). It is separate from `favorites.json`, ignored by Git, UTF-8/Japanese-safe, and treats missing or broken JSON as an empty cache.
- Myウォッチリスト reads snapshot values first, then falls back field-by-field to current Ranking/Cockpit session results, symbol DB rows, favorite metadata, and finally `未取得`. Snapshot values include price, 1-day / 5-day / approximately 20-business-day change, copied existing AI総合 / 上昇気配 / 下振れ警戒, trend state, source/status/error, and snapshot timestamps.
- The explicit `ウォッチリストを更新` now selects at most the configured maximum, prioritizing missing/failed/stale snapshots. It fetches only OHLCV through the configured MarketData adapter; live providers are called only when `allow_external_providers=true`. Scores are copied from existing computed rows and are not recalculated or used to alter Ranking. Failed updates preserve prior values and mark the snapshot `failed`.
- Phase 32-G background behavior remains non-blocking candidate registration through the existing symbol DB queue: at most three symbols, six-hour TTL, once per session. It does not automatically run live OHLCV, AI調査, external News, Forecast/score recalculation, or Decision Report generation.
- Phase 32-H removes the normal-screen Radar-reason, update-options, and empty-note expanders. Filters are limited to `すべて`, `更新推奨`, `上昇傾向`, `下落注意`, `未取得`, and `メモ未入力`; sorting defaults to newest-added and exposes `確認優先度順` instead of the internal Radar term. Cards use three desktop columns, stronger restrained trend backgrounds, natural missing-data wording, and a subdued remove action.
- On the first Myウォッチリスト visit per session, eligible missing/failed/stale snapshot candidates outside the six-hour TTL are automatically refreshed up to three items while the shared loading mascot is visible. Worker-disabled sessions skip this path. Provider opt-in remains enforced by the Phase 32-G refresh service, prior snapshots survive failures, and AI調査 / News / Decision Report are not auto-run.
- Final runtime polish removes the empty `判断メモ` row completely, reads snapshot `price` before older row aliases, and uses the existing Cockpit preview calculation during bounded auto/manual snapshot refresh so AI総合 / 上昇気配 / 下振れ警戒 are persisted when calculation succeeds. The page title uses the dedicated star-play `smai-title-watchlist.webp` asset.
- Watchlist Groups adds an always-expanded `グループ別` view while preserving the existing
  `すべて` card/table view. Custom profiles save `watchlist_groups.json` below their profile;
  `SMAIデフォルト` keeps the same schema in Streamlit session only. Favorites and placements
  remain separate, one symbol belongs to at most one group, and unplaced or invalid-reference
  favorites appear in the final slate `未分類` section.
- Groups support a name, optional description, up/down display order, and one of eight preset
  tones (`cyan`, `blue`, `purple`, `green`, `amber`, `orange`, `rose`, `slate`). Creation
  chooses an unused tone first and then the least-used tone; creation/edit dialogs can override
  it. Deleting a group removes only its placements, so its favorite symbols return to `未分類`.
- The dedicated editor exposes a touch-safe destination select per symbol. Removing a favorite
  hides it without deleting placement, allowing a later re-favorite to restore the previous
  group. D&D is not enabled in this MVP.
- Watchlist Groups UI polish restores the original full-information Myウォッチリスト cards
  inside normal group sections and removes placement selects from those cards. Sections can be
  opened/closed in session; a closed header keeps its name, count, description, and up to three
  representative symbols visible. The Cockpit CTA uses the existing
  `Cockpit画面で確認` wording.
- `グループを編集` opens a large dedicated editor. Group add/name/description/tone/delete and
  a multi-container D&D chip board update `watchlist_groups_edit_draft` only;
  `保存して閉じる` atomically persists the complete validated state, while `キャンセル`
  discards it. Chips show only symbol/name; dragging across groups changes placement and
  dragging within a group changes `order`. The component is provided by pinned
  project-owned `ui/components/watchlist_sortable` component. Its D&D implementation follows
  the earlier Apache-2.0 sortable component approach, while adding SMAI-specific group actions.
- D&D uses stable group IDs and normalized symbol IDs; display labels are not identifiers.
  Cross-container previews calculate from the latest local state, invalid indexes are ignored,
  and cancel / outside-drop restores the drag-start snapshot. Python accepts only a complete
  payload containing every known container and symbol exactly once. No-op payloads leave the
  draft untouched. The board uses a fixed component key with monotonic client sequences and server
  acknowledgments, so stale rerun props cannot replace newer local moves and drops do not remount
  the iframe. Collision detection prioritizes the chip
  directly under the pointer, falls back to the containing group, and retains the last valid target
  while crossing gaps. Wrapped groups keep a visible tail drop lane even when chips fill a row.
  Every custom group container has its own `↑` / `↓` / `編集` controls in the D&D header;
  `未分類` has no mutation controls. Order changes remain draft-only until `保存して閉じる`,
  and `編集` opens only that group's inline settings. There is no shared selector toolbar,
  lower per-group editing stack, or duplicated expander list.
  On the normal screen, the top-level `グループを編集` action is the only group mutation entry
  point. Clicking a tone-colored group header expands/collapses it; separate create, close, and
  per-group edit buttons are not rendered. The configured tone covers the complete normal-screen
  group panel (header, description, cards, and actions), while card-specific status accents remain
  unchanged. Tone classes also use per-container backgrounds inside the editor component. On touch devices, draggable
  chips suppress page pan and text selection during a drag; surrounding group/drop-zone space
  remains available for normal scrolling.
- Watchlist card actions distinguish in-place review from navigation. `銘柄を詳しく見る` opens the existing Ranking-style wide `銘柄データ` dialog with snapshot values and its `AI Research` tab; AI Research loading stays inside the dialog instead of blocking the full app. The old card-level `AI調査` / `レポート` navigation buttons are removed. `Cockpit画面で確認` remains the explicit page transition and uses a separate visual treatment, while `解除` stays subdued.

## 2026-06-26 Symbol Metadata Operations Update

- `tools/normalize_symbol_universe_quality.py` backfills missing `*_source` / `*_as_of` / `*_quality` fields from existing metadata and can optionally mark obvious outliers as `suspicious`.
- `tools/run_symbol_universe_metadata_batch.py` now supports checkpointed live refresh review with `chunks.jsonl`, chunk manifests, `failed_symbols.csv`, and `no_update_symbols.csv`.
- `tools/export_symbol_universe_metadata_gaps.py` is the reviewed patch candidate exporter for low-coverage markets and targeted metrics such as Korea `pbr`.
- `tools/apply_symbol_universe_metadata_patch.py` preserves `source_url` both as provenance and as `manual_source_url:<url>` in `data_quality_reasons`.

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\normalize_symbol_universe_quality.py --write
.\venv_SMAI\Scripts\python.exe .\tools\run_symbol_universe_metadata_batch.py --preset weak-asia --provider yahoo --allow-live --fill-missing-only --write
.\venv_SMAI\Scripts\python.exe .\tools\export_symbol_universe_metadata_gaps.py --preset korea-pbr
.\venv_SMAI\Scripts\python.exe .\tools\apply_symbol_universe_metadata_patch.py --patch data\marketdata\manual_metadata_patches\korea_pbr_manual_patch_33rows.csv --write
```

## 1. 目的

この文書は、現在の Smart Market AI MVP をローカルで起動、確認、説明するための運用ガイドです。
API 仕様、CSV provider、Streamlit UI、手動確認、外部 provider の扱いをこの 1 ファイルに集約します。

## 2. 現在の MVP 範囲

実装済み:

- FastAPI backend
- `GET /health`
- `POST /risk/pre-trade-check`
- `POST /portfolio/rebalance-check`
- `POST /screening/score`
- `POST /forecast/evaluate`
- `POST /scoring/investment-score`
- 既定の `yahoo` live MarketData provider
- テスト / オフライン確認用の deterministic `mock` / `csv` MarketData provider
- Feature Snapshot / Screening Score / Forecast Evaluation / Investment Score
- Portfolio-to-Risk rebalance-check workflow
- Decision Report context / Markdown / JSON / manifest / ZIP export for cockpit, ranking, and rebalance
- Research RAG Phase 20 local evidence slice
  - local UTF-8 document registration, chunking, keyword evidence search, Research Summary / ResearchBrief
  - Settings upload, Cockpit `AI調査を更新`, Ranking modal `AI Research`, Cockpit Decision Report Research Evidence / Research Score
- Performance Profile first slice
  - `SMAI_PERFORMANCE_PROFILE=notebook|workstation` で、Research RAG external fetch の最大並列数、request timeout、global timeout を切り替える
  - 未指定時は `notebook`。未知のprofile名は warning を出して `notebook` にfallbackする
  - Phase 3Aで Research external fetch の provider -> profile source key mapping、source別実行summary、HTTP取得の retry / backoff、source別 limiter入口を追加
  - global timeout 到達時は取得済みpartial resultを返し、未完了providerを `timeout` として source summary / UI に残す
  - News dashboard cache / MarketData live provider / Symbol DB background refresh への共通profile適用は後続範囲
- News dashboard cache/update backend foundation
  - `NewsDashboardSnapshot` / `NewsUpdateStatus` contracts, latest snapshot cache, one-generation backup, atomic save, bounded cleanup, cache-size/status helpers
  - TTL / minimum-interval skip, bounded retry, failure fallback, rotating update logs
- Symbol database background refresh foundation
  - freshness classification, refresh priority queue, queue/status recovery, latest-only normalized symbol cache
  - Streamlit startup daemon worker that updates missing / stale local symbol records without blocking rendering
  - Cockpit selected symbols and Ranking comparison targets are registered as background priority hints without adding user-facing controls
  - Cockpit `データを取得` prioritizes price / forecast rendering, then registers the selected symbol for background priority refresh with a 30-minute in-session TTL
  - Ranking `ランキング作成` runs a bounded target preflight refresh before ranking creation
  - Cockpit selected-symbol caption and the shared Ranking / Cockpit `銘柄データ` modal show saved symbol DB freshness, source, update times, and missing key fields
- Phase 23 Advanced Forecast adapter registry + `advanced_linear` / `advanced_tree_sklearn` / `advanced_gbdt_sklearn` / `advanced_quantile` backend + API + Cockpit + Ranking auxiliary display slice
  - `advanced_linear` forecast adapter foundation for Cockpit / Ranking
  - `advanced_tree_sklearn` forecast adapter using scikit-learn `ExtraTreesRegressor` by default for nonlinear feature interaction checks
  - `advanced_gbdt_sklearn` forecast adapter using scikit-learn `HistGradientBoostingRegressor` for boosting-style nonlinear checks
  - `advanced_quantile` forecast adapter for deterministic historical forward-return range checks
  - advanced forecast consensus layer that conservatively combines registered advanced adapters at one common horizon using confidence, error improvement, model agreement, and validation sample context
  - `POST /forecast/evaluate` accepts `adapter=advanced_linear`, `adapter=advanced_tree_sklearn`, `adapter=advanced_gbdt_sklearn`, or `adapter=advanced_quantile` with `horizon_days` 1-60 and returns predicted return, forecast close, validation metrics, confidence, and warnings. `advanced_quantile` also returns lower / upper predicted return and forecast close range fields.
  - Cockpit overlays advanced forecast context on the existing price / forecast chart using the same period-derived horizon as baseline forecasts. The default horizon is roughly one twelfth of the displayed period and capped at 60 days. The initial chart emphasizes actual price, `AI予測インサイト` as the consensus line, and its lower-to-upper prediction range band; advanced model lines and simple forecast lines can be added with two grouped chart checkboxes that only filter already-built chart rows, while the fixed-color chart legend dims individual displayed series. Individual advanced model cards remain visible below the chart for detail confirmation. Naive / moving-average / momentum simple forecasts stay available as backend baseline / detail context, but are not part of the default Cockpit chart or main model-card display. The chart legend sits below the chart, the right forecast-focus chart is titled `予測スコープ`, and the full chart restores small point markers while keeping the actual-price line thinner. `表示通貨` は JPY / USD の二択にし、取得通貨が JPY なら円、USD なら $、それ以外または古い状態値なら円を初期値にする。取得済み USDJPY レートはラジオボタン右横に `＄円相場` として短く表示する。換算はチャート表示だけで、スコア、予測計算、Ranking には影響しない。
  - Ranking rows retain one period-derived common-horizon advanced forecast consensus return (`advanced_forecast_predicted_return`), horizon days, score, confidence, and AI総合用の高度予測上昇 / 下降警戒 / 信頼スコア. Ranking の上昇気配 / 下降警戒にはAI予測インサイトを25%までブレンドし、`AI総合` はこれらを `予測・上昇気配30%` / `リスク・下振れ警戒25%` の中で低信頼時に中立寄せしながら加味する。Ranking の理由表示、深掘り候補、score detail、Decision Report でも同じ文脈で説明する
  - Ridge-style lightweight deterministic forecasting, scikit-learn tree ensemble / histogram gradient boosting forecasting, and quantile range checks for 1-60 day forward returns
  - walk-forward / time-series validation, validation metrics, confidence, and feature contribution summary
  - designed to keep normal checks network-free; `scikit-learn` is pinned in setup requirements for tree / boosting adapters
- Low-cost Assistant backend first slice
  - deterministic `TemplateAssistantService` that explains score / risk / research / next checkpoints from Decision Report context without LLM or network
- Low-cost Assistant Streamlit / Agentic first slices
  - Cockpit / Ranking show a fixed floating `SMAI Copilot` mascot. The panel registers the current page / section context and, in the default config, uses question chips to explain what to check next without running price fetch, ranking creation, network calls, or LLM calls.
  - Cockpit contexts currently cover data setup, `AI予測インサイト`, `上昇気配・下降警戒`, and Decision Report. Ranking contexts cover ranking setup, ranking results, and selected deep-dive candidate checks.
  - SMAI parent can optionally call `smai-ai-gateway` `/api/v1/context-answer` through `assistant.gateway.enabled=true`. The default remains disabled, schema-validated, and deterministic fallback is used on timeout, Gateway error, invalid JSON/schema, empty answer, or missing context.
  - Side menu includes `SMAIアシスタント`, a dedicated conversation workspace with a SMAIナビ header, material chips, 6 guided intent cards, 240-character limited free text, session-local history, a centered single-column chat layout, a chat-width `新しい会話` action, compact per-response actions, one-at-a-time current pending step display, grouped pseudo-streaming answer display, and Markdown memo export. The first SMAIナビ utterance appears only after the user submits text or selects a card. Normal submit updates the chat placeholder from pending to final answer without an extra post-submit rerun. Free text is routed through a rule-based Intent Router and read-only `Assistant Tool Layer`; executed checks are shown as `実行した確認`. Clear research requests such as `トヨタはこれから上がるかな？` stop at a chat-thread Tool Plan card with approve / cached-only / cancel actions before any external fetch. When the user selects `取得して分析する`, planned `news_fetch` / `research_fetch` tools can call the existing transient `AI調査を更新` external-source path and compress source URL / provider / published_at / freshness warning into the Assistant answer and Decision Report draft. `取得済み情報だけで回答` and `キャンセル` remain network-free.
- `SMAI LLM Factor` SMAI-side first slice
  - `backend/llm_factor` provides `LLMFactorResult` / factor / evidence schemas, source hash retention, deterministic fake service validation, and a file-backed cache with generated_at / expires_at / model / prompt version metadata.
  - `run_llm_factor_backtest(case)` provides a deterministic fixture-based evaluator for LLM material scores versus forward returns / drawdowns. It is an exploratory alpha-factor diagnostic, not a trading strategy backtest.
  - `load_llm_factor_historical_fixture_pack()` and `run_llm_factor_validation_report(fixture_pack, config)` provide the broader deterministic validation phase. The fixture pack covers domestic large caps, US large caps, ETFs, high-dividend names, growth names, low-news-coverage names, Osaka Gas `9532.T`, and mixed global segments. The report exports JSON / Markdown and covers Accuracy, Precision, Recall, F1, AUC, Top-N return, top-bottom spread, Sharpe Ratio, maximum drawdown, baseline comparison, segment metrics, and validation warnings.
  - Phase 27-A / 27-B adds optional live generation through `smai-ai-gateway` `/api/v1/llm-factor/generate`, compact Cockpit context, HTTP adapter, `llm_factor.v1` validation, live cache keys by context / prompt / schema / model / profile, standardized fallback reasons, and a live smoke guide at `Documents/27B_LLM_Factor_Live_Smoke.md`.
  - Cockpit shows `AI材料分析` as a reference-only panel under `05 根拠資料` using existing Research / News / external-source context when available. It is not blended into Forecast, Ranking, Investment Score, or Research Score.
  - Provider, model, profile, generated time, fallback reason, validation warnings, missing fields, and cache captions are kept in closed detail expanders so the normal UI reads as material interpretation rather than runtime diagnostics.
  - Ranking shows display-only AI material reference columns only when `詳細列を表示する` is enabled: `ニュース材料`, `材料件数`, `材料信頼度`, and `材料の新しさ`. Cache hits reuse cached `LLMFactorResult`; cache misses use deterministic fake values. These columns are non-sortable reference information and do not change Ranking score, rank, Forecast, Investment Score, or default order.
- Cockpit LLM Interpretation
  - Phase 28-A adds a Cockpit-only `AI解釈メモ` reference panel. It compresses visible Cockpit price / forecast / Investment Score / Research Evidence / AI材料分析 into `AssistantContextBundle`, calls Gateway `/api/v1/context-answer` with `task_type=cockpit_interpretation` only when `llm_interpretation.cockpit.enabled=true`, validates the response, caches by context / prompt / schema / model / profile, and falls back to a deterministic reading memo when disabled or unavailable.
  - Phase 29-A moves this panel to the main reading entry as `03 AI解釈メモ`; strong points, cautions, contradictions / uncertainty, and next checks stay visible, while runtime metadata and cache information sit in a closed detail expander. It does not modify Ranking, Forecast, AI総合, Investment Score, Research Score, Assistant tool execution, or Decision Report contents.
  - Cockpit's normal post-forecast flow is `03 AI解釈メモ` -> `04 スコア・リスクの内訳` -> `05 根拠資料` -> `06 確認レポート` -> `07 詳細データ`.
- Streamlit UI
  - Market Data: `銘柄コックピット` / `銘柄ランキング`
  - Investment News: `投資レーダー` dashboard with news stream, heatmap, category lanes, and related-symbol cockpit handoff
  - Rebalance: summary flow / allocation comparison / risk confirmation
- JSON / CSV / Markdown / manifest / ZIP export
- file-backed rebalance scenarios

未実装または将来範囲:

- `polygon` などの追加 live provider adapter 本体
- 追加 provider adapter / fund metadata source
- 追加 Research RAG external source adapters / vector search の運用UI
- Research Score によるランキング順位統合は現時点では見送り。Cockpit / Ranking Research Summary と Cockpit Decision Report への参考表示、Investment Score optional numeric input、disabled-by-default weight は対応済み
- `投資レーダー` dashboard の追加ニュースprovider、詳細フィルタ、Watchlist連動、通知
- Advanced Forecast ranking logic: Ranking retains and displays common-horizon advanced forecast fields, blends consensus-derived advanced upside / downside into Ranking direction signals at 25%, and `AI総合` includes advanced upside / downside / quality as part of a tuned 30/30/25/10/5 evaluation profile. Other ranking profiles are tuned as comparison policies but still do not use LLM Factor or live interpretation results.
- `反転期待` is an independent Ranking exploration policy. It combines pullback state 30%, forecast upside room 30%, downside safety 20%, company/data quality 10%, and early reversal setup 10%, then applies hard caps for poor data quality, high downside warning, low risk confirmation, excessive drawdown, non-positive forecast, no upward models, and sharp recent decline. It never overwrites `total_score`. Ranking, Cockpit, Myウォッチリスト snapshots, Ranking History, Assistant context, and Decision Report retain the same score, label, reason, and supporting fields. Treat it as a further-review priority, not buy advice.
  - When selected, the Ranking condition card shows a beginner summary and the exact 30/30/20/10/10 formula. `反転期待スコアの詳しい計算方法を見る` shows component inputs, the 20-day-high pullback point bands, 5-day-return adjustments, and every hard-cap threshold.
- `SMAI LLM Factor` の予測モデル統合は後続範囲。実 LLM/Gateway 接続MVP、live smoke手順、cache / TTL / reproducibility、Ranking 参考カラム、deterministic backtest evaluator、broader historical fixture pack、extended validation report は実装済み。既存予測モデル / Ranking score / rank / Forecast / Investment Score には検証完了前に混ぜない
- Cockpit `AI解釈メモ` は Phase 28-A MVP として実装済み。Phase 29-Aで主導線を `03 AI解釈メモ` -> `04 スコア・リスクの内訳` -> `05 根拠資料` -> `06 確認レポート` -> `07 詳細データ` に整理済み。Ranking / Radar / News / Decision Report への展開、Assistant からの画面説明連携、Decision Report への自動挿入は後続範囲
- Assistant の長い会話履歴、参照文脈の本格拡張は後続範囲。Streamlit の floating `SMAI Copilot` question-panel、専用 `SMAIアシスタント` workspace / limited free-text / live Gateway first slice、SMAI 親側の Gateway HTTP client wiring と opt-in live smoke path、承認後 `news_fetch` / `research_fetch` の外部取得MVP、Decision Report下書き保存/archive UX MVPは実装済み
- 銘柄DB live provider refresh wiring は background refresh 基盤実装済み後の provider / opt-in 接続タスクとして扱う
- broker への live order 送信
- Execution workflow
- PDF / Excel export

現在の MVP は、ローカル検証と説明用です。
MarketData と Research / News の標準導線では外部 source を使いますが、通常検証は fake / fixture / mock config で network-free に保ちます。broker や execution provider への注文送信は行いません。
Research RAG / News RAG は実運用では情報鮮度が重要です。標準導線では、`AI調査を更新` が EDINET securities-report metadata/link（`EDINET_API_KEY` 設定時のみ live call、未設定時 no-op）、TDnet 適時開示、企業IRサイト、Google News RSS headline search、Yahoo Finance profile / news を取得/参照し、source URL、provider、published_at、fetched_at、freshness warning を確認材料として表示します。Yahoo Finance を使う Research 側 adapter は MarketData 側と同じ yfinance cache / shared session 設定を使います。Google News RSS は一般ニュースのヘッドライン幅を広げる補助sourceで、検索語は会社名・関連キーワード・銘柄コードに決算/業績/株価/配当などの投資文脈語を添えます。ニュースURL表示自体は `外部参照ソース` と詳細データに実装済みです。Cockpit Research Summary では、`最新ニュース・開示サマリー` の直後に `投資ヒントとなるニュース` と `ニュース・開示の出典を表示（URL付きN件）` を置きます。サマリと注目材料は `Market Intelligence` の主表示カードとして扱い、出典は初期折りたたみの小さな citation list としてURL付きニュース・TDnet・企業IR・EDINET・Google News・Yahoo Finance を確認できるようにします。ニュース専用URLが無い場合も、外部参照ソース側に公式資料・provider URLがある可能性を案内します。取得本文は既定では保持せず、session-local の一時参照として扱います。通常検証は fake adapter / fixture / RSS fixture を使い、network 非依存を維持します。

外部取得の実行環境profileは `SMAI_PERFORMANCE_PROFILE` で選択します。`notebook` は Research external fetch profile上限4 workers / provider timeout 12秒 / global timeout 30秒 / cache TTL 30分、`workstation` はprofile上限10 workers / provider timeout 15秒 / global timeout 45秒 / cache TTL 20分です。実際の worker 数は profile 上限と external source adapter 数の小さい方に抑えます。現時点でこのprofileが実際に制御するのは `DefaultExternalResearchAdapter` の並列度、全体待ち時間、source別 limiter入口、EDINET / TDnet / 企業IR / Google News RSS の request timeout と retry / backoff です。provider名は `edinet -> edinet`、`tdnet -> tdnet`、`company_ir_site -> ir_pages`、`google_news_rss -> news`、`yahoo_finance -> yahoo_finance` に正規化します。HTTP 5xx、timeout、一時的な接続失敗はretry対象、HTTP 4xx / 404、データなし、parse error はretry対象外です。global timeout 到達時は取得済み情報だけを返し、未完了providerを `timeout` として `ExternalResearchFetchResult.provider_statuses`、直近summary、Cockpitの外部参照ソース確認メモ、Streamlit `設定 / データ情報` に残します。直近summaryには source別に `success / failed / timeout / no_result / cache_hit`、elapsed、retry回数、result数を保存します。`processing.rag_workers`、`forecast_workers`、`background_refresh_workers`、`llm_workers` は設定として保持しますが、共通適用は後続フェーズです。`SMAI_LLM_PROFILE` はLLMモデル選択用であり、この performance profile とは分けて扱います。Yahoo/yfinance timeoutの本格適用、adapter内部のURL/page単位並列化、News / MarketData / Symbol refresh へのprofile適用は後続範囲です。

親SMAIの汎用 Assistant service から Gateway 接続を試す場合は、SMAI 側の `SMAI_CONFIG_FILE` に次のような設定を指定します。通常確認やCIではこの設定を使わず、`enabled: false` の既定値を維持します。専用 `SMAIアシスタント` workspace と親SMAIの `HttpAssistantGatewayClient` は、`http://127.0.0.1` / `localhost` の `smai-ai-gateway` が未起動なら画面遷移時の診断またはチャット送信時に自動起動を一度試し、失敗時は同じ画面内で deterministic fallback に戻ります。自動起動を無効にする場合は `SMAI_ASSISTANT_GATEWAY_AUTOSTART=0` を指定します。

```yaml
assistant:
  gateway:
    enabled: true
    base_url: "http://127.0.0.1:8088"
    context_answer_path: "/api/v1/context-answer"
    timeout_seconds: 90
    execution_mode: "auto"          # auto|light|quality|off
    environment_profile: "notebook" # notebook|desktop|server|offline
```

SMAI 親は通常 `model` を固定指定せず、`task_type` と環境ヒントだけを Gateway に渡します。Gateway 側が `notebook_dev` / `notebook_standard` / `desktop_fast` / `desktop_analysis` / `desktop_heavy` から model / timeout / token budget を選び、分析・整理系の応答下部には `qwen3:1.7b / live / notebook_dev / ollama / stock_summary / 4230ms` のような控えめなメタ情報を表示します。通常会話、自己紹介、できること案内では技術メタ情報を表に出さず、自然な会話表示とコピー操作だけにします。ノートPC開発の既定は `qwen3:1.7b` で、SMAIアシスタント上部の小さなモデルピッカーから `qwen3:4b` / `qwen3:8b` / `qwen3:14b` / `qwen3:30b` profile へ切り替えられます。親側 HTTP timeout 既定はローカルLLMの実測に合わせて 90 秒です。Gateway / provider / model / timeout / schema / empty-answer 失敗時だけ deterministic fallback に戻り、その場合は `fallback: gateway_unavailable`、`fallback: provider_unavailable`、`fallback: model_not_found`、`fallback: provider_timeout` のように理由を分けます。開発用 metadata として `request_id`、`timeout_sec`、`context_tokens_estimate`、`prompt_chars`、`response_chars`、`tool_execution_ms`、`llm_generation_ms`、`total_elapsed_ms`、conversation mode、`gateway_error_type`、`gateway_error_message`、`gateway_url`、`http_status`、`provider_error_type`、`provider_error_message` も保持し、分析・整理系の回答では通常本文ではなく `技術情報を表示` にだけ出します。SMAIアシスタントのヘッダーは `AssistantRuntimeStatus` を唯一の表示モデルとして使い、初期表示では自動ヘルスチェックで赤エラーにせず `LLM待機中` として表示し、model変更 / 送信開始 / LLM成功 / fallback / Tool Plan表示 / Tool実行 / キャンセル / 新しい会話で更新します。表示は `準備完了`、`LLM待機中`、`接続確認中`、`回答生成中`、`調査計画あり`、`材料確認中`、`簡易モードで回答中`、`LLM接続エラー`、`Ollama未接続`、`モデル未取得` に整理し、成功時は古いエラーを消して `準備完了` に戻します。通常focusの入力欄はcyan系、validation error時だけ赤系の枠にします。

LLM Tool Planner を試す場合は、別設定 `assistant.llm_planner` を明示ONにします。既定は `enabled: false` で、通常確認・CI・Playwright smoke は network-free の deterministic Tool Plan / Guided Workflow を使います。ONの場合も Gateway `/api/v1/assistant/tool-plan` は action案のJSONを返すだけで、SMAI 親側が schema / action allowlist / confirmation / unsafe wording / unsupported action を検証し、valid plan だけを既存の `次にできること` / `確認フロー` に採用します。invalid / timeout / Gateway fallback / malformed response は非表示にし、fallback reason は `技術情報を表示` にだけ保持します。

Phase 30-Hでは、SMAIアシスタント初回描画時に `assistant.warmup` 設定でbackground LLM warmupを開始します。初期値は health timeout 3秒、全体timeout 15秒、chat warmupはOFFです。画面描画はwarmupを待たず、準備中でもSMAI標準ナビと安全な確認フローを利用できます。Gateway / provider / model確認が失敗またはtimeoutになった場合もdeterministic fallbackで継続し、永久スピナーにはしません。

準備中カードの市場ヘッドラインは `data/cache/news_dashboard_snapshot.json` の前回取得キャッシュを最大5件使い、キャッシュなし・破損時はbundled sampleへ戻ります。ロード表示のための同期外部ニュース取得は行いません。古いキャッシュは `前回取得` と最終更新時刻を表示します。

Assistant loading UIは投資レーダーの既存マスコットassetを小さなヘッダーアイコンとして表示し、assetを読めない場合はCSSレーダーへ切り替わります。LLM起動確認中は2秒間隔でwarmup状態だけを軽量確認し、準備完了後は手動更新なしで通常チャット画面へ1回だけ自動遷移します。timeout / Gateway未接続時も同様に監視を終了し、`fallbackあり` の表示とSMAI標準ナビ、入力欄、既存のchat/workflow sessionを維持します。

追加の30-H recovery sliceでは、warming / retrying / model loading中だけmain領域をモーダルで覆い、sidebarは操作可能なまま維持します。Gateway未接続、provider未接続、model missing、timeoutを区別し、既定で最大3回を軽いbackoff付きで自動確認した後はfallbackへ移行します。再接続はstartup warmupが自動処理し、ユーザー向けの再接続ボタンは表示しません。

モデル選択はGateway `GET /models` から取得できた実在モデルだけを使います。取得後の優先順位は画面での明示選択、利用可能な中で最も高性能なモデルです。設定modelは一覧取得前の接続確認だけに使い、一覧取得後のdefaultを固定しません。モデル一覧を取得できない間はselectorを無効表示にし、固定候補を補いません。チャットはメッセージ件数が増えた時だけ末尾へ自動スクロールし、通常rerunではスクロールを強制しません。

モデル変更UIはchat input横の単一 `AIモデル` selectboxです。選択肢には取得済みmodel名と特色・負荷感をまとめて表示し、用途profileの別radioや内部名（`notebook_dev` など）は表示しません。初回は取得済みmodelの性能順topを選び、ユーザーが変更した後はそのmodelをsession内で保持します。selectboxとchat input / 送信ボタンは画面下部へ常時固定し、モデル選択理由・LLM接続先・一般注意文の補助captionはcomposer下へ重ねて表示しません。

Loading modalの市場ヘッドラインは、キャッシュ済みニュースを最大5件だけ表示します。市場全体、日本・米国株、決算、金利・為替、その他の順で優先し、各項目をカテゴリbadge、最大2行title、source / `前回取得` metadataに分けたmini news cardとして表示します。古いcacheでは前回取得記事であることを補足し、cacheがない場合は同期的な外部取得やdemo記事を使わず、`市場ヘッドラインを準備中です` の案内へ切り替えます。

Phase 30-G1 の Workflow Session は親SMAI側だけの session-local runtime です。validation gate を通った `AssistantGuidedWorkflow` だけを `AssistantWorkflowSession` に変換し、`SMAIアシスタント` の `確認フロー` カードに進行状態と現在stepを表示します。`update_research` / `create_decision_report` は従来どおり確認カードでユーザーが押した1 actionだけを実行し、成功・一部成功・失敗・キャンセルの結果を session step に反映します。`update_research` 成功後に `create_decision_report` が確認待ちになっても自動実行はしません。失敗時は session を failed にし、同じターンで Tool Plan 由来の確認promptへ自動fallbackしません。Gateway は workflow session、action execution、skip/cancel 状態管理を担当しません。

Phase 30-G2 では、この session に最小限のUI操作を接続しています。active session では `AI調査をスキップ` / `レポート作成をスキップ` / `フローを中止` を表示し、failed session では `AI調査をもう一度更新` / `今ある材料で確認` / `フローを中止` を表示します。`もう一度更新` は step を確認待ちに戻すだけで、ユーザーが改めて確認カードを押すまで外部取得しません。`今ある材料で確認` は失敗したAI調査更新を skipped にし、確認レポート作成など次のstepを確認待ちにするだけです。スキップや中止も session-local JSON 更新だけで、保存・外部取得・スコア変更・broker操作は行いません。

```yaml
assistant:
  llm_planner:
    enabled: true
    gateway_url: "http://127.0.0.1:8088"
    endpoint_path: "/api/v1/assistant/tool-plan"
    timeout_seconds: 15
    max_steps: 5
    fallback_to_deterministic: true
    show_source_details: false
    execution_mode: "auto"
    environment_profile: "notebook"
    preferred_profile: "assistant_fast"
```

Gateway 接続失敗時も `TemplateAssistantService` に戻るため、SMAI の予測、ランキング、Investment Score、Research Score、LLM Factor 参考列は変更されません。

`SMAIアシスタント` workspace はサイドメニューから開けます。初期表示では、SMAIナビのヘッダー、参照中の材料チップ、チャット幅に揃えた `新しい会話` アクション、`SMAIの使い方を聞きたい`、`この銘柄を整理したい`、`予測とリスクを比べたい`、`ニュース材料を見たい`、`Decision Reportを作りたい`、`自由に会話する` の6カード、入力欄を表示し、最初のSMAIナビ発話はユーザーが送信またはカード選択した後にだけ出します。自由入力はルールベース Intent Router で `app_help` / `identity` / `capability_help` / `stock_summary` / `forecast_risk_compare` / `news_materials` / `decision_report_draft` / `free_chat` に正規化し、旧intent由来の `forecast_check` / `chart_check` / `rag_search` / `file_export` は表示用にそれぞれ予測比較・銘柄整理・ニュース材料・Decision Report下書きへ寄せます。さらに `Command Center / Research Mode` の初期スライスとして、自由入力を `normal_chat` / `soft_research_suggestion` / `research_plan` に判定し、明確な調査依頼ではTool Planカードを表示して、`取得して分析する` / `取得済み情報だけで回答` / `キャンセル` の選択を先に残します。Tool Planカードは対象を可能な範囲で `銘柄名（コード）` として表示し、`銘柄を特定`、`価格の動き`、`AI予測・下振れ警戒`、`最新ニュース`、`根拠資料 / Research Evidence` のようなユーザー向け項目名にします。`取得して分析する` 後はchat thread内のSMAIナビbubbleで、完了項目をチェック、実行中項目を `確認中` として表示します。承認後実行はread-only `Assistant Tool Layer` の結果に加え、計画に `news_fetch` / `research_fetch` が含まれる場合だけ既存 `fetch_external_research_for_symbol()` 経路を呼び、source URL、provider、published_at、freshness warning、短い要約を `AssistantResearchContextBundle` に圧縮します。取得失敗時も回答全体は落とさず、failed / missing / caution として既存材料中心で継続します。`取得済み情報だけで回答` では外部取得を行わず、外部取得予定だった項目を未確認材料として残し、取得済み範囲に絞ることと不足材料を明示します。`キャンセル` では外部情報を取得せず、必要になったら再依頼できる自然な返答にします。`Decision Reportに追加` 後は下書きプレビューを表示し、`下書きを保存` で `exports/decision_reports/` にMarkdown、ZIP、`assistant_decision_report_manifest.json` を保存します。`Markdown保存` はブラウザの単体Markdownダウンロード、`ZIP保存` は `report.md` と `manifest.json` のダウンロードです。保存内容はユーザー質問、対象、Assistant回答サマリ、確認済み材料、未確認材料、注意点、次に確認すること、source URL、freshness warning、Tool Status、取得条件です。外部取得本文、provider raw fields、debug logs、raw exception、request_id、latency、Gateway内部情報、LLM内部思考は保存しません。read-only `Assistant Tool Layer` は現在文脈、銘柄推定、価格、予測、ニュース/RAG、Decision Report下書きに必要な安全な確認だけを実行します。回答はLLM / Gatewayの自然な会話応答を主役にし、SMAI側のread-only Tool Layerで確認した材料を補助情報として渡します。Gateway接続時は固定リード文を付けず、LLMが会話文脈とTool結果を読んで必要な範囲で回答します。通常送信では、チャットスレッドのplaceholder内で待機中カードを出し、その同じ場所を最終回答に差し替えます。送信直後の待機中カードには、`現在の処理` として `銘柄を確認中`、`価格・予測材料を確認中`、`ニュース材料を整理中`、`LLMへ回答作成を依頼中` のような intent 別ステップを1件だけ表示し、約0.34秒ごとに次の現在処理へ切り替えます。最新ターンではUI側の擬似ストリーミングで本文を文またはまとまり単位に段階表示し、更新間隔は約0.16秒に抑えます。pending / assistant カードには最小高さを設定し、回答差し替え時の縦方向の跳ねを抑えます。その下に必要な場合だけintent別の構造化整理、実行した確認、LLM / fallbackメタ情報を控えめに表示します。会話履歴は中央1カラムに集約し、ユーザー発話は右寄せ、SMAI応答は左寄せ、入力欄は同じカラム幅に揃えます。通常設定では deterministic fallback の説明を使い、価格取得、ランキング再作成、スコア変更、予測値変更、売買推奨は行いません。Gateway接続が使える場合は /api/v1/context-answer へintent別prompt guideとTool結果を渡し、失敗時は同じ画面内で deterministic answer に戻ります。

Assistant response policyでは、雑談・自己紹介・用語説明に機能導線カードを出さず、通常回答とSMAI内での使われ方の補足に留めます。銘柄未指定の広い相談はテーマ/セクター探索として扱い、銘柄特定や外部ニュース取得を必須にしません。ランキング、コックピット、ニュース取得、比較、レポート作成などのカードはユーザーが明確に希望した場合だけ表示し、外部取得とDecision Report作成の実行前確認は維持します。SMAIナビは売買推奨ではなく、確認材料と使い方を整理します。

回答下部には `コピー`、`Markdownで保存`、`Decision Reportに追加` のアクションを小さなリンクとして表示します。MVPではブラウザのダウンロードリンクでMarkdown memoを作成し、永続Decision Report保存や自動ファイル大量生成は行いません。Markdown memoには `実行した確認`、確認した材料、強気材料、弱気材料、未確認事項、次に確認すること、SMAIナビの整理、売買推奨ではない注記を含めます。

Investment News dashboard はサイドメニューの `投資レーダー` から開けます。現時点では `backend/news` の snapshot / status / cache / refresh manager と deterministic dashboard builder を使い、保存済みsnapshotがなければ fake snapshot / fixture から市場ニュースヘッドライン、株式ヒートマップ風の投資ヒートマップ、3列のカテゴリ別ニュースカード、銘柄名付き関連銘柄の `銘柄コックピット` 導線を表示します。ニュースカードの関連銘柄は、本文に出た銘柄を最大8件まで優先表示し、残り枠に `SMAI推測候補` を補完します。投資ヒートマップはニュースに直接紐づいた関連銘柄だけでなく、ローカル銘柄ユニバース全体からカテゴリ適合、時価総額帯、データ品質、ニュース鮮度、材料タイプ、市場シグナルを見て注目度順の銘柄タイルを補完します。市場指標がある場合は値動き / 取引量を使い、欠ける場合はニュース材料から代理シグナルを補完します。銘柄タイルは企業名を主、シンボルを補助タグとして表示し、クリックすると同一アプリ内の該当 `銘柄コックピット` へ移動します。Investment Score / Research Score / Ranking order は変更しません。詳細フィルタ、Watchlist連動、通知、追加providerは後続範囲です。

### SMAI Assistant free_chat runtime note

SMAIアシスタントの自由会話 `free_chat` は、体感速度を優先する軽量経路です。SMAI 親側では銘柄特定 tool、RAG、news、長い会話履歴、銘柄固有 context を送らず、Gateway には短い user question と最小 context だけを渡します。Gateway 側は task_type を主軸にしつつ、実際の Ollama model ごとに token budget を調整します。軽量会話の目安は `qwen3:1.7b` が 280-300 tokens、`qwen3:4b` が 320 tokens、`qwen3:8b` が 360-450 tokens、`qwen3:14b` が 360-500 tokens です。短い挨拶や名前質問もまずLLMへ投げます。アシスタント画面は `header -> 新しい会話 action -> material chips -> initial quick cards or chat thread -> bottom composer` を基本構造とし、主要セクションを SMAI 共通の 1320px content lane、会話本文を 1180px chat lane に揃えます。モデル選択 UI は composer 内で入力欄の左に置きます。待機中カードは現在の処理だけを1件表示して順次切り替えますが、これはUI側の軽量表示であり、真のLLM token streamingではありません。回答本文は、Gatewayから最終応答を受け取った後に文またはまとまり単位で約0.16秒ごとに表示します。

## 3. API 起動と確認

FastAPI を起動します。

```powershell
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

確認 URL:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

主な API:

| API | 役割 |
| --- | --- |
| `GET /health` | API 起動確認 |
| `POST /risk/pre-trade-check` | trade intent を deterministic risk rule で評価 |
| `POST /portfolio/rebalance-check` | 現在 portfolio と target allocation から配分見直し候補を作り Risk check へ接続 |
| `POST /screening/score` | Feature Snapshot から Screening Score / ranking / reason を返す |
| `POST /forecast/evaluate` | OHLCV から baseline forecast と walk-forward metrics を返す。`adapter=advanced_linear` 指定時は 1〜60日の線形高度予測、`adapter=advanced_tree_sklearn` 指定時は scikit-learn ツリー型高度予測、`adapter=advanced_gbdt_sklearn` 指定時は scikit-learn ブースティング高度予測、`adapter=advanced_quantile` 指定時はレンジ高度予測を返す。各高度予測は予測変化率、予測価格、信頼度、検証指標、特徴量要約または注意点を返し、`advanced_quantile` は下振れ / 上振れレンジも返す |
| `POST /scoring/investment-score` | Screening / Direction signal / Forecast agreement compatibility / Data quality / Risk signal を統合した Investment Score を返す。`research_scores_by_symbol` は任意入力で、既定 weight は 0.0 |

エラー応答は JSON です。

```json
{
  "code": "APP-2002",
  "message": "Target weights must not exceed 1",
  "details": {
    "target_weight_sum": "1.1"
  }
}
```

主な status code:

- `422`: request validation、domain validation、provider schema mismatch
- `429`: provider rate limit
- `502`: data source error
- `503`: provider unavailable
- `504`: provider timeout

## 4. 手動確認 workflow

サーバーを起動せずに rebalance-check flow を確認する場合は、demo script を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

期待される結果:

- `proposal.trades` に `AAPL` の `BUY` trade が 1 件含まれる
- `risk_decision.status` が `BLOCK` になる
- `risk_decision.breaches` に dividend-yield data 欠損と concentration が含まれる

FastAPI 経由で確認する場合:

```powershell
$body = Get-Content .\examples\portfolio_rebalance_check.json -Raw
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/portfolio/rebalance-check `
  -ContentType "application/json" `
  -Body $body
```

Investment Score:

```powershell
$body = @{
  symbols = @("AAPL", "7203.T")
  as_of = "2026-04-09"
  horizon_days = 1
  # 任意: Research Score を既に別経路で計算済みの場合だけ渡す。既定 weight は 0.0。
  research_scores_by_symbol = @{ AAPL = "60" }
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/scoring/investment-score `
  -ContentType "application/json" `
  -Body $body
```

主な確認項目:

- `rank`
- `total_score`
- `score_band`
- `breakdown`
- `research_score` は任意入力の保持値です。既定設定では総合点や順位には寄与しません。
- `warnings`
- `reasons`
- `decision_support_note`

## 5. CSV MarketData provider

設定上の既定 provider は `yahoo` です。
Streamlit の Cockpit / Ranking / Market Data 画面では provider 選択の初期表示と表示順先頭が `yahoo` です。通常の API も live data を主導線として扱い、local checks / CI は `tests/fixtures/config/local.yaml` などで `mock` を明示して network-free に保ちます。
Cockpit の単銘柄取得では、Yahoo の `Ticker.history` を先に使います。`possibly delisted` / `no price data` 系の一時的な失敗は、`raise_errors=False` と日足の非拡張終了日で再試行してから no-data として扱います。DNS / curl timeout 系の一時通信失敗も同じ条件で1回だけ再試行します。Ranking の多銘柄取得は速度と負荷を優先し、一括取得の成功/失敗をそのまま扱います。
ローカル CSV を使う場合は、`SMAI_CONFIG_FILE` で設定ファイルを指定します。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe .\tools\run_rebalance_check_demo.py
```

API / UI 起動時も同じ設定を使えます。

```powershell
$env:SMAI_CONFIG_FILE = ".\config\csv_example.yaml"
.\venv_SMAI\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

CSV sample は `data/marketdata/` 配下にあります。

- `symbols.csv`
- `ohlcv.csv`
- `fx_rates.csv`
- `fundamentals.csv`

`fx_rates.csv` の対応 pair は現在 `USDJPY` のみです。

## 6. Streamlit UI

起動:

```powershell
.\venv_SMAI\Scripts\python.exe -m streamlit run .\ui\app.py
```

### CSVダウンロード

Ranking、Forecast、Screening、Investment Score、RebalanceのCSVは、一時ファイルを
使わず画面描画時にUTF-8 BOM付きbytesとして生成し、`text/csv` と `.csv` ファイル名で
配信します。CSV download buttonはStreamlit fragment内に置き、クリック時の全画面
rerunでin-memory media URLが先に無効化される競合を避けます。空データではbuttonを
表示せず、出力対象がないことを表示します。

Streamlitプロセスそのものを再起動すると、再起動前のブラウザータブが保持する
in-memory download URLは無効になります。その場合は画面を再読み込みし、新しい
download buttonから取得してください。

### 同一LANのiPad / iPhoneから使う

信頼できる家庭内LANに限り、`scripts\run_lan_server.bat` から
`0.0.0.0:8501` で起動できます。通常起動とEXEの起動設定は変更しません。
iPad / iPhoneは同じWi-Fiから `http://<Desktop PCのIPv4>:8501` をSafariで開きます。
ホーム画面用アイコンとPWA風metadataも配信しますが、オフライン動作やService Workerを
含む完全なPWAではありません。FirewallはPrivate profileだけを許可し、ルーターの
ポート開放やインターネットへの直接公開は行いません。

IP確認、Firewall、固定IP予約、ホーム画面追加、制約、トラブルシュートの詳細は
`docs/LAN_PWA_ACCESS_GUIDE.md` を参照してください。
Windowsログオン時の自動起動、状態確認、停止、タスク登録/解除、運用ログ、
銘柄DBメンテナンスとの分離は `docs/SERVER_OPERATIONS_GUIDE.md` を参照してください。
銘柄DBメンテナンスは別のif-dueタスクで最終成功から既定7日経過時だけ実行し、
失敗後24時間は再実行を抑制します。
一括更新のreportは実施日時ごとに `reports/YYYY-MM-DD_HHMM/` へ保存します。
ホーム画面アイコンは
`http://<Desktop PCのIPv4>:8501/app/static/pwa/apple-touch-icon-v2.png`
で直接確認できます。旧アイコンが残る場合は既存ショートカットを削除し、
Safariで再読み込みしてから追加し直します。

### プレ配布EXE

Windows向けプレ配布は PyInstaller の `onedir` 形式で作成します。
開発環境がないPCでの起動確認用であり、onefile化、インストーラー化、署名、自動アップデートは対象外です。

```powershell
.\venv_SMAI\Scripts\python.exe -m pip install -r setup\requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\build_exe.ps1
```

成果物:

```text
dist\SMAI\SMAI.exe
dist\SMAI\README_PRE_RELEASE.txt
```

`SMAI.exe` は `ui/app.py` を Streamlit headless で起動し、実行時キャッシュ、出力、ログ、ユーザー設定を `%LOCALAPPDATA%\SmartMarketAI` に保存します。配布物には `backend/`, `ui/`, `config/`, 必要最小限の `data/marketdata/`, `data/research_docs/`, `examples/rebalance_scenarios/` を同梱し、`.git/`, `venv_SMAI/`, cache、`outputs/`, live/raw取得物、秘密情報は含めません。

EXE起動時のCRUD系ランタイム領域:

| 用途 | 既定パス | 環境変数 |
| --- | --- | --- |
| ニュース/銘柄更新キャッシュ | `%LOCALAPPDATA%\SmartMarketAI\cache` | `SMAI_CACHE_DIR` |
| エクスポート/生成出力 | `%LOCALAPPDATA%\SmartMarketAI\outputs` | `SMAI_OUTPUT_DIR` |
| 更新ログ | `%LOCALAPPDATA%\SmartMarketAI\logs` | `SMAI_LOG_DIR` |
| ユーザー設定 | `%LOCALAPPDATA%\SmartMarketAI\user_config` | `SMAI_USER_CONFIG_DIR` |

ランチャーは上記ディレクトリを起動時に作成し、配布フォルダ直下や `_internal` 配下へ実行時データを書き込まない方針です。通常の開発/CI起動では環境変数がなければ従来どおり `data/cache` と `logs` を使います。

銘柄の正式マスタは `data/marketdata/symbol_universe.csv` です。外部取得や背景更新で変わる銘柄データはランタイムキャッシュとして `symbols_cache.sqlite` に保存し、既存の `symbols_cache.json` がある場合は初回読み込み時にキャッシュDBへ移行します。キャッシュ由来の値は自動で正式マスタへ昇格しません。正式登録へ反映する場合は、別途レビュー/登録導線で確認してから `symbol_universe.csv` を更新します。

銘柄DBの時刻は用途別に分けます。`cached_at` は runtime cache に保存した時刻、`source_as_of` は元データの基準日、`source_updated_at` は provider / source 側の更新日時、`promoted_at` は公式軽量メトリクスDBへ昇格した時刻です。古い `updated_at` は互換フィールドとして残しますが、UIの `銘柄DB最終更新` は `cached_at` を優先します。

ランキング / 検索で使う軽量指標は、runtime cache から許可フィールドだけを `symbol_metrics.sqlite` に昇格します。通常の background refresh と Cockpit の background priority refresh 後に加え、Ranking の preflight refresh 後も軽量指標を sync します。`symbol_metrics.sqlite` は runtime writable な軽量DBで、既定では `SMAI_CACHE_DIR` 配下を使います。分離したい場合は `SMAI_SYMBOL_METRICS_DIR` で保存先を指定できます。`symbol_universe.csv` に存在しない銘柄、または `is_active=false` の銘柄については、background sync 後に公式軽量メトリクスを prune します。CSV が読めない場合は誤削除を避けるため prune をスキップします。

### Side menu

Streamlit UI は左サイドメニューで画面を切り替えます。
サイドメニューは画面選択と実行環境の簡易表示だけにし、各 workflow の入力はそれぞれの画面内に置きます。
配色・文字階層・カード・テーブル・ボタン・チャートの共通テーマは `ui/styles.py` の `THEME_COLORS` / CSS custom properties を正とします。AI分析、Research Summary、Decision Report などの生成・整理結果は cyan / blue 系の AI text / accent、投資判断やリスクは positive / warning / negative / info / neutral の semantic text / signal token を使います。

| screen | 役割 |
| --- | --- |
| `銘柄コックピット` | 1 銘柄の価格、予測、Investment Score、注意点を深掘りする |
| `銘柄ランキング` | 複数銘柄を条件で絞り、Investment Score で比較する |
| `投資レーダー` | 市場ニュース、投資ヒートマップ、カテゴリ別材料から確認候補を探す |
| `SMAIアシスタント` | SMAIナビと会話し、6つの相談カード、自由入力、read-only Tool Layer、実行した確認、チャット幅の `新しい会話`、Markdown memo、Decision Report下書き保存/archiveで材料整理や判断メモ保存を行う |
| `リバランス` | 現在資産、目標配分、配分見直し候補、Risk 判定を確認する |
| `設定 / データ情報` | Runtime、config、scenario directory、銘柄候補を確認する |

### 銘柄コックピット

確認できるもの:

- provider / symbol / company name / period
- `銘柄を探す`: データ取得元、銘柄検索、銘柄選択、銘柄名を先に表示する。候補の絞り込みは直下の `絞り込み条件` チップで現在状態を確認し、詳細条件は `絞り込み条件を変更` expander を開いた時だけ表示する。条件なしでは `全体` / `NISA指定なし` / `商品指定なし` / `条件なし` / `候補N件` を表示し、クリアボタンは出さない。
- コックピットの `絞り込み条件` 項目は、ランキング画面のカテゴリ別条件セットに追従する。日本株/米国株/ETF など商品に応じて、`業種・セクター` / `投資テーマ` / `時価総額帯` / `連動指数` / `信託報酬/経費率` / `複雑さ` / `PER` / `PBR` / `ROE` などの表示対象を切り替える。通貨条件は共通で表示し、コックピット既定値では候補母集団を狭めすぎないよう広めに保つ。
- Detail filters narrow the Symbol select list by preference: region, product, NISA, market cap, theme/sector, beta band, dividend/category, currency, PER/PBR/ROE/dividend yield ranges. Product defaults to `指定なし`, which does not narrow by stock / ETF. These filters affect only the candidate list and do not change period selection, provider fetch, Forecast, Ranking, or scoring logic.
- cockpit period preset: `カスタム`, `短期: 1週間`, `短期: 1か月`, `中期: 3か月`, `中期: 6か月`, `年初来`, `長期: 1年`, `長期: 3年`, `長期: 5年`
- default cockpit period is `カスタム`; preset選択時は Start / End を自動表示し、`カスタム` の時だけ手入力する
- period preset help explains the intended review basis: short-term material reaction, medium-term trend, long-term drawdown resilience / structural change, and custom event windows
- collapsed sample symbol reference
- `データを取得` 実行中は、入力確認、価格・予測材料取得、予測 / スコア / チャート整理、表示更新の進捗を共通SMAIローディング画面で表示する。
- `AI調査を更新` 実行中は、外部参照ソース取得、企業リサーチレポート生成、ニュース / 開示材料整理、表示更新の進捗を共通SMAIローディング画面で表示する。ローディング画面の `市場トピック` は保存済みニュースcacheだけを使い、追加通信しない。
- 右下の floating `SMAI Copilot` は、現在見ているコックピット section に応じて固定質問を出す。データ取得前、`AI予測インサイト`、`上昇気配・下降警戒`、Decision Report の読み方を deterministic に説明し、価格取得や予測再計算は走らせない
- 価格・予測チャート: 初期表示では実績価格、`AI予測インサイト`、予測レンジ帯を先に確認し、個別モデル線の重なりで読みづらくしない。十分な履歴がある場合は `advanced_linear`、`advanced_tree_sklearn`、`advanced_gbdt_sklearn`、`advanced_quantile` を取得期間から決まる共通の予測日数で計算する。高度予測モデルと単純予測モデルはチャート直上のグループチェックでまとめて追加する。このチェックは取得済みチャート行の表示対象だけを変え、データ取得や予測再計算は走らせない。表示後は固定色のチャート内凡例クリックで個別系列を薄くできる。`表示通貨` は円 (JPY) と $ (USD) の二択で、取得通貨が JPY なら円、USD なら $、それ以外または古い状態値なら円を初期値にする。USDJPY が取得できた場合だけチャートの全価格系列を表示換算し、ラジオボタン右横には `＄円相場` の短い値だけを表示する。スコアや予測計算は変えない。`AI予測インサイト` カードは結論、中心予測（高度予測モデルの統合結果）、下振れ予測 / 上振れ予測、予測価格、予測レンジ、信頼度、モデル合意度、予測ばらつき、主な理由、注意点を主表示にする。信頼度が低い、または判断保留に近い場合は amber accent を使う。個別高度モデルカードは常時表示し、平均 RMSE、誤差改善、過去検証の方向一致率、相対的に安定したモデル、単純予測比較は `高度予測モデルの詳細を見る` / `検証指標を見る` / `単純予測との比較を見る` で確認する。Consensus helper には `統合予測 = Σ(各モデルの予測変化率 × 重み) ÷ Σ重み` と、重みを信頼度・誤差改善・モデル合意度・検証数から保守的に丸めることを明記する。各モデルの helper も直近値維持、移動平均、モメンタム、線形、ツリー、ブースティング、レンジの考え方を初心者向けの短い計算式で説明する。予測日数の初期値は取得期間のおよそ 1/12 を使い、60日を上限にする。全体チャートの右側に、最新実績の数日前から予測部分までを自動抽出した拡大図を並べ、タイトルは `予測スコープ（31日）` のように期間を示す。全体チャートは `価格チャート` として小さな点マーカーを復活させつつ線を主役にする。naive / moving-average / momentum の単純予測は backend baseline / fallback / 詳細確認用として残すが、既定のチャート表示と主要モデルカードには出さない。
- `Signal Reading / シグナル読み取り`: Analysis KPI と同じ `上昇気配` / `下降警戒` を、予測変化率、モデル方向一致、予測のばらつきと合わせて解釈する。売買推奨ではなく比較・確認材料として扱う。
- forecast agreement compatibility、forecast spread、best RMSE model
- Investment Score summary
- score breakdown chart
- post-fetch confirmation summary lifts key closed-detail items into the main view: latest price, OHLCV period/volume, forecast range, screening components, short-term features, data quality, and forecast evaluation
- period-aware evaluation summarizes the fetched window as short-term reaction, medium-term trend, annual trend, or long-term resilience, with return, range position, drawdown, and volatility checks
- warnings / reasons
- Forecast metrics / Screening Score / provider detail
- Research Summary: `最新ニュース・開示サマリー` の近くに `投資ヒントとなるニュース` と `ニュース・開示の出典を表示（URL付きN件）` が出ます。`最新ニュース・開示サマリー` と `投資ヒントとなるニュース` は `Market Intelligence` の主表示カードとして扱い、`ニュース・開示の出典` は初期折りたたみの小さな citation list として元記事・TDnet・企業IR・EDINET・Yahoo Finance を開けます。`投資ヒントとなるニュース` はURL付きの一般ニュースだけを `注目材料 Top 3` として表示し、タイトル、公開日、鮮度、出典、材料分類、確認観点、短い要約、種別アクセントを優先します。raw URLはカード本文に出さず、hrefは維持します。TDnet、企業IR、EDINET、provider source、URL不足ニュースはこの専用カードに混ぜず、下部の `ニュース・開示の出典` と `詳細情報・開発者向け` で確認します。
- JSON / CSV downloads

### 銘柄ランキング

#### ランキング履歴

- カスタムプロフィールで `ランキング作成` が正常完了すると、保存時点の条件と結果を
  `data/user/profiles/<user_id>/ranking_history/` に保存します。`default` プロフィールでは
  永続保存せず、プロフィールの選択・作成を案内します。
- ランキング画面上部の `📚 ランキング履歴` から一覧と詳細を開けます。通常履歴は
  ユーザーごとに直近30件を保持し、ピン留め済み履歴は自動削除しません。
- 同一条件・同一結果の短時間の再描画保存を避けるため、同じsignatureは5分以内に
  重複保存しません。保存失敗時も現在のランキング結果表示は継続します。
- 詳細に表示する価格・スコアは保存時点の値で、現在値ではありません。現在情報は
  `現在の銘柄を確認` からコックピットを開いて確認します。
- `この条件で再ランキング` は条件をフォームへ復元するだけです。外部取得や
  ランキング作成は自動実行せず、利用者が条件確認後に `ランキング作成` を押します。
- 履歴一覧は保存日時、対象、基準、取得日、候補/保存件数、主要条件、上位銘柄を
  比較できる全幅の横長行カードで表示します。カード全体から詳細を開け、埋め込みCTAも
  表示します。ピン留めは上段、通常履歴は下段で二色を交互に使います。
- 履歴詳細では保存時の条件/基準、注目候補、上位10件グラフ、上昇気配×下振れ警戒、
  深掘り銘柄、詳細テーブルを保存snapshotだけから表示します。タイトル、dashboard、
  条件カード、metric card、section headingは通常ランキング画面と同じ共有スタイルです。
- `表示中の並べ替え` は保存時基準を初期値にし、保存データに存在する指標だけを選べます。
  変更はカード、棒グラフ、深掘り候補、テーブルの表示順だけに反映し、snapshot/indexを
  更新せず、現在データの取得やランキング再計算も行いません。

確認できるもの:

- provider
- 地域 / 商品 / 評価方針
  - 地域: `国内` / `米国` / `全体`
  - 商品: `株式` / `ETF` / `指定なし`
  - 評価方針: `AI総合` / `上昇気配重視` / `モメンタム・トレンド` / `成長クオリティ` / `割安クオリティ` / `高配当の持続性` / `低ボラ・安定` / `安定成長` / `小型・成長探索` / `NISA長期適合` / `データ信頼度優先` / `ETF低コスト・コア` / `ETFインカム・分散`
- 初期表示は `ランキング作成条件` に地域、商品、取得期間、データ取得元、作成対象件数、評価方針を1列にまとめ、直下に `選択中の評価方針` と `ランキング条件` の要約カードを横並びで表示する。詳細条件は閉じず、属性条件、数値条件、キーワード検索を常時表示し、入力が終わった後に `ランキング作成` を押す導線にする。
- `評価方針` はSMAIの複合評価プロファイルを選ぶ主導線です。評価方針メモは短い説明と重みチップだけを表示し、上位銘柄はまず詳しく確認したい候補として示す。
  - 右下の floating `SMAI Copilot` は、ランキング作成前、ランキング結果、深掘り候補の section に応じて固定質問を出す。順位の理由、深掘り比較、AI総合 / 上昇気配 / 下降警戒の読み分け、低信頼データの注意点を deterministic に説明し、ランキング再作成は走らせない。
  - AI総合: `総合マルチファクター`。重みは `基礎評価30%` / `予測・上昇気配30%` / `リスク・下振れ警戒25%` / `データ信頼度10%` / `Research確認材料5%`。上昇気配・下降警戒自体も、AI予測インサイトがある場合は通常方向シグナルに25%までブレンドされる。
  - 上昇気配重視: 予測・上昇気配と下振れ警戒、基礎評価、データ信頼度を重視する。短期的に詳しく確認したい候補の整理に使う。
  - モメンタム・トレンド: 取得期間の価格評価、上昇気配・下降警戒、基礎評価を重視し、追随リスクも確認する。
  - 成長クオリティ: ROE、上昇気配、基礎評価、データ信頼度を重視し、PER/PBRは成長期待との釣り合い確認に使う。
  - 割安クオリティ: PER/PBRの低さに加え、ROE、リスク、データ信頼度、Research確認材料を確認し、割安に見える理由を確認しやすくする。
  - 高配当の持続性: 配当利回り、配当カテゴリ、リスク、PBR、データ信頼度、Research確認材料を組み合わせ、極端な高配当は減配リスク確認対象にする。
  - 低ボラ・安定: リスク、β分類、データ信頼度、銘柄規模、Research確認材料を重視し、値動きの落ち着きを優先する。
  - 安定成長: リターンだけでなくリスク、データ信頼度、条件適合度を合わせて見る。
  - 小型・成長探索: 小型/中型、ROE、基礎評価、上昇気配を重視し、リスク15%とDB信頼度も確認する。
  - NISA長期適合: NISA適合、投資スタイル、リスク、データ信頼度、ROE、Research確認材料を重視する。
  - データ信頼度優先: metadata source、更新日、データ信頼度、欠損の少なさを最優先する。
  - ETF低コスト・コア: 経費率、連動指数、複雑性、NISA適合、DB信頼度を重視する。
  - ETFインカム・分散: ETFの利回り、経費率、指数、通貨、複雑性、データ信頼度、Research確認材料を重視する。
  - 旧来の `配当重視` / `成長重視` / `割安重視` / `安定重視` / `トレンド重視` は内部互換として残すが、上部UIでは代表プロファイルへ統合して重複表示しない。
- ランキング結果画面では、`評価方針` で候補を採点し、そのスコア順に上位カード / Top 10棒グラフ / `SMAIメモ` を表示する。単一指標ソートは上部ドロップダウンには置かず、詳細テーブルの列ヘッダークリックで表示中データをローカルに並べ替える。詳細テーブルの通常表示は `順位` / `銘柄` / `銘柄名` / `現在株価（円）` / `総合スコア` / `判断方針` / `配当利回り` / `PER` / `PBR` / `ROE` / `上昇気配` / `下降警戒` / `予測変化率` / `予測確度` / `SMAIメモ` を優先して表示する。`現在株価（円）` は表示用にJPYへ統一し、USD価格は同じ取得元から取得できた最新USDJPYで換算する。換算できない非JPY価格は円価格として誤表示せず `N/A` にする。`詳細列を表示する` を有効にすると、`ニュース材料` / `材料件数` / `材料信頼度` / `材料の新しさ` / `予測日数` / `モデル方向` / `予測根拠` / `基礎評価` / `リスク` / `データ信頼度` / `条件適合度` / `DB信頼度` / `根拠状態` などの補助列を確認できる。ニュース材料はAI要約による参考情報であり、現在のランキング順位には反映しない。N/Aは未取得または未評価を表す。長い評価理由、確認ポイント、スコア内訳、取得状態は tooltip / 行クリック後の `選択銘柄の詳細メモ` / 銘柄データで確認する。`AI予測インサイト` がある候補では、並べ替え理由と確認ポイントに、上昇気配 / 下降警戒へ25%まで反映していることと、低信頼時は控えめに読むことを表示する。
- `上昇気配` / `下降警戒` は、予測エッジ、モデル別方向エッジ、価格モメンタム、トレンド確認を組み合わせる。予測変化率とモメンタムはボラティリティ調整し、モデル間の開きは直接加点せず、スコアを中立へ寄せる信頼度調整として扱う。ランキングは売買推奨ではなく、深掘り候補の比較優先度として扱う。
- `作成対象` は、外部 provider 取得前の件数上限です。既定は `標準: 上位300件` で、候補が多い場合は総合マルチファクター基準の条件適合度とDB信頼度で事前に上位候補を選んでから価格データを取得します。`評価方針` の変更、詳細テーブルの列ソート、検索、絞り込みは取得対象を変えず、取得済みデータの再評価・再ソートとして扱います。外部取得は `ランキング作成` を押した場合のみ実行します。全件取得も選べますが、Yahoo live data では時間がかかります。ランキング作成前の銘柄DB preflight 更新は、比較候補30件までは全件、31件以上は最大50件、対象スキャンは最大300件に制限し、残りはバックグラウンド優先更新へ回します。
- ランキング結果の総合スコアには、取得期間の市場評価に加えて、条件適合度とDB信頼度を反映する。
  - 条件適合度: NISA、時価総額、配当、PER/PBR/ROE、ETF経費率、複雑性などを評価方針別に評価する。投資魅力度を直接保証するものではありません。
  - DB信頼度: `metadata_source`、`metadata_as_of` / `metadata_updated_at`、ランキング判断に使う主要項目の登録状況を評価する。
- 基本条件
  - period preset: `短期: 1か月` / `標準: 3か月` / `中期: 6か月` / `長期: 1年`
  - currency
  - 配当/分配金カテゴリ
  - 配当/分配金利回り
  - market-cap tier
  - ETF index family
  - max expense ratio
  - theme
  - keyword
- 常設の詳細条件パネル
  - `ランキング条件` 要約カードで、現在の地域、商品、評価方針、取得期間、詳細条件あり/なし、候補数をチップ表示する
  - `属性条件` / `数値条件` / `キーワード検索` に分けて表示
  - 地域 × 商品に応じて、現在の銘柄マスタで判定できる詳細条件だけを表示
  - 株式: 業種/テーマ、時価総額、市場感応度（β）、配当利回り、PER、PBR、ROE、NISA
  - ETF: 連動指数、信託報酬/経費率、分配金利回り、複雑さ
  - `取得期間` の `?` help では、標準3か月は20日/60日系の予測材料、1か月は直近反応、6か月は中期トレンド、1年は安定性確認に使うことを説明
  - 時価総額は、日本株では 10兆円 / 1兆円 / 1,000億円 / 100億円、米国株では $200B / $10B / $2B / $300M を目安に表示
  - 配当/分配金カテゴリは、0%、0%超〜3%未満、3%以上の利回り帯を選択肢に表示。ただし連続増配候補は curated metadata 由来
  - 配当/分配金カテゴリと数値条件の `配当/分配金利回り(%)` は同じ軸の条件なので、片方を指定した場合はもう片方を非活性にする
  - 各条件の `?` help で、指標の意味、目安値、注意点を確認可能
  - 条件のクリア
  - 条件変更後の候補数表示
- 比較する銘柄
  - 初期状態では候補をすべて選択
  - 銘柄リストは折りたたみ内で確認・変更
- `ランキング作成` は詳細条件入力欄の下に置く。直前の薄型サマリーで候補数、実際の作成対象件数、評価方針、期間、取得元、詳細条件あり/なしを確認できる。
- `ランキング作成` 実行中はprogress bar直下に非モーダルのSMAIローディングカードを表示し、前回結果と画面を覆わない。現在のランキング生成は同期処理のため、完全な操作応答を可能にするbackground job化は後続とする。
- ranking result with ticker / company name / score / warnings
- ranking result は AgGrid で表示し、銘柄行をクリックするとローカル銘柄マスタ `symbol_universe.csv` と保存済み銘柄キャッシュDB `symbols_cache.sqlite` の登録値をモーダルで確認できます
- `銘柄データ` モーダルの `データ情報` タブでは、銘柄DB鮮度、銘柄DB最終更新、銘柄DB取得元、価格データ更新、財務データ更新、不足している主要項目を確認できます。これはデータ信頼度の確認材料であり、売買推奨やランキング順位変更ではありません。
- Cockpit の `データを取得` では、価格・予測・Investment Score の表示を優先し、取得成功後に選択中1銘柄を background priority refresh へ登録します。同じセッションでは同じ銘柄の登録を30分TTLで抑制します。Ranking の `ランキング作成` では、上記上限内の比較候補を同期 preflight 更新対象へ渡してから ranking creation を進めます。失敗しても前回保存データと通常の market-data fetch / ranking creation は継続します。
- 銘柄データモーダルの `AI Research` タブでは、`AIで資料を確認` を押した場合だけ登録済みResearch資料を検索し、Research Summary、根拠資料名、資料日、根拠数、詳細 evidence を確認できます
- 選択銘柄をコックピットへ渡す deep-dive flow

注意:

- ranking の候補条件は、provider fetch 前に使える `data/marketdata/symbol_universe.csv` の curated metadata を中心にしています。
- 地域 / 商品 / 詳細条件は provider fetch 前の候補 universe を絞ります。`重視して並べ替え` は Investment Score の表示順の重み付けに使い、候補 universe そのものは絞りません。
- `市場感応度（β）` は metadata の `risk_band` を使う provider fetch 前の条件です。β 0.8未満を低変動、0.8〜1.2を市場並み、1.2超を高変動として扱います。
- Ranking result の Risk / リスクスコアは取得期間の価格データを見た後の確認材料です。候補条件の `市場感応度（β）` とは別の指標として確認します。
- 投資信託は MVP のランキング / スクリーニング / チャート対象外です。source seed や metadata schema は将来対応として残しますが、default ranking universe と UI の主要導線には出しません。
- 配当/分配金カテゴリや SMAI 投資テーマは現在 curated metadata / source import / opt-in metadata refresh / deterministic backfill で管理します。live provider 由来の更新は明示 opt-in です。高配当は投資テーマ条件にも出せますが、利回りを厳密に絞る場合は配当/分配金カテゴリまたは配当/分配金利回り条件を使います。
- 株式の詳細条件は `業種・セクター` と `投資テーマ` を分けます。`業種・セクター` は `sector`, `sector_gics`, `tse_33_industry`, `topix_17` など公式/取得元に近い分類を使い、`投資テーマ` は `theme` と `smai_theme_tags` を使います。JPX 東証上場銘柄一覧の `規模区分` は `market_cap_tier` へ変換し、`時価総額` 条件で使います。
- 株式の `investment_style` は、国内株・米国株とも一括投資向きの候補として `lump_sum` に機械バックフィルしています。ETF の積立可否は source 確認が必要なため、未確認の `investment_style=unknown` は残します。
- ETF の `nisa_category` は、JPX / IMAJ / SBI のローカル公式 source CSV と照合し、現在の ETF 1,046件では `growth` または `none` に確定済みです。未確認の `unknown` は ETF には残していません。
- Ranking UI の NISA 条件は `指定なし（NISAで絞らない）` / `NISA対象のみ（成長投資枠）` / `NISA対象外のみ` です。現在の株式候補は国内株・米国株とも成長投資枠対象として整理済みのため、株式で `NISA対象のみ（成長投資枠）` を選んでも候補数が変わらない場合があります。ETF は対象/対象外が混在するため、この条件で候補数が変わります。
- ranking universe の MVP 方針は、SBI証券で取り扱いがあり、現物・NISA・長期投資で検討しやすい株式・ETFを初期対象にすることです。詳細は [09_SBI_Symbol_Universe_Policy.md](./09_SBI_Symbol_Universe_Policy.md) を参照してください。
- `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse` は Phase 18 policy columns として `symbol_universe.csv` に保持します。既存候補は local curated / source-import seed であり、SBI取扱確認済み master ではないため、`tradability=unknown` は初期 ranking で通します。
- ranking 候補抽出前に default SBI ranking universe policy を適用します。MVP の対象は `stock` / `etf` です。`mutual_fund` / `fund` / `investment_trust` / `adr` / `reit` / FX / CFD / 先物 / option / crypto / bond / MMF / commodity、レバレッジ、インバース、`not_tradable`、`is_sbi_supported=false`、`is_active=false` は初期候補から除外します。
- `symbol_universe.csv` は Phase 16/18 UI 用の銘柄候補マスタです。必須列は `symbol`, `name`, `market`, `asset_type`, `currency`, `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, `risk_band` です。任意列 `yahoo_symbol` は、表示用 symbol と Yahoo 取得用 symbol が異なる ETF で使います。公式分類の任意列として `sector_gics`, `industry_gics`, `subindustry_gics`, `tse_33_industry`, `topix_17` を持ち、SMAI 側の横断テーマは `smai_theme_tags`, `theme_confidence`, `theme_source` に分離します。
- Phase 18 metadata columns は `metadata_source`, `metadata_as_of`, `metadata_updated_at` です。現在の master は `curated_csv`, `yahoo`, `jpx`, `imaj`, `jpx_nisa_growth`, `sbi_us_stock`, `sbi_us_etf`, `sbi_us_stock_removed`, `sbi_us_etf_removed`, `manual`, `mutual_fund_seed` などの metadata source を行ごとに保持します。
- Metadata fields are governed by `backend/marketdata/symbol_metadata_schema.py`.
  - `core`: symbol, name, market, asset type, currency, official sector/industry, SMAI theme/tags, aliases.
  - `ranking_filter`: dividend, PER/PBR/ROE, expense ratio, risk, complexity, quality fields. Source/freshness is tracked before live provider updates are trusted.
- `fund_extended`: trust fee, AUM, NISA eligibility, installment availability, management style, and distribution policy. Mutual-fund seed/source import rows can store these fields in `symbol_universe.csv`, but these fields are future extension metadata and are not MVP ranking filters.
- `設定 / データ情報` の `ランキング銘柄候補` では、候補数、metadata 出所、metadata 基準日、形式確認 status を確認できます。CSV の列形式 / 選択値 / 数値 / 重複 ticker / metadata 欠損に問題がある場合は一覧に表示されます。
- 常設パネルで条件を変えると、候補数と「比較する銘柄」の選択候補が同じ画面内で確認できます。

Symbol universe metadata refresh:

- `tools/refresh_symbol_universe_metadata.py` は provider-neutral な metadata refresh command です。
- 現在実装済みの metadata provider は network 非依存の `curated_csv` と、明示実行する `yahoo` です。
- 既定は dry-run で、CSV / manifest は書き換えません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

- Yahoo live metadata は外部通信のため `--provider yahoo --allow-live` を明示した場合だけ実行します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --provider yahoo --allow-live --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

- `--write` を付けた場合だけ `symbol_universe.csv` と `data/marketdata/symbol_universe_manifest.json` を更新します。write 前に validation error が残る場合は書き込みを拒否します。
- Yahoo provider は取得できた `sector`, `dividend_yield_pct`, `dividend_category`, `per`, `pbr`, `roe_pct`, `market_cap_tier`, `risk_band`, ETF の `expense_ratio_pct`, metadata source/as-of/update fields を正規化して返します。`dividendYield` は yfinance が返す percentage value として扱い、`trailingAnnualDividendYield` は ratio から percentage に変換します。ETFの `annualReportExpenseRatio` は ratio から percentage に変換し、`netExpenseRatio` は percentage value として扱います。非数値、無限大、負の PER/PBR/配当/分配金利回り/経費率など schema に入れられない値は空欄のままにします。失敗銘柄は manifest の `failed_symbols` / `failures` に残します。
- live metadata refresh は対象を絞って実行できます。`--symbols`, `--asset-type`, `--market`, `--metadata-source`, `--missing-any`, `--limit` を使い、いきなり全件取得しない運用を推奨します。manifest の `selection` に対象件数と対象銘柄sampleを残します。
- `tools/backfill_symbol_universe_screening_metadata.py` は network なしの決定的バックフィルです。最新のローカル `jpx_listed_stock_*.csv` から日本株の `tse_33_industry` / `topix_17` を空欄だけ補完し、米国株は現在の `sector` から GICS 大分類へ一対一対応できる場合だけ `sector_gics` を補完します。`consumer` のように GICS 上で Consumer Discretionary / Consumer Staples の判別が必要な分類は推定で埋めません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --provider yahoo --allow-live --asset-type stock --market jp --metadata-source jpx_listed_stock --missing-any per,pbr,roe_pct,dividend_yield_pct --limit 20 --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00
.\venv_SMAI\Scripts\python.exe .\tools\backfill_symbol_universe_screening_metadata.py --updated-at 2026-06-22T00:00:00+09:00 --write
```

- 問題なければ `--write` を付けて同じ条件を反映します。live取得は通信状態やprovider応答に依存するため、失敗銘柄は manifest で確認し、必要に応じて小さい単位で再実行します。

Symbol universe source import:

- `tools/build_symbol_universe_source.py` は、公式 raw file を SMAI 用 source CSV へ変換する command です。現在は JPX の東証上場銘柄一覧から国内株 source を作る `--source-kind jpx_listed_stock`、JPX 国内 ETF / ETN source を作る `--source-kind jpx_etf`、JPX listed REIT source を作る `--source-kind jpx_reit`、SBI米国株 / 米国ETF・海外ETF のローカル raw file から source を作る `--source-kind sbi_us_stock` / `sbi_us_etf`、NISA制度 metadata 更新 source を作る `--source-kind nisa_eligibility` に対応しています。raw file は CSV、Excel (`.xls` / `.xlsx`)、JPX ETF/ETN / REIT 公式一覧の HTML、SBI の CP932 HTML を扱えます。PDF は通常 import 対象外です。既定は dry-run で、`--write` を付けた場合だけ source CSV / manifest を書き込みます。
- `tools/import_symbol_universe_source.py` は、JPX などのローカル source CSV を `symbol_universe.csv` 形式へ取り込む command です。
- 既定は dry-run で、`--write` を付けた場合だけ CSV / manifest を更新します。write 前に validation error が残る場合は書き込みを拒否します。
- 初期 source として `data/marketdata/symbol_universe_sources/jpx_etf_seed.csv` と `data/marketdata/symbol_universe_sources/jpx_stock_seed.csv` を置いています。2026-05-20 時点では JPX 東証上場銘柄一覧から国内株 3,645件を追加し、JPX seed と合わせて `symbol_universe.csv` に取り込み済みです。国内株 3,747件と米国株 4,334件は NISA 成長投資枠対象として `nisa_category=growth`, `nisa_growth_eligible=true`, `nisa_tsumitate_eligible=false` に整理済みです。2026-05-26 時点では JPX ETF/ETN 公式一覧 HTML 402件、JPX NISA ETF/ETN Excel 28件、IMAJ NISA listed-fund Excel 294件、SBI公式米国株 HTML 4,330行、SBI公式米国ETF HTML 612件を source 化しています。candidate master は 9,197件です。IMAJ source に含まれるインフラファンド等 5件は現行 MVP の候補マスタには未登録のため、`nisa_eligibility` の update-only failure として manifest に残します。
- MVP 向け source profile として `jpx_listed_stock`, `jpx_stock`, `jpx_etf`, `jpx_reit`, `sbi_us_stock`, `sbi_us_etf`, `sbi_availability`, `nisa_eligibility`, `quality_review`, `ranking_metadata` を使えます。`jpx_listed_stock` / `jpx_stock` source の `source_industry_33` / `source_industry_17` は import 時に `tse_33_industry` / `topix_17` へ写します。`mutual_fund_seed` は将来対応用 profile として残します。
- 追加 seed として `sbi_us_stock_seed.csv`, `sbi_us_etf_seed.csv`, `mutual_fund_seed.csv` を置いています。SBI US stock / ETF は 2026-05-21 の公式 HTML source に置き換えて拡張済みです。投信 4件は future extension seed として保持し、default ranking universe から除外します。
- `nisa_eligibility_seed.csv` は既存の株式・ETF 31件へ NISA metadata を付与する local seed です。2026-05-19 時点で `symbol_universe.csv` に反映済みです。国内株と米国株は stock profile 側で成長投資枠対象として扱い、ETF / REIT / 投信など個別判定が必要な商品は `nisa_eligibility` source で更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_seed.csv --source-profile jpx_etf --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

JPX 東証上場銘柄一覧を使う場合は、先に公式 Excel (`.xls` / `.xlsx`) / CSV を `data/marketdata/raw/` などに保存し、SMAI 用 source CSV に変換します。ETF / ETN / REIT はこの builder では除外し、国内株だけを `jpx_listed_stock` source として作ります。JPX の `規模区分` は `TOPIX Core30 -> mega`, `TOPIX Large70 -> large`, `TOPIX Mid400 -> mid`, `TOPIX Small 1/2 -> small` として `market_cap_tier` に変換します。国内株 import profile は、NISA 成長投資枠が上場株式等を対象にする制度であることを前提に `growth / true / false` を既定値にします。整理・監理銘柄などの例外が確認できた場合は、後続の `nisa_eligibility` source で `none` などへ明示更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_listed_stock --raw-file .\data\marketdata\raw\jpx_listed_stock_20260520.xls --output-csv .\data\marketdata\symbol_universe_sources\jpx_listed_stock_20260520.csv --as-of 2026-05-20 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_listed_stock_20260520.csv --source-profile jpx_listed_stock --as-of 2026-05-20 --updated-at 2026-05-20T00:00:00+09:00 --write
```

JPX 国内 ETF / ETN を使う場合は、JPX ETF raw file を `jpx_etf` source として変換します。公式 ETF/ETN 一覧 HTML も扱えます。builder は `.T` 付き symbol、指数 family、信託報酬、商品系 theme、ETN / レバレッジ / インバース判定を保持します。商品系ETF、レバレッジ、インバースは ranking universe policy 側で除外できます。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_etf --raw-file .\data\marketdata\raw\jpx_etf_2026-05.xlsx --output-csv .\data\marketdata\symbol_universe_sources\jpx_etf_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_2026-05.csv --source-profile jpx_etf --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_etf --raw-file .\data\marketdata\raw\jpx_etf_20260520.html --output-csv .\data\marketdata\symbol_universe_sources\jpx_etf_20260520.csv --as-of 2026-05-20 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_20260520.csv --source-profile jpx_etf --as-of 2026-05-20 --updated-at 2026-05-20T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_20260520.csv --source-profile jpx_etf --as-of 2026-05-20 --updated-at 2026-05-20T00:00:00+09:00 --update-existing --write
```

JPX の「NISA 成長投資枠対象銘柄一覧」のように、列名にふりがなが含まれる Excel も `jpx_etf` / `nisa_eligibility` source として扱えます。銘柄本体を追加してから制度 metadata を更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_etf --raw-file .\data\marketdata\raw\jpx_etf_20260521_NISA.xlsx --output-csv .\data\marketdata\symbol_universe_sources\jpx_etf_nisa_growth_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_nisa_growth_20260521.csv --source-profile jpx_etf --source-name jpx_nisa_growth --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind nisa_eligibility --raw-file .\data\marketdata\raw\jpx_etf_20260521_NISA.xlsx --output-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_jpx_etf_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_jpx_etf_20260521.csv --source-profile nisa_eligibility --source-name jpx_nisa_growth --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --update-existing --write
```

JPX REIT を保持する場合は、JPX REIT 公式 HTML を `jpx_reit` source として変換します。REIT は master に保持しますが、MVP ranking universe では `reit` を初期対象外にしているため、ランキング候補には出ません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_reit --raw-file .\data\marketdata\raw\jpx_reit_20260521.html --output-csv .\data\marketdata\symbol_universe_sources\jpx_reit_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_reit_20260521.csv --source-profile jpx_reit --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
```

IMAJ の「NISA成長投資枠対象の対象銘柄（国内ETF、REIT等）」Excel は、複数シート構成でも対象シートを自動検出します。5桁で末尾 `0` が付く国内コードは4桁 `.T` symbol に正規化します。REIT を追加した後に再適用すると REIT の NISA metadata も更新できます。インフラファンドなど未登録 symbol は update-only failure として manifest に残します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind nisa_eligibility --raw-file .\data\marketdata\raw\imaj_nisa_growth_listed_fund_20260519.xlsx --output-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_imaj_listed_fund_20260519.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_imaj_listed_fund_20260519.csv --source-profile nisa_eligibility --source-name imaj --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --update-existing --write
```

SBI米国株 / 米国ETF・海外ETF の取扱一覧を使う場合も、まずローカル raw CSV / Excel / HTML を source CSV に変換します。SBI公式HTMLは CP932 を扱えます。`sbi_us_stock` builder は米国株ページ内に混在するETF表を stock として取り込まないようにスキップします。`sbi_us_stock` builder は既知のクラス株式表記として `BRKB` / `UHALB` を Yahoo-compatible な `BRK-B` / `UHAL-B` に正規化します。米国株 import profile は NISA 成長投資枠を既定で `growth / true / false` にします。`sbi_us_etf` builder は、名称や明示フラグからレバレッジ / インバース ETF を判定し、後段の ranking universe policy で除外できるように `is_leveraged` / `is_inverse` を保持します。現在取り込んだ SBI 公式 ETF HTML は米国形式 ticker が中心です。将来 raw に香港・韓国・シンガポールなどの市場別コードが含まれる場合は、Yahoo symbol suffix / 通貨 / exchange mapping を決めてから追加します。
SBI source は公式ページ内に同一 ticker の重複・旧表記が混在する場合があります。既存銘柄の名称を一括上書きせず、通常は新規追加だけを `sbi_us_stock` / `sbi_us_etf` で行い、最新一覧から消えた銘柄は `sbi_availability` profile で `tradability=not_tradable`, `is_sbi_supported=false` に更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_stock --raw-file .\data\marketdata\raw\sbi_us_stock_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_etf --raw-file .\data\marketdata\raw\sbi_us_etf_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_2026-05.csv --source-profile sbi_us_stock --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_2026-05.csv --source-profile sbi_us_etf --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_stock --raw-file .\data\marketdata\raw\sbi_us_stock_20260521.html --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_etf --raw-file .\data\marketdata\raw\sbi_us_etf_20260521.html --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_20260521.csv --source-profile sbi_us_stock --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_20260521.csv --source-profile sbi_us_etf --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
```

JPX のように source 側が4桁コードで、SMAI 側では yfinance-compatible な `.T` suffix が必要な場合は、`jpx_stock` profile を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_stock_seed.csv --source-profile jpx_stock --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

SBI profile の dry-run 例:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_seed.csv --source-profile sbi_us_etf --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

NISA eligibility のように既存銘柄の制度 metadata だけを更新する場合は `--source-profile nisa_eligibility --update-existing` を使います。この profile は `nisa_category`, `nisa_growth_eligible`, `nisa_tsumitate_eligible`, metadata source/as-of/update fields だけを更新し、既存の市場や商品分類は上書きしません。公式または確認済み raw file から source CSV を作る場合は、先に `--source-kind nisa_eligibility` で 4桁国内コードを `.T` 付き symbol に変換し、成長投資枠 / つみたて投資枠 / 対象外を canonical fields に正規化します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind nisa_eligibility --raw-file .\data\marketdata\raw\nisa_eligibility_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_2026-05.csv --source-profile nisa_eligibility --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --update-existing
```

Ranking metadata のように既存銘柄の条件列だけを更新する場合は `--source-profile ranking_metadata --update-existing` を使います。テンプレートは `data/marketdata/symbol_universe_sources/ranking_metadata_template.csv` です。この profile は `PER`, `PBR`, `ROE`, `配当利回り`, `時価総額`, `リスク`, ETF の `信託報酬/経費率` など ranking filter 用 metadata だけを更新し、名称・市場・商品分類は上書きしません。source CSV には `per` / `pe_ratio`, `pbr` / `price_to_book`, `roe_pct` / `roe`, `dividend_yield_pct` / `dividend_yield` などの列名を使えます。未確認値は空欄のままにし、推定値で埋めません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\ranking_metadata_2026-05.csv --source-profile ranking_metadata --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --update-existing --write
```

provider 再取得後も極端な値が残るなど、数値を修正せず注意フラグだけ付けたい場合は `quality_review` profile を使います。この profile は `data_quality` と metadata fields だけを更新し、PER/PBR/ROE や商品分類は上書きしません。

Ranking metadata coverage:

- `tools/check_symbol_universe_metadata_coverage.py` は、`symbol_universe.csv` の属性充足率を network なしで集計し、`data/marketdata/symbol_universe_quality_report.json` へ出力します。総件数、地域別、商品別、全体coverage、日本株・米国株・ETF別coverageを含み、`unknown` は充足済みとして数えません。
- 2026-06-22 の9,197件baselineでは、日本株はPER 91.51% / PBR 99.28% / ROE 95.33% / 配当利回り100%、米国株はPER 70.97% / PBR 88.76% / ROE 90.09% / 配当利回り98.85%、ETFは経費率98.18% / 指数分類100% / 分配利回り95.03% / 資産クラス98.37%です。日本株の `tse_33_industry` / `topix_17` は JPX source 由来で3,746件、米国株の `sector_gics` は一対一対応できる範囲で3,662件を補完済みです。
- PER/PBR/ROE/配当利回り/時価総額分類/経費率/AUM/平均出来高には、optionalな `*_source` / `*_as_of` / `*_quality` を持てます。`quality` は `confirmed` / `derived` / `estimated` / `unknown` / `stale` です。既存CSVに新カラムがなくても読み込み可能です。
- `refresh_symbol_universe_metadata.py --fill-missing-only` は空欄だけを補完し、既存の正規値やそのprovenanceを別providerで上書きしません。取得不可の値は `0`、平均値、簡易推定値で埋めず、空欄のまま維持します。
- Yahoo provider / yfinance の書き込み値を `symbol_universe.csv` の運用上の source-of-record とします。Yahoo Japan などのWeb画面や ETF 情報サイトは sanity check の参照に使いますが、trailing / forward / 会社予想 / TTM / 更新タイミングの違いがあるため完全一致は受け入れ条件にしません。正確な監査済み財務値が必要な場合は、将来の公式IR / 有価証券報告書 / 追加 verified provider の取り込み対象として扱います。
- DB書き込み時は `dividend_yield_pct > 20`, `PER <= 0 or > 200`, `PBR <= 0 or > 50`, `ROE < -100 or > 100` をランキング用の異常値として空欄化します。これらは詳細テーブル、カード、確認メモで `N/A` / 要確認相当として扱い、総合スコアやランキング計算には混入させません。
- Phase 18 の実装完了後は、NISA / ETF / stock metadata source の継続更新、上記の provider/source 欠損補完、海外ETF `yahoo_symbol` mapping の追加 live smoke は運用タスクとして扱います。これらは通常のリリース完了条件ではなく、確認済み source や network 利用可能時に更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\enrich_symbol_universe_etf_metadata.py --write
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_metadata_coverage.py --checked-at 2026-06-22T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --provider yahoo --asset-type etf --missing-any asset_class,aum,average_volume --fill-missing-only --allow-live --write
```

- `tools/enrich_symbol_universe_etf_metadata.py` は、ETF の `index_family` 補完に加え、`data/marketdata/symbol_universe_sources/` 配下の JPX / IMAJ / SBI 公式 source CSV を使って ETF の NISA 対象 / 対象外を照合します。名称だけで NISA を推定しません。

SBI ranking universe policy:

- MVP対象: 国内株式、米国株式、国内ETF、米国ETF/海外ETF。
- 初期除外: 投資信託、ADR、REIT、FX、CFD、先物・オプション、暗号資産、債券、外貨建MMF、貴金属・コモディティ系ETF、レバレッジ、インバース、非tradable、非SBI対応。
- `symbol_universe.csv` / schema に SBI policy columns を追加済みです。local curated / source-import seed は conservative default として `broker=sbi_securities`, `tradability=unknown`, `is_sbi_supported=true`, `is_active=true`, `is_leveraged=false`, `is_inverse=false` を持てます。JPX 国内株と SBI 米国株 profile は `nisa_category=growth`, `investment_style=lump_sum` を既定値にし、ETF / REIT / 投信など個別判定が必要な商品では source 更新します。
- `tradability=unknown` は stock / ETF の初期 seed として通し、`not_tradable` だけを除外します。NISA metadata は国内株・米国株の成長投資枠 backfill と ETF / REIT source import まで反映済みです。ETF は公式 source 照合により `nisa_category=unknown` を解消済みです。投信公式 source import は Future Phase です。
- SBI証券サイトへのログインや画面スクレイピングは通常 workflow に含めません。SBI / JPX / NISA 一覧などを手動または curated source CSV に整形し、source import command で local master へ反映します。投信協会 / 投信CSV / 基準価額は Future Phase で扱います。
- Ranking / Screening は source site を直接参照せず、`symbol_universe.csv` と default policy helper だけを参照します。
- 投信向け metadata として `trust_fee_pct`, `aum`, `nisa_tsumitate_eligible`, `nisa_growth_eligible`, `installment_available`, `management_style`, `distribution_policy` を source CSV から取り込めます。ただし MVP ではランキング対象外です。
- 現在の候補マスタは 9,197件です。内訳は stock 8,087件、ETF 1,046件、REIT 58件、投信 4件、ADR 2件です。default ranking universe では stock / ETF のみを対象にします。2026-05-26 更新では、SBI最新一覧から消えた米国株19件・米国ETF5件を削除せず、履歴確認できるよう `not_tradable` / `is_sbi_supported=false` として保持しています。

Yahoo coverage check:

- `tools/check_symbol_universe_yahoo_coverage.py` は、`symbol_universe.csv` の対象行について Yahoo OHLCV（日足価格）を取得できるか確認する live smoke command です。外部通信を使うため、通常の local checks / CI には含めません。
- 国内株の確認例。metadata refresh 後は `metadata_source` が `yahoo` になるため、通常は `--asset-type stock --market jp` を主条件にします。refresh 前の raw/source 単位で確認する場合だけ `--metadata-source jpx_listed_stock` などを明示します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --asset-type stock --market jp --sample-size 30 --batch-size 10 --timeout-ms 15000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_jp_stock_sample30_20260520
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --asset-type stock --market jp --batch-size 25 --timeout-ms 20000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_jp_stock_full_20260520
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --asset-type stock --market us --metadata-source sbi_us_stock --batch-size 50 --timeout-ms 25000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_sbi_us_stock_full_20260520
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --asset-type etf --market us --metadata-source sbi_us_etf --batch-size 50 --timeout-ms 25000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_sbi_us_etf_full_20260520
```

- 2026-05-21 に実行した JPX 追加国内株の Yahoo coverage check では、サンプル 30件は 30/30 件成功。全数 3,645件は 3,641件成功、4件は短期期間で `YAHOO-NO-BARS` でした。失敗4件の個別再試行では、`9237.T` は同じ短期期間で取得成功し、`2344.T` / `4530.T` / `6565.T` は 2026-04-01 からの長め期間では取得できるものの、2026-05-12 〜 2026-05-20 ではバーがありませんでした。
- 2026-05-21 に実行した SBI 米国株 / 米国ETF の Yahoo coverage check では、米国株サンプル 30/30、米国株全数 4,240/4,293、米国ETFサンプル 29/30、米国ETF全数 593/607 が成功しました。失敗はすべて短期期間での `YAHOO-NO-BARS` です。クラス株式表記を正規化した `BRK-B` / `UHAL-B` の個別再確認は 2/2 成功しました。
- `--symbols` を使うと、失敗銘柄や表記修正後の銘柄だけを小さく再確認できます。
- `tools/analyze_yahoo_coverage_failures.py` は保存済みの coverage CSV を、銘柄マスタと照合して原因別に棚卸しします。2026-05-22 時点では、SBI米国株の失敗53件は `no_bars_short_window_or_yahoo_unsupported` 51件、旧表記 alias 解決済み2件です。SBI米国ETFの失敗14件は、レバレッジ除外3件、`yahoo_symbol` mapping 済み11件です。mapping 済み行は ranking / rebalance の Yahoo 取得時に provider symbol へ変換します。
- 結果は `data/marketdata/live_checks/` に JSON / CSV で保存します。

Phase 16 ranking implementation notes:

- `data/marketdata/symbol_universe.csv` is the ranking candidate master used before provider fetch. It is intentionally curated/local-first and currently carries display/search/filter metadata such as `symbol`, `name`, `market`, `asset_type`, `currency`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, and `risk_band`. Optional `yahoo_symbol` is used only when Yahoo needs a different ticker than the display/source symbol.
- Streamlit startup starts a daemon background symbol DB refresh worker instead of blocking the UI. The worker reads the formal master `symbol_universe.csv`, writes latest-only normalized runtime records to `data/cache/symbols_cache.sqlite`, keeps `symbol_refresh_queue.json` empty after successful batches, and updates `symbol_refresh_status.json`. Existing `symbols_cache.json` is treated as a legacy cache import source, not as the primary runtime store. The current network-free maintenance plan is: immediate startup batch 150 symbols, 75 symbols after 3 minutes, 75 symbols after 8 minutes, then 50 symbols every 5 minutes, with fresh records skipped and a 1000-symbol per-session safety cap. Cockpit selected symbols and Ranking comparison targets are registered internally as priority hints, so missing / stale records used by current workflows move ahead of ordinary background candidates without changing the visible UI. Cockpit registers the selected symbol only after a successful price / forecast fetch and skips repeated same-symbol requests for 30 minutes in the current session.
- To check whether any symbol is stuck in the refresh queue, inspect `symbol_refresh_queue.json` or run `backend.symbols.startup.find_pending_symbol_refresh_tasks()`. A healthy post-startup state has no `pending`, `retryable`, or `in_progress` tasks left after the local batch completes.
- The Phase 18 schema helper validates required columns, allowed enum values, decimal fields, duplicate tickers, and metadata freshness/source columns without requiring live provider access.
- The in-page screening condition panel filters comparison candidates by metadata, NISA eligibility, and metric ranges. `取得期間` and `重視して並べ替え` are not screening filters; they control ranking calculation and display ordering.
- Ranking build uses a fast batch path first: it fetches OHLCV in chunks, builds feature snapshots from already-fetched market data, then reuses existing Screening / Investment Score services. If the batch path fails with a provider/domain error, local/deterministic providers can fall back to the existing per-symbol preview path; live Yahoo failures are reported once without retrying every symbol to avoid repeated network failures.
- Yahoo OHLCV separates the stability-first Cockpit path from the speed-first Ranking path. Single-symbol Cockpit requests use `Ticker.history` first, retry transient DNS / curl timeout failures once with the same parameters, and retry Yahoo `possibly delisted` / `no price data` responses with `raise_errors=False` plus a non-expanded daily end date before surfacing a structured no-data error. Multi-symbol Ranking requests keep the smaller non-threaded yfinance `download` chunk path and retry empty batch responses once to absorb first-call warm-up / transient empty responses. The cockpit reuses one fetched OHLCV range for quote display and feature construction instead of fetching the same symbol again, and initial fetch skips live FX / fundamentals so price / forecast / score rows can render without waiting on nonessential live requests. SMAI shares one curl_cffi-backed yfinance session across `Search`, `download`, and `Ticker` calls so Yahoo cookie / crumb state stays attached to the same session. Because live Yahoo requests are network-dependent and can be slow or noisy, Streamlit ranking warns when selected symbols exceed 30 and suppresses yfinance's raw console noise in favor of structured UI error rows.
- Ranking rows are cached in Streamlit session state by `provider + symbols + start + end`. Re-running the same request or changing only the ranking weight preset reuses fetched rows and only re-sorts the display.
- Ranking display rows reuse a single symbol-master lookup map when building notes and modal guidance. This avoids repeated `symbol_universe.csv` scans during long-period ranking reruns and keeps row-click symbol-detail modal opening responsive.
- Ranking rows can include common-horizon advanced forecast fields (`advanced_forecast_horizon_days`, `advanced_forecast_predicted_return`, `advanced_forecast_score`, `advanced_forecast_confidence`, `advanced_forecast_upside_score`, `advanced_forecast_downside_score`, `advanced_forecast_quality_score`). These are calculated from the advanced forecast consensus over registered adapters, currently `advanced_linear`, `advanced_tree_sklearn`, `advanced_gbdt_sklearn`, and `advanced_quantile`, then shown as `高度予測` / `高度予測日数` / `高度予測スコア` / confidence context in the ranking table and selected-candidate details when enough local history exists. The consensus uses capped weights from confidence, error improvement, model agreement, and validation sample context. Ranking blends derived advanced upside / downside into `上昇気配` / `下降警戒` at 25%, and `AI総合` places the derived advanced scores inside the `予測・上昇気配30%` and `リスク・下振れ警戒25%` groups; missing or low-confidence advanced data is pulled toward neutral 50 instead of being treated as zero.
- Cockpit price / forecast display leads with `AI予測インサイト`. The card shows a short conclusion, `中心予測` as the main display name for the advanced-model consensus, downside / upside cases, forecast price, forecast range, confidence reason, model agreement, forecast dispersion, main reasons, cautions, and the forecast horizon. `中心予測` stays one row above the scenario cases, and the forecast price / range row follows the downside / upside comparison. Individual advanced model cards stay visible under the chart, while RMSE, error improvement, historical direction accuracy, relatively stable model, and simple forecast baseline comparisons are folded so the first view stays focused on the integrated forecast and uncertainty. The forecast remains decision-support context, not a future guarantee.
- Ranking result pages show `今回のランキング条件` before the ranking guide. It displays the selected evaluation policy, short summary, suited-for text, main-focus chips, common forecast horizon for that ranking run, grouped weight profile for `AI総合`, and a reminder that `下降警戒` / advanced downside caution are lower-is-better fields. The guide expander also includes beginner term rows for `AI総合`, `上昇気配`, `下降警戒`, `AI予測インサイト`, advanced upside / downside / confidence, and horizon.
- The ranking progress indicator reports batch fetch, feature construction, direction signal calculation, and final sorting so large candidate sets do not look frozen.
- Ranking deep-dive controls are rendered before the Decision Report block. The ranking Decision Report is generated lazily by `確認レポートを作成`, then reused for the same ranking source / evaluation policy so resorting and cockpit handoff remain responsive. Ranking report は上位候補メモとスコア詳細を分け、明細には symbol、銘柄名、評価方針、確認観点を並べて出力する。`AI予測インサイト` がある場合は、候補メモ、スコア詳細、分布、ファクター別上位、group checkpoint にも同じ予測文脈を残す。
- Ranking remains decision support only. Click a ranking row to open the shared `銘柄データ` modal with short ranking context plus local master details. Use the cockpit for detailed price / forecast / score-reason review.
- In `銘柄コックピット`, `銘柄データを見る` sits beside symbol selection and opens the same local-master modal for the selected symbol. Start / End inputs wrap to the next row. After fetch, the cockpit shows `投資判断メモ` combining score, warnings, valuation, income, price trend, and next-check wording. Research Evidence starts with an operation card that says `AI調査で確認すること` / `確認方針` before fetch, labels the button area as `調査アクション`, and shows `企業リサーチレポートを更新しました` after fetch. When AI Research has a report, the result panel begins with `企業リサーチサマリー`, followed by `定量情報サマリー`, `IR情報サマリー`, and `最新ニュース・開示サマリー`. These sections explain the company overview, main businesses, products/services, regions, scale, key metrics, IR availability, news/disclosures, and missing critical items as a company-understanding report. Normal UI keeps `企業理解の確認ポイント` as the main follow-up, while `詳細情報・開発者向け` is limited to distinct verification data such as Research Score, data-quality warnings, documents/source rows, grounded answers, retrieval quality, extracted claims, evidence detail, and external-source fetch status.
- `銘柄コックピット` と `銘柄ランキング` のresult areaには、Markdown / JSON / manifest / ZIP downloadsを持つ目立つ `Decision Report` blockを表示する。Markdownは人が読むmemo、JSONはstructured reproduction context、manifestはpackage contentsの説明、ZIPはfull package保存用。Cockpit reportsは、overall judgement card、3-line summary、main evidence block、sectioned detail expandersを持つstructured UIとして先に表示する。Cockpit / Ranking Research Summary panels は、AI Research reportがある場合にResearch Score summary、component、warning rowsを参考contextとして表示する。Cockpit では `Research Score（根拠資料の確認材料）` の折りたたみ内に読み方、要約、観点別内訳、注意点をまとめ、詳細データ側は検索品質や根拠詳細を中心にする。Ranking selected-candidate breakdownはreport-derived Research Score / confidenceを確認材料として表示できるが、ランキング順位は変えない。Cockpit `AI調査を更新` でResearch reportが作成され、documentsまたはevidenceがある場合、exported contextには `Research Evidence` と `Research Score` sectionsが入り、component rows、confidence、supporting evidence、warnings、non-advice notesを保存する。Cockpit / Ranking reports は `AI予測インサイト` がある場合、中心予測・信頼度・方向シグナルへの反映を同じ確認材料として保存する。Ranking reportsは単一top-symbol reportではなく、comparison context、score distribution、factor leaders、group-level deep-dive checkpointsを中心にする。Ranking Markdown bodyは `レポート本文を表示` 内に置く。これはpoint-in-time analysis memoであり、buy/sell/hold instructionではない。
- In `リバランス`, the result area shows a prominent `投資判断レポート` block with Markdown / JSON / manifest / ZIP downloads. The report organizes current holdings, target allocation, allocation drift, rebalance review candidates, Risk breaches, and confirmation checkpoints. The Markdown body remains inside `レポート本文を表示`. It is a review aid, not an order instruction.
- UI リッチな PDF report / Excel report は将来の Advanced Export 範囲です。現行の Decision Report export は Markdown / JSON / manifest / ZIP を正とします。

Phase 16 final UI smoke checklist:

- Change screening conditions and confirm candidate count / comparison symbols update coherently.
- Build a ranking and confirm progress messages are shown.
- Run the same ranking again and confirm cached rows are reused.
- Change only `重視して並べ替え` and confirm rows are re-sorted without a provider refetch.
- Click a ranking row and confirm the symbol-detail modal opens quickly, including `判断補助` guidance when ranking context exists.
- Open `銘柄データを見る` in `銘柄コックピット` and confirm the selected symbol's local-master data appears in the same modal.
- Fetch cockpit data and confirm `投資判断メモ` appears without presenting buy/sell advice.
- Confirm Rebalance labels continue to describe decision support rather than buy/sell advice.

### 投資レーダー

確認できるもの:

- 保存済み news dashboard snapshot。保存済みがない場合は network-free demo snapshot を表示する。
- `ニュース表示を更新` で Standard Mode の外部ニュースRSS取得を実行し、`data/cache/news_dashboard_snapshot.json` に保存する。Google News RSS を12カテゴリで取得し、raw 150〜250件程度の候補から URL / title 重複を除き、最大100件の確認材料に圧縮する。RSS取得に失敗した場合は既存cache、保存済みがなければ demo snapshot にフォールバックする。
- `市場ニュースヘッドライン` は重複のない4件を2列×2段で6秒ずつ静止表示し、次の4件へ切り替える。ホバー中は停止し、ページドット選択後は選択ページを固定する。モーション抑制環境では自動切替しない。
- `ニュース表示を更新` 実行中も共通SMAIローディング画面を表示し、既存cacheの `市場トピック` を読み物として表示する。更新処理のための追加fetchは行わない。
- タイトル右上に `情報鮮度` とJST取得時刻を小さく表示する。上部の状態カードは置かず、更新ボタンと必要時の警告だけを表示する。ヒートマップ本体の top-line でセクター数と銘柄タイル数を確認する。
- 市場ニュースヘッドライン。流れるヘッドラインバーとカードに title、source、published_at、freshness、category、AIコメント、確認ポイント、元記事リンクを表示する。ヘッドラインはピル内で2行まで読めるようにし、UI初期表示は20〜30件程度に抑え、保存上限100件を一度にカード描画しない。
- 投資ヒートマップ。投資カテゴリをセクター枠、注目銘柄をシンボル＋銘柄名 / 企業名付きタイルとして詰める株式ヒートマップ風UIで、値動き、取引量の活発さ、ニュース件数、freshness、risk / positive / official source count から集計した確認用の温度感を見る。銘柄タイルはニュースに直接紐づく銘柄に加え、`data/marketdata/symbol_universe.csv` の広い候補からカテゴリ適合、時価総額帯、データ品質、市場シグナルを使って注目度順に補完する。市場指標が欠けるカテゴリは、ニュース材料の positive / risk / official / heat_score から `ニュース代理` のシグナルを表示する。
- カテゴリ別ニュースレーン。カテゴリごとの代表ニュースを幅のある3列カードで確認し、上部ヘッドラインに出した上位記事は下部カード側から除外して重複感を抑える。関連銘柄は `本文に出た銘柄` と `SMAI推測候補` を分けて縦並びボタンで表示する。本文に出た銘柄は最大8件まで優先し、推測候補は残り枠に可変で補完する。
- 関連銘柄ボタンにはシンボルと銘柄名 / 企業名を表示し、`銘柄コックピット` へ遷移する。Investment Score / Research Score / Ranking order は変更しない。

運用上の注意:

- 通常 checks は fake snapshot / Static adapter / RSS fixture ベースで network-free に維持する。live RSS smoke は手動更新または明示的な検証時だけ行う。
- ニュースは市場テーマと確認材料の入口であり、売買判断や銘柄推奨ではない。
- 追加provider、詳細フィルタ、Watchlist連動、通知は後続範囲。

### リバランス

Rebalance は `Rebalance Cockpit` として、次の順に確認します。

1. 現在資産
2. 目標配分
3. 配分見直し候補
4. Risk 判定

確認できるもの:

- sample / account / as-of / cash / target weight input
- summary flow
- target allocation percentage input
- current positions
- target allocations
- allocation comparison chart
- rebalance review candidates
- risk decision
- beginner-friendly risk breach confirmation points
- `投資判断レポート` Markdown / JSON / manifest / ZIP download for current holdings, targets, drift, rebalance review candidates, Risk breaches, and confirmation checkpoints
- JSON / CSV / Markdown / ZIP export

## 7. 外部 MarketData provider

現在使える provider:

| provider | 状態 | 既定/用途 | 主な用途 |
| --- | --- | --- | --- |
| `yahoo` | 実装済み | 既定 | yfinance による live data 取得 |
| `mock` | 実装済み | テスト / オフライン用 | deterministic な MVP 確認 |
| `csv` | 実装済み | テスト / オフライン用 | ローカル CSV 確認 |
| `polygon` | metadata のみ | 将来候補 | live provider 候補 |

`yahoo` は既定設定で `allow_external_providers: true` です。
通常の自動テストと local checks は `tests/fixtures/config/local.yaml` などで `mock` を明示し、外部 API に依存させません。

## 8. ローカル検証

まとめて確認:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

個別確認:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check . --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy .
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

Markdown UTF-8 check:

```powershell
.\venv_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

SMAIアシスタント / Confirmable Action の Playwright smoke:

```powershell
.\venv_SMAI\Scripts\python.exe tools\playwright_assistant_action_smoke.py
```

このコマンドは network-free の静的HTML harnessを生成し、Tool Plan、navigation link、Workflow Sessionの進行状態、`create_decision_report` / `update_research` の確認カード、success / partial_success / failed result card、安全文言、raw provider detail 非表示を確認します。起動済み Streamlit も確認する場合だけ、別terminalで `SMAI_DISABLE_BACKGROUND_WORKERS=1` を指定してアプリを起動し、次のようにURLを渡します。

```powershell
.\venv_SMAI\Scripts\python.exe tools\playwright_assistant_action_smoke.py --app-url http://127.0.0.1:8524
```

Assistant loading UI / auto transition の実Streamlit smoke:

```powershell
.\venv_SMAI\Scripts\python.exe tools\playwright_assistant_loading_streamlit_smoke.py
```

このコマンドは空きportで遅延fake GatewayとStreamlitを起動し、warming中のInvestment Radar icon、ready後の自動遷移、入力途中テキスト保持、Gateway失敗時のfallback表示・入力可能状態・stack trace非表示を確認します。外部network、実Ollama、既存Gateway processには依存しません。

## 9. 更新ルール

- 実装状態が変わったら README / PROJECT_CONTEXT / Roadmap / Operations Guide を同期する。
- UI に見える変更は `07_UI_Wording_Policy.md` と `08_Phase16_UI_Improvement_Plan.md` も確認する。
- 作業履歴は `Documents/99_Work_Log.md` の先頭へ追加する。
- Research RAG は Phase 20 local evidence slice を deterministic foundation として開始済み。`backend/research` の local UTF-8 document ingestion / chunk / keyword search / deterministic Research Summary、`設定 / データ情報` での session-local資料登録は、通常 tests / demo seed / user archive / fallback として維持する。今後の標準ユーザー導線では、`銘柄コックピット` の `AI調査を更新` が外部の最新IR・開示・ニュース・provider evidence を取得/参照し、Research Evidence / Research Score / Cockpit Decision Report に反映する。価格データ取得時にはResearch RAGを自動実行しない。Ranking evidence-status display は軽量表示に留め、Research Score によるランキング順位変更は現時点では行わない。
- Stock News RAG は Phase 21.5 の first local deterministic slice として、`source_type=news` で登録されたローカル資料から URL 付きニュースだけを `銘柄コックピット` の Research Evidence card に統合表示する。これはテスト/fixtureの土台であり、通常ユーザー導線では外部ニュース adapter に置き換える方向。news 資料には `url:` または `source_url:` 行、任意で `source:` / `summary:` 行を含める。Investment Score / ランキング順位は変更しない。
- External Research / News fetch は Phase 21.6 / 21.7 の first UI slice として、`ExternalResearchSourceAdapter` protocol と backend `allow_network` gate を持つ。独立した `外部資料取得（明示許可）` UI は廃止し、`AI調査を更新` の標準処理へ統合済み。既定 adapter は EDINET（`EDINET_API_KEY` 設定時のみ live call、未設定時 no-op）、TDnet timely disclosure、企業IR site、Google News RSS headline search、Yahoo Finance profile / news を順に取得する。Phase 21.7 backend では `ExternalStockNewsAdapter` / `ExternalStockNewsFetchService` が URL 付き外部ニュースを `StockNewsEvidence` に正規化し、viewpoint、sentiment、freshness、dedupe、network opt-in gate を扱う。Google News RSS は取得したRSS itemを `source_type=news` の `ExternalResearchSourcePayload` に変換し、通常 checks はRSS文字列fixtureで確認する。取得本文・変換Markdown・manifest JSON は既定では保持しない。取得結果は session-local RAG store でその場の summary / Research Score / News 表示に一時参照し、画面やReportには provider / fetched_at / published_at / source URL / freshness_status / freshness warning / 短い要約だけを残す。Cockpit Decision Report には `外部参照ソース` section として trace row だけを含め、本文・local path・document hash は含めない。通常 checks は fake adapter / fixture を使い、network 非依存を維持する。
- `tools/fetch_research_yfinance_profile.py --symbol 7203.T --write` は、確認用の実データResearch資料を Yahoo Finance / yfinance から取得して `data/research_docs/` に保存する。外部通信を使うため通常 checks には含めない。
- EDINET / TDnet / IR site などの外部 source adapter が安定しても、外部取得本文を自動保存しない。`data/research_docs/` は開発 fixture、demo seed、private note、ユーザーが明示保存した資料、または fallback として扱う。永続化が必要な場合は、既定取得とは別の `資料を保存する` / archive action として実装する。
- Research Summary は、外部LLMを使わず、local rule-based `CompanyResearchSummary`、`ResearchBrief`、`InvestmentInsight`、`InvestmentQuestionSummary` へ変換してから表示する。通常表示では provider profile の生フィールド羅列を出さず、`CompanyResearchEvidence` で company profile / IR / TDnet / news / market data の役割を正規化する。最初に `企業リサーチサマリー` として企業概要、主な事業、製品・サービス、地域展開、規模感、直近の注目ポイントを表示する。続けて `定量情報サマリー` に売上高、営業利益、純利益、EPS、PER、PBR、ROE、配当利回り、時価総額、従業員数、`IR情報サマリー` に決算短信、決算説明資料、有価証券報告書、適時開示、中期経営計画、配当・自社株買い、業績予想修正、`最新ニュース・開示サマリー` に直近ニュース/開示と影響カテゴリ、公式IR確認要否を表示する。IR情報サマリーは category-specific required / exclude keywords と source重複抑制を使い、`tdnet` source typeだけでは業績予想修正や配当・自社株買いに分類しない。`found` は本文精読済みではなく `関連候補あり` と表示し、内容確認はリンク先の公式資料で行う前提にする。ニュース/開示は `Market Intelligence` パネルとして通常カードから分け、URL付き項目は初期折りたたみの citation list から開く。その直後の `投資ヒントとなるニュース` はURL付き一般ニュースだけの `注目材料 Top 3` 表示で、TDnetやprovider sourceを混ぜない。IR / news / metric では found / missing / unparsed / unverified を区別する。`詳細情報・開発者向け` は通常表示と用途が重なるAI整理メモ、読み方サマリー、出典カード再掲を省き、Research Score、データ品質、検索品質、抽出主張、根拠資料詳細、外部source取得状況などの検証用データに絞る。上部の operation card は fetch 前の `確認方針` と fetch 後の `企業リサーチレポートを更新しました` / `追加確認` に分け、抽出指標数、出典カード数、Research Score は詳細側に下げる。
- Research Summary maturity slice として、`ResearchBrief` の前段に `ResearchFactSummary` を追加済み。運用上の表示目標は、取得状態や件数ではなく、事業概要、主要事業、地域・収益源、確認済みのIR / 公式資料 / TDnet / ニュース、主要定量指標、業績見通し、配当・株主還元方針、直近イベント、良材料候補、注意材料候補、未確認項目を source-backed fact として提示すること。provider-only の情報は公式資料と同列に扱わず、`外部データ由来では` と明示する。
- ResearchBrief の確認ポイントは、provider profile や検索根拠の英語断片をそのまま出さず、`会社概要`、`確認できた事実`、`公式資料で未確認` の3ブロックに言い換える。良材料候補 / 注意材料候補は詳細側の確認材料とし、主表示では件数よりも、事業・数値・業績見通し・株主還元・未確認項目の中身を優先する。ニュース取得警告などの「根拠不足」は注意材料ではなく確認不足として扱う。
- `ResearchBrief` の定量評価では、取得できた PER / PBR / ROE / 売上高 / 営業利益 / 純利益 / EPS / 配当 / 時価総額などを source type と confidence 付きの小カードで表示する。取得できない主要指標は missing metrics として警告パネルに明示する。
- `ResearchBrief` の確認不足は、`未確認の定量指標` のような内部表現をそのまま見せず、`まだ確認できていない数値` として表示する。これは悪材料ではなく、公式資料で追加確認する項目であることを併記する。
- `ResearchBrief` の confidence は情報源の信頼度であり、投資判断の正しさではない。公式IR / TDnet / EDINET / 企業IRは high、Yahoo Finance / provider profile / news は medium、キーワード抽出のみは low として説明する。Research Score は調査メモの後ろに表示し、ランキング順位は既定では変更しない。
## スマホ / PWA の前回状態復元

Streamlit の WebSocket session が iOS / Safari / PWA 側で破棄されても、SMAI は
URL の `client=smai_client_...` に対応する
`data/user_state/clients/<client_id>.json` から軽量な前回状態を復元します。

- URL に `client` がなければ安全なランダムIDを生成し、query parameterへ反映します。
- `last_seen_at` から30分以内は、前回ユーザー、主要画面、Cockpit銘柄を自動復元します。
- 30分を超えた場合、または保存ユーザーが存在しない場合は、該当端末のJSONを削除して
  ユーザー選択画面へ戻ります。
- 明示的なプロフィール/ページ URL query parameter は通常起動より優先します。
- 保存対象は最後のユーザー、主要画面、Cockpit 銘柄、Ranking の主要条件、
  Cockpit / Ranking のデータ取得元です。
- DataFrame、画像、ニュース本文、Research本文、LLM応答は保存しません。
- 値が変わった場合だけ atomic write し、破損JSON、存在しないユーザー、
  読み書き失敗時は通常起動へフォールバックします。
- 復元だけでは価格取得、ランキング作成、AI調査更新、ニュース取得を実行しません。
- ユーザーメニューの `この端末のセッションを解除` で、端末JSONと選択状態を削除して
  ユーザー選択画面へ戻せます。
- 手動起動・自動起動・監視復旧は共通ランチャーの排他ロックを使用します。
  同時に起動された場合、後続処理は既存サーバーを検出して正常終了します。
- Streamlit 1.38では未対応の切断セッション保持・WebSocket ping設定を使用しません。
  セッション復旧はクライアントスナップショットを使用します。

手動確認では、ユーザー、Cockpit、銘柄を選択してF5更新またはPWAを閉じ、30分以内の
再表示で同じ状態が復元されることを確認します。`last_seen_at` を30分超へ変更した場合は、
ユーザー選択画面へ戻り、該当する `clients/<client_id>.json` が削除されることも確認します。
LAN URLとTailscale URLは別々に確認します。
