from __future__ import annotations

from collections.abc import Mapping, Sequence

EMPTY_TEXT = "未登録"
NOT_CALCULATED_TEXT = "未計算"
UNKNOWN_TEXT = "未確認"
OK_TEXT = "OK"
WARN_TEXT = "要確認"
CAUTION_TEXT = "注意"
NO_SYMBOL_CANDIDATE_LABEL = "条件に合う候補なし"

MARKET_DATA_PERIOD_CUSTOM = "custom"
MARKET_DATA_PERIOD_PRESETS = {
    MARKET_DATA_PERIOD_CUSTOM: "カスタム",
    "short_1w": "短期: 1週間",
    "short_1m": "短期: 1か月",
    "medium_3m": "中期: 3か月",
    "medium_6m": "中期: 6か月",
    "ytd": "年初来",
    "long_1y": "長期: 1年",
    "long_3y": "長期: 3年",
    "long_5y": "長期: 5年",
}
MARKET_DATA_PERIOD_HELP_TEXT = {
    MARKET_DATA_PERIOD_CUSTOM: "検証したい決算日、急落日、投資開始想定日に合わせて任意の期間を設定します。",
    "short_1w": "決算・ニュース・急変後の短期反応を確認します。ノイズが大きいため、売買判断の主根拠にはしません。",
    "short_1m": "直近の需給変化やモメンタムの継続性を確認します。短期材料の賞味期限を見る補助期間です。",
    "medium_3m": "四半期決算や業績修正後の評価変化を確認します。短期ノイズと中期トレンドの切り分けに使います。",
    "medium_6m": "半期程度のトレンド、押し目、下落耐性を確認します。投資テーマが市場に織り込まれているかを見ます。",
    "ytd": "年初来の市場環境に対する相対感を確認します。同じ年の地合いの中で強弱を比べる時に使います。",
    "long_1y": "直近1年の業績期待、相場循環、リスク耐性を確認します。初期レビューの基準期間として使いやすい設定です。",
    "long_3y": "複数決算期をまたぐ成長持続性と景気感応度を確認します。一時的な上振れや下振れをならして見ます。",
    "long_5y": "長期の構造変化、最大下落、回復力を確認します。長期保有の候補では必ず確認したい期間です。",
}

FORECAST_ACTUAL_LABEL = "実績価格"
MARKET_DATA_MODE_LABELS = {
    "cockpit": "銘柄コックピット",
    "ranking": "銘柄ランキング",
}

DECISION_SUPPORT_DISCLAIMER = (
    "SMAIの表示は投資判断を補助する確認材料であり、売買を推奨するものではありません。"
)
DECISION_REPORT_SUPPORT_MESSAGE = (
    "このレポートは、その時点の判断材料、根拠、不確実性、確認ポイントを保存する分析メモです。"
    "買い・売り・保有の指示ではありません。"
)
DECISION_REPORT_DOWNLOAD_GUIDE = (
    "Markdownは読む用、JSONは再現用、manifestは同梱内容の確認用、ZIPは一式保存用です。"
)
DECISION_REPORT_MARKDOWN_DOWNLOAD_LABEL = "Markdown（読む用）をダウンロード"
DECISION_REPORT_JSON_DOWNLOAD_LABEL = "JSON（再現用）をダウンロード"
DECISION_REPORT_MANIFEST_DOWNLOAD_LABEL = "manifest（内容確認）をダウンロード"
DECISION_REPORT_ZIP_DOWNLOAD_LABEL = "一式ZIP（保存用）をダウンロード"
DECISION_REPORT_MARKDOWN_DOWNLOAD_HELP = (
    "人が読むためのMarkdown形式です。判断材料、根拠、不確実性、確認ポイントを見返す用途に使います。"
)
DECISION_REPORT_JSON_DOWNLOAD_HELP = (
    "画面表示やレポート生成に使った構造化contextです。再現確認や後続処理に使います。"
)
DECISION_REPORT_MANIFEST_DOWNLOAD_HELP = (
    "レポート一式に含まれるファイル、情報元、作成日時を確認するための一覧です。"
)
DECISION_REPORT_ZIP_DOWNLOAD_HELP = "Markdown、JSON、manifestをまとめた保存用パッケージです。"

NG_INVESTMENT_ADVICE_TERMS = (
    "買い" + "推奨",
    "売り" + "推奨",
    "上がる" + "銘柄",
    "下がる" + "銘柄",
    "上昇" + "確定",
    "下落" + "確定",
    "必ず" + "上がる",
    "必ず" + "下がる",
)

COMMON_COLUMN_LABELS = {
    "field": "項目",
    "value": "内容",
    "code": "コード",
    "message": "内容",
    "details": "診断情報",
    "component": "区分",
    "symbol": "銘柄コード",
    "name": "銘柄名",
    "rank": "順位",
    "provider": "データ取得元",
    "source": "出典",
    "source_url": "出典URL",
    "source_type": "資料種別",
    "published_at": "公開日",
    "collected_at": "取得日時",
    "fetched_at": "取得日時",
    "as_of": "基準日",
    "ts": "日時",
    "bars": "価格データ数",
    "first_ts": "開始日時",
    "last_ts": "終了日時",
    "first_close": "開始終値",
    "last_close": "直近終値",
    "total_volume": "出来高合計",
    "bid": "買気配",
    "ask": "売気配",
    "last": "現在値",
    "model": "モデル",
    "horizon_days": "予測日数",
    "forecast_close": "予測終値",
    "ensemble_forecast_close": "平均予測",
    "median_forecast_close": "中央値予測",
    "min_forecast_close": "予測下限",
    "max_forecast_close": "予測上限",
    "forecast_range": "予測レンジ",
    "forecast_range_pct": "予測レンジ(%)",
    "forecast_return_pct": "予測変化率",
    "mae": "MAE",
    "rmse": "RMSE",
    "direction_accuracy": "方向一致率",
    "sample_count": "評価サンプル数",
    "model_count": "モデル数",
    "agreement": "モデル一致度",
    "up_model_count": "上向きモデル数",
    "down_model_count": "下向きモデル数",
    "flat_model_count": "横ばいモデル数",
    "up_direction_ratio": "上向き比率",
    "down_direction_ratio": "下向き比率",
    "upside_signal_score": "上昇気配",
    "downside_signal_score": "下降警戒",
    "direction_net_score": "方向シグナル(補助)",
    "direction_signal_label": "方向ラベル(補助)",
    "total_score": "総合スコア",
    "score_band": "評価",
    "screening_score": "スクリーニング",
    "forecast_agreement_score": "モデル一致度",
    "data_quality_score": "データ品質",
    "database_fit_score": "条件適合度",
    "metadata_confidence_score": "DB信頼度",
    "research_score": "根拠スコア",
    "risk_signal_score": "リスク確認",
    "risk_score": "リスク確認",
    "momentum_score": "モメンタム",
    "liquidity_score": "流動性",
    "forecast_score": "予測評価",
    "data_quality": "データ品質",
    "summary": "サマリー",
    "forecast_reason": "予測理由",
    "reason_labels": "理由ラベル",
    "reasons": "理由",
    "warnings": "注意点",
    "note": "補足",
    "feature_version": "特徴量バージョン",
    "close_1d": "1日前終値",
    "return_1d": "1日リターン",
    "momentum_5d": "5日モメンタム",
    "adv_20d": "20日平均売買代金",
    "vol_20d": "20日ボラティリティ",
    "drawdown_20d": "20日ドローダウン",
    "data_completeness": "データ充足率",
    "dividend_yield": "配当利回り",
    "market_cap_jpy": "時価総額(円)",
    "data_quality_reasons": "データ品質理由",
    "missing": "欠損項目",
    "missing_summary": "欠損サマリー",
    "qty": "数量",
    "currency": "通貨",
    "fx_rate_jpy": "為替レート(円)",
    "value_jpy": "評価額(円)",
    "target_weight": "目標比率",
    "current_weight": "現在比率",
    "drift": "差分",
    "side": "見直し方向",
    "price_hint": "参考価格",
    "breach": "確認事項",
    "account_id": "口座ID",
    "cash_jpy": "現金(円)",
    "total_value_jpy": "現在資産(円)",
    "trade_count": "見直し候補数",
    "risk_status": "リスク判定",
    "adapter_protocol": "接続方式",
    "implemented": "実装状況",
    "live_adapter": "ライブ取得",
    "smoke_check_status": "動作確認状況",
    "timeout_seconds": "タイムアウト秒数",
}

EMPTY_STATE_MESSAGES = {
    "ranking_rows": "ランキングはまだ作成されていません。条件を指定して作成してください。",
    "investment_score_rows": "投資スコアはまだありません。",
    "chart_rows": "チャートに表示できるデータがありません。",
    "forecast_summary": "予測サマリーはまだありません。",
    "forecast_metrics": "予測精度データはまだありません。",
    "provider_metadata": "取得元情報はまだありません。",
    "quote_rows": "現在値データはまだありません。",
    "ohlcv_rows": "価格データはまだありません。",
    "fx_rows": "為替データはまだありません。",
    "feature_snapshot_rows": "特徴量データはまだありません。",
    "screening_score_rows": "スクリーニングスコアはまだありません。",
    "ranking_errors": "取得エラーはありません。",
    "current_positions": "現在の保有データはまだありません。",
    "target_allocations": "目標配分はまだありません。",
    "allocation_comparison": "配分比較に表示できるデータがありません。",
    "rebalance_candidates": "配分見直し候補はありません。",
    "detail_rows": "表示できる詳細データはまだありません。",
}


def user_facing_column_label(column: str) -> str:
    return COMMON_COLUMN_LABELS.get(column, column)


def user_facing_table_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        {user_facing_column_label(str(column)): value for column, value in row.items()}
        for row in rows
    ]
