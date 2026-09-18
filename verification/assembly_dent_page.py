"""Native scene and magnified geometric-support review for the small dents."""
import argparse
import html
import json
from pathlib import Path
import shutil
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]

def build(root):
    root=Path(root).resolve();assets=root/'review_assets';assets.mkdir(exist_ok=True)
    reference=Path(r'C:\Users\daugh\Downloads\CheckWeighShell\CheckWeighShell\images\20260904_051433_717_cam3936.jpg')
    shutil.copy2(reference,assets/'real.jpg')
    old=ROOT/'verification/assembly_realism_v2_final/balanced/all/images/assembly_0000260915_f001.png'
    shutil.copy2(old,assets/'previous.png')
    images=[];cards=[];rows=[]
    for path in sorted((root/'metadata').glob('*.json')):
        info=json.loads(path.read_text());im=Image.open(root/info['image']).convert('RGB')
        recipe=info['recipe'];items=recipe['instances']
        family=items[0].get('dent_family',items[0]['kind']) if items else 'good'
        boxes=[a['bbox_xywh'] for a in info['parts'] if a['specimen_id']==recipe['specimen_id']]
        x=min(b[0] for b in boxes)-18;y=min(b[1] for b in boxes)-28
        right=max(b[0]+b[2] for b in boxes)+18;bottom=max(b[1]+b[3] for b in boxes)+28
        crop=im.crop((x,y,right,bottom));crop.save(assets/(path.stem+'_part.png'))
        parts=[];defects=[]
        for field,target,color in [('parts',parts,'#69d9ff'),('annotations',defects,'#ff8263')]:
            for a in info[field]:
                bx,by,bw,bh=a['bbox_xywh']
                target.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}"/><text x="{bx}" y="{by-7}">{a["name"]}</text>')
        overlays='<g class="parts" stroke="#69d9ff" fill="#69d9ff">'+''.join(parts)+'</g><g class="defects" stroke="#ff8263" fill="#ff8263">'+''.join(defects)+'</g>'
        annotations=[a for a in info['annotations'] if a['specimen_id']==recipe['specimen_id']]
        sizes=', '.join(f'{a["bbox_xywh"][2]} × {a["bbox_xywh"][3]} px' for a in annotations) or 'No visible defect box'
        sizes+=' · '+recipe.get('lighting','BALANCED').replace('_',' ').title()
        detail=''
        if annotations:
            a=annotations[0];bx,by,bw,bh=a['bbox_xywh'];pad=32
            close=im.crop((bx-pad,by-pad,bx+bw+pad,by+bh+pad))
            close.save(assets/(path.stem+'_detail.png'))
            detail=f'<img class="close" src="review_assets/{path.stem}_detail.png" title="Magnified native defect crop">'
        cards.append(f'<article><header><h2>{html.escape(family.replace("_"," ").title())}</h2><p>{sizes} · seed {recipe["seed"]}</p></header><div class="scene"><img src="{info["image"]}"><svg viewBox="0 0 1920 1200">{overlays}</svg></div><div class="detail"><img class="part" src="review_assets/{path.stem}_part.png">{detail}</div></article>')
        rows.append(dict(sample=path.stem,family=family,visible_defect_sizes=[a['bbox_xywh'][2:] for a in annotations]))
        images.append(info['image'])
    (root/'review_summary.json').write_text(json.dumps(rows,indent=2))
    (root/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Small and shallow dents · Assembly Studio</title>
<style>:root{color-scheme:dark}body{margin:26px auto;padding:0 22px;max-width:1600px;background:#0d161d;color:#e2edf0;font:15px Segoe UI,system-ui}h1{font-size:30px}h2{font-size:18px;margin:0}p{color:#a3bdc8;line-height:1.6}.bar{position:sticky;top:0;background:#14252f;padding:14px;z-index:3;display:flex;gap:22px;border-radius:8px}.grid,.refs{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:20px 0}article{background:#172630;border:1px solid #29414e;border-radius:10px;overflow:hidden}header{padding:16px}header p{margin-bottom:0}img{display:block;width:100%}.scene{position:relative}.scene svg{position:absolute;inset:0;width:100%;height:100%;font-size:22px}svg rect{fill:none;stroke-width:3}svg text{stroke:none}.parts,.defects{display:none}.show-parts .parts,.show-defects .defects{display:block}.detail{display:flex;gap:12px;align-items:center;padding:12px;background:#101d25}.part{width:75%;object-fit:contain}.close{width:23%;image-rendering:auto;border:1px solid #3e626e}.note{padding:14px;background:#13232d;border-radius:8px}a{color:#8fe0ce}@media(max-width:900px){.grid,.refs{grid-template-columns:1fr}}input{accent-color:#71dcc2}</style>
<h1>Smaller dents, subtler reflections</h1><p>New dent mix: approximately 65% small circular, 20% broad shallow, 15% larger varied. Class ratios and fold coverage stay unchanged. Native 1920 × 1200 images; enlarged crops below each frame reveal the small features.</p>
<div class="bar"><label><input type="checkbox" onchange="document.body.classList.toggle('show-defects',this.checked)"> Defect boxes</label><label><input type="checkbox" onchange="document.body.classList.toggle('show-parts',this.checked)"> Shell / ferrule boxes</label></div>
<div class="refs"><article><header><h2>Real camera reference</h2></header><img src="review_assets/real.jpg"></article><article><header><h2>Previous refined environment</h2></header><img src="review_assets/previous.png"></article></div>
<p class="note">The updated scene replaces the flat pale rail with a curved metallic face, rounds the fastener ends, and reduces track bump. These remain inferred fixtures. Boxes follow visible geometric support; especially shallow dents may still be difficult to detect under some lighting. The real photograph is a review asset only, outside the synthetic image folders.</p>
<div class="grid">'''+''.join(cards)+'</div></html>',encoding='utf-8')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);build(p.parse_args().root)
