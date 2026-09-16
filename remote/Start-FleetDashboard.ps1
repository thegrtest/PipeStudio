param([switch]$NoBrowser,[int]$Port=0)
$ErrorActionPreference='Stop'
$pipeRoot=Split-Path -Parent $PSScriptRoot
$pipeState=Join-Path $pipeRoot '.cache/fleet-dashboard'
$pipeReceipt=Join-Path $pipeState 'server.json'
$pipeUrl=$null
if (Test-Path -LiteralPath $pipeReceipt) {
    try {
        $pipePrevious=Get-Content -Raw -LiteralPath $pipeReceipt | ConvertFrom-Json
        if ($pipePrevious.url -match '^http://127\.0\.0\.1:\d+$') {
            $pipeHealth=Invoke-RestMethod ($pipePrevious.url+'/health') -TimeoutSec 2
            if ($pipeHealth.application -eq 'PipeStudioFleet') { $pipeUrl=$pipePrevious.url }
        }
    } catch { }
}
if (-not $pipeUrl) {
    New-Item -ItemType Directory -Force -Path $pipeState | Out-Null
    $pipePython=Join-Path $pipeRoot '.venv/Scripts/python.exe'
    $pipeScript=Join-Path $PSScriptRoot 'fleet_dashboard.py'
    $pipeStarted=[DateTimeOffset]::UtcNow
    $pipeProcess=Start-Process -FilePath $pipePython -ArgumentList @('"'+$pipeScript+'"','--port',[string]$Port) -WorkingDirectory $pipeRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $pipeState 'stdout.log') -RedirectStandardError (Join-Path $pipeState 'stderr.log') -PassThru
    for ($pipeAttempt=0; $pipeAttempt -lt 40; $pipeAttempt++) {
        Start-Sleep -Milliseconds 100
        if ($pipeProcess.HasExited) { throw 'Dashboard exited; inspect .cache/fleet-dashboard/stderr.log' }
        if (Test-Path -LiteralPath $pipeReceipt) {
            $pipeCurrent=Get-Content -Raw -LiteralPath $pipeReceipt | ConvertFrom-Json
            # Windows venv launchers can give the Python child a different PID.
            if ([DateTimeOffset]::Parse($pipeCurrent.started) -ge $pipeStarted) { $pipeUrl=$pipeCurrent.url; break }
        }
    }
    if (-not $pipeUrl) { throw 'Dashboard did not become ready.' }
}
Write-Output $pipeUrl
if (-not $NoBrowser) { Start-Process $pipeUrl }
