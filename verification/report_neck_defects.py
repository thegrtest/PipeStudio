"""Reference comparison and accepted export audit for the neck-defect review."""
import argparse
import hashlib
import html
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);args=ap.parse_args()
    root=args.folder.resolve();assets=root/'assets';assets.mkdir(exist_ok=True)
    data=json.loads((root/'all/manifest.json').read_text());cards=[];tiles=[]
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    refs=[]
    for camera in (1130,2829):
        name=f'20260905_012931_613_cam{camera}.jpg'
        source=ROOT.parent/'Synthetic/train/images/all'/name
        im=Image.open(source).convert('RGB');im.save(assets/name,quality=96)
        box=(465,77,532,144) if camera==1130 else (338,10,453,138)
        im.crop(box).resize((256,256)).save(assets/f'real_{camera}_crop.jpg',quality=97)
        label=ROOT.parent/'Synthetic/train/labels/all'/f'{source.stem}.txt'
        refs.append(dict(image=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                         labels=label.read_text().strip().splitlines()))
    labels=0;hashes=0
    for r in data['samples']:
        name=r['sample_id'];rgb=Image.open(root/'all'/r['image']).convert('RGB')
        assert rgb.size==(640,640)
        for rel,digest in r['output_sha256'].items():
            assert hashlib.sha256((root/'all'/rel).read_bytes()).hexdigest()==digest,rel
            hashes+=1
        lines=(root/'all/labels'/f'{name}.txt').read_text().splitlines()
        assert len(lines)==len(r['instances'])==1
        values=[float(v) for v in lines[0].split()]
        assert len(values)==5 and values[0]==1 and all(0<=v<=1 for v in values[1:])
        labels+=1
        assert r['glare_guard']['passed'] and r['visibility_guard']['passed']
        rgb.save(assets/f'{name}.jpg',quality=96)
        annotated=rgb.copy();draw=ImageDraw.Draw(annotated)
        a=r['instances'][0];x,y,w,h=a['bbox_xywh']
        draw.rectangle((x,y,x+w,y+h),outline='#76ffab',width=2)
        draw.text((x,max(0,y-21)),'Dent',font=font,fill='#76ffab')
        annotated.save(assets/f'{name}_labels.jpg',quality=96)
        check=r['visibility_guard']['instances'][0]
        control=Image.open(root/'all'/check['control_image']).convert('RGB')
        box=(max(0,x-18),max(0,y-18),min(640,x+w+18),min(640,y+h+18))
        strip=Image.new('RGB',(640,350),'#14202c');sd=ImageDraw.Draw(strip)
        for i,(im,title) in enumerate(((rgb,'Generated detail'),(control,'Same scene, defect removed'))):
            crop=im.crop(box);crop.thumbnail((310,310));scale=min(310/crop.width,310/crop.height)
            crop=crop.resize((round(crop.width*scale),round(crop.height*scale)))
            strip.paste(crop,(i*320+(320-crop.width)//2,32+(310-crop.height)//2));sd.text((i*320+7,6),title,font=font,fill='white')
        strip.save(assets/f'{name}_detail.jpg',quality=96)
        tile=Image.new('RGB',(320,356),'#14202c');tile.paste(annotated.resize((320,320)),(0,36))
        ImageDraw.Draw(tile).text((6,6),f"{r['setup']} / {r['size_bin']}",font=font,fill='white');tiles.append(tile)
        cards.append(f'''<article><h2>{html.escape(r['review_scenario'])} · {r['setup']}</h2>
        <div class="pair"><img src="assets/{name}.jpg"><img src="assets/{name}_labels.jpg"></div>
        <img src="assets/{name}_detail.jpg"><p>640 × 640 · Dent (class 1) · box {w} × {h} pixels ·
        visibility p90 {check['p90_change_codes']}/255 · shape/texture {check['shape_to_texture_ratio']:.2f} ·
        {len(r.get('visibility_repair_history',[]))} visibility retries.</p></article>''')
    sheet=Image.new('RGB',(960,356*((len(tiles)+2)//3)),'#0c141e')
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%3)*320,(i//3)*356))
    sheet.save(root/'contact_sheet.jpg',quality=95)
    (root/'audit.json').write_text(json.dumps(dict(accepted=len(data['samples']),labels=labels,
        verified_file_hashes=hashes,rejected=len(data.get('rejected',[])),references=refs),indent=2))
    (root/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Neck crescent · reference study</title>
    <style>body{{font:16px system-ui;background:#0c141e;color:#deebf5;max-width:1320px;margin:40px auto;padding:0 24px}}h1,h2{{color:white}}article{{padding:20px;margin:24px 0;background:#14202c;border-radius:12px}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}img{{max-width:100%}}p{{line-height:1.6}}a{{color:#8dd9ff}}</style>
    <h1>Neck crescent and rolled mouth · reference study</h1>
    <p>{len(data['samples'])} accepted synthetic frames at native 640 × 640. The source annotations label these defects as Dent (class 1).
    Curved recessed creases, unequal raised edges and a locally lowered mouth are modeled in the pipe surface.
    Lighting, camera softness, surface grain, defect position and size vary through the shared renderer.</p>
    <h2>Real references</h2><div class="pair"><img src="assets/20260905_012931_613_cam1130.jpg"><img src="assets/20260905_012931_613_cam2829.jpg"></div>
    <div class="pair"><div><img src="assets/real_1130_crop.jpg"></div><div><img src="assets/real_2829_crop.jpg"></div></div>
    <p>Real photos are comparison references only. Synthetic labels come from visible geometric support.
    Each accepted defect passes glare and matched-control visibility tests at model resolution. These checks measure visible image evidence; detector accuracy still requires evaluation.
    The rolled mouth remains a continuous wall, not a material tear.</p>
    <p><a href="all/manifest.json">Generation and visibility metadata</a> · <a href="audit.json">Export audit</a> · <a href="all/data.yaml">Class mapping</a></p>
    {''.join(cards)}''',encoding='utf-8')
    print(json.dumps(dict(accepted=len(data['samples']),labels=labels,verified_hashes=hashes)))

if __name__=='__main__':main()
