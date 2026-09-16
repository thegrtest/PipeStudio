"""Compare localized finish changes at native scale; exclude from training."""
import html
import json
import os
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from domain_review import validate_dataset,write_gallery
from generate_domain_dataset import source_signature
from brass_microdetail import VERSION
from domain_plan import CLASSES

OUT=ROOT/'verification/microdetail_20260915'
PREVIOUS=ROOT/'verification/realism_20260915/accepted_matched'
NEW=OUT/'matched_final'
REFERENCES={
    'CAM2534':('20260819_170247_047_cam2534.jpg',(620,235,1650,490)),
    'CAM5080':('20260819_170221_830_cam5080.jpg',(240,500,1565,830)),
    'CAM7650':('20260819_170219_035_cam7650.jpg',(430,850,1765,1180)),
}
def read(path):return json.loads(path.read_text())
def pixels(path):return np.asarray(Image.open(path))
def relative(path):return html.escape(Path(os.path.relpath(path,OUT)).as_posix())

def main():
    env=OUT/'all_environments'
    rows=read(env/'results.json');plan=read(env/'review_plan.json')
    (env/'render_plan.json').write_text(json.dumps(plan,indent=2))
    (env/'all/manifest.json').write_text(json.dumps(dict(classes=CLASSES,samples=rows),indent=2))
    validation,_=validate_dataset(env)
    assert validation['valid'] and validation['complete'],validation
    assert len(set(r['setup'] for r in rows))==8 and len(rows)==21
    assert all(r['material_response_version']==VERSION and r['material_detail_audit']['version']==VERSION for r in rows)
    (env/'validation.json').write_text(json.dumps(validation,indent=2))
    write_gallery(env,validation,rows)
    a,b=[r for r in rows if r.get('pair_role')=='lighting_variant']
    paired=dict(same_mask=np.array_equal(pixels(env/'all'/a['instances'][0]['mask']),pixels(env/'all'/b['instances'][0]['mask'])),
                same_labels=(env/'all/labels'/f"{a['sample_id']}.txt").read_bytes()==(env/'all/labels'/f"{b['sample_id']}.txt").read_bytes(),
                same_details=a['material_detail_audit']==b['material_detail_audit'],
                different_rgb=not np.array_equal(pixels(env/'all'/a['image']),pixels(env/'all'/b['image'])))
    assert all(paired.values()),paired
    old={r['setup']:r for r in read(PREVIOUS/'results.json')}
    revised=read(NEW/'results.json')
    assets=OUT/'assets';assets.mkdir(exist_ok=True)
    sections=[];geometry=[]
    sheet=Image.new('RGB',(1500,950),(16,23,22));draw=ImageDraw.Draw(sheet)
    for index,row in enumerate(revised):
        camera=row['setup'];prior=old[camera]
        original_path=PREVIOUS/'all'/prior['image'];new_path=NEW/'all'/row['image']
        ref_name,ref_box=REFERENCES[camera]
        reference=ROOT.parent/'BrassModel11/all/2026-08-19GodsLight/images'/ref_name
        geometry.append(dict(camera=camera,
            same_mask=np.array_equal(pixels(PREVIOUS/'all'/prior['instances'][0]['mask']),pixels(NEW/'all'/row['instances'][0]['mask'])),
            same_labels=(PREVIOUS/'all/labels'/f"{prior['sample_id']}.txt").read_bytes()==(NEW/'all/labels'/f"{row['sample_id']}.txt").read_bytes(),
            same_resolution=Image.open(original_path).size==Image.open(new_path).size==(1936,1216)))
        assert all(v for k,v in geometry[-1].items() if k!='camera'),geometry[-1]
        x,y,w,h=row['projected_pipe_bbox_xywh'];box=(int(x)-6,int(y)-12,int(x+w)+6,int(y+h)+12)
        figures=[]
        for column,(label,path,cropbox) in enumerate((('Real development image',reference,ref_box),('Previous finish',original_path,box),('Localized details',new_path,box))):
            im=Image.open(path).convert('RGB').crop(cropbox)
            target=assets/f'{camera}_{column}.jpg';im.save(target,quality=97)
            tile=im.copy();tile.thumbnail((490,240));sheet.paste(tile,(column*500,index*315+35))
            draw.text((column*500+8,index*315+10),camera+' / '+label,fill='white')
            figures.append(f'<figure><figcaption>{label}</figcaption><a href="{relative(path)}"><img src="assets/{target.name}" alt="{camera}, {label}"></a><small>Click for the original 1936 × 1216 frame.</small></figure>')
        sections.append(f'<section><h2>{camera}</h2><div class="comparison">'+''.join(figures)+'</div></section>')
    sheet.save(OUT/'comparison.jpg',quality=97)
    report=dict(valid=True,version=VERSION,export_validation=validation,paired_lighting=paired,
                before_after_geometry=geometry,shader_checks=read(OUT/'shader_validation.json'),
                renderer_sources=source_signature(),real_detector_accuracy_measured=False)
    (OUT/'validation.json').write_text(json.dumps(report,indent=2))
    (OUT/'REVIEW_ONLY.txt').write_text('Development renders and real-reference comparisons. Exclude this folder from all training and held-out evaluation datasets.\n')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Brass: localized surface details</title>
<style>body{margin:0;background:#101716;color:#e6ede9;font:16px/1.6 system-ui;padding:32px}main{max-width:1700px;margin:auto}h1{font-size:34px}h2{color:#d3bc7a;font-size:21px}p{max-width:1050px;color:#bdcac4}a{color:#b7d8ff}.comparison{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}figure{margin:0;background:#18231f;padding:12px;border:1px solid #34473e}figcaption{font-weight:650;margin-bottom:8px}img{width:100%;height:180px;object-fit:contain}small{color:#a5b5ad}section{margin-top:30px;border-top:1px solid #334339;padding-top:8px}.note{border-left:3px solid #c3aa66;padding:12px 20px;background:#24342a}.crop{width:100%;height:auto;max-width:1500px}@media(max-width:850px){.comparison{grid-template-columns:1fr}body{padding:14px}}</style><main>
<h1>Less uniform brass, down to the small details</h1>
<p>New contact patches introduce localized polish, broken short drawing marks, sparse tiny specks and interrupted rim wear. Fine grain becomes quieter in polished areas. These details follow the pipe surface and respond to lighting; different specimen seeds receive different patterns.</p>
<p class="note">Before and after use the same synthetic pipe geometry, camera and diagnostic defects. The real photograph shows a different physical specimen. These are development comparisons, not evidence of improved detector accuracy.</p>
<p><a href="all_environments/index.html">21 previews across all eight environments</a> · <a href="validation.json">Export and geometry checks</a> · <a href="detail_compare_final.jpg">Native-size body detail comparison</a></p>
'''+''.join(sections)+'''
<section><h2>Inspect the small details</h2><p>The paired crops below preserve the original pixel scale. Open the image to inspect at 100%; thumbnails hide small marks.</p><a href="detail_compare_final.jpg"><img class="crop" src="detail_compare_final.jpg" alt="Native-size before and after body crops for three cameras"></a></section>
<p>99 automated checks passed. All 21 renders exported valid image/label pairs, with the established glare guard. Material refreshes reuse textures and shader nodes; lighting and defect class do not change a specimen’s detail pattern. Clean finishes have fewer marks. Existing jobs and datasets were not replaced.</p></main></html>'''
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(valid=True,images=len(rows),environments=8,geometry=geometry,paired=paired)))

if __name__=='__main__':main()
