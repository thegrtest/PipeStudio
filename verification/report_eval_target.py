"""Create an annotated review of the fleet preflight without changing its dataset."""
import argparse
import html
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    ap=argparse.ArgumentParser();ap.add_argument('dataset',type=Path);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();root=args.dataset.resolve();out=args.output.resolve();assets=out/'assets';assets.mkdir(parents=True,exist_ok=True)
    records=json.loads((root/'all/manifest.json').read_text())['samples']
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17);cards=[];tiles=[]
    for r in records:
        im=Image.open(root/'all'/r['image']).convert('RGB');stem=r['sample_id'];im.save(assets/(stem+'.jpg'),quality=96)
        labeled=im.copy();draw=ImageDraw.Draw(labeled)
        for a in r['instances']:
            x,y,w,h=a['bbox_xywh'];draw.rectangle((x,y,x+w,y+h),outline='#80ffad',width=2)
            draw.text((max(0,x),max(0,y-20)),a['kind'],font=font,fill='#80ffad')
        labeled.save(assets/(stem+'_labels.jpg'),quality=96)
        tile=Image.new('RGB',(320,365),'#17222c');tile.paste(labeled.resize((320,320)),(0,40))
        d=ImageDraw.Draw(tile);d.text((4,3),r['setup']+' / '+r['target_family'],font=font,fill='white');tiles.append(tile)
        checks=[]
        for check in r['visibility_guard']['instances']:
            a=r['instances'][check['instance_index']];x,y,w,h=a['bbox_xywh']
            bounds=(max(0,x-20),max(0,y-20),min(im.width,x+w+20),min(im.height,y+h+20))
            control=Image.open(root/'all'/check['control_image']).convert('RGB')
            crops=Image.new('RGB',(560,280),'#101920');d=ImageDraw.Draw(crops)
            for j,(source,label) in enumerate(((im,'Defect'),(control,'Same scene: this defect removed'))):
                crop=source.crop(bounds);crop.thumbnail((270,240));crops.paste(crop,(j*280+(270-crop.width)//2,30+(240-crop.height)//2));d.text((j*280+4,4),label,font=font,fill='white')
            name=stem+f'_detail_{check["instance_index"]}.jpg';crops.save(assets/name,quality=96)
            checks.append(f'<details><summary>{a["kind"]}: {w:.0f} × {h:.0f} pixels · visibility passed</summary><img src="assets/{name}"><p>p90 change: {check["p90_change_codes"]}/255; changed support: {check["changed_fraction"]:.0%}; shape/texture: {check["shape_to_texture_ratio"]}.</p></details>')
        cards.append(f'''<article><h2>{html.escape(r['setup']+' / '+r['review_scenario'])}</h2><p>{html.escape(stem)} · 640 × 640 · {len(r['instances'])} labels</p>
          <div class="pair"><a href="assets/{stem}.jpg"><img src="assets/{stem}.jpg"></a><a href="assets/{stem}_labels.jpg"><img src="assets/{stem}_labels.jpg"></a></div>
          {''.join(checks) or '<p>Clean control: intentional empty label file. Keep for training.</p>'}</article>''')
    sheet=Image.new('RGB',(960,365*((len(tiles)+2)//3)),'#10151e')
    for i,t in enumerate(tiles):sheet.paste(t,((i%3)*320,(i//3)*365))
    sheet.save(out/'contact.jpg',quality=95)
    content='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Targeted evaluation-gap generation</title>
    <style>body{background:#0e1720;color:#e3edf5;font:16px/1.6 system-ui;max-width:1320px;margin:32px auto;padding:0 24px}h1{line-height:1.2}article{background:#1b2936;border:1px solid #334653;border-radius:12px;padding:22px;margin:24px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:15px}img{max-width:100%;display:block}a{color:#a6dcff}details{margin-top:15px}summary{cursor:pointer;color:#a1ebbd}p{color:#c3d1dc}@media(max-width:760px){.pair{grid-template-columns:1fr}}</style>
    <h1>Targeted defects for the weak camera views</h1><p>Preflight images from DGX and AGX using the existing procedural renderer. Small body dents, broad shallow depressions, narrow neck folds, mixed defects and clean controls. Native 640 × 640 matches the supplied square-camera references.</p>
    <p>The production plan has 3,000 training images: 1,000 per view, 1,350 Fold-primary, 1,350 Dent-primary, and 300 clean controls. It includes 600 two-defect and 600 three-defect scenes. No synthetic images are assigned to validation.</p>
    <p>Each geometric label is checked against a render with only that defect removed, at model input size. Glare and visibility checks are passed before publication. These checks establish visible rendered evidence, not improvement in real-world YOLOX accuracy.</p>
    <p><a href="../eval_gap_20260923_232143/index.html">Baseline evaluation findings</a> · <a href="contact.jpg">Contact sheet</a></p>'''+''.join(cards)+'</html>'
    (out/'index.html').write_text(content,encoding='utf-8')
    stats=dict(images=len(records),labels=sum(len(r['instances']) for r in records),
               all_glare_passed=all(r['glare_guard']['passed'] for r in records),
               all_visibility_passed=all(r['visibility_guard']['passed'] for r in records),
               depth_repairs=sum(len(r.get('visibility_repair_history',[])) for r in records),
               angle_retries=sum(r.get('visibility_reposition_attempt',0) for r in records))
    (out/'preflight_summary.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats,indent=2));print(out/'index.html')


if __name__=='__main__':main()
