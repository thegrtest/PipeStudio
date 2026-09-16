"""Read a committed fleet image and return a small JPEG without changing it."""
import io
from pathlib import Path
import re
import sys

from PIL import Image, ImageOps


def create_preview(root, job, image_path):
    if not isinstance(job, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', job):
        raise ValueError('Invalid job identifier')
    root = Path(root).resolve()
    images = (root/'jobs'/job/'all/images').resolve()
    source = Path(image_path).resolve()
    if (not images.is_relative_to(root) or not source.is_relative_to(images)
            or source.suffix.lower() != '.png' or not source.is_file()):
        raise ValueError('Preview must be a generated PNG inside this job')
    if source.stat().st_size > 64*1024*1024:
        raise ValueError('Image exceeds preview input limit')
    with Image.open(source) as image:
        image.thumbnail((960, 720), Image.Resampling.LANCZOS)
        image = ImageOps.exif_transpose(image).convert('RGB')
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=82)
    data = output.getvalue()
    if len(data) > 1024*1024:
        raise ValueError('Preview exceeds transfer limit')
    return data


if __name__ == '__main__':
    sys.stdout.buffer.write(create_preview(*sys.argv[1:]))
