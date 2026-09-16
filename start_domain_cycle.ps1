param([int]$Count=3200,[int]$Seed=-1,[string]$OutputDir='',[ValidateSet('reference','yolox')][string]$Profile='yolox')
$ErrorActionPreference='Stop'
$studioRoot=$PSScriptRoot
$python=(Get-Command python -ErrorAction Stop).Source
if ($Seed -lt 0) { $Seed=Get-Random -Minimum 1 -Maximum 1900000000 }
if (-not $OutputDir) {
    $stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
    $OutputDir=Join-Path (Split-Path $studioRoot -Parent) "BrassDomainCycle_$stamp"
}
$script=Join-Path $studioRoot 'generate_domain_dataset.py'
if (-not (Test-Path -LiteralPath (Join-Path $OutputDir 'render_plan.json'))) {
    & $python $script --output $OutputDir --count $Count --seed $Seed --profile $Profile --prepare-only
    if ($LASTEXITCODE -ne 0) { throw 'Dataset plan preparation failed.' }
}
$arguments='"{0}" --output "{1}" --resume' -f $script,$OutputDir
$proc=Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $studioRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $OutputDir 'launcher.log') -RedirectStandardError (Join-Path $OutputDir 'launcher-errors.log')
Write-Output "Started camera-matched generator: PID=$($proc.Id), Output=$OutputDir"
