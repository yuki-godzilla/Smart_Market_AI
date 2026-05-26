from __future__ import annotations

RESEARCH_STATUS_WITH_EVIDENCE = "根拠あり"
RESEARCH_STATUS_INSUFFICIENT = "根拠不足"
RESEARCH_STATUS_STALE = "最新資料が古い"

RESEARCH_NO_REGISTERED_DOCUMENTS = "登録済みResearch資料がありません。"
RESEARCH_DOCUMENTS_OR_CHUNKS_MISSING = (
    "登録済みResearch資料または検索チャンクがないため、資料面の根拠は限られます。"
)
RESEARCH_REGISTERED_EVIDENCE_NOTE = (
    "登録済みResearch資料があります。詳細モーダルのAI Researchで根拠抜粋を確認できます。"
)
RESEARCH_STALE_DOCUMENT_NOTE = (
    "登録資料はありますが、最新資料日が2年以上前です。新しいIR資料や決算資料を確認してください。"
)
RESEARCH_STALE_REPORT_NOTE = "AI Researchで根拠は見つかりましたが、最新資料日が2年以上前です。"
RESEARCH_INSUFFICIENT_REPORT_NOTE = (
    "AI Researchでは十分な根拠を確認できませんでした。資料登録や別資料の確認が必要です。"
)
RESEARCH_EVIDENCE_CHECK_FALLBACK = "AI Researchで資料根拠を確認します。"
RESEARCH_COCKPIT_SECTION_TITLE = "06 Research Evidence / 根拠資料"
RESEARCH_RANKING_LOOKUP_TITLE = "AI Research / 根拠資料"
RESEARCH_COCKPIT_INTRO = (
    "価格データ取得時にはResearch RAGを自動実行しません。"
    "登録済み資料から根拠を整理したい場合だけ、AIデータ取得を実行してください。"
)
RESEARCH_RANKING_LOOKUP_INTRO = (
    "この銘柄の登録資料から、投資判断前に確認したい材料と注意点を整理します。"
)
RESEARCH_FETCH_BUTTON_LABEL = "AIデータ取得"
RESEARCH_RANKING_FETCH_BUTTON_LABEL = "AIで資料を確認"
RESEARCH_FETCH_SPINNER = "Research資料から根拠を整理しています。"
RESEARCH_NOT_FETCHED_MESSAGE = (
    "Research RAGは未取得です。必要な場合は「AIデータ取得」を押してください。"
)
RESEARCH_DETAIL_EXPANDER_LABEL = "Research RAG 詳細"
RESEARCH_DETAIL_OK_CAPTION = "登録資料から検索できた根拠と観点別サマリです。"


def research_evidence_confirmed_note(evidence_count: int) -> str:
    return f"AI Researchで{evidence_count}件の根拠を確認済みです。"
