# 97_Functional_Spec_Issues

#### [BACK TO README](../README.md)

## Purpose

Smart Market AI の「実装バグではないが、仕様意図が曖昧・重複・誤解されやすい」点を管理する台帳です。

実装修正に入る前に、ここで期待方向を整理し、必要に応じて [96_Manual_UX_Review_Checklist.md](./96_Manual_UX_Review_Checklist.md)、[03_Functional_design.md](./03_Functional_design.md)、[07_UI_Wording_Policy.md](./07_UI_Wording_Policy.md)、[05_Implementation_Roadmap.md](./05_Implementation_Roadmap.md) と同期します。

## Status Values

- `Open`: 仕様整理が必要
- `Needs decision`: ユーザーまたは設計判断が必要
- `In review`: 文言・設計レビュー中
- `Resolved`: 仕様または文言として解決済み
- `Deferred`: 将来フェーズへ延期

## Functional Spec Issue Register

| ID | Area | Symptom | Current Behavior | Expected Direction | Impact | Priority | Status | Related Docs / Code | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FS-001 | Investment Score | 高スコアが売買判断そのものに見える | Screening、Forecast、Data Quality、Risk signal を統合した数値として表示される | 「比較・分析用スコア」であり、買い/売りの指示ではないと明示する | 投資助言誤認、過信 | High | Open | `backend/scoring`, `ui/app.py`, `Documents/07_UI_Wording_Policy.md` | スコアの隣に役割説明が必要か検討 |
| FS-002 | Ranking | 上位銘柄を買うべきと誤解される | 条件に応じて候補を並べ替え、上位を表示する | Ranking は候補探索・比較・screening の入口として定義する | 投資助言誤認 | High | Open | `ui/ranking.py`, `ui/app.py`, `Documents/05_Implementation_Roadmap.md` | 「おすすめ」表現は禁止 |
| FS-003 | Data Quality / Database Fit / Metadata Confidence | Database Fit / Metadata Confidence が投資魅力度に見える | Ranking sort profile に補助的に反映される | 投資魅力度ではなく、評価に使うデータの充実度・信頼度として扱う | スコア解釈の混乱 | High | Open | `ui/ranking.py`, `Documents/06_MVP_Operations_Guide.md` | UI名と説明の見直し候補 |
| FS-004 | Rebalance Cockpit | Rebalance結果が売買指示に見える | allocation drift、proposed trades、risk breach を表示する | 配分見直しシミュレーション、review candidate として扱う | 実注文との誤認 | High | Open | `ui/rebalance_app.py`, `backend/portfolio`, `backend/risk` | broker integration は deferred |
| FS-005 | Decision Report | Report が投資推奨書に見える | Cockpit / Ranking / Rebalance の判断材料をMarkdown/JSON等で保存し、冒頭noteで判断材料メモ・非助言であることを明示する | ある時点の判断材料、根拠、不確実性、確認ポイントの保存・説明として定義する | Product safety, compliance risk | High | In review | `backend/reporting`, `ui/app.py`, `Documents/05_Implementation_Roadmap.md` | Markdown / UI 冒頭noteを補強済み。実画面で継続確認 |
| FS-006 | Research Summary / Research Evidence | Research Summary の信頼度が分かりにくい | local 登録資料と first external fetch slice から deterministic summary と evidence を表示する | 外部最新IR・開示・ニュース・provider evidence を主ソースとし、資料名、資料日、取得日時、provider、source URL、source type、根拠数、data quality warning を明示し、保証ではないと伝える。local 登録資料は tests / archive / fallback として区別する | 根拠の過信 | High | Open | `backend/research`, `ui/research_state.py`, `Documents/04_Detail_Design/04-8_Onepager_Research_RAG.md` | provider snapshot と公式IR、外部一時参照とlocal archiveを区別 |
| FS-006a | Research Summary / CompanyResearchSummary | Research Summary が生データ羅列または取得状態の説明に寄り、ユーザーが知りたい企業概要・事業・IR・指標が見えにくい | `CompanyResearchSummaryBuilder` が `CompanyResearchEvidence` 正規化層、`ResearchBrief` / `ResearchFactSummary` を入力として、provider profile、news、TDnet trace、evidence を企業概要、主な事業、製品・サービス、地域、定量情報、IR情報、最新ニュース・開示へ変換し、Cockpit / Ranking Research Summary に表示する | 主表示は `企業リサーチサマリー` / `定量情報サマリー` / `IR情報サマリー` / `最新ニュース・開示サマリー` に集約し、事業概要、主要事業、製品・サービス、確認済みIR / 公式資料、主要定量指標、直近ニュース/開示、未取得 / 未解析 / 公式未確認を source-backed fact として表示する。AI読み取りメモ、確認できた情報 / 注意して読む情報、出典カード、Research Score、件数、confidence、外部取得失敗の技術詳細は補助情報として扱う。外部LLMは任意の後続候補で、まず local rule-based 生成を維持する | ユーザーが企業像をつかめない、provider raw fields を投資根拠と誤読する、取得件数だけが成果に見える | UX readability | High | Resolved | `CompanyResearchSummary` + `CompanyResearchEvidence` slice は実装済み。2026-06-01に国内株 / 海外株 / ETF / 外部取得失敗・資料不足ケースを実画面確認し、主表示と折りたたみ境界を調整済み |
| FS-006b | Research Summary / News source URL | ニュースURL表示が未実装に見える | 外部参照ソースと詳細データにはURL表示があるが、`最新ニュース・開示サマリー` 付近から辿りにくい | `最新ニュース・開示サマリー` 直後に `ニュース・開示の出典を表示（URL付きN件）` を置き、URL付き出典がある場合は初期展開して、ニュース、TDnet、企業IR、EDINET、Yahoo Finance を簡易リンクで表示する。ニュース専用URLが無い場合も、外部参照ソース側に公式資料・provider URLがある可能性を案内する | URL表示未実装の誤解、ニュースと公式開示の混同、provider raw fields の露出 | UX readability | High | In review | UI表示限定slice実装済み。取得ロジック、外部source正規化、Research Score、Ranking順位、transient-by-default方針は変更しない |
| FS-007 | Forecast | Forecast と Investment Score の関係が曖昧 | Forecast agreement が Investment Score に反映される | Forecast は将来予測の保証ではなく、モデル間の見方や不確実性の一要素として説明する | 予測過信 | High | Open | `backend/forecast`, `backend/scoring`, `ui/app.py` | chart文言とscore内訳を確認 |
| FS-008 | Ranking criteria | NISA / Dividend / Growth / ETF criteria の使い分けが分かりにくい | ranking purpose と detail filters が複数存在する | 目的別に「候補 universe を絞る条件」と「表示順を変える条件」を分けて説明する | UX confusion | High | Open | `ui/ranking.py`, `Documents/09_SBI_Symbol_Universe_Policy.md` | 投資スタイル別の期待値整理 |
| FS-009 | Symbol Cockpit | Cockpit が何を深掘りする画面か曖昧 | 価格、特徴量、Forecast、Score、Research、Decision Report が同居する | 1銘柄の確認画面として、価格・特徴量・予測・リスク・スコア・根拠を順に確認する役割を明確化する | 情報過多 | Medium | Open | `ui/app.py`, `Documents/03_Functional_design.md` | 情報階層レビュー対象 |
| FS-010 | Screening Score | Screening Score と Investment Score の違いが曖昧 | Screening Score はFeature Snapshot由来、Investment Scoreは統合スコア | Screening は候補評価の一部、Investment Score は複数観点の統合値として説明する | Score confusion | Medium | Open | `backend/screening`, `backend/scoring` | UI内訳ラベルの整合 |
| FS-011 | Risk | Riskが「安全/危険」の絶対判定に見える | risk breach、risk score、volatility/drawdownが表示される | リスクは確認材料であり、安全保証や売買禁止/推奨ではないと説明する | Wording risk | High | Open | `backend/risk`, `ui/rebalance_app.py`, `ui/app.py` | Risk low != safe |
| FS-012 | Market Data provider | provider差とdata freshnessが見えにくい | mock/csv/yahoo の provider と取得日が画面に出る箇所がある | provider、取得期間、as-of、欠損、部分失敗を一貫して表示する | Data confidence | High | Open | `backend/marketdata`, `ui/app.py`, `Documents/06_MVP_Operations_Guide.md` | live provider opt-inを維持 |
| FS-013 | Research Score | Research Score が既存scoreを上書きするように見える | `ResearchScoreService`、Investment Score optional input、Cockpit / Ranking / Decision Report 参考表示は実装済み。`scoring.weights.research` は既定 `0.0` で、通常の総合点・順位は変えない。Cockpit UI ではResearch Scoreの読み方、要約、観点別内訳、注意点を同じ折りたたみにまとめる | Research Score は根拠資料の充実度・鮮度・信頼度を整理する参考スコアとして扱う。資料不足時は欠損/低信頼として表示し、既定では既存scoreやランキング順位を上書きしない | Score hierarchy confusion | Medium | In review | `backend/research`, `backend/scoring`, `ui/app.py`, `Documents/05_Implementation_Roadmap.md` | ランキング順位への統合はいまは見送り。UI wording slice 実装済み。残課題は次の実画面回帰で「根拠資料の確認材料」として誤読されないか確認すること |
| FS-014 | Assistant future | Assistantが売買助言を返すように見える | Future scope / planned | Assistant は説明・要約・観点提示に限定し、注文や売買指示はしない | Product safety | High | Deferred | `Documents/05_Implementation_Roadmap.md` | 実装前にpolicy必要 |
| FS-015 | Execution / Broker | Executionの位置づけが曖昧 | broker order sending は deferred | Risk、report、audit、user confirmation が揃うまで実装しない | Safety and compliance | High | Deferred | `backend/execution` future, `Documents/05_Implementation_Roadmap.md` | 明示依頼なしに触らない |
| FS-016 | Decision Report exports | Markdown/JSON/manifest/ZIPの使い分けが分かりにくい | Markdown（読む用）、JSON（再現用）、manifest（内容確認）、ZIP（保存用）としてUIラベル・help・manifest説明に反映する | Markdownは人間向け、JSON/manifest/ZIPは再現・保存向けとして説明する | UX confusion | Medium | In review | `backend/reporting`, `ui/app.py` | PDF/Excelはfuture。download文言と回帰テストを追加済み |
| FS-017 | NISA criteria | NISA対象が投資適合性に見える | NISA metadataで候補を絞れる | NISAは制度上の候補条件であり、投資魅力度や安全性ではないと説明する | Wording risk | Medium | Open | `Documents/09_SBI_Symbol_Universe_Policy.md`, `ui/ranking.py` | NISA eligible != recommended |
| FS-018 | ETF criteria | ETF低コスト/インカム条件が万能評価に見える | expense ratio、index family、dividendなどで比較する | ETF目的別の比較条件であり、商品適合性は別途確認が必要とする | Spec ambiguity | Medium | Open | `ui/ranking.py`, symbol metadata schema | 複雑ETF除外方針と整合 |
| FS-019 | Dividend criteria | 高配当が良い銘柄に見える | dividend yield/categoryでranking/filter可能 | 配当利回りは確認材料であり、減配リスクや一時要因も見る必要がある | Product safety | Medium | Open | `ui/ranking.py`, `Documents/07_UI_Wording_Policy.md` | 高配当=推奨を避ける |
| FS-020 | Growth criteria | Growth rankingが成長保証に見える | growth/quality profileで並べ替える | 成長候補の探索条件であり、将来成長の保証ではないと説明する | Wording risk | Medium | Open | `ui/ranking.py`, `backend/scoring` | Forecastとの関係も確認 |
