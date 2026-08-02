# 46 大規模リファクタリング計画

## 1. 目的

SMAIの機能拡張を止めずに、責務境界、依存方向、フォルダ構成、テスト容易性を段階的に改善する。
この作業では数値ロジックの変更を構造変更へ混ぜず、Forecast、Ranking、Scoring、Riskの意味と結果を
維持する。単一の巨大差分で全ファイルを移動せず、互換importと回帰テストを伴うvertical sliceで進める。

## 2. 2026-07-20時点の監査結果

主要な肥大化箇所は次のとおり。

| ファイル | 行数 | 主な問題 |
|---|---:|---|
| `ui/app.py` | 23,468 | composition、状態管理、取得、計算、整形、描画が集中 |
| `ui/styles.py` | 9,384 | Pythonと大規模CSS定義が同居 |
| `backend/research/service.py` | 8,791 | 複数のResearch use caseと整形処理が集中 |
| `ui/views/copilot.py` | 5,585 | 会話制御、action、表示が集中 |
| `ui/views/news.py` | 3,893 | 取得状態、presenter、画面表示が集中 |
| `ui/ranking.py` | 2,864 | universe policy、scoring policy、表示向け補助が混在 |

静的import監査では238 Python module、692内部依存edgeを確認した。特に次を優先課題とする。

- `backend.investment_candidates.exporter -> ui.ranking`という逆向き依存が1件ある。
- `ui.app`の内部module fan-outが57で、application composition rootとしても過大である。
- `backend.assistant` / `backend.news`周辺と`backend.research`周辺にpackage exportを含む循環がある。
- `backend.research`、`backend.forecast`、`ui/views`はpackage単位でも大きく、変更影響の局所化が弱い。

行数は品質そのものではないが、複数責務の同居と変更理由の多さを示す警告として利用する。
`tools/audit_python_architecture.py`は、全importをfan-outとして数えつつ、module import時に実行される
eager importだけを循環判定に使う。関数内のlazy importと`TYPE_CHECKING`を実行時循環として誤報しない。

## 3. 依存方向

許可する基本方向は次のとおり。

```text
composition roots (ui/app.py, backend/app, scripts, tools)
    -> UI views/controllers / API routes
        -> application use cases
            -> domain policy + typed contracts
                -> repository/provider/gateway ports

edge adapters (Streamlit, FastAPI, Yahoo, SQLite, HTTP Gateway)
    -> portsを実装し、composition rootで注入
```

禁止・抑制する方向:

- `backend`から`ui`をimportしない。
- domain計算からStreamlit、FastAPI、HTTP client、filesystem実装を直接参照しない。
- UI描画関数から永続化やProvider固有処理を新設しない。
- package `__init__.py`で多数の実装moduleをeager importしない。
- LLM自由文からdeterministicなForecast、Ranking、Scoring結果を上書きしない。

## 4. 目標フォルダ構成

一律に全domainへ空ファイルを作らず、分割が必要になったdomainから次の語彙へ揃える。

```text
backend/<domain>/
    contracts.py       # 外部公開するtyped data contract
    ports.py           # repository/provider/gateway Protocol
    policies.py        # 純粋・決定論的な判断と計算
    service.py         # use case orchestration
    repository.py      # local persistence adapter
    gateways.py        # external adapter（必要なdomainのみ）
    evaluation.py      # runtimeと分離した検証（必要なdomainのみ）

ui/views/<feature>/
    page.py            # Streamlit layout / widget
    controller.py      # session stateとuse case呼出し
    presenter.py       # domain resultから表示modelへの純粋変換

ui/components/         # 複数画面で再利用する表示部品
ui/content/            # 日本語文言・凡例・警告
ui/assets/styles/      # base / component / page別CSS
```

既存公開importを使う呼出元が多い場合、元moduleは薄いcompatibility façadeとして一定期間残す。
新旧経路が同じcallable、contract、結果を返すことをboundary testで証明してから削除する。

## 5. 実施順序

### 5.1 評価結果と改訂方針

2026-08-02時点で、R0とR1は目的どおり依存境界とRanking application flowを固定できている。
一方、従来計画には次の改善余地があった。

- R1完了後も上位ロードマップにR1途中の作業が残り、現在地が一致していなかった。
- R2以降は一つの項目が大きく、次のcommitで何を移し、何を残すか判断しにくかった。
- 構造改善、Forecast / LLMの評価データ成熟待ち、Notification N6実接続が同じ待ち行列に見えた。
- 各段階の開始条件、完了条件、runtime採用を止める条件が十分に明示されていなかった。

このため、以降は作業を次の3トラックに分ける。

| トラック | 役割 | 現在地 | 実行ルール |
|---|---|---|---|
| A: 構造改善 | R2からR6までの責務分離 | R2進行中 | 主実装トラック。評価データの成熟を待たず進めてよい |
| B: 評価・観測 | Phase 35 / 36、sealed Forecast audit | 成熟待ち | 収集・集計は継続可能。採用gate通過前は数値、順位、runtime weightを変えない |
| C: 運用接続 | Notification N6、live Provider / Gateway接続 | foundation完了、実接続待ち | user境界とportが固定された機能から小さく接続し、通常testはnetwork-freeに保つ |

トラックBの待機はトラックAを止めない。トラックCも独立して進められるが、分割中の巨大UIや
aggregate serviceへ新しいProvider処理を直接追加せず、対象domainのcontroller / port境界が
確定してから接続する。

### 5.2 優先実行順

| 優先 | 作業単位 | 着手条件 | 完了後に可能になること |
|---:|---|---|---|
| 1 | R2-B Research / Report context分離 | 現行Cockpit state / presenter testがgreen | Cockpitの取得・組立・描画を独立検証できる |
| 2 | R2-C presenter / page境界の完了 | R2-B contextと同値testが固定済み | `ui.app`を互換composition rootへ縮小できる |
| 3 | R3-A〜C Research use case分割 | R2完了、既存Research contract baseline固定済み | ResearchとN6 event接続を安定したportへ接続できる |
| 4 | R4-A〜C Copilot / News / CSS分割 | R3完了、対象画面のstate / responsive baseline取得済み | 主要画面の責務とresponsive回帰範囲を局所化できる |
| 5 | R5 package cycle / 公開API整理 | R2〜R4の互換façade一覧が確定 | compatibility façadeの段階削除を始められる |
| 6 | R6 継続gate | R5 architecture auditがgreen | 新しい肥大化と逆依存をCIで検知できる |

各作業単位は構造変更だけを含む。金融数値、Provider選択、LLM prompt、通知配信条件を変える場合は、
別の設計判断、commit、回帰確認を用意する。

### R0: 境界を機械的に固定（🟦 完了・継続監視）

- backend-to-UI逆依存をport / adapterへ反転する。
- `backend`から`ui`へのimport禁止testを追加する。
- Assistant / News間のpackage façade相互参照を直接contract importへ置き換える。
- module数、内部edge、eager cycle、巨大module / function、fan-outを再実行可能なCLIで監査する。
- 構造変更で予測値、ranking順、scoreが変わらないことを明示する。

### R1: Ranking application flowを`ui.app`から分離（🟦 完了）

- 入力条件、job request、進捗、結果、sanitized errorをtyped contract化する。
- MarketData取得とranking orchestrationをUI非依存use caseへ移す。
- Streamlit session / job registryはcontroller adapterに限定する。
- 既存function名はcompatibility façadeとして残し、CLIとテストを新use caseへ移行する。

完了内容:

- 副作用のないpolicy説明、上向き兆候の点数表、条件summary HTMLを
  `ui/ranking_policy_presenter.py`へ移した。
- `RankingBuildRequest` / `RankingBuildResult`と`RankingBuildService`をbackend側へ追加し、cache再利用、
  銘柄DB preflight、MarketData build、結果publishの順序をStreamlit非依存serviceへ移した。
- `ui/ranking_application.py`にpreflight / MarketData builder adapter、typed job起動controller、matchingした
  完了jobをbrowser sessionごとに一度だけ採用するcontroller adapterを分離した。
- live cohort、高速build、fixture preview fallback、live失敗時のfail-closed error rowを選ぶ外側pipelineを
  Streamlit非依存にした。
- OHLCV / Quote / FX入力、fundamental、feature、Forecast consensus、Screening / Investment Score、
  表示enrichment / sortをそれぞれ`RankingMarketDataInputs`、`RankingFundamentalInputs`、
  `RankingFeatureInputs`、`RankingForecastInputs`、`RankingScoreInputs`、`RankingPresentationInputs`の
  typed境界へ分離した。
- large cohortの上位候補だけへadvanced Forecastを適用するoptional orchestrationを分離し、bounded candidate、
  失敗隔離、cache release、再sortをStreamlit非依存にした。

既存のrows / error rows / source / timestamp / ranking history handoff、provider / cache挙動、進捗cadence、
数値ロジック、最終順位を維持する。描画と`st.rerun()`はUI edgeに残し、既存function名はcompatibility
façadeとして新use caseへ委譲する。以上をもってR1は完了し、主実装はR2へ移行した。

### R2: Cockpit application flowを分離（🟨 進行中）

- symbol/date/provider選択、取得、Forecast実行、表示model生成を分ける。
- `page`、`controller`、`presenter`を分離し、rerun時state contractを固定する。

進捗: 最初にfilter defaults、active-condition判定、universe絞り込み、keyword / alias / sector /
theme検索順位を`ui/cockpit_filter_policy.py`へ分離した。新moduleはStreamlit stateを参照せず、
`ui.app`にはsession stateの読書きと描画を残した。続いて`ui/cockpit_application.py`へ
`CockpitPreviewRequest`、preview load、preview/session state採用を分離した。symbol、期間、provider、
forecast horizonの入力と、preview、status、forecast days、chart display currencyの更新境界を固定し、
widget、progress、error/toast、後続renderは`ui.app`に残した。さらに`CockpitDisplayModel`へ、同一horizonの
Forecast chart、consensus、metrics、高度Forecast、score display rowsを組み立てる順序を移した。既存Forecast
functionはUI edgeから注入し、renderとinteractive stateは`ui.app`に残す。`CockpitPresentationContext`で
symbol labelとdisplay modelをhero・technical detail presenterへ共通入力として渡し、個別row引数を廃止した。
summary、Research、Decision Reportとinteractive renderingは引き続き`ui.app`に残す。
その後、preview、status、forecast horizon、chart display currencyを
`CockpitPreviewState` / `CockpitPreviewSessionKeys`に集約した。previewが存在する場合はその
statusとhorizonを正とし、Ranking / RadarからCockpitへ遷移する際は4つのpreview-owned stateを
まとめて破棄する。これにより古いpreviewの補助状態が次の銘柄表示へ残らない。Forecast、Score、
Research取得、render順は変更しない。

残りは次の2 sliceに固定する。

#### R2-B: Research / Decision Report contextを分離

- summary、Research、Decision Reportが参照する入力をtyped contextへまとめる。
- MarketData / Forecast / Researchの取得、表示用組立、Streamlit描画を別のcallableにする。
- Assistant / Reportへ渡すsymbol、horizon、根拠、warning、data qualityの意味を維持する。
- widget、progress、toast、download、rerunはUI edgeに残す。
- 取得失敗と根拠不足を空の正常値へ変換せず、既存のwarning / unavailable表示を維持する。

進捗（2026-08-02）: 初回sliceとして`CockpitSummaryContext`、`CockpitResearchContext`、
`CockpitDecisionReportRenderContext`を追加した。symbol一致を確認済みのResearch / news /
external resultを一度だけ解決し、LLM材料、確認メモ、Decision Reportへ同じsnapshotを渡す。
Decision Reportのoverview、要約、根拠行、score、symbol metadataはStreamlit描画前にcontextへ固定する。
header summaryも同じ方法で入力を固定する。外部取得、更新progress、toast、`st.rerun()`はUI edgeに残し、
Forecast、Score、Research Score、Decision Report本文、出典順は変更していない。

続くR2-B sliceでは、外部Research取得、企業Research report生成、stock news report生成を、
UIのbutton / progress表示から分離したuse caseへ移す方針とした。contextは取得済み値を安全に共有する層であり、
Provider呼出しやsession mutationを保持しない。

進捗（2026-08-02、続き）: `run_cockpit_research_refresh`へ外部Research取得、企業Research report生成、
stock news report生成の実行順、progress event、処理時間trace、外部取得失敗時の継続を移した。成功した外部結果、
report、news reportは各builder直後に注入したpublisherからUI stateへ採用するため、後段の失敗で既に得た
session-local根拠を失わない。UIはbutton、loading、通知、技術詳細、trace表示、`st.rerun()`だけを担当する。
use caseはStreamlit / session state / Provider実装をimportせず、fixture clockとcallbackで成功・外部失敗経路を
検証する。次のR2-B判断は、Research操作cardと表示panelをpage / controllerへ分けるか、R2-Cへ進むかで行う。

完了条件:

- context builderがStreamlit非依存で、fixtureによる単体testを持つ。
- Research / Reportの主要fieldと出典順が移動前後で一致するboundary testがある。
- Forecast、Score、Research Score、Decision Report本文の計算・意味を変更しない。

#### R2-C: presenter / page境界を閉じる

- hero、Forecast、score、risk、Research、report、technical detailのpresenter入力を明示する。
- `ui.app`はnavigation、dependency wiring、session controller、page呼出しを担うcomposition rootへ縮小する。
- interactionを伴うcard、button、expander、downloadはpage側に残し、純粋な表示変換だけをpresenterへ移す。
- 互換importを残す場合は移行先と削除条件を明記する。

進捗（2026-08-02、初回slice）: Research操作cardのtitle、要約、根拠状態chip、注目/注意材料、
button labelを`ui/cockpit_research_presenter.py`のStreamlit非依存modelへ移した。HTML、button、
widget keyは`ui/views/cockpit.py`へ集約し、`ui.app._render_research_operation_card`は既存caller向けの
compatibility façadeとしてmodelとpage componentへ委譲する。Cockpitの取得済みResearch結果についても、
未取得時のexternal/news fallbackと通常panelへの振り分けをpage componentへ移し、app controllerは
context解決、refresh use case、通知、rerun、既存panel rendererの注入だけを担当する。Research内容、
根拠数、出典順、button key、更新操作、Forecast / Score / Ranking数値は変更していない。次sliceでは
Research詳細panelとDecision Reportの表示modelを同じ境界で縮小する。

進捗（2026-08-02、第二slice）: `CockpitDecisionReportRenderContext`を入力として、確認レポートの
overview cardとAI要約HTMLを`ui/cockpit_decision_report_presenter.py`へ、見出し、根拠表、詳細section、
ダウンロード導線を`ui/views/cockpit.py`のpage componentへ移した。`ui.app`はcontext組立と、既存table、
detail section、download、assistant contextへのadapter注入だけを持つ。Report本文、overview field、
summary上限3件、根拠行、download file名、assistant context、数値計算は変更していない。次sliceでは
Decision Reportのdetail section内部をcontext対応のpresenterへ段階移行する。

進捗（2026-08-02、第三slice）: 確認レポート詳細の確認方針、score、価格・予測、
fundamental、valuation、risk、根拠資料、補足の行を`CockpitDecisionReportDetailModel`へ固定した。
modelは上部表示と同じ`CockpitDecisionReportRenderContext.evidence_rows`を再利用し、詳細側で根拠行を
再計算しない。expander、table、根拠card、empty state、補足表の描画はpage componentへ集約し、app側は
既存row builderとrenderer adapterを注入する。詳細sectionの順序、初期展開状態、根拠cardの上限、
empty message、数値と出典の意味は変更していない。次sliceではCockpit Research詳細panelの同様の分離を
評価する。

R2完了gate:

- Cockpitの主要application flowにStreamlit非依存のcontract / controller / presenter境界がある。
- Ranking / Radar handoff、rerun、preview invalidation、user切替で旧stateが混ざらない。
- Desktop 1366x768、iPhone 375x812、iPad相当viewportで不要なpage横scrollがない。
- 移動前後のfixtureでForecast chart、score、Research、Reportの主要出力が一致する。

### R3: Research serviceをuse case別に分割（🟨 第一slice完了・R2後に再開）

- company profile、product/service、financial summary、evidence、external fetchを分ける。
- 正規化、要約、永続化、外部取得の境界を明示する。
- 現在の`backend.research`公開contractは互換testを維持する。

進捗: 第一sliceとして、事業分類、補助事業分類、製品・サービス分類、地域・顧客分類の
決定論的heuristicを`company_business_policy.py`と`company_product_policy.py`へ分離した。
`company_profile_policy.py`は薄いcompatibility façadeとし、`service.py`からstore、provider、UIに
依存しない約1,660行を除去した。次のsliceではsummary builderが依存する会社概要・定量・IR整形を
contract単位で分ける。R3-Aの開始後は、選択済み定量値の欠損状態・要約・出典組立を
`quantitative_summary.py`へ、選択済み会社概要値の`CompanyOverviewSummary`組立を
`overview_summary.py`へ移した。business profile / fact選択、規模・直近材料の導出、clip policy、
source収集はservice側に残し、既存contract値・citation順・fallbackをbuilder testで固定している。
続くIR sliceでは、serviceにsource card / candidate収集、分類、fact由来key point選択を残し、
分類済み候補から`IRSummaryItem`のmissing / found state、metadata、classification、evidence level、
表示文言を組み立てる責務を`ir_summary.py`へ移した。

#### R3-A: summary builderを分割

- 会社概要、定量、IR、最新ニュース・開示のfact selectionと表示用summaryをuse case別に分ける。
- source-backed fact、citation、published / acquired時刻、reliabilityを共通contractで維持する。
- 分類policy、文言整形、source選択を一つの関数へ再集約しない。

#### R3-B: evidence / external fetch / persistenceをport化

- evidence検索、外部取得、archive、cache / repositoryをProtocolとadapterへ分ける。
- timeout、schema、sanitization、point-in-time条件をserviceから追跡可能にする。
- live失敗時は既存archive / cacheを破損させず、staleとunavailableを区別する。

#### R3-C: façadeと公開contractを固定

- 既存`backend.research` importを薄いfaçadeで維持し、新use caseへ委譲する。
- contract同値、citation順、fallback、重複排除をboundary testで固定する。
- package eager cycleを増やさず、R5で削除する互換層を一覧化する。

R3完了gateは、主要Research use caseが個別にfixture検証でき、通常testが外部networkを必要とせず、
Research Score、Ranking順位、Forecast数値を一切変更していないことである。

### R4: UI viewとstyleを分割（⬜ R3後）

- Copilot / Newsをpage-controller-presenterへ分ける。
- `ui/styles.py`のCSSをbase、component、page assetへ分け、loaderだけをPythonへ残す。
- PC、iPhone、iPadのviewport回帰を各画面sliceで実行する。

進捗（2026-08-02、R4-A初回slice）: profile / model catalogue、profile fallback、option matching、
label変換を`ui/copilot_model_policy.py`へ分離した。このmoduleはStreamlit / Gatewayをimportせず、
viewはcatalog・session state選択、runtime status、widgetを維持する。既存のview helperは薄い
compatibility façadeとして残すため、Provider probe、timeout / fallback、conversation state、文言は不変である。

進捗（2026-08-02、R4-B初回slice）: News / Radarの鮮度、候補由来、データ状態、材料分類labelと
neutral material toneを`ui/news_display_policy.py`へ移した。viewはrefresh、cache / Provider、
user-scoped state、candidate生成、widgetを維持し、既存private名はcompatibility aliasで残す。
ニュース取得・候補・順位・保存・表示文言の意味は変更していない。

#### R4-A: Copilot

- conversation state、command dispatch、Assistant gateway呼出し、response presenter、widget描画を分ける。
- typed schema、timeout、fallback、sanitizationをcontroller境界で維持する。
- LLM失敗時もdeterministicな主要機能と保存済み会話を破損させない。

#### R4-B: News / Radar

- query / filter state、cache / provider取得、card model生成、page描画を分ける。
- user別Watchlist、news cache、Research sourceを暗黙に共有しない。
- N6はこのportまたはR3のResearch event portへ接続し、viewから通知を直接配送しない。

#### R4-C: CSS assets

- base token、共通component、page固有CSSの順に移し、読み込み順を固定する。
- selector衝突とunused ruleをsliceごとに確認し、一括rewriteを避ける。
- Desktop、iPhone、iPadでnavigation、modal、table / chart内部scroll、touch targetを確認する。

R4完了gateは、CopilotとNewsの取得・状態・表示変換が独立test可能で、主要画面のresponsive smokeが
通り、文言・色・指標単位・ユーザーデータ境界が移動前後で一致することである。

### R5: package cycleと公開APIを整理（⬜ R4後）

- `__init__.py`を薄くし、型だけのimportは`TYPE_CHECKING`へ寄せる。
- Assistant / News / Researchの循環を実依存と再export由来に分類して解消する。
- 公開API一覧とdeprecation期間を記録する。

完了gate:

- architecture auditで新しいbackend-to-UI逆依存とeager cycleが0件である。
- 公開contract、compatibility façade、内部moduleを一覧化し、削除条件が確認できる。
- import時にProvider接続、LLM起動、filesystem mutationなどの重い副作用を発生させない。
- façade削除は呼出元移行と回帰testが揃ったものだけを別sliceで行う。

### R6: 継続的な保守gate（⬜ 最終統合・以後継続）

- 新規moduleは原則600行以下、新規functionは原則80行以下を目安とする。
- 超過が適切な生成物、宣言表、CSS、schemaの場合は理由を文書化する。
- module dependency、巨大function、境界違反を定期監査し、単純な行数だけでCIを失敗させない。

完了gate:

- `tools/audit_python_architecture.py`のbaselineと許容例外がversion管理されている。
- 新しい逆依存、eager cycle、巨大functionの増加を説明付きで検出できる。
- 通常CIはnetwork-freeかつdeterministicで、live smokeは明示opt-inの別経路にある。
- 行数警告だけでなく、依存方向、責務数、test境界を保守判断へ使う。

## 6. 評価・運用トラックの採用gate

### 6.1 Forecast / Phase 35 / Phase 36

- sealed auditはhorizonごとに最低100件の成熟結果が揃うまでruntime採用判断へ使わない。
- range / calibration候補はtarget coverage 60%、最低coverage 55%、proper interval score 1%以上改善、
  適用率50%以上という既定gateを満たす。結果を見て閾値を下げない。
- Phase 35は新規symbol / 新規期間のwalk-forward holdoutで評価し、既存監査群を再調整に使わない。
- aggregate改善だけで採用せず、market、asset type、regime、confidence、disagreement別の大幅劣化を確認する。
- Phase 36の材料収集・Gateway評価はpoint-in-time条件を維持し、未来の公開・取得情報を混ぜない。
- Phase 36のbadge評価は完了30件かつ評価日3日以上を最低条件とし、failure率5%超なら不採用とする。
  条件を満たしても`badge_only_candidate`までとし、rank / score correctionはfalseのまま維持する。
- LLM材料によるForecast range / confidence変更は、別途100件/horizonの時点整合caseで評価し、
  方向値と中心値を変更しない。score、順位の補正はさらに独立した設計・監査を必要とする。
- latency、failure、citation、schema、cache、false positiveを記録し、失敗を「材料なし」と同一視しない。
- gate未達、結果未成熟、subgroup悪化、data leakage疑いがあれば不採用またはshadow継続とする。

Phase 37の本気分析モードはPhase 36の証拠が揃った後にdefault-offで開始し、通常Rankingを先に確定した
上位候補へだけ適用する。初期sliceでは説明と確認材料を追加するだけとし、通常score / 順位を変更しない。

### 6.2 Notification N6

- Favorite / news / sector cache adapterはactive `user_id`を必須にし、system userを除外する。
- 最初はmanual / dry-runでevent payload、dedupe key、quiet hours、severity、CTAを確認する。
- scheduler接続は明示opt-inのまま維持し、配送失敗を成功扱いしない。
- Research / Report eventはR3のuse case完了後、その保存成功または完了eventから生成する。
- view、Provider、Research serviceからNotification Gatewayを直接呼ばず、Producer / port境界へ接続する。
- live smokeは通常testと分離し、外部障害でfavorites、archive、cache、session stateを破損させない。

## 7. 各sliceの完了条件と検証

- 振る舞いを変えず、既存API / UI / export contractを維持する。
- 移動した責務に単体testまたはboundary testがある。
- backend-to-UI、domain-to-frameworkなどの逆依存を増やさない。
- Forecast / Ranking / Scoring変更を伴う場合は構造変更とcommitを分離し、時系列回帰を追加する。
- targeted test、Ruff、Blackを通し、適切な間隔で全体testとCIを確認する。
- compatibility façadeには移行先と削除条件をdocstringまたは設計書で示す。
- runtime artifact、cache、secret、偶発差分をcommitしない。

最低限の検証は次のように選ぶ。

| 変更 | 必須確認 |
|---|---|
| contract / policy / service分離 | 対象pytest、boundary test、Ruff、Black |
| import / package変更 | architecture audit、対象pytest、import smoke |
| Streamlit state / UI分離 | state test、対象AppTest、Desktop / iPhone / iPad smoke |
| Research / external adapter | fixture test、timeout / schema / fallback test、network-free通常test |
| 金融数値変更 | 構造変更と別commit、temporal regression、subgroup / audit gate |
| live Provider / Gateway / 通知 | 明示opt-in live smoke。通常testの成功とは別に報告 |

一つのsliceは、原則として「一つの責務移動」「互換層」「証明test」で閉じる。全体testが長時間化する場合も、
targeted testを省略せず、project checkとCIの最後の確認commitを記録する。

## 8. リスクと停止条件

- import移動でStreamlit起動時だけ発生する循環や重い初期化を作らない。
- pickle、JSON、CSV、SQLite、Pydantic contractのmodule pathやfieldを暗黙に変更しない。
- 巨大moduleの分割と数値改善、UI redesign、Provider変更を同時に行わない。
- 同一sliceで広範な回帰失敗が発生した場合は、互換層を残して分割単位を小さくする。
- 全体テスト成功だけで視覚・live-provider・長時間jobの未確認を成功扱いしない。
- 評価用LLM / Forecast結果を、採用gateの記録なしに通常runtimeへ接続しない。
- R2〜R4の分割中moduleへN6や新Providerの恒久実装を足し、分割対象をさらに肥大化させない。

この計画はfolderを最終目的とせず、変更理由が一つの場所に集まり、依存方向と失敗境界が説明可能になることを
最終目的とする。
