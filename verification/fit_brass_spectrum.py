"""Fit aggregate grain power; discard phase, pixel locations and lighting.

Only explicit body ROIs away from the supplied neck/shoulder fold labels are
used. This is development reference analysis, not held-out model evaluation.
"""
import json,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
ROOT=Path(__file__).resolve().parents[1]
REF=ROOT.parent/'BrassModel11/all/2026-08-19GodsLight/images'
CASES=[('20260819_170247_047_cam2534.jpg',(1000,300,1512,428),126.),
       ('20260819_170221_830_cam5080.jpg',(550,580,1062,708),162.),
       ('20260819_170219_035_cam7650.jpg',(700,930,1212,1058),164.)]
axis=np.linspace(0,80,65);power=[];records=[]
for name,box,px_per_unit in CASES:
    label=REF.parent/'labels'/Path(name).with_suffix('.txt').name
    if not label.is_file():raise ValueError('Missing development ROI label: '+str(label))
    annotation_count=0
    for line in label.read_text().splitlines():
        vals=[float(v) for v in line.split()]
        if not vals:continue
        if len(vals)==5:
            _,cx,cy,w,h=vals;xb=(cx-w/2,cx+w/2);yb=(cy-h/2,cy+h/2)
        elif len(vals)>=7 and len(vals)%2:
            xb=(min(vals[1::2]),max(vals[1::2]));yb=(min(vals[2::2]),max(vals[2::2]))
        else:raise ValueError('Malformed reference label: '+str(label))
        if min(box[2],xb[1]*1936)>max(box[0],xb[0]*1936) and min(box[3],yb[1]*1216)>max(box[1],yb[0]*1216):
            raise ValueError('Reference ROI overlaps a labeled defect: '+name)
        annotation_count+=1
    image=Image.open(REF/name).convert('RGB')
    green=np.asarray(image.crop(box),dtype=float)[...,1]
    slow=np.asarray(Image.fromarray(green.astype('uint8')).filter(ImageFilter.GaussianBlur(18)),dtype=float)
    detail=(green-slow)/np.maximum(slow,30)
    # Remove isolated outliers; labels are not used to learn a defect pattern.
    detail=np.clip(detail,-.18,.18)
    for x in range(0,385,64):
        patch=detail[:,x:x+128];patch=patch-patch.mean()
        patch*=np.hanning(128)[:,None]*np.hanning(128)[None,:]
        p=np.abs(np.fft.fft2(patch))**2
        # Fold all frequency quadrants into an even directional power field.
        folded=np.empty((65,65))
        for y in range(65):
            for k in range(65):folded[y,k]=np.mean([p[y,k],p[-y%128,k],p[y,-k%128],p[-y%128,-k%128]])
        native=np.arange(65)*px_per_unit/128
        interp=np.array([np.interp(axis,native,line,left=line[0],right=0) for line in folded])
        interp=np.array([np.interp(axis,native,line,left=line[0],right=0) for line in interp.T]).T
        interp/=max(interp.sum(),1e-12);power.append(interp)
    records.append(dict(image=name,roi_xyxy=box,pixels_per_scene_unit=px_per_unit,detail_std=float(detail.std()),checked_annotations=annotation_count,no_label_overlap=True))
mean=np.mean(power,axis=0)
# Smooth sparse spectral estimates, retaining directional structure. Applying
# a 3x3 neighborhood to log power avoids storing individual frequency spikes.
log=np.log(mean+1e-8);pad=np.pad(log,1,mode='edge')
log=sum(pad[y:y+65,x:x+65] for y in range(3) for x in range(3))/9
result=dict(version='development-brass-spectrum-1',axis_cycles_per_scene_unit=axis.tolist(),
            log_power=log.round(6).tolist(),references=records,
            representation='Aggregate power only; phase, photo pixels, defects and lighting are not retained.',
            limitations='Three development ROIs; image-space appearance estimate, not a measured BRDF or sensor-independent texture.')
(ROOT/'reference_brass_spectrum.json').write_text(json.dumps(result,separators=(',',':')))
print('FITTED_BRASS_SPECTRUM',len(power),'patches')
