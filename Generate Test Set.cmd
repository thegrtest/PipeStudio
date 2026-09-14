@echo off
setlocal
"%~dp0.venv\Scripts\python.exe" "%~dp0generate_test_set.py" %*
if errorlevel 1 pause
endlocal
