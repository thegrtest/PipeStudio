"""Native-scale review of the shared tapered-pipe finish; never training data."""
import html
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from brass_microdetail import VERSION
from domain_plan import CLASSES
from domain_review import validate_dataset, write_gallery

OUT = ROOT/'verification/finish_20260919'
REF = ROOT.parent/'BrassModel11/all/2026-08-19GodsLight/images'
REFERENCES = {
    'CAM2534': ('20260819_170247_047_cam2534.jpg', (860,290,1400,460), (610,250,850,480), (1580,90,1725,540)),
    'CAM5080': ('20260819_170221_830_cam5080.jpg', (400,550,1100,750), (1250,500,1580,815), (175,275,325,845)),
    'CAM7650': ('20260819_170219_035_cam7650.jpg', (650,910,1300,1090), (1440,840,1780,1170), (350,700,510,1200)),
}


def read(path):
    return json.loads(path.read_text())


def compare_pairs(before, after):
    old = {r['sample_id']:r for r in read(before/'results.json')}
    checks = []
    for row in read(after/'results.json'):
        prior = old[row['sample_id']]
        files = [row['pipe_mask']]+[x['mask'] for x in row['instances']]
        checks.append(dict(sample_id=row['sample_id'],
            identical_masks=all(np.array_equal(np.asarray(Image.open(before/'all'/f)),
                np.asarray(Image.open(after/'all'/f))) for f in files),
            identical_labels=(before/'all/labels'/f"{row['sample_id']}.txt").read_bytes()==
                (after/'all/labels'/f"{row['sample_id']}.txt").read_bytes(),
            native_resolution=(prior['width'],prior['height'])==(row['width'],row['height']),
            glare_passed=row['glare_guard']['passed'], material_version=row['material_response_version']))
    assert all(r['identical_masks'] and r['identical_labels'] and r['native_resolution'] and
               r['glare_passed'] and r['material_version']==VERSION for r in checks),checks
    return checks


def main():
    env = OUT/'after_environments'
    rows = read(env/'results.json')
    (env/'render_plan.json').write_text(json.dumps(read(env/'review_plan.json'),indent=2))
    (env/'all/manifest.json').write_text(json.dumps(dict(classes=CLASSES,samples=rows),indent=2))
    validation,_ = validate_dataset(env)
    assert validation['valid'] and validation['complete'],validation
    assert len(rows)==21 and len({r['setup'] for r in rows})==8
    (env/'validation.json').write_text(json.dumps(validation,indent=2))
    write_gallery(env,validation,rows)
    checks = compare_pairs(OUT/'before_environments',env)
    matched = compare_pairs(OUT/'before',OUT/'final_matched')
    pairs = [r for r in rows if r.get('pair_role')=='lighting_variant']
    assert len(pairs)==2
    a,b = pairs
    lighting_check = dict(same_finish=a['material_detail_audit']==b['material_detail_audit'],
        same_labels=(env/'all/labels'/f"{a['sample_id']}.txt").read_bytes()==
                    (env/'all/labels'/f"{b['sample_id']}.txt").read_bytes(),
        changed_pixels=(env/'all'/a['image']).read_bytes()!=(env/'all'/b['image']).read_bytes())
    assert all(lighting_check.values()),lighting_check
    assets=OUT/'assets';assets.mkdir(exist_ok=True)
    sections=[]
    native_sheet=Image.new('RGB',(1740,700),(18,25,23));draw=ImageDraw.Draw(native_sheet)
    for index,row in enumerate(read(OUT/'final_matched/results.json')):
        camera=row['setup'];name,*boxes=REFERENCES[camera]
        real=REF/name
        paths=[real,OUT/'before/all'/row['image'],OUT/'final_matched/all'/row['image']]
        regions=[]
        for region,box in zip(('Body','Shoulder and rim','Mount'),boxes):
            figures=[]
            for col,(label,path) in enumerate(zip(('Real development photograph','Before','Refined'),paths)):
                im=Image.open(path).convert('RGB').crop(box)
                target=assets/f'{camera}_{region.split()[0]}_{col}.jpg';im.save(target,quality=98)
                figures.append(f'<figure><figcaption>{label}</figcaption><a href="assets/{target.name}"><img src="assets/{target.name}" alt="{label}, {region}"></a></figure>')
                if region=='Body':
                    im.thumbnail((570,195));native_sheet.paste(im,(col*580,index*230+26))
                    draw.text((col*580+6,index*230+6),camera+' / '+label,fill='white')
            regions.append(f'<details {"open" if region=="Body" else ""}><summary>{region} — open the crop at native pixel scale</summary><div class="three">'+''.join(figures)+'</div></details>')
        sections.append(f'<section><h2>{camera}</h2>'+''.join(regions)+'</section>')
    native_sheet.save(OUT/'comparison.jpg',quality=97)
    variants=[]
    for row in rows[:16:2]:
        stem=row['sample_id']
        for role,folder in [('before','before_environments'),('after','after_environments')]:
            im=Image.open(OUT/folder/'all'/row['image']);im.thumbnail((800,800))
            im.save(assets/f'{stem}_{role}.jpg',quality=95)
        variants.append(f'<figure><figcaption>{row["setup"]} · {row["width"]} × {row["height"]}</figcaption>'
            f'<img class="toggle" src="assets/{stem}_after.jpg" data-before="assets/{stem}_before.jpg" data-after="assets/{stem}_after.jpg" alt="{row["setup"]}">'
            f'<a href="after_environments/all/{row["image"]}">Full-resolution render</a></figure>')
    report=dict(valid=True,material_version=VERSION,environment_exports=validation,
        before_after_checks=checks,matched_camera_checks=matched,paired_lighting=lighting_check,
        shader_checks=read(OUT/'shader_validation.json'),detector_transfer_measured=False,
        notes='Different physical specimens in real/synthetic crops. Appearance review only; not a calibrated or blinded realism test.')
    (OUT/'validation.json').write_text(json.dumps(report,indent=2))
    (OUT/'REVIEW_ONLY.txt').write_text('Development controls, repeated specimens and reference photographs. Exclude from training and held-out evaluation datasets.\n')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tapered brass — shared finish refinement</title><style>
body{background:#111917;color:#e4ece7;font:16px/1.6 system-ui;margin:0;padding:28px}main{max-width:1800px;margin:auto}
h1{font-size:32px}h2,summary{color:#d5c18a}p{max-width:1100px}a{color:#a9d4eb}.three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}figure{margin:0;padding:10px;background:#1e2b25}figure img{width:100%;height:190px;object-fit:contain}figcaption{font-weight:600}.grid img{height:330px}details{margin:12px 0}section{border-top:1px solid #3b493f;margin-top:26px;padding-top:8px}button{background:#d5c18a;color:#14201a;border:0;border-radius:6px;padding:10px 18px;font:inherit;cursor:pointer}.note{border-left:3px solid #d5c18a;padding:12px 18px;background:#21332a}@media(max-width:800px){.grid,.three{grid-template-columns:1fr}body{padding:14px}}
</style><main><h1>Tapered brass: drawing, burnishing and contact wear</h1>
<p>The shared finish now includes irregular axial drawing texture, interrupted draw tracks, shoulder burnishing and faint neck rubs. Sparse handling marks sit over this manufacturing texture. Machine fixtures have localized wipe wear using a consistent physical scale.</p>
<p class="note">Compared against native camera crops, with an intermediate render pass refined after review. The real and synthetic images contain different physical specimens. Remaining gaps include the holder shape, the distribution of reflected light and the exact color of individual parts. Detector transfer and visual indistinguishability have not been established.</p>
<p>21 validation frames cover all eight environments, plus three matched-camera comparisons. Before/after masks and labels match exactly, dimensions are preserved, and every final export passes the glare guard. Two lighting views keep the same surface details. These review files are excluded from production datasets.</p>
<p><a href="after_environments/index.html">Inspect all 21 labeled examples</a> · <a href="validation.json">Validation details</a> · <a href="comparison.jpg">Surface comparison sheet</a></p>
<h2>Across the inspection environments</h2><p><button id="toggle" type="button">Show before</button> <span id="state">Showing refined finish</span></p><div class="grid">'''+''.join(variants)+'''</div>
<h2>Real camera patches</h2><p>Each crop preserves its original pixel dimensions. Click it for a 100% view; display scaling can hide small finish differences.</p>'''+''.join(sections)+'''
</main><script>let before=false;document.getElementById('toggle').onclick=()=>{before=!before;document.querySelectorAll('.toggle').forEach(im=>im.src=before?im.dataset.before:im.dataset.after);document.getElementById('state').textContent=before?'Showing previous finish':'Showing refined finish';document.getElementById('toggle').textContent=before?'Show refined':'Show before';};</script></html>'''
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(valid=True,environments=8,images=len(rows),matched_cameras=len(matched),paired_lighting=lighting_check)))


if __name__=='__main__':main()
