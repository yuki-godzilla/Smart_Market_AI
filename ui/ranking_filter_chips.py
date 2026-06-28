from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import streamlit as st

from backend.marketdata.ranking_universe_policy import symbol_allowed_by_ranking_universe_policy
from ui.content.ranking_texts import (
    RANKING_INVESTMENT_THEME_LABELS,
    RANKING_OFFICIAL_SECTOR_LABELS,
)
from ui.ranking import (
    RANKING_PRODUCT_ALL,
    RANKING_PRODUCT_ETF,
    RANKING_PRODUCT_MUTUAL_FUND,
    RANKING_PRODUCT_STOCK,
)

# Exploration filters are applied immediately to ranking candidates.
# Keep the old draft/applied keys as compatibility aliases for existing sessions/tests,
# but do not expose a dirty/intermediate state in the UI.
DRAFT_COUNTRY_FILTER_STATE_KEY = "market_data_ranking_draft_country_market_filters"
DRAFT_SECTOR_FILTER_STATE_KEY = "market_data_ranking_draft_sector_chip_filters"
DRAFT_THEME_FILTER_STATE_KEY = "market_data_ranking_draft_theme_chip_filters"
APPLIED_COUNTRY_FILTER_STATE_KEY = "market_data_ranking_applied_country_market_filters"
APPLIED_SECTOR_FILTER_STATE_KEY = "market_data_ranking_applied_sector_chip_filters"
APPLIED_THEME_FILTER_STATE_KEY = "market_data_ranking_applied_theme_chip_filters"
ACTIVE_DIALOG_STATE_KEY = "market_data_ranking_active_filter_dialog"
PENDING_DIALOG_SIGNATURE_STATE_KEY = "market_data_ranking_pending_dialog_signature"
SECTOR_VIEW_STATE_KEY = "market_data_ranking_sector_chip_view"
THEME_VIEW_STATE_KEY = "market_data_ranking_theme_chip_view"
BASELINE_ROWS_CACHE_STATE_KEY = "market_data_ranking_static_chip_baseline_rows_cache_v2"
STATIC_OPTION_COUNTS_CACHE_STATE_KEY = "market_data_ranking_static_chip_option_counts_cache_v2"

# Legacy keys that used to be selectbox filters. They are now represented by chips.
LEGACY_EXPLORATION_SELECT_KEYS = (
    "market_data_ranking_official_sector",
    "market_data_ranking_theme",
)

COUNTRY_MARKET_OPTIONS: tuple[tuple[str, str], ...] = (
    ("jp", "日本"),
    ("us", "米国"),
    ("hong_kong", "中国・香港"),
    ("korea", "韓国"),
    ("singapore", "シンガポール"),
    ("thailand", "タイ"),
    ("malaysia", "マレーシア"),
    ("indonesia", "インドネシア"),
    ("vietnam", "ベトナム"),
)

MAJOR_SECTOR_VALUES: tuple[str, ...] = (
    "technology",
    "communication",
    "consumer",
    "financial",
    "healthcare",
    "energy",
    "industrial",
    "materials",
    "real_estate",
    "utilities",
)
ETF_SECTOR_VALUES: tuple[str, ...] = ("index", "bond", "commodity", "currency", "reit")
MAJOR_THEME_VALUES: tuple[str, ...] = (
    "high_dividend",
    "dividend",
    "growth",
    "value",
    "technology",
    "semiconductor",
    "bond",
    "commodity",
    "reit",
    "emerging",
    "china",
    "india",
)


@dataclass(frozen=True)
class FilterOption:
    value: str
    label: str
    count: int = 0


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, tuple | set):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


def _selected(key: str) -> list[str]:
    return _as_list(st.session_state.get(key, []))


def _set_selected(key: str, values: Sequence[str]) -> None:
    st.session_state[key] = [str(value) for value in values if str(value)]


def sync_ranking_exploration_legacy_state() -> None:
    """Keep removed legacy selectboxes from silently filtering together with chips."""
    for key in LEGACY_EXPLORATION_SELECT_KEYS:
        st.session_state[key] = "all"


def _ensure_draft_applied_state() -> None:
    # Migration from older one-state chip keys.
    legacy_to_draft = {
        "market_data_ranking_country_market_filters": DRAFT_COUNTRY_FILTER_STATE_KEY,
        "market_data_ranking_sector_chip_filters": DRAFT_SECTOR_FILTER_STATE_KEY,
        "market_data_ranking_theme_chip_filters": DRAFT_THEME_FILTER_STATE_KEY,
    }
    for legacy_key, draft_key in legacy_to_draft.items():
        if draft_key not in st.session_state and legacy_key in st.session_state:
            _set_selected(draft_key, _selected(legacy_key))

    for draft_key, applied_key in (
        (DRAFT_COUNTRY_FILTER_STATE_KEY, APPLIED_COUNTRY_FILTER_STATE_KEY),
        (DRAFT_SECTOR_FILTER_STATE_KEY, APPLIED_SECTOR_FILTER_STATE_KEY),
        (DRAFT_THEME_FILTER_STATE_KEY, APPLIED_THEME_FILTER_STATE_KEY),
    ):
        # Apply exploration filters immediately.  The applied key is retained only
        # for compatibility with existing cache/signature callers.
        st.session_state.setdefault(draft_key, _selected(applied_key))
        _set_selected(applied_key, _selected(draft_key))


def draft_exploration_filters() -> dict[str, list[str]]:
    _ensure_draft_applied_state()
    return {
        "country_market": _selected(DRAFT_COUNTRY_FILTER_STATE_KEY),
        "sector": _selected(DRAFT_SECTOR_FILTER_STATE_KEY),
        "theme": _selected(DRAFT_THEME_FILTER_STATE_KEY),
    }


def applied_exploration_filters() -> dict[str, list[str]]:
    _ensure_draft_applied_state()
    return {
        "country_market": _selected(APPLIED_COUNTRY_FILTER_STATE_KEY),
        "sector": _selected(APPLIED_SECTOR_FILTER_STATE_KEY),
        "theme": _selected(APPLIED_THEME_FILTER_STATE_KEY),
    }


def exploration_filters_dirty() -> bool:
    _ensure_draft_applied_state()
    return False


def ranking_filter_dialog_is_open() -> bool:
    return bool(st.session_state.get(ACTIVE_DIALOG_STATE_KEY))


def apply_draft_exploration_filters() -> None:
    _ensure_draft_applied_state()
    _set_selected(APPLIED_COUNTRY_FILTER_STATE_KEY, _selected(DRAFT_COUNTRY_FILTER_STATE_KEY))
    _set_selected(APPLIED_SECTOR_FILTER_STATE_KEY, _selected(DRAFT_SECTOR_FILTER_STATE_KEY))
    _set_selected(APPLIED_THEME_FILTER_STATE_KEY, _selected(DRAFT_THEME_FILTER_STATE_KEY))
    st.session_state.pop(ACTIVE_DIALOG_STATE_KEY, None)
    sync_ranking_exploration_legacy_state()


def clear_ranking_exploration_filters(*, apply: bool = False) -> None:
    _ensure_draft_applied_state()
    _set_selected(DRAFT_COUNTRY_FILTER_STATE_KEY, [])
    _set_selected(DRAFT_SECTOR_FILTER_STATE_KEY, [])
    _set_selected(DRAFT_THEME_FILTER_STATE_KEY, [])
    if apply:
        _set_selected(APPLIED_COUNTRY_FILTER_STATE_KEY, [])
        _set_selected(APPLIED_SECTOR_FILTER_STATE_KEY, [])
        _set_selected(APPLIED_THEME_FILTER_STATE_KEY, [])
    st.session_state.pop(ACTIVE_DIALOG_STATE_KEY, None)
    sync_ranking_exploration_legacy_state()


def _csv_values(value: object) -> set[str]:
    text = str(value or "")
    values: set[str] = set()
    for separator in (",", ";", "|"):
        if separator in text:
            for item in text.split(separator):
                item = item.strip()
                if item:
                    values.add(item)
            return values
    text = text.strip()
    return {text} if text else set()


def _row_theme_values(row: Mapping[str, str]) -> set[str]:
    values: set[str] = set()
    for field in (
        "theme",
        "tags",
        "smai_theme_tags",
        "index_family",
        "asset_class",
        "dividend_category",
    ):
        values.update(_csv_values(row.get(field, "")))
    if str(row.get("is_leveraged", "")).lower() == "true":
        values.add("leveraged")
    if str(row.get("is_inverse", "")).lower() == "true":
        values.add("inverse")
    if str(row.get("is_hedged", "")).lower() == "true":
        values.add("hedged")
    expense = str(row.get("expense_ratio_pct", "")).strip()
    try:
        if expense and float(expense) <= 0.2:
            values.add("low_cost")
    except ValueError:
        pass
    return values


def _row_sector_values(row: Mapping[str, str]) -> set[str]:
    values: set[str] = set()
    for field in (
        "sector",
        "theme",
        "tags",
        "smai_theme_tags",
        "asset_class",
        "index_family",
        "sector_gics",
        "industry_gics",
        "tse_33_industry",
        "topix_17",
    ):
        values.update(_csv_values(row.get(field, "")))
    asset_type = str(row.get("asset_type", ""))
    if asset_type == "reit":
        values.add("reit")
        values.add("real_estate")
    return values


def _row_matches_country(row: Mapping[str, str], selected: Sequence[str]) -> bool:
    if not selected:
        return True
    market = str(row.get("market", ""))
    if market in selected:
        return True
    if "hong_kong" in selected and market in {"china", "hk"}:
        return True
    return False


def _row_matches_values(row_values: set[str], selected: Sequence[str]) -> bool:
    return not selected or any(value in row_values for value in selected)


def apply_ranking_applied_exploration_filters(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    filters = applied_exploration_filters()
    selected_countries = filters["country_market"]
    selected_sectors = filters["sector"]
    selected_themes = filters["theme"]
    if not selected_countries and not selected_sectors and not selected_themes:
        return rows
    filtered: list[dict[str, str]] = []
    for row in rows:
        if not _row_matches_country(row, selected_countries):
            continue
        if not _row_matches_values(_row_sector_values(row), selected_sectors):
            continue
        if not _row_matches_values(_row_theme_values(row), selected_themes):
            continue
        filtered.append(row)
    return filtered


# Backward-compatible alias for older tests/callers.
def apply_ranking_exploration_filters(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return apply_ranking_applied_exploration_filters(rows)


def _rows_signature(rows: Sequence[dict[str, str]]) -> tuple[object, ...]:
    if not rows:
        return (0,)
    symbols = [str(row.get("symbol", "")) for row in rows]
    return (len(rows), tuple(symbols[:8]), tuple(symbols[-8:]))


def _static_counts_cache_key(
    rows: Sequence[dict[str, str]], product_type: str, category: str, view: str = ""
) -> tuple[object, ...]:
    return (_rows_signature(rows), product_type, category, view)


def _matches_product(row: Mapping[str, str], product_type: str) -> bool:
    if product_type == RANKING_PRODUCT_ALL:
        return True
    asset_type = str(row.get("asset_type", ""))
    if product_type == RANKING_PRODUCT_STOCK:
        return asset_type in {"stock", "adr"}
    if product_type == RANKING_PRODUCT_ETF:
        return asset_type == "etf"
    if product_type == RANKING_PRODUCT_MUTUAL_FUND:
        return asset_type == "mutual_fund"
    return asset_type == product_type


def _baseline_rows(rows: Sequence[dict[str, str]], product_type: str) -> list[dict[str, str]]:
    cache_key = (_rows_signature(rows), product_type)
    try:
        cache = st.session_state.setdefault(BASELINE_ROWS_CACHE_STATE_KEY, {})
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        cache = None
    baseline = [
        row
        for row in rows
        if symbol_allowed_by_ranking_universe_policy(row) and _matches_product(row, product_type)
    ]
    if cache is not None:
        cache.clear()
        cache[cache_key] = baseline
    return baseline


def _country_options(rows: Sequence[dict[str, str]], product_type: str) -> list[FilterOption]:
    cache_key = _static_counts_cache_key(rows, product_type, "country")
    cache = st.session_state.setdefault(STATIC_OPTION_COUNTS_CACHE_STATE_KEY, {})
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    base_rows = _baseline_rows(rows, product_type)
    options: list[FilterOption] = []
    for value, label in COUNTRY_MARKET_OPTIONS:
        count = sum(1 for row in base_rows if _row_matches_country(row, [value]))
        options.append(FilterOption(value=value, label=label, count=count))
    cache.clear()
    cache[cache_key] = options
    return options


def _sector_options(
    rows: Sequence[dict[str, str]], product_type: str, view: str
) -> list[FilterOption]:
    cache_key = _static_counts_cache_key(rows, product_type, "sector", view)
    cache = st.session_state.setdefault(STATIC_OPTION_COUNTS_CACHE_STATE_KEY, {})
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    base_rows = _baseline_rows(rows, product_type)
    counts: dict[str, int] = {}
    for row in base_rows:
        for value in _row_sector_values(row):
            counts[value] = counts.get(value, 0) + 1
    if view == "major":
        values = list(MAJOR_SECTOR_VALUES)
    elif view == "etf":
        values = list(ETF_SECTOR_VALUES)
    else:
        excluded = set(MAJOR_SECTOR_VALUES) | set(ETF_SECTOR_VALUES) | {"all", "balanced"}
        values = sorted(
            value
            for value, count in counts.items()
            if value and value not in excluded and count > 0
        )[:80]
    options = [
        FilterOption(
            value=value,
            label=RANKING_OFFICIAL_SECTOR_LABELS.get(
                value,
                RANKING_INVESTMENT_THEME_LABELS.get(value, value),
            ),
            count=counts.get(value, 0),
        )
        for value in values
    ]
    cache[cache_key] = options
    return options


def _theme_options(
    rows: Sequence[dict[str, str]], product_type: str, view: str
) -> list[FilterOption]:
    cache_key = _static_counts_cache_key(rows, product_type, "theme", view)
    cache = st.session_state.setdefault(STATIC_OPTION_COUNTS_CACHE_STATE_KEY, {})
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    base_rows = _baseline_rows(rows, product_type)
    counts: dict[str, int] = {}
    for row in base_rows:
        for value in _row_theme_values(row):
            counts[value] = counts.get(value, 0) + 1
    if view == "major":
        values = list(MAJOR_THEME_VALUES)
    else:
        excluded = set(MAJOR_THEME_VALUES) | {"all", "balanced"}
        values = sorted(
            value
            for value, count in counts.items()
            if value and value not in excluded and count > 0
        )[:80]
    options = [
        FilterOption(
            value=value,
            label=RANKING_INVESTMENT_THEME_LABELS.get(
                value,
                RANKING_OFFICIAL_SECTOR_LABELS.get(value, value),
            ),
            count=counts.get(value, 0),
        )
        for value in values
    ]
    cache[cache_key] = options
    return options


def _format_selected(labels_by_value: Mapping[str, str], values: Sequence[str]) -> str:
    if not values:
        return "指定なし"
    labels = [labels_by_value.get(value, value) for value in values]
    if len(labels) <= 2:
        return ", ".join(labels)
    return f"{', '.join(labels[:2])} +{len(labels) - 2}"


def _count_map_from_options(options: Sequence[FilterOption]) -> dict[str, int]:
    return {option.value: option.count for option in options}


def draft_estimated_candidate_count(rows: Sequence[dict[str, str]], *, product_type: str) -> int:
    """Lightweight draft estimate used by the ranking candidate card.

    This intentionally uses static/product-only option counts. It must not apply all
    detail filters or rebuild filtered rows; exact counts are produced only after
    the explicit candidate update action.
    """
    filters = draft_exploration_filters()
    estimates: list[int] = []
    countries = filters.get("country_market", [])
    if countries:
        counts = _count_map_from_options(_country_options(rows, product_type))
        estimates.append(sum(counts.get(value, 0) for value in countries))
    sectors = filters.get("sector", [])
    if sectors:
        # Use one baseline sector count map over the product-only universe. Values can overlap,
        # so this is an upper-bound-ish estimate; using min across categories keeps it conservative.
        base_rows = _baseline_rows(rows, product_type)
        counts: dict[str, int] = {}
        for row in base_rows:
            for value in _row_sector_values(row):
                counts[value] = counts.get(value, 0) + 1
        estimates.append(sum(counts.get(value, 0) for value in sectors))
    themes = filters.get("theme", [])
    if themes:
        base_rows = _baseline_rows(rows, product_type)
        counts: dict[str, int] = {}
        for row in base_rows:
            for value in _row_theme_values(row):
                counts[value] = counts.get(value, 0) + 1
        estimates.append(sum(counts.get(value, 0) for value in themes))
    if not estimates:
        return len(_baseline_rows(rows, product_type))
    return max(min(estimates), 0)


def exploration_filter_chip_labels(*, draft: bool = False) -> list[str]:
    filters = draft_exploration_filters()
    country_labels = dict(COUNTRY_MARKET_OPTIONS)
    sector_labels = {**RANKING_OFFICIAL_SECTOR_LABELS, **RANKING_INVESTMENT_THEME_LABELS}
    theme_labels = {**RANKING_INVESTMENT_THEME_LABELS, **RANKING_OFFICIAL_SECTOR_LABELS}
    chips: list[str] = []
    if filters.get("country_market"):
        chips.append("国・市場: " + _format_selected(country_labels, filters["country_market"]))
    if filters.get("sector"):
        chips.append("業種: " + _format_selected(sector_labels, filters["sector"]))
    if filters.get("theme"):
        chips.append("テーマ: " + _format_selected(theme_labels, filters["theme"]))
    return chips


def _card_html(title: str, selected_text: str, *, active: bool, dirty: bool) -> str:
    class_names = ["smai-filter-card"]
    if active:
        class_names.append("smai-filter-card--active")
    badge = ""
    return (
        f'<div class="{" ".join(class_names)}">'
        f'<span class="smai-filter-card-title">{html.escape(title)}</span>'
        f"<strong>{html.escape(selected_text)}</strong>"
        f"{badge}"
        "</div>"
    )


def _ensure_filter_card_css() -> None:
    st.markdown(
        """
        <style>
        .smai-exploration-filter-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.65rem;
            margin: 0.3rem 0 0.85rem 0;
        }

        .smai-filter-card {
            position: relative;
            min-height: 4.8rem;
            padding: 0.78rem 0.95rem;
            border-radius: 0.95rem;
            border: 1px solid rgba(68, 156, 255, 0.32);
            background: linear-gradient(135deg, rgba(9, 21, 42, 0.92), rgba(13, 42, 67, 0.72));
            box-shadow: 0 0.25rem 1.1rem rgba(0, 0, 0, 0.22);
            text-align: center;
        }

        .smai-filter-card--active {
            border-color: rgba(251, 146, 60, 0.64);
            background:
                radial-gradient(circle at 86% 16%, rgba(251, 146, 60, 0.11), transparent 40%),
                radial-gradient(circle at 16% 14%, rgba(56, 189, 248, 0.13), transparent 34%),
                linear-gradient(
                    135deg,
                    rgba(18, 38, 76, 0.96),
                    rgba(42, 61, 128, 0.91) 44%,
                    rgba(76, 58, 154, 0.86) 100%
                );
            box-shadow:
                0 0 0 1px rgba(251, 146, 60, 0.11),
                0 0.6rem 1.45rem rgba(8, 25, 48, 0.28),
                0 0 0.95rem rgba(251, 146, 60, 0.07),
                inset 0 1px 0 rgba(255, 255, 255, 0.08);
        }

        .smai-filter-card-title {
            display: block;
            color: #ffffff;
            font-size: 0.78rem;
            font-weight: 800;
            margin-bottom: 0.38rem;
            text-align: left;
        }

        .smai-filter-card--active .smai-filter-card-title {
            color: #ffffff;
        }

        .smai-filter-card strong {
            display: block;
            width: 100%;
            color: #eff8ff;
            font-size: 1.06rem;
            line-height: 1.35;
            text-align: center;
            margin-top: 0.1rem;
        }

        .smai-filter-card--active strong {
            color: #fb923c;
            text-shadow:
                0 0 0.55rem rgba(251, 146, 60, 0.18),
                0 0 0.95rem rgba(239, 68, 68, 0.10);
            font-weight: 800;
        }

        .smai-filter-card-badge {
            position: absolute;
            right: 0.7rem;
            top: 0.65rem;
            padding: 0.12rem 0.45rem;
            border-radius: 999px;
            background: rgba(251, 146, 60, 0.12);
            border: 1px solid rgba(251, 146, 60, 0.34);
            color: #ffedd5;
            font-size: 0.68rem;
            font-weight: 700;
        }

        .smai-filter-card-caption {
            color: #8fa8c8;
            font-size: 0.82rem;
            margin: 0.05rem 0 0.55rem 0;
        }

        .smai-result-summary-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.55rem;
            margin-top: 0.45rem;
        }

        .smai-result-summary-card {
            padding: 0.7rem 0.8rem;
            border-radius: 0.75rem;
            background: rgba(6, 20, 38, 0.72);
            border: 1px solid rgba(138, 180, 248, 0.20);
        }

        .smai-result-summary-card span {
            display: block;
            color: #91a9c9;
            font-size: 0.76rem;
            margin-bottom: 0.25rem;
        }

        .smai-result-summary-card strong {
            color: #eff8ff;
            font-size: 0.92rem;
            line-height: 1.35;
        }

        div[data-testid="stDialog"] button[kind="primary"] {
            background: linear-gradient(135deg, #06b6d4, #22c55e) !important;
            border: 1px solid rgba(125, 211, 252, 0.9) !important;
            color: #ffffff !important;
            font-weight: 800 !important;
        }

        .smai-chip-checkbox-hint {
            color: #bfdbfe;
            font-size: 0.82rem;
            margin: 0.3rem 0 0.55rem;
        }

        div[data-testid="stDialog"] div[data-testid="stCheckbox"] label,
        div[role="dialog"] div[data-testid="stCheckbox"] label {
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 0.72rem;
            background: rgba(8, 30, 55, 0.72);
            padding: 0.48rem 0.62rem;
            min-height: 2.65rem;
        }

        div[data-testid="stDialog"] div[data-testid="stCheckbox"] label:hover,
        div[role="dialog"] div[data-testid="stCheckbox"] label:hover {
            border-color: rgba(34, 211, 238, 0.75);
            background: rgba(8, 90, 120, 0.50);
        }

        div[data-testid="stDialog"] button[aria-label="Close"],
        div[role="dialog"] button[aria-label="Close"],
        div[data-testid="stDialog"] button[title="Close"],
        div[role="dialog"] button[title="Close"] {
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _open_dialog(category: str) -> None:
    st.session_state[ACTIVE_DIALOG_STATE_KEY] = category
    # Force pending checkbox state to be re-synchronized from the current draft
    # when a dialog is opened. Without this, Streamlit can keep stale widget
    # values from a previous modal session, and Cancel would not reliably mean
    # "restore the state from when the dialog was opened".
    st.session_state.pop(PENDING_DIALOG_SIGNATURE_STATE_KEY, None)


def render_ranking_exploration_filter_cards(
    rows: Sequence[dict[str, str]],
    *,
    product_type: str,
    render_dialog: bool = True,
) -> None:
    _ensure_draft_applied_state()
    sync_ranking_exploration_legacy_state()
    _ensure_filter_card_css()
    st.markdown(
        '<div class="smai-ranking-builder-subhead">探索条件</div>'
        '<p class="smai-ranking-builder-caption">国・市場、業種、テーマで候補を追加で絞ります。未指定なら絞りません。</p>',
        unsafe_allow_html=True,
    )
    country_labels = dict(COUNTRY_MARKET_OPTIONS)
    sector_labels = {
        value: RANKING_OFFICIAL_SECTOR_LABELS.get(
            value, RANKING_INVESTMENT_THEME_LABELS.get(value, value)
        )
        for value in set(MAJOR_SECTOR_VALUES)
        | set(ETF_SECTOR_VALUES)
        | set(_selected(DRAFT_SECTOR_FILTER_STATE_KEY))
    }
    theme_labels = {
        value: RANKING_INVESTMENT_THEME_LABELS.get(
            value, RANKING_OFFICIAL_SECTOR_LABELS.get(value, value)
        )
        for value in set(MAJOR_THEME_VALUES) | set(_selected(DRAFT_THEME_FILTER_STATE_KEY))
    }
    dirty = exploration_filters_dirty()
    card_specs = (
        (
            "国・市場",
            _format_selected(country_labels, _selected(DRAFT_COUNTRY_FILTER_STATE_KEY)),
            "country",
            bool(_selected(DRAFT_COUNTRY_FILTER_STATE_KEY)),
        ),
        (
            "業種・セクター",
            _format_selected(sector_labels, _selected(DRAFT_SECTOR_FILTER_STATE_KEY)),
            "sector",
            bool(_selected(DRAFT_SECTOR_FILTER_STATE_KEY)),
        ),
        (
            "投資テーマ",
            _format_selected(theme_labels, _selected(DRAFT_THEME_FILTER_STATE_KEY)),
            "theme",
            bool(_selected(DRAFT_THEME_FILTER_STATE_KEY)),
        ),
    )
    cols = st.columns(3)
    for col, (title, selected_text, category, active) in zip(cols, card_specs, strict=True):
        with col:
            st.markdown(
                _card_html(title, selected_text, active=active, dirty=dirty and active),
                unsafe_allow_html=True,
            )
            st.button(
                f"{title}を選ぶ",
                key=f"ranking_filter_open_{category}",
                on_click=_open_dialog,
                args=(category,),
                type="primary",
                use_container_width=True,
            )

    selected_any = any(draft_exploration_filters().values())
    if selected_any:
        st.button(
            "探索条件をクリア",
            on_click=clear_ranking_exploration_filters,
            kwargs={"apply": True},
            key="ranking_clear_draft_exploration_filters",
        )

    # Do not warm all static option counts during initial page rendering.
    # Counts are built lazily only for the dialog category the user opens.
    if render_dialog:
        _render_active_dialog(rows, product_type=product_type)


def render_active_ranking_filter_dialog(
    rows: Sequence[dict[str, str]],
    *,
    product_type: str,
) -> None:
    _ensure_draft_applied_state()
    _ensure_filter_card_css()
    _render_active_dialog(rows, product_type=product_type)


def warm_static_filter_options(rows: Sequence[dict[str, str]], *, product_type: str) -> None:
    """Populate product-only static option caches outside the modal path.

    Opening a dialog should only read these cached option lists. If a cache was
    not warmed yet, the dialog functions still work, but normal page rendering
    tries to do the small product-only aggregation first so the modal opens more
    like a visual layer than a data-processing step.
    """
    try:
        _country_options(rows, product_type)
        _sector_options(rows, product_type, "major")
        _theme_options(rows, product_type, "major")
    except Exception:
        # Cache warming is opportunistic; never block the ranking page.
        return


def _render_active_dialog(rows: Sequence[dict[str, str]], *, product_type: str) -> None:
    category = str(st.session_state.get(ACTIVE_DIALOG_STATE_KEY, ""))
    if not category:
        return
    if category == "country":
        _show_dialog(
            "国・市場を選択",
            lambda: _render_option_dialog_body(
                DRAFT_COUNTRY_FILTER_STATE_KEY, _country_options(rows, product_type)
            ),
        )
    elif category == "sector":
        _show_dialog("業種・セクターを選択", lambda: _render_sector_dialog(rows, product_type))
    elif category == "theme":
        _show_dialog("投資テーマを選択", lambda: _render_theme_dialog(rows, product_type))


def _show_dialog(title: str, renderer: Callable[[], None]) -> None:
    dialog = getattr(st, "dialog", None)
    if callable(dialog):

        @dialog(title)
        def _dialog() -> None:
            renderer()

        _dialog()
    else:
        with st.container(border=True):
            st.subheader(title)
            renderer()


def _close_dialog() -> None:
    st.session_state.pop(ACTIVE_DIALOG_STATE_KEY, None)
    st.session_state.pop(PENDING_DIALOG_SIGNATURE_STATE_KEY, None)


def _safe_rerun() -> None:
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        rerun()
    experimental_rerun = getattr(st, "experimental_rerun", None)
    if callable(experimental_rerun):
        experimental_rerun()


def _option_label(option: FilterOption) -> str:
    return f"{option.label} {option.count:,}件" if option.count else f"{option.label} 0件"


def _pending_signature(state_key: str, options: Sequence[FilterOption]) -> tuple[object, ...]:
    return (
        str(st.session_state.get(ACTIVE_DIALOG_STATE_KEY, "")),
        state_key,
        tuple(option.value for option in options),
        tuple(_selected(state_key)),
    )


def _prepare_pending_checkboxes(state_key: str, options: Sequence[FilterOption]) -> None:
    signature = _pending_signature(state_key, options)
    if st.session_state.get(PENDING_DIALOG_SIGNATURE_STATE_KEY) == signature:
        return
    current = set(_selected(state_key))
    for option in options:
        st.session_state[f"{state_key}_pending_{option.value}"] = option.value in current
    st.session_state[PENDING_DIALOG_SIGNATURE_STATE_KEY] = signature


def _discard_pending_checkboxes(state_key: str, option_values: Sequence[str]) -> None:
    for value in option_values:
        st.session_state.pop(f"{state_key}_pending_{value}", None)
    st.session_state.pop(PENDING_DIALOG_SIGNATURE_STATE_KEY, None)


def _checkbox_grid_options(state_key: str, options: Sequence[FilterOption]) -> list[str]:
    current = set(_selected(state_key))
    selected: list[str] = []
    cols_per_row = 3
    for start in range(0, len(options), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, option in zip(cols, options[start : start + cols_per_row], strict=False):
            with col:
                checked = st.checkbox(
                    _option_label(option),
                    value=option.value in current,
                    key=f"{state_key}_pending_{option.value}",
                )
                if checked:
                    selected.append(option.value)
    return selected


def _render_option_dialog_body(state_key: str, options: Sequence[FilterOption]) -> None:
    st.caption(
        "件数は商品条件のみ反映した目安です。現在の絞り込み結果は候補サマリーで確認できます。"
    )
    st.markdown(
        '<p class="smai-chip-checkbox-hint">チップ風の候補を選び、適用でカードとランキング候補だけ更新します。ランキング結果の再作成は「ランキング作成」まで行いません。</p>',
        unsafe_allow_html=True,
    )
    option_values = [option.value for option in options]
    _prepare_pending_checkboxes(state_key, options)

    # Do not use st.form here. Some Streamlit versions show a false
    # "Missing Submit Button" warning when st.form is rendered inside
    # st.dialog together with styled checkbox/column layouts.  The checkbox
    # widgets are pending-only state, so their reruns do not update ranking
    # results; Apply/Cancel are plain buttons that close the dialog explicitly.
    selected = _checkbox_grid_options(state_key, options)
    current_labels = [_option_label(option) for option in options if option.value in set(selected)]
    if current_labels:
        st.caption("選択中: " + " / ".join(label.rsplit(" ", 1)[0] for label in current_labels[:6]))

    action_cols = st.columns([1, 1, 1])
    with action_cols[0]:
        cancel_clicked = st.button("キャンセル", key=f"{state_key}_dialog_cancel")
    with action_cols[1]:
        clear_clicked = st.button("すべて解除", key=f"{state_key}_dialog_clear")
    with action_cols[2]:
        apply_clicked = st.button("適用", key=f"{state_key}_dialog_apply", type="primary")

    if cancel_clicked:
        # Do not touch draft/applied filters. Drop pending widget state and close.
        _discard_pending_checkboxes(state_key, option_values)
        _close_dialog()
        _safe_rerun()

    if clear_clicked:
        _set_selected(state_key, [])
        apply_draft_exploration_filters()
        _discard_pending_checkboxes(state_key, option_values)
        _close_dialog()
        _safe_rerun()

    if apply_clicked:
        _set_selected(state_key, selected)
        apply_draft_exploration_filters()
        _discard_pending_checkboxes(state_key, option_values)
        _close_dialog()
        _safe_rerun()


def _render_sector_dialog(rows: Sequence[dict[str, str]], product_type: str) -> None:
    view = str(st.session_state.get(SECTOR_VIEW_STATE_KEY, "major"))
    labels = {"major": "主要", "etf": "ETF・商品", "detail": "詳細"}
    view = st.radio(
        "表示",
        list(labels),
        index=list(labels).index(view) if view in labels else 0,
        format_func=lambda value: labels[value],
        horizontal=True,
        key="market_data_ranking_sector_view_radio",
    )
    st.session_state[SECTOR_VIEW_STATE_KEY] = view
    _render_option_dialog_body(
        DRAFT_SECTOR_FILTER_STATE_KEY, _sector_options(rows, product_type, view)
    )


def _render_theme_dialog(rows: Sequence[dict[str, str]], product_type: str) -> None:
    view = str(st.session_state.get(THEME_VIEW_STATE_KEY, "major"))
    labels = {"major": "主要", "detail": "詳細"}
    view = st.radio(
        "表示",
        list(labels),
        index=list(labels).index(view) if view in labels else 0,
        format_func=lambda value: labels[value],
        horizontal=True,
        key="market_data_ranking_theme_view_radio",
    )
    st.session_state[THEME_VIEW_STATE_KEY] = view
    _render_option_dialog_body(
        DRAFT_THEME_FILTER_STATE_KEY, _theme_options(rows, product_type, view)
    )


def _top_counts(
    rows: Sequence[dict[str, str]],
    value_func: Callable[[Mapping[str, str]], Iterable[str]],
    labels: Mapping[str, str],
    *,
    limit: int = 5,
) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        for value in value_func(row):
            if not value or value == "all":
                continue
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return "該当なし"
    ordered = sorted(counts.items(), key=lambda item: (-item[1], labels.get(item[0], item[0])))[
        :limit
    ]
    return " / ".join(f"{labels.get(value, value)} {count:,}" for value, count in ordered)


def result_summary_html(rows: Sequence[dict[str, str]], *, dirty: bool = False) -> str:
    country_labels = dict(COUNTRY_MARKET_OPTIONS)
    sector_labels = {**RANKING_OFFICIAL_SECTOR_LABELS, **RANKING_INVESTMENT_THEME_LABELS}
    theme_labels = {**RANKING_INVESTMENT_THEME_LABELS, **RANKING_OFFICIAL_SECTOR_LABELS}
    country_text = _top_counts(rows, lambda row: [str(row.get("market", ""))], country_labels)
    sector_text = _top_counts(rows, _row_sector_values, sector_labels)
    theme_text = _top_counts(rows, _row_theme_values, theme_labels)
    dirty_note = ""
    return (
        '<section class="smai-ranking-target-summary smai-ranking-target-summary--ready">'
        "<strong>現在の候補サマリー</strong>"
        f"<span>候補数: {len(rows):,}件</span>"
        f"{dirty_note}"
        '<div class="smai-result-summary-grid">'
        f'<div class="smai-result-summary-card"><span>国・市場</span><strong>{html.escape(country_text)}</strong></div>'
        f'<div class="smai-result-summary-card"><span>業種・セクター</span><strong>{html.escape(sector_text)}</strong></div>'
        f'<div class="smai-result-summary-card"><span>投資テーマ</span><strong>{html.escape(theme_text)}</strong></div>'
        "</div>"
        "</section>"
    )
