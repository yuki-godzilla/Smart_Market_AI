# 41 Point-in-Time LLM材料・銘柄横断予測 改善設計

更新日: 2026-07-20

## 1. 結論

予測精度改善の次候補は、LLMに将来価格を自由文で生成させる方式ではない。次の2経路を分離する。

1. **価格経路**: 現行Consensusと固定保守anchorを基準に、同一時点の銘柄横断関係を軽量GBDTで評価する。
2. **材料経路**: 予測時点で実在・保存済みだったニュース、開示、IRだけからLLM event特徴量を作り、
   市場控除後の実現インパクトで情報源の有用性を事後更新する。

価格経路の初回監査は不採用となった。60銘柄・1,440点で調整し、完全非重複52銘柄・1,248点で
監査した横断GBDTは、Consensus比では20日4.37%、60日10.27%改善したが、より強い固定anchor比では
20日1.96%、60日1.31%悪化した。別の非重複39銘柄・936点でもanchor比20日2.60%、60日2.68%
悪化し、失敗が再現した。したがってForecast、Cockpit、Ranking、Investment Scoreは変更しない。

材料経路は因果契約、Source Memory、市場残差ラベルまで実装した。ただし実ニュース・開示の
point-in-time archiveがまだ存在しないため、LLMあり/なしの実市場精度比較は未実施である。既存の
synthetic/static fixtureを実精度の代用にしない。

## 2. 最新研究から採用した要点

| 研究 | 公開時点 | SMAIで採用する要点 | 採用しない短絡 |
| --- | --- | --- | --- |
| [Point-in-Time Financial RAG with Frozen LLMs and Market-Feedback Adaptive Retrieval](https://arxiv.org/html/2605.31201v2) | arXiv v2, 2026-06-21 | 予測時点で存在した証拠だけを検索、EDGAR等は受付時刻を使用、event anchor自身・重複・未来資料を除外、Source Memoryをbounded rerankに限定、市場残差で情報源を評価 | LLMの文章評価をそのまま価格returnへ加算 |
| [FinTSB: Comprehensive and Practical Benchmark for Financial Time Series Forecasting](https://arxiv.org/html/2502.18834v3) | arXiv v3, 2026-06-01 | 時系列と銘柄横断関係を併用、RMSE・ranking・portfolioを分離評価、XGBoost/LightGBM系の計算効率、単一モデル万能論を避ける | deep / foundation modelなら常にtreeや統計modelより良いという前提 |
| [Financial Sentiment Analysis in the Era of LLMs](https://aclanthology.org/2026.evaleval-1.4/) | ACL 2026 | 金融文脈固有の評価、モデル差・prompt差を固定して比較、一般感情と市場インパクトを分離 | positive/negative感情を将来騰落の正解ラベルにすること |
| [Reverso: Efficient Foundation Model for Time Series Forecasting](https://arxiv.org/html/2602.17634v1) | arXiv, 2026 | foundation model比較では精度だけでなく速度・memory・事前学習範囲を監査 | local-first SMAIへ大型modelを先に常駐導入 |
| [R&D-Agent-Quant](https://arxiv.org/html/2505.15155v2) | arXiv v2, 2025 | 仮説、実験、失敗、再試験をartifactとして残す研究loop | audit結果を見て同じauditへ自動再調整 |
| [Are Language Models Actually Useful for Time Series Forecasting?](https://arxiv.org/html/2406.16964) | arXiv, 2024 | LLM部分を外すablationと単純baseline比較を必須化 | LLMが入っていること自体を追加価値とみなすこと |
| [Conformal Prediction for Time Series with Change Points](https://arxiv.org/abs/2509.02844) | arXiv, 2025 | regime change時のcoverage低下を別途監視し、将来の区間校正候補とする | 非定常下でも固定幅の信頼区間を保証と表示 |

論文は査読済み・preprint・版更新中のものが混在する。実装根拠は論文タイトルの新しさではなく、
SMAIの因果境界、local-first、計算量、再現可能性に適合する部分に限定した。

## 3. 全体構成

```text
ニュース / TDnet / EDINET / 企業IR
  -> 公開時刻・利用可能時刻・保存時刻をUTCで記録
  -> eventを最初の取引判断時刻へ割当
  -> 未来 / 後日保存 / anchor自身 / 重複 / 別銘柄を除外
  -> static relevance上位20件
  -> bounded Source Memory rerank
  -> LLM readerへ最大5件、typed label + citation IDs
  -> horizon満了後に市場残差labelを確定
  -> 引用が有効なsource familyだけSource Memory更新
  -> shadow評価

現行Forecast群
  -> 固定保守anchor
  -> 同一originの予測値・乖離・分散・横断percentile rank
  -> 小規模HistGradientBoosting residual
  -> 古い70% originでfit / 新しい30% originでgate
  -> 不通過ならanchorへ完全fallback
  -> symbol非重複audit
```

2経路は評価段階では融合しない。LLM材料経路が先に目指すのはconfidence上限またはquantile rangeの
拡幅であり、価格中心値の補正は別の厳しいgateとする。

## 4. Point-in-Time材料契約

### 4.1 時刻

- `occurred_at`: eventが発生・公表された時刻。
- `decision_at`: SMAIがそのeventを利用できる最初の取引判断時刻。
- `published_at`: 人向け表示の公表時刻。
- `available_at`: 配信元で機械的に利用可能になった時刻。EDINET/EDGAR系は提出日ではなく受付時刻を使う。
- `archived_at`: SMAIのarchiveへ実際に保存した時刻。

資料は`available_at <= decision_at`かつ`archived_at <= decision_at`の場合だけpoint-in-time証拠とする。
後日取得した過去記事は参考調査には使えても、過去予測の精度検証には使わない。全時刻はtimezone-aware
で保存し、日付だけのsource metadataを予測特徴量へ使わない。

通常取引中の材料は同日引け後の判断時刻、引け後・休日の材料は次の取引判断時刻へ割り当てる。
取引所calendar自体は呼び出し側が供給し、単純な暦日加算を行わない。

### 4.2 event type

`earnings_guidance`、`legal_regulatory`、`capital_transactions`、
`management_operations`、`other_mixed`の5分類とする。event anchor本文だけを決定論的cue countへ渡し、
同数または該当なしは`other_mixed`とする。取得した資料、未来return、Source Memoryを分類入力へ入れない。

### 4.3 evidence control

- static retrieval候補は最大20件、LLM readerへ渡すのは最大5件。
- anchor URL・同一title・正規化後の重複URLを除外する。
- 別銘柄はpeer contextと明示された資料だけ許可し、候補poolの20%以下に制限する。
- Source Memoryはstatic relevanceを置換せず、最大`lambda * delta = 0.30 * 0.20 = 0.06`だけ加減する。
- 不明なcitation ID、候補から除外済みのcitation、citationなしの応答はmemoryを更新しない。

### 4.4 市場残差label

LLMのpositive / negative感情ではなく、horizon別の市場控除後returnを正解とする。

```text
epsilon_h = stock_return_h - (alpha_h + beta_h * benchmark_return_h)
z_h       = epsilon_h / sigma_h

label = +1  if z_h > 1
         0  if -1 <= z_h <= 1
        -1  if z_h < -1
```

`alpha_h`と`beta_h`は、予測originの20取引日前で終わる過去252取引日のoverlapping horizon returnから
推定し、最低120標本を要求する。targetが満了するまではlabelを返さず、満了後もその時点以後の
Source Memory更新にしか使わない。

### 4.5 Source Memory

cell keyは`(source_family, event_type, horizon)`。正解時はpositive mass、不正解時はnegative massへ、
有効引用のsource family数で等分したcreditを加える。class不均衡がある場合は
`w_y = 1 / (3 * pi_y)`を使う。

```text
utility     = (positive_mass + 1) / (positive_mass + negative_mass + 2)
reliability = n / (n + 30)
adjustment  = 0.30 * clip(reliability * (utility - 0.5), -0.20, 0.20)
```

neutral prior 0.5と`kappa=30`で少数例を強く縮小する。memoryは明示snapshotとして入出力し、hidden
global stateを持たせない。

## 5. 銘柄横断残差GBDT

### 5.1 目的と特徴量

過去の残差Ridgeが見ていなかった同一originの横断関係だけを追加した。入力は予測時点で確定している。

- 固定anchor return
- Consensus / advanced quantile / moving-averageのanchor差
- 3予測のdispersion
- 上記5値の同一origin・horizon内percentile rank
- market、asset type、regimeのone-hot

targetは`actual_return - anchor_return`。HistGradientBoostingはlearning rate 0.05、100 iterations、
最大7 leaves、L2=10、min leaf 20へ事前固定した。補正はfit残差絶対値90%点または25%の小さい方、
最終returnは絶対75%で制限する。方向headはConsensusのまま保持する。

### 5.2 因果gate

- 各監査originで`target_at <= origin_at`のdevelopment historyだけを使う。
- 20日・60日を分離する。
- 同一originで5銘柄未満ならanchorへfallbackする。
- 利用可能originの古い70%でfit、新しい30%で固定anchor比1%以上改善しなければfallbackする。
- 外側auditではConsensus比・anchor比とも1%以上、補正採用点だけでもanchor比1%以上を要求する。
- market / asset type / regime / periodで相対10%超かつ絶対RMSE 0.005超の劣化を禁止する。
- 補正採用率50%以上を要求する。

### 5.3 horizon別モデルルーター

予測期間に応じた使い分けは採用候補とする。ただし、予測ごとに都合の良いmodelを選ぶ学習routerでは
なく、developmentで決めた`horizon policy`を凍結して別期間・別symbolへ適用する決定論的routerとする。

| 役割 | 20日候補 | 60日候補 | 120日以上候補 |
| --- | --- | --- | --- |
| price center | `advanced_quantile` / `moving_average_3`寄りの保守blendをshadow継続 | `moving_average_3`中心をshadow継続 | 点予測を未採用。scenario / broad rangeを先に評価 |
| direction | 現行advanced Consensus | 現行advanced Consensus。ただしconfidenceを20日と別校正 | 方向精度の別監査が揃うまで`unknown`を許容 |
| uncertainty | `advanced_quantile` range | horizon別`advanced_quantile` range | conformal / regime-aware coverageを新規評価 |
| LLM材料 | 短期eventのconfidence / adverse risk | 持続性・guidanceのconfidence / range | 数値価格ではなく構造変化・scenario材料 |

選択指標も役割別にする。price centerはRMSE / MAE、directionはbalanced accuracy / Brier、rangeは
coverage / width、Ranking用途はrank IC / Top-k liftを使い、1つの平均scoreへ混ぜない。20日で良い
modelを60日へ自動流用せず、Source Memoryも`(source_family, event_type, horizon)`で分ける。

現時点では固定保守profile自体が過去年代のETF / downtrend subgroup gateに失敗しているため、
このrouterもruntime未採用である。横断GBDTは20日・60日とも候補集合から外す。次の実装はpolicy
contractとhorizon別evaluation reportまでに限定し、UI / Forecast値の切替は別監査後とする。

## 6. 実測結果

### 6.1 完全非重複52銘柄監査

| Horizon | Samples | Consensus RMSE | 固定anchor RMSE | 横断GBDT RMSE | vs Consensus | vs anchor |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20日 | 624 | 0.120205 | **0.112739** | 0.114947 | +4.37% | **-1.96%** |
| 60日 | 624 | 0.218857 | **0.193853** | 0.196388 | +10.27% | **-1.31%** |

補正採用は232 / 1,248点、18.59%。採用点だけではanchor比20日6.90%、60日19.20%悪化した。
20日downtrend 28点も7.88%悪化した。overall、selected-only、coverageの全gateで不通過である。

### 6.2 別の非重複39銘柄参考再現

| Horizon | Samples | Consensus RMSE | 固定anchor RMSE | 横断GBDT RMSE | vs Consensus | vs anchor |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20日 | 468 | 0.084843 | **0.077965** | 0.079989 | +5.72% | **-2.60%** |
| 60日 | 468 | **0.158364** | 0.154464 | 0.158597 | -0.15% | **-2.68%** |

補正採用は215 / 936点、22.97%。採用点だけではanchor比20日7.52%、60日16.47%悪化し、
20日downtrendは21.74%、2019年以前は10.28%悪化した。初回監査の失敗方向と一致する。

### 6.3 判断

非線形化と横断rankを加えても、内部時系列gateで選ばれた補正関係は別銘柄へ一般化しなかった。
tree深さ、leaf数、最低標本数、採用率を今回の結果に合わせて変更しない。価格中心値の次候補としては
不採用とし、現行runtimeを維持する。

## 7. LLM材料経路の採用gate

実archiveが揃った後、同じevent predictionを`static retrieval`と`static + Source Memory`で
prequential比較する。horizon満了後にしかmemoryを更新しない。

最低限、次をvalidationとsymbol非重複auditの両方で満たす。

- 3-class macro F1、balanced accuracy、log loss、Brier scoreを確認する。
- adverse event / 将来drawdownのAUROCとfalse-positive削減を確認する。
- confidence calibrationをECEまたはreliability tableで確認する。
- Source Memoryありのablationがstatic retrievalを改善し、market / asset / event typeで重大劣化しない。
- citation validity 100%、future evidence 0件、target未満了update 0件を要求する。
- LLM timeout、schema failure、stale/insufficient evidenceではLLM寄与0へfallbackする。
- 最初のruntime候補はconfidence cap / range wideningだけ。中心return加算、Ranking順位補正はfalseのまま。

## 8. 実装対応

- `backend/llm_factor/point_in_time.py`
  - timezone-aware event / evidence contract
  - event assignmentとdeterministic event type
  - future / late archive / duplicate / unrelated / peer cap
  - causal market-residual label
  - bounded Source Memory update / rerank
- `backend/forecast/cross_sectional_residual.py`
  - 同一originのcross-sectional feature
  - causal temporal fit / validation gate
  - GBDT residual correctionとfallback
  - overall / subgroup / selected-only adoption gate
- `tools/evaluate_cross_sectional_residual_forecast.py`
  - symbol非重複監査runner
  - manifest、metrics、predictions、decisions、Markdown report
- `tests/test_point_in_time_llm_events.py`
- `tests/test_cross_sectional_residual_forecast.py`

## 9. 次の作業

1. TDnet、EDINET、企業IR、ニュースの新規取得分からpoint-in-time archiveを開始する。
2. `available_at`の根拠がない過去資料は過去精度検証から除外する。
3. archiveにevent prediction、citation IDs、model、prompt version、source hashを保存する。
4. 20日・60日target満了を待ってprequential Source Memory ablationを実行する。
5. gate通過時だけ、上位候補のconfidence cap / quantile range拡幅をshadow接続する。
6. price / direction / uncertainty / materialを分けたhorizon policy contractを評価専用で追加する。
7. 価格中心値は後日の新暦期間で固定anchorを再監査し、今回の横断GBDTは再調整しない。

この順序では、最新研究を導入したことではなく、未来情報を使わず既存baselineより実際に良いことを
採用条件にできる。
