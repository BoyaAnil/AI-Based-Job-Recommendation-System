@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "WEB_DIR=%SCRIPT_DIR%.."
set "LOG_FILE=%WEB_DIR%\logs\daily_job_refresh.log"

cd /d "%WEB_DIR%"

echo [%date% %time%] Starting daily job refresh... >> "%LOG_FILE%"

rem Run the Django management command to refresh jobs for India
".\.venv\Scripts\python.exe" manage.py refresh_daily_jobs --force --location "India" --limit 100 >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
  echo [%date% %time%] Daily job refresh failed! >> "%LOG_FILE%"
  exit /b 1
) else (
  echo [%date% %time%] Daily job refresh completed successfully! >> "%LOG_FILE%"
  exit /b 0
)

endlocal
