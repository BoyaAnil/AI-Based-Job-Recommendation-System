# Daily India Job Refresh PowerShell Script
# Run this script to manually refresh India jobs or use with Task Scheduler

Write-Host "Starting Daily India Job Refresh at $(Get-Date)" -ForegroundColor Green

# Set working directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$webDir = Split-Path -Parent $scriptPath
Set-Location $webDir

Write-Host "Working directory: $webDir" -ForegroundColor Yellow

# Activate virtual environment
$venvPath = Join-Path $webDir ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & $venvPath
} else {
    Write-Host "Virtual environment not found at: $venvPath" -ForegroundColor Red
    exit 1
}

# Run the job refresh command for remote foreign jobs plus India-wide jobs.
Write-Host "Running job refresh command..." -ForegroundColor Yellow
python manage.py refresh_daily_jobs --force --location "Remote | India" --limit 50 --query "software developer"

# Check exit code
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Job refresh completed successfully!" -ForegroundColor Green
} else {
    Write-Host "✗ Job refresh failed with exit code: $LASTEXITCODE" -ForegroundColor Red
}

Write-Host "Daily India Job Refresh completed at $(Get-Date)" -ForegroundColor Green

# Pause for 5 seconds to see results
Start-Sleep -Seconds 5
