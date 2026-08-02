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
            "assert 'backend.research.service' in sys.modules",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
