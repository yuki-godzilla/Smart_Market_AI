from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_research_package_defers_legacy_service_import_but_preserves_public_export():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import backend.research; "
            "assert 'backend.research.service' not in sys.modules; "
            "from backend.research import ResearchInMemoryStore; "
            "assert ResearchInMemoryStore.__name__ == 'ResearchInMemoryStore'; "
            "assert 'backend.research.service' not in sys.modules; "
            "from backend.research import ResearchInMemoryVectorStore; "
            "assert ResearchInMemoryVectorStore.__name__ == 'ResearchInMemoryVectorStore'; "
            "assert 'backend.research.service' not in sys.modules; "
            "from backend.research import ResearchIngestionService; "
            "assert ResearchIngestionService.__name__ == 'ResearchIngestionService'; "
            "assert 'backend.research.service' not in sys.modules; "
            "from backend.research import ResearchQueryExpansionService; "
            "assert ResearchQueryExpansionService.__name__ == 'ResearchQueryExpansionService'; "
            "assert 'backend.research.service' not in sys.modules; "
            "from backend.research import ResearchEvidenceReranker; "
            "assert ResearchEvidenceReranker.__name__ == 'ResearchEvidenceReranker'; "
            "assert 'backend.research.service' not in sys.modules; "
            "from backend.research import ResearchAnalysisService; "
            "assert ResearchAnalysisService.__name__ == 'ResearchAnalysisService'; "
            "assert 'backend.research.service' in sys.modules",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
