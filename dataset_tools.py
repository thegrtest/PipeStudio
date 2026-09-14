"""Validate, inspect and score rendered pipe challenge sets without Blender.

No real-world accuracy is implied: these reports measure performance on synthetic
images and crisp visible geometric-support boxes, not perceptual defect visibility.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import sys
from urllib.parse import quote
import uuid

from PIL import Image, ImageDraw, ImageOps

CLASSES = {0: "Fold", 1: "Dent"}
CLEAN_KINDS = ("NONE", "CLEAN")
SPLITS = ("train", "val", "test")
LIMITATION = ("Synthetic challenge results cannot establish real-world transfer. "
              "Boxes describe visible procedural geometry support, not measured "
              "perceptual visibility or an acceptance criterion. Keep a separate "
              "untouched real inspection test set.")
CORE_FIELDS = ("image", "mask", "width", "height", "class_id", "defect_type",
               "bbox_xywh", "visible_mask_pixels", "has_visible_geometric_mask",
               "parameters")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(value, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def relative_file(root, value, directory):
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing {directory} path")
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or relative.parts[0] != directory:
        raise ValueError(f"path must be relative inside {directory}/: {value}")
    path = (root / relative).resolve()
    if not path.is_relative_to((root / directory).resolve()):
        raise ValueError(f"path escapes {directory}/: {value}")
    return path


def read_manifest(folder):
    root = Path(folder).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("samples"), list):
        raise ValueError("manifest.json must contain a samples list")
    if any(not isinstance(sample, dict) for sample in manifest["samples"]):
        raise ValueError("each manifest sample must be an object")
    return root, manifest


def specimen_group(sample):
    return str(sample.get("specimen_id") or sample.get("specimen_group") or
               sample.get("sample_id") or sample["image"])


def groups_and_splits(samples, ratios=(0.0, 0.0, 1.0)):
    if len(ratios) != 3 or any(not math.isfinite(x) or x < 0 for x in ratios) or sum(ratios) <= 0:
        raise ValueError("split ratios must be three nonnegative finite values with positive sum")
    total = sum(ratios)
    limits = (ratios[0] / total, (ratios[0] + ratios[1]) / total)
    explicit = {}
    for sample in samples:
        group = specimen_group(sample)
        split = sample.get("split")
        if split is not None:
            if split not in SPLITS:
                raise ValueError(f"invalid split {split!r} for {sample['image']}")
            if group in explicit and explicit[group] != split:
                raise ValueError(f"specimen split leakage: {group} occurs in {explicit[group]} and {split}")
            explicit[group] = split
    result = {}
    for sample in samples:
        group = specimen_group(sample)
        score = int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:16], 16) / 2**64
        result[sample["image"]] = explicit.get(group, SPLITS[0 if score < limits[0] else 1 if score < limits[1] else 2])
    return result


def finite_numbers(values, count):
    return (isinstance(values, (tuple, list)) and len(values) == count and
            all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in values))


def validate_dataset(folder):
    errors, warnings = [], []
    try:
        root, manifest = read_manifest(folder)
    except (OSError, ValueError) as exc:
        return {"valid": False, "errors": [str(exc)], "warnings": [], "sample_count": 0}
    samples = manifest["samples"]
    if not samples:
        warnings.append("Dataset has no samples.")
    classes = manifest.get("classes")
    if classes is not None and classes != {str(k): v for k, v in CLASSES.items()}:
        errors.append("manifest classes must be 0=Fold, 1=Dent")
    try:
        groups_and_splits(samples)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    if samples and any(not (s.get("specimen_id") or s.get("specimen_group")) for s in samples):
        warnings.append("Some samples lack specimen_id: separate images are treated as separate groups. Supply shared IDs for paired or related views.")
    seen = set()
    sample_ids = set()
    expected = {name: set() for name in ("images", "masks", "labels", "metadata")}
    for index, sample in enumerate(samples, 1):
        label = str(sample.get("image", f"sample #{index}"))
        try:
            if label in seen:
                raise ValueError("duplicate image in manifest")
            seen.add(label)
            sample_id = sample.get("sample_id")
            if sample_id is not None:
                if str(sample_id) in sample_ids:
                    raise ValueError("duplicate sample_id in manifest")
                sample_ids.add(str(sample_id))
            image_path = relative_file(root, sample.get("image"), "images")
            mask_path = relative_file(root, sample.get("mask"), "masks")
            relative_stem = image_path.relative_to(root / "images").with_suffix("")
            label_path = root / "labels" / relative_stem.with_suffix(".txt")
            meta_path = root / "metadata" / relative_stem.with_suffix(".json")
            for name, path in zip(expected, (image_path, mask_path, label_path, meta_path)):
                if path in expected[name]:
                    raise ValueError(f"duplicate {name} file reference")
                expected[name].add(path)
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            for field in CORE_FIELDS:
                if field not in sample or field not in metadata:
                    raise ValueError(f"missing required metadata field: {field}")
                if sample[field] != metadata[field]:
                    raise ValueError(f"manifest/metadata mismatch: {field}")
            with Image.open(image_path) as source:
                source.load()
                size = source.size
            if size != (sample["width"], sample["height"]):
                raise ValueError("image dimensions disagree with metadata")
            with Image.open(mask_path) as source:
                source.load()
                if source.size != size:
                    raise ValueError("mask and image dimensions differ")
                rgb = source.convert("RGB")
                colors = rgb.getcolors(maxcolors=3)
                if colors is None or any(color not in ((0, 0, 0), (255, 255, 255)) for _, color in colors):
                    raise ValueError("mask must contain only binary black and white pixels")
                mask = rgb.convert("L")
                extent = mask.getbbox()
                actual_box = None if extent is None else [extent[0], extent[1], extent[2] - extent[0], extent[3] - extent[1]]
                pixel_count = mask.histogram()[255]
            if sample["bbox_xywh"] != actual_box:
                raise ValueError(f"metadata box disagrees with mask: expected {actual_box}")
            if sample["visible_mask_pixels"] != pixel_count or sample["has_visible_geometric_mask"] is not bool(actual_box):
                raise ValueError("metadata visibility disagrees with mask")
            class_id = sample["class_id"]
            expected_class = {"NONE": None, "CLEAN": None, "FOLD": 0, "DENT": 1}.get(sample["defect_type"], "invalid")
            if expected_class == "invalid" or class_id != expected_class or isinstance(class_id, bool):
                raise ValueError("class_id and defect_type must agree with NONE/FOLD/DENT")
            if actual_box and class_id is None:
                raise ValueError("clean sample has a visible defect mask")
            lines = [line.split() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not actual_box:
                if lines:
                    raise ValueError("clean/hidden sample must have an empty YOLO label")
            else:
                if len(lines) != 1 or len(lines[0]) != 5:
                    raise ValueError("one visible defect requires one five-field YOLO label")
                if lines[0][0] != str(class_id):
                    raise ValueError("YOLO class disagrees with metadata")
                coords = list(map(float, lines[0][1:]))
                if not finite_numbers(coords, 4) or any(v < 0 or v > 1 for v in coords):
                    raise ValueError("YOLO coordinates must be finite normalized values")
                cx, cy, bw, bh = coords
                if bw <= 0 or bh <= 0 or cx - bw / 2 < -1e-7 or cy - bh / 2 < -1e-7 or cx + bw / 2 > 1 + 1e-7 or cy + bh / 2 > 1 + 1e-7:
                    raise ValueError("YOLO box falls outside the image")
                width, height = size
                actual = [(cx - bw / 2) * width, (cy - bh / 2) * height, bw * width, bh * height]
                if any(abs(a - b) > .02 for a, b in zip(actual, actual_box)):
                    raise ValueError("YOLO box disagrees with mask box by more than 0.02 pixels")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{label}: {exc}")
    for name, suffix in (("images", ".png"), ("masks", ".png"), ("labels", ".txt"), ("metadata", ".json")):
        actual = {p.resolve() for p in (root / name).rglob("*") if p.is_file() and p.suffix.lower() == suffix}
        for extra in sorted(actual - expected[name]):
            display = extra.relative_to(root).as_posix() if extra.is_relative_to(root) else str(extra)
            errors.append(f"Unlisted {name} file: {display}")
        for missing in sorted(expected[name] - actual):
            errors.append(f"Missing {name} file: {missing.relative_to(root).as_posix()}")
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "sample_count": len(samples), "limitation": LIMITATION}


def require_valid(folder):
    validation = validate_dataset(folder)
    if not validation["valid"]:
        raise ValueError("Dataset validation failed:\n" + "\n".join(validation["errors"]))
    return read_manifest(folder), validation


def dimension(sample, name):
    parameters = sample.get("parameters", {})
    fallback = {"scenario": sample.get("scenario_id"), "style": sample.get("defect_style", parameters.get("defect_style")),
                "lighting": sample.get("lighting_profile", parameters.get("lighting_profile")),
                "environment": parameters.get("environment"), "severity": sample.get("severity")}
    value = fallback.get(name)
    return str(value) if value is not None else "unspecified"


def dataset_stats(samples):
    grouped = {}
    for axis in ("environment", "style", "lighting", "severity", "scenario"):
        totals = defaultdict(lambda: {"samples": 0, "visible": 0, "hidden_defect": 0, "clean": 0})
        for sample in samples:
            row = totals[dimension(sample, axis)]
            row["samples"] += 1
            row["visible"] += bool(sample["bbox_xywh"])
            row["clean"] += sample["defect_type"] in CLEAN_KINDS
            row["hidden_defect"] += sample["defect_type"] not in CLEAN_KINDS and not sample["bbox_xywh"]
        grouped[axis] = dict(sorted(totals.items()))
    return {"samples": len(samples), "visible_defects": sum(bool(s["bbox_xywh"]) for s in samples),
            "classes": dict(Counter(s["defect_type"] for s in samples)),
            "specimen_groups": len({specimen_group(s) for s in samples}),
            "by": grouped, "limitation": LIMITATION}


def report_dataset(folder):
    (root, manifest), validation = require_valid(folder)
    samples = manifest["samples"]
    report_dir = root / "report"
    thumb_dir = report_dir / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    stats = dataset_stats(samples)
    stats["validation"] = validation
    atomic_json(report_dir / "stats.json", stats)
    cards = []
    contact_thumbs = []
    for index, sample in enumerate(samples, 1):
        with Image.open(root / sample["image"]) as source:
            thumb = ImageOps.contain(source.convert("RGB"), (360, 240))
            annotated = thumb.copy()
            if sample["bbox_xywh"]:
                # Coordinates are scaled within the image before letterboxing.
                x, y, width, height = sample["bbox_xywh"]
                scale_x, scale_y = thumb.width / source.width, thumb.height / source.height
                box = (min(thumb.width - 1, round(x * scale_x)), min(thumb.height - 1, round(y * scale_y)),
                       min(thumb.width - 1, round((x + width) * scale_x) - 1),
                       min(thumb.height - 1, round((y + height) * scale_y) - 1))
                box = (box[0], box[1], max(box[0], box[2]), max(box[1], box[3]))
                overlay = ImageDraw.Draw(annotated)
                overlay.rectangle(box, outline="#ffd23f", width=2)
                text = CLASSES[sample["class_id"]]
                extent = overlay.textbbox((0, 0), text)
                tag_width, tag_height = extent[2] - extent[0] + 8, extent[3] - extent[1] + 6
                tag_x = max(0, min(box[0], thumb.width - tag_width))
                tag_y = box[1] - tag_height - 2 if box[1] >= tag_height + 2 else box[1] + 2
                tag_y = max(0, min(tag_y, thumb.height - tag_height))
                overlay.rectangle((tag_x, tag_y, tag_x + tag_width, tag_y + tag_height), fill="#ffd23f")
                overlay.text((tag_x + 4 - extent[0], tag_y + 3 - extent[1]), text, fill="#101820")
            tile = Image.new("RGB", (360, 276), "#101820")
            image_offset = ((360 - thumb.width) // 2, (240 - thumb.height) // 2)
            tile.paste(thumb, image_offset)
            draw = ImageDraw.Draw(tile)
            draw.text((8, 244), f"{index}: {sample['defect_type']} | {dimension(sample, 'lighting')}", fill="#eed9a8")
            draw.text((8, 259), f"{dimension(sample, 'style')} | {dimension(sample, 'severity')}", fill="#bdc8d0")
            tile.save(thumb_dir / f"{index:06d}.jpg", quality=88)
            annotated_tile = tile.copy()
            annotated_tile.paste(annotated, image_offset)
            annotated_tile.save(thumb_dir / f"{index:06d}-boxes.jpg", quality=88)
            if index <= 48:
                contact_thumbs.append(tile)
        attrs = " ".join(f'data-{key}="{html.escape(dimension(sample, key), quote=True)}"' for key in ("environment", "style", "lighting", "severity", "scenario"))
        source_url = "../" + quote(sample["image"], safe="/")
        mask_url = "../" + quote(sample["mask"], safe="/")
        title = html.escape(str(sample.get("sample_id", sample["image"])))
        detail = html.escape(" · ".join((dimension(sample, "scenario"), dimension(sample, "environment"), dimension(sample, "style"), dimension(sample, "severity"))))
        visible = "Visible geometry" if sample["bbox_xywh"] else "Clean" if sample["defect_type"] in CLEAN_KINDS else "Hidden defect"
        cards.append(f'<article {attrs}><a href="{source_url}"><img loading="lazy" src="thumbs/{index:06d}.jpg" data-original="thumbs/{index:06d}.jpg" data-annotated="thumbs/{index:06d}-boxes.jpg" alt="{title}"></a><h3>{title}</h3><p>{detail}</p><p>{visible} · <a href="{mask_url}">Mask</a></p></article>')
    if contact_thumbs:
        columns = min(4, len(contact_thumbs))
        sheet = Image.new("RGB", (columns * 360, math.ceil(len(contact_thumbs) / columns) * 276), "#101820")
        for index, tile in enumerate(contact_thumbs):
            sheet.paste(tile, ((index % columns) * 360, (index // columns) * 276))
        sheet.save(report_dir / "contact-sheet.jpg", quality=90)
    selectors = []
    for key in ("environment", "style", "lighting", "severity", "scenario"):
        options = '<option value="">All</option>' + ''.join(f'<option>{html.escape(value)}</option>' for value in stats["by"][key])
        selectors.append(f'<label>{key.title()} <select data-filter="{key}">{options}</select></label>')
    content = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pipe Studio challenge gallery</title>
<style>body{font:15px system-ui;margin:28px;background:#101820;color:#e0e6ed}h1{color:#ebc570}a{color:#f4ce7f}header{max-width:1100px}nav{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}label{display:grid;gap:5px}select{padding:8px;background:#1c2a35;color:inherit;border:1px solid #53606a}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}article{background:#1a2732;padding:12px;overflow:hidden;border-radius:8px}article img{width:100%;height:auto}article h3{font-size:14px;overflow-wrap:anywhere}article p{font-size:13px;color:#bdc8d0}article[hidden]{display:none}.note{line-height:1.6;color:#bdc8d0}</style>
<header><h1>Pipe Studio synthetic challenge set</h1><p>__COUNT__ images · __VISIBLE__ visible defects · __GROUPS__ specimen groups</p><p class="note">__LIMITATION__</p><p><a href="stats.json">Statistics JSON</a> · <a href="contact-sheet.jpg">Contact sheet (first 48)</a> · <a href="../manifest.json">Manifest</a></p></header><nav>__SELECTORS__<label style="align-content:center"><span><input type="checkbox" id="show-boxes"> Show boxes</span></label></nav><p id="count"></p><main>__CARDS__</main>
<script>const filters=[...document.querySelectorAll('[data-filter]')],cards=[...document.querySelectorAll('article')];function update(){let n=0;for(const card of cards){card.hidden=!filters.every(f=>!f.value||card.dataset[f.dataset.filter]===f.value);if(!card.hidden)n++;}document.querySelector('#count').textContent=n+' matching images';}filters.forEach(f=>f.addEventListener('change',update));const boxes=document.querySelector('#show-boxes');function updateBoxes(){for(const card of cards){const img=card.querySelector('img');img.src=boxes.checked?img.dataset.annotated:img.dataset.original;}}boxes.addEventListener('change',updateBoxes);update();updateBoxes();</script></html>'''
    for key, value in {"COUNT": len(samples), "VISIBLE": stats["visible_defects"], "GROUPS": stats["specimen_groups"], "LIMITATION": html.escape(LIMITATION), "SELECTORS": "".join(selectors), "CARDS": "".join(cards)}.items():
        content = content.replace("__" + key + "__", str(value))
    atomic_text(report_dir / "index.html", content)
    atomic_text(root / "report.html", '<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=report/index.html"><title>Pipe Studio report</title><p><a href="report/index.html">Open the Pipe Studio challenge gallery</a></p></html>')
    return {"report": str(root / "report.html"), "gallery": str(report_dir / "index.html"), "statistics": str(report_dir / "stats.json"), **stats}


def coco_document(samples, splits):
    images, annotations = [], []
    for image_id, sample in enumerate(samples, 1):
        images.append({"id": image_id, "file_name": sample["image"], "width": sample["width"], "height": sample["height"],
                       "sample_id": sample.get("sample_id", sample["image"]), "specimen_id": specimen_group(sample),
                       "split": splits[sample["image"]], "scenario_id": dimension(sample, "scenario"),
                       "lighting_profile": dimension(sample, "lighting")})
        box = sample["bbox_xywh"]
        if box:
            annotations.append({"id": len(annotations) + 1, "image_id": image_id, "category_id": sample["class_id"],
                                "bbox": box, "area": box[2] * box[3], "iscrowd": 0})
    return {"info": {"description": "Pipe Studio synthetic box challenge (not real inspection validation)",
                     "date_created": datetime.now(timezone.utc).isoformat(), "limitation": LIMITATION,
                     "annotation_type": "bounding boxes only; segmentation intentionally omitted"},
            "images": images, "annotations": annotations, "categories": [{"id": key, "name": value} for key, value in CLASSES.items()]}


def export_coco(folder, ratios=(0.0, 0.0, 1.0)):
    (root, manifest), validation = require_valid(folder)
    samples = manifest["samples"]
    splits = groups_and_splits(samples, ratios)
    document = coco_document(samples, splits)
    atomic_json(root / "annotations.coco.json", document)
    split_counts = {}
    for split in SPLITS:
        chosen = [item for item in document["images"] if item["split"] == split]
        ids = {item["id"] for item in chosen}
        split_counts[split] = len(chosen)
        atomic_json(root / "splits" / f"{split}.coco.json", {**document, "images": chosen, "annotations": [a for a in document["annotations"] if a["image_id"] in ids]})
        atomic_text(root / "splits" / f"{split}.txt", "".join((root / item["file_name"]).as_posix() + "\n" for item in chosen))
    atomic_json(root / "splits" / "groups.json", [{"image": s["image"], "specimen_id": specimen_group(s), "split": splits[s["image"]]} for s in samples])
    yaml = f'# Synthetic challenge only. {LIMITATION}\npath: {json.dumps(root.as_posix())}\ntrain: splits/train.txt\nval: splits/val.txt\ntest: splits/test.txt\nnames:\n  0: Fold\n  1: Dent\n'
    atomic_text(root / "dataset.yaml", yaml)
    return {"coco": str(root / "annotations.coco.json"), "yaml": str(root / "dataset.yaml"), "counts": split_counts,
            "warnings": validation["warnings"], "limitation": LIMITATION}


def box_iou(left, right):
    x = max(left[0], right[0])
    y = max(left[1], right[1])
    end_x = min(left[0] + left[2], right[0] + right[2])
    end_y = min(left[1] + left[3], right[1] + right[3])
    intersection = max(0, end_x - x) * max(0, end_y - y)
    union = left[2] * left[3] + right[2] * right[3] - intersection
    return intersection / union if union > 0 else 0.0


def evaluation_splits(root, samples):
    """Honor saved grouped splits, rejecting stale assignments after dataset edits."""
    split_path = root / "splits" / "groups.json"
    if not split_path.exists():
        return groups_and_splits(samples)
    rows = json.loads(split_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != len(samples):
        raise ValueError("Saved split assignments are stale; run coco export again")
    saved = {}
    for row in rows:
        if not isinstance(row, dict) or not all(key in row for key in ("image", "specimen_id", "split")):
            raise ValueError("Malformed saved split assignments; run coco export again")
        if row["image"] in saved:
            raise ValueError("Duplicate image in saved split assignments")
        saved[row["image"]] = row
    assigned = []
    for sample in samples:
        row = saved.get(sample["image"])
        if row is None or str(row["specimen_id"]) != specimen_group(sample) or (sample.get("split") is not None and sample["split"] != row["split"]):
            raise ValueError("Saved split assignments disagree with manifest; run coco export again")
        assigned.append({**sample, "split": row["split"]})
    return groups_and_splits(assigned)


def metric_counts(tp=0, fp=0, fn=0, images=0):
    return {"images": images, "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def evaluate_dataset(folder, predictions_file, confidence=.25, iou_threshold=.5, split=None):
    if not math.isfinite(confidence) or not 0 <= confidence <= 1 or not math.isfinite(iou_threshold) or not 0 < iou_threshold <= 1:
        raise ValueError("confidence must be in [0,1], IoU in (0,1]")
    (root, manifest), _ = require_valid(folder)
    samples = manifest["samples"]
    assignments = evaluation_splits(root, samples)
    if split is not None and split not in SPLITS:
        raise ValueError("unknown evaluation split")
    predictions = json.loads(Path(predictions_file).read_text(encoding="utf-8"))
    if not isinstance(predictions, list):
        raise ValueError("predictions must be a COCO-style list")
    selected_ids = {i for i, s in enumerate(samples, 1) if split is None or assignments[s["image"]] == split}
    by_image = defaultdict(list)
    excluded = 0
    for index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            raise ValueError(f"prediction {index} must be an object")
        image_id, category = prediction.get("image_id"), prediction.get("category_id")
        box, score = prediction.get("bbox"), prediction.get("score")
        if not isinstance(image_id, int) or isinstance(image_id, bool) or not 1 <= image_id <= len(samples):
            raise ValueError(f"prediction {index} has an unknown integer image_id; use annotations.coco.json IDs")
        if not isinstance(category, int) or isinstance(category, bool) or category not in CLASSES:
            raise ValueError(f"prediction {index} category_id must be 0 (Fold) or 1 (Dent)")
        if not finite_numbers(box, 4) or box[2] <= 0 or box[3] <= 0:
            raise ValueError(f"prediction {index} bbox must be finite x,y,width,height with positive size")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError(f"prediction {index} score must be in [0,1]")
        if image_id not in selected_ids:
            excluded += 1
        elif score >= confidence:
            by_image[image_id].append(prediction)
    per_image = []
    for image_id in sorted(selected_ids):
        sample = samples[image_id - 1]
        ground_truth = sample["bbox_xywh"]
        matched = False
        tp = fp = 0
        for prediction in sorted(by_image[image_id], key=lambda item: -item["score"]):
            if ground_truth and not matched and prediction["category_id"] == sample["class_id"] and box_iou(prediction["bbox"], ground_truth) >= iou_threshold:
                matched = True
                tp += 1
            else:
                fp += 1
        per_image.append({"image_id": image_id, "image": sample["image"],
                          "scenario": dimension(sample, "scenario"), "lighting": dimension(sample, "lighting"),
                          "visibility": "visible" if ground_truth else "clean" if sample["defect_type"] in CLEAN_KINDS else "hidden_defect",
                          **metric_counts(tp, fp, int(bool(ground_truth) and not matched), 1)})
    def aggregate(rows):
        return metric_counts(*(sum(row[key] for row in rows) for key in ("tp", "fp", "fn", "images")))
    grouped = {}
    for axis in ("scenario", "lighting", "visibility"):
        values = defaultdict(list)
        for row in per_image:
            values[row[axis]].append(row)
        grouped[axis] = {key: aggregate(rows) for key, rows in sorted(values.items())}
    result = {"confidence_threshold": confidence, "iou_threshold": iou_threshold, "split": split or "all",
              "metric": "Greedy score-ordered one-to-one class matching at one IoU threshold; not mAP",
              "overall": aggregate(per_image), "by": grouped, "per_image": per_image,
              "predictions_excluded_by_split": excluded, "limitation": LIMITATION}
    atomic_json(root / "evaluation.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "report", "coco", "evaluate"):
        sub = commands.add_parser(command)
        sub.add_argument("folder", type=Path)
        if command == "coco":
            sub.add_argument("--split-ratios", default="0,0,1", help="train,val,test group proportions; explicit manifest splits take priority")
        if command == "evaluate":
            sub.add_argument("predictions", type=Path)
            sub.add_argument("--confidence", type=float, default=.25)
            sub.add_argument("--iou", type=float, default=.5)
            sub.add_argument("--split", choices=SPLITS)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_dataset(args.folder)
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 1
        if args.command == "report":
            result = report_dataset(args.folder)
        elif args.command == "coco":
            result = export_coco(args.folder, tuple(map(float, args.split_ratios.split(","))))
        else:
            result = evaluate_dataset(args.folder, args.predictions, args.confidence, args.iou, args.split)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
