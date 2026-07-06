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
| UX-001 | Symbol Cockpit | 1銘柄を初めて確認する | 銘柄を選び、期間を選択し、価格データを取得する | 価格、特徴量、Forecast、Investment Score、注意点の関係が順番に理解できる | 情報量が多く、最初に何を見るべきか分からない | UX Confusion | High | Resolved | 2026-07-04に取得後主導線を`01 判断サマリー`→`02 価格・AI予測`→`03 AI調査・材料分析`→`04 確認メモ`→`05 確認レポート`へ再編。長い表とexportを単一の詳細expanderへ退避し、mock 7203.Tを4 viewportで確認。live provider確認は任意の運用smokeとして継続 |
| UX-002 | Symbol Cockpit | Investment Score を読む | スコア、内訳、警告、メモを確認する | 売買判断ではなく、比較・分析用の補助スコアとして読める | 高スコアが「買うべき」に見える | Product Safety | High | Resolved | 2026-07-04に初期KPIを投資スコア、上昇気配、下降警戒、データ信頼度の4枚へ限定し、SMAI InsightをKPI直下へ配置。スコア詳細は折りたたみへ退避し、非助言captionを含む取得後画面を4 viewportで確認 |
| UX-003 | Symbol Cockpit | データ不足時の確認 | 欠損や provider warning がある銘柄を表示する | 何が不足し、判断時にどう注意するか分かる | 欠損が単なるエラーに見える、または見逃される | Data Confidence | High | Not tested | Data quality 表示を確認 |
| UX-004 | Ranking | 候補探索を開始する | 条件を選択し、候補数を確認してランキング作成する | Ranking が候補探索・比較の入口だと分かる | 上位銘柄が推奨銘柄に見える | Product Safety | High | In review | 2026-06-03に評価方針・詳細条件・信頼度の読み方ガイドを追加し、Chrome headless + 8502 実画面で展開確認。取得後ランキング結果は継続確認 |
| UX-005 | Ranking | 評価方針 / 詳細テーブル列ソートを変える | 同じ取得結果で評価方針を変更し、詳細テーブルの列名もクリックする | 評価方針は候補探索の主導線、列ソートは表示済み候補の補助操作だと分かる | 評価方針変更と列ソートの役割、再取得有無が分からない | State Visibility | Medium | In review | 2026-06-03に評価方針=取得後の並べ替え、詳細条件=取得前の絞り込みとして説明を追加し、Chrome headless + 8502 実画面で確認。cache 表示は継続確認 |
| UX-006 | Ranking | Database Fit / Metadata Confidence を読む | ランキング結果と詳細モーダルで補助指標を確認する | 投資魅力度ではなく、評価材料の充実度として理解できる | DB適合度が銘柄の良し悪しに見える | Spec Ambiguity | High | In review | 2026-06-03に条件適合度 / DB信頼度は投資魅力度ではなく評価材料の充実度だとガイドで明示し、Chrome headless + 8502 実画面で確認。結果表 / 詳細モーダルは継続確認 |
| UX-007 | Ranking | 銘柄詳細モーダルを開く | ranking row をクリックし、各タブを確認する | 銘柄マスタ、判断補助、AI Research の役割が分かる | タブが多く、何を見ればよいか迷う | Navigation / Flow | Medium | Not tested | タブ名と順序を確認 |
| UX-008 | Ranking | AI Research を使う | `AI Research` タブで `AIで資料を確認` を押す | 外部最新情報と保存済み資料から企業概要・IR・ニュース・定量情報を整理する機能だと分かる | AIが投資判断を代行するように見える | Wording Risk | High | Not tested | Research Evidence 注意書き |
| UX-009 | Rebalance Cockpit | 保有資産の配分を見直す | sample または手入力で目標配分を設定し、結果を確認する | 配分見直しシミュレーションとして読める | 提案売買が注文指示に見える | Product Safety | High | Not tested | Execution deferred を明示 |
| UX-010 | Rebalance Cockpit | Risk breach を確認する | 制約違反が出る入力で結果を確認する | 何を再確認すべきかが分かる | breach が強制的な禁止・指示に見える | Wording Risk | Medium | Not tested | Risk wording を確認 |
| UX-011 | Decision Report | Cockpit report を保存する | Cockpit で Decision Report を作成し Markdown / JSON を確認する | あとから見返すための確認メモとして、価格・予測・根拠資料・注意点が整理されていると分かる | レポートが投資推奨書に見える | Product Safety | High | In review | 2026-06-19 Phase 31-Aで共通冒頭noteを確認メモ表現へ更新。実画面で継続確認 |
| UX-012 | Decision Report | Ranking report を読む | ランキング結果から Decision Report を作成する | 比較条件、分布、確認ポイントが中心になる | 上位1銘柄の推奨レポートに見える | Wording Risk | High | In review | 2026-06-19 Phase 31-AでRanking reportの通常UIを確認レポート表現へ更新。実画面で継続確認 |
| UX-013 | Decision Report | Rebalance report を読む | Rebalance 結果から report を作成する | 配分差分と確認ポイントの記録として読める | 売買指示書に見える | Product Safety | High | In review | 売買指示ではない説明と形式説明を補強済み。broker連携なしを継続確認 |
| UX-014 | Research Summary / Evidence | 外部最新資料で Research Score を確認する | `AI調査を更新` で外部 source を取得/参照し、Research Summary / Research Score / 根拠カードを表示する | 資料名、公開日、取得日時、provider、URL、根拠数、鮮度、Research Score の内訳と confidence が確認でき、売買推奨ではなく根拠資料の充実度だと分かる | 根拠の鮮度や信頼度が分かりにくい、または高スコアが「買い」に見える | Data Confidence | High | Resolved | 2026-06-02に国内大型/中小型、米国大型/中小型、国内ETF、海外ETF、資料不足ケースの24銘柄で回帰確認。Cockpitでは根拠資料の確認材料、Ranking lookupでは参考情報として表示される |
| UX-014a | Research Summary / Brief | 企業リサーチレポートを読む | `AI調査を更新` 後に Research Summary 冒頭を確認する | `企業リサーチサマリー` / `定量情報サマリー` / `IR情報サマリー` / `最新ニュース・開示サマリー` が先に読め、provider raw fields が通常表示に出ず、主な事業、製品・サービス、地域、公式資料、主要数値、直近ニュース/開示、未取得 / 未解析 / 公式未確認が source-backed fact として表示される。`詳細情報・開発者向け` は Research Score、データ品質、検索品質、抽出主張、根拠資料詳細、外部source取得状況など、通常表示と用途が重ならない検証用データに絞られている | 生データ羅列で何を確認すべきか分からない、取得状態だけで中身が分からない、またはAIが投資判断したように見える。詳細 expander が多すぎて主表示より目立つ、または上のサマリと同じ用途の情報を再掲している | UX Readability | High | In review | 2026-06-01に国内株 / 海外株 / ETF の実画面で確認済み。2026-06-03に詳細情報を単一の `詳細情報・開発者向け` expanderへ集約し、用途重複セクションを削減。実画面回帰で通常画面の階層感を確認する |
| UX-014b | Research Summary / News source URL | ニュース・開示URL導線を確認する | `AI調査を更新` 後に `最新ニュース・開示サマリー` と `ニュース・開示の出典を表示（URL付きN件）` を確認する | サマリと注目材料は主表示カードとして読め、出典は初期折りたたみの小さな引用リストとして補足的に確認できる。URL付きニュース、TDnet、企業IR、EDINET、Yahoo Finance の href、`target="_blank"`、`rel="noopener noreferrer"` は維持され、raw URL文字列は本文表示されない。ニュース専用URLが無い場合も、外部参照ソース側の公式資料・provider URLがある可能性が伝わる | URL表示が未実装に見える、ニュースと公式開示が混同される、provider raw fields や取得本文が通常UIに出る、クリック可能性が分からない、出典がサマリと同じ重さに見える | UX Readability | High | In review | 2026-06-03に出典パネルを初期折りたたみの小さな citation list へ変更。実画面回帰で国内株 / 米国株 / ETF / source no-op / 大阪ガスを確認する |
| UX-014c | Research Summary / Investment hint news | 投資ヒントニュースカードを確認する | `AI調査を更新` 後に `投資ヒントとなるニュース` / `注目材料 Top 3` を確認する | URL付き一般ニュースだけがIR/開示とは別系統のヘッドラインカードで表示され、TDnet、企業IR、EDINET、provider profile、URL不足ニュースは混ざらない。タイトル、公開日、鮮度、出典、材料分類、確認観点、短い要約、ニュース/重要材料/リスク材料のアクセント、右側の `元記事を見る` 導線が読め、カード全体をクリックしてURLへ移動できる。raw URLや長い解説が通常カードに出ず、売買推奨やランキング順位変更に見えない | ニュース・開示・provider source が混ざり、何が投資ヒントニュースか分からない。カードが重く、URL文字列や説明が多すぎる | UX Readability | High | In review | Market Intelligence Top 3 layout polish slice 実装済み。provider breadth拡張は後続 scope |
| UX-015 | Research Summary / Evidence | 外部取得失敗または資料不足の銘柄を確認する | 外部 source が取得できない銘柄、または保存資料だけの銘柄で Research Summary / Research Score 表示を確認する | 外部取得失敗や根拠不足として控えめに扱われ、低信頼または未取得の参考情報だと分かる。既定の Investment Score / ランキング順位は変わらない | 情報なしが低評価や売買判断に見える | Spec Ambiguity | Medium | Resolved | 2026-06-01に外部取得失敗 / 資料不足ケースを実画面で確認済み。通常警告は日本語の fallback 説明、raw provider detail は `取得失敗の技術詳細` に折りたたみ |
| UX-016 | Forecast | Forecast chart を読む | 複数モデルの予測線、実績線、評価指標を確認する | 予測は不確実な参考情報だと分かる | 予測線が確定未来に見える | Product Safety | High | Resolved | 2026-07-04に`02 価格・AI予測`へ予測設定を集約し、予測日数を日本語化。mock 7203.T・予測1日でモバイルチャート描画、viewport内配置、将来保証ではない説明をPlaywrightで確認 |
| UX-017 | Forecast | Forecast agreement を読む | Investment Score の Forecast agreement を確認する | モデル間の見方の近さとして理解できる | 的中率や予想の正しさに見える | Wording Risk | Medium | Resolved | 2026-07-04にモデル一致・検証指標を初期表示から詳細へ退避し、主表示はSMAI Insightと予測レンジ中心に整理。mock取得後画面と既存表示契約testで確認 |
| UX-018 | Risk | Risk score を読む | Ranking / Cockpit / Rebalance で risk 表示を確認する | 価格変動や制約違反の確認材料だと分かる | リスクが低ければ安全と誤解される | Wording Risk | High | In review | Cockpitは2026-07-04に重複していたリスク確認KPIを外し、下降警戒とSMAI Insightへ整理。詳細値は折りたたみで維持し4 viewport確認済み。Ranking / Rebalance側の横断確認は継続 |
| UX-019 | Market Data provider / data freshness | Yahoo live provider を使う | live provider で取得、失敗、再取得を確認する | provider、対象期間、取得失敗、鮮度が分かる | 古い/欠損データであることを見落とす | Data Confidence | High | Not tested | freshness表示を確認 |
| UX-020 | Market Data provider / data freshness | 大量ランキング取得を行う | 30件超の live ranking を実行する | 時間がかかること、部分失敗があり得ることが分かる | 途中停止や部分結果の意味が分からない | Error Recovery | Medium | Not tested | progress / error rows |
| UX-021 | Score explanation / confidence / coverage | Score hierarchy を確認する | Investment Score、Screening、Forecast、Risk、Data Quality、Research Scoreを横断して読む | Investment Score は複数材料の統合参考値、Research Score は根拠資料の充実度・鮮度・信頼度の参考値、Data Quality / Database Fit / Metadata Confidence は信頼度・coverage 系の確認材料として区別できる | スコアが多く、上下関係やランキング順位への影響有無が分からない | Spec Ambiguity | High | Resolved | 2026-06-02のPhase 22回帰で、Research Score が売買推奨・総合スコア・ランキング順位と混同されにくい表示であることを確認。Ranking統合は引き続き見送り |
| UX-022 | Score explanation / confidence / coverage | Metadata coverage 欠損を確認する | DB信頼度が低い銘柄を詳細表示する | 評価材料が少ないため慎重に見るべきと分かる | 銘柄自体が悪いと誤解される | Data Confidence | High | Not tested | DB指標の説明を確認 |
| UX-023 | Navigation / Flow | Ranking から Cockpit へ移動する | Rankingで選択銘柄をCockpitに渡す | 比較から深掘りへ進む導線だと分かる | 画面遷移後に何が引き継がれたか分からない | State Visibility | Medium | Not tested | period/provider引継ぎ |
| UX-024 | Error Recovery | provider failure から復帰する | provider error 後に期間や銘柄を変えて再実行する | 原因と次の行動が分かる | raw error が難しい、再試行方法が不明 | Error Recovery | High | Not tested | domain error表示を確認 |
| UX-025 | Investment News dashboard | 投資レーダー画面を開く | サイドメニューから `投資レーダー` を開き、市場ニュースヘッドライン、投資ヒートマップ、カテゴリ別ニュースレーン、銘柄名付き関連銘柄導線を確認する | 市場ニュースの温度感と確認候補を把握し、気になる材料は `銘柄コックピット` で深掘りする入口だと分かる。Investment Score / Research Score / Ranking順位は変わらない | ニュースや投資ヒートマップが売買推奨や銘柄推奨に見える、値動き色が投資判断そのものに見える | Product Safety | High | In review | Phase 22.x 初期MVP実装済み。禁止表現、URL、freshness、source type、銘柄名付き関連銘柄 handoff は自動テストで確認。実画面smokeで表示密度と遷移を確認する |
| UX-N01 | 通知センター | 通知カードから今日見る材料を確認する | カテゴリ、重要度、要約、SMAI上の変化、次に見ること、CTAを読む | 通知だけで売買判断を完結せず、対象画面で根拠を確認する入口だと分かる | 高スコア、上昇、注目候補が買い推奨に見える | Product Safety | High | Planned | N4 UI実装時にカード密度、色以外の重要度表現、CTAの非自動実行を確認 |
| UX-N02 | お気に入り通知 | お気に入り追加以降レポートを読む | 登録日、登録時価格、現在価格、参考変化、AI総合変化を確認する | SMAI推奨実績ではなく監視開始後の参考変化と分かり、欠損値は未取得になる | 現在値から登録時価格を推定する、運用成績や推奨実績に見える | Product Safety / Data Quality | High | Planned | 登録時snapshot保存後に実装。既存お気に入りの欠損を推定補完しない |
| UX-N03 | ntfy通知 | スマートフォンPushを受け取る | 短い要約から通知センターまたは対象画面を開く | topicや内部情報が見えず、tapで外部取得や注文が自動実行されない | Push本文が長い、秘密値露出、tapで破壊的処理が走る | Security / UX | High | Planned | N3-B以降。通常テストはfake transportのみ |
| UX-N04 | 通知 / 右上ユーザーエリア | 全画面から表示ユーザーと設定入口を確認する | 固定右上入口からユーザー設定、通知設定、ユーザー切替を操作する | メニューが3項目に収まり、通知先とアイコンはユーザー設定、通知カテゴリは通知設定に分かれる | スマホで横overflow、スクロールで入口が消える、設定の役割が混ざる | Security / Responsive UX | High | In review | network-free UI契約test実装済み。4 viewportの固定表示とプロフィール画像選択を実画面確認する |
| UX-N05 | ユーザーicon Asset | 初回選択・右上・設定でiconを確認する | manifest候補から高品質local Assetを選択し、大/小表示とfallbackを確認する | icon IDだけが保存され、画像未配置でもカードが崩れない | 絵文字プロフィール、外部画像、縦横比崩れ、スマホで小さすぎるtap target | Visual Quality / Security | High | In review | 既存公式SMAI Assetのみenabled。後続高品質Asset追加後に複数ユーザー並びを実画面確認 |
| UX-026 | SMAIアシスタント | LLM planner / Guided Workflow の安全性を確認する | fixture評価と代表画面で `次にできること` / `確認フロー` を確認する | unknown action、未確認外部取得、broker/order文言、buy/sell/hold指示、unsupported ready action はUI採用されず、必要時はdeterministic fallbackが表示される | LLM plannerが危険または未接続の操作を自然な提案として見せてしまう | Product Safety | High | In review | Phase 30-Fで fixture-based Agent Evaluation Harness を追加。通常確認はnetwork-free。実画面ではfallback workflowとconfirmation cardが壊れていないことを継続確認する |

## 上向き兆候 UX確認

- Rankingに「上向き兆候」が表示され、旧「反転期待」がユーザー向け画面に残っていない。
- 上昇気配との違い、形状ラベル、score、上向き余地、下落安全性が読み取れる。
- 落ちるナイフ・配当罠は見落とされず、過度に恐怖を煽らない。
- 買い推奨に見えず、予測信頼度が低い場合に過信させない。
- 上向き兆候mapが調整・安定度と上向き余地の関係として読める。

## 本気分析モード UX確認

- Ranking作成付近にあり、初期値OFFで、通常より時間がかかると分かる。
- AI材料分析が買い推奨ではないと分かる。
- 分析中、完了、部分失敗が分かり、失敗時も通常Rankingが残る。

## 既存予測モデル評価 UX確認

- 通常Rankingを阻害せず、評価の要点が専門用語だけに偏らない。
- model disagreementとconfidenceを過度な不安や確定未来として表現しない。
