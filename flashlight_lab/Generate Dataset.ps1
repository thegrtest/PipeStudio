param(
    [int]$Count = 12,
    [int]$Seed = 1000,
    [int]$Width = 1536,
    [int]$Samples = 64,
    [double]$CleanProbability = 0.3,
    [double]$RollDegrees = 35,
    [string]$Output = '',
    [string]$Blender = '',
    [switch]$Resume,
    [switch]$Demo
)
$ErrorActionPreference = 'Stop'
if (-not $Blender) {
    $Blender = (Get-ChildItem 'C:\Program Files\Blender Foundation\Blender *\blender.exe' | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}
if (-not (Test-Path -LiteralPath $Blender)) { throw 'Specify -Blender with the path to blender.exe.' }
if (-not $Output) { $Output = Join-Path $PSScriptRoot ('output\batch_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff')) }
$renderArgs = @('-b','--factory-startup','--python-exit-code','1','--python',(Join-Path $PSScriptRoot 'flashlight_scene.py'),'--','--output',$Output,'--count',"$Count",'--seed',"$Seed",'--width',"$Width",'--samples',"$Samples",'--clean-probability',$CleanProbability.ToString([cultureinfo]::InvariantCulture),'--roll-degrees',$RollDegrees.ToString([cultureinfo]::InvariantCulture))
if ($Resume) { $renderArgs += '--resume' }
if ($Demo) { $renderArgs += '--demo' }
& $Blender @renderArgs
if ($LASTEXITCODE -ne 0) { throw "Blender exited with code $LASTEXITCODE" }
Write-Host "Dataset saved to $Output"
