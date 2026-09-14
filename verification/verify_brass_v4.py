"""Blender checks for live material controls and exact geometric-mask isolation."""
from pathlib import Path
import sys,json,hashlib,math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy,numpy as np
import pipe_studio as s
from scene_presets import SCENE_PRESETS
from brass_finishes import FINISH_ITEMS
out=ROOT/'verification'/'brass-v4'/'checks';out.mkdir(parents=True,exist_ok=True)
s.register();scene=s.fresh_scene();s.setup_scene(scene)

def mesh_signature():
    mesh=bpy.data.objects['PS_Pipe'].data
    a=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',a)
    mask=np.empty(len(mesh.vertices),dtype=np.float32);mesh.attributes['defect_mask'].data.foreach_get('value',mask)
    return hashlib.sha256(a.tobytes()+mask.tobytes()).hexdigest()

def sockets():
    result={}
    for n in bpy.data.materials['PS_Brass'].node_tree.nodes:
        for i,socket in enumerate(tuple(n.inputs)+tuple(n.outputs)):
            value=getattr(socket,'default_value',None)
            if isinstance(value,(int,float)):
                assert math.isfinite(value),(n.name,socket.name)
                result[n.name+str(i)]=value
            elif value is not None and not isinstance(value,str) and hasattr(value,'__len__'):
                values=tuple(value)
                if all(isinstance(v,(int,float)) for v in values):
                    assert all(math.isfinite(v) for v in values),(n.name,socket.name)
                    result[n.name+str(i)]=values
    return result

checks=[]
def light_signature():
    return tuple((name,tuple(bpy.data.objects[name].location),tuple(bpy.data.objects[name].rotation_euler),
                  tuple(bpy.data.objects[name].data.color),bpy.data.objects[name].data.energy,
                  bpy.data.objects[name].data.size,bpy.data.objects[name].data.size_y)
                 for name in ('PS_Key','PS_Fill','PS_Rim','PS_Bounce'))

for env in ('MACHINE','GODSLIGHT','STUDIO'):
    s.apply_settings(scene,{**SCENE_PRESETS[env],'resolution':320,'samples':8})
    original=s.settings_dict(scene.pipe_studio); signature=mesh_signature()
    lights=light_signature()
    if env!='GODSLIGHT':
        assert tuple(bpy.data.objects['PS_Fill'].data.color)==(1,1,1),'Rig tint must reset on environment switch'
    for profile,_,_ in FINISH_ITEMS:
        assert bpy.ops.pipe.brass_finish(preset=profile)=={'FINISHED'}
        assert mesh_signature()==signature
        current=s.settings_dict(scene.pipe_studio)
        for key in ('length','radius','wall_ratio','defect','angle','camera_yaw','camera_elevation','key_power','key_angle','lighting_profile'):
            assert current[key]==original[key],(env,profile,key)
        mat=bpy.data.materials['PS_Brass'];nodes=mat.node_tree.nodes
        assert mat['pipe_brass_version']==4
        assert nodes['BrassShader'].inputs['Anisotropic'].default_value>.1
        assert nodes['PolishedBrass'].inputs['Anisotropic'].default_value>.1
        assert nodes['BrassShader'].inputs['Tangent'].is_linked
        assert nodes['BrassShader'].inputs['Metallic'].default_value==1
        assert nodes['DullOxide'].inputs['Metallic'].default_value==0
        assert not nodes['Brass output'].inputs['Displacement'].is_linked
        snapshot=sockets();s.refresh(scene)
        assert sockets()==snapshot,'Material update must be idempotent'
        assert light_signature()==lights,'Finish updates must preserve actual lights without accumulating color'
    checks.append(env+' finish operators preserve geometry/camera/lights; directional reflection is active')

base={**SCENE_PRESETS['MACHINE'],'resolution':480,'samples':16,'seed':271}
records=[];mask_arrays=[]
for name,values in [('bare',dict(oxide_amount=0,polish_amount=0,finish_marks=0)),
                    ('worn',dict(oxide_amount=1,polish_amount=1,finish_marks=1)),
                    ('worn_relight',dict(oxide_amount=1,polish_amount=1,finish_marks=1,key_power=750))]:
    s.apply_settings(scene,{**base,**values});sockets()
    record=s.export_frame(scene,out,name);records.append(record)
    im=bpy.data.images.load(str(out/record['mask']),check_existing=False)
    pixels=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(pixels);bpy.data.images.remove(im)
    assert set(np.unique(pixels))<={0.,1.}
    mask_arrays.append(pixels)
assert all(np.array_equal(mask_arrays[0],x) for x in mask_arrays[1:]),'Appearance must not change diagnostic mask pixels'
assert records[0]['bbox_xywh'] and len({tuple(r['bbox_xywh']) for r in records})==1
s.apply_settings(scene,{**base,'defect':'NONE','oxide_amount':1,'polish_amount':1,'finish_marks':1})
clean=s.export_frame(scene,out,'marked_clean');assert clean['bbox_xywh'] is None and clean['visible_mask_pixels']==0
records.append(clean)
checks.append('Bare/worn/relit masks are pixel-identical; fully marked clean pipe stays unlabeled')
s.atomic_json(out/'manifest.json',{'classes':{'0':'Fold','1':'Dent'},'samples':records})
s.atomic_json(out/'result.json',{'passed':True,'checks':checks,'renderer':bpy.app.version_string,
    'baseline_mask_pixel_hash':hashlib.sha256(mask_arrays[0].tobytes()).hexdigest()})
print('BRASS_V4_CHECKS_PASSED',flush=True)
