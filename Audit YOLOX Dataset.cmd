@echo off
cd /d "%~dp0"
python yolox_readiness.py --synthetic "..\thegreatawkaning" --real "..\BrassModel11\all\2026-08-19GodsLight" --real "..\BrassModel11\all\2026-08-20" --output "verification\yolox_readiness"
pause
