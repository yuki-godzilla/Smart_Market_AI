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
    "SMAIが銘柄分析時に参照したニュース・外部情報・補足データです。"
    "投資判断の背景を確認し、価格予測やスコアだけでは見えない材料を把握できます。"
)
RESEARCH_RANKING_LOOKUP_INTRO = (
    "この銘柄の登録資料から、投資判断前に確認したい材料と注意点を整理します。"
)
RESEARCH_FETCH_BUTTON_LABEL = "AI調査を更新"
RESEARCH_NEWS_BUTTON_LABEL = "ニュースのみ再取得"
RESEARCH_NEWS_SPINNER = "登録済みニュース資料から確認材料を整理しています。"
RESEARCH_NEWS_NOT_FETCHED_MESSAGE = (
    "Recent News はまだ整理されていません。登録済みの news 資料からURL付きニュースを確認する場合は"
    "「ニュースのみ再取得」を実行してください。"
)
RESEARCH_NEWS_EMPTY_MESSAGE = (
    "URL付きのニュース根拠は見つかりませんでした。"
    "source_type=news の資料に URL を含めて登録してください。"
)
RESEARCH_RANKING_FETCH_BUTTON_LABEL = "AIで資料を確認"
RESEARCH_FETCH_SPINNER = "Research資料から根拠を整理しています。"
RESEARCH_NOT_FETCHED_MESSAGE = "根拠資料はまだ取得されていません。「AI調査を更新」を押すと、関連ニュースや外部情報を確認できます。"
RESEARCH_DETAIL_EXPANDER_LABEL = "詳細データを表示"
RESEARCH_DETAIL_OK_CAPTION = "登録資料から検索できた根拠と観点別サマリです。"


def research_evidence_confirmed_note(evidence_count: int) -> str:
    return f"AI Researchで{evidence_count}件の根拠を確認済みです。"
