"""Build a local before/after viewer and labeled analysis crops; originals stay intact."""
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'examples'/'brass-v4'
sections=[]
for env,label,reference in [('godslight','GodsLight','godslight-horizontal.jpg'),('machine','Upright inspection','upright-inspection.png')]:
    cards=''.join(f'<a class="card" href="images/{env}_{kind}_reference.png"><img loading="lazy" src="images/{env}_{kind}_reference.png"><span>{name}</span></a>' for kind,name in [('reference','Matched reference'),('drawn','Drawn / burnished'),('mottled','Mottled / handled'),('satin','Satin')])
    sections.append(f'''<section id="{env}"><h2>{label}</h2><div class="comparison-grid"><figure><img src="../../references/{reference}"><figcaption>Real reference photograph</figcaption></figure><figure><div class="wipe" style="--cut:50%"><img src="images/{env}_reference_reference.png" alt="Refined brass surface V4"><img class="before" src="../realism-v3/images/{env}.png" alt="Previous brass surface V3"><div class="line"></div><b class="left">Previous V3</b><b class="right">Refined V4</b></div><label class="slider">Drag to compare <input aria-label="Before after split for {label}" type="range" min="0" max="100" value="50"></label><figcaption>Same camera and geometry; revised brass finish and reference lighting.</figcaption></figure></div><div class="cards">{cards}</div></section>''')
    # Analyze the same body region at a common display size, with each input
    # independently labeled. Crops/resampling are confined to this review file.
    frames=[('REAL PHOTO',ROOT/'references'/reference),('PREVIOUS V3',ROOT/'examples'/'realism-v3'/'images'/(env+'.png')),
            ('REFINED V4',folder/'images'/(env+'_reference_reference.png'))]
    normalized=(.14,.44,.78,.66) if env=='godslight' else (.53,.37,.72,.93)
    tile_w,tile_h=(1000,220) if env=='godslight' else (280,560)
    board=Image.new('RGB',(tile_w,3*(tile_h+38)) if env=='godslight' else (3*tile_w,tile_h+38),'#111c23')
    draw=ImageDraw.Draw(board);font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',20)
    for index,(title,path) in enumerate(frames):
        with Image.open(path) as im:
            crop=im.convert('RGB').crop(tuple(round(v*(im.width if k%2==0 else im.height)) for k,v in enumerate(normalized)))
            crop=ImageOps.fit(crop,(tile_w,tile_h),method=Image.Resampling.LANCZOS)
        x,y=(0,index*(tile_h+38)) if env=='godslight' else (index*tile_w,0)
        draw.text((x+12,y+7),title,font=font,fill='#eed197');board.paste(crop,(x,y+38))
    board.save(folder/(env+'_surface_comparison.jpg'),quality=96)
html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Brass surface V4 comparison</title>
<style>*{box-sizing:border-box}body{margin:0;padding:32px;background:#111c23;color:#e8e8df;font:15px system-ui;line-height:1.5}header,section{max-width:1500px;margin:0 auto 40px}h1{font-size:32px;margin-bottom:8px;color:#eed197}h2{color:#d8b666}a{color:#eed197}nav{display:flex;gap:20px}.comparison-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:start}figure{margin:0;background:#192731;padding:12px;border-radius:12px}img{display:block;width:100%;height:auto}figcaption{color:#bbc5c9;margin-top:10px;font-size:13px}.wipe{position:relative}.before{position:absolute;inset:0;clip-path:inset(0 calc(100% - var(--cut)) 0 0);height:100%;object-fit:fill}.line{position:absolute;top:0;bottom:0;left:var(--cut);width:2px;background:#eed197}b{position:absolute;top:10px;padding:4px 8px;background:#111c23bb;font-size:12px}.left{left:10px}.right{right:10px}.slider{display:flex;gap:20px;align-items:center;padding:12px 0}input{flex:1;accent-color:#d8b666}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:20px}.card{background:#192731;padding:10px;border-radius:8px;text-decoration:none}.card span{display:block;padding:8px 0 0}.note{max-width:950px;color:#bbc5c9}@media(max-width:850px){body{padding:14px}.comparison-grid{grid-template-columns:1fr}.cards{grid-template-columns:1fr 1fr}}</style>
<header><h1>Brass surface / V4</h1><p class="note">Directional reflections, uneven drawn-metal streaks, dull mottled patches and exposed cut rims. The real photograph remains the comparison target; this is a visual fit, not a measured material calibration.</p><nav><a href="#godslight">GodsLight</a><a href="#machine">Upright inspection</a><a href="report/index.html">All rendered examples and masks</a><a href="../../BRASS_SURFACE.md">Material notes</a></nav></header>'''+''.join(sections)+'''<script>document.querySelectorAll('input').forEach(input=>input.addEventListener('input',()=>input.closest('figure').querySelector('.wipe').style.setProperty('--cut',input.value+'%')));</script></html>'''
(folder/'comparison.html').write_text(html,encoding='utf-8')
print(folder/'comparison.html')

