# Roadmap

## Phase 1: ローカル Ollama 接続

- FastAPI Gateway
- `/health`
- `/api/v1/chat`
- `/api/v1/summarize`
- Ollama client
- 基本 schema / tests
- provider error detail
- opt-in live Ollama smoke

## Phase 2: SMAI から投資コメント生成に利用

- SMAI 側 `AssistantContextBundle` から Gateway へ接続
- SMAI Copilot / Decision Report の説明補助
- deterministic fallback 維持

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
