from pathlib import Path
from PIL import Image
root = Path(__file__).resolve().parents[1]
folder = root/'examples/rolling-shells/dirty-defect-loop'
with Image.open(folder/'preview.png') as im:
    im.convert('RGB').save(folder/'preview.jpg', quality=95, subsampling=0)
print(folder/'preview.jpg')
