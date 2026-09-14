@echo off
setlocal
if exist "%~dp0examples\button-track\Brass Button Track.blend" (
  start "" "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" "%~dp0examples\button-track\Brass Button Track.blend" --python "%~dp0open_blender_workspace.py"
) else if exist "%~dp0examples\inspection-modes\Inspection Studio.blend" (
  start "" "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" "%~dp0examples\inspection-modes\Inspection Studio.blend" --python "%~dp0open_blender_workspace.py"
) else if exist "%~dp0examples\brass-v4\Brass Surface V4.blend" (
  start "" "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" "%~dp0examples\brass-v4\Brass Surface V4.blend" --python "%~dp0open_blender_workspace.py"
) else if exist "%~dp0examples\challenge-v3\Inspection Realism V3.blend" (
  start "" "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" "%~dp0examples\challenge-v3\Inspection Realism V3.blend" --python "%~dp0open_blender_workspace.py"
) else (
  start "" "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --factory-startup --python "%~dp0pipe_studio.py" -- --preset MACHINE
)
endlocal
