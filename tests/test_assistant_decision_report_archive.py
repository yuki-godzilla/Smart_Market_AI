from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

from backend.assistant import (
    AssistantResearchMaterial,
    assistant_research_bundle_to_decision_report_context,
    build_assistant_research_context_bundle,
    render_research_bundle_markdown_memo,
)
from backend.reporting import archive_assistant_decision_report_draft


def test_archive_assistant_decision_report_draft_writes_markdown_manifest_and_zip(tmp_path):
    bundle = build_assistant_research_context_bundle(
        subject="トヨタ自動車（7203.T）",
        choice="approve",
        tool_plan=None,
        planned_tools=(),
    )
    bundle = bundle.__class__(
        subject=bundle.subject,
        choice=bundle.choice,
        confirmed_materials=(
            AssistantResearchMaterial(
                key="news_fetch",
                label="最新ニュース",
                status="confirmed",
                summary="Toyota guidance newsを確認しました。",
                external=True,
                sources=("Toyota guidance | fake | news | latest | https://example.com/news",),
            ),
        ),
        missing_materials=(
            AssistantResearchMaterial(
                key="research_fetch",
                label="根拠資料 / Research Evidence",
                status="failed",
                summary="Research Evidenceは取得できませんでした。",
                external=True,
            ),
        ),
        caution_materials=("最新ニュース: 取得できた外部情報に古い可能性がある材料が含まれます。",),
        next_checkpoints=("公式IRの更新有無を確認します。",),
        report_context=None,
    )
    context = assistant_research_bundle_to_decision_report_context(
        bundle,
        user_question="トヨタはこれから上がるかな？",
        assistant_answer="provider raw request_id=abc\n取得できた材料を整理しました。",
        intent="stock_forward_view",
        created_at=datetime(2026, 6, 17, 15, 30, tzinfo=UTC),
    )
    markdown = render_research_bundle_markdown_memo(context)

    result = archive_assistant_decision_report_draft(context, tmp_path, markdown=markdown)

    saved_markdown = result.markdown_path.read_text(encoding="utf-8")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    report = manifest["reports"][0]

    assert result.markdown_path.name.startswith("20260617_153000_assistant_decision_report_7203T_")
    assert result.zip_path is not None and result.zip_path.exists()
    assert "https://example.com/news" in saved_markdown
    assert "## Tool Status" in saved_markdown
    assert "- news_fetch: confirmed" in saved_markdown
    assert "provider raw" not in saved_markdown.lower()
    assert "request_id" not in saved_markdown.lower()
    assert report["symbol"] == "7203.T"
    assert report["company_name"] == "トヨタ自動車"
    assert report["cached_only"] is False
    assert report["tool_status"] == {
        "news_fetch": "success",
        "research_fetch": "failed",
    }
    assert report["source_count"] == 1
    assert report["freshness_warnings"]

    with ZipFile(BytesIO(result.zip_path.read_bytes())) as archive:
        assert sorted(archive.namelist()) == ["manifest.json", "report.md"]
        assert "https://example.com/news" in archive.read("report.md").decode("utf-8")
        zip_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        assert zip_manifest["draft_id"] == result.draft_id


def test_archive_cached_only_draft_marks_external_tools_skipped(tmp_path):
    bundle = build_assistant_research_context_bundle(
        subject="トヨタ自動車（7203.T）",
        choice="cached_only",
        tool_plan=None,
        planned_tools=(
            {
                "name": "news_fetch",
                "label": "最新ニュース",
                "external": True,
                "required": False,
            },
            {
                "name": "research_fetch",
                "label": "根拠資料 / Research Evidence",
                "external": True,
                "required": False,
            },
        ),
    )
    context = assistant_research_bundle_to_decision_report_context(
        bundle,
        user_question="トヨタはこれから上がるかな？",
        assistant_answer="取得済み情報だけで整理します。",
        intent="stock_forward_view",
        created_at=datetime(2026, 6, 17, 16, 0, tzinfo=UTC),
    )
    markdown = render_research_bundle_markdown_memo(context)

    result = archive_assistant_decision_report_draft(context, tmp_path, markdown=markdown)
    saved_markdown = result.markdown_path.read_text(encoding="utf-8")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    report = manifest["reports"][0]

    assert "今回は取得済み情報のみで整理しています。" in saved_markdown
    assert "最新ニュースやResearch Evidenceは未確認材料として残します。" in saved_markdown
    assert report["cached_only"] is True
    assert report["fetch_mode"] == "cached_only"
    assert report["tool_status"] == {
        "news_fetch": "skipped",
        "research_fetch": "skipped",
    }
