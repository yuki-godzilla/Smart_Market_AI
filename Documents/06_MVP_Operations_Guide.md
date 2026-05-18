# MVP Operations Guide

#### [BACK TO README](../README.md)

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
- deterministic な `mock` / `csv` MarketData provider
- 明示 opt-in の `yahoo` live provider adapter 経路
- Feature Snapshot / Screening Score / Forecast Evaluation / Investment Score
- Portfolio-to-Risk rebalance-check workflow
- Streamlit UI
  - Market Data: `銘柄コックピット` / `銘柄ランキング`
  - Rebalance: summary flow / allocation comparison / risk confirmation
- JSON / CSV / Markdown / manifest / ZIP export
- file-backed rebalance scenarios

未実装:

- `polygon` などの追加 live provider adapter 本体
- provider fundamentals からの symbol metadata refresh
- Research RAG / IR資料検索 / Research Score
- Decision Report の本格 workflow
- broker への live order 送信
- Execution workflow
- PDF / Excel export

現在の MVP は、ローカル検証と説明用です。
外部 API へ接続する場合は明示 opt-in が必要で、broker や execution provider へ注文を送りません。

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
| `POST /portfolio/rebalance-check` | 現在 portfolio と target allocation から売買案を作り Risk check へ接続 |
| `POST /screening/score` | Feature Snapshot から Screening Score / ranking / reason を返す |
| `POST /forecast/evaluate` | OHLCV から baseline forecast と walk-forward metrics を返す |
| `POST /scoring/investment-score` | Screening / Forecast agreement / Data quality / Risk signal を統合した Investment Score を返す |

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
- `warnings`
- `reasons`
- `decision_support_note`

## 5. CSV MarketData provider

設定上の既定 provider は deterministic な `mock` です。
Streamlit の Market Data 画面では provider 選択の初期表示と表示順先頭が `yahoo` です。通常の API / local checks は `mock` / `csv` を基準にしつつ、UI では生きた株価データを主導線として扱います。
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

### Side menu

Streamlit UI は左サイドメニューで画面を切り替えます。
サイドメニューは画面選択と実行環境の簡易表示だけにし、各 workflow の入力はそれぞれの画面内に置きます。

| screen | 役割 |
| --- | --- |
| `銘柄コックピット` | 1 銘柄の価格、予測、Investment Score、注意点を深掘りする |
| `銘柄ランキング` | 複数銘柄を条件で絞り、Investment Score で比較する |
| `リバランス` | 現在資産、目標配分、必要な売買、Risk 判定を確認する |
| `設定 / データ情報` | Runtime、config、scenario directory、銘柄候補を確認する |

### 銘柄コックピット

確認できるもの:

- provider / symbol / company name / period
- collapsed sample symbol reference
- 価格・予測チャート
- forecast agreement、forecast spread、best RMSE model
- Investment Score summary
- score breakdown chart
- warnings / reasons
- Forecast metrics / Screening Score / provider detail
- JSON / CSV downloads

### 銘柄ランキング

確認できるもの:

- provider
- 地域 / 商品 / ランキング目的
  - 地域: `国内` / `米国` / `その他海外` / `全体`
  - 商品: `株式` / `ETF` / `投信` / `全体`
  - ランキング目的: `総合評価` / `短期上昇期待` / `中長期成長` / `高配当` / `割安` / `低リスク` / `低コスト`
- ランキング目的に応じた表示順
  - 総合評価 / 高配当 / 割安: バランス重視
  - 短期上昇期待 / 中長期成長: 予測一致重視
  - 低リスク: リスク控えめ
  - 低コスト: データ品質重視
- 基本条件
  - period preset
  - currency
  - dividend category
  - minimum dividend yield
  - market-cap tier
  - ETF index family
  - max expense ratio
  - theme
  - keyword
- 常設の詳細条件パネル
  - `属性条件` / `数値条件` / `キーワード検索` に分けて表示
  - 地域 × 商品に応じて、現在の銘柄マスタで判定できる詳細条件だけを表示
  - 株式: 業種/テーマ、時価総額、配当利回り、PER、PBR、ROE、リスク
  - ETF: 連動指数、信託報酬/経費率、分配金利回り、複雑さ
  - 投信: 条件定義は追加済み。現在の銘柄マスタに候補がないため future metadata 扱い
  - 条件のクリア
  - 条件変更後の候補数表示
- 比較する銘柄
  - 初期状態では候補をすべて選択
  - 銘柄リストは折りたたみ内で確認・変更
- ranking result with ticker / company name / score / warnings
- 選択銘柄をコックピットへ渡す deep-dive flow

注意:

- ranking の候補条件は、provider fetch 前に使える `data/marketdata/symbol_universe.csv` の curated metadata を中心にしています。
- 地域 / 商品は provider fetch 前の候補 universe を絞ります。ランキング目的は Investment Score の表示順の重み付けに使い、候補 universe そのものは絞りません。
- dividend category や theme は現在 curated metadata です。provider fundamentals からの自動更新は将来拡張です。
- `symbol_universe.csv` は Phase 16 UI 用の銘柄候補マスタです。列は `symbol`, `name`, `market`, `asset_type`, `currency`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, `risk_band` です。
- 常設パネルで条件を変えると、候補数と「比較する銘柄」の選択候補が同じ画面内で確認できます。

Phase 16 ranking implementation notes:

- `data/marketdata/symbol_universe.csv` is the ranking candidate master used before provider fetch. It is intentionally curated/local-first and currently carries display/search/filter metadata such as `symbol`, `name`, `market`, `asset_type`, `currency`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, and `risk_band`.
- The in-page screening condition panel filters comparison candidates by metadata and metric ranges. `取得期間` and `重視条件` are not screening filters; they control ranking calculation and display ordering.
- Ranking build uses a fast batch path first: it fetches OHLCV in chunks, builds feature snapshots from already-fetched market data, then reuses existing Screening / Investment Score services. If the batch path fails with a provider/domain error, local/deterministic providers can fall back to the existing per-symbol preview path; live Yahoo failures are reported once without retrying every symbol to avoid repeated network failures.
- Yahoo OHLCV uses the same non-threaded yfinance download path for single-symbol cockpit and multi-symbol ranking requests. The cockpit reuses one fetched OHLCV range for quote display and feature construction instead of fetching the same symbol again. Yahoo cockpit fetch prioritizes price data: initial fetch skips live FX and fundamentals so price / forecast / score rows can render without waiting on nonessential live requests. SMAI shares one curl_cffi-backed yfinance session across `Search`, `download`, and `Ticker` calls so Yahoo cookie / crumb state stays attached to the same session. If yfinance returns an empty batch response, the provider retries once after a short delay to absorb first-call warm-up / transient empty responses. Because live Yahoo requests are network-dependent and can be slow or noisy, Streamlit ranking warns when selected symbols exceed 30, uses smaller non-threaded download chunks, and suppresses yfinance's raw console noise in favor of structured UI error rows.
- Ranking rows are cached in Streamlit session state by `provider + symbols + start + end`. Re-running the same request or changing only the ranking weight preset reuses fetched rows and only re-sorts the display.
- The ranking progress indicator reports batch fetch, feature construction, forecast agreement calculation, and final sorting so large candidate sets do not look frozen.
- Ranking remains decision support only. Use `深掘りする銘柄` to move one selected symbol into `銘柄コックピット` for detailed price / forecast / score-reason review.

Phase 16 final UI smoke checklist:

- Change screening conditions and confirm candidate count / comparison symbols update coherently.
- Build a ranking and confirm progress messages are shown.
- Run the same ranking again and confirm cached rows are reused.
- Change only `重視条件` and confirm rows are re-sorted without a provider refetch.
- Open a selected symbol in `銘柄コックピット` and confirm provider / symbol handoff.
- Confirm Rebalance labels continue to describe decision support rather than buy/sell advice.

### リバランス

Rebalance は `Rebalance Cockpit` として、次の順に確認します。

1. 現在資産
2. 目標配分
3. 必要な売買
4. Risk 判定

確認できるもの:

- sample / account / as-of / cash / target weight input
- summary flow
- target allocation percentage input
- current positions
- target allocations
- allocation comparison chart
- proposed trades
- risk decision
- beginner-friendly risk breach confirmation points
- JSON / CSV / Markdown / ZIP export

## 7. 外部 MarketData provider

現在使える provider:

| provider | 状態 | opt-in | 主な用途 |
| --- | --- | --- | --- |
| `mock` | 実装済み | 不要 | 既定の MVP 確認 |
| `csv` | 実装済み | 不要 | ローカル CSV 確認 |
| `yahoo` | 実装済み経路あり | 必要 | yfinance による live data 確認 |
| `polygon` | metadata のみ | 将来必要 | live provider 候補 |

`yahoo` を使う場合は、設定で `allow_external_providers: true` を明示します。
通常の自動テストと local checks は外部 API に依存させません。

## 8. ローカル検証

まとめて確認:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_local_checks.py
```

個別確認:

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend ui tests --no-cache
.\venv_SMAI\Scripts\python.exe -m mypy backend
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

Markdown UTF-8 check:

```powershell
.\venv_SMAI\Scripts\python.exe -c "from pathlib import Path; [p.read_text(encoding='utf-8') for p in Path('.').rglob('*.md') if '.git' not in p.parts]; print('markdown utf-8 ok')"
```

## 9. 更新ルール

- 実装状態が変わったら README / PROJECT_CONTEXT / Roadmap / Operations Guide を同期する。
- UI に見える変更は `07_UI_Wording_Policy.md` と `08_Phase16_UI_Improvement_Plan.md` も確認する。
- 作業履歴は `Documents/99_Work_Log.md` の先頭へ追加する。
- Research RAG は現時点では planned として扱い、実装済み前提にしない。
