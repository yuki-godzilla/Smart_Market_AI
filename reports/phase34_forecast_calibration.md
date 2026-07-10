# Forecast Consensus Calibration Sprint

予測方向を変えず、予測幅だけを保守的に縮小する事前定義候補を比較します。
factorは調整群の前半originで選び、後半originと銘柄非重複の検証群で確認します。

| Stage | Horizon | Factor | Default RMSE | Candidate RMSE | Direction | Adopted |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| tuning-holdout | 20 | 0.50 | 0.0686 | 0.0693 | 0.6724 | no |
| tuning-holdout | 60 | 0.75 | 0.2037 | 0.2084 | 0.6552 | no |

監査群を確認するまではruntimeへ適用しません。
