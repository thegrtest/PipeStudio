"""Build a visual review without changing source photographs or training data."""
import html
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification/soap_reference_20260923'
REAL=ROOT.parent/'TestDataset/all/2026-08-18/images'
REFERENCES={
    'CAM7650':'20260813_125949_296_cam7650.jpg',
    'CAM5080':'20260812_174502_805_cam5080.jpg',
    'CAM2534':'20260813_124051_709_cam2534.jpg',
}
REGIONS={'CAM7650':(180,810,1640,1200),'CAM5080':(210,470,1610,855),'CAM2534':(585,205,1695,520)}


def build():
    assets=OUT/'assets';assets.mkdir(exist_ok=True)
    manifest=json.loads((OUT/'final/all/manifest.json').read_text())
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
    cards=[]; checks=[]; annotation_count=0
    for index,row in enumerate(manifest['samples']):
        stem=row['sample_id'];camera=row['setup']
        image=Image.open(OUT/'final/all'/row['image']).convert('RGB')
        assert image.size==(1936,1216)
        image.save(assets/(stem+'.jpg'),quality=96)
        reference=('20260813_125905_445_cam7650.jpg' if camera=='CAM7650'
                   and row['instances'][0]['spot']['subtype']=='coalesced_residue' else REFERENCES[camera])
        real=Image.open(REAL/reference).convert('RGB')
        boxes=[]
        label_path=OUT/'final/all/labels'/(stem+'.txt')
        labels=label_path.read_text().splitlines()
        assert len(labels)==len(row['instances'])
        for label,instance in zip(labels,row['instances']):
            fields=label.split();assert len(fields)==5 and fields[0]=='2'
            assert all(0<=float(v)<=1 for v in fields[1:])
            x,y,w,h=instance['bbox_xywh']
            assert w>0 and h>0 and instance['visible_mask_pixels']>=8
            boxes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>')
            annotation_count+=1
        crop=REGIONS[camera]
        # Equal source-pixel scale for real and synthetic part crops.
        rw,rh=crop[2]-crop[0],crop[3]-crop[1]
        board=Image.new('RGB',(rw,2*(rh+38)),(20,26,30));draw=ImageDraw.Draw(board)
        for i,(im,title) in enumerate(((real,'REAL - supplied camera reference'),(image,'SYNTHETIC - procedural soap film'))):
            y=i*(rh+38);draw.text((10,y+3),title,font=font,fill='#e0e8ed')
            board.paste(im.crop(crop),(0,y+38))
        board.save(assets/(stem+'_compare.jpg'),quality=96)
        subtypes=', '.join(sorted({i['spot']['subtype'].replace('_',' ') for i in row['instances']}))
        cards.append(f'''<article><h2>{camera} · {html.escape(subtypes)}</h2>
          <p>{len(labels)} soap labels · 1936 × 1216 · independent specimen seed<br>Reference: {reference}</p>
          <a href="assets/{stem}_compare.jpg"><img src="assets/{stem}_compare.jpg" alt="Real above, synthetic below at the same pixel scale"></a>
          <details><summary>Full frame and labels</summary><div class="frame"><a href="final/all/images/{stem}.png"><img src="assets/{stem}.jpg"></a>
          <svg viewBox="0 0 1936 1216">{''.join(boxes)}</svg></div>
          <a href="final/all/labels/{stem}.txt">YOLO labels</a> · <a href="final/all/metadata/{stem}.json">Parameters and masks</a></details></article>''')
        check=OUT/'final/controls'/(stem+'_visibility.json')
        if check.exists():
            checks.extend(dict(sample_id=stem,**item) for item in json.loads(check.read_text())['instances'])
    summary=dict(images=len(manifest['samples']),soap_labels=annotation_count,class_id=2,
                 dimensions=[1936,1216],rgb_visibility_checks=checks,
                 synthetic_only=True,development_preview=True,reference_photos_added_to_dataset=False)
    (OUT/'validation.json').write_text(json.dumps(summary,indent=2))
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Soap residue · reference comparison</title><style>
    body{margin:0;background:#10171d;color:#dce4ea;font:16px/1.55 system-ui}main{max-width:1240px;margin:40px auto;padding:0 24px}
    h1{font-size:38px;line-height:1.15}h2{font-size:22px;margin-bottom:4px}p{color:#afbec9}a{color:#90d3eb}
    article{background:#1c252d;border:1px solid #38434d;border-radius:12px;padding:22px;margin:26px 0}
    img{width:100%;display:block}details{margin-top:14px}summary{cursor:pointer}button{padding:10px 18px;background:#9bcd94;border:0;border-radius:5px;cursor:pointer}
    .frame{position:relative;margin:16px 0}svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;display:none}
    .labels svg{display:block}rect{fill:none;stroke:#9fff79;stroke-width:3}.badge{color:#b8d9a1}
    </style><main><p class="badge">PIPESTUDIO · SOAP CLASS REVIEW</p><h1>Thin, pale residue on drawn brass</h1>
    <p>Six native-resolution synthetic examples, compared with the supplied camera photographs. Real image above; generated image below, using equal-sized crops. Click any comparison for the full crop.</p>
    <p>Three material passes refined the yellow/cream tint, irregular boundaries, faint film, and joined islands. These are development previews; visual similarity and RGB-change checks do not establish real-world model accuracy.</p>
    <button onclick="document.body.classList.toggle('labels')">Toggle soap boxes in full frames</button>
    '''+''.join(cards)+'''<p>YOLO class 2: Soap stain. Original camera images were used only as references. Active fleet jobs and training datasets were not changed.</p></main></html>'''
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':build()
