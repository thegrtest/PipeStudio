"""Persistent row recipes and small, local defect updates in the Blender workspace."""
import copy
import json
import random
import time
import math
import struct
import bpy
import button_track as track

RECIPE_KEYS=('seed','flashlight_count','flashlight_layout','flashlight_index','flashlight_region',
    'flashlight_roll','defect','angle','position','depth','width','arc','defect_rotation',
    'irregularity','defect_style','crimp_opening','crimp_lift','crimp_spread','crimp_twist',
    'crimp_fold_depth','crimp_tightness','body_twist','body_twist_span')

def key(p):
    # Blender stores FloatProperty values as float32. Normalize both incoming
    # settings and read-back settings so float precision cannot discard edits.
    values={k:(round(struct.unpack('f',struct.pack('f',p[k]))[0],6) if isinstance(p[k],float) else p[k]) for k in RECIPE_KEYS}
    return json.dumps(values,sort_keys=True)

def remember(scene,p,spec):
    scene['flashlight_recipe']=json.dumps(spec)
    scene['button_row_key']=key(p)
    scene['button_row_next_index']=spec.get('next_shell_index',0)
    scene['button_row_defective_count']=sum(bool(item['defect']) for item in spec['items'])

def recipe(scene,p):
    previous=json.loads(scene.get('flashlight_recipe','{}'))
    if (scene.get('button_row_key')==key(p) and previous.get('version') in (11,track.RECIPE_VERSION)
            and len(previous.get('items',[]))==p['flashlight_count']):
        previous['exposure']=p['exposure']
        track.plastic_dents.upgrade(previous);previous['version']=track.RECIPE_VERSION
        return previous
    return track.make_recipe(p)

def next_spec(spec,p):
    updated=copy.deepcopy(spec)
    revision=spec.get('row_revision',0)+1
    index=(p['flashlight_index'] if p['flashlight_layout']=='SINGLE' else spec.get('next_shell_index',0))%len(spec['items'])
    rng=random.Random(p['seed']+revision*7919)
    region=p['flashlight_region'] if p['flashlight_layout']=='SINGLE' else rng.choice(track.REGION_KEYS)
    kinds=('DENT','SCRATCH','OPEN_CENTER','PROTRUDING_CRIMP') if region=='PLASTIC_FACE' else ('DENT','SCRATCH')
    if region=='BODY':kinds=('DENT','DENT','SCRATCH','TWIST')
    kind=(p['defect'] if p['flashlight_layout']=='SINGLE' and p['defect']!='NONE' else rng.choice(kinds))
    if spec.get('required_body_dents'):
        old=spec['items'][index].get('defect')
        if old and old['region']=='BODY' and old['kind']=='plastic_dent':
            region='BODY';kind='DENT'
        elif region=='BODY' and kind=='DENT':
            kind='SCRATCH'
    q={**p,'seed':p['seed']+revision*7919,'flashlight_layout':'SINGLE','flashlight_index':index,
       'flashlight_region':region,'defect':kind,'position':rng.uniform(.1,.9),
       'depth':max(.004,min(.25,p['depth']*rng.choice((.1,.2,.35,.65,1.)))),'width':max(.025,min(.18,p['width']*rng.uniform(.6,1.4))),
       'angle':rng.uniform(65,115),'arc':rng.uniform(15,45),'irregularity':rng.uniform(.1,.55),
       'defect_style':rng.choice(('DEFAULT','ELONGATED','DOUBLE','OBLIQUE','WRINKLED','BRANCHED')),
       'crimp_opening':min(.35,max(.01,p['crimp_opening']*rng.uniform(.5,1.5))),
       'crimp_lift':min(.25,max(.01,p['crimp_lift']*rng.uniform(.5,1.5)))}
    q['body_twist']=(p['body_twist']*rng.uniform(.8,1.2) if p['flashlight_layout']=='SINGLE' else rng.choice((-1,1))*rng.choice((3,6,10,15,25)))
    q['body_twist']=max(-140,min(140,q['body_twist']))
    candidate=track.make_recipe(q)['items'][index]
    updated['items'][index]['defect']=candidate['defect']
    updated['defects']=[item['defect'] for item in updated['items'] if item['defect']]
    updated.update(row_revision=revision,last_changed_index=index,next_shell_index=(index+1)%len(spec['items']))
    return updated,index

def mutate(scene,p):
    from flashlight_integration import mask_view
    started=time.perf_counter()
    spec=recipe(scene,p)
    # A stale recipe must be synchronized before local mutation is safe.
    if scene.get('button_row_key')!=key(p):
        from flashlight_integration import refresh
        refresh(scene,p)
        spec=recipe(scene,p)
    updated,index=next_spec(spec,p)
    item=updated['items'][index]
    regions={item['defect']['region']} if item['defect'] else set()
    if spec['items'][index]['defect']:regions.add(spec['items'][index]['defect']['region'])
    twisted=any(d and d['kind']=='body_twist' for d in (item['defect'],spec['items'][index]['defect']))
    mask_view(scene,False)
    old=[o for o in scene.objects if o.get('flashlight_id')==index and
         (o.get('inspection_region') in regions or (o.get('annotation_only') and 'PLASTIC_FACE' in regions))]
    originals={o['inspection_region']:o for o in old if o.get('inspection_region')}
    before=set(scene.objects)
    try:
        for region in regions:
            source=originals[region]
            mat=source.data.materials[0]
            if region in ('BODY','TOP'):track.side(item,region,mat)
            else:track.end_face(item,region,mat,source.data.materials[2] if region=='BRASS_FACE' else None)
        created=set(scene.objects)-before
    except Exception:
        for obj in set(scene.objects)-before:
            mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
            if mesh.users==0:bpy.data.meshes.remove(mesh)
        mask_view(scene,scene.pipe_studio.mask_view)
        raise
    materials=set()
    for obj in old:
        mesh=obj.data;materials.update(mesh.materials)
        bpy.data.objects.remove(obj,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    for obj in created:
        obj['inspection_flashlight']=True
        if obj.get('inspection_region'):
            obj.name=f'Button flashlight {index:02} | {obj["inspection_region"]}'
    for mat in materials:
        if mat and mat.users==0:bpy.data.materials.remove(mat)
    if twisted and 'PLASTIC_FACE' not in regions:
        # An intact closure follows the tube by rigid rotation; its mesh and
        # material need no rebuild when only body torsion changes.
        cap=next(o for o in scene.objects if o.get('inspection_region')=='PLASTIC_FACE' and o['flashlight_id']==index)
        angle=item['defect']['twist_degrees'] if item['defect'] and item['defect']['kind']=='body_twist' else 0
        cap.rotation_euler.y=item['roll']-math.radians(angle)
    remember(scene,p,updated)
    scene['button_row_last_update_seconds']=time.perf_counter()-started
    scene['button_row_rebuilt_regions']=len(regions)
    mask_view(scene,scene.pipe_studio.mask_view)
    bpy.context.view_layer.update()
    return index
