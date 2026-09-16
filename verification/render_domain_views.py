"""Quick Blender render of the three camera recipes and reference crease."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pipe_studio as studio
from domain_profiles import camera_settings
from app_model import validate_settings, front_angle

folder=ROOT/'verification'/'domain-camera-preflight'
folder.mkdir(parents=True,exist_ok=True)
studio.register()
scene=studio.fresh_scene()
studio.setup_scene(scene)
for camera in ('CAM2534','CAM5080','CAM7650'):
    settings=validate_settings({**camera_settings(camera), 'resolution':960,'samples':64,
        'seed':20260914,'defect':'FOLD','defect_style':'AXIAL_PINCH','position':.86,
        'width':.032,'arc':15,'depth':.07,'secondary_strength':.35,'defect_rotation':0})
    settings['angle']=front_angle(settings)
    studio.apply_settings(scene,settings)
    result=studio.export_frame(scene,folder,camera.lower())
    print('DOMAIN_CAMERA_RENDER',camera,result['bbox_xywh'],flush=True)
