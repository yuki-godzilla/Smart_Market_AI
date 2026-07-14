# 外部接続安定化

SMAI は `.streamlit/config.toml` を共通設定として使い、`0.0.0.0:8501`、static
配信、WebSocket 圧縮、30秒 ping、300秒の切断セッション保持で起動します。
`scripts/run_lan_server.bat` はMagicDNSの通常アクセスURL
`http://desktop-bqrpr4c:8501` を1つだけ表示します。
常駐起動の診断情報は `logs/server_ops/smai_server_*.log` に残ります。

## 今回確認した主因

ユーザーアイコン12枚は元画像が各約1.7〜2.1MB、1254pxで、以前は static URL が
ないためbase64 data URIとして画面HTMLへ埋め込まれていました。アイコン編集画面では
元データ合計約22MB（base64化後はさらに約33%増）がrerunごとに送られ得る状態でした。
外部回線やiOS Safari/PWAでWebSocketメッセージが重くなる直接要因です。

現在は `scripts/optimize_ui_assets.py` で生成した256px WebPを
`/app/static/assets/user_icons/` から配信します。これは128px表示の2倍解像度で、
Retina表示品質を保ちながらWebSocket本文へ画像データを載せません。候補一覧は最初の
8件を表示し、残りは「もっと見る」で読み込みます。元PNGは削除せず保持します。

## 確認手順

1. `scripts/run_lan_server.bat` で起動する。
2. LAN内・外出先の両方でMagicDNS URLを使い、初期ユーザー選択、ユーザー追加、
   アイコン変更を確認する。
3. ブラウザーのNetworkでアイコンが `/app/static/` のWebPとして取得され、
   HTMLに巨大な `data:image/...;base64` がないことを確認する。
4. iPhone/iPad Safariとホーム画面追加版で、切断、表示品質、保存失敗時の表示を確認する。

実機/Tailscaleの検証はローカル自動テストとは分離し、結果を作業ログへ記録します。

## PWAでの成果物確認

SMAIが生成するJSON、CSV、Markdown、PDF、ZIPは、外部ページを「開く」リンクとして
扱いません。`st.download_button`を使う共通部品に寄せ、JSON/MarkdownはSMAI内の
プレビューとコピー欄を利用できます。PDFプレビューは明示操作後だけSMAI内iframeへ
表示し、ZIPはダウンロードのみです。Assistant回答に残っていた`data:` URIリンクも
廃止し、「最新回答のコピー・保存」からプレビュー、コピー、Markdownダウンロードを
選ぶ構成にしました。

ニュース、企業IR、TDnet、EDINET、Yahoo Financeなどの外部Webページは成果物では
ないため、従来どおり外部リンクを維持します。

## 追加画像最適化

共通のマスコット、ロゴ、タイトルアートは`/app/static/assets/`配信へ切り替えました。
元画像は`ui/assets/`に保持し、軽量版を別名で生成します。

- Watchlistタイトル: 1,885,538 B → 25,028 B
- SMAIロゴ: 264,732 B → 32,248 B
- Cockpitマスコット: 195,270 B → 25,734 B
- Assistantアイコン: 184,216 B → 32,192 B

変換結果は`logs/server_ops/asset_optimization_report.md`、画面別の静的診断ベースラインは
`logs/server_ops/ui_delivery_diagnostics.md`で確認できます。

## 外部接続診断

設定画面の「外部接続診断」を開くと、次を確認できます。

- localhost / LAN / Tailscale / 不明の接続診断
- 軽量モード
- static配信とWebSocket圧縮
- ping intervalと切断セッション保持時間
- 最適化済み画像件数と合計サイズ
- session_stateのキー数とJSON換算の概算サイズ

「診断スナップショットをログへ保存」は値の中身を記録せず、件数・サイズ・設定だけを
`logs/server_ops/external_connection_diagnostics.log`へ追記します。

## 6環境チェックリスト

次の各環境で同じ順序で確認します。

1. MagicDNS / サーバーPC Windows Chrome（localhostは切り分けだけ）
2. MagicDNS / LAN内 Windows Chrome
3. MagicDNS / 外出先 Windows Chrome
4. MagicDNS / iPhone Safari
5. MagicDNS / iPad Safari
6. MagicDNS / iPhone / iPad PWA

各環境で、初期ユーザー選択、ユーザー切替、アイコン編集、Ranking、Cockpit、
Watchlist、投資レーダー、Assistantを順に表示します。その後、JSONの内容表示・コピー・
ダウンロード、CSVの表・ダウンロード、Markdownのプレビュー・コピー・ダウンロード、
PDFのSMAI内表示・ダウンロード、ZIPのダウンロードを確認します。

Chrome/SafariのNetworkでは`/app/static/`画像がキャッシュ可能な個別リクエストになり、
DocumentやWebSocketに巨大なbase64画像がないことを確認します。Consoleでは
WebSocket切断、Streamlit例外、404を確認します。切断時は発生画面、操作、時刻、
接続種別、診断スナップショットを記録してください。
