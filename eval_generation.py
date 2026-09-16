"""Generation changes motivated by the September 14 real-image visual audit.

All choices are reproducible; class never enters the light/fixture streams.
The new recipe is a transfer hypothesis, not a measured accuracy improvement.
"""
import math
import random
from app_model import front_angle
from geometry import DENT_STYLES

VERSION = 'real-eval-20260914-v2'


def refine_slots(slots, seed, setup_index):
    rng = random.Random(f'{VERSION}:{seed}:{setup_index}:slots')
    folds = [slot for slot in slots if slot['primary']=='FOLD']
    styles = ['AXIAL_PINCH']*round(.50*len(folds)) + ['SOFT_BUCKLE']*round(.20*len(folds))
    styles += [DENT_STYLES[i%len(DENT_STYLES)] for i in range(len(folds)-len(styles))]
    rng.shuffle(styles)
    for slot,style in zip(folds,styles): slot['style']=style
    dents = [slot for slot in slots if slot['primary']=='DENT']
    styles = ['SHALLOW_SWEEP']*round(.45*len(dents))
    styles += [DENT_STYLES[i%len(DENT_STYLES)] for i in range(len(dents)-len(styles))]
    rng.shuffle(styles)
    for slot,style in zip(dents,styles): slot['style']=style
    # A quarter of each class's mixed specimens add a second occurrence of
    # that primary class. Keep total instance counts balanced across classes.
    for kind in ('FOLD','DENT','SOAP_STAIN','OIL_STAIN'):
        mixed = [slot for slot in slots if slot['primary']==kind and 'secondary' in slot]
        rng.shuffle(mixed)
        for slot in mixed[:len(mixed)//4]: slot['repeat_primary']=True


def choose_style(kind, rng):
    r=rng.random()
    if kind=='FOLD':
        return 'AXIAL_PINCH' if r<.50 else 'SOFT_BUCKLE' if r<.70 else rng.choice(DENT_STYLES)
    return 'SHALLOW_SWEEP' if r<.45 else rng.choice(DENT_STYLES)


def refine_geometry(spec, settings, kind, size, rng, occupied):
    """Use class-specific physical extents; a broad dent need not be deep."""
    style=spec['defect_style']
    if style=='SHALLOW_SWEEP':
        ranges={
            'small': ((.025,.045),(.038,.050),(12,19)),
            'medium': ((.030,.065),(.056,.085),(20,33)),
            'large': ((.040,.085),(.090,.115),(30,45)),
        }[size]
        spec.update(depth=rng.uniform(*ranges[0]),width=rng.uniform(*ranges[1]),
                    arc=rng.uniform(*ranges[2]),defect_rotation=rng.uniform(-20,20))
        if not occupied:
            spec['position']=rng.uniform(.40,min(.67,settings['taper_start']-.12))
        # Some broad deformation reaches the silhouette; it is still a dent.
        if rng.random()<.30:
            spec['angle']=(front_angle(settings)+rng.choice((-1,1))*rng.uniform(55,73))%360
    elif style=='SOFT_BUCKLE':
        ranges={'small':(.024,.048,.014,.020,8,13),
                'medium':(.045,.080,.018,.027,10,18),
                'large':(.075,.115,.025,.036,15,24)}[size]
        spec.update(depth=rng.uniform(*ranges[:2]),width=rng.uniform(*ranges[2:4]),
                    arc=rng.uniform(*ranges[4:]),defect_rotation=rng.uniform(-14,14))
        if not occupied:
            spec['position']=rng.uniform(settings['taper_start']+.012,settings['taper_end']+.012)
        if rng.random()<.55:
            spec['angle']=(front_angle(settings)+rng.choice((-1,1))*rng.uniform(58,76))%360
    elif kind=='FOLD' and style=='AXIAL_PINCH':
        # Favor short neck slits without making the whole mask vanish at 640.
        spec['width']*=.90
        spec['width']=max(.012,spec['width'])
        spec['defect_rotation']=rng.uniform(-12,12) if rng.random()<.9 else rng.uniform(-24,24)
    return spec


def fixture_parameters(seed, context):
    if context not in ('normal','reflective'): raise ValueError('Unknown reflection context')
    rng=random.Random(f'{VERSION}:{seed}:fixture')
    return dict(version=VERSION,context=context,
                light_scale=rng.uniform(1.10,1.50) if context=='reflective' else rng.uniform(.75,1.10),
                roughness_scale=rng.uniform(.70,.90) if context=='reflective' else rng.uniform(.92,1.12))


def apply_fixture_parameters(scene, parameters):
    """Adjust existing hardware, never place an unlabelled mark on the pipe.

    Absolute baselines prevent brightness/roughness accumulating between rows.
    Linked fixture lamps keep their existing receiver isolation from the pipe.
    """
    import bpy
    params=parameters or dict(light_scale=1.,roughness_scale=1.)
    light_scale=params['light_scale'];roughness_scale=params['roughness_scale']
    if not (.5<=light_scale<=1.8 and .6<=roughness_scale<=1.3):
        raise ValueError('Fixture nuisance parameters exceed supported bounds')
    changed=[]
    for obj in scene.objects:
        if obj.type=='LIGHT' and 'Fixture' in obj.name:
            base=obj.data.get('eval_base_energy')
            if base is None:
                base=float(obj.data.energy);obj.data['eval_base_energy']=base
            obj.data.energy=base*light_scale
            if not obj.hide_render:changed.append(obj.name)
    # All modeled inspection setups use this roughness node on their hardware.
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.name.startswith('PS_Env'):continue
        node=mat.node_tree.nodes.get('Uneven fixture roughness')
        if node is None:continue
        for name in ('To Min','To Max'):
            key='eval_base_'+name.replace(' ','_')
            base=node.get(key)
            if base is None:
                base=float(node.inputs[name].default_value);node[key]=base
            node.inputs[name].default_value=max(.08,min(.98,base*roughness_scale))
    bpy.context.view_layer.update()
    return dict(**params,fixture_lights=changed)
