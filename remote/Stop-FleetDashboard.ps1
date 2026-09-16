$ErrorActionPreference='Stop'
$pipeRoot=Split-Path -Parent $PSScriptRoot
$pipeReceipt=Join-Path $pipeRoot '.cache/fleet-dashboard/server.json'
if (-not (Test-Path -LiteralPath $pipeReceipt)) { return }
$pipeState=Get-Content -Raw -LiteralPath $pipeReceipt | ConvertFrom-Json
$pipeProcess=Get-CimInstance Win32_Process -Filter ('ProcessId = '+[int]$pipeState.pid)
$pipeExpected=Join-Path $PSScriptRoot 'fleet_dashboard.py'
if ($pipeProcess -and $pipeProcess.CommandLine.Contains($pipeExpected)) {
    Stop-Process -Id $pipeProcess.ProcessId
    Write-Output 'Dashboard stopped. Generation workers were not changed.'
} elseif ($pipeProcess) {
    throw 'Saved PID belongs to a different process; it was not stopped.'
}
