"""Deterministic exploration candidates derived from Investment Radar news evidence."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256

from backend.news.contracts import (
    NewsDashboardSnapshot,
    NewsFreshnessStatus,
    NewsHeadlineCard,
    NewsSymbolMatch,
    NewsSymbolMatchKind,
    RadarCandidate,
    RadarCandidateDataStatus,
    RadarCandidateEvidence,
    RadarCandidateMap,
    RadarCandidateMaterialTone,
    RadarCandidateProvenance,
)

_FRESHNESS_WEIGHT: dict[NewsFreshnessStatus, int] = {
    "latest": 40,
    "recent": 28,
    "stale": 12,
    "unknown": 6,
}
_PROVENANCE_DIRECTNESS: dict[RadarCandidateProvenance, float] = {
    "direct_mention": 1.0,
    "inferred_candidate": 0.55,
    "macro_proxy": 0.1,
}
_PROVENANCE_ORDER: dict[RadarCandidateProvenance, int] = {
    "direct_mention": 0,
    "inferred_candidate": 1,
    "macro_proxy": 2,
}
_POSITIVE_MATERIAL_TYPES = {"earnings", "shareholder_return", "theme", "fund_flow"}
_CAUTION_MATERIAL_TYPES = {"risk", "policy", "macro"}
_MATERIAL_PRIORITY_BONUS = {
    "risk": 12,
    "earnings": 10,
    "policy": 8,
    "macro": 7,
    "shareholder_return": 6,
    "theme": 6,
    "fund_flow": 4,
}


def build_radar_candidate_map(
    snapshot: NewsDashboardSnapshot,
    *,
    watchlist_symbols: Collection[str] = (),
    symbol_metadata_by_symbol: Mapping[str, Mapping[str, object]] | None = None,
) -> RadarCandidateMap:
    """Aggregate traceable news candidates without changing any investment score.

    Candidates are intentionally keyed by both symbol and provenance.  A direct
    mention and a theme-derived candidate for the same symbol remain separate,
    so the UI never presents an inferred connection as an article mention.
    """

    normalized_watchlist = {
        symbol.strip().upper() for symbol in watchlist_symbols if symbol and symbol.strip()
    }
    metadata = {
        symbol.strip().upper(): row
        for symbol, row in (symbol_metadata_by_symbol or {}).items()
        if symbol and symbol.strip()
    }
    grouped: dict[tuple[str, RadarCandidateProvenance], dict[str, RadarCandidateEvidence]] = {}
    display_names: dict[tuple[str, RadarCandidateProvenance], str | None] = {}

    for card in snapshot.stream_headlines:
        for match, provenance in _candidate_matches(card):
            symbol = match.symbol.strip().upper()
            if not symbol:
                continue
            key = (symbol, provenance)
            evidence = _candidate_evidence(card, symbol=symbol, provenance=provenance)
            grouped.setdefault(key, {})[evidence.evidence_id] = evidence
            if key not in display_names and match.name:
                display_names[key] = match.name

    candidates = [
        _build_candidate(
            symbol=symbol,
            provenance=provenance,
            evidence_by_id=evidence_by_id,
            display_name=display_names.get((symbol, provenance)),
            watchlist_match=symbol in normalized_watchlist,
            symbol_metadata=metadata.get(symbol),
        )
        for (symbol, provenance), evidence_by_id in grouped.items()
        if evidence_by_id
    ]
    candidates.sort(
        key=lambda candidate: (
            _PROVENANCE_ORDER[candidate.provenance],
            -candidate.confirmation_priority,
            -candidate.directness,
            candidate.symbol,
            candidate.candidate_id,
        )
    )
    return RadarCandidateMap(generated_at=snapshot.generated_at, candidates=candidates)


def filter_radar_candidates(
    candidate_map: RadarCandidateMap,
    *,
    markets: Collection[str] = (),
    asset_types: Collection[str] = (),
    provenances: Collection[RadarCandidateProvenance] = (),
    rag_statuses: Collection[RadarCandidateDataStatus] = (),
    watchlist_only: bool = False,
) -> list[RadarCandidate]:
    """Apply display-only filters while preserving the deterministic map order."""

    selected_markets = {value.strip() for value in markets if value and value.strip()}
    selected_asset_types = {value.strip() for value in asset_types if value and value.strip()}
    selected_provenances = set(provenances)
    selected_rag_statuses = set(rag_statuses)
    return [
        candidate
        for candidate in candidate_map.candidates
        if (not selected_markets or candidate.market in selected_markets)
        and (not selected_asset_types or candidate.asset_type in selected_asset_types)
        and (not selected_provenances or candidate.provenance in selected_provenances)
        and (not selected_rag_statuses or candidate.rag_data_status in selected_rag_statuses)
        and (not watchlist_only or candidate.watchlist_match)
    ]


def _candidate_matches(
    card: NewsHeadlineCard,
) -> list[tuple[NewsSymbolMatch, RadarCandidateProvenance]]:
    matches: list[tuple[NewsSymbolMatch, RadarCandidateProvenance]] = []
    seen: set[tuple[str, RadarCandidateProvenance]] = set()
    for match in card.symbol_matches:
        provenance = _match_provenance(match)
        if provenance is None:
            continue
        key = (match.symbol.strip().upper(), provenance)
        if not key[0] or key in seen:
            continue
        seen.add(key)
        matches.append((match, provenance))
    fallback_groups: tuple[
        tuple[Sequence[str], RadarCandidateProvenance, NewsSymbolMatchKind], ...
    ] = (
        (card.related_symbols, "direct_mention", "direct_mention"),
        (card.inferred_symbols, "inferred_candidate", "category_inferred"),
        (card.macro_proxy_symbols, "macro_proxy", "macro_proxy"),
    )
    for symbols, fallback_provenance, kind in fallback_groups:
        for symbol in symbols:
            normalized = symbol.strip().upper()
            key = (normalized, fallback_provenance)
            if not normalized or key in seen:
                continue
            seen.add(key)
            matches.append(
                (NewsSymbolMatch(symbol=normalized, kind=kind, confidence=0.0), fallback_provenance)
            )
    return matches


def _match_provenance(match: NewsSymbolMatch) -> RadarCandidateProvenance | None:
    if match.kind == "macro_proxy":
        return "macro_proxy"
    if match.kind in {"category_inferred", "llm_verified_inferred"}:
        return "inferred_candidate"
    if match.kind == "rejected":
        return None
    return "direct_mention"


def _candidate_evidence(
    card: NewsHeadlineCard,
    *,
    symbol: str,
    provenance: RadarCandidateProvenance,
) -> RadarCandidateEvidence:
    identity = "\x1f".join(
        (
            card.url or "",
            card.source_name or "",
            card.source_type,
            card.title,
            card.published_at.isoformat() if card.published_at else "",
            symbol,
            provenance,
        )
    )
    return RadarCandidateEvidence(
        evidence_id=f"radar-news-{sha256(identity.encode('utf-8')).hexdigest()[:20]}",
        headline_title=card.title,
        source_name=card.source_name,
        source_type=card.source_type,
        source_url=card.url,
        category=card.category,
        material_type=card.material_type,
        provenance=provenance,
        directness=_PROVENANCE_DIRECTNESS[provenance],
        published_at=card.published_at,
        fetched_at=card.fetched_at,
        freshness_status=card.freshness_status,
    )


def _build_candidate(
    *,
    symbol: str,
    provenance: RadarCandidateProvenance,
    evidence_by_id: Mapping[str, RadarCandidateEvidence],
    display_name: str | None,
    watchlist_match: bool,
    symbol_metadata: Mapping[str, object] | None,
) -> RadarCandidate:
    evidence = sorted(
        evidence_by_id.values(),
        key=lambda item: (
            -_FRESHNESS_WEIGHT[item.freshness_status],
            -_published_timestamp(item.published_at),
            item.headline_title,
            item.evidence_id,
        ),
    )
    freshness_status: NewsFreshnessStatus = "unknown"
    if evidence:
        freshness_status = max(
            (item.freshness_status for item in evidence),
            key=lambda status: (_FRESHNESS_WEIGHT[status], status),
        )
    latest_published_at = max(
        (item.published_at for item in evidence if item.published_at is not None),
        key=_published_timestamp,
        default=None,
    )
    categories = sorted({item.category for item in evidence})
    independent_source_count = len(
        {
            (item.source_name or item.source_type).strip().casefold()
            for item in evidence
            if (item.source_name or item.source_type).strip()
        }
    )
    material_tone = _material_tone(evidence)
    symbol_data_status = _symbol_data_status(symbol_metadata)
    market = _metadata_text(symbol_metadata, "market")
    asset_type = _metadata_text(symbol_metadata, "asset_type")
    gaps = _confirmation_gaps(
        provenance=provenance,
        symbol_data_status=symbol_data_status,
    )
    return RadarCandidate(
        candidate_id=f"radar:{provenance}:{symbol}",
        symbol=symbol,
        display_name=display_name or _metadata_text(symbol_metadata, "name"),
        market=market,
        asset_type=asset_type,
        provenance=provenance,
        categories=categories,
        evidence_ids=[item.evidence_id for item in evidence],
        evidence=evidence,
        freshness_status=freshness_status,
        latest_published_at=latest_published_at,
        independent_source_count=independent_source_count,
        watchlist_match=watchlist_match,
        symbol_data_status=symbol_data_status,
        price_data_status="not_checked",
        rag_data_status="not_checked",
        confirmation_gaps=gaps,
        directness=_PROVENANCE_DIRECTNESS[provenance],
        confirmation_priority=_confirmation_priority(
            evidence,
            watchlist_match=watchlist_match,
        ),
        material_tone=material_tone,
        is_investigation_candidate=provenance != "macro_proxy",
    )


def _confirmation_priority(
    evidence: Sequence[RadarCandidateEvidence],
    *,
    watchlist_match: bool,
) -> int:
    freshest = max((_FRESHNESS_WEIGHT[item.freshness_status] for item in evidence), default=0)
    breadth = min(3, len(evidence)) * 8
    material_bonus = max(
        (_MATERIAL_PRIORITY_BONUS.get(item.material_type, 3) for item in evidence), default=0
    )
    watchlist_bonus = 14 if watchlist_match else 0
    return min(100, freshest + breadth + material_bonus + watchlist_bonus)


def _material_tone(evidence: Sequence[RadarCandidateEvidence]) -> RadarCandidateMaterialTone:
    material_types = {item.material_type for item in evidence}
    positive = bool(material_types & _POSITIVE_MATERIAL_TYPES)
    caution = bool(material_types & _CAUTION_MATERIAL_TYPES)
    if positive and caution:
        return "mixed"
    if positive:
        return "positive"
    if caution:
        return "caution"
    return "unknown"


def _symbol_data_status(metadata: Mapping[str, object] | None) -> RadarCandidateDataStatus:
    if metadata is None:
        return "unavailable"
    freshness = (_metadata_text(metadata, "data_freshness_status") or "").casefold()
    if freshness in {"latest", "fresh", "recent"}:
        return "available"
    return "partial"


def _confirmation_gaps(
    *,
    provenance: RadarCandidateProvenance,
    symbol_data_status: RadarCandidateDataStatus,
) -> list[str]:
    gaps = [
        "価格データはこの候補マップでは未確認です。",
        "RAG根拠は「根拠を確認」の明示操作で確認します。",
    ]
    if symbol_data_status == "unavailable":
        gaps.insert(0, "銘柄DBの確認情報がありません。")
    elif symbol_data_status == "partial":
        gaps.insert(0, "銘柄DBの鮮度または項目を確認してください。")
    if provenance == "macro_proxy":
        gaps.insert(0, "市場背景を確認する代理指標であり、通常の個別銘柄候補ではありません。")
    return gaps


def _metadata_text(metadata: Mapping[str, object] | None, key: str) -> str | None:
    if metadata is None:
        return None
    value = str(metadata.get(key) or "").strip()
    return value or None


def _published_timestamp(value: datetime | None) -> float:
    if value is None:
        return 0.0
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).timestamp()
    return value.timestamp()
