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

### R0: 境界を機械的に固定

- backend-to-UI逆依存をport / adapterへ反転する。
- `backend`から`ui`へのimport禁止testを追加する。
- Assistant / News間のpackage façade相互参照を直接contract importへ置き換える。
- module数、内部edge、eager cycle、巨大module / function、fan-outを再実行可能なCLIで監査する。
- 構造変更で予測値、ranking順、scoreが変わらないことを明示する。

### R1: Ranking application flowを`ui.app`から分離

- 入力条件、job request、進捗、結果、sanitized errorをtyped contract化する。
- MarketData取得とranking orchestrationをUI非依存use caseへ移す。
- Streamlit session / job registryはcontroller adapterに限定する。
- 既存function名はcompatibility façadeとして残し、CLIとテストを新use caseへ移行する。

### R2: Cockpit application flowを分離

- symbol/date/provider選択、取得、Forecast実行、表示model生成を分ける。
- `page`、`controller`、`presenter`を分離し、rerun時state contractを固定する。

### R3: Research serviceをuse case別に分割

- company profile、product/service、financial summary、evidence、external fetchを分ける。
- 正規化、要約、永続化、外部取得の境界を明示する。
- 現在の`backend.research`公開contractは互換testを維持する。

### R4: UI viewとstyleを分割

- Copilot / Newsをpage-controller-presenterへ分ける。
- `ui/styles.py`のCSSをbase、component、page assetへ分け、loaderだけをPythonへ残す。
- PC、iPhone、iPadのviewport回帰を各画面sliceで実行する。

### R5: package cycleと公開APIを整理

- `__init__.py`を薄くし、型だけのimportは`TYPE_CHECKING`へ寄せる。
- Assistant / News / Researchの循環を実依存と再export由来に分類して解消する。
- 公開API一覧とdeprecation期間を記録する。

### R6: 継続的な保守gate

- 新規moduleは原則600行以下、新規functionは原則80行以下を目安とする。
- 超過が適切な生成物、宣言表、CSS、schemaの場合は理由を文書化する。
- module dependency、巨大function、境界違反を定期監査し、単純な行数だけでCIを失敗させない。

## 6. 各sliceの完了条件

- 振る舞いを変えず、既存API / UI / export contractを維持する。
- 移動した責務に単体testまたはboundary testがある。
- backend-to-UI、domain-to-frameworkなどの逆依存を増やさない。
- Forecast / Ranking / Scoring変更を伴う場合は構造変更とcommitを分離し、時系列回帰を追加する。
- targeted test、Ruff、Blackを通し、適切な間隔で全体testとCIを確認する。
- compatibility façadeには移行先と削除条件をdocstringまたは設計書で示す。
- runtime artifact、cache、secret、偶発差分をcommitしない。

## 7. リスクと停止条件

- import移動でStreamlit起動時だけ発生する循環や重い初期化を作らない。
- pickle、JSON、CSV、SQLite、Pydantic contractのmodule pathやfieldを暗黙に変更しない。
- 巨大moduleの分割と数値改善、UI redesign、Provider変更を同時に行わない。
- 同一sliceで広範な回帰失敗が発生した場合は、互換層を残して分割単位を小さくする。
- 全体テスト成功だけで視覚・live-provider・長時間jobの未確認を成功扱いしない。

この計画はfolderを最終目的とせず、変更理由が一つの場所に集まり、依存方向と失敗境界が説明可能になることを
最終目的とする。
