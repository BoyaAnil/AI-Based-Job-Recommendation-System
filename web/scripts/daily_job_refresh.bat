@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "WEB_DIR=%SCRIPT_DIR%.."

cd /d "%WEB_DIR%"
".\.venv\Scripts\python.exe" manage.py fetch_jobs --source auto --query "software developer" --location "India" --limit 100 --require-location-match --clear

endlocal
