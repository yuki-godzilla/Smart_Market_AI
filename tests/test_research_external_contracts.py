from backend.research import (
    DefaultExternalResearchAdapter as PublicDefaultExternalResearchAdapter,
)
from backend.research import (
    ExternalResearchFetchRequest as PublicExternalResearchFetchRequest,
)
from backend.research.external_adapters import DefaultExternalResearchAdapter
from backend.research.external_contracts import ExternalResearchFetchRequest
from backend.research.service import (
    DefaultExternalResearchAdapter as ServiceDefaultExternalResearchAdapter,
)
from backend.research.service import (
    ExternalResearchFetchRequest as ServiceExternalResearchFetchRequest,
)


def test_external_research_contract_public_exports_stay_compatible():
    assert PublicExternalResearchFetchRequest is ExternalResearchFetchRequest
    assert ServiceExternalResearchFetchRequest is ExternalResearchFetchRequest


def test_external_research_adapter_public_exports_stay_compatible():
    assert PublicDefaultExternalResearchAdapter is DefaultExternalResearchAdapter
    assert ServiceDefaultExternalResearchAdapter is DefaultExternalResearchAdapter
