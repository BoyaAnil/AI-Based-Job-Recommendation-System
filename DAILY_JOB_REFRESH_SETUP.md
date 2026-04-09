# Daily Job Refresh Setup Guide

## Problem Fixed
The daily job refresh wasn't running because there was no automated scheduler. The new `refresh_daily_jobs` management command solves this.

## Quick Start

### Step 1: Test the Command
First, test that the command works:

```powershell
cd "c:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web"
python manage.py refresh_daily_jobs --force --location "India" --limit 100
```

You should see output like:
```
✓ Refresh successful!
  Source: jsearch
  Query: software developer
  Location: India
  Added: 45 jobs
  Updated: 32 jobs
  Total in DB: 523 jobs
```

### Step 2: Schedule with Windows Task Scheduler

#### Option A: Using PowerShell Script (Recommended)

1. Open **Windows Task Scheduler** (Win + R → `taskschd.msc`)
2. Click **Create Task** on the right panel
3. Fill in the details:
   - **Name**: `Daily Job Refresh - India`
   - **Description**: `Automatically refresh India jobs daily at 6 AM`
   - Check: ✓ "Run with highest privileges"

4. Go to **Triggers** tab:
   - Click **New**
   - **Begin the task**: On a schedule
   - **Weekly**: Select all days (or just weekdays)
   - **Time**: 06:00:00 (6 AM)
   - Click **OK**

5. Go to **Actions** tab:
   - Click **New**
   - **Action**: Start a program
   - **Program/script**: 
     ```
     powershell.exe
     ```
   - **Add arguments**:
     ```
     -ExecutionPolicy Bypass -File "C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web\scripts\run_daily_job_refresh.ps1"
     ```
   - Click **OK**

6. Go to **Settings** tab:
   - Check: ✓ "Run task as soon as possible after a scheduled start is missed"
   - Check: ✓ "If the task fails, restart every: 60 minutes"
   - Set: "Stop the task if it runs longer than: 1 hour"
   - Click **OK**

#### Option B: Using Batch Script

1. Open **Windows Task Scheduler**
2. Click **Create Task**
3. Fill in the details (same as above)
4. Go to **Actions** tab:
   - **Program/script**: 
     ```
     C:\Users\boyaa\OneDrive\Documents\AI Resume Analyzer and Job Recommendation\web\scripts\daily_job_refresh.bat
     ```
   - Click **OK**

### Step 3: Monitor the Logs

The batch script logs to:
```
web\logs\daily_job_refresh.log
```

Check this file to see when jobs were last refreshed.

### Step 4: Verify It's Working

After scheduling, you can:
1. Right-click the task → **Run** to test immediately
2. Check the logs to confirm it executed
3. Refresh your browser's Jobs page to see new India jobs

## Command Options

```powershell
# Force refresh (even if refresh window not reached)
python manage.py refresh_daily_jobs --force

# Custom location
python manage.py refresh_daily_jobs --force --location "Bangalore"

# Custom limit
python manage.py refresh_daily_jobs --force --limit 150

# Custom query
python manage.py refresh_daily_jobs --force --query "backend engineer"

# All options
python manage.py refresh_daily_jobs --force --query "python developer" --location "India" --limit 100
```

## Configuration

Edit `web/.env` to customize defaults:

```
AUTO_DAILY_JOB_REFRESH=true
AUTO_DAILY_JOB_REFRESH_HOURS=24
AUTO_DAILY_JOB_QUERY=software developer
AUTO_DAILY_JOB_LOCATION=India
AUTO_DAILY_JOB_LIMIT=100
AUTO_DAILY_JOB_REQUIRE_LOCATION_MATCH=true
```

## Troubleshooting

**Q: The task doesn't run**
- Check Windows Task Scheduler → History tab for error messages
- Verify the file paths are correct
- Run the script manually to test

**Q: No new jobs appearing**
- Check `web\logs\daily_job_refresh.log` for errors
- Verify `JSEARCH_API_KEY` is set in `.env` file
- Try running: `python manage.py refresh_daily_jobs --force`

**Q: Getting location filter errors**
- Jobs might not have "India" in the location field
- Temporarily set `AUTO_DAILY_JOB_REQUIRE_LOCATION_MATCH=false` in `.env`
- Or use `--location "Bangalore"` or remove the filter

## API Keys Required

Make sure these are in `web/.env`:
```
JSEARCH_API_KEY=your_api_key_here
```

The system uses JSearch primarily, with fallback to The Muse and Remotive APIs.
