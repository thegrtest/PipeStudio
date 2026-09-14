"""Appearance-only recipes motivated by the source inspection image families."""
from scene_presets import SCENE_PRESETS
FINISH_ITEMS=[('REFERENCE','Matched inspection brass','Material for the selected reference photo'),
              ('DRAWN','Drawn and burnished','Longer bright bands and uneven axial machining'),
              ('MOTTLED','Mottled / handled','Patchier brown finish and scuffs'),
              ('SATIN','Satin brass','More diffuse inspection finish')]
FINISH_KEYS=('roughness','texture_strength','wear','finish_marks','brass_green','oxide_amount','polish_amount')

def finish_settings(environment,profile):
    if profile not in {x[0] for x in FINISH_ITEMS}:
        raise ValueError('Unknown brass finish')
    base=SCENE_PRESETS[environment]
    values={key:base[key] for key in FINISH_KEYS}
    if profile=='DRAWN':
        values.update(roughness=.32,texture_strength=.62,wear=.26,finish_marks=.22,
                      oxide_amount=.23,polish_amount=.68,brass_green=.55)
    elif profile=='MOTTLED':
        values.update(roughness=.48,texture_strength=.65,wear=.65,finish_marks=.80,
                      oxide_amount=.83,polish_amount=.33,brass_green=.78)
    elif profile=='SATIN':
        values.update(roughness=.52,texture_strength=.40,wear=.30,finish_marks=.18,
                      oxide_amount=.44,polish_amount=.18,brass_green=.65)
    return values
