"""Validate isolated regression images and show original/corrected pairs."""
import html
import json
import sys
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from domain_review import validate_dataset
from glare_guard import assess
import numpy as np

folder=ROOT/'verification/glare_guard'
original=ROOT.parent/'BrassRealismV2_Validated80_20260914'
records=json.loads((folder/'results.json').read_text())
source_plan=json.loads((original/'render_plan.json').read_text())
planned={row['sample_id']:row for row in source_plan['samples']}
plan={**source_plan,'samples':[planned[row['sample_id']] for row in records],
      'purpose':'Glare regression review only; not a production dataset'}
(folder/'render_plan.json').write_text(json.dumps(plan,indent=2))
(folder/'all/manifest.json').write_text(json.dumps(dict(classes=plan['classes'],samples=records),indent=2))
report,_=validate_dataset(folder)
for row in records:
    def mask(path):return np.asarray(Image.open(folder/'all'/path).convert('L'))>127
    rgb=np.asarray(Image.open(folder/'all'/row['image']).convert('RGB'),dtype=np.float32)/255
    measured=assess(rgb,[mask(a['mask']) for a in row['instances']],mask(row['pipe_mask']))
    for key in ('instances','pipe_clipped_fraction'):
        assert measured[key]==row['glare_guard'][key],(row['sample_id'],key)
(folder/'validation.json').write_text(json.dumps(report,indent=2))
assert report['valid'],report['errors']
ordered=sorted(records,key=lambda r:(-r['glare_guard']['retries'],r['sample_id']))
parts=['<!doctype html><meta charset="utf-8"><title>Defect glare check</title>',
       '<style>body{background:#141918;color:#eee;font:16px system-ui;margin:32px}h1{font-size:28px}section{margin:36px 0}figure{margin:0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}img{width:100%;max-height:620px;object-fit:contain;background:#080b09}p{color:#bec9c2}small{color:#94d7b2}</style>',
       '<h1>Keep reflections. Recover defect detail.</h1>',
       f'<p>{len(records)} validated previews across {len(set(r["setup"] for r in records))} environments. Geometry, defect classes, masks and output dimensions are preserved. Only failed lighting candidates are rerendered.</p>',
       '<p>These are review images. Active production jobs retain their saved renderer.</p>']
for row in ordered:
    q=row['glare_guard']; before=q['attempts'][0]
    peak=lambda value:max((i['clipped_fraction'] for i in value['instances']),default=0)
    parts.append(f'<section><h2>{html.escape(row["setup"])} · {html.escape(row["primary_kind"])}</h2><small>Worst defect near-clipping: {peak(before):.1%} → {peak(q):.1%}; lighting retries: {q["retries"]}</small><div class="pair">')
    for label,path in [('Original',original/'all'/row['image']),('Glare checked',folder/'all'/row['image'])]:
        parts.append(f'<figure><p>{label}</p><img src="{path.as_uri()}"></figure>')
    parts.append('</div></section>')
(folder/'index.html').write_text('\n'.join(parts),encoding='utf-8')
target=next(r for r in records if r['sample_id']=='domain_0914610001_machine')
canvas=Image.new('RGB',(1000,450),(20,25,24));draw=ImageDraw.Draw(canvas)
for index,(title,path) in enumerate([('Original',original/'all'/target['image']),('Glare checked',folder/'all'/target['image'])]):
    im=Image.open(path);im.thumbnail((495,400))
    canvas.paste(im,(index*500,42));draw.text((index*500+12,12),title,fill='white')
canvas.save(folder/'before_after.jpg',quality=94)
print(json.dumps(dict(valid=report['valid'],samples=len(records),setups=sorted({r['setup'] for r in records}),
                     retries={i:sum(r['glare_guard']['retries']==i for r in records) for i in range(6)})))
