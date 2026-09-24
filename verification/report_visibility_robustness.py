"""Review real references, accepted RGB, labels and per-instance clean twins."""
import argparse
import html
import json
from pathlib import Path
import sys
from PIL import Image,ImageDraw,ImageFont
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from defect_visibility import DEFAULTS


def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);args=ap.parse_args()
    root=args.folder.resolve();assets=root/'assets';assets.mkdir(exist_ok=True)
    data=json.loads((root/'all/manifest.json').read_text())
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    source=ROOT.parent/'AllNew/september/images'
    refs=['20260905_014229_933_cam1489.jpg','20260905_012833_253_cam1489.jpg']
    for name in refs:
        with Image.open(source/name) as im:im.save(assets/name,quality=95)
    cards=[];tiles=[]
    for r in data['samples']:
        stem=r['sample_id'];rgb=Image.open(root/'all'/r['image']).convert('RGB')
        rgb.save(assets/(stem+'.jpg'),quality=96)
        labeled=rgb.copy();draw=ImageDraw.Draw(labeled)
        for a in r['instances']:
            x,y,w,h=a['bbox_xywh'];draw.rectangle((x,y,x+w,y+h),outline='#80ffad',width=2)
            draw.text((max(0,x),max(0,y-22)),f"{a['kind']} {a.get('instance_id','')}",font=font,fill='#80ffad')
        labeled.save(assets/(stem+'_labels.jpg'),quality=95)
        thumbnail=labeled.resize((320,320));tile=Image.new('RGB',(320,370),'#17202b');tile.paste(thumbnail,(0,40))
        ImageDraw.Draw(tile).text((5,5),r['review_scenario'][:35],fill='white',font=font);tiles.append(tile)
        comparisons=[]
        for check in r['visibility_guard']['instances']:
            a=r['instances'][check['instance_index']];control=Image.open(root/'all'/check['control_image']).convert('RGB')
            x,y,w,h=a['bbox_xywh'];pad=24
            box=(max(0,x-pad),max(0,y-pad),min(rgb.width,x+w+pad),min(rgb.height,y+h+pad))
            damage_crop=rgb.crop(box);control_crop=control.crop(box)
            delta=np.mean(np.abs(np.array(damage_crop,dtype=float)-np.array(control_crop,dtype=float)),axis=2)
            delta_img=Image.fromarray(np.uint8(np.clip(delta*8,0,255))).convert('RGB')
            strip=Image.new('RGB',(780,280),'#111923');d=ImageDraw.Draw(strip)
            for k,(im,title) in enumerate(((damage_crop,'Defect'),(control_crop,'This defect removed'),(delta_img,'RGB change x8 (QA only)'))):
                im=im.copy();im.thumbnail((250,240));strip.paste(im,(k*260+(250-im.width)//2,30+(240-im.height)//2));d.text((k*260+5,5),title,font=font,fill='white')
            comp=f'{stem}_instance_{check["instance_index"]}.jpg';strip.save(assets/comp,quality=96)
            comparisons.append(f'<p>Instance {check["instance_index"]}: p90 change {check["p90_change_codes"]}/255; {check["changed_fraction"]:.0%} of support changed; coherent cue {check["largest_changed_component"]} pixels; shape/texture ratio {check.get("shape_to_texture_ratio","first-pass check")}.</p><img src="assets/{comp}">')
        background=r.get('background_variation',{})
        thresholds=(r['visibility_guard']['instances'][0]['thresholds']
                    if r['visibility_guard']['instances'] else {})
        cards.append(f'''<article><h2>{html.escape(r['review_scenario'])}</h2>
        <p>{stem} · {r['width']} × {r['height']} · {r['surface_condition']} · {len(r.get('visibility_repair_history',[]))} visibility repairs</p>
        <div class="pair"><a href="assets/{stem}.jpg"><img src="assets/{stem}.jpg"></a><img src="assets/{stem}_labels.jpg"></div>
        {''.join(comparisons)}<details><summary>Background and visibility controls</summary><pre>{html.escape(json.dumps(dict(background=background,thresholds=thresholds),indent=2))}</pre></details></article>''')
    rejected_cards=[]
    for rejected in data.get('rejected',[]):
        stem=rejected['sample_id']
        audit=json.loads((root/'all/rejected'/(stem+'_visibility.json')).read_text())
        shots=[]
        for attempt in audit['attempts']:
            source=root/'all/rejected'/f'{stem}_attempt_{attempt["attempt"]}.png'
            if source.exists():
                name=source.stem+'.jpg'
                with Image.open(source) as im:im.convert('RGB').save(assets/name,quality=95)
                check=next(c for c in attempt['report']['instances'] if not c['passed'])
                shots.append(f'<div><img src="assets/{name}"><p>Attempt {attempt["attempt"]+1}; shape/texture {check.get("shape_to_texture_ratio","not measured")}; {html.escape(", ".join(check["reasons"]))}</p></div>')
        rejected_cards.append(f'<article><h2>Rejected: {html.escape(rejected["review_scenario"])}</h2><p>No positive training pair was exported for this candidate.</p><div class="pair">'+''.join(shots)+'</div></article>')
    sheet=Image.new('RGB',(320*3,370*((len(tiles)+2)//3)),'#10151e')
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%3)*320,(i//3)*370))
    sheet.save(root/'contact_sheet.jpg',quality=94)
    repairs=sum(len(r.get('visibility_repair_history',[])) for r in data['samples'])
    nlabels=sum(len(r['instances']) for r in data['samples'])
    versions=sorted({r['visibility_guard']['version'] for r in data['samples']})
    historical=('<p><strong>Earlier development pass:</strong> this version checks RGB change but does not yet require the shape to exceed surface texture. Use the final review for the stronger gate.</p>'
                if 'counterfactual-visibility-1' in versions else '')
    earlier=('<p><a href="../pass1/index.html">Earlier variety pass (development only; weaker visibility test)</a></p>'
             if root.name=='final' and (root.parent/'pass1/index.html').exists() else '')
    content=f'''<!doctype html><meta charset="utf-8"><title>Inverted camera · defect visibility review</title>
    <style>body{{background:#0d131c;color:#dce6ef;font:16px system-ui;max-width:1280px;margin:40px auto;padding:0 24px}}h1,h2{{color:#fff}}article{{margin:36px 0;padding:22px;background:#17212e;border-radius:12px}}p{{line-height:1.6}}img{{max-width:100%}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}pre{{overflow:auto}}a{{color:#93dbff}}</style>
    <h1>Inverted camera · visible defects and scene variation</h1>
    <p>Guard: {html.escape(', '.join(versions))}</p>{historical}{earlier}
    <p>{len(data['samples'])} accepted 640 × 640 development frames · {nlabels} defect boxes · {repairs} repair attempts · {len(data.get('rejected',[]))} rejected candidates after bounded retries.</p>
    <p>Same geometry sampling, material, camera, noise seed and final illumination for each defect/control comparison. Positive labels are exported only after a coherent RGB cue survives the camera response at model size. This is an observability proxy, not proof of YOLOX detection or real-world transfer.</p>
    <h2>Your real references</h2><div class="pair"><img src="assets/{refs[0]}"><img src="assets/{refs[1]}"></div>
    <p>Small low-contrast body dents and an extreme collapsed outlet. The current larger synthetic buckle remains a closed surface; it does not reproduce the torn/open topology in the second photograph. Real photographs appear here only as development references.</p>
    <p>Background changes are limited to small hardware offsets, jaw spacing, wheel height, finish roughness, texture scale and tint. Lighting, blur, finish and class balancing remain in the existing recipe. Clean controls share the same nuisance settings. Existing fleet jobs were not replaced.</p>
    {''.join(cards)}{''.join(rejected_cards)}<p>Each sample records its actual thresholds above. Production uses geometry labels, not the amplified QA difference images.</p>'''
    (root/'index.html').write_text(content,encoding='utf-8')
    print(root/'index.html');print(dict(accepted=len(data['samples']),labels=nlabels,repairs=repairs,rejected=len(data.get('rejected',[]))))


if __name__=='__main__':main()
