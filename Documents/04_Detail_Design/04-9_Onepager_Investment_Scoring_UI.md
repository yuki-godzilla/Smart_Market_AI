# 04-9_Onepager_Investment_Scoring_UI

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

## 0) Maturity Review Note / 2026-05-24

Investment Score UI は売買判断そのものではなく、複数観点を統合した比較・分析用スコアとして扱います。

Score hierarchy:

- `Investment Score`: Screening、Direction Signal、Forecast agreement 互換、Risk signal、Data Quality などを統合した比較・分析用スコア。
- `Screening Score`: Feature Snapshot 由来の候補評価。Investment Score の構成要素のひとつ。
- `Direction Signal`: 上昇気配、下降警戒、モデル方向一致、予測変化率、直近トレンドを整理した深掘り用シグナル。売買推奨ではない。
- `Forecast agreement`: baseline forecast model 間の見方の近さ。ランキング主役ではなく補助指標で、将来価格の保証ではない。
- `Risk signal`: 価格変動や制約違反の確認材料。安全保証ではない。
- `Data Quality`: 評価に使った market data / feature の充実度。
- `Database Fit`: 選択した ranking profile に対して、local symbol master の登録情報がどの程度使えるかを示す補助指標。
- `Metadata Confidence`: metadata source、freshness、coverage に基づく補助指標。投資魅力度ではない。
- `Research Evidence`: 資料根拠の補足レイヤー。Phase 20 local evidence slice では score の絶対的な正しさを保証しない。

仕様や文言に迷う場合は、実装修正前に [../96_Manual_UX_Review_Checklist.md](../96_Manual_UX_Review_Checklist.md) と [../97_Functional_Spec_Issues.md](../97_Functional_Spec_Issues.md) を確認します。

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
- `upside_signal_score`
- `downside_signal_score`
- `forecast_return_pct`
- `model_upside_strength_score`
- `model_downside_strength_score`
- `data_quality_score`
- `risk_signal_score`
- `breakdown`
- `warnings`
- `reasons`
- `decision_support_note`

UI note:

- Ranking and Symbol Cockpit use `upside_signal_score` / `downside_signal_score` as the main direction-support indicators.
- Older direction net / label fields may remain in backend contracts for compatibility, but they are not introduced as new public UI indicators.

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
| direction_signal | 上昇気配、下降警戒、モデル別の予測リターン強度、予測変化率、直近トレンドを整理する。上昇気配と下降警戒の差分をランキング用方向シグナルとして扱う |
| forecast_agreement | 複数 forecast model の見方が近いか。互換と補助表示用。方向シグナルでは加点ではなく中立寄せの信頼度調整として扱う |
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
  - direction signal / upside signal / downside warning
  - forecast agreement compatibility
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
- provider fundamentals 由来の配当利回り・sector・ETF属性は、既存の opt-in metadata refresh / source import 経路で更新する。次 slice では SBI ranking-universe policy を candidate extraction に接続する。
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

## 8) 上向き兆候と本気分析モード

上向き兆候は、下落・調整・横ばいから上向きに変わる兆しを整理する独立探索軸であり、旧UI名は「反転期待」である。買い推奨ではなく深掘り優先度として扱う。

主要軸は `AI総合 / 上昇気配 / 上向き兆候 / 下降警戒`。上向き兆候モードとCockpitカードでは、スコア、形状ラベル、調整・安定度、押し目深度、上向き余地、下落安全性、下降警戒、配当罠警戒、理由、予測信頼度、モデル見解のばらつきを表示する。

ランキング作成付近に初期値OFFの `本気分析モード（AI材料分析つき）` を置く。ON時だけ通常ランキング後の上位候補にニュース・開示・IRのAI材料分析を行う。初期段階は参考バッジとし、順位反映は性能試験後、上位候補内、制限幅付きに限る。

「上向き兆候が高い = 買い」「底打ち確定」「反転確定」「買い時」と表示しない。予測信頼度が低い、またはモデル不一致が大きい場合は過信を抑える。
