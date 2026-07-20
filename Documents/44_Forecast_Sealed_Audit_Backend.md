# Forecast Sealed Audit Backend

## 1. 目的

Forecastのモデル選択、中心return、方向return、予測幅、confidenceを、予測時点のまま保存し、
指定した営業日数の価格が実際に観測された後だけ実績returnを付与する。

過去データを現在のcodeで再生した結果と、将来時点で実際に保存した予測を区別する。新しいモデルや
range校正のruntime採用は、この新暦期間または新symbolのsealed auditを通過するまで行わない。

## 2. 責務境界

- `backend/forecast/sealed_audit.py`: contract、SQLite repository、capture、maturation、集計、export
- `tools/manage_forecast_sealed_audit.py`: `init`、`capture`、`mature`、`status`、`export`
- `data/cache/forecast_sealed_audit.sqlite`: local-onlyの追記専用監査DB
- `forecast_model_validation_points.csv`: 既存評価器とRolling Conformalへ渡す成熟済みpoint

Forecast、Cockpit、Ranking、Scoringのruntime計算値は変更しない。監査DBの停止・破損・lock競合を
通常Forecastの成功に見せず、監査処理側だけをfail-closedにする。

## 3. 不変contract

### Manifest

予測を保存する前に次を固定する。

- cohort: `new_calendar`、`new_symbol`、`mixed`
- symbol集合
- horizon集合
- 受付可能な最古origin
- source revision
- model selection / confidence / interval policy version
- 1 horizonあたり最低100成熟case
- target coverage 60%、最低coverage 55%
- proper interval score改善1%以上
- range候補の適用率50%以上

同じmanifest IDへ異なる内容を保存できない。

### Prediction snapshot

同じ`manifest / symbol / horizon / origin`は1件だけ保存する。内容には次を含む。

- origin時刻・価格・provider
- 中心return・方向return・予測価格
- lower / upper range
- center / direction confidence
- selection policy、horizon band、audit status、selection mode
- center / direction adapter、weight、model disagreement
- 入力bar数と全barのSHA-256
- 実際にDBへ記録した時刻

symbol / horizon / policyがmanifestと異なる場合、originが受付境界より古い場合、originから記録までが
7日を超える場合、capture実行時のsource revisionがmanifestと異なる場合は保存しない。同一keyの再実行は
既存snapshotを保持し、異なる値で上書きしない。

### Matured outcome

保存時のproviderと同じ日足からoriginを探し、ちょうど`horizon_days`本後のbarをtargetとする。
次の場合は実績を付与しない。

- target bar数が不足している
- targetが観測時刻より後
- targetがprediction記録時点ですでに観測可能だった
- origin barが消失、重複または価格改訂されている
- providerが異なる
- target価格が0以下

実績returnは、保存済みorigin priceとtarget closeから再計算して一致を確認する。outcomeも上書きしない。

## 4. 保存と改変検知

SQLiteはforeign key、WAL、busy timeout、transaction、unique keyを使う。manifest、prediction、outcomeは
canonical JSONとSHA-256を保存し、読み込み時にdigestとschemaを再検証する。JSONだけ、hashだけ、DB
versionだけを変更しても正常データとして読み込まない。

DBはruntime artifactでありGitへcommitしない。破損時に空の監査結果へ暗黙fallbackせず、
`ForecastSealedAuditCorruptData`として停止する。

## 5. 成熟後の評価

`export`は成熟済みoutcomeだけを既存`ForecastValidationPoint`へ変換する。

- RMSE
- direction accuracy
- interval coverage
- mean interval width
- 60% coverage用proper interval score
- horizon別のcaptured / matured / required / ready

必要case数へ到達したことは「評価可能」を意味し、runtime採用を意味しない。Rolling Conformal候補は、
`evaluate_rolling_conformal_intervals.py --evaluation-role new_sealed_audit`へexport CSVを渡し、事前固定gateと
subgroup監査を別途通過する必要がある。

## 6. 運用順序

1. Git revision、symbol、horizon、受付originを決めて`init`
2. 最新OHLCV snapshotを作成した直後に`capture`
3. 同一originの再実行はskipされることを確認
4. OHLCV更新後に`mature`
5. `status`でhorizon別成熟数を監視
6. 最低case数到達後に`export`
7. 現行runtimeと候補を、中心・方向・range・confidence・subgroup別に比較

収集頻度は毎営業日または週次でよい。1回の実行で過去originを人工的に量産せず、その時点で利用可能な
最新originだけを保存する。

## 7. 現時点の採用状態

- Sealed Audit repository / CLI: backend採用
- Forecast runtimeへの自動記録: 未接続。明示運用CLIのみ
- 予測中心・方向・range・confidence: 変更なし
- Rolling Conformal runtime接続: 不採用のまま
- UI表示: 変更なし

次のbackend作業は、監査対象symbol manifestを事前固定し、現在時点のOHLCV snapshot収集とcaptureを
定期運用できるようにすることである。UIの進捗表示はbackendの保存・評価contractが安定した後に行う。
