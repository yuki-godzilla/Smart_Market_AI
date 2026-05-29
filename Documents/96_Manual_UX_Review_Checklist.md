# 96_Manual_UX_Review_Checklist

#### [BACK TO README](../README.md)

## Purpose

Smart Market AI の主要画面を、実装バグだけでなく「動くが分かりにくい」「期待と違う」「投資助言に見えすぎる」という観点で確認するための手動UXレビュー台帳です。

このチェックリストは、新機能追加の前に既存導線の分かりにくさを棚卸しするために使います。結果は必要に応じて [97_Functional_Spec_Issues.md](./97_Functional_Spec_Issues.md) に転記します。

## Status Values

- `Not tested`: まだ手動確認していない
- `Open`: 問題または曖昧さがある
- `Needs decision`: 仕様判断が必要
- `Resolved`: 文言、仕様、実装、運用のいずれかで解決済み
- `Deferred`: 将来フェーズへ明示的に延期

## Issue Types

- `Spec Ambiguity`
- `UX Confusion`
- `Wording Risk`
- `State Visibility`
- `Data Confidence`
- `Product Safety`
- `Navigation / Flow`
- `Error Recovery`

## Manual UX Review Checklist

| ID | Area | Scenario | Review Steps | Expected Experience | Potential UX Issue | Issue Type | Priority | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UX-001 | Symbol Cockpit | 1銘柄を初めて確認する | 銘柄を選び、期間を選択し、価格データを取得する | 価格、特徴量、Forecast、Investment Score、注意点の関係が順番に理解できる | 情報量が多く、最初に何を見るべきか分からない | UX Confusion | High | Not tested | 初心者視点で確認 |
| UX-002 | Symbol Cockpit | Investment Score を読む | スコア、内訳、警告、メモを確認する | 売買判断ではなく、比較・分析用の補助スコアとして読める | 高スコアが「買うべき」に見える | Product Safety | High | Not tested | Wording policy と照合 |
| UX-003 | Symbol Cockpit | データ不足時の確認 | 欠損や provider warning がある銘柄を表示する | 何が不足し、判断時にどう注意するか分かる | 欠損が単なるエラーに見える、または見逃される | Data Confidence | High | Not tested | Data quality 表示を確認 |
| UX-004 | Ranking | 候補探索を開始する | 条件を選択し、候補数を確認してランキング作成する | Ranking が候補探索・比較の入口だと分かる | 上位銘柄が推奨銘柄に見える | Product Safety | High | Not tested | 「おすすめ」表現を避ける |
| UX-005 | Ranking | 並べ替え条件を変える | 同じ取得結果で ranking purpose / weight preset を変更する | 条件に応じて比較順が変わることが分かる | 条件変更が再取得か再ソートか分からない | State Visibility | Medium | Not tested | cache 表示も確認 |
| UX-006 | Ranking | Database Fit / Metadata Confidence を読む | ランキング結果と詳細モーダルで補助指標を確認する | 投資魅力度ではなく、評価材料の充実度として理解できる | DB適合度が銘柄の良し悪しに見える | Spec Ambiguity | High | Not tested | 97台帳にも記載 |
| UX-007 | Ranking | 銘柄詳細モーダルを開く | ranking row をクリックし、各タブを確認する | 銘柄マスタ、判断補助、AI Research の役割が分かる | タブが多く、何を見ればよいか迷う | Navigation / Flow | Medium | Not tested | タブ名と順序を確認 |
| UX-008 | Ranking | AI Research を使う | `AI Research` タブで `AIで資料を確認` を押す | 外部最新情報と保存済み資料から企業概要・IR・ニュース・定量情報を整理する機能だと分かる | AIが投資判断を代行するように見える | Wording Risk | High | Not tested | Research Evidence 注意書き |
| UX-009 | Rebalance Cockpit | 保有資産の配分を見直す | sample または手入力で目標配分を設定し、結果を確認する | 配分見直しシミュレーションとして読める | 提案売買が注文指示に見える | Product Safety | High | Not tested | Execution deferred を明示 |
| UX-010 | Rebalance Cockpit | Risk breach を確認する | 制約違反が出る入力で結果を確認する | 何を再確認すべきかが分かる | breach が強制的な禁止・指示に見える | Wording Risk | Medium | Not tested | Risk wording を確認 |
| UX-011 | Decision Report | Cockpit report を保存する | Cockpit で Decision Report を作成し Markdown / JSON を確認する | その時点の判断材料、根拠、不確実性の保存だと分かる | レポートが投資推奨書に見える | Product Safety | High | Not tested | 冒頭 note を確認 |
| UX-012 | Decision Report | Ranking report を読む | ランキング結果から Decision Report を作成する | 比較条件、分布、確認ポイントが中心になる | 上位1銘柄の推奨レポートに見える | Wording Risk | High | Not tested | Ranking固有文脈を確認 |
| UX-013 | Decision Report | Rebalance report を読む | Rebalance 結果から report を作成する | 配分差分と確認ポイントの記録として読める | 売買指示書に見える | Product Safety | High | Not tested | broker連携なしを確認 |
| UX-014 | Research Summary / Evidence | 外部最新資料で Research Score を確認する | `AI調査を更新` で外部 source を取得/参照し、Research Summary / Research Score / 根拠カードを表示する | 資料名、公開日、取得日時、provider、URL、根拠数、鮮度、Research Score の内訳と confidence が確認でき、売買推奨ではなく根拠資料の充実度だと分かる | 根拠の鮮度や信頼度が分かりにくい、または高スコアが「買い」に見える | Data Confidence | High | In review | 公式資料、provider snapshot、外部一時取得、local archive の区別も確認 |
| UX-014a | Research Summary / Brief | 企業リサーチレポートを読む | `AI調査を更新` 後に Research Summary 冒頭を確認する | `企業リサーチサマリー` / `定量情報サマリー` / `IR情報サマリー` / `最新ニュースサマリー` が先に読め、AI読み取りメモは折りたたみ内にある。provider raw fields が通常表示に出ず、主な事業、製品・サービス、地域、公式資料、主要数値、直近ニュース、未取得 / 未解析 / 公式未確認が source-backed fact として表示される | 生データ羅列で何を確認すべきか分からない、取得状態だけで中身が分からない、またはAIが投資判断したように見える | UX Readability | High | In review | 情報過多にならず、主表示と折りたたみ詳細の境界が分かるか実画面で確認。確認できた情報 / 注意して読む情報、出典カード、Research Score、外部参照ソース、詳細表は必要時に開く情報として分ける |
| UX-015 | Research Summary / Evidence | 外部取得失敗または資料不足の銘柄を確認する | 外部 source が取得できない銘柄、または保存資料だけの銘柄で Research Summary / Research Score 表示を確認する | 外部取得失敗や根拠不足として控えめに扱われ、低信頼または未取得の参考情報だと分かる。既定の Investment Score / ranking order は変わらない | 情報なしが低評価や売買判断に見える | Spec Ambiguity | Medium | In review | `scoring.weights.research=0.0` の既定挙動と fallback 表示も確認 |
| UX-016 | Forecast | Forecast chart を読む | 複数モデルの予測線、実績線、評価指標を確認する | 予測は不確実な参考情報だと分かる | 予測線が確定未来に見える | Product Safety | High | Not tested | chart label / caption |
| UX-017 | Forecast | Forecast agreement を読む | Investment Score の Forecast agreement を確認する | モデル間の見方の近さとして理解できる | 的中率や予想の正しさに見える | Wording Risk | Medium | Not tested | 用語説明を確認 |
| UX-018 | Risk | Risk score を読む | Ranking / Cockpit / Rebalance で risk 表示を確認する | 価格変動や制約違反の確認材料だと分かる | リスクが低ければ安全と誤解される | Wording Risk | High | Not tested | 安全保証表現を避ける |
| UX-019 | Market Data provider / data freshness | Yahoo live provider を使う | live provider で取得、失敗、再取得を確認する | provider、対象期間、取得失敗、鮮度が分かる | 古い/欠損データであることを見落とす | Data Confidence | High | Not tested | freshness表示を確認 |
| UX-020 | Market Data provider / data freshness | 大量ランキング取得を行う | 30件超の live ranking を実行する | 時間がかかること、部分失敗があり得ることが分かる | 途中停止や部分結果の意味が分からない | Error Recovery | Medium | Not tested | progress / error rows |
| UX-021 | Score explanation / confidence / coverage | Score hierarchy を確認する | Investment Score、Screening、Forecast、Risk、Data Quality、Research Scoreを横断して読む | Investment Score は複数材料の統合参考値、Research Score は根拠資料の充実度・鮮度・信頼度の参考値、Data Quality / Database Fit / Metadata Confidence は信頼度・coverage 系の確認材料として区別できる | スコアが多く、上下関係やranking orderへの影響有無が分からない | Spec Ambiguity | High | In review | FS-013 と合わせて、Research Score が既定順位を変えないことを確認 |
| UX-022 | Score explanation / confidence / coverage | Metadata coverage 欠損を確認する | DB信頼度が低い銘柄を詳細表示する | 評価材料が少ないため慎重に見るべきと分かる | 銘柄自体が悪いと誤解される | Data Confidence | High | Not tested | DB指標の説明を確認 |
| UX-023 | Navigation / Flow | Ranking から Cockpit へ移動する | Rankingで選択銘柄をCockpitに渡す | 比較から深掘りへ進む導線だと分かる | 画面遷移後に何が引き継がれたか分からない | State Visibility | Medium | Not tested | period/provider引継ぎ |
| UX-024 | Error Recovery | provider failure から復帰する | provider error 後に期間や銘柄を変えて再実行する | 原因と次の行動が分かる | raw error が難しい、再試行方法が不明 | Error Recovery | High | Not tested | domain error表示を確認 |
