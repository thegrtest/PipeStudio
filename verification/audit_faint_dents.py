"""Read-only visual sampling of Synthetic dent labels; never edits a dataset.

Geometry-depth selection is a risk sample, not a prevalence estimate. Neither
normal texture contrast nor a projected support box proves defect visibility.
"""
import html
import json
import random
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT.parent/'Synthetic'
OUT=ROOT/'verification/faint_dents_20260923'


def main():
    source=json.loads((OUT/'source_rows.json').read_text())
    files={p.stem:p for p in (DATA/'all/images').iterdir() if p.suffix.lower() in ('.png','.jpg','.jpeg')}
    split_files={part:{p.stem:p for p in (DATA/part/'images').rglob('*') if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg')}
                 for part in ('train','val')}
    candidates=[]
    for sid,row in source.items():
        if sid not in files: continue
        labels=[list(map(float,s.split())) for s in (DATA/'all/labels'/f'{sid}.txt').read_text().splitlines() if s.strip()]
        if len(labels)!=len(row['instances']): continue
        for index,item in enumerate(row['instances']):
            if item['kind']!='DENT' or labels[index][0]!=1:continue
            spec=item['spec']
            # Dimensionless axial slope proxy, not an optical visibility score.
            slope=spec['depth']*spec['radius']/(spec['width']*spec['length'])
            candidates.append(dict(sample_id=sid,instance=index,setup=row['setup'],
                style=spec['defect_style'],depth=spec['depth'],width=spec['width'],arc=spec['arc'],
                slope_proxy=slope,label=labels[index],source_plan=row['source_plan'],
                size_bin=item['size_bin'],settings=row['settings'],spec=spec))
    selected=[];used=set()
    def take(rows,n,reason):
        for r in rows:
            key=(r['sample_id'],r['instance'])
            if key in used:continue
            selected.append({**r,'selection':reason});used.add(key)
            n-=1
            if not n:break
    inverted=[r for r in candidates if r['setup']=='INVERTED']
    take(sorted((r for r in inverted if r['style']=='SHALLOW_SWEEP'),key=lambda r:r['slope_proxy']),12,'inverted: lowest sweep slope')
    rng=random.Random(230924)
    shuffled=[r for r in inverted if r['style']=='SHALLOW_SWEEP'];rng.shuffle(shuffled)
    take(shuffled,6,'inverted: seeded random sweeps')
    shuffled=[r for r in inverted if r['style']!='SHALLOW_SWEEP'];rng.shuffle(shuffled)
    take(shuffled,6,'inverted: other dent controls')
    for setup in sorted({r['setup'] for r in candidates}-{'INVERTED'}):
        take(sorted((r for r in candidates if r['setup']==setup and r['style']=='SHALLOW_SWEEP'),key=lambda r:r['slope_proxy']),4,'other cameras: lowest sweep slope')
    (OUT/'assets').mkdir(exist_ok=True)
    cards=[]
    for index,r in enumerate(selected):
        path=files[r['sample_id']]
        with Image.open(path) as opened:im=opened.convert('RGB')
        w,h=im.size;scale=640/max(w,h)
        r['source_image']=str(path.resolve());r['dimensions']=[w,h]
        _,cx,cy,bw,bh=r['label'];box=[(cx-bw/2)*w,(cy-bh/2)*h,(cx+bw/2)*w,(cy+bh/2)*h]
        # Raw pixels and separately boxed context avoid hiding shallow shading.
        pad=max(24,min(bw*w,bh*h)*.40)
        crop=(max(0,int(box[0]-pad)),max(0,int(box[1]-pad)),min(w,int(box[2]+pad+1)),min(h,int(box[3]+pad+1)))
        raw=im.crop(crop);raw.save(OUT/'assets'/f'{index:02d}_native.png')
        down=im.resize((round(w*scale),round(h*scale)),Image.Resampling.BILINEAR)
        sx,sy=round(cx*down.width),round(cy*down.height)
        model_crop=down.crop((sx-96,sy-80,sx+96,sy+80))
        model_crop.save(OUT/'assets'/f'{index:02d}_640.png')
        r['box_at_640']=[round(bw*w*scale,2),round(bh*h*scale,2)]
        context=im.copy();d=ImageDraw.Draw(context);d.rectangle(box,outline='#ff5f4a',width=max(1,round(w/640)))
        context.thumbnail((640,400));context.save(OUT/'assets'/f'{index:02d}_context.jpg',quality=92)
        r['review_index']=index
        in_train=path.stem in split_files['train'];in_val=path.stem in split_files['val']
        r['splits']=[k for k,v in [('train',in_train),('val',in_val)] if v]
        title=f"{index:02d} {r['sample_id']} / dent {r['instance']}"
        cards.append(f'<article><h2>{html.escape(title)}</h2><p>{r["style"]}; depth {r["depth"]:.4f} × radius; box at 640: {r["box_at_640"]}; {r["splits"]}</p><div><img src="assets/{index:02d}_context.jpg"><img src="assets/{index:02d}_native.png"><img width="192" height="160" src="assets/{index:02d}_640.png"></div><p>Left: location; middle: native unboxed crop; right: crop after resize to 640, shown at 1:1.</p></article>')
    for start in range(0,len(selected),12):
        page=Image.new('RGB',(4*300,3*226),'#181b1e');d=ImageDraw.Draw(page)
        for pos,r in enumerate(selected[start:start+12]):
            idx=r['review_index'];x=pos%4*300;y=pos//4*226
            crop=Image.open(OUT/'assets'/f'{idx:02d}_640.png').resize((240,200),Image.Resampling.NEAREST)
            page.paste(crop,(x,y));d.text((x,y+201),f'{idx:02d} {r["setup"]} {r["style"]}',fill='white')
            d.text((x,y+214),f'depth {r["depth"]:.3f}  {r["sample_id"].split("_")[1]}',fill='white')
        page.save(OUT/f'crops_{start//12:02d}.jpg',quality=96)
    summary=dict(dataset=str(DATA),matched_synthetic_dent_instances=len(candidates),styles=dict(Counter(r['style'] for r in candidates)),review_count=len(selected),selection='Risk sample, not prevalence estimate. Only synthetic records with exact sample ID and aligned label class were included.',dataset_modified=False)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    (OUT/'review.json').write_text(json.dumps(selected,indent=2))
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Dent visibility investigation</title><style>body{background:#14191d;color:#e6ecee;font:15px system-ui;margin:24px}article{padding:16px;margin-bottom:22px;background:#222b30}h2{font-size:16px}img{object-fit:contain;max-width:640px;vertical-align:top;margin:5px}p{color:#c4d0d7}</style><h1>Dent visibility investigation — read-only</h1><p>Native crops and 640-input crops from Desktop/Synthetic. Selected for shallow geometry risk; this is not an estimate of how many labels are bad. No dataset or running worker was changed.</p>'+''.join(cards),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
