# Forecast Model Weighting Adjustments

同一rolling-origin foldで現行consensusと候補weightを比較します。前半originでweightを作り、後半holdoutでRMSE改善かつ方向一致率維持を確認します。

## 20営業日

- 判定: 保留
- tuning origin数: 0
- holdout origin数: 0
- 現行RMSE: 0.0000
- 候補RMSE: 0.0000
- 現行方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutでRMSE改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.2500
  - `advanced_tree_sklearn`: 0.2500
  - `advanced_gbdt_sklearn`: 0.2500
  - `advanced_quantile`: 0.2500

## 60営業日

- 判定: 保留
- tuning origin数: 0
- holdout origin数: 0
- 現行RMSE: 0.0000
- 候補RMSE: 0.0000
- 現行方向一致率: 0.0000
- 候補方向一致率: 0.0000
- 理由: 時系列holdoutでRMSE改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.2500
  - `advanced_tree_sklearn`: 0.2500
  - `advanced_gbdt_sklearn`: 0.2500
  - `advanced_quantile`: 0.2500
