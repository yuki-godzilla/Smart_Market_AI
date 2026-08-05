from __future__ import annotations

from backend.news import (
    NewsCategoryQuery,
    NewsSymbolExtractionEvaluationCase,
    evaluate_news_symbol_extraction,
)


def _query(category: str = "個別企業") -> NewsCategoryQuery:
    return NewsCategoryQuery(
        category=category,
        region="グローバル",
        material_type="theme",
        query=category,
    )


def test_labelled_symbol_extraction_holdout_covers_tickers_names_categories_and_macro():
    report = evaluate_news_symbol_extraction(
        [
            NewsSymbolExtractionEvaluationCase(
                case_id="company-name-us",
                text="Tesla は新型EVの生産計画を発表した。",
                category_query=_query(),
                expected_direct_symbols=("TSLA",),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="explicit-dollar-ticker",
                text="$TSLA の会社発表を確認する。",
                category_query=_query(),
                expected_direct_symbols=("TSLA",),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="explicit-exchange-ticker",
                text="NYSE: KO の会社発表を確認する。",
                category_query=_query(),
                expected_direct_symbols=("KO",),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="jp-bracket-code",
                text="【4063】の会社発表を確認。",
                category_query=_query(),
                expected_direct_symbols=("4063.T",),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="jp-exchange-code",
                text="東証: 4502 の薬価影響を確認。",
                category_query=_query(),
                expected_direct_symbols=("4502.T",),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="jp-company-name",
                text="富士通は企業向けAI基盤を強化する。",
                category_query=_query(),
                expected_direct_symbols=("6702.T",),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="numeric-false-positive-guard",
                text="市場は2026年の見通しを注視している。",
                category_query=_query(),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="reit-category",
                text="オフィス賃料とREIT市場の動向を確認する。",
                category_query=_query("不動産・REIT"),
                expected_inferred_symbols=("1488.T", "8801.T", "8802.T"),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="telecom-category",
                text="5Gと広告プラットフォームをめぐる通信業界の材料。",
                category_query=_query("通信・メディア"),
                expected_inferred_symbols=("9432.T", "9984.T", "GOOGL", "META"),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="industrials-category",
                text="航空宇宙と設備投資の受注動向。",
                category_query=_query("工業・資本財"),
                expected_inferred_symbols=("7011.T", "6301.T", "6503.T"),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="healthcare-category",
                text="医薬品の臨床試験と薬価改定を確認。",
                category_query=_query("ヘルスケア"),
                expected_inferred_symbols=("4502.T", "4568.T", "JNJ"),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="materials-category",
                text="化学素材の需要を確認。",
                category_query=_query("素材・化学"),
                expected_inferred_symbols=("4063.T", "5706.T", "5108.T"),
            ),
            NewsSymbolExtractionEvaluationCase(
                case_id="macro-proxy",
                text="米国株はFRBの金利見通しと原油価格を注視している。",
                category_query=_query("地政学・マクロリスク"),
                expected_inferred_symbols=("XLE", "XOM", "CVX", "1605.T"),
                expected_macro_proxy_symbols=("TLT", "SPY", "QQQ", "USDJPY", "US10Y"),
            ),
        ]
    )

    assert report.case_count == 13
    assert report.direct_metric.precision == 1.0
    assert report.direct_metric.recall == 1.0
    assert report.inferred_metric.precision == 1.0
    assert report.inferred_metric.recall == 1.0
    assert report.macro_proxy_metric.precision == 1.0
    assert report.macro_proxy_metric.recall == 1.0
    assert all(
        not (
            case.missing_direct_symbols
            or case.unexpected_direct_symbols
            or case.missing_inferred_symbols
            or case.unexpected_inferred_symbols
            or case.missing_macro_proxy_symbols
            or case.unexpected_macro_proxy_symbols
        )
        for case in report.case_results
    )
