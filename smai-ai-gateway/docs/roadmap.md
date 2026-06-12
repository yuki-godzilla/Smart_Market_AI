# Roadmap

## Phase 1: ローカル Ollama 接続

- FastAPI Gateway
- `/health`
- `/api/v1/chat`
- `/api/v1/summarize`
- `/api/v1/context-answer`
- Ollama client
- 基本 schema / tests
- provider error detail
- opt-in live Ollama smoke
- SMAI 本体側の `SMAI LLM Factor` 初期 schema / fake service / file-backed cache / deterministic backtest evaluator / Cockpit 参考表示 / Ranking 参考表示は親プロジェクト側で実装済み。Gateway 側にはまだ構造化抽出 endpoint を追加しない。

## Phase 2: SMAI から投資コメント生成に利用

- SMAI 側 `AssistantContextBundle` から Gateway へ接続
- SMAI Copilot / Decision Report の説明補助
- context answer response の `materials` / `cautions` / `next_checkpoints` を UI 表示へ接続
- deterministic fallback 維持

## Phase 2.5: 構造化特徴量生成の安全基盤

- 将来の `SMAI LLM Factor` 向けに、RAG / News / IR 由来の定性材料を JSON へ変換する prompt profile を検討する
- Gateway は provider 呼び出し、prompt 実行、timeout、error normalization を担当する
- `LLMFactorResult`、factor schema、source hash、file-backed cache、deterministic backtest evaluator、Cockpit / Ranking 参考表示は SMAI 本体側の初期 slice で実装済み。broader historical backtest、cache policy expansion、UI 統合拡張も SMAI 本体側で扱い、Gateway から SMAI module は import しない
- LLM は最終予測、ランキング順位、Investment Score、売買判断を決めない
- source URL、source date、model name、prompt version を保持できる request / response 形を検討する
- 通常 tests は network-free、live provider smoke は opt-in に分離する

## Phase 3: 他ローカルツールへ展開

- SMAI 以外のローカルクライアントからの利用
- 汎用テキスト要約
- 汎用プロンプト実行
- 汎用チャット

## Phase 4: 運用機能

- 認証
- ログ
- API key
- rate limit
- provider 切替

## Phase 5: 別リポジトリ化 / Git submodule化

- SMAI 本体との境界を HTTP API に限定
- Gateway 単体 CI
- versioning

## Phase 6: スマホ / PWA / クラウド対応

- PWA / mobile client からの利用
- Cloud deploy option
- remote provider support
