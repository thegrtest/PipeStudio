"""Opt-in training supplement for the September 23 real-image evaluation gaps."""
from collections import Counter
from copy import deepcopy
import math

from app_model import front_angle, validate_settings
from capture_variation import parameters as background_parameters
from domain_plan import _settings, _rng, _schedule, validate_domain_plan
from domain_profiles import reference_frame, setup_dimensions, sample_camera_softness, SOFTNESS_MIX
from eval_generation import fixture_parameters
from geometry import PipeSpec, radius_at

VERSION = 'eval-gap-20260924-v1'
SETUPS = ('UPRIGHT', 'FOREGROUND', 'INVERTED')
# Exact 20-row blocks per view: 10% clean, 45% Fold, 45% Dent; 40% mixed.
SLOTS = [('NONE', 'clean', 0)] * 2 + [('DENT', 'round', 1)] * 3 + [('DENT', 'broad', 1)] * 2
SLOTS += [('FOLD', 'neck', 1)] * 3 + [('FOLD', 'body', 1)] * 2
SLOTS += [(kind, 'mixed', count) for kind in ('DENT', 'FOLD') for count in (2, 2, 3, 3)]


def instance(p, kind, family, index, rng, position=None, compact=False, edge=False):
    s = {k:p[k] for k in PipeSpec.__dataclass_fields__}
    s.update(defect=kind, irregularity=rng.uniform(.12,.35), secondary_strength=rng.uniform(.25,.70),
             angle=(front_angle(p) + rng.uniform(-30,30)) % 360, defect_rotation=rng.uniform(-8,8))
    if edge:
        s['angle'] = (front_angle(p)+rng.choice((-1,1))*rng.uniform(44,61)) % 360
    if family == 'neck':
        s.update(defect_style='AXIAL_PINCH', position=rng.uniform(.901,.948),
                 width=rng.uniform(.021,.033), arc=rng.uniform(8,12), depth=rng.uniform(.075,.14))
        region, size = 'neck', 'small'
    elif family == 'crescent':
        s.update(defect_style='CRESCENT_CREASE', position=rng.uniform(.868,.878),
                 width=rng.uniform(.017,.022), arc=rng.uniform(12,21), depth=rng.uniform(.060,.090))
        region, size = 'shoulder_neck', 'small'
    elif family == 'broad':
        s.update(defect_style='SHALLOW_SWEEP', position=rng.uniform(.40,.71),
                 width=rng.uniform(.037,.055), arc=rng.uniform(16,26), depth=rng.uniform(.035,.065))
        region, size = 'body', 'medium'
    elif kind == 'FOLD':
        s.update(defect_style='BODY_BUCKLE', position=rng.uniform(.43,.72),
                 width=rng.uniform(.012,.014) if compact else rng.uniform(.019,.036),
                 arc=rng.uniform(9,13) if compact else rng.uniform(14,27),
                 depth=rng.uniform(.065,.10) if compact else rng.uniform(.08,.16))
        region, size = 'body', 'small' if compact else 'medium'
    else:
        s.update(defect_style='DEFAULT', position=rng.uniform(.37,.73),
                 width=rng.uniform(.012,.014) if compact else rng.uniform(.012,.021),
                 depth=rng.uniform(.040,.070))
        local_radius=radius_at(s['position'], PipeSpec(**s))
        s['arc']=max(8,min(24,math.degrees(s['width']*s['length']/local_radius)*rng.uniform(.8,1.15)))
        region, size = 'body', 'small'
    if position is not None: s['position'] = position
    s = validate_settings({**p, **s})
    return dict(instance_id=f'defect_{index:02d}', kind=kind, class_id=0 if kind=='FOLD' else 1,
                size_bin=size, region=region, gap_family=family,
                spec={k:s[k] for k in PipeSpec.__dataclass_fields__},
                source_feature_ids=[VERSION+':'+family])


def make_plan(total=3000, seed=924100000, quality='full', preview=False):
    if isinstance(total,bool) or not isinstance(total,int) or total<60 or total%60 or total>1000000:
        raise ValueError('Eval-gap count must be a multiple of 60, from 60 to 1,000,000')
    if quality not in ('quick','full') or not isinstance(preview,bool):raise ValueError('Invalid quality/preview')
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=2000000000-total:
        raise ValueError('Seed must leave room for every unique specimen')
    rows=[];per_view=total//3
    for setup in SETUPS:
        slots=SLOTS*(per_view//20)
        _rng(seed,VERSION+':slots:'+setup).shuffle(slots)
        # Nuisance schedules do not depend on defect class or morphology.
        finish=_schedule(per_view,{'clean':.25,'handled':.45,'dirty':.30},_rng(seed,'finish:'+setup))
        light=_schedule(per_view,{'mild':.70,'stronger':.25,'stress':.05},_rng(seed,'light:'+setup))
        softness=_schedule(per_view,SOFTNESS_MIX,_rng(seed,'softness:'+setup))
        for offset,(kind,family,count) in enumerate(slots):
            specimen_seed=seed+len(rows);rng=_rng(specimen_seed,VERSION+':defects')
            p=_settings(setup,specimen_seed,light[offset],finish[offset],quality)
            material_rng=_rng(specimen_seed,VERSION+':finish')
            p.update(samples=96 if quality=='full' else 64,
                     roughness=material_rng.uniform(.46,.59),
                     oxide_amount=material_rng.uniform(.48,.74),
                     polish_amount=material_rng.uniform(.10,.20),
                     finish_marks=material_rng.uniform(.13,.32),
                     texture_strength=material_rng.uniform(.44,.58),
                     camera_softness=sample_camera_softness(specimen_seed,softness[offset]))
            p=validate_settings(p);items=[]
            if count==1:
                items=[instance(p,kind,family,0,rng,edge=rng.random()<.30)]
            elif count:
                other='FOLD' if kind=='DENT' else 'DENT'
                if rng.random()<.5:
                    # Compact adjacent pair: separate supports with 40-55px axial distance.
                    center=rng.uniform(.48,.62);distance=rng.uniform(.074,.089)
                    items=[instance(p,kind,'round' if kind=='DENT' else 'body',0,rng,center,True),
                           instance(p,other,'round' if other=='DENT' else 'body',1,rng,center+distance,True)]
                    if count==3:
                        items.append(instance(p,kind,'neck' if kind=='FOLD' else 'crescent',2,rng))
                else:
                    items=[instance(p,kind,'neck' if kind=='FOLD' else 'crescent',0,rng),
                           instance(p,other,'round' if other=='DENT' else 'body',1,rng,position=rng.uniform(.56,.67),edge=rng.random()<.25)]
                    if count==3:
                        items.append(instance(p,kind,'round' if kind=='DENT' else 'body',2,rng,position=rng.uniform(.30,.40)))
            if items:p=validate_settings({**p,**items[0]['spec']})
            name=f'evalgap_{specimen_seed:010d}_{setup.lower()}'
            row=dict(sample_id=name,specimen_id=name,scenario_id=setup.lower()+'_'+family,
                     split='train',setup=setup,settings=p,instances=items,primary_kind=kind,
                     size_bin=items[0]['size_bin'] if items else 'good',severity=items[0]['size_bin'] if items else 'good',
                     lighting_profile=p['lighting_profile'],lighting_regime=light[offset],surface_condition=finish[offset],
                     camera_softness_band=softness[offset],generation_revision=VERSION,sampling_profile='eval-gap',
                     review_scenario=family+' / '+kind.lower()+f' / {count} defects',target_family=family,
                     instance_spacing_policy='compact-separated-v1',
                     background_variation=background_parameters(specimen_seed),
                     fixture_parameters=fixture_parameters(specimen_seed,'reflective' if _rng(specimen_seed,'fixture').random()<.25 else 'normal'),
                     resolution_profile={**reference_frame(setup),'expected_dimensions':list(setup_dimensions(setup,quick=quality=='quick')),'quality':quality,'upscaled':False},
                     visibility_reposition_limit=3)
            rows.append(row)
    # Interleave cameras without correlating sample order with camera or defect class.
    _rng(seed,VERSION+':order').shuffle(rows)
    return recount(dict(schema_version=1,seed=seed,preview=preview,quality=quality,generation_revision=VERSION,
        classes={'0':'Fold','1':'Dent','2':'Soap stain','3':'Oil stain'},
        calibrated=False,require_visible_defects=True,minimum_mask_pixels=8,
        purpose='Training-only targeted supplement; development eval images are not copied into the dataset.',
        ratio_definition='Three square-camera views equally; 45% Fold / 45% Dent / 10% clean; 40% mixed (20% two and 20% three defects). No synthetic validation split.',
        generation_policy=dict(defects_only=False,allowed_defects=['FOLD','DENT']),samples=rows))


def recount(plan):
    rows=plan['samples']
    plan.update(expected_primary_counts=dict(Counter(r['primary_kind'] for r in rows)),
                expected_instance_counts=dict(Counter(i['kind'] for r in rows for i in r['instances'])),
                expected_setup_counts=dict(Counter(r['setup'] for r in rows)))
    return validate_domain_plan(plan)


def preview_plan(seed=924090000):
    plan=make_plan(300,seed);selected=[]
    for setup in SETUPS:
        candidates=[r for r in plan['samples'] if r['setup']==setup]
        cases=[('DENT','round',1),('DENT','broad',1),('FOLD','neck',1),
               ('FOLD','mixed',3),('DENT','mixed',2),('NONE','clean',0)]
        # Alternating assignment to two nodes must give BOTH a clean control.
        if setup=='FOREGROUND':cases.reverse()
        for kind,family,count in cases:
            row=deepcopy(next(r for r in candidates if r['primary_kind']==kind and r['target_family']==family and len(r['instances'])==count))
            row.update(keep_visibility_controls=True,split='test');selected.append(row)
    plan.update(samples=selected,preview=True,purpose='Development review only, excluded from production seeds.')
    return recount(plan)


def reposition(row, attempt):
    """Deterministic fallback after failed visibility QA; do not change classes or lighting."""
    from defect_visibility import reposition_eval_gap
    return reposition_eval_gap(row,attempt)
