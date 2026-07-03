# ウォッチリストグループ 実装計画

## 1. 方針

既存お気に入り、snapshot、Cockpit handoffを変更せず、
保存基盤から表示、編集へ小さな縦切りで進める。各Phaseはnetwork-free testを通し、
後続Phaseを待たずに安全にrollbackできる単位とする。

## 2. Phase 0: 調査・設計

- 要件、UI、保存設計、コード影響調査、実装計画
- MVPとD&D後続の境界
- 受入条件とテスト方針

完了条件はdefault/sessionとcustom/profile保存、favoritesとの責務分離、
responsive 4 viewport、fallback操作が明文化されていること。

## 3. Phase 1: 保存基盤

候補:

- `ui/watchlist_groups.py`または`backend/watchlist_groups/`
- `tests/test_watchlist_groups.py`

実装:

- typed models、validation、repository/service
- custom profile JSONとdefault session adapter
- group CRUD、order変更、placement更新
- atomic write、破損fallback、group ID生成

確認:

- user分離、default非永続、CRUD、削除時未分類、破損、atomic write

## 4. Phase 2: グループ別表示

候補:

- `ui/app.py`
- `ui/styles.py`
- watchlist/UI関連tests

実装:

- favorites＋groupsからview modelを作るpure helper
- `グループ別／すべて`
- 未分類を最後に合成
- compact card renderer
- 現行filter/sort、Cockpit handoff、欠損表示の再利用

## 5. Phase 3: グループ作成・編集・削除

- `st.dialog`による作成・編集・削除確認
- 同名、文字数、制御文字、最大件数error
- 上へ／下へ
- danger/secondary/primary style
- 削除でfavorites/snapshotが変わらないことを確認

## 6. Phase 4: 配置編集モード

- user-scoped edit modeとwidget key
- symbolごとのgroup select＋保存
- 未分類への移動
- user切替時のstale state除去
- normal/edit modeの見た目分離

確認:

- 1 symbol = 1 group
- 新規お気に入りは未分類
- 解除後非表示、再登録後復帰
- smartphone/iPadのselect操作

## 7. Phase 5: D&D spike・任意導入

先に独立spikeを行い、次を満たす場合だけ依存追加する。

- Streamlit 1.38とonedir EXEでcomponent assetを読み込める。
- PC mouse、iPad touch、iPhone scroll共存を確認できる。
- group IDとsymbolのイベントが安定し、rerunで重複保存しない。
- Playwrightで成功・失敗・fallbackを再現できる。
- packageの保守状況、license、脆弱性、bundle sizeが許容範囲である。

不合格ならselectを正式MVP操作として維持する。採用時もD&Dは編集モード限定、
select fallback必須とする。

## 8. Phase 6: UI仕上げ・レスポンシブ

- shared responsive/card-grid classを優先
- 375×812、810×1080、1080×810、1366×768で確認
- page-level overflow、44px touch target、dialog、長いgroup名、20groupを確認
- Streamlit exception、Cockpit遷移、解除、判断メモを回帰確認
- screenshotを`docs/responsive/screenshots/watchlist_groups/`へ保存

## 9. Phase 7: 将来拡張

- group icon・自由色入力
- placement手動順
- group/銘柄D&D
- collapse（既定は常時展開を維持）
- 配置先付きお気に入り追加
- export/import、明示cleanup

複数group所属やAI自動分類は別要件として再設計する。

## 10. 変更対象ファイル候補

| path | 目的 |
| --- | --- |
| `ui/watchlist_groups.py` | model/repository/serviceまたはUI向けfacade |
| `ui/user_data.py` | 既存profile/session helperの必要最小限の共通化 |
| `ui/app.py` | page、view model接続、dialogs、配置編集 |
| `ui/styles.py` | group grid、compact card、button variants、responsive |
| `setup/requirements.txt` | D&Dを採用したPhase 5だけ |
| `tests/test_watchlist_groups.py` | 保存・validation・user分離 |
| `tests/test_ui_forecast_display.py` | view model/card helper |
| `tests/test_ui_news_streamlit_page.py` | Streamlit page interaction |
| `tests/test_ui_styles.py` | class/breakpoint |
| responsive smoke | 4 viewport |
| `Documents/06_MVP_Operations_Guide.md` | 実装時の操作・保存仕様 |
| `PROJECT_CONTEXT.md` | Phase完了時だけcurrent state更新 |
| `Documents/99_Work_Log.md` | 各sliceのdurable result |

保存層を`backend/`へ置く場合でもStreamlitをimportさせず、
default session adapterだけを`ui/`に残す。

## 11. テスト方針

### 保存基盤

- group作成、改名、削除、順序変更
- placement作成・更新・未分類化
- 不正ID、symbol、名前、timestamp、version、21件目
- custom user分離、default session-only
- JSON破損、unknown group、atomic replace失敗
- 削除時にfavoritesを変更しない

### UI/view model

- group別の生成、件数、順序、未分類最後
- favoritesにないplacementは非表示
- 再お気に入り化で以前のplacementへ復帰
- dialog、edit mode、select、confirm
- 空状態、filter/sort、compact cardの欠損表示
- button classのprimary/edit/positive/secondary/danger差

### 回帰

- 現行カード／テーブル
- お気に入り追加・解除
- Ranking、Cockpit、投資レーダーからの追加
- Cockpit、詳細dialog、判断メモ
- user切替、default説明、snapshot prune
- responsive My Radar smoke

### D&D

- pointer drag、touch代替、group間移動
- rerun後の一回保存、同一group no-op
- component失敗時select fallback
- mobileで無効化する場合のselect表示

## 12. 検証順

1. 新規repository/serviceのtargeted pytest
2. view model/helper pytest
3. Streamlit AppTest
4. Ruff対象file
5. project Black helper
6. network-free responsive Playwright smoke
7. meaningful code change完了時に全体local checks

## 13. リスク

- `ui/app.py`が大きく、page-local追加で保守性が悪化する。
- 現行filter/sortとgroup orderの優先順位が分かりにくくなり得る。
- 同一profileの複数browser更新でlost updateが起き得る。
- default session stateとcustom JSONの挙動差。
- 20group×多数cardによるrerun・DOM負荷。
- 外部D&D componentのtouch、bundle、license、テスト不安定性。
- placement保持が「解除で全削除」との期待に反する可能性。

## 14. rollback

- groups fileを読めない、またはfeature flagをoffにした場合は現行「すべて」表示へ戻す。
- favorites/snapshot schemaを変更しないため、group機能だけを無効化できる。
- 各Phaseを独立commitとし、D&D依存追加は専用commitに分ける。
- migrationはbackupとversion checkなしに実行しない。
