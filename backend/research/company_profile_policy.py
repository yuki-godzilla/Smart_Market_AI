"""Compatibility façade for company-profile classification policies."""

from backend.research.company_business_policy import (
    _company_research_business_terms,
    _company_research_customer_segments,
    _company_research_filter_main_businesses,
    _company_research_filter_supporting_businesses,
    _company_research_regions_from_text,
    _company_research_supporting_business_terms,
)
from backend.research.company_product_policy import (
    _company_research_inferred_products_services,
    _company_research_products_services,
)

__all__ = [
    "_company_research_business_terms",
    "_company_research_customer_segments",
    "_company_research_filter_main_businesses",
    "_company_research_filter_supporting_businesses",
    "_company_research_inferred_products_services",
    "_company_research_products_services",
    "_company_research_regions_from_text",
    "_company_research_supporting_business_terms",
]
