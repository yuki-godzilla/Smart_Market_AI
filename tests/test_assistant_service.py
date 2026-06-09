from datetime import UTC, datetime

from backend.assistant import ASSISTANT_SCHEMA_VERSION, AssistantRequest, TemplateAssistantService
from backend.reporting import build_decision_report_context, build_report_section


def _sample_report_context():
    score_section = build_report_section(
        title="Score breakdown",
        source_kind="cockpit",
        provider="mock",
        symbol="7203.T",
        summary={
            "Investment Score": "72.5",
            "Screening": "68.0",
            "Data Quality": "WARN",
        },
        warnings=["データ品質に注意があります。"],
    )
    research_section = build_report_section(
        title="Research Evidence",
        source_kind="research",
        symbol="7203.T",
        rows=[
            {
                "source": "TDnet",
                "published_at": "2026-05-31",
                "summary": "決算短信を確認済み",
                "confirmation_point": "公式資料の更新日と業績予想を確認します。",
            }
        ],
        notes=["根拠資料は出典と鮮度を合わせて確認します。"],
    )
    risk_section = build_report_section(
        title="Risk checkpoints",
        source_kind="rebalance",
        symbol="7203.T",
        rows=[
            {
                "area": "Volatility",
                "finding": "短期変動が大きい",
                "confirmation_point": "短期の値動きを単独判断に使わないよう確認します。",
            }
        ],
        warnings=["短期変動リスクがあります。"],
    )
    return build_decision_report_context(
        title="投資判断レポート - 7203.T",
        sections=[score_section, research_section, risk_section],
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
    )


def test_template_assistant_answers_score_question_from_report_context():
    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="このスコアはどう見ればいいですか？",
            report_context=_sample_report_context(),
        )
    )

    assert response.schema_version == ASSISTANT_SCHEMA_VERSION
    assert response.intent == "score"
    assert "候補比較の入口" in response.answer
    assert "売買判断" in response.answer
    assert response.reasons[0] == "Investment Score: 72.5"
    assert any("売買推奨ではありません" in caution for caution in response.cautions)
    assert response.citations[0].section_title == "Score breakdown"


def test_template_assistant_refuses_buy_sell_direction_but_keeps_checkpoints():
    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="7203.Tは買うべきですか？",
            report_context=_sample_report_context(),
        )
    )

    assert response.intent == "advice_boundary"
    assert "買う・売る・保有するといった指示では答えません" in response.answer
    assert any("判断材料" in checkpoint for checkpoint in response.next_checkpoints)
    assert response.citations


def test_template_assistant_research_question_uses_research_section_first():
    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="根拠資料とニュースで何を確認する？",
            report_context=_sample_report_context(),
        )
    )

    assert response.intent == "research"
    assert response.citations[0].source_kind == "research"
    assert any("出典と鮮度" in reason for reason in response.reasons)
    assert any("出典URL" in checkpoint for checkpoint in response.next_checkpoints)


def test_template_assistant_answers_forecast_question_from_report_context():
    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="AI予測インサイトをどう読む？",
            report_context=_sample_report_context(),
        )
    )

    assert response.intent == "forecast"
    assert "中心予測" in response.answer
    assert any("予測レンジ" in checkpoint for checkpoint in response.next_checkpoints)
    assert any("将来価格の保証" in caution for caution in response.cautions)


def test_template_assistant_answers_direction_question_before_risk_intent():
    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="上昇気配と下降警戒の理由は？",
            report_context=_sample_report_context(),
        )
    )

    assert response.intent == "direction"
    assert "上昇気配を攻めの材料" in response.answer
    assert "下降警戒を慎重材料" in response.answer
    assert any("深掘りの優先度" in caution for caution in response.cautions)


def test_template_assistant_answers_ranking_question_from_report_context():
    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="なぜこの候補が上位？",
            report_context=_sample_report_context(),
        )
    )

    assert response.intent == "ranking"
    assert "深掘り候補" in response.answer
    assert any("1位だけで閉じず" in checkpoint for checkpoint in response.next_checkpoints)


def test_template_assistant_treats_beginner_usage_question_as_next_steps():
    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="この画面でまず見る点は？",
            report_context=_sample_report_context(),
        )
    )

    assert response.intent == "next_steps"
    assert any("不足" in checkpoint for checkpoint in response.next_checkpoints)


def test_template_assistant_next_steps_use_news_specific_wording():
    context = build_decision_report_context(
        title="SMAI Assistant - 投資レーダー",
        sections=[
            build_report_section(
                title="投資レーダー / ニュース確認",
                source_kind="research",
                summary={
                    "画面": "投資レーダー",
                    "セクション": "ニュース確認",
                    "見方": "市場ニュース、カテゴリ別材料、関連銘柄、出典の鮮度を確認します。",
                },
            )
        ],
    )

    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="この画面でまず見る点は？",
            report_context=context,
        )
    )

    assert response.intent == "next_steps"
    assert "ニュースの流れ" in response.answer
    assert "スコア内訳" not in response.answer


def test_template_assistant_news_questions_change_materials_and_checkpoints():
    context = build_decision_report_context(
        title="SMAI Assistant - 投資レーダー",
        sections=[
            build_report_section(
                title="投資レーダー / ニュース確認",
                source_kind="research",
                summary={
                    "画面": "投資レーダー",
                    "セクション": "ニュース確認",
                    "見方": "市場ニュース、カテゴリ別材料、関連銘柄、出典の鮮度を確認します。",
                },
            )
        ],
    )

    flow = TemplateAssistantService().answer(
        AssistantRequest(question="ニュースはどこから見る？", report_context=context)
    )
    related = TemplateAssistantService().answer(
        AssistantRequest(question="関連銘柄はどう読む？", report_context=context)
    )
    source = TemplateAssistantService().answer(
        AssistantRequest(question="出典と鮮度で何を見る？", report_context=context)
    )

    assert "市場全体の見出し" in flow.reasons
    assert "本文に直接出た銘柄" in related.reasons
    assert "公開日と更新の新しさ" in source.reasons
    assert flow.reasons != related.reasons
    assert related.reasons != source.reasons
    assert any("銘柄コックピット" in checkpoint for checkpoint in related.next_checkpoints)
    assert any("公開日" in checkpoint for checkpoint in source.next_checkpoints)


def test_template_assistant_next_steps_use_rebalance_specific_wording():
    context = build_decision_report_context(
        title="SMAI Assistant - リバランス",
        sections=[
            build_report_section(
                title="リバランス / 配分見直し",
                source_kind="rebalance",
                summary={
                    "画面": "リバランス",
                    "セクション": "配分見直し",
                    "見方": "現在比率と目標比率のズレ、提案取引、リスク警告を確認します。",
                },
            )
        ],
    )

    response = TemplateAssistantService().answer(
        AssistantRequest(
            question="この画面でまず見る点は？",
            report_context=context,
        )
    )

    assert response.intent == "next_steps"
    assert "現在比率と目標比率のズレ" in response.answer
    assert "スコア内訳" not in response.answer


def test_template_assistant_ranking_questions_change_guidance():
    context = build_decision_report_context(
        title="SMAI Assistant - 銘柄ランキング",
        sections=[
            build_report_section(
                title="銘柄ランキング / 深掘り候補",
                source_kind="ranking",
                summary={
                    "画面": "銘柄ランキング",
                    "セクション": "深掘り候補",
                    "見方": "AI総合、上昇気配、下降警戒、データ信頼度を確認します。",
                },
            )
        ],
    )

    signals = TemplateAssistantService().answer(
        AssistantRequest(
            question="AI総合・上昇気配・下降警戒の違いは？",
            report_context=context,
        )
    )
    confidence = TemplateAssistantService().answer(
        AssistantRequest(question="低信頼データはどう読む？", report_context=context)
    )

    assert "AI総合: 候補の総合評価" in signals.reasons
    assert "欠損や古い価格データ" in confidence.reasons
    assert any("同じ意味のスコア" in caution for caution in signals.cautions)
    assert any("結論を控えめ" in caution for caution in confidence.cautions)


def test_template_assistant_settings_provider_question_is_specific():
    context = build_decision_report_context(
        title="SMAI Assistant - 設定 / データ情報",
        sections=[
            build_report_section(
                title="設定 / データ取得元",
                source_kind="manual",
                summary={
                    "画面": "設定 / データ情報",
                    "セクション": "データ設定",
                    "見方": "データ取得元、ローカル資料、キャッシュ状態を確認します。",
                },
            )
        ],
    )

    response = TemplateAssistantService().answer(
        AssistantRequest(question="データ取得元はどう選ぶ？", report_context=context)
    )

    assert "local/mock/yahoo/csv の用途" in response.reasons
    assert any("通常確認ならlocal/mock" in checkpoint for checkpoint in response.next_checkpoints)


def test_template_assistant_without_context_returns_general_confirmation_path():
    response = TemplateAssistantService().answer(
        AssistantRequest(question="次に何を確認すればいい？")
    )

    assert response.intent == "next_steps"
    assert response.citations == []
    assert "一般的な確認順" in response.answer
    assert response.cautions[0].startswith("投資判断レポートや根拠資料が未指定")
    assert "投資判断レポートを作成" in response.next_checkpoints[0]
