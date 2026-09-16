@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0remote\Fleet.ps1" -Action Ready
pause
