from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from statistics import median

from backend.assistant import AssistantContextBundle, AssistantContextSection
from backend.news.contracts import NewsDashboardSnapshot, RadarCandidate, RadarCandidateMap
from backend.news.radar_market import RadarMarketSnapshot, radar_market_snapshot_is_stale

from .radar_overview_context_metadata import (
    build_radar_overview_bundle,
    radar_overview_context_warnings,
)
from .radar_overview_models import (
    RadarOverviewInterpretationContext,
    RadarOverviewMarketState,
)

_NUMERIC_PATTERN = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:[.,]\d+)*(?:%|点|件|日)?")
_ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def build_radar_overview_interpretation_context(
    news_snapshot: NewsDashboardSnapshot,
    candidate_map: RadarCandidateMap,
    market_snapshot: RadarMarketSnapshot | None,
    *,
    as_of: date | None = None,
    now: datetime | None = None,
    max_themes: int = 3,
    max_sector_groups: int = 4,
    max_deep_dive_candidates: int = 2,
    max_text_chars: int = 240,
) -> RadarOverviewInterpretationContext:
    """Build an eight-section, display-only Radar overview context."""

    _validate_context_limits(max_themes, max_sector_groups, max_deep_dive_candidates)
    now_utc = _ensure_utc(now or datetime.now(UTC))
    resolved_as_of = as_of or _ensure_utc(news_snapshot.generated_at).date()
    theme_entries = _theme_entries(
        news_snapshot,
        candidate_map.candidates,
        max_themes=max_themes,
        max_text_chars=max_text_chars,
    )
    deep_candidates = [
        item
        for item in candidate_map.candidates
        if item.is_investigation_candidate and item.provenance != "macro_proxy"
    ][:max_deep_dive_candidates]
    market_state, market_summary, sector_rows, market_warnings = _market_context(
        market_snapshot,
        now=now_utc,
        max_sector_groups=max_sector_groups,
    )
    counts = {
        provenance: sum(item.provenance == provenance for item in candidate_map.candidates)
        for provenance in ("direct_mention", "inferred_candidate", "macro_proxy")
    }
    context_hash = _overview_context_hash(
        news_snapshot=news_snapshot,
        as_of=resolved_as_of,
        counts=counts,
        market_state=market_state,
        market_summary=market_summary,
        sector_rows=sector_rows,
        theme_entries=theme_entries,
        deep_candidates=deep_candidates,
    )
    context_id = f"radar-overview:{context_hash[:24]}"
    sections = _overview_sections(
        news_snapshot=news_snapshot,
        candidate_count=len(candidate_map.candidates),
        as_of=resolved_as_of,
        context_id=context_id,
        context_hash=context_hash,
        counts=counts,
        market_state=market_state,
        market_summary=market_summary,
        sector_rows=sector_rows,
        theme_entries=theme_entries,
        deep_candidates=deep_candidates,
        max_text_chars=max_text_chars,
    )
    return _overview_context_model(
        news_snapshot=news_snapshot,
        candidate_map=candidate_map,
        as_of=resolved_as_of,
        now=now_utc,
        context_id=context_id,
        context_hash=context_hash,
        market_state=market_state,
        sections=sections,
        sector_rows=sector_rows,
        theme_entries=theme_entries,
        deep_candidates=deep_candidates,
        market_warnings=market_warnings,
    )


def _validate_context_limits(
    max_themes: int,
    max_sector_groups: int,
    max_deep_dive_candidates: int,
) -> None:
    if not 1 <= max_themes <= 3:
        raise ValueError("max_themes must be between 1 and 3")
    if not 1 <= max_sector_groups <= 4:
        raise ValueError("max_sector_groups must be between 1 and 4")
    if not 1 <= max_deep_dive_candidates <= 2:
        raise ValueError("max_deep_dive_candidates must be between 1 and 2")


def _overview_context_hash(
    *,
    news_snapshot: NewsDashboardSnapshot,
    as_of: date,
    counts: dict[str, int],
    market_state: RadarOverviewMarketState,
    market_summary: dict[str, str],
    sector_rows: list[dict[str, str]],
    theme_entries: list[dict[str, str]],
    deep_candidates: list[RadarCandidate],
) -> str:
    return _stable_hash(
        {
            "as_of": as_of.isoformat(),
            "news_generated_at": _format_datetime(news_snapshot.generated_at),
            "news_fetched_at": _format_datetime(news_snapshot.fetched_at),
            "news_freshness": news_snapshot.freshness_status,
            "candidate_counts": counts,
            "market_state": market_state,
            "market_summary": market_summary,
            "sector_rows": sector_rows,
            "theme_entries": theme_entries,
            "deep_candidates": [_candidate_hash_payload(item) for item in deep_candidates],
        }
    )


def _overview_sections(
    *,
    news_snapshot: NewsDashboardSnapshot,
    candidate_count: int,
    as_of: date,
    context_id: str,
    context_hash: str,
    counts: dict[str, int],
    market_state: RadarOverviewMarketState,
    market_summary: dict[str, str],
    sector_rows: list[dict[str, str]],
    theme_entries: list[dict[str, str]],
    deep_candidates: list[RadarCandidate],
    max_text_chars: int,
) -> list[AssistantContextSection]:
    sections = [
        _scope_section(
            context_id=context_id,
            context_hash=context_hash,
            as_of=as_of,
            news_snapshot=news_snapshot,
            counts=counts,
            candidate_count=candidate_count,
        ),
        _market_section(market_state=market_state, summary=market_summary),
        _sector_section(sector_rows),
        *[_theme_section(item) for item in theme_entries],
        *[_candidate_section(item, max_text_chars=max_text_chars) for item in deep_candidates],
    ]
    if len(sections) > 8:
        raise ValueError("radar overview context must not exceed eight sections")
    return sections


def _overview_context_model(
    *,
    news_snapshot: NewsDashboardSnapshot,
    candidate_map: RadarCandidateMap,
    as_of: date,
    now: datetime,
    context_id: str,
    context_hash: str,
    market_state: RadarOverviewMarketState,
    sections: list[AssistantContextSection],
    sector_rows: list[dict[str, str]],
    theme_entries: list[dict[str, str]],
    deep_candidates: list[RadarCandidate],
    market_warnings: list[str],
) -> RadarOverviewInterpretationContext:
    candidates_by_id = {item.candidate_id: item for item in candidate_map.candidates}
    related_candidate_ids = _dedupe(
        [
            candidate_id
            for entry in theme_entries
            for candidate_id in entry["related_candidate_ids"].split(",")
            if candidate_id
        ]
    )
    allowed_candidate_ids = _dedupe(
        [*related_candidate_ids, *[item.candidate_id for item in deep_candidates]]
    )
    allowed_candidates = [
        candidates_by_id[item] for item in allowed_candidate_ids if item in candidates_by_id
    ]
    bundle = build_radar_overview_bundle(
        context_hash=context_hash,
        market_state=market_state,
        sections=sections,
        created_at=now,
    )
    return RadarOverviewInterpretationContext(
        radar_context_id=context_id,
        as_of=as_of,
        bundle=bundle,
        context_hash=context_hash,
        market_state=market_state,
        allowed_evidence_ids=[section.section_id for section in sections],
        allowed_symbols=_dedupe([item.symbol for item in allowed_candidates]),
        allowed_numeric_values=_allowed_numeric_values(bundle),
        allowed_dates=_allowed_dates(bundle, as_of=as_of.isoformat()),
        allowed_sector_ids=[row["sector_id"] for row in sector_rows],
        allowed_theme_ids=[entry["theme_id"] for entry in theme_entries],
        allowed_candidate_ids=allowed_candidate_ids,
        deep_dive_candidate_ids=[item.candidate_id for item in deep_candidates],
        theme_candidate_ids={
            entry["theme_id"]: [item for item in entry["related_candidate_ids"].split(",") if item]
            for entry in theme_entries
        },
        candidate_provenance={item.candidate_id: item.provenance for item in allowed_candidates},
        warnings=radar_overview_context_warnings(
            news_snapshot=news_snapshot,
            candidate_map=candidate_map,
            market_warnings=market_warnings,
        ),
    )


def radar_overview_interpretation_context_hash(
    news_snapshot: NewsDashboardSnapshot,
    candidate_map: RadarCandidateMap,
    market_snapshot: RadarMarketSnapshot | None,
    *,
    now: datetime | None = None,
) -> str:
    return build_radar_overview_interpretation_context(
        news_snapshot,
        candidate_map,
        market_snapshot,
        now=now,
    ).context_hash


def _market_context(
    snapshot: RadarMarketSnapshot | None,
    *,
    now: datetime,
    max_sector_groups: int,
) -> tuple[RadarOverviewMarketState, dict[str, str], list[dict[str, str]], list[str]]:
    if snapshot is None:
        return (
            "missing",
            {
                "status": "missing",
                "direction_available": "no",
                "note": "候補銘柄の価格snapshotは未取得です。",
            },
            [],
            ["市場snapshotがないため、候補集合の値動きは未確認です。"],
        )
    if radar_market_snapshot_is_stale(snapshot, now=now):
        return (
            "stale",
            {
                "status": "stale",
                "direction_available": "no",
                "generated_at": _format_datetime(snapshot.generated_at),
                "provider": snapshot.provider,
                "note": "市場snapshotが古いため、数値と方向は解釈対象外です。",
            },
            [],
            ["市場snapshotが古いため、候補集合とセクターの方向は表示しません。"],
        )

    tiles = list(snapshot.tiles)
    up_count = sum(item.change_pct > 0.1 for item in tiles)
    down_count = sum(item.change_pct < -0.1 for item in tiles)
    flat_count = len(tiles) - up_count - down_count
    state: RadarOverviewMarketState = "partial" if snapshot.unavailable_symbols else "fresh"
    summary = {
        "status": state,
        "direction_available": "yes" if tiles else "no",
        "provider": snapshot.provider,
        "lookback_sessions": str(snapshot.lookback_sessions),
        "requested_count": str(snapshot.requested_count),
        "measured_count": str(len(tiles)),
        "unavailable_count": str(len(snapshot.unavailable_symbols)),
        "up_count": str(up_count),
        "down_count": str(down_count),
        "flat_count": str(flat_count),
        "generated_at": _format_datetime(snapshot.generated_at),
        "latest_as_of": max((_format_datetime(item.as_of) for item in tiles), default="未取得"),
        "scope_note": "数値は取得済み候補集合だけを示し、市場全体を代表しません。",
    }
    grouped: dict[str, list[float]] = defaultdict(list)
    for tile in tiles:
        grouped[tile.sector or "未分類"].append(tile.change_pct)
    sector_rows = []
    for label, values in grouped.items():
        sector_rows.append(
            {
                "sector_id": _stable_id("sector", label),
                "sector_label": label,
                "measured_count": str(len(values)),
                "up_count": str(sum(value > 0.1 for value in values)),
                "down_count": str(sum(value < -0.1 for value in values)),
                "median_change_pct": f"{median(values):.2f}%",
                "comparison_state": "comparable" if len(values) >= 2 else "insufficient",
            }
        )
    sector_rows.sort(
        key=lambda row: (
            -int(row["measured_count"]),
            -abs(float(row["median_change_pct"].rstrip("%"))),
            row["sector_label"],
        )
    )
    warnings = []
    if snapshot.unavailable_symbols:
        warnings.append(f"価格を確認できない候補が{len(snapshot.unavailable_symbols)}件あります。")
    if not tiles:
        warnings.append("比較可能な候補価格がありません。")
    return state, summary, sector_rows[:max_sector_groups], warnings


def _theme_entries(
    snapshot: NewsDashboardSnapshot,
    candidates: list[RadarCandidate],
    *,
    max_themes: int,
    max_text_chars: int,
) -> list[dict[str, str]]:
    candidates_by_category: dict[str, list[RadarCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.provenance == "macro_proxy" or not candidate.is_investigation_candidate:
            continue
        for category in candidate.categories:
            candidates_by_category[category].append(candidate)

    cells = sorted(snapshot.heatmap_cells, key=lambda item: (-item.heat_score, item.category))
    entries: list[dict[str, str]] = []
    for cell in cells:
        related = candidates_by_category.get(cell.category, [])[:3]
        if not related and cell.news_count <= 0:
            continue
        entries.append(
            {
                "theme_id": _stable_id("theme", cell.category),
                "theme_label": _clean(cell.category, max_text_chars),
                "region": _clean(cell.region or "未分類", max_text_chars),
                "news_count": str(cell.news_count),
                "official_source_count": str(cell.official_source_count),
                "freshness_ratio": f"{cell.freshness_ratio * 100:.0f}%",
                "dominant_material_type": _clean(
                    cell.dominant_material_type or "未分類", max_text_chars
                ),
                "market_metric_source": cell.market_metric_source,
                "related_candidate_ids": ",".join(item.candidate_id for item in related),
                "related_symbols": ",".join(item.symbol for item in related),
                "relationships": ",".join(
                    f"{item.candidate_id}={item.provenance}" for item in related
                ),
                "news_evidence_ids": ",".join(
                    _dedupe([evidence_id for item in related for evidence_id in item.evidence_ids])[
                        :6
                    ]
                ),
            }
        )
        if len(entries) >= max_themes:
            break
    return entries


def _scope_section(
    *,
    context_id: str,
    context_hash: str,
    as_of: date,
    news_snapshot: NewsDashboardSnapshot,
    counts: dict[str, int],
    candidate_count: int,
) -> AssistantContextSection:
    return _section(
        section_id="radar_scope",
        title="今日の投資レーダー範囲",
        source_kind="radar_overview_scope",
        summary={
            "radar_context_id": context_id,
            "context_hash": context_hash,
            "as_of": as_of.isoformat(),
            "news_generated_at": _format_datetime(news_snapshot.generated_at),
            "news_fetched_at": _format_datetime(news_snapshot.fetched_at),
            "news_freshness": news_snapshot.freshness_status,
            "candidate_count": str(candidate_count),
            "direct_mention_count": str(counts["direct_mention"]),
            "inferred_candidate_count": str(counts["inferred_candidate"]),
            "macro_proxy_count": str(counts["macro_proxy"]),
        },
        notes=[
            "Candidates are confirmation targets, not an investment ranking.",
            "Direct mentions, inferred candidates, and macro proxies must remain distinct.",
        ],
    )


def _market_section(*, market_state: str, summary: dict[str, str]) -> AssistantContextSection:
    return _section(
        section_id="radar_market_breadth",
        title="取得済み候補集合の値動き",
        source_kind="radar_market_breadth",
        summary={"market_state": market_state, **summary},
        notes=[
            "Never generalize this measured candidate set to the whole market.",
            "When direction_available=no, do not state price direction or sector mood.",
        ],
    )


def _sector_section(rows: list[dict[str, str]]) -> AssistantContextSection:
    return _section(
        section_id="radar_sector_comparison",
        title="取得済み候補集合内のセクター比較",
        source_kind="radar_sector_comparison",
        summary={"sector_group_count": str(len(rows))},
        rows=rows,
        notes=[
            "Sector rows describe only measured candidate tiles.",
            "comparison_state=insufficient must not be treated as a sector trend.",
        ],
    )


def _theme_section(entry: dict[str, str]) -> AssistantContextSection:
    return _section(
        section_id=entry["theme_id"],
        title=entry["theme_label"],
        source_kind="radar_news_theme",
        summary=entry,
        notes=[
            "News volume and freshness are not individual price direction.",
            "inferred_candidate means theme relation, not a direct article mention.",
        ],
    )


def _candidate_section(
    candidate: RadarCandidate, *, max_text_chars: int
) -> AssistantContextSection:
    return _section(
        section_id=candidate.candidate_id,
        title=f"確認候補 {candidate.symbol}",
        source_kind="radar_overview_candidate",
        symbol=candidate.symbol,
        summary={
            "candidate_id": candidate.candidate_id,
            "symbol": candidate.symbol,
            "display_name": _clean(candidate.display_name or candidate.symbol, max_text_chars),
            "provenance": candidate.provenance,
            "categories": _clean(",".join(candidate.categories) or "未分類", max_text_chars),
            "freshness": candidate.freshness_status,
            "independent_source_count": str(candidate.independent_source_count),
            "watchlist_match": "yes" if candidate.watchlist_match else "no",
            "confirmation_priority": str(candidate.confirmation_priority),
            "confirmation_gaps": _clean(
                " / ".join(candidate.confirmation_gaps) or "なし", max_text_chars
            ),
            "news_evidence_ids": ",".join(candidate.evidence_ids[:6]),
        },
        notes=[
            "Confirmation priority is a review order, not investment attractiveness.",
            "Opening this candidate must not automatically start market, News, or RAG retrieval.",
        ],
    )


def _section(
    *,
    section_id: str,
    title: str,
    source_kind: str,
    summary: dict[str, str],
    rows: list[dict[str, str]] | None = None,
    notes: list[str] | None = None,
    symbol: str | None = None,
) -> AssistantContextSection:
    return AssistantContextSection(
        section_id=section_id,
        title=title,
        source_kind=source_kind,
        symbol=symbol,
        summary=summary,
        rows=rows or [],
        notes=notes or [],
        included_fields=sorted(summary),
    )


def _candidate_hash_payload(candidate: RadarCandidate) -> dict[str, object]:
    return {
        "candidate_id": candidate.candidate_id,
        "symbol": candidate.symbol,
        "display_name": candidate.display_name,
        "provenance": candidate.provenance,
        "categories": candidate.categories,
        "evidence_ids": candidate.evidence_ids,
        "freshness_status": candidate.freshness_status,
        "independent_source_count": candidate.independent_source_count,
        "watchlist_match": candidate.watchlist_match,
        "confirmation_priority": candidate.confirmation_priority,
        "confirmation_gaps": candidate.confirmation_gaps,
    }


def _allowed_numeric_values(bundle: AssistantContextBundle) -> list[str]:
    values: set[str] = set()
    for text in _bundle_values(bundle):
        for match in _NUMERIC_PATTERN.findall(text):
            normalized = _normalize_number(match)
            if normalized:
                values.add(normalized)
    return sorted(values)


def _allowed_dates(bundle: AssistantContextBundle, *, as_of: str) -> list[str]:
    values = {as_of}
    for text in _bundle_values(bundle):
        values.update(_ISO_DATE_PATTERN.findall(text))
    return sorted(values)


def _bundle_values(bundle: AssistantContextBundle) -> list[str]:
    values: list[str] = []
    for section in bundle.sections:
        values.extend(section.summary.values())
        values.extend(value for row in section.rows for value in row.values())
    return values


def _normalize_number(value: str) -> str:
    cleaned = value.replace(",", "").rstrip("%点件日").lstrip("+")
    try:
        return format(Decimal(cleaned).normalize(), "f")
    except InvalidOperation:
        return ""


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.strip().encode("utf-8")).hexdigest()[:12]
    return f"radar_{prefix}:{digest}"


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "未取得"
    return _ensure_utc(value).isoformat()


def _clean(value: object, max_chars: int) -> str:
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
