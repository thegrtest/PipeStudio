param(
    [ValidateSet('Prepare','Start','Status','Stop','Resume','Fetch','Doctor','Sync','Ready','Launch','Defects-Only')][string]$Action='Status',
    [string]$Nodes='desktop,spark,agx',
    [int]$Count=3200,
    [switch]$PerNode,
    [Nullable[int]]$Seed=$null,
    [ValidateSet('quick','full')][string]$Quality='full',
    [switch]$Smoke,
    [switch]$Force,
    [string]$Run
)
$ErrorActionPreference='Stop'
$pipeRoot=Split-Path -Parent $PSScriptRoot
$pipePython=Join-Path $pipeRoot '.venv/Scripts/python.exe'
$pipeArguments=@((Join-Path $PSScriptRoot 'fleet.py'),$Action.ToLowerInvariant(),'--nodes',$Nodes,'--count',$Count,'--quality',$Quality)
if ($null -ne $Seed) { $pipeArguments+=@('--seed',[string]$Seed) }
if ($Smoke) { $pipeArguments+='--smoke' }
if ($PerNode) { $pipeArguments+='--per-node' }
if ($Force) { $pipeArguments+='--force' }
if ($Run) { $pipeArguments+=@('--run',$Run) }
& $pipePython @pipeArguments
exit $LASTEXITCODE
