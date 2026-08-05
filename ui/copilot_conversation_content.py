from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CopilotIntent = Literal[
    "app_help",
    "identity",
    "capability_help",
    "stock_summary",
    "forecast_risk_compare",
    "news_materials",
    "decision_report_draft",
    "free_chat",
    "concept_explanation",
    "broad_discovery",
]


@dataclass(frozen=True)
class CopilotConversationPreset:
    intent: CopilotIntent
    label: str
    description: str
    context_id: str
    default_question: str
    prompt_instruction: str


def copilot_conversation_presets() -> tuple[CopilotConversationPreset, ...]:
    return (
        CopilotConversationPreset(
            intent="app_help",
            label="SMAIの使い方を聞きたい",
            description="画面ごとの役割と、次に開く場所を確認します。",
            context_id="copilot_app_help",
            default_question="SMAIの使い方と、最初に見る画面を教えてください。",
            prompt_instruction=(
                "SMAIの画面と機能を説明し、ユーザーが次に開くべき画面を案内してください。"
            ),
        ),
        CopilotConversationPreset(
            intent="stock_summary",
            label="この銘柄を整理したい",
            description="見る材料、注意点、次に確認することに分けます。",
            context_id="copilot_cockpit_overview",
            default_question="この銘柄を、見る材料・注意点・次に確認することに分けて整理してください。",
            prompt_instruction=(
                "現在の銘柄文脈を、見る材料、注意点、次に確認することに分けて整理してください。"
            ),
        ),
        CopilotConversationPreset(
            intent="forecast_risk_compare",
            label="予測とリスクを比べたい",
            description="予測側とリスク側の温度差を見ます。",
            context_id="copilot_cockpit_overview",
            default_question="AI予測インサイトと下振れ警戒を比べて、確認ポイントを整理してください。",
            prompt_instruction=(
                "予測側の見方、リスク側の見方、矛盾・温度差、確認ポイントの順に整理してください。"
            ),
        ),
        CopilotConversationPreset(
            intent="news_materials",
            label="ニュース材料を見たい",
            description="強気材料、弱気材料、未確認材料を分けます。",
            context_id="copilot_news_overview",
            default_question="ニュースや開示材料を、強気材料・弱気材料・未確認材料に分けて整理してください。",
            prompt_instruction=(
                "ニュース、開示、Research Evidenceを、強気材料、弱気材料、未確認材料、"
                "次に見る資料に分けて整理してください。"
            ),
        ),
        CopilotConversationPreset(
            intent="decision_report_draft",
            label="Decision Reportを作りたい",
            description="判断メモとして残す下書きを作ります。",
            context_id="copilot_cockpit_overview",
            default_question="Decision Reportに残すための整理メモを作ってください。",
            prompt_instruction=(
                "確認した材料、強気材料、弱気材料、未確認事項、次回確認、メモの順に"
                "Decision Reportの下書きを作ってください。"
            ),
        ),
        CopilotConversationPreset(
            intent="free_chat",
            label="自由に会話する",
            description="SMAIや投資材料について自由に相談します。",
            context_id="copilot_app_help",
            default_question="SMAIナビとして、自由相談を始めてください。",
            prompt_instruction=(
                "SMAIナビの口調で自然に会話してください。投資やSMAI以外の話題では、"
                "主な役割がSMAIと投資判断材料の整理であることを添えてください。"
            ),
        ),
    )
