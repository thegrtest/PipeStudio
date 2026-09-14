"""Editable inspection light arrangements, separate from specimen recipes."""
LIGHT_DEFAULTS=dict(inspection_light_rig='SEGMENTED',inspection_light_distance=1.,inspection_track_finish='METAL')
LIGHT_LIMITS=dict(inspection_light_distance=(.45,1.6))
LIGHT_PRESETS={
    'PHOTO':dict(inspection_light_rig='CONTINUOUS',inspection_light_distance=1.,inspection_track_finish='DARK',
                 key_power=40.,rim_power=1700.,fill_power=145.,key_angle=40.35,key_span=.45,light_softness=.25,
                 ambient_strength=.012,exposure=-.60,color_cast=.35,tone_mapping='STANDARD'),
    'EARLIER':dict(inspection_light_rig='SEGMENTED',inspection_light_distance=1.,inspection_track_finish='METAL',
                   key_power=1500.,rim_power=1500.,fill_power=145.,key_angle=45.,key_span=.45,light_softness=.25,
                   ambient_strength=.012,exposure=-.60,color_cast=.35,tone_mapping='STANDARD'),
}
