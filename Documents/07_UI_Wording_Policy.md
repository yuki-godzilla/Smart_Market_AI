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
- Direction Signal は「上がる銘柄/下がる銘柄」ではなく、「上昇気配」「下降警戒」「深掘り候補」として表現する。ランキングと銘柄コックピットの主表示は `上昇気配` / `下降警戒` の2指標に絞る。
- Forecast agreement は主表示ではなく、モデル一致度の補助指標として扱う。
- Risk は「安全/危険の絶対判定」ではなく、「価格変動、制約違反、確認ポイント」として表現する。

## Current UI Wording Addendum / 2026-05-23

- Ranking tables should keep the supplemental note to a short sentence. Detailed decision-support wording belongs in the shared `銘柄データ` modal.
- Ranking dashboard labels may use `Screening Candidates`, `Comparison Candidates`, `Further Review Candidates`, `Top 10 Score Comparison`, and `Evaluation Confidence`; avoid labeling top rows as recommended securities.
- Ranking charts should explain that Investment Score and Evaluation Confidence are different concepts: one is a comparison score, the other is data reliability / coverage.
- Ranking chart descriptions should state what to compare, how to read quadrants, and what to be careful about, while avoiding buy/sell wording.
- Evaluation Confidence should be described as evaluation reliability / data coverage, not as a main attractiveness factor.
- Symbol Cockpit dashboard labels may use `Symbol Cockpit Summary`, `Analysis KPI`, `Score Breakdown`, `Selected Candidate`, and `Research Evidence Summary`; explain these as analysis / confirmation views rather than advice.
- Cockpit `Decision View` should be treated as a confirmation level, not a buy/sell direction.
- Cockpit score cards should keep the visible caption focused on the current value reading, such as `今回: 中立圏` or `今回: 確認優先`. Metric definitions and calculation notes should move to a `?` help tooltip beside the card label.
- Cockpit chart copy should frame `Price & Forecast` as the main analysis view, then direct users to Score Breakdown for reasons and Data Details for verification.
- Cockpit `SMAI Insight` should describe the actual state shown by the numbers: dominance, conflict, neutral state, model split, and forecast spread. Avoid one generic balance message when one side is clearly higher.
- Cockpit tables should use `確認ポイント` for the next verification lens, not for repeating metric definitions. When space is available, mention the actual value band and what to compare next.
- Avoid repeating the same score as multiple adjacent cards. If `Analysis KPI` already shows a score, later sections should summarize or interpret it rather than carding it again.
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

Research RAG では、外部の最新IR・開示・ニュース・provider evidence から読み取れる判断材料と根拠を短く示します。local 登録資料は tests / archive / fallback として扱い、通常ユーザー導線では外部 source の鮮度、provider、公開日、取得日時、URL を近くに示します。
「AIが判断した」よりも、「この資料ではこう読める」という表現に寄せます。
ニュースURL表示は `外部参照ソース` と詳細データに実装済みです。`最新ニュース・開示サマリー` 周辺では、URL付きニュース・開示がある場合は `ニュース・開示の出典を表示（URL付きN件）` を初期展開して確認できるようにし、ニュース専用URLが無い場合も外部参照ソース側に公式資料・provider URLがある可能性を案内します。

推奨:

- `この資料では、配当方針を安定的に維持する姿勢が読み取れます。`
- `中期経営計画では、海外事業を成長領域として示しています。`
- `事業リスクとして、為替や原材料価格の影響が挙げられています。`
- `根拠資料と公開日を確認できます。`
- `ニュース・開示の出典を表示（URL付きN件）`
- `ニュース専用のURL付き根拠は見つかりませんでした。関連する公式開示・企業IR・provider情報は外部参照ソースも確認してください。`
- `ニュース専用のURL付き根拠は見つかりませんでしたが、公式資料・企業IR・provider情報のURLは上の「ニュース・開示の出典」または外部参照ソースで確認できます。`
- `外部参照ソースにURL付きの公式資料・provider情報があります。`
- `資料が少ないため、Research Score の信頼度は控えめです。`
- `Research Score は根拠資料の充実度・鮮度・信頼度を整理する参考スコアです。売買推奨ではありません。`

避ける:

- `この会社は長期投資に最適です。`
- `IR資料から買い判断です。`
- `このリスクは問題ありません。`
- `ニュースURL表示は未実装です。`
- `URLはありません。`
- `情報が存在しません。`
- 根拠資料なしで断定する説明。

根拠表示では、可能な限り以下を近くに表示します。

- 資料名
- 公開日
- ページ番号または section
- 抜粋または短い要約
- 情報の鮮度
- Research data quality warning

### ResearchBrief / ローカルAI整理メモ

Research Summary は、生データ一覧ではなく「読める投資調査メモ」として表示します。外部LLMを使わない段階では、local rule-based `ResearchBrief` に変換してから UI に出します。

表示順の推奨:

1. `AI整理メモ`
2. `読み方サマリー`
3. `確認ポイント`
4. `定量指標`
5. `確認不足`
6. `次に確認すべき資料`
7. `出典カードを表示`
8. `ニュース・開示の出典を表示`
9. `Research Score（根拠資料の確認材料）を表示`
10. `外部参照ソースを表示`
11. `詳細データ`

主表示が答える問い:

- この会社は何をしている会社か。
- どの公式資料、IR、TDnet、ニュース、provider 情報を確認したか。
- 売上高、営業利益、純利益、EPS、配当、PER、PBR、ROE などの主要指標は確認できたか。
- 良材料候補と注意材料候補は何か。
- まだ公式資料で確認できていないことは何か。
- 次にどの資料を見ればよいか。

表示ルール:

- `AI整理メモ` は通常の表ではなく、調査メモの入口として目立つカードにする。
- `売買推奨ではありません` と不足指標の有無はメモの近くにバッジで表示する。抽出指標数、出典カード数、Research Score は主表示ではなく折りたたみ側に下げる。
- Research Evidence の上部操作カードは `AI調査ステータス` のような取得管理表示ではなく、`AI調査でわかったこと` として `事業`、`確認済み`、`次に見る` の3行で表示する。
- `資料n件`、`根拠n件`、`出典カードn件` は補助情報に留め、主表示の本文には事業概要、確認済みIR / 公式資料、主要指標、直近イベントなどの fact を置く。
- provider-only の情報は `外部データ由来では` と明示し、公式IR、TDnet、EDINET、企業IRと同じ信頼度に見せない。
- `読み方サマリー` は `確認できたこと`、`注意して見ること`、`まだ足りないこと`、`次にやること` の4観点に絞る。詳細な根拠リストではなく、最初に読む順番を示す。
- `確認ポイント` は `会社概要`、`確認できた事実`、`公式資料で未確認` の3ブロックを基本にする。長い provider text、raw fields、件数中心の表示を初期表示に出さない。
- 初期表示では `外部provider` ではなく `外部データ`、`情報源信頼度: 中` ではなく `補助情報として確認` のような自然な表現を使う。詳細データや出典カードでは、必要に応じて source type / confidence を表示する。
- `良材料候補` / `注意材料候補` は詳細側で確認する材料とし、主表示では件数ではなく、実際に確認できた事実や未確認項目に言い換える。
- ニュース未取得、URLなし、資料不足、低信頼などは `注意材料候補` ではなく `確認不足` に寄せる。
- `定量指標` は source type と confidence が見える小カードで表示し、取得できない主要指標は `確認不足` の警告パネルにまとめる。確認不足では `まだ確認できていない数値` と書き、悪材料ではなく追加確認項目であることを示す。
- `出典カード`、`Research Score（根拠資料の確認材料）`、`外部参照ソース` は折りたたみ表示にして、score や forecast と区別して読む文脈にする。Research Score の折りたたみ内には、読み方、要約、観点別内訳、注意点をまとめる。

推奨表現:

- `現時点で確認できた情報`
- `良材料候補`
- `注意材料候補`
- `公式資料による裏取りが必要です。`
- `この指標は外部データ由来の補助情報です。`
- `この confidence は情報源の信頼度であり、投資判断の正しさではありません。`

避ける表現:

- `買い材料です`
- `割安です`
- `成長確定です`
- `リスクはありません`
- `AIが投資判断しました`

通常表示で避ける provider raw fields:

- `Provider Symbol`
- `Quote Type`
- `Exchange`
- `Currency`
- raw `Sector` / `Industry`
- provider field dump

これらは必要な場合だけ `詳細データ` に残します。


## 現在の主要 UI ラベル（2026-05-19）

現在の Streamlit UI では、以下の画面名・表現を標準として扱います。

| 表示 | 意味 | 方針 |
| --- | --- | --- |
| `銘柄コックピット` | 1銘柄の深掘り | 価格・予測・スコア・注意点を読む画面 |
| `銘柄ランキング` | 複数銘柄比較 | 買う銘柄の確定ではなく、深掘り候補の整理 |
| `並べ替え条件` | 銘柄ランキングの表示順 | 候補を絞らず、スコアの並び順を変える設定。選択中の条件ごとに、重視する指標と確認すべきリスクを help / caption で説明する |
| `時価総額` | provider fetch 前の会社規模 | `大型` だけで終えず、日本株/米国株の金額目安を選択肢か help で示す |
| `配当/分配金カテゴリ` | provider fetch 前の配当・分配金分類 | 0%、0%超〜3%未満、3%以上の利回り目安を表示し、連続増配候補は metadata 指定であることを補足する |
| `市場感応度（β）` | provider fetch 前の値動き目安 | β 0.8未満 / 0.8〜1.2 / 1.2超の目安を help で示し、`低め` のような曖昧な表示だけにしない |
| `Risk` / `リスクスコア` | ランキング後の確認材料 | 取得期間の値動きなどを、候補取得後に確認する |
| `Rebalance Cockpit` | 保有と目標配分の確認 | 現在資産 -> 目標配分 -> 必要な売買 -> Risk 判定 |
| `Investment Score` | 投資判断補助スコア | 売買推奨ではなく、複数材料を統合した参考値 |
| `Research Score` / `根拠スコア` | 根拠資料の充実度・鮮度・信頼度を整理する参考スコア | 良い銘柄・買い候補の点数ではなく、資料に基づく確認材料のそろい具合として説明する。既定では Investment Score やランキング順位を変えない |
| `Direction Signal` | `上昇気配` / `下降警戒` の2指標で深掘り候補を整理する考え方 | 新しい方向系の公開指標を増やさず、売買推奨ではなく比較・確認の優先度として説明する |
| `上昇気配` | 予測エッジ、モデル別方向エッジ、価格モメンタム、トレンド確認を統合した補助指標 | 「上がる」と断定せず、上向きシグナルとして説明する |
| `下降警戒` | 下向きの予測エッジ、モデル別方向エッジ、価格モメンタム、トレンド確認を統合した補助指標 | 売り推奨ではなく、リスク確認候補として説明する |
| `Forecast agreement` / `モデル一致度` | 予測モデルの見方の近さ | 主表示ではなく補助指標として、「モデルの見方が近い / 割れている」と説明する |
| `Data quality` | データ品質 | 欠損・履歴不足は warning として明示する |

Investment Score、Forecast、Ranking の周辺では、断定的な「買い」「売り」ではなく、
「候補」「確認材料」「注意点」「深掘り」などの表現を優先します。

## 横断 UI 文言テーブル / 2026-05-27

SMAI の初期表示は日本語中心にし、英語の技術名や内部キーは詳細表示、ダウンロード、または括弧内に寄せます。
通常ユーザーが最初に見る画面では、結論、要約、重要指標、注意点、根拠、次に確認することを優先します。

### 共通 UI 文言

| 用途 | 推奨文言 | 避けたい文言 | 備考 |
| --- | --- | --- | --- |
| データ取得元 | `データ取得元` | `Provider` | 詳細では provider 名自体は残してよい |
| 現在値 | `現在値` | `Quote` | 詳細データでのみ Quote を補足してよい |
| 価格データ | `価格データ` | `OHLCV` | 初期表示では OHLCV を見出しにしない |
| 特徴量 | `特徴量データ` | `Feature Snapshot` | 詳細データに寄せる |
| 根拠 | `根拠資料` | `Research Evidence` | 画面見出しは日本語中心 |
| 投資スコア | `投資スコア` | `Investment Score` | 内部キー・CSV列名は維持してよい |
| データ信頼度 | `データ信頼度` | `Evaluation Confidence` / `Data Confidence` | 投資魅力度と混同させない |
| リスク | `リスク確認` | `Risk` | 絶対的な安全/危険判定にしない |
| 詳細 | `詳細データを表示` | `raw data` / `debug` | 初期表示では控えめにする |

### ボタン文言

| 用途 | 推奨文言 |
| --- | --- |
| データ取得 | `データを取得` |
| ランキング | `ランキングを作成` |
| 銘柄詳細 | `この銘柄を詳しく見る` / `銘柄データを見る` |
| AI調査 | `AI調査を更新` |
| レポート | `レポートを作成` / `レポートを表示` |
| ダウンロード | `CSVをダウンロード` / `JSONをダウンロード` / `レポート一式ZIPをダウンロード` |
| 条件変更 | `条件を変更` / `条件をリセット` |

主操作は primary button、副操作や保存操作は secondary button、download button、または expander 内に置きます。Research Evidence の操作カードは `AI調査を更新` だけを常時表示し、ニュース再取得・CSV・詳細展開のような低頻度操作は主導線に並べません。

### 空状態・取得中・エラー文言

| 状態 | 推奨文言 |
| --- | --- |
| 銘柄未選択 | `銘柄を選択すると、分析結果を表示できます。` |
| データ未取得 | `データはまだ取得されていません。条件を指定してデータを取得してください。` |
| ランキング未作成 | `ランキングはまだ作成されていません。条件を指定して作成してください。` |
| 投資スコアなし | `投資スコアはまだありません。` |
| 予測なし | `予測サマリーはまだありません。` |
| チャートなし | `チャートに表示できるデータがありません。` |
| 根拠資料なし | `根拠資料はまだ取得されていません。AI調査を更新すると、関連ニュースや外部情報を確認できます。` |
| レポートなし | `投資判断レポートはまだ作成されていません。` |
| データ取得中 | `価格データを取得しています。` |
| ランキング作成中 | `条件に合う銘柄を整理しています。` |
| AI調査中 | `関連ニュースと外部情報を調査しています。取得には少し時間がかかる場合があります。` |
| 取得失敗 | `データ取得に失敗しました。条件や取得元を確認してください。` |
| 銘柄未選択エラー | `対象の銘柄を1件以上選んでください。` |

### 投資判断・評価文言

| 現在/内部的な表現 | 推奨文言 |
| --- | --- |
| `見方` | `総合評価` |
| `強め` | `前向きに確認` |
| `バランス型` | `中立〜やや前向き` |
| `注意して確認` | `慎重に確認` |
| `弱め` | `慎重寄り` |

避ける: `買いです`、`売りです`、`必ず上がります`、`投資すべきです`、`安全です`。
使う: `判断材料として確認してください`、`短期判断では注意が必要です`、`詳しく確認する候補です`。

### データ取得・データ品質文言

取得元、基準日、公開日、取得日時、データ品質、欠損、鮮度を区別します。
`metadata`、`provider response`、`cache key`、`backend`、`query` は初期表示に出しすぎず、`取得元データを表示` や `詳細データを表示` に格納します。

### ランキング・候補選定文言

`Ranking` は `ランキング`、`Candidate` は `候補銘柄`、`Top picks` は `注目候補`、`Open in cockpit` は `この銘柄を詳しく見る` とします。
ランキングは売買推奨ではなく、詳しく確認したい候補の整理として表現します。

### 銘柄詳細・コックピット文言

銘柄コックピットは、`価格・予測・投資スコア・根拠資料を1画面で確認する分析ビュー` として説明します。
`Provider`、`OHLCV`、`Feature Snapshot` は初期表示から外し、`詳細データ` に寄せます。

### 価格・予測文言

`Price & Forecast` は `価格・予測`、`Forecast Summary` は `予測サマリー`、`Forecast Metrics` は `予測精度`、`Actual price` は `実績価格`、`Predicted price` は `予測価格` とします。
予測は将来保証ではなく、モデル間の見方や短期的な方向感を確認する補助材料として扱います。

### スコア・評価内訳文言

`Score Breakdown` は `評価の内訳`、`Weight` は `重み`、`Contribution` は `寄与度`、`Factor` は `評価項目`、`Reason` は `理由` とします。
スコアは単独で売買判断に使わず、内訳、データ品質、根拠資料と合わせて表示します。

### RAG / Research Evidence / 根拠資料文言

`RAG` は `AI調査`、`Research Evidence` は `根拠資料`、`Evidence count` は `根拠件数`、`Source count` は `出典数`、`Latest published` は `最新公開日`、`Investment impact` は `投資判断への影響` とします。
根拠資料はスコア算出そのものではなく、投資判断の背景を確認する参考情報です。
Research Score / 根拠スコアを表示する場合も、資料の多さ・鮮度・信頼度の整理であり、企業価値や売買判断を保証する点数ではないことを近くに示します。

### 投資ニュース文言

`Market News` は `投資ニュース`、`Recent News` は `関連ニュース`、`Source` は `出典`、`Published` は `公開日`、`Sentiment` は `材料分類` とします。
ニュースは市場や業界の動きを確認し、銘柄選定や投資判断の参考にするものとして表示します。

### 投資判断レポート文言

`Investment Report` は `投資判断レポート`、`Overall judgement` は `総合判断`、`Confidence` は `信頼度`、`Investment stance` は `投資スタンス`、`Key risks` は `主な注意材料` とします。
Markdown は素表示だけにせず、可能な範囲で `総合判断`、`3行サマリ`、`判断理由`、`スコア内訳`、`価格・予測`、`根拠資料との対応`、`リスク`、`補足` に分けて表示します。

### 詳細データ・開発者向け文言

`Developer Data Details` は `詳細データ`、`Download raw JSON` は `詳細JSONをダウンロード` とします。
内部確認用の JSON、CSV列名、取得元レスポンス、検索品質、抽出claimなどは expander 内に置き、通常ユーザーには必要な場合のみ開ける構成にします。

### ダウンロード文言

形式と対象を明示します。
例: `ランキングCSVをダウンロード`、`投資スコアJSONをダウンロード`、`レポートMarkdownをダウンロード`、`レポート一式ZIPをダウンロード`。

## 更新ルール

UI 文言、レポート文言、初心者向け説明を大きく変える場合は、この文書も更新します。

実装で使う文言とこの文書がずれた場合は、実際の UI を確認し、自然な方に揃えます。
