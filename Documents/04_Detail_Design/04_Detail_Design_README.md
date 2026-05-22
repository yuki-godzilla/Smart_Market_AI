# 📄 Detail Design - Smart Market AI

#### [BACK TO README](../../README.md)

## Current Sync Status

この索引は **2026-05-18 時点の実装状態に同期済み**です。

| Area | Document | Status |
|---|---|---|
| 詳細設計方針 | [Detailed Design Policy](./04-1_Detailed_design_policy.md) | synced |
| MarketData / DataAccess | [Marketdata DataAccess](./04-2_Onepager_marketdata_dataaccess.md) | implemented / synced |
| Execution | [Execution](./04-3_Onepager_Execution.md) | deferred design note |
| Risk | [Risk](./04-4_Onepager_Risk.md) | implemented / synced |
| Feature Builder | [Feature Builder](./04-5_Onepager_Feature_Builder.md) | implemented / synced |
| Portfolio | [Portfolio](./04-6_Onepager_Portfolio.md) | implemented / synced |
| Implementation class diagram | [Implementation Class Diagram](./04-7_Implementation_Class_Diagram.md) | mostly synced; diagram reference |
| Research RAG | [Research RAG](./04-8_Onepager_Research_RAG.md) | designed / planned |
| Investment Scoring UI | [Investment Scoring UI](./04-9_Onepager_Investment_Scoring_UI.md) | implemented; final smoke recommended |

## 読み方

- 実装判断は `README.md`、`PROJECT_CONTEXT.md`、この索引、各One-Pagerの `Current Sync Status` を優先する。
- `Execution` と `Research RAG` は設計メモを含むが、現在の通常導線では未実装として扱う。
- `Portfolio` は no-solver が正。optimizer solver は future scope。
- RAG実装に入る場合は `04-8` と `05_Implementation_Roadmap.md` の Phase R1 以降を使う。
