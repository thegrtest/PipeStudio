@echo off
start "Rolling shell capture" "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" "%~dp0Rolling shell capture.blend" --python "%~dp0..\..\open_rolling_capture.py"
