# Reports

Generated maintenance reports are grouped by the Desktop PC local execution date and time.

```text
reports/
  YYYY-MM-DD_HHMM/
    *.json
    *.md
```

`run_symbol_universe_import_all.bat` writes directly to the current execution folder.
The folder timestamp is the actual local run time, not the optional data `as-of` argument.
Seconds remain in each report filename.

Keep this README at the report root. Generated report artifacts should not be added directly
beside it.
