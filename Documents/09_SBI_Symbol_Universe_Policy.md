# SBI Symbol Universe Policy

## 1. 目的

SMAI の銘柄ランキング、比較分析、将来の銘柄推薦で使う MVP ユニバースは、当面 **SBI証券で取り扱いがあり、個人投資家が現物・NISA・長期投資で使いやすい株式・ETF** を前提に整理する。

この方針は、売買推奨ではなく、ランキング対象をユーザーが実際に検討しやすい候補へ絞るためのものです。

## 2. 現在の実装状態

現在の ranking candidate master は `data/marketdata/symbol_universe.csv` です。

実装済み:

- `symbol_universe.csv` による local-first な候補マスタ
- `backend/marketdata/symbol_metadata_schema.py` による列・enum・decimal・metadata freshness 定義
- `symbol_universe.csv` の conservative default metadata
  - `broker=sbi_securities`
  - `tradability=unknown`
  - `nisa_category=unknown`
  - `investment_style=unknown`
  - `is_sbi_supported=true`
  - `is_active=true`
  - `is_leveraged=false`
  - `is_inverse=false`
- `backend/marketdata/ranking_universe_policy.py` による初期 ranking universe policy
- ranking 候補抽出前の policy enforcement
- `tools/import_symbol_universe_source.py` による source CSV import
- import source profile
  - `sbi_us_stock`
  - `sbi_us_etf`
- source seed CSV
  - `data/marketdata/symbol_universe_sources/sbi_us_stock_seed.csv`
  - `data/marketdata/symbol_universe_sources/sbi_us_etf_seed.csv`
- `symbol_universe.csv` への source seed 反映
  - 米国株 8件を追加
  - 米国 ETF 7件を追加し、既存 ETF 3件を SBI ETF profile で更新
  - 投資信託 4件を将来対応 seed として追加済み。ただし MVP ranking universe からは除外する
- `tools/refresh_symbol_universe_metadata.py` による provider-neutral metadata refresh
- JPX seed による国内株 / 国内 ETF の候補拡張

未実装:

- SBI公式一覧や NISA 一覧からの自動または半自動 source adapter
- 投信 CSV / 基準価額 / 投信 ranking 対応。これは Future Phase とし、MVP には含めない

## 3. 銘柄マスタ取得方針

SMAI は初期段階では、SBI証券サイトから直接リアルタイム取得・スクレイピングするアプリにはしない。

理由:

- SBI証券の画面構成変更に弱い。
- ログイン、動的画面、利用規約、アクセス負荷、保守性のリスクがある。
- 投資信託は基準価額、信託報酬、NISA区分、積立可否などの更新運用が重いため、MVPから外す。
- ランキング機能の本質は、取得そのものではなく比較・分析・判断材料の整理である。

基本経路:

1. SBI公式サイト、JPX、NISA対象商品リストなどで取扱銘柄・制度情報を確認する。
2. CSV / JSON / YAML などの local source に整形する。
3. SMAI の source import / metadata refresh が `symbol_universe.csv` へ取り込む。
4. ranking / screening / cockpit は `symbol_universe.csv` を候補 universe として使う。
5. 将来、必要な範囲だけ自動更新 adapter を追加する。

つまり SMAI は、当面 **SBI証券から直接取得するアプリ** ではなく、**SBI証券で買える前提のローカル銘柄マスタを持ち、それを分析・ランキングするアプリ** として扱う。

### 3.1 現在の実装への対応

現状の実装では、ChatGPT案の概念を次の既存構成へ対応付ける。

| 概念 | 現在の実装 |
| --- | --- |
| SecurityMaster | `data/marketdata/symbol_universe.csv` の1行 |
| Enum / field catalog | `backend/marketdata/symbol_metadata_schema.py` |
| Repository / loader | `ui/symbol_universe.py` の CSV loader / validator |
| Source import | `backend/marketdata/symbol_universe_import.py` と `tools/import_symbol_universe_source.py` |
| Metadata refresh | `backend/marketdata/symbol_metadata_refresh.py` と `tools/refresh_symbol_universe_metadata.py` |
| RankingUniverseSelector | `backend/marketdata/ranking_universe_policy.py` |
| Ranking への適用 | `ui/ranking.py` の候補抽出前 policy enforcement |

今すぐ `backend/domain/security` / `backend/infrastructure/security_master` / `backend/application/ranking` のような新階層は作らない。
銘柄マスタが大きくなり、API / UI / batch の複数箇所から同じ repository が必要になった段階で、既存構成に合わせて `backend/marketdata/security_master/` などへ昇格する。

### 3.2 現在のマスタ形式

初期マスタは `data/marketdata/symbol_universe.csv` に集約する。

現在の主要列:

```text
symbol,name,market,asset_type,currency,broker,tradability,nisa_category,
investment_style,is_sbi_supported,is_active,is_leveraged,is_inverse,
theme,sector,aliases,dividend_category,dividend_yield_pct,market_cap_tier,
index_family,expense_ratio_pct,complexity,tags,per,pbr,roe_pct,
consensus_rating,forecast_agreement,data_quality,risk_band,
metadata_source,metadata_as_of,metadata_updated_at
```

注意:

- `symbol` は現在、provider 互換を優先し、日本株は `7203.T` のような yfinance-compatible symbol を使う。
- 将来、JPX 4桁コード、exchange、ISIN、fund code などを分離したくなった場合は、追加列または dedicated master へ拡張する。
- JSON / YAML master は将来の候補だが、現時点では CSV import / validation / manifest が整っているため CSV を標準とする。

### 3.3 段階的な拡張

すべての SBI 取扱商品を一度に完全収録しない。MVP では、ランキング体験に効く範囲から段階的に増やす。

Phase A: 完了

- 国内株式
- 米国主要株
- 国内 ETF
- 米国主要 ETF

Phase B:

- SBI取扱米国株式の拡張
- SBI取扱海外 ETF の拡張
- NISA 対象判定の追加

Phase C:

- SBI取扱銘柄一覧の自動または半自動 adapter
- 外部 public source との同期

Future Phase:

- 主要投資信託ウォッチリスト
- 投信 CSV 取込
- 投信基準価額チャート
- 投信 Provider 連携
- 投信ランキング

### 3.4 商品別 source 方針

国内株式:

- まず JPX 上場銘柄一覧をベースにする。
- SBI証券での厳密な取扱可否は後続拡張として扱う。
- 初期値は `is_sbi_supported=true`, `tradability=unknown` を許容する。
- 監理銘柄、整理銘柄、売買停止銘柄、上場廃止予定銘柄、極端に流動性が低い銘柄は、将来 `is_active=false` や quality warning で扱う。

米国株式:

- SBI証券の米国株式取扱銘柄一覧を手動 CSV 化または source CSV 化して取り込む。
- Nasdaq / NYSE / AMEX 上場情報や Yahoo などは補助 metadata source として扱う。
- 初期は主要銘柄から始め、SBI確認済み source が入ったものは `tradability=tradable` へ更新する。

国内 ETF / ETN:

- JPX ETF / ETN 一覧と SBI ETF 取扱情報を source 候補にする。
- ETF では連動指数、投資地域、資産クラス、信託報酬、純資産総額、分配金利回り、レバレッジ / インバース判定を優先する。
- ETN は `complexity=etn` または dedicated flag を持たせ、初期 ranking では除外または上級者向け候補にする。

米国 ETF / 海外 ETF:

- SBI証券の海外 ETF 取扱銘柄一覧を source 候補にする。
- ETF.com、issuer 公式サイト、Yahoo などは補助 metadata source として扱う。
- VOO / VTI / VT / QQQ / SPY / IVV など、長期投資で比較されやすい銘柄を優先して整備する。

投資信託:

- MVP では ranking / screening / chart 対象にしない。
- 主要ファンドの seed は将来対応用の保持データとして扱う。
- SBI の投信検索画面を直接スクレイピングしない。
- Future Phase では、信託報酬、純資産総額、投資対象地域、投資対象資産、インデックス / アクティブ、NISA成長投資枠、NISAつみたて投資枠、積立対応、分配方針を優先 metadata とする。

## 4. 初期対象

MVP ranking universe の対象:

- 国内株式
- 米国株式
- 国内 ETF
- 米国 ETF / 海外 ETF
- NISA成長投資枠対象商品

投資信託、REIT、ADR は `symbol_universe.csv` や schema に残してよいが、MVP の default ranking universe からは除外する。

## 5. 初期対象外

初期 ranking universe では、次の商品を既定で除外する。

- FX
- CFD
- 先物・オプション
- 信用取引専用の評価軸
- 暗号資産
- 債券
- 外貨建MMF
- 金・銀・プラチナなどの直接的な貴金属商品
- 投資信託
- ADR
- REIT
- レバレッジ商品
- インバース商品

注意:

- SBI証券で取り扱いがある商品でも、SMAI の初期 ranking では対象外にすることがある。
- 既存 seed に import 経路確認用の commodity ETF などが含まれる場合でも、ranking 候補抽出では commodity / leveraged / inverse / untradable を既定除外する。

## 6. 分類定義

### 6.1 地域

MVP UI 表示は `国内` / `米国` / `全体` とする。

内部分類は当面 `market` を使い、将来 `region` へ拡張できるようにする。

| UI | 現在の値 | 将来の標準値 |
| --- | --- | --- |
| 国内 | `jp` | `domestic` |
| 米国 | `us` | `us` |
| 全体 | `all` | `global` / `all` |

### 6.2 商品

初期 ranking で扱う商品分類:

- `stock`: 個別株
- `etf`: ETF

Future extension として master / schema に残してよいが、MVP ranking からは除外する分類:

- `mutual_fund`: 投資信託
- `fund`
- `investment_trust`
- `reit`: REIT
- `adr`

初期対象外として許容値に追加してよいが ranking から除外する分類:

- `fx`
- `cfd`
- `futures`
- `option`
- `crypto`
- `bond`
- `mmf`
- `commodity`

## 7. SBI policy metadata

`symbol_universe.csv` に追加する候補の metadata:

| column | 内容 |
| --- | --- |
| `broker` | 初期値は `sbi_securities` |
| `tradability` | `tradable` / `not_tradable` / `unknown` |
| `nisa_category` | `growth` / `tsumitate` / `both` / `none` / `unknown` |
| `investment_style` | `lump_sum` / `recurring` / `both` / `unknown` |
| `is_sbi_supported` | SBI証券取扱商品かどうか |
| `is_active` | 現在有効な候補かどうか |
| `is_leveraged` | レバレッジ商品かどうか |
| `is_inverse` | インバース商品かどうか |

ETF / 投信 / REIT 向けに将来追加する候補:

- `asset_class`
- `underlying_index`
- `distribution_yield_pct`
- `tracking_method`
- `total_net_assets`
- `property_type`

投信向けに `symbol_universe.csv` へ取り込み可能になった metadata。ただし MVP では ranking / screening / chart で使わない:

- `trust_fee_pct`
- `aum`
- `nisa_tsumitate_eligible`
- `nisa_growth_eligible`
- `installment_available`
- `management_style`
- `distribution_policy`

## 8. Default ranking universe policy

既定 policy の概念:

```yaml
ranking_universe:
  broker: sbi_securities
  include_asset_types:
    - stock
    - etf
  exclude_asset_types:
    - mutual_fund
    - fund
    - investment_trust
    - adr
    - reit
    - fx
    - cfd
    - futures
    - option
    - crypto
    - bond
    - mmf
    - commodity
  exclude_leveraged: true
  exclude_inverse: true
  exclude_untradable: true
  require_active: true
  require_sbi_supported: true
  include_nisa_only: false
```

除外条件:

- `asset_type` が初期対象外
- `is_leveraged` が true
- `is_inverse` が true
- `tradability` が `not_tradable`
- `is_sbi_supported` が明示的に false
- `is_active` が明示的に false

`tradability=unknown` は初期 seed の保守的な状態表現として扱い、stock / ETF では現在の既定 policy で ranking 候補として通す。
これは既存 `symbol_universe.csv` が SBI取扱確認済み master ではなく、SBI前提で整備中の candidate seed であるためです。

将来、上級者向け設定で一部をON/OFFできるようにし、既定は長期投資・NISA・初心者向けに保守的にする。

## 9. 商品別フィルタ定義

### 国内株式

- `market_cap_tier`
- `sector`
- `dividend_yield_pct`
- `per`
- `pbr`
- `roe_pct`
- `liquidity`
- `nisa_growth_eligible`

### 米国株式

- `market_cap_tier`
- `sector`
- `dividend_yield_pct`
- `per`
- `pbr`
- `roe_pct`
- `beta`
- `volatility`
- `liquidity`
- `nisa_growth_eligible`

### ETF

- `expense_ratio_pct`
- `aum`
- `underlying_index`
- `market` / future `region`
- `asset_class`
- `distribution_yield_pct`
- `tracking_method`
- `leverage_type`
- `liquidity`
- `nisa_growth_eligible`

### 投資信託

- `trust_fee_pct`
- `total_net_assets`
- `management_style`
- `underlying_index`
- `market` / future `region`
- `asset_class`
- `installment_available`
- `nisa_growth_eligible`
- `nisa_tsumitate_eligible`
- `distribution_policy`

### REIT

- `market` / future `region`
- `dividend_yield_pct`
- `nav_ratio`
- `market_cap_tier`
- `liquidity`
- `property_type`
- `nisa_growth_eligible`

## 10. Source adapter 方針

今回の範囲では、SBI証券へのログイン、スクレイピング、リアルタイム取得は行わない。

優先する source path:

1. ローカル CSV seed / 手動 curated source
2. SBI取扱銘柄一覧を人手で取得した CSV の import
3. JPX / FSA / NISA対象商品リストなどの public source import
4. Yahoo / FMP / EODHD / Alpha Vantage などの metadata refresh
5. 将来必要な場合のみ、SBI source adapter を明示 opt-in で追加

通常テストは network 非依存に保つ。

現在の source profile:

| profile | 用途 | 主な default |
| --- | --- | --- |
| `jpx_stock` | JPX国内株 seed | `market=jp`, `asset_type=stock`, `currency=JPY`, `symbol_suffix=.T`, `tradability=unknown` |
| `jpx_etf` | JPX国内 ETF seed | `market=jp`, `asset_type=etf`, `currency=JPY`, `tradability=unknown` |
| `sbi_us_stock` | SBI取扱米国株 seed | `market=us`, `asset_type=stock`, `currency=USD`, `tradability=tradable` |
| `sbi_us_etf` | SBI取扱米国/海外 ETF seed | `market=us`, `asset_type=etf`, `currency=USD`, `tradability=tradable` |
| `nisa_eligibility` | NISA制度 metadata 更新 source | 既存銘柄の `nisa_category`, `nisa_growth_eligible`, `nisa_tsumitate_eligible`, metadata fields だけを更新 |
| `mutual_fund_seed` | Future extension 用の主要投資信託 seed | `market=jp`, `asset_type=mutual_fund`, `currency=JPY`, `tradability=unknown` |

`jpx_*`, `sbi_*`, `mutual_fund_seed` は `broker=sbi_securities`, `is_sbi_supported=true`, `is_active=true`, `is_leveraged=false`, `is_inverse=false` を補完する。
source CSV 側に `is_leveraged` / `is_inverse` がある場合は、source 側の値を優先する。
`nisa_eligibility` は `--update-existing` と組み合わせる前提で、制度 metadata 以外の市場・商品・名称を上書きしない。

2026-05-18 時点の `symbol_universe.csv` は 146件です。
内訳は `stock=120`, `etf=20`, `mutual_fund=4`, `adr=2` です。MVP ranking universe はこのうち `stock` / `etf` のみを対象にします。

NG:

- Ranking / Screening が SBI証券サイトを直接参照する。
- UI 操作中に SBI の検索画面をスクレイピングする。
- source 取得失敗が既存 ranking UI を壊す。

OK:

- Ranking / Screening は `symbol_universe.csv` と policy helper だけを見る。
- source import / metadata refresh は batch command と manifest で管理する。
- live provider や自動 adapter は明示 opt-in にする。

## 11. 責務分離と将来構成

現在は最小構成を優先し、既存 `backend/marketdata` と `ui` の helper で実装する。

将来、銘柄マスタの利用箇所が増えた場合の候補:

```text
backend/marketdata/security_master/
  models.py        # SecurityMaster 相当
  repository.py    # CSV / JSON / future adapter loader
  universe.py      # RankingUniverseSelector 相当
  filters.py       # 商品別 filter 定義
```

判断基準:

- API と UI の両方から同じ銘柄マスタ loader が必要になった。
- `ui/symbol_universe.py` に backend 向け責務が増えた。
- ETF や将来の投信 / REIT の専用 metadata が増え、CSV列だけでは扱いづらくなった。
- source adapter が複数になり、取得元ごとの repository 境界が必要になった。

この段階までは、既存 `symbol_universe.csv`、schema、import command、policy helper を拡張する。

## 12. 実装順

Phase 18 の実装順:

1. `symbol_metadata_schema.py` に SBI policy columns を追加する。完了。
2. `asset_type` に `reit` と初期対象外の分類を追加する。完了。
3. ranking universe policy helper を追加する。完了。
4. `ui/ranking.py` の候補抽出前に policy を適用する。完了。
5. レバレッジ / インバース / 非SBI / 非tradable の除外テストを追加する。完了。
6. `symbol_universe.csv` の既存行へ conservative default metadata を付与する。完了。
7. SBI / NISA / future 投信 metadata source import を追加する。部分完了。
   - `--source-profile` と seed CSV は追加済み。
   - JPX stock / ETF profile と NISA eligibility profile は追加済み。
   - SBI US stock / ETF / mutual fund seed は `symbol_universe.csv` へ反映済み。
   - MVP ranking は stock / ETF のみを対象にし、mutual fund seed は Future Phase 用の保持データとする。
   - SBI公式一覧 / NISA公式一覧などからの半自動 adapter は未実装。

NISA / SBI確認済みなどの UI 表示は、対応する official / curated source metadata が入ってから追加する。投信の積立可否や基準価額は Future Phase で扱う。
