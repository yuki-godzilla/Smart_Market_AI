from __future__ import annotations

import html
from uuid import uuid4

import streamlit as st

from backend.assistant import AssistantMessage, AssistantResponse
from ui.components.assistant import SmaiAssistantContext, assistant_response_for_context
from ui.components.mascot import render_page_title

COPILOT_CHAT_HISTORY_STATE_KEY = "smai_copilot_chat_history"
COPILOT_CONVERSATION_ID_STATE_KEY = "smai_copilot_conversation_id"


def copilot_context_options() -> tuple[SmaiAssistantContext, ...]:
    return (
        SmaiAssistantContext(
            context_id="copilot_cockpit_overview",
            page_key="cockpit",
            page_label="銘柄コックピット",
            section_key="copilot_cockpit",
            section_label="価格・予測・材料確認",
            lead="1銘柄の価格、AI予測インサイト、上昇気配、下降警戒、根拠資料を整理します。",
            summary={
                "用途": "単一銘柄の深掘り",
                "主な材料": "価格チャート、AI予測インサイト、Risk、Research Evidence",
            },
            suggested_questions=(
                "この銘柄でまず確認する順番は？",
                "AI予測インサイトと下降警戒をどう見比べる？",
                "Decision Reportに残す確認点は？",
            ),
            priority=80,
        ),
        SmaiAssistantContext(
            context_id="copilot_ranking_overview",
            page_key="ranking",
            page_label="銘柄ランキング",
            section_key="copilot_ranking",
            section_label="候補比較",
            lead="ランキング上位候補を、総合スコア、上昇気配、下降警戒、データ信頼度で比べます。",
            summary={
                "用途": "候補の比較",
                "主な材料": "AI総合、上昇気配、下降警戒、データ信頼度、深掘り候補",
            },
            suggested_questions=(
                "ランキング上位候補は何から比べる？",
                "AI総合・上昇気配・下降警戒の違いは？",
                "低信頼データの候補はどう扱う？",
            ),
            priority=70,
        ),
        SmaiAssistantContext(
            context_id="copilot_news_overview",
            page_key="news",
            page_label="投資レーダー",
            section_key="copilot_news",
            section_label="ニュース材料確認",
            lead="市場ニュース、カテゴリ別材料、関連銘柄、出典と鮮度を分けて確認します。",
            summary={
                "用途": "ニュースから確認候補を探す",
                "主な材料": "市場ニュース、投資ヒートマップ、関連銘柄、source URL",
            },
            suggested_questions=(
                "今日のニュースはどこから見る？",
                "関連銘柄はどう深掘りする？",
                "出典と鮮度で何を確認する？",
            ),
            priority=60,
        ),
        SmaiAssistantContext(
            context_id="copilot_llm_factor_overview",
            page_key="cockpit",
            page_label="銘柄コックピット",
            section_key="llm_factor_reference",
            section_label="AI材料分析",
            lead="RAG・ニュース・IR由来の定性材料を参考スコアとして読み、予測や順位とは分けて扱います。",
            summary={
                "用途": "定性材料の参考確認",
                "主な材料": "強気材料、弱気材料、カタリスト、リスク、出典URL、材料鮮度",
                "統合状態": "Forecast、Ranking、Investment Scoreには未統合",
            },
            warnings=(
                "LLM材料分析は参考表示であり、売買推奨やランキング順位の決定には使いません。",
            ),
            suggested_questions=(
                "AI材料分析は予測とどう分けて読む？",
                "強気材料と弱気材料の両方が高い時は？",
                "出典URLと材料鮮度では何を見る？",
            ),
            priority=50,
        ),
        SmaiAssistantContext(
            context_id="copilot_rebalance_overview",
            page_key="rebalance",
            page_label="リバランス",
            section_key="copilot_rebalance",
            section_label="配分見直し",
            lead="現在比率、目標比率、ズレ、提案取引、リスク警告を確認します。",
            summary={
                "用途": "配分見直し",
                "主な材料": "現在比率、目標比率、提案取引、Risk check",
            },
            suggested_questions=(
                "配分のズレは何から見る？",
                "提案取引はどう確認する？",
                "リスク警告がある時は？",
            ),
            priority=40,
        ),
    )


def copilot_context_label(context: SmaiAssistantContext) -> str:
    return f"{context.page_label} / {context.section_label}"


def copilot_history_messages(
    turns: list[dict[str, str]],
    *,
    max_turns: int = 4,
) -> list[AssistantMessage]:
    messages: list[AssistantMessage] = []
    for turn in turns[-max_turns:]:
        question = str(turn.get("question", "")).strip()
        answer = str(turn.get("answer", "")).strip()
        if question:
            messages.append(AssistantMessage(role="user", content=question))
        if answer:
            messages.append(AssistantMessage(role="assistant", content=answer))
    return messages


def copilot_turn_html(turn: dict[str, str]) -> str:
    question = html.escape(str(turn.get("question", "")))
    answer = html.escape(str(turn.get("answer", "")))
    context_label = html.escape(str(turn.get("context_label", "")))
    reasons = _list_html(_split_lines(turn.get("reasons", "")))
    cautions = _list_html(_split_lines(turn.get("cautions", "")))
    checkpoints = _list_html(_split_lines(turn.get("next_checkpoints", "")))
    return (
        '<article class="smai-copilot-turn">'
        '<div class="smai-copilot-user">'
        f"<span>{context_label}</span>"
        f"<strong>{question}</strong>"
        "</div>"
        '<div class="smai-copilot-answer">'
        f"<p>{answer}</p>"
        '<div class="smai-copilot-answer-grid">'
        f'{_block_html("見る材料", reasons)}'
        f'{_block_html("注意点", cautions)}'
        f'{_block_html("次に確認", checkpoints)}'
        "</div>"
        "</div>"
        "</article>"
    )


def render_copilot_workspace_page() -> None:
    render_page_title(
        "SMAI Copilot",
        "銘柄、ランキング、ニュース、配分見直しの確認材料を横断して整理します。",
        "cockpit",
    )
    st.markdown('<section class="smai-copilot-workspace">', unsafe_allow_html=True)

    contexts = copilot_context_options()
    labels = [copilot_context_label(context) for context in contexts]
    selected_label = st.selectbox("相談文脈", labels, key="smai_copilot_context_select")
    selected_context = contexts[labels.index(selected_label)]
    quick_questions = tuple(selected_context.suggested_questions)
    selected_question = st.selectbox(
        "質問例",
        quick_questions,
        key="smai_copilot_question_example",
    )
    question = st.text_area(
        "質問",
        value=selected_question,
        max_chars=240,
        key="smai_copilot_question",
    )

    left, right = st.columns([1, 1])
    with left:
        submit = st.button("Copilotに確認", type="primary", use_container_width=True)
    with right:
        clear = st.button("履歴をクリア", use_container_width=True)

    if clear:
        st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = []
        st.session_state[COPILOT_CONVERSATION_ID_STATE_KEY] = _new_conversation_id()

    if submit:
        _handle_copilot_submit(selected_context, question)

    history = _copilot_history()
    if not history:
        st.info("相談する文脈を選び、質問を入力すると、確認材料・注意点・次に見る点を整理します。")
    else:
        st.markdown("#### 会話履歴")
        for turn in history:
            st.markdown(copilot_turn_html(turn), unsafe_allow_html=True)

    st.caption(
        "SMAI Copilotは判断材料の整理を補助します。"
        "売買推奨、スコア変更、ランキング順位変更は行いません。"
    )
    st.markdown("</section>", unsafe_allow_html=True)


def _handle_copilot_submit(context: SmaiAssistantContext, question: str) -> None:
    normalized_question = question.strip()
    if not normalized_question:
        st.warning("質問を入力してください。")
        return

    history = _copilot_history()
    conversation_id = _conversation_id()
    response = assistant_response_for_context(
        context,
        normalized_question,
        conversation_id=conversation_id,
        message_history=copilot_history_messages(history),
        referenced_context_ids=[context.context_id],
    )
    history.append(_turn_from_response(context, normalized_question, response))
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = history


def _turn_from_response(
    context: SmaiAssistantContext,
    question: str,
    response: AssistantResponse,
) -> dict[str, str]:
    return {
        "context_id": context.context_id,
        "context_label": copilot_context_label(context),
        "question": question,
        "answer": response.answer,
        "reasons": "\n".join(response.reasons),
        "cautions": "\n".join(response.cautions),
        "next_checkpoints": "\n".join(response.next_checkpoints),
    }


def _copilot_history() -> list[dict[str, str]]:
    raw_history = st.session_state.get(COPILOT_CHAT_HISTORY_STATE_KEY)
    if not isinstance(raw_history, list):
        raw_history = []
        st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = raw_history
    return [
        {str(key): str(value) for key, value in item.items()}
        for item in raw_history
        if isinstance(item, dict)
    ]


def _conversation_id() -> str:
    conversation_id = st.session_state.get(COPILOT_CONVERSATION_ID_STATE_KEY)
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        conversation_id = _new_conversation_id()
        st.session_state[COPILOT_CONVERSATION_ID_STATE_KEY] = conversation_id
    return conversation_id


def _new_conversation_id() -> str:
    return f"smai-copilot-{uuid4().hex}"


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _block_html(title: str, body: str) -> str:
    if not body:
        return ""
    return (
        '<section class="smai-copilot-answer-block">'
        f"<span>{html.escape(title)}</span>"
        f"{body}"
        "</section>"
    )


def _list_html(items: list[str]) -> str:
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items[:4]) + "</ul>"
