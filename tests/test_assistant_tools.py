from datetime import UTC, datetime

from backend.assistant import (
    AssistantToolLayer,
    build_assistant_research_context_bundle,
    execute_assistant_tool_plan,
)
from backend.reporting import build_decision_report_context, build_report_section


def _sample_context():
    price = build_report_section(
        title="価格チャート",
        source_kind="cockpit",
        symbol="7203.T",
        summary={"価格": "直近反発", "trend": "上向き"},
    )
    forecast = build_report_section(
        title="AI予測インサイト",
        source_kind="cockpit",
        symbol="7203.T",
        summary={"予測": "やや上向き", "downside": "中"},
    )
    research = build_report_section(
        title="Research Evidence",
        source_kind="research",
        symbol="7203.T",
        summary={"根拠": "決算資料を確認"},
    )
    return build_decision_report_context(
        title="銘柄コックピット - 7203.T",
        sections=[price, forecast, research],
        created_at=datetime(2026, 6, 14, 6, 0, tzinfo=UTC),
    )


def test_assistant_tool_layer_get_current_context_from_report():
    current = AssistantToolLayer().get_current_context(_sample_context())

    assert current.symbol == "7203.T"
    assert current.has_price
    assert current.has_forecast
    assert current.has_research
    assert current.has_decision_report


def test_assistant_tool_layer_resolves_known_symbol_alias():
    result = AssistantToolLayer().resolve_symbol("トヨタを見て")

    assert result.status == "ok"
    assert result.details["symbol"] == "7203.T"


def test_execute_assistant_tool_plan_keeps_missing_tool_as_result():
    plan = execute_assistant_tool_plan(
        intent="news_materials",
        message="ニュースを調べて",
        report_context=_sample_context(),
    )

    assert plan.intent == "news_materials"
    assert any(result.name == "search_news_materials" for result in plan.executed)
    assert any(result.status == "missing" for result in plan.executed)


def test_execute_assistant_tool_plan_builds_decision_report_draft():
    plan = execute_assistant_tool_plan(
        intent="decision_report_draft",
        message="トヨタをレポートにして",
        report_context=_sample_context(),
    )

    assert plan.report_context is not None
    assert plan.report_context.title == "SMAIアシスタント Decision Report下書き"
    assert any(result.name == "get_forecast_summary" for result in plan.executed)


def test_research_context_bundle_groups_confirmed_and_missing_materials():
    plan = execute_assistant_tool_plan(
        intent="stock_summary",
        message="トヨタこれから上がるかな",
        report_context=_sample_context(),
    )
    planned_tools = (
        {"name": "symbol_resolve", "label": "銘柄を特定", "external": False, "required": True},
        {"name": "price_fetch", "label": "価格の動き", "external": True, "required": True},
        {
            "name": "forecast_fetch",
            "label": "AI予測・下振れ警戒",
            "external": False,
            "required": True,
        },
        {"name": "news_fetch", "label": "最新ニュース", "external": True, "required": False},
        {
            "name": "research_fetch",
            "label": "根拠資料 / Research Evidence",
            "external": True,
            "required": False,
        },
    )

    bundle = build_assistant_research_context_bundle(
        subject="トヨタ自動車（7203.T）",
        choice="approve",
        tool_plan=plan,
        planned_tools=planned_tools,
    )

    confirmed_labels = [material.label for material in bundle.confirmed_materials]
    missing_labels = [material.label for material in bundle.missing_materials]
    assert "銘柄を特定" in confirmed_labels
    assert "価格の動き" in confirmed_labels
    assert "AI予測・下振れ警戒" in confirmed_labels
    assert "根拠資料 / Research Evidence" in confirmed_labels
    assert "最新ニュース" in missing_labels
    symbol_material = next(
        material for material in bundle.confirmed_materials if material.label == "銘柄を特定"
    )
    assert symbol_material.summary == "7203.T"
    assert any("未確認" in caution for caution in bundle.caution_materials)
    assert any(line == "確認できた材料:" for line in bundle.llm_context_lines())
    assert any(line == "未確認材料:" for line in bundle.llm_context_lines())
    assert not any("銘柄を特定: 銘柄を特定" in line for line in bundle.llm_context_lines())


def test_research_context_bundle_cached_only_marks_external_tools_missing():
    plan = execute_assistant_tool_plan(
        intent="stock_summary",
        message="トヨタこれから上がるかな",
        report_context=_sample_context(),
    )
    planned_tools = (
        {"name": "price_fetch", "label": "価格の動き", "external": True, "required": True},
        {
            "name": "forecast_fetch",
            "label": "AI予測・下振れ警戒",
            "external": False,
            "required": True,
        },
        {"name": "news_fetch", "label": "最新ニュース", "external": True, "required": False},
    )

    bundle = build_assistant_research_context_bundle(
        subject="トヨタ自動車（7203.T）",
        choice="cached_only",
        tool_plan=plan,
        planned_tools=planned_tools,
    )

    missing_labels = bundle.missing_labels()
    confirmed_labels = tuple(material.label for material in bundle.confirmed_materials)
    assert "価格の動き" in missing_labels
    assert "最新ニュース" in missing_labels
    assert "AI予測・下振れ警戒" in confirmed_labels
    assert any("外部取得は行っていない" in caution for caution in bundle.caution_materials)


def test_export_markdown_report_avoids_overwrite(tmp_path):
    tools = AssistantToolLayer()

    first = tools.export_markdown_report("# memo\n", tmp_path, symbol="7203.T")
    second = tools.export_markdown_report("# memo\n", tmp_path, symbol="7203.T")

    assert first.exists()
    assert second.exists()
    assert first != second
    assert first.read_text(encoding="utf-8") == "# memo\n"
