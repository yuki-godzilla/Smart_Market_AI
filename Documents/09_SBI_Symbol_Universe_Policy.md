# SBI Symbol Universe Policy

## 1. 目的

SMAI の銘柄ランキング、比較分析、将来の銘柄推薦で使う初期ユニバースは、当面 **SBI証券で取り扱いがあり、個人投資家が現物・NISA・長期投資で使いやすい商品** を前提に整理する。

この方針は、売買推奨ではなく、ランキング対象をユーザーが実際に検討しやすい候補へ絞るためのものです。

## 2. 現在の実装状態

現在の ranking candidate master は `data/marketdata/symbol_universe.csv` です。

実装済み:

- `symbol_universe.csv` による local-first な候補マスタ
- `backend/marketdata/symbol_metadata_schema.py` による列・enum・decimal・metadata freshness 定義
- `tools/import_symbol_universe_source.py` による source CSV import
- `tools/refresh_symbol_universe_metadata.py` による provider-neutral metadata refresh
- JPX seed による国内株 / 国内 ETF の候補拡張

未実装:

- SBI証券取扱商品かどうかを表す broker / tradability / NISA / 積立対応 metadata
- 初期 ranking から FX / CFD / 先物 / option / crypto / bond / MMF / commodity / leveraged / inverse を除外する policy enforcement
- SBI公式一覧や投信/NISA一覧からの自動または半自動 source adapter

## 3. 初期対象

初期 ranking universe の対象:

- 国内株式
- 米国株式
- 国内 ETF
- 米国 ETF / 海外 ETF
- 投資信託
- REIT
- NISA成長投資枠対象商品
- NISAつみたて投資枠対象商品
- 積立対応商品

ETF / 投信 / REIT は、商品分類と評価軸が異なるため、`asset_type` と詳細 metadata を分けて管理する。

## 4. 初期対象外

初期 ranking universe では、次の商品を既定で除外する。

- FX
- CFD
- 先物・オプション
- 信用取引専用の評価軸
- 暗号資産
- 債券
- 外貨建MMF
- 金・銀・プラチナなどの直接的な貴金属商品
- レバレッジ商品
- インバース商品

注意:

- SBI証券で取り扱いがある商品でも、SMAI の初期 ranking では対象外にすることがある。
- 既存 seed には import 経路確認用の commodity ETF が含まれる場合がある。SBI policy enforcement 実装後は、commodity / leveraged / inverse / untradable を既定除外する。

## 5. 分類定義

### 5.1 地域

UI表示は既存の `国内` / `米国` / `その他海外` / `全体` を維持する。

内部分類は当面 `market` を使い、将来 `region` へ拡張できるようにする。

| UI | 現在の値 | 将来の標準値 |
| --- | --- | --- |
| 国内 | `jp` | `domestic` |
| 米国 | `us` | `us` |
| その他海外 | `developed_ex_us`, `emerging`, `other_global` | `developed_ex_us`, `emerging`, `other` |
| 全体 | `all` | `global` / `all` |

### 5.2 商品

初期 ranking で扱う商品分類:

- `stock`: 個別株
- `etf`: ETF
- `mutual_fund`: 投資信託
- `reit`: REIT

既存互換:

- `adr`, `fund`, `investment_trust` は既存データ互換のため当面許容する。
- SBI policy 実装時は、`adr` を米国株相当として扱うか、個別に対象外にするかを policy で決める。

初期対象外として許容値に追加してよいが ranking から除外する分類:

- `fx`
- `cfd`
- `futures`
- `option`
- `crypto`
- `bond`
- `mmf`
- `commodity`

## 6. SBI policy metadata

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
- `aum`
- `distribution_yield_pct`
- `tracking_method`
- `trust_fee_pct`
- `total_net_assets`
- `distribution_policy`
- `property_type`

## 7. Default ranking universe policy

既定 policy の概念:

```yaml
ranking_universe:
  broker: sbi_securities
  include_asset_types:
    - stock
    - etf
    - mutual_fund
    - reit
  exclude_asset_types:
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
  require_sbi_supported: true
  include_nisa_only: false
```

除外条件:

- `asset_type` が初期対象外
- `is_leveraged` が true
- `is_inverse` が true
- `tradability` が `tradable` ではない
- `is_sbi_supported` が false
- `is_active` が false

将来、上級者向け設定で一部をON/OFFできるようにし、既定は長期投資・NISA・初心者向けに保守的にする。

## 8. 商品別フィルタ定義

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

## 9. Source adapter 方針

今回の範囲では、SBI証券へのログイン、スクレイピング、リアルタイム取得は行わない。

優先する source path:

1. ローカル CSV seed / 手動 curated source
2. SBI取扱銘柄一覧を人手で取得した CSV の import
3. JPX / FSA / IMAJ / 投信協会 / NISA対象商品リストなどの public source import
4. Yahoo / FMP / EODHD / Alpha Vantage などの metadata refresh
5. 将来必要な場合のみ、SBI source adapter を明示 opt-in で追加

通常テストは network 非依存に保つ。

## 10. 実装順

次の Phase 18 slice として、以下の順で進める。

1. `symbol_metadata_schema.py` に SBI policy columns を追加する。
2. `asset_type` に `reit` と初期対象外の分類を追加する。
3. ranking universe policy helper を追加する。
4. `ui/ranking.py` の候補抽出前に policy を適用する。
5. レバレッジ / インバース / 非SBI / 非tradable の除外テストを追加する。
6. `symbol_universe.csv` の既存行へ conservative default metadata を付与する。
7. SBI / NISA / 投信 metadata source import を追加する。

UI表示は、policy helper が安定してから追加する。
