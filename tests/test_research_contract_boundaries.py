from backend.research import ResearchDocument, ResearchSearchRequest
from backend.research.contracts import (
    ResearchDocument as DirectResearchDocument,
)
from backend.research.contracts import (
    ResearchSearchRequest as DirectResearchSearchRequest,
)
from backend.research.service import ResearchDocument as LegacyResearchDocument
from backend.research.service import ResearchSearchRequest as LegacyResearchSearchRequest


def test_research_contracts_keep_package_and_legacy_imports() -> None:
    assert ResearchDocument is DirectResearchDocument is LegacyResearchDocument
    assert ResearchSearchRequest is DirectResearchSearchRequest is LegacyResearchSearchRequest


def test_research_contract_validation_is_unchanged() -> None:
    request = ResearchSearchRequest(symbol="7203.T", query="業績", top_k=5)

    assert request.symbol == "7203.T"
    assert request.query == "業績"
    assert request.top_k == 5
