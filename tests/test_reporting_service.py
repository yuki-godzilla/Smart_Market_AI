from datetime import UTC, date, datetime

import pytest

from backend.core.errors import ValidationAppError
from backend.reporting import (
    DECISION_REPORT_SCHEMA_VERSION,
    DECISION_SUPPORT_NOTE,
    build_data_confidence_section,
    build_decision_checkpoints_section,
    build_decision_report_context,
    build_decision_report_manifest,
    build_report_section,
    build_symbol_metadata_section,
    render_decision_report_markdown,
)


def test_build_decision_report_context_combines_existing_workflow_outputs():
    cockpit = build_report_section(
        title="Symbol cockpit",
        source_kind="cockpit",
        provider="mock",
        symbol="7203.T",
        as_of=date(2026, 5, 17),
        summary={"investment_score": "72.50", "score_band": "BALANCED"},
        warnings=["data_quality:warn"],
    )
    ranking = build_report_section(
        title="Ranking result",
        source_kind="ranking",
        provider="mock",
        rows=[
            {"rank": "1", "symbol": "7203.T", "score": "72.50"},
            {"rank": "2", "symbol": "AAPL", "score": "68.10"},
        ],
        metadata={"preset": "balanced"},
    )
    rebalance = build_report_section(
        title="Rebalance check",
        source_kind="rebalance",
        summary={"risk_status": "BLOCK", "trade_count": "2"},
        notes=["Risk result is context for review, not an order instruction."],
    )

    context = build_decision_report_context(
        title="Decision support report",
        sections=[cockpit, ranking, rebalance],
        created_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
        tags=["phase-18", "local-first"],
    )

    assert context.schema_version == DECISION_REPORT_SCHEMA_VERSION
    assert context.decision_support_note == DECISION_SUPPORT_NOTE
    assert [section.source.kind for section in context.sections] == [
        "cockpit",
        "ranking",
        "rebalance",
    ]
    assert context.sections[1].rows[0]["symbol"] == "7203.T"


def test_render_decision_report_markdown_is_deterministic_and_includes_disclaimer():
    context = build_decision_report_context(
        title="Decision support report",
        sections=[
            build_report_section(
                title="Ranking result",
                source_kind="ranking",
                provider="mock",
                rows=[{"rank": "1", "symbol": "7203.T", "memo": "value | checked"}],
            )
        ],
        created_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
    )

    markdown = render_decision_report_markdown(context)

    assert markdown.startswith("# Decision support report\n")
    assert f"- 位置づけ: {DECISION_SUPPORT_NOTE}" in markdown
    assert "| 順位 | 銘柄 | memo |" in markdown
    assert "| 1 | 7203.T | value \\| checked |" in markdown


def test_build_decision_report_manifest_describes_local_export_files():
    context = build_decision_report_context(
        title="Decision support report",
        sections=[
            build_report_section(
                title="Symbol cockpit",
                source_kind="cockpit",
                summary={"symbol": "7203.T"},
            )
        ],
        created_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
    )

    manifest = build_decision_report_manifest(context)

    assert manifest.schema_version == DECISION_REPORT_SCHEMA_VERSION
    assert manifest.sources == ["cockpit"]
    assert manifest.section_count == 1
    assert {file["filename"] for file in manifest.files} == {
        "decision_report_context.json",
        "decision_report.md",
    }


def test_standard_sections_capture_metadata_confidence_and_checkpoints():
    data_confidence = build_data_confidence_section(
        provider="yahoo",
        symbol="6857.T",
        as_of=date(2026, 5, 22),
        price_period="2026-05-15 to 2026-05-22",
        data_quality="100",
        metadata_source="yahoo",
        metadata_as_of="2026-05-22",
        missing_fields=["risk_band"],
        coverage_rows=[
            {"field": "dividend_yield_pct", "status": "available", "value": "0.22%"},
            {"field": "risk_band", "status": "missing", "value": ""},
        ],
    )
    symbol_metadata = build_symbol_metadata_section(
        symbol="6857.T",
        name="Advantest",
        metadata={
            "asset_type": "stock",
            "nisa_category": "growth",
            "market_cap_tier": "large",
            "per": "52.42",
            "pbr": "28.93",
            "roe_pct": "57.65",
        },
    )
    checkpoints = build_decision_checkpoints_section(
        symbol="6857.T",
        checkpoints=[
            {
                "area": "Valuation",
                "finding": "PER/PBR are high",
                "confirmation_point": "Check whether earnings growth supports the valuation.",
            },
            {
                "area": "Income",
                "finding": "Dividend yield is low",
                "confirmation_point": "Review dividend policy rather than yield alone.",
            },
        ],
    )

    context = build_decision_report_context(
        title="Decision support report",
        sections=[data_confidence, symbol_metadata, checkpoints],
        created_at=datetime(2026, 5, 22, 15, 30, tzinfo=UTC),
    )
    markdown = render_decision_report_markdown(context)

    assert data_confidence.source.kind == "metadata"
    assert data_confidence.summary["missing_fields"] == "risk_band"
    assert symbol_metadata.summary["nisa_category"] == "growth"
    assert "データ取得状況と信頼性" in markdown
    assert "一部のメタデータは空欄です" in markdown
    assert "確認ポイント" in markdown
    assert "売買指示ではありません" in markdown


def test_build_decision_checkpoints_section_rejects_empty_rows():
    with pytest.raises(ValidationAppError) as exc_info:
        build_decision_checkpoints_section(checkpoints=[])

    assert "Decision checkpoints require" in exc_info.value.message


def test_build_report_section_rejects_empty_content():
    with pytest.raises(ValidationAppError) as exc_info:
        build_report_section(title="Empty", source_kind="manual")

    assert "must include summary" in exc_info.value.message
