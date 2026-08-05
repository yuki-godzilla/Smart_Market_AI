# Smart Market AI MagicDNS / PWA風アクセスガイド

Smart Market AI（SMAI）は、TailscaleのMagicDNSを使い、家庭内LANでも外出先でも
同じURLからDesktop PC上のMain Applicationへ接続します。接続端末（Windows、iPad、
iPhone）ではTailscaleを起動してください。インターネットへの直接公開は行いません。

この文書はiPhone / iPadから見る手順に絞っています。Windowsログオン時の自動起動、
停止、状態確認、タスク登録、ログ確認は
[Desktop PCサーバー運用ガイド](SERVER_OPERATIONS_GUIDE.md)を参照してください。

## 1. 使用するURL

このSMAIサーバーのMagicDNS端末名は `desktop-bqrpr4c`、Main Applicationの正式ポートは
`8501` です。通常アクセスには次だけを使用します。

```text
http://desktop-bqrpr4c:8501
```

サーバーPC上での起動確認・障害切り分けには次を使用します。

```text
http://localhost:8501
```

LAN IPv4、Tailscale IP、`0.0.0.0`、`localhost`を、他端末やQRコード用のURLとして
使わないでください。MagicDNS名を変える場合は `config/server.yaml` の
`network.tailscale_hostname`、または `SMAI_TAILSCALE_HOSTNAME` を更新します。

## 2. Desktop PCで起動する

1. SMAIサーバーPCでTailscaleを起動し、同じtailnetへログインします。
2. エクスプローラーから `scripts/run_lan_server.bat` を実行します。
3. 起動メッセージの「Normal access」に表示されたURLが
   `http://desktop-bqrpr4c:8501` であることを確認します。
4. サーバーPCでは `http://localhost:8501` を開き、SMAIが表示されることを確認します。

手動・自動・監視復旧の起動は共通ランチャーを使うため、同時起動しても既存サーバーを
再利用します。Webサーバーの `0.0.0.0:8501` は待受設定であり、ブラウザー用URLでは
ありません。日常的な自動起動には `scripts/start_smai_server.bat` を使います。

## 3. iPad / iPhone / 別PCから開く

1. 接続する端末でTailscaleを起動し、サーバーPCと同じtailnetへログインします。
2. Safariまたはブラウザーで `http://desktop-bqrpr4c:8501` を開きます。
3. ユーザー選択、銘柄コックピット、ランキング、投資レーダー、Myウォッチリスト、
   SMAIアシスタントが使えることを確認します。

このURLは家庭内LANと外出先で共通です。iPad / iPhoneは表示・操作端末であり、分析、
外部取得、LLM Gateway、Agent Workflowは従来どおりDesktop PC側で動きます。

## 4. Safariのホーム画面に追加する

1. Safariで `http://desktop-bqrpr4c:8501` を開きます。
2. 共有ボタンを押し、`ホーム画面に追加`を選択します。
3. 名前を `SMAI` または `Smart Market AI` にして追加します。
4. ホーム画面のアイコンから起動し、主要画面へ移動できることを確認します。

SMAIはホーム画面用アイコン、テーマ色、アプリ名、manifestを配信します。ただし
Streamlitは一般的な静的PWAフレームワークではないため、Service Worker、オフライン
起動、更新キャッシュ、iOSネイティブアプリ相当の完全なPWA動作は提供しません。

ホーム画面用アイコンは次のURLから直接確認できます。

```text
http://desktop-bqrpr4c:8501/app/static/pwa/apple-touch-icon-v2.png
```

以前追加したホーム画面アイコンが古い場合は、既存のSMAIショートカットを削除し、
SafariでSMAIを再読み込みしてから追加し直してください。

## 5. 外部接続診断

SMAIの `設定 / データ情報` にある `外部接続診断` では、現在の接続種別、
WebSocket設定、最適化済み画像量、session stateの概算を確認できます。通常アクセスとして
表示するURLはMagicDNS URLだけです。診断スナップショットを保存しても、投資データや
入力内容そのものはログへ保存しません。Quick Lookと画面別の通信確認は
[外部接続安定化](EXTERNAL_ACCESS_STABILITY.md)を参照してください。

## 6. 接続できない場合

1. 接続端末とSMAIサーバーPCでTailscaleが起動していることを確認します。
2. 両端末が同じtailnetに参加し、MagicDNSが有効であることを確認します。
3. URLが `http://desktop-bqrpr4c:8501` であることを確認します。
4. サーバーPCで `http://localhost:8501` が開くことを確認します。
5. `scripts/check_smai_server_status.bat` でSMAIのhealth checkを確認します。
6. Windows FirewallがSMAIのTCP 8501待受を遮断していないことを確認します。

名前解決が失敗する場合はTailscale / MagicDNSの状態を、名前解決後に接続できない場合は
SMAI起動状態とWindows Firewallを確認します。ルーターのポート開放、ポート転送、
UPnP、Tailscale Funnel、公開用リバースプロキシは使用しません。

## 7. セキュリティ上の注意

- SMAIはTailscale tailnet内だけで利用します。
- TCP 8501をインターネットへ直接公開しません。
- ルーターのポート開放、ポート転送、UPnPは行いません。
- Tailscaleの認証キー、APIキー、他端末のIPアドレス一覧をSMAI画面やログへ載せません。

## 8. PWA成果物と表示の確認

- PWAではSMAI生成ファイルの「開く」リンクを使わず、内容表示、コピー、プレビュー、
  ダウンロードを利用します。
- JSON/PDF/ZIP操作後にQuick Lookや外部Viewerへ自動遷移しないことを確認します。
- ニュース、企業IR、TDnet、EDINETなどの外部情報源リンクは通常の外部ページです。
- 問題発生時は設定画面の「外部接続診断」でスナップショットを保存します。

詳細な6環境チェックリストとNetwork/Console確認項目は
[`EXTERNAL_ACCESS_STABILITY.md`](EXTERNAL_ACCESS_STABILITY.md)を参照してください。

表示は、iPad横向き、iPad縦向き、iPhone横向き、iPhone縦向きの順で確認します。
狭い画面ではカードや入力欄を縦に並べ、詳細テーブルは横スクロールできます。PC幅では
従来レイアウトを維持します。

## 9. PWAを閉じた後の状態復元

SMAIは、主要操作で値が変わったときだけ
`data/user_state/last_session.json` に軽量な復元情報を保存します。iOSがタブ、
WebSocket、WebViewプロセスを破棄して新しいStreamlit sessionになった場合も、
最後のユーザー、主要画面、Cockpit銘柄、Ranking主要条件を可能な範囲で復元します。

URLに `smai_start_profile`、`smai_page`、`smai_symbol` が指定されている場合はURLを優先します。
復元時に価格取得、ランキング作成、AI調査更新、ニュース取得は自動実行されません。
`.streamlit/config.toml` の5分TTLは短時間の再接続補助であり、iOS側のプロセス破棄を防ぐ設定では
ありません。

実機では、PWAを閉じた直後、5分経過後、MagicDNS接続時をそれぞれ確認してください。
複数端末・複数ユーザーが同じSMAIサーバーを使う場合、現在のスナップショットは
アプリ全体で最後に操作した状態です。
