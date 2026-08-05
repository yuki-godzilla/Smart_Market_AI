"""Pure assembly for the company-overview Research summary."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from backend.research.contracts import (
    CompanyBusinessProfile,
    CompanyOverviewSummary,
    ResearchEvidenceLevel,
)


@dataclass(frozen=True)
class CompanyOverviewSummaryInputs:
    """Already-selected company facts needed for the display summary contract."""

    symbol: str
    company_name: str
    business_profile: CompanyBusinessProfile
    business_overview: str
    business_segments: list[str]
    regions: list[str]
    scale_summary: str
    recent_focus: str
    source_types: Sequence[str]
    source_titles: Sequence[str]


def build_company_overview_summary(
    inputs: CompanyOverviewSummaryInputs,
    *,
    clip_text: Callable[[str], str],
    evidence_level_from_source_types: Callable[[Sequence[str]], ResearchEvidenceLevel],
    unique_text: Callable[[Sequence[str]], list[str]],
) -> CompanyOverviewSummary:
    """Build the established overview contract from deterministic selected inputs."""

    business_profile = inputs.business_profile
    return CompanyOverviewSummary(
        company_name=inputs.company_name,
        symbol=inputs.symbol,
        business_profile=business_profile,
        industry=business_profile.industry,
        sector=business_profile.sector,
        business_overview=clip_text(inputs.business_overview),
        main_businesses=inputs.business_segments,
        business_segments=inputs.business_segments,
        supporting_businesses=business_profile.supporting_businesses,
        products_services=business_profile.products_services,
        products_services_status=business_profile.products_services_status,
        regions=inputs.regions,
        customer_segments=business_profile.customer_segments,
        scale_summary=inputs.scale_summary,
        recent_focus=inputs.recent_focus,
        information_status=business_profile.information_status,
        evidence_level=(
            business_profile.evidence_level
            if business_profile.evidence_level != "missing"
            else evidence_level_from_source_types(inputs.source_types)
        ),
        source_titles=unique_text(inputs.source_titles)[:5],
    )
