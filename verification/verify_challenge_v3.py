"""Audit the completed 96-image V3 starter without changing any render output."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dataset_tools import atomic_json, validate_dataset
from geometry import PipeSpec
from lighting_profiles import LIGHTING_IDS

VERIFICATION = Path(__file__).resolve().parent
STABLE_KEYS = tuple(PipeSpec.__dataclass_fields__) + (
    "roughness", "texture_strength", "wear", "finish_marks", "brass_green",
    "environment", "background", "camera_yaw", "camera_elevation", "camera_zoom",
    "camera_shift_x", "camera_shift_y", "focus_blur", "frame_aspect", "resolution",
    "samples")


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contact_sheet(folder, groups, specimen_number, kind):
    """Two environment rows by six lighting columns, preserving image aspect."""
    width, height = 320, 252
    sheet = Image.new("RGB", (width * len(LIGHTING_IDS), height * 2 + 38), "#101820")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 11), f"V3 {kind}: identical specimen and camera across lighting presets", fill="#edcc83")
    for row, environment in enumerate(("machine", "godslight")):
        specimen_id = f"{environment}_s{specimen_number:03d}"
        samples = {sample["lighting_profile"]: sample for sample in groups.get(specimen_id, [])}
        for column, light in enumerate(LIGHTING_IDS):
            left, top = column * width, row * height + 38
            draw.text((left + 8, top + 7), f"{environment.upper()} / {light}", fill="#edcc83")
            sample = samples.get(light)
            if sample is None:
                draw.text((left + 8, top + 76), "Missing sample", fill="#ed817d")
                continue
            with Image.open(folder / sample["image"]) as source:
                thumb = ImageOps.contain(source.convert("RGB"), (width - 8, height - 58))
                sheet.paste(thumb, (left + (width - thumb.width) // 2,
                                   top + 28 + (height - 58 - thumb.height) // 2))
            caption = f"{sample['defect_type']} / {sample.get('severity', 'unspecified')}"
            draw.text((left + 8, top + height - 21), caption, fill="#bdc8d0")
    path = VERIFICATION / f"challenge-v3-lighting-{kind}.jpg"
    sheet.save(path, quality=94)
    return str(path)


def verify(folder):
    folder = Path(folder).resolve()
    validation = validate_dataset(folder)
    errors = list(validation["errors"])
    result = {"dataset": str(folder), "validation": validation, "passed": False,
              "errors": errors, "expected_images": 96, "expected_specimens": 16,
              "expected_visible_boxes": 72}
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        samples = manifest["samples"]
        state = json.loads((folder / "status.json").read_text(encoding="utf-8"))
        if state.get("state") != "complete":
            errors.append(f"Generation is not complete: {state.get('state')}")
        if len(samples) != 96:
            errors.append(f"Expected 96 images, found {len(samples)}")
        groups = defaultdict(list)
        for sample in samples:
            groups[sample["specimen_id"]].append(sample)
        if len(groups) != 16:
            errors.append(f"Expected 16 independent specimens, found {len(groups)}")
        counts = dict(Counter(sample["defect_type"] for sample in samples))
        if counts != {"NONE": 24, "DENT": 36, "FOLD": 36}:
            errors.append(f"Unexpected class image counts: {counts}")
        visible = sum(bool(sample["bbox_xywh"]) for sample in samples)
        if visible != 72:
            errors.append(f"Expected 72 visible defect boxes, found {visible}; inspect hidden_defect_samples")
        result.update(image_count=len(samples), specimen_count=len(groups), class_image_counts=counts,
                      visible_boxes=visible,
                      hidden_defect_samples=[sample["sample_id"] for sample in samples
                                             if sample["defect_type"] != "NONE" and not sample["bbox_xywh"]])
        group_reports = {}
        output_hash_count = 0
        for specimen_id, views in sorted(groups.items()):
            lights = [sample["lighting_profile"] for sample in views]
            if len(lights) != 6 or set(lights) != set(LIGHTING_IDS):
                errors.append(f"{specimen_id}: missing/duplicate lighting profiles: {lights}")
            first = views[0]["parameters"]
            changed = sorted({key for sample in views for key in STABLE_KEYS
                              if key not in first or key not in sample["parameters"] or first[key] != sample["parameters"][key]})
            if changed:
                errors.append(f"{specimen_id}: geometry/camera/finish differs across lighting: {changed}")
            split_values = {sample.get("split") for sample in views}
            if split_values != {"test"}:
                errors.append(f"{specimen_id}: starter must be test-only, found {split_values}")
            mask_hashes, mask_pixel_hashes, beauty_hashes, beauty_pixel_hashes = set(), set(), set(), set()
            mask_metadata = defaultdict(set)
            for sample in views:
                if sample["lighting_profile"] != sample["parameters"].get("lighting_profile"):
                    errors.append(f"{sample['sample_id']}: lighting metadata disagrees with rendered parameters")
                expected_files = {sample["image"], sample["mask"],
                                  f"labels/{sample['sample_id']}.txt", f"metadata/{sample['sample_id']}.json"}
                recorded_hashes = sample.get("output_sha256", {})
                if set(recorded_hashes) != expected_files:
                    errors.append(f"{sample['sample_id']}: expected exactly four output hashes")
                for relative, expected in recorded_hashes.items():
                    path = (folder / relative).resolve()
                    if not path.is_relative_to(folder):
                        errors.append(f"{sample['sample_id']}: output hash path escapes dataset")
                    elif not path.is_file() or file_hash(path) != expected:
                        errors.append(f"{sample['sample_id']}: file hash mismatch: {relative}")
                    else:
                        output_hash_count += 1
                mask_hashes.add(file_hash(folder / sample["mask"]))
                with Image.open(folder / sample["mask"]) as source:
                    # PNG Date/RenderTime chunks vary per render. Compare native
                    # decoded pixels, dimensions and mode exactly, without tolerance.
                    header = f"{source.mode}:{source.width}x{source.height}:".encode("ascii")
                    mask_pixel_hashes.add(hashlib.sha256(header + source.tobytes()).hexdigest())
                    for key, value in source.info.items():
                        mask_metadata[key].add(repr(value))
                beauty_hashes.add(file_hash(folder / sample["image"]))
                with Image.open(folder / sample["image"]) as source:
                    beauty_pixel_hashes.add(hashlib.sha256(source.convert("RGB").tobytes()).hexdigest())
            if len(mask_pixel_hashes) != 1:
                errors.append(f"{specimen_id}: exact binary mask pixels change with lighting ({len(mask_pixel_hashes)} unique hashes)")
            if len(beauty_pixel_hashes) != 6:
                errors.append(f"{specimen_id}: expected six different beauty renders, found {len(beauty_pixel_hashes)} pixel hashes")
            group_reports[specimen_id] = {"images": len(views), "lighting_profiles": lights,
                                         "stable_fields_checked": len(STABLE_KEYS),
                                         "changed_stable_fields": changed,
                                         "unique_mask_byte_hashes": len(mask_hashes),
                                         "unique_mask_pixel_hashes": len(mask_pixel_hashes),
                                         "mask_metadata_variant_keys": sorted(key for key, values in mask_metadata.items() if len(values) > 1),
                                         "unique_beauty_byte_hashes": len(beauty_hashes),
                                         "unique_beauty_pixel_hashes": len(beauty_pixel_hashes)}
        result.update(verified_output_hashes=output_hash_count, groups=group_reports,
                      mask_comparison="Exact decoded native pixel bytes, mode and dimensions; no tolerance. PNG metadata can differ by Date, RenderTime and Cycles timings. All recorded file hashes are still checked individually.")
        if validation["valid"]:
            result["contact_sheets"] = [contact_sheet(folder, groups, 3, "dent"),
                                        contact_sheet(folder, groups, 5, "fold")]
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"Audit could not finish: {type(exc).__name__}: {exc}")
    result["passed"] = not errors
    result["limitation"] = "Checks dataset integrity and paired-light consistency; no detector or real-world accuracy is evaluated."
    output = VERIFICATION / "challenge-v3-final.json"
    atomic_json(output, result)
    return result, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "examples" / "challenge-v3")
    args = parser.parse_args()
    result, output = verify(args.dataset)
    print(json.dumps({"passed": result["passed"], "report": str(output), "errors": result["errors"],
                      "image_count": result.get("image_count"), "visible_boxes": result.get("visible_boxes"),
                      "contact_sheets": result.get("contact_sheets", [])}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
