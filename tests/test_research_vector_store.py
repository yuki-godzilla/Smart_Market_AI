from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_vector_store_module_has_no_legacy_service_import_side_effect():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import backend.research.vector_store; "
            "assert 'backend.research.service' not in sys.modules",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
