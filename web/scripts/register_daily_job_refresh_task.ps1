$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$TaskName = 'AI Resume Analyzer Daily Job Refresh'
$RefreshScript = Join-Path $ScriptDir 'run_daily_job_refresh.ps1'

if (-not (Test-Path $RefreshScript)) {
    Write-Error "Refresh script not found at $RefreshScript"
    exit 1
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-ExecutionPolicy Bypass -File \"$RefreshScript\""
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Refresh latest jobs daily for AI Resume Analyzer' -Force

Write-Host "Scheduled task '$TaskName' created for 6:00 AM daily refresh." -ForegroundColor Green