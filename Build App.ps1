$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pipeBuildPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pipeBuildPython)) {
    throw 'Create .venv and install requirements-build.txt first.'
}
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot '.cache\pyinstaller'
& $pipeBuildPython create_app_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
$pipeBuildIcon = Join-Path $PSScriptRoot 'assets\pipe.ico'
& $pipeBuildPython -m PyInstaller --noconfirm --onedir --windowed --noupx --name 'Pipe Studio' --icon $pipeBuildIcon --distpath 'dist' --workpath '.cache\pyinstaller-build' --specpath '.cache' 'desktop_app.py'
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
