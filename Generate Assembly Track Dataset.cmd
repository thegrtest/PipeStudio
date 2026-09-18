@echo off
setlocal
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0assembly_generate.py" --count 120 --samples 96 %*
pause
endlocal
