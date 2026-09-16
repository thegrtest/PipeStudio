import hashlib
import json
from pathlib import Path
import shutil
import unittest
import uuid

import numpy as np
from PIL import Image

from domain_review import validate_dataset, write_gallery


class DomainReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture_root = (Path(__file__).parent / "verification" / ".domain-review-tests").resolve()
        self.root = self.fixture_root / uuid.uuid4().hex
        for name in ("images", "labels", "masks", "metadata"):
            (self.root / "all" / name).mkdir(parents=True, exist_ok=True)
        self.records = []
        self.add_sample("one")

    def tearDown(self):
        if self.root.resolve().is_relative_to(self.fixture_root) and self.root != self.fixture_root:
            shutil.rmtree(self.root)

    def add_sample(self, sid, empty=False):
        image_path = self.root / "all" / "images" / f"{sid}.png"
        Image.new("RGB", (80, 60), "#846331").save(image_path)
        label_path = self.root / "all" / "labels" / f"{sid}.txt"
        label_path.write_text("" if empty else "0 0.25 0.25 0.25 0.16666667\n")
        row = {
            "sample_id": sid, "image": f"images/{sid}.png", "width": 80, "height": 60,
            "setup": "GODS_CAM2534", "primary_kind": "NONE" if empty else "FOLD",
            "surface_condition": "clean", "split": "train", "parameters": {}, "instances": [],
        }
        files = [image_path, label_path]
        if not empty:
            mask_path = self.root / "all" / "masks" / f"{sid}_00.png"
            mask = np.zeros((60, 80), dtype=np.uint8)
            mask[10:20, 10:30] = 255
            Image.fromarray(mask).save(mask_path)
            files.append(mask_path)
            row["instances"] = [{"class_id": 0, "kind": "FOLD", "mask": f"masks/{sid}_00.png", "bbox_xywh": [10, 10, 20, 10], "visible_mask_pixels": 200}]
        metadata_path = self.root / "all" / "metadata" / f"{sid}.json"
        metadata_path.write_text(json.dumps(row))
        files.append(metadata_path)
        row["output_sha256"] = {p.relative_to(self.root / "all").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        self.records.append(row)
        self.save_manifest()

    def save_manifest(self):
        (self.root / "render_plan.json").write_text(json.dumps({"samples": [{"sample_id": r["sample_id"]} for r in self.records]}))
        (self.root / "all" / "manifest.json").write_text(json.dumps({"classes": {0: "Fold", 1: "Dent", 2: "Soap stain", 3: "Oil stain"}, "samples": self.records}))

    def codes(self, report):
        return {item["code"] for item in report["errors"]}

    def test_valid_dataset_and_gallery(self):
        report, rows = validate_dataset(self.root)
        self.assertTrue(report["valid"], report["errors"])
        self.assertTrue(report["complete"])
        self.assertEqual(report["box_sizes_at_640_by_class"]["0"]["short_side_q10_q50_q90"], [80., 80., 80.])
        write_gallery(self.root, report, rows)
        self.assertTrue((self.root / "index.html").is_file())
        with Image.open(self.root / "contact_sheet.png") as image:
            image.verify()

    def test_missing_label_is_rejected(self):
        (self.root / "all" / "labels" / "one.txt").unlink()
        report, _ = validate_dataset(self.root)
        self.assertFalse(report["valid"])
        self.assertIn("missing_labels", self.codes(report))

    def test_bbox_mismatch_is_rejected_even_with_updated_hash(self):
        path = self.root / "all" / "labels" / "one.txt"
        path.write_text("0 0.8 0.8 0.1 0.1\n")
        self.records[0]["output_sha256"]["labels/one.txt"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save_manifest()
        report, _ = validate_dataset(self.root)
        self.assertIn("label_bbox_mismatch", self.codes(report))

    def test_duplicate_image_bytes_are_rejected(self):
        self.add_sample("two")
        report, _ = validate_dataset(self.root)
        self.assertIn("duplicate_image_bytes", self.codes(report))

    def test_mask_corruption_is_rejected(self):
        path = self.root / "all" / "masks" / "one_00.png"
        with Image.open(path) as image:
            mask = np.array(image)
        mask[3, 4] = 120
        Image.fromarray(mask).save(path)
        report, _ = validate_dataset(self.root)
        self.assertTrue({"mask_binary", "mask_bbox", "mask_pixel_count", "output_hash_mismatch"} <= self.codes(report))

    def test_plan_incompleteness_is_explicit(self):
        (self.root / "render_plan.json").write_text(json.dumps({"samples": [{"sample_id": "one"}, {"sample_id": "two"}]}))
        report, _ = validate_dataset(self.root)
        self.assertIn("committed_count", self.codes(report))
        report, _ = validate_dataset(self.root, allow_incomplete=True)
        self.assertTrue(report["valid"])
        self.assertFalse(report["complete"])
        self.assertTrue(report["warnings"])

    def test_blender_rgb_and_rgba_binary_masks_are_valid(self):
        path = self.root / "all" / "masks" / "one_00.png"
        for mode in ("RGB", "RGBA"):
            with Image.open(path) as image:
                mask = image.convert(mode)
            mask.save(path)
            self.records[0]["output_sha256"]["masks/one_00.png"] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.save_manifest()
            report, _ = validate_dataset(self.root)
            self.assertTrue(report["valid"], report["errors"])

    def test_colored_mask_is_rejected(self):
        path = self.root / "all" / "masks" / "one_00.png"
        with Image.open(path) as image:
            mask = np.array(image.convert("RGB"))
        mask[10, 10, 1] = 0
        Image.fromarray(mask).save(path)
        report, _ = validate_dataset(self.root)
        self.assertIn("mask_color_planes", self.codes(report))

    def test_missing_planned_instance_cannot_become_good(self):
        planned = {"sample_id": "one", "primary_kind": "FOLD", "instances": [{"kind": "FOLD", "class_id": 0}, {"kind": "OIL_STAIN", "class_id": 3}]}
        (self.root / "render_plan.json").write_text(json.dumps({"samples": [planned]}))
        report, _ = validate_dataset(self.root)
        self.assertIn("plan_sample_mismatch", self.codes(report))

    def test_float32_parameters_and_record_only_timing_are_valid(self):
        self.records[0]["parameters"] = {"roughness": float(np.float32(.35)), "seed": 21}
        self.records[0]["generation_seconds"] = 3.14
        self.save_manifest()
        planned = {"sample_id": "one", "settings": {"roughness": .35, "seed": 21}, "instances": [{"kind": "FOLD", "class_id": 0}]}
        (self.root / "render_plan.json").write_text(json.dumps({"samples": [planned]}))
        report, _ = validate_dataset(self.root)
        self.assertTrue(report["valid"], report["errors"])

    def test_glare_is_remeasured_instead_of_trusting_passed_flag(self):
        row=self.records[0]
        row['glare_guard']={'passed':True}
        row['pipe_mask']=row['instances'][0]['mask']
        Image.new('RGB',(80,60),'white').save(self.root/'all'/row['image'])
        self.save_manifest()
        report,_=validate_dataset(self.root)
        self.assertIn('obscuring_glare',self.codes(report))


if __name__ == "__main__":
    unittest.main()
