"""Headless Blender v3 integration smoke; source images and user scenes untouched.

Run from the project with Blender -b --factory-startup --python
verification/verify_v3_blender.py. Uses a fresh scene, 320 px and eight beauty
samples; writes evidence to verification/v3-smoke. Do not run alongside a
production GPU render. A failure writes result.json and exits nonzero.
"""
from pathlib import Path
import hashlib
import json
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bpy
import numpy as np
import pipe_studio as studio
from geometry import DEFECT_STYLES
from lighting_profiles import LIGHTING_IDS, LIGHT_KEYS, lighting_settings
from scene_presets import SCENE_PRESETS

OUT=ROOT/'verification'/'v3-smoke'
OUT.mkdir(parents=True,exist_ok=True)
REPORT={'passed':False,'blender':bpy.app.version_string,'checks':[],'lighting':{},'exports':[]}

def require(condition, message):
    if not condition: raise AssertionError(message)

def mesh_digest():
    mesh=bpy.data.objects['PS_Pipe'].data
    vertices=np.empty(len(mesh.vertices)*3,dtype=np.float32)
    mesh.vertices.foreach_get('co',vertices)
    return hashlib.sha256(vertices.tobytes()).hexdigest()

def flush_callbacks():
    # bpy timers do not advance during a synchronous headless Python script.
    if bpy.app.timers.is_registered(studio.delayed_refresh):
        bpy.app.timers.unregister(studio.delayed_refresh)
    studio.delayed_refresh()

def rounded(values): return tuple(round(float(v),5) for v in values)

def camera_snapshot(scene):
    cam=scene.camera
    return (rounded(cam.location),rounded(cam.rotation_euler),round(cam.data.lens,5),
            round(cam.data.shift_x,5),round(cam.data.shift_y,5),
            round(cam.data.dof.focus_distance,5),round(cam.data.dof.aperture_fstop,5))

def beauty_snapshot(scene):
    pipe=bpy.data.objects['PS_Pipe']
    background=scene.world.node_tree.nodes['Background']
    return {'parameters':studio.settings_dict(scene.pipe_studio),
            'view_transform':scene.view_settings.view_transform,
            'exposure':scene.view_settings.exposure,'samples':scene.cycles.samples,
            'denoise':scene.cycles.use_denoising,'dof':scene.camera.data.dof.use_dof,
            'compositing':scene.render.use_compositing,'filepath':scene.render.filepath,
            'pipe_material':pipe.data.materials[0].name,
            'ambient':background.inputs['Strength'].default_value,
            'camera':camera_snapshot(scene),
            'environment_materials':{obj.name:[mat.name if mat else None for mat in obj.data.materials]
              for obj in bpy.data.collections['PS_Studio'].objects
              if obj.name.startswith(('PS_EnvMachine_','PS_EnvGods_')) and hasattr(obj.data,'materials')}}

def validate_export(info, stem, visible, class_id):
    path=OUT/info['mask']
    im=bpy.data.images.load(str(path),check_existing=False)
    try:
        width,height=im.size
        pixels=np.empty(width*height*4,dtype=np.float32)
        im.pixels.foreach_get(pixels)
        pixels=pixels.reshape(height,width,4)[::-1]
        rgb=pixels[:,:,:3]
        require(np.all(np.isfinite(rgb)),stem+': nonfinite mask')
        require(np.all((rgb==0)|(rgb==1)),stem+': mask PNG contains intermediate/antialiased values')
        require(np.array_equal(rgb[:,:,0],rgb[:,:,1]) and np.array_equal(rgb[:,:,1],rgb[:,:,2]),stem+': mask channels differ')
        ys,xs=np.where(rgb[:,:,0]>0.5)
        bbox=None if len(xs)==0 else [int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)]
        require(bbox==(list(info['bbox_xywh']) if info['bbox_xywh'] else None),stem+': metadata bbox differs from saved mask')
        require(len(xs)==info['visible_mask_pixels'],stem+': metadata mask pixel count differs')
        require(bool(bbox)==visible,stem+': unexpected visibility '+str(bbox))
        require(width==320 and height==round(320/scene.pipe_studio.frame_aspect),stem+': wrong dimensions')
    finally:
        bpy.data.images.remove(im)
    label=(OUT/'labels'/(stem+'.txt')).read_text().strip()
    if visible:
        fields=label.split()
        require(len(fields)==5 and int(fields[0])==class_id,stem+': wrong YOLO class/field count')
        require(all(0<=float(v)<=1 for v in fields[1:]),stem+': invalid YOLO normalized box')
        expected=studio.yolo_box(bbox,width,height)
        require(all(abs(float(value)-want)<1e-7 for value,want in zip(fields[1:],expected)),stem+': YOLO box mismatch')
    else:
        require(not label,stem+': unexpected nonempty label')
    require((OUT/info['image']).stat().st_size>500,stem+': beauty not written')
    require((OUT/'metadata'/(stem+'.json')).is_file(),stem+': metadata not written')

try:
    studio.register()
    scene=studio.fresh_scene()
    studio.setup_scene(scene)
    p=scene.pipe_studio
    required=('defect_style','defect_rotation','secondary_strength','lighting_profile','light_azimuth','key_span','finish_marks')
    require(all(key in p.bl_rna.properties for key in required),'New Blender properties are not registered')
    require(set(item.identifier for item in p.bl_rna.properties['defect_style'].enum_items)==set(DEFECT_STYLES),'Defect style enum mismatch')
    require(set(item.identifier for item in p.bl_rna.properties['lighting_profile'].enum_items)==set(LIGHTING_IDS),'Lighting enum mismatch')
    REPORT['checks'].append('All new properties and style/profile enums registered')

    values={**SCENE_PRESETS['MACHINE'],'defect':'DENT','defect_style':'DEFAULT',
            'position':.76,'angle':180,'depth':.12,'width':.035,'arc':20,
            'resolution':320,'samples':8,'finish_marks':.65}
    studio.apply_settings(scene,values)
    flush_callbacks()
    before=mesh_digest()
    for key,value in [('defect_style','DOUBLE'),('defect_rotation',37.0),('secondary_strength',.82)]:
        setattr(p,key,value)
        require(studio.GEOMETRY_DIRTY,'Geometry callback did not mark dirty for '+key)
        flush_callbacks()
        after=mesh_digest()
        require(before!=after,'Geometry callback did not rebuild changed '+key)
        before=after
    require(studio.get_spec(p).defect_style=='DOUBLE','get_spec dropped new geometry settings')
    REPORT['checks'].append('RNA geometry callbacks rebuild style, rotation and secondary-lobe settings')

    mesh_before=mesh_digest()
    p.finish_marks=.87
    flush_callbacks()
    require(mesh_digest()==mesh_before,'Appearance marks changed geometry')
    amount=bpy.data.materials['PS_Brass'].node_tree.nodes['Finish marks amount'].outputs[0].default_value
    require(abs(amount-.87)<1e-5,'Appearance callback did not update finish material')
    REPORT['checks'].append('Finish marks callback updates material without deforming pipe')

    light_fields=set(LIGHT_KEYS)|{'lighting_profile'}
    for environment in ('MACHINE','GODSLIGHT','STUDIO'):
        studio.apply_settings(scene,{**SCENE_PRESETS[environment],**{key:values[key] for key in ('resolution','samples')},
                                    'defect':'DENT','defect_style':'DOUBLE','defect_rotation':37,
                                    'position':.76,'depth':.12,'width':.035,'arc':20,
                                    'finish_marks':.87,'roughness':.47,'texture_strength':.41,'wear':.31})
        flush_callbacks()
        shape=mesh_digest(); camera=camera_snapshot(scene)
        preserved={key:value for key,value in studio.settings_dict(p).items() if key not in light_fields}
        records=[]
        for profile in LIGHTING_IDS:
            # Exercise the actual enum UI callback, including REFERENCE when already selected.
            p.lighting_profile='LOW_LIGHT' if profile=='REFERENCE' else 'REFERENCE'
            flush_callbacks()
            p.lighting_profile=profile
            flush_callbacks()
            actual=studio.settings_dict(p)
            expected=lighting_settings(environment,profile)
            for key,value in expected.items():
                require(abs(actual[key]-value)<1e-4 if isinstance(value,(int,float)) else actual[key]==value,
                        environment+'/'+profile+': lighting callback differs on '+key)
            require({key:value for key,value in actual.items() if key not in light_fields}==preserved,
                    environment+'/'+profile+': lighting recipe changed geometry/camera/material settings')
            require(mesh_digest()==shape,environment+'/'+profile+': lighting changed mesh')
            require(camera_snapshot(scene)==camera,environment+'/'+profile+': lighting changed actual camera')
            key=bpy.data.objects['PS_Key']
            records.append({'profile':profile,'location':rounded(key.location),'energy':round(key.data.energy,4),
                            'size':round(key.data.size,4),'size_y':round(key.data.size_y,4)})
        require(len({tuple(record['location'])+(record['energy'],) for record in records})==6,
                environment+': key positions/energies not distinct across six profiles')
        REPORT['lighting'][environment]=records
    REPORT['checks'].append('Six lighting UI presets per environment preserve shape/camera/finish and drive distinct key position/energy combinations')

    cases=[
        ('appearance_only_clean','MACHINE','NONE','DEFAULT',180,0,False,None),
        ('double_dent_rotated','MACHINE','DENT','DOUBLE',180,37,True,1),
        ('branched_fold_rotated','GODSLIGHT','FOLD','BRANCHED',178,42,True,0),
        ('backside_hidden','MACHINE','FOLD','BRANCHED',0,42,False,0),
    ]
    for index,(stem,environment,defect,style,angle,rotation,visible,class_id) in enumerate(cases):
        studio.apply_settings(scene,{**SCENE_PRESETS[environment],
            'defect':defect,'defect_style':style,'defect_rotation':rotation,'secondary_strength':.78,
            'position':.78 if environment=='MACHINE' else .79,'angle':angle,'depth':.13,
            'width':.033,'arc':18,'resolution':320,'samples':8,'finish_marks':1,
            'sensor_noise':.008,'focus_blur':.35,'exposure':.2})
        flush_callbacks()
        p.mask_view=False
        flush_callbacks()
        scene.render.filepath=str(OUT/'sentinel-restored-path.png')
        if index==3: scene.render.use_compositing=False
        before=beauty_snapshot(scene)
        info=studio.export_frame(scene,OUT,stem)
        require(beauty_snapshot(scene)==before,stem+': beauty state was not fully restored after mask export')
        require(not scene.get('_ps_camera_response_diagnostic',False),stem+': diagnostic compositor bypass remains active')
        validate_export(info,stem,visible,class_id)
        REPORT['exports'].append(info)
        print('V3_EXPORT_PASSED '+stem,flush=True)
    REPORT['checks'].append('Four PNG exports have exact binary masks, correct/empty boxes and YOLO labels, and restore beauty state')
    REPORT['passed']=True
except BaseException as exc:
    REPORT['error']=repr(exc)
    REPORT['traceback']=traceback.format_exc()
    studio.atomic_json(OUT/'result.json',REPORT)
    print(REPORT['traceback'],flush=True)
    raise
else:
    studio.atomic_json(OUT/'result.json',REPORT)
    print('V3_BLENDER_CHECKS_PASSED',flush=True)
