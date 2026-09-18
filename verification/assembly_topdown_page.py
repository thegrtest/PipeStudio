"""Build a transparent real/old/new camera comparison, outside training data."""
import argparse
import json
from pathlib import Path
from PIL import Image,ImageDraw
from assembly_dent_page import build,ROOT


def main(root):
    root=root.resolve();build(root)
    assets=root/'review_assets'
    key='assembly_0000361000_f001'
    newer=Image.open(assets/(key+'_part.png')).convert('RGB')
    # Native real crop, with margins matching the generated-part crops.
    real=Image.open(assets/'real.jpg').crop((576,700,1170,849)).convert('RGB')
    previous_root=ROOT/'verification/assembly_small_dents_v3_final'
    old=Image.open(previous_root/'review_assets'/(key+'_part.png')).convert('RGB')
    crops=[('REAL CAMERA - supplied cam3936 reference',real),('PREVIOUS - lower camera and procedural background',old),('UPDATED - elevated camera, rendered part / real empty track',newer)]
    canvas=Image.new('RGB',(max(im.width for _,im in crops)+32,sum(im.height+48 for _,im in crops)+16),(15,27,35))
    draw=ImageDraw.Draw(canvas);y=12
    for title,im in crops:
        draw.text((16,y),title,fill=(220,235,239));canvas.paste(im,(16,y+24));y+=im.height+48
    canvas.save(assets/'native_comparison.png')
    page=(root/'index.html').read_text(encoding='utf-8')
    page=page.replace('Small and shallow dents · Assembly Studio','Elevated camera comparison · Assembly Studio')
    page=page.replace('Smaller dents, subtler reflections','Closer to the real camera view')
    start=page.index('<p class="note">');end=page.index('</p>',start)+4
    note='''<p class="note">New default: <b>CAMERA_MATCHED</b>. The camera is about 36° above the track, compared with the previous low view. The nominal assembly is fitted to approximately 550 pixels wide, centered near (872, 775), at native 1920 × 1200. These are inferred camera parameters, not measured calibration. Movement follows the photographed diagonal corridor.</p>
<p class="note">This is a <b>hybrid rendering</b>: the background comes from two visually checked, empty frames of this machine. Every visible assembly, defect and contact shadow is rendered in Blender. No real product is copied into the generated images. Source names and hashes are recorded in metadata. The original and refined fully procedural environments remain available.</p>
<p class="note">The part's copper, neck, four-bar balance and shaded brass have been adjusted. The crops below are shown at native pixels, with different crop widths preserved. The finish and reflections can still reveal the rendering; this review does not establish indistinguishability or transfer accuracy. A model evaluation on held-out real parts and a separate capture session is still needed. Geometric label support does not guarantee that a shallow dent is visually detectable.</p>
<article><header><h2>Native part crops — real / previous / updated</h2></header><img src="review_assets/native_comparison.png" style="width:auto;max-width:100%;margin:0 auto"></article>'''
    page=page[:start]+note+page[end:]
    page=page.replace('New dent mix:','Dent mix:')
    (root/'index.html').write_text(page,encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);main(p.parse_args().root)
