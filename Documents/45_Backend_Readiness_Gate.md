# Backend Readiness Gate

## 1. 目的

Forecast、LLM材料、MarketData、既存FastAPIを固めた後、Frontend usability test / 改善sprintへ
移行できるかを、コード未実装と将来データの成熟待ちを混同せずに判定する。

`tools/audit_backend_readiness.py`は外部通信やruntime計算値の変更を行わず、次を確認する。

- FastAPIの必須6 route
- 設定済みMarketData Providerの初期化・health contract
- request read timeoutと公開operation全体deadline
- sealed Forecast SQLite、foreign key、全payload hash、manifest、prediction / outcome関係
- horizon別の成熟case gate
- point-in-time材料archiveのhash
- LLM材料risk signal storeのhashと蓄積状態

## 2. 判定

| 状態 | 意味 | Frontend sprint |
| --- | --- | --- |
| `ready` | 全contractと運用証拠が揃っている | 移行可能 |
| `ready_with_pending_evidence` | コードblockerはなく、将来targetまたは新規材料の蓄積待ちだけがある | 移行可能 |
| `not_ready` | API欠落、Provider初期化失敗、DB/hash破損などのblockerがある | 移行不可 |

`pending`を解消するために、未成熟targetを人工的に作る、今日取得した過去記事を過去originへ投入する、
必要case数を下げる、採用gateを緩めることは禁止する。

## 3. 実行

```powershell
.\venv_SMAI\Scripts\python.exe .\tools\audit_backend_readiness.py `
  --sealed-audit-database data\cache\forecast_sealed_audit.sqlite `
  --sealed-audit-manifest-id fsa_20260720_new_calendar_v1 `
  --material-archive data\cache\point_in_time_material_archive_v1.json `
  --material-risk-signals data\cache\llm_material_risk_signals_v1.json `
  --output reports\backend_readiness
```

JSONとMarkdownをatomicに出力する。`not_ready`だけexit code 2、それ以外は0とする。

## 4. 2026-07-20実監査

- 状態: `ready_with_pending_evidence`
- Frontend usability sprintへ移行可能: `true`
- blocker: 0
- pass:
  - 必須API route 6件
  - Yahoo Provider `available`
  - connect 1秒 / read 5秒 / operation 45秒
  - sealed Forecast manifest 1、prediction 360、DB / foreign key / hash正常
  - point-in-time材料113件、hash正常
- pending:
  - Forecast outcome 0 / pending 360。20〜120日の将来targetと100件/horizon gate待ち
  - LLM材料risk signal 0。active origin 2026-07-17より材料保存開始2026-07-20が後のため因果的に未生成

pending 2件は時間経過と新規取得でのみ解消する。runtime Forecast、Cockpit、Ranking、Scoreへの
未検証モデル接続は行わない。

## 5. Gate外

次はbackend blockerではない。

- Frontendのレイアウト、文言、操作性、responsive確認
- broker execution。安全待ちを維持する
- Polygon等の任意追加Provider
- PDF / Excelなど追加export形式
- LLM / Forecast候補のruntime採用。成熟監査gate通過後の別判断とする

このreadinessは通常のpytest、Ruff、Black、Mypyを代替しない。Frontend sprint移行前には、同じrevisionで
project-wide regressionが通過していることも必須とする。
