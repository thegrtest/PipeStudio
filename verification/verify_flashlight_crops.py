"""Independent Pillow check: crops retain exact source pixels and valid boxes."""
import json
import sys
from pathlib import Path
from PIL import Image,ImageChops

def verify(folder):
    folder=Path(folder)
    crops=json.loads((folder/'crops.json').read_text())['crops']
    assert crops
    sources={}
    for c in crops:
        source=sources.setdefault(c['source_image'],Image.open(folder/c['source_image']).convert('RGB'))
        x,y,w,h=c['source_bbox_xywh']
        assert 0<=x<x+w<=source.width and 0<=y<y+h<=source.height
        image=Image.open(folder/c['image']).convert('RGB')
        assert image.size==(w,h)
        assert ImageChops.difference(image,source.crop((x,y,x+w,y+h))).getbbox() is None,c['image']
        for a in c['annotations']:
            ax,ay,aw,ah=a['bbox_xywh']
            assert 0<=ax<ax+aw<=w and 0<=ay<ay+ah<=h
    result=dict(passed=True,crops=len(crops),source_images=len(sources),pixel_exact=True)
    (folder/'crop-validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))

if __name__=='__main__':verify(sys.argv[1])
