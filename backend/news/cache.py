from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

from backend.core.runtime_paths import CACHE_DIR_ENV, runtime_path_from_env
from backend.news.contracts import (
    NewsCategoryLane,
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    NewsHeatmapCell,
    NewsUpdateStatus,
)

MAX_NEWS_ITEMS = 100
MAX_STREAM_HEADLINES = 20
MAX_HEADLINES_PER_CATEGORY = 5
MAX_HEATMAP_CELLS = 30
MAX_CHECKPOINTS_PER_NEWS = 3
MAX_SUMMARY_CHARS = 300
MAX_AI_COMMENT_CHARS = 240

NEWS_CACHE_DIR: Final[Path] = runtime_path_from_env(CACHE_DIR_ENV, "data/cache")
NEWS_SNAPSHOT_FILENAME: Final[str] = "news_dashboard_snapshot.json"
NEWS_PREVIOUS_SNAPSHOT_FILENAME: Final[str] = "news_dashboard_snapshot.prev.json"
NEWS_TMP_SNAPSHOT_FILENAME: Final[str] = "news_dashboard_snapshot.tmp.json"
NEWS_UPDATE_STATUS_FILENAME: Final[str] = "news_update_status.json"

PROHIBITED_RECOMMENDATION_TERMS: tuple[str, ...] = (
    "買い",
    "売り",
    "今すぐ投資",
    "必ず上がる",
    "確実に儲かる",
)


def normalize_snapshot_for_cache(
    snapshot: NewsDashboardSnapshot,
) -> NewsDashboardSnapshot:
    """Return a storage-bounded snapshot without raw fields or oversized text."""

    remaining_news = MAX_NEWS_ITEMS
    stream_headlines = _normalize_headline_sequence(
        snapshot.stream_headlines,
        limit=min(MAX_STREAM_HEADLINES, remaining_news),
    )
    remaining_news -= len(stream_headlines)

    category_lanes: list[NewsCategoryLane] = []
    for lane in snapshot.category_lanes:
        if remaining_news <= 0:
            break
        headlines = _normalize_headline_sequence(
            lane.headlines,
            limit=min(MAX_HEADLINES_PER_CATEGORY, remaining_news),
        )
        remaining_news -= len(headlines)
        category = _normalize_text(lane.category)
        if category and headlines:
            category_lanes.append(NewsCategoryLane(category=category, headlines=headlines))

    heatmap_cells = [
        _normalize_heatmap_cell(cell) for cell in snapshot.heatmap_cells[:MAX_HEATMAP_CELLS]
    ]

    return NewsDashboardSnapshot(
        schema_version=snapshot.schema_version,
        generated_at=snapshot.generated_at,
        fetched_at=snapshot.fetched_at,
        freshness_status=snapshot.freshness_status,
        stream_headlines=stream_headlines,
        heatmap_cells=heatmap_cells,
        category_lanes=category_lanes,
    )


def load_cached_news_dashboard_snapshot(
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
) -> NewsDashboardSnapshot | None:
    """Load the latest normalized dashboard snapshot if it exists and is valid."""

    cache_file = _cache_path(cache_dir, NEWS_SNAPSHOT_FILENAME)
    if not cache_file.exists():
        return None
    try:
        return NewsDashboardSnapshot.model_validate_json(cache_file.read_text(encoding="utf-8"))
    except ValueError:
        return None


def save_cached_news_dashboard_snapshot(
    snapshot: NewsDashboardSnapshot,
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
) -> NewsDashboardSnapshot:
    """Normalize and atomically save the latest snapshot with one previous backup."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    normalized = normalize_snapshot_for_cache(snapshot)
    cache_file = _cache_path(cache_root, NEWS_SNAPSHOT_FILENAME)
    tmp_file = _cache_path(cache_root, NEWS_TMP_SNAPSHOT_FILENAME)

    try:
        tmp_file.write_text(
            normalized.model_dump_json(indent=2),
            encoding="utf-8",
        )
        NewsDashboardSnapshot.model_validate_json(tmp_file.read_text(encoding="utf-8"))
        rotate_previous_snapshot(cache_dir=cache_root)
        tmp_file.replace(cache_file)
    finally:
        if tmp_file.exists():
            tmp_file.unlink()
    return normalized


def rotate_previous_snapshot(
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
) -> None:
    """Keep at most one previous valid snapshot backup."""

    cache_root = Path(cache_dir)
    cache_file = _cache_path(cache_root, NEWS_SNAPSHOT_FILENAME)
    previous_file = _cache_path(cache_root, NEWS_PREVIOUS_SNAPSHOT_FILENAME)
    if not cache_file.exists():
        return
    previous_file.write_bytes(cache_file.read_bytes())


def cleanup_news_cache_files(
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
) -> list[Path]:
    """Remove only bounded, known news-dashboard temporary or extra files."""

    cache_root = Path(cache_dir)
    if not cache_root.exists():
        return []

    allowed_names = {
        NEWS_SNAPSHOT_FILENAME,
        NEWS_PREVIOUS_SNAPSHOT_FILENAME,
        NEWS_UPDATE_STATUS_FILENAME,
    }
    deleted: list[Path] = []
    for path in cache_root.iterdir():
        if not path.is_file():
            continue
        name = path.name
        should_delete = (
            name == NEWS_TMP_SNAPSHOT_FILENAME
            or (
                name.startswith("news_dashboard_snapshot.prev.")
                and name != NEWS_PREVIOUS_SNAPSHOT_FILENAME
            )
            or name.startswith("news_dashboard_snapshot.copy")
            or name.startswith("news_dashboard_debug")
            or (
                name.startswith("news_dashboard_snapshot")
                and name.endswith(".json")
                and name not in allowed_names
            )
        )
        if should_delete:
            path.unlink()
            deleted.append(path)
    return deleted


def get_news_cache_file_size(
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
) -> int | None:
    """Return the latest snapshot cache size in bytes."""

    cache_file = _cache_path(cache_dir, NEWS_SNAPSHOT_FILENAME)
    if not cache_file.exists():
        return None
    return cache_file.stat().st_size


def load_news_update_status(
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
) -> NewsUpdateStatus:
    """Load latest-only refresh status, falling back to an empty status."""

    status_file = _cache_path(cache_dir, NEWS_UPDATE_STATUS_FILENAME)
    if not status_file.exists():
        return NewsUpdateStatus()
    try:
        return NewsUpdateStatus.model_validate_json(status_file.read_text(encoding="utf-8"))
    except ValueError:
        return NewsUpdateStatus()


def save_news_update_status(
    status: NewsUpdateStatus,
    *,
    cache_dir: Path | str = NEWS_CACHE_DIR,
) -> NewsUpdateStatus:
    """Save the latest-only refresh status without keeping history arrays."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    normalized = status.model_copy(
        update={"cache_file_size_bytes": get_news_cache_file_size(cache_dir=cache_root)}
    )
    status_file = _cache_path(cache_root, NEWS_UPDATE_STATUS_FILENAME)
    status_file.write_text(normalized.model_dump_json(indent=2), encoding="utf-8")
    return normalized


def news_snapshot_item_count(snapshot: NewsDashboardSnapshot) -> int:
    """Count headline cards stored across stream and category lanes."""

    return len(snapshot.stream_headlines) + sum(
        len(lane.headlines) for lane in snapshot.category_lanes
    )


def contains_prohibited_recommendation_terms(text: str | None) -> bool:
    """Check whether text includes recommendation-like wording banned for news cards."""

    if not text:
        return False
    return any(term in text for term in PROHIBITED_RECOMMENDATION_TERMS)


def _normalize_headline_sequence(
    headlines: Sequence[NewsHeadlineCard],
    *,
    limit: int,
) -> list[NewsHeadlineCard]:
    if limit <= 0:
        return []
    normalized: list[NewsHeadlineCard] = []
    for headline in headlines:
        if len(normalized) >= limit:
            break
        normalized.append(_normalize_headline_card(headline))
    return normalized


def _normalize_headline_card(headline: NewsHeadlineCard) -> NewsHeadlineCard:
    return NewsHeadlineCard(
        title=_normalize_text(headline.title) or headline.title.strip(),
        summary=_truncate_optional_text(headline.summary, MAX_SUMMARY_CHARS),
        url=_normalize_optional_text(headline.url),
        source_name=_normalize_optional_text(headline.source_name),
        source_type=_normalize_text(headline.source_type) or headline.source_type.strip(),
        published_at=headline.published_at,
        fetched_at=headline.fetched_at,
        freshness_status=headline.freshness_status,
        category=_normalize_text(headline.category) or headline.category.strip(),
        region=_normalize_optional_text(headline.region),
        material_type=_normalize_text(headline.material_type) or headline.material_type.strip(),
        related_symbols=_dedupe_symbols(headline.related_symbols),
        inferred_symbols=_dedupe_symbols(headline.inferred_symbols),
        is_official_source=headline.is_official_source,
        ai_comment=_truncate_optional_text(headline.ai_comment, MAX_AI_COMMENT_CHARS),
        investment_checkpoints=_limit_text_items(
            headline.investment_checkpoints,
            limit=MAX_CHECKPOINTS_PER_NEWS,
            max_chars=MAX_SUMMARY_CHARS,
        ),
    )


def _normalize_heatmap_cell(cell: NewsHeatmapCell) -> NewsHeatmapCell:
    return NewsHeatmapCell(
        category=_normalize_text(cell.category) or cell.category.strip(),
        region=_normalize_optional_text(cell.region),
        price_change_pct=getattr(cell, "price_change_pct", None),
        volume_activity_score=getattr(cell, "volume_activity_score", None),
        news_count=cell.news_count,
        risk_count=cell.risk_count,
        positive_count=cell.positive_count,
        official_source_count=cell.official_source_count,
        freshness_ratio=cell.freshness_ratio,
        heat_score=cell.heat_score,
        dominant_material_type=_normalize_optional_text(cell.dominant_material_type),
    )


def _limit_text_items(
    values: Iterable[str],
    *,
    limit: int,
    max_chars: int,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _truncate_text(_normalize_text(value), max_chars)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _dedupe_symbols(symbols: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _truncate_optional_text(value: str | None, max_chars: int) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    return _truncate_text(normalized, max_chars)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize_text(value)
    return normalized or None


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return f"{value[: max_chars - 3]}..."


def _cache_path(cache_dir: Path | str, filename: str) -> Path:
    return Path(cache_dir) / filename
