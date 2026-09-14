param([string]$Blender = '')
$ErrorActionPreference = 'Stop'
if (-not $Blender) {
    $Blender = (Get-ChildItem 'C:\Program Files\Blender Foundation\Blender *\blender.exe' | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}
$scene = Join-Path $PSScriptRoot 'output\reference\Flashlight Inspection.blend'
$controls = Join-Path $PSScriptRoot 'blender_controls.py'
if (-not (Test-Path -LiteralPath $scene)) { throw 'Generate the reference scene first; see README.md.' }
Start-Process -FilePath $Blender -ArgumentList @('"' + $scene + '"','--python','"' + $controls + '"') -WindowStyle Normal
