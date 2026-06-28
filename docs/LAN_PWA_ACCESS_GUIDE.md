# Smart Market AI LAN / PWA風アクセスガイド

Smart Market AI（SMAI）を Desktop PC で動かしたまま、同じ家庭内 Wi-Fi の
iPad / iPhone から Safari で閲覧・操作する手順です。外出先アクセスや
インターネット公開を行うための設定ではありません。

この文書はiPhone / iPadから見る手順に絞っています。Windowsログオン時の自動起動、
停止、状態確認、タスク登録、ログ確認は
[Desktop PCサーバー運用ガイド](SERVER_OPERATIONS_GUIDE.md)を参照してください。

## 1. Desktop PC で LAN 公開起動する

1. Desktop PC を信頼できるプライベートネットワークに接続します。
2. エクスプローラーから `scripts/run_lan_server.bat` を実行します。
3. Windows Firewall の確認が表示された場合は、**プライベートネットワークだけ**
   許可します。パブリックネットワークは許可しません。
4. Desktop PC のブラウザーで `http://localhost:8501` を開き、SMAI が表示される
   ことを確認します。

この BAT を使った場合だけ、Streamlit は `0.0.0.0:8501` で待ち受けます。
Streamlit標準出力のURLには自動検出したDesktop PCのIPv4アドレスを表示します。
IPを自動検出できない場合は、開けない仮アドレスを表示せず `localhost` に戻します。
その場合は `ipconfig` でIPv4アドレスを確認してください。
通常の起動方法や配布 EXE の設定は変更しません。終了する場合は起動した
コマンド画面で `Ctrl+C` を押します。

日常的な自動起動では、対話用BATではなくタスクスケジューラ用の
`scripts/start_smai_server.bat` を使います。登録方法はサーバー運用ガイドに
まとめています。

## 2. Desktop PC のローカル IP を確認する

コマンドプロンプトで次を実行します。

```powershell
ipconfig
```

現在使っている Wi-Fi または Ethernet の `IPv4 アドレス` を確認します。
たとえば `192.168.0.20` です。`169.254.*` や未接続アダプターの値は使いません。

## 3. iPad / iPhone から開く

1. iPad / iPhone を Desktop PC と同じ Wi-Fi に接続します。
2. Safari で `http://<Desktop PC の IPv4 アドレス>:8501` を開きます。
3. IP が `192.168.0.20` なら、URL は `http://192.168.0.20:8501` です。
4. サイドメニューから、銘柄ランキング、銘柄コックピット、投資レーダー、
   Myウォッチリスト、SMAIアシスタントなどへ移動できることを確認します。

初回表示には Desktop PC 側の処理時間がかかる場合があります。iPad / iPhone は
表示・操作端末であり、分析、外部取得、LLM Gateway、Agent Workflow は従来どおり
Desktop PC 側で動きます。

## 4. Safari のホーム画面に追加する

1. Safari で SMAI を開きます。
2. 共有ボタンを押します。
3. `ホーム画面に追加` を選択します。
4. 名前を `SMAI` または `Smart Market AI` にして追加します。
5. ホーム画面のアイコンから起動し、主要画面へ移動できることを確認します。

SMAI はホーム画面用アイコン、テーマ色、アプリ名、manifest を配信します。
ただし Streamlit は一般的な静的 PWA フレームワークではないため、Service Worker、
オフライン起動、更新キャッシュ、iOS ネイティブアプリ相当の完全な PWA 動作は
提供しません。Safari / iOS の版によって、初回のホーム画面追加時にタイトルや
アイコンの反映タイミングが異なる場合があります。

ホーム画面用アイコンは、Streamlitのエントリポイント `ui/app.py` に対応する
`ui/static/pwa/` に配置し、標準static配信を使います。次のURLから直接確認できます。
`<Desktop PCのIP>` は実際のIPv4アドレスへ置き換えてください。

```text
http://<Desktop PCのIP>:8501/app/static/pwa/apple-touch-icon-v2.png
```

Streamlit単体のstatic URLには `/app/static/` が付くため、
`/assets/pwa/apple-touch-icon.png` では配信されません。

以前追加したホーム画面アイコンが `S` の簡易表示のままの場合は、既存のSMAI
ショートカットをホーム画面から削除し、SafariでSMAIを再読み込みしてから
`ホーム画面に追加` をやり直してください。iOSが以前のアイコンを保持する場合が
あるため、現在はキャッシュ回避用の `apple-touch-icon-v2.png` を参照しています。
それでも更新されない場合はSafariのSMAIタブを閉じて開き直すか、SafariのWebサイト
データを消去してから再追加します。

## 5. 接続できない場合

- Desktop PC 側で `http://localhost:8501` が開くか確認します。
- 両方の端末が同じ Wi-Fi / 同じゲスト分離されていないネットワークか確認します。
- `ipconfig` で現在の IPv4 アドレスを再確認します。
- Windows Defender Firewall で TCP 8501 の受信を**プライベートネットワークだけ**
  許可します。
- セキュリティソフトやルーターの端末間通信ブロック（AP isolation）が有効でないか
  確認します。

ファイアウォール規則を手動で作る場合も、対象は Private profile と TCP 8501 に
限定してください。Public profile を許可しないでください。

## 6. IP アドレスを固定する

Desktop PC の IP が変わるとホーム画面の接続先も変わります。Windows に固定値を
直接設定するより、Deco X50 などのルーターアプリで Desktop PC の DHCP アドレスを
予約する方法を推奨します。例として `192.168.0.20` を予約します。

## 7. セキュリティ上の注意

- 家庭内など、信頼できる同一 LAN での利用に限定します。
- ルーターのポート開放やポート転送は行いません。
- TCP 8501 をインターネットへ直接公開しません。
- 本対応は認証、HTTPS、VPN、Tailscale、Cloudflare Tunnel を追加しません。
- 外出先アクセスが必要になった場合は、認証・HTTPS・VPN を含む別フェーズとして
  設計と安全確認を行います。

HTTP のため、同じ LAN 上の信頼できない利用者から通信内容を保護する構成では
ありません。公共 Wi-Fi や共有ネットワークでは LAN 公開起動しないでください。

## 8. 表示確認の優先順

まず iPad 横向き、次に iPad 縦向き、iPhone 横向き、iPhone 縦向きの順で確認します。
狭い画面ではカードや入力欄を縦に並べ、詳細テーブルは横スクロールできます。
PC 幅では従来レイアウトを維持します。iPhone は最低限の閲覧・操作対応であり、
完全最適化は今回の対象外です。
