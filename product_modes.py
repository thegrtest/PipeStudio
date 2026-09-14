"""Product-specific choices shared by desktop, Blender and renderer validation."""
from shell_appearance import POLYMER_DEFAULTS, POLYMER_LIMITS, APPEARANCE_PRESETS
from shell_lighting import LIGHT_DEFAULTS, LIGHT_LIMITS, LIGHT_PRESETS
MODE_LABELS = {'PIPE': 'Tapered pipe', 'FLASHLIGHT': 'Flashlight'}
ENVIRONMENTS = {'PIPE': ('STUDIO', 'MACHINE', 'GODSLIGHT'), 'FLASHLIGHT': ('TRACK', 'TRACK_GRAZING', 'BUTTON_TRACK')}
PRODUCT_DEFAULTS = dict(product_mode='PIPE', flashlight_surface='PLASTIC', flashlight_layout='SINGLE',
                        flashlight_count=6, flashlight_index=2, flashlight_roll=0., battery_probability=.75,
                        flashlight_region='BODY',flashlight_camera='FRONT_45',flashlight_capture='ALL',flashlight_projection='PERSP',
                        flashlight_length_scale=1.,flashlight_reference_elevation=55.,
                        flashlight_variation='VARIED',flashlight_crops='ON',
                        crimp_twist=18.,crimp_fold_depth=.085,crimp_tightness=.85,crimp_opening=.15,crimp_lift=.08,crimp_spread=.26,dust_amount=.22,
                        body_twist=25.,body_twist_span=.65,**POLYMER_DEFAULTS,**LIGHT_DEFAULTS)
PRODUCT_LIMITS = dict(flashlight_count=(2,12), flashlight_index=(0,11), flashlight_roll=(-180,180), battery_probability=(0,1),
                     flashlight_length_scale=(.75,1.5),flashlight_reference_elevation=(35,70),
                     crimp_twist=(0,40),crimp_fold_depth=(.035,.14),crimp_tightness=(0,1),crimp_opening=(.005,.35),crimp_lift=(.005,.25),crimp_spread=(.1,.42),dust_amount=(0,1),
                     body_twist=(-140,140),body_twist_span=(.2,.9),**POLYMER_LIMITS,**LIGHT_LIMITS)
FLASHLIGHT_DEFAULTS = dict(product_mode='FLASHLIGHT',environment='TRACK',defect='DENT',angle=90.,
                          depth=.13,width=.075,arc=25.,position=.6,frame_aspect=1.5,
                          roughness=.43,texture_strength=.12,wear=.18,key_power=500.,fill_power=200.,
                          rim_power=300.,ambient_strength=.12,camera_zoom=1.,camera_shift_x=0.,camera_shift_y=0.,
                          exposure=0.,sensor_noise=0.,flashlight_surface='PLASTIC',flashlight_layout='SINGLE',
                          flashlight_count=6,flashlight_index=2,flashlight_roll=0.,battery_probability=.75)
FLASHLIGHT_PRESETS = {
    'Overhead inspection': dict(environment='TRACK',key_power=500.,fill_power=200.,rim_power=300.,exposure=0.),
    'Grazing inspection': dict(environment='TRACK_GRAZING',key_power=180.,fill_power=450.,rim_power=180.,exposure=0.),
    'Brass button track': dict(environment='BUTTON_TRACK',key_power=1500.,fill_power=145.,rim_power=1500.,
                              roughness=.27,texture_strength=.56,wear=.42,finish_marks=.65,oxide_amount=.48,polish_amount=.32,
                              light_softness=.25,key_span=.45,key_angle=45.,frame_aspect=2.,flashlight_camera='REFERENCE',flashlight_capture='ALL',
                              flashlight_projection='PERSP',
                              exposure=-.60,ambient_strength=.012,color_cast=.35,sensor_noise=.007,tone_mapping='STANDARD',
                              flashlight_layout='MIXED',defect='DENT'),
}
FLASHLIGHT_PRESETS['Brass button track'].update(APPEARANCE_PRESETS['REFERENCE'])
FLASHLIGHT_PRESETS['Brass button track'].update(LIGHT_PRESETS['PHOTO'])


def initial_settings(mode, defaults):
    return {**defaults, **(FLASHLIGHT_DEFAULTS if mode=='FLASHLIGHT' else {}), 'product_mode':mode}
