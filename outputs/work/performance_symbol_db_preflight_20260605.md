# Symbol DB Preflight Performance Check - 2026-06-05

## Scope

- Target UI: Streamlit `ui/app.py`
- Operations:
  - Cockpit initial render
  - Cockpit `データを取得`
  - Ranking `最新データを取得して更新`
- Provider: `mock`
- Reason: keep the normal verification path deterministic and network-free.
- Browser note: in-app Browser was unavailable in this session. Streamlit AppTest was used for widget-level screen operation, and the running Streamlit server was checked through HTTP. Edge/Chrome headless screenshot attempts produced blank or no screenshot, so screenshots are not retained.

## Results

| Scenario | Runs | Avg sec | Min sec | Max sec | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| HTTP GET `/` | 5 | 0.005 | 0.003 | 0.012 | Running Streamlit server responded 200 |
| Cockpit initial render | 3 | 1.577 | 0.918 | 2.856 | First run includes colder app setup |
| Cockpit `データを取得` | 3 | 6.174 | 5.785 | 6.543 | Status OK |
| Ranking selected 30 / all | 3 | 2.067 | 1.941 | 2.263 | 1 result row, 29 unsupported mock rows |
| Ranking selected 50 / all | 3 | 1.969 | 1.777 | 2.159 | 1 result row, 49 unsupported mock rows |
| Ranking selected 300 / all | 3 | 2.108 | 1.861 | 2.417 | 1 result row, 299 unsupported mock rows |
| Ranking fast 100 | 3 | 1.548 | 1.478 | 1.637 | Default prefilter selected 100 unsupported mock rows |
| Ranking balanced 300 | 3 | 1.496 | 1.414 | 1.563 | Default prefilter selected 300 unsupported mock rows |

## Interpretation

- Ranking selected-count scaling stayed roughly flat between 30, 50, and 300 selected candidates.
- The new bounded Symbol DB preflight did not add a visible performance cliff in the tested local UI path.
- The 30 / 50 / 300 selected-candidate test is the most relevant check for the new preflight threshold because it keeps the selected set explicit and uses `作成対象=全件取得`.
- Cockpit fetch remains heavier than ranking in this deterministic path, around 6 seconds, but completed successfully.

## Artifacts

- Raw run data: `outputs/work/performance_symbol_db_preflight_20260605.json`
- Selected-count scaling data: `outputs/work/performance_symbol_db_preflight_20260605_selected_scale.json`
