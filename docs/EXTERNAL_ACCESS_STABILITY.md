# 外部接続安定化

SMAI は `.streamlit/config.toml` を共通設定として使い、`0.0.0.0:8501`、static
配信、WebSocket 圧縮、30秒 ping、300秒の切断セッション保持で起動します。
`scripts/run_lan_server.bat` は LAN URL と、取得できる場合は Tailscale URL を表示します。
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
2. LANとTailscaleの各URLで初期ユーザー選択、ユーザー追加、アイコン変更を確認する。
3. ブラウザーのNetworkでアイコンが `/app/static/` のWebPとして取得され、
   HTMLに巨大な `data:image/...;base64` がないことを確認する。
4. iPhone/iPad Safariとホーム画面追加版で、切断、表示品質、保存失敗時の表示を確認する。

実機/Tailscaleの検証はローカル自動テストとは分離し、結果を作業ログへ記録します。
