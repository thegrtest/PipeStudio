"""Make a displayable preview; source capture PNGs remain untouched."""
from pathlib import Path
import json
from PIL import Image

root = Path(__file__).resolve().parents[1]
folder = Path(json.loads((root / 'examples/rolling-shells/quality-collection-preflight.json').read_text())['folder'])
source = folder / 'images/rolling_p0000_00001_front_45.png'
output = root / 'examples/rolling-shells/quality-study/verified-production-front.jpg'
with Image.open(source) as im:
    print(dict(format=im.format, mode=im.mode, size=im.size))
    im.convert('RGB').save(output, quality=95, subsampling=0)
print(output)
