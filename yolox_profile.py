"""Bounded nuisance sampling for the next YOLOX transfer experiment.

This is a candidate recipe, not an empirically optimal distribution. Keep the
baseline and real development evaluation fixed while comparing it.
"""
import random
from app_model import LIMITS, validate_settings

CAPTURE_MIX={'matched':.70,'focus_noise':.20,'framing_light':.10}


def capture_settings(settings,condition,seed):
    if condition not in CAPTURE_MIX: raise ValueError('Unknown capture condition')
    p=dict(settings)
    rng=random.Random(f'yolox-transfer-v1:{seed}:capture')
    if condition=='focus_noise':
        p['optical_blur']*=rng.uniform(1.10,1.35)
        p['sensor_noise']*=rng.uniform(1.15,1.60)
        p['highlight_scatter']*=rng.uniform(.85,1.10)
    elif condition=='framing_light':
        p['camera_zoom']*=rng.uniform(.97,1.03)
        p['camera_shift_x']+=rng.uniform(-.006,.006)
        p['camera_shift_y']+=rng.uniform(-.006,.006)
        p['camera_yaw']+=rng.uniform(-.6,.6)
        p['light_azimuth']+=rng.uniform(-5,5)
        p['exposure']+=rng.uniform(-.18,.18)
    for key,(low,high) in LIMITS.items():
        if key in p: p[key]=max(low,min(high,p[key]))
    return validate_settings(p)


def projected_sizes(box,width,height,input_sizes=(640,960)):
    """YOLOX letterbox scale (no crop/stretch); diagnostics never drop a label."""
    result={}
    for size in input_sizes:
        scale=size/max(width,height)
        short=min(box[2:])*scale
        result[str(size)]=dict(width_px=round(box[2]*scale,3),height_px=round(box[3]*scale,3),
                              short_side_px=round(short,3),below_4px=short<4,
                              below_8px=short<8)
    return result
