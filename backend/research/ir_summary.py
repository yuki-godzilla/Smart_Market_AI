"""Pure display-contract assembly for classified Research IR candidates."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

from backend.research.contracts import (
    InformationStatus,
    IRDocumentType,
    IRSummaryItem,
    ResearchEvidenceLevel,
)
from backend.research.ir_classification import IRCategoryMatch, IRCategoryRule


def build_ir_summary_item(
    *,
    rule: IRCategoryRule,
    match: IRCategoryMatch | None,
    key_points: Sequence[str],
    clip_text: Callable[[str], str],
    evidence_level_from_source_type: Callable[[str], ResearchEvidenceLevel],
) -> IRSummaryItem:
    """Build the established user-facing contract for one classified IR category."""

    ir_document_type = cast(IRDocumentType, rule.ir_document_type)
    if match is None:
        return IRSummaryItem(
            document_type=rule.document_type,
            ir_document_type=ir_document_type,
            title="未取得",
            availability="missing",
            information_status="missing",
            summary=(
                f"{rule.document_type}は未取得です。公式IR、TDnet、EDINETで追加確認してください。"
            ),
            key_points=[],
            evidence_level="missing",
            classification_confidence=0.0,
        )

    candidate = match.candidate
    resolved_key_points = list(key_points)
    if not resolved_key_points and candidate.body and candidate.source_type != "tdnet":
        resolved_key_points = [clip_text(candidate.body)]
    information_status: InformationStatus = "found"
    return IRSummaryItem(
        document_type=rule.document_type,
        ir_document_type=ir_document_type,
        title=candidate.title,
        availability="found",
        information_status=information_status,
        summary=build_ir_summary_text(
            rule.document_type,
            resolved_key_points,
            information_status,
        ),
        key_points=resolved_key_points,
        source_title=candidate.source_title or candidate.title,
        source_url=candidate.source_url,
        evidence_level=evidence_level_from_source_type(candidate.source_type),
        classification_reason=match.classification_reason,
        matched_keywords=list(match.matched_keywords),
        classification_confidence=match.classification_confidence,
        source_category=candidate.source_type,
    )


def build_ir_summary_text(
    document_type: str,
    key_points: Sequence[str],
    information_status: InformationStatus,
) -> str:
    """Keep the established availability wording for an IR display row."""

    if key_points:
        return (
            f"{document_type}に関連しそうな資料候補があります。内容はリンク先で確認してください。"
        )
    if information_status == "found":
        return "関連しそうな資料候補があります。内容はリンク先で確認してください。"
    if information_status == "unparsed":
        return "資料タイトルは取得済みですが、本文は未解析です。詳細はリンク先で確認してください。"
    return f"{document_type}の出典は確認できています。詳細は出典カードで確認してください。"
