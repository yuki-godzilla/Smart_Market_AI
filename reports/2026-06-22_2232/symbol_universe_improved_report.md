# symbol_universe.csv 精度向上レポート

## 出力ファイル

- `symbol_universe_improved.csv`: 改善済みDB
- `symbol_universe_improved_change_log.csv`: 変更差分ログ
- `symbol_universe_improved_report.md`: このレポート

## 実施方針

- 外部照合なしで、CSV内の既存根拠列だけを使った安全な正規化に限定。
- `smai_theme_tags` に入っている高信頼テーマを、ランキングUIが現在参照している `tags` / `theme` に同期。
- `sector` は広義セクターとして維持し、明確な半導体・REIT・債券・商品ETFなどだけ補正。
- `data_quality` は空欄を避け、主要メタデータ・数値カバレッジから `OK` / `WARN` / `BLOCK` を付与。
- `industry_gics` / `subindustry_gics` は全件空欄だったが、外部ソースなしにGICS業種を推定投入すると誤分類リスクが高いため今回は未投入。JP業種は既存の `tse_33_industry` / `topix_17` を正として利用する前提。

## 変更件数

- `tags`: 9197 件
- `data_quality`: 9057 件
- `theme`: 1166 件
- `theme_source`: 1166 件
- `theme_confidence`: 1166 件
- `sector`: 33 件

## 変更理由別件数

- `sync_filter_tags_from_smai_theme_tags`: 9197 件
- `backfill_data_quality_from_required_metadata_coverage`: 9057 件
- `promote_primary_theme_from_smai_theme_tags`: 1166 件
- `mark_theme_rule_source`: 1166 件
- `raise_theme_confidence_for_exact_theme_tag`: 1166 件
- `high_confidence_sector_normalization`: 33 件

## ランキングUIの既存ロジックで拾える件数 before/after

| key | before | after | delta |
|---|---:|---:|---:|
| `semiconductor` | 0 | 34 | +34 |
| `automotive` | 0 | 130 | +130 |
| `trading` | 0 | 288 | +288 |
| `bank` | 0 | 222 | +222 |
| `insurance` | 0 | 31 | +31 |
| `high_dividend` | 0 | 1251 | +1251 |
| `reit` | 43 | 56 | +13 |
| `bond` | 3 | 160 | +157 |
| `commodity` | 39 | 56 | +17 |
| `technology` | 1382 | 1397 | +15 |
| `communication` | 478 | 1501 | +1023 |
| `financial` | 831 | 831 | +0 |
| `industrial` | 1598 | 1598 | +0 |
| `materials` | 492 | 492 | +0 |
| `real_estate` | 275 | 325 | +50 |
| `utilities` | 134 | 154 | +20 |

## theme 分布 after

| theme | 件数 |
|---|---:|
| `balanced` | 1845 |
| `technology` | 1316 |
| `consumer` | 1245 |
| `healthcare` | 1179 |
| `communication` | 957 |
| `financial` | 828 |
| `index` | 749 |
| `energy` | 357 |
| `trading` | 287 |
| `bond` | 160 |
| `automotive` | 130 |
| `reit` | 56 |
| `commodity` | 54 |
| `semiconductor` | 34 |

## sector 分布 after

| sector | 件数 |
|---|---:|
| `consumer` | 1614 |
| `industrial` | 1597 |
| `technology` | 1396 |
| `healthcare` | 1182 |
| `index` | 980 |
| `financial` | 831 |
| `materials` | 492 |
| `communication` | 478 |
| `real_estate` | 292 |
| `energy` | 201 |
| `utilities` | 134 |

## data_quality 分布 before/after

| quality | before | after |
|---|---:|---:|
| `OK` | 119 | 8618 |
| `WARN` | 21 | 540 |
| `BLOCK` | 0 | 39 |
| `(empty)` | 9057 | 0 |

## 代表銘柄チェック after

| symbol | name | market | asset_type | theme | sector | tags | smai_theme_tags | JPX33 | TOPIX17 | GICS sector | data_quality |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7203.T | Toyota Motor | jp | stock | automotive | consumer | balanced,lower_risk,automotive,consumer,high_dividend | automotive,consumer,high_dividend | 輸送用機器 | 自動車・輸送機 |  | OK |
| 6758.T | Sony Group | jp | stock | technology | technology | balanced,technology | technology | 電気機器 | 電機・精密 |  | OK |
| 8035.T | Tokyo Electron | jp | stock | semiconductor | technology | growth,semiconductor,technology | semiconductor,technology | 電気機器 | 電機・精密 |  | OK |
| 6146.T | Disco | jp | stock | semiconductor | technology | growth,semiconductor,technology | semiconductor,technology | 機械 | 機械 |  | OK |
| 6723.T | Renesas Electronics | jp | stock | semiconductor | technology | growth,semiconductor,technology | semiconductor,technology | 電気機器 | 電機・精密 |  | OK |
| 6920.T | Lasertec | jp | stock | semiconductor | technology | growth,semiconductor,technology | semiconductor,technology | 電気機器 | 電機・精密 |  | OK |
| 7735.T | SCREEN Holdings | jp | stock | semiconductor | technology | growth,semiconductor,technology | semiconductor,technology | 電気機器 | 電機・精密 |  | OK |
| 8306.T | Mitsubishi UFJ Financial Group | jp | stock | financial | financial | balanced,bank,financial | bank,financial | 銀行業 | 銀行 |  | OK |
| 8058.T | Mitsubishi Corporation | jp | stock | trading | industrial | dividend,high_dividend,industrial,trading | high_dividend,industrial,trading | 卸売業 | 商社・卸売 |  | OK |
| 9532.T | 大阪瓦斯 | jp | stock | energy | utilities | dividend,energy,utilities | energy,utilities | 電気・ガス業 | 電力・ガス |  | OK |
| NVDA | NVIDIA | us | stock | semiconductor | technology | growth,semiconductor,technology | semiconductor,technology |  |  | Information Technology | OK |
| TSLA | Tesla | us | stock | automotive | consumer | growth,automotive,consumer | automotive,consumer |  |  |  | OK |
| AMD | Advanced Micro Devices | us | stock | technology | technology | growth,technology | technology |  |  | Information Technology | OK |
| SMH | ヴァンエック ベクトル半導体ETF | us | etf | semiconductor | technology | low_cost,index,semiconductor | index,semiconductor |  |  |  | OK |
| QQQ | Invesco QQQ Trust | us | etf | index | index | growth,index | index |  |  |  | OK |
| SPY | SPDR S&P 500 ETF | us | etf | index | index | installment,balanced,lower_risk,index | index |  |  |  | OK |
