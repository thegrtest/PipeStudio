"""Read-only snapshot of committed fleet images, with native and model-size QA."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shlex
import sys

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'remote')]
from fleet import run
from fleet_common import read_json,inside,safe_name
from assembly_plan import visible_box,yolo_line


def review(runs,output,limit=6):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    nodes=read_json(ROOT/'fleet_nodes.local.json')['nodes'];cards=[];receipts=[]
    for target in runs:
        name,job=target.split('=',1);job=safe_name(job);node=nodes[name]
        remote=node['root']+'/jobs/'+job
        code="""import json,sys
from pathlib import Path
p=Path(sys.argv[1]);files=sorted((p/'metadata').glob('*.json'))
print(json.dumps(dict(accepted=len(files),rejected=len(list((p/'rejections').glob('*.json'))),
    records=[json.loads(f.read_text()) for f in files[:int(sys.argv[2])]])))
"""
        result=json.loads(run(['ssh','-o','BatchMode=yes',node['alias'],
            shlex.join([node['python'],'-c',code,remote,str(limit)])]))
        checked=[]
        for info in result['records']:
            qa=info['visibility_quality'];assert qa['passed']
            assert qa['beauty_sha256']==info['sha256'][info['image']]
            assert len(qa['instances'])==len(info['annotations']) and not info['hidden_defects']
            files={info['image'],f'all/labels/{info["sample_id"]}.txt'}
            files|={a['mask'] for a in info['annotations']}
            local=output/name
            for relative in sorted(files):
                path=inside(local,relative);path.parent.mkdir(parents=True,exist_ok=True)
                run(['scp','-q','-o','BatchMode=yes',node['alias']+':'+remote+'/'+relative,str(path)])
                if relative in info['sha256']:
                    assert hashlib.sha256(path.read_bytes()).hexdigest()==info['sha256'][relative]
            assert Image.open(local/info['image']).size==(1920,1200)
            lines=[];boxes=[];metrics=[]
            for a,entry in zip(info['annotations'],qa['instances']):
                assert entry['passed'] and entry['screen']['passed'] and entry['counterfactual']['passed']
                mask=np.asarray(Image.open(local/a['mask']).convert('L'))>127
                assert visible_box(mask,minimum=1)==a['bbox_xywh']
                assert int(mask.sum())==a['visible_pixels']
                lines.append(yolo_line(a['class_id'],a['bbox_xywh'],1920,1200))
                x,y,w,h=a['bbox_xywh']
                boxes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>')
                screen=entry['screen'];cf=entry['counterfactual']
                metrics.append(f'{a["name"]}: {screen["model_box"]} px support; '
                    f'{cf["p90_change_codes"]:.1f} RGB change; glare {screen["glare_fraction"]:.1%}')
            assert (local/f'all/labels/{info["sample_id"]}.txt').read_text().splitlines()==lines
            record=local/'metadata'/f'{info["sample_id"]}.json';record.parent.mkdir(exist_ok=True)
            record.write_text(json.dumps(info,indent=2),encoding='utf-8')
            src=f'{name}/{info["image"]}'
            part=next(p for p in info['parts'] if p['specimen_id']==info['recipe']['specimen_id'] and p['name']=='shell')
            x,y,w,h=part['bbox_xywh'];x=max(0,x-30);y=max(0,y-30)
            cards.append(f'<article><h2>{html.escape(name)} · {info["recipe"]["lighting"]} · {info["recipe"]["condition"]}</h2>'
                f'<div class="frame"><img src="{src}" width="640" height="400"><svg class="labels" viewBox="0 0 1920 1200">{"".join(boxes)}</svg></div>'
                '<p>Above: 640-pixel input scale. Below: enlarged detail.</p>'
                f'<svg class="crop" viewBox="{x} {y} {w+60} {h+60}"><image href="{src}" width="1920" height="1200"/></svg>'
                f'<p>{html.escape(" | ".join(metrics) or "Clean control; intentionally empty defect labels.")}</p>'
                f'<p><a href="{src}">Native 1920 × 1200</a> · <a href="{name}/metadata/{info["sample_id"]}.json">Measurements</a></p></article>')
            checked.append(info['sample_id'])
        receipts.append(dict(node=name,job=job,accepted=result['accepted'],rejected=result['rejected'],checked=checked))
    page='''<!doctype html><meta charset="utf-8"><title>Strict assembly visibility</title>
<style>body{font:15px system-ui;background:#111b20;color:#dae5e8;margin:28px}a{color:#9bd5ff}article{background:#1c2a31;padding:18px;margin:24px 0;max-width:900px}h2{font-size:19px}.frame{width:640px;height:400px;position:relative}.frame svg{position:absolute;inset:0;width:100%;height:100%;fill:none;stroke:#ff7850;stroke-width:2}.crop{display:block;width:720px;max-width:100%;margin-top:15px}.hide .labels{display:none}button{padding:10px}</style>
<h1>Strict assembly visibility · both cameras</h1>
<p>Snapshot of committed images from the running fleet. Failed candidates are excluded. Images, labels and mask bounds were checked; native resolution is 1920 × 1200. Thresholds assess rendered evidence at 640 pixels, not YOLOX accuracy.</p>
<button onclick="document.body.classList.toggle('hide')">Toggle defect boxes</button>'''+''.join(cards)
    (output/'index.html').write_text(page,encoding='utf-8')
    (output/'receipt.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    return receipts


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='append',required=True,help='node=job')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--limit',type=int,default=6)
    args=parser.parse_args();print(json.dumps(review(args.run,args.output,args.limit),indent=2))
