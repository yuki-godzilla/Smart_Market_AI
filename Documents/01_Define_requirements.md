# 📄 Define Requirements - Smart Market AI (Refined Version)

#### [BACK TO README](../README.md)

## 次期重点要件: Multi-Model Investment Intelligence

Phase 9 までの MVP では、Portfolio-to-Risk workflow、local reporting、外部 MarketData provider の opt-in 準備までを整備しました。
次期ロードマップでは、注文執行よりも、外部データ取得、銘柄スコアリング、複数予測モデル、可視化、投資判断補助を優先します。

### 目的

ユーザーが複数銘柄を比較し、予測モデルの結果、スコア内訳、リスク要因、データ品質を確認しながら、投資判断の材料を整理できるようにします。
本機能は売買推奨ではなく、判断材料を構造化して提示する支援機能です。

### 主要要件

- 外部 provider から取得した市場データを、明示 opt-in の場合だけ利用できること。
- `mock` / `csv` provider による deterministic なローカル検証経路を維持すること。
- 銘柄ごとの特徴量 snapshot を作成し、screening、forecast、report から再利用できること。
- 複数の forecast model を同じインターフェースで実行・比較できること。
- 銘柄スコアは、screening score、forecast score、risk penalty、data quality を分解して説明できること。
- UI とレポートでは、最終スコアだけでなく、モデル間の一致・不一致、不確実性、注意点を表示すること。
- 最新研究を参考にする高度なモデルは、既定経路ではなく optional adapter として追加できること。
- IR資料、有価証券報告書、決算資料、中期経営計画、ニュース等を検索し、長期企業分析の根拠を提示できること。
- RAG由来の情報は、Research Score と evidence として扱い、Investment Score への統合は optional から開始すること。

### 非優先要件

- broker への live order 送信は今回の重点から外す。
- 外部 provider を既定動作にしない。
- 重い ML ライブラリを通常の MVP 確認や CI の必須依存にしない。
- 単一モデルの予測を投資助言として扱わない。
- RAG回答を、根拠のない断定・売買推奨・自動売買判断として扱わない。

## 1. Background & Purpose
個人投資家がNISA制度や通常の株式投資において、効率的かつ戦略的に投資判断を行えるよう支援するAIツールを開発する。
株価データ、企業財務データ、経済指標、ニュース等を統合的に分析し、**高配当株（国内外）**や安定成長型投資信託の選定、売買タイミング予測、リスク評価を行い、ユーザーに分かりやすいレポートとして提供する。

---

## 2. Scope
- **対象市場**
  - *投資枠*: 高配当の個別株（国内外）
  - *積立枠*: 安定成長する投資信託
- **対象ユーザー**: 初心者〜中級者の個人投資家
- **対象機能**: 銘柄予測、ランキング、ポートフォリオ最適化、市場予測、リスク分析、レポート出力
- **対象外**: 信用取引、仮想通貨、先物・オプション

---

## 3. Functional Requirements (What the System Will Do)
| 機能 | 概要 |
|------|------|
| 銘柄予測 | 株価や配当の将来予測（回帰／分類） |
| 銘柄ランキング | 配当利回り・成長率・リスクスコアによる順位付け |
| 市場予測 | 日経平均・TOPIXなどの指数トレンド分析 |
| ポートフォリオ最適化 | 分散投資と期待リターン最大化を考慮した最適構成 |
| リスク分析 | 経済指標・ニュース分析による下落リスク評価 |
| Research RAG | IR資料・有報・決算資料・中計・ニュースから長期企業分析の根拠を検索・要約・指数化 |
| レポート出力 | PDF・Excel出力およびStreamlitでのダッシュボード表示 |

---

## 4. Non-Functional Requirements (How the System Should Behave)
| 要件 | 内容 |
|------|------|
| ユーザビリティ | 初心者でも直感的に操作可能なUI（Streamlitベース） |
| パフォーマンス | ローカル実行で5秒以内に主要分析を完了 |
| 拡張性 | 新しい指標・モデルを容易に追加可能 |
| 保守性 | UI・ロジック分離のモジュール構造 |
| セキュリティ | 金融情報は外部送信せずローカル完結、HTTPS通信対応 |

---

## 5. Technologies
| 項目 | 技術・ライブラリ |
|------|----------------|
| 言語 | Python 3.x |
| Webフレームワーク | Streamlit または Flask |
| 機械学習 | scikit-learn, XGBoost, PyTorch, Prophet |
| 可視化 | matplotlib, plotly, seaborn |
| データ取得 | yfinance, pandas_datareader, requests |
| ポートフォリオ分析 | PyPortfolioOpt, cvxpy |
| レポート出力 | pandas, openpyxl, fpdf |

---

## 6. Input & Output Requirements
**Input**
- 銘柄コード（国内外ティッカー対応）
- 投資種別（個別株/投信）
- 投資金額・リスク許容度

**Output**
- 売買判断（信頼度付き）
- 銘柄スコアリングとランキング
- 最適ポートフォリオ構成
- 市場動向予測（PDF・Excelレポート）
- Streamlitダッシュボード

---

## 7. Constraints & Prerequisites
- 無料または低コストのAPI利用
- PC操作の基本スキルを有するユーザーを想定
- 金融アドバイスではなく情報提供が目的（免責文表示必須）

---

## 8. Future Considerations
- 予測スパン（1日・1週間・1ヶ月）の柔軟設定
- ファンダメンタルデータ取得の自動化
- 投信商品のリスク・パフォーマンス可視化
