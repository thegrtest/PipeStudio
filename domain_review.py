"""Validate a committed domain dataset and write an inspectable HTML gallery.

Usage: python domain_review.py OUTPUT [--allow-incomplete]

Only OUTPUT/validation.json, OUTPUT/index.html and OUTPUT/contact_sheet.png are
written. Images, labels, masks, plans and manifests are never modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import quote

import numpy as np
from PIL import Image, ImageDraw, ImageOps


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(root, value, fallback=None):
    """Accept paths relative to the run or its all directory, confined to run."""
    value = fallback if not value else value
    if not isinstance(value, str):
        raise ValueError("expected a relative file path")
    path = Path(value.replace("\\", "/"))
    if path.is_absolute() or path.drive or ".." in path.parts:
        raise ValueError(f"unsafe manifest path: {value}")
    path = (root / path) if path.parts and path.parts[0] == "all" else (root / "all" / path)
    path = path.resolve()
    if not path.is_relative_to((root / "all").resolve()):
        raise ValueError(f"manifest path leaves all/: {value}")
    return path


def _quantiles(values):
    if not values:
        return {"count": 0}
    data = np.asarray(values, dtype=float)
    return {
        "count": len(values),
        "width_q10_q50_q90": np.quantile(data[:, 0], [.1, .5, .9]).round(3).tolist(),
        "height_q10_q50_q90": np.quantile(data[:, 1], [.1, .5, .9]).round(3).tolist(),
        "short_side_q10_q50_q90": np.quantile(data.min(axis=1), [.1, .5, .9]).round(3).tolist(),
        "aspect_ratio_q10_q50_q90": np.quantile(data.max(axis=1) / np.maximum(data.min(axis=1), 1e-8), [.1, .5, .9]).round(3).tolist(),
    }


def _read_labels(path):
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        values = [float(v) for v in line.split()]
        if len(values) != 5 or not np.isfinite(values).all():
            raise ValueError(f"line {line_no}: expected five finite YOLO values")
        if values[0] not in (0, 1, 2, 3):
            raise ValueError(f"line {line_no}: class must be 0..3")
        if not (0 <= values[1] <= 1 and 0 <= values[2] <= 1 and 0 < values[3] <= 1 and 0 < values[4] <= 1):
            raise ValueError(f"line {line_no}: invalid normalized box")
        rows.append(values)
    return rows


def _matches_expected(actual, expected):
    """Allow FloatProperty roundoff, but require every originally planned field."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and _matches_expected(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_matches_expected(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, bool) or isinstance(expected, str) or expected is None:
        return type(actual) is type(expected) and actual == expected
    if isinstance(expected, int) and not isinstance(expected, bool):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual == expected
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and bool(np.isclose(actual, expected, rtol=2e-6, atol=2e-6))
    return actual == expected


def validate_dataset(output, *, allow_incomplete=False):
    root = Path(output).resolve()
    problems = []
    warnings = []
    records = []
    counts = {name: Counter() for name in ("setup", "primary_kind", "surface_condition", "split", "instance_class", "instance_kind")}
    sizes = defaultdict(list)
    setup_sizes = defaultdict(lambda: defaultdict(list))
    hash_owners = {}
    image_paths = set()
    sample_ids = set()
    planned_rows = {}

    def error(code, detail, sample=None):
        problems.append({"code": code, "sample_id": sample, "detail": str(detail)})

    try:
        manifest = json.loads((root / "all" / "manifest.json").read_text(encoding="utf-8-sig"))
        records = manifest.get("samples", [])
        if not isinstance(records, list):
            raise ValueError("manifest.samples must be a list")
        classes = manifest.get("classes", {})
        ids = set(range(len(classes))) if isinstance(classes, list) else {int(key) for key in classes}
        if ids != {0, 1, 2, 3}:
            error("class_mapping", "manifest.classes must define exactly IDs 0, 1, 2, 3")
    except Exception as exc:
        error("manifest", exc)
        records = []

    planned_count = None
    try:
        plan = json.loads((root / "render_plan.json").read_text(encoding="utf-8-sig"))
        planned = plan.get("samples")
        planned_count = len(planned) if isinstance(planned, list) else int(plan.get("total", plan.get("count")))
        if planned_count != len(records):
            detail = f"committed {len(records)} samples, planned {planned_count}"
            (warnings.append if allow_incomplete else lambda text: error("committed_count", text))(detail)
        if isinstance(planned, list) and all(isinstance(row, dict) and row.get("sample_id") for row in planned):
            planned_rows = {str(row["sample_id"]): row for row in planned}
            planned_ids = {str(row["sample_id"]) for row in planned}
            extra = {str(row.get("sample_id")) for row in records if isinstance(row, dict)} - planned_ids
            if extra:
                error("unexpected_samples", sorted(extra))
    except Exception as exc:
        error("render_plan", exc)

    for row in records:
        if not isinstance(row, dict):
            error("sample_record", "sample must be an object")
            continue
        sid = str(row.get("sample_id", ""))
        if not sid or sid in sample_ids:
            error("sample_id", f"empty or repeated sample ID {sid!r}", sid)
        sample_ids.add(sid)
        planned_row = planned_rows.get(sid, {})
        for field in ("setup", "primary_kind", "surface_condition", "split", "instances"):
            if field in planned_row and not _matches_expected(row.get(field), planned_row[field]):
                error("plan_sample_mismatch", field, sid)
        if "settings" in planned_row and not _matches_expected(row.get("parameters"), planned_row["settings"]):
            error("plan_parameters_mismatch", "exported parameters differ from planned settings", sid)
        for field in ("setup", "primary_kind", "surface_condition", "split"):
            counts[field][str(row.get(field, "unknown"))] += 1
        try:
            image_path = _resolve(root, row.get("image"), f"images/{sid}.png")
            if image_path in image_paths:
                error("duplicate_image_path", image_path.name, sid)
            image_paths.add(image_path)
            label_path = _resolve(root, row.get("label"), f"labels/{image_path.stem}.txt")
            metadata_path = _resolve(root, row.get("metadata"), f"metadata/{image_path.stem}.json")
            if image_path.stem != label_path.stem:
                error("stem_mismatch", f"{image_path.name} vs {label_path.name}", sid)
            with Image.open(image_path) as im:
                im.load()
                width, height = im.size
                if row.get('glare_guard'):
                    from glare_guard import assess
                    display_rgb=np.asarray(im.convert('RGB'),dtype=np.float32)/255
                    with Image.open(_resolve(root,row.get('pipe_mask'))) as silhouette:
                        pipe_support=np.asarray(silhouette.convert('L'))>127
                    supports=[]
                    for instance in row.get('instances',[]):
                        with Image.open(_resolve(root,instance['mask'])) as support:
                            supports.append(np.asarray(support.convert('L'))>127)
                    measured=assess(display_rgb,supports,pipe_support)
                    if not measured['passed'] or not row['glare_guard'].get('passed'):
                        error('obscuring_glare','Final image fails defect/pipe highlight limits',sid)
                if im.mode != "RGB":
                    error("image_mode", f"expected RGB, found {im.mode}", sid)
            if (row.get("width"), row.get("height")) != (width, height):
                error("image_dimensions", f"manifest {(row.get('width'), row.get('height'))}, image {(width, height)}", sid)
            digest = _sha256(image_path)
            if digest in hash_owners:
                error("duplicate_image_bytes", f"same image bytes as {hash_owners[digest]}", sid)
            else:
                hash_owners[digest] = sid
            labels = _read_labels(label_path)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            if not isinstance(metadata, dict):
                error("metadata", "metadata must be an object", sid)
            else:
                for key in ("sample_id", "image", "width", "height", "setup", "primary_kind", "surface_condition", "instances", "glare_guard", "pipe_mask"):
                    if key in metadata and key in row and metadata[key] != row[key]:
                        error("metadata_mismatch", key, sid)
            required_files = {image_path, label_path, metadata_path}
            expected_labels = []
            instances = row.get("instances", [])
            if not isinstance(instances, list):
                raise ValueError("instances must be a list")
            for number, instance in enumerate(instances):
                if not isinstance(instance, dict):
                    error("instance_record", f"instance {number} is not an object", sid)
                    continue
                cid = instance.get("class_id")
                if cid not in (0, 1, 2, 3) or isinstance(cid, bool):
                    error("instance_class", f"instance {number}: {cid}", sid)
                    continue
                counts["instance_class"][str(cid)] += 1
                counts["instance_kind"][str(instance.get("kind", cid))] += 1
                mask_path = _resolve(root, instance.get("mask"), f"masks/{image_path.stem}_{number:02d}.png")
                required_files.add(mask_path)
                with Image.open(mask_path) as mask_image:
                    if mask_image.format != "PNG":
                        error("mask_format", f"instance {number}: expected PNG", sid)
                    mask = np.asarray(mask_image)
                # Blender stores pixels internally as RGBA even when it saves
                # PNG RGB. Replicated binary planes are equivalent to an L mask.
                if mask.ndim == 3 and mask.shape[2] in (3, 4):
                    if not (np.array_equal(mask[:, :, 0], mask[:, :, 1]) and np.array_equal(mask[:, :, 0], mask[:, :, 2])):
                        error("mask_color_planes", f"instance {number}: RGB channels differ", sid)
                    if mask.shape[2] == 4 and not np.all(mask[:, :, 3] == np.iinfo(mask.dtype).max):
                        error("mask_alpha", f"instance {number}: alpha must be fully opaque", sid)
                    mask = mask[:, :, 0]
                if mask.ndim != 2 or mask.shape != (height, width):
                    error("mask_dimensions", f"instance {number}: expected {(height, width)}, got {mask.shape}", sid)
                    continue
                unique = set(np.unique(mask).tolist())
                if not (unique <= {0, 255} or unique <= {0, 1}):
                    error("mask_binary", f"instance {number}: values {sorted(unique)[:12]}", sid)
                ys, xs = np.nonzero(mask)
                pixels = len(xs)
                if pixels == 0:
                    error("empty_instance_mask", f"instance {number}", sid)
                    continue
                if instance.get("visible_mask_pixels") != pixels:
                    error("mask_pixel_count", f"instance {number}: metadata {instance.get('visible_mask_pixels')}, actual {pixels}", sid)
                x, y = int(xs.min()), int(ys.min())
                w, h = int(xs.max()) + 1 - x, int(ys.max()) + 1 - y
                actual_bbox = [x, y, w, h]
                if instance.get("bbox_xywh") != actual_bbox:
                    error("mask_bbox", f"instance {number}: metadata {instance.get('bbox_xywh')}, actual {actual_bbox}", sid)
                expected_labels.append([cid, (x + w / 2) / width, (y + h / 2) / height, w / width, h / height])
                projected = [w * 640 / max(width, height), h * 640 / max(width, height)]
                sizes[str(cid)].append(projected)
                setup_sizes[str(row.get("setup", "unknown"))][str(cid)].append(projected)
            unmatched = list(labels)
            for expected in expected_labels:
                match = next((idx for idx, label in enumerate(unmatched) if label[0] == expected[0] and np.allclose(label[1:], expected[1:], rtol=0, atol=2e-5)), None)
                if match is None:
                    error("label_bbox_mismatch", f"no label matches mask box {expected}", sid)
                else:
                    unmatched.pop(match)
            if unmatched or len(labels) != len(instances):
                error("label_instance_count", f"labels {len(labels)}, instances {len(instances)}, unmatched labels {len(unmatched)}", sid)
            declared_hashes = row.get("output_sha256", {})
            if not isinstance(declared_hashes, dict):
                raise ValueError("output_sha256 must be a relative-path -> SHA256 object")
            hashed_files = set()
            for relative, expected_hash in declared_hashes.items():
                hashed_path = _resolve(root, relative)
                hashed_files.add(hashed_path)
                if _sha256(hashed_path) != expected_hash:
                    error("output_hash_mismatch", relative, sid)
            for missing_hash in required_files - hashed_files:
                error("missing_output_hash", str(missing_hash.relative_to(root)), sid)
        except Exception as exc:
            error("sample_files", f"{type(exc).__name__}: {exc}", sid)

    images_dir, labels_dir = root / "all" / "images", root / "all" / "labels"
    disk_images = {p.resolve() for p in images_dir.glob("*") if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}}
    image_stems = {p.stem for p in disk_images}
    label_stems = {p.stem for p in labels_dir.glob("*.txt")}
    if len(image_stems) != len(disk_images):
        error("duplicate_image_stems", "multiple image files share the same label stem")
    if image_stems - label_stems:
        error("missing_labels", sorted(image_stems - label_stems))
    if label_stems - image_stems:
        error("orphan_labels", sorted(label_stems - image_stems))
    if disk_images - image_paths:
        error("uncommitted_images", sorted(p.name for p in disk_images - image_paths))
    if image_paths - disk_images:
        error("missing_images", sorted(p.name for p in image_paths - disk_images))

    return {
        "schema_version": 1, "output": str(root), "valid": not problems,
        "complete": planned_count is not None and len(records) == planned_count and not problems,
        "planned_count": planned_count, "committed_count": len(records),
        "image_count": len(disk_images), "label_count": len(label_stems),
        "unique_image_hash_count": len(hash_owners), "errors": problems, "warnings": warnings,
        "counts": {key: dict(value) for key, value in counts.items()},
        "box_sizes_at_640_by_class": {key: _quantiles(value) for key, value in sizes.items()},
        "box_sizes_at_640_by_setup_and_class": {setup: {cid: _quantiles(value) for cid, value in classes.items()} for setup, classes in setup_sizes.items()},
    }, records


def _image_url(root, row):
    return quote(_resolve(root, row.get("image"), f"images/{row.get('sample_id')}.png").relative_to(root).as_posix(), safe="/")


def write_gallery(output, report, records):
    root = Path(output).resolve()
    cards = []
    contact_records = []
    representatives = set()
    for row in records:
        if not isinstance(row, dict):
            continue
        try:
            url = _image_url(root, row)
            image_path = _resolve(root, row.get("image"), f"images/{row.get('sample_id')}.png")
            setup = str(row.get("setup", "unknown"))
            kind = str(row.get("primary_kind", "unknown"))
            instance_list = row.get("instances", [])
            classes = ", ".join(str(item.get("kind", item.get("class_id"))) for item in instance_list if isinstance(item, dict)) or "good / no defects"
            caption = f"{row.get('sample_id', '')} · {setup} · {kind} · {row.get('surface_condition', '')}"
            cards.append(f'<article data-filter="{html.escape(caption.lower(), quote=True)}"><a href="{url}"><img loading="lazy" src="{url}" alt="{html.escape(caption, quote=True)}"></a><p>{html.escape(caption)}</p><small>{html.escape(classes)}</small></article>')
            # At most one good/fold/dent/stain view per setup, up to 32 tiles.
            bucket = "good" if not instance_list else ("fold" if kind.upper() == "FOLD" else "dent" if kind.upper() == "DENT" else "stain")
            key = (setup, bucket)
            if key not in representatives and image_path.is_file() and len(contact_records) < 32:
                representatives.add(key)
                contact_records.append((image_path, caption))
        except Exception:
            continue
    issues = "".join(f'<li>{html.escape(str(issue))}</li>' for issue in report["errors"][:30])
    status = "VALIDATED" if report["valid"] else "REVIEW FAILED"
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Domain render review</title>
<style>body{{margin:0;background:#101519;color:#e2e7e9;font:15px system-ui}}header{{padding:26px;position:sticky;top:0;background:#101519ed;z-index:1}}h1{{font-size:24px;margin:0 0 8px}}a{{color:#b4dce7}}input{{width:min(620px,90%);padding:12px;margin-top:14px;background:#253039;color:white;border:1px solid #53636e;border-radius:6px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px;padding:24px}}article{{background:#20282e;padding:9px;border-radius:8px}}img{{width:100%;aspect-ratio:1.59;object-fit:contain;background:#080b0e}}p{{font-size:13px;overflow-wrap:anywhere}}small{{color:#b6c3cc}}details{{padding:0 25px}}[hidden]{{display:none!important}}</style>
<header><h1>Domain render review · {status}</h1><div>{report['committed_count']} committed / {report['planned_count']} planned · {len(report['errors'])} errors · <a href="validation.json">Validation details</a> · <a href="contact_sheet.png">Contact sheet</a></div><input id="filter" placeholder="Filter by camera setup, defect, surface or sample ID" aria-label="Filter images"></header>
<details {'open' if issues else ''}><summary>Validation issues</summary><ul>{issues or '<li>All checks passed.</li>'}</ul></details><main>{''.join(cards)}</main>
<script>document.getElementById('filter').addEventListener('input',event=>{{const words=event.target.value.toLowerCase().split(/\\s+/).filter(Boolean);document.querySelectorAll('article').forEach(card=>{{card.hidden=!words.every(word=>card.dataset.filter.includes(word));}});}});</script></html>'''
    (root / "index.html").write_text(page, encoding="utf-8")
    if contact_records:
        tile_w, tile_h, columns = 480, 340, 4
        sheet = Image.new("RGB", (columns * tile_w, ((len(contact_records) + columns - 1) // columns) * tile_h), "#151b20")
        draw = ImageDraw.Draw(sheet)
        for index, (path, caption) in enumerate(contact_records):
            x, y = (index % columns) * tile_w, (index // columns) * tile_h
            try:
                with Image.open(path) as im:
                    thumbnail = ImageOps.contain(im.convert("RGB"), (tile_w - 12, tile_h - 44))
                sheet.paste(thumbnail, (x + (tile_w - thumbnail.width) // 2, y))
                draw.text((x + 7, y + tile_h - 40), caption[:72], fill="white")
                draw.text((x + 7, y + tile_h - 23), caption[72:144], fill="#b8c6cf")
            except Exception:
                draw.text((x + 7, y + 12), "Image could not be decoded", fill="red")
        sheet.save(root / "contact_sheet.png")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--allow-incomplete", action="store_true", help="Allow fewer committed samples than planned; all committed files must still validate.")
    args = parser.parse_args(argv)
    if not args.output.is_dir():
        parser.error("OUTPUT must be an existing dataset run directory")
    report, records = validate_dataset(args.output, allow_incomplete=args.allow_incomplete)
    (args.output / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_gallery(args.output, report, records)
    print(json.dumps({key: report[key] for key in ("valid", "complete", "planned_count", "committed_count", "image_count", "label_count", "errors")}, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
