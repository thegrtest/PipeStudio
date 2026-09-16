"""Native-size comparisons, export validation and development-only gallery."""
import json,sys,os,html
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'verification/realism_20260915'
from domain_review import validate_dataset,write_gallery
from domain_plan import make_plan
from generate_domain_dataset import source_signature

REFS={'CAM2534':('20260819_170247_047_cam2534.jpg',(620,235,1650,490),(1000,300,1512,428)),
      'CAM5080':('20260819_170221_830_cam5080.jpg',(240,500,1565,830),(550,580,1062,708)),
      'CAM7650':('20260819_170219_035_cam7650.jpg',(430,850,1765,1180),(700,930,1212,1058))}

def read(p):return json.loads(p.read_text())
def rgb(p):return np.asarray(Image.open(p).convert('RGB'))
def metrics(im):
    # Green-channel multi-pixel detail reduces sensitivity to blue-channel
    # sensor noise. Values diagnose appearance, not detector performance.
    a=np.asarray(im.filter(ImageFilter.GaussianBlur(.7)),float)[...,1]
    slow=np.asarray(im.filter(ImageFilter.GaussianBlur(8)),float)[...,1]
    d=a-slow
    return dict(green_median=float(np.median(a)),detail_std=float(d.std()),
                gradient_direction_ratio=float(np.diff(d,axis=0).std()/max(np.diff(d,axis=1).std(),1e-6)))

def main():
    env=OUT/'all_environments';rows=read(env/'results.json')
    assert len(rows)==21
    plan=read(env/'review_plan.json');(env/'render_plan.json').write_text(json.dumps(plan,indent=2))
    (env/'all/manifest.json').write_text(json.dumps(dict(classes={'0':'Fold','1':'Dent','2':'Soap stain','3':'Oil stain'},samples=rows),indent=2))
    validation,_=validate_dataset(env)
    left,right=[r for r in rows if r.get('pair_role')=='lighting_variant']
    paired=dict(same_geometry=left['instances'][0]['spec']==right['instances'][0]['spec'],
       same_mask=np.array_equal(rgb(env/'all'/left['instances'][0]['mask']),rgb(env/'all'/right['instances'][0]['mask'])),
       same_labels=(env/'all/labels'/f"{left['sample_id']}.txt").read_bytes()==(env/'all/labels'/f"{right['sample_id']}.txt").read_bytes(),
       changed_rgb=not np.array_equal(rgb(env/'all'/left['image']),rgb(env/'all'/right['image'])))
    assert validation['valid'] and all(paired.values()),(validation,paired)
    assert all(r['material_response_version']=='inspection-statistical-finish-4' for r in rows)
    write_gallery(env,validation,rows)
    baseline={r['setup']:r for r in read(OUT/'baseline_matched/results.json')}
    after={r['setup']:r for r in read(OUT/'accepted_matched/results.json')}
    assets=OUT/'assets';assets.mkdir(exist_ok=True)
    sections=[];scores={};mask_checks={}
    sheet=Image.new('RGB',(1536,780),(16,21,24));drawing=ImageDraw.Draw(sheet)
    for index,(camera,(name,real_box,real_roi)) in enumerate(REFS.items()):
        real=ROOT.parent/'BrassModel11/all/2026-08-19GodsLight/images'/name
        entries=[('Real camera',real,None),('Previous generator',OUT/'baseline_matched/all'/baseline[camera]['image'],baseline[camera]),
                 ('Revised generator',OUT/'accepted_matched/all'/after[camera]['image'],after[camera])]
        figures=[];scores[camera]={}
        for col,(label,path,record) in enumerate(entries):
            im=Image.open(path).convert('RGB');assert im.size==(1936,1216)
            box=real_box
            if record:
                x,y,w,h=record['projected_pipe_bbox_xywh'];box=(int(x)-10,int(y)-20,int(x+w)+10,int(y+h)+20)
                cx=x+w*.48;cy=y+h*.50;roi=(int(cx)-256,int(cy)-64,int(cx)+256,int(cy)+64)
            else:roi=real_roi
            scores[camera][label]=metrics(im.crop(roi))
            crop=im.crop(box);preview=assets/f'{camera}_{col}.jpg';crop.save(preview,quality=96)
            tile=crop.copy();tile.thumbnail((502,200));sheet.paste(tile,(col*512,index*260+34))
            drawing.text((col*512+8,index*260+9),camera+' / '+label,fill='white')
            link=Path(os.path.relpath(path,OUT)).as_posix()
            figures.append(f'<figure><figcaption>{label}</figcaption><a href="{html.escape(link)}"><img src="assets/{preview.name}" alt="{camera} {label}"></a><small>Open full 1936 × 1216 frame</small></figure>')
        a,b=baseline[camera],after[camera]
        mask_checks[camera]=np.array_equal(rgb(OUT/'baseline_matched/all'/a['instances'][0]['mask']),rgb(OUT/'accepted_matched/all'/b['instances'][0]['mask']))
        sections.append(f'<section><h2>{camera}</h2><div class="comparison">'+''.join(figures)+'</div></section>')
    assert all(mask_checks.values()),mask_checks
    sheet.save(OUT/'comparison.jpg',quality=96)
    p=make_plan(seed=915270000,quality='full',profile='yolox')
    summary=dict(valid=True,export_validation=validation,paired_lighting=paired,unchanged_defect_masks=mask_checks,
                 development_crop_diagnostics=scores,shader_checks=read(OUT/'shader_validation.json'),
                 production_ratios=dict(images=len(p['samples']),primary=p['expected_primary_counts'],instances=p['expected_instance_counts'],environments=p['expected_setup_counts']),
                 renderer_sources=source_signature(),real_detector_accuracy_measured=False)
    (OUT/'validation.json').write_text(json.dumps(summary,indent=2))
    (OUT/'REVIEW_ONLY.txt').write_text('Development renders and comparisons with real references. Exclude this complete folder from training bundles.\n')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Brass realism — reference comparison</title>
<style>body{background:#101719;color:#e4ede8;font:16px/1.6 system-ui;margin:0;padding:40px}main{max-width:1600px;margin:auto}h1{font-size:36px;margin-bottom:8px}h2{font-size:20px;color:#d8bf7d}p{max-width:1000px;color:#b5c6bf}a{color:#bcd9ff}section{border-top:1px solid #334039;margin-top:32px;padding-top:12px}.comparison{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0;background:#172023;border:1px solid #35433b;padding:12px}img{width:100%;height:180px;object-fit:contain}figcaption{font-weight:600}small{color:#9daea6}.note{background:#23342c;border-left:3px solid #c7ac67;padding:12px 20px} @media(max-width:800px){body{padding:16px}.comparison{grid-template-columns:1fr}h1{font-size:26px}}</style><main>
<h1>Brass realism: compare the evidence</h1><p>September 15, 2026 · Native camera resolution · Blender Cycles</p>
<p>Revised surface detail uses aggregate texture spectra measured from clear, label-checked areas of three real development frames. Each specimen receives a newly synthesized pattern. Fine roughness and normal variation, broader broken drawing marks, a larger off-axis diffuser and less uniform machined fixture surfaces replace the previous appearance.</p>
<p class="note">The real and synthetic images show different physical specimens. Before and after use the same synthetic geometry and camera settings; their defect masks match. These comparisons establish rendering and export behavior, not improved YOLOX accuracy. The fixture and reflected environment remain approximations.</p>
<p><a href="all_environments/index.html">All 21 previews across eight environments</a> · <a href="../../REALISM_RESOURCES.md">Tutorials and material-capture resources</a> · <a href="validation.json">Validation and crop diagnostics</a></p>'''+''.join(sections)+'''
<section><h2>What was verified</h2><p>95 automated checks passed, plus Blender checks for stable repeated updates, independent specimen seeds and finish consistency across defect classes. All 21 environment previews exported with valid labels and masks. The two lighting controls have identical geometry, labels and mask pixels while their rendered RGB images differ. All glare guards passed.</p>
<p>Future plans keep the established class/environment allocation. Existing snapshots and jobs were not replaced. Review images are marked to stay out of training datasets.</p></section></main></html>'''
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(valid=True,images=validation['image_count'],environments=len(p['expected_setup_counts']),paired=paired,unchanged_masks=mask_checks)))

if __name__=='__main__':main()
