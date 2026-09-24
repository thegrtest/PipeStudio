"""Small repeatable changes to the existing inverted inspection hardware.

No photographed pixels or artificial marks are added to the part. Parameters
are sampled independently of defect class and reset to absolute baselines.
"""
import random

VERSION='capture-background-1'


def parameters(seed):
    rng=random.Random(f'{VERSION}:{seed}')
    return dict(version=VERSION,offset_x=rng.uniform(-.045,.045),offset_z=rng.uniform(-.035,.035),
                jaw_gap=rng.uniform(-.04,.04),wheel_shift=rng.uniform(-.06,.06),
                brightness=rng.uniform(.88,1.12),roughness_offset=rng.uniform(-.035,.035),
                texture_scale=rng.uniform(.92,1.08),cool_tint=rng.uniform(-.025,.025))


def apply_variation(scene,params=None):
    import bpy
    defaults=dict(offset_x=0.,offset_z=0.,jaw_gap=0.,wheel_shift=0.,brightness=1.,
                  roughness_offset=0.,texture_scale=1.,cool_tint=0.)
    p={**defaults,**(params or {})};changed=[]
    bounds=dict(offset_x=.06,offset_z=.06,jaw_gap=.06,wheel_shift=.08,
                roughness_offset=.05,cool_tint=.04)
    if any(abs(p[key])>limit for key,limit in bounds.items()) or not .8<=p['brightness']<=1.2 or not .85<=p['texture_scale']<=1.15:
        raise ValueError('Capture background variation exceeds supported mild bounds')
    for obj in scene.objects:
        if not obj.name.startswith('PS_Capture_Inverse'):continue
        if 'variation_base_location' not in obj:obj['variation_base_location']=list(obj.location)
        x,y,z=obj['variation_base_location'];side=-1 if x<0 else 1
        if 'Backing' not in obj.name:
            x+=p['offset_x'];z+=p['offset_z']
            if 'Upper' in obj.name or 'Lip' in obj.name:x+=side*p['jaw_gap']
            if 'Wheel' in obj.name:z+=p['wheel_shift']
        obj.location=(x,y,z)
        if not obj.hide_render:changed.append(obj.name)
    for mat in bpy.data.materials:
        if not mat.name.startswith('PS_EnvMachine_Capture') or not mat.use_nodes:continue
        for node in mat.node_tree.nodes:
            if node.type=='VALTORGB':
                for index,element in enumerate(node.color_ramp.elements):
                    key=f'variation_color_{index}'
                    if key not in node:node[key]=list(element.color)
                    r,g,b,a=node[key]
                    element.color=(r*p['brightness']*(1-p['cool_tint']),g*p['brightness'],b*p['brightness']*(1+p['cool_tint']),a)
            if node.name=='Uneven fixture roughness':
                for name in ('To Min','To Max'):
                    key='eval_base_'+name.replace(' ','_')
                    baseline=node.get(key)
                    if baseline is None:
                        baseline=node.inputs[name].default_value;node[key]=baseline
                    scale=scene.get('capture_fixture_roughness_scale',1.)
                    node.inputs[name].default_value=max(.08,min(.98,baseline*scale+p['roughness_offset']))
            if node.type=='TEX_NOISE':
                if 'variation_base_scale' not in node:node['variation_base_scale']=node.inputs['Scale'].default_value
                node.inputs['Scale'].default_value=node['variation_base_scale']*p['texture_scale']
    bpy.context.view_layer.update()
    return dict(**p,objects=changed)
