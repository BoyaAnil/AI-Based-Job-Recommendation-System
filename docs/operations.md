# Operations Runbook

## Seed Demo Data

From `web/`:

```powershell
python manage.py seed_demo
```

What it does:

- Loads `sample_data/jobs.json` into `Job`
- Creates/updates demo users:
  - `demo / demo1234`
  - `admin / admin1234`

## Import Real Jobs

Basic:

```powershell
python manage.py fetch_jobs --source auto --query "developer" --location "India" --limit 50
```

Useful options:

- `--source auto|jsearch|themuse|remotive`
- `--clear` to delete existing jobs first
- `--require-location-match` to keep only location-matching jobs

Examples:

```powershell
python manage.py fetch_jobs --source themuse --query "software" --location "India" --limit 100 --require-location-match --clear
python manage.py fetch_jobs --source jsearch --query "python developer" --location "India" --limit 50
```

## Recommendation-Time API Refresh

The recommendations page can fetch jobs dynamically before scoring when `include_api=1`.
Data source fallback order is:

1. JSearch
2. The Muse
3. Remotive

## Scheduled Daily Refresh (Windows)

Script available:

- `web/scripts/daily_job_refresh.bat`

Task registration example:

```powershell
$taskName='AI Resume Analyzer Daily Job Refresh'
$script='C:\path\to\repo\web\scripts\daily_job_refresh.bat'
$action=New-ScheduledTaskAction -Execute $script
$trigger=New-ScheduledTaskTrigger -Daily -At 9:00AM
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Description 'Refresh latest real jobs daily for AI Resume Analyzer' -Force
```

## Health Checks

- Django app responds at `/` and auth routes
- Flask health endpoint: `GET http://127.0.0.1:5000/health`

## Logs and Diagnostics

- Django exceptions are visible in terminal during development
- If `DJANGO_EMAIL_BACKEND` is file-based, emails are written to `web/sent_emails/`
