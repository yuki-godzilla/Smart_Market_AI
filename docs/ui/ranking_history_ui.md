# ランキング履歴 UI 設計

## 1. 導線

`ui/app.py::_render_market_data_ranking()` の `render_page_title()` 直後、作成条件カードより前に「ランキング履歴」ボタンを置く。結果の有無に依存せず表示でき、既存条件フォームを囲む column 構造へ影響しにくい。

- desktop: タイトル直下の右寄せ action
- smartphone: タイトル直下で横幅100%、最低44px相当のタップ領域
- default ユーザー: ボタンは表示し、押下後に「保存履歴にはプロフィール選択が必要です」と案内する

## 2. サブビューと遷移

ランキングは side menu 上では同じ `ranking` ページを維持し、内部サブビューだけを切り替える。

```text
ranking
  ├─ live
  │    └─ [ランキング履歴] → history_list
  ├─ history_list
  │    ├─ [ランキングへ戻る] → live
  │    └─ [行/詳細] → history_detail(run_id)
  └─ history_detail
       ├─ [履歴一覧へ戻る] → history_list
       ├─ [ランキング画面へ戻る] → live
       └─ [この条件で再ランキング] → filters復元 → live
```

推奨 state:

```python
ranking_view_mode = "live" | "history_list" | "history_detail"
selected_ranking_history_id = str | None
ranking_history_restore_notice = str | None
```

無効な mode、別ユーザーの run_id、削除済み run_id は `history_list` へ戻す。ユーザー切替時には選択 run_id を破棄する。永続化対象は履歴データであり、サブビュー自体は session state でよい。PWA復帰で state が失われても live へ安全に戻る。

## 3. 一覧画面

上から次の順に構成する。

1. `ランキング履歴` タイトルと「ランキングへ戻る」
2. `保存履歴 n件 / ピン留め n件 / 通常 n / 30件`
3. 検索欄とフィルターチップ
4. `ピン留め済み` セクション
5. `通常履歴` セクション

列は `作成日 / データ取得日 / 種別 / 対象 / 条件 / 候補数 / 上位銘柄 / 操作`。PC は AgGrid または dataframe、スマホは1履歴1カードを基本にし、ページ全体の横スクロールを発生させない。表を使う場合だけ component-local scroll を許可する。

空状態、破損状態を区別する。

- 0件: ランキング作成への CTA
- snapshot 欠損: 一覧メタデータは表示し、「詳細データを読み込めません」を付ける
- index 不正: 復旧可能な snapshot の自動全走査はMVPでは行わず、安全なエラーとログを出す

## 4. 詳細画面

### ヘッダー

- 戻る導線2種
- ピン留め状態
- 対象、ランキング種別
- 作成日時、データ取得日、provider、取得期間
- 候補件数、保存行数

### 操作

- `この条件で再ランキング`: 保存 filters を既知キーだけ復元し live へ戻る。実行はしない。
- `CSV出力`: Phase 7。snapshot の `result_rows` だけを出力する。
- `ピン留め / 解除`: 即時更新可。結果本体は変更せず index と snapshot metadata の整合を保つ。
- `削除`: 通常履歴は確認、ピン留め履歴は強い確認文を表示する。既存 `st.dialog` パターンを再利用する。

### 注意表示

結果の直前に次を常時表示する。

> このランキングは保存時点の結果です。現在の株価・スコアとは異なる場合があります。現在の情報は銘柄コックピットで確認してください。

## 5. 結果 UI 再利用

現行 `_render_ranking_result_table()` は dataframe 相当の `display_rows` を受け取るため表示面は再利用可能だが、内部で現在の favorites、symbol universe、詳細 dialog を参照する。先に次の境界へ小さく分離する。

```python
render_ranking_result_table(
    rows,
    *,
    mode: Literal["live", "history"],
    action_policy: RankingResultActionPolicy,
    snapshot_as_of: date | None = None,
)
```

| 操作 | live | history |
| --- | --- | --- |
| 保存済み列の表示・ソート | 可 | 可 |
| お気に入り切替 | 可 | 可。ただし「現在のお気に入り」と明示 |
| 銘柄詳細 | 現在 universe + live row | snapshot rowを主表示。現在情報は別導線 |
| コックピット | 深掘り | 「現在の銘柄を確認」 |
| AI調査 / My Radar | 現在データの操作 | 自動実行せず現在画面へ遷移 |
| Decision Report生成 | live context | MVPでは非表示 |

履歴表示に `investment_score_display_rows()` や現在の Research/LLM enrichment を再実行してはならない。保存時に display 用の安定列と raw/typed 列を snapshot に格納する。

## 6. レスポンシブ確認

`375x812`、`810x1080`、`1080x810`、`1366x768` で確認する。共有 `smai-responsive-*` / `smai-card-grid-*` クラスを優先し、履歴専用 CSS は `ui/styles.py` に集約する。

- 戻る/ピン/削除 CTA が重ならない
- 条件サマリーが折り返す
- 上位銘柄が省略表示でも識別できる
- dialog が viewport 内に収まる
- Streamlit exception と page-level overflow がない
