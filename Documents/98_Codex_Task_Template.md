# 98_Codex_Task_Template

#### [BACK TO README](../README.md)

## 目的

Codex に実装・修正・調査を依頼するときのテンプレートです。
2026-05-18 時点では、SMAI は Phase 16 まで概ね実装済み、Research RAG と Decision Report は planned、Execution は deferred です。

毎回の説明量を減らしつつ、実装品質、検証、初心者向け説明を落とさないために使います。
必要な項目だけ残してください。

---

## Template

### Task

- 何を実装・修正・調査するか:
- 期待するユーザー視点の変化:
- 対象フェーズ:
  - Phase 16 final UI smoke / Decision Report preparation / Research RAG R1-R3 / bugfix / docs-only など

### Current Assumption

- 現在実装済みとして扱うもの:
- planned として扱うもの:
- deferred として扱うもの:

例:

```text
Investment Score, Screening, Forecast, Risk, Portfolio, mock/csv MarketData は実装済みとして扱う。
Research RAG は planned。Execution / broker order sending は deferred。
```

### Scope

- 対象範囲:
- 触ってよいファイル・モジュール:
- 対象外にする範囲:

### Do Not

- 実施しないこと:
- 変更してはいけない前提:
- 今回は後回しにすること:

よく使う制約:

```text
- brokerへの実注文送信は実装しない。
- 通常テストで外部ネットワークに依存しない。
- 投資出力を売買推奨として表現しない。
- 大規模リファクタより、小さな縦切りを優先する。
```

### Reference

- まず読む資料:
  - `AGENTS.md`
  - `PROJECT_CONTEXT.md`
  - `Documents/05_Implementation_Roadmap.md`
- 関連する詳細設計:
  - MarketData: `Documents/04_Detail_Design/04-2_Onepager_marketdata_dataaccess.md`
  - Risk: `Documents/04_Detail_Design/04-4_Onepager_Risk.md`
  - FeatureBuilder: `Documents/04_Detail_Design/04-5_Onepager_Feature_Builder.md`
  - Portfolio: `Documents/04_Detail_Design/04-6_Onepager_Portfolio.md`
  - Research RAG: `Documents/04_Detail_Design/04-8_Onepager_Research_RAG.md`
  - Investment Score UI: `Documents/04_Detail_Design/04-9_Onepager_Investment_Scoring_UI.md`
- 関連するコード:
- 関連するテスト:

### Acceptance Criteria

- 完了条件:
- UI で確認できる変化:
- API や出力で確認できる変化:
- ドキュメント更新条件:
- 投資判断補助としての注意書きが保たれていること:

### Verification

- 実行する確認コマンド:
- 手動確認の観点:
- 実行しなくてよい確認:
- 実行できなかった場合の扱い:

例:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_scoring_service.py tests/test_scoring_api.py -q
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

Black は直接 `python -m black --check .` ではなく、原則 `tools/run_black_check.py` または `tools/run_local_checks.py` を使う。

### Expected Files To Change

- 変更が想定されるファイル:
- 新規作成が想定されるファイル:
- 変更しない予定のファイル:

### Handoff Format

作業完了時は以下を出力すること。

- changed files
- what changed and why
- commands run and results
- commands not run and why
- remaining risks / TODOs
- suggested commit message

### Notes For Beginner-Friendly Explanation

- 初学者向けに説明してほしい用語:
- 使い方として説明してほしい操作:
- 注意点として明記してほしいこと:
- 提案してほしい commit message の粒度:
