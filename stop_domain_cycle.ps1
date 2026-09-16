param([switch]$Quiet)
$ErrorActionPreference='Stop'
$desktopRoot=Split-Path $PSScriptRoot -Parent
$count=0
foreach ($directory in Get-ChildItem -LiteralPath $desktopRoot -Directory -Filter 'BrassDomain*') {
    $progressPath=Join-Path $directory.FullName 'progress.json'
    if (-not (Test-Path -LiteralPath $progressPath)) { continue }
    try { $progress=Get-Content -Raw -LiteralPath $progressPath | ConvertFrom-Json } catch { continue }
    if ($progress.state -eq 'rendering') {
        New-Item -ItemType File -Path (Join-Path $directory.FullName 'cancel.flag') -Force | Out-Null
        $count+=1
    }
}
if ($Quiet) { Write-Output $count }
else { Write-Output "Requested stop after the current image for $count camera-matched cycle(s)." }
