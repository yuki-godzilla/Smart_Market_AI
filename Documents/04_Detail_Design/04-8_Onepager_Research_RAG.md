# 04-8_Onepager_Research_RAG

#### [BACK TO DETAIL DESIGN README](./04_Detail_Design_README.md)

Status: Phase 20 local evidence slice is implementation complete as the deterministic foundation. Product direction now prioritizes external fresh evidence for Research RAG / News RAG: `AI調査を更新` should become the standard action that fetches or references current IR, disclosure, company-site, provider-profile, and news sources for the selected symbol. Local registered documents remain for tests, demo seeds, user-saved archives, private notes, and fallback. Phase 21 covers advanced Research RAG extraction, query expansion, optional vector / hybrid search, grounded answer generation, Stock News RAG, external fetch integration, and local ResearchBrief readability; deterministic query expansion, structured extraction, template grounded answer, retrieval quality, evidence reranker, first UI / Decision Report display, optional vector / hybrid contract/scoring, keyword-fallback hybrid retrieval wrapper, local embedding generation, optional vector-index build workflow, in-memory local vector store, file-backed vector cache, first Cockpit external fetch UI slice, and first local `ResearchBriefBuilder` slice have started. TDnet timely disclosure + Yahoo Finance profile/news are wired as the default first live source set. Phase 22 Research Score has a deterministic service slice, disabled-by-default Investment Score input slice, Cockpit / Ranking Research Summary display slice, selected-candidate breakdown context, and Cockpit Decision Report section slice. Ranking order integration, EDINET / company IR site adapters, and Assistant integration remain later phases unless explicitly assigned.

## Phase 20 Implementation Baseline / 実装ベースライン

Phase 20 では、Research RAG を「銘柄を推奨するAI」ではなく、既存の `銘柄コックピット` / `銘柄ランキング` / `Decision Report` に資料根拠を添える evidence layer として実装する。

Research RAG は通常検証を deterministic-first に保つが、実運用の価値は資料・ニュースの鮮度に大きく依存する。通常ユーザー導線では外部 source adapter による current evidence を優先し、source URL、published_at、fetched_at、freshness warning を備えて表示する。取得本文は既定では保存せず、その回の RAG summary / score / 表示で一時参照する。local 登録資料は fixture / archive / fallback の位置づけに下げる。

### Goals

- 外部の最新IR・開示・ニュース・provider evidence から、長期企業分析の確認材料を検索できるようにする。
- 価格、Forecast、Investment Score、銘柄DB metadata だけでは説明しにくい、成長材料、株主還元、財務安全性、事業リスク、確認不足を根拠付きで整理する。
- 初期段階ではランキング順位や Investment Score を直接変えない。Research Score 初期 slice は実装済みだが、既定 weight は 0.0 で ranking order integration は後続 opt-in とする。
- 通常 checks は network、外部 scraping、外部 LLM、外部 vector DB に依存しない。

### Initial Library Policy

- Runtime dependency は既存の `pydantic` と Python 標準ライブラリを優先する。
- MVP の既定保存先は in-memory service とする。local file manifest や `sqlite3` などの永続 store は、ユーザーが明示保存を選ぶ archive / export 機能として必要になった段階で検討する。
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
- `tools/fetch_research_yfinance_profile.py`: 明示実行で Yahoo Finance profile を取得し、確認用の実データResearch Markdownを `data/research_docs/` に保存する開発・検証用補助 tool。通常UIの外部取得方針とは別で、ユーザー向け既定動作ではない。

### User Flow Target

1. `銘柄コックピット` で `AI調査を更新` を押す。
2. source adapter が選択銘柄の外部最新資料・ニュース・provider evidence を取得/参照し、session-local RAG store に一時登録する。
3. local 登録資料、demo seed、user-saved archive がある場合は補助 evidence / fallback として合わせて検索する。
4. `Research Summary`、Research Score、根拠カード、外部参照ソース trace を表示する。
5. `Decision Report` に `Research Evidence` / `Research Score` / `外部参照ソース` section と根拠不足 warning を含める。

Current UI status:

- `設定 / データ情報` で Markdown / Text / CSV を session-local に登録できる。
- `銘柄コックピット` では価格データ取得時にResearch RAGを自動実行しない。`AI調査を更新` はResearch Evidence冒頭の操作カードに置き、押した場合だけ選択銘柄の Research Evidence を表示する。今後はこの action が外部 source search を含む標準動作になる。初期表示は判断向け summary metrics、観点別要点、根拠カードに絞り、source / retrieval quality / evidence table は `詳細データを表示` に折りたたむ。
- `銘柄コックピット` では独立した `外部資料取得（明示許可）` panel / checkbox を廃止し、TDnet timely disclosure と Yahoo Finance provider profile / news 取得を `AI調査を更新` に統合済み。取得本文は session-local RAG store に一時登録してその場の summary / score / news 表示に使い、画面には provider、fetched_at、published_at、source URL、freshness_status、warnings、短い要約を表示する。既定では Markdown / manifest JSON を保存しない。
- `銘柄ランキング` では、ランキング行クリックで開く `銘柄データ` モーダルに `AI Research` タブを追加する。タブ内の `AIで資料を確認` ボタンを押した場合だけ、選択銘柄の Research Summary、資料名、資料日、根拠数、詳細 evidence を表示する。
- Cockpit Decision Report は、`AI調査を更新` により取得済みで、登録資料または evidence がある場合だけ `Research Evidence` section を含める。外部資料取得を実行済みの場合は、取得本文ではなく source URL / provider / fetched_at / published_at / freshness_status / 短い要約 / warnings を `外部参照ソース` section として残す。
- Ranking evidence-status display は follow-up work。

Current seed data:

- `data/research_docs/7203_T_yfinance_profile_20260523.md` は、`7203.T` の Yahoo Finance / yfinance profile から取得した確認用の実データResearch資料。
- この資料は market-data provider snapshot であり、監査済み開示資料ではない。重要事項は公式IR / 有価証券報告書 / 適時開示で確認する。

### External Fetch Storage Policy / 外部取得の保持方針

- 外部 source adapter からの Live 取得は、既定では session-local / transient とする。
- 取得本文、変換 Markdown、manifest JSON、document_hash、local_path は自動保存しない。
- UI / Decision Report に残すのは、source URL、provider、published_at、fetched_at、freshness warning、短い要約/引用範囲、スコア参照の根拠説明に限定する。
- `data/research_docs/` は、手動アップロード、private note、開発 fixture、ユーザーが明示保存した資料の fallback として残す。
- 永続化が必要な場合は、既定取得とは別の `資料を保存する` / archive action として実装し、保存範囲・保持期間・削除導線を明示する。

### Guardrails

- RAG output は売買推奨ではなく、判断材料、根拠、注意点の整理に限定する。
- 資料がない銘柄を不利な投資判断として扱わない。`根拠不足` / `低信頼` として表示する。
- 外部 source adapter は `AI調査を更新` の標準ユーザー導線として扱うが、backend safety gate と fake adapter tests を維持する。LLM、外部 embedding、hybrid search は explicit opt-in とし、通常 local checks には入れない。

## Phase 21 Plan: Advanced Research RAG - Evidence Extraction And Grounded Answers

Phase 21 は、Phase 20 の deterministic evidence foundation を壊さず、根拠検索を「外部最新情報から欲しい情報を抽出すること」と「根拠付き説明文」へ拡張する planned phase です。RAG 単体で売買推奨、buy / sell / hold 判断、ランキング順位や Investment Score の直接変更は行いません。

### Phase 21 Goals

- 登録済み Research 資料から、企業理解と判断補助に関係する情報を抽出する。
- 抽出した主張、要点、不足情報を必ず `ResearchEvidence` と紐づける。
- 銘柄コックピット、ランキングモーダル、Decision Report で自然な説明文を表示できるようにする。
- keyword search baseline を維持しながら、query expansion、optional embedding / vector store / hybrid search、evidence reranking を追加できる設計にする。
- Research Score 連携に向けて、根拠数、鮮度、信頼度、source type、根拠多様性を扱える中間 contract を整える。

### Phase 20 / Phase 21 Boundary

- Phase 20: local document registration, chunking, deterministic keyword search, Research Evidence, Research Summary, Decision Report connection.
- Phase 21: query expansion, structured evidence extraction, grounded answer generation, optional embedding retrieval, local vector store abstraction, hybrid search, evidence reranking, Research Score integration preparation.
- Phase 21.5: Stock News RAG MVP. `銘柄コックピット` の選択銘柄だけを対象に、URL 根拠付き recent news summary、investment_viewpoint、sentiment_for_investment、freshness_status を表示する。Investment Score / ranking order は変更しない。
- Phase 22+: Research Score の ranking integration、ResearchBrief 表示 polish、外部 source adapter 追加、Assistant。

### Phase 21.5 News RAG Boundary

- 初期対象は個別銘柄ニュース深掘りだけ。市場全体の `投資ニュース` 画面、関連銘柄自動抽出、Watchlist / portfolio 連動、Decision Report 自動反映、Research Score / News Score 化は後続候補。
- `StockNewsEvidence` は `symbol`, `company_name`, `title`, `url`, `source`, `published_at`, `summary`, `investment_viewpoint`, `sentiment_for_investment`, `freshness_status` を持つ方向で検討する。
- `investment_viewpoint` は `earnings`, `growth`, `shareholder_return`, `risk`, `macro`, `other` から開始する。
- `sentiment_for_investment` は `positive`, `negative`, `neutral`, `mixed`, `unknown` とし、buy / sell / hold ではなくニュース材料の方向感として扱う。
- `freshness_status` は `latest`, `recent`, `stale`, `unknown` とし、古いニュースを最新材料のように扱わない。
- 外部ニュース取得は backend の network gate を通す adapter とし、通常ユーザー導線では `AI調査を更新` に統合する。通常 checks / CI は fake adapter / fixture を使い、network、live scraping、外部LLMに依存させない。

### Phase 21.6 / 21.7 External Fetch Boundary

- Phase 21.6 は `AI調査を更新` の標準処理として、TDnet + Yahoo Finance 初期 slice 実装済み。次は EDINET / 企業IR site / provider profile 拡張などの外部資料取得 adapter を追加する候補とする。
- Phase 21.7 は `AI調査を更新` から選択銘柄に限定した外部ニュース取得 adapter を使う候補とする。
- 外部取得結果は既定では source URL、provider、fetched_at、published_at、freshness_status、短い要約/引用範囲だけを表示・Report context に渡す。取得本文・document_hash・manifest は自動保持しない。通常 tests / CI では fake adapter / fixture を使う。
- 外部資料取得・外部ニュース取得は通常ユーザー導線の primary source とし、local deterministic slice は tests / fixture / archive / fallback として残す。失敗時はローカル資料・ローカル news evidence 表示に戻る。
- これらの child phases でも Investment Score / ranking order を変更せず、buy / sell / hold を出さない。

Current implementation note: `ExternalResearchFetchService`, `TDnetResearchAdapter`, `YahooFinanceResearchAdapter`, and `DefaultExternalResearchAdapter` are wired to the Cockpit Research Evidence panel as a first UI slice. The UI runs external source search from `AI調査を更新` and no longer exposes a separate explicit-permission panel. The flow registers external payload text in the session-local RAG store, rebuilds chunks for the current session, records source trace rows with freshness_status, and does not write fetched payload Markdown or manifest files. Cockpit Decision Report includes an `外部参照ソース` trace section for those rows without retaining fetched source text. A future explicit archive action may opt into persistence separately.

### CompanyResearchSummary / ResearchBrief ローカル企業リサーチレポート化方針

Research Summary 改善では、`CompanyResearchReport` / evidence と Streamlit UI の間に、表示専用の `CompanyResearchSummary` と `ResearchBrief` 層を置く。provider dump や raw evidence を主表示に出すのではなく、deterministic なローカルルールで、企業概要、事業内容、規模感、定量情報、IR情報、最新ニュースを読める企業リサーチレポートへ変換する。投資判断メモは主役ではなく、企業理解のための AI読み取りメモ / 確認ポイントとして後段に置く。外部LLM / OpenAI API 連携は後続に回し、通常 checks は network / LLM 非依存を維持する。

現行の読みやすさ改善 slice では、`ResearchBrief` の前段に `ResearchFactSummary` を置き、さらに UI の主表示として `CompanyResearchSummary` を作る。これは取得件数や出典カード数ではなく、ユーザーが最初に知りたい「この会社は何をしているか」「どの事業で稼いでいるか」「規模感はどれくらいか」「主要指標やIR資料は確認できたか」「直近ニュースは何か」を source-backed fact として整理する層である。
銘柄タイプ別の表示切替もこの読みやすさ改善 slice に含める。`SecurityResearchTypeDetector` は provider metadata / quoteType / exchange / symbol suffix から domestic stock、foreign stock、ETF / fund、unknown を判定し、`ResearchPageViewModelBuilder` は個別株を `CompanyResearchSummary`、ETF / fund を `ETFResearchSummary` に振り分ける。ETF / fund では企業概要・売上・営業利益・決算短信・有価証券報告書ではなく、ファンド概要、投資対象、対象地域、ベンチマーク、純資産総額、NAV、経費率、分配金利回り、上位保有銘柄、運用会社資料の確認ポイントを主表示にする。foreign stock は企業リサーチ構成を維持しつつ、TDnet / EDINET / 決算短信ではなく Annual Report、10-K / 10-Q、Earnings Release、Investor Presentation、SEC Filing の確認文言を使う。

推奨 pipeline:

1. `CompanyResearchReport` / `StockNewsReport` / `ExternalResearchFetchResult` / provider profile から候補事実を集める。
2. local rule-based extractor で `ResearchFactSummary` を作る。
3. `CompanyResearchSummaryBuilder` は `CompanyResearchEvidence` の正規化層を通して、source type ごとにプロフィール、IR、TDnet、ニュース、定量情報の役割を分ける。
4. `CompanyResearchSummaryBuilder` は正規化済み evidence と `ResearchBrief` / `ResearchFactSummary` / external trace を使い、企業概要、主な事業、製品・サービス、地域、規模感、定量情報、IR資料、最新ニュースを組み立てる。
5. `ResearchBriefBuilder` / `InvestmentInsightBuilder` / `InvestmentQuestionSummaryBuilder` は、後段の確認メモ、読み方サマリー、企業理解の確認ポイント、UI card を組み立てる。
6. AI読み取りメモ、source card、Research Score、raw evidence は確認用 detail に下げる。

`ResearchFactSummary` の候補 contract:

```python
class ResearchFactSummary(BaseModel):
    business_overview: list[ResearchFactItem]
    business_segments: list[ResearchFactItem]
    financial_snapshot: list[ResearchFactItem]
    recent_events: list[ResearchFactItem]
    positive_materials: list[ResearchFactItem]
    caution_materials: list[ResearchFactItem]
    missing_items: list[ResearchMissingItem]


class ResearchFactItem(BaseModel):
    label: str
    value: str
    source_title: str
    source_type: Literal["official", "tdnet", "edinet", "company_ir", "provider", "news", "user_note"]
    published_at: date | None
    confidence: Literal["high", "medium", "low", "unknown"]


class ResearchMissingItem(BaseModel):
    label: str
    reason: str
    next_source_hint: str
```

初期抽出対象:

- 事業概要: 何をしている会社か、主要事業、収益源、地域、セグメント。
- IR / 公式確認: 決算短信、有価証券報告書、適時開示、会社IR、EDINET、公式ニュース。
- 定量情報: 売上高、営業利益、純利益、EPS、配当、PER、PBR、ROE、時価総額。
- 業績見通し: 通期予想、業績予想、業績修正、上方修正、下方修正。
- 株主還元方針: 配当方針、増配、減配、自社株買い、配当性向、株主還元方針。
- 直近イベント: 決算発表、業績修正、配当変更、自社株買い、重要ニュース。
- 良材料候補: 成長、収益性、株主還元、財務安全性など、根拠付きで確認できたもの。
- 注意材料候補: 事業リスク、業績悪化、財務負担、鮮度不足、ニュース由来の確認事項。
- 未確認項目: 公式資料でまだ裏取りできていない主要指標や一次情報。

表示ルール:

- 主表示では企業リサーチサマリーを先頭に置き、source-backed fact だけを断定的に扱う。provider-only の場合は `外部プロバイダー情報では` と書き、公式IRと同じ重みで見せない。
- `資料n件`、`出典カードn件`、`Research Score` は補助情報であり、主表示の結論にしない。
- 未確認項目は悪材料ではなく、追加で確認する項目として扱う。
- 外部LLM / local lightweight LLM を使う場合も、入力は抽出済み fact に限定し、出力は validated JSON として `ResearchFactSummary` に戻す。失敗時は deterministic rule-based summary に戻る。

実装 contract の要点:

```python
class CompanyResearchSummary(BaseModel):
    symbol: str
    overview: CompanyOverviewSummary
    quantitative: QuantitativeSummary
    ir_items: list[IRSummaryItem]
    news_items: list[NewsSummaryItem]
    ai_reading_notes: list[str]
    missing_critical_items: list[str]
    normalized_evidence: list[CompanyResearchEvidence]


class CompanyResearchEvidence(BaseModel):
    kind: Literal["company_profile", "business_description", "financial_metric", "ir_document", "tdnet_disclosure", "news", "market_data", "unknown"]
    title: str
    body: str
    source_type: str
    reliability: Literal["official", "semi_official", "market_provider", "news", "unknown"]
    information_status: Literal["found", "missing", "unparsed", "unverified", "not_applicable"]


class ResearchBrief(BaseModel):
    memo: str
    metrics: list[ResearchMetric]
    missing_metrics: list[str]
    business_overview: str
    positive_candidates: list[str]
    caution_candidates: list[str]
    confirmation_gaps: list[str]
    next_actions: list[str]
    source_cards: list[ResearchBriefSourceCard]


class ResearchMetric(BaseModel):
    label: str
    value: str
    source_type: str
    source_title: str
    source_confidence: Literal["high", "medium", "low", "unknown"]
```

`ResearchBriefBuilder` の責務:

- Yahoo Finance / provider profile は企業概要・事業内容に圧縮し、Provider Symbol、Quote Type、Exchange、Currency、Sector、Industry などの raw field は通常表示に出さない。
- 定量指標と定性トピックを分離する。
- 初期対象指標は、売上高、営業利益、純利益、EPS、配当、PER、PBR、ROE、時価総額とし、local regex / keyword rule で抽出する。
- 取得できない重要指標は `missing_metrics` に入れる。
- 定性 evidence は local keyword で成長材料、業績材料、株主還元、リスク、市場テーマ、良材料候補、注意材料候補、不足根拠に分類する。
- source confidence は出典の役割で付与する。公式IR / TDnet / EDINET / 企業IRは `high`、provider profile / news は `medium`、keyword 抽出のみは `low` とする。
- 公式IR不足、最新決算不足、業績見通し不足、配当方針不足、リスク記述不足、ニュース鮮度不足、一次情報不足、主要指標不足は `missing_points` に出す。
- TDnet、企業IR、EDINET、最新決算資料、配当方針、リスク要因などの確認を `next_actions` に出す。
- raw evidence / provider field dump は detail rows のみに残す。

Cockpit Research Summary の推奨表示順:

1. 企業リサーチサマリー
2. 定量情報サマリー
3. IR情報サマリー
4. 最新ニュース・開示サマリー
5. 企業理解の確認ポイント
6. AI読み取りメモ / 確認できた情報 / 注意して読む情報 / 不足している情報は折りたたみ
7. 出典カード
8. Research Score
9. 外部参照ソース / 取得失敗の技術詳細 / 詳細データ

Research Score は先頭ブロックに置かない。local AI整理メモと出典カードの後、または detail / context 内で、根拠の充足度、鮮度、信頼度を確認する参考スコアとして表示する。

ローカルAI整理メモのテンプレート例:

- provider profile のみ: `外部データから企業概要の一部は確認できますが、主力事業、収益構造、主要指標は公式IR・決算資料で追加確認が必要です。`
- 公式開示あり: `公式開示情報が確認できています。決算内容、業績修正、配当方針などの一次情報を優先して企業像を確認してください。`
- 根拠が少ない場合: `現時点では、確認できた企業情報が限られています。最新決算、事業セグメント、配当方針、リスク要因を公式資料で確認してください。`

この slice の追加テストでは、`CompanyResearchSummaryBuilder` が企業概要、定量情報、IR資料、最新ニュースを分けること、`CompanyResearchEvidence` で source type ごとの役割を正規化すること、provider profile から主な事業 / 製品サービス / 地域を分けること、ニュースタイトルを事業内容に混ぜないこと、IR document type と found / missing / unparsed / unverified を区別すること、provider raw field を通常表示で隠すこと、metric extraction / missing metrics、source type 別 evidence label、keyword-based topic classification、source card の確認目的、UI表示順を確認する。

### Structured Evidence Extraction

`ResearchChunk` / `ResearchEvidence` から、以下のカテゴリに沿って構造化された claim を抽出する。

- `growth`: 成長戦略、海外展開、新規事業、中期経営計画、投資計画、収益拡大施策。
- `shareholder_return`: 配当方針、増配、自社株買い、DOE、配当性向、株主還元方針。
- `financial_safety`: 自己資本比率、キャッシュ、現金同等物、有利子負債、財務余力、格付け。
- `business_risk`: 為替リスク、原材料価格、規制、訴訟、地政学リスク、特定事業依存、サプライチェーンリスク。
- `confirmation_gap`: 該当カテゴリの根拠なし、古い資料、provider snapshot のみ、低信頼資料、判断に必要な情報不足。

### Candidate Contracts

```python
class ResearchExtractedClaim(BaseModel):
    schema_version: str = "research-extraction-v1"
    symbol: str
    category: Literal[
        "growth",
        "shareholder_return",
        "financial_safety",
        "business_risk",
        "confirmation_gap",
    ]
    claim: str
    summary: str
    supporting_evidence: list[ResearchEvidence]
    confidence: Decimal
    missing_information: list[str] = []
    caution_note: str | None = None

class ResearchEmbedding(BaseModel):
    schema_version: str = "research-embedding-v1"
    chunk_id: str
    document_id: str
    symbol: str
    embedding_model: str
    vector: list[float]
    created_at: datetime
    text_hash: str

class ResearchRetrievalCandidate(BaseModel):
    symbol: str
    document_id: str
    chunk_id: str
    title: str
    source_type: str
    published_at: date | None = None
    section_title: str | None = None
    excerpt: str
    keyword_score: Decimal | None = None
    vector_score: Decimal | None = None
    freshness_score: Decimal | None = None
    reliability: Decimal
    final_relevance_score: Decimal
    retrieval_backend: Literal["keyword", "vector", "hybrid"]

class ResearchRetrievalQuality(BaseModel):
    backend: Literal["keyword", "vector", "hybrid"]
    query: str
    expanded_terms: list[str]
    candidate_count: int
    evidence_count: int
    warnings: list[str]
```

Current implementation note: `ResearchExtractedClaim` is available as the first structured extraction contract, and `CompanyResearchReport.extracted_claims` carries generated claims. Claims for regular categories are created only when supporting evidence exists; missing topic evidence is represented as `confirmation_gap` so unsupported claims are not mixed into generated summaries.

Current implementation note: `ResearchRetrievalQuality` is available as the first retrieval transparency contract, and `CompanyResearchReport.retrieval_quality` carries the keyword backend, category query set, expanded terms, retrieved candidate count, deduped evidence count, and warnings. Vector / hybrid backend values remain future optional paths.

### Query Expansion

`config/research_query_terms.yml` を候補に、カテゴリごとの検索語を deterministic に管理する。LLM に依存せず、CI で安定して検証できることを前提にする。

- `growth`: 成長戦略、海外展開、新規事業、中期経営計画、投資計画、収益拡大、事業拡大。
- `shareholder_return`: 株主還元、配当、増配、自社株買い、DOE、配当性向、利益還元。
- `financial_safety`: 財務安全性、自己資本比率、キャッシュ、現金同等物、有利子負債、格付け、財務余力。
- `business_risk`: 事業リスク、為替、原材料、規制、訴訟、地政学、サプライチェーン、依存度。
- `confirmation_gap`: 根拠不足、確認不足、資料不足、古い資料、公式IR未確認、追加確認。

Current implementation note: `ResearchQueryExpansionService` and `ResearchQueryExpansionResult` provide the deterministic baseline, and `config/research_query_terms.yml` is the initial editable dictionary. `ResearchSearchRequest` supports `query_category` and `expanded_terms`; category-aware search remains optional so Phase 20 keyword behavior is preserved.

### Optional Embedding / Vector / Hybrid Search

- Default は Phase 20 相当の keyword search とする。
- Embedding は config で明示的に有効化した場合のみ使う。local provider と cache を優先し、外部 embedding API は explicit opt-in にする。
- `ResearchEmbeddingService` は `chunk_id` / `text_hash` / `embedding_model` 単位で cache し、同じ chunk text の再embeddingを避ける。
- `ResearchVectorStore` は file-based cache または sqlite-based store を MVP 候補とする。FAISS / Chroma / sqlite-vss / cloud vector DB は必須にしない。
- `HybridResearchRetrievalService` は keyword_score、vector_score、freshness_score、reliability_score、source_type priority、evidence diversity を使う。
- vector path が使えない場合は keyword fallback + warning とし、通常 CI は network / external API / heavy ML library に依存しない。

Current implementation note: `ResearchEvidenceReranker` is available as the first deterministic evidence reranker. It preserves `ResearchEvidence` output, suppresses duplicate chunks, and orders evidence by relevance, reliability, freshness, and source-type priority. It is wired into keyword retrieval and company-level evidence ordering without changing scoring or ranking behavior.

Current implementation note: `ResearchEmbedding` and `ResearchRetrievalCandidate` are available as optional vector / hybrid intermediate contracts. `ResearchDisabledVectorStore` is the default disabled vector-store fallback and reports a retrieval-quality warning instead of performing vector search. `ResearchHybridScorer` deterministically combines keyword, vector, freshness, reliability, and source-type priority scores, but it is not wired into the default keyword retrieval path yet.

Current implementation note: `ResearchEmbeddingService` is available as the first local embedding generator. It creates deterministic hash-based vectors for chunk text and query text, keeps `chunk_id` / `text_hash` / `embedding_model` cache-key fields, and can explicitly upsert generated embeddings into writable vector stores. It has no external embedding API, LLM, vector DB, or network dependency.

Current implementation note: `ResearchVectorIndexService` and `ResearchVectorIndexSummary` are available as the first optional vector-index build workflow. They rebuild a writable vector store from already chunked local Research documents, report chunk / embedded counts and missing text-index warnings, and keep vector indexing explicit rather than part of the default keyword path.

Current implementation note: `HybridResearchRetrievalService` is available as an optional wrapper. It uses vector candidates when a vector store provides them, converts hybrid-scored candidates back to `ResearchEvidence`, and falls back to the existing keyword retrieval with retrieval-quality warnings when vector search is disabled or empty. The default `ResearchRetrievalService` keyword path remains unchanged.

Current implementation note: `ResearchInMemoryVectorStore` is available as the first local vector store. It stores `ResearchRetrievalCandidate` + `ResearchEmbedding` pairs in memory, uses optional `ResearchSearchRequest.query_vector`, calculates deterministic cosine similarity, filters by symbol and source type, and reports vector retrieval quality. It has no external embedding, vector DB, or network dependency.

Current implementation note: `ResearchFileVectorStore` is available as the first file-backed vector cache. It persists the same candidate / embedding pairs as UTF-8 JSONL, reloads them across service instances, reports empty cache state in retrieval quality, raises `ResearchSearchError` for invalid cache content, and keeps keyword retrieval as the default path.

### Grounded Answer Generation

Default は template-based generation とする。`ResearchGroundedAnswerService` は `ResearchExtractedClaim` と `ResearchEvidence` から自然文回答を作る。

- 根拠がない内容は書かない。
- 根拠不足は `confirmation_gap` として明示する。
- 断定しすぎず、資料名、資料日、根拠数を保持する。
- 売買推奨に見える表現を避ける。
- Optional LLM adapter を使う場合も、明示 opt-in、通常 CI では disabled、入力は ResearchEvidence に限定、Evidence にない内容を生成しない、buy / sell / hold を出さない、生成結果に evidence reference を残す。

Current implementation note: `ResearchGroundedAnswerService` is available as the first template-based grounded answer service. `CompanyResearchReport.grounded_answer` is generated from `ResearchExtractedClaim` and referenced `ResearchEvidence` only, carries warning text for gaps, and includes an explicit non-recommendation note.

### UI / Decision Report Direction

- Cockpit: Research Summary、観点別抽出ポイント、根拠数、最新資料日、Data Quality、Retrieval Quality、検索方式、Research RAG 詳細を表示する。
- Ranking modal: `AIで資料を確認` button、根拠付き Research Summary、観点別抽出結果、根拠不足 warning、evidence table、retrieval backend 表示を追加する。
- Decision Report: Research Evidence section、Grounded Answer section、Data Quality section、Retrieval Quality section、根拠不足 warning、売買推奨ではない旨の注記を追加する。

Current implementation note: cockpit and ranking Research Summary panels now build a local `CompanyResearchSummary` as the primary company-understanding report, then show `ResearchBrief`, AI reading notes, confirmation-point cards, Research Score summary/component/warning rows, and detailed `CompanyResearchReport.grounded_answer`, `CompanyResearchReport.retrieval_quality`, and `ResearchExtractedClaim` rows behind secondary sections. Ranking selected-candidate breakdown can show report-derived Research Score context, the Cockpit Research Evidence panel can explicitly fetch TDnet + Yahoo Finance external profile/news, and the Cockpit Decision Report carries both `Research Evidence` and `Research Score` sections when a Research report has documents or evidence. External live fetch should be transient by default; ranking order and default Investment Score behavior remain unchanged.

### Phase 21 Test Plan

- Unit: query expansion、ResearchExtractedClaim validation、embedding cache key generation、vector store disabled mode、hybrid score calculation、evidence reranking、template answer generation、confirmation_gap generation。
- Integration: sample Markdown/Text/CSV -> chunk -> keyword search -> query expansion -> evidence extraction -> grounded answer -> Decision Report section。
- Fallback: embedding disabled 時は keyword search のみ、vector store failure 時は keyword fallback、LLM disabled 時は template answer、evidence 不足時は confirmation_gap。
- Golden: 既知の Research 資料から期待するカテゴリ別抽出、warning、根拠のない主張を生成しないことを確認。
- CI: 外部 API、外部 LLM、live scraping、network に依存しない。

## 1) Purpose & Scope

* **Purpose**: IR資料・有価証券報告書・決算資料・中期経営計画・統合報告書・ニュース等の非構造データを検索し、長期企業分析の根拠提示を行う。高度RAG抽出、根拠付き回答生成、Research Score 初期 slice、CompanyResearchSummary / ResearchBrief 初期 slice は実装済みで、次は表示 polish と追加 source adapter を扱う。
* **Scope**: ローカル資料登録、テキスト抽出、チャンク化、メタデータ管理、キーワード検索、企業リサーチサマリ、ResearchBrief、Decision Report への接続。ベクトル/ハイブリッド検索と根拠付き回答生成の初期 slice、Research Score 初期 slice は実装済み。Assistant / ranking order への接続は後続。
* **Out of Scope**: RAG単体での売買推奨、自動売買判断、証券口座ログイン情報の取得、規約違反リスクのある無制限スクレイピング、外部LLM/APIを必須にする実装。

### 1.1 前提

* 通常ユーザー導線は **external-fresh-source first**、通常 tests / CI は **deterministic fixture first** とする。
* Phase 20 MVP は UTF-8 Markdown / Text / CSV の手動登録資料を対象にする。PDF は後続対応候補。
* 外部取得は `AI調査を更新` の標準 source とする。TDnet + Yahoo Finance は初期 slice 実装済みで、EDINET / IR RSS / 企業IR / News API 等は adapter として段階的に追加する。
* RAGの出力は、投資助言ではなく「判断材料・根拠・注意点」の整理に限定する。
* Research Score は optional input として初期 slice 実装済み。既定では `scoring.weights.research=0.0` とし、既存スコアや ranking order を壊さない。

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
        """検索結果を使い、企業の長期評価サマリを返す。Research Score は別サービスで参考表示する。"""
```

* Phase 20 実装済み例外: `ResearchDocumentError`, `ResearchParseError`, `ResearchSearchError`
* `healthcheck()`, `metrics()`, `reload_config()` は Phase 21+ の運用拡張候補。

## 3) Current Phase 20 Data Contracts (Pydantic)

```python
class ResearchDocument(BaseModel):
    schema_version: str = "research-evidence-v1"
    document_id: str
    symbol: str
    title: str
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
    company_name: str | None = None
    published_at: date | None = None
    collected_at: datetime
    local_path: str
    language: Literal["ja", "en", "unknown"] = "unknown"
    provider: str = "local"
    reliability: Decimal
    document_hash: str

class ResearchChunk(BaseModel):
    schema_version: str = "research-evidence-v1"
    chunk_id: str
    document_id: str
    symbol: str
    title: str
    source_type: str
    published_at: date | None = None
    section_title: str | None = None
    text: str
    chunk_index: int
    char_count: int
    metadata: dict[str, str] = {}

class ResearchEvidence(BaseModel):
    symbol: str
    document_id: str
    chunk_id: str
    title: str
    source_type: str
    published_at: date | None = None
    section_title: str | None = None
    excerpt: str
    relevance_score: Decimal
    reliability: Decimal

class ResearchSummaryPoint(BaseModel):
    category: Literal[
        "growth",
        "shareholder_return",
        "financial_safety",
        "business_risk",
        "confirmation_gap",
    ]
    label: str
    summary: str
    evidence: list[ResearchEvidence]

class ResearchDataQuality(BaseModel):
    status: Literal["OK", "WARN", "BLOCK"]
    latest_document_date: date | None
    document_count: int
    evidence_count: int
    warnings: list[str]

class CompanyResearchReport(BaseModel):
    schema_version: str = "research-evidence-v1"
    symbol: str
    as_of: date
    summary: str
    points: list[ResearchSummaryPoint]
    evidence: list[ResearchEvidence]
    data_quality: ResearchDataQuality
    decision_support_note: str
```

### 3.1 Research Score 現状 / Future Notes

Research Score 初期 slice は、evidence / extracted claim に紐づく参考情報として実装済み。optional input として扱い、明示的に weight を設定しない限り default Investment Score / ranking order には影響させない。

```python
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
    confidence: Decimal
    summary: str
```

Current implementation note: `ResearchScore` and `ResearchScoreService` are available as the first Research Score MVP slice. The service scores evidence coverage for growth, profitability, shareholder return, financial safety, business risk disclosure, disclosure quality, and freshness from `CompanyResearchReport`, keeps supporting evidence, confidence, warnings, and a non-advice summary, and does not change Investment Score or ranking order by default. Cockpit / Ranking Research Summary panels show Research Score as reference context, and Cockpit Decision Report adds a `Research Score` section when a Research report with documents or evidence is present.

## 4) Algorithms & Rules

### 4.1 Document Ingestion

* MVPの deterministic foundation はローカルファイル登録だが、通常ユーザー導線は外部 source adapter を優先する。
* 登録時に `symbol`, `source_type`, `title`, `published_at`, `provider`, `reliability` を必須または推奨メタデータとして扱う。
* 外部URL取得は source adapter 経由で扱い、通常 tests / CI では fake adapter を使う。実装上の backend safety gate は残してよいが、UIでは `AI調査を更新` が標準導線になる。
* 同一資料の重複は `document_hash` または `source_url + published_at + title` で検知する。

### 4.2 Text Extraction / Chunking

* Phase 20 MVP は UTF-8 Markdown / Text / CSV を対象に開始する。PDF は後続フェーズで扱う。
* 画像OCR、図表構造化、表の厳密抽出は後続フェーズに回す。
* chunk は `DEFAULT_MAX_CHARS` / `DEFAULT_OVERLAP_CHARS` を基準に文字数で分割する。
* section title、source_type、published_at を保持する。page は PDF 対応時の拡張候補。
* 本文抽出できない資料は `ResearchParseError` とし、空文字の chunk を作らない。

### 4.3 Retrieval

* Phase R3 は keyword search をMVPとする。
* Phase R5 で embedding + vector store を追加し、keyword + vector の hybrid search に拡張する。
* 検索結果は `relevance_score`, `reliability`, `published_at`, `source_type` を持つ。
* 古い資料は freshness penalty を与え、最新資料と過去資料の混在をUIで見えるようにする。

### 4.4 Research Analysis / Score

* Phase 20 は Research Summary / Research Evidence / Research Data Quality を返す。
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

* `research_score` は Investment Score に optional input として渡せるが、既定 weight は 0.0 とする。
* Research Score が無い銘柄でも既存の Screening / Forecast / Risk / Data Quality score は動作する。
* 初期重みは `research: 0.0` または低めにし、UI上で「研究情報を参考表示」として扱う。

Current implementation note: Investment Score accepts optional `research_scores_by_symbol` input and `scoring.weights.research` with default `0.0`. When the weight remains `0.0`, Research Score is carried as optional context but does not change total score, score band, breakdown, or ranking order. When explicitly weighted, missing Research Score uses a neutral 50 input with a warning rather than treating missing evidence as a bad security. Research Summary panels and Decision Report can display Research Score as reference context with component rows, confidence, supporting evidence, warnings, and non-advice notes.

## 5) Error Handling & Retries

* ローカルファイルが無い/読めない: `ResearchDocumentError`
* PDF本文抽出不可: PDF対応時は `ResearchParseError`
* chunk生成不可: Phase 20 実装では `ResearchParseError`
* index未構築: `ResearchSearchError` または空結果 + warning
* 外部ソース取得失敗: provider error を `details` に保持し、通常CIでは実行しない
* LLM/embedding adapter失敗: fallbackとして keyword search / template summary に戻す

## 6) Idempotency & Security

* 登録資料は `document_hash` で重複検知する。
* ローカルファイルパスは設定済み `research.document_dirs` 配下に限定する。
* 外部取得は source adapter ごとに robots / 利用規約 / rate limit を尊重する。UI上の個別許可checkboxではなく、`AI調査を更新` の外部情報取得として分かる表示にする。
* APIキーや外部LLMのcredentialはSecret管理し、ログに出さない。
* RAG回答には、資料タイトル、公開日、ページ番号などの根拠を付ける。
* 著作権保護の観点から、長い本文の丸写しを避け、短い引用または要約に留める。

## 7) Performance Budget

* `register_document`: 1資料 P95 < 2s（PDF本文抽出は後続フェーズのため除く）
* `build_chunks`: Phase 20 の UTF-8 text chunking は通常 UI 操作を妨げない範囲に収める。PDF の P95 は後続対応時に設定する。
* `search`: keyword search P95 < 500ms、vector search P95 < 1s
* `analyze_company`: cached evidence 利用時 P95 < 3s
* AI調査の通常UI操作は外部 source adapter を使う前提にする。通常 tests / CI は fake adapter / fixture で代替し、外部API/LLMに依存しない。

## 8) Observability

* ログ: `corr_id, symbol, document_id, source_type, provider, chunk_count, latency_ms, status`
* メトリクス: `research_documents_total`, `research_chunks_total`, `research_search_latency_ms`, `research_empty_result_total`, `research_parse_error_total`
* トレース: ingestion -> extraction -> chunking -> index -> retrieval -> analysis のspan化
* UI/Reportでは `latest_document_date`, `document_count`, `evidence_count`, `data_quality.status` を表示する。

## 9) Config Knobs（config.yml）

```yaml
research:
  enabled: true
  provider: external_first
  document_dirs:
    - data/research_docs
  allow_external_sources: true
  chunking:
    max_chars: 1200
    overlap_chars: 180
  retrieval:
    backend: keyword # keyword|vector|hybrid
    top_k: 8
    freshness_half_life_days: 365
  embeddings:
    enabled: false
    provider: local
    model: null
  scoring:
    enabled: false # optional integration
    default_weight_in_investment_score: 0.0
  external_sources:
    edinet: false
    tdnet: false
    news: false
```

## 10) Test Plan

* **Unit**: document metadata validation、chunking、重複検知、Research Data Quality、extraction / grounded answer、Research Score rule scoring、ResearchBrief builder。
* **Integration**: sample Markdown/Text/CSV -> chunk -> search -> report の一連フロー
* **Golden Test**: 既知のIRサンプルから期待する evidence / summary / warning を返す
* **Property-based**: chunk文字数、chunk順序、空本文の扱い、不変条件検証
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
