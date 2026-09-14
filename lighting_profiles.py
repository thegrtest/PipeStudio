"""Lighting-only recipes, visually motivated by the inspection photographs."""
from scene_presets import SCENE_PRESETS

LIGHTING_ITEMS = [
    ('REFERENCE','Matched reference','Return lighting to the selected reference environment'),
    ('SOFT_BOX','Broad diffuse','Broad reflection and softer contrast'),
    ('LEFT_RAKE','Left grazing','Narrow source from the left reveals shallow dents and lips'),
    ('RIGHT_RAKE','Right grazing','Opposite grazing direction on the same specimen'),
    ('LOW_LIGHT','Dim inspection','Lower illumination with more visible sensor noise'),
    ('SHOULDER_GLARE','Shoulder glare','Narrow bright reflections with inspection-camera clipping'),
]
LIGHTING_IDS = tuple(item[0] for item in LIGHTING_ITEMS)
LIGHT_KEYS = ('key_power','key_angle','fill_power','rim_power','light_softness',
              'ambient_strength','exposure','color_cast','sensor_noise','tone_mapping',
              'light_azimuth','key_span')

def lighting_settings(environment, profile):
    if profile not in LIGHTING_IDS:
        raise ValueError('Unknown lighting profile: '+str(profile))
    base=SCENE_PRESETS[environment]
    result={key:base[key] for key in LIGHT_KEYS}
    machine=environment=='MACHINE'
    if profile=='SOFT_BOX':
        result.update(key_power=min(2500,base['key_power']*1.05),light_softness=2.6,
                      key_span=1.35,fill_power=110 if machine else 140,
                      key_angle=48,ambient_strength=.07 if machine else .19)
    elif profile in ('LEFT_RAKE','RIGHT_RAKE'):
        result.update(key_power=1700 if machine else 240,light_softness=.27,
                      key_span=.42,key_angle=35 if machine else 28,
                      light_azimuth=-52 if profile=='LEFT_RAKE' else 52,
                      fill_power=18 if machine else 36,rim_power=45,ambient_strength=.03 if machine else .09)
    elif profile=='LOW_LIGHT':
        result.update(key_power=max(30,base['key_power']*.42),fill_power=base['fill_power']*.50,
                      rim_power=base['rim_power']*.45,ambient_strength=base['ambient_strength']*.5,
                      exposure=-.45,sensor_noise=.022)
    elif profile=='SHOULDER_GLARE':
        result.update(key_power=2500 if machine else 440,light_softness=.20,key_span=.65 if machine else 1.15,
                      key_angle=45 if machine else 78,light_azimuth=20 if machine else 5,fill_power=28 if machine else 48,
                      ambient_strength=.04 if machine else .13,tone_mapping='STANDARD',exposure=.35)
    result['lighting_profile']=profile
    return result
