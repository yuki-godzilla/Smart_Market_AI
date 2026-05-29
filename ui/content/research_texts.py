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
RESEARCH_COCKPIT_SECTION_TITLE = "06 根拠資料"
RESEARCH_RANKING_LOOKUP_TITLE = "AI調査 / 根拠資料"
RESEARCH_COCKPIT_INTRO = (
    "SMAIがニュース・外部情報・補足データを、投資判断前に見る材料へ整理します。"
    "価格予測やスコアだけでは見えない良い材料、注意材料、確認不足を確認できます。"
)
RESEARCH_RANKING_LOOKUP_INTRO = (
    "この銘柄の保存済み資料から、投資判断前に確認したい材料と注意点を整理します。"
)
RESEARCH_FETCH_BUTTON_LABEL = "AI調査を更新"
RESEARCH_RANKING_FETCH_BUTTON_LABEL = "AIで資料を確認"
RESEARCH_FETCH_SPINNER = "外部参照ソースと保存済み資料を、投資判断前の確認メモに整理しています。"
RESEARCH_NOT_FETCHED_MESSAGE = "投資判断メモはまだ作成されていません。「AI調査を更新」を押すと、関連ニュースや外部情報を確認材料に変換できます。"
RESEARCH_INVESTMENT_INSIGHT_TITLE = "SMAI 投資判断サマリー"
RESEARCH_INVESTMENT_INSIGHT_SUMMARY_LABEL = "現在の見立て"
RESEARCH_INVESTMENT_INSIGHT_POSITIVE_LABEL = "良い材料"
RESEARCH_INVESTMENT_INSIGHT_NEGATIVE_LABEL = "注意材料"
RESEARCH_INVESTMENT_INSIGHT_GAPS_LABEL = "まだ判断に足りない情報"
RESEARCH_INVESTMENT_INSIGHT_NOTE = (
    "売買の指示ではなく、source-backed な判断材料と確認不足の整理です。"
)
RESEARCH_INVESTMENT_QUESTION_SUMMARY_TITLE = "投資判断で知りたいこと"
RESEARCH_INVESTMENT_QUESTION_MORE_LABEL = "その他の確認ポイントを見る"
RESEARCH_DETAIL_EXPANDER_LABEL = "詳細データを表示"
RESEARCH_DETAIL_OK_CAPTION = "登録資料から検索できた根拠と観点別サマリです。"


def research_evidence_confirmed_note(evidence_count: int) -> str:
    return f"AI Researchで{evidence_count}件の根拠を確認済みです。"
