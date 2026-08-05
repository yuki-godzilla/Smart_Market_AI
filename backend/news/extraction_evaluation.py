"""Labelled, network-free evaluation for Investment News symbol extraction."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from backend.news.sources import (
    NewsCategoryQuery,
    NewsSymbolExtractionResult,
    extract_news_symbols,
)


@dataclass(frozen=True)
class NewsSymbolExtractionEvaluationCase:
    """One held-out headline and its human-labelled symbol expectations."""

    case_id: str
    text: str
    category_query: NewsCategoryQuery
    expected_direct_symbols: tuple[str, ...] = ()
    expected_inferred_symbols: tuple[str, ...] = ()
    expected_macro_proxy_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewsSymbolExtractionMetric:
    """Set-based precision and recall for one extraction provenance."""

    expected_count: int
    selected_count: int
    correct_count: int

    @property
    def precision(self) -> float:
        if self.selected_count == 0:
            return 1.0 if self.expected_count == 0 else 0.0
        return self.correct_count / self.selected_count

    @property
    def recall(self) -> float:
        if self.expected_count == 0:
            return 1.0
        return self.correct_count / self.expected_count

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 0.0 if denominator == 0 else 2 * self.precision * self.recall / denominator


@dataclass(frozen=True)
class NewsSymbolExtractionCaseResult:
    case_id: str
    extraction: NewsSymbolExtractionResult
    missing_direct_symbols: tuple[str, ...]
    unexpected_direct_symbols: tuple[str, ...]
    missing_inferred_symbols: tuple[str, ...]
    unexpected_inferred_symbols: tuple[str, ...]
    missing_macro_proxy_symbols: tuple[str, ...]
    unexpected_macro_proxy_symbols: tuple[str, ...]


@dataclass(frozen=True)
class NewsSymbolExtractionEvaluationReport:
    """Aggregate metrics plus per-case errors for review before a rule ships."""

    case_results: tuple[NewsSymbolExtractionCaseResult, ...]
    direct_metric: NewsSymbolExtractionMetric
    inferred_metric: NewsSymbolExtractionMetric
    macro_proxy_metric: NewsSymbolExtractionMetric

    @property
    def case_count(self) -> int:
        return len(self.case_results)


def evaluate_news_symbol_extraction(
    cases: Sequence[NewsSymbolExtractionEvaluationCase],
) -> NewsSymbolExtractionEvaluationReport:
    """Run the production extractor against human-labelled, offline examples."""

    result_rows: list[NewsSymbolExtractionCaseResult] = []
    counters = {
        "direct": Counter(expected=0, selected=0, correct=0),
        "inferred": Counter(expected=0, selected=0, correct=0),
        "macro": Counter(expected=0, selected=0, correct=0),
    }
    for case in cases:
        extraction = extract_news_symbols(case.text, case.category_query)
        expected_direct = _symbol_set(case.expected_direct_symbols)
        expected_inferred = _symbol_set(case.expected_inferred_symbols)
        expected_macro = _symbol_set(case.expected_macro_proxy_symbols)
        selected_direct = _symbol_set(extraction.related_symbols)
        selected_inferred = _symbol_set(extraction.inferred_symbols)
        selected_macro = _symbol_set(extraction.macro_proxy_symbols)
        _update_counter(counters["direct"], expected_direct, selected_direct)
        _update_counter(counters["inferred"], expected_inferred, selected_inferred)
        _update_counter(counters["macro"], expected_macro, selected_macro)
        result_rows.append(
            NewsSymbolExtractionCaseResult(
                case_id=case.case_id,
                extraction=extraction,
                missing_direct_symbols=tuple(sorted(expected_direct - selected_direct)),
                unexpected_direct_symbols=tuple(sorted(selected_direct - expected_direct)),
                missing_inferred_symbols=tuple(sorted(expected_inferred - selected_inferred)),
                unexpected_inferred_symbols=tuple(sorted(selected_inferred - expected_inferred)),
                missing_macro_proxy_symbols=tuple(sorted(expected_macro - selected_macro)),
                unexpected_macro_proxy_symbols=tuple(sorted(selected_macro - expected_macro)),
            )
        )
    return NewsSymbolExtractionEvaluationReport(
        case_results=tuple(result_rows),
        direct_metric=_metric_from_counter(counters["direct"]),
        inferred_metric=_metric_from_counter(counters["inferred"]),
        macro_proxy_metric=_metric_from_counter(counters["macro"]),
    )


def _symbol_set(symbols: Iterable[str]) -> set[str]:
    return {symbol.strip().upper() for symbol in symbols if symbol.strip()}


def _update_counter(counter: Counter[str], expected: set[str], selected: set[str]) -> None:
    counter["expected"] += len(expected)
    counter["selected"] += len(selected)
    counter["correct"] += len(expected & selected)


def _metric_from_counter(counter: Counter[str]) -> NewsSymbolExtractionMetric:
    return NewsSymbolExtractionMetric(
        expected_count=counter["expected"],
        selected_count=counter["selected"],
        correct_count=counter["correct"],
    )
