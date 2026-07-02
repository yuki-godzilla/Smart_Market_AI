# ランキング履歴 実装計画

## Phase 0: 調査・設計

- 要件、UI、保存契約、既存コード影響を確定する。
- 完了条件: 本ディレクトリ群の設計文書レビュー完了。

## Phase 1: 保存基盤

- `backend/ranking_history/models.py`、`repository.py`、`service.py` を追加。
- user-scoped path、atomic JSON/GZIP、lock、dedupe、30件 prune を実装。
- default ユーザーは永続保存不可を typed error/result で表す。
- 保存トリガーを `ui/app.py` の明示的なランキング作成成功後へ接続する。ただし UI はまだ一覧を持たなくてよい。
- テスト: user isolation、round-trip、corrupt/missing、atomic failure、dedupe、prune。

## Phase 2: 一覧画面

- `ui/ranking_history.py` に一覧 view model、検索、filter、section sort を実装。
- `ui/app.py::_render_market_data_ranking()` 冒頭へ履歴ボタンと subview router を追加。
- `ui/styles.py` に共有 breakpoint 準拠の最小 CSS を追加。
- テスト: view model、遷移 state、default user、responsive browser smoke。

## Phase 3: 詳細画面

- snapshot loader、条件・metadata・注意表示を実装。
- pin/unpin と確認付き delete を追加。
- 欠損 snapshot の安全な fallback を実装。
- テスト: ownership、missing/corrupt、pin/delete、一覧復帰。

## Phase 4: 結果 UI の history mode

- `_render_ranking_result_table()` と周辺 action を、表示と live action policy に分離する。
- history は保存済み `result_rows` のみを表示し、現在 enrichment や再計算を禁止する。
- お気に入りは「現在」、保存時状態は監査表示として明確に分離する。
- コックピット CTA は現在情報を開く導線として扱う。
- テスト: live/history action matrix、現在値混入防止、通常ランキング回帰。

## Phase 5: ピン留め・削除・保存上限の統合確認

- 一覧上段固定、pin解除時 prune、競合時再読込を確認。
- 容量・件数表示、破損通知、操作ログを整える。
- テスト: 30 normal + pinned、境界時刻、複数 repository instance。

## Phase 6: 条件復元

- snapshot filters の allowlist validator と `ui/ranking_state.py` の復元関数を追加。
- 廃止キーは無視し、未知値は現行 default へ落とし、注意を表示。
- live へ戻すだけで `ランキング作成` は利用者が押す。
- テスト: full/partial/old filters、外部取得が自動発火しないこと。

## Phase 7: 将来拡張

- snapshot CSV、タイトル/メモ、履歴比較、cleanup/migration UI。
- CSV は既存 `investment_score_csv_download()` の入力契約を共通化して再利用する。

## 変更対象候補

- 新規: `backend/ranking_history/{__init__,models,repository,service}.py`
- 新規: `ui/ranking_history.py`
- 更新: `ui/app.py`, `ui/ranking_state.py`, `ui/state.py`, `ui/styles.py`, `ui/content/ranking_texts.py`
- 更新: `Documents/06_MVP_Operations_Guide.md`, `PROJECT_CONTEXT.md`, `Documents/99_Work_Log.md`（実装時）
- 新規テスト: `tests/test_ranking_history_{repository,service,ui}.py`
- 更新テスト: `tests/test_ui_forecast_display.py`, `tests/test_favorites.py`, `tests/test_user_profiles.py`, `tests/test_last_session_state.py`
- UI smoke: `tests/ui/test_responsive_ranking_history_smoke.py` または既存 ranking smoke 拡張

## 検証順

1. repository/service の targeted pytest
2. ranking UI helper、favorites、user profile、last session の回帰
3. Ruff、Mypy 対象モジュール、project Black helper
4. 4 viewport の network-free Streamlit smoke
5. 必要時のみ全体 local checks

## リスクと対策

- 現行 `ui/app.py` が巨大: 大規模分割を前提にせず、新規 service/UI module と小さい adapter を追加する。
- display row が日本語キー依存: snapshot contract は英語キー、変換関数を1箇所に置く。
- rerun 重複: button success path + persistent signature window の二重防御。
- index/snapshot 部分更新: atomic replace と保存/削除順序を固定。
- 複数ブラウザ競合: user-scoped lock、lock後再読込。
- 履歴と現在値混同: history mode は enrichment 禁止、注意文、CTA文言を分離。
- default user 方針: 永続化しない既存境界を維持し、暗黙の共有保存へ fallback しない。

## ロールバック

機能 flag または subview 導線を無効化すれば live ranking は従来経路を維持できる構造にする。保存データは独立ディレクトリのため、機能無効化時も削除しない。schema migration は reversible backup なしに実行しない。
