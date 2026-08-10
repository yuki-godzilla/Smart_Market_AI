from __future__ import annotations

from datetime import datetime

from backend.assistant import AssistantContextBundle, AssistantContextSection
from backend.news.contracts import NewsDashboardSnapshot, RadarCandidateMap

from .radar_overview_models import RadarOverviewMarketState


def build_radar_overview_bundle(
    *,
    context_hash: str,
    market_state: RadarOverviewMarketState,
    sections: list[AssistantContextSection],
    created_at: datetime,
) -> AssistantContextBundle:
    return AssistantContextBundle(
        bundle_id=f"radar-overview-interpretation-{context_hash[:24]}",
        title="Investment Radar Overview Interpretation",
        source="streamlit_context",
        created_at=created_at,
        active_context_id="radar_overview_interpretation",
        sections=sections,
        tags=["radar", "overview", "interpretation", market_state],
        privacy_notes=[
            "Only displayed News/Radar metadata and a bounded market snapshot are included.",
            "External article bodies, source URLs, provider raw fields, user notes, and debug data are excluded.",
            "Candidate order, scores, rankings, forecasts, and investment decisions must not be changed.",
            "Market movement describes only the measured candidate set, never the whole market.",
        ],
    )


def radar_overview_context_warnings(
    *,
    news_snapshot: NewsDashboardSnapshot,
    candidate_map: RadarCandidateMap,
    market_warnings: list[str],
) -> list[str]:
    warnings = [*market_warnings]
    if news_snapshot.freshness_status == "stale":
        warnings.append("ニュースsnapshotが古いため、現在の状況として断定できません。")
    if not candidate_map.candidates:
        warnings.append("確認候補がありません。")
    return list(dict.fromkeys(item.strip() for item in warnings if item.strip()))
