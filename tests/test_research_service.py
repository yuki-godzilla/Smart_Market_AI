import hashlib
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.config import PERFORMANCE_PROFILE_ENV, ExternalFetchPerformanceConfig
from backend.research import (
    CompanyBusinessProfile,
    CompanyIRSiteResearchAdapter,
    CompanyResearchReport,
    CompanyResearchRequest,
    CompanyResearchSummaryBuilder,
    CompositeExternalResearchAdapter,
    DefaultExternalResearchAdapter,
    EDINETResearchAdapter,
    ETFResearchSummaryBuilder,
    ExternalResearchFetchManifestEntry,
    ExternalResearchFetchRequest,
    ExternalResearchFetchResult,
    ExternalResearchFetchService,
    ExternalResearchSourcePayload,
    ExternalResearchStockNewsAdapter,
    ExternalStockNewsFetchService,
    GoogleNewsRSSResearchAdapter,
    HybridResearchRetrievalService,
    InvestmentInsightBuilder,
    InvestmentQuestionSummaryBuilder,
    ResearchAnalysisService,
    ResearchBrief,
    ResearchBriefBuilder,
    ResearchChunk,
    ResearchDataQuality,
    ResearchDisabledVectorStore,
    ResearchDocumentError,
    ResearchDocumentRegisterRequest,
    ResearchEmbedding,
    ResearchEmbeddingService,
    ResearchEvidence,
    ResearchEvidenceReranker,
    ResearchFileVectorStore,
    ResearchHybridScorer,
    ResearchIndexService,
    ResearchIngestionService,
    ResearchInMemoryStore,
    ResearchInMemoryVectorStore,
    ResearchMetric,
    ResearchPageViewModelBuilder,
    ResearchQueryExpansionService,
    ResearchRetrievalCandidate,
    ResearchRetrievalQuality,
    ResearchRetrievalService,
    ResearchScoreService,
    ResearchSearchError,
    ResearchSearchRequest,
    ResearchSourceTrace,
    ResearchSummaryPoint,
    ResearchVectorIndexService,
    SecurityResearchTypeDetector,
    StockNewsAnalysisService,
    StockNewsEvidence,
    StockNewsReport,
    StockNewsRequest,
    TDnetResearchAdapter,
    YahooFinanceResearchAdapter,
    research_profile_source_key_for_provider,
)

FORBIDDEN_RECOMMENDATION_WORDS = [
    "買い推奨",
    "購入推奨",
    "売り推奨",
    "売却推奨",
    "今すぐ買う",
    "今すぐ売る",
    "割安です",
    "割高です",
]


class FakeExternalResearchAdapter:
    provider = "fake_external"
    requires_network = False

    def __init__(self, payloads: list[ExternalResearchSourcePayload]) -> None:
        self.payloads = payloads

    def fetch_sources(
        self, request: ExternalResearchFetchRequest
    ) -> list[ExternalResearchSourcePayload]:
        return self.payloads


class NetworkExternalResearchAdapter(FakeExternalResearchAdapter):
    requires_network = True


class FailingExternalResearchAdapter(FakeExternalResearchAdapter):
    provider = "failing_external"

    def fetch_sources(
        self, request: ExternalResearchFetchRequest
    ) -> list[ExternalResearchSourcePayload]:
        raise ResearchDocumentError("provider failed")


class TimeoutExternalResearchAdapter(FakeExternalResearchAdapter):
    provider = "timeout_external"

    def fetch_sources(
        self, request: ExternalResearchFetchRequest
    ) -> list[ExternalResearchSourcePayload]:
        raise TimeoutError("provider timed out")


class SlowExternalResearchAdapter(FakeExternalResearchAdapter):
    provider = "slow_external"

    def fetch_sources(
        self, request: ExternalResearchFetchRequest
    ) -> list[ExternalResearchSourcePayload]:
        time.sleep(0.2)
        return self.payloads


class FakeHTTPStatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.response = SimpleNamespace(status_code=status_code)


class FakeYahooTicker:
    def get_info(self) -> dict[str, object]:
        return {
            "longName": "Toyota Motor Corporation",
            "symbol": "7203.T",
            "currency": "JPY",
            "sector": "Consumer Cyclical",
            "industry": "Auto Manufacturers",
            "marketCap": 35_000_000_000_000,
            "enterpriseValue": 37_000_000_000_000,
            "totalRevenue": 45_000_000_000_000,
            "operatingIncome": 5_000_000_000_000,
            "netIncomeToCommon": 4_000_000_000_000,
            "trailingEps": 320.12,
            "forwardPE": 10.4,
            "trailingPE": 12.5,
            "priceToBook": 1.2,
            "returnOnEquity": 0.124,
            "dividendYield": 0.021,
            "fullTimeEmployees": 380_000,
            "longBusinessSummary": "Toyota sells vehicles globally and invests in growth.",
        }

    @property
    def news(self) -> list[dict[str, object]]:
        return [
            {
                "title": "Toyota raises guidance",
                "link": "https://finance.yahoo.com/news/toyota-guidance",
                "publisher": "Yahoo Finance",
                "providerPublishTime": 1779667200,
                "summary": "Toyota raised guidance after revenue growth.",
            }
        ]


def test_research_local_document_flow_registers_chunks_searches_and_summarizes(
    tmp_path,
):
    document_path = tmp_path / "7203_research.md"
    document_path.write_text(
        """# 7203 Research Note

## Growth

The company explains growth strategy through hybrid demand, software revenue, and
market expansion outside Japan.

## Shareholder Return

Dividend policy and shareholder return remain part of the capital allocation plan.

## Risk

Business risk includes competition, supply constraints, and foreign exchange demand.
""",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    document = ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="7203 Research Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
            reliability=Decimal("0.80"),
        )
    )
    summary = index.rebuild_index(symbol="7203.T")
    evidence = retrieval.search(
        ResearchSearchRequest(symbol="7203.T", query="growth strategy market", top_k=2)
    )
    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 24))
    )

    assert document.symbol == "7203.T"
    assert summary.document_count == 1
    assert summary.chunk_count >= 3
    assert evidence
    assert evidence[0].title == "7203 Research Note"
    assert evidence[0].reliability == Decimal("0.80")
    assert report.data_quality.status == "OK"
    assert report.data_quality.document_count == 1
    assert any(point.category == "growth" and point.evidence for point in report.points)
    growth_claim = next(claim for claim in report.extracted_claims if claim.category == "growth")
    assert growth_claim.supporting_evidence
    assert growth_claim.confidence > Decimal("0")
    assert "売買推奨ではありません" in (growth_claim.caution_note or "")
    assert report.grounded_answer is not None
    assert report.grounded_answer.provider == "template"
    assert report.grounded_answer.referenced_evidence
    assert "売買推奨ではなく" in report.grounded_answer.answer
    assert report.retrieval_quality is not None
    assert report.retrieval_quality.backend == "keyword"
    assert report.retrieval_quality.candidate_count >= report.retrieval_quality.evidence_count
    assert report.retrieval_quality.evidence_count == len(report.evidence)
    assert "growth" in report.retrieval_quality.query
    assert "strategy" in report.retrieval_quality.expanded_terms


def test_research_score_service_scores_evidence_backed_report(tmp_path):
    document_path = tmp_path / "7203_score_note.md"
    document_path.write_text(
        """# 7203 Research Score Note

## Growth

Growth strategy includes market expansion, software revenue, profitability margin,
operating income improvement, and ROE improvement.

## Shareholder Return

Shareholder return includes dividend policy and buyback capacity.

## Financial Safety

Financial safety includes cash, equity capital, liquidity, and balance sheet strength.

## Business Risk

Business risk includes competition, regulation, supply chain, and foreign exchange.
""",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    ResearchIndexService(store, max_chars=260).rebuild_index(symbol="7203.T")
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="7203 Research Score Note",
            local_path=str(document_path),
            source_type="annual_report",
            published_at=date(2026, 5, 1),
            reliability=Decimal("0.90"),
        )
    )
    ResearchIndexService(store, max_chars=260).rebuild_index(symbol="7203.T")
    report = ResearchAnalysisService(
        ingestion,
        ResearchRetrievalService(store),
    ).analyze_company(CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 25)))

    score = ResearchScoreService().score_report(report)

    assert score.schema_version == "research-score-v1"
    assert score.symbol == "7203.T"
    assert score.total_score > Decimal("0")
    assert score.growth_score > Decimal("0")
    assert score.profitability_score > Decimal("0")
    assert score.shareholder_return_score > Decimal("0")
    assert score.financial_safety_score > Decimal("0")
    assert score.business_risk_score > Decimal("0")
    assert score.disclosure_quality_score > Decimal("0")
    assert score.freshness_score == Decimal("100.00")
    assert score.evidence_count == len(report.evidence)
    assert score.confidence > Decimal("0")
    assert score.supporting_evidence
    assert "売買推奨ではなく" in score.summary
    assert "not advice" in score.decision_support_note


def test_research_score_service_marks_missing_evidence_low_confidence():
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store)
    report = ResearchAnalysisService(
        ingestion,
        ResearchRetrievalService(store),
    ).analyze_company(CompanyResearchRequest(symbol="MSFT", as_of=date(2026, 5, 24)))

    score = ResearchScoreService().score_report(report)

    assert score.total_score == Decimal("0.00")
    assert score.confidence == Decimal("0")
    assert score.evidence_count == 0
    assert score.supporting_evidence == []
    assert any("根拠不足" in warning for warning in score.warnings)
    assert "売買判断ではありません" in score.summary


def test_research_brief_builder_shapes_readable_local_memo():
    provider_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Provider Symbol: 7203.T\n"
            "Quote Type: EQUITY\n"
            "Currency: JPY\n"
            "Toyota sells vehicles globally and invests in software services.\n"
            "Market Cap: 35,000,000,000,000 JPY\n"
            "PER: 12.5倍\n"
            "PBR: 1.1倍\n"
            "ROE: 9.8%"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    official_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-ir",
        chunk_id="chunk-ir",
        title="7203 決算短信",
        source_type="earnings_report",
        published_at=date(2026, 5, 20),
        section_title="業績",
        excerpt=(
            "売上高 45兆円、営業利益 5兆円、純利益 4兆円、"
            "EPS 320円、配当 75円。通期予想は売上高46兆円、営業利益5.2兆円です。"
            "配当方針は安定配当と増配を重視します。"
            "日本、北米、欧州で車両販売とソフトウェアサービスを展開しています。"
            "成長戦略と株主還元を説明しています。"
        ),
        relevance_score=Decimal("0.88"),
        reliability=Decimal("0.94"),
    )
    risk_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-risk",
        chunk_id="chunk-risk",
        title="TDnet 適時開示",
        source_type="tdnet",
        published_at=date(2026, 5, 22),
        section_title="Risk",
        excerpt="供給制約と為替変動が事業リスクとして説明されています。",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.90"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="3件の根拠から確認材料を整理しました。",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="成長戦略は決算短信を主な確認材料として見ます。",
                evidence=[official_evidence],
            ),
            ResearchSummaryPoint(
                category="business_risk",
                label="事業リスク",
                summary="供給制約と為替変動を注意材料候補として見ます。",
                evidence=[risk_evidence],
            ),
        ],
        evidence=[official_evidence, provider_evidence, risk_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=3,
            evidence_count=3,
            warnings=[],
        ),
    )
    news_report = StockNewsReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                title="Toyota raises guidance",
                url="https://example.com/toyota-guidance",
                source="Example News",
                published_at=date(2026, 5, 24),
                summary="Guidance was raised after revenue growth.",
                investment_viewpoint="growth",
                sentiment_for_investment="positive",
                freshness_status="latest",
            )
        ],
    )
    external_result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="fake_external",
        fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="TDnet 7203",
                symbol="7203.T",
                source_type="tdnet",
                source_url="https://example.com/tdnet/7203",
                provider="tdnet",
                published_at=date(2026, 5, 22),
                fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
                freshness_status="latest",
                document_id="external-tdnet",
            )
        ],
    )

    brief = ResearchBriefBuilder().build(
        report,
        news_report=news_report,
        external_research_result=external_result,
    )

    metric_labels = {metric.label for metric in brief.metrics}
    assert {
        "売上高",
        "営業利益",
        "純利益",
        "EPS",
        "配当",
        "PER",
        "PBR",
        "ROE",
        "時価総額",
    } <= metric_labels
    assert brief.missing_metrics == []
    assert "自動車・モビリティ関連事業" in brief.business_overview
    assert "公式IR" in brief.business_overview
    assert "Toyota sells vehicles" not in brief.business_overview
    assert "Provider Symbol" not in brief.business_overview
    assert "Quote Type" not in brief.business_overview
    assert "売買推奨ではありません" in brief.memo
    assert any("成長材料" in candidate for candidate in brief.positive_candidates)
    assert any("Toyota raises guidance" in candidate for candidate in brief.positive_candidates)
    assert any("供給制約" in candidate for candidate in brief.caution_candidates)
    assert any(
        material.source_type == "earnings_report" and material.source_confidence == "high"
        for material in brief.positive_materials
    )
    assert any(
        material.source_type == "news" and material.source_confidence == "medium"
        for material in brief.positive_materials
    )
    assert any(
        material.source_type == "tdnet" and material.source_confidence == "high"
        for material in brief.caution_materials
    )
    assert not any(
        "主な確認材料として見ます" in candidate for candidate in brief.positive_candidates
    )
    assert any(card.source_confidence == "high" for card in brief.source_cards)
    assert any(card.source_confidence == "medium" for card in brief.source_cards)
    assert any(card.source_url == "https://example.com/tdnet/7203" for card in brief.source_cards)
    assert brief.fact_summary is not None
    assert brief.fact_summary.business_overview
    assert brief.fact_summary.business_segments[0].label == "主要事業"
    assert "自動車・モビリティ" in brief.fact_summary.business_segments[0].value
    assert any("北米" in item.value for item in brief.fact_summary.business_regions)
    assert any("製品・車両販売" in item.value for item in brief.fact_summary.revenue_drivers)
    financial_labels = {item.label for item in brief.fact_summary.financial_snapshot}
    assert {"売上高", "営業利益", "純利益", "EPS", "配当"} <= financial_labels
    assert any("通期予想" in item.value for item in brief.fact_summary.earnings_outlook)
    assert any("配当方針" in item.value for item in brief.fact_summary.shareholder_return_policy)
    assert any(item.label == "決算短信" for item in brief.fact_summary.recent_events)
    assert any(item.label == "適時開示" for item in brief.fact_summary.recent_events)
    assert any(item.label == "成長材料" for item in brief.fact_summary.positive_materials)
    assert any(item.label == "事業リスク" for item in brief.fact_summary.caution_materials)
    assert brief.fact_summary.missing_items == []


def test_company_research_summary_builder_splits_overview_metrics_ir_and_news():
    provider_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Toyota sells vehicles globally and provides financial services. "
            "Market Cap: 35,000,000,000,000 JPY PER: 12.5倍 PBR: 1.1倍 ROE: 9.8%"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    official_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-ir",
        chunk_id="chunk-ir",
        title="7203 決算短信",
        source_type="earnings_report",
        published_at=date(2026, 5, 20),
        section_title="業績",
        excerpt=(
            "売上高 45兆円、営業利益 5兆円、純利益 4兆円、EPS 320円、配当 75円。"
            "通期予想は売上高46兆円、営業利益5.2兆円です。"
            "日本、北米、欧州で車両販売と金融サービスを展開しています。"
        ),
        relevance_score=Decimal("0.88"),
        reliability=Decimal("0.94"),
    )
    tdnet_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-tdnet",
        chunk_id="chunk-tdnet",
        title="TDnet 7203 適時開示",
        source_type="tdnet",
        published_at=date(2026, 5, 22),
        section_title="開示",
        excerpt="適時開示で自社株買いと株主還元方針を説明しています。",
        relevance_score=Decimal("0.82"),
        reliability=Decimal("0.90"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence, official_evidence, tdnet_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=3,
            evidence_count=3,
            warnings=[],
        ),
    )
    news_report = StockNewsReport(
        symbol="7203.T",
        company_name="Toyota Motor Corporation",
        as_of=date(2026, 5, 25),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                title="Toyota expands software services",
                url="https://example.com/toyota-software",
                source="Example News",
                published_at=date(2026, 5, 24),
                summary="Toyota expanded software services in global markets.",
                investment_viewpoint="growth",
                sentiment_for_investment="positive",
                freshness_status="latest",
            )
        ],
    )
    external_result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="fake_external",
        fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="TDnet 7203 適時開示",
                symbol="7203.T",
                source_type="tdnet",
                source_url="https://example.com/tdnet/7203",
                provider="tdnet",
                published_at=date(2026, 5, 22),
                fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
                freshness_status="latest",
                document_id="external-tdnet",
                content_summary="自社株買いと株主還元方針を説明しています。",
            )
        ],
    )

    summary = CompanyResearchSummaryBuilder().build(
        report,
        news_report=news_report,
        external_research_result=external_result,
    )

    ir_by_type = {item.document_type: item for item in summary.ir_items}
    dumped = str(summary.model_dump(mode="json"))

    assert summary.schema_version == "company-research-summary-v1"
    assert summary.overview.company_name == "Toyota Motor Corporation"
    assert "自動車" in summary.overview.business_overview
    assert "日本" in summary.overview.regions
    assert summary.quantitative.revenue == "45兆円"
    assert summary.quantitative.operating_profit == "5兆円"
    assert summary.quantitative.per == "12.5倍"
    assert summary.quantitative.market_cap == "35兆円"
    assert ir_by_type["決算短信"].availability == "found"
    assert ir_by_type["適時開示"].availability == "found"
    assert ir_by_type["配当・自社株買い"].source_url == "https://example.com/tdnet/7203"
    assert summary.news_items[0].topic_type == "product"
    assert summary.news_items[0].impact_hint == "product"
    assert summary.news_items[0].official_confirmation_required is True
    assert summary.news_items[0].information_status == "unverified"
    assert summary.ai_reading_notes
    assert not any(term in dumped for term in FORBIDDEN_RECOMMENDATION_WORDS)


def test_company_research_summary_builder_keeps_missing_items_explicit():
    report = CompanyResearchReport(
        symbol="MSFT",
        as_of=date(2026, 5, 25),
        summary="No source-backed evidence.",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=["登録済みResearch資料がありません。"],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)

    assert summary.overview.evidence_level == "missing"
    assert summary.quantitative.evidence_level == "missing"
    assert summary.quantitative.revenue is None
    assert "売上高" in summary.quantitative.missing_items
    assert all(item.availability == "missing" for item in summary.ir_items)
    assert summary.news_items == []
    assert "直近ニュース・開示" in summary.missing_critical_items
    assert "外部プロフィールから一部情報は確認できます" in summary.overview.business_overview


def test_security_research_type_detector_classifies_stock_and_etf_types():
    detector = SecurityResearchTypeDetector()

    etf_report = CompanyResearchReport(
        symbol="SPY",
        as_of=date(2026, 5, 25),
        summary="ETF profile.",
        points=[],
        evidence=[
            ResearchEvidence(
                symbol="SPY",
                document_id="doc-etf",
                chunk_id="chunk-etf",
                title="SPY Provider Profile",
                source_type="provider_profile",
                published_at=date(2026, 5, 24),
                section_title="Profile",
                excerpt="Quote Type: ETF\nExchange: NYSEARCA\nFund Name: SPDR S&P 500 ETF Trust",
                relevance_score=Decimal("0.72"),
                reliability=Decimal("0.68"),
            )
        ],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    domestic_report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Domestic equity profile.",
        points=[],
        evidence=[
            ResearchEvidence(
                symbol="7203.T",
                document_id="doc-equity-jp",
                chunk_id="chunk-equity-jp",
                title="Toyota Provider Profile",
                source_type="provider_profile",
                published_at=date(2026, 5, 24),
                section_title="Profile",
                excerpt="Quote Type: EQUITY\nExchange: TSE",
                relevance_score=Decimal("0.72"),
                reliability=Decimal("0.68"),
            )
        ],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    foreign_report = CompanyResearchReport(
        symbol="MSFT",
        as_of=date(2026, 5, 25),
        summary="Foreign equity profile.",
        points=[],
        evidence=[
            ResearchEvidence(
                symbol="MSFT",
                document_id="doc-equity-us",
                chunk_id="chunk-equity-us",
                title="Microsoft Provider Profile",
                source_type="provider_profile",
                published_at=date(2026, 5, 24),
                section_title="Profile",
                excerpt="Quote Type: EQUITY\nExchange: NASDAQ",
                relevance_score=Decimal("0.72"),
                reliability=Decimal("0.68"),
            )
        ],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    unknown_report = CompanyResearchReport(
        symbol="12345",
        as_of=date(2026, 5, 25),
        summary="No type metadata.",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=[],
        ),
    )

    assert detector.detect(etf_report) == "etf"
    assert detector.detect(domestic_report) == "domestic_stock"
    assert detector.detect(foreign_report) == "foreign_stock"
    assert detector.detect(unknown_report) == "unknown"


def test_etf_research_summary_builder_maps_fund_fields_without_company_ir_requirements():
    provider_evidence = ResearchEvidence(
        symbol="SPY",
        document_id="doc-etf",
        chunk_id="chunk-etf",
        title="SPY Provider Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: SPDR S&P 500 ETF Trust Provider Symbol: SPY "
            "Quote Type: ETF Exchange: PCX Currency: USD Website: https://example.com\n"
            "Fund Family: State Street\n"
            "Currency: USD\n"
            "Benchmark: S&P 500\n"
            "Asset Category: ETF\n"
            "Expense Ratio: 0.09%\n"
            "Dividend Yield: 1.2%\n"
            "AUM: 500,000,000,000 USD\n"
            "NAV: 540.25 USD\n"
            "Trailing PE: 22.5\n"
            "Price To Book: 4.1\n"
            "Top Holdings: Apple, Microsoft, NVIDIA, Amazon\n"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="SPY",
        as_of=date(2026, 5, 25),
        summary="ETF profile.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = ETFResearchSummaryBuilder().build(report)
    page_model = ResearchPageViewModelBuilder().build(report)

    assert page_model.security_type == "etf"
    assert page_model.etf_summary is not None
    assert page_model.company_summary is None
    assert page_model.question_summary is None
    assert summary.fund_name == "SPDR S&P 500 ETF Trust"
    assert summary.provider_name == "State Street"
    assert summary.benchmark_index == "S&P 500"
    assert summary.expense_ratio == "0.09%"
    assert summary.dividend_yield == "1.2%"
    assert summary.aum == "500B USD"
    assert summary.nav == "540.25 USD"
    assert summary.per == "22.5倍"
    assert summary.pbr == "4.1倍"
    assert summary.top_holdings[:3] == ["Apple", "Microsoft", "NVIDIA"]
    assert "Provider Symbol" not in summary.fund_name
    assert "Quote Type" not in summary.fund_overview
    assert "Website:" not in summary.fund_overview
    assert "経費率" not in summary.missing_items
    assert "上位保有銘柄" not in summary.missing_items
    dumped = str(summary.model_dump(mode="json"))
    assert "決算短信" not in dumped
    assert "有価証券報告書" not in dumped


def test_etf_research_summary_builder_maps_extended_provider_fields_and_non_equity_ratios():
    provider_evidence = ResearchEvidence(
        symbol="TLT",
        document_id="doc-etf-bond",
        chunk_id="chunk-etf-bond",
        title="TLT Provider Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: iShares 20+ Year Treasury Bond ETF\n"
            "Quote Type: ETF\n"
            "Fund Family: iShares\n"
            "Category: Long Government\n"
            "Asset Category: Bond\n"
            "Annual Report Expense Ratio: 0.15%\n"
            "Net Assets: 48,000,000,000 USD\n"
            "NAV Price: 90.25 USD\n"
            "Trailing Annual Dividend Yield: 4.5%\n"
            "Trailing PE: -4287\n"
            "Price To Book: 0.58\n"
            "Top Holdings: U.S. Treasury 4.0%, U.S. Treasury 3.5%\n"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="TLT",
        as_of=date(2026, 5, 25),
        summary="ETF profile.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = ETFResearchSummaryBuilder().build(report)

    assert summary.provider_name == "iShares"
    assert summary.asset_class == "債券"
    assert summary.expense_ratio == "0.15%"
    assert summary.aum == "48B USD"
    assert summary.nav == "90.25 USD"
    assert summary.dividend_yield == "4.5%"
    assert summary.per is None
    assert summary.pbr is None
    assert summary.top_holdings[:2] == ["U.S. Treasury 4.0%", "U.S. Treasury 3.5%"]
    assert "経費率" not in summary.missing_items
    assert "純資産総額" not in summary.missing_items
    assert "基準価額 / NAV" not in summary.missing_items


def test_etf_research_summary_builder_adds_asset_specific_missing_guidance():
    provider_evidence = ResearchEvidence(
        symbol="BND",
        document_id="doc-etf-bond-missing",
        chunk_id="chunk-etf-bond-missing",
        title="BND Provider Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Vanguard Total Bond Market Index Fund\n"
            "Quote Type: ETF\n"
            "Category: Total Bond Market\n"
            "Asset Category: Bond\n"
            "Dividend Yield: 3.9%\n"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="BND",
        as_of=date(2026, 5, 25),
        summary="ETF profile.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = ETFResearchSummaryBuilder().build(report)

    assert summary.asset_class == "債券"
    assert "経費率" in summary.missing_items
    assert "上位保有銘柄" in summary.missing_items
    assert any("債券ETFとして" in note for note in summary.risk_notes)
    assert any("経費率は未取得" in note for note in summary.risk_notes)
    assert any("上位保有銘柄は未取得" in note for note in summary.risk_notes)
    dumped = str(summary.model_dump(mode="json"))
    assert "決算短信" not in dumped
    assert "有価証券報告書" not in dumped


def test_company_research_summary_builder_maps_provider_quantitative_fields():
    provider_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Toyota Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Toyota Motor Corporation\n"
            "Market Cap: 35,000,000,000,000 JPY\n"
            "Enterprise Value: 37,000,000,000,000 JPY\n"
            "Total Revenue: 45,000,000,000,000 JPY\n"
            "Operating Income: 5,000,000,000,000 JPY\n"
            "Net Income To Common: 4,000,000,000,000 JPY\n"
            "Trailing EPS: 320.12\n"
            "Forward PE: 10.4\n"
            "Price To Book: 1.2\n"
            "Return On Equity: 12.4%\n"
            "Dividend Yield: 2.1%\n"
            "Full Time Employees: 380,000 人\n"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)

    assert summary.quantitative.market_cap == "35兆円"
    assert summary.quantitative.enterprise_value == "37兆円"
    assert summary.quantitative.revenue == "45兆円"
    assert summary.quantitative.operating_profit == "5兆円"
    assert summary.quantitative.net_income == "4兆円"
    assert summary.quantitative.eps == "320.12"
    assert summary.quantitative.per == "10.4倍"
    assert summary.quantitative.pbr == "1.2倍"
    assert summary.quantitative.roe == "12.4%"
    assert summary.quantitative.dividend_yield == "2.1%"
    assert summary.quantitative.employee_count == "380,000 人"
    assert "売上高" not in summary.quantitative.missing_items
    assert "PER" not in summary.quantitative.missing_items
    assert "PBR" not in summary.quantitative.missing_items
    assert "ROE" not in summary.quantitative.missing_items
    assert "配当利回り" not in summary.quantitative.missing_items
    assert "従業員数" not in summary.quantitative.missing_items
    assert "企業価値" not in summary.quantitative.missing_items
    assert "Toyota Yahoo Finance Profile" in summary.quantitative.source_titles


def test_company_research_summary_builder_compacts_large_usd_quantitative_fields():
    provider_evidence = ResearchEvidence(
        symbol="MSFT",
        document_id="doc-profile-usd",
        chunk_id="chunk-profile-usd",
        title="Microsoft Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Microsoft Corporation\n"
            "Currency: USD\n"
            "Market Cap: 1,660,405,547,008\n"
            "Enterprise Value: 1,632,438,567,424\n"
            "Total Revenue: 97,878,999,040\n"
            "Net Income To Common: 3,862,000,128\n"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="MSFT",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)

    assert summary.quantitative.market_cap == "1.66T USD"
    assert summary.quantitative.enterprise_value == "1.63T USD"
    assert summary.quantitative.revenue == "97.88B USD"
    assert summary.quantitative.net_income == "3.86B USD"


def test_company_research_summary_builder_preserves_compact_usd_metric_suffixes():
    provider_evidence = ResearchEvidence(
        symbol="TSLA",
        document_id="doc-profile-compact-usd",
        chunk_id="chunk-profile-compact-usd",
        title="Tesla Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Tesla, Inc\n"
            "Currency: USD\n"
            "Market Cap: 1.66T USD\n"
            "Enterprise Value: 1.63T USD\n"
            "Total Revenue: 97.88B USD\n"
            "Net Income To Common: 3.86B USD\n"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="TSLA",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)

    assert summary.quantitative.market_cap == "1.66T USD"
    assert summary.quantitative.enterprise_value == "1.63T USD"
    assert summary.quantitative.revenue == "97.88B USD"
    assert summary.quantitative.net_income == "3.86B USD"


def test_company_research_summary_builder_maps_provider_camel_case_quantitative_fields():
    provider_evidence = ResearchEvidence(
        symbol="6758.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Sony Provider Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Sony Group Corporation\n"
            "Currency: JPY\n"
            "marketCap: 16,200,000,000,000\n"
            "enterpriseValue: 17,500,000,000,000\n"
            "totalRevenue: 12,000,000,000,000\n"
            "operatingIncome: 1,200,000,000,000\n"
            "netIncome: 970,000,000,000\n"
            "trailingEps: 156.3\n"
            "trailingPE: 18.4\n"
            "priceToBook: 2.1\n"
            "returnOnEquity: 0.124\n"
            "dividendYield: 0.012\n"
            "fullTimeEmployees: 113000\n"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="6758.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)

    assert summary.quantitative.market_cap == "16.2兆円"
    assert summary.quantitative.enterprise_value == "17.5兆円"
    assert summary.quantitative.revenue == "12兆円"
    assert summary.quantitative.operating_profit == "1.2兆円"
    assert summary.quantitative.net_income == "9,700億円"
    assert summary.quantitative.eps == "156.3円"
    assert summary.quantitative.per == "18.4倍"
    assert summary.quantitative.pbr == "2.1倍"
    assert summary.quantitative.roe == "12.4%"
    assert summary.quantitative.dividend_yield == "1.2%"
    assert summary.quantitative.employee_count == "113,000人"
    assert not {
        "時価総額",
        "企業価値",
        "売上高",
        "営業利益",
        "純利益",
        "EPS",
        "PER",
        "PBR",
        "ROE",
        "配当利回り",
        "従業員数",
    }.intersection(summary.quantitative.missing_items)


def test_company_research_summary_builder_prefers_context_metric_value_over_truncated_metric():
    provider_evidence = ResearchEvidence(
        symbol="6758.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Sony Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Sony Group Corporation Currency: JPY "
            "Market Cap: 20.25兆円 Enterprise Value: 20.24兆円 "
            "Total Revenue: 12.48兆円 Net Income To Common: 1.03兆円 "
            "Trailing EPS: 171.51円 Trailing PE: 19.99倍 "
            "Price To Book: 2.49倍 Return On Equity: 12.37% "
            "Dividend Yield: 1.01% Full Time Employees: 113,000 人"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="6758.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    brief = ResearchBrief(
        symbol="6758.T",
        as_of=date(2026, 5, 25),
        memo="Provider metrics.",
        metrics=[
            ResearchMetric(
                key="market_cap",
                label="時価総額",
                value="20",
                source_title="Sony Yahoo Finance Profile",
                source_type="provider_profile",
            ),
            ResearchMetric(
                key="per",
                label="PER",
                value="19",
                source_title="Sony Yahoo Finance Profile",
                source_type="provider_profile",
            ),
        ],
        missing_metrics=[],
        business_overview="Sony provider profile.",
    )

    summary = CompanyResearchSummaryBuilder().build(report, brief=brief)

    assert summary.quantitative.market_cap == "20.25兆円"
    assert summary.quantitative.per == "19.99倍"
    assert summary.quantitative.pbr == "2.49倍"
    assert summary.quantitative.roe == "12.37%"
    assert summary.quantitative.dividend_yield == "1.01%"
    assert summary.overview.scale_summary == (
        "確認できた規模情報は時価総額 20.25兆円、売上高 12.48兆円です。"
    )
    assert "時価総額 20です" not in summary.overview.scale_summary
    assert "時価総額" not in summary.quantitative.missing_items
    assert "PER" not in summary.quantitative.missing_items


def test_company_research_summary_builder_keeps_zero_metrics_and_ignores_empty_values():
    provider_evidence = ResearchEvidence(
        symbol="ZERO",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Zero Metrics Provider Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Zero Metrics Inc.\n"
            "Market Cap: 0 JPY\n"
            "Enterprise Value: NaN\n"
            "Total Revenue: \n"
            "Operating Income: None\n"
            "Net Income: null\n"
            "Trailing EPS: 0\n"
            "Trailing PE: 0\n"
            "Price To Book: 0\n"
            "Return On Equity: 0\n"
            "Dividend Yield: 0\n"
            "Full Time Employees: 0\n"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="ZERO",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)

    assert summary.quantitative.market_cap == "0円"
    assert summary.quantitative.eps == "0"
    assert summary.quantitative.per == "0倍"
    assert summary.quantitative.pbr == "0倍"
    assert summary.quantitative.roe == "0%"
    assert summary.quantitative.dividend_yield == "0%"
    assert summary.quantitative.employee_count == "0人"
    assert "時価総額" not in summary.quantitative.missing_items
    assert "PER" not in summary.quantitative.missing_items
    assert "PBR" not in summary.quantitative.missing_items
    assert "ROE" not in summary.quantitative.missing_items
    assert "配当利回り" not in summary.quantitative.missing_items
    assert "従業員数" not in summary.quantitative.missing_items
    assert "売上高" in summary.quantitative.missing_items
    assert "企業価値" in summary.quantitative.missing_items


def test_company_research_summary_builder_normalizes_business_profile_without_news_mix():
    provider_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Toyota Motor Corporation\n"
            "Sector: Consumer Cyclical\n"
            "Industry: Auto Manufacturers\n"
            "Toyota manufactures automobiles, commercial vehicles, and vehicle parts. "
            "It provides maintenance, leasing, financial services, and mobility services globally. "
            "It serves dealers, fleet customers, and consumers in Japan, North America, Europe, "
            "and Asia. Employees: 380,000"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )
    news_report = StockNewsReport(
        symbol="7203.T",
        company_name="Toyota Motor Corporation",
        as_of=date(2026, 5, 25),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                title="Toyota launches battery product",
                url="https://example.com/toyota-battery",
                source="Example News",
                published_at=date(2026, 5, 24),
                summary="Toyota launched a battery product.",
                investment_viewpoint="growth",
                sentiment_for_investment="positive",
                freshness_status="latest",
            )
        ],
    )

    summary = CompanyResearchSummaryBuilder().build(report, news_report=news_report)
    profile = summary.overview.business_profile

    assert profile is not None
    assert profile.company_name == "Toyota Motor Corporation"
    assert profile.sector == "Consumer Cyclical"
    assert profile.industry == "Auto Manufacturers"
    assert profile.information_status == "found"
    assert "自動車事業" in profile.main_businesses
    assert "金融サービス" in profile.supporting_businesses
    assert "リース" in profile.supporting_businesses
    assert profile.main_businesses != profile.products_services
    assert "自動車" in profile.products_services
    assert "商用車" in profile.products_services
    assert "車両" in profile.products_services
    assert "部品" in profile.products_services
    assert "保守・整備" in profile.products_services
    assert "リース" in profile.products_services
    assert "モビリティサービス" in profile.products_services
    assert "日本" in profile.regions
    assert "北米" in profile.regions
    assert "フリート顧客" in profile.customer_segments
    assert summary.quantitative.employee_count == "380,000人"
    assert "Toyota launches battery product" not in profile.business_summary
    assert profile.business_summary.startswith("外部プロフィールから、Toyota Motor Corporationは")
    assert "事業別売上や利益構成" in profile.business_summary


def test_company_research_summary_builder_prioritizes_semiconductor_business_context():
    provider_evidence = ResearchEvidence(
        symbol="NVDA",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="NVIDIA Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: NVIDIA Corporation\n"
            "Sector: Technology\n"
            "Industry: Semiconductors\n"
            "Business Summary: NVIDIA operates as a data center scale AI infrastructure "
            "company. It provides GPUs, accelerated computing platforms, networking "
            "products, gaming graphics, and automotive platforms worldwide."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="NVDA",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    profile = summary.overview.business_profile

    assert profile is not None
    assert "半導体・GPU" in profile.main_businesses
    assert "AI・データセンター" in profile.main_businesses
    assert "自動車事業" not in profile.main_businesses
    assert "モビリティ事業" not in profile.main_businesses
    assert "GPU" in profile.products_services
    assert "AIインフラ" in profile.products_services
    assert "半導体・GPU" in summary.overview.business_overview


def test_company_research_summary_builder_prioritizes_software_cloud_over_retail_noise():
    provider_evidence = ResearchEvidence(
        symbol="MSFT",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Microsoft Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Microsoft Corporation\n"
            "Sector: Technology\n"
            "Industry: Software - Infrastructure\n"
            "Business Summary: Microsoft develops software, cloud platforms, Azure, "
            "productivity services, devices, and retail customer solutions worldwide."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="MSFT",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    profile = summary.overview.business_profile

    assert profile is not None
    assert "ソフトウェア・クラウド" in profile.main_businesses
    assert "小売・EC" not in profile.main_businesses
    assert "ソフトウェアサービス" in profile.products_services
    assert "ソフトウェア・クラウド" in summary.overview.business_overview


def test_company_research_summary_builder_prioritizes_financial_sector_over_software_noise():
    provider_evidence = ResearchEvidence(
        symbol="JPM",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="JPMorgan Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: JPMorgan Chase & Co.\n"
            "Sector: Financial Services\n"
            "Industry: Banks - Diversified\n"
            "Business Summary: JPMorgan provides investment banking, commercial banking, "
            "asset management, credit, loan, payment, and digital platform services."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="JPM",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    profile = summary.overview.business_profile

    assert profile is not None
    assert "銀行・金融サービス" in profile.main_businesses
    assert "決済ネットワーク" not in profile.main_businesses
    assert "ソフトウェア・クラウド" not in profile.main_businesses
    assert "銀行サービス" in profile.products_services
    assert "融資・クレジット" in profile.products_services


def test_company_research_summary_builder_weights_auto_retail_and_payment_contexts():
    tesla_evidence = ResearchEvidence(
        symbol="TSLA",
        document_id="doc-tesla",
        chunk_id="chunk-tesla",
        title="Tesla Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Tesla, Inc\n"
            "Sector: Consumer Cyclical\n"
            "Industry: Auto Manufacturers\n"
            "Business Summary: Tesla designs electric vehicles, energy generation "
            "and storage systems, charging services, vehicle software, leasing, "
            "insurance, and financing services."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    retail_evidence = ResearchEvidence(
        symbol="9983.T",
        document_id="doc-retail",
        chunk_id="chunk-retail",
        title="Fast Retailing Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Fast Retailing Co., Ltd\n"
            "Sector: Consumer Cyclical\n"
            "Industry: Apparel Retail\n"
            "Business Summary: Fast Retailing operates apparel brands, clothing "
            "retail stores, e-commerce, online sales, and global brand operations."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    payment_evidence = ResearchEvidence(
        symbol="V",
        document_id="doc-visa",
        chunk_id="chunk-visa",
        title="Visa Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Visa Inc\n"
            "Sector: Financial Services\n"
            "Industry: Credit Services\n"
            "Business Summary: Visa operates a global card network for payments, "
            "digital payment transactions, merchant services, settlement, fraud detection, "
            "and marketing services for clients."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )

    tesla = CompanyResearchSummaryBuilder().build(
        CompanyResearchReport(
            symbol="TSLA",
            as_of=date(2026, 5, 25),
            summary="Research summary.",
            points=[],
            evidence=[tesla_evidence],
            data_quality=ResearchDataQuality(
                status="OK",
                latest_document_date=date(2026, 5, 24),
                document_count=1,
                evidence_count=1,
                warnings=[],
            ),
        )
    )
    retail = CompanyResearchSummaryBuilder().build(
        CompanyResearchReport(
            symbol="9983.T",
            as_of=date(2026, 5, 25),
            summary="Research summary.",
            points=[],
            evidence=[retail_evidence],
            data_quality=ResearchDataQuality(
                status="OK",
                latest_document_date=date(2026, 5, 24),
                document_count=1,
                evidence_count=1,
                warnings=[],
            ),
        )
    )
    payment = CompanyResearchSummaryBuilder().build(
        CompanyResearchReport(
            symbol="V",
            as_of=date(2026, 5, 25),
            summary="Research summary.",
            points=[],
            evidence=[payment_evidence],
            data_quality=ResearchDataQuality(
                status="OK",
                latest_document_date=date(2026, 5, 24),
                document_count=1,
                evidence_count=1,
                warnings=[],
            ),
        )
    )

    tesla_profile = tesla.overview.business_profile
    retail_profile = retail.overview.business_profile
    payment_profile = payment.overview.business_profile

    assert tesla_profile is not None
    assert "自動車事業" in tesla_profile.main_businesses
    assert "銀行・金融サービス" not in tesla_profile.main_businesses
    assert "リース" in tesla_profile.supporting_businesses
    assert "保険" in tesla_profile.supporting_businesses
    assert "電気自動車" in tesla_profile.products_services
    assert "蓄電池" in tesla_profile.products_services
    assert "リース" not in tesla_profile.products_services
    assert "保険" not in tesla_profile.products_services

    assert retail_profile is not None
    assert "アパレル小売" in retail_profile.main_businesses
    assert "小売・EC" in retail_profile.main_businesses
    assert "ソフトウェア・クラウド" not in retail_profile.main_businesses
    assert "金融サービス" not in retail_profile.supporting_businesses
    assert "衣料品" in retail_profile.products_services
    assert "店舗販売" in retail_profile.products_services
    assert "オンライン販売" in retail_profile.products_services

    assert payment_profile is not None
    assert "決済ネットワーク" in payment_profile.main_businesses
    assert "銀行・金融サービス" not in payment_profile.main_businesses
    assert "広告・マーケティング" not in payment_profile.main_businesses
    assert "ソフトウェア" not in payment_profile.supporting_businesses
    assert "カード決済" in payment_profile.products_services
    assert "デジタル決済" in payment_profile.products_services
    assert "加盟店サービス" in payment_profile.products_services
    assert "広告サービス" not in payment_profile.products_services


def test_company_research_summary_builder_avoids_telecom_noise_and_maps_amazon_style_mix():
    nintendo_evidence = ResearchEvidence(
        symbol="7974.T",
        document_id="doc-nintendo",
        chunk_id="chunk-nintendo",
        title="Nintendo Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Nintendo Co., Ltd\n"
            "Sector: Communication Services\n"
            "Industry: Electronic Gaming & Multimedia\n"
            "Business Summary: Nintendo develops video game platforms, game software, "
            "entertainment content, consoles, and network services."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    amazon_evidence = ResearchEvidence(
        symbol="AMZN",
        document_id="doc-amazon",
        chunk_id="chunk-amazon",
        title="Amazon Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Amazon.com, Inc\n"
            "Sector: Consumer Cyclical\n"
            "Industry: Internet Retail\n"
            "Business Summary: Amazon operates an e-commerce marketplace, online stores, "
            "AWS cloud computing services, advertising services, subscription services, "
            "devices, logistics, and digital content."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )

    nintendo = CompanyResearchSummaryBuilder().build(
        CompanyResearchReport(
            symbol="7974.T",
            as_of=date(2026, 5, 25),
            summary="Research summary.",
            points=[],
            evidence=[nintendo_evidence],
            data_quality=ResearchDataQuality(
                status="OK",
                latest_document_date=date(2026, 5, 24),
                document_count=1,
                evidence_count=1,
                warnings=[],
            ),
        )
    )
    amazon = CompanyResearchSummaryBuilder().build(
        CompanyResearchReport(
            symbol="AMZN",
            as_of=date(2026, 5, 25),
            summary="Research summary.",
            points=[],
            evidence=[amazon_evidence],
            data_quality=ResearchDataQuality(
                status="OK",
                latest_document_date=date(2026, 5, 24),
                document_count=1,
                evidence_count=1,
                warnings=[],
            ),
        )
    )

    nintendo_profile = nintendo.overview.business_profile
    amazon_profile = amazon.overview.business_profile

    assert nintendo_profile is not None
    assert "ゲーム・エンタメ" in nintendo_profile.main_businesses
    assert "通信サービス" not in nintendo_profile.main_businesses
    assert "ゲーム" in nintendo_profile.products_services

    assert amazon_profile is not None
    assert amazon_profile.main_businesses[:3] == [
        "小売・EC",
        "ソフトウェア・クラウド",
        "広告・マーケティング",
    ]
    assert "クラウドサービス" in amazon_profile.products_services
    assert "広告サービス" in amazon_profile.products_services
    assert "マーケットプレイスサービス" in amazon_profile.products_services


def test_company_research_summary_builder_avoids_payment_noise_for_trading_company():
    provider_evidence = ResearchEvidence(
        symbol="8058.T",
        document_id="doc-trading",
        chunk_id="chunk-trading",
        title="Mitsubishi Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Mitsubishi Corporation\n"
            "Sector: Industrials\n"
            "Industry: Conglomerates\n"
            "Business Summary: Mitsubishi operates natural gas, industrial materials, "
            "petroleum and chemicals solution, mineral resources, industrial infrastructure, "
            "automotive and mobility, food industry, consumer industry, power solution, "
            "urban development, logistics, infrastructure, "
            "and transaction-related services."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="8058.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    profile = summary.overview.business_profile

    assert profile is not None
    assert "総合商社・事業投資" in profile.main_businesses
    assert "ガス・エネルギーインフラ" not in profile.main_businesses
    assert "電力・エネルギー供給" not in profile.main_businesses
    assert "決済ネットワーク" not in profile.main_businesses
    assert "決済ネットワーク" not in profile.products_services
    assert "都市ガス" not in profile.products_services
    assert "電力" not in profile.products_services


def test_company_research_summary_builder_keeps_consumer_electronics_finance_related():
    provider_evidence = ResearchEvidence(
        symbol="6758.T",
        document_id="doc-sony",
        chunk_id="chunk-sony",
        title="Sony Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 6, 1),
        section_title="Profile",
        excerpt=(
            "Company Name: Sony Group Corporation\n"
            "Sector: Technology\n"
            "Industry: Consumer Electronics\n"
            "Business Summary: Sony operates electronics, game, music, pictures, "
            "imaging products, financial services, banking, leasing, and insurance businesses."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="6758.T",
        as_of=date(2026, 6, 1),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 6, 1),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    profile = summary.overview.business_profile

    assert profile is not None
    assert "エレクトロニクス" in profile.main_businesses
    assert "ゲーム・エンタメ" in profile.main_businesses
    assert "銀行・金融サービス" not in profile.main_businesses
    assert "金融サービス" not in profile.main_businesses
    assert "銀行サービス" not in profile.products_services
    assert "リース" not in profile.products_services
    assert "保険" not in profile.products_services


def test_company_research_summary_builder_handles_industrial_conglomerate_railroad_and_heavy_machinery():
    hitachi_evidence = ResearchEvidence(
        symbol="6501.T",
        document_id="doc-hitachi",
        chunk_id="chunk-hitachi",
        title="Hitachi Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 6, 1),
        section_title="Profile",
        excerpt=(
            "Company Name: Hitachi, Ltd.\n"
            "Sector: Industrials\n"
            "Industry: Conglomerates\n"
            "Business Summary: Hitachi operates Digital Systems and Services, "
            "Green Energy and Mobility, and Connective Industries, including "
            "power grids, industrial systems, IT services, and healthcare systems."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    railroad_evidence = ResearchEvidence(
        symbol="9020.T",
        document_id="doc-railroad",
        chunk_id="chunk-railroad",
        title="JR East Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 6, 1),
        section_title="Profile",
        excerpt=(
            "Company Name: East Japan Railway Company\n"
            "Sector: Industrials\n"
            "Industry: Railroads\n"
            "Business Summary: JR East operates passenger railway, rail stations, "
            "transportation infrastructure, real estate, retail stores, and station services."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    machinery_evidence = ResearchEvidence(
        symbol="CAT",
        document_id="doc-cat",
        chunk_id="chunk-cat",
        title="Caterpillar Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 6, 1),
        section_title="Profile",
        excerpt=(
            "Company Name: Caterpillar Inc.\n"
            "Sector: Industrials\n"
            "Industry: Farm & Heavy Construction Machinery\n"
            "Business Summary: Caterpillar manufactures construction machinery, "
            "heavy equipment, engines, turbines, parts, and maintenance services "
            "for mining, energy, and construction customers."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )

    def build_profile(symbol: str, evidence: ResearchEvidence) -> CompanyBusinessProfile:
        summary = CompanyResearchSummaryBuilder().build(
            CompanyResearchReport(
                symbol=symbol,
                as_of=date(2026, 6, 1),
                summary="Research summary.",
                points=[],
                evidence=[evidence],
                data_quality=ResearchDataQuality(
                    status="OK",
                    latest_document_date=date(2026, 6, 1),
                    document_count=1,
                    evidence_count=1,
                    warnings=[],
                ),
            )
        )
        profile = summary.overview.business_profile
        assert profile is not None
        return profile

    hitachi_profile = build_profile("6501.T", hitachi_evidence)
    railroad_profile = build_profile("9020.T", railroad_evidence)
    machinery_profile = build_profile("CAT", machinery_evidence)

    assert hitachi_profile.main_businesses == ["産業インフラ・デジタル"]
    assert "医薬品・ヘルスケア" not in hitachi_profile.main_businesses
    assert "自動車・モビリティ" not in hitachi_profile.main_businesses
    assert "材料・化学" not in hitachi_profile.supporting_businesses
    assert "デジタルシステム" in hitachi_profile.products_services
    assert "産業インフラ" in hitachi_profile.products_services

    assert railroad_profile.main_businesses == ["鉄道・交通インフラ"]
    assert "広告・マーケティング" not in railroad_profile.main_businesses
    assert "小売・EC" not in railroad_profile.main_businesses
    assert "医薬品" not in railroad_profile.products_services
    assert "鉄道サービス" in railroad_profile.products_services
    assert "交通インフラ" in railroad_profile.products_services

    assert machinery_profile.main_businesses == ["産業機械・建設機械"]
    assert "エレクトロニクス" not in machinery_profile.main_businesses
    assert "ソフトウェア・クラウド" not in machinery_profile.main_businesses
    assert "建設機械" in machinery_profile.products_services
    assert "産業機械" in machinery_profile.products_services
    assert "エンジン" in machinery_profile.products_services


def test_company_research_summary_builder_prioritizes_healthcare_and_energy_sectors():
    healthcare_evidence = ResearchEvidence(
        symbol="4502.T",
        document_id="doc-healthcare",
        chunk_id="chunk-healthcare",
        title="Takeda Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Takeda Pharmaceutical Company Limited\n"
            "Sector: Healthcare\n"
            "Industry: Drug Manufacturers - Specialty & Generic\n"
            "Business Summary: Takeda researches pharmaceutical medicine, therapy, "
            "biotech, diagnostics, and healthcare products. Financial information is "
            "available from company filings."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    energy_evidence = ResearchEvidence(
        symbol="XOM",
        document_id="doc-energy",
        chunk_id="chunk-energy",
        title="Exxon Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Exxon Mobil Corporation\n"
            "Sector: Energy\n"
            "Industry: Oil & Gas Integrated\n"
            "Business Summary: Exxon explores, produces, refines, and sells oil and gas "
            "products. The company also uses data platforms in operations."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )

    healthcare = CompanyResearchSummaryBuilder().build(
        CompanyResearchReport(
            symbol="4502.T",
            as_of=date(2026, 5, 25),
            summary="Research summary.",
            points=[],
            evidence=[healthcare_evidence],
            data_quality=ResearchDataQuality(
                status="OK",
                latest_document_date=date(2026, 5, 24),
                document_count=1,
                evidence_count=1,
                warnings=[],
            ),
        )
    )
    energy = CompanyResearchSummaryBuilder().build(
        CompanyResearchReport(
            symbol="XOM",
            as_of=date(2026, 5, 25),
            summary="Research summary.",
            points=[],
            evidence=[energy_evidence],
            data_quality=ResearchDataQuality(
                status="OK",
                latest_document_date=date(2026, 5, 24),
                document_count=1,
                evidence_count=1,
                warnings=[],
            ),
        )
    )

    healthcare_profile = healthcare.overview.business_profile
    energy_profile = energy.overview.business_profile

    assert healthcare_profile is not None
    assert "医薬品・ヘルスケア" in healthcare_profile.main_businesses
    assert "アパレル小売" not in healthcare_profile.main_businesses
    assert "金融サービス" not in healthcare_profile.supporting_businesses
    assert "金融商品" not in healthcare_profile.products_services
    assert "ブランド運営" not in healthcare_profile.products_services
    assert "医薬品" in healthcare_profile.products_services
    assert energy_profile is not None
    assert "エネルギー" in energy_profile.main_businesses
    assert "AI・データセンター" not in energy_profile.main_businesses
    assert "データセンター向け製品" not in energy_profile.products_services
    assert "石油・ガス" in energy_profile.products_services


def test_company_research_summary_builder_prioritizes_gas_utility_context():
    provider_evidence = ResearchEvidence(
        symbol="9532.T",
        document_id="doc-osaka-gas",
        chunk_id="chunk-osaka-gas",
        title="Osaka Gas Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 6, 1),
        section_title="Profile",
        excerpt=(
            "Company Name: Osaka Gas Co., Ltd\n"
            "Sector: Utilities\n"
            "Industry: Utilities - Regulated Gas\n"
            "Business Summary: Osaka Gas produces, supplies, and sells city gas, "
            "electricity, LNG, LPG, energy services, and gas appliances. "
            "It operates Domestic Energy, International Energy, and Life & Business "
            "Solutions segments, including real estate, software and information "
            "solutions, fine materials, carbon material products, and maintenance services."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="9532.T",
        as_of=date(2026, 6, 1),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 6, 1),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    profile = summary.overview.business_profile

    assert profile is not None
    assert "ガス・エネルギーインフラ" in profile.main_businesses
    assert "電力・エネルギー供給" in profile.main_businesses
    assert "ソフトウェア・クラウド" not in profile.main_businesses
    assert "小売・EC" not in profile.main_businesses
    assert "金融サービス" not in profile.main_businesses
    assert "海外エネルギー" in profile.supporting_businesses
    assert "ライフサービス" in profile.supporting_businesses
    assert "不動産" in profile.supporting_businesses
    assert "情報ソリューション" in profile.supporting_businesses
    assert "材料・化学" in profile.supporting_businesses
    assert "ソフトウェア" not in profile.supporting_businesses
    assert "部品・アフターサービス" not in profile.supporting_businesses
    assert "都市ガス" in profile.products_services
    assert "電力" in profile.products_services
    assert "LNG" in profile.products_services
    assert "LPG" in profile.products_services
    assert "エネルギーサービス" in profile.products_services
    assert "ガス機器" in profile.products_services
    assert "生活関連サービス" in profile.products_services
    assert "ソフトウェアサービス" not in profile.products_services
    assert "保守・整備" not in profile.products_services
    assert "ソフトウェア・クラウド" not in summary.overview.business_overview


def test_company_research_summary_builder_adds_safe_product_candidates_when_missing():
    provider_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Toyota Motor Corporation\n"
            "Sector: Consumer Cyclical\n"
            "Industry: Auto Manufacturers\n"
            "Toyota has global operations."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    profile = summary.overview.business_profile

    assert profile is not None
    assert profile.products_services_status == "unverified"
    assert "自動車（補完候補）" in profile.products_services
    assert all("補完候補" in item for item in profile.products_services)
    assert summary.overview.products_services_status == "unverified"


def test_company_research_summary_builder_hides_provider_raw_labels_from_overview():
    provider_evidence = ResearchEvidence(
        symbol="ACME",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Provider Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Acme Corporation Provider Symbol: ACME Quote Type: EQUITY "
            "Sector: Technology Industry: Software - Application Country: Japan "
            "Website: https://example.com Business Summary: Acme provides cloud platform services."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="ACME",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    assert summary.overview.business_overview
    visible_text = " ".join(
        [
            summary.overview.company_name,
            summary.overview.business_overview,
            summary.overview.industry or "",
            summary.overview.sector or "",
        ]
    )
    assert "Provider Symbol" not in visible_text
    assert "Quote Type" not in visible_text
    assert "Website:" not in visible_text
    assert "https://example.com" not in summary.overview.business_overview
    assert "Technology Industry" not in summary.overview.business_overview


def test_company_research_summary_builder_leads_with_understood_business_context():
    provider_evidence = ResearchEvidence(
        symbol="6758.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Sony Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Sony Group Corporation\n"
            "Sector: Technology\n"
            "Industry: Consumer Electronics\n"
            "Business Summary: Sony operates game, music, movie, semiconductor, "
            "consumer electronics, and financial services businesses globally."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="6758.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)

    assert summary.overview.company_name == "Sony Group Corporation"
    assert summary.overview.business_overview.startswith(
        "外部プロフィールから、Sony Group Corporationは"
    )
    assert "ゲーム・エンタメ" in summary.overview.business_overview
    assert "金融サービス" in summary.overview.business_overview
    assert "ただし、事業別売上や利益構成" in summary.overview.business_overview
    assert "Business Summary" not in summary.overview.business_overview
    assert "Provider Symbol" not in summary.overview.business_overview


def test_company_research_summary_builder_distinguishes_ir_statuses_and_types():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=[],
        ),
    )
    external_result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="fake_tdnet",
        fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="2026年3月期 業績予想修正に関するお知らせ",
                symbol="7203.T",
                source_type="tdnet",
                source_url="https://example.com/tdnet/forecast",
                provider="tdnet",
                published_at=date(2026, 5, 20),
                fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
                freshness_status="latest",
                document_id="external-forecast",
                content_summary="",
            ),
            ExternalResearchFetchManifestEntry(
                title="配当予想の修正および自己株式取得に関するお知らせ",
                symbol="7203.T",
                source_type="tdnet",
                source_url="https://example.com/tdnet/shareholder-return",
                provider="tdnet",
                published_at=date(2026, 5, 21),
                fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
                freshness_status="latest",
                document_id="external-return",
                content_summary="",
            ),
            ExternalResearchFetchManifestEntry(
                title="定款一部変更に関するお知らせ",
                symbol="7203.T",
                source_type="tdnet",
                source_url="https://example.com/tdnet/articles",
                provider="tdnet",
                published_at=date(2026, 5, 22),
                fetched_at=datetime(2026, 5, 25, tzinfo=UTC),
                freshness_status="latest",
                document_id="external-articles",
                content_summary="",
            ),
        ],
    )

    summary = CompanyResearchSummaryBuilder().build(
        report,
        external_research_result=external_result,
    )
    ir_by_type = {item.ir_document_type: item for item in summary.ir_items}

    assert ir_by_type["forecast_revision"].availability == "found"
    assert ir_by_type["forecast_revision"].information_status == "found"
    assert ir_by_type["forecast_revision"].status == "found"
    assert ir_by_type["forecast_revision"].source_url == "https://example.com/tdnet/forecast"
    assert "関連しそうな資料候補" in ir_by_type["forecast_revision"].summary
    assert ir_by_type["forecast_revision"].matched_keywords
    assert ir_by_type["forecast_revision"].classification_reason == (
        "specific_required_keyword_match"
    )
    assert ir_by_type["shareholder_return"].availability == "found"
    assert ir_by_type["shareholder_return"].information_status == "found"
    assert ir_by_type["earnings_summary"].information_status == "missing"
    assert any(item.information_status == "missing" for item in summary.ir_items)
    assert summary.news_items
    assert any(
        item.title == "2026年3月期 業績予想修正に関するお知らせ"
        and item.topic_type == "forecast_revision"
        and "公式開示として取得済み" in item.summary
        and "会社発表ベースの開示資料" in item.summary
        and "企業理解上の意味" in item.summary
        and "本文未解析" in item.summary
        and item.impact_hint == "financial"
        and item.official_confirmation_required is False
        and item.information_status == "unparsed"
        and item.status == "unparsed"
        for item in summary.news_items
    )
    forecast_topics = [
        item
        for item in summary.news_items
        if item.title == "2026年3月期 業績予想修正に関するお知らせ"
    ]
    assert len(forecast_topics) == 1
    assert "適時開示「2026年3月期 業績予想修正に関するお知らせ」を確認しました" not in (
        forecast_topics[0].summary
    )
    assert any(
        item.title == "定款一部変更に関するお知らせ"
        and item.topic_type == "tdnet"
        and item.impact_hint == "ir"
        and item.official_confirmation_required is False
        for item in summary.news_items
    )


def test_company_research_summary_builder_keeps_rsu_tdnet_out_of_return_and_forecast_ir():
    report = CompanyResearchReport(
        symbol="6856.T",
        as_of=date(2026, 6, 18),
        summary="Research summary.",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=[],
        ),
    )
    external_result = ExternalResearchFetchResult(
        symbol="6856.T",
        provider="fake_tdnet",
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title=(
                    "リストリクテッド・ストック・ユニット（RSU）付与制度としての"
                    "自己株式処分の払込完了に関するお知らせ"
                ),
                symbol="6856.T",
                source_type="tdnet",
                source_url="https://example.com/tdnet/rsu",
                provider="tdnet",
                published_at=date(2026, 6, 15),
                fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
                freshness_status="latest",
                document_id="external-rsu",
                content_summary="",
            )
        ],
    )

    summary = CompanyResearchSummaryBuilder().build(
        report,
        external_research_result=external_result,
    )
    ir_by_type = {item.ir_document_type: item for item in summary.ir_items}

    assert ir_by_type["timely_disclosure"].availability == "found"
    assert ir_by_type["timely_disclosure"].source_url == "https://example.com/tdnet/rsu"
    assert ir_by_type["timely_disclosure"].classification_reason in {
        "tdnet_generic_disclosure",
        "optional_keyword_match",
    }
    assert ir_by_type["shareholder_return"].availability == "missing"
    assert ir_by_type["forecast_revision"].availability == "missing"


def test_company_research_summary_builder_does_not_treat_provider_profile_as_ir_document():
    provider_evidence = ResearchEvidence(
        symbol="9532.T",
        document_id="doc-provider-only",
        chunk_id="chunk-provider-only",
        title="Osaka Gas Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 6, 1),
        section_title="Profile",
        excerpt=(
            "Company Name: Osaka Gas Co., Ltd Provider Symbol: 9532.T Quote Type: EQUITY "
            "Sector: Utilities Industry: Utilities - Regulated Gas "
            "Trailing Annual Dividend Yield: 2.4% "
            "Data Quality Notes: Confirm important facts against official IR, annual report, "
            "or regulatory filings."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="9532.T",
        as_of=date(2026, 6, 1),
        summary="Provider only.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 6, 1),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = CompanyResearchSummaryBuilder().build(report)
    ir_by_type = {item.ir_document_type: item for item in summary.ir_items}

    assert ir_by_type["annual_report"].availability == "missing"
    assert ir_by_type["shareholder_return"].availability == "missing"


def test_company_research_summary_builder_shapes_news_topic_confirmation_text():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Research summary.",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=[],
        ),
    )
    news_report = StockNewsReport(
        symbol="7203.T",
        company_name="Toyota Motor Corporation",
        as_of=date(2026, 5, 25),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                title="Toyota expands software services",
                url="https://example.com/news",
                source="Example News",
                published_at=date(2026, 5, 24),
                summary="Software services expanded in overseas markets.",
                investment_viewpoint="growth",
                sentiment_for_investment="positive",
                freshness_status="latest",
            )
        ],
    )

    summary = CompanyResearchSummaryBuilder().build(report, news_report=news_report)

    assert summary.news_items[0].topic_type == "product"
    assert summary.news_items[0].official_confirmation_required is True
    assert "外部ニュースとして取得" in summary.news_items[0].summary
    assert "企業理解上の意味" in summary.news_items[0].summary
    assert "公式IRで確認が必要" in summary.news_items[0].summary


def test_research_brief_builder_marks_missing_metrics_as_confirmation_gaps():
    report = CompanyResearchReport(
        symbol="MSFT",
        as_of=date(2026, 5, 25),
        summary="登録資料が限られます。",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=["登録済みResearch資料がありません。"],
        ),
    )

    brief = ResearchBriefBuilder().build(report)

    assert brief.metrics == []
    assert "売上高" in brief.missing_metrics
    assert any("未確認の定量指標" in gap for gap in brief.confirmation_gaps)
    assert any("公式資料" in action for action in brief.next_actions)
    assert "未確認メモ" in brief.memo
    assert "not advice" in brief.decision_support_note
    assert brief.fact_summary is not None
    assert any(
        item.category == "financial_metric" and "売上高" in item.reason
        for item in brief.fact_summary.missing_items
    )
    assert any(item.category == "official_source" for item in brief.fact_summary.missing_items)


def test_investment_insight_builder_keeps_provider_profile_neutral_and_marks_gaps():
    provider_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Toyota sells vehicles globally and invests in growth areas. "
            "Provider Symbol: 7203.T Quote Type: EQUITY"
        ),
        relevance_score=Decimal("0.70"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Provider profile only.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    insight = InvestmentInsightBuilder().build(report)

    assert insight.schema_version == "investment-insight-v1"
    assert insight.positive_points == []
    assert insight.negative_points == []
    assert insight.neutral_points
    assert insight.neutral_points[0].source_type == "provider_profile"
    assert insight.confidence != "high"
    assert insight.status_label == "公式資料確認待ち"
    assert insight.confidence_label == "低"
    assert insight.primary_action_label == "決算資料を確認"
    assert any("売上高が未確認" in gap for gap in insight.confirmation_gaps)
    assert any("PER/PBR/ROEが未確認" in gap for gap in insight.confirmation_gaps)
    assert any("公式資料" in gap for gap in insight.confirmation_gaps)
    assert "check_official_materials" in insight.action_hints


def test_investment_insight_builder_keeps_news_only_confidence_below_high():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="No official evidence.",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=["登録済みResearch資料がありません。"],
        ),
    )
    news_report = StockNewsReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        news=[
            StockNewsEvidence(
                symbol="7203.T",
                title="Toyota raises guidance",
                url="https://example.com/toyota-guidance",
                source="Example News",
                published_at=date(2026, 5, 24),
                summary="Guidance was raised after revenue growth.",
                investment_viewpoint="growth",
                sentiment_for_investment="positive",
                freshness_status="latest",
            )
        ],
    )

    insight = InvestmentInsightBuilder().build(report, news_report=news_report)

    assert insight.confidence != "high"
    assert insight.status_label == "ニュース先行"
    assert insight.confidence_label == "低"
    assert insight.primary_action_label == "公式IRで裏取り"
    assert any(point.source_type == "news" for point in insight.positive_points)
    assert any("公式IR" in gap for gap in insight.confirmation_gaps)
    assert "wait_for_confirmation" in insight.action_hints
    assert "insufficient_evidence" in insight.action_hints


def test_investment_insight_builder_marks_empty_research_as_insufficient():
    report = CompanyResearchReport(
        symbol="MSFT",
        as_of=date(2026, 5, 25),
        summary="No source-backed evidence.",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=["登録済みResearch資料がありません。"],
        ),
    )

    insight = InvestmentInsightBuilder().build(report)

    assert insight.status_label == "判断材料不足"
    assert insight.confidence_label == "低"
    assert insight.primary_action_label == "資料追加が必要"
    assert insight.primary_action_label
    assert "insufficient_evidence" in insight.action_hints


def test_investment_insight_builder_classifies_positive_negative_and_avoids_advice_terms():
    positive_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-ir",
        chunk_id="chunk-ir",
        title="7203 決算短信",
        source_type="earnings_report",
        published_at=date(2026, 5, 20),
        section_title="業績",
        excerpt=(
            "売上高 45兆円、営業利益 5兆円、純利益 4兆円、EPS 320円、"
            "PER 12倍、PBR 1.1倍、ROE 9.8%、配当 75円。"
            "上方修正と増配、成長セグメントの拡大を発表しました。"
        ),
        relevance_score=Decimal("0.90"),
        reliability=Decimal("0.95"),
    )
    negative_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-risk",
        chunk_id="chunk-risk",
        title="TDnet リスク開示",
        source_type="tdnet",
        published_at=date(2026, 5, 21),
        section_title="注意点",
        excerpt="一部地域で減益、コスト増、為替リスクが注意点として説明されています。",
        relevance_score=Decimal("0.86"),
        reliability=Decimal("0.92"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Official evidence exists.",
        points=[],
        evidence=[positive_evidence, negative_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 21),
            document_count=2,
            evidence_count=2,
            warnings=[],
        ),
    )

    insight = InvestmentInsightBuilder().build(report)

    positive_text = " ".join(point.summary for point in insight.positive_points)
    negative_text = " ".join(point.summary for point in insight.negative_points)
    dumped = str(insight.model_dump(mode="json"))

    assert "上方修正" in positive_text or "増配" in positive_text
    assert "減益" in negative_text or "コスト増" in negative_text
    assert insight.status_label == "材料混在"
    assert insight.confidence_label == "中"
    assert insight.primary_action_label == "良悪材料を比較"
    assert "review" in insight.action_hints
    assert not any(term in dumped for term in FORBIDDEN_RECOMMENDATION_WORDS)
    assert not any(term in insight.short_summary for term in FORBIDDEN_RECOMMENDATION_WORDS)
    assert len(insight.short_summary.split("。")) <= 4


def test_investment_insight_builder_marks_metric_shortage_and_limits_initial_points():
    evidence_rows = [
        ResearchEvidence(
            symbol="7203.T",
            document_id=f"doc-positive-{index}",
            chunk_id=f"chunk-positive-{index}",
            title=f"7203 決算短信 positive {index}",
            source_type="earnings_report",
            published_at=date(2026, 5, 20),
            section_title="良材料",
            excerpt=f"成長戦略と上方修正、増配に関する材料 {index} を確認しました。",
            relevance_score=Decimal("0.82"),
            reliability=Decimal("0.90"),
        )
        for index in range(4)
    ]
    evidence_rows.extend(
        ResearchEvidence(
            symbol="7203.T",
            document_id=f"doc-risk-{index}",
            chunk_id=f"chunk-risk-{index}",
            title=f"TDnet risk {index}",
            source_type="tdnet",
            published_at=date(2026, 5, 21),
            section_title="注意点",
            excerpt=f"為替リスクとコスト増に関する注意材料 {index} を確認しました。",
            relevance_score=Decimal("0.80"),
            reliability=Decimal("0.88"),
        )
        for index in range(4)
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Official evidence exists with missing metrics.",
        points=[],
        evidence=evidence_rows,
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 21),
            document_count=len(evidence_rows),
            evidence_count=len(evidence_rows),
            warnings=[],
        ),
    )

    insight = InvestmentInsightBuilder().build(report)

    assert insight.status_label == "材料混在"
    assert insight.primary_action_label
    assert len(insight.positive_points) == 3
    assert len(insight.negative_points) == 3
    assert len(insight.confirmation_gaps) <= 3
    assert any("PER/PBR/ROE" in gap for gap in insight.confirmation_gaps)
    assert not any(term in insight.short_summary for term in FORBIDDEN_RECOMMENDATION_WORDS)


def test_investment_insight_builder_marks_quantitative_metric_shortage_status():
    official_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-ir",
        chunk_id="chunk-ir",
        title="7203 決算短信",
        source_type="earnings_report",
        published_at=date(2026, 5, 20),
        section_title="会社概要",
        excerpt="会社概要と事業セグメントを説明しています。売上高 45兆円。",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.92"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Official evidence exists but metrics are limited.",
        points=[],
        evidence=[official_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 20),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    insight = InvestmentInsightBuilder().build(report)

    assert insight.status_label == "定量指標不足"
    assert insight.confidence_label == "低〜中"
    assert insight.primary_action_label == "PER/PBR/ROEを確認"
    assert any("PER/PBR/ROE" in gap for gap in insight.confirmation_gaps)


def test_investment_question_summary_builder_always_generates_fixed_questions():
    report = CompanyResearchReport(
        symbol="MSFT",
        as_of=date(2026, 5, 25),
        summary="No source-backed evidence.",
        points=[],
        evidence=[],
        data_quality=ResearchDataQuality(
            status="WARN",
            latest_document_date=None,
            document_count=0,
            evidence_count=0,
            warnings=["登録済みResearch資料がありません。"],
        ),
    )

    summary = InvestmentQuestionSummaryBuilder().build(report)

    categories = {answer.category for answer in summary.answers}
    dumped = str(summary.model_dump(mode="json"))

    assert summary.schema_version == "investment-question-summary-v1"
    assert len(summary.answers) == 10
    assert {"business_model", "financial_trend", "valuation"} <= categories
    assert all(answer.question for answer in summary.answers)
    assert all(answer.answer for answer in summary.answers)
    assert any(answer.evidence_level == "missing" for answer in summary.answers)
    assert "PER・PBR・ROE・配当利回りが未取得" in next(
        answer.answer for answer in summary.answers if answer.category == "valuation"
    )
    assert "株主還元は判断できません" in next(
        answer.answer for answer in summary.answers if answer.category == "shareholder_return"
    )
    assert not any(term in dumped for term in FORBIDDEN_RECOMMENDATION_WORDS)


def test_investment_question_summary_builder_maps_sources_to_answers():
    provider_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Yahoo Finance Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Toyota sells vehicles globally and invests in software services. "
            "PER 12.5倍 PBR 1.1倍 ROE 9.8% Dividend 75円"
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    official_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-ir",
        chunk_id="chunk-ir",
        title="7203 決算短信",
        source_type="earnings_report",
        published_at=date(2026, 5, 20),
        section_title="業績",
        excerpt=(
            "売上高 45兆円、営業利益 5兆円、純利益 4兆円、EPS 320円。"
            "通期予想は売上高46兆円、営業利益5.2兆円です。"
            "成長戦略と株主還元を確認できます。"
        ),
        relevance_score=Decimal("0.88"),
        reliability=Decimal("0.94"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 25),
        summary="Source-backed evidence exists.",
        points=[],
        evidence=[provider_evidence, official_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=2,
            evidence_count=2,
            warnings=[],
        ),
    )

    summary = InvestmentQuestionSummaryBuilder().build(report)
    answers = {answer.category: answer for answer in summary.answers}

    assert answers["business_model"].source_titles
    assert "Yahoo Finance Profile" in answers["business_model"].source_titles
    assert answers["business_model"].evidence_level in {"medium", "high"}
    assert answers["financial_trend"].evidence_level == "high"
    assert "売上高 45兆円" in answers["financial_trend"].answer
    assert answers["valuation"].source_titles
    assert "PER" in answers["valuation"].answer
    assert answers["key_takeaway"].answer


def test_investment_question_summary_builder_hides_internal_source_names():
    provider_evidence = ResearchEvidence(
        symbol="ACME",
        document_id="doc-profile",
        chunk_id="chunk-profile",
        title="Provider Profile",
        source_type="provider_profile",
        published_at=date(2026, 5, 24),
        section_title="Profile",
        excerpt=(
            "Company Name: Acme Corporation Provider Symbol: ACME Quote Type: EQUITY "
            "Business Summary: source_type=news provider_profile ExternalResearchFetchResult "
            "source_ynews cloud platform services."
        ),
        relevance_score=Decimal("0.72"),
        reliability=Decimal("0.68"),
    )
    report = CompanyResearchReport(
        symbol="ACME",
        as_of=date(2026, 5, 25),
        summary="Source-backed evidence exists.",
        points=[],
        evidence=[provider_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 5, 24),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    summary = InvestmentQuestionSummaryBuilder().build(report)
    dumped = str(summary.model_dump(mode="json"))

    assert "source_type" not in dumped
    assert "provider_profile" not in dumped
    assert "ExternalResearchFetchResult" not in dumped
    assert "source_ynews" not in dumped


def test_research_ingestion_deduplicates_by_document_hash(tmp_path):
    document_path = tmp_path / "note.md"
    document_path.write_text("Growth strategy and dividend policy.", encoding="utf-8")
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    request = ResearchDocumentRegisterRequest(
        symbol="AAPL",
        title="Apple Note",
        local_path=str(document_path),
        published_at=date(2026, 5, 1),
    )

    first = ingestion.register_document(request)
    second = ingestion.register_document(request)

    assert first.document_id == second.document_id
    assert len(ingestion.list_documents("AAPL")) == 1


def test_research_search_applies_freshness_and_source_type_filters(tmp_path):
    old_path = tmp_path / "old_report.md"
    old_path.write_text(
        "Growth strategy includes market expansion in the legacy plan.",
        encoding="utf-8",
    )
    new_path = tmp_path / "new_report.md"
    new_path.write_text(
        "Growth strategy includes market expansion in the current plan.",
        encoding="utf-8",
    )
    note_path = tmp_path / "user_note.md"
    note_path.write_text(
        "Growth strategy includes market expansion in the analyst note.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Old Annual Report",
            local_path=str(old_path),
            source_type="annual_report",
            published_at=date(2023, 1, 1),
        )
    )
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="New Annual Report",
            local_path=str(new_path),
            source_type="annual_report",
            published_at=date(2026, 5, 1),
        )
    )
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="User Note",
            local_path=str(note_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    index.rebuild_index(symbol="7203.T")

    evidence = retrieval.search(
        ResearchSearchRequest(
            symbol="7203.T",
            query="growth strategy market expansion",
            top_k=3,
            as_of=date(2026, 5, 25),
        )
    )
    filtered = retrieval.search(
        ResearchSearchRequest(
            symbol="7203.T",
            query="growth strategy market expansion",
            top_k=3,
            source_types=["user_note"],
            as_of=date(2026, 5, 25),
        )
    )

    assert evidence[-1].title == "Old Annual Report"
    old = next(row for row in evidence if row.title == "Old Annual Report")
    new = next(row for row in evidence if row.title == "New Annual Report")
    assert old.relevance_score < new.relevance_score
    assert [row.source_type for row in filtered] == ["user_note"]


def test_research_query_expansion_loads_config_and_expands_terms():
    expansion = ResearchQueryExpansionService.from_yaml(Path("config/research_query_terms.yml"))

    result = expansion.expand_query("growth", category="growth")

    assert result.category == "growth"
    assert "growth" in result.expanded_terms
    assert "strategy" in result.expanded_terms
    assert "overseas" in result.expanded_terms


def test_stock_news_analysis_uses_local_news_with_source_url(tmp_path):
    latest_path = tmp_path / "7203_news_latest.md"
    latest_path.write_text(
        """source: Example News
url: https://example.com/7203-earnings
summary: 7203 raised guidance after revenue growth and announced a dividend increase.
""",
        encoding="utf-8",
    )
    stale_path = tmp_path / "7203_news_stale.md"
    stale_path.write_text(
        """source: Example News
url: https://example.com/7203-risk
summary: 7203 faces regulation risk in an older market update.
""",
        encoding="utf-8",
    )
    missing_url_path = tmp_path / "7203_news_missing_url.md"
    missing_url_path.write_text(
        "summary: 7203 has a news-like note, but no source URL.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="7203 Latest Earnings News",
            local_path=str(latest_path),
            source_type="news",
            company_name="Toyota",
            published_at=date(2026, 5, 24),
        )
    )
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="7203 Older Risk News",
            local_path=str(stale_path),
            source_type="news",
            company_name="Toyota",
            published_at=date(2026, 1, 1),
        )
    )
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="7203 Missing URL News",
            local_path=str(missing_url_path),
            source_type="news",
            published_at=date(2026, 5, 24),
        )
    )

    report = StockNewsAnalysisService(ingestion).analyze_symbol_news(
        StockNewsRequest(
            symbol="7203.T",
            company_name="Toyota",
            as_of=date(2026, 5, 25),
        )
    )

    assert report.symbol == "7203.T"
    assert [row.title for row in report.news] == [
        "7203 Latest Earnings News",
        "7203 Older Risk News",
    ]
    assert report.news[0].url == "https://example.com/7203-earnings"
    assert report.news[0].source == "Example News"
    assert report.news[0].investment_viewpoint == "earnings"
    assert report.news[0].sentiment_for_investment == "positive"
    assert report.news[0].freshness_status == "latest"
    assert report.news[1].freshness_status == "stale"
    assert any("source URL" in warning for warning in report.warnings)


def test_external_stock_news_fetch_service_normalizes_research_payloads_without_live_call():
    fetched_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    adapter = ExternalResearchStockNewsAdapter(
        FakeExternalResearchAdapter(
            [
                ExternalResearchSourcePayload(
                    symbol="7203.T",
                    title="7203 Provider Profile",
                    content="Business Summary: Toyota sells vehicles globally.",
                    source_type="provider_profile",
                    source_url="https://example.com/profile",
                    provider="fake_external",
                    company_name="Toyota",
                    published_at=date(2026, 5, 25),
                    fetched_at=fetched_at,
                    reliability=Decimal("0.65"),
                ),
                ExternalResearchSourcePayload(
                    symbol="7203.T",
                    title="7203 Guidance Raised",
                    content=(
                        "source: Example News\n"
                        "url: https://example.com/7203-guidance\n"
                        "summary: Toyota raised guidance after revenue growth."
                    ),
                    source_type="news",
                    source_url="https://example.com/7203-guidance",
                    provider="fake_external",
                    company_name="Toyota",
                    published_at=date(2026, 5, 25),
                    fetched_at=fetched_at,
                    reliability=Decimal("0.70"),
                ),
                ExternalResearchSourcePayload(
                    symbol="7203.T",
                    title="7203 Guidance Raised Duplicate",
                    content=(
                        "source: Example News\n"
                        "url: https://example.com/7203-guidance\n"
                        "summary: Duplicate article should be deduped by URL."
                    ),
                    source_type="news",
                    source_url="https://example.com/7203-guidance",
                    provider="fake_external",
                    company_name="Toyota",
                    published_at=date(2026, 5, 25),
                    fetched_at=fetched_at,
                    reliability=Decimal("0.70"),
                ),
            ]
        )
    )

    report = ExternalStockNewsFetchService(adapter).fetch_news(
        StockNewsRequest(
            symbol="7203.T",
            company_name="Toyota",
            as_of=date(2026, 5, 25),
        )
    )

    assert report.symbol == "7203.T"
    assert [row.title for row in report.news] == ["7203 Guidance Raised"]
    assert report.news[0].url == "https://example.com/7203-guidance"
    assert report.news[0].source == "Example News"
    assert report.news[0].investment_viewpoint == "earnings"
    assert report.news[0].sentiment_for_investment == "positive"
    assert report.news[0].freshness_status == "latest"
    assert report.warnings == []


def test_external_stock_news_fetch_service_warns_about_stale_external_news():
    class FakeExternalStockNewsAdapter:
        provider = "fake_news"
        requires_network = False

        def fetch_news(self, request: StockNewsRequest) -> list[StockNewsEvidence]:
            return [
                StockNewsEvidence(
                    symbol=request.symbol,
                    company_name=request.company_name,
                    title="7203 Old Risk News",
                    url="https://example.com/7203-old-risk",
                    source="Example News",
                    published_at=date(2026, 1, 10),
                    summary="Older lawsuit risk article.",
                    investment_viewpoint="risk",
                    sentiment_for_investment="negative",
                )
            ]

    report = ExternalStockNewsFetchService(FakeExternalStockNewsAdapter()).fetch_news(
        StockNewsRequest(
            symbol="7203.T",
            company_name="Toyota",
            as_of=date(2026, 5, 25),
        )
    )

    assert report.news[0].freshness_status == "stale"
    assert any("公開日が古い" in warning for warning in report.warnings)


def test_external_stock_news_fetch_service_requires_explicit_network_opt_in():
    class NetworkExternalStockNewsAdapter:
        provider = "network_news"
        requires_network = True

        def fetch_news(self, request: StockNewsRequest) -> list[StockNewsEvidence]:
            raise AssertionError("network adapter should not be called without opt-in")

    with pytest.raises(ResearchDocumentError, match="requires explicit network opt-in"):
        ExternalStockNewsFetchService(NetworkExternalStockNewsAdapter()).fetch_news(
            StockNewsRequest(symbol="7203.T", as_of=date(2026, 5, 25)),
            allow_network=False,
        )


def test_google_news_rss_adapter_parses_investment_headlines_without_live_call():
    requested_urls: list[str] = []
    rss_text = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Toyota raises guidance after strong hybrid demand</title>
      <link>https://news.google.com/rss/articles/toyota-guidance</link>
      <pubDate>Tue, 02 Jun 2026 09:30:00 GMT</pubDate>
      <source url="https://example.com">Example News</source>
      <description><![CDATA[<a href="https://example.com/toyota">Toyota</a> raised guidance after revenue growth.]]></description>
    </item>
    <item>
      <title>Toyota supplier risk headline</title>
      <link>https://news.google.com/rss/articles/toyota-risk</link>
      <pubDate>Mon, 01 Jun 2026 08:15:00 GMT</pubDate>
      <source url="https://example.com">Example News</source>
      <description>Supplier risk may affect production.</description>
    </item>
  </channel>
</rss>
"""

    def fake_http_get(url: str) -> str:
        requested_urls.append(url)
        return rss_text

    adapter = GoogleNewsRSSResearchAdapter(
        http_get=fake_http_get,
        lookback_days=7,
        max_results=1,
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota Motor",
            related_keywords=["トヨタ自動車"],
            provider=adapter.provider,
            as_of=date(2026, 6, 2),
            allow_network=True,
        )
    )

    assert requested_urls
    assert "news.google.com/rss/search" in requested_urls[0]
    assert "when%3A7d" in requested_urls[0]
    assert payloads[0].symbol == "7203.T"
    assert payloads[0].title == "Toyota raises guidance after strong hybrid demand"
    assert payloads[0].source_type == "news"
    assert payloads[0].source_url == "https://news.google.com/rss/articles/toyota-guidance"
    assert payloads[0].provider == "google_news_rss"
    assert payloads[0].published_at == date(2026, 6, 2)
    assert "source: Example News" in payloads[0].content
    assert "summary: Toyota raised guidance after revenue growth." in payloads[0].content
    assert "売買推奨ではなく" in payloads[0].content
    assert len(payloads) == 1


def test_google_news_rss_adapter_ignores_invalid_feed_without_live_call():
    adapter = GoogleNewsRSSResearchAdapter(http_get=lambda _: "not xml")

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="AAPL",
            company_name="Apple Inc.",
            provider=adapter.provider,
            as_of=date(2026, 6, 2),
            allow_network=True,
        )
    )

    assert payloads == []


def test_google_news_rss_adapter_does_not_retry_when_retry_count_zero():
    calls = 0

    def fake_http_get(url: str) -> str:
        nonlocal calls
        calls += 1
        raise TimeoutError("feed timed out")

    adapter = GoogleNewsRSSResearchAdapter(
        http_get=fake_http_get,
        retry_count=0,
        retry_backoff_sec=0,
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="AAPL",
            company_name="Apple Inc.",
            provider=adapter.provider,
            as_of=date(2026, 6, 2),
            allow_network=True,
        )
    )

    assert payloads == []
    assert calls == 1
    assert adapter._last_retry_attempts == 0
    assert adapter._last_research_error.details["timeout"] is True


def test_google_news_rss_adapter_retries_transient_timeout_then_succeeds():
    calls = 0
    rss_text = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Apple supplier update</title>
      <link>https://news.google.com/rss/articles/apple</link>
      <pubDate>Tue, 02 Jun 2026 09:30:00 GMT</pubDate>
      <source url="https://example.com">Example News</source>
      <description>Apple supplier update.</description>
    </item>
  </channel>
</rss>
"""

    def fake_http_get(url: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("feed timed out")
        return rss_text

    adapter = GoogleNewsRSSResearchAdapter(
        http_get=fake_http_get,
        retry_count=1,
        retry_backoff_sec=0,
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="AAPL",
            company_name="Apple Inc.",
            provider=adapter.provider,
            as_of=date(2026, 6, 2),
            allow_network=True,
        )
    )

    assert calls == 2
    assert len(payloads) == 1
    assert adapter._last_retry_attempts == 1


def test_google_news_rss_adapter_does_not_retry_http_404():
    calls = 0

    def fake_http_get(url: str) -> str:
        nonlocal calls
        calls += 1
        raise FakeHTTPStatusError(404)

    adapter = GoogleNewsRSSResearchAdapter(
        http_get=fake_http_get,
        retry_count=2,
        retry_backoff_sec=0,
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="AAPL",
            company_name="Apple Inc.",
            provider=adapter.provider,
            as_of=date(2026, 6, 2),
            allow_network=True,
        )
    )

    assert payloads == []
    assert calls == 1
    assert adapter._last_retry_attempts == 0
    assert adapter._last_research_error.details["status_code"] == 404


def test_external_research_fetch_service_registers_sources_without_persisting_payloads(
    tmp_path,
):
    fetched_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    adapter = FakeExternalResearchAdapter(
        [
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 External IR Update",
                content="Revenue growth and dividend policy are discussed in the latest source.",
                source_type="provider_profile",
                source_url="https://example.com/7203-ir",
                provider="fake_external",
                company_name="Toyota",
                published_at=date(2026, 5, 24),
                fetched_at=fetched_at,
                reliability=Decimal("0.80"),
            ),
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 External News",
                content="summary: 7203 raised guidance after revenue growth.\nurl: https://example.com/7203-news",
                source_type="news",
                source_url="https://example.com/7203-news",
                provider="fake_external",
                company_name="Toyota",
                published_at=date(2026, 5, 25),
                fetched_at=fetched_at,
                reliability=Decimal("0.70"),
            ),
        ]
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)

    result = ExternalResearchFetchService(
        adapter,
        ingestion,
        index,
        cache_dir=tmp_path,
    ).fetch_register_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider="fake_external",
            as_of=date(2026, 5, 25),
            allow_network=False,
        )
    )

    assert result.symbol == "7203.T"
    assert result.provider == "fake_external"
    assert result.retention_policy == "session"
    assert len(result.entries) == 2
    assert result.manifest_path is None
    assert {entry.source_type for entry in result.entries} == {
        "provider_profile",
        "news",
    }
    assert all(entry.source_url.startswith("https://example.com/") for entry in result.entries)
    assert {entry.retention_policy for entry in result.entries} == {"session"}
    assert all(entry.local_path is None for entry in result.entries)
    assert all(entry.document_hash is None for entry in result.entries)
    assert {entry.freshness_status for entry in result.entries} == {"latest"}
    assert any("Revenue growth" in entry.content_summary for entry in result.entries)
    assert list(tmp_path.iterdir()) == []
    assert len(store.list_documents("7203.T")) == 2
    assert sum(len(chunks) for chunks in store.chunks_by_document_id.values()) >= 2
    assert all(
        document.local_path.startswith("external://") for document in store.list_documents("7203.T")
    )

    news_report = StockNewsAnalysisService(ingestion).analyze_symbol_news(
        StockNewsRequest(symbol="7203.T", as_of=date(2026, 5, 25))
    )
    assert [row.title for row in news_report.news] == ["7203 External News"]
    assert news_report.news[0].freshness_status == "latest"


def test_external_research_fetch_service_warns_about_stale_sources(tmp_path):
    fetched_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    adapter = FakeExternalResearchAdapter(
        [
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 Old External News",
                content="summary: Older update that should not be treated as current.",
                source_type="news",
                source_url="https://example.com/7203-old-news",
                provider="fake_external",
                company_name="Toyota",
                published_at=date(2026, 1, 10),
                fetched_at=fetched_at,
                reliability=Decimal("0.70"),
            ),
        ]
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)

    result = ExternalResearchFetchService(adapter, ingestion, index).fetch_register_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider="fake_external",
            as_of=date(2026, 5, 25),
            allow_network=False,
        )
    )

    assert len(result.entries) == 1
    assert result.entries[0].freshness_status == "stale"
    assert any("公開日が古い" in warning for warning in result.warnings)


def test_external_research_fetch_service_keeps_provider_statuses_and_partial_warning(tmp_path):
    fetched_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    success = FakeExternalResearchAdapter(
        [
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 Provider Profile",
                content="Provider profile snapshot.",
                source_type="provider_profile",
                source_url="https://example.com/profile",
                provider="fake_external",
                company_name="Toyota",
                published_at=date(2026, 5, 25),
                fetched_at=fetched_at,
                reliability=Decimal("0.65"),
            )
        ]
    )
    adapter = CompositeExternalResearchAdapter(
        [success, SlowExternalResearchAdapter([])],
        external_fetch_config=ExternalFetchPerformanceConfig(
            max_workers=2,
            global_timeout_sec=0.05,
        ),
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)

    result = ExternalResearchFetchService(adapter, ingestion, index).fetch_register_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider=adapter.provider,
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert len(result.entries) == 1
    assert [status.status for status in result.provider_statuses] == ["success", "timeout"]
    assert any("時間切れ" in warning for warning in result.warnings)


def test_external_research_fetch_service_reuses_registered_source_by_url(tmp_path):
    class RefreshingExternalResearchAdapter:
        provider = "fake_external"
        requires_network = False

        def __init__(self) -> None:
            self.calls = 0

        def fetch_sources(
            self, request: ExternalResearchFetchRequest
        ) -> list[ExternalResearchSourcePayload]:
            self.calls += 1
            fetched_at = datetime(2026, 5, 25, 9, self.calls, tzinfo=UTC)
            return [
                ExternalResearchSourcePayload(
                    symbol=request.symbol,
                    title="7203 External News",
                    content="summary: Same URL content should not be re-registered.",
                    source_type="news",
                    source_url="https://example.com/7203-news",
                    provider=self.provider,
                    company_name=request.company_name,
                    published_at=date(2026, 5, 25),
                    fetched_at=fetched_at,
                    reliability=Decimal("0.70"),
                )
            ]

    adapter = RefreshingExternalResearchAdapter()
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    service = ExternalResearchFetchService(adapter, ingestion, index)
    request = ExternalResearchFetchRequest(
        symbol="7203.T",
        company_name="Toyota",
        provider="fake_external",
        as_of=date(2026, 5, 25),
        allow_network=False,
    )

    first = service.fetch_register_sources(request)
    second = service.fetch_register_sources(request)

    assert adapter.calls == 2
    assert len(store.list_documents("7203.T")) == 1
    assert len(store.all_chunks("7203.T")) >= 1
    assert first.entries[0].document_id == second.entries[0].document_id
    assert first.entries[0].fetched_at != second.entries[0].fetched_at


def test_external_research_fetch_requires_explicit_network_opt_in(tmp_path):
    adapter = NetworkExternalResearchAdapter([])
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)

    with pytest.raises(ResearchDocumentError, match="explicit network opt-in"):
        ExternalResearchFetchService(
            adapter,
            ingestion,
            index,
            cache_dir=tmp_path,
        ).fetch_register_sources(
            ExternalResearchFetchRequest(
                symbol="7203.T",
                provider="fake_external",
                allow_network=False,
            )
        )


def test_yahoo_finance_research_adapter_builds_profile_and_news_payloads_without_live_call():
    adapter = YahooFinanceResearchAdapter(ticker_factory=lambda symbol: FakeYahooTicker())

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider="yahoo_finance",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert [payload.source_type for payload in payloads] == ["provider_profile", "news"]
    assert payloads[0].source_url == "https://finance.yahoo.com/quote/7203.T/profile"
    assert payloads[0].published_at == date(2026, 5, 25)
    assert "Market Cap: 35兆円" in payloads[0].content
    assert "Enterprise Value: 37兆円" in payloads[0].content
    assert "Total Revenue: 45兆円" in payloads[0].content
    assert "Operating Income: 5兆円" in payloads[0].content
    assert "Trailing EPS: 320.12円" in payloads[0].content
    assert "Forward PE: 10.4倍" in payloads[0].content
    assert "Return On Equity: 12.4%" in payloads[0].content
    assert "Dividend Yield: 2.1%" in payloads[0].content
    assert "Full Time Employees: 380,000 人" in payloads[0].content
    assert "Toyota sells vehicles" in payloads[0].content
    assert payloads[1].source_url == "https://finance.yahoo.com/news/toyota-guidance"
    assert payloads[1].published_at == date(2026, 5, 25)
    assert "revenue growth" in payloads[1].content


def test_yahoo_finance_research_adapter_uses_shared_yfinance_runtime(monkeypatch):
    ticker_calls: list[tuple[str, object]] = []

    class FakeYFinance:
        def Ticker(self, symbol: str, *, session: object | None = None) -> FakeYahooTicker:
            ticker_calls.append((symbol, session))
            return FakeYahooTicker()

    monkeypatch.setattr(
        "backend.marketdata.providers.yahoo._load_yfinance",
        lambda: FakeYFinance(),
    )
    monkeypatch.setattr(
        "backend.marketdata.providers.yahoo.shared_yfinance_session",
        lambda: "shared-session",
    )

    payloads = YahooFinanceResearchAdapter().fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider="yahoo_finance",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert ticker_calls == [("7203.T", "shared-session")]
    assert payloads[0].source_url == "https://finance.yahoo.com/quote/7203.T/profile"


def test_yahoo_finance_research_adapter_keeps_percent_style_dividend_yield_readable():
    class PercentDividendTicker:
        def get_info(self) -> dict[str, object]:
            return {
                "longName": "Microsoft Corporation",
                "symbol": "MSFT",
                "quoteType": "EQUITY",
                "exchange": "NMS",
                "currency": "USD",
                "dividendYield": 0.85,
                "longBusinessSummary": "Microsoft provides software and cloud services.",
            }

        @property
        def news(self) -> list[dict[str, object]]:
            return []

    adapter = YahooFinanceResearchAdapter(ticker_factory=lambda symbol: PercentDividendTicker())

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="MSFT",
            provider="yahoo_finance",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert [payload.source_type for payload in payloads] == ["provider_profile"]
    assert "Dividend Yield: 0.85%" in payloads[0].content
    assert "Dividend Yield: 85%" not in payloads[0].content


def test_yahoo_finance_research_adapter_exports_etf_metric_candidates():
    class ETFMetricsTicker:
        def get_info(self) -> dict[str, object]:
            return {
                "longName": "Example Treasury ETF",
                "symbol": "TLT",
                "quoteType": "ETF",
                "exchange": "NASDAQ",
                "currency": "USD",
                "fundFamily": "Example Funds",
                "category": "Long Government",
                "expenseRatio": 0.0015,
                "annualReportExpenseRatio": 0.0014,
                "netAssets": 48_000_000_000,
                "navPrice": 90.25,
                "regularMarketPrice": 91.1,
                "yield": 0.045,
                "trailingAnnualDividendYield": 0.044,
                "topHoldings": [
                    {"symbol": "US912810TT51", "holdingName": "U.S. Treasury 4.0%"},
                    {"symbol": "US912810TW80", "holdingName": "U.S. Treasury 3.5%"},
                ],
                "longBusinessSummary": "The fund invests in long-term U.S. Treasury bonds.",
            }

        @property
        def news(self) -> list[dict[str, object]]:
            return []

    adapter = YahooFinanceResearchAdapter(ticker_factory=lambda symbol: ETFMetricsTicker())

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="TLT",
            provider="yahoo_finance",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    content = payloads[0].content
    assert "Fund Family: Example Funds" in content
    assert "Category: Long Government" in content
    assert "Expense Ratio: 0.15%" in content
    assert "Annual Report Expense Ratio: 0.14%" in content
    assert "Net Assets: 48B USD" in content
    assert "NAV Price: 90.25 USD" in content
    assert "Regular Market Price: 91.1 USD" in content
    assert "Yield: 4.5%" in content
    assert "Trailing Annual Dividend Yield: 4.4%" in content
    assert "Top Holdings: US912810TT51" in content


def test_company_ir_site_research_adapter_discovers_official_ir_page_without_live_call():
    class WebsiteTicker:
        def get_info(self) -> dict[str, object]:
            return {
                "longName": "Toyota Motor Corporation",
                "symbol": "7203.T",
                "website": "https://example.com",
            }

    requested_urls: list[str] = []

    def fake_http_get(url: str) -> str:
        requested_urls.append(url)
        if url == "https://example.com/ir":
            return """
            <html><body>
              Investor Relations
              Financial Results
              Annual Report
              株主 投資家 決算
            </body></html>
            """
        raise ResearchDocumentError("page not found")

    adapter = CompanyIRSiteResearchAdapter(
        ticker_factory=lambda symbol: WebsiteTicker(),
        http_get=fake_http_get,
        candidate_paths=("ir", "investors"),
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider="company_ir_site",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert requested_urls == ["https://example.com/ir"]
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload.provider == "company_ir_site"
    assert payload.source_type == "company_ir"
    assert payload.source_url == "https://example.com/ir"
    assert payload.title == "Toyota 公式IRサイト"
    assert payload.published_at is None
    assert payload.reliability == Decimal("0.82")
    assert "source: company official IR site" in payload.content
    assert "Financial Results" in payload.content


def test_company_ir_site_research_adapter_uses_shared_yfinance_runtime(monkeypatch):
    ticker_calls: list[tuple[str, object]] = []
    requested_urls: list[str] = []

    class WebsiteTicker:
        def get_info(self) -> dict[str, object]:
            return {
                "longName": "Toyota Motor Corporation",
                "symbol": "7203.T",
                "website": "https://example.com",
            }

    class FakeYFinance:
        def Ticker(self, symbol: str, *, session: object | None = None) -> WebsiteTicker:
            ticker_calls.append((symbol, session))
            return WebsiteTicker()

    def fake_http_get(url: str) -> str:
        requested_urls.append(url)
        return "<html><body>Investor Relations Financial Results 決算</body></html>"

    monkeypatch.setattr(
        "backend.marketdata.providers.yahoo._load_yfinance",
        lambda: FakeYFinance(),
    )
    monkeypatch.setattr(
        "backend.marketdata.providers.yahoo.shared_yfinance_session",
        lambda: "shared-session",
    )

    payloads = CompanyIRSiteResearchAdapter(
        http_get=fake_http_get,
        candidate_paths=("ir",),
    ).fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider="company_ir_site",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert ticker_calls == [("7203.T", "shared-session")]
    assert requested_urls == ["https://example.com/ir"]
    assert payloads[0].source_url == "https://example.com/ir"


def test_company_ir_site_research_adapter_uses_explicit_website_resolver_first():
    requested_urls: list[str] = []

    def fake_http_get(url: str) -> str:
        requested_urls.append(url)
        return "<html><body>IR情報 投資家 決算 統合報告書</body></html>"

    adapter = CompanyIRSiteResearchAdapter(
        ticker_factory=lambda symbol: pytest.fail("ticker should not be used"),
        http_get=fake_http_get,
        website_resolver=lambda request: "example.com/investors",
        candidate_paths=("ir",),
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="AAPL",
            company_name="Apple Inc.",
            provider="company_ir_site",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert requested_urls == ["https://example.com/investors"]
    assert payloads[0].source_type == "company_ir"
    assert payloads[0].source_url == "https://example.com/investors"


def test_tdnet_research_adapter_builds_disclosure_payloads_without_live_call():
    requested_urls: list[str] = []

    def fake_http_get(url: str) -> str:
        requested_urls.append(url)
        return """
        <html><body><table>
          <tr>
            <td>15:00</td><td>7203</td><td>トヨタ自動車</td>
            <td><a href="./140120260525000001.pdf">2026年3月期 決算短信</a></td>
          </tr>
          <tr>
            <td>15:10</td><td>6758</td><td>ソニーグループ</td>
            <td><a href="./140120260525000002.pdf">別会社の開示</a></td>
          </tr>
        </table></body></html>
        """

    adapter = TDnetResearchAdapter(
        http_get=fake_http_get,
        lookback_days=1,
        max_pages_per_day=1,
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider="tdnet",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert requested_urls == ["https://www.release.tdnet.info/inbs/I_list_001_20260525.html"]
    assert len(payloads) == 1
    assert payloads[0].source_type == "tdnet"
    assert payloads[0].source_url == ("https://www.release.tdnet.info/inbs/140120260525000001.pdf")
    assert payloads[0].published_at == date(2026, 5, 25)
    assert payloads[0].reliability == Decimal("0.85")
    assert "TDnet timely disclosure" in payloads[0].content
    assert "決算短信" in payloads[0].content


def test_tdnet_research_adapter_continues_after_page_fetch_failure():
    def fake_http_get(url: str) -> str:
        if "I_list_001" in url:
            raise ResearchDocumentError("temporary tdnet page failure")
        return """
        <tr>
          <td>16:00</td><td>7203</td><td>Toyota</td>
          <td><a href="./140120260525000003.pdf">Notice of dividend policy</a></td>
        </tr>
        """

    adapter = TDnetResearchAdapter(
        http_get=fake_http_get,
        lookback_days=1,
        max_pages_per_day=2,
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider="tdnet",
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert len(payloads) == 1
    assert payloads[0].source_url == ("https://www.release.tdnet.info/inbs/140120260525000003.pdf")


def test_edinet_research_adapter_builds_filing_payloads_without_live_call():
    requested_urls: list[str] = []

    def fake_http_get_json(url: str) -> dict[str, object]:
        requested_urls.append(url)
        return {
            "metadata": {"status": "200"},
            "results": [
                {
                    "docID": "S100TOYOTA",
                    "edinetCode": "E02144",
                    "secCode": "72030",
                    "filerName": "トヨタ自動車株式会社",
                    "docDescription": "有価証券報告書－第122期",
                    "docTypeCode": "120",
                    "periodStart": "2025-04-01",
                    "periodEnd": "2026-03-31",
                    "submitDateTime": "2026-06-24 15:00",
                },
                {
                    "docID": "S100SONY",
                    "edinetCode": "E01777",
                    "secCode": "67580",
                    "filerName": "ソニーグループ株式会社",
                    "docDescription": "有価証券報告書",
                    "docTypeCode": "120",
                    "submitDateTime": "2026-06-24 15:05",
                },
            ],
        }

    adapter = EDINETResearchAdapter(
        http_get_json=fake_http_get_json,
        api_key="test-edinet-key",
        lookback_days=1,
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="トヨタ自動車",
            provider="edinet",
            as_of=date(2026, 6, 24),
            allow_network=True,
        )
    )

    assert requested_urls == [
        "https://disclosure.edinet-fsa.go.jp/api/v2/documents.json?"
        "date=2026-06-24&type=2&Subscription-Key=test-edinet-key"
    ]
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload.provider == "edinet"
    assert payload.source_type == "annual_report"
    assert payload.title == "7203 EDINET 有価証券報告書－第122期"
    assert payload.source_url == (
        "https://disclosure.edinet-fsa.go.jp/api/v2/documents/S100TOYOTA?type=2"
    )
    assert "test-edinet-key" not in payload.source_url
    assert payload.company_name == "トヨタ自動車"
    assert payload.published_at == date(2026, 6, 24)
    assert payload.reliability == Decimal("0.90")
    assert "source: EDINET official filing" in payload.content
    assert "filer_name: トヨタ自動車株式会社" in payload.content
    assert "document_id: S100TOYOTA" in payload.content
    assert "period_end: 2026-03-31" in payload.content


def test_edinet_research_adapter_skips_live_fetch_without_api_key():
    adapter = EDINETResearchAdapter(api_key="", lookback_days=1)

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            provider="edinet",
            as_of=date(2026, 6, 24),
            allow_network=True,
        )
    )

    assert payloads == []


def test_composite_external_research_adapter_combines_sources_without_live_call():
    fetched_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    first = FakeExternalResearchAdapter(
        [
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 TDnet Disclosure",
                content="Latest official disclosure.",
                source_type="tdnet",
                source_url="https://example.com/tdnet.pdf",
                provider="tdnet",
                company_name="Toyota",
                published_at=date(2026, 5, 25),
                fetched_at=fetched_at,
                reliability=Decimal("0.85"),
            )
        ]
    )
    second = FakeExternalResearchAdapter(
        [
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 Provider Profile",
                content="Provider profile snapshot.",
                source_type="provider_profile",
                source_url="https://example.com/profile",
                provider="yahoo_finance",
                company_name="Toyota",
                published_at=date(2026, 5, 25),
                fetched_at=fetched_at,
                reliability=Decimal("0.65"),
            )
        ]
    )
    adapter = CompositeExternalResearchAdapter([first, second])

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider=adapter.provider,
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert adapter.provider == "tdnet_yahoo_finance"
    assert [payload.provider for payload in payloads] == ["tdnet", "yahoo_finance"]
    assert [payload.source_type for payload in payloads] == [
        "tdnet",
        "provider_profile",
    ]


def test_composite_external_research_adapter_continues_after_source_failure():
    fetched_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    fallback = FakeExternalResearchAdapter(
        [
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 Provider Profile",
                content="Provider profile snapshot.",
                source_type="provider_profile",
                source_url="https://example.com/profile",
                provider="yahoo_finance",
                company_name="Toyota",
                published_at=date(2026, 5, 25),
                fetched_at=fetched_at,
                reliability=Decimal("0.65"),
            )
        ]
    )
    adapter = CompositeExternalResearchAdapter([FailingExternalResearchAdapter([]), fallback])

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider=adapter.provider,
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert [payload.provider for payload in payloads] == ["yahoo_finance"]


def test_research_provider_to_profile_source_mapping():
    assert research_profile_source_key_for_provider("edinet") == "edinet"
    assert research_profile_source_key_for_provider("tdnet") == "tdnet"
    assert research_profile_source_key_for_provider("company_ir_site") == "ir_pages"
    assert research_profile_source_key_for_provider("google_news_rss") == "news"
    assert research_profile_source_key_for_provider("yahoo_finance") == "yahoo_finance"
    assert research_profile_source_key_for_provider("custom_provider") == "custom_provider"


def test_composite_external_research_adapter_records_source_traces():
    fetched_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    success = FakeExternalResearchAdapter(
        [
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 Provider Profile",
                content="Provider profile snapshot.",
                source_type="provider_profile",
                source_url="https://example.com/profile",
                provider="fake_external",
                company_name="Toyota",
                published_at=date(2026, 5, 25),
                fetched_at=fetched_at,
                reliability=Decimal("0.65"),
            )
        ]
    )
    no_result = FakeExternalResearchAdapter([])
    failed = FailingExternalResearchAdapter([])
    timeout = TimeoutExternalResearchAdapter([])
    adapter = CompositeExternalResearchAdapter([success, no_result, failed, timeout])

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider=adapter.provider,
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert len(payloads) == 1
    assert [trace.status for trace in adapter.last_source_traces] == [
        "success",
        "no_result",
        "failed",
        "timeout",
    ]
    assert isinstance(adapter.last_source_traces[0], ResearchSourceTrace)
    assert adapter.last_source_traces[0].result_count == 1
    assert adapter.last_source_traces[2].error_type == "ResearchDocumentError"
    assert adapter.last_source_traces[3].error_type == "TimeoutError"


def test_composite_external_research_adapter_all_failures_return_empty_with_traces():
    adapter = CompositeExternalResearchAdapter(
        [FailingExternalResearchAdapter([]), TimeoutExternalResearchAdapter([])]
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider=adapter.provider,
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert payloads == []
    assert [trace.status for trace in adapter.last_source_traces] == ["failed", "timeout"]


def test_composite_external_research_adapter_global_timeout_returns_partial_results():
    fetched_at = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    success = FakeExternalResearchAdapter(
        [
            ExternalResearchSourcePayload(
                symbol="7203.T",
                title="7203 Provider Profile",
                content="Provider profile snapshot.",
                source_type="provider_profile",
                source_url="https://example.com/profile",
                provider="fake_external",
                company_name="Toyota",
                published_at=date(2026, 5, 25),
                fetched_at=fetched_at,
                reliability=Decimal("0.65"),
            )
        ]
    )
    slow = SlowExternalResearchAdapter([])
    adapter = CompositeExternalResearchAdapter(
        [success, slow],
        external_fetch_config=ExternalFetchPerformanceConfig(
            max_workers=2,
            global_timeout_sec=0.05,
        ),
    )

    payloads = adapter.fetch_sources(
        ExternalResearchFetchRequest(
            symbol="7203.T",
            company_name="Toyota",
            provider=adapter.provider,
            as_of=date(2026, 5, 25),
            allow_network=True,
        )
    )

    assert [payload.provider for payload in payloads] == ["fake_external"]
    assert [trace.status for trace in adapter.last_source_traces] == ["success", "timeout"]
    assert adapter.last_source_traces[1].provider == "slow_external"
    assert adapter.last_source_traces[1].error_type == "TimeoutError"


def test_composite_external_research_adapter_source_worker_limit_uses_profile_source_key():
    adapter = CompositeExternalResearchAdapter(
        [FakeExternalResearchAdapter([])],
        external_fetch_config=ExternalFetchPerformanceConfig(
            max_workers=4,
            per_source_workers={"ir_pages": 2},
        ),
    )

    assert adapter._source_worker_limit("company_ir_site") == 2
    assert adapter._source_worker_limit("unknown_provider") == 1


def test_composite_external_research_adapter_uses_profile_worker_limit():
    adapter = CompositeExternalResearchAdapter(
        [
            FakeExternalResearchAdapter([]),
            FakeExternalResearchAdapter([]),
            FakeExternalResearchAdapter([]),
            FakeExternalResearchAdapter([]),
        ],
        external_fetch_config=ExternalFetchPerformanceConfig(max_workers=2),
    )

    assert adapter._max_workers() == 2


def test_composite_external_research_adapter_caps_workers_by_adapter_count():
    adapter = CompositeExternalResearchAdapter(
        [FakeExternalResearchAdapter([]), FakeExternalResearchAdapter([])],
        external_fetch_config=ExternalFetchPerformanceConfig(max_workers=10),
    )

    assert adapter._max_workers() == 2


def test_external_research_adapters_accept_profile_timeout():
    assert GoogleNewsRSSResearchAdapter(request_timeout_sec=7.5).request_timeout_sec == 7.5
    assert CompanyIRSiteResearchAdapter(request_timeout_sec=7.5).request_timeout_sec == 7.5
    assert TDnetResearchAdapter(request_timeout_sec=7.5).request_timeout_sec == 7.5
    assert EDINETResearchAdapter(request_timeout_sec=7.5).request_timeout_sec == 7.5


def test_default_external_research_adapter_includes_edinet_as_optional_source():
    adapter = DefaultExternalResearchAdapter()

    assert adapter.provider == "edinet_tdnet_company_ir_google_news_yahoo_finance"
    assert [source.provider for source in adapter.adapters] == [
        "edinet",
        "tdnet",
        "company_ir_site",
        "google_news_rss",
        "yahoo_finance",
    ]


def test_default_external_research_adapter_applies_workstation_profile(monkeypatch):
    monkeypatch.setenv(PERFORMANCE_PROFILE_ENV, "workstation")

    adapter = DefaultExternalResearchAdapter()

    assert adapter.performance_profile_name == "workstation"
    assert adapter.external_fetch_config is not None
    assert adapter.external_fetch_config.max_workers == 10
    assert adapter._max_workers() == len(adapter.adapters)
    assert [
        source.request_timeout_sec
        for source in adapter.adapters
        if hasattr(source, "request_timeout_sec")
    ] == [15.0, 15.0, 15.0, 15.0, 15.0]
    assert [
        source.retry_count for source in adapter.adapters if hasattr(source, "retry_count")
    ] == [2, 2, 2, 2]
    assert [
        source.retry_backoff_sec
        for source in adapter.adapters
        if hasattr(source, "retry_backoff_sec")
    ] == [1.2, 1.2, 1.2, 1.2]


def test_research_search_uses_category_query_expansion(tmp_path):
    document_path = tmp_path / "growth_note.md"
    document_path.write_text(
        "The medium-term plan explains overseas expansion and revenue expansion.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Research Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    index.rebuild_index(symbol="7203.T")

    without_expansion = retrieval.search(
        ResearchSearchRequest(symbol="7203.T", query="growth strategy")
    )
    with_expansion = retrieval.search(
        ResearchSearchRequest(
            symbol="7203.T",
            query="growth strategy",
            query_category="growth",
        )
    )

    assert not without_expansion
    assert with_expansion
    assert with_expansion[0].title == "Research Note"


def test_research_analysis_uses_query_expansion_for_topic_evidence(tmp_path):
    document_path = tmp_path / "growth_note.md"
    document_path.write_text(
        "The medium-term plan explains overseas expansion and revenue expansion.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Research Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    index.rebuild_index(symbol="7203.T")

    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 25))
    )

    assert any(point.category == "growth" and point.evidence for point in report.points)
    assert any(
        claim.category == "growth" and claim.supporting_evidence
        for claim in report.extracted_claims
    )


def test_research_analysis_adds_confirmation_gap_claim_for_missing_topic_evidence(
    tmp_path,
):
    document_path = tmp_path / "shareholder_note.md"
    document_path.write_text(
        "Dividend policy and shareholder return remain part of capital allocation.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Shareholder Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    index.rebuild_index(symbol="7203.T")

    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 25))
    )

    gap_claims = [
        claim for claim in report.extracted_claims if claim.category == "confirmation_gap"
    ]
    assert gap_claims
    assert any("成長材料" in claim.claim for claim in gap_claims)
    assert all(not claim.supporting_evidence for claim in gap_claims)
    assert all(claim.confidence == Decimal("0") for claim in gap_claims)
    assert report.grounded_answer is not None
    assert "追加確認が必要" in report.grounded_answer.answer


def test_research_grounded_answer_uses_template_without_unsupported_claims():
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store)
    retrieval = ResearchRetrievalService(store)

    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="MSFT", as_of=date(2026, 5, 24))
    )

    assert report.grounded_answer is not None
    assert report.grounded_answer.provider == "template"
    assert report.grounded_answer.evidence_count == 0
    assert not report.grounded_answer.referenced_evidence
    assert "十分な根拠はまだ確認できません" in report.grounded_answer.answer
    assert "売買推奨ではなく" in report.grounded_answer.answer
    assert report.retrieval_quality is not None
    assert report.retrieval_quality.evidence_count == 0
    assert "検索で根拠候補が見つかりませんでした。" in report.retrieval_quality.warnings


def test_research_evidence_reranker_prefers_official_sources_when_scores_are_close():
    reranker = ResearchEvidenceReranker()
    user_note = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-user",
        chunk_id="chunk-user",
        title="User Note",
        source_type="user_note",
        published_at=date(2026, 5, 1),
        excerpt="Growth strategy and overseas expansion.",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.80"),
    )
    annual_report = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-annual",
        chunk_id="chunk-annual",
        title="Annual Report",
        source_type="annual_report",
        published_at=date(2025, 12, 1),
        excerpt="Growth strategy and overseas expansion.",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.80"),
    )

    reranked = reranker.rerank([user_note, annual_report], as_of=date(2026, 5, 25))

    assert [row.title for row in reranked] == ["Annual Report", "User Note"]


def test_research_evidence_reranker_prefers_reliability_and_suppresses_duplicates():
    reranker = ResearchEvidenceReranker()
    duplicate_low = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-a",
        chunk_id="same-chunk",
        title="Low Duplicate",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        excerpt="Dividend policy.",
        relevance_score=Decimal("0.50"),
        reliability=Decimal("0.90"),
    )
    duplicate_high = duplicate_low.model_copy(
        update={
            "title": "High Duplicate",
            "relevance_score": Decimal("0.70"),
            "reliability": Decimal("0.90"),
        }
    )
    low_reliability = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-b",
        chunk_id="chunk-b",
        title="Low Reliability",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        excerpt="Dividend policy.",
        relevance_score=Decimal("0.70"),
        reliability=Decimal("0.30"),
    )

    reranked = reranker.rerank(
        [low_reliability, duplicate_low, duplicate_high],
        as_of=date(2026, 5, 25),
    )

    assert [row.title for row in reranked] == ["High Duplicate", "Low Reliability"]
    assert len(reranked) == 2


def test_research_analysis_warns_when_evidence_reliability_is_low(tmp_path):
    document_path = tmp_path / "low_reliability_note.md"
    document_path.write_text(
        "Growth strategy includes market expansion and shareholder return.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    index = ResearchIndexService(store, max_chars=240)
    retrieval = ResearchRetrievalService(store)

    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Low Reliability Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
            reliability=Decimal("0.40"),
        )
    )
    index.rebuild_index(symbol="7203.T")

    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 25))
    )

    assert report.data_quality.status == "WARN"
    assert report.data_quality.evidence_count > 0
    assert "信頼度が低い" in " ".join(report.data_quality.warnings)


def test_research_ingestion_rejects_path_outside_document_dirs(tmp_path):
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    outside_path = tmp_path / "outside.md"
    outside_path.write_text("Growth strategy.", encoding="utf-8")
    ingestion = ResearchIngestionService(ResearchInMemoryStore(), document_dirs=[allowed_dir])

    with pytest.raises(ResearchDocumentError) as exc_info:
        ingestion.register_document(
            ResearchDocumentRegisterRequest(
                symbol="AAPL",
                title="Outside",
                local_path=str(outside_path),
            )
        )

    assert "outside configured document directories" in exc_info.value.message


def test_research_analysis_marks_missing_evidence_as_warning():
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store)
    retrieval = ResearchRetrievalService(store)
    report = ResearchAnalysisService(ingestion, retrieval).analyze_company(
        CompanyResearchRequest(symbol="MSFT", as_of=date(2026, 5, 24))
    )

    assert report.data_quality.status == "WARN"
    assert report.data_quality.document_count == 0
    assert report.data_quality.evidence_count == 0
    assert any(point.category == "confirmation_gap" for point in report.points)


def test_research_disabled_vector_store_returns_empty_candidates_and_quality_warning():
    vector_store = ResearchDisabledVectorStore()
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth strategy",
        expanded_terms=["growth", "strategy"],
    )

    candidates = vector_store.search(request)
    quality = vector_store.retrieval_quality(request)

    assert candidates == []
    assert quality.backend == "vector"
    assert quality.candidate_count == 0
    assert quality.evidence_count == 0
    assert quality.expanded_terms == ["growth", "strategy"]
    assert "Vector retrieval is disabled" in quality.warnings[0]


def test_research_hybrid_scorer_combines_keyword_vector_freshness_and_reliability():
    candidate = ResearchRetrievalCandidate(
        symbol="7203.T",
        document_id="doc-1",
        chunk_id="chunk-1",
        title="Annual Report",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Growth",
        excerpt="Growth strategy and overseas expansion.",
        keyword_score=Decimal("0.80"),
        vector_score=Decimal("0.60"),
        reliability=Decimal("0.90"),
    )

    scored = ResearchHybridScorer().score(candidate, as_of=date(2026, 5, 25))

    assert scored.retrieval_backend == "hybrid"
    assert scored.freshness_score == Decimal("1")
    assert scored.final_relevance_score == Decimal("0.7700")


def test_research_embedding_contract_carries_cache_key_fields():
    embedding = ResearchEmbedding(
        chunk_id="chunk-1",
        symbol="7203.T",
        embedding_model="local-test",
        vector=[0.1, 0.2, 0.3],
        created_at=datetime(2026, 5, 25, tzinfo=UTC),
        text_hash="abc123",
    )

    assert embedding.chunk_id == "chunk-1"
    assert embedding.embedding_model == "local-test"
    assert embedding.text_hash == "abc123"


def test_research_embedding_service_builds_stable_chunk_and_query_vectors():
    created_at = datetime(2026, 5, 25, tzinfo=UTC)
    service = ResearchEmbeddingService(dimensions=8, created_at=created_at)
    chunk = ResearchChunk(
        document_id="doc-1",
        chunk_id="chunk-growth",
        symbol="7203.t",
        title="Growth Note",
        source_type="user_note",
        published_at=date(2026, 5, 1),
        text="Growth strategy includes market expansion and overseas revenue.",
        chunk_index=0,
        char_count=64,
        metadata={"reliability": "0.80"},
    )

    first = service.embed_chunk(chunk)
    second = service.embed_chunk(chunk)
    query_vector = service.build_query_vector("growth strategy market")
    candidate = service.candidate_from_chunk(chunk, keyword_score=Decimal("0.25"))

    assert first.schema_version == "research-embedding-v1"
    assert first.symbol == "7203.T"
    assert first.embedding_model == "local-hash-v1"
    assert first.created_at == created_at
    assert first.text_hash == hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
    assert first.vector == second.vector
    assert len(first.vector) == 8
    assert len(query_vector) == 8
    assert any(value != 0 for value in query_vector)
    assert candidate.reliability == Decimal("0.80")
    assert candidate.final_relevance_score == Decimal("0.25")
    assert candidate.retrieval_backend == "vector"


def test_research_embedding_service_upserts_chunks_for_vector_search():
    service = ResearchEmbeddingService(
        dimensions=16,
        created_at=datetime(2026, 5, 25, tzinfo=UTC),
    )
    vector_store = ResearchInMemoryVectorStore()
    growth_chunk = ResearchChunk(
        document_id="doc-growth",
        chunk_id="chunk-growth",
        symbol="7203.T",
        title="Growth Note",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        text="Growth strategy includes market expansion and overseas revenue.",
        chunk_index=0,
        char_count=64,
        metadata={"reliability": "0.90"},
    )
    dividend_chunk = growth_chunk.model_copy(
        update={
            "document_id": "doc-dividend",
            "chunk_id": "chunk-dividend",
            "title": "Dividend Note",
            "text": "Shareholder return includes dividend policy and capital allocation.",
        }
    )
    service.upsert_chunks([growth_chunk, dividend_chunk], vector_store)
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth strategy market",
        query_vector=service.build_query_vector("growth strategy market"),
        top_k=1,
    )

    candidates = vector_store.search(request)
    quality = vector_store.retrieval_quality(request)

    assert [candidate.chunk_id for candidate in candidates] == ["chunk-growth"]
    assert candidates[0].final_relevance_score == candidates[0].vector_score
    assert quality.backend == "vector"
    assert quality.candidate_count == 1


def test_research_embedding_service_rejects_invalid_dimensions():
    with pytest.raises(ResearchSearchError):
        ResearchEmbeddingService(dimensions=1)


def test_research_vector_index_service_rebuilds_file_cache_from_chunks(tmp_path):
    document_path = tmp_path / "vector_note.md"
    document_path.write_text(
        "Growth strategy includes market expansion and overseas revenue.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Vector Note",
            local_path=str(document_path),
            source_type="annual_report",
            published_at=date(2026, 5, 1),
            reliability=Decimal("0.90"),
        )
    )
    text_summary = ResearchIndexService(store, max_chars=240).rebuild_index(symbol="7203.T")
    cache_path = tmp_path / "vectors.jsonl"
    embedding_service = ResearchEmbeddingService(
        dimensions=16,
        created_at=datetime(2026, 5, 25, tzinfo=UTC),
    )
    vector_index = ResearchVectorIndexService(
        store,
        ResearchFileVectorStore(cache_path),
        embedding_service,
    )

    summary = vector_index.rebuild_index(symbol="7203.T")
    reloaded = ResearchFileVectorStore(cache_path)
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth strategy market",
        query_vector=embedding_service.build_query_vector("growth strategy market"),
    )
    candidates = reloaded.search(request)

    assert summary.schema_version == "research-vector-index-v1"
    assert summary.embedding_model == "local-hash-v1"
    assert summary.dimensions == 16
    assert summary.chunk_count == text_summary.chunk_count
    assert summary.embedded_count == text_summary.chunk_count
    assert summary.symbols == ["7203.T"]
    assert not summary.warnings
    assert cache_path.exists()
    assert candidates
    assert candidates[0].title == "Vector Note"
    assert candidates[0].retrieval_backend == "vector"


def test_research_vector_index_service_warns_when_text_index_is_missing():
    summary = ResearchVectorIndexService(
        ResearchInMemoryStore(),
        ResearchInMemoryVectorStore(),
    ).rebuild_index(symbol="7203.T")

    assert summary.chunk_count == 0
    assert summary.embedded_count == 0
    assert summary.symbols == []
    assert "rebuild the text index first" in summary.warnings[0]


def test_hybrid_retrieval_falls_back_to_keyword_when_vector_store_is_disabled(tmp_path):
    document_path = tmp_path / "growth_note.md"
    document_path.write_text(
        "Growth strategy includes market expansion and overseas revenue.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    ResearchIndexService(store, max_chars=240).rebuild_index(symbol="7203.T")
    ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Growth Note",
            local_path=str(document_path),
            source_type="user_note",
            published_at=date(2026, 5, 1),
        )
    )
    ResearchIndexService(store, max_chars=240).rebuild_index(symbol="7203.T")
    keyword = ResearchRetrievalService(store)
    hybrid = HybridResearchRetrievalService(keyword)
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth strategy market",
        top_k=2,
        as_of=date(2026, 5, 25),
    )

    evidence = hybrid.search(request)
    quality = hybrid.retrieval_quality(request)

    assert evidence
    assert evidence[0].title == "Growth Note"
    assert quality.backend == "hybrid"
    assert quality.candidate_count == len(evidence)
    assert "Hybrid retrieval fell back to keyword retrieval." in quality.warnings


def test_hybrid_retrieval_scores_vector_candidates_when_available():
    class FakeVectorStore:
        def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]:
            return [
                ResearchRetrievalCandidate(
                    symbol=request.symbol,
                    document_id="doc-vector",
                    chunk_id="chunk-vector",
                    title="Vector Report",
                    source_type="annual_report",
                    published_at=date(2026, 5, 1),
                    section_title="Growth",
                    excerpt="Growth strategy and overseas expansion.",
                    keyword_score=Decimal("0.50"),
                    vector_score=Decimal("0.90"),
                    reliability=Decimal("0.80"),
                )
            ]

        def retrieval_quality(
            self,
            request: ResearchSearchRequest,
            *,
            expanded_terms: list[str] | None = None,
        ) -> ResearchRetrievalQuality:
            return ResearchRetrievalQuality(
                backend="vector",
                query=request.query,
                expanded_terms=expanded_terms or request.expanded_terms,
                candidate_count=1,
                evidence_count=1,
                warnings=[],
            )

    hybrid = HybridResearchRetrievalService(
        ResearchRetrievalService(ResearchInMemoryStore()),
        vector_store=FakeVectorStore(),
    )
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth strategy",
        top_k=1,
        as_of=date(2026, 5, 25),
    )

    evidence = hybrid.search(request)
    quality = hybrid.retrieval_quality(request)

    assert evidence[0].title == "Vector Report"
    assert evidence[0].relevance_score == Decimal("0.7450")
    assert quality.backend == "hybrid"
    assert quality.candidate_count == 1


def test_hybrid_retrieval_keeps_exact_keyword_evidence_alongside_vector_candidates(tmp_path):
    official_path = tmp_path / "official_growth.md"
    official_path.write_text(
        "Official medium-term plan: growth strategy and overseas expansion are confirmed.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    document = ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Official Medium-term Plan",
            local_path=str(official_path),
            source_type="annual_report",
            published_at=date(2026, 5, 1),
            reliability=Decimal("0.95"),
        )
    )
    ResearchIndexService(store, max_chars=240).build_chunks(document.document_id)

    class FakeVectorStore:
        def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]:
            return [
                ResearchRetrievalCandidate(
                    symbol="7203.T",
                    document_id="semantic-news",
                    chunk_id="semantic-news-1",
                    title="Semantic market commentary",
                    source_type="news",
                    published_at=date(2026, 5, 20),
                    excerpt="A broadly related market commentary.",
                    vector_score=Decimal("0.82"),
                    reliability=Decimal("0.55"),
                )
            ]

        def retrieval_quality(
            self,
            request: ResearchSearchRequest,
            *,
            expanded_terms: list[str] | None = None,
        ) -> ResearchRetrievalQuality:
            return ResearchRetrievalQuality(
                backend="vector",
                query=request.query,
                expanded_terms=expanded_terms or [],
                candidate_count=1,
                evidence_count=1,
            )

    evidence = HybridResearchRetrievalService(
        ResearchRetrievalService(store),
        vector_store=FakeVectorStore(),
    ).search(
        ResearchSearchRequest(
            symbol="7203.T",
            query="growth strategy overseas expansion",
            top_k=2,
            as_of=date(2026, 5, 25),
        )
    )

    assert {row.title for row in evidence} == {
        "Official Medium-term Plan",
        "Semantic market commentary",
    }
    assert evidence[0].title == "Official Medium-term Plan"


def test_research_analysis_reports_hybrid_retrieval_quality(tmp_path):
    document_path = tmp_path / "hybrid_report.md"
    document_path.write_text(
        "Growth strategy includes market expansion, overseas revenue, cash discipline, "
        "dividend policy, and regulation risk.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    document = ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="7203.T",
            title="Hybrid Research Report",
            local_path=str(document_path),
            source_type="annual_report",
            published_at=date(2026, 5, 1),
            reliability=Decimal("0.90"),
        )
    )
    ResearchIndexService(store, max_chars=240).build_chunks(document.document_id)
    vector_store = ResearchInMemoryVectorStore()
    ResearchVectorIndexService(store, vector_store).rebuild_index(symbol="7203.T")

    report = ResearchAnalysisService(
        ingestion,
        HybridResearchRetrievalService(
            ResearchRetrievalService(store),
            vector_store=vector_store,
        ),
    ).analyze_company(CompanyResearchRequest(symbol="7203.T", as_of=date(2026, 5, 25)))

    assert report.retrieval_quality is not None
    assert report.retrieval_quality.backend == "hybrid"
    assert report.retrieval_quality.keyword_candidate_count > 0
    assert report.retrieval_quality.document_count == 1
    assert report.retrieval_quality.latency_ms >= 0


def test_research_analysis_marks_low_relevance_cross_topic_matches_as_gaps(tmp_path):
    document_path = tmp_path / "spy_profile.md"
    document_path.write_text(
        "SPY fund profile: S&P 500 index exposure, expense ratio, distribution policy, "
        "tracking method and market risk.",
        encoding="utf-8",
    )
    store = ResearchInMemoryStore()
    ingestion = ResearchIngestionService(store, document_dirs=[tmp_path])
    document = ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol="SPY",
            title="SPY Fund Profile",
            local_path=str(document_path),
            source_type="provider_profile",
            published_at=date(2026, 6, 1),
            reliability=Decimal("0.90"),
        )
    )
    ResearchIndexService(store, max_chars=240).build_chunks(document.document_id)
    vector_store = ResearchInMemoryVectorStore()
    ResearchVectorIndexService(store, vector_store).rebuild_index(symbol="SPY")
    report = ResearchAnalysisService(
        ingestion,
        HybridResearchRetrievalService(
            ResearchRetrievalService(store),
            vector_store=vector_store,
        ),
    ).analyze_company(CompanyResearchRequest(symbol="SPY", as_of=date(2026, 7, 12)))

    points_by_category = {point.category: point for point in report.points}
    assert not points_by_category["growth"].evidence
    assert not points_by_category["financial_safety"].evidence
    assert points_by_category["business_risk"].evidence
    assert any(
        claim.category == "confirmation_gap" and "成長材料" in claim.claim
        for claim in report.extracted_claims
    )
    assert report.retrieval_quality is not None
    assert any("関連性が低い候補" in warning for warning in report.retrieval_quality.warnings)


def test_vector_index_rebuild_batches_file_writes_and_replaces_symbol_entries(
    tmp_path, monkeypatch
):
    vector_store = ResearchFileVectorStore(tmp_path / "vectors.jsonl")
    store = ResearchInMemoryStore()
    first_chunk = ResearchChunk(
        document_id="doc-current",
        chunk_id="chunk-current-1",
        symbol="7203.T",
        title="Current IR",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        text="Growth strategy and dividend policy.",
        chunk_index=0,
        char_count=36,
    )
    second_chunk = first_chunk.model_copy(
        update={
            "chunk_id": "chunk-current-2",
            "chunk_index": 1,
            "text": "Cash and financial safety are maintained.",
        }
    )
    stale_chunk = first_chunk.model_copy(
        update={
            "document_id": "doc-stale",
            "chunk_id": "chunk-stale",
            "title": "Stale IR",
            "text": "Old business description.",
        }
    )
    embedding_service = ResearchEmbeddingService(
        dimensions=16,
        created_at=datetime(2026, 5, 25, tzinfo=UTC),
    )
    stale_candidate, stale_embedding = embedding_service.embedding_candidate_pair(stale_chunk)
    vector_store.upsert(stale_candidate, stale_embedding)
    store.chunks_by_document_id["doc-current"] = [first_chunk, second_chunk]

    write_count = 0
    original_write = vector_store._write_entries

    def count_write() -> None:
        nonlocal write_count
        write_count += 1
        original_write()

    monkeypatch.setattr(vector_store, "_write_entries", count_write)
    summary = ResearchVectorIndexService(
        store,
        vector_store,
        embedding_service,
    ).rebuild_index(symbol="7203.T")

    reloaded = ResearchFileVectorStore(vector_store.cache_path)
    assert summary.embedded_count == 2
    assert write_count == 1
    assert set(reloaded._entries) == {"chunk-current-1", "chunk-current-2"}


def test_vector_index_rebuild_removes_cached_vectors_when_symbol_has_no_chunks(tmp_path):
    vector_store = ResearchFileVectorStore(tmp_path / "vectors.jsonl")
    embedding_service = ResearchEmbeddingService(
        dimensions=16,
        created_at=datetime(2026, 5, 25, tzinfo=UTC),
    )
    removed_chunk = ResearchChunk(
        document_id="doc-transient",
        chunk_id="chunk-transient",
        symbol="7203.T",
        title="Transient external source",
        source_type="news",
        published_at=date(2026, 5, 20),
        text="Temporary external research material.",
        chunk_index=0,
        char_count=37,
    )
    retained_chunk = removed_chunk.model_copy(
        update={
            "document_id": "doc-retained",
            "chunk_id": "chunk-retained",
            "symbol": "6758.T",
            "title": "Other symbol material",
        }
    )
    vector_store.upsert_many(
        [
            embedding_service.embedding_candidate_pair(removed_chunk),
            embedding_service.embedding_candidate_pair(retained_chunk),
        ]
    )

    summary = ResearchVectorIndexService(
        ResearchInMemoryStore(),
        vector_store,
        embedding_service,
    ).rebuild_index(symbol="7203.T")

    reloaded = ResearchFileVectorStore(vector_store.cache_path)
    assert summary.chunk_count == 0
    assert summary.embedded_count == 0
    assert "No research chunks available" in summary.warnings[0]
    assert set(reloaded._entries) == {"chunk-retained"}


def test_in_memory_vector_store_searches_by_query_vector_and_filters_symbol():
    store = ResearchInMemoryVectorStore()
    toyota_candidate = ResearchRetrievalCandidate(
        symbol="7203.T",
        document_id="doc-toyota",
        chunk_id="chunk-toyota",
        title="Toyota Vector Note",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Growth",
        excerpt="Growth strategy and overseas expansion.",
        keyword_score=Decimal("0.40"),
        reliability=Decimal("0.90"),
    )
    unrelated_candidate = toyota_candidate.model_copy(
        update={
            "symbol": "6758.T",
            "document_id": "doc-sony",
            "chunk_id": "chunk-sony",
            "title": "Sony Vector Note",
        }
    )
    store.upsert(
        toyota_candidate,
        ResearchEmbedding(
            chunk_id="chunk-toyota",
            symbol="7203.T",
            embedding_model="local-test",
            vector=[1.0, 0.0],
            created_at=datetime(2026, 5, 25, tzinfo=UTC),
            text_hash="hash-toyota",
        ),
    )
    store.upsert(
        unrelated_candidate,
        ResearchEmbedding(
            chunk_id="chunk-sony",
            symbol="6758.T",
            embedding_model="local-test",
            vector=[1.0, 0.0],
            created_at=datetime(2026, 5, 25, tzinfo=UTC),
            text_hash="hash-sony",
        ),
    )
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth",
        query_vector=[1.0, 0.0],
    )

    candidates = store.search(request)
    quality = store.retrieval_quality(request)

    assert [candidate.title for candidate in candidates] == ["Toyota Vector Note"]
    assert candidates[0].vector_score == Decimal("1.0000")
    assert quality.backend == "vector"
    assert quality.candidate_count == 1
    assert not quality.warnings


def test_in_memory_vector_store_empty_query_reports_warning():
    store = ResearchInMemoryVectorStore()
    request = ResearchSearchRequest(symbol="7203.T", query="growth")

    assert store.search(request) == []
    quality = store.retrieval_quality(request)

    assert quality.backend == "vector"
    assert quality.candidate_count == 0
    assert "Vector query is empty" in quality.warnings[0]


def test_in_memory_vector_store_rejects_mismatched_embedding_chunk_id():
    store = ResearchInMemoryVectorStore()
    candidate = ResearchRetrievalCandidate(
        symbol="7203.T",
        document_id="doc-1",
        chunk_id="chunk-candidate",
        title="Vector Note",
        source_type="annual_report",
        excerpt="Growth strategy.",
        reliability=Decimal("0.90"),
    )

    with pytest.raises(ResearchSearchError):
        store.upsert(
            candidate,
            ResearchEmbedding(
                chunk_id="chunk-embedding",
                symbol="7203.T",
                embedding_model="local-test",
                vector=[1.0, 0.0],
                created_at=datetime(2026, 5, 25, tzinfo=UTC),
                text_hash="hash",
            ),
        )


def test_file_vector_store_persists_entries_and_searches_after_reload(tmp_path):
    cache_path = tmp_path / "research_vectors.jsonl"
    store = ResearchFileVectorStore(cache_path)
    candidate = ResearchRetrievalCandidate(
        symbol="7203.T",
        document_id="doc-toyota",
        chunk_id="chunk-toyota",
        title="Toyota File Vector Note",
        source_type="annual_report",
        published_at=date(2026, 5, 1),
        section_title="Growth",
        excerpt="Growth strategy and overseas expansion.",
        keyword_score=Decimal("0.40"),
        reliability=Decimal("0.90"),
    )
    store.upsert(
        candidate,
        ResearchEmbedding(
            chunk_id="chunk-toyota",
            symbol="7203.T",
            embedding_model="local-test",
            vector=[1.0, 0.0],
            created_at=datetime(2026, 5, 25, tzinfo=UTC),
            text_hash="hash-toyota",
        ),
    )

    reloaded = ResearchFileVectorStore(cache_path)
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth",
        query_vector=[1.0, 0.0],
    )
    candidates = reloaded.search(request)
    quality = reloaded.retrieval_quality(request)

    assert cache_path.exists()
    assert [candidate.title for candidate in candidates] == ["Toyota File Vector Note"]
    assert candidates[0].vector_score == Decimal("1.0000")
    assert quality.backend == "vector"
    assert quality.candidate_count == 1
    assert not quality.warnings


def test_file_vector_store_reports_empty_cache_warning(tmp_path):
    store = ResearchFileVectorStore(tmp_path / "missing_vectors.jsonl")
    request = ResearchSearchRequest(
        symbol="7203.T",
        query="growth",
        query_vector=[1.0, 0.0],
    )

    assert store.search(request) == []
    quality = store.retrieval_quality(request)

    assert quality.candidate_count == 0
    assert "Vector cache is empty" in quality.warnings[0]
    assert "Vector retrieval found no matching candidates." in quality.warnings


def test_file_vector_store_rejects_invalid_cache(tmp_path):
    cache_path = tmp_path / "research_vectors.jsonl"
    cache_path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(ResearchSearchError):
        ResearchFileVectorStore(cache_path)
