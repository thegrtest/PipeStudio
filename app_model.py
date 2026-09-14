"""Validated desktop settings and reproducible visual presets."""
from dataclasses import asdict
from geometry import PipeSpec
import math
from product_modes import PRODUCT_DEFAULTS, PRODUCT_LIMITS, ENVIRONMENTS, FLASHLIGHT_DEFAULTS

DEFAULTS={**asdict(PipeSpec()),'roughness':.34,'texture_strength':.12,'key_power':650.0,
          'key_angle':55.0,'fill_power':250.0,'exposure':0.0,'background':'GREY',
          'camera_yaw':22.0,'camera_elevation':16.0,'focus_blur':0.0,
          'resolution':1920,'samples':96,'wear':.18,'light_softness':1.5,
          'color_cast':0.0,'sensor_noise':0.0,'environment':'STUDIO','camera_zoom':1.0,
          'camera_shift_x':0.0,'camera_shift_y':0.0,'frame_aspect':1.6,
          'ambient_strength':.30,'brass_green':0.0,'rim_power':455.0,'tone_mapping':'AGX',
          'lighting_profile':'REFERENCE','light_azimuth':0.0,'key_span':1.0,'finish_marks':0.0,
          'oxide_amount':.38,'polish_amount':.42,**PRODUCT_DEFAULTS}

LIMITS={'length':(2,12),'radius':(.3,1.5),'end_ratio':(.35,1),'wall_ratio':(.03,.22),
        'taper_start':(0,.90),'taper_end':(.1,1),'position':(.03,.97),'angle':(0,360),
        'depth':(0,.25),'width':(.01,.18),'arc':(8,65),'irregularity':(0,.65),
        'seed':(0,2000000000),'roughness':(.06,.85),'texture_strength':(0,.7),
        'key_power':(30,2500),'key_angle':(5,175),'fill_power':(0,1500),'exposure':(-3,3),
        'camera_yaw':(-175,175),'camera_elevation':(0,70),'focus_blur':(0,1),
        'resolution':(320,2560),'samples':(8,256),'wear':(0,1),'light_softness':(.15,5),
        'color_cast':(-1,1),'sensor_noise':(0,.025),'body_taper':(0,.12),'shoulder_roundness':(0,1),
        'camera_zoom':(.6,2.5),'camera_shift_x':(-.5,.5),'camera_shift_y':(-.5,.5),
        'frame_aspect':(.8,2),'ambient_strength':(0,2),'brass_green':(0,1),'rim_power':(0,2500),
        'defect_rotation':(-75,75),'secondary_strength':(0,1),'light_azimuth':(-80,80),
        'key_span':(.25,2),'finish_marks':(0,1),'oxide_amount':(0,1),'polish_amount':(0,1),**PRODUCT_LIMITS}

PRESETS={
 'Soft studio': {'roughness':.34,'texture_strength':.12,'wear':.18,'key_power':650,
                 'fill_power':250,'key_angle':55,'light_softness':1.5,'exposure':0,
                 'background':'GREY','color_cast':0,'sensor_noise':0,'camera_yaw':22,'camera_elevation':16},
 'Inspection light': {'roughness':.43,'texture_strength':.20,'wear':.32,'key_power':850,
                 'fill_power':100,'key_angle':75,'light_softness':.45,'exposure':-.35,
                 'background':'GREEN','color_cast':.30,'sensor_noise':.004,'camera_yaw':0,'camera_elevation':5},
 'Grazing light': {'roughness':.30,'texture_strength':.12,'wear':.14,'key_power':850,
                 'fill_power':40,'key_angle':17,'light_softness':.35,'exposure':-.20,
                 'background':'DARK','color_cast':0,'sensor_noise':0,'camera_yaw':12,'camera_elevation':12},
 'Brushed brass': {'roughness':.48,'texture_strength':.28,'wear':.23,'key_power':950,
                 'fill_power':280,'key_angle':65,'light_softness':2.2,'exposure':.15,
                 'background':'GREY','color_cast':0,'sensor_noise':0,'camera_yaw':22,'camera_elevation':16}}


def validate_settings(values):
    if not isinstance(values,dict):
        raise ValueError('A preset must contain an object of settings.')
    mode=values.get('product_mode','PIPE')
    if mode not in ENVIRONMENTS:
        raise ValueError('Unknown product mode.')
    merged={**DEFAULTS,**(FLASHLIGHT_DEFAULTS if mode=='FLASHLIGHT' else {}),**{k:v for k,v in values.items() if k in DEFAULTS}}
    for key,(low,high) in LIMITS.items():
        value=merged[key]
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
            raise ValueError(f'{key} must be a finite number.')
        if not low-1e-6<=value<=high+1e-6:
            raise ValueError(f'{key} must be between {low} and {high}.')
        value=max(low,min(high,value))
        if key in ('flashlight_count','flashlight_index') and value!=int(value):
            raise ValueError(f'{key} must be an integer.')
        merged[key]=int(value) if key in ('seed','resolution','samples','flashlight_count','flashlight_index') else round(value,6)
    if merged['background'] not in ('GREY','DARK','GREEN'):
        raise ValueError('Unknown backdrop.')
    if merged['environment'] not in ENVIRONMENTS[mode]:
        raise ValueError('Unknown environment.')
    if merged['tone_mapping'] not in ('AGX','STANDARD'):
        raise ValueError('Unknown tone mapping.')
    if merged['lighting_profile'] not in ('REFERENCE','SOFT_BOX','LEFT_RAKE','RIGHT_RAKE','LOW_LIGHT','SHOULDER_GLARE'):
        raise ValueError('Unknown lighting profile.')
    if merged['flashlight_surface'] not in ('PLASTIC','METAL') or merged['flashlight_layout'] not in ('SINGLE','MIXED'):
        raise ValueError('Unknown flashlight surface or arrangement.')
    if merged['flashlight_region'] not in ('TOP','BODY','BRASS_FACE','PLASTIC_FACE') or merged['flashlight_camera'] not in ('FRONT_45','REAR_45','OVERHEAD','REFERENCE') or merged['flashlight_capture'] not in ('ALL','CURRENT'):
        raise ValueError('Unknown flashlight region or camera.')
    if merged['flashlight_variation'] not in ('VARIED','REFERENCE') or merged['flashlight_crops'] not in ('ON','OFF'):
        raise ValueError('Unknown capture variation or crop option.')
    if merged['flashlight_projection'] not in ('ORTHO','PERSP'):
        raise ValueError('Unknown inspection camera projection.')
    if merged['inspection_light_rig'] not in ('SEGMENTED','CONTINUOUS') or merged['inspection_track_finish'] not in ('DARK','METAL'):
        raise ValueError('Unknown shell inspection light rig or track finish.')
    if mode=='FLASHLIGHT':
        allowed=('NONE','DENT','SCRATCH','OPEN_CENTER','PROTRUDING_CRIMP','TWIST') if merged['environment']=='BUTTON_TRACK' else ('NONE','DENT','SCRATCH')
        if merged['defect'] not in allowed:
            raise ValueError('Flashlights support clean, dent and metal scratch.')
        if merged['defect']=='SCRATCH' and merged['flashlight_surface']!='METAL' and merged['environment']!='BUTTON_TRACK':
            raise ValueError('Scratches require the metal surface.')
        if merged['flashlight_index']>=merged['flashlight_count']:
            raise ValueError('Selected flashlight must be inside the row.')
    else:
        PipeSpec(**{k:merged[k] for k in PipeSpec.__dataclass_fields__}).validate()
    return merged


def front_angle(values):
    if values.get('product_mode')=='FLASHLIGHT':
        return (90+values.get('flashlight_roll',0))%360
    if values.get('environment')=='MACHINE':
        return (180+values['camera_yaw'])%360
    yaw=math.radians(values['camera_yaw']); elevation=math.radians(values['camera_elevation'])
    return math.degrees(math.atan2(math.sin(elevation),-math.cos(yaw)*math.cos(elevation)))%360
