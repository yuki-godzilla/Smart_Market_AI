# Forecast Model Weighting Adjustments

同一rolling-origin foldで現行consensusと候補weightを比較します。前半originでweightを作り、後半holdoutでRMSE 1%以上改善かつ方向一致率維持を確認します。

## 20営業日

- 判定: 保留
- tuning origin数: 6
- holdout origin数: 5
- 現行RMSE: 0.0803
- 候補RMSE: 0.0799
- 現行方向一致率: 0.3696
- 候補方向一致率: 0.3696
- 理由: 時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.2173
  - `advanced_tree_sklearn`: 0.2443
  - `advanced_gbdt_sklearn`: 0.2597
  - `advanced_quantile`: 0.2788

## 60営業日

- 判定: 保留
- tuning origin数: 5
- holdout origin数: 4
- 現行RMSE: 0.1769
- 候補RMSE: 0.1771
- 現行方向一致率: 0.7091
- 候補方向一致率: 0.7091
- 理由: 時系列holdoutでRMSE 1%以上改善と方向一致率維持を同時に満たさないため保留します。
- 候補weight:
  - `advanced_linear`: 0.2345
  - `advanced_tree_sklearn`: 0.2538
  - `advanced_gbdt_sklearn`: 0.2467
  - `advanced_quantile`: 0.2650
