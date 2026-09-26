"""Camera-scale brass microfinish; generated fields, never copied photo pixels."""
import json
import math
import numpy as np

VERSION='assembly-camera-patch-finish-1'


def grain_field(seed,length,radius,width=1024,height=768):
    """Short correlated grain in physical coordinates, with a periodic seam.

    Camera patches constrain the visible scale. The random phase and seed are
    independent of defect class; this is an appearance fit, not alloy metrology.
    """
    rng=np.random.default_rng([int(seed),393617])
    fx=np.fft.rfftfreq(width,d=length/width)
    fy=np.fft.fftfreq(height,d=math.tau*radius/height)
    spectrum=np.exp(-.5*((math.tau*.022*fx[None,:])**2+(math.tau*.012*fy[:,None])**2))
    frequency=np.hypot(fx[None,:],fy[:,None])
    spectrum*=1-np.exp(-(frequency/4.)**4)
    z=np.fft.irfft2(np.fft.rfft2(rng.normal(size=(height,width)))*spectrum,s=(height,width))
    z/=max(float(z.std()),1e-8)
    return np.clip(.5+.065*z,.08,.92).astype(np.float32)


def configure_finish(material,recipe):
    if recipe.get('look') not in ('CAMERA_MATCHED','WARM_TRACK'):return
    n=material.node_tree.nodes
    grain=n['Inspection statistical grain'].image
    params=dict(version=VERSION,seed=recipe['seed'],length=recipe['base']['length'],radius=recipe['base']['radius'])
    signature=json.dumps(params,sort_keys=True)
    if grain.get('assembly_finish_signature')!=signature:
        w,h=grain.size
        pixels=np.ones((h,w,4),dtype=np.float32)
        pixels[...,:3]=grain_field(params['seed'],params['length'],params['radius'],w,h)[...,None]
        grain.pixels.foreach_set(pixels.ravel());grain.update();grain.pack()
        grain['assembly_finish_signature']=signature
    n['Inspection statistical grain multiplier'].inputs['To Min'].default_value=.15
    n['Inspection statistical grain multiplier'].inputs['To Max'].default_value=1.85
    for shader in ('BrassShader','PolishedBrass','DullOxide'):
        n['Inspection measured grain '+shader].inputs[0].default_value=1.
    # Muted warm tarnish leaves darker quiet areas between the small traces.
    n['Thin oxide film'].inputs[1].default_value=.50
    ramp=n['OxideColors'].color_ramp
    ramp.elements[0].color=(.13,.095,.060,1);ramp.elements[1].color=(.32,.24,.15,1)
    if n.get('Assembly camera roughness variation'):
        n['Assembly camera roughness variation'].inputs[1].default_value=.06
        n['Assembly camera roughness variation'].inputs[2].default_value=-.03
    if recipe.get('look')=='WARM_TRACK':
        # The second station is burnished at camera scale. Fine drawn grain
        # remains, but the former high-amplitude mottling looks like corrosion.
        n['Inspection statistical grain multiplier'].inputs['To Min'].default_value=.50
        n['Inspection statistical grain multiplier'].inputs['To Max'].default_value=1.50
        for shader in ('BrassShader','PolishedBrass','DullOxide'):
            n['Inspection measured grain '+shader].inputs[0].default_value=.65
        params['station']='WARM_TRACK';params['grain_mix']=.65
        signature=json.dumps(params,sort_keys=True)
    material['assembly_finish_version']=VERSION
    material['assembly_finish_parameters']=signature
