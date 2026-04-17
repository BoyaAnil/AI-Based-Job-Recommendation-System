@echo off
echo Starting Daily India Job Refresh at %DATE% %TIME%
cd "C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web"

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Run the job refresh command for remote foreign jobs plus India-wide jobs.
python manage.py refresh_daily_jobs --force --location "Remote ^| India" --limit 50 --query "software developer"

REM Log completion
echo Daily India Job Refresh completed at %DATE% %TIME%

REM Pause for 5 seconds to see results
timeout /t 5 /nobreak > nul
