from __future__ import annotations

from backend.core.errors import AppError


class ResearchDocumentError(AppError):
    """Local research document registration or external Research fetch failed."""

    code = "RESEARCH-1001"
