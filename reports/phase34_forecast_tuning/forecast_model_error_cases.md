# Forecast Model Error Cases

誤差が大きいrolling-origin例です。売買判断ではなくモデル改善用です。

| Symbol | Model | Horizon | Origin | Predicted | Actual | Absolute error |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| AMD | advanced_gbdt_sklearn | 60 | 2026-04-13 | 0.0385 | 1.2150 | 1.1765 |
| AMD | advanced_quantile | 60 | 2026-04-13 | 0.0921 | 1.2150 | 1.1229 |
| AMD | forecast_consensus | 60 | 2026-04-13 | 0.1103 | 1.2150 | 1.1047 |
| AMD | advanced_tree_sklearn | 60 | 2026-04-13 | 0.1220 | 1.2150 | 1.0930 |
| AMD | advanced_linear | 60 | 2026-04-13 | 0.1908 | 1.2150 | 1.0242 |
| AMD | advanced_tree_sklearn | 60 | 2016-11-07 | 0.0840 | 0.7586 | 0.6746 |
| AMD | advanced_gbdt_sklearn | 60 | 2016-11-07 | 0.1011 | 0.7586 | 0.6575 |
| AMD | advanced_quantile | 60 | 2016-11-07 | 0.1207 | 0.7586 | 0.6379 |
| AMD | forecast_consensus | 60 | 2016-11-07 | 0.1606 | 0.7586 | 0.5980 |
| 4755.T | advanced_quantile | 60 | 2019-02-22 | -0.0613 | 0.3690 | 0.4303 |
| AMD | advanced_linear | 60 | 2016-11-07 | 0.3368 | 0.7586 | 0.4218 |
| 4755.T | forecast_consensus | 60 | 2019-02-22 | -0.0373 | 0.3690 | 0.4063 |
| 4755.T | advanced_gbdt_sklearn | 60 | 2019-02-22 | -0.0342 | 0.3690 | 0.4032 |
| 4755.T | advanced_quantile | 60 | 2023-11-24 | -0.0382 | 0.3636 | 0.4018 |
| 4755.T | advanced_linear | 60 | 2019-02-22 | -0.0249 | 0.3690 | 0.3939 |
| 4755.T | advanced_tree_sklearn | 60 | 2019-02-22 | -0.0222 | 0.3690 | 0.3912 |
| 4755.T | forecast_consensus | 60 | 2023-11-24 | -0.0187 | 0.3636 | 0.3823 |
| 4755.T | advanced_tree_sklearn | 60 | 2023-11-24 | -0.0167 | 0.3636 | 0.3803 |
| 4755.T | advanced_linear | 60 | 2023-11-24 | -0.0108 | 0.3636 | 0.3744 |
| 4755.T | advanced_gbdt_sklearn | 60 | 2023-11-24 | -0.0031 | 0.3636 | 0.3667 |
