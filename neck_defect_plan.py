"""Targeted neck crescent / rolled-mouth recipe using shared capture + QA.

Class 1 follows the supplied real annotations. This deliberately targeted
recipe is opt-in; it does not change general fleet class/shape proportions.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import random

from app_model import validate_settings, front_angle
from capture_plan import capture_settings
from capture_variation import parameters as background_parameters
from domain_plan import validate_domain_plan
from geometry import PipeSpec

VERSION='neck-crescent-20260923-v3'


def make_plan(count=6,seed=923910000):
    if not isinstance(count,int) or count<6 or count%6:
        raise ValueError('Use a multiple of six for both cameras and all three variants.')
    rows=[]
    for index in range(count):
        setup=('UPRIGHT','FOREGROUND')[(index//3)%2]
        variant=index%3;part_seed=seed+index;rng=random.Random(part_seed)
        p=capture_settings(setup)
        p.update(seed=part_seed,samples=96,
            roughness=rng.uniform(.47,.54),oxide_amount=rng.uniform(.57,.70),
            polish_amount=rng.uniform(.11,.18),finish_marks=rng.uniform(.15,.25),
            key_power=p['key_power']*rng.uniform(.87,1.08),fill_power=rng.uniform(13,22),
            exposure=rng.uniform(-.34,-.19),camera_softness=rng.uniform(.05,.30),
            sensor_noise=rng.uniform(.016,.021),camera_shift_y=p['camera_shift_y']+rng.uniform(-.004,.004))
        is_rim=variant==2
        p.update(defect='DENT',defect_style='ROLLED_LIP' if is_rim else 'CRESCENT_CREASE',
            position=rng.uniform(.935,.943) if is_rim else rng.uniform(.868,.878),
            angle=front_angle(p)+(rng.uniform(-12,8) if is_rim else
                rng.uniform(32,46) if variant==0 else rng.uniform(-28,28)),
            depth=rng.uniform(.16,.21) if is_rim else rng.uniform(.055,.085),
            width=rng.uniform(.037,.042) if is_rim else rng.uniform(.017,.022),
            arc=rng.uniform(22,27) if is_rim else rng.uniform(11,15) if variant==0 else rng.uniform(17,22),
            defect_rotation=0 if is_rim else rng.uniform(-9,9),
            irregularity=rng.uniform(.12,.30),secondary_strength=rng.uniform(.45,.78))
        p=validate_settings(p)
        spec=asdict(PipeSpec(**{k:p[k] for k in PipeSpec.__dataclass_fields__}).validate())
        name=f'neck_{part_seed:010d}_{setup.lower()}'
        description=('Small crescent at neck base','Wider asymmetric crescent','Rolled mouth with connected neck crease')[variant]
        item=dict(instance_id='defect_00',kind='DENT',class_id=1,
                  size_bin='large' if is_rim else 'small' if variant==0 else 'medium',
                  region='mouth_neck' if is_rim else 'shoulder_neck',spec=spec,
                  source_feature_ids=['real_20260905_012931_neck_crescent'])
        rows.append(dict(sample_id=name,specimen_id=name,scenario_id=setup.lower()+'_neck_crescent',
            split='train',setup=setup,settings=p,instances=[item],primary_kind='DENT',
            size_bin=item['size_bin'],severity=item['size_bin'],lighting_profile=p['lighting_profile'],
            surface_condition='handled',lighting_regime='mild',review_scenario=description,
            generation_revision=VERSION,keep_visibility_controls=True,
            background_variation=background_parameters(part_seed)))
    return validate_domain_plan(dict(schema_version=1,seed=seed,preview=False,quality='full',
        generation_revision=VERSION,classes={'0':'Fold','1':'Dent','2':'Soap stain','3':'Oil stain'},
        calibrated=False,require_visible_defects=True,minimum_mask_pixels=8,
        purpose='Targeted neck defect supplement; real examples are development references only.',
        ratio_definition='Both square cameras equally represented; small/wider crescent and rolled mouth equally represented. All labels retain source class 1 Dent.',
        generation_policy=dict(defects_only=True,allowed_defects=['DENT']),
        expected_primary_counts={'DENT':count},expected_instance_counts={'DENT':count},
        expected_setup_counts=dict(Counter(r['setup'] for r in rows)),samples=rows))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--count',type=int,default=6)
    ap.add_argument('--seed',type=int,default=923910000);args=ap.parse_args()
    plan=make_plan(args.count,args.seed);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:json.dump(plan,handle,indent=2)
