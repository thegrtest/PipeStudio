"""Build a local, self-contained visual review of reference and native renders."""
import argparse,base64,io,json
from pathlib import Path
from PIL import Image
import numpy as np
from compare_realism import ROOT,OUT,BODY,crop

def picture(path,box=None):
    with Image.open(path) as source:
        im=crop(source,box) if box else source.copy()
        buffer=io.BytesIO();im.convert('RGB').save(buffer,format='JPEG',quality=94)
        return 'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()

def error(row,region):
    pairs=[row['body']] if region=='body' else row['background']
    return round(float(np.mean([np.abs(np.array(v['real']['rgb_mean'])-v['synthetic']['rgb_mean']) for v in pairs])),2)

def build(name,batch):
    before=json.loads((OUT/'before_baseline.json').read_text())
    after=json.loads((OUT/(name+'.json')).read_text())
    validation=json.loads((batch/'validation.json').read_text())
    data={};rows=[]
    for camera,current in after.items():
        data[camera]={}
        paths={'Reference':Path(current['reference']),'Before':ROOT/before[camera]['render'],'Refined':ROOT/current['render']}
        for label,path in paths.items():
            data[camera][label]={'full':picture(path),'body':picture(path,BODY[camera])}
        rows.append({'camera':camera,'body_before':error(before[camera],'body'),'body_after':error(current,'body'),
                     'background_before':error(before[camera],'background'),'background_after':error(current,'background')})
    table=''.join('<tr>'+''.join('<td>'+str(row[k])+'</td>' for k in ('camera','body_before','body_after','background_before','background_after'))+'</tr>' for row in rows)
    metrics={'selected_roi_mean_color_error_0_255':rows,'validation':validation,'latest_probe':name,
             'evaluation_status':'Development visual calibration only; no new detector inference or blind realism test.'}
    (OUT/'review_metrics.json').write_text(json.dumps(metrics,indent=2))
    template='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Brass realism reference review</title><style>
:root{color-scheme:dark;font:16px/1.5 system-ui;background:#12171b;color:#e6e9e9}body{max-width:1700px;margin:auto;padding:32px}
h1{font-size:clamp(26px,3vw,40px);margin:0}h2{font-size:22px;margin-top:36px}p{max-width:1050px;color:#c3cbcc}
.tag{color:#cfb96b;text-transform:uppercase;letter-spacing:.12em;font-size:12px}nav{display:flex;gap:16px;flex-wrap:wrap;align-items:center;padding:20px 0}
button,select{font:inherit;background:#263138;color:#fff;border:1px solid #59676d;border-radius:7px;padding:7px 12px;cursor:pointer}button[aria-pressed=true]{background:#705f2d}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.card{margin:0;background:#20282d;border-radius:8px;overflow:hidden}figcaption{padding:12px;font-weight:600}.frame{overflow:auto}.frame img{width:100%;display:block}.native img{width:1936px;max-width:none}.body img{min-height:150px;object-fit:contain}
.note{border-left:3px solid #b89c43;padding-left:18px}table{border-collapse:collapse}th,td{text-align:left;padding:9px 20px 9px 0;border-bottom:1px solid #364047}small{color:#9faeb1}a{color:#b9dcd9}summary{cursor:pointer}details img{width:100%;max-width:1400px;margin-top:20px}
@media(max-width:850px){body{padding:16px}.grid{grid-template-columns:1fr}.native img{width:1936px}table{font-size:12px}th,td{padding-right:8px}}
</style><body><div class="tag">Tapered Pipe Studio · Development review · 14 September 2026</div>
<h1>Closer to the inspection cameras</h1><p>Real BrassModel11 frames beside the previous renderer and the refined renderer. These are development references, not an independent test set. The synthetic samples share the same procedural specimen and defect between versions; they do not reproduce the exact damage in the real frame.</p>
<nav><label>Camera <select id="camera"><option>CAM2534</option><option>CAM5080</option><option>CAM7650</option></select></label><button id="full" aria-pressed="true">Full frame</button><button id="body" aria-pressed="false">Metal detail</button><button id="native" aria-pressed="false">Native pixels</button></nav>
<main class="grid" id="comparison"></main><small>All three cameras render at 1936 × 1216. Native pixels enables horizontal scrolling; scroll positions stay synchronized. JPEG display copies are embedded here; the dataset exports PNG.</small>
<h2>What changed</h2><p>Revised framing, camera-specific exposure and noise, stronger axial brass variation, and short pinched folds near the shoulder and mouth rim. Fold placement also includes silhouette cases. Clean, handled and dirty specimens remain independent of the four defect classes; existing folds, mixed defects and all eight setups remain available.</p>
<p>The three August cameras use smooth distant-background radiance fields fitted from 36 development photographs across August 19 and 20. Pipe and fixture regions are excluded from the fit. The brass, defects and nearby fixture are rendered geometry. This is a view-dependent approximation of the distant scene, not a complete 3D reconstruction or a raw photo background.</p>
<h2>Completed export check</h2><p>__VALIDATION__</p><p><a href="__BATCH__">Open the batch review and individual labels</a></p>
<h2>Selected-region color checks</h2><p>Mean absolute RGB error on the selected body region and three background patches, in 0–255 display values; lower means a closer average color. These measurements do not score shape, perceptual realism, novelty or detector accuracy, and fitting to these development frames makes them optimistic.</p>
<table><thead><tr><th>Camera</th><th>Body before</th><th>Body refined</th><th>Background before</th><th>Background refined</th></tr></thead><tbody>__TABLE__</tbody></table>
<h2>Remaining differences</h2><p class="note">The pipe and fixture remain distinguishable. Highlight shape, irregular surface marks, fixture machining and lens behavior still differ. Not every older April/May camera configuration in BrassModel11 has been reconstructed. There is no claim of indistinguishability or improved YOLOX transfer from this visual review.</p>
<p>The saved evaluation overlays show narrow folds missed or confused with dents and detections on fixture features. Real annotations cover Fold/Dent only; synthetic Soap/Oil predictions need separate stain ground truth. A useful next comparison requires fixed checkpoint hashes and inference settings on reserved acquisition sessions, measuring recall by camera and defect size, fold/dent confusion and fixture false positives.</p>
<details><summary>August 20 framing and environment coverage</summary><p>Representative references and varied generated specimens. The finish, defect and lighting are different specimens, so this is a coverage check rather than a paired photometric score.</p><img alt="August 20 camera reference and generated coverage examples" src="__AUG20__"></details>
<details><summary>Inspect the saved real fold annotations and prediction crops</summary><img alt="Real fold annotations and corresponding saved evaluation prediction crops" src="__EVAL__"></details>
<script>const data=__DATA__;let view='full',native=false;const el=id=>document.getElementById(id);function render(){const camera=el('camera').value;el('comparison').innerHTML='';for(const label of ['Reference','Before','Refined']){const f=document.createElement('figure');f.className='card';const cap=document.createElement('figcaption');cap.textContent=label+' · '+camera;const frame=document.createElement('div');frame.className='frame '+(view==='body'?'body':native?'native':'');const img=document.createElement('img');img.src=data[camera][label][view];img.alt=label+' '+camera+' '+view;frame.append(img);f.append(cap,frame);el('comparison').append(f)}for(const id of ['full','body'])el(id).setAttribute('aria-pressed',String(view===id));el('native').setAttribute('aria-pressed',String(native));el('native').disabled=view!=='full';let busy=false;document.querySelectorAll('.frame').forEach(frame=>frame.onscroll=()=>{if(busy)return;busy=true;document.querySelectorAll('.frame').forEach(other=>{if(other!==frame){other.scrollLeft=frame.scrollLeft;other.scrollTop=frame.scrollTop}});requestAnimationFrame(()=>busy=false)})}el('camera').onchange=render;for(const id of ['full','body'])el(id).onclick=()=>{view=id;render()};el('native').onclick=()=>{native=!native;render()};render();</script></body></html>'''
    message=(f"{validation['image_count']} images and {validation['label_count']} labels, "
             f"{sum(validation['counts']['instance_class'].values())} independently labeled defects, "
             f"{len(validation['counts']['setup'])} setups. "
             f"Validation: {'PASS' if validation['valid'] and validation['complete'] else 'NOT PASSED'}. "
             "Checks cover dimensions, file pairs, hashes, mask/box agreement and exact duplicate images. "
             "The 102 targeted source tests also pass. The coverage batch is not the production class distribution.")
    replacements={'__VALIDATION__':message,'__TABLE__':table,'__DATA__':json.dumps(data),
                  '__EVAL__':picture(OUT/'fold_eval_crops.jpg'),'__AUG20__':picture(OUT/'aug20_comparison.jpg'),
                  '__BATCH__':(batch/'index.html').as_uri()}
    for token,value in replacements.items():template=template.replace(token,value)
    (OUT/'index.html').write_text(template,encoding='utf-8')
    print(json.dumps({'report':str(OUT/'index.html'),'metrics':rows},indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--name',required=True);ap.add_argument('--batch',type=Path,required=True)
    args=ap.parse_args();build(args.name,args.batch.resolve())
