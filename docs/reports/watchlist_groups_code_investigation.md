# Watchlist Groups コード影響調査

調査日: 2026-07-03

## 1. 結論

既存のお気に入りは既にcustom userごとに分離され、defaultだけsession-onlyである。
ウォッチリストグループも同じ境界で独立JSON/session payloadとして追加できる。
Myウォッチリストの表示payloadとCockpit handoffは再利用可能だが、
グループ別表示には現行フルカードとは別のcompact rendererが適する。

MVPのD&D採用は推奨しない。現行Streamlitと依存に標準・既導入のD&D手段がなく、
スマホ/iPad、onedir、E2Eの検証コストが保存・基本UIより大きいためである。

## 2. 調査した主なファイル

- `ui/app.py`
- `ui/favorites.py`
- `ui/user_data.py`
- `ui/watchlist_snapshots.py`
- `ui/styles.py`
- `ui/notification_center.py`
- `backend/users/user_repository.py`
- `backend/ranking_history/repository.py`
- watchlist、favorites、profiles、styles、responsive関連tests
- `setup/requirements.txt`
- responsive/operations/wording/UX/spec docs
- `PROJECT_CONTEXT.md`

## 3. Myウォッチリスト画面

### メイン描画

`ui.app._render_my_watchlist_page()`が担当する。

1. page titleとdefault session-only caption
2. `load_favorites()`
3. 削除済みfavoriteのsnapshot prune
4. current rows＋snapshotから`_favorite_display_payload()`を生成
5. bounded auto snapshot/background refresh
6. filter/sort
7. カード／テーブル切替
8. カードは3列で`_render_favorite_card()`を描画

### カード描画

- `_favorite_card_html()`がheader、badges、値動き、metrics、Decision TrailをHTML化する。
- `_render_favorite_card()`が詳細dialog、Cockpit、解除、判断メモformを加える。
- `_favorite_display_payload()`がfavorite、snapshot、computed rowを表示値へ変換する。

表示payloadとstatus helperはcompact cardでも再利用できる。現行フルカードは情報量が多く、
group sectionごとに反復すると縦長になるためHTMLそのものの再利用は推奨しない。

### お気に入り取得と並び順

- 取得元は`ui.favorites.load_favorites()`。
- `_favorite_filter_and_sort_rows()`が画面全体のfilter/sortを行う。
- 初期sortは「追加日が新しい順」。
- 保存されたfavorites listの順番を手動順としては使っていない。

グループ別では、まず現行filter/sortを適用し、その安定順のままgroupへpartitionする。

### 表示モード

現行は`market_data_watchlist_display_mode`でカード／テーブルを選ぶ。
新しい「グループ別／すべて」は別keyにし、`すべて`内で既存keyを維持する。

### Cockpit・解除・関連機能

- Cockpitは`_select_favorite_symbol_for_cockpit()`がsymbolとcontextをsession stateへ渡す。
- 解除は`remove_favorite()`後にtoast＋rerun。
- `build_favorite_radar_items()`はpriority/categoryを計算し、保存順を変更しない。
- group機能はsnapshot pruneやbackground refresh対象を変えない。
- 通知N6はgroup placementを通知条件に暗黙利用しない。

## 4. お気に入り保存

- custom: `data/user/profiles/<user_id>/favorites.json`
- default: `smai_default_user_favorites` session payload
- legacy fallback定数: `data/user/favorites.json`

主な関数は`load_favorites`、`save_favorites`、`add_favorite`、
`remove_favorite`、`toggle_favorite`。

`normalize_favorite_symbol()`はtrim＋uppercaseだけを行う。
`7974.T`と`7974`は別であり、銘柄名解決や`.T`補完はしない。

favoritesの現行saveは直接`write_text()`でatomicではない。
groupsの新規保存ではこれを踏襲せず、ranking historyのatomic helper patternを使う。
placement保持を採るため、`remove_favorite()`へgroup cleanupを組み込まない。

## 5. ユーザー別保存

- `ui.user_data.current_user_id()`はsessionの`smai_current_user_id`を読む。
- `profile_data_path(filename)`はcustom userだけprofile配下のpathを返す。
- defaultは編集不可system profileで、お気に入りとsnapshotをfileへ保存しない。
- group名制約は既存profile名のtrim後1〜32文字、制御文字禁止を再利用できる。
- ranking historyは同一directoryのtemporary、flush、`os.fsync`、
  `os.replace`、cleanupを実装している。

## 6. UI状態管理

推奨key:

- `watchlist_groups_view_mode`
- `watchlist_groups_edit_mode`
- `watchlist_groups_dialog`
- `watchlist_groups_active_group_id`
- `watchlist_groups_move_<user_id>_<symbol>`
- `watchlist_groups_save_token_<user_id>_<symbol>`

user IDとsymbolをkeyへ含め、ユーザー切替時にはtransient stateをclearする。
`st.dialog`は現行Streamlit 1.38で利用でき、既存の銘柄データdialog例もある。
form submit後に保存し、select変更だけでは保存しない。

## 7. UI差し込み候補

- page title直後・default caption後: group CTAと表示mode
- refresh操作前: group/view controls
- filter/sort後: grouped view modelへpartition
- `_render_favorite_card()`相当: compact group cardと配置select
- 現行card/table loop: `すべて`表示としてそのまま残す

保存・grouping helperを`ui/app.py`へ直接積み増さず、専用moduleに分ける。

## 8. D&D調査

### 現環境

- Streamlit: 1.38.0
- 関連API: `st.dialog`、`st.fragment`
- 標準`sortable`/`draggable`: なし
- `streamlit-sortables`: 未導入
- repository内の既存D&D component: なし

### 実装候補

1. `streamlit-sortables`等のthird-party component
2. 独自Streamlit component
3. HTML/JS injection

3はイベント同期、security、保守性が弱く推奨しない。1を小さなspikeで評価し、
不適合ならselectを維持するのがMVPとして妥当。

### 外部依存・onedir

依存追加時はfrontend asset、license、PyInstaller collect、offline起動、
bundle sizeを確認する必要がある。現時点では実build検証をしていない。

### スマホ/iPad

dragとpage scroll、長押し、drop targetの競合がある。mouse動作をtouch対応の根拠にしない。
375×812、810×1080、1080×810で評価し、合格前はmobile D&Dを無効にする。

### テスト

Playwrightとresponsive smoke基盤は導入済み。iframe componentならframe locator、
pointer event、rerun完了待ちの専用testが必要。component failure時にselectが
表示・保存できることを必須testにする。

### 推奨

- MVP: D&Dなし、select＋保存、group順は上下ボタン
- Phase 5: dependencyを隔離したspike
- 採用後: 編集モード限定、select fallback常設

## 9. テスト影響範囲

新規:

- group model/repository/service unit tests
- grouping view model tests
- Streamlit dialog/edit mode tests
- D&D採用時のcomponent/E2E tests

回帰:

- favorites、profiles、snapshots
- watchlist table/card helpers
- Streamlit watchlist page
- styles
- responsive My Radar smoke

## 10. 実装時の注意点

- grouping前にcurrent favoritesで絞り、orphan placementを表示しない。
- unknown group参照を未分類へ安全に落とす。
- group削除とplacement削除を1回のatomic updateにする。
- group名でplacementやwidget valueを保持しない。
- defaultでprofile fileを作らない。
- snapshot refresh、Radar priority、Cockpit contextをgroupで変更しない。
- group別の件数がfilter後であることをUI文言とtestで固定する。
- 20group×多数銘柄でDOMとrerun時間を測る。
- button色だけで操作意味を伝えない。

## 11. 未確認事項

- third-party D&D componentの最新保守状況、license、既知issue
- onedir buildへの実同梱可否
- iPhone/iPad実機のtouch D&D
- 同一custom profileを複数browserから同時更新した場合のlock要件
- 初回リリース時のgroup別／すべての既定値
- 非表示placementのcleanup UIを将来提供するか

## 12. 推奨実装順

1. typed storageとdefault adapter
2. pure grouping view model
3. grouped read-only表示と未分類
4. group CRUD・上下順
5. select配置編集
6. responsive polish
7. D&D spike
