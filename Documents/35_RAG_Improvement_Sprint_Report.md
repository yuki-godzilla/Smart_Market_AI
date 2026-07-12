# RAG改善スプリント報告

実施日: 2026-07-12

## 結論

Research RAGを、既存の決定論的なキーワード検索を土台にしたローカル・ハイブリッド検索へ更新した。AI調査の根拠探索だけを対象とし、Investment Score、Research Scoreの既定重み、Forecast、Ranking順位、保存済みユーザーデータは変更していない。

検索性能では、file-backed vector indexの160チャンク再構築を、160回の全JSONL書込みから1回の原子的書込みへ変更した。同一端末での比較は237.83 msから2.37 ms（約100.2倍）だった。これは小規模なローカル資料でも、外部取得後の再索引をUI待ち時間にしないための改善である。

## SMAI内でのRAG利用箇所

| 導線 | RAGの役割 | 今回の影響 |
| --- | --- | --- |
| 銘柄コックピット `AI調査を開始・更新` | IR・開示・ニュース・保存済み資料を根拠付き企業リサーチへ整理 | 標準でhybrid検索、検索方式を通常画面にも表示 |
| ランキング詳細 `AIで資料を確認` | 選択銘柄を深掘りし、根拠・Research Scoreを参考表示 | 同じhybrid経路。順位・総合スコアは不変 |
| SMAIアシスタント `update_research` | ユーザー確認後に外部資料を収集し、RAG材料として整理 | 取得済み資料の検索品質が改善。外部実行権限は不変 |
| Decision Report | Research Evidence、Grounded Answer、取得トレースを保存用メモへ接続 | `retrieval_quality`の透明性情報が拡張。売買推奨は行わない |
| LLM材料分析 | RAG/IR/ニュースを定性材料の入力として参照 | 入力根拠の品質のみ改善。材料バッジ、Ranking、Forecastへは未統合 |

## 実装内容

1. `HybridResearchRetrievalService`がキーワード候補とベクトル候補を統合するようにした。従来の「ベクトル候補が1件でもあればキーワード候補を捨てる」挙動を廃止し、公式資料の完全一致を失わない。
2. 同一資料の隣接チャンクは最大2件までにして、長い資料が検索上位を独占しないようにした。
3. StreamlitのResearch stateで、資料の自動読込・アップロード・外部資料のセッション登録ごとにローカルvector indexを同期するようにした。前セッションのtransient資料は完全再構築時に除外し、資料がゼロ件になった銘柄を再構築した場合も、その銘柄の古いvectorだけを削除する。
4. JSONL vector cacheは一括`upsert_many`で1回だけ原子的に更新する。破損キャッシュはin-memory storeへ安全に退避し、キーワード検索を止めない。
5. 観点別分析では、関連度0.10未満の候補を主張の根拠に採用しない。弱い偶然一致は`confirmation_gap`として追加確認へ回す。
6. `ResearchRetrievalQuality`へキーワード候補数、ベクトル候補数、資料数、ローカル処理時間を追加し、Cockpit/Rankingの詳細表と通常画面の検索方式captionへ出す。

## 定量評価

### 再索引ベンチマーク

Windowsローカル、32次元の決定論的local-hash embedding、160チャンクで比較した。

| 指標 | 旧: チャンクごとの`upsert` | 新: 一括`upsert_many` |
| --- | ---: | ---: |
| JSONL書込み回数 | 160 | 1 |
| 再索引時間 | 237.83 ms | 2.37 ms |
| 相対速度 | 1.0x | 100.2x |

### シナリオ評価

すべてnetwork-freeの資料fixtureを用い、2026-07-12時点で評価した。検索・分析はそれぞれ約0.77〜1.30 msで、既定の`analyze_company` 3秒予算を大きく下回った。資料がない場合を正常系として扱い、低スコアや投資魅力度へ変換していない。

| シナリオ | 資料 | 検索方式 | 支持された観点 | 結果 |
| --- | ---: | --- | --- | --- |
| 国内株: 7203.T | 1 | hybrid | 成長、還元、財務安全性、事業リスク | 各観点の明示記述を根拠化 |
| 米国株: AAPL | 1 | hybrid | 還元、財務安全性、事業リスク | 成長根拠は薄く、確認不足として保持 |
| ETF: SPY | 1 | hybrid | 分配/還元、事業リスク | 「market」の偶然一致だけによる成長・財務安全性の主張を抑制 |
| 資料不足: MISSING | 0 | hybrid→keyword fallback | なし | 5件の`confirmation_gap`。空結果を良し悪しへ変換しない |

## 実画面評価

この実行環境では、Cockpitの実DOMでデフォルトプロフィール選択後のデータ取得元セレクタを確認した。通常画面には検索方式・根拠数・資料数、詳細には候補数・処理時間を表示する。プロフィール選択時のStreamlit rerun競合を避けるため、RAG UI smokeは選択済みプロフィールカードを待ってからCockpitへ進むようにした。

隔離Streamlitを使うopt-in UI smokeは、実行環境のプロセス管理がテスト開始時に隔離サーバーを終了させたため、今回の再検証では完走できなかった。通常の開発端末で `SMAI_RUN_RAG_UI_SMOKE=1` を指定して再実行する。実機Safari / PWA、継続ログイン済みブラウザ、外部LLMも未検証である。

## 回帰確認

- `pytest tests/test_research_service.py tests/test_research_external_fetch.py tests/test_research_external_registration.py tests/test_ui_forecast_display.py tests/test_ui_content_texts.py tests/ui/test_rag_hybrid_streamlit_smoke.py -q`: **524 passed, 1 skipped**
- `SMAI_RUN_RAG_UI_SMOKE=1 pytest tests/ui/test_rag_hybrid_streamlit_smoke.py -vv -s`: 隔離Streamlitが実行環境により終了するため、今回の再検証は未完走（通常端末で要実行）
- Ruff（Research、関連UI、関連tests）: passed
- mypy（`backend/research`、`ui/research_state.py`）: passed
- Black helper: Research関連の変更ファイルはpassed。巨大な既存`ui/app.py`には今回と無関係の既存整形差分があるため、全ファイルBlackは未達のまま。

## 残リスクと次スプリント

- local-hash embeddingは外部モデル不要で高速だが、意味理解は限定的である。今回の関連度floorとkeyword統合で誤主張を抑えたが、採用前にはラベル付きIR/ニュース集合でprecision・recallを計測する。
- 外部ソースのライブ取得はprovider・ネットワーク状態に依存する。失敗時は既存資料へfallbackするが、取得済み資料の鮮度を投資評価へ自動反映しない。
- PDFの本文・表・ページ位置の抽出、保存済み資料の明示archive、RAG品質の継続メトリクスは未実装である。
- Research Scoreの既定weightは0.0のままであり、Ranking順位・Forecast・Investment Scoreを変える利用は別の時系列評価と明示承認が必要である。
