"""Flashlight backend for the shared Blender inspection workspace."""
import json
import math
import random
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from flashlight_lab import flashlight_scene as lab
from app_model import validate_settings, front_angle


def recipe(values):
    p=validate_settings(values)
    spec=lab.recipe(p['seed'],False,p['flashlight_count'],clean_probability=0)
    rng=random.Random(p['seed']+331)
    spec['exposure']=p['exposure']
    spec['light_gain']=1
    for item in spec['items']:
        item['battery_installed']=rng.random()<p['battery_probability']
        item['roll']=math.radians(p['flashlight_roll'])
        item['defect']=None
        if p['defect']=='NONE' or (p['flashlight_layout']=='SINGLE' and item['index']!=p['flashlight_index']):
            continue
        if p['flashlight_layout']=='MIXED':
            # A seeded row contains clean parts as well as all supported damage types.
            kind=['clean','metal_scratch','plastic_dent','clean','metal_dent','plastic_dent'][item['index']%6]
            if kind=='clean':
                continue
        else:
            kind='metal_scratch' if p['defect']=='SCRATCH' else ('plastic_dent' if p['flashlight_surface']=='PLASTIC' else 'metal_dent')
        plastic=kind=='plastic_dent'
        length=2.405 if plastic else .405
        d=dict(id=item['index']+1,kind=kind,angle=math.radians(p['angle']),
               y=(-1.025 if plastic else -1.425)+p['position']*length,
               depth=p['depth']*.5*(.05 if kind=='metal_scratch' else 1),
               arc=math.radians(p['arc']),length=p['width']*length,
               tilt=math.tan(math.radians(p['defect_rotation']))*.4)
        if p['flashlight_layout']=='MIXED':
            start=-1.025 if plastic else -1.425
            d['y']=start+max(.03,min(.97,p['position']+rng.uniform(-.12,.12)))*length
        if kind=='metal_scratch':
            d['lines']=[dict(y=d['y']+rng.uniform(-.06,.06),length=max(.025,d['length']*2),
                             offset=rng.uniform(-d['arc']*.7,d['arc']*.7),
                             slope=rng.uniform(-.1,.1)*(1+p['irregularity']*4),width=.015+p['irregularity']*.02)
                        for _ in range(3+round(p['irregularity']*6))]
        elif p['irregularity']:
            d['tilt']+=rng.uniform(-1,1)*p['irregularity']
        # Zero depth means no affected surface and no labels.
        item['defect']=d if d['depth']>0 else None
    return spec


def clear_owned(scene):
    materials=set()
    for obj in list(scene.objects):
        if obj.get('inspection_flashlight'):
            data=obj.data
            if obj.type=='MESH':
                materials.update(m for m in data.materials if m)
            kind=obj.type
            bpy.data.objects.remove(obj,do_unlink=True)
            if data and data.users==0:
                store={'MESH':bpy.data.meshes,'LIGHT':bpy.data.lights,'CAMERA':bpy.data.cameras}.get(kind)
                if store is not None:
                    store.remove(data)
    for mat in materials:
        if mat.users==0:
            bpy.data.materials.remove(mat)


def activate_pipe(scene):
    if scene.get('_active_product')!='FLASHLIGHT':
        return
    for obj in scene.objects:
        if obj.get('inspection_flashlight'):
            obj.hide_render=True
            obj.hide_set(True)
        elif obj.name.startswith('PS_'):
            obj.hide_render=False
            obj.hide_set(False)
    scene.camera=bpy.data.objects.get('PS_Camera')
    if scene.get('_pipe_world') in bpy.data.worlds:
        scene.world=bpy.data.worlds[scene['_pipe_world']]
    scene.render.use_compositing=True
    scene['_active_product']='PIPE'


def refresh(scene, values):
    p=validate_settings(values)
    mask_view(scene,False)
    if scene.get('_active_product')!='FLASHLIGHT' and scene.world:
        scene['_pipe_world']=scene.world.name
    clear_owned(scene)
    old_world=scene.world
    existing=set(scene.objects)
    for obj in existing:
        if obj.name.startswith('PS_'):
            obj.hide_render=True
            obj.hide_set(True)
    if p['environment']=='BUTTON_TRACK':
        import button_track
        import button_row
        spec=button_row.recipe(scene,p)
        button_row.remember(scene,p,spec)
        button_track.build_scene(spec,p)
    else:
        spec=recipe(p)
        lab.build_scene(spec,p['resolution'],p['samples'],reset=False,preserve_objects=True)
    for obj in set(scene.objects)-existing:
        obj['inspection_flashlight']=True
    scene.world['inspection_flashlight']=True
    if old_world and old_world.get('inspection_flashlight') and old_world.users==0:
        bpy.data.worlds.remove(old_world)
    scene['_active_product']='FLASHLIGHT'
    scene.render.use_compositing=False
    scene.render.resolution_y=round(p['resolution']/p['frame_aspect'])
    scene.camera.data.ortho_scale=max(p['flashlight_count']-.22,3.8*p['frame_aspect'])/p['camera_zoom']
    scene.camera.data.shift_x=p['camera_shift_x']
    scene.camera.data.shift_y=p['camera_shift_y']
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=p['ambient_strength']
    scene.view_settings.view_transform='Standard' if p['tone_mapping']=='STANDARD' else 'AgX'
    powers={'Broad inspection softbox':p['key_power'],'Right grazing strip':p['fill_power'],'Top edge reflection':p['rim_power']}
    for obj in scene.objects:
        if not obj.get('inspection_flashlight'):
            continue
        if obj.type=='LIGHT':
            obj.data.energy=powers.get(obj.name.split('.')[0],p['fill_power'])
            obj.data.color=(1,max(.5,1-abs(p['color_cast'])*.2),max(.5,1-max(0,p['color_cast'])*.4))
            if obj.name.startswith('Broad inspection'):
                theta=math.radians(p['key_angle'])
                obj.location=(-4*math.cos(theta),-.5,1+4*math.sin(theta))
                obj.data.size=p['light_softness']*2.66
                obj.data.size_y=4*p['key_span']
            if p['environment']=='TRACK_GRAZING' and obj.name.startswith('Right grazing'):
                obj.location=(4,.3,1.15)
                obj.data.size=.35
            obj.rotation_euler=(Vector((0,0,.4))-obj.location).to_track_quat('-Z','Y').to_euler()
        if obj.type=='MESH':
            for mat in obj.data.materials:
                if not mat or not mat.use_nodes:
                    continue
                bsdf=mat.node_tree.nodes.get('Principled BSDF')
                if bsdf and ('Plastic' in mat.name or 'bulb housing' in mat.name):
                    socket=bsdf.inputs['Roughness']
                    for link in list(socket.links):
                        mat.node_tree.links.remove(link)
                    socket.default_value=p['roughness']
                    for node in mat.node_tree.nodes:
                        if node.type=='BUMP':
                            node.inputs['Strength'].default_value=p['texture_strength']
    if p['environment']=='BUTTON_TRACK':
        button_track.configure(scene,p)
    devices=[d.name for d in bpy.context.preferences.addons['cycles'].preferences.devices if d.use and d.type!='CPU']
    scene['pipe_device']=', '.join(devices) or 'CPU'
    scene['flashlight_recipe']=json.dumps(spec)
    bpy.context.view_layer.update()


def mask_view(scene, enabled):
    for obj in scene.objects:
        if obj.type!='MESH' or not obj.get('inspection_flashlight'):
            continue
        if obj.get('annotation_only'):
            obj.hide_render=not enabled;obj.hide_set(not enabled)
        if enabled:
            if 'flashlight_original_materials' not in obj:
                obj['flashlight_original_materials']=[m.name for m in obj.data.materials]
            for i in range(len(obj.data.materials)):
                color='White' if i==1 and obj.get('defect_id') else 'Black'
                name='InspectionMask'+color
                obj.data.materials[i]=bpy.data.materials.get(name) or lab.emission(name,(1,1,1) if color=='White' else (0,0,0))
        elif 'flashlight_original_materials' in obj:
            for i,name in enumerate(obj['flashlight_original_materials']):
                obj.data.materials[i]=bpy.data.materials[name]
            del obj['flashlight_original_materials']


def export_frame(scene, folder, stem, values):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    mask_view(scene,False)
    if values['environment']=='BUTTON_TRACK':
        import button_track
        try:
            return button_track.export_frame(scene,folder,stem,values)
        finally:mask_view(scene,scene.pipe_studio.mask_view)
    spec=json.loads(scene['flashlight_recipe'])
    state=(scene.render.filepath,scene.camera.data.dof.use_dof,scene.render.use_compositing)
    try:
        scene.camera.data.dof.use_dof=False
        scene.render.use_compositing=False
        info=lab.export_frame(scene,spec,folder,stem)
        w,h=info['width'],info['height']
        union=np.zeros((h,w),dtype=bool)
        for annotation in info['annotations']:
            im=bpy.data.images.load(str(folder/annotation['mask']),check_existing=False)
            data=np.empty(w*h*4,dtype=np.float32)
            im.pixels.foreach_get(data)
            union |= data.reshape(h,w,4)[::-1,:,0]>.5
            bpy.data.images.remove(im)
        lab.save_binary(folder/'masks'/f'{stem}.png',union)
        ys,xs=np.where(union)
        bbox=[int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)] if len(xs) else None
        if values['sensor_noise']>0:
            path=folder/info['image']
            im=bpy.data.images.load(str(path),check_existing=False)
            pixels=np.empty(w*h*4,dtype=np.float32)
            im.pixels.foreach_get(pixels)
            pixels=pixels.reshape(h,w,4)
            noise=np.random.default_rng(values['seed']).normal(0,values['sensor_noise'],(h,w,3))
            pixels[:,:,:3]=np.clip(pixels[:,:,:3]+noise,0,1)
            im.pixels.foreach_set(pixels.ravel())
            im.filepath_raw=str(path); im.save()
            bpy.data.images.remove(im)
        info.update(mask=f'masks/{stem}.png',bbox_xywh=bbox,visible_mask_pixels=int(union.sum()),
                    has_visible_geometric_mask=bool(bbox),parameters=values,product_mode='FLASHLIGHT',
                    defect_type=values['defect'],renderer='Blender '+bpy.app.version_string+' / Cycles',calibrated=False)
        lab.write_json(folder/'metadata'/f'{stem}.json',info)
        return info
    finally:
        scene.render.filepath,scene.camera.data.dof.use_dof,scene.render.use_compositing=state
        mask_view(scene,scene.pipe_studio.mask_view)


def run_job(job_path):
    import pipe_studio as studio
    job_path=Path(job_path)
    folder=job_path.parent
    job=json.loads(job_path.read_text())
    base=validate_settings(job['settings'])
    scene=bpy.context.scene
    completed=[]
    button=base['environment']=='BUTTON_TRACK'
    if button:
        import button_track
    classes=button_track.CLASSES if button else lab.CLASSES
    # Make each per-image YOLO dataset usable while the long batch is running.
    for relative,names in [('',classes)]+([('regions',button_track.REGIONS),('shells',('shell',))] if button else []):
        destination=folder/relative
        destination.mkdir(parents=True,exist_ok=True)
        (destination/'classes.txt').write_text('\n'.join(names)+'\n')
        (destination/'dataset.yaml').write_text('path: '+destination.resolve().as_posix()+'\ntest: images\nnames:\n'+
            ''.join(f'  {index}: {json.dumps(name)}\n' for index,name in enumerate(names)))
    if job.get('resume') and (folder/'manifest.json').exists():
        completed=json.loads((folder/'manifest.json').read_text())['samples']
    views_per_row=3 if button and base['flashlight_capture']=='ALL' else 1
    if len(completed)%views_per_row:
        raise ValueError('Cannot resume an incomplete specimen group in the manifest')
    first_row=len(completed)//views_per_row
    try:
        for i in range(first_row,job['count']):
            if (folder/'cancel.flag').exists():
                studio.atomic_json(folder/'status.json',dict(state='cancelled',completed=i,total=job['count'],rendered_images=len(completed)))
                break
            current=dict(base)
            if job.get('randomize'):
                rng=random.Random(base['seed']+i*7919)
                if button:
                    from flashlight_capture import varied_settings
                    current=varied_settings(base,i)
                else:
                    current.update(seed=base['seed']+i,position=rng.uniform(.15,.85),
                                   depth=base['depth']*rng.uniform(.5,1),exposure=max(-3,min(3,base['exposure']+rng.uniform(-.15,.15))))
                if not job.get('front_only',True):
                    current['flashlight_roll']=rng.uniform(-180,180)
                elif not button:
                    current['angle']=front_angle(current)
                if rng.random()<job.get('clean_fraction',.2):
                    current['defect']='NONE'
            if button and not job.get('randomize') and job.get('flashlight_recipe'):
                import button_row
                button_row.remember(scene,current,job['flashlight_recipe'])
            if button and job.get('body_dents_per_row'):
                import button_row
                forced=button_track.force_body_dents(button_track.make_recipe(current),current,job['body_dents_per_row'])
                assert sum(d['kind']=='plastic_dent' and d['region']=='BODY' for d in forced['defects'])==job['body_dents_per_row']
                button_row.remember(scene,current,forced)
            studio.apply_settings(scene,current)
            studio.atomic_json(folder/'status.json',dict(state='rendering',completed=i,total=job['count'],rendered_images=len(completed)))
            if button:
                mask_view(scene,False)
                completed.extend(button_track.export_views(scene,folder,f'flashlight_{i:05d}',current))
            else:
                completed.append(export_frame(scene,folder,f'flashlight_{i:05d}',current))
            # Keep the workspace manifest shape; retain the lab format for its review tool.
            studio.atomic_json(folder/'manifest.json',dict(product_mode='FLASHLIGHT',classes=dict(enumerate(classes)),
                               samples=completed,images=completed,seed=base['seed'],calibrated=False))
        else:
            studio.atomic_json(folder/'status.json',dict(state='complete',completed=job['count'],total=job['count'],rendered_images=len(completed),
                               last_image=str(folder/completed[-1]['image']) if completed else None))
        (folder/'classes.txt').write_text('\n'.join(classes)+'\n')
        coco=dict(images=[],annotations=[],categories=[dict(id=i,name=n) for i,n in enumerate(classes)])
        for image_id,info in enumerate(completed,1):
            coco['images'].append(dict(id=image_id,file_name=info['image'],width=info['width'],height=info['height']))
            for a in info['annotations']:
                if a['bbox_xywh']:
                    coco['annotations'].append(dict(id=len(coco['annotations'])+1,image_id=image_id,category_id=a['class_id'],
                                                   bbox=a['bbox_xywh'],area=a['visible_pixels'],iscrowd=0))
        studio.atomic_json(folder/'annotations.coco.json',coco)
        (folder/'dataset.yaml').write_text('path: '+folder.as_posix()+'\ntest: images\nnames:\n'+''.join(f'  {i}: {n}\n' for i,n in enumerate(classes)))
        if button:button_track.write_region_dataset(folder,completed)
        if completed:
            studio.save_blend(folder/'last_scene.blend')
    except Exception as exc:
        studio.atomic_json(folder/'status.json',dict(state='failed',completed=len(completed),error=str(exc)))
        raise
