@echo off
setlocal
if exist "%~dp0dist\Pipe Studio\Pipe Studio.exe" (
  start "" "%~dp0dist\Pipe Studio\Pipe Studio.exe"
) else (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0desktop_app.py"
)
endlocal
