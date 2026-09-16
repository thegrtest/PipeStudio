"""Deterministic image noise for reference inspection cameras, beauty only.

The August camera JPEGs have much more blue-channel noise than the renders.
This is an empirical camera-response approximation, not sensor calibration.
Input/output RGB are scene-linear values; the observation model is expressed
in encoded pixel values so its dark-channel variance remains controlled.
"""
def apply_sensor_noise(pixels,settings):
    import numpy as np
    from domain_profiles import optical_reference_width
    def value(key,default):
        return settings.get(key,default) if isinstance(settings,dict) else getattr(settings,key,default)
    amount=float(value('sensor_noise',0))
    if amount<=0:return pixels
    rng=np.random.default_rng(int(value('seed',42)))
    rgb=pixels[...,:3]
    if value('environment','STUDIO')!='GODSLIGHT' or value('inspection_camera','ORIGINAL')=='ORIGINAL':
        sigma=amount*np.sqrt(np.maximum(rgb,0)+.01)
        rgb[:]=np.clip(rgb+rng.normal(size=rgb.shape)*sigma,0,1)
        return pixels
    signal=np.clip(rgb,0,1)
    encoded=np.where(signal<=.0031308,12.92*signal,1.055*np.power(signal,1/2.4)-.055)
    scale=min(1.,float(value('resolution',1936))/optical_reference_width(settings))
    gains=np.array({'CAM2534':[1.40,1.40,4.5],'CAM5080':[.90,.90,4.5],
                    'CAM7650':[.85,.90,4.5]}[value('inspection_camera','CAM2534')],dtype=np.float32)
    sigma=amount*scale*np.sqrt(.10+encoded)*gains
    encoded=np.clip(encoded+rng.normal(size=encoded.shape)*sigma,0,1)
    rgb[:]=np.where(encoded<=.04045,encoded/12.92,np.power((encoded+.055)/1.055,2.4))
    return pixels
