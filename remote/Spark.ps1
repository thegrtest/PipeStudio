param(
    [ValidateSet('Status','Start','Stop','Fetch','Shell')][string]$Action = 'Status',
    [ValidateRange(1,100000)][int]$Count = 3000,
    [ValidateRange(1,1000000000)][int]$Seed = 910000,
    [switch]$Smoke,
    [ValidatePattern('^[A-Za-z0-9_.-]+$')][string]$SshAlias = 'pipestudio-spark'
)
$ErrorActionPreference = 'Stop'
$pipeRoot = Split-Path -Parent $PSScriptRoot
$pipeCommand = 'cd ~/PipeStudio && .venv/bin/python remote/spark_control.py '
if ($Action -eq 'Shell') { & ssh $SshAlias; exit $LASTEXITCODE }
if ($Action -eq 'Fetch') {
    $pipeResult = & ssh -o BatchMode=yes $SshAlias ($pipeCommand + 'pack')
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the dataset transfer.' }
    $pipeTransfer = $pipeResult | ConvertFrom-Json
    if ($pipeTransfer.job -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unexpected remote job name.' }
    $pipeDestination = Join-Path $pipeRoot 'exports/spark_captures'
    $pipeCache = Join-Path $pipeRoot '.cache/spark-transfers'
    New-Item -ItemType Directory -Force -Path $pipeDestination,$pipeCache | Out-Null
    $pipeArchive = Join-Path $pipeCache ($pipeTransfer.job + '.tar.gz')
    & scp -o BatchMode=yes "${SshAlias}:$($pipeTransfer.archive)" $pipeArchive
    if ($LASTEXITCODE -ne 0) { throw 'Dataset transfer failed; remote originals are retained.' }
    & tar -xzf $pipeArchive -C $pipeDestination
    if ($LASTEXITCODE -ne 0) { throw 'Dataset extraction failed.' }
    Write-Output (Join-Path $pipeDestination $pipeTransfer.job)
    exit 0
}
$pipeArguments = $Action.ToLowerInvariant()
if ($Action -eq 'Start') {
    $pipeArguments += " --count $Count --seed $Seed"
    if ($Smoke) { $pipeArguments += ' --smoke' }
}
& ssh -o BatchMode=yes $SshAlias ($pipeCommand + $pipeArguments)
exit $LASTEXITCODE
