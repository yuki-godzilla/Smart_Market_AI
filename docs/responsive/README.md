# SMAI レスポンシブ確認ガイド

## 目的

Cockpit、Ranking、My Radar、投資レーダー、SMAI Assistant、リバランス、設定 / データ情報を、PC の情報密度を保ちながら iPhone / iPad でも安全に閲覧・操作できるようにします。投資判断、スコア、予測、データ取得、AI、RAG のロジックは変更対象外です。

## 対象 viewport

- iPhone 13 mini: 375 x 812
- iPad 第8世代・縦: 810 x 1080
- iPad 第8世代・横: 1080 x 810
- PC: 1366 x 768 以上

共通ブレークポイントは smartphone `max-width: 767px`、tablet `768px–1024px`、desktop `1025px` 以上です。

## 対応範囲

- 共通カードグリッド: PC 3列、iPad 縦 2列、iPhone 1列
- Streamlit columns: iPad では折り返し、iPhone では原則縦積み。比較しやすいKPI行と、保存/キャンセルなど2択の主要操作は2列を維持する
- ボタン、ダウンロード、リンクボタン: iPhone で全幅・高さ 44px 以上
- チャート、表、data editor: viewport 内に収め、必要な箇所だけ横スクロール
- 長い URL / 銘柄名 / 数値: カード内で折り返し
- ダイアログ、Assistant: viewport 内でスクロール可能
- 長いウォッチリスト、ニュース、履歴、根拠カードは、画面外の描画を遅延して初期スクロールを軽くする

## 確認手順

1. `scripts/run_lan_server.bat` など既存手順で Streamlit を起動します。
2. Chrome DevTools の Device toolbar を開き、上記4 viewportを順番に指定します。
3. Cockpit → Ranking → My Radar → 投資レーダー → SMAI Assistant → リバランス → 設定 / データ情報の順に確認します。
4. ページ全体の横スクロール、切れたボタン、カード外にはみ出す文字、Streamlit エラーがないことを確認します。
5. 表とヒートマップは、そのコンポーネント内部だけ横スクロールできることを確認します。

LAN 接続時は、サーバー画面に表示された Network URL を同一ネットワーク上の端末で開きます。LAN 公開や外部 provider 接続は自動テストの前提にしません。

## スクリーンショット

保存先は `docs/responsive/screenshots/<screen>/` とし、ファイル名は次を使います。

- `iphone13mini.png`
- `ipad8_portrait.png`
- `ipad8_landscape.png`
- `pc_1366.png`

画面名は `cockpit`、`ranking`、`my_radar`、`investment_radar`、`assistant`、`rebalance`、`settings` です。自動取得環境がない場合は Chrome DevTools の Capture screenshot を使います。

## Playwright

Playwright は任意のスモーク用途です。通常起動・CI・ローカルチェックの必須実行にはしていません。外部データ、AI調査、LLM接続へ依存しない local provider で確認します。

Streamlit が起動済みの状態で、PowerShell から次を実行します。

```powershell
$env:SMAI_RUN_RESPONSIVE_SMOKE = "1"
.\venv_SMAI\Scripts\python.exe -m pytest tests/ui/test_responsive_cockpit_smoke.py tests/ui/test_responsive_ranking_smoke.py tests/ui/test_responsive_my_radar_smoke.py tests/ui/test_responsive_investment_radar_smoke.py tests/ui/test_responsive_assistant_smoke.py tests/ui/test_responsive_rebalance_settings_smoke.py -q
Remove-Item Env:SMAI_RUN_RESPONSIVE_SMOKE
```

URLを変更する場合は `SMAI_STREAMLIT_URL` も指定します。テストは4 viewportの横はみ出し、Streamlit例外、画面見出し、ボタンまたはチャット入力の存在を検査し、Cockpit / Ranking / My Radar / 投資レーダー / SMAI Assistantのスクリーンショットを保存します。

Cockpitチャートの実描画確認は、ローカルのmock providerを使う次の任意スモークで行います。

```powershell
$env:SMAI_RUN_RESPONSIVE_CHART_SMOKE = "1"
.\venv_SMAI\Scripts\python.exe -m pytest tests/ui/test_responsive_cockpit_smoke.py -q
Remove-Item Env:SMAI_RUN_RESPONSIVE_CHART_SMOKE
```

## 既知の残課題

- Streamlit の DOM 属性はバージョン変更で変わる場合があります。
- 画面別の厳密な visual regression とスクリーンショット自動保存は未導入です。
- 実機 Safari ではブラウザの文字拡大設定も含めて最終確認が必要です。
