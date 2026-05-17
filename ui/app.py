from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast

import altair as alt
import pandas as pd
import streamlit as st
from pydantic import ValidationError

from backend.app.main import RebalanceCheckRequest
from backend.forecast import forecast_model_display_name
from backend.portfolio.workflow import PortfolioRiskResult
from ui.rebalance_app import (
    MarketDataPreview,
    RebalanceScenarioError,
    build_market_data_preview,
    build_rebalance_report_context,
    build_rebalance_request,
    forecast_chart_rows,
    forecast_consensus_rows_for_bars,
    forecast_metric_csv_download,
    forecast_metric_json_download,
    forecast_metric_rows_for_bars,
    forecast_reference_period,
    get_rebalance_sample,
    investment_score_csv_download,
    investment_score_json_download,
    rebalance_sample_names,
    request_json_download,
    result_json_download,
    result_markdown_report_download,
    result_report_zip_download,
    run_rebalance_check,
    runtime_settings_summary,
    sample_widget_key,
    screening_score_csv_download,
    screening_score_json_download,
    symbol_name,
    symbol_reference_rows,
    table_csv_download,
    target_allocations_json,
    yfinance_search_symbol_rows,
)

MARKET_DATA_PROVIDER_OPTIONS = ["mock", "yahoo", "csv"]
MARKET_DATA_PREVIEW_STATE_KEY = "market_data_preview"
MARKET_DATA_STATUS_STATE_KEY = "market_data_status_message"
MARKET_DATA_FORECAST_DAYS_STATE_KEY = "market_data_forecast_horizon_days"
MARKET_DATA_TOAST_STATE_KEY = "market_data_toast_message"
MARKET_DATA_RANKING_STATE_KEY = "market_data_ranking_rows"
MARKET_DATA_RANKING_ERROR_STATE_KEY = "market_data_ranking_error_rows"
RANKING_FILTER_DIALOG_STATE_KEY = "market_data_ranking_filter_dialog_open"
REBALANCE_RESULT_STATE_KEY = "rebalance_result"
REBALANCE_REQUEST_STATE_KEY = "rebalance_request"

FORECAST_ACTUAL_LABEL = "実績価格"
MARKET_DATA_MODE_COCKPIT = "cockpit"
MARKET_DATA_MODE_RANKING = "ranking"
MARKET_DATA_MODE_LABELS = {
    MARKET_DATA_MODE_COCKPIT: "銘柄コックピット",
    MARKET_DATA_MODE_RANKING: "銘柄ランキング",
}
RANKING_PRESET_BALANCED = "balanced"
RANKING_PRESET_FORECAST = "forecast"
RANKING_PRESET_QUALITY = "quality"
RANKING_PRESET_RISK = "risk"
RANKING_WEIGHT_PRESET_LABELS = {
    RANKING_PRESET_BALANCED: "バランス重視",
    RANKING_PRESET_FORECAST: "予測一致重視",
    RANKING_PRESET_QUALITY: "データ品質重視",
    RANKING_PRESET_RISK: "リスク控えめ",
}
RANKING_WEIGHT_PRESETS: dict[str, dict[str, Decimal]] = {
    RANKING_PRESET_BALANCED: {
        "screening_score": Decimal("0.50"),
        "forecast_agreement_score": Decimal("0.20"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.10"),
    },
    RANKING_PRESET_FORECAST: {
        "screening_score": Decimal("0.35"),
        "forecast_agreement_score": Decimal("0.40"),
        "data_quality_score": Decimal("0.15"),
        "risk_signal_score": Decimal("0.10"),
    },
    RANKING_PRESET_QUALITY: {
        "screening_score": Decimal("0.35"),
        "forecast_agreement_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.40"),
        "risk_signal_score": Decimal("0.10"),
    },
    RANKING_PRESET_RISK: {
        "screening_score": Decimal("0.35"),
        "forecast_agreement_score": Decimal("0.15"),
        "data_quality_score": Decimal("0.20"),
        "risk_signal_score": Decimal("0.30"),
    },
}
RANKING_PERIOD_PRESETS = {
    "short": 7,
    "medium": 30,
    "long": 365,
}
RANKING_PERIOD_LABELS = {
    "short": "短期: 1週間",
    "medium": "中期: 1か月",
    "long": "長期: 1年",
}
RANKING_MARKET_LABELS = {
    "all": "すべて",
    "jp": "日本株",
    "us": "米国株",
    "etf": "ETF",
}
RANKING_ASSET_TYPE_LABELS = {
    "all": "すべて",
    "stock": "個別株",
    "etf": "ETF",
    "adr": "ADR",
}
RANKING_CURRENCY_LABELS = {
    "all": "すべて",
    "JPY": "JPY",
    "USD": "USD",
}
RANKING_DIVIDEND_LABELS = {
    "all": "指定なし",
    "high_dividend": "高配当候補",
    "dividend": "配当あり",
    "none": "配当なし",
    "growth_dividend": "連続増配候補",
}
RANKING_COMPLEXITY_LABELS = {
    "beginner": "初心者向け",
    "standard": "標準まで",
    "all": "上級者向けも含める",
}
RANKING_THEME_LABELS = {
    "all": "指定なし",
    "technology": "テクノロジー",
    "semiconductor": "半導体",
    "financial": "金融",
    "consumer": "消費",
    "healthcare": "ヘルスケア",
    "energy": "エネルギー",
    "automotive": "自動車",
    "trading": "商社",
    "index": "インデックス",
    "dividend": "高配当",
}
RANKING_MARKET_CAP_LABELS = {
    "all": "指定なし",
    "mega": "超大型",
    "large": "大型",
    "mid": "中型",
}
RANKING_INDEX_FAMILY_LABELS = {
    "all": "指定なし",
    "sp500": "S&P 500",
    "nasdaq100": "NASDAQ 100",
    "total_us": "全米",
    "small_us": "米国小型",
}
JP_THEME_BY_SYMBOL = {
    "7203.T": "automotive",
    "7267.T": "automotive",
    "6902.T": "automotive",
    "8306.T": "financial",
    "8411.T": "financial",
    "8316.T": "financial",
    "8766.T": "financial",
    "8591.T": "financial",
    "8058.T": "trading",
    "8001.T": "trading",
    "8031.T": "trading",
    "4519.T": "healthcare",
    "4568.T": "healthcare",
    "4502.T": "healthcare",
    "8035.T": "semiconductor",
    "6981.T": "semiconductor",
    "6861.T": "technology",
    "6501.T": "technology",
    "9613.T": "technology",
    "6702.T": "technology",
    "9432.T": "technology",
    "4689.T": "technology",
    "4755.T": "technology",
    "1605.T": "energy",
    "6098.T": "consumer",
    "2914.T": "consumer",
    "7974.T": "consumer",
    "8801.T": "consumer",
    "9020.T": "consumer",
    "9022.T": "consumer",
    "4661.T": "consumer",
    "5108.T": "consumer",
    "3382.T": "consumer",
    "8267.T": "consumer",
    "9843.T": "consumer",
    "4452.T": "consumer",
    "4911.T": "consumer",
    "2502.T": "consumer",
    "2802.T": "consumer",
}
US_THEME_BY_SYMBOL = {
    "AAPL": "technology",
    "MSFT": "technology",
    "GOOGL": "technology",
    "META": "technology",
    "ORCL": "technology",
    "ADBE": "technology",
    "CRM": "technology",
    "NOW": "technology",
    "UBER": "technology",
    "ABNB": "technology",
    "PYPL": "technology",
    "NVDA": "semiconductor",
    "AMD": "semiconductor",
    "INTC": "semiconductor",
    "AVGO": "semiconductor",
    "TSLA": "automotive",
    "TM": "automotive",
    "SONY": "consumer",
    "AMZN": "consumer",
    "NFLX": "consumer",
    "KO": "consumer",
    "PEP": "consumer",
    "PG": "consumer",
    "COST": "consumer",
    "WMT": "consumer",
    "HD": "consumer",
    "MCD": "consumer",
    "NKE": "consumer",
    "DIS": "consumer",
    "JPM": "financial",
    "BAC": "financial",
    "V": "financial",
    "MA": "financial",
    "AXP": "financial",
    "BRK-B": "financial",
    "UNH": "healthcare",
    "JNJ": "healthcare",
    "LLY": "healthcare",
    "MRK": "healthcare",
    "PFE": "healthcare",
    "ABBV": "healthcare",
    "XOM": "energy",
    "CVX": "energy",
}
HIGH_DIVIDEND_SYMBOLS = {
    "9432.T",
    "8058.T",
    "8001.T",
    "8031.T",
    "2914.T",
    "8411.T",
    "8316.T",
    "8591.T",
    "4502.T",
    "1605.T",
    "XOM",
    "CVX",
    "PFE",
    "ABBV",
}
GROWTH_DIVIDEND_SYMBOLS = {"KO", "PEP", "PG", "JNJ", "MCD", "HD", "WMT", "COST"}
NO_DIVIDEND_SYMBOLS = {
    "NVDA",
    "TSLA",
    "GOOGL",
    "AMZN",
    "META",
    "NFLX",
    "AMD",
    "ADBE",
    "CRM",
    "NOW",
    "SHOP",
    "UBER",
    "ABNB",
    "PYPL",
}
LOWER_RISK_SYMBOLS = {
    "7203.T",
    "9432.T",
    "8306.T",
    "8058.T",
    "8001.T",
    "4502.T",
    "KO",
    "PEP",
    "PG",
    "JNJ",
    "COST",
    "WMT",
    "SPY",
    "VTI",
    "VOO",
}
INSTALLMENT_SYMBOLS = {"SPY", "QQQ", "VTI", "VOO", "IWM"}
ETF_SYMBOLS = INSTALLMENT_SYMBOLS
ADR_SYMBOLS = {"TM", "SONY"}
DIVIDEND_YIELD_PCT_BY_SYMBOL = {
    "7203.T": "2.6",
    "9983.T": "0.7",
    "6758.T": "0.8",
    "8306.T": "3.1",
    "9432.T": "3.4",
    "8058.T": "3.2",
    "8001.T": "2.4",
    "8031.T": "3.0",
    "2914.T": "4.5",
    "8411.T": "3.4",
    "8316.T": "3.2",
    "8591.T": "3.2",
    "4502.T": "4.0",
    "1605.T": "3.6",
    "AAPL": "0.5",
    "MSFT": "0.7",
    "INTC": "1.2",
    "AVGO": "1.2",
    "ORCL": "1.4",
    "JPM": "2.2",
    "BAC": "2.5",
    "V": "0.8",
    "MA": "0.6",
    "AXP": "1.1",
    "BRK-B": "0.0",
    "UNH": "1.4",
    "JNJ": "3.0",
    "LLY": "0.7",
    "MRK": "3.0",
    "PFE": "6.0",
    "ABBV": "3.7",
    "XOM": "3.4",
    "CVX": "4.0",
    "KO": "3.1",
    "PEP": "3.0",
    "PG": "2.4",
    "COST": "0.6",
    "WMT": "1.0",
    "HD": "2.2",
    "MCD": "2.3",
    "SPY": "1.2",
    "QQQ": "0.6",
    "VTI": "1.3",
    "VOO": "1.2",
    "IWM": "1.3",
}
MARKET_CAP_TIER_BY_SYMBOL = {
    "AAPL": "mega",
    "MSFT": "mega",
    "NVDA": "mega",
    "GOOGL": "mega",
    "AMZN": "mega",
    "META": "mega",
    "7203.T": "large",
    "9983.T": "large",
    "6758.T": "large",
    "8306.T": "large",
    "9432.T": "large",
    "6861.T": "large",
    "8035.T": "large",
    "8058.T": "large",
    "8001.T": "large",
    "JPM": "large",
    "BAC": "large",
    "V": "large",
    "MA": "large",
    "UNH": "large",
    "JNJ": "large",
    "LLY": "large",
    "XOM": "large",
    "CVX": "large",
}
ETF_INDEX_FAMILY_BY_SYMBOL = {
    "SPY": "sp500",
    "VOO": "sp500",
    "QQQ": "nasdaq100",
    "VTI": "total_us",
    "IWM": "small_us",
}
ETF_EXPENSE_RATIO_PCT_BY_SYMBOL = {
    "SPY": "0.09",
    "QQQ": "0.20",
    "VTI": "0.03",
    "VOO": "0.03",
    "IWM": "0.19",
}
JP_SYMBOL_ALIASES = {
    "7203.T": "トヨタ 自動車",
    "9983.T": "ファーストリテイリング ユニクロ",
    "6758.T": "ソニー",
    "8306.T": "三菱UFJ 銀行 金融",
    "9432.T": "NTT 日本電信電話 通信 高配当",
    "6861.T": "キーエンス",
    "8035.T": "東京エレクトロン 半導体",
    "6098.T": "リクルート",
    "4063.T": "信越化学",
    "6501.T": "日立",
    "8058.T": "三菱商事 商社 高配当",
    "8001.T": "伊藤忠 商社",
    "8031.T": "三井物産 商社",
    "2914.T": "日本たばこ JT 高配当",
    "7974.T": "任天堂",
    "4519.T": "中外製薬 ヘルスケア",
    "4568.T": "第一三共 ヘルスケア",
    "4502.T": "武田薬品 ヘルスケア 高配当",
    "8316.T": "三井住友 金融",
    "8591.T": "オリックス 金融 高配当",
}
SYMBOL_UNIVERSE_OVERRIDES: dict[str, dict[str, str]] = {
    "7203.T": {"theme": "automotive", "tags": "balanced,lower_risk"},
    "9432.T": {
        "theme": "telecom",
        "dividend_category": "high_dividend",
        "tags": "dividend,lower_risk",
    },
    "8058.T": {"theme": "trading", "dividend_category": "high_dividend", "tags": "dividend"},
    "8001.T": {"theme": "trading", "dividend_category": "dividend", "tags": "dividend"},
    "2914.T": {"theme": "consumer", "dividend_category": "high_dividend", "tags": "dividend"},
    "AAPL": {
        "theme": "technology",
        "dividend_category": "dividend",
        "tags": "growth,balanced",
    },
    "MSFT": {
        "theme": "technology",
        "dividend_category": "dividend",
        "tags": "growth,balanced",
    },
    "NVDA": {"theme": "semiconductor", "dividend_category": "none", "tags": "growth"},
    "TSLA": {"theme": "automotive", "dividend_category": "none", "tags": "growth"},
    "JPM": {"theme": "financial", "dividend_category": "dividend", "tags": "dividend"},
    "XOM": {"theme": "energy", "dividend_category": "dividend", "tags": "dividend"},
    "KO": {
        "theme": "consumer",
        "dividend_category": "growth_dividend",
        "tags": "dividend,lower_risk",
    },
    "PG": {
        "theme": "consumer",
        "dividend_category": "growth_dividend",
        "tags": "dividend,lower_risk",
    },
    "SPY": {"asset_type": "etf", "theme": "index", "tags": "installment,balanced,lower_risk"},
    "QQQ": {"asset_type": "etf", "theme": "index", "tags": "installment,growth"},
    "VTI": {"asset_type": "etf", "theme": "index", "tags": "installment,balanced,lower_risk"},
    "VOO": {"asset_type": "etf", "theme": "index", "tags": "installment,balanced,lower_risk"},
    "IWM": {"asset_type": "etf", "theme": "index", "tags": "installment"},
}


def main() -> None:
    st.set_page_config(page_title="Smart Market AI", layout="wide")
    st.title("Smart Market AI")

    market_data_tab, rebalance_tab = st.tabs(["Market Data", "Rebalance"])

    with st.sidebar:
        _render_runtime_settings()
        _render_symbol_reference()
        try:
            sample_names = rebalance_sample_names()
            sample_name = cast(str, st.selectbox("Sample", sample_names))
            sample = get_rebalance_sample(sample_name)
        except RebalanceScenarioError as exc:
            st.error(str(exc))
            st.stop()
        if sample.description:
            st.caption(sample.description)

        account_id = st.text_input(
            "Account",
            value=sample.account_id,
            key=sample_widget_key(sample_name, "account"),
        )
        as_of = st.date_input(
            "As of",
            value=default_as_of_date(),
            key=sample_widget_key(sample_name, "as_of"),
        )
        cash_jpy_text = st.text_input(
            "Cash JPY",
            value=str(sample.cash_jpy),
            key=sample_widget_key(sample_name, "cash_jpy"),
        )
        apple_target_weight = cast(
            int,
            st.slider(
                "AAPL target weight",
                min_value=0,
                max_value=100,
                value=_default_apple_target_weight(sample.targets_json),
                step=5,
                format="%d%%",
                key=sample_widget_key(sample_name, "apple_target_weight"),
            ),
        )

    with rebalance_tab:
        st.subheader("Rebalance Cockpit")
        st.caption(
            "現在の保有、目標配分、必要な売買、Risk 判定を確認します。売買送信は行いません。"
        )
        generated_targets_json = target_allocations_json(
            toyota_weight=Decimal(100 - apple_target_weight) / Decimal("100"),
            apple_weight=Decimal(apple_target_weight) / Decimal("100"),
        )
        with st.expander("Advanced JSON input"):
            col_positions, col_targets = st.columns(2)
            with col_positions:
                positions_json = st.text_area(
                    "Positions",
                    value=sample.positions_json,
                    height=280,
                    key=sample_widget_key(sample_name, "positions"),
                )
            with col_targets:
                targets_json = st.text_area(
                    "Targets",
                    value=generated_targets_json,
                    height=280,
                    key=sample_widget_key(sample_name, "targets"),
                )

        if st.button("Run rebalance check", type="primary"):
            try:
                request = build_rebalance_request(
                    account_id=account_id,
                    as_of=_single_date_from_input(as_of),
                    cash_jpy=_decimal_from_text(cash_jpy_text),
                    positions_json=positions_json,
                    targets_json=targets_json,
                )
                result = asyncio.run(run_rebalance_check(request))
                st.session_state[REBALANCE_RESULT_STATE_KEY] = result
                st.session_state[REBALANCE_REQUEST_STATE_KEY] = request
            except InvalidOperation:
                st.error("Cash JPY must be a decimal number.")
                return
            except ValueError as exc:
                st.error(str(exc))
                return
            except ValidationError as exc:
                st.error("Request validation failed.")
                st.json(exc.errors())
                return
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
                return

        stored_rebalance = rebalance_result_from_state()
        if stored_rebalance is not None:
            result, request = stored_rebalance
            _render_result(result, request)

    with market_data_tab:
        _render_market_data_preview()


def _decimal_from_text(value: str) -> Decimal:
    return Decimal(value.strip())


def _single_date_from_input(value: object) -> date:
    if isinstance(value, date):
        return value
    raise ValueError("As of must be a single date.")


def default_as_of_date() -> date:
    return date.today()


def default_market_data_start_date() -> date:
    return default_market_data_end_date() - timedelta(days=7)


def default_market_data_end_date() -> date:
    return date.today()


def default_forecast_horizon_days(start: date, end: date) -> int:
    """Choose a compact forecast horizon from the displayed chart period."""

    if end < start:
        raise ValueError("End must be on or after Start")
    display_days = (end - start).days + 1
    return max(1, min(30, round(display_days / 10)))


def _default_apple_target_weight(targets_json: str) -> int:
    if '"symbol": "AAPL"' not in targets_json:
        return 0
    if '"target_weight": "0.5"' in targets_json:
        return 50
    return 0


def _render_runtime_settings() -> None:
    settings = runtime_settings_summary()
    st.caption("Runtime")
    st.write(f"Provider: `{settings['provider']}`")
    st.write(f"Config: `{settings['config_file']}`")
    st.write(f"Scenarios: `{settings['scenario_dir']}`")
    if settings["provider"] == "csv":
        st.write(f"CSV data: `{settings['csv_data_dir']}`")


def _render_symbol_reference() -> None:
    st.caption("Sample Symbols")
    st.dataframe(symbol_reference_rows(), hide_index=True, use_container_width=True)


def _provider_option_index(provider: str) -> int:
    try:
        return MARKET_DATA_PROVIDER_OPTIONS.index(provider)
    except ValueError:
        return 0


def default_market_data_provider() -> str:
    return "yahoo"


def _symbol_from_candidate(label: str) -> str | None:
    if not label:
        return None
    return label.split(" - ", 1)[0]


def _name_from_candidate(label: str) -> str | None:
    if " - " not in label:
        return None
    return label.split(" - ", 1)[1]


def symbol_candidate_labels(rows: list[dict[str, str]], query: str = "") -> list[str]:
    labels = [f"{row['symbol']} - {row['name']}" for row in rows]
    normalized_query = query.strip().lower()
    if normalized_query:
        labels = [label for label in labels if normalized_query in label.lower()]
    return labels


def ranking_period_label(preset: str) -> str:
    return RANKING_PERIOD_LABELS.get(preset, preset)


def ranking_period_dates(preset: str, end: date) -> tuple[date, date]:
    days = RANKING_PERIOD_PRESETS.get(preset, RANKING_PERIOD_PRESETS["medium"])
    return end - timedelta(days=days), end


def symbol_universe_rows(reference_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [_symbol_universe_row(row) for row in reference_rows]


def filter_symbol_universe_rows(
    rows: list[dict[str, str]],
    *,
    purpose: str = "all",
    market: str = "all",
    asset_type: str = "all",
    currency: str = "all",
    dividend_category: str = "all",
    min_dividend_yield_pct: Decimal | str | int = Decimal("0"),
    market_cap_tier: str = "all",
    index_family: str = "all",
    max_expense_ratio_pct: Decimal | str | int = Decimal("1.00"),
    complexity: str = "standard",
    theme: str = "all",
    query: str = "",
    limit: int = 10,
) -> list[dict[str, str]]:
    normalized_query = query.strip().lower()
    min_dividend = _decimal_filter_value(min_dividend_yield_pct, Decimal("0"))
    max_expense = _decimal_filter_value(max_expense_ratio_pct, Decimal("1.00"))
    filtered: list[dict[str, str]] = []
    for row in rows:
        tags = _symbol_universe_values(row, "tags")
        if purpose != "all" and purpose not in tags:
            continue
        if market == "etf":
            if row.get("asset_type") != "etf":
                continue
        elif market != "all" and row.get("market") != market:
            continue
        if asset_type != "all" and row.get("asset_type") != asset_type:
            continue
        if currency != "all" and row.get("currency") != currency:
            continue
        if dividend_category != "all" and row.get("dividend_category") != dividend_category:
            continue
        dividend_yield = _decimal_filter_value(row.get("dividend_yield_pct", ""), Decimal("0"))
        if dividend_yield < min_dividend:
            continue
        if market_cap_tier != "all" and row.get("market_cap_tier") != market_cap_tier:
            continue
        if index_family != "all" and row.get("index_family") != index_family:
            continue
        expense_ratio = row.get("expense_ratio_pct", "")
        if row.get("asset_type") == "etf" and expense_ratio:
            if _decimal_filter_value(expense_ratio, Decimal("99")) > max_expense:
                continue
        if not _symbol_complexity_allowed(row.get("complexity", "standard"), complexity):
            continue
        if theme != "all" and theme not in tags and row.get("theme") != theme:
            continue
        if normalized_query:
            label = " ".join(
                [
                    row.get("symbol", ""),
                    row.get("name", ""),
                    row.get("theme", ""),
                    row.get("dividend_category", ""),
                    row.get("tags", ""),
                    row.get("aliases", ""),
                ]
            ).lower()
            if normalized_query not in label:
                continue
        filtered.append(row)
    return filtered[: max(limit, 0)]


def _decimal_filter_value(value: Decimal | str | int, default: Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return default


def _symbol_universe_row(row: dict[str, str]) -> dict[str, str]:
    symbol = row.get("symbol", "").strip()
    symbol_upper = symbol.upper()
    default_market = "jp" if symbol_upper.endswith(".T") else "us"
    default_currency = "JPY" if default_market == "jp" else "USD"
    default_asset_type = "adr" if symbol_upper in ADR_SYMBOLS else "stock"
    if symbol_upper in ETF_SYMBOLS:
        default_asset_type = "etf"
    theme = (
        JP_THEME_BY_SYMBOL.get(symbol_upper)
        if default_market == "jp"
        else US_THEME_BY_SYMBOL.get(symbol_upper)
    ) or "consumer"
    dividend_category = "dividend"
    if symbol_upper in HIGH_DIVIDEND_SYMBOLS:
        dividend_category = "high_dividend"
    elif symbol_upper in GROWTH_DIVIDEND_SYMBOLS:
        dividend_category = "growth_dividend"
    elif symbol_upper in NO_DIVIDEND_SYMBOLS or default_asset_type == "etf":
        dividend_category = "none"
    tags = {"balanced"}
    if symbol_upper in LOWER_RISK_SYMBOLS or default_asset_type == "etf":
        tags.add("lower_risk")
    if symbol_upper in INSTALLMENT_SYMBOLS:
        tags.add("installment")
    if theme in {"technology", "semiconductor"} and default_asset_type != "etf":
        tags.add("growth")
    if dividend_category in {"dividend", "high_dividend", "growth_dividend"}:
        tags.add("dividend")
    if dividend_category == "high_dividend":
        tags.add("dividend")
    universe_row = {
        "symbol": symbol,
        "name": row.get("name", symbol),
        "market": default_market,
        "asset_type": default_asset_type,
        "currency": default_currency,
        "theme": theme,
        "dividend_category": dividend_category,
        "dividend_yield_pct": DIVIDEND_YIELD_PCT_BY_SYMBOL.get(symbol_upper, "0"),
        "market_cap_tier": MARKET_CAP_TIER_BY_SYMBOL.get(symbol_upper, "mid"),
        "index_family": ETF_INDEX_FAMILY_BY_SYMBOL.get(symbol_upper, ""),
        "expense_ratio_pct": ETF_EXPENSE_RATIO_PCT_BY_SYMBOL.get(symbol_upper, ""),
        "complexity": "beginner" if default_asset_type == "etf" else "standard",
        "tags": ",".join(sorted(tags)),
        "aliases": JP_SYMBOL_ALIASES.get(symbol_upper, ""),
    }
    overrides = SYMBOL_UNIVERSE_OVERRIDES.get(symbol_upper, {})
    override_tags = overrides.get("tags", "")
    universe_row.update(overrides)
    if override_tags:
        merged_tags = _symbol_universe_values({"tags": ",".join(sorted(tags))}, "tags")
        merged_tags.update(_symbol_universe_values({"tags": override_tags}, "tags"))
        universe_row["tags"] = ",".join(sorted(merged_tags))
    if universe_row["asset_type"] == "etf":
        universe_row["market"] = "us"
    return universe_row


def _symbol_universe_values(row: dict[str, str], key: str) -> set[str]:
    return {value.strip() for value in row.get(key, "").split(",") if value.strip()}


def _symbol_complexity_allowed(symbol_complexity: str, selected_complexity: str) -> bool:
    if selected_complexity == "all":
        return True
    if selected_complexity == "standard":
        return symbol_complexity in {"beginner", "standard"}
    return symbol_complexity == "beginner"


def _ranking_filter_value(key: str, default: str) -> str:
    value = st.session_state.get(key, default)
    return str(value) if value is not None else default


def _ranking_filter_int(key: str, default: int) -> int:
    value = st.session_state.get(key, default)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return default


def ranking_filter_summary() -> str:
    period = ranking_period_label(_ranking_filter_value("market_data_ranking_period", "short"))
    market = RANKING_MARKET_LABELS.get(
        _ranking_filter_value("market_data_ranking_market", "all"),
        "すべて",
    )
    asset_type = RANKING_ASSET_TYPE_LABELS.get(
        _ranking_filter_value("market_data_ranking_asset_type", "all"),
        "すべて",
    )
    dividend = RANKING_DIVIDEND_LABELS.get(
        _ranking_filter_value("market_data_ranking_dividend", "all"),
        "指定なし",
    )
    min_dividend = _ranking_filter_value("market_data_ranking_min_dividend", "0.0")
    limit = _ranking_filter_int("market_data_ranking_limit", 6)
    return (
        f"条件: {period} / {market} / {asset_type} / "
        f"配当 {min_dividend}% 以上 / {dividend} / 最大 {limit} 件"
    )


def ranking_filter_signature(
    *,
    purpose: str,
    period_preset: str,
    market: str,
    asset_type: str,
    currency: str,
    dividend_category: str,
    min_dividend_yield_pct: str = "0.0",
    market_cap_tier: str = "all",
    index_family: str = "all",
    max_expense_ratio_pct: str = "1.00",
    complexity: str,
    theme: str,
    query: str,
    limit: int,
) -> str:
    return "|".join(
        [
            purpose,
            period_preset,
            market,
            asset_type,
            currency,
            dividend_category,
            min_dividend_yield_pct,
            market_cap_tier,
            index_family,
            max_expense_ratio_pct,
            complexity,
            theme,
            query.strip().lower(),
            str(limit),
        ]
    )


def _ranking_filter_signature_from_state() -> str:
    return ranking_filter_signature(
        purpose="all",
        period_preset=_ranking_filter_value("market_data_ranking_period", "short"),
        market=_ranking_filter_value("market_data_ranking_market", "all"),
        asset_type=_ranking_filter_value("market_data_ranking_asset_type", "all"),
        currency=_ranking_filter_value("market_data_ranking_currency", "all"),
        dividend_category=_ranking_filter_value("market_data_ranking_dividend", "all"),
        min_dividend_yield_pct=_ranking_filter_value("market_data_ranking_min_dividend", "0.0"),
        market_cap_tier=_ranking_filter_value("market_data_ranking_market_cap", "all"),
        index_family=_ranking_filter_value("market_data_ranking_index_family", "all"),
        max_expense_ratio_pct=_ranking_filter_value("market_data_ranking_max_expense", "1.00"),
        complexity=_ranking_filter_value("market_data_ranking_complexity", "standard"),
        theme=_ranking_filter_value("market_data_ranking_theme", "all"),
        query=_ranking_filter_value("market_data_ranking_symbol_query", ""),
        limit=_ranking_filter_int("market_data_ranking_limit", 6),
    )


@st.dialog("候補条件")
def _render_ranking_filter_dialog() -> None:
    st.caption("銘柄を取得する前に分かる属性だけで候補を絞ります。")
    col_period, col_min_dividend = st.columns([1.0, 1.0])
    with col_period:
        st.selectbox(
            "期間",
            list(RANKING_PERIOD_PRESETS),
            index=list(RANKING_PERIOD_PRESETS).index(
                _ranking_filter_value("market_data_ranking_period", "short")
            ),
            key="market_data_ranking_period",
            format_func=ranking_period_label,
        )
    with col_min_dividend:
        st.number_input(
            "配当利回り(%)以上",
            min_value=0.0,
            max_value=10.0,
            value=float(_ranking_filter_value("market_data_ranking_min_dividend", "0.0")),
            step=0.1,
            key="market_data_ranking_min_dividend",
        )
    col_market, col_type = st.columns(2)
    with col_market:
        st.selectbox(
            "対象市場",
            list(RANKING_MARKET_LABELS),
            index=list(RANKING_MARKET_LABELS).index(
                _ranking_filter_value("market_data_ranking_market", "all")
            ),
            key="market_data_ranking_market",
            format_func=lambda value: RANKING_MARKET_LABELS[value],
        )
    with col_type:
        st.selectbox(
            "銘柄タイプ",
            list(RANKING_ASSET_TYPE_LABELS),
            index=list(RANKING_ASSET_TYPE_LABELS).index(
                _ranking_filter_value("market_data_ranking_asset_type", "all")
            ),
            key="market_data_ranking_asset_type",
            format_func=lambda value: RANKING_ASSET_TYPE_LABELS[value],
        )
    col_currency, col_dividend = st.columns(2)
    with col_currency:
        st.selectbox(
            "通貨",
            list(RANKING_CURRENCY_LABELS),
            index=list(RANKING_CURRENCY_LABELS).index(
                _ranking_filter_value("market_data_ranking_currency", "all")
            ),
            key="market_data_ranking_currency",
            format_func=lambda value: RANKING_CURRENCY_LABELS[value],
        )
    with col_dividend:
        st.selectbox(
            "配当カテゴリ",
            list(RANKING_DIVIDEND_LABELS),
            index=list(RANKING_DIVIDEND_LABELS).index(
                _ranking_filter_value("market_data_ranking_dividend", "all")
            ),
            key="market_data_ranking_dividend",
            format_func=lambda value: RANKING_DIVIDEND_LABELS[value],
        )
    col_market_cap, col_theme = st.columns(2)
    with col_market_cap:
        st.selectbox(
            "時価総額",
            list(RANKING_MARKET_CAP_LABELS),
            index=list(RANKING_MARKET_CAP_LABELS).index(
                _ranking_filter_value("market_data_ranking_market_cap", "all")
            ),
            key="market_data_ranking_market_cap",
            format_func=lambda value: RANKING_MARKET_CAP_LABELS[value],
        )
    with col_theme:
        st.selectbox(
            "テーマ",
            list(RANKING_THEME_LABELS),
            index=list(RANKING_THEME_LABELS).index(
                _ranking_filter_value("market_data_ranking_theme", "all")
            ),
            key="market_data_ranking_theme",
            format_func=lambda value: RANKING_THEME_LABELS[value],
        )
    col_index, col_expense = st.columns(2)
    with col_index:
        st.selectbox(
            "ETF連動対象",
            list(RANKING_INDEX_FAMILY_LABELS),
            index=list(RANKING_INDEX_FAMILY_LABELS).index(
                _ranking_filter_value("market_data_ranking_index_family", "all")
            ),
            key="market_data_ranking_index_family",
            format_func=lambda value: RANKING_INDEX_FAMILY_LABELS[value],
        )
    with col_expense:
        st.number_input(
            "信託報酬(%)以下",
            min_value=0.0,
            max_value=2.0,
            value=float(_ranking_filter_value("market_data_ranking_max_expense", "1.00")),
            step=0.01,
            key="market_data_ranking_max_expense",
        )
    st.text_input(
        "キーワード",
        value=_ranking_filter_value("market_data_ranking_symbol_query", ""),
        key="market_data_ranking_symbol_query",
        placeholder="ticker or company name",
    )
    st.number_input(
        "表示件数",
        min_value=1,
        max_value=20,
        value=_ranking_filter_int("market_data_ranking_limit", 6),
        step=1,
        key="market_data_ranking_limit",
    )
    preview_rows = filter_symbol_universe_rows(
        symbol_universe_rows(symbol_reference_rows()),
        purpose="all",
        market=_ranking_filter_value("market_data_ranking_market", "all"),
        asset_type=_ranking_filter_value("market_data_ranking_asset_type", "all"),
        currency=_ranking_filter_value("market_data_ranking_currency", "all"),
        dividend_category=_ranking_filter_value("market_data_ranking_dividend", "all"),
        min_dividend_yield_pct=_ranking_filter_value("market_data_ranking_min_dividend", "0.0"),
        market_cap_tier=_ranking_filter_value("market_data_ranking_market_cap", "all"),
        index_family=_ranking_filter_value("market_data_ranking_index_family", "all"),
        max_expense_ratio_pct=_ranking_filter_value("market_data_ranking_max_expense", "1.00"),
        complexity=_ranking_filter_value("market_data_ranking_complexity", "standard"),
        theme=_ranking_filter_value("market_data_ranking_theme", "all"),
        query=_ranking_filter_value("market_data_ranking_symbol_query", ""),
        limit=_ranking_filter_int("market_data_ranking_limit", 6),
    )
    st.caption(f"この条件で {len(preview_rows)} 件が候補になります。")
    if preview_rows:
        preview_labels = symbol_candidate_labels(preview_rows)[:5]
        st.caption("候補例: " + " / ".join(preview_labels))
    else:
        st.warning("この条件に合う候補がありません。条件を少し広げてください。")
    if st.button("条件を適用", key="apply_market_data_ranking_filters"):
        st.session_state["market_data_ranking_filter_signature"] = (
            _ranking_filter_signature_from_state()
        )
        st.session_state.pop(MARKET_DATA_RANKING_STATE_KEY, None)
        st.session_state.pop(MARKET_DATA_RANKING_ERROR_STATE_KEY, None)
        st.session_state[RANKING_FILTER_DIALOG_STATE_KEY] = False
        st.rerun()


def merged_symbol_candidate_rows(
    reference_rows: list[dict[str, str]],
    live_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge representative and live-search symbol candidates without duplicates."""

    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in [*reference_rows, *live_rows]:
        symbol = row.get("symbol", "").strip()
        name = row.get("name", "").strip() or symbol
        normalized_symbol = symbol.upper()
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        merged.append({"symbol": symbol, "name": name})
    return merged


def _render_market_data_preview() -> None:
    st.subheader("Market Data")
    mode = cast(
        str,
        st.radio(
            "表示モード",
            [MARKET_DATA_MODE_COCKPIT, MARKET_DATA_MODE_RANKING],
            horizontal=True,
            key="market_data_mode",
            format_func=lambda value: MARKET_DATA_MODE_LABELS.get(value, value),
        ),
    )
    if mode == MARKET_DATA_MODE_RANKING:
        _render_market_data_ranking()
        return

    symbol_options = symbol_reference_rows()
    col_provider, col_search, col_symbol, col_name, col_start, col_end = st.columns(
        [1.0, 1.3, 1.7, 1.4, 1.0, 1.0]
    )
    with col_provider:
        provider = cast(
            str,
            st.selectbox(
                "Provider",
                MARKET_DATA_PROVIDER_OPTIONS,
                index=_provider_option_index(default_market_data_provider()),
                key="market_data_provider",
            ),
        )
    with col_search:
        symbol_query = st.text_input(
            "Symbol search",
            value="",
            key="market_data_symbol_search",
            placeholder="ticker or company name",
        )
    with col_symbol:
        live_symbol_options = (
            yfinance_search_symbol_rows(symbol_query) if symbol_query.strip() else []
        )
        candidate_rows = merged_symbol_candidate_rows(symbol_options, live_symbol_options)
        symbol_option_labels = symbol_candidate_labels(candidate_rows, symbol_query)
        if not symbol_option_labels:
            symbol_option_labels = symbol_candidate_labels(symbol_options)
        symbol_candidate = cast(
            str,
            st.selectbox(
                "Symbol",
                symbol_option_labels,
                index=min(1, len(symbol_option_labels) - 1),
                key="market_data_symbol_candidate",
                placeholder="ticker or company name",
            ),
        )
    symbol = _symbol_from_candidate(symbol_candidate) or "AAPL"
    with col_name:
        company_name = symbol_name(symbol) or _name_from_candidate(symbol_candidate) or "名称未登録"
        st.text_input("Name", value=company_name, disabled=True, key="market_data_symbol_name")
    with col_start:
        start = st.date_input(
            "Start",
            value=default_market_data_start_date(),
            key="market_data_start",
        )
    with col_end:
        end = st.date_input("End", value=default_market_data_end_date(), key="market_data_end")

    if st.button("Fetch market data", key="fetch_market_data"):
        try:
            start_date = _single_date_from_input(start)
            end_date = _single_date_from_input(end)
            forecast_horizon_days = default_forecast_horizon_days(start_date, end_date)
            st.session_state[MARKET_DATA_FORECAST_DAYS_STATE_KEY] = forecast_horizon_days
            preview = asyncio.run(
                build_market_data_preview(
                    symbol=symbol.strip(),
                    start=start_date,
                    end=end_date,
                    provider_override=provider,
                    forecast_horizon_days=forecast_horizon_days,
                )
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

        st.session_state[MARKET_DATA_PREVIEW_STATE_KEY] = preview
        st.session_state[MARKET_DATA_STATUS_STATE_KEY] = preview.status
        if preview.status == "OK":
            st.session_state[MARKET_DATA_TOAST_STATE_KEY] = "データを取得しました。"

    stored_preview = _market_data_preview_from_state()
    if stored_preview is None:
        return

    toast_message = st.session_state.pop(MARKET_DATA_TOAST_STATE_KEY, None)
    if toast_message:
        st.toast(str(toast_message), icon="✅")

    if st.session_state.get(MARKET_DATA_STATUS_STATE_KEY) != "OK":
        st.error("Market data fetch failed.")
        _render_provider_error_summary(stored_preview.error_rows)

    _render_market_data_preview_result(stored_preview)


def _render_market_data_ranking() -> None:
    st.subheader("銘柄ランキング")
    st.caption("複数銘柄を比較し、深掘り候補を整理します。売買推奨ではありません。")
    symbol_options = symbol_universe_rows(symbol_reference_rows())
    purpose = "all"
    period_preset = _ranking_filter_value("market_data_ranking_period", "short")
    market = _ranking_filter_value("market_data_ranking_market", "all")
    asset_type = _ranking_filter_value("market_data_ranking_asset_type", "all")
    currency = _ranking_filter_value("market_data_ranking_currency", "all")
    dividend_category = _ranking_filter_value("market_data_ranking_dividend", "all")
    min_dividend_yield_pct = _ranking_filter_value("market_data_ranking_min_dividend", "0.0")
    market_cap_tier = _ranking_filter_value("market_data_ranking_market_cap", "all")
    index_family = _ranking_filter_value("market_data_ranking_index_family", "all")
    max_expense_ratio_pct = _ranking_filter_value("market_data_ranking_max_expense", "1.00")
    complexity = _ranking_filter_value("market_data_ranking_complexity", "standard")
    theme = _ranking_filter_value("market_data_ranking_theme", "all")
    symbol_query = _ranking_filter_value("market_data_ranking_symbol_query", "")
    display_limit = _ranking_filter_int("market_data_ranking_limit", 6)

    col_provider, col_preset, col_filter = st.columns([1.0, 1.2, 2.8])
    with col_provider:
        provider = cast(
            str,
            st.selectbox(
                "Provider",
                MARKET_DATA_PROVIDER_OPTIONS,
                index=_provider_option_index(default_market_data_provider()),
                key="market_data_ranking_provider",
            ),
        )
    with col_preset:
        weight_preset = cast(
            str,
            st.selectbox(
                "重視条件",
                list(RANKING_WEIGHT_PRESETS),
                key="market_data_ranking_weight_preset",
                format_func=ranking_weight_preset_label,
            ),
        )
    with col_filter:
        if st.button("候補条件を変更", key="open_market_data_ranking_filters"):
            st.session_state[RANKING_FILTER_DIALOG_STATE_KEY] = True
        st.caption(ranking_filter_summary())
    if st.session_state.get(RANKING_FILTER_DIALOG_STATE_KEY):
        _render_ranking_filter_dialog()
    filtered_symbol_rows = filter_symbol_universe_rows(
        symbol_options,
        purpose=purpose,
        market=market,
        asset_type=asset_type,
        currency=currency,
        dividend_category=dividend_category,
        min_dividend_yield_pct=min_dividend_yield_pct,
        market_cap_tier=market_cap_tier,
        index_family=index_family,
        max_expense_ratio_pct=max_expense_ratio_pct,
        complexity=complexity,
        theme=theme,
        query=symbol_query,
        limit=display_limit,
    )
    labels = symbol_candidate_labels(filtered_symbol_rows)
    filter_signature = ranking_filter_signature(
        purpose=purpose,
        period_preset=period_preset,
        market=market,
        asset_type=asset_type,
        currency=currency,
        dividend_category=dividend_category,
        min_dividend_yield_pct=min_dividend_yield_pct,
        market_cap_tier=market_cap_tier,
        index_family=index_family,
        max_expense_ratio_pct=max_expense_ratio_pct,
        complexity=complexity,
        theme=theme,
        query=symbol_query,
        limit=display_limit,
    )
    default_labels = [
        label for label in labels if _symbol_from_candidate(label) in {"AAPL", "7203.T"}
    ][:2]
    if not default_labels:
        default_labels = labels[: min(2, len(labels))]
    col_symbols, col_period_text = st.columns([2.8, 1.2])
    with col_symbols:
        selected_labels = cast(
            list[str],
            st.multiselect(
                "比較する銘柄",
                labels,
                default=default_labels,
                key=f"market_data_ranking_symbols_{filter_signature}",
            ),
        )
    with col_period_text:
        end_date = default_market_data_end_date()
        start_date, end_date = ranking_period_dates(period_preset, end_date)
        st.caption(f"取得期間: {start_date.isoformat()} 〜 {end_date.isoformat()}")
        st.caption(f"候補数: {len(filtered_symbol_rows)}")
    if not labels:
        st.warning("この条件に合う候補がありません。候補条件を広げてください。")

    if st.button("ランキング作成", key="build_market_data_ranking"):
        symbols = [_symbol_from_candidate(label) for label in selected_labels]
        ranking_symbols = [symbol for symbol in symbols if symbol]
        if not ranking_symbols:
            st.error("Ranking symbols を1件以上選んでください。")
            return
        rows, error_rows = asyncio.run(
            _build_market_data_ranking_rows(
                ranking_symbols,
                start=start_date,
                end=end_date,
                provider=provider,
            )
        )
        st.session_state[MARKET_DATA_RANKING_STATE_KEY] = rows
        st.session_state[MARKET_DATA_RANKING_ERROR_STATE_KEY] = error_rows

    rows = st.session_state.get(MARKET_DATA_RANKING_STATE_KEY, [])
    error_rows = st.session_state.get(MARKET_DATA_RANKING_ERROR_STATE_KEY, [])
    if rows:
        ranked_rows = apply_ranking_weight_preset(
            cast(list[dict[str, str]], rows),
            weight_preset,
        )
        display_rows = investment_score_display_rows(ranked_rows)
        st.caption(
            f"重視条件: {ranking_weight_preset_label(weight_preset)}。"
            "上位の銘柄ほど、今回の条件では深掘り候補として見やすい順です。"
        )
        _render_table(display_rows, "No ranking rows.")
        deep_dive_symbols = ranking_symbol_options(ranked_rows)
        if deep_dive_symbols:
            selected_symbol = cast(
                str,
                st.selectbox(
                    "深掘りする銘柄",
                    deep_dive_symbols,
                    format_func=symbol_candidate_label,
                    key="market_data_ranking_deep_dive_symbol",
                ),
            )
            st.button(
                "銘柄コックピットで確認",
                key="market_data_ranking_open_cockpit",
                on_click=_select_ranking_symbol_for_cockpit,
                args=(selected_symbol, provider),
            )
        col_json, col_csv = st.columns(2)
        col_json.download_button(
            "Download ranking JSON",
            data=investment_score_json_download(ranked_rows),
            file_name="investment_score_ranking.json",
            mime="application/json",
        )
        col_csv.download_button(
            "Download ranking CSV",
            data=investment_score_csv_download(ranked_rows),
            file_name="investment_score_ranking.csv",
            mime="text/csv",
        )
    else:
        st.info("銘柄を選んで ranking を作成してください。")
    if error_rows:
        with st.expander("取得できなかった銘柄"):
            _render_table(cast(list[dict[str, str]], error_rows), "No ranking errors.")


async def _build_market_data_ranking_rows(
    symbols: list[str],
    *,
    start: date,
    end: date,
    provider: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    error_rows: list[dict[str, str]] = []
    forecast_horizon_days = default_forecast_horizon_days(start, end)
    for symbol in symbols:
        preview = await build_market_data_preview(
            symbol=symbol,
            start=start,
            end=end,
            provider_override=provider,
            forecast_horizon_days=forecast_horizon_days,
        )
        if preview.investment_score_rows:
            rows.extend(preview.investment_score_rows)
        for error_row in preview.error_rows:
            error_rows.append({"symbol": symbol, **error_row})
    return _rank_investment_score_rows(rows), error_rows


def _select_ranking_symbol_for_cockpit(symbol: str, provider: str) -> None:
    st.session_state["market_data_mode"] = MARKET_DATA_MODE_COCKPIT
    st.session_state["market_data_provider"] = provider
    st.session_state["market_data_symbol_candidate"] = symbol_candidate_label(symbol)
    st.session_state.pop(MARKET_DATA_PREVIEW_STATE_KEY, None)
    st.session_state.pop(MARKET_DATA_STATUS_STATE_KEY, None)


def ranking_symbol_options(rows: list[dict[str, str]]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for row in rows:
        symbol = row.get("symbol", "").strip()
        normalized = symbol.upper()
        if not symbol or normalized in seen:
            continue
        symbols.append(symbol)
        seen.add(normalized)
    return symbols


def symbol_candidate_label(symbol: str) -> str:
    name = symbol_name(symbol)
    if name:
        return f"{symbol} - {name}"
    return symbol


def _market_data_preview_from_state() -> MarketDataPreview | None:
    preview = st.session_state.get(MARKET_DATA_PREVIEW_STATE_KEY)
    if isinstance(preview, MarketDataPreview):
        return preview
    return None


def _render_market_data_preview_result(preview: MarketDataPreview) -> None:
    symbol_label = _market_data_preview_symbol_label(preview)
    forecast_horizon_days = _render_market_data_cockpit_header(preview, symbol_label)
    forecast_rows = forecast_chart_rows(preview.bars, horizon_days=forecast_horizon_days)
    consensus_rows = forecast_consensus_rows_for_bars(
        preview.bars,
        horizon_days=forecast_horizon_days,
    )
    metric_rows = forecast_metric_rows_for_bars(preview.bars, horizon_days=forecast_horizon_days)

    st.subheader("価格・予測チャート")
    _render_target_symbol_caption(symbol_label)
    for index, message in enumerate(forecast_chart_summary(consensus_rows, metric_rows)):
        if index == 0:
            st.info(message)
        else:
            st.caption(message)
    chart_currency = preview.bars[0].symbol.currency if preview.bars else ""
    _render_market_chart(
        forecast_rows,
        currency=chart_currency,
        title="実績価格と予測",
    )
    st.caption("縦の点線は、実績価格から予測表示へ切り替わる位置です。")
    _render_investment_score_section(preview, symbol_label)

    with st.expander("Forecast details"):
        for index, message in enumerate(forecast_metric_summary(metric_rows)):
            if index == 0:
                st.info(message)
            else:
                st.caption(message)
        st.subheader("Forecast Summary")
        _render_target_symbol_caption(symbol_label)
        _render_table(forecast_consensus_display_rows(consensus_rows), "No forecast summary.")
        st.subheader("Forecast Metrics")
        _render_target_symbol_caption(symbol_label)
        _render_table(forecast_metric_display_rows(metric_rows), "No forecast metrics.")
        if metric_rows:
            col_json, col_csv = st.columns(2)
            col_json.download_button(
                "Download forecast JSON",
                data=forecast_metric_json_download(metric_rows),
                file_name="forecast_metrics.json",
                mime="application/json",
            )
            col_csv.download_button(
                "Download forecast CSV",
                data=forecast_metric_csv_download(metric_rows),
                file_name="forecast_metrics.csv",
                mime="text/csv",
            )

    with st.expander("Screening Score"):
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.screening_rows, "No screening score rows.")
        if preview.screening_rows:
            col_json, col_csv = st.columns(2)
            col_json.download_button(
                "Download screening JSON",
                data=screening_score_json_download(preview.screening_rows),
                file_name="screening_score.json",
                mime="application/json",
            )
            col_csv.download_button(
                "Download screening CSV",
                data=screening_score_csv_download(preview.screening_rows),
                file_name="screening_score.csv",
                mime="text/csv",
            )

    with st.expander("Provider / Quote / OHLCV"):
        st.subheader("Provider")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.provider_rows, "No provider metadata.")

        st.subheader("Quote")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.quote_rows, "No quote rows.")

        st.subheader("OHLCV Summary")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.ohlcv_rows, "No OHLCV rows.")

    with st.expander("FX / Feature Snapshot"):
        st.subheader("FX")
        _render_table(preview.fx_rows, "No FX rows.")

        st.subheader("Feature Snapshot")
        _render_target_symbol_caption(symbol_label)
        _render_table(preview.feature_rows, "No feature snapshot rows.")

    if preview.error_rows:
        st.subheader("Errors")
        st.dataframe(preview.error_rows, hide_index=True, use_container_width=True)


def _render_market_data_cockpit_header(
    preview: MarketDataPreview,
    symbol_label: str,
) -> int:
    st.subheader("銘柄コックピット")
    metadata_col, horizon_col = st.columns([4.0, 1.0])
    provider_name = _metadata_value(preview.provider_rows, "provider") or "unknown"
    as_of = _market_data_as_of(preview)
    with horizon_col:
        forecast_horizon_days = cast(
            int,
            st.number_input(
                "Forecast days",
                min_value=1,
                max_value=30,
                step=1,
                key=MARKET_DATA_FORECAST_DAYS_STATE_KEY,
                help="取得済みデータを使ってチャートと指標だけを再計算します。",
            ),
        )
    reference_period = forecast_reference_period(preview.bars, horizon_days=forecast_horizon_days)
    with metadata_col:
        st.caption(
            f"対象: {symbol_label} / Provider: {provider_name} / "
            f"基準日: {as_of or '未取得'} / 参照期間: {reference_period}日"
        )
    return forecast_horizon_days


def _render_result(result: PortfolioRiskResult, request: RebalanceCheckRequest) -> None:
    context = build_rebalance_report_context(result)
    summary = context.summary
    status = summary["risk_status"]

    st.subheader("Summary")
    col_total, col_cash, col_trades, col_status = st.columns(4)
    col_total.metric("現在資産", f"{summary['total_value_jpy']} JPY")
    col_cash.metric("現金", f"{summary['cash_jpy']} JPY")
    col_trades.metric("必要な売買", summary["trade_count"])
    col_status.metric("Risk 判定", status)
    _render_rebalance_flow(summary)

    if status == "ALLOW":
        st.success("Risk 判定: ALLOW。今回の条件では大きな制約違反はありません。")
    elif status == "REVIEW":
        st.warning("Risk 判定: REVIEW。売買案の前提と制約を確認してください。")
    elif status == "BLOCK":
        st.error("Risk 判定: BLOCK。主な理由を確認し、目標配分や制約を見直してください。")
    else:
        st.info("売買案がないため、Risk 判定は行われていません。")

    current_rows = context.current_rows
    target_rows = context.target_rows
    allocation_rows = context.allocation_rows
    trade_rows = context.trade_rows
    breach_rows = context.breach_rows

    col_current, col_targets = st.columns(2)
    with col_current:
        st.subheader("Current Positions")
        _render_table(current_rows, "No current positions.")
    with col_targets:
        st.subheader("Target Allocations")
        _render_table(target_rows, "No target allocations.")

    st.subheader("Allocation Comparison")
    _render_allocation_comparison_chart(allocation_rows)
    _render_table(
        allocation_rows,
        "No allocation comparison is available.",
    )

    st.subheader("Proposed Trades")
    _render_table(trade_rows, "No rebalance trades were proposed.")

    if breach_rows:
        st.subheader("Risk Breaches")
        st.dataframe(
            risk_breach_display_rows(breach_rows),
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("Downloads"):
        st.json(result.model_dump(mode="json"))
        st.download_button(
            "Download JSON",
            data=result_json_download(result),
            file_name="rebalance_check_result.json",
            mime="application/json",
        )
        st.download_button(
            "Download request JSON",
            data=request_json_download(request),
            file_name="rebalance_request.json",
            mime="application/json",
        )
        st.download_button(
            "Download report Markdown",
            data=result_markdown_report_download(result, request=request),
            file_name="rebalance_report.md",
            mime="text/markdown",
        )
        st.download_button(
            "Download report ZIP",
            data=result_report_zip_download(result, request=request),
            file_name="rebalance_report.zip",
            mime="application/zip",
        )
        st.download_button(
            "Download summary CSV",
            data=table_csv_download([summary]),
            file_name="rebalance_summary.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download current positions CSV",
            data=table_csv_download(
                current_rows,
                fieldnames=["symbol", "qty", "currency", "last", "fx_rate_jpy", "value_jpy"],
            ),
            file_name="rebalance_current_positions.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download target allocations CSV",
            data=table_csv_download(
                target_rows,
                fieldnames=["symbol", "currency", "target_weight"],
            ),
            file_name="rebalance_target_allocations.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download allocation comparison CSV",
            data=table_csv_download(
                allocation_rows,
                fieldnames=["symbol", "current_weight", "target_weight", "drift"],
            ),
            file_name="rebalance_allocation_comparison.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download proposed trades CSV",
            data=table_csv_download(
                trade_rows,
                fieldnames=["symbol", "side", "qty", "price_hint", "currency"],
            ),
            file_name="rebalance_proposed_trades.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download risk breaches CSV",
            data=table_csv_download(breach_rows, fieldnames=["breach"]),
            file_name="rebalance_risk_breaches.csv",
            mime="text/csv",
        )


def rebalance_result_from_state() -> tuple[PortfolioRiskResult, RebalanceCheckRequest] | None:
    result = st.session_state.get(REBALANCE_RESULT_STATE_KEY)
    request = st.session_state.get(REBALANCE_REQUEST_STATE_KEY)
    if isinstance(result, PortfolioRiskResult) and isinstance(request, RebalanceCheckRequest):
        return result, request
    return None


def _render_table(rows: list[dict[str, str]], empty_message: str) -> None:
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info(empty_message)


def rebalance_flow_rows(summary: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"step": "現在", "value": f"{summary.get('total_value_jpy', '')} JPY"},
        {"step": "目標", "value": "target allocations"},
        {"step": "売買案", "value": f"{summary.get('trade_count', '0')} trades"},
        {"step": "Risk", "value": summary.get("risk_status", "")},
    ]


def _render_rebalance_flow(summary: dict[str, str]) -> None:
    step_cols = st.columns(4)
    for col, row in zip(step_cols, rebalance_flow_rows(summary), strict=True):
        col.caption(row["step"])
        col.write(row["value"])


def allocation_chart_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in rows:
        symbol = row.get("symbol", "")
        for field, label in (
            ("current_weight", "現在"),
            ("target_weight", "目標"),
        ):
            value = _optional_decimal_from_text(row.get(field, ""))
            if value is None:
                continue
            records.append(
                {
                    "symbol": symbol,
                    "type": label,
                    "weight": float(value),
                }
            )
    return pd.DataFrame(records)


def _render_allocation_comparison_chart(rows: list[dict[str, str]]) -> None:
    frame = allocation_chart_frame(rows)
    if frame.empty:
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadius=3)
        .encode(
            x=alt.X("weight:Q", title="Weight (%)"),
            y=alt.Y("symbol:N", title=None, sort=None),
            color=alt.Color("type:N", title="配分"),
            yOffset="type:N",
            tooltip=[
                alt.Tooltip("symbol:N", title="銘柄"),
                alt.Tooltip("type:N", title="配分"),
                alt.Tooltip("weight:Q", title="Weight (%)"),
            ],
        )
        .properties(height=max(120, 54 * len(rows)))
    )
    st.altair_chart(chart, use_container_width=True)


def risk_breach_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "breach": row.get("breach", ""),
            "確認ポイント": risk_breach_message(row.get("breach", "")),
        }
        for row in rows
    ]


def risk_breach_message(breach: str) -> str:
    if breach.startswith("R5:min_dividend_yield:"):
        symbol = breach.rsplit(":", maxsplit=1)[-1]
        return f"{symbol} は配当利回りの条件を満たしていない可能性があります。"
    if breach == "R3:max_concentration":
        return "1銘柄への集中度が高くなっています。目標配分を確認してください。"
    if breach.startswith("R2:cash"):
        return "現金残高に関する制約を確認してください。"
    return "Risk ルールに抵触しています。条件と入力を確認してください。"


def _render_investment_score_section(preview: MarketDataPreview, symbol_label: str) -> None:
    rows = investment_score_display_rows(preview.investment_score_rows)
    if not rows:
        st.info("No investment score rows.")
        return

    row = rows[0]
    score_col, band_col, forecast_col, quality_col, risk_col = st.columns(5)
    score_col.metric("総合スコア", row.get("総合スコア", ""))
    band_col.metric("見方", row.get("見方", ""))
    forecast_col.metric("予測一致", row.get("予測一致", ""))
    quality_col.metric("データ品質", row.get("データ品質", ""))
    risk_col.metric("Risk", row.get("Risk", ""))

    warning = row.get("注意点", "")
    if warning:
        st.warning(warning)
    else:
        st.info("大きな注意点はありません。スコアの内訳も確認してください。")
    for line in investment_score_summary_lines(row):
        st.caption(line)
    _render_score_breakdown_chart(score_component_rows(row))

    with st.expander("Investment Score details / downloads"):
        _render_target_symbol_caption(symbol_label)
        _render_table(rows, "No investment score rows.")
        col_json, col_csv = st.columns(2)
        col_json.download_button(
            "Download investment score JSON",
            data=investment_score_json_download(preview.investment_score_rows),
            file_name="investment_score.json",
            mime="application/json",
        )
        col_csv.download_button(
            "Download investment score CSV",
            data=investment_score_csv_download(preview.investment_score_rows),
            file_name="investment_score.csv",
            mime="text/csv",
        )


def investment_score_summary_lines(row: dict[str, str]) -> list[str]:
    lines = [
        f"{row.get('銘柄', 'この銘柄')} は「{row.get('見方', '要確認')}」として確認できます。",
    ]
    warning = row.get("注意点", "")
    if warning:
        lines.append(f"注意点: {warning}。")
    else:
        lines.append("大きな注意点はありません。")
    note = row.get("補足", "")
    if note:
        lines.append(note)
    return lines[:3]


def score_component_rows(row: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"要素": "Screening", "スコア": row.get("Screening", "")},
        {"要素": "Forecast", "スコア": row.get("予測一致", "")},
        {"要素": "Risk", "スコア": row.get("Risk", "")},
        {"要素": "Data Quality", "スコア": row.get("データ品質", "")},
    ]


def _render_score_breakdown_chart(rows: list[dict[str, str]]) -> None:
    frame = pd.DataFrame(rows)
    frame["score"] = pd.to_numeric(frame["スコア"], errors="coerce")
    frame = frame.dropna(subset=["score"])
    if frame.empty:
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadius=4)
        .encode(
            x=alt.X("score:Q", title="Score", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("要素:N", title=None, sort=None),
            color=alt.Color("要素:N", legend=None),
            tooltip=[
                alt.Tooltip("要素:N", title="要素"),
                alt.Tooltip("score:Q", title="スコア"),
            ],
        )
        .properties(height=150)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_market_chart(
    rows: list[dict[str, str]],
    *,
    currency: str = "",
    title: str = "",
) -> None:
    if not rows:
        st.info("No chart rows.")
        return
    y_axis_title = f"終値 ({currency})" if currency else "終値"
    chart_data = market_chart_long_frame(rows)
    boundary_data = forecast_boundary_frame(rows)
    legend_data = chart_data[["series_label", "line_label"]].drop_duplicates().copy()
    line_type_legend_data = pd.DataFrame(
        [
            {"line_label": "実績", "description": "実線: 実績価格"},
            {"line_label": "予測", "description": "破線: 予測モデル"},
        ]
    )
    disabled_series = alt.selection_point(
        fields=["series_label"],
        on="click",
        toggle="true",
        empty=False,
    )
    chart = (
        alt.Chart(chart_data)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Date", axis=alt.Axis(format="%m/%d", labelAngle=0)),
            y=alt.Y("value:Q", title=y_axis_title, scale=alt.Scale(zero=False)),
            color=alt.Color(
                "series_label:N",
                title="価格・モデル",
                legend=None,
            ),
            strokeDash=alt.StrokeDash(
                "line_label:N",
                title="実績/予測",
                scale=alt.Scale(domain=["実績", "予測"], range=[[1, 0], [6, 4]]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("date:T", title="日付"),
                alt.Tooltip("series_label:N", title="価格・モデル"),
                alt.Tooltip("value:Q", title="終値"),
                alt.Tooltip("line_label:N", title="実績/予測"),
            ],
            opacity=alt.condition(disabled_series, alt.value(0.18), alt.value(1.0)),
        )
        .properties(height=540, width=1400)
    )
    if not boundary_data.empty:
        boundary_rule = (
            alt.Chart(boundary_data)
            .mark_rule(color="#f59e0b", opacity=0.65, strokeDash=[4, 4])
            .encode(x="date:T")
        )
        chart = chart + boundary_rule
    series_legend_base = alt.Chart(legend_data).encode(
        y=alt.Y("series_label:N", title=None, axis=None, sort=None),
        color=alt.Color("series_label:N", title="価格・モデル", legend=None),
        opacity=alt.condition(disabled_series, alt.value(0.25), alt.value(1.0)),
        tooltip=[
            alt.Tooltip("series_label:N", title="価格・モデル"),
            alt.Tooltip("line_label:N", title="実績/予測"),
        ],
    )
    series_legend = series_legend_base.mark_point(filled=True, size=95).encode(
        x=alt.value(12)
    ) + series_legend_base.mark_text(align="left", baseline="middle", dx=16, fontSize=12).encode(
        x=alt.value(12),
        text="series_label:N",
    )
    line_type_legend_base = alt.Chart(line_type_legend_data).encode(
        y=alt.Y("description:N", title=None, axis=None, sort=None),
        strokeDash=alt.StrokeDash(
            "line_label:N",
            scale=alt.Scale(domain=["実績", "予測"], range=[[1, 0], [6, 4]]),
            legend=None,
        ),
    )
    line_type_legend = line_type_legend_base.mark_rule(color="#c9d1dc", strokeWidth=2).encode(
        x=alt.value(12),
        x2=alt.value(46),
    ) + line_type_legend_base.mark_text(
        align="left",
        baseline="middle",
        dx=52,
        fontSize=12,
        color="#c9d1dc",
    ).encode(
        x=alt.value(12),
        text="description:N",
    )
    legend = alt.vconcat(
        series_legend.properties(title="価格・モデル", height=190, width=190),
        line_type_legend.properties(title="実績/予測", height=60, width=190),
        spacing=10,
    )
    combined_chart = (
        alt.hconcat(chart, legend, spacing=10)
        .add_params(disabled_series)
        .resolve_scale(color="shared")
        .configure(background="#090d14")
        .configure_view(fill="#101722", stroke="#344155")
        .configure_axis(
            domainColor="#3b4556",
            gridColor="#2b3646",
            labelColor="#c9d1dc",
            titleColor="#c9d1dc",
            tickColor="#3b4556",
        )
        .configure_title(color="#e5edf7", fontSize=13, anchor="start", offset=8)
        .properties(title=title or None)
    )
    st.altair_chart(
        combined_chart,
        use_container_width=True,
    )


def _render_provider_error_summary(rows: list[dict[str, str]]) -> None:
    for row in rows:
        st.warning(f"{row.get('code', 'ERROR')}: {row.get('message', '')}")
        details = row.get("details", "")
        if details:
            st.code(details, language="json")


def market_chart_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows).set_index("ts")
    frame.index = pd.to_datetime(frame.index).date
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def market_chart_long_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = market_chart_frame(rows).reset_index(names="date")
    long_frame = frame.melt(id_vars="date", var_name="series", value_name="value")
    long_frame = long_frame.dropna(subset=["value"])
    long_frame["line_type"] = long_frame["series"].map(
        lambda series: "actual" if series == "close" else "forecast"
    )
    long_frame["line_label"] = long_frame["line_type"].map(
        lambda line_type: "実績" if line_type == "actual" else "予測"
    )
    long_frame["series_label"] = long_frame["series"].map(_forecast_series_label)
    return long_frame


def forecast_boundary_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = market_chart_frame(rows).reset_index(names="date")
    actual_rows = frame.dropna(subset=["close"])
    if actual_rows.empty:
        return pd.DataFrame(columns=["date"])
    latest_actual_date = actual_rows["date"].max()
    return pd.DataFrame([{"date": latest_actual_date}])


def forecast_metric_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "モデル": _forecast_series_label(row.get("model", "")),
            "銘柄": row.get("symbol", ""),
            "予測日数": row.get("horizon_days", ""),
            "予測終値": row.get("forecast_close", ""),
            "MAE(小さいほど良い)": row.get("mae", ""),
            "RMSE(小さいほど良い)": row.get("rmse", ""),
            "方向一致率(高いほど良い)": row.get("direction_accuracy", ""),
            "評価サンプル数": row.get("sample_count", ""),
        }
        for row in rows
    ]


def forecast_chart_summary(
    consensus_rows: list[dict[str, str]],
    metric_rows: list[dict[str, str]],
) -> list[str]:
    if not consensus_rows:
        return ["予測を表示するには、もう少し価格データが必要です。"]

    row = consensus_rows[0]
    agreement = _forecast_agreement_label(row.get("agreement", ""))
    range_pct = row.get("forecast_range_pct") or "未計算"
    model_count = row.get("model_count") or "0"
    messages = [
        f"{model_count} つの予測モデルの見方は「{agreement}」です。予測の開きは {range_pct} です。",
        "実線はこれまでの価格、点線はモデルごとの予測です。点線同士が近いほど、モデルの見方が近い状態です。",
    ]
    metric_messages = forecast_metric_summary(metric_rows)
    if metric_messages:
        messages.append(metric_messages[0])
    return messages


def forecast_consensus_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "銘柄": row.get("symbol", ""),
            "予測日数": row.get("horizon_days", ""),
            "モデル数": row.get("model_count", ""),
            "平均予測": row.get("ensemble_forecast_close", ""),
            "中央値予測": row.get("median_forecast_close", ""),
            "予測下限": row.get("min_forecast_close", ""),
            "予測上限": row.get("max_forecast_close", ""),
            "予測の開き": row.get("forecast_range", ""),
            "予測の開き(%)": row.get("forecast_range_pct", ""),
            "モデル一致度": _forecast_agreement_label(row.get("agreement", "")),
        }
        for row in rows
    ]


def investment_score_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "順位": row.get("rank", ""),
            "銘柄": row.get("symbol", ""),
            "銘柄名": symbol_name(row.get("symbol", "")) or "",
            "総合スコア": row.get("total_score", ""),
            "見方": _investment_score_band_label(row.get("score_band", "")),
            "Screening": row.get("screening_score", ""),
            "予測一致": row.get("forecast_agreement_score", ""),
            "データ品質": row.get("data_quality_score", ""),
            "Risk": row.get("risk_signal_score", "") or "未接続",
            "注意点": _investment_warning_label(row.get("warnings", "")),
            "補足": row.get("note", ""),
        }
        for row in rows
    ]


def forecast_metric_summary(rows: list[dict[str, str]]) -> list[str]:
    candidates: list[tuple[Decimal, dict[str, str]]] = []
    for row in rows:
        rmse = _optional_decimal_from_text(row.get("rmse", ""))
        sample_count = _int_from_text(row.get("sample_count", ""))
        if rmse is None or sample_count <= 0:
            continue
        candidates.append((rmse, row))

    if not candidates:
        return [
            "予測評価に必要なサンプルがまだ不足しています。日付範囲を広げるとモデル比較が安定します。"
        ]

    best_rmse, best_row = min(candidates, key=lambda item: item[0])
    best_label = _forecast_series_label(best_row.get("model", ""))
    direction = best_row.get("direction_accuracy") or "未計算"
    return [
        (
            f"今回の比較では「{best_label}」が RMSE {best_rmse} で最も誤差が小さいです。"
            f"方向一致率は {direction} です。"
        ),
        "誤差と方向一致率で、モデルの当たりやすさを比べます。",
    ]


def _forecast_series_label(series: str) -> str:
    if series == "close":
        return FORECAST_ACTUAL_LABEL
    return forecast_model_display_name(series)


def _forecast_agreement_label(value: str) -> str:
    labels = {
        "HIGH": "高い",
        "MEDIUM": "中くらい",
        "LOW": "低い",
        "UNKNOWN": "未判定",
    }
    return labels.get(value, value)


def _investment_score_band_label(value: str) -> str:
    labels = {
        "STRONG": "強め",
        "BALANCED": "バランス型",
        "CAUTION": "注意して確認",
        "REVIEW": "要確認",
    }
    return labels.get(value, value)


def _investment_warning_label(value: str) -> str:
    if not value:
        return ""
    labels = {
        "data_quality:warn": "データ品質に注意",
        "data_quality:block": "データ不足が大きい",
        "model_disagreement:high": "モデルの見方が割れています",
        "model_count:insufficient": "予測モデル数が少なめです",
    }
    return ", ".join(labels.get(item.strip(), item.strip()) for item in value.split(","))


def _optional_decimal_from_text(value: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace("%", ""))
    except InvalidOperation:
        return None


def _int_from_text(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _rank_investment_score_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    ranked = sorted(
        rows,
        key=lambda row: _optional_decimal_from_text(row.get("total_score", "")) or Decimal("-1"),
        reverse=True,
    )
    return [
        {
            **row,
            "rank": str(index),
        }
        for index, row in enumerate(ranked, start=1)
    ]


def apply_ranking_weight_preset(
    rows: list[dict[str, str]],
    preset: str,
) -> list[dict[str, str]]:
    weights = RANKING_WEIGHT_PRESETS[preset]
    preset_label = ranking_weight_preset_label(preset)
    reweighted_rows: list[dict[str, str]] = []
    for row in rows:
        total = Decimal("0")
        for field, weight in weights.items():
            component_score = _optional_decimal_from_text(row.get(field, "")) or Decimal("0")
            total += component_score * weight
        warnings = row.get("warnings", "")
        reweighted_rows.append(
            {
                **row,
                "total_score": _format_score(total),
                "score_band": _score_band_for_total(total, warnings),
                "note": f"{preset_label}で並べ替えています。売買推奨ではなく、深掘り候補の整理です。",
            }
        )
    return _rank_investment_score_rows(reweighted_rows)


def ranking_weight_preset_label(preset: str) -> str:
    return RANKING_WEIGHT_PRESET_LABELS.get(preset, preset)


def _score_band_for_total(total_score: Decimal, warnings: str) -> str:
    warning_items = {item.strip() for item in warnings.split(",") if item.strip()}
    if "data_quality:block" in warning_items:
        return "REVIEW"
    if total_score >= Decimal("75") and not warning_items:
        return "STRONG"
    if warning_items and total_score < Decimal("65"):
        return "CAUTION"
    if total_score >= Decimal("55"):
        return "BALANCED"
    if total_score >= Decimal("40"):
        return "CAUTION"
    return "REVIEW"


def _format_score(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"))
    return format(rounded.normalize(), "f")


def _metadata_value(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        if row.get("field") == field:
            return row.get("value", "")
    return ""


def _market_data_as_of(preview: MarketDataPreview) -> str:
    if preview.bars:
        return preview.bars[-1].ts.date().isoformat()
    for row in preview.ohlcv_rows:
        last_ts = row.get("last_ts", "")
        if last_ts:
            return last_ts[:10]
    for row in preview.quote_rows:
        ts = row.get("ts", "")
        if ts:
            return ts[:10]
    return ""


def _market_data_preview_symbol_label(preview: MarketDataPreview) -> str:
    symbol = _market_data_preview_symbol(preview)
    if not symbol:
        return "selected symbol"
    name = symbol_name(symbol)
    if name:
        return f"{symbol} - {name}"
    return symbol


def _market_data_preview_symbol(preview: MarketDataPreview) -> str:
    if preview.bars:
        return preview.bars[0].symbol.raw
    for rows in (
        getattr(preview, "investment_score_rows", []),
        preview.screening_rows,
        preview.ohlcv_rows,
        preview.quote_rows,
        preview.feature_rows,
    ):
        for row in rows:
            symbol = row.get("symbol", "").strip()
            if symbol:
                return symbol
    return ""


def _render_target_symbol_caption(symbol_label: str) -> None:
    st.caption(f"対象: {symbol_label}")


if __name__ == "__main__":
    main()
