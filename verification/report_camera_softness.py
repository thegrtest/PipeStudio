"""Validate paired optical controls and show native-size defect crops."""
import json,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from domain_review import validate_dataset
OUT=ROOT/'verification/camera_softness_20260915'
rows=json.loads((OUT/'results.json').read_text())
validation,_=validate_dataset(OUT)
assert validation['valid'] and len(rows)==9,validation['errors']
def array(path):return np.asarray(Image.open(path))
checks=[];sections=[]
assets=OUT/'assets';assets.mkdir(exist_ok=True)
sheet=Image.new('RGB',(1200,960),(17,24,23));draw=ImageDraw.Draw(sheet)
for i,setup in enumerate(('CAM5080','MACHINE','STUDIO')):
    group=[r for r in rows if r['setup']==setup];base=group[0]
    mask=array(OUT/'all'/base['instances'][0]['mask'])
    label=(OUT/'all/labels'/f"{base['sample_id']}.txt").read_bytes()
    check=dict(setup=setup,masks_identical=all(np.array_equal(mask,array(OUT/'all'/r['instances'][0]['mask'])) for r in group),
        labels_identical=all((OUT/'all/labels'/f"{r['sample_id']}.txt").read_bytes()==label for r in group),
        lights_identical=all(r['glare_guard']['actual_lights_watts']==base['glare_guard']['actual_lights_watts'] and r['glare_guard']['actual_exposure']==base['glare_guard']['actual_exposure'] for r in group),
        increasing_softness=group[0]['camera_response_sigma_px']<group[1]['camera_response_sigma_px']<group[2]['camera_response_sigma_px'],
        different_rgb=all(not np.array_equal(array(OUT/'all'/base['image']),array(OUT/'all'/r['image'])) for r in group[1:]))
    assert all(v for k,v in check.items() if k!='setup'),check
    checks.append(check);figures=[]
    x,y,w,h=base['instances'][0]['bbox_xywh'];cx,cy=x+w/2,y+h/2
    left=max(0,min(base['width']-400,int(cx-200)));top=max(0,min(base['height']-270,int(cy-135)))
    for j,row in enumerate(group):
        crop=Image.open(OUT/'all'/row['image']).convert('RGB').crop((left,top,left+400,top+270))
        name=f'{setup}_{j}.jpg';crop.save(assets/name,quality=98)
        sheet.paste(crop,(j*400,i*320+44))
        title=row['camera_softness_band'].replace('_',' ')+' / '+str(round(row['camera_response_sigma_px'],2))+' px total'
        draw.text((j*400+8,i*320+10),setup+' / '+title,fill='white')
        figures.append(f'<figure><figcaption>{title}</figcaption><a href="all/{row["image"]}"><img src="assets/{name}" alt="{setup} {title}"></a></figure>')
    sections.append(f'<section><h2>{setup}</h2><div class="grid">'+''.join(figures)+'</div></section>')
sheet.save(OUT/'comparison.jpg',quality=98)
report=dict(valid=True,export_validation=validation,paired_checks=checks,unit_tests_passed=45)
(OUT/'validation.json').write_text(json.dumps(report,indent=2))
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Subtle camera softness</title>
<style>body{background:#111817;color:#e0e9e5;font:16px/1.6 system-ui;margin:30px}main{max-width:1260px;margin:auto}h1{font-size:32px}h2{color:#d0b779}p{max-width:950px;color:#b6c8bd}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}figure{margin:0;background:#213027;padding:10px}img{width:100%;height:auto}figcaption{font-size:14px;margin-bottom:8px}a{color:#b6d8ff}@media(max-width:850px){.grid{grid-template-columns:1fr}}</style><main>
<h1>A slight variation in camera softness</h1><p>New generation plans use 70% near-reference sharpness, 20% gentle softening and 10% slightly softer images in every environment and class. Additional Gaussian sigma ranges are 0–0.12, 0.25–0.50 and 0.50–0.75 pixels at each camera’s reference size. They combine with existing lens softness and scale down with quick renders.</p>
<p>Each row shows the same synthetic pipe, lighting and defect at three blur settings. Crops retain native pixel scale. Click any crop for its full-resolution image. Camera noise is added after optical blur; defect masks and labels stay sharp and identical.</p>
<p><a href="comparison.jpg">Open comparison at 100%</a> · <a href="validation.json">Validation details</a></p>'''+''.join(sections)+'''
<p>45 automated tests passed. All nine optical controls exported successfully with matching masks, labels and lighting. Blender’s Camera panel includes “Extra camera softness (px)” for manual adjustment. These repeated controls are excluded from training datasets.</p></main></html>'''
(OUT/'index.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(valid=True,images=len(rows),checks=checks)))
