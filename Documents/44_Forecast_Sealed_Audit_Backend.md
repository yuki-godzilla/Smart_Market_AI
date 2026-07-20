# Forecast Sealed Audit Backend

## 1. 目的

Forecastのモデル選択、中心return、方向return、予測幅、confidenceを、予測時点のまま保存し、
指定した営業日数の価格が実際に観測された後だけ実績returnを付与する。

過去データを現在のcodeで再生した結果と、将来時点で実際に保存した予測を区別する。新しいモデルや
range校正のruntime採用は、この新暦期間または新symbolのsealed auditを通過するまで行わない。

## 2. 責務境界

- `backend/forecast/sealed_audit.py`: contract、SQLite repository、capture、maturation、集計、export
- `backend/forecast/live_dataset.py`: batch取得、全cohort完全性確認、diagnostic snapshot
- `backend/forecast/sealed_audit_cycle.py`: verify、mature、capture、export、backupのrun-once contract
- `tools/manage_forecast_sealed_audit.py`: `init`、`capture`、`mature`、`status`、`export`、`verify`、`backup`
- `tools/run_forecast_sealed_audit_cycle.py`: local snapshotまたは明示live取得からの一括運用
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

run-once captureは固定cohortの全symbolがeligibleであり、全model / horizonの候補計算が成功してから
prediction batchを追記する。1銘柄だけ欠損したpartial cohortや、一部modelだけ成功した結果を正常runとして
保存しない。

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

`verify`はSQLite integrity、foreign key、全行のschema / SHA-256、manifest / prediction / outcome関係を
一括確認する。`backup`はSQLite online backupを一時ファイルへ作り、同じ完全性検証を通過した後だけatomic
replaceする。`export`も成熟前predictionとoutcomeをhash付きJSONLへ出力するため、DB backupと可読artifactの
両方を残せる。

live取得は監査DBと分離した一意のrun directoryへ保存する。全symbolのbarとmetadata、日足・timezone・provider・
timestamp一意性を確認し、Provider error、no bars、欠損metadata、mixed providerが1件でもあればDB更新前に停止する。
失敗snapshotとtyped failureは診断用に残すため、再実行時に失敗を空データや成功へ見せない。

run-once全体はDB単位のfile lockで多重起動を拒否する。既知のcollection / cycle失敗は、理由を500文字へ制限した
`sealed_forecast_audit_cycle_failure.json`と非0 exit codeを残す。lock競合もretry-safeな失敗として扱う。

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
2. `run_forecast_sealed_audit_cycle.py --allow-live`で完全な最新snapshotだけを確定
3. 既存predictionの`mature`を重大異常時all-or-noneで実行
4. 最新originの全predictionをall-or-noneで`capture`
5. DB全体を`verify`し、artifact exportとatomic backupを作成
6. 同一origin再実行がskipされることをrun resultで確認
7. 最低case数到達後、現行runtimeと候補を中心・方向・range・confidence・subgroup別に比較

収集頻度は毎営業日または週次でよい。1回の実行で過去originを人工的に量産せず、その時点で利用可能な
最新originだけを保存する。

## 7. 現時点の採用状態

- Sealed Audit repository / CLI: backend採用
- replay-safe run-once / strict live snapshot: backend採用。外部scheduler登録は未実施
- Forecast runtimeへの自動記録: 未接続。明示運用CLIのみ
- 予測中心・方向・range・confidence: 変更なし
- Rolling Conformal runtime接続: 不採用のまま
- UI表示: 変更なし

2026-07-20にcommit `79ccef8`、既存固定60銘柄、日本株25・米国株25・米国ETF10、
20 / 40 / 60 / 80 / 100 / 120日で`fsa_20260720_new_calendar_v1`を開始した。74,355日足、全60銘柄
eligible、共通origin 2026-07-17から360 predictionを保存した。targetは未到来のためoutcomeは0件である。

同日のrun-once実データ再生では、60銘柄を再検証し、同一origin 360件をすべてskip、pending 360件、
outcome追加0件として完了した。DB全体verify、hash付きartifact、検証済みbackupも同じrunで成功した。

次のbackend作業は、実point-in-time材料の継続収集・成熟監査を同じ水準のrun contractへまとめ、LLM Gatewayと
MarketData Providerのtimeout / partial failure / recovery観測をbackend完了gateで確認することである。UIの進捗表示は
backend contractが安定した後に行う。
