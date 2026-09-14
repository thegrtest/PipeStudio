"""Capture only the launched Blender workspace for command-driven visual QA."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import time
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parent
runtime=json.loads((ROOT/'blender_runtime.json').read_text())
user=ctypes.windll.user32
user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user.IsWindowVisible.argtypes=[wintypes.HWND]
user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user.SetForegroundWindow.argtypes=[wintypes.HWND]
user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
user.GetForegroundWindow.restype=wintypes.HWND
callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
user.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
ctypes.windll.shcore.SetProcessDpiAwareness(1)
windows=[]
@callback_type
def visit(window,_):
    pid=wintypes.DWORD(); user.GetWindowThreadProcessId(window,ctypes.byref(pid))
    if pid.value==runtime['pid'] and user.IsWindowVisible(window):
        windows.append(window)
    return True
user.EnumWindows(visit,0)
assert windows,'The Blender process has no visible window.'
window=windows[0]
user.ShowWindow(window,9); user.SetForegroundWindow(window)
time.sleep(1)
rect=wintypes.RECT(); user.GetWindowRect(window,ctypes.byref(rect))
target=ROOT/'verification'/'blender-workspace.png'
ImageGrab.grab(window=window).save(target)
print(json.dumps({'visible':True,'pid':runtime['pid'],'environment':runtime['environment'],'screenshot':str(target)}))
