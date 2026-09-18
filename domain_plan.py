"""Independent, balanced synthetic specimens across eight inspection setups.

Primary image allocation is 10% good and 22.5% for each defect class. The
reference recipe mixes 25% of defective images; YOLOX mixes 40%, including
some repeated primary instances. Reference photographs describe camera/shape targets;
they are neither copied into this plan nor used as render backgrounds.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import random

from app_model import DEFAULTS, LIMITS, front_angle, validate_settings
from capture_plan import capture_settings
from domain_profiles import (CAMERAS, camera_settings, setup_dimensions, reference_frame,
                             SOFTNESS_MIX, sample_camera_softness)
from geometry import DENT_STYLES, FOLD_STYLES, PipeSpec, _sample_fold_rotation
from scene_presets import SCENE_PRESETS


SETUPS = ('MACHINE', 'CAM2534', 'CAM5080', 'CAM7650', 'UPRIGHT',
          'FOREGROUND', 'INVERTED', 'STUDIO')
KINDS = ('FOLD', 'DENT', 'SOAP_STAIN', 'OIL_STAIN')
CLASS_IDS = {kind: index for index, kind in enumerate(KINDS)}
CLASSES = {'0': 'Fold', '1': 'Dent', '2': 'Soap stain', '3': 'Oil stain'}
GEOMETRY_KEYS = tuple(PipeSpec.__dataclass_fields__)
BODY_KEYS = ('length', 'radius', 'end_ratio', 'wall_ratio', 'taper_start',
             'taper_end', 'body_taper', 'shoulder_roundness', 'seed')
SIZE_RANGES = {
    'small': dict(depth=(.025, .065), width=(.014, .030), arc=(8, 18)),
    'medium': dict(depth=(.065, .125), width=(.026, .044), arc=(15, 27)),
    'large': dict(depth=(.13, .215), width=(.040, .066), arc=(23, 38)),
}
SPOT_RANGES = {
    'small': ((.008, .020), (5, 13)),
    'medium': ((.020, .045), (11, 24)),
    'large': ((.045, .075), (22, 40)),
}
PREVIEW_CASES = (
    dict(primary='NONE', size='clean', finish='clean'),
    dict(primary='FOLD', size='small', style='AXIAL_PINCH', strength=.15),
    dict(primary='FOLD', size='medium', style='AXIAL_PINCH', strength=.80),
    dict(primary='FOLD', size='medium', style='ELONGATED'),
    dict(primary='DENT', size='small', style='DEFAULT'),
    dict(primary='DENT', size='large', style='DOUBLE'),
    dict(primary='SOAP_STAIN', size='small', subtype='ring'),
    dict(primary='OIL_STAIN', size='small', subtype='acid_burn'),
    dict(primary='FOLD', size='small', style='AXIAL_PINCH', secondary='OIL_STAIN'),
    dict(primary='SOAP_STAIN', size='small', subtype='patch', secondary='DENT'),
)


def _rng(seed, stream):
    return random.Random(f'brass-domain-v1:{seed}:{stream}')


def _schedule(count, proportions, rng):
    """Largest-remainder allocation avoids dropping examples by rounding."""
    allocations = {key: int(count*share) for key, share in proportions.items()}
    remaining = count-sum(allocations.values())
    order = sorted(proportions, key=lambda key: (count*proportions[key]-allocations[key]), reverse=True)
    for key in order[:remaining]:
        allocations[key] += 1
    values = [key for key in proportions for _ in range(allocations[key])]
    rng.shuffle(values)
    return values


def _bounded(key, value):
    low, high = LIMITS[key]
    return max(low, min(high, value))


def _settings(setup, seed, regime, finish, quality):
    # Label and geometry choices never enter either nuisance RNG stream.
    rng = _rng(seed, 'camera-light')
    variation = .60 if regime == 'mild' else 1.4
    if setup in CAMERAS:
        session='AUG20' if _rng(seed,'acquisition-session').random()<.30 else 'AUG19'
        p = {**DEFAULTS, **SCENE_PRESETS['GODSLIGHT'],
             **camera_settings(setup, seed=seed, variation=variation,session=session)}
    else:
        p = dict(capture_settings(setup) if setup in ('UPRIGHT', 'FOREGROUND', 'INVERTED')
                 else SCENE_PRESETS[setup])
        if setup=='STUDIO':
            # The lighting studio still photographs the same short-shoulder
            # pipe as the inspection rigs, not the generic long-cone demo.
            p.update({key:SCENE_PRESETS['GODSLIGHT'][key] for key in BODY_KEYS if key!='seed'})
        for key, spread in (('key_power', .14), ('fill_power', .18), ('rim_power', .14),
                            ('ambient_strength', .15), ('light_softness', .10)):
            p[key] = _bounded(key, p[key]*(1+rng.uniform(-spread, spread)*variation))
        p['exposure'] += rng.uniform(-.16, .16)*variation
        p['color_cast'] += rng.uniform(-.035, .035)*variation
        p['key_angle'] += rng.uniform(-5, 5)*variation
        p['light_azimuth'] += rng.uniform(-5, 5)*variation
        p['camera_zoom'] *= rng.uniform(.988, 1.012)
        p['camera_shift_x'] += rng.uniform(-.005, .005)
        p['camera_shift_y'] += rng.uniform(-.004, .004)
        p['camera_yaw'] += rng.uniform(-1, 1)
        p['camera_elevation'] = max(0, p['camera_elevation']+rng.uniform(-.2, .3))
        p['focus_blur'] = _bounded('focus_blur', p['focus_blur']+rng.uniform(-.025, .025))
        p['sensor_noise'] = _bounded('sensor_noise', p['sensor_noise']*rng.uniform(.85, 1.12))
    p['lighting_profile'] = 'REFERENCE'
    if regime == 'stress':
        if rng.random() < .5:
            p['lighting_profile'] = 'LOW_LIGHT'
            p['exposure'] -= rng.uniform(.30, .65)
            p['fill_power'] *= rng.uniform(.40, .65)
        else:
            p['lighting_profile'] = rng.choice(('LEFT_RAKE', 'RIGHT_RAKE'))
            p['light_azimuth'] += (-1 if p['lighting_profile']=='LEFT_RAKE' else 1)*rng.uniform(15, 30)
            p['key_span'] = _bounded('key_span', p['key_span']*rng.uniform(.65, .85))
            p['fill_power'] *= rng.uniform(.55, .8)
    p.update(seed=seed, product_mode='PIPE', defect='NONE', depth=0,
             defect_style='DEFAULT', defect_rotation=0)
    # Shape dimensions vary only slightly and are shared by every instance.
    shape_rng = _rng(seed, 'body')
    p['end_ratio'] += shape_rng.uniform(-.008, .008)
    p['body_taper'] = _bounded('body_taper', p['body_taper']+shape_rng.uniform(-.004, .004))
    p['shoulder_roundness'] = _bounded('shoulder_roundness', p['shoulder_roundness']+shape_rng.uniform(-.025, .035))
    finish_rng = _rng(seed, 'normal-finish')
    ranges = {
        'clean': dict(finish_marks=(.06,.20), oxide_amount=(.10,.30), wear=(.10,.25),
                      polish_amount=(.42,.64), roughness=(.31,.44), texture_strength=(.24,.42)),
        'handled': dict(finish_marks=(.20,.44), oxide_amount=(.30,.56), wear=(.25,.45),
                        polish_amount=(.22,.43), roughness=(.38,.53), texture_strength=(.36,.55)),
        'dirty': dict(finish_marks=(.42,.72), oxide_amount=(.54,.79), wear=(.42,.68),
                      polish_amount=(.12,.30), roughness=(.43,.60), texture_strength=(.42,.63)),
    }[finish]
    p.update({key:finish_rng.uniform(*limits) for key,limits in ranges.items()})
    p['samples'] = 128 if quality=='full' else 64
    width,height=setup_dimensions(setup,quick=quality=='quick')
    p['resolution']=width
    # Keep the original aspect in quick mode; raster rounding accounts for the
    # sub-pixel height difference without changing the camera's field of view.
    frame=reference_frame(setup)
    p['frame_aspect']=frame['width']/frame['height']
    return validate_settings(p)


def _placement(settings, rng, kind, style=None, occupied=()):
    if style == 'AXIAL_PINCH':
        if rng.random()<.42:
            region='neck_rim'
            position=rng.uniform(max(.92,settings['taper_end']+.035),.97)
        else:
            region = 'shoulder_neck'
            position = rng.uniform(max(.82, settings['taper_start']), min(.90, settings['taper_end']+.02))
    else:
        region = rng.choices(('body','shoulder','neck'), weights=(30,45,25) if kind=='FOLD' else (55,30,15))[0]
        bounds = {'body':(.36,min(.73,settings['taper_start']-.025)),
                  'shoulder':(settings['taper_start']+.012, settings['taper_end']-.012),
                  'neck':(settings['taper_end']+.015, min(.95,settings['taper_end']+.060))}[region]
        position = rng.uniform(*bounds)
    angle = (front_angle(settings)+rng.uniform(-40,40))%360
    if kind=='FOLD' and not occupied and rng.random()<.20:
        angle=(front_angle(settings)+rng.choice((-1,1))*rng.uniform(58,77))%360
    # Secondary instances get their own visible location. Use a body site if
    # the short neck/shoulder is already occupied; avoid overlapping labels.
    for other in occupied:
        if abs(position-other['position']) < .12:
            region = 'body'
            candidates = [value for value in (.39,.52,.65,.73)
                          if all(abs(value-item['position'])>=.14 for item in occupied)]
            if not candidates:
                # Two existing defects can occupy every old anchor. Search
                # the usable body/neck instead of failing a three-instance run.
                candidates=[.24+i*.01 for i in range(74)
                            if all(abs(.24+i*.01-item['position'])>=.14 for item in occupied)]
            if not candidates:raise ValueError('No separated visible placement remains for another defect')
            position = rng.choice(candidates)+rng.uniform(-.012,.012)
            position=min(.97,position)
            region=('body' if position<settings['taper_start'] else
                    'shoulder' if position<settings['taper_end'] else 'neck')
            angle = (front_angle(settings)+rng.uniform(-35,35))%360
    return round(position,6), round(angle,6), region


def _instance(settings, kind, size, instance_index, style=None, strength=None, subtype=None, occupied=(), profile='reference'):
    rng = _rng(settings['seed'], f'instance-{instance_index}-{kind}')
    if profile=='yolox' and kind in ('FOLD','DENT') and style is None:
        from eval_generation import choose_style
        style=choose_style(kind,rng)
    elif kind=='FOLD':
        style = style or ('AXIAL_PINCH' if rng.random()<.6 else rng.choice(DENT_STYLES))
    elif kind=='DENT':
        style = style or rng.choice(DENT_STYLES)
    position,angle,region = _placement(settings,rng,kind,style,occupied)
    result = dict(instance_id=f'defect_{instance_index:02d}', kind=kind,
                  class_id=CLASS_IDS[kind], size_bin=size, region=region)
    if kind in ('FOLD','DENT'):
        spec = {key:settings[key] for key in GEOMETRY_KEYS}
        spec.update({key:rng.uniform(*bounds) for key,bounds in SIZE_RANGES[size].items()})
        # The new pinch is axial before rotation; legacy folds retain their
        # wider orientation distribution and original profile formulas.
        spec.update(defect=kind, defect_style=style, position=position, angle=angle,
                    defect_rotation=_sample_fold_rotation(rng,style) if kind=='FOLD' else rng.uniform(-60,60),
                    irregularity=rng.uniform(.12,.42),
                    secondary_strength=strength if strength is not None else rng.uniform(.1,.9))
        if kind=='FOLD' and style=='AXIAL_PINCH':
            # Narrow transverse extent approximates the short side of the
            # supplied axial folds; depth still changes with severity.
            spec['arc'] *= .86
            spec['arc'] = max(8,spec['arc'])
        if profile=='yolox':
            from eval_generation import refine_geometry
            spec=refine_geometry(spec,settings,kind,size,rng,occupied)
            result['region']=('body' if spec['position']<settings['taper_start'] else
                              'shoulder' if spec['position']<settings['taper_end'] else 'neck')
        valid = validate_settings({**settings,**spec})
        result['spec'] = {key:valid[key] for key in GEOMETRY_KEYS}
        result['source_feature_ids'] = ['aug19_axial_pinch_slit_and_unequal_lip' if style=='AXIAL_PINCH'
                                        else 'retained_fold_'+style.lower() if kind=='FOLD'
                                        else 'dent_'+style.lower()]
        if style in ('SHALLOW_SWEEP','SOFT_BUCKLE'):
            result['source_feature_ids']=['real_eval_20260914_'+style.lower()]
    else:
        if subtype is None:
            subtype = rng.choice(('ring','speckled_residue','patch')) if kind=='SOAP_STAIN' else rng.choice(('oil_pocket','acid_burn'))
        axial,angular = SPOT_RANGES[size]
        result['spot'] = dict(kind=kind, subtype=subtype, seed=rng.randrange(2000000000),
                              position=position, angle=angle, axial_size=rng.uniform(*axial),
                              angular_size=rng.uniform(*angular), strength=rng.uniform(.35,.82),
                              irregularity=rng.uniform(.25,.70), rotation=rng.uniform(-70,70))
        result['source_feature_ids'] = ['aug11_soap_residue_small_varied_spots' if kind=='SOAP_STAIN'
                                        else 'oil_pocket_and_acid_discoloration']
    return result


def _location(instance):
    value = instance.get('spec',instance.get('spot'))
    return {key:value[key] for key in ('position','angle')}


def _production_slots(per_setup, setup_index, seed, mixed_ratio=(1,4)):
    # Spread indivisible per-camera quotas around the eight setups. Global
    # class ratios stay exact and every camera still gets the same image count.
    counts = [{kind:per_setup*weight//40 for kind,weight in [('NONE',4)]+[(k,9) for k in KINDS]}
              for _ in SETUPS]
    cursor = 0
    for kind,weight in [('NONE',4)]+[(k,9) for k in KINDS]:
        remainder = per_setup*len(SETUPS)*weight//40-counts[0][kind]*len(SETUPS)
        for offset in range(remainder):
            counts[(cursor+offset)%len(SETUPS)][kind] += 1
        cursor += remainder
    slots = [dict(primary=kind) for kind,count in counts[setup_index].items() for _ in range(count)]
    candidates = {kind:[slot for slot in slots if slot['primary']==kind] for kind in KINDS}
    for kind,values in candidates.items():
        _rng(seed,f'mixed-slots-{setup_index}-{kind}').shuffle(values)
    prior_defective = sum(per_setup-count['NONE'] for count in counts[:setup_index])
    numerator,denominator=mixed_ratio
    mixed_count = (prior_defective+per_setup-counts[setup_index]['NONE'])*numerator//denominator-prior_defective*numerator//denominator
    for index in range(mixed_count):
        primary_index = (index+setup_index)%4
        # Every complete group of four gives one secondary of each class.
        # Rotate its derangement so all distinct class pairs occur. Remainder
        # pairs rotate over setups, balancing secondary counts globally too.
        shift = 1+(index//4+setup_index)%3 if index< mixed_count//4*4 else 1
        kind = KINDS[primary_index]
        slot = candidates[kind].pop()
        slot['secondary'] = KINDS[(primary_index+shift)%4]
    folds = [slot for slot in slots if slot['primary']=='FOLD']
    styles = ['AXIAL_PINCH']*round(.6*len(folds))
    styles += [DENT_STYLES[i%len(DENT_STYLES)] for i in range(len(folds)-len(styles))]
    _rng(seed,f'fold-styles-{setup_index}').shuffle(styles)
    for slot,style in zip(folds,styles):
        slot['style']=style
    _rng(seed,f'class-order-{setup_index}').shuffle(slots)
    return slots


def make_plan(total=3200, seed=20260914, quality='full', preview=False, profile='reference'):
    """Return a validated plan; preview=True creates 80 representative images.

    Full runs require a multiple of 40 for exact global primary counts and
    equal setup sizes. Per-camera class quotas differ by at most one image.
    Geometry instances carry complete PipeSpec dictionaries. Stain
    axial_size is a fractional pipe-length half-extent; angular_size is its
    circumferential half-extent in degrees. Each row is a unique specimen.
    """
    if profile not in ('reference','yolox'): raise ValueError('Unknown sampling profile')
    if not isinstance(preview,bool) or quality not in ('quick','full'):
        raise ValueError('Choose quick/full quality and a boolean preview flag.')
    if isinstance(total,bool) or not isinstance(total,int) or total<320 or total%40 or total>1000000:
        raise ValueError('total must be a multiple of 40 between 320 and 1000000.')
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=2000000000-(80 if preview else total):
        raise ValueError('seed must leave room for unique specimen seeds within 0..2000000000.')
    total = 80 if preview else total
    per_setup = total//len(SETUPS)
    slot_groups = [[dict(item) for item in PREVIEW_CASES] if preview
                   else _production_slots(per_setup,index,seed,(2,5) if profile=='yolox' else (1,4)) for index in range(len(SETUPS))]
    if profile=='yolox':
        from eval_generation import refine_slots
        for setup_index,slots in enumerate(slot_groups):
            if preview:
                slots[2].update(style='SOFT_BUCKLE')
                slots[3].update(primary='DENT',style='SHALLOW_SWEEP',size='large')
                slots[5].update(style='SHALLOW_SWEEP',secondary='SOAP_STAIN',repeat_primary=True)
            else:refine_slots(slots,seed,setup_index)
    instance_total = sum((slot['primary']!='NONE')+('secondary' in slot)+bool(slot.get('repeat_primary')) for group in slot_groups for slot in group)
    sizes = _schedule(instance_total, {'small':.45,'medium':.40,'large':.15}, _rng(seed,'instance-sizes'))
    rows=[]
    for setup_index,(setup,slots) in enumerate(zip(SETUPS,slot_groups)):
        lights = _schedule(per_setup,{'mild':.7,'stronger':.2,'stress':.1},_rng(seed,f'lighting-{setup}'))
        finishes = _schedule(per_setup,{'clean':.3,'handled':.35,'dirty':.35},_rng(seed,f'finish-{setup}'))
        conditions=['matched']*per_setup
        softness_bands=['near_reference']*per_setup
        # All environments and classes (including good parts) receive the
        # same slight-blur proportions, independently of light/finish choices.
        for kind in ('NONE',)+KINDS:
            indices=[i for i,slot in enumerate(slots) if slot['primary']==kind]
            for i,band in zip(indices,_schedule(len(indices),SOFTNESS_MIX,_rng(seed,f'softness-{setup}-{kind}'))):
                softness_bands[i]=band
        reflection_contexts=['normal']*per_setup
        if profile=='yolox':
            from yolox_profile import CAPTURE_MIX
            # Each image class sees the same nuisance proportions within a rig,
            # including good specimens. Avoid label-correlated render styles.
            for kind in ('NONE',)+KINDS:
                indices=[i for i,slot in enumerate(slots) if slot['primary']==kind]
                scheduled=_schedule(len(indices),CAPTURE_MIX,_rng(seed,f'capture-{setup}-{kind}'))
                for i,condition in zip(indices,scheduled): conditions[i]=condition
                # Sound parts and every defect class see the same finish,
                # light-regime and reflective-fixture proportions per camera.
                for target,proportions,stream in (
                    (lights,{'mild':.7,'stronger':.2,'stress':.1},'eval-light'),
                    (finishes,{'clean':.3,'handled':.35,'dirty':.35},'eval-finish'),
                    (reflection_contexts,{'normal':.7,'reflective':.3},'eval-fixture')):
                    for i,value in zip(indices,_schedule(len(indices),proportions,_rng(seed,f'{stream}-{setup}-{kind}'))):
                        target[i]=value
        for index,slot in enumerate(slots):
            specimen_seed = seed+setup_index*per_setup+index
            finish = slot.get('finish',finishes[index])
            settings = _settings(setup,specimen_seed,lights[index],finish,quality)
            settings['camera_softness']=sample_camera_softness(specimen_seed,softness_bands[index])
            if profile=='yolox':
                from yolox_profile import capture_settings as vary_capture
                settings=vary_capture(settings,conditions[index],specimen_seed)
            primary = slot['primary']
            instances=[]
            if primary!='NONE':
                scheduled_size = sizes.pop()
                size = slot.get('size',scheduled_size)
                instances.append(_instance(settings,primary,size,0,slot.get('style'),slot.get('strength'),slot.get('subtype'),profile=profile))
                if primary in ('FOLD','DENT'):
                    settings = validate_settings({**settings,**instances[0]['spec']})
                if slot.get('secondary'):
                    secondary_size = sizes.pop()
                    instances.append(_instance(settings,slot['secondary'],secondary_size,1,
                                               occupied=[_location(instances[0])],profile=profile))
                if slot.get('repeat_primary'):
                    instances.append(_instance(settings,primary,sizes.pop(),2,
                                               occupied=[_location(a) for a in instances],profile=profile))
            else:
                size='clean'
            name=f'domain_{specimen_seed:010d}_{setup.lower()}'
            frame=reference_frame(setup)
            resolution_profile={**frame,'expected_dimensions':list(setup_dimensions(setup,quick=quality=='quick')),
                                'quality':quality,'upscaled':False}
            features=[f'inspection_camera_{setup.lower()}']
            features += [feature for instance in instances for feature in instance['source_feature_ids']]
            rows.append(dict(sample_id=name,specimen_id=name,split='test' if preview else 'train',
                             scenario_id=setup.lower()+'_'+primary.lower(),setup=setup,primary_kind=primary,
                             severity=size,size_bin=size,surface_condition=finish,lighting_regime=lights[index],
                             lighting_profile=settings['lighting_profile'],pair_role='independent',
                             capture_condition=conditions[index],sampling_profile=profile,
                             camera_softness_band=softness_bands[index],
                             source_feature_ids=features,resolution_profile=resolution_profile,
                             settings=settings,instances=instances))
            if profile=='yolox':
                from eval_generation import VERSION,fixture_parameters
                rows[-1].update(generation_revision=VERSION,reflection_context=reflection_contexts[index],
                                fixture_parameters=fixture_parameters(specimen_seed,reflection_contexts[index]))
    # Interleaved rendering shows camera and defect diversity before completion.
    _rng(seed,'render-order').shuffle(rows)
    plan=dict(schema_version=1,appearance_version=13 if profile=='yolox' else 11,seed=seed,quality=quality,preview=preview,
              sampling_profile=profile,
              purpose='Independent synthetic brass inspection specimens with camera-specific light variation and mixed defects.',
              classes=CLASSES,environments=list(SETUPS),calibrated=False,
              require_visible_defects=True,minimum_mask_pixels=8,
              size_definition='Geometric/material extent bins; actual projected boxes and pixel counts are exported after rendering.',
              finish_definition='Normal clean/handled/dirty finish is sampled independently of defect class; localized SOAP/OIL marks are labeled.',
              camera_softness_definition='Additional native-reference Gaussian sigma: 70% 0-.12px, 20% .25-.50px, 10% .50-.75px; proportions rounded within each camera/class; combined in quadrature with existing optics before sensor noise; masks bypass blur.',
              ratio_definition='Primary image classes: 10% NONE, 22.5% per defect. '+('40%' if profile=='yolox' else '25%')+' of defective images add a distinct second class.'+
                  (' A quarter of mixed specimens per primary class add a repeated primary instance (rounded down per setup).' if profile=='yolox' else ''),
              expected_primary_counts=dict(Counter(row['primary_kind'] for row in rows)),
              expected_instance_counts=dict(Counter(instance['kind'] for row in rows for instance in row['instances'])),
              expected_setup_counts=dict(Counter(row['setup'] for row in rows)),
              samples=rows)
    return validate_domain_plan(plan)


def defects_only_plan(plan, preserved=0):
    """Replace only unrendered good specimens; committed rows stay byte-identical."""
    if isinstance(preserved,bool) or not isinstance(preserved,int) or not 0<=preserved<=len(plan['samples']):
        raise ValueError('Invalid committed prefix length')
    result=deepcopy(plan)
    rows=result['samples']
    counts=Counter(r['primary_kind'] for r in rows)
    for row in rows[preserved:]:
        if row['primary_kind']!='NONE': continue
        rng=_rng(row['settings']['seed'],'defects-only')
        kind=min(KINDS,key=lambda k:counts[k]); counts[kind]+=1
        size=rng.choices(('small','medium','large'),weights=(45,40,15))[0]
        settings=row['settings']
        profile=row.get('sampling_profile','reference') if row.get('generation_revision') else 'reference'
        instances=[_instance(settings,kind,size,0,profile=profile)]
        if kind in ('FOLD','DENT'):
            settings=validate_settings({**settings,**instances[0]['spec']})
        if rng.random()<.25:
            secondary=rng.choice([k for k in KINDS if k!=kind])
            secondary_size=rng.choices(('small','medium','large'),weights=(45,40,15))[0]
            instances.append(_instance(settings,secondary,secondary_size,1,occupied=[_location(instances[0])],profile=profile))
        row.update(primary_kind=kind,scenario_id=row['setup'].lower()+'_'+kind.lower(),
                   severity=size,size_bin=size,settings=settings,instances=instances,
                   source_feature_ids=[f"inspection_camera_{row['setup'].lower()}"]+
                       [f for instance in instances for f in instance['source_feature_ids']])
    result['generation_policy']=dict(defects_only=True,
        preserved_sample_ids=[r['sample_id'] for r in rows[:preserved]])
    result['ratio_definition']='All future images contain labeled defects; previously committed images are preserved.'
    result['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in rows))
    result['expected_instance_counts']=dict(Counter(a['kind'] for r in rows for a in r['instances']))
    result['expected_setup_counts']=dict(Counter(r['setup'] for r in rows))
    validate_domain_plan(result)
    allowed=plan.get('generation_policy',{}).get('allowed_defects')
    return restrict_defect_kinds(result,allowed,preserved) if allowed else result


def restrict_defect_kinds(plan, allowed, preserved=0):
    """Change future defect classes without changing committed rows or capture settings."""
    allowed=tuple(dict.fromkeys(allowed))
    if not allowed or any(kind not in KINDS for kind in allowed):
        raise ValueError('Allowed defects must be a nonempty subset of supported kinds')
    if isinstance(preserved,bool) or not isinstance(preserved,int) or not 0<=preserved<=len(plan['samples']):
        raise ValueError('Invalid committed prefix length')
    result=deepcopy(plan); rows=result['samples']
    # Balance replacements against the future rows which can remain unchanged.
    counts=Counter(r['primary_kind'] for r in rows[preserved:]
                   if all(i['kind'] in allowed for i in r['instances']))
    for row in rows[preserved:]:
        if all(i['kind'] in allowed for i in row['instances']): continue
        rng=_rng(row['settings']['seed'],'allowed-defects:'+','.join(allowed))
        kind=min(allowed,key=lambda k:counts[k]); counts[kind]+=1
        size=row['size_bin'] if row['size_bin'] in ('small','medium','large') else 'medium'
        profile=row.get('sampling_profile','reference') if row.get('generation_revision') else 'reference'
        settings=validate_settings({**row['settings'],'defect':'NONE'})
        instances=[_instance(settings,kind,size,0,profile=profile)]
        if kind in ('FOLD','DENT'): settings=validate_settings({**settings,**instances[0]['spec']})
        if len(row['instances'])>1 and len(allowed)>1:
            secondary=rng.choice([k for k in allowed if k!=kind])
            instances.append(_instance(settings,secondary,row['instances'][1]['size_bin'],1,
                                       occupied=[_location(instances[0])],profile=profile))
        row.update(primary_kind=kind,scenario_id=row['setup'].lower()+'_'+kind.lower(),
                   severity=size,size_bin=size,settings=settings,instances=instances,
                   source_feature_ids=[f"inspection_camera_{row['setup'].lower()}"]+
                       [f for instance in instances for f in instance['source_feature_ids']])
    result['generation_policy']={**result.get('generation_policy',{}),'allowed_defects':list(allowed),
                                'preserved_sample_ids':[r['sample_id'] for r in rows[:preserved]]}
    result['ratio_definition']='Future defect classes restricted to '+', '.join(allowed)+'; committed specimens preserved.'
    result['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in rows))
    result['expected_instance_counts']=dict(Counter(i['kind'] for r in rows for i in r['instances']))
    result['expected_setup_counts']=dict(Counter(r['setup'] for r in rows))
    return validate_domain_plan(result)


def validate_domain_plan(plan):
    from generation_plan import validate_plan
    validate_plan(plan)
    rows=plan['samples']
    actual_primary=Counter(row['primary_kind'] for row in rows)
    actual_instances=Counter(instance['kind'] for row in rows for instance in row['instances'])
    actual_setups=Counter(row['setup'] for row in rows)
    if any(actual!=plan[key] for actual,key in ((actual_primary,'expected_primary_counts'),
                                               (actual_instances,'expected_instance_counts'),
                                               (actual_setups,'expected_setup_counts'))):
        raise ValueError('Recorded allocation differs from the planned specimens.')
    policy=plan.get('generation_policy',{})
    if policy.get('defects_only') or policy.get('allowed_defects'):
        preserved=policy.get('preserved_sample_ids',[])
        ids={r['sample_id'] for r in rows}
        preserved_ids=set(preserved)
        if len(preserved)!=len(preserved_ids) or not preserved_ids.issubset(ids):
            raise ValueError('Preserved specimens must name unique rows in this plan')
        if policy.get('defects_only') and any(r['primary_kind']=='NONE' or not r['instances'] for r in rows if r['sample_id'] not in preserved_ids):
            raise ValueError('Defects-only generation cannot include future good specimens')
        allowed=policy.get('allowed_defects',KINDS)
        if not allowed or any(k not in KINDS for k in allowed): raise ValueError('Invalid allowed defect classes')
        if any(i['kind'] not in allowed for r in rows if r['sample_id'] not in preserved_ids for i in r['instances']):
            raise ValueError('Future specimen contains an excluded defect class')
    elif not plan.get('preview'):
        expected={kind:len(rows)*9//40 for kind in KINDS}
        expected['NONE']=len(rows)//10
        if actual_primary!=expected or actual_setups!={setup:len(rows)//8 for setup in SETUPS}:
            raise ValueError('Production primary counts and setups must remain exactly balanced.')
    if len({row['settings']['seed'] for row in rows})!=len(rows):
        raise ValueError('Each row must have an independent unique specimen seed.')
    for row in rows:
        if 'resolution_profile' in row:
            profile=row['resolution_profile']
            expected=setup_dimensions(row['setup'],quick=profile['quality']=='quick')
            actual=(row['settings']['resolution'],round(row['settings']['resolution']/row['settings']['frame_aspect']))
            if actual!=expected or tuple(profile['expected_dimensions'])!=expected:
                raise ValueError('Render dimensions differ from the reference resolution profile.')
        instances=row['instances']
        kinds=[instance['kind'] for instance in instances]
        if len(kinds)>3 or (len(kinds)==2 and len(set(kinds))!=2) or (len(kinds)==3 and
            (len(set(kinds))!=2 or kinds[2]!=kinds[0] or not row.get('generation_revision'))):
            raise ValueError('Mixed specimens need two distinct classes, with an optional repeated primary instance in revisioned plans.')
        if (row['primary_kind']=='NONE')!= (not kinds) or kinds and kinds[0]!=row['primary_kind']:
            raise ValueError('Primary image class disagrees with its instances.')
        if row['primary_kind'] in ('NONE','SOAP_STAIN','OIL_STAIN') and row['settings']['defect']!='NONE':
            raise ValueError('A stain or good primary must start with undeformed base geometry.')
        for instance in instances:
            if instance['class_id']!=CLASS_IDS[instance['kind']]:
                raise ValueError('Instance class ID is inconsistent.')
            if instance['kind'] in ('FOLD','DENT'):
                PipeSpec(**instance['spec']).validate()
                if any(instance['spec'][key]!=row['settings'][key] for key in BODY_KEYS):
                    raise ValueError('Every defect must use the shared specimen body and seed.')
                if instance['spec']['defect']!=instance['kind']:
                    raise ValueError('Instance geometry disagrees with its class.')
            else:
                spot=instance['spot']
                if (spot['kind']!=instance['kind'] or not .03<=spot['position']<=.97
                        or not 0<=spot['angle']<=360 or not .003<=spot['axial_size']<=.12
                        or not 3<=spot['angular_size']<=65 or not 0<=spot['strength']<=1):
                    raise ValueError('Stain parameters are outside supported surface coordinates.')
        if any(abs(_location(a)['position']-_location(b)['position'])<.12
               for i,a in enumerate(instances) for b in instances[i+1:]):
            raise ValueError('Mixed instances must have separately visible positions.')
    return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path,help='New render_plan.json path.')
    parser.add_argument('--total',type=int,default=3200)
    parser.add_argument('--seed',type=int,default=20260914)
    parser.add_argument('--quality',choices=('quick','full'),default='full')
    parser.add_argument('--preview',action='store_true')
    args=parser.parse_args()
    plan=make_plan(args.total,args.seed,args.quality,args.preview)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as target:
        json.dump(plan,target,indent=2,allow_nan=False)
    digest=hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps(dict(images=len(plan['samples']),output=str(args.output.resolve()),sha256=digest,
                          primary=plan['expected_primary_counts'],instances=plan['expected_instance_counts']),indent=2))


if __name__=='__main__':
    main()
