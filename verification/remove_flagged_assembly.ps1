param([Parameter(Mandatory=$true)][string]$AuditPath,[Parameter(Mandatory=$true)][string]$DatasetRoot)
$ErrorActionPreference='Stop'
$auditFile=(Resolve-Path -LiteralPath $AuditPath).Path
$report=Get-Content -LiteralPath $auditFile -Raw | ConvertFrom-Json
$scope=(Resolve-Path -LiteralPath $DatasetRoot).Path.TrimEnd('\')
if ($scope -ne $report.root) { throw 'Audit root does not match the explicit dataset root' }
$prefix=$scope+'\'
$targets=[System.Collections.Generic.List[string]]::new()
foreach ($row in $report.results) {
    if (-not $row.remove) { continue }
    $referenceHash=$null
    foreach ($copy in $row.copies) {
        $imagePath=[IO.Path]::GetFullPath((Join-Path $scope $copy.image))
        $labelPath=[IO.Path]::GetFullPath((Join-Path $scope $copy.label))
        foreach ($path in @($imagePath,$labelPath)) {
            if (-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { throw "Out of scope: $path" }
            if ([IO.Path]::GetFileNameWithoutExtension($path) -notmatch '^assembly_\d+_f\d+$') { throw "Not an assembly: $path" }
        }
        if ([IO.Path]::GetExtension($imagePath) -notin @('.png','.jpg','.jpeg') -or [IO.Path]::GetExtension($labelPath) -ne '.txt') { throw 'Unexpected file type' }
        $currentHash=(Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash
        if ($null -eq $referenceHash) { $referenceHash=$currentHash }
        elseif ($currentHash -ne $referenceHash) { throw "Mirrored images differ: $imagePath" }
        $targets.Add($imagePath)
        if ($null -ne $copy.label_text) {
            if ([IO.File]::ReadAllText($labelPath).Replace("`r`n","`n") -cne $copy.label_text) { throw "Label changed since audit: $labelPath" }
            $targets.Add($labelPath)
        } elseif (Test-Path -LiteralPath $labelPath) { throw "A label appeared since audit: $labelPath" }
    }
}
if (($targets | Select-Object -Unique).Count -ne $targets.Count) { throw 'Repeated deletion path' }
$receipt=Join-Path (Split-Path -Parent $auditFile) 'deletion.json'
@{state='validated';dataset_root=$scope;file_count=$targets.Count;paths=$targets} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receipt -Encoding utf8
foreach ($path in $targets) { Remove-Item -LiteralPath $path }
@{state='complete';dataset_root=$scope;file_count=$targets.Count;removed_unique=$report.summary.remove_unique;paths=$targets} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receipt -Encoding utf8
Write-Output "Removed $($targets.Count) files for $($report.summary.remove_unique) unique questionable assembly images."
