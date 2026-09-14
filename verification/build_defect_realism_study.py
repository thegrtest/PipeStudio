from pathlib import Path
import sys,json,math,time
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
studio.register();scene=bpy.context.scene
folder=root/'examples/defect-realism-study';folder.mkdir(exist_ok=True)
infos=[]
cases=[('clean','NONE',0,.015),('shallow_dent','DENT',0,.012),('moderate_dent','DENT',0,.07),
       ('twist_8','TWIST',8,.015),('twist_35','TWIST',35,.015),('twist_100','TWIST',100,.015)]
for name,kind,angle,depth in cases:
    studio.apply_settings(scene,dict(defect=kind,depth=depth,body_twist=angle,body_twist_span=.7,
        flashlight_layout='SINGLE',flashlight_index=1,flashlight_region='BODY',flashlight_camera='FRONT_45',
        resolution=1200,samples=48,position=.5,width=.14,arc=40,defect_style='DEFAULT'))
    obj=next(o for o in scene.objects if o.get('inspection_region')=='BODY' and o['flashlight_id']==1)
    assert obj.data.attributes.get('inspection_rest_position')
    if kind=='TWIST':
        assert min(math.hypot(v.co.x,v.co.z) for v in obj.data.vertices)>.4
        cap=next(o for o in scene.objects if o.get('inspection_region')=='PLASTIC_FACE' and o['flashlight_id']==1)
        assert abs(cap.rotation_euler.y+math.radians(angle))<1e-5
        assert any(p.material_index==1 for p in obj.data.polygons)
    info=track.export_frame(scene,folder,name,studio.settings_dict(scene.pipe_studio));infos.append(info)
    if kind=='TWIST':assert info['annotations'][0]['class_id']==6 and info['annotations'][0]['visible_pixels']>100
    elif kind=='NONE':assert not info['annotations']
    r=scene.render;r.use_border=True;r.use_crop_to_border=True
    r.border_min_x=.17;r.border_max_x=.36;r.border_min_y=0;r.border_max_y=1
    r.filepath=str(folder/(name+'_detail.png'));bpy.ops.render.render(write_still=True)
    r.use_border=False;r.use_crop_to_border=False
track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos))
studio.atomic_json(folder/'checks.json',dict(passed=True,cases=len(cases),twist_class=6,material_coordinates_attached=True))
print('DEFECT_REALISM_STUDY_VERIFIED',flush=True)
