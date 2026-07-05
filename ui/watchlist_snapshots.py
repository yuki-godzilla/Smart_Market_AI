from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.core.data_contracts import Bar
from ui.favorites import FavoriteStock, normalize_favorite_symbol
from ui.user_data import (
    is_default_session_user,
    profile_data_path,
    session_payload,
    set_session_payload,
)

LOGGER = logging.getLogger(__name__)
WATCHLIST_SNAPSHOTS_FILE_PATH = Path("data/user/watchlist_snapshots.json")
WATCHLIST_SNAPSHOTS_VERSION = 1


@dataclass(frozen=True)
class WatchlistSnapshot:
    symbol: str
    name: str | None = None
    market: str | None = None
    asset_type: str | None = None
    currency: str | None = None
    price: float | None = None
    price_jpy: float | None = None
    fx_rate_jpy: float | None = None
    price_display: str | None = None
    price_change_1d: float | None = None
    price_change_5d: float | None = None
    price_change_1m: float | None = None
    ai_score: float | None = None
    upside_score: float | None = None
    reversal_expectation_score: float | None = None
    reversal_expectation_label: str | None = None
    reversal_expectation_reason: str | None = None
    downside_risk_score: float | None = None
    trend_label: str | None = None
    trend_icon: str | None = None
    trend_status: str | None = None
    research_status: str | None = None
    latest_news_status: str | None = None
    latest_news_count: int | None = None
    source: str | None = None
    status: str | None = None
    error: str | None = None
    last_snapshot_at: str | None = None
    last_price_at: str | None = None
    last_score_at: str | None = None
    last_news_at: str | None = None


def load_watchlist_snapshots(
    path: Path | None = None,
) -> dict[str, WatchlistSnapshot]:
    if path is None and is_default_session_user():
        return _snapshots_from_payload({"snapshots": session_payload("watchlist_snapshots", {})})
    snapshots_path = (
        path or profile_data_path("watchlist_snapshots.json") or WATCHLIST_SNAPSHOTS_FILE_PATH
    )
    if not snapshots_path.exists():
        return {}
    try:
        payload = json.loads(snapshots_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Failed to load watchlist snapshots from %s: %s", snapshots_path, exc)
        return {}
    return _snapshots_from_payload(payload)


def _snapshots_from_payload(payload: object) -> dict[str, WatchlistSnapshot]:
    raw_snapshots = payload.get("snapshots", {}) if isinstance(payload, dict) else {}
    if not isinstance(raw_snapshots, dict):
        return {}
    snapshots: dict[str, WatchlistSnapshot] = {}
    for raw_symbol, raw_snapshot in raw_snapshots.items():
        if not isinstance(raw_snapshot, Mapping):
            continue
        snapshot = _snapshot_from_mapping(raw_snapshot, fallback_symbol=str(raw_symbol))
        if snapshot is not None:
            snapshots[snapshot.symbol] = snapshot
    return snapshots


def save_watchlist_snapshots(
    snapshots: Mapping[str, WatchlistSnapshot],
    path: Path | None = None,
) -> None:
    try:
        normalized = {
            symbol: replace(snapshot, symbol=symbol)
            for raw_symbol, snapshot in snapshots.items()
            if (symbol := normalize_favorite_symbol(raw_symbol or snapshot.symbol))
        }
        payload = {
            "version": WATCHLIST_SNAPSHOTS_VERSION,
            "snapshots": {
                symbol: _snapshot_to_json(snapshot)
                for symbol, snapshot in sorted(normalized.items())
            },
        }
        if path is None and is_default_session_user():
            set_session_payload("watchlist_snapshots", payload["snapshots"])
            return
        snapshots_path = (
            path or profile_data_path("watchlist_snapshots.json") or WATCHLIST_SNAPSHOTS_FILE_PATH
        )
        snapshots_path.parent.mkdir(parents=True, exist_ok=True)
        snapshots_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        LOGGER.warning("Failed to save watchlist snapshots: %s", exc)


def get_watchlist_snapshot(
    symbol: str,
    path: Path | None = None,
) -> WatchlistSnapshot | None:
    return load_watchlist_snapshots(path).get(normalize_favorite_symbol(symbol))


def upsert_watchlist_snapshot(
    snapshot: WatchlistSnapshot,
    path: Path | None = None,
) -> WatchlistSnapshot:
    symbol = normalize_favorite_symbol(snapshot.symbol)
    if not symbol:
        raise ValueError("symbol is required")
    snapshots = load_watchlist_snapshots(path)
    existing = snapshots.get(symbol)
    normalized = replace(snapshot, symbol=symbol)
    if existing is not None:
        normalized = _merge_snapshots(existing, normalized)
    snapshots[symbol] = normalized
    save_watchlist_snapshots(snapshots, path)
    return normalized


def update_watchlist_snapshot_status(
    symbol: str,
    *,
    status: str,
    error: str | None = None,
    path: Path | None = None,
) -> WatchlistSnapshot | None:
    normalized = normalize_favorite_symbol(symbol)
    snapshots = load_watchlist_snapshots(path)
    existing = snapshots.get(normalized)
    if existing is None:
        return None
    updated = replace(existing, status=status, error=error if error is not None else existing.error)
    snapshots[normalized] = updated
    save_watchlist_snapshots(snapshots, path)
    return updated


def remove_watchlist_snapshot(symbol: str, path: Path | None = None) -> bool:
    normalized = normalize_favorite_symbol(symbol)
    snapshots = load_watchlist_snapshots(path)
    if normalized not in snapshots:
        return False
    del snapshots[normalized]
    save_watchlist_snapshots(snapshots, path)
    return True


def prune_snapshots_for_removed_favorites(
    favorite_symbols: set[str],
    path: Path | None = None,
) -> int:
    keep = {normalize_favorite_symbol(symbol) for symbol in favorite_symbols if symbol.strip()}
    snapshots = load_watchlist_snapshots(path)
    remaining = {symbol: snapshot for symbol, snapshot in snapshots.items() if symbol in keep}
    removed_count = len(snapshots) - len(remaining)
    if removed_count:
        save_watchlist_snapshots(remaining, path)
    return removed_count


def classify_watchlist_trend(
    *,
    price_change_1d: object = None,
    price_change_5d: object = None,
    price_change_1m: object = None,
) -> tuple[str, str, str]:
    one_day = _finite_float(price_change_1d)
    five_day = _finite_float(price_change_5d)
    one_month = _finite_float(price_change_1m)
    if all(value is None for value in (one_day, five_day, one_month)):
        return "missing", "未取得", "…"
    if one_day is not None and one_day <= -5:
        return "sharp_down", "急落警戒", "↓"
    if (five_day is not None and five_day <= -3) or (one_month is not None and one_month <= -5):
        return "down", "下落注意", "↘"
    if five_day is not None and one_month is not None and five_day >= 3 and one_month >= 5:
        return "up", "上昇傾向", "↗"
    if five_day is not None and five_day > 0:
        return "short_up", "短期上昇", "↑"
    if any(value is not None for value in (one_day, five_day, one_month)):
        return "flat", "横ばい", "→"
    return "unknown", "判定保留", "?"


def build_watchlist_snapshot_for_symbol(
    symbol: str,
    *,
    favorite: FavoriteStock | None = None,
    row: Mapping[str, Any] | None = None,
    bars: Sequence[Bar] = (),
    previous: WatchlistSnapshot | None = None,
    source: str = "local_cache",
    now: datetime | None = None,
) -> WatchlistSnapshot:
    normalized = normalize_favorite_symbol(symbol)
    if not normalized:
        raise ValueError("symbol is required")
    row = row or {}
    timestamp = (now or datetime.now(UTC)).astimezone().isoformat(timespec="seconds")
    sorted_bars = sorted(
        (bar for bar in bars if bar.symbol.raw.upper() == normalized),
        key=lambda bar: bar.ts,
    )
    closes = [float(bar.close) for bar in sorted_bars if _finite_float(bar.close) is not None]
    price = closes[-1] if closes else _first_float(row, "price", "last_price", "close")
    currency = _first_text(row, "currency") or (favorite.currency if favorite else None)
    fx_rate_jpy = _first_float(row, "fx_rate_jpy")
    price_jpy = _first_float(row, "price_jpy", "current_price_jpy")
    if price_jpy is None and price is not None:
        if str(currency or "").upper() == "JPY":
            price_jpy = price
        elif fx_rate_jpy is not None:
            price_jpy = price * fx_rate_jpy
    change_1d = _price_change(closes, 1) if closes else _first_float(row, "price_change_1d")
    change_5d = _price_change(closes, 5) if closes else _first_float(row, "price_change_5d")
    change_1m = _price_change(closes, 20) if closes else _first_float(row, "price_change_1m")
    trend_status, trend_label, trend_icon = classify_watchlist_trend(
        price_change_1d=change_1d,
        price_change_5d=change_5d,
        price_change_1m=change_1m,
    )
    snapshot = WatchlistSnapshot(
        symbol=normalized,
        name=_first_text(row, "name") or (favorite.name if favorite else None),
        market=_first_text(row, "market") or (favorite.market if favorite else None),
        asset_type=_first_text(row, "asset_type") or (favorite.asset_type if favorite else None),
        currency=currency,
        price=price,
        price_jpy=price_jpy,
        fx_rate_jpy=fx_rate_jpy,
        price_display=_format_price(price, currency),
        price_change_1d=change_1d,
        price_change_5d=change_5d,
        price_change_1m=change_1m,
        ai_score=_first_float(
            row,
            "ai_score",
            "investment_score",
            "total_score",
            "総合スコア",
        ),
        upside_score=_first_float(
            row,
            "upside_score",
            "upside_signal_score",
            "upside",
            "上昇気配",
        ),
        reversal_expectation_score=_first_float(row, "reversal_expectation_score"),
        reversal_expectation_label=_first_text(row, "reversal_expectation_label"),
        reversal_expectation_reason=_first_text(row, "reversal_expectation_reason"),
        downside_risk_score=_first_float(
            row,
            "downside_risk_score",
            "downside_signal_score",
            "downside",
            "下降警戒",
            "下振れ警戒",
        ),
        trend_label=trend_label,
        trend_icon=trend_icon,
        trend_status=trend_status,
        research_status=_first_text(row, "research_status") or "not_researched",
        latest_news_status=_first_text(row, "latest_news_status") or "unknown",
        latest_news_count=_first_int(row, "latest_news_count"),
        source=source,
        status=(
            "ok"
            if price is not None
            or any(
                value is not None
                for value in (
                    _first_float(
                        row,
                        "ai_score",
                        "investment_score",
                        "total_score",
                        "総合スコア",
                    ),
                    _first_float(
                        row,
                        "upside_score",
                        "upside_signal_score",
                        "upside",
                        "上昇気配",
                    ),
                    _first_float(
                        row,
                        "downside_risk_score",
                        "downside_signal_score",
                        "downside",
                        "下降警戒",
                    ),
                )
            )
            else "missing"
        ),
        error="",
        last_snapshot_at=timestamp,
        last_price_at=timestamp if price is not None else None,
        last_score_at=(
            timestamp
            if any(
                _first_float(row, key) is not None
                for key in ("ai_score", "investment_score", "total_score", "総合スコア")
            )
            else None
        ),
    )
    return _merge_snapshots(previous, snapshot) if previous is not None else snapshot


def mark_watchlist_snapshot_failed(
    symbol: str,
    *,
    previous: WatchlistSnapshot | None,
    error: str,
    now: datetime | None = None,
) -> WatchlistSnapshot:
    timestamp = (now or datetime.now(UTC)).astimezone().isoformat(timespec="seconds")
    if previous is None:
        return WatchlistSnapshot(
            symbol=normalize_favorite_symbol(symbol),
            status="failed",
            error=error[:240],
            last_snapshot_at=timestamp,
        )
    return replace(
        previous,
        status="failed",
        error=error[:240],
        last_snapshot_at=timestamp,
    )


def _merge_snapshots(
    existing: WatchlistSnapshot,
    incoming: WatchlistSnapshot,
) -> WatchlistSnapshot:
    values = asdict(existing)
    for key, value in asdict(incoming).items():
        if key == "symbol" or value is not None:
            values[key] = value
    return WatchlistSnapshot(**values)


def _snapshot_from_mapping(
    raw: Mapping[str, Any],
    *,
    fallback_symbol: str,
) -> WatchlistSnapshot | None:
    symbol = normalize_favorite_symbol(str(raw.get("symbol") or fallback_symbol))
    if not symbol:
        return None
    fields = WatchlistSnapshot.__dataclass_fields__
    values = {key: raw.get(key) for key in fields if key != "symbol"}
    for key in (
        "price",
        "price_change_1d",
        "price_change_5d",
        "price_change_1m",
        "ai_score",
        "upside_score",
        "reversal_expectation_score",
        "downside_risk_score",
    ):
        values[key] = _finite_float(values.get(key))
    values["latest_news_count"] = _finite_int(values.get("latest_news_count"))
    return WatchlistSnapshot(symbol=symbol, **values)


def _snapshot_to_json(snapshot: WatchlistSnapshot) -> dict[str, Any]:
    return asdict(snapshot)


def _price_change(closes: Sequence[float], period: int) -> float | None:
    if len(closes) <= period or closes[-period - 1] == 0:
        return None
    return round((closes[-1] / closes[-period - 1] - 1) * 100, 4)


def _format_price(price: float | None, currency: str | None) -> str | None:
    if price is None:
        return None
    suffix = "円" if str(currency or "").upper() == "JPY" else ""
    return f"{price:,.2f}".rstrip("0").rstrip(".") + suffix


def _first_float(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _finite_float(row.get(key))
        if value is not None:
            return value
    return None


def _first_int(row: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = _finite_int(row.get(key))
        if value is not None:
            return value
    return None


def _first_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value and value not in {"None", "null", "nan", "NaN", "未取得"}:
            return value
    return None


def _finite_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(Decimal(str(value).replace(",", "").replace("%", "").strip()))
    except (ValueError, TypeError, ArithmeticError):
        return None
    return number if math.isfinite(number) else None


def _finite_int(value: object) -> int | None:
    number = _finite_float(value)
    return int(number) if number is not None else None
