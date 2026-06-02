# Phase 22 Research Score UX Polish スプリントテスト結果

## 対象

- Branch: `main`
- Base commit: `88ad646 Exclude generated build artifacts from mypy`
- 実行日時: 2026-06-02
- 起動方法: `localhost:8501` 応答確認、Streamlit AppTest による UI レンダリング確認
- network opt-in: live 経路は大阪ガスで 120 秒超過。通常確認は fake external source / deterministic preview で network 非依存
- EDINET_API_KEY: 未設定
- 確認画面: 銘柄コックピット、Ranking AI Research lookup、Research Summary 共通パネル、Research Score 折りたたみ、詳細データ表示

## 実画面確認結果

### Cockpit

- 結果: OK
- Research Score 表示: `Research Score（根拠資料の確認材料）を表示`
- display_context: `cockpit`
- 気づき: Research Summary の主表示を邪魔せず、Research Score は折りたたみ内の補助情報として読める。売買推奨や順位付けに見える文言は検出なし。

### Ranking

- 結果: OK
- Research Score 表示: `Research Score（参考情報）を表示`
- display_context: `ranking`
- ランキング順位との関係: 参考情報として表示され、Cockpit 用の `根拠資料の確認材料` ラベルは混入なし
- 総合スコアとの関係: `総合スコア` / `Research Score` / `データ品質` は役割分離されている
- 気づき: AppTest では Streamlit dialog の押下後状態が安定取得できなかったため、同じ Ranking AI Research lookup helper を単独 view として確認した。

### Research Score 折りたたみ

- 結果: OK
- 読み方: OK
- 要約: OK
- 観点別内訳: OK
- 注意点: OK
- 気づき: `Research Score要約`、`観点別の内訳`、`注意点` が同一 expander にまとまる。閉じた状態では主表示が重くならない。

### 重複表示

- 結果: OK
- 詳細データ側の表示: `Research Score内訳` / `Research Score注意点` の重複見出しなし
- 気づき: 詳細データ側はデータ品質、出典、検索品質、根拠詳細、外部参照ソース取得状況が中心。

### AI調査更新後の表示

- 結果: OK
- Research Summary: 国内株、米国株、ETF、source no-op の各カテゴリで主表示あり
- Research Score: Cockpit 文脈で折りたたみ表示
- source 表示: source ありケースは出典カード / 外部参照ソース、source no-op ケースは資料不足表示
- 気づき: 取得できないことを「情報が存在しない」と断定する表示は検出なし。

## ランダム抽出した確認銘柄

Random seed: `20260602`

| 分類 | 銘柄名 | ticker / code | 市場 | 抽出理由 | 結果 | メモ |
|---|---|---|---|---|---|---|
| 国内大型株 | 大阪瓦斯 | 9532.T | 東証 | 重点確認枠 | OK | Research Summary / Score / source OK |
| 国内大型株 | IHI | 7013.T | 東証 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 国内大型株 | 大塚ホールディングス | 4578.T | 東証 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 国内大型株 | 住友金属鉱山 | 5713.T | 東証 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 国内中小型株 | 大本組 | 1793.T | 東証 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 国内中小型株 | ジーフット | 2686.T | 東証 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 国内中小型株 | メタリアル | 6182.T | 東証 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 国内中小型株 | unbanked | 8746.T | 東証 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 米国大型株 | Stanley Black & Decker | SWK | 米国 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 米国大型株 | YPF | YPF | 米国 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 米国大型株 | CloudFlare Inc A | NET | 米国 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 米国大型株 | Robinhood Markets Inc A | HOOD | 米国 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 米国中小型株 | Nuvation Bio Inc A | NUVB | 米国 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 米国中小型株 | Core Molding Technologies | CMT | 米国 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 米国中小型株 | Freightos Limited | CRGO | 米国 | sector分散ランダム抽出 | OK | Research Summary / Score / source OK |
| 国内ETF | 上場インデックスファンド日経平均高配当株50 | 399A.T | 東証 | テーマ分散ランダム抽出 | OK | ETF summary / Score / source OK |
| 国内ETF | MAXIS Jリート上場投信 | 1597.T | 東証 | テーマ分散ランダム抽出 | OK | ETF summary / Score / source OK |
| 国内ETF | NEXT FUNDS ドイツ国債7-10年 | 2245.T | 東証 | テーマ分散ランダム抽出 | OK | ETF summary / Score / source OK |
| 海外ETF | Invesco NASDAQ Future Gen 200 ETF | QQQS | 米国 | テーマ分散ランダム抽出 | OK | ETF summary / Score / source OK |
| 海外ETF | Xtrackers Singapore Government Bond UCITS ETF | DCSX | 米国 | テーマ分散ランダム抽出 | OK | ETF summary / Score / source OK |
| 海外ETF | VanEck Uranium and Nuclear Energy ETF | NLR | 米国 | テーマ分散ランダム抽出 | OK | ETF summary / Score / source OK |
| 情報不足銘柄 | 住友林業 | 1911.T | 東証 | metadata欠損・source no-op確認 | OK | source no-op / 資料不足表示 OK |
| 情報不足銘柄 | Liminatus Pharma Inc A | LIMN | 米国 | metadata欠損・source no-op確認 | OK | source no-op / 資料不足表示 OK |
| 情報不足銘柄 | グラッドキューブ | 9561.T | 東証 | metadata欠損・source no-op確認 | OK | source no-op / 資料不足表示 OK |
| 銘柄切替 | 9532.T -> 6182.T -> QQQS ほか | mixed | mixed | 連続実行 | OK | 前銘柄の Research Score / source 混入なし |

## 文言確認

| 確認項目 | 結果 | メモ |
|---|---|---|
| Cockpit: 根拠資料の確認材料 | OK | Cockpit expander label で確認 |
| Ranking: 参考情報 | OK | Ranking lookup view で確認 |
| ランキング順位 表記 | OK | 静的検索 / テストで確認 |
| Ranking順位 残存なし | OK | `rg` と UI text で検出なし |
| 売買推奨ではない | OK | UI caption / notes に表示 |
| ランキング順位を変えない | OK | score hierarchy tests / wording で確認 |
| 総合スコアを変えない | OK | score hierarchy tests / optional weight default 0.0 |
| Research Score 内訳の重複なし | OK | 詳細データ側に重複見出しなし |
| Research Score 注意点の重複なし | OK | 詳細データ側に重複見出しなし |

## 計算ロジック非変更確認

- ランキング順位: 変更なし。今回の sprint では ranking / scoring 実装ファイルを変更していない
- 総合スコア: 変更なし。Research Score optional weight は既定 0.0 のまま
- Research Score算出: 変更なし。表示文脈と折りたたみ境界のみ確認
- Ranking sort order: 変更なし。Research Score を sort key に混入させる変更なし
- 差分有無: 計算ロジック差分なし。`ui/app.py` は black helper 指摘に対する caption 1行化のみ

## source 表示確認

| source type | 結果 | メモ |
|---|---|---|
| EDINET | OK | fake official source として source card / trace 表示 |
| TDnet | OK | fake official source として source card / trace 表示 |
| 企業IRサイト | OK | fake official source として source card / trace 表示 |
| Yahoo Finance | OK | provider profile / news の補助sourceとして表示 |
| 外部ニュース | OK | news source として表示。URL不足警告は補足情報として表示 |

## network / API KEY 条件確認

| 条件 | 結果 | メモ |
|---|---|---|
| network opt-in 有効 | NG/制限あり | 大阪ガス live AI調査更新は AppTest で 120 秒超過。外部取得の失敗ケースとして記録 |
| network opt-in 無効 | OK | fake external source / no-op source で network 非依存確認 |
| EDINET_API_KEY 設定あり | 未実施 | 環境変数未設定のため |
| EDINET_API_KEY 未設定 | OK | no-op / fake source 条件でクラッシュなし |

## 検出した不具合

| 優先度 | 内容 | 再現手順 | 対応 |
|---|---|---|---|
| P2 | in-app Browser `iab` がこのセッションで利用不可 | Browser plugin 接続時に `Browser is not available: iab` | Streamlit AppTest で代替。アプリ実装の不具合ではない |
| P2 | live external fetch は AppTest で 120 秒超過 | 大阪ガスで `AI調査を更新` を live 実行 | 通常確認は fake/local fixture に切替。live smoke は別枠推奨 |

## 修正した内容

- `ui/app.py`: black helper 指摘に対する Research Score caption の1行化のみ。表示文言・計算ロジックの変更なし
- ドキュメントに Phase 22 Research Score UX 回帰結果を追加
- UXチェックリストと現在地文書を回帰完了状態へ同期

## 追加・更新したテスト

- 追加なし。既存の Research Score UI 文言テストを再実行

## 実行した検証コマンド

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests\test_ui_forecast_display.py -q -k "research_score or score_confidence_hierarchy"
```

結果: `5 passed, 205 deselected`

```powershell
.\venv_SMAI\Scripts\python.exe -m ruff check ui\app.py tests\test_ui_forecast_display.py --no-cache
```

結果: `All checks passed!`

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py ui\app.py tests\test_ui_forecast_display.py
```

結果: 初回は `ui/app.py` の1行整形で失敗。手動整形後に `Black check passed for 2 Python file(s).`

```powershell
.\venv_SMAI\Scripts\python.exe -m mypy ui\app.py tests\test_ui_forecast_display.py
```

結果: `Success: no issues found in 2 source files`

```powershell
git diff --check
```

結果: OK。CRLF warning のみ

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests\test_ui_forecast_display.py -q
```

結果: 初回は Windows Temp 権限で `tmp_path` setup が失敗。workspace basetemp 指定で再実行し `210 passed`

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest -q --basetemp outputs\work\phase22_full_pytest_tmp
```

結果: `663 passed`
