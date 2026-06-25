# Manual / Reviewed Metadata Patches

Small markets or provider-specific gaps can be filled with a reviewed CSV patch instead of hard-coding values.

Recommended workflow:

1. Identify low-coverage symbols with `tools/check_symbol_universe_metadata_coverage.py`.
2. Research a small set manually from trusted sources.
3. Put rows into `manual_metadata_patch_template.csv` format.
4. Dry-run the patch.
5. Apply with `--write` after checking the manifest.

```powershell
python tools\apply_symbol_universe_metadata_patch.py --patch data\marketdata\manual_metadata_patches\my_patch.csv
python tools\apply_symbol_universe_metadata_patch.py --patch data\marketdata\manual_metadata_patches\my_patch.csv --write
```

Use `source` values like `official_exchange`, `annual_report`, `verified_csv`, or `manual_review`. Avoid vague sources.
