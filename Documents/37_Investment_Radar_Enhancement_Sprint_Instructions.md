# 投資レーダー強化スプリント 指示書

作成日: 2026-07-13

## 次セッションへ渡す依頼文

```text
投資レーダーを、ニュースと市場の変化を見る画面から、根拠をたどって確認候補を絞り込める探索画面へ強化してください。

まず `AGENTS.md`、`PROJECT_CONTEXT.md`、`Documents/05_Implementation_Roadmap.md`、
`Documents/35_RAG_Improvement_Sprint_Report.md`、`Documents/06_MVP_Operations_Guide.md`、
`backend/news/`、`backend/research/`、`backend/assistant/`、`ui/views/news.py`、
関連tests、必要なら `smai-ai-gateway/` を確認し、実コードとテストを正として現状を把握してください。

目的は、直接言及・SMAI推測・マクロ代理指標を混同せず、ニュース由来の追加候補、
根拠資料、未確認事項、次の確認を一つの導線にすることです。候補マップは探索・確認用であり、
ランキング、Forecast、Investment Score、Research Scoreの既定weight、売買判断を変えてはいけません。

この指示書の「必須スコープ」「安全境界」「完了条件」「検証」「成果物」を守り、
小さく一貫したvertical sliceで実装、テスト、必要文書更新、git diff確認、commit、pushまで完了してください。
作業開始時点の未関連差分・runtime artifact・別スプリントの変更は、変更・混入・破棄しないでください。
```

## 1. スプリントの目的

投資レーダーを、次の二つを両立する確認型の市場探索画面へ改善する。

1. **候補探索の明瞭化**
   - 市場ニュース、カテゴリ、Watchlist、銘柄DBから、次に確認する候補を表示する。
   - 本文に出た銘柄、SMAIの関連候補、マクロ代理指標を明確に区別する。
   - 候補が表示された理由、根拠の鮮度、ソースの広がり、未確認事項を追跡可能にする。

2. **根拠確認の深化**
   - 選択候補に対し、既存hybrid RAGを根拠確認として再利用する。
   - LLMは、検証済みの候補・根拠IDだけを使う説明・要約・確認点の整理に限定する。
   - RAGやLLMの不足・失敗・staleを、投資魅力度や数値スコアへ暗黙に変換せず、確認不足として表示する。

このスプリントは、探索効率、根拠性、情報の鮮度・不確実性の可視化を上げる。
Ranking順位、Investment Score、Research Score既定weight、Forecast値、銘柄DBの正規データ、
broker連携、売買行為を変更するスプリントではない。

## 2. 現在の土台

実装済みの機能は削除せず、責務を保ったまま再利用・統合する。

- `backend/news/`
  - `dashboard.py` が正規化済み `NewsHeadlineCard` から `NewsDashboardSnapshot`、カテゴリlane、ヒートマップcellを決定論的に構築する。
  - `sources.py` がGoogle News RSS / fixtureの取得、URL・タイトル重複除去、直接言及、SMAI推測、マクロ代理指標の抽出を担う。
  - `contracts.py` には `NewsSymbolMatch`、`NewsHeadlineCard`、`NewsHeatmapCell`、将来のLLM再確認用contractがある。
- `ui/views/news.py`
  - 現行の市場ヒートマップ、カテゴリ・鮮度・ソース・Watchlist filter、ニュースカード、Cockpit handoffを描画する。
  - ヒートマップ候補選定にはUI側の表示ロジックが残るため、追加候補のdomain logicは新しいbackend serviceへ置く。
- `backend/research/`
  - keyword + vectorのhybrid retrieval、reranker、`ResearchRetrievalQuality`、relevance floor、`confirmation_gap`を実装済み。
  - 資料不足を低スコアや投資魅力度に変換せず、確認不足として保持する。
- `backend/assistant/` と `smai-ai-gateway/`
  - Gatewayを使う場合も、親SMAIがtyped contract、schema validation、timeout、sanitization、fallbackを管理する。
  - GatewayはSMAI本体moduleをimportせず、SMAIに対する実行権限を持たない。
- User data / UI
  - Watchlistは`user_id`境界を持つ。Cockpit handoffはsame-app navigationを使い、外部取得や保存を自動実行しない。

現在の実装状況はコードとテストを正とする。本書と実コードに差があれば、実装前に最小限の現状表を作り、対象文書だけを更新する。

## 3. 必須スコープ

### 3.1 決定論的な追加候補マップ

既存の市場ヒートマップを置き換えず、その下または詳細導線に「追加候補マップ」を追加する。

- `RadarCandidate`、`RadarCandidateEvidence`、`RadarCandidateMap`などのtyped contractを導入する。
- candidateは最低限、symbol、表示名、market、asset type、候補由来、カテゴリ、根拠ID群、鮮度、独立ソース数、Watchlist関連、データ状態、確認不足を持つ。
- 候補由来は少なくとも以下を分け、表示上も同じ色・ラベルに混ぜない。
  - `direct_mention`: 記事本文または見出しに明示された銘柄
  - `inferred_candidate`: テーマ・カテゴリ・ローカル銘柄DBからのSMAI推測候補
  - `macro_proxy`: 市場全体の背景確認用の指標・代理銘柄。通常の銘柄候補にはしない
- 追加候補マップの表示意味を固定する。
  - 横軸: 根拠の直接性
  - 縦軸: 確認優先度（鮮度、重複除去後の根拠数、材料種別、Watchlist関連性）
  - 円の大きさ: 根拠の広がり
  - 色: 好材料 / 注意材料 / 混在 / 判断不能
  - 形: 候補由来
  - 枠線: 銘柄DB・価格・RAG根拠のデータ状態
- 「確認優先度」は投資魅力度、期待収益、買い推奨、ランキング順位として表現しない。計算要素を詳細で説明し、各要素を追跡できるようにする。
- 候補ID、表示順、dedupe、同点時の順序はnetwork-freeでdeterministicにする。候補の根拠が一件も追跡できない場合は表示しない。

### 3.2 候補詳細と探索UX

- 候補クリック時に、次を一つの詳細surfaceで表示する。
  - 「なぜこの候補か」: 根拠記事・カテゴリ・直接性・Watchlist関連
  - 「材料の構成」: 好材料、注意材料、混在、判断不能
  - 「データの状態」: ニュース鮮度、銘柄DB/価格の取得状態、RAG確認状態
  - 「次の確認」: RAG根拠確認、Cockpitを開く、外部資料を確認する場合の明示操作
- 既存filterに加え、market、asset type、候補由来、RAG確認状態、Watchlist一致で絞り込めるようにする。デフォルトは直接言及候補を優先し、推測候補は表示上で常に明示する。
- RAG・LLM実行、外部ニュース更新、Cockpitのデータ取得、保存、レポート作成を、画面表示や候補クリックだけで開始してはいけない。
- PCでは地図と詳細を並べて比較できるようにし、iPhoneでは地図、選択中候補、根拠、詳細の順に縦積みする。表・地図だけに必要な内部スクロールは許可するが、ページ全体の横スクロールを発生させない。

### 3.3 候補単位のRAG根拠束

- 明示的な`根拠を確認`操作でだけ、選択候補向け `RadarResearchContext` / `RadarEvidenceBundle` を生成する。
- queryはsymbol、カテゴリ、ニュース時点、候補根拠を使って縮約し、既存のhybrid retrieval、reranker、relevance floorを再利用する。巨大なraw本文やprovider fieldをUI state / Gatewayへ渡さない。
- citationにはstableなevidence ID、source type、公開時刻、取得時刻、鮮度、直接性を持たせる。ユーザー画面には短い引用・要約・出典リンクを表示し、raw URLや技術情報は必要時だけ詳細に畳む。
- 取得時点より未来の資料を混ぜない。ニュース転載・同一URL・同一文書近接chunkの重複を抑制し、独立根拠数を表示する。
- 根拠がない、関連度が低い、文書がstale、取得に失敗した場合は`confirmation_gap` / unavailableとして扱う。空の結果を良い・悪いシグナル、候補順位、scoreへ変換してはいけない。
- 外部資料の取得は既存のapproved flowだけを使い、ユーザー確認後に限る。RAG本文を新規に永続archiveすることは本スプリントの対象外とする。

### 3.4 根拠限定のLLM解釈メモ

- RAG根拠束がある選択候補に限り、opt-inの`radar_interpretation.v1`を導入する。初期対象は一画面で最大5候補程度に制限する。
- response contractは少なくとも次を持ち、自由文だけを採用してはいけない。
  - `candidate_id`
  - `summary`
  - `positive_materials`
  - `cautions`
  - `unknowns`
  - `next_checkpoints`
  - `cited_evidence_ids`
- 親SMAIはcandidate ID、evidence ID、文字数、schema、引用対応、unsafe wordingを検証する。候補束にない銘柄・数値・日付・事実を追加した出力は不採用とし、決定論的な確認メモへfallbackする。
- LLM出力はRanking、Forecast、Investment Score、Research Score、追加候補マップの位置・色・順序を変更してはいけない。
- 既存の`NewsSymbolLLMExtractionRequest/Response`を実運用で候補追加に使わない。まずはfixtureとラベル付き評価集合でshadow-only評価し、将来も直接言及ラベルへ昇格させない。
- Gateway停止、provider/model不足、timeout、malformed response、cache失敗時も画面を止めない。通常表示は次の確認を示し、技術原因は詳細表示に限定する。

### 3.5 評価・回帰の設計

- 実装前に、candidate map / RAG / LLMそれぞれの正常系と失敗系をfixture化する。
- 少なくとも次を評価集合に含める。
  - 国内株、米国株、ETF / REIT、複数market・asset type
  - 本文直接言及、テーマ推測、マクロ代理、Watchlist一致、銘柄なしニュース
  - 転載・重複ニュース、古いニュース、資料不足、関連度不足、provider失敗
  - 正負材料の混在、候補名の曖昧さ、誤った同名・短いalias候補
  - LLMの未知銘柄、根拠外数値、引用不一致、投資助言表現、timeout / schema failure
- 受入gateは少なくとも以下を守る。
  - 表示candidateはすべて根拠IDへ戻れる
  - 直接言及 / 推測 / macro proxyの混同がない
  - RAG引用は選択candidateの許可済みevidence IDのみ
  - LLMの根拠外銘柄・根拠外数値・unsafe wording採用は0件
  - 資料不足・取得失敗がscoreや順位を変えない
  - default画面描画はnetwork / Gatewayを待たない

## 4. 推奨する実施順序

1. **R0: 現状監査と評価契約**
   - 現行snapshot、ヒートマップ、symbol extraction、filter、Watchlist handoff、RAG、LLM boundaryの実装とtestsを確認する。
   - candidate map用fixture、provenance、dedupe、直接性、確認不足の期待値を先に固定する。

2. **R1: 決定論的な追加候補マップ**
   - `backend/news/`へ候補生成serviceとcontractを追加し、UI表示ロジックからdomain logicを分離する。
   - existing market heatmapを維持したまま、候補マップ、filter、詳細、Cockpit handoffを追加する。
   - 通常テストはfixture / static snapshotのみで完結させる。

3. **R2: RAG根拠束**
   - existing hybrid retrievalを候補確認へ接続し、citation、鮮度、検索品質、confirmation gapを候補詳細へ表示する。
   - 自動外部取得や自動保存を導入せず、local / cached materialsを優先する。

4. **R3: AI解釈メモ**
   - Gateway / parent contract、validator、sanitizer、cache、fallbackを小さなvertical sliceで実装する。
   - LLMの候補追加はshadow-onlyに留め、説明・確認点の整理だけを表示する。

5. **R4: UI・live smoke・文書**
   - PC、iPhone、iPadで候補→根拠→Cockpitの導線を確認する。
   - live RSS / live Gatewayは明示opt-in smokeとして実行し、通常pytestと混同しない。
   - 実装済み範囲、運用、UI文言、残リスクだけを文書更新する。

6. **commit / push**
   - 各sliceは、関連コード・tests・必要最小限の文書だけをstageする。
   - 既存dirty worktreeの未関連差分、cache、ログ、スクリーンショット、他スプリントの成果物を混ぜない。

## 5. 明示的な非スコープ

- Ranking順位、Investment Score、Research Score既定weight、Forecast値、上向き兆候の計算変更
- 候補マップを売買推奨、期待収益、目標価格、確定的な反発予測として見せること
- broker / 証券会社接続、注文、約定、資金移動、自動売買
- 確認なしのニュース更新、外部資料取得、RAG本文保存、Decision Report保存
- LLMによる銘柄の自動追加、直接言及ラベルへの自動昇格、候補順位/地図座標の変更
- 通常CIでのlive provider、Ollama、外部LLM依存
- GatewayからのSMAI Python module import、GatewayによるSMAI action直接実行
- user_id境界を越えるWatchlist・Radar状態・保存結果の共有
- 既存`ui/views/news.py`全体の無関係な書き換え、大規模UI framework置換

これらに着手する必要が判明した場合は、実装前に必要性、影響、代替案を説明してユーザーに確認する。

## 6. 完了条件

以下を、適用可能な範囲で満たすこと。

- 追加候補マップが既存市場ヒートマップを壊さず、候補の由来・根拠・鮮度・未確認事項を示す。
- candidate生成は決定論的で、dedupe、tie-break、direct/inferred/macro proxy分離をテストで証明する。
- candidate詳細から、根拠確認とCockpit handoffへ安全に進める。画面遷移だけで外部取得や保存が始まらない。
- RAG結果は引用、鮮度、検索品質、確認不足を示し、資料不足を魅力度や順位へ変換しない。
- LLMの採用結果はcandidate/evidence ID、schema、sanitization、投資助言禁止を通過したものだけである。
- Gateway / provider / schema / timeout failure時に決定論的fallbackを表示し、Radarの閲覧を継続できる。
- Ranking、Forecast、Investment Score、Research Score既定weight、user data boundary、external-fetch policyを変えない。
- 新規・変更済みの振る舞いをnetwork-free testsで証明する。
- UI変更はPC、iPhone、iPadを確認し、横はみ出し、例外、タップ領域、候補→根拠→Cockpit導線を確認する。
- `git diff`にsecret、raw provider payload、raw RAG本文、不要なruntime cache、未関連変更を含めない。

## 7. 検証の標準セット

対象に応じて絞り込みつつ、handoff前に実行結果を報告する。

```powershell
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_news_dashboard_service.py tests/test_ui_news_view.py tests/test_ui_news_streamlit_page.py -q
.\venv_SMAI\Scripts\python.exe -m pytest tests/test_research_service.py tests/test_research_external_fetch.py -q
.\venv_SMAI\Scripts\python.exe -m ruff check backend/news backend/research backend/assistant ui/views/news.py tests --no-cache
.\venv_SMAI\Scripts\python.exe .\tools\run_black_check.py
```

追加で確認する候補:

```powershell
# 新規Radar candidate / RAG / LLM contract testsを追加後に対象を指定して実行
.\venv_SMAI\Scripts\python.exe -m pytest tests -q -k "news or radar or research or llm"

$env:SMAI_RUN_RESPONSIVE_SMOKE = "1"
.\venv_SMAI\Scripts\python.exe -m pytest tests/ui/test_responsive_investment_radar_smoke.py -q
Remove-Item Env:SMAI_RUN_RESPONSIVE_SMOKE

# Gatewayを起動した通常端末だけで、明示opt-inのRadar LLM smokeを実行
```

live RSS、外部資料取得、Gateway / Ollama、実機Safari / PWAの確認は、通常pytestとは分離したopt-in smokeとする。実行できなかった確認を成功扱いにせず、理由と再実行方法を残す。

## 8. 成果物とhandoff

- `backend/news/`のcandidate map / RAG / LLM境界と対象tests
- 必要最小限の`ui/views/news.py`、共通UI文言、responsive smoke
- 必要に応じたGateway contract / Gateway test。ただしGatewayはSMAI本体をimportしない
- 必要最小限の`PROJECT_CONTEXT.md`、Roadmap、Operations Guide、UI wording policy、短いスプリント報告
- candidate provenance、RAG citation、LLM safety、fallback、responsiveの評価結果
- changed files、変更理由、実行結果、未実行確認、残リスク、commit hash、push結果を含む完了報告

## 9. 優先順位の判断

次の順で優先する。

1. candidate根拠の取り違え、direct/inferred/macro proxy混同、user/session境界、投資助言表現
2. RAG citation不一致、future資料混入、資料不足をscore化する経路、LLMの根拠外出力採用
3. fallback不能、外部障害での画面停止、重複候補、重複実行、Cockpitへの誤handoff
4. 候補詳細・filter・地図の可読性、モバイルの操作性、パフォーマンス
5. LLM候補再確認のshadow評価や、追加Provider・高度な関係グラフ

新機能を増やす前に、候補がどの根拠から来たか、何が未確認か、次に何を確認するかを、決定論的に説明できる状態を優先する。

## 10. 設計参考

- [TradingView Stock Heatmap](https://www.tradingview.com/heatmap/stock/): セクター、国、時価総額を使う市場マップの参考。SMAIは同等の外部データ取得を前提にせず、表示構造だけを参考にする。
- [Finviz S&P 500 Map](https://finviz.com/map.ashx): 地図とスクリーナーを分ける探索導線の参考。SMAIでは候補マップをランキングの代替にしない。
- [Koyfin Market Dashboards](https://www.koyfin.com/features/market-dashboards/): マクロ・市場データを一画面で横断する構成の参考。
- [Azure AI Search Hybrid Search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview) と [Elastic hybrid search](https://www.elastic.co/guide/en/elasticsearch/reference/current/semantic-text-hybrid-search.html): keyword / vector融合の参考。SMAI既存hybrid retrievalを優先して再利用する。
- [Temporal-Aware Multi-Modal RAG in Finance](https://arxiv.org/abs/2503.05185) と [FinRAGBench-V](https://aclanthology.org/2025.emnlp-main.211/): 金融RAGにおける時点、複数資料種別、citation traceabilityの評価観点の参考。研究結果を投資成績の保証として扱わない。
