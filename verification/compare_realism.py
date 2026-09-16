"""Read-only reference audit and before/after comparison; never trains on photos."""
import argparse
from collections import Counter
import json
import re
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT=Path(__file__).resolve().parents[1]
DESKTOP=ROOT.parent
REAL=DESKTOP/'BrassModel11'/'all'
OUT=ROOT/'verification'/'realism_v2'
REFERENCES={
    'CAM2534':'20260819_170247_047_cam2534.jpg',
    'CAM5080':'20260819_170221_830_cam5080.jpg',
    'CAM7650':'20260819_170219_035_cam7650.jpg',
}
BODY={'CAM2534':(.46,.245,.82,.385),'CAM5080':(.16,.465,.66,.645),
      'CAM7650':(.26,.745,.75,.935)}
PATCHES={'CAM2534':[(.08,.1,.28,.3),(.55,.04,.77,.17),(.3,.78,.5,.95)],
         'CAM5080':[(.30,.12,.5,.30),(.78,.06,.96,.25),(.77,.72,.95,.94)],
         'CAM7650':[(.33,.04,.57,.24),(.65,.2,.91,.48),(.04,.25,.15,.48)]}

def crop(im,box):
    return im.crop(tuple(round(v*im.size[i%2]) for i,v in enumerate(box)))

def metrics(im,box):
    im=crop(im,box).convert('RGB')
    a=np.asarray(im,dtype=np.float32)
    smooth=np.asarray(im.filter(ImageFilter.GaussianBlur(2)),dtype=np.float32)
    residual=a-smooth
    l=a@np.array([.2126,.7152,.0722])
    return {'rgb_mean':np.mean(a,axis=(0,1)).round(2).tolist(),
            'luma_q10_q50_q90':np.quantile(l,[.1,.5,.9]).round(2).tolist(),
            'highpass_rgb_std':np.std(residual,axis=(0,1)).round(3).tolist(),
            'gradient_xy': [round(float(np.mean(np.abs(np.diff(l,axis=d)))),3) for d in (1,0)]}

def inventory():
    summary=[]; selected=[]
    for folder in sorted(REAL.iterdir()):
        if not (folder/'images').is_dir():continue
        files=sorted((folder/'images').glob('*.jpg'))
        def camera_of(p):
            match=re.search(r'cam\d+',p.stem)
            return match.group() if match else 'unidentified'
        cameras=sorted(set(camera_of(p) for p in files))
        sizes=Counter()
        for camera in cameras:
            group=[p for p in files if camera_of(p)==camera]
            for p in group[::max(1,len(group)//8)][:8]:
                with Image.open(p) as im:sizes[str(im.size)]+=1
            if group:selected.append((folder.name,camera,group[len(group)//2]))
        summary.append({'session':folder.name,'images':len(files),'cameras':cameras,'sampled_dimensions':dict(sizes)})
    canvas=Image.new('RGB',(1200,((len(selected)+2)//3)*288),(22,25,28));draw=ImageDraw.Draw(canvas)
    for i,(session,camera,p) in enumerate(selected):
        x=(i%3)*400;y=(i//3)*288
        with Image.open(p) as im:
            im.thumbnail((400,252));canvas.paste(im,(x,y+30))
        draw.text((x+6,y+7),session+' / '+camera,fill='white')
    OUT.mkdir(exist_ok=True,parents=True)
    canvas.save(OUT/'reference_inventory.jpg',quality=92)
    (OUT/'reference_inventory.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

def compare(render_dir,name):
    OUT.mkdir(exist_ok=True,parents=True)
    report={};canvas=Image.new('RGB',(1440,3*570),(22,25,28));draw=ImageDraw.Draw(canvas)
    for i,(camera,filename) in enumerate(REFERENCES.items()):
        actual=REAL/'2026-08-19GodsLight'/'images'/filename
        candidates=sorted((render_dir/'all'/'images').glob('*'+camera.lower()+'*.png'))
        if not candidates:candidates=sorted((render_dir/'images').glob('*'+camera.lower()+'*.png'))
        if not candidates:continue
        synthetic=candidates[0]
        with Image.open(actual) as a,Image.open(synthetic) as b:
            report[camera]={'reference':str(actual),'render':str(synthetic),
                'body':{'real':metrics(a,BODY[camera]),'synthetic':metrics(b,BODY[camera])},
                'background':[{'real':metrics(a,p),'synthetic':metrics(b,p)} for p in PATCHES[camera]]}
            y=i*570
            for col,im,label in ((0,a,'REAL / '+camera),(1,b,'SYNTHETIC / '+camera)):
                thumb=im.copy();thumb.thumbnail((720,452));canvas.paste(thumb,(col*720,y+25))
                region=crop(im,BODY[camera]);region.thumbnail((710,85));canvas.paste(region,(col*720,y+480))
                draw.text((col*720+8,y+6),label,fill='white')
    canvas.save(OUT/(name+'.jpg'),quality=95)
    (OUT/(name+'.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v['body'] for k,v in report.items()},indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--inventory',action='store_true')
    ap.add_argument('--render',type=Path);ap.add_argument('--name',default='comparison')
    args=ap.parse_args()
    if args.inventory:inventory()
    if args.render:compare(args.render,args.name)
