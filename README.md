# 📊 Smart Market AI - 要件定義書

## Links
#### 1. [Define Requirements](./Documents/01_Define_requirements.md)
#### 2. [System Design](./Documents/02_System_design.md)
#### 3. [Functional Design](./Documents/03_Functional_design.md)
#### 4. [Detail Design](./Documents/04_Detail_Design/04.Detail_Design_README.md)
#### 5. [Implementation Checklist & Stubs](./Documents/05_Implementation_Checklist_and_Stubs.md)

---

## 1. プロジェクト概要

「Smart Market AI」は、NISAを活用した個人投資家向けの**市場予測・銘柄分析支援AIアプリ**である。  
売買タイミング予測やポートフォリオ最適化などを通じて、投資判断をスマートにサポートする。

---

## 2. 目的

- 銘柄の売買タイミングを予測する
- 優良銘柄をランキング表示する
- 市場全体（日経平均など）の方向性を予測する
- ポートフォリオ（分散投資戦略）を最適化する
- 上記をレポート形式で出力する

---

## 3. 対象市場・資産

- **投資枠（NISA）**：配当利率の高い日本の個別株
- **積立枠（つみたてNISA）**：安定成長する信託商品（インデックスファンドなど）

---

## 4. AIの役割

- 株価の将来予測（数値予測）
- 株価上昇 / 下落の2値分類
- ニュースデータによるリスク分析
- 強化学習または最適化理論によるポートフォリオ自動最適化

---

## 5. 予測スパン（※検討中）

- 短期（1日〜1週間）
- 中期（1ヶ月〜四半期）
- 長期（1年程度）

---

## 6. データソース（※検討中）

候補：
- Yahoo Finance / yfinance（株価、配当）
- 投資信託協会 / モーニングスター（信託商品）
- NewsAPI / GNews（ニュース）
- ファンダメンタル：EDINET、決算短信など

---

## 7. 技術構成

| 項目 | 技術 |
|------|------|
| 言語 | Python |
| UI | Streamlit（Webアプリ） |
| モデル | scikit-learn, XGBoost, PyTorch, Prophet 他 |
| 可視化 | matplotlib, plotly, seaborn |
| ポートフォリオ分析 | PyPortfolioOpt, cvxpy |
| レポート出力 | openpyxl, fpdf, pandas |
| データ取得 | yfinance, requests, BeautifulSoup |
| ニュース処理 | transformers, textblob, VADER |

---

## 8. 出力形式

- Streamlit上でのWeb可視化
- PDF / Excel形式での週次・月次レポート出力

---

## 9. 開発ステップ（案）

1. 2値分類モデルで「株価上昇／下落」を予測する PoC を構築
2. 信託商品のスコア化／ランキングロジックを作成
3. ポートフォリオ自動最適化ロジックを実装
4. Streamlitによる可視化ダッシュボードを作成
5. レポート生成機能を追加

---

## 10. その他

- 開発名・コード名：**Smart Market AI（SMAI）**
- 想定利用者：NISA/つみたてNISAを活用する個人投資家
