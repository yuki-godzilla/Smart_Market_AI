# Forecast Model Weighting Adjustments

同一rolling-origin foldで現行consensusと候補weightを比較します。前半originでweightを作り、後半holdoutでRMSE 1%以上改善かつ方向一致率維持を確認します。

## 20営業日

- 判定: 保留
- tuning origin数: 10
- holdout origin数: 8
- 現行RMSE: 0.0776
- 候補RMSE: 0.0776
- 現行方向一致率: 0.6250
- 候補方向一致率: 0.6250
- 理由: 時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.2304
  - `advanced_tree_sklearn`: 0.2786
  - `advanced_gbdt_sklearn`: 0.2399
  - `advanced_quantile`: 0.2511

## 60営業日

- 判定: 保留
- tuning origin数: 10
- holdout origin数: 7
- 現行RMSE: 0.2034
- 候補RMSE: 0.2024
- 現行方向一致率: 0.6000
- 候補方向一致率: 0.5750
- 理由: 時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.0526
  - `advanced_tree_sklearn`: 0.4575
  - `advanced_gbdt_sklearn`: 0.0690
  - `advanced_quantile`: 0.4208
