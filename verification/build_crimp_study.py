"""Three-camera crimp defect study and independent geometric opening checks."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track
studio.register()
scene=bpy.context.scene
folder=root/'examples'/'crimp-study';folder.mkdir(exist_ok=True)
infos=[];checks=[]
for kind in ('NONE','OPEN_CENTER','PROTRUDING_CRIMP'):
    studio.apply_settings(scene,dict(defect=kind,flashlight_layout='SINGLE',flashlight_index=1,
        flashlight_region='PLASTIC_FACE',flashlight_capture='ALL',flashlight_camera='FRONT_45',
        resolution=1200,samples=48,crimp_opening=.18,crimp_lift=.09,crimp_spread=.28))
    face=next(o for o in scene.objects if o.get('inspection_region')=='PLASTIC_FACE' and o['flashlight_id']==1)
    tree=BVHTree.FromPolygons([v.co for v in face.data.vertices],[p.vertices for p in face.data.polygons])
    location,normal,index,distance=tree.ray_cast(Vector((.001,1.8,.002)),Vector((0,-1,0)))
    if kind=='OPEN_CENTER':assert location is None,'Opening is capped by geometry'
    elif kind=='NONE':
        assert location is not None and max(v.co.y for v in face.data.vertices)<=1.350001
    else:assert location is not None and location.y>1.42,'Center did not protrude'
    current=button_track.export_views(scene,folder,kind.lower(),studio.settings_dict(scene.pipe_studio))
    assert all(o.hide_render for o in scene.objects if o.get('annotation_only'))
    if kind=='NONE':assert not any(i['annotations'] for i in current)
    else:
        first=current[0]
        assert first['annotations'][0]['visible_pixels']>10,(kind,first['annotations'])
        assert first['annotations'][0]['class_id']==(4 if kind=='OPEN_CENTER' else 5)
    infos.extend(current)
    checks.append(dict(kind=kind,axial_ray_hit_y=location.y if location is not None else None))
    # Tight Blender render for comparing the six folds to the close-up reference.
    render=scene.render
    render.use_border=True;render.use_crop_to_border=True
    render.border_min_x=.17;render.border_max_x=.36;render.border_min_y=0;render.border_max_y=.29
    render.filepath=str(folder/(kind.lower()+'_detail.png'))
    bpy.ops.render.render(write_still=True)
    render.use_border=False;render.use_crop_to_border=False
button_track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(button_track.CLASSES)),images=infos,samples=infos))
studio.atomic_json(folder/'geometry-checks.json',dict(passed=True,checks=checks))
studio.apply_settings(scene,{'defect':'OPEN_CENTER'})
studio.arrange_view()
studio.save_blend(root/'examples'/'button-track'/'Brass Button Track.blend')
print('CRIMP_STUDY_VERIFIED',flush=True)
