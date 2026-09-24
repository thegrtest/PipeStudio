"""September 23 body-dent/crease transfer experiment using the existing renderer.

The supplied checkpoint montages are development references, not ground truth
labels. All training labels come from modeled geometry. No photo pixels enter
the renderer and this recipe does not claim improved real-world accuracy.
"""
from collections import Counter
import math

from app_model import front_angle, validate_settings
from domain_plan import (make_plan as base_plan, validate_domain_plan,
                         _settings, _schedule, _rng, _instance, _location)
from domain_profiles import SOFTNESS_MIX, sample_camera_softness, reference_frame, setup_dimensions
from eval_generation import fixture_parameters
from geometry import PipeSpec, radius_at
from capture_variation import parameters as background_parameters
from yolox_profile import CAPTURE_MIX, capture_settings

VERSION = 'body-gap-20260923-v3-visible'
TARGET_SETUP = 'INVERTED'


def target_instance(settings, kind, size, index, targeted, occupied=()):
    rng = _rng(settings['seed'], f'{VERSION}:geometry:{index}:{kind}')
    item = _instance(settings, kind, size, index, occupied=occupied, profile='yolox')
    if not targeted:
        item['gap_family'] = 'retained'
        return item
    spec = item['spec']
    # Most primary examples sit just above the shoulder, where the supplied
    # shallow pockets disappear against the darker body. Other sites prevent
    # the model learning one fixed defect position.
    hi = min(.75, settings['taper_start']-.04)
    lo = min(.57, hi-.14)
    position = rng.uniform(lo, hi) if rng.random()<.7 else rng.uniform(.34, hi)
    candidates = [(.30+i*.01) for i in range(65)
                  if all(abs(.30+i*.01-other['position'])>=.145 for other in occupied)]
    if any(abs(position-other['position'])<.14 for other in occupied):
        body_sites = [p for p in candidates if p<hi]
        if not body_sites: body_sites=candidates
        if not body_sites: raise ValueError('No separated surface site for target instance')
        position = rng.choice(body_sites)
    spec['position'] = position
    offset = rng.uniform(-28,28)
    if rng.random()<.15: offset=rng.choice((-1,1))*rng.uniform(43,64)
    spec['angle'] = (front_angle(settings)+offset)%360
    spec['irregularity'] = rng.uniform(.12,.38)
    spec['secondary_strength'] = rng.uniform(.15,.75)
    if kind=='DENT':
        depth,width = {'small':((.020,.050),(.012,.020)),
                       'medium':((.045,.095),(.021,.036)),
                       'large':((.095,.16),(.038,.052))}[size]
        spec.update(defect_style='DEFAULT',depth=rng.uniform(*depth),width=rng.uniform(*width),
                    defect_rotation=rng.uniform(-35,35))
        # Match axial and circumferential distances for shallow round/oval
        # pockets. Diameter and depth vary independently, not a deep crater.
        local_radius=radius_at(position,PipeSpec(**spec))
        spec['arc']=max(8,min(55,math.degrees(spec['width']*spec['length']/local_radius)*rng.uniform(.80,1.18)))
        item['gap_family']='shallow_round_body_dent'
        style=rng.choices(('DEFAULT','ELONGATED','DOUBLE'),(.70,.18,.12))[0]
        spec['defect_style']=style
        if style=='ELONGATED':
            spec['width']=max(.01,spec['width']*.78)
            item['gap_family']='shallow_oval_body_dent'
        elif style=='DOUBLE':item['gap_family']='paired_body_dimple'
    else:
        depth,width,arc = {'small':((.035,.075),(.017,.025),(10,18)),
                           'medium':((.070,.140),(.026,.042),(18,30)),
                           'large':((.130,.210),(.043,.060),(30,42))}[size]
        spec.update(defect_style='BODY_BUCKLE',depth=rng.uniform(*depth),
                    width=rng.uniform(*width),arc=rng.uniform(*arc),
                    defect_rotation=rng.uniform(-16,16))
        item['gap_family']='transverse_body_buckle'
        style=rng.choices(('BODY_BUCKLE','WRINKLED','SOFT_BUCKLE'),(.70,.15,.15))[0]
        spec['defect_style']=style
        if style!='BODY_BUCKLE':item['gap_family']='uneven_body_'+style.lower()
    spec=validate_settings({**settings,**spec})
    item['spec']={key:spec[key] for key in PipeSpec.__dataclass_fields__}
    item['region']=('body' if position<settings['taper_start'] else
                    'shoulder' if position<settings['taper_end'] else 'neck')
    item['source_feature_ids']=[VERSION+':'+item['gap_family']]
    return item


def make_plan(total=3200,seed=923000000,quality='full',preview=False):
    # A single square-camera environment, explicitly requested for this gap.
    if not isinstance(preview,bool): raise ValueError('Preview must be a boolean')
    if preview: total=320
    if isinstance(total,bool) or total<320 or total%160:
        raise ValueError('Body-gap total must be a multiple of 160, at least 320')
    plan=base_plan(total,seed,quality,profile='yolox')
    per_kind=total//2
    # 40% mixed; one quarter of those also repeat the primary class.
    expected_instances=total//2 + total//5 + total//20
    sizes={kind:_schedule(expected_instances,{'small':.45,'medium':.40,'large':.15},
                          _rng(seed,VERSION+':sizes:'+kind)) for kind in ('FOLD','DENT')}
    rows=[]
    for setup in (TARGET_SETUP,):
        originals=plan['samples']
        kinds=_schedule(len(originals),{'FOLD':.5,'DENT':.5},_rng(seed,VERSION+':classes:'+setup))
        schedules={}
        for kind in ('FOLD','DENT'):
            definitions={
                'finish':{'clean':.30,'handled':.35,'dirty':.35},
                'light':{'mild':.70,'stronger':.20,'stress':.10},
                'capture':CAPTURE_MIX, 'softness':SOFTNESS_MIX,
                'target':{True:.70,False:.30},
                'visibility':{'body_shadow':.60,'ordinary':.40},
                'multiplicity':{1:.60,2:.30,3:.10},
                'fixture':{'normal':.70,'reflective':.30},
                'split':{'train':.80,'val':.20},
            }
            schedules[kind]={key:_schedule(per_kind,weights,_rng(seed,f'{VERSION}:{setup}:{kind}:{key}'))
                             for key,weights in definitions.items()}
        for row,kind in zip(originals,kinds):
            choice={key:values.pop() for key,values in schedules[kind].items()}
            specimen_seed=row['settings']['seed']
            p=_settings(setup,specimen_seed,choice['light'],choice['finish'],quality)
            # This camera's references have a muted body with fine grain,
            # not the strong continuous burnished tracks in the first preview.
            # Keep finish variation independent of class and defect geometry.
            finish_rng=_rng(specimen_seed,VERSION+':muted-finish')
            rough={'clean':(.43,.53),'handled':(.48,.60),'dirty':(.53,.64)}[choice['finish']]
            p['roughness']=finish_rng.uniform(*rough)
            p['polish_amount']*=finish_rng.uniform(.30,.48)
            p['texture_strength']=max(p['texture_strength'],finish_rng.uniform(.45,.57))
            p['camera_softness']=sample_camera_softness(specimen_seed,choice['softness'])
            p=capture_settings(p,choice['capture'],specimen_seed)
            # Same visibility conditions for both labels and all finish states;
            # bright shoulder/background glints are retained as context.
            rng=_rng(specimen_seed,VERSION+':visibility')
            if choice['visibility']=='body_shadow':
                p['fill_power']*=rng.uniform(.68,.88)
                p['ambient_strength']*=rng.uniform(.78,.95)
                p['exposure']-=rng.uniform(.06,.18)
                p['sensor_noise']=min(.025,p['sensor_noise']*rng.uniform(1.02,1.16))
            p=validate_settings(p)
            instances=[]
            for i in range(choice['multiplicity']):
                ikind=kind if i!=1 else ('DENT' if kind=='FOLD' else 'FOLD')
                size=sizes[ikind].pop()
                target=choice['target'] if i==0 else _rng(specimen_seed,f'{VERSION}:secondary:{i}').random()<.70
                instances.append(target_instance(p,ikind,size,i,target,[_location(x) for x in instances]))
            p=validate_settings({**p,**instances[0]['spec']})
            row.update(sample_id=f'bodygap_{specimen_seed:010d}_{setup.lower()}',
                       setup=setup,
                       resolution_profile={**reference_frame(setup),
                           'expected_dimensions':list(setup_dimensions(setup,quick=quality=='quick')),
                           'quality':quality,'upscaled':False},
                       primary_kind=kind,scenario_id=setup.lower()+'_body_gap_'+kind.lower(),
                       split='test' if preview else choice['split'],settings=p,instances=instances,
                       severity=instances[0]['size_bin'],size_bin=instances[0]['size_bin'],
                       surface_condition=choice['finish'],lighting_regime=choice['light'],
                       lighting_profile=p['lighting_profile'],capture_condition=choice['capture'],
                       sampling_profile='body-gap',camera_softness_band=choice['softness'],
                       generation_revision=VERSION,gap_targeted=choice['target'],
                       gap_visibility=choice['visibility'],reflection_context=choice['fixture'],
                       fixture_parameters=fixture_parameters(specimen_seed,choice['fixture']))
            row['background_variation']=background_parameters(specimen_seed)
            row['specimen_id']=row['sample_id']
            row['source_feature_ids']=[VERSION]+[f for x in instances for f in x['source_feature_ids']]
            rows.append(row)
    assert all(not values for values in sizes.values())
    plan['samples']=rows
    plan.update(generation_revision=VERSION,preview=preview,
        generation_policy=dict(defects_only=True,allowed_defects=['FOLD','DENT'],preserved_sample_ids=[]),
        ratio_definition='INVERTED only; 50% Fold / 50% Dent primary; 40% mixed (10% total have three instances); 70% targeted body defects.',
        gap_reference_note='Checkpoint montages are visual development references only; predictions are not ground-truth annotations. No transfer gain measured.',
        expected_primary_counts=dict(Counter(r['primary_kind'] for r in rows)),
        expected_instance_counts=dict(Counter(i['kind'] for r in rows for i in r['instances'])),
        expected_setup_counts=dict(Counter(r['setup'] for r in rows)))
    return validate_domain_plan(plan)
