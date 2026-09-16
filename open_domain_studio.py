"""Open the tapered-pipe controls on the matched horizontal inspection camera."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio
from domain_profiles import camera_settings
from app_model import validate_settings,front_angle
studio.register()
scene=studio.fresh_scene()
studio.setup_scene(scene)
p=validate_settings({**camera_settings('CAM5080'),'defect':'FOLD','defect_style':'AXIAL_PINCH',
    'position':.86,'depth':.05,'width':.032,'arc':15,'secondary_strength':.35,'seed':20260914})
p['angle']=front_angle(p)
studio.apply_settings(scene,p)
bpy.app.timers.register(studio.arrange_view,first_interval=.4)
print('CAMERA_MATCHED_PIPE_STUDIO_READY',flush=True)
