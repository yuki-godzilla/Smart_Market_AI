# Point-in-Time材料アーカイブ・長期Forecast信頼度 検証レポート

更新日: 2026-07-20

## 1. 結論

今回の変更では、実ニュース・IRを今後のpoint-in-time評価へ蓄積するlocal archiveと、LLM材料リスクを
価格中心値へ混ぜずconfidence上限・rangeだけでshadow比較する契約を実装した。

Forecastは20 / 40 / 60 / 80 / 100 / 120営業日へ評価を広げた。60日超の価格中心は、方向一致率だけを
見ると一定の情報を持つが、RMSEと60%想定range coverageが安定せず、中心予測の`low`を解除できない。
一方、Quantileモデル自身のorigin以前検証がmedium / highの長期caseは、実績方向一致率が80日59%、
100日57%、120日59%だった。このため、中心予測と方向判定のconfidenceを分離し、60日超120日以下では
中心を`low`に維持しながら、方向だけを条件付きで最大`medium`まで表示する。

## 2. 実装した材料アーカイブ

`backend/llm_factor/material_archive.py`に次を実装した。

- schema: `point-in-time-material-archive-v1`
- URL、title、短いsummary、source family / type、symbol、content hashを保存
- `published_at`、`available_at`、`first_archived_at`、`last_seen_at`を分離
- 同一recordはstable hashでdeduplicateし、観測回数と最初・最後の観測時刻を更新
- atomic replace、読み込み不能時のwarning、破損archiveの暗黙上書き禁止
- raw本文全量を既定保存せず、source traceに必要なmetadataと短いsummaryだけを保持
- archiveは共有market evidenceであり、user noteやcredentialを保存しない

本日、`7203.T`と`NVDA`を対象とした銘柄別取得と広域Google Newsを実行し、113件を初回保存した。
対象時点でEDINET / TDnet該当は0件、company IR 1件、銘柄別Google News 10件、Yahoo Finance 2件、
その他は広域ニュースsourceだった。これは収集動作と実source coverageの確認であり、113件の将来labelは
まだ成熟していない。

重要な因果境界は次のとおりである。

- 今日取得した過去記事も`first_archived_at=今日の実観測時刻`とする
- `first_archived_at > forecast origin`の材料は既存のpoint-in-time selectorが除外する
- dateしかないIRはintraday公開時刻を推測せず、実fetch時刻を`available_at`とする
- provider replayをlive observedと同じsealed evidenceとして扱わない

## 3. LLM材料リスクのshadow契約

`llm-material-risk-shadow-v1`はtyped output、citation、provider、model、prompt version、生成時刻を必須にした。
適用時も`center_return_adjustment=0`をschemaで固定し、次の変更しか許可しない。

| 条件 | confidence上限 | range倍率 | 中心return |
| --- | --- | ---: | ---: |
| valid citationなし / relevance不足 | 変更なし | 1.00 | 0 |
| adverse / uncertainty 65以上 | medium | 1.15 | 0 |
| adverse / uncertainty 80以上 | low | 1.25 | 0 |

`backend/llm_factor/material_shadow_evaluation.py`は、Forecast pointとsignalをsymbol / horizon / originで結び、
coverageだけでなく幅を罰するproper interval scoreで`without LLM`と`with LLM`を比較する。成熟case 100件未満は
必ず`insufficient_evidence`とし、100件以上でもinterval score 1%以上改善とcoverage維持を満たさない限り
runtime候補にしない。方向値と中心値は構造上不変である。

## 4. 長期Forecastバックテスト設計

### 4.1 Cohort

| Role | Cohort | 評価symbol | Origin / horizon | 備考 |
| --- | --- | ---: | ---: | --- |
| validation | Phase 34 validation | 21 | 63 | 価格不連続1symbol除外 |
| validation | Extended validation | 23 | 69 | symbol分離済み |
| audit | Phase 34 audit | 19 | 57 | symbol分離済み |
| audit | Extended audit | 23 | 69 | symbol分離済み |
| pooled validation | 2群 | 44 | 132 | horizonごと |
| pooled audit | 2群 | 42 | 126 | horizonごと |

直近750 bars、最大3 rolling origins、20 / 40 / 60 / 80 / 100 / 120日で、4 advanced adapter、
runtime consensus、regime-gated shadowを未来情報なしで再実行した。各adapterの内部validationにも
horizon相当のpurgeがある。

この実行中、metadata splitを指定してもOHLCV内の分割外symbolを読み込む既存dataset境界不備を検出した。
`backend/forecast/dataset.py`を、metadataに明示されたsymbolだけを読む契約へ修正し、誤った2実行を停止して
正しい21 / 19 symbolで再実行した。拡張群はOHLCV自体がsplit済みだったため影響しない。

### 4.2 Pooled結果

| Role | Horizon | N | Router RMSE | Zero RMSE | Direction | 60% range coverage | Mean width |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| validation | 20 | 132 | 0.0869 | 0.0841 | 54.55% | 47.73% | 0.1093 |
| audit | 20 | 126 | 0.0744 | 0.0729 | 50.79% | 53.97% | 0.0968 |
| validation | 40 | 132 | 0.1487 | 0.1237 | 39.39% | 39.39% | 0.1499 |
| audit | 40 | 126 | 0.1307 | 0.1023 | 46.03% | 46.03% | 0.1238 |
| validation | 60 | 132 | 0.2218 | 0.2053 | 47.73% | 32.58% | 0.1844 |
| audit | 60 | 126 | 0.1874 | 0.1643 | 45.24% | 36.51% | 0.1542 |
| validation | 80 | 132 | 0.2684 | 0.2742 | 56.06% | 33.33% | 0.2089 |
| audit | 80 | 126 | 0.1775 | 0.1721 | 57.14% | 40.48% | 0.1721 |
| validation | 100 | 132 | 0.3020 | 0.3011 | 55.30% | 30.30% | 0.2267 |
| audit | 100 | 126 | 0.1762 | 0.1640 | 57.94% | 36.51% | 0.1708 |
| validation | 120 | 132 | 0.3404 | 0.3254 | 55.30% | 35.61% | 0.2525 |
| audit | 120 | 126 | 0.2224 | 0.1950 | 57.14% | 37.30% | 0.1887 |

80日validationの中心だけはzero baselineより2.1%良いが、auditでは3.1%悪化した。100日、120日も
validation / auditを同時に改善しない。中心confidenceをmediumへ上げるgateは不通過である。

### 4.3 Range倍率のvalidation選択・audit確認

倍率候補`1.00 / 1.10 / 1.25 / 1.50 / 2.00`をvalidationだけでproper interval score最小にして、
auditへ再調整なしで適用した。3 horizonとも1.50が選ばれた。

| Horizon | validation coverage | audit coverage before | audit coverage after | audit interval score改善 | 判定 |
| ---: | ---: | ---: | ---: | ---: | --- |
| 80 | 50.76% | 40.48% | 58.73% | 0.06% | 1% gate未達 |
| 100 | 44.70% | 36.51% | 50.79% | 0.33% | 1% gate未達 |
| 120 | 47.73% | 37.30% | 55.56% | 0.72% | 1% gate未達 |

coverageだけは増えるが、幅の拡大を含むproper score改善が小さい。固定1.50倍をruntimeへ採用しない。

### 4.4 Subgroup

長期中心には複数のmaterial failureが残った。主なaudit例は次のとおりである。

- ETF 80日: zero baseline比RMSE 56.29%悪化（18点）
- ETF 100日: 20.65%悪化（18点）
- stock 120日: 14.12%悪化（108点）
- US 120日: 22.19%悪化（75点）
- downtrend 120日: 43.19%悪化、方向37.50%（24点）
- high volatility 120日: range coverage 27.78%（18点）

全体方向一致率だけで長期confidenceを一律mediumにすると、downtrendなどの弱点を隠すため不採用とする。

## 5. 役割別confidence

全6 horizon・4群のruntime consensus 1,548点を既存confidence別に見ると次のとおりだった。

| Confidence | N | RMSE | Zero RMSE | Direction | Range coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| high | 49 | 0.06 | 0.06 | 61% | 61% |
| medium | 177 | 0.11 | 0.09 | 53% | 42% |
| low | 1,322 | 0.22 | 0.21 | 51% | 38% |

長期Quantileのorigin以前validation confidenceを方向役へ使うと、medium / highをmediumへまとめた172点 / horizonの
実績方向一致率は80日59%、100日57%、120日59%だった。low 86点 / horizonは52%、56%、51%だった。

この結果から`role_separated_confidence_v1`を追加した。

- backward-compatibleな`confidence`は価格中心のconfidenceとして維持
- `center_confidence`: 60日超は引き続きlow
- `direction_confidence`: 61〜120日はQuantile内部confidenceがmedium / highの時だけmedium、残りlow
- 120日超は中心・方向ともlow
- Ranking scoreは引き続き保守的なcenter confidenceを使い、方向mediumだけで順位寄与を増やさない

## 6. 採否

| 対象 | 判定 |
| --- | --- |
| point-in-time材料archive | 採用。今後のreal evidenceを蓄積 |
| LLM confidence / range shadow evaluator | 採用。runtime未接続 |
| LLMによる価格中心値変更 | 不採用、schemaで0固定 |
| 長期中心confidence medium | 不採用、low維持 |
| 長期方向confidence medium | 条件付き採用、最大120日・内部検証medium以上のみ |
| 固定range 1.50倍 | 不採用、proper score 1% gate未達 |

## 7. 次の監査

1. 本日以降のarchiveを継続し、20 / 60 / 120日targetが成熟するまで保存する。
2. 100件以上の時点整合caseで、LLMなし / ありのinterval score、coverage、false positive、drawdown識別を比較する。
3. 新しい暦期間のForecast auditで、中心lowと方向mediumの分離が再現するか確認する。
4. 監査結果を見てLLM閾値、range倍率、confidence閾値を後付け変更しない。

SMAIの出力は投資判断支援情報であり、将来価格、利益、方向の実現を保証しない。
