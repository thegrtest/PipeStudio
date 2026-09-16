"""Reproducible visual camera recipes from August inspection references.

These are manual visual estimates, not optical or radiometric calibrations.
The real photographs remain evaluation references, never render backplates.
No labels or defects are selected by this module. The baseline drawn-brass
finish is independent of class and can be overridden for clean/dirty examples.
"""
from copy import deepcopy
import math
import random

CAMERAS = ('CAM2534', 'CAM5080', 'CAM7650')
SOFTNESS_MIX = {'near_reference':.70, 'gentle':.20, 'slightly_soft':.10}
SOFTNESS_RANGES = {'near_reference':(0., .12), 'gentle':(.25, .50), 'slightly_soft':(.50, .75)}
FRAME_SIZES = {'CAM2534':(1936,1216),'CAM5080':(1936,1216),'CAM7650':(1936,1216),
               'UPRIGHT':(640,640),'FOREGROUND':(640,640),'INVERTED':(640,640),
               'MACHINE':(795,638),'STUDIO':(1936,1216)}
_FRAME_REFERENCES = {
    'CAM2534':'BrassModel11/all/2026-08-19GodsLight/images/20260819_170247_047_cam2534.jpg',
    'CAM5080':'BrassModel11/all/2026-08-19GodsLight/images/20260819_170221_830_cam5080.jpg',
    'CAM7650':'BrassModel11/all/2026-08-19GodsLight/images/20260819_170219_035_cam7650.jpg',
    'UPRIGHT':'TaperedPipeStudio/references/september-2026/reference_04.jpg',
    'FOREGROUND':'TaperedPipeStudio/references/september-2026/reference_01.jpg',
    'INVERTED':'TaperedPipeStudio/references/september-2026/reference_03.jpg',
    'MACHINE':'references/upright-inspection.png', 'STUDIO':None}


def reference_frame(setup):
    """Verified supplied-file dimensions and provenance, not sensor calibration.

    MACHINE uses the full supplied screenshot dimensions. Its UI strip is not
    rendered, and no unverified content crop is asserted as a camera format.
    """
    if setup not in FRAME_SIZES:
        raise ValueError(f'Unknown inspection setup: {setup}')
    width,height=FRAME_SIZES[setup]
    kind='screenshot_proxy' if setup=='MACHINE' else 'studio_proxy' if setup=='STUDIO' else 'reference_image'
    caveat=('Full screenshot dimensions, including its UI border; the synthetic image contains only the scene. Native camera dimensions are unknown.'
            if setup=='MACHINE' else 'No real studio camera reference; uses the GodsLight image dimensions as a proxy.'
            if setup=='STUDIO' else 'Matches supplied image dimensions; sensor and optics are not calibrated.')
    return dict(setup=setup,width=width,height=height,source_dimensions=[width,height],
                source_reference=_FRAME_REFERENCES[setup],source_kind=kind,
                source_reference_base='desktop' if setup in CAMERAS else 'repository_root' if setup!='STUDIO' else None,
                sensor_calibrated=False,caveat=caveat)


def setup_dimensions(setup, quick=False):
    """Native full output; quick output caps the longest edge without upscaling."""
    frame=reference_frame(setup)
    width,height=frame['width'],frame['height']
    scale=min(1.,960/max(width,height)) if quick else 1.
    return round(width*scale),round(height*scale)


def optical_reference_width(settings):
    """Reference pixel width used by the Gaussian lens response."""
    def value(key,default):
        return settings.get(key,default) if isinstance(settings,dict) else getattr(settings,key,default)
    environment=value('environment','STUDIO')
    if environment=='BUTTON_TRACK': return 1200
    if environment=='MACHINE':
        view=value('capture_view','ORIGINAL')
        return FRAME_SIZES[view][0] if view in ('UPRIGHT','FOREGROUND','INVERTED') else FRAME_SIZES['MACHINE'][0]
    return FRAME_SIZES['CAM2534'][0]

CAMERA_ITEMS = [('ORIGINAL', 'Original camera', 'Existing environment camera'),
                ('CAM2534', '2534 / left-facing', 'Olive enclosure, holder on right'),
                ('CAM5080', '5080 / bright', 'Bright green enclosure, holder on left'),
                ('CAM7650', '7650 / dark', 'Low framing against dark machinery')]

_SHARED = dict(environment='GODSLIGHT', capture_view='ORIGINAL',
               length=8.0, radius=.90, end_ratio=.68, body_taper=.040,
               taper_start=.80, taper_end=.88, shoulder_roundness=.18,
               wall_ratio=.045, resolution=1936, frame_aspect=1936/1216, camera_yaw=.7,
               camera_elevation=.5, background='GREEN', tone_mapping='STANDARD',
               optical_blur=1.0, highlight_scatter=1.0,
               lighting_profile='REFERENCE', light_azimuth=0.0,
               roughness=.51,texture_strength=.62,oxide_amount=.54,
               polish_amount=.20,finish_marks=.36,wear=.39,brass_green=.90)

_RECIPES = {
 'CAM2534': dict(roll_degrees=180.0, mouth_side='left', holder_side='right',
     background='olive', expected_center=(.588,.300),
     settings=dict(camera_zoom=.654,camera_shift_x=-.088,camera_shift_y=-.125,
         key_power=420.,key_angle=67.,fill_power=76.,rim_power=38.,
         key_span=.55,light_softness=1.55,ambient_strength=.16,
         exposure=-.10,color_cast=.25,sensor_noise=.009,focus_blur=.82)),
 'CAM5080': dict(roll_degrees=0.0, mouth_side='right', holder_side='left',
     background='bright_green', expected_center=(.465,.556),
     settings=dict(camera_zoom=.835,camera_shift_x=.035,camera_shift_y=.035,
         key_power=280.,key_angle=78.,fill_power=36.,rim_power=38.,
         key_span=.65,light_softness=1.8,ambient_strength=.14,
         exposure=-.04,color_cast=.32,sensor_noise=.011,focus_blur=.80)),
 'CAM7650': dict(roll_degrees=0.0, mouth_side='right', holder_side='left',
     background='dark_green', expected_center=(.567,.834),
     settings=dict(camera_zoom=.842,camera_shift_x=-.067,camera_shift_y=.210,
         key_power=340.,key_angle=67.,fill_power=86.,rim_power=30.,
         key_span=.43,light_softness=1.15,ambient_strength=.13,
         exposure=-.24,color_cast=.25,sensor_noise=.013,focus_blur=.81))}


def camera_recipe(camera):
    """Return independent metadata and baseline settings for one named camera."""
    if camera not in _RECIPES:
        raise ValueError(f'Unknown inspection camera: {camera}')
    recipe = deepcopy(_RECIPES[camera])
    recipe['settings'] = {**_SHARED, **recipe['settings'], 'inspection_camera':camera}
    return recipe


def camera_settings(camera, seed=0, variation=0.0, session='AUG19'):
    """Visual baseline plus mild seeded nuisance variation, independent of labels.

    variation=0 is the baseline; 1 spans typical exposure/illumination changes.
    Values up to 2 provide stress examples without changing which rig is shown.
    The same specimen can be rendered with multiple camera/lighting settings.
    """
    if not isinstance(variation,(int,float)) or not math.isfinite(variation) or not 0<=variation<=2:
        raise ValueError('variation must be finite and between 0 and 2')
    p = camera_recipe(camera)['settings']
    if session not in ('AUG19','AUG20'):raise ValueError('Unknown capture session.')
    p['capture_session']=session
    if session=='AUG20' and camera=='CAM5080':p['camera_shift_y']+=.120
    rng = random.Random(f'inspection-camera-v1:{camera}:{seed}')
    def jitter(extent): return rng.uniform(-extent, extent)*variation
    for name, extent in (('key_power',.17),('fill_power',.22),('rim_power',.18),
                         ('ambient_strength',.20),('light_softness',.12),('key_span',.09)):
        p[name] *= 1+jitter(extent)
    p['exposure'] += jitter(.20)
    p['color_cast'] += jitter(.055)
    p['key_angle'] += jitter(6)
    p['light_azimuth'] += jitter(7)
    p['camera_yaw'] += jitter(.8)
    p['camera_elevation'] = max(0,p['camera_elevation']+jitter(.30))
    p['camera_zoom'] *= 1+jitter(.018)
    p['camera_shift_x'] += jitter(.008)
    p['camera_shift_y'] += jitter(.006)
    p['focus_blur'] += jitter(.025)
    p['sensor_noise'] *= 1+jitter(.28)
    p['optical_blur'] = 1+jitter(.28)
    p['highlight_scatter'] = 1+jitter(.30)
    return p


def inspection_light_positions(settings):
    """Physical lamp placement, including effective nuisance-angle controls.

    The real body is brightest above its midline. A frontal fill instead made
    a conspicuous central reflection band. The elevation estimates come from
    development-frame brightness profiles, not measured lamp coordinates.
    """
    def value(key,default):
        return settings.get(key,default) if isinstance(settings,dict) else getattr(settings,key,default)
    camera=value('inspection_camera','CAM2534')
    recipe=camera_recipe(camera)
    side=-1 if camera=='CAM2534' else 1
    shoulder=value('length',8.)*((value('taper_start',.8)+value('taper_end',.88))/2-.5)
    key_angle=value('key_angle',recipe['settings']['key_angle'])
    azimuth=value('light_azimuth',0.)
    angle=math.radians(key_angle-67)
    y,z=-4.6,side*(4.5+2*math.sin(angle))
    rotation=math.radians(side*azimuth)
    key=(shoulder+7.0,y*math.cos(rotation)-z*math.sin(rotation),y*math.sin(rotation)+z*math.cos(rotation))
    elevation=(65 if camera=='CAM7650' else 55)+.5*(key_angle-recipe['settings']['key_angle'])+.5*azimuth
    elevation=math.radians(max(15,min(85,elevation)))
    fill=(0.,-6*math.cos(elevation),side*6*math.sin(elevation))
    return dict(key=key,key_target=(shoulder,0.,0.),fill=fill,fill_target=(0.,0.,0.))


def optical_response(settings):
    """Pure, bounded beauty-image response; diagnostic masks bypass this later."""
    def value(key, default):
        return settings.get(key,default) if isinstance(settings,dict) else getattr(settings,key,default)
    environment=value('environment','STUDIO')
    camera=value('inspection_camera','ORIGINAL')
    sigma=.50 if environment=='MACHINE' else .55
    scatter=.055 if environment=='MACHINE' else .035
    threshold=2.5
    if environment=='GODSLIGHT' and camera in CAMERAS:
        sigma={'CAM2534':.70,'CAM5080':.85,'CAM7650':.75}[camera]
        scatter={'CAM2534':.045,'CAM5080':.075,'CAM7650':.055}[camera]
        threshold={'CAM2534':1.9,'CAM5080':1.35,'CAM7650':1.7}[camera]
    sigma*=max(0.,min(2.,float(value('optical_blur',1.))))
    scatter*=max(0.,min(2.,float(value('highlight_scatter',1.))))
    extra = (max(0., min(1., float(value('camera_softness',0.))))
             if value('product_mode','PIPE')=='PIPE' else 0.)
    base = sigma if environment in {'MACHINE','GODSLIGHT','BUTTON_TRACK'} else 0.
    # Independent Gaussian point-spread variances add; do not stack filters
    # or add radii directly. Diagnostic labels still bypass the compositor.
    return dict(sigma_at_reference=sigma,scatter=scatter,threshold=threshold,
                extra_sigma_at_reference=extra,total_sigma_at_reference=math.hypot(base,extra))


def sample_camera_softness(seed, band):
    """Native-reference pixel sigma; seed stream never inspects defect class."""
    if band not in SOFTNESS_RANGES:raise ValueError('Unknown camera softness band')
    rng=random.Random(f'camera-softness-v1:{seed}')
    return round(rng.uniform(*SOFTNESS_RANGES[band]),6)
