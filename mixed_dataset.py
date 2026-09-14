"""Independent specimens, exact per-folder class totals, and balanced reference rigs."""
from collections import Counter
import json
from pathlib import Path
import random

from app_model import front_angle,validate_settings
from generation_plan import validate_plan,write_plan
from lighting_profiles import lighting_settings
from scene_presets import SCENE_PRESETS

ROOT=Path(__file__).resolve().parent
ENVIRONMENTS=('MACHINE','GODSLIGHT')
KINDS=('NONE','FOLD','DENT')
FOLD_STYLE_WEIGHTS={'FOLD':(0.18, 0.20, 0.16, 0.14, 0.16, 0.16)}
STYLES={'FOLD':('DEFAULT','ELONGATED','DOUBLE','OBLIQUE','WRINKLED','BRANCHED'),
        'DENT':('DEFAULT','ELONGATED','DOUBLE','OBLIQUE','WRINKLED')}
FEATURES={'FOLD':{'DEFAULT':'fold_rolled_lip','ELONGATED':'fold_rolled_lip','OBLIQUE':'fold_rolled_lip',
                  'WRINKLED':'fold_nested_crease','BRANCHED':'fold_converging_tracks'},
          'DENT':{'DEFAULT':'dent_shallow_oval','ELONGATED':'dent_axial_trough','DOUBLE':'dent_cluster',
                  'OBLIQUE':'dent_oblique_shoulder','WRINKLED':'dent_nested_neck'}}

def clamp(value,low,high):
    return max(low,min(high,value))

def specimen_settings(env,kind,severity,seed,light='REFERENCE'):
    rng=random.Random(seed);p=dict(SCENE_PRESETS[env])
    p.update(lighting_settings(env,light))
    p.update(seed=seed,defect=kind,defect_style=rng.choice(STYLES[kind]) if kind!='NONE' else 'DEFAULT',
             irregularity=rng.uniform(.10,.40),secondary_strength=rng.uniform(.30,.75),
             roughness=clamp(p['roughness']+rng.uniform(-.055,.055),.20,.70),
             texture_strength=clamp(p['texture_strength']+rng.uniform(-.06,.045),.24,.70),
             wear=clamp(p['wear']+rng.uniform(-.08,.12),0,1),
             oxide_amount=clamp(p['oxide_amount']+rng.uniform(-.13,.15),0,1),
             polish_amount=clamp(p['polish_amount']+rng.uniform(-.10,.13),0,1),
             finish_marks=rng.uniform(.12,.60),brass_green=clamp(p['brass_green']+rng.uniform(-.12,.05),0,1),
             body_taper=clamp(p['body_taper']+rng.uniform(-.006,.006),0,.12),
             end_ratio=p['end_ratio']+rng.uniform(-.015,.015),
             shoulder_roundness=clamp(p['shoulder_roundness']+rng.uniform(-.045,.075),0,1),
             camera_yaw=rng.uniform(-1.7,1.7),camera_elevation=p['camera_elevation']+rng.uniform(-.35,.50),
             camera_zoom=p['camera_zoom']+rng.uniform(-.018,.018),
             camera_shift_x=p['camera_shift_x']+rng.uniform(-.004,.004),
             camera_shift_y=p['camera_shift_y']+rng.uniform(-.005,.005),
             focus_blur=clamp(p['focus_blur']+rng.uniform(-.05,.025),0,1))
    # Most folds follow the neck/shoulder; dents also populate the visible body.
    region=rng.choices(('body','shoulder','neck'),weights=(20,45,35) if kind=='FOLD' else (50,35,15))[0]
    position={'body':rng.uniform(.37,.73),'shoulder':rng.uniform(.78,.865),'neck':rng.uniform(.89,.935)}[region]
    if kind=='NONE':
        p.update(depth=0,position=.6,width=.015,arc=12,defect_rotation=0)
        if rng.random()<.35:
            p.update(finish_marks=rng.uniform(.60,.90),oxide_amount=rng.uniform(.55,.80))
    else:
        # Small means both reduced footprint and shallow physical deformation.
        bounds={'small':((.024,.060) if kind=='FOLD' else (.018,.050),(.010,.018),(8,15)),
                'medium':((.065,.125),(.018,.032),(14,25)),
                'large':((.13,.21),(.027,.046),(23,35))}[severity]
        depth,width,arc=(rng.uniform(*limits) for limits in bounds)
        if kind=='FOLD':
            style=rng.choices(STYLES['FOLD'],weights=FOLD_STYLE_WEIGHTS['FOLD'],k=1)[0]
            p.update(defect_style=style)
            fold_roll=rng.random()
            if fold_roll < 0.20:
                rotation=rng.uniform(36,74)
            elif fold_roll < 0.40:
                rotation=rng.uniform(-74,-38)
            elif fold_roll < 0.58:
                rotation=rng.uniform(8,30)
            elif fold_roll < 0.76:
                rotation=rng.uniform(-30,-8)
            elif fold_roll < 0.90:
                rotation=rng.uniform(-12,12)
            else:
                rotation=rng.uniform(-55,55)
            if style=='OBLIQUE':
                rotation-=28
        else:
            rotation=rng.uniform(-55,55)
        p.update(position=position,depth=depth,width=width,arc=arc,
                 defect_rotation=clamp(rotation,-75,75))
    p['angle']=(front_angle(p)+rng.uniform(-32,32))%360
    # Small within-rig variation keeps the source environment recognizable.
    for key in ('key_power','fill_power','rim_power'):
        p[key]=clamp(p[key]*rng.uniform(.90,1.10),30 if key=='key_power' else 0,2500 if key!='fill_power' else 1500)
    p['light_azimuth']=clamp(p['light_azimuth']+rng.uniform(-5,5),-80,80)
    p['color_cast']=clamp(p['color_cast']+rng.uniform(-.045,.045),-1,1)
    p['sensor_noise']=clamp(p['sensor_noise']*rng.uniform(.85,1.12),0,.025)
    return validate_settings(p),region

def severity_schedule(count,rng):
    small=round(count*.35);medium=round(count*.45)
    values=['small']*small+['medium']*medium+['large']*(count-small-medium)
    rng.shuffle(values);return values

def make_mixed_plan(batch_index,counts,seed=20260911):
    if set(counts)!=set(KINDS) or any(isinstance(v,bool) or not isinstance(v,int) or v<0 for v in counts.values()) or sum(counts.values())!=500:
        raise ValueError('Provide nonnegative integer NONE/FOLD/DENT counts totaling 500.')
    if not isinstance(batch_index,int) or isinstance(batch_index,bool) or not 1<=batch_index<=4:
        raise ValueError('Batch index must be 1..4.')
    rng=random.Random(seed+batch_index*10000)
    first={k:v//2 for k,v in counts.items()}
    odd=[k for k in KINDS if counts[k]%2]
    if batch_index%2==0: odd.reverse()
    for kind in odd[:250-sum(first.values())]: first[kind]+=1
    allocations=[first,{k:counts[k]-first[k] for k in KINDS}]
    samples=[];index=0
    for env,allocation in zip(ENVIRONMENTS,allocations):
        lights=['REFERENCE']*150+['SOFT_BOX']*40+['LEFT_RAKE']*20+['RIGHT_RAKE']*20+['LOW_LIGHT']*10+['SHOULDER_GLARE']*10
        rng.shuffle(lights)
        for kind in KINDS:
            severities=['clean']*allocation[kind] if kind=='NONE' else severity_schedule(allocation[kind],rng)
            for severity in severities:
                sample_seed=seed+(batch_index-1)*500+index
                light=lights.pop();p,region=specimen_settings(env,kind,severity,sample_seed,light)
                specimen_id=f'b{batch_index:02d}_specimen_{index:04d}'
                samples.append({'sample_id':specimen_id,'specimen_id':specimen_id,'split':'test',
                    'scenario_id':env.lower()+'_'+kind.lower()+'_'+severity,'severity':severity,
                    'defect_region':region if kind!='NONE' else None,'lighting_profile':light,
                    'source_feature_ids':[FEATURES[kind][p['defect_style']]] if kind!='NONE' else [],
                    'settings':p})
                index+=1
    rng.shuffle(samples)
    # Sequential filenames reveal the shuffled order without creating class folders.
    for n,item in enumerate(samples,1): item['sample_id']=f'b{batch_index:02d}_{n:04d}'
    catalog=ROOT/'verification'/'dataset-study-v3'/'feature_catalog.json'
    plan={'schema_version':1,'appearance_version':4,'seed':seed,'quality':'full',
          'purpose':'Independent randomized tapered brass pipes; four mixed folders of 500 images.',
          'classes':{'0':'Fold','1':'Dent'},'environments':list(ENVIRONMENTS),'calibrated':False,
          'batch_index':batch_index,'expected_class_counts':counts,
          'expected_environment_counts':{'MACHINE':250,'GODSLIGHT':250},
          'require_visible_defects':True,'minimum_mask_pixels':8,
          'source_feature_catalog':json.loads(catalog.read_text()) if catalog.exists() else None,
          'samples':samples}
    validate_mixed_plan(plan);return plan

def validate_mixed_plan(plan):
    validate_plan(plan)
    samples=plan['samples']
    if len(samples)!=500 or Counter(s['settings']['defect'] for s in samples)!=plan['expected_class_counts']:
        raise ValueError('Class counts do not match the 500-image allocation.')
    if Counter(s['settings']['environment'] for s in samples)!={'MACHINE':250,'GODSLIGHT':250}:
        raise ValueError('Each batch needs 250 images per environment.')
    if len({s['settings']['seed'] for s in samples})!=500 or len({s['specimen_id'] for s in samples})!=500:
        raise ValueError('Each image must depict an independent seeded specimen.')
    for kind in ('FOLD','DENT'):
        defects=[s for s in samples if s['settings']['defect']==kind]
        if defects and not .30<=sum(s['severity']=='small' for s in defects)/len(defects)<=.40:
            raise ValueError('Small defects must make up roughly 35% of each defect class.')
    return plan

def write_dataset(root,counts,seed=20260911):
    root=Path(root).resolve()
    if root.exists() and any(root.iterdir()): raise FileExistsError('Choose a new empty output directory: '+str(root))
    root.mkdir(parents=True,exist_ok=True)
    plans=[]
    for batch in range(1,5):
        plans.append(write_plan(make_mixed_plan(batch,counts,seed),root/f'batch_{batch:02d}'/'all'))
    summary={'schema_version':1,'total_images':2000,'batch_count':4,'images_per_batch':500,
             'counts_per_batch':counts,'environments_per_batch':{'MACHINE':250,'GODSLIGHT':250},
             'plans':[str(p.relative_to(root)) for p in plans],'seed':seed,
             'quality':'Reference resolution: upright 1600x1250, GodsLight 1936x1216; 192 Cycles samples.',
             'small_defects':'Approximately 35% of each defect class have small footprints and shallow displacement.',
             'classes':{'0':'Fold','1':'Dent'},'good_labels':'Existing empty .txt file, never a missing label.'}
    (root/'dataset_request.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (root/'README.md').write_text(
        '# Synthetic tapered brass pipes\n\n'
        f'2,000 unique specimens in four shuffled folders of 500. Each folder contains {counts["NONE"]} good, '
        f'{counts["FOLD"]} folds and {counts["DENT"]} dents; 250 upright and 250 GodsLight images.\n\n'
        'Use batch_01/all/images and batch_01/all/labels (likewise batches 02–04). '
        'YOLO classes: 0 Fold, 1 Dent. Good images have empty matching .txt files. '
        'Masks, recipes, and provenance are retained alongside images and labels.\n\n'
        'About 35% of defective specimens are small/shallow, 45% medium, 20% large. '
        'Appearance, light, pose, and defect morphology vary with independent deterministic seeds. '
        'The four folders are delivery partitions; exported evaluation lists assign all images to test.\n\n'
        'Check progress.json for render progress and completion.json for final verified counts. '
        'These are synthetic images and geometric-support labels, not measured defect visibility.\n',encoding='utf-8')
    return plans

def make_preflight(seed=20262911):
    samples=[]
    cases=[('NONE','clean','REFERENCE'),('FOLD','small','REFERENCE'),('DENT','small','REFERENCE'),
           ('FOLD','small','LEFT_RAKE'),('DENT','small','RIGHT_RAKE'),('FOLD','medium','SOFT_BOX'),
           ('DENT','large','LOW_LIGHT'),('FOLD','large','SHOULDER_GLARE')]
    for env in ENVIRONMENTS:
        for kind,severity,light in cases:
            index=len(samples);p,region=specimen_settings(env,kind,severity,seed+index,light)
            name=f'preflight_{index:02d}_{env.lower()}_{kind.lower()}_{severity}'
            samples.append({'sample_id':name,'specimen_id':name,'split':'test','severity':severity,
                'scenario_id':env.lower()+'_'+kind.lower()+'_'+severity,'lighting_profile':light,'settings':p})
    return {'schema_version':1,'appearance_version':4,'seed':seed,'quality':'full','classes':{'0':'Fold','1':'Dent'},
            'purpose':'Full-resolution visibility and timing trial before the 2,000-image batch.',
            'require_visible_defects':True,'minimum_mask_pixels':8,'samples':samples}
