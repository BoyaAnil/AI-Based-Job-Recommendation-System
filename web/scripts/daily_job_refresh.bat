@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "WEB_DIR=%SCRIPT_DIR%.."

cd /d "%WEB_DIR%"
rem Primary refresh (auto source). Keep location hint, but do not enforce strict match.
".\.venv\Scripts\python.exe" manage.py fetch_jobs --source auto --query "software developer" --location "India" --limit 100 --clear

rem If source APIs fail (or return too little), fall back to Remotive for a fresh global set.
if errorlevel 1 (
  ".\.venv\Scripts\python.exe" manage.py fetch_jobs --source remotive --limit 100 --clear
)

endlocal
