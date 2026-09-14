"""Seeded defect recipes and local mesh replacement for the rolling stream."""
import copy
import hashlib
import json
import math
import random
import bpy
from mathutils import Matrix

DEFECT_KEYS=('seed','position','angle','depth','width','arc','irregularity','defect_rotation',
             'defect_style','crimp_opening','crimp_lift','crimp_spread','body_twist','body_twist_span')


def rigs_in(scene):
    return sorted((obj for obj in scene.objects if 'rolling_index' in obj),key=lambda obj:obj['rolling_index'])


def make_recipe(base,rigs,options,pass_index):
    import button_track as track
    from flashlight_capture import varied_settings
    pass_seed=options['random_seed']+pass_index*100003
    items=[];groups=[];prototype=None
    for offset in range(0,len(rigs),6):
        group_index=offset//6
        varied=varied_settings({**base,'seed':pass_seed+group_index*7919},0)
        p={**base,**{key:varied[key] for key in DEFECT_KEYS},'defect':'DENT',
           'flashlight_count':6,'flashlight_layout':'MIXED'}
        row=track.force_body_dents(track.make_recipe(p),p,options['body_dents'])
        prototype=prototype or row
        rng=random.Random(p['seed']+593)
        for local,item in enumerate(row['items']):
            shell_id=offset+local
            if shell_id>=len(rigs):break
            item=copy.deepcopy(item)
            item.update(index=shell_id,source_shell=shell_id,rolling_index=rigs[shell_id]['rolling_index'],
                flip=bool(rigs[shell_id]['rolling_index']%2),length_scale=base['flashlight_length_scale'],
                random_group=group_index)
            defect=item.get('defect')
            if defect:
                defect.update(id=shell_id*4+track.REGION_KEYS.index(defect['region'])+1,flashlight_id=shell_id)
                defect['depth']*=options['defect_strength']
                if defect['kind']=='open_center':defect['opening']=min(.35*.482,defect['opening']*options['defect_strength'])
                if defect['kind']=='protruding_crimp':defect['lift']=min(.25,defect['lift']*options['defect_strength'])
                if defect['kind']=='body_twist':
                    limit=options['twist_limit']
                    if limit==0:item['defect']=None
                    else:defect['twist_degrees']=math.copysign(rng.uniform(min(2,limit),limit),defect['twist_degrees'])
            items.append(item)
        groups.append(dict(index=group_index,seed=p['seed'],body_dents_per_six=options['body_dents']))
    from rolling_soiling import assign
    assign(items,options,pass_seed)
    spec={**prototype,'seed':pass_seed,'items':items,'defects':[item['defect'] for item in items if item['defect']],
        'rolling_capture':True,'randomized':True,'randomization_version':1,'pass_index':pass_index,
        'source_variant_count':len(items),'random_groups':groups,'appearance_parameters':copy.deepcopy(base),
        'randomization_settings':{key:options[key] for key in ('random_seed','body_dents','defect_strength','twist_limit',
            'mix_soiling','dirty_fraction','dirt_strength') if key in options}}
    if options.get('mix_soiling'):spec['randomization_version']=2
    spec.pop('required_body_dents',None)
    digest=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
    spec['recipe_sha256']=digest
    # Rendering the same underlying specimens at another resolution must not
    # make them eligible for a different training/validation split.
    # Dirt variants of the same geometry also belong in the same split.
    identities=[{key:value for key,value in item.items() if key!='normal_appearance'} for item in items]
    identity=hashlib.sha256(json.dumps({'version':1,'items':identities},sort_keys=True).encode()).hexdigest()
    spec['split_group']='rolling_recipe_'+identity[:16]
    return spec


def build(scene,spec):
    """Replace shell meshes once per pass; preserve the track, cameras and motion."""
    import button_track as track
    import flashlight_materials as materials
    import rolling_soiling
    rigs=rigs_in(scene)
    if len(rigs)!=len(spec['items']):raise ValueError('Saved recipe does not match the rolling rig count.')
    old_meshes=set()
    for rig in rigs:
        for obj in list(rig.children):
            if obj.type=='MESH' and (obj.get('inspection_region') or obj.get('annotation_only')):
                old_meshes.add(obj.data)
                bpy.data.objects.remove(obj,do_unlink=True)
    for mesh in old_meshes:
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        if material.get('rolling_generated') and material.users==0:bpy.data.materials.remove(material)
    p=spec['appearance_parameters']
    clean_geometry={}
    def region_mesh(item,region,material,button_material=None):
        defect=item.get('defect')
        reusable=region in ('TOP','BRASS_FACE') and (not defect or defect['region']!=region)
        if reusable and region in clean_geometry:
            obj=clean_geometry[region].copy()
            scene.collection.objects.link(obj)
            obj.location=(item['x'],0,.505)
            obj.rotation_euler=(0,item['roll'],math.pi if item['flip'] else 0)
            obj.scale.y=item['length_scale']
            obj['flashlight_id']=item['index']
            obj['region_instance_id']=item['index']*4+track.REGION_KEYS.index(region)+1
            obj['defect_id']=0
            for index,slot in enumerate(obj.material_slots):
                slot.link='OBJECT'
                slot.material=button_material if index==2 else material
            return obj
        obj=(track.side(item,region,material) if region in ('BODY','TOP') else
             track.end_face(item,region,material,button_material))
        if reusable:clean_geometry[region]=obj
        return obj
    for item,rig in zip(spec['items'],rigs):
        existing=set(scene.objects)
        seed=item['material_seed']
        local_p=rolling_soiling.material_parameters(p,item)
        body=materials.plastic(local_p,seed,body=True,rib_spec=item)
        plastic=materials.plastic(local_p,seed)
        brass=materials.brass(local_p,seed)
        brass_face=materials.brass(local_p,seed,face=True)
        button=materials.button(local_p,seed)
        for mat in (body,plastic,brass,brass_face,button):rolling_soiling.apply(mat,item.get('normal_appearance'))
        region_mesh(item,'BODY',body);region_mesh(item,'TOP',brass)
        region_mesh(item,'BRASS_FACE',brass_face,button);region_mesh(item,'PLASTIC_FACE',plastic)
        for obj in set(scene.objects)-existing:
            obj.parent=rig;obj.matrix_parent_inverse=Matrix.Identity(4);obj.location=(0,0,0)
            obj.name=f'Random stream {item["index"]:02} | '+obj.get('inspection_region','aperture label')
            obj['inspection_flashlight']=True;obj['inspection_label_exclude']=False
            for collection in list(obj.users_collection):collection.objects.unlink(obj)
            next(iter(rig.users_collection)).objects.link(obj)
            for slot in obj.material_slots:
                if slot.material:slot.material['rolling_generated']=True
        rig['capture_shell_id']=item['index']
        rig['source_shell']=item['index']
    for obj in scene.objects:
        if obj.type=='MESH' and (obj.get('inspection_region') or obj.get('annotation_only')) and not obj.parent:
            obj['inspection_label_exclude']=True
    scene['rolling_randomized_recipe']=json.dumps(spec)
    scene['flashlight_recipe']=json.dumps(spec)
    scene.frame_set(scene.frame_current)
    return rigs,spec,spec


def randomize(scene,base,options,pass_index=0,recipe=None):
    rigs=rigs_in(scene)
    if not rigs:raise ValueError('Open the rolling shell workspace before randomizing.')
    spec=recipe if recipe is not None else make_recipe(base,rigs,options,pass_index)
    return build(scene,spec)
