@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_domain_cycle.ps1" -Profile yolox %*
pause
