"""Compare saved/current rim geometry and check the joined exterior profiles."""
from pathlib import Path
import sys
import math
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track
studio.register();scene=bpy.context.scene
folder=root/'examples'/'rim-detail';folder.mkdir(exist_ok=True)
def detail(name):
    r=scene.render
    r.resolution_x=1600;r.resolution_y=800;r.resolution_percentage=100;scene.cycles.samples=64
    r.use_border=True;r.use_crop_to_border=True
    r.border_min_x=.02;r.border_max_x=.205;r.border_min_y=0;r.border_max_y=.325
    r.filepath=str(folder/(name+'.png'));bpy.ops.render.render(write_still=True)
    r.use_border=False;r.use_crop_to_border=False
detail('previous_rim')
studio.apply_settings(scene,dict(defect='NONE',flashlight_layout='SINGLE',flashlight_index=0,
    flashlight_region='BRASS_FACE',flashlight_camera='FRONT_45',flashlight_capture='ALL',resolution=1600,samples=64))
detail('refined_rim')
boundary_errors=[]
for i in range(scene.pipe_studio.flashlight_count):
    face=next(o for o in scene.objects if o.get('inspection_region')=='BRASS_FACE' and o['flashlight_id']==i)
    collar=next(o for o in scene.objects if o.get('inspection_region')=='TOP' and o['flashlight_id']==i)
    for a,b in zip(face.data.vertices[-768:],collar.data.vertices[:768]):
        boundary_errors.append((a.co-b.co).length)
        assert (a.co-b.co).length<1e-6,('Open rim joint',i,a.co[:],b.co[:])
    assert abs(max(math.hypot(v.co.x,v.co.z) for v in collar.data.vertices)-button_track.BRASS_RIM_RADIUS)<1e-6
    assert min(v.co.y for v in face.data.vertices)<button_track.button_profile(0)
infos=button_track.export_views(scene,folder,'clean',studio.settings_dict(scene.pipe_studio))
assert len(infos)==3 and all(not i['annotations'] for i in infos)
button_track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(button_track.CLASSES)),images=infos,samples=infos))
studio.atomic_json(folder/'rim-checks.json',dict(passed=True,clean_views=3,joined_rims=scene.pipe_studio.flashlight_count,
    boundary_vertex_error_max=max(boundary_errors),outer_radius=button_track.BRASS_RIM_RADIUS,
    crown_behind_rim=True,recipe_version=infos[0]['recipe']['version']))
studio.apply_settings(scene,dict(resolution=1200,samples=48))
studio.arrange_view();studio.save_blend(root/'examples'/'button-track'/'Brass Button Track.blend')
print('RIM_STUDY_VERIFIED',flush=True)
