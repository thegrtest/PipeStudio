"""Reproducible September square-camera recipes and balanced defect sizes."""
import hashlib
import json
import random
from app_model import validate_settings
from scene_presets import SCENE_PRESETS

VIEWS=('UPRIGHT','FOREGROUND','INVERTED')
FOLD_STYLES=('DEFAULT', 'ELONGATED', 'DOUBLE', 'OBLIQUE', 'WRINKLED', 'BRANCHED')
FOLD_STYLE_WEIGHTS=(0.18, 0.20, 0.16, 0.14, 0.16, 0.16)
BASE={**SCENE_PRESETS['MACHINE'],'defect':'NONE','depth':0,'frame_aspect':1,
      'resolution':640,'samples':192,'camera_zoom':1.10,'camera_shift_x':-.274,
      'camera_shift_y':-.072,'camera_elevation':4,'end_ratio':.70,
      'taper_start':.79,'taper_end':.88,'body_taper':.075,
      'roughness':.49,'texture_strength':.57,'oxide_amount':.67,'polish_amount':.16,
      'wear':.47,'finish_marks':.22,'brass_green':.90,'key_power':2100,
      'fill_power':15,'rim_power':55,'ambient_strength':.035,
      'key_angle':65,'light_softness':.95,'key_span':.85,'color_cast':-.08,
      'sensor_noise':.019,'focus_blur':.65,'exposure':-.28}

def capture_settings(view):
    p={**BASE,'capture_view':view}
    if view=='FOREGROUND':
        p.update(camera_shift_x=-.245)
    if view=='INVERTED':
        p.update(camera_shift_x=-.014,camera_shift_y=.088,camera_elevation=0,
                 body_taper=.025,key_power=1750,fill_power=10,ambient_strength=.024)
    return validate_settings(p)


def _weighted_choice(rng, values, weights):
    total = sum(weights)
    threshold = rng.random() * total
    for value, weight in zip(values, weights):
        threshold -= weight
        if threshold <= 0:
            return value
    return values[-1]


def _sample_fold_rotation(rng, style):
    roll = rng.random()
    if roll < 0.20:
        angle = rng.uniform(36, 74)
    elif roll < 0.40:
        angle = rng.uniform(-74, -38)
    elif roll < 0.58:
        angle = rng.uniform(8, 30)
    elif roll < 0.76:
        angle = rng.uniform(-30, -8)
    elif roll < 0.90:
        angle = rng.uniform(-12, 12)
    else:
        angle = rng.uniform(-55, 55)
    if style == 'OBLIQUE':
        angle -= 28
    return max(-75.0, min(75.0, angle))

def recipe_digest():
    return hashlib.sha256(json.dumps([capture_settings(v) for v in VIEWS],sort_keys=True).encode()).hexdigest()

SIZE_RANGES={
    'small':dict(depth=(.035,.065),width=(.010,.017),arc=(8,13)),
    'medium':dict(depth=(.085,.14),width=(.019,.030),arc=(15,24)),
    'large':dict(depth=(.17,.24),width=(.031,.047),arc=(25,37)),
}

def make_capture_plan(phase='clean',seed=9112026,repeats=5):
    if phase not in ('clean','defects') or not 3<=repeats<=100:
        raise ValueError('Choose clean/defects and 3-100 repeats.')
    samples=[]
    for view_index,view in enumerate(VIEWS):
        # Clean images include normal finish variations, with empty labels.
        recipes=[('NONE','clean',i) for i in range(1 if phase=='clean' else repeats+1)]
        if phase=='defects':
            recipes += [(kind,size,i) for kind in ('DENT','FOLD') for size in SIZE_RANGES for i in range(repeats)]
        for number,(kind,size,repeat) in enumerate(recipes):
            part_seed=seed+view_index*10000+number
            rng=random.Random(part_seed)
            p={**capture_settings(view),'seed':part_seed,'defect':kind}
            if phase!='clean':
                p.update(roughness=p['roughness']+rng.uniform(-.025,.025),
                         oxide_amount=p['oxide_amount']+rng.uniform(-.055,.055),
                         polish_amount=p['polish_amount']+rng.uniform(-.035,.035),
                         finish_marks=rng.uniform(.14,.38),
                         camera_shift_x=p['camera_shift_x']+rng.uniform(-.006,.006),
                         camera_shift_y=p['camera_shift_y']+rng.uniform(-.004,.004),
                         key_power=p['key_power']*rng.uniform(.91,1.09),
                         fill_power=p['fill_power']*rng.uniform(.85,1.15),
                         exposure=p['exposure']+rng.uniform(-.07,.07),
                         sensor_noise=rng.uniform(.016,.022))
            if kind!='NONE':
                # Visible body / shoulder / neck proportions sampled in every size.
                region=('shoulder','neck','body','shoulder','neck')[repeat%5]
                position={'shoulder':(.805,.865),'neck':(.893,.93),'body':(.43,.76)}[region]
                style = _weighted_choice(rng, FOLD_STYLES, FOLD_STYLE_WEIGHTS) if kind=='FOLD' else rng.choice(('DEFAULT','ELONGATED','DOUBLE'))
                p.update({key:rng.uniform(*bounds) for key,bounds in SIZE_RANGES[size].items()})
                p.update(position=rng.uniform(*position),angle=rng.uniform(155,205),
                         irregularity=rng.uniform(.14,.40),secondary_strength=rng.uniform(.32,.70),
                         defect_style=style,
                         defect_rotation=_sample_fold_rotation(rng, style) if kind=='FOLD' else rng.uniform(-15,20))
            else:
                region='none'
            name=f'{view.lower()}_{kind.lower()}_{size}_{repeat:03d}'
            split='test' if phase=='clean' or repeat==repeats-1 else 'val' if repeat==repeats-2 else 'train'
            samples.append(dict(sample_id=name,specimen_id=name,scenario_id=view.lower()+'_'+kind.lower(),
                split=split,lighting_profile='REFERENCE',severity=size,size_bin=size,
                size_definition='Relative geometric footprint and depth; actual projected box size is in metadata.',
                defect_region=region,pair_role='independent',source_feature_ids=[],settings=validate_settings(p)))
    return dict(schema_version=1,appearance_version=4,seed=seed,quality='reference_640',
        purpose='Independent synthetic training starter matched to September inspection captures.',
        classes={'0':'Fold','1':'Dent'},calibrated=False,environments=['MACHINE'],capture_views=list(VIEWS),
        require_visible_defects=True,minimum_mask_pixels=8,recipe_sha256=recipe_digest(),
        workspace_settings=capture_settings('FOREGROUND'),samples=samples)
