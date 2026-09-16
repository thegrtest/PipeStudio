"""Fit low-frequency background radiance, excluding pipes and mounting hardware.

The output contains 280 smooth basis coefficients per acquisition/camera, not
photographs or image textures. Multiple reference frames suppress transient
objects. These source sessions are development references, not an evaluation
holdout. High-frequency photographic details cannot be reproduced by this fit.
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageFilter
ROOT=Path(__file__).resolve().parents[1]
REAL=ROOT.parent/'BrassModel11'/'all'
W,H=128,80
u,v=np.meshgrid((np.arange(W)+.5)/W,(np.arange(H)+.5)/H)
centers=np.array([(x,y) for y in np.linspace(0,1,14) for x in np.linspace(0,1,20)])
sigma=np.array([.050,.070])
xy=np.stack((u,v),axis=-1).reshape(-1,2)
kernel=np.exp(-.5*np.sum(((xy[:,None,:]-centers[None,:,:])/sigma)**2,axis=2))
basis=kernel/kernel.sum(axis=1,keepdims=True)
fields={}
for session,folder in (('AUG19','2026-08-19GodsLight'),('AUG20','2026-08-20')):
    for camera in ('CAM2534','CAM5080','CAM7650'):
        paths=sorted((REAL/folder/'images').glob('*_'+camera.lower()+'.jpg'))
        # A compact, reproducible development subset, not all evaluation images.
        selected=[paths[round(i*(len(paths)-1)/5)] for i in range(6)]
        frames=[]
        for path in selected:
            with Image.open(path) as im:
                arr=np.asarray(im.convert('RGB').filter(ImageFilter.GaussianBlur(10)).resize((W,H),Image.Resampling.LANCZOS),dtype=np.float64)/255
                frames.append(np.where(arr<=.04045,arr/12.92,((arr+.055)/1.055)**2.4))
        target=np.median(frames,axis=0).reshape(-1,3)
        if camera=='CAM2534':
            valid=(u<.81)&~((u>.28)&(v>.17)&(v<.44))
        elif camera=='CAM5080':
            low,high=(.39,.72) if session=='AUG19' else (.58,.93)
            valid=(u>.17)&~((u<.84)&(v>low)&(v<high))
        else:
            valid=(u>.26)&~((u<.94)&(v>.67))
        mask=valid.ravel()
        A=basis[mask];Y=target[mask]
        # Weak mean prior stabilizes unobserved, masked portions behind the part.
        ridge=.015
        coef=np.linalg.solve(A.T@A+ridge*np.eye(len(centers)),A.T@Y+ridge*np.tile(Y.mean(axis=0),(len(centers),1)))
        error=np.mean(np.abs(A@coef-Y),axis=0)
        fields[camera+'_'+session]={'centers':centers.round(6).tolist(),'sigma':sigma.tolist(),
            'coefficients':coef.round(7).tolist(),'source_references':[str(p.relative_to(ROOT.parent)).replace('\\','/') for p in selected],
            'source_dimensions':[1936,1216],'fit_mae_linear_rgb':error.round(5).tolist(),
            'excluded_regions':'Entire part envelope and mounting fixture; no defect pixels are used.'}
result={'version':1,'representation':'Normalized Gaussian basis, linear RGB radiance; 20 by 14 control centers.',
        'calibrated':False,'reference_use':'Development backgrounds only; never use these sessions as an untouched holdout.',
        'fields':fields}
(ROOT/'reference_environment_fields.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print({k:v['fit_mae_linear_rgb'] for k,v in fields.items()})
