from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.research.service import (
        CompanyResearchReport,
        CompanyResearchSummary,
        ETFResearchSummary,
        ExternalResearchFetchResult,
        InvestmentInsight,
        InvestmentQuestionSummary,
        ResearchBrief,
        ResearchPageViewModel,
        SecurityResearchType,
        StockNewsReport,
    )

_SERVICE_SYMBOL_NAMES = (
    "CompanyResearchSummary",
    "ETFResearchSummary",
    "InvestmentInsight",
    "InvestmentQuestionSummary",
    "ResearchBrief",
    "ResearchPageViewModel",
    "_INVESTMENT_QUESTION_SPECS",
    "_company_research_ai_reading_notes",
    "_company_research_evidence_level_from_source_types",
    "_company_research_ir_items",
    "_company_research_missing_critical_items",
    "_company_research_news_items",
    "_company_research_normalized_evidence",
    "_company_research_overview_summary",
    "_company_research_quantitative_summary",
    "_etf_research_asset_class",
    "_etf_research_benchmark_index",
    "_etf_research_fund_overview",
    "_etf_research_investment_target",
    "_etf_research_metric_value",
    "_etf_research_missing_items",
    "_etf_research_region_focus",
    "_etf_research_risk_notes",
    "_etf_research_sector_focus",
    "_etf_research_source_text",
    "_etf_research_top_holdings",
    "_investment_insight_action_hints",
    "_investment_insight_confidence",
    "_investment_insight_confidence_label",
    "_investment_insight_confirmation_gaps",
    "_investment_insight_headline",
    "_investment_insight_negative_points",
    "_investment_insight_neutral_points",
    "_investment_insight_positive_points",
    "_investment_insight_primary_action_label",
    "_investment_insight_short_summary",
    "_investment_insight_status_label",
    "_investment_question_answer",
    "_investment_question_missing_critical_items",
    "_research_brief_business_overview",
    "_research_brief_caution_materials",
    "_research_brief_confirmation_gaps",
    "_research_brief_memo",
    "_research_brief_metrics",
    "_research_brief_missing_metric_labels",
    "_research_brief_next_actions",
    "_research_brief_positive_materials",
    "_research_brief_source_cards",
    "_research_fact_summary",
    "_security_research_detection_text",
    "_security_research_exchange_is_domestic",
    "_security_research_exchange_is_foreign",
    "_security_research_metadata_value",
    "_unique_text",
)

_INVESTMENT_QUESTION_SPECS: Any = None
_company_research_ai_reading_notes: Any = None
_company_research_evidence_level_from_source_types: Any = None
_company_research_ir_items: Any = None
_company_research_missing_critical_items: Any = None
_company_research_news_items: Any = None
_company_research_normalized_evidence: Any = None
_company_research_overview_summary: Any = None
_company_research_quantitative_summary: Any = None
_etf_research_asset_class: Any = None
_etf_research_benchmark_index: Any = None
_etf_research_fund_overview: Any = None
_etf_research_investment_target: Any = None
_etf_research_metric_value: Any = None
_etf_research_missing_items: Any = None
_etf_research_region_focus: Any = None
_etf_research_risk_notes: Any = None
_etf_research_sector_focus: Any = None
_etf_research_source_text: Any = None
_etf_research_top_holdings: Any = None
_investment_insight_action_hints: Any = None
_investment_insight_confidence: Any = None
_investment_insight_confidence_label: Any = None
_investment_insight_confirmation_gaps: Any = None
_investment_insight_headline: Any = None
_investment_insight_negative_points: Any = None
_investment_insight_neutral_points: Any = None
_investment_insight_positive_points: Any = None
_investment_insight_primary_action_label: Any = None
_investment_insight_short_summary: Any = None
_investment_insight_status_label: Any = None
_investment_question_answer: Any = None
_investment_question_missing_critical_items: Any = None
_research_brief_business_overview: Any = None
_research_brief_caution_materials: Any = None
_research_brief_confirmation_gaps: Any = None
_research_brief_memo: Any = None
_research_brief_metrics: Any = None
_research_brief_missing_metric_labels: Any = None
_research_brief_next_actions: Any = None
_research_brief_positive_materials: Any = None
_research_brief_source_cards: Any = None
_research_fact_summary: Any = None
_security_research_detection_text: Any = None
_security_research_exchange_is_domestic: Any = None
_security_research_exchange_is_foreign: Any = None
_security_research_metadata_value: Any = None
_unique_text: Any = None


def _load_all_service_symbols() -> None:
    from backend.research import service as research_service

    module_globals = globals()
    for name in _SERVICE_SYMBOL_NAMES:
        module_globals[name] = getattr(research_service, name)


class ResearchBriefBuilder:
    """Build a readable local Research memo without external LLM calls."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
    ) -> ResearchBrief:
        _load_all_service_symbols()
        metrics = _research_brief_metrics(report.evidence)
        missing_metrics = _research_brief_missing_metric_labels(metrics)
        positive_materials = _research_brief_positive_materials(report, news_report)
        caution_materials = _research_brief_caution_materials(report, news_report)
        positive_candidates = [material.summary for material in positive_materials]
        caution_candidates = [material.summary for material in caution_materials]
        confirmation_gaps = _research_brief_confirmation_gaps(
            report,
            missing_metrics,
            news_report=news_report,
        )
        next_actions = _research_brief_next_actions(
            report,
            missing_metrics,
            external_research_result=external_research_result,
        )
        source_cards = _research_brief_source_cards(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        fact_summary = _research_fact_summary(
            report,
            metrics=metrics,
            positive_materials=positive_materials,
            caution_materials=caution_materials,
            missing_metrics=missing_metrics,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        return ResearchBrief(
            symbol=report.symbol,
            as_of=report.as_of,
            memo=_research_brief_memo(
                report,
                metrics,
                source_cards,
                fact_summary=fact_summary,
            ),
            metrics=metrics,
            missing_metrics=missing_metrics,
            business_overview=_research_brief_business_overview(
                report,
                fact_summary=fact_summary,
            ),
            positive_candidates=positive_candidates,
            caution_candidates=caution_candidates,
            positive_materials=positive_materials,
            caution_materials=caution_materials,
            confirmation_gaps=confirmation_gaps,
            next_actions=next_actions,
            source_cards=source_cards,
            fact_summary=fact_summary,
        )


class SecurityResearchTypeDetector:
    """Detect the research display type from provider metadata and symbol shape."""

    def detect(
        self,
        report: CompanyResearchReport,
        *,
        external_research_result: ExternalResearchFetchResult | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> SecurityResearchType:
        _load_all_service_symbols()
        symbol = report.symbol.strip()
        text = _security_research_detection_text(
            report,
            external_research_result=external_research_result,
            metadata=metadata,
        )
        quote_type = _security_research_metadata_value(text, "quoteType", "Quote Type")
        explicit_type = _security_research_metadata_value(
            text,
            "security_type",
            "Security Type",
            "product_type",
            "Product Type",
            "asset_category",
            "Asset Category",
        )
        combined_type = f"{quote_type} {explicit_type}".lower()
        if any(keyword in combined_type for keyword in ("etf", "exchange traded fund")):
            return "etf"
        if any(keyword in combined_type for keyword in ("fund", "mutual fund", "investment trust")):
            return "fund"

        exchange = _security_research_metadata_value(
            text, "exchange", "Exchange", "market", "Market"
        )
        if "equity" in combined_type or not combined_type.strip():
            if symbol.upper().endswith(".T") or _security_research_exchange_is_domestic(exchange):
                return "domestic_stock"
            if _security_research_exchange_is_foreign(exchange):
                return "foreign_stock"
            if re.fullmatch(r"[A-Z]{1,5}(?:[-.][A-Z])?", symbol.upper()):
                return "foreign_stock"
        return "unknown"


class ETFResearchSummaryBuilder:
    """Build an ETF / fund-understanding report without treating it as a company."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
    ) -> ETFResearchSummary:
        _load_all_service_symbols()
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        normalized_evidence = _company_research_normalized_evidence(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        text = _etf_research_source_text(report, external_research_result=external_research_result)
        fund_name = (
            _security_research_metadata_value(
                text,
                "longName",
                "Company Name",
                "Fund Name",
                "Name",
                "shortName",
            )
            or report.symbol
        )
        provider_name = _security_research_metadata_value(
            text,
            "fundFamily",
            "Fund Family",
            "provider",
            "Provider",
            "issuer",
            "Issuer",
        )
        investment_target = _etf_research_investment_target(text)
        asset_class = _etf_research_asset_class(text)
        region_focus = _etf_research_region_focus(text)
        sector_focus = _etf_research_sector_focus(text)
        top_holdings = _etf_research_top_holdings(text)
        benchmark_index = _etf_research_benchmark_index(text)
        expense_ratio = _etf_research_metric_value(
            "expense_ratio",
            text,
            (
                r"annual report expense ratio",
                r"annualReportExpenseRatio",
                r"expense ratio",
                r"expenseRatio",
                r"net expense ratio",
                r"経費率",
            ),
        )
        dividend_yield = _etf_research_metric_value(
            "dividend_yield",
            text,
            (
                r"trailing annual dividend yield",
                r"trailingAnnualDividendYield",
                r"dividend yield",
                r"dividendYield",
                r"\byield\b",
                r"分配金利回り",
                r"配当利回り",
            ),
        )
        aum = _etf_research_metric_value(
            "aum",
            text,
            (
                r"net assets",
                r"netAssets",
                r"total assets",
                r"totalAssets",
                r"AUM",
                r"純資産総額",
            ),
        )
        nav = _etf_research_metric_value(
            "nav",
            text,
            (
                r"NAV",
                r"nav price",
                r"navPrice",
                r"regular market price",
                r"regularMarketPrice",
                r"market price",
                r"基準価額",
            ),
        )
        per = _etf_research_metric_value(
            "per",
            text,
            (r"PER", r"trailing PE", r"forward PE", r"trailingPE", r"forwardPE"),
        )
        pbr = _etf_research_metric_value(
            "pbr",
            text,
            (r"PBR", r"price[- ]to[- ]book", r"priceToBook"),
        )
        if asset_class and asset_class != "株式":
            per = None
            pbr = None
        source_titles = _unique_text(
            [
                *[row.title for row in report.evidence if row.source_type == "provider_profile"],
                *[
                    entry.title
                    for entry in (
                        external_research_result.entries if external_research_result else []
                    )
                    if entry.source_type in {"provider_profile", "news", "tdnet"}
                ],
            ]
        )[:5]
        missing_items = _etf_research_missing_items(
            expense_ratio=expense_ratio,
            dividend_yield=dividend_yield,
            aum=aum,
            nav=nav,
            top_holdings=top_holdings,
            benchmark_index=benchmark_index,
        )
        news_items = _company_research_news_items(
            prepared_brief,
            normalized_evidence=normalized_evidence,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        return ETFResearchSummary(
            symbol=report.symbol,
            fund_name=fund_name,
            provider_name=provider_name or None,
            fund_overview=_etf_research_fund_overview(
                fund_name=fund_name,
                investment_target=investment_target,
                asset_class=asset_class,
                region_focus=region_focus,
                benchmark_index=benchmark_index,
            ),
            investment_target=investment_target,
            asset_class=asset_class,
            region_focus=region_focus,
            sector_focus=sector_focus,
            expense_ratio=expense_ratio,
            dividend_yield=dividend_yield,
            aum=aum,
            nav=nav,
            per=per,
            pbr=pbr,
            top_holdings=top_holdings,
            benchmark_index=benchmark_index,
            risk_notes=_etf_research_risk_notes(
                top_holdings=top_holdings,
                benchmark_index=benchmark_index,
                region_focus=region_focus,
                asset_class=asset_class,
                expense_ratio=expense_ratio,
                aum=aum,
                nav=nav,
            ),
            news_items=news_items,
            source_titles=source_titles,
            missing_items=missing_items,
            evidence_level=_company_research_evidence_level_from_source_types(
                [row.source_type for row in report.evidence]
            ),
        )


class CompanyResearchSummaryBuilder:
    """Build a company-understanding report from existing Research RAG outputs."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
        insight: InvestmentInsight | None = None,
    ) -> CompanyResearchSummary:
        _load_all_service_symbols()
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        prepared_insight = insight or InvestmentInsightBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
            brief=prepared_brief,
        )
        normalized_evidence = _company_research_normalized_evidence(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        overview = _company_research_overview_summary(
            report,
            prepared_brief,
            normalized_evidence=normalized_evidence,
            news_report=news_report,
        )
        quantitative = _company_research_quantitative_summary(
            prepared_brief,
            normalized_evidence=normalized_evidence,
        )
        ir_items = _company_research_ir_items(
            report,
            prepared_brief,
            normalized_evidence=normalized_evidence,
            external_research_result=external_research_result,
        )
        news_items = _company_research_news_items(
            prepared_brief,
            normalized_evidence=normalized_evidence,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        ai_notes = _company_research_ai_reading_notes(
            prepared_brief,
            prepared_insight,
            quantitative=quantitative,
            ir_items=ir_items,
            news_items=news_items,
        )
        return CompanyResearchSummary(
            symbol=report.symbol,
            overview=overview,
            quantitative=quantitative,
            ir_items=ir_items,
            news_items=news_items,
            ai_reading_notes=ai_notes,
            missing_critical_items=_company_research_missing_critical_items(
                overview,
                quantitative,
                ir_items,
                news_items,
            ),
            normalized_evidence=normalized_evidence,
        )


class InvestmentInsightBuilder:
    """Build a source-backed investment review memo without external LLM calls."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
    ) -> InvestmentInsight:
        _load_all_service_symbols()
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        positive_points = _investment_insight_positive_points(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        negative_points = _investment_insight_negative_points(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        neutral_points = _investment_insight_neutral_points(
            report,
            prepared_brief,
            external_research_result=external_research_result,
        )
        confirmation_gaps = _investment_insight_confirmation_gaps(
            report,
            prepared_brief,
            news_report=news_report,
        )
        action_hints = _investment_insight_action_hints(
            report,
            prepared_brief,
            positive_points=positive_points,
            negative_points=negative_points,
            confirmation_gaps=confirmation_gaps,
            news_report=news_report,
        )
        confidence = _investment_insight_confidence(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        status_label = _investment_insight_status_label(
            report,
            prepared_brief,
            positive_points=positive_points,
            negative_points=negative_points,
            news_report=news_report,
        )
        confidence_label = _investment_insight_confidence_label(status_label, confidence)
        primary_action_label = _investment_insight_primary_action_label(status_label)
        display_positive_points = positive_points[:3]
        display_negative_points = negative_points[:3]
        display_confirmation_gaps = confirmation_gaps[:3]
        return InvestmentInsight(
            symbol=report.symbol,
            as_of=report.as_of,
            headline=_investment_insight_headline(
                positive_points=positive_points,
                negative_points=negative_points,
                neutral_points=neutral_points,
                confirmation_gaps=confirmation_gaps,
            ),
            short_summary=_investment_insight_short_summary(
                report,
                prepared_brief,
                positive_points=positive_points,
                negative_points=negative_points,
                neutral_points=neutral_points,
                confirmation_gaps=confirmation_gaps,
                action_hints=action_hints,
                confidence=confidence,
                status_label=status_label,
            ),
            status_label=status_label,
            confidence_label=confidence_label,
            primary_action_label=primary_action_label,
            positive_points=display_positive_points,
            negative_points=display_negative_points,
            neutral_points=neutral_points,
            confirmation_gaps=display_confirmation_gaps,
            action_hints=action_hints,
            confidence=confidence,
        )


class InvestmentQuestionSummaryBuilder:
    """Build fixed investor questions from source-backed Research facts."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
        insight: InvestmentInsight | None = None,
    ) -> InvestmentQuestionSummary:
        _load_all_service_symbols()
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        prepared_insight = insight or InvestmentInsightBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
            brief=prepared_brief,
        )
        answers = [
            _investment_question_answer(
                category,
                report,
                prepared_brief,
                prepared_insight,
                news_report=news_report,
                external_research_result=external_research_result,
            )
            for category, _ in _INVESTMENT_QUESTION_SPECS
        ]
        top_takeaway = next(
            (
                answer.answer
                for answer in answers
                if answer.category == "key_takeaway" and answer.answer.strip()
            ),
            "",
        )
        return InvestmentQuestionSummary(
            symbol=report.symbol,
            answers=answers,
            top_takeaway=top_takeaway,
            missing_critical_items=_investment_question_missing_critical_items(
                prepared_brief,
                answers,
            ),
        )


class ResearchPageViewModelBuilder:
    """Build the top-level Research page model for company, foreign stock, or ETF views."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
        insight: InvestmentInsight | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ResearchPageViewModel:
        _load_all_service_symbols()
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        prepared_insight = insight or InvestmentInsightBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
            brief=prepared_brief,
        )
        security_type = SecurityResearchTypeDetector().detect(
            report,
            external_research_result=external_research_result,
            metadata=metadata,
        )
        if security_type in {"etf", "fund"}:
            return ResearchPageViewModel(
                symbol=report.symbol,
                security_type=security_type,
                etf_summary=ETFResearchSummaryBuilder().build(
                    report,
                    news_report=news_report,
                    external_research_result=external_research_result,
                    brief=prepared_brief,
                ),
            )
        return ResearchPageViewModel(
            symbol=report.symbol,
            security_type=security_type,
            company_summary=CompanyResearchSummaryBuilder().build(
                report,
                news_report=news_report,
                external_research_result=external_research_result,
                brief=prepared_brief,
                insight=prepared_insight,
            ),
            question_summary=InvestmentQuestionSummaryBuilder().build(
                report,
                news_report=news_report,
                external_research_result=external_research_result,
                brief=prepared_brief,
                insight=prepared_insight,
            ),
        )
