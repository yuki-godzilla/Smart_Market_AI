# Ranking History コード影響調査報告

調査日: 2026-07-03

## 1. 調査ファイル

- `ui/app.py`: ranking page、作成処理、結果 dashboard/table、CSV/JSON、cockpit/favorite CTA
- `ui/ranking.py`: 条件、label、filter/signature、ranking helper
- `ui/ranking_state.py`, `ui/state.py`: 条件と結果の session state
- `ui/ranking_filter_chips.py`: `st.dialog` を使う既存 sub-UI
- `ui/styles.py`, `docs/responsive/*`: responsive 方針
- `ui/user_data.py`, `backend/users/user_repository.py`, `ui/notification_center.py`: profile ID と切替
- `ui/favorites.py`, `ui/watchlist_snapshots.py`: profile別 JSON 保存
- `ui/last_session.py`: atomic JSON と復帰 state
- `backend/news/cache.py`, `backend/symbols/cache.py`: temp file / replace / backup の参考実装
- ranking/user/favorite/watchlist/last-session/style/responsive 関連テスト
- `PROJECT_CONTEXT.md`, `Documents/96_Manual_UX_Review_Checklist.md`, `Documents/97_Functional_Spec_Issues.md`

## 2. ランキング画面

### 構造

- メイン描画: `ui/app.py::_render_market_data_ranking()`（8355行付近）
- page routing: `ui/app.py::main()` が side menu の `ranking` を同関数へ振り分ける
- 条件 UI: 同関数の冒頭から action area。探索条件 dialog は `ui/ranking_filter_chips.py`
- 条件状態: `ui/ranking_state.py::current_ranking_filter_state()` / `persist_ranking_filter_state()`
- 作成 button: `build_market_data_ranking`（8671行付近）
- 計算: `_build_market_data_ranking_rows()` と fast/from-previews variants（9525行以降）
- 保存差込候補: 計算成功後の `set_cached_ranking_build()`、`MARKET_DATA_RANKING_STATE_KEY` 等への代入箇所（8738–8744行付近）
- 結果変換: `apply_ranking_weight_preset()` → `investment_score_display_rows()` → Research/LLM reference の表示 enrichment
- 結果 table: `_render_ranking_result_table()`（5547行付近）、入力は `list[dict[str, str]]`
- table frame: `ranking_result_aggrid_frame()`（3392行付近）
- cockpit CTA / favorite: 8860–8910行付近
- CSV/JSON: `investment_score_csv_download()` / `investment_score_json_download()` を 8951行付近で使用
- responsive smoke: `tests/ui/test_responsive_ranking_smoke.py`

### 安全な保存トリガー

保存は button click 分岐内で計算が成功し、`rows` と `error_rows` が確定した直後に行う。条件変更、AgGrid event、dialog rerun、download rerun では呼ばない。さらに repository で5分の signature dedupe を行う。例外時や全件失敗時を保存するかは、MVPでは「結果行1件以上のみ保存」を推奨する。

### UI再利用評価

table は rows 入力のため再利用余地がある。ただし現在は以下が密結合している。

- `load_favorites()` による現在状態の混入
- favorite click 時の `toggle_favorite()`
- `_symbol_universe_rows_by_symbol()` による現在 metadata
- `_render_symbol_universe_detail_dialog()` による保存時/現在値の混在
- key が `ranking_source` と preset を前提にする

したがって、まず `mode="live" | "history"` と action policy を追加し、pure frame builder と Streamlit actions を分離する。dashboard 全体の丸ごと再利用は、現在の Research/LLM enrichment と Decision Report を再実行するため不可。履歴は snapshot から表示用 rows を組み立てる。

## 3. ユーザー別保存

- 現在 user ID: `st.session_state["smai_current_user_id"]`
- accessor: `ui.user_data.current_user_id()`
- path: `data/user/profiles/<user_id>/<filename>` を `profile_data_path()` が生成
- ID: `backend/users/user_repository.py` が `u_<random>` を生成し、system `default` を持つ
- favorites / watchlist snapshots: profile配下 JSON。default は session state のみ
- 通知: SQLite だが、履歴の大きな snapshot 保存モデルとは目的が異なる
- legacy `data/user/favorites.json` は migration 用。新規履歴の fallback にしない

注意: favorites と watchlist snapshot は direct `write_text` で atomic ではない。ランキング履歴は index + snapshot のため、`ui/last_session.py` 等の temporary file + replace を採用する。

## 4. 画面遷移

既存 top-level は side menu と session state。Assistant は target page を side menu state/queryへ渡し、ranking-to-cockpit は session state に symbol/period を設定する。Ranking 内には filter dialog の substate があるが、一覧/詳細の page router はない。

推奨は side menu page を `ranking` のまま維持し、`ranking_view_mode` と selected run ID で `_render_market_data_ranking()` 冒頭から live/list/detail を分岐すること。ユーザー切替時の stale run ID、dialog open state、last-session restore との衝突を初期化する。履歴 subview を last-session 保存対象にするのは非MVPとする。

## 5. 条件復元

`current_ranking_filter_state()` は既存 defaults と metric defaults を列挙しており、snapshot 化に使える。復元用の public helper は未実装。`apply_ranking_filter_state()` は preview rows と選択 labels の更新を伴うため、そのまま過去条件復元には使わない。

新規 `restore_ranking_filters(filters)` は allowlist、型変換、現行 options 検証を行い、該当 widget/session keys と `MARKET_DATA_RANKING_FILTERS_STATE_KEY` を設定する。結果 state/cache は clear するが、計算関数を呼ばない。

## 6. 削除確認

汎用削除確認 helper は見当たらない。既存には symbol detail と ranking filter で `st.dialog` の実績があり、Assistant には独自確認 card がある。履歴削除には `st.dialog` で対象日時・名前を示し、キャンセル/削除を明示する小さな専用 dialog が自然である。

## 7. テスト方針

### 保存基盤

- profile A/B の分離、default 非永続
- index/snapshot round-trip と ownership
- 30通常履歴 + 任意 pin、pin解除時 prune
- index atomic failure、snapshot write failure、lock timeout
- missing/corrupt/unknown-version/oversize
- 5分未満/以上の signature dedupe（時計 injection）

### UI・状態

- live → list → detail → list/live
- user切替で detail selection clear
- pin section が上、各 section は新しい順
- snapshot rows のみが history table に渡る
- 保存時点注意文が常時表示
- history action policy で live enrichment/report が呼ばれない

### 条件復元

- 全条件、部分条件、未知キー、廃止値、型不正
- 復元後に live form が表示され、buttonを押すまで fetch/build が0回

### 回帰

- `tests/test_favorites.py`
- `tests/test_user_profiles.py`
- `tests/test_watchlist_snapshots.py`
- `tests/test_last_session_state.py`
- ranking helper/UI tests（主に `tests/test_ui_forecast_display.py`）
- `tests/test_ui_styles.py`
- `tests/ui/test_responsive_ranking_smoke.py`

手動/Playwright は4 viewport、page overflow、tap target、dialog、Streamlit exception、ユーザー切替を確認する。

## 8. 主なリスク

1. 現在の ranking display row は日本語表示キーで、将来の文言変更に弱い。
2. 保存前後で Research/LLM reference が session/current cache から付加され、永続対象境界を明示する必要がある。
3. favorite は保存時状態と現在状態の意味が異なる。
4. 複数 browser の同一 profile 更新は既存 JSON と同様に競合し得る。
5. pin 無制限は容量増加要因。MVP後に容量表示/上限を検討する。
6. default user を暗黙に共有ファイルへ保存すると U1 の分離方針を破る。

## 9. 未確認・次フェーズ決定事項

- `ranking_logic_version` / `universe_version` の正式な version source
- 1 snapshot の最大行数・最大 byte と pin 容量警告閾値
- Research/LLM の短い表示値を snapshot に含めるか、MVPでは除外するか
- 通常履歴削除にも毎回 dialog を出すか（推奨: 出す）
- CSV を Phase 3 に前倒しするか

## 10. 推奨実装順

typed contract → repository atomicity/user isolation → service dedupe/prune → 作成成功点への保存接続 → 一覧 → 詳細 → table action policy → 条件復元。巨大な `ui/app.py` の全面分割は行わず、履歴固有責務だけを新規 module へ出す。
