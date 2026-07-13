# 投資レーダー根拠追跡強化スプリント報告

作成日: 2026-07-13

## 実装範囲

投資レーダーを、ニュース一覧から確認候補を辿る探索画面へ段階的に拡張した。既存の市場ヒートマップ、Ranking、Forecast、Investment Score、Research Scoreの計算・既定weight・表示順は変更していない。

- `RadarCandidate` / `RadarCandidateEvidence` / `RadarCandidateMap` を導入し、news snapshotからnetwork-freeかつ安定順序で候補を集約する。
- `direct_mention`、`inferred_candidate`、`macro_proxy` は候補ID・ラベル・形・通常候補として扱うかどうかまで分離する。マクロ代理は背景確認用であり、通常の銘柄候補としてCockpitやAI根拠整理へ進めない。
- 候補マップは横軸を直接性、縦軸を確認優先度、円の大きさを独立根拠数、色を材料構成、形を由来として表示する。確認優先度は鮮度・根拠の広がり・材料種別・Watchlist一致だけから決め、投資魅力度や順位ではない。
- candidate詳細には、候補理由、根拠記事、鮮度、材料構成、銘柄DB/価格/RAGの状態、確認不足、Cockpit handoffを集約した。候補選択や画面遷移だけでは外部取得、RAG、LLM、保存を開始しない。

## RAG根拠束

`根拠を確認（ローカルRAG）` の明示操作でのみ `RadarResearchContext` と `RadarEvidenceBundle` を生成する。既存のhybrid retrievalとrerankerを再利用し、短いsymbol・カテゴリ・見出し文脈だけを検索語に渡す。本文全体やprovider raw payloadはUI stateおよびGatewayへ渡さない。

- citationは安定ID、資料種別、公開時刻、検索時刻、鮮度、直接性、短い抜粋を持つ。
- 選択候補と異なるsymbol、候補ニュース時点より未来の資料、relevance floor未満の資料は採用しない。
- 資料なし・低関連度・取得失敗は `confirmation_gap` / unavailableとして表示する。候補の色、位置、順位、scoreには変換しない。

## AI根拠整理

`radar_interpretation.v1` は既定で無効であり、RAG根拠束がある候補で利用者が明示操作したときだけ実行する。候補ID、ニュース根拠ID、local RAG citation IDだけをGateway-safe contextに含め、Ranking・Forecast・価格・外部記事本文・provider raw fieldは送らない。

- Gateway応答はcandidate/evidence ID、引用対応、文字数、投資助言・score/rank変更表現を検証する。
- 不明な引用、助言表現、schema不正、Gateway/provider/timeout失敗は採用せず、`この根拠だけでは判断できません`という決定論的な確認メモを表示する。
- LLM結果は説明・注意点・未確認点・次の確認の整理に限定し、候補追加、直接言及への昇格、候補マップの位置・色・順序、Ranking、Forecast、Investment Score、Research Scoreを変更しない。

## 検証と残課題

network-freeのcandidate、RAG、AI契約、既存News UI回帰、設定回帰を実行した。通常画面のStreamlit AppTestでは、追加候補マップと明示RAG操作の表示を確認した。

2026-07-13のR4確認では、保存を伴わない明示live Google News RSS取得で100 headline・9 category laneを正規化し、direct 21件 / inferred 26件 / macro proxy 9件の計56候補がすべて根拠IDを持つことを確認した。7203.Tの既存local資料を一時メモリだけに読んだcandidate RAGでは4 citationを取得し、公開日が古いことを全件`stale`として表示した。Radar Gatewayは設定上既定どおり無効であり、接続せず決定論的な`disabled` fallbackを表示した。起動中StreamlitのHTTP応答は200だった。

この実行環境ではin-app browser runtimeを利用できなかったため、iPhone/iPad/PCのlive responsive smokeは未実行とした。通常端末では次を実行して確認する。

```powershell
$env:SMAI_RUN_RESPONSIVE_SMOKE = "1"
.\venv_SMAI\Scripts\python.exe -m pytest tests/ui/test_responsive_investment_radar_smoke.py -q
Remove-Item Env:SMAI_RUN_RESPONSIVE_SMOKE
```

Gatewayを有効にする場合も、通常pytestとは別のローカルGateway環境で、未知の引用・助言表現・timeout・schema不正がfallback表示になることを確認する。実機Safari/PWAも未確認である。AI候補追加やNews Score化はこのスプリントの対象外である。
