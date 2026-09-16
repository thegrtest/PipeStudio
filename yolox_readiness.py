"""Read-only YOLO label/input-scale audit. No training or source mutation.

Run: python yolox_readiness.py --synthetic ../thegreatawkaning
     --real ../BrassModel11/all/2026-08-19GodsLight --output verification/yolox_readiness
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import numpy as np
from PIL import Image

CLASS_NAMES={'0':'Fold','1':'Dent','2':'Soap stain','3':'Oil / acid stain'}
IMAGE_EXTS={'.png','.jpg','.jpeg','.bmp','.tif','.tiff'}


def parse_labels(text):
    rows=[]
    for number,line in enumerate(text.splitlines(),1):
        if not line.strip():continue
        values=[float(v) for v in line.split()]
        if len(values)!=5 or not np.isfinite(values).all():raise ValueError(f'Invalid row {number}')
        cid,x,y,w,h=values
        if cid not in (0,1,2,3) or min(w,h)<=0 or max(w,h)>1:
            raise ValueError(f'Invalid class or extent, row {number}')
        if x-w/2 < -1e-5 or y-h/2 < -1e-5 or x+w/2 > 1.00001 or y+h/2 > 1.00001:
            raise ValueError(f'Box outside frame, row {number}')
        rows.append((int(cid),x,y,w,h))
    return rows


def input_dimensions(box,width,height,size):
    scale=size/max(width,height)
    return box[3]*width*scale,box[4]*height*scale


def camera_name(stem):
    value=stem.lower()
    for camera in ('cam2534','cam5080','cam7650','foreground','inverted','upright','machine','studio'):
        if re.search(r'(?:^|_)'+camera+r'(?:_|$)',value):return camera.upper()
    return 'UNKNOWN'


def summarize(root,input_sizes=(640,960)):
    root=Path(root).resolve()
    if (root/'all/images').is_dir():root=root/'all'
    if not (root/'images').is_dir() or not (root/'labels').is_dir():
        raise ValueError('Expected images/labels or all/images/labels at '+str(root))
    counts=Counter();classes=Counter();cameras=Counter();dimensions=Counter()
    values=defaultdict(list);by_camera=defaultdict(list);issues=[];inventory=hashlib.sha256()
    matched_labels=set()
    for image in sorted((root/'images').iterdir()):
        if image.suffix.lower() not in IMAGE_EXTS:continue
        counts['images']+=1
        label=root/'labels'/(image.stem+'.txt')
        if not label.exists():
            counts['missing_labels']+=1;issues.append(dict(image=str(image),reason='missing_label'));continue
        matched_labels.add(label.name)
        try:
            with Image.open(image) as raster:width,height=raster.size
            content=label.read_text(encoding='utf-8-sig');rows=parse_labels(content)
        except (OSError,ValueError) as error:
            counts['invalid_pairs']+=1;issues.append(dict(image=str(image),reason=str(error)));continue
        counts['valid_pairs']+=1;counts['empty_labels']+=not rows
        counts['mixed_class_images']+=len({r[0] for r in rows})>1
        dimensions[f'{width}x{height}']+=1
        camera=camera_name(image.stem);cameras[camera]+=1
        stat=image.stat()
        # Inventory signature detects membership/label/stat changes; not a pixel
        # hash or a replacement for the generator's committed-file checksums.
        inventory.update(json.dumps([image.name,stat.st_size,stat.st_mtime_ns,content]).encode())
        for box in rows:
            cid=str(box[0]);classes[cid]+=1
            for size in input_sizes:
                w,h=input_dimensions(box,width,height,size)
                values[(cid,size)].append(min(w,h))
                by_camera[(camera,cid,size)].append(min(w,h))
    counts['orphan_labels']=sum(p.name not in matched_labels for p in (root/'labels').glob('*.txt') if p.name!='classes.txt')
    def distribution(items):
        a=np.asarray(items)
        return dict(count=len(items),short_side_q10_q50_q90=np.quantile(a,[.1,.5,.9]).round(2).tolist(),
                    below_2px=int((a<2).sum()),below_4px=int((a<4).sum()),below_8px=int((a<8).sum()))
    return dict(root=str(root),counts=dict(counts),instance_classes=dict(classes),cameras=dict(cameras),
                image_dimensions=dict(dimensions),inventory_signature=inventory.hexdigest(),
                signature_definition='Image names, sizes, mtimes and label contents; not image-content hashes.',
                size_by_class={f'{cid}@{size}':distribution(items) for (cid,size),items in sorted(values.items())},
                size_by_camera_class={f'{camera}/{cid}@{size}':distribution(items) for (camera,cid,size),items in sorted(by_camera.items())},
                issues=issues)


def write_report(sources,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    result=dict(purpose='Input-scale and label readiness; does not predict real-world YOLOX accuracy.',
                class_names=CLASS_NAMES,sources=sources)
    (output/'audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    parts=['<!doctype html><meta charset="utf-8"><title>YOLOX readiness</title>',
           '<style>body{font:16px system-ui;background:#121917;color:#e7eee9;margin:36px;max-width:1200px}table{border-collapse:collapse;width:100%;margin:24px 0}td,th{text-align:left;border-bottom:1px solid #3c5145;padding:10px}p{line-height:1.6;color:#c5d2c8}h2{margin-top:48px}a{color:#90daba}</style>',
           '<h1>What reaches YOLOX?</h1><p>Native image resolution is preserved during rendering. This audit measures defect thickness after the aspect-preserving resize to 640 and 960 pixels. Tiny-box counts are review flags, not reasons to delete difficult labels.</p>',
           '<p>This report does not establish transfer accuracy. Keep the first model and dataset fixed; judge subsequent experiments against the same real development frames.</p>']
    for name,source in sources.items():
        c=source['counts'];parts.append(f'<h2>{html.escape(name)}</h2><p>{c.get("images",0):,} images; {c.get("valid_pairs",0):,} valid pairs; {c.get("empty_labels",0):,} explicit empty labels; {c.get("mixed_class_images",0):,} mixed-class images. Missing labels: {c.get("missing_labels",0)}; invalid pairs: {c.get("invalid_pairs",0)}.</p>')
        parts.append('<table><tr><th>Class / input</th><th>Instances</th><th>Thickness p10 / median / p90</th><th>Under 4 px</th><th>Under 8 px</th></tr>')
        for key,d in source['size_by_class'].items():
            cid,size=key.split('@')
            parts.append(f'<tr><td>{CLASS_NAMES[cid]} / {size}</td><td>{d["count"]}</td><td>{d["short_side_q10_q50_q90"]}</td><td>{d["below_4px"]}</td><td>{d["below_8px"]}</td></tr>')
        parts.append('</table>')
    parts.append('<h2>Next experiment</h2><p>Keep 10% good specimens, balance four primary defect classes, and mix two classes in 40% of defective images. Keep all eight environments equally represented. Apply moderate camera variation independently of labels and retain the glare check.</p><p>The real development annotations may cover Fold/Dent only. Unannotated Soap/Oil marks cannot establish precision for those classes. Review those labels before reporting stain metrics.</p><p>Known August 19/20 references have already influenced the renderer. They are development data. Reserve fresh sessions and complete part sequences for the final holdout.</p><p><a href="audit.json">Detailed counts by camera and class</a></p>')
    (output/'index.html').write_text('\n'.join(parts),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic',type=Path,required=True)
    parser.add_argument('--real',type=Path,action='append',default=[])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sources={'Synthetic bundle':summarize(args.synthetic)}
    for root in args.real:sources['Real development: '+root.name]=summarize(root)
    write_report(sources,args.output)
    print(json.dumps({name:source['counts'] for name,source in sources.items()},indent=2))
