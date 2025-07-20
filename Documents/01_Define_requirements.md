# 📄 Define Requirements - Smart Market AI

## 1. Back Ground & Purpose

個人投資家がNISA制度を活用する際に、投資判断を支援するためのAIツールを開発する。
銘柄の選定や売買のタイミング、リスク分析などをAIが支援し、ユーザーにレポートとして提供することを目的とする。

---

## 2. Scope

- 対象市場：
  - 投資枠：日本の高配当個別株
  - 積立枠：安定成長する投資信託商品
- 対象ユーザー：個人投資家（初心者〜中級者）
- 対象機能（後述）
- 対象外：信用取引、仮想通貨、先物・オプションなど

---

## 3. Functional Requirement（What the system will do）

### 🔹 Core function List

| 機能 | 概要 |
|------|------|
| 銘柄予測 | 株価の将来予測（数値／2値分類）を行う |
| 銘柄ランキング | 配当利回り・成長率等を基にスコア化し優良銘柄を表示 |
| 市場予測 | 日経平均やTOPIXなどの動向を分析・予測 |
| ポートフォリオ最適化 | 複数銘柄の組み合わせと分散効果を分析し、最適化 |
| リスク分析 | ニュースや指標から投資リスクを評価する |
| レポート出力 | PDF/Excel形式での出力、Streamlit UIでの表示 |

---

## 4. Non-Functional Elements（How the system should behave）

| 要件 | 内容 |
|------|------|
| ユーザビリティ | 初心者でも使いやすいUI（Streamlitベース） |
| パフォーマンス | 小規模なローカル実行を前提とした設計（高速な予測） |
| 拡張性 | 銘柄追加・指標追加・アルゴリズム変更に対応しやすい構成 |
| 保守性 | モジュール分割・ロジックとUIの分離 |
| セキュリティ | 金融情報の外部送信を行わず、ローカル完結が基本 |

---

## 5. Techs

| 項目 | 内容 |
|------|------|
| 言語 | Python 3.x |
| Webフレームワーク | Streamlit（またはFlask） |
| 機械学習 | scikit-learn, XGBoost, PyTorch, Prophet など |
| 可視化 | matplotlib, plotly, seaborn |
| データ取得 | yfinance, pandas_datareader, requests |
| ポートフォリオ分析 | PyPortfolioOpt, cvxpy |
| レポート出力 | pandas, openpyxl, fpdf |

---

## 6. Input-Output Requirement

### 🔽 Input

- 銘柄コード（ティッカー）
- 投資対象タイプ（個別株 or 投資信託）
- 投資金額・希望リスク度合い（ポートフォリオ用）

### 🔼 Output

- 売買判断（上がる／下がる、信頼度付き）
- 銘柄ランキング（スコア付き）
- 最適ポートフォリオ提案（分散と期待リターン）
- 市場予測レポート（PDF, Excel）
- Streamlit上でのダッシュボード可視化

---

## 7. Constraints & Prerequisites

- ローカル環境で動作（外部APIは無料の範囲）
- ユーザーは基本的なPC操作ができること
- 金融アドバイスを目的としない（注意書き必要）

---

## 8. Future Considerations

- 予測スパン（1日／1週間／1ヶ月）
- ファンダメンタルデータの取得方法
- 投資信託データの可視化