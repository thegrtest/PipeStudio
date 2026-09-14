"""Measure the supplied photo's ink coverage for a Blender UV stamp asset.

The source photo is retained unchanged. Background color and rib highlights are
rejected; only the dark printing becomes a scalar material mask.
"""
from pathlib import Path
from PIL import Image,ImageFilter
import json,math
root=Path(__file__).resolve().parents[1]
source=root/'flashlight_lab/references/body_print_reference.png'
out=root/'examples/reference-print-study';out.mkdir(exist_ok=True)
photo=Image.open(source).convert('RGB')
regions={'brand':dict(box=(1127,194,1193,470),body_y=(108,550),diameter=177),
         'size':dict(box=(452,185,517,459),body_y=(108,549),diameter=179)}
combined=Image.new('L',(2611,2048))
for name,spec in regions.items():
    patch=photo.crop(spec['box'])
    red=patch.getchannel('R')
    # A local upper quartile fills ink strokes without letting bright dust
    # dictate the estimated red-polymer background.
    background=red.filter(ImageFilter.RankFilter(17,216)).filter(ImageFilter.GaussianBlur(2))
    coverage=Image.new('L',patch.size)
    coverage.putdata([round(255*max(0,min(1,(b-r-13)/max(35,.52*b))))
                      for r,b in zip(red.getdata(),background.getdata())])
    # Reject isolated background flecks; retain holes and broken stamp edges.
    w,h=coverage.size;values=list(coverage.getdata());seen=set()
    for i,v in enumerate(values):
        if v<25 or i in seen:continue
        pending=[i];seen.add(i);component=[]
        while pending:
            j=pending.pop();component.append(j);x,y=j%w,j//w
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                xx,yy=x+dx,y+dy;k=yy*w+xx
                if 0<=xx<w and 0<=yy<h and k not in seen and values[k]>=25:
                    seen.add(k);pending.append(k)
        if len(component)<4:
            for j in component:values[j]=0
    coverage.putdata(values)
    coverage.save(out/f'{name}_ink.png')
    patch.save(out/f'{name}_reference.png')
    # Texture pixels map to the real reference's ratios, including its larger
    # arc mark and the gap between the two size markings.
    atlas=Image.new('L',(2611,2048))
    body_start,body_end=spec['body_y'];body_length=body_end-body_start
    pixels_y=2048/body_length
    pixels_x=2611/(math.pi*spec['diameter'])
    stamp=coverage.rotate(180).resize((round(w*pixels_x),round(h*pixels_y)),Image.Resampling.LANCZOS)
    # F starts at the brass end in canonical shell coordinates.
    y=round(2048*(1-(spec['box'][3]-body_start)/body_length))
    x=round(.75*2611-stamp.width/2)
    atlas.paste(stamp,(x,y))
    atlas.save(root/f'flashlight_lab/assets/body_print_v3_{name}.png')
    combined.paste(stamp,(x-(round(2611/4) if name=='size' else 0),y))
combined.save(root/'flashlight_lab/assets/body_print_v3.png')
(out/'source_measurements.json').write_text(json.dumps(dict(source=str(source),regions=regions,
    note='Source ink shapes; estimated local paint background removed; no RGB photo pasted onto the shell'),indent=2))
print('REFERENCE_INK_EXTRACTED')
