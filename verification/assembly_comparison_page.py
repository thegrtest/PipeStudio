"""Build a local comparison, keeping real references outside exported datasets."""
import argparse
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]

def build(folder):
    folder=Path(folder).resolve();refs=folder/'references';refs.mkdir(exist_ok=True)
    source=Path(r'C:\Users\daugh\Downloads\CheckWeighShell\CheckWeighShell\images')
    names=['20260904_051433_717_cam3936.jpg','20260904_051424_654_cam3936.jpg','20260904_051424_983_cam3936.jpg']
    for name in names:shutil.copy2(source/name,refs/name)
    data={preset:[json.loads(p.read_text()) for p in sorted((folder/preset/'metadata').glob('*.json'))]
          for preset in ('current','balanced','four_lines')}
    assert all(len(v)==3 for v in data.values())
    original=[json.loads((ROOT/'verification'/'assembly_track'/'metadata'/(v['sample_id']+'.json')).read_text()) for v in data['current']]
    for i in range(3):
        for field in ('annotations','parts'):
            assert all(data[p][i][field]==data['current'][i][field] for p in data),field
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Assembly realism comparison · Pipe Studio</title><style>
:root{color-scheme:dark;font-family:Inter,Segoe UI,system-ui,sans-serif;background:#0b1318;color:#e4edf1}
*{box-sizing:border-box}body{margin:0;padding:30px;max-width:1800px;margin:auto}h1{font-size:30px;margin:8px 0}h2{font-size:18px;margin:0}p{color:#aabcc6;line-height:1.5;margin:8px 0 16px}.eyebrow{color:#75d4c7;font-size:12px;letter-spacing:2px;text-transform:uppercase}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.badges span{border:1px solid #2a404e;padding:6px 10px;border-radius:18px;color:#b7d0db;font-size:12px}
.controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap;padding:16px;background:#14222c;border-radius:10px;margin-bottom:22px;position:sticky;top:0;z-index:3}
select,button{font:inherit;border:1px solid #375564;color:#eff9fc;background:#203542;padding:7px 11px;border-radius:6px}label{font-size:14px}.top{display:grid;grid-template-columns:1fr 1fr;gap:18px}.lights{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:18px}
article{background:#14212a;border:1px solid #263d49;border-radius:12px;overflow:hidden}.heading{padding:15px 18px 8px}.heading p{font-size:13px;min-height:36px;margin-bottom:5px}canvas{width:100%;display:block;background:#070d11}a{color:#7cddd0}.foot{padding:22px;background:#111f28;margin-top:22px;border-radius:10px}.foot p:last-child{margin-bottom:0}.hint{font-size:13px}input{accent-color:#67cebc}
@media(max-width:1050px){.lights{grid-template-columns:1fr}.top{grid-template-columns:1fr}body{padding:18px}.heading p{min-height:0}}
</style><header><div class="eyebrow">Pipe Studio / Assembly inspection</div><h1>Closer to the camera</h1>
<p>Real reference, preserved first version, and three reflection setups on the same specimens.</p><div class="badges"><span>1920 × 1200 native</span><span>9 paired labeled previews</span><span>Inert exterior assembly</span><span>Training not started</span></div></header>
<div class="controls"><label>Specimen <select id="sample"><option value="0">Good / handling marks</option><option value="1">Dent / mixed defects</option><option value="2">Scratch</option></select></label>
<label>Reference <select id="reference"><option value="0">Centered assembly</option><option value="1">Two assemblies / 654</option><option value="2">Two assemblies / 983</option></select></label>
<label><input type="checkbox" id="crop"> Part detail</label><label><input type="checkbox" id="parts"> Shell + ferrule boxes</label><label><input type="checkbox" id="defects"> Defect boxes</label></div>
<div class="top"><article><div class="heading"><h2>Real camera reference</h2><p>Supplied cam3936 photograph. Kept outside the synthetic training folders.</p></div><canvas id="real"></canvas></article>
<article><div class="heading"><h2>First version · preserved</h2><p>Original saved render, unchanged. <a href="../assembly_track/index.html">Open the earlier review</a>.</p></div><canvas id="original"></canvas></article></div>
<div class="lights"><article><div class="heading"><h2>Current lighting</h2><p>Original bar placement on the refined scene; the broadest finish variation.</p></div><canvas id="current"></canvas></article>
<article><div class="heading"><h2>Balanced · in between</h2><p>Four softer reflection bands, with restrained variation in brightness.</p></div><canvas id="balanced"></canvas></article>
<article><div class="heading"><h2>Four crisp lines</h2><p>Four narrow, equally powered bars. Actual reflections bend over dents.</p></div><canvas id="four_lines"></canvas></article></div>
<div class="foot"><h2>What changed after comparison</h2><p>Revised camera and companion placement; rounder copper end and end rim; warmer worn brass and a darker neck; finer fixture wear and softened foreground acrylic. Removed an unsupported reflection ghost and fixed stale rail objects surviving scene rebuilds.</p>
<p>All three variants share geometry, pose and finish seeds. Reflection width changes with both emitter width and surface roughness. Blue boxes track shell/ferrule; coral boxes mark visible defect support. These three specimens demonstrate lighting choices, not a balanced training batch.</p>
<p class="hint">Remaining differences: rail/fastener construction, acrylic reflections, shadow color and fine surface texture still need calibration. This comparison does not demonstrate model transfer to real images.</p></div>
<script>const DATA=__DATA__,REFS=__REFS__,ORIGINAL=__ORIGINAL__;
const cache=new Map();let revision=0;
function load(url){if(!cache.has(url))cache.set(url,new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=reject;im.src=url}));return cache.get(url)}
function union(a){const x=Math.min(...a.map(v=>v[0])),y=Math.min(...a.map(v=>v[1]));return[x,y,Math.max(...a.map(v=>v[0]+v[2]))-x,Math.max(...a.map(v=>v[1]+v[3]))-y]}
function draw(id,im,box,info){const c=document.getElementById(id);const detail=document.getElementById('crop').checked;
let [x,y,w,h]=detail?box:[0,0,im.width,im.height];if(detail){x-=22;y-=28;w+=44;h+=56}c.width=Math.ceil(w);c.height=Math.ceil(h);const ctx=c.getContext('2d');ctx.drawImage(im,x,y,w,h,0,0,w,h);
if(!info)return;const groups=[];if(document.getElementById('parts').checked)groups.push([info.parts,'#67dcff']);if(document.getElementById('defects').checked)groups.push([info.annotations,'#ff8469']);
for(const [items,color]of groups)for(const a of items){ctx.strokeStyle=ctx.fillStyle=color;ctx.lineWidth=detail?1.3:3;const b=a.bbox_xywh;ctx.strokeRect(b[0]-x,b[1]-y,b[2],b[3]);ctx.font=(detail?'12':'23')+'px Segoe UI';ctx.fillText(a.name,b[0]-x,Math.max(13,b[1]-y-5))}}
async function update(){const rev=++revision,index=+document.getElementById('sample').value,ref=+document.getElementById('reference').value;
const r=await load('references/'+REFS[ref]);if(rev!==revision)return;draw('real',r,[[592,720,561,103],[321,664,548,123],[140,630,550,120]][ref]);
const old=await load('../assembly_track/all/images/'+DATA.current[index].sample_id+'.png');if(rev!==revision)return;const oi=ORIGINAL[index];draw('original',old,union(oi.parts.filter(a=>a.specimen_id===oi.recipe.specimen_id).map(a=>a.bbox_xywh)),oi);
for(const preset of Object.keys(DATA)){const info=DATA[preset][index];const im=await load(preset+'/'+info.image);if(rev!==revision)return;const boxes=info.parts.filter(a=>a.specimen_id===info.recipe.specimen_id).map(a=>a.bbox_xywh);draw(preset,im,union(boxes),info)}}
for(const input of document.querySelectorAll('input,select'))input.addEventListener('change',()=>update().catch(console.error));update().catch(console.error);
</script></html>'''
    html=html.replace('__DATA__',json.dumps(data)).replace('__REFS__',json.dumps(names)).replace('__ORIGINAL__',json.dumps(original))
    (folder/'index.html').write_text(html,encoding='utf-8')
    return folder/'index.html'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path)
    print(build(p.parse_args().folder))
