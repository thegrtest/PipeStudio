"""Screen only assembly-named synthetic images; deletion is a separate step."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from assembly_quality import inspect_support


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();root=args.root.resolve();groups=defaultdict(list);untouched=[]
    for image in root.rglob('*'):
        if image.suffix.lower() not in ('.png','.jpg','.jpeg') or not image.is_file():continue
        if not re.fullmatch(r'assembly_\d+_f\d+',image.stem):
            untouched.append(dict(path=str(image.relative_to(root)),sha256=hashlib.sha256(image.read_bytes()).hexdigest()));continue
        rel=list(image.relative_to(root).parts)
        if rel.count('images')!=1:raise ValueError('Unrecognized image path: '+str(image))
        rel[rel.index('images')]='labels';label=root/Path(*rel).with_suffix('.txt')
        groups[image.stem].append((image,label))
    def one(entry):
        stem,copies=entry;reports=[];bad=False
        # Different labels on a mirrored image must each be checked.
        by_label={label.read_text(encoding='utf-8') if label.exists() else None:(image,label) for image,label in copies}
        for text,(image,label) in by_label.items():
            reasons=[];boxes=[]
            if text is None:reasons=['missing_label']
            else:
                try:
                    for line in text.splitlines():
                        if not line.strip():continue
                        parts=list(map(float,line.split()))
                        if len(parts)!=5 or not np.isfinite(parts).all():raise ValueError()
                        c,x,y,w,h=parts
                        if not c.is_integer() or c<0 or min(w,h)<=0 or not (0<=x-w/2<=x+w/2<=1.000001 and 0<=y-h/2<=y+h/2<=1.000001):raise ValueError()
                        boxes.append((x,y,w,h))
                except ValueError:reasons=['invalid_label']
            with Image.open(image) as source:
                width,height=source.size;scale=min(1.,640/max(width,height))
                rgb=np.asarray(source.convert('RGB').resize((round(width*scale),round(height*scale)),Image.Resampling.BOX),dtype=np.float32)/255
            for index,(x,y,w,h) in enumerate(boxes):
                hh,ww=rgb.shape[:2];mask=np.zeros((hh,ww),dtype=bool)
                x0=max(0,round((x-w/2)*ww));x1=min(ww,round((x+w/2)*ww))
                y0=max(0,round((y-h/2)*hh));y1=min(hh,round((y+h/2)*hh))
                mask[y0:y1,x0:x1]=True
                check=inspect_support(rgb,mask,legacy_box=True)
                # Floating point text rounding must not inflate tiny boxes.
                if min(w*ww,h*hh)<5 or max(w*ww,h*hh)<9:
                    check['passed']=False;check['reasons'].append('subthreshold_yolo_box')
                reports.append(dict(label=str(label.relative_to(root)),box_index=index,**check))
                bad|=not check['passed']
            if reasons:bad=True;reports.append(dict(label=str(label.relative_to(root)),passed=False,reasons=reasons))
        return dict(stem=stem,remove=bad,checks=reports,copies=[dict(image=str(i.relative_to(root)),label=str(l.relative_to(root)),label_text=l.read_text(encoding='utf-8') if l.exists() else None) for i,l in copies])
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(one,groups.items()))
    rejected=[r for r in results if r['remove']]
    summary=dict(unique_assembly_images=len(results),remove_unique=len(rejected),retain_unique=len(results)-len(rejected),
        image_copies_to_remove=sum(len(r['copies']) for r in rejected),untouched_other_images=len(untouched),
        reasons=dict(Counter(reason for r in rejected for c in r['checks'] for reason in c['reasons'])))
    args.output.mkdir(parents=True,exist_ok=False)
    report=dict(root=str(root),summary=summary,screening_note='640-pixel input box-only audit. A pass is not proof of defect visibility; rejected pairs are removed as a whole.',results=results,untouched=untouched)
    (args.output/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
