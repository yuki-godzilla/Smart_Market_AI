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
- 追加 provider adapter / fund metadata source
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
  - 取得期間、候補数、選択数は銘柄リストの上に1行で表示
  - 銘柄リストは折りたたみ内で確認・変更
- ranking result with ticker / company name / score / warnings
- 選択銘柄をコックピットへ渡す deep-dive flow

注意:

- ranking の候補条件は、provider fetch 前に使える `data/marketdata/symbol_universe.csv` の curated metadata を中心にしています。
- 地域 / 商品は provider fetch 前の候補 universe を絞ります。ランキング目的は Investment Score の表示順の重み付けに使い、候補 universe そのものは絞りません。
- dividend category や theme は現在 curated metadata / source import / opt-in metadata refresh で管理します。live provider 由来の更新は明示 opt-in です。
- ranking universe の将来方針は、SBI証券で取り扱いがあり、現物・NISA・長期投資で検討しやすい商品を初期対象にすることです。詳細は [09_SBI_Symbol_Universe_Policy.md](./09_SBI_Symbol_Universe_Policy.md) を参照してください。
- `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse` は Phase 18 policy columns として `symbol_universe.csv` に保持します。既存候補は local curated / source-import seed であり、SBI取扱確認済み master ではないため、`tradability=unknown` は初期 ranking で通します。
- ranking 候補抽出前に default SBI ranking universe policy を適用します。FX / CFD / 先物 / option / crypto / bond / MMF / commodity、レバレッジ、インバース、`not_tradable`、`is_sbi_supported=false`、`is_active=false` は初期候補から除外します。
- `symbol_universe.csv` は Phase 16/18 UI 用の銘柄候補マスタです。必須列は `symbol`, `name`, `market`, `asset_type`, `currency`, `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, `risk_band` です。
- Phase 18 metadata columns は `metadata_source`, `metadata_as_of`, `metadata_updated_at` です。現在の deterministic baseline では全行 `metadata_source=curated_csv`, `metadata_as_of=2026-05-18`, `metadata_updated_at=2026-05-18T00:00:00+09:00` です。
- Metadata fields are governed by `backend/marketdata/symbol_metadata_schema.py`.
  - `core`: symbol, name, market, asset type, currency, sector/theme, aliases.
  - `ranking_filter`: dividend, PER/PBR/ROE, expense ratio, risk, complexity, quality fields. Source/freshness is tracked before live provider updates are trusted.
  - `fund_extended`: trust fee, AUM, NISA eligibility, installment availability, management style, and distribution policy. These are cataloged for Phase 18 universe expansion but are kept out of `symbol_universe.csv` until a dedicated fund metadata source is added.
- `設定 / データ情報` の `ランキング銘柄候補` では、候補数、metadata 出所、metadata 基準日、形式確認 status を確認できます。CSV の列形式 / 選択値 / 数値 / 重複 ticker / metadata 欠損に問題がある場合は一覧に表示されます。
- 常設パネルで条件を変えると、候補数と「比較する銘柄」の選択候補が同じ画面内で確認できます。

Symbol universe metadata refresh:

- `tools/refresh_symbol_universe_metadata.py` は provider-neutral な metadata refresh command です。
- 現在実装済みの provider は network 非依存の `curated_csv` と、明示 opt-in の `yahoo` です。
- 既定は dry-run で、CSV / manifest は書き換えません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

- Yahoo live metadata は外部通信のため `--provider yahoo --allow-live` を明示した場合だけ実行します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\refresh_symbol_universe_metadata.py --provider yahoo --allow-live --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

- `--write` を付けた場合だけ `symbol_universe.csv` と `data/marketdata/symbol_universe_manifest.json` を更新します。write 前に validation error が残る場合は書き込みを拒否します。
- Yahoo provider は取得できた `sector`, `dividend_yield_pct`, `dividend_category`, `per`, `pbr`, `roe_pct`, `market_cap_tier`, `risk_band`, ETF の `expense_ratio_pct`, and metadata source/as-of/update fields を正規化して返します。失敗銘柄は manifest の `failed_symbols` / `failures` に残します。

Symbol universe source import:

- `tools/import_symbol_universe_source.py` は、JPX などのローカル source CSV を `symbol_universe.csv` 形式へ取り込む command です。
- 既定は dry-run で、`--write` を付けた場合だけ CSV / manifest を更新します。write 前に validation error が残る場合は書き込みを拒否します。
- 初期 source として `data/marketdata/symbol_universe_sources/jpx_etf_seed.csv` と `data/marketdata/symbol_universe_sources/jpx_stock_seed.csv` を置いています。2026-05-18 時点では国内 ETF 8件、国内株 24件を `symbol_universe.csv` に取り込み済みです。
- SBI / 投信向け source profile として `sbi_us_stock`, `sbi_us_etf`, `mutual_fund_seed` を追加しています。各 profile は market / asset_type / currency と SBI policy columns を補完します。
- 追加 seed として `sbi_us_stock_seed.csv`, `sbi_us_etf_seed.csv`, `mutual_fund_seed.csv` を置いています。2026-05-18 時点では、米国株 8件、米国 ETF 7件、投信 4件を `symbol_universe.csv` に取り込み済みです。既存 ETF 3件は SBI ETF profile で更新済みです。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_seed.csv --source-name jpx --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

JPX のように source 側が4桁コードで、SMAI 側では yfinance-compatible な `.T` suffix が必要な場合は、import defaults を指定します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_stock_seed.csv --source-name jpx --default-market jp --default-asset-type stock --default-currency JPY --symbol-suffix .T --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

SBI profile の dry-run 例:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_seed.csv --source-profile sbi_us_etf --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

SBI ranking universe policy:

- 初期対象: 国内株式、米国株式、国内ETF、米国ETF/海外ETF、投資信託、REIT。
- 初期除外: FX、CFD、先物・オプション、暗号資産、債券、外貨建MMF、貴金属、レバレッジ、インバース、非tradable、非SBI対応。
- `symbol_universe.csv` / schema に SBI policy columns を追加済みです。既存127件は conservative default として `broker=sbi_securities`, `tradability=unknown`, `nisa_category=unknown`, `investment_style=unknown`, `is_sbi_supported=true`, `is_active=true`, `is_leveraged=false`, `is_inverse=false` を持ちます。
- `tradability=unknown` は初期 seed として通し、`not_tradable` だけを除外します。SBI / NISA / 投信の公式 source import は後続範囲です。
- SBI証券サイトへのログインや画面スクレイピングは通常 workflow に含めません。SBI / JPX / 投信協会 / NISA 一覧などを手動または curated source CSV に整形し、source import command で local master へ反映します。
- Ranking / Screening は source site を直接参照せず、`symbol_universe.csv` と default policy helper だけを参照します。
- 投信向け metadata として `trust_fee_pct`, `aum`, `nisa_tsumitate_eligible`, `nisa_growth_eligible`, `installment_available`, `management_style`, `distribution_policy` を source CSV から取り込めます。
- 現在の候補マスタは 146件です。内訳は stock 120件、ETF 20件、投信 4件、ADR 2件です。

Phase 16 ranking implementation notes:

- `data/marketdata/symbol_universe.csv` is the ranking candidate master used before provider fetch. It is intentionally curated/local-first and currently carries display/search/filter metadata such as `symbol`, `name`, `market`, `asset_type`, `currency`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, and `risk_band`.
- The Phase 18 schema helper validates required columns, allowed enum values, decimal fields, duplicate tickers, and metadata freshness/source columns without requiring live provider access.
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
