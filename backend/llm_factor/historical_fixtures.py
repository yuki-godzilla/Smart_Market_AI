from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta

from backend.llm_factor.backtest_contracts import (
    LLMFactorBacktestSignal,
    LLMFactorPriceBar,
)
from backend.llm_factor.validation_contracts import (
    LLMFactorBaselineScore,
    LLMFactorFixtureManifest,
    LLMFactorHistoricalFixturePack,
)

DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_ID = "llm-factor-broader-historical-v1"
DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_VERSION = "2026-06-12"

_FIXTURE_START_DATE = date(2025, 1, 6)
_SIGNAL_DATE_COUNT = 8
_SIGNAL_DATE_STEP_DAYS = 35
_PRICE_BAR_DAYS = 23

_SYMBOL_BLUEPRINTS: tuple[tuple[str, str, str, str, str], ...] = (
    ("7203.T", "JP", "large_cap", "high", "jp_large_cap"),
    ("6758.T", "JP", "large_cap", "high", "jp_large_cap"),
    ("8306.T", "JP", "large_cap", "high", "jp_large_cap"),
    ("9432.T", "JP", "large_cap", "medium", "jp_large_cap"),
    ("9984.T", "JP", "large_cap", "high", "jp_large_cap"),
    ("AAPL", "US", "large_cap", "high", "us_large_cap"),
    ("MSFT", "US", "large_cap", "high", "us_large_cap"),
    ("NVDA", "US", "growth", "high", "us_large_cap"),
    ("AMZN", "US", "growth", "high", "us_large_cap"),
    ("GOOGL", "US", "large_cap", "high", "us_large_cap"),
    ("1306.T", "ETF", "etf", "medium", "etf"),
    ("2558.T", "ETF", "etf", "medium", "etf"),
    ("SPY", "ETF", "etf", "high", "etf"),
    ("VOO", "ETF", "etf", "high", "etf"),
    ("QQQ", "ETF", "etf", "high", "etf"),
    ("2914.T", "JP", "high_dividend", "medium", "high_dividend"),
    ("8058.T", "JP", "high_dividend", "high", "high_dividend"),
    ("9434.T", "JP", "high_dividend", "medium", "high_dividend"),
    ("VZ", "US", "high_dividend", "medium", "high_dividend"),
    ("T", "US", "high_dividend", "medium", "high_dividend"),
    ("4485.T", "JP", "growth", "medium", "growth"),
    ("3697.T", "JP", "growth", "medium", "growth"),
    ("TSLA", "US", "growth", "high", "growth"),
    ("SHOP", "US", "growth", "high", "growth"),
    ("SNOW", "US", "growth", "high", "growth"),
    ("9991.T", "JP", "small_like", "low", "low_news_coverage"),
    ("9992.T", "JP", "small_like", "low", "low_news_coverage"),
    ("LOWN1", "US", "small_like", "low", "low_news_coverage"),
    ("LOWN2", "US", "small_like", "low", "low_news_coverage"),
    ("LOWN3", "US", "small_like", "low", "low_news_coverage"),
    ("9532.T", "JP", "utility", "medium", "osaka_gas_9532_t"),
    ("9531.T", "JP", "utility", "medium", "osaka_gas_9532_t"),
    ("9502.T", "JP", "utility", "medium", "osaka_gas_9532_t"),
    ("9503.T", "JP", "utility", "medium", "osaka_gas_9532_t"),
    ("9513.T", "JP", "utility", "medium", "osaka_gas_9532_t"),
)


def load_llm_factor_historical_fixture_pack(
    fixture_id: str = DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_ID,
) -> LLMFactorHistoricalFixturePack:
    """Load the deterministic broader fixture pack used by validation tests."""

    if fixture_id != DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_ID:
        raise ValueError(f"Unknown LLM Factor historical fixture pack: {fixture_id}")
    return build_llm_factor_historical_fixture_pack()


def build_llm_factor_historical_fixture_pack() -> LLMFactorHistoricalFixturePack:
    signals: list[LLMFactorBacktestSignal] = []
    prices: list[LLMFactorPriceBar] = []
    baseline_scores: list[LLMFactorBaselineScore] = []
    symbol_segments = _symbol_segments()
    signal_dates = [
        _FIXTURE_START_DATE + timedelta(days=_SIGNAL_DATE_STEP_DAYS * index)
        for index in range(_SIGNAL_DATE_COUNT)
    ]
    for symbol_index, (symbol, market, style, news_coverage, symbol_group) in enumerate(
        _SYMBOL_BLUEPRINTS
    ):
        for date_index, signal_date in enumerate(signal_dates):
            signal = _signal_for_blueprint(
                symbol=symbol,
                market=market,
                style=style,
                news_coverage=news_coverage,
                symbol_group=symbol_group,
                symbol_index=symbol_index,
                date_index=date_index,
                signal_date=signal_date,
            )
            returns = _fixture_returns(
                signal=signal,
                symbol=symbol,
                style=style,
                news_coverage=news_coverage,
                symbol_group=symbol_group,
                date_index=date_index,
            )
            signals.append(signal)
            prices.extend(
                _price_path(
                    symbol=symbol,
                    signal_date=signal_date,
                    symbol_index=symbol_index,
                    return_1d=returns["1d"],
                    return_5d=returns["5d"],
                    return_20d=returns["20d"],
                    drawdown=returns["drawdown"],
                )
            )
            baseline_scores.extend(_baseline_scores(signal, returns))
    manifest = _manifest(
        signals=signals,
        prices=prices,
        baseline_scores=baseline_scores,
        symbol_segments=symbol_segments,
    )
    return LLMFactorHistoricalFixturePack(
        fixture_id=DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_ID,
        version=DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_VERSION,
        description=(
            "Deterministic validation fixture for SMAI LLM Factor metrics. "
            "It is synthetic/static and does not represent live market, news, or LLM output."
        ),
        signals=signals,
        prices=prices,
        baseline_scores=baseline_scores,
        manifest=manifest,
        symbol_segments=symbol_segments,
    )


def _symbol_segments() -> dict[str, dict[str, str]]:
    return {
        symbol: {
            "market": market,
            "style": style,
            "news_coverage": news_coverage,
            "symbol_group": symbol_group,
            "fixture_pack": "mixed_global",
        }
        for symbol, market, style, news_coverage, symbol_group in _SYMBOL_BLUEPRINTS
    }


def _signal_for_blueprint(
    *,
    symbol: str,
    market: str,
    style: str,
    news_coverage: str,
    symbol_group: str,
    symbol_index: int,
    date_index: int,
    signal_date: date,
) -> LLMFactorBacktestSignal:
    latent = _deterministic_noise(symbol, date_index, scale=1.0)
    cycle = ((date_index % 4) - 1.5) / 4
    bullish: float
    bearish: float
    catalyst: float
    risk: float
    confidence: float
    evidence_quality: float
    freshness: float
    source_count: int
    if symbol_group == "osaka_gas_9532_t":
        bullish = 48 + 8 * latent + 2 * cycle
        bearish = 38 - 5 * latent
        catalyst = 35 + 8 * abs(cycle)
        risk = 35 + 18 * _positive_noise(symbol, date_index, "risk")
        confidence = 72
        evidence_quality = 70
        freshness = 68
        source_count = 2
    elif symbol_group == "low_news_coverage":
        bullish = 42 + 25 * latent
        bearish = 40 - 20 * latent
        catalyst = 35 + 20 * abs(latent)
        risk = 45 + 20 * _positive_noise(symbol, date_index, "risk")
        confidence = 24 + 8 * _positive_noise(symbol, date_index, "confidence")
        evidence_quality = 22 + 10 * _positive_noise(symbol, date_index, "quality")
        freshness = 25 + 10 * _positive_noise(symbol, date_index, "freshness")
        source_count = 0 if date_index % 2 == 0 else 1
    elif style == "growth":
        bullish = 52 + 34 * latent + 8 * cycle
        bearish = 36 - 18 * latent + 12 * _positive_noise(symbol, date_index, "bear")
        catalyst = 62 + 28 * _positive_noise(symbol, date_index, "cat")
        risk = 42 + 35 * _positive_noise(symbol, date_index, "risk")
        confidence = 66 + 20 * _positive_noise(symbol, date_index, "confidence")
        evidence_quality = 62 + 18 * _positive_noise(symbol, date_index, "quality")
        freshness = 70 + 20 * _positive_noise(symbol, date_index, "freshness")
        source_count = 3
    elif style == "high_dividend":
        bullish = 58 + 18 * latent
        bearish = 32 - 12 * latent
        catalyst = 45 + 12 * _positive_noise(symbol, date_index, "cat")
        risk = 28 + 15 * _positive_noise(symbol, date_index, "risk")
        confidence = 74
        evidence_quality = 76
        freshness = 70
        source_count = 3
    elif style == "etf":
        bullish = 50 + 12 * latent
        bearish = 42 - 8 * latent
        catalyst = 38 + 10 * _positive_noise(symbol, date_index, "cat")
        risk = 30 + 12 * _positive_noise(symbol, date_index, "risk")
        confidence = 62
        evidence_quality = 60
        freshness = 65
        source_count = 2
    elif market == "US":
        bullish = 50 + 30 * latent + 5 * cycle
        bearish = 38 - 22 * latent
        catalyst = 55 + 25 * _positive_noise(symbol, date_index, "cat")
        risk = 35 + 25 * _positive_noise(symbol, date_index, "risk")
        confidence = 72
        evidence_quality = 75
        freshness = 80
        source_count = 4
    else:
        bullish = 50 + 28 * latent + 4 * cycle
        bearish = 36 - 20 * latent
        catalyst = 50 + 18 * _positive_noise(symbol, date_index, "cat")
        risk = 32 + 20 * _positive_noise(symbol, date_index, "risk")
        confidence = 70
        evidence_quality = 72
        freshness = 76
        source_count = 3
    return LLMFactorBacktestSignal(
        symbol=symbol,
        signal_date=signal_date,
        available_at=datetime.combine(signal_date, datetime.min.time(), tzinfo=UTC),
        bullish_score=_clamp_score(bullish),
        bearish_score=_clamp_score(bearish),
        catalyst_score=_clamp_score(catalyst),
        risk_score=_clamp_score(risk),
        confidence_score=_clamp_score(confidence),
        evidence_quality_score=_clamp_score(evidence_quality),
        freshness_score=_clamp_score(freshness),
        source_count=source_count,
        llm_factor_result_id=f"{DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_ID}:{symbol}:{date_index}",
    )


def _fixture_returns(
    *,
    signal: LLMFactorBacktestSignal,
    symbol: str,
    style: str,
    news_coverage: str,
    symbol_group: str,
    date_index: int,
) -> dict[str, float]:
    net = (signal.bullish_score - signal.bearish_score) / 100
    catalyst = signal.catalyst_score / 100
    risk = signal.risk_score / 100
    noise = _deterministic_noise(symbol, date_index, scale=0.01)
    if symbol_group == "low_news_coverage":
        base = _deterministic_noise(symbol, date_index, "return", scale=0.018)
        return {
            "1d": base * 0.4,
            "5d": base * 0.8,
            "20d": base,
            "drawdown": -0.04 - risk * 0.04,
        }
    if symbol_group == "osaka_gas_9532_t":
        return {
            "1d": 0.004 * net + noise * 0.2,
            "5d": 0.010 * net + noise * 0.3,
            "20d": 0.018 * net + noise * 0.4,
            "drawdown": -0.015 - risk * 0.055,
        }
    if style == "growth":
        dispersion = _deterministic_noise(symbol, date_index, "dispersion", scale=0.045)
        return {
            "1d": 0.020 * net + 0.008 * catalyst + dispersion * 0.35,
            "5d": 0.055 * net + 0.020 * catalyst + dispersion * 0.65,
            "20d": 0.100 * net + 0.035 * catalyst + dispersion,
            "drawdown": -0.035 - risk * 0.12 - abs(dispersion) * 0.4,
        }
    if style == "high_dividend":
        return {
            "1d": 0.004 * net + noise * 0.2,
            "5d": 0.010 * net + noise * 0.3,
            "20d": 0.018 * net + noise * 0.4,
            "drawdown": -0.012 - risk * 0.035,
        }
    if style == "etf":
        return {
            "1d": 0.003 * net + noise * 0.2,
            "5d": 0.007 * net + noise * 0.3,
            "20d": 0.012 * net + noise * 0.4,
            "drawdown": -0.018 - risk * 0.035,
        }
    if news_coverage == "high":
        return {
            "1d": 0.015 * net + noise * 0.3,
            "5d": 0.035 * net + noise * 0.6,
            "20d": 0.060 * net + 0.012 * catalyst + noise,
            "drawdown": -0.020 - risk * 0.065,
        }
    return {
        "1d": 0.012 * net + noise * 0.3,
        "5d": 0.028 * net + noise * 0.6,
        "20d": 0.050 * net + 0.010 * catalyst + noise,
        "drawdown": -0.018 - risk * 0.055,
    }


def _price_path(
    *,
    symbol: str,
    signal_date: date,
    symbol_index: int,
    return_1d: float,
    return_5d: float,
    return_20d: float,
    drawdown: float,
) -> list[LLMFactorPriceBar]:
    entry_price = 100.0 + symbol_index
    anchors = {
        0: entry_price,
        1: entry_price,
        2: entry_price * (1 + max(return_1d, -0.8)),
        6: entry_price * (1 + max(return_5d, -0.8)),
        21: entry_price * (1 + max(return_20d, -0.8)),
        22: entry_price * (1 + max(return_20d, -0.8)),
    }
    drawdown_day = 3
    anchors[drawdown_day] = min(
        anchors.get(drawdown_day, entry_price),
        entry_price * (1 + max(drawdown, -0.8)),
    )
    prices: list[LLMFactorPriceBar] = []
    for offset in range(_PRICE_BAR_DAYS):
        close = _interpolated_anchor_price(anchors, offset)
        prices.append(
            LLMFactorPriceBar(
                symbol=symbol,
                date=signal_date + timedelta(days=offset),
                close=max(close, 1.0),
            )
        )
    return prices


def _interpolated_anchor_price(anchors: dict[int, float], offset: int) -> float:
    if offset in anchors:
        return anchors[offset]
    previous_offsets = [anchor_offset for anchor_offset in anchors if anchor_offset < offset]
    next_offsets = [anchor_offset for anchor_offset in anchors if anchor_offset > offset]
    if not previous_offsets or not next_offsets:
        return anchors[max(previous_offsets or next_offsets)]
    left = max(previous_offsets)
    right = min(next_offsets)
    ratio = (offset - left) / (right - left)
    return anchors[left] + (anchors[right] - anchors[left]) * ratio


def _baseline_scores(
    signal: LLMFactorBacktestSignal,
    returns: dict[str, float],
) -> list[LLMFactorBaselineScore]:
    net = signal.bullish_score - signal.bearish_score
    ranking_score = _clamp_score(50 + 0.30 * net - 0.08 * signal.risk_score)
    forecast_score = _clamp_score(50 + returns["20d"] * 550)
    investment_score = _clamp_score(
        0.45 * ranking_score + 0.35 * forecast_score + 0.20 * (100 - signal.risk_score)
    )
    return [
        LLMFactorBaselineScore(
            symbol=signal.symbol,
            signal_date=signal.signal_date,
            baseline_name="ranking_score",
            score=ranking_score,
        ),
        LLMFactorBaselineScore(
            symbol=signal.symbol,
            signal_date=signal.signal_date,
            baseline_name="forecast_score",
            score=forecast_score,
        ),
        LLMFactorBaselineScore(
            symbol=signal.symbol,
            signal_date=signal.signal_date,
            baseline_name="investment_score",
            score=investment_score,
        ),
        LLMFactorBaselineScore(
            symbol=signal.symbol,
            signal_date=signal.signal_date,
            baseline_name="naive_baseline",
            score=50.0,
        ),
    ]


def _manifest(
    *,
    signals: list[LLMFactorBacktestSignal],
    prices: list[LLMFactorPriceBar],
    baseline_scores: list[LLMFactorBaselineScore],
    symbol_segments: dict[str, dict[str, str]],
) -> LLMFactorFixtureManifest:
    all_dates = [signal.signal_date for signal in signals] + [price.date for price in prices]
    segment_values = sorted(
        {value for segments in symbol_segments.values() for value in segments.values()}
    )
    markets = sorted({segments["market"] for segments in symbol_segments.values()})
    fixture_hash = _fixture_hash(
        signals=signals,
        prices=prices,
        baseline_scores=baseline_scores,
        symbol_segments=symbol_segments,
    )
    return LLMFactorFixtureManifest(
        fixture_id=DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_ID,
        version=DEFAULT_LLM_FACTOR_HISTORICAL_FIXTURE_VERSION,
        generated_by="backend.llm_factor.historical_fixtures",
        is_synthetic_or_static=True,
        data_policy=(
            "deterministic validation fixture only; no live market data, real news, or real LLM output"
        ),
        markets=markets,
        segments=segment_values,
        symbol_count=len(symbol_segments),
        signal_count=len(signals),
        price_bar_count=len(prices),
        start_date=min(all_dates),
        end_date=max(all_dates),
        fixture_hash=fixture_hash,
    )


def _fixture_hash(
    *,
    signals: list[LLMFactorBacktestSignal],
    prices: list[LLMFactorPriceBar],
    baseline_scores: list[LLMFactorBaselineScore],
    symbol_segments: dict[str, dict[str, str]],
) -> str:
    payload = {
        "signals": [
            signal.model_dump(mode="json")
            for signal in sorted(signals, key=lambda row: (row.symbol, row.signal_date))
        ],
        "prices": [
            price.model_dump(mode="json")
            for price in sorted(prices, key=lambda row: (row.symbol, row.date))
        ],
        "baseline_scores": [
            score.model_dump(mode="json")
            for score in sorted(
                baseline_scores,
                key=lambda row: (row.symbol, row.signal_date, row.baseline_name),
            )
        ],
        "symbol_segments": dict(sorted(symbol_segments.items())),
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _deterministic_noise(
    symbol: str,
    date_index: int,
    salt: str = "base",
    *,
    scale: float,
) -> float:
    raw = hashlib.sha256(f"{symbol}:{date_index}:{salt}".encode("utf-8")).hexdigest()
    value = int(raw[:8], 16) / 0xFFFFFFFF
    return (value * 2 - 1) * scale


def _positive_noise(symbol: str, date_index: int, salt: str) -> float:
    return (_deterministic_noise(symbol, date_index, salt, scale=1.0) + 1) / 2


def _clamp_score(value: float) -> float:
    return min(100.0, max(0.0, value))
