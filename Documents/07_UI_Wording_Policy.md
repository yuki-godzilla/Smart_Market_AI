# UI 文言ポリシー

#### [BACK TO README](../README.md)

## Investment-Support Wording Guardrails / 2026-05-24

Smart Market AI の UI、レポート、説明文では、売買を指示する表現を避け、判断補助・確認候補・比較材料として表現します。

Avoid:

- `Buy`
- `Sell`
- `Strong Buy`
- `今すぐ購入`
- `売却推奨`
- `買うべき`
- `売るべき`
- `この銘柄がおすすめ`
- `安全な銘柄`
- `必ず上がる`

Prefer:

- `Candidate`
- `Watch`
- `Review`
- `Attractive`
- `Caution`
- `Further review`
- `確認候補`
- `比較候補`
- `深掘り候補`
- `注意して確認`
- `判断材料`
- `配分見直し候補`
- `review candidate`

Area-specific wording:

- Ranking は「おすすめ」ではなく、「候補探索」「比較」「screening」「深掘り候補の整理」として表現する。
- Investment Score は「売買判断」ではなく、「複数観点を統合した比較・分析用スコア」として表現する。
- Database Fit / Metadata Confidence / Data Quality は「投資魅力度」ではなく、「評価に使えるデータの充実度・信頼度」として表現する。
- Rebalance は「売買」ではなく、「配分見直し」「simulation」「review candidate」として表現する。
- Decision Report は「投資推奨書」ではなく、「ある時点の判断材料、根拠、不確実性、確認ポイントの保存・説明」として表現する。
- Research Evidence は「根拠」だが、確定情報や保証ではない。資料名、日付、source type、抜粋、信頼度、根拠不足 warning をできるだけ近くに表示する。
- Forecast は「将来の保証」ではなく、「baseline model による参考予測、不確実性、モデル間の見方」として表現する。
- Risk は「安全/危険の絶対判定」ではなく、「価格変動、制約違反、確認ポイント」として表現する。

## Current UI Wording Addendum / 2026-05-23

- Ranking tables should keep the supplemental note to a short sentence. Detailed decision-support wording belongs in the shared `銘柄データ` modal.
- Ranking dashboard labels may use `Screening Candidates`, `Comparison Candidates`, `Further Review Candidates`, `Top 10 Score Comparison`, and `Evaluation Confidence`; avoid labeling top rows as recommended securities.
- Ranking charts should explain that Investment Score and Evaluation Confidence are different concepts: one is a comparison score, the other is data reliability / coverage.
- Ranking chart descriptions should state what to compare, how to read quadrants, and what to be careful about, while avoiding buy/sell wording.
- Evaluation Confidence should be described as evaluation reliability / data coverage, not as a main attractiveness factor.
- Symbol Cockpit dashboard labels may use `Symbol Cockpit Summary`, `Analysis KPI`, `Score Breakdown`, `Selected Candidate`, and `Research Evidence Summary`; explain these as analysis / confirmation views rather than advice.
- Cockpit `Decision View` should be treated as a confirmation level, not a buy/sell direction.
- Cockpit chart copy should frame `Price & Forecast` as the main analysis view, then direct users to Score Breakdown for reasons and Data Details for verification.
- Overall UI tone should be Professional but Friendly: short labels, calm explanations, restrained dashboard wording, and no advice-like urgency.
- Badges should clarify state rather than imply action: `Review`, `Check data`, `High Confidence`, `Evidence`, `Context`, and similar neutral labels are preferred.
- Chart descriptions should help users decide what to inspect next, while keeping the message framed as comparison / confirmation support.
- UI captions should stay short. Long explanations, quadrant reading guides, raw reasons, and report text should move to help text, tooltip, expander, Preview / Raw tabs, or downloads.
- The shared symbol-detail modal may show score interpretation, caution, valuation, income, and next-action rows, but must not present buy/sell advice.
- Cockpit fetch results may show `投資判断メモ` that combines score, warnings, symbol-master data, and price trend into confirmation points.
- Decision Report Markdown should be Japanese-first: section titles, table headers, notes, and confirmation points should read as a user-facing report, while JSON may keep stable internal schema keys.
- Avoid table or modal layouts where long guidance text is clipped horizontally.

## 目的

Smart Market AI の UI、レポート、説明文で使う文言の方針をまとめます。

目的は、投資初心者にも読みやすく、かつ過度に保守的すぎない表現で、判断材料を自然に伝えることです。

## 基本方針

- 短く、具体的に、画面上で迷わない言葉を使う。
- 技術的な正確さは保ちつつ、最初に目に入る文言は人が読む言葉にする。
- モデル名、指標名、provider 名などの技術名は必要に応じて残す。
- 売買推奨ではなく、判断材料を整理する表現にする。
- 免責のような強い注意書きは、必要な場所にだけ置く。
- 同じ概念には同じ言葉を使い、画面ごとに言い換えすぎない。

## トーン

推奨:

- 落ち着いた、簡潔な説明
- 「比較する」「確認する」「参考にする」「整理する」
- 「今回の期間では」「このデータでは」など、評価対象を限定する表現

避ける:

- 「必ず」「安全」「儲かる」「買うべき」「売るべき」
- 過度に断定的な投資判断
- 毎回長い免責文を表示すること
- 技術用語だけで完結する説明

## 投資判断補助の言い方

UI 上では、売買判断そのものではなく、判断材料を比較する表現を使います。

推奨:

- `モデルの当たりやすさを比べます。`
- `今回の期間では、このモデルの誤差が最も小さいです。`
- `スコアと理由を確認できます。`
- `データ品質に注意が必要です。`

避ける:

- `この銘柄を買うべきです。`
- `この予測は正しいです。`
- `このモデルが最も優秀です。`
- `投資判断の責任は負いません。` を画面内で何度も繰り返すこと

## チャート凡例

モデル名は尊重し、凡例タイトルで意味を補います。

Forecast chart の推奨凡例:

```text
価格・モデル
実績価格
予測: 3日モメンタム
予測: 3日移動平均
予測: 直近値維持

実績/予測
実績
予測
```

方針:

- `価格・モデル`: 実績価格と予測モデルをまとめる凡例タイトル。
- `実績/予測`: 実績線と予測線の線種を説明する凡例タイトル。
- モデル名は `予測: <モデル名>` の形で残す。
- チャート上に長い説明テキストを重ねない。
- 予測境界は必要なら薄い縦線などの視覚的な補助に留める。

## 指標説明

指標説明は短くします。

推奨:

```text
誤差と方向一致率で、モデルの当たりやすさを比べます。
```

必要に応じて補足する場合:

```text
RMSE/MAE は予測誤差、方向一致率は値動きの向きが合った割合です。
```

避ける:

```text
RMSE/MAE は小さいほど良く、方向一致率は高いほど良い指標です。予測は投資判断の補助であり、売買推奨ではありません。
```

理由:

- 内容は正しいが、画面上では少し保守的で長い。
- 必要な注意は残しつつ、通常 UI では軽い説明に寄せる。

## UI ラベルの方針

- ボタンは操作を表す短い言葉にする。
- テーブル見出しは短くし、補足は caption や説明文へ逃がす。
- エラーは原因と次の行動が分かる文にする。
- スコアや警告は、理由を日本語で添える。
- 英語の技術識別子は、必要な場合だけそのまま表示する。

## 例

| 用途 | 推奨 | 避ける |
| --- | --- | --- |
| モデル比較 | `今回の期間では「予測: 3日移動平均」の誤差が最も小さいです。` | `最も優秀なモデルです。` |
| 指標説明 | `誤差と方向一致率で、モデルの当たりやすさを比べます。` | `投資判断の補助であり、売買推奨ではありません。` を毎回表示 |
| データ品質 | `一部の特徴量が不足しています。` | `データが不完全です。` だけで終わる |
| 予測 | `予測: 直近値維持` | `naive` だけ |


## Research RAG / 根拠表示の文言

Research RAG では、資料から読み取れる判断材料と根拠を短く示します。
「AIが判断した」よりも、「この資料ではこう読める」という表現に寄せます。

推奨:

- `この資料では、配当方針を安定的に維持する姿勢が読み取れます。`
- `中期経営計画では、海外事業を成長領域として示しています。`
- `事業リスクとして、為替や原材料価格の影響が挙げられています。`
- `根拠資料と公開日を確認できます。`
- `資料が少ないため、Research Score の信頼度は控えめです。`

避ける:

- `この会社は長期投資に最適です。`
- `IR資料から買い判断です。`
- `このリスクは問題ありません。`
- 根拠資料なしで断定する説明。

根拠表示では、可能な限り以下を近くに表示します。

- 資料名
- 公開日
- ページ番号または section
- 抜粋または短い要約
- 情報の鮮度
- Research data quality warning


## 現在の主要 UI ラベル（2026-05-19）

現在の Streamlit UI では、以下の画面名・表現を標準として扱います。

| 表示 | 意味 | 方針 |
| --- | --- | --- |
| `銘柄コックピット` | 1銘柄の深掘り | 価格・予測・スコア・注意点を読む画面 |
| `銘柄ランキング` | 複数銘柄比較 | 買う銘柄の確定ではなく、深掘り候補の整理 |
| `並べ替え条件` | 銘柄ランキングの表示順 | 候補を絞らず、スコアの並び順を変える設定。選択中の条件ごとに、重視する指標と確認すべきリスクを help / caption で説明する |
| `時価総額` | provider fetch 前の会社規模 | `大型` だけで終えず、日本株/米国株の金額目安を選択肢か help で示す |
| `配当カテゴリ` | provider fetch 前の配当分類 | 0%、0%超〜3%未満、3%以上の利回り目安を表示し、連続増配候補は metadata 指定であることを補足する |
| `市場感応度（β）` | provider fetch 前の値動き目安 | β 0.8未満 / 0.8〜1.2 / 1.2超の目安を help で示し、`低め` のような曖昧な表示だけにしない |
| `Risk` / `リスクスコア` | ランキング後の確認材料 | 取得期間の値動きなどを、候補取得後に確認する |
| `Rebalance Cockpit` | 保有と目標配分の確認 | 現在資産 -> 目標配分 -> 必要な売買 -> Risk 判定 |
| `Investment Score` | 投資判断補助スコア | 売買推奨ではなく、複数材料を統合した参考値 |
| `Forecast agreement` | 予測モデルの見方の近さ | 「モデルの見方が近い / 割れている」と説明する |
| `Data quality` | データ品質 | 欠損・履歴不足は warning として明示する |

Investment Score、Forecast、Ranking の周辺では、断定的な「買い」「売り」ではなく、
「候補」「確認材料」「注意点」「深掘り」などの表現を優先します。

## 更新ルール

UI 文言、レポート文言、初心者向け説明を大きく変える場合は、この文書も更新します。

実装で使う文言とこの文書がずれた場合は、実際の UI を確認し、自然な方に揃えます。
