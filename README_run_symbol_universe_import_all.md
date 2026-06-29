# SMAI Symbol Universe Import All v5

`run_symbol_universe_import_all.bat` を Smart_Market_AI のルート直下へ配置して実行します。

```powershell
.\run_symbol_universe_import_all.bat 2026-06-23
```

## v5の方針

- コアUniverse更新を優先して最後まで通す安全版です。
- SBI外国株、SBI海外ETF、JPX/SBI既存ソース、screening backfill を実行します。
- 旧NISA系、quality review、ranking metadata は現行スキーマと未整合なためデフォルトスキップします。
- 必要な場合だけ環境変数で個別に有効化できます。

## 任意フラグ

```bat
set RUN_LEGACY_NISA_SEED=1
set RUN_NISA_LISTED_FUND=1
set RUN_NISA_JPX_ETF=1
set RUN_QUALITY_REVIEW=1
set RUN_RANKING_METADATA=1
```

これらは現状ではバリデーションで止まる可能性があるため、別スプリントで正規化後に有効化してください。

## 出力

- `logs/symbol_universe_import_all_<RUN_ID>.log`
- `reports/<実施日時>/import_*_<RUN_ID>.json`
- `data/marketdata/backup/symbol_universe_before_import_all_<RUN_ID>.csv`

レポートは実施日時ごとに `YYYY-MM-DD_HHMM` フォルダへ分けます。

```text
reports/2026-06-29_0904/
```

引数の基準日ではなく、実際にメンテナンスを実行したPCローカル日時を使います。
既存レポートを含む配置規約は `reports/README.md` を参照してください。
