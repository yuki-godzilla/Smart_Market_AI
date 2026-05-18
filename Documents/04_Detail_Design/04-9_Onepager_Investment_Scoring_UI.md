# 04-9_Onepager_Investment_Scoring_UI

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

## 1) Purpose & Scope

この文書は、現在実装済みの Investment Score と、Phase 16 で実装済みの Streamlit scoring UI を整理する Onepager です。
最終 Streamlit browser smoke は推奨確認として残します。

対象:

- `backend/scoring`
- `POST /scoring/investment-score`
- left side menu
- `銘柄コックピット`
- `銘柄ランキング`
- `リバランス` / `Rebalance Cockpit`
- `設定 / データ情報`

対象外:

- Research Score 統合
- LLM / AI assistant
- broker order execution
- PDF / Excel report

## 2) Public Interfaces

### API

```text
POST /scoring/investment-score
```

Input:

- `symbols: list[str]`
- `as_of: date`
- `horizon_days: int`

Output:

- `rank`
- `symbol`
- `total_score`
- `score_band`
- `screening_score`
- `forecast_agreement`
- `forecast_agreement_score`
- `data_quality_score`
- `risk_signal_score`
- `breakdown`
- `warnings`
- `reasons`
- `decision_support_note`

### Service

```python
InvestmentScoringService.score(
    screening_scores,
    forecast_consensus_by_symbol=None,
) -> list[InvestmentScore]
```

## 3) Scoring Components

Investment Score は `ScreeningScore` を直接置き換えず、別 contract として扱います。

現在の構成:

| component | 役割 |
| --- | --- |
| screening | Feature Snapshot 由来の総合 screening score |
| forecast_agreement | 複数 forecast model の見方が近いか |
| data_quality | 欠損・履歴不足・provider data quality |
| risk_signal | 現時点では Screening risk score を初期 risk signal として利用 |

重みは `scoring.weights` で設定します。
weight total は config validation で確認します。

## 4) UI Mapping

### 銘柄コックピット

目的: 1 銘柄を深掘りする。

表示順:

1. provider / symbol / company name / period
2. 価格・予測チャート
3. forecast summary
4. Investment Score
5. warnings / reasons
6. score breakdown chart
7. Forecast Metrics / Screening Score / provider details
8. JSON / CSV download

### Side Menu

目的: 画面選択と実行環境の確認だけに絞る。

- `銘柄コックピット`
- `銘柄ランキング`
- `リバランス`
- `設定 / データ情報`
- Runtime は expander に畳む

### 銘柄ランキング

目的: 複数銘柄を比較し、深掘り候補を整理する。

現在の実装:

- provider selection
- ranking preset
  - balanced
  - forecast agreement
  - data quality
  - lower risk
- in-page screening condition panel and candidate filter controls
- static / curated metadata による fetch-before filtering
- ticker / company name 表示
- selected ranking symbol を cockpit state へ渡す flow
- ranking cache / progress display

### Rebalance Cockpit

目的: 候補を保有に入れた場合の配分と risk を確認する。

現在の実装:

- JSON input を advanced input に移動
- sample / account / as-of / cash input を Rebalance 画面内に配置
- summary flow
- target allocation percentage input
- allocation comparison chart
- risk breach confirmation points
- latest result persistence in Streamlit session state

## 5) Rules & Constraints

- Investment Score は売買推奨ではない。
- `decision_support_note` を出力に含める。
- Ranking は「買う銘柄の確定」ではなく「深掘り候補の整理」として表示する。
- Fetch-before filters は provider fetch 前に判断できる static / curated metadata だけを使う。
- provider fundamentals 由来の配当利回り・sector・ETF属性は、将来の metadata refresh command で更新する。
- Research Score は optional input として後続統合する。

## 6) Test Plan

Backend:

- `tests/test_scoring_service.py`
- `tests/test_scoring_api.py`
- `tests/test_screening_service.py`
- `tests/test_forecast_service.py`

UI helper:

- `tests/test_ui_forecast_display.py`
- `tests/test_ui_rebalance_app.py`

Verification:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy backend
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

## 7) Open Questions

- Research Score を Investment Score に統合する場合の default weight。
- ranking result と cockpit summary を Decision Report へ渡す最小 schema。
- symbol metadata refresh の更新頻度と review flow。
- beginner-friendly UI と detailed analyst view の切り替え方。
