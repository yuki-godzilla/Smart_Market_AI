@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM Smart Market AI - Symbol Universe Import All (v5 core-safe)
REM ------------------------------------------------------------
REM Place this file in the Smart_Market_AI repository root.
REM Usage:
REM   run_symbol_universe_import_all.bat
REM   run_symbol_universe_import_all.bat 2026-06-23
REM
REM Optional maintenance flags, disabled by default because these
REM enrichment sources still need schema/source normalization:
REM   set RUN_LEGACY_NISA_SEED=1
REM   set RUN_NISA_LISTED_FUND=1
REM   set RUN_NISA_JPX_ETF=1
REM   set RUN_QUALITY_REVIEW=1
REM   set RUN_RANKING_METADATA=1
REM ============================================================

cd /d "%~dp0"

if not exist "tools\import_symbol_universe_source.py" (
  echo [ERROR] Please place this .bat in the Smart_Market_AI repository root.
  echo         Current directory: %CD%
  exit /b 1
)

set "AS_OF=%~1"
if "%AS_OF%"=="" (
  for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "AS_OF=%%i"
)
set "AS_OF_COMPACT=%AS_OF:-=%"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_ID=%%i"

set "PYTHON_EXE=python"
if exist "venv_SMAI\Scripts\python.exe" set "PYTHON_EXE=venv_SMAI\Scripts\python.exe"

set "BASE_CSV=data\marketdata\symbol_universe.csv"
set "SOURCE_DIR=data\marketdata\symbol_universe_sources"
set "RAW_DIR=data\marketdata\raw"
set "REPORT_DIR=reports"
set "LOG_DIR=logs"
set "BACKUP_DIR=data\marketdata\backup"
set "LOG_FILE=%LOG_DIR%\symbol_universe_import_all_%RUN_ID%.log"
set "BACKUP_CSV=%BACKUP_DIR%\symbol_universe_before_import_all_%RUN_ID%.csv"
set "SBI_FOREIGN_CSV=%SOURCE_DIR%\sbi_foreign_stock_official_%AS_OF_COMPACT%.csv"
set "SBI_OVERSEAS_ETF_CSV=%SOURCE_DIR%\sbi_overseas_etf_official_%AS_OF_COMPACT%.csv"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%REPORT_DIR%" mkdir "%REPORT_DIR%"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
if not exist "%RAW_DIR%" mkdir "%RAW_DIR%"
if not exist "%SOURCE_DIR%" mkdir "%SOURCE_DIR%"

call :log "============================================================"
call :log "SMAI Symbol Universe Import All v5"
call :log "AS_OF=%AS_OF%"
call :log "RUN_ID=%RUN_ID%"
call :log "PYTHON_EXE=%PYTHON_EXE%"
call :log "============================================================"

if not exist "%BASE_CSV%" (
  call :log "[ERROR] Base CSV not found: %BASE_CSV%"
  exit /b 1
)

copy /Y "%BASE_CSV%" "%BACKUP_CSV%" >nul
if errorlevel 1 (
  call :log "[ERROR] Failed to create backup: %BACKUP_CSV%"
  exit /b 1
)
call :log "[OK] Backup created: %BACKUP_CSV%"

call :run_cmd "Compile import tools" "%PYTHON_EXE% -m py_compile tools\import_symbol_universe_source.py tools\fetch_sbi_foreign_symbol_universe_sources.py tools\fetch_sbi_overseas_etf_symbol_universe_source.py tools\backfill_symbol_universe_screening_metadata.py"
if errorlevel 1 goto :fail

call :run_cmd "Fetch SBI foreign stock official list" "%PYTHON_EXE% tools\fetch_sbi_foreign_symbol_universe_sources.py --write --as-of %AS_OF% --output-csv %SBI_FOREIGN_CSV% --raw-dir %RAW_DIR%\sbi_foreign --report %REPORT_DIR%\sbi_foreign_stock_import_report_%RUN_ID%.json"
if errorlevel 1 goto :fail

call :run_cmd "Fetch SBI overseas ETF official list" "%PYTHON_EXE% tools\fetch_sbi_overseas_etf_symbol_universe_source.py --write --as-of %AS_OF% --base-csv %BASE_CSV% --output-csv %SBI_OVERSEAS_ETF_CSV% --raw-dir %RAW_DIR%\sbi_overseas_etf --report %REPORT_DIR%\sbi_overseas_etf_import_report_%RUN_ID%.json"
if errorlevel 1 goto :fail

call :import_append_profile "JPX listed stock" "%SOURCE_DIR%\jpx_listed_stock_20260520.csv" jpx_listed_stock
if errorlevel 1 goto :fail
call :import_append_profile "JPX ETF" "%SOURCE_DIR%\jpx_etf_20260522.csv" jpx_etf
if errorlevel 1 goto :fail
call :import_append_profile "JPX REIT" "%SOURCE_DIR%\jpx_reit_20260521.csv" jpx_reit
if errorlevel 1 goto :fail
call :import_append_profile "SBI US stock" "%SOURCE_DIR%\sbi_us_stock_20260526.csv" sbi_us_stock
if errorlevel 1 goto :fail
call :import_append_profile "SBI US ETF" "%SOURCE_DIR%\sbi_us_etf_20260526.csv" sbi_us_etf
if errorlevel 1 goto :fail
call :import_append_profile "Mutual fund seed" "%SOURCE_DIR%\mutual_fund_seed.csv" mutual_fund_seed
if errorlevel 1 goto :fail
call :import_append_raw "SBI foreign stock official" "%SBI_FOREIGN_CSV%" sbi_foreign_stock
if errorlevel 1 goto :fail
call :import_append_raw "SBI overseas ETF official" "%SBI_OVERSEAS_ETF_CSV%" sbi_overseas_etf
if errorlevel 1 goto :fail

REM Optional enrichment sources. Default skip keeps core universe refresh green.
if "%RUN_LEGACY_NISA_SEED%"=="1" (
  call :import_update_profile "NISA eligibility seed legacy" "%SOURCE_DIR%\nisa_eligibility_seed.csv" nisa_eligibility
  if errorlevel 1 goto :fail
) else call :log "[SKIP] NISA eligibility seed legacy - set RUN_LEGACY_NISA_SEED=1 to run"

if "%RUN_NISA_LISTED_FUND%"=="1" (
  call :import_update_profile "NISA listed fund latest" "%SOURCE_DIR%\nisa_eligibility_imaj_listed_fund_20260522.csv" nisa_eligibility
  if errorlevel 1 goto :fail
) else call :log "[SKIP] NISA listed fund latest - set RUN_NISA_LISTED_FUND=1 after fixing source/schema"

if "%RUN_NISA_JPX_ETF%"=="1" (
  call :import_update_profile "NISA JPX ETF latest" "%SOURCE_DIR%\nisa_eligibility_jpx_etf_20260522.csv" nisa_eligibility
  if errorlevel 1 goto :fail
) else call :log "[SKIP] NISA JPX ETF latest - set RUN_NISA_JPX_ETF=1 after fixing source/schema"

if "%RUN_QUALITY_REVIEW%"=="1" (
  call :import_update_profile "ETF index review" "%SOURCE_DIR%\symbol_etf_index_review_20260526.csv" quality_review
  if errorlevel 1 goto :fail
  call :import_update_profile "Numeric outlier review" "%SOURCE_DIR%\symbol_numeric_outlier_review_20260526.csv" quality_review
  if errorlevel 1 goto :fail
) else call :log "[SKIP] quality review sources - set RUN_QUALITY_REVIEW=1 after fixing source/schema"

if "%RUN_RANKING_METADATA%"=="1" (
  call :import_update_profile "Ranking metadata template" "%SOURCE_DIR%\ranking_metadata_template.csv" ranking_metadata
  if errorlevel 1 goto :fail
) else call :log "[SKIP] ranking metadata template - set RUN_RANKING_METADATA=1 after fixing source/schema"

call :run_cmd "Backfill screening metadata" "%PYTHON_EXE% tools\backfill_symbol_universe_screening_metadata.py --write --csv %BASE_CSV% --source-dir %SOURCE_DIR% --manifest %REPORT_DIR%\symbol_universe_screening_backfill_%RUN_ID%.json"
if errorlevel 1 goto :fail

call :log ""
call :log "[RUN] Final DB summary"
%PYTHON_EXE% -c "import pandas as pd; df=pd.read_csv(r'%BASE_CSV%', low_memory=False); print('shape=', df.shape); print('market='); print(df['market'].value_counts(dropna=False).head(30).to_string()); print('asset_type='); print(df['asset_type'].value_counts(dropna=False).to_string())" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :fail
call :log "[OK] Final DB summary"

call :log "[DONE] All imports completed successfully."
call :log "[LOG] %LOG_FILE%"
call :log "[BACKUP] %BACKUP_CSV%"
exit /b 0

:import_append_profile
set "LABEL=%~1"
set "CSV=%~2"
set "PROFILE=%~3"
if not exist "%CSV%" (
  call :log "[SKIP] %LABEL% - source CSV not found: %CSV%"
  exit /b 0
)
call :run_cmd "Import append-only: %LABEL%" "%PYTHON_EXE% tools\import_symbol_universe_source.py --write --base-csv %BASE_CSV% --source-csv %CSV% --source-name %PROFILE% --source-profile %PROFILE% --as-of %AS_OF% --manifest %REPORT_DIR%\import_%PROFILE%_%RUN_ID%.json"
exit /b !ERRORLEVEL!

:import_append_raw
set "LABEL=%~1"
set "CSV=%~2"
set "SOURCE_NAME=%~3"
if not exist "%CSV%" (
  call :log "[SKIP] %LABEL% - source CSV not found: %CSV%"
  exit /b 0
)
call :run_cmd "Import append-only: %LABEL%" "%PYTHON_EXE% tools\import_symbol_universe_source.py --write --base-csv %BASE_CSV% --source-csv %CSV% --source-name %SOURCE_NAME% --as-of %AS_OF% --manifest %REPORT_DIR%\import_%SOURCE_NAME%_%RUN_ID%.json"
exit /b !ERRORLEVEL!

:import_update_profile
set "LABEL=%~1"
set "CSV=%~2"
set "PROFILE=%~3"
if not exist "%CSV%" (
  call :log "[SKIP] %LABEL% - source CSV not found: %CSV%"
  exit /b 0
)
call :run_cmd "Import update-existing: %LABEL%" "%PYTHON_EXE% tools\import_symbol_universe_source.py --write --update-existing --base-csv %BASE_CSV% --source-csv %CSV% --source-name %PROFILE% --source-profile %PROFILE% --as-of %AS_OF% --manifest %REPORT_DIR%\import_%PROFILE%_%RUN_ID%.json"
exit /b !ERRORLEVEL!

:run_cmd
set "LABEL=%~1"
set "CMD=%~2"
call :log ""
call :log "[RUN] %LABEL%"
call :log "      %CMD%"
call %CMD% >> "%LOG_FILE%" 2>&1
set "RC=!ERRORLEVEL!"
if not "!RC!"=="0" (
  call :log "[ERROR] %LABEL% failed with exit code !RC!. See: %LOG_FILE%"
  exit /b !RC!
)
call :log "[OK] %LABEL%"
exit /b 0

:log
if "%~1"=="" (
  echo(
  echo(>> "%LOG_FILE%"
) else (
  echo %~1
  echo %~1>> "%LOG_FILE%"
)
exit /b 0

:fail
call :log ""
call :log "[FAILED] Import pipeline stopped."
call :log "[RESTORE HINT] copy /Y "%BACKUP_CSV%" "%BASE_CSV%""
exit /b 1
