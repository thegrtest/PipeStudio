"""Command-line check of the app's own visible window and completed preview."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import time
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parent
user=ctypes.windll.user32
user.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR]
user.FindWindowW.restype=wintypes.HWND
user.IsWindowVisible.argtypes=[wintypes.HWND]
user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
user.SetForegroundWindow.argtypes=[wintypes.HWND]
user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
user.GetForegroundWindow.restype=wintypes.HWND
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
deadline=time.time()+30
while time.time()<deadline:
    try:
        runtime=json.loads((ROOT/'desktop_runtime.json').read_text())
        window=user.FindWindowW(None,'Pipe Studio | Tapered metal pipes')
        pid=wintypes.DWORD()
        if window:
            user.GetWindowThreadProcessId(window,ctypes.byref(pid))
        state=json.loads((Path(runtime['session'])/'status.json').read_text())
        if window and pid.value==runtime['pid'] and user.IsWindowVisible(window) and state.get('state')=='done':
            break
    except (OSError,ValueError):
        pass
    time.sleep(.25)
else:
    raise RuntimeError('No visible Pipe Studio window with a completed preview was found.')
user.ShowWindow(window,9); user.SetForegroundWindow(window)
time.sleep(.5)
rect=wintypes.RECT(); user.GetWindowRect(window,ctypes.byref(rect))
result={'passed':True,'pid':pid.value,'executable':runtime['executable'],'visible':True,
        'preview_image':state['image'],'device':state.get('device'),'window_bounds':[rect.left,rect.top,rect.right,rect.bottom]}
if user.GetForegroundWindow()==window:
    image_path=ROOT/'verification'/'launched-app.png'
    ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom)).save(image_path)
    result['screenshot']=str(image_path)
(ROOT/'verification'/'launch-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
