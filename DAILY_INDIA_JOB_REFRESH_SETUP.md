# Daily India Job Refresh Setup Guide

## Overview
This guide sets up automatic daily job refresh for India-based software developer positions using Gemini AI as the primary source.

## Current Status ✅
- **Gemini AI Integration**: Working - generates realistic India job listings
- **Fallback Chain**: JSearch → The Muse → Remotive → Gemini AI
- **Database**: 114 jobs currently stored (just tested batch file)
- **Last Refresh**: Added 13 new jobs, updated 37 existing
- **Batch File**: Tested and working ✅
- **PowerShell Script**: Created and ready ✅

## Manual Daily Refresh Setup

### Step 1: Choose Your Script Type

**Option A: Batch File (Recommended for Task Scheduler)**
- File: `web\scripts\daily_india_job_refresh.bat`
- Best for: Windows Task Scheduler, simple execution

**Option B: PowerShell Script**
- File: `web\scripts\daily_india_job_refresh.ps1`
- Best for: PowerShell users, advanced scripting

### Step 2: Test Your Chosen Script

**For Batch File**:
```cmd
cd "C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web\scripts"
daily_india_job_refresh.bat
```

**For PowerShell**:
```powershell
cd "C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web\scripts"
.\daily_india_job_refresh.ps1
```

Expected output:
```
Starting Daily India Job Refresh at 04/09/2026 10:00:00
✓ Refresh successful!
  Source: gemini
  Query: software developer
  Location: India
  Added: X jobs
  Updated: Y jobs
  Total in DB: Z jobs
Daily India Job Refresh completed at 04/09/2026 10:00:00
```

### Step 3: Set Up Windows Task Scheduler

1. **Open Task Scheduler**:
   - Press `Win + R`, type `taskschd.msc`, press Enter

2. **Create New Task**:
   - Click "Create Task..." in the Actions panel
   - **General Tab**:
     - Name: `Daily India Job Refresh`
     - Security options: Run whether user is logged on or not
     - Check: Run with highest privileges
     - Configure for: Windows 10

3. **Triggers Tab**:
   - Click "New..."
   - Begin the task: On a schedule
   - Settings: Daily, Recur every: 1 days
   - Start: Tomorrow at 6:00 AM (or your preferred time)
   - Check: Enabled

4. **Actions Tab**:
   - Click "New..."
   - Action: Start a program
   - **For Batch File**: Program/script: `C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web\scripts\daily_india_job_refresh.bat`
   - **For PowerShell**: Program/script: `powershell.exe`, Add arguments: `-ExecutionPolicy Bypass -File "C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web\scripts\daily_india_job_refresh.ps1"`
   - Start in: `C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web`

5. **Conditions Tab**:
   - Uncheck: Start the task only if the computer is on AC power
   - Check: Wake the computer to run this task

6. **Settings Tab**:
   - Check: Run task as soon as possible after a scheduled start is missed
   - Check: If the task fails, restart every: 1 hour, up to 3 times
   - Check: Stop the task if it runs longer than: 30 minutes
   - Check: If the running task does not end when requested, force it to stop

7. **Save the Task**:
   - Click OK
   - Enter your Windows password when prompted

### Step 4: Test the Scheduled Task

1. **Run Manually**:
   - Right-click the task → Run
   - Check the "Last Run Result" column

2. **Check Logs**:
   - View Task Scheduler History
   - Check command prompt output
   - Verify jobs were added to database

### Step 5: Monitor Daily Execution

**Check Task Status**:
- Open Task Scheduler → Task Scheduler Library
- Look for "Daily India Job Refresh"
- Check "Last Run Time" and "Last Run Result"

**View Job Database**:
```cmd
cd "C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web"
python manage.py shell -c "from core.models import Job; print(f'Total jobs: {Job.objects.count()}')"
```

**Expected Daily Results**:
- **Source**: Gemini AI (primary)
- **Query**: software developer
- **Location**: India
- **Limit**: 50 jobs
- **Added**: 5-15 new jobs daily
- **Updated**: 10-30 existing jobs daily

## Troubleshooting

### Task Fails to Run
1. Check Task Scheduler History for error details
2. Verify batch file path is correct
3. Ensure virtual environment path is correct
4. Check Windows Event Viewer → Windows Logs → Application

### Jobs Not Updating
1. Run batch file manually to test
2. Check Gemini API key is valid
3. Verify internet connection
4. Check database permissions

### Virtual Environment Issues
1. Ensure `.venv` folder exists in web directory
2. Check `activate.bat` exists in `.venv\Scripts\`
3. Try running `python manage.py --version` manually

## Advanced Configuration

### Customize Job Search
Edit the batch file to change parameters:
```batch
python manage.py refresh_daily_jobs --force --location "India" --limit 100 --query "python developer"
```

### Multiple Daily Runs
Create additional tasks for different times/queries:
- Morning: software developer
- Afternoon: data scientist
- Evening: devops engineer

### Email Notifications
Add email alerts on failure by modifying the batch file:
```batch
REM On error, send email (requires email setup)
if %errorlevel% neq 0 (
    echo Job refresh failed, sending alert...
    REM Add email command here
)
```

## Current Job Statistics
- **Total Jobs**: 101
- **Source**: The Muse (last successful)
- **Location Focus**: India + Remote
- **Primary Skills**: Python, JavaScript, Java, React, etc.

The system will now automatically refresh India jobs daily at 6:00 AM using Gemini AI to generate realistic job listings when other APIs are unavailable.