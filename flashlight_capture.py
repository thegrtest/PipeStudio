"""Deterministic capture variation, separate from mesh/render code."""
import random
from app_model import validate_settings

STYLES=('DEFAULT','ELONGATED','DOUBLE','OBLIQUE','WRINKLED','BRANCHED')

def varied_settings(base,index):
    rng=random.Random(base['seed']+index*7919)
    p=dict(base)
    p.update(seed=base['seed']+index,defect_style=rng.choice(STYLES),position=rng.uniform(.08,.92),
             angle=rng.uniform(65,115),depth=base['depth']*rng.choice((.12,.25,.45,.7,1.0)),
             width=max(.01,min(.18,base['width']*rng.uniform(.45,1.8))),arc=rng.uniform(12,52),
             irregularity=rng.uniform(.08,.6),defect_rotation=rng.uniform(-55,55))
    p['crimp_opening']=max(.005,min(.35,base['crimp_opening']*rng.uniform(.3,1.7)))
    p['crimp_lift']=max(.005,min(.25,base['crimp_lift']*rng.uniform(.3,1.7)))
    p['crimp_spread']=max(.1,min(.42,base['crimp_spread']*rng.uniform(.75,1.25)))
    p['body_twist']=(rng.choice((-1,1))*max(2,min(25,abs(base['body_twist'])*rng.choice((.15,.25,.4,.6,.8))))
                     if abs(base['body_twist'])>1e-6 else 0.)
    p['body_twist_span']=rng.uniform(.35,.85)
    if base['flashlight_variation']=='VARIED':
        p['dust_amount']=min(1,base['dust_amount']*rng.uniform(.6,1.4))
        for key,spread,low,high in [('roughness',.08,.1,.65),('wear',.16,0,1),('finish_marks',.22,0,1),
                                  ('oxide_amount',.15,0,1),('polish_amount',.18,0,1),('exposure',.22,-3,3),('color_cast',.13,-1,1)]:
            p[key]=max(low,min(high,base[key]+rng.uniform(-spread,spread)))
        for key,high in [('key_power',2500),('fill_power',1500),('rim_power',2500)]:
            p[key]=max(30 if key=='key_power' else 0,min(high,base[key]*rng.uniform(.8,1.2)))
        p['flashlight_roll']=max(-180,min(180,base['flashlight_roll']+rng.uniform(-20,20)))
        p['camera_shift_x']=max(-.5,min(.5,base['camera_shift_x']+rng.uniform(-.012,.012)))
        p['camera_shift_y']=max(-.5,min(.5,base['camera_shift_y']+rng.uniform(-.012,.012)))
        p['sensor_noise']=min(.012,base['sensor_noise']*rng.uniform(.6,1.8))
        if base['environment']=='BUTTON_TRACK':
            # Keep the chosen polymer finish; diversify gently and retain zero/off.
            for key,low,high in [('plastic_roughness',.12,.7),('crimp_roughness',.12,.7)]:
                p[key]=max(low,min(high,base[key]+rng.uniform(-.025,.025)))
            for key in ('plastic_finish_variation','groove_polish','groove_residue','plastic_ink_wear'):
                p[key]=min(1,base[key]*rng.uniform(.85,1.15))
            if base['finish_marks']==0:p['finish_marks']=0.
    return validate_settings(p)
