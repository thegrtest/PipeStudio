"""Reproducible visual recipes for the inert brass/copper rolling assembly.

Scene units and inferred proportions, not engineering dimensions. Component
tracking and surface-defect class IDs deliberately have separate namespaces.
"""
from dataclasses import asdict
import math
import random

from geometry import PipeSpec

VERSION = 'assembly-track-v5'
DEFECT_CLASSES = ('dent', 'ding', 'scratch', 'deformity')
PART_CLASSES = ('shell', 'ferrule')
CONDITIONS = ('good',) + DEFECT_CLASSES
NATIVE_SIZE = (1920, 1200)
# Complete 40-specimen blocks: 10% good and 22.5% each diagnostic class.
# Start with one of each so the default 15-frame review covers every family.
SCHEDULE = CONDITIONS + ('good',)*3 + tuple(c for c in DEFECT_CLASSES for _ in range(8))
DEFECT_SETS = ('ALL', 'DENTS_FOLDS')
DENTS_FOLDS_SCHEDULE = ('dent','deformity')*4 + ('good',) + ('dent','deformity')*5 + ('good',)


def make_specimen(seed, condition=None, look='CAMERA_MATCHED', lighting='BALANCED', allowed_defects=None):
    from assembly_realism import LOOKS,LIGHTING_PRESETS
    if look not in LOOKS or lighting not in LIGHTING_PRESETS:raise ValueError('Unknown assembly look or lighting')
    rng = random.Random(seed)
    condition = condition or CONDITIONS[seed % len(CONDITIONS)]
    if condition not in CONDITIONS:
        raise ValueError('Unknown assembly condition: ' + condition)
    allowed=tuple(allowed_defects) if allowed_defects is not None else DEFECT_CLASSES
    if not allowed or any(k not in DEFECT_CLASSES for k in allowed):raise ValueError('Invalid allowed defects')
    if condition!='good' and condition not in allowed:raise ValueError('Condition excluded by defect selection')
    base = PipeSpec(length=6.6, radius=.62, end_ratio=.66, wall_ratio=.09,
                    taper_start=.77, taper_end=.87, body_taper=.016,
                    shoulder_roundness=.25, defect='NONE', seed=seed)
    clean = rng.random() < .30
    finish = dict(seed=seed, length=base.length, radius=base.radius,
                  product_mode='PIPE', roughness=rng.uniform(.24, .32),
                  texture_strength=rng.uniform(.30, .48),
                  wear=rng.uniform(.08, .18) if clean else rng.uniform(.20, .42),
                  finish_marks=rng.uniform(.06, .16) if clean else rng.uniform(.22, .52),
                  oxide_amount=rng.uniform(.18, .27) if clean else rng.uniform(.30, .45),
                  polish_amount=rng.uniform(.40, .65), brass_green=rng.uniform(0, .12))
    instances = []
    initial_roll = rng.uniform(-math.pi, math.pi)
    kinds = [] if condition == 'good' else [condition]
    if kinds and len(allowed)>1 and rng.random() < .35:
        kinds.append(rng.choice([c for c in allowed if c != condition]))
    # Seeded roll is independent of the condition. A defect remains fixed to
    # its specimen while successive camera frames expose different surfaces.
    for index, kind in enumerate(kinds):
        spec = asdict(base)
        # Camera-facing sector at the middle capture, including near-silhouette
        # cases. Subsequent frames can legitimately hide the same defect.
        angle = ((36 if look=='CAMERA_MATCHED' else 12) + rng.uniform(-48, 48) - math.degrees(initial_roll)) % 360
        small = rng.random() < .55
        spec.update(defect='DENT', position=rng.uniform(.16, .84), angle=angle,
                    irregularity=rng.uniform(.15, .55),
                    defect_rotation=rng.uniform(-65, 65),
                    secondary_strength=rng.uniform(.15, .85))
        if kind == 'dent':
            spec.update(depth=rng.uniform(.06, .16), width=rng.uniform(.035, .07) if small else rng.uniform(.07, .12),
                        arc=rng.uniform(15, 35), defect_style=rng.choice(('DEFAULT', 'DOUBLE', 'ELONGATED', 'SHALLOW_SWEEP')))
        elif kind == 'ding':
            spec.update(depth=rng.uniform(.06, .15), width=rng.uniform(.012, .025),
                        arc=rng.uniform(8, 14), defect_style=rng.choice(('DEFAULT', 'DOUBLE')))
        elif kind == 'deformity':
            spec.update(defect='FOLD', depth=rng.uniform(.09, .23), width=rng.uniform(.055, .12),
                        arc=rng.uniform(24, 50), defect_style=rng.choice(('SOFT_BUCKLE', 'AXIAL_PINCH', 'WRINKLED')))
        else:
            # Proxy is used only to refine the sampling grid. Actual scratch
            # is an independent thin, tapered groove with a matching support.
            spec.update(depth=.05, width=.07, arc=8, defect_style='AXIAL_PINCH')
        item = dict(instance_id=index, kind=kind, class_id=DEFECT_CLASSES.index(kind), spec=spec)
        if kind=='dent' and look in ('REFINED','CAMERA_MATCHED'):
            from assembly_dents import dent_detail
            item.update(dent_detail(seed,index,spec,base))
        if kind == 'scratch':
            item['scratch'] = dict(length=rng.uniform(.42, 1.30), width=rng.uniform(.026, .048),
                                   depth=rng.uniform(.008, .019), curvature=rng.uniform(-.07, .07))
        instances.append(item)
    # Environment randomness must not encode defect classes.
    env_rng = random.Random(seed ^ 0x592814)
    return dict(version=VERSION, look=look, lighting=lighting, specimen_id=f'assembly_{seed:010d}', seed=seed,
                condition=condition, base=asdict(base), finish=finish,
                clean_finish=clean, initial_roll=initial_roll, instances=instances,
                environment=dict(exposure=env_rng.uniform(-.22, .15),
                    light_scale=env_rng.uniform(.90, 1.12),
                    bar_balance=[env_rng.uniform(.92, 1.08) for _ in range(4)],
                    light_shift=env_rng.uniform(-.12, .12),
                    softness_px=env_rng.uniform(.35, .70),
                    noise=env_rng.uniform(.007, .012)))


def capture_pose(recipe, index, frames=3):
    if frames < 1 or not 0 <= index < frames:
        raise ValueError('Invalid capture index/count')
    # Down-track movement, no-slip nominal rolling. The closed brass end
    # stays tangent to the guide plane; X clearance does not randomize.
    travel = 0.0 if frames == 1 else (index / (frames - 1) - .5) * 6.0
    radius = recipe['base']['radius']
    return dict(travel=travel, roll=recipe['initial_roll'] + travel / radius,
                guide_clearance=0.0, frame_index=index)


def make_plan(count=15, seed=260915,look='CAMERA_MATCHED',lighting='BALANCED',defect_set='ALL'):
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError('Count must be a positive integer')
    if defect_set not in DEFECT_SETS:raise ValueError('Unknown defect set: '+defect_set)
    allowed=('dent','deformity') if defect_set=='DENTS_FOLDS' else DEFECT_CLASSES
    schedule=DENTS_FOLDS_SCHEDULE if defect_set=='DENTS_FOLDS' else SCHEDULE
    # Balance primary conditions over complete schedule blocks. Frames
    # from one specimen always share its split_group and physical finish.
    rows=[]
    for index in range(count):
        specimen_index=index // 3
        recipe=make_specimen(seed + specimen_index, schedule[specimen_index % len(schedule)],look,lighting,allowed)
        frame=index % 3
        companion_condition='good' if recipe['condition']=='good' else (allowed[(specimen_index+1)%2] if defect_set=='DENTS_FOLDS' else CONDITIONS[(specimen_index+2)%5])
        companion=make_specimen(seed+100000+specimen_index,companion_condition,look,lighting,allowed)
        rows.append(dict(sample_id=f"{recipe['specimen_id']}_f{frame:03d}",
                         split_group=recipe['specimen_id'], recipe=recipe,
                         companions=[companion],pose=capture_pose(recipe, frame)))
    return rows


def visible_box(binary, minimum=4):
    import numpy as np
    yy, xx = np.where(binary)
    if len(xx) < minimum:
        return None
    return [int(xx.min()), int(yy.min()), int(xx.max()-xx.min()+1), int(yy.max()-yy.min()+1)]


def yolo_line(class_id, box, width, height):
    x,y,w,h=box
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > width or y+h > height:
        raise ValueError('Annotation outside image')
    return f'{class_id} {(x+w/2)/width:.8f} {(y+h/2)/height:.8f} {w/width:.8f} {h/height:.8f}'
