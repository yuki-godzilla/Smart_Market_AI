# 47. Package Public API Compatibility

最終更新: 2026-08-02

## 目的

本書はR5のpackage境界を管理する。`backend.assistant`、`backend.news`、`backend.research`のpackage rootから提供する名前を、安定contract、互換façade、内部実装へ分ける。公開名の削除や移動は、ここに記した移行条件と境界testがそろった別sliceだけで行う。

package importはProvider通信、LLM起動、background worker開始、filesystem mutationを行ってはならない。通常testはnetwork-freeであり、live smokeは明示opt-inの別経路とする。

## 公開境界

| Package | 安定contract / 軽量export | 互換façade | 現在の方針 | 削除・変更条件 |
|---|---|---|---|---|
| `backend.research` | `contracts`、external contract、source trace、summary builder、`ResearchInMemoryStore`、vector store、ingestion/index | legacy aggregate `service` exportを`__getattr__`で遅延解決 | package importでaggregate serviceを読まない。既存の`from backend.research import ResearchAnalysisService`は維持する | 直接importの呼出元移行、public import smoke、service回帰、移行告知を満たした別commitのみ |
| `backend.assistant` | gateway contract、action result、workflow session、model catalog、純粋policy | package rootの既存service / gateway / tool再export | 現在は広い互換入口を維持する。root importの副作用は接続・起動・書込みを伴わないことを確認対象とする | 利用側をsubmodule importまたは専用façadeへ移し、Assistant scenario / gateway contract回帰を固定してから |
| `backend.news` | news / Radar contract、cache path policy、source adapter contract、Radar deterministic builder | package rootのcache / dashboard / refresh / background再export | 現在は広い互換入口を維持する。background workerは明示関数呼出でのみ開始する | view / schedulerの利用側を専用入口へ移し、cache / user state / live smokeの境界testを固定してから |

## import safety contract

- package importはnetwork request、Gateway health probe、LLM warmup、background refresh、cache writeを開始しない。
- eager import cycleと`backend -> ui` dependencyはarchitecture baselineで0件を維持する。
- package rootのpublic名は`__all__`とimport smokeで追跡する。`__all__`にない内部helperを新規利用しない。
- compatibility façadeは計算結果を変換せず、既存contractを委譲するだけにする。

## 2026-08-02 の移行優先順位

1. Researchは軽量なstore、vector retrieval、ingestion/indexを直接公開し、aggregate serviceのみ遅延読込とする。
2. Assistantはgateway contract / model policy / workflow contractを安定入口として維持し、viewからの直接service依存を増やさない。
3. Newsは表示policyと取得・cache・background workerの境界を維持し、viewからbackground workerを直接開始しない。
4. 各packageのrootを全面的にlazy化するかは、import graph、scenario test、実行時profileを測定してから決める。

## 検証

- `tests/test_research_package_api.py`は、Research package import、store / vector / ingestion public export、legacy service exportの遅延読込を別processで確認する。
- `tools/audit_python_architecture.py --baseline config/architecture_baseline.json`はbackend-to-UI edgeとeager cycleを検証する。
- Assistant / NewsのProvider、LLM、background workerを伴う確認は、通常CIではなく明示opt-inのlive smokeとして実行する。
