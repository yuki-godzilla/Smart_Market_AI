# 📄 Define Requirements - Smart Market AI (Refined Version)

#### [BACK TO README](../README.md)

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
