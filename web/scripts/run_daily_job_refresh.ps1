$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$ManagePy = Join-Path $ProjectRoot 'manage.py'

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python environment not found at $PythonExe"
    exit 1
}

# Run the Django management command to refresh remote foreign jobs plus India-wide jobs.
Write-Host "Refreshing daily jobs at $(Get-Date)" -ForegroundColor Green
& $PythonExe $ManagePy refresh_daily_jobs --force --location "Remote | India" --limit 100

if ($LASTEXITCODE -eq 0) {
    Write-Host "Daily job refresh completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Daily job refresh failed. Check logs for details." -ForegroundColor Red
}

exit $LASTEXITCODE
