# Forecast Model Weighting Adjustments

同一rolling-origin foldで現行consensusと候補weightを比較します。前半originでweightを作り、後半holdoutでRMSE 1%以上改善かつ方向一致率維持を確認します。

## 20営業日

- 判定: 保留
- tuning origin数: 6
- holdout origin数: 5
- 現行RMSE: 0.0686
- 候補RMSE: 0.0683
- 現行方向一致率: 0.6724
- 候補方向一致率: 0.6724
- 理由: 時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.0479
  - `advanced_tree_sklearn`: 0.4108
  - `advanced_gbdt_sklearn`: 0.0773
  - `advanced_quantile`: 0.4639

## 60営業日

- 判定: 保留
- tuning origin数: 6
- holdout origin数: 4
- 現行RMSE: 0.2037
- 候補RMSE: 0.2033
- 現行方向一致率: 0.6552
- 候補方向一致率: 0.6379
- 理由: 時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.0758
  - `advanced_tree_sklearn`: 0.4206
  - `advanced_gbdt_sklearn`: 0.0756
  - `advanced_quantile`: 0.4280
