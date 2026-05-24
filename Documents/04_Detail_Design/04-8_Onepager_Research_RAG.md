# 04-8_Onepager_Research_RAG

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

## Phase 20 Implementation Baseline / 実装ベースライン

Phase 20 では、Research RAG を「銘柄を推奨するAI」ではなく、既存の `銘柄コックピット` / `銘柄ランキング` / `Decision Report` に資料根拠を添える local-first evidence layer として実装する。

### Goals

- ローカル資料から、長期企業分析の確認材料を検索できるようにする。
- 価格、Forecast、Investment Score、銘柄DB metadata だけでは説明しにくい、成長材料、株主還元、財務安全性、事業リスク、確認不足を根拠付きで整理する。
- 初期段階ではランキング順位や Investment Score を直接変えない。Research Score / score integration は Phase 21 に回す。
- 通常 checks は network、外部 scraping、外部 LLM、外部 vector DB に依存しない。

### Initial Library Policy

- Runtime dependency は既存の `pydantic` と Python 標準ライブラリを優先する。
- MVP の保存先は in-memory service / local file manifest から始め、必要になった段階で `sqlite3` などの local store に広げる。
- MVP 検索は deterministic keyword search とする。日本語形態素解析、embedding、vector DB、LLM は optional future adapter として扱う。
- PDF 対応が必要になった段階で `pypdf` などを追加検討する。Phase 20 MVP は UTF-8 Markdown / Text / CSV fixture を優先する。

### Implemented Phase 20 Backend Slice

`backend/research` に以下の contract / service を追加する。

- `ResearchDocumentRegisterRequest`: local document 登録 request。
- `ResearchDocument`: symbol、title、source_type、published_at、local_path、reliability、document_hash を持つ登録済み資料。
- `ResearchChunk`: document から切り出した検索対象 chunk。source、section、published_at、metadata と紐づく。
- `ResearchSearchRequest`: symbol / query / top_k / source_type filter を持つ検索 request。
- `ResearchEvidence`: 検索結果。source_type、title、published_at、section、excerpt、relevance_score、reliability を含む。
- `ResearchDataQuality`: document_count、latest_document_date、evidence_count、warnings を持つ資料品質。
- `CompanyResearchReport`: deterministic Research Summary。summary、topic別 points、evidence、data_quality を含む。
- `ResearchIngestionService`: local UTF-8 document を登録し、hash による重複登録を避ける。
- `ResearchIndexService`: registered document を Markdown section / paragraph based chunk に分割する。
- `ResearchRetrievalService`: symbol と query から deterministic keyword scoring で evidence を返す。
- `ResearchAnalysisService`: growth、shareholder_return、financial_safety、business_risk、confirmation_gap を template summary として返す。
- `build_research_evidence_section`: Decision Report に Research Summary / Evidence / Data Quality を追加する標準 section builder。
- `ui.research_state`: Streamlit session-local research store、upload registration、cockpit analysis helper。
- `tools/fetch_research_yfinance_profile.py`: 明示実行で Yahoo Finance profile を取得し、確認用の実データResearch Markdownを `data/research_docs/` に保存する運用補助 tool。

### User Flow Target

1. `設定 / データ情報` または運用 tool で、銘柄に紐づくローカル資料を登録する。
2. index rebuild で資料を chunk 化する。
3. `銘柄ランキング` では、候補銘柄に `根拠あり` / `資料が古い` / `根拠不足` のような軽い状態を表示する。Phase 20 では順位を直接変えない。
4. `銘柄コックピット` で選択銘柄の `Research Summary` を表示する。
5. `Decision Report` に `Research Evidence` section と根拠不足 warning を含める。

Current UI status:

- `設定 / データ情報` で Markdown / Text / CSV を session-local に登録できる。
- `銘柄コックピット` では価格データ取得時にResearch RAGを自動実行しない。`AIデータ取得` ボタンはResearchセクションの見出し横に置き、押した場合だけ選択銘柄の Research Summary を表示する。資料名 / 資料日 / 根拠数を表示し、観点別サマリ / evidence table は `Research RAG 詳細` に折りたたむ。
- `銘柄ランキング` では、ランキング行クリックで開く `銘柄データ` モーダルに `AI Research` タブを追加する。タブ内の `AIで資料を確認` ボタンを押した場合だけ、選択銘柄の Research Summary、資料名、資料日、根拠数、詳細 evidence を表示する。
- Cockpit Decision Report は、`AIデータ取得` により取得済みで、登録資料または evidence がある場合だけ `Research Evidence` section を含める。
- Ranking evidence-status display は follow-up work。

Current seed data:

- `data/research_docs/7203_T_yfinance_profile_20260523.md` は、`7203.T` の Yahoo Finance / yfinance profile から取得した確認用の実データResearch資料。
- この資料は market-data provider snapshot であり、監査済み開示資料ではない。重要事項は公式IR / 有価証券報告書 / 適時開示で確認する。

### Storage Migration / `data/research_docs` の将来扱い

- 外部 source adapter が安定し、EDINET / TDnet / IR site / provider profile から明示操作で最新資料を取得できるようになったら、`data/research_docs/` は手動登録の主経路ではなくす。
- ただし完全削除はしない。取得済み資料の cache、監査用 archive、オフライン fixture、private note fallback として残す。
- 廃止対象は「通常ユーザーが手で資料を置く運用」。長期的には `外部資料を取得` / `資料キャッシュを更新` が主導線になり、`data/research_docs/` は生成物・cacheとして扱う。
- 削除や格下げの前提は、source URL、provider、fetched_at、document_hash、manifest、再取得/再現手順が揃っていること。

### Guardrails

- RAG output は売買推奨ではなく、判断材料、根拠、注意点の整理に限定する。
- 資料がない銘柄を不利な投資判断として扱わない。`根拠不足` / `低信頼` として表示する。
- 外部 source adapter、LLM、embedding、hybrid search は explicit opt-in とし、通常 local checks には入れない。

## 1) Purpose & Scope

* **Purpose**: IR資料・有価証券報告書・決算資料・中期経営計画・統合報告書・ニュース等の非構造データを検索し、長期企業分析、根拠提示、Research Score 化を行う。
* **Scope**: ローカル資料登録、テキスト抽出、チャンク化、メタデータ管理、キーワード検索、将来のベクトル/ハイブリッド検索、企業分析サマリ、Research Score、Decision Report / Assistant / Investment Score への接続。
* **Out of Scope**: RAG単体での売買推奨、自動売買判断、証券口座ログイン情報の取得、規約違反リスクのある無制限スクレイピング、外部LLM/APIを必須にする実装。

### 1.1 前提

* 既定経路は **local-first / deterministic-first** とする。
* 初期MVPは、ローカルPDF/Markdown/Text/CSVなどの手動登録資料を対象にする。
* 外部取得（EDINET / TDnet / IR RSS / News API 等）は明示 opt-in の adapter として後続フェーズで扱う。
* RAGの出力は、投資助言ではなく「判断材料・根拠・注意点」の整理に限定する。
* Research Score は、初期段階では Investment Score への optional input とし、既存スコアを壊さない。

## 2) Public Interfaces (Python想定)

```python
class ResearchIngestionService:
    def register_document(self, request: ResearchDocumentRegisterRequest) -> ResearchDocument:
        """ローカル資料または許可済み外部ソースの資料を登録する"""

    def list_documents(self, symbol: str | None = None) -> list[ResearchDocument]:
        """登録済み資料を銘柄・資料種別で一覧する"""

class ResearchIndexService:
    def build_chunks(self, document_id: str) -> list[ResearchChunk]:
        """資料本文を検索可能な chunk に分割する"""

    def rebuild_index(self, symbol: str | None = None) -> ResearchIndexSummary:
        """検索 index を再構築する"""

class ResearchRetrievalService:
    def search(self, request: ResearchSearchRequest) -> list[ResearchEvidence]:
        """銘柄と自然文 query に対して根拠 chunk を返す"""

class ResearchAnalysisService:
    def analyze_company(self, request: CompanyResearchRequest) -> CompanyResearchReport:
        """検索結果を使い、企業の長期評価サマリと Research Score を返す"""
```

* 例外: `ResearchDocumentError`, `ResearchParseError`, `ResearchIndexError`, `ResearchSearchError`, `DataUnavailableError`, `ConfigError`
* 非機能I/F: `healthcheck()`, `metrics()`, `reload_config()`

## 3) Data Contracts (Pydantic)

```python
class ResearchDocument(BaseModel):
    document_id: str
    symbol: str
    company_name: str | None = None
    source_type: Literal[
        "annual_report",
        "earnings_report",
        "earnings_presentation",
        "medium_term_plan",
        "integrated_report",
        "tdnet",
        "news",
        "user_note",
    ]
    title: str
    published_at: date | None = None
    collected_at: datetime
    source_url: str | None = None
    local_path: str | None = None
    language: Literal["ja", "en", "unknown"] = "unknown"
    provider: str = "local"
    reliability: Decimal

class ResearchChunk(BaseModel):
    chunk_id: str
    document_id: str
    symbol: str
    section_title: str | None = None
    text: str
    page: int | None = None
    chunk_index: int
    token_count: int
    embedding_model: str | None = None
    metadata: dict[str, str] = {}

class ResearchEvidence(BaseModel):
    symbol: str
    document_id: str
    title: str
    source_type: str
    published_at: date | None = None
    page: int | None = None
    excerpt: str
    relevance_score: Decimal
    reliability: Decimal

class ResearchScore(BaseModel):
    symbol: str
    total_score: Decimal
    growth_score: Decimal
    profitability_score: Decimal
    shareholder_return_score: Decimal
    financial_safety_score: Decimal
    business_risk_score: Decimal
    disclosure_quality_score: Decimal
    freshness_score: Decimal
    evidence_count: int
    summary: str

class ResearchDataQuality(BaseModel):
    status: Literal["OK", "WARN", "BLOCK"]
    latest_document_date: date | None
    document_count: int
    evidence_count: int
    warnings: list[str]

class CompanyResearchReport(BaseModel):
    symbol: str
    as_of: date
    summary: str
    growth_points: list[str]
    shareholder_return_points: list[str]
    risk_points: list[str]
    evidence: list[ResearchEvidence]
    research_score: ResearchScore
    data_quality: ResearchDataQuality
```

## 4) Algorithms & Rules

### 4.1 Document Ingestion

* MVPはローカルファイル登録を優先する。
* 登録時に `symbol`, `source_type`, `title`, `published_at`, `provider`, `reliability` を必須または推奨メタデータとして扱う。
* 外部URL取得は `research.allow_external_sources: true` の明示設定がある場合だけ許可する。
* 同一資料の重複は `document_hash` または `source_url + published_at + title` で検知する。

### 4.2 Text Extraction / Chunking

* PDF / Markdown / Text を対象に開始する。
* 画像OCR、図表構造化、表の厳密抽出は後続フェーズに回す。
* chunk は 500〜1000 tokens 程度を目安にする。
* page、section title、source_type、published_at を必ず保持する。
* 本文抽出できない資料は `ResearchParseError` とし、空文字の chunk を作らない。

### 4.3 Retrieval

* Phase R3 は keyword search をMVPとする。
* Phase R5 で embedding + vector store を追加し、keyword + vector の hybrid search に拡張する。
* 検索結果は `relevance_score`, `reliability`, `published_at`, `source_type` を持つ。
* 古い資料は freshness penalty を与え、最新資料と過去資料の混在をUIで見えるようにする。

### 4.4 Research Analysis / Score

* Research Score は以下の観点で構成する。
  * `growth_score`: 成長戦略、海外展開、新規事業、中期目標
  * `profitability_score`: 利益率、ROE、価格転嫁、改善施策
  * `shareholder_return_score`: 配当方針、増配、自社株買い、DOE/配当性向
  * `financial_safety_score`: 自己資本、キャッシュ、負債、財務余力
  * `business_risk_score`: 事業依存、為替、原材料、規制、訴訟、地政学
  * `disclosure_quality_score`: 定量目標、資料の明確さ、継続開示
  * `freshness_score`: 直近資料の鮮度、更新頻度
* MVPではLLM採点を必須にせず、ルール/キーワード/テンプレートから deterministic に始める。
* optional LLM adapter を使う場合も、根拠 chunk と score breakdown を保持する。

### 4.5 Scoring Integration

* `research_score` は Investment Score に optional input として渡す。
* Research Score が無い銘柄でも既存の Screening / Forecast / Risk / Data Quality score は動作する。
* 初期重みは `research: 0.0` または低めにし、UI上で「研究情報を参考表示」として扱う。

## 5) Error Handling & Retries

* ローカルファイルが無い/読めない: `ResearchDocumentError`
* PDF本文抽出不可: `ResearchParseError`
* chunk生成不可: `ResearchIndexError`
* index未構築: `ResearchSearchError` または空結果 + warning
* 外部ソース取得失敗: provider error を `details` に保持し、通常CIでは実行しない
* LLM/embedding adapter失敗: fallbackとして keyword search / template summary に戻す

## 6) Idempotency & Security

* 登録資料は `document_hash` で重複検知する。
* ローカルファイルパスは設定済み `research.document_dirs` 配下に限定する。
* 外部取得は opt-in とし、robots / 利用規約 / rate limit を尊重する。
* APIキーや外部LLMのcredentialはSecret管理し、ログに出さない。
* RAG回答には、資料タイトル、公開日、ページ番号などの根拠を付ける。
* 著作権保護の観点から、長い本文の丸写しを避け、短い引用または要約に留める。

## 7) Performance Budget

* `register_document`: 1資料 P95 < 2s（PDF本文抽出を除く）
* `build_chunks`: 50ページPDF P95 < 10s（OCRなし）
* `search`: keyword search P95 < 500ms、vector search P95 < 1s
* `analyze_company`: cached evidence 利用時 P95 < 3s
* 通常UI操作は外部API/LLMに依存しない。

## 8) Observability

* ログ: `corr_id, symbol, document_id, source_type, provider, chunk_count, latency_ms, status`
* メトリクス: `research_documents_total`, `research_chunks_total`, `research_search_latency_ms`, `research_empty_result_total`, `research_parse_error_total`
* トレース: ingestion -> extraction -> chunking -> index -> retrieval -> analysis のspan化
* UI/Reportでは `latest_document_date`, `document_count`, `evidence_count`, `data_quality.status` を表示する。

## 9) Config Knobs（config.yml）

```yaml
research:
  enabled: true
  provider: local
  document_dirs:
    - data/research_docs
  allow_external_sources: false
  chunking:
    max_tokens: 800
    overlap_tokens: 120
  retrieval:
    backend: keyword # keyword|vector|hybrid
    top_k: 8
    freshness_half_life_days: 365
  embeddings:
    enabled: false
    provider: local
    model: null
  scoring:
    enabled: true
    default_weight_in_investment_score: 0.0
  external_sources:
    edinet: false
    tdnet: false
    news: false
```

## 10) Test Plan

* **Unit**: document metadata validation、chunking、重複検知、freshness score、Research Scoreのルール計算
* **Integration**: sample Markdown/PDF -> chunk -> search -> report の一連フロー
* **Golden Test**: 既知のIRサンプルから期待する evidence / summary / warning を返す
* **Property-based**: chunk token数、chunk順序、空本文の扱い、不変条件検証
* **E2E**: Streamlit Research view で銘柄検索 -> Research Summary -> Decision Report export
* **CI方針**: 外部API、外部LLM、live scrapingに依存しない。外部接続は手動 smoke または opt-in test に分離する。

## 11) Migration/Compatibility

* `research` module は既存 `marketdata`, `forecast`, `scoring` を壊さない独立コンポーネントとして追加する。
* `InvestmentScore` への接続は optional field から始める。
* `DecisionReport` は既存 forecast / scoring report context を拡張し、Research evidence を追加する。
* embedding model や chunking rule は version を持ち、再index時に差分を追跡する。

## 12) Open Questions（TBD）

* 初期資料形式を PDF / Markdown / Text のどこまでにするか。
* EDINET / TDnet / IRサイト / News API の優先順位。
* embedding backend を local にするか cloud optional にするか。
* Research Score の初期重みと、Investment Score への統合タイミング。
* 日本語/英語資料の同時検索における翻訳・正規化方針。
* 図表・表・画像PDFの扱い。
* 著作権・引用量・保存期間の運用ルール。
