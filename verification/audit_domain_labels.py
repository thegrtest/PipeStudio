"""Read-only size/class audit of the real reference subset and synthetic bundle."""
from pathlib import Path
from collections import Counter, defaultdict
import json
import numpy as np
from PIL import Image

DESKTOP = Path(r"C:\Users\daugh\OneDrive\Desktop")
SOURCES = {
    "real_godslight": DESKTOP / "BrassModel11/all/2026-08-19GodsLight",
    "synthetic_bundle": DESKTOP / "thegreatawkaning/all",
}


def summarize(root):
    boxes = defaultdict(list)
    shapes = Counter()
    empty = missing = 0
    for img in (root / "images").iterdir():
        if img.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        with Image.open(img) as im:
            width, height = im.size
        shapes[f"{width}x{height}"] += 1
        label = root / "labels" / (img.stem + ".txt")
        if not label.exists():
            missing += 1
            continue
        lines = label.read_text().splitlines()
        empty += not any(line.strip() for line in lines)
        scale = 640.0 / max(width, height)
        for line in lines:
            t = line.split()
            if len(t) != 5:
                continue
            cid = int(t[0])
            boxes[cid].append([float(t[3]) * width * scale,
                               float(t[4]) * height * scale])
    return {
        "root": str(root), "image_shapes": dict(shapes),
        "empty_labels": empty, "missing_labels": missing,
        "box_dimensions_at_640": {
            str(cid): {
                "count": len(values),
                "width_q10_q50_q90": np.quantile(np.array(values)[:, 0], [.1, .5, .9]).round(2).tolist(),
                "height_q10_q50_q90": np.quantile(np.array(values)[:, 1], [.1, .5, .9]).round(2).tolist(),
                "short_side_q10_q50_q90": np.quantile(np.min(values, axis=1), [.1, .5, .9]).round(2).tolist(),
                "aspect_ratio_long_over_short_q10_q50_q90": np.quantile(np.max(values, axis=1) / np.maximum(np.min(values, axis=1), 1e-6), [.1, .5, .9]).round(2).tolist(),
            } for cid, values in sorted(boxes.items())
        },
    }


if __name__ == "__main__":
    result = {name: summarize(root) for name, root in SOURCES.items()}
    output = Path(__file__).with_name("domain_label_sizes_20260914.json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
