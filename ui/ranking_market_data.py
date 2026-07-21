"""Streamlit-independent MarketData acquisition stage for Ranking builds."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from backend.core.data_contracts import (
    Bar,
    DailySnapshot,
    DataQuality,
    FeatureSnapshot,
    FundamentalSnapshot,
    Quote,
)
from backend.forecast.service import ForecastConsensus

RankingRow = dict[str, str]
RankingProgressReporter = Callable[[Callable[[str, float], None] | None, str, float], None]
OhlcvFetcher = Callable[..., Awaitable[tuple[list[Bar], list[RankingRow], set[str]]]]
FxRateFetcher = Callable[[Any, set[str]], Awaitable[dict[str, Any]]]
BarsDisplayMapper = Callable[..., list[Bar]]
BarsBySymbolBuilder = Callable[[list[str], list[Bar]], dict[str, list[Bar]]]
CurrencyBySymbolBuilder = Callable[[dict[str, list[Bar]]], dict[str, str]]
ErrorRowBuilder = Callable[..., RankingRow]
FundamentalsFetcher = Callable[..., Awaitable[tuple[list[FundamentalSnapshot], list[RankingRow]]]]
FundamentalsDisplayMapper = Callable[..., list[FundamentalSnapshot]]
FeatureRowsBuilder = Callable[..., list[DailySnapshot]]
MissingSummaryBuilder = Callable[[list[DailySnapshot]], dict[str, int]]
QualitySummaryBuilder = Callable[[list[DailySnapshot]], dict[DataQuality, int]]
ForecastEvaluationBuilder = Callable[..., list[Any]]
ForecastConsensusBuilder = Callable[..., ForecastConsensus | None]
ScreeningScorer = Callable[..., list[Any]]
InvestmentScorer = Callable[..., list[Any]]
InvestmentRowsBuilder = Callable[[list[Any]], list[RankingRow]]
FeatureDetailEnricher = Callable[..., list[RankingRow]]
AdvancedForecastEnricher = Callable[[list[RankingRow], dict[str, dict[str, str]]], list[RankingRow]]
RankingRowsSorter = Callable[[list[RankingRow]], list[RankingRow]]
LatestVolumeBuilder = Callable[[Mapping[str, list[Bar]]], dict[str, str]]


@dataclass(frozen=True)
class RankingMarketDataInputs:
    """Fetched inputs needed by the feature and score stages of one Ranking build."""

    bars: list[Bar]
    bars_by_symbol: dict[str, list[Bar]]
    quotes: list[Quote]
    available_symbols: list[str]
    error_rows: list[RankingRow]
    source_currency_by_symbol: dict[str, str]
    jpy_fx_rates: dict[str, Any]
    usd_jpy_rate: Any | None


@dataclass(frozen=True)
class RankingFundamentalInputs:
    """Fundamentals and non-fatal fetch errors for usable Ranking symbols."""

    fundamentals: list[FundamentalSnapshot]
    error_rows: list[RankingRow]


@dataclass(frozen=True)
class RankingFeatureInputs:
    """Feature rows and their immutable snapshot for the Ranking score stage."""

    feature_rows: list[DailySnapshot]
    feature_snapshot: FeatureSnapshot
    provider_name: str


@dataclass(frozen=True)
class RankingForecastInputs:
    """Point-in-time Forecast consensus values used by Ranking scoring."""

    horizon_days: int
    consensus_by_symbol: dict[str, ForecastConsensus]


@dataclass(frozen=True)
class RankingScoreInputs:
    """Deterministic Screening and Investment Score outputs before UI enrichment."""

    screening_scores: list[Any]
    investment_scores: list[Any]
    score_rows: list[RankingRow]


@dataclass(frozen=True)
class RankingPresentationInputs:
    """Fully enriched and sorted rows returned by a Ranking build."""

    ranked_rows: list[RankingRow]


async def acquire_ranking_market_data_inputs(
    symbols: list[str],
    *,
    provider: str,
    start: date,
    end: date,
    adapter: Any,
    feature_start: datetime,
    fetch_end: datetime,
    provider_symbols_by_symbol: Mapping[str, str],
    symbol_chunks: Sequence[list[str]],
    display_symbols_by_provider_symbol: Mapping[str, list[str]],
    fetch_ohlcv: OhlcvFetcher,
    bars_with_display_symbols: BarsDisplayMapper,
    bars_by_symbol_builder: BarsBySymbolBuilder,
    currency_by_symbol_builder: CurrencyBySymbolBuilder,
    fetch_jpy_fx_rates: FxRateFetcher,
    no_bars_error_row: ErrorRowBuilder,
    insufficient_bars_error_row: ErrorRowBuilder,
    report_progress: RankingProgressReporter,
    progress_callback: Callable[[str, float], None] | None,
) -> RankingMarketDataInputs:
    """Fetch price inputs, preserve per-symbol errors, and prepare usable quotes.

    All provider/cache behavior remains injected at this edge. The returned
    contract contains no Streamlit state and is sufficient for the downstream
    feature, forecast, and score assembly stages.
    """

    bars: list[Bar] = []
    error_rows: list[RankingRow] = []
    provider_fetch_error_symbols: set[str] = set()
    for index, symbol_chunk in enumerate(symbol_chunks, start=1):
        report_progress(
            progress_callback,
            f"価格データをまとめて取得しています ({index}/{len(symbol_chunks)})。",
            0.1 + (0.35 * (index - 1) / len(symbol_chunks)),
        )
        chunk_bars, chunk_errors, chunk_failed_symbols = await fetch_ohlcv(
            adapter,
            symbol_chunk,
            provider=provider,
            start=feature_start,
            end=fetch_end,
            display_symbols_by_provider_symbol=display_symbols_by_provider_symbol,
        )
        bars.extend(chunk_bars)
        error_rows.extend(chunk_errors)
        provider_fetch_error_symbols.update(chunk_failed_symbols)

    bars = bars_with_display_symbols(
        bars,
        provider_symbols_by_symbol=dict(provider_symbols_by_symbol),
    )
    report_progress(progress_callback, "価格データを整理しています。", 0.45)
    bars_by_symbol = bars_by_symbol_builder(symbols, bars)
    source_currency_by_symbol = currency_by_symbol_builder(bars_by_symbol)
    source_currencies = {
        currency or ("JPY" if symbol.endswith(".T") else "USD")
        for symbol, currency in source_currency_by_symbol.items()
    }
    jpy_fx_rates = await fetch_jpy_fx_rates(adapter, source_currencies)

    available_symbols: list[str] = []
    quotes: list[Quote] = []
    for symbol in symbols:
        symbol_bars = bars_by_symbol[symbol]
        if not symbol_bars:
            if symbol not in provider_fetch_error_symbols:
                error_rows.append(
                    no_bars_error_row(
                        provider=provider,
                        symbol=symbol,
                        display_start=start,
                        display_end=end,
                        fetch_start=feature_start,
                        fetch_end=fetch_end,
                    )
                )
            continue
        if len(symbol_bars) < 2:
            error_rows.append(
                insufficient_bars_error_row(
                    provider=provider,
                    symbol=symbol,
                    bar_count=len(symbol_bars),
                    display_start=start,
                    display_end=end,
                )
            )
            continue
        latest = symbol_bars[-1]
        available_symbols.append(symbol)
        quotes.append(
            Quote(
                symbol=latest.symbol,
                bid=None,
                ask=None,
                last=latest.close,
                ts=latest.ts,
            )
        )

    return RankingMarketDataInputs(
        bars=bars,
        bars_by_symbol=bars_by_symbol,
        quotes=quotes,
        available_symbols=available_symbols,
        error_rows=error_rows,
        source_currency_by_symbol=source_currency_by_symbol,
        jpy_fx_rates=jpy_fx_rates,
        usd_jpy_rate=jpy_fx_rates.get("USD"),
    )


async def acquire_ranking_fundamental_inputs(
    symbols: list[str],
    *,
    provider: str,
    as_of: date,
    adapter: Any,
    provider_symbols_by_symbol: Mapping[str, str],
    display_symbols_by_provider_symbol: Mapping[str, list[str]],
    fetch_fundamentals: FundamentalsFetcher,
    fundamentals_with_display_symbols: FundamentalsDisplayMapper,
) -> RankingFundamentalInputs:
    """Fetch and restore fundamentals without coupling the score stage to a provider."""

    provider_symbols = [provider_symbols_by_symbol[symbol] for symbol in symbols]
    provider_fundamentals, error_rows = await fetch_fundamentals(
        adapter,
        provider_symbols,
        provider=provider,
        as_of=as_of,
        display_symbols_by_provider_symbol=display_symbols_by_provider_symbol,
    )
    fundamentals = fundamentals_with_display_symbols(
        provider_fundamentals,
        provider_symbols_by_symbol={
            symbol: provider_symbols_by_symbol[symbol] for symbol in symbols
        },
    )
    return RankingFundamentalInputs(fundamentals=fundamentals, error_rows=error_rows)


def build_ranking_feature_inputs(
    symbols: list[str],
    *,
    as_of: date,
    adapter: Any,
    provider: str,
    quotes: list[Quote],
    fundamentals: list[FundamentalSnapshot],
    bars: list[Bar],
    feature_builder_config: Any,
    build_feature_rows: FeatureRowsBuilder,
    build_missing_summary: MissingSummaryBuilder,
    build_quality_summary: QualitySummaryBuilder,
) -> RankingFeatureInputs:
    """Build the deterministic FeatureSnapshot used by Ranking scoring."""

    feature_rows = build_feature_rows(
        symbols=symbols,
        as_of=as_of,
        quotes=quotes,
        fundamentals=fundamentals,
        bars=bars,
        cfg=feature_builder_config,
    )
    provider_name = adapter.healthcheck().get("provider", provider)
    feature_snapshot = FeatureSnapshot(
        as_of=as_of,
        provider=provider_name,
        rows=feature_rows,
        missing_summary=build_missing_summary(feature_rows),
        quality_summary=build_quality_summary(feature_rows),
    )
    return RankingFeatureInputs(
        feature_rows=feature_rows,
        feature_snapshot=feature_snapshot,
        provider_name=provider_name,
    )


def build_ranking_forecast_inputs(
    symbols: list[str],
    *,
    bars_by_symbol: Mapping[str, list[Bar]],
    horizon_days: int,
    build_evaluations: ForecastEvaluationBuilder,
    summarize_consensus: ForecastConsensusBuilder,
    report_progress: RankingProgressReporter,
    progress_callback: Callable[[str, float], None] | None,
) -> RankingForecastInputs:
    """Create the existing deterministic consensus once for each usable symbol."""

    consensus_by_symbol: dict[str, ForecastConsensus] = {}
    for index, symbol in enumerate(symbols, start=1):
        history = bars_by_symbol[symbol]
        consensus = summarize_consensus(
            build_evaluations(history, horizon_days=horizon_days),
            history=history,
        )
        if consensus is not None:
            consensus_by_symbol[consensus.symbol] = consensus
        if index != 1 and index % 10 != 0 and index != len(symbols):
            continue
        progress = 0.65 + (0.05 * index / len(symbols))
        report_progress(
            progress_callback,
            f"基本予測を計算しています ({index}/{len(symbols)})。",
            progress,
        )
    return RankingForecastInputs(
        horizon_days=horizon_days,
        consensus_by_symbol=consensus_by_symbol,
    )


def build_ranking_score_inputs(
    feature_snapshot: FeatureSnapshot,
    *,
    forecast_consensus_by_symbol: Mapping[str, ForecastConsensus],
    score_screening: ScreeningScorer,
    score_investment: InvestmentScorer,
    build_investment_rows: InvestmentRowsBuilder,
) -> RankingScoreInputs:
    """Run the existing deterministic score services before display enrichment."""

    screening_scores = score_screening(
        feature_snapshot,
        forecast_consensus_by_symbol=forecast_consensus_by_symbol,
    )
    investment_scores = score_investment(
        screening_scores,
        forecast_consensus_by_symbol=forecast_consensus_by_symbol,
    )
    return RankingScoreInputs(
        screening_scores=screening_scores,
        investment_scores=investment_scores,
        score_rows=build_investment_rows(investment_scores),
    )


def build_ranking_presentation_inputs(
    score_rows: list[RankingRow],
    *,
    feature_rows: list[DailySnapshot],
    bars_by_symbol: Mapping[str, list[Bar]],
    source_currency_by_symbol: Mapping[str, str],
    usd_jpy_rate: Any | None,
    jpy_fx_rates: Mapping[str, Any],
    provider_name: str,
    advanced_forecast_fields_by_symbol: dict[str, dict[str, str]],
    enrich_feature_details: FeatureDetailEnricher,
    enrich_advanced_forecast: AdvancedForecastEnricher,
    build_latest_volume: LatestVolumeBuilder,
    sort_rows: RankingRowsSorter,
) -> RankingPresentationInputs:
    """Enrich base score rows for display and apply the established final order."""

    enriched_rows = enrich_feature_details(
        score_rows,
        feature_rows,
        latest_volume_by_symbol=build_latest_volume(bars_by_symbol),
        source_currency_by_symbol=source_currency_by_symbol,
        usd_jpy_rate=usd_jpy_rate,
        jpy_fx_rates=jpy_fx_rates,
        provider_name=provider_name,
    )
    enriched_rows = enrich_advanced_forecast(
        enriched_rows,
        advanced_forecast_fields_by_symbol,
    )
    return RankingPresentationInputs(ranked_rows=sort_rows(enriched_rows))
