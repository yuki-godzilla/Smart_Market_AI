from datetime import UTC, date, datetime

from backend.assistant import (
    AssistantResearchContextBundle,
    AssistantResearchMaterial,
    AssistantToolLayer,
    assistant_research_bundle_to_decision_report_context,
    assistant_tool_results_from_external_research_failure,
    assistant_tool_results_from_external_research_fetch,
    build_assistant_research_context_bundle,
    execute_assistant_tool_plan,
    render_research_bundle_markdown_memo,
)
from backend.reporting import build_decision_report_context, build_report_section
from backend.research import ExternalResearchFetchManifestEntry, ExternalResearchFetchResult


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


def test_research_bundle_to_decision_report_context_carries_materials_without_debug():
    plan = execute_assistant_tool_plan(
        intent="stock_summary",
        message="トヨタこれから上がるかな",
        report_context=_sample_context(),
    )
    bundle = build_assistant_research_context_bundle(
        subject="トヨタ自動車（7203.T）",
        choice="approve",
        tool_plan=plan,
        planned_tools=(
            {"name": "symbol_resolve", "label": "銘柄を特定", "external": False},
            {"name": "price_fetch", "label": "価格の動き", "external": True},
            {"name": "forecast_fetch", "label": "AI予測・下振れ警戒", "external": False},
            {"name": "news_fetch", "label": "最新ニュース", "external": True},
        ),
    )

    context = assistant_research_bundle_to_decision_report_context(
        bundle,
        user_question="トヨタはこれから上がるかな？",
        assistant_answer="確認材料を整理しました。\nprovider raw fields\nrequest_id=abc\nlatency=10",
        intent="stock_summary",
        created_at=datetime(2026, 6, 14, 6, 30, tzinfo=UTC),
    )
    markdown = render_research_bundle_markdown_memo(context)

    assert context.title == "SMAIアシスタント Decision Report下書き: トヨタ自動車"
    assert context.sections[0].source.symbol == "7203.T"
    assert context.sections[0].summary["company_name"] == "トヨタ自動車"
    assert context.sections[0].summary["user_question"] == "トヨタはこれから上がるかな？"
    assert "価格の動き" in context.sections[0].summary["available_materials"]
    assert "最新ニュース" in context.sections[0].summary["missing_materials"]
    assert markdown.startswith("# Decision Report Draft: トヨタ自動車")
    assert "## 上昇方向を見る材料" in markdown
    assert "## 注意すべき材料" in markdown
    assert "## 未確認材料" in markdown
    assert "最新ニュース" in markdown
    assert "provider raw" not in markdown.lower()
    assert "request_id" not in markdown
    assert "latency" not in markdown.lower()


def test_external_research_fetch_tool_results_feed_bundle_sources_and_report_markdown():
    fetch_result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="fake_external",
        fetched_at=datetime(2026, 6, 17, 6, 0, tzinfo=UTC),
        entries=[
            ExternalResearchFetchManifestEntry(
                title="Toyota raises guidance",
                symbol="7203.T",
                source_type="news",
                source_url="https://example.com/toyota-guidance",
                provider="fake_news",
                published_at=date(2026, 6, 16),
                fetched_at=datetime(2026, 6, 17, 6, 0, tzinfo=UTC),
                freshness_status="latest",
                document_id="doc-news",
                content_summary="Toyota raised guidance after stronger demand.",
            ),
            ExternalResearchFetchManifestEntry(
                title="Toyota IR",
                symbol="7203.T",
                source_type="company_ir",
                source_url="https://example.com/toyota-ir",
                provider="fake_ir",
                published_at=None,
                fetched_at=datetime(2026, 6, 17, 6, 0, tzinfo=UTC),
                freshness_status="unknown",
                document_id="doc-ir",
                content_summary="Official IR page was checked.",
            ),
        ],
        warnings=["ニュースの鮮度は取得時点に依存します。"],
    )
    plan = execute_assistant_tool_plan(
        intent="stock_summary",
        message="トヨタこれから上がるかな",
        report_context=_sample_context(),
    )
    external_results = assistant_tool_results_from_external_research_fetch(fetch_result)
    external_results_by_name = {result.name: result for result in external_results}
    updated_plan = plan.__class__(
        intent=plan.intent,
        current_context=plan.current_context,
        executed=tuple(
            external_results_by_name.get(result.name, result) for result in plan.executed
        ),
        report_context=plan.report_context,
    )

    bundle = build_assistant_research_context_bundle(
        subject="トヨタ自動車（7203.T）",
        choice="approve",
        tool_plan=updated_plan,
        planned_tools=(
            {"name": "news_fetch", "label": "最新ニュース", "external": True},
            {
                "name": "research_fetch",
                "label": "根拠資料 / Research Evidence",
                "external": True,
            },
        ),
    )
    context = assistant_research_bundle_to_decision_report_context(
        bundle,
        user_question="トヨタはこれから上がるかな？",
        assistant_answer="取得材料を整理しました。",
        intent="stock_summary",
        created_at=datetime(2026, 6, 17, 6, 30, tzinfo=UTC),
    )
    markdown = render_research_bundle_markdown_memo(context)

    confirmed_labels = [material.label for material in bundle.confirmed_materials]
    assert "最新ニュース" in confirmed_labels
    assert "根拠資料 / Research Evidence" in confirmed_labels
    assert any("ニュースの鮮度" in caution for caution in bundle.caution_materials)
    assert "## 出典" in markdown
    assert "https://example.com/toyota-guidance" in markdown
    assert "https://example.com/toyota-ir" in markdown
    assert "provider raw" not in markdown.lower()


def test_external_research_failure_tool_results_become_missing_materials():
    plan = execute_assistant_tool_plan(
        intent="stock_summary",
        message="トヨタこれから上がるかな",
        report_context=_sample_context(),
    )
    failure_results = assistant_tool_results_from_external_research_failure(
        message="外部情報の取得結果を確認できませんでした。",
        include_news=True,
        include_research=True,
    )
    failure_by_name = {result.name: result for result in failure_results}
    updated_plan = plan.__class__(
        intent=plan.intent,
        current_context=plan.current_context,
        executed=tuple(failure_by_name.get(result.name, result) for result in plan.executed),
        report_context=plan.report_context,
    )

    bundle = build_assistant_research_context_bundle(
        subject="トヨタ自動車（7203.T）",
        choice="approve",
        tool_plan=updated_plan,
        planned_tools=(
            {"name": "news_fetch", "label": "最新ニュース", "external": True},
            {
                "name": "research_fetch",
                "label": "根拠資料 / Research Evidence",
                "external": True,
            },
        ),
    )

    assert "最新ニュース" in bundle.missing_labels()
    assert "根拠資料 / Research Evidence" in bundle.missing_labels()
    assert any("取得結果を確認できません" in caution for caution in bundle.caution_materials)


def test_news_research_bundle_to_decision_report_context_keeps_news_materials():
    bundle = AssistantResearchContextBundle(
        subject="銀行ニュース",
        choice="approve",
        confirmed_materials=(
            AssistantResearchMaterial(
                key="news_fetch",
                label="最新ニュース",
                status="confirmed",
                summary="銀行セクターの政策金利材料を確認しました。",
                external=True,
            ),
        ),
        missing_materials=(
            AssistantResearchMaterial(
                key="research_fetch",
                label="根拠資料 / Research Evidence",
                status="missing",
                summary="個別銘柄の根拠資料は未確認です。",
                external=True,
            ),
        ),
        caution_materials=("ニュースだけで判断せず、価格・業績・開示も確認します。",),
        next_checkpoints=("関連銘柄とセクター影響を確認します。",),
    )

    context = assistant_research_bundle_to_decision_report_context(
        bundle,
        user_question="銀行ニュースを見せてよ",
        assistant_answer="注目材料を整理しました。",
        intent="news_materials",
        created_at=datetime(2026, 6, 14, 7, 0, tzinfo=UTC),
    )
    markdown = render_research_bundle_markdown_memo(context)

    assert context.sections[1].rows[0]["label"] == "最新ニュース"
    assert "銀行セクターの政策金利材料" in markdown
    assert "根拠資料 / Research Evidence" in markdown
    assert "関連銘柄とセクター影響" in markdown


def test_export_markdown_report_avoids_overwrite(tmp_path):
    tools = AssistantToolLayer()

    first = tools.export_markdown_report("# memo\n", tmp_path, symbol="7203.T")
    second = tools.export_markdown_report("# memo\n", tmp_path, symbol="7203.T")

    assert first.exists()
    assert second.exists()
    assert first != second
    assert first.read_text(encoding="utf-8") == "# memo\n"
