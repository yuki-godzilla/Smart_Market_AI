# Forecast Model Weighting Adjustments

同一rolling-origin foldで現行consensusと候補weightを比較します。前半originでweightを作り、後半holdoutでRMSE 1%以上改善かつ方向一致率維持を確認します。

## 20営業日

- 判定: 保留
- tuning origin数: 8
- holdout origin数: 6
- 現行RMSE: 0.1006
- 候補RMSE: 0.1004
- 現行方向一致率: 0.6744
- 候補方向一致率: 0.6977
- 理由: 時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.2416
  - `advanced_tree_sklearn`: 0.2562
  - `advanced_gbdt_sklearn`: 0.1958
  - `advanced_quantile`: 0.3064

## 60営業日

- 判定: 保留
- tuning origin数: 7
- holdout origin数: 6
- 現行RMSE: 0.2862
- 候補RMSE: 0.2875
- 現行方向一致率: 0.6136
- 候補方向一致率: 0.6136
- 理由: 時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.3030
  - `advanced_tree_sklearn`: 0.2184
  - `advanced_gbdt_sklearn`: 0.2467
  - `advanced_quantile`: 0.2318
