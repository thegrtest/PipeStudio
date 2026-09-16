"""Locate runnable local dependencies without retaining another user's paths."""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent

def configured():
    path = ROOT / 'local_runtime.json'
    return json.loads(path.read_text()) if path.exists() else {}

def python_path():
    candidates = [configured().get('python'), os.environ.get('PIPE_STUDIO_PYTHON'),
                  str(ROOT / '.venv' / 'Scripts' / 'python.exe'),
                  str(ROOT / '.venv' / 'bin' / 'python'), shutil.which('python3'), shutil.which('python')]
    for value in candidates:
        if not value or not Path(value).is_file():
            continue
        check = subprocess.run([value, '-c', 'import PIL, numpy'], capture_output=True,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if check.returncode == 0:
            return Path(value)
    raise FileNotFoundError('A working Python with Pillow and NumPy is required; set local_runtime.json.')

def blender_path():
    candidates = [configured().get('blender'), os.environ.get('PIPE_STUDIO_BLENDER'), shutil.which('blender')]
    candidates += list((ROOT / '.runtime').glob('blender*/blender.exe'))
    candidates += sorted(Path('C:/Program Files/Blender Foundation').glob('Blender */blender.exe'), reverse=True)
    for value in candidates:
        if value and Path(value).is_file():
            return Path(value).resolve()
    raise FileNotFoundError('Blender is missing. Place portable Blender in .runtime or set local_runtime.json.')
