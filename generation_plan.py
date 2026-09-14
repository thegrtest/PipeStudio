"""Build reproducible paired-light inspection challenges without starting Blender."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from app_model import validate_settings, front_angle
from lighting_profiles import LIGHTING_IDS, lighting_settings
from scene_presets import SCENE_PRESETS

ROOT=Path(__file__).resolve().parent
ARCHETYPES=(
    dict(name='clean',defect='NONE',style='DEFAULT',severity='clean',position=.62,depth=0,width=.025,arc=12,rotation=0,feature=None),
    dict(name='finish_marks',defect='NONE',style='DEFAULT',severity='appearance_only',position=.80,depth=0,width=.025,arc=12,rotation=0,feature=None),
    dict(name='shallow_dent',defect='DENT',style='DEFAULT',severity='subtle',position=.79,depth=.040,width=.017,arc=12,rotation=0,feature='dent_shallow_oval'),
    dict(name='axial_trough',defect='DENT',style='ELONGATED',severity='medium',position=.61,depth=.085,width=.046,arc=15,rotation=-8,feature='dent_axial_trough'),
    dict(name='clustered_dent',defect='DENT',style='DOUBLE',severity='severe',position=.86,depth=.15,width=.025,arc=20,rotation=18,feature='dent_cluster'),
    dict(name='oblique_fold',defect='FOLD',style='OBLIQUE',severity='medium',position=.82,depth=.12,width=.026,arc=24,rotation=38,feature='fold_rolled_lip'),
    dict(name='nested_fold',defect='FOLD',style='WRINKLED',severity='subtle',position=.89,depth=.065,width=.021,arc=24,rotation=66,feature='fold_nested_crease'),
    dict(name='converging_fold',defect='FOLD',style='BRANCHED',severity='severe',position=.86,depth=.20,width=.028,arc=30,rotation=68,feature='fold_converging_tracks'),
)

def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def make_plan(seed=42,specimens=8,environments=('MACHINE','GODSLIGHT'),quality='quick',lights=LIGHTING_IDS):
    if isinstance(specimens,bool) or not isinstance(specimens,int) or not 3<=specimens<=200:
        raise ValueError('specimens must be an integer between 3 and 200 per environment')
    if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<=1999990000:
        raise ValueError('seed must be an integer between 0 and 1999990000')
    if quality not in ('quick','full') or not environments or len(set(environments))!=len(environments):
        raise ValueError('Invalid quality or environments')
    if not lights or len(set(lights))!=len(lights) or any(x not in LIGHTING_IDS for x in lights):
        raise ValueError('Invalid lighting list')
    samples=[]
    for env_index,env in enumerate(environments):
        if env not in ('MACHINE','GODSLIGHT'):
            raise ValueError('Choose MACHINE or GODSLIGHT')
        for specimen_index in range(specimens):
            # Small requests still cover clean, dent, and fold.
            order=(0,2,5,1,3,4,6,7) if specimens<8 else tuple(range(8))
            archetype=ARCHETYPES[order[specimen_index%len(ARCHETYPES)]]
            specimen_seed=seed+env_index*1000+specimen_index
            rng=random.Random(specimen_seed)
            p=dict(SCENE_PRESETS[env])
            p.update(seed=specimen_seed,defect=archetype['defect'],defect_style=archetype['style'],
                depth=archetype['depth']*rng.uniform(.92,1.08),position=archetype['position']+rng.uniform(-.012,.012),
                width=archetype['width']*rng.uniform(.94,1.06),arc=archetype['arc']*rng.uniform(.95,1.05),
                defect_rotation=max(-75,min(75,archetype['rotation']+rng.uniform(-4,4))),
                secondary_strength=rng.uniform(.40,.75),irregularity=rng.uniform(.16,.36),
                roughness=max(.06,min(.85,p['roughness']+rng.uniform(-.035,.035))),
                body_taper=max(0,p['body_taper']+rng.uniform(-.008,.008)),
                end_ratio=p['end_ratio']+rng.uniform(-.012,.012),
                shoulder_roundness=p['shoulder_roundness']+rng.uniform(-.04,.06),
                camera_yaw=rng.uniform(-1.8,1.8),
                camera_elevation=p['camera_elevation']+rng.uniform(0,.6),
                finish_marks=rng.uniform(.15,.35),
                oxide_amount=max(0,min(1,p['oxide_amount']+rng.uniform(-.10,.10))),
                polish_amount=max(0,min(1,p['polish_amount']+rng.uniform(-.10,.10))),
                camera_shift_y=p['camera_shift_y']+rng.uniform(-.006,.006))
            if archetype['name']=='finish_marks':
                p.update(finish_marks=.90,wear=.68,texture_strength=.65,oxide_amount=.78)
            p['angle']=(front_angle(p)+rng.uniform(-16,16))%360
            if quality=='quick':
                p.update(resolution=960,samples=48)
            specimen_id=f'{env.lower()}_s{specimen_index:03d}'
            for light in lights:
                settings=validate_settings({**p,**lighting_settings(env,light)})
                sample_id=specimen_id+'_'+light.lower()
                samples.append({'sample_id':sample_id,'specimen_id':specimen_id,
                    'scenario_id':env.lower()+'_'+archetype['name'],'split':'test',
                    'lighting_profile':light,'severity':archetype['severity'],
                    'pair_role':'reference' if light=='REFERENCE' else 'lighting_variant',
                    'source_feature_ids':[archetype['feature']] if archetype['feature'] else [],
                    'settings':settings})
    catalog=ROOT/'verification'/'dataset-study-v3'/'feature_catalog.json'
    evidence=json.loads(catalog.read_text(encoding='utf-8')) if catalog.exists() else None
    return {'schema_version':1,'appearance_version':4,'seed':seed,'quality':quality,
        'purpose':'Synthetic lighting challenge; same specimen is repeated under each light.',
        'classes':{'0':'Fold','1':'Dent'},'specimens_per_environment':specimens,
        'environments':list(environments),'lighting_profiles':list(lights),
        'source_feature_catalog':evidence,
        'calibrated':False,'samples':samples}

def validate_plan(plan):
    if not isinstance(plan,dict) or plan.get('schema_version')!=1 or not plan.get('samples'):
        raise ValueError('Expected a non-empty schema_version 1 render plan')
    ids=set(); groups={}
    from geometry import PipeSpec
    # Geometry, camera and finish must stay fixed for paired lighting comparisons.
    stable_keys=tuple(PipeSpec.__dataclass_fields__)+('roughness','texture_strength','wear','finish_marks','oxide_amount','polish_amount',
        'environment','camera_yaw','camera_elevation','camera_zoom','camera_shift_x','camera_shift_y','focus_blur',
        'frame_aspect','resolution','brass_green')
    for sample in plan['samples']:
        name=sample.get('sample_id','')
        if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name) or name in ids:
            raise ValueError('Sample IDs must be unique safe lowercase names')
        ids.add(name)
        if sample.get('split') not in ('train','val','test') or not sample.get('specimen_id'):
            raise ValueError('Every sample needs a specimen_id and split')
        settings=validate_settings(sample['settings'])
        if sample.get('lighting_profile')!=settings['lighting_profile']:
            raise ValueError('Lighting metadata disagrees with saved settings: '+name)
        stable=tuple(settings[k] for k in stable_keys)+(sample['split'],)
        prior=groups.setdefault(sample['specimen_id'],stable)
        if stable!=prior:
            raise ValueError('Paired specimen geometry/camera/finish or split differs: '+sample['specimen_id'])
    return plan

def write_plan(plan,folder):
    validate_plan(plan)
    folder=Path(folder).resolve(); folder.mkdir(parents=True,exist_ok=True)
    path=folder/'render_plan.json'
    if path.exists() or (folder/'manifest.json').exists():
        raise FileExistsError('This output already contains a plan. Choose a new folder, or resume its existing plan.')
    path.write_text(json.dumps(plan,indent=2,allow_nan=False),encoding='utf-8')
    return path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--specimens',type=int,default=8,help='Per environment; each gets all six lights')
    parser.add_argument('--quality',choices=('quick','full'),default='quick')
    parser.add_argument('--environment',choices=('BOTH','MACHINE','GODSLIGHT'),default='BOTH')
    args=parser.parse_args()
    envs=('MACHINE','GODSLIGHT') if args.environment=='BOTH' else (args.environment,)
    plan=make_plan(args.seed,args.specimens,envs,args.quality)
    path=write_plan(plan,args.output)
    print(f'{len(plan["samples"])} images planned: {path}')

if __name__=='__main__':
    main()
