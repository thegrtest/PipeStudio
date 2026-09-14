"""Validate flashlight masks/labels, export COCO, and build an overlay gallery."""
import argparse
import hashlib
import html
import json
from pathlib import Path
from PIL import Image, ImageDraw


def review(folder,regions=False):
    folder=Path(folder).resolve()
    manifest=json.loads((folder/'manifest.json').read_text())
    if isinstance(manifest['classes'],dict):
        manifest['classes']=[manifest['classes'][str(i)] for i in range(len(manifest['classes']))]
    if regions:
        manifest['classes']=['top','body','Brass Face','Plastic Face']
    report=folder/('region-review' if regions else 'review')
    report.mkdir(exist_ok=True)
    coco=dict(images=[],annotations=[],categories=[dict(id=i,name=name) for i,name in enumerate(manifest['classes'])])
    cards=[]
    total=0
    empty=0
    for image_id,info in enumerate(manifest['images'],1):
        path=folder/info['image']
        with Image.open(path) as original:
            image=original.convert('RGB')
        w,h=image.size
        assert (w,h)==(info['width'],info['height']),path
        for relative,digest in info.get('sha256',{}).items():
            assert hashlib.sha256((folder/relative).read_bytes()).hexdigest()==digest,relative
        draw=ImageDraw.Draw(image)
        expected=[]
        for a in info['region_annotations' if regions else 'annotations']:
            with Image.open(folder/a['mask']) as source:
                mask=source.convert('L')
            assert mask.size==(w,h),a
            histogram=mask.histogram()
            assert sum(histogram[1:255])==0,a
            visible=histogram[255]
            assert visible==a['visible_pixels'],a
            bounds=mask.getbbox()
            bbox=[bounds[0],bounds[1],bounds[2]-bounds[0],bounds[3]-bounds[1]] if bounds else None
            assert bbox==a['bbox_xywh'],a
            if bbox:
                x,y,bw,bh=bbox
                expected.append([a['class_id'],(x+bw/2)/w,(y+bh/2)/h,bw/w,bh/h])
                coco['annotations'].append(dict(id=len(coco['annotations'])+1,image_id=image_id,
                                               category_id=a['class_id'],bbox=bbox,area=visible,iscrowd=0))
                color=['#54e686','#ffbd42','#66caff','#ce8cff','#ff668d','#38e8df','#ff934f'][a['class_id']]
                draw.rectangle((x,y,x+bw-1,y+bh-1),outline=color,width=2)
                draw.text((x,max(1,y-14)),a['class_name'],fill=color,stroke_width=1,stroke_fill='black')
                total+=1
        label=folder/('regions/labels' if regions else 'labels')/f'{path.stem}.txt'
        actual=[[float(x) for x in row.split()] for row in label.read_text().splitlines() if row.strip()]
        assert len(actual)==len(expected),label
        if actual:
            assert all(len(row)==5 for row in actual),label
            assert all(abs(a-b)<=1e-7 for row,want in zip(actual,expected) for a,b in zip(row,want)),label
        else:
            empty+=1
        coco['images'].append(dict(id=image_id,file_name=info['image'],width=w,height=h,
                                   specimen_group=info['specimen_group'],split=info['split']))
        overlay=report/f'{path.stem}.jpg'
        image.thumbnail((1000,700))
        image.save(overlay,quality=92)
        noun='regions' if regions else 'defects'
        cards.append(f'<article><a href="../{html.escape(info["image"])}"><img src="{overlay.name}"></a><p>{path.stem} · {len(expected)} visible {noun} · seed {info["recipe"]["seed"]}</p></article>')
    (folder/('regions.review.coco.json' if regions else 'annotations.coco.json')).write_text(json.dumps(coco,indent=2))
    result=dict(images=len(manifest['images']),visible_defects=total,empty_label_images=empty,validation='passed')
    if regions:result['visible_regions']=result.pop('visible_defects')
    (report/'validation.json').write_text(json.dumps(result,indent=2))
    (report/'index.html').write_text('<!doctype html><html><meta charset="utf-8"><title>Flashlight Lab review</title><style>body{background:#171b20;color:#eef0f3;font:16px system-ui;max-width:1300px;margin:32px auto;padding:20px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:20px}img{width:100%}article{margin:0;background:#242b32;padding:12px}p{margin:10px 0}</style><h1>Flashlight Lab — Blender renders</h1><p>Visible geometric-support boxes: green plastic dent; amber metal dent; blue metal scratch. Click to view the original render.</p><main>'+''.join(cards)+'</main></html>',encoding='utf-8')
    print(json.dumps(result))
    page=report/'index.html'
    legend='Region instance boxes: green top; amber body; blue Brass Face; purple Plastic Face.' if regions else 'Defect support boxes: green plastic dent; amber metal dent; blue metal scratch; purple plastic scratch; pink open center; teal protruding crimp; orange body twist.'
    page.write_text(page.read_text(encoding='utf-8').replace('Visible geometric-support boxes: green plastic dent; amber metal dent; blue metal scratch.',legend),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',type=Path)
    parser.add_argument('--regions',action='store_true')
    args=parser.parse_args()
    review(args.folder,args.regions)
