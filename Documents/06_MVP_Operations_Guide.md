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
- 地域 / 商品 / 重視して並べ替え
  - 地域: `国内` / `米国` / `全体`
  - 商品: `株式` / `ETF`
  - 重視して並べ替え: `配当重視` / `成長重視` / `割安重視` / `安定重視` / `トレンド重視`
- `重視して並べ替え` に応じた表示順
  - 配当重視 / 割安重視: バランス重視
  - 成長重視 / トレンド重視: 予測一致重視
  - 安定重視: リスク控えめ
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
  - 株式: 業種/テーマ、時価総額、配当利回り、PER、PBR、ROE、NISA
  - ETF: 連動指数、信託報酬/経費率、分配金利回り、複雑さ
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
- 地域 / 商品 / 詳細条件は provider fetch 前の候補 universe を絞ります。`重視して並べ替え` は Investment Score の表示順の重み付けに使い、候補 universe そのものは絞りません。
- Risk / 値動きの大きさは取得期間の価格データを見た後の確認材料です。詳細条件では絞らず、ranking result / score breakdown 側で確認します。
- 投資信託は MVP のランキング / スクリーニング / チャート対象外です。source seed や metadata schema は将来対応として残しますが、default ranking universe と UI の主要導線には出しません。
- dividend category や theme は現在 curated metadata / source import / opt-in metadata refresh で管理します。live provider 由来の更新は明示 opt-in です。
- 株式の `業種/テーマ` は `theme`, `sector`, `tags` を見ます。JPX 東証上場銘柄一覧の `規模区分` は `market_cap_tier` へ変換し、`時価総額` 条件で使います。
- ranking universe の MVP 方針は、SBI証券で取り扱いがあり、現物・NISA・長期投資で検討しやすい株式・ETFを初期対象にすることです。詳細は [09_SBI_Symbol_Universe_Policy.md](./09_SBI_Symbol_Universe_Policy.md) を参照してください。
- `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse` は Phase 18 policy columns として `symbol_universe.csv` に保持します。既存候補は local curated / source-import seed であり、SBI取扱確認済み master ではないため、`tradability=unknown` は初期 ranking で通します。
- ranking 候補抽出前に default SBI ranking universe policy を適用します。MVP の対象は `stock` / `etf` です。`mutual_fund` / `fund` / `investment_trust` / `adr` / `reit` / FX / CFD / 先物 / option / crypto / bond / MMF / commodity、レバレッジ、インバース、`not_tradable`、`is_sbi_supported=false`、`is_active=false` は初期候補から除外します。
- `symbol_universe.csv` は Phase 16/18 UI 用の銘柄候補マスタです。必須列は `symbol`, `name`, `market`, `asset_type`, `currency`, `broker`, `tradability`, `nisa_category`, `investment_style`, `is_sbi_supported`, `is_active`, `is_leveraged`, `is_inverse`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, `risk_band` です。
- Phase 18 metadata columns は `metadata_source`, `metadata_as_of`, `metadata_updated_at` です。現在の master は `curated_csv`, `jpx`, `sbi_us_stock`, `sbi_us_etf`, `mutual_fund_seed` などの source を行ごとに保持します。
- Metadata fields are governed by `backend/marketdata/symbol_metadata_schema.py`.
  - `core`: symbol, name, market, asset type, currency, sector/theme, aliases.
  - `ranking_filter`: dividend, PER/PBR/ROE, expense ratio, risk, complexity, quality fields. Source/freshness is tracked before live provider updates are trusted.
- `fund_extended`: trust fee, AUM, NISA eligibility, installment availability, management style, and distribution policy. Mutual-fund seed/source import rows can store these fields in `symbol_universe.csv`, but these fields are future extension metadata and are not MVP ranking filters.
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

- `tools/build_symbol_universe_source.py` は、公式 raw file を SMAI 用 source CSV へ変換する command です。現在は JPX の東証上場銘柄一覧から国内株 source を作る `--source-kind jpx_listed_stock`、JPX 国内 ETF / ETN source を作る `--source-kind jpx_etf`、SBI米国株 / 米国ETF・海外ETF のローカル raw CSV から source を作る `--source-kind sbi_us_stock` / `sbi_us_etf`、NISA制度 metadata 更新 source を作る `--source-kind nisa_eligibility` に対応しています。raw file は CSV と Excel (`.xls` / `.xlsx`) を扱えます。PDF は通常 import 対象外です。既定は dry-run で、`--write` を付けた場合だけ source CSV / manifest を書き込みます。
- `tools/import_symbol_universe_source.py` は、JPX などのローカル source CSV を `symbol_universe.csv` 形式へ取り込む command です。
- 既定は dry-run で、`--write` を付けた場合だけ CSV / manifest を更新します。write 前に validation error が残る場合は書き込みを拒否します。
- 初期 source として `data/marketdata/symbol_universe_sources/jpx_etf_seed.csv` と `data/marketdata/symbol_universe_sources/jpx_stock_seed.csv` を置いています。2026-05-20 時点では JPX 東証上場銘柄一覧から国内株 3,645件を追加し、JPX seed と合わせて `symbol_universe.csv` に取り込み済みです。2026-05-21 時点では JPX NISA 成長投資枠 ETF/ETN Excel から 27件の ETF/ETN metadata を取り込み済みです。
- MVP 向け source profile として `jpx_listed_stock`, `jpx_stock`, `jpx_etf`, `sbi_us_stock`, `sbi_us_etf`, `nisa_eligibility`, `ranking_metadata` を使えます。`mutual_fund_seed` は将来対応用 profile として残します。
- 追加 seed として `sbi_us_stock_seed.csv`, `sbi_us_etf_seed.csv`, `mutual_fund_seed.csv` を置いています。2026-05-19 時点では、SBI US stock source 28件、SBI US ETF source 22件、投信 4件を `symbol_universe.csv` に取り込み済みです。投信 4件は default ranking universe から除外されます。
- `nisa_eligibility_seed.csv` は既存の株式・ETF 31件へ NISA metadata を付与する local seed です。2026-05-19 時点で `symbol_universe.csv` に反映済みです。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_seed.csv --source-profile jpx_etf --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

JPX 東証上場銘柄一覧を使う場合は、先に公式 Excel (`.xls` / `.xlsx`) / CSV を `data/marketdata/raw/` などに保存し、SMAI 用 source CSV に変換します。ETF / ETN / REIT はこの builder では除外し、国内株だけを `jpx_listed_stock` source として作ります。JPX の `規模区分` は `TOPIX Core30 -> mega`, `TOPIX Large70 -> large`, `TOPIX Mid400 -> mid`, `TOPIX Small 1/2 -> small` として `market_cap_tier` に変換します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_listed_stock --raw-file .\data\marketdata\raw\jpx_listed_stock_20260520.xls --output-csv .\data\marketdata\symbol_universe_sources\jpx_listed_stock_20260520.csv --as-of 2026-05-20 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_listed_stock_20260520.csv --source-profile jpx_listed_stock --as-of 2026-05-20 --updated-at 2026-05-20T00:00:00+09:00 --write
```

JPX 国内 ETF / ETN を使う場合は、同じ raw file または JPX ETF raw file を `jpx_etf` source として変換します。builder は `.T` 付き symbol、指数 family、信託報酬、商品系 theme、ETN / レバレッジ / インバース判定を保持します。商品系ETF、レバレッジ、インバースは ranking universe policy 側で除外できます。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_etf --raw-file .\data\marketdata\raw\jpx_etf_2026-05.xlsx --output-csv .\data\marketdata\symbol_universe_sources\jpx_etf_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_2026-05.csv --source-profile jpx_etf --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
```

JPX の「NISA 成長投資枠対象銘柄一覧」のように、列名にふりがなが含まれる Excel も `jpx_etf` / `nisa_eligibility` source として扱えます。銘柄本体を追加してから制度 metadata を更新します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind jpx_etf --raw-file .\data\marketdata\raw\jpx_etf_20260521_NISA.xlsx --output-csv .\data\marketdata\symbol_universe_sources\jpx_etf_nisa_growth_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_etf_nisa_growth_20260521.csv --source-profile jpx_etf --source-name jpx_nisa_growth --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind nisa_eligibility --raw-file .\data\marketdata\raw\jpx_etf_20260521_NISA.xlsx --output-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_jpx_etf_20260521.csv --as-of 2026-05-21 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_jpx_etf_20260521.csv --source-profile nisa_eligibility --source-name jpx_nisa_growth --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --update-existing --write
```

SBI米国株 / 米国ETF・海外ETF の取扱一覧を使う場合も、まずローカル raw CSV / Excel を source CSV に変換します。`sbi_us_etf` builder は、名称や明示フラグからレバレッジ / インバース ETF を判定し、後段の ranking universe policy で除外できるように `is_leveraged` / `is_inverse` を保持します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_stock --raw-file .\data\marketdata\raw\sbi_us_stock_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind sbi_us_etf --raw-file .\data\marketdata\raw\sbi_us_etf_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_stock_2026-05.csv --source-profile sbi_us_stock --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_2026-05.csv --source-profile sbi_us_etf --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --write
```

JPX のように source 側が4桁コードで、SMAI 側では yfinance-compatible な `.T` suffix が必要な場合は、`jpx_stock` profile を使います。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\jpx_stock_seed.csv --source-profile jpx_stock --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

SBI profile の dry-run 例:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\sbi_us_etf_seed.csv --source-profile sbi_us_etf --as-of 2026-05-18 --updated-at 2026-05-18T00:00:00+09:00
```

NISA eligibility のように既存銘柄の制度 metadata だけを更新する場合は `--source-profile nisa_eligibility --update-existing` を使います。この profile は `nisa_category`, `nisa_growth_eligible`, `nisa_tsumitate_eligible`, metadata source/as-of/update fields だけを更新し、既存の市場や商品分類は上書きしません。公式または確認済み raw file から source CSV を作る場合は、先に `--source-kind nisa_eligibility` で 4桁国内コードを `.T` 付き symbol に変換し、成長投資枠 / つみたて投資枠 / 対象外を canonical fields に正規化します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\build_symbol_universe_source.py --source-kind nisa_eligibility --raw-file .\data\marketdata\raw\nisa_eligibility_2026-05.csv --output-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_2026-05.csv --as-of 2026-05-19 --write
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\nisa_eligibility_2026-05.csv --source-profile nisa_eligibility --as-of 2026-05-19 --updated-at 2026-05-19T00:00:00+09:00 --update-existing
```

Ranking metadata のように既存銘柄の条件列だけを更新する場合は `--source-profile ranking_metadata --update-existing` を使います。テンプレートは `data/marketdata/symbol_universe_sources/ranking_metadata_template.csv` です。この profile は `PER`, `PBR`, `ROE`, `配当利回り`, `時価総額`, `リスク`, ETF の `信託報酬/経費率` など ranking filter 用 metadata だけを更新し、名称・市場・商品分類は上書きしません。source CSV には `per` / `pe_ratio`, `pbr` / `price_to_book`, `roe_pct` / `roe`, `dividend_yield_pct` / `dividend_yield` などの列名を使えます。未確認値は空欄のままにし、推定値で埋めません。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\import_symbol_universe_source.py --source-csv .\data\marketdata\symbol_universe_sources\ranking_metadata_2026-05.csv --source-profile ranking_metadata --as-of 2026-05-21 --updated-at 2026-05-21T00:00:00+09:00 --update-existing --write
```

Ranking metadata coverage:

- `tools/check_symbol_universe_metadata_coverage.py` は、`symbol_universe.csv` の ranking filter 用 metadata がどの程度埋まっているかを network なしで集計します。
- 2026-05-21 時点の出力は `data/marketdata/symbol_universe_metadata_coverage.json` です。現状、JPX listed-stock 追加分は `market_cap_tier` が 1,550 / 3,645件、`PER` / `PBR` / `ROE` / `配当利回り` は 0 / 3,645件です。これらは JPX 上場銘柄一覧に含まれないため、公式・確認済み source CSV または明示 opt-in の metadata refresh で追加します。

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_metadata_coverage.py --checked-at 2026-05-21T00:00:00+09:00 --write
```

SBI ranking universe policy:

- MVP対象: 国内株式、米国株式、国内ETF、米国ETF/海外ETF。
- 初期除外: 投資信託、ADR、REIT、FX、CFD、先物・オプション、暗号資産、債券、外貨建MMF、貴金属・コモディティ系ETF、レバレッジ、インバース、非tradable、非SBI対応。
- `symbol_universe.csv` / schema に SBI policy columns を追加済みです。local curated / source-import seed は conservative default として `broker=sbi_securities`, `tradability=unknown`, `nisa_category=unknown`, `investment_style=unknown`, `is_sbi_supported=true`, `is_active=true`, `is_leveraged=false`, `is_inverse=false` を持てます。
- `tradability=unknown` は stock / ETF の初期 seed として通し、`not_tradable` だけを除外します。NISA seed import はありますが、公式 source の継続更新は後続範囲です。投信公式 source import は Future Phase です。
- SBI証券サイトへのログインや画面スクレイピングは通常 workflow に含めません。SBI / JPX / NISA 一覧などを手動または curated source CSV に整形し、source import command で local master へ反映します。投信協会 / 投信CSV / 基準価額は Future Phase で扱います。
- Ranking / Screening は source site を直接参照せず、`symbol_universe.csv` と default policy helper だけを参照します。
- 投信向け metadata として `trust_fee_pct`, `aum`, `nisa_tsumitate_eligible`, `nisa_growth_eligible`, `installment_available`, `management_style`, `distribution_policy` を source CSV から取り込めます。ただし MVP ではランキング対象外です。
- 現在の候補マスタは 3,898件です。内訳は stock 3,817件、ETF 75件、投信 4件、ADR 2件です。default ranking universe では stock / ETF のみを対象にします。

Yahoo coverage check:

- `tools/check_symbol_universe_yahoo_coverage.py` は、`symbol_universe.csv` の対象行について Yahoo OHLCV（日足価格）を取得できるか確認する live smoke command です。外部通信を使うため、通常の local checks / CI には含めません。
- JPX 東証上場銘柄一覧から追加した国内株の確認例:

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --metadata-source jpx_listed_stock --asset-type stock --market jp --sample-size 30 --batch-size 10 --timeout-ms 15000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_jpx_listed_stock_sample30_20260520
.\venv_SMAI\Scripts\python.exe .\tools\check_symbol_universe_yahoo_coverage.py --metadata-source jpx_listed_stock --asset-type stock --market jp --batch-size 25 --timeout-ms 20000 --start 2026-05-12 --end 2026-05-20 --label yahoo_coverage_jpx_listed_stock_full_20260520
```

- 2026-05-21 に実行した JPX 追加国内株の Yahoo coverage check では、サンプル 30件は 30/30 件成功。全数 3,645件は 3,641件成功、4件は短期期間で `YAHOO-NO-BARS` でした。失敗4件の個別再試行では、`9237.T` は同じ短期期間で取得成功し、`2344.T` / `4530.T` / `6565.T` は 2026-04-01 からの長め期間では取得できるものの、2026-05-12 〜 2026-05-20 ではバーがありませんでした。
- 結果は `data/marketdata/live_checks/` に JSON / CSV で保存します。

Phase 16 ranking implementation notes:

- `data/marketdata/symbol_universe.csv` is the ranking candidate master used before provider fetch. It is intentionally curated/local-first and currently carries display/search/filter metadata such as `symbol`, `name`, `market`, `asset_type`, `currency`, `theme`, `dividend_category`, `dividend_yield_pct`, `market_cap_tier`, `index_family`, `expense_ratio_pct`, `complexity`, `tags`, `aliases`, `per`, `pbr`, `roe_pct`, `sector`, `consensus_rating`, `forecast_agreement`, `data_quality`, and `risk_band`.
- The Phase 18 schema helper validates required columns, allowed enum values, decimal fields, duplicate tickers, and metadata freshness/source columns without requiring live provider access.
- The in-page screening condition panel filters comparison candidates by metadata, NISA eligibility, and metric ranges. `取得期間` and `重視して並べ替え` are not screening filters; they control ranking calculation and display ordering.
- Ranking build uses a fast batch path first: it fetches OHLCV in chunks, builds feature snapshots from already-fetched market data, then reuses existing Screening / Investment Score services. If the batch path fails with a provider/domain error, local/deterministic providers can fall back to the existing per-symbol preview path; live Yahoo failures are reported once without retrying every symbol to avoid repeated network failures.
- Yahoo OHLCV uses the same non-threaded yfinance download path for single-symbol cockpit and multi-symbol ranking requests. The cockpit reuses one fetched OHLCV range for quote display and feature construction instead of fetching the same symbol again. Yahoo cockpit fetch prioritizes price data: initial fetch skips live FX and fundamentals so price / forecast / score rows can render without waiting on nonessential live requests. SMAI shares one curl_cffi-backed yfinance session across `Search`, `download`, and `Ticker` calls so Yahoo cookie / crumb state stays attached to the same session. If yfinance returns an empty batch response, the provider retries once after a short delay to absorb first-call warm-up / transient empty responses. Because live Yahoo requests are network-dependent and can be slow or noisy, Streamlit ranking warns when selected symbols exceed 30, uses smaller non-threaded download chunks, and suppresses yfinance's raw console noise in favor of structured UI error rows.
- Ranking rows are cached in Streamlit session state by `provider + symbols + start + end`. Re-running the same request or changing only the ranking weight preset reuses fetched rows and only re-sorts the display.
- The ranking progress indicator reports batch fetch, feature construction, forecast agreement calculation, and final sorting so large candidate sets do not look frozen.
- Ranking remains decision support only. Use `深掘りする銘柄` to move one selected symbol into `銘柄コックピット` for detailed price / forecast / score-reason review.

Phase 16 final UI smoke checklist:

- Change screening conditions and confirm candidate count / comparison symbols update coherently.
- Build a ranking and confirm progress messages are shown.
- Run the same ranking again and confirm cached rows are reused.
- Change only `重視して並べ替え` and confirm rows are re-sorted without a provider refetch.
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
