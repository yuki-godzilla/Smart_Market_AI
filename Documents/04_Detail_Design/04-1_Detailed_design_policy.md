# 🧭 04-1_Detailed_Design_Policy

#### [BACK TO README](../../README.md)

## 0. Current Sync Status

この文書は **2026-05-18 時点の実装状態に同期済み**です。
現在の詳細設計は「実装済みMVP」と「planned / deferred」を混在させず、以下の扱いで読むこと。

| 区分 | 現在の扱い |
|---|---|
| Core / Config / Error / Data contracts | implemented |
| MarketData mock / csv / provider registry / opt-in live adapter foundation | implemented |
| Feature Store Lite | implemented |
| Risk pre-trade check | implemented |
| Portfolio snapshot / no-solver rebalance / Portfolio-to-Risk workflow | implemented |
| Screening Score | implemented |
| Forecast baseline / multi-model consensus | implemented |
| Investment Score | implemented |
| Streamlit cockpit / ranking / rebalance UI | implemented; final browser smoke recommended |
| Research RAG | designed, not implemented |
| Execution / broker order sending | deferred, not implemented |
| optimizer based portfolio solver | deferred, not implemented |

## 1. Purpose

01〜03で定義した要件・SLO・非機能を、Codex が実装しやすい粒度に落とし込みます。
方針は **実装を正にし、ドキュメントは現在地・制約・次の一手を短く示す** ことです。

## 2. Scope

### 実装済みとして扱う範囲

- `backend/app/main.py`: FastAPI entrypoint and wiring
- `backend/core`: settings, data contracts, domain errors
- `backend/marketdata`: mock / csv providers, provider registry, live provider adapter foundation, feature builder
- `backend/risk`: deterministic pre-trade rules
- `backend/portfolio`: snapshot, no-solver rebalance, risk workflow
- `backend/screening`: explainable score ranking
- `backend/forecast`: deterministic baseline models, evaluation, consensus
- `backend/scoring`: Investment Score
- `ui/app.py`: market-data cockpit, ranking, forecast / screening / scoring display
- `ui/rebalance_app.py`: Rebalance Cockpit
- `tools`: local check helpers and rebalance demo

### 設計済みだが未実装として扱う範囲

- `backend/research`: Research RAG / evidence search / Research Score
- `backend/reporting`: Decision Report dedicated module
- `backend/execution`: broker order execution / webhook / idempotency
- optimizer solver backend: `pulp` / `ortools`

## 3. Detail Design Depth Policy

| 対象 | 詳細度 | 理由 |
|---|---:|---|
| MarketData / FeatureBuilder | High | すべての分析の入力であり、欠損・通貨・期間の影響が大きい |
| Risk | High | 判定根拠と BLOCK / REVIEW の説明責任が必要 |
| Portfolio | High | 金額換算・目標配分・Risk連携の整合性が必要 |
| Screening / Forecast / Investment Score | High | UIでユーザー判断に直結する |
| Streamlit UI | Medium | 初心者向け文言・導線・ダウンロードが重要 |
| Research RAG | High, planned | 長期企業分析の中核候補だが、現時点では未実装 |
| Execution | Low for now | broker送信は重点外。設計メモとして保持 |

## 4. One-Pager Template

各 One-Pager は以下を最低限含めます。

1. Current Sync Status
2. Purpose & Scope
3. Public Interfaces
4. Data Contracts
5. Algorithms & Rules
6. Error Handling
7. Config Knobs
8. Test Plan
9. Out of Scope / Deferred
10. Next Implementation Target

## 5. Cross-cutting Standards

- 通貨・数量・価格は `Decimal` を優先する。
- 日付は `date`、日時は UTC `datetime` を基本にする。
- Pydantic v2 の `StrictBaseModel` / `StrictConfigModel` を再利用し、未知フィールドは拒否する。
- default config provider は `mock`。Streamlit Market Data の provider selector は投資判断 UI として `yahoo` を初期表示・先頭表示し、外部 provider は画面上での明示 opt-in として扱う。
- API の domain error は `AppError` 系から構造化レスポンスに変換する。
- 投資判断系の出力は「売買推奨ではない」ことを明記する。
- UI文言は初心者向けに理由・注意点を併記する。
- 作業履歴は `Documents/99_Work_Log.md` に追記する。

## 6. Repository Layout

```text
backend/
  app/main.py
  core/{config.py,data_contracts.py,errors.py}
  marketdata/{data_access.py,feature_builder.py,provider_*}
  risk/service.py
  portfolio/{service.py,workflow.py}
  screening/service.py
  forecast/{service.py,registry.py}
  scoring/service.py
ui/
  app.py
  rebalance_app.py
tools/
  run_local_checks.py
  run_black_check.py
Documents/
  04_Detail_Design/
```

Planned / deferred modules may appear in documents, but should not be treated as implemented unless code exists.

## 7. Implementation Order From Here

現在の次の自然な順序は以下です。

1. Phase 16 final smoke: ranking 条件、cache/progress、preset resort、cockpit handoff、Rebalance 文言を確認する。
2. Decision Report planning: UIの結果をレポート入力として再利用できる形にする。
3. Research RAG R1-R3: local document ingestion -> chunk store -> keyword retrieval。
4. Research Summary / Research Score: evidence based summary and optional Investment Score input。
5. Optional LLM adapter: deterministic context を作ってから低コストに接続する。
6. Execution / broker sending: 明示的に再開するまでは保留。

## 8. Definition of Done

ドキュメント更新のDoD:

- 実装済み / planned / deferred が明確に分かれている。
- 主要 API / UI / service 名が現在のコードと一致している。
- Codex が最初に読む資料として矛盾が少ない。
- 変更した場合は `99_Work_Log.md` に短く追記する。

実装変更のDoD:

- contract -> service -> API/UI -> test の縦切りが揃っている。
- default path は deterministic / local-first。
- 変更に対応する targeted test がある。
- UIに出る文言は `07_UI_Wording_Policy.md` と矛盾しない。

## 9. Open Questions

| 項目 | 現在の扱い |
|---|---|
| Research RAG の初期検索方式 | keyword search MVP から開始予定 |
| vector store / embedding | R5 以降の拡張 |
| Research Score の Investment Score 統合重み | 未決。まず optional input とする |
| optimizer solver | deferred。現状は `backend/portfolio/service.py` の no-solver のみ |
| broker execution | deferred。現在のSMAIは発注しない |
